package com.divinerdojo.agentic_journal

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Receives BOOT_COMPLETED and MY_PACKAGE_REPLACED broadcasts.
 *
 * flutter_local_notifications exact alarms (exactAllowWhileIdle) are cleared
 * when the device reboots. The actual rescheduling happens in the Dart layer:
 * NotificationSchedulerService.rescheduleFromTasks() is called from
 * AgenticJournalApp.initState() via notificationBootRestoreProvider when the
 * user next opens the app after a reboot.
 *
 * This Kotlin receiver exists solely to hold the RECEIVE_BOOT_COMPLETED
 * manifest entry (required to receive the system broadcast). It does not
 * start a background service or trigger a WorkManager job — rescheduling is
 * deferred until the user opens the app (on-launch approach). See ADR-0033.
 *
 * Note: onDidReceiveBackgroundNotificationResponse fires when a user TAPS a
 * notification, NOT on boot — it is unrelated to reboot rescheduling.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // Rescheduling is handled in the Dart layer at app launch.
        // See NotificationSchedulerService.rescheduleFromTasks() and
        // notificationBootRestoreProvider in notification_providers.dart.
    }
}
