---
walkthrough_id: WT-20260220-phase2-assistant-registration
phase: Phase 2
modules: [assistant-registration, onboarding, session-lifecycle, app-navigation]
target_audience: Developer new to Android and Flutter
bloom_levels: [Understand, Apply, Analyze]
mastery_tier: Tier 2 (API integration, async patterns, state management)
review_reference: REV-20260220-005000
adr_references: [ADR-0004, ADR-0007]
estimated_reading_time: 18_minutes
---

# Phase 2 Guided Walkthrough: Assistant Registration & Session Lifecycle

## Section 1: High-Level Summary

### What Phase 2 Does

Phase 2 adds three major capabilities to Agentic Journal:

1. **Android Assistant Registration** — Allows the app to register as your device's default assistant, so when you invoke the assistant gesture (squeeze the phone, press the assistant button, or say "Hey Assistant"), it launches Agentic Journal instead of Google Assistant or Siri.

2. **Onboarding Flow** — First-launch detection and routing that gates the app until the user completes setup.

3. **Session Management & Lifecycle** — Infrastructure to create journal sessions, send messages, handle completion, and ensure that concurrent operations (rapid gestures, back presses, network failures) don't orphan or duplicate sessions.

### Why It Matters

Recall **ADR-0004 (Offline-First Architecture)**: The assistant gesture must respond **instantly** without network. This puts unique demands on Phase 2:

- The Kotlin layer must detect the assistant gesture and notify Dart before the UI even loads.
- The session lifecycle must guard against race conditions — the user might gesture twice rapidly, or press back while a session is ending.
- The flow must survive all of these failure modes: network timeout, database lock, provider initialization delay, widget rebuild during navigation.

Phase 2 is where offline-first meets "respond now" in reality.

### The Reading Order

You'll walk through six files in this sequence:

1. **MainActivity.kt** — Where Kotlin receives the assistant gesture from Android
2. **AssistantRegistrationService** — Where Dart wraps the Kotlin methods
3. **OnboardingProviders** — First-launch detection and state management
4. **SettingsProviders** — Assistant status queries and date tracking
5. **SessionProviders** — Session lifecycle with defensive guards
6. **App.dart** — Root orchestration: routing, onboarding gate, auto-launch

Each layer builds on the previous one. By the end, you'll understand the full request flow from gesture to session creation.

---

## Section 2: The Platform Channel Bridge (Files 1–2)

### What Is a Platform Channel?

Dart code runs on the Dart VM, which doesn't have direct access to Android APIs. When Dart needs to call native code (like checking if the app is the default assistant), it uses a **platform channel** — a serialized message bridge.

Think of it like an RPC system:

```
Dart (flutter/services.dart)
    ↓ [MethodChannel serializes method name + args to bytes]
Dart VM ← → Native layer (Java/Kotlin)
    ↑ [Kotlin deserializes, executes, sends back result]
Kotlin (android/MainActivity.kt)
```

The channel name (`com.divinerdojo.journal/assistant`) must match exactly on both sides, or the message will never route.

### File 1: MainActivity.kt — The Kotlin Side

Let's read the Kotlin code strategically. Start here:

```kotlin
private val CHANNEL = "com.divinerdojo.journal/assistant"
private var launchedAsAssistant = false
```

**Why this field?** When Android launches the app via the assistant gesture, the OS sends an `Intent` with `action == Intent.ACTION_ASSIST`. But Dart doesn't get this Intent immediately — the Flutter engine takes a few frames to initialize. We need to **capture the gesture flag immediately** in `onCreate`, then hand it to Dart later.

```kotlin
override fun onCreate(savedInstanceState: Bundle?) {
    super.onCreate(savedInstanceState)
    launchedAsAssistant = intent?.action == Intent.ACTION_ASSIST ||
            intent?.action == "android.intent.action.VOICE_ASSIST"
}
```

This runs before the Flutter engine is even initialized. We're setting a flag: "Hey, we were launched as assistant."

Then comes the critical part:

```kotlin
override fun onNewIntent(intent: Intent) {
    super.onNewIntent(intent)
    launchedAsAssistant = intent.action == Intent.ACTION_ASSIST ||
            intent.action == "android.intent.action.VOICE_ASSIST"
}
```

**Why `onNewIntent`?** In `AndroidManifest.xml`, the activity is marked `android:launchMode="singleTop"`. This means:

- **First time**: Android creates the app, calls `onCreate`.
- **App already running, user gestures again**: Android **reuses** the existing Activity and calls `onNewIntent` instead of creating a new one.

Without `onNewIntent`, the second gesture would be silently ignored. With it, we update the flag and notify Dart that a new gesture just arrived.

Now the platform channel setup:

```kotlin
override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        .setMethodCallHandler { call, result ->
            when (call.method) {
                "isDefaultAssistant" -> result.success(checkIsDefaultAssistant())
                "openAssistantSettings" -> { openAssistantSettings(); result.success(null) }
                "wasLaunchedAsAssistant" -> {
                    val wasLaunched = launchedAsAssistant
                    launchedAsAssistant = false  // read-then-clear
                    result.success(wasLaunched)
                }
                else -> result.notImplemented()
            }
        }
}
```

This runs **after** Flutter is ready. It registers a handler for three methods:

- `isDefaultAssistant`: Query the system API to see if this app is currently registered as the default assistant.
- `openAssistantSettings`: Open the system settings for the user to select a default assistant.
- `wasLaunchedAsAssistant`: **Return the gesture flag and immediately clear it** (read-then-clear pattern). This is important: Dart should only see the flag once. After Dart reads it, we reset it to false so the flag doesn't accidentally fire again on the next session.

The two query methods delegate to OS APIs:

```kotlin
private fun checkIsDefaultAssistant(): Boolean {
    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
        val roleManager = getSystemService(RoleManager::class.java)
        return roleManager?.isRoleHeld(RoleManager.ROLE_ASSISTANT) ?: false
    }
    return false
}
```

On Android 10+, there's a clean `RoleManager` API. On older devices, we return false (conservative). This is a defensive pattern: when in doubt, don't claim a capability we can't verify.

### File 2: AssistantRegistrationService — The Dart Side

Now the mirror side in Dart:

```dart
class AssistantRegistrationService {
  final MethodChannel _channel;
  final bool _isAndroid;

  AssistantRegistrationService({MethodChannel? channel, bool? isAndroid})
    : _channel = channel ?? const MethodChannel('com.divinerdojo.journal/assistant'),
      _isAndroid = isAndroid ?? Platform.isAndroid;
```

The constructor accepts optional overrides for the channel and platform. **Why?** For testing. In tests, we can pass a mock channel that doesn't call native code. This is the **constructor injection pattern** from ADR-0007 applied to a service dependency.

```dart
  Future<bool> isDefaultAssistant() async {
    if (!_isAndroid) return false;  // Non-Android platforms get false
    try {
      final result = await _channel.invokeMethod<bool>('isDefaultAssistant');
      return result ?? false;  // If native returns null, default to false
    } on PlatformException {
      return false;  // If native code crashes, return false (not re-throw)
    }
  }
```

The pattern here is defensive:

1. **Platform guard**: If not Android, return false immediately.
2. **Try-catch**: If the Kotlin side crashes, catch it and default to false. This is important for crash resilience — a broken platform channel shouldn't crash the app.
3. **Null coalesce**: If Kotlin returns null, treat it as false.

All three methods follow this pattern. The key insight: **Dart services wrapping platform channels must be defensive**. The native layer might not be initialized, might return null, might throw, and the Dart code must survive all of it.

### Platform Channel Timing: When Does It Work?

Here's the critical timing issue that the review flagged:

```
[App startup]
    ↓
onCreate() runs BEFORE Flutter engine is ready
    → Sets launchedAsAssistant = true
    ↓
configureFlutterEngine() runs AFTER Flutter is ready
    → Registers platform channel handler
    ↓
Dart code calls wasLaunchedAsAssistant()
    → Kotlin handler runs, returns true, clears flag
    ↓
[Session starts immediately, user has fast response]
```

But what if there's a delay in configureFlutterEngine? Or Dart code calls wasLaunchedAsAssistant() **before** the channel is fully set up?

Answer: It hangs or times out. The review noted this as a risk. The Phase 2 implementation handles it by wrapping the call in `addPostFrameCallback` with a try-catch (see File 6, app.dart).

---

## Section 3: State Management Layer (Files 3–4)

Now we step up a layer to see how the platform channel integrates with Dart's state management.

### Understanding Provider Patterns in Riverpod 2.x

Riverpod is a "reactive dependency injection" library. Providers are:

- **Declarative**: You describe what you want, not how to compute it
- **Reactive**: When a dependency changes, dependents automatically re-run
- **Testable**: Providers can be overridden in tests

There are three main provider types you'll see in Phase 2:

| Provider Type | Lifecycle | Use Case |
|---|---|---|
| `Provider<T>` | Compute once, cache forever | Stateless services (channels, DAOs) |
| `FutureProvider<T>` | Async compute, cache, recompute on demand | Async queries (fetch from API, read file) |
| `StateProvider<T>` or `Notifier<T>` | Mutable state, notifiers for complex logic | Session ID, form fields, complex state transitions |
| `StreamProvider<T>` | Real-time stream of values | Watch database changes, live list updates |

And crucially, two ways to access providers:

- `ref.watch(provider)` — Subscribe to changes (rebuilds widget if value changes)
- `ref.read(provider)` — Get current value once (no subscription, no rebuilds)

**Key insight**: `ref.watch` is for reactive UI (widgets that should re-render). `ref.read` is for imperative actions (button presses, initialization).

### File 3: OnboardingProviders — First-Launch Detection

```dart
final sharedPreferencesProvider = Provider<SharedPreferences>((ref) {
  throw UnimplementedError(
    'sharedPreferencesProvider must be overridden in ProviderScope.');
});
```

**Fail-fast pattern**: This provider intentionally throws if not overridden. Why? Because SharedPreferences is only available after app startup initialization, and we want to catch this mistake early in development rather than have it silently fail at runtime. In `main.dart`, this provider is overridden with the real SharedPreferences instance.

```dart
class OnboardingNotifier extends Notifier<bool> {
  @override
  bool build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return prefs.getBool(onboardingCompleteKey) ?? false;
  }
  // ...
}
```

**`ref.watch` here is a semantic mistake** (the review flagged it). SharedPreferences is not reactive. When you call `setBool`, it doesn't notify Riverpod that the value changed — you have to manually tell Riverpod. The correct pattern is:

```dart
  @override
  bool build() {
    final prefs = ref.read(sharedPreferencesProvider);  // ← Should be read, not watch
    return prefs.getBool(onboardingCompleteKey) ?? false;
  }
```

Why does it matter? `ref.watch` is a hint to readers: "This value is reactive." But it's not. Using `ref.read` is more honest about what's happening.

```dart
  Future<void> completeOnboarding() async {
    final prefs = ref.read(sharedPreferencesProvider);  // ← Correctly uses ref.read
    await prefs.setBool(onboardingCompleteKey, true);
    state = true;  // Manually notify Riverpod
  }
```

After saving to disk, we manually update `state = true`. This tells Riverpod: "The state changed, notify dependents." This is how `StateNotifier` works — you own the state mutations.

### File 4: SettingsProviders — Derived State

```dart
final assistantServiceProvider = Provider<AssistantRegistrationService>((ref) {
  return AssistantRegistrationService();
});
```

This is straightforward: a stateless service, created once and reused. No dependencies.

```dart
final isDefaultAssistantProvider = FutureProvider<bool>((ref) async {
  final service = ref.watch(assistantServiceProvider);
  return service.isDefaultAssistant();
});
```

This is a `FutureProvider`, which means:

- The first time it's called, it triggers `service.isDefaultAssistant()` (an async call)
- While loading, it returns an `AsyncValue.loading` state
- When done, it caches the result
- If you read it again, it returns the cached result without re-computing

This is useful for Settings screens: "Is this app the default assistant?" Query once, cache, display the result.

```dart
final lastSessionDateProvider = FutureProvider<DateTime?>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  final sessions = await sessionDao.getAllSessionsByDate();
  if (sessions.isEmpty) return null;
  return sessions.first.startTime;
});
```

This provider **has a bug** that the review flagged. It re-fetches all sessions every time, duplicating the query logic already in `allSessionsProvider`. The correct pattern is:

```dart
final lastSessionDateProvider = FutureProvider<DateTime?>((ref) async {
  final sessions = ref.watch(allSessionsProvider);
  return sessions.when(
    data: (list) => list.isEmpty ? null : list.first.startTime,
    loading: () => null,
    error: (_, __) => null,
  );
});
```

Derive from the stream, don't duplicate the DAO call. This keeps the source of truth single.

---

## Section 4: Session Lifecycle and Defensive Guards (File 5)

This is where the complexity lives. The review identified three defensive guards that prevent session data corruption under concurrent operations.

### Streaming Sessions: The Foundation

```dart
final allSessionsProvider = StreamProvider<List<JournalSession>>((ref) {
  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.watchAllSessions();
});
```

**StreamProvider**: This means Riverpod watches the database for changes. When `sessionDao.watchAllSessions()` emits a new list (because a session was created or updated), all dependents automatically re-run. This is how the UI stays in sync with the database.

The DAO is injected via constructor (ADR-0007):

```dart
// The DAO is injected via the database_provider.dart
final sessionDaoProvider = Provider((ref) {
  final db = ref.watch(databaseProvider);
  return SessionDao(db);
});
```

### The Session State Machine

```dart
class SessionState {
  final String? activeSessionId;
  final int followUpCount;
  final List<String> usedQuestions;
  final bool isSessionEnding;
  // ...
}
```

This is the Dart equivalent of a state enum. It tracks:

- `activeSessionId`: Is a session in progress? Which one?
- `followUpCount`: How many follow-up messages have been sent?
- `usedQuestions`: Which questions have we already asked (to avoid repeats)?
- `isSessionEnding`: Is an end-session operation in progress?

That last field is the key to understanding the defensive guard.

### Guard 1: startSession() Active-Session Guard

```dart
Future<String> startSession() async {
  // GUARD: prevent orphaned sessions from rapid calls
  if (state.activeSessionId != null) return state.activeSessionId!;
  // ... rest of the method
}
```

**The race condition it prevents:**

```
[User gestures twice rapidly]
    ↓
startSession() called twice
    ↓
First call: activeSessionId == null, enters function
Second call: activeSessionId == null (first call hasn't finished yet), enters function
    ↓
[Both calls now run createSession(), get two session IDs]
    ↓
Orphaned session: One session is created but never written to the database
(or both are written, causing data duplication)
```

The guard: Before doing anything, check if a session is already active. If yes, return that session ID. If no, proceed.

**Timeline with guard:**

```
[First call]  activeSessionId = null → enter, set activeSessionId = "session-1", continue
[Second call] activeSessionId = "session-1" → return "session-1" immediately, no duplicate
```

This is a simple idempotency check. If called multiple times rapidly, it's safe — the second and third calls just return the same session ID.

### Guard 2: endSession() Concurrent-Call Guard

```dart
Future<void> endSession() async {
  // GUARD: prevent duplicate closing from concurrent calls
  if (state.isSessionEnding) return;
  // ... rest of the method
}
```

**The race condition it prevents:**

```
[User is in session, presses back button]
[This calls endSession()]
    ↓
endSession() starts: generates summary, saves closing message, sets state
    ↓
[Before endSession() completes, user presses back again]
[This calls endSession() a second time]
    ↓
Second call: isSessionEnding == false (first call hasn't set it yet), enters function
    ↓
[Both calls now generate summaries and save closing messages]
    ↓
Duplicate closing message in database
```

The guard: Before ending the session, check if an end-session operation is already in progress. If yes, return immediately (idempotent). If no, set `isSessionEnding = true` and proceed.

**Timeline with guard:**

```
[First call]  isSessionEnding = false → enter, set isSessionEnding = true, continue
[Second call] isSessionEnding = true → return immediately, no duplicate
```

### Guard 3: sendMessage() Implicit Guard via State Check

The `sendMessage()` method doesn't have an explicit guard, but it has an implicit safety check:

```dart
Future<void> sendMessage(String text) async {
  if (state.activeSessionId == null) return;  // Implicit guard
  // ... rest
}
```

If there's no active session, the method is a no-op. This prevents sending messages to null session IDs.

### Why These Guards Matter

Without guards, here's what could happen:

1. **Orphaned sessions**: User gestures twice, two sessions created, one is "forgotten" in memory
2. **Duplicate messages**: User presses back during endSession, closing message saved twice
3. **Corrupt state**: State machine has `activeSessionId != null` but database has no session with that ID

The guards are **defensive programming**: assume the worst (concurrent calls, timing races, user impatience) and prevent data corruption.

### StateNotifier vs Notifier: Why StateNotifier?

The code uses `StateNotifier<SessionState>`, which is the **legacy** Riverpod 1.x pattern. Riverpod 2.x prefers `Notifier<T>`. Why didn't Phase 2 migrate?

Answer: The review didn't recommend it (not a blocking issue), and migrating `StateNotifier` → `Notifier` is mechanical but risky during active development. The existing `StateNotifier` works fine. Migration is a separate task.

**The pattern difference:**

```dart
// StateNotifier (legacy, used in Phase 2)
class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier() : super(const SessionState());

  void updateState() {
    state = state.copyWith(activeSessionId: "new-id");  // Mutate state directly
  }
}

// Notifier (Riverpod 2.x, new style)
class SessionNotifier extends Notifier<SessionState> {
  @override
  SessionState build() => const SessionState();

  void updateState() {
    state = state.copyWith(activeSessionId: "new-id");  // Same mutation pattern
  }
}
```

Both work the same way. `Notifier` is just the new preferred style. For Phase 2, `StateNotifier` is fine.

---

## Section 5: The Orchestration Layer (File 6: app.dart)

Now everything connects at the root.

### The Root Widget

```dart
class AgenticJournalApp extends ConsumerStatefulWidget {
  const AgenticJournalApp({super.key});
  @override
  ConsumerState<AgenticJournalApp> createState() => _AgenticJournalAppState();
}
```

`ConsumerStatefulWidget` is a widget that can access `ref`. It's like `StatefulWidget` but with Riverpod integration.

### Initialization Hook: Assistant Launch Detection

```dart
@override
void initState() {
  super.initState();
  _checkAssistantLaunch();
}

Future<void> _checkAssistantLaunch() async {
  if (_assistantLaunchChecked) return;  // Guard: only check once per app lifetime
  _assistantLaunchChecked = true;

  final service = ref.read(assistantServiceProvider);
  final wasAssistant = await service.wasLaunchedAsAssistant();
  final hasOnboarded = ref.read(onboardingNotifierProvider);

  if (wasAssistant && hasOnboarded && mounted) {
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      try {
        await ref.read(sessionNotifierProvider.notifier).startSession();
        _navigatorKey.currentState?.pushNamed('/session');
      } catch (_) {
        // startSession failed — stay on initial route
      }
    });
  }
}
```

**What's happening:**

1. `wasLaunchedAsAssistant()` — Call the platform channel to check if we were launched via gesture
2. `hasOnboarded` — Check if the user has completed onboarding (they might be on first launch)
3. If both true: Start a session automatically and navigate to `/session`

**Why `addPostFrameCallback` and `try-catch`?**

- `addPostFrameCallback`: We can't navigate until the first frame has rendered. This callback runs after the UI is ready.
- `try-catch`: If `startSession()` fails (database locked, initialization incomplete), we silently fail and stay on the current route. This is defensive — the app should never crash because session creation failed.

**Why `ref.read` instead of `ref.watch`?**

- `wasLaunchedAsAssistant`: A one-time query, not reactive. No point in watching.
- `hasOnboarded`: We read it once at startup. If the user changes it during app execution, we don't need to re-check (no automatic re-launch). So `read` is correct.

### Routing: Conditional Initialization

```dart
@override
Widget build(BuildContext context) {
  final hasCompletedOnboarding = ref.watch(onboardingNotifierProvider);
  return MaterialApp(
    title: 'Agentic Journal',
    navigatorKey: _navigatorKey,
    theme: AppTheme.light,
    darkTheme: AppTheme.dark,
    themeMode: ThemeMode.system,
    initialRoute: hasCompletedOnboarding ? '/' : '/onboarding',
    routes: {
      '/': (context) => const SessionListScreen(),
      '/session': (context) => const JournalSessionScreen(),
      '/settings': (context) => const SettingsScreen(),
      '/onboarding': (context) => const OnboardingScreen(),
    },
    // ...
  );
}
```

**`ref.watch(onboardingNotifierProvider)`** — We watch this because it should affect which route the app starts on. If the user completes onboarding, the app should re-build and start at `/` instead of `/onboarding`.

**The routing gate:**

```dart
initialRoute: hasCompletedOnboarding ? '/' : '/onboarding'
```

If onboarding is not complete, start at the onboarding screen. Otherwise, start at the home screen (session list).

### Data Flow: From Gesture to Screen

Let's trace a complete scenario:

```
[User: Squeeze phone to open assistant]
    ↓
[Android OS: See default assistant is Agentic Journal]
    ↓
[Android: Launch MainActivity with ACTION_ASSIST]
    ↓
MainActivity.onCreate() runs
    → Sets launchedAsAssistant = true
    ↓
[Dart app starts, builds root widget]
    ↓
app.dart: initState() calls _checkAssistantLaunch()
    ↓
wasLaunchedAsAssistant() → Calls platform channel
    → Kotlin reads launchedAsAssistant (true) and clears it
    ↓
_checkAssistantLaunch() sees wasAssistant=true, hasOnboarded=true
    ↓
addPostFrameCallback: Calls sessionNotifierProvider.notifier.startSession()
    ↓
startSession() checks: activeSessionId == null? Yes.
    → Creates session in database
    → Queries assistant for greeting
    → Saves greeting as first message
    → Sets activeSessionId = "session-123"
    ↓
Navigation: _navigatorKey.pushNamed('/session')
    ↓
JournalSessionScreen builds with activeSessionId = "session-123"
    → Subscribes to activeSessionMessagesProvider
    → Displays greeting message to user
    ↓
[Response time: ~500ms from gesture to greeting on screen]
```

**Key insight**: The offline-first architecture (ADR-0004) means all of this happens locally. No network round-trip to check "is this the default assistant?" or to fetch the greeting. The greeting is prepared by the local agent, saved to the local database, and displayed. That's why the response is fast.

### The Three Routes

```dart
routes: {
  '/': (context) => const SessionListScreen(),     // Home: list of past sessions
  '/session': (context) => const JournalSessionScreen(),  // Active session
  '/settings': (context) => const SettingsScreen(),     // Settings + assistant registration UI
  '/onboarding': (context) => const OnboardingScreen(),  // First launch
}
```

- **`/`**: SessionListScreen shows all past sessions, with an "Start New Session" button
- **`/session`**: JournalSessionScreen is the active session UI where the user types messages
- **`/settings`**: Assistant registration UI (buttons to check status, open settings)
- **`/onboarding`**: First launch flow (welcome, privacy notice, assistant registration offer)

### Dynamic Routes: Session Details

```dart
onGenerateRoute: (settings) {
  if (settings.name == '/session/detail') {
    final sessionId = settings.arguments as String;
    return MaterialPageRoute(
      builder: (context) => SessionDetailScreen(sessionId: sessionId),
    );
  }
  return null;
},
```

`onGenerateRoute` is called for routes not in the `routes` map. If someone navigates to `/session/detail?sessionId=123`, this generates the route dynamically, passing the session ID to the detail screen.

---

## Section 6: Key Concepts Summary

### Timing & Lifecycle

**The Cold-Start Challenge:**

On first app launch (especially via assistant gesture), there's a race:

```
Thread 1: [Platform layer initializes]
Thread 2: [Dart VM starts]
Thread 3: [Flutter engine configures]
Thread 4: [MainActivity.onNewIntent fires]
Thread 5: [Platform channel handler registers]
```

These are **not sequential** — they overlap. If Dart code calls the platform channel before the handler is registered, it hangs or times out.

**The Phase 2 solution:**

- `addPostFrameCallback`: Delays the platform channel call until Flutter is fully ready
- `try-catch`: If it fails anyway, the app doesn't crash
- Read-then-clear flag: Ensures the gesture flag is consumed exactly once

### Race Conditions & Defensive Guards

The three guards (startSession active check, endSession concurrent check, sendMessage null check) are not paranoia — they're response to real failure modes:

1. **Rapid gestures** — User gestures twice in 100ms
2. **User impatience** — User presses back while endSession is running
3. **UI rebuilds** — Widget tree rebuilds trigger methods multiple times
4. **Database locks** — Concurrent writes to drift database

Each guard adds ~1 line of code and prevents a category of data corruption.

### Provider Patterns: watch vs read

| Use Case | Pattern | Why |
|---|---|---|
| Widget rebuilds when value changes | `ref.watch(provider)` | Subscribe to changes |
| Button click handler | `ref.read(provider)` | Get current value once |
| Initialization check | `ref.read(provider)` | No need for subscription |
| Conditional routing | `ref.watch(provider)` | Route should change if value changes |
| Derived FutureProvider | `ref.watch(upstream)` | React to upstream changes |

**Rule of thumb**: Use `watch` in `build()` methods, use `read` in event handlers and one-time checks.

### Constructor Injection (ADR-0007)

Every service and DAO in Phase 2 is injected, not global:

```dart
// Correct: Testable
class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier({required SessionDao sessionDao, required Ref ref})
    : _sessionDao = sessionDao, _ref = ref;
}

// Incorrect: Hard to test
class SessionNotifier extends StateNotifier<SessionState> {
  final sessionDao = SessionDao(AppDatabase.instance);  // Global!
}
```

With constructor injection, tests can pass a mock DAO. Without it, the real database is always used.

### Android Lifecycle: singleTop & onNewIntent

- **`launchMode="singleTop"`**: Same task instance reused
  - First gesture: `onCreate` + `configureFlutterEngine`
  - Second gesture (app running): `onNewIntent` only
- **Without `singleTop`**: Every gesture creates a new Activity instance (memory leak, visual stutter)

### Offline-First Guarantee (ADR-0004)

Phase 2 doesn't require network because:

- Session creation: Local database write only
- Greeting: Fetched from local agent (no cloud call)
- Message save: Local database write only
- Navigation: Purely local state

The only network operation is sync to Supabase, which happens in the background (Phase 4). Phase 2 is 100% offline-capable.

---

## Section 7: For Testing & Debugging

### How to Test Platform Channels

```dart
// In tests, override the channel with a mock:
testWidgets('Assistant gesture launches session', (WidgetTester tester) async {
  final mockChannel = MockMethodChannel();
  mockChannel.onMethodCall('wasLaunchedAsAssistant', (_) => true);

  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        assistantServiceProvider.overrideWithValue(
          AssistantRegistrationService(channel: mockChannel),
        ),
      ],
      child: const AgenticJournalApp(),
    ),
  );

  // Assert that /session route was pushed
  expect(find.byType(JournalSessionScreen), findsOneWidget);
});
```

### How to Test Riverpod Providers

```dart
test('startSession returns existing ID on rapid calls', () async {
  final container = ProviderContainer();

  final notifier = container.read(sessionNotifierProvider.notifier);

  final id1 = await notifier.startSession();
  final id2 = await notifier.startSession();  // Rapid second call

  expect(id1, equals(id2));  // Should return same ID, not create duplicate
});
```

### Debugging Platform Channel Timing

Add logging to see when things happen:

```kotlin
// In MainActivity.kt
override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
    super.configureFlutterEngine(flutterEngine)
    Log.d("AssistantBridge", "Platform channel registering")
    MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        .setMethodCallHandler { call, result ->
            Log.d("AssistantBridge", "Method called: ${call.method}")
            // ...
        }
    Log.d("AssistantBridge", "Platform channel ready")
}
```

If you see logs like:

```
D/AssistantBridge: Platform channel registering
D/AssistantBridge: Method called: wasLaunchedAsAssistant
D/AssistantBridge: Platform channel ready
```

Then the channel is working. If `wasLaunchedAsAssistant` is missing, the Dart code either failed or called before registration.

---

## Next Steps

After reading this walkthrough:

1. **Review the files** in reading order (Files 1-6)
2. **Run the tests** to see the patterns in action: `flutter test`
3. **Complete the quiz** to verify understanding
4. **Explain back** the three main design decisions:
   - Why is singleTop + onNewIntent necessary?
   - What would happen without the startSession guard?
   - Why use `ref.read` instead of `ref.watch` in _checkAssistantLaunch?

---

## References

- **ADR-0004**: Offline-First Architecture — explains why Phase 2 must work without network
- **ADR-0007**: Constructor Injection DAOs — explains why services are injected, not global
- **REV-20260220-005000**: Phase 2 Review — the checkpoint findings that motivated the defensive guards
- **Flutter Platform Channels**: https://docs.flutter.dev/platform-integration/platform-channels
- **Riverpod Documentation**: https://riverpod.dev

