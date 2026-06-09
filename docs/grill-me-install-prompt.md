# Grill-Me Install Prompt

A portable, copy-paste prompt to add the `grill-me` skill to any other project.
Paste everything inside the code block below into a fresh Claude Code session in the
target project.

````
Add a "grill-me" skill to this project.

Placement:
- If this project keeps Claude skills in `.claude/skills/<name>/SKILL.md` (one folder per skill), create `.claude/skills/grill-me/SKILL.md`.
- Otherwise, match wherever this project stores its agent/skill/prompt files; if there's no such convention, default to `.claude/skills/grill-me/SKILL.md` and create the folders.
- If a project index/registry of skills exists (e.g. a Rules Index or skills list in CLAUDE.md or a README), add a one-line reference to grill-me there for discoverability. If no such index exists, skip that step.

Write the file with EXACTLY this content:

---
name: grill-me
description: Interview the user relentlessly — one question at a time, with a recommended answer for each — to stress-test a plan, design, process, or decision until every branch is resolved. Checkpoints each answer to a dated file in brainstorms/, so the session survives context drift and can resume where it left off after an interruption. Use when the user wants to think through or pressure-test something, get grilled on a design or decision, or says "grill me".
---

_Purpose: turn a fuzzy idea into resolved, captured decisions by interviewing the user relentlessly and checkpointing every answer to disk — so the session survives context drift and can resume after an interruption._

## The interview

Interview me relentlessly about every aspect of this topic until we reach a shared understanding. Walk down each branch of the decision tree, resolving dependencies between decisions one at a time.

- Ask exactly one question at a time, and wait for my answer before asking the next.
- For every question, propose your recommended answer with a one-line rationale, so I can react ("yes", or "yes, but change X") instead of authoring from a cold start.
- If a question can be answered by reading the codebase or existing project files, do that instead of asking me.
- If you hit a branch I can't or shouldn't answer — it's someone else's call, or needs data I don't have — don't guess. Record it under **Flagged for others** and move on.
- Match depth to stakes: a tight, well-understood topic may resolve in ~15 questions; a fuzzy or high-stakes one may take 50 or more. Don't wrap early — the edge cases that matter usually surface in the back half.

## Checkpoint every answer to disk

The live conversation will drift as it grows; the file is the source of truth.

- The moment I answer a question, append that exchange to the session file (see below) **before** asking the next question.
- Capture my answer **verbatim** in the Q&A log — do not paraphrase it.
- After each append, update **Key decisions** and **Open threads** to reflect the new state.

## Session file

Store one file per topic at `brainstorms/YYYY-MM-DD-<topic-slug>.md`, where the date is when the topic was first grilled and `<topic-slug>` is a short kebab-case name. Create the `brainstorms/` folder and the file lazily, on the first answered question. Use this structure:

```
# Grill: <Topic>

> Status: in-progress | complete
> Started: YYYY-MM-DD · Last updated: YYYY-MM-DD

## Highlights
<3–6 lines a future reader can skim in 30 seconds>

## Key decisions
- <Decision stated as a commitment — what we settled and why>

## Open threads
- <An unresolved branch, or the exact next question to ask on resume>

## Flagged for others
- <A question I couldn't or shouldn't answer — and who/what it needs>

## Q&A log
### Session 1 — YYYY-MM-DD
**Q:** <your question>
**A:** <my verbatim answer>
```

## Resume an interrupted session

On startup, derive the topic slug from my request and search `brainstorms/` for a file whose name ends with `-<topic-slug>.md`.

- **If a match exists:** read it. Briefly replay **Highlights** and **Key decisions** so we both re-anchor, tell me what's still in **Open threads**, and ask whether anything has changed since the last session. Then continue from the first open thread. Do **not** re-ask questions already answered in the Q&A log. Append new exchanges under a fresh `### Session N — YYYY-MM-DD` marker in the same file.
- **If no match exists:** create a new file from the template above and start fresh.

## When the session ends

Set `Status: complete`. Make sure **Highlights** works as a 30-second digest, **Key decisions** read as commitments, and **Open threads** / **Flagged for others** clearly state what still needs another human or more thought. Then offer to fold the captured decisions into the relevant skill, document, or plan.

(End of file content.)

After creating it, confirm the path you used and whether you added an index reference.
````
