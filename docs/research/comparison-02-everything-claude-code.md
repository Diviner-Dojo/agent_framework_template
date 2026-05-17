---
title: "Everything Claude Code Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "2 of 6"
target_repo: affaan-m/everything-claude-code
target_path: C:/Work/AI/research_projects/everything-claude-code
target_version: v2.0.0-rc.1 (in-tree alpha; latest stable lineage v1.10.0)
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "additive-to-v4; pattern tags reflect v4 working positions, structural-craft observations are net-new"
prior_research:
  - docs/analysis/ANALYSIS-20260515-everything-claude-code.md (project-analyst, 2026-05-15, confidence 0.87)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 12-agent deliberation, 0.75 synthesis confidence)
  - docs/research/comparison-01-superpowers.md (sibling comparison, sequence 1 of 6)
principles_challenged: [2, 3, 7, 8]
verdict_summary:
  v4_sprint1_confirmed: 1
  v4_sprint1_additive: 1
  path_a_staging: 2
  deliberated_and_deferred: 2
  below_threshold: 2
  structural_craft_contributions: 5
---

# Everything Claude Code vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

This is project 2 of 6 in the cross-repo research sweep. The authoritative inputs are:

- [`docs/analysis/ANALYSIS-20260515-everything-claude-code.md`](../analysis/ANALYSIS-20260515-everything-claude-code.md) — your project-analyst's per-project rubric (9 patterns scored, confidence 0.87). Patterns 1-9 already carry scores. **This document does not re-score them without new evidence; it inherits the rubric and tags v4 status.**
- [`docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md`](../analysis/SYNTHESIS-20260515-adoption-brief-v4.md) — the cross-project synthesis with deliberated working positions. ECC items appear in Sprint 1 (Pre-Report Gate sub-pattern, 0.78) and Sprint 2 gated on Tier 0 (Agent Introspection Debugging; Santa Method context isolation for HIGH/CRITICAL only; Context Budget Audit one-time session).

**This document's contribution** is fresh-eyes structural-craft observations — additive value that the panel may not have surfaced because the panel is invested in the existing framework structure. Pattern adoption scores already exist in ANALYSIS-ecc; v4 already deliberated the headline candidates. Where my reading aligns with v4, the tag captures it. Where I add structural-craft observations, §5.4 collects them.

ECC is the **richest** repo in the survey by raw catalog size (60 agents, 230 skills, 75 commands, comprehensive hook matrix, 1,723+ tests). The danger in studying it is mistaking *size* for *signal* — the user's framework gets nothing from copying ECC's surface; the value is in the few load-bearing primitives the surface is built around.

---

## 1. Identity & What's Useful

**Everything Claude Code (ECC)** is a multi-harness AI-agent plugin and performance system, currently at v2.0.0-rc.1 (Rust control-plane alpha) on a v1.10.0 stable lineage. It distributes via npm (`ecc-universal`, `ecc-agentshield`), a Claude Code plugin manifest, and parallel sync surfaces for Codex/Cursor/OpenCode/Gemini/GitHub Copilot/Kiro/Trae. The catalog is enormous — 60 agents, 230 skills (the [`AGENTS.md`](../../../../research_projects/everything-claude-code/AGENTS.md) header is even larger), 75 legacy command shims being migrated toward skills-first. **18 install profiles** (core / developer / security / research / full / ...) let users select a subset rather than swallow the whole thing.

Underneath the volume sit a handful of architecturally distinctive primitives.

**Top 5 things worth studying:**

1. **Code-reviewer with explicit Pre-Report Gate, false-positive taxonomy, and `It Is Acceptable And Expected To Return Zero Findings` clause** — [`agents/code-reviewer.md:40-74`](../../../../research_projects/everything-claude-code/agents/code-reviewer.md). The strongest single artifact in the catalog; addresses reviewer-noise erosion directly. (Pre-Report Gate is already v4 Sprint 1 at 0.78.)
2. **Santa Method — dual reviewers with *context isolation* and "both must PASS" convergence loop** — [`skills/santa-method/SKILL.md`](../../../../research_projects/everything-claude-code/skills/santa-method/SKILL.md). Architecturally purer independence than parallel-panel review; reserved for Sprint 2 HIGH/CRITICAL gating in v4.
3. **Agent Introspection Debugging — four-phase self-debug loop (Capture → Diagnose → Contain → Report)** — [`skills/agent-introspection-debugging/SKILL.md`](../../../../research_projects/everything-claude-code/skills/agent-introspection-debugging/SKILL.md). Pure guidance, no infrastructure. Fills gap between named infrastructure failures and in-flight reasoning failures.
4. **Hook-runtime gating via env vars (`ECC_HOOK_PROFILE=minimal|standard|strict`, `ECC_DISABLED_HOOKS=...`)** and a `run-with-flags.js` wrapper threaded through every hook entry — [`hooks/hooks.json:43-340`](../../../../research_projects/everything-claude-code/hooks/hooks.json). Permits tuning the hook matrix without editing hook files. The Claude-Code-only `everything-claude-code/.claude/settings.json` has no equivalent profile switch.
5. **Context-budget audit with concrete calibration numbers** — `~500 tokens per MCP tool schema`, `description >30 words flags bloated frontmatter`, `agents >200 lines are heavy`, `files >800 lines extract by responsibility`. [`skills/context-budget/SKILL.md:24-68`](../../../../research_projects/everything-claude-code/skills/context-budget/SKILL.md). Quantification turns a vague intuition into an actionable audit.

**Cultural signal worth noting.** ECC is unapologetically *operator-flavoured commerce* — ECC Pro at \$19/seat/month, sponsorship tiers, a GitHub App for PR audits, and an explicit "OSS stays free" guard (`README.md:77`). The README's hero promises "*the performance optimization system for AI agent harnesses*"; the [`SOUL.md`](../../../../research_projects/everything-claude-code/SOUL.md) is a five-bullet declaration; the [`RULES.md`](../../../../research_projects/everything-claude-code/RULES.md) is "Must Always / Must Never" terse. The contributor surface is wide-open: language reviewers, framework experts, DevOps, domain skills. **The opposite cultural pole from Superpowers**, which refuses 94% of outside skills. ECC absorbs everything and ships profiles; Superpowers refuses everything and ships opinionation. Your framework is closer to Superpowers in spirit but with ECC's research posture — methodology-publishing for-future-team, not catalog-distribution.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Everything Claude Code | Agent Framework Template |
|---|---|---|
| Plan before build | `/plan` + `planner.md` (opus, PROACTIVE) | `/plan` command (manual invocation) |
| Multi-stage review | Single code-reviewer with explicit Pre-Report Gate + FP taxonomy | `/review` facilitator + 2+ specialists (parallel panel) |
| Independent dual review | Santa Method (context isolation, fresh agents per round) | `independent-perspective` multi-instance dispatch |
| Test-first discipline | `tdd-workflow` skill + tdd-guide agent | `testing_requirements.md` + qa-specialist |
| Failure diagnosis | `agent-introspection-debugging` skill (4-phase self-debug) | `failure_taxonomy.md` (8 named classes) |
| External-pattern intake | Loose contributor pipeline (`CONTRIBUTING.md`) | `/analyze-project` + adoption log + Rule of Three |
| Session bootstrap | `SessionStart` hook + observer-loop + state persistence | `SessionStart` hook + `BUILD_STATUS.md` + 6-point dashboard |
| Context budgeting | `context-budget` skill (token audit methodology) | None — implicit |
| Reasoning capture | None — `observe.sh` captures tool calls, not deliberation | Four-layer stack: events.jsonl → SQLite → memory → optional vector |
| ADR / decision lineage | None | ADR series + `framework-lineage.yaml` + Steward |

### Theirs-only (you don't have this)

- **Hook-runtime gating** (`ECC_HOOK_PROFILE`, `ECC_DISABLED_HOOKS`) — tune hook matrix without editing hook files.
- **Install profiles** (core / developer / security / research / full) — selective subset adoption.
- **Multi-harness sync** — same catalog deployed across 8 harnesses with parallel rule/skill mirrors.
- **GateGuard fact-forcing hook** — blocks first Edit/Write/MultiEdit to a file and demands investigation (importers, schemas, instruction). A *pre-action* discipline gate that's not in your stack.
- **Pre-Report Gate inside the code-reviewer** — 4 questions before writing any finding; "Zero findings is valid" clause; HIGH/CRITICAL require proof (snippet + scenario + why existing guards don't catch it). 24/25 in your analyst's scoring.
- **Santa Method context isolation** with both-must-PASS verdict and convergence loop.
- **Confidence-scored instinct architecture** with project-scoping by git-remote-hash.
- **Prompt Defense Baseline** copy-pasted into 60 agents (uniform anti-injection posture).
- **`context-budget` calibration numbers** — concrete token estimates per artifact type.
- **`rules-distill` and `skill-comply`** automation skills for catalog hygiene.
- **`run-with-flags.js` wrapper pattern** — uniform entry point for every hook with profile/disabled-set evaluation.
- **Stop-time batched format+typecheck** (`stop:format-typecheck`) — defer per-Edit linting cost to a single batched pass.

### Yours-only (they don't have this)

- **Reasoning-capture infrastructure** (Layer 1-4) — ECC captures tool-call observations but no deliberation transcripts or curated memory.
- **ADRs as immutable decision history** with supersession references.
- **Steward agent + `framework-lineage.yaml`** — no equivalent governance of cross-derivation drift.
- **Sourced-assertion memory substrate** (`assertion_store/`) — ECC's "instincts" carry confidence + evidence but no source-URI Suchness preservation.
- **12-specialist panel with Values + Domain Lens** — ECC has 60 narrow-role agents; none is a *perspective* dispatched on adversarial review.
- **Education gates** (walkthrough / quiz / explain-back) — ECC trusts the developer as the gate.
- **Failure taxonomy** with named recovery paths and retry limits.
- **Quality gate** with regression-ledger check + review-existence enforcement.
- **Adoption log** with Rule of Three for external patterns.
- **Cross-agent dispatch + multi-instance protocols** (4 instance types pre-approved for independent-perspective).
- **Retro / meta-review nested loops.**
- **Cost-attribution telemetry** via `ingest_token_usage.py` (ADR-0013) — ECC has a cost-tracker hook but no model-pricing YAML or per-discussion attribution.

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Reasoning capture is still the central differentiator.** ECC's `observe.sh` captures tool-call observations, and `continuous-learning-v2` clusters them into "instincts" with confidence scores — but **no deliberation transcripts, no ADRs, no decision lineage**. The instinct format (trigger / confidence / domain / evidence) is structurally adjacent to your assertion store, but the substrate underneath is operational telemetry, not source-cited reasoning. Your bet on reasoning-as-primary-artifact holds: even at 230 skills and 60 agents, ECC institutionally remembers *what the model did*, not *what the team decided and why*.

2. **Curation over catalog is your strategic edge.** ECC has 230 skills with 18 install profiles; the SOUL.md still claims "135 skills" and CLAUDE.md mentions "30 specialized agents" while WORKING-CONTEXT.md says 60. That drift is the cost of scale. Your 12 agents + 17 commands + 6 skills is a deliberate ceiling. The framework-evolution path (Steward → developer → /review) is professional governance ECC lacks.

3. **Steward / lineage / immutable-ADR triad is unique value.** ECC has no equivalent. Their version-management is a Rust control-plane (`ecc2/`), changelog, and PR backlog — operational, not philosophical. Your lineage manifest + Steward gate + ADR supersession-only doctrine is *the* differentiator for a methodology-publishing template.

4. **12-specialist panel produces real dissent.** ECC's 60 agents are all *narrow-role workers* (language reviewer, build resolver, refactor cleaner). None has a Values block; none is dispatched on adversarial review. The 12-agent deliberation captured at DISC-20260516-050945 produced genuine Steward-vs-independent-perspective dissent that ECC's catalog architecture cannot generate.

5. **Four-layer capture stack is publishable methodology.** ECC's session-state persistence (PreCompact → SessionStart restore) lives in hooks that are tuned by environment variables — useful for individual operators, but the capture is not an institutional artifact. Your stack converts session reasoning into curated memory through a human gate (Principle #7). That's the methodology-publishing claim.

6. **Principle #8 substrate discipline holds.** Your hooks are PowerShell + Python; your rules are markdown. ECC has 60+ hook entrypoints, a `run-with-flags.js` wrapper, a Node hot-path dispatcher, a JSON schema validator, and a Rust control-plane in alpha. ECC's surface is structurally heavier than yours because it has to be — multi-harness sync forces parallel surfaces. Your substrate stays light; the cost is paying for cross-harness portability you don't need (you're Claude-Code-only by design).

---

## 4. Weaknesses This Comparison Exposes

### 4.1 No hook-runtime gating — your hooks are binary on/off

ECC's `ECC_HOOK_PROFILE=minimal|standard|strict` and `ECC_DISABLED_HOOKS=...` ([`hooks/hooks.json:43-340`](../../../../research_projects/everything-claude-code/hooks/hooks.json)) let an operator switch hook intensity without editing config or restarting. Your hooks are file-listed in `.claude/settings.json` and either run or don't. A derived project that needs lighter validation for a hot-path session, or a stricter posture for a security-sensitive task, has no calibration knob.

**Maps to**: §5.4 — structural-craft contribution. Below v4 attention threshold but worth seeding.

### 4.2 No install-profile primitive — derived projects inherit everything

Your template spawns derivatives by full instantiation. ECC's profile system (`core` / `developer` / `security` / `research` / `full`) lets users pick a subset based on their use case. Insight Journal is a clinical journaling app; VerificationPortal is a verification workflow; Howie is yet to bootstrap. Each inherits all 12 agents + 17 commands + 14 rules + 6 skills + 4-layer capture stack — even when several of those are unused.

This is **a fresh-eyes observation specific to template-vs-derived dynamics**. Not a v4 item; not in the ANALYSIS rubric.

**Maps to**: §5.4 — structural-craft contribution.

### 4.3 GateGuard pattern (fact-forcing first-touch gate) has no equivalent

ECC's `pre:edit-write:gateguard-fact-force` ([`hooks/hooks.json:91-97`](../../../../research_projects/everything-claude-code/hooks/hooks.json)) blocks the *first* Edit/Write/MultiEdit to any file and demands the agent demonstrate it has investigated importers, data schemas, and user instruction before allowing the edit. This is a behavior-shaping primitive at the *pre-tool* layer — it forces context-grounding before action.

Your framework relies on the agent voluntarily reading surrounding code via Read tool. The Pre-Report Gate (v4 Sprint 1) addresses this at review time; GateGuard addresses it at write time. Different leverage point.

**Maps to**: §5.4 — structural-craft contribution.

### 4.4 No skill-authoring meta-discipline (carried over from comparison-01)

ECC has a `docs/SKILL-DEVELOPMENT-GUIDE.md` and a `skill-create` command, but no equivalent of Superpowers' `writing-skills` (TDD applied to skill authoring with pressure scenarios). ECC's catalog scale (230 skills) means content quality has measurable drift — the WORKING-CONTEXT.md confirms an active audit lane ("rewrite content-facing skills to use source-backed voice modeling, remove generic LLM rhetoric, canned CTA patterns"). The same risk applies to your Path A skills investment.

**Maps to**: §5.4 — structural-craft contribution (cross-references comparison-01 Meta-Question 4).

### 4.5 No batched-cost optimization at Stop-time

ECC's `stop:format-typecheck` hook ([`hooks/hooks.json:267-273`](../../../../research_projects/everything-claude-code/hooks/hooks.json)) accumulates edited file paths during a session via `post:edit:accumulate` and runs format + typecheck *once* at Stop time on the batch, rather than after every Edit. Your `auto-format.sh` runs ruff format + ruff check on every Edit. The batched approach is a cost discipline visible in ECC; it's not in your scope.

**Maps to**: §5.4 — structural-craft contribution; below v4 threshold.

### 4.6 Surface drift is a real concern at scale (lessons for Path A)

ECC's SOUL.md says "30 specialized agents, 135 skills, 60 commands"; WORKING-CONTEXT.md says "47 agents, 79 commands, 181 skills"; AGENTS.md says "60 agents, 230 skills, 75 legacy command shims"; plugin.json description says "60 agents, 230 skills, 75 legacy command shims" again. **Three different counts in three documents.** Your project-analyst flagged this as an anti-pattern (documentation count drift). The lesson for your framework: as Path A's skills investment grows the catalog, drift becomes structural — needs a count-authoritative-source rule baked into `.claude/rules/framework_doc_sync.md`.

**Maps to**: §5.4 — structural-craft contribution.

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How ECC stands against your 8 Non-Negotiable Principles:

| # | Principle | ECC stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **Disagrees by omission** — captures *tool-call observations*, not deliberation | Compatible (no contest) | ECC's instinct architecture is operational telemetry. Your reasoning capture has no peer. Hold. |
| 2 | Capture must be automatic | **Agrees, different leverage** — captures tool calls 100% via PreToolUse hook; clusters into instincts via background Haiku agent | Compatible | ECC's `observe.sh` + observer-loop is a credible second-order substrate for instinct learning; your structured-command capture is for deliberation. Different goals, both automatic. |
| 3 | Collaboration precedes adversarial rigor | **Disagrees — Santa Method is intentionally adversarial** | **Yes** | ECC's strongest verification pattern (Santa) is adversarial by design. Your Principle #3 scopes adversarial to security/fault-injection/anti-groupthink. The Santa Method context-isolation primitive (v4 Sprint 2) fits Principle #3 only if reframed as "anti-groupthink scope" — worth being explicit. |
| 4 | Independence prevents confirmation loops | **Strongly agrees, sharper** — fresh agents per round, no shared memory between reviewers | Compatible (and sharper) | ECC's Santa Method is the architecturally purer form of your independent-perspective dispatch. v4 already gates context isolation to HIGH/CRITICAL in Sprint 2. |
| 5 | ADRs are never deleted | **No equivalent** | Neutral | ECC has no decision-history concept. Yours has one. Hold. |
| 6 | Education gates before merge | **Disagrees by omission** | Compatible (no contest) | ECC trusts the developer as the gate. v4 substantially reframes #6 (Option C default, Option B carve-out for 4 security classes). ECC's silence is not a signal. |
| 7 | Layer 3 promotion requires human approval | **Partial — instinct format requires human review, but instinct cluster→skill *evolution* is automated** | **Yes** | ECC's `continuous-learning-v2` evolves instincts into skills/commands/agents via clustering — closer to automated promotion than you'd allow. Adopt format only, decline evolution (already v4 working position). |
| 8 | Least-complex intervention first | **Strongly disagrees — ECC is maximally-complex by design** | **Yes — fundamental** | ECC is 60 agents, 230 skills, 75 commands, 60+ hooks, Rust control-plane in alpha. The opposite pole. Your Principle #8 *is the right principle for your project type*. Hold the line; this is by-design divergence. |

**Four principles are challenged: #2, #3, #7, #8.** #3 surfaces a Santa-Method classification question (is "anti-groupthink" wide enough to cover dual-independent-reviewer?). #7 is settled in v4 (instinct format yes, automation no). #8 is by-design divergence with ECC's strategic posture; your project is methodology-publishing, ECC's is performance-system-distribution.

### 5.2 Adoption Candidates — v4-Aligned

Each pattern carries a **v4 status tag**. Patterns 1-9 below inherit scores from [ANALYSIS-20260515-everything-claude-code.md](../analysis/ANALYSIS-20260515-everything-claude-code.md); per the pre-flight rule, I do not re-score them. New scoring (Patterns 10-12) reflects fresh-eyes findings.

#### Pattern 1 (FP Taxonomy Pre-Report Gate sub-pattern): Pre-Report Gate only

**Score: 24/25 (FP Taxonomy)** — **CONFIRMED — v4 Sprint 1 at 0.78 confidence (Pre-Report Gate sub-pattern only)**

| Dim | Score (from ANALYSIS) | Rationale |
|---|---|---|
| Prevalence | 4 | Explicit pre-report gate is distinctive |
| Elegance | 5 | 4-question gate, drop-in markdown |
| Evidence | 5 | Mature: 183K stars, 1,723 tests |
| Fit | 5 | Drop-in addition to qa/architecture/security specialist agents |
| Maintenance | 5 | Low ongoing cost |

**Status note**: v4 commits the **Pre-Report Gate sub-pattern only** to Sprint 1 at 0.78 (independent-perspective turn 4, turn 16). The full FP-taxonomy (HIGH/CRITICAL proof requirement, common false-positives list, "Zero findings is valid" clause) is held for re-evaluation in Sprint 2 once survival rate is measurable. My analysis confirms the Sprint 1 framing is correct: the Pre-Report Gate is the load-bearing primitive; the rest of the taxonomy is language-specific noise that doesn't generalize cleanly to a Python/FastAPI codebase.

**Action**: Sprint 1 — add Pre-Report Gate (4 questions) to `qa-specialist.md`, `architecture-consultant.md`, `security-specialist.md` per v4 working position.

#### Pattern 6 (Agent Introspection Debugging)

**Score: 20/25** — **DELIBERATED — v4 Sprint 2, gated on Tier 0**

Status carried from v4. My read: the four-phase loop is well-formed (Capture → Diagnose → Contain → Report) and the root-cause pattern table is genuinely useful for autonomous `/build_module` runs. The "smallest reversible action" recovery heuristic is the sharpest single move. Sprint 2 gating is appropriate — needs the failure-taxonomy plumbing fixed first so retried-classes have a place to land.

**Action**: None now. Sprint 2 re-evaluation will revisit.

#### Pattern 1 in ANALYSIS (Santa Method context isolation)

**Score: 21/25** — **DELIBERATED — v4 Sprint 2, HIGH/CRITICAL only**

Status carried from v4. v4's working position (context isolation for HIGH/CRITICAL tier, not full convergence loop) is the right adapt-don't-adopt move. My fresh observation: the "both must PASS, not majority" rule is the architecturally load-bearing piece — it's what differentiates Santa from a parallel-panel review. When v4 Sprint 2 re-evaluates, the question is whether HIGH/CRITICAL reviews should require **both specialists to APPROVE** rather than facilitator-synthesized verdict. That's the principle worth porting, not the iteration cap.

**Action**: None now. Captured for Sprint 2 re-evaluation.

#### Pattern 8 in ANALYSIS (Context Budget Audit one-time session)

**Score: 19/25** — **DELIBERATED — v4 Sprint 2, one-time practice**

Status carried from v4. ECC's calibration numbers (~500 tokens per MCP tool schema, agents >200 lines = heavy, descriptions >30 words = bloated frontmatter) are concrete enough to make the audit actionable in one session. Worth pairing with `ingest_token_usage.py` (ADR-0013) for cost-attribution baseline.

**Action**: None now. Sprint 2.

#### Pattern 10: Hook-Runtime Profile Gating (NEW — structural-craft adjacent)

**Score: 18/25** — **Below threshold; structural-craft observation**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 2 | Unique to ECC in this survey |
| Elegance | 4 | Single env-var switch in `run-with-flags.js`; tidy |
| Evidence | 4 | Shipped in v1.8.0+, multiple test files validate |
| Fit | 4 | Wraps cleanly around your existing `.claude/hooks/` |
| Maintenance | 4 | Low — wrapper script, profile constants in JSON |

**Below threshold, but worth seeding**: when Path A's skills investment lands SessionStart bootstrap (Pattern 1 in comparison-01), the same `using-the-framework` skill could read a `FRAMEWORK_HOOK_PROFILE` env var to scale verbosity. Mark as structural-craft contribution rather than Sprint candidate.

**Status**: Structural-craft contribution (§5.4).

#### Pattern 11: GateGuard Fact-Forcing Pre-Edit Gate (NEW)

**Score: 19/25** — **Below threshold; Path A staging-adjacent**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | Distinctive to ECC; conceptually similar to Pre-Report Gate at write time |
| Elegance | 4 | First-touch-per-file gate is structurally clean |
| Evidence | 3 | Documented as pre-write but limited test surface visible |
| Fit | 4 | Your `validate_tool_use.py` already runs at PreToolUse Write/Edit — could grow this gate |
| Maintenance | 4 | Markdown-pluggable gate criteria |

**Status note**: This is a *pre-action* sibling of the Pre-Report Gate. The Pre-Report Gate prevents low-quality findings; GateGuard prevents low-context edits. Path A's R3 (imperative voice tightening in skills) is adjacent but not identical. Worth re-scoring after Path A R1 + R2 land — if the agent's behavior on first-touch edits remains low-context, this gate is the right structural escalation.

**Action**: Defer; re-score after Path A R1+R2.

#### Pattern 12: Catalog Count Authoritative Source (NEW — anti-pattern lesson)

**Score: not formally scored — anti-pattern lesson, hygiene rule**

Three documents in ECC give three different agent/skill/command counts (SOUL.md: 30/135/60; WORKING-CONTEXT.md: 47/79/181; AGENTS.md and plugin.json: 60/230/75). At your current scale (12 agents, 17 commands, 14 rules, 6 skills) drift is invisible; at Path A's projected scale (skills investment growing skills surface), it becomes structural. The fix is upstream: declare a single source of truth (probably `framework-lineage.yaml` or a new manifest at `.claude/manifest.yaml`) and reference it from all surface-facing docs. **No new content** — a rule in `framework_doc_sync.md` saying "counts live in the manifest; docs reference, never duplicate."

**Action**: Path A R6-adjacent (command-surface audit) is the right moment to add this rule.

### 5.3 Verdict Tally — v4-Aware

- **CONFIRMED — v4 Sprint 1** (1):
  - FP Taxonomy → Pre-Report Gate sub-pattern (0.78) — confirmed from ANALYSIS, sub-pattern scoping correct
- **DELIBERATED — v4 Sprint 2, gated on Tier 0** (2):
  - Agent Introspection Debugging (20/25)
  - Santa Method context isolation, HIGH/CRITICAL only (21/25)
- **DELIBERATED — v4 Sprint 2, one-time practice** (1):
  - Context Budget Audit (19/25)
- **Path A staging-adjacent** (0 net-new; GateGuard re-scored later)
- **Below threshold** (3):
  - Confidence-Scored Instinct format only — v4 already accepts format, declines automation (17/25)
  - Hook-Runtime Profile Gating (18/25) — see §5.4 instead
  - GateGuard Fact-Forcing Pre-Edit Gate (19/25) — defer; re-score post-Path A
- **Structural-craft contributions** (5): see §5.4

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

These are the genuine additive value of the outside-eyes pass. None appear in v4 or the ANALYSIS doc.

#### Contribution 1: Install profiles solve template-derived inheritance bloat

**Frame**: ECC's `core` / `developer` / `security` / `research` / `full` profile architecture is structurally identical to the problem your template-derived model has: the template inherits everything to the derivative. ECC sidesteps this with profile manifests (`install-plan.js --profile <X>` + `install-apply.js`). The user's framework has *intentionally* not adopted this — `framework-lineage.yaml` encodes "pinned traits" (intentional divergence) per derivation, which is your closer-to-philosophical version of the same control.

**Question**: at what derivation count does the profile primitive earn its keep? IJ + VP today is two; Howie makes three; if a fourth derivation surfaces patterns that should *exclude* parts of the template (e.g., Howie may not need education gates if its audience is technical), a profile primitive becomes a real lever. v4 has no position on this; it's worth tracking as a derived-project signal.

**Status**: Open question, framework-evolution signal, not adoption candidate.

#### Contribution 2: Hook-runtime profile gating

**Frame**: ECC's `ECC_HOOK_PROFILE=minimal|standard|strict` and `ECC_DISABLED_HOOKS=...` ([`hooks/hooks.json:43-340`](../../../../research_projects/everything-claude-code/hooks/hooks.json)) live above the hook content via a wrapper (`run-with-flags.js`). The hook scripts don't need to know about the profile; they exit cleanly when disabled. Your hook stack runs binary on/off via `.claude/settings.json`. A derived project that wants stricter posture for `/build_module` and lighter posture for exploratory chat has no calibration. The wrapper-script primitive is small (one Node file plus a JSON profile map) and additive.

**Status**: Structural-craft observation. Below v4 attention threshold. Worth surfacing for Path A R6 (command-surface audit) — if commands have runtime profiles, hooks should too.

#### Contribution 3: First-touch context-grounding gate

**Frame**: GateGuard ([`hooks/hooks.json:91-97`](../../../../research_projects/everything-claude-code/hooks/hooks.json)) is a *pre-action* discipline. The Pre-Report Gate is a *pre-finding* discipline. Together they form a two-stage anti-hallucination posture: don't act without context-grounding; don't report without proof. v4 commits the Pre-Report Gate to Sprint 1. Its sibling — first-touch pre-edit context-grounding — has no v4 position. The framework currently relies on agent discretion to read surrounding code before editing. For autonomous `/build_module` runs, this is a real exposure.

The leverage point is the existing `validate_tool_use.py` PreToolUse hook (already running on Write/Edit). Adding a first-touch-per-session flag that requires the agent to demonstrate context (via Read of importers or schema before Write/Edit on a file) is a small extension. **Worth scoring after Path A R1+R2 land** — if those tighten in-skill behavior shaping, GateGuard may become redundant; if they don't, GateGuard is the right structural escalation.

**Status**: Future adoption candidate, deferred pending Path A signal.

#### Contribution 4: Catalog-count drift is a structural anti-pattern at scale

**Frame**: ECC's SOUL.md / WORKING-CONTEXT.md / AGENTS.md / plugin.json disagree on agent/skill/command counts. Your project-analyst flagged this as anti-pattern in ANALYSIS-ecc. The lesson for your framework specifically: at current scale (12/17/14/6) drift is invisible. Path A grows the skills surface; the drift risk activates. The fix is structural — one manifest as authoritative source, all surface docs reference it.

This is a hygiene rule, not a pattern. It belongs in `framework_doc_sync.md` (which already exists in your `.claude/rules/`). One sentence: *"Catalog counts (agents / commands / rules / skills) are authoritative in `framework-lineage.yaml` or `.claude/manifest.yaml`; all other documents reference, never duplicate."* No additional infrastructure.

**Status**: Hygiene rule. Worth adding when Path A R4 (SKILL.md skeleton adoption) is being designed.

#### Contribution 5: ECC's commercial posture is your inversion-test

**Frame**: ECC has \$19/seat/month ECC Pro, a GitHub App marketplace product, sponsorship tiers, and "OSS stays free" guard. The README opens with "the performance system for AI agent harnesses." The product is built to monetize the catalog. Your framework's [`CLAUDE.md`](../../../../agent_framework_template/CLAUDE.md) opens with: *"The framework exists to serve contributors and users. Its reasoning, memory, capability, and evolution must never accumulate value at their expense."* The Prime Objective formally refuses extraction.

ECC is not extractive — they ship MIT and the OSS catalog is real — but their *posture* assumes scale-via-volume and monetization-via-pro-tier. Your posture assumes scale-via-curation and value-via-methodology. **ECC is the inversion test for your Prime Objective**: every adoption from ECC needs to clear "would this pattern, at scale, push the framework toward extraction?" The answer for Pre-Report Gate is no (it reduces noise, serves the user). The answer for instinct-cluster→skill evolution automation is yes (it accumulates value into the framework's "intelligence" away from the user) — which is exactly why v4 declines that piece.

**Status**: Strategic-posture observation. Not adoption candidate. Useful frame for future evaluations.

### 5.5 Meta-Questions for Framework Evolution

1. **At what derivation count does the install-profile primitive become a real lever?** Today: 2 (IJ + VP). Howie makes 3. If pinned-traits in `framework-lineage.yaml` start carrying repeated "excludes education_gates" or "excludes assertion_store" entries, that's the signal to move from per-derivation pin to declared profiles.

2. **Is Principle #3 ("Collaboration precedes adversarial rigor") wide enough to cover dual-independent-reviewer convergence?** Santa Method is intentionally adversarial. v4 Sprint 2 considers context isolation for HIGH/CRITICAL — but the principle currently scopes adversarial to *security / fault-injection / anti-groupthink*. Either the Santa adaptation goes under "anti-groupthink" (loose fit) or Principle #3 needs an explicit "independence-by-isolation" clause.

3. **Hook profiles vs. command profiles vs. skill profiles — do they share a substrate?** If Path A R6 audits 17 commands and 4-6 convert to auto-triggered skills, you may end up with a profile system anyway. Worth designing the profile primitive once (env var + manifest) rather than thrice.

4. **What does ECC's `WORKING-CONTEXT.md` pattern add over your `BUILD_STATUS.md`?** ECC distinguishes *sprint state* (WORKING-CONTEXT.md — current sprint, blockers, constraints, dated execution notes) from *session state*. Your BUILD_STATUS.md does both. At template-vs-derived scale, splitting may earn its keep in derived projects (especially Howie when it bootstraps). v4 marks Pattern 9 from ANALYSIS as "partially covered" — worth re-evaluating when Howie's data lands.

---

## 6. Open Tasks Surfaced by This Document

Captured for forward visibility, not for immediate action:

| Task | Owner | Sequencing |
|---|---|---|
| Sprint 1: Pre-Report Gate (sub-pattern only) in qa/architecture/security specialist agents | framework developer | Post-Tier-0 |
| Sprint 2: Agent Introspection Debugging as new skill | framework developer | Tier 0 healed + 60d data |
| Sprint 2: Santa Method context isolation in `review_gates.md` for HIGH/CRITICAL — including "both must APPROVE" rule clarification | framework developer | Tier 0 healed + 60d data |
| Sprint 2: Context Budget Audit one-time session with ECC's calibration numbers | framework developer | Tier 0 healed |
| Sprint 1/Path A R4: Add hygiene rule to `framework_doc_sync.md` — catalog counts authoritative in manifest, docs reference only | framework developer | Whenever Path A R4 is being designed |
| Re-score GateGuard fact-forcing pre-edit gate after Path A R1+R2 ship | framework developer | Post-Path-A |
| Track Howie bootstrap signal for install-profile primitive evaluation | steward | When Howie reaches Sprint 1 |
| Decide Principle #3 phrasing for Santa Method adaptation — anti-groupthink scope or explicit independence-by-isolation clause | steward | Before Sprint 2 |
| Re-evaluate Pattern 9 (WORKING-CONTEXT vs BUILD_STATUS split) when Howie's data lands | framework developer | Howie + 60d |

---

## Appendix: What I Didn't Examine

For honesty about scope:

- The `ecc2/` Rust control-plane prototype (alpha; orthogonal to the methodology layer).
- Detailed content of language-specific reviewer agents beyond `code-reviewer.md`, `planner.md`, `silent-failure-hunter.md`.
- The full 230 skills directory — sampled `santa-method`, `agent-introspection-debugging`, `council`, `context-budget`, `continuous-learning-v2`, `verification-loop`, `search-first`, `prompt-optimizer`, `rules-distill`, `skill-comply`, `coding-standards`. The operator/content lane (`brand-voice`, `content-engine`, `investor-materials`, `seo-specialist`) is structurally outside your framework's scope.
- The npm package source (`ecc-universal`, `ecc-agentshield`) — distribution mechanism, not methodology.
- The `tests/` directory beyond confirming the gate-guard, hook-flag, and config-protection test files exist.
- Non-English documentation (`docs/ja-JP/`, `docs/zh-CN/`, `docs/pt-BR/`, etc.) — translation surfaces, not new content.
- The multi-harness adapter code (`.codex/`, `.cursor/`, `.opencode/`, `.gemini/`, `.kiro/`, `.trae/`) — relevant only if your framework ever pivots from Claude-Code-only.
- The ECC Pro hosted product and GitHub App marketplace surface (commercial layer, not methodology).

If a future pass needs more granularity, the repo is at `C:/Work/AI/research_projects/everything-claude-code/`.
