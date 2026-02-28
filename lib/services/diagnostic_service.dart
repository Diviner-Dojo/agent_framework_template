// ===========================================================================
// file: lib/services/diagnostic_service.dart
// purpose: Active health check runner for developer diagnostics.
//
// Unlike AppLogger (passive recording), this service actively probes
// each subsystem and returns structured pass/fail results. Used by the
// diagnostics screen to verify the full initialization chain on-device.
//
// Checks: environment config, connectivity, Supabase reachability,
//   Claude API proxy, layer selection, SharedPreferences, TTS proxy,
//   local LLM status.
//
// See: Runtime Observability plan
// ===========================================================================

import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../config/environment.dart';
import '../repositories/agent_repository.dart';
import '../services/connectivity_service.dart';

/// Result of a single diagnostic check.
class DiagnosticResult {
  /// Human-readable name of the check (e.g., "Claude API Proxy").
  final String name;

  /// Whether the check passed.
  final bool passed;

  /// Detail about the result (e.g., "200 OK in 340ms" or "timeout").
  final String detail;

  /// How long the check took to run.
  final Duration elapsed;

  /// Creates a diagnostic result.
  const DiagnosticResult({
    required this.name,
    required this.passed,
    required this.detail,
    required this.elapsed,
  });
}

/// Runs active health checks against all app subsystems.
///
/// Each check has a 10-second timeout. Results are returned as a list
/// of [DiagnosticResult] for display in the diagnostics screen.
class DiagnosticService {
  final Environment _env;
  final ConnectivityService? _connectivityService;
  final AgentRepository? _agentRepository;
  final SharedPreferences? _prefs;
  final Dio _dio;

  /// Creates a DiagnosticService.
  ///
  /// All parameters are optional to allow partial diagnostics when
  /// some services are unavailable.
  DiagnosticService({
    Environment env = const Environment(),
    ConnectivityService? connectivityService,
    AgentRepository? agentRepository,
    SharedPreferences? prefs,
    Dio? dio,
  }) : _env = env,
       _connectivityService = connectivityService,
       _agentRepository = agentRepository,
       _prefs = prefs,
       _dio = dio ?? Dio();

  /// Run all diagnostic checks and return the results.
  Future<List<DiagnosticResult>> runAll() async {
    final results = <DiagnosticResult>[];

    results.add(await _checkEnvironment());
    results.add(await _checkConnectivity());
    results.add(await _checkSupabaseReachability());
    results.add(await _checkClaudeProxy());
    results.add(_checkLayerSelection());
    results.add(_checkSharedPreferences());
    results.add(await _checkTtsProxy());
    results.add(_checkLocalLlm());

    return results;
  }

  /// Check 1: Environment configuration.
  Future<DiagnosticResult> _checkEnvironment() async {
    final sw = Stopwatch()..start();
    final configured = _env.isConfigured;
    final urlSet = _env.supabaseUrl.isNotEmpty;
    final keySet = _env.supabaseAnonKey.isNotEmpty;
    sw.stop();

    return DiagnosticResult(
      name: 'Environment Config',
      passed: configured,
      detail: configured
          ? 'SUPABASE_URL: set, SUPABASE_ANON_KEY: set'
          : 'SUPABASE_URL: ${urlSet ? "set" : "empty"}, '
                'SUPABASE_ANON_KEY: ${keySet ? "set" : "empty"}',
      elapsed: sw.elapsed,
    );
  }

  /// Check 2: Network connectivity.
  Future<DiagnosticResult> _checkConnectivity() async {
    final sw = Stopwatch()..start();
    if (_connectivityService == null) {
      sw.stop();
      return DiagnosticResult(
        name: 'Network Connectivity',
        passed: false,
        detail: 'ConnectivityService not available',
        elapsed: sw.elapsed,
      );
    }

    final online = _connectivityService.isOnline;
    sw.stop();

    return DiagnosticResult(
      name: 'Network Connectivity',
      passed: online,
      detail: online ? 'Online' : 'Offline (no network detected)',
      elapsed: sw.elapsed,
    );
  }

  /// Check 3: Supabase REST API reachability.
  Future<DiagnosticResult> _checkSupabaseReachability() async {
    final sw = Stopwatch()..start();

    if (!_env.isConfigured) {
      sw.stop();
      return DiagnosticResult(
        name: 'Supabase Reachability',
        passed: false,
        detail: 'Skipped — environment not configured',
        elapsed: sw.elapsed,
      );
    }

    try {
      final response = await _dio
          .get(
            '${_env.supabaseUrl}/rest/v1/',
            options: Options(
              headers: {
                'apikey': _env.supabaseAnonKey,
                'Authorization': 'Bearer ${_env.supabaseAnonKey}',
              },
              receiveTimeout: const Duration(seconds: 10),
              sendTimeout: const Duration(seconds: 10),
            ),
          )
          .timeout(const Duration(seconds: 10));
      sw.stop();

      return DiagnosticResult(
        name: 'Supabase Reachability',
        passed: response.statusCode == 200,
        detail: '${response.statusCode} in ${sw.elapsedMilliseconds}ms',
        elapsed: sw.elapsed,
      );
    } on Exception catch (e) {
      sw.stop();
      return DiagnosticResult(
        name: 'Supabase Reachability',
        passed: false,
        detail: _friendlyError(e),
        elapsed: sw.elapsed,
      );
    }
  }

  /// Check 4: Claude API proxy Edge Function.
  Future<DiagnosticResult> _checkClaudeProxy() async {
    final sw = Stopwatch()..start();

    if (!_env.isConfigured) {
      sw.stop();
      return DiagnosticResult(
        name: 'Claude API Proxy',
        passed: false,
        detail: 'Skipped — environment not configured',
        elapsed: sw.elapsed,
      );
    }

    try {
      final response = await _dio
          .post(
            _env.claudeProxyUrl,
            data: {
              'messages': [
                {'role': 'user', 'content': 'ping'},
              ],
              'mode': 'chat',
            },
            options: Options(
              headers: {
                'apikey': _env.supabaseAnonKey,
                'Authorization': 'Bearer ${_env.supabaseAnonKey}',
                'Content-Type': 'application/json',
              },
              receiveTimeout: const Duration(seconds: 10),
              sendTimeout: const Duration(seconds: 10),
            ),
          )
          .timeout(const Duration(seconds: 10));
      sw.stop();

      final statusOk =
          response.statusCode != null &&
          response.statusCode! >= 200 &&
          response.statusCode! < 300;

      return DiagnosticResult(
        name: 'Claude API Proxy',
        passed: statusOk,
        detail: '${response.statusCode} in ${sw.elapsedMilliseconds}ms',
        elapsed: sw.elapsed,
      );
    } on Exception catch (e) {
      sw.stop();
      return DiagnosticResult(
        name: 'Claude API Proxy',
        passed: false,
        detail: _friendlyError(e),
        elapsed: sw.elapsed,
      );
    }
  }

  /// Check 5: Layer selection.
  DiagnosticResult _checkLayerSelection() {
    final sw = Stopwatch()..start();

    if (_agentRepository == null) {
      sw.stop();
      return DiagnosticResult(
        name: 'Layer Selection',
        passed: false,
        detail: 'AgentRepository not available',
        elapsed: sw.elapsed,
      );
    }

    final label = _agentRepository.activeLayerLabel;
    sw.stop();

    return DiagnosticResult(
      name: 'Layer Selection',
      passed: label != 'Offline',
      detail: 'Active layer: $label',
      elapsed: sw.elapsed,
    );
  }

  /// Check 6: SharedPreferences.
  DiagnosticResult _checkSharedPreferences() {
    final sw = Stopwatch()..start();

    if (_prefs == null) {
      sw.stop();
      return DiagnosticResult(
        name: 'SharedPreferences',
        passed: false,
        detail: 'Not loaded',
        elapsed: sw.elapsed,
      );
    }

    final preferClaude = _prefs.getBool('preferClaude') ?? false;
    final journalOnly = _prefs.getBool('journalOnlyMode') ?? false;
    sw.stop();

    return DiagnosticResult(
      name: 'SharedPreferences',
      passed: true,
      detail: 'preferClaude=$preferClaude, journalOnlyMode=$journalOnly',
      elapsed: sw.elapsed,
    );
  }

  /// Check 7: ElevenLabs TTS proxy reachability.
  Future<DiagnosticResult> _checkTtsProxy() async {
    final sw = Stopwatch()..start();

    if (!_env.isConfigured) {
      sw.stop();
      return DiagnosticResult(
        name: 'TTS Proxy',
        passed: false,
        detail: 'Skipped — environment not configured',
        elapsed: sw.elapsed,
      );
    }

    try {
      // HEAD request to check reachability — the Edge Function may return
      // an error for HEAD but that still proves network reachability.
      final response = await _dio
          .head(
            _env.elevenlabsProxyUrl,
            options: Options(
              headers: {
                'apikey': _env.supabaseAnonKey,
                'Authorization': 'Bearer ${_env.supabaseAnonKey}',
              },
              receiveTimeout: const Duration(seconds: 10),
              sendTimeout: const Duration(seconds: 10),
              // Accept any status — we just want to know if reachable.
              validateStatus: (_) => true,
            ),
          )
          .timeout(const Duration(seconds: 10));
      sw.stop();

      return DiagnosticResult(
        name: 'TTS Proxy',
        passed: true,
        detail:
            'Reachable (${response.statusCode}) in '
            '${sw.elapsedMilliseconds}ms',
        elapsed: sw.elapsed,
      );
    } on Exception catch (e) {
      sw.stop();
      return DiagnosticResult(
        name: 'TTS Proxy',
        passed: false,
        detail: _friendlyError(e),
        elapsed: sw.elapsed,
      );
    }
  }

  /// Check 8: Local LLM status.
  DiagnosticResult _checkLocalLlm() {
    final sw = Stopwatch()..start();

    if (_agentRepository == null) {
      sw.stop();
      return DiagnosticResult(
        name: 'Local LLM',
        passed: false,
        detail: 'AgentRepository not available',
        elapsed: sw.elapsed,
      );
    }

    // The layer label tells us if local LLM is the active layer.
    // There's no public API to check model status directly, so we
    // report what we can observe.
    final label = _agentRepository.activeLayerLabel;
    final isLocalLlm = label == 'Local LLM';
    sw.stop();

    return DiagnosticResult(
      name: 'Local LLM',
      passed: isLocalLlm,
      detail: isLocalLlm ? 'Loaded and active' : 'Not active (layer: $label)',
      elapsed: sw.elapsed,
    );
  }

  /// Convert an exception to a short, friendly error string.
  String _friendlyError(Exception e) {
    if (e is DioException) {
      return switch (e.type) {
        DioExceptionType.connectionTimeout => 'Connection timeout',
        DioExceptionType.sendTimeout => 'Send timeout',
        DioExceptionType.receiveTimeout => 'Receive timeout',
        DioExceptionType.connectionError => 'Connection error: ${e.message}',
        _ => 'HTTP error: ${e.message}',
      };
    }
    return e.toString();
  }
}
