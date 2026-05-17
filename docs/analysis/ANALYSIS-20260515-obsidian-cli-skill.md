---
analysis_id: ANALYSIS-20260515-obsidian-cli-skill
repo: https://github.com/pablo-mano/Obsidian-CLI-skill
analyst: project-analyst
date: 2026-05-15
status: summary-only (agent did not invoke Write — recovered from returned summary)
---

# Obsidian-CLI-skill

## Profile

- **Type**: Claude Code plugin / skill — not a software system but a knowledge artifact
- **Purpose**: Teaches AI agents how to operate Obsidian vaults via Obsidian's official CLI (v1.12+, IPC-based)
- **Composition**: Single `SKILL.md` file + 130+ command reference + eval dataset of 35 labeled trigger queries + marketplace packaging metadata
- **Activity**: 173 stars, 18 forks, active February–March 2026
- **Maintenance signal**: Short, focused project; active during a tight window

## Notable Patterns

### Pattern 1 — Skill Description as Activation Classifier  **[19/25 — strongly recommended floor]**

The `SKILL.md` `description` field is written as a **model-routing instruction**, not a human-readable summary. It contains:

- Explicit positive trigger conditions
- Explicit exclusions
- A discrimination principle (e.g., "the user is asking Claude to act, not to explain")

The description was **empirically rewritten twice** based on eval-set failures.

**Applicability to this framework**: Our `.claude/skills/*.md` descriptions are currently human-readable summaries, not routing instructions. Rewriting them in this style costs **30–60 minutes across all 7 skills** and requires zero infrastructure changes. Direct, low-cost adoption.

### Pattern 2 — Gotcha-Driven Documentation for Agents  **[18/25]**

Every non-obvious CLI behavior is documented **with cause and workaround**, written specifically to prevent agent mistakes:

- Wrong path format
- List-value stored as string
- Multi-line JS failure mode

**Applicability to this framework**: Our `CLAUDE.md` Known Limitations section already does this at project scope. Extending the pattern **into skill files** is a natural complement with zero structural cost.

## Cross-Reference to This Framework

- Our existing `.claude/skills/*.md` files (python-project-patterns, testing-playbook, security-checklist, performance-playbook, adr-writing, feature-status-registry) are candidates for the description-rewrite treatment.
- The activation-classifier pattern aligns with Principle #8 (Least-complex intervention first) — prompt-level change, no command/agent/architecture changes required.

## Insight Journal Cross-Reference  **[FLAGGED]**

If Insight Journal uses an Obsidian vault, this skill can be installed directly:

```
/plugin marketplace add https://github.com/pablo-mano/Obsidian-CLI-skill
```

Zero code changes, immediate vault-access capability for AI workflows in that derived project.

## Top 2 Recommendations

1. **Rewrite `.claude/skills/*.md` descriptions as activation classifiers** — Effort: S (30–60 min), Scope: framework, Value: improves skill-routing accuracy with zero infra change.
2. **Extend gotcha-driven docs into skill files** — Effort: S, Scope: framework, Value: low-cost complement to existing CLAUDE.md Known Limitations pattern.

Plus:

3. **Install the skill directly in Insight Journal** if it uses an Obsidian vault — Effort: trivial, Scope: derived project, Value: immediate.

## Verdict

- **Best pattern adoption score**: 19/25
- **Overall recommendation**: **CONDITIONAL ADOPT** — adopt the two patterns (description-as-classifier, gotcha docs) into our existing skill files; directly install the upstream skill in Insight Journal if applicable.

## Recovery Note

The original background agent (project-analyst) completed a coherent analysis but did not invoke the `Write` tool — only returned a summary. This file reconstructs the report from that summary. The deep cite-by-file detail (specific line numbers in upstream SKILL.md, full eval-set breakdown) was not preserved; the load-bearing decision content is captured.
