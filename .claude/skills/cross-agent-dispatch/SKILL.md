---
name: cross-agent-dispatch
description: Protocol for any specialist to request the facilitator dispatch a different agent. Use during multi-agent reviews or builds when a specialist needs another agent's expertise, or when capturing dispatch-request / dispatch-decision events. For multi-instance splits of the same agent, see the multi-instance-dispatch skill instead.
---

# Cross-Agent Dispatch Protocol

> Enables any specialist to request the facilitator dispatch another agent when domain expertise
> beyond their own would improve the team's output. All requests are captured for retrospective
> analysis of how the team collaborates.

## The Core Rule

**Any specialist may request that another agent be dispatched. All requests go through the facilitator. All requests are captured.**

No agent dispatches another agent directly. The facilitator evaluates every request and decides whether to act on it. This preserves the single-orchestrator pattern while enabling organic collaboration.

## How to Request

Include a dispatch request block in your output:

```yaml
dispatch_request:
  requesting_agent: <your agent name>
  requested_agent: <agent to dispatch>
  instance_type: <optional: for agents with multi-instance support>
  reason: <why this agent's expertise is needed — be specific>
  context_to_provide: <what the dispatched agent needs to know>
  urgency: blocking | enhancing
```

- **blocking**: Your analysis cannot be completed meaningfully without this agent's input. The facilitator should prioritize this dispatch.
- **enhancing**: Your analysis is complete, but another agent's perspective would improve the team's collective output. The facilitator dispatches at their discretion.

## Facilitator Evaluation

When the facilitator receives a dispatch request:

1. **Evaluate the reasoning**: Is the requested expertise genuinely needed, or is the requesting agent just subdividing its own work?
2. **Consider the workflow**: Is this review/build already dispatching the requested agent? If so, the request may be redundant — or it may indicate a specific focus the standard dispatch would miss.
3. **Consider the budget**: Each dispatch consumes rate limit. Is the value proportional to the cost?
4. **Approve or deny**: Capture the decision.

The facilitator may also modify the request — dispatching a different agent than requested, or adjusting the context provided.

## Capture

All dispatch requests and decisions are captured via `write_event.py`:

### Request Event
```bash
python scripts/write_event.py <discussion_id> \
  --agent <requesting_agent> \
  --intent proposal \
  --tags "dispatch-request,requested:<requested_agent>" \
  --content "Dispatch request: <reason>"
```

### Decision Event
```bash
python scripts/write_event.py <discussion_id> \
  --agent facilitator \
  --intent decision \
  --tags "dispatch-decision,requested:<requested_agent>,outcome:<approved|denied>" \
  --content "Dispatch <approved|denied>: <rationale>"
```

## Known Dispatch Patterns

These are established cross-agent collaboration patterns. The facilitator should recognize and expedite these:

| Requesting Agent | Requested Agent | Pattern |
|---|---|---|
| independent-perspective (Research Scout) | project-analyst | Cross-domain discovery: Scout found an external pattern worth deep investigation |
| ux-evaluator | independent-perspective (Research Scout) | Creative UX challenge: needs research into how other apps solve a design problem |
| educator | security-specialist | Knowledge gap: developer needs threat model explanation during education gate |
| educator | architecture-consultant | Knowledge gap: developer needs architectural reasoning explained |
| any specialist | docs-knowledge | Constitution check: specialist uncertain whether a pattern aligns with CLAUDE.md/PHILOSOPHY.md |
| docs-knowledge | any specialist | Knowledge flow: historian found a stuck insight that needs domain validation before promotion |

## What This Protocol Does NOT Cover

- **Multi-instance splits**: Covered by the `multi-instance-dispatch` skill. Splits are an agent requesting copies of itself; dispatch requests are an agent requesting a *different* agent.
- **Standard facilitator dispatch**: The facilitator's normal specialist assembly during reviews and builds is not a "dispatch request" — it's the facilitator's core responsibility. This protocol covers agent-initiated requests only.
- **Model tier overrides**: The facilitator's ability to dispatch agents at higher model tiers is independent of this protocol and documented in the facilitator agent definition.

## Retrospective Value

The `dispatch-request` and `dispatch-decision` tags enable retrospective analysis:

- Which agents most frequently request help from others? (May indicate scope gaps)
- Which requests are most often denied? (May indicate misunderstanding of other agents' roles)
- Which cross-agent collaborations produce the highest-value findings? (Informs team development)
- Are there patterns of requests that suggest a permanent collaboration channel should be formalized?

The facilitator and steward review these patterns during `/meta-review`.
