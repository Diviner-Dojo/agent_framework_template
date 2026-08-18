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

## Step 0: Knowledge Pipeline Dashboard

Run the knowledge pipeline dashboard to gather baseline metrics:

```bash
python scripts/knowledge_dashboard.py --no-log
```

Include the pipeline health score and any gaps in the retro data gathering. This provides context on whether knowledge is being captured and amplified effectively.

## Step 1: Gather Data

Query SQLite for the sprint period:

```bash
python -c "
import sqlite3, sys
conn = sqlite3.connect('metrics/evaluation.db')
broken = []
degraded = []
# The EXPLICIT set of objects this block knows how to read. 'no such table' is only a benign
# pre-migration story for a name IN this set; for any other name it means the query asks for
# something that was never in the schema (typo / un-propagated rename) and must fail loudly.
KNOWN_OBJECTS = ['discussions', 'turns', 'education_results', 'protocol_yield']
# Recent discussions
for row in conn.execute('SELECT discussion_id, risk_level, collaboration_mode, status, agent_count FROM discussions ORDER BY created_at DESC LIMIT 20'):
    print(row)
print('---')
# Protocol durations (effort analysis)
print('=== Protocol Durations ===')
for row in conn.execute('''
    SELECT discussion_id, command_type,
           ROUND((julianday(closed_at) - julianday(created_at)) * 24 * 60, 1) as duration_minutes
    FROM discussions
    WHERE status = 'closed' AND closed_at IS NOT NULL
    ORDER BY created_at DESC LIMIT 20
'''):
    print(row)
print('---')
# Protocol yield (if table exists)
try:
    print('=== Protocol Yield ===')
    for row in conn.execute('''
        SELECT protocol_type, COUNT(*) as invocations,
               SUM(findings_blocking) as total_blocking,
               SUM(findings_advisory) as total_advisory,
               SUM(agent_turns_used) as total_turns,
               ROUND(CAST(SUM(findings_blocking) AS REAL) / NULLIF(SUM(agent_turns_used), 0), 2) as yield_per_turn
        FROM protocol_yield
        GROUP BY protocol_type
    '''):
        print(row)
except sqlite3.Error as e:
    # Do NOT downgrade a query error to '(table not yet created)'. A broken read path that
    # reports itself as merely unavailable teaches the reader that missing data is normal,
    # and the defect survives every retro. Do not kill the whole data-gathering step either:
    # the sections below are still valid. So: name it loudly, classify it, and let the
    # end-of-block banner set the exit code. Guarded by tests/test_command_sql.py.
    msg = str(e)
    obj = msg.split(':', 1)[1].strip().split('.')[-1] if msg.startswith('no such table') else ''
    if obj and obj in KNOWN_OBJECTS:
        print('SCHEMA SKEW [protocol_yield]: ' + msg)
        print('  This project predates the protocol_yield migration — run scripts/init_db.py.')
        print('  Protocol-yield analysis is DEGRADED for this retro.')
        degraded.append('protocol_yield')
    elif obj:
        print('INSTRUMENT FAILURE [protocol_yield]: \'' + obj + '\' is not an object this command knows.')
        print('  This is a typo or an un-propagated rename, NOT a missing migration.')
        print('  Objects this block knows: ' + ', '.join(KNOWN_OBJECTS))
        broken.append('protocol_yield')
    else:
        print('INSTRUMENT FAILURE [protocol_yield]: ' + type(e).__name__ + ': ' + msg)
        print('  The protocol_yield table is present and the query still failed.')
        broken.append('protocol_yield')
print('---')
# Recent turns by agent
for row in conn.execute('SELECT agent, intent, COUNT(*) FROM turns GROUP BY agent, intent ORDER BY COUNT(*) DESC'):
    print(row)
print('---')
# Recent education results
for row in conn.execute('SELECT bloom_level, question_type, AVG(score), SUM(passed), COUNT(*) FROM education_results GROUP BY bloom_level, question_type'):
    print(row)
print('---')
# ADR-0035 zero-miss watch (the all-first-ask signal). The tutor both teaches and
# grades — the developer declined an independent grader (Q9, empty-governance risk)
# on condition the gap stays WATCHED. Misses are the only variance the instrument has,
# so a sustained run of sessions with zero recorded misses is the named signature
# of grading gone soft. Columns: session, attempts, misses, newest timestamp.
print('=== Zero-miss watch (ADR-0035): newest 10 education sessions ===')
for row in conn.execute('SELECT session_id, COUNT(*), SUM(passed = 0), MAX(timestamp) FROM education_results GROUP BY session_id ORDER BY MAX(timestamp) DESC LIMIT 10'):
    print(row)
conn.close()
if broken:
    print('')
    print('BROKEN INSTRUMENTS: ' + ', '.join(broken))
    print('These queries name an object that was never in the schema, or failed against a schema')
    print('that IS present. Neither is a missing migration — stop and fix the query or the view.')
    sys.exit(1)
if degraded:
    print('')
    print('DEGRADED INSTRUMENTS: ' + ', '.join(degraded))
    print('This retro is running on PARTIAL data. Say so explicitly in the retro report and')
    print('name which sections are affected — a retro that under-reports silently is the bug')
    print('this banner exists to prevent. Run scripts/init_db.py to clear it.')
    sys.exit(2)
"
```

Read the exit code of this and every DB block below, do not just read the output:

- **exit 2 — DEGRADED**: an object this block explicitly knows is absent because the project's
  DB predates a migration. The retro may continue, but the report MUST name the degraded
  instrument and must not present its conclusions as covering it.
- **exit 1 — BROKEN**: either the query is wrong against a schema that IS present, or it names an
  object that was never in the schema (typo / un-propagated rename). Neither is a missing
  migration. Stop and fix it — do not write the section as if there were simply no data.
- **exit 0**: every instrument answered.

**Read the zero-miss watch, not just its rows (ADR-0035).** The third column is the
session's recorded misses. A sustained run of newest sessions all at `0` — every concept
passing on the first ask — is the watched signal that grading has gone soft: the tutor
both teaches and grades, and the developer accepted that asymmetry only with this watch
on it. When the pattern appears, NAME it in the retro report as the ADR-0035 signal and
recommend a look at the graded transcripts (the verbatim answers are in Layer 1). It is
a signal to a human, never a gate: nothing fails on it, and a zero-miss run can also
simply mean easy material or a good week.

Also read recent discussion transcripts from `discussions/`.

### Step 1b: Spec Pipeline Health Check

Check for stale specs that may have been implemented but not marked complete:

```bash
python -c "
import pathlib, re
from datetime import datetime, timezone
specs = list(pathlib.Path('docs/sprints').glob('SPEC-*.md'))
stale = []
for s in specs:
    text = s.read_text(encoding='utf-8')
    status_m = re.search(r'^status:\s*(.+)$', text, re.MULTILINE)
    type_m = re.search(r'^type:\s*(.+)$', text, re.MULTILINE)
    if not status_m: continue
    status = status_m.group(1).strip().strip('\"')
    spec_type = type_m.group(1).strip().strip('\"') if type_m else 'spec'
    if spec_type == 'vision': continue
    if status in ('approved', 'reviewed'):
        stale.append((s.name, status))
if stale:
    print(f'WARNING: {len(stale)} specs may be stale (approved/reviewed but not complete):')
    for name, st in stale:
        print(f'  [{st}] {name}')
    print('Action: Verify if these specs have been implemented. If so, update status to complete.')
else:
    print('Spec pipeline healthy: no stale approved/reviewed specs.')
"
```

Include stale spec count in the retro report. Cross-reference against recent commits if specs have been stale >7 days.

### Step 1c: Retro Action Resolution Check

Check the retro action registry for open items from previous retros:

```bash
python -c "
import pathlib
registry = pathlib.Path('memory/decisions/retro-action-registry.md')
if registry.exists():
    text = registry.read_text(encoding='utf-8')
    open_count = text.lower().count('status: open') + text.lower().count('status: in-progress')
    completed = text.lower().count('status: completed') + text.lower().count('status: done')
    deferred = text.lower().count('status: deferred')
    print(f'Retro actions: {open_count} open, {completed} completed, {deferred} deferred')
    if open_count > 0:
        print('Review open items below — check if any have been resolved through other mechanisms (ADRs, rules, commits).')
else:
    print('No retro action registry found at memory/decisions/retro-action-registry.md')
"
```

Before writing the draft retro, review open retro actions from previous retros. If an action item has been resolved through a different mechanism (ADR, rule change, commit), update its status in the registry and note the resolution reference.

### Step 1d: Protocol Yield Coverage Read-Out (REQUIRED)

This is the step that makes "this gate caught nothing" and "this gate was never measured"
distinguishable. Run it — the Protocol Value Assessment section of the draft cannot be
written honestly without its output.

```bash
python scripts/efficiency_report.py
```

Read the exit code:

- **exit 0** — report rendered. Copy the `Yield coverage by protocol type` table and the
  `measured` column of each slice into the draft.
- **exit 2** — bad `--since` argument. Fix the date and re-run.
- **exit 1** — the database is absent or unreadable. This is a BROKEN INSTRUMENT, exactly
  as in Step 1, and the output says so in those words. Do not write the yield sections as
  if there were simply no data: nothing was measured, so nothing may be concluded. Leave
  the Protocol Value Assessment table unfilled, record "instrument unavailable — yield not
  assessed this sprint" in its place, and make repairing it the action.

**How to read the output — this is the whole point of the step:**

- `-` in a yield cell means **NEVER MEASURED**: no `protocol_yield` row exists for that
  bucket.
- `0` in a yield cell means **MEASURED AND CAUGHT NOTHING**: a protocol ran and recorded
  zero findings.

These are not the same fact and must never be merged in the retro write-up. Carry the
distinction through into every sentence you write about a protocol's value. If the report
prints a `NEVER MEASURED:` line, name those protocols in the retro as *uninstrumented*, and
record instrumenting them as the action — never their removal. See the ANTI-DELETION GUARD
in the Step 3 template before drafting the Protocol Value Assessment.

Also read the `Recording integrity` block. If it prints an `HONESTY WARNING` about the
false-positive rate, that is a finding about **our recording discipline**, not a compliment
to the specialist panel. Put it in "What Needs Improvement".

### Step 1e: Calibration Drift Audit (ADVISORY — NEVER A GATE)

```bash
python scripts/audit_calibration.py --report-only
```

This surfaces drift between stated confidence, recorded severity, and the noise classifier.
It exits 0 whenever it ran, regardless of how many proposals it emits — **it is advisory and
must never be treated as a gate**. Exit 1 means the audit itself failed to run (database
absent or unreadable), never that calibration drifted; the report prints `BROKEN INSTRUMENT`
in that case. On exit 1, report the instrument as broken and write **no** calibration
conclusion — a failed audit is not a clean bill of health.

`--report-only` suppresses the proposal **queue** artifact under `memory/calibration-proposals/`.
It does **not** suppress the run log: every invocation appends one line to
`metrics/calibration_log.jsonl`, including runs that emit zero proposals, so "the audit ran
and found nothing" stays distinguishable from "the audit was never run". Drop
`--report-only` only if the developer asks for the queue to be written.

> **THE ADR-0024 HUMAN GATE IS ABSOLUTE.** Calibration proposals are `status: pending`
> **communication artifacts, not instruction files.** The agent must **NEVER** edit a
> classifier surface off its own proposal — not `scripts/extract_findings.py`, not
> `.claude/skills/severity-calibration/SKILL.md`, not any other classifier. Doing so is
> **self-modification**: the system tuning the instrument that grades it, which is the one
> thing the human-mediated Prime Objective and Principle #6 (curated memory needs human
> approval) exist to prevent. Report the proposals to the developer and stop there. A human
> applies them, or they do not get applied.

Summarise the proposals in the retro under "## Agent Calibration" and mark each as
`pending developer decision`. Treat any proposal flagged `[low-confidence]` as a single soft
signal — `confidence_calibration` is a rough proxy, not a verdict.

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

## Effort Analysis
- **Total protocol time**: [Sum of discussion durations for this sprint, in minutes]
- **Overhead ratio**: [Protocol time / estimated total dev time]
- **Highest-cost protocol**: [Which command type consumed the most time]
- **Value-per-minute**: [Blocking findings per minute of protocol time]
- **Trend**: [Is overhead growing, stable, or shrinking vs. previous sprint?]

## Protocol Value Assessment

Fill this in from the Step 1d yield-coverage read-out. The `Measured` column is not
optional and must be copied across verbatim — it is what makes every other column
interpretable.

| Protocol | Measured (runs w/ yield ÷ runs) | Invocations | Blocking Findings | Advisory | False Positives | Agent Turns | Yield/Turn | Trend |
|----------|-------------------------------|------------|-------------------|----------|-----------------|-------------|------------|-------|
| review | | | | | | | | |
| checkpoint | | | | | | | | |
| education_gate | | | | | | | | |
| quality_gate | | | | | | | | |
| retro | | | | | | | | |

Write `NEVER MEASURED` — not `0` — in every cell of any protocol with no recorded yield.

### THE ANTI-DELETION GUARD (read before writing a single word of this section)

**A gate with no recorded yield may be worthless, or may simply never have been measured —
those look identical and are not the same. Never propose deleting a gate on absence of
evidence.**

Zero blocking findings has two completely different causes:

- **Measured, caught nothing** — the protocol ran, yield was recorded, the count was 0.
  This is real evidence, and it is a legitimate input to a relaxation discussion.
- **Never measured** — no `protocol_yield` row was ever written. This says *nothing at all*
  about the protocol's value. It is a defect in the instrument, not a verdict on the gate.

If a protocol is unmeasured, the only honest recommendation is **"instrument it, then
re-assess next sprint"** — never "relax it", never "remove it". Wire `record_yield.py` into
it and argue from what it records. This guard exists because a real deletion recommendation
was once made from silence and had to be personally reversed by the developer: 
deleting the measurement deletes the ability to ever answer "was that right?".

Present data; do NOT recommend automatic relaxation (Principle #7 — human decides).
```

## Step 4: Review Adoption Log + Knowledge Pipeline

### 4a. Adoption Log Review

Check `memory/lessons/adoption-log.md` for:
1. Patterns with 3+ sightings that haven't been adopted yet (Rule of Three trigger)
2. Recently deferred patterns that may warrant re-evaluation
3. Whether adopted patterns from external analyses are actually being used in the codebase
4. **PENDING adoption age**: Run the stale adoption checker:

```bash
python scripts/check_stale_adoptions.py
```

If stale count > 5 (exit code 2), recommend the developer run `/batch-evaluate` to clear the backlog.

### 4b. Rule of Three (Discussion-Derived Patterns)

Query the unified Rule of Three view for patterns crossing the 3-discussion threshold:

```bash
python -c "
import sqlite3, sys
conn = sqlite3.connect('metrics/evaluation.db')
conn.row_factory = sqlite3.Row

# This file is CORE: it propagates to derived projects whose evaluation.db may predate a
# migration and therefore carry different column names for the same instrument. So: read
# the real schema first, pick an order column from a documented preference list, and use
# name-keyed row access. Hardcoding hub column names here turns a legible instrument into a
# dead command in exactly the projects that run /retro most. Guarded by tests/test_command_sql.py.
# The obj argument is the ONE object this probe may be missing. 'no such table' is a benign
# pre-migration story only for that exact name; for any other name it means the probe asks for
# something that was never in the schema (typo / un-propagated rename) and must fail loudly.
def columns_of(label, probe, obj):
    try:
        return [d[0] for d in conn.execute(probe).description]
    except sqlite3.Error as e:
        conn.close()
        msg = str(e)
        if msg == 'no such table: ' + obj:
            print('SCHEMA SKEW [' + label + ']: ' + msg)
            print('  This project predates that migration — run scripts/init_db.py.')
            print('  This retro section is DEGRADED: it was NOT checked. Say so in the report.')
            sys.exit(2)
        print('INSTRUMENT FAILURE [' + label + ']: cannot read schema: ' + type(e).__name__ + ': ' + msg)
        print('  The probe names something other than ' + obj + ', or the object exists and the')
        print('  read still failed. Neither is a missing migration — fix the query or the view.')
        sys.exit(1)

# SQL-injection note: only a column/table name from a LITERAL list in this file is ever
# interpolated below, and it must also appear in the introspected schema. No caller-
# supplied value reaches the statement; row VALUES stay parameterised (see security_baseline).
def pick(label, cols, prefs):
    for c in prefs:
        if c in cols:
            return c
    conn.close()
    print('INSTRUMENT FAILURE [' + label + ']: none of ' + str(prefs) + ' exist.')
    print('  actual columns: ' + str(cols))
    print('  The schema drifted past every name this command knows. Fix the view, or add the')
    print('  new name to the preference list above — do NOT report this as an absence of data.')
    sys.exit(1)

def get(row, *names):
    for n in names:
        if n in row.keys():
            return row[n]
    return None

# Presence of the COLUMN, not truthiness of the value — same helper as 4c. get() alone cannot
# tell 'this schema generation has no such column' from 'the column is NULL for this row', and
# dropping a NULL would silently shrink the instrument for exactly the rows where a value was
# undefined.
def has(row, name):
    return name in row.keys()

cols = columns_of('v_rule_of_three', 'SELECT * FROM v_rule_of_three LIMIT 0', 'v_rule_of_three')
# Order by the view's own per-discussion count — the Rule of Three IS a per-discussion
# threshold, so the sighting/discussion count is the only ranking that matches the purpose.
# 'sighting_count' is the current hub name; 'discussion_count' is the pre-migration name.
order = pick('v_rule_of_three', cols, ['sighting_count', 'discussion_count'])
try:
    rows = conn.execute('SELECT * FROM v_rule_of_three ORDER BY ' + order + ' DESC').fetchall()
except sqlite3.Error as e:
    conn.close()
    print('INSTRUMENT FAILURE [v_rule_of_three]: ' + type(e).__name__ + ': ' + str(e))
    print('This is the pattern-promotion instrument. Fix it — do not record the retro as if no patterns existed.')
    sys.exit(1)
conn.close()
if rows:
    print('=== Rule of Three Hits (ranked by ' + order + ') ===')
    for row in rows:
        label = get(row, 'summary', 'pattern_key') or '(no summary)'
        cat = get(row, 'category') or '-'
        first = str(get(row, 'first_seen'))[:10]
        last = str(get(row, 'last_seen'))[:10]
        print('  [' + str(cat) + '] ' + str(label))
        # Conditional-append in BOTH directions, exactly as 4c does for v_agent_dashboard.
        # agent_count exists ONLY on the pre-migration schema — and it is the cross-agent
        # corroboration number, the thing that separates a pattern three agents independently
        # saw from one agent repeating itself. That is the whole point of a Rule of Three, so
        # a repair that stops printing it has deleted the measurement it claimed to fix.
        # pattern_hash exists only on the hub schema. Neither may be dropped.
        parts = [str(row[order]) + ' discussions']
        if has(row, 'agent_count'):
            parts.append(str(get(row, 'agent_count')) + ' agents')
        parts.append(first + '..' + last)
        print('      ' + ' | '.join(parts))
        if has(row, 'pattern_hash'):
            print('      hash: ' + str(get(row, 'pattern_hash')))
        # Provenance: the discussion IDs this pattern was actually sighted in. Without it the
        # reader cannot check the claim, which is the tether the whole capture stack exists for.
        if has(row, 'discussion_ids') or has(row, 'discussions'):
            print('      sources: ' + str(get(row, 'discussion_ids', 'discussions')))
else:
    print('v_rule_of_three is readable and empty — no pattern has crossed the 3-discussion threshold yet.')
"
```

### 4c. Agent Effectiveness Summary

Query the agent dashboard for effectiveness trends:

```bash
python -c "
import sqlite3, sys
conn = sqlite3.connect('metrics/evaluation.db')
conn.row_factory = sqlite3.Row

# Same CORE-propagation rule as 4b: introspect, branch, use name-keyed access.
# The obj argument is the ONE object this probe may be missing. 'no such table' is a benign
# pre-migration story only for that exact name; for any other name it means the probe asks for
# something that was never in the schema (typo / un-propagated rename) and must fail loudly.
def columns_of(label, probe, obj):
    try:
        return [d[0] for d in conn.execute(probe).description]
    except sqlite3.Error as e:
        conn.close()
        msg = str(e)
        if msg == 'no such table: ' + obj:
            print('SCHEMA SKEW [' + label + ']: ' + msg)
            print('  This project predates that migration — run scripts/init_db.py.')
            print('  This retro section is DEGRADED: it was NOT checked. Say so in the report.')
            sys.exit(2)
        print('INSTRUMENT FAILURE [' + label + ']: cannot read schema: ' + type(e).__name__ + ': ' + msg)
        print('  The probe names something other than ' + obj + ', or the object exists and the')
        print('  read still failed. Neither is a missing migration — fix the query or the view.')
        sys.exit(1)

# SQL-injection note: only a column/table name from a LITERAL list in this file is ever
# interpolated below, and it must also appear in the introspected schema. No caller-
# supplied value reaches the statement; row VALUES stay parameterised (see security_baseline).
def pick(label, cols, prefs):
    for c in prefs:
        if c in cols:
            return c
    conn.close()
    print('INSTRUMENT FAILURE [' + label + ']: none of ' + str(prefs) + ' exist.')
    print('  actual columns: ' + str(cols))
    print('  Fix the view or extend the preference list — do NOT report this as an absence of data.')
    sys.exit(1)

def get(row, *names):
    for n in names:
        if n in row.keys():
            return row[n]
    return None

# Presence of the COLUMN, not truthiness of the value. get() alone cannot tell 'this schema
# generation has no such column' from 'the column is NULL for this row', and dropping a NULL
# would silently shrink the instrument for exactly the rows where a ratio was undefined.
def has(row, name):
    return name in row.keys()

cols = columns_of('v_agent_dashboard', 'SELECT * FROM v_agent_dashboard LIMIT 0', 'v_agent_dashboard')
# Rank by DISTINCT findings, not raw volume: this section reports which agents contributed
# unique signal, and an agent that restates everyone else's finding is not more effective.
# 'total_unique_findings' is the current hub name; 'total_findings' is the pre-migration name.
order = pick('v_agent_dashboard', cols, ['total_unique_findings', 'total_findings'])
try:
    rows = conn.execute('SELECT * FROM v_agent_dashboard ORDER BY ' + order + ' DESC').fetchall()
except sqlite3.Error as e:
    conn.close()
    print('INSTRUMENT FAILURE [v_agent_dashboard]: ' + type(e).__name__ + ': ' + str(e))
    print('This is the agent-effectiveness instrument. Fix it — do not write the retro section as if no data existed.')
    sys.exit(1)
conn.close()
if rows:
    print('=== Agent Effectiveness (ranked by ' + order + ') ===')
    for row in rows:
        agent = get(row, 'agent')
        disc = get(row, 'discussions_participated', 'discussions')
        uniq = get(row, 'total_unique_findings', 'total_unique')
        dup = get(row, 'total_duplicate_findings')
        fp = get(row, 'total_false_positives')
        ratio = get(row, 'uniqueness_ratio', 'uniqueness_pct')
        cal = get(row, 'avg_calibration')
        # Conditional-append in BOTH directions: hub-only columns (duplicate / false-positive)
        # AND pre-migration-only columns (total_findings raw volume, survival_pct). A repair
        # that drops a column the DB can still answer is measurement deleted by the fix.
        parts = [str(disc) + ' discussions']
        if has(row, 'total_findings'):
            parts.append(str(get(row, 'total_findings')) + ' findings')
        parts.append(str(uniq) + ' unique')
        if has(row, 'total_duplicate_findings'):
            parts.append(str(dup) + ' duplicate')
        if has(row, 'total_false_positives'):
            parts.append(str(fp) + ' false-positive')
        parts.append('uniqueness=' + str(ratio))
        if has(row, 'survival_pct'):
            parts.append('survived=' + str(get(row, 'survival_pct')))
        parts.append('conf=' + str(get(row, 'avg_confidence')))
        parts.append('calib=' + str(cal))
        print('  ' + str(agent) + ': ' + ', '.join(parts))
else:
    print('v_agent_dashboard is readable and empty — no agent_effectiveness rows recorded yet.')
"
```

### 4d. Forgetting Curve Check

Run a dry-run staleness check on promoted knowledge:

```bash
python scripts/enforce_forgetting_curve.py --dry-run
```

Add all findings to the draft under "## Knowledge Pipeline Health" and "## External Learning" sections. Include a PENDING age summary:

```markdown
### PENDING Adoption Age
- Total PENDING: N
- Stale (>14 days): M
- Oldest: [pattern name] (X days)
- Recommendation: [run /batch-evaluate | no action needed]
```

## Step 5: Create Discussion + Dispatch Specialists

### 5a. Create Discussion

```bash
python scripts/create_discussion.py "retro-YYYYMMDD" --risk low --mode ensemble
```

Use the actual date. Save the returned `discussion_id` — you will need it for all subsequent capture calls.

### 5.1. Write Context-Brief (Before Specialist Dispatch)

Immediately after creating the discussion, capture a context-brief event. This must be
written before any specialist is dispatched — it produces `turn_id=1` in the discussion
and injects developer framing into specialist prompts.

Summarise the developer's request from the current session. Populate all four fields;
write "(none stated)" if a field was not addressed. Strip business context (deadlines,
client names, regulatory pressures) — record structural intent only.

```bash
# INVARIANT: This must be the first write_event.py call in this workflow.
# turn_id=1 is required for extraction pipeline integrity. Any reordering
# silently breaks context-brief capture. See DISC-20260302-231156.
python scripts/write_event.py "<discussion_id>" "facilitator" "evidence" \
  "## Request Context
- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [sprint period and discussions being analyzed]
- **Developer-stated motivation**: [why this retro is being run, if stated; or 'none stated']
- **Explicit constraints**: [developer-stated constraints agents should respect; or 'none stated']" \
  --tags "context-brief"
# If invoked without prior conversational context (cold start), populate all four
# fields as "(none stated)" and add tag "context-brief-cold-start" so uninstrumented
# invocations are queryable: --tags "context-brief,context-brief-cold-start"
```

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

## Step 5.5: Developer Input Capture Gate (SPEC-20260302-192548)

Evaluate developer-input capture effectiveness before writing the final retrospective. This gate runs every sprint until Step 3 is formally initiated or abandoned.

**Assess the following three signals** (all are observable from sprint discussions and retro analysis):

- **Signal A — Specialist echo**: Are specialists repeating findings already stated as explicit developer constraints in context-brief sections this sprint? (Inspect context-brief events in sprint discussions and compare to specialist critique events.)
- **Signal B — Framing drift**: Has framing drift been observed this sprint? (Facilitator synthesis diverges from what the developer actually asked for — noted in retro or review feedback.)
- **Signal C — Disposition activity** (pending implementation): `SELECT COUNT(*) FROM findings WHERE disposition != 'open'` — expected to return 0 until ADR-0030 ships. If non-zero: dispositions are being captured and the mechanism is live.

**Decision rule**:
- If Signal A or Signal B is Yes → recommend initiating Step 3 (ADR-0030 + `agent="developer"` schema extension) and include in the retro document.
- If both Signal A and Signal B are No (and Signal C = 0) → formally defer Step 3 with a one-line rationale in the retro document.
- Once Signal C > 0, retire Signal C from the gate and re-evaluate the others.

Remove this step once Step 3 is either shipped or formally abandoned.

## Step 6: Finalize and Close

### 6a. Write Journey Chapter and Update Orientation (REQUIRED)

Before writing the final retro, update the project's narrative memory. These are NOT optional — they are the mechanism that prevents the developer from losing the thread.

**Journey chapter** — append a new chapter to `memory/journey.md`:
```markdown
## Chapter N: [Title] (YYYY-MM-DD)

[What was built this sprint. What was tried and rejected. What was learned.
What changed about the project's direction. Written as narrative, not bullet points.
3-5 paragraphs. Address the developer in second person ("you built...")]
```

**Innovations check** — if any new template-worthy patterns emerged this sprint, add entries to `memory/innovations.md` with the origin story.

**Orientation update** — rewrite `memory/decisions/current-arc.md` to reflect:
- What was just finished
- What is being worked on now
- Three things to hold in mind
- Key open questions

### 6b. Write Final Retrospective

Save the final version to `docs/sprints/RETRO-YYYYMMDD.md`, incorporating specialist feedback. Add a "## Specialist Review Notes" section summarizing what the specialists found.

### 6c. Capture Synthesis Event

```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent synthesis \
  --content "<summary of final retro with specialist input incorporated>" \
  --tags "retro,synthesis"
```

### 6d. Record Protocol Yield

Record yield metrics for this retrospective. **This step is not optional and not skippable
even when the retro found nothing.** An unrecorded retro is indistinguishable from a retro
that was never run, and that ambiguity is what the Step 1d guard exists to prevent. If this
command fails, HALT and say so — do not proceed as if the yield had been recorded.

```bash
python scripts/record_yield.py <discussion_id> retro pass \
  --blocking <N> --advisory <M> --false-positive <FP> --turns <agent_turn_count>
```

Where `<N>` is the count of actionable findings (proposed adjustments), `<M>` is the count
of informational observations, and `<FP>` is the count of findings that turned out to be
wrong (see below). **A retro with zero findings still records `--blocking 0` — a recorded
zero is evidence; an absent row is not.**

#### Recording honesty (`--false-positive`)

Count here every finding that was raised and then turned out to be **wrong**: the code
already handled it, the concern did not apply, the claim was factually incorrect, or it was
withdrawn on inspection. A finding that was correct but declined as out-of-scope is **not**
a false positive.

**Do not round this down, and do not leave it at 0 because 0 looks better.** These numbers
feed the yield ratios, the calibration audit, and every future argument about which gates
earn their cost. A flattering number here silently corrupts every downstream metric — and it
corrupts them in the direction that makes our own gates look better than they are, which is
the one direction nobody will think to check. If the panel raised something wrong this
sprint, record it.

### 6e. Close Discussion

```bash
python scripts/close_discussion.py <discussion_id>
```

## Step 7: Cross-Project Knowledge Check

Before presenting, ask: **"Did this sprint produce any lessons that belong in shared-memory?"**

Check for:
- New universal warnings (mistakes that would apply to any project)
- Framework innovations (new rules, commands, or agent patterns that are tech-stack agnostic)
- Heritage-worthy discussions (formative moments: crises survived, identity-defining decisions, process evolution)

If yes:
1. Add entries to `~/.claude/shared-memory/universal-warnings.md` (for lessons)
2. Add entries to `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md` (for framework changes)
3. Propose heritage candidates to the developer (heritage promotion requires human approval)
4. Run `bash ~/.claude/sync-all-memories.sh` to push changes to the backup hub

This step ensures that innovations flow outward to sibling projects through the shared-memory propagation channel. See DISC-20260411-171115 for the propagation architecture decision.

## Step 8: Present

Present the retrospective to the developer with specific recommended actions, noting which recommendations were validated by specialist review.

