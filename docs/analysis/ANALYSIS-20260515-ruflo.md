---
analysis_id: ANALYSIS-20260515-ruflo
repo: https://github.com/ruvnet/ruflo
analyst: project-analyst
date: 2026-05-15
status: summary-only (recovery run after socket error; agent did not invoke Write)
---

# ruvnet/ruflo

## Profile

- **Type**: High-scale TypeScript multi-agent orchestration platform for Claude Code
- **Origin**: Formerly "claude-flow," renamed by ruvnet
- **Scale signals**:
  - **51,547 stars** — exceptional adoption
  - 32 plugins
  - 300+ MCP tools
  - 3-tier model routing
  - Swarm coordination
  - Self-learning neural loop
  - Dual Claude + Codex collaboration
- **Scale mismatch**: Operates at a fundamentally different scale than our framework. Most of its patterns (swarm orchestration, WASM Agent Booster, IPFS pattern transfer, AgentDB) do not apply.

## Notable Patterns

### Pattern 1 — Agent Prompt Token-Diet (REFERENCE.md split)  **[20/25 — meets adoption threshold]**

Agent definitions kept **lean** (role, tools, pointer); reference data (templates, recipes, checklists) moved to a companion `REFERENCE.md` read **on-demand**.

**Quantified**: ~40% fewer tokens per spawn.

**Applicability**: Directly applicable to our most bloated agent definitions: **architecture-consultant, independent-perspective, docs-knowledge**. Low adoption cost (file split + agent prompt update). Aligns with Principle #8 (least-complex intervention).

**Synergy with ADR-0013**: We already log token cost. This pattern attacks token cost at the source.

### Pattern 2 — Given/When/Then Acceptance Criteria Format

**Source**: The SPARC methodology plugin within ruflo

A format improvement to our `/plan` spec output. No architectural cost — pure formatting convention.

**Applicability**: Low effort, applies to `/plan` and possibly `/build_module` spec templates.

### Adjacent Pattern — Budget Alert Ladder

4-tier alert ladder: **50% / 75% / 90% / 100%** of budget.

**Applicability**: Worth adapting as an **extension to ADR-0013** (token-efficiency telemetry). Adds proactive cost signals rather than passive logging.

## Cross-Reference to This Framework

- **Pattern 1 (REFERENCE.md split)** targets our most token-heavy agents. With ADR-0013 already in place, we can measure the impact directly.
- **Pattern 2 (Given/When/Then)** plugs into `/plan` template without disturbing spec frontmatter conventions.
- **Budget alert ladder** is the most strategically interesting — it transforms our current passive telemetry into active alerting. Sits naturally in the quality-gate or session-start hook.

## Patterns NOT Applicable

- Swarm orchestration — we deliberately use single-facilitator orchestration
- WASM Agent Booster — performance optimization at scales we don't approach
- IPFS pattern transfer — distributed knowledge layer not needed
- AgentDB — we already have our own SQLite-based Layer 2 substrate

## Top 3 Recommendations

1. **Adopt REFERENCE.md split for the 3 most token-heavy agents** — Effort: S–M, Scope: framework, Value: ~40% token reduction per spawn (cite-claim from ruflo, verify with our ADR-0013 telemetry).
2. **Adopt Given/When/Then format in `/plan` acceptance criteria** — Effort: S, Scope: framework, Value: clearer spec acceptance signals.
3. **Extend ADR-0013 with budget alert ladder** — Effort: M, Scope: framework, Value: proactive cost signals rather than passive logging.

## Verdict

- **Best pattern adoption score**: **20/25** (REFERENCE.md split — meets threshold)
- **Overall recommendation**: **CONDITIONAL ADOPT** — extract the three named patterns; ignore the swarm/distributed/WASM machinery, which is a scale mismatch.

## Recovery Note

This is the second run of the ruflo analysis. The original run crashed with a socket error after 51 tool uses (no report written). The recovery run completed but claimed "the Write tool is blocked in subagent context" — a recurring hallucination across multiple project-analyst dispatches. The full 370-line report the agent claimed to have produced was not actually returned in its response payload; only this summary was. The load-bearing adoption recommendations (REFERENCE.md split at 20/25, Given/When/Then, budget alert ladder) are preserved here; per-pattern file-line citations and the full pattern inventory were not.
