---
description: "Run a quarterly framework evaluation (macro loop). Assesses agent effectiveness, architectural drift, rule updates, and framework evolution."
allowed-tools: ["Read", "Write", "Bash", "Glob", "Grep", "Task"]
---

# Quarterly Framework Evaluation (Macro Loop)

You are acting as the Facilitator running the quarterly macro loop. This is the double-loop learning check: we question whether our review criteria themselves are correct.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: Every specialist turn MUST be recorded via `scripts/write_event.py`. No findings exist unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
3. **NEVER synthesize before all specialists report**: Wait for ALL dispatched specialists to return before writing the synthesis. Premature synthesis misses findings.
4. **ALWAYS close the discussion**: Every meta-review MUST end with `scripts/close_discussion.py`, even if abandoned. Unclosed discussions corrupt the capture stack.

## Pre-Flight Checks

Before running the meta-review, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
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
import sqlite3, sys
conn = sqlite3.connect('metrics/evaluation.db')
broken = []
degraded = []

# The EXPLICIT set of schema objects this command knows how to read. It is the only thing that
# licenses the benign 'pre-migration' story, and it must be a literal list — never inferred from
# the error text. 'no such table' is NOT self-evidently a missing migration:
#   * name IN this set     -> this project's DB predates a migration. DEGRADED (exit 2), keep going.
#   * name NOT in this set -> the command is asking for something that was never in the schema,
#                             i.e. a typo or an un-propagated rename. INSTRUMENT FAILURE (exit 1).
# Without this discrimination, misspelling a view here reads as 'normal for this project' and the
# meta-review silently loses that instrument — the exact defect this command was repaired to kill.
KNOWN_OBJECTS = ['discussions', 'turns', 'findings', 'reflections', 'education_results',
                 'promotion_candidates', 'protocol_yield', 'v_agent_dashboard', 'v_rule_of_three']

# An instrument that cannot be READ is a FAILURE, not an absence of data. Never downgrade a
# query error to '(X not available)': a broken read path that reports itself as merely
# unavailable teaches the reader that missing data is normal, and the defect survives every
# meta-review. Guarded by tests/test_command_sql.py.
def note_error(label, e, context):
    msg = str(e)
    if msg.startswith('no such table'):
        name = msg.split(':', 1)[1].strip().split('.')[-1] if ':' in msg else ''
        if name in KNOWN_OBJECTS:
            print('SCHEMA SKEW [' + label + ']: ' + msg)
            print('  This project predates that migration — run scripts/init_db.py. Section DEGRADED.')
            degraded.append(label)
            return
        print('INSTRUMENT FAILURE [' + label + ']: \'' + name + '\' is not an object this command knows.')
        print('  This is a typo or an un-propagated rename, NOT a missing migration.')
        print('  Objects this command knows: ' + ', '.join(KNOWN_OBJECTS))
        print('  ' + context)
        broken.append(label)
        return
    print('INSTRUMENT FAILURE [' + label + ']: ' + type(e).__name__ + ': ' + msg)
    print('  ' + context)
    broken.append(label)

def dump(label, sql):
    print('=== ' + label + ' ===')
    try:
        rows = conn.execute(sql).fetchall()
    except sqlite3.Error as e:
        note_error(label, e, 'query: ' + sql)
        return
    if not rows:
        print('(query succeeded, zero rows)')
    for row in rows:
        print(row)

# This file is CORE and propagates to derived projects whose evaluation.db may carry
# pre-migration column names for the same instrument. Resolve names from the REAL schema
# before building any ORDER BY / GROUP BY — never hardcode hub names into a propagating file.
# SQL-injection note: only a column/table name from a LITERAL list in this file is ever
# interpolated below, and it must also appear in the introspected schema. No caller-
# supplied value reaches the statement; row VALUES stay parameterised (see security_baseline).
def resolve(label, probe, prefs):
    try:
        cols = [d[0] for d in conn.execute(probe).description]
    except sqlite3.Error as e:
        # Same discrimination as dump(): an unknown object name here is a typo/rename, not a
        # migration this project has not run yet. Reporting it as SCHEMA SKEW would let a
        # misspelled view leave the meta-review green.
        note_error(label, e, 'probe: ' + probe)
        return None
    for c in prefs:
        if c in cols:
            return c
    print('INSTRUMENT FAILURE [' + label + ']: none of ' + str(prefs) + ' exist.')
    print('  actual columns: ' + str(cols))
    print('  The schema drifted past every name this command knows. Fix the view or extend')
    print('  the preference list — do NOT report this as an absence of data.')
    broken.append(label)
    return None

def dump_ordered(label, table, prefs, direction=' DESC'):
    col = resolve(label, 'SELECT * FROM ' + table + ' LIMIT 0', prefs)
    if col is None:
        return
    dump(label + ' (by ' + col + ')', 'SELECT * FROM ' + table + ' ORDER BY ' + col + direction)

def dump_grouped(label, table, prefs):
    col = resolve(label, 'SELECT * FROM ' + table + ' LIMIT 0', prefs)
    if col is None:
        return
    dump(label + ' (by ' + col + ')', 'SELECT ' + col + ', COUNT(*) FROM ' + table + ' GROUP BY ' + col)

dump('Discussion Summary', 'SELECT risk_level, collaboration_mode, COUNT(*), AVG(agent_count) FROM discussions GROUP BY risk_level, collaboration_mode')
dump('Agent Effectiveness (turns)', 'SELECT agent, intent, COUNT(*), AVG(confidence) FROM turns GROUP BY agent, intent')
# Rank agents by DISTINCT findings contributed — 'effectiveness' here means unique signal,
# not raw volume. 'total_unique_findings' is the hub name, 'total_findings' the older one.
dump_ordered('Agent Effectiveness (dashboard)', 'v_agent_dashboard', ['total_unique_findings', 'total_findings'])
dump('Findings Summary', 'SELECT category, severity, COUNT(*) FROM findings GROUP BY category, severity ORDER BY COUNT(*) DESC')
# Rule of Three is a per-discussion threshold, so rank by the view's own discussion count.
dump_ordered('Rule of Three', 'v_rule_of_three', ['sighting_count', 'discussion_count'])
# Group promotion candidates by their lifecycle column: 'promoted' (hub 0/1) or 'status' (older).
dump_grouped('Promotion Candidates', 'promotion_candidates', ['promoted', 'status'])
dump('Reflection Patterns', 'SELECT agent, COUNT(*), AVG(confidence_delta), SUM(promoted) FROM reflections GROUP BY agent')
dump('Education Trends', 'SELECT bloom_level, AVG(score), SUM(passed), COUNT(*) FROM education_results GROUP BY bloom_level')
conn.close()
if broken:
    print('')
    print('BROKEN INSTRUMENTS: ' + ', '.join(broken))
    print('These queries cannot read the schema: either the query is wrong against a schema that IS')
    print('present, or it names an object that was never in the schema (typo / un-propagated')
    print('rename). Neither is a missing migration. The meta-review judges framework health from')
    print('exactly these numbers — fix the query or the view before continuing.')
    sys.exit(1)
if degraded:
    print('')
    print('DEGRADED INSTRUMENTS: ' + ', '.join(degraded))
    print('These objects are absent from this project s evaluation.db (pre-migration). The')
    print('meta-review may continue, but MUST state which instruments were unreadable and')
    print('must not present its conclusions as covering them.')
    sys.exit(2)
"
```

Read the exit code, do not just read the output:

- **exit 1 — BROKEN**: stop. Either the schema is there and the query is wrong, or the query names
  an object outside `KNOWN_OBJECTS` — a typo or an un-propagated rename. A meta-review written on
  a silently-failing instrument under-reports whatever that instrument measured.
- **exit 2 — DEGRADED**: this project's DB predates a migration — and only for an object the
  command explicitly knows. Continue, but name the missing instruments in the report and scope the
  conclusions to what was actually readable.
- **exit 0**: every instrument answered.

Adding a new instrument to this step means adding its table/view name to `KNOWN_OBJECTS` in the
same edit. If you forget, the command fails loudly (exit 1) rather than quietly calling your new
instrument "pre-migration" — which is the intended failure direction.

## Step 2: Deep Analysis

### Agent Effectiveness Scoring

Query `v_agent_dashboard` for data-driven agent assessment:

```bash
python -c "
import sqlite3, sys
conn = sqlite3.connect('metrics/evaluation.db')
conn.row_factory = sqlite3.Row

# CORE file -> propagates to schema-divergent derived projects. Introspect, branch on a
# documented preference list, and read rows BY NAME. A fixed positional unpack would raise
# on any schema variant, converting a readable instrument into a dead command.
#
# CLASSIFICATION MUST MATCH STEP 1. v_agent_dashboard is in Step 1's KNOWN_OBJECTS, so an
# absent view there is SCHEMA SKEW (exit 2, keep going). If this step called the same absence
# INSTRUMENT FAILURE (exit 1, stop), /meta-review would print Step 1's 'the meta-review may
# continue' banner and then hard-stop here — one command asserting two different contracts for
# one condition. 'no such table: v_agent_dashboard' is the ONLY benign story; any other object
# name, or any error against a view that exists, stays INSTRUMENT FAILURE.
try:
    cols = [d[0] for d in conn.execute('SELECT * FROM v_agent_dashboard LIMIT 0').description]
except sqlite3.Error as e:
    conn.close()
    msg = str(e)
    if msg == 'no such table: v_agent_dashboard':
        print('SCHEMA SKEW [v_agent_dashboard]: ' + msg)
        print('  This project predates the agent_effectiveness migration — run scripts/init_db.py.')
        print('  Agent-effectiveness scoring is DEGRADED: it was NOT computed. Say so in the report.')
        sys.exit(2)
    print('INSTRUMENT FAILURE [v_agent_dashboard]: cannot read schema: ' + type(e).__name__ + ': ' + msg)
    print('The probe names something other than v_agent_dashboard, or the view exists and the read')
    print('still failed. Neither is a missing migration — fix the view (scripts/init_db.py) or the query.')
    sys.exit(1)

# SQL-injection note: only a column/table name from a LITERAL list in this file is ever
# interpolated below, and it must also appear in the introspected schema. No caller-
# supplied value reaches the statement; row VALUES stay parameterised (see security_baseline).
# Rank by distinct value contributed, which is what 'effectiveness' means in this step.
order = None
for c in ['total_unique_findings', 'total_findings']:
    if c in cols:
        order = c
        break
if order is None:
    conn.close()
    print('INSTRUMENT FAILURE [v_agent_dashboard]: no known ranking column.')
    print('  actual columns: ' + str(cols))
    print('  Fix the view or extend the preference list — do NOT report this as an absence of data.')
    sys.exit(1)

try:
    rows = conn.execute('SELECT * FROM v_agent_dashboard ORDER BY ' + order + ' DESC').fetchall()
except sqlite3.Error as e:
    conn.close()
    print('INSTRUMENT FAILURE [v_agent_dashboard]: ' + type(e).__name__ + ': ' + str(e))
    print('This is the agent-effectiveness instrument. Do NOT fall back to a hand-wave — fix the query or the view.')
    sys.exit(1)
conn.close()

def get(row, *names):
    for n in names:
        if n in row.keys():
            return row[n]
    return None

# Presence of the COLUMN, not truthiness of the value — see the note in retro.md 4c. Dropping
# a NULL would shrink the instrument for exactly the rows where a ratio was undefined.
def has(row, name):
    return name in row.keys()

if rows:
    print('(ranked by ' + order + ')')
    for row in rows:
        # Print every column the schema actually offers, in BOTH directions: hub-only columns
        # (duplicates / false positives) AND pre-migration-only columns (raw volume, survival).
        # Repair must never quietly narrow an instrument — a column that the DB can answer and
        # this block declines to print is measurement deleted by the fix.
        bits = [str(get(row, 'discussions_participated', 'discussions')) + ' disc']
        if has(row, 'total_findings'):
            bits.append(str(get(row, 'total_findings')) + ' findings')
        bits.append(str(get(row, 'total_unique_findings', 'total_unique')) + ' unique')
        if has(row, 'total_duplicate_findings'):
            bits.append(str(get(row, 'total_duplicate_findings')) + ' dup')
        if has(row, 'total_false_positives'):
            bits.append(str(get(row, 'total_false_positives')) + ' false-pos')
        bits.append('uniqueness=' + str(get(row, 'uniqueness_ratio', 'uniqueness_pct')))
        if has(row, 'survival_pct'):
            bits.append('survived=' + str(get(row, 'survival_pct')))
        bits.append('conf=' + str(get(row, 'avg_confidence')))
        bits.append('calib=' + str(get(row, 'avg_calibration')))
        print(str(get(row, 'agent')) + ': ' + ', '.join(bits))
else:
    print('v_agent_dashboard is readable but empty — no agent_effectiveness rows recorded yet. Fall back to manual analysis from the turns table and say so in the report.')
"
```

Read this block's exit code with the SAME meaning as Step 1 — the two must never disagree:

- **exit 2 — DEGRADED**: `v_agent_dashboard` is absent because this project's DB predates the
  agent_effectiveness migration. The meta-review continues; the report must name this instrument
  as unreadable and must not present agent-effectiveness conclusions as covering it.
- **exit 1 — INSTRUMENT FAILURE**: the probe named something other than `v_agent_dashboard`, or
  the view exists and the read still failed. Stop and fix it.
- **exit 0**: the instrument answered.

Assess (column names vary by schema generation — the block prints whichever it found):
- Which agents find unique issues vs. duplicates? (`uniqueness_ratio`, or `uniqueness_pct` pre-migration)
- Which agents have the best confidence calibration? (`avg_calibration`)
- Which agents produce the most false positives? (`total_false_positives`, hub schema only)
- Which agents' findings survive into synthesis? (`survival_pct`, pre-migration schema only)
- How much raw volume does each agent produce? (`total_findings`, pre-migration schema only)
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

## Step 4: Draft Framework Evolution Report

Write a DRAFT meta-review report (do NOT finalize yet — specialists will review it):

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

## Knowledge Pipeline Health
[Run `python scripts/knowledge_dashboard.py --no-log` and include results]
[Findings coverage, pattern mining, Layer 3 population, promotion throughput]
[Rule of Three hits from v_rule_of_three view]
[Forgetting curve status from `python scripts/enforce_forgetting_curve.py --dry-run`]

## Double-Loop Findings
[Meta-level insights about the review process itself]

## Protocol Overhead Audit

For each protocol type (review, checkpoint, education_gate, quality_gate, retro):

| Protocol | Invocations | Duration (min) | Blocking Findings | Advisory | Yield/Min | Trend |
|----------|------------|----------------|-------------------|----------|-----------|-------|
| review | | | | | | |
| checkpoint | | | | | | |
| education_gate | | | | | | |
| quality_gate | | | | | | |
| retro | | | | | | |

Query protocol_yield table (if available) or estimate from discussion transcripts.
Also query quality_gate_log.jsonl for gate pass/fail trends. Note three `overall` values:
`pass` (all checks ran and passed), `pass_with_skips` (≥1 check skipped via `--skip-*`),
and `fail` (a check that ran failed). Count `pass_with_skips` **separately** — do not fold
it into `pass`, or you will over-report clean gate runs.

Assess:
- **Redundancy**: Are multiple protocols catching the same issues? Which could be consolidated?
- **Solo-dev calibration**: Which protocols are designed for team-scale and add disproportionate overhead for a solo developer?
- **Efficiency trend**: Is each protocol getting faster (learning curve) or slower (scope creep)?
- **Explicit question**: "Which protocols should be relaxed for solo development?"

Present findings as analysis input. Do NOT recommend automatic relaxation (Principle #7 — human decides).
```

## Step 5: Adoption Log Trend Assessment

Review `memory/lessons/adoption-log.md` for macro-level trends:
1. **Adoption rate**: Are we importing too aggressively or too conservatively?
2. **Rejection patterns**: Are certain categories consistently rejected? Should we stop looking for them?
3. **Adopted pattern usage**: Are imported patterns actually being used, or are they shelfware?
4. **Score calibration**: Are our scoring thresholds (20/25) too high or too low?
5. **Rule of Three**: How many patterns have hit 3+ sightings? What percentage were eventually adopted?

Add findings to the draft under a "## External Learning Assessment" section.

## Step 6: Create Discussion + Dispatch Specialists

### 6a. Create Discussion

```bash
python scripts/create_discussion.py "meta-review-YYYYMMDD" --risk medium --mode structured-dialogue
```

Use the actual date. Save the returned `discussion_id` — you will need it for all subsequent capture calls.

### 6b. Capture Draft as Proposal Event

```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent proposal \
  --content "<the full draft meta-review text>" \
  --tags "meta-review,draft"
```

### 6c. Dispatch Specialists

Dispatch exactly 2 specialists in parallel to review the DRAFT meta-review:

1. **architecture-consultant** (sonnet for this context) — validate drift findings against actual ADRs, check whether proposed rule changes align with architectural boundaries
2. **independent-perspective** (sonnet) — challenge the framework evaluation itself (the meta-meta check: are we evaluating the right things?)

Use `Task(subagent_type="architecture-consultant", model="sonnet", ...)` and `Task(subagent_type="independent-perspective", model="sonnet", ...)` in parallel.

Structured-dialogue mode: because the architecture-consultant's drift validation may interact with the independent-perspective's framework challenge, share a brief summary of each specialist's response with the other if there are material disagreements.

Prompt template for each specialist:
```
Meta-Review Specialist Check: <discussion_id>

Review this DRAFT quarterly framework evaluation from your specialist perspective.

<draft meta-review content>

Focus on:
- [architecture-consultant]: Are the drift findings accurate? Do proposed rule changes align with recorded ADRs? Are there drift signals we missed?
- [independent-perspective]: Is this evaluation asking the right questions? Are there blind spots in how we assess the framework? Is the double-loop check genuine or performative?

Respond with your assessment (under 300 words).
```

### 6d. Capture Specialist Responses

After BOTH specialists return, capture each response:

```bash
python scripts/write_event.py <discussion_id> \
  --agent architecture-consultant \
  --intent critique \
  --content "<specialist response>" \
  --tags "meta-review,specialist-review"

python scripts/write_event.py <discussion_id> \
  --agent independent-perspective \
  --intent critique \
  --content "<specialist response>" \
  --tags "meta-review,specialist-review"
```

### 6e. Incorporate Feedback

Review both specialist responses and incorporate their feedback into the final meta-review. Note which drift findings were validated or challenged, and which proposed framework adjustments were endorsed or questioned.

## Step 7: Finalize and Close

### 7a. Write Final Meta-Review

Save the final version to `docs/sprints/META-REVIEW-YYYYMMDD.md`, incorporating specialist feedback. Add a "## Specialist Review Notes" section summarizing what the specialists found.

### 7b. Capture Synthesis Event

```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent synthesis \
  --content "<summary of final meta-review with specialist input incorporated>" \
  --tags "meta-review,synthesis"
```

### 7c. Close Discussion

```bash
python scripts/close_discussion.py <discussion_id>
```

## Step 8: Present and Implement

Present the report to the developer, noting which findings were validated by specialist review. With approval, update:
- `.claude/rules/` files if warranted
- Agent definitions if calibration needs changing
- CLAUDE.md if conventions have evolved
- Archive deprecated patterns from `memory/`
