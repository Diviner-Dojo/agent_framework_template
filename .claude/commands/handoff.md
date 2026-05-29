---
description: Cleanly wrap up the current session and write a paste-ready handoff prompt (ADR-0018). Optionally launch a consent-gated continuation. The deterministic entry point for the wrapping-up-sessions skill.
allowed-tools: ["Read", "Write", "Edit", "Bash", "Task"]
argument-hint: "[--launch headless|none] [--soft|--hard]"
---

# /handoff — Session Wrap-Up & Handoff

You are wrapping up the current session on demand. This command is a thin, deterministic
entry point — **the protocol lives in the `wrapping-up-sessions` skill**. Load that skill
and execute its wrap-up protocol. Do not duplicate its steps here.

## Arguments

- `--launch none` (default): produce the handoff artifact and STOP — report the path and
  how to continue (`claude --resume` / paste). Never spawns a process.
- `--launch headless`: request a consent-gated auto-launch. This proceeds **only if** the
  CLAUDE.md Autonomous Execution Authorization is active **AND** `ALLOW_AUTO_LAUNCH_SESSION`
  is set. If either is absent, fall back to `--launch none` and say why.
- `--soft` / `--hard`: treat this as a soft (finish-then-wrap) or hard (wrap now) trigger.
  Defaults to soft when invoked manually.

## What to do

1. Invoke the **`wrapping-up-sessions`** skill and run its protocol end to end:
   finish/checkpoint the current step → update `BUILD_STATUS.md` → close/checkpoint open
   discussions → write `docs/handoff/HANDOFF-<ts>.md` from the template (including open
   `/review` advisories + education deferrals + carry-forward constraints) → enforce
   retention → decide continuation → report.
2. For continuation, use `src.context_sensor.build_launch_command(...)` and only
   `subprocess.run(cmd, shell=False)` if it returns a non-`None` command. Seed it with the
   validated handoff path only — never inline untrusted text.
3. Report the handoff path, the one-line next step, and any BLOCKING open questions.

## Guardrails

- Never push, force-push, or auto-merge.
- Never auto-launch without BOTH consent keys.
- Never wrap up mid-edit or with a file lock held.
- `docs/handoff/` and `.claude/hooks/.state/` are gitignored — do not stage them.