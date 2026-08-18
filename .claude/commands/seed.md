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

2. Confirm this template has the philosophy the seeded constitution will cite:
   ```bash
   grep -q "Growth has a brake" ./PHILOSOPHY.md || echo "FATAL: template PHILOSOPHY.md is not current"
   ```
   Shared memory is **optional** — do not gate on it. `/seed` must work on a machine
   that has never had `~/.claude/shared-memory/`.

## Step 1: Copy the Philosophy

> **`FRAMEWORK.md` is retired (ADR-0036).** It used to be copied here as a second
> constitution and it drifted four months out of date, publishing a competing
> list of eight while `CLAUDE.md` carried seven. There is now exactly one
> constitution — the seeded project's own `CLAUDE.md`, written in Step 5 — and one
> philosophy, `PHILOSOPHY.md`. Do not reintroduce a universal-principles file.

`PHILOSOPHY.md` is **required, not optional**: Step 5's principles block cites its
*Growth has a brake* section by name. A seeded project whose constitution points at a
missing file is precisely the dangling-pointer defect ADR-0036 exists to end, so this
step **fails loudly** instead of continuing.

```bash
TARGET="$ARGUMENTS"

# Prefer the developer's personal copy (PHILOSOPHY.md carries their values and transfers
# when the human is the same), but ONLY if it is current enough to satisfy the citation.
# Otherwise fall back to this template's copy, which is the source of truth.
if grep -q "Growth has a brake" ~/.claude/shared-memory/PHILOSOPHY.md 2>/dev/null; then
  cp ~/.claude/shared-memory/PHILOSOPHY.md "$TARGET/PHILOSOPHY.md"
else
  cp ./PHILOSOPHY.md "$TARGET/PHILOSOPHY.md"
fi

# Hard gate: the citation target must exist and must contain the cited section.
grep -q "Growth has a brake" "$TARGET/PHILOSOPHY.md" \
  || { echo "FATAL: seeded PHILOSOPHY.md lacks the section CLAUDE.md will cite"; exit 1; }

# Mechanical guard, not a note to the reader: a retired FRAMEWORK.md may still be sitting
# in shared-memory on this machine (Principle #2 - enforced by the script, not by prose).
if [ -f ~/.claude/shared-memory/FRAMEWORK.md ]; then
  echo "NOTE: a retired FRAMEWORK.md exists in shared-memory (ADR-0036). It is NOT being copied."
fi
[ ! -f "$TARGET/FRAMEWORK.md" ] \
  || { echo "FATAL: FRAMEWORK.md was seeded into the target; it is retired (ADR-0036)"; exit 1; }
```

## Step 2: Scaffold Directory Structure

Create the framework skeleton with empty directories and placeholder files:

```
.claude/
  agents/       — Copy all agent definitions from shared-memory or template
  commands/     — Copy all command definitions
  hooks/        — Copy hook scripts
  rules/        — Copy rule files
  skills/       — Copy skill definitions. REQUIRED, not optional: Step 5's principles
                  block cites `.claude/skills/selecting-review-gates/SKILL.md` as the
                  normative home of the review-plurality floors. Omitting it makes the
                  seeded constitution cite a directory that does not exist (ADR-0036).
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

Adapt the auto-format hook to the project's tech stack — the formatter command depends on the project's language and toolchain.

## Step 4: Initialize Database

```bash
cd "$TARGET" && python scripts/init_db.py
```

This creates `metrics/evaluation.db` with the correct schema for the capture pipeline.

## Step 5: Create Project CLAUDE.md

Generate a project-specific CLAUDE.md that:
1. **Carries the seven non-negotiable principles INLINE** — copied verbatim from this
   template's `CLAUDE.md` § *Non-Negotiable Principles*, including the "Retired, and where
   the value went" note so a reader of an older artifact can re-point a stale citation.
   This replaces the retired `FRAMEWORK.md` delegation (ADR-0036). **Do not** write
   "see FRAMEWORK.md" or otherwise point at a universal-principles file: it no longer
   exists, and a seeded project whose constitution is a dangling pointer has no
   constitution at all. Inline them even though it duplicates the template — one
   authoritative copy per project beats one shared copy that silently drifts, which is
   exactly how the retired `FRAMEWORK.md` came to publish a list of eight against the
   template's seven.

   **Re-point every cross-reference in the block as you copy it.** The template's text
   cites three things that do NOT exist in a fresh seed, and copying them unaltered
   reproduces the exact defect this step forbids. Verified rewrites:

   | Template text | Renders in a seeded project as |
   |---|---|
   | `ADR-0031 Decision 6` | `ADR-0031 Decision 6 **of the upstream framework template**` — the seeded `docs/adr/` is empty by design, so name it as upstream provenance, never as a local document |
   | `PHILOSOPHY.md` § *Growth has a brake* | unchanged — Step 1 guarantees the file and the section, and fails loudly otherwise |
   | `.claude/skills/selecting-review-gates/SKILL.md` | unchanged — Step 2 scaffolds `skills/`, which is why that directory is required rather than optional |

   Any other citation that resolves only in the template must be rewritten the same way
   or dropped. The rule is the one this command already states: **a pointer that names
   something the project does not have is worse than no pointer.**
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
4. `grep -c '^[1-7]\. \*\*' CLAUDE.md` — should be `7`: the seven principles are inline,
   not delegated to a file that no longer exists (ADR-0036)
5. **Every pointer the constitution makes must resolve** — this is the check that would
   have caught the defect ADR-0036 was written about, so do not skip it:
   ```bash
   test -f PHILOSOPHY.md && grep -q "Growth has a brake" PHILOSOPHY.md \
     || echo "FAIL: CLAUDE.md cites PHILOSOPHY.md § Growth has a brake; it is missing"
   test -f .claude/skills/selecting-review-gates/SKILL.md \
     || echo "FAIL: CLAUDE.md cites the review-plurality skill; it was not scaffolded"
   grep -n "ADR-0031" CLAUDE.md | grep -qv "upstream" \
     && echo "FAIL: ADR-0031 cited as a local document, but docs/adr/ is empty by design"
   test ! -f FRAMEWORK.md || echo "FAIL: retired FRAMEWORK.md present (ADR-0036)"
   ```
   Any `FAIL:` line means the seeded project's constitution points at something it does
   not have. Fix it before handing the project over.
6. `test -f CLAUDE.md` — project-specific config present
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
2. Read your CLAUDE.md — it carries the seven non-negotiable principles inline, and
   PHILOSOPHY.md for the *why* beneath them
3. Read the heritage collection if it exists (`~/.claude/shared-memory/heritage/HERITAGE.md`)
4. Read universal-warnings.md for lessons from prior projects
5. Run `/review` on your first code change to verify the pipeline works
6. Your first `/retro` should happen within 2 weeks of starting
