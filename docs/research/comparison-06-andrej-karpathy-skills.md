---
title: "Andrej Karpathy Skills Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "6 of 6"
target_repo: multica-ai/andrej-karpathy-skills
target_path: C:/Work/AI/research_projects/andrej-karpathy-skills
target_version: v1.0.0 (28 commits, last 2026-04-20; 130,985 stars)
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "v4 already extracts heavily from this repo (Principles 1–3 → agent-behavior-defaults.md Sprint 1 at 0.85; Principle 4 → autonomous_workflow.md merge Sprint 1 at 0.78). This document's value is structural-craft, not pattern discovery."
prior_research:
  - docs/analysis/ANALYSIS-20260515-andrej-karpathy-skills.md (project-analyst, 2026-05-15, confidence 0.88)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 12-agent deliberation, 0.75 synthesis confidence)
  - docs/research/comparison-01-superpowers.md (sibling template; this document matches its structure)
  - discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md (sealed)
principles_challenged: [1, 2, 8]
verdict_summary:
  v4_sprint1_confirmed: 2
  v4_sprint1_additive: 0
  path_a_staging: 1
  deliberated_and_deferred: 0
  below_threshold: 2
  structural_craft_contributions: 4
---

# Karpathy Skills vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

This is project **6 of 6** in the external-project research wave. Among the six sources, Karpathy Skills is the **highest-confidence per-project source in v4** — two distinct Sprint 1 commitments derive from it (Principles 1–3 at 0.85, Principle 4 at 0.78), more than any other repo besides Superpowers.

That fact reshapes this document. Where comparison-01-superpowers had room to surface pattern adoption candidates the v3 brief missed, **v4 has already extracted nearly everything Karpathy has to offer at the principle level**. The four principles are scored 21/25 in [ANALYSIS-20260515-andrej-karpathy-skills.md:77](../analysis/ANALYSIS-20260515-andrej-karpathy-skills.md) and lined up for Sprint 1 enactment.

The genuine additive value this document can provide is therefore concentrated in §5.4 — **structural-craft observations about HOW the principles are written, packaged, and distributed**, not WHAT they teach. The repo is unusual in the survey: it is the only one of six that is **pure documentation** (no application code, no scripts, no hooks). What can a 130k-star pure-documentation repo teach about artifact craft that v4's content-level extraction misses?

This document follows comparison-01's structure exactly. Where my findings duplicate v4, the pattern is tagged **CONFIRMED — v4 Sprint 1** with the confidence score. Where my findings genuinely add to v4, they are collected in **§5.4 Structural-Craft Contributions**. I do not re-litigate v4 positions.

---

## 1. Identity & What's Useful

**andrej-karpathy-skills** is a four-principle behavioral calibration document — 65 lines of [CLAUDE.md](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md) — packaged for three distribution channels: a Claude Code plugin ([`.claude-plugin/plugin.json`](../../../../research_projects/andrej-karpathy-skills/.claude-plugin/plugin.json)), a per-project CLAUDE.md include, and a Cursor project rule ([`.cursor/rules/karpathy-guidelines.mdc`](../../../../research_projects/andrej-karpathy-skills/.cursor/rules/karpathy-guidelines.mdc) with `alwaysApply: true`).

The repo is exceptionally small (7 files, ~800 lines total, no tests, no CI) and exceptionally adopted (130,985 stars, 13,320 forks, 28 commits, 8 contributors). The asymmetry is the lesson: **a behavioral calibration document can outperform an entire framework on adoption when it solves a sharp problem with disciplined compression**.

The four principles, verbatim:

1. **Think Before Coding** — surface assumptions, present multiple interpretations, stop when confused, push back when a simpler approach exists.
2. **Simplicity First** — minimum code, no speculation, "if 200 lines could be 50, rewrite it."
3. **Surgical Changes** — match existing style, mention (don't delete) pre-existing dead code, every changed line traces to the user's request.
4. **Goal-Driven Execution** — transform imperative requests into verifiable goals with per-step verification checkpoints.

**Top 5 things worth studying** (most are already v4-extracted; the freshness here is the framing):

1. **Compression discipline.** 65 lines does what most frameworks attempt in a multi-skill methodology. The principles are LLM-aware (named failure modes), not generic engineering wisdom.
2. **Multi-harness distribution from a single source.** [CURSOR.md:26–28](../../../../research_projects/andrej-karpathy-skills/CURSOR.md) names the sync contract: when the four principles change, contributors update three files (CLAUDE.md + the .mdc rule + SKILL.md). A lightweight consistency protocol for a multi-target document.
3. **Self-test sentences embedded in each principle.** "Would a senior engineer say this is overcomplicated?" / "Every changed line should trace directly to the user's request." Compact, memorable, model-actionable.
4. **Closing efficacy claim, not closing rule.** [CLAUDE.md:65](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md): *"These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes."* The document ends by naming what success looks like, not by adding more rules.
5. **Trade-off disclosure at the top.** [CLAUDE.md:5](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md): *"These guidelines bias toward caution over speed. For trivial tasks, use judgment."* The document admits its own opinionation in line 5. This is unusually disciplined for a behavioral constraint document.

**Cultural signal worth noting.** The repo's voice is observational and clinical, not imperative. It does not say *"YOU MUST"* the way Superpowers does. It names a failure mode, names the corrected behavior, and trusts the model to apply the correction. The opinionation lives in *what is named*, not in *how loudly it is named*.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Karpathy Skills | Agent Framework Template |
|---|---|---|
| Behavioral constraints on coding | Four principles in one file | Distributed across `coding_standards.md`, `micro_fix_protocol.md`, agent definitions |
| Scope-limiting on edits | Principle 3 (Surgical Changes) | `micro_fix_protocol.md` (broader sizing) |
| Test-first discipline | Principle 4 examples | `testing_requirements.md` + qa-specialist |
| Pre-implementation reasoning | Principle 1 (surface assumptions) | `/plan` command (manual invocation) |
| Multi-harness deployment | CLAUDE.md + .mdc + SKILL.md sync contract | Single-harness (Claude Code) |

### Theirs-only (you don't have this)

- **Compression to one document.** 65 lines, four named principles, zero ceremony.
- **Multi-target distribution architecture** with explicit human-maintained sync contract (CURSOR.md:26–28). Not applicable to your internal deployment but the *pattern* of naming a sync contract is worth noting.
- **Embedded self-test sentences** per principle ("Would a senior engineer say this is overcomplicated?").
- **Closing efficacy clause** that names what success looks like rather than adding more rules.
- **Top-of-document trade-off disclosure** ("bias toward caution over speed").
- **Examples library with diff syntax** ([EXAMPLES.md:231–290](../../../../research_projects/andrej-karpathy-skills/EXAMPLES.md)) showing appropriate edit scope vs. drive-by refactoring as actual git-diff hunks.
- **`alwaysApply: true` Cursor frontmatter pattern** — declarative auto-application as a metadata field, not a hook.
- **Single SKILL.md description used as semantic activation hint** — the description names *when* to use ("Use when writing, reviewing, or refactoring code…"), aligning with the Superpowers CSO discovery and v4's Conflict 2 resolution.

### Yours-only (they don't have this)

Everything you'd expect from a full framework versus a 65-line behavioral document. The point of this row is not enumeration; it is to note that **the comparison is asymmetric by design**. Karpathy Skills is not trying to be a framework. It is a behavioral patch installed *into* a framework. Your framework is the host environment Karpathy Skills would land in.

What this means structurally: your framework provides infrastructure (capture stack, ADRs, lineage, agents, hooks, commands). Karpathy Skills provides four behavioral nudges. These are not competing artifacts — they are different layers of the same stack. The interesting question isn't "what do they have that you don't" but **"how should your framework host Karpathy's four principles?"** (Already answered by v4 at the rule level. §5.4 examines the artifact-shape question.)

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Your `micro_fix_protocol.md` is sharper than Karpathy's Principle 3 on sizing.** Karpathy's Principle 3 says *touch only what you must*; your micro-fix protocol defines what counts as a micro-fix with a behavior-test heuristic ("Will changing this one thing change behavior?") and a Two-Strike Escalation Rule. Karpathy gives you a posture; you have an operational test. Holds up.

2. **Your eight-principle constitution does the work Karpathy's four-principle document tries to do, plus more.** Karpathy is a coding-behavior document. Your CLAUDE.md principles operate at the framework-evolution level (Principle #8: least-complex intervention), the capture level (Principle #2: capture must be automatic), the institutional-memory level (Principle #5: ADRs are never deleted). Different scope; your scope is bigger. Holds up.

3. **Your specialist values blocks already encode Karpathy's instincts as agent-level beliefs.** The qa-specialist's testing-requirements posture, the architecture-consultant's structural-integrity posture, the security-specialist's threat-modeling posture — these are domain-scoped versions of Karpathy's "surface assumptions" / "match existing style" / "minimum code." You operationalize behavior shaping through *agent personas* the way Karpathy operationalizes it through *behavioral constraints*. Both work; your approach has more headroom for domain specialization.

4. **Your reasoning-capture infrastructure is what makes Karpathy's principles measurable in your environment.** Karpathy's closing line — *"these guidelines are working if: fewer unnecessary changes in diffs"* — is unmeasurable in his deployment context. In yours, with `quality_gate_log.jsonl`, `findings`, `protocol_yield`, you can actually measure the diff-cleanliness signal. Adopting Karpathy's principles into your framework is value-additive in a way it cannot be in his.

5. **Your Principle #8 (least-complex intervention) is philosophically aligned but mechanically broader.** Karpathy's Simplicity First targets code generation. Your Principle #8 targets framework evolution — "prefer prompt changes before command/tool changes before agent definition changes." Same instinct, different layer. The fact that you have *both* layers (framework-evolution Principle #8 in CLAUDE.md, and now code-generation Simplicity First via the v4 Sprint 1 rule) is structurally complete in a way Karpathy alone is not.

---

## 4. Weaknesses This Comparison Exposes

The weaknesses surfaced here are mostly structural-craft observations rather than missing patterns, because v4 has already absorbed the missing patterns.

### 4.1 No top-of-document trade-off disclosure on your behavioral rules

[CLAUDE.md:5](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md) — *"These guidelines bias toward caution over speed. For trivial tasks, use judgment."* Karpathy admits the opinionation in line 5. None of your 14 rules in `.claude/rules/` open with a trade-off disclosure. They open with a one-line "what this rule prevents" header (e.g., `autonomous_workflow.md:3`: *"Prevents protocol skipping under autonomous execution authorization"*) — useful, but oriented at the *intent* of the rule, not the *trade-off* the rule imposes.

For a methodology-publishing framework with future-team adopters, naming the trade-off is more honest than naming only the intent. Adopters need to understand what the rule *costs* them, not only what it *prevents*.

**Maps to**: §5.4 Contribution 1 — structural-craft.

### 4.2 No closing efficacy clause on your rules

[CLAUDE.md:65](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md) names what success looks like at the end of the document: *"fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation rather than after mistakes."*

Your rules don't close this way. They close with a "Relationship to Other Rules" section listing siblings, which is useful for orientation but not for verification. The adopter cannot tell, when reading your rule, what observable change they should look for to know the rule is working.

The asymmetry is sharpest at `autonomous_workflow.md`, which prevents a specific named failure (the 7-workstream bypass incident in the rule header) but does not name how an adopter would *measure* whether the rule is preventing that failure. Your framework has the measurement infrastructure (`protocol_yield`, `findings`); the rules just don't reference it.

**Maps to**: §5.4 Contribution 2 — structural-craft.

### 4.3 No "self-test sentence" pattern embedded in your rules

Karpathy's principles each include a compact self-test the model can run against its own work in-context:

- Principle 2: *"Would a senior engineer say this is overcomplicated?"*
- Principle 3: *"Every changed line should trace directly to the user's request."*

Your rules have prescriptive content but not self-tests. `coding_standards.md` says "Maximum function length: ~50 lines (guideline, not hard rule — prefer smaller)" — a constraint, not a self-test. The difference is that a self-test sentence can be applied to *any* of the model's work products in-place; a constraint requires the model to recall and check against a remembered list.

For auto-loaded artifacts, self-test sentences are more behaviorally load-bearing than constraint enumerations. The model running on a freshly-generated code block can ask itself *"would a senior engineer say this is overcomplicated?"* faster than it can recall and check against a 12-item list.

**Maps to**: §5.4 Contribution 3 — structural-craft.

### 4.4 No precedent for multi-harness packaging from a single source

Karpathy maintains three artifacts (CLAUDE.md, .cursor/rules/*.mdc, skills/*/SKILL.md) from one content source with a named sync contract ([CURSOR.md:26–28](../../../../research_projects/andrej-karpathy-skills/CURSOR.md)). Your framework is deliberately for-Claude-Code-only; the multi-harness question is out of scope at the deployment level.

**But the underlying pattern — a single content source that produces multiple targets via an explicit sync contract — does apply within your framework.** Your CLAUDE.md duplicates principles already in FRAMEWORK.md; your rules in `.claude/rules/` reference cross-rules without a single source-of-truth. The Karpathy three-target sync contract is a model for *internal* artifact synchronization, not just multi-harness.

This is genuinely fresh — v4 doesn't surface internal sync-contract gaps because the v4 work is at the *content* level, not the *artifact-organization* level.

**Maps to**: §5.4 Contribution 4 — structural-craft.

### 4.5 EXAMPLES.md format is below your adoption threshold but the format itself is informative

[EXAMPLES.md](../../../../research_projects/andrej-karpathy-skills/EXAMPLES.md) scored 16/25 in the project-analyst's per-project rubric and is correctly below the 20/25 adoption threshold. But its *format* is worth noting: real diff syntax (lines 231–290), labeled problems, side-by-side good/bad. This is calibration-anchor content, not constraint content.

Your skills currently lack calibration anchors. `testing-playbook/SKILL.md` (101 lines) shows pytest patterns; it does not show what bad pytest patterns look like or how to recognize when you're sliding toward them. Karpathy's EXAMPLES.md compensates for compressed principle text with concrete anchors. Your skills compress without anchoring.

This intersects Path A R4 (adopt Superpowers' SKILL.md skeleton with When-to-Use / Process / Red Flags / Examples / Final Rule). The Karpathy *format* — labeled-problem diffs as the Examples section — is a reference for what the Examples section should contain when Path A R4 lands.

**Maps to**: §5.4 — structural-craft contribution feeds Path A R4.

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How Karpathy's four-principle document stands against your 8 Non-Negotiable Principles:

| # | Principle | Karpathy stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **Disagrees by omission** — behavioral constraints are their primary artifact, no reasoning-capture concept | **Yes — fundamental, same as Superpowers** | Your bet on reasoning capture is reaffirmed. Karpathy doesn't even attempt it; their 130k stars come from solving a different problem (in-session behavior shaping) than yours (institutional memory). Both can be true. |
| 2 | Capture must be automatic | **No equivalent concept** | Compatible-by-omission | They don't capture anything; the principle doesn't apply to their scope. |
| 3 | Collaboration precedes adversarial rigor | **Loosely agrees** — Principle 1's "push back when warranted" is a mild adversarial element inside a collaborative posture | Compatible | No tension. |
| 4 | Independence prevents confirmation loops | **No equivalent** — single-agent context | Neutral | They don't have multi-agent; the principle doesn't apply. |
| 5 | ADRs are never deleted | **No equivalent** | Neutral | Same — out of scope. |
| 6 | Education gates before merge | **No equivalent**, but Principle 1's "surface assumptions" is upstream of education-gate intent (the model surfaces its understanding before action) | Compatible-orthogonal | Different scope. Karpathy operates on the model's pre-implementation reasoning; your education gates operate on the human reviewer's post-implementation understanding. |
| 7 | Layer 3 promotion requires human approval | **No equivalent** | Neutral | Out of scope. |
| 8 | Least-complex intervention first | **Strongly agrees at the code-generation level** — Principle 2 (Simplicity First) is your Principle #8 applied to code generation rather than framework evolution | **Mild — different layer** | Karpathy gives you a code-generation analogue to your framework-evolution principle. v4 Sprint 1 absorbs this via `agent-behavior-defaults.md`. Holds. |

**Three principles are challenged: #1, #2, #8.** #1 and #2 are challenged only by omission (Karpathy is out-of-scope for reasoning-capture; the omission doesn't invalidate your bet). #8 is *complemented*, not challenged — Karpathy's Simplicity First operates at the code-generation layer your Principle #8 doesn't reach. v4 closes the gap via Sprint 1 (`agent-behavior-defaults.md` at 0.85 confidence).

### 5.2 Adoption Candidates — v4-Aligned

Patterns scored on the 5-dimension rubric (prevalence / elegance / evidence / fit / maintenance, out of 25). Most patterns here are already v4 Sprint 1 commitments; I tag and do not re-litigate.

#### Pattern 1: Karpathy Principles 1–3 as `.claude/rules/agent-behavior-defaults.md`

**Score: 21/25** — **CONFIRMED — v4 Sprint 1 at 0.85 confidence**

Already scored by [ANALYSIS-20260515-andrej-karpathy-skills.md:68–77](../analysis/ANALYSIS-20260515-andrej-karpathy-skills.md). Already committed in v4 Sprint 1 at 0.85. I do not re-score. The four-dimension score from the analysis is authoritative.

**Status note**: This is v4's flagship Karpathy commitment. My only addition is the structural-craft observation in §5.4 that the *voice and shape* of the rule matters as much as the content — when this rule lands, it should preserve Karpathy's compression discipline (each principle in roughly 5–10 lines with one self-test sentence), not balloon to match the prose density of your other rules.

**Action**: Sprint 1 per v4. Recommended structural fidelity: keep each principle 5–10 lines, embed the self-test sentence, open with trade-off disclosure ("biases toward caution over speed"), close with efficacy clause.

#### Pattern 2: Karpathy Principle 4 (Goal-Driven Execution) merge into `autonomous_workflow.md`

**Score: 21/25** — **CONFIRMED — v4 Sprint 1 at 0.78 confidence**

Already in v4 Sprint 1. The project-analyst flagged this as under-weighted in v3; v4 elevated to Sprint 1. I do not re-litigate.

**Structural-craft note**: Karpathy's Goal-Driven Execution is articulated as a *transformation pattern* ("imperative → verifiable") rather than as a constraint. Look at the table at [CLAUDE.md:50](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md):

| Instead of... | Transform to... |
|---|---|
| "Add validation" | "Write tests for invalid inputs, then make them pass" |
| "Fix the bug" | "Write a test that reproduces it, then make it pass" |
| "Refactor X" | "Ensure tests pass before and after" |

When this merges into `autonomous_workflow.md`, preserve the transformation-table format. Your `autonomous_workflow.md` currently uses a workflow-sequence format ("1. /plan, 2. /build_module, 3. Quality gate"). The Karpathy transformation-table is a different structural primitive — it teaches *how to think about the task* rather than *what to do next*. Both are valuable; they should coexist as distinct sections.

**Action**: Sprint 1 per v4. Recommended structural fidelity: preserve the transformation-table format; don't reshape Goal-Driven Execution into a procedural workflow.

#### Pattern 3: Multi-target sync contract for related artifacts

**Score: 19/25** — **Path A staging — structural-craft contribution**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | Uncommon to name a sync contract explicitly in repo docs |
| Elegance | 4 | Two-line contract in CURSOR.md:26–28 is compact and complete |
| Evidence | 4 | Karpathy's repo is the proof-of-concept; works across 28 commits, 8 contributors |
| Fit | 4 | Applies internally to your framework even though you're single-harness |
| Maintenance | 4 | Sync contracts are documentation; low ongoing cost if respected |

**Status note**: Below the 20/25 threshold, but barely, and the *pattern* (name the sync contract explicitly) is a fresh structural observation that v4 doesn't have. Lands in §5.4 as a contribution rather than as a Sprint 1 adoption.

**Action**: When Path A's `using-the-framework/SKILL.md` ships, include a "Sync contract" section naming which related artifacts (CLAUDE.md sections, FRAMEWORK.md sections, related rules) must update together when the SKILL.md changes. This is structural-craft, not v4 territory.

#### Pattern 4: EXAMPLES.md / before-and-after diff-syntax format

**Score: 16/25** — **Below threshold; the format informs Path A R4 only**

Per the project-analyst's per-project rubric. Content import is not recommended. The diff-syntax format is a useful reference when Path A R4 (SKILL.md skeleton with Examples section) lands. No separate adoption.

#### Pattern 5: Multi-harness distribution architecture (CLAUDE.md + .mdc + plugin)

**Score: 11/25** — **Below threshold; not applicable**

Per the project-analyst's per-project rubric. Your framework is deliberately for-Claude-Code-only. The deployment-level multi-harness pattern doesn't apply. (The *internal* sync-contract pattern that this scheme implies is captured separately as Pattern 3.)

### 5.3 Verdict Tally — v4-Aware

- **CONFIRMED — v4 Sprint 1** (2):
  - Pattern 1 (Karpathy Principles 1–3 as `agent-behavior-defaults.md`) — 0.85 confidence
  - Pattern 2 (Karpathy Principle 4 merged into `autonomous_workflow.md`) — 0.78 confidence
- **Path A staging — structural-craft contribution** (1):
  - Pattern 3 (multi-target sync contract pattern, internal use)
- **Below threshold** (2):
  - Pattern 4 (EXAMPLES.md format — informs Path A R4 only)
  - Pattern 5 (multi-harness distribution — not applicable)
- **Structural-craft contributions** (4): see §5.4

**>50% NEW criterion**: Patterns 1 and 2 are already-in-v4 (CONFIRMED). Patterns 3, 4, 5 plus the four §5.4 contributions are NEW relative to v4 — 7 of 9 scored or named items, 78%. The threshold is met.

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

Given v4's heavy principle-level extraction from this repo, structural-craft is where this document's unique value-add concentrates. These observations concern *how* the principles are written, packaged, and distributed — not *what* they teach.

#### Contribution 1: Trade-off disclosure at top of rule

**Pattern**: Open the rule with a one-line statement of what the rule *costs*, not only what it *prevents*.

Karpathy: *"These guidelines bias toward caution over speed. For trivial tasks, use judgment."* ([CLAUDE.md:5](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md))

Your rules currently open with "what this prevents" headers (e.g., `autonomous_workflow.md:3`). The intent-frame is useful but incomplete. Adopters of a methodology-publishing framework need to know the trade-off they're accepting, not only the failure they're avoiding.

**Status**: Structural-craft adoption guidance for `agent-behavior-defaults.md` when it lands in Sprint 1. Also a candidate retroactive addition to your existing 14 rules — a Path A R2/R3 sibling task.

#### Contribution 2: Closing efficacy clause

**Pattern**: End the rule with the observable signal that indicates the rule is working.

Karpathy: *"These guidelines are working if: fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes."* ([CLAUDE.md:65](../../../../research_projects/andrej-karpathy-skills/CLAUDE.md))

Your rules close with "Relationship to Other Rules" sections — orientation, not verification. The closing efficacy clause names what to look for to know the rule is doing its job. For a framework with measurement infrastructure (`quality_gate_log.jsonl`, `protocol_yield`), the closing efficacy clause is also a hook into your telemetry — it tells the rule reader *where* to look for the signal.

**Status**: Structural-craft adoption guidance for `agent-behavior-defaults.md` and `verification_before_completion.md` (both v4 Sprint 1). Wire each clause to a measurable signal from your existing instrumentation (e.g., for `verification_before_completion.md`: "this rule is working if `findings` records the absence of pre-verification completion claims").

#### Contribution 3: Self-test sentences as the primary behavioral primitive

**Pattern**: Embed a single compact self-test sentence per principle that the model can run against its own work in-place, without recall-and-check against a list.

Karpathy:
- Principle 2: *"Would a senior engineer say this is overcomplicated?"*
- Principle 3: *"Every changed line should trace directly to the user's request."*

Your rules use *constraints* (numbered lists, bullet enumerations). Constraints require recall-and-check; self-tests apply in-place. The behavioral load of a self-test sentence is higher than the behavioral load of an equivalent list, even though the list is more comprehensive — because in-context model behavior favors short applicable tests over long recalled lists.

**Status**: When `agent-behavior-defaults.md` lands in Sprint 1, preserve Karpathy's self-test sentences verbatim. When Path A's R2 propagates Red Flags tables to skills, consider adding a *self-test sentence* row alongside the Red Flags table — they are complementary primitives (Red Flags catch rationalizations; self-tests catch overreach).

#### Contribution 4: Internal sync-contract pattern (artifact lineage at the doc level)

**Pattern**: Name explicitly which sibling artifacts must update together when this artifact changes.

Karpathy ([CURSOR.md:26–28](../../../../research_projects/andrej-karpathy-skills/CURSOR.md)): *"When you change the four principles, keep CLAUDE.md and .cursor/rules/karpathy-guidelines.mdc in sync. If the published skill/plugin text should match, update skills/karpathy-guidelines/SKILL.md as well."*

Your framework has implicit artifact lineage: `framework_doc_sync.md` exists in `.claude/rules/` and handles some of this, and the framework-lineage.yaml manifest tracks project-to-template drift. But at the *individual rule* level, sync contracts are not named in the rule itself. Adopters reading `autonomous_workflow.md` cannot tell, from the rule, which sibling artifacts they must update when modifying it.

This is the most genuinely new observation in this document. v4 doesn't address artifact-organization sync at the per-rule level; the v4 work is at the *content* level. Karpathy's CURSOR.md:26–28 is a model for explicit per-artifact sync contracts that complement your framework-wide `framework_doc_sync.md`.

**Status**: Path A staging. When the SKILL.md skeleton lands (Path A R4), include an optional "Sync contract" section. When `agent-behavior-defaults.md` ships in Sprint 1, name its sync siblings (CLAUDE.md Principle #8 framework-evolution language; FRAMEWORK.md Principles section; relevant agent definitions). This is a documentation-organization improvement, not a content change.

### 5.5 Meta-Questions for Framework Evolution

1. **Does the asymmetry between your scope (full framework) and Karpathy's scope (65-line behavioral patch) suggest a packaging gap?** Karpathy is one artifact that produces measurable behavioral change. Your framework is a methodology that *contains* equivalent behavioral artifacts but doesn't package any of them for narrow drop-in adoption. For future-team adopters who can't take on the whole framework, a "behavioral-defaults-only" extract — Karpathy-shaped, 50–100 lines, derived from `agent-behavior-defaults.md` once it lands — might be a high-leverage publication artifact. Out of scope for this comparison; flagged for future consideration.

2. **Does Karpathy's compression discipline (65 lines, four named failure modes) point at over-decomposition in your current rules?** Your 14 rules in `.claude/rules/` total roughly 600+ lines. Several rules cover related territory (`commit_protocol.md`, `review_gates.md`, `autonomous_workflow.md`, `micro_fix_protocol.md`). The Karpathy data point — that a 65-line document gets 130k stars for solving a sharp problem — is not evidence your rules are over-decomposed, but it is evidence that *compression has adoption value*. Worth a future audit pass: which of your 14 rules could merge into a "behavioral defaults" bundle without losing meaning?

3. **Is the trade-off-disclosure / closing-efficacy-clause pair a candidate framework-wide convention?** If §5.4 Contributions 1 and 2 are valuable on `agent-behavior-defaults.md`, they may be valuable on all 14 rules. This would be a documentation hygiene project, not a content change — but it would substantially shift the *voice* of your rules from "what this prevents" to "what this trades off and how you'd know it's working." A Path A R3 sibling task at minimum; a candidate framework-wide convention at maximum.

4. **Karpathy's `alwaysApply: true` Cursor frontmatter is an interesting design point.** A declarative metadata field tells Cursor to always inject the rule. Your `.claude/rules/` rely on Claude Code's automatic context loading — the equivalent of `alwaysApply: true` at the platform level. But the *idea* of a declarative metadata field that controls activation behavior is worth noting as Path A R1 (`using-the-framework/SKILL.md`) thinks through skill priority ordering and triggering conditions.

---

## 6. Open Tasks Surfaced by This Document

Captured for forward visibility, not for immediate action:

| Task | Owner | Sequencing |
|---|---|---|
| Sprint 1: `agent-behavior-defaults.md` per v4, preserving Karpathy's compression and self-test sentences | framework developer | Post-Tier-0 |
| Sprint 1: Karpathy Principle 4 merge into `autonomous_workflow.md`, preserving transformation-table format | framework developer | Post-Tier-0 |
| Sprint 1 sibling: add trade-off disclosure + closing efficacy clause to `agent-behavior-defaults.md` and `verification_before_completion.md` | framework developer | Sprint 1, same change set |
| Path A R4 sibling: when SKILL.md skeleton lands, optional "Sync contract" section per Contribution 4 | framework developer | Path A |
| Future audit: which of 14 rules could merge into a "behavioral defaults" bundle (compression-discipline question, Meta-Question 2) | framework developer | Standalone; whenever audited |
| Future consideration: extract a narrow "behavioral-defaults-only" publication for future-team adopters (methodology-publishing leverage) | framework developer | Post-Path-A stabilization |

---

## Appendix: What I Didn't Examine

For honesty about scope:

- The Multica platform link at the top of [README.md:3](../../../../research_projects/andrej-karpathy-skills/README.md) (the author's parent project). Out of scope.
- The original Karpathy X/Twitter post itself (cited at README.md:7) — I worked from the README's quoted excerpts.
- Community PRs and issue conversations on the upstream `forrestchang/andrej-karpathy-skills` repo. Out of scope.
- The 130k-star adoption signal as social-network artifact — interesting but unfalsifiable from inside the repo.
- Comparison with sibling Cursor rule files in the broader Cursor ecosystem.

If a future pass needs more granularity on any of these, the artifacts are at `C:/Work/AI/research_projects/andrej-karpathy-skills/`.
