---
project_name: "Claude Agentic Framework (dralgorhythm)"
source: "github.com/dralgorhythm/claude-agentic-framework"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [shell, typescript, markdown, hooks, multi-agent, claude-code, swarm]
---

## Overview

"A More Effective Agent Harness for Claude." Shell/TypeScript/Markdown-based framework with 67 skills, 10 commands, 6 tiered worker agents, 9 hooks. Production-proven — March 2026 backport from a deployed "argo" project brought battle-tested improvements. Major source of hook patterns for our framework. 13 commits since February with focus on hook reliability hardening, token optimization, and swarm research capabilities.

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Shell (hooks), TypeScript (skill-activation), Markdown (definitions) |
| Framework | Claude Code native |
| Database | None (Beads for coordination) |
| Testing | None |
| CI/CD | None |
| Deployment | Local/developer tool |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Token Budget Optimization Methodology | 22/25 | ADOPT |
| Swarm Research — Verification Tiers + Confidence Vocabulary | 19/25 | ADAPT |
| Dangerous Command Guard (warn tier) | 18/25 | ADAPT |
| Two-Hat Refactoring Rule | 17/25 | ADOPT |
| Stop Hook with Uncommitted-Change Detection | 17/25 | DEFER |
| Pipe-to-Shell Deny Patterns | 16/25 | ADAPT |
| Remove set -e from Hooks | 15/25 | AUDIT (confirmed in 2 of our hooks) |
| SubagentStop Hook | 14/25 | DEFER |

## Solution Paths

### infra/token-audit — Measuring and reducing per-turn context cost

**Problem**: Per-turn token cost growing without measurement (1,763 tokens wasted per turn)
**Tried**: No measurement — context grew organically
**Chosen**: Systematic audit: enumerate all auto-loaded files, sum token cost, identify double-loading (tech-strategy.md loaded twice), relocate detail from CLAUDE.md to rule files (same info, half the overhead), condense skill files by replacing inline examples with Context7 lookups, cap skill suggestions to top 3.
**Evidence**: Commit a71238b, quantified savings in commit message
**Tags**: [infra/token-audit, infra/context-management]

### hooks/reliability — Remove set -e from all hooks

**Problem**: `set -e` causes silent failures in hooks — any non-zero exit terminates without useful output
**Tried**: Standard bash with `set -e` (inherited from templates)
**Chosen**: Remove `set -e` and `set -eo pipefail` from all hooks. Per-command error handling instead. Template comment block explicitly warns against `set -e`.
**Evidence**: Commit 57138ae, all hook files
**Tags**: [hooks/reliability, hooks/bash-patterns]

### security/command-tiers — Two-tier destructive command protection

**Problem**: Binary allow/block for destructive commands misses gray-zone commands
**Tried**: Single deny list in settings.json
**Chosen**: Two-tier approach: hard deny in settings.json (force push, rm -r, terraform destroy) + soft warn via dangerous-command-guard.sh hook (exits 0, writes to stderr for agent transcript visibility). Covers: terraform operations, docker prune, kubectl delete.
**Evidence**: .claude/hooks/dangerous-command-guard.sh, .claude/settings.json
**Tags**: [security/command-tiers, hooks/pretooluse-patterns]

## Applicability Assessment

Our primary source for hook infrastructure patterns. The token optimization methodology (22/25) is the highest-scoring pattern from this project and addresses a real problem in our growing CLAUDE.md. The set -e removal is an urgent audit item — confirmed present in 2 of our hooks. The two-tier destructive command pattern and verification tiers for research agents are strong adapts.
