---
name: multi-instance-dispatch
description: Protocol for dispatching one specialist as multiple parallel instances. Use when the facilitator evaluates a specialist's split_request, or to apply independent-perspective's 4 instance types (Independent Analyst, Team Observer, Research Scout, Process Critic). Max 3 instances per agent per review.
---

# Multi-Instance Protocol

## Principle

Any specialist agent may request to be dispatched as multiple parallel instances when splitting would produce meaningfully better results than a single pass. The Facilitator evaluates and approves or denies each request. All requests and decisions are captured for evaluation.

## How It Works

### For Specialists

When you recognize during your work that splitting into multiple focused instances would be more effective than a single broad pass, include a **split request** in your output:

```yaml
split_request:
  reason: "Why splitting would produce better results than continuing as one instance"
  proposed_instances:
    - focus: "What this instance would do"
      context_needed: "What context it needs from the Facilitator"
    - focus: "What this instance would do"
      context_needed: "What context it needs from the Facilitator"
  efficiency_argument: "Why this is worth the resource cost"
```

You do NOT split yourself. You complete your current work to the best of your ability and include the split request alongside your findings. The Facilitator decides whether to act on it.

### For the Facilitator

When a specialist returns a split request:

1. **Evaluate**: Is the efficiency gain real? Would the split produce insights that a single pass would miss, or is it just doing the same work twice with different labels?
2. **Decide**: Approve or deny. Consider rate limit budget, the risk level of the current review, and whether the specialist's reasoning is sound.
3. **Capture**: Record the request and decision via `write_event.py` with tags `split-request,<agent-name>`:
   - If approved: intent `decision`, include the specialist's reasoning and your approval rationale
   - If denied: intent `decision`, include the specialist's reasoning and your denial rationale
4. **Dispatch**: If approved, dispatch the additional instances with the context specified in the request.

### Capture Format

```
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent decision \
  --tags "split-request,<agent-name>" \
  --content "Split request from <agent>: <summary>. Decision: <approved/denied>. Rationale: <why>."
```

## Evaluation

Split request data accumulates in Layer 1 discussions and can be queried via the `split-request` tag. During retrospectives and meta-reviews, evaluate:

- How often are split requests made? By which agents?
- What percentage are approved vs. denied?
- For approved splits: did the additional instances produce findings that the original instance missed?
- Are any agents over-requesting splits (suggesting their base definition needs refinement)?
- Are any agents under-requesting splits in situations where the Facilitator had to manually dispatch multiples?

This data informs whether multi-instance dispatch should become a standard pattern for certain agent/situation combinations, or whether it should remain request-based.

## Constraints

- Specialists CANNOT dispatch themselves — only the Facilitator dispatches via `Task()`
- A split request does not pause the specialist's current work — complete your analysis first, then suggest the split
- The independent-perspective agent has pre-approved multi-instance dispatch (see its agent definition) — it does not need to request splits for its defined instance types. It defines 4 instance types (Independent Analyst, Team Observer, Research Scout, Process Critic), but the Facilitator selects at most 3 per review per the dispatch guidance table in its agent definition. The 4 types are options, not simultaneous defaults.
- Maximum instances per agent per review: 3 (including the original). The Facilitator may override this for exceptional situations but should document why.
