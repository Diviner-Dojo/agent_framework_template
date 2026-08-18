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
2. **NEVER skip the linter**: `ruff check` and `ruff format` MUST run and pass before triggering review.
3. **NEVER declare completion with failing tests**: If tests fail, fix the implementation and re-run. Do NOT move to the review step with failing tests.
4. **ALWAYS follow the spec**: Implementation must satisfy all acceptance criteria in the spec. If the spec is ambiguous, ask the developer — do not guess.
5. **ALWAYS recommend the education gate**: Every build MUST end with an education gate recommendation.
6. **ALWAYS create a discussion at build start**: The build discussion captures all checkpoint events and specialist deliberation. No build runs without a discussion.
7. **ALWAYS close the discussion at build end**: Even if the build fails or is abandoned. Unclosed discussions corrupt the capture stack.
8. **NEVER exceed 2 checkpoint iterations per task**: After Round 2, capture the unresolved concern and continue. The build is not blocked by specialist disagreement.
9. **NEVER carry a rejected option only in your head**: when a task made you choose between two implementable options, the losing option is recorded in Step 3a.5 *before* you evaluate the checkpoint. Not at the end of the build, not in the summary. `/review` re-reads these records against the diff and can fail them (`scripts/verify_paths_not_taken.py`), so an unrecorded choice is a gap the reviewer sees and a false record is a finding.

## Pre-Flight Checks

Before starting the build, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for d in ['src', 'tests']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
for rule in ['.claude/rules/coding_standards.md', '.claude/rules/security_baseline.md', '.claude/rules/testing_requirements.md', '.claude/skills/running-build-checkpoints/SKILL.md']:
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

**Confidence check (CLAUDE.md Workflow Sequencing gate):** before generating code, confirm each task's intent and scope is ~95% clear from the spec. For any task with material ambiguity, list the assumptions and ask the developer (in-conversation `AskUserQuestion`, or the `notifying-the-developer` skill if AFK) rather than guessing. Micro-fix-sized tasks are exempt; the developer may explicitly override to accept the risk.

## Step 2: Create Build Discussion

Create a discussion to capture all checkpoint events:

```bash
python scripts/create_discussion.py "build-<module-slug>" --risk medium --mode structured-dialogue
```

Store the returned `discussion_id` — all subsequent capture calls reference it.

Capture the context-brief as the first event (turn_id=1), before the build plan.

Summarise the developer's request from the current session. Populate all four fields;
write "(none stated)" if a field was not addressed. Strip business context (deadlines,
client names, regulatory pressures) — record structural intent only.

```bash
# INVARIANT: This must be the first write_event.py call in this workflow.
# turn_id=1 is required for extraction pipeline integrity. Any reordering
# silently breaks context-brief capture.
python scripts/write_event.py "<discussion_id>" "facilitator" "evidence" \
  "## Request Context
- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [which spec is being implemented; module name and location]
- **Developer-stated motivation**: [why this module is being built, if stated; or 'none stated']
- **Explicit constraints**: [developer-stated constraints agents should respect; or 'none stated']" \
  --tags "context-brief"
# If invoked without prior conversational context (cold start), populate all four
# fields as "(none stated)" and add tag "context-brief-cold-start" so uninstrumented
# invocations are queryable: --tags "context-brief,context-brief-cold-start"
```

Capture the build plan as the second event:
```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "proposal" "Build plan: <N tasks from spec>" --tags "build-plan"
```

## Step 2.5: Pre-Build Enrichment

Before executing the first task, search for existing solutions relevant to the build's domain per the `searching-prior-art` skill:

1. **Grep the regression ledger** for the build's domain: `grep -i "<domain>" memory/bugs/regression-ledger.md` — check both the bug table and the `## Known-Broken Approaches` section.
2. **Read solution paths** in `memory/projects/_self.md` for the relevant taxonomy domain(s). If any solution paths match the build's scope, inject them into checkpoint specialist context as `## Known Solution Paths` so specialists are aware of prior art.
3. **Search `docs/adr/`** for relevant architectural decisions that constrain this build.
4. **Search `memory/patterns/`** for promoted patterns in this domain.

This is a context-assembly step, not a checkpoint. It runs once at build start, not per-task. If no relevant prior art exists, proceed without injecting — zero matches is the normal case for novel domains.

If a known-broken approach is found, explicitly note it and explain the alternative.

## Step 3: Execute Tasks (Loop)

For each task in the spec, execute Steps 3a, 3a.5, and 3b:

### Step 3a: Generate Code

Based on the current task:
1. Create or modify source files in `src/`
2. Follow the coding standards in `.claude/rules/coding_standards.md`
3. Follow the security baseline in `.claude/rules/security_baseline.md`
4. Include type annotations on all public functions
5. Include Google-style docstrings
6. Follow existing patterns in the codebase

### Step 3a.5: Record the Path Not Taken (while deciding, not after)

**Fire this step the moment you pick one implementable option over another** — while the
rejected option is still in front of you, before you move on and before Step 3b. It is not a
closing summary step and it must never be batched to the end of the build.

Why the timing is the whole mechanism: an "alternatives considered" section written after the
work is a **reconstruction**. By then the rejected option is remembered through the lens of the
one that shipped, so it comes back tidier, weaker, and more obviously wrong than it was — which
is precisely the story that reads well and teaches nothing. The record is only worth reading if
it was written when the choice was still live.

**Record when any of these is true** (they mirror the Step 3b trigger categories, because the
same forks that need a second opinion are the ones worth recording):

- you chose one pattern, abstraction, or library over another that would also have worked
- you chose a schema shape, an interface, or an error-handling posture over a named other one
- you chose to change a structure rather than patch it again — or the reverse
- you rejected an approach the pre-build enrichment (Step 2.5) surfaced as prior art
- a specialist's REVISE in Step 3b made you change approach: the approach you abandoned is a
  path not taken and gets its own record

**Do not record** a choice with no live alternative (naming a variable, following the only
pattern the codebase has, doing exactly what the spec dictates). A record per trivial choice
buries the real ones.

Write one event per decision, tagged `path-not-taken`. The `decision` intent is used because it
is the only one of the seven that means *a choice was made*, and — measured — `decision` events
are not scanned by `scripts/extract_findings.py`, so a record adds no false finding to the
review's counts.

```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "decision" \
  "## Path Not Taken
- **Decision**: [what was being decided, in one line]
- **Chosen**: [what you actually implemented]
- **Rejected**: [the specific other option you could have implemented]
- **Why rejected**: [the reason, at the time, in your own words]
- **Files**: [repo-relative paths this decision lands in, comma-separated]
- **Falsifier**: [a literal string that WOULD appear in the added lines if the rejected option had shipped]" \
  --tags "path-not-taken,task-<N>"
```

**The `Falsifier` field is what makes the record checkable, and it is the one people get wrong.**
It is not a restatement of the rejection. It is a concrete token — a symbol name, a flag, an
import, a call — that a checker can search the diff's added lines for. If the rejected option had
shipped, that string would be there; because it did not, it is not.

- Good: `COMMAND_TEXT_RE`, `subprocess.run(`, `--patch-guard`, `class RetryMiddleware`
- Rejected by the checker: `a different approach`, `n/a`, `the alternative`, anything under 4
  characters. These name nothing a diff can be searched for, and
  `scripts/verify_paths_not_taken.py` reports them as `UNFALSIFIABLE` rather than letting them
  pass as records.

If you genuinely cannot name a falsifier, that is information: the "alternative" you are about
to write down may not have been a real option. Say so in `Why rejected` instead of inventing a
token — a fabricated falsifier is worse than an absent record, because it survives the
mechanical check and gets taught to the developer as fact.

### Step 3b: Checkpoint Evaluation

After generating code for the task, evaluate whether it triggers a checkpoint per the `running-build-checkpoints` skill:

**Check trigger categories:**
- New module (2+ new files under `src/`)
- Architecture choice (pattern selection, abstraction decisions)
- Database schema (SQLAlchemy models, Alembic migrations)
- Security-relevant code (auth, encryption, tokens, validation)
- API routes (FastAPI endpoints, middleware, dependency injection)
- External API integration (HTTP clients, third-party services)

**Check exemptions:**
- Scaffolding, dependency config, pure test writing, theme/style-only, docs, final verification

**If checkpoint triggers:**

1. Select 2 specialists from the trigger table in the rule file.
2. Dispatch both specialists in parallel:
   ```
   Task(subagent_type="<specialist>", model="sonnet", prompt="Build Checkpoint Review: <discussion_id>\nTask: <N> - <title>\nTrigger: <category>\n\n## Developer Context\n[Paste the four-field content from the context-brief event written in Step 2]\n\nReview this code from your specialist perspective. This is a mid-build checkpoint, not a full review.\n\nFocus on:\n- Whether the implementation approach is sound\n- Whether it aligns with existing ADRs and patterns\n- Any risks that would be expensive to fix later\n\n<code content or file paths>\n\nRespond with APPROVE or REVISE (under 200 words).")
   ```
3. Capture each specialist's response:
   ```bash
   python scripts/write_event.py "<discussion_id>" "<specialist>" "critique" "<response>" --tags "checkpoint,task-<N>" --confidence <score>
   ```
4. If both APPROVE -> continue to next task.
5. If any REVISE -> implement the requested changes, then re-dispatch **only** the specialist(s) who said REVISE for Round 2.
6. After Round 2, if still REVISE -> capture with `--risk-flags "unresolved-checkpoint"` and continue.

**If checkpoint does NOT trigger:**

Capture a brief bypass note:
```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "decision" "Task <N>: checkpoint bypass — <reason>" --tags "checkpoint-bypass,task-<N>"
```

Continue to the next task.

## Step 4: Generate Tests

After all tasks are complete, create tests in `tests/` that cover:
1. All acceptance criteria from the spec
2. Edge cases (empty inputs, boundary values, error states)
3. At least one integration-level test per major component
4. Follow testing requirements in `.claude/rules/testing_requirements.md`

## Step 5: Run Tests and Linter

```bash
pytest tests/ -v --tb=short
```

If tests fail, fix the implementation and re-run until all pass.

```bash
ruff check src/ tests/
ruff format --check src/ tests/
```

Fix any issues found.

## Step 6: Run Quality Gate

```bash
python scripts/quality_gate.py
```

All checks must pass before proceeding.

## Step 6.5: Self-Check the Path-Not-Taken Records

Run the same check `/review` will run, before handing the change over. Fixing a record now costs
a minute; a `CONTRADICTED` record found at review time is a finding against the build.

```bash
# FIRST — capture the tree RIGHT NOW, before `-N` touches it. This is what makes the reversal at
# the end of this block SCOPED, and it cannot be recovered afterwards: once `-N` has run, the
# untracked files are no longer untracked and this command reports none of them.
# Keep TWO sets of lines, because `--all` reaches both and the reversal must reach both back:
#   `??` — untracked paths, which `-N` REGISTERS; and
#   ` D` — tracked files deleted in the worktree, which `-N` promotes to STAGED DELETIONS.
# Measured on a throwaway repo: with ` D sibling.txt` present, after `-N` the index carried
# `0  1  sibling.txt`, a ??-only reset left it there, and a plain `git commit -m` then SUCCEEDED
# and shipped that deletion ("1 file changed, 1 deletion(-)"). The `commit -a` warning below does
# not cover this: no `-a` is involved.
git status --porcelain --untracked-files=all

# MANDATORY first line. `git diff` NEVER shows untracked files, and a build whose trigger is
# "2+ new files under src/" produces exactly those. Measured on a throwaway repo: with a 40-line
# untracked src/new_module.py, `git diff HEAD` is 0 bytes; after --intent-to-add the same diff
# reports "1 file changed, 40 insertions(+)". (A byte size used to be quoted here instead. It was
# dropped because it is not reproducible from the shape this sentence names: across path x
# trailing-newline x LF/CRLF the diff runs 448-527 bytes. The insertion count is 40 in all eight.)
# Skip this line and every record naming a NEW file is falsely reported PHANTOM — a blocking
# failure against a truthful record, which is the one outcome that teaches builders to stop
# recording.
#
# SCOPE, and it is narrow — but narrow is not the same as safe. For the UNTRACKED paths `-N`
# registers, it stages no content: measured, in a tree whose only change is the new file,
# `git diff --cached --numstat` is EMPTY afterwards and `git commit -m` refuses with "no changes
# added to commit". That EMPTY result is conditional on the tree, not a property of `-N` — if any
# tracked file was deleted in the worktree, `--all` stages that deletion and `commit -m` will
# happily commit it (see the capture step above). But `git
# commit -am` DOES commit the file in full ("1 file changed, 40 insertions(+)"), so never follow
# this with `commit -a`. It also does NOT replace explicit staging: the `committing-changes` skill
# Step 1.8 (Required) says never `git add -A` / `git add .` with an entangled tree, and that still
# governs the commit. Measured on this repo, `git add --dry-run --intent-to-add --all` named 14
# paths including .claude/settings.json and two other slices' files — none of which belong in your
# commit. This line is for the DIFF you hand the checker, nothing else.
git add --intent-to-add --all

git diff HEAD | python scripts/verify_paths_not_taken.py --discussion "<discussion_id>" --diff -

# THE REVERSAL, once the checker has its diff. `-N` is not free: it leaves every path above
# registered in the index, where it changes what LATER commands see — `git stash` will carry them,
# and the `git add <path>` you were going to run for an explicit, scoped commit now sits in a tree
# where the untracked set has been quietly redefined. Un-register exactly the paths the first
# command printed, and nothing else.
#
# SCOPED, and the scoping is the whole instruction. `git reset -q` with no pathspec resets the
# WHOLE index: measured on a throwaway repo with one file deliberately staged before `-N`, the
# bare form left `git diff --cached --numstat` EMPTY — it silently unstaged work that had nothing
# to do with this check. With the pathspec, the same repo still reported the sibling's staged
# change afterwards. Never the bare form, and never `git reset -q -- .`, which is the bare form
# wearing a pathspec.
#
# Pass BOTH sets the capture step told you to keep — the `??` paths AND the ` D` paths. A ??-only
# reset is the incomplete reversal measured above, and it fails in the silent direction.
git reset -q -- <the ?? paths AND the ` D` paths the first command printed>

# VERIFY THE REVERSAL rather than assuming it. This must match what the capture step saw before
# `-N` ran; anything extra is something `-N` staged and the reset did not reach, and it is about
# to ride along on your next commit.
git diff --cached --numstat
```

Read the exit code — the four values mean different things and must not be collapsed:

- **0** — `MECHANICALLY-CLEAR`: no record was structurally broken, none was refuted **in code**,
  and every high-churn file is spoken for. Continue. **Read the word literally.** The script does
  not print `VERIFIED` and cannot: all it did was fail to find your falsifier string in the added
  lines, so a record you invented — a straw-man alternative plus a token that was never going to
  appear — passes this exactly as a true one does. Exit 0 is not evidence your record is true; it
  is evidence nothing here refuted it. The run prints a `caveat` saying so beside the verdict.
- **1** — a record is `CONTRADICTED` (the diff added the falsifier, so the "rejected" approach is
  what shipped), `PHANTOM` (it names files this change never touched), or `UNFALSIFIABLE`.
  **First check the checker's input, then fix the record.** Two input mistakes produce a failure
  against work that is entirely honest, and both are stated in the failure text when they apply:
  a diff taken without the `--intent-to-add` line above (new files invisible → false `PHANTOM`,
  and the message says so when the path exists on disk), and a path typo. Once the input is
  right, the record is what changes — not the checker: rewrite it to say what actually happened.
  A record that no longer matches the code is a record that was written from memory. Never edit
  `scripts/verify_paths_not_taken.py` to make your own record pass; that is the generator
  rewriting its own evaluator.
- **`CONTRADICTED-IN-PROSE`** — advisory, and does **not** change the exit code. The falsifier
  turned up in a comment or a markdown line rather than in code. Writing a comment that explains
  why you rejected an approach is good practice and must not refute the record of it, so the
  checker reports the coincidence and leaves the judgement to a reader. Read the line; if the
  approach really did ship, fix the record.
- **2** — coverage gap: files changed with real churn that no record names. Ask yourself whether
  each was a mechanical change or a choice. If it was a choice, go back and write the record you
  skipped. If it was mechanical, leave it — exit 2 is advisory here and `/review` will see it too.
  Bookkeeping paths are skipped before this check runs (`DEFAULT_EXCLUDES` in the script:
  `discussions/*`, `docs/reviews/*`, `metrics/*`, `BUILD_STATUS.md`) and the run prints how many
  it skipped. `discussions/*` is the one to understand: Layer 1 grows *because* you wrote records,
  so without it writing more records made your own `events.jsonl` cross the threshold and be
  reported unspoken-for. `tests/` is deliberately NOT skipped — a test-design choice is a choice.
- **3** — instrument failure. HALT per behavioural rule 2. Do NOT read it as "no problems".

This self-check is not the gate. `/review` re-runs it independently on the review's own diff
range, because a builder checking its own work is the generator evaluating itself.

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

### Step 7b: Request Agent Reflections

After recording yield, request reflections from each checkpoint specialist who participated (non-blocking). For each specialist who gave a REVISE verdict:

Dispatch a reflection request (sonnet tier, 150-word cap):
```
Task(subagent_type="<agent-name>", model="sonnet", prompt="Reflection Request: <discussion_id>\n\nYou reviewed a build checkpoint. Reflect briefly (under 150 words):\n1. What did you miss?\n2. What improvement rule would you propose?\n3. Was your confidence appropriate?\n\nFormat:\n## What I Missed\n<text>\n## Candidate Improvement Rule\n<text>\n## Confidence Calibration\nDelta: +/-Z.Z")
```

Capture via `write_event.py` with intent=reflection, tags=reflection. If a specialist fails to produce a reflection, log the gap and continue.

Seal the discussion:
```bash
python scripts/close_discussion.py "<discussion_id>"
```

Note: `close_discussion.py` automatically extracts findings, surfaces promotion candidates, and computes agent effectiveness.

## Step 7c: Update Spec Lifecycle

If this build was driven by a spec (SPEC-*.md), update the spec's status to reflect completion:

```bash
python -c "
import pathlib, re
from datetime import datetime, timezone
spec_path = pathlib.Path('<spec_file_path>')
if spec_path.exists():
    text = spec_path.read_text(encoding='utf-8')
    text = re.sub(r'^status:\s*.+$', 'status: complete', text, count=1, flags=re.MULTILINE)
    # Add completion metadata if not present
    if 'completed_at:' not in text:
        text = re.sub(r'^(status: complete)$', r'\1\ncompleted_at: ' + datetime.now(timezone.utc).strftime('%Y-%m-%d'), text, count=1, flags=re.MULTILINE)
    # Note: completed_commit should be added AFTER committing (when SHA is available).
    # Run this step post-merge to solve the timing problem.
    spec_path.write_text(text, encoding='utf-8')
    print(f'Spec updated to complete: {spec_path.name}')

    # If spec has intake_ids, notify developer to update linked items
    intake_match = re.search(r'^intake_ids:\s*\[(.+)\]', text, re.MULTILINE)
    if intake_match:
        ids = [i.strip() for i in intake_match.group(1).split(',')]
        print(f'Linked intake items to update: {ids}')
else:
    print('No spec path provided or file not found — skipping lifecycle update.')
"
```

If the spec references `intake_ids`, notify the developer that the corresponding intake items should be updated.

## Step 8: Present Build Summary

Present to the developer:

1. **Tasks completed**: List of all tasks with status
2. **Checkpoints fired**: Which tasks triggered reviews, which specialists responded, outcomes
3. **Unresolved concerns**: Any tasks where specialists still had concerns after Round 2 (risk_flags: unresolved-checkpoint)
4. **Paths not taken**: Every `path-not-taken` record written in Step 3a.5 — decision, chosen,
   rejected — plus the Step 6.5 exit code verbatim, **and the build `discussion_id` stated
   explicitly on its own line**. The id is the only handle that reaches these records: `/review`
   Step 6.4 passes it to `scripts/verify_paths_not_taken.py --discussion`, and a review that is
   not given it falls back to writing `NOT RUN`, which verifies nothing. (`/review` can also
   recover it with `--list-sources`, but recovery is not a substitute for handing it over — the
   listing cannot tell which discussion belongs to this change.) `/plan` states its spec-time id
   the same way at its Step 7; if this build came from a spec, repeat that id here too, because
   both sets of records are claims about the one diff. If zero records were written on a build
   with more than one task, say so explicitly and say why; "no alternatives arose" is a claim,
   and it is the claim the reviewer will test first.
5. **Test results**: Pass count, coverage
6. **Quality gate**: Pass/fail status
7. **Next step**: Recommend `/review <files>` for a full multi-agent review before committing
8. **Education gate**: Recommend `/walkthrough` and `/quiz` on the new module
