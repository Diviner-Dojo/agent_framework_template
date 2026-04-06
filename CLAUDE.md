# Project Constitution

## Project Identity

- **Framework**: AI-Native Agentic Development Framework v3.4
- **Tech Stack**: Python 3.11+, FastAPI, SQLite, pytest
- **Formatting**: ruff
- **Typing**: strict (all public functions have type annotations)
- **Testing**: pytest with >=80% coverage target
- **Dependencies**: managed via pyproject.toml + requirements.txt

## Non-Negotiable Principles

1. **Reasoning is the primary artifact.** Code is output. Deliberation, trade-offs, and decision lineage are the durable assets. Every significant decision must be traceable to the discussion that produced it.
2. **Capture must be automatic.** The capture system uses structured commands that guarantee event-level recording. The model cannot opt out of logging. Enforced at the command/tooling layer.
3. **Collaboration precedes adversarial rigor.** Multi-perspective analysis is the default. Adversarial modes are scoped exclusively to: security review (red-teaming), fault injection/stress testing, anti-groupthink checks.
4. **Independence prevents confirmation loops.** The agent that generates code must not be the sole evaluator. At minimum, one specialist who did not participate in generation must perform independent review.
5. **ADRs are never deleted.** Only superseded with references to the replacing decision. This creates an immutable decision history.
6. **Education gates before merge.** Walkthrough, quiz, explain-back, then merge. Proportional to complexity and risk. Deferrals require developer acknowledgment and must be logged in the retro. Deferred gates must be completed before the next phase begins, or formally re-deferred with documented rationale.
7. **Layer 3 promotion requires human approval.** No discussion insight is promoted automatically.
8. **Least-complex intervention first.** When improving the framework, prefer prompt changes before command/tool changes before agent definition changes before architectural changes. Lower-complexity interventions are cheaper, more reversible, and faster to validate. Only escalate to structural changes when simpler interventions have been tried or are demonstrably insufficient.

## Architectural Boundaries

### Four-Layer Capture Stack
- **Layer 1 — Immutable Files**: `discussions/` — events.jsonl + transcript.md, sealed after closure
- **Layer 2 — Relational Index**: `metrics/evaluation.db` — SQLite for querying and metrics
- **Layer 3 — Curated Memory**: `memory/` — human-approved patterns and rules
- **Layer 4 — Optional Vector**: Only when corpus grows large enough

### Agent Architecture

#### Leadership Hierarchy
- **Steward** (`steward.md`): Framework philosopher-guardian. Evaluates agent definition changes, rule modifications, and philosophy evolution. Also maintains framework lineage tracking. Does not participate in day-to-day reviews — only activated for framework evolution and lineage decisions. Cannot dispatch other agents (no Task tool). See `PHILOSOPHY.md` for the values the steward protects.
- **Facilitator** (`facilitator.md`): Team leader and workflow orchestrator. Leads specialists through insightful guidance, contextual dispatch, and rigorous synthesis. The single orchestrator for all multi-agent workflows.
- **Specialists**: 10 domain agents, each with a distilled Values section (load-bearing beliefs) and a procedural Domain Lens (reasoning sequence applied before analysis). Equal in standing, different in strengths.

#### Agent Roster (12 agents)

| Agent | Model | Role |
|-------|-------|------|
| steward | opus | Framework philosopher-guardian + lineage tracking |
| facilitator | opus | Team leader, workflow orchestrator |
| architecture-consultant | opus | Structural integrity, ADR validation, boundary enforcement |
| independent-perspective | opus | Anti-groupthink, cross-domain innovation, multi-instance (4 types) |
| security-specialist | sonnet | Vulnerability identification, threat modeling, auth review |
| qa-specialist | sonnet | Test coverage, edge cases, reliability, regression prevention |
| performance-analyst | sonnet | Latency, resource efficiency, scalability, cost |
| docs-knowledge | sonnet | Team Historian — decision traceability, knowledge flow, documentation |
| ux-evaluator | sonnet | The User in the Room — interaction flow, emotional design, accessibility |
| project-analyst | sonnet | External project analysis, cross-domain discovery pipeline |
| educator | sonnet | The Coach — walkthroughs, quizzes, mastery tracking |
| history-analyst | sonnet | Git history context — churn, refactors, reverts, blame (--deep only) |

#### Orchestration Rules
- Subagents CANNOT spawn other subagents, except the **project-analyst** which serves as a delegated orchestrator for `/analyze-project`
- The facilitator (main agent) orchestrates all other multi-agent workflows
- Multiple subagents can run concurrently with true parallelism
- Each subagent gets its own isolated context window

#### Model Override
The facilitator may override an agent's default model tier upward (sonnet → opus) when the task demands deeper reasoning. All overrides are recorded with `model:<tier>` tags in event capture for retrospective analysis.

#### Cross-Agent Collaboration Protocols
- **Cross-Agent Dispatch** (`.claude/rules/cross_agent_dispatch_protocol.md`): Any specialist can request dispatch of another agent through the facilitator. All requests captured with `dispatch-request` / `dispatch-decision` tags.
- **Multi-Instance Dispatch** (`.claude/rules/multi_instance_protocol.md`): Specialists can request parallel instance splits. Independent-perspective has pre-approved multi-instance dispatch with 4 instance types (Independent Analyst, Team Observer, Research Scout, Process Critic). All others need facilitator approval. Max 3 instances per agent per review.
- **Discovery Pipeline**: independent-perspective (Research Scout) → project-analyst → docs-knowledge chain for cross-domain innovation capture.

#### Agent Improvement Path
1. Facilitator observes a pattern across multiple reviews
2. Facilitator proposes a specific change with evidence
3. Steward evaluates against framework philosophy and principles
4. Developer approves the change
5. Change goes through `/review` like any code change

### Collaboration Mode Spectrum (facilitator selects per change)
1. **Ensemble** — independent contribution, no inter-agent exchange (lightest)
2. **Yes, And** — collaborative building, each agent builds on previous
3. **Structured Dialogue** — coopetitive exchange with multi-round discussion (default for significant changes)
4. **Dialectic Synthesis** — thesis-antithesis-synthesis with ACH matrix (high-stakes decisions)
5. **Adversarial** — red team, scoped to security/fault-injection/anti-groupthink only

### Exploration Intensity (orthogonal to collaboration mode)
- **Low**: Primary analysis with brief notes on alternatives
- **Medium**: 2-3 alternatives with trade-off analysis (default)
- **High**: Thorough exploration of alternatives, edge cases, failure modes

## ID Format Conventions

- **Discussion**: `DISC-YYYYMMDD-HHMMSS-slug`
- **ADR**: `ADR-NNNN` (zero-padded sequential)
- **Review**: `REV-YYYYMMDD-HHMMSS`
- **Reflection**: `REFL-YYYYMMDD-HHMMSS-agent`
- **Analysis**: `ANALYSIS-YYYYMMDD-HHMMSS-slug`

## Artifact Format Standard

All structured artifacts use **YAML frontmatter + Markdown body**:
```
---
key: value
---

## Section
Content here.
```

## Directory Layout

```
.claude/
  agents/       — Agent definitions (12: steward + facilitator + 10 specialists)
  commands/     — Slash command workflows (17 commands)
  custodian/    — Steward lineage tracking (lineage-events.jsonl, vouchers/)
  hooks/        — Automated lifecycle hooks (7 hooks: format, locking, secrets, commit-gates, session-lifecycle)
  rules/        — Auto-loaded standards (includes cross-agent and multi-instance protocols)
  skills/       — Reference knowledge (playbooks, checklists)
docs/
  adr/          — Architecture Decision Records
  reviews/      — Structured review reports
  sprints/      — Sprint plans and retrospectives
  templates/    — Reusable artifact templates
discussions/    — Layer 1: Immutable discussion capture
memory/         — Layer 3: Curated promoted knowledge
  archive/      — Superseded or deprecated knowledge
  bugs/         — Regression ledger tracking fixed bugs and their regression tests
  decisions/    — Promoted decision summaries
  lessons/      — Adoption log and external project patterns
  patterns/     — Promoted code and process patterns
  projects/     — Solution-path knowledge base (TAXONOMY.md, _self.md, project profiles)
  reflections/  — Promoted agent reflections
  rules/        — Promoted rules (graduated to .claude/rules/)
metrics/        — Layer 2: SQLite relational index + JSONL trend logs
                  quality_gate_log.jsonl, knowledge_pipeline_log.jsonl,
                  deploy_log.jsonl, emulator_test_log.jsonl
scripts/        — Capture pipeline utilities + quality gate
  lineage/      — Lineage tracking utilities (manifest, drift, init)
src/            — Application source code
tests/          — Test suite
framework-lineage.yaml — Lineage manifest (project-template relationship)
PHILOSOPHY.md   — Framework philosophy: why we work the way we do
REVIEW.md       — Review-specific rules (injected into specialist prompts during /review, see ADR-0006)
BUILD_STATUS.md — Session state persistence (read at start, update before compaction)
```

## External Project Analysis

The `/analyze-project` command points the specialist team outward — at any external project (local or GitHub) — to evaluate patterns worth adopting. The `/discover-projects` command finds candidates via GitHub search.

Analysis results are scored on a 5-dimension rubric (prevalence, elegance, evidence, fit, maintenance) out of 25. Only patterns scoring >= 20/25 are recommended. The adoption log at `memory/lessons/adoption-log.md` tracks all evaluated patterns across analyses and enforces the Rule of Three: patterns seen in 3+ independent projects get priority consideration.

## Lineage Tracking

The Steward agent manages framework lineage — tracking how derived projects relate to the canonical template. The `framework-lineage.yaml` manifest at the project root encodes the project's fork point, drift status, divergence distance, and pinned traits (intentional divergences).

Key commands:
- `/lineage` — Show drift status, validate manifest, generate drift reports
- `python scripts/lineage/init_lineage.py --project-name NAME --template-version VERSION` — Initialize lineage tracking

Lineage events are recorded in `.claude/custodian/lineage-events.jsonl` (append-only). SQLite tables `lineage_nodes` and `lineage_file_drift` provide queryable lineage data. See `docs/STEWARD_ARCHITECTURE.md` for the full five-phase roadmap and `docs/adr/ADR-0002-adopt-steward-agent.md` for the adoption decision.

## Quality Gate

Before declaring work complete, run the quality gate to verify all documented standards:
```
python scripts/quality_gate.py
```
This checks: formatting (ruff format), linting (ruff check), tests (pytest), coverage (>= 80%), ADR completeness, review existence (for code changes), regression ledger (verifies guard tests exist for known bugs), and BUILD_STATUS.md freshness (advisory only — warns but does not block). Use `--fix` to auto-fix formatting and lint issues. Use `--skip-*` flags to skip individual checks (e.g., `--skip-reviews` to bypass the review existence check, `--skip-regression` to bypass the regression ledger check).

Each run appends a JSONL record to `metrics/quality_gate_log.jsonl` for trend analysis. The independent-perspective agent uses this data during retro and meta-review to assess protocol marginal value.

## Error Handling

The recommended error handling pattern uses a structured exception hierarchy with centralized handling. All application errors should inherit from an `AppError` base class carrying `(message, error_code, details, status_code)`. Projects extend the hierarchy with domain-specific subclasses. Routes raise semantic exceptions (e.g., `NotFoundError("todo", id)`) — a centralized handler converts them to consistent JSON responses. See `.claude/skills/python-project-patterns/SKILL.md` for implementation guidance.

## Hooks

The project uses Claude Code hooks (configured in `.claude/settings.json`) for automated lifecycle actions:

### PreToolUse Hooks
- **File Locking + Secret Detection + Protected Files** (`.claude/hooks/pre-tool-use-validator.sh` → `validate_tool_use.py`): On Write/Edit — acquires atomic file locks (prevents concurrent agent edits, 120s auto-expiry), blocks edits to protected files (.env, .git/, evaluation.db, .claude/settings.json), scans content for 12 secret patterns (API keys, AWS keys, JWT, GitHub PATs, private keys, exported secrets, Slack tokens, Bearer tokens, Anthropic keys, OpenAI keys, GCP API keys, GCP OAuth tokens). Test files are exempt from secret scanning.
- **Pre-Commit Quality Gate** (`.claude/hooks/pre-commit-gate.sh`): On `git commit` — injects reminder to run `python scripts/quality_gate.py` before committing. Uses 5-minute verification cache to avoid repetition.
- **Pre-Push Main Blocker** (`.claude/hooks/pre-push-main-blocker.sh`): On `git push` — blocks direct pushes to main/master branch with remediation instructions for branch-based workflow.

### PostToolUse Hooks
- **Auto-Format** (`.claude/hooks/auto-format.sh`): Runs `ruff format` + `ruff check --fix` on any Python file after every Edit or Write.
- **Lock Release** (`.claude/hooks/post-tool-use-unlock.sh` → `release_lock.py`): Releases file locks after Write/Edit completes.

### Session Hooks
- **PreCompact** (`.claude/hooks/pre-compact.ps1`): Before context compaction, prompts the agent to update `BUILD_STATUS.md` with current task state.
- **SessionStart** (`.claude/hooks/session-start.ps1`): On session resume or post-compaction, prompts the agent to read `BUILD_STATUS.md` and runs a 6-point process health dashboard: retro age, open retro actions, pending adoptions, promotion candidates, stale specs, and Layer 3 health.

### User Notification Hook (Optional)
- **Notification**: Fires a system notification when Claude Code completes a task. Platform-specific setup required — see `docs/setup/notification-hook.md` for Windows (BurntToast), macOS (osascript), and Linux (notify-send) instructions.

`BUILD_STATUS.md` is session-scoped working state at the project root. It is ephemeral and distinct from the four-layer capture stack — it preserves in-flight context across sessions rather than capturing completed decisions. Open advisories from reviews should be accumulated in BUILD_STATUS.md so they persist across sessions until addressed — this prevents advisory findings from being lost when review reports are closed.

## Push Notifications

The framework supports push notifications to the developer's phone/desktop via [ntfy.sh](https://ntfy.sh) when long-running tasks complete. This follows the BYOK (bring your own key) pattern — the mechanism is committed, the destination is in `.env`.

**Setup**: Copy `.env.example` to `.env` and set `NTFY_TOPIC` to your unique topic slug. Subscribe to the same topic in the ntfy app (iOS/Android/web). See `.env.example` for full setup instructions.

**Usage**:
- CLI: `python scripts/notify.py "Build complete" --title "MyProject"`
- Library: `from scripts.notify import send_notification; send_notification("Done")`
- Integrated: `close_discussion.py` sends a notification automatically when discussions are sealed.

**Design principles**:
- Best-effort — notification failures never block the calling script
- stdlib only (urllib) — no pip dependencies
- Topic slug is the only authentication — treat it like a secret, store in `.env`
- Keep notification messages generic (e.g., "Build complete", "Review finished") — ntfy.sh is a public relay by default, so avoid including file paths or internal IDs in payloads
- Supports custom server (`NTFY_SERVER`) and token auth (`NTFY_TOKEN`) for self-hosted setups

## Commit Protocol

Every commit must pass two gates:

1. **Quality Gate** (automated via git pre-commit hook): `python scripts/quality_gate.py` runs automatically before every `git commit`. If formatting, linting, tests, or coverage fail, the commit is blocked.
2. **Code Review** (agent-assisted): Run `/review <files>` before committing to get multi-agent specialist review. The review produces a verdict (approve / approve-with-changes / request-changes / reject) and a structured report in `docs/reviews/`. Supports auto-scope detection (PR diff, staged, unstaged, HEAD~1), `--cost low|medium|high` for model tier routing, `--deep` for git history analysis, and `--comment` for PR comment posting. Includes facilitator finding verification, confidence annotation (no findings suppressed), REVIEW.md rule injection into all specialist prompts, and self-healing documentation suggestions.

For low-risk changes (config, docs, simple fixes), the quality gate alone may suffice. For any code change, always run `/review` first. Framework-only changes (`.claude/`, `scripts/`, `docs/`) touching more than 5 files require `/review` — large framework changes are medium-risk regardless of whether they touch product code.

## Build Review Protocol

During `/build_module`, mid-build checkpoint reviews enforce Principle #4 (independence) within the build itself — not just at commit time. When a build task matches a trigger category (new module, architecture choice, database schema, security-relevant code, API routes, external API integration, UI flow changes), the facilitator dispatches exactly 2 specialists for a focused checkpoint review.

Checkpoints are capped at 2 iterations per task (Round 1 → optional Round 2). Unresolved concerns after Round 2 are captured and surfaced in the build summary but do not block the build. After checkpoints, specialists who gave REVISE verdicts are asked for 150-word reflections (what they missed, improvement rules, confidence calibration). See `.claude/rules/build_review_protocol.md` for trigger categories, exempt tasks, and the specialist prompt template.

## Capture Pipeline

When a `/review`, `/deliberate`, `/build_module`, `/plan`, `/retro`, `/meta-review`, or `/lineage` command runs:
1. `scripts/create_discussion.py` creates the discussion directory and registers it in SQLite (with `command_type` inferred from slug prefix)
2. Each agent turn is captured via `scripts/write_event.py` to events.jsonl
2a. After `/review` checkpoints, specialists who gave REVISE verdicts are dispatched for reflections; results are ingested into SQLite via `scripts/ingest_reflection.py`. Education gate results are recorded via `scripts/record_education.py`.
3. `scripts/close_discussion.py` seals the discussion:
   - `scripts/generate_transcript.py` converts events.jsonl → transcript.md
   - `scripts/ingest_events.py` inserts events into SQLite (Layer 2), including searchable `content_excerpt` and `tags`
   - Updates discussion status to `closed` in SQLite (with `duration_minutes`)
   - `scripts/extract_findings.py` parses events for structured findings (severity, category, summary)
   - `scripts/mine_patterns.py` clusters similar findings using Jaccard similarity
   - `scripts/surface_candidates.py` identifies recurring patterns for promotion queue
   - `scripts/compute_agent_effectiveness.py` computes per-agent uniqueness/survival metrics
   - Sets discussion directory to read-only
4. `scripts/record_yield.py` records protocol yield metrics (blocking/advisory finding counts, agent turns, outcome) into the `protocol_yield` table. Called at synthesis time in `/review`, `/build_module`, and `/retro`.
5. Each `python scripts/quality_gate.py` run appends a JSONL record to `metrics/quality_gate_log.jsonl` for trend analysis.
6. `/knowledge-health` runs `scripts/knowledge_dashboard.py` to report on all pipeline layers and append to `metrics/knowledge_pipeline_log.jsonl`.

**Context-brief events** (turn_id=1, agent="facilitator", tags="context-brief") are emitted by: /review, /deliberate, /build_module, /plan, /retro. Excluded: /analyze-project (outward-facing scouting, no developer request context), /meta-review (aggregate analysis, no single request context).

**New SQLite tables**: `findings`, `promotion_candidates`, `pattern_sightings`, `agent_effectiveness`, `lineage_nodes`, `lineage_file_drift`
**New SQLite views**: `v_rule_of_three`, `v_agent_dashboard`
**New columns**: `turns.content_excerpt`, `turns.tags`, `discussions.command_type`, `discussions.duration_minutes`, `discussions.related_discussion_id`

## Known Limitations

Document known data quality issues, extraction rate baselines, and enforcement gaps here as they are discovered. This section prevents the same limitations from being rediscovered across sessions.

- The pre-commit hook does not support `--skip-reviews` passthrough — the quality gate's review existence check cannot be bypassed from `git commit` arguments
- The pre-commit hook's regression ledger check and review reminder are suppressed during the 5-minute verification cache window after a quality gate run. Stale cache entries may cause these checks to be silently skipped.

## Autonomous Execution Authorization

This section uses a structured format for scoping autonomous execution. Derived projects should customize by uncommenting and filling in the sections below.

### Authorization Format

```markdown
**Branch scope**: [branch pattern, e.g., "feature/*", "lab/*", or "all"]
**Effective**: [date or "until revoked"]

#### Authorized Actions (no confirmation needed)
- [action 1, e.g., "Run pytest and quality_gate.py"]
- [action 2, e.g., "Run ruff format and ruff check --fix"]
- [action 3, e.g., "Create branches, stage files, and commit"]

#### Prohibited Actions (always require confirmation)
- [action 1, e.g., "git push to any remote"]
- [action 2, e.g., "Destructive git operations (reset --hard, clean -f, branch -D)"]
- [action 3, e.g., "Modifying .claude/settings.json"]
```

IMPORTANT: Enabling autonomous execution authorizes executing the **full workflow** without pausing for permission at each step. It does NOT authorize skipping steps. See `.claude/rules/autonomous_workflow.md` for the mandatory workflow sequence.

<!-- Uncomment and customize for your project:

**Branch scope**: all
**Effective**: until revoked

#### Authorized Actions
- Run `pytest` and `python scripts/quality_gate.py` without confirmation
- Run `ruff format` and `ruff check --fix` without confirmation
- Run `python scripts/init_db.py` without confirmation
- Run knowledge pipeline scripts without confirmation
- Create branches, stage files, and commit (but NOT push or force-push)

#### Prohibited Actions
- `git push` to any remote
- Destructive git operations (reset --hard, clean -f, branch -D)
- Modifying `.claude/settings.json`
- Deleting files outside of `memory/archive/`
- Any operation affecting production environments
-->

## Domain Safety Constraints

<!-- Uncomment and customize for your project. If your domain has safety constraints
     that must be treated as blocking review findings (medical, financial, accessibility,
     privacy, etc.), declare them here. Review specialists read CLAUDE.md as context,
     so constraints declared here are enforced at blocking-finding severity.

     Example for a medical journaling app:
     - Clinical language must never be used in user-facing text (blocking)
     - Emotional state labels must use validated psychological scales only (blocking)
     - No diagnostic or prescriptive language in AI-generated responses (blocking)

     Example for a financial app:
     - All monetary calculations must use decimal types, never floating point (blocking)
     - Transaction amounts must be validated against account balance before processing (blocking)

     Declare your domain constraints below:
-->

## Framework Evolution

Changes to agent definitions, rules, or framework philosophy follow a gated path:

1. **Observation**: Facilitator identifies a pattern across multiple reviews
2. **Proposal**: Development note with evidence, diagnosis, and proposed change
3. **Steward Gate**: Steward evaluates alignment with `PHILOSOPHY.md` and principles — verdicts: APPROVE / REVISE / DEFER / DECLINE
4. **Developer Approval**: Human gate preserved (Principle #7)
5. **Review**: Change goes through `/review` like any code change
6. **Documentation Sync**: Verify downstream documentation artifacts are updated per `.claude/rules/framework_doc_sync.md`

The Steward is activated only for framework evolution — not for day-to-day reviews.

## Agent Invocation Pattern

Commands invoke specialist agents via the Task tool:
```
Task(subagent_type="agent-name", prompt="...")
```

Model override (facilitator only, for harder tasks):
```
Task(subagent_type="agent-name", model="opus", prompt="...")
```

All agent turns are captured with `model:<tier>` tags for retrospective analysis.
The facilitator collects all results and synthesizes a unified report.
