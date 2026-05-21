# Handoff: Add `/status` Command + Git Visualizer

**Source**: `Diviner-Dojo/agent_framework_template`, branch `feature/project-analysis-backport`  
**Date**: 2026-04-06

## Context

The framework template now has a `/status` slash command that generates an interactive browser-based visual map of the git repo. This handoff adds it to any project that uses the template.

## What to add — 2 files

### File 1: `scripts/git_visualize.py`

Copy this file from the template repo. The source is:

```
https://github.com/DanEvans-collab/AGENT_FRAMEWORK_TEMPLATE_EXPLORATORY.git
Branch: feature/project-analysis-backport
Path: scripts/git_visualize.py
```

This is a standalone Python script (stdlib only, no pip dependencies) that:

- Parses `git log`, `git branch`, `git remote`, `git stash`, and `git status`
- Generates an interactive HTML infographic and opens it in the browser
- Shows three zones left-to-right: **Public Repo** (upstream) → **Your GitHub Copy** (origin) → **Your Computer** (local)
- Color-coded branches with plain-English explanations (book/desk metaphors)
- Health bar at top: sync status, active branches, cleanup opportunities, unsaved changes
- Remote/upstream branches collapsed by default with "what are these?" explainers
- Bottom cards for uncommitted files and stashes
- Run with `python scripts/git_visualize.py` (or `--no-open` to generate without opening)

If this project doesn't have an `upstream` remote, the script still works — the upstream zone will just be empty. If the project only has `origin`, that's fine too.

### File 2: `.claude/commands/status.md`

Create this file with the following exact content:

```markdown
---
description: "Show repository status: interactive visual map of branches, sync state, and working directory health. Opens a browser-based infographic."
allowed-tools: ["Bash", "Read"]
---

# Repository Status

Run the git visualizer to generate an interactive map of the repository:

```bash
python scripts/git_visualize.py
```

After the visualization opens in the browser, provide a brief text summary:

1. **Where you are**: Current branch and what you're working on (last commit message)
2. **Sync status**: Whether your repo is in sync with upstream
3. **Cleanup opportunities**: Any merged branches that can be deleted, stale stashes
4. **Unsaved work**: Any uncommitted or untracked files

Keep the text summary to 5-6 lines max — the visual has the detail.
```

## Verification

After adding both files, run:

```bash
python scripts/git_visualize.py
```

A browser tab should open showing the repo map. Then test `/status` from Claude Code.

## Adaptation notes

- If this project has different remote names (not `origin`/`upstream`), the script auto-detects whatever remotes exist
- No changes needed to `CLAUDE.md` — this is a utility command, not a framework-level feature
- No dependencies to install — it's pure Python stdlib
