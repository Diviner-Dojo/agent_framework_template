---
title: "Superpowers Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "1 of 6"
target_repo: obra/superpowers
target_path: C:/Work/AI/research_projects/superpowers
target_version: v5.1.0
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "revised post-SYNTHESIS-20260515-adoption-brief-v4 reading; pattern tags reflect v4 working positions"
prior_research:
  - docs/analysis/ANALYSIS-20260515-superpowers.md (project-analyst, 2026-05-15, confidence 0.92)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 12-agent deliberation, 0.75 synthesis confidence)
  - discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md (sealed)
principles_challenged: [1, 2, 6, 8]
verdict_summary:
  v4_sprint1_confirmed: 2
  v4_sprint1_additive: 1
  path_a_staging: 2
  deliberated_and_deferred: 1
  below_threshold: 2
  structural_craft_contributions: 4
---

# Superpowers vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

**Original version (2026-05-16, morning)**: Written without knowledge of the project's prior research stack.

**This version (2026-05-16, afternoon)**: Revised after reading [`docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md`](../analysis/SYNTHESIS-20260515-adoption-brief-v4.md) and [`docs/analysis/ANALYSIS-20260515-superpowers.md`](../analysis/ANALYSIS-20260515-superpowers.md). v4 is the authoritative cross-project synthesis containing scored patterns and deliberated working positions; ANALYSIS-superpowers is the per-project rubric scoring from the project-analyst agent. This document's contribution is reframed accordingly:

- **Where my findings duplicate v4**: pattern is marked **CONFIRMED — v4 Sprint 1** with the v4 confidence score.
- **Where my findings contradict v4's deliberated position**: pattern is marked **DELIBERATED AND DEFERRED** and the recommendation is withdrawn. The 12-agent deliberation produced the working position; this document does not override it.
- **Where my findings were missed in the original pass**: three patterns from ANALYSIS-superpowers are added with explicit acknowledgment of the gap.
- **Where my findings genuinely add to v4**: collected in a new **Structural-Craft Contributions** section (§5.4). These are the unique value of the outside-eyes pass.

This document is a structural-craft complement, not a primary adoption recommendation. The adoption decisions live in v4 and the adoption-log; this document feeds them.

---

## 1. Identity & What's Useful

**Superpowers** is a plugin-shipped skill library that ships a fixed software-development methodology across eight coding harnesses (Claude Code, Codex CLI, Codex App, Factory Droid, Gemini CLI, OpenCode, Cursor, GitHub Copilot CLI). The methodology is encoded as 14 skill files under four categories:

- **Testing**: `test-driven-development` (with `testing-anti-patterns` reference)
- **Debugging**: `systematic-debugging`, `verification-before-completion`
- **Collaboration**: `brainstorming`, `writing-plans`, `executing-plans`, `dispatching-parallel-agents`, `requesting-code-review`, `receiving-code-review`, `using-git-worktrees`, `finishing-a-development-branch`, `subagent-driven-development`
- **Meta**: `writing-skills`, `using-superpowers`

The methodology runs a fixed workflow: **brainstorming → using-git-worktrees → writing-plans → subagent-driven-development → test-driven-development → requesting-code-review → finishing-a-development-branch**. Skills auto-trigger via a `SessionStart` hook ([superpowers/hooks/hooks.json](../../../../research_projects/superpowers/hooks/hooks.json)) that mounts a `using-superpowers` bootstrap. That bootstrap is a manifesto declaring: *"If you think there is even a 1% chance a skill might apply to what you are doing, you ABSOLUTELY MUST invoke the skill."* The bootstrap is the leverage — without it, the skills are inert files on disk.

**Top 5 things worth studying:**

1. **Auto-trigger mechanism** — `SessionStart` hook + `using-superpowers` bootstrap. ([skills/using-superpowers/SKILL.md](../../../../research_projects/superpowers/skills/using-superpowers/SKILL.md))
2. **Red Flags tables** inside every skill — explicit enumeration of the rationalizations agents reach for, paired with the reality. See [skills/test-driven-development/SKILL.md:80–94](../../../../research_projects/superpowers/skills/test-driven-development/SKILL.md) for the canonical example.
3. **Subagent-driven development with two-stage review** — fresh subagent per task, *spec compliance* reviewer dispatched separately from *code quality* reviewer, each with its own prompt template file. ([skills/subagent-driven-development/](../../../../research_projects/superpowers/skills/subagent-driven-development/))
4. **Plan as junior-engineer instructions** — "bite-sized tasks (2–5 minutes each), every task has exact file paths, complete code, verification steps." ([README.md:160](../../../../research_projects/superpowers/README.md))
5. **Writing skills IS TDD applied to documentation** — pressure-scenario subagent tests, watch the rule fail without the skill, write the skill, watch the rule pass. ([skills/writing-skills/SKILL.md](../../../../research_projects/superpowers/skills/writing-skills/SKILL.md))

**Cultural signal worth noting.** Their [CLAUDE.md](../../../../research_projects/superpowers/CLAUDE.md) is an anti-slop manifesto: 94% PR rejection rate, refusal of domain-specific skills, refusal of third-party dependencies, refusal of "compliance" rewrites to Anthropic's published skill guidance. Their terminology ("your human partner" — never "the user") is deliberately load-bearing. The opinionation is the product as much as the skills are.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Superpowers | Agent Framework Template |
|---|---|---|
| Plan before build | `writing-plans` skill (auto-trigger after brainstorming) | `/plan` command (manual invocation) |
| Multi-stage code review | Spec-compliance reviewer → code-quality reviewer (sequenced, separate subagents) | `/review` with facilitator + 2+ specialists (parallel) |
| Test-first discipline | `test-driven-development` skill (iron law, Red Flags table) | `testing_requirements.md` rule + `qa-specialist` agent (review-after) |
| Isolated workspace | `using-git-worktrees` skill | Implicit (branch hygiene, no worktree command) |
| Subagent dispatch | Per-task fresh implementer + 2 reviewers | Per-review specialist panel (12 agents) |
| Brainstorm / spec | `brainstorming` skill (Socratic, auto-triggered) | `/deliberate` command (Structured Dialogue / Dialectic) |
| Process skills | 14 auto-triggered skills | 6 reference skills + 14 rules + 17 commands |
| Bootstrap on session | `SessionStart` hook → manifesto skill | `SessionStart` hook → `BUILD_STATUS.md` + 6-point dashboard |

### Theirs-only (you don't have this)

- **Manifesto-style auto-trigger** with anti-rationalization framing (`1% chance → MUST use`).
- **Red Flags / rationalization tables** embedded in every skill.
- **Two-stage sequenced review** (spec, then quality, distinct subagents with separate prompt files) — a sharper independence pattern than your parallel-specialist dispatch.
- **`<SUBAGENT-STOP>` gate** — prevents the bootstrap skill from being processed by dispatched subagents. Architecturally clever subagent context hygiene your analyst flagged as a blind-spot in your framework (subagents currently receive the full system prompt including all auto-loaded rules).
- **Implementer Status Protocol** — four-state (DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT) with defined handling paths for each. Your checkpoint protocol has only APPROVE/REVISE; no "completed with doubts" state.
- **Verification-Before-Completion gate** — before any completion claim, run the verification command in the current message and cite its output. Inserts the gate at every mid-task completion assertion, not just at commit time.
- **Continuous-execution doctrine** baked into subagent-driven-development: *"Do not pause to check in with your human partner between tasks. Execute all tasks from the plan without stopping."*
- **Atomic-task planning** — plans break into 2–5 minute units with complete code in the plan itself.
- **Cross-harness portability** — same skill files run on 8 harnesses.
- **Skill testing methodology** — pressure scenarios with subagents to verify a skill actually changes behavior.
- **CSO (description as triggering conditions only)** — empirically discovered that workflow-summary descriptions cause Claude to shortcut past the skill. Descriptions must name triggers, not workflows.

### Yours-only (they don't have this)

- **Four-layer capture stack** — `events.jsonl` → SQLite → curated memory → optional vector. Superpowers has zero reasoning-capture infrastructure.
- **ADRs as immutable decision history.**
- **Education gates** (walkthrough → quiz → explain-back → merge). No equivalent in Superpowers. **Note**: v4 substantially reframes this principle (Option C default with Option B carve-out for 4 security classes) — read v4 for current working position.
- **External project analysis** with adoption log + Rule of Three. Superpowers explicitly *refuses* outside skills (94% rejection rate).
- **Lineage tracking** (`framework-lineage.yaml`, Steward agent).
- **Sourced-assertion memory substrate** (assertion_store + MCP server).
- **12-specialist panel** with distinct Values blocks and Domain Lenses. Superpowers has one workflow voice.
- **Failure taxonomy** (8 named classes with recovery paths).
- **Quality gate** automation (formatting, linting, tests, coverage, ADR completeness, review existence, regression ledger).
- **Knowledge pipeline** — findings extraction, pattern mining, Rule of Three, agent effectiveness tracking.
- **Retro / meta-review loops** (nested micro/meso/macro). **Note**: v4 flags that the template repo itself hasn't executed `/retro` in 68 days — discipline inherited by derived projects but unvalidated upstream. Tier 0 includes running the template's first /retro.
- **Multi-instance and cross-agent dispatch protocols.**

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Reasoning capture is genuinely differentiated and high-leverage.** Superpowers does not even attempt it. If "reasoning is the primary artifact" (Principle #1) is your central bet, this comparison validates that bet — Superpowers' methodology is excellent in-session but produces no compounding institutional memory across sessions, projects, or time. Your `discussions/`, SQLite index, ADRs, and adoption log do something Superpowers can't.

2. **Education gates pattern is unique value (with v4 caveat).** Superpowers ships and trusts the human reviewer to be the gate. Your walkthrough/quiz/explain-back loop was a different leverage point — designed to ensure the human partner internalizes what was built, not just approves it. v4's reframing (Option C default with Option B carve-out for 4 security classes) preserves the intent (decision-maker can evaluate work six months hence) via a less-friction mechanism (Decision Rationale Capture) for the user's stated audience (non-coding manager). The pattern still differentiates you from Superpowers; the implementation has evolved.

3. **Multi-specialist values diversity produces genuine dissent.** Your specialists have load-bearing Values blocks (security cares about threats, qa cares about edge cases, ux cares about friction). Superpowers has *one* workflow voice across all 14 skills. The 12-agent deliberation captured at DISC-20260516-050945 (Steward vs. independent-perspective on enactment timing) is a real example of this value — the dissent is preserved, not smoothed over.

4. **External project analysis pipeline is a strategic posture, not a feature.** Superpowers is methodology-first and closed (94% rejection of outside skills). You are exploration-first and open. The fact that *this very document exists* — a structured comparison feeding adoption decisions through your panel — is something Superpowers' philosophy actively rules out.

5. **Failure taxonomy is professional infrastructure Superpowers lacks.** Eight named failure classes with recovery paths and retry limits is rare in this category. When something goes wrong, you have a map.

6. **Least-complex intervention (#8) is alive in your design at the substrate level.** Your hooks are PowerShell + Python, your rules are markdown, your skills are markdown. You haven't over-engineered the substrate. The substrate discipline holds. The *command surface* may not (see §5.4) — but that's a different question.

---

## 4. Weaknesses This Comparison Exposes

Ordered by severity for the framework's evolution. Note: §5 maps each of these to a v4 working position or a Path A staging step.

### 4.1 No auto-trigger mechanism — your skills and rules are passive

You have 14 rules, 6 framework skills, and 17 commands — all loaded into the agent's context but relying on the model to remember to consult them. Superpowers has a `SessionStart` hook + manifesto skill that explicitly binds the agent.

Your CLAUDE.md *describes* the rules; Superpowers' `using-superpowers` *binds the agent to them*. Your skills risk being dead weight if the model doesn't proactively consult them. This is a real practical asymmetry — Principle #2 ("Capture must be automatic — the model cannot opt out") is enforced at your *capture* layer but not at your *guidance-consumption* layer. Your guidance is opt-in by default.

**Maps to**: §5.2 Pattern 1 — Path A staging.

### 4.2 No anti-rationalization (Red Flags) tables in skills and rules

Your *agents* use the technique implicitly (in "Anti-Patterns to Avoid" sections). Your *skills* and *rules* do not. Superpowers' skills include explicit tables enumerating the rationalizations agents reach for:

| Excuse | Reality |
|---|---|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "TDD will slow me down" | TDD faster than debugging. Pragmatic = test-first. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Tests after achieve same goals" | Tests-after = 'what does this do?' Tests-first = 'what should this do?' |

The technique already lives in your agents; it just hasn't propagated.

**Maps to**: §5.2 Pattern 2 — v4 Sprint 1 confirmed.

### 4.3 Your TDD posture is softer than theirs

You have `testing_requirements.md` and a `qa-specialist`. Superpowers has TDD as **iron law**. Your qa-specialist *reviews* tests after the fact; their TDD skill *prevents* untested code from existing at all. Different leverage points — both valid, but the model will write tests-after if it can, and your posture currently permits that.

**Maps to**: §5.2 Pattern 2 (Red Flags tables, including for testing) — Path A staging propagates this.

### 4.4 Your review architecture is parallel; theirs is sequenced

Your `/review` and `build_review_protocol` dispatch multiple specialists in *parallel*. Superpowers dispatches a *spec-compliance* reviewer first, then — only after spec passes — a *code-quality* reviewer.

**Maps to**: §5.2 Pattern 3 — **DELIBERATED AND DEFERRED in v4**. The 12-agent panel chose PARALLEL preserved; two-stage re-evaluation gated to Sprint 2 once survival rate is measurable. My recommendation to sequence now does not override the deliberation.

### 4.5 Your plan granularity is coarser than theirs

Your `/plan` produces a spec. Theirs produces an atomic task list designed for a junior engineer to execute mechanically.

**Maps to**: §5.2 Pattern 4 — below v4 attention threshold; defer.

### 4.6 17 commands may be over-engineered orchestration surface

Superpowers has zero commands. Everything is auto-triggered skills. Your commands include some that may not earn their cognitive overhead (`/seed`, `/onboard`, `/promote`, `/spawn-project`, `/conversation`). Each command requires the developer to remember to invoke it. Principle #8 (least-complex intervention) suggests an audit.

**Maps to**: §5.4 — structural-craft contribution. v4 defers conversation/status canonicalization but doesn't audit the broader command surface. This is a fresh-eyes observation.

### 4.7 Cross-harness lock-in to Claude Code

Your hooks are PowerShell, your skill structure uses Claude Code's `.claude/`, your scripts assume Claude Code's transcript format. Superpowers runs on 8 harnesses with one skill set. **This is a deliberate choice** — your framework is for-future-team-on-Claude-Code, not multi-harness. Worth being explicit about.

**Maps to**: not an adoption candidate; strategic posture observation.

### 4.8 Your behavior-shaping prose lacks bite in skills specifically

Voice intensity by artifact type (my measurement; v4 does not measure this):

| Artifact type | Yours (1-5) | Theirs (1-5) |
|---|---|---|
| Commands | 5/5 (ALL CAPS rules) | N/A |
| Agents | 4/5 (facilitator strong) | N/A |
| Rules | 3-4/5 | N/A (embedded in skills) |
| Skills | **2/5 (mostly descriptive)** | **3.8/5** |
| Hooks | N/A (code) | N/A |

The artifacts most likely to be auto-loaded have the *least* behavior-shaping bite.

**Maps to**: §5.4 — structural-craft contribution. Path A staging closes this.

### 4.9 No execution-worker artifact class

Your agents are uniformly "specialist perspectives" (security, qa, performance) with Values + Domain Lens. You have no role-specific *execution-worker template* pattern (Superpowers' implementer / spec-reviewer / code-quality-reviewer prompt template files). The Implementer Status Protocol (DONE_WITH_CONCERNS state) is folded into Sprint 1 additively, but the broader pattern — templates as a distinct artifact class — is not articulated.

**Maps to**: §5.4 — structural-craft contribution. R5 in Path A roadmap.

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How Superpowers stands against your 8 Non-Negotiable Principles:

| # | Principle | Superpowers stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **Disagrees by omission** — behavior shaping is their primary artifact | **Yes — fundamental** | Your bet on reasoning capture is the central differentiator. Hold the line, but consider that behavior shaping is *also* a primary artifact, and you have less of it than they do. |
| 2 | Capture must be automatic | **Partial** — they auto-*invoke* behavior; you auto-*record* reasoning | **Yes** | Your principle is enforced at the capture layer but not at the *guidance-consumption* layer. Auto-invocation is the gap; Path A closes it. |
| 3 | Collaboration precedes adversarial rigor | **Loosely agrees** — collaborative skills, no adversarial mode | Compatible | No tension. |
| 4 | Independence prevents confirmation loops | **Strongly agrees** — fresh subagent per task + separate spec reviewer + separate quality reviewer | Compatible (and arguably sharper) | v4 deliberated and preserved PARALLEL; re-evaluation gated to Sprint 2 with measurement requirement. |
| 5 | ADRs are never deleted | **No equivalent** | Neutral | Their philosophy has no decision-history concept. Yours has one. Hold. |
| 6 | Education gates before merge | **Disagrees by omission** — no education gate | **Yes** | v4 substantially reframes this principle (Option C default with Option B carve-out). Your differentiation evolves but the principle is preserved in intent. |
| 7 | Layer 3 promotion requires human approval | **Partial** — human-partner approval at PR submission only; no knowledge-promotion concept | Neutral | They have no knowledge-promotion pipeline. Yours is differentiated. |
| 8 | Least-complex intervention first | **Strongly agrees at substrate level** — zero-dependency, prose-as-code. **Disagrees implicitly at orchestration surface** — your 17 commands vs. their 0 | **Yes — for command surface** | Substrate discipline holds. Command surface should be audited. §5.4 makes this concrete. |

**Four principles are challenged: #1, #2, #6, #8.** #1 and #6 are validated by what Superpowers omits. #2 and #8 suggest changes — auto-invocation mechanism (#2, addressed in Path A) and command-surface audit (#8, addressed in §5.4).

### 5.2 Adoption Candidates — v4-Aligned

Each pattern below carries a **v4 status tag** indicating its place in the existing research workflow. Patterns are scored on the 5-dim rubric (prevalence / elegance / evidence / fit / maintenance, out of 25) consistent with the format used in ANALYSIS-20260515-superpowers.md.

#### Pattern 1: SessionStart bootstrap + auto-loaded "using-the-framework" skill

**Score: 22/25** — **Path A staging**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 4 | Auto-trigger via session hooks is widespread; the "1% chance → MUST" framing is distinctive to Superpowers |
| Elegance | 5 | One hook + one skill replaces ad-hoc rule consultation |
| Evidence | 5 | Shipped v5.1.0 across 8 harnesses, mature, widely deployed |
| Fit | 4 | Your hooks system supports SessionStart; you'd author `using-the-framework` skill at moderate threshold |
| Maintenance | 4 | Markdown content; low ongoing cost |

**Status note**: Your project-analyst (ANALYSIS-20260515-superpowers.md) flagged session-start bootstrap as a *cost concern* under your ADR-0013 token tracking discipline — listed it as an anti-pattern. My analysis reframes the same mechanism as a positive pattern *at moderate threshold* ("when clearly relevant," not Superpowers' "1% chance"). This divergence is unsettled in v4. **Path A** (skills investment) is the chosen direction, which positions Pattern 1 as staging work — implement when post-Tier-0 data is in and threshold can be calibrated against actual session telemetry.

**Action when staging**: Author `.claude/skills/using-the-framework/SKILL.md` with frontmatter description naming triggering conditions (CSO pattern), include `<SUBAGENT-STOP>` equivalent, informational-query exemption, and skill priority ordering. Wire via the existing SessionStart hook.

#### Pattern 2: Red Flags / `| Excuse | Reality |` tables in rules and skills

**Score: 21/25** — **CONFIRMED — v4 Sprint 1 at 0.85 confidence (rules portion)**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | The explicit *rationalization → reality* table pattern is distinctive |
| Elegance | 4 | Two-column markdown table; light format |
| Evidence | 5 | Used consistently across all 14 Superpowers skills with documented eval methodology |
| Fit | 5 | Drop-in addition to your rules and skills; technique already exists in your agents |
| Maintenance | 4 | Needs care to keep current as model behavior evolves |

**Status note**: v4 commits this for `commit_protocol.md`, `autonomous_workflow.md`, `build_review_protocol.md` in Sprint 1 (0.85 confidence). My contribution is the observation that *the technique already lives in your agents* (in "Anti-Patterns to Avoid" sections) — the work is propagating an existing house style, not introducing a foreign pattern. Path A extends Sprint 1's rules coverage to also include skills.

**Action**: Sprint 1 — add to `commit_protocol.md`, `autonomous_workflow.md`, `build_review_protocol.md`. Path A — extend to `testing-playbook/SKILL.md`, `security-checklist/SKILL.md`, `adr-writing/SKILL.md`.

#### Pattern 3: Sequenced two-stage review (spec compliance → code quality)

**Score: 20/25** — **DELIBERATED AND DEFERRED — v4 Sprint 2 re-eval, gated on measurement**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | Most frameworks use single-pass or parallel-panel review |
| Elegance | 5 | Clean separation — spec correctness vs. code quality are different questions |
| Evidence | 4 | Superpowers' subagent-driven-development is the main case |
| Fit | 4 | Would complement existing facilitator panel reviews |
| Maintenance | 4 | Clear roles, low drift risk |

**Status note**: My original recommendation was to adapt this pattern into `build_review_protocol.md`. **This was wrong given v4**: the 12-agent deliberation already considered this and chose PARALLEL preserved. Two-Stage Review re-evaluation is gated to Sprint 2, with the explicit condition that survival rate must be measurable first (independent-perspective turn 16). The recommendation is withdrawn for now — my comparison is supporting evidence for the Sprint 2 re-evaluation, not a now-decision.

**Action**: None now. v4 Sprint 2 re-evaluation will revisit when survival-rate data is in. My analysis enters the evidence pool for that pass.

#### Pattern 4: Atomic-task plan granularity

**Score: 18/25** — **Below threshold; defer**

Their plans break into 2–5 minute atomic units with complete code; yours produce specs that `/build_module` interprets. Below v4 attention threshold and the 20/25 adoption gate. Worth re-scoring if you find spec-to-task ambiguity becoming a friction point in `/build_module` execution. Path A's R5 (`docs/templates/` for execution workers) addresses a related but distinct gap.

#### Pattern 5: Continuous-execution doctrine

**Score: 17/25** — **Below threshold; likely covered by Karpathy Principle 4**

Their explicit "don't pause between tasks" framing is sharper than your `autonomous_workflow` rule's current articulation. v4 Sprint 1 folds **Karpathy Principle 4 (Goal-Driven Execution)** into `autonomous_workflow.md` at 0.78 confidence; that integration likely subsumes this pattern. Verify alignment when the Karpathy merge happens; no separate adoption recommended.

#### Pattern 6: Imperative voice tightening (in skills specifically)

**Score: 19/25** — **Path A staging — structural-craft contribution**

Below the 20/25 threshold as a standalone adoption candidate, but the underlying *measurement* of voice intensity by artifact type is a genuinely new finding v4 lacks (see §4.8 table). Path A's R3 closes the gap by bringing skills from 2/5 to ~3.5-4/5 — match agent-level intensity, not command-level absolute mandate.

#### Pattern 7: Verification-Before-Completion (added — missed in original)

**Score: 20/25** — **CONFIRMED — v4 Sprint 1 at 0.85 confidence**

Cited in your project-analyst (ANALYSIS-20260515-superpowers.md, Pattern 3 in that document, 20/25). **I missed this in my original pass and should have surfaced it as a primary recommendation.**

Source: `skills/verification-before-completion/SKILL.md`. Before any completion claim, run the verification command *in the current message* and cite its output. "Expressing satisfaction before verification" is a protocol violation. Maps claim types to required commands (tests pass → pytest output; bug fixed → regression test red-green cycle).

**Why it matters**: Your framework gates verification at commit time (`quality_gate.py`, pre-commit hook). Superpowers inserts the gate at *every mid-task completion assertion*, preventing trust erosion before the commit gate fires. v4 commits to a new `.claude/rules/verification_before_completion.md` in Sprint 1 at 0.85 confidence.

**Action**: Sprint 1 — create `.claude/rules/verification_before_completion.md` per v4 working position. Map claim types to required verification commands.

#### Pattern 8: Implementer Status Protocol — DONE_WITH_CONCERNS (added — missed in original)

**Score: not formally rescored; v4 working position is "Sprint 1 additive"**

Cited in your project-analyst (ANALYSIS-20260515-superpowers.md, Pattern 4 in that document, marked "Investigate Further"). **I missed this in my original pass.**

Source: `skills/subagent-driven-development/SKILL.md:104-119`; `implementer-prompt.md`. Four-state status protocol — DONE / DONE_WITH_CONCERNS / BLOCKED / NEEDS_CONTEXT — each with a defined handling path. DONE_WITH_CONCERNS captures "completed but uncertain"; prevents silent doubt suppression.

**Why it matters**: Your checkpoint protocol has APPROVE and REVISE. No "completed with doubts" state exists. v4 (architecture-consultant turn 14 + project-analyst turn 10) folds this into Sprint 1 as additive — uses the existing `risk_flags` plumbing, no new infrastructure required.

**Action**: Sprint 1 — add DONE_WITH_CONCERNS as third disposition state in `build_review_protocol.md`. The state surfaces "completed but uncertain" findings via the existing `risk_flags: ["unresolved-checkpoint"]` mechanism.

#### Pattern 9: `<SUBAGENT-STOP>` subagent context hygiene (added — missed in original)

**Score: not formally rescored; "Investigate" — Path A enabler**

Cited as a blind-spot observation in your project-analyst (ANALYSIS-20260515-superpowers.md, "Blind Spot Identified"). **I missed this entirely in my original pass.**

Source: `skills/using-superpowers/SKILL.md` opening block. The `<SUBAGENT-STOP>` tag prevents the bootstrap skill from being processed by dispatched subagents. Superpowers' insight: when a subagent is dispatched for a focused task, it should not have to also process the framework-bootstrap manifest — that's controller-level guidance, not worker-level.

**Why it matters**: Your subagents currently receive the full system prompt including all auto-loaded rules. **Subagent context is heavier than it needs to be.** When Path A's Pattern 1 (using-the-framework SessionStart bootstrap) lands, you'll want a SUBAGENT-STOP-equivalent so dispatched subagents skip the framework-bootstrap skill content.

**Action**: When Path A's Pattern 1 ships, include a SUBAGENT-STOP-style gate in `using-the-framework/SKILL.md`. Subagents dispatched via Task tool should not have to re-process the manifesto skill.

### 5.3 Verdict Tally — v4-Aware

- **CONFIRMED — v4 Sprint 1 (will land post-Tier-0)** (3):
  - Pattern 2 (Rationalization Tables in rules) — 0.85 confidence
  - Pattern 7 (Verification-Before-Completion as new rule) — 0.85 confidence
  - Pattern 8 (DONE_WITH_CONCERNS additive to build_review_protocol)
- **Path A staging — skills investment** (2):
  - Pattern 1 (SessionStart bootstrap + using-the-framework skill at moderate threshold)
  - Pattern 6 (imperative voice tightening in skills)
- **Path A enabler — to ship with Pattern 1** (1):
  - Pattern 9 (`<SUBAGENT-STOP>` gate equivalent)
- **DELIBERATED AND DEFERRED** (1):
  - Pattern 3 (sequenced two-stage review) — v4 Sprint 2 re-eval gated on measurement
- **Below threshold** (2):
  - Pattern 4 (atomic-task plans)
  - Pattern 5 (continuous-execution doctrine — likely covered by Karpathy Principle 4)
- **Structural-craft contributions** (4): see §5.4

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

These are the genuine additive value of the outside-eyes pass. None of these appear in v4 or the source ANALYSIS docs. They are structural observations about artifact craft, not pattern adoption recommendations.

#### Contribution 1: Imperative voice distribution by artifact type

**Measurement** (1-5 scale, where 1 = descriptive and 5 = absolute mandate):

| Artifact type | Yours | Superpowers |
|---|---|---|
| Commands | 5/5 (review.md "NEVER skip capture") | N/A |
| Agents | 4/5 (facilitator.md "You must...") | N/A |
| Rules | 3-4/5 (testing_requirements.md imperative but compact) | N/A (embedded in skills) |
| **Skills** | **2/5 (testing-playbook.md descriptive)** | **3.8/5** |

**Observation**: The artifacts most likely to be auto-loaded (skills, if Pattern 1 lands) have the least behavior-shaping bite. v4 doesn't measure this. Path A's R3 closes the gap.

#### Contribution 2: Principle #8 audit candidate — 17 commands

**Observation**: Superpowers has zero commands; everything is auto-triggered skills. Your 17 commands include some that look like workflows the model could auto-trigger from context: `/onboard`, `/seed`, `/promote`, `/conversation`, `/status`, `/walkthrough`, `/quiz`. Each command requires the developer to remember to invoke it at the right moment.

v4 defers `/conversation` and `/status` canonicalization but does not audit the broader command surface. Principle #8 (least-complex intervention first) suggests an audit: for each of your 17 commands, ask *does this need explicit invocation, or could the model auto-trigger it from context?* Likely 4-6 commands convertible to auto-triggered skills.

**Status**: Path A R6 — independent of skills investment timing; can run in parallel whenever audited.

#### Contribution 3: First-order behavior shaping vs. second-order infrastructure

**Frame**: Your framework's primary investment is *second-order infrastructure* — it captures reasoning, runs deliberations, tracks lineage, surfaces patterns. Superpowers' primary investment is *first-order behavior shaping* — it directs work in the moment via auto-triggered skills.

You have less of *theirs* than they have of *yours*. The framework evolution question isn't "is my bet right?" (it is) but "do you want both?" v4 implicitly answers yes — Sprint 1's Rationalization Tables + Verification-Before-Completion are first-order behavior-shaping additions to a previously-second-order framework. The pattern continues in Path A.

#### Contribution 4: Execution-worker artifact class is missing

**Observation**: Your `.claude/agents/` directory contains 12 specialist-persona definitions (Values + Domain Lens + Anti-Patterns). All are *perspectives* used for review/deliberation/evaluation. None are *role-specific dispatch templates* for execution workers (Superpowers' implementer-prompt.md, spec-reviewer-prompt.md, code-quality-reviewer-prompt.md).

v4 absorbs the *DONE_WITH_CONCERNS state* from this pattern (Pattern 8 above) but does not articulate the broader pattern — that templates as a distinct artifact class would give you Superpowers' lighter dispatch model in addition to your specialist-perspective model. Path A R5 creates `docs/templates/` for these.

### 5.5 Meta-Questions for Framework Evolution

These survive from the original document, refined post-v4 reading.

1. **Reasoning capture vs. behavior shaping — do you want both?** Your bet on reasoning-capture compounds at the institution level. Their bet on behavior-shaping compounds at the session level. v4 implicitly chooses *both* (Sprint 1's first-order additions to a second-order framework). Path A is the extension of that choice into the skills layer.

2. **For-you or for-future-team?** Resolved in dialogue (2026-05-16) in favor of for-future-team. The template/spawn model is intrinsically methodology-publishing. This shapes priority: developer experience for adopters, documentation quality, learning curve, abstraction-vs-flexibility trade-offs.

3. **Your 17 commands may be substituting for missing auto-trigger infrastructure.** Several commands look like skills that should auto-trigger from context. Once Path A's Pattern 1 (`using-the-framework` SessionStart bootstrap) lands, the natural follow-on is the Principle #8 command audit (Path A R6). Auto-triggered skills shift the "did I remember to invoke?" burden onto the model.

4. **Your "writing-skills"-equivalent is missing.** Superpowers' meta-skill `writing-skills` formalizes skill creation as TDD-on-documentation. You have no equivalent skill-authoring discipline. As your framework evolves (especially during Path A's skills investment), the process by which you author new skills becomes the bottleneck. Worth scoring as a future pattern: **TDD applied to skill authoring** — likely high adoption fit, particularly given v4's Sprint 1 commitment to expand rules and your Path A commitment to invest in skills.

---

## 6. Open Tasks Surfaced by This Document

Captured for forward visibility, not for immediate action:

| Task | Owner | Sequencing |
|---|---|---|
| Update `comparison-01-superpowers.md` to v4-aligned form | claude-opus-4-7 | This session — DONE on creation of this version |
| Sprint 1: `.claude/rules/verification_before_completion.md` | framework developer | Post-Tier-0 |
| Sprint 1: Rationalization Tables in `commit_protocol.md`, `autonomous_workflow.md`, `build_review_protocol.md` | framework developer | Post-Tier-0 |
| Sprint 1 additive: DONE_WITH_CONCERNS in `build_review_protocol.md` | framework developer | Post-Tier-0 |
| Path A R1: `using-the-framework/SKILL.md` + SessionStart wire | framework developer | Path A — post-Tier-0 + threshold calibration |
| Path A R2 extension to skills | framework developer | Path A |
| Path A R3: imperative voice tightening in skills | framework developer | Path A |
| Path A R4: SKILL.md skeleton adoption (When to Use / Process / Red Flags / Examples / Final Rule) | framework developer | Path A |
| Path A R5: `docs/templates/` for execution-worker prompts | framework developer | Path A |
| Path A R6: Principle #8 command audit (17 commands → keep/convert/borderline) | framework developer | Standalone; whenever audited |
| Pattern 3 re-evaluation when survival rate measurable | v4 Sprint 2 process | Gated on Tier 0 + measurement infrastructure |

---

## Appendix: What I Didn't Examine

For honesty about scope:
- Skill *content* of `brainstorming`, `systematic-debugging`, `verification-before-completion`, `requesting-code-review`, `receiving-code-review`, `using-git-worktrees`, `finishing-a-development-branch`, `dispatching-parallel-agents`, `executing-plans`. (Read `using-superpowers`, `test-driven-development`, `subagent-driven-development`, `writing-skills`; skimmed others.)
- The `tests/` directory and its skill-testing infrastructure.
- The `scripts/` directory.
- The Codex / Gemini / Cursor harness adapter code.
- Marketing/sponsorship pages and the related blog post.

If a future pass needs more granularity on any of these, they're at `C:/Work/AI/research_projects/superpowers/`.
