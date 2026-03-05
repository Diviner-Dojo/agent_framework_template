---
discussion_id: DISC-20260305-174906-advisory-a2-a8-a9-implementation
started: 2026-03-05T17:49:26.044637+00:00
ended: 2026-03-05T17:57:59.081353+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260305-174906-advisory-a2-a8-a9-implementation

## Turn 1 — facilitator (evidence)
*2026-03-05T17:49:26.044637+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement advisory follow-up sprint A2+A8+A9 from REV-20260305-164139. A2: add ProviderContainer test covering the failedTaskIds null-out path in notificationBootRestoreProvider. A8: condition textInputAction on _isTextInputMode (newline in voice+text mode, send in text-primary mode). A9: replace 'Values normalized to 0–1 (1 = highest recorded)' with plain-language copy.
- **Files/scope**: test/providers/notification_providers_test.dart (new), lib/ui/screens/journal_session_screen.dart (textInputAction change), lib/ui/screens/check_in_history_screen.dart (copy change), test/ui/journal_session_screen_test.dart (regression test updated to match new behavior)
- **Developer-stated motivation**: Close 3 actionable advisories from the last sprint review. The regression test was blocking because it asserted TextInputAction.send unconditionally; the A8 fix intentionally changes default-mode behavior.
- **Explicit constraints**: ADHD clinical UX constraints apply to copy changes. Regression test must not be deleted — it should be updated to assert the new correct behavior.

---

## Turn 2 — qa-specialist (proposal)
*2026-03-05T17:53:06.596888+00:00 | confidence: 0.88*
*tags: qa, a2, a8, a9, test-coverage*

## QA Analysis — Advisory Sprint A2/A8/A9

**Confidence**: 0.88

### Coverage Assessment

A2 (notification test): Three tests cover all meaningful provider branches — failedTaskIds null-out, successful reschedule ID update, and empty-task early return. The real taskDao.updateNotificationId call via in-memory DB is tested, not mocked. Fake scheduler design is appropriate.

A8 (textInputAction regression test update): The updated regression test asserts TextInputAction.newline in voice+text mode (default). The text-primary mode (TextInputAction.send) path is never exercised in any widget test.

A9 (copy change): No test asserts the new or old subtitle string. Acceptable for pure copy.

### Findings

**Finding QA-1 [Medium]** — Missing widget test for text-primary mode textInputAction
Location: test/ui/journal_session_screen_test.dart (gap)
The regression test for A8 asserts newline in voice+text mode but the text-primary path (TextInputAction.send) has no widget test. The original A6 regression protected unconditional .send; A8 split this into a conditional. The send branch is now unprotected. An accidental inversion of the conditional (! _isTextInputMode) would pass the existing regression test since default mode is false.
Recommendation: Add companion test that taps 'Text' segment and asserts TextInputAction.send.

**Finding QA-2 [Low]** — Regression ledger staleness
Location: memory/bugs/regression-ledger.md
The ledger entry for the 'Send button pushed off screen' bug references the old test name and old assertion (unconditional TextInputAction.send). Needs update to match new test name and mode-conditional behavior.

**Finding QA-3 [Low]** — No copy regression test for A9
Location: test/ui/check_in_history_screen_test.dart (gap)
No test asserts the new subtitle string. Advisory only — future copy revert would not be caught.

**Finding QA-4 [Low]** — No mixed-mode provider test
Location: test/providers/notification_providers_test.dart
No test exercises both failedTaskIds and rescheduled loops in a single provider run. Single-task tests pass; a shared-state bug between the two loops would be missed.

### Strengths
- Test isolation correct: per-test DB creation, container.dispose() + database.close() in tearDown
- Fake scheduler overrides only rescheduleFromTasks — avoids over-mocking
- _SuccessSchedulerService asserts new ID (1001 not 1000) — meaningful, not trivial
- Regression test preserves @Tags(['regression']) and lineage comment (REV-20260305-164139-A8 supersedes REV-145506-A6)

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-05T17:53:30.822520+00:00 | confidence: 0.88*
*tags: ux, a8, a9, discoverability, copy-quality*

## UX Analysis — Advisory Sprint A8/A9

**Confidence**: 0.88

### A8 — textInputAction Flow

**Finding UX-1 [High]** — No affordance that Enter won't submit in voice+text mode
Location: lib/ui/screens/journal_session_screen.dart:748
In voice+text mode, textInputAction is now TextInputAction.newline which suppresses onSubmitted on Android. The IME Enter key shows a newline glyph instead of 'Send'. A user who types a thought and presses Enter expecting submission will silently get a newline with no in-field signal pointing to the send icon. The send icon is accessible via _buildActionButton's default case, but there is no discoverability bridge between the text field and that icon when the mode is voice+text.
Recommendation: Add helperText to InputDecoration shown only in voice+text mode when mic is not actively listening: 'Tap send icon to submit'. Alternatively a suffixIcon tooltip if helperText height is a concern on small-screen layouts.
Note: Submit path has no dead end — the send icon is always reachable. This is a discoverability gap, not a functional breakage.

**Finding UX-3 [Low]** — 'Listening...' hint on disabled field may read as error state
Location: lib/ui/screens/journal_session_screen.dart:744
When isListening, the hint text becomes 'Listening...' and the field is disabled (greyed out). Greyed-out + message-hint can appear as error to users unfamiliar with the voice mode pattern. Phase indicator chip above covers this adequately. Low priority.
Alternative hint: 'Listening...' → keep as is, or 'Type to interrupt...'

### A9 — Copy Quality

**Finding UX-2 [Medium]** — Y-axis labels (0.0/0.5/1.0) contradict plain-language subtitle
Location: lib/ui/screens/check_in_history_screen.dart:804-811
The subtitle now reads 'Chart scaled to your own range — top of chart is your personal highest.' The Y-axis tick labels still display 0.0, 0.5, 1.0. A user reading the subtitle then looking at the axis sees numeric labels that reference the 0–1 scale the old copy described, creating tension. The subtitle says 'personal highest' but the axis says '1.0'.
Recommendation: Replace Y-axis labels with plain descriptors: 'Low', 'Mid', 'High' to match the new subtitle framing. Out of scope for this advisory sprint but worth logging as a follow-up advisory.
Note: The axis label issue is pre-existing — A9 improved the subtitle but exposed the inconsistency. Not introduced by this change.

### Flow Assessment

A8: The mode-conditioned textInputAction is the minimal and correct fix. The interaction model is sound — text-primary mode submits on Enter, voice+text mode inserts newline. No dead end. Send button accessible in both modes. inline comment with REV ID makes lineage traceable. The existing onSubmitted wire does not cause double-submit because TextInputAction.newline suppresses onSubmitted on Android IME.

A9 copy passes all ADHD clinical UX constraints: no evaluative framing, no comparison to other users, no gap/streak references, 'your personal highest' keeps chart exploratory not normative.

### Strengths
- Mode-conditional textInputAction is minimal intervention; no restructuring of _sendMessage or _buildActionButton logic
- A9 subtitle correctly frames chart as self-referential (your range) vs absolute
- SegmentedButton stops voice orchestrator on mode switch (line 659) — mode transition is trustworthy
- TextInputAction.newline correctly suppresses double-submit risk while leaving onSubmitted wire intact

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T17:54:12.163712+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:6, synthesis*

## Request Context
- **What was requested**: Implement advisory follow-up sprint A2+A8+A9 from REV-20260305-164139. A2: ProviderContainer test for failedTaskIds null-out path. A8: condition textInputAction on _isTextInputMode. A9: plain-language chart subtitle.
- **Files/scope**: test/providers/notification_providers_test.dart (new, 3 tests), lib/ui/screens/journal_session_screen.dart (textInputAction conditional), lib/ui/screens/check_in_history_screen.dart (subtitle copy), test/ui/journal_session_screen_test.dart (regression test updated for new behavior)
- **Developer-stated motivation**: Close 3 actionable advisories from REV-20260305-164139. Regression test was blocking quality gate; updated to assert the new correct behavior.
- **Explicit constraints**: ADHD clinical UX constraints; regression test must be updated not deleted.

## Verdict: approve-with-changes

**Blocking findings: 0**
**Advisory findings: 6**

## Summary

All three advisory implementations are functionally correct. Quality gate passes 7/7 at 81.3% coverage. The changes correctly address the three original advisories. Six advisory findings emerge from specialist review, none blocking merge.

## Advisory Findings

**A-1 [Medium, QA] Missing test for text-primary mode textInputAction.send**
The A8 regression test update covers voice+text mode (newline) but leaves the text-primary mode (send) path without a widget test. If the conditional is accidentally inverted, the regression test would pass because the default is false. A companion test tapping the 'Text' segment and asserting TextInputAction.send would complete the two-mode contract.
*Recommended action: Add before next sprint.*

**A-2 [Low, QA] Regression ledger entry is stale**
memory/bugs/regression-ledger.md line 30 references old test name ('textInputAction.send') and old assertion. Needs update to reflect new test name and mode-conditional behavior.
*Recommended action: Update now (trivial edit).*

**A-3 [High, UX] No discoverability affordance in voice+text mode for Enter-to-newline change**
In voice+text mode, Enter now inserts a newline (correct per A8 intent). But there is no in-field signal telling users that Enter won't submit — users who habitually press Enter to submit will silently get a newline. The send icon is accessible but not pointed to. Recommend helperText: 'Tap send icon to submit' visible in voice+text mode when mic is inactive.
*Recommended action: Advisory for next sprint; does not block — submit path has no dead end.*

**A-4 [Medium, UX] Y-axis labels (0.0/0.5/1.0) contradict plain-language subtitle**
The A9 subtitle change ('Chart scaled to your own range') is correct, but Y-axis tick labels still display 0.0/0.5/1.0 which references the 0–1 normalization the new copy no longer describes. A user sees 'top of chart is your personal highest' but the axis shows '1.0'. This is pre-existing inconsistency exposed by the subtitle change; recommend replacing axis labels with 'Low/Mid/High' in a follow-up.
*Recommended action: Follow-up advisory — out of scope for this sprint.*

**A-5 [Low, QA] No mixed-mode provider test**
notification_providers_test.dart has no test exercising both failedTaskIds and rescheduled loops in a single provider run. Single-task tests pass; a shared-state bug between loops would be missed.
*Recommended action: Add fourth test before next sprint.*

**A-6 [Low, QA] No copy regression test for A9**
No test asserts the new subtitle string, so a future copy revert would not be caught automatically.
*Recommended action: Low-priority; copy-only change is low risk.*

## Strengths

- A2 test design is correct: real DAO via in-memory DB, fake scheduler only overrides rescheduleFromTasks, both the null-out path and the update path are verified against actual DB state.
- A8 minimal intervention: single conditional expression, inline comment with REV ID, no restructuring of _sendMessage or _buildActionButton logic. TextInputAction.newline correctly suppresses onSubmitted on Android IME — no double-submit risk.
- A9 copy passes all ADHD clinical UX constraints. 'Your personal highest' framing is self-referential and non-normative.
- Regression test update preserves @Tags(['regression']), retains the protection intent, and documents lineage (REV-20260305-164139-A8 supersedes REV-145506-A6).
- Quality gate: 7/7 pass, 81.3% coverage (2488 tests, 0 failures).

## Education Gate
Deferred per ADHD roadmap policy. No walkthrough/quiz required for this advisory sprint.

---

## Turn 5 — qa-specialist (reflection)
*2026-03-05T17:57:56.411493+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

I identified the text-primary textInputAction.send branch as missing a test (A-1) but did not pre-empt a deeper structural concern: when a regression test is *updated* rather than deleted, I should immediately ask whether the update degrades the protection intent. Here the original A6 test unconditionally asserted `.send`; the update made it mode-conditional but only tested one mode. I caught that gap in the same review, so no miss there. What I would check next time more deliberately: when a regression test lineage comment changes (supersedes REV-145506-A6), actively enumerate *all* behaviors the prior test was protecting and verify each has a corresponding test arm in the new version.

## Candidate Improvement Rule

When a regression test is updated (not just added), the reviewer must enumerate every behavior the original test asserted and confirm each assertion is preserved in the updated test or transferred to a new companion test. A superseded-lineage comment is a signal to do this enumeration explicitly, not implicitly.

## Confidence Calibration
Original: 0.88, Revised: 0.85, Delta: -0.03

---

## Turn 6 — ux-evaluator (reflection)
*2026-03-05T17:57:59.081353+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

I caught the Y-axis label contradiction (A-4) only as an advisory, but it deserves higher severity. The subtitle says "top of chart is your personal highest" yet the axis renders literal normalized values (0.0, 0.5, 1.0) — a user reading both simultaneously gets contradictory information. That is a cognitive-load failure, not merely advisory. I should have traced the full rendering path from subtitle copy through to axis label generation before assigning severity, rather than flagging the copy change in isolation. Next time: when reviewing a copy change for a data visualization, immediately locate the corresponding axis/label code and check consistency before assigning severity.

## Candidate Improvement Rule

When a UI copy change describes a data transformation (normalization, scaling, bucketing), the reviewer must verify that all rendered numeric values in the same view (axis labels, tooltips, legend values) are consistent with the new description. A copy-only review of a chart subtitle is incomplete without inspecting the axis rendering code in the same file.

## Confidence Calibration
Original: 0.82, Revised: 0.74, Delta: -0.08

---
