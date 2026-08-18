# Autonomous Workflow Protocol

> Prevents protocol skipping under autonomous execution authorization.
> Root cause: Derived project experienced a 7-workstream implementation that bypassed /plan,
> /build_module, /review, and BUILD_STATUS.md updates. All code was written without
> independent evaluation (Principle #3 violation).

## Mandatory Workflow for Code Changes

When implementing features, bug fixes, or any change touching `src/` or `tests/`:

### Multi-file features (3+ files or 2+ new files under `src/`)

1. **`/plan`** — Structured spec + specialist design review + developer approval
2. **`/build_module`** — Implementation with mid-build checkpoint reviews (per the `running-build-checkpoints` skill)
3. **Quality gate** — `python scripts/quality_gate.py`
4. **`/review`** — Multi-agent specialist code review
5. **Address blocking findings** — fix before commit
6. **Commit + push**

### Small changes (1-2 files, no new modules)

1. Implement the change
2. **Quality gate** — `python scripts/quality_gate.py`
3. **`/review`** — Multi-agent specialist code review (skip ONLY for docs/config-only changes)
4. **Commit + push**

### Non-negotiable at every scale

- **BUILD_STATUS.md**: Update at session start, before compaction, and after each commit
- **`/review`**: Required before any commit touching `src/` — no exceptions
- **Pre-build search**: Check `memory/projects/` and `memory/bugs/regression-ledger.md` for prior art before building (per the `searching-prior-art` skill)
- **Layer 1 capture**: Every `/review`, `/build_module`, `/plan` creates a discussion automatically via capture pipeline

## What "Autonomous Execution" Means

The CLAUDE.md autonomous execution authorization permits executing the **full workflow** without pausing to ask permission at each step. It does **NOT** permit skipping steps.

> "Proceed without asking" ≠ "proceed without reviewing."

The authorization removes the need to ask "may I commit?" or "may I push?" — it does not remove the need to run `/review` before committing or `/plan` before building.

## Violations

If you are about to commit without having run `/review`, **STOP**. Run `/review` first. There is no time pressure that justifies skipping independent evaluation (Principle #3).

If you are about to implement a multi-file feature without `/plan`, **STOP**. The cost of catching a bad design after implementation is far higher than catching it at spec review time.

## Calibration Loop (closes the audit→tighten loop — ADR-0024)

The framework *computes* a calibration signal (`agent_effectiveness.confidence_calibration`)
and classifies findings (severity/category/is_noise) but historically never read those signals
back to tighten its classifier — it only clustered post-hoc. `scripts/audit_calibration.py`
closes that loop, a back-flow pattern from `dan_research_karpathy_wiki` (SPEC-20260610-205507 D2).

- **When to run:** periodically (e.g. at `/retro`/`/meta-review` time, or after a batch of
  reviews), not on every commit. It is **advisory — never a gate-blocking step**; the quality
  gate's pass/fail meaning is unaffected.
- **What it does:** reads `metrics/evaluation.db` read-only, surfaces drift signals (per-agent
  calibration error, category is_noise rate, heuristic-vs-recorded severity disagreement), and
  writes **proposals** to `memory/calibration-proposals/CALIB-<ts>.md` (append-only) plus a line
  to `metrics/calibration_log.jsonl`.
- **Human gate (non-negotiable):** proposals are `status: pending` **communication** artifacts,
  not instruction files. Tightening a classifier surface (`scripts/extract_findings.py` patterns
  → full `/review`; `.claude/skills/severity-calibration/SKILL.md` → Steward gate) is a
  **developer action**. The agent must **never** edit a classifier surface off a proposal — that
  would be self-modification (Principle #6; Prime Objective human-mediated enforcement). The
  `confidence_calibration` metric is a rough proxy; treat single-signal proposals as low-confidence.

## Relationship to Other Rules

- `committing-changes` skill — defines the commit sequence (quality gate → review → education gate → commit)
- `running-build-checkpoints` skill — defines mid-build checkpoint triggers and specialist dispatch
- `selecting-review-gates` skill — defines risk tiers, specialist selection, and quality thresholds
- This rule adds the **sequencing requirement**: which commands must run, in what order, for what scope of change
