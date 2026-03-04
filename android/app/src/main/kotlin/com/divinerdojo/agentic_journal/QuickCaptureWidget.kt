package com.divinerdojo.agentic_journal

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

// ===========================================================================
// QuickCaptureWidget.kt
// purpose: Android home screen widget that opens the app directly into the
//          last-used quick capture mode (Phase 4B — ADHD effortless capture).
//
// Design:
//   - One tap → app opens in the right mode immediately, no mode picker.
//   - Last-used mode is read from SharedPreferences (Flutter writes this key).
//   - Flutter stores prefs under the "FlutterSharedPreferences" file; each key
//     is prefixed with "flutter." so the Dart key "last_capture_mode" maps to
//     the Android key "flutter.last_capture_mode".
//   - No content preview — journal entries are private; the widget is only an
//     entry point, not a window into the user's journal.
//   - If no mode has been stored yet (first-time user), we pass null and the
//     Flutter side opens the quick capture palette normally.
//
// Platform channel:
//   The widget passes the launch mode as an Intent extra
//   (EXTRA_WIDGET_LAUNCH_MODE). MainActivity reads it in onCreate/onNewIntent
//   and exposes it to Flutter via the "com.divinerdojo.journal/widget" channel.
// ===========================================================================

class QuickCaptureWidget : AppWidgetProvider() {

    companion object {
        /** Intent extra key carrying the capture mode string from the widget. */
        const val EXTRA_WIDGET_LAUNCH_MODE = "widget_launch_mode"

        /** SharedPreferences file written by Flutter's SharedPreferences plugin. */
        private const val FLUTTER_PREFS_FILE = "FlutterSharedPreferences"

        /** Flutter SharedPreferences key for last_capture_mode (prefixed). */
        private const val PREF_LAST_CAPTURE_MODE = "flutter.last_capture_mode"
    }

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (widgetId in appWidgetIds) {
            updateWidget(context, appWidgetManager, widgetId)
        }
    }

    private fun updateWidget(
        context: Context,
        appWidgetManager: AppWidgetManager,
        widgetId: Int
    ) {
        // Read the last-used capture mode from Flutter's SharedPreferences.
        val prefs = context.getSharedPreferences(FLUTTER_PREFS_FILE, Context.MODE_PRIVATE)
        val lastMode: String? = prefs.getString(PREF_LAST_CAPTURE_MODE, null)

        // Build the launch intent carrying the capture mode as an extra.
        // FLAG_ACTIVITY_SINGLE_TOP ensures we don't stack multiple Main instances.
        val launchIntent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            if (lastMode != null) {
                putExtra(EXTRA_WIDGET_LAUNCH_MODE, lastMode)
            }
        }

        val pendingIntent = PendingIntent.getActivity(
            context,
            widgetId, // Use widgetId as request code so each widget gets its own PendingIntent.
            launchIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        // Apply the tap action to the entire widget layout.
        val views = RemoteViews(context.packageName, R.layout.quick_capture_widget)
        views.setOnClickPendingIntent(R.id.widget_label, pendingIntent)

        appWidgetManager.updateAppWidget(widgetId, views)
    }
}
