---
adr_id: ADR-0011
title: "Meta-Command Specialist Dispatch and Review Enforcement"
status: accepted
date: 2026-02-19
decision_makers: [developer, facilitator]
discussion_id: null  # Decision made during framework evaluation implementation session
supersedes: null
risk_level: medium
confidence: 0.90
tags: [capture, review, retro, meta-review, quality-gate, principle-2, principle-4]
---

## Context

A framework evaluation identified three related gaps:

1. **Gap #1 — Feedback loop never closed**: `/retro` and `/meta-review` have never been run. These commands evaluate agent effectiveness but lack capture pipeline integration and specialist dispatch — meaning the commands that assess quality are themselves unreviewed (an ironic gap).

2. **Gap #2 — Review enforcement is opt-in**: The commit protocol requires running `/review` before committing code changes, but nothing in the quality gate actually checks whether a review was run. Compliance depends entirely on the agent remembering to do it.

3. **Gap #3 — Stale references**: The commit protocol still references `src/` and `tests/` (Python-era paths), when the project migrated to Flutter/Dart (`lib/` and `test/`) in ADR-0002.

ADR-0009 established mandatory discussion capture for all agent-dispatching commands but explicitly exempted `/retro` and `/meta-review` because they did not dispatch agents at the time. This ADR extends ADR-0009 by adding specialist dispatch to both commands, removing them from the exempt list, and adding automated review enforcement to the quality gate.

## Decision

### 1. `/retro` and `/meta-review` now dispatch specialists

Both commands are upgraded to follow the same capture pattern established by ADR-0009:

**`/retro`** dispatches 2 specialists to review the DRAFT retrospective:
- `independent-perspective` (sonnet) — challenges retro findings for blind spots and confirmation bias
- `docs-knowledge` (sonnet) — checks whether findings should update CLAUDE.md or rules

**`/meta-review`** dispatches 2 specialists to review the DRAFT framework evaluation:
- `architecture-consultant` (sonnet) — validates drift findings against actual ADRs
- `independent-perspective` (sonnet) — challenges the framework evaluation itself (meta-meta check)

Both commands now include:
- CRITICAL BEHAVIORAL RULES section (matching `/review`, `/plan`, etc.)
- Capture script pre-flight checks
- Full discussion lifecycle: create → proposal event → specialist dispatch → critique events → synthesis → close

### 2. Quality gate enforces review existence

`scripts/quality_gate.py` gains a new Check 6 — "Review existence":
- Detects staged code files (under `lib/`, `test/`, `scripts/`, `.claude/agents/`, `.claude/commands/`, `.claude/rules/`)
- Checks for review reports matching today's date in `docs/reviews/`
- FAILs if code changes are staged with no review report from today
- Bypassable with `--skip-reviews` flag
- Fails safe: if git is unavailable or no files are staged, the check passes

### 3. Stale references fixed

The commit protocol (`.claude/rules/commit_protocol.md`) is updated to reference `lib/` and `test/` instead of `src/` and `tests/`, and to reference `dart format`/`dart analyze`/`flutter test` instead of `ruff`/`pytest`.

## Alternatives Considered

### Alternative 1: Leave `/retro` and `/meta-review` without specialist dispatch
- **Pros**: Simpler commands, less overhead
- **Cons**: The commands that evaluate quality are themselves unevaluated — Principle #4 violation. Findings may contain blind spots that go unchallenged.
- **Reason rejected**: If we believe independent review matters, it matters for the review process itself, not just for code.

### Alternative 2: Enforce review existence via git hook instead of quality gate
- **Pros**: Impossible to bypass without `--no-verify`
- **Cons**: Git hooks are harder to maintain, can't easily share state with the quality gate, and the quality gate already runs as a pre-commit hook. Adding a separate hook creates maintenance burden.
- **Reason rejected**: The quality gate already runs as a pre-commit hook. Adding the check there is simpler and keeps all gate logic in one place.

### Alternative 3: Require review report to reference specific staged files
- **Pros**: Stronger guarantee that the review covers the actual changes
- **Cons**: Review reports don't currently contain a machine-parseable list of reviewed files. Would require changes to the review command output format. Over-engineering for the current project scale.
- **Reason rejected**: Checking for same-day review existence is sufficient. False positives (review exists but for different files) are unlikely at current project scale and addressed by developer awareness.

## Consequences

### Positive
- The feedback loop can now close: `/retro` produces specialist-reviewed retrospectives with captured reasoning
- `/meta-review` evaluations are themselves evaluated — no more unreviewed reviews
- The quality gate catches missing reviews automatically instead of relying on agent memory
- All agent-dispatching commands now integrate the capture pipeline: `/review`, `/deliberate`, `/analyze-project`, `/plan`, `/walkthrough`, `/quiz` (ADR-0009), `/build_module` (ADR-0010), `/retro`, `/meta-review` (this ADR) — ADR-0009 fully satisfied

### Negative
- `/retro` and `/meta-review` take longer due to specialist dispatch (2 additional agent calls each)
- Quality gate has one more check that may cause commit failures — but `--skip-reviews` provides an escape hatch
- Developers must create review reports on the same day as the commit for the check to pass

### Neutral
- The capture pipeline scripts themselves are unchanged
- The specialist prompt pattern matches existing checkpoint review patterns
- The `--skip-reviews` flag follows the same convention as other `--skip-*` flags

## Linked Discussion

No formal discussion captured for this decision. It was made during the 2026-02-19 framework evaluation session. The retrospective that identified the gaps is captured in DISC-20260219-221241-retro-20260219. The review of this implementation is captured in DISC-20260219-223248-review-feedback-loop-enforcement (REV-20260219-223712).
