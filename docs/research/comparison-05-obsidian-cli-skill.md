---
title: "Obsidian-CLI-skill Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "5 of 6"
target_repo: pablo-mano/Obsidian-CLI-skill
target_path: C:/Work/AI/research_projects/Obsidian-CLI-skill
target_version: v1.3.0 (skill); v1.12.4+ (Obsidian CLI minimum)
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "framed as additive to SYNTHESIS-20260515-adoption-brief-v4; CSO description framing is the Conflict 2 cross-source convergence point with superpowers"
prior_research:
  - docs/analysis/ANALYSIS-20260515-obsidian-cli-skill.md (project-analyst, 2026-05-15, recovered-from-summary, top score 19/25)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 0.75 synthesis confidence)
  - docs/research/comparison-01-superpowers.md (sibling — converges on CSO description framing)
  - discussions/2026-05-16/DISC-20260516-050945-framework-adoption-sequence-two-project/transcript.md (sealed)
principles_challenged: [2, 8]
verdict_summary:
  v4_sprint1_confirmed: 1
  v4_sprint1_additive: 0
  path_a_staging: 2
  deliberated_and_deferred: 0
  below_threshold: 1
  structural_craft_contributions: 4
---

# Obsidian-CLI-skill vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

This is the **fifth** of six external-project comparisons. It is written *after* v4 SYNTHESIS is in hand and the per-project ANALYSIS exists, so its contribution is additive — not a re-derivation of patterns already scored.

The single most consequential finding in obsidian-cli-skill is the **CSO description framing** — descriptions written as model-routing instructions, empirically pressure-tested against an eval set, rewritten when failures expose phrasing that triggers on the wrong cue. v4 (Conflict 2 resolution) already adopts this framing on the strength of **cross-source convergence with Superpowers** (project-analyst turn 10 Rule-of-Three argument: two unrelated projects reached the same counter-intuitive finding via independent pressure testing). This document does not re-litigate that adoption — it is tagged CONFIRMED — and instead focuses on what obsidian-cli-skill adds *beyond* the convergence point:

- **What v4 has via convergence**: CSO is the adoption decision.
- **What this document adds**: the *eval-loop methodology* that produced the CSO insight in obsidian-cli, and several structural-craft observations about how a small single-skill repo handles versioning, mirroring, gotcha docs, and cross-harness compatibility — observations the project-analyst's recovered-from-summary analysis did not preserve.

The repo is small (1,301 lines across two markdown files, one HTML eval tool, one JSON dataset, plus marketplace manifests). Its discipline-to-surface-area ratio is high. Several patterns visible here are easy to miss in larger repos because the noise is lower.

---

## 1. Identity & What's Useful

**Obsidian-CLI-skill** is a single-skill Claude Code plugin that teaches AI coding agents how to operate Obsidian vaults via Obsidian's official CLI (v1.12+, IPC-based). It is not a software system, not a framework, not a methodology. It is one well-crafted SKILL.md + one 651-line command reference + one 35-case eval dataset + an HTML authoring tool for the eval set + marketplace packaging. 173 stars, 18 forks, activity concentrated in a tight Feb–Mar 2026 window with a sharp evolutionary arc that's fully observable in git.

The repo composition tells the story:

- `skills/obsidian-cli/SKILL.md` (289 lines) — frontmatter description + 22 trigger phrases + skill body
- `skills/obsidian-cli/references/command-reference.md` (651 lines) — full reference, externalized
- `eval/eval_set.json` (35 entries: 20 positive + 15 negative) + `eval/eval_review.html` (220 lines, self-contained authoring UI)
- `plugins/obsidian-cli/skills/obsidian-cli/` — **mirrored** copy of the skill for marketplace packaging
- `.claude-plugin/marketplace.json` + `.claude-plugin/plugin.json` — packaging
- README.md installs the same skill across **8 harnesses**: Claude Code, Cursor, Cortex Code, GitHub Copilot, Windsurf, Nanoclaw, Openclaw, plus a generic "any LLM" fallback

**Top 5 things worth studying:**

1. **CSO description (description-as-routing-instruction)** — `skills/obsidian-cli/SKILL.md:4-18`. Written as triggers + exclusions + a discrimination principle (*"the user is asking Claude to act, not to explain"*). Already adopted in v4.

2. **Eval-loop authoring discipline** — `eval/eval_set.json` + `eval/eval_review.html`. The description was rewritten **three times** based on observable eval-set failures, each rewrite recorded as a discrete commit with the rationale captured in the message. The HTML tool is a self-contained single-file editor for the dataset, kept in the repo alongside the skill.

3. **Gotcha-driven docs with cause-and-workaround grain** — `skills/obsidian-cli/SKILL.md:255-275` (Tips section: 13 numbered items, each one an empirically-discovered failure pattern with a documented workaround). The format is `behavior → cause → workaround` and is consistent across both `Tips` and `Troubleshooting` sections.

4. **References pattern (skill body + externalized reference doc)** — `skills/obsidian-cli/SKILL.md:50-52` ("Read `references/command-reference.md` when you need specific flags, output formats, or subcommands"). The skill is the routing surface and the conceptual overview; the reference doc is the full enumeration. The skill stays scannable; the reference is consulted on demand.

5. **Cross-harness portability via prose-as-substrate** — the same `SKILL.md` file ships unchanged across 8 harnesses with harness-specific install paths. The skill content is portable because it's prose; portability is achieved at the *substrate* layer, not via an adapter layer.

**Cultural signal**. There is no manifesto, no philosophy file, no opinionated rejection of upstream patterns. The repo is *empirically humble*: it logs failures (3 documented gotchas in v1.3.0 from issue #1), tracks the eval set in git, and the commit graph shows two Claude-authored commits (`8fc3803` and `a882e74`) where the AI was a contributor under human review. The PR #5 merge ("skill-creator-improvements") is itself an example of using a skill-creation methodology — likely Anthropic's `skill-creator` skill — *on the skill itself*. This is dogfooding the eval-loop discipline.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Obsidian-CLI-skill | Agent Framework Template |
|---|---|---|
| Skill format | SKILL.md with YAML frontmatter | SKILL.md with YAML frontmatter |
| Skill packaging | `.claude-plugin/` marketplace manifests | None (no plugin packaging) |
| Externalized reference | `references/command-reference.md` | Skills are mostly self-contained |
| Multi-harness install | 8 harnesses documented | Claude Code only |
| Empirical evaluation | `eval/eval_set.json` + HTML reviewer | None (skills not eval-tested) |
| Gotcha documentation | 13 Tips + 10-row Troubleshooting table | `CLAUDE.md` Known Limitations (project-level only) |

### Theirs-only (you don't have this)

- **CSO description framing in skill frontmatter** (already CONFIRMED in v4 via cross-source convergence)
- **Eval set + authoring tool** kept in-repo alongside the skill itself
- **Triggers list as separate YAML field** (22 trigger phrases listed below the prose description)
- **Skill version field** in frontmatter (`version: "1.3.0"`)
- **`.claude-plugin/marketplace.json` + `plugin.json` manifests** — plugin packaging schema
- **Cross-harness install matrix** with harness-specific notes (e.g., Windsurf's 12,000-char rule limit forcing a 2-file split)
- **Mirrored skill location** for marketplace compatibility (`plugins/obsidian-cli/skills/obsidian-cli/` + canonical `skills/obsidian-cli/`)
- **Gotchas with full cause-and-workaround triplets** embedded *in the skill body*, not just in a project-level Known Limitations file

### Yours-only (they don't have this)

- Everything in your reasoning-capture stack (events.jsonl, SQLite, ADRs, lineage, sourced-assertion substrate).
- 12-agent specialist panel; 14 rules; 17 commands.
- External-project analysis pipeline (`/analyze-project`, adoption log, Rule of Three) — this very document is its output.
- Hooks, quality gate, capture pipeline, failure taxonomy, knowledge pipeline.
- ADRs as immutable decision history; promotion gates; education gates (v4-reframed).

The shapes are entirely different: theirs is a single-skill artifact with eval-loop discipline; yours is a methodology-publishing framework. The comparison is structural-craft only, not feature parity.

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Your reasoning-capture central bet remains uncontested by this comparison.** Obsidian-CLI-skill has zero session capture, zero ADRs, zero deliberation infrastructure. Nothing in this repo challenges Principle #1.

2. **Your skill *body* prose is comparable in quality.** The framework's `python-project-patterns/SKILL.md`, `testing-playbook/SKILL.md`, etc., contain reasonable reference content. The body craft is fine.

3. **Your gotcha capture exists at the right grain — just at the wrong level.** Your `CLAUDE.md` Known Limitations section uses the same `behavior → cause → workaround` shape obsidian-cli uses in its skill body. The technique is in your house style — just not propagated into skill files yet. This is alignment, not gap.

4. **Your strategic posture (for-future-team, methodology-publishing) does not need cross-harness portability.** Obsidian-CLI-skill ships across 8 harnesses because it's a small reusable artifact with no infrastructure dependencies. Your framework's hooks, capture scripts, and PowerShell tooling make it Claude-Code-specific by design. This is a deliberate trade-off, not a gap to close.

---

## 4. Weaknesses This Comparison Exposes

Ordered by severity. Several are direct extensions of weaknesses already surfaced in comparison-01-superpowers (§4.1, §4.8) — obsidian-cli-skill is corroborating evidence, not new failure modes.

### 4.1 Skill descriptions are workflow summaries, not routing instructions

All 6 framework skill descriptions use the **anti-pattern** obsidian-cli-skill rejected after eval testing:

| Skill | Current description (truncated) |
|---|---|
| `testing-playbook` | "Testing strategies and patterns for Python/pytest projects. Reference when writing tests..." |
| `security-checklist` | "Security review checklist for Python/FastAPI applications. Reference during security reviews..." |
| `adr-writing` | "Guide for writing Architecture Decision Records. Reference when creating ADRs..." |
| `python-project-patterns` | "Python project patterns and best practices for FastAPI applications. Reference when writing or reviewing Python code." |
| `performance-playbook` | "Performance analysis techniques for Python/FastAPI applications. Reference when reviewing performance..." |
| `feature-status-registry` | "Pattern for tracking feature implementation status in derived projects. Reference when..." |

Source: [`Grep -r "^description:" .claude/skills/`](../../.claude/skills/) — pattern observed across all 6.

Obsidian-CLI-skill went through this exact phrasing in v1 (`c7b35b3`, *"Optimize skill description and add eval set"*) — *"Use this skill for any workflow where the user controls Obsidian from a terminal or script"* — and demoted it because the eval set caught natural-language vault requests being misclassified. The v2 rewrite (`a882e74`, *"Apply optimized description from run_loop eval"*) explicitly emphasized **vault action intent over CLI syntax**, with the discrimination principle *"the user is asking Claude to act, not to explain"*. Your framework's current descriptions describe contents ("Testing strategies and patterns...") and use **the word "Reference when"** — which signals *passive consultation*, not *active routing*. The model has no reason to consult them proactively.

**Maps to**: v4 Conflict 2 (CONFIRMED). Path A's R1+R4 work covers this. Project-analyst already estimated 30–60 minutes effort across all 6 skills.

### 4.2 No eval-loop infrastructure for skills

Your knowledge pipeline (`v_rule_of_three`, `agent_effectiveness`, findings extraction) measures *agent behavior in discussions*. There is no equivalent measurement of *skill triggering* — no `skill_trigger_log`, no labeled eval set, no "did this skill fire when it should have?" feedback. Path A's commitment to make skills load-bearing implicitly assumes the skills are *triggered correctly*; without measurement, there's no way to know if Pattern 1's SessionStart bootstrap actually changes invocation rates.

Obsidian-CLI-skill's eval-set + HTML tool is the lightest possible infrastructure for this: 35 labeled queries in JSON, a 220-line single-file editor for curating them. The repo's history shows the maintainer cycling description → eval → rewrite three times over six days. The technique is portable.

**Maps to**: §5.2 Pattern 2 — Path A staging. The eval-loop is the missing measurement layer Path A's threshold calibration needs.

### 4.3 No skill versioning convention

Obsidian-cli-skill's frontmatter carries `version: "1.3.0"`, and the README badge tracks that version. Your skills have no version field, no changelog, no notion of "this skill is at v1.2.0 and changed in this way." For a methodology-publishing framework whose central bet is institutional memory, the absence of skill versioning is a small but real gap — derived projects (Insight Journal, VerificationPortal) consume the framework's skills, and a skill content change has no record of when it changed or what changed.

**Maps to**: §5.4 — structural-craft contribution. Below the 20/25 adoption threshold as a feature in isolation, but worth carrying into the Path A skills investment as a hygiene addition.

### 4.4 Skill body / reference split is asymmetric across the 6 framework skills

Obsidian-cli-skill cleanly separates the **skill body** (50KB conceptual overview + most common patterns, lives in `SKILL.md`) from the **reference** (132KB enumeration of all commands, lives in `references/command-reference.md`). The skill body explicitly *points to* the reference: *"Read `references/command-reference.md` when you need specific flags, output formats, or subcommands for any command group."*

Your 6 skills are flat — no skill has a `references/` subdirectory. Some, like `python-project-patterns`, mix conceptual guidance with implementation snippets in the same file. This isn't broken — your skills are smaller and the split doesn't pay off at their current size — but Path A's commitment to make skills load-bearing will grow them. Worth knowing the pattern exists.

**Maps to**: §5.4 — structural-craft contribution. Adopt opportunistically when a skill grows past ~300 lines.

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How obsidian-cli-skill stands against your 8 Non-Negotiable Principles:

| # | Principle | Obsidian-CLI-skill stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **No equivalent** | Compatible | The repo has *commit-level* reasoning capture (Claude-authored commits, eval-rewrite rationale in messages) but no session capture. Nothing challenges your bet. |
| 2 | Capture must be automatic | **Partial** — eval-set is automatic (in CI sense) but skill triggering is *evaluated*, not *captured* | **Yes — measurement gap** | Your principle is enforced at the capture layer for *agent behavior in discussions*; not enforced at the *skill-triggering* layer. Path A's skills investment needs an eval-loop equivalent. |
| 3 | Collaboration precedes adversarial rigor | **N/A** | Compatible | No multi-agent surface. |
| 4 | Independence prevents confirmation loops | **N/A** | Compatible | Single-author skill repo. |
| 5 | ADRs are never deleted | **No equivalent** | Compatible | Commit history is the closest analog; less structured but observable. |
| 6 | Education gates before merge | **N/A** | Compatible | No equivalent. |
| 7 | Layer 3 promotion requires human approval | **N/A** | Compatible | No knowledge-promotion pipeline. |
| 8 | Least-complex intervention first | **Strongly agrees** — one skill, one reference, one eval set, one HTML tool, zero infrastructure | **Yes — by example** | The repo is a strong case for §5.4 Contribution 2 below: the simplest skill-with-evaluation possible is *very* simple. |

**Two principles are challenged: #2 and #8.** #2 in a new way (skill-triggering measurement, not capture); #8 by example (the eval-loop is achievable in a single HTML file). Neither overrides the working positions in v4.

### 5.2 Adoption Candidates — v4-Aligned

#### Pattern 1: CSO description framing (description as activation classifier)

**Score: 22/25** — **CONFIRMED — v4 Conflict 2 resolution (cross-source convergence)**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 4 | Convergent across obsidian-cli-skill and superpowers; not yet ubiquitous |
| Elegance | 5 | Pure prompt-level change; zero infrastructure |
| Evidence | 5 | Empirically validated against 35-case eval set; description rewritten 3× over 6 days based on observable failures |
| Fit | 5 | Drop-in to all 6 existing `.claude/skills/*.md` files; 30–60 min total per project-analyst estimate |
| Maintenance | 3 | Needs care during evolution — adding capabilities means updating description triggers/exclusions in sync. Reduces to 4 if eval-loop measurement (Pattern 2 below) is in place. |

**Status note**: v4 commits the CSO framing as Conflict 2 resolution on the Rule-of-Three-via-two-sources argument (project-analyst turn 10). My contribution beyond what v4 already has: the precise **discrimination-principle sentence** from obsidian-cli's v2 rewrite — *"the user is asking Claude to act, not to explain"* — is a copy-able template. Substitute the action verb per skill: testing-playbook becomes *"the user is asking Claude to design/review/write tests, not to explain testing concepts"*; security-checklist becomes *"the user is asking Claude to evaluate or harden, not to teach security"*.

**Action**: Path A R4 — when authoring CSO descriptions for the 6 framework skills, use the discrimination-principle template. Cite this comparison in the migration note.

#### Pattern 2: Eval-set + authoring tool kept in-repo alongside the skill

**Score: 21/25** — **Path A staging — addresses §4.2 measurement gap**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 2 | Distinctive to skill repos with discipline; not common in general |
| Elegance | 5 | One JSON file + one self-contained HTML file. No frameworks, no deps. |
| Evidence | 5 | Observable in obsidian-cli git history: 3 description rewrites driven by eval failures over 6 days |
| Fit | 4 | New artifact class for your framework; fits well under `.claude/skills/<name>/eval/` or `docs/research/eval-sets/` |
| Maintenance | 5 | Labeled JSON + static HTML — drift risk is the eval set going stale, not the tool |

**Status note**: v4 does not have this. The eval-loop is the **missing measurement layer** Path A's Pattern 1 (SessionStart bootstrap + threshold calibration) implicitly requires. Without it, threshold calibration for "when clearly relevant" is unobservable — there's no way to measure skill invocation rate against intended invocation rate.

**Action when staging**: When Path A R1 (SessionStart bootstrap) is on the work-list, ship an `eval/` directory per skill with a 20–40-query labeled set (positive triggers, negative non-triggers, the discrimination edge cases). Reuse obsidian-cli's `eval_review.html` directly — it's MIT-style permissive in spirit, single file, no dependencies. Run the eval set against each skill *before* and *after* the SessionStart bootstrap lands; the diff is the calibration data.

#### Pattern 3: Gotcha-driven docs embedded in skill body (not just project-level Known Limitations)

**Score: 20/25** — **Path A staging**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | The pattern is recognizable; obsidian-cli's discipline (every gotcha gets cause + workaround) is distinctive |
| Elegance | 4 | Numbered Tips list + Troubleshooting table; both lightweight markdown |
| Evidence | 4 | Skill body section 255-275 + Troubleshooting 278-289; 13 + 10 entries respectively, sourced from issue #1 and live testing |
| Fit | 5 | Technique already exists in your `CLAUDE.md` Known Limitations; extending to skills is structural-house-style alignment |
| Maintenance | 4 | Gotchas accumulate; needs periodic pruning as upstream tools change |

**Status note**: Project-analyst already scored this at 18/25 in the recovered-from-summary ANALYSIS doc. My re-scoring at 20/25 reflects (a) reading the actual artifact to see the `behavior → cause → workaround` triplet is consistent across 23 entries, and (b) explicit alignment with Path A's R2 — Red Flags tables in skills. Gotcha-driven docs are the *positive-format complement* to Red Flags tables (Red Flags = anti-rationalization; Gotchas = empirical-failure-with-workaround).

**Action**: Path A R2 — when adding Red Flags tables to skills, also add a Gotchas / Tips section per skill where each entry follows the `behavior → cause → workaround` shape. Migrate relevant entries from `CLAUDE.md` Known Limitations to the appropriate skill body.

#### Pattern 4: Skill version field + skill changelog

**Score: 18/25** — **Below threshold; carry into Path A as hygiene addition**

Frontmatter `version` field (`skills/obsidian-cli/SKILL.md:3`) + README badge + commit history *as* changelog. Below the 20/25 threshold as a standalone adoption candidate; the value compounds when (a) Path A's skills investment increases skill content velocity, and (b) the framework's downstream consumers (Insight Journal, VerificationPortal) need to know what changed. Not a Sprint 1 item; add when authoring the Path A SKILL.md skeleton (R4).

#### Pattern 5: Cross-harness portability via prose-as-substrate

**Score: not formally rescored** — **DELIBERATELY OUT OF SCOPE for your framework**

Obsidian-cli-skill ships unchanged across 8 harnesses. Your framework deliberately targets Claude Code only (per `user_framework_developer.md` strategic posture: *for-future-team-on-Claude-Code, not multi-harness*). Comparison-01-superpowers §4.7 already flagged this as a strategic-posture observation, not an adoption candidate. Obsidian-cli-skill provides corroborating evidence that prose-as-substrate enables portability — but your framework's hooks, capture scripts, and PowerShell tooling are intentionally non-portable. Not an adoption candidate.

### 5.3 Verdict Tally — v4-Aware

- **CONFIRMED — v4 Sprint 1 (via Conflict 2 resolution)** (1):
  - Pattern 1 (CSO description framing) — cross-source convergence with superpowers, copy-able discrimination-principle template added
- **Path A staging** (2):
  - Pattern 2 (eval-set + HTML authoring tool) — addresses Path A's missing measurement layer
  - Pattern 3 (gotcha-driven docs in skill body) — complements Path A R2 Red Flags tables
- **Below threshold** (1):
  - Pattern 4 (skill version field + changelog) — carry into Path A R4 as hygiene
- **Strategic-posture observation, not adoption candidate** (1):
  - Pattern 5 (cross-harness portability) — out of scope by design
- **Structural-craft contributions** (4): see §5.4

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

#### Contribution 1: The eval-rewrite loop is *the* generative pattern, not the description itself

**Frame**: v4 adopts the CSO description framing as *content*. What obsidian-cli-skill shows in its git history is that CSO is not a *style*; it's the **observable equilibrium of an iterative pressure-test loop**. Three commits, in order:

1. `c7b35b3` (2026-03-04) — *"Optimize skill description and add eval set"* — adds eval set + initial CLI-oriented description ("the single clearest signal: the user is invoking or wants to invoke the `obsidian` command...")
2. `de356e8` (2026-03-04, same day) — *"Broaden skill description to trigger on vault intent, not just CLI mentions"* — first rewrite when eval cases like *"add this to my daily note"* fail.
3. `a882e74` (2026-03-04, same day) — *"Apply optimized description from run_loop eval; add v2 eval set"* — second rewrite, references *"run_loop eval"* explicitly.

The author cycled three rewrites *on the same day*. The CSO framing is the artifact at iteration 3. Without the eval-loop, the author would have stopped at iteration 1 (the CLI-syntax-as-trigger version, which is precisely your framework's current description pattern).

**Implication for Path A**: Adopting CSO descriptions as v4 commits to is necessary but insufficient. The *durable* adoption is the **eval-rewrite habit** — a labeled set + a quick rewrite loop. Without this, your CSO descriptions will be written once and drift back to workflow-summary form as skills evolve.

#### Contribution 2: The plugins/ mirror is *stale* — a structural-craft caution

**Observation**: The repo has two locations for the canonical SKILL.md:
- `skills/obsidian-cli/SKILL.md` (current, v1.3.0 with version field + 22-trigger list)
- `plugins/obsidian-cli/skills/obsidian-cli/SKILL.md` (mirrored for marketplace packaging, **stale by 39 lines** — no version field, no triggers list, narrower description)

The drift is observable via `diff plugins/obsidian-cli/skills/obsidian-cli/SKILL.md skills/obsidian-cli/SKILL.md` — 39 lines of difference, all in frontmatter. The marketplace install path (`/plugin install obsidian-cli` → loads from `plugins/`) serves the *older* SKILL.md to users. The direct-clone path (`cp -r skills/obsidian-cli ~/.cursor/skills/`) serves the *current* SKILL.md.

This is a real bug in the repo, *and* it's a transferable lesson for your framework: **when one source artifact ships through two distribution channels, drift is the default outcome unless mechanically synced**. Your framework will face this when:
- Skills land in `.claude/skills/` (canonical) and are inherited by derived projects via `framework-lineage.yaml` pinning
- Rules land in `.claude/rules/` (canonical) and may be cloned into derived projects' customized rule sets

Recommend: when Path A ships the SessionStart bootstrap + 6 CSO descriptions, validate that **derived-project lineage sync is mechanical, not manual**. The `lineage_file_drift` SQLite table already tracks this; verify it covers skills frontmatter, not just file presence.

#### Contribution 3: PR #5 is the framework's own `skill-creator` skill applied to a real skill

**Observation**: The PR #5 merge (`d778231`) was created from a branch named `claude/skill-creator-improvements-VvYl5`. The improvements commit (`8fc3803`) is Claude-authored and applied: (a) README command-count correction (100+ → 130+), (b) 9 missing command groups added, (c) 4 troubleshooting entries propagated SKILL.md → README, (d) `version` field + expanded description with explicit skip conditions, (e) 22-entry triggers list, (f) eval set expanded 20 → 35 cases.

This is **dogfooding** — the maintainer applied Anthropic's `skill-creator` skill (visible in your system reminder as `anthropic-skills:skill-creator`) to improve an existing skill, captured the result as a single PR, and the diff is the audit trail.

**Implication for your framework**: Your `.claude/agents/` includes 12 specialist agents but no *skill-improver* agent. Path A's R4 (Adopt Superpowers' SKILL.md skeleton: When to Use → Process → Red Flags → Examples → Final Rule) will likely benefit from an analogous *skill-creator-style* methodology — author once, then have a dedicated review pass against the eval set. Worth scoring as a future pattern alongside Comparison-01's "writing-skills is missing" observation (§5.5 #4 in that document).

#### Contribution 4: The `triggers:` YAML list is the under-rated bridge

**Observation**: obsidian-cli-skill's frontmatter has *both* a prose description *and* a 22-entry `triggers:` list. The triggers list is not part of the standard Claude Code skill frontmatter schema (your framework's skills don't have it; Anthropic's published skill examples don't have it). It's a custom field the maintainer added empirically.

The function: the prose description carries the discrimination principle ("act, not explain"); the triggers list carries the **literal substring matchers** the model can pattern-match against the user message. The two are complementary — prose for routing logic, triggers for surface-form matching.

Whether this field is *actually consumed* by Claude Code's skill-routing infrastructure is harness-dependent and undocumented. Even if it isn't consumed mechanically, it serves as **eval-set-derived ground truth in the artifact itself** — the 22 triggers are exactly the phrases the eval set tests positive cases against.

**Implication for your framework**: Path A R4's SKILL.md skeleton should consider whether to include a `triggers:` list. Two design options:
- **Option A**: Include `triggers:` as a documented field, even if not currently consumed by Claude Code's routing. It serves as in-artifact ground truth for the eval set.
- **Option B**: Don't include `triggers:` — keep frontmatter minimal, store triggers in the eval-set JSON alongside the labels.

Either is defensible. The choice matters because it sets the convention for the framework's adopters.

### 5.5 Meta-Questions for Framework Evolution

1. **Path A's threshold calibration needs an eval loop — and obsidian-cli-skill shows the lightest possible version**. Pattern 1's "when clearly relevant" threshold (rejected Superpowers' "1% chance → MUST") is calibrated against *what*? Without a labeled set, "clearly relevant" is unmeasurable. The obsidian-cli approach (35 cases in JSON, 220 lines of HTML to edit them) is the floor. Ship this alongside Path A R1 or the calibration is folklore.

2. **CSO descriptions need maintenance discipline, not just initial authoring**. The repo's three same-day rewrites show CSO is not a one-time format; it's an equilibrium under evolutionary pressure. As your framework's skills grow under Path A, the descriptions will drift back toward workflow-summary form unless the eval-loop fires. This is operational discipline, not artifact craft.

3. **Skill versioning is small but compounding**. Your derived projects (Insight Journal, VerificationPortal) inherit framework skills via lineage pinning. Without a version field, "the framework's testing-playbook" is an unstable referent. Worth adding during Path A R4 even though it scored below threshold as a standalone pattern.

4. **Dogfooding is observable in commit graphs**. PR #5's `claude/skill-creator-improvements-VvYl5` branch name is a small structural-craft signal: the maintainer explicitly named the methodology they applied. Your framework's commits would benefit from similar naming hygiene — when an agent or skill is the *generator* of a change, name it in the branch or commit. Helps reconstruct provenance later.

---

## 6. Open Tasks Surfaced by This Document

| Task | Owner | Sequencing |
|---|---|---|
| Path A R4: SKILL.md skeleton — include CSO description with discrimination-principle template from obsidian-cli v2 | framework developer | Path A |
| Path A R4: Decide whether to include `triggers:` YAML field in skill frontmatter (Option A vs. B above) | framework developer | Path A — design call |
| Path A staging: author 20-40-query labeled eval set per skill, vendor `eval_review.html` from obsidian-cli as in-repo authoring tool | framework developer | Path A — ships alongside R1 SessionStart bootstrap |
| Path A R2: when adding Red Flags tables, also add a Tips/Gotchas section with `behavior → cause → workaround` triplets per skill | framework developer | Path A |
| Path A R4: add `version` field to skill frontmatter; document changelog convention | framework developer | Path A — hygiene |
| Validate `lineage_file_drift` SQLite table covers skill frontmatter drift, not just file presence | framework developer | Before Path A skills ship to derived projects |
| Score "skill-improver agent" pattern (analogous to Superpowers' writing-skills) | future research pass | Standalone |

---

## Appendix: What I Didn't Examine

For honesty about scope:

- The full 651-line `references/command-reference.md` (read the head + a middle section; the structure was clear by section 3).
- The exact rendering of `eval_review.html` in a browser — I read the static HTML + the JS but did not run the page.
- The marketplace-install user experience (`/plugin marketplace add ...` → `/plugin install obsidian-cli`) — not testable in this sandbox.
- The other 7 harness install paths in README beyond Claude Code, Cursor, and Windsurf (skimmed; format is consistent).
- The `dev:mobile` command added in the most recent commit (`10c02c7`, post-PR-5) — outside the merge-PR signal the task scope flagged.
- Issue #1 thread on GitHub (the three documented gotchas in v1.3.0 came from this) — not fetched.

If a future pass needs more detail on any of these, they're at `C:/Work/AI/research_projects/Obsidian-CLI-skill/` or `github.com/pablo-mano/Obsidian-CLI-skill`.
