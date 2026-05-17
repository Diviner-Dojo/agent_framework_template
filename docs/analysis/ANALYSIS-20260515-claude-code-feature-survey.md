---
analysis_id: ANALYSIS-20260515-claude-code-feature-survey
analyst: claude-code-guide
date: 2026-05-15
scope: Built-in slash commands, telemetry, observability, hooks, MCP, agents, output styles, IDE integration, CLI features
status: summary-only (full deep-dive deferred — see Recovery Note at bottom)
---

# Claude Code Feature Survey + Gap Analysis

## Executive Summary

This project has built a sophisticated 12-agent agentic framework with 17 custom slash commands, deep capture pipelines, and multi-layer memory systems. However, the current setup is missing three high-value observability features that would dramatically improve the developer's ability to understand and optimize their own use of Claude Code.

## Top 3 Missed Opportunities (Ranked)

### 1. `/insights` — Local Usage Analytics  **[HIGH VALUE, NOT USING]**

- **What it does**: Analyzes the last 30 days of Claude Code sessions and generates an interactive HTML report with activity trends, friction points, and personalized CLAUDE.md improvements.
- **Why it matters here**: This developer maintains a 12-agent / 17-command framework. They have no data on which agents and commands actually get used vs. sit idle. `/insights` answers this directly.
- **How to use**: Run `claude /insights` in the terminal.
- **Cross-project**: Run separately in each derived project (agent_framework_template, Howie Family Wiki, Insight Journal); aggregate manually or via a small custom script.
- **Effort**: S (single command, no config).
- **Source**: [Claude Code usage analytics](https://support.claude.com/en/articles/12157520-claude-code-usage-analytics)

### 2. OpenTelemetry Export — Cost & Token Tracking at Scale  **[HIGH VALUE, NOT USING]**

- **What it does**: Streams real-time traces, metrics, and logs to observability backends (Honeycomb, Datadog, Grafana, local OTLP collector).
- **Why it matters here**: The framework already logs token costs to `metrics/quality_gate_log.jsonl` (ADR-0013), but there is no export path or cross-project aggregation. OTEL provides unified visibility across the template + every derived project.
- **How to enable**:
  ```bash
  export CLAUDE_CODE_ENABLE_TELEMETRY=1
  export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317  # or cloud provider
  claude
  ```
- **Value**: Agent-level cost breakdown, cache efficiency, cross-project aggregation, retroactive analysis without re-parsing JSONL.
- **Effort**: M (env vars + local collector or cloud destination).
- **Sources**: [Observability with OpenTelemetry](https://code.claude.com/docs/en/agent-sdk/observability), [Monitor Claude Code activity with OpenTelemetry](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry)

### 3. `/team-onboarding` — Derived Project Setup Guide Generation  **[MEDIUM VALUE, NOT USING]**

- **What it does**: Auto-generates a markdown onboarding guide from your 30-day usage history that derived projects can paste as a first message to inherit your setup.
- **Why it matters here**: Directly solves the "how do I onboard a new project into this framework" problem without manual documentation. Synergizes with the existing `/seed` and `/spawn-project` commands.
- **How to use**: `claude /team-onboarding` → returns shareable markdown.
- **Effort**: S (single command).
- **Source**: [Claude Code usage analytics](https://support.claude.com/en/articles/12157520-claude-code-usage-analytics)

## Survey Areas Covered (per the agent run)

The agent reported having reviewed the following dimensions. Detailed breakdowns by category were prepared but not written to file due to token budget at the end of the run (see Recovery Note).

- **Built-in slash commands**: ~131+ surveyed; cross-referenced against this project's 17 custom commands in `.claude/commands/`. Custom coverage assessed as "excellent" — no redundant duplication with built-ins identified.
- **Custom slash commands**: All 17 actively used.
- **Telemetry**: `/insights`, OTEL export, JSONL transcript locations (`~/.claude/projects/<slug>/*.jsonl`), team analytics endpoints.
- **Hook events**: 23 hook events available in Claude Code; **this project uses 7** — gap of 16 unused hook events. (Specific list of unused events not captured in the summary; needs follow-up.)
- **MCP servers**: 2 currently registered (`sqlite`, `agent-memory`); both actively used.
- **Agents**: 12 defined; 10 actively used. **2 partially used**: `ux-evaluator`, `history-analyst`. (Worth investigating: are they under-dispatched or under-relevant to actual change profiles?)
- **Output styles, settings hierarchy, IDE integrations, CLI features**: surveyed; no critical gaps flagged in summary.
- **Plan mode, fast mode, effort-level tuning**: flagged as "opportunities for optimization" — specifics not captured.

## Source References (verified URLs from the run)

- [Claude Code usage analytics | Claude Help Center](https://support.claude.com/en/articles/12157520-claude-code-usage-analytics)
- [Track team usage with analytics — Claude Code Docs](https://code.claude.com/docs/en/analytics)
- [Observability with OpenTelemetry — Claude Code Docs](https://code.claude.com/docs/en/agent-sdk/observability)
- [Monitor Claude Code activity with OpenTelemetry](https://support.claude.com/en/articles/14477985-monitor-claude-cowork-activity-with-opentelemetry)
- [Commands reference — Claude Code Docs](https://code.claude.com/docs/en/commands.md)
- [Hooks reference — Claude Code Docs](https://code.claude.com/docs/en/hooks.md)
- [Skills reference — Claude Code Docs](https://code.claude.com/docs/en/skills.md)
- [MCP connector guide — Claude Code Docs](https://code.claude.com/docs/en/mcp.md)
- [Settings hierarchy — Claude Code Docs](https://code.claude.com/docs/en/settings.md)
- [Model configuration — Claude Code Docs](https://code.claude.com/docs/en/model-config)
- [VS Code extension — Claude Code Docs](https://code.claude.com/docs/en/vs-code)
- [Interactive mode & keybindings — Claude Code Docs](https://code.claude.com/docs/en/interactive-mode)
- [Claude Code on the web](https://code.claude.com/docs/en/claude-code-on-the-web)

## Recovery Note

The original background agent (`claude-code-guide`) completed its research but ran out of response budget while attempting to inline the full report in its return message — it never invoked the `Write` tool. The structured summary captured here represents the agent's load-bearing findings. The following deep-dive sections were prepared but not preserved:

- Full table of 131+ built-in slash commands with USING / NOT USING labels.
- Specific list of which 16 hook events are unused and which would be high-value to add.
- Output-style and settings-hierarchy gap analysis.
- Plan-mode / fast-mode / effort-level tuning recommendations.

If the deliberation step needs any of these expanded, a focused follow-up agent can drill into the specific area — the costliest discovery work (cataloging features, mapping current usage) is done; only the surface area of the writeup was lost.

## Recommendations Carried into Deliberation

1. **Adopt `/insights` immediately** as a cost-free, high-signal check on framework actual-vs-intended usage.
2. **Adopt OTEL export** before the next derived project hits production scale — aligns with ADR-0013 and the dual-repo governance model.
3. **Investigate the 2 partially-used agents** (`ux-evaluator`, `history-analyst`) during the cross-agent deliberation — are they mis-scoped or do we need to fix dispatch heuristics?
4. **Audit the 16 unused hook events** — fast follow-up agent can produce the inventory.
