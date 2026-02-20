---
spec_id: SPEC-20260220-000100
title: "Phase 2: Android Assistant Registration, Settings & Onboarding"
status: approved
risk_level: medium
phase: 2
source: docs/product-brief.md
estimated_tasks: 10
autonomous_execution: true
depends_on: SPEC-20260219-174121
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260219-235437-phase2-spec-review
---

## Goal

Make the app launchable from Android's default assistant gesture (long-press Home), add a settings screen showing assistant registration status, and build a first-launch onboarding flow. Optionally add voice input via `speech_to_text`.

After Phase 2, the app:
- Responds to `ACTION_ASSIST` intent on Android (launches directly into a new journal session)
- Has a settings screen where the user can check/set default assistant status
- Guides first-time users through setup via an onboarding flow
- (Stretch) Accepts voice input via a microphone button in the chat UI

## Context

- Phase 1 delivered a working offline journaling app with rule-based conversations, drift persistence, and 85 passing tests
- The app currently has 3 screens: session list (home), journal session (chat), session detail (read-only transcript)
- Navigation uses string-based named routes — sufficient for Phase 2's additions (go_router migration deferred to pre-Phase 5)
- The developer has never written native Kotlin or platform channels — comments must explain Android concepts thoroughly
- META-REVIEW-20260219 recommended designing a `ConversationAgent` abstract interface at Phase 2 to prepare for Phase 3's LLM integration; this is included as a stretch task
- ADR-0006 (Three-Layer Agent Design) anticipated Layer B at Phase 3 — the interface design prepares that boundary

## Constraints

- **Android-only native code**: The platform channel and intent filter are Android-specific. iOS gets a no-op stub.
- **No network calls**: Phase 2 remains offline-only. Supabase/Claude integration is Phase 3-4.
- **Minimal new dependencies**: Only `speech_to_text` (stretch) and `permission_handler` if voice is implemented.
- **PATH requirement**: Every shell command using `flutter` or `dart` must include: `export PATH="$PATH:/c/src/flutter/bin"`
- **Windows/Git Bash**: Shell environment is Git Bash on Windows 11. Use Unix syntax.
- **Comment thoroughly**: The developer is learning Flutter and Android. Inline comments explaining "why" are required, especially for Kotlin/platform channel concepts.

## Requirements

### Functional
- R1: AndroidManifest.xml has ACTION_ASSIST + ACTION_VOICE_ASSIST intent filters on MainActivity
- R2: Platform channel `com.divinerdojo.journal/assistant` exposes `isDefaultAssistant` and `openAssistantSettings` methods from Kotlin to Dart
- R3: `AssistantRegistrationService` wraps the platform channel with proper error handling and iOS no-op fallback
- R4: Settings screen shows current assistant registration status and a button to open system assistant settings
- R5: Onboarding screen explains the app, guides assistant setup, shown only on first launch
- R6: Navigation updated with routes for `/settings` and `/onboarding`
- R7: When launched via ACTION_ASSIST intent, app opens directly into a new journal session (not session list)
- R8: Settings accessible from session list app bar (gear icon)
- R9: First-launch detection uses a simple Riverpod provider backed by shared preferences or a local flag

### Stretch (Voice Input)
- R10: `speech_to_text` dependency added, microphone button in chat input bar
- R11: Voice input transcribes to text and inserts as a message with `inputMethod = 'VOICE'`
- R12: Microphone permission requested gracefully with explanation

### Stretch (Agent Interface)
- R13: Abstract `ConversationAgent` interface extracted from `AgentRepository`, preparing for Layer B plugin at Phase 3

### Non-Functional
- NF1: Platform channel calls handle PlatformException gracefully (never crash)
- NF2: All new code passes `dart format` and `dart analyze` with zero issues
- NF3: Test coverage >= 80% for new and modified code
- NF4: No secrets, API keys, or credentials in source code

## Acceptance Criteria

- [ ] Long-press Home on Android emulator triggers the app (or navigates to assistant settings to set it)
- [ ] Settings screen shows "Default assistant: Yes/No" with a button to open system settings
- [ ] First app launch shows onboarding; subsequent launches go to session list
- [ ] Launching via ACTION_ASSIST starts a new session immediately
- [ ] Settings accessible via gear icon in session list app bar
- [ ] All 10+ new tests pass
- [ ] `dart analyze` reports zero errors
- [ ] Coverage >= 80% for new code
- [ ] (Stretch) Microphone button appears, tapping starts voice recognition
- [ ] (Stretch) `ConversationAgent` abstract class exists with current methods as interface

## Risk Assessment

| Risk | Impact | Likelihood | Mitigation |
|---|---|---|---|
| Emulator doesn't support long-press Home gesture | Medium | Medium | Test with `adb shell am start -a android.intent.action.ASSIST` command instead |
| `speech_to_text` has compatibility issues with Flutter 3.x | Low | Medium | Voice input is stretch — skip if problematic |
| Platform channel type mismatch between Kotlin and Dart | Medium | Low | Use only primitive types (bool, String); thorough error handling |
| First-launch detection races with async initialization | Low | Low | Use synchronous SharedPreferences check before MaterialApp builds |

## Affected Components

### New Files
- `lib/services/assistant_registration_service.dart` — Platform channel wrapper (injectable for testing)
- `lib/ui/screens/settings_screen.dart` — Settings with assistant status
- `lib/ui/screens/onboarding_screen.dart` — First-launch guide
- `lib/providers/onboarding_providers.dart` — First-launch state management (single notifier, no dual provider)
- `test/services/assistant_registration_service_test.dart`
- `test/ui/settings_screen_test.dart`
- `test/ui/onboarding_screen_test.dart`
- `test/providers/onboarding_providers_test.dart`
- `test/app_routing_test.dart` — Navigation logic tests (onboarding redirect, assistant-launch, routes)

### Modified Files
- `android/app/src/main/AndroidManifest.xml` — ACTION_ASSIST intent filters
- `android/app/src/main/kotlin/.../MainActivity.kt` — Platform channel handler
- `lib/app.dart` — Add `/settings` and `/onboarding` routes, onboarding redirect
- `lib/ui/screens/session_list_screen.dart` — Add settings gear icon to app bar
- `lib/ui/screens/journal_session_screen.dart` — (Stretch) Add microphone button
- `pubspec.yaml` — Add shared_preferences dependency; (stretch) speech_to_text

### Unchanged
- Database layer (no schema changes)
- Agent repository (unchanged unless stretch R13 is implemented)
- Existing test files (no modifications needed)

## Dependencies

### Depends On
- Phase 1 complete (walking skeleton with working drift DB, agent, and UI)
- Android SDK with API 21+ for assistant intents

### Depended On By
- Phase 3 (LLM integration) — if R13 is implemented, the ConversationAgent interface simplifies Layer B addition
- Phase 4 (Cloud Sync) — settings screen provides future home for sync configuration

---

## Task Breakdown

### Task 1: Add Dependencies

**What**: Add `shared_preferences` to pubspec.yaml for first-launch detection and onboarding state persistence.

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter pub add shared_preferences
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter pub get
```

**Acceptance**: `pubspec.yaml` includes `shared_preferences`, `flutter pub get` succeeds with no errors.

**Checkpoint**: No — dependency config only.

---

### Task 2: Android Manifest — Assistant Intent Filters

**What**: Add `ACTION_ASSIST` and `ACTION_VOICE_ASSIST` intent filters to `MainActivity` in `AndroidManifest.xml`. This tells Android the app can handle assistant requests.

**File**: `android/app/src/main/AndroidManifest.xml`

**Changes**:
Add a second `<intent-filter>` block inside the existing `<activity>` element, after the MAIN/LAUNCHER filter:

```xml
<!-- Register as a digital assistant candidate.
     ACTION_ASSIST: triggered by long-press Home on most devices.
     ACTION_VOICE_ASSIST: triggered by "Hey Google" or voice button on some devices.
     The user must manually select this app as default in Settings → Apps → Default Apps → Digital Assistant. -->
<intent-filter>
    <action android:name="android.intent.action.ASSIST" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
<intent-filter>
    <action android:name="android.intent.action.VOICE_ASSIST" />
    <category android:name="android.intent.category.DEFAULT" />
</intent-filter>
```

Also add a `<meta-data>` element for the assistant to provide a search action (required by some Android versions):
```xml
<meta-data
    android:name="com.android.systemui.action_assist_icon"
    android:resource="@mipmap/ic_launcher" />
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter build apk --debug 2>&1 | tail -5
```

**Verification (security baseline)**:
```bash
grep 'allowBackup="false"' android/app/src/main/AndroidManifest.xml
```
This must still output a match. If `allowBackup` was reset to `true` by any tooling, fix it immediately.

**Acceptance**: APK builds successfully. `AndroidManifest.xml` contains both intent filters and `android:allowBackup="false"`.

**Checkpoint**: No — XML config only.

---

### Task 3: Native Kotlin Platform Channel

**What**: Implement the Kotlin side of the platform channel in `MainActivity.kt`. This provides two methods to Dart: `isDefaultAssistant` (checks if this app is the current default) and `openAssistantSettings` (opens the system settings where the user can change the default).

**File**: `android/app/src/main/kotlin/com/divinerdojo/agentic_journal/MainActivity.kt`

**Full replacement content**:
```kotlin
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

    /// Check if this app currently holds the ROLE_ASSISTANT.
    /// Returns true if we are the default, false otherwise.
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

    /// Open the system settings page where the user can set the default
    /// digital assistant app.
    private fun openAssistantSettings() {
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            // Android 10+: Open the "Default apps" settings which includes
            // the digital assistant role assignment.
            Intent(Settings.ACTION_MANAGE_DEFAULT_APPS_SETTINGS)
        } else {
            // Older Android: Open voice input settings as a fallback.
            Intent(Settings.ACTION_VOICE_INPUT_SETTINGS)
        }
        // FLAG_ACTIVITY_NEW_TASK is required when launching from a non-Activity context,
        // and also prevents the Settings app from being added to our back stack.
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        startActivity(intent)
    }
}
```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter build apk --debug 2>&1 | tail -5
```

**Acceptance**: APK builds with the new Kotlin code. No compilation errors.

**Checkpoint**: Yes — **security-relevant** (platform channel is a bridge between native and Flutter, handles intent data) + **architecture choice** (platform channel pattern). Specialists: security-specialist, architecture-consultant.

---

### Task 4: Flutter AssistantRegistrationService

**What**: Create the Dart-side platform channel wrapper. This service provides a clean API that the rest of the Flutter app uses — the UI never interacts with `MethodChannel` directly. Includes iOS no-op fallback.

**File**: `lib/services/assistant_registration_service.dart`

**Content**:
```dart
// ===========================================================================
// file: lib/services/assistant_registration_service.dart
// purpose: Platform channel wrapper for Android assistant registration.
//
// Platform Channels (for the Python developer):
//   This is the Dart side of a Kotlin↔Dart bridge. When you call
//   _channel.invokeMethod('isDefaultAssistant'), Flutter sends a message
//   to the Kotlin code in MainActivity.kt, which calls Android APIs and
//   returns the result. On iOS, these methods will throw PlatformException
//   (no iOS assistant concept), so we catch and return safe defaults.
//
// Why a Service class (not a repository)?
//   Services wrap external platform APIs. Repositories wrap data storage.
//   This class wraps Android's RoleManager API via a platform channel —
//   it's a platform service, not a data repository.
// ===========================================================================

import 'dart:io' show Platform;
import 'package:flutter/services.dart';

/// Provides access to Android's default assistant registration system.
///
/// On Android: checks if this app is the default assistant and opens
/// the system settings where the user can change it.
/// On iOS: all methods return safe defaults (no assistant concept on iOS).
///
/// The [isAndroid] parameter enables testing: in flutter test, Platform.isAndroid
/// is always false, so we inject the platform check to make the channel code
/// path reachable in tests.
class AssistantRegistrationService {
  final MethodChannel _channel;
  final bool _isAndroid;

  /// Creates the service.
  ///
  /// [channel] defaults to the production channel. Override in tests to use
  /// a mock channel via TestDefaultBinaryMessengerBinding.
  /// [isAndroid] defaults to Platform.isAndroid. Override to `true` in tests
  /// to exercise the channel code path.
  AssistantRegistrationService({
    MethodChannel? channel,
    bool? isAndroid,
  })  : _channel = channel ?? const MethodChannel('com.divinerdojo.journal/assistant'),
        _isAndroid = isAndroid ?? Platform.isAndroid;

  /// Check if this app is currently set as the default digital assistant.
  ///
  /// Returns `true` only on Android 10+ when the app holds ROLE_ASSISTANT.
  /// Returns `false` on iOS, older Android, or if the check fails.
  Future<bool> isDefaultAssistant() async {
    if (!_isAndroid) return false;
    try {
      final result = await _channel.invokeMethod<bool>('isDefaultAssistant');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }

  /// Open the system settings screen where the user can set the default
  /// digital assistant app.
  ///
  /// On Android 10+: opens Default Apps settings.
  /// On older Android: opens Voice Input settings.
  /// On iOS: no-op.
  Future<void> openAssistantSettings() async {
    if (!_isAndroid) return;
    try {
      await _channel.invokeMethod<void>('openAssistantSettings');
    } on PlatformException {
      // If we can't open assistant settings, fail silently.
      // The UI already shows manual instructions as a fallback.
    }
  }

  /// Check if the app was launched via the assistant gesture (long-press Home).
  ///
  /// Returns `true` exactly once after an assistant-gesture launch, then
  /// clears the flag. This prevents re-triggering on hot reload or
  /// navigation rebuilds.
  ///
  /// Returns `false` on iOS or if the check fails.
  Future<bool> wasLaunchedAsAssistant() async {
    if (!_isAndroid) return false;
    try {
      final result = await _channel.invokeMethod<bool>('wasLaunchedAsAssistant');
      return result ?? false;
    } on PlatformException {
      return false;
    }
  }
}
```

**Riverpod Provider** (add to `lib/providers/settings_providers.dart`):
```dart
/// Provider for the assistant registration service.
final assistantServiceProvider = Provider<AssistantRegistrationService>((ref) {
  return AssistantRegistrationService();
});

/// Provides the current default assistant status.
/// Refreshed when the settings screen is visited.
final isDefaultAssistantProvider = FutureProvider<bool>((ref) async {
  final service = ref.watch(assistantServiceProvider);
  return service.isDefaultAssistant();
});
```

**Verification**: `dart analyze lib/services/assistant_registration_service.dart` reports zero errors.

**Acceptance**: Service class exists with three methods, provider registered.

**Checkpoint**: No — service wrapper with no business logic.

---

### Task 5: Onboarding State Management

**What**: Create providers for first-launch detection using `shared_preferences`. The onboarding screen should show only once — after the user completes it, a flag is persisted so subsequent launches go straight to the session list.

**File**: `lib/providers/onboarding_providers.dart`

**Content**:
```dart
// ===========================================================================
// file: lib/providers/onboarding_providers.dart
// purpose: Manages first-launch detection for the onboarding flow.
//
// SharedPreferences (for the Python developer):
//   SharedPreferences is Android/iOS's equivalent of a simple key-value store
//   (like a persistent dict). It's backed by an XML file on Android and
//   NSUserDefaults on iOS. Good for small settings, NOT for structured data
//   (use drift/SQLite for that).
//
// Why not use drift for this?
//   The onboarding flag needs to be checked BEFORE the database is ready.
//   SharedPreferences is synchronous-ready (after initial async load),
//   while drift requires async initialization. Using SharedPreferences
//   avoids a chicken-and-egg problem where we'd need the DB to decide
//   whether to show onboarding, but the DB isn't ready yet.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Key used in SharedPreferences to track onboarding completion.
const _onboardingCompleteKey = 'onboarding_complete';

/// Provider for the SharedPreferences instance.
///
/// This must be overridden in main.dart with the actual instance
/// (SharedPreferences requires async initialization).
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider must be overridden in ProviderScope',
  );
});

/// Notifier to mark onboarding as complete.
///
/// This is the SINGLE SOURCE OF TRUTH for onboarding state. Do NOT create
/// a separate Provider<bool> that reads from SharedPreferences directly —
/// that would cause widgets watching the separate provider to miss updates
/// when completeOnboarding() is called. Always watch this notifier.
///
/// Called when the user finishes the onboarding flow. Persists the flag
/// to SharedPreferences so the onboarding screen won't show again.
class OnboardingNotifier extends StateNotifier<bool> {
  final SharedPreferences _prefs;

  OnboardingNotifier(this._prefs) : super(_prefs.getBool(_onboardingCompleteKey) ?? false);

  /// Mark onboarding as complete. Persists to SharedPreferences.
  /// Idempotent — safe to call multiple times.
  Future<void> completeOnboarding() async {
    await _prefs.setBool(_onboardingCompleteKey, true);
    state = true;
  }
}

/// Provider for the onboarding notifier.
///
/// The notifier's STATE (bool) is the onboarding completion status.
/// Watch `onboardingNotifierProvider` to get the current bool value.
/// Use `ref.read(onboardingNotifierProvider.notifier).completeOnboarding()`
/// to mark onboarding as done.
final onboardingNotifierProvider =
    StateNotifierProvider<OnboardingNotifier, bool>((ref) {
  final prefs = ref.watch(sharedPreferencesProvider);
  return OnboardingNotifier(prefs);
});
```

**Update `lib/main.dart`**: Initialize SharedPreferences before runApp and pass it as a ProviderScope override.

```dart
import 'package:shared_preferences/shared_preferences.dart';
import 'providers/onboarding_providers.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();

  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
      ],
      child: const AgenticJournalApp(),
    ),
  );
}
```

**Verification**: `dart analyze lib/providers/onboarding_providers.dart` reports zero errors.

**Acceptance**: Onboarding state can be read synchronously, persists across app restarts.

**Checkpoint**: Yes — **state management** (new Riverpod providers, SharedPreferences integration). Specialists: architecture-consultant, qa-specialist.

---

### Task 6: Settings Screen

**What**: Build the settings screen showing assistant registration status and a setup button. Accessible from session list app bar via a gear icon.

**File**: `lib/ui/screens/settings_screen.dart`

**UI Layout**:
```
AppBar: "Settings"
Body:
  Card: "Digital Assistant"
    - Status line: "Default assistant: [Yes ✓ / No ✗]"
    - Button: "Set as Default Assistant" (calls openAssistantSettings)
    - Text: manual instructions as fallback
  Card: "About"
    - App name and version
    - "Phase 2 — Offline journaling with assistant gesture"
```

**Key behaviors**:
- Watches `isDefaultAssistantProvider` for reactive status updates
- Calls `assistantServiceProvider.openAssistantSettings()` on button tap
- Invalidates `isDefaultAssistantProvider` when returning from system settings (using `WidgetsBindingObserver.didChangeAppLifecycleState`)
- Shows a loading indicator while checking assistant status

**Verification**: Widget test confirms the screen renders, shows status, and handles button tap.

**Acceptance**: Settings screen shows assistant status, button opens system settings.

**Checkpoint**: No — UI-only, no business logic or architecture decisions.

---

### Task 7: Onboarding Screen

**What**: Build the first-launch onboarding screen that explains the app and guides the user to set it as the default assistant.

**File**: `lib/ui/screens/onboarding_screen.dart`

**UI Layout** (PageView with 2-3 pages):
```
Page 1: "Welcome to Agentic Journal"
  - Icon/illustration
  - "Your AI-powered personal journal"
  - "Capture your thoughts through natural conversation"

Page 2: "Set Up Assistant Gesture"
  - Icon: phone with home button
  - "Long-press the Home button to start journaling instantly"
  - Button: "Set as Default Assistant" → opens system settings
  - Text: "You can always change this later in Settings"

Page 3 (optional): "You're All Set!"
  - Checkmark icon
  - "Start your first journal entry"
  - Button: "Begin Journaling" → completes onboarding, navigates to session list
```

**Key behaviors**:
- Uses `PageView` with dot indicators for page navigation
- "Skip" button in top-right for users who want to skip setup
- Completing onboarding (last page button or skip) calls `onboardingNotifier.completeOnboarding()`
- After completion, navigates to session list with `pushReplacementNamed('/')`

**Verification**: Widget test confirms pages render, skip works, completion persists flag.

**Acceptance**: First launch shows onboarding. After completing, subsequent launches skip it.

**Checkpoint**: No — UI scaffolding only.

---

### Task 8: Navigation and Intent Routing

**What**: Update `lib/app.dart` to add new routes, handle onboarding redirect, and detect assistant-gesture launches.

**Changes to `lib/app.dart`**:

1. Add route entries:
   - `'/settings'` → `SettingsScreen()`
   - `'/onboarding'` → `OnboardingScreen()`

2. Change `initialRoute` logic:
   - Watch `onboardingNotifierProvider` (the single source of truth — NOT a separate hasCompleted provider)
   - If value is `false` → initial route is `/onboarding`
   - Otherwise → initial route is `/`

3. **Assistant-launch detection** (IMPORTANT — lifecycle anchor):
   - Convert `AgenticJournalApp` from `ConsumerWidget` to `ConsumerStatefulWidget`
   - In `initState()`, call `wasLaunchedAsAssistant()` EXACTLY ONCE with a `_assistantLaunchChecked` guard bool
   - If the result is `true`, use `WidgetsBinding.instance.addPostFrameCallback` to auto-start a new session and navigate to `/session`
   - NEVER call `wasLaunchedAsAssistant()` in `build()` — widget rebuilds would re-trigger the check
   - The one-shot flag on the Kotlin side provides defense-in-depth, but the Dart-side `_assistantLaunchChecked` guard is the primary protection against double-fire during hot-reload

   ```dart
   class _AgenticJournalAppState extends ConsumerState<AgenticJournalApp> {
     bool _assistantLaunchChecked = false;

     @override
     void initState() {
       super.initState();
       _checkAssistantLaunch();
     }

     Future<void> _checkAssistantLaunch() async {
       if (_assistantLaunchChecked) return;
       _assistantLaunchChecked = true;

       final service = ref.read(assistantServiceProvider);
       final wasAssistant = await service.wasLaunchedAsAssistant();
       if (wasAssistant && mounted) {
         WidgetsBinding.instance.addPostFrameCallback((_) async {
           await ref.read(sessionNotifierProvider.notifier).startSession();
           if (mounted) {
             Navigator.of(context).pushNamed('/session');
           }
         });
       }
     }
     // ... build() method with MaterialApp as before
   }
   ```

4. Add settings gear icon to `session_list_screen.dart` app bar:
   ```dart
   actions: [
     IconButton(
       icon: const Icon(Icons.settings),
       onPressed: () => Navigator.pushNamed(context, '/settings'),
     ),
   ],
   ```

**Verification**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter build apk --debug 2>&1 | tail -5
```

**Acceptance**: All routes work, first launch shows onboarding, settings accessible via gear icon, assistant launch auto-starts session.

**Checkpoint**: Yes — **architecture choice** (routing pattern, intent detection flow). Specialists: architecture-consultant, independent-perspective.

---

### Task 9: Tests

**What**: Write tests for all new code. Target >= 80% coverage on new files.

**Test files**:

1. **`test/services/assistant_registration_service_test.dart`**
   - **Testability approach**: Construct `AssistantRegistrationService(isAndroid: true)` in tests to bypass the `Platform.isAndroid` guard. Mock the MethodChannel using `TestDefaultBinaryMessengerBinding` to intercept channel calls.
   - Test `isDefaultAssistant()` returns `true` when channel returns `true`
   - Test `isDefaultAssistant()` returns `false` when channel returns `false`
   - Test `isDefaultAssistant()` returns `false` on `PlatformException`
   - Test `isDefaultAssistant()` returns `false` when `isAndroid: false` (iOS path)
   - Test `openAssistantSettings()` calls the channel method
   - Test `wasLaunchedAsAssistant()` returns channel result

2. **`test/providers/onboarding_providers_test.dart`**
   - **Setup**: Call `SharedPreferences.setMockInitialValues({})` in `setUp()` to ensure test isolation
   - Test `onboardingNotifierProvider` returns `false` initially (no key in prefs)
   - Test `onboardingNotifier.completeOnboarding()` sets state to `true`
   - Test `completeOnboarding()` called twice is idempotent (no exception, still `true`)
   - Test provider throws `UnimplementedError` when `sharedPreferencesProvider` is not overridden

3. **`test/ui/settings_screen_test.dart`**
   - Widget test: screen renders with assistant status card
   - Widget test: "Set as Default" button is present
   - Widget test: about card shows app version
   - Widget test: lifecycle resume triggers re-read of `isDefaultAssistantProvider` (mock service, verify called twice: once on load, once on resume via `tester.binding.handleAppLifecycleStateChanged`)

4. **`test/ui/onboarding_screen_test.dart`**
   - Widget test: first page renders with welcome text
   - Widget test: skip button exists and calls completion
   - Widget test: page navigation works (swipe or dot tap)
   - Widget test: final page button completes onboarding
   - Widget test: navigating away mid-flow (Page 2) does NOT mark onboarding complete

5. **`test/app_routing_test.dart`** (NEW — addresses routing logic gap)
   - Widget test: `onboardingNotifier` state `false` → initial route is `/onboarding`
   - Widget test: `onboardingNotifier` state `true` → initial route is `/`
   - Widget test: `wasLaunchedAsAssistant` returns `true` → navigates to `/session`
   - Widget test: settings route `/settings` resolves to `SettingsScreen`
   - Use `ProviderScope` overrides for `sharedPreferencesProvider` and mock `AssistantRegistrationService`

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"
flutter test
flutter test --coverage
```

**Acceptance**: All new tests pass. Coverage >= 80% on new files.

**Checkpoint**: No — pure test writing.

---

### Task 10: Final Verification and Quality Gate

**What**: Run the full quality gate and verify all acceptance criteria.

**Commands**:
```bash
export PATH="$PATH:/c/src/flutter/bin"

# Full quality gate
python scripts/quality_gate.py --skip-reviews

# Manual verification checklist:
# 1. flutter build apk --debug succeeds
# 2. All tests pass
# 3. dart analyze reports zero errors
# 4. Coverage >= 80%
# 5. android:allowBackup="false" still set:
grep 'allowBackup="false"' android/app/src/main/AndroidManifest.xml

# Test assistant intent via adb (if emulator available):
# adb shell am start -a android.intent.action.ASSIST -n com.divinerdojo.agentic_journal/.MainActivity
```

**Acceptance**: Quality gate passes 5/5 (or 6/6 if review exists). APK builds. All acceptance criteria met.

**Checkpoint**: No — final verification only.

---

## Stretch Tasks

### Stretch A: Voice Input

**Dependencies**: `speech_to_text` package, microphone permission.

**Tasks**:
1. Add `speech_to_text` to `pubspec.yaml`
2. Add microphone permission to AndroidManifest.xml: `<uses-permission android:name="android.permission.RECORD_AUDIO" />`
3. Create `lib/services/voice_input_service.dart` wrapping `speech_to_text`
4. Add microphone toggle button to `journal_session_screen.dart` input bar (left of text field)
5. On tap: start listening → show waveform/pulse animation → on result, insert text into input field
6. Set `inputMethod = 'VOICE'` when sending voice-transcribed messages
7. Request permission gracefully with explanation dialog
8. Widget tests for microphone button states

### Stretch B: ConversationAgent Interface

**Purpose**: Extract abstract interface from `AgentRepository` to prepare for Layer B (Phase 3).

**Tasks**:
1. Create `lib/agents/conversation_agent.dart` with abstract class (in `lib/agents/`, NOT `lib/repositories/` — the interface defines behavior, not data access):
   ```dart
   abstract class ConversationAgent {
     String getGreeting({DateTime? lastSessionDate, required DateTime now});
     String? getFollowUp({required String latestUserMessage, required List<String> conversationHistory, required int followUpCount});
     bool shouldEndSession({required int followUpCount, required String latestUserMessage});
     String generateLocalSummary(List<String> userMessages);
   }
   ```
2. Make `AgentRepository` implement `ConversationAgent`
3. Update `SessionNotifier` to depend on `ConversationAgent` (not `AgentRepository`)
4. Update provider to expose `ConversationAgent` type
5. No behavior change — pure refactor

---

## Test Strategy

| Component | Test Type | Key Scenarios |
|---|---|---|
| AssistantRegistrationService | Unit (mocked channel) | Channel returns true/false, PlatformException handling, iOS no-op (isAndroid: false) |
| OnboardingProviders | Unit (mocked SharedPrefs) | First launch false, completion persists true, double-call idempotent, provider override check |
| SettingsScreen | Widget | Renders status, button present, about card, lifecycle resume re-reads status |
| OnboardingScreen | Widget | Pages render, skip works, completion navigates, mid-flow exit safe |
| App routing (app_routing_test) | Widget | Onboarding redirect on first launch, normal route, assistant-launch → /session, settings route |

## Definition of Done

- [ ] ACTION_ASSIST intent filter in AndroidManifest.xml
- [ ] Platform channel working (Kotlin ↔ Dart)
- [ ] Settings screen with assistant status and setup button
- [ ] Onboarding flow on first launch only
- [ ] Navigation routes for /settings and /onboarding
- [ ] Settings accessible from session list app bar
- [ ] All tests pass, coverage >= 80%, quality gate green
- [ ] (Stretch) Voice input via microphone button
- [ ] (Stretch) ConversationAgent abstract interface extracted

---

## Specialist Review Notes

Reviewed by architecture-consultant, security-specialist, and qa-specialist (DISC-20260219-235437-phase2-spec-review).

### Blocking Findings Addressed
1. **Architecture — assistant-launch lifecycle anchor**: `wasLaunchedAsAssistant()` must be called exactly once in `ConsumerStatefulWidget.initState()` with a `_assistantLaunchChecked` guard. Spec updated with concrete code showing the anchor point. Never call in `build()`.
2. **Security — allowBackup verification**: Added explicit `grep` check for `android:allowBackup="false"` in Task 2 verification and Task 10 checklist.
3. **QA — missing routing tests**: Added `test/app_routing_test.dart` with 4 scenarios covering onboarding redirect, normal route, assistant-launch detection, and settings route.
4. **QA — untestable service**: Refactored `AssistantRegistrationService` to accept injectable `isAndroid` and `channel` parameters. Tests pass `isAndroid: true` to exercise the channel code path.

### Advisory Findings Noted
- **Architecture**: Consider ADR-0012 for platform channel conventions (channel naming, primitive-types-only, iOS no-op pattern). Deferred to implementation phase.
- **Architecture**: `hasCompletedOnboardingProvider` removed — single source of truth is `onboardingNotifierProvider`. Doc comment warns against creating a separate provider.
- **Architecture**: ConversationAgent interface moved from `lib/repositories/` to `lib/agents/` (behavioral interface, not data access).
- **QA**: Added double-call idempotency test, lifecycle resume test for settings screen, mid-flow exit test for onboarding, `SharedPreferences.setMockInitialValues({})` requirement.
- **Security**: Voice-transcribed text should be treated as untrusted user input (noted for stretch goal implementation).
