# Project Constitution

## Project Identity

- **Framework**: AI-Native Agentic Development Framework v2.1
- **Tech Stack**: Flutter 3.x + Dart, Riverpod, drift, Supabase, dio
- **Formatting**: `dart format`
- **Typing**: Dart's built-in type system (strict, sound null safety)
- **Testing**: `flutter test` with >=80% coverage target
- **Dependencies**: managed via `pubspec.yaml`

## Non-Negotiable Principles

1. **Reasoning is the primary artifact.** Code is output. Deliberation, trade-offs, and decision lineage are the durable assets. Every significant decision must be traceable to the discussion that produced it.
2. **Capture must be automatic.** The capture system uses structured commands that guarantee event-level recording. The model cannot opt out of logging. Enforced at the command/tooling layer.
3. **Collaboration precedes adversarial rigor.** Multi-perspective analysis is the default. Adversarial modes are scoped exclusively to: security review (red-teaming), fault injection/stress testing, anti-groupthink checks.
4. **Independence prevents confirmation loops.** The agent that generates code must not be the sole evaluator. At minimum, one specialist who did not participate in generation must perform independent review.
5. **ADRs are never deleted.** Only superseded with references to the replacing decision. This creates an immutable decision history.
6. **Education gates before merge.** Walkthrough, quiz, explain-back, then merge. Proportional to complexity and risk.
7. **Layer 3 promotion requires human approval.** No discussion insight is promoted automatically.
8. **Least-complex intervention first.** When improving the framework, prefer prompt changes before command/tool changes before agent definition changes before architectural changes. Lower-complexity interventions are cheaper, more reversible, and faster to validate. Only escalate to structural changes when simpler interventions have been tried or are demonstrably insufficient.

## Architectural Boundaries

### Four-Layer Capture Stack
- **Layer 1 — Immutable Files**: `discussions/` — events.jsonl + transcript.md, sealed after closure
- **Layer 2 — Relational Index**: `metrics/evaluation.db` — SQLite for querying and metrics
- **Layer 3 — Curated Memory**: `memory/` — human-approved patterns and rules
- **Layer 4 — Optional Vector**: Only when corpus grows large enough

### Agent Architecture
- Subagents CANNOT spawn other subagents, except the **project-analyst** which serves as a delegated orchestrator for `/analyze-project` (it scouts the target project, then dispatches domain specialists to evaluate applicability)
- The facilitator (main agent) orchestrates all other multi-agent workflows
- Multiple subagents can run concurrently with true parallelism
- Each subagent gets its own isolated context window
- Agents declare a `model:` tier in their YAML frontmatter for cost optimization:
  - **opus**: Complex generation and architectural reasoning (facilitator, architecture-consultant)
  - **sonnet**: Analysis, review, and evaluation (security-specialist, qa-specialist, performance-analyst, independent-perspective, docs-knowledge, project-analyst, ux-evaluator)
  - **haiku**: Mechanical verification and lightweight tasks (educator)

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
  agents/       — Specialist agent definitions (10 core, including project-analyst and ux-evaluator)
  commands/     — Slash command workflows (12 commands)
  hooks/        — Automated lifecycle hooks (7 hooks: format, locking, secrets, commit-gates, session-lifecycle)
  rules/        — Auto-loaded standards (all agents inherit)
  skills/       — Reference knowledge (playbooks, checklists)
android/        — Android platform code (Kotlin, manifest, assistant registration)
ios/            — iOS platform code
lib/            — Application source code (Flutter/Dart)
test/           — Test suite (Flutter tests)
integration_test/ — Integration tests
supabase/       — Supabase migrations and Edge Functions
docs/
  adr/          — Architecture Decision Records
  reviews/      — Structured review reports
  sprints/      — Sprint plans and retrospectives
  templates/    — Reusable artifact templates
discussions/    — Layer 1: Immutable discussion capture
memory/         — Layer 3: Curated promoted knowledge
  archive/      — Superseded or deprecated knowledge
  decisions/    — Promoted decision summaries
  lessons/      — Adoption log tracking patterns from external project reviews
  patterns/     — Promoted code and process patterns
  reflections/  — Promoted agent reflections
  rules/        — Promoted rules (graduated to .claude/rules/)
metrics/        — Layer 2: SQLite relational index + quality_gate_log.jsonl (trend data)
scripts/        — Capture pipeline utilities + quality gate (Python dev tools)
BUILD_STATUS.md — Session state persistence (read at start, update before compaction)
```

## External Project Analysis

The `/analyze-project` command points the specialist team outward — at any external project (local or GitHub) — to evaluate patterns worth adopting. The `/discover-projects` command finds candidates via GitHub search.

Analysis results are scored on a 5-dimension rubric (prevalence, elegance, evidence, fit, maintenance) out of 25. Only patterns scoring >= 20/25 are recommended. The adoption log at `memory/lessons/adoption-log.md` tracks all evaluated patterns across analyses and enforces the Rule of Three: patterns seen in 3+ independent projects get priority consideration.

## Quality Gate

Before declaring work complete, run the quality gate to verify all documented standards:
```
python scripts/quality_gate.py
```
This checks: formatting (`dart format`), linting (`dart analyze`), tests (`flutter test`), coverage (>= 80%), ADR completeness, and review existence (for code changes). Use `--fix` to auto-fix issues via `dart fix --apply`. Use `--skip-*` flags to skip individual checks (e.g., `--skip-reviews` to bypass review existence).

Each run appends a result record to `metrics/quality_gate_log.jsonl` for trend analysis at retro and meta-review time.

**Known limitation**: The review existence check verifies that a review report exists for today, not that it covers the specific files being committed.

## Error Handling

Error handling patterns TBD — will be defined during Phase 1 implementation. General principles: use Dart's typed exception system, catch specific exception types (never bare `catch`), and provide user-friendly error messages at the UI layer.

## Hooks

The project uses Claude Code hooks (configured in `.claude/settings.json`) for automated lifecycle actions:

### PreToolUse Hooks
- **File Locking + Secret Detection + Protected Files** (`.claude/hooks/pre-tool-use-validator.sh` → `validate_tool_use.py`): On Write/Edit — acquires atomic file locks (prevents concurrent agent edits, 120s auto-expiry), blocks edits to protected files (.env, .git/, evaluation.db, .claude/settings.json), scans content for 12 secret patterns (API keys, AWS keys, JWT, GitHub PATs, private keys, exported secrets, Slack tokens, Bearer tokens, Anthropic keys, OpenAI keys, GCP API keys, GCP OAuth tokens). Test files are exempt from secret scanning.
- **Pre-Commit Quality Gate** (`.claude/hooks/pre-commit-gate.sh`): On `git commit` — injects reminder to run `python scripts/quality_gate.py` before committing. Uses 5-minute verification cache to avoid repetition.
- **Pre-Push Main Blocker** (`.claude/hooks/pre-push-main-blocker.sh`): On `git push` — blocks direct pushes to main/master branch with remediation instructions for branch-based workflow.

### PostToolUse Hooks
- **Auto-Format** (`.claude/hooks/auto-format.sh`): Runs `dart format` on any Dart file after every Edit or Write.
- **Lock Release** (`.claude/hooks/post-tool-use-unlock.sh` → `release_lock.py`): Releases file locks after Write/Edit completes.

### Session Hooks
- **PreCompact** (`.claude/hooks/pre-compact.ps1`): Before context compaction, prompts the agent to update `BUILD_STATUS.md` with current task state.
- **SessionStart** (`.claude/hooks/session-start.ps1`): On session resume or post-compaction, prompts the agent to read `BUILD_STATUS.md` to restore working context.

`BUILD_STATUS.md` is session-scoped working state at the project root. It is ephemeral and distinct from the four-layer capture stack — it preserves in-flight context across sessions rather than capturing completed decisions.

## Commit Protocol

Every commit must pass two gates:

1. **Quality Gate** (automated via git pre-commit hook): `python scripts/quality_gate.py` runs automatically before every `git commit`. If formatting (`dart format`), linting (`dart analyze`), tests (`flutter test`), or coverage fail, the commit is blocked.
2. **Code Review** (agent-assisted): Run `/review <files>` before committing to get multi-agent specialist review. The review produces a verdict (approve / approve-with-changes / request-changes / reject) and a structured report in `docs/reviews/`.

For low-risk changes (config, docs, simple fixes), the quality gate alone may suffice. For any code change, always run `/review` first. Framework-only changes (`.claude/`, `scripts/`, `docs/`) touching more than 5 files require `/review` — large framework changes are medium-risk regardless of whether they touch product code.

## Build Review Protocol

The `/build_module` command integrates mid-build checkpoint reviews to enforce Principle #4 (independence) during code generation, not just at commit time. After each build task, the facilitator evaluates whether a checkpoint triggers based on trigger categories defined in `.claude/rules/build_review_protocol.md`:

- **Triggers**: new module, architecture choice, database schema, security-relevant code, state management wiring, external API integration, UI flow / navigation
- **Exempt**: scaffolding, dependency config, pure test writing, theme/style-only, docs, final verification
- **Protocol**: 2 specialists dispatched per checkpoint, APPROVE or REVISE (under 200 words), max 2 rounds — build continues after Round 2 regardless of outcome
- **Capture**: All checkpoint events go into the build's discussion via `write_event.py`
- **Unresolved concerns**: Flagged with `risk_flags: ["unresolved-checkpoint"]` and surfaced in the build summary
- **Plan mode boundary**: Multi-file builds executed via plan mode (3+ new files under `lib/`) must use `/build_module` — plan mode continuation does not substitute for checkpoint coverage

## Capture Pipeline

When a `/review`, `/deliberate`, `/analyze-project`, `/build_module`, `/retro`, or `/meta-review` command runs:
1. `scripts/create_discussion.py` creates the discussion directory and registers it in SQLite
2. Each agent turn is captured via `scripts/write_event.py` to events.jsonl
3. `scripts/close_discussion.py` seals the discussion:
   - `scripts/generate_transcript.py` converts events.jsonl → transcript.md
   - `scripts/ingest_events.py` inserts events into SQLite (Layer 2)
   - Updates discussion status to `closed` in SQLite
   - Sets discussion directory to read-only
4. `scripts/record_yield.py` records protocol yield metrics (blocking/advisory finding counts, agent turns, outcome) into the `protocol_yield` table. Called at synthesis time in `/review`, `/build_module`, and `/retro`.
5. Each `python scripts/quality_gate.py` run appends a JSONL record to `metrics/quality_gate_log.jsonl` for trend analysis.

**Known data quality**: Pre-migration discussions (before 2026-02-22) have NULL `duration_minutes` — backfill via `created_at`/`closed_at` is pending. The `protocol_yield` table had a duplicate-recording bug prior to the dedup guard added to `record_yield.py`.

## Agent Invocation Pattern

Commands invoke specialist agents via the Task tool:
```
Task(subagent_type="agent-name", prompt="...")
```
The facilitator collects all results and synthesizes a unified report.
