---
name: wrapping-up-sessions
description: Model-aware session wrap-up + handoff (ADR-0018). Use when context is running low / a soft or hard wrap-up nudge fired, when the developer says wrap up / hand off / continue in a fresh session, or when a long session should cleanly checkpoint before quality degrades or auto-compaction. Covers the threshold model, the wrap-up protocol, the handoff artifact, and the consent-gated auto-launch continuation.
---

# Wrapping Up Long Sessions

> A session stays self-aware of its context occupancy and, once it crosses a
> **model-specific** threshold, cleanly wraps up: finish the current step, capture
> state, write a paste-ready handoff, then (only with explicit consent) launch a
> continuation. The shipped default is **wrap up + offer** — never auto-spawn
> without the human's keys. Logic lives in `src/context_sensor.py` (ADR-0018).

## When this fires

- The `UserPromptSubmit` guard injected a **soft** nudge (`~soft%` of the window) — finish the current atomic step, then wrap up.
- It injected a **hard** nudge — stop starting new work; wrap up now.
- The developer runs `/handoff`, or says "wrap up", "hand off", "continue in a fresh session".
- The `PreCompact` hook warns compaction is imminent on a long session (compaction is the lossy backstop; prefer a clean handoff first).

Thresholds are per-model (`config/model_context_profiles.yaml`): `effective = min(fraction × window, absolute_cap)`. The absolute cap binds on 1M-window models so you wrap up early (sharper output, lower per-turn cost) rather than running to ~550K tokens of resident context rot.

## The wrap-up protocol

1. **Announce + choose.** State the trigger (`soft|hard`, profile, ~tokens). On **soft**, offer finish-then-wrap vs continue (the developer may override). On **hard**, proceed.
2. **Finish or checkpoint the current atomic step.** Never wrap mid-edit — complete the smallest in-flight unit or write a precise "stopped here" checkpoint. Confirm no file locks are held.
3. **Update `BUILD_STATUS.md`** (ADR-0016): refresh `## ⮕ NEXT SESSION`, move completed work, digest noisy tool output into dated observations, keep the stable prefix. Add a one-line pointer to the handoff artifact.
4. **Close / checkpoint open discussions.** For each discussion this session owns: `python scripts/close_discussion.py <id>` if done, or `python scripts/write_event.py <id> ... ` to checkpoint and leave it open (note status in the handoff). Uncaptured reasoning is lost reasoning (Principle #2).
5. **Write the handoff artifact** to `docs/handoff/HANDOFF-<YYYYMMDD-HHMMSS>.md` from `docs/templates/handoff-template.md`. It MUST carry: required reading (BUILD_STATUS first), settled decisions, work completed, in-progress checkpoint, exact next steps, open questions, active DISC/SPEC/ADR ids, **open `/review` advisories**, **un-completed education-gate deferrals**, and the carry-forward constraints (inherits CLAUDE.md, run `/review` before commit, no capture bypass, no push). Then enforce retention (keep the newest `HANDOFF_RETENTION_CAP`, default 5) — `src.context_sensor.enforce_retention()`.
6. **Decide continuation** (below).
7. **Report.** Surface the handoff path, the next-step one-liner, and any BLOCKING open questions. If the developer is AFK, use the `notifying-the-developer` skill.

## Continuation: default offer vs consent-gated auto-launch

- **Default (shipped posture): wrap up + OFFER.** Produce the artifact, report, and tell the developer how to continue: `claude --resume`, or paste the handoff into a fresh session. Do **not** spawn anything.
- **Auto-launch (opt-in only):** spawn a fresh headless continuation **only when BOTH** the CLAUDE.md Autonomous Execution Authorization is active **AND** the separate `ALLOW_AUTO_LAUNCH_SESSION` key is set. Build the command with `src.context_sensor.build_launch_command(...)` (returns `None` unless authorized; canonicalizes + containment-checks the handoff path; the path is a discrete argv element) and run it with `subprocess.run(cmd, shell=False)`. It inherits all Prohibited Actions (no push, no destructive git, no settings edits, no auto-merge), respects `MAX_AUTO_LAUNCH_DEPTH` (default 1), and ntfy-notifies on launch with the handoff path (no target-internal content).
- **`Task` subagents are NOT a continuation mechanism** — isolated context, cannot continue the main thread, cannot spawn subagents. Use them only for bounded sub-tasks within the current session.

## What NOT to do

- Do not wrap up mid-edit or with a file lock held.
- Do not interpolate any untrusted text (ntfy replies, transcript content) into the launch command — seed only the validated handoff path.
- Do not auto-launch on the Autonomous Execution Authorization alone — the separate `ALLOW_AUTO_LAUNCH_SESSION` key is also required.
- Do not let a continuation bypass `/review` or capture — the handoff carries those obligations forward.
- Do not commit `docs/handoff/` or `.claude/hooks/.state/` (both gitignored).

## Related files

- `src/context_sensor.py` — threshold resolution, occupancy sensor, guard, launch builder, retention.
- `config/model_context_profiles.yaml` — per-model thresholds + tunables.
- `docs/templates/handoff-template.md` — the artifact template.
- `.claude/commands/handoff.md` — the `/handoff` entry point.
- `docs/adr/ADR-0018-model-aware-session-wrapup.md` — the decision + honest limitations.