---
description: "Generate a guided walkthrough of code for developer education. Education gate step 1."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task"]
argument-hint: "[file or directory to walk through]"
---

# Guided Code Walkthrough (Education Gate Step 1)

Delegate to the educator agent to produce a guided reading path.

## Pre-Flight Checks

Before starting the walkthrough, verify the target file(s) exist and the educator agent is available:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('.claude/agents/educator.md').exists():
    errors.append('Missing educator agent definition: .claude/agents/educator.md')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the target file or directory specified by the user does not exist, tell the developer and ask for the correct path.

## Workflow

1. Read the specified file(s) or directory
2. Dispatch to the educator agent:

```
Task(subagent_type="educator", prompt="Generate a guided walkthrough for the following code. Use progressive disclosure: start with high-level summary, then module structure, then key functions, then implementation details. Connect to relevant ADRs in docs/adr/. Adapt depth to code complexity.\n\nCode:\n<code content>")
```

3. Present the walkthrough to the developer
4. After the developer has read it, suggest they run `/quiz` to verify understanding
