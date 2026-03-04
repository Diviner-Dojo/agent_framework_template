---
discussion_id: DISC-20260304-141351-review-phase-3a-quick-capture-mode
started: 2026-03-04T14:14:10.950401+00:00
ended: 2026-03-04T14:24:53.943433+00:00
agents: [architecture-consultant, facilitator, qa-specialist, ux-evaluator]
total_turns: 5
---

# Discussion: DISC-20260304-141351-review-phase-3a-quick-capture-mode

## Turn 1 — facilitator (evidence)
*2026-03-04T14:14:10.950401+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement Phase 3A Quick Capture Mode from SPEC-20260302-adhd-informed-feature-roadmap — replace the FAB long-press mode picker with a one-tap palette of 5 large capture mode buttons (Write, Voice, Photo, Mood Tap, Check-In); persist the last-used mode so it is pre-highlighted on repeat visits.
- **Files/scope**: lib/providers/last_capture_mode_provider.dart (new), lib/ui/widgets/quick_capture_palette.dart (new), lib/ui/screens/session_list_screen.dart (modified: FAB wired to palette, _showModePicker removed), test/providers/last_capture_mode_provider_test.dart (new, 6 tests), test/ui/quick_capture_palette_test.dart (new, 11 tests)
- **Developer-stated motivation**: ADHD initiation difficulty (the #1 clinical barrier). Every capture requires starting a full AI conversation session — too much friction. One-tap palette with last-used mode remembered eliminates mode-selection decision on repeat visits. The '10-Second Promise' from SPEC-20260302 Phase 3A.
- **Explicit constraints**: ADHD UX — no pressure framing, no gap language, no streaks; 48dp minimum tap targets; 'A few words is enough.' copy; last-used mode highlighted without imposing it; voice mode pre-enabled before session navigation; photo mode stores preference but does not yet auto-open camera.

---

## Turn 2 — qa-specialist (proposal)
*2026-03-04T14:19:50.932620+00:00 | confidence: 0.87*
*tags: qa*

## QA Specialist Review — Phase 3A Quick Capture Mode

**Confidence:** 0.87

### Strengths
- Excellent test isolation: each widget test builds its own complete MaterialApp + Scaffold boilerplate
- Correct context handling: VoidCallback onTap pattern from parent context is correctly verified by inspect of the widget tree
- Sentinel value ('sentinel') in dismiss-returns-null test properly distinguishes null result from un-set result
- ADHD copy verified by text finders in renders-ADHD-header-copy test
- Provider setUp/tearDown pattern is clean; addTearDown(container.dispose) present on all containers

### Findings

**Medium — Missing dispatch branch tests (A1)**
`_openQuickCapturePalette` has 5 routing branches: null/abandoned, __quick_mood_tap__, voice (pre-enable), pulse_check_in, and text. Zero widget tests cover these routing branches. If a routing regression is introduced (e.g., voice pre-enable accidentally fires for text mode), no test will catch it. These branches touch voiceModeEnabledProvider, showQuickMoodTapSheet, and _startNewSession — all with observable side effects.

**Medium — setMode before context.mounted check (A2)**
In _openQuickCapturePalette: `await ref.read(lastCaptureModeProvider.notifier).setMode(selected)` executes before the second `context.mounted` check at line 3. If the widget unmounts between sheet dismissal and that await completing, the mode is persisted even though the user never completed navigation. The practical impact is low (mode persistence is a hint, not a gate), but it violates the intent that only a successfully completed navigation updates the preference.

**Low — Highlight test via indirect semantics assertion (A3)**
The 'tile matching lastMode has semantics label' test asserts via Semantics.properties.label rather than directly on the Material color. This is acceptable (semantics are the accessibility contract), but a direct color assertion on the highlighted Material widget would catch color-not-set regressions that the semantics test would miss (e.g., if isHighlighted is wired to semantics but not to bgColor).

**Low — Provider accepts arbitrary strings (A4)**
LastCaptureModeNotifier.setMode() accepts any String? value with no validation. An invalid mode key would be persisted and then passed to showQuickCapturePalette where it would simply not match any tile (unknown-key-no-highlight test confirms this). No crash occurs, but stale invalid state could confuse future mode routing. Advisory: consider validating against the canonical mode key set or documenting the open-set contract.

**Low — Shared SharedPreferences in round-trip test (A5)**
The 'all valid mode keys round-trip' test creates a new ProviderContainer per iteration but reuses the same `prefs` object across all iterations. Because setMode() only writes the current mode (not appends), this doesn't cause test failures, but it's a subtle coupling that could bite if the test is refactored to check for absence of prior-mode values.

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-04T14:20:17.664460+00:00 | confidence: 0.88*
*tags: ux*

## UX Evaluator Review — Phase 3A Quick Capture Mode

**Confidence:** 0.88

### Strengths
- ADHD framing is well-executed: 'What's on your mind? A few words is enough.' removes performance pressure
- Last-used mode highlight with primaryContainer background is correctly implemented
- 48dp minimum tap targets satisfied by vertical: 20 + icon(32) + gap(8) + text padding
- Five-tile grid layout with full-width Check-In tile gives visual hierarchy (structured vs freeform)
- VoidCallback onTap from parent context correctly handles Navigator routing

### Findings

**HIGH — Photo mode dispatches identically to text session (B1 — BLOCKING)**
The palette presents 'Photo' with camera_alt_outlined icon implying immediate camera access. The dispatch in session_list_screen.dart routes 'photo' as a plain text session (no journalingMode override, no camera trigger). The user sees a camera affordance, taps it, and enters a text journaling session with no camera — this is actively misleading. Per review_gates.md: 'data displayed in the UI that is provably incorrect at implementation time must be classified as blocking.' Camera-open dispatch is not yet implemented (Bug 2 in BUILD_STATUS.md: STT stops after photo). Recommended fix: remove Photo tile from palette until camera dispatch is implemented, or replace with 'coming soon' visual treatment with tap disabled.

**HIGH — FAB tooltip not updated during _isStarting state (A3)**
The FloatingActionButton tooltip ('New Entry') is static. When _isStarting is true (session creation in progress), the FAB is disabled (onPressed: null) but the tooltip still reads 'New Entry', suggesting a new action is available. Should read 'Opening...' or similar during _isStarting.

**Medium — setMode persisted before navigation (A2)**
setMode is awaited before _startNewSession. If session start fails (e.g., Supabase offline), the mode is already persisted as the 'last used' mode for a session that never opened. Minor: the preference is a hint, not a gate, but could mislead the user on the next open.

**Medium — Check-In tile lacks descriptor copy (A4)**
'Check-In' tile gives no hint about what the check-in entails. A user unfamiliar with Pulse Check-In will not know whether this is a 1-tap action or a multi-step questionnaire. Consider adding a sub-label '6 quick questions' (or dynamically computed from activeDefaultTemplateProvider item count) below the tile label.

**Medium — Missing barrierLabel on showModalBottomSheet (A5)**
showModalBottomSheet does not set barrierLabel, so TalkBack announces the barrier as 'Dismiss' (default). The modal has a sheet handle drag affordance but no screen-reader announcement that this is the capture mode selector. Set barrierLabel: 'Close capture mode selector'.

**Medium — DraggableScrollableSheet not used (A6)**
The sheet uses isScrollControlled: true + SingleChildScrollView. At 200% text scale the tile labels grow significantly and could cause the sheet to fill the screen with no visible draggable handle affordance. Consider DraggableScrollableSheet with minChildSize/maxChildSize to give the user a drag handle and prevent full-screen coverage.

**Low — Semantics excludeSemantics missing (A7)**
_ModeButton wraps its content in Semantics(button: true, label: '...') but does not set excludeSemantics: true. TalkBack will traverse child semantics (icon + text label) in addition to the button-level label, resulting in double-announcement of the tile label.

**Low — Check-In tile creates second entry point for pulse_check_in (A8)**
The Quick Check-In CTA banner (Phase 2B) is already present on SessionListScreen. Adding a second Check-In entry in the palette creates two UI paths to the same flow. This is acceptable but developers should ensure both paths call the same handler.

---

## Turn 4 — architecture-consultant (proposal)
*2026-03-04T14:20:38.703828+00:00 | confidence: 0.82*
*tags: architecture*

## Architecture Consultant Review — Phase 3A Quick Capture Mode

**Confidence:** 0.82

### Strengths
- Clean separation: palette widget is stateless and has no Riverpod dependency — caller manages state; this is the right boundary
- VoidCallback onTap delegation pattern correctly avoids Navigator.of(context) context capture issues inside bottom sheet builder
- SharedPreferences-backed StateNotifier follows existing onboarding_providers pattern
- Dart 3 named record typedef for _ModeEntry is ergonomic and avoids a separate class

### Findings

**HIGH — Photo mode dispatches as text session (B1 — BLOCKING)**
quick_capture_palette.dart presents Photo as a full mode tile. session_list_screen.dart dispatch in _openQuickCapturePalette has no special handling for 'photo' — it falls through to _startNewSession(context, journalingMode: null), identical to text. The palette UI contract is violated: Photo promises camera-open, but delivers a plain text session. Per review_gates.md the 'provably incorrect at implementation time' rule applies. Options:
  A) Remove Photo tile from _kModes until photo dispatch is implemented (simplest, no misleading UX)
  B) Add a 'coming soon' disabled tile as a placeholder
  C) Implement camera dispatch now (requires Bug 2 fix from BUILD_STATUS.md)
Option A is recommended. Option C is too large for this review cycle.

**Medium — StateNotifier vs Notifier<T> pattern (A8)**
LastCaptureModeNotifier extends StateNotifier<String?> which is deprecated in Riverpod 2.x and removed in 3.0. The existing codebase has at least one Notifier<T> usage (ReminderService pattern). New providers should use Notifier<T> with NotifierProvider to avoid a migration cliff. Advisory: migrate or document the intent to migrate.

**Medium — Voice pre-enable ordering dependency undocumented (A9)**
In _openQuickCapturePalette, voiceModeEnabledProvider.notifier.setEnabled(true) is called before _startNewSession. The comment 'enable voice mode before creating session so session_providers can read it synchronously' is missing. Without this comment, a future refactor could reorder the calls, breaking the synchronous read contract in session_providers.dart. Add the explanatory comment.

**Medium — Removed journaling modes have no recorded decision (A10)**
The legacy _showModePicker referenced JournalingMode.gratitude, JournalingMode.dreamAnalysis, and JournalingMode.moodCheckIn. These have been removed from the FAB-accessible flow without an ADR or decision record. If these modes still exist as enum values (which they likely do from Phase 1), the omission is intentional but undocumented. Either add a decision record explaining why these modes were consolidated, or confirm the modes are deprecated and update the spec.

**Low — Mode keys are bare string literals (A11)**
The mode key strings ('text', 'voice', 'photo', '__quick_mood_tap__', 'pulse_check_in') appear in _kModes, _openQuickCapturePalette dispatch switch, and tests. A typo in any location would cause a silent routing miss. Extract to const String kCaptureModeText = 'text'; etc. in a shared constants file, or at minimum within quick_capture_palette.dart. The double-underscore convention for '__quick_mood_tap__' is particularly fragile.

---

## Turn 5 — facilitator (synthesis)
*2026-03-04T14:24:53.943433+00:00 | confidence: 0.9*
*tags: blocking:1, advisory:11*

## Request Context
- **What was requested**: Multi-agent review of Phase 3A Quick Capture Mode files: last_capture_mode_provider.dart, quick_capture_palette.dart, session_list_screen.dart, and their tests
- **Files/scope**: lib/providers/last_capture_mode_provider.dart, lib/ui/widgets/quick_capture_palette.dart, lib/ui/screens/session_list_screen.dart, test/providers/last_capture_mode_provider_test.dart, test/ui/quick_capture_palette_test.dart
- **Developer-stated motivation**: Replace FAB long-press mode picker with one-tap Quick Capture Palette presenting 5 large tiles, highlight last-used mode for ADHD repeat-capture UX, wire voice pre-enable
- **Explicit constraints**: ADHD clinical UX constraints (no gap-shaming, no streaks, no pressure framing); 48dp minimum tap targets; context.mounted guards after every await

## Synthesis

**Verdict: approve-with-changes** — 1 blocking finding identified and resolved in-review. 11 advisory findings remain open.

### Blocking Finding (B1) — RESOLVED IN REVIEW

All three specialists independently flagged that 'Photo' tile dispatched identically to a plain text session. Per review_gates.md: 'data displayed in the UI that is provably incorrect at implementation time must be classified as blocking.' The palette icon (camera_alt_outlined) and label ('Photo') create an explicit camera affordance that the dispatch code does not fulfill.

**Resolution applied in review**: Removed Photo tile from _kModes in quick_capture_palette.dart. Grid layout updated from 2+2+1 (5 tiles) to 2+2 (4 tiles: Write, Voice in row 1; Mood Tap, Check-In in row 2). Doc comment in both files updated. Photo tile test removed; 'renders all five mode labels' test renamed and updated to assert Photo is absent. Quality gate 7/7 passes, 16/16 tests pass.

### Architecture

Clean separation between palette widget (stateless, no Riverpod) and caller (manages persistence and dispatch). VoidCallback onTap delegation correctly prevents Navigator.of(context) capturing wrong context from bottom sheet builder. SharedPreferences-backed StateNotifier follows existing onboarding_providers pattern.

Advisory A8: StateNotifier is deprecated in Riverpod 2.x. New providers should use Notifier<T>. Defer migration to a dedicated advisory sprint to avoid scope creep.

Advisory A10: Removed journaling modes (gratitude, dreamAnalysis, moodCheckIn) from FAB flow with no recorded decision. These enum values still exist from Phase 1. Need either an ADR explaining consolidation or confirmation they are intentionally deferred.

Advisory A11: Mode key strings are bare literals. Extract to constants to prevent silent routing misses from typos (especially '__quick_mood_tap__').

Advisory A9: Voice pre-enable ordering dependency (setEnabled before _startNewSession) lacks an explanatory comment. Add comment for future refactor safety.

### UX

ADHD framing is correct throughout. 'What's on your mind? A few words is enough.' properly removes performance pressure. Last-used mode highlight with primaryContainer is implemented correctly. 48dp tap targets satisfied.

Advisory A3: FAB tooltip static ('New journal entry') during _isStarting state. Should read 'Opening...' when disabled.
Advisory A4: Check-In tile lacks descriptor copy. '6 quick questions' would clarify what the flow entails.
Advisory A5: showModalBottomSheet missing barrierLabel for screen-reader announcement.
Advisory A6: DraggableScrollableSheet not used — risk at 200% text scale.
Advisory A7: Semantics(button: true) wraps children without excludeSemantics: true — TalkBack will double-announce tile labels.

### QA

Test isolation is excellent. VoidCallback onTap fix from build checkpoint correctly prevents Navigator context capture. Sentinel value in dismiss test properly distinguishes null from unset.

Advisory A1: _openQuickCapturePalette dispatch branches not tested (voice pre-enable, mood tap routing, pulse_check_in routing). All 3 routing branches have observable side effects.
Advisory A2: setMode called before second context.mounted check — mode persisted for abandoned navigation. Low practical impact but violates the persistence-on-success intent.

---
