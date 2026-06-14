---
discussion_id: DISC-20260606-071432-walkthrough-telemetry-cost-a1
started: 2026-06-06T07:17:41.841179+00:00
ended: 2026-06-06T07:17:41.841179+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260606-071432-walkthrough-telemetry-cost-a1

## Turn 1 — educator (proposal)
*2026-06-06T07:17:41.841179+00:00 | confidence: 0.88*
*tags: walkthrough, education*

Gatekeeper walkthrough (concept-first, 0.88) for Telemetry A1. 4 load-bearing concepts: (1) COMPUTE-DON'T-STORE - discussion_model_tokens stores token counts + tier, NO cost column; dollars derived at read from model_pricing.yaml; a price change is a 1-line YAML edit not a data migration (ADR-0013). (2) COVERAGE HONESTY - coverage% on TOKEN denominator (cost is proportional to tokens not discussions); unknown tier -> cost_usd None, counted in denominator not total, never zero-rated; 'honest $632 @ 90% coverage' vs 'misleading $632 hiding 10%' - same ethic as pass_with_skips. Zero-tokens -> 0% not 100%. (3) WATERMARK + not-yet-analyzed backstop - incremental skip by closed_at>watermark; the strict-> same-timestamp silent-skip bug; backstop = a closed discussion with no rows is ALWAYS a target (watermark is optimization, backstop is correctness). Known limit: gates re-WRITE not re-READ (full corpus parsed each run). (4) PURE/TRANSPORT boundary - src/telemetry pure+unit-tested, scripts/telemetry I/O+transport-fidelity boundary (live ~/.claude not unit-tested, R-A5). 4 invariants + failure modes + diagnostic recipes (--dry-run, query discussion_model_tokens, --full-rescan). 4 quiz-prep questions on: pricing-change blast radius, token-vs-discussion coverage, same-timestamp backstop, and the add-a-cost_usd-column anti-pattern.

---
