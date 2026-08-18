---
name: wrapping-up-sessions
description: Model-aware session wrap-up + handoff (ADR-0018, ADR-0033). Use when a soft or hard checkpoint nudge fired, when the developer says wrap up / hand off / continue in a fresh session / context is running low, or when a long session should cleanly checkpoint before it ends or auto-compaction destroys the thread. Covers the threshold model, the wrap-up protocol, the handoff artifact, and the consent-gated auto-launch continuation.
---

# Wrapping Up Long Sessions

> Once a session crosses a **model-specific** threshold, it cleanly checkpoints:
> finish the current step, capture state, write a paste-ready handoff, then (only
> with explicit consent) launch a continuation. The shipped default is **wrap up +
> offer** — never auto-spawn without the human's keys. Logic lives in
> `src/context_sensor.py` (ADR-0018 structure, ADR-0033 cap values).
>
> **The point is that the thread survives, not that the model is degrading.** The
> caps exist for cost and handoff headroom; Anthropic documents no quality cliff
> and states capability holds across the full 1M window (ADR-0033, 2026-08-08).

## When this fires

- The `UserPromptSubmit` guard injected a **soft** checkpoint nudge — finish the current atomic step, then wrap up.
- It injected a **hard** checkpoint nudge — stop starting new work; wrap up now.
- The developer runs `/handoff`, or says "wrap up", "hand off", "continue in a fresh session".
- The `PreCompact` hook warns compaction is imminent on a long session (compaction is the lossy backstop; prefer a clean handoff first).

Thresholds are per-model (`config/model_context_profiles.yaml`): `effective = min(fraction × window, absolute_cap)`. The absolute cap binds on 1M-window models, so the trigger there is a *decided* number rather than a by-product of window size; the percentage binds on 200K models.

**The nudge you received carries no numbers, and that is deliberate.** Occupancy, percentage, and threshold decide *whether* you are told to checkpoint; they are no longer part of *what* you are told. Surfacing a remaining-token count to a model is a documented cause of premature wrap-up — of a session trimming its own work or proposing a fresh start while it still had ample room. So: **do not go hunting for the figure to fill the gap, and do not shorten your work on account of context.** The readout still exists — for the developer, on the terminal status line. A checkpoint nudge means *write the handoff so the thread survives*, not *you are running out of room*.

**Do not infer a threshold from this page — read the config.** Governing record: **ADR-0033** (`docs/adr/ADR-0033-wrapup-cap-recalibration.md`, § *Derivation, re-anchored on documented and measured numbers*); the live numbers are the config's `CAP RECALIBRATION` block. The caps are anchored on Anthropic's documented server-side compaction default trigger plus the measured cost of writing one handoff: they exist for **cost and handoff headroom, not because output quality degrades**.

> **RETIRED 2026-08-08: no documented quality cliff.** Earlier versions of this page justified the caps by "the bottom edge of the researched effective-working-fraction band" and cited a governing record — "ADR-0018, Amendment 2026-08-07" — that **does not exist**: that amendment was an in-place rewrite of an immutable ADR and was reverted, so the citation pointed at deleted text. The band is third-party, older, and measured on earlier model generations; Anthropic publishes no degradation threshold and states capability holds across the full 1M window. Both claims are withdrawn. If you are reading a downstream copy that still contains either, it predates 2026-08-08.

If a nudge looks premature, check which profile resolved (the status line marks `~` normalized / `?` defaulted / `!` window cross-check disagrees) before assuming the caps are wrong.

## The wrap-up protocol

1. **Announce + choose.** State the trigger — level (`soft|hard`) and profile, with **no token count, percentage, or occupancy figure**. That holds for every step below too: the rule above governs what you *write*, not only what you were told, and the readout is not yours to fetch — it is the developer's, on their status line. On **soft**, offer finish-then-wrap vs continue (the developer may override). On **hard**, proceed.
2. **Finish or checkpoint the current atomic step.** Never wrap mid-edit — complete the smallest in-flight unit or write a precise "stopped here" checkpoint. Confirm no file locks are held.
3. **Update `BUILD_STATUS.md`** (ADR-0016): refresh `## ⮕ NEXT SESSION`, move completed work, digest noisy tool output into dated observations, keep the stable prefix. Add a one-line pointer to the handoff artifact.
4. **Close / checkpoint open discussions.** For each discussion this session owns: `python scripts/close_discussion.py <id>` if done, or `python scripts/write_event.py <id> ... ` to checkpoint and leave it open (note status in the handoff). Uncaptured reasoning is lost reasoning (Principle #2).
5. **Write the handoff artifact** to `docs/handoff/HANDOFF-<YYYYMMDD-HHMMSS>.md` from `docs/templates/handoff-template.md`. **Do not fill in that template's occupancy slot.** Its "What this is" field still asks why the wrap-up fired as `(soft/hard, profile, ~tokens)`; write the level and the profile, leave the third out, and do not go looking for what would go in it. Step 1 is the nearer and more explicit instruction, and the template is stale on that point rather than authoritative — it predates ADR-0033's amendment 2 and has not yet been re-cut (ADR-0033, § *Carry-forward — the handoff template was not re-cut*). It MUST carry: required reading (BUILD_STATUS first), settled decisions, work completed, in-progress checkpoint, exact next steps, open questions, active DISC/SPEC/ADR ids, **open `/review` advisories**, **un-completed education-gate deferrals**, and the carry-forward constraints (inherits CLAUDE.md, run `/review` before commit, no capture bypass, no push). Then enforce retention (keep the newest `HANDOFF_RETENTION_CAP`, default 5) — `src.context_sensor.enforce_retention()`.
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
- `docs/templates/handoff-template.md` — the artifact template. Stale on one point, and not yet re-cut: its trigger field still asks for `~tokens`, which step 5 tells you not to fill.
- `.claude/commands/handoff.md` — the `/handoff` entry point.
- `.claude/hooks/context_guard.py` — the **model-facing** surface (figure-free by design).
- `.claude/hooks/context_statusline.py` — the **developer-facing** surface (keeps every number).
- `docs/adr/ADR-0033-wrapup-cap-recalibration.md` — **governing record** for the cap values, the documented anchor, and the no-countdown decision.
- `docs/adr/ADR-0018-model-aware-session-wrapup.md` — the original decision + honest limitations. Superseded on the 1M cap VALUES only; still governs the threshold structure, consent model, and sensor design. Immutable — record disagreements in a superseding ADR, never by editing it.