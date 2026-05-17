---
synthesis_id: SYNTHESIS-20260515-adoption-brief
date: 2026-05-15
sources:
  - ANALYSIS-20260515-claude-code-feature-survey
  - ANALYSIS-20260515-andrej-karpathy-skills
  - ANALYSIS-20260515-obsidian-cli-skill
  - ANALYSIS-20260515-open-design
  - ANALYSIS-20260515-ruflo
  - ANALYSIS-20260515-everything-claude-code
  - ANALYSIS-20260515-superpowers
purpose: Deliberation brief — what the 12-agent panel should weigh in on
---

# Adoption Synthesis — Deliberation Brief

## Premise

Seven parallel research streams (1 Claude Code feature survey + 6 external repo analyses) produced 30+ scored patterns. This brief consolidates the **cross-cutting convergences**, **adoption-ready patterns**, and **open conflicts** for the 12-agent deliberation.

## Cross-Cutting Convergences (Rule of Three+ triggers)

### Theme 1 — Review Noise / False Positives  **[3 sightings]**

| Source | Pattern | Score |
|---|---|---|
| ECC | False-Positive Taxonomy on `code-reviewer.md` (Pre-Report Gate, "zero findings is valid") | **24/25** |
| superpowers | Two-Stage Review (spec compliance before code quality) | 21/25 |
| superpowers | Rationalization Tables (`Excuse \| Reality`) | 21/25 |

All three address the same failure mode: **LLM reviewers produce unbacked findings that erode trust**. The framework currently has no Pre-Report Gate, no spec-vs-quality separation, and no rationalization counters.

### Theme 2 — Behavioral Constraints Before Code Generation  **[3 sightings]**

| Source | Pattern | Score |
|---|---|---|
| Karpathy | Think Before Coding / Simplicity / Surgical Changes | 21/25 |
| superpowers | Verification-Before-Completion gate | 20/25 |
| ECC | Agent Introspection Debugging | 20/25 |

All three address pre-emptive vs post-hoc discipline. The framework currently catches issues at `/review` time, not at generation time. **No instruction exists** to surface assumptions, resist speculative abstractions, or verify before claiming completion.

### Theme 3 — Token / Context Discipline  **[4 sightings]**

| Source | Pattern | Score |
|---|---|---|
| CC survey | `/insights`, OTEL, audit underused agents (ux-evaluator, history-analyst) | High value |
| ruflo | REFERENCE.md split (40% per-spawn token reduction) | 20/25 |
| ECC | Context Budget Audit methodology | 19/25 |
| obsidian-cli-skill | Description-as-classifier | 19/25 |

All four address the same hidden cost: **agent frontmatter loads on every Task dispatch**. We have ADR-0013 telemetry but no audit methodology and no description-routing discipline. **Strongest convergence in the synthesis.**

### Theme 4 — Skill Description as Routing Instruction  **[3 sightings]**

| Source | Pattern |
|---|---|
| obsidian-cli-skill | Description = activation classifier with explicit triggers + exclusions + discrimination principle |
| superpowers | CSO (description = triggering conditions only, NOT workflow summary) |
| Karpathy | Description = semantic activation hint |

Convergence with **internal conflict**: obsidian-cli-skill says description should be a routing classifier; superpowers warns that any description that summarizes workflow becomes a shortcut Claude follows instead of the full skill. Deliberation should resolve.

## Adoption-Ready Shortlist (Strong Adopt, ≥ 20/25)

| # | Pattern | Source | Score | Effort | Slot |
|---|---|---|---|---|---|
| 1 | False-Positive Taxonomy on specialist agents | ECC | **24/25** | S | Edit qa-specialist, architecture-consultant, security-specialist |
| 2 | Karpathy Principles 1–3 as agent-behavior-defaults | Karpathy | 21/25 | S | New `.claude/rules/agent-behavior-defaults.md` |
| 3 | Two-Stage Review (spec → quality) | superpowers | 21/25 | S | Augment `build_review_protocol.md` |
| 4 | Rationalization Tables | superpowers | 21/25 | S | Augment commit/autonomous/build-review rules |
| 5 | Santa Method context isolation (HIGH/CRITICAL only) | ECC | 21/25 | S | `review_gates.md` + facilitator |
| 6 | REFERENCE.md split for token-heavy agents | ruflo | 20/25 | S–M | architecture-consultant, independent-perspective, docs-knowledge |
| 7 | Agent Introspection Debugging skill | ECC | 20/25 | S | New `.claude/skills/agent-introspection/` |
| 8 | Verification-Before-Completion rule | superpowers | 20/25 | S | New `.claude/rules/verification_before_completion.md` |
| 9 | `/insights` + OTEL + `/team-onboarding` | CC survey | High value | S–M | Workflow change (not a file change) |

**All 9 are documentation/prompt changes.** Zero code. Zero ADR required (Karpathy principles may warrant an ADR for adoption rationale).

## Adopt-As-Practice (not file changes)

- **Context Budget Audit** (ECC, 19/25) — one-time audit session of CLAUDE.md, agent frontmatter, MCP schemas. Potential 5K–20K token recovery.
- **Five-State Coverage Checklist** (open-design, 19/25) — adapt into `ux-evaluator` Domain Lens.

## Defer / Conditional

| Pattern | Source | Score | Trigger to revisit |
|---|---|---|---|
| Rules Distill automation | ECC | 19/25 | Skill count hits 25+ |
| Prompt Defense Baseline (broad) | ECC | 19/25 | Adding agents that process external content |
| Skill-Comply (subprocess measurement) | ECC | 16/25 | Rule-of-Three finding fires for a rule that should have caught it |
| Confidence-Scored Instinct automation | ECC | 17/25 | Never — violates Principle #7. Adopt format only. |
| Given/When/Then in `/plan` | ruflo | unscored | Optional cosmetic; bundle with a `/plan` template refresh |
| Budget alert ladder | ruflo | unscored | When ADR-0013 telemetry has ≥ 1 month of data |
| TDD for documentation | superpowers | unscored | High effort; defer |
| Layered CLAUDE.md hierarchy | open-design | unscored | When root CLAUDE.md exceeds working-memory load |

## Open Conflicts for Deliberation

### Conflict 1 — Sequential vs Parallel Review

- **superpowers** argues for sequential review (spec → quality) for ordering enforcement
- **Our current model** is parallel dispatch for cost efficiency
- **Resolution candidate**: sequential for HIGH/CRITICAL; parallel for medium

### Conflict 2 — Skill Description Philosophy

- **obsidian-cli-skill**: description should be a routing classifier with explicit triggers + exclusions
- **superpowers**: description should be triggering conditions ONLY, never workflow summary — workflow summary becomes a shortcut Claude follows instead of the full skill
- **Anthropic best practices** (embedded in superpowers repo): description = what + when
- **Resolution candidate**: superpowers framing — descriptions name triggers, not workflows

### Conflict 3 — Automated Promotion vs Principle #7

- **ECC continuous-learning-v2** automates Layer 3 promotion based on confidence + cross-project frequency
- **Our Principle #7**: Layer 3 promotion requires human approval
- **Resolution candidate**: adopt the data model (trigger / confidence / domain / evidence), reject the automation. Use it as a richer queue for human gate review.

### Conflict 4 — Cost vs Independence in Reviews

- **Santa Method (ECC)**: fresh agents, no shared context, each round — costly but architecturally pure
- **Our Structured Dialogue mode**: specialists can read facilitator's prior synthesis — cheaper, may erode independence
- **Resolution candidate**: context isolation for HIGH/CRITICAL only

## Underused Agent Investigation

The CC feature survey flagged **`ux-evaluator`** and **`history-analyst`** as partially used. The open-design analysis suggests a concrete enrichment for `ux-evaluator` (Five-State Coverage). The deliberation should consider:

- Is `ux-evaluator` under-dispatched or under-relevant?
- Is `history-analyst` under-dispatched because `/review --deep` is rarely used?
- Should agents that don't earn their context cost be retired?

## Deliberation Question

**For the 12-agent panel:**

> Given 9 adoption-ready patterns (most scoring ≥ 20/25, all prompt-level changes), four open conflicts, and two underused agents — what is the highest-leverage adoption sequence to improve coding results, and what should be deferred or declined?

Expected outputs from the deliberation:
- A prioritized adoption sequence with effort estimates
- Resolutions for the four open conflicts
- A verdict on the two underused agents (improve / retire / leave alone)
- Surfacing any pattern that didn't make this synthesis but should have

## Notes for the Deliberation Facilitator

- All 7 source reports are at `docs/analysis/ANALYSIS-20260515-*.md`
- 3 of the 7 reports were recovered from agent summaries (project-analyst agents repeatedly hallucinated a "write block"). Decision content is preserved; some per-pattern line citations were lost. **This is itself a finding worth surfacing in the deliberation.**
- This brief is the canonical input — agents should read it first, then drill into specific ANALYSIS files as needed.
