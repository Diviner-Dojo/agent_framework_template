---
description: "Independent multi-agent review of a change. Findings are captured to the discussion record."
argument-hint: "[file/dir] [--deep]"
---

# Review

This command exists for one reason: **you wrote the code, so you cannot be its
only judge** (Principle #3). The value is not the checklist — it is that the
reviewing agents run in separate contexts and never saw why you made your
choices. Preserve that. Give them the diff and the stakes, not your reasoning.

Open the record:

```bash
python scripts/create_discussion.py --type review --slug "<short-slug>"
```

Pick reviewers by what could actually go wrong here, not by ceremony. Most
changes need one or two. Reach for `contrarian` when a decision felt obvious —
that is exactly when it is worth a second look.

| Agent | Looks for |
|---|---|
| `code-reviewer` | correctness, edge cases, test coverage, performance |
| `security-reviewer` | trust boundaries, authz, injection, secret handling |
| `architecture-reviewer` | boundaries, coupling, drift from existing shape |
| `contrarian` | the unconsidered alternative, the buried assumption |

Dispatch them in a single message so they run concurrently. Record each set of
findings as it arrives:

```bash
python scripts/write_event.py <discussion-id> --agent <name> --type critique --content "..."
```

Then judge the findings yourself — reviewers surface candidates, they don't
issue verdicts. Report everything they found and filter in the open, rather
than asking them to self-censor to high-severity only.

Write the report to `docs/reviews/REV-<timestamp>.md`.

Then record what the review actually yielded. **This is the only place ground
truth enters the system** — nothing else knows which findings survived your
judgment, and without it agent effectiveness, calibration, and the risk weights
are all guesses:

```bash
python scripts/record_yield.py <discussion-id> review <outcome> \
  --blocking <n> --advisory <n> --false-positive <n> --turns <n>
```

`--false-positive` is the count you examined and rejected. Record it honestly
even when — especially when — it makes a reviewer look bad; a flattering number
here silently corrupts every downstream metric. Outcome is one of `approve`,
`approve-with-changes`, `request-changes`, `reject`.

Seal the record:

```bash
python scripts/close_discussion.py <discussion-id>
```

Close the discussion even if the review is abandoned — an unsealed discussion
corrupts the capture stack. Finish by naming the blocking findings plainly, and
offer `/teach` if the change carries a concept worth holding.
