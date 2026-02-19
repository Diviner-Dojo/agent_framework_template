---
description: "Run a quarterly framework evaluation (macro loop). Assesses agent effectiveness, architectural drift, rule updates, and framework evolution."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep"]
---

# Quarterly Framework Evaluation (Macro Loop)

You are acting as the Facilitator running the quarterly macro loop. This is the double-loop learning check: we question whether our review criteria themselves are correct.

## Pre-Flight Checks

Before running the meta-review, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('metrics/evaluation.db').exists():
    errors.append('Missing metrics database: metrics/evaluation.db — run scripts/init_db.py first')
for d in ['discussions', 'docs/adr', 'docs/sprints', 'memory', '.claude/rules']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
if not pathlib.Path('memory/lessons/adoption-log.md').exists():
    errors.append('Missing adoption log: memory/lessons/adoption-log.md')
if not pathlib.Path('CLAUDE.md').exists():
    errors.append('Missing project constitution: CLAUDE.md')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing. The metrics database and CLAUDE.md are essential for this analysis.

## Step 1: Gather Comprehensive Data

Query SQLite for the full period:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
print('=== Discussion Summary ===')
for row in conn.execute('SELECT risk_level, collaboration_mode, COUNT(*), AVG(agent_count) FROM discussions GROUP BY risk_level, collaboration_mode'):
    print(row)
print('=== Agent Effectiveness ===')
for row in conn.execute('SELECT agent, intent, COUNT(*), AVG(confidence) FROM turns GROUP BY agent, intent'):
    print(row)
print('=== Reflection Patterns ===')
for row in conn.execute('SELECT agent, COUNT(*), AVG(confidence_delta), SUM(promoted) FROM reflections GROUP BY agent'):
    print(row)
print('=== Education Trends ===')
for row in conn.execute('SELECT bloom_level, AVG(score), SUM(passed), COUNT(*) FROM education_results GROUP BY bloom_level'):
    print(row)
conn.close()
"
```

## Step 2: Deep Analysis

### Agent Effectiveness Scoring
- Which agents find unique issues vs. duplicates?
- Which agents have the best confidence calibration?
- Which agents are most frequently overridden by the developer?

### Drift Analysis
- Read all ADRs in `docs/adr/` and compare against current code
- Is the codebase gradually departing from architectural principles?

### Rule Update Candidates
- Which promoted patterns in `memory/` should become permanent rules in `.claude/rules/`?
- Which existing rules should be deprecated or revised?

### Decision Churn Index
- How volatile are architectural decisions? (superseded ADR count / total ADR count)

### Education Trend Analysis
- Is developer competence growing, plateauing, or declining?
- Are higher Bloom's levels being achieved over time?

## Step 3: Double-Loop Check

Explicitly ask:
- "Are our review criteria themselves correct?"
- "Should we change what we're measuring or how we're evaluating?"
- "Are there categories of issues we're systematically missing?"
- "Are there categories we're over-flagging?"

## Step 4: Produce Framework Evolution Report

Save to `docs/sprints/META-REVIEW-YYYYMMDD.md`:

```markdown
---
meta_review_id: META-REVIEW-YYYYMMDD
period: [start date] to [end date]
---

## Executive Summary
[2-3 sentences on framework health]

## Agent Effectiveness
[Per-agent assessment with metrics]

## Architectural Drift Assessment
[How well code matches recorded decisions]

## Rule Evolution
### Proposed New Rules
### Proposed Rule Changes
### Proposed Deprecations

## Education Assessment
[Developer competence trends]

## Framework Adjustments
[Specific structural changes recommended]

## Double-Loop Findings
[Meta-level insights about the review process itself]
```

## Step 5: Adoption Log Trend Assessment

Review `memory/lessons/adoption-log.md` for macro-level trends:
1. **Adoption rate**: Are we importing too aggressively or too conservatively?
2. **Rejection patterns**: Are certain categories consistently rejected? Should we stop looking for them?
3. **Adopted pattern usage**: Are imported patterns actually being used, or are they shelfware?
4. **Score calibration**: Are our scoring thresholds (20/25) too high or too low?
5. **Rule of Three**: How many patterns have hit 3+ sightings? What percentage were eventually adopted?

Include findings in the meta-review under a "## External Learning Assessment" section.

## Step 6: Present and Implement

Present the report to the developer. With approval, update:
- `.claude/rules/` files if warranted
- Agent definitions if calibration needs changing
- CLAUDE.md if conventions have evolved
- Archive deprecated patterns from `memory/`
