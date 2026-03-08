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

## Step 1: Understand Intent

Read the developer's feature description. Ask clarifying questions if needed:
- What problem does this solve?
- Who is the user/consumer?
- What constraints apply?
- What does success look like?

## Step 2: Produce Structured Spec

Write a spec document to `docs/sprints/SPEC-YYYYMMDD-HHMMSS-slug.md` with status `draft`:

```markdown
---
spec_id: SPEC-YYYYMMDD-HHMMSS
title: "[Feature title]"
status: draft
risk_level: [low/medium/high/critical]
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
