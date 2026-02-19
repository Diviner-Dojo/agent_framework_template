---
description: "Run a sprint retrospective (meso loop). Analyzes all discussions from the sprint, identifies patterns, and proposes process adjustments."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep", "Task"]
---

# Sprint Retrospective (Meso Loop)

You are acting as the Facilitator running the weekly/sprint meso loop.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: Every specialist turn MUST be recorded via `scripts/write_event.py`. No findings exist unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
3. **NEVER synthesize before all specialists report**: Wait for ALL dispatched specialists to return before writing the synthesis. Premature synthesis misses findings.
4. **ALWAYS close the discussion**: Every retrospective MUST end with `scripts/close_discussion.py`, even if abandoned. Unclosed discussions corrupt the capture stack.

## Pre-Flight Checks

Before running the retrospective, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if not pathlib.Path('metrics/evaluation.db').exists():
    errors.append('Missing metrics database: metrics/evaluation.db — run scripts/init_db.py first')
if not pathlib.Path('discussions').exists():
    errors.append('Missing discussions directory: discussions/')
if not pathlib.Path('docs/sprints').exists():
    errors.append('Missing sprints directory: docs/sprints/')
if not pathlib.Path('memory/lessons/adoption-log.md').exists():
    errors.append('Missing adoption log: memory/lessons/adoption-log.md')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing. The metrics database is essential — suggest running `python scripts/init_db.py` if it's missing.

## Step 1: Gather Data

Query SQLite for the sprint period:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
# Recent discussions
for row in conn.execute('SELECT discussion_id, risk_level, collaboration_mode, status, agent_count FROM discussions ORDER BY created_at DESC LIMIT 20'):
    print(row)
print('---')
# Recent turns by agent
for row in conn.execute('SELECT agent, intent, COUNT(*) FROM turns GROUP BY agent, intent ORDER BY COUNT(*) DESC'):
    print(row)
print('---')
# Recent education results
for row in conn.execute('SELECT bloom_level, question_type, AVG(score), SUM(passed), COUNT(*) FROM education_results GROUP BY bloom_level, question_type'):
    print(row)
conn.close()
"
```

Also read recent discussion transcripts from `discussions/`.

## Step 2: Analyze Patterns

Assess:
1. **Reopened decisions**: Were any ADRs superseded? Why?
2. **Override frequency**: How often did the developer reject agent recommendations?
3. **Frequent issue tags**: What categories of issues keep appearing?
4. **Time-to-resolution**: How many rounds did discussions take?
5. **Education gate pass/fail rates**: Are developers passing? At what Bloom's levels?
6. **Agent contribution**: Which agents surfaced unique issues vs. noise?

## Step 3: Draft Retrospective

Write a DRAFT retrospective document (do NOT finalize yet — specialists will review it):

```markdown
---
retro_id: RETRO-YYYYMMDD
period: [start date] to [end date]
discussions_analyzed: N
---

## What Went Well
- [Patterns that worked]

## What Needs Improvement
- [Recurring issues, process friction]

## Proposed Adjustments
- [Specific changes to review gates, agent config, or process]

## Agent Calibration
- [Which agents need sensitivity adjustment]

## Education Trends
- [Developer competence growth or gaps]

## Risk Heuristic Updates
- [Changes to how we assess risk for different types of changes]
```

## Step 4: Review Adoption Log

Check `memory/lessons/adoption-log.md` for:
1. Patterns with 3+ sightings that haven't been adopted yet (Rule of Three trigger)
2. Recently deferred patterns that may warrant re-evaluation
3. Whether adopted patterns from external analyses are actually being used in the codebase

Add findings to the draft under a "## External Learning" section.

## Step 5: Create Discussion + Dispatch Specialists

### 5a. Create Discussion

```bash
python scripts/create_discussion.py "retro-YYYYMMDD" --risk low --mode ensemble
```

Use the actual date. Save the returned `discussion_id` — you will need it for all subsequent capture calls.

### 5b. Capture Draft as Proposal Event

```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent proposal \
  --content "<the full draft retro text>" \
  --tags "retro,draft"
```

### 5c. Dispatch Specialists

Dispatch exactly 2 specialists in parallel to review the DRAFT retro:

1. **independent-perspective** (sonnet) — challenge retro findings for blind spots, confirmation bias, and missing perspectives
2. **docs-knowledge** (sonnet) — check whether findings should update CLAUDE.md, `.claude/rules/`, or other documentation

Use `Task(subagent_type="independent-perspective", model="sonnet", ...)` and `Task(subagent_type="docs-knowledge", model="sonnet", ...)` in parallel.

Prompt template for each specialist:
```
Retrospective Review: <discussion_id>

Review this DRAFT sprint retrospective from your specialist perspective.

<draft retro content>

Focus on:
- [independent-perspective]: Are there blind spots? Confirmation bias? Missing perspectives? Are the proposed adjustments well-justified or reflexive?
- [docs-knowledge]: Do any findings warrant updates to CLAUDE.md, .claude/rules/, or documentation? Are any proposed adjustments already covered by existing rules?

Respond with your assessment (under 300 words).
```

### 5d. Capture Specialist Responses

After BOTH specialists return, capture each response:

```bash
python scripts/write_event.py <discussion_id> \
  --agent independent-perspective \
  --intent critique \
  --content "<specialist response>" \
  --tags "retro,specialist-review"

python scripts/write_event.py <discussion_id> \
  --agent docs-knowledge \
  --intent critique \
  --content "<specialist response>" \
  --tags "retro,specialist-review"
```

### 5e. Incorporate Feedback

Review both specialist responses and incorporate their feedback into the final retrospective. Note which findings were challenged, which documentation updates are needed, and which proposed adjustments were validated or rejected.

## Step 6: Finalize and Close

### 6a. Write Final Retrospective

Save the final version to `docs/sprints/RETRO-YYYYMMDD.md`, incorporating specialist feedback. Add a "## Specialist Review Notes" section summarizing what the specialists found.

### 6b. Capture Synthesis Event

```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent synthesis \
  --content "<summary of final retro with specialist input incorporated>" \
  --tags "retro,synthesis"
```

### 6c. Close Discussion

```bash
python scripts/close_discussion.py <discussion_id>
```

## Step 7: Present

Present the retrospective to the developer with specific recommended actions, noting which recommendations were validated by specialist review.
