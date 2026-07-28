---
description: "Brief the developer on a change so they can make the next decision well. Risk-scaled, always skippable, always recorded."
argument-hint: "[file/dir/topic] [--depth light|standard|deep]"
---

# Teach

Teaching is the point of this framework, not a toll on the way to merge.

Score the change unless the developer named a depth:

```bash
python scripts/assess_risk.py
```

Then deliver at that depth. Aim at the **next decision** the developer will
face, not at whether they can recite what you wrote.

**light** — three lines. What changed, why it matters, what to watch for.

**standard** — the concept they now need, the tradeoff that was live and which
way you went, and the thing most likely to bite them later. Close with one
real question: something a person who understood would answer differently from
someone who didn't. Not a recall check.

**deep** — the above, plus walk the code in the order it executes rather than
the order it appears. Stop where a reasonable person would have chosen
differently and say so. Keep going until they can explain it back in their own
words — then stop, immediately.

Throughout: if they say skip, stop and record it. No second ask, no
disappointment, no "are you sure." Their time is theirs.

```bash
python scripts/briefing.py record --scope "<what>" --depth <depth> --risk <n> \
  --concept "<the one idea they should now hold>"
# or, if they skipped:
python scripts/briefing.py record --scope "<what>" --depth <depth> --risk <n> \
  --deferred --note "<their reason, if given>"
```

Write `--concept` as the single sentence you would want them to still have in
six months. If you can't compress it to one sentence, you haven't found it yet.

Anything genuinely surprising that came out of the conversation is a candidate
for `/remember`.
