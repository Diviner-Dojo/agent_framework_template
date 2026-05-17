---
title: "Ruflo Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "3 of 6"
target_repo: ruvnet/ruflo
target_path: C:/Work/AI/research_projects/ruflo
target_version: v3.6.24 (branch fix/issues-may-1-3, +22 commits queued for 3.6.25)
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "additive to SYNTHESIS-20260515-adoption-brief-v4; Ruflo's REFERENCE.md split was already scored 20/25 in v4 Sprint 1 at 0.58 confidence (hygiene value, not cost)"
prior_research:
  - docs/analysis/ANALYSIS-20260515-ruflo.md (project-analyst, 2026-05-15, summary-only after socket-error recovery)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 12-agent deliberation, 0.75 synthesis confidence)
  - discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md (sealed)
principles_challenged: [1, 2, 4, 8]
verdict_summary:
  v4_sprint1_confirmed: 1
  v4_sprint1_additive: 0
  path_a_staging: 1
  deliberated_and_deferred: 0
  below_threshold: 3
  structural_craft_contributions: 5
---

# Ruflo vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

This is the third project in the 6-repo research arc and the first whose ANALYSIS document was a degraded recovery run. `ANALYSIS-20260515-ruflo.md` (78 lines) is summary-only — the original 51-tool dispatch crashed with a socket error and the recovery run claimed Write was blocked, so the load-bearing claims (REFERENCE.md split at 20/25, Given/When/Then in `/plan`, budget alert ladder) survive but the per-pattern file-line citations don't. This document re-grounds those claims in the actual repo and adds the structural-craft observations the recovery pass couldn't surface.

**v4 already absorbed**: REFERENCE.md split for facilitator + architecture-consultant + qa-specialist as Sprint 1 hygiene work (0.58 confidence). v4 explicitly down-graded ANALYSIS's "~40% token reduction" framing — the savings are real but small in dollars (~$0.04–$0.08 per 90 days at 2.7M–5.4M tokens), and the value is **structural hygiene** (lean agent prompt as policy) more than cost.

**Scale caveat**: Ruflo operates at a fundamentally different scale (51,547 stars, 32 plugins, 300 MCP tools, 49 CLI commands, 43 agent definitions across 4,256 files). Most of its surface — swarm topologies, GOAP planner, federation breaker, IPFS plugin registry, WASM Agent Booster — is a **scale mismatch** with the user's template. The structural-craft observations below extract what survives the mismatch: the audit-as-CI-gate discipline, the plugin-as-bounded-context decomposition, the witness manifest, and the way token-cost shows up as a **design discipline** rather than telemetry.

**Windows case-collision note**: `.agents/skills/worker-benchmarks/` and `.agents/skills/worker-integration/` had `SKILL.md`/`skill.md` pairs that didn't all check out on Windows. I sampled the plugin tree (which is unaffected) and treated the case-shadowed files as out of scope. No load-bearing finding depends on them.

---

## 1. Identity & What's Useful

**Ruflo** (formerly claude-flow, renamed by ruvnet 2026) is a **multi-agent orchestration platform** for Claude Code — a swarm coordinator, vector-memory layer, federation protocol, and 32-plugin marketplace shipped as the `ruflo` npm package + an MCP server. Where Superpowers is a single fixed methodology (one set of 14 skills, one workflow), Ruflo is a **substrate** that ships many compositional plugins. The repo's identity is the marketplace and the plugin-as-bounded-context discipline, not any single workflow.

The runtime offers two install paths — `/plugin install ruflo-core@ruflo` (slash commands only, zero workspace files, no MCP) and `npx ruflo init` (98 agents, 60+ commands, 30 skills, MCP server, hooks, daemon). Those two paths are explicitly documented as different surface areas in the README (#1744). The repo treats **surface honesty** as a load-bearing user contract.

**Top 5 things worth studying:**

1. **Plugin-as-bounded-context decomposition.** 32 plugins, each with `agents/`, `commands/`, `skills/`, `scripts/`, `docs/adrs/`, and an optional `REFERENCE.md` — a uniform Claude Code plugin specification. ([plugins/README.md:110–121](../../../../research_projects/ruflo/plugins/README.md))
2. **REFERENCE.md companion-file split.** Cited in ANALYSIS; instances at `plugins/ruflo-cost-tracker/REFERENCE.md`, `ruflo-adr/REFERENCE.md`, `ruflo-ddd/REFERENCE.md`, `ruflo-iot-cognitum/REFERENCE.md`. The agent prompt (`cost-analyst.md`, 92 lines) contains the role, tools, and a *pointer*; pricing tables, formulas, budget ladders, and report shapes live in `REFERENCE.md` and are loaded on-demand. ([plugins/ruflo-cost-tracker/agents/cost-analyst.md:14–16](../../../../research_projects/ruflo/plugins/ruflo-cost-tracker/agents/cost-analyst.md))
3. **Witness manifest with Ed25519 signatures + per-OS bundles.** `verification/<linux|macos|windows>/manifest.md.json` + `history.jsonl`. Every documented fix carries a SHA-256, a distinctive marker substring, and a reproducible signature derived from `sha256(gitCommit + ':ruflo-witness/v1')`. Three regressions on 2026-05-08 (#1859, #1862, #1867) passed unit tests but broke on first install — the witness catches "load-bearing line of a documented fix has been deleted" before publish. ([verification/README.md:1–48](../../../../research_projects/ruflo/verification/README.md))
4. **Audit-as-CI-gate with monotone-decreasing baseline.** `scripts/audit-tool-descriptions.mjs` (146 lines) scans every MCPTool description for "Use when…" guidance, enforces ≥80 chars, requires uniqueness, and writes a baseline at `verification/mcp-tool-baseline.json` that is monotone-decreasing — CI fails on any regression. ADR-112 is the policy; the script is the enforcement. ([scripts/audit-tool-descriptions.mjs:1–100](../../../../research_projects/ruflo/scripts/audit-tool-descriptions.mjs))
5. **Token-cost as a structural design discipline.** ADR-098 Part 2 quantified per-agent prompt sizes (19–105 lines), set an explicit budget (≤60 lines), and shipped four discrete commits to move reference tables out of agent prompts and into `REFERENCE.md`. Part 3 dropped `security-auditor` from `model: opus` → `model: sonnet` with a documented revert criterion. Token-cost is policy, not telemetry. ([v3/docs/adr/ADR-098-plugin-capability-sync-and-optimization.md:90–104](../../../../research_projects/ruflo/v3/docs/adr/ADR-098-plugin-capability-sync-and-optimization.md))

**Cultural signal worth noting.** Ruflo's `CLAUDE.md` and `AGENTS.md` carry two simultaneous voices: the maximalist marketplace pitch ("100+ agents, 314 MCP tools, 27 hooks, self-learning, federation, GOAP planner") and a much sharper operational discipline (ADR-098's prompt-size audit, ADR-112's discoverability-baseline, the witness manifest's per-OS regression protection). The discipline is the part worth studying; the maximalism is the part to filter past.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Ruflo | Agent Framework Template |
|---|---|---|
| Multi-agent dispatch | Swarm `swarm_init` + `agent_spawn` + `SendMessage` topology | Facilitator + 10 specialists, single-orchestrator panel |
| Memory substrate | AgentDB + HNSW + SONA, 6+ namespaces | events.jsonl → SQLite → memory/ → optional vector |
| ADR lifecycle | `ruflo-adr` plugin with `proposed → accepted → deprecated → superseded` state machine | ADR-NNNN sequential, immutable, never deleted |
| Cost tracking | `ruflo-cost-tracker` plugin with budget ladder + Prometheus export | ADR-0013 token telemetry via `ingest_token_usage.py` |
| Hook system | 27 hooks (PreToolUse/PostToolUse/UserPromptSubmit/SessionStart/Stop/SubagentStop/Notification/PermissionRequest) | 7 hooks (file-locking, format, secrets, commit-gate, push-blocker, pre/post-compact, session-start) |
| Cross-agent comms | `SendMessage` named addressing + `TeammateIdle`/`TaskCompleted` hooks | Cross-Agent Dispatch + Multi-Instance protocols via facilitator |
| Plan methodology | SPARC plugin (Specification → Pseudocode → Architecture → Refinement → Completion + 5 gate checks) | `/plan` + `/build_module` + 4 collaboration modes |

### Theirs-only (you don't have this)

- **Plugin-as-bounded-context model** — each capability ships as a self-contained plugin with its own agents/commands/skills/scripts/ADRs/README, opt-in via `--plugin-dir` or marketplace install.
- **REFERENCE.md companion-file split** — agent prompt is a lean dispatch (role + tools + on-demand pointer); reference tables live adjacent in a file the agent reads only when needed.
- **Witness manifest with Ed25519 per-OS attestation** — three-layer regression protection (install smoke + behavioral smoke + presence attestation). Reproducible public key, no committed private key, per-OS bundles for CRLF/path-separator drift.
- **Audit-as-CI-gate with monotone-decreasing baseline** — every MCP tool description must have "Use when …" guidance, ≥80 chars, unique. Baseline can shrink, never grow. CI gates on the count.
- **Surface honesty in install paths** — README documents two install paths side-by-side (lite plugin vs. full CLI), explicitly noting "MCP server NOT registered" for the lite path and "Files in your workspace: Zero" — sets expectation about surface, not just capability.
- **4-tier budget alert ladder enforced by an exit code** — `cost-budget-check` skill exits 1 on HARD_STOP (100%), enabling `budget check && spawn …` fail-closed patterns. The alert ladder lives in REFERENCE.md as data; the skill is the enforcement.
- **Plugin discovery via IPFS/Pinata** — registry as immutable, decentralized JSON pinned by CID. Distribution is content-addressed, not version-addressed.
- **Stop / SubagentStop completion-evaluation hooks** — `prompt`-type hooks (not commands) that ask the model to self-assess "is the task done?" and return `{"decision": "stop"}` or `{"decision": "continue", "reason": "..."}`. A prompt-as-hook pattern your framework doesn't use.
- **Status doc tiered by question** — three docs for three audiences: STATUS.md ("is it ready?"), USERGUIDE.md ("how do I?"), verification.md ("trust but verify"). Each answers a specific question; none try to be all three. ([docs/STATUS.md:1–10](../../../../research_projects/ruflo/docs/STATUS.md))

### Yours-only (they don't have this)

- **Reasoning capture as primary artifact** (Principle #1) — Ruflo has memory and pattern learning but no immutable discussion ledger. Their SONA / ReasoningBank is *learning from outcomes*, not *preserving deliberation*.
- **12-specialist panel with Values + Domain Lens** — Ruflo's plugin agents are role-named (coder/reviewer/architect/cost-analyst), but they lack the panel-of-perspectives architecture and load-bearing values blocks.
- **Education gates** (Principle #6, with v4 reframing) — no equivalent in Ruflo.
- **Lineage tracking with framework-lineage.yaml + Steward** — Ruflo has plugin versions and ADR supersession but no template-to-derivative lineage manifest.
- **Sourced-assertion memory substrate with `project://` URIs** — Ruflo's memory is per-namespace + per-key; no Suchness preservation, no source-back primitive.
- **Failure taxonomy (8 named classes with recovery paths)** — Ruflo has `continueOnError: true` on every hook and `|| true` on every command; no named taxonomy.
- **Capture pipeline with sealed discussions + transcript generation** — Ruflo captures events and patterns but does not produce immutable transcripts.
- **External project analysis with Rule of Three** — Ruflo's marketplace is curated, not Rule-of-Three-gated.

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Reasoning capture differentiates more sharply against Ruflo than against Superpowers.** Ruflo has more *learning* infrastructure (HNSW, SONA, ReasoningBank, neural training hooks on 36/43 agents per ADR-098 Part 4) than Superpowers but still no equivalent of your immutable discussion ledger. Their bet is "patterns extracted from outcomes"; yours is "deliberation preserved as artifact." Both are valid; only yours produces an audit trail of *why*, not just *what worked*.

2. **Single-facilitator orchestration is the right answer at your scale.** Ruflo's `SendMessage` named-agent topology is a real coordination win at 8–15 active workers; at 12 specialists doing structured panels for code review, your facilitator-orchestrator is cleaner. v4 already noted swarm orchestration as "deliberately not adopted" — this analysis confirms.

3. **Failure taxonomy beats `continueOnError: true`.** Ruflo's hooks all set `continueOnError: true` and pipe with `|| true` so a hook failure is silent. Your failure taxonomy (8 named classes, max-retries, escalation paths) is operationally more honest. The trade-off is brittleness — Ruflo's hooks never block; yours sometimes do — but blocking is *information*, not just friction.

4. **Plugin-as-bounded-context is a posture decision, not a feature gap.** Ruflo's 32 plugins solve the marketplace problem (third-party authors, opt-in surface, independent versioning). Your for-future-team-on-Claude-Code template is single-author; the plugin model would add accidental complexity. Hold the line, but adopt the *internal* discipline (lean agent prompts, REFERENCE.md split, audit-as-gate) without the *external* surface (marketplace, IPFS registry, versioned plugin spec).

5. **ADR immutability is sharper than ruflo-adr's state machine.** Ruflo's `proposed → accepted → deprecated → superseded` lifecycle allows status changes; your "ADRs are never deleted, only superseded with references" is a strictly stronger invariant. The state-machine framing is useful documentation; the immutability discipline is what makes the history queryable in 18 months.

---

## 4. Weaknesses This Comparison Exposes

Ordered by severity for the framework's evolution. Each maps to a v4 working position, a structural-craft contribution, or a defer.

### 4.1 Your audit discipline doesn't run continuously

Ruflo has `scripts/audit-tool-descriptions.mjs` enforcing **"Use when …" guidance + ≥80 chars + unique"** on every MCP tool description, with `verification/mcp-tool-baseline.json` as a **monotone-decreasing baseline** that CI gates on. You have audits — `scripts/quality_gate.py`, the regression ledger, the knowledge dashboard — but you don't have a "this number can only go down" baseline for any policy you enforce. This is a distinct mechanism: not "is the metric green?" but "did anyone make it worse?"

**Maps to**: §5.4 — structural-craft contribution.

### 4.2 Token-cost is telemetry; it could be policy

Your ADR-0013 logs token usage and lets analysis-time tooling compute cost. Ruflo's ADR-098 Part 2 sets a **prompt-size budget per agent** (≤60 lines) and shipped four discrete commits to enforce it. Your `facilitator.md`, `architecture-consultant.md`, and `independent-perspective.md` agent definitions have no equivalent policy — they grow with each Sprint addition and nothing prevents drift. v4's Sprint 1 hygiene item (REFERENCE.md split for those three agents) addresses the *symptom* once; the *policy* (budget + audit + monotone-decreasing baseline) would prevent recurrence.

**Maps to**: §5.4 — structural-craft contribution. Synergy with v4 Sprint 1 REFERENCE.md split (0.58 confidence).

### 4.3 Your hooks block; Ruflo's hooks have a `prompt` type

Ruflo's `Stop` and `SubagentStop` hooks are `{"type": "prompt"}` (not `{"type": "command"}`) — they ask the model to evaluate completion and return JSON. This is a different hook pattern entirely: the model self-audits at session-end. Your hooks are all command-type. The model-as-evaluator at hook boundaries is a structural option you haven't named.

**Maps to**: §5.4 — structural-craft contribution. Low-priority; included for completeness.

### 4.4 No "is it ready?" doc distinct from "how do I use it?" doc

Ruflo splits documentation by question: STATUS.md = "is it ready?", USERGUIDE.md = "how do I?", verification.md = "trust but verify". Your `BUILD_STATUS.md` is session-scoped working state; your `FRAMEWORK.md` is the constitution; your `CLAUDE.md` is project config. **None is the "what currently works" doc for an adopter.** A for-future-team-on-Claude-Code framework needs an "is it ready?" doc badly — and you don't have one.

**Maps to**: §5.4 — structural-craft contribution. Sits naturally between FRAMEWORK.md and CLAUDE.md.

### 4.5 SPARC's per-phase gate-check pattern is sharper than your `/plan → /build_module` handoff

Ruflo's `sparc-orchestrator` enforces 5 phase gates with explicit pass criteria (Phase 1: ≥3 acceptance criteria + constraints + edge cases; Phase 4: tests pass + review approved + coverage ≥80%; Phase 5: traceability matrix complete). Your `/plan` produces a spec; `/build_module` interprets it. There's no formal between-phase gate beyond "did the build complete?" Below v4 attention threshold given Path A's commitments, but worth noting.

**Maps to**: §5.2 Pattern 3 — below threshold; defer.

### 4.6 No regression-protection layer between unit tests and production users

Ruflo's three-layer regression stack — install smoke + behavioral smoke + witness manifest — catches a specific bug class your framework cannot: *"the load-bearing line of a documented fix is still present."* Your `memory/bugs/` regression ledger requires a guard test to exist; if no test was written, the regression slips through. Witness manifests attest *presence of a marker substring*, not *behavior*, which is cheap to maintain and catches refactor-deletion regressions.

**Maps to**: §5.2 Pattern 4 — below threshold; defer (scale mismatch — your fix volume doesn't justify the per-OS signing overhead).

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How Ruflo stands against your 8 Non-Negotiable Principles:

| # | Principle | Ruflo stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **Disagrees by emphasis** — patterns and outcomes are primary; reasoning is captured incidentally via SONA trajectories | **Yes — different bet** | Your differentiator holds. Their learning loop is impressive but lossy at the *why* layer. |
| 2 | Capture must be automatic | **Strongly agrees** — 27 hooks fire automatically; nothing manual | Compatible | They've built a wider capture surface (every tool use, every Bash, every search). Your capture is event-typed; theirs is tool-typed. Both work. |
| 3 | Collaboration precedes adversarial rigor | **Neutral** — swarm topologies are collaborative by default; no adversarial mode | Compatible | No tension. |
| 4 | Independence prevents confirmation loops | **Disagrees in practice** — agents in a swarm share memory and pass results to each other; not separated for independent review | **Yes** | Your facilitator + independent-perspective architecture is sharper. Ruflo's `code-review-swarm` is parallel review, not separated-eyes review. |
| 5 | ADRs are never deleted | **Disagrees** — `proposed → accepted → deprecated → superseded` state machine allows status changes; their ADRs supersede in place | Compatible | Their state machine is useful framing; your immutability is a strictly stronger invariant. Hold. |
| 6 | Education gates before merge | **Disagrees by omission** — no education gate concept | **Yes** | Same as Superpowers. v4's Option C default + Option B carve-out preserves the principle. |
| 7 | Layer 3 promotion requires human approval | **Partial** — patterns auto-promote via SONA neural training (`hooks post-task --train-neural true`); no human gate | **Yes — values divergence** | Your human gate is the right answer for a for-future-team artifact. Auto-promotion is appropriate for a learning agent; inappropriate for curated methodology. |
| 8 | Least-complex intervention first | **Strongly disagrees at substrate; agrees at audit** — 32 plugins, 300 MCP tools, 27 hooks, 49 CLI commands. But ADR-098 is least-complex intervention applied to *agent prompts*. | **Mixed** | Their substrate is maximalist; their *internal discipline* is minimalist. Adopt the discipline; reject the substrate. Confirms Principle #8 audit candidate from comparison-01. |

**Four principles are challenged: #1, #2, #4, #8.** #1 and #4 are validated by Ruflo's omission. #2 is a different question — their auto-capture surface is *wider* than yours (every tool use, not just every event-typed command); your event taxonomy is *deeper* (typed semantics, sealed discussions). #8 is the most interesting: Ruflo proves that maximalist substrate can coexist with minimalist discipline if the discipline is *audited continuously*.

### 5.2 Adoption Candidates — v4-Aligned

#### Pattern 1: REFERENCE.md companion-file split (agent prompt + sibling reference)

**Score: 21/25** — **CONFIRMED — v4 Sprint 1 at 0.58 confidence (re-scored upward with new evidence)**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | Distinctive to Ruflo; 4 of 32 plugins use it (cost-tracker, adr, ddd, iot-cognitum) |
| Elegance | 5 | One file split, one pointer in the agent prompt, on-demand loading. Lighter than skill-loading; heavier than inlining |
| Evidence | 4 | Shipped in production (ADR-098 Part 2 status: Implemented; 4 commits cited) |
| Fit | 5 | Drop-in for your three heaviest agents; your file conventions already support sibling files |
| Maintenance | 4 | Two-file sync risk; mitigated by REFERENCE being read-only reference data, not narrative |

**Status note**: v4 already commits this for facilitator + architecture-consultant + qa-specialist at 0.58 confidence — explicitly framed as *hygiene* (lean prompt as policy) rather than *cost* (~$0.04–$0.08 savings/90d). My re-score (21 vs. ANALYSIS's 20) is based on new evidence: the *technique is mature enough to have its own ADR* (ADR-098 Part 2), and the four-plugin example set demonstrates the pattern survives multiple authors. The cost saving is genuinely small; the *discipline* signal is strong.

**Action**: v4 Sprint 1 already commits the three named agents. The Path A staging extension (R2-equivalent) would propagate the pattern to skills as Red Flags tables propagate to skills — same logic, same file structure.

#### Pattern 2: 4-tier budget alert ladder with exit-code enforcement

**Score: 18/25** — **Below threshold; defer with rescore conditions**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | 50/75/90/100% ladders are common; the *exit-code enforcement* is distinctive |
| Elegance | 4 | Clean — REFERENCE.md as data, skill as gate, exit-code as fail-closed signal |
| Evidence | 4 | Shipped in ruflo-cost-tracker P2; documented + smoke-tested |
| Fit | 3 | ADR-0013 is "accepted, not enacted" per v4; the budget concept exists but isn't operationally wired |
| Maintenance | 4 | Stable structure; thresholds rarely change |

**Status note**: ANALYSIS scored the budget alert ladder as "worth adapting as an extension to ADR-0013" without a numeric score. I score it at 18/25. v4 Sprint 2 has "/insights adoption per project + ADR-0013 promotion to accepted with `ingest_token_usage.py` baseline run." Until ADR-0013 promotes from accepted-but-not-enacted, the budget ladder has nothing to gate. **Re-score conditions**: ADR-0013 promotes + 30d of baseline data + a derived project actually hits a budget threshold.

**Action**: Hold. Re-evaluate when v4 Sprint 2 promotes ADR-0013.

#### Pattern 3: SPARC per-phase gate-check protocol

**Score: 16/25** — **Below threshold; defer**

Ruflo's SPARC orchestrator enforces 5 gate checks with explicit per-phase criteria. Your `/plan → /build_module` handoff has no formal between-phase gate beyond the BUILD_STATUS.md/checkpoint mechanism. Below v4 attention threshold and the 20/25 adoption gate. The structural insight worth preserving: **phase transitions are natural integration points for independent review**, which your build_review_protocol.md already exploits via mid-build checkpoints. SPARC's contribution is *naming the phases*; you already have the *mechanism*. Not worth the import.

#### Pattern 4: Witness manifest with Ed25519 + per-OS bundles

**Score: 14/25** — **Below threshold; scale mismatch**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 2 | Distinctive to Ruflo (one publicly available example) |
| Elegance | 5 | Three-layer regression protection: install smoke + behavioral smoke + presence attestation. Reproducible pubkey, no committed private key |
| Evidence | 5 | Live in CI; 103 documented fixes attested; #1859/#1862/#1867 motivated the layer |
| Fit | 1 | Scale mismatch — your fix volume (regression ledger entries) does not justify per-OS Ed25519 signing |
| Maintenance | 1 | High — per-OS CI matrix, marker maintenance, signature regeneration on every regen |

**Action**: Don't adopt the mechanism. Capture the *frame*: **regression protection has three independent layers, not one**. Your regression ledger is Layer 1 (behavioral smoke); witness manifests would be Layer 2 (presence attestation); the install smoke layer doesn't apply to a template. The frame is useful; the mechanism is overkill.

#### Pattern 5: Audit-as-CI-gate with monotone-decreasing baseline

**Score: 22/25** — **Path A staging — structural-craft contribution**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 4 | Common in lint configs (e.g., `eslint-disable` baseline) but uncommon in agent-framework discipline |
| Elegance | 5 | "This number can only go down" is a one-line policy with enormous operational leverage |
| Evidence | 5 | ADR-112 + `audit-tool-descriptions.mjs` + `verification/mcp-tool-baseline.json` in CI |
| Fit | 4 | Your `scripts/quality_gate.py` already runs in CI; baseline pattern is additive |
| Maintenance | 4 | Baseline file is one number per policy; update via `--update-baseline` flag |

**Status note**: This is the structural pattern v4 doesn't have. v4 has *protocol yield metrics* (uniqueness, survival rate, confidence calibration) but no *policy baseline that can only shrink*. The two are complementary: yield metrics measure marginal value; baselines enforce non-regression. Your `quality_gate.py` could grow a `--baseline=N` mode for any property that should monotonically improve (e.g., agents-without-Values-blocks count, rules-without-Red-Flags-tables count, commands-with-fewer-than-3-examples count).

**Action**: Path A staging. After Path A's R3 (Red Flags propagation to skills) lands, add a baseline check: "count of skills without Red Flags tables can only go down." Then propagate the pattern.

### 5.3 Verdict Tally — v4-Aware

- **CONFIRMED — v4 Sprint 1** (1):
  - Pattern 1 (REFERENCE.md split for facilitator + architecture-consultant + qa-specialist) — 0.58 confidence in v4; re-scored to 21/25 with new evidence
- **Path A staging** (1):
  - Pattern 5 (Audit-as-CI-gate with monotone-decreasing baseline)
- **Below threshold** (3):
  - Pattern 2 (budget alert ladder — rescore after ADR-0013 promotes)
  - Pattern 3 (SPARC gate-check — mechanism already covered by build_review_protocol checkpoints)
  - Pattern 4 (witness manifest — scale mismatch; preserve the *three-layer frame*)
- **Structural-craft contributions** (5): see §5.4

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

#### Contribution 1: Token-cost as design discipline, not telemetry

**Frame**: v4 treats token cost as something to **measure** (ADR-0013 logging, ingest_token_usage.py, `v_token_efficiency` view). Ruflo treats token cost as something to **budget** (ADR-098 Part 2: agent prompts ≤60 lines, four discrete enforcement commits, security-auditor opus→sonnet downgrade with a documented revert criterion).

**Observation**: The leverage points are different. Measurement tells you *what happened*; budgets tell you *what's allowed*. v4 Sprint 1's REFERENCE.md split is a one-time hygiene event; Ruflo's ADR-098 establishes a *policy that prevents recurrence*. The audit-as-CI-gate (Contribution 4 below) is the enforcement mechanism that closes the loop. Without it, the discipline decays with every new agent.

#### Contribution 2: Surface honesty as a structural pattern

**Frame**: Ruflo's README documents two install paths side-by-side (Claude Code Plugin = slash commands only, zero workspace files, no MCP; CLI install = full Ruflo loop) — with an explicit table mapping which capabilities work in which path. The user sees the *surface contract* before opting in.

**Observation**: Your framework has two surfaces that are *not* explicitly contracted: (a) the template-as-source and (b) the derived-project-as-active. These are different surfaces — the template has agents/rules/commands/skills but no operational discipline (no /retro execution, no BUILD_STATUS.md in active use), while derived projects have both. Adopters of your template need a surface-honesty doc that says: *here's what the template gives you (infrastructure)*, *here's what you have to instantiate (operational discipline)*. The template-vs-derived distinction the user pushed back on (memory file `feedback_template_vs_derived.md`) is structurally identical to Ruflo's plugin-vs-CLI distinction — both are valid; the contract just has to be explicit.

#### Contribution 3: "Is it ready?" doc as a distinct artifact class

**Frame**: Ruflo's docs/STATUS.md is explicitly *not* USERGUIDE.md and explicitly *not* verification.md. It answers a question — "what currently works?" — that the other two docs don't.

**Observation**: A for-future-team-on-Claude-Code framework needs three audiences served by three docs: *what is this?* (FRAMEWORK.md, you have this), *how do I configure it?* (CLAUDE.md, you have this), *what currently works?* (no equivalent). Your `metrics/knowledge_pipeline_log.jsonl` and `metrics/quality_gate_log.jsonl` contain the data; nothing renders it for an adopter. A `STATUS.md` generated by `knowledge_dashboard.py` would close the loop. Below v4 attention threshold but a real omission given the for-future-team strategic posture.

#### Contribution 4: Audit-as-CI-gate with monotone-decreasing baseline (lifted to a frame)

**Frame**: Ruflo enforces *any policy* by writing the current count of violations to a baseline file and gating CI on "the count can shrink, not grow." `audit-tool-descriptions.mjs` is one application; the pattern generalizes.

**Observation**: This is the structural complement to v4's protocol yield metrics. Yield metrics measure *added value*; baselines enforce *non-regression of discipline*. Your framework currently has neither baseline files nor an `--update-baseline` workflow for any of its 14 rules. Three candidates to apply the pattern to once Path A lands:

| Discipline | Baseline metric | What it would prevent |
|---|---|---|
| Red Flags tables in rules | count of rules without `\| Excuse \| Reality \|` table | Rules drifting back to descriptive prose |
| Agent prompt size | count of agents > N lines (calibrate N from v4 Sprint 1 hygiene baselines) | Agent prompts re-bloating after the split |
| Skill imperative voice | count of skills with voice intensity < 3/5 (from comparison-01-superpowers §4.8) | Skills drifting back to descriptive after Path A's R3 |

**Status**: Path A staging. The pattern is most valuable *after* discipline has been added (Sprint 1's Rationalization Tables, Path A's R3 voice tightening) — otherwise there's nothing to baseline against.

#### Contribution 5: Plugin-as-bounded-context (adopt the discipline, reject the surface)

**Frame**: Ruflo's 32 plugins are *not* a feature gap for your framework — they're a substrate choice for a marketplace. But the *internal discipline* of plugin-as-bounded-context (each plugin has its own agents/commands/skills/scripts/ADRs/README, internal coupling but external isolation) is a useful frame for *future template subdivisions*.

**Observation**: Your framework's `.claude/` tree has 12 agents + 17 commands + 14 rules + 6 skills all living in one flat namespace. If the framework grows (Path A adds skills; v4 Sprint 1 adds rules; future passes may add agents), the flat namespace becomes a liability. Ruflo's plugin model suggests a future refactor *if needed*: group related artifacts into named bundles (e.g., a `review-bundle/` containing facilitator + review specialists + review commands + review rules + review skills). Not a now-recommendation; a frame to hold when the next surface-size question lands.

### 5.5 Meta-Questions for Framework Evolution

1. **Is token-cost measurement enough, or do you want token-cost policy?** v4 Sprint 1 commits to the symptom (REFERENCE.md split); Ruflo's ADR-098 commits to the policy (≤60 line budget). The difference matters once the framework adds another five Sprint cycles of capabilities. Without a budget, the agent definitions grow with each addition.

2. **What other disciplines deserve a monotone-decreasing baseline?** The pattern generalizes far beyond MCP tool descriptions. Once Path A's Red Flags tables land in skills, *count of skills without Red Flags tables* becomes a baselineable metric. Once Path A's R3 voice tightening lands, *count of skills with voice intensity < 3/5* becomes baselineable. This is the long-term enforcement mechanism for *every discipline you add*.

3. **Should "what currently works?" be a generated artifact?** Your `knowledge_dashboard.py` already aggregates pipeline health into `metrics/knowledge_pipeline_log.jsonl`. A rendered `STATUS.md` for the template repo would be cheap to produce (one script) and would let adopters of the template see which capabilities are validated vs. aspirational. For-future-team posture suggests this is worth doing.

4. **Stop / SubagentStop as prompt-type hooks — a structural option you haven't named.** Ruflo's two `prompt`-type hooks ask the model to self-evaluate completion. Your hooks are all command-type. This isn't an adoption recommendation; it's a *modality you haven't considered*. Useful for future passes: when does model-as-evaluator beat script-as-evaluator?

---

## 6. Open Tasks Surfaced by This Document

Captured for forward visibility, not for immediate action:

| Task | Owner | Sequencing |
|---|---|---|
| Sprint 1: REFERENCE.md split for facilitator + architecture-consultant + qa-specialist | framework developer | Already in v4 at 0.58 confidence; re-scored to 21/25 here |
| Path A R8 (new): Audit-as-CI-gate with monotone-decreasing baseline — apply to Red Flags tables in skills | framework developer | Post Path A R2 (Red Flags landed in skills) |
| Path A R9 (new): Monotone-decreasing baseline for agent prompt size | framework developer | Post Sprint 1 REFERENCE.md split; baseline = current size after split |
| Path A R10 (new): Monotone-decreasing baseline for skill imperative voice | framework developer | Post Path A R3 (voice tightening) |
| Path A R11 (new): Generate STATUS.md for the template repo from `knowledge_dashboard.py` output | framework developer | Standalone; can run any time post-Tier-0 |
| Pattern 2 (budget alert ladder) re-evaluation | v4 Sprint 2 process | After ADR-0013 promotes to accepted-and-enacted |
| Structural frame: three-layer regression protection (preserve, don't implement) | framework developer | Reference document only; no code change |

---

## Appendix: What I Didn't Examine

For honesty about scope:
- 28 of 32 plugins (only sampled ruflo-core, ruflo-cost-tracker, ruflo-adr, ruflo-sparc in depth)
- The `v3/@claude-flow/` monorepo packages (cli/codex/guidance/hooks/memory/security) — TypeScript runtime not directly applicable to your Python+markdown substrate
- The `agentdb.rvf` binary format and Rust WASM kernels
- The `goal.ruv.io` Goal Planner / GOAP A* implementation
- The hosted UI at `flo.ruv.io` and the `ruvocal/` Docker stack
- Federation protocol details (mTLS, ed25519 challenge-response, PII pipeline, trust scoring formula)
- The case-shadowed `SKILL.md`/`skill.md` pairs in `.agents/skills/worker-benchmarks/` and `.agents/skills/worker-integration/` (Windows checkout limitation)
- The `tests/` directory and the 1933-test vitest suite

If a future pass needs more granularity on any of these, they're at `C:/Work/AI/research_projects/ruflo/`.
