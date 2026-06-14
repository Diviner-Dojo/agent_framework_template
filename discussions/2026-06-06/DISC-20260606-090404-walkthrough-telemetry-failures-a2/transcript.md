---
discussion_id: DISC-20260606-090404-walkthrough-telemetry-failures-a2
started: 2026-06-06T09:04:04.563730+00:00
ended: 2026-06-06T09:04:04.563730+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260606-090404-walkthrough-telemetry-failures-a2

## Turn 1 — educator (proposal)
*2026-06-06T09:04:04.563730+00:00 | confidence: 0.88*
*tags: walkthrough, education*

Concept-first walkthrough for Telemetry A2 (failure signals), 0.88. 5 load-bearing concepts to teach INTERACTIVELY (analogy-first, gatekeeper's why, one at a time) next session: (1) GROUNDING-BEFORE-CODING - spec said 'Task', transcripts said 'Agent' (zero 'Task' matches); stop-loop deferred for no reliable signal. Standard: detect only what real evidence supports; the gatekeeper's test for any future detector. (2) TWO-SIDED ORPHAN MODEL + false-positive guard - parent-side (dispatched, no result) vs transcript-side (hung mid-flight); run_in_background excluded so async dispatches aren't false positives; parent-side orphans are often 'uncosted' (no transcript back-link). (3) CONSERVATIVE RETRY DETECTION - threshold 3 not 2 (one retry is normal), consecutive-only (interleaved = reuse not loop), wasted = repeats 2..N only; --retry-threshold is the tuning lever. (4) COST-WEIGHTED RANKING + carried compute-don't-store / unknown-never-zero-rated - store wasted tokens, derive dollars at read; 'uncosted' sorts last, never $0. (5) WATERMARK BOUNDARY >= not > - one-char fix closing a silent same-timestamp skip; invisible failure mode. 4 explain-back questions drafted (grounding standard; the 3-dispatch orphan scenario; the interleaved-reads retry scenario; the 4.5M-token uncosted-ranking challenge). Teaching order: start with grounding (frames all others); concept 4 compresses to a confirm-check if A1's compute-don't-store landed.

---
