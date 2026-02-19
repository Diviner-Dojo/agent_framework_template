---
description: "Search GitHub for interesting projects to analyze. Finds repos by topic, language, or keywords, checks for AI integration artifacts, and presents ranked candidates for /analyze-project."
allowed-tools: ["Read", "Bash", "Glob", "Grep"]
argument-hint: "[search query — topic, technology, or keywords]"
---

# Discover Projects on GitHub

You are acting as the Facilitator. This command helps the developer find external projects worth analyzing with `/analyze-project`.

## Step 1: Understand the Search Intent

Accept a search query from the developer. This can be:
- A technology or framework (e.g., "fastapi", "next.js", "rust cli")
- A topic (e.g., "agentic coding", "code review automation")
- A specific query (e.g., "claude code template", "multi-agent development")
- A problem domain (e.g., "todo api best practices", "authentication patterns")

## Step 2: Search GitHub for Repositories

Run a repository search sorted by stars:

```bash
gh search repos "<query>" --stars=">50" --sort=stars --limit=20 --json fullName,stargazersCount,description,language,updatedAt
```

If the developer specified a language, add `--language=<lang>`:
```bash
gh search repos "<query>" --language=python --stars=">50" --sort=stars --limit=20 --json fullName,stargazersCount,description,language,updatedAt
```

If the developer is looking for recent/active projects, add `--updated=>2025-01-01`:
```bash
gh search repos "<query>" --stars=">50" --sort=stars --updated=">2025-01-01" --limit=20 --json fullName,stargazersCount,description,language,updatedAt
```

## Step 3: Check for AI Integration Artifacts (Optional)

For the top 5-10 candidates, check if they have Claude Code or AI integration:

```bash
gh search code --filename CLAUDE.md --json repository,path | grep -i "<repo-name>"
```

Or check for `.claude/` directory content:
```bash
gh api search/code -f "q=path:.claude/ repo:<owner/repo>" --jq '.total_count'
```

For a quick check on a specific repo:
```bash
gh repo view <owner/repo> --json description,repositoryTopics,stargazerCount --jq '{stars: .stargazerCount, desc: .description, topics: [.repositoryTopics[].name]}'
```

## Step 4: Present Ranked Candidates

Display a table to the developer:

```
## GitHub Search Results: "<query>"

| # | Repository | Stars | Language | Last Updated | AI Integration | Description |
|---|-----------|-------|----------|-------------|----------------|-------------|
| 1 | owner/repo | 5.2k | Python | 2026-02-15 | CLAUDE.md | Brief description |
| 2 | owner/repo | 3.1k | TypeScript | 2026-01-20 | None | Brief description |
| ... | | | | | | |
```

For each candidate with AI integration artifacts, briefly note what was found (e.g., "Has CLAUDE.md + 5 agent definitions" or "Has .cursorrules only").

## Step 5: Developer Selection

Ask the developer which projects they'd like to analyze in depth.

For each selected project, suggest running:
```
/analyze-project <owner/repo>
```

## Tips for Effective Searches

- **Find Claude Code projects**: `gh search repos --topic=claude-code --sort=stars`
- **Find projects with CLAUDE.md**: `gh search code --filename CLAUDE.md`
- **Find well-maintained projects**: Add `--updated=">2025-06-01"` and `--stars=">200"`
- **Find by specific topic**: `gh search repos --topic=<topic> --sort=stars`
- **Narrow by license**: Add `--license=mit` or `--license=apache-2.0`
- **Check a repo before cloning**: `gh repo view <owner/repo>` shows README in terminal
