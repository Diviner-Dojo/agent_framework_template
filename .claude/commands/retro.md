---
description: "Run a sprint retrospective (meso loop). Analyzes all discussions from the sprint, identifies patterns, and proposes process adjustments."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep"]
---

# Sprint Retrospective (Meso Loop)

You are acting as the Facilitator running the weekly/sprint meso loop.

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

## Step 3: Produce Retrospective

Write a retrospective document to `docs/sprints/RETRO-YYYYMMDD.md`:

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

Include findings in the retrospective under a "## External Learning" section.

## Step 5: Present

Present the retrospective to the developer with specific recommended actions.
