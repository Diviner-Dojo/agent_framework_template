---
synthesis_id: SYNTHESIS-20260515-adoption-brief-v2
date: 2026-05-15
supersedes: SYNTHESIS-20260515-adoption-brief
sources:
  - SYNTHESIS-20260515-adoption-brief (v1, template-local signal only)
  - Derived-project telemetry from agentic_journal (Flutter/Dart ADHD-informed journal app, 90-day window)
purpose: Recalibrated deliberation brief — hub-vs-spoke denominator now included
---

# Adoption Synthesis v2 — Recalibrated with Derived-Project Telemetry

## What Changed from v1

v1 evaluated 30+ patterns using template-local signal only. v2 incorporates 90-day telemetry from agentic_journal:
- 1,708 facilitator turns, 568 architecture-consultant, 519 qa-specialist, 260 ux-evaluator, 254 security-specialist
- 178 `/review` runs, 114 `/build_module` runs, 23 `/analyze_project`, 15 `/deliberate`, 10 `/retro`
- 228 findings across 6 categories (architecture-dominant: 66, then testing 48, ux 41)

**The data flipped four v1 conclusions and added three new framework-level problems no external repo addresses.**

## Conclusion Flips from v1

| v1 conclusion | v2 conclusion | Evidence |
|---|---|---|
| `ux-evaluator` underused, possibly retire | **4th most-used agent** (260 dispatches). Critical to derived projects. v1 was template-local bias. | top_5_agents_by_dispatch |
| `history-analyst` underused | Correctly rare — only fires on `/review --deep`. Not a flaw. | trigger model + 3 dispatches |
| ECC False-Positive Taxonomy is top pick (24/25) | **Demoted** — solves noise problem AJ doesn't have. Findings are distinct (uniqueness ≈ 1.0); they're orphaned, not noisy. | survival ≤ 12.5%, uniqueness ≈ 1.0 |
| Education gates: enforce or audit | **Dead-letter in this project**. Bypass is formalized in `autonomous_workflow.md`. Decision: structural (block commit) or accept ADHD opt-out — not "audit". | 2 retros + 1 walkthrough + 1 quiz in 90 days |

## v2 Adoption Shortlist (Re-ranked by Evidence-Adjusted Value)

### Tier 1 — Targets a Confirmed Pain Pattern

| # | Pattern | Source | Score | Confirms |
|---|---|---|---|---|
| 1 | **Rationalization Tables** (`Excuse \| Reality`) | superpowers | 21/25 | AJ's 2 retros + formalized education-gate bypass = exactly the bypass culture this pattern targets |
| 2 | **Verification-Before-Completion** gate | superpowers | 20/25 | AJ's 0 unresolved-checkpoint despite 60+ day-old "low value" retro flag — completion claims aren't being verified |
| 3 | **REFERENCE.md split** for top-3 token-heavy agents | ruflo | 20/25 | facilitator (1708), architecture-consultant (568), qa-specialist (519) — real token surface. 40% reduction × volume = measurable cost recovery via ADR-0013 telemetry |
| 4 | **Karpathy Principles 1–3** as agent-behavior-defaults | Karpathy | 21/25 | Architecture findings are 29% of all findings → over-architecting is real. Surgical Changes + Simplicity First target it pre-emptively |

### Tier 2 — Solid Adoption, Confirmed by Pattern Convergence

| # | Pattern | Source | Score | Notes |
|---|---|---|---|---|
| 5 | **Agent Introspection Debugging** skill | ECC | 20/25 | Pure guidance. Fills `failure_taxonomy.md` gap for in-flight reasoning failures |
| 6 | **Santa Method context isolation** (HIGH/CRITICAL only) | ECC | 21/25 | Affects 3 critical findings (`process` category) — narrow scope, low cost |
| 7 | **`/insights` adoption** across all 4 (?) projects | CC survey | High-value | Cross-project aggregation requires manual run today; OTEL fixes that long-term |

### Tier 3 — Demoted from v1 (solves wrong problem here)

| # | Pattern | Source | v1 Score | Why demoted |
|---|---|---|---|---|
| — | ECC **False-Positive Taxonomy** | ECC | 24/25 | AJ findings aren't noisy (uniqueness ≈ 1.0). Adopt only AFTER the disposition pipeline is fixed; without that, this pattern increases survival of zero findings |
| — | **Two-Stage Review** (spec → quality) | superpowers | 21/25 | AJ already has 178 `/review` runs at high cost. Sequential dispatch would 2× that without addressing the survival problem |

## New Framework-Level Problems (No External Repo Addresses)

These are now **first-class deliberation items** alongside the external-repo adoptions:

### P1 — Capture Pipeline Disposition Gap  **[HIGH]**

- **Symptom**: ≤12.5% finding survival across all agents; 45% NULL `command_type`
- **Root cause hypothesis**: `extract_findings → mine_patterns → surface_candidates → /retro → /promote` is broken or under-run downstream. /retro itself has decayed (last on-disk RETRO 60+ days ago).
- **Impact**: Agents look low-value when their work is actually being captured and discarded. False signal for retro and meta-review.
- **Adjacent**: hyphen-vs-underscore inconsistency in `command_type` field (`analyze_project` vs `analyze-project`, `deliberate` vs `deliberation`, `build_module` vs `build`)

### P2 — Checkpoint Protocol Persistence Gap  **[HIGH]**

- **Symptom**: 0 `unresolved-checkpoint` flags across 342 discussions despite 114 `/build_module` runs
- **Two interpretations**: (a) protocol works perfectly (refuted by RETRO-20260301 calling it low-value 60+ days ago), (b) Round-2 REVISE outcomes aren't being written to `state.json`
- **Decision needed**: write a structural test that the flag CAN fire, OR relax the protocol per RETRO-20260301's 7-month-old recommendation
- **Framework principle pressure**: this is exactly the kind of low-value-protocol-that-runs-anyway that Principle #8 warns against

### P3 — Education Gate as Dead-Letter  **[MEDIUM]**

- **Symptom**: 1 walkthrough + 1 quiz in 90 days; 2 retros explicitly named the bypass; `autonomous_workflow.md` formalizes it
- **Reality**: Principle #6 ("Education gates before merge") is silently abandoned in this project
- **Decision needed**: structural (block commit), risk-tiered (only above HIGH), or acknowledged opt-out (workflow class declares "no education gate" with documented reason)
- **Quote from RETRO-20260220**: "third time is not an anomaly — it is the actual process"

### P4 — Retro Cadence Decay  **[MEDIUM]**

- **Symptom**: last on-disk RETRO is RETRO-20260318 (~60 days ago); DB shows 10 retros in 90 days but no recent on-disk files
- **Implication**: the framework's *learning loop* is partially broken — discussions accumulate but don't get distilled into retros, which don't get distilled into promoted memory, which doesn't influence future agent calibration

### P5 — Template Lacks "External-Input" Command Class  **[OPPORTUNITY]**

- **Symptom**: AJ's 5 local command additions (`conversation`, `feedback-review`, `journal-review`, `status`, `watcher`) all cluster around external-data-ingestion + status-surfacing
- **Question for deliberation**: Should the template grow a generic external-input command class, or is each derived project's pattern too project-specific to canonicalize?

## v2 Adoption Path (Effort-Ordered Within Tier)

```
Week 1 (S effort, immediate wins):
  ├── Adopt Rationalization Tables in commit/autonomous/build-review rules
  ├── Adopt Verification-Before-Completion as new rule
  ├── Adopt Karpathy Principles 1–3 as agent-behavior-defaults
  └── Adopt Agent Introspection Debugging as new skill

Week 1 (S effort, framework-internal):
  ├── Investigate P1 capture-pipeline disposition gap (debug script first)
  ├── Investigate P2 checkpoint flag persistence (verify code path)
  ├── Fix command_type naming drift (rename + migration)
  └── Add structural test that unresolved-checkpoint flag can fire

Week 2 (M effort):
  ├── REFERENCE.md split for facilitator + architecture-consultant + qa-specialist
  ├── Santa Method context isolation for HIGH/CRITICAL reviews
  ├── Context Budget Audit (one-time session)
  └── Education Gate policy decision (structural OR acknowledged opt-out) — needs developer decision

Week 3+:
  └── /insights + OTEL adoption across all derived projects
```

## Open Questions for Deliberation

1. **The False-Positive Taxonomy question**: should this still be adopted even though AJ data demotes it? Argument for: the pattern is universally good; argument against: scarce attention should target P1/P2 first.

2. **The Two-Stage Review question**: same as above. AJ runs 178 reviews in 90 days — doubling that dispatch cost may not justify the quality gain *until* findings start surviving.

3. **The "external-input command class" question (P5)**: is `conversation`/`feedback-review`/`journal-review`/`status`/`watcher` a real pattern, or just one project's local solution to a specific need?

4. **The education-gate question (P3)**: structural, risk-tiered, or acknowledged opt-out? This is a Principle #6 amendment.

5. **The checkpoint-protocol question (P2)**: RETRO-20260301 said relax. Do we honor a 60+ day-old retro signal, or investigate first?

6. **The "agentic_journal" vs "Insight Journal" naming**: the telemetry came from `agentic_journal` — is that a synonym for Insight Journal in user memory, or a third derived project the hub didn't know about?

## Deliberation Question (Recalibrated)

> Given (a) 4 confirmed-pain-pattern adoptions from external repos that target documented AJ symptoms, (b) 5 framework-level problems no external repo addresses, and (c) 2 demoted v1 candidates that may still be worth adopting later — what is the highest-leverage *sequenced* adoption plan that also resolves the 5 open questions above?

Expected outputs from the deliberation:
- Sequenced adoption plan (week 1 / week 2 / week 3+) with effort and dependencies
- Resolutions for the 5 open questions
- A verdict on whether to fix the capture pipeline BEFORE adopting any pattern that depends on it (False-Positive Taxonomy, Two-Stage Review)
- Surfacing any pattern the synthesis missed

## Notes for the Deliberation Facilitator

- Source reports at `docs/analysis/ANALYSIS-20260515-*.md`
- v1 brief at `docs/analysis/SYNTHESIS-20260515-adoption-brief.md` (superseded by this v2)
- AJ telemetry data is the load-bearing reweighting — agents should read it before re-scoring
- 3 of the 7 source reports were recovered from agent return values (project-analyst write-block hallucination). Decision content preserved; per-pattern line citations partially lost.
