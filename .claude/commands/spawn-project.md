---
description: "Create a new project from the framework template"
allowed-tools: ["Read", "Bash", "Glob"]
argument-hint: "<target-folder-path> <project-name>"
---

# Spawn New Project

Create a new project from this framework template. Copies framework files, initializes lineage tracking and the metrics database, and optionally sets up a git repository.

## Parse Arguments

Extract the target folder path and project name from the user's input: $ARGUMENTS

The first argument is the target folder path. The second argument is the project name (may be quoted).

If either is missing, ask the user:
- "Where should I create the project? (full path to a folder that doesn't exist yet)"
- "What should the project be called?"

## Pre-Flight

Verify the target directory does not already exist. If it does, tell the user and ask for a different path.

## Run

```bash
python scripts/spawn_project.py "<target-folder-path>" --name "<project-name>"
```

If the user says they don't want git initialized, add `--no-git`.

## Post-Spawn Guidance

After the script completes, tell the user:

1. **Open the new project folder** in your editor
2. **Review and customize `CLAUDE.md`** — update the project identity section with your project's name, description, and tech stack
3. **Review and customize `PHILOSOPHY.md`** — replace the template's mission statement with your own
4. **Install dependencies**: `pip install -r requirements.txt`
5. **Verify**: `python scripts/quality_gate.py`
6. **Start building**: Use `/plan` for your first feature
