---
analysis_id: ANALYSIS-20260515-open-design
repo: https://github.com/nexu-io/open-design
analyst: project-analyst
date: 2026-05-15
status: summary-only (recovered from agent return value — agent did not invoke Write)
---

# nexu-io/open-design

## Profile

- **Type**: Local-first, AI-assisted **UI design tool** — a TypeScript/Electron/Next.js **product**, not an agent framework template
- **Function**: Runs AI agents (Claude, Codex, Copilot) to generate and critique HTML/CSS design artifacts
- **Domain mismatch**: Not a Python project, not an agent framework. Largest domain gap of the 6 repos surveyed.
- **Composition**:
  - 151 brand design-system files
  - 133 agent skill definitions
  - 11 brand-agnostic "craft" markdown files encoding universal UI rules (typography, color, accessibility, animation, form validation, anti-AI-slop)

## Notable Patterns

### Pattern 1 — Five-State Coverage Checklist  **[19/25 — below adoption threshold]**

**Location**: `craft/state-coverage.md`

Every interactive surface must render five states:
1. **Loading**
2. **Empty**
3. **Error**
4. **Populated**
5. **Edge**

Ships with specific test matrices and loading-duration thresholds.

**Applicability**: Adapt into the **ux-evaluator agent's Domain Lens** — a low-cost prompt enrichment. The ux-evaluator was flagged in the CC feature survey as one of the 2 underused agents; this enrichment could improve its dispatch yield.

### Pattern 2 — Layered AGENTS.md Hierarchy  **[score not stated — below 19/25]**

Root file covers cross-cutting concerns; directory-level files cover local concerns; no duplication.

**Applicability**: Worth adapting **as our CLAUDE.md grows beyond comfortable working-memory load**. Our root CLAUDE.md is already long (~400 lines). At some point, splitting into per-directory CLAUDE.md fragments may be necessary. Not urgent yet.

## Cross-Reference to This Framework

- The five-state checklist fills a real gap — our `review_gates.md` mentions UI accessibility concerns but has no concrete state-coverage requirement
- The layered CLAUDE.md hierarchy is forward-looking — implement only when root CLAUDE.md becomes unwieldy
- Most of the project's value (brand design system, anti-AI-slop rules for visual artifacts) is domain-locked to design tooling and not portable

## Top Recommendations

1. **Adopt five-state coverage checklist into ux-evaluator's Domain Lens** — Effort: S, Scope: framework, Value: enriches the ux-evaluator agent (currently underused per CC survey), gives concrete review criteria.
2. **Defer layered CLAUDE.md split** — Note the pattern for future use when root CLAUDE.md exceeds working-memory load.

## Verdict

- **Best pattern adoption score**: **19/25** (Five-State Coverage)
- **Overall recommendation**: **DEFER**
- **Rationale**: Domain mismatch (UI design tool vs. Python agent framework) is too large for strong adoption recommendations. The five-state pattern is the one genuinely portable artifact; everything else is design-domain-specific.

## Recovery Note

The original background agent (project-analyst) completed its analysis and returned a coherent summary, but did not invoke the `Write` tool. This file is reconstructed from that summary. Specific file-line citations and the full pattern inventory were not preserved.
