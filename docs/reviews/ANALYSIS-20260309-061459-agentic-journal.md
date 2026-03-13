---
analysis_id: "ANALYSIS-20260309-061459-agentic-journal"
discussion_id: "DISC-20260309-060506-analyze-agentic-journal"
target_project: "<local-path>/agentic_journal/"
target_language: "Dart/Flutter"
target_stars: "N/A"
target_license: "NONE"
license_risk: "N/A — own project"
agents_consulted: [project-analyst, architecture-consultant, independent-perspective, docs-knowledge]
patterns_evaluated: 11
patterns_recommended: 4
analysis_date: "2026-03-09"
---

## Project Profile

- **Name**: agentic_journal ("Insight Journal")
- **Source**: <local-path>/agentic_journal/ (local)
- **Tech Stack**: Flutter 3.x / Dart 3.11+, Riverpod 2.6, drift 2.25 (SQLite ORM), Supabase 2.8, dio, sherpa_onnx + speech_to_text (STT), ElevenLabs (TTS), llamadart (local LLM). Python 3.11+ for framework tooling.
- **Size**: ~115,000 LOC (55.6k Dart lib/, 49.9k Dart test/, 9.3k Python scripts/)
- **Maturity**: Active production app. 36 ADRs, 100+ captured discussions, 40+ regression ledger entries. Version 1.0.0+33.
- **AI Integration**: Sophisticated. Direct derivative of our template v2.1 — same 10 agents, 13+ commands, 7 hooks, full capture pipeline. Has made targeted extensions.

### Tech Stack Details

- `drift: ^2.25.0` — type-safe SQLite ORM with code generation
- `flutter_riverpod: ^2.6.1` + `riverpod_annotation` — code-generated providers, strict DI
- `llamadart: 0.6.2` — on-device LLM inference (llama.cpp bindings)
- `sherpa_onnx: ^1.12.25` — offline STT/TTS via ONNX models
- `supabase_flutter: ^2.8.0` — cloud sync, auth, realtime
- Python `yaml` used in quality_gate.py for ADR frontmatter parsing
- Framework scripts extended: `deploy.py`, `bump_version.py`, `test_on_emulator.py`, `record_education.py`, `build_release.py`

### Key Files Examined

| File | Significance |
|------|-------------|
| `.claude/rules/capability_protection.md` | CPP protocol definition with OS resource invariants |
| `CAPABILITY_STATUS.md` | Live capability registry — machine-readable |
| `docs/adr/ADR-0035-capability-protection-protocol.md` | Decision lineage, incident post-mortem |
| `scripts/quality_gate.py:504-686` | CPP C2 quality gate implementation in Python |
| `.claude/rules/autonomous_workflow.md` | Autonomous authorization vs. protocol bypass clarification |
| `.claude/commands/ship.md` | Fully automated end-to-end delivery workflow |
| `scripts/bump_version.py` | Semantic version automation |
| `EDUCATION_GATE_MANIFEST.md` | Structured education gate completion record |
| `memory/bugs/regression-ledger.md` | 40+ entries — signal about AI-dev discipline |
| `DART_DEFINE_FLAGS.md` | Environment variable documentation pattern |

### License

- **License**: No license (own project)
- **Risk level**: N/A — developer's own project
- **Attribution required**: N/A
- **Adoption constraint**: None — own project, no restrictions

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.92)

Six notable patterns identified from survey of a direct derivative project with 3 weeks of active AI-assisted development, 100+ discussions, and 36 ADRs. The project extends the template with two novel rules (autonomous_workflow, capability_protection) and a capability registry (CAPABILITY_STATUS.md), all created in response to real production incidents. The project has active capture pipeline, high regression discipline (40+ ledger entries), and sophisticated framework customization.

### Architecture Consultant (confidence: 0.85)

Three applicable patterns:
1. **CPP Two-PR Pattern**: New integrations cannot become default in the same PR. Python analog uses FastAPI dependency injection registrations and env-var feature flags. Adapt CAPABILITY_STATUS.md registry first, quality gate automation later.
2. **Autonomous Workflow Rule**: Closes gap between commit_protocol.md and CLAUDE.md autonomous authorization section. Near-verbatim adoption replacing `lib/` with `src/`.
3. **Pre-flight validation in /ship**: Python validation script and CRITICAL BEHAVIORAL RULES list worth backporting regardless of automation level.

Recommended: Defer automated /ship, adopt pre-flight patterns.

### Documentation & Knowledge (confidence: 0.82)

Three documentation patterns:
1. **Education Gate Manifest**: Standardized artifact recording gate completion with Bloom's distribution, pass thresholds, and ADR connections. Template should add template file.
2. **Known Limitations with live data**: Template should populate real limitations from own pipeline runs instead of commented-out examples.
3. **BUILD_STATUS.md advisory accumulation**: Document practice of tracking open advisories across reviews. Zero code cost.

### Independent Perspective (confidence: 0.80)

Two key insights:
1. **CPP + autonomous_workflow are a dependency pair**: CPP enforcement gap means agent can self-certify PROVEN without actual testing; CPP only works if /review is not skippable, which is what autonomous_workflow enforces. Adopt both or neither.
2. **Domain constraints as blocking review findings**: Template should model how derived projects declare domain safety constraints at blocking-finding severity in CLAUDE.md.

Pre-mortem on automated /ship identified 3 failure scenarios: auto-semver misclassification, review-skipped commit, branch cleanup after partial failure.

---

## Pattern Scorecard

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Prior Sightings | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|----------------|---------|
| Autonomous Workflow Rule | 5 | 4 | 4 | 5 | 5 | 23 | 0 (new) | **ADOPT** |
| CAPABILITY_STATUS.md Registry | 4 | 4 | 3 | 4 | 4 | 19 | 0 (new) | DEFER |
| CPP Quality Gate (C2+C3) | 4 | 3 | 3 | 3 | 3 | 16 | 0 (new) | DEFER |
| Education Gate Manifest | 4 | 4 | 3 | 5 | 5 | 21 | 0 (new) | **ADOPT** |
| Domain Constraints Pattern | 5 | 4 | 3 | 4 | 5 | 21 | 0 (new) | **ADOPT** |
| BUILD_STATUS.md Advisory Tracking | 4 | 5 | 3 | 5 | 5 | 22 | 0 (new) | **ADOPT** |
| Pre-flight Validation in /ship | 4 | 4 | 4 | 5 | 5 | 22 | 2 (+2 Rule of Three) | **ADOPT** |
| Known Limitations Live Data | 4 | 4 | 5 | 5 | 4 | 22 | 1 (already adopted) | Already ADOPTED |
| bump_version.py | 4 | 5 | 5 | 4 | 4 | 22 | 1 (already adopted) | Already ADOPTED |
| Automated /ship Command | 4 | 4 | 3 | 3 | 3 | 17 | 0 (new) | DEFER |
| DART_DEFINE_FLAGS.md | 3 | 4 | 3 | 3 | 4 | 17 | 0 (new) | DEFER |

---

## Recommended Adoptions

*Patterns scoring >= 20/25.*

### Autonomous Workflow Rule (Score: 23/25)

- **What**: A dedicated rule separating "autonomous execution authorization" from "protocol bypass authorization." Created after a session bypassed `/plan`, `/build_module`, and `/review` entirely. Defines workflow tiers: multi-file features require `/plan` + `/build_module`; small changes require quality gate + `/review`.
- **Where it goes**: `.claude/rules/autonomous_workflow.md`
- **Why it scored high**: Prevalence:5 (every project using autonomous execution faces this), Fit:5 (already written in framework-agnostic language), Maintenance:5 (set and forget rule).
- **Implementation notes**: Near-verbatim copy from target. One substitution: `lib/` → `src/`. Closes a documented gap between commit_protocol.md and the CLAUDE.md autonomous authorization section.
- **Sightings**: 1 (first seen here)

### Education Gate Manifest (Score: 21/25)

- **What**: Standardized artifact recording education gate completion: which steps completed, Bloom's taxonomy distribution, pass thresholds, ADR connections, mastery progression, handoff criteria.
- **Where it goes**: `docs/templates/education-gate-manifest-template.md`
- **Why it scored high**: Fit:5 (template already has /quiz and /walkthrough), Maintenance:5 (template file, no ongoing cost).
- **Implementation notes**: Create template file. Update `/quiz` and `/walkthrough` commands to reference creating manifest on gate completion.
- **Sightings**: 1 (first seen here)

### Domain Constraints as Blocking Findings (Score: 21/25)

- **What**: A CLAUDE.md section pattern where derived projects declare domain-specific safety constraints (medical, financial, accessibility) at blocking-finding severity, so review specialists treat them as non-negotiable.
- **Where it goes**: CLAUDE.md — new commented-out section after Autonomous Execution Authorization
- **Why it scored high**: Prevalence:5 (every domain-specific project has safety constraints), Maintenance:5 (zero code cost, documentation only).
- **Implementation notes**: Add a commented-out template section showing the pattern. Zero code changes.
- **Sightings**: 1 (first seen here)

### BUILD_STATUS.md Advisory Tracking (Score: 22/25)

- **What**: Document the practice of accumulating open advisories from reviews in BUILD_STATUS.md so they persist across sessions until addressed.
- **Where it goes**: CLAUDE.md — one paragraph in the BUILD_STATUS.md section
- **Why it scored high**: Elegance:5 (uses existing artifact), Fit:5 (BUILD_STATUS.md already exists), Maintenance:5 (zero code cost).
- **Implementation notes**: One paragraph addition to CLAUDE.md.
- **Sightings**: 1 (first seen here)

### Pre-flight Validation in /ship (Score: 22/25 — Rule of Three triggered)

- **What**: Python validation script checking prerequisites exist, `gh` CLI is accessible, branch state is correct before starting delivery. Plus explicit CRITICAL BEHAVIORAL RULES list as pass/fail gates at the top of the command.
- **Where it goes**: `.claude/commands/ship.md` — enhance existing command
- **Why it scored high**: Previously seen in 2 analyses (Pre-Flight Checks for Commands, build_module Pre-Flight). Third sighting triggers Rule of Three (+2 bonus).
- **Implementation notes**: Add pre-flight validation section to existing `/ship` command. Add explicit behavioral rules list.
- **Sightings**: 3 (Rule of Three)

---

## Anti-Patterns & Warnings

### Sensitive Credentials in Repository

- **What**: `android/key.properties` and `android/release-key.jks` (Android signing credentials) committed to repo
- **Where seen**: `android/key.properties`, `android/release-key.jks`
- **Why it's bad**: Platform-specific credential files bypass the code-level secret scanning hooks
- **Our safeguard**: Our PreToolUse hook scans for 12 secret patterns. Consider adding `.jks`, `.keystore`, and `key.properties` patterns for Flutter/mobile derived projects.

### Windows `nul` File Artifact

- **What**: A `nul` file at project root — Windows artifact from attempting to create a file named `nul`
- **Where seen**: Project root
- **Why it's bad**: Pollutes repository, may cause cross-platform issues
- **Our safeguard**: Should be gitignored in derived projects

---

## Deferred Patterns

### CAPABILITY_STATUS.md Registry (Score: 19/25)

- **What**: Human-maintained markdown registry of capability maturity (PROVEN/EXPERIMENTAL/BROKEN/DEPRECATED) with device-test dates and verified-on hardware. Two-PR Pattern prevents new integrations from becoming default in the same PR.
- **Why deferred**: Evidence:3 (seen only in this project), Fit:4 (needs Python adaptation for FastAPI dependency injection). Independent-perspective notes CPP depends on autonomous_workflow being in place first.
- **Revisit if**: Autonomous workflow rule is adopted and a similar "experimental integration becomes default" incident occurs in the template or another derived project.

### CPP Quality Gate Automation (Score: 16/25)

- **What**: Git diff analysis in quality_gate.py to detect default-value changes and cross-reference against capability registry.
- **Why deferred**: Fit:3 (Flutter-specific Riverpod provider detection not transferable), Evidence:3, Maintenance:3 (requires ongoing adaptation for new integration patterns).
- **Revisit if**: CAPABILITY_STATUS.md registry is adopted and manual enforcement proves insufficient.

### Automated /ship Command (Score: 17/25)

- **What**: Fully automated delivery: semver classification, version bump, quality gate, review, commit, branch, push, PR, merge, sync, cleanup.
- **Why deferred**: Fit:3 (template is a teaching framework, manual checklist is appropriate), Maintenance:3 (complex error recovery logic). Pre-mortem identified 3 failure scenarios.
- **Revisit if**: Template evolves to support production deployment workflows, or a derived project needs autonomous delivery.

### DART_DEFINE_FLAGS.md / CONFIGURATION.md (Score: 17/25)

- **What**: Dedicated environment variable documentation with variable table, usage examples, IDE integration, security rationale.
- **Why deferred**: Fit:3 (template has minimal env var requirements), Prevalence:3 (only relevant when project has compile-time config).
- **Revisit if**: Template adds features requiring environment variables.

---

## Specialist Consensus

- **Agents that agreed**: All three specialists agreed the autonomous_workflow rule is the highest-value, lowest-cost adoption. Architecture-consultant and independent-perspective agreed CPP + autonomous_workflow are a dependency pair.
- **Notable disagreements**: Architecture-consultant recommended full CPP adoption path (registry + quality gate); independent-perspective cautioned that CPP enforcement gap (self-certification) means the quality gate provides incomplete protection without the /review trigger (C3). Reconciled: adopt registry first, quality gate only after review trigger is confirmed working.
- **Strongest signal**: The autonomous workflow rule closes a real, documented gap in the template. When derived projects enable autonomous execution, there is currently no rule governing what that authorization does and does not permit regarding protocol compliance. This gap was exposed by a real incident (7 implementation streams written without independent evaluation).
