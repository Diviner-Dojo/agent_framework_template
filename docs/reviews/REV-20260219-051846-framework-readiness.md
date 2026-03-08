---
review_id: REV-20260219-051846
discussion_id: DISC-20260219-051846-framework-readiness-review
risk_level: high
collaboration_mode: structured-dialogue
exploration_intensity: high
agents_activated: [architecture-consultant, qa-specialist, security-specialist, docs-knowledge, independent-perspective]
verdict: approve-with-changes
confidence: 0.88
---

# Framework Readiness Review

**Scope**: Full evaluation of the AI-Native Agentic Development Framework Template against the original research specification, assessing architectural consistency, internal coherence, and readiness for replication to actual projects.

**Reference**: Original framework specification document

---

## Executive Summary

The framework template is **architecturally sound and ready for replication with targeted fixes**. The four-layer capture stack faithfully realizes the research specification. The 9-agent panel is well-calibrated with domain-specific anti-patterns. The capture pipeline is complete and thoroughly tested. Domain separation between the sample Todo API and framework infrastructure is clean.

However, the rapid adoption of 20 patterns from 7 external projects has introduced several inconsistencies, dead code, and documentation drift that must be resolved before using this template for production projects. No adopted pattern has been empirically validated (all in PENDING state). The framework is at the upper boundary of single-developer maintainability.

**Bottom line**: Fix the 12 required changes below, then this template is ready for replication.

---

## Convergence Map (Where Specialists Agree)

### 1. Project-Analyst Subagent Contradiction (4/5 specialists flagged)
**Architecture, QA, Docs, Independent** all identified that CLAUDE.md states "Subagents CANNOT spawn other subagents" but `project-analyst.md` dispatches specialists via the Task tool. This is the most consistently flagged finding across the review.

### 2. quality_gate.py Hardcoded Paths (3/5 specialists flagged)
**Architecture, QA, Independent** identified that `SRC_DIR = PROJECT_ROOT / "src"` and `TESTS_DIR = PROJECT_ROOT / "tests"` will silently pass on empty directories when a consumer replaces the sample app with a different layout.

### 3. Missing Test Coverage for Framework Scripts (3/5 specialists flagged)
**QA, Architecture, Independent** identified that `scripts/` has 48% coverage while the quality gate only measures `src/` (89%). `ingest_reflection.py` has 0% coverage, `quality_gate.py` has 0%, `close_discussion.py` has 33%.

### 4. Secret Detection Pattern Gaps (3/5 specialists flagged)
**Security, Docs, Independent** identified missing Anthropic API key (`sk-ant-`), OpenAI key (`sk-proj-`), and GCP key patterns — directly relevant to this AI-native framework's users.

### 5. CLAUDE.md Documentation Drift (3/5 specialists flagged)
**Docs, Architecture, Independent** identified multiple CLAUDE.md inaccuracies: "6 secret patterns" (actually 8), incomplete memory directory layout, missing capture pipeline sub-steps, ADR-0001 says "8 agents" (actually 9).

### 6. backup_utils.py: Adopted but Never Called (2/5 specialists flagged)
**Independent, QA** identified that `backup_utils.py` was adopted from an external project but no hook, command, or script actually calls `backup_file()` before modifying framework files. The pattern is inert.

---

## Points of Dissent

### Framework Complexity vs. Value
**Independent-perspective** argues the framework is over-engineered for typical use: "A stripped-down version (4 agents, 5 commands, JSONL without SQLite, no hooks) would cover 80% of the value at 40% of the complexity." **Architecture-consultant** disagrees: "The SQLite Layer 2 schema with CHECK constraints is self-documenting and enables the evaluation metrics the research specifies." The truth is somewhere between — the infrastructure is correctly built for the aspirational use case, but that use case hasn't been validated yet.

### SQLite Layer 2 Necessity
**Independent-perspective** questions whether SQLite is premature given no query currently uses it. **Architecture-consultant** notes the schema's constraints and indexes are architecturally sound and the `/retro` and `/meta-review` commands are designed to query it. This is a reasonable disagreement about timing vs. architecture.

---

## Required Changes Before Replication (12 Items)

### MUST FIX (Blocking — Fix before using as template)

**R1. Add Anthropic/OpenAI/GCP secret patterns** [Security Finding 1]
- Add `sk-ant-`, `sk-proj-`, `AIzaSy`, `ya29.` patterns to both `validate_tool_use.py` and `redact_secrets.py`
- This is the single most relevant security gap for an AI-native framework

**R2. Protect .claude/settings.json from agent writes** [Security Finding 4]
- Add `.claude/settings.json` to `PROTECTED_PATTERNS` in `validate_tool_use.py`
- An agent that can rewrite settings.json can disable all hooks

**R3. Fix quality_gate.py silent-pass on empty directories** [Independent, Architecture, QA]
- Add startup validation: verify `SRC_DIR` and `TESTS_DIR` exist and contain `.py` files
- Fail loudly if directories are absent or empty — a silent pass is worse than no gate
- Consider making paths configurable via `pyproject.toml`

**R4. Resolve project-analyst subagent contradiction** [All specialists]
- Update CLAUDE.md to document the exception: "Subagents CANNOT spawn other subagents, except the project-analyst which serves as a delegated orchestrator for /analyze-project"
- Or restructure so the facilitator command dispatches specialists based on project-analyst's scout report
- Document the decision in a new ADR

**R5. Fix CLAUDE.md documentation drift** [Docs Findings 2-5]
- Update "6 secret patterns" → "8 secret patterns"
- Expand memory/ directory layout to show all 6 subdirectories
- Expand Capture Pipeline to show generate_transcript, ingest_events as sub-steps of close_discussion
- Fix hooks description: "format, locking, secrets, commit-gates, session-lifecycle"
- Update ADR-0001 agent count: "8 core agents" → "9 core agents"

### SHOULD FIX (Non-blocking but important for quality)

**R6. Add missing tests for framework scripts** [QA Findings 1-3]
- `ingest_reflection.py`: Test happy path, missing frontmatter, colon-in-YAML-value
- `close_discussion.py`: Test full orchestration, missing DB, nonexistent discussion
- `quality_gate.py`: Test `check_adrs()` with valid/invalid/malformed ADR files
- Target: scripts/ coverage from 48% → 75%+

**R7. Enable ruff B and ANN rulesets** [QA Finding - Quality Gate Gap]
- `pyproject.toml` selects only `E, F, I, N, W, UP` but `coding_standards.md` requires type annotations and no mutable defaults
- Add `B` (flake8-bugbear) and `ANN` (type annotations) to enforce documented standards

**R8. Add micro-loop reflection trigger** [Architecture Finding 3]
- Add a "reflection round" step to `/review` and `/deliberate` commands
- After synthesis, prompt each participating specialist to produce a reflection
- Capture via `write_event.py` with intent `reflection`, then `ingest_reflection.py`

**R9. Change secret detection from `ask` to `deny`** [Security Finding 2]
- Advisory-only prompts are fragile in automated/headless contexts
- Switch to hard deny with documented escape hatch (`CLAUDE_ALLOW_SECRETS=1`)

**R10. Delete or integrate backup_utils.py** [Independent Finding]
- Either wire `backup_file()` into the `/promote` command and framework file modification paths
- Or remove the module and its tests until integration is ready — dead code is confusing

**R11. Add cross-platform session hook documentation** [Architecture Finding 13]
- Session hooks use PowerShell (`.ps1`) — will fail on macOS/Linux
- Either provide bash equivalents or document platform requirement clearly

**R12. Fix close_discussion.py import brittleness** [Architecture Finding 10, Docs Finding 12]
- Add `sys.path` manipulation or convert to absolute imports
- Currently fails if run from project root: `python scripts/close_discussion.py`

---

## Recommended Improvements (Non-blocking, Nice-to-Have)

1. **Create `scripts/compute_metrics.py`** for the 5 research-specified evaluation metrics (disagreement rate, unique issue detection, false positive frequency, decision volatility, consensus latency)
2. **Add PENDING age check** to quality gate — fail if adopted patterns stay PENDING > 60 days
3. **Add stale `.acquiring` directory cleanup** in file locking (timeout-based, matching 120s lock expiry)
4. **Create `docs/templates/spec-template.md`** — the only missing artifact template
5. **Add `todo.db` and `nul` to `.gitignore`** — clean up Windows artifacts
6. **Bootstrap ADR-0001's `discussion_id: null`** — either create a seeded discussion or document the bootstrapping exception
7. **Mark time.sleep-dependent backup tests as `@pytest.mark.slow`**

---

## Education Gate Recommendation

**Recommended: Abbreviated walkthrough + targeted quiz** (medium risk, demonstrated competence)

The changes are well-understood and scoped. A full education gate is not warranted for documentation fixes and pattern additions. A targeted quiz on the capture pipeline flow and the dual-layer secret detection architecture would confirm understanding of the most complex subsystems.

---

## Specialist Confidence Scores

| Specialist | Confidence | Findings | Key Observation |
|---|---|---|---|
| architecture-consultant | 0.88 | 13 | "Template architecturally ready with 4 medium-severity items" |
| qa-specialist | 0.91 | 11 | "scripts/ at 48% coverage is the critical gap" |
| security-specialist | 0.91 | 10 | "Missing AI-native key patterns is the #1 security gap" |
| docs-knowledge | 0.91 | 16 | "CLAUDE.md drift in 5 areas; agent definitions exemplary" |
| independent-perspective | 0.82 | 7 scenarios | "Framework at upper boundary of single-dev maintainability" |

**Weighted Average Confidence**: 0.88

---

## What's Genuinely Well Done

1. **Four-layer capture stack** faithfully realizes the research spec with proper SQLite schema, CHECK constraints, indexes, and idempotent operations
2. **Agent anti-pattern sections** are calibrated and domain-specific — prevent the most common false-positive failure modes
3. **Capture pipeline test suite** (19 tests) proves infrastructure works independently of Claude Code
4. **Clean domain separation** — delete `src/` and `tests/test_routes.py`, framework continues working
5. **Adoption log** demonstrates real learning: 59 patterns scored, 20 adopted, with sighting tracking and Rule of Three
6. **Error handling pattern** (AppError hierarchy + centralized handlers) is exemplary for a template
7. **Secret detection dual-layer** (write-time hooks + read-time redaction) is architecturally sound
8. **Agent activation triggers** ("Activate for...") in descriptions follow Anthropic's Agent Skills Specification
