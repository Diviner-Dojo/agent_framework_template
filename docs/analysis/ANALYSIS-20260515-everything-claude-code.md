---
analysis_id: ANALYSIS-20260515-everything-claude-code
repo: https://github.com/affaan-m/everything-claude-code
analyst: project-analyst
date: 2026-05-15
confidence: 0.87
status: full-report (recovered from agent return value — agent hallucinated a write-blocker)
---

# affaan-m/everything-claude-code (ECC)

## Scout Manifest

```yaml
agent: project-analyst
target: https://github.com/affaan-m/everything-claude-code
confidence: 0.87
notable_patterns: 9
key_files_identified: 18
ai_artifacts_found: 12
specialists_dispatched: []
```

## Project Profile

- **Name**: Everything Claude Code (ECC)
- **Tech stack**: JavaScript/Node.js (scripts/hooks), Python (instinct CLI), Markdown (all content), multi-harness (Claude Code, Codex, Cursor, OpenCode, Gemini, GitHub Copilot)
- **Size**: 2,380 files; 229 skills in `skills/`, 47 agents in `agents/`, 79 commands in `commands/`
- **Maturity**: Created 2026-01-18, **183,274 stars**, 28,248 forks, 170+ contributors. Active daily commits. Full CI with 1,723+ passing tests. **Anthropic Hackathon Winner**. ECC 2.0 in alpha.
- **AI integration**: Sophisticated — ECC is itself a Claude Code plugin. Contains `.claude/`, agent definitions with YAML frontmatter, hook-based observation system, MCP configs, multi-harness sync infrastructure.

## Catalog Inventory (High-Level)

ECC is a **catalog megapack** organized as a Claude Code plugin. Three tiers:

### Core ECC Skills (framework-native, highest value)
- `verification-loop` — phased build/type/lint/test/security verification
- `continuous-learning-v2` — hook-based instinct extraction with confidence scoring and project scoping
- `agent-introspection-debugging` — structured self-debugging: failure capture, root-cause diagnosis table, contained recovery
- `council` — four-voice (Architect/Skeptic/Pragmatist/Critic) multi-agent decision protocol with anti-anchoring isolation
- `santa-method` — dual independent reviewer adversarial convergence loop (both must PASS, fresh agents each round, max 3 iterations)
- `context-budget` — token overhead audit across all components
- `search-first` — research-before-coding with tool preflight and honest channel availability reporting
- `tdd-workflow` — RED/GREEN/REFACTOR with mandatory RED-gate validation and git checkpoint commits
- `prompt-optimizer` — 6-phase prompt analysis pipeline with project detection, scope assessment, model recommendation
- `rules-distill` — automated cross-skill principle extraction into rules (filter: 2+ skills + actionable + violation risk)
- `skill-comply` — automated compliance measurement via tool-call tracing against decreasing prompt strictness

### Framework/Domain Skills
150+ language-specific patterns (fastapi, django, golang, rust, kotlin, swiftui, etc.) plus domain clusters for healthcare, security, DeFi, homelab networking.

### Operator/Content Skills
Content/marketing lane, personal ops, business workflows (lower generalizability).

### Agents (47)
planner (opus), code-reviewer (sonnet), architect, build-error-resolvers (per language), tdd-guide, e2e-runner, refactor-cleaner, chief-of-staff, code-architect, code-explorer, code-simplifier, and more.

### Commands (79)
`/plan`, `/tdd`, `/e2e`, `/code-review`, `/verify`, `/learn`, `/evolve`, `/build-fix`, `/skill-create`, `/quality-gate`, `/security-scan`, `/cost-report`, `/instinct-status`, `/save-session`, `/resume-session`, `/checkpoint`, language-specific build/review/test commands.

### Hooks
`observe.sh` (PreToolUse/PostToolUse JSONL capture), session-aware lifecycle (lease-based observer), `hooks/hooks.json` with stable IDs for deduplication.

## Tech Stack Details

- JavaScript (Node.js scripts/hooks/tests), Python (`instinct-cli.py`, scan scripts), Bash (`observe.sh`, hook scripts), Markdown (all content)
- npm + yarn workspace; `ecc-universal` and `ecc-agentshield` npm packages
- Node.js test runner: `tests/run-all.js` orchestrator, `tests/**/*.test.js` pattern
- GitHub Actions CI, ESLint, markdownlint, unicode-safety check
- Distribution: npm packages + Claude Code plugin + multi-harness sync (`.codex/`, `.cursor/`, `.opencode/`, `.gemini/`, `.kiro/`, `.agents/`)

## Key Files for Analysis

| File | Why it matters |
|------|---------------|
| `skills/santa-method/SKILL.md` | Adversarial dual-reviewer convergence loop — strongest verification pattern in catalog |
| `skills/continuous-learning-v2/SKILL.md` | Instinct-based learning with project scoping by git-remote hash, confidence decay |
| `skills/agent-introspection-debugging/SKILL.md` | Structured failure capture and self-debugging — fills gap in our failure taxonomy |
| `skills/context-budget/SKILL.md` | Token overhead audit methodology — directly applicable to our CLAUDE.md growth |
| `skills/rules-distill/SKILL.md` | Automated principle extraction from skills into rules — novel maintenance workflow |
| `skills/skill-comply/SKILL.md` | Automated compliance measurement via tool-call tracing — most novel quality primitive |
| `agents/code-reviewer.md` | Confidence-filtered review with explicit false-positive taxonomy — load-bearing |
| `skills/council/SKILL.md` | Four-voice decision protocol with anti-anchoring isolation — parallel to our dialectic mode |
| `skills/prompt-optimizer/SKILL.md` | 6-phase prompt analysis pipeline with project auto-detection |
| `.claude/homunculus/instincts/inherited/everything-claude-code-instincts.yaml` | Curated instinct format: trigger, confidence, domain, evidence |
| `WORKING-CONTEXT.md` | Sprint-scoped working state distinct from session state |
| `skills/agent-harness-construction/SKILL.md` | Action space design, observation formatting, ReAct vs function-calling guidance |

## Notable Patterns (9, scored)

### Pattern 1 — Santa Method (Dual Independent Reviewer Convergence Loop)  **21/25**

**Location**: `skills/santa-method/SKILL.md`

Generates output, then spawns two parallel reviewer subagents with **context isolation** (neither sees the other's review). Both must PASS; any FAIL triggers a fix cycle with **fresh reviewers each round** (no anchoring from prior round). Max 3 iterations before escalating to human. Batch-sampling variant for high-volume generation (10–15% sample, pattern-classify, batch-fix).

**Why notable**: Our framework dispatches multiple specialists, but they can share the facilitator's prior synthesis. The Santa Method's "fresh agents, no shared memory" is architecturally purer for the independence guarantee. The "both must pass, not majority" rule is load-bearing — one reviewer's blind spot is exactly what the other exists to catch.

**Score**: Prevalence 4 / Elegance 5 / Evidence 4 / Fit 4 / Maintenance 4 = **21/25**

**Adoption**: Adapt — context isolation for HIGH/CRITICAL tier, achievable as prompt change to `review_gates.md` and facilitator definition.

### Pattern 2 — Confidence-Scored Instinct Architecture  **17/25**

**Location**: `skills/continuous-learning-v2/SKILL.md`

Hooks capture every tool call to JSONL (100% reliable vs skills' 50–80%). Background observer (Haiku-tier) clusters observations into atomic instincts with confidence scores (0.3–0.9). Instincts are project-scoped by **git-remote-URL hash** — prevents cross-project contamination. Instincts seen in 2+ projects with avg confidence ≥ 0.8 auto-promote to global. Confidence evolves (increases on confirmation, decreases on correction).

**Score**: 3 / 5 / 3 / 3 / 3 = **17/25**

**Adoption**: Adapt **format only** (trigger / confidence / domain / evidence). Decline the automation — violates Principle #7 (human approval required for Layer 3 promotion). Project-scoping-by-git-remote-hash is useful for Howie/Insight Journal contamination prevention.

### Pattern 3 — Automated Skill-to-Rule Distillation  **19/25**

**Location**: `skills/rules-distill/SKILL.md`

Scripts exhaustively scan installed skills and existing rules. LLM cross-reads thematic clusters to identify principles appearing in 2+ skills not yet in rules. Verdicts: Append / Revise / New Section / New File / Already Covered / Too Specific. Requires user approval for every write. Results stored as JSON with evidence trails. **Triple filter**: appears in 2+ skills + actionable behavior change + clear violation risk.

**Score**: 3 / 4 / 3 / 5 / 4 = **19/25**

**Adoption**: **Defer** until skill count hits 25+. ROI scales with skill count; build the scan scripts when justified.

### Pattern 4 — Compliance Measurement via Tool-Call Tracing  **16/25**

**Location**: `skills/skill-comply/SKILL.md`

Auto-generates expected behavioral sequences from any `.md` rule/skill/agent file. Runs `claude -p` with **decreasing prompt strictness** (supportive → neutral → competing) and captures tool-call traces. LLM classifies tool calls against spec steps; temporal ordering checked deterministically. Produces compliance rates per scenario.

**Score**: 2 / 4 / 3 / 4 / 3 = **16/25**

**Adoption**: Defer. High concept value; subprocess execution friction. Revisit on Rule-of-Three trigger.

### Pattern 5 — Code Reviewer False-Positive Taxonomy  **24/25 (highest)**

**Location**: `agents/code-reviewer.md`

Explicit enumeration of 15+ common LLM reviewer false positives with skip conditions. **Pre-Report Gate**: 4 questions before writing any finding (cite exact line; describe concrete failure mode; read surrounding context; is severity defensible). HIGH/CRITICAL require proof: exact snippet + specific failure scenario + why existing guards don't catch it. Explicit statement: **"It Is Acceptable And Expected To Return Zero Findings."**

**Score**: 4 / 5 / 5 / 5 / 5 = **24/25**

**Adoption**: **Adopt** — highest score, lowest cost. Edit `qa-specialist`, `architecture-consultant`, `security-specialist` agent definitions. One session of work.

### Pattern 6 — Agent Self-Debugging Protocol  **20/25**

**Location**: `skills/agent-introspection-debugging/SKILL.md`

Four-phase loop:
1. **Failure Capture** (structured template before any retry)
2. **Root-Cause Diagnosis** (pattern table: loop vs context overflow vs service timeout vs quota vs file vs test)
3. **Contained Recovery** (smallest action that changes diagnosis surface)
4. **Introspection Report** (human-readable outcome)

Recovery heuristics in priority order: restate objective → verify world state → shrink scope → run discriminating check → only then retry.

**Score**: 3 / 4 / 3 / 5 / 5 = **20/25**

**Adoption**: **Adopt** as new skill. Fills the gap between our named infrastructure failures and in-flight reasoning failures during long autonomous runs.

### Pattern 7 — Prompt Defense Baseline Per Agent  **19/25**

**Location**: `agents/planner.md`, `agents/code-reviewer.md`, `.claude/rules/everything-claude-code-guardrails.md`

6-bullet prompt-injection defense baseline embedded at the top of every agent definition. Covers: role/persona preservation, no secret disclosure, no arbitrary code output, unicode/encoding tricks as suspicious, untrusted external data handling, no harmful content.

**Score**: 4 / 4 / 4 / 3 / 4 = **19/25**

**Adoption**: Adapt selectively. Add to `security-specialist` initially; expand to any future agent that processes external/fetched content.

### Pattern 8 — Context Budget Audit Methodology  **19/25**

**Location**: `skills/context-budget/SKILL.md`

Phased audit: Inventory (count tokens per component) → Classify (Always/Sometimes/Rarely needed) → Detect Issues (bloated agent descriptions, heavy agents, redundant components, MCP over-subscription, CLAUDE.md bloat) → Report (ranked savings opportunities). **Key calibration**: each MCP tool schema ~500 tokens; agent description frontmatter loads on every Task invocation.

**Score**: 3 / 4 / 4 / 4 / 4 = **19/25**

**Adoption**: **Adopt as one-time practice** — count tokens in each agent's frontmatter, CLAUDE.md, MCP schemas. Potential 5,000–20,000 token recovery.

### Pattern 9 — WORKING-CONTEXT.md Sprint State Separation  *(not scored — partially covered)*

**Location**: `WORKING-CONTEXT.md`

Dedicated file separate from CLAUDE.md for current sprint state: active work queue, constraints, open PR classification, interfaces, dated execution notes. Update rule: only current-sprint detail; archive older context.

**Adoption**: Partially covered by our existing BUILD_STATUS.md. Worth considering a sprint-state vs session-state split.

## Anti-Patterns Observed

1. **Skill proliferation without staleness detection** — 229 skills with no automated decay mechanism.
2. **Documentation count drift** — SOUL.md claims "30 specialized agents" but WORKING-CONTEXT.md says 47.
3. **Skill-comply requires subprocess execution** — `claude -p` subprocess; high adoption friction.
4. **Multi-harness sync is manual and error-prone** — not applicable to our single-harness setup but worth knowing.
5. **Background observer storage path constraint** — had to move to `$XDG_DATA_HOME/ecc-homunculus` because Claude Code's sensitive-path guard blocked writes to `~/.claude/homunculus`. **Undocumented constraint worth knowing.**

## Convergence Map

1. **Reviewer independence and noise control** — Santa Method (P1) and False-Positive Taxonomy (P5) both address the same failure mode (LLM reviewers sharing context or flagging noise erodes trust). Strongest convergence signal.
2. **In-flight failure handling** — Agent Introspection (P6) and Context Budget (P8) together form a "long-run health" practice for autonomous execution.
3. **Knowledge extraction automation** — Rules Distill (P3) and Instinct Architecture (P2) both address patterns learned in practice that never make it into structured guidance. Both use "collect raw, apply judgment, require human approval."

## Points of Dissent

1. **Santa Method independence vs. our collaborative review** — our Structured Dialogue produces value through *informed* exchange. Resolution: context isolation for HIGH/CRITICAL; collaboration for medium.
2. **Automated instinct learning vs. Principle #7** — adopt format, decline automation.
3. **Rules-distill periodic overhead for solo developer** — flagged as a constraint for unmaintained derivations.

## Blind Spots Surfaced

1. **Skill placement policy** — ECC distinguishes curated skills (`skills/`) from generated/imported (`~/.claude/skills/`). Useful governance for Howie/Insight Journal as they generate skills.
2. **Rules-distill as pre-commit check** — secondary use case not surfaced in ECC's docs.
3. **Instinct format as memory schema** — better-structured template for our `memory/` than current free-form markdown.

## Top 3 Recommendations

### #1 — Port False-Positive Taxonomy to Specialist Agents  (24/25, **Adopt**)
- **Edit**: `.claude/agents/qa-specialist.md`, `architecture-consultant.md`, `security-specialist.md`
- **Add**: Pre-Report Gate (4 questions before any finding); "zero findings is valid" statement; HIGH/CRITICAL proof requirement (snippet + scenario + why existing guards don't catch it); Python/FastAPI-adapted false-positive list
- **Effort**: S (one session)
- **Why #1**: Highest score, lowest cost. Directly addresses active reviewer credibility erosion.

### #2 — Adopt Agent Introspection Debugging Protocol  (20/25, **Adopt**)
- **Create**: `.claude/skills/agent-introspection/SKILL.md` based on ECC's four-phase loop
- **Reference**: from `failure_taxonomy.md` (unclassified in-flight failures) and `autonomous_workflow.md`
- **Imports**: Failure Capture template; root-cause pattern table (loop / context overflow / service / quota / file / test); "smallest reversible action" recovery heuristic; Introspection Report format
- **Effort**: S
- **Why #2**: Fills the gap between named infrastructure failures and in-flight reasoning failures during `/build_module` autonomous runs. Pure guidance, no infrastructure.

### #3 — Santa Method Context Isolation for HIGH/CRITICAL Reviews  (21/25, **Adapt**)
- **Add to** `review_gates.md`: `## Context Isolation Requirement` for HIGH/CRITICAL tier
- **Add to** facilitator agent: "For HIGH risk or above, dispatch primary reviewers before synthesizing your own analysis"
- **Defer**: convergence loop + iteration cap. Adopt only the context-isolation primitive.
- **Effort**: S
- **Why #3**: Strengthens Principle #4 with minimal friction.

## Verdict Summary Table

| Pattern | Score | Recommendation |
|---------|-------|----------------|
| False-Positive Taxonomy | **24/25** | **Adopt** — edit 3 agent definitions |
| Santa Method (context isolation) | 21/25 | **Adapt** — edit `review_gates.md` + facilitator |
| Agent Introspection Debugging | 20/25 | **Adopt** — create new skill file |
| Rules Distill | 19/25 | **Defer** — adopt when skill count hits 25+ |
| Context Budget Audit | 19/25 | **Adopt as one-time practice** |
| Prompt Defense Baseline | 19/25 | **Adapt selectively** — `security-specialist` only initially |
| Confidence-Scored Instincts | 17/25 | **Adapt format only** — decline automation |
| Skill-Comply Measurement | 16/25 | **Defer** — revisit on Rule-of-Three trigger |

## Overall Verdict

- **Best pattern adoption score**: **24/25** (False-Positive Taxonomy — strongly recommended)
- **Overall recommendation**: **STRONG ADOPT** for the top 3; CONDITIONAL/DEFER for the rest

This is the richest source in the 6-repo survey. Three patterns clear the 20/25 threshold and are direct prompt-level changes with zero architectural cost.

## Recovery Note

Agent returned the full report inline but claimed "subagent constraints" prevented Write. The constraint did not exist — this is the third project-analyst dispatch with the same hallucination pattern. Full content preserved verbatim with light reformatting.
