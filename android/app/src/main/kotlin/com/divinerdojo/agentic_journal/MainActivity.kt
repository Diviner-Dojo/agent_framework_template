package com.divinerdojo.agentic_journal

import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
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
    // Channel names must match the Dart side exactly.
    private val CHANNEL = "com.divinerdojo.journal/assistant"
    private val AUDIO_CHANNEL = "com.divinerdojo.journal/audio"

    // Flag to track if we were launched via the assistant gesture.
    // This is set in onCreate and read by Flutter to decide whether
    // to auto-start a journal session.
    private var launchedAsAssistant = false

    // Flag to track if the launch was specifically a VOICE_ASSIST intent.
    // Used by Phase 7B to distinguish voice launch from generic assistant launch.
    private var launchedAsVoiceAssistant = false

    // Audio focus management for voice recording (Phase 7A).
    private var audioManager: AudioManager? = null
    private var audioFocusRequest: AudioFocusRequest? = null
    private var audioMethodChannel: MethodChannel? = null

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        // Check if this launch was triggered by the assistant gesture.
        // ACTION_ASSIST means the user long-pressed Home (or similar gesture).
        launchedAsAssistant = intent?.action == Intent.ACTION_ASSIST ||
                intent?.action == "android.intent.action.VOICE_ASSIST"
        // Track specifically voice-assist launches for Phase 7B continuous mode.
        launchedAsVoiceAssistant = intent?.action == "android.intent.action.VOICE_ASSIST"
    }

    // Handle the case where the app is already running (singleTop) and the
    // user triggers the assistant gesture again. In singleTop mode, Android
    // calls onNewIntent instead of onCreate, so we need to re-check the
    // intent action here.
    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        launchedAsAssistant = intent.action == Intent.ACTION_ASSIST ||
                intent.action == "android.intent.action.VOICE_ASSIST"
        launchedAsVoiceAssistant = intent.action == "android.intent.action.VOICE_ASSIST"
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
                    "wasLaunchedAsVoiceAssistant" -> {
                        // Return true specifically for VOICE_ASSIST intent.
                        // Phase 7B uses this to auto-start continuous voice mode.
                        val wasVoice = launchedAsVoiceAssistant
                        launchedAsVoiceAssistant = false
                        result.success(wasVoice)
                    }
                    else -> result.notImplemented()
                }
            }

        // Audio focus channel for voice recording (Phase 7A — ADR-0015).
        audioManager = getSystemService(AUDIO_SERVICE) as AudioManager
        audioMethodChannel = MethodChannel(
            flutterEngine.dartExecutor.binaryMessenger, AUDIO_CHANNEL
        )
        audioMethodChannel!!.setMethodCallHandler { call, result ->
            when (call.method) {
                "requestAudioFocus" -> {
                    result.success(requestAudioFocus())
                }
                "abandonAudioFocus" -> {
                    abandonAudioFocus()
                    result.success(null)
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

    // =========================================================================
    // Audio Focus Management (Phase 7A — ADR-0015)
    // =========================================================================

    // Audio focus change listener that forwards events to Flutter.
    private val audioFocusChangeListener = AudioManager.OnAudioFocusChangeListener { focusChange ->
        // Forward focus change to Flutter via the audio method channel.
        // Android AudioManager constants:
        //   AUDIOFOCUS_GAIN = 1
        //   AUDIOFOCUS_LOSS = -1
        //   AUDIOFOCUS_LOSS_TRANSIENT = -2
        //   AUDIOFOCUS_LOSS_TRANSIENT_CAN_DUCK = -3
        audioMethodChannel?.invokeMethod("onAudioFocusChange", focusChange)
    }

    // Request audio focus for voice recording.
    // Returns true if focus was granted.
    private fun requestAudioFocus(): Boolean {
        val am = audioManager ?: return false

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val focusRequest = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_ASSISTANT)
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build()
                )
                .setOnAudioFocusChangeListener(audioFocusChangeListener)
                .build()

            audioFocusRequest = focusRequest
            val result = am.requestAudioFocus(focusRequest)
            return result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        } else {
            @Suppress("DEPRECATION")
            val result = am.requestAudioFocus(
                audioFocusChangeListener,
                AudioManager.STREAM_MUSIC,
                AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
            )
            return result == AudioManager.AUDIOFOCUS_REQUEST_GRANTED
        }
    }

    // Abandon audio focus when recording is done.
    private fun abandonAudioFocus() {
        val am = audioManager ?: return

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            audioFocusRequest?.let { am.abandonAudioFocusRequest(it) }
            audioFocusRequest = null
        } else {
            @Suppress("DEPRECATION")
            am.abandonAudioFocus(audioFocusChangeListener)
        }
    }
}
