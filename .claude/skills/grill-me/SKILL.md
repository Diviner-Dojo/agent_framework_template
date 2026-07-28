---
name: grill-me
description: Interview the user relentlessly — one question at a time, each with a recommended answer — to stress-test a plan, design, or decision until every branch is resolved. Checkpoints each answer to a dated file in brainstorms/ so the session survives interruption. Use when the user wants to think something through or says "grill me".
---

Turn a fuzzy idea into resolved, captured decisions by interviewing the user
one question at a time, writing every answer to disk as it arrives.

## The interview

Walk down each branch of the decision tree, resolving dependencies one at a
time.

- **One question per turn.** Wait for the answer before asking the next. This
  is the whole discipline — batching questions gets you shallow answers to all
  of them.
- **Propose your recommended answer** with a one-line rationale, so they can
  react rather than author from a cold start.
- **Read before asking.** Anything answerable from the codebase or existing
  files, answer yourself.
- **Don't guess on someone else's call.** If a branch needs data you don't have
  or authority you don't hold, record it under **Flagged for others** and move
  on.
- **Match depth to stakes.** A tight topic may resolve in ~15 questions; a
  fuzzy or high-stakes one may take 50+. Don't wrap early — the edge cases that
  matter usually surface in the back half.

## Checkpoint every answer

The conversation drifts as it grows; the file is the source of truth.

The moment they answer, append that exchange to the session file **before**
asking the next question. Capture their answer **verbatim** — do not
paraphrase. Then update **Key decisions** and **Open threads**.

## Session file

One file per topic at `brainstorms/YYYY-MM-DD-<topic-slug>.md`, created lazily
on the first answered question.

```
# Grill: <Topic>

> Status: in-progress | complete
> Started: YYYY-MM-DD · Last updated: YYYY-MM-DD

## Highlights
<3–6 lines a future reader can skim in 30 seconds>

## Key decisions
- <What we settled, stated as a commitment, and why>

## Open threads
- <An unresolved branch, or the exact next question to ask on resume>

## Flagged for others
- <A question they couldn't or shouldn't answer — and who it needs>

## Q&A log
### Session 1 — YYYY-MM-DD
**Q:** <question>
**A:** <verbatim answer>
```

## Resuming

Derive the slug from their request and search `brainstorms/` for a file ending
`-<topic-slug>.md`.

If one exists, read it, replay **Highlights** and **Key decisions** so you both
re-anchor, say what's still open, and ask whether anything has changed. Then
continue from the first open thread — never re-ask what the Q&A log already
answered. Append under a fresh `### Session N` marker.

## Ending

Set `Status: complete`. Make **Highlights** work as a 30-second digest and
**Key decisions** read as commitments. Then offer to fold the result into
`/decide`, a plan, or the relevant document.
