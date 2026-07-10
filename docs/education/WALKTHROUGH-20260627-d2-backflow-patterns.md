# Walkthrough — D2 Backflow Patterns (read at your leisure)

> **Education gate, deferred.** You asked to take this offline. Read whenever you have
> the focus; there's nothing to install or run. When you're ready, ping me and we'll do a
> 5-minute explain-back to close the gate (Principle #6). The merge to your *local* main
> has already happened — nothing is pushed.
>
> **The one-sentence version:** this branch teaches the framework to *stop wasting the
> memory it already collects* — it closes three loops that were previously open (write-only).

---

## The big idea tying all three together

Your framework captures a huge amount as it works: every review finding, every confidence
score, every discussion transcript. The recurring problem these three changes fix is the
same one each time: **we were writing all that down and never reading it back.** A diary you
never re-read. Each ADR closes one of those open loops.

Two of the three (the Stop hook and the calibration loop) are **"backflow"** patterns — they
were invented first in one of your *other* projects (`dan_research_karpathy_wiki`, the
"central brain") and are now flowing *back* into the template so every project benefits.
That direction matters: the template is the hub, but good ideas are allowed to travel
upstream from the leaves. Each one credits the wiki as its origin (that's the Prime
Objective's attribution rule in action — contributors keep credit).

---

## 1. The one-shot Stop hook (ADR-0023)

**The problem, in plain terms.** When a session ends — especially an overnight, you're-asleep
session — it just... stops. Silently. Unless I happened to remember to text you mid-task,
you'd wake up with no idea what finished or what's next.

**The naive fix that's actually worse.** You could make it auto-text "Claude's turn ended!"
every single time it stops. The wiki tried a version of this and learned the lesson: that's
*spam*. A notification that fires on every stop is noise you'll start ignoring — which means
you'll miss the one that mattered.

**The actual design — "one-shot, intent-queued."** Think of it like leaving a sticky note
on the door *before* you leave the house. The orchestrator, right before stopping, writes
**exactly one** note describing what finished and what's next. When the session truly ends,
the Stop hook reads that note, sends it to your phone **once**, throws the note away, and
otherwise stays completely silent. No note on the door → no text. One note → one text.

**The safety nut you should appreciate.** The wiki's version let your *text reply* flow
straight back into the next prompt. This template **forbids that** — a text message is
unauthenticated; anyone could send it. So the template version deliberately *deviates*: it
will act only on a reply that matches a fixed list of allowed choices you set in advance,
never on raw reply text. (This is the same "treat out-of-band replies as untrusted" rule
that's baked into your constitution.) That deviation is the interesting part — porting an
idea isn't copy-paste; it's adapting it to *your* safety rules.

**How you'd know it's working:** an overnight run ends and you get exactly one useful "here's
what I did / here's the next decision" text — not ten "turn ended" pings.

---

## 2. The confidence-calibration loop (ADR-0024)

**The problem.** Every specialist agent attaches a *confidence* number to its findings ("I'm
0.90 sure this is a security bug"). The framework already quietly computes whether those
numbers are *honest* — i.e., when an agent says 0.90, is it actually right ~90% of the time?
But nothing ever *used* that signal. The agents were graded and the report was filed in a
drawer no one opened.

**The analogy.** Imagine a weather forecaster who says "70% chance of rain" every day, and
someone tracks that it actually rains only 40% of those days — but nobody ever tells the
forecaster to recalibrate. They keep being overconfident forever. This change builds the
"hey, your 70% is really a 40%" feedback — and acts on it.

**The design — audit, then *propose*, never auto-edit.** A read-only script
(`audit_calibration.py`) looks at the track record and spots drift: an agent that's
chronically overconfident, categories that are mislabeled, severity scores that don't match
reality. When it finds drift past a threshold, it doesn't *change* anything. It writes a
**proposal** — "I think this classifier should be tightened, and here's the raw evidence that
made me think so" — into a dated queue for **you** to approve or reject.

**Why the human gate is the whole point.** A system that silently re-tunes its own judgment
is a system that can quietly drift away from what you actually want — and cover its tracks.
So the loop is closed *through you*: machine proposes with evidence, human disposes. That's
the same principle as "Layer 3 promotion requires human approval," applied to the framework's
own self-tuning. This is the design choice I'd most want you to internalize.

**How you'd know it's working:** periodically a "calibration proposal" shows up with evidence
attached, you say yes/no, and the agents' confidence scores slowly get more trustworthy.

---

## 3. The T4-A knowledge-loop revival (ADR-0022)

**The problem.** Four months of captured review findings (396 of them) were sitting in a
database that *nothing read back*. Worse, two bugs made the pile actively misleading:

- **Severity was nonsense.** The classifier matched keywords against the whole text, so a
  finding saying *"no injection risk was found"* got filed as **critical** (it saw the word
  "injection"). Result: 53 "critical" findings vs. 1 "high" — exactly backwards.
- **Scaffolding masqueraded as findings.** Section headers like "## Findings" and summary
  lines like "8 findings (1 blocking)" were being stored *as if they were findings
  themselves*, polluting the pile.

**The fix, two halves.** (a) **Reconnect the read path** — the "search prior art before you
build" step now actually queries that findings database and the discussion transcripts, so
the four-month investment finally gets *consumed* before new work starts. (b) **Clean the
capture** — add an `is_noise` flag to mark the junk, and fix the severity classifier so it
stops crying wolf.

**Why it matters to you specifically:** this is the difference between a memory system that
*hoards* and one that *learns*. Your whole philosophy is "reasoning is the primary artifact" —
this makes the captured reasoning re-usable instead of write-only.

**How you'd know it's working:** before building something, I can now say "we hit this exact
problem in March, here's what we learned" instead of rediscovering it.

---

## The thread to pull, when you're ready

When we close the gate, I'll just ask you to explain back — in your own words, no syntax —
roughly these (this is to confirm *I taught it well*, not to test you):

1. Why is "text you once, only when there's something to say" better than "text you every
   time"? (the Stop hook's whole reason for existing)
2. When the calibration loop notices an agent is overconfident, what does it do — and what does
   it pointedly **not** do? (the human gate)
3. What does "the knowledge loop was write-only" mean, and why is that a waste?

If you can answer those three, you've got it — that's the gate.

---

*Branch: `feat/d2-backflow-patterns` · ADRs 0022/0023/0024 · already reviewed (REV-20260613-170043,
Steward 0.90) · quality gate 7/7 · merged to local main, NOT pushed.*
