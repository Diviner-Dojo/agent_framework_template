---
discussion_id: DISC-20260303-013421-review-sprint-n1-intent-classifier-refactor-and-advisory-resolution
started: 2026-03-03T01:34:40.097670+00:00
ended: 2026-03-03T01:57:02.211914+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 10
---

# Discussion: DISC-20260303-013421-review-sprint-n1-intent-classifier-refactor-and-advisory-resolution

## Turn 1 — facilitator (evidence)
*2026-03-03T01:34:40.097670+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Ship Sprint N+1 — intent classifier stability refactor and framework advisory resolution (SPEC-20260303-010332)
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, .claude/commands/{review,deliberate,build_module,plan,retro}.md, CLAUDE.md, docs/adr/ADR-0030-developer-input-capture.md, docs/sprints/SPEC-20260303-010332.md
- **Developer-stated motivation**: Eliminate regression class from PR #56 and PR #57 (char-count wildcard brittleness, divergent event noun lists); close highest-priority advisory findings from REV-20260302-232244 (INVARIANT comments, cold-start fallback, privacy filter, ADR-0030 stub)
- **Explicit constraints**: Zero behavior change for currently-passing tests; word-count wildcard must be strictly a superset of old char-count wildcard; no new Flutter dependencies; framework changes are documentation-only

---

## Turn 2 — qa-specialist (proposal)
*2026-03-03T01:47:32.230740+00:00 | confidence: 0.88*
*tags: round-1, qa*

APPROVE-WITH-CHANGES (confidence: 0.88). QA findings: F1 (medium) Missing test for new FP territory — word-count wildcard now matches 'Add context to the call summary' (4 words before 'call'); spec risk table explicitly called for tests documenting this accepted tradeoff. F2 (low) @Tags(['regression']) absent from both regression groups. F3 (low) Voice preamble test confidence should be >= 0.75 (has temporal boost from 'tomorrow'). F4 (low) 'Set the call to silent' carry-forward from REV-20260302-230547 A1. Strengths: shared constant eliminates root cause, asymmetric anchor design correct and documented, test coverage structure distinguishes short-message guard path from full scoring path.

---

## Turn 3 — architecture-consultant (proposal)
*2026-03-03T01:47:35.948166+00:00 | confidence: 0.88*
*tags: round-1, architecture*

APPROVE-WITH-CHANGES (confidence: 0.88). Architecture findings: F1 (medium) _hasStrongCalendarSignal constructs RegExp per call — should be static final field; pre-existing pattern now more costly with larger pattern. F2 (low) _calendarEventNouns doc comment should name the two specific consumers. F3 (low) ADR-0030 template deviations — missing risk_level, confidence, tags frontmatter; ## References should be ## Linked Discussion; 'Alternative D chosen' label conflicts with proposed status. F4 (info) Asymmetric anchor design sound. F5 (info) INVARIANT comment approach correct. Architecture consultant verdict: approve-with-changes, F3 should be resolved before sprint declared complete.

---

## Turn 4 — docs-knowledge (proposal)
*2026-03-03T01:47:40.294525+00:00 | confidence: 0.88*
*tags: round-1, docs*

APPROVE-WITH-CHANGES (confidence: 0.88). Docs findings: F1 (structural note, no change) plan.md INVARIANT placement different but correct. F2 (low) retro.md write_event.py call missing quotes around 'facilitator' and 'evidence' args — inconsistent with other 4 files. F3 (low) ADR-0030 missing risk_level, confidence, tags fields; ## References should be ## Linked Discussion (overlaps architecture F3). F4 (medium) Advisory A6 not addressed — out of scope per spec, must carry forward as open advisory. F5 (low) build_module.md structural position note, no change needed. F6 (low) ADR-0030 Alternative D labeled 'chosen' conflicts with proposed status. Advisory coverage: A1-A5 closed, A6 open (carry forward). CLAUDE.md is accurate and current.

---

## Turn 5 — qa-specialist (critique)
*2026-03-03T01:49:06.590997+00:00 | confidence: 0.82*
*tags: round-2, qa*

Round 2: ADR-0030 template fields → ADVISORY (ADR-0029 also missing same fields, consistent project pattern; substance fully present). Missing FP test → ADVISORY (SPEC risk table 'add' is recommendation; no observed regression; advisory level.

---

## Turn 6 — architecture-consultant (critique)
*2026-03-03T01:49:09.033504+00:00 | confidence: 0.82*
*tags: round-2, architecture*

Round 2: Missing FP test → BLOCKING (SPEC risk table required it; confirmation gate is downstream mitigation, not test coverage substitute; adds 1 test). @Tags missing → BLOCKING (testing requirements rule unambiguous). Facilitator notes: flutter_test group doesn't support tags parameter — @Tags finding is advisory given technical constraint.

---

## Turn 7 — facilitator (synthesis)
*2026-03-03T01:51:57.675595+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:8*

## Request Context
- **What was requested**: Ship Sprint N+1 — intent classifier stability refactor and framework advisory resolution (SPEC-20260303-010332)
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, .claude/commands/{review,deliberate,build_module,plan,retro}.md, CLAUDE.md, docs/adr/ADR-0030-developer-input-capture.md
- **Developer-stated motivation**: Eliminate regression class from PR #56 and PR #57; close advisory findings A1-A5 from REV-20260302-232244
- **Explicit constraints**: Zero behavior change for passing tests; word-count wildcard must be superset of char-count wildcard; no new Flutter dependencies; framework changes documentation-only

## Synthesis

Verdict: approve-with-changes. 1 blocking finding (B1) resolved in-review. 0 blocking findings remain. 8 advisory findings. Three specialists (qa, architecture, docs-knowledge), 2 rounds.

B1 (resolved): Missing false-positive test for new word-count territory — SPEC risk table required 'explicit false-positive tests for new coverage.' Test added: 'Add context to the call summary' → calendarEvent (documents accepted behavior via confirmation gate ADR-0020 §8). 

B2 (resolved, advisory per QA, re-ruled advisory): retro.md unquoted write_event.py args — fixed to match other 4 files.

Advisory items: A1 missing @Tags on regression groups (flutter_test group doesn't support tags; project uses library-level @Tags in standalone files — consistent gap with existing PR #56/57 group). A2 _hasStrongCalendarSignal constructs RegExp per call — pre-existing, negligible at scale. A3 ADR-0030 missing risk_level/confidence/tags fields and ## Linked Discussion section — fixed Alternative D label; template fields deferred. A4 A6 from REV-20260302-232244 (documentation_policy.md enforcement note) carried forward — out of scope per spec. A5 _calendarEventNouns doc comment should name specific consumers explicitly. A6 voice preamble test confidence assertion can be tightened to >= 0.75. A7 'Set the call to silent' carry-forward from REV-20260302-230547.

All acceptance criteria from SPEC-20260303-010332 met: 10 regression tests in new group (was 9, 1 added for FP territory), all 1937 tests pass, 81.2% coverage.

---

## Turn 8 — qa-specialist (reflection)
*2026-03-03T01:56:41.412159+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I initially classified F1 (the missing FP territory test) as advisory rather than blocking. My reasoning was that the confirmation gate backstops misclassification, making it a defense-in-depth gap rather than a direct failure path. That framing was defensible but incomplete: regression tests for intentional behavior changes are blocking by project policy regardless of downstream mitigations, because the test documents accepted behavior under the new wildcard. I should have caught that distinction at first pass rather than requiring the architecture-consultant's REVISE to surface it. I also did not probe whether _hasStrongCalendarSignal had its own distinct FP exposure in the short-message path — both patterns share _calendarEventNouns but have different anchors, and the 4-word boundary interacts differently with the word-count wildcard.

## Candidate Improvement Rule
When reviewing a bug fix that changes a pattern's matching breadth (widens or narrows a regex, threshold, or guard), the reviewer must explicitly enumerate the new acceptance boundary and flag any input that crosses from non-match to match as requiring a documented test, even if the behavior change is intentional. 'Accepted behavior' without a test is an undocumented contract.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

The F1 misclassification (advisory vs. blocking) was a genuine error in risk judgment, not just a borderline call. A 6-point downward revision reflects that: the core analysis was sound and coverage of other findings was accurate, but the one finding that required escalation was the one I underweighted.

---

## Turn 9 — architecture-consultant (reflection)
*2026-03-03T01:56:56.418588+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The RegExp-per-call concern (F1) was flagged as a medium advisory but I did not check whether the hot path actually matters at this call rate. _hasStrongCalendarSignal is only reached when words.length <= 4, which is a guard branch, not the primary scoring path. The allocation cost is real but the frequency is low. I should have scoped the advisory more precisely: 'medium in the limit (high-frequency voice mode), low in practice (guard branch, cold start only).' I also did not audit whether _extractSearchTerms — which also constructs a RegExp inside a frequently-called private method — was a more consequential instance of the same pattern. That was the more actionable location and I did not surface it.

## Candidate Improvement Rule
When flagging a per-call allocation concern, always identify the call site's execution frequency before assigning severity. A guard branch that fires only on short messages (and triggers a short-circuit exit) is not equivalent to a loop body or a hot path in voice transcription. Severity should reflect actual call rate, not theoretical worst case. If call rate cannot be determined from static analysis alone, downgrade to Info and note the uncertainty.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

The original 0.88 reflected high confidence in the boundary and pattern findings. The delta reflects two sources of over-confidence: the F1 severity was not anchored to actual call-site frequency, and _extractSearchTerms's inline RegExp — a structurally identical case — was not noticed. Both omissions indicate the pattern-matching scan was shallower than the confidence implied.

---

## Turn 10 — docs-knowledge (reflection)
*2026-03-03T01:57:02.211914+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The most significant gap was not cross-checking ADR-0030's frontmatter fields against the ADR template at review-open time — catching risk_level, confidence, tags, and ## Linked Discussion during initial triage would have surfaced F3/A3 before Round 1 rather than having it emerge mid-panel. I also did not verify whether ADR-0029 shared the same omissions before flagging A3; architecture-consultant had to note the consistency issue to prevent an inconsistent blocking standard. Next time: run a two-minute ADR template diff at review-open as a checklist step, and check the two most recent ADRs for the same omissions before classifying template gaps as advisory vs. blocking.

## Candidate Improvement Rule
ADR template completeness check: When a review scope includes an ADR file, the docs-knowledge agent must diff the ADR frontmatter against the canonical template fields and check the two most recent ADRs in docs/adr/ for the same omissions. If multiple existing ADRs share the gap, classify as advisory with a note about inconsistency. If only the new ADR has the gap, elevate to blocking. This prevents inconsistent blocking standards across the ADR corpus.

## Confidence Calibration
Original: 0.88, Revised: 0.83, Delta: -0.05

The 0.88 was slightly high. The panel produced one blocked finding that required a two-round disagreement to resolve, a template-gap advisory that required retroactive consistency checking to keep advisory (not blocking), and a carry-forward advisory (A6) that I did not independently verify was out-of-scope before accepting the SPEC's framing. A score in the 0.82-0.85 range would have better reflected the residual uncertainty around the F1 blocking threshold and the ADR consistency question.

---
