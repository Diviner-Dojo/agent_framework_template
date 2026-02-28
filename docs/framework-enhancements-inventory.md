# Framework Enhancements: Complete Inventory

The project started from commit `3b78c9d "Initial commit: Agent Framework Template"` and has grown through **37 commits** across ~7 days. The template provided the *directory structure concept* and *four-layer capture stack design*. Nearly everything else is custom.

## Agents (10 custom definitions)

| Agent | Model Tier | Key Enhancement |
|---|---|---|
| `facilitator` | opus | 7 responsibilities, collaboration mode selection, persona bias detection |
| `architecture-consultant` | opus | ADR validation, boundary enforcement, Principle #8 embedded |
| `security-specialist` | sonnet | OWASP Top-10, trust boundary analysis, adversarial mode scoping |
| `qa-specialist` | sonnet | 6 edge-case categories, anti-pattern: no 100% coverage demands |
| `performance-analyst` | sonnet | Algorithmic complexity, hot path analysis, anti-premature-optimization |
| `independent-perspective` | sonnet | Pre-mortem analysis, Protocol Marginal Value Assessment (queries `protocol_yield`) |
| `docs-knowledge` | sonnet | Self-healing documentation concept, Write tool access |
| `educator` | haiku | Bloom's taxonomy quiz, mastery tier tracking, adaptive intensity |
| `project-analyst` | sonnet | Only subagent that orchestrates other subagents (scout + dispatch) |
| `ux-evaluator` | sonnet | Material 3 compliance, WCAG AA, Flutter/Android-specific checks |

Every agent has: Anti-Patterns section, Persona Bias Safeguard, structured output format (all adopted from external project analyses).

## Commands (13 slash commands)

| Command | Purpose |
|---|---|
| `/review` | Multi-agent code review with risk-tiered specialist assembly |
| `/build_module` | Module construction with mid-build checkpoint reviews |
| `/deliberate` | Structured multi-agent discussion on any topic |
| `/analyze-project` | External project analysis with 5-dimension scoring rubric |
| `/retro` | Sprint retrospective with protocol value assessment |
| `/meta-review` | Quarterly framework evaluation with double-loop checks |
| `/plan` | Spec-driven feature planning with specialist review |
| `/walkthrough` | Education gate step 1 |
| `/quiz` | Education gate step 2 (Bloom's taxonomy) |
| `/promote` | Layer 3 memory promotion (requires human approval) |
| `/onboard` | Project takeover protocol with debt ledger |
| `/discover-projects` | GitHub repo discovery for analysis candidates |
| `/batch-evaluate` | Batch evaluate PENDING pattern adoptions |

All commands have: CRITICAL BEHAVIORAL RULES, Pre-Flight Checks, `state.json` session resumption, full capture pipeline integration.

## Hooks (7 automation hooks)

| Hook | Trigger | Function |
|---|---|---|
| `validate_tool_use.py` | PreToolUse (Write/Edit) | File locking (120s expiry) + protected file blocking + 12-pattern secret scanning |
| `release_lock.py` | PostToolUse (Write/Edit) | Session-aware lock release |
| `pre-commit-gate.sh` | PreToolUse (git commit) | Quality gate reminder with 5-min verification cache |
| `pre-push-main-blocker.sh` | PreToolUse (git push) | Blocks direct push to main/master |
| `auto-format.sh` | PostToolUse (Write/Edit) | Auto-formats Python files with ruff |
| `pre-compact.ps1` | PreCompact | Prompts BUILD_STATUS.md update before context compaction |
| `session-start.ps1` | SessionStart | Reads BUILD_STATUS.md on resume |

## Rules (7 auto-loaded standards)

- `build_review_protocol.md` — 7 checkpoint trigger categories, 2-round max, exempt task list
- `coding_standards.md` — Dart/Flutter + Python conventions
- `commit_protocol.md` — 4-step commit gate (quality -> review -> education -> status update)
- `documentation_policy.md` — What/where/format for all artifacts
- `review_gates.md` — 4 risk tiers (Low->Critical) with agent count and specialist triggers
- `security_baseline.md` — Flutter/Dart security standards (drift, flutter_secure_storage, Supabase RLS)
- `testing_requirements.md` — 80% coverage target, isolation, organization, tags

## Scripts (14 Python utilities)

- **Capture pipeline**: `create_discussion.py`, `write_event.py`, `close_discussion.py`, `generate_transcript.py`, `ingest_events.py`, `ingest_reflection.py`
- **Metrics**: `record_yield.py` (protocol yield), `record_education.py` (education gate results)
- **Quality**: `quality_gate.py` (6 checks: format, lint, test, coverage, ADR completeness, review existence)
- **Database**: `init_db.py` (6 tables, 12 indexes, migration guards)
- **Security**: `redact_secrets.py` (16 patterns, read-time redaction for `/analyze-project`)
- **Safety**: `backup_utils.py` (backup-before-modify, one-command rollback, 90-day prune)

## ADRs (16 architectural decisions)

6 framework-level (ADR-0001, 0007-0011) + 10 application-level (ADR-0002-0006, 0012-0015, 0017)

## Discussions & Capture

**50+ discussions** across: 10 project analyses, 10+ reviews, 5 retros, 4 builds, 5 spec reviews, 8 education sessions, 1 meta-review, 1 deliberation

## Knowledge from External Project Analysis

7 projects analyzed (ContractorVerification, CritInsight, claude-agentic-framework, wshobson/agents, self-learning-agent, agenticakm, self-improving-coding-agent). **59 patterns evaluated, 20 adopted, 5 confirmed**. Key imports:

- **File locking + secret detection** <- claude-agentic-framework + wshobson/agents
- **Session continuity hooks** (pre-compact/session-start) <- CritInsight + ContractorVerification
- **Auto-format hook** <- CritInsight
- **Pre-commit gate + push blocker** <- claude-agentic-framework
- **Secret redaction + backup utilities** <- self-learning-agent
- **Model-tier agent assignments** <- CritInsight (Rule of Three: 4 sightings)
- **Anti-Patterns sections in agents** <- self-improving-coding-agent
- **CRITICAL BEHAVIORAL RULES + Pre-flight checks in commands** <- wshobson/agents
- **Session resumption via state.json** <- wshobson/agents
- **ADR completeness check** <- AgenticAKM
- **Intervention complexity hierarchy** (Principle #8) <- self-improving-coding-agent
- **Adoption audit feedback loop** (PENDING/CONFIRMED/REVERTED) <- self-improving-coding-agent

## What Came from the Template Baseline

The initial commit (`3b78c9d`) provided:

- The directory structure concept (`.claude/agents/`, `.claude/commands/`, `.claude/rules/`, `.claude/skills/`, `discussions/`, `memory/`, `metrics/`, `scripts/`, `docs/adr/`)
- The four-layer capture stack conceptual design (Layer 1-4)
- The collaboration mode spectrum concept
- Starter `CLAUDE.md` (heavily rewritten)
- Starter agent definitions (heavily customized)
- Starter skill files (`security-checklist`, `testing-playbook`, `performance-playbook`, `python-project-patterns` — still reference Python/FastAPI, predating the Flutter pivot)

Everything else listed above was built on top of that skeleton.
