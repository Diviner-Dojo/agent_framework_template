---
project_name: "claude-agents (wshobson/agents)"
source: "github.com/wshobson/agents"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [markdown, python, plugin-system, multi-agent, claude-code, skill-library]
---

## Overview

Intelligent automation and multi-agent orchestration for Claude Code. Markdown-based plugin system with Python 3.12+ tooling. 75 plugins, ~182 agents, ~147 skills, ~95 commands. The dominant feature since February is PluginEval — a three-layer quality evaluation framework (static analysis, LLM judge, Monte Carlo simulation) with Elo-based pairwise comparison and badge certification. Very actively maintained (76 commits since Feb 2026, updated daily).

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Markdown (plugins), Python 3.12+ (eval tooling) |
| Framework | Typer (CLI), Pydantic (models) |
| Database | None (file-based) |
| Testing | pytest (12 test files for PluginEval) |
| CI/CD | None |
| Deployment | Plugin marketplace |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Anchored Rubric Design for LLM Evaluation | 20/25 | ADOPT |
| Named Anti-Pattern Detection with Multiplicative Penalty | 18/25 | ADAPT |
| Three-Layer Quality Evaluation with Blend Weights | 17/25 | DEFER |
| Delegated Context Isolation for Large Tool Outputs | 15/25 | DEFER |

## Solution Paths

### agent-eval/anchored-rubrics — Calibrating LLM judges with concrete examples

**Problem**: LLM evaluators score inconsistently without calibration reference points
**Tried**: Abstract scale descriptions ("score 1-5")
**Chosen**: Anchored rubrics — explicit text examples at each score level (0.0, 0.25, 0.5, 0.75, 1.0) for each dimension. F1 operationalization for triggering accuracy (10 mental test prompts: 5 should-trigger, 5 should-not).
**Evidence**: plugins/plugin-eval/agents/eval-judge.md, plugins/plugin-eval/skills/evaluation-methodology/references/rubrics.md
**Tags**: [agent-eval/anchored-rubrics, agent-eval/llm-judge-design]

### agent-eval/anti-pattern-catalog — Named flags for structural problems

**Problem**: Quality issues in agent definitions have no canonical identifiers for tracking
**Tried**: Ad-hoc review comments
**Chosen**: Named anti-pattern catalog (OVER_CONSTRAINED, EMPTY_DESCRIPTION, MISSING_TRIGGER, BLOATED_SKILL, ORPHAN_REFERENCE, DEAD_CROSS_REF) with multiplicative penalty (5% per flag, floor at 50%). Used retroactively to drive corpus-wide improvement campaign.
**Evidence**: plugins/plugin-eval/src/plugin_eval/layers/static.py, CLAUDE.md
**Tags**: [agent-eval/anti-pattern-catalog, quality/static-analysis]

### agent-eval/token-optimization — Measuring and reducing per-turn context cost

**Problem**: Framework context cost growing without measurement
**Tried**: No measurement (context grew organically)
**Chosen**: Systematic audit: identified double-loading (tech-strategy.md), relocated detail from CLAUDE.md to rule files, condensed skill files (35-59% reduction), capped skill suggestions to top 3. Result: -1,763 tokens/turn base, -7,000 tokens/turn per 4-worker swarm.
**Evidence**: Commit a71238b, .claude/rules/agent-constraints.md
**Tags**: [agent-eval/token-optimization, infra/context-management]

## Applicability Assessment

The project's direction is complementary to ours: they evaluate AI artifact quality; we govern AI-assisted development reasoning. The anchored rubric pattern is the most directly transferable — applicable to any agent that returns scored judgments (educator, independent-perspective, adoption evaluator). The anti-pattern detection OVER_CONSTRAINED flag is applicable to our agent definitions. The token optimization methodology is a critical practice we should adopt.
