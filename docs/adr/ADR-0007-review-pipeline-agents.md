---
adr_id: ADR-0007
title: "Introduce review-pipeline agents: finding-validator, compliance-auditor, history-analyst"
status: superseded
date: 2026-03-16
decision_makers: [facilitator, architecture-consultant, docs-knowledge, security-specialist, qa-specialist, compliance-auditor]
discussion_id: DISC-20260316-205136-review-sprint1-sprint2-release-prep
supersedes: null
superseded_by: "ADR-0009 — Steward revision: finding-validator demoted to facilitator step (Principle #8), compliance-auditor demoted to rule injection (Principle #8, role overlap with docs-knowledge). history-analyst retained."
risk_level: medium
confidence: 0.87
tags: [agents, review, validation, compliance, pipeline]
---

## Context

The v3.0 framework (ADR-0005) refined the existing 11-agent roster with enhanced specialist philosophies and collaboration protocols, maintaining the same agent count. However, the `/review` command's pipeline had three structural gaps identified through practical use and analysis of the DIY Code Review Blueprint v2.1:

1. **No finding verification**: Specialists reported findings but nothing independently checked whether those findings existed in the actual code. False positives eroded developer trust in review output.
2. **No rule compliance auditing**: CLAUDE.md and `.claude/rules/` encode project standards, but no agent specifically verified adherence with evidence. Compliance was assessed informally by whichever specialist happened to notice a violation.
3. **No git history context**: Reviews assessed code at a point in time without awareness of churn patterns, recent refactors, reverted changes, or authorship concentration — signals that indicate fragile or unstable code.

ADR-0006 (REVIEW.md convention) introduced review-time-only rules and noted "a compliance-auditor agent (ADR pending, part of the same sprint)" — acknowledging the need for a dedicated compliance enforcement agent.

## Decision

Introduce three new specialist agents that extend the `/review` pipeline with post-dispatch verification, compliance enforcement, and historical context:

### 1. Finding Validator (Sonnet tier)

**Role**: Independently verifies bug and security findings against actual code. Acts as a false-positive filter between specialist dispatch and facilitator synthesis.

**Position in pipeline**: After all specialists report, before confidence filtering. Receives findings as structured JSON objects with defined fields (severity, location, description, code_reference). Returns validation results with confidence scores.

**Key design choices**:
- Conservative filtering: when uncertain, retains the finding (err toward false negatives in filtering)
- Compliance findings from the compliance-auditor are pre-validated trivially (confidence 0.99) because they include exact rule quotation as built-in evidence
- Failure mode: if the validator errors, all findings proceed as "unvalidated" — the review is never blocked by validator failure

**Tools**: Read, Glob, Grep, Bash — needs code access for verification but no write capability.

### 2. Compliance Auditor (Sonnet tier)

**Role**: Audits code changes against CLAUDE.md and REVIEW.md rules with exact rule quotation. Every violation must cite the specific rule text being broken.

**Position in pipeline**: Dispatched alongside other specialists (parallel). Its findings flow through the finding-validator like all others, though with trivial confirmation.

**Key design choices**:
- Exact quotation required: vague references like "this violates coding standards" are rejected as findings
- No interpretation: reports what rules say, not what they should say
- REVIEW.md content is wrapped in XML delimiters with explicit prompt-injection defense framing
- No Write/Edit tools: an auditor must not modify the code it audits (integrity boundary)

**Tools**: Read, Glob, Grep — read-only access for rule lookup and code comparison.

### 3. History Analyst (Sonnet tier)

**Role**: Surfaces git history patterns for files under review — churn frequency, recent refactors, reverted changes, bug fix patterns, and authorship concentration.

**Position in pipeline**: Dispatched only when `--deep` flag is used (opt-in). Provides contextual intelligence that helps other specialists and the facilitator calibrate risk.

**Key design choices**:
- Deep mode only: adds latency and is most valuable for high-risk reviews, so it's gated behind `--deep`
- History only: reports what git history shows, does not judge code quality
- Privacy-aware: reports author counts and concentrations but does not make judgments about individuals
- Graceful degradation: if a git command fails (shallow clone, missing history), notes the limitation and skips that analysis

**Tools**: Read, Glob, Grep, Bash — needs Bash for git log/blame commands.

### Model Tier Rationale

All three agents use Sonnet tier, consistent with the cost optimization rationale in `build_review_protocol.md`:
- Finding-validator performs evaluation, not generation — consistent, focused verification
- Compliance-auditor performs rule matching with exact quotation — structured, bounded task
- History-analyst runs git commands and summarizes output — data gathering, not deep reasoning

The facilitator may override to Opus for exceptionally complex reviews per the standard model-override policy.

### Bidirectional Coupling

The finding-validator and compliance-auditor have an intentional behavioral coupling: the validator recognizes compliance findings (by `agent: "compliance-auditor"` tag) and confirms them trivially rather than re-verifying rule quotations. The compliance-auditor's definition references this behavior. This coupling is a pragmatic design choice — these agents were designed as a unit within the review pipeline. Future changes to either agent's output format must account for this dependency.

## Alternatives Considered

### Alternative 1: Fold validation into the facilitator

- **Pros**: No new agents, simpler pipeline, fewer dispatches
- **Cons**: The facilitator already orchestrates the entire review workflow. Adding finding verification to its responsibilities would violate Principle #4 (the code generator should not be the sole evaluator) — the facilitator synthesizes findings and would be both judge and verifier. Also increases facilitator prompt size.
- **Reason rejected**: Independence is the core value proposition. A separate validator provides genuine independent verification.

### Alternative 2: Have each specialist self-validate

- **Pros**: No new agent, validation happens inline
- **Cons**: Violates Principle #4 directly — the agent that found the issue would verify its own finding. Self-validation cannot catch hallucinated code references or location errors.
- **Reason rejected**: Self-validation is not validation.

### Alternative 3: Single "review-hardening" agent combining all three roles

- **Pros**: One agent instead of three, simpler dispatch
- **Cons**: Three distinct skill domains (code verification, rule compliance, git history analysis) in one agent would create a generalist that does none well. The tools needed differ (compliance needs read-only, history needs Bash for git). Violates the framework's specialist-per-domain architecture.
- **Reason rejected**: Specialist separation produces better results per ADR-0005's philosophy. Three focused agents outperform one broad one.

### Alternative 4: Make history analysis always-on (no --deep flag)

- **Pros**: Every review gets historical context
- **Cons**: Adds latency and cost to every review, even low-risk ones where history context provides marginal value. Git commands on large repos can be slow.
- **Reason rejected**: Proportional response — deep analysis for reviews that warrant it, not by default.

## Consequences

### Positive
- False positive rate in reviews decreases (finding-validator filters hallucinated or outdated findings)
- Rule compliance becomes machine-verifiable with exact quotation evidence
- High-risk reviews gain temporal context that point-in-time analysis misses
- Agent count (14) creates a comprehensive review pipeline with clear specialization

### Negative
- Three more agent definitions to maintain (definitions, anti-patterns, specialist philosophies)
- Finding-validator/compliance-auditor coupling creates a maintenance dependency between two peer agents
- Review command complexity increases (Steps 6.3-6.5 in the pipeline)
- Total review latency increases when all three are dispatched (mitigated by parallel dispatch and Sonnet tier)

### Neutral
- Agent count increases from 11 to 14, requiring CLAUDE.md and framework spec updates (completed)
- The `--deep` flag creates a two-tier review experience (standard vs. deep) that developers must learn

## Linked Discussion

See: discussions/2026-03-16/DISC-20260316-205136-review-sprint1-sprint2-release-prep/

Review report: docs/reviews/REV-20260316-205136.md
