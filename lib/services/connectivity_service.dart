// ===========================================================================
// file: lib/services/connectivity_service.dart
// purpose: Wraps the connectivity_plus plugin to provide a simple
//          online/offline check for the LLM fallback decision.
//
// The AgentRepository uses this to decide whether to call Claude (online)
// or fall back to the rule-based agent (offline). This is a point-in-time
// snapshot — if connectivity drops DURING a dio call, the timeout/catch
// path in AgentRepository handles the fallback.
//
// Design:
//   - Stream-based monitoring via connectivity_plus
//   - isOnline getter for point-in-time checks
//   - Riverpod provider for dependency injection
//   - Testable via constructor injection (accepts a stream)
//
// TOCTOU Note:
//   There is an inherent time-of-check-to-time-of-use gap between
//   checking isOnline and dispatching the HTTP call. This is handled
//   by the timeout + catch fallback in AgentRepository, not by the
//   connectivity check itself. The connectivity check is an optimization
//   to avoid unnecessary network calls when we KNOW we're offline.
//
// See: ADR-0006 (Three-Layer Agent Design — Layer B online check)
// ===========================================================================

import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';

/// Service that monitors network connectivity state.
///
/// Provides a simple [isOnline] getter and a [onConnectivityChanged] stream
/// for reactive updates. Used by AgentRepository to decide between
/// Claude API (online) and rule-based agent (offline).
class ConnectivityService {
  final Connectivity _connectivity;
  final Stream<List<ConnectivityResult>> _connectivityStream;

  /// The most recent connectivity results from the platform.
  List<ConnectivityResult> _currentStatus = [];

  /// Subscription to the connectivity stream.
  StreamSubscription<List<ConnectivityResult>>? _subscription;

  /// Creates a ConnectivityService.
  ///
  /// [connectivity] — the connectivity_plus instance (injectable for testing).
  /// [connectivityStream] — optional stream override for testing.
  ConnectivityService({
    Connectivity? connectivity,
    Stream<List<ConnectivityResult>>? connectivityStream,
  }) : _connectivity = connectivity ?? Connectivity(),
       _connectivityStream =
           connectivityStream ??
           (connectivity ?? Connectivity()).onConnectivityChanged;

  /// Initialize the service by checking current connectivity and
  /// subscribing to changes.
  ///
  /// Call this once at app startup. Safe to call multiple times
  /// (subsequent calls are no-ops).
  // coverage:ignore-start
  Future<void> initialize() async {
    if (_subscription != null) return; // Already initialized

    // Get the initial connectivity state.
    _currentStatus = await _connectivity.checkConnectivity();

    // Subscribe to changes.
    _subscription = _connectivityStream.listen((results) {
      _currentStatus = results;
    });
  }
  // coverage:ignore-end

  /// Whether the device currently has network connectivity.
  ///
  /// Returns true if ANY connection type other than "none" is active.
  /// This checks for wifi, mobile, ethernet, vpn, etc.
  ///
  /// Note: This does NOT guarantee the network is actually reachable
  /// (e.g., captive portals). The dio timeout handles unreachable cases.
  bool get isOnline {
    if (_currentStatus.isEmpty) return false;
    return !_currentStatus.every((result) => result == ConnectivityResult.none);
  }

  /// Stream of connectivity changes for reactive updates.
  ///
  /// Each emission is a list of active connection types. If the list
  /// contains only ConnectivityResult.none, the device is offline.
  Stream<List<ConnectivityResult>> get onConnectivityChanged =>
      _connectivityStream;

  /// Clean up the subscription when the service is no longer needed.
  void dispose() {
    _subscription?.cancel();
    _subscription = null;
  }
}
