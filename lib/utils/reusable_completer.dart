// ===========================================================================
// file: lib/utils/reusable_completer.dart
// purpose: Drop-in Completer wrapper with double-completion guard, reset(),
//          and setTimeout(). Replaces scattered Completer + Timer + isCompleted
//          patterns that are prone to race conditions.
//
// See: Sprint N+1, Enhancement E8
// ===========================================================================

import 'dart:async';

/// A reusable [Completer] wrapper with double-completion guards and timeout.
///
/// Standard [Completer] throws [StateError] on double completion and cannot
/// be reset. This wrapper:
///   - Silently ignores `complete()` / `completeError()` after first completion
///   - Supports `reset()` to create a fresh internal Completer
///   - Supports `setTimeout()` to auto-complete after a duration
///   - Supports `cancelTimeout()` to cancel without completing
class ReusableCompleter<T> {
  Completer<T> _completer = Completer<T>();
  Timer? _timeoutTimer;

  /// Whether the current Completer has been completed.
  bool get isCompleted => _completer.isCompleted;

  /// The future for the current Completer.
  Future<T> get future => _completer.future;

  /// Complete with a value. No-op if already completed.
  void complete(T value) {
    if (!_completer.isCompleted) {
      _timeoutTimer?.cancel();
      _completer.complete(value);
    }
  }

  /// Complete with an error. No-op if already completed.
  void completeError(Object error, [StackTrace? stackTrace]) {
    if (!_completer.isCompleted) {
      _timeoutTimer?.cancel();
      _completer.completeError(error, stackTrace);
    }
  }

  /// Reset to a fresh Completer.
  ///
  /// Throws [StateError] if the previous Completer was not completed.
  /// Call [complete] or [completeError] before resetting.
  void reset() {
    if (!_completer.isCompleted) {
      throw StateError(
        'Cannot reset ReusableCompleter: previous future not yet completed.',
      );
    }
    _timeoutTimer?.cancel();
    _completer = Completer<T>();
  }

  /// Auto-complete with [timeoutValue] after [duration].
  ///
  /// Cancels any previously set timeout. No-op if already completed.
  void setTimeout(Duration duration, T timeoutValue) {
    _timeoutTimer?.cancel();
    if (_completer.isCompleted) return;
    _timeoutTimer = Timer(duration, () {
      complete(timeoutValue);
    });
  }

  /// Cancel the active timeout without completing.
  void cancelTimeout() {
    _timeoutTimer?.cancel();
  }

  /// Cancel timeout and release resources.
  ///
  /// Call this in `dispose()` to prevent timer leaks.
  void dispose() {
    _timeoutTimer?.cancel();
  }
}
