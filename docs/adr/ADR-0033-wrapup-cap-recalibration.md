---
adr_id: ADR-0033
title: "Recalibrate the 1M-window wrap-up caps on a documented anchor; ADR-0018's magnitude objection upheld on cost, withdrawn on quality; stop showing the model a context countdown"
status: proposed
date: 2026-08-08
decision_makers: [fixer-slice-s5c, fixer-slice-s5d]
discussion_id:
discussion_provenance: >-
  ABSENT. No Layer 1 discussion was opened for slice S5c, and this field is left
  empty rather than pointed at a discussion that does not contain this reasoning.
  The reasoning of record is this document plus the CAP RECALIBRATION block in
  config/model_context_profiles.yaml, bound to the resolver by
  tests/test_context_sensor.py::TestCapRationaleIsRecorded.
spec_id:
supersedes: ADR-0018
supersedes_scope: >-
  The 1M-window absolute cap VALUES in ADR-0018's "Thresholds" bullet and the
  magnitude half of its "The 1M-window threshold model" argument, ONLY. ADR-0018's
  threshold STRUCTURE (min(fraction x window, absolute_cap); which term binds on
  which window class; integer inclusive comparison; conservative-floor fallback),
  its consent model, its sensor/hook design, its handoff protocol, and its
  2026-06-07 auto-launch amendment all STAND and are not touched here.
extends:
scope: framework
risk_level: high
confidence: 0.62
tags: [context-window, session-wrapup, thresholds, judgment, recalibration, adr-0018, principle-4, context-countdown, premature-wrapup]
---

## Context

`config/model_context_profiles.yaml` resolves a model to a wrap-up profile and computes
`effective = min(fraction x window, absolute_cap)`. On a 1M-token window the absolute cap is the
binding term, so the 1M trigger is whatever number is written in that cap. ADR-0018 set it, in May
2026, against Opus 4.7: **soft 140000 / hard 180000**.

**The measured harm.** On 2026-08-07 a live session on a 1M-window model was issued a hard "stop
work and hand off" order at roughly **19% occupancy** — 190000 resident tokens against a hard cap of
180000, which is 18% of the window the session was actually running in. Nothing was wrong with the
machinery; the number was simply calibrated for a different window. The regression is pinned by
`tests/test_context_sensor.py::TestWrapupCapRecalibration::test_a_19_percent_1m_session_no_longer_trips_the_hard_stop`.

**The failed first fix, and why this ADR exists at all.** A prior slice (S5b) raised the caps to soft
400000 / hard 500000 and bound them to a written rationale with tests. The binding was good work and
survives here. The way it was recorded was not: it **amended `ADR-0018` in place, deleting twelve
lines of that ADR's original reasoning** — including the sentence that argued against the very
magnitude it was moving to. Principle #4 says ADRs are never deleted, only superseded with a
reference to the replacement. ADR-0018 has been reverted to its committed state. This document is
the replacement it should have been.

That failure mode is the whole reason this record is worth writing: **an amendment that improved a
number by deleting the reasoning that argued against it.** The objection is therefore quoted here in
full, engaged in full, and partially conceded rather than deleted.

**The objection, quoted from ADR-0018 as accepted** (§ "The 1M-window threshold model (why the
absolute cap)"):

> Percentage alone is the wrong control on a 1M window: 55% = 550K tokens, which is wasteful
> (per-turn cost scales with resident context) and still degraded.

**The number both documents leaned on, and why it is gone.** ADR-0018's Context section recorded the
research grounding, and it is a *range*, not a point:

> Anthropic publishes **no** hard "% threshold"; third-party benchmarks (RULER/LongBench) put the
> high-quality "effective" working fraction at ~50–65% of the window.

Both the 180000 that caused the harm (18% of 1M) and the 500000 that S5b proposed (50%) were
positions taken against that one range. Neither was measured. **As of the 2026-08-08 amendment
below, that range is retired as a justification for any number in this system** — see *Amendment
2026-08-08* immediately after the Decision.

## Decision

### The caps

Two profiles move. Their canonical values, in the form the tests parse:

```
CAP opus_1m: soft 300000 / hard 400000
CAP sonnet_1m: soft 250000 / hard 350000
```

As fractions of a 1M window that is opus soft 30% / hard 40%, and sonnet soft 25% / hard 35%. The two
200K-window profiles (`sonnet_200k`, `haiku_200k`) are **unchanged**; see *Why the 200K class was not
touched* below.

These values are **lower than the 400000/500000 the failed amendment proposed** and higher than the
140000/180000 they replace. Moving down from S5b's numbers is the substantive concession this
document makes to the objection above — not a rewording of it.

### Amendment 2026-08-08 (pre-acceptance): three developer-approved changes

The authoritative Anthropic reference was loaded *after* the caps slice shipped, and it contradicts
two things this record was built on. The developer approved three amendments on 2026-08-08, folded
into the body above and below rather than appended as a diff:

1. **RETIRED 2026-08-08: no documented quality cliff** — the rationale was wrong, not the number.
   The reference states a 1M window as both default and maximum for Claude Opus 5, and that
   instruction following, tool calling, and reasoning stay strong across it. The "context rot" /
   "effective working fraction 50–65%" justification is third-party, older, and measured on earlier
   model generations. **The cap exists for cost and handoff headroom, not for degradation.**
   Disposition 3 moves from *narrowed* to *withdrawn*; the derivation is re-anchored (both above).
2. **Stop injecting the countdown into the model's context** — see *The countdown the model was
   being shown* below. This is the behavioral half of the amendment and the sharpest of the three.
3. **Anchor the cap on documented numbers** — the 150000 server-side compaction default trigger plus
   the measured handoff cost, replacing the retired band (see the derivation above).

**Why revising in place is legitimate here, and would not be for ADR-0018.** This record has
`status: proposed`, was created in this same effort, and has never been committed or accepted, so
there is no accepted reasoning for a reader to be deprived of — the thing Principle #4 protects. What
it superseded is untouched: ADR-0018 stands intact, objection included, and
`test_adr_0018_was_not_amended_in_place` still fails if anyone edits it back. The change is recorded
here rather than performed silently precisely because the last attempt at "just fix the number" is
what this document exists to correct.

### The countdown the model was being shown

The `UserPromptSubmit` guard (`.claude/hooks/context_guard.py` → `src/context_sensor.py`) injected a
budget countdown into the **model's** context on every prompt. Measured 2026-08-08 by piping a real
payload through the hook, a 1M-window session at 65% occupancy received, verbatim:

> ⛔ Context HARD wrap-up: ~651,312 tokens (~65% of the opus_1m window; hard threshold 400,000). Stop
> starting new work. […] before context degrades / auto-compaction.

Three budget figures and a degradation claim, on every turn. The reference names this pattern twice
as a *cause* of the failure the machinery exists to prevent:

> Budget countdowns rendered into context: surfacing remaining-token counts to the model can cause
> premature wrap-up behavior; avoid showing them where possible.

and, on long-running agents:

> it can worry about running out of context — suggesting a new session or trimming its own work —
> most often when the harness surfaces a remaining-token countdown. Avoid showing explicit
> context-budget counts.

**Decision: keep the checkpoint, delete the countdown.** The model-facing nudge is now fixed,
figure-free text at both levels (`_nudge_text`), plus the reference's own recommended
context-anxiety mitigation ("Room to write it in full is reserved at this threshold … do not trim
your work, shorten your answers, or suggest a new session on account of context"). The
developer-facing status line is **unchanged** and still carries occupancy, thresholds, and the
resolution markers.

#### The reassurance clause had to be re-worded, and the first version of it was false

The first attempt at that mitigation said **"Context remaining is ample"**. It was justified from
`opus_1m`, which leaves 430000 tokens above its hard cap — 17.2x the reserve. That survey only ever
covered the 1M class, and `_nudge_text` is **profile-independent**: one constant reaches every
profile. Measured 2026-08-08 by piping payloads through both hooks, a `sonnet_200k` session reading
`ctx 70% | 141K/200K` received the identical sentence — with **26000 tokens** left before the harness
auto-compacts: 1.04x the `RESERVE` and **1.15x** `HANDOFF`, the term the derivation table above
defines as the measured cost of one handoff — followed by "do not trim your work … on account of
context".

> **Ratio corrected 2026-08-08 (round 3), re-divided in round 4, and re-divided again on 2026-08-09
> (round 5).** This sentence first said *1.42x*. That figure is 26000 ÷ **18371** (SUPERSEDED) — the
> four-component *live-measured subtotal as round 2 measured it* — not `HANDOFF`, which is that
> subtotal **plus** the itemized `BUILD_STATUS` edit payload. Two quantities, one name, and the
> larger denominator is the one this document defines. Divided by `HANDOFF` as the terms table
> states it, 26000 tokens of headroom is **1.15x** one handoff (round 3 printed 1.28x off the
> then-stated `HANDOFF` of 20391 (SUPERSEDED); round 4's corrected 20568 (SUPERSEDED) divided to
> 1.26x; the 2026-08-09 re-measurement to 22687 divides to 1.15x). Every correction has moved the
> same way: the correction is sharper, not softer, than what it
> replaces, and the tightest profile has
> *less* margin over one handoff than the retracted number claimed — less again after round 4, and
> less again after round 5. The denominator moved because the measurement moved, not because the
> claim was re-argued.
> `TestCapRationaleIsRecorded::test_the_adrs_stated_handoff_ratio_is_computed_against_its_own_defined_term`
> performs the division, so the two cannot part company again.

The counter-evidence was already inside this document: the headroom table below records
`sonnet_200k` at 1.04x and *Why the 200K class was not touched* says in terms that it "clears the
handoff reserve by 1000 tokens". The nudge asserted the opposite to the profile nearest the
mechanical floor. That is this amendment's own failure mode, mirrored: the countdown over-stated
scarcity to every session, and the first fix under-stated it to every session — which is the more
dangerous direction, because thread loss is the harm this machinery exists to prevent.

**The rule now pinned:** a constant emitted to every profile may only assert what holds at the
*tightest* profile. So the wording moved off *how much window is left* (profile-dependent, false at
200K) and onto *room to write the handoff is reserved* — which holds for all four profiles by
construction, since `TestHandoffHeadroomInvariant` requires `auto_compact_tok − hard_tok ≥ 25000` and
the measured handoff cost sits under that reserve. The claim is enforced rather than asserted:
`test_the_reassurance_is_true_on_the_tightest_profile_not_just_on_1m` re-measures the handoff cost,
finds the tightest profile in the config, and fails naming the nudge if the promise stops being true
there.

**The alternative considered and rejected: emit nothing to the model at all.** That reading is
available — the reference says avoid showing counts, not "keep instructing". It was rejected because
the documentation objects to the *countdown*, not to being told to checkpoint, and deleting the nudge
deletes the mechanism: a session that is never told to checkpoint dies without a handoff and the
thread is lost, which is the harm the developer ranks highest and the reason this system was built.
Too permissive is the worse failure; the cheapest way to be neither is to change *what the model is
told*, which is what was done.

Enforced by `TestModelFacingNudgeCarriesNoFigures`, which sweeps occupancies from below-soft to
far-past-hard and asserts (a) the injected text contains **no digit at all**, (b) the status line for
the *same* reading still does — and reproduces, verbatim, the readings this ADR and both hook
docstrings quote as measured, in all three resolution states and both window classes — and (c) the
reassurance clause is true on the *tightest* profile the config defines, not merely on `opus_1m`. A
future edit cannot quietly restore the countdown, cannot "fix" the test by blinding the developer
instead, and cannot re-introduce a comforting sentence that only holds for 1M-window models.

#### The second surface: the protocol was still ORDERING the recital (round 3, 2026-08-08)

De-numbering the guard removed the figure from what the model is *handed*. It did not remove it from
what the model is *told to go and say*. `.claude/skills/wrapping-up-sessions/SKILL.md` — the page the
nudge sends the model to, and the one this amendment had already edited — kept, in **protocol step
1**, the instruction:

> **Announce + choose.** State the trigger (`soft|hard`, profile, ~tokens).

That sat roughly ten lines under this amendment's own new warning not to go hunting for the figure,
and it fired at the exact moment the amendment exists to protect: the wrap-up itself. Its effect is
worse than the guard's was, because a model obeying it has to go *look the number up* — the
"suggesting a new session / trimming its own work" behaviour the reference attributes to
context-budget awareness, triggered by our own instruction rather than by the harness. The skill is
CORE and propagates verbatim, so four derived projects would have received it. Step 1 now names the
level and the profile and forbids the figure in terms, and says the prohibition governs every step
below it, not only that one.

**The guard against the class, not the instance.** The suite already had
`test_the_wrapup_skill_cites_a_governing_record_that_exists`, added when the same page was found
citing a phantom amendment — a point fix for one previous defect. Nothing read the page's
*instructions*. `TestWrapupProtocolOrdersNoFigureRecital` now does: it flags any instruction to
utter an occupancy figure, by verb-and-term rather than by literal, and independently flags any
mention of such a figure inside the protocol's own steps that is not a prohibition. Its own docstring
states what it cannot catch, and its mutation cases restore the deleted instruction in six phrasings
— including one with no verb at all — and require each to be caught.

### This is a judgment, and the thing it turns on is not measurable here

"At what occupancy does output quality actually degrade?" **is not answerable from this repository.**
There is no eval harness, no held-out task set, no quality-vs-occupancy series, and no per-turn
telemetry that would separate a degraded answer from a hard question. No number in this ADR is
derived from such a measurement and none should be read as if it were.

What is being replaced is **not evidence**. The 140000/180000 pair was also a judgment: chosen in May
2026, against Opus 4.7, with nothing behind it either, and ADR-0031 concedes in writing that it is
"plausibly still conservative". This ADR replaces a stale judgment with a current one plus the two
things the old one never had — a written derivation, and tests that fire when the derivation stops
matching the config.

### Disposition of ADR-0018's magnitude objection: cost UPHELD, quality WITHDRAWN

The quoted objection bundles three distinct claims. They do not share a fate, and collapsing them is
how the previous attempt talked itself into deleting the sentence.

**1. Structural — "percentage alone is the wrong control on a 1M window". UPHELD, IN FULL,
UNCHANGED.** The absolute cap must remain the binding term on a 1M window; the percentage governs the
200K class. Nothing here weakens that, and both new caps stay strictly below their fraction products
(300000 and 400000 against 0.55 x 1M = 550000 and 0.70 x 1M = 700000), so control has not quietly
reverted to the fractions. Enforced by
`TestWrapupCapRecalibration::test_absolute_caps_still_bind_on_the_1m_profiles`.

**2. Cost — "wasteful (per-turn cost scales with resident context)". UPHELD, and now the load-bearing
reason the cap exists at all.** The mechanism is real and undisputed: resident context is re-billed
every turn net of cache, so a session running at 500000 pays materially more per turn than one
running at 400000, for its entire time in that band. Nothing in this repo quantifies the *benefit*
side of that trade, so the honest response to an unrebutted cost objection is to **take less of the
thing it objects to**. That is why the hard cap is 400000 and not the 500000 the failed amendment
chose. With claim 3 withdrawn (below), this claim and the handoff-affordability floor are the *only*
things holding the cap up — and cost is the only one of the two that argues for a cap rather than
merely a ceiling.

**3. Quality — "55% ... is still degraded". WITHDRAWN as to the models this config maps.** This ADR
originally *narrowed* the claim by appeal to a third-party "effective working fraction ~50–65%" band,
reasoning that a point claim inside a range is neither confirmed nor refuted. The 2026-08-08
amendment goes further and retires the band itself, which removes the narrowing's own footing. The
authoritative Anthropic reference states, for Claude Opus 5, a 1M-token context window as both the
default *and* the maximum, and that **instruction following, tool calling, and reasoning stay strong
across the full window**. Anthropic publishes no degradation threshold. The retired band is
third-party, older, and measured on earlier model generations. There is therefore nothing left
supporting a quality-based cap, and this ADR no longer asserts one.

**What is NOT claimed.** Not that ADR-0018 was wrong: its objection was written against a different
model generation, where it may well have held, and on the cost half this ADR says it was right and
acts on it. Not that the cap is unnecessary: claim 2 alone justifies one. And not that a bigger cap
would be *safe* — only that "quality degrades" is no longer an argument anyone here can make.

### Derivation, re-anchored on documented and measured numbers

Every term is published by Anthropic or measured in this repo. None is a quality estimate.

| Term | Value | Source |
|---|---:|---|
| `UNIT` | 150000 | **Documented** — Anthropic's server-side compaction default trigger |
| `HANDOFF` | 22687 | **Measured** in this repo — the *sum of the itemization below*, re-counted from the files on disk 2026-08-09 (round 5) |
| `RESERVE` | 25000 | `HANDOFF` rounded up, covering un-itemized steps |
| `RUNWAY` | 100000 | soft→hard gap; 4.4x `HANDOFF` |
| `TIER_STEP` | 50000 | `RUNWAY / 2`; sonnet sits one step below opus |

```
opus_1m   soft = 2 x UNIT              = 300000
opus_1m   hard = opus soft + RUNWAY    = 400000
sonnet_1m soft = opus soft - TIER_STEP = 250000
sonnet_1m hard = opus hard - TIER_STEP = 350000
```

1. **`UNIT` is the anchor, and it is a context-management threshold rather than a quality one.**
   150000 is where Anthropic's own stack judges a conversation large enough to begin summarizing. It
   says nothing about whether the model is still good at 150001 tokens — it says the conversation has
   become large enough to be worth managing, which is precisely the cost claim in disposition 2.
2. **`2 x UNIT` is the one genuinely chosen number left in this ADR.** `1x` (150000) would read "big
   enough for Anthropic to start summarizing" as "big enough to stop working" — a category error, and
   it lands within 30000 tokens of the 180000 cap that produced the measured harm. `3x` (450000)
   clears every mechanical check too, which is exactly why clearing them is not the test. `2x` is the
   smallest multiple that clears the old harmful cap by more than a full `RUNWAY`.
3. **`RUNWAY` is sized on the measured handoff cost, not chosen.** The soft→hard gap must be wide
   enough to *finish the current atomic step and then* write the handoff, not merely to bail out.
4. **MECHANICAL FLOOR — checked, deliberately not binding.** The hard cap must leave room to actually
   WRITE the handoff before the harness auto-compacts at `0.83 x window = 830000`:
   `830000 − 400000 = 430000` spare against a ~22700-token measured need (17.2x `RESERVE`; round 4
   stated the same multiple against a ~20600 (SUPERSEDED) token need). The cost
   anchor binds long before the floor does — the floor is a backstop, not a target.

**Honest disclosure about this derivation.** It was constructed *after* these values were already in
force, to replace a justification found to be unsupported. It is a defensible re-derivation, not
independent evidence that 300000/400000 are correct. What genuinely changed on 2026-08-08 is the
anchor — from a third-party quality band measured on older models to a number Anthropic publishes —
and the retirement of every quality claim built on the old one. The values did not move, and a reader
is entitled to weigh that accordingly. Enforced by
`TestWrapupCapRecalibration::test_1m_hard_caps_stay_within_the_documented_compaction_anchor`, which
requires `hard < 3 x 150000` — strictly tighter than the `hard < 50% x window` band test it replaces.

### The handoff-affordability anchor, re-measured

A hard nudge that fires with no room to act on it loses the thread, which is the harm this machinery
exists to prevent. The cost of writing one handoff was re-measured on **2026-08-09 (round 5)** from
this repo's own
files — including **the actual `docs/handoff/HANDOFF-*.md` artifacts on disk** (16 of them, excluding
`HANDOFF-supervisor-rolling.md`, which is appended to across a whole chain of sessions and is not the
cost of one write). Characters were counted and divided by 3.5 chars/token, a divisor set below the
lowest ratio observed for these files under a real BPE tokenizer, so each line over-states cost. The
16 artifacts run 3132–15207 chars (median 5908), so taking the maximum over-states a typical write by
a further ~2.6x — a spread that has widened from ~1.5x at round 4, and that is the subject of the
open question recorded below:

| Component | chars | tokens |
|---|---:|---:|
| `wrapping-up-sessions/SKILL.md` load | 9091 | 2597 |
| `BUILD_STATUS.md` read (protocol step 3) | 46018 | 13148 |
| `docs/templates/handoff-template.md` read (step 5) | 2275 | 650 |
| handoff artifact write (largest on disk: `HANDOFF-20260809-instruments-first-wave3.md`) | 15207 | 4344 |
| **live-measured subtotal** | | **20739** |
| `BUILD_STATUS` `NEXT SESSION` edit payload (measured once, ~2 x 3409 chars) | | 1948 |
| **total** | | **~22687** |

The reserve the tests enforce is **25000 tokens** — the total rounded up, the excess covering what was
not itemized (close_discussion calls, retention, the final report turn).

> **Total corrected 2026-08-08 (round 4), and the two documents were stale in different ways.**
> Round 3 grew the `SKILL.md` component by a third instalment (177 tok). In the **config** that
> instalment reached the itemization but not the `HANDOFF` term above it, so one file gave two
> answers sixty lines apart: `HANDOFF = 20391` (SUPERSEDED) over an itemization totalling
> 20568 (SUPERSEDED).
> **This ADR** was internally consistent — and wrong at the source: its `SKILL.md` row still read
> 8473 chars / 2420 tok for a file that had grown to 9091 chars, so its 20391 (SUPERSEDED) was a
> correct sum of a stale measurement. Both were re-counted from the files on disk at round 4 to
> **20568** (SUPERSEDED), and re-counted again on 2026-08-09 to the **22687** the table above now
> states.
>
> The pre-existing check compared this ADR's terms table to the config's terms table. They agreed —
> at 20391 (SUPERSEDED) — so it stayed green throughout, which is all it could ever prove: that the
> two documents were copied from each other. `TestHandoffCostDerivationIsSelfConsistent` now *adds
> the itemization up* in both files and requires every stated total to equal it. A number restated
> in three documents needs a test that reads the derivation, not one that compares two copies of the
> same claim. Nothing about the caps moved (see immediately below).
>
> `(SUPERSEDED)` above is a **machine-read marker**, not editorial colour.
> `TestEveryRestatementOfTheDerivedTotalIsBound` scans this file and the config for any figure near
> the derived total and requires it to either equal that total or carry this marker immediately
> after it. A stale figure that reads as current is the whole defect of round 4; the marker is how a
> reader — and the suite — tells "is the total" from "was the total".

**Did the caps move? No — re-checked, and they hold.** `HANDOFF` appears in the derivation only as a
sanity bound (`RUNWAY ≥ 4 x` the live subtotal, `HANDOFF ≤ RESERVE`), never as a term the cap
arithmetic multiplies: the caps come from `UNIT`, `RUNWAY` and `TIER_STEP`, all unchanged. At 22687
the bounds still hold with room — `RUNWAY` 100000 is 4.8x the 20739 live subtotal and 4.4x `HANDOFF`,
and 22687 still fits inside the 25000 `RESERVE` that every profile's headroom is sized against. So
`opus_1m` stays soft 300000 / hard 400000 and `sonnet_1m` stays soft 250000 / hard 350000, and the
headroom table below is unchanged. This held at round 4's total and it holds again at round 5's; the
re-measurement of 2026-08-09 moved no cap. The one figure that *did* move with it is the tightest
profile's headroom expressed in handoffs (1.28x → 1.26x → 1.15x, above), because that ratio is
divided by `HANDOFF`.

**The margin is 2313 tokens — it was 4432 (SUPERSEDED) until the 2026-08-09 re-measurement, and it
is the re-measurement rather than the spending below that took most of it — and this amendment has
now spent 885 of it in three instalments.** The
`SKILL.md` row rose from 1712 to 2348 tokens when that page was retargeted off its severed ADR
citation and taught not to go hunting for the figures the guard no longer supplies; by a further
**72 tok** (2348 → 2420) in round 3, when protocol step 1 stopped ordering the agent to announce a
token figure at wrap-up; and by **177 tok** more (2420 → 2597) in round 3's follow-up, when step 5
was made to rule explicitly on the handoff template's own request for that figure. The first
instalment was **636 tok**. All three are real costs charged against this reserve; they are recorded
here rather than absorbed silently, and they are the reason to treat the reserve as tight. The
subtotal is re-measured on every test run, so further growth fails a test rather than eroding the
margin unnoticed.

#### Re-measured 2026-08-09 (round 5) — this ADR's own trigger fired, and this is what it produced

This section exists because § *What would change these numbers* named the trigger **in advance**:
"`BUILD_STATUS.md` or `handoff-template.md` growing … the early one fires when the live
four-component subtotal reaches the stated `HANDOFF` total … and asks only for a re-measurement."
On 2026-08-09 it fired. Nothing here re-argues a decision; it restates a measurement, which is the
only part of this record that was ever declared maintainable. **No cap moved, no term was
re-derived, and no sentence of the reasoning above was deleted** — the round-4 figures are still in
the text carrying the `(SUPERSEDED)` marker this ADR built for exactly this purpose.

What moved (round 4 → round 5), and why the two components moved for opposite reasons:

| Component | round 4 | round 5 | why |
|---|---:|---:|---|
| handoff artifact write | 2520 | 4344 | the term takes the **largest** artifact on disk, and a new one is now the largest |
| `BUILD_STATUS.md` read | 12853 | 13148 | ordinary session growth, after a retention trim that undid most of it |
| live-measured subtotal | 18620 (SUPERSEDED) | 20739 | |
| **total (`HANDOFF`)** | 20568 (SUPERSEDED) | **22687** | |

**The floor is not breached.** 22687 still fits inside the 25000 `RESERVE` that every profile's
headroom is sized against, so the cap arithmetic was re-checked and left exactly as it was. The
margin narrowed from 4432 (SUPERSEDED) to 2313 tokens. That is the honest number to hold on to:
the reserve is tight, not roomy, and it is now tighter than the round-4 text describes it as being.

**OPEN QUESTION 1 — max or median? A developer decision, deliberately NOT taken here.** The
`handoff_artifact_write` term takes the *largest* artifact on disk. A good handoff is usually the
largest one yet, so **this tripwire should be expected to fire on roughly every wrap-up**. A warning
that fires every time stops being read — the same *advisory becomes wallpaper* failure a reviewer
identified in `scripts/verify_paths_not_taken.py`'s coverage proxy on 2026-08-09, and a failure
this document is unusually badly placed to shrug off, since its whole subject is instruments that
are believed rather than read. The two candidate terms answer different questions:

- **max** answers *"can the worst case still afford to write its handoff?"* — the affordability
  floor's question, and the conservative direction;
- **median** answers *"what does writing a handoff usually cost?"* — the growth-detector's
  question, and the one that would stop the wire firing on every good handoff.

The measured spread is now ~2.6x (16 artifacts, 3132–15207 chars, median 5908), up from ~1.5x at
round 4, so the choice matters more than it did. Which question the instrument is *for* is a
decision about the instrument, not a measurement, and Principle #6 puts it with the developer.
**Left as max.**

**OPEN QUESTION 2 — the `BUILD_STATUS.md` retention cap is load-bearing, and nothing enforces it.**
Before trimming, the Wave 3 session entry took `BUILD_STATUS.md` to 51774 chars (14543 tokens) and
tripped the early wire on that one component alone. Trimming to the documented cap of **three**
`## Previous Session` blocks brought it back to 46018 chars. That cap is stated in `CLAUDE.md` and
observed by hand; it is not checked by anything, and the measurement above is what it looks like
when it is nearly missed. Whether it should be mechanically enforced is a separate change with its
own scope, recorded here rather than smuggled into a re-measurement.

Headroom per profile (`auto_compact_tok − hard_tok`) against that reserve:

| profile | auto-compact | hard | headroom | x reserve |
|---|---:|---:|---:|---:|
| `opus_1m` | 830000 | 400000 | 430000 | 17.2x |
| `sonnet_1m` | 830000 | 350000 | 480000 | 19.2x |
| `sonnet_200k` | 166000 | 140000 | 26000 | 1.04x |
| `haiku_200k` | 166000 | 130000 | 36000 | 1.44x |

The subtotal is recomputed live by `_measured_handoff_cost_tokens()` on every test run rather than
trusted from this table, so the invariant fails when `BUILD_STATUS.md` or the template outgrows the
reserve.

### Why the 200K class was not touched

The table above is also the finding that scoped this change: **the class actually near the mechanical
constraint is 200K, not 1M.** `sonnet_200k` clears the handoff reserve by 1000 tokens. Moving a
threshold that tight belongs in its own change with its own measurement; doing it inside the 1M
recalibration would make both unmeasurable.

### An internal inconsistency in this file, named rather than resolved

As *fractions*, the untouched 200K profiles are far more permissive than the 1M ones this ADR sets:
`sonnet_200k` hard is 70% of its window and `haiku_200k` hard is 65%, against `opus_1m` at 40%. As
*absolute tokens* the ordering reverses — 400000 is 2.9x `sonnet_200k`'s 140000. Whether context
degradation tracks the fraction of the window or the absolute token count is precisely the
unmeasurable question above, and this config currently answers it **differently in the two window
classes**. That is a real inconsistency. It is recorded rather than papered over, and it is a second
reason the 200K pair should be revisited on its own evidence rather than adjusted to match a 1M
argument.

### Carry-forward — the handoff template was not re-cut

A third surface carries the same literal, and this slice could not edit it. Protocol step 5 orders the
handoff artifact be written **from** `docs/templates/handoff-template.md`, and that template's first
field reads, measured on disk 2026-08-08:

> `<3–5 lines: the arc in flight, where we are, why a wrap-up fired (soft/hard, profile, ~tokens).>`

So the protocol simultaneously forbade the figure in what the model writes (step 1: the rule "holds
for every step below too … the readout is not yours to fetch") and handed the model a form whose
first field asks for it, four steps later. Measured, this propagates exactly like the skill:
`scripts/lineage/manifest.py` lists `docs/templates/` in `FRAMEWORK_PATHS`, and
`C:/Work/AI/CovenRPG`, `C:/Work/AI/VerificationPortal` and `C:/Work/AI/marrow` each already hold one
occurrence (`agentic_journal` has no copy of the template).

**What survives the literal, stated exactly** (corrected round 4 — an earlier wording claimed the
template was the *only* surviving instance outside passages quoting it as deleted, which was wrong
about the file this slice itself edited). Counted on disk 2026-08-08, `~tokens` survives in four
places, and they are not all the same kind of thing:

| where | what it is |
|---|---|
| `docs/templates/handoff-template.md` (1 occurrence) | a **live request** — a field asking its writer to supply the figure |
| `.claude/skills/wrapping-up-sessions/SKILL.md` (**2 occurrences, both live**) | live text, but **quoting the template's field in order to forbid filling it** — protocol step 5, and the `## Related files` note flagging the template as stale |
| this ADR, and `tests/test_context_sensor.py` | the record and its pins: quoted instructions, detector fixtures, mutation cases |

So the accurate claim is narrower and still the point: the template is the only place where the
literal functions as a **request**. The two in `SKILL.md` are the point-of-use fix described below —
they exist *because* the template still asks, and option 1 removes them along with the field.

**What was done, and why that is not the whole fix.** The template was outside the authorized file
scope, so the contradiction is resolved at the **point of use** instead: step 5 now names the field,
tells the model not to fill it, and says the template is stale on that point rather than
authoritative. That is defensible on its own terms — step 5 is the nearer and more explicit
instruction, and the developer-facing artifact was never the surface this amendment objected to. It
is not equivalent to striking the field, because a derived project reading the template alone still
sees the request.

**The obligation.** A slice with `docs/templates/` in scope must close it one of two ways:

1. **Strike `~tokens`** from the field, leaving `(soft/hard, profile)`. Then step 5's reconciliation
   clause becomes redundant and may be dropped with it — `TestHandoffTemplateAgreesWithTheProtocol`
   goes vacuous along that branch by construction, and says so in the test body.
2. **Keep the number** in the artifact — permissible, it is developer-facing — and then state in
   step 5 **where the model obtains it**, because the guard no longer supplies it and the page
   forbids hunting for it. There is currently no such source; inventing one is a decision, not an
   edit.

Doing neither is the state this section exists to make unrepeatable.
`TestHandoffTemplateAgreesWithTheProtocol` fails whenever the template asks for a figure and no
instruction step rules on it. Measured 2026-08-08 against the wording that shipped in round 2, that
assertion trips; against the wording now in step 5, it passes.

## Alternatives Considered

- **Amend ADR-0018 in place (what S5b did).** Rejected — this is the defect being fixed. Principle #4:
  ADRs are superseded with a reference to the replacement, never rewritten. Deleting the twelve lines
  containing the objection also destroyed the only written argument *against* the new number, which is
  the specific thing a decision record exists to preserve.
- **Keep 400000 / 500000 (S5b's values) and rebut the objection in prose.** Rejected. Answering an
  unrebutted cost objection with a better-worded paragraph and the same number is what this slice was
  convened to stop. Under the 2026-08-08 re-anchoring 500000 is also above `3 x UNIT` (450000), the
  ceiling the documented anchor supports.
- **Take a larger multiple of the anchor (`4 x UNIT` -> hard 700000).** Rejected. It clears every
  mechanical constraint, and that is precisely why it is the wrong test to pass: the mechanical floor
  is not the binding consideration, and it maximizes exposure to the cost objection — which, since
  disposition 3 was withdrawn, is the only objection left standing.
- **Leave the caps at 140000 / 180000.** Rejected. It produced a measured harm (a hard stop at ~19%
  occupancy, 2026-08-07), and it is barely above the point at which Anthropic's own stack merely
  *starts* summarizing. "Conservative" is not free: it discards a whole session's worth of context
  every session, a certain and continuous cost, and — now that the quality justification is withdrawn
  — it buys nothing measurable in return.
- **Go lower still (e.g. hard 250000).** Rejected, but it is the closest call here, and the 2026-08-08
  amendment makes it closer rather than further: with disposition 3 withdrawn, the cost objection is
  unopposed by any counter-evidence, and cost argues downward. It was not taken because 250000 is not
  a clean multiple of the documented anchor and would need its own justification, and because
  `2 x UNIT` is already the smallest multiple that clears the demonstrated harm by a full `RUNWAY`.
  Per-turn cost telemetry (ADR-0020 A1) is the evidence that would settle it.
- **Percentage-only thresholds on 1M.** Rejected, unchanged from ADR-0018 — see disposition 1 above.
  This ADR does not reopen it.
- **Defer until quality-vs-occupancy is measured.** Rejected as the status quo in disguise: deferring
  keeps 140000/180000 live, and that number is the one with a demonstrated failure. The 2026-08-08
  amendment strengthens this: the measurement would now settle a question no live number depends on.
- **Delete the wrap-up nudge entirely rather than de-numbering it.** Rejected — see *The countdown the
  model was being shown*. It reads the reference's "avoid showing counts" as "say nothing", and it
  trades a documented nudge-quality problem for an undocumented thread-loss problem, which is the
  worse of the two.

## Consequences

### Positive
- The 1M classes stop being calibrated against a 200K-era number; a frontier session gets roughly 3x
  the usable context it got under the conservative floor (soft 100000 -> 300000).
- **The framework stops telling every long session it is running out of room.** The model-facing
  countdown is gone, which removes a documented cause of premature wrap-up — and removes it before
  the behavior propagates to the four downstream projects. Both surfaces are covered: what the guard
  *hands* the model (`_nudge_text`) and what the wrap-up protocol *orders it to say* (SKILL.md step
  1). The second was found in round 3, after the first had shipped.
- **The class is guarded, not just the instance.** `TestWrapupProtocolOrdersNoFigureRecital` reads
  the wrap-up skill's instruction text and fails on any *reworded* order to emit an occupancy figure,
  not only on the literal one that shipped. Prose in a CORE skill is an instruction; it now has a
  test, which is what the two previous point fixes to that same page lacked.
- The cap values now have a written derivation that is *executed*: `TestCapRationaleIsRecorded` parses
  the `CAP <profile>: soft N / hard M` lines out of both this ADR and the config and compares them
  against what `resolve_threshold` actually computes. The three cannot drift apart silently.
- The anchor is now a number Anthropic publishes rather than a third-party benchmark nobody here can
  rerun, so "what would change this" is answerable by reading a document.
- ADR-0018 survives intact, objection included, and a reader can see the argument that was made
  against the number now in force. `test_adr_0018_was_not_amended_in_place` fails if anyone edits it
  back.

### Negative / limitations (honest)
- **The values did not move when their justification did.** The 2026-08-08 re-derivation was built
  after the fact and lands exactly on the numbers already in force. That is disclosed in the
  derivation and is the single largest reason to distrust this record: a reader is entitled to read
  it as a rationale fitted to a number rather than a number derived from a rationale.
- **`2 x UNIT` is still a choice.** The anchor is documented; the multiple is not. Nothing rules out
  `1.5x` or `3x`.
- **The cost objection is upheld, not solved, and is now unopposed.** Running to 400000 costs more per
  turn than running to 180000, and with disposition 3 withdrawn there is no longer any counter-claim
  arguing for the higher cap. The honest position is that the cap is *higher than the only surviving
  objection would prefer*, justified by continuity rather than by cost.
- **Removing the model-facing numbers is untested against behavior.** That the countdown causes
  premature wrap-up is Anthropic's finding, not this repo's; that removing it helps is inferred. What
  is verified here is only that the figures are gone and the checkpoint still fires.
- **One constant now speaks for four profiles that are not alike.** De-numbering bought
  profile-independence and paid for it in precision: the nudge cannot say "you have 430000 tokens of
  room" to `opus_1m` and something soberer to `sonnet_200k`, so it says only what is true of both.
  The first version of this amendment ignored that and shipped a sentence false at 200K (recorded
  above). The tightest-profile test is a floor, not a fix: if the 200K class is ever revisited on its
  own evidence, the honest options are a profile-aware *phrasing* — never a figure — or accepting
  that the weakest true claim is all the model gets.
- **Direction of error is asymmetric and was chosen deliberately.** Erring conservative wastes context
  every session — certain, continuous, and demonstrated. Erring permissive risks a session dying
  without a handoff — rarer, but the worse failure. The 430000-token spare margin, the 100000-token
  soft-to-hard runway, and `TestHandoffHeadroomInvariant` are what buy down the worse failure.
- **This ADR carries no Layer 1 discussion.** See `discussion_provenance` in the frontmatter.
- **ADR-0018's `status:` is not flipped.** ADRs are immutable to the agent; recording the supersession
  one-directionally here (`supersedes: ADR-0018`, scoped by `supersedes_scope`) is the agent-side half,
  and the frontmatter edit on ADR-0018 is a developer action. Same constraint ADR-0032 recorded for
  ADR-0031.

### Neutral
- `config/model_context_profiles.yaml`'s `CAP RECALIBRATION` block is rewritten to carry these numbers
  and to cite this ADR as its governing record.
- The realised correction for an unmapped frontier model changes from ~4.0x to ~3.0x on soft
  (100000 -> 300000); the config's `MEASURED COST` block is updated and is checked against the resolver
  by `TestConfigCostClaimIsMeasured`.
- `.claude/skills/wrapping-up-sessions/SKILL.md` is retargeted to this ADR. It previously cited
  "**ADR-0018, Amendment 2026-08-07**" — an amendment that **does not exist**: it was the in-place
  rewrite of an immutable ADR, and it was reverted. The citation pointed at deleted text. Fixed to
  this record, by stable section anchor rather than by line number. RETIRED from that page at the
  same time: its claim that the cap sits at "the bottom edge of the researched
  effective-working-fraction band", which nothing supports.

## What would change these numbers

Named triggers, not "revisit periodically":

- **The documented anchor moving.** If Anthropic changes the server-side compaction default trigger
  off 150000, `2 x UNIT` changes with it and the whole derivation must be re-run. This trigger
  replaced "new research on context rot" — it is checkable against a published document.
- **Per-turn cost telemetry (ADR-0020 A1) showing the 300000–400000 band costs more than the context
  it buys.** That is disposition 2's evidence arriving, and it would push the caps back down. With
  disposition 3 withdrawn it is now the only live evidence that argues the caps *down*.
- **`auto_compact_fraction` moving off 0.83** (a harness change). Re-run the headroom arithmetic;
  `TestHandoffHeadroomInvariant` fails first, which is the point.
- **`BUILD_STATUS.md` or `handoff-template.md` growing.** The cost is re-measured from them at test
  time, against **two** tripwires. The early one fires when the live four-component subtotal reaches
  the stated `HANDOFF` total of 22687 (currently 20739 — about 6800 characters of `BUILD_STATUS`
  growth away) and asks only for a re-measurement. **This trigger has now fired**: it fired on
  2026-08-09 and produced the round-5 re-measurement recorded above, which is the clause working as
  written rather than a hypothetical. The floor is the 25000 `RESERVE`, which every
  profile's headroom is sized against and which cannot be raised without re-checking all four.
- **Anthropic publishing an actual degradation threshold**, or a quality-vs-occupancy measurement in
  this repo. Either **reopens** disposition 3, which is currently withdrawn for want of support in
  either direction.
- **Any resolution of the fraction-vs-absolute-tokens inconsistency** named in the config.

## Linked Records

- Superseded (cap values only): `docs/adr/ADR-0018-model-aware-session-wrapup.md`
- Live numbers + derivation: `config/model_context_profiles.yaml`, `CAP RECALIBRATION` block
- Model-facing nudge text (figure-free): `src/context_sensor.py::_nudge_text`
- Surface split (model vs developer): `.claude/hooks/context_guard.py` /
  `.claude/hooks/context_statusline.py`
- Binding tests: `tests/test_context_sensor.py::TestCapRationaleIsRecorded`,
  `::TestWrapupCapRecalibration`, `::TestHandoffHeadroomInvariant`,
  `::TestModelFacingNudgeCarriesNoFigures`, `::TestNoQualityCliffClaimSurvives`,
  `::TestWrapupProtocolOrdersNoFigureRecital`,
  `::TestHandoffCostDerivationIsSelfConsistent` (the itemization adds up to every total
  derived from it, in both documents, and the three instalment enumerations agree with
  each other), `::TestEveryRestatementOfTheDerivedTotalIsBound` (no free literal for a
  figure the itemization already derives, and every `Nx HANDOFF` ratio is a division the
  test performs)
- Retargeted by this amendment: `.claude/skills/wrapping-up-sessions/SKILL.md`
