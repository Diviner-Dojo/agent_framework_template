---
description: "Generate a guided walkthrough of code for developer education. Education gate step 1."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task"]
argument-hint: "[file or directory to walk through]"
---

# Guided Code Walkthrough (Education Gate Step 1)

Delegate to the educator agent to produce a guided reading path.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: The educator's walkthrough output MUST be recorded via `scripts/write_event.py`. No walkthrough exists unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed.
3. **ALWAYS close the discussion**: Every walkthrough MUST end with `scripts/close_discussion.py`, even if abandoned.

## Pre-Flight Checks

Before starting the walkthrough, verify the target file(s) exist and prerequisites are available:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('.claude/agents/educator.md').exists():
    errors.append('Missing educator agent definition: .claude/agents/educator.md')
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the target file or directory specified by the user does not exist, tell the developer and ask for the correct path.

## Workflow

### Step 1: Create Discussion

```
python scripts/create_discussion.py "walkthrough-<slug>" --risk low --mode ensemble
```

Store the returned discussion ID.

### Step 2: Read and Dispatch

1. Read the specified file(s) or directory
2. Dispatch to the educator agent:

```
Task(subagent_type="educator", prompt="Generate a guided walkthrough for the following code. Use progressive disclosure: start with high-level summary, then module structure, then key functions, then implementation details. Connect to relevant ADRs in docs/adr/. Adapt depth to code complexity.\n\nCode:\n<code content>")
```

### Step 3: Capture

Record the educator's walkthrough output:
```
python scripts/write_event.py "<discussion_id>" "educator" "proposal" "<walkthrough content>" --confidence <score> --tags "walkthrough,education"
```

### Step 4: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

### Step 5: Present

Present the walkthrough to the developer. After they have read it, suggest they run `/quiz` to verify understanding.
