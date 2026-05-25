---
spec_id: SPEC-20260525-160115
title: "Generalized backend-agnostic watcher daemon (governance-aligned)"
type: vision
status: draft
risk_level: high
intake_ids: []
completed_at:
completed_commit:
---

## Goal

Capture — as a deferred design, not an approved build — a **backend-agnostic,
governance-aligned polling-watcher daemon** for the framework template,
generalized from agentic_journal's `scripts/dev_watcher/` pipeline. The watcher
polls a work source on a fixed interval, dispatches one item per cycle to an
autonomous Claude Code session, and pushes a phone notification at every
meaningful transition (work ready, PR opened, review blocked, backend
unreachable, advisory budget breach).

This document exists so the methodology is **on the record and ready to
greenlight** without committing the template to build it now. Promotion to an
actionable `type: spec` requires the specialist design review described under
*Promotion Gate* below.

## Context

### Why this is a vision and not a spec

The framework's own prior analysis already evaluated this pattern and **deferred
it**:

> `/watcher Autonomous Pipeline | 16/25 | DEFER` — and: "The Supabase-specific
> patterns (/watcher, /journal-review, /status) are **not portable** but
> represent an aspirational architecture for cloud-connected framework
> derivatives." — `memory/projects/agentic-journal.md` (analyzed 2026-04-06)

16/25 is below the 20/25 ADOPT threshold (Rule of Three, `memory/lessons/adoption-log.md`).
The driving objection was **portability**: agentic_journal's watcher is welded to
Supabase (`supabase_client.py`, the `dev_work_items` table, a `dev_work_items`
FSM) and to a Flutter app's remote dev-work queue — none of which the template has.

The developer's instruction was to "benefit from that project's methodology, but
not at the expense of yours, if it is better." The reconciliation, captured here:
**generalize away the Supabase coupling** (the specific reason for the DEFER) and
**bring the governance hardening home** (the part that is genuinely better than a
naive watcher). That turns a non-portable derivative feature into a reusable hub
capability — but it is a high-risk autonomous-execution surface, so it stays
deferred until a derived project actually needs it and the promotion gate is run.

### What was already harvested separately

The notify *primitive* (`scripts/notify.py`, hardened beyond the source),
`.env` config, the `notifying-the-developer` skill, the inbound
`scripts/ask_developer.py`, and the discussion-close hook
(`scripts/close_discussion.py`) already exist. The **task-boundary notification
hooks** workstream (extending notify to long-running scripts such as
`quality_gate.py`) is being built now as a separate small change — it is *not*
the deferred item and does not depend on this vision.

### Source methodology (agentic_journal `scripts/dev_watcher/`)

- `watcher.py` — `schedule`-driven loop; polls every N minutes, single-threaded,
  one item per cycle; runs once immediately on start; `KeyboardInterrupt` to stop.
- `poller.py` — queries the backend in priority order (revisions → approved →
  queued); processes the first actionable item; pushes a **"Pipeline offline"**
  alert (deduped via a `_was_down` latch) when the backend is unreachable.
- `tasks.py` — per-state handlers; push on each transition (plan-ready,
  PR-opened, review-blocked, revision-received).
- `claude_executor.py` — dispatches the `claude` CLI via stdin; **sanitizes** all
  work-item content before prompt assembly; advisory **budget-threshold** push
  (`WATCHER_OUTPUT_WARN_BYTES` / `WATCHER_ELAPSED_WARN_SECS`, never aborts);
  **verdict-gated PR**: the dispatched session must run `/review` and emit a
  sentinel-bracketed verdict block, and the watcher halts on
  `REQUEST-CHANGES`/`REJECT`/`BLOCKED`/absent.
- `supabase_client.py` — the backend adapter (the part to abstract away).
- `fsm.py` — single source of truth for valid status transitions.

## Requirements (design intent — refine at promotion to spec)

- **R1 — Pluggable poll-source.** Define a backend-agnostic `WorkSource`
  interface (e.g. `get_actionable_item() -> WorkItem | None`,
  `mark(item, status, **fields)`, `is_reachable() -> bool`). Ship a **reference
  adapter** that needs no cloud backend — a local SQLite or JSONL/file-queue
  source — plus a no-op demo source. Supabase, a REST queue, etc. become
  third-party adapters in derived projects, not template dependencies.
- **R2 — Loop.** Fixed-interval poll, single-threaded, one item per cycle, run
  immediately on start, clean `KeyboardInterrupt` shutdown. Evaluate `schedule`
  (one new dep, pin in `requirements.txt`) vs a stdlib `time`-based loop; prefer
  stdlib if it keeps the footprint light without much cost.
- **R3 — Notify on the three human-relevant moments.** State transition,
  backend-unreachable (deduped latch), and advisory budget-threshold breach.
  All via `scripts/notify.py` — best-effort, no-op when `NTFY_TOPIC` unset.
- **R4 — Governance-aligned autonomous dispatch (the load-bearing requirement).**
  Any Claude Code dispatch routes through `/review` and **halts on blocking
  verdicts**. Port agentic_journal's hardened gate verbatim in spirit:
  - Halt on `REQUEST-CHANGES` / `REJECT` / `BLOCKED`.
  - **Absent verdict is BLOCKING** (security-F2 — "no signal" must never mean
    "passing").
  - Verdict extraction is **scoped to sentinel-bracketed blocks**
    (`BEGIN_WATCHER_VERDICT` / `END_WATCHER_VERDICT`); a bare `Verdict:` line
    outside the block is ignored (security-F1 — defends against
    prompt-injection from attacker-controlled poll-source content).
  - **Sanitize** all poll-source content before interpolation into a dispatched
    prompt, and strip the sentinel tokens from that content so it cannot forge a
    verdict block.
- **R5 — Opt-in / inert when unconfigured.** No configured poll-source ⇒ the
  watcher does nothing and breaks nothing, mirroring the notify no-op contract.
  Dispatch of an autonomous session must additionally require the explicit
  Autonomous Execution Authorization + `ALLOW_AUTO_LAUNCH_SESSION` posture the
  framework already defines (CLAUDE.md Always-On Invariants, ADR-0018) — the
  watcher is exactly the kind of unattended auto-launch those gates govern.

## Constraints

- Python 3.11+; keep the stdlib-light footprint where reasonable. At most one new
  dependency (`schedule`), pinned in `requirements.txt`, and only if it earns its
  place over a stdlib loop.
- No Supabase/Flutter/Dart-specific content in any template artifact.
- The watcher must not weaken any existing gate: it *consumes* `/review`, it does
  not replace it. It must respect `.claude/rules/autonomous_workflow.md`
  ("proceed without asking" ≠ "proceed without reviewing") and Principle #4
  (the generator is never its sole evaluator).
- Out-of-band notification text stays confidentiality-safe (ntfy.sh is a public
  relay): no secrets, private paths, or PII (`notifying-the-developer` skill).

## Acceptance Criteria

_None — this is a `type: vision` document (idea capture). Acceptance criteria are
authored when/if it is promoted to a `type: spec`._

## Risk Assessment

- **High risk — autonomous code dispatch.** A daemon that runs Claude Code
  unattended and opens PRs is the single most safety-sensitive surface the
  framework could add. The verdict-gate (R4) is the mitigation and is
  non-negotiable; the absent-verdict-is-blocking and sentinel-scoping rules are
  the specific defenses against the two failure modes agentic_journal already hit
  (REV-20260507 security-F1/F2). This is *why* the build stays gated behind the
  promotion review.
- **Medium risk — prompt injection via poll-source.** Work-item content is
  untrusted input crossing a trust boundary into an LLM prompt. Sanitize +
  sentinel-strip (R4) at the boundary; never assume internal-origin data is safe.
- **Medium risk — abstraction quality.** A poorly-drawn `WorkSource` boundary
  re-couples the watcher to a backend's quirks. The reference adapter exists to
  prove the boundary holds with zero cloud dependencies.
- **Low risk — notification noise / footprint.** Mitigated by the no-op contract,
  the dedupe latch, and advisory-only thresholds.

## Affected Components (anticipated, if promoted)

### New files
- `scripts/watcher/` package: `watcher.py` (loop), `poller.py` (cycle),
  `tasks.py` (transitions), `dispatch.py` (Claude executor + verdict gate +
  sanitizer + budget thresholds), `sources.py` (`WorkSource` interface +
  reference adapter + no-op source), `fsm.py` (transition table).
- `tests/test_watcher.py` — verdict extraction (incl. injection + absent-verdict),
  sanitizer, budget thresholds, FSM transitions, reference-adapter, notify
  best-effort.
- An ADR documenting the watcher capability + the verdict-gate safety contract.

### Modified files
- `.env.example` — watcher env vars (poll interval, budget thresholds, source config).
- `.claude/skills/notifying-the-developer/SKILL.md` — watcher pattern section.
- Possibly a `/watcher` command wrapper, and CLAUDE.md Directory Layout note.

## Dependencies

- Depends on: `scripts/notify.py` (exists); the `/review` workflow + verdict
  conventions; the Autonomous Execution Authorization + `ALLOW_AUTO_LAUNCH_SESSION`
  posture (ADR-0018).
- Depended on by: any future cloud-connected framework derivative that wants an
  unattended dev-work pipeline.

## Promotion Gate (required before this becomes a `type: spec`)

Before any implementation, run a specialist design review of this design:
- **security-specialist** — the autonomous-dispatch surface, the verdict-gate
  (F1/F2), and the poll-source trust boundary.
- **architecture-consultant** — the `WorkSource` abstraction boundary and where
  the package sits relative to the existing capture/quality stack.
- **independent-perspective** — whether an unattended auto-dispatch daemon
  belongs in the *template* at all, vs. remaining a derived-project capability,
  and whether the 16/25 DEFER should actually be overturned.

Promotion also requires explicit developer approval (this is a framework-evolution
-adjacent capability) and resolves the active-spec budget at that time.
