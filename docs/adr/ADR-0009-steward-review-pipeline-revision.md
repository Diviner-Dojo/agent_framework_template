---
adr_id: ADR-0009
title: "Review Pipeline Revision — Demote finding-validator and compliance-auditor to facilitator steps"
status: accepted
date: 2026-03-24
decision_makers: [steward, facilitator, developer]
discussion_id: null
supersedes: ADR-0007
risk_level: medium
confidence: 0.92
tags: [agents, review, steward-revision, pipeline, principle-8]
---

## Context

ADR-0007 introduced three new specialist agents (finding-validator, compliance-auditor, history-analyst) to extend the `/review` pipeline. After the v3.1 review pipeline enhancements were propagated to a downstream project (agentic_journal), the project's **Steward agent** performed a full philosophical evaluation of every proposed change against the framework's eight non-negotiable principles and PHILOSOPHY.md.

The Steward issued **REVISE** on the overall proposal, approving some elements and rejecting others. The developer accepted all Steward recommendations. The revised pipeline was implemented, tested, and committed in the downstream project. This ADR back-propagates those Steward-reviewed revisions to the canonical template.

## Steward Verdicts

### finding-validator — REVISE: Demote to facilitator step

The Steward found that finding-validator performs a mechanical verification procedure, not a specialist perspective. It reads a file at a reported location and says "confirmed" or "not confirmed." It has no specialist philosophy, does not bring a unique lens, and does not participate in dialogue. This is a verification procedure, not a peer agent.

**Principle violated:** #8 (Least-complex intervention first) — An agent is the most complex option for what is fundamentally a validation step. The facilitator already reads all specialist outputs. Before writing the synthesis, the facilitator can read the actual files at each reported finding location and filter demonstrably false findings.

**Resolution:** Removed `.claude/agents/finding-validator.md`. Finding verification is now a facilitator synthesis sub-step (Step 6.3 in `/review`).

### compliance-auditor — REVISE: Demote to rule injection

The Steward identified the same structural problem: the compliance-auditor reads rules and checks code against them — a checklist, not a perspective. Additional concerns:

- **Letter-vs-spirit rigidity:** When a specialist says "this violates rule 14 but serves the user better," the compliance-auditor has no framework for evaluating that trade-off.
- **Role overlap:** The docs-knowledge agent already has "Constitution Currency" as a core responsibility. A separate compliance-auditor dilutes that mandate.

**Principle violated:** #8 (Least-complex intervention first) — If there are specific review rules that agents consistently miss, encode them in REVIEW.md and inject them into all specialist prompts during `/review`. This is a prompt-level intervention — Principle #8's preferred layer.

**Resolution:** Removed `.claude/agents/compliance-auditor.md`. REVIEW.md content is now injected into ALL specialist dispatch prompts during `/review` using `<review-rules>` delimiters with prompt injection defense.

### history-analyst — APPROVE

The Steward found that history-analyst brings a genuinely distinct perspective: git history analysis (churn patterns, revert frequency, blame concentration, refactoring cadence) is a lens no current agent provides. It requires tool use, analytical judgment, and produces findings that change how the team evaluates risk.

**No changes.** History-analyst retained exactly as-is.

### Confidence filtering — REVISE: Replace with confidence annotation

The Steward identified confidence filtering as "the most philosophically dangerous element" in the proposal:

- **Principle #1** (Reasoning is the primary artifact): Filtering a finding with confidence 0.72 means the developer never sees the reasoning. The finding that was 0.72 confident but prophetic is lost.
- **Principle #4** (Independence prevents confirmation loops): Confidence filtering is facilitated suppression — the facilitator decides which specialist perspectives the developer sees.

**Resolution:** All findings are now presented. Low-confidence findings (< 0.80) are grouped in a "Speculative Findings — Lower Confidence" section. The developer sees everything with context and makes their own judgment.

### REVIEW.md — REVISE: Add subordination clause

REVIEW.md must explicitly declare subordination to prevent a shadow constitution:

> **In any conflict, CLAUDE.md and PHILOSOPHY.md govern.**

## Decision

1. **Remove finding-validator agent** — demote to facilitator synthesis sub-step
2. **Remove compliance-auditor agent** — demote to REVIEW.md rule injection into all specialist prompts
3. **Keep history-analyst agent** — approved without revision
4. **Replace confidence filtering with confidence annotation** — no findings suppressed
5. **Add REVIEW.md subordination clause** — explicit governance hierarchy
6. **Agent count: 14 → 12** (steward + facilitator + 10 specialists)

## Alternatives Considered

### Keep finding-validator and compliance-auditor as agents

- **Pros**: Stronger separation of concerns, independent verification
- **Cons**: Violates Principle #8 — agents are the most complex intervention for what are fundamentally a validation procedure and a checklist. The facilitator can perform verification as a synthesis sub-step, and rule compliance is better achieved by injecting rules into specialist prompts.
- **Reason rejected**: Steward evaluation found these are procedures, not perspectives

## Consequences

### Positive
- Agent roster is leaner (12 vs 14), reducing coordination overhead
- Principle #8 is better respected — simpler interventions for simpler tasks
- Principle #1 is better respected — no specialist reasoning is suppressed
- Principle #4 is better respected — no automated gate decides what the developer sees
- docs-knowledge's constitutional-review mandate is no longer diluted
- REVIEW.md has clear governance hierarchy

### Negative
- Finding verification is now the facilitator's responsibility — increases facilitator prompt complexity
- Rule compliance depends on specialists applying injected rules through their own lens — may miss violations that a dedicated auditor would catch

### Neutral
- Agent count decreases from 14 to 12 — requires documentation updates across CLAUDE.md, framework spec, and presentations
- ADR-0007 is superseded (not deleted, per Principle #5)

## Linked Discussion

Back-propagated from downstream project (agentic_journal) Steward evaluation.
Supersedes: ADR-0007
