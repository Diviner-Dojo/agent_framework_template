# Micro-Fix Protocol

> Prevents over-engineering of cosmetic changes. Ensures small fixes stay small.

## What Is a Micro-Fix

A change that modifies only the **presentation** of existing behavior, not the behavior itself:
- Icon, text, or label changes
- Color, spacing, or visibility adjustments
- Menu item reordering
- CSS/style-only changes
- Static string corrections

## What Is NOT a Micro-Fix

Any change that could alter **program behavior**, even subtly:
- Platform API calls, lifecycle callbacks
- Data pipelines or database schemas
- Cross-component communication
- State management changes
- Network requests or external integrations
- Configuration that affects runtime behavior

## Sizing Heuristic

Ask: **"Will changing this one thing change behavior?"**

- If **no** → micro-fix. Make the change, run the linter, verify visually, done.
- If **yes** or **maybe** → not a micro-fix. Use the standard workflow (`/plan` if multi-file, `/build_module` if new module).

## Micro-Fix Workflow

1. Make the change (single file, single concern)
2. Run linter (`ruff check` / `ruff format`)
3. Verify the result (visually or via test)
4. Done — no `/plan`, no `/build_module` needed

Micro-fixes are **NOT exempt** from `/review` or the quality gate when committing. They only skip the planning and build phases.

## Two-Strike Escalation Rule

If a micro-fix doesn't produce the expected result after **two attempts**, STOP coding and switch to diagnosis:

1. Add logging/debug output to understand the current state
2. Read the relevant code to understand why the change isn't working
3. If the root cause is not cosmetic, escalate to the standard workflow

**Rationale**: If a "simple" change fails twice, it's not simple. Continuing to guess wastes time and risks introducing bugs.
