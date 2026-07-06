---
adr_id: ADR-0024
title: "Confidence-calibration loop — audit-to-tighten feedback closed via a human-gated proposal queue"
status: accepted
date: 2026-06-13
decision_makers: [orchestrator, independent-perspective, qa-specialist, security-specialist, steward]
discussion_id: DISC-20260613-234253-d2-pattern2-calibration-loop
spec_id: SPEC-20260610-205507
supersedes:
scope: framework
risk_level: high
confidence: 0.88
tags: [backflow, calibration, classifier, capture, human-in-the-loop, dan-research-wiki]
---

## Context

The template **computes** a calibration signal it never reads. `scripts/compute_agent_effectiveness.py`
writes `agent_effectiveness.confidence_calibration = |confidence_avg − unique/(unique+duplicate)|`
per agent-discussion, and `scripts/mine_patterns.py` clusters findings post-hoc into
`pattern_sightings`. Neither feeds anything back: the severity/category classifiers
(`scripts/extract_findings.py` static `_SEVERITY_PATTERNS`/`_CATEGORY_PATTERNS`) and the
`severity-calibration` skill rubric are tuned once and never revisited against their own track
record. The loop between "how the classifier decided" and "tighten the classifier" is open.

**Origin (back-flow, SPEC-20260610-205507 decision D2, pattern 2 of 5).** This design is harvested
from **dan_research_karpathy_wiki** (a derived satellite), which built it first. The wiki's
classifier is an LLM topic-routing procedure that emits a HIGH/MEDIUM/LOW **confidence** per
routing decision; every decision is logged append-only to `routing.log.md`; the router
periodically re-reads the log and, on drift signals (several MEDIUM routings to a wiki → topic too
vague; repeated **user redirects** → classifier miscalibrated), **proposes tightening the
classifier prompt** before the next batch (wiki `CLAUDE.md` §"Confidence calibration"; the wiki's
"future-you uses the log to calibrate confidence"). The donor (this template) "only clusters
post-hoc" — the wiki closes the loop the donor leaves open. Attribution per the Prime Objective
test (a): the wiki is credited as origin; the `back_flow` ledger line in its `framework-lineage.yaml`
flips `owed → delivered` with this ADR.

The mapping was gated by an **independent enumeration** (independent-perspective, conf 0.91,
DISC-20260613-234253) of which Always-On Invariants the port touches and how it must deviate from
the wiki version — the orchestrator did not self-enumerate (SPEC critical mitigation).

## Decision

Port the pattern as a **read-only audit script + a documented loop procedure**, with the
audit→tighten loop closed through a **human-gated proposal queue** — never a mechanical edit:

1. **`scripts/audit_calibration.py`** — read-only on `metrics/evaluation.db`. Computes drift
   signals from data the template already records — per-agent `confidence_calibration` over a
   conservative threshold, `is_noise` rates, and severity explicit-marker-vs-heuristic
   disagreements — and emits a human-readable **calibration report**. Each drift signal that
   crosses threshold produces a **proposal** to tighten a named classifier surface, written to an
   append-only, dated queue artifact under `memory/calibration-proposals/`. Every proposal carries
   the **raw evidence** that triggered it (the metric value + sample finding summaries), is typed
   `classifier-code` or `skill-rubric` (distinct approval paths), and is stamped `status: pending`.
   The run appends one line to `metrics/calibration_log.jsonl` (capture is automatic).
2. **`.claude/rules/autonomous_workflow.md` "Calibration Loop" section** (the donor target named by
   the wiki ledger) — when to run the audit, that it *closes* the compute-but-never-read loop, and
   that any proposed classifier tightening is **advisory** (never gate-blocking) and requires
   **developer action** to apply (the agent never edits a classifier surface off a proposal).
3. **Tests `tests/test_audit_calibration.py`** — lock the guards below.

The script **never modifies any classifier surface**. It reads and reports; a human applies.

### Adaptations (deliberate deviations from the wiki version)

The wiki, single-user, lets the LLM router auto-propose and silently incorporate tightened prompts.
In this framework that would make an autonomous calibration run a **self-modification**. Adaptations,
all load-bearing unless noted:

- **Human-gated proposal queue, not auto-propose.** Proposals are written to
  `memory/calibration-proposals/CALIB-<ts>.md` as `status: pending` *communication* artifacts —
  never instruction files an agent acts on. Classifier surfaces (`scripts/extract_findings.py`
  patterns; `.claude/skills/severity-calibration/SKILL.md`) are applied **only by developer
  action**. Principle #7 (Layer 3 promotion requires human approval) + Prime Objective
  (human-mediated enforcement). Without this, an AFK agent could read its own proposal and "apply
  what a human would approve anyway."
- **Deterministic read-only script, not an LLM re-read.** A Python audit over pre-computed metrics
  is reproducible and regression-testable; an LLM re-read is neither. Principle #2 (capture at the
  tooling layer, model cannot opt out).
- **`is_noise = 0` on every severity query.** Noise rows carry an *unmaintained* severity
  (ADR-0022; regression ledger 2026-06-12). Aggregating severity without the filter computes drift
  over corrupted data — a meta-calibration failure. Regression-tested.
- **Raw evidence per proposal.** The report includes the metric value + sample finding summaries
  behind each proposal, so the human approval is substantive, not rubber-stamp (Principle #1; the
  human is the independent evaluator per Principle #4).
- **Typed proposals → correct approval path.** `classifier-code` proposals (the static pattern
  dicts) are code changes needing the full `/review` → commit path; `skill-rubric` proposals are
  prompt/skill changes needing the Steward gate. Conflating them would route a change through the
  wrong gate.
- **Advisory, not gate-integrated.** Calibration emits proposals that can never auto-apply; wiring
  it into the quality gate would add non-blocking noise to every commit and erode the gate's
  hard-pass/fail meaning. (Not load-bearing for correctness, but for gate trust.)
- **Signals adapted to the template's data model.** The wiki's user-redirect signal has no dense
  analog (`findings_false_positive` is sparsely recorded), so drift detection is scoped to
  `confidence_calibration` + `is_noise` rate + marker-vs-heuristic disagreement, and the report
  states this gap rather than over-trusting a sparse column.

### Residual risks (accepted, from the independent enumeration)

- **`confidence_calibration` is a rough proxy** (`|confidence_avg − unique/(unique+duplicate)|`,
  where "accuracy" ≈ uniqueness ratio). An agent can score well by being confidently the sole
  finder of a category regardless of correctness. Mitigation: conservative thresholds (stated in
  the script), and proposals triggered by calibration error *alone* (no corroborating is_noise or
  marker disagreement) are flagged **low-confidence** in the report. The metric is a *signal for
  human judgment*, not a measurement.
- **Agent-authored finding text is untrusted input.** `summary`/`raw_excerpt` are read into the
  report display-only; the script never passes them to a shell, prompt, or eval sink
  (sanitize-at-trust-boundary). Regression-tested with a shell-metacharacter payload.
- **Raw DB errors.** All sqlite access is wrapped; only `type(exc).__name__` + a generic message
  is surfaced (never-expose-raw-DB-errors), mirroring the ADR-0023 no-detail error discipline.
- **Queue self-application.** The enforcement assumption is that classifier-surface files are
  write-protected for agent edits; this ADR makes that requirement explicit. A settings.json
  PreToolUse protection entry for those surfaces would be defense-in-depth (both the Steward and
  security reviews encouraged it) but is **not authored here** — it is a follow-on draft diff for
  the developer (the validator denies agent edits to settings.json by design). The loop is correct
  without it because the queue is non-actionable by construction.
- **Queue is human-read, never machine-parsed** (security review, LOW). The proposal queue is a
  Markdown artifact a human reads; agent-authored finding text is embedded display-only (repr-quoted).
  No agent or CI automation may parse the queue as instructions — a crafted `summary` could otherwise
  forge a `status:` or surface path. If programmatic consumption is ever needed, switch to a
  structured (JSONL, explicit-schema) format rather than scraping the Markdown.

## Consequences

- The template gains the feedback loop it was missing: the already-computed calibration signal
  becomes legible and actionable, with the human as the gate.
- Shipping is behavior-neutral: a read-only script + an advisory rule section change nothing until a
  human runs the audit and chooses to apply a proposal.
- `metrics/calibration_log.jsonl` makes every calibration run traceable (append-only).
- Tests lock: read-only-on-DB, `is_noise=0` filter, no-sink for finding text, generic-error,
  no-auto-apply (the script writes only to the queue + log, never to a classifier surface),
  append-only queue.

## Alternatives Considered

- **Auto-applying tightenings (the wiki's model):** rejected — self-modification under autonomy;
  violates Principle #7 + the Prime Objective.
- **Wiring calibration into `quality_gate.py`:** rejected — a non-blocking advisory in a hard gate
  erodes the gate's pass/fail meaning.
- **An LLM agent doing the re-read each cycle:** rejected for the loop's core — non-reproducible,
  not regression-testable, can't be captured deterministically. (A human still reads the report;
  the *signal extraction* is deterministic.)
- **Doing nothing (keep computing `confidence_calibration` unread):** rejected — that is exactly the
  open loop this pattern closes.
