---
project_name: "self_improving_coding_agent"
source: "github.com/MaximeRobeyns/self_improving_coding_agent"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [python, fastapi, multi-agent, self-improving, llm-tools, benchmarks]
---

## Overview

Self-modifying multi-agent framework that evaluates and rewrites its own code across benchmark iterations. Python 3.11+, FastAPI, asyncio, Anthropic/OpenAI/Google/Vertex/Fireworks/DeepSeek providers, tiktoken. ~26,700 LOC with ~85 source files. Features a full callgraph system tracking every agent execution as a DAG, an async LLM oversight module, a review committee tool with four named specialist reviewers, and a FastAPI web server with WebSocket push for live callgraph visualization.

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Python 3.11+ |
| Framework | FastAPI (web server) |
| Database | None (in-memory callgraph, file-based persistence) |
| Testing | pytest (14 test files) |
| CI/CD | None |
| Deployment | Docker |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Deterministic Seeded Metrics Factory | ~20/25 | ADOPT |
| Named-Role Review Committee with Model-Tier Differentiation | — | ADAPT |
| Adaptive Overseer Scheduling | — | DEFER |
| Execution Tree Injection Post-Sub-Agent-Return | — | DEFER |
| Ephemeral Per-Step Tool Injection (refinement) | — | Already adopted |
| Depth-Ordered Batch Cancellation | — | Footnote |
| Header-Driven Rate Limit Reservation | — | Footnote |
| Self-Referential Agent-Aware README | — | DEFER |

## Solution Paths

### llm/cache-stability — Dynamic budget in prefill breaks KV cache

**Problem**: Including cost/budget data in agent prefill messages invalidates KV cache for the entire conversation
**Tried**: Budget field in prefill messages (causes 25% cost increase instead of 90% cost decrease)
**Chosen**: Remove budget field from prefill entirely; track separately in callgraph. Never inject changing metrics into agent context.
**Evidence**: src/types/agent_types.py lines 141-158 (commented-out code with explanation)
**Tags**: [llm/cache-stability, llm/cost-optimization]

### agent-workflow/anti-loop — Embedding behavioral guardrails in tool responses

**Problem**: Agents getting stuck in planning loops, submitting to review committee repeatedly
**Tried**: Prompt-level "don't loop" instructions
**Chosen**: Anti-loop instruction embedded directly in the tool response: "If this is your third time submitting, prioritize action over endless design." Tool output as behavioral guardrail.
**Evidence**: src/tools/committee_design.py
**Tags**: [agent-workflow/anti-loop, agent-workflow/tool-design]

### agent-workflow/context-amnesia — Injecting execution tree post-sub-agent-return

**Problem**: Orchestrator loses track of what earlier sub-agents actually did
**Tried**: Relying on sub-agent self-reported summaries
**Chosen**: After every sub-agent returns, override `_handle_agent_call` to inject the full callgraph execution tree as an OVERSEER_NOTIFICATION into the orchestrator's own context — verified ground truth rather than self-reported summary.
**Evidence**: src/agents/implementations/main_orchestrator.py lines 149-169
**Tags**: [agent-workflow/context-amnesia, agent-workflow/orchestration]

### testing/deterministic-fixtures — Seeded metrics factory

**Problem**: Test fixtures for agent systems either mock everything (brittle) or call real APIs (slow/expensive)
**Tried**: Mocking, real API calls
**Chosen**: `make_random_agent_metrics(seed=42)` — generates fully deterministic, structurally valid, internally consistent metrics objects. Fixed `base_time = datetime(2025, 1, 1)` avoids datetime.now() nondeterminism.
**Evidence**: src/utils/metrics.py lines 14-95
**Tags**: [testing/deterministic-fixtures, testing/agent-testing]

## Applicability Assessment

The most technically sophisticated project analyzed. Its primary contributions are the deterministic test fixtures pattern (directly applicable to our test suite) and the role-to-model-tier differentiation in review committees (refinement of our existing model-override capability). The KV cache stability solution path is critical knowledge for any future work injecting dynamic data into agent context.
