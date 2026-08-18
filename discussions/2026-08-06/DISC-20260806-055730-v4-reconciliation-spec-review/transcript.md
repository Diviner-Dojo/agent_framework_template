---
discussion_id: DISC-20260806-055730-v4-reconciliation-spec-review
started: 2026-08-06T06:11:56.950252+00:00
ended: 2026-08-06T06:11:57.797376+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260806-055730-v4-reconciliation-spec-review

## Turn 1 — facilitator (proposal)
*2026-08-06T06:11:56.950252+00:00 | confidence: 0.8*
*tags: review, dispatch*

Spec review dispatched: four reviewers, each in a context that never saw the generation reasoning, each given the artifacts and the specific risk to look for (merged Principle #3). architecture-consultant (taxonomy re-inflation + base-selection measurement), security-specialist/opus (enforcement loss at the seams), qa-specialist (is the N=1 A/B capable of detecting anything, or evidence theatre), independent-perspective (attack the thesis; is 'evidence-gated' real).

---

## Turn 2 — architecture-consultant (critique)
*2026-08-06T06:11:57.086155+00:00 | confidence: 0.85*
*tags: blocking, measurement, taxonomy*

REVISE (0.85). BLOCKING: the spec's flagship measurement is wrong - v4's quality_gate.py delta vs merge-base af3fd10 is +123/-5, not the claimed +50/-5. 'Orthogonal deltas' is also false: both trees independently added check_promotion_backlog() (absent from the ancestor), main's a superset. The taxonomy's re-inflation bound is never applied to the 25 main-only scripts / 10,297 lines - including all of scripts/telemetry/ (ADR-0020), never mentioned in any section.

---

## Turn 3 — security-specialist (critique)
*2026-08-06T06:11:57.385268+00:00 | confidence: 0.86*
*tags: blocking, enforcement, reward-function*

REVISE (0.86). AC3 as written permits a Stop-hook rewrite that drops the untrusted-ntfy-reply allow-list (a CLAUDE.md always-on invariant); tests/test_stop_hook.py does not exist on the v4 base so nothing would catch it. The add-back writes into .claude/hooks/, which v4 PROTECTS (the B5 remediation) - the cheapest unblock silently reverts it. Also: --rebaseline is NOT a lock as the spec claims; it is a store_true flag whose consent requirement lives in a docstring and a warning printed AFTER the baseline is rewritten. It exits 0.

---

## Turn 4 — qa-specialist (critique)
*2026-08-06T06:11:57.524217+00:00 | confidence: 0.88*
*tags: blocking, experiment-design, power*

REVISE (0.88). The A/B is not executable as specced. Task equivalence FALSIFIED by diff: assertion_store/embeddings.py, mcp_server/server.py, tests/test_mcp_server.py all differ across trees - v4 had already fixed the eager-import bug that makes those tests skip on main, so the task is strictly easier on v4 for reasons unrelated to the thesis. The v4 arm has no telemetry, no stop_hook, no model_call_log - the primary metric is unobtainable. Neither tree's gate measures coverage for those directories, so 'gate-green' is undefined. Three of four metrics detect only an order-of-magnitude effect at N=1; only subagent-call share carries structural signal.

---

## Turn 5 — independent-perspective (critique)
*2026-08-06T06:11:57.659792+00:00 | confidence: 0.8*
*tags: blocking, anti-groupthink, decision-rule*

REVISE (0.80). 'Evidence-gated' gates nothing: no acceptance criterion is contingent on the A/B result, base selection is settled in section 3.3 before section 4 runs, and R1 pre-declares 'inconclusive' acceptable. The ADR names this risk in Consequences and ships without closing it, which inoculates against the criticism rather than answering it. The measurement site is also wrong by the repo's own recorded standard: hub artifacts are judged by derived-project usage, and the three consumers are never consulted before the decision to replace their framework. Unconsidered alternatives: keep both and choose per project; pilot on one derived project first.

---

## Turn 6 — facilitator (synthesis)
*2026-08-06T06:11:57.797376+00:00 | confidence: 0.85*
*tags: synthesis, verdict*

Verdict REVISE 4/4, 5 blocking. Every relayed claim re-verified against the repository before acceptance - three reviewer counts were themselves off and corrected in the REV (25 main-only scripts not 24; 18 missing test modules not 19; 23 ADR-0029 refs excluding sealed discussions not 24). Two of the blocking findings are the generator's own factual errors, caught only by contexts that had not seen the reasoning. Recorded in ADR-0031 as the strongest in-repo evidence that the governance layer should not be thinned. Full report: REV-20260805-213438.

---
