---
discussion_id: DISC-20260305-222735-advisory-closeout-sprint
started: 2026-03-05T22:27:52.594141+00:00
ended: 2026-03-05T22:34:52.528148+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260305-222735-advisory-closeout-sprint

## Turn 1 — facilitator (evidence)
*2026-03-05T22:27:52.594141+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Advisory close-out sprint implementing 8 open advisories from REV-20260305-193138 and REV-20260305-203427
- **Files/scope**: lib/ui/screens/check_in_history_screen.dart, lib/ui/screens/settings_screen.dart, test/ui/check_in_history_screen_test.dart, test/ui/journal_session_screen_test.dart, test/ui/settings_data_management_test.dart
- **Developer-stated motivation**: Clear all open advisories before final review and ship; ensure no regressions in recently delivered ADHD roadmap phases
- **Explicit constraints**: ADHD clinical UX constraints (no shaming language); all 8 advisories must be closed; quality gate must pass 7/7

---

## Turn 2 — qa-specialist (proposal)
*2026-03-05T22:30:52.129345+00:00 | confidence: 0.91*
*tags: qa, advisory:4*

## QA Review — Advisory Closeout Sprint

**Confidence: 0.91**

### Coverage Assessment
- Suite: 82.3% coverage, 2499 tests — above 80% threshold.
- check_in_history_screen.dart: reservedSize changes covered by crash-guard regression tests. fl_chart axis limitation accurately documented.
- settings_screen.dart: FileSystemException branch not directly reachable in test environment — acceptable; test acknowledges this.
- journal_session_screen_test.dart: isWaiting=true and isSpeaking=true branches now tested. isListening=true remains untested.
- settings_data_management_test.dart: timestamp exact assertion + isEmpty assertions additive and correct.

### Findings

**A-1 [Low, missing-test]** — helperText isListening=true branch untested.
The helperText condition (line 611-756 journal_session_screen.dart) has four guards: !_isTextInputMode, !isListening, !isWaiting, !isSpeaking. This sprint added isWaiting and isSpeaking tests. Existing tests cover _isTextInputMode=true. The isListening=true branch has no dedicated regression test.
Recommendation: Add test with VoiceLoopPhase.listening using same overrideWithValue pattern as isSpeaking test.

**A-2 [Low, weak-assertion]** — TabBar assertion in crash-guard test.
find.byType(TabBar) lives above the chart in the Scaffold wrapper; it would pass even if the chart widget tree were removed. The takeException() check is the real guard. Documented limitation in the comment. No action required.

**A-3 [Low, weak-assertion]** — isWaiting test uses protected StateNotifier.state setter.
Uses // ignore: invalid_use_of_protected_member to set state directly. If SessionNotifier is refactored to Riverpod 2 Notifier, this test will fail to compile. The isSpeaking test correctly uses overrideWithValue.
Recommendation: Add comment explaining why no other path exists (sendMessage() requires live Claude call), or migrate to overrideWith pattern.

**A-4 [Low, flaky-risk]** — Export retry loop 15x500ms = 7.5s max.
On slow CI runners, 7.5s may be tight. No explicit failure message when file not found before loop ends. Existing reason string provides adequate diagnostic. Low-priority.

### Strengths
- All 6 regression tests use tags: ['regression'] with review reference comments
- Fake service implementations (_NoopAudioFocusService etc.) correctly implement interfaces and dispose StreamControllers
- SnackBar text assertion updated in all locations
- Export retry loop guards partial writes with FormatException catch
- isWaiting and isSpeaking independently isolated (prevents conjunction false-pass)

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-05T22:31:04.304414+00:00 | confidence: 0.88*
*tags: ux, advisory:4*

## UX Review — Advisory Closeout Sprint

**Confidence: 0.88**

### Friction Points

**UX-A1 [Low, missing-feedback]** — FileSystemException message mentions 'storage permissions' incorrectly.
On Android API 29+, apps write to Downloads without WRITE_EXTERNAL_STORAGE. The message 'Check storage permissions and available space.' points users to the wrong settings panel. Out-of-space or path-not-found are the most common FileSystemException causes.
Recommendation: Reorder to 'Export failed: could not write to Downloads folder. Check that you have enough storage space available.' Drop misleading permissions reference or make it secondary.

**UX-A2 [Low, accessibility]** — Export button disabled state not live-region announced.
During export, onPressed=null disables the button. TalkBack users tap, hear silence, and have no auditory confirmation export started. Button label changes from 'Export My Data' to 'Exporting...' + spinner but accessibility tree does not emit live-region update.
Recommendation: Add Semantics wrapper with label: _isExporting ? 'Exporting data, please wait' : 'Export My Data'.

**UX-A3 [Low, accessibility]** — Date labels clip at 200% text scale despite reservedSize: 36.
reservedSize: 36 was sized for default scale. At 200% system text scale, labelSmall (~11sp) renders at ~22sp and clips inside the 36dp space. The bump improves default case but does not fully resolve large-text accessibility.
Recommendation: Wrap date Text in MediaQuery(data: ..copyWith(textScaler: TextScaler.noScaling)) in both _buildDailyScoreChart and _buildRollingChart.

**UX-A4 [Low, cognitive-load]** — Correlation tile 'move together/opposite' phrasing borderline.
'weak, move together — 6 days' requires inference of correlation terminology. ADHD clinical constraint is met (no causal language) but phrase is at the edge of plain language. Not blocking.
Recommendation: Future copy pass. No change required to ship.

### Flow Assessment
Export flow is complete: loading → success SnackBar → FileSystemException SnackBar → generic SnackBar. All paths produce feedback. _isExporting guard prevents double-submission. helperText suppression correctly shows hint only when text field is the active submit path.

### Strengths
- ADHD clinical UX compliance solid throughout
- Error message redesign removes raw exception object from user-visible output
- Three-tier catch structure maps clearly to three user situations
- _isExporting gives three simultaneous in-progress signals (spinner + label + disabled)
- Regression test guards chart subtitle plain-language copy against revert

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T22:31:23.295654+00:00 | confidence: 0.92*
*tags: blocking:0, advisory:8*

## Request Context
- **What was requested**: Advisory close-out sprint implementing 8 open advisories from REV-20260305-193138 and REV-20260305-203427
- **Files/scope**: lib/ui/screens/check_in_history_screen.dart, lib/ui/screens/settings_screen.dart, test/ui/check_in_history_screen_test.dart, test/ui/journal_session_screen_test.dart, test/ui/settings_data_management_test.dart
- **Developer-stated motivation**: Clear all open advisories before final review and ship; ensure no regressions in recently delivered ADHD roadmap phases
- **Explicit constraints**: ADHD clinical UX constraints; quality gate 7/7; all 8 advisories must be closed

## Verdict: APPROVE

All 8 target advisories implemented correctly. 0 blocking findings. 8 advisory findings (4 QA, 4 UX) — all Low severity.

## Summary

**Production changes (2 files)**:
- check_in_history_screen.dart: reservedSize 28→36 on both chart bottom axes — correct, matches leftTitles: 36
- settings_screen.dart: success SnackBar shortened; error handling split into FileSystemException (plain-language, 8s) and generic Exception (clean, 8s); raw exception object removed from user-visible output

**Test changes (3 files)**:
- check_in_history_screen_test.dart: crash-guard comment extended; TabBar assertion replaces fragile textContaining('/ 100')
- journal_session_screen_test.dart: isWaiting and isSpeaking helperText regression tests added; 3 correct fake service implementations
- settings_data_management_test.dart: exact timestamp assertion; isEmpty assertions for check_ins/photos; SnackBar text assertion updated

**Open advisory findings (8)**:
1. [QA] isListening=true helperText branch untested — add one more test with VoiceLoopPhase.listening
2. [QA] TabBar assertion doesn't verify chart tree — documented limitation, acceptable
3. [QA] isWaiting test uses protected .state setter — add explanatory comment or migrate to overrideWith
4. [QA] Export retry loop 7.5s max — increase to 20 iterations if CI flakiness seen
5. [UX] FileSystemException message mentions 'storage permissions' misleadingly — rephrase to space check
6. [UX] Export button not a live-region during operation — add Semantics wrapper
7. [UX] Date labels clip at 200% text scale — add TextScaler.noScaling cap in both chart builders
8. [UX] Correlation 'move together/opposite' phrasing borderline — future copy pass

Quality gate: 6/6 (review check skipped per convention), coverage 82.3%, 2499 tests.

---

## Turn 5 — qa-specialist (reflection)
*2026-03-05T22:34:47.941395+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I did not systematically walk the entire helperText condition chain at the start of the review. I identified the isWaiting and isSpeaking branches as new additions and confirmed they were tested, but I arrived at the isListening gap only by noticing it was the one remaining untested branch — not by beginning with a complete branch inventory. A structured branch-coverage sweep (enumerate all predicates, mark each as covered or not, then report gaps) would have surfaced this earlier and with higher confidence.

## Candidate Improvement Rule
**Conditional-chain completeness check**: For any widget test touching a multi-arm conditional expression, enumerate every predicate and confirm at least one test exercises each arm before assessing coverage. Flag any untested arm as a finding, not an afterthought.

## Confidence Calibration
Original: 0.91, Revised: 0.84, Delta: -0.07

---

## Turn 6 — ux-evaluator (reflection)
*2026-03-05T22:34:52.528148+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The bottom-axis date labels use reservedSize: 36 but render via theme.textTheme.labelSmall with no textScaler cap. At 200% text scale it will still clip. I caught this as a finding but did not trace it to the precise widget-level root cause. I also did not check whether the export OutlinedButton.icon carries a semanticLabel, which compounds the TalkBack gap I flagged.

## Candidate Improvement Rule
**Text-scale clip audit rule**: When reviewing any widget that uses a fixed reservedSize or SizedBox alongside a theme.textTheme.* style, verify that either (a) a MediaQuery.textScalerOf guard caps the rendered size, or (b) a FittedBox/AutoSizeText is applied. Flag as MEDIUM accessibility when neither is present.

## Confidence Calibration
Original: 0.88, Revised: 0.80, Delta: -0.08

---
