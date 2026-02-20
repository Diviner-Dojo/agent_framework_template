---
quiz_id: QUIZ-20260220-phase2-assistant-registration
module: Phase 2 — Assistant Registration & Session Lifecycle
target_audience: Developer new to Android and Flutter
bloom_distribution: {remember: 2, understand: 4, apply: 3, analyze: 4, evaluate: 1}
total_questions: 14
pass_threshold: 0.70
time_limit_minutes: 30
open_book: true
---

# Phase 2 Quiz: Assistant Registration & Session Lifecycle

**Instructions:**
- You may reference the code and walkthrough while answering
- Focus on explaining concepts in your own words, not just copying code
- At least 70% correct (10/14 questions) to pass
- Questions are tagged with Bloom's level for your reference

---

## Section A: Platform Channels (Files 1–2)

### Q1 [Remember] — Platform Channel Basics
**What is the channel name used in Phase 2 to communicate between Kotlin and Dart?**

A) `com.divinerdojo.agentic_journal/platform`
B) `com.divinerdojo.journal/assistant`
C) `com.flutter.channel/assistant`
D) `android.intent.action/ASSIST`

<details>
<summary>Click to reveal answer</summary>

**Correct answer: B** — `com.divinerdojo.journal/assistant`

**Why this matters:** The channel name must match exactly on both sides (Kotlin and Dart). If they differ, messages never route. This is the RPC endpoint address.

**Common mistake:** Confusing the Intent action (`Intent.ACTION_ASSIST`) with the channel name. The Intent tells Android which app to launch; the channel name tells Dart how to talk to Kotlin.

</details>

---

### Q2 [Understand] — Why onNewIntent Exists
**In your own words, explain why MainActivity has both `onCreate()` and `onNewIntent()` methods. What problem does `onNewIntent()` solve?**

Provide a 2-3 sentence explanation.

<details>
<summary>Click to reveal answer</summary>

**Exemplar response:**

"Since the app is marked `launchMode="singleTop"`, Android reuses the same Activity instance instead of creating a new one when the user gestures again. `onCreate()` only runs on first launch, so we need `onNewIntent()` to detect that the app was already running and a new gesture just arrived. Without it, the second gesture would be silently ignored."

**Grading rubric:**
- ✓ Mentions singleTop launch mode
- ✓ Explains that onCreate doesn't run on subsequent gestures
- ✓ Shows that onNewIntent captures the new gesture

**Common mistakes:**
- Confusing Intent with the gesture flag (they're separate concepts)
- Thinking singleTop prevents duplicate Activity creation (it does, but that's not why we need onNewIntent)
- Missing the "flag capture for the second gesture" piece

</details>

---

### Q3 [Apply] — Platform Channel Defensive Patterns
**The AssistantRegistrationService wraps platform channel calls defensively. Given this code:**

```dart
Future<bool> isDefaultAssistant() async {
  if (!_isAndroid) return false;
  try {
    final result = await _channel.invokeMethod<bool>('isDefaultAssistant');
    return result ?? false;
  } on PlatformException {
    return false;
  }
}
```

**Trace through: What happens if the Kotlin side crashes? What does the app do?**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"If Kotlin crashes, the `invokeMethod` call throws a `PlatformException`. The try-catch catches it and returns `false`, making the method safe. The app doesn't crash; it just treats the platform layer as unavailable."

**Grading:**
- ✓ Identifies the try-catch
- ✓ Shows that PlatformException is caught (not re-thrown)
- ✓ Explains the safe fallback (returns false, not null)

**Why this matters:** A broken platform layer shouldn't crash the Dart app. Defensive fallbacks are essential for production apps.

**Alternative scenario:** What if `invokeMethod` returns `null` instead of crashing?

Answer: `result ?? false` handles it — null becomes false.

</details>

---

### Q4 [Analyze] — Timing Race in Platform Channels
**The review flagged a "platform channel timing race" as a risk. Describe the race condition: What could go wrong if Dart calls `wasLaunchedAsAssistant()` before the platform channel handler is registered?**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"The `invokeMethod` call would block or time out because there's no handler on the Kotlin side to receive it. The Dart code would hang, or the platform channel would time out after a delay (usually 30 seconds), causing a delayed or failed response. On cold app start, if Flutter initialization is slow, this could happen."

**Grading:**
- ✓ Identifies the root cause (handler not registered)
- ✓ Describes the symptom (hangs, times out)
- ✓ Explains why it matters in the app lifecycle (cold start is slow)

**How Phase 2 solves it:**
- `addPostFrameCallback` delays the call until Flutter is ready
- `try-catch` prevents a crash if it times out anyway

**Follow-up question (bonus):** Why can't we just make the handler registration faster?

Answer: We can't control when Flutter initializes the engine. It's out of our control, so we must code defensively by delaying the call.

</details>

---

## Section B: State Management & Providers (Files 3–4)

### Q5 [Understand] — ref.watch vs ref.read
**The walkthrough explains that OnboardingNotifier uses `ref.watch(sharedPreferencesProvider)` in `build()`, but the review marked it as semantically incorrect. Explain why `ref.read` is more appropriate here.**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"`ref.watch` is used for reactive values that should trigger rebuilds when they change. But SharedPreferences is not reactive — when you call `setBool`, it doesn't notify Riverpod automatically. Using `ref.watch` misleads readers into thinking this is reactive when it's not. `ref.read` is more honest: 'Get the value once, don't watch for changes.'"

**Grading:**
- ✓ Explains what ref.watch means (reactive, triggers rebuilds)
- ✓ Explains why SharedPreferences isn't reactive
- ✓ Shows that ref.read is clearer intent

**Key insight:** Choosing `watch` vs `read` isn't just a code optimization — it's a communication signal to future readers about whether the value is reactive.

</details>

---

### Q6 [Apply] — Deriving State Without Duplication
**The `lastSessionDateProvider` duplicates the DAO query instead of deriving from `allSessionsProvider`. Rewrite it correctly:**

```dart
// WRONG (current):
final lastSessionDateProvider = FutureProvider<DateTime?>((ref) async {
  final sessionDao = ref.watch(sessionDaoProvider);
  final sessions = await sessionDao.getAllSessionsByDate();
  if (sessions.isEmpty) return null;
  return sessions.first.startTime;
});

// CORRECT (your answer):
final lastSessionDateProvider = FutureProvider<DateTime?>((ref) async {
  // ... your code here
});
```

<details>
<summary>Click to reveal answer</summary>

**Exemplar response:**

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

**Grading:**
- ✓ Uses `ref.watch(allSessionsProvider)` (reactive, derives from existing provider)
- ✓ Handles AsyncValue with `.when()` (loading, error, data states)
- ✓ Returns null for loading/error states (safe defaults)
- ✓ Extracts `first.startTime` only from non-empty list

**Why this is better:**
- Single source of truth (allSessionsProvider)
- Automatically reacts to session list changes
- Avoids duplicate DAO queries
- More efficient (reuses cached result from allSessionsProvider)

</details>

---

## Section C: Session Lifecycle & Defensive Guards (File 5)

### Q7 [Understand] — The startSession Guard
**What race condition does the `startSession()` guard prevent? Describe the scenario without the guard.**

```dart
if (state.activeSessionId != null) return state.activeSessionId!;
```

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"Without the guard, if `startSession()` is called twice rapidly (e.g., rapid assistant gestures), both calls would enter the function body because the state hasn't been updated yet. Both would create separate sessions in the database, and the first one could be orphaned (forgotten) in memory. The guard ensures that if a session is already active, the second call just returns the existing session ID instead of creating a duplicate."

**Grading:**
- ✓ Identifies the race condition (concurrent calls)
- ✓ Explains the symptom (two sessions created)
- ✓ Shows what the guard does (idempotent return)

**Real-world scenario:** User clicks "Start Session" button twice in quick succession (network lag makes them click twice), or OS re-sends the assistant gesture.

</details>

---

### Q8 [Analyze] — endSession Guard vs startSession Guard
**Compare the two guards:**

1. `startSession()` guard: `if (state.activeSessionId != null) return state.activeSessionId!;`
2. `endSession()` guard: `if (state.isSessionEnding) return;`

**Why does `startSession()` return the session ID while `endSession()` just returns (void)?**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"`startSession()` must return a session ID because callers depend on it — they need to know which session was created (even if it was already active). Returning the existing ID is still correct; the caller gets a valid session ID either way. `endSession()` returns void, so it doesn't matter if it's called twice — the second call just returns without doing anything, which is safe."

**Grading:**
- ✓ Recognizes that return types affect guard design
- ✓ Explains why startSession must return the ID (callers need it)
- ✓ Explains why endSession returning void is fine (idempotent action)

**Deeper insight:** The guards are designed with the caller's needs in mind. If the caller needs data, the guard returns it. If the caller doesn't care, the guard just prevents duplicate side effects.

</details>

---

### Q9 [Debug Scenario] — Session State Corruption
**Here's a failing test:**

```dart
test('Rapid session start calls don\'t create duplicate sessions', () async {
  final container = ProviderContainer();
  final notifier = container.read(sessionNotifierProvider.notifier);

  final id1 = notifier.startSession();
  final id2 = notifier.startSession();

  // Both should return the same ID
  expect(await id1, equals(await id2));

  // Database should have exactly 1 session
  final sessions = await sessionDao.getAllSessions();
  expect(sessions.length, equals(1));  // FAILING: expects 1, got 2
});
```

**Without the guard, why does the test fail?**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"Without the guard, both `startSession()` calls enter the function body because the state hasn't been updated by either call yet. Both calls create a session in the database independently, so `getAllSessions()` returns 2 sessions instead of 1. With the guard, the second call sees that `activeSessionId != null` and returns immediately, so only 1 session is created."

**Grading:**
- ✓ Identifies that both calls enter the function
- ✓ Explains the database-level effect (2 sessions created)
- ✓ Shows how the guard fixes it (early return prevents second creation)

**Follow-up:** How would you fix this without the guard?

Answer: Make the DAO call atomic (database-level uniqueness constraint) or lock the session creation. But that's more complex; the guard is simpler.

</details>

---

### Q10 [Apply] — Guard Coverage
**Which of these calls should be guarded and why? Classify each:**

1. `sendMessage(String text)` — sending a user message
2. `getSessionHistory()` — fetching past messages
3. `updateSessionMetadata(...)` — updating last_updated timestamp
4. `deleteSession(String id)` — hard-deleting a session

For each, answer: **Guard needed (Y/N)? Why?**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

1. `sendMessage()` — **Y**, needs guard. Could send duplicate messages if called twice rapidly.
2. `getSessionHistory()` — **N**, read-only. Can't corrupt data; multiple calls are safe.
3. `updateSessionMetadata()` — **N**, idempotent. Updating last_updated twice gives same result as once.
4. `deleteSession()` — **Y**, needs guard. Second delete on already-deleted session could error or create inconsistency.

**Grading:**
- ✓ Identifies that writes need guards, reads don't
- ✓ Recognizes idempotency (update is safe) vs side effects (delete is risky)
- ✓ Explains reasoning for each

**Pattern:** Guard any operation that:
- Has side effects (creates, deletes, sends)
- Could race with itself
- Leaves inconsistent state if called twice

Don't guard:
- Reads (no mutations)
- Idempotent updates (same result on retry)

</details>

---

## Section D: App Orchestration (File 6)

### Q11 [Understand] — Routing Gate Logic
**The app routes to either `/` or `/onboarding` based on onboarding status. Explain the logic and why `ref.watch` is appropriate here (unlike in OnboardingNotifier).**

```dart
initialRoute: hasCompletedOnboarding ? '/' : '/onboarding',
```

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

"If the user hasn't completed onboarding, start at `/onboarding`. If they have, start at `/`. The app needs to re-build (re-route) if the onboarding status changes during execution (user completes onboarding in the onboarding screen). So `ref.watch` is correct here — it subscribes to changes. When the user completes onboarding and `state = true`, the widget rebuilds with a new `initialRoute`, which updates the navigation."

**Grading:**
- ✓ Explains the conditional routing logic
- ✓ Shows that the route should change if onboarding status changes
- ✓ Correctly identifies that `ref.watch` makes sense (reactive UI)

**Contrast:** In `OnboardingNotifier.build()`, we used `ref.read` because we only initialize once and manually manage state changes. In `AgenticJournalApp.build()`, we use `ref.watch` because the entire widget should rebuild and update the route.

**Key insight:** The same provider can use `watch` in some places (reactive) and `read` in others (one-time) depending on context.

</details>

---

### Q12 [Analyze] — Cold-Start Flow with Guards
**Trace the cold-start flow when the user gestures to open the assistant (assuming they've already completed onboarding):**

1. What happens in Kotlin?
2. What happens in Dart?
3. Where do the three defensive guards apply?

Provide a 5-10 sentence chronological trace.

<details>
<summary>Click to reveal answer</summary>

**Exemplar trace:**

"1. Android receives the gesture and calls MainActivity.onCreate(), which captures `launchedAsAssistant = true`.

2. Flutter initializes and calls configureFlutterEngine(), registering the platform channel handler.

3. Dart app starts, calls initState(), which calls _checkAssistantLaunch().

4. _checkAssistantLaunch() reads `wasLaunchedAsAssistant()` via platform channel, which returns true and clears the flag (read-then-clear guard #1).

5. In addPostFrameCallback, _checkAssistantLaunch() calls `startSession()`, which checks `if (state.activeSessionId != null)` (guard #2) — it's null, so it proceeds to create a session.

6. startSession creates a session in the database, gets a greeting from the agent, and saves it.

7. Navigation pushes `/session`, and JournalSessionScreen displays the greeting to the user."

**Grading:**
- ✓ Shows Kotlin → Android → Dart sequence
- ✓ Explains why addPostFrameCallback is needed
- ✓ Identifies where each guard applies (read-then-clear, active-session guard)
- ✓ Explains why try-catch wraps the callback (third guard against errors)

**Advanced observation:** The guards work at different layers:
- Read-then-clear: Kotlin side (flag consumption)
- Active-session: Dart side (state machine)
- Try-catch: Error handling (resilience)

</details>

---

### Q13 [Evaluate] — Is addPostFrameCallback Necessary?
**Defend or critique this statement: "We could simplify the code by calling `startSession()` directly in `_checkAssistantLaunch()` instead of wrapping it in `addPostFrameCallback`."**

Provide a 3-4 sentence evaluation.

<details>
<summary>Click to reveal answer</summary>

**Exemplar response (Critique):**

"No, we can't. `addPostFrameCallback` is necessary because navigation requires the widget tree to be fully built. If we call `startSession()` and navigate before the first frame renders, the navigation call would fail or have undefined behavior. `addPostFrameCallback` ensures the UI is ready before we navigate. Additionally, it gives time for the platform channel to fully initialize (reducing the timing race)."

**Grading rubric:**
- ✓ Explains that widgets must be built before navigation
- ✓ Notes that timing depends on platform channel setup
- ✓ Connects to the platform channel timing risk from File 1–2

**Alternative response (Defend the statement):**

"Actually, we could simplify it [explanation of why]. But the trade-off isn't worth it because [risks]. The current approach is defensive and well-motivated."

If you defend it, you must explain why and acknowledge the trade-off.

**Why this question matters:** It tests whether you understand the *why* behind a design choice, not just the implementation.

</details>

---

### Q14 [Change Impact] — Removing the Try-Catch
**If we removed the try-catch around `startSession()` in `_checkAssistantLaunch`, what would happen if session creation fails?**

```dart
// CURRENT (safe):
try {
  await ref.read(sessionNotifierProvider.notifier).startSession();
  _navigatorKey.currentState?.pushNamed('/session');
} catch (_) {
  // startSession failed — stay on initial route
}

// WITHOUT TRY-CATCH (risky):
await ref.read(sessionNotifierProvider.notifier).startSession();
_navigatorKey.currentState?.pushNamed('/session');
```

**What breaks? Provide 2-3 consequences.**

<details>
<summary>Click to reveal answer</summary>

**Expected response:**

1. **App crashes on unhandled exception**: If `startSession()` throws (e.g., database locked), the exception propagates and crashes the app, presenting a poor user experience on first launch.

2. **Navigation to broken state**: Even if the app doesn't crash, it would navigate to `/session` with a null session ID (because `startSession()` never completed), leading to a blank screen or null reference errors in JournalSessionScreen.

3. **Silent failures become obvious**: Without the guard, timing issues or database initialization problems become visible to users as crashes. With the guard, the app gracefully stays on the home screen and the user can try again.

**Grading:**
- ✓ Identifies that uncaught exceptions crash the app
- ✓ Explains that navigation would happen anyway (broken state)
- ✓ Shows why defensive programming matters for user experience

**Principle:** Defensive guards aren't just for safety — they provide better UX. Users expect the app to gracefully degrade, not crash on first launch.

</details>

---

## Scoring

**Total: 14 questions**
- 14/14 = 100% (expert)
- 12–13/14 = 86-93% (proficient)
- 10–11/14 = 71-79% (pass)
- 9/14 = 64% (below threshold)

**Pass threshold: 70% (10/14 correct)**

If you score below 70%, review the sections where you missed questions and retry.

If you score 70+%, proceed to the **Explain-Back Assessment**.

