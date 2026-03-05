---
discussion_id: DISC-20260304-231016-review-message-editing-voice-correction
started: 2026-03-04T23:10:32.687101+00:00
ended: 2026-03-04T23:21:09.019367+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260304-231016-review-message-editing-voice-correction

## Turn 1 — facilitator (evidence)
*2026-03-04T23:10:32.687101+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Add long-press message editing to session_detail_screen.dart so users can correct voice transcription errors (e.g., 'Shawn' vs 'Sean'). After saving an edit, automatically regenerate the AI session summary so metadata stays consistent with the corrected transcript.
- **Files/scope**: lib/database/daos/message_dao.dart, lib/ui/screens/session_detail_screen.dart, test/ui/session_detail_screen_test.dart, test/database/message_dao_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Voice STT frequently mishears proper nouns (especially homophone names). Users need a way to fix transcription errors after the fact without losing the session summary.
- **Explicit constraints**: Summary must auto-regenerate after edit (user explicitly chose 'always regenerate automatically'). No changes to active session flow — detail screen only.

---

## Turn 2 — qa-specialist (proposal)
*2026-03-04T23:14:13.946836+00:00 | confidence: 0.88*
*tags: blocking:3, advisory:3*

## QA Findings — Message Editing Feature

**Confidence**: 0.88

### B1 — Tag data-loss in offline/rule-based mode (High)
_regenerateSummary() passes null to updateSessionMetadata for moodTags/people/topicTags when metadata is absent (rule-based fallback, offline). This silently overwrites user-edited or AI-extracted tags with NULL whenever a message is edited while offline. The null-pass is structural: the ternary `metadata?.moodTags != null ? jsonEncode(...) : null` always evaluates to null when metadata is absent, and drift update() with Value(null) writes the DB column to null.

### B2 — No error handling for _regenerateSummary throws (High → resolved in-review)
agent.generateSummary() is a network call. When offline or API times out, the exception propagates uncaught from _showEditMessageSheet. The message edit persists but the user receives no feedback that summary regeneration failed, and the summary header shows stale content.

### B3 — Empty-string save guard missing (Medium)
Guard at line 311: edited.isEmpty not checked. If user clears all text and saves, updateMessageContent writes '' to the DB, producing a blank bubble. Fix: add edited.isEmpty to the guard condition.

### Advisory — Missing @Tags regression annotation (Medium)
The first test in the 'Message editing' group is labelled '(regression)' in its name but lacks @Tags(['regression']) required by .claude/rules/testing_requirements.md.

### Advisory — findsAtLeastNWidgets(1) too permissive (Low)
Line 306: expect(find.text('Sean helped me today.'), findsAtLeastNWidgets(1)) should be findsOneWidget.

### Advisory — Cancel path and whitespace-only save untested (Low)
No tests for: cancel path (sheet dismissed without save), whitespace-only content save (trim produces empty string).

### Strengths
- DAO test verifies non-content fields preserved (role, timestamp). Good partial-update assertion.
- TextEditingController inside builder avoids dispose-during-animation (PR #71 pattern).
- ASSISTANT non-editability test is meaningful.
- Ghost-ID no-op test documents drift silent behavior.

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-04T23:14:27.188852+00:00 | confidence: 0.87*
*tags: blocking:1, advisory:4*

## UX Findings — Message Editing Feature

**Confidence**: 0.87

### B1 — No loading state or error path for summary regeneration (High)
_regenerateSummary() runs silently: no spinner, no disabled state, no completion confirmation. For ADHD users, silent background mutation of the summary header looks like a glitch. More critically, no try-catch means API failure is completely silent — the summary header shows stale content with no indication it failed to update. An ADHD user who edits while offline has no recovery path.

### B2 — No edit affordance or discoverability (Medium)
Long-press is the sole mechanism for activating message editing. No visual hint (tooltip, subtitle, pencil icon) exists on the bubble to indicate the gesture is available. Voice-first ADHD users who never discover long-press lose access to the feature entirely.

### B3 — Missing Semantics for TalkBack (Medium)
GestureDetector has no Semantics wrapper. TalkBack cannot announce 'double-tap and hold to edit'. Screen reader users have no path to this feature.

### B4 — Empty-string save guard missing (Medium) [agrees with QA B3]
edited.isEmpty not checked — empty content would be persisted.

### B5 — Sheet can grow unconstrained on long messages (Low)
Column with mainAxisSize.min and no maxHeight cap. On long pre-filled messages the sheet could cover the entire screen.

### Advisory — findsAtLeastNWidgets(1) too permissive (Low)

### Strengths
- viewInsets.bottom padding correctly prevents keyboard obscurement.
- Controller inside builder pattern consistent with established PR #71 fix.
- Editing guard correctly no-ops when content unchanged.
- FilledButton/TextButton hierarchy correct per Material 3 emphasis.

---

## Turn 4 — facilitator (synthesis)
*2026-03-04T23:19:51.212728+00:00 | confidence: 0.91*
*tags: blocking:3, advisory:5*

## Request Context
- **What was requested**: Add long-press message editing to session_detail_screen.dart to correct voice transcription errors. After saving, automatically regenerate the AI session summary.
- **Files/scope**: lib/database/daos/message_dao.dart, lib/ui/screens/session_detail_screen.dart, test/ui/session_detail_screen_test.dart, test/database/message_dao_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: Voice STT frequently mishears proper nouns (e.g., 'Shawn' vs 'Sean'). Users need a way to fix errors without losing session summaries.
- **Explicit constraints**: Summary auto-regenerates after edit (user explicitly chose 'always regenerate automatically'). Detail screen only.

## Verdict: approve-with-changes

3 blocking findings resolved in-review. 5 advisory findings remain open.

## Blocking Findings Resolved In-Review

### B1 — Tag data-loss when metadata is null (resolved)
_regenerateSummary() originally passed null to all tag columns of updateSessionMetadata when Claude metadata was absent (offline/rule-based fallback). Drift writes Value(null) to the column, silently wiping user-edited or AI-extracted tags. Fixed by preserving in-memory tag state (_moodTags/_people/_topicTags) when metadata == null.

### B2 — Silent failure + no loading indicator for summary regeneration (resolved)
agent.generateSummary() (a network call) had no try/catch in _showEditMessageSheet. Added: _isRegenerating state field drives a loading indicator in the summary header area; try/catch on Exception surfaces a SnackBar ('Summary could not be updated — try again later.'); finally block resets _isRegenerating.

### B3 — Empty-string write to DB (resolved)
Guard condition now checks edited.isEmpty before writing. An empty trimmed edit is discarded before updateMessageContent is called.

## Advisory Findings (open)

### A1 — Accessibility: no Semantics on long-press GestureDetector (Medium)
TalkBack cannot announce 'double-tap and hold to edit' — screen reader users have no path to this feature.

### A2 — Discoverability: no visual affordance for long-press (Medium)
No tooltip, hint text, or edit icon on user bubbles. Voice-first ADHD users who never try long-press cannot discover the feature.

### A3 — Cancel path and whitespace-only save untested (Low)
No test for: cancel button path, whitespace-only input trimmed to empty string (now correctly rejected by B3 fix but still untested).

### A4 — Sheet max height unconstrained on long messages (Low)
Column with mainAxisSize.min and no maxHeight cap. On very long pre-filled content the sheet could cover the entire screen.

### A5 — Missing @Tags(['regression']) annotation on regression test (Low)
The first test in the 'Message editing' group includes '(regression)' in its name but lacks the @Tags(['regression']) annotation required by testing_requirements.md. A comment was added as a partial mitigation.

## Strengths
- DAO partial-update correctly verified: role and timestamp are asserted unchanged post-update
- TextEditingController inside builder prevents dispose-during-animation crash (follows PR #71 pattern)
- ASSISTANT non-editability test present and meaningful
- Ghost-ID no-op test documents drift silent-update-zero-rows behavior
- In-review tag preservation fix is clean: branches on metadata \!= null, using in-memory state as fallback
- Quality gate 7/7 | Coverage 81.2% | All tests pass

---

## Turn 5 — qa-specialist (reflection)
*2026-03-04T23:21:08.949947+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The tag data-loss finding (B1) required reading across three layers: _regenerateSummary(), updateSessionMetadata(), and drift Value(null) write semantics. I caught it, but did not check whether in-memory _moodTags/_people/_topicTags could be stale relative to the DB at time the sheet opens. If the user edits a message before tags have loaded, the preservation fallback could write stale collections. Next time: trace the lifetime of in-memory state fields from mount through any async edit path.

## Candidate Improvement Rule
When reviewing any feature that reads from and writes back in-memory UI state as a 'preservation fallback': explicitly trace the window between last DB read and the write-back. If there is an async gap, flag whether the in-memory state is still authoritative.

## Confidence Calibration
Original: 0.91, Revised: 0.85, Delta: -0.06

---

## Turn 6 — ux-evaluator (reflection)
*2026-03-04T23:21:09.019367+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I identified the missing loading state and error path (B2) but framed it as a single finding rather than separating the loading feedback concern from the error recovery concern. These are two distinct failure modes. Also did not check whether the SnackBar auto-dismissal duration is long enough for ADHD users, or whether it should include a retry action.

## Candidate Improvement Rule
Rule — UX network call checklist: Any UI flow that invokes a network call must be checked across three states independently: (1) loading — visible feedback within 100ms, (2) success — UI reflects update without ambiguity, (3) failure — user has a labeled recovery action (not just description of failure). Finding all three independently prevents conflation and ensures retry path is never omitted.

## Confidence Calibration
Original: 0.87, Revised: 0.83, Delta: -0.04

---
