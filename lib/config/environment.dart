// ===========================================================================
// file: lib/config/environment.dart
// purpose: Externalized configuration for the Supabase Edge Function and
//          Claude API proxy. Values are injected at compile time via
//          --dart-define flags, NOT hardcoded.
//
// Usage (build command):
//   flutter run \
//     --dart-define=SUPABASE_URL=https://your-project.supabase.co \
//     --dart-define=SUPABASE_ANON_KEY=eyJ... \
//     --dart-define=CLAUDE_PROXY_TIMEOUT=30
//
// SECURITY NOTE:
//   String.fromEnvironment bakes values into the compiled binary. They are
//   extractable from the APK via `strings` or apktool. This is acceptable
//   because:
//     - The Supabase anon key is semi-public by design (RLS enforces access
//       control, not the key itself)
//     - The genuine secret is ANTHROPIC_API_KEY inside the Edge Function,
//       which NEVER reaches the client (ADR-0005)
//     - Phase 4 adds JWT-based auth for real access control
//
// See: ADR-0005 (Claude API via Supabase Edge Function Proxy)
// ===========================================================================

/// Compile-time environment configuration for the Claude API proxy.
///
/// All values come from `--dart-define` flags at build time. When values
/// are missing (empty string), [isConfigured] returns false and the app
/// uses Layer A (rule-based agent) exclusively.
class Environment {
  /// Supabase project URL (e.g., "https://abc123.supabase.co").
  /// Empty string when not provided via --dart-define.
  final String supabaseUrl;

  /// Supabase anonymous key for Edge Function access.
  /// Semi-public by design — RLS enforces real access control.
  final String supabaseAnonKey;

  /// Timeout in seconds for Claude API calls via the Edge Function.
  /// Defaults to 30 seconds if not specified.
  final int claudeProxyTimeoutSeconds;

  /// Creates an Environment with the given configuration values.
  ///
  /// The default constructor reads from compile-time --dart-define values.
  /// Use the named constructor [Environment.custom] for testing.
  const Environment({
    this.supabaseUrl = const String.fromEnvironment('SUPABASE_URL'),
    this.supabaseAnonKey = const String.fromEnvironment('SUPABASE_ANON_KEY'),
    this.claudeProxyTimeoutSeconds = const int.fromEnvironment(
      'CLAUDE_PROXY_TIMEOUT',
      defaultValue: 30,
    ),
  });

  /// Test-friendly constructor that accepts explicit values.
  const Environment.custom({
    required this.supabaseUrl,
    required this.supabaseAnonKey,
    this.claudeProxyTimeoutSeconds = 30,
  });

  /// The full URL for the Claude proxy Edge Function.
  ///
  /// Supabase Edge Functions are hosted at:
  ///   {supabaseUrl}/functions/v1/{function-name}
  String get claudeProxyUrl => '$supabaseUrl/functions/v1/claude-proxy';

  /// The full URL for the ElevenLabs TTS proxy Edge Function.
  ///
  /// See: ADR-0022 (Voice Engine Swap)
  String get elevenlabsProxyUrl => '$supabaseUrl/functions/v1/elevenlabs-proxy';

  /// The WebSocket URL for the Deepgram STT proxy Edge Function.
  ///
  /// Converts the HTTPS Supabase URL to WSS for WebSocket connections.
  /// The Deepgram API key lives in Supabase secrets — never in client code.
  ///
  /// See: ADR-0031 (Deepgram Nova-3 STT)
  String get deepgramProxyWsUrl {
    final wsBase = supabaseUrl
        .replaceFirst('https://', 'wss://')
        .replaceFirst('http://', 'ws://');
    return '$wsBase/functions/v1/deepgram-proxy';
  }

  /// Whether the environment is fully configured for Claude API access.
  ///
  /// Returns false when --dart-define values are missing. When false,
  /// ClaudeApiService disables itself and the app uses Layer A exclusively.
  bool get isConfigured => supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;

  /// Validates that the Supabase URL uses HTTPS.
  ///
  /// Returns true if configured with HTTPS or if not configured at all
  /// (unconfigured is safe — it just means Layer A only).
  /// Returns false only if configured with a non-HTTPS URL.
  bool get isSecure => !isConfigured || supabaseUrl.startsWith('https://');

  /// Timeout as a Duration for use with dio.
  Duration get claudeProxyTimeout =>
      Duration(seconds: claudeProxyTimeoutSeconds);
}
