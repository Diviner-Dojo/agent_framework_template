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
