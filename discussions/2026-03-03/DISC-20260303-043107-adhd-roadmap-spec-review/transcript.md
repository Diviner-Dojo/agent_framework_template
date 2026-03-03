---
discussion_id: DISC-20260303-043107-adhd-roadmap-spec-review
started: 2026-03-03T04:31:19.977351+00:00
ended: 2026-03-03T04:37:02.986540+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260303-043107-adhd-roadmap-spec-review

## Turn 1 — facilitator (evidence)
*2026-03-03T04:31:19.977351+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Review the ADHD-informed feature roadmap spec (SPEC-20260302-adhd-informed-feature-roadmap.md) for specialist feedback before implementation begins
- **Files/scope**: docs/sprints/SPEC-20260302-adhd-informed-feature-roadmap.md — 4-phase roadmap: Pulse Check-In Questionnaire (Phase 1 with Voice Capture Prerequisites), Quick Wins (Phase 2), Engagement/Retention (Phase 3), Polish (Phase 4)
- **Developer-stated motivation**: Spec was assembled from ADHD clinical research and updated with voice capture improvements from DISC-20260303-031401; needs specialist validation before /build_module is invoked
- **Explicit constraints**: Maintain ADHD-clinical framing throughout; voice improvements must be cohesively integrated; no behavior change to currently-passing tests

---

## Turn 2 — architecture-consultant (critique)
*2026-03-03T04:36:00.934906+00:00 | confidence: 0.87*
*tags: architecture, blocking, request-changes*

Verdict: Request Changes. 2 high blocking findings, 4 medium advisory.

BLOCKING F1 — SessionNotifier boundary violation: spec adds 3 new state fields to SessionNotifier (already 20+ fields, 8 dependencies). Check-in state should live in separate CheckInNotifier in questionnaire_providers.dart. SessionNotifier retains only journalingMode + one isCheckInActive bool. Coordinate via session ID. Matches pattern of tasks/calendar providers. ADR refs: ADR-0007, ADR-0025.

BLOCKING F2 — Missing ADR for questionnaire schema: every prior table group has an ADR (ADR-0018/photos, ADR-0019/location, ADR-0020/calendar, ADR-0021/video, ADR-0024/audio). 4-table questionnaire schema + WHO-5 licensing + sync decision = ADR-level scope. Need ADR-0032 before Task 1. ADR-0031 (Deepgram) was called out; ADR-0032 (questionnaire schema) was not.

MEDIUM F3 — QuestionnaireTemplates table vs ADR-0025: ADR-0025 rejected a modes table for single fixed defaults. Spec justifies with Task 8 (user config), but if Task 8 only does enable/disable, SharedPreferences is sufficient. Requires ADR-0025 extension or clarification.

MEDIUM F4 — pulseCheckIn JournalingMode enum: check-in is form-driven, not LLM-prompt-driven. systemPromptFragment should be empty or minimal, documented explicitly so future agents don't assume LLM drives the questions.

MEDIUM F5 — P1 ADR-0031 scope gap: spec gives Deepgram config values but doesn't note that Deepgram speech_final/utterance_end events don't map cleanly to SpeechResult.isFinal. ADR-0031 must scope this mapping explicitly or orchestrator state machine will break mid-P1. ADR refs: ADR-0022, ADR-0016.

MEDIUM F6 — Phase 3A dependency not visible at phase level: dependency on Phase 1 Voice Prerequisites is only in a parenthetical; should be a prominent 'Blocked on P0+P1' marker like Phase 4F.

---

## Turn 3 — qa-specialist (critique)
*2026-03-03T04:36:16.773677+00:00 | confidence: 0.88*
*tags: qa, blocking, request-changes, edge-cases*

Verdict: Request Changes (pre-implementation). 5 high blocking findings.

BLOCKING F1 — No formal acceptance criteria checklist. Verification section lists test types but not pass/fail inputs/outputs. Example missing: 'Composite for [8,6,3,7,5,9] anxiety reversed on 1-10 scale = 72.2 not 73.3'.

BLOCKING F2 — Partial completion policy unspecified. What happens when user abandons mid-flow (4 of 6 items)? compositeScore and value fields have no nullable annotations in schema spec. If partial saves supported, both must be nullable before Task 1 is built (requires drift migration to change after).

BLOCKING F3 — Reverse-scoring formula bug: spec says 'scaleMax + 1 - raw_value' but this is only correct when scaleMin=1. General formula must be 'scaleMax + scaleMin - raw_value'. For 1-10: 10+1-1=10 (correct only accidentally). For 0-10: 10+1-0=11 (WRONG — out of range). Must be clarified/corrected before implementation.

BLOCKING F4 — Numeric parser input contract too narrow (only 3 examples). Need full contract table before Task 6: 'seven'→7, 'ten out of ten'→10, 'about a six'→6, 'zero'→null(out of range), 'eleven'→null, 'six point five'→null or 7(spec must decide), 'I don't know'→null, 'skip'→null.

BLOCKING F5 — Voice flow error branches not specified: non-numeric response, out-of-range number, 'skip'/'I don't know' — all produce undefined SessionNotifier behavior. Pattern from regression ledger: unspecified voice error branches cause orchestrator stuck-in-processing (4 prior bugs documented). Must define before Task 4.

MEDIUM F6 — journaling_mode_test.dart 'hasLength(5)' breaks on Task 3 — will fail quality gate on first commit. Must note in Task 3 spec.

MEDIUM F7 — Schema nullable annotations missing for compositeScore and CheckInAnswer.value.

MEDIUM F8 — No test specified for system-default-cannot-be-deleted constraint.

MEDIUM F9 — Division by zero: all items deactivated → computeCompositeScore(empty list) must return null, not NaN.

---

## Turn 4 — docs-knowledge (critique)
*2026-03-03T04:36:31.305220+00:00 | confidence: 0.88*
*tags: docs, blocking, license-risk*

Verdict: Approve with required changes. 2 blocking findings.

BLOCKING F1 — ADR-0031 reference without creation obligation. Spec blocks P1 on ADR-0031 (correct) but doesn't make the ADR creation itself a deliverable from this review. In team use, a developer reading the spec would begin Tasks 1-9 and hit the ADR blocker at P1 without warning. Recommendation: add 'required_adrs' frontmatter field listing ADR-0031 (and ADR-0032 per architecture-consultant) with status 'not-written' and what they block.

BLOCKING F2 — WHO-5 CC BY-NC-SA 3.0 license incompatibility risk. NC clause prohibits commercial use. If app is distributed commercially or as freemium, WHO-5 items require a formal license request to Psychiatric Centre North Zealand (WHO-5 rights holder). PHQ screeners are public domain (no issue). Spec surface-registers the license but has no resolution path, legal review note, or contingency (replace WHO-5 items with custom questions). This can block app store submission. Must add License Notes section with: NC clause acknowledgment, license request path, contingency plan before Task 2 (seed defaults) ships.

MEDIUM F3 — Frontmatter missing reviewed_by, discussion_id (expected after review completes).

MEDIUM F4 — No formal Acceptance Criteria checklist (Verification section is prose bullets, not checkboxes).

LOW F5 — Phase ordering rationale not documented. Why Phase 1 (9 tasks, 4 tables) before Phase 2 (3 quick wins)? Add one paragraph explaining build dependency rationale.

LOW F6 — CLAUDE.md not updated with Clinical UX Constraints pointer. Approved in DISC-20260303-042204 synthesis but not applied. Future review agents on greeting/reminder code have no signal that clinical constraints apply.

---

## Turn 5 — facilitator (synthesis)
*2026-03-03T04:37:02.986540+00:00 | confidence: 0.88*
*tags: blocking:7, advisory:9, request-changes-resolved*

## Request Context
- **What was requested**: Review SPEC-20260302-adhd-informed-feature-roadmap.md before /build_module
- **Files/scope**: docs/sprints/SPEC-20260302-adhd-informed-feature-roadmap.md — 4-phase ADHD roadmap
- **Developer-stated motivation**: Spec assembled from ADHD clinical research and voice deliberation; needs validation before implementation
- **Explicit constraints**: ADHD-clinical framing maintained; voice improvements cohesively integrated

## Verdict: Request Changes — Resolved In-Review

7 blocking findings identified. All 7 resolved by spec edits during review (see changes below).

## Blocking Findings Resolved

B1 (arch): SessionNotifier boundary — Task 4 rewritten to use dedicated CheckInNotifier in questionnaire_providers.dart; SessionNotifier retains only journalingMode + isCheckInActive flag.
B2 (arch): ADR-0032 requirement added — questionnaire schema is ADR-level scope (4 tables + WHO-5 licensing + sync decision). Required ADRs frontmatter section added.
B3 (qa): Partial completion policy added — compositeScore nullable, CheckInAnswer.value nullable. No partial save by default (all 6 required), but architecture supports future partial saves.
B4 (qa): Reverse-scoring formula corrected — 'scaleMax + 1 - raw_value' was wrong for scaleMin != 1; corrected to 'scaleMax + scaleMin - raw_value'.
B5 (qa): Numeric parser input contract table added with 13 defined inputs.
B6 (qa): Voice flow error branches defined — non-numeric re-prompts once, out-of-range re-prompts with range, skip/unknown accepted as null.
B7 (docs): WHO-5 license notes section added — NC clause risk documented, license request path, contingency (replace with custom item).

## Advisory Findings (not blocking, noted)
- arch F3: QuestionnaireTemplates vs ADR-0025 — noted in ADR-0032 scope
- arch F4: pulseCheckIn systemPromptFragment — clarified as empty/minimal in Task 3
- arch F5: Deepgram speech_final mapping — added to P1 ADR-0031 scope
- arch F6: Phase 3A blocked marker — made explicit
- arch F7-9: Numeric parser location, P0 comment, fl_chart review — noted in tasks
- qa F6: journaling_mode_test.dart update — added to Task 3
- qa F8-9: System default delete test, empty list guard — added to Verification
- docs F5: Phase ordering rationale — added
- docs F6: CLAUDE.md Clinical UX Constraints — applied

## Status: spec moved to reviewed

---
