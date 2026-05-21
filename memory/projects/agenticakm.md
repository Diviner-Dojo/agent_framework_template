---
project_name: "AgenticAKM"
source: "github.com/sa4s-serc/AgenticAKM"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [python, jupyter, gemini, openai, adr-generation, academic-research]
---

## Overview

Academic research system (ICSE 2025 paper) demonstrating that a multi-agent pipeline generates higher-quality ADRs from code repositories than a single-prompt LLM approach. Validated through a user study across 29 repositories. Python 3.12, Google Gemini API, OpenAI API, Pydantic. ~700 LOC core + 1,446 generated ADR files. Research-grade — no tests, no CI/CD. Repository is frozen (no code changes since October 2025).

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Python 3.12 |
| Framework | None (Jupyter notebooks + single module) |
| Database | None |
| Testing | Manual (human evaluation study) |
| CI/CD | None |
| Deployment | Research artifact |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Decomposed Context Construction (Three-Signal Intake) | 17/25 | DEFER |
| Empirical Approach Comparison as Validation Strategy | 16/25 | REJECT |
| Feedback-Loop Halt with Best-Effort Continuation | 15/25 | REJECT (already have equivalent) |

## Solution Paths

### agent-workflow/best-effort-continuation — Continue on verification failure

**Problem**: When a verification agent rejects intermediate output, should the orchestrator halt or continue?
**Tried**: Halt-on-failure (return empty list if max attempts exceeded) — coded then deliberately commented out
**Chosen**: Best-effort continuation — proceed with best available output even if unverified. At corpus scale (29 repos), halt-on-failure produces gaps that cannot be filled retroactively.
**Evidence**: Code/AdrAgents.py OrchestratorAgent.run() lines ~430-490 (commented-out halt logic)
**Tags**: [agent-workflow/best-effort-continuation, agent-workflow/verification-loops]

### data/key-file-selection — File-size ranking fails on vendor-heavy repos

**Problem**: Which files in an unknown repository deserve LLM attention when context is limited?
**Tried**: Largest N files by byte size — vendor/library files (angular.js, jquery.js) dominate in frontend repos
**Chosen**: Size ranking fails without filtering dist/, build/, vendor/, node_modules/. The code filters node_modules but not dist/. Known-broken approach.
**Evidence**: Code/AdrAgents.py RepoSummarizer._summarize_key_files()
**Tags**: [data/key-file-selection, agent-workflow/context-construction]

## Applicability Assessment

Frozen research artifact. The best-effort continuation solution path confirms our own build_review_protocol.md Round 2 continuation design. The file-size ranking failure is a documented anti-pattern worth knowing if we ever add automated key-file selection to /analyze-project. No further analysis warranted unless the repo receives new commits.
