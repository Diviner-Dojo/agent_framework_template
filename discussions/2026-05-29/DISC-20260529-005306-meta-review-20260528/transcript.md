---
discussion_id: DISC-20260529-005306-meta-review-20260528
started: 2026-05-29T05:02:31.950565+00:00
ended: 2026-05-29T05:15:27.479760+00:00
agents: [architecture-consultant, facilitator, independent-perspective]
total_turns: 4
---

# Discussion: DISC-20260529-005306-meta-review-20260528

## Turn 1 — facilitator (proposal)
*2026-05-29T05:02:31.950565+00:00 | confidence: 0.82*
*tags: meta-review, draft*

---
meta_review_id: META-REVIEW-20260528
status: draft
period: 2026-03-09 .. 2026-05-26 (template-hub telemetry)
denominator: hub-only (template repo; cross-instance view deferred — see scope note)
prior_meta_review: META-REVIEW-20260523 (draft, hub-lens / 4-instance)
---

# Quarterly Framework Evaluation (Macro / Double-Loop) — DRAFT

## Scope note
Run from the template hub against **hub-local telemetry only** (57 discussions, 377 turns,
2026-03-09 → 2026-05-26). This is a deliberate, developer-confirmed narrowing: the
2026-05-23 draft already did the cross-instance hub-lens pass. This run instead asks a
question that pass under-weighted: **is the framework's own capture-and-promotion machinery
healthy on the instance that builds it?** Where a finding here echoes the prior review, that
is signal (the issue persisted 5 days and a release later), not redundancy.

## Executive Summary
The capture pipeline's *front half* is working hard and its *back half* is idle. The hub
ingested 207 findings and 184 pattern sightings this period, yet **promoted zero** of them to
curated memory — Layer 3 holds 0 patterns, 0 rules, 0 reflections. The single mechanism built
to close that loop (the Adoption Audit Loop, adopted 2026-02-19) has itself never run: 45
adopted patterns sit PENDING, none audited to CONFIRMED/REVERTED. Two governance integrity
signals also surfaced: the quality gate logged `overall: pass` on runs where individual checks
report `fail` (the verification-cache/skip path), and the meta-review's own `decisions` drift
table is empty while ADR supersession lives only in file frontmatter. Architectural foundations
remain stable (2/18 ADRs superseded, ~11% churn) — the framework is not thrashing its principles;
it is **accumulating knowledge it never consolidates.**

## Agent Effectiveness (hub lens)

| Agent | Disc | Unique | Dup | Uniq% | Conf | Calib | Read |
|---|---|---|---|---|---|---|---|
| architecture-consultant | 17 | 9 | 10 | 47% | 0.856 | 0.494 | workhorse; half its findings duplicate others |
| qa-specialist | 14 | 8 | 6 | 57% | 0.858 | 0.441 | solid uniqueness, weakest calibration |
| security-specialist | 14 | 8 | 8 | 50% | 0.881 | 0.490 | highest confidence; 21 of 49 sec findings = critical |
| docs-knowledge | 7 | 5 | 2 | 71% | 0.855 | 0.356 | high uniqueness, low dispatch |
| independent-perspective | 6 | 3 | 4 | 43% | 0.808 | 0.508 | anti-groupthink valve; under-dispatched |
| educator | 3 | 2 | 1 | 67% | 0.873 | 0.340 | |
| facilitator | 6 | 1 | 5 | 17% | 0.824 | 0.720 | orchestrator — duplication expected |
| ux-evaluator | 1 | 1 | 0 | 100% | 0.820 | — | hub has ~no frontend; domain-misfit confirmed |
| performance-analyst | 1 | 0 | 1 | 0% | 0.580 | — | **lowest confidence, 0 unique** — near-dormant on hub |
| steward / history / project | 1–3 | 0 | — | — | — | — | episodic by design |

**Calibration is the weak axis.** Where agents carry enough findings to compute it (arch, qa,
security, docs, independent), calibration clusters 0.36–0.51 — meaning stated confidence tracks
outcome only loosely. The four reflections captured this period **all show negative
confidence_delta** (arch −0.04, docs −0.13, qa −0.08, security −0.11): on reflection, agents
judged themselves *less* right than they claimed in the moment. Small n (4), but every sample
points the same direction → **systematic point-of-claim overconfidence.**

## Architectural Drift Assessment
- **18 ADRs, 2 superseded** (ADR-0002→0005, ADR-0007→0009) — ~11% churn. Stable; foundations
  are not being rewritten even as features land (ADR-0018 wrap-up, ADR-0019 async-collab-loop).
- **ADR-0017 is a numbering gap** — no file, no inbound references. Either an aborted decision
  or one that was made and never recorded. Minor, but Principle #5 ("ADRs are never deleted,
  only superseded with references") implies the *numbering* is also part of the immutable trail;
  a silent gap should be explained with a tombstone note.
- **The `decisions` SQLite table is empty.** Supersession is recorded only in ADR frontmatter
  (`supersedes:`/`status: superseded`). The meta-review's own drift instrument therefore can't
  compute churn — this analysis had to read the files directly. Measurement gap, not a code gap.

## Rule Evolution
### Proposed New Rules
- **"Verification must challenge assumptions, not just code"** (carried from META-REVIEW-20260523
  finding #2; the `/distribute` self-confirming-test case). Still unwritten 5 days later — it has
  now survived two macro loops as a candidate. Promote or explicitly decline.
### Proposed Rule Changes
- None blocking. Calibration weakness (above) is an agent-prompt/reflection-cadence issue, not a
  rule gap.
### Proposed Deprecations
- None. No rule is firing wrongly; the problem is rules/patterns that *should exist but don't*.

## Education Assessment
All Bloom levels pass at ~100% (understand 5/5, apply 5/6, analyze 5/5, evaluate 3/3). With
near-universal pass and tiny n, this is the **rubber-stamp signature** the 2026-05-23 review
diagnosed (finding D: "re-aim the educator at the decision-maker's possibility-space"). **Status:
unaddressed.** This run adds no new evidence but confirms the gate has not changed behavior since
the prior review flagged it as a *values-level* miss (Principle #7 approval requires real
comprehension).

## Framework Adjustments (proposed — developer decides, Principle #7)
- **A. Promotion throughput is the #1 health gap.** 3 promotion candidates (correctness ×4,
  testing ×3, documentation ×3) have hit/neared Rule of Three and sit unpromoted. Run a `/promote`
  pass on the 3 candidates, or record why each is declined. Make **promotion throughput a
  first-class dashboard metric** (findings-in vs patterns-out), because today the pipeline looks
  busy while its output is zero.
- **B. Run the adoption audit.** 45 PENDING adoptions, 0 audited. The very pattern built to stop
  write-only logging is being applied write-only. Sample the highest-leverage PENDING adoptions
  (regression ledger, autonomous_workflow rule, named failure taxonomy) and mark CONFIRMED with
  evidence or REVERTED — per the loop's own design, "evaluated at the next /retro or /meta-review."
- **C. Quality-gate log integrity.** Runs logged `overall: pass` while `checks` report `fail`
  (e.g. 2026-05-25T17:08:28 all-7-fail-but-pass; 2026-05-28T02:06:18 reviews-fail-but-pass).
  This is the verification-cache/skip path surfacing in the audit trail. A gate whose log says
  PASS while checks say FAIL erodes Principle #2 (capture cannot be opted out of). Make `overall`
  reflect the actual check results, or log the skip reason explicitly.
- **D. Re-aim the education gate** — carried verbatim from META-REVIEW-20260523 finding D. No new
  analysis; flagged as still-open so it isn't lost between loops.
- **E. Calibration feedback.** Negative reflection deltas + loose calibration suggest agents
  should see their own calibration history. Lightweight: surface `avg_calibration` back into the
  agent's working context, or add a brief reflection-cadence prompt on high-confidence findings.

## Knowledge Pipeline Health
`python scripts/knowledge_dashboard.py`:
- **Layer 1** — 71 discussions on disk.
- **Layer 2** — 57 indexed/closed, 377 turns.
- **Findings** — 207 total (critical 32, medium 124, low 40, info 11). Security is the densest
  critical category (21 critical of 49 security findings).
- **Pattern sightings** — 184 (167 unique). **Rule of Three qualified: 3.**
- **Promotion candidates: 3. Promoted: 0.**
- **Layer 3 (curated)** — decisions 1, lessons 2, patterns 0, reflections 0, rules 0, bugs 1,
  archive 0. **The consolidated-knowledge layer is effectively empty.**
- **Forgetting curve** (`enforce_forgetting_curve.py --dry-run`): 0 flagged, 0 archived — nothing
  to forget because nothing was ever promoted.

**The pipeline shape is the headline finding:** 207 findings → 184 sightings → 3 RoT → 3
candidates → **0 promoted → 0 in Layer 3.** Backpressure is total at the promotion gate.

## Double-Loop Findings (the criteria themselves)
1. **We measure ingestion, not consolidation.** Every dashboard number that is large measures the
   *front* of the pipeline (findings, sightings, turns); the one number that measures the *point*
   of the pipeline — patterns/rules promoted — is zero and isn't surfaced as a health signal. We
   are optimizing the metric that is easy to move, not the one that matters.
2. **`survival_pct` still missing from the hub dashboard** (prior review's measurement-drift
   finding). The decision-relevant "did this finding reach synthesis?" metric remains
   uncomputable here. Persisted across two macro loops.
3. **Self-confirming verification still unguarded** (prior finding #2). A defect class identified,
   named, and proposed-as-a-rule has gone two cycles without a rule. The meta-loop is *detecting*
   but not *converting* — the same backpressure as the promotion gate, one level up.
4. **The audit loops don't audit themselves.** Adoption audit (write-only), decisions table
   (empty), promotion (0 throughput): three different consolidation mechanisms, all built, all
   idle. The framework reliably *generates* governance machinery and unreliably *runs* it. This is
   the meta-pattern — and it is plausibly a solo-developer-bandwidth signal, not a design flaw.

## Protocol Overhead Audit

| Protocol | Invocations | Blocking | Advisory | Agent-turns | Blocking/turn | Adv:Block | Trend |
|----------|------------|----------|----------|-------------|---------------|----------|-------|
| review | 18 | 51 | 176 | 105 | 0.49 | 3.5:1 | dense, advisory-heavy |
| checkpoint | 5 | 6 | 8 | 18 | 0.33 | 1.3:1 | lean, good blocking ratio |
| quality_gate | 92 runs | — | — | — | 73 pass / 19 fail | — | reviews-check fails 57%, regression 36% |
| education_gate | ~5–6 | 0 | 0 | — | ~100% pass | — | rubber-stamp (see above) |
| retro | 0 captured | — | — | — | — | — | not run this period |

Token-efficiency (`v_token_efficiency`): review yield 0.142, build_module 0.01.

Assessment:
- **Redundancy**: review and checkpoint both run qa/security/architecture and ~half of
  architecture-consultant's findings are duplicates (47% unique). The homogeneous core panel
  reasons from one mental model; independent-perspective (best calibration, lowest dispatch) is
  the only structural escape and is under-used.
- **Solo-dev calibration**: review's 3.5:1 advisory:blocking ratio is the advisory flood the prior
  review flagged. Checkpoints are leaner (1.3:1) and shouldn't be cut. The dominant quality-gate
  friction is the **reviews-existence (57% fail)** and **regression (36% fail)** checks — exactly
  the two documented Known Limitations (date-rollover false-negative; cache-window silent skip).
- **Efficiency trend**: build_module token yield (0.01) is an order of magnitude below review
  (0.142) — builds spend heavily for little captured finding-yield, expected (building ≠ finding).
- **Explicit question — which protocols to relax for solo dev?** Candidate: an **advisory budget**
  on review (cap or "would this change the merge decision?" filter before capture) to drain the
  3.5:1 flood. *Not* checkpoints (lean, catch real issues per `/distribute`). Developer decides
  (Principle #7) — presented as input, not a recommendation to auto-apply.

## External Learning Assessment (adoption-log macro trends)
- **Volume**: 165 patterns evaluated across 18 analyses → 62 adopted, 42 deferred, 33 rejected.
  Adoption rate ~38%, rejection ~20%. Neither aggressive nor starved — healthy intake.
- **Audit gap (the headline)**: 45 adopted patterns carry `Adoption Status: PENDING`; **zero have
  been audited to CONFIRMED or REVERTED** through the loop (the 7 "already confirmed" are
  rediscoveries of existing template features, not outcome audits). The learning ledger is
  recording decisions but not outcomes — the exact write-only failure the Adoption Audit Loop was
  adopted to fix has recurred against the audit loop itself.
- **Shelfware risk**: with no audit, we cannot tell which of 62 adopted patterns are load-bearing
  vs inert. Recommend the batch-evaluate pass (B above) starting with the 25/25 and 24/25 scorers.
- **Score calibration (20/25 threshold)**: distribution looks well-placed — rejects cluster
  ≤16/25, adopts ≥20/25, deferrals fill 17–19. No evidence the threshold is mis-set.
- **Rule of Three**: 3 patterns qualified in-DB this period; historically RoT has fired correctly
  (e.g. /ship pre-flight +2 bonus). The mechanism works; the *promotion that should follow it*
  does not.

## Open questions for the panel
- Is **zero promotion** a genuine pipeline failure, or correct restraint (the 3 candidates are
  review-verdict boilerplate like "APPROVE-WITH-CHANGES", not real reusable patterns)? If the
  candidates are noise, the fix is candidate *quality*, not promotion *throughput*.
- Is the empty `decisions` table a real capture gap, or is ADR frontmatter the intended source of
  truth and the table vestigial?
- Is the "audit loops don't run" meta-pattern a design flaw or simply solo-developer bandwidth —
  and if the latter, should the framework *reduce* the number of consolidation rituals rather than
  exhort the developer to run more of them (Principle #8, least-complex intervention)?


---

## Turn 2 — architecture-consultant (critique)
*2026-05-29T05:10:39.391272+00:00 | confidence: 0.88*
*tags: meta-review, specialist-review*

Verdict: core claims structurally sound but carry three errors needing correction before this meta-review is authoritative. (confidence 0.88)

ADR drift verification:
- ADR-0002→0005: PARTIALLY INCORRECT. ADR-0005 carries `supersedes: ADR-0002`, but ADR-0002's own frontmatter still reads `status: accepted` (not superseded) — stale bidirectional supersession, a real minor drift the draft missed (spirit of Principle #5).
- ADR-0007→0009: correctly verified (0007 status: superseded; 0009 supersedes: 0007).
- ADR-0017 "numbering gap": REQUIRES QUALIFICATION. No file in main, but worktree evidence (feat/distribute-b1-floor) shows it was drafted, built against, reviewed, then superseded by ADR-0019 and never merged to main. It is a MERGE-ARTIFACT gap, not an aborted/never-recorded decision. If that worktree never merges, ADR-0017 + its supersession-by-0019 are permanently lost to main history. Tombstone recommendation stands; characterization should change.
- `decisions` table empty: CONFIRMED (0 rows). v_rule_of_three view is schema-sound.

Promotion-candidate quality (answers the draft open question): all three candidates' summary fields are truncated verdict headers ("## Verdict: APPROVE WITH CHANGES (confidence 0...", "QA Review (confidence 0..."). These are review-verdict BOILERPLATE, not reusable patterns — the pattern fingerprinter hashed verdict-opener text that repeats across reviews. ZERO PROMOTION IS CORRECT RESTRAINT. The fix is upstream candidate-extraction/fingerprint quality (filter structural verdict markers before hashing), NOT promotion throughput.

Proposed adjustments:
- A (promotion metric): amend — fix candidate-extraction quality first, then measure throughput against REAL candidates.
- B (adoption audit): fully aligned with the loop's design contract.
- C (quality-gate log integrity): STRONGEST finding architecturally. overall:pass while checks:fail is a Principle #2 capture-integrity VIOLATION, not cosmetic. The --skip-* path must emit an explicit skip record, not a synthetic pass.
- E (calibration feedback): consistent with Principle #8.

Missed signals: (1) ADR-0002 stale status (incomplete bidirectional supersession); (2) ADR-0017 is a merge/promotion gap, not numbering; (3) v_rule_of_three hashes review-boilerplate text — capture-pipeline-level extraction design gap.

---

## Turn 3 — independent-perspective (critique)
*2026-05-29T05:12:15.364792+00:00 | confidence: 0.82*
*tags: meta-review, specialist-review*

(independent-analyst, confidence 0.82)

The draft's most honest sentence is buried in its own open questions: "Is zero promotion a genuine pipeline failure, or correct restraint?" That doubt undermines the headline — but the document leads with the headline and footnotes the doubt.

The denominator problem has not been fixed; it has been RE-FRAMED AS A FEATURE. The hub is where the framework is built, not where it is used. Promotion backpressure on a lab instance is expected: lab work produces exploratory findings, most of which correctly don't graduate to curated rules. The prior review's whole argument was that hub-only telemetry is the wrong signal; this draft re-scopes around that argument rather than rebutting it. The 0-promotion headline may describe a healthy filter, not a broken pump.

Five-day re-flagging is noise dressed as signal. Three findings are carried verbatim from META-REVIEW-20260523 as "still unaddressed after 5 days and a release." Five days is not a governance cycle. Re-flagging unchanged findings at this cadence manufactures the appearance of persistent failure, and reveals the meta-review has no concept of "reasonable remediation time."

The evaluation has NO OUTCOME DATA whatsoever. Neither review measures whether the framework helps the developer build faster, ship fewer regressions, or make better decisions. The entire evaluation is a process audit — pipeline counts, calibration, protocol invocations. The actual end-state (does this framework produce better software, faster, for its developer?) is unexamined in both runs.

The meta-review is itself the pattern it criticizes. Finding #4 ("audit loops dont audit themselves") is generated by another consolidation ritual that will not close its own loop — its recommendations will themselves not be audited. The draft names this risk but does not escape it.

One genuinely sharp finding: quality-gate logs reporting overall:pass when checks report fail is a real integrity issue, not a process complaint. It should be LOUDER, not buried in item C.

---

## Turn 4 — facilitator (synthesis)
*2026-05-29T05:15:27.479760+00:00 | confidence: 0.85*
*tags: meta-review, synthesis*

META-REVIEW-20260528 finalized (hub-only scope, developer-directed). Two scope-independent findings survived specialist scrutiny; the original headline did not.

CORRECTED HEADLINE: The draft's "promotion backpressure" headline (207 findings -> 0 promoted -> empty Layer 3) was overturned. architecture-consultant verified the 3 Rule-of-Three promotion candidates are review-verdict BOILERPLATE (truncated "## Verdict: APPROVE WITH CHANGES..." headers), so zero promotion is CORRECT RESTRAINT. The real defect is upstream: the pattern-sightings fingerprinter hashes verdict-header text, inflating Rule-of-Three with noise (Adjustment A').

TOP FINDING (both specialists' pick, scope-independent): Quality-gate log integrity — runs logged overall:pass while individual checks report fail (the --skip-*/cache path). This is a Principle #2 capture-integrity violation; the skip path must emit an explicit skip record, not a synthetic pass (Adjustment C, promoted to #1).

ADR corrections (architecture-consultant): ADR-0002 status stale (accepted despite superseded by 0005); ADR-0017 is a worktree MERGE gap (drafted/reviewed/superseded-by-0019 in feat/distribute-b1-floor, never merged to main; at risk of permanent loss), not a numbering gap. Architecture stable overall (2/18 superseded).

REAL audit gap (scope-independent): 45 adopted patterns PENDING, 0 audited to CONFIRMED/REVERTED — the adoption audit loop runs write-only (Adjustment B).

DOUBLE-LOOP (independent-perspective, accepted): (1) hub-only re-frames rather than rebuts the prior denominator objection — a lab instance SHOULD promote little; (2) NEITHER macro loop measures developer OUTCOMES (velocity, regressions, decision quality) — the central blind spot; (3) the meta-review is itself an un-audited ritual — mitigation: log adjustments to BUILD_STATUS so the next loop audits this one. 5-day re-flagging of prior findings (verification-assumptions rule, education-gate re-aim) noted as "still candidate," not negligence.

Adjustments owed to developer (Principle #7): C (gate-log integrity), A' (fix fingerprinting; do NOT promote current 3), B (run adoption audit), D (re-aim education gate, carried), E (calibration feedback). Plus: add an outcome signal to the next loop.

---
