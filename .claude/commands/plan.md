---
description: "Sprint/feature planning with spec-driven development. Produces a structured spec, gets specialist review, then developer approval before implementation begins."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[feature or goal description]"
---

# Spec-Driven Feature Planning

You are acting as the Facilitator. Every significant change begins with an executable specification.

## Step 1: Understand Intent

Read the developer's feature description. Ask clarifying questions if needed:
- What problem does this solve?
- Who is the user/consumer?
- What constraints apply?
- What does success look like?

## Step 2: Produce Structured Spec

Write a spec document with:

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

## Step 3: Specialist Review of Spec

Dispatch relevant specialists to review the spec (not code — the spec itself):
- architecture-consultant: Are the boundaries correct? Does this align with ADRs?
- security-specialist: Are there security implications not addressed?
- qa-specialist: Are the acceptance criteria testable?

Capture their feedback.

## Step 4: Revise and Present

Incorporate specialist feedback into the spec. Present the final spec to the developer for approval.

## Step 5: Developer Approval

Wait for explicit developer approval of the spec before proceeding to implementation.

## Step 6: Save Spec

Save the approved spec to `docs/sprints/SPEC-YYYYMMDD-HHMMSS-slug.md`.

Tell the developer they can now use `/build_module` to implement against this spec.
