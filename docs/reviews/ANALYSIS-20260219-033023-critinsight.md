---
analysis_id: "ANALYSIS-20260219-033023-critinsight"
discussion_id: "DISC-20260219-032511-analyze-critinsight"
target_project: "critinsight"
target_language: "Python"
target_stars: "N/A"
agents_consulted: [project-analyst, architecture-consultant, security-specialist, qa-specialist, docs-knowledge, independent-perspective]
patterns_evaluated: 8
patterns_recommended: 3
analysis_date: "2026-02-19"
---

## Project Profile

- **Name**: CritInsight
- **Source**: critinsight (local project)
- **Tech Stack**: Python 3.12+, FastAPI, SQLAlchemy 2.0 (async), LiteLLM, Instructor, sqlglot, LanceDB, Plotly, Streamlit, Pydantic Settings, ARQ
- **Size**: ~42,400 LOC (23,600 source + 18,800 test) across 175 files
- **Maturity**: Very young (all commits within a single day — Feb 13, 2026; 5 commits). Comprehensive test suite (1,063 tests). Ruff + mypy strict. Docker compose. No CI/CD pipeline. `.env.example` present.
- **AI Integration**: Sophisticated — 3 Claude Code agents with model-tier assignment, 3 hooks (auto-format, pre-compact, session-start), 2 skills, session continuity via BUILD_STATUS.md

### Tech Stack Details

- FastAPI >=0.115.0 with Uvicorn
- LiteLLM >=1.55.0 (provider-agnostic LLM routing)
- Instructor >=1.7.0 (structured output with Pydantic validation)
- SQLAlchemy 2.0 async (aiosqlite + aioodbc)
- LanceDB >=0.14.0 (vector store for dev)
- sqlglot >=26.0 (SQL AST parsing for safety validation)
- cryptography >=43.0 (connection string encryption)
- Dev: pytest, pytest-asyncio, pytest-cov, mypy, ruff

### Key Files Examined

| File | Significance |
|------|-------------|
| `CLAUDE.md` | 214-line project context with session continuity protocol, build levels, coding standards, design rationale, spec-to-code mapping |
| `BUILD_STATUS.md` | Session-persistent state machine tracking development progress |
| `.claude/settings.json` | Hook configuration: PostToolUse auto-format, PreCompact state save, SessionStart context restore |
| `.claude/agents/component-builder.md` | Subagent with `model: opus` — demonstrates model-tier assignment |
| `.claude/agents/safety-auditor.md` | Subagent with `model: sonnet` |
| `.claude/agents/test-runner.md` | Subagent with `model: haiku` — cost optimization |
| `.claude/hooks/pre-compact.ps1` | Hook that reminds Claude to save state before context compaction |
| `.claude/hooks/session-start.ps1` | Hook that reminds Claude to read BUILD_STATUS.md on resume |
| `.claude/hooks/auto-format.sh` | Auto-runs ruff format + ruff check --fix after every file edit |
| `src/interfaces/protocols.py` | 288-line Protocol-based DI across 8 components |
| `src/interfaces/types.py` | 660-line shared type system (cross-component Pydantic models) |
| `src/pipeline/orchestrator.py` | 5-phase pipeline with context passing |
| `src/pipeline/factory.py` | Factory with optional DI (real or mock components) |
| `src/pipeline/models.py` | Pipeline context, phase results, metrics, graceful decline |
| `src/safety/validator.py` | 5-layer sequential validation with audit |
| `src/safety/parser.py` | sqlglot-based SQL parsing, injection detection |
| `src/safety/layers/base.py` | Abstract validation layer pattern |
| `src/config/settings.py` | Deeply nested Pydantic Settings with YAML defaults |
| `src/api/main.py` | FastAPI lifespan with factory-created pipeline |
| `src/api/dependencies.py` | Global mutable state DI (anti-pattern noted) |
| `specs/spec-query-safety.md` | NLSpec-driven development example |
| `tests/pipeline/conftest.py` | Mock infrastructure for 8 protocol-based components |

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.88)

CritInsight is an AI-assisted SQL analysis platform with multi-tenant support, 5-layer safety validation, and LLM-powered query generation. The project was built rapidly (all 5 commits in a single day) with AI agents, evidenced by its sophisticated Claude Code integration. Despite its youth, it has 1,063 tests and strict typing.

Seven patterns were identified in the initial survey: Session Continuity Hooks, Protocol-Based DI, 5-Layer Safety Validation, Build Levels, NLSpec-Driven Development, Model-Tier Agent Assignment, and Pipeline Context Object. Seven anti-patterns were also noted (see Anti-Patterns section).

### Architecture Consultant (confidence: 0.82)

Protocol-Based DI with Factory pattern is well-executed across 8 components via a 288-line `protocols.py`. Build Levels (L0/L1/L2) provide clean import boundaries that enable parallel subagent construction. Both patterns require a larger codebase to justify their overhead. Our framework at ~345 LOC source would be over-engineered with full protocol DI. Recommends deferring both until our project grows to 3+ independently decoupled components.

### Security Specialist (confidence: 0.85)

The 5-layer deterministic safety validation with an explicit "no LLM in the safety path" rule is sound security architecture. The abstract `BaseLayer` pattern with `_create_passed_result` / `_create_failed_result` helpers is generalizable. However, the tenant middleware does not validate tenant IDs at the middleware level (only at the dependency layer), and the global mutable state for DI in `dependencies.py` is a concurrency concern. The SQL-specific implementation is not transferable to our domain.

### QA Specialist (confidence: 0.80)

Protocol-matching mock infrastructure in `tests/pipeline/conftest.py` demonstrates comprehensive testing. Each mock implements the full protocol interface, enabling integration-level testing without external dependencies. 1,063 tests across 30+ files with co-located conftest mocks is impressive coverage. The conftest pattern of co-locating mocks with the tests that use them keeps test dependencies focused. Worth noting for when our project grows.

### Documentation & Knowledge (confidence: 0.83)

BUILD_STATUS.md as a session-persistent state machine is genuinely novel and solves a real problem (AI session continuity) with no equivalent in our framework. The NLSpec approach (specs/ directory with spec-to-code mapping table in CLAUDE.md) creates a traceable design-to-implementation pipeline. Recommends adopting session continuity pattern and a lightweight spec-to-code mapping table adaptation.

### Independent Perspective (confidence: 0.78)

The Claude Code hook system (auto-format, pre-compact, session-start) is the single most directly transferable pattern — requires no architectural changes and delivers immediate value. Model-tier agent assignment is also directly applicable.

**Hidden risk**: This project was built in a single day by AI agents. Patterns are optimized for AI-speed development, not human team collaboration. Some patterns that work beautifully for parallel agent construction may add unnecessary overhead in our context. The sophisticated infrastructure (8 protocols, 5 pipeline phases, 3 build levels) is justified by the project's complexity but should not be cargo-culted into simpler projects.

---

## Pattern Scorecard

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|---------|
| PostToolUse Auto-Format Hook | 5 | 5 | 4 | 5 | 5 | **24** | ADOPT |
| Model-Tier Agent Assignment | 4 | 5 | 3 | 5 | 5 | **22** | ADOPT |
| Session Continuity Hooks | 5 | 4 | 3 | 5 | 4 | **21** | ADOPT |
| Spec-to-Code Mapping Table | 4 | 4 | 3 | 4 | 4 | **19** | DEFER |
| Protocol-Based DI with Factory | 5 | 4 | 5 | 2 | 3 | **19** | DEFER |
| Pipeline Context Object | 4 | 4 | 3 | 2 | 3 | **16** | DEFER |
| Build Levels (L0/L1/L2) | 3 | 4 | 2 | 2 | 3 | **14** | SKIP |
| 5-Layer Safety Validation | 3 | 4 | 2 | 1 | 3 | **13** | SKIP |

**Sighting note**: Session Continuity Hooks is the 2nd sighting of a session persistence pattern (first seen as "Session Initialization Protocol" in ContractorVerification, scored 18/25 DEFERRED). The CritInsight implementation is more mature and automated via hooks. One more independent sighting triggers the Rule of Three bonus (+2).

---

## Recommended Adoptions

*Only patterns scoring >= 20/25.*

### PostToolUse Auto-Format Hook (Score: 24/25)

- **What**: A hook that automatically runs `ruff format` and `ruff check --fix` after every file edit, ensuring code is always formatted before the developer or other agents see it
- **Where it goes**: `.claude/settings.json` (hook config) + `.claude/hooks/auto-format.sh` (script)
- **Why it scored high**: Prevalence:5 (every Python project needs formatting), Elegance:5 (one hook, zero cognitive overhead), Evidence:4 (auto-format on save is an industry standard, just applied to Claude's edit model), Fit:5 (we already use ruff), Maintenance:5 (set and forget)
- **Implementation notes**: Add `PostToolUse` hook to settings.json that triggers on `Write` and `Edit` tool calls. Script runs `ruff format <file>` and `ruff check --fix <file>`. Reference: `critinsight/.claude\hooks\auto-format.sh`
- **Sightings**: 1 (first sighting)

### Model-Tier Agent Assignment (Score: 22/25)

- **What**: Assigns different Claude model tiers to agent definitions based on task complexity: Opus for complex code generation/architecture, Sonnet for analysis/review, Haiku for mechanical verification
- **Where it goes**: `.claude/agents/*.md` (add `model:` field to YAML frontmatter of each agent)
- **Why it scored high**: Prevalence:4 (common need for cost optimization), Elegance:5 (one line per agent file), Evidence:3 (emerging practice in multi-agent systems), Fit:5 (our 9 agents have no model tiers), Maintenance:5 (set once, update when model pricing changes)
- **Implementation notes**: Suggested tiers for our agents: `opus` for facilitator, architecture-consultant; `sonnet` for security-specialist, qa-specialist, performance-analyst, independent-perspective, docs-knowledge, project-analyst; `haiku` for educator. Reference: `critinsight/.claude\agents\component-builder.md`
- **Sightings**: 1 (first sighting)

### Session Continuity Hooks (Score: 21/25)

- **What**: Three-part system for maintaining context across Claude sessions: (1) PreCompact hook reminds Claude to save state before context window compaction, (2) SessionStart hook reminds Claude to read saved state on resume, (3) BUILD_STATUS.md acts as the persistent state file
- **Where it goes**: `.claude/hooks/pre-compact.ps1`, `.claude/hooks/session-start.ps1`, `BUILD_STATUS.md` (or integration with existing `docs/sprints/` directory)
- **Why it scored high**: Prevalence:5 (every AI-assisted project faces session continuity), Elegance:4 (simple hook mechanism, no custom tooling), Evidence:3 (emerging practice), Fit:5 (we have no equivalent), Maintenance:4 (BUILD_STATUS.md requires some manual upkeep, but hooks automate the reminders)
- **Implementation notes**: Adapt to our framework's existing capture infrastructure. Rather than a standalone BUILD_STATUS.md, consider integrating with our `docs/sprints/` directory or creating a lightweight `SESSION_STATE.md` at project root. Reference: `critinsight/.claude\hooks\pre-compact.ps1`, `critinsight/.claude\hooks\session-start.ps1`
- **Sightings**: 2 (previously seen as "Session Initialization Protocol" in ContractorVerification, scored 18/25 DEFERRED)

---

## Anti-Patterns & Warnings

*Things this project does that we should actively avoid.*

### God File (838-line registry)

- **What**: `src/tenant/registry.py` at 838 lines violates the project's own 300-line guideline
- **Where seen**: `critinsight/src\tenant\registry.py`
- **Why it's bad**: Accumulates during rapid AI-driven development. Hard to test, hard to review, high merge conflict risk
- **Our safeguard**: Our coding standards recommend ~50 lines per function. Monitor for file growth during rapid development sprints

### Global Mutable State for DI

- **What**: Module-level global variables set by `set_*` functions for dependency injection
- **Where seen**: `critinsight/src\api\dependencies.py` lines 28-55
- **Why it's bad**: Concurrency risk, testing hazard, makes import order matter
- **Our safeguard**: Use FastAPI's `app.state` or lifespan-scoped dependencies instead

### Private Member Access Breaking Abstractions

- **What**: `tenant_manager._conn_mgr` — accessing private attributes with `# noqa: SLF001` suppression
- **Where seen**: `critinsight/src\pipeline\factory.py` line 247
- **Why it's bad**: Breaks the protocol abstraction the rest of the codebase carefully maintains
- **Our safeguard**: Our coding standards enforce single underscore convention. If you need an attribute, make it part of the public interface

### Mock Fallbacks in Production Code

- **What**: LLM client has `_mock_structured_response` and mock fallback paths when dependencies are None
- **Where seen**: `critinsight/src\llm\client.py` lines 411-413, 511-529
- **Why it's bad**: Embeds test behavior in production code. Should use protocol injection instead
- **Our safeguard**: Our Principle #4 (independence) separates generation from evaluation. Keep test-only code in test files

### Deprecated API Usage (datetime.utcnow)

- **What**: Uses `datetime.utcnow()` throughout, deprecated since Python 3.12
- **Where seen**: Multiple files across the codebase
- **Why it's bad**: Returns naive datetime, ambiguous timezone. Use `datetime.now(timezone.utc)` instead
- **Our safeguard**: Use `datetime.now(timezone.utc)` consistently. Add to coding standards if needed

### No CI/CD Despite Comprehensive Tests

- **What**: 1,063 tests but no automated pipeline to run them
- **Where seen**: No `.github/workflows/`, no `Makefile`, no `tox.ini`
- **Why it's bad**: Quality checks are only as good as the discipline to run them manually
- **Our safeguard**: Our `scripts/quality_gate.py` provides local automation. Consider CI/CD when deploying

---

## Deferred Patterns

*Patterns scoring 15-19. Interesting but not ready for adoption.*

### Spec-to-Code Mapping Table (Score: 19/25)

- **What**: A table in CLAUDE.md that maps each component specification to its implementation files, enabling AI agents to quickly navigate from design intent to code
- **Why deferred**: Evidence:3 (only seen in AI-heavy workflows), Fit:4 (would be useful but our project is small enough that it's not yet needed)
- **Revisit if**: Our project grows to 10+ source modules, or we add NLSpec-style specification documents

### Protocol-Based DI with Factory (Score: 19/25)

- **What**: All components defined as Python Protocols. Factory creates real or mock implementations. Tests inject protocol-matching mocks
- **Why deferred**: Fit:2 (our project has ~345 LOC source — protocol DI would be over-engineering at this scale)
- **Revisit if**: We add 3+ components that need decoupling, or our test suite needs mock isolation across multiple services

### Pipeline Context Object (Score: 16/25)

- **What**: Mutable context object that accumulates state across pipeline phases, with metrics derivation and graceful decline (user-friendly error messages)
- **Why deferred**: Fit:2 (our framework uses a simpler sequential approach), Evidence:3 (common pattern but not standardized)
- **Revisit if**: We build a multi-stage processing pipeline (e.g., a multi-phase code review or analysis pipeline)

---

## Specialist Consensus

- **Agents that agreed**: All 5 specialists (architecture, security, QA, docs, independent) agreed on the top 3 patterns (Session Continuity Hooks, Model-Tier Assignment, Auto-Format Hook). 4/5 flagged session continuity as the most impactful
- **Notable disagreements**: Build Levels — architecture-consultant saw it as a strong pattern, independent-perspective argued it's optimized for greenfield AI-built projects and doesn't transfer to our established structure. Security and QA disagreed on the 5-Layer Safety Validation — security praised the architecture while QA noted the abstract pattern is transferable even if the SQL-specific implementation is not
- **Strongest signal**: The session continuity pattern (PreCompact + SessionStart + BUILD_STATUS.md) is the single most important finding. It is the 2nd independent sighting of a session persistence pattern, has strong specialist consensus (4/5), and fills a concrete gap in our framework with low adoption cost. One more sighting triggers the Rule of Three
