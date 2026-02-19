---
description: "Generate a guided walkthrough of code for developer education. Education gate step 1."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task"]
argument-hint: "[file or directory to walk through]"
---

# Guided Code Walkthrough (Education Gate Step 1)

Delegate to the educator agent to produce a guided reading path.

## Workflow

1. Read the specified file(s) or directory
2. Dispatch to the educator agent:

```
Task(subagent_type="educator", prompt="Generate a guided walkthrough for the following code. Use progressive disclosure: start with high-level summary, then module structure, then key functions, then implementation details. Connect to relevant ADRs in docs/adr/. Adapt depth to code complexity.\n\nCode:\n<code content>")
```

3. Present the walkthrough to the developer
4. After the developer has read it, suggest they run `/quiz` to verify understanding
