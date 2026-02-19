---
description: "Trigger a structured multi-agent discussion on a topic. Creates a discussion, dispatches specialists, captures all reasoning, and produces a synthesis."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[topic to discuss]"
---

# Structured Multi-Agent Discussion

You are acting as the Facilitator. Run the following workflow step by step.

## Step 1: Create Discussion

Run: `python scripts/create_discussion.py "<slug>" --risk <level> --mode <mode>`

Choose the slug from the topic. Assess risk level based on the topic:
- Low: Documentation, tooling, minor config
- Medium: Feature design, refactoring approach, process changes
- High: Architecture decisions, security design, data model changes
- Critical: Auth/authz design, data migration, infrastructure

Choose collaboration mode:
- Ensemble: Simple topic, just need breadth of perspectives
- Structured Dialogue: Default for most topics
- Dialectic: Genuine competing approaches to evaluate

Record the discussion_id from the output.

## Step 2: Assess and Select Specialists

Based on the topic, determine which specialist agents should participate:
- Architecture questions → architecture-consultant
- Security topics → security-specialist
- Quality/testing topics → qa-specialist
- Performance concerns → performance-analyst
- Documentation/knowledge → docs-knowledge
- Complex or high-risk topics → independent-perspective

Always include at least 2 specialists.

## Step 3: Dispatch Specialists

For each selected specialist, use the Task tool:
```
Task(subagent_type="<agent-name>", prompt="Discussion: <discussion_id>\nTopic: <topic>\n\nAnalyze this topic from your specialist perspective. Provide your structured analysis following your output format.")
```

Run independent specialists in parallel where possible.

## Step 4: Capture Events

For each specialist's response, capture it as an event:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<content>" --confidence <score> --tags "<tags>"
```

If the collaboration mode is Structured Dialogue or Dialectic, run a second round where specialists can respond to each other's findings:
```
python scripts/write_event.py "<discussion_id>" "<agent-name>" "critique" "<response>" --reply-to <turn_id> --confidence <score>
```

## Step 5: Synthesize

Write your synthesis as the facilitator:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "<synthesis>" --confidence <score>
```

If a decision was reached:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "decision" "<decision>" --confidence <score>
```

## Step 6: Close Discussion

Run: `python scripts/close_discussion.py "<discussion_id>"`

This generates the transcript, ingests events into SQLite, and seals the discussion.

## Step 7: Present Results

Present to the developer:
1. Summary of the discussion topic
2. Key perspectives from each specialist
3. Points of agreement and disagreement
4. Decision or recommendation reached
5. Confidence level and any caveats
6. Link to the full discussion transcript

If an ADR is warranted, offer to create one using the template at `docs/templates/adr-template.md`.
