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
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
print('=== Discussion Summary ===')
for row in conn.execute('SELECT risk_level, collaboration_mode, COUNT(*), AVG(agent_count) FROM discussions GROUP BY risk_level, collaboration_mode'):
    print(row)
print('=== Agent Effectiveness (turns) ===')
for row in conn.execute('SELECT agent, intent, COUNT(*), AVG(confidence) FROM turns GROUP BY agent, intent'):
    print(row)
print('=== Agent Effectiveness (dashboard) ===')
try:
    for row in conn.execute('SELECT * FROM v_agent_dashboard ORDER BY total_findings DESC'):
        print(row)
except: print('(v_agent_dashboard not available)')
print('=== Findings Summary ===')
try:
    for row in conn.execute('SELECT category, severity, COUNT(*) FROM findings GROUP BY category, severity ORDER BY COUNT(*) DESC'):
        print(row)
except: print('(findings table not available)')
print('=== Rule of Three ===')
try:
    for row in conn.execute('SELECT * FROM v_rule_of_three ORDER BY discussion_count DESC'):
        print(row)
except: print('(v_rule_of_three not available)')
print('=== Promotion Candidates ===')
try:
    for row in conn.execute('SELECT status, COUNT(*) FROM promotion_candidates GROUP BY status'):
        print(row)
except: print('(promotion_candidates not available)')
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

Query `v_agent_dashboard` for data-driven agent assessment:

```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
try:
    rows = conn.execute('SELECT * FROM v_agent_dashboard ORDER BY total_findings DESC').fetchall()
    if rows:
        for agent, disc, total, unique, uniq_pct, surv_pct, avg_conf, avg_cal in rows:
            print(f'{agent}: {disc} disc, {total} findings, {uniq_pct or 0}% unique, {surv_pct or 0}% survived, conf={avg_conf or 0:.3f}')
    else:
        print('No agent effectiveness data — fall back to manual analysis from turns table.')
except sqlite3.OperationalError:
    print('v_agent_dashboard not available — fall back to manual analysis.')
conn.close()
"
```

Assess:
- Which agents find unique issues vs. duplicates? (uniqueness_pct)
- Which agents have the best confidence calibration? (avg_calibration)
- Which agents' findings survive into synthesis? (survival_pct)
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
Also query quality_gate_log.jsonl for gate pass/fail trends.

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
