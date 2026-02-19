---
description: "Promote a reflection, pattern, or lesson to curated memory (Layer 3). Requires human approval."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep"]
argument-hint: "[path to artifact to promote]"
---

# Promote to Curated Memory (Layer 3)

Promote a reflection, pattern, or lesson from discussion artifacts to the curated memory layer.

## Promotion Criteria

Before promoting, verify ALL of the following:
1. The insight has been confirmed across 2+ independent discussions
2. The insight addresses a recurring pattern (not a one-off issue)
3. The artifact includes context, examples, and rationale
4. A human has reviewed and approved the promotion

## Workflow

### Step 1: Read the Candidate

Read the artifact the developer wants to promote. Assess it against the promotion criteria above.

### Step 2: Present for Approval

Show the developer:
- What will be promoted
- Which criteria it meets
- Where it will be stored in `memory/`
- What impact it will have (will it become a rule? A pattern reference?)

**Wait for explicit developer approval before proceeding.**

### Step 3: Promote

Based on artifact type, save to the appropriate `memory/` subdirectory:
- Decision summaries → `memory/decisions/`
- Validated patterns/anti-patterns → `memory/patterns/`
- Agent reflections → `memory/reflections/`
- Synthesized lessons → `memory/lessons/`
- Rule candidates → `memory/rules/` (may later be promoted to `.claude/rules/`)

### Step 4: Update SQLite

If promoting a reflection, mark it as promoted:
```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
conn.execute('UPDATE reflections SET promoted = 1 WHERE reflection_id = ?', ('<reflection_id>',))
conn.commit()
conn.close()
"
```

### Step 5: Confirm

Report what was promoted and where it was saved.

## Forgetting Curve

Note: Promoted knowledge that hasn't been referenced or validated within 90 days will be flagged for review. Knowledge unconfirmed for 180 days is moved to `memory/archive/` (not deleted).
