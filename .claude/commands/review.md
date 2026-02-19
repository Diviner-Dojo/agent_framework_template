---
description: "Run a multi-agent code review with specialist panel. Assesses risk, assembles the right team, captures all findings, and produces a structured review report."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[file, directory, or description of changes to review]"
---

# Multi-Agent Code Review

You are acting as the Facilitator. Run the following workflow step by step.

## Step 1: Read the Code

Read the files or directory specified by the user. Understand what the code does, what changed (if reviewing a diff), and what risks are present.

## Step 2: Risk Assessment

Assess the risk level of the changes:
- **Low**: Config changes, documentation, simple bug fixes, formatting
- **Medium**: New features, refactoring, test changes, dependency updates
- **High**: Security-related code, architecture changes, database schema, API contracts
- **Critical**: Authentication/authorization, payment processing, data migration, infrastructure

## Step 3: Create Discussion

```
python scripts/create_discussion.py "<slug>" --risk <level> --mode <mode>
```

Select collaboration mode based on risk:
- Low → ensemble
- Medium → structured-dialogue
- High → structured-dialogue or dialectic
- Critical → dialectic

## Step 4: Assemble Specialist Team

Select specialists based on what's being reviewed:
- **Always**: qa-specialist (every code review)
- **API/endpoint changes**: security-specialist, performance-analyst
- **Database changes**: performance-analyst, security-specialist
- **Architecture/module boundaries**: architecture-consultant
- **New modules or significant features**: architecture-consultant, docs-knowledge
- **High/Critical risk**: independent-perspective
- **Security-related**: security-specialist (adversarial mode)

## Step 5: Dispatch Specialists

For each specialist, use the Task tool with the code content and review context:

```
Task(subagent_type="<agent-name>", prompt="Code Review: <discussion_id>\nRisk Level: <level>\n\nReview the following code from your specialist perspective:\n\n<code content>\n\nProvide your structured analysis following your output format. Include confidence score.")
```

Run independent specialists in parallel.

## Step 6: Capture Events

For each specialist's response:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<findings>" --confidence <score> --tags "<tags>"
```

For structured-dialogue mode, run a second round where specialists can respond to each other. Capture those as critiques with --reply-to.

## Step 7: Synthesize Review Report

Write the synthesis event:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "<synthesis>" --confidence <score>
```

Create the review report following `docs/templates/review-report-template.md` and save it to:
```
docs/reviews/REV-YYYYMMDD-HHMMSS.md
```

## Step 8: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

## Step 9: Present to Developer

Present:
1. **Verdict**: approve / approve-with-changes / request-changes / reject
2. **Required changes** (blocking): Must be addressed before merge
3. **Recommended improvements** (non-blocking): Should be addressed but don't block
4. **Strengths**: What the code does well
5. **Education gate**: Whether a walkthrough/quiz is needed and at what Bloom's level

## Step 10: Education Gate (if needed)

For medium-risk and above, recommend the developer run:
- `/walkthrough <files>` for guided code reading
- `/quiz <files>` for comprehension assessment

Record the education gate recommendation in the review report.
