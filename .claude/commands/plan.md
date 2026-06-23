---
description: "Sprint/feature planning with spec-driven development. Produces a structured spec, gets specialist review, then developer approval before implementation begins."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[feature or goal description]"
---

# Spec-Driven Feature Planning

You are acting as the Facilitator. Every significant change begins with an executable specification.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: Every specialist turn MUST be recorded via `scripts/write_event.py`. No findings exist unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
3. **NEVER synthesize before all specialists report**: Wait for ALL dispatched specialists to return before writing the synthesis. Premature synthesis misses findings.
4. **ALWAYS close the discussion**: Every planning session MUST end with `scripts/close_discussion.py`, even if abandoned. Unclosed discussions corrupt the capture stack.
5. **Confidence gate before building**: A spec is not approved for `/build_module` until intent and scope are ~95% clear. If material ambiguity remains, list your assumptions explicitly and ask the developer (in-conversation `AskUserQuestion`, or the `notifying-the-developer` skill if AFK) rather than proceeding on a guess — wrong-path implementation costs far more than a clarifying question. The developer may explicitly override to accept the risk. (Implements the CLAUDE.md Workflow Sequencing confidence gate.)

## Pre-Flight Checks

Before starting planning, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for d in ['docs/sprints', 'docs/adr']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
if not pathlib.Path('CLAUDE.md').exists():
    errors.append('Missing project constitution: CLAUDE.md')
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Step 0.5: Spec Budget Check

Before creating a new spec, check the active spec count:

```bash
python -c "
import pathlib, re
specs = list(pathlib.Path('docs/sprints').glob('SPEC-*.md'))
active = 0
for s in specs:
    text = s.read_text(encoding='utf-8')
    status = re.search(r'^status:\s*(.+)$', text, re.MULTILINE)
    spec_type = re.search(r'^type:\s*(.+)$', text, re.MULTILINE)
    if status:
        st = status.group(1).strip().strip('\"')
        tp = spec_type.group(1).strip().strip('\"') if spec_type else 'spec'
        if tp == 'spec' and st in ('draft', 'reviewed', 'approved'):
            active += 1
print(f'Active specs: {active}/5')
if active >= 5:
    print('WARNING: Spec budget reached (5 active). Consider completing or retiring an existing spec before creating a new one.')
"
```

If the budget is reached, inform the developer. They may override, or they may want to create a `type: vision` document instead (visions don't count toward the budget).

## Step 0.7: Determine Type

Ask the developer: is this an **actionable spec** (something to build in the near term) or a **vision document** (an idea to capture for future consideration)?

- `type: spec` — has concrete requirements, acceptance criteria, and affected components. Counts toward the active budget.
- `type: vision` — captures an idea, direction, or aspiration. No acceptance criteria required. Does not count toward the budget, does not appear in "ready to build" pipeline.

## Step 1: Understand Intent

Read the developer's feature description. Ask clarifying questions if needed:
- What problem does this solve?
- Who is the user/consumer?
- What constraints apply?
- What does success look like?

## Step 1.5: Prior Art Lookup

Before drafting the spec, search for existing solution paths relevant to the feature's domain. This surfaces approaches that other projects have tried — both successful and failed — so the spec can build on prior knowledge instead of rediscovering dead ends.

1. **Search `memory/projects/`** for solution paths related to the feature's domain — look for `## Solution Paths` sections in project profiles
2. **Search `memory/bugs/regression-ledger.md`** Known-Broken Approaches for approaches to avoid
3. **Search `docs/adr/`** for relevant architectural decisions that constrain this feature
4. **If no matches in the first searches**, fall through to broader pattern search in `memory/patterns/`

This step is non-blocking — if no relevant solution paths exist, proceed to Step 2. The goal is to inform the spec, not to gate it. Include relevant prior art in the spec's Context section — what approaches have been tried, what worked, what failed. If a known-broken approach exists, add it to the Constraints section.

## Step 2: Produce Structured Spec

Write a spec document to `docs/sprints/SPEC-YYYYMMDD-HHMMSS-slug.md` with status `draft`:

```markdown
---
spec_id: SPEC-YYYYMMDD-HHMMSS
title: "[Feature title]"
type: spec  # or "vision" for idea capture
status: draft
risk_level: [low/medium/high/critical]
intake_ids: []  # optional: link to intake items driving this spec
completed_at:   # YYYY-MM-DD — set when status changes to "complete"
completed_commit:  # short SHA — merge commit where feature entered mainline
---

## Goal
[What this feature accomplishes]

## Context
[Why this is needed now, what forces are at play]

## Requirements
- [Functional requirement 1]
- [Functional requirement 2]

## Constraints
- [Technical constraints]
- [Business constraints]

## Acceptance Criteria
- [ ] [Testable criterion 1]
- [ ] [Testable criterion 2]

## Risk Assessment
- [Identified risks and mitigations]

## Affected Components
- [Which modules/files will be changed]

## Dependencies
- [What this depends on]
- [What depends on this]
```

## Step 3: Create Discussion

Create a discussion to capture the specialist review:

```
python scripts/create_discussion.py "<spec-slug>-spec-review" --risk <level> --mode structured-dialogue
```

Store the returned discussion ID — it is needed for all subsequent capture steps.

## Step 3.5: Write Context-Brief (Before Specialist Dispatch)

Immediately after creating the discussion, capture a context-brief event. This must be
written before any specialist is dispatched — it produces `turn_id=1` in the discussion
and injects developer framing into specialist prompts.

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
- **Files/scope**: [what spec or feature is being planned]
- **Developer-stated motivation**: [why this feature is needed, if stated; or 'none stated']
- **Explicit constraints**: [developer-stated constraints agents should respect; or 'none stated']" \
  --tags "context-brief"
# If invoked without prior conversational context (cold start), populate all four
# fields as "(none stated)" and add tag "context-brief-cold-start" so uninstrumented
# invocations are queryable: --tags "context-brief,context-brief-cold-start"
```

## Step 4: Dispatch Specialists and Capture

Dispatch relevant specialists to review the spec (not code — the spec itself):
- architecture-consultant: Are the boundaries correct? Does this align with ADRs?
- security-specialist: Are there security implications not addressed?
- qa-specialist: Are the acceptance criteria testable and the test strategy sufficient?

For each specialist, use the Task tool:
```
Task(subagent_type="<agent-name>", prompt="Spec Review: <discussion_id>\nRisk Level: <level>\n\n## Developer Context\n[Paste the four-field content from the context-brief event written in Step 3.5]\n\nReview the following spec from your specialist perspective:\n\n<spec content>\n\nProvide structured analysis with findings (blocking vs advisory) and a verdict.")
```

Run independent specialists in parallel.

**Capture each specialist's response immediately**:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "critique" "<findings>" --confidence <score> --tags "<tags>"
```

## Step 5: Synthesize and Revise

Write the facilitator synthesis event. **The synthesis content must begin with a `## Request Context` section** before the findings summary. Populate all four fields from the developer's request and session context.

```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" \
  "## Request Context
- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [what spec or feature is being planned]
- **Developer-stated motivation**: [why this feature is needed, if stated]
- **Explicit constraints**: [any developer-stated constraints; or 'none stated']

## Synthesis
<summary of all findings and spec changes made>" --confidence <score>
```

Incorporate specialist feedback into the spec. Update the spec's:
- `status` field to `reviewed`
- Add `reviewed_by` field with list of specialists
- Add `discussion_id` field linking to the capture

## Step 6: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

## Step 7: Present to Developer

Present the final spec to the developer for approval, including:
1. Summary of specialist findings (blocking vs advisory)
2. Changes made to address blocking findings
3. Advisory items noted but deferred
4. Link to the discussion transcript

## Step 8: Developer Approval

Wait for explicit developer approval of the spec before proceeding to implementation.

Tell the developer they can now use `/build_module` to implement against this spec.

## Step 9 (optional): Emit a goal contract for `/goal-loop`

`/plan` is the **upstream** path for a *loop-shaped* feature — one whose acceptance criteria are
verifiable and expected to converge through build → verify → refine (ADR-0026, spec R10). After the
spec is approved, offer to emit a `GOAL-…` goal contract derived from the spec's **Acceptance
Criteria**:

- Translate each verifiable AC into a `success_criteria` entry, mapping its check to a `verify`
  method (a deterministic command / `quality_gate` → `verify_owner: gate`; an independent-checker
  judgment → `llm-judge` + `verify_owner: checker`). Keep ≥1 deterministic anchor and the judge
  fraction under `max_judge_fraction` — an all-judge contract is rejected.
- Set `derived_from: <this SPEC id>` so each criterion traces back to a spec AC.
- Author via the **`authoring-goal-contracts`** skill (it gatekeeps + validates) into
  `loops/contracts/GOAL-…md`, then `python scripts/goal_loop.py loops/contracts/GOAL-….md
  --validate-only`.

**Suggest, never impose** — emit a contract only if the developer wants the loop; a non-loop-shaped
spec (subjective or exploratory ACs) just proceeds to `/build_module`. The loop never pushes or
auto-merges, and still halts at goal-met for `/review` + the required education walkthrough.
