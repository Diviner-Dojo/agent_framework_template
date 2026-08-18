---
title: "Prescriptiveness assessment — where the framework dictates HOW rather than WHAT"
date: 2026-08-15
type: research
status: findings-for-developer-decision
branch: feat/framework-v4-instruments-first
method: read-only survey of the agent-facing instruction surface, two passes
---

# Prescriptiveness assessment

## Why this exists

The instruments-first effort measured **volume** — how much of the instruction surface is
deletable scaffolding — and found under 4%. That measurement is sound, and it retired the
"the framework is too big for the model" thesis.

It does not answer the developer's actual hypothesis, which was that the framework is **too
prescriptive** for frontier models: that it constrains judgment rather than merely occupying
context. Volume and prescriptiveness are different properties, and nothing in the instruments
measures the second. This survey does.

**Method.** Five probes over `CLAUDE.md`, `.claude/rules`, `.claude/commands`, `.claude/agents`,
`.claude/skills` — mechanical ladders, absolute modals, ordering mandates, prescribed phrasing,
pass/fail obedience framing — then a second pass separating genuine *mandates* from
*measurements* the first pass caught as noise (e.g. "40 insertions", "64.8%"). Counts below are
from the filtered pass.

---

## F1 — The prescriptiveness is in the COMMANDS, not the agents

| layer | words | absolute modals (MUST/NEVER/ALWAYS) | per 1k words |
|---|---|---|---|
| `.claude/commands` (24 files) | 44,618 | 106 | **2.38** |
| `.claude/agents` (12 files) | 18,594 | 8 | **0.43** |

**5.5× denser in the dispatching layer than in the charters.** And:

- **14 of 24 commands** carry a `CRITICAL BEHAVIORAL RULES` obedience block.
- **0 of 12 agents** carry one.

The agent charters already describe a role and trust the model to fill it. The commands that
dispatch those agents do not. This is the single clearest structural finding in the survey.

**It is also not new — it is the Wave 3 slice A defect, generalised.** That defect was
`/quiz` and `selecting-review-gates` *ordering the inverse* of `educator.md`'s own charter: a
30/70 Bloom's mix in the charter, the inverse commanded by the dispatcher, live for 21 days.
That was treated as a bug. This survey says it was a **symptom of the layer relationship**: the
commands routinely over-specify what the charters already govern, so the two can disagree, and
when they do the command wins.

---

## F2 — Four ceremony ladders keyed to counting files, and they disagree

| location | rule |
|---|---|
| `CLAUDE.md:39-40` | 3+ files, or 2+ new under `src/` → `/plan` → `/build_module` → gate → `/review`; 1-2 files → implement → gate → `/review` |
| `.claude/rules/autonomous_workflow.md:12,21` | the same ladder, restated |
| `CLAUDE.md:48` + `.claude/commands/ship.md:158-159` | framework changes **> 5 files** → `/review` required; **≤ 5 files** → quality gate sufficient |
| `.claude/skills/selecting-review-gates/SKILL.md:201` | **3+ UI files** → dispatch `ux-evaluator` |

Consequences, stated plainly:

1. **Ceremony is a function of file count, not stakes.** A four-file typo sweep and a four-file
   auth rewrite draw identical process. This is the property the developer named.
2. **The thresholds do not agree with each other** (3, 2, 5, 3), so the answer to "what process
   does this change need" depends on which document is consulted.
3. **This ladder was already scheduled for deletion and the deletion was lost.** The v4
   reconciliation's decision C6 was to delete `autonomous_workflow.md`'s rigid file-count ladder
   in favour of *"match ceremony to stakes"* — commands **available, not mandatory**. ADR-0032
   retired the whole reconciliation over its wrong merge base, and C6 went out with it. The
   ladder is live by accident, not by decision.

---

## F3 — Fixed panel sizes, only one of which is defended

| location | rule | verdict |
|---|---|---|
| `review.md:430`, `selecting-review-gates:142` | critical risk → **at least 3** independent specialists | **KEEP.** This is the retained plurality half of retired Principle #3, backed by `PHILOSOPHY.md` ("Growth has a brake"). It is a floor, keyed to risk. |
| `retro.md:671`, `meta-review.md:425` | "Dispatch **exactly 2** specialists in parallel" | arbitrary — `exactly` forbids both 1 and 3 with no stated warrant |
| `running-build-checkpoints:42` | "dispatches **exactly 2** specialists" | arbitrary, same shape |
| `deliberate.md:17,139` | "**ALWAYS** include at least 2 specialists" | floor is defensible (independence); the `ALWAYS` framing is not |

The distinction that matters: **a floor keyed to risk is stakes-matching; an `exactly N` is
ceremony.** Three of the four are `exactly N` or `ALWAYS`.

---

## F4 — Word caps on the model's own reasoning

Eleven instances cap what a dispatched model may produce:

- `running-build-checkpoints`: **"under 200 words"** ×4 (APPROVE, REVISE, the protocol step, the dispatch prompt)
- `retro.md:690`, `meta-review.md:446`: **"under 300 words"**
- `review.md:961`, `build_module.md:375`: **"150-word cap"** on reflections

These were written when context and cost were the binding constraints. On a frontier model they
cap the depth of the thing being asked for — a checkpoint specialist that finds a subtle
architectural problem must either truncate the finding or break the instruction. Note the
contrast with this session's own evidence: the three blind critics produced 700–1,500-word
reports, and the highest-value finding in the whole slice (the staged-deletion hazard) needed a
measured, multi-paragraph argument to land.

---

## F5 — What is NOT over-prescription (do not delete these)

Stated because the risk of acting on this report is cutting the wrong things:

- **The plurality floor** (≥3 independent specialists at critical risk) — keyed to risk, and the
  surviving half of a retired principle.
- **The seven Non-Negotiable Principles** and the education gate's **exactly two** non-declinable
  classes — constitutional facts, not ceremony. `exactly two` there is a *limit on* gating, not
  an instance of it.
- **Every "Measured …" sentence** — these are evidence with a provenance, and the
  measurement-thinner veto applies.
- **The safety imperatives** in the `--intent-to-add` fences — this session demonstrated what
  happens when one is incomplete.
- **`CRITICAL BEHAVIORAL RULE` items that encode a real invariant** (never skip capture, never
  push without consent). The finding in F1 is about the *density and framing* of the blocks, not
  that all their content is spurious.

---

## Recommendation — ranked by leverage

1. **Replace the file-count ladders with a stakes-keyed trigger** (F2). Reinstate v4 decision
   C6's intent — "match ceremony to stakes", commands available rather than mandatory — as its
   own reviewed slice, and reconcile the four disagreeing thresholds to one rule. Highest
   leverage: it is the developer's exact complaint, it is already a decided-then-lost decision,
   and it touches four surfaces.
2. **Move obedience-block content into the charters, or delete it where the charter already says
   it** (F1). The structural fix for the defect class Wave 3 found by accident.
3. **Retire the `exactly 2` panel sizes; keep the risk-keyed floors** (F3).
4. **Drop the word caps on specialist output** (F4), or restate them as guidance rather than a
   bound.

Each is a vertical slice under the effort's existing method (builder ≠ reviewer, blind critic on
diff + stakes, mutation-proven guards). None requires new machinery.

**One honest caveat about this report.** These are counted markers, not measured harm. The survey
shows where prescriptiveness *is*; it does not prove each instance costs anything. The one place
harm was demonstrated is the inverted-Bloom's defect, which is F1's shape. Treat the ranking as a
hypothesis ordered by expected value, not as an established damage report — and note that this is
the same discipline the effort applies elsewhere: the instrument reports what it can see, and
says so.
