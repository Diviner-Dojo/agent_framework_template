---
meta_review_id: META-REVIEW-20260528
status: final
period: 2026-03-09 .. 2026-05-26 (template-hub telemetry)
denominator: hub-only (template repo; cross-instance view deferred — see scope note)
prior_meta_review: META-REVIEW-20260523 (draft, hub-lens / 4-instance)
specialists: architecture-consultant (sonnet, conf 0.88), independent-perspective (sonnet, conf 0.82)
discussion: DISC-20260529-005306-meta-review-20260528
---

# Quarterly Framework Evaluation (Macro / Double-Loop) — FINAL

## Scope note
Run from the template hub against **hub-local telemetry only** (57 discussions, 377 turns,
2026-03-09 → 2026-05-26), at the developer's direction. The 2026-05-23 draft did the
cross-instance hub-lens pass; this run audits the framework's own capture machinery on the
instance that builds it. **Specialist caveat (independent-perspective), accepted:** the hub is the
*lab*, not a *user*. Several "health" readings below would mean something different on a derived
project. Where a hub reading is expected-for-a-lab (notably low promotion), this report now says so
rather than scoring it as failure. The genuine, scope-independent findings are flagged as such.

## Executive Summary
Two findings survived specialist scrutiny as scope-independent and real; the original headline did
not. **(1) Quality-gate log integrity** — the gate logged `overall: pass` on runs where individual
`checks` report `fail` (the `--skip-*`/verification-cache path). A gate whose audit trail says PASS
while its checks say FAIL is a **Principle #2 violation** (capture cannot be opted out of), not a
cosmetic issue. **(2) The pattern-extraction stage fingerprints review-verdict boilerplate** —
all three "Rule of Three" promotion candidates are truncated verdict headers (`"## Verdict: APPROVE
WITH CHANGES (confidence 0…"`), not reusable patterns. The draft mistook **zero promotion** for
pipeline backpressure; specialists verified it is **correct restraint** — the defect is one stage
upstream, in what the pipeline nominates, not in whether it promotes. Architecture is stable (2/18
ADRs superseded), with one newly-surfaced drift: ADR-0017 was decided, reviewed, and superseded
in a worktree but **never merged to main** — at risk of permanent loss from main history.

## Agent Effectiveness (hub lens)

| Agent | Disc | Unique | Dup | Uniq% | Conf | Calib | Read |
|---|---|---|---|---|---|---|---|
| architecture-consultant | 17 | 9 | 10 | 47% | 0.856 | 0.494 | workhorse; half its findings duplicate others |
| qa-specialist | 14 | 8 | 6 | 57% | 0.858 | 0.441 | solid uniqueness, weakest calibration |
| security-specialist | 14 | 8 | 8 | 50% | 0.881 | 0.490 | highest confidence; 21 of 49 sec findings critical |
| docs-knowledge | 7 | 5 | 2 | 71% | 0.855 | 0.356 | high uniqueness, low dispatch |
| independent-perspective | 6 | 3 | 4 | 43% | 0.808 | 0.508 | anti-groupthink valve; under-dispatched |
| educator | 3 | 2 | 1 | 67% | 0.873 | 0.340 | |
| facilitator | 6 | 1 | 5 | 17% | 0.824 | 0.720 | orchestrator — duplication expected |
| ux-evaluator | 1 | 1 | 0 | 100% | 0.820 | — | hub has ~no frontend; domain-misfit confirmed |
| performance-analyst | 1 | 0 | 1 | 0% | 0.580 | — | lowest confidence, 0 unique — near-dormant on hub |
| steward / history / project | 1–3 | 0 | — | — | — | — | episodic by design |

**Calibration is the weak axis.** Where enough findings exist to compute it (arch, qa, security,
docs, independent), calibration clusters 0.36–0.51 — stated confidence tracks outcome only loosely.
All four reflections this period show **negative confidence_delta** (arch −0.04, docs −0.13, qa
−0.08, security −0.11): on reflection, agents judged themselves *less* right than claimed in the
moment. Small n (4), but uniformly directional → point-of-claim overconfidence. (Hub-scope caveat:
a 4-reflection sample is thin; treat as a hypothesis to confirm on a derived project, not a verdict.)

## Architectural Drift Assessment (specialist-corrected)
- **18 ADRs, 2 superseded** (ADR-0002→0005, ADR-0007→0009) — ~11% churn. Stable.
- **ADR-0002 has a stale status.** ADR-0005 carries `supersedes: ADR-0002`, but ADR-0002's own
  frontmatter still reads `status: accepted`. Bidirectional supersession is incomplete — minor, but
  against the spirit of Principle #5's immutable trail. *(Surfaced by architecture-consultant; the
  draft missed it.)*
- **ADR-0017 is an unmerged-branch ADR, not a numbering gap and not at risk of loss**
  *(verified post-review against the worktree; corrects an architecture-consultant claim this report
  initially repeated)*. ADR-0017 ("Down-Propagation Protocol") exists on `feat/distribute-b1-floor`
  with `status: accepted`, `supersedes: null`. It is **not** superseded by ADR-0019 (that is the
  unrelated async-collab-loop). Main allocated 0018/0019 to other decisions and never used 0017, so
  there is **no numbering conflict** — ADR-0017 slots cleanly into main whenever the distribute
  branch merges. Net: a normal not-yet-merged ADR, not a drift incident. *(Lesson: a specialist's
  supersession claim was propagated into the draft unverified — see Specialist Review Notes.)*
- **The `decisions` SQLite table is empty.** Supersession lives only in ADR frontmatter; the
  meta-review's own drift instrument can't compute churn (this analysis read the files directly).
  Open question for the developer: is the table vestigial, or a genuine capture gap?

## Rule Evolution
### Proposed New Rules
- **"Verification must challenge assumptions, not just code"** — carried from META-REVIEW-20260523
  finding #2 (the `/distribute` self-confirming-test case). *Re-flagged with a caveat
  (independent-perspective): 5 days is not a remediation cycle; this is "still a candidate," not
  "negligently unaddressed."* Decision still owed: promote or explicitly decline.
### Proposed Rule Changes / Deprecations
- None. No rule is firing wrongly.

## Education Assessment
~100% pass across all Bloom levels on tiny n — the rubber-stamp signature the 2026-05-23 review
diagnosed (finding D). Re-flagged for continuity only; **this run adds no new evidence** and does
not re-argue it. The substantive case lives in the prior review.

## Framework Adjustments (proposed — developer decides, Principle #7)
Re-ordered by specialist-validated severity:

- **C → now #1. Quality-gate log integrity (scope-independent, both specialists' strongest pick).**
  Runs logged `overall: pass` while `checks` report `fail` (e.g. 2026-05-25T17:08:28 — all 7 checks
  fail, overall pass; 2026-05-28T02:06:18 — reviews fail, overall pass). The `--skip-*`/cache path
  must emit an **explicit skip record**, not a synthetic pass. Until then the gate log cannot be
  trusted as a capture artifact (Principle #2).
- **A′. Fix pattern-extraction quality, not promotion throughput** *(amended per
  architecture-consultant)*. The fingerprinter in the pattern-sightings step hashes raw text
  including verdict-header markers (`## Verdict:`, `QA Review`), so common review openers accumulate
  false Rule-of-Three hits. Filter structural/verdict markers before hashing. **Then** measuring
  promotion throughput becomes meaningful — against real candidates. Do *not* promote the current 3.
- **B. Run the adoption audit.** 45 PENDING adoptions, 0 audited to CONFIRMED/REVERTED. The loop's
  own contract says "evaluated at the next /retro or /meta-review." Sample the highest-scoring
  adoptions (regression ledger 25/25, autonomous_workflow 23/25, named failure taxonomy 22/25) and
  mark them with evidence. Aligned with the loop's design; no boundary concerns.
- **D. Re-aim the education gate** — carried verbatim from META-REVIEW-20260523 finding D; still
  open. Flagged so it isn't lost between loops, not re-argued.
- **E. Calibration feedback** (least-complex, Principle #8): surface existing `avg_calibration` back
  into agent working context, or add a short reflection prompt on high-confidence findings.

## Knowledge Pipeline Health (reframed)
`python scripts/knowledge_dashboard.py`:
- **Layer 1** — 71 discussions. **Layer 2** — 57 indexed/closed, 377 turns.
- **Findings** — 207 (critical 32, medium 124, low 40, info 11); security densest critical (21/49).
- **Pattern sightings** — 184 (167 unique). **Rule of Three qualified: 3** — but all 3 are verdict
  boilerplate (see A′), so this count is inflated by extraction noise.
- **Promotion candidates: 3. Promoted: 0** — **correct restraint, not backpressure** (verified).
- **Layer 3 (curated)** — patterns 0, rules 0, reflections 0, decisions 1, lessons 2, bugs 1.
  Sparse — but expected on a lab instance that explores more than it codifies (independent-
  perspective). Not scored as failure here.
- **Forgetting curve** — 0 flagged, 0 archived (nothing promoted to forget).

**Reframed pipeline read:** the front half ingests heavily and the promotion gate correctly holds —
the actionable defect is the **nomination stage** feeding it noise (A′), and the **inability to
tell good adoptions from inert ones** because the audit never runs (B).

## Double-Loop Findings (the criteria themselves)
1. **We measure ingestion, not consolidation — and the consolidation we *can* measure is fed noise.**
   The fix is upstream candidate quality (A′), not exhortation to promote more.
2. **`survival_pct` still absent from the hub dashboard** — the decision-relevant "did this finding
   reach synthesis?" metric remains uncomputable here. Persisted across two macro loops.
3. **No outcome data — the central blind spot (independent-perspective).** Neither this review nor
   the prior one measures whether the framework helps the developer build faster, ship fewer
   regressions, or decide better. Both are *process* audits. The genuine end-state — does this
   framework produce better software, faster, for its developer? — is unexamined. This is the most
   important thing the macro loop is *not* looking at, and the highest-value addition to the next run.
4. **The meta-review is itself an un-audited ritual (accepted self-critique).** Finding #4 of the
   draft — "audit loops don't audit themselves" — applies to this document: it detects non-running
   loops and emits recommendations that will themselves not be audited unless tracked. Mitigation:
   the adjustments above are logged to BUILD_STATUS advisories with owners, so the *next* loop can
   audit *this* one. Without that, the critique is self-fulfilling.

## Protocol Overhead Audit

| Protocol | Invocations | Blocking | Advisory | Agent-turns | Blocking/turn | Adv:Block | Trend |
|----------|------------|----------|----------|-------------|---------------|----------|-------|
| review | 18 | 51 | 176 | 105 | 0.49 | 3.5:1 | dense, advisory-heavy |
| checkpoint | 5 | 6 | 8 | 18 | 0.33 | 1.3:1 | lean, good blocking ratio |
| quality_gate | 92 runs | — | — | — | 73 pass / 19 fail | — | reviews-check fails 57%, regression 36% |
| education_gate | ~5–6 | 0 | 0 | — | ~100% pass | — | rubber-stamp (prior review) |
| retro | 0 captured | — | — | — | — | — | not run this period |

Token-efficiency (`v_token_efficiency`): review yield 0.142, build_module 0.01.

- **Redundancy**: review's core panel (qa/security/architecture) overlaps — architecture-consultant
  is 47% unique. independent-perspective (best calibration, lowest dispatch) is the structural
  escape and is under-used.
- **Solo-dev calibration**: review's 3.5:1 advisory:blocking is the advisory flood. Dominant
  quality-gate friction is the **reviews-existence (57% fail)** and **regression (36% fail)** checks
  — the two documented Known Limitations (date-rollover false-negative; cache-window silent skip).
  Candidate relaxation: an advisory budget / "would this change the merge decision?" filter on
  review. *Not* checkpoints (lean, catch real issues). Presented as input — developer decides (#7).

## External Learning Assessment (adoption-log macro trends)
- 165 patterns evaluated / 62 adopted / 42 deferred / 33 rejected. ~38% adoption, ~20% rejection —
  healthy intake; score thresholds (20/25) look well-placed (rejects ≤16, adopts ≥20).
- **Audit gap (real, scope-independent)**: 45 adopted patterns are PENDING; **zero audited to
  CONFIRMED/REVERTED** through the loop (the 7 "already confirmed" are rediscoveries of existing
  template features, not outcome audits). We cannot tell which of 62 adopted patterns are
  load-bearing vs shelfware. → Adjustment B.
- **Rule of Three** fires correctly historically (e.g. /ship pre-flight +2); the in-DB count this
  period is inflated by the verdict-boilerplate fingerprinting bug (A′).

## Specialist Review Notes
- **architecture-consultant (conf 0.88)** — Validated the draft as "structurally sound with three
  errors." Verified ADR-0007→0009; corrected ADR-0002 (stale `accepted` status) and ADR-0017
  (worktree merge gap, not numbering gap). **Decisive correction:** inspected the 3 promotion
  candidates and confirmed they are verdict boilerplate → zero promotion is correct restraint; fix
  is upstream fingerprinting (A′). Endorsed C as the strongest finding (Principle #2 capture
  violation) and B/E as boundary-clean.
- **independent-perspective (conf 0.82)** — Argued the hub-only scope re-frames rather than rebuts
  the prior review's denominator objection (lab instances *should* promote little); flagged the
  total **absence of outcome data** in both runs as the real blind spot; cautioned that 5-day
  re-flagging manufactures the appearance of failure; and turned finding #4 on the instrument
  itself (the meta-review is another un-audited ritual). Singled out C as the one finding that
  should be *louder*. All four challenges are accepted and incorporated above.

## Open questions for the developer
- Are the 3 RoT candidates noise we should discard (A′ says yes), or is one salvageable?
- Is the empty `decisions` table vestigial or a real capture gap to wire up?
- Should the next macro loop add an **outcome signal** (regressions shipped, build velocity,
  decision-reversal rate) so we stop auditing only our own internals?
- Is the "audit rituals don't run" meta-pattern a design flaw or solo-dev bandwidth — and if the
  latter, should we *reduce* consolidation rituals (Principle #8) rather than add enforcement?
