---
analysis_id: ANALYSIS-20260607-rh-oversight-deepdive
title: "rh-claude-framework telemetry deep-dive: capability gap analysis against our Layer B dashboard"
type: analysis
target: C:/Work/AI/_external_repos/rh-claude-framework (private, MIT-licensed telemetry subpackage)
date: 2026-06-07
analyst: project-analyst
related: [ADR-0020, SPEC-20260607-064958, DISC-20260607-063709]
---

# rh-claude-framework — Telemetry Deep-Dive

> Scout confidence 0.97. Capability-gap analysis against a concrete reference system
> (not an abstract quality review). No specialist panel dispatched — the gap is
> unambiguous from forensic reading. Goal: make our Layer B dashboard **at least as
> functional and helpful** as Ross Barbieri's.

## 1. Capability Inventory of Ross's System

### 1.1 Private Framework (packages/oversight, packages/shared, packages/output)

The enforcement layer feeds the telemetry layer. Key telemetry-adjacent capabilities:

**Event emission from hooks (oversight package)**
- `rh-agent-oversight-guard.js` — PreToolUse:Agent guard; emits to `~/.claude/oversight-events.jsonl` on every
  auto-inject, block, or pass. Captures: event_type (instructions_loaded, oversight_auto_inject,
  oversight_block), session_id, timestamp, agent_type, missing_elements[].
- `rh-agent-result-guard.js` — PostToolUse:Agent guard; emits result_checked, result_failed, result_block events.
- `rh-consolidation-guard.js` — PreToolUse:Write guard for synthesis docs; emits consolidation_blocked/ok.
- `rh-read-audit.js` — PostToolUse:Read guard; emits read_incomplete when verification token is absent.
- All guards write JSONL to `~/.claude/oversight-events.jsonl` via config.oversightDir.

**Cross-session trend aggregation (oversight package)**
- `rh-supervisor-sweep.js` — reads the events JSONL over a sliding window (default 7d, max 90d), aggregates by:
  event_type counts + per-window deltas, session groupings, top-N missing oversight elements,
  subagent-failure patterns, daily-cadence bar chart (ASCII), Layer 3a supervisory-log rejections.
  Writes supervisor-trends.md. Exposed as CLI subcommand `rh-oversight supervisor-sweep`.

**Scribe / session-drain outputs (output + skills packages)**
- Per-session: recommendations.md, cleanup.md, learnings files under `~/.claude/memory-shared/learnings/`.
  Generated at session end by /rh-quit via the multiscope agent.
- Per-turn staging: `~/.claude/scribe-staging/<session>.jsonl` captures every turn's structured data
  before the 10K-char tail truncates it.

### 1.2 Telemetry Dashboard (packages/telemetry) — Private but MIT-licensed

**Data sources**
- `~/.claude.json` — Anthropic-written session registry: cost, token counts, model, duration, lines changed,
  FPS. Parsed by server/parser.js via chokidar file watcher (3s polling on Windows/OneDrive).
- `~/.claude/stats-cache.json` — Anthropic-written aggregate stats (NOTE: stopped updating in Claude Code
  v2.1.118 when /usage was merged; requires manual /usage panel open to refresh). Powers Overview tab
  aggregate cards. Known staleness risk documented in PLAN-20260520-frontend-v2.md.
- `~/.claude/telemetry-failures.jsonl` — append-only persistent failure store written by hook-forwarder on
  every PostToolUseFailure, validation block, orphaned agent, and config change. Cross-session. Survives
  server restarts.
- `~/.claude/oversight-events.jsonl` — written by oversight package guards. Read by trends router for
  cross-session aggregation.
- `~/.claude/oversight/supervisory-log.md` — Layer 3a Stop-hook LLM rejections. Read by trends router.
- Live session data from 12 Claude Code hooks posting to the Express server.

**Live hook event pipeline (the standing server)**

    Claude Code hooks → hook-forwarder.js → POST /api/* → store.js (EventEmitter)
      → broadcaster.js → WebSocket → React UI

Hook coverage (12 hooks): SessionStart (auto-start), PreToolUse:Bash (tool-validator), PostToolUse
(tool events), PostToolUseFailure (failures + failure store), Stop (turn boundary + Layer 3a LLM review),
UserPromptSubmit (current prompt), SubagentStart/Stop (agent lifecycle), PreCompact (compaction detection),
ConfigChange, TaskCompleted, statusLine (live cost + context + model piggybacked on stdout).

**Frontend surfaces (v1)**
- Overview tab — aggregate stats cards (from stats-cache), daily activity bar chart, hourly heatmap,
  recent sessions table.
- Live session tabs (one per active session, green pulsing dot) — context window gauge + runway/velocity,
  model breakdown mini, turn heartbeat strip, tabbed subpanel:
  - Agents tab — unified table: active (green, live cost/context from transcript) + completed (gray, sorted
    by cost desc) + orphaned (red). Header strip: total cost, context %, tool count, orphaned count,
    failure count. SubagentTimeline (collapsible Gantt). Detail panel: Prompt | Result side-by-side.
  - Tools tab — live tool event feed, last 200 events, retry-detection badges, validation-block markers.
  - Turns tab — per-turn breakdown with Lollipop / Swimlane / List timeline views.
  - Failures tab — persistent failure tracking with expandable detail, pattern badges, error-class grouping
    chips, cross-session view from failure store.
  - Details tab — TurnTracker (per-turn cost + velocity + estimated turns remaining), TurnCostChart
    (cost over time by turn), PerformanceMetrics (CLI frame FPS p50/p95/p99), CurrentPrompt,
    TaskCompletions.
- Trends tab — cross-session oversight aggregation via GET /api/trends?days=N. Day-range selector
  (1/7/14/30), 3 summary cards with prior-window deltas, daily BarChart, event-type table, top missing
  oversight elements, top subagent-failure patterns, top sessions by event count.
- Picture-in-Picture — browser Document PiP API for floating dashboard alongside Claude.

**Frontend surfaces (v2, in-flight)**
- History surface (v2 Phase 1, landed): aggregate multi-session statistics from new /api/aggregates
  endpoint that walks `~/.claude/projects/` transcript JSONLs directly (not stale stats-cache).
- Failures surface (v2, landed): promoted from subtab to top-level.
- Oversight surface (v2, landed): surface for oversight-events and supervisory-log.
- Trends surface (v2, landed): cross-session trends.
- Live, Sessions, Subagents surfaces (v2, planned as Phases 3.1-3.3).

**Failure intelligence**
- server/failure-store.js — append-only JSONL persistence. In-memory cache (last N records).
  Classifies every failure into errorClass: not_found, permission, size_limit, timeout, network,
  validation, orphan, config, suggestion, other. Deduplication via SHA-1 hash of tool+input for
  retry-chain detection. Query API: by session, tool, time range. Pattern API: frequency by tool,
  by error class, by session. Digest API: summary for time window.
- server/failure-alerting.js — sliding-window FailureAlerter: if same tool fails >= threshold times
  within window, broadcasts a failureAlert WebSocket event.
- Cross-session failure history from `~/.claude/telemetry-failures.jsonl` (persists across server restarts).

**Context window tracking**
- Gauge: fill % + amber (80%) + red (90%) thresholds.
- Runway: estimated turns remaining = (contextLimit - currentTokens) / avg tokens-per-turn.
- Velocity: average tokens consumed per turn (computed from contextHistory deltas).
- Cache hit ratio: cacheRead / (cacheRead + input).
- Compaction detection: PreCompact hook → recordCompact() → stamps every active subagent with
  _spannedCompactAt + marks turn history entry.
- 1M-context model detection: resolves reported 200K context_window_size to 1M for extended-context
  models (prevents 100% showing when only 20% is used).
- Context override: user can cycle the assumed window size via localStorage.

**Forced-continuation / Stop-hook loop detection**
- Detection: if last lifecycle event was 'stop' and tool event arrives with no intervening
  UserPromptSubmit, the Stop hook returned {ok: false}. Deduplicated per stop-sequence. Emits
  forcedContinuation event. UI: amber badge (1 consecutive), red "Possible Stop-hook loop" banner (2+).

**Orphaned subagent detection**
- Server sweeps active subagents on periodic timer. Any subagent with no tool event for > 10 minutes
  moves to history with status:'orphaned' + a failure-store row + red lane in Agents tab.

**Config-change visibility**
- ConfigChange hook fires when settings.json is modified during a session. Persisted to failure store
  as eventType:'config_change'. Rendered on Failures tab as cyan rows. Catches the "my hooks stopped
  working" class of mystery.

**Hook health self-monitoring**
- server/hook-health.js — polls hook-debug.log every 60s, computes p95 transcript-parse latency,
  surfaces "hooks ok" / "hooks N err" chip on Failures tab. Catches the meta-failure where telemetry
  breaks silently and the dashboard lies by omission.

**StatusLine stall detection**
- Server counts tool events since last statusLine POST. If >= threshold tool events pile up without
  a new statusLine post, marks statusLine as stalled. Cleared on next real statusLine POST.

**Model breakdown**
- Donut chart: cost per model family (Opus/Sonnet/Haiku) with consistent color system (purple/blue/cyan).
- Per-subagent cost attribution from transcript JSONL parsing piggybacked on tool events.
- Per-turn cost: difference between consecutive cumulative cost snapshots.

**Tool validation (deterministic, no LLM)**
- Layer 1 tool-validator-v2.js (PreToolUse:Bash): blocks cat→Read, head/tail→Read, grep/rg→Grep,
  find→Glob, sed→Edit, awk→Edit, echo/printf >→Write. Allows all legitimate bash. Exit 2 = block.
  Rendered as validation_block rows on Failures tab.

**CLI telemetry (no browser required)**
- rh-telemetry subcommands: session summary, all sessions sorted by cost, cost breakdown by model,
  context window details, daily activity (last 14d), specific project details.
- Inline /rh-telemetry Claude Code skill: live stats inside a session without leaving conversation.

**Performance metrics**
- CLI frame timing: FPS, p50/p95/p99, avg/min/max.

**Plan/subscription usage**
- PlanUsage component: renders usage gauges in global header strip. Detects Max vs Pro vs individual
  plans from OAuth credentials.

---

## 2. Architecture Characterization

**Primary mode: LIVE / STREAMING with retrospective fallback.**

The telemetry dashboard is a standing server process (Express + WebSocket on :7890) that:
1. Auto-starts on SessionStart hook (via start-bg.js)
2. Receives real-time POST events from 12 Claude Code hooks
3. Maintains in-memory state (store.js EventEmitter) pushed to browser via WebSocket
4. Polls `~/.claude.json` every 3 seconds (chokidar) as fallback for file-based session data
5. Persists failure history to JSONL for cross-session/restart survival

No database. All state is in-memory. Failure store and oversight events use append-only JSONL files
for persistence (not SQLite). The "compute at read time" constraint manifests as periodic chokidar
file-parse rather than DB queries.

The standing-server constraint is non-negotiable for their use case: real-time monitoring requires
a process that is alive during the session. They mitigate user friction via the SessionStart hook
auto-starting the server in the background.

---

## 3. Gap Analysis

| Capability | Ross has | We have | We lack |
|---|---|---|---|
| Time axis — trend over time | TurnCostChart, DailyActivity, HourlyHeatmap, SubagentTimeline, TrendsTab (7/14/30d) | None — aggregate totals only | Time series for any metric |
| Live / streaming view | WebSocket updates on every hook event; pulsing dots | None — static HTML snapshot | Any live view |
| Context window runway | Gauge (fill%, amber/red), velocity, estimated turns remaining, cache-hit ratio, compaction markers | None | All of it |
| Forced-continuation / Stop-loop detection | Automatic indirect detection; amber/red banner; per-session history | None | All of it |
| Orphaned subagent detection | Automatic (10-min idle sweep); red lane; failure-store row | A2 orphaned-subagent signal exists | Only retrospective, no real-time detection |
| Subagent agent lanes | Unified table: status, model, cost, context%, duration, tool count, failure count, parent linkage, Gantt | None | All of it |
| Per-turn cost chart | TurnCostChart (line chart, spikes visible) | None | All of it |
| Per-session model breakdown | Donut (Opus/Sonnet/Haiku), per-subagent cost attribution | A1 aggregate total by tier only | Session-scoped split, per-subagent attribution |
| Cross-session failure history | Persistent JSONL (survives restart), error-class chips, retry-chain detection, 24h digest | None — A2 signals not surfaced as cross-session history | All of it |
| Failure actionability | Error-class chips, sliding-window alerter, prompt linkage, remediation hints on validation blocks | Failures ranked by cost-weight | No class grouping, no actionable guidance, no prompt linkage |
| Config-drift visibility | ConfigChange hook → cyan rows on Failures tab | None | The "why did my hooks stop working" class of mystery |
| Hook health self-monitoring | hook-health.js chip (p95 latency, error log) | None | All of it |
| Time-frame filtering | Day-range selector (1/7/14/30d) | None | Any user-selectable time window |
| Interactive exploration | Tab switching, click-to-expand, localStorage context override, PiP, filter toggles | None | All interactivity |
| CLI inline summary | rh-telemetry CLI + /rh-telemetry skill | None | No in-session access |
| Time window declared on dashboard | Each tab shows data recency; Trends shows selected window | Not stated anywhere | We do not tell the user what time window the data covers |
| Retry-loop detection | SHA-1 hash deduplication of tool+input, retry badges | A2 retry-loop signal (count) | No visual retry-chain nesting |
| Oversight events surfaced | Trends tab: guard outcomes, missing-elements analysis, top-sessions by violation count | None | Oversight signals captured but not surfaced |

---

## 4. Prioritized Adoption Recommendations

### Priority 1 — Time window declaration (1–2 hours, no Steward gate)
Add earliest/latest DB event timestamps to DashboardData. Render as a header subtitle:
"Data covers: 2026-05-01 to 2026-06-07 (38 days) · Generated: 2026-06-07 14:23 UTC."
Pure render change. Zero constraint conflicts.

### Priority 2 — Client-side time-series charts in generated HTML (2–4 hours, no Steward gate)
Extract per-week cost/failure rollups from evaluation.db (data is already there in discussions table).
Bake as a JSON literal in the generated HTML. Inline Chart.js from CDN. The HTML remains a static
artifact; the chart is client-side filtering of baked-in data. Compatible with compute-don't-store
(derive the series from token counts × pricing at generation time, never store dollar series).
Compatible with read-only DB and html.escape discipline (data is a JSON literal in a `<script>` block,
not interpolated into HTML attributes).

### Priority 3 — Failure actionability: error-class grouping + remediation hints (3–5 hours, no Steward gate)
Extend RankedFailure with error_class mapped from signal_type. Add class-grouping summary chips above
the ranked table. Add fixed remediation hints per class (e.g., orphaned_subagent → "Check for context
compaction mid-session; subagent may have been lost at compaction boundary"). Link failures to the
discussion they occurred in (discussion_id is in the DB). All retrospective and static.

### Priority 4 — Oversight signals surfaced: weekly trends + prior-window deltas (4–6 hours, no Steward gate)
Add a Trends section to the generated HTML. Query evaluation.db for A2 failure signals grouped by week
and by type. Render a sparkline-style mini-chart (pure CSS/SVG, no library needed) showing the trend.
Show prior-window delta ("orphaned agents this week: 3, down 2 from last week"). All retrospective.
The data is in the DB today.

### Priority 5 — Interactive static HTML (3–5 hours, no Steward gate)
Tab switching between A1/A2/A3 panels, time-range filter that re-renders the embedded chart data,
expandable failure rows — all via ~50 lines of inline vanilla JS. Still a static artifact; all data
baked in at generation time. Interactivity just filters it in the browser.

### Priority 6 — Standing server / live monitoring (multiple sessions, Steward gate required)
Replicate Ross's core live monitoring: FastAPI + websockets standing server, hooks posting to it,
React or htmx frontend. This is the form-factor gate — it reopens the no-standing-process constraint.
Recommended sequencing: deliver Priorities 1–5 first, then reassess whether the live-monitoring gap
remains the most important unmet need. If yes, write the form-factor gate document and submit to the
Steward with evidence from Priorities 1–5's outcomes.
The Steward will want: (1) evidence the gap persists after Priorities 1–5, (2) scope limit for the
standing server (no auto-start by default; developer opts in explicitly), (3) zero production overhead
when idle.

---

## 5. Licensing and Prime-Objective Note

**The private repo (rh-claude-framework)**
- License: MIT (stated in README.md and packages/telemetry/LICENSE).
- The private clone was provided for analysis only. We may not redistribute its code or submit PRs.
- We CAN implement equivalent functionality in Python from scratch, with attribution to Ross Barbieri
  in the ADR or analysis doc: "architectural patterns drawn from toolbeltross/rh-claude-framework."
  Ideas and patterns are not copyrightable; code implementations are.

**The public rh-telemetry repo (now archived — migrated into rh-claude-framework)**
- Was MIT-licensed on GitHub as toolbeltross/rh-telemetry (now read-only/archived). Content is
  identical to packages/telemetry/ in the private monorepo.
- MIT license permits: use, copy, modify, merge, distribute, sublicense, sell — with copyright notice.
- Safe and Prime-Objective-aligned path: reimplement patterns in Python rather than lift Node/JS code.

**Contamination risk: LOW**, with one guard required:
- DO NOT copy JavaScript code verbatim from the private repo into Python files.
- DO NOT reuse test fixture JSON/JSONL samples (may contain Ross's session data).
- DO attribute architectural patterns (failure-class taxonomy, orphan-sweep algorithm,
  sliding-window alerter) to rh-claude-framework in the ADR authorizing any new standing server.

**On error-class vocabulary**: the class names (not_found, permission, orphan, config, validation)
are domain terminology, not creative expression. They may be reused verbatim. The classifier
function implementation must be original Python.

**Prime-Objective**: Ross is not a contributor to our framework — he gets a reference/credit note
in the relevant ADR, not contributor attribution. The principle of not claiming his architectural
work as ours without attribution applies under the spirit of clause (a).
