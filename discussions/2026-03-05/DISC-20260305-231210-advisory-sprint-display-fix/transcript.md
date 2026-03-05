---
discussion_id: DISC-20260305-231210-advisory-sprint-display-fix
started: 2026-03-05T23:12:26.599134+00:00
ended: 2026-03-05T23:20:22.810281+00:00
agents: [facilitator, qa-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260305-231210-advisory-sprint-display-fix

## Turn 1 — facilitator (evidence)
*2026-03-05T23:12:26.599134+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement remaining advisory fixes before ship: UX-A1 (FileSystemException SnackBar copy), UX-A3 (chart date label text scaling), QA-A1 (isListening helperText regression test), QA-A3 (comment on isWaiting test pattern). Also implement a display bug fix: long journal entry USER messages in session_detail_screen and journal_session_screen were rendering full-length with no truncation, consuming most of the visible screen when continuing a prior entry.
- **Files/scope**: lib/ui/widgets/chat_bubble.dart (new _CollapsibleMessageText StatefulWidget), lib/ui/screens/settings_screen.dart (copy fix), lib/ui/screens/check_in_history_screen.dart (MediaQuery.noScaling on date labels), test/ui/journal_session_screen_test.dart (new isListening test + QA-A3 comment)
- **Developer-stated motivation**: User observed long journal entries dominating the screen when reviewing/continuing a session (screenshot provided). UX advisory items from REV-20260305-223132. Goal is clean state before ship.
- **Explicit constraints**: ADHD clinical UX constraints must be respected; quality gate must pass 7/7; all advisory sources must be traced in comments.

---

## Turn 2 — ux-evaluator (proposal)
*2026-03-05T23:15:33.749408+00:00 | confidence: 0.88*
*tags: ui, accessibility, ux*

## Findings

**UX-1 [High]** — 'Show more' toggle has no Semantics wrapper. TalkBack announces raw label with no role, no hint, no association to truncated content. WCAG SC 1.3.1 + 4.1.2 violated. Remediation: wrap GestureDetector in Semantics(button: true, label: 'Show more of this message', hint: 'Expands full message').

**UX-2 [High]** — GestureDetector tap target is ~15-18dp (labelSmall text + 4dp top padding). Well below 48dp Material/WCAG 2.5.5 minimum. Motor accessibility barrier. Remediation: replace GestureDetector with InkWell + symmetric vertical padding 14dp each side.

**UX-3 [Medium]** — 300-char threshold may trigger for messages that already render within 5 lines, creating a 'Show more' toggle that reveals no new content (false affordance). Raise threshold to ~500 chars (~8-9 lines at 15sp/75%-width bubble).

**UX-4 [Medium]** — Scroll recycling in ListView collapses _isExpanded state silently. User expands a long message, scrolls away, returns to find it collapsed again. ADHD continuity break. Partially mitigated by ValueKey fix from QA; full fix requires expansion state map in parent screen.

**UX-5 [Medium]** — FileSystemException SnackBar now has correct copy ('Check available storage space') but no recovery action. User correctly learns the cause but has no next step. Consider SnackBarAction opening storage settings; minimum fix: extend duration to 12s.

**UX-6 [Low]** — Left axis (Low/Mid/High) labels not wrapped in MediaQuery.noScaling. Partial fix — right fix covers only bottom axis date labels. At 200% scale, 'High' at 22sp clips in 36dp reservation. Apply same noScaling pattern to leftTitles in both charts.

---

## Turn 3 — qa-specialist (proposal)
*2026-03-05T23:15:47.315460+00:00 | confidence: 0.88*
*tags: state-management, testing, coverage*

## Findings

**QA-1 [High]** — _CollapsibleMessageText StatefulWidget has no key. Instantiated inside ChatBubble in ListView.builder in journal_session_screen.dart:477 and session_detail_screen.dart:659. No caller passes key: to ChatBubble. When list rebuilds, Flutter position-based reconciliation may migrate _isExpanded=true state to whichever message occupies the original index. In active session screen, new messages arriving at bottom could cause stale expansion state at other positions. Fix: add ValueKey(msg.messageId) to ChatBubble calls in both screens.

**QA-2 [Medium]** — No didUpdateWidget override in _CollapsibleMessageTextState. session_detail_screen allows long-press editing of USER messages. After a content edit, the widget rebuilds with new content but retains _isExpanded from before the edit. If previously expanded + content shortened below threshold, 'Show more' disappears correctly (isLong=false). If previously expanded + content still long, stays expanded with stale context. Fix: override didUpdateWidget to reset _isExpanded when widget.content changes.

**QA-3 [Medium]** — No widget tests for _CollapsibleMessageText. New StatefulWidget with interactive behavior (collapsed/expanded state, threshold boundary, toggle label) has zero test coverage. Recommend 5 tests in chat_bubble_test.dart: short message no-toggle, long message shows toggle, tap expands, tap again collapses, assistant message never collapses.

**QA-4 [Low]** — isListening test (QA-A1) teardown ordering: addTearDown(container.dispose) registered after pumpAndSettle rather than immediately. Consistent with isSpeaking twin; no defect, cosmetic inconsistency only.

**QA-5 [Low]** — FileSystemException error path has no test. Copy regression could go undetected. Defer acceptable given I/O-dependent path; suggest regression ledger note if deferred.

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T23:16:07.242780+00:00 | confidence: 0.88*
*tags: blocking:3, advisory:8*

## Request Context
- **What was requested**: Advisory sprint fixes (UX-A1, UX-A3, QA-A1, QA-A3) + display bug fix for long USER messages in session_detail_screen (collapsible ChatBubble)
- **Files/scope**: chat_bubble.dart, settings_screen.dart, check_in_history_screen.dart, journal_session_screen_test.dart
- **Developer-stated motivation**: Long journal entries dominated the screen when continuing/reviewing a session (screenshot provided). Clear advisory backlog before ship.
- **Explicit constraints**: ADHD clinical UX; 7/7 quality gate; advisory sources traced in comments.

## Synthesis

Three blocking findings must be resolved before merge:

**BLOCKING-1 (UX-1)**: _CollapsibleMessageText 'Show more/less' toggle has no Semantics wrapper. TalkBack announces raw text label with no button role, no state hint, and no association to the truncated content it controls. WCAG SC 4.1.2 violation. Fix: Semantics(button: true, label: ..., hint: ...).

**BLOCKING-2 (UX-2)**: GestureDetector tap target is ~15dp (labelSmall + 4dp padding). Below 48dp Material/WCAG 2.5.5 minimum. Direct motor accessibility barrier. Fix: replace GestureDetector with InkWell + vertical padding 14dp each side.

**BLOCKING-3 (QA-1)**: No key on ChatBubble in ListView.builder (both screens). _CollapsibleMessageText _isExpanded state can migrate to the wrong message when the list rebuilds. Fix: ValueKey(msg.messageId) at both call sites.

Eight advisory findings carried forward:
- QA-2 (Medium): Add didUpdateWidget to reset _isExpanded on content change
- QA-3 (Medium): Add widget tests for _CollapsibleMessageText (5 tests)
- UX-3 (Medium): Raise collapse threshold from 300 to 500 chars
- UX-4 (Medium): Scroll recycling collapses expanded state (partially mitigated by key fix)
- UX-5 (Medium): SnackBar no recovery action for storage full
- UX-6 (Low): Left axis (Low/Mid/High) labels also need MediaQuery.noScaling
- QA-5 (Low): FileSystemException error path has no test
- QA-4 (Low): teardown ordering cosmetic (no action)

Non-_CollapsibleMessageText changes all approved: settings copy fix correct, MediaQuery.noScaling on date labels correct (partial — bottom axis only), isListening test structurally correct and matches isSpeaking pattern, QA-A3 comment thorough.

---

## Turn 5 — ux-evaluator (reflection)
*2026-03-05T23:20:22.745102+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The character-count threshold check is a proxy for line count, not actual rendered line count. Threshold validity depends on font size, bubble width, and device density — none of which I verified before raising UX-3. I should have anchored threshold advisories to layout math: 75% max-width, 15sp/1.4 line-height at minimum phone width. Next time: verify thresholds against layout constraints before classifying them.

## Candidate Improvement Rule
When reviewing a collapse/truncation widget that uses a character-count threshold, verify the threshold against the minimum supported viewport width, font size, and line count limit before classifying it as incorrect. Threshold findings without layout math are advisory candidates, not blocking.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

---

## Turn 6 — qa-specialist (reflection)
*2026-03-05T23:20:22.810281+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The accessibility findings (Semantics, 48dp tap target) were caught by ux-evaluator, not me. Minimum touch target size is testable and measurable — I should have caught the 15dp target independently. I also did not immediately cross-reference the new _CollapsibleMessageText against the existing chat_bubble_test.dart to frame zero coverage as blocking.

## Candidate Improvement Rule
New interactive StatefulWidget = test coverage required before merge. When a new StatefulWidget with user-triggered state transitions is introduced to a widget that already has a test file, tests for the new state machine must be present in that file before approval — this converts QA-A2 class findings from advisory to blocking when test infrastructure already exists.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

---
