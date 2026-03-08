---
description: "Promote a reflection, pattern, or lesson to curated memory (Layer 3). Requires human approval."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep"]
argument-hint: "[path to artifact to promote]"
---

# Promote to Curated Memory (Layer 3)

Promote a reflection, pattern, or lesson from discussion artifacts to the curated memory layer.

## Pre-Flight Checks

Before promoting, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('memory').exists():
    errors.append('Missing memory directory: memory/')
if not pathlib.Path('metrics/evaluation.db').exists():
    errors.append('Missing metrics database: metrics/evaluation.db')
for subdir in ['decisions', 'patterns', 'reflections', 'lessons', 'rules']:
    d = pathlib.Path('memory') / subdir
    if not d.exists():
        errors.append(f'Missing memory subdirectory: memory/{subdir}/')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Promotion Criteria

Before promoting, verify ALL of the following:
1. The insight has been confirmed across 2+ independent discussions
2. The insight addresses a recurring pattern (not a one-off issue)
3. The artifact includes context, examples, and rationale
4. A human has reviewed and approved the promotion

## Workflow

### Step 1: Check Promotion Queue

Before accepting a manual path, query the promotion_candidates table for pending items:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
try:
    rows = conn.execute('''
        SELECT candidate_id, candidate_type, title, evidence_count, target_path, created_at
        FROM promotion_candidates WHERE status = 'pending'
        ORDER BY evidence_count DESC, created_at
    ''').fetchall()
    if rows:
        print(f'=== {len(rows)} Pending Promotion Candidates ===')
        for i, (cid, ctype, title, evidence, target, created) in enumerate(rows, 1):
            print(f'  {i}. [{ctype.upper()}] {title[:70]}')
            print(f'     Evidence: {evidence} | Target: {target} | Since: {created[:10]}')
    else:
        print('No pending promotion candidates in the queue.')
except sqlite3.OperationalError:
    print('promotion_candidates table not available — proceeding with manual promotion.')
conn.close()
"
```

If there are pending candidates, present them to the developer for selection. If the developer provides a specific artifact path instead, proceed with that.

### Step 1b: Read the Candidate

Read the artifact the developer wants to promote (either from the queue or a manual path). Assess it against the promotion criteria above.

### Step 2: Present for Approval

Show the developer:
- What will be promoted
- Which criteria it meets
- Where it will be stored in `memory/`
- What impact it will have (will it become a rule? A pattern reference?)

**Wait for explicit developer approval before proceeding.**

### Step 3: Promote

Based on artifact type, save to the appropriate `memory/` subdirectory:
- Decision summaries -> `memory/decisions/`
- Validated patterns/anti-patterns -> `memory/patterns/`
- Agent reflections -> `memory/reflections/`
- Synthesized lessons -> `memory/lessons/`
- Rule candidates -> `memory/rules/` (may later be promoted to `.claude/rules/`)

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

If promoting from the promotion_candidates queue, update the candidate status:
```bash
python -c "
import sqlite3
from datetime import datetime, timezone
now = datetime.now(timezone.utc).isoformat()
conn = sqlite3.connect('metrics/evaluation.db')
conn.execute('''UPDATE promotion_candidates
    SET status = 'approved', promoted_at = ?, reviewed_at = ?, last_referenced_at = ?,
        human_verdict = 'approved'
    WHERE candidate_id = ?''', (now, now, now, '<candidate_id>'))
conn.commit()
conn.close()
"
```

### Step 5: Confirm

Report what was promoted and where it was saved.

## Forgetting Curve

Promoted knowledge that hasn't been referenced or validated within 90 days will be flagged for review. Knowledge unconfirmed for 180 days is moved to `memory/archive/` (not deleted).

To check staleness now: `python scripts/enforce_forgetting_curve.py --dry-run`
