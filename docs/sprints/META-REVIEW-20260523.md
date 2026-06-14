---
meta_review_id: META-REVIEW-20260523
status: draft
period: 2026-02-18 .. 2026-05-23 (full life of the derived-project corpus)
denominator: hub-lens (template + agentic_journal + VerificationPortal + howie_family_wiki)
---

# Quarterly Framework Evaluation (Macro / Double-Loop) — DRAFT

## Method note (the denominator correction)
This evaluation is run from the template hub, but the framework's ends are realized **downstream**.
Telemetry pulled across all four instances:

| Instance | Discussions | Turns | Active range | Role |
|---|---|---|---|---|
| agentic_journal | 657 | 3,915 | 2026-02-18 → today | mature workhorse (Flutter/Dart) |
| VerificationPortal | 25 | 201 | 2026-04-06 → 2026-05-16 | backend data-verification (quiet ~1wk) |
| howie_family_wiki | 11 | 94 | 2026-05-17 → today | newly online (2nd-project POC) |
| template (hub) | 45 | 319 | framework-building only | the lab, not a user |

The hub is ~7% of real exercise; agentic_journal alone is ~85%. **Every finding below is read against derived-project usage, not template-local activity.**

## Executive Summary
The framework's *philosophy* is demonstrably working — independence and the Prime Objective have teeth (the concurrent `/distribute` review caught a real (b)/(c) extraction risk that three build checkpoints missed). Its *operational economy* has slack: ~90% of specialist findings never reach synthesis, agent panels are domain-blind (uniform defaults that misfit backend vs. frontend), the education gate is near-unused downstream despite being a Non-Negotiable, and the measurement instrument itself has drifted between instances. Architectural decisions are stable (1/16 ADRs superseded). Net: **achieving its ends on values, leaking effort on execution.**

## Agent Effectiveness (hub lens; survival data from agentic_journal — the only instance whose view tracks it)

| Agent | Findings | Uniqueness% | Survival% | Read |
|---|---|---|---|---|
| architecture-consultant | 67 | 97 | 6 | high volume, low survival |
| qa-specialist | 49 | 92 | 6 | high volume, low survival |
| ux-evaluator | 42 | 100 | 7 | **frontend-only** (0 findings in backend VerificationPortal) |
| security-specialist | 28 | 89 | **0** | 0 survival in a frontend app; **real value on framework/backend code** (`/distribute`) → domain-fit, not quality |
| docs-knowledge | 25 | 100 | 4 | |
| independent-perspective | 9 | 100 | **11** | **highest survival, lowest dispatch** — punches above its weight |
| performance-analyst | 9 | 100 | 0 | |

**Headline finding — survival collapse.** Across every agent, 0–11% of findings survive into synthesis. We are running 4–5-agent panels and discarding ~90% of their output. Two readings, both actionable:
1. We reward finding **volume** (counts) but the decision-relevant metric is finding **impact** (survival) — and the hub's own dashboard doesn't even compute survival.
2. The advisory flood (below) is mostly noise that doesn't change outcomes.

**Counter-signal worth its own emphasis — independent-perspective.** Lowest dispatch (9 findings) yet highest survival (11%) and 100% uniqueness, and it is the agent that broke the `/distribute` blind spot the homogeneous checkpoint panel shared. The framework is **under-weighting its highest-impact agent.**

## Domain-Fit Misalignment (confirms a standing observation)
ux-evaluator: 42 findings / 100% unique in agentic_journal (frontend) vs **0** in VerificationPortal (backend). security-specialist: ~0 survival in the frontend app, real value on framework/backend code. The template ships **uniform agent defaults**, so every derived project pays for the wrong panel. → **Domain-tiered default panels** (frontend / backend / framework) is the highest-leverage structural change.

## Measurement-Instrument Drift (double-loop: can we even measure ourselves?)
`v_agent_dashboard` has **diverged** between instances:
- hub: `total_unique_findings, total_duplicate_findings, total_false_positives, uniqueness_ratio`
- agentic_journal: `total_findings, uniqueness_pct, survival_pct, avg_calibration`

The hub **lacks `survival_pct`** — the single most decision-relevant effectiveness metric exists only downstream and was never synced back. A meta-review can't compare instances apples-to-apples. This is precisely the class of drift `/distribute` exists to remediate → **this evaluation directly motivates finishing `/distribute`.**

## Protocol Overhead / Solo-Dev Calibration
agentic_journal: review = 201 invocations, **1.4 blocking + 7.9 advisory per review**, 911 agent-turns; checkpoint = 77 invocations, **0.31 blocking per checkpoint**, 502 turns. The advisory:blocking ratio (~5.5:1) plus low survival says we generate a large advisory tail that doesn't convert to outcomes. **Checkpoints are turn-expensive for their blocking yield** — but the `/distribute` build shows them catching real issues, so the answer is calibration (when to fire, how many specialists), not removal.

## Education Gate — mis-designed against its actual user (root cause from the developer, 2026-05-23)
walkthrough/quiz command discussions ≈ 0–2 across all instances (657-discussion agentic_journal: walkthrough=1, quiz=1) despite Principle #6 ("education gates before merge"); where it runs, pass rates are ~100%. **The developer supplied the root cause directly** (primary evidence, stronger than the telemetry inference): the gate underperformed because its *original conception was wrong*. It was built to teach Python syntax / coding routines; what the developer actually needs is to be taught **the high-level concepts each commit uses, so they can understand what is *possible*** — the space of options, not the implementation.

The deeper root: the developer was once a coder whose managers "never really understood my code or skills," and now occupies the **manager seat relative to the agents** — the same uncomprehending-manager gap, from the other side. This is not operational slack; it is a **values-level miss**:
- It undercuts Principle #7. Approval at gates requires understanding; a gate that teaches the wrong thing produces *nominal* approval — the ~100%-pass rubber-stamp the data shows. The framework's human-authority model rests on comprehension the gate isn't building.
- It contradicts Non-Negotiable #1. The gate-as-built taught the *output* (code); the framework declares *reasoning* the primary artifact. A correctly-aimed gate teaches the reasoning + possibility-space — i.e. it would finally serve Principle #1 for the human.
- It is a Prime-Objective concern: a framework that reproduces the manager↔maker alienation between the developer and their agents is failing "serve the contributor" for its own primary human.

**This reframes the fix from "enforce or downgrade Principle #6" to "re-aim the educator at the decision-maker's possibility-space."** (Re-aim, not retire.)

## Decision Stability (healthy)
16 ADRs, 1 superseded (~6% churn). Foundations are stable even as features accrue (ADR-0016 restructure, `/distribute`). The framework is not thrashing its own principles.

## Double-Loop Findings (the criteria themselves)
1. **We measure volume, not impact.** Counts reward noisy agents; survival/calibration reward useful ones. Recalibrate the dashboard (and sync it everywhere) to make survival first-class.
2. **A whole class of defect is unguarded: self-confirming verification.** The `/distribute` case — 3 checkpoints + 7/7 gate + 32 green tests passed a Prime-Objective-violating flaw because the **test fixture encoded the same assumption as the code**. No gate currently asks "does the test share the code's blind spot?" Only a *different frame* (independent-perspective) broke out. Candidate rule: checkpoint/review specialists must challenge the test's assumptions, not just the code's correctness.
3. **We over-flag.** The advisory flood with ~6% survival means most advisory output is unconverted. Consider an advisory budget or a "would this change the merge decision?" filter before capture.
4. **Homogeneous panels share blind spots.** The build-checkpoint panel (qa/security/architecture) reasons from the same mental model that wrote the code; independence is the only escape. Weight independent-perspective up; consider it mandatory (not just high/critical) on anything touching the Prime Objective.

## Framework Adjustments (proposed — developer decides, Principle #7)
- **A. Domain-tiered default panels** (frontend/backend/framework) shipped from the template. Highest leverage; directly fixes the ux-evaluator/security misfit.
- **B. Make `survival_pct` first-class in the hub dashboard and sync the metrics schema to all instances** (via `/distribute` once it lands).
- **C. Recalibrate review economy**: weight independent-perspective up; add an advisory filter / budget; revisit checkpoint specialist-count vs. turn cost.
- **D. Re-aim the education gate at the decision-maker's possibility-space** (developer-sourced root cause): reframe the educator from "teach syntax/code-maintenance" to "teach the high-level concepts each commit uses + what they make possible," so the gatekeeper's Principle-#7 approval is real comprehension, not a rubber stamp. This is the gate finally serving Principle #1 (reasoning over output) for the human. Highest *values* leverage — it closes the manager↔maker gap the framework exists to dissolve.
- **E. New rule candidate**: "verification must challenge assumptions, not just code" (the self-confirming-test guard), promoted from the `/distribute` case.
- **F. Finish `/distribute`** — it is the propagation channel that makes A and B deployable across instances rather than hand-applied.

## Open questions for the panel
- Is `survival_pct` measuring what we think (does it undercount findings folded-not-quoted into synthesis)? If the metric is wrong, finding #1 changes.
- Is the education-gate gap a measurement artifact (gate folded into build/review flows) or a real skip?
- VerificationPortal went quiet ~2026-05-16 — is the framework serving it, or did its overhead stall the project?
