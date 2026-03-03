---
discussion_id: DISC-20260303-180530-review-checkin-screen-history-export
started: 2026-03-03T18:05:46.636337+00:00
ended: 2026-03-03T18:17:02.616080+00:00
agents: [architecture-consultant, facilitator, performance-analyst, qa-specialist, ux-evaluator]
total_turns: 8
---

# Discussion: DISC-20260303-180530-review-checkin-screen-history-export

## Turn 1 — facilitator (evidence)
*2026-03-03T18:05:46.636337+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Build Phase 1 Task 10 from the ADHD roadmap: dedicated CheckInScreen (slider-based, no chat chrome), export completeness (check-ins + photos in JSON export), and CheckInHistoryScreen (progressive disclosure after first check-in, expandable cards with score chip and per-question answer bars)
- **Files/scope**: lib/ui/screens/check_in_screen.dart (new), lib/ui/screens/check_in_history_screen.dart (new), lib/providers/questionnaire_providers.dart (history providers + CheckInHistoryEntry), lib/providers/session_providers.dart (completeCheckInSession), lib/database/daos/questionnaire_dao.dart (watchAllResponsesWithAnswers), lib/ui/screens/session_list_screen.dart (routing + history icon), lib/ui/screens/settings_screen.dart (export completeness), lib/app.dart (routes)
- **Developer-stated motivation**: Complete the non-voice check-in UX path and give users access to their check-in history with ADHD-safe design (no gap dates, no streaks, no gap-shaming)
- **Explicit constraints**: No intl package; ADHD UX constraints (no gap dates, no streaks, neutral score chip palette); progressive disclosure (history icon hidden until first check-in); PopScope back-button handling; completeCheckInSession must bypass empty-session auto-discard guard

---

## Turn 2 — qa-specialist (proposal)
*2026-03-03T18:11:03.026976+00:00 | confidence: 0.88*
*tags: qa*

## QA Review

**Confidence: 0.88**

### Well-Covered
- CheckInNotifier (all 13 notifier tests), watchAllResponsesWithAnswers (empty + answers + score), completeCheckInSession (4 assertions incl. wasAutoDiscardedProvider), CheckInHistoryScreen widget tests.

### Findings

**F1 (Medium)**: Completion path entirely untested — no test exercises checkInState.isComplete, completeCheckInSession dispatch, or completion card buttons (Done + Add journal note). The _sessionComplete guard could silently regress.

**F2 (Medium)**: Discard confirmation 'Discard' tap path untested — only 'Keep going' is tested. If discardSession() were accidentally removed, ghost sessions would appear in journal list (see regression-ledger 2026-03-02).

**F3 (Medium)**: _CheckInHistoryIconButton progressive disclosure untested — count=0 hidden and count>=1 shown have no test cases in session_list_screen_test.dart. Provider is not overridden in test harness.

**F4 (Low)**: _normalizeValue private function — no unit test. Boundary cases (value==scaleMin, value==scaleMax, out-of-range, degenerate 5,5,5) unverified.

**F5 (Low)**: _formatTime boundary cases (midnight 00:00, noon 12:00) untested. CalendarEventCard solved this by exposing @visibleForTesting static methods.

**F6 (Low)**: checkInHistoryProvider multi-template cache scenario untested. If two responses share different templates, the itemTextCache/templateCache logic is exercised only by the smoke test, not a unit test.

---

## Turn 3 — architecture-consultant (proposal)
*2026-03-03T18:11:21.372045+00:00 | confidence: 0.88*
*tags: architecture*

## Architecture Review

**Confidence: 0.88**

### Alignment
Changes are well-aligned with ADR-0025 (journaling modes), ADR-0032 (four-table schema), ADR-0007 (constructor-injected DAO), ADR-0029 (ref.read/watch constraint). completeCheckInSession correctly scopes the empty-session bypass. Progressive disclosure via checkInCountProvider follows _TasksIconButton/_GalleryIconButton pattern exactly.

### Findings

**F1 (Medium — BLOCKING)**: checkInHistoryProvider calls getActiveItemsForTemplate(templateId) which filters isActive=true. If a user deactivates a questionnaire item after completing check-ins, that item's question text silently disappears from historical answers — fallback 'Question N' displayed instead. ADR-0032 explicitly supports item deactivation via updateItem. Fix: add getAllItemsForTemplate (no isActive filter) to QuestionnaireDao and use it in the history provider. Active-only is correct for the 'answer today' path; the history path needs the full historical record.

**F2 (Medium — Advisory)**: async* + await-for + asyncMap pattern is novel relative to all other StreamProviders in the codebase. Undocumented. Add an inline comment explaining why async* is used (DAO round-trips for metadata resolution) and acknowledging the known backpressure characteristic. A new ADR is not warranted at current scale.

**F3 (Low — Advisory)**: _sessionComplete=true set inside build() — only screen in codebase that mutates widget-local state in the build phase. Correct and safe due to addPostFrameCallback deferral, but inconsistent with broader pattern (callbacks from buttons or initState). Consider ref.listen in initState for future refactor.

**F4 (Low — Advisory)**: 'pulse_check_in' string literal duplicated across session_list_screen.dart mode picker and routing logic. Define a JournalingMode constants class. Do not use Dart enum (ADR-0025 rejected for forward compatibility).

**F5 (Informational)**: Score chip toStringAsFixed(0) on floating-point — floating-point precision could produce 99.99 or 100.00000001; toStringAsFixed rounds correctly in both cases. No change required.

---

## Turn 4 — ux-evaluator (proposal)
*2026-03-03T18:11:53.335153+00:00 | confidence: 0.88*
*tags: ux, accessibility, adhd-constraints*

UX Review (confidence 0.88). ADHD constraints: FULLY COMPLIANT -- no gap dates, no streaks, neutral score chip, warm microcopy, positive discard framing. Findings: F1 HIGH BLOCKING: _CheckInEntryCard InkWell has no Semantics -- TalkBack cannot identify as interactive. Fix: Semantics(button:true, label) wrapper or ExpansionTile. F2 HIGH BLOCKING (adjacent, pulse_check_in_widget.dart): Slider no semanticFormatterCallback -- TalkBack says '5' with no scale context. Fix: semanticFormatterCallback. F3 HIGH BLOCKING: LinearProgressIndicator in _AnswerRow no semantic label -- TalkBack says '50%' with no question context. Fix: Semantics(label:'question: value', excludeSemantics:true). F4 Medium Advisory: completeCheckInSession failure not surfaced -- 'Check-in saved.' shows before DAO write confirmed. Add _saveFailed state + retry. F5 Medium Advisory: History error state shows raw exception string to user. Replace with user-friendly message + Try again button. F6 Medium Advisory: PopScope(canPop:false) held after _sessionComplete=true -- blocks Android predictive back. Make canPop dynamic. F7 Medium Advisory (adjacent): Disabled Next/Finish button in pulse_check_in_widget.dart gives no hint why. F8 Low Advisory: No loading indicator on 'Add a journal note' CTA -- potential double-tap. F9 Low Advisory: insights_outlined icon recognition gap for non-TalkBack users.

---

## Turn 5 — performance-analyst (proposal)
*2026-03-03T18:12:06.469064+00:00 | confidence: 0.88*
*tags: performance, database*

Performance Review (confidence 0.88). The IN-clause batch pattern for answers is correct -- N+1 eliminated in both watchAllResponsesWithAnswers and getAllResponsesForSession. Index coverage is complete (idx_checkin_responses_session_id, idx_checkin_answers_response_id). Findings: F1 Low Advisory: checkInCountProvider fetches full rows just to call .length -- wasteful on hot home screen observable. Fix: add watchCheckInCount() with selectOnly + column.count() to QuestionnaireDao, matching existing getMessageCount pattern in message_dao.dart. F2 Low Advisory: checkInHistoryProvider allocates fresh itemTextCache and templateCache per emission even though template data is effectively static. Fix: hoist caches outside the await-for loop (above the stream subscription). F3 Low Informational: asyncMap vs JOIN -- asyncMap + IN-clause is the correct trade-off. A drift JOIN would require complex TypedResult projection. No change recommended. F4 Low Informational: Export loop 4 queries per session -- acceptable for offline cold-path operation. Batch optimization deferred until user reports slowness. F5 Low Advisory: isIn() IN-clause bound-parameter limit is 999 in SQLite. At 1-3 check-ins/day, ceiling reached in 1-3 years. Add a code comment noting the limit and suggesting chunked queries if scale approaches that threshold.

---

## Turn 6 — facilitator (synthesis)
*2026-03-03T18:12:38.721076+00:00 | confidence: 0.87*
*tags: blocking:4, advisory:17*

## Request Context
- **What was requested**: Build Phase 1 Task 10: dedicated CheckInScreen, export completeness, CheckInHistoryScreen
- **Files/scope**: check_in_screen.dart (new), check_in_history_screen.dart (new), questionnaire_providers.dart, session_providers.dart, questionnaire_dao.dart, session_list_screen.dart, settings_screen.dart, app.dart
- **Developer-stated motivation**: Complete non-voice check-in UX path with ADHD-safe history dashboard (no gap dates, no streaks)
- **Explicit constraints**: No intl package; ADHD clinical UX constraints; progressive disclosure; completeCheckInSession bypasses empty-session guard

## Verdict: approve-with-changes (4 blocking, 17 advisory)

### Blocking Findings (must fix before merge)

**B1 (Architecture)**: checkInHistoryProvider calls getActiveItemsForTemplate(templateId) which filters isActive=true. Deactivated questionnaire items silently lose their question text in historical view -- 'Question N' fallback shown instead. ADR-0032 supports item deactivation. Fix: add getAllItemsForTemplate (no isActive filter) to QuestionnaireDao for the history path.

**B2 (UX/Accessibility)**: _CheckInEntryCard InkWell has no Semantics wrapper. TalkBack users cannot identify the card as interactive or determine its expanded/collapsed state. Fix: Semantics(button:true, label:'date, score X, expanded/collapsed') or replace with ExpansionTile.

**B3 (UX/Accessibility)**: _AnswerRow LinearProgressIndicator has no semantic annotation. TalkBack announces '50%' with no question context. Fix: Semantics(label:'question: value', excludeSemantics:true) wrapping the Row.

**B4 (UX/Accessibility, adjacent)**: Slider in pulse_check_in_widget.dart (not in primary scope) has no semanticFormatterCallback. TalkBack announces raw numeric value with no scale context. Fix: semanticFormatterCallback to include scale max.

### Advisory Findings

A1 (QA Medium): CheckInScreen completion path untested -- no test exercises isComplete, completeCheckInSession dispatch, or completion card CTAs.
A2 (QA Medium): Discard 'Discard' confirmation tap untested -- only 'Keep going' is tested.
A3 (QA Medium): _CheckInHistoryIconButton progressive disclosure untested -- count=0/1 cases not in session_list_screen_test.dart.
A4 (QA Low): _normalizeValue boundary cases (min, max, out-of-range, degenerate) untested.
A5 (QA Low): _formatTime midnight/noon boundary cases untested.
A6 (QA Low): checkInHistoryProvider multi-template caching scenario untested.
A7 (Architecture Medium): async* + asyncMap pattern undocumented relative to other StreamProviders -- add inline comment.
A8 (Architecture Low): _sessionComplete set inside build() -- inconsistent with broader pattern, advisory refactor.
A9 (Architecture Low): 'pulse_check_in' string literal duplicated -- define JournalingMode constants class.
A10 (UX Medium): completeCheckInSession failure not surfaced -- 'Check-in saved.' shows before DAO write confirmed.
A11 (UX Medium): History error state exposes raw exception string -- replace with user-friendly message + retry.
A12 (UX Medium): PopScope(canPop:false) held after completion -- blocks predictive back (API 33+).
A13 (UX Medium, adjacent): Disabled Next/Finish in pulse_check_in_widget.dart gives no hint why.
A14 (UX Low): No loading indicator on 'Add a journal note' CTA.
A15 (Performance Low): checkInCountProvider fetches full rows for count -- should use COUNT query.
A16 (Performance Low): checkInHistoryProvider rebuilds caches per emission -- hoist caches outside await-for loop.
A17 (Performance Low): IN-clause limit 999 -- add code comment for future maintainers.

### Strengths
- ADHD clinical UX constraints upheld across all new screens: no gap-shaming, no streaks, neutral score chip palette, warm microcopy, positive discard framing. Zero violations.
- completeCheckInSession is precisely scoped and well-documented -- the empty-session guard bypass is explicit and traceable (Principle 1).
- _sessionComplete bool guard correctly prevents double-invocation of session close.
- _AnswerRow scaleMin/scaleMax required constructor fields prevent hardcoded 1-10 from creeping back in.
- _normalizeValue guard for scaleMin==scaleMax prevents division-by-zero.
- Progressive disclosure follows exact same pattern as _TasksIconButton and _GalleryIconButton -- consistent.
- completeCheckInSession regression test has 4 meaningful assertions including wasAutoDiscardedProvider=false.

---

## Turn 7 — qa-specialist (reflection)
*2026-03-03T18:16:55.673626+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The three accessibility blockings (B2, B3, B4) were correctly caught, but I did not flag completeCheckInSession optimistic save (A10) as blocking. Also did not proactively audit pulse_check_in_widget.dart (adjacent to new flow) -- the slider semantics gap was surfaced by UX, not QA. Next time I would explicitly audit adjacent files touched by new flows.

## Candidate Improvement Rule
When a new screen introduces a completion or save action, QA must check whether the save is confirmed before success feedback is shown. If completeCheckInSession() is async and the success indicator fires synchronously, flag optimistic-save-without-error-handling as medium-blocking.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

---

## Turn 8 — ux-evaluator (reflection)
*2026-03-03T18:17:02.616080+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The PopScope(canPop:false) issue (F6) was flagged advisory when it warrants closer examination -- once _sessionComplete is true, predictive back remains blocked. Did not fully probe the 'Add a journal note' CTA for race condition during async window -- double-tap possible.

## Candidate Improvement Rule
For any PopScope(canPop:false) usage, verify that canPop becomes true once the destructive-action risk is resolved. Static canPop:false persisting past the point of no destructive consequence is a platform violation, not merely advisory.

## Confidence Calibration
Original: 0.88, Revised: 0.84, Delta: -0.04

---
