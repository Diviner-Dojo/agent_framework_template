---
adr_id: ADR-0018
title: "Model-aware session wrap-up and handoff"
status: superseded
superseded_by: ADR-0029
date: 2026-05-23
decision_makers: [facilitator, architecture-consultant, security-specialist, qa-specialist, steward]
discussion_id: DISC-20260523-192249-build-session-wrapup
supersedes: null
risk_level: high
scope: framework
confidence: 0.86
tags: [context-window, session-wrapup, handoff, hooks, statusline, auto-launch, consent]
---

> **Superseded by ADR-0029 (2026-07-28).** model-aware session wrap-up was removed; native compaction and a 1M context supersede it. The decision and its
> reasoning are preserved here; only its status changed.


## Context

Long sessions degrade silently. As a context window fills, recall drops ("context rot",
"lost-in-the-middle"), and ADR-0016's thesis — every turn re-pays the resident context — means a
fuller window costs *more per turn* while answering *worse*. The framework's only reaction point was
Claude Code's ~83% auto-compaction (the `PreCompact` hook reminds us to update `BUILD_STATUS.md`): a
late, lossy, involuntary event. There was no awareness of context occupancy and no proactive, clean
handoff.

Research grounding (web research): Anthropic publishes **no** hard "% threshold"; third-party
benchmarks (RULER/LongBench) put the high-quality "effective" working fraction at ~50–65% of the
window; Claude degrades slowest among frontier models but is not immune. Context windows: Opus 4.7 /
Sonnet 4.6 = 1,000,000; Sonnet 4.5 / Haiku 4.5 = 200,000. The only **confirmed** live occupancy
signal is the Claude Code `statusLine` JSON (`context_window.used_percentage`, `context_window_size`,
`transcript_path`, `model`) — but statusLine is display-only and cannot halt or inject. Whether hooks
receive the same `context_window` data is undocumented.

The feature was specified in `SPEC-20260523-110504-session-wrapup`, spec-reviewed (architecture
APPROVE-WITH-CHANGES 0.82, security REVISE 0.87, qa REVISE 0.82 — all blocking findings folded), and
Steward-gated (REVISE 0.88, four conditions folded). The developer approved.

## Decision

Add a model-aware wrap-up capability whose logic lives in one coverage-measured module
(`src/context_sensor.py`), with thin Claude Code hook wrappers and a `wrapping-up-sessions` skill +
`/handoff` command:

- **Occupancy sensor.** A `statusLine` command writes an atomic, per-session sidecar
  (`.claude/hooks/.state/context-occupancy.<session_id>.json`); a `UserPromptSubmit` guard reads it
  (or, if missing/stale per `SIDECAR_FRESHNESS_SECONDS=300`, falls back to a transcript-token estimate
  reusing `scripts/ingest_token_usage.py`). If neither signal is available the guard is silent — it
  never errors the session.
- **Thresholds.** `config/model_context_profiles.yaml` resolves model → profile (tier × window-class)
  → `effective = min(fraction × window, absolute_cap)`. The **absolute cap binds on 1M windows** (Opus
  soft 140K / hard 180K) so we wrap up at the top of the "good recall" band rather than running to
  ~550K tokens of resident rot; the **percentage binds on 200K windows** (~55–70%). Comparison is on
  integer tokens, inclusive. Unknown models fall back to the **most conservative profile** (`haiku_200k`,
  the floor) so they wrap up earliest, never never.
- **Phased enforcement.** v1 ships advisory self-awareness only: the guard injects a one-shot soft
  nudge (debounced via a `.state` flag, re-armed when occupancy drops below soft) and a stronger hard
  nudge. The coercive `Stop`-hook block is **v2** and is **not authorized by this ADR**.
- **Handoff.** The `wrapping-up-sessions` skill writes `docs/handoff/HANDOFF-<ts>.md` from
  `docs/templates/handoff-template.md`, carrying reasoning lineage and open obligations (see
  Consequences). Retention is FIFO at `HANDOFF_RETENTION_CAP=5`.
- **Continuation.** Default = wrap up + **offer**. Auto-launch a headless `claude --print` continuation
  only when **both** the Autonomous Execution Authorization **and** a separate `ALLOW_AUTO_LAUNCH_SESSION`
  key are present; the command is built by `build_launch_command` (returns `None` unless authorized;
  canonicalizes + containment-checks the handoff path, then inlines that validated path into a fixed
  single-positional prompt — injection-safe under `shell=False`, the form `claude --print` accepts),
  inherits all Prohibited Actions, is depth-capped at `MAX_AUTO_LAUNCH_DEPTH=1`, and
  ntfy-notifies on launch.

### The 1M-window threshold model (why the absolute cap)

Percentage alone is the wrong control on a 1M window: 55% = 550K tokens, which is wasteful (per-turn
cost scales with resident context) and still degraded. `min(fraction × window, absolute_cap)` lets the
percentage govern the 200K class and the cap govern the 1M class with one set of knobs — the binding
control simply differs by window class. Caps (120K–180K) sit at the top of the third-party "good
recall" band; Opus caps highest (slowest degradation), Haiku lowest (fastest).

### Consent default (Steward conditions 1–2)

The **shipped framework posture is wrap-up + offer.** Auto-launch is operative only when the human has
authored **both** consent keys. This keeps clause (c) ("no value accrual from derivatives without
human-authored, per-instance assent") and Principle #7 satisfied: spawning a process that continues
work autonomously requires a fresh, explicit human act, not inference from the general autonomous-auth
flag (which authorizes *workflow steps*, not *process spawning*). **`/distribute` never stages or sets
either consent key in a target**; the derived project's human authors both. `ALLOW_AUTO_LAUNCH_SESSION`
and the per-model threshold numbers are **pinned-trait candidates** so distribution cannot overwrite a
target's local consent posture or tuning.

## Alternatives Considered

- **Percentage-only thresholds.** Rejected: wasteful and degraded on 1M windows (550K of resident
  rot); the absolute cap is needed.
- **Separate config file per window class.** Rejected: duplicates the threshold knobs; one file keyed
  by tier × window-class with `min(fraction, cap)` is simpler.
- **Hook-only mechanical trigger (coerce wrap-up now).** Rejected for v1: depends on undocumented hook
  `context_window` access and risks stop-loops; deferred to a separately-gated v2 (Principle #8).
- **Auto-launch on the autonomous-auth flag alone.** Rejected (Steward): conflates workflow autonomy
  with process spawning; a separate `ALLOW_AUTO_LAUNCH_SESSION` key is required.
- **`Task` subagents for continuation.** Rejected: isolated context, cannot continue the main thread,
  cannot spawn subagents — structurally wrong for "pick up where we left off."
- **Deriving model→profile from `model_pricing.yaml`'s `models:` map.** Rejected: the two maps update
  on different cadences (pricing on price changes; profiles on new-model windows). The duplication of
  the model-ID list is a **conscious** decision, not drift.

## Consequences

### Positive
- Sessions become context-self-aware and wrap up cleanly before degradation/auto-compaction, preserving
  reasoning quality and cutting per-turn cost.
- One coverage-measured core (`src/context_sensor.py`, 92% covered) owns all threshold / parsing /
  spawn logic; hooks and the skill stay thin.
- The handoff artifact preserves lineage: required reading (BUILD_STATUS first), settled decisions,
  in-progress checkpoint, exact next steps, **open `/review` advisories**, **un-completed education-gate
  deferrals**, and an explicit "inherits CLAUDE.md, run `/review` before any commit, do not bypass
  capture" — so a continuation cannot resume past a pending evaluation (Principles #1/#2/#4/#6).

### Negative / limitations (honest)
- Thresholds are research-informed **heuristics**, not Anthropic-official; they are one-line tunable.
- statusLine is the only confirmed live signal and is display-only; hook `context_window` access is
  undocumented — hence the sidecar bridge + transcript fallback.
- The transcript estimate (`input + cache_read + cache_create` of the newest message) is approximate
  (sliding-window/cache effects); it is stamped `transcript-estimate` and is lower-confidence.
- v1 nudges are decline-able mid-task; the gap is closed only by the (future, separately-gated) v2
  Stop-block, which itself yields to the ~83% auto-compact backstop after bounded retries.
- Auto-launch is a real OS process; gated by dual consent, no-push, file-path-only seeding, depth cap,
  and ntfy notify. The exact `claude --print` continuation invocation should be verified against the
  installed CLI at first real use.
- The env-var auto-compact backstop applies to new sessions only and cannot exceed ~83%.

### Neutral
- Adds `config/model_context_profiles.yaml`, a `wrapping-up-sessions` skill, a `/handoff` command, and
  `docs/handoff/` (gitignored). `settings.json` (statusLine + `UserPromptSubmit` hooks + `"env"`
  backstop) is a documented **manual** edit — no `/update-config` tool is introduced.
- Distributable later via `/distribute` (opt-in HARD GATE), minus the consent keys.

## Linked Discussion

- Spec review: `DISC-20260523-190838-session-wrapup-spec-review` (sealed)
- Steward gate: `DISC-20260523-191709-session-wrapup-steward-gate` (sealed)
- Build: `DISC-20260523-192249-build-session-wrapup`
- Spec: `docs/sprints/SPEC-20260523-110504-session-wrapup.md`

## Amendment — 2026-06-07: auto-launch wedge + external supervisor (v2)

**First real use of the consent-gated auto-launch failed**, confirming the limitation flagged
above ("verify the exact `claude --print` invocation at first real use"). On Windows / CLI
v2.1.143, `subprocess.Popen(["claude", "--print", prompt])` from inside a running session
**wedged**: a headless run that needs tools (Read/Bash/Edit) **hangs forever on the first
tool-permission request** — 0 CPU, 0 stdout — because in non-interactive mode there is no one
to approve it. A trivial no-tool prompt returned fine, which masked the defect (a smoke-test
fidelity gap). Worse, the parent session inferred success from an indirect signal (a poll-lock
supersede) and **falsely reported "continuation is live"** when it had frozen.

**Two root causes, both fixed:**
1. **Missing permission flag.** Headless agentic runs require `--permission-mode
   bypassPermissions` (verified: a real `Bash` tool then runs, `permission_denials:[]`, exit 0).
   Do NOT add `--bare` — it forces `ANTHROPIC_API_KEY`-only auth (breaks an OAuth subscription)
   AND skips the project's PreToolUse hooks. `bypassPermissions` does NOT skip hooks, so the
   pre-push blocker / settings.json validator / pre-commit gate still enforce
   no-push / no-settings-edit / review-before-commit.
2. **An agent should not spawn its own successor from inside a dying session** (fragile). The
   robust pattern is an **external supervisor** (`scripts/session_supervisor.py`): a plain
   process with no LLM context that chains fresh `claude -p` runs via a rolling handoff, looping
   until a `SUPERVISOR_DONE` sentinel. Real exit codes + JSON output + a progress log make
   "did it make progress?" verifiable, not inferred — closing the false-positive failure mode.

**Supersedes** the in-session `build_launch_command` + `Popen` self-spawn as the recommended
mechanism. `build_launch_command` remains for reference; new autonomous continuation uses the
supervisor. Safety: clean-git-tree preflight (`bypassPermissions` allows destructive local Bash
the hooks don't block), `--max-sessions` / `--max-budget-usd` / `--per-session-timeout` caps,
fail-closed unknown-sentinel-stop. Review: `REV-20260607-225506`
(`DISC-20260607-225506-review-session-supervisor`). A full Steward gate + ADR for the supervisor
as a first-class capability is owed (operate-then-formalize).
