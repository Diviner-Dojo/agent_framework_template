---
description: "Bootstrap a new project into the framework. Scaffolds empty structures, wires hooks, copies universal principles, and creates the project's first discussion."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[target project path]"
---

# Seed a New Project into the Framework

You are acting as the Facilitator. This command bootstraps a brand-new project (or empty repo) into the AI-Native Agentic Development Framework. Unlike `/onboard` (which adapts an existing codebase), `/seed` starts fresh.

## Pre-Flight

1. Verify the target project path exists and is a git repo:
   ```bash
   cd "$ARGUMENTS" && git status
   ```
   If it doesn't exist or isn't a git repo, ask the developer.

2. Check that shared memory is available:
   ```bash
   ls ~/.claude/shared-memory/FRAMEWORK.md ~/.claude/shared-memory/PHILOSOPHY.md 2>/dev/null
   ```
   If missing, warn the developer that shared memory hasn't been set up yet.

## Step 1: Copy Universal Principles

Copy the framework's universal files into the project root:

```bash
TARGET="$ARGUMENTS"
cp ~/.claude/shared-memory/FRAMEWORK.md "$TARGET/FRAMEWORK.md"
# Only copy PHILOSOPHY.md if the same developer owns both projects
# (PHILOSOPHY.md contains the developer's values — it transfers when the human is the same)
cp ~/.claude/shared-memory/PHILOSOPHY.md "$TARGET/PHILOSOPHY.md" 2>/dev/null || true
```

## Step 2: Scaffold Directory Structure

Create the framework skeleton with empty directories and placeholder files:

```
.claude/
  agents/       — Copy all agent definitions from shared-memory or template
  commands/     — Copy all command definitions
  hooks/        — Copy hook scripts
  rules/        — Copy rule files
docs/
  adr/          — Empty, ready for project's own decisions
  reviews/      — Empty
  sprints/      — Empty
  templates/    — Copy review, ADR, reflection templates
discussions/    — Empty Layer 1
memory/
  archive/
  bugs/         — Create regression-ledger.md with headers only
  decisions/    — Create retro-action-registry.md with headers only
  lessons/      — Create adoption-log.md with headers only
  patterns/
  reflections/
  projects/     — Create _self.md with empty template
  rules/
  security/     — Create threat-model.md with headers only
  performance/  — Create hotspot-registry.md with headers only
  ux/           — Create design-patterns.md with headers only
  architecture/ — Create drift-log.md with headers only
metrics/        — Initialize evaluation.db
scripts/        — Copy capture pipeline scripts
```

For each standing document (regression-ledger, threat-model, etc.), create the file with proper headers but no entries. The project will fill these as it works.

## Step 3: Wire Hooks

Create `.claude/settings.json` with the standard hook configuration:
- PreToolUse: file locking, secret detection, pre-commit gate, pre-push main blocker
- PostToolUse: auto-format, lock release
- PreCompact: BUILD_STATUS.md reminder + shared memory sync
- SessionStart: BUILD_STATUS.md restore + process health nudge

Adapt the auto-format hook to the project's tech stack (not all projects use `dart format`).

## Step 4: Initialize Database

```bash
cd "$TARGET" && python scripts/init_db.py
```

This creates `metrics/evaluation.db` with the correct schema for the capture pipeline.

## Step 5: Create Project CLAUDE.md

Generate a project-specific CLAUDE.md that:
1. References FRAMEWORK.md for universal principles
2. Contains placeholders for: tech stack, formatting command, test command, coverage target, dependencies
3. Has an empty "Autonomous Execution Authorization" section (developer fills in)
4. Has an empty "Clinical UX Constraints" section (or domain-specific equivalent)
5. Has a "Pre-Build Lookup" section pointing to the project's own regression ledger and _self.md

Ask the developer to fill in the project-specific values.

## Step 6: Symlink Shared Memory

Create a junction/symlink so the project can read shared memory:

```bash
# Windows (junction)
cmd //c "mklink /J \"$TARGET\\.claude\\shared-memory\" \"$HOME\\.claude\\shared-memory\""
# Unix (symlink)
# ln -s ~/.claude/shared-memory "$TARGET/.claude/shared-memory"
```

Add to `.gitignore`: `.claude/shared-memory`

## Step 7: Heritage Discovery

Check if a heritage collection exists and tell the developer:

```bash
if [ -d ~/.claude/shared-memory/heritage ]; then
  COUNT=$(find ~/.claude/shared-memory/heritage -name "*.md" -not -name "HERITAGE.md" | wc -l)
  echo "Heritage collection found: $COUNT formative discussions from prior projects."
  echo "Read ~/.claude/shared-memory/heritage/HERITAGE.md for the reading guide."
fi
```

If heritage exists, add to the session-start hook a note that heritage is available.

## Step 8: Create First Discussion

Create the project's origin story — its first Layer 1 discussion:

```bash
cd "$TARGET"
python scripts/create_discussion.py "why-we-adopted-this-framework"
```

Then capture a facilitator turn documenting:
- Why this project adopted the framework
- What the developer hopes to gain from it
- What the project's domain is
- Any inherited warnings from the universal-warnings.md that are especially relevant

Ask the developer these questions. Their answers become the project's founding document.

## Step 9: Embed Universal Warnings

If `~/.claude/shared-memory/universal-warnings.md` exists, read it and note which warnings are most relevant to the new project's domain. Add a reference in the project's CLAUDE.md or memory.

## Step 10: Verification

Run a quick check that everything is wired:
1. `ls .claude/agents/ | wc -l` — should be 12+
2. `ls .claude/commands/ | wc -l` — should be 15+
3. `ls .claude/rules/ | wc -l` — should be 10+
4. `test -f FRAMEWORK.md` — universal principles present
5. `test -f CLAUDE.md` — project-specific config present
6. `test -f metrics/evaluation.db` — capture database initialized
7. `test -d discussions/` — Layer 1 ready
8. `test -d memory/bugs/` — standing documents ready

Report results to the developer.

## What /seed Does NOT Do

- Does not copy any project-specific memories from other projects (contamination risk)
- Does not copy regression ledger entries (those are instance-specific)
- Does not copy ADRs from other projects (decisions are project-specific)
- Does not set up CI/CD (that's project-specific infrastructure)
- Does not configure the tech stack (developer fills in CLAUDE.md)

## After Seeding

Tell the developer:
1. Fill in the placeholders in CLAUDE.md (tech stack, formatting, testing)
2. Read FRAMEWORK.md to understand the universal principles
3. Read the heritage collection if it exists (`~/.claude/shared-memory/heritage/HERITAGE.md`)
4. Read universal-warnings.md for lessons from prior projects
5. Run `/review` on your first code change to verify the pipeline works
6. Your first `/retro` should happen within 2 weeks of starting
