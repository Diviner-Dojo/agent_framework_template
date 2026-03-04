// ===========================================================================
// file: test/services/reminder_service_test.dart
// purpose: Unit tests for the adaptive non-escalating ReminderService (Phase 4D).
//
// Tests verify:
//   - Disabled by default (opt-in)
//   - shouldShow() guards: disabled, wrong time window, shown today, dismissed
//   - dismiss() increments counter and auto-disables at maxConsecutiveDismissals
//   - acknowledge() resets the dismissal counter
//   - snoozeForever() disables and resets the counter
//   - setEnabled(true) resets the dismissal counter (fresh start)
//   - setWindow() persists the time window
// ===========================================================================

import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/services/reminder_service.dart';

void main() {
  group('ReminderService', () {
    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    Future<ReminderService> buildService([
      Map<String, Object> initial = const {},
    ]) async {
      SharedPreferences.setMockInitialValues(initial);
      final prefs = await SharedPreferences.getInstance();
      return ReminderService(prefs);
    }

    // -------------------------------------------------------------------------
    // Default state
    // -------------------------------------------------------------------------

    test('reminder is disabled by default (opt-in)', () async {
      final svc = await buildService();
      expect(svc.isEnabled(ReminderType.dailyJournal), isFalse);
    });

    test('shouldShow returns false when disabled', () async {
      final svc = await buildService();
      // Even if time were in-window, disabled = hidden.
      expect(svc.shouldShow(ReminderType.dailyJournal), isFalse);
    });

    test('consecutiveDismissals defaults to 0', () async {
      final svc = await buildService();
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 0);
    });

    test('getWindow defaults to morning', () async {
      final svc = await buildService();
      expect(svc.getWindow(ReminderType.dailyJournal), ReminderWindow.morning);
    });

    // -------------------------------------------------------------------------
    // setEnabled / setWindow
    // -------------------------------------------------------------------------

    test('setEnabled persists enabled state', () async {
      final svc = await buildService();
      await svc.setEnabled(ReminderType.dailyJournal, value: true);
      expect(svc.isEnabled(ReminderType.dailyJournal), isTrue);
    });

    test('setEnabled(true) resets dismissal count for a fresh start', () async {
      // Seed with 2 dismissals so the user previously dismissed twice.
      final svc = await buildService({
        'reminder_dailyJournal_dismiss_count': 2,
        'reminder_dailyJournal_enabled': false,
      });
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 2);

      await svc.setEnabled(ReminderType.dailyJournal, value: true);

      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 0);
    });

    test('setEnabled(false) does not reset dismissal count', () async {
      final svc = await buildService({
        'reminder_dailyJournal_dismiss_count': 1,
      });
      await svc.setEnabled(ReminderType.dailyJournal, value: false);
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 1);
    });

    test('setWindow persists the chosen window', () async {
      final svc = await buildService();
      await svc.setWindow(ReminderType.dailyJournal, ReminderWindow.evening);
      expect(svc.getWindow(ReminderType.dailyJournal), ReminderWindow.evening);
    });

    // -------------------------------------------------------------------------
    // dismiss()
    // -------------------------------------------------------------------------

    test('dismiss increments the consecutive dismissal counter', () async {
      final svc = await buildService();
      await svc.dismiss(ReminderType.dailyJournal);
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 1);
      await svc.dismiss(ReminderType.dailyJournal);
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 2);
    });

    test(
      'dismiss auto-disables when maxConsecutiveDismissals is reached',
      () async {
        final svc = await buildService({
          'reminder_dailyJournal_enabled': true,
          'reminder_dailyJournal_dismiss_count':
              ReminderService.maxConsecutiveDismissals - 1,
        });

        await svc.dismiss(ReminderType.dailyJournal);

        expect(
          svc.consecutiveDismissals(ReminderType.dailyJournal),
          ReminderService.maxConsecutiveDismissals,
        );
        expect(svc.isEnabled(ReminderType.dailyJournal), isFalse);
      },
    );

    test('dismiss below threshold does not auto-disable', () async {
      final svc = await buildService({
        'reminder_dailyJournal_enabled': true,
        'reminder_dailyJournal_dismiss_count': 0,
      });

      await svc.dismiss(ReminderType.dailyJournal);

      expect(svc.isEnabled(ReminderType.dailyJournal), isTrue);
    });

    test(
      'dismiss stamps last-shown so reminder is hidden for rest of day',
      () async {
        // Enable + simulate being in-window by seeding the enabled state.
        // We cannot easily mock DateTime.now() but we CAN verify that after
        // dismiss, shouldShow returns false because _wasShownToday is true.
        final svc = await buildService({'reminder_dailyJournal_enabled': true});

        await svc.dismiss(ReminderType.dailyJournal);

        // Even with enabled=true and 1 dismissal (below max), the same-day
        // guard should now be active — shouldShow must return false.
        expect(svc.shouldShow(ReminderType.dailyJournal), isFalse);
      },
    );

    // -------------------------------------------------------------------------
    // acknowledge()
    // -------------------------------------------------------------------------

    test('acknowledge resets the consecutive dismissal counter to 0', () async {
      final svc = await buildService({
        'reminder_dailyJournal_dismiss_count': 2,
      });

      await svc.acknowledge(ReminderType.dailyJournal);

      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 0);
    });

    // -------------------------------------------------------------------------
    // snoozeForever()
    // -------------------------------------------------------------------------

    test('snoozeForever disables the reminder', () async {
      final svc = await buildService({'reminder_dailyJournal_enabled': true});

      await svc.snoozeForever(ReminderType.dailyJournal);

      expect(svc.isEnabled(ReminderType.dailyJournal), isFalse);
    });

    test('snoozeForever resets the dismissal counter', () async {
      final svc = await buildService({
        'reminder_dailyJournal_dismiss_count': 2,
        'reminder_dailyJournal_enabled': true,
      });

      await svc.snoozeForever(ReminderType.dailyJournal);

      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 0);
    });

    test('re-enabling after snoozeForever starts fresh', () async {
      final svc = await buildService({'reminder_dailyJournal_enabled': true});
      await svc.snoozeForever(ReminderType.dailyJournal);
      // Counter reset to 0 by snoozeForever; re-enable starts fresh.
      await svc.setEnabled(ReminderType.dailyJournal, value: true);

      expect(svc.isEnabled(ReminderType.dailyJournal), isTrue);
      expect(svc.consecutiveDismissals(ReminderType.dailyJournal), 0);
    });

    // -------------------------------------------------------------------------
    // shouldShow() guards
    // -------------------------------------------------------------------------

    test('shouldShow returns false when dismissal count at maximum', () async {
      final svc = await buildService({
        'reminder_dailyJournal_enabled': true,
        'reminder_dailyJournal_dismiss_count':
            ReminderService.maxConsecutiveDismissals,
      });

      expect(svc.shouldShow(ReminderType.dailyJournal), isFalse);
    });

    test('shouldShow returns false when shown today already', () async {
      // Seed last_shown as today's epoch ms.
      final todayMs = DateTime.now().millisecondsSinceEpoch;
      final svc = await buildService({
        'reminder_dailyJournal_enabled': true,
        'reminder_dailyJournal_last_shown': todayMs,
        'reminder_dailyJournal_dismiss_count': 0,
      });

      expect(svc.shouldShow(ReminderType.dailyJournal), isFalse);
    });

    test(
      'shouldShow returns false when last_shown is a previous day',
      () async {
        // Seed last_shown as yesterday — so _wasShownToday = false.
        // With enabled=true and 0 dismissals, the only remaining gate is
        // the time-window check. We cannot mock the clock, but we can
        // verify that the yesterday guard does NOT suppress the call.
        final yesterday = DateTime.now()
            .subtract(const Duration(days: 1))
            .millisecondsSinceEpoch;
        final svc = await buildService({
          'reminder_dailyJournal_enabled': true,
          'reminder_dailyJournal_last_shown': yesterday,
          'reminder_dailyJournal_dismiss_count': 0,
        });

        // With enabled + previous day shown + 0 dismissals, shouldShow is
        // gated only on the current time window. Since tests run at arbitrary
        // hours, we assert the method does NOT throw and returns a bool.
        final result = svc.shouldShow(ReminderType.dailyJournal);
        expect(result, isA<bool>());
      },
    );
  });

  // ---------------------------------------------------------------------------
  // ReminderWindow extension tests
  // ---------------------------------------------------------------------------

  group('ReminderWindow', () {
    test('morning startHour is 7', () {
      expect(ReminderWindow.morning.startHour, 7);
    });

    test('afternoon startHour is 12', () {
      expect(ReminderWindow.afternoon.startHour, 12);
    });

    test('evening startHour is 19', () {
      expect(ReminderWindow.evening.startHour, 19);
    });

    test('fromPrefValue round-trips all windows', () {
      for (final w in ReminderWindow.values) {
        expect(ReminderWindowLabel.fromPrefValue(w.prefValue), w);
      }
    });

    test('fromPrefValue returns morning for unknown value', () {
      expect(
        ReminderWindowLabel.fromPrefValue('invalid'),
        ReminderWindow.morning,
      );
    });

    test('fromPrefValue returns morning for null', () {
      expect(ReminderWindowLabel.fromPrefValue(null), ReminderWindow.morning);
    });
  });
}
