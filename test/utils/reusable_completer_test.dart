// ===========================================================================
// file: test/utils/reusable_completer_test.dart
// purpose: Tests for ReusableCompleter — double-completion guard, reset,
//          setTimeout, and cancelTimeout.
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/utils/reusable_completer.dart';

void main() {
  group('ReusableCompleter', () {
    group('complete', () {
      test('completes with a value', () async {
        final completer = ReusableCompleter<String>();
        completer.complete('hello');

        expect(completer.isCompleted, isTrue);
        expect(await completer.future, 'hello');
      });

      test('ignores second complete call (double-completion guard)', () async {
        final completer = ReusableCompleter<String>();
        completer.complete('first');
        completer.complete('second'); // Should be ignored.

        expect(await completer.future, 'first');
      });

      test('completes with null value', () async {
        final completer = ReusableCompleter<String?>();
        completer.complete(null);

        expect(completer.isCompleted, isTrue);
        expect(await completer.future, isNull);
      });
    });

    group('completeError', () {
      test('completes with an error', () async {
        final completer = ReusableCompleter<String>();
        completer.completeError(StateError('test error'));

        expect(completer.isCompleted, isTrue);
        await expectLater(completer.future, throwsA(isA<StateError>()));
      });

      test('ignores completeError after complete', () async {
        final completer = ReusableCompleter<String>();
        completer.complete('ok');
        completer.completeError(StateError('should be ignored'));

        expect(await completer.future, 'ok');
      });
    });

    group('reset', () {
      test('resets after completion', () async {
        final completer = ReusableCompleter<int>();
        completer.complete(1);
        expect(await completer.future, 1);

        completer.reset();
        expect(completer.isCompleted, isFalse);

        completer.complete(2);
        expect(await completer.future, 2);
      });

      test('throws if reset before completion', () {
        final completer = ReusableCompleter<int>();
        expect(() => completer.reset(), throwsStateError);
      });
    });

    group('setTimeout', () {
      test('auto-completes with timeout value after duration', () async {
        final completer = ReusableCompleter<String?>();
        completer.setTimeout(const Duration(milliseconds: 50), null);

        final result = await completer.future;
        expect(result, isNull);
        expect(completer.isCompleted, isTrue);
      });

      test('does not auto-complete if completed before timeout', () async {
        final completer = ReusableCompleter<String?>();
        completer.setTimeout(const Duration(milliseconds: 200), 'timeout');

        completer.complete('manual');
        final result = await completer.future;
        expect(result, 'manual');
      });

      test('subsequent setTimeout cancels previous', () async {
        final completer = ReusableCompleter<String?>();
        completer.setTimeout(const Duration(milliseconds: 50), 'first');
        completer.setTimeout(const Duration(milliseconds: 100), 'second');

        final result = await completer.future;
        // The second timeout should fire (after the first was cancelled).
        expect(result, 'second');
      });

      test('no-op if already completed', () async {
        final completer = ReusableCompleter<String?>();
        completer.complete('done');
        // Should not throw or cause issues.
        completer.setTimeout(const Duration(milliseconds: 50), 'timeout');

        expect(await completer.future, 'done');
      });
    });

    group('cancelTimeout', () {
      test('cancels active timeout without completing', () async {
        final completer = ReusableCompleter<String?>();
        completer.setTimeout(const Duration(milliseconds: 50), 'timeout');
        completer.cancelTimeout();

        // Give time for the cancelled timer to have fired (if it wasn't cancelled).
        await Future<void>.delayed(const Duration(milliseconds: 100));

        expect(completer.isCompleted, isFalse);

        // Clean up by completing manually.
        completer.complete('manual');
        expect(await completer.future, 'manual');
      });
    });

    group('dispose', () {
      test('cancels timeout on dispose', () async {
        final completer = ReusableCompleter<String?>();
        completer.setTimeout(const Duration(milliseconds: 50), 'timeout');
        completer.dispose();

        // Give time for the timer to have fired (if not disposed).
        await Future<void>.delayed(const Duration(milliseconds: 100));

        // The completer should not have been completed by the timer.
        expect(completer.isCompleted, isFalse);

        // Clean up.
        completer.complete('cleanup');
      });
    });

    group('isCompleted', () {
      test('false initially', () {
        final completer = ReusableCompleter<int>();
        expect(completer.isCompleted, isFalse);
      });

      test('true after complete', () {
        final completer = ReusableCompleter<int>();
        completer.complete(42);
        expect(completer.isCompleted, isTrue);
      });

      test('false after reset', () async {
        final completer = ReusableCompleter<int>();
        completer.complete(1);
        await completer.future;

        completer.reset();
        expect(completer.isCompleted, isFalse);
      });
    });
  });
}
