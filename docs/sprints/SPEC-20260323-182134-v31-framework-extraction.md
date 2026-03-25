---
spec_id: SPEC-20260323-182134
title: "Release v3.1.0: Framework Enhancements from Real-World Usage"
status: approved
risk_level: medium
type: spec
reviewed_by: [architecture-consultant, qa-specialist, docs-knowledge]
discussion_id: DISC-20260323-182242-v31-framework-extraction-spec-review
---

## Goal

Extract battle-tested framework enhancements from the agentic_journal project (33 days, 323 discussions, 385 commits, 11 retros) into the canonical template. Ship as v3.1.0 — the first release informed by real-world derived project experience.

## Context

The agentic_journal project forked from this template at v3.0.0 and has been the framework's first real-world deployment. Through 33 days of intensive use, the framework evolved in four dimensions: process bug fixes, new capabilities, rule enhancements, and agent definition refinements. An extraction report (FRAMEWORK_TEMPLATE_EXTRACTION_REPORT.md) was produced by the source project's specialist team to guide this work.

The template must remain tech-stack-neutral (Python/FastAPI defaults with parameterization guidance). All Flutter/Dart/ADHD-specific content must be stripped during extraction. The goal is to upstream the structural improvements while preserving the template's generality.

## Requirements

### Category 1: Process Bug Fixes (6 items) — all document/prompt bugs, not code bugs

1. **Spec lifecycle completion** — Add spec status update to `build_module.md` (Step 7c) and `ship.md` (Step 7d) that sets `status: complete`, `completed_at`, `completed_by` when a build/ship finishes
2. **Retro spec audit** — Add Step 1b to `retro.md` that detects stale specs (approved/reviewed but not complete for >7 days), distinguishing vision vs actionable specs
3. **Retro action tracking** — Add Step 1c to `retro.md` that checks `memory/decisions/retro-action-registry.md` for open action items
4. **Spec budget + type distinction** — Add Step 0.5 to `plan.md` limiting active specs to 5, and Step 0.7 adding `type: spec` vs `type: vision` distinction
5. **Review-to-commit traceability** — Add `reviewed_files: []` to review report template YAML frontmatter; update `review.md` to populate it
6. **Related discussions linking** — Add `--related` flag to `create_discussion.py`, add `related_discussion_id` column to `init_db.py` schema using the existing migration guard pattern (try/except ALTER TABLE)

### Category 2: New Capabilities (7 items)

7. **BUILD_STATUS freshness check** — Add Check 10 (advisory) to `quality_gate.py` warning when BUILD_STATUS.md is older than 60 minutes
8. **Promotion notifications** — Add notification step to `close_discussion.py` that queries `promotion_candidates` table and suggests `/promote` when pending > 0
9. **Session health nudges** — Expand `session-start.ps1` with 6-point health dashboard: retro age, open retro actions, pending adoptions, promotion candidates, stale specs, Layer 3 health. Health checks should call a single dashboard script rather than embedding query logic inline.
10. **Context-brief formalization** — Formalize Step 3.5 in `review.md` capturing developer request context as turn_id=1 with `context-brief` tag
11. **Agent reflection capture** — Add Step 7c to `review.md` dispatching reflection requests to REVISE specialists; enhance existing `ingest_reflection.py` script with improvements from source project
12. **Developer assessment in reviews** — Add `developer_assessment` section to review report template for counterfactual analysis (`would-have-caught` / `would-have-missed` tags)
13. **Record education script** — Enhance existing `record_education.py` script with improvements from source project for education gate results capture to SQLite

### Category 3: Rule Enhancements (4 items)

14. **Trust boundary sanitization** — Add to `security_baseline.md`: "Sanitize data at every trust boundary — not just user input. Data interpolated into LLM prompts, action triggers, or cross-process channels must be validated at the boundary"
15. **Injectable seams gate** — Add to `review_gates.md` Architectural Gates: "New external dependency integrations must define an abstract interface enabling test substitution"
16. **Data correctness blocking gate** — Add to `review_gates.md`: "Data displayed in the UI that is provably incorrect at implementation time must be classified as blocking"
17. **Advisory carry-forward** — Add to `review_gates.md`: advisory findings must be carried forward in the next review report until resolved or formally accepted

### Category 4: Agent Definition Upgrades (12 agents)

18. **Verdict-first output format** — Add to all specialist agents (including finding-validator, compliance-auditor, history-analyst): "Always open your output with a 1-2 sentence plain-language verdict before the YAML block"
19. **Facilitator expansion** — Add: dispatch quick-reference table, survival rate checkpoint, advisory backlog management, Socratic prompting techniques, model tier override guidance with table, team development notes section, agents_activated with model tiers
20. **Independent-perspective expansion** — Expand capabilities and instance type guidance without altering hierarchical standing (remains a specialist, not elevated to peer of facilitator). Add richer philosophy, innovation scouting guidance, partnership-with-facilitator section framed as collaboration not co-leadership
21. **Steward streamlining** — Refocus on framework governance; add Tool Use Protocol; simplify activation patterns
22. **Architecture-consultant** — Add Tool Use Protocol, expand specialist philosophy, add verdict-first
23. **Docs-knowledge expansion** — Add Model and Configuration Awareness section (track model tier of findings), Documentation Completeness baseline checks
24. **Educator enhancement** — Add Knowledge Gap Escalation, Adaptive Intensity, persona bias safeguard
25. **QA-specialist refinement** — Refine philosophy ("tests are a contract"), add verdict-first
26. **Security-specialist** — Add verdict-first, refine philosophy
27. **Performance-analyst** — Add verdict-first
28. **UX-evaluator** — Add verdict-first, Tool Use Protocol (no ADHD/clinical content)
29. **Finding-validator** — Add verdict-first
30. **Compliance-auditor** — Add verdict-first

### Category 5: Infrastructure Updates

31. **Micro-fix protocol** — New rule `.claude/rules/micro_fix_protocol.md` (generalized: strip Flutter-specific examples, keep the sizing heuristic and two-strike escalation). Placed in rules/ (auto-loaded) because the two-strike escalation is meant to be enforced, not consulted.
32. **Version bump** — Update `pyproject.toml` from 3.0.0 to 3.1.0
33. **CLAUDE.md sync** — Explicit section checklist:
    - Capture Pipeline section: add reflection ingestion as step 2a
    - Capture Pipeline section: add `record_education.py` reference
    - Hooks section: update SessionStart description for 6-point health dashboard
    - Quality Gate section: update check count (add BUILD_STATUS freshness)
    - Rules enumeration: update count from 11 to 12 (micro_fix_protocol added)
    - Known Limitations: review for any new gaps introduced
    - Agent Roster table: confirm no tier changes (no changes expected in v3.1)
34. **ADR-0008** — Document the extraction decision with required content:
    - Extraction source and scope (agentic_journal, 33 days, 323 discussions)
    - Inclusion rationale for each category
    - Explicit exclusion list with rationale per item (capability protection, ADHD constraints, sync boundary pattern, Flutter tooling)
    - Tech-stack-neutrality as a named architectural consequence
    - Reference to source extraction report as a referenced discussion artifact
    - Note that Items 1-6 are document/prompt bugs (no regression tests required)
35. **Framework doc sync** — Per `framework_doc_sync.md`, update:
    - `docs/FRAMEWORK_SPECIFICATION.md`: version bump, quality gate check count, micro loop trigger status ("Planned" → "Implemented"), implementation status section
    - `docs/diviner-dojo-framework-presentation.html`: version badge, rule count
    - `docs/how-to-use-presentation.html`: version, stats
36. **Lineage event** — Append version transition event (3.0.0 → 3.1.0) to `.claude/custodian/lineage-events.jsonl`

### Category 6: Test Coverage

37. **Tests for record_education.py** — Add `tests/test_record_education.py`: happy path, score boundary values (0.0, 1.0, 1.01), FK violation, `passed` bool coercion, invalid bloom_level
38. **Tests for ingest_reflection.py** — Add `tests/test_ingest_reflection.py`: valid reflection round-trip, missing frontmatter, duplicate reflection_id idempotency, confidence_delta extraction variants, no trailing newline
39. **Test for BUILD_STATUS freshness check** — Add test for the new quality_gate.py check: stale vs fresh BUILD_STATUS.md, missing file
40. **Test for related_discussion_id migration** — Add test covering: fresh DB, existing DB without column, existing DB with column
41. **Template neutrality test** — Add `tests/test_template_neutrality.py` that greps `.claude/agents/`, `.claude/rules/`, `.claude/commands/` for forbidden terms ["Flutter", "Dart", "ADHD", "agentic_journal"]

## Constraints

- All changes must be tech-stack-neutral (Python/FastAPI defaults, parameterizable)
- No Flutter/Dart/ADHD-specific content in any file
- Agent definitions: keep the template's 14-agent roster (don't drop to 11)
- Independent-perspective remains a specialist (equal standing per ADR-0005), not elevated to peer of facilitator
- finding-validator, compliance-auditor, history-analyst: add verdict-first but keep template versions otherwise
- UX-evaluator: add verdict-first and Tool Use Protocol but do NOT import ADHD-specific content
- Scripts must remain Python (not Dart/Flutter)
- Preserve backward compatibility with existing derived projects (use migration guard pattern for schema changes)
- Process bug fixes (Items 1-6) are document/prompt bugs — no regression tests or ledger entries required

## Acceptance Criteria

- [ ] All 6 process bug fixes implemented (document/prompt changes, no code tests needed)
- [ ] All 7 new capabilities implemented
- [ ] All 4 rule enhancements applied
- [ ] All 12 agent definitions updated: facilitator, steward, architecture-consultant, independent-perspective, docs-knowledge, educator, qa-specialist, security-specialist, performance-analyst, ux-evaluator, finding-validator, compliance-auditor (+ history-analyst verdict-first = 13 total)
- [ ] Micro-fix protocol rule added (generalized, no Flutter-specific content)
- [ ] quality_gate.py passes on the template itself with no checks skipped on a clean branch
- [ ] Tests pass: test_record_education.py, test_ingest_reflection.py, test_template_neutrality.py, BUILD_STATUS freshness check test, migration test
- [ ] CLAUDE.md updated per explicit section checklist (Item 33)
- [ ] ADR-0008 includes: extraction source, inclusion rationale, exclusion list with per-item rationale, tech-stack-neutrality consequence
- [ ] Framework doc sync complete: FRAMEWORK_SPECIFICATION.md, presentations updated per sync points
- [ ] CLAUDE.md Agent Roster table unchanged — no tier changes in v3.1.0. Confirmed.
- [ ] Version bumped to 3.1.0
- [ ] No Flutter/Dart/ADHD-specific content in any file (verified by test_template_neutrality.py)
- [ ] Lineage event appended for version transition

## Risk Assessment

- **Medium risk**: Agent definition changes could alter review behavior in unpredictable ways. Mitigation: changes are additive (verdict-first, new sections) not destructive (no removal of existing guidance). Independent-perspective expansion keeps specialist standing per ADR-0005.
- **Low risk**: Process bug fixes are well-defined and tested in the source project for 33 days. These are document/prompt bugs, not code bugs.
- **Low risk**: Rule enhancements are small, targeted additions to existing rule files.
- **Low risk**: Schema change uses existing migration guard pattern for backward compatibility.

## Affected Components

### Commands (5 files)
- `.claude/commands/build_module.md` — Step 7c spec lifecycle
- `.claude/commands/ship.md` — Step 7d spec lifecycle
- `.claude/commands/retro.md` — Steps 1b, 1c
- `.claude/commands/plan.md` — Steps 0.5, 0.7
- `.claude/commands/review.md` — Steps 3.5, 7c, reviewed_files

### Rules (3 files)
- `.claude/rules/security_baseline.md` — Trust boundary note
- `.claude/rules/review_gates.md` — 3 new gates + advisory lifecycle
- `.claude/rules/micro_fix_protocol.md` — NEW file

### Agents (13 files)
- `.claude/agents/facilitator.md` — Major expansion
- `.claude/agents/independent-perspective.md` — Capability expansion (not hierarchy change)
- `.claude/agents/steward.md` — Streamlining
- `.claude/agents/architecture-consultant.md` — Tool Use Protocol + verdict-first
- `.claude/agents/docs-knowledge.md` — Model awareness + completeness checks
- `.claude/agents/educator.md` — Gap escalation + adaptive intensity
- `.claude/agents/qa-specialist.md` — Philosophy + verdict-first
- `.claude/agents/security-specialist.md` — Verdict-first
- `.claude/agents/performance-analyst.md` — Verdict-first
- `.claude/agents/ux-evaluator.md` — Verdict-first + Tool Use Protocol
- `.claude/agents/finding-validator.md` — Verdict-first
- `.claude/agents/compliance-auditor.md` — Verdict-first
- `.claude/agents/history-analyst.md` — Verdict-first

### Scripts (4 existing + enhancements)
- `scripts/quality_gate.py` — Check 10 (BUILD_STATUS freshness)
- `scripts/create_discussion.py` — `--related` flag
- `scripts/init_db.py` — `related_discussion_id` column (migration guard)
- `scripts/close_discussion.py` — Promotion notification
- `scripts/record_education.py` — Enhance existing
- `scripts/ingest_reflection.py` — Enhance existing

### Tests (5 files, new)
- `tests/test_record_education.py` — NEW
- `tests/test_ingest_reflection.py` — NEW
- `tests/test_template_neutrality.py` — NEW
- Tests for BUILD_STATUS freshness check (in existing or new test file)
- Tests for related_discussion_id migration (in existing or new test file)

### Templates (1 file)
- `docs/templates/review-report-template.md` — reviewed_files + developer_assessment

### Hooks (1 file)
- `.claude/hooks/session-start.ps1` — 6-point health nudge

### Docs (3+ files)
- `docs/adr/ADR-0008-v31-real-world-extraction.md` — NEW
- `CLAUDE.md` — Sync per explicit checklist
- `docs/FRAMEWORK_SPECIFICATION.md` — Version, check count, micro loop status
- `docs/diviner-dojo-framework-presentation.html` — Version badge, counts
- `docs/how-to-use-presentation.html` — Version, stats

### Config (1 file)
- `pyproject.toml` — Version 3.0.0 → 3.1.0

### Lineage (1 file)
- `.claude/custodian/lineage-events.jsonl` — Version transition event

## Dependencies

- Source project at `C:\Work\AI\agentic_journal\` must be accessible for reading enhanced files
- No external dependency additions required
- All changes are additive — no breaking changes to existing framework consumers

## Build Task Breakdown

| Task | Files | Checkpoint? | Trigger |
|------|-------|-------------|---------|
| T1: Process bug fixes — commands | build_module.md, ship.md, retro.md, plan.md | Yes | Architecture choice (process workflow) |
| T2: Review enhancements | review.md, review-report-template.md | Yes | Architecture choice |
| T3: Script enhancements | quality_gate.py, create_discussion.py, init_db.py, close_discussion.py | Yes | Architecture choice (schema + pipeline changes) |
| T4: Script enhancements — existing | record_education.py, ingest_reflection.py | Yes | Architecture choice (enhance existing pipeline scripts) |
| T5: Rule enhancements | security_baseline.md, review_gates.md, micro_fix_protocol.md | Yes | Adds blocking gates (enforcement behavior change) |
| T6: Agent upgrades — leadership | facilitator.md, steward.md | Yes | Architecture choice |
| T7: Agent upgrades — specialists | 11 agent files | Yes | Architecture choice |
| T8: Test coverage | 5 test files | No | Pure test writing (exempt) |
| T9: Session hooks | session-start.ps1 | No | Config |
| T10: Infrastructure + doc sync | CLAUDE.md, pyproject.toml, ADR-0008, FRAMEWORK_SPECIFICATION.md, presentations, lineage event | No | Docs/config |

## Spec Review Summary

Three specialists reviewed this spec. All returned REVISE verdicts. Blocking findings addressed:

1. **Architecture-consultant**: Independent-perspective "peer of facilitator" contradicts ADR-0005 hierarchy → Reframed as capability expansion without hierarchy change (Item 20 revised)
2. **Architecture-consultant**: Task 4 incorrectly characterized existing scripts as new → Recharacterized as "enhance existing" (Items 11, 13 revised)
3. **QA-specialist**: record_education.py and ingest_reflection.py have 0% test coverage → Added Category 6 with 5 test requirements (Items 37-41)
4. **QA-specialist**: quality_gate.py passes criterion misleadingly weak → Criterion now specifies "no checks skipped" + explicit test file requirements
5. **Docs-knowledge**: CLAUDE.md sync scope too vague → Replaced with explicit 7-point section checklist (Item 33)
6. **Docs-knowledge**: ADR-0008 content scope undefined → Added 6-point content requirement (Item 34)

Advisory findings noted for build phase:
- Session health dashboard coupling (arch): consider script-based approach vs inline
- Micro-fix protocol placement (arch): kept in rules/ with documented rationale
- T5 checkpoint (arch): upgraded to Yes
- Framework doc sync gap (docs): added T10 with explicit artifacts
- Lineage event (docs): added Item 36
- Template neutrality test (qa): added Item 41
- Process bug classification (qa): noted as document/prompt bugs in constraints
