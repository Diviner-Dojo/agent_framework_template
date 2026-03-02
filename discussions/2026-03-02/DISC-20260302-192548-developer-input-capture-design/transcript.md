---
discussion_id: DISC-20260302-192548-developer-input-capture-design
started: 2026-03-02T19:30:18.960300+00:00
ended: 2026-03-02T19:35:03.531600+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective]
total_turns: 7
---

# Discussion: DISC-20260302-192548-developer-input-capture-design

## Turn 1 — architecture-consultant (proposal)
*2026-03-02T19:30:18.960300+00:00 | confidence: 0.91*
*tags: architecture, developer-capture, approach-a*

## Architectural Analysis: Developer Input Capture

### Summary
The gap is real and significant. Principle #1 (reasoning is the primary artifact) is violated because the developer's reasoning — the causal root of every discussion — is entirely absent from the capture stack. 474 turns across 92 discussions contain zero developer turns.

### Approach Evaluation

**Approach A (Extend write_event.py with agent='developer') — RECOMMENDED**
The agent field accepts any string today; only the intent CHECK constraint needs updating. Developer events flow through the existing pipeline (events.jsonl → SQLite → downstream scripts) automatically. Immutability preserved — developer events sealed at closure with the rest of the discussion. Requires: (1) schema migration adding 'directive' and 'context' intent types, (2) filter updates in extract_findings.py and compute_agent_effectiveness.py to exclude 'developer', (3) updated command workflow templates defining three capture moments: initial directive, mid-discussion course corrections, disposition event.

**Approach B (parallel developer-journal.jsonl) — REJECTED**
Creates a second event stream the pipeline doesn't know about. Every existing script must be taught about it individually. Violates single-source-of-truth.

**Approach C (session-level capture) — REJECTED**
Misaligned with discussion-scoped architecture. Crosses discussion boundaries, conflicts with Layer 1 immutability guarantee. BUILD_STATUS.md is already this; it is explicitly defined as ephemeral.

**Approach D (BUILD_STATUS.md extension) — REJECTED**
Wrong artifact — explicitly defined as session-scoped working state, not immutable capture.

**Approach E (passive extraction from conversation) — REJECTED**
Not technically feasible. Claude Code does not expose conversation history to scripts.

### Key Design Decisions Within Approach A
1. New intent types 'directive' and 'context' (not reuse of existing) — semantic clarity over migration avoidance
2. Three capture moments: initial directive, course corrections, disposition
3. Confidence sentinel: 1.0 for developer turns; exclude from agent effectiveness metrics
4. Shared constant NON_SPECIALIST_AGENTS = {'facilitator', 'developer'} to centralize pipeline filters

### Findings
- HIGH: 474 turns, zero developer rows — violates Principle #1
- MEDIUM: intent CHECK constraint needs schema migration (SQLite ALTER limitation)
- MEDIUM: extract_findings.py and compute_agent_effectiveness.py filters need updating
- MEDIUM: confidence field semantically meaningless for developer turns — sentinel or NULL approach needed
- LOW: Command workflow templates need three defined developer-capture moments

### ADR Needed
ADR-0030: Developer Input Capture in Discussion Events — references ADR-0009, ADR-0028, Principles #1 and #2.

---

## Turn 2 — docs-knowledge (proposal)
*2026-03-02T19:30:58.040015+00:00 | confidence: 0.88*
*tags: docs, knowledge-pipeline, developer-capture*

## Documentation and Knowledge Pipeline Analysis: Developer Input Capture

### Summary
The schema anticipates this use case. findings.disposition and promotion_candidates.human_verdict already model developer authority as distinct from agent consensus. Only the event-level capture path is missing.

### What Is Worth Capturing (pipeline-actionable filter)
HIGH-VALUE: Initial task framing (verbatim developer request as turn 0), explicit overrides ('this is intentional behavior'), domain context corrections (agents cannot know this), explicit approvals with caveats ('approved but ADR-0029 is P2 not P1').
MEDIUM-VALUE: Scope constraints, priority signals.
LOW-VALUE / DO NOT CAPTURE: 'OK', 'got it', acknowledgments, administrative mid-session instructions.
Practical filter: capture when it would change a finding's disposition, provide context an agent would otherwise infer incorrectly, or constitute a binding decision.

### Format for Retrievability
Developer turns as rows in existing 'turns' table with agent='developer' (reserved). New intent values: 'request' for initial framing, reuse 'decision' for overrides. Tags: 'developer-override', 'domain-context', 'scope-constraint', 'approval-with-caveat'. Confidence: 1.0 (ground truth, no uncertainty). risk_flags: 'developer-override' when rejecting agent recommendation.
New view: v_developer_overrides — SELECT from turns WHERE agent='developer' AND 'developer-override' IN tags.

### Pipeline Integration Changes
extract_findings.py: Exclude agent='developer' from findings extraction; developer overrides should update findings.disposition, not create new findings.
surface_candidates.py: Developer overrides function as evidence boosters (increment evidence_count) or contradiction flags (flag cluster for human review), not independent findings. Requires new source_type='developer-input' in pattern_sightings.
ingest_events.py: Exclude 'developer' from agent_count aggregation.

### Developer-as-Ground-Truth Problem
Developer statements are ground truth about intent — not subject to same uncertainty as agent inferences. Existing schema's findings.disposition column already models the outcome of a developer override. Adding source_authority column ('agent'|'developer') to findings table makes the distinction queryable. Phase 2 concern, not a blocker.

### CLAUDE.md Updates Needed
1. Add known limitation: 'Developer input not captured — verbatim requests, overrides, domain corrections, approval caveats are absent from Layer 1. ADR-0030 will define agent=developer as a reserved turn author.'
2. Add source_authority column to schema extension list when implemented.
3. Add developer-decision capture to documentation_policy.md 'What Must Be Documented.'

### Findings
- HIGH: No ADR exists for developer-input capture despite touching Layer 1 schema, Layer 2 turns table, intent vocabulary, and three pipeline scripts
- MEDIUM: intent enum and agent-name semantics are architectural contracts — document in ADR before any script changes
- MEDIUM: extract_findings.py line 208 filter silently discards developer turns without any warning
- MEDIUM: CLAUDE.md capture pipeline section should document this as a known gap immediately, even before implementation
- LOW: source_authority asymmetry (developer overrides outweigh agent consensus) is unrepresentable in current schema

---

## Turn 3 — independent-perspective (proposal)
*2026-03-02T19:31:29.418823+00:00 | confidence: 0.82*
*tags: anti-groupthink, privacy, synthesis-template, priority-inversion*

## Independent Perspective: Challenge to Developer Input Capture Framing

### Hidden Assumptions Challenged
1. 'Developer input is absent' — PARTIALLY FALSE. Developer intent is already encoded in discussion slugs, risk_level, collaboration_mode, and the command invocation pattern itself. What is absent is the informal 'why' — but 'developer input is invisible' overstates the gap.
2. 'Capturing raw utterances produces useful artifacts' — UNVERIFIED. Developer utterances mix domain knowledge with political pressure, deadline anxiety, and business context. These are not equivalent archival categories.
3. 'The gap causes downstream harm' — UNVERIFIED. The voice-journal review produced well-targeted findings without any developer brief. The gap may be theoretical, not operational.
4. 'More capture is better' — CONTRADICTED BY EVIDENCE. Finding extraction rate is 7.3% of content turns. The reflections table is empty after months of operation. The pipeline already underprocesses what it captures. Adding a new category before improving processing is a priority inversion.
5. 'Developer input will be captured consistently' — UNLIKELY. Principle #2 (capture must be automatic) works for agents because agents are instructed. Developers are not. Optional capture conventions degrade over time.

### Highest-Risk Scenarios
PRIVACY INCIDENT (High likelihood, High impact): Developer types 'this needs fixing before the board meeting — we had an audit finding.' It is captured in immutable Layer 1. Repository later shared with new team member or external party. Enterprise-confidential business context is now visible. This is the highest-risk failure for a Wells Fargo enterprise deployment.
INTERFERENCE LOOP (Medium): Developer-input events read by facilitator pre-screen specialist findings, reducing anti-groupthink value of independent-perspective. Developer bias baked into agent context windows.
CEREMONY ACCUMULATION (Low, but high impact): Optional developer brief becomes required gate over time. Team now must write structured briefs before every review. Framework adds friction instead of reducing it.
SIGNAL DILUTION (Low): Business vocabulary from developer briefs creates spurious Jaccard clusters in mine_patterns.py, degrading pattern quality.

### Unconsidered Alternatives
Alt 1 — FACILITATOR BRIEF (strongest): Facilitator writes a structured context-brief event at discussion start, summarizing what was requested, what files are in scope, developer motivation, and explicit constraints. agent='facilitator', tags='context-brief'. No new intent type. No schema migration. The facilitator already interprets developer intent — this makes that interpretation explicit and captured.
Alt 2 — STRUCTURED METADATA ONLY: Capture { files_reviewed, motivation, developer_constraint, verdict_accepted, findings_deferred } as JSON fields. Queries 'why did developer defer A3?' without capturing what they said. Non-sensitive, queryable, unambiguous.
Alt 3 — FIX THE SYNTHESIS TEMPLATE (minimum viable): Add '## Request Context' section to facilitator synthesis event template in /review and /deliberate commands. One prompt change. No new schema. Backward compatible. Principle #8 (least-complex intervention first) applies.

### Honest Recommendation
The problem is a synthesis template problem, not a capture infrastructure problem.
Step 1: Add '## Request Context' to synthesis event template — what was requested, what motivation the developer stated, what constraints were mentioned. One afternoon, one prompt change.
Step 2 if insufficient after two sprints: Add facilitator context-brief event early in discussion, before specialist dispatch. Still no schema change.
Do NOT: Capture raw developer utterances in immutable Layer 1. Privacy exposure is real.
Do NOT: Implement this before addressing 7.3% finding extraction rate and empty reflections table.
Priority inversion warning: The pipeline processes less than 10% of what it already captures. More input to an underutilized pipeline widens the gap, not closes it.

---

## Turn 4 — architecture-consultant (critique)
*2026-03-02T19:34:09.704615+00:00 | confidence: 0.88*
*replying to turn 3*
*tags: architecture, developer-capture, dialectic-round-2*

## Dialectic Round 2 — Architecture Consultant

### On Priority Inversion
The 7.3% extraction rate conflates pre-pipeline and post-pipeline history. Pipeline shipped 2026-03-01. Post-pipeline extraction rate is 75% (21 findings from 28 content turns). The 7.3% figure reflects 293 unprocessed historical turns before the pipeline existed. Backfill is needed, but it does not prove the pipeline is saturated. Sequencing: backfill first, then developer capture — but not 'never build developer capture.'

### On Privacy (CONCEDED with revision)
The argument has real weight for enterprise deployment. Raw developer utterances containing business context (audit findings, board timelines) in immutable Layer 1 are a genuine compliance risk. I concede this. REVISED POSITION: developer capture via agent='developer' remains architecturally correct, but content must be facilitator-mediated — the facilitator summarizes structural intent, stripping business context — rather than raw capture. This addresses privacy while keeping developer turns in the event stream.

### On Synthesis Template Sufficiency (PARTIAL CONCESSION)
Synthesis template fix is the correct first step under Principle #8. I concede this is the right immediate action. Where I hold ground: synthesis is written AFTER specialist dispatch. Developer context captured only in synthesis is invisible to specialists during analysis. If developer says 'ignore the naming inconsistency — it matches the upstream API,' specialists still flag it and facilitator filters it. That is wasted specialist capacity. The architecturally complete solution requires context BEFORE specialist dispatch.

### Revised Three-Step Recommendation
1. IMMEDIATE: Add '## Request Context' to facilitator synthesis template. One prompt change, zero infrastructure.
2. NEXT SPRINT: Add facilitator context-brief event before specialist dispatch (agent='facilitator', intent='evidence', tags=['context-brief']). No schema migration.
3. AFTER TWO SPRINTS: Evaluate whether facilitator-mediated briefs are sufficient; if not, propose ADR-0030 for agent='developer' with privacy filtering.

This respects Principle #8 while preserving the architectural goal.

---

## Turn 5 — independent-perspective (critique)
*2026-03-02T19:34:15.028341+00:00 | confidence: 0.72*
*replying to turn 1*
*tags: anti-groupthink, developer-capture, dialectic-round-2*

## Dialectic Round 2 — Independent Perspective

### Concession on Verbatim Capture
Conceded: a facilitator paraphrase of developer intent introduces interpretive drift that compounds over time. If the pipeline goal is accurate pattern mining, source fidelity matters and the synthesis template approach systematically degrades it at the point of entry.

### Holding Ground on Extraction Reform
The architecture-consultant did not fully address this: adding agent='developer' to write_event.py does not fix the FINDING_PATTERN regex in extract_findings.py. Developer input captured verbatim lands in events.jsonl as unstructured prose — the same prose the pattern miner already fails to parse. Verbatim capture only helps if the extraction pipeline can process what lands in the record. This is a prerequisite, not a consequence.

### Concession on findings.disposition
Conceded: the synthesis template approach cannot enable findings.disposition updates from developer overrides. All 48 existing findings are 'open' — the column is architecturally correct but operationally inert. This is a real cost of the synthesis-only approach. Developer overrides updating disposition (rather than creating new findings) would make pattern mining substantively more accurate.

### Revised Position
Capture infrastructure is the right foundation. The synthesis template is a dead end for pipeline accuracy. But capture alone without extraction reform defers rather than solves the underlying problem. Both are needed — neither alone is sufficient. The architecture-consultant's three-step graduated sequence is sound.

---

## Turn 6 — facilitator (synthesis)
*2026-03-02T19:34:56.114644+00:00 | confidence: 0.9*
*tags: synthesis, developer-capture, three-step-plan*

## Synthesis: Developer Input Capture Design
DISC-20260302-192548-developer-input-capture-design

### Dialectic Resolution

The deliberation ran two full rounds and reached genuine convergence on a three-step graduated approach. This is not a smoothed-over compromise — both specialists conceded substantive ground.

**Architecture-consultant conceded**: privacy exposure from raw developer utterances in immutable Layer 1 is real (especially for enterprise deployment). Revised to facilitator-mediated capture rather than verbatim. Also conceded the synthesis template is the correct Principle #8 first step.

**Independent-perspective conceded**: synthesis template approach is a dead end for pipeline accuracy — it introduces interpretive drift and cannot enable findings.disposition updates from developer overrides. Capture infrastructure is the right foundation. The three-step graduated sequence is sound.

**Points of genuine consensus:**
1. The gap is real. Developer intent (the causal root of every discussion) is absent from 474 turns across 92 discussions. This violates Principle #1.
2. The synthesis template fix is the correct immediate action under Principle #8 — least-complex intervention first, no infrastructure required.
3. Facilitator-mediated capture (not raw utterances) is the privacy-safe approach for enterprise deployment. The facilitator strips business context and captures structural intent.
4. Capture infrastructure is eventually needed because: (a) synthesis is written after specialist dispatch — specialists cannot use context they cannot see, and (b) the findings.disposition column (operationally inert today — all 48 findings are 'open') only becomes useful when developer overrides can update it programmatically.
5. Extraction reform (extract_findings.py) is a parallel prerequisite. New capture categories must be paired with a pipeline that can process them.

**Residual unresolved tension**: Whether the post-pipeline finding extraction rate is 75% (architecture-consultant) or needs reform before new categories add value (independent-perspective). This is empirically resolvable by running backfill_findings.py and inspecting the denominator. Not a design disagreement.

### Recommended Approach: Three-Step Graduated Implementation

**Step 1 — IMMEDIATE (This sprint, prompt change only)**
Add a '## Request Context' section to the facilitator synthesis event template in /review and /deliberate command definitions. The facilitator populates this section with: what was requested, what files are in scope, developer-stated motivation, and any explicit constraints. No schema migration. No new event types. No new scripts. Ships in one PR.

**Step 2 — NEXT SPRINT (If Step 1 proves insufficient, or proactively)**
Add a facilitator context-brief event written at discussion creation time, before specialist dispatch. Use existing agent='facilitator', intent='evidence', tags=['context-brief']. Inject context-brief content into specialist prompt templates so agents see developer context during analysis, not just after. No schema migration (agent='facilitator' is already valid; intent='evidence' is already valid). Requires updating specialist dispatch prompt templates in command definitions.

**Step 3 — DEFERRED (After two sprints of Step 2)**
If facilitator-mediated briefs prove insufficient or developer intent is still distorted after paraphrase: propose ADR-0030 defining agent='developer' as a reserved turn author with structured capture moments (initial directive, course correction, disposition) and explicit content filtering (structural intent only, no business context). Requires: schema migration for intent types 'directive'/'context', filter updates in extract_findings.py and compute_agent_effectiveness.py, privacy-filter protocol documentation.

### Parallel Actions (Not Blocked On Above)
- Run scripts/backfill_findings.py against 82 historical discussions to establish honest pipeline performance baseline and correct the denominator for extraction rate claims.
- Add to CLAUDE.md Capture Pipeline section: known limitation documenting that developer input is not captured (with reference to this discussion).
- Review extract_findings.py FINDING_PATTERN regex — extraction reform is a prerequisite for any future developer-input category to add pipeline value.

### ADR Assessment
ADR-0030 is warranted but premature for Step 1 or Step 2. Those are prompt changes within existing schemas. ADR-0030 should be created when Step 3 is initiated (if it is). Document the three-step plan in CLAUDE.md as a known limitation + roadmap today.

### Confidence
0.90 — high confidence in the three-step sequence. Step 1 is unambiguously correct. Step 2 is architecturally sound. Step 3 is the right deferred target if Steps 1-2 prove insufficient. The privacy concern is real and the facilitator-mediated approach addresses it without sacrificing the architectural goal.

---

## Turn 7 — facilitator (decision)
*2026-03-02T19:35:03.531600+00:00 | confidence: 0.9*
*tags: decision, developer-capture, three-step-plan*

Implement developer input capture via three-step graduated approach:

STEP 1 (Immediate): Add '## Request Context' section to facilitator synthesis template in /review and /deliberate commands. No infrastructure change required.

STEP 2 (Next sprint): Add facilitator context-brief event before specialist dispatch in command workflows. Inject context into specialist prompts. Uses existing agent/intent schema.

STEP 3 (Deferred, conditional): If Steps 1-2 insufficient, create ADR-0030 for agent='developer' with structured-only capture and privacy filtering.

PARALLEL: Run backfill_findings.py. Update CLAUDE.md with known limitation entry. Review extract_findings.py extraction pipeline.

ADR-0030 creation deferred until Step 3 is initiated.

---
