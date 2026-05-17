---
synthesis_id: SYNTHESIS-20260516-comparison-cross-cut
date: 2026-05-16
status: LIVING DOCUMENT (working observations, non-binding, candidate input for v5)
analyst: claude-opus-4-7
relates_to: SYNTHESIS-20260515-adoption-brief-v4
posture: additive — surfaces what fresh-eyes structural-craft pass adds to v4 working positions
sources:
  - docs/research/comparison-01-superpowers.md (v4-aligned rewrite, 432 lines)
  - docs/research/comparison-02-everything-claude-code.md (372 lines)
  - docs/research/comparison-03-ruflo.md (334 lines)
  - docs/research/comparison-04-open-design.md (369 lines)
  - docs/research/comparison-05-obsidian-cli-skill.md (347 lines)
  - docs/research/comparison-06-andrej-karpathy-skills.md (346 lines)
synthesis_confidence: 0.65
confidence_notes: |
  Lower than v4's 0.75 because this is one analyst's cross-cut pass, not a 12-agent
  deliberation. 0.65 reflects: (a) 6-doc sample of fresh-eyes work, (b) most patterns
  are corroborated within the 6 comparisons, (c) several patterns rest on cross-source
  Rule-of-Three signal (Path A measurement infrastructure: 3 sources; compositional
  assembly: 3 sources; sync-contract / drift: 3 sources), (d) the patterns scored
  above threshold in individual comparisons may need v4-style 12-agent re-deliberation
  before enactment.
purpose: |
  Cross-cut analysis of the 6 comparison documents written in the research wave. Surfaces
  Rule-of-Three candidates (patterns appearing in 2+ comparisons with corroborating
  evidence), structural-craft patterns v4 lacks, cross-source tensions worth preserving,
  and specific items v5 deliberation should consider.
---

# Comparison Cross-Cut — v1

## Purpose & Posture

This document is the **cross-cut** of the six fresh-eyes comparison documents at `docs/research/comparison-01..06`. It exists because:

1. The 6 comparisons were written *after* v4 SYNTHESIS as a complementary fresh-eyes pass — v4's source list is the 7 ANALYSIS docs, not the comparisons.
2. The comparisons explicitly added structural-craft observations v4 lacks (per `feedback_outside_contractor_mode.md`).
3. Several observations recur across multiple comparisons — a within-research-wave Rule-of-Three signal worth surfacing before v5 deliberation.

**This document is not v5.** It is a candidate input for v5 — a living surface that captures what the cross-cut shows. v4's posture applies: non-binding, observation-only, no enactment.

**Nothing in this document overrides a v4 deliberated position.** Where the comparisons surface evidence against a v4 position (one case: Pattern 3 sequenced two-stage review in comparison-01), that evidence is captured for re-evaluation, not as a now-decision.

## Confidence Calibration

This synthesis is at **0.65 confidence** — meaningfully lower than v4's 0.75. The drop reflects:

- **One-analyst pass, not 12-agent deliberation.** v4's confidence rests on a sealed 18-turn dialectic; this synthesis is a single fresh-eyes cross-cut.
- **Cross-corroboration within the 6 comparisons strengthens specific patterns** (see §3 Rule-of-Three Candidates) — but the 6 comparisons share an analyst, so corroboration is partial confirmation, not independent Rule-of-Three.
- **Source-level Rule-of-Three holds for patterns where the comparisons surface evidence from independent target repos** — e.g., the Eval-Loop pattern is corroborated by Superpowers + Obsidian-CLI + Karpathy (three independent target authors), so the cross-source signal is genuine even if the analyst is one.

Read §3 with this calibration: a 0.65-confidence cross-cut should inform v5 deliberation, not pre-empt it.

---

## What Changed Since v4

v4 was built from 7 ANALYSIS-*.md per-project rubrics. The 6 comparison documents in `docs/research/` were not part of v4's source list. This synthesis surfaces what they add.

**Three things are genuinely new at the cross-cut level:**

1. **Twelve structural-craft observations** v4 doesn't surface (consolidated in §2 below) — focused on artifact shape, voice intensity, prompt-assembly architecture, and adopter-facing surface honesty.

2. **Cross-source Rule-of-Three signals** within the comparison wave — patterns appearing in 2+ comparisons with corroborating evidence from independent target repos (§3).

3. **One direct tension with a v4 working position** — comparison-01's Pattern 3 (sequenced two-stage review) initially contradicted v4's PARALLEL-preserved working position; the analyst withdrew the recommendation and captured the evidence for v4 Sprint 2 re-evaluation per existing process (§4).

**What this synthesis confirms about v4:**

- v4's Sprint 1 commitments (Rationalization Tables, Verification-Before-Completion, Karpathy Principles 1–3 as agent-behavior-defaults.md, Karpathy Principle 4 merge, Pre-Report Gate sub-pattern, REFERENCE.md split) are all corroborated by the comparison pass. None are challenged.
- v4's Education Gate reframe (Option C default + Option B carve-out) is corroborated by Karpathy's omission and Open Design's merge-bar alternative — different audience, different leverage point. The reframe stands.
- v4's DEFER on Pattern 3 (sequenced two-stage review, Sprint 2 measurement-gated) is correct — comparison-01's analyst alignment with the ANALYSIS-superpowers score was naive of the cross-project deliberation. The Sprint 2 re-evaluation framing is sharper.

---

## §2 — Structural-Craft Observations v4 Lacks

Each item below is a §5.4 contribution from one or more comparisons. Items are ordered by aggregate signal strength (how many comparisons surface a related observation × how directly they map to Path A or Sprint-1 enactment).

### 2.1 Path A's threshold calibration is unmeasurable without an eval-loop layer

**Sources**: comparison-01 §5.5 Meta-Question 4 (Superpowers writing-skills TDD-on-documentation), comparison-05 Pattern 2 + Contribution 1 (Obsidian-CLI eval-set + HTML tool + observable 3-rewrite cycle), comparison-06 Meta-Question 1 (Karpathy compression discipline as evidence eval-driven authoring works).

**Three independent target repos converge on this observation.** Path A R1's SessionStart bootstrap commits to "when clearly relevant" as the threshold — but "clearly relevant" is unmeasurable without a labeled set of positive/negative skill-invocation cases. Without measurement, threshold calibration is folklore.

The lightest possible eval-loop is concrete and tested: 35 labeled cases in JSON + a 220-line single-file HTML editor (Obsidian-CLI). No frameworks, no dependencies. The eval-rewrite habit (three same-day Obsidian-CLI rewrites driven by observable failures) is what produces CSO-quality descriptions; CSO as content is the output, the loop is the generative pattern.

**Path A implication**: ship an `eval/` directory per skill alongside Pattern 1 SessionStart bootstrap. Reuse Obsidian-CLI's `eval_review.html` directly. Run the eval set before and after the bootstrap lands; the diff is calibration data.

### 2.2 Compositional / on-demand assembly is missing at the prompt-assembly layer

**Sources**: comparison-02 Contribution 1 + 2 (ECC install profiles + hook-runtime gating), comparison-04 Pattern 1 + Contribution 1 (Open Design `od.craft.requires` declarative-injection at 21/25 Path A staging), comparison-06 Pattern 5 (Karpathy multi-target distribution — pattern of declarative metadata).

**Three independent target repos converge on this observation.** The framework's assembly model is "auto-load everything in the manifest at session start." Open Design loads 293 catalog entries (133 skills + 11 craft + 149 design-systems) because nothing is loaded by default — entries are pulled in by per-skill `od.craft.requires` declarations. ECC has 230 skills × 18 install profiles. Karpathy ships one source artifact to three targets via explicit sync contract.

The framework today (~32 entries) fits comfortably in the auto-load model. Path A's skills investment grows the catalog. At ~50 entries the inherited-surface cost compounds across derived projects (Insight Journal, VerificationPortal, future Howie). **Decide during Path A's first 5 skills whether to build the compositional substrate, not after.** Building it after means rewriting frontmatter for entries already in production.

**Path A implication**: a `requires:` frontmatter field per skill + a request-time assembler (potentially in the SessionStart hook path) is the substrate-level expression of Principle #8 at the prompt-assembly layer.

### 2.3 Documentation drift at scale becomes a structural anti-pattern

**Sources**: comparison-02 §4.6 + Contribution 4 (ECC: SOUL.md / WORKING-CONTEXT.md / AGENTS.md / plugin.json give three different agent/skill/command counts), comparison-05 Contribution 2 (Obsidian-CLI: plugins/ mirror stale by 39 lines from canonical skills/), comparison-06 Contribution 4 (Karpathy: internal sync-contract pattern at per-artifact level).

**Three independent target repos surface this.** Multiple representations of the same content drift unless mechanically synced. The framework today has invisible drift risk; Path A's growth activates it. The fix is structural: declare a single source of truth per content type, reference from everywhere else.

The framework already has `framework_doc_sync.md` at the framework-wide level. What's missing is **per-artifact sync contracts** (Karpathy's CURSOR.md:26-28 pattern): each rule, each skill, each agent declares which sibling artifacts must update together. The `lineage_file_drift` SQLite table already tracks file-level drift; verify it covers frontmatter, not just file presence.

**Path A implication**: when authoring `using-the-framework/SKILL.md` (R1) and the SKILL.md skeleton (R4), include an optional "Sync contract" section. When `agent-behavior-defaults.md` ships in Sprint 1, name its sync siblings explicitly.

### 2.4 Token-cost is currently telemetry; could be policy

**Sources**: comparison-02 Contribution 2 (ECC hook-runtime profile gating), comparison-03 Pattern 5 + Contribution 1 (Ruflo audit-as-CI-gate with monotone-decreasing baseline at 22/25 Path A staging + token-cost as design discipline ADR-098), comparison-06 Meta-Question 2 (Karpathy compression discipline as evidence compression has adoption value).

**Three independent sources.** The framework's ADR-0013 logs token usage; analysis-time tooling computes cost from raw counts. This is measurement. Ruflo's ADR-098 Part 2 sets a *budget* (agent prompts ≤60 lines) with discrete enforcement commits + a CI gate that's monotone-decreasing. This is *policy*.

The leverage points differ. Measurement tells you what happened; budgets tell you what's allowed. v4 Sprint 1's REFERENCE.md split addresses the symptom once; without a policy + audit gate, the same drift recurs after every Sprint addition.

**Path A implication**: after Path A R3 (voice tightening) and R2 (Red Flags propagation to skills) land, add a baseline audit. Pattern works for any discipline added:

| Discipline | Baseline metric |
|---|---|
| Red Flags tables in skills | count of skills without `\| Excuse \| Reality \|` table |
| Agent prompt size | count of agents > N lines (calibrate from Sprint 1 REFERENCE.md split) |
| Skill imperative voice | count of skills with voice intensity < 3/5 |
| CSO descriptions | count of skill descriptions matching "Reference when" anti-pattern |

The pattern generalizes far beyond MCP tool descriptions. **This is the long-term enforcement mechanism for every discipline Path A adds.**

### 2.5 The framework lacks named-violation block-list at pre-action / pre-merge time

**Sources**: comparison-02 Pattern 11 (ECC GateGuard fact-forcing pre-edit gate, 19/25), comparison-04 Pattern 3 (Open Design Forbidden Surfaces, 20/25 adopt above threshold).

**Two independent target repos surface the same shape.** The framework has Principles (what to aspire to) and Failure Taxonomy (what breaks at run time). It lacks an enumerated **named-violation block-list** at pre-action / pre-merge time — close-on-sight architectural mistakes, fact-forcing pre-edit context-grounding, banned patterns named with concrete examples.

These are complementary to existing artifacts, not duplicates:
- Principles operate at *what-to-aspire-to* granularity (aspirational)
- Failure Taxonomy operates at *what-breaks-at-runtime* granularity (reactive)
- Forbidden Surfaces / GateGuard operate at *what-not-to-recreate* / *what-context-to-establish-first* granularity (preventive)

**Path A implication**: drop-in addition. New `.claude/rules/forbidden_patterns.md` enumerating 6–10 named violations the framework already implicitly bans (Steward dispatching agents; subagent recursion; `/promote` without human gate; ADR deletion vs supersession; direct `memory/` writes; `discussions/` sealed-directory edits). Plus extend `validate_tool_use.py` PreToolUse hook with a first-touch-per-session flag requiring context demonstration (GateGuard equivalent).

### 2.6 The 5-dim adoption rubric needs anti-grade-inflation discipline

**Source**: comparison-04 Pattern 2 (Open Design 5-Dim Critique skill, 20/25 adopt).

Open Design's `design-templates/critique/SKILL.md` is structurally identical to the framework's 5-dim adoption rubric (prevalence / elegance / evidence / fit / maintenance), with one critical addition: explicit anti-grade-inflation rules.

| Rule | Mechanism |
|---|---|
| Don't average up | Score the worst sustained band, not the kindest |
| Evidence per score | "Feels right" is not evidence |
| Innovation is allowed to be low | Don't punish appropriate conservatism |
| Overall mean above 8/10 is suspicious | Check yourself |

**Why this matters now**: the project-analyst agent's scoring drifts toward inflation across the 6 comparison docs in this wave. Pattern scores cluster at 4/5 with similar rationales. Adoption of this discipline is a Domain Lens addition for the project-analyst agent — single-paragraph change.

**Action**: when `agent-behavior-defaults.md` lands in Sprint 1, add a Scoring Discipline subsection to `project-analyst.md` Domain Lens. Wording template (lifted from Open Design's critique skill):

> *Don't average up — score the worst sustained band. Cite evidence for every score; "feels right" is not evidence. Overall mean above 4.0/5 across all five dimensions is suspicious; check yourself. Innovation/fit is allowed to be low — don't punish appropriate conservatism.*

### 2.7 Imperative-voice prose structures Karpathy uses that the framework's rules don't

**Sources**: comparison-01 Pattern 6 + §4.8 (voice distribution quantification: skills 2/5, commands 5/5, rules 3-4/5, agents 4/5), comparison-06 Contributions 1 + 2 + 3 (trade-off disclosure at top, closing efficacy clause at bottom, self-test sentences embedded in each principle).

**Two angles on the same theme.** comparison-01 measures voice distribution. comparison-06 names three specific prose patterns Karpathy uses that the framework's rules currently don't. The patterns:

1. **Trade-off disclosure at top** — *"These guidelines bias toward caution over speed. For trivial tasks, use judgment."* The framework's rules open with "what this prevents" headers; the trade-off frame is more honest for adopters.
2. **Closing efficacy clause** — *"These guidelines are working if: [observable signals]."* The framework's rules close with "Relationship to Other Rules" — orientation, not verification. The efficacy clause names what to look for and (for measurable signals) what telemetry to consult.
3. **Self-test sentences** — *"Would a senior engineer say this is overcomplicated?"* The framework uses constraint enumerations; self-tests apply in-place without recall-and-check.

**Path A implication**: when `agent-behavior-defaults.md` lands in Sprint 1, preserve Karpathy's three prose primitives. A Path A R3 sibling task is to retroactively add trade-off + efficacy + self-test prose to the framework's existing 14 rules — documentation hygiene, not content change. Candidate framework-wide convention.

### 2.8 "Is it ready?" doc is a missing artifact class for adopters

**Source**: comparison-03 Contribution 3 (Ruflo STATUS.md as distinct artifact class), corroborated by comparison-02 Meta-Question 4 (ECC WORKING-CONTEXT.md vs BUILD_STATUS.md split).

The framework has FRAMEWORK.md (what is this?), CLAUDE.md (how do I configure it?), and BUILD_STATUS.md (session-scoped working state). It lacks a "what currently works?" doc for an adopter — an instantiated derived project asking "which capabilities of the framework are validated vs. aspirational?"

For a methodology-publishing framework with for-future-team posture, this is a real omission. The data exists in `metrics/knowledge_pipeline_log.jsonl` and `metrics/quality_gate_log.jsonl`; nothing renders it for an adopter. A generated `STATUS.md` (one script over knowledge_dashboard.py output) would close the loop.

**Path A implication**: standalone task; can run any time post-Tier-0. Below v4 attention threshold; cited here because for-future-team posture makes it a real gap.

### 2.9 Self-critique loop on agent output, mid-emission

**Source**: comparison-04 §4.2 (Open Design critique skill designed to run on agent's own output before emission).

The framework's `/review` runs post-build, gated to commit time. `build_review_protocol.md` mid-build checkpoints use dispatched specialists, not a self-applied checklist. Open Design's critique skill is structurally different: the agent runs the 5-dim critique against its own output *before emitting it to the user*.

This is a structural option the framework doesn't have. v4 implicitly handles it via panel review post-emission; the mid-emission self-check is a different leverage point — particularly useful for the autonomous `/build_module` runs where panel review fires only at checkpoint boundaries.

**Path A implication**: below v4 attention threshold for now. Worth re-scoring after Path A's R3 (voice tightening in skills) lands — if skills become more behaviorally load-bearing, a mid-emission self-check pattern in those skills becomes higher-leverage.

### 2.10 ECC as inversion-test for the framework's Prime Objective

**Source**: comparison-02 Contribution 5.

ECC's commercial posture — ECC Pro at $19/seat, GitHub App marketplace, "OSS stays free" guard — is structurally opposite to the framework's Prime Objective ("framework must never accumulate value at users' expense"). This becomes a screening lens for any ECC adoption: *would this pattern, at scale, push the framework toward extraction?*

The lens makes existing v4 decisions legible as Prime-Objective-aligned rather than arbitrary:
- Pre-Report Gate (Sprint 1) clears the test — reduces noise, serves user.
- Instinct-cluster → skill evolution automation fails the test — accumulates value into the framework's "intelligence" away from the user. **This is exactly why v4 declines that piece.**

**Status**: strategic-posture frame, not adoption candidate. Useful as a screening question in future adoption deliberations.

### 2.11 Inherited surface compounds across derived projects

**Sources**: comparison-02 Contribution 1 (ECC install profiles), comparison-04 Contribution 1 (Open Design compositional substrate), implicitly across multiple comparisons.

The user's template-vs-derived model means every derived project (Insight Journal, VerificationPortal, future Howie) inherits the full 12-agent + 17-command + 14-rule + 6-skill surface. Insight Journal is a clinical journaling app; VerificationPortal is a verification workflow. Each pays the inherited cost even when several artifacts are unused.

**This is a fresh-eyes observation specific to template-spawn dynamics that v4 does not surface.** ECC's install-profile primitive and Open Design's compositional substrate are two different solutions to the same underlying problem.

**Path A implication**: tracked as derived-project signal. When `framework-lineage.yaml`'s pinned-traits start carrying repeated "excludes X" entries across multiple derivations, that's the trigger to move from per-derivation pin to declared profiles.

### 2.12 Operational checklists as an artifact class parallel to rules

**Source**: comparison-04 §4.4 + Meta-Question 2 (Open Design merge bar).

The framework has principles, rules, agents, commands, skills, hooks — but no **checklist artifact class**. Open Design's merge bar gates concrete artifact compliance ("example_prompt actually works", "Triggers are concrete", "No CDN imports beyond what other skills already use"). The framework's adoption-log entries pass through Rule of Three but not through an operational merge bar.

This is not a duplicate of Principle #6 (which is about the decision-maker) nor of Quality Gate (which is about code). It's a third tier: *the artifact has to satisfy operationally-checkable rules before it ships*.

**Path A implication**: when Path A's skills investment reaches the point of merging the first new skill into the template (vs. usable only in a derived project), the merge-bar concept becomes load-bearing. Lift the structure from Open Design's `docs/skills-contributing.md §5` directly.

---

## §3 — Rule-of-Three Candidates (Cross-Source Corroboration)

The strongest signal from the cross-cut is when an observation surfaces in 3+ comparisons with evidence from independent target repos. Three patterns hit this bar.

### Rule-of-Three Candidate 1: Eval-Loop Infrastructure for Skills

**Sources**: comparison-01 (Superpowers writing-skills), comparison-05 (Obsidian-CLI eval-set + HTML tool), comparison-06 (Karpathy compression discipline).

**Cross-source independence**: three different target authors (obra/Jesse Vincent, pablo-mano, Karpathy via multica-ai). Three different domains (general dev methodology, single-skill, behavioral calibration). Convergent finding.

**Confidence**: 0.78 (target-repo independence is high; analyst is single but evidence is grounded in observable artifacts and git history).

**Aggregate observation**: Path A's commitment to make skills load-bearing requires measurement infrastructure to calibrate the threshold. Obsidian-CLI's eval-set + HTML tool is the lightest possible version (35 cases, 220 lines of HTML). Superpowers' writing-skills meta-skill is the discipline. Karpathy's compression-as-equilibrium is evidence that eval-driven authoring produces durable artifacts.

**v5 deliberation question**: Should Path A R1 (SessionStart bootstrap) be gated on shipping an eval-set per skill?

### Rule-of-Three Candidate 2: Compositional / On-Demand Assembly at the Prompt-Assembly Layer

**Sources**: comparison-02 (ECC install profiles + hook-runtime gating), comparison-04 (Open Design `od.craft.requires` declarative-injection at 21/25), comparison-06 (Karpathy multi-target distribution as small-scale precedent).

**Cross-source independence**: three different target authors. Three different scales (60 agents + 230 skills, 293 entries across three axes, 65 lines + multi-target sync). Three different mechanisms but same underlying observation: at scale, auto-load-everything stops working.

**Confidence**: 0.72 (target-repo independence high; mechanism diversity is itself evidence; threshold for the framework — when does it activate? — is uncertain).

**Aggregate observation**: the framework's current assembly model loads everything in the manifest at session start. This compounds across derived projects. Three different target repos converge on compositional / on-demand assembly as the architectural fix. The mechanism varies; the underlying observation does not.

**v5 deliberation question**: Should Path A R1 (SessionStart bootstrap) include the substrate decision (compositional vs auto-load) — i.e., is this a Path A-R1-blocking architectural call, or a later refactor?

### Rule-of-Three Candidate 3: Multi-Source Documentation Sync Discipline

**Sources**: comparison-02 (ECC: SOUL.md / WORKING-CONTEXT.md / AGENTS.md / plugin.json catalog-count drift), comparison-05 (Obsidian-CLI plugins/ mirror stale by 39 lines), comparison-06 (Karpathy internal sync-contract pattern as the prescriptive answer).

**Cross-source independence**: three different target repos. Two illustrate the failure mode (drift); one illustrates the prescriptive answer (named sync contract). Together they form a problem-solution pair.

**Confidence**: 0.74 (failure mode is observable artifact; prescriptive answer has working precedent at small scale; framework activation threshold is again uncertain).

**Aggregate observation**: the framework will face documentation drift between multiple representations of the same content as Path A grows the catalog. The fix exists (per-artifact sync contracts à la Karpathy CURSOR.md:26-28); the framework's existing `framework_doc_sync.md` operates at the framework-wide level but not at the per-artifact level.

**v5 deliberation question**: Should `framework_doc_sync.md` be amended to require per-artifact sync contracts on rules and skills, or is the framework-wide rule sufficient?

---

## §4 — Cross-Source Tensions Worth Preserving

Per v4's living-document hygiene rule ("genuine dissent preserved, not smoothed over"), these are tensions surfaced across the comparisons that should inform v5.

### Tension 1: Principle #3 scope question — Santa Method classification

**Source**: comparison-02 §5.1 (Principle #3 stress-test).

ECC's Santa Method (v4 Sprint 2 commitment, HIGH/CRITICAL context isolation) is intentionally **adversarial** — dual reviewers, no shared memory, "both must PASS" convergence. The framework's Principle #3 scopes adversarial to *security / fault-injection / anti-groupthink*. Santa Method fits "anti-groupthink" loosely; the principle currently doesn't have an explicit "independence-by-isolation" clause.

**Steward question for v5**: amend Principle #3 to add explicit "independence-by-isolation" scope, or accept Santa Method under "anti-groupthink" with a clarifying note?

### Tension 2: Pattern 3 (sequenced two-stage review) re-evaluation evidence

**Source**: comparison-01 (originally recommended adopt; demoted to DELIBERATED AND DEFERRED per v4's PARALLEL-preserved position).

v4 Sprint 2 has scheduled re-evaluation gated on survival-rate measurement. The fresh-eyes pass surfaced corroborating evidence that the spec-vs-quality separation is structurally cleaner than parallel-panel review for execution-time checkpoints, but withdrew the recommendation per v4 process.

**v5 deliberation question for Sprint 2**: when measurement infrastructure for survival rate is in place, what specifically should the re-evaluation measure to confirm or refute the working position?

### Tension 3: Token-cost as policy vs. telemetry

**Source**: comparison-03 §5.5 Meta-Question 1.

v4's Sprint 1 REFERENCE.md split addresses the symptom of agent prompt bloat. The cross-cut surfaces a stronger pattern: token-cost as design *policy* (Ruflo ADR-098: ≤60 line agent prompts as enforced budget, with audit-as-CI-gate as the enforcement mechanism). The two differ — measurement vs. policy.

**v5 deliberation question**: Should v5 commit to a token-cost policy (budget + audit gate) on top of v4's Sprint 1 hygiene event? If yes, what budgets and which artifacts?

### Tension 4: Compression value vs. framework-rule decomposition

**Source**: comparison-06 Meta-Question 2.

Karpathy's 65-line document gets 130k stars by solving a sharp problem with disciplined compression. The framework's 14 rules total 600+ lines. Several rules cover related territory (`commit_protocol.md`, `review_gates.md`, `autonomous_workflow.md`, `micro_fix_protocol.md`). Karpathy is not evidence the framework is over-decomposed; it is evidence compression has adoption value.

**v5 deliberation question**: Should v5 commission an audit of the framework's 14 rules for consolidation candidates — which rules could merge into a "behavioral defaults" bundle without losing meaning?

---

## §5 — Confirmed v4 Sprint-1 / Sprint-2 Commitments (Cross-Cut Validation)

The comparison pass corroborates these v4 positions. No re-litigation; this is confirmation.

| v4 commitment | Cross-cut corroboration |
|---|---|
| Sprint 1 — Rationalization Tables in rules (0.85) | Comparison-01 confirms; comparison-04 surfaces anti-grade-inflation as parallel pattern in scoring rubric |
| Sprint 1 — Verification-Before-Completion as new rule (0.85) | Comparison-01 added (originally missed); comparison-02 surfaces GateGuard as pre-action sibling |
| Sprint 1 — Karpathy Principles 1-3 as agent-behavior-defaults.md (0.85) | Comparison-06 confirms; adds prose-structure guidance (trade-off disclosure + closing efficacy + self-test sentences) |
| Sprint 1 — Karpathy Principle 4 merge into autonomous_workflow.md (0.78) | Comparison-06 confirms; adds transformation-table format preservation |
| Sprint 1 — Pre-Report Gate sub-pattern (0.78) | Comparison-02 confirms sub-pattern scoping is correct (full FP-taxonomy not generalizable to Python/FastAPI) |
| Sprint 1 — REFERENCE.md split for facilitator + architecture-consultant + qa-specialist (0.58) | Comparison-03 re-scores upward to 21/25 with new evidence (ADR-098 maturity, 4-plugin example set) |
| Sprint 1 — DONE_WITH_CONCERNS additive to build_review_protocol | Comparison-01 added (originally missed) |
| Sprint 2 — Two-Stage Review re-evaluation (PARALLEL preserved) | Comparison-01 originally challenged; recommendation withdrawn; evidence captured for re-eval |
| Sprint 2 — Santa Method context isolation HIGH/CRITICAL only | Comparison-02 surfaces "both must APPROVE" as the architecturally load-bearing piece (vs. iteration cap) |
| Sprint 2 — Context Budget Audit one-time session | Comparison-02 confirms; ECC calibration numbers (~500 tokens/MCP tool, agents >200 lines = heavy) are actionable inputs |

---

## §6 — Inputs for v5 Deliberation

These are the items v5 should explicitly consider, ordered by aggregate confidence × leverage.

### High-confidence, drop-in additions (no architectural change)

1. **Anti-grade-inflation discipline** on `project-analyst.md` Domain Lens (§2.6). Drop-in. Single-paragraph change. Addresses observable inflation in the project-analyst's scoring across the comparison wave.

2. **`.claude/rules/forbidden_patterns.md`** enumerating 6–10 named violations (§2.5). Drop-in additive. Complements existing `failure_taxonomy.md` (which is reactive) with preventive named-violation enumeration.

3. **Trade-off disclosure + closing efficacy clause + self-test sentences** as required structural elements in new behavior-shaping rules (§2.7). When `agent-behavior-defaults.md` ships in Sprint 1, use these. Path A R3 sibling task: retroactively add to existing 14 rules.

### Path A staging (deferred until post-Tier-0)

4. **Eval-loop infrastructure** per skill (§2.1, Rule-of-Three Candidate 1). Ship alongside Path A R1 SessionStart bootstrap. Reuse Obsidian-CLI's `eval_review.html`.

5. **Compositional / on-demand assembly substrate** (§2.2, Rule-of-Three Candidate 2). Architectural call for Path A's first 5 skills. Building it later means rewriting frontmatter for entries in production.

6. **Monotone-decreasing baselines** (§2.4) as enforcement mechanism for any discipline added. Apply after Path A R3 (voice) and R2 (Red Flags in skills) land — there has to be discipline to baseline.

7. **Per-artifact sync contracts** (§2.3, Rule-of-Three Candidate 3) in SKILL.md skeleton (Path A R4) and `agent-behavior-defaults.md` (Sprint 1). Karpathy CURSOR.md:26-28 pattern.

### Below current threshold but worth tracking

8. **Self-critique loop / mid-emission self-check** (§2.9). Re-score after Path A R3 lands.

9. **"Is it ready?" doc as artifact class** (§2.8). Standalone task; one script over `knowledge_dashboard.py` output.

10. **Operational checklist artifact class** (§2.12). Triggers when Path A's skills investment reaches first-skill-merged-into-template milestone.

11. **Install-profile primitive** (§2.11). Triggers when derived projects start showing repeated "excludes X" pinned-traits entries.

12. **ECC inversion-test as screening lens** (§2.10). Strategic-posture frame, not adoption candidate. Useful in v5's adoption deliberation as a screening question for any ECC-derived adoption.

---

## §7 — What This Synthesis Does Not Do

Per v4 living-document hygiene rule, the scope boundaries this document honors:

- **Does not re-deliberate v4 working positions.** Where a comparison surfaced evidence against a v4 position (Pattern 3 sequenced review), the evidence is captured for v4 Sprint 2 re-evaluation, not as a now-decision.
- **Does not promote any pattern past human gate.** All items above are observations and candidates. Principle #7 is preserved.
- **Does not enact anything.** No ADRs are created. No `.claude/rules/`, `.claude/agents/`, `.claude/commands/`, or `CLAUDE.md` edits. The 0.65 synthesis confidence is below the threshold for binding action.
- **Does not override the 0.75 v4 confidence ceiling.** This synthesis is at 0.65 — explicitly lower. v5 deliberation supersedes this document if it produces different working positions.
- **Does not address Tier 0.** Tier 0 plumbing fixes (slug normalization, NULL command_type backfill, CAPTURE_PIPELINE_ERROR events, missing retro-action-registry.md, first template /retro) remain prerequisites for any Sprint 1 enactment. This synthesis assumes Tier 0 sequencing.

---

## §8 — Cross-Reference

- **v4 SYNTHESIS**: `docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md` (authoritative cross-project working positions)
- **Per-project ANALYSIS**: `docs/analysis/ANALYSIS-20260515-{superpowers,everything-claude-code,ruflo,open-design,obsidian-cli-skill,andrej-karpathy-skills}.md` (project-analyst rubrics)
- **Per-project comparisons (this synthesis's source)**: `docs/research/comparison-{01..06}-*.md`
- **Sealed deliberation transcript**: `discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md`
- **Living research state**: `C:\Users\evans\.claude\projects\C--Work-AI-research-projects\memory\project_research_state.md`

---

## §9 — Living-Document Hygiene

When updating this document, preserve:
- The frontmatter's `date` and `synthesis_confidence` fields (update on revision; do not delete history)
- Cross-source citations (do not collapse multiple sources into a single citation — independence is evidence)
- The 0.65 confidence ceiling unless v5 deliberation supersedes it

When adding new research:
- Append new sections; do not overwrite working positions
- If a working position is invalidated by new evidence, mark it `~~struck~~` with supersession evidence cited inline — do not delete (preserve decision history per v4 living-document rule)
- New comparisons (if a 7th project enters research scope) should append cross-cut observations here before v5 deliberation, not after
