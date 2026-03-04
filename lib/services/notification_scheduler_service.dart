// coverage:ignore-file — requires flutter_local_notifications + timezone
// native plugins; cannot unit-test without device integration.
// ===========================================================================
// file: lib/services/notification_scheduler_service.dart
// purpose: Schedule and cancel OS-level local notifications for timed
//          reminders and tasks with explicit time components.
//
// Design principles (ADR-0033):
//   - Plugin injected via constructor — enables mock injection in tests.
//   - Fires once, no re-escalation (ADHD contract).
//   - Lock-screen visibility = private (personal content protection).
//   - Past-time scheduling is rejected with an exception.
//   - Notification IDs are in the range 1000–1999 (task namespace).
//
// Usage:
//   // Production (via notificationSchedulerProvider):
//   final service = NotificationSchedulerService(FlutterLocalNotificationsPlugin());
//   await service.initialize();
//
//   // Tests:
//   final service = NotificationSchedulerService(mockPlugin);
// ===========================================================================

import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:timezone/data/latest_all.dart' as tz;
import 'package:timezone/timezone.dart' as tz;

/// Minimum notification ID in the task namespace (ADR-0033 §Notification ID Namespace).
const int _kTaskNotificationIdMin = 1000;

/// Maximum notification ID in the task namespace.
const int _kTaskNotificationIdMax = 1999;

/// Android notification channel ID for task reminders.
const String _kChannelId = 'task_reminders';

/// Android notification channel name (shown in system Settings → App Notifications).
const String _kChannelName = 'Task Reminders';

/// Android notification channel description.
const String _kChannelDescription =
    'Notifications for scheduled tasks and reminders';

/// Exception thrown when a reminder time is in the past.
class PastReminderTimeException implements Exception {
  /// The scheduled time that was rejected.
  final DateTime scheduledAt;

  const PastReminderTimeException(this.scheduledAt);

  @override
  String toString() => 'PastReminderTimeException: $scheduledAt is in the past';
}

/// Exception thrown when the notification permission is denied.
class NotificationPermissionDeniedException implements Exception {
  const NotificationPermissionDeniedException();

  @override
  String toString() =>
      'NotificationPermissionDeniedException: '
      'User denied notification permission';
}

/// SharedPreferences key for persisted notification ID counter.
const String _kNextIdPrefKey = 'notification_scheduler_next_id';

/// Schedules and cancels OS-level local notifications for timed reminders.
///
/// The [plugin] parameter accepts a [FlutterLocalNotificationsPlugin] instance.
/// In production, use the singleton provided by [notificationSchedulerProvider].
/// In tests, inject a mock plugin to keep tests deterministic.
///
/// See: ADR-0033, SPEC-20260304-061650.
class NotificationSchedulerService {
  final FlutterLocalNotificationsPlugin _plugin;

  /// Whether [initialize] has been called successfully.
  bool _initialized = false;

  /// Tracks the next notification ID to assign (cycles within 1000–1999).
  ///
  /// Persisted to SharedPreferences on each allocation so that app restarts
  /// do not reset the counter to 1000 and silently overwrite a still-pending
  /// OS notification from a previous session.
  int _nextId = _kTaskNotificationIdMin;

  /// Creates the service with the given plugin instance.
  ///
  /// The plugin is not initialized in the constructor — call [initialize]
  /// before scheduling notifications.
  NotificationSchedulerService(this._plugin);

  /// Initialize the notification plugin and create Android notification channels.
  ///
  /// Must be called once at app startup (e.g., in main() before runApp).
  /// Safe to call multiple times — subsequent calls are no-ops.
  Future<void> initialize() async {
    if (_initialized) return;

    // Restore persisted notification ID counter to prevent collision with
    // still-pending OS notifications from previous app sessions.
    final prefs = await SharedPreferences.getInstance();
    _nextId = prefs.getInt(_kNextIdPrefKey) ?? _kTaskNotificationIdMin;
    if (_nextId < _kTaskNotificationIdMin ||
        _nextId > _kTaskNotificationIdMax) {
      _nextId = _kTaskNotificationIdMin;
    }

    // Initialize timezone data for TZDateTime scheduling.
    tz.initializeTimeZones();

    const androidSettings = AndroidInitializationSettings(
      '@mipmap/ic_launcher',
    );
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );

    await _plugin.initialize(
      settings,
      onDidReceiveNotificationResponse: _onNotificationTapped,
      onDidReceiveBackgroundNotificationResponse:
          _onBackgroundNotificationTapped,
    );

    // Create the Android notification channel.
    const androidChannel = AndroidNotificationChannel(
      _kChannelId,
      _kChannelName,
      description: _kChannelDescription,
      importance: Importance.high,
      // ADHD contract: no badge accumulation.
      showBadge: false,
      // ADHD contract: fire once, no sound loop.
      playSound: true,
    );

    await _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >()
        ?.createNotificationChannel(androidChannel);

    _initialized = true;
  }

  /// Request notification permission from the user.
  ///
  /// Returns true if permission was granted (or already granted).
  /// Returns false if the user denied the request.
  ///
  /// On Android < 13, POST_NOTIFICATIONS is not required and this
  /// method always returns true.
  Future<bool> requestPermission() async {
    final android = _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    if (android != null) {
      final granted = await android.requestNotificationsPermission();
      return granted ?? false;
    }
    final ios = _plugin
        .resolvePlatformSpecificImplementation<
          IOSFlutterLocalNotificationsPlugin
        >();
    if (ios != null) {
      final granted = await ios.requestPermissions(
        alert: true,
        badge: false,
        sound: true,
      );
      return granted ?? false;
    }
    return true;
  }

  /// Check whether notification permission has been granted.
  Future<bool> hasPermission() async {
    final android = _plugin
        .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin
        >();
    if (android != null) {
      final granted = await android.areNotificationsEnabled();
      return granted ?? false;
    }
    return true;
  }

  /// Schedule an OS-level local notification at [scheduledAt].
  ///
  /// Returns the notification ID assigned to this notification.
  /// Store this ID on the task row ([Task.notificationId]) so the
  /// notification can be cancelled when the task is completed or deleted.
  ///
  /// Throws [PastReminderTimeException] if [scheduledAt] is in the past.
  /// Throws [NotificationPermissionDeniedException] if permission is denied
  /// and [requestPermissionIfNeeded] is true.
  ///
  /// Parameters:
  ///   [title] — notification title (task name, e.g. "Cat meds").
  ///   [body]  — notification body shown below the title.
  ///   [scheduledAt] — exact local DateTime when the notification fires.
  ///   [requestPermissionIfNeeded] — if true, request permission if not granted.
  Future<int> scheduleNotification({
    required String title,
    required String body,
    required DateTime scheduledAt,
    bool requestPermissionIfNeeded = true,
  }) async {
    // Past-time guard (spec Requirement 8).
    if (scheduledAt.isBefore(DateTime.now())) {
      throw PastReminderTimeException(scheduledAt);
    }

    // Permission check.
    if (requestPermissionIfNeeded) {
      final permitted = await hasPermission();
      if (!permitted) {
        final granted = await requestPermission();
        if (!granted) {
          throw const NotificationPermissionDeniedException();
        }
      }
    }

    final id = await _nextNotificationId();
    final tzScheduled = tz.TZDateTime.from(scheduledAt, tz.local);

    final androidDetails = AndroidNotificationDetails(
      _kChannelId,
      _kChannelName,
      channelDescription: _kChannelDescription,
      importance: Importance.high,
      priority: Priority.high,
      // ADHD contract: lock-screen privacy (spec Requirement 4).
      visibility: NotificationVisibility.private,
      // ADHD contract: no badge accumulation.
      showWhen: true,
      // Do not set `ongoing` — user dismissal is final.
      autoCancel: true,
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentSound: true,
      // iOS badge count is not incremented (ADHD contract).
      badgeNumber: 0,
    );

    final details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );

    await _plugin.zonedSchedule(
      id,
      title,
      body,
      tzScheduled,
      details,
      // Exact alarm — fires even in battery-saving modes.
      androidScheduleMode: AndroidScheduleMode.exactAllowWhileIdle,
      // Absolute time interpretation required by iOS (UILocalNotification).
      // We always schedule for a specific moment, not a wall-clock recurrence.
      uiLocalNotificationDateInterpretation:
          UILocalNotificationDateInterpretation.absoluteTime,
      // Do not repeat — ADHD contract: fires once.
      matchDateTimeComponents: null,
    );

    // Log scheduled time only — do not log user-supplied title in case it
    // contains sensitive content (health reminders, personal names). See
    // security review finding: logcat is readable by privileged processes.
    if (kDebugMode) {
      debugPrint(
        '[NotificationSchedulerService] Scheduled #$id at $scheduledAt',
      );
    }
    return id;
  }

  /// Cancel a previously scheduled notification by [notificationId].
  ///
  /// Safe to call on IDs that have already fired or been dismissed.
  /// No-op if [notificationId] is null.
  Future<void> cancelNotification(int? notificationId) async {
    if (notificationId == null) return;
    await _plugin.cancel(notificationId);
    if (kDebugMode) {
      debugPrint(
        '[NotificationSchedulerService] Cancelled notification #$notificationId',
      );
    }
  }

  /// Cancel all scheduled task notifications.
  ///
  /// Used during app reset / sign-out to clear all pending alarms.
  Future<void> cancelAll() async {
    await _plugin.cancelAll();
    if (kDebugMode) {
      debugPrint('[NotificationSchedulerService] Cancelled all notifications');
    }
  }

  /// Allocate the next notification ID in the task namespace (1000–1999).
  ///
  /// IDs cycle: after 1999, wraps back to 1000. The counter is persisted to
  /// SharedPreferences so that app restarts do not reset to 1000 and
  /// overwrite still-pending OS notifications from the previous session.
  ///
  /// The caller stores the returned ID on the task row for later cancellation.
  Future<int> _nextNotificationId() async {
    final id = _nextId;
    _nextId = _nextId >= _kTaskNotificationIdMax
        ? _kTaskNotificationIdMin
        : _nextId + 1;
    // Persist the counter so the next app session starts from the correct ID.
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_kNextIdPrefKey, _nextId);
    return id;
  }
}

/// Called when the user taps a notification while the app is in the foreground
/// or background (but not terminated).
void _onNotificationTapped(NotificationResponse response) {
  // Navigation is handled by the app's router when the app is resumed.
  // The payload could be used to deep-link to a specific task in the future.
  // Do not log response.payload — may contain task IDs or content in future.
  if (kDebugMode) {
    debugPrint(
      '[NotificationSchedulerService] Notification tapped: id=${response.id}',
    );
  }
}

/// Called when a notification is tapped while the app is terminated.
///
/// This is a top-level function (not a method) as required by
/// flutter_local_notifications for background handling.
@pragma('vm:entry-point')
void _onBackgroundNotificationTapped(NotificationResponse response) {
  // Background handler — cannot use kDebugMode safely in a background isolate.
  // No logging to avoid logcat exposure of notification IDs.
}
