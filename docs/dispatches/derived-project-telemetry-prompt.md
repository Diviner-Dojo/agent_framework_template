# Derived-Project Telemetry Prompt

Paste the prompt below as the **first message** in a fresh Claude Code session inside each derived project (Howie Family Wiki, Insight Journal, any others). It runs a read-only usage survey against the local capture pipeline and returns a structured paste-back block.

**Purpose**: gather hub-vs-spoke usage data the template repo cannot see on its own. The output feeds the recalibrated synthesis at `docs/analysis/SYNTHESIS-20260515-adoption-brief.md` before the framework-level deliberation runs.

**Date**: 2026-05-15

---

## The prompt (copy from the fenced block below)

````markdown
You are running a usage telemetry survey for the hub framework template at
`c:\Work\AI\AI Gen Framework Research\agent_framework_template`. The developer
is recalibrating template-level adoption decisions and needs derived-project
usage data that doesn't exist in the template itself.

DO NOT MODIFY ANY FILES. Read-only. Produce a structured report at the end.

## Step 1 — Confirm you are in a template-derived project

Verify the following exist (don't fail if some are absent — note them):
- `.claude/agents/` with multiple agent definition files
- `.claude/commands/` with slash command files
- `.claude/rules/` with rule files
- `metrics/evaluation.db` (the Layer 2 SQLite from the four-layer capture stack)
- `CLAUDE.md` at the repo root
- `discussions/` directory

If three or more of these are missing, stop and report: "This does not appear
to be a template-derived project." Otherwise continue.

## Step 2 — Pull the data

For each of the following, use the dedicated tools (Bash for sqlite queries,
Glob/Grep/Read for files). Skip any section where the underlying data isn't
present and note "not available" instead of fabricating.

### 2a. Agent dispatch counts (last 90 days)
If `metrics/evaluation.db` exists, run:
```
sqlite3 metrics/evaluation.db "SELECT agent, COUNT(*) AS dispatches FROM turns WHERE created_at >= date('now','-90 days') GROUP BY agent ORDER BY dispatches DESC;"
```
Capture the full result.

### 2b. Command usage (last 90 days)
```
sqlite3 metrics/evaluation.db "SELECT command_type, COUNT(*) AS runs FROM discussions WHERE created_at >= date('now','-90 days') GROUP BY command_type ORDER BY runs DESC;"
```

### 2c. Top findings by category and severity
```
sqlite3 metrics/evaluation.db "SELECT severity, category, COUNT(*) AS n FROM findings GROUP BY severity, category ORDER BY n DESC LIMIT 20;"
```

### 2d. Agent effectiveness (if the table exists)
```
sqlite3 metrics/evaluation.db "SELECT agent, uniqueness, survival_rate FROM agent_effectiveness ORDER BY uniqueness DESC;"
```
If the table doesn't exist, note "agent_effectiveness table not populated."

### 2e. Divergence from canonical template
List the contents of `.claude/agents/`, `.claude/commands/`, `.claude/rules/`.
Compare names against the canonical template roster:

Canonical agents (12): steward, facilitator, architecture-consultant,
independent-perspective, security-specialist, qa-specialist,
performance-analyst, docs-knowledge, ux-evaluator, project-analyst, educator,
history-analyst.

Canonical commands (17 — verify against the template): plan, build_module,
review, deliberate, retro, meta-review, analyze-project, discover-projects,
ship, seed, onboard, lineage, knowledge-health, batch-evaluate, promote,
walkthrough, quiz.

Report: (a) agents/commands/rules present here but NOT in canonical, (b)
canonical agents/commands NOT present here, (c) any agents/commands/rules
that share a name but appear modified (diff against template if you have
access to a checked-out copy at
`c:\Work\AI\AI Gen Framework Research\agent_framework_template`).

### 2f. Friction signals
Search for:
- `discussions/**/state.json` entries with `risk_flags` containing
  "unresolved-checkpoint" — list discussion IDs
- `BUILD_STATUS.md` "Open advisories" section — count and topics
- Any retro reports in `docs/sprints/` mentioning agents that
  produced low-value findings or were skipped
- Any deferred education gates (search for "deferred" near "education" in
  recent discussion transcripts)

### 2g. Wishlist signals (light search, don't go deep)
Grep recent discussions and BUILD_STATUS.md for phrases like "wish we had",
"missing", "would be nice to have", "should add", "if only" — list 5 most
recent matches with file:line references.

## Step 3 — Report format

Produce a fenced markdown block exactly in this structure. The developer will
paste it back into the hub Claude session. KEEP IT TIGHT — they should be
able to copy the whole thing in one go.

```yaml
project_name: <name from CLAUDE.md or directory name>
data_window: last 90 days (or "no DB" if step 2a failed)
agents_present_count: N
commands_present_count: N
rules_present_count: N

top_5_agents_by_dispatch:
  - agent: name, count: N
  - ...

top_5_commands_by_runs:
  - command: name, count: N
  - ...

agents_never_used: [list of canonical agents with 0 dispatches]
canonical_missing: [agents/commands not present in this project at all]
local_additions: [agents/commands/rules added beyond canonical]
divergent_files: [files sharing a canonical name but appearing modified]

top_finding_categories:
  - <category>: severity=<sev>, count=N
  - ...

friction_signals:
  unresolved_checkpoints: N (discussion IDs)
  open_advisories: N (topics if available)
  deferred_education_gates: N
  retro_mentioned_low_value_agents: [list]

wishlist_recent:
  - "<phrase>" — file:line
  - ...

notes_for_template_decisions:
  <2-4 bullets in your own words: what would you tell the template
  maintainer about how this project uses (or doesn't use) the framework?
  Where is the friction real? Where is the framework over- or under-serving
  this project's actual work?>
```

When complete, output ONLY the report block (and a brief 1-line note if
any step failed). Do not add explanation or recommendations — those happen
back at the hub.
````

---

## After you run it

Paste the returned YAML block(s) back into the hub session at
`c:\Work\AI\AI Gen Framework Research\agent_framework_template`. I will:

1. Re-synthesize the adoption brief with the actual hub-vs-spoke denominator.
2. Re-scope each candidate adoption (framework / derived-only / both).
3. Ask whether to launch `/deliberate` with the recalibrated brief.

## Notes on portability

- The prompt assumes the four-layer capture pipeline is wired up. If a
  derived project diverged from that, the agent will note it under
  `canonical_missing` and you can still get partial data.
- Safe to run multiple times — read-only.
- If a derived project doesn't have `metrics/evaluation.db`, sections 2a–2d
  will report "not available" and the rest will still produce useful divergence
  + friction + wishlist signal.
