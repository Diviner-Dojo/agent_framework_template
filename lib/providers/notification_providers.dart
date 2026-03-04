// ===========================================================================
// file: lib/providers/notification_providers.dart
// purpose: Riverpod providers for the OS-level notification scheduler (ADR-0033).
//
// Providers:
//   flutterLocalNotificationsProvider — plugin singleton (overrideable in tests)
//   notificationSchedulerProvider     — scheduler singleton wired to plugin
//   notificationBootRestoreProvider   — one-shot FutureProvider that reschedules
//                                       OS alarms cleared by device reboot
//
// The plugin instance is created once and shared via the provider.
// NotificationSchedulerService.initialize() is called in main() before
// runApp() to set up channels and restore the ID counter.
//
// See: lib/services/notification_scheduler_service.dart
//      SPEC-20260304-061650, ADR-0033
// ===========================================================================

import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/notification_scheduler_service.dart';
import 'database_provider.dart';

/// The underlying [FlutterLocalNotificationsPlugin] singleton.
///
/// Exposed as a provider so tests can override it with a mock.
final flutterLocalNotificationsProvider =
    Provider<FlutterLocalNotificationsPlugin>((ref) {
      return FlutterLocalNotificationsPlugin();
    });

/// Singleton [NotificationSchedulerService] wired to the plugin.
///
/// Call [NotificationSchedulerService.initialize] in `main()` before
/// `runApp()` to set up notification channels and restore the ID counter.
///
/// Override in tests:
/// ```dart
/// notificationSchedulerProvider.overrideWithValue(
///   NotificationSchedulerService(MockFlutterLocalNotificationsPlugin()),
/// )
/// ```
final notificationSchedulerProvider = Provider<NotificationSchedulerService>((
  ref,
) {
  final plugin = ref.watch(flutterLocalNotificationsProvider);
  return NotificationSchedulerService(plugin);
});

/// Reschedules pending task notifications after device reboot or reinstall.
///
/// OS exact alarms (`exactAllowWhileIdle`) are cleared when a device reboots.
/// This FutureProvider queries tasks with a future [reminderTime] that still
/// carry a stored [notificationId] (meaning their alarm has been wiped by the
/// reboot), creates fresh OS alarms via [NotificationSchedulerService], and
/// persists the new IDs back to the database.
///
/// Called once per app launch from [AgenticJournalApp.initState] via a
/// post-frame callback — same pattern as [llmAutoLoadProvider]. The provider
/// is non-autodispose so the completed Future is cached for the app lifetime
/// and the boot-restore only runs once per cold start.
///
/// Tasks that cannot be rescheduled (past due, permission revoked) are
/// silently skipped — the user simply will not receive that reminder.
final notificationBootRestoreProvider = FutureProvider<void>((ref) async {
  final scheduler = ref.read(notificationSchedulerProvider);
  final taskDao = ref.read(taskDaoProvider);

  final tasks = await taskDao.getTasksWithPendingReminders();
  if (tasks.isEmpty) return;

  final updates = await scheduler.rescheduleFromTasks(tasks);
  for (final (:taskId, :newNotificationId) in updates) {
    await taskDao.updateNotificationId(taskId, newNotificationId);
  }
});
