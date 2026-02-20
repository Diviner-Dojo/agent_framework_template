package com.divinerdojo.agentic_journal

import android.content.Intent
import android.os.Bundle
import android.provider.Settings
import android.app.role.RoleManager
import android.os.Build
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

// ===========================================================================
// MainActivity.kt
// purpose: Flutter's Android host activity with platform channel for
//          assistant registration.
//
// Platform Channels Explained (for the Python developer):
//   Platform channels are Flutter's bridge between Dart and native code.
//   Think of it like an RPC call: Dart calls a method name with arguments,
//   Kotlin receives the call, executes native Android APIs, and returns
//   a result. The channel name must match exactly on both sides.
//
// Assistant Registration:
//   Android has a "default digital assistant" role. When the user long-presses
//   the Home button, Android launches whichever app holds this role.
//   We can CHECK if we hold the role, but we cannot SET it programmatically —
//   the user must do it manually in Settings. We can open the right Settings
//   page for them.
//
// API Level Handling:
//   - Android 10+ (API 29+): Use RoleManager to check ROLE_ASSISTANT
//   - Android 5-9 (API 21-28): Use Settings.ACTION_VOICE_INPUT_SETTINGS
//     as a fallback (no direct way to check assistant role)
// ===========================================================================

class MainActivity : FlutterActivity() {
    // Channel name must match the Dart side exactly.
    private val CHANNEL = "com.divinerdojo.journal/assistant"

    // Flag to track if we were launched via the assistant gesture.
    // This is set in onCreate and read by Flutter to decide whether
    // to auto-start a journal session.
    private var launchedAsAssistant = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Check if this launch was triggered by the assistant gesture.
        // ACTION_ASSIST means the user long-pressed Home (or similar gesture).
        launchedAsAssistant = intent?.action == Intent.ACTION_ASSIST ||
                intent?.action == "android.intent.action.VOICE_ASSIST"
    }

    // Handle the case where the app is already running (singleTop) and the
    // user triggers the assistant gesture again. In singleTop mode, Android
    // calls onNewIntent instead of onCreate, so we need to re-check the
    // intent action here.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        launchedAsAssistant = intent.action == Intent.ACTION_ASSIST ||
                intent.action == "android.intent.action.VOICE_ASSIST"
    }

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        // Set up the method channel that Dart will call.
        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
            .setMethodCallHandler { call, result ->
                when (call.method) {
                    "isDefaultAssistant" -> {
                        result.success(checkIsDefaultAssistant())
                    }
                    "openAssistantSettings" -> {
                        openAssistantSettings()
                        result.success(null)
                    }
                    "wasLaunchedAsAssistant" -> {
                        // Return true if the app was launched via assistant gesture,
                        // then clear the flag so it's only reported once.
                        val wasLaunched = launchedAsAssistant
                        launchedAsAssistant = false
                        result.success(wasLaunched)
                    }
                    else -> result.notImplemented()
                }
            }
    }

    // Check if this app currently holds the ROLE_ASSISTANT.
    // Returns true if we are the default, false otherwise.
    private fun checkIsDefaultAssistant(): Boolean {
        // RoleManager is only available on Android 10+ (API 29).
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val roleManager = getSystemService(RoleManager::class.java)
            return roleManager?.isRoleHeld(RoleManager.ROLE_ASSISTANT) ?: false
        }
        // On older Android versions, there's no reliable way to check.
        // Return false and let the user verify manually.
        return false
    }

    // Open the system settings page where the user can set the default
    // digital assistant app.
    private fun openAssistantSettings() {
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+: Open the "Default apps" settings which includes
            // the digital assistant role assignment.
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
        } else {
            // Older Android: Open voice input settings as a fallback.
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
        }
        // FLAG_ACTIVITY_NEW_TASK is required when launching from a non-Activity
        // context, and also prevents the Settings app from being added to our
        // back stack.
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }
}
