---
synthesis_id: SYNTHESIS-20260515-adoption-brief-v3
date: 2026-05-15
supersedes: SYNTHESIS-20260515-adoption-brief-v2
sources:
  - SYNTHESIS-20260515-adoption-brief (v1, template-local only)
  - SYNTHESIS-20260515-adoption-brief-v2 (added agentic_journal/Insight Journal telemetry)
  - VerificationPortal telemetry (21-day window, 2026-04-06 → 2026-04-27)
purpose: Final deliberation brief — two derived projects + template signal, ready for /deliberate
---

# Adoption Synthesis v3 — Two-Project Recalibration

## What's New in v3

v2 reweighted v1 with one derived project. v3 adds a second (VerificationPortal). The cross-project pattern matters more than either dataset alone.

### Two-project convergences (Rule of Three nearly satisfied)

| Pattern | Insight Journal (90d) | VerificationPortal (21d) | Framework verdict |
|---|---|---|---|
| Disposition pipeline broken | ≤12.5% survival, 45% NULL command_type | 0% Layer 3 promotion, 50% NULL command_type | **Systemic framework gap, not project-local** |
| Education gate dead-letter | 2 retros + formalized bypass | 4 deferral references | **Framework gap — Principle #6 silently abandoned** |
| Checkpoint flag never fires | 0 across 342 discussions | 0 across 21 discussions | **Persistence bug or low-value protocol** |
| Local `conversation` + `status` commands | added | added | **Cross-project pattern — canonicalize** |
| Heavy facilitator load | 1708 dispatches | 72 dispatches (3x next agent) | **Token-cost target confirmed** |

### Two-project divergences (the right answer is "depends")

| Pattern | Insight Journal | VerificationPortal | Framework verdict |
|---|---|---|---|
| ux-evaluator value | 4th most-dispatched, distinct work | 0% uniqueness, retro-flagged | **Domain-tier the default dispatch — not blanket** |
| Top finding category | architecture (29%) | correctness (29%) | **No single "noise pattern" exists; tiered review panels needed** |
| Local agent additions | 0 | 4 (none used yet) | **VP's aspirational additions suggest forcing-function gap** |

## v3 Adoption Shortlist (Re-ranked with Two-Project Evidence)

### Tier 0 — Foundation (must precede anything else)

| # | Pattern / Fix | Why Tier 0 | Effort |
|---|---|---|---|
| 0a | **Fix capture pipeline disposition gap** (P1 from v2, now confirmed in 2 projects) | Adopting any "improve review quality" pattern is wasted while 50% of discussions have NULL `command_type` and ≤12.5% of findings survive. Build a debug script that traces a finding from generation → ingestion → promotion. | M |
| 0b | **Fix command_type naming drift** (hyphen-vs-underscore) | Same pipeline. AJ shows `analyze_project` vs `analyze-project`, `deliberate` vs `deliberation`, etc. Half the rows are unattributable. Migration + slug normalization in capture scripts. | S |
| 0c | **Decide checkpoint persistence vs relaxation** (P2 from v2, confirmed in 2 projects) | 0 flags across 363 combined discussions. Either Round-2 REVISE isn't being written to `state.json` or the protocol is producing zero value. RETRO-20260301 from IJ said relax. **Decide before adopting any new review pattern.** | S decision + S–M implementation |

### Tier 1 — Targets Confirmed Two-Project Pain Pattern

| # | Pattern | Source | Score | Confirmed By |
|---|---|---|---|---|
| 1 | **Risk/domain-tiered specialist dispatch** (replaces blanket panels) | VP retro + ECC False-Positive Taxonomy (adapted) | n/a (synthesized) | VP: "2 specialists instead of 4 would catch the same blockers at half the cost"; IJ: 178 reviews, ≤12.5% survival |
| 2 | **Rationalization Tables** | superpowers | 21/25 | Both projects: education gate bypass + 60d-old unresolved retro signal in IJ |
| 3 | **Verification-Before-Completion** | superpowers | 20/25 | Both projects: 0 checkpoint flags despite RETRO-naming low value (IJ); 83% advisory yield (VP) |
| 4 | **REFERENCE.md split for top-3 hot agents** | ruflo | 20/25 | IJ: facilitator (1708) + arch-consultant (568) + qa-specialist (519). VP: facilitator (72) + arch-consultant (34) + qa-specialist (34). Same top-3, both projects. |
| 5 | **Karpathy Principles 1–3** as agent-behavior-defaults | Karpathy | 21/25 | Architecture findings dominate both projects (29% IJ, 22% VP). Surgical Changes + Simplicity First target it pre-emptively. |

### Tier 2 — Cross-Project Local-Addition Promotion

| # | Pattern | Source | Rationale |
|---|---|---|---|
| 6 | **Canonicalize `conversation` command** | IJ + VP both added independently | 2-of-2 hit on the same local addition. Pattern is real. Hub should expose it. |
| 7 | **Canonicalize `status` command** | IJ + VP both added independently | Same logic. |

### Tier 3 — Pure Adoption, Confirmed by Pattern Convergence

| # | Pattern | Source | Score | Notes |
|---|---|---|---|---|
| 8 | **Agent Introspection Debugging** skill | ECC | 20/25 | Pure guidance; complements failure_taxonomy.md |
| 9 | **Context Budget Audit** (one-time) | ECC | 19/25 | Both projects show facilitator + arch-consultant + qa-specialist as load-bearers |
| 10 | **`/insights` adoption per project** | CC survey | High-value | Manual today; OTEL fixes long-term |

### Demoted from v1/v2 (solves the wrong problem)

| # | Pattern | v1 Score | Why demoted |
|---|---|---|---|
| — | ECC **False-Positive Taxonomy** verbatim | 24/25 | AJ uniqueness ≈ 1.0; VP uniqueness 0.82–0.87 across agents. Findings aren't noisy, they're orphaned. Adopt the spirit (risk/domain-tiered dispatch — see Tier 1 #1), not the literal taxonomy. |
| — | **Two-Stage Review** (spec → quality) | 21/25 | Doubles review cost. AJ already runs 178 reviews; doubling them while 87% of findings don't survive is upside-down economics. Re-evaluate after Tier 0 lands. |
| — | **Santa Method context isolation** | 21/25 | Same logic as Two-Stage — adds cost. Defer until disposition pipeline is healed. |

## Education Gate — Framework-Level Decision Required

Two projects, two different bypass patterns:
- IJ: bypass formalized in `autonomous_workflow.md` ("third time is not an anomaly — it is the actual process")
- VP: 4 deferrals in 21 days, no formalization

**Options for the deliberation:**

1. **Structural enforcement** — block commit, no override. Principle #6 honored, friction maximized.
2. **Risk-tiered** — block on HIGH/CRITICAL only, opt-out otherwise.
3. **Acknowledged opt-out** — declare a "no education gate" workflow class with documented rationale. Principle #6 amended.
4. **Defer the framework decision** — fix Tier 0 first, see whether better disposition changes the math.

Recommendation: **option 4** unless the deliberation surfaces a stronger argument.

## Open Conflicts for Deliberation

1. **VP's panel-size question (literal)**: "Would 2 specialists instead of 4 catch the same 3 blockers at half the cost?" Tier 1 #1 is the synthesized answer; the deliberation should ratify or counter it.
2. **Is `conversation`/`status` canonicalization premature** if only 2 projects have adopted them and we don't have Howie data yet?
3. **IJ retro from 60+ days ago said relax checkpoint protocol**. Honor the stale signal or investigate first? Tier 0 #2c.
4. **Skill description philosophy** (open from v1): obsidian-cli-skill says descriptions = routing classifiers with explicit triggers; superpowers says descriptions = triggers ONLY (workflow summaries become shortcuts). Resolve.
5. **The "external-input command class" framing**: is the `conversation`/`status` pattern a general external-input class (Tier 2 #6/#7 are the lightweight version), or a one-off generalization?

## Framework Problems With No External-Repo Solution

Listed for completeness — these are framework-internal work items:

- **P1 — Capture pipeline disposition gap** (Tier 0 #0a)
- **P2 — Checkpoint flag persistence** (Tier 0 #0c)
- **P3 — Education gate dead-letter** (decision above)
- **P4 — Retro cadence decay** (IJ: last on-disk retro 60+ days ago)
- **P5 — Naming drift in capture pipeline** (Tier 0 #0b)
- **P6 — VP added 4 aspirational agents that never fire** — forcing-function or retirement decision

## Deliberation Question (v3)

> Given (a) Tier 0 foundational fixes that must precede any pattern adoption, (b) Tier 1–3 ranked adoptions backed by two-project evidence, (c) 6 framework-internal problems no external repo solves, and (d) 5 open conflicts including one literal question from a derived-project retro — produce a sequenced adoption plan, resolutions for all conflicts, and surface anything the synthesis missed.

Expected outputs:
- A 3-tier sequenced plan (Tier 0 → Tier 1 → Tier 2/3) with effort, dependencies, and risk
- Resolutions for all 5 open conflicts
- A verdict on whether `conversation`/`status` canonicalization should wait for a third project's data
- A verdict on education gate framework policy
- A meta-finding: anything in the v3 brief that's miscalibrated or missing

## Notes for the Deliberation Facilitator

- All source reports at `docs/analysis/ANALYSIS-20260515-*.md`
- v1 and v2 briefs are superseded by this v3
- Two-project denominator is the load-bearing change since v1 — agents should read both projects' telemetry blocks before re-scoring
- 3 of the 7 source reports were recovered from agent return values (project-analyst write-block hallucination). Decision content preserved; per-pattern line citations partially lost.
- Third derived project (Howie Family Wiki) does not yet exist — Rule of Three across derived projects cannot be fully validated until it does. Several findings sit at "two-project pattern" which is strong but not yet rule-of-three.
