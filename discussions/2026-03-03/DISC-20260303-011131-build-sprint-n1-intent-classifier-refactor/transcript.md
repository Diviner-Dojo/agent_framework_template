---
discussion_id: DISC-20260303-011131-build-sprint-n1-intent-classifier-refactor
started: 2026-03-03T01:11:40.921391+00:00
ended: 2026-03-03T01:33:15.115483+00:00
agents: [architecture-consultant, facilitator, qa-specialist]
total_turns: 8
---

# Discussion: DISC-20260303-011131-build-sprint-n1-intent-classifier-refactor

## Turn 1 — facilitator (evidence)
*2026-03-03T01:11:40.921391+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement SPEC-20260303-010332 — Sprint N+1 intent classifier stability refactor and framework advisory resolution
- **Files/scope**: lib/services/intent_classifier.dart (shared constant, word-count wildcard, anchor removal); test/services/intent_classifier_test.dart (9 regression tests); .claude/commands/*.md, CLAUDE.md, docs/adr/ADR-0030 stub (framework docs)
- **Developer-stated motivation**: Eliminate the class of regression that produced PR #56 and PR #57 by extracting a shared noun constant and replacing brittle char-limit wildcards with word-count wildcards. Also close highest-priority advisory findings from REV-20260302-232244.
- **Explicit constraints**: Zero behavior change for existing passing tests; word-count wildcard must use [\w-]+ to handle hyphenated tokens; _hasStrongCalendarSignal must be updated in same commit as _calendarIntentPattern; no new Flutter dependencies.

---

## Turn 2 — facilitator (proposal)
*2026-03-03T01:11:45.782076+00:00 | confidence: 0.8*
*tags: build-plan*

Build plan: 3 tasks from SPEC-20260303-010332
- Task 1: intent_classifier.dart — shared constant + word-count wildcards + anchor removal (R1.1/R1.2/R1.3) — checkpoint: architecture-choice
- Task 2: Regression tests (R1.4) — 9 tests — checkpoint exempt (pure test writing)
- Task 3: Framework advisory fixes R2.1-R2.5 — checkpoint exempt (docs/commands only)

---

## Turn 3 — facilitator (decision)
*2026-03-03T01:16:49.780501+00:00 | confidence: 0.8*
*tags: task-1, architecture-choice*

Task 1 complete: R1.1 (shared _calendarEventNouns constant), R1.2 (word-count wildcard in both _calendarIntentPattern and _hasStrongCalendarSignal), R1.3 (voice preamble anchor \b in _calendarIntentPattern, ^ preserved in _hasStrongCalendarSignal). Architecture-choice checkpoint triggered: pattern selection changes in intent_classifier.dart.

---

## Turn 4 — qa-specialist (critique)
*2026-03-03T01:18:17.496052+00:00 | confidence: 0.88*
*tags: checkpoint, task-1*

APPROVE (confidence: 0.88). Implementation sound. Shared _calendarEventNouns constant directly eliminates root cause of PR #57 regression (two locations drifting). Doc cross-references clear. Existing regression tests at lines 269-325 cover motivating cases. Advisory (not blocking): new word-count wildcard is broader by design — consider adding a 5-word non-match boundary test and voice preamble path test in Task 2.

---

## Turn 5 — architecture-consultant (critique)
*2026-03-03T01:18:20.053310+00:00 | confidence: 0.88*
*tags: checkpoint, task-1*

APPROVE (confidence: 0.88). Aligns with ADR-0013 §2 and ADR-0020 §3. Deliberate \b vs ^ anchor asymmetry between _calendarIntentPattern and _hasStrongCalendarSignal is architecturally correct. Shared constant enforces sync at compile time. Two low-severity informational findings: (1) _hasStrongCalendarSignal constructs RegExp per call — pre-existing pattern, negligible at scale; (2) greedy {0,4} backtracking in mid-string call site — doc comment adequately flags it.

---

## Turn 6 — facilitator (decision)
*2026-03-03T01:22:04.529380+00:00 | confidence: 0.8*
*tags: task-2, checkpoint-bypass*

Task 2 complete: 9 regression tests added to test/services/intent_classifier_test.dart in group 'word-count wildcard and voice preamble anchor regressions'. All 44 intent classifier tests pass. Checkpoint bypass — pure test writing, no production code changes.

---

## Turn 7 — facilitator (decision)
*2026-03-03T01:26:10.969290+00:00 | confidence: 0.8*
*tags: task-3, checkpoint-bypass*

Task 3 complete: R2.1 INVARIANT comments added to all five context-brief steps (review.md, deliberate.md, build_module.md, plan.md, retro.md). R2.2 cold-start fallback instructions added to all five files. R2.3 privacy filter sentence added to build_module.md. R2.4 context-brief command list added to CLAUDE.md Capture Pipeline section. R2.5 ADR-0030-developer-input-capture.md stub created (status: proposed). Note: retro.md lacked a context-brief step entirely; Step 5.1 added to address both R2.1 and R2.2. Checkpoint bypass — documentation-only changes, no production code modified.

---

## Turn 8 — facilitator (synthesis)
*2026-03-03T01:33:15.115483+00:00 | confidence: 0.95*
*tags: build-summary, blocking:0, advisory:2*

Build complete: 3 tasks, 1 checkpoint fired (Task 1 architecture-choice, both APPROVE), 0 unresolved concerns. Track 1 (intent classifier): shared _calendarEventNouns constant extracted, word-count wildcard (\s+[\w-]+){0,4} replaces .{0,15} in both _calendarIntentPattern and _hasStrongCalendarSignal, voice preamble ^ → \b in _calendarIntentPattern, 9 regression tests all pass. Track 2 (framework advisories): INVARIANT comments added to all 5 context-brief steps, cold-start fallback added to all 5, privacy filter added to build_module.md, CLAUDE.md command list added, ADR-0030 stub created. Quality gate: 7/7. Tests: 1936 total, all pass, 81.2% coverage.

---
