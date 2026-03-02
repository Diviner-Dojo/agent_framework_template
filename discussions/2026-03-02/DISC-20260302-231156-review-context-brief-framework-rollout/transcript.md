---
discussion_id: DISC-20260302-231156-review-context-brief-framework-rollout
started: 2026-03-02T23:12:08.118272+00:00
ended: 2026-03-02T23:24:58.042232+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 12
---

# Discussion: DISC-20260302-231156-review-context-brief-framework-rollout

## Turn 1 — facilitator (evidence)
*2026-03-02T23:12:08.118272+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Review framework-wide rollout of the context-brief capture step — 7 files changed across .claude/commands/ (review, deliberate, build_module, plan, retro), .claude/rules/documentation_policy.md, CLAUDE.md, and docs/templates/review-report-template.md
- **Files/scope**: .claude/commands/review.md, deliberate.md, build_module.md, plan.md, retro.md; .claude/rules/documentation_policy.md; CLAUDE.md; docs/templates/review-report-template.md
- **Developer-stated motivation**: Developer input (verbatim requests, domain context corrections, approval caveats) is not captured in Layer 1 discussions. Facilitator synthesis templates include a Request Context section as partial mitigation. Changes implement SPEC-20260302-192548 Step 2: add context-brief event (turn_id=1) before specialist dispatch in all major commands; require synthesis events to begin with Request Context section
- **Explicit constraints**: Must not break existing command workflows; context-brief must always be turn_id=1 (before any specialist); changes are purely additive (no removal of existing steps)

---

## Turn 2 — qa-specialist (proposal)
*2026-03-02T23:17:45.756709+00:00 | confidence: 0.82*
*tags: qa, medium-risk, structured-dialogue*

## QA Review: Context-Brief Framework Rollout

**Confidence: 0.82**

### F1 (Medium): turn_id=1 invariant is convention-only
The context-brief step is specified to produce turn_id=1, but write_event.py assigns turn_ids sequentially based on existing events. Nothing prevents a facilitator from writing another event before the context-brief, breaking the invariant. This is a tooling gap: the promise is strong (always turn_id=1) but enforcement is weak (sequential counter). Recommend: add a warning in write_event.py or document explicitly that the guarantor is always calling context-brief immediately after create_discussion.py.

### F2 (Medium): retro disposition condition always fires
In retro.md, the condition for including the context-brief standing agenda item reads: 'if any discussion from this sprint was created after SPEC-20260302-192548 was adopted'. Since SPEC was adopted on 2026-03-02 and all future retros will have discussions after this date, the condition is always true and adds no gating value. Consider simplifying to 'always check context-brief coverage' without the conditional.

### F3 (Medium): no-framing edge case
When /review is invoked with no conversational context (e.g., `/review lib/foo.dart` as the very first message in a session), the four-field context-brief will have nothing to draw from for developer-stated motivation or constraints. The spec says 'write (none stated)' — this is acceptable as a fallback but should be documented explicitly so facilitators don't invent plausible-sounding motivations.

### F4 (Low): context-brief may go stale in long builds
build_module.md writes context-brief as turn_id=1 at build start. For multi-hour builds across sessions, the developer context captured at start may not reflect late amendments. The current design is correct (capture intent at invocation time), but a note in build_module.md that the context-brief represents initial intent would prevent misreading stale context as authoritative.

### F5 (Low): plan.md doesn't initialize state.json
Unlike review.md which has explicit state.json initialization after create_discussion.py, the updated plan.md adds context-brief but does not initialize a state.json for resumption tracking. Other commands have this; plan.md is inconsistent.

### F6 (Low): documentation_policy.md carve-out needed
The new rule 'All facilitator synthesis events must include ## Request Context' should carve out retro, which explicitly does not write a context-brief or synthesis with developer-stated context. Without the carve-out, a future reviewer enforcing this rule mechanically will flag retro synthesis events as non-compliant.

### F7 (Medium): plan.md synthesis step missing ## Request Context requirement
The plan.md synthesis step was not updated to include the ## Request Context section requirement that was added to review.md and documented in documentation_policy.md. This is a hybrid state — context-brief added but synthesis not updated — creating inconsistency within the same document.

---

## Turn 3 — docs-knowledge (proposal)
*2026-03-02T23:17:59.574935+00:00 | confidence: 0.91*
*tags: docs, medium-risk, structured-dialogue*

## Documentation Review: Context-Brief Framework Rollout

**Confidence: 0.91**

### F1 (Medium): plan.md synthesis step lacks ## Request Context — hybrid state
plan.md now includes the context-brief step (Step 3.5) but the synthesis step was not updated to require ## Request Context in the synthesis event. This creates a hybrid state: intent capture is present, but the synthesis doesn't close the loop by surfacing that context in the output artifact. Every other command updated both steps. plan.md is the only one with the gap.

### F2 (Medium): CLAUDE.md doesn't document which commands have context-brief
The CLAUDE.md update adds known limitations for ADR-0030 and extraction rate baseline, but doesn't document the scope of the context-brief rollout: which commands now capture it (review, deliberate, build_module, plan, retro as standing agenda) versus which don't (analyze-project, meta-review). Without this, a developer onboarding later cannot tell whether omission from a command is intentional exclusion or a missed update.

### F3 (Low): build_module.md missing privacy filter sentence
The build_module.md context-brief section includes the four-field capture pattern, but does not include the privacy filter sentence present in review.md: 'Strip business context (deadlines, client names, regulatory pressures) — record structural intent only.' For a team-use framework (Wells Fargo context), this omission is notable — build invocations may capture client-sensitive framing that should be filtered.

### F4 (Low): ADR-0030 wording — 'deferred' vs 'not yet created'
CLAUDE.md says 'ADR-0030 deferred' in the known limitations section. The ADR does not exist. 'Deferred' implies a written ADR whose implementation is pending; 'not yet created' or 'ADR-0030 placeholder' would be more accurate. Minor but matters for documentation integrity.

### F5 (Low): documentation_policy.md rule has no enforcement mechanism noted
The new rule added to documentation_policy.md ('All facilitator synthesis events must include a ## Request Context section') is a convention rule with no automated enforcement. Adding a note that this is enforced via review checklist (not tooling) sets accurate expectations and signals to future maintainers that adding a linter would be valuable.

---

## Turn 4 — qa-specialist (proposal)
*2026-03-02T23:18:38.893351+00:00 | confidence: 0.82*
*tags: qa, medium-risk*

## QA Review — Context-Brief Framework Rollout
Confidence: 0.82

### F1 (Medium): turn_id=1 invariant is convention-only, not enforced
The spec requires context-brief to be turn_id=1. write_event.py assigns turn_ids sequentially. Any event written before the context-brief (e.g., state.json initialization, a premature write_event call) silently breaks this invariant. There is no guard in write_event.py that rejects a context-brief submitted after turn 1 already exists. Recommend: add a --assert-first-turn flag that fails if the discussion already has events when context-brief is submitted, or at minimum add a comment in each command noting the ordering dependency.

### F2 (Medium): Retro disposition condition always fires
In retro.md Step 7.5, the condition 'if any discussion in the sprint has context-brief events' is structurally guaranteed to be true for any retro run after today, since the rollout covers all commands. The disposition block will always run; it is never a conditional. The 'if not' branch is dead code. Recommend: rewrite as an unconditional standing agenda item, or make the condition meaningful (e.g., 'if context-brief coverage < 100%').

### F3 (Medium): No-framing edge case — /review invoked with no conversational context
The context-brief prompt says 'Summarise the developer's request from the current session.' If /review is invoked with no prior conversation (cold start), there is no request to summarize. The command gives no fallback. Agents will either hallucinate a request context or leave fields blank, both undermining the quality goal. Recommend: add a fallback instruction: 'If invoked without prior conversation, write the files/scope from the review arguments and "(no session context)" for motivation and constraints.'

### F4 (Low): Context-brief may be stale in long build sessions
build_module.md correctly places context-brief as turn_id=1. However, for long builds spanning hours or context compaction, the initial framing may diverge from what the developer actually needs by the end. Acceptable given how builds are structured (spec given upfront). No action required; document as known limitation.

### F5 (Low): plan.md missing state.json initialization step
plan.md adds Step 3.5 for context-brief but does not add a state.json initialization step (comparable to review.md Step 3). If plan.md is the entry point to a multi-session spec effort, losing state between sessions risks the same problems the state.json was designed to solve. Advisory: add state.json initialization to plan.md's Step 3.

### F6 (Low): documentation_policy.md carve-out needed for retro
The new rule 'All facilitator synthesis events must include a ## Request Context section' applies globally. Retro syntheses document sprint-wide patterns, not a single developer request — the Request Context section would be artificial. The rule should carve out retro (and meta-review) or reframe as 'where a single developer request is being addressed.'

### F7 (Medium): plan.md synthesis step lacks ## Request Context requirement
The review.md synthesis step now requires '## Request Context' as the opening section. The plan.md synthesis step (Step 7 or equivalent) was not updated with this requirement. The pattern is inconsistent — plans produce synthesis events but won't have the Request Context header, breaking the extraction pipeline's assumed structure.

---

## Turn 5 — docs-knowledge (proposal)
*2026-03-02T23:18:57.330647+00:00 | confidence: 0.91*
*tags: docs, medium-risk*

## Documentation Review — Context-Brief Framework Rollout
Confidence: 0.91

### F1 (Medium): plan.md synthesis step lacks ## Request Context requirement — hybrid state
plan.md was updated to add Step 3.5 (context-brief capture) but the synthesis step was not updated to require a ## Request Context opening section, as review.md's synthesis was. This creates a hybrid state: context-brief is captured at turn_id=1 but the synthesis won't reference it in the expected structure. The extraction pipeline (extract_findings.py) and any future tooling that keys on ## Request Context will miss plan discussions. Blocking: update plan.md synthesis step to match review.md.

### F2 (Medium): CLAUDE.md doesn't document which commands have context-brief and why analyze-project/meta-review are excluded
The two new CLAUDE.md lines describe the extraction-rate baseline and the developer input capture gap, but don't enumerate which commands now emit context-brief events. A developer reading CLAUDE.md can't determine from the capture pipeline section whether /deliberate, /retro, /build_module, /plan all participate. The analyze-project and meta-review exclusions are undocumented. Recommend: add a brief list: 'Context-brief events (turn_id=1) are emitted by: /review, /deliberate, /build_module, /plan, /retro. Excluded: /analyze-project (outward-facing, no developer request context), /meta-review (aggregate analysis, no single request).'

### F3 (Low): build_module.md missing privacy filter sentence
The context-brief instruction says 'Strip business context (deadlines, client names, regulatory pressures) — record structural intent only.' This sentence does not appear in build_module.md's context-brief step. The review.md and deliberate.md versions include it. A developer reading only build_module.md won't know to apply the filter. Recommend: add the privacy filter sentence to build_module.md's context-brief guidance.

### F4 (Low): ADR-0030 'deferred' vs 'not yet created' wording in CLAUDE.md
CLAUDE.md references 'ADR-0030 deferred' as a known limitation. ADR-0030 does not exist in docs/adr/ — no placeholder, no stub. 'Deferred' implies a decision was started and paused; 'not yet created' is more accurate. Either create a stub ADR-0030 with status: proposed, or change the wording to 'pending ADR creation.' Recommend: create stub ADR-0030 to make the reference resolvable.

### F5 (Low): documentation_policy.md new rule has no enforcement mechanism noted
The new line 'All facilitator synthesis events must include a ## Request Context section...' is a rule without an enforcement path. Unlike the context-brief requirement (enforced by command workflow order) or the regression test requirement (enforced by quality_gate.py), this rule has no automated check. No action required to block merge, but recommend a comment: '(Verified by review facilitator during synthesis step — no automated check.)'

---

## Turn 6 — architecture-consultant (proposal)
*2026-03-02T23:19:18.169317+00:00 | confidence: 0.87*
*tags: architecture, medium-risk*

## Architecture Review — Context-Brief Framework Rollout
Confidence: 0.87

### F1 (Medium): turn_id=1 invariant is convention-only — acceptable for now, but fragile
The turn_id sequence is assigned by write_event.py in insertion order. The invariant that context-brief = turn_id=1 is enforced only by command workflow order (Step 3.5 fires before Step 5). Any future command refactor that inserts an event before Step 3.5 silently breaks the invariant without error. This is an acceptable trade-off given the cost of enforcement tooling, but the risk should be documented. Recommend: add a comment block in each command's context-brief step — '# INVARIANT: This must be the first write_event.py call in this workflow. turn_id=1 is required for extraction pipeline integrity.' Additionally, worth filing as a candidate for write_event.py --assert-first-turn flag in a future cleanup sprint.

### F2 (Medium): Retro standing agenda placement is structurally weak
retro.md adds the context-brief review item as a standalone block appended after Step 7, rather than integrating it as a numbered step (e.g., Step 7.5 or Step 8). This creates a two-tier agenda where the main 7-step structure is 'official' and the appended block is advisory. Facilitators following the numbered steps will reach 'Step 7: Close discussion' and may close without performing the context-brief coverage check. The block should be embedded as Step 7.5 with a numbered heading and integrated into the workflow sequence, not appended as a free-floating section. Blocking: restructure retro.md to embed context-brief coverage review as a numbered step before close_discussion.

### F3 (Low): analyze-project exclusion is under-documented at the architectural level
The analyze-project exclusion from context-brief is correct (outward-facing scouting, no single developer request framing), but the rationale appears only implicitly. CLAUDE.md and the commands themselves don't articulate why this command is excluded while /plan and /retro (also not a single-request pattern) are included. Recommend: add a one-sentence exclusion rationale to CLAUDE.md and to analyze-project.md.

### F4 (Info): ADR-0030 deferred reference — placeholder file recommended
The CLAUDE.md known-limitations section references 'ADR-0030 deferred.' This is not a blocking architectural issue (decisions can be deferred), but a placeholder stub with status: proposed, title, and a one-line problem statement would make the reference resolvable and prevent confusion. Not blocking.

### F5 (Low): retro context-brief exclusion is architecturally sound
The retro command summarizes sprint-wide discussions. Requiring a context-brief on the retro itself would create a meta-level recursion (the facilitator summarizing their own intent to summarize). The exclusion is correct. The standing agenda item approach (checking coverage of sprint discussions) is the right architectural alternative.

### F6 (Info): build_module.md context-brief reordering relative to build plan is correct
The build_module.md change places context-brief as turn_id=1 before the build plan event. This is architecturally correct: the build plan is a proposal derived from the developer's request, so the request context must precede the plan in the discussion record. Approved.

---

## Turn 7 — qa-specialist (critique)
*2026-03-02T23:20:36.627131+00:00 | confidence: 0.82*
*replying to turn 4*
*tags: qa, round-2, critique*

## Round 2 — QA Cross-Review

**Endorses architecture-consultant on retro placement (F2):** The standing agenda item appended after Step 7 is visually detached from the numbered workflow. An agent executing the command could complete Step 7 and stop, missing the item entirely. The blocking classification is appropriate — it affects reliable execution, not just readability.

**Endorses docs-knowledge on plan.md synthesis gap (F7/F1):** Confirmed in the current file. plan.md Step 5 synthesis writes a synthesis event but contains no ## Request Context requirement, unlike review.md Step 7. Inconsistency is real. Blocking is appropriate.

**Advisory (not blocking) on CLAUDE.md enumeration:** Endorses making the context-brief command list informational in CLAUDE.md, but not blocking.

**Elevates F2 (retro dead-code) to blocking:** The disposition condition in the standing agenda checks for non-open findings, but the schema acknowledges this column is not yet implemented — the condition is structurally always-true, making the diagnostic value permanently undermined. The standing agenda item cannot do its job as written. Elevating to blocking.

---

## Turn 8 — architecture-consultant (critique)
*2026-03-02T23:20:41.425525+00:00 | confidence: 0.82*
*replying to turn 6*
*tags: architecture, round-2, critique*

## Round 2 — Architecture Cross-Review

**Endorses QA F2 (retro dead-code) at medium severity:** Confirmed — the condition 'if any discussion has context-brief' is structurally always-true post-rollout. Replace the tautological condition with the three concrete behavioral signals already listed beneath it.

**Endorses QA F3 (cold-start) with architectural reframe:** The cold-start case is a contract gap, not just a fallback design problem. The context-brief step carries an implicit precondition (facilitator has session context to summarize). Correct fix: add a guard instruction — 'If no conversational context exists, populate all four fields as (none stated) and tag context-brief-cold-start for analysis.' This keeps the invariant while making cold-start explicit and queryable.

**Partial disagreement with docs-knowledge on plan.md (blocking vs advisory):** The plan.md synthesis gap is real but advisory for /plan specifically — the spec file is the primary durable artifact, the synthesis event is internal scaffolding. Blocking is appropriate for /review and /deliberate where the synthesis IS the primary durable artifact. Developer should decide.

**F1 (turn_id=1 invariant) remains valid and uncontested.** The cold-start analysis reinforces it as load-bearing.

---

## Turn 9 — facilitator (synthesis)
*2026-03-02T23:22:38.236701+00:00 | confidence: 0.88*
*tags: blocking:3, advisory:6*

## Request Context
- **What was requested**: Review 7 framework files implementing the context-brief capture step (SPEC-20260302-192548 Step 2) across all slash commands: /review, /deliberate, /build_module, /plan, /retro, plus updates to documentation_policy.md and CLAUDE.md.
- **Files/scope**: .claude/commands/review.md, deliberate.md, build_module.md, plan.md, retro.md; .claude/rules/documentation_policy.md; CLAUDE.md; docs/templates/review-report-template.md
- **Developer-stated motivation**: Implement SPEC-20260302-192548 Step 2 — ensure every slash command captures developer framing as turn_id=1 context-brief event before specialist dispatch, improving extraction pipeline quality and reducing specialist echo.
- **Explicit constraints**: All commands must emit context-brief at turn_id=1; analyze-project and meta-review are excluded (outward-facing / aggregate analysis).

## Synthesis

Verdict: **approve-with-changes** — 3 blocking findings resolved during review, 6 advisory findings documented.

### Blocking Findings (3, all resolved during review)

**B1 — RESOLVED: plan.md synthesis step lacked ## Request Context requirement.**
QA (F7) and docs-knowledge (F1) independently identified that plan.md added the context-brief Step 3.5 but did not update the synthesis step to require a ## Request Context opening section, creating a hybrid state where context-brief is captured but not referenced in the synthesis structure. Fixed: plan.md Step 5 now requires ## Request Context as the opening section of the synthesis event, consistent with review.md.

**B2 — RESOLVED: Retro standing agenda structurally weak (appended after Step 7).**
Architecture-consultant (F2) identified that the standing agenda was appended as a free-floating block after Step 7 rather than integrated as a numbered step. Agents completing the numbered workflow reach 'Step 7: Present' and may stop without executing the gate. Fixed: restructured as Step 5.5 (before finalization), with numbered heading embedded in the workflow sequence.

**B3 — RESOLVED: Retro disposition condition always fires (dead code).**
QA (F2, elevated to blocking in Round 2) identified that the condition  returns zero rows structurally — the disposition column is not yet implemented, so the condition is permanently true and one branch is dead code. Fixed: rewritten as three explicit observable signals (specialist echo, framing drift, disposition activity) with a clear decision rule and a note that Signal C is pending implementation.

### Advisory Findings (6)

**A1 (Medium): turn_id=1 invariant is convention-only.**
QA (F1) and architecture-consultant (F1) both flag that the turn_id=1 guarantee for context-brief is enforced by command ordering, not tooling. Any future reorder silently breaks extraction pipeline integrity. Recommendation: add INVARIANT comment to each command's context-brief step. Long-term: write_event.py --assert-first-turn flag. Accepted as known limitation.

**A2 (Medium): Cold-start edge case — no fallback for /review invoked without session context.**
QA (F3) and architecture-consultant (architectural elevation in Round 2) identify that if /review is invoked fresh (no prior conversation), the context-brief step has no fallback instruction. Architecture proposes: tag with 'context-brief-cold-start' and populate all four fields as '(none stated)'. Advisory: add fallback guidance to review.md and equivalents in a follow-up.

**A3 (Medium): CLAUDE.md doesn't enumerate which commands have context-brief.**
Docs-knowledge (F2): The exclusions of analyze-project and meta-review are undocumented. Recommend adding a list of context-brief-emitting commands to CLAUDE.md's capture pipeline section. Advisory.

**A4 (Low): build_module.md missing privacy filter sentence.**
Docs-knowledge (F3): 'Strip business context...' sentence absent from build_module.md context-brief step. Advisory: add in a follow-up pass.

**A5 (Low): ADR-0030 'deferred' wording — stub file recommended.**
Docs-knowledge (F4) and architecture-consultant (F4): CLAUDE.md references 'ADR-0030 deferred' but no stub file exists. Recommend creating a stub ADR-0030 with status: proposed. Advisory.

**A6 (Low): documentation_policy.md rule has no enforcement mechanism noted.**
Docs-knowledge (F5): The new rule about ## Request Context in synthesis events has no automated check. Recommend adding a parenthetical noting it's verified by the review facilitator. Advisory.

### Panel Agreement
All three specialists independently converged on B1 (plan.md synthesis gap) and B3 (retro dead-code). Architecture-consultant called B2 blocking; QA endorsed in Round 2. Architecture partially disagreed on B1 severity for /plan specifically (advisory vs blocking), noting that the spec file is the primary artifact for /plan and the synthesis is internal scaffolding — deferred to facilitator judgment, who classified as blocking for consistency with review.md pattern.

---

## Turn 10 — qa-specialist (reflection)
*2026-03-02T23:24:42.026500+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

The regression-ledger check was skipped entirely. For framework command files that modify workflow steps, I should have verified whether any bugs previously logged in `memory/bugs/regression-ledger.md` touched these command files. Additionally, I did not explicitly verify that the three in-review fixes (B1, B2, B3) were actually applied to the files on disk before emitting the synthesis — I accepted the facilitator's characterization that they were resolved without independently confirming the diffs.

## Candidate Improvement Rule

When blocking findings are classified as 'resolved during review,' the QA specialist must independently verify that the resolution was actually applied to the file on disk (by reading the updated file) before endorsing 'approve-with-changes.' Self-reported resolutions without verification create a false confidence signal.

## Confidence Calibration

Original: 0.82, Revised: 0.78, Delta: -0.04

---

## Turn 11 — docs-knowledge (reflection)
*2026-03-02T23:24:49.385341+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

My docs-knowledge review identified 5 findings (F1-F5), all of which were validated. However, I did not check the `docs/templates/review-report-template.md` file directly — I referenced it only inferentially. Had the template update been subtly inconsistent with the command-level changes, I would have missed it. I also did not flag the growing advisory backlog (72 total) as a discoverability risk.

## Candidate Improvement Rule

When reviewing cross-cutting framework changes (rollouts touching 5+ files), the docs-knowledge agent should verify that any existing template files referenced by the changed commands are also consistent with the rollout — specifically by reading template files directly, not inferring consistency from command-level changes.

## Confidence Calibration

Original: 0.91, Revised: 0.85, Delta: -0.06

---

## Turn 12 — architecture-consultant (reflection)
*2026-03-02T23:24:58.042232+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

I did not flag the cold-start edge case (A2) that QA identified — a quick precondition simulation of 'what must be true for this step to execute correctly?' would have surfaced it. I also did not independently read the excluded command files (/deliberate, /analyze-project, /meta-review) to confirm the exclusion rationale; I relied on the facilitator's evidence event framing. My F2 on retro placement was correct and blocking, but the stronger framing (agents stop at Step 7 and never reach the gate) was clearer in Round 2 than in Round 1.

## Candidate Improvement Rule

Precondition simulation check: For any new step added to a command workflow, explicitly ask 'what must be true in the environment for this step to execute correctly?' and 'what happens if that precondition is absent?' This catches cold-start gaps, ordering invariants, and dead-code conditions.

## Confidence Calibration

Original: 0.87, Revised: 0.83, Delta: -0.04

---
