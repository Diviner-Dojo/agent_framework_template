---
project_name: "self-learning-agent (slagent)"
source: "github.com/daegwang/self-learning-agent"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [typescript, node, cli, claude-code, session-observation, self-learning]
---

## Overview

CLI tool that observes AI coding agent sessions (Claude Code, Codex), analyzes sessions using an AI reviewer, and writes improvement suggestions directly into instruction files (CLAUDE.md, AGENTS.md). TypeScript 5.4 / Node.js ESM, zero runtime dependencies (stdlib-only). ~2,900 LOC across 16 source files. Very early maturity — two commits total (February 2026), no tests, no CI. Repository is frozen.

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | TypeScript 5.4 |
| Framework | Node.js ESM (stdlib-only) |
| Database | None (file-based session store) |
| Testing | None |
| CI/CD | None |
| Deployment | npm package |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Delta Review (reviewedEventCount cursor) | 17/25 | DEFER |
| Scope-Toggle at Review Time | 16/25 | DEFER |
| Confidence-Threshold Gating (minConfidence) | 17/25 | DEFER |
| Multi-Framework Test Output Parser | 15/25 | REJECT |
| Filesystem-as-Oracle Path Decode | 13/25 | REJECT |
| Ring Buffer for Event Capture | 12/25 | REJECT |

## Solution Paths

### agent-cli/subprocess — Prompt-via-stdin for CLI-spawned agents

**Problem**: OS argument length limits when passing large prompts to spawned agent CLIs
**Tried**: Command-line arguments (breaks on large prompts)
**Chosen**: Pass prompts through stdin (`child.stdin.write(prompt); child.stdin.end()`) with SIGTERM timeout on the child process
**Evidence**: src/analyzer/reviewer.ts callReviewer()
**Tags**: [agent-cli/subprocess, agent-cli/large-prompts]

### agent-cli/nested-agents — Strip CLAUDECODE env var before spawning nested agents

**Problem**: Nested agent inherits Claude Code session context, causing it to behave as if operating inside an existing session
**Tried**: Default environment inheritance
**Chosen**: Explicitly `delete env.CLAUDECODE` before spawning the subprocess
**Evidence**: src/analyzer/reviewer.ts callReviewer()
**Tags**: [agent-cli/nested-agents, agent-cli/environment-isolation]

### hooks/file-watching — Gitignore-aware file watcher (from-scratch implementation)

**Problem**: File watcher needs to respect .gitignore patterns without external dependencies
**Tried**: N/A (built from scratch)
**Chosen**: Self-contained gitignore parser reading .gitignore + .git/info/exclude, handling negation patterns, directory-only patterns, anchored patterns, and ** globbing. Zero dependencies.
**Evidence**: src/watcher/ignore.ts
**Tags**: [hooks/file-watching, infra/gitignore-parsing]

## Applicability Assessment

Frozen project with no patterns above the adoption threshold. The solution paths for subprocess spawning (stdin for large prompts, CLAUDECODE env stripping) are valuable reference knowledge if we ever spawn agent CLIs from scripts. The gitignore-aware file watcher is a proven approach if hooks need dynamic ignore support.
