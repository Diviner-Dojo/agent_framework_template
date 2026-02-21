// ===========================================================================
// file: lib/services/claude_api_service.dart
// purpose: HTTP client that calls the Claude API proxy Edge Function.
//
// This service handles all communication with the Supabase Edge Function
// that proxies Claude API calls. The Claude API key is NEVER in this code
// or anywhere in the Flutter app (ADR-0005).
//
// Responsibilities:
//   - POST conversation messages to the Edge Function
//   - Parse responses into typed AgentResponse objects
//   - Defensive metadata parsing (never throws on bad metadata)
//   - Configurable timeout with typed exceptions
//   - TLS enforcement (no SSL bypass)
//   - Debug-only logging (never log journal content in release)
//
// The service has two modes matching the Edge Function:
//   - "chat": Send conversation messages, get a follow-up response
//   - "metadata": Send full conversation, get structured metadata
//
// See: ADR-0005 (Claude API via Supabase Edge Function Proxy)
//      ADR-0012 (Optional Auth — JWT injection for authenticated users)
// ===========================================================================

import 'dart:convert';

import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../config/environment.dart';
import '../models/agent_response.dart';
import '../models/search_models.dart';

// ---------------------------------------------------------------------------
// Typed exceptions for error handling
// ---------------------------------------------------------------------------

/// Base exception for Claude API service errors.
///
/// All exceptions from this service extend this class, so callers can
/// catch [ClaudeApiException] to handle any service error generically,
/// or catch specific subtypes for targeted handling.
class ClaudeApiException implements Exception {
  final String message;
  const ClaudeApiException(this.message);

  @override
  String toString() => 'ClaudeApiException: $message';
}

/// The Edge Function is not configured (missing URL or anon key).
class ClaudeApiNotConfiguredException extends ClaudeApiException {
  const ClaudeApiNotConfiguredException()
    : super('Claude API proxy is not configured');
}

/// Network error (no connectivity, DNS failure, connection refused).
class ClaudeApiNetworkException extends ClaudeApiException {
  const ClaudeApiNetworkException(super.message);
}

/// The request timed out.
class ClaudeApiTimeoutException extends ClaudeApiException {
  const ClaudeApiTimeoutException() : super('Claude API request timed out');
}

/// The Edge Function returned an error status code.
class ClaudeApiServerException extends ClaudeApiException {
  final int statusCode;
  const ClaudeApiServerException(this.statusCode, super.message);
}

/// The response could not be parsed (missing required fields).
class ClaudeApiParseException extends ClaudeApiException {
  const ClaudeApiParseException(super.message);
}

// ---------------------------------------------------------------------------
// Service
// ---------------------------------------------------------------------------

/// HTTP client for the Claude API proxy Edge Function.
///
/// Uses [dio] for HTTP with configurable timeouts and TLS enforcement.
/// All methods throw typed [ClaudeApiException] subtypes on failure.
///
/// The service self-disables when [isConfigured] is false (missing
/// environment config). Callers should check [isConfigured] before
/// calling methods, or catch [ClaudeApiNotConfiguredException].
class ClaudeApiService {
  final Dio _dio;
  final Environment _environment;

  /// Optional callback that returns the current JWT access token.
  /// When provided and returns non-null, the JWT is sent as the Bearer
  /// token instead of the anon key. This enables authenticated Edge
  /// Function calls when the user is signed in (Phase 4).
  final String? Function()? _accessTokenProvider;

  /// Creates a ClaudeApiService with the given environment configuration.
  ///
  /// [environment] — provides the Edge Function URL, anon key, and timeout.
  /// [dio] — injectable for testing. If not provided, creates a default
  ///   Dio instance with TLS enforcement and appropriate timeouts.
  /// [accessTokenProvider] — optional callback returning the current JWT.
  ///   When provided and returns non-null, the JWT replaces the anon key
  ///   as the Bearer token for Edge Function auth.
  ClaudeApiService({
    required Environment environment,
    Dio? dio,
    String? Function()? accessTokenProvider,
  }) : _environment = environment,
       _accessTokenProvider = accessTokenProvider,
       _dio = dio ?? _createDefaultDio(environment);

  /// Create a properly configured Dio instance.
  ///
  /// Security requirements (per spec):
  ///   - No SSL certificate verification bypass
  ///   - No BadCertificateCallback overrides
  ///   - Logging only in debug mode (never log journal content in release)
  static Dio _createDefaultDio(Environment environment) {
    final dio = Dio(
      BaseOptions(
        connectTimeout: environment.claudeProxyTimeout,
        receiveTimeout: environment.claudeProxyTimeout,
        sendTimeout: environment.claudeProxyTimeout,
        headers: {
          'Content-Type': 'application/json',
          // Send the proxy access key as Bearer token for auth
          if (environment.supabaseAnonKey.isNotEmpty)
            'Authorization': 'Bearer ${environment.supabaseAnonKey}',
          // Supabase Edge Functions also accept the anon key in this header
          if (environment.supabaseAnonKey.isNotEmpty)
            'apikey': environment.supabaseAnonKey,
        },
      ),
    );

    // Only add logging in debug mode — NEVER log journal content in release.
    // Even in debug, we log headers only (not request/response bodies) to
    // avoid dumping personal journal entries to the console.
    if (kDebugMode) {
      dio.interceptors.add(
        LogInterceptor(
          requestBody: false, // Don't log journal messages
          responseBody: false, // Don't log Claude responses
          requestHeader: true,
          responseHeader: true,
        ),
      );
    }

    return dio;
  }

  /// Whether the service is configured and ready to make API calls.
  ///
  /// Returns false when environment variables are missing (no --dart-define).
  /// When false, AgentRepository should use Layer A (rule-based) exclusively.
  bool get isConfigured => _environment.isConfigured && _environment.isSecure;

  /// Send a chat message and get Claude's conversational response.
  ///
  /// [messages] — the conversation history as role/content pairs.
  /// [context] — optional session context (time of day, days since last, etc.)
  ///
  /// Returns the response text from Claude.
  /// Throws typed [ClaudeApiException] on any failure.
  Future<String> chat({
    required List<Map<String, String>> messages,
    Map<String, dynamic>? context,
  }) async {
    _ensureConfigured();

    final response = await _post({
      'messages': messages,
      'mode': 'chat',
      if (context != null) 'context': context,
    });

    final responseText = response['response'];
    if (responseText is! String || responseText.isEmpty) {
      throw const ClaudeApiParseException(
        'Missing or empty "response" field in Edge Function response',
      );
    }

    return responseText;
  }

  /// Extract structured metadata from a completed conversation.
  ///
  /// [messages] — the full conversation transcript.
  ///
  /// Returns an [AgentMetadata] with summary, mood tags, people, and topics.
  /// On metadata parse failure, returns [AgentMetadata] with all null fields
  /// (the session end flow must complete normally regardless).
  Future<AgentMetadata> extractMetadata({
    required List<Map<String, String>> messages,
  }) async {
    _ensureConfigured();

    final response = await _post({'messages': messages, 'mode': 'metadata'});

    // Try to parse metadata from the response
    final metadata = response['metadata'];
    if (metadata is Map<String, dynamic>) {
      return AgentMetadata.fromJson(metadata);
    }

    // If the Edge Function returned the raw text (parse failed server-side),
    // try to parse it ourselves as a fallback.
    final responseText = response['response'];
    if (responseText is String) {
      return _tryParseMetadataFromText(responseText);
    }

    // Nothing parseable — return empty metadata (not an error)
    return const AgentMetadata();
  }

  /// Send a recall query with journal context to get a grounded answer.
  ///
  /// [question] — the user's natural language question about their history.
  /// [contextEntries] — pre-serialized session context maps from
  ///   [SearchRepository.getSessionContext()]. Accepts Map<String, dynamic>
  ///   not domain types — serialization stays in the caller, keeping this
  ///   service as a transport layer (ADR-0013 §5).
  ///
  /// Returns a [RecallResponse] with the synthesized answer and cited session IDs.
  /// Missing `cited_sessions` in the response returns an empty list, not an
  /// exception (defensive parsing per qa-specialist).
  ///
  // NOTE: contextEntries contains raw journal content. NEVER enable
  // requestBody logging for this path (security-specialist).
  Future<RecallResponse> recall({
    required String question,
    required List<Map<String, dynamic>> contextEntries,
  }) async {
    _ensureConfigured();

    final response = await _post({
      'messages': [
        {'role': 'user', 'content': question},
      ],
      'mode': 'recall',
      'context_entries': contextEntries,
    });

    // Defensive parsing: extract answer and cited_sessions.
    // If fields are missing or wrong type, use safe defaults.
    final answer = response['response'];
    if (answer is! String || answer.isEmpty) {
      throw const ClaudeApiParseException(
        'Missing or empty "response" field in recall response',
      );
    }

    // cited_sessions may be missing entirely — return empty list, not error.
    final citedRaw = response['cited_sessions'];
    final citedSessionIds = <String>[];
    if (citedRaw is List) {
      for (final item in citedRaw) {
        if (item is String) {
          citedSessionIds.add(item);
        }
      }
    }

    return RecallResponse(answer: answer, citedSessionIds: citedSessionIds);
  }

  // =========================================================================
  // Private helpers
  // =========================================================================

  /// Ensure the service is configured before making API calls.
  void _ensureConfigured() {
    if (!isConfigured) {
      throw const ClaudeApiNotConfiguredException();
    }
  }

  /// Resolve per-request auth options.
  ///
  /// When an access token is available (user is authenticated), returns
  /// Options that override the Authorization header with the JWT.
  /// When not authenticated, returns null (uses default headers from Dio).
  Options? _resolveAuthOptions() {
    final token = _accessTokenProvider?.call();
    if (token != null && token.isNotEmpty) {
      return Options(headers: {'Authorization': 'Bearer $token'});
    }
    return null;
  }

  /// Make a POST request to the Edge Function.
  ///
  /// Handles all error translation from dio exceptions to typed
  /// [ClaudeApiException] subtypes.
  ///
  /// When an [_accessTokenProvider] is set and returns a JWT, it overrides
  /// the default Authorization header for this request.
  Future<Map<String, dynamic>> _post(Map<String, dynamic> body) async {
    try {
      // Build per-request headers. When authenticated, use JWT instead of anon key.
      final Options? options = _resolveAuthOptions();

      final response = await _dio.post<Map<String, dynamic>>(
        _environment.claudeProxyUrl,
        data: body,
        options: options,
      );

      final data = response.data;
      if (data == null) {
        throw const ClaudeApiParseException(
          'Empty response from Edge Function',
        );
      }

      return data;
    } on DioException catch (e) {
      switch (e.type) {
        case DioExceptionType.connectionTimeout:
        case DioExceptionType.sendTimeout:
        case DioExceptionType.receiveTimeout:
          throw const ClaudeApiTimeoutException();
        case DioExceptionType.connectionError:
          throw ClaudeApiNetworkException(
            'Network error: ${e.message ?? "connection failed"}',
          );
        case DioExceptionType.badResponse:
          final statusCode = e.response?.statusCode ?? 0;
          final errorBody = e.response?.data;
          final errorMessage = errorBody is Map
              ? (errorBody['error'] ?? 'Unknown error')
              : 'Server error';
          throw ClaudeApiServerException(statusCode, errorMessage.toString());
        default:
          throw ClaudeApiNetworkException(e.message ?? 'Unknown network error');
      }
    }
  }

  /// Try to parse metadata JSON from a raw text response.
  ///
  /// This is the client-side fallback when the Edge Function's server-side
  /// parse failed (METADATA_PARSE_ERROR). We strip markdown code fences
  /// and try jsonDecode.
  ///
  /// On any failure, returns empty AgentMetadata (never throws).
  AgentMetadata _tryParseMetadataFromText(String text) {
    try {
      // Strip markdown code fences if present
      final cleaned = text
          .replaceAll(RegExp(r'^```json?\s*', multiLine: true), '')
          .replaceAll(RegExp(r'```\s*$', multiLine: true), '')
          .trim();

      final json = jsonDecode(cleaned);
      if (json is Map<String, dynamic>) {
        return AgentMetadata.fromJson(json);
      }
    } on FormatException catch (e) {
      // JSON parse failure — not an error for the session end flow.
      if (kDebugMode) {
        debugPrint('Metadata parse failed (FormatException): $e');
      }
    } catch (e) {
      // Unexpected error (e.g., RangeError from regex) — still not fatal.
      if (kDebugMode) {
        debugPrint('Metadata parse failed (${e.runtimeType}): $e');
      }
    }
    return const AgentMetadata();
  }
}
