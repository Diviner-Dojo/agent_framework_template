---
title: "Open Design Comparison"
date: 2026-05-16
last_updated: 2026-05-16
sequence: "4 of 6"
target_repo: nexu-io/open-design
target_path: C:/Work/AI/research_projects/open-design
target_version: 0.8.0-preview (head commit 6bf865a4, 1001 commits, 615 bot + 24+ human contributors)
analyst: claude-opus-4-7
framework_under_comparison: agent_framework_template (v3.4)
v4_alignment: "additive to SYNTHESIS-20260515-adoption-brief-v4; honors v4 verdict (DEFER, low Sprint-1 commitment) and supplies fresh-eyes patterns the original ANALYSIS missed"
prior_research:
  - docs/analysis/ANALYSIS-20260515-open-design.md (project-analyst, 2026-05-15, recovered from agent return value — agent did not invoke Write)
  - docs/analysis/SYNTHESIS-20260515-adoption-brief-v4.md (living document, 12-agent deliberation, 0.75 synthesis confidence)
principles_challenged: [1, 3, 4, 6, 8]
verdict_summary:
  v4_sprint1_confirmed: 0
  v4_sprint1_additive: 0
  path_a_staging: 1
  adopt_above_threshold: 2
  deliberated_and_deferred: 0
  below_threshold: 3
  structural_craft_contributions: 3
---

# Open Design vs. Agent Framework Template — Deep Comparison

## 0. Document Status and Relationship to Prior Research

The original ANALYSIS-20260515-open-design.md was **recovered from the project-analyst's return value** — the agent did not invoke Write, so specific file-line citations and the full pattern inventory were never persisted. It surfaced two patterns (Five-State Coverage, layered AGENTS.md), scored only one (19/25), and concluded **DEFER** on the basis of domain mismatch (UI design tool vs. Python agent framework).

This document does three things in addition:

1. **Re-scores the Five-State Coverage pattern with fresh evidence.** The shipped `craft/state-coverage.md` is substantially more sophisticated than the recovered summary indicates — it carries WCAG-grounded ARIA rules, a duration-keyed loading-indicator matrix, retry exponential-backoff discipline, and form-specific sub-states (Untouched / Dirty-valid / Submitted-pending). The pattern crosses 20/25 once you read what actually shipped.
2. **Surfaces three additional patterns the recovered ANALYSIS missed** — `od.craft.requires` declarative-injection pattern, 5-Dimension Critique Discipline skill, and Forbidden-Surfaces PR enforcement.
3. **Returns three outside-contractor observations in §5.4** that v4 does not have and the existing ANALYSIS could not surface from the domain-mismatch frame.

Open Design is by far the largest cultural and surface-size gap among the six target repos. v4's DEFER posture is correctly load-bearing — there is no Sprint 1 commitment to chase here. But the design-tooling domain produced an artifact discipline worth borrowing precisely *because* the failure modes of generative UI design are concrete and visible in a way text-only AI work isn't. This comparison treats "domain mismatch" as a starting condition, not a stopping rule.

---

## 1. Identity & What's Useful

**Open Design** is an open-source, agent-native alternative to Claude Design / Figma. It is **a TypeScript/Electron/Next.js product**, not an agent framework template — but it ships a sophisticated *substrate* of design knowledge that the agent reads as system-prompt context. The substrate is three axes: `skills/` (133 entries, artifact-shape recipes), `design-systems/` (149 entries, brand visual language), and `craft/` (11 entries, brand-agnostic universal craft rules). The daemon parses an extended frontmatter and **declaratively injects** the requested craft references into the system prompt above each skill body.

The repo has 1001 commits, 24+ human contributors across multiple languages (`pftom`, `PerishCode`, `nettee`, `lefarcen`, `mrcfps`, `shangxinyu1` are the top human contributors; the rest of the long tail spans CJK, Cyrillic, Western European names), an automated maintainer-promotion protocol with a 7-dimension anti-sock-puppet rubric (`MAINTAINERS.md`), and a PR-duty tooling control plane (`pnpm tools-pr`). The latest commit (`6bf865a4 fix(ci): avoid duplicate nix-check runs on PR branches`) is one of a recurring CI-stability cadence. This is a *thriving production-scale OSS project*, not an experiment.

**Top 5 things worth studying:**

1. **`craft/` axis with declarative `od.craft.requires` frontmatter** — universal rules opt-in per skill, token cost paid only for what's requested. See [craft/README.md:23-43](../../../../research_projects/open-design/craft/README.md) and [craft/state-coverage.md](../../../../research_projects/open-design/craft/state-coverage.md).
2. **5-Dimension Critique Skill with anti-grade-inflation discipline** — Philosophy / Hierarchy / Detail / Functionality / Innovation, each 0-10 with mandatory evidence citations, plus four explicit anti-inflation rules ("don't average up", "don't grade-inflate", "evidence per score", "innovation is allowed to be low"). See [design-templates/critique/SKILL.md:155-168](../../../../research_projects/open-design/design-templates/critique/SKILL.md).
3. **Forbidden Surfaces + Product Relevance Test as PR gates** — a canonical list of architectural mistakes that close-on-sight, plus a `1. Product relevance test` that runs **before** implementation review. See [docs/code-review-guidelines.md:30-67](../../../../research_projects/open-design/docs/code-review-guidelines.md).
4. **Anti-AI-slop with auto-checked vs. guidance tiers** — P0 rules wired into `apps/daemon/src/lint-artifact.ts`, P1/P2 explicitly flagged as "(guidance, not auto-checked)" to keep the contract with the linter honest. See [craft/anti-ai-slop.md:1-13](../../../../research_projects/open-design/craft/anti-ai-slop.md).
5. **Skills Merge Bar + "Common reasons we close skill PRs" appendix** — eight named close-patterns ("Sponsor / promo content", "Vendor API as a skill", "Triggers that won't fire", etc.). See [docs/skills-contributing.md:249-261](../../../../research_projects/open-design/docs/skills-contributing.md).

**Cultural signal worth noting.** Six README languages (en/es/pt-BR/de/fr/zh-CN/zh-TW/ko/ja-JP/ar/ru/uk/tr), parallel CONTRIBUTING/MAINTAINERS/QUICKSTART localizations, an `i18n coverage` test (`e2e/tests/localized-content.test.ts`) that enforces every skill has English fallback display copy for de/ru/fr, and a contributor base whose top 10 includes names from at least four cultural regions. The localization is enforced as a CI gate, not aspirational. Compare to your single-locale framework — not a deficit, a different cultural posture. Their MAINTAINERS.md operationalizes an external-maintainer path (≥20 merged PRs + 7-dim account-quality rubric + qualitative judgment); your framework has only `Core Team` analogue (the human developer alone). Different scale; worth being explicit about.

---

## 2. Value Map

### What overlaps (theirs / yours)

| Capability | Open Design | Agent Framework Template |
|---|---|---|
| Multi-axis knowledge | skills/ + design-systems/ + craft/ (3 axes; 293 entries total) | rules/ + skills/ + agents/ (3 axes; 14 + 6 + 12 = 32 entries) |
| Declarative context injection | `od.craft.requires: [typography, color, anti-ai-slop]` per skill | Agent dispatch + REVIEW.md injection (centralized, not per-skill) |
| Review discipline | 5-dim critique skill + design-review skill (visual audit) | facilitator + 10 specialists + 5-dim adoption rubric |
| PR gates | Product Relevance Test + Forbidden Surfaces + lanes | Quality Gate + /review + 8 failure classes |
| Anti-pattern enumeration | Anti-AI-slop P0/P1/P2 tiers + "Common reasons we close PRs" | Failure Taxonomy + agent "Anti-Patterns to Avoid" sections |
| External contribution model | MAINTAINERS.md (≥20 PR + 7-dim rubric + Emeritus path) | Steward gate + developer approval (single human) |
| Self-critique loop | Critique skill runs on agent's own output before emission | (None — review is post-build, not mid-emission self-check) |

### Theirs-only (you don't have this)

- **`od.craft.requires: [...]` per-skill declarative context injection** — the daemon assembles the system prompt by pulling only the requested craft references, paying token cost for what's used. Your `REVIEW.md` injection is all-or-nothing per command; your skills are auto-loaded as-is, not assembled compositionally.
- **Auto-checked vs. guidance enforcement tiers** — explicit per-rule labeling so the contract with the linter stays honest. Your rules don't distinguish between hard-enforced and aspirational items.
- **5-Dimension Critique Skill with anti-grade-inflation rules** — explicit "don't average up" / "evidence per score" / "innovation is allowed to be low" / "overall mean above 8 is suspicious; check yourself" rules. Your 5-dim adoption rubric doesn't carry equivalent anti-inflation discipline.
- **Product Relevance Test as the first PR gate** — runs before forbidden-surfaces check, before implementation review. Asks: does this change identify the Open Design feature it modifies, do tests exercise *existing* flows through public seams, are assertions providing real signal (anti-tautology rule)? See [docs/code-review-guidelines.md:32-44](../../../../research_projects/open-design/docs/code-review-guidelines.md). Your /review has no equivalent "is this in scope?" gate before specialists dispatch.
- **Forbidden Surfaces as a canonical block-list** — twelve named architectural mistakes that recreate banned patterns close-on-sight (e.g., "Root lifecycle aliases: `pnpm dev`, `pnpm dev:all`, `pnpm daemon`"). Your principles describe what to do; this enumerates what's banned with named violation patterns.
- **"Common reasons we close skill PRs" appendix** — eight named close-patterns with concrete examples (Domain-specific app smuggled as tests, Standalone-app E2E URLs, Tautological assertions, Ad hoc launcher script). Your failure taxonomy has 8 internal failure classes; this is the *external-contribution* equivalent — what gets bounced before merge.
- **External-maintainer pathway with quantitative + qualitative gates** — ≥20 merged PRs (soft floor) + 7-dim profile-quality rubric (≥5 of 7 admission lines, zero veto lines) + Core Team qualitative judgment + early-project waiver clause + auto-expiring inactive transition (90/60-day signals, 14-day response window) + Emeritus path with simple return (3 PRs in 30d). Reads like Apache governance distilled by someone who has tried it.
- **Localization as a CI gate** — `e2e/tests/localized-content.test.ts` enforces every skill has English fallback display for de/ru/fr. Skills with incomplete display copy fail typecheck.
- **PR-duty control plane (`pnpm tools-pr`)** — encodes repo-specific knowledge (review-lane derivation, forbidden-surface flags, per-lane checklists) as a thin `gh` wrapper. Read-only on the PR surface; never approves/merges/comments/closes. Maintainer tooling as code.

### Yours-only (they don't have this)

- **Four-layer capture stack** with discussions/ → SQLite → memory/ → vector substrate.
- **ADRs as immutable decision history** (Principle #5). Open Design has `docs/spec.md`, `docs/architecture.md`, but no never-deleted decision ledger.
- **Multi-specialist review with Values + Domain Lens** — Open Design's review lane is single-pass against a flat checklist; no multi-perspective dispatch.
- **Education gates** (walkthrough → quiz → explain-back). Open Design has no education-gate equivalent — they have a `merge bar` ([docs/skills-contributing.md:167](../../../../research_projects/open-design/docs/skills-contributing.md)) which is the same idea applied differently (educate the contributor *before* the PR opens, via the contributor guide).
- **Knowledge pipeline** (findings extraction, pattern mining, Rule of Three, agent effectiveness, promotion candidates).
- **Lineage tracking** with framework-lineage.yaml + Steward agent.
- **Memory substrate** (assertion_store + MCP transport).
- **Retro / meta-review loops** (micro / meso / macro).
- **Reasoning-capture infrastructure** at the layer Open Design simply doesn't attempt — they capture artifacts, not reasoning.

---

## 3. Strengths Your Framework Holds Up Under Contact

1. **Reasoning capture remains the differentiator.** Open Design has a sophisticated knowledge substrate (skills + design-systems + craft) but zero reasoning-capture infrastructure. Their `auto-memory store` in 0.7.0 (CHANGELOG: "agents accumulate durable context across runs and projects") is a step toward what you have, but it's session-state persistence, not deliberation capture. Principle #1 (reasoning is the primary artifact) holds.

2. **Specialist values diversity remains genuinely unique.** Open Design's review lanes (default / contract / design-system / skill / craft) are filter-by-type, not perspective-by-type. Their critique skill scores 5 dimensions but does so from one design-aesthetic voice. Your facilitator + 10 specialists with distinct Values blocks produce dissent of the kind preserved in DISC-20260516-050945. Open Design's review process — even at 1001 commits — captures correctness through a single perspective. Yours captures it through coopetition.

3. **Lineage tracking and framework evolution path holds against an active OSS comparator.** Open Design is at 0.8.0-preview with no equivalent of `framework-lineage.yaml` or upstream/downstream drift tracking. Their evolution is unidirectional (Core Team decides). Yours preserves derived-project → template propagation as a designed event class. Where Open Design has more contributors, you have more *protocol* for how patterns become institutional.

4. **Multi-language localization is *their* strength, not yours — but at your scale it's not yet a gap.** Open Design supports 18 locales (their i18n test). You support one. The asymmetry is real, but the deliberate-choice frame applies (cf. comparison-01-superpowers.md §4.7 cross-harness lock-in): your template is for a single developer producing derivatives, not a public OSS product. Worth being explicit about — when a derivative ships externally, the localization gap becomes operational.

5. **External project analysis pipeline still earns its keep.** You analyzed Open Design; Open Design's CHANGELOG cites four upstream open-source shoulders ([huashu-design][hd], [guizang-ppt][gp], [open-codesign][oc], [multica][mu]) but has no structured cross-project pattern-mining infrastructure. Their adoption is *credit*; yours is *adoption log + Rule of Three + threshold rubric*. The contrast affirms Principle #3 (collaboration precedes adversarial) at the methodology-discovery level.

---

## 4. Weaknesses This Comparison Exposes

Ordered by what would actually move the framework if addressed.

### 4.1 No declarative per-skill context injection — your skills are loaded whole

Open Design's skills declare `od.craft.requires: [typography, color, anti-ai-slop]` in frontmatter; the daemon injects only those craft sections. A skill that needs only typography pays no token cost for color/motion content. Your skills are loaded whole into context; your rules likewise. **For a methodology-publishing framework whose derivatives pay the inherited surface cost on every session, this is a real architectural gap.**

The structural craft observation: the per-skill `od.craft.requires` pattern is *Principle #8 (least-complex intervention) operationalized in the system-prompt assembly layer*. You don't have that layer — your assembly is "auto-load everything documented in the framework manifest". This compounds across derived projects (Insight Journal, VerificationPortal, future Howie).

**Maps to**: §5.2 Pattern 1 — Path A staging candidate. Path A's skills investment direction would benefit from a compositional-injection mechanism similar to `od.craft.requires` rather than auto-loading all skills equally.

### 4.2 No mid-emission self-critique loop

Open Design's critique skill is designed to run on the agent's own output *before* the artifact is emitted to the user (see [design-templates/critique/SKILL.md:46-48](../../../../research_projects/open-design/design-templates/critique/SKILL.md): "As a self-check loop the agent can run on its own output before emitting it"). Your `/review` runs *after* the code is written, gated to commit time. The build-review-protocol mid-build checkpoint is closer but still uses dispatched specialists, not a self-applied checklist.

The 5-Dimension Critique pattern with anti-grade-inflation rules is a structural craft contribution your framework lacks at the *self-check* layer: agents emit their reasoning + work, but no canonical "score-your-own-output-on-these-5-dimensions-with-evidence-citation" discipline lives in your skills.

**Maps to**: §5.2 Pattern 2 — adopt above threshold for the adoption-rubric domain. Could enrich the existing 5-dim adoption rubric with anti-inflation discipline.

### 4.3 No "forbidden surfaces" canonical block-list

Open Design's [code-review-guidelines.md §2](../../../../research_projects/open-design/docs/code-review-guidelines.md) enumerates twelve recreated-pattern violations that close-on-sight ("Root lifecycle aliases: `pnpm dev`, `pnpm dev:all`, ...", "Cross-app private imports", etc.). Your framework has Principles (what to do) and a Failure Taxonomy (what breaks at run time), but no equivalent **named-violation-pattern block-list** that closes PRs before specialist review.

The gap: your principles operate at *what-to-aspire-to* granularity; their forbidden surfaces operate at *what-not-to-recreate* granularity. The two are complementary, not duplicates. Without the latter, your /review specialists relitigate the same architectural violations across discussions.

**Maps to**: §5.2 Pattern 3 — adopt above threshold. A `.claude/rules/forbidden_surfaces.md` enumerating named violations would be drop-in additive.

### 4.4 Your principles are aspirational; their checklists are operational

Reading the merge bar in [docs/skills-contributing.md:167-202](../../../../research_projects/open-design/docs/skills-contributing.md) against your Principle #6 ("Education gates before merge"):

Their merge bar gates concrete failures: `example.html is hand-built`, `No AI slop in the example`, `Honest placeholders`, `references/checklist.md exists with at least P0 gates`, `example_prompt actually works (run it locally end-to-end)`, `Triggers are concrete (not "design something cool")`, `Single self-contained folder`, `No CDN imports beyond what other skills already use`, `No images larger than ~250 KB`, `No fonts you didn't license`, `Slug is ASCII, kebab-case`.

Your education gate gates *whether the developer understood the change*. Both are valid; theirs is *operationally enforceable* in a way yours is not (because yours is about cognitive uptake, theirs is about artifact compliance).

The structural observation: **Principle #6 in v4's Option C carve-out form (Decision Rationale Capture) is the right reframe for your single-developer-managing-non-coder-decisions audience, but the merge bar as a separate concept does not yet exist in your framework**. Adoption-log entries pass through Rule of Three but not through an Open Design-style merge bar.

**Maps to**: §5.4 Structural-Craft Contribution — observation-only; v4 already evolves Principle #6 and a separate "merge bar" would compete with that work.

### 4.5 Your surface is centralized; theirs is compositional

Your framework loads `CLAUDE.md` + `FRAMEWORK.md` + auto-loaded rules + all skills + auto-loaded agent definitions on every session. Open Design's daemon (`apps/daemon/src/skills.ts`) parses skill frontmatter and injects only the resolved subset. **The architectural difference is that your assembly happens at file-system load time; theirs happens at request-routing time.**

The implication: as your framework's surface grows (Path A skills investment will grow it more), the assembly model becomes the bottleneck. Open Design's *compositional* model accommodates a 293-entry catalog because nothing is loaded by default — entries are pulled in by skill declaration. Your model accommodates a ~50-entry catalog comfortably; beyond that, derived projects pay the inherited surface cost.

**Maps to**: §5.4 Structural-Craft Contribution. This is a framework-architecture observation that may not warrant a Sprint-1 adoption but is worth surfacing as a long-term constraint to think about when Path A's skills grow past ~20 entries.

---

## 5. Evolutionary Signals & Adoption Candidates

### 5.1 Principle Stress-Test

How Open Design stands against your 8 Non-Negotiable Principles:

| # | Principle | Open Design stance | Friction? | Signal |
|---|---|---|---|---|
| 1 | Reasoning is the primary artifact | **Disagrees by design** — the artifact (HTML deck/prototype) is the primary product; reasoning is in-session and discarded | Yes — fundamental | Your bet is preserved. Their bet works because the artifact is itself the design decision. Different problems. |
| 2 | Capture must be automatic | **Partial** — auto-memory store ships in 0.7.0 but is session-state, not deliberation capture | Compatible | Their auto-memory store is a derived-projects-only need; your assertion_store substrate already addresses it. |
| 3 | Collaboration precedes adversarial rigor | **Disagrees by omission** — review is single-perspective filtering, not multi-perspective coopetition | Yes | Your multi-specialist values diversity is genuinely differentiated; their PR governance is excellent but single-voice. |
| 4 | Independence prevents confirmation loops | **Partial** — maintainers approve, Core Team merges; reviewer ≠ author by structural rule | Compatible | Their structural separation matches your Principle #4. Different mechanism, same intent. |
| 5 | ADRs are never deleted | **No equivalent** — they have `docs/spec.md`, `docs/architecture.md`, RFC drafts in `docs/rfc-drafts/`, but no never-deleted decision ledger | Neutral | Your differentiator. Their long-form docs evolve; your ADRs accrete. |
| 6 | Education gates before merge | **Different mechanism** — Skills Merge Bar (educate the contributor BEFORE PR opens via skills-contributing.md and Common Reasons We Close PRs appendix) | Yes — different leverage point | They educate contributors upfront via discoverable checklists; you educate the developer mid-flight via quiz. Their model fits their audience (volunteer contributors); yours fits yours (non-coding manager). |
| 7 | Layer 3 promotion requires human approval | **Compatible** — Core Team holds merge button regardless of approvals | Compatible | Their MAINTAINERS.md structurally enforces this for code, your /promote does it for knowledge. |
| 8 | Least-complex intervention first | **Strongly agrees at compositional level** — `od.craft.requires` is the substrate-level expression of Principle #8 (pull only what's needed) | Yes — your framework lacks an equivalent assembly layer | Their compositional context injection is what Principle #8 looks like operationalized in the prompt-assembly layer. You have nothing equivalent. |

**Five principles are stress-tested: #1, #3, #4, #6, #8.** #1 and #3 are validated by what Open Design omits. #4 is reflected, not refuted, at a different mechanism. #6 has a different leverage point worth thinking about (educate the contributor upfront via skills-contributing.md analogues, not just the developer mid-flight via quiz). #8 is the most consequential — Open Design's compositional substrate is what your framework lacks at the assembly layer.

### 5.2 Adoption Candidates — v4-Aligned

#### Pattern 1: `od.craft.requires` declarative context injection per skill

**Score: 21/25** — **Path A staging — adopt only when Path A's skills count grows past ~10-15 entries**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | Pattern of opt-in context references is seen in MCP and some skill frameworks; the declarative-frontmatter implementation is distinctive |
| Elegance | 5 | YAML frontmatter declares dependencies; daemon assembles at request time. Light, composable, forward-compatible (unknown values silently ignored) |
| Evidence | 5 | Shipped in production Open Design with 1001 commits, 133 skills using it, 11 craft files referenced |
| Fit | 3 | Requires a request-time assembly layer in your framework that does not yet exist. Could ship without it as a documentation convention but the leverage is in the assembly |
| Maintenance | 5 | Markdown + YAML; low ongoing cost once the assembly is built |

**Status note**: Above threshold but **Path A staging** rather than Sprint 1, because the substrate change to add a per-skill compositional-injection mechanism is *itself* a Principle #8 escalation (from prompt change → tooling change). Worth scoring now and re-visiting when Path A's skills count grows past ~10-15 — at that point your derived projects begin paying inherited surface cost the compositional model would mitigate.

**Action**: When Path A skills count grows past ~10-15: design a `requires:` frontmatter field in your skills, build a request-time assembler in the dispatch path (or via a SessionStart hook variant), document the forward-compatibility ("unknown values silently ignored") posture.

#### Pattern 2: 5-Dimension Critique Discipline with anti-grade-inflation rules

**Score: 20/25** — **Adopt above threshold — enriches existing 5-dim adoption rubric**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | The 5-dim scoring pattern is widespread; the anti-grade-inflation discipline ("don't average up", "innovation is allowed to be low") is distinctive |
| Elegance | 4 | Four explicit rules in a "Scoring discipline (read before you score)" section; clean separation between scoring procedure and anti-rationalization |
| Evidence | 4 | Shipped as a production skill, distilled from huashu-design's expert-critique flow, validated through 0.7.0 / 0.8.0-preview cycles |
| Fit | 5 | Your 5-dim adoption rubric (prevalence / elegance / evidence / fit / maintenance) is structurally identical; the anti-inflation discipline is drop-in additive |
| Maintenance | 4 | Add 4 sentences to `.claude/skills/adoption-rubric/SKILL.md` (does not exist yet) or to the project-analyst agent prompt |

**Status note**: The structural rhyme between their 5-dim critique and your 5-dim adoption rubric is exact. The anti-grade-inflation rules ("don't average up — the score is the worst sustained band"; "if every score is 7+, you're not reviewing critically"; "evidence per score — no 'feels off'") are technique your adoption rubric does not currently carry. The project-analyst agent has had its scoring drift toward grade inflation in prior comparisons (multiple scores ≥4 with similar rationales) — this is the discipline that would prevent it.

**Action**: Add an explicit "Scoring discipline" subsection to `.claude/agents/project-analyst.md` Domain Lens. Wording: *Don't average up — score the worst sustained band, not the kindest one. Cite evidence for every score; "feels right" is not evidence. Overall mean above 4.0/5 across all five dimensions is suspicious; check yourself. Innovation/fit is allowed to be low — don't punish appropriate conservatism.*

#### Pattern 3: Forbidden Surfaces — canonical named-violation block-list

**Score: 20/25** — **Adopt above threshold — additive complement to Failure Taxonomy**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 3 | "Banned-pattern" lists exist in style guides; the close-on-sight enforcement tier is distinctive |
| Elegance | 4 | Twelve named violations, each with a concrete pattern; runs *before* implementation review |
| Evidence | 4 | Shipped in production; the Appendix "examples of failed product-relevance reviews" gives concrete close-reasons |
| Fit | 5 | Drop-in additive — would live at `.claude/rules/forbidden_patterns.md`, parallel to existing `failure_taxonomy.md` |
| Maintenance | 4 | Grows slowly; new entries land when a /review or /retro identifies a recurring violation |

**Status note**: Your Failure Taxonomy enumerates 8 run-time failures (HOOK_BLOCK, QUALITY_GATE_FAIL, etc.). The Forbidden Surfaces pattern enumerates *what not to write* (e.g., "Subagents trying to spawn other subagents", "Bypassing /review for code changes >5 framework files", "Writing to memory/ without /promote", "Hardcoded model tier overrides outside facilitator"). The Failure Taxonomy is reactive; Forbidden Surfaces is preventive. They complement.

**Action**: Create `.claude/rules/forbidden_patterns.md` enumerating 6-10 named violations the framework already implicitly bans but doesn't enumerate (Steward dispatching agents; subagent recursion; `/promote` without human gate; ADR deletion vs. supersession; `memory/` direct writes; `discussions/` sealed-directory edits; `evaluation.db` Write; etc.).

#### Pattern 4: External-maintainer pathway with quantitative + qualitative gates

**Score: 16/25** — **Below threshold for now; re-score when first non-developer contributor lands**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 4 | Standard pattern in mature OSS (Apache approver model, K8s SIGs, Mozilla peers) |
| Elegance | 4 | Three explicit criteria + 7-dim sock-puppet rubric + Emeritus path + early-project waiver |
| Evidence | 5 | Documented in shipping MAINTAINERS.md v1, drafted 2026-05-11, in active use |
| Fit | 1 | Single-developer framework today; this is for-future-team infrastructure with no current consumer |
| Maintenance | 2 | Process documents drift if not exercised; an unenforced governance doc is worse than none |

**Status note**: Worth knowing this exists; below threshold for current adoption because there is no second human contributor yet. Re-score when Howie or a third human collaborator joins.

#### Pattern 5: Auto-checked vs. guidance enforcement tiers

**Score: 18/25** — **Below threshold but worth keeping as a documentation discipline**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 2 | Distinctive; few frameworks explicitly label which rules the linter actually checks vs. which are guidance |
| Elegance | 4 | Single inline tag `(guidance, not auto-checked)` on each guidance rule keeps the contract honest |
| Evidence | 3 | New pattern; in production but not battle-tested at year-scale |
| Fit | 5 | Could drop into your existing rules — e.g., in `quality_gate.py` checks vs. `.claude/rules/*` rules |
| Maintenance | 4 | Light annotation; the discipline is in the labeling consistency |

**Status note**: Below the 20/25 threshold but worth folding into your `Known Limitations` section in CLAUDE.md when documenting rules — annotate which are automation-enforced (hooks, quality_gate.py) vs. agent-prompt-enforced (specialist Values blocks, rule text). Closes a small honesty gap.

#### Pattern 6: PR-duty tooling (`pnpm tools-pr`) as a read-only encoded-knowledge control plane

**Score: 14/25** — **Below threshold; not portable**

| Dim | Score | Rationale |
|---|---|---|
| Prevalence | 2 | Their tools-pr is bespoke to multi-contributor OSS scale; not seen in template frameworks |
| Elegance | 4 | Read-only on PR surface; encodes repo-specific knowledge as a thin gh wrapper; classify tags use a fixed dictionary |
| Evidence | 3 | In production but new |
| Fit | 1 | No PR queue to triage in your single-developer framework; the tool is for a problem you don't have |
| Maintenance | 4 | Bash + gh CLI; light |

**Status note**: Cited for completeness. Re-score if your framework ever spawns a contribution surface beyond derived projects.

### 5.3 Verdict Tally — v4-Aware

- **Adopt above threshold** (2):
  - Pattern 2 (5-dim critique anti-grade-inflation rules) — add to project-analyst Domain Lens
  - Pattern 3 (Forbidden Surfaces named-violation block-list) — new `.claude/rules/forbidden_patterns.md`
- **Path A staging** (1):
  - Pattern 1 (`od.craft.requires` declarative injection) — adopt when skills count grows past ~10-15
- **Below threshold** (3):
  - Pattern 4 (external-maintainer pathway) — re-score when second human contributor lands
  - Pattern 5 (auto-checked vs. guidance enforcement tiers) — light documentation discipline; fold into rule annotations
  - Pattern 6 (PR-duty tooling) — not applicable to single-developer framework
- **Structural-craft contributions** (3): see §5.4

**v4 alignment**: v4 has zero Sprint-1 commitments to Open Design patterns (the recovered ANALYSIS produced only one 19/25 score). This document adds two above-threshold patterns (3 and 2) that are below the v4-Sprint-1 ceiling but represent genuine drop-in adds. Neither overrides a deliberated v4 position; both should land as additive supplements to Sprint 1 work.

### 5.4 Structural-Craft Contributions — Findings v4 Does Not Have

#### Contribution 1: Your framework lacks a compositional context-injection substrate

**Frame**: Open Design's `od.craft.requires` is *Principle #8 (least-complex intervention) operationalized at the prompt-assembly layer*. Each skill declares its dependencies; the daemon resolves them per-request; nothing is loaded by default. Your framework's assembly model is "auto-load everything in the framework manifest at session start" — by Path A's projected skills count, this will compound across derived projects.

The architecture observation: as the framework's catalog grows, the *consumer* (derived project) pays the inherited surface cost on every session. A compositional substrate (per-skill `requires:` frontmatter + a request-time assembler) shifts the cost from sessions to the skill author. Open Design has 133 skills + 11 craft files + 149 design systems — 293 entries — because no single session loads them all. Your framework will hit a wall before reaching 50 entries because every session loads everything.

This is not a Sprint-1 adoption recommendation. It is an architectural observation that should inform Path A's skills investment design: build the assembly mechanism in parallel with the first skills, not after.

#### Contribution 2: Your principles are aspirational; their checklists are operational at a different layer

**Frame**: Reading Open Design's [docs/skills-contributing.md §5 Merge Bar](../../../../research_projects/open-design/docs/skills-contributing.md) against your Principle #6 (Education gates before merge):

Their merge bar gates *artifact compliance*: example.html is hand-built, no AI slop, honest placeholders, references/checklist.md exists, example_prompt actually works, triggers are concrete. Your education gate gates *developer comprehension*: walkthrough, quiz, explain-back.

Both are valid leverage points. v4's Option C carve-out is the right reframe for your audience (non-coding manager). But the merge-bar concept — **operationally checkable gates on the contributed artifact itself** — is missing from your framework as a separate concept.

This is not a duplicate of Principle #6 (which is about the decision-maker), nor of Quality Gate (which is about the code). It's a third tier: *the artifact has to satisfy operationally-checkable rules before it ships*. Your adoption-log entries pass Rule of Three; their skills pass the merge bar. These are not the same gate.

**The structural observation**: Path A's skills investment will eventually need its own merge bar — operational criteria for what makes a skill mergeable into the framework template (vs. usable only in a derived project). When that work happens, lift the structure from Open Design's [skills-contributing.md §5](../../../../research_projects/open-design/docs/skills-contributing.md) directly.

#### Contribution 3: Your governance is upstream-only; their governance has a downstream-contribution lane

**Frame**: Your framework's evolution path (CLAUDE.md §Framework Evolution) goes Observation → Proposal → Steward Gate → Developer Approval → Review. **All five steps assume the developer is the contributor.** There is no path for a contribution to land from a derived project, much less from a third party.

Open Design's MAINTAINERS.md operationalizes a downstream-contribution lane — External Maintainer with structural permission gates, an approval that counts as the required merge approval, an Emeritus path, an early-project waiver, an automatic-inactivity transition. The point is not the rubric details; it's that **a contribution-from-outside lane is a designed concept, not an absence**.

You don't currently have a non-developer contributor — but you have derived projects (Insight Journal, VerificationPortal) that *should* contribute back upstream when patterns survive two-project independence. v4 explicitly defers `conversation`/`status` canonicalization on the grounds that 2-of-2 from one developer is correlated. **But the absence of a downstream-contribution lane means even if the 2-of-2 were independent, there's no defined mechanism for the contribution to land.** The steward agent + lineage tracking (`upstream_promotion_candidate` event class, deferred per v4 steward turn 2) are the right primitives — they're just not wired into a *human governance lane*.

**The implication for Path A**: when designing the `upstream_promotion_candidate` event class, also design the human-side lane it triggers. Open Design's three-criteria External Maintainer model is the structural rhyme worth borrowing from — even at single-derived-project scale, the question "*who* approves a derived → template promotion, and by *what* qualitative bar?" is unanswered in your framework today.

### 5.5 Meta-Questions for Framework Evolution

These are observations Path A's design decisions will eventually need to engage with.

1. **At what scale does your assembly model break?** Your current ~32-entry catalog (14 rules + 6 skills + 12 agents) loads cleanly. Path A roughly doubles skills. At ~50 entries the inherited-surface cost compounds; at ~100 (Open Design-scale) it becomes operational drag on every derived-project session. **Decide now whether to build the compositional substrate during Path A's first 5 skills or after** — building it after means rewriting skill frontmatter for entries already in production.

2. **Operational checklists are not the same artifact class as principles or rules.** Your framework has principles (CLAUDE.md), rules (.claude/rules/), agent definitions (.claude/agents/), commands (.claude/commands/), skills (.claude/skills/), and hooks (.claude/hooks/). It does not have a *checklist artifact class* — concrete, gated, operationally checkable, parallel to (not subsumed by) the principles and rules. Open Design's merge bar is a checklist; their craft-file "Common mistakes (lint these)" sections are checklists; their PR-template `Surface area` checkboxes are checklists. Worth considering whether your framework should add `.claude/checklists/` as a sibling to `.claude/rules/`.

3. **The substrate-vs-product distinction.** Your framework is *substrate that spawns products*. Open Design is *product that ships substrate*. The asymmetry is real: their craft/skills/design-systems substrate is in-tree with the product because they ship together. Your substrate has to be portable across derived projects, which means it can't have product-tied assumptions baked in. This is a constraint v4 doesn't make fully explicit — yours is a *traveling substrate*, theirs is a *bundled substrate*. The constraint shapes which Open Design patterns are portable (the abstractions: declarative-injection, anti-grade-inflation, forbidden-patterns) and which aren't (the concretes: their craft-file content, their design-system entries).

4. **The "describe what's banned" gap.** Your Principles say what to aim for; your Failure Taxonomy says what breaks at run time; you don't have a layer that says **here are named pre-commit / pre-merge architectural violations we close-on-sight**. Pattern 3 (Forbidden Surfaces) closes this. Worth asking whether the gap exists for the same reason your framework hasn't run /retro in 68 days (history-analyst turn 12 in DISC-20260516-050945) — both gaps are *self-discipline-of-the-template-itself* gaps. Patterns to enumerate violations are easier to articulate when the friction of recurring violations has been felt.

---

## 6. Open Tasks Surfaced by This Document

| Task | Owner | Sequencing |
|---|---|---|
| Adopt: anti-grade-inflation discipline in project-analyst Domain Lens | framework developer | Sprint 1 additive, low cost |
| Adopt: `.claude/rules/forbidden_patterns.md` with 6-10 named violations | framework developer | Sprint 1 additive, draft from existing implicit bans |
| Design: compositional-injection substrate (per-skill `requires:` frontmatter + request-time assembler) before Path A skills count reaches ~10 | framework developer | Path A — early architecture decision |
| Consider: `.claude/checklists/` as a sibling artifact class to `.claude/rules/` | framework developer | Path A — design decision |
| Consider: human-side downstream-contribution lane to pair with `upstream_promotion_candidate` event class | steward + framework developer | Sprint 3 (post-Tier-0, post-Tier-1, when `upstream_promotion_candidate` enacts) |
| Re-score Pattern 4 (external-maintainer pathway) when second human contributor lands | framework developer | Triggered by contributor signal |
| Re-score Pattern 5 (auto-checked vs. guidance enforcement tiers) when rules are next audited | framework developer | Whenever rules audit happens |

---

## Appendix: What I Didn't Examine

For honesty about scope:
- The 133 skills' SKILL.md bodies (read [design-templates/critique/SKILL.md](../../../../research_projects/open-design/design-templates/critique/SKILL.md) and [skills/design-review/SKILL.md](../../../../research_projects/open-design/skills/design-review/SKILL.md); skimmed structures of others)
- The 149 design-systems' DESIGN.md content
- The 11 craft files beyond `README.md`, `state-coverage.md`, `anti-ai-slop.md`, `accessibility-baseline.md`, opening of `laws-of-ux.md`
- The `apps/` source code (`apps/daemon`, `apps/web`, `apps/desktop`, `apps/packaged`)
- The `packages/contracts`, `packages/sidecar-proto`, `packages/sidecar`, `packages/platform` boundary code
- The `tools/dev`, `tools/pack`, `tools/pr` tooling internals
- The `e2e/` test architecture beyond skim of the localization test reference
- The Nix flake (`flake.nix`, `flake.lock`, `nix/`)
- The CHANGELOG beyond the 0.7.0 section
- The `prompt-templates/` (93 entries: 43 gpt-image-2 + 39 Seedance + 11 HyperFrames)

If a future pass needs more granularity on any of these, they're at `C:/Work/AI/research_projects/open-design/`.

[hd]: https://github.com/alchaincyf/huashu-design
[gp]: https://github.com/op7418/guizang-ppt-skill
[oc]: https://github.com/OpenCoworkAI/open-codesign
[mu]: https://github.com/multica-ai/multica
