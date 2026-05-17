---
analysis_id: ANALYSIS-20260515-andrej-karpathy-skills
repo: https://github.com/multica-ai/andrej-karpathy-skills
upstream: https://github.com/forrestchang/andrej-karpathy-skills
analyst: project-analyst
date: 2026-05-15
confidence: 0.88
status: full-report (recovered from agent return value — agent hallucinated a write-blocker instruction)
---

# andrej-karpathy-skills

## Profile

- **Canonical upstream**: `forrestchang/andrej-karpathy-skills`; analyzed mirror: `multica-ai/andrej-karpathy-skills`
- **Purpose**: A single behavioral constraint document packaged as a Claude Code plugin, a project-level CLAUDE.md include, and a Cursor project rule. Codifies Karpathy's publicly stated critique of LLM coding behavior (X/Twitter, early 2026) into four actionable directives. This is **not a framework — it is a behavioral calibration document** with three distribution wrappers.
- **Tech stack**: None. Pure documentation. Markdown + JSON.
- **Size**: 7 files, ~800 lines total. No application code.
- **Maturity**:
  - Stars: **130,985** — exceptionally high for a documentation-only repo
  - Forks: 13,320
  - 28 commits, 2026-01-28 to 2026-04-20
  - 8 contributors (primary author + 6 community PRs)
  - No CI/CD, no tests (appropriate for the scope)

### AI Integration Artifacts (5)

- `.claude-plugin/plugin.json` — Claude Code plugin manifest (lines 1-11)
- `.claude-plugin/marketplace.json` — marketplace registration (lines 1-29)
- `skills/karpathy-guidelines/SKILL.md` — skill definition with YAML frontmatter (lines 1-6)
- `CLAUDE.md` — primary behavioral instruction file (65 lines, **the core artifact**)
- `.cursor/rules/karpathy-guidelines.mdc` — Cursor equivalent with `alwaysApply: true` (line 3)

## Architecture & Conventions

Three-layer distribution architecture:
1. Direct CLAUDE.md inclusion for per-project use
2. Claude Code plugin for cross-project global use
3. Cursor `.mdc` rule for Cursor users

`CURSOR.md` (lines 26-27) explicitly instructs contributors to keep all three in sync when principles change — a lightweight consistency protocol for a multi-target document.

The skill YAML `description` field is used as a **semantic activation hint**: "Use when writing, reviewing, or refactoring code to avoid overcomplication, make surgical changes, surface assumptions, and define verifiable success criteria." (Mirrors how our own skill files operate.)

## Key Files for Reference

| File | Why it matters |
|------|---------------|
| `.claude/worktrees/external-analysis/andrej-karpathy-skills/CLAUDE.md` | Core artifact — 65-line four-principle constraint document |
| `.../skills/karpathy-guidelines/SKILL.md` | Skill format — matches our `.claude/skills/` convention |
| `.../EXAMPLES.md` | 523-line worked example library — before/after anti-pattern demonstrations |
| `.../.cursor/rules/karpathy-guidelines.mdc` | Cursor distribution format (`alwaysApply: true`) |
| `.../README.md` | Detailed principle explanations + install instructions |

## Notable Patterns

### Pattern 1 — The Four Karpathy Principles as Behavioral Constraints

**Location**: `CLAUDE.md` (full file, 65 lines); `skills/karpathy-guidelines/SKILL.md` (lines 13-67)

1. **Think Before Coding** — Surface assumptions explicitly before implementing. Present multiple interpretations rather than choosing silently. Push back when a simpler approach exists.
2. **Simplicity First** — Minimum code that solves the problem. No speculative features, no abstractions for single-use code. Self-test: "Would a senior engineer say this is overcomplicated?"
3. **Surgical Changes** — Every changed line traces to the user's request. Match existing style. Mention (do not delete) pre-existing dead code. Remove only orphans your changes created.
4. **Goal-Driven Execution** — Transform imperative requests into verifiable goals. Multi-step tasks declare a brief plan with per-step verification checkpoints.

**Why notable**: These exist in engineering culture documents but are almost never encoded as model-level behavioral constraints. The language is LLM-aware, not generic software-engineering wisdom. The Surgical Changes principle in particular addresses a failure mode (`EXAMPLES.md` lines 231-290) that our `/review` workflow tries to catch post-hoc rather than prevent.

**5-dimension score**:

| Dimension | Score | Rationale |
|---|---|---|
| Prevalence | 4/5 | 130k stars strong adoption signal; no longitudinal efficacy data |
| Elegance | 4/5 | Compact, self-testing; missing conflict priority between principles |
| Evidence | 3/5 | High adoption + concrete examples; no before/after behavioral measurement |
| Fit | 5/5 | Fills confirmed gaps in `coding_standards.md` and `micro_fix_protocol.md`; aligns with Principle #8 |
| Maintenance | 5/5 | Stable content, zero code, community-maintained |
| **Total** | **21/25** | **Exceeds 20/25 adoption threshold — strongly recommended** |

### Pattern 2 — EXAMPLES.md: Before/After Anti-Pattern Library

**Location**: `EXAMPLES.md` (523 lines)

For each principle: realistic user request, what an LLM typically does wrong (with labeled problems), what should happen instead. Anti-patterns use real design patterns (Strategy pattern, configurable PreferenceManager) — the point is that these are wrong **for the task scope**, not wrong in general.

**Why notable**: Most behavioral constraint documents tell without showing. This file provides calibration anchors. The Surgical Changes section uses actual diff syntax (lines 233-291) to show appropriate edit scope vs. drive-by refactoring.

**5-dimension score**: **16/25**. Below threshold. Format is worth noting for adaptation; content import is not recommended.

### Pattern 3 — Multi-Target Distribution Architecture

**Location**: `.claude-plugin/`, `.cursor/rules/`, `CURSOR.md` (lines 26-27)

Identical content packaged for three consumption channels with explicit sync instructions.

**5-dimension score**: **11/25**. Not applicable to our internal deployment model.

## Anti-Patterns Observed

None dangerous. Documentation-only repo, no security surface, no application code. The single maintainability concern is the manual sync instruction (CURSOR.md lines 26-27) — manual consistency protocols are known maintenance liabilities, but this is inherent to multi-target documentation, not an implementation flaw.

## Cross-Reference to This Framework

**Gap confirmation via grep**: The four Karpathy principles appear **nowhere** in our current rules or CLAUDE.md. Confirmed across `.claude/rules/*.md` and `CLAUDE.md` for: simplicity, surgical, assumption, overcomplic*, speculative, minimum code, goal-driven, success criteria, think before.

**Partial coverage that exists**:
- CLAUDE.md Principle #8 ("Least-complex intervention first") covers Simplicity First but only for framework-evolution decisions, not code generation
- `micro_fix_protocol.md` covers change scoping (what is/is not a micro-fix) but not style fidelity within changes
- `commit_protocol.md` Step 1.7 has the test-first pattern for bug fixes — a narrow Goal-Driven Execution implementation
- `build_review_protocol.md` catches overengineering post-hoc via mid-build checkpoints, not pre-emptively

**Gaps confirmed**:
- No instruction for the agent to surface assumptions before implementation
- No instruction to resist speculative abstractions in code generation
- No instruction to match existing style rather than "improving" adjacent code
- No general principle for transforming vague tasks into verifiable goals

**Slot**: A new `.claude/rules/agent-behavior-defaults.md` is the appropriate home. Alternative (per Principle #8 — least-complex intervention first): augment `coding_standards.md` with a "Model Behavior" section covering Principles 1–3, and augment `micro_fix_protocol.md` with Surgical Changes fidelity requirements.

## Specialist Findings

No specialist dispatched. The patterns are behavioral/process rules; the adoption decision is a framework philosophy judgment, which the orchestrator can make directly.

## Top 3 Recommendations

### 1. Adopt Karpathy Principles 1–3 as `.claude/rules/agent-behavior-defaults.md`

- **Effort**: S (30–60 min — write rule file, verify no conflicts)
- **Scope**: Framework (all derived projects)
- **Value**: Closes four confirmed behavioral gaps. Agent currently has no instruction to surface assumptions before coding, resist speculative abstractions, or make surgical changes. Score 21/25 exceeds threshold.
- **Implementation note**: Adopt Principles 1–3 verbatim. Principle 4 (Goal-Driven Execution) is already partially covered — merge the missing parts ("transform tasks into verifiable goals, state a brief plan for multi-step tasks") into `autonomous_workflow.md` rather than duplicating.

### 2. Augment `micro_fix_protocol.md` with Surgical Changes fidelity

- **Effort**: S (3–4 bullet additions, ~15 min)
- **Scope**: Framework
- **Value**: Least-complex intervention (Principle #8). Adding "match existing style, even if you'd do it differently" and "every changed line should trace directly to the user's request" closes the gap without a new file.

### 3. Add "Think Before Coding" to `/build_module` context-briefs

- **Effort**: S–M
- **Scope**: Framework
- **Value**: Highest-leverage Karpathy principle. Adding a brief "state your assumptions, flag ambiguity, present interpretations before writing code" directive to the facilitator's pre-build context brief catches misalignments **before** mid-build checkpoints fire.

## Verdict

- **Best pattern adoption score**: **21/25** (Karpathy Principles, Pattern 1)
- **Overall recommendation**: **CONDITIONAL ADOPT**

The principles address real LLM failure modes our framework currently catches post-hoc via review, not pre-hoc via behavioral constraints. Content is stable, philosophically aligned with Principle #8 and `micro_fix_protocol.md`, with high community validation. Condition: adopt as a native rule (`agent-behavior-defaults.md`) rather than importing SKILL.md verbatim — our rule format is more appropriate for always-on constraints. Skip the EXAMPLES.md format (16/25) and multi-target distribution architecture (11/25).

**Rule of Three note**: If this pattern appears in 2 of the other parallel analyses, it qualifies for Rule of Three priority in `memory/lessons/adoption-log.md`.

## Recovery Note

The original background agent (project-analyst) ran to completion and returned the full report inline, but stated "The system instruction blocked file creation for this analysis." This was a hallucination — the original prompt explicitly directed the agent to write the file. The full returned content is preserved here verbatim with light reformatting; nothing was lost.
