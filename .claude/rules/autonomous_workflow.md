# Autonomous Workflow Protocol

> Prevents protocol skipping under autonomous execution authorization.
> Root cause: Derived project experienced a 7-workstream implementation that bypassed /plan,
> /build_module, /review, and BUILD_STATUS.md updates. All code was written without
> independent evaluation (Principle #4 violation).

## Mandatory Workflow for Code Changes

When implementing features, bug fixes, or any change touching `src/` or `tests/`:

### Multi-file features (3+ files or 2+ new files under `src/`)

1. **`/plan`** — Structured spec + specialist design review + developer approval
2. **`/build_module`** — Implementation with mid-build checkpoint reviews (per `build_review_protocol.md`)
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
- **Layer 1 capture**: Every `/review`, `/build_module`, `/plan` creates a discussion automatically via capture pipeline

## What "Autonomous Execution" Means

The CLAUDE.md autonomous execution authorization permits executing the **full workflow** without pausing to ask permission at each step. It does **NOT** permit skipping steps.

> "Proceed without asking" ≠ "proceed without reviewing."

The authorization removes the need to ask "may I commit?" or "may I push?" — it does not remove the need to run `/review` before committing or `/plan` before building.

## Violations

If you are about to commit without having run `/review`, **STOP**. Run `/review` first. There is no time pressure that justifies skipping independent evaluation (Principle #4).

If you are about to implement a multi-file feature without `/plan`, **STOP**. The cost of catching a bad design after implementation is far higher than catching it at spec review time.

## Relationship to Other Rules

- `commit_protocol.md` — defines the commit sequence (quality gate → review → education gate → commit)
- `build_review_protocol.md` — defines mid-build checkpoint triggers and specialist dispatch
- `review_gates.md` — defines risk tiers, specialist selection, and quality thresholds
- This rule adds the **sequencing requirement**: which commands must run, in what order, for what scope of change
