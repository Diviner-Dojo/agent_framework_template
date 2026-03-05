---
discussion_id: DISC-20260304-145506-review-bug-fixes-phase3a-advisories
started: 2026-03-04T14:55:23.055129+00:00
ended: 2026-03-04T15:05:26.585574+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 4
---

# Discussion: DISC-20260304-145506-review-bug-fixes-phase3a-advisories

## Turn 1 — facilitator (evidence)
*2026-03-04T14:55:23.055129+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Ship bug fixes and Phase 3A advisory items: Bug 1 (keyboard overflow — TextField maxLines: null → 6), Bug 2 (STT stops after photo — capturePhotoDescription() restores paused state so orchestrator.resume() works), Advisory A1 (dispatch branch tests for _openQuickCapturePalette), Advisory A3 (FAB tooltip shows 'Opening...' during _isStarting), Advisory A9 (voice pre-enable ordering comment improved).
- **Files/scope**: lib/services/voice_session_orchestrator.dart, lib/ui/screens/journal_session_screen.dart, lib/ui/screens/session_list_screen.dart, test/services/voice_session_orchestrator_test.dart, test/ui/journal_session_screen_test.dart, test/ui/session_list_screen_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Two device-observed bugs caused user-facing failures (send button inaccessible on long input; STT permanently stopped after photo capture). Three Phase 3A advisories were deferred from REV-20260304-142456 for this sprint.
- **Explicit constraints**: ADHD clinical UX constraints apply (no gap-shaming, no streaks, 48dp tap targets). Regression tests required for all bug fixes tagged @Tags(['regression']).

---

## Turn 2 — qa-specialist (proposal)
*2026-03-04T14:59:17.768062+00:00 | confidence: 0.85*
*tags: qa, regression, dispatch-branches*

## QA Assessment (confidence: 0.85)

### Blocking Findings

**B1 (High) — Missing @Tags(['regression']) on regression test files**
Location: test/ui/journal_session_screen_test.dart, test/services/voice_session_orchestrator_test.dart
Both files hosting the new Bug 1 and Bug 2 regression tests lack @Tags(['regression']). testing_requirements.md states: 'Tag regression tests with @Tags(['regression']).' Without the tag, flutter test --tags regression filtering is broken and the quality gate regression guard cannot identify them. Protocol violation on two files simultaneously.
Fix: Add tags: ['regression'] to the specific regression testWidgets/test/group in each file.

### Advisory Findings

**A1 (Medium) — capturePhotoDescription non-paused branch not tested**
The regression test covers only the paused-state branch. The wasInContinuousMode && previousPhase!=idle → _startListening() branch (the pre-fix normal path) has no dedicated capturePhotoDescription test. A refactor touching the conditional could silently break it.
Fix: Add test for non-paused continuous case (caller did not call pause() before capturePhotoDescription).

**A2 (Medium) — pulse_check_in dispatch branch not covered**
Three of five dispatch branches are tested (__quick_mood_tap__, voice, text). The pulse_check_in branch routes to /check_in — a distinct path that could be silently unified with /session in a future refactor.
Fix: Add testWidgets for Check-In tile → /check_in route.

**A3 (Low) — Bare post-startContinuousMode assertion timing concern**
Test asserts phase==listening immediately after startContinuousMode without a microtask yield. Relies on mockTts.autoComplete=true being in force. If setUp ever changes this, the assertion becomes flaky. Primary regression assertion is unaffected.
Fix: Move/remove the incidental assertion or add a short await after startContinuousMode.

**A4 (Low) — Silence timeout path in capturePhotoDescription not tested**
No test covers: caller pauses → capturePhotoDescription → user says nothing → timeout → null returned with paused state restored. Timeout is not injectable (5-second hardcoded), making it CI-expensive to test.
Advisory: Acknowledge as known gap or make timeout injectable.

### Strengths
- Bug 2 regression test correctly models the full caller sequence (startContinuousMode → pause → capturePhotoDescription → assert phase=paused → resume → assert phase=listening).
- Bug 1 regression test is appropriately minimal — checks TextField.maxLines directly.
- Regression ledger entries well-formed: file, root cause, fix, test location.
- ProviderScope.containerOf(element) pattern used correctly — descendant element, not ProviderScope element itself.
- Test isolation is sound — each test calls SharedPreferences.setMockInitialValues({}) independently.

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-04T14:59:44.430975+00:00 | confidence: 0.87*
*tags: ux, maxlines, fab-state, accessibility*

## UX Assessment (confidence: 0.87)

### Advisory Findings

**A5 (Medium) — maxLines: 6 not adaptive to screen height; missing minLines**
Location: lib/ui/screens/journal_session_screen.dart:724
On small phones (360dp wide) with keyboard raised, the usable body is ~280-320dp. Voice mode stacks additional widgets above the text row (SegmentedButton, phase indicator, transcript preview). A 6-line TextField consumes 120-150dp leaving 130-180dp for the message list. Fix is directionally correct (unbounded is clearly worse) but the ceiling is not adaptive. Also: minLines is absent — multi-line affordance is invisible until user types past line 1.
Advisory: Add minLines: 1. Consider maxLines: 4 instead of 6, or wrap the bottom container in ConstrainedBox limiting total height to min(240, screenHeight*0.35).

**A6 (Low) — No textInputAction: TextInputAction.send with maxLines > 1**
Location: lib/ui/screens/journal_session_screen.dart:730
With maxLines > 1, Flutter's default textInputAction is newline — Enter key adds a newline instead of submitting. onSubmitted callback exists but only fires on action key, which now inserts newline. User has no keyboard shortcut to send. Pre-existing behavior not introduced by this change, but the maxLines fix makes it more noticeable.
Advisory: Add textInputAction: TextInputAction.send.

**A7 (Low) — FAB not visually disabled during _isStarting (no color change)**
Location: lib/ui/screens/session_list_screen.dart:142-155
FAB with onPressed: null in Material 3 does not visually dim by default. Spinner icon replaces the add icon (communicates loading), but the FAB remains the same color/elevation as enabled. Users who tap again during _isStarting receive no haptic or visual response. Tooltip only visible on long-press.
Advisory: Add backgroundColor: _isStarting ? Theme.of(context).colorScheme.surfaceContainerHighest : null, or Semantics label for screen readers.

**A8 (Low) — Bottom padding uses viewPadding.bottom instead of padding.bottom (pre-existing)**
Location: lib/ui/screens/journal_session_screen.dart
viewPadding.bottom is the physical notch/gesture-bar inset and does not change when keyboard opens. The Scaffold already excludes the keyboard area via resizeToAvoidBottomInset: true. The container's padding is then double-counted, stealing ~24-34dp of vertical space. Pre-existing behavior but interacts with the maxLines fix.
Advisory: Use MediaQuery.of(context).padding.bottom instead of viewPadding.bottom in the input container.

### Strengths
- maxLines: 6 fix resolves the primary bug. TextField is inside Expanded within a Row, so the send button is always visible regardless of field height — the fix works at the layout level.
- FAB loading state has two feedback channels: spinner icon (visual) + tooltip update (assistive text).
- _isStarting guard is consistent across all three session-start entry points in session_list_screen.dart.
- ADHD clinical UX constraints intact: no gap language, no streaks, no escalating copy across all changed files.
- Voice pre-enable comment (A9) is exemplary — explains the why, names the race condition, describes what would fail without the ordering.
- context.mounted guards are present at every async boundary in _openQuickCapturePalette.

---

## Turn 4 — facilitator (synthesis)
*2026-03-04T15:05:26.585574+00:00 | confidence: 0.88*
*tags: blocking:0, advisory:8*

## Request Context
- **What was requested**: Ship bug fixes and Phase 3A advisory items: Bug 1 (keyboard overflow — TextField maxLines: null → 6), Bug 2 (STT stops after photo — capturePhotoDescription() restores paused state so orchestrator.resume() works), Advisory A1 (dispatch branch tests for _openQuickCapturePalette), Advisory A3 (FAB tooltip shows 'Opening...' during _isStarting), Advisory A9 (voice pre-enable ordering comment improved).
- **Files/scope**: lib/services/voice_session_orchestrator.dart, lib/ui/screens/journal_session_screen.dart, lib/ui/screens/session_list_screen.dart, test/services/voice_session_orchestrator_test.dart, test/ui/journal_session_screen_test.dart, test/ui/session_list_screen_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Two device-observed bugs causing user-facing failures. Three Phase 3A advisories resolved.
- **Explicit constraints**: ADHD clinical UX constraints apply. Regression tests required for all bug fixes tagged @Tags(['regression']).

## Synthesis

**Verdict: approve-with-changes** (1 blocking resolved in-review, 8 advisory)

### Blocking Finding (resolved in-review)
B1 (QA): Missing @Tags(['regression']) / tags: ['regression'] on both regression tests. Required by testing_requirements.md. Fixed: added tags: ['regression'] named parameter to testWidgets in journal_session_screen_test.dart and to test() in voice_session_orchestrator_test.dart. Quality gate 7/7 confirmed post-fix.

### Advisory Findings (8)
A1 (QA, Medium): capturePhotoDescription non-paused branch not tested — the wasInContinuousMode path and the else path have no capturePhotoDescription-specific test.
A2 (QA, Medium): pulse_check_in dispatch branch not covered — only 3 of 5 palette dispatch branches are tested. /check_in routing is distinct from /session and should be pinned.
A3 (QA, Low): Post-startContinuousMode phase assertion in Bug 2 regression test fires before a microtask yield. Incidental assertion, does not affect the regression target but may be timing-sensitive if mock setup changes.
A4 (QA, Low): Silence timeout path not tested — capturePhotoDescription returns null on timeout; paused-state restoration in that path is untested. Timeout is not injectable, making this CI-expensive.
A5 (UX, Medium): maxLines: 6 not adaptive to screen height; minLines absent. On 360dp devices with voice mode controls visible, 6 lines may consume 120-150dp leaving little room for message list. Consider maxLines: 4 or ConstrainedBox wrapper.
A6 (UX, Low): No textInputAction: TextInputAction.send — with maxLines > 1, Enter key adds newline instead of sending. Pre-existing behavior, newly more noticeable.
A7 (UX, Low): FAB not visually disabled during _isStarting (no color change). Spinner icon communicates loading, but FAB color/elevation unchanged. Accessible tooltip only shows on long-press.
A8 (UX, Low): Input container uses viewPadding.bottom instead of padding.bottom — double-counts bottom padding when keyboard is open. Pre-existing, interacts with maxLines fix to steal additional vertical space.

### Strengths
- Both bug fixes are correct and targeted. The paused-state restoration logic in capturePhotoDescription is well-explained with a detailed comment documenting the race condition.
- Regression test for Bug 2 correctly models the full caller sequence.
- Regression test for Bug 1 is appropriately minimal — checks the property directly.
- ProviderScope.containerOf pattern used correctly in dispatch branch tests.
- ADHD clinical UX constraints intact across all changed files.
- context.mounted guards present at every async boundary in _openQuickCapturePalette.

---
