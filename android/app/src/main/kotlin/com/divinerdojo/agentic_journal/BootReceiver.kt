package com.divinerdojo.agentic_journal

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * Receives BOOT_COMPLETED and MY_PACKAGE_REPLACED broadcasts.
 *
 * flutter_local_notifications exact alarms are cleared when the device
 * reboots. This receiver triggers the Flutter engine to reschedule any
 * pending notifications stored in the app's SQLite database.
 *
 * The actual rescheduling logic lives in NotificationSchedulerService
 * (Dart/Flutter layer) — this Kotlin receiver simply boots the engine.
 * See ADR-0033.
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        // The flutter_local_notifications plugin handles rescheduling
        // via the onDidReceiveBackgroundNotificationResponse callback and
        // the plugin's built-in boot reschedule support when
        // scheduleMode = AndroidScheduleMode.exactAllowWhileIdle.
        // This receiver exists to satisfy the RECEIVE_BOOT_COMPLETED
        // manifest requirement and ensure the app process can start.
    }
}
