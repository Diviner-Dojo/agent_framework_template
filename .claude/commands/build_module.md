---
description: "Build a module from a spec with integrated quality gates and mid-build checkpoint reviews. Generates code task-by-task, dispatches specialist checkpoints, runs tests, triggers review, and activates education gate."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[spec file path or module description]"
---

# Module Construction with Checkpoint Reviews

You are acting as the Facilitator. Build code against an approved spec with integrated quality controls and mid-build specialist checkpoints.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip tests**: Every module MUST have tests before declaring completion. No untested code passes this gate.
2. **NEVER skip the linter**: `dart analyze` and `dart format` MUST run and pass before triggering review.
3. **NEVER declare completion with failing tests**: If tests fail, fix the implementation and re-run. Do NOT move to the review step with failing tests.
4. **ALWAYS follow the spec**: Implementation must satisfy all acceptance criteria in the spec. If the spec is ambiguous, ask the developer — do not guess.
5. **ALWAYS recommend the education gate**: Every build MUST end with an education gate recommendation.
6. **ALWAYS create a discussion at build start**: The build discussion captures all checkpoint events and specialist deliberation. No build runs without a discussion.
7. **ALWAYS close the discussion at build end**: Even if the build fails or is abandoned. Unclosed discussions corrupt the capture stack.
8. **NEVER exceed 2 checkpoint iterations per task**: After Round 2, capture the unresolved concern and continue. The build is not blocked by specialist disagreement.

## Pre-Flight Checks

Before starting the build, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for d in ['lib', 'test']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
for rule in ['.claude/rules/coding_standards.md', '.claude/rules/security_baseline.md', '.claude/rules/testing_requirements.md', '.claude/rules/build_review_protocol.md']:
    if not pathlib.Path(rule).exists():
        errors.append(f'Missing required rule file: {rule}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Step 1: Read the Spec

If a spec file path is provided, read it. If not, check `docs/sprints/` for the most recent approved spec, or ask the developer what to build.

Parse the spec into a numbered task list. Each task becomes a build unit that may trigger a checkpoint.

## Step 2: Create Build Discussion

Create a discussion to capture all checkpoint events:

```bash
python scripts/create_discussion.py "build-<module-slug>" --risk medium --mode structured-dialogue
```

Store the returned `discussion_id` — all subsequent capture calls reference it.

Capture the build plan as the first event:
```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "proposal" "Build plan: <N tasks from spec>" --tags "build-plan"
```

## Step 3: Execute Tasks (Loop)

For each task in the spec, execute Steps 3a and 3b:

### Step 3a: Generate Code

Based on the current task:
1. Create or modify source files in `lib/`
2. Follow the coding standards in `.claude/rules/coding_standards.md`
3. Follow the security baseline in `.claude/rules/security_baseline.md`
4. Use Dart's type system with sound null safety
5. Follow existing patterns in the codebase (Riverpod, drift, etc.)

### Step 3b: Checkpoint Evaluation

After generating code for the task, evaluate whether it triggers a checkpoint per `.claude/rules/build_review_protocol.md`:

**Check trigger categories:**
- New module (2+ new files under `lib/`)
- Architecture choice (pattern selection, abstraction decisions)
- Database schema (drift tables, migrations, DAOs)
- Security-relevant code (auth, encryption, tokens, validation)
- State management (Riverpod providers, state notifiers)
- External API integration (dio, Supabase, Edge Functions)

**Check exemptions:**
- Scaffolding, dependency config, pure test writing, theme/style-only, docs, final verification

**If checkpoint triggers:**

1. Select 2 specialists from the trigger table in the rule file.
2. Dispatch both specialists in parallel:
   ```
   Task(subagent_type="<specialist>", model="sonnet", prompt="Build Checkpoint Review: <discussion_id>\nTask: <N> - <title>\nTrigger: <category>\n\nReview this code from your specialist perspective. This is a mid-build checkpoint, not a full review.\n\nFocus on:\n- Whether the implementation approach is sound\n- Whether it aligns with existing ADRs and patterns\n- Any risks that would be expensive to fix later\n\n<code content or file paths>\n\nRespond with APPROVE or REVISE (under 200 words).")
   ```
3. Capture each specialist's response:
   ```bash
   python scripts/write_event.py "<discussion_id>" "<specialist>" "critique" "<response>" --tags "checkpoint,task-<N>" --confidence <score>
   ```
4. If both APPROVE → continue to next task.
5. If any REVISE → implement the requested changes, then re-dispatch **only** the specialist(s) who said REVISE for Round 2.
6. After Round 2, if still REVISE → capture with `--risk-flags "unresolved-checkpoint"` and continue.

**If checkpoint does NOT trigger:**

Capture a brief bypass note:
```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "decision" "Task <N>: checkpoint bypass — <reason>" --tags "checkpoint-bypass,task-<N>"
```

Continue to the next task.

## Step 4: Generate Tests

After all tasks are complete, create tests in `test/` that cover:
1. All acceptance criteria from the spec
2. Edge cases (empty inputs, boundary values, error states)
3. At least one integration-level test per major component
4. Follow testing requirements in `.claude/rules/testing_requirements.md`

## Step 5: Run Tests and Linter

```bash
flutter test --reporter expanded
```

If tests fail, fix the implementation and re-run until all pass.

```bash
dart analyze lib/ test/
dart format --set-exit-if-changed lib/ test/
```

Fix any issues found.

## Step 6: Run Quality Gate

```bash
python scripts/quality_gate.py
```

All checks must pass before proceeding.

## Step 7: Close Discussion

Capture the build outcome. Count total blocking and advisory findings across all checkpoints:

```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "Build complete: <N tasks>, <M checkpoints fired>, <K unresolved concerns>" --tags "build-summary,blocking:<B>,advisory:<A>"
```

Record yield metrics for each checkpoint that fired during the build:

```bash
python scripts/record_yield.py "<discussion_id>" checkpoint <outcome> --blocking <N> --advisory <M> --turns <turns>
```

Where `<outcome>` is: approve, revise-resolved, or revise-unresolved.

Seal the discussion:
```bash
python scripts/close_discussion.py "<discussion_id>"
```

## Step 8: Present Build Summary

Present to the developer:

1. **Tasks completed**: List of all tasks with status
2. **Checkpoints fired**: Which tasks triggered reviews, which specialists responded, outcomes
3. **Unresolved concerns**: Any tasks where specialists still had concerns after Round 2 (risk_flags: unresolved-checkpoint)
4. **Test results**: Pass count, coverage
5. **Quality gate**: Pass/fail status
6. **Next step**: Recommend `/review <files>` for a full multi-agent review before committing
7. **Education gate**: Recommend `/walkthrough` and `/quiz` on the new module
