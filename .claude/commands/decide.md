---
description: "Capture an architectural decision as an ADR with its reasoning. Use before implementing, not after."
argument-hint: "<decision topic>"
---

# Decide

An ADR written after the fact is a summary. An ADR written before is a
decision. Use this when a choice is hard to reverse, when reasonable engineers
would disagree, or when someone in a year will ask "why is it like this."

Open the record first, so the deliberation itself is captured rather than just
its conclusion:

```bash
python scripts/create_discussion.py --type decision --slug "<short-slug>"
```

Search for prior art before proposing anything. A decision that contradicts an
existing ADR without knowing it is worse than no decision:

```bash
grep -ril "<keyword>" docs/adr/ memory/ | head
```

Then think it through in the open. Lay out the real alternatives — including
the one you don't favour, argued honestly — and what would have to be true for
each to be right. If a genuine fork appears, stop and put it to the developer;
that is their call, not yours.

Write to `docs/adr/ADR-NNNN-<slug>.md`, next sequential number, never reusing
one:

```markdown
---
adr_id: ADR-NNNN
title: "<what was decided>"
status: accepted
date: <YYYY-MM-DD>
decision_makers: [developer, <agents involved>]
discussion_id: DISC-...
supersedes:
scope: framework | project
---

## Context
What forced a decision. The constraints that were real at the time.

## Decision
What we chose, in the active voice.

## Alternatives Considered
What else was on the table, and what would have made each of them right.

## Consequences
What this costs. What it forecloses. What we'll wish we'd known.
```

The field names and the four headings are exact — `scripts/quality_gate.py`
checks them literally, and a near-miss (`id:`, or `## Alternatives`) fails the
gate. Verify before you finish:

```bash
python scripts/quality_gate.py --skip-tests --skip-coverage
```

`discussion_id` is required, because an ADR that can't point back to its
reasoning has lost the property that makes it trustworthy.

Superseding an earlier ADR means setting the old one's status to `superseded`
with a pointer forward. It is never deleted (Principle #4).

Close the discussion when done.
