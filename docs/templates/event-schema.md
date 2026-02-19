# Discussion Event Schema

## Overview

Every canonical reasoning session produces an `events.jsonl` file where each line is a JSON object representing one turn in the discussion. This is the Layer 1 immutable capture format.

## Event Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `discussion_id` | string | yes | Links to parent discussion (format: `DISC-YYYYMMDD-HHMMSS-slug`) |
| `turn_id` | integer | yes | Sequential within discussion, starting at 1 |
| `timestamp` | string (ISO 8601) | yes | When the turn occurred |
| `agent` | string | yes | Which specialist produced this turn |
| `reply_to` | integer or null | yes | Which turn_id this responds to (null for initial turns) |
| `intent` | string (enum) | yes | One of: `proposal`, `critique`, `question`, `evidence`, `synthesis`, `decision`, `reflection` |
| `content` | string | yes | The substantive content of the turn |
| `tags` | array[string] | yes | Topical tags for retrieval |
| `confidence` | float (0-1) | yes | Agent's self-assessed confidence |
| `risk_flags` | array[string] | no | Any risk signals detected (empty array if none) |

## Intent Values

- **proposal**: Suggesting an approach, design, or change
- **critique**: Identifying concerns or issues with an existing proposal
- **question**: Asking for clarification or raising an open question
- **evidence**: Presenting data, benchmarks, or analysis results
- **synthesis**: Combining multiple perspectives into a unified view
- **decision**: Recording a decision that was reached
- **reflection**: Post-discussion self-assessment by an agent

## Example Event

```json
{"discussion_id": "DISC-20260218-140000-auth-refactor", "turn_id": 1, "timestamp": "2026-02-18T14:00:15Z", "agent": "architecture-consultant", "reply_to": null, "intent": "proposal", "content": "The authentication module should be refactored to use OAuth 2.0 PKCE flow. The current session-based approach doesn't support our mobile client requirements.", "tags": ["authentication", "oauth", "architecture"], "confidence": 0.85, "risk_flags": []}
```

## Immutability Rule

After a discussion is closed (status changes to `closed`), the `events.jsonl` and `transcript.md` files are sealed. No modifications are permitted. Corrections or additions must be recorded as new discussions that reference the original.
