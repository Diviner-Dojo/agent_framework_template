---
adr_id: ADR-0031
title: "Reconcile v4 onto main as a judgment call, recorded as one; instruments are a third category"
status: proposed
date: 2026-08-05
decision_makers: [developer]
discussion_id: DISC-20260806-055721-v4-reconciliation
spec_id: SPEC-20260805-210524
supersedes:
extends: [ADR-0030]
scope: framework
risk_level: critical
confidence: 0.72
tags: [v4, reconciliation, scaffolding, governance, instruments, judgment, opus-5, measurement, falsifiers]
---

> **rev 4.** Folds Steward gates 2 (REVISE, 0.85) and 3 (REVISE, 0.86 — loop closed, no further
> Steward cycle required; remaining items routed to `/review`). Adds the authoritative
> seven-row principle table, splits main #3's retirement into *posture* (retired) and
> **plurality** (retained as a dispatch concern, now in Appendix A and AC7), repairs a
> structurally broken decision table that had orphaned the #8 row out of the record, and
> re-points principle citations to the merged numbering after rev 3 left them half-converted
> and ambiguous. **Gate status: all Steward blockers cleared; `decision_makers` remains
> `[developer]` because the Principle #7 developer approval of Decision 6 and the AC7
> dispositions has not yet occurred — the Steward gate does not substitute for it.**
>
> **rev 3.** Folds the Steward gate (REVISE, conf 0.82). Adds Decision 6 (the constitution,
> reconciled per-principle with the developer → seven principles), Appendix A (the closed
> enumeration AC13 was missing), the discriminating instrument bound R-B4, and a benefit
> restated in a unit `PHILOSOPHY.md` does not disclaim.
>
> **rev 2.** Rev 1 of this ADR claimed the reconciliation was *evidence-gated*. A four-reviewer
> panel established that it was not, and that two of its load-bearing measurements were wrong.
> Rev 2 removes the evidence framing rather than repairing it into a weak experiment, on the
> developer's decision. `decision_makers` lists only the developer; the Steward gate has not
> yet run, and rev 1's frontmatter asserted a consensus that did not exist.

## Context

Two framework lines diverged. Private `main` (v3.5) continued forward — a per-call cost/cache
sensor (Wave 1), a green-able quality gate with stack profiles and a debt baseline (Wave 2),
and a machine-readable education-gate registry (RepoCademy Phase 0, ADR-0029). In parallel, an
offline session rebuilt the framework from empty against the *public* repo's July state,
deleting ~90% of the instruction surface on the thesis that scaffolding built for weaker models
now degrades frontier ones (ADR-0030, formerly numbered 0029).

Both are post-review artifacts. They collide on five surfaces — the quality gate, the Stop hook
carrying the cost sensor, an ADR number, education, `.claude/settings.json` — and on a sixth
that rev 1 missed entirely: 10,297 lines of `scripts/` present on main and absent from v4,
including the whole telemetry subsystem.

The external record supports the thesis specifically: Anthropic deleted >80% of Claude Code's
system prompt for Opus 5 / Fable 5 with no measurable eval loss, and Cherny's method is an
ablation — delete, add back line by line, measure — on a recurring cadence. What that guidance
keeps is equally specific: "safety and permissions and static analysis," and external
deterministic verification, as opposed to instructions telling the model to self-verify.

**But the method does not transfer.** Anthropic ablated their own system prompt against
internal eval suites at product scale. This repo would be ablating a third-party layer stacked
on an already-ablated prompt, with one developer and no eval infrastructure. That asymmetry is
the reason for this ADR's central procedural decision.

## Decision

**Reconcile onto the v4 base, and record the decision as a judgment call rather than a
measured outcome.**

### 1. v4 is the base — a judgment informed by merge surface

Against the true common ancestor `af3fd10`, v4's delta to `scripts/quality_gate.py` is
**+123/−5**; main's, including Wave 2, is **+929/−50**. v4's delta is ~7.5× smaller, so
v4-as-base minimises the merge surface.

That is the whole of the claim. Rev 1 stated **+50/−5**, measured against `e4c8d73` — the
public upstream, which is *not* an ancestor of `main` — while asserting it was against the
common ancestor. Rev 1 also called the two deltas "orthogonal"; they overlap, and both trees
independently added a `check_promotion_backlog()` absent from the ancestor, which is a real
collision requiring an explicit decision.

Rev 1 built a rhetorical claim on the wrong number — *"the strongest practical argument for
main-as-base does not survive being measured, which is itself the first application of this
ADR's method."* That sentence is withdrawn. Base selection is judgment informed by a
measurement, not a decision produced by one.

### 2. Instruments are a third category

ADR-0030 sorts every file into **scaffolding** (delete) and **governance** (keep). That binary
is what let the rebuild sever `record_yield.py`, `ingest_token_usage.py`, and the `briefings`
outcome column — the things that could have told anyone whether the rebuild worked. All were
caught at review, not by the test.

| Bucket | Test | Disposition |
|---|---|---|
| Scaffolding | Tells the model *how to think* | Delete |
| Governance | Constrains *what may happen to the human* | Keep; prefer code over prose |
| **Instruments** | Tells *us* whether a deletion was right | **Keep** |

Rev 1 bounded this with "an instrument must name the question it answers." The panel correctly
identified that as a documentation requirement rather than a test — almost any file can be
given a plausible-sounding question during the restoration that wants to keep it. The bound is
tightened: the question must be **traceable to a pre-existing artifact** (an ADR, a CLAUDE.md
pointer, a REV finding), the instrument must **arrive with its test module**, and the whole
classification is **reviewed by an independent context**.

Honest correction to rev 1's supporting examples: `audit_calibration.py` fits ADR-0030's
*existing* governance test. Its deletion was a per-directory sweep — a process failure, not a
taxonomy gap. The genuine third-bucket cases are the three pure-measurement items above.

### 3. Enforcement gets the benefit of the doubt, in both directions

Rev 1 wrote this asymmetry one-directionally, guarding main's enforcement on the way in. v4 is
the base and has *stronger* protection in at least one place: `.claude/hooks/` is in
`PROTECTED_PATTERNS`. The reconciliation's task is writing five hook files into that directory,
so the cheapest unblock is deleting the pattern — reverting the B5 fix precisely when six hook
paths are dangling.

### 4. Measurement is continuous, and gates nothing

**This is the change rev 1's review forced.** Rev 1 called itself evidence-gated. The panel
established that no acceptance criterion was contingent on the proposed measurement; that the
chosen A/B task was not equivalent across trees (three of four files differ; v4 had already
fixed a bug that makes those tests skip on main); that the v4 arm had no instrument to measure
with at all; that neither tree's gate measures the task's coverage, so "gate-green" was
undefined; and that three of four metrics were undetectable at N=1.

Most importantly: the measurement site was wrong. This framework is a hub, and its artifacts
are properly judged against derived-project usage — a standard already recorded in this repo —
not against template-local work.

Repairing that into a defensible experiment would cost weeks and still most likely return
"inconclusive," which buys false confidence rather than information. So the framing is dropped
instead of patched.

What is kept is the **sensor**, running continuously and gating nothing, plus **named
falsifiers** so this decision stays revisable:

- **F-A** Subagent-call share does not fall materially after the merge — v4's core
  productivity claim would be wrong.
- **F-B** Deferred briefings accumulate faster than v3.5's deferred education gates — the
  leaner education path would be degrading the human's understanding.
- **F-C** A derived project's `/apply-framework` run surfaces regressions template-local work
  did not — this is the correct measurement site, reached at P6.
- **F-D** No reduction in output tokens per session at comparable work over a trailing quarter.

### 5. Model-facing scaffolding and human-facing handholding are separate surfaces

**Developer requirement, 2026-08-05.** The framework must work well with frontier models
*and* keep the developer able to hold it in their head, across an attention profile that
oscillates between piercing focus and needing substantial hand-holding.

Rev 1 treated this as a tradeoff. It is not one. Two distinct surfaces were conflated:

- **Model-facing scaffolding** — collaboration modes, exploration dials, reasoning
  sequences, mandated self-verification. Delete; deleting it is what un-inhibits the model.
- **Human-facing handholding** — walkthroughs, the education gate, briefings, plain-language
  summaries, pacing. Keep; no model capability replaces it, by the same argument ADR-0030
  uses for code that persists state past the context window.

Every deletion candidate must therefore answer **which surface does this serve** before the
§2 bucket test is applied. This carries acceptance criteria (AC12 no net thinning, AC13
explain-back), not a caveat.

The follow-on it implies — **capacity-adaptive briefing depth**, where change-risk is the
floor rather than the answer and depth is adjustable on request in either direction — is
*new work*, not reconciliation. It is committed and sequenced immediately after merge and
**before distribution to derived projects**, on the reasoning that distribution is when the
developer most needs to hold the system in their head and is the point of highest
irreversibility. Falsifier F-B is its early-warning signal.

### 6. Constitutional reconciliation — per-principle, developer-approved

**This was the Steward gate's first blocking finding, and it is the most important thing
rev 2 missed.** Both trees edited the constitution — v4 `CLAUDE.md +120/−109`,
`PHILOSOPHY.md +102/−21`; main `+1/0` and `+33/0` — and taking v4 as the base would have
silently reduced **nine Non-Negotiable Principles to six**. Rev 2 never named `CLAUDE.md` or
`PHILOSOPHY.md` in any section, including out-of-scope. A constitutional amendment was
arriving as a side effect of base selection, which is exactly what CLAUDE.md's Framework
Evolution clause routes through the Steward and human approval (merged Principle #6).

Four principles differed. Each was put to the developer individually on 2026-08-05 and
decided:

| Principle (main numbering) | v4 disposition | **Developer decision** |
|---|---|---|
| **#9 Clarify before acting (95% rule)** | deleted; replaced by "make routine judgment calls yourself" | **KEEP, and AMEND.** Also the developer's standing global instruction, marked mandatory. Rationale: asymmetric cost — over-caution costs a few questions and is switched off with one word ("proceed"); under-caution costs confidently building the wrong thing, which happened twice in the session that produced this ADR. **Amendment (developer, same session):** the principle obliges reaching confidence, *not* asking. Asking spends the developer's attention, which for an ADHD-oscillating gatekeeper is the scarce resource the framework exists to protect — so knowledge of the developer and the project record closes the gap first, and asking is reserved for genuine forks. **The "name what you are extrapolating from" clause is load-bearing, not decorative:** it is what keeps evidence-based extrapolation from becoming confident hallucination, and it is the only thing that makes a wrong inference visible in one line rather than three hours later. A silent inference is the failure mode this principle exists to prevent, wearing the amendment as cover. |
| **#6 Education gates before merge** | weakened to "understanding is offered… you can always say skip" | **HYBRID.** v4's offered-and-skippable briefing is the default for everyday work — more humane and more honest, and main's blocking version demonstrably produced a month-long invisible deferral backlog. **Skip is unavailable for two named classes: changes to the framework's own governance/safety mechanisms, and distribution to derived projects.** These are where human approval (main #7 / merged #6) would otherwise become a rubber stamp. |
| **#3 Collaboration precedes adversarial rigor** | deleted | **RETIRE** — with the plurality half explicitly preserved elsewhere, see below. Model-facing scaffolding by Decision 5's test: it instructs interaction *style*, not what may happen to the human. The anti-finding-inflation half is superseded in mechanism by the retained `severity-calibration` skill (code rather than prose), and v4's lens-based agent design makes "posture" unparseable. |
| **#8 Least-complex intervention first** | deleted | **MOVE, not delete.** Retired from `CLAUDE.md`; the value is added to `PHILOSOPHY.md` paired with the raft passage. The raft passage covers *removal* ("set the raft down, gladly and often") but is silent on *growth*; #8 is the growth-side brake and retiring it outright leaves nothing constraining how new complexity enters. Recorded confidence ~0.7 — the case for outright retirement is respectable, and this principle was in force throughout the growth to ~9,000 lines that it existed to prevent. |

**Closing the #3 retirement (Steward B3).** The principle carried two things, and only one is
scaffolding.

- *Posture* — "collaboration is the default stance" — is retired. That is the scaffolding half.
- **Plurality** — *several* independent contexts, not one — is **not** retired, and is not
  covered by merged Principle #3, which requires only a separate context. This matters
  concretely: the review that produced this ADR used **four** reviewers plus a Steward, and the
  two findings that mattered most (the wrong merge-base, the constitution being silently
  rewritten) were each caught by exactly one of them. A single reviewer would have missed one or
  both. Meanwhile v4's `CLAUDE.md` instructs *"Prefer one agent over several."*
  **Disposition:** plurality is retained as a *dispatch* concern, not a principle — the panel
  size for critical-risk changes lives in `/review` and the `selecting-review-gates` skill, both
  of which AC7 must disposition. v4's "prefer one agent" guidance is scoped to ordinary
  delegation and must not be read as governing review panels. Recorded so the merged tree cannot
  silently become single-reviewer.
- **`PHILOSOPHY.md`'s refusal list** pairs "collaboration before adversarial rigor" against the
  extraction mode *"authoritative single-source answers."* That pairing is re-pointed to the
  plurality disposition above rather than deleted; the refusal survives the principle's
  retirement. AC14 covers it.

**Resulting merged principle list — the authoritative numbering.** A construction rule is not a
list; AC14 requires re-pointing citations to "the merged numbering," so the merged numbering is
written out here and this table is the referent:

| # | Principle | Provenance |
|---|---|---|
| **1** | **Reasoning is the primary artifact.** Code is output; every significant decision traces to the discussion that produced it. | unchanged both trees |
| **2** | **Capture is automatic.** Enforced by scripts and hooks, not by instruction. A decision that exists only in a context window did not happen. | unchanged both trees |
| **3** | **The generator is never the sole evaluator.** Independent review means a *separate context* that did not see the reasoning behind the code — an information property, not a personality. | main #4 / v4 #3 |
| **4** | **ADRs are never deleted.** Superseded, with a reference to the replacement. | main #5 / v4 #4 |
| **5** | **Understanding before merge — offered, not withheld.** Briefing depth is sized to risk and may be declined, and the decline is recorded rather than judged. **Skip is unavailable for two classes: changes to the framework's own governance or safety mechanisms, and distribution to derived projects.** | main #6 / v4 #5, **hybridised here** |
| **6** | **Curated memory needs human approval.** Nothing reaches `memory/` automatically. | main #7 / v4 #6 |
| **7** | **Clarify before acting (95% rule).** Reach ≥95% confidence on intent **and** scope before a plan, code, or any substantive action. **Close the gap from accumulated knowledge of the developer and the project record first; ask only when the remaining uncertainty is a genuine fork evidence cannot resolve. When extrapolating rather than asking, name what you are extrapolating from.** Mandatory unless the developer explicitly overrides ("proceed" / "just do it"). Micro-fixes exempt. | main #9, **restored and amended here** |

Retired: main #3 (collaboration precedes adversarial rigor) and main #8 (least-complex
intervention — relocated to `PHILOSOPHY.md`, not lost).

The hybrid at #5 is what gives AC13 something to stand on: without a class where skip is
unavailable, an acceptance criterion promising "never waived" is contradicted by the base
framework's own text and is decoration.

**Count strings must be corrected in the same change.** Main's `PHILOSOPHY.md:76` and `:99`
already say *"the eight principles"* while `CLAUDE.md` carries nine — a live, undetected drift
that proves these strings rot silently. The merged tree says **seven**, everywhere, and AC14
covers the count strings explicitly.

Two consistency defects the Steward found must be fixed in the same change: v4's
`PHILOSOPHY.md` refers to "the six principles" while the surrounding text still reflects the
older list, and internal principle-number citations (including in ADR-0031 and
REV-20260805-213438) must be re-pointed to the merged numbering.

### 7. ADR renumbering

v4's `ADR-0029-framework-v4-scaffolding-removal` becomes **ADR-0030**. main's ADR-0029
(RepoCademy) keeps its number — older, already merged, and referenced by
`docs/education/CONTRACTS.md`, the versioned contract an external repo builds against. Breaking
a published cross-repo contract to save internal edits is the wrong trade. The renumbering
touches 23 files excluding sealed discussions; rev 1 said 13.

## Alternatives Considered

**Repair the evidence gate rather than drop it** — pre-register a threshold and reversal path,
move the measurement to a derived project, redesign as a counterbalanced sub-task battery
(N≈5–8 paired). Rejected on cost/benefit: weeks of delay for a design whose honest ceiling is
still "detects a large effect or reports inconclusive," while the v4 branch goes further stale.
Recorded because it is the option a better-resourced team should take.

**main as the base, applying v4's deletions incrementally.** Rejected. It optimizes toward the
existing shape — ADR-0030's objection to consolidation-in-place, still correct — and the merge
surface is ~7.5× larger.

**Merge first, compare trailing windows afterward.** Rejected. It permanently confounds the
framework change with the model change. ADR-0030 already records the loss of v3-vs-v4
comparability as a real cost; the falsifiers in §4 are the cheap partial recovery.

**Keep both frameworks and choose per project.** Not considered in rev 1; raised by review.
The repo has a precedent (`config/gate_profiles.yaml` selects behaviour per profile), and a
framework-version profile would let real usage decide over months. Rejected for this cycle
because maintaining two framework lines across four repos is a larger ongoing cost than the
reconciliation, and the developer is a single maintainer. Worth revisiting if P6 goes badly.

**Pilot v4 on one derived project first, leaving the template on v3.5.** Not considered in
rev 1; raised by review, and the strongest of the unconsidered alternatives, because it puts
the decision where the evidence actually is. Rejected on ordering risk: distributing a
mid-reconciliation framework to a live project inverts the back-out story, and `/apply-framework`
is itself under test. Retained as the P6 design — F-C is exactly this question, asked later.

**Keep ADR-0030's binary taxonomy and rely on review to catch over-deletions.** Rejected. It
worked once, at the cost of nine blocking findings, and depends on a reviewer noticing an
absence — the hardest thing to notice.

**Delete the wrap-up/context-sensor machinery entirely, as v4 did.** Rejected; see
Consequences. The failure was miscalibration, and the remedy for a miscalibrated instrument is
calibration.

## Consequences

**A concrete instance, found during this work.** `config/model_context_profiles.yaml` mapped no
Claude 5 model, so every current-generation model fell through to the conservative default and
was measured against a 200K window. Observed live: a hard "stop and hand off" order at ~131K
resident context — roughly **13% of the actual 1M window, a ~5× premature wrap-up.** It fired on
every session, on every frontier model, in this repo and in all three derived projects, and
nothing reported it, because a fail-safe default is silent by construction.

This is the specimen case for the third bucket. The instrument was correct when written
(2026-05-23, against Opus 4.7), became a large invisible tax as models moved, and v4's
disposition — delete the protocol wholesale — would have removed the tax along with the ability
to detect the next one. Fixed by four map entries. **Carried:** even corrected, the caps bind at
14%/18% of a 1M window and are plausibly still conservative.

**What this buys, in a unit PHILOSOPHY.md does not disclaim (M8).** ADR-0030 states its benefit
as *"the instruction surface drops from ~9,000 lines to under 900"* and *"`CLAUDE.md` goes from
17KB to roughly 5KB"* — against `PHILOSOPHY.md`'s own standard: *"We measure what matters: **not
lines of code**, but clarity of thought."* Reporting a line count as the benefit, in a framework
whose constitution disclaims line counts, is the same category error as calling an audit trail a
lock.

The mission-aligned unit is already in the developer's own words: **the ability to keep the
framework in their head.** Restated: this reconciliation succeeds if the developer can explain
the governance mechanisms in Appendix A without reference material, and fails if they cannot —
regardless of token savings. **AC13 is that measurement**, which is why it is named the
criterion that outranks the engineering, and why the Steward was right that it had to be made
capable of failing before that claim meant anything.

Line count is a proxy the model benefits from. Explain-back is the thing the framework exists
to protect.

**What this costs — stated plainly.** This is a judgment call. The framework's own preference is
for decisions traceable to evidence, and this one is traceable to reasoning, external reports
this repo cannot reproduce, and a merge-surface measurement that bears on *how* to merge rather
than *whether* the thesis is right. Anyone reading this later should treat "v4 is better" as an
unverified claim that the falsifiers in §4 are designed to test, not as a finding.

**The honest account of rev 1.** Rev 1 dressed this judgment in evidence language, and the panel
took it apart. Two of its numbers were wrong because they were asserted from documents rather
than produced by a command — in a document whose argument was that claims should be measured.
That failure mode is worth more than the numbers: the generator was confident, internally
consistent, and wrong, and only an independent context that had not seen the reasoning caught
it. That is **merged Principle #3** — the generator is never the sole evaluator — doing exactly
what it exists for, and it is the strongest evidence in this whole record that the governance
layer should not be thinned.

Attribution matters here, because rev 3 originally cited this as "Principle #3" under *main's*
numbering, where #3 is the posture principle this same ADR retires — a document citing as its
strongest evidence a principle it deletes two sections earlier. The catch belongs to
independent-context review, and specifically to **plurality**: four reviewers found different
things, and the two findings that mattered most — the wrong merge-base and the constitution
being silently rewritten — were each caught by exactly one of them. Merged #3 requires only
*a* separate context, so plurality is dispositioned separately in Decision 6 rather than
assumed.

**A tension that turned out not to be one.** Rev 1 recorded token cost and human legibility as
an unresolved tradeoff. The developer's own statement of the requirement resolved it, and the
resolution is now Decision item 5: **model-facing scaffolding and human-facing handholding are
separate surfaces.** Instructions telling the model how to think are what §2's evidence says to
delete; documents explaining the system to the developer are not the same artifacts, share no
code, and do not trade off. They looked like one dial only because ADR-0030 deleted ~90% of
everything at once and both were inside that 90%.

What remains is narrower and real: between merge and the follow-on (SPEC §9), briefing depth is
still derived from change-risk alone, so a high-risk change landing on a low-capacity day is
under-served. The developer's attention oscillates; the framework can neither detect that nor
ask. Interim mitigations are AC12 (no net thinning of the human-facing surface) and AC13
(explain-back at the education gate), plus the standing rule that on a low-capacity day the
answer is never "skip the gate" but "hold more of the thread."

**AC13 was decoration in rev 2, and the Steward proved it.** It could not fail: it named no
enumeration of "retained governance mechanisms", no mechanism enforced it, the base
framework's own text said skip is always available, and the repo's only education instrument
is multiple-choice recognition rather than production. A consequence clause that named no
action ("this reconciliation was a mistake") is a sentiment, and sentiments lose to delivery
pressure.

The repair, decided with the developer 2026-08-05, changes where the burden falls. The first
draft said: a mechanism the developer cannot explain is removed. That was wrong, and the
reason it was wrong is the requirement in Decision 5 — **the explain-back signal varies with
the developer's attention state.** Using a variable signal to trigger the irreversible removal
of a safeguard would let a scattered day delete a security control, in a framework being
redesigned precisely to accommodate that variance.

The adopted rule inverts the burden: **a mechanism that cannot be explained is a defect in the
mechanism, not in the developer.** It is simplified, or re-documented, or explicitly retired by
a recorded decision — never automatically. Unresolved items block promotion and distribution,
the two classes where Decision 6 makes skip unavailable, and nothing else.

This makes "the developer cannot follow this" an alarm about framework complexity rather than
a judgement about the developer — which is the retired main Principle #8's brake, doing work in its relocated
home in `PHILOSOPHY.md`.

**What we will wish we had known.** Whether a single-developer framework can ever generate
enough signal to answer "was that deletion right?" If the falsifiers stay ambiguous, the honest
conclusion is that this framework's deletion decisions are judgment calls — which is fine, as
long as they are labelled that way and not dressed as measurements. Rev 1 is the cautionary
example.

## Appendix A — Retained governance mechanisms (the AC13 scope)

AC13 requires the developer to explain, in their own words, why each retained governance
mechanism exists. That criterion is unevaluable over an undefined set, which is why the
Steward rated it decorative. This is the **closed enumeration**. Anything not on this list is
outside AC13; adding to the list is itself a governance change under Decision 6.

Grouped by what they protect. The grouping is the teaching order, not a ranking.

**1. The human stays the decision-maker**
| Mechanism | What it prevents |
|---|---|
| **Principle #7** — clarify before acting (95% rule) | the agent building the wrong thing confidently, on an assumption never surfaced |
| **Principle #6** — curated memory / Layer 3 promotion needs human approval | the framework absorbing its own conclusions without assent |
| Education gate hybrid — skip unavailable for governance changes + distribution | merged Principle #6 (curated-memory) approval degrading into a rubber stamp |
| No push, no auto-merge, no propagation without per-instance confirmation | irreversible outward action taken on standing authorization |
| `apply_assent_preflight` | the Prime Objective's per-instance assent at the cross-repo boundary |

**2. The generator is not the sole evaluator**
| Mechanism | What it prevents |
|---|---|
| Review-existence check in the quality gate ⚠ | code reaching a commit with no independent read — **but the check is date-scoped and satisfied by *any* review dated today, and false-negatives across midnight** |
| **Review plurality** — several independent contexts for critical-risk changes, not one (`/review` + `selecting-review-gates`; AC7) | a single reviewer's blind spot becoming the project's. Retained from main #3 when its posture half was retired: this reconciliation's two most serious findings — the wrong merge-base and the constitution being silently rewritten — were each caught by exactly **one** of four reviewers, and the second by neither the panel nor the generator but only the Steward |
| ADR immutability — superseded, never deleted | the decision record being rewritten by whoever holds the pen |
| Automatic Layer 1 capture | a decision existing only in a context window |

**3. The agent cannot edit its own reward function**
| Mechanism | What it prevents |
|---|---|
| `--rebaseline` developer-consent rule *(audit trail today — see AC2)* | failures laundered into "pre-existing debt" |
| `config/gate_baseline.json` + `gate_profiles.yaml` are review-gated | the same, via the config rather than the flag |
| Quality gate as a deterministic pass/fail before commit | "it looks fine to me" substituting for a check |
| Regression-ledger check | a fixed bug losing its guard |

**4. Untrusted input cannot become an instruction**
| Mechanism | What it prevents |
|---|---|
| ntfy matched-choice-label allow-list (`match_choice`) | an unauthenticated phone message becoming an agent instruction |
| Never print the ntfy topic slug, including on error paths | leaking the only credential the channel has |
| RepoCademy's deterministic ingest as sole writer | LLM-routed phone content reaching Layer 1/2 or flipping a gate |
| `wrap_data_only` + `redact_secrets` | target-repo file contents being read as instructions; secrets entering a written doc |

**5. The agent cannot quietly expand its own permissions**
| Mechanism | What it prevents |
|---|---|
| `PROTECTED_PATTERNS` incl. `.claude/settings.json` and `.claude/hooks/` | a named-but-absent hook path becoming a pre-authorized execution slot |
| Pre-commit gate hook ⚠ | committing without the gate — **but a 5-minute verification cache suppresses the regression-ledger check and review reminder inside that window** |
| Pre-push main blocker ⚠ | pushing directly to a protected branch — **but it matches on command text and permits a `cd`-prefixed push by design** |
| `check_clean_tree` | staging a framework apply over uncommitted work |

**Rows marked ⚠ carry a known weakness, stated here rather than discovered at the gate.** Chief
among them: `PROTECTED_PATTERNS` is enforced only on the `Write|Edit` matcher, so `Bash(*)`
routes around it entirely (§8 R6) — group 5 is materially weaker than it reads.

This disclosure is load-bearing for AC13, not decoration. If the developer explains a row as
written and the row overstates what the mechanism does, they will have correctly explained
something untrue, which defeats the criterion. **An explain-back on a ⚠ row is satisfied only
if the developer can also state the weakness.**

**Not listed, deliberately:** `MAX_AUTO_LAUNCH_DEPTH = 1`. It exists on main
(`src/context_sensor.py`) but not in live v4 code, and §10 declines to re-arm auto-launch as
part of this work — so it is not a mechanism the merged tree retains. Asking for an explain-back
on a cap over an absent capability is exactly the ceremony AC13 should be eliminating. If AC7
restores the capability, the row is added by the amendment path below.

**Where the live list lives, and how it changes.** This appendix is the enumeration *as of
ADR-0031*. Several rows are contingent on acceptance criteria that resolve after this ADR is
written — row 9 on AC2, the ntfy rows on AC3, the RepoCademy row on AC5a, `PROTECTED_PATTERNS`
on AC11. Because ADRs are immutable (Principle #4), the **live** list is maintained in
`docs/education/governance-mechanisms.md`, seeded from this appendix at merge and thereafter the
AC13 referent. Adding to, removing from, or re-scoping a row in that file is itself a governance
change under Decision 6 — which means it is a Principle #5 class where skip is unavailable.

## Related

- ADR-0030 — scaffolding removal (the v4 rebuild; renumbered from 0029 here)
- ADR-0029 — RepoCademy education-gate registry (retains its number)
- ADR-0018 — model-aware session wrap-up (the miscalibrated instrument)
- ADR-0020 / ADR-0013 — telemetry and cost model (the retained instruments)
- ADR-0021 — `/apply-framework` (the distribution path tested at P6, where F-C is answered)
- SPEC-20260805-210524 — the reconciliation spec (rev 3)
- REV-20260728-140000 — the v4 review whose findings shaped the third bucket
- `PHILOSOPHY.md` — the constitution both lines are measured against
