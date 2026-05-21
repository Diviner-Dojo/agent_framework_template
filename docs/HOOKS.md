# Hooks

> Claude Code lifecycle hooks (configured in `.claude/settings.json`).
> Referenced from CLAUDE.md (kept slim per ADR-0016). Hooks are the framework's
> mechanical enforcement layer — they run regardless of what the model decides.

## PreToolUse
- **File Locking + Secret Detection + Protected Files** (`pre-tool-use-validator.sh` → `validate_tool_use.py`): on Write/Edit — acquires atomic file locks (prevents concurrent agent edits, 120s auto-expiry), blocks edits to protected files (.env, .git/, evaluation.db, .claude/settings.json), scans content for 12 secret patterns (API keys, AWS keys, JWT, GitHub PATs, private keys, exported secrets, Slack tokens, Bearer tokens, Anthropic keys, OpenAI keys, GCP API keys, GCP OAuth tokens). Test files are exempt from secret scanning.
- **Pre-Commit Quality Gate** (`pre-commit-gate.sh`): on `git commit` — injects a reminder to run `python scripts/quality_gate.py`. 5-minute verification cache to avoid repetition.
- **Pre-Push Main Blocker** (`pre-push-main-blocker.sh`): on `git push` — blocks direct pushes to main/master with branch-workflow remediation.

## PostToolUse
- **Auto-Format** (`auto-format.sh`): runs `ruff format` + `ruff check --fix` on any Python file after every Edit or Write.
- **Lock Release** (`post-tool-use-unlock.sh` → `release_lock.py`): releases file locks after Write/Edit completes.

## Session
- **PreCompact** (`pre-compact.ps1`): before context compaction, prompts the agent to update `BUILD_STATUS.md`.
- **SessionStart** (`session-start.ps1`): on resume/post-compaction, prompts the agent to read `BUILD_STATUS.md` and runs a 6-point process-health dashboard (retro age, open retro actions, pending adoptions, promotion candidates, stale specs, Layer-3 health).

## Notification (optional)
- **Notification**: fires a system notification when Claude Code completes a task. Platform-specific setup — see `docs/setup/notification-hook.md`.

## BUILD_STATUS.md lifecycle
Session-scoped working state at the project root. Ephemeral and distinct from the four-layer capture stack — it preserves in-flight context across sessions rather than capturing completed decisions. Open advisories from reviews accumulate here so they persist across sessions until addressed.

**Incremental Summary Merging**: when updating BUILD_STATUS.md before compaction, preserve the previous session's content under a `## Previous Session (YYYY-MM-DD HH:MM)` heading rather than overwriting. Cap at 3 retained previous sessions (remove the oldest when adding a fourth).

**Tool-output digest (ADR-0016 / Mastra-inspired)**: when summarizing during compaction, digest noisy tool output (logs, file dumps, search results) into compact dated observations rather than verbatim text, and keep the stable prefix stable to maximize prompt-cache hits. Compress tool results that were useful for one step but are noise for every subsequent turn.
