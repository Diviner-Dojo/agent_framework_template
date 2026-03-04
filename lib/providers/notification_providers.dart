// ===========================================================================
// file: lib/providers/notification_providers.dart
// purpose: Riverpod providers for the OS-level notification scheduler (ADR-0033).
//
// notificationSchedulerProvider — singleton NotificationSchedulerService.
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
