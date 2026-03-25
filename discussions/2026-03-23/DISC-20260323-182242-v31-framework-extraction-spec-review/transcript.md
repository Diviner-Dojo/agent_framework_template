---
discussion_id: DISC-20260323-182242-v31-framework-extraction-spec-review
started: 2026-03-23T18:22:51.800801+00:00
ended: 2026-03-23T18:28:50.477058+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 5
---

# Discussion: DISC-20260323-182242-v31-framework-extraction-spec-review

## Turn 1 — facilitator (evidence)
*2026-03-23T18:22:51.800801+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Extract framework enhancements from the agentic_journal project (33 days real-world use, 323 discussions, 385 commits) into the canonical template and release as v3.1.0
- **Files/scope**: ~30 files across commands, rules, agents, scripts, templates, hooks, and infrastructure. Four categories: process bug fixes, new capabilities, rule enhancements, agent definition upgrades
- **Developer-stated motivation**: The agentic_journal is the first real-world deployment of this framework. Enhancements discovered through use should flow back to the template so all future derived projects benefit
- **Explicit constraints**: All changes must be tech-stack-neutral (strip Flutter/Dart/ADHD-specific content). Keep the 14-agent roster. Preserve backward compatibility with existing derived projects

---

## Turn 2 — architecture-consultant (critique)
*2026-03-23T18:26:34.802755+00:00 | confidence: 0.82*
*tags: spec-review, architecture*

Verdict: REVISE. 7 findings (2 medium, 5 low/info). BLOCKING: (1) Independent-perspective elevation to 'peer of facilitator' contradicts ADR-0005 hierarchy - either scope change to avoid hierarchy modification or expand ADR-0008 to supersede. (2) Task 4 incorrectly characterizes record_education.py and ingest_reflection.py as new files when they already exist in scripts/ - recharacterize as 'enhance existing'. ADVISORY: (3) Session-start 6-point health dashboard creates coupling fan-out - consider separate /health-check command. (4) related_discussion_id needs migration guard pattern. (5) micro_fix_protocol may belong in skills/ not rules/. (6) CLAUDE.md sync needs explicit section checklist. (7) T5 rule enhancements should trigger checkpoint (adds blocking gates, not just docs).

---

## Turn 3 — qa-specialist (critique)
*2026-03-23T18:26:41.218807+00:00 | confidence: 0.87*
*tags: spec-review, qa*

Verdict: REVISE. 8 findings (3 high, 2 medium, 3 low). BLOCKING: (1) record_education.py has 0% test coverage with untested FK violations, score constraints, bool coercion. Add tests/test_record_education.py. (2) ingest_reflection.py has 0% test coverage with fragile YAML parser, regex edge cases, Windows line endings. Add tests/test_ingest_reflection.py. (3) quality_gate.py passes criterion is misleadingly weak - coverage scoped to src/ only, scripts/ excluded. Add explicit test for BUILD_STATUS freshness check. ADVISORY: (4) Schema migration for related_discussion_id needs 3-scenario test. (5) Agent count test is load-bearing for 14-roster constraint. (6) Process bugs need code-vs-document classification. (7) Regression ledger empty despite 6 bug fixes. (8) Add test_template_neutrality.py to permanently guard tech-stack-neutral constraint.

---

## Turn 4 — docs-knowledge (critique)
*2026-03-23T18:26:47.447505+00:00 | confidence: 0.87*
*tags: spec-review, docs*

Verdict: REVISE. 7 findings (2 high, 5 medium/low). BLOCKING: (1) CLAUDE.md Capture Pipeline section must explicitly add reflection ingestion as a pipeline step - developers won't discover the path from REVISE verdict to SQLite reflections table. (2) ADR-0008 content scope undefined - must include exclusion rationale, extraction provenance, tech-stack-neutrality as named consequence. ADVISORY: (3) SessionStart hook description outdated after 6-point dashboard. (4) FRAMEWORK_SPECIFICATION.md micro loop status stale ('Planned' should become 'Implemented'). (5) Quality gate check count stale in docs (5 should become 6). (6) Lineage manifest needs version transition event. (7) Model tier confirmation needed. Also: framework_doc_sync.md rule triggered - FRAMEWORK_SPECIFICATION.md and HTML presentations not in affected components list. Must extend T9 or add T10.

---

## Turn 5 — facilitator (synthesis)
*2026-03-23T18:28:50.477058+00:00 | confidence: 0.85*
*tags: synthesis, spec-review*

## Request Context
- **What was requested**: Extract framework enhancements from agentic_journal (33 days real-world use) into the template and release as v3.1.0
- **Files/scope**: ~40 files across commands, rules, agents, scripts, templates, hooks, tests, docs, and infrastructure
- **Developer-stated motivation**: First real-world deployment feedback flowing back to the canonical template for all future derived projects
- **Explicit constraints**: Tech-stack-neutral (strip Flutter/Dart/ADHD), keep 14-agent roster, preserve backward compatibility

## Synthesis
Three specialists reviewed (architecture-consultant, qa-specialist, docs-knowledge). All returned REVISE. Six blocking findings addressed in spec revision: (1) independent-perspective reframed as capability expansion not hierarchy change per ADR-0005, (2) existing scripts recharacterized from 'new' to 'enhance existing', (3) 5 test files added as Category 6, (4) quality gate criterion strengthened, (5) CLAUDE.md sync replaced with 7-point section checklist, (6) ADR-0008 given 6-point content scope. Advisory items incorporated: T5 upgraded to checkpoint, framework doc sync artifacts added as T10, template neutrality test added, lineage event added. Spec updated to reviewed status. 41 items across 10 build tasks.

---
