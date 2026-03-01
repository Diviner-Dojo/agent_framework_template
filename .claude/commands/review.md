---
description: "Run a multi-agent code review with specialist panel. Assesses risk, assembles the right team, captures all findings, and produces a structured review report."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[file, directory, or description of changes to review]"
---

# Multi-Agent Code Review

You are acting as the Facilitator. Run the following workflow step by step.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: Every specialist turn MUST be recorded via `scripts/write_event.py`. No findings exist unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
3. **NEVER synthesize before all specialists report**: Wait for ALL dispatched specialists to return before writing the synthesis. Premature synthesis misses findings.
4. **ALWAYS close the discussion**: Every review MUST end with `scripts/close_discussion.py`, even if the review is abandoned. Unclosed discussions corrupt the capture stack.
5. **NEVER skip the education gate recommendation**: Every review report MUST include an education gate recommendation, even if the recommendation is "not needed."

## Pre-Flight Checks

Before starting the review, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
for d in ['discussions', 'docs/reviews', 'docs/templates']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
if not pathlib.Path('docs/templates/review-report-template.md').exists():
    errors.append('Missing review report template: docs/templates/review-report-template.md')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Session Resumption Check

Before creating a new discussion, check for an in-progress review session:

```bash
python -c "
import pathlib, json
for d in sorted(pathlib.Path('discussions').glob('*/*/state.json'), reverse=True):
    state = json.loads(d.read_text())
    if state.get('command') == 'review' and state.get('status') == 'in_progress':
        print(f'FOUND IN-PROGRESS REVIEW: {state[\"discussion_id\"]} (phase: {state.get(\"current_phase\", \"unknown\")})')
        print(f'  Started: {state.get(\"started_at\", \"unknown\")}')
        print(f'  Path: {d.parent}')
        break
else:
    print('No in-progress review sessions found.')
"
```

If an in-progress session is found, ask the developer: **Resume the previous session or start fresh?** If resuming, read the phase output files from the discussion directory to restore context. If starting fresh, proceed normally.

## Step 1: Read the Code

Read the files or directory specified by the user. Understand what the code does, what changed (if reviewing a diff), and what risks are present.

## Step 2: Risk Assessment

Assess the risk level of the changes:
- **Low**: Config changes, documentation, simple bug fixes, formatting
- **Medium**: New features, refactoring, test changes, dependency updates
- **High**: Security-related code, architecture changes, database schema, API contracts
- **Critical**: Authentication/authorization, payment processing, data migration, infrastructure

## Step 3: Create Discussion and Initialize State

```
python scripts/create_discussion.py "<slug>" --risk <level> --mode <mode>
```

Select collaboration mode based on risk:
- Low → ensemble
- Medium → structured-dialogue
- High → structured-dialogue or dialectic
- Critical → dialectic

After creating the discussion, initialize the workflow state file:

```bash
python -c "
import json, pathlib
from datetime import datetime, timezone
state = {
    'command': 'review',
    'discussion_id': '<discussion_id>',
    'status': 'in_progress',
    'started_at': datetime.now(timezone.utc).isoformat(),
    'current_phase': 'specialist_dispatch',
    'completed_phases': ['risk_assessment', 'discussion_created'],
    'risk_level': '<level>',
    'collaboration_mode': '<mode>'
}
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state_path.write_text(json.dumps(state, indent=2))
print(f'State initialized: {state_path}')
"
```

## Step 4: Assemble Specialist Team

Select specialists based on what's being reviewed:
- **Always**: qa-specialist (every code review)
- **API/endpoint changes**: security-specialist, performance-analyst
- **Database changes**: performance-analyst, security-specialist
- **Architecture/module boundaries**: architecture-consultant
- **New modules or significant features**: architecture-consultant, docs-knowledge
- **UI/screen changes**: ux-evaluator, qa-specialist
- **High/Critical risk**: independent-perspective
- **Security-related**: security-specialist (adversarial mode)

## Step 5: Dispatch Specialists

For each specialist, use the Task tool with the code content and review context:

```
Task(subagent_type="<agent-name>", prompt="Code Review: <discussion_id>\nRisk Level: <level>\n\nReview the following code from your specialist perspective:\n\n<code content>\n\nProvide your structured analysis following your output format. Include confidence score.")
```

Run independent specialists in parallel.

## Step 6: Capture Events

For each specialist's response:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<findings>" --confidence <score> --tags "<tags>"
```

For structured-dialogue mode, run a second round where specialists can respond to each other. Capture those as critiques with --reply-to.

## Step 7: Synthesize Review Report

Before writing the synthesis, count findings across all specialist responses:
- **Blocking findings**: Issues that must be fixed before merge (security vulnerabilities, correctness bugs, architectural violations)
- **Advisory findings**: Recommendations that improve quality but don't block merge

Include these counts as tags on the synthesis event for yield tracking.

Write the synthesis event:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "<synthesis>" --confidence <score> --tags "blocking:<N>,advisory:<M>"
```

Create the review report following `docs/templates/review-report-template.md` and save it to:
```
docs/reviews/REV-YYYYMMDD-HHMMSS.md
```

Update the workflow state:
```bash
python -c "
import json, pathlib
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state = json.loads(state_path.read_text())
state['current_phase'] = 'complete'
state['completed_phases'].append('synthesis')
state['status'] = 'complete'
state['report_path'] = 'docs/reviews/REV-YYYYMMDD-HHMMSS.md'
state_path.write_text(json.dumps(state, indent=2))
"
```

## Step 7b: Record Protocol Yield

After synthesizing, record the yield metrics for this review:

```bash
python scripts/record_yield.py "<discussion_id>" review <verdict> --blocking <N> --advisory <M> --turns <agent_turn_count>
```

Where `<verdict>` maps to: approve, approve-with-changes, request-changes, or reject.

## Step 7c: Request Agent Reflections

After recording yield, request reflections from each specialist who participated (non-blocking — failures do not halt closure). For each specialist:

1. Dispatch a reflection request (sonnet tier, 150-word cap):
   ```
   Task(subagent_type="<agent-name>", model="sonnet", prompt="Reflection Request: <discussion_id>\n\nYou just completed a review. Reflect briefly (under 150 words) on:\n1. What did you miss or what would you check next time?\n2. What improvement rule would you propose for future reviews?\n3. Was your confidence appropriate given what you found?\n\nFormat:\n## What I Missed\n<text>\n## Candidate Improvement Rule\n<text>\n## Confidence Calibration\nOriginal: X.X, Revised: Y.Y, Delta: ±Z.Z")
   ```

2. Capture each reflection:
   ```bash
   python scripts/write_event.py "<discussion_id>" "<agent-name>" "reflection" "<reflection_content>" --tags "reflection"
   ```

3. Ingest each reflection into SQLite:
   ```bash
   python -c "
   import pathlib, tempfile
   content = '''---
   reflection_id: REFL-<timestamp>-<agent>
   discussion_id: <discussion_id>
   agent: <agent-name>
   timestamp: <now>
   ---

   <reflection_content>
   '''
   p = pathlib.Path(tempfile.mktemp(suffix='.md'))
   p.write_text(content, encoding='utf-8')
   from scripts.ingest_reflection import ingest_reflection
   ingest_reflection(p)
   p.unlink()
   "
   ```

If a specialist fails to produce a reflection, log the gap and continue to closure. Do NOT block on reflection failures.

## Step 8: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

Note: `close_discussion.py` now automatically extracts findings, surfaces promotion candidates, and computes agent effectiveness as part of the closure pipeline.

## Step 9: Present to Developer

Present:
1. **Verdict**: approve / approve-with-changes / request-changes / reject
2. **Required changes** (blocking): Must be addressed before merge
3. **Recommended improvements** (non-blocking): Should be addressed but don't block
4. **Strengths**: What the code does well
5. **Education gate**: Whether a walkthrough/quiz is needed and at what Bloom's level

## Step 10: Education Gate (if needed)

For medium-risk and above, recommend the developer run:
- `/walkthrough <files>` for guided code reading
- `/quiz <files>` for comprehension assessment

Record the education gate recommendation in the review report.
