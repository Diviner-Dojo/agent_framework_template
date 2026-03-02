---
description: "Trigger a structured multi-agent discussion on a topic. Creates a discussion, dispatches specialists, captures all reasoning, and produces a synthesis."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[topic to discuss]"
---

# Structured Multi-Agent Discussion

You are acting as the Facilitator. Run the following workflow step by step.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: Every specialist turn MUST be recorded via `scripts/write_event.py`. Uncaptured reasoning is lost reasoning.
2. **NEVER continue on failure**: If any step fails, HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
3. **ALWAYS include at least 2 specialists**: Single-perspective discussions violate the independence principle (Non-Negotiable Principle #4).
4. **ALWAYS close the discussion**: Every deliberation MUST end with `scripts/close_discussion.py`, even if abandoned.
5. **NEVER resolve dissent artificially**: If specialists disagree, present both sides. Do NOT smooth over genuine disagreements in the synthesis.

## Pre-Flight Checks

Before starting the deliberation, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
for d in ['discussions', 'docs/adr']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Session Resumption Check

Before creating a new discussion, check for an in-progress deliberation:

```bash
python -c "
import pathlib, json
for d in sorted(pathlib.Path('discussions').glob('*/*/state.json'), reverse=True):
    state = json.loads(d.read_text())
    if state.get('command') == 'deliberate' and state.get('status') == 'in_progress':
        print(f'FOUND IN-PROGRESS DELIBERATION: {state[\"discussion_id\"]} (phase: {state.get(\"current_phase\", \"unknown\")})')
        print(f'  Topic: {state.get(\"topic\", \"unknown\")}')
        print(f'  Path: {d.parent}')
        break
else:
    print('No in-progress deliberation sessions found.')
"
```

If an in-progress session is found, ask the developer: **Resume the previous session or start fresh?** If resuming, read phase output files from the discussion directory to restore context.

## Step 1: Create Discussion

Run: `python scripts/create_discussion.py "<slug>" --risk <level> --mode <mode>`

Choose the slug from the topic. Assess risk level based on the topic:
- Low: Documentation, tooling, minor config
- Medium: Feature design, refactoring approach, process changes
- High: Architecture decisions, security design, data model changes
- Critical: Auth/authz design, data migration, infrastructure

Choose collaboration mode:
- Ensemble: Simple topic, just need breadth of perspectives
- Structured Dialogue: Default for most topics
- Dialectic: Genuine competing approaches to evaluate

Record the discussion_id from the output.

Initialize the workflow state file:

```bash
python -c "
import json, pathlib
from datetime import datetime, timezone
state = {
    'command': 'deliberate',
    'discussion_id': '<discussion_id>',
    'status': 'in_progress',
    'started_at': datetime.now(timezone.utc).isoformat(),
    'current_phase': 'specialist_dispatch',
    'completed_phases': ['discussion_created'],
    'topic': '<topic>'
}
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state_path.write_text(json.dumps(state, indent=2))
print(f'State initialized: {state_path}')
"
```

## Step 1.5: Write Context-Brief (Before Specialist Dispatch)

Immediately after initializing `state.json`, capture a context-brief event. This must be
written before any specialist is dispatched — it produces `turn_id=1` in the discussion
and injects developer framing into specialist prompts.

Summarise the developer's request from the current session. Populate all four fields;
write "(none stated)" if a field was not addressed. Strip business context (deadlines,
client names, regulatory pressures) — record structural intent only.

```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "evidence" \
  "## Request Context
- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [topic or materials handed to this deliberation]
- **Developer-stated motivation**: [why this topic is being deliberated, if stated; or 'none stated']
- **Explicit constraints**: [developer-stated constraints agents should respect; or 'none stated']" \
  --tags "context-brief"
```

## Step 2: Assess and Select Specialists

Based on the topic, determine which specialist agents should participate:
- Architecture questions → architecture-consultant
- Security topics → security-specialist
- Quality/testing topics → qa-specialist
- Performance concerns → performance-analyst
- Documentation/knowledge → docs-knowledge
- Complex or high-risk topics → independent-perspective

Always include at least 2 specialists.

## Step 3: Dispatch Specialists

For each selected specialist, use the Task tool:
```
Task(subagent_type="<agent-name>", prompt="Discussion: <discussion_id>\nTopic: <topic>\n\n## Developer Context\n[Paste the four-field content from the context-brief event written in Step 1.5]\n\nAnalyze this topic from your specialist perspective. Provide your structured analysis following your output format.")
```

Run independent specialists in parallel where possible.

## Step 4: Capture Events

For each specialist's response, capture it as an event:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<content>" --confidence <score> --tags "<tags>"
```

If the collaboration mode is Structured Dialogue or Dialectic, run a second round where specialists can respond to each other's findings:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "critique" "<response>" --reply-to <turn_id> --confidence <score>
```

## Step 5: Synthesize

**The synthesis content must begin with a `## Request Context` section** before the
analysis body. Populate all four fields from the developer's original request and session
context. Write "(none stated)" for any field not explicitly addressed — do NOT leave
fields blank or as placeholders.

```
## Request Context
- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [topic or materials handed to this deliberation]
- **Developer-stated motivation**: [why this topic is being deliberated, if stated]
- **Explicit constraints**: [any developer-stated constraints; or "none stated"]
```

Write your synthesis as the facilitator:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "<synthesis>" --confidence <score>
```

If a decision was reached:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "decision" "<decision>" --confidence <score>
```

## Step 6: Close Discussion

Update the workflow state:
```bash
python -c "
import json, pathlib
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state = json.loads(state_path.read_text())
state['current_phase'] = 'complete'
state['completed_phases'].append('synthesis')
state['status'] = 'complete'
state_path.write_text(json.dumps(state, indent=2))
"
```

Run: `python scripts/close_discussion.py "<discussion_id>"`

This generates the transcript, ingests events into SQLite, and seals the discussion.

## Step 7: Present Results

Present to the developer:
1. Summary of the discussion topic
2. Key perspectives from each specialist
3. Points of agreement and disagreement
4. Decision or recommendation reached
5. Confidence level and any caveats
6. Link to the full discussion transcript

If an ADR is warranted, offer to create one using the template at `docs/templates/adr-template.md`.
