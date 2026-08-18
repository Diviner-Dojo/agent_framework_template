---
discussion_id: DISC-20260612-190124-supervisor-resilience-tiering-review
started: 2026-06-12T19:01:57.375358+00:00
ended: 2026-06-12T23:55:08.672279+00:00
agents: [facilitator, qa-specialist, security-specialist]
total_turns: 6
---

# Discussion: DISC-20260612-190124-supervisor-resilience-tiering-review

## Turn 1 — facilitator (evidence)
*2026-06-12T19:01:57.375358+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Execute work item 2 of WORKITEMS-20260612-lean-supervisor (developer-approved 2026-06-12): (a) sleep-until-reset on subscription usage-limit kills with capped retries, (b) turn-budget awareness injected into the per-session prompt, (c) per-run MODEL: tiering parsed from the rolling handoff's NEXT RUN header and passed as --model. Then /review before commit (small-change workflow).
- **Files/scope**: scripts/session_supervisor.py + tests/test_session_supervisor.py, uncommitted working-tree changes only.
- **Developer-stated motivation**: Two overnight chains died on usage-limit kills (2026-06-11 17:47, 2026-06-12 07:46) wasting the post-reset window; an 80-turn clip (07:09) produced a no-sentinel chain stop; mechanical phases should run cheaper orchestrator tiers (lean-dispatch skill).
- **Explicit constraints**: Lean dispatch policy binding (sonnet specialists, compact structured returns). Quality floor unchanged: deterministic gate + reviews + opus Steward regardless of orchestrator tier. Supervisor safety posture unchanged (no --bare, hooks still fire, clean-tree preflight).

---

## Turn 2 — qa-specialist (proposal)
*2026-06-12T19:06:00.237712+00:00 | confidence: 0.88*
*tags: model-tier:sonnet*

VERDICT: approve-with-changes. CONFIDENCE: 0.88. F1 MED parse_reset_seconds boundary: 'candidate <= now_ts' rolls exact-reset-time to tomorrow (correct) but untested — add ==-boundary test pinning the <= operator. F2 LOW detect_usage_limit stdout slot untested (candidates order result->stderr->stdout). F3 LOW limit-kill at max_sessions: sleeper fires but retry never executes (wasted sleep, outcome 'max-sessions'); add interaction test. F4 LOW DST-day '+= 24*3600' drifts +/-1h on 2 days/yr; recommend docstring note or mday+1 mktime renormalization. STRENGTHS: sleeper seam; pure parser isolation; adversarial argv-smuggling test. Regression-ledger contract: claims entries at lines 55-56 cover both bugs (TO VERIFY). Test adequacy: behavioral assertions, regression markers present.

---

## Turn 3 — security-specialist (proposal)
*2026-06-12T19:06:05.918078+00:00 | confidence: 0.92*
*tags: model-tier:sonnet*

VERDICT: approve-with-changes. CONFIDENCE: 0.92. F1 MED (CWE-696) limit_retries x max_sessions interaction: i increments on retried iterations, so a limit kill near the session cap sleeps then exits labeled 'max-sessions', masking the usage-limit cause; fix by checking remaining slots before sleeping / labeling outcome usage-limit. F2 LOW (A03) _MODEL_RE permits leading '-'/'.', so 'MODEL: -h' yields argv '--model -h' (CLI rejects -> failed session, no escalation); anchor first char alphanumeric. Trust-boundary table: MODEL->argv (charset+discrete argv, ok); CLI output->sleep (None->fallback, capped, ok); output->classify (strict sentinels, ok); handoff path control-char guard unchanged. STRENGTHS: space-blocking regex + discrete argv satisfies rule 19; parse failure cannot produce zero/negative/unbounded sleep; sleeper seam testable.

---

## Turn 4 — facilitator (critique)
*2026-06-12T23:53:52.713972+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 5 verified (qa F1 ==-boundary untested: confirmed '<=' at parse_reset_seconds; qa F2 stdout slot untested: confirmed candidates order; qa F3 + sec F1 convergent wasted-sleep/mislabeled-outcome at session cap: confirmed by loop inspection; qa F4 DST drift: confirmed raw +86400; sec F2 leading-hyphen charset: confirmed). 0 inconclusive. 1 specialist claim corrected: qa asserted regression-ledger lines 55-56 already covered the two new bugs — FALSE, the ledger was unmodified in this tree (entries were still owed; now written as part of the fold). ALL 5 verified findings FOLDED in-session: (1) ==-boundary test, (2) stdout detection test, (3) no-slot guard before sleep + honest 'usage-limit' outcome + interaction test, (4) DST-safe mday+1 mktime renormalization, (5) _MODEL_RE first-char alphanumeric + leading-hyphen/dot test. 60/60 tests pass post-fold; ruff clean. 2 regression-ledger entries added (usage-limit chain stop; turn-cap no-sentinel clip).

---

## Turn 5 — facilitator (synthesis)
*2026-06-12T23:54:10.707921+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:5, speculative:0, model-tiers:qa-sonnet+security-sonnet*

## Request Context
- **What was requested**: Work item 2 of WORKITEMS-20260612-lean-supervisor (developer-approved 2026-06-12): supervisor sleep-until-reset on usage-limit kills, turn-budget prompt awareness, per-run MODEL: tiering; small-change workflow (gate + /review).
- **Files/scope**: scripts/session_supervisor.py + tests/test_session_supervisor.py (uncommitted), + regression-ledger entries.
- **Developer-stated motivation**: 2 overnight usage-limit chain kills wasted the post-reset window; an 80-turn clip caused a no-sentinel stop; mechanical phases should run cheaper tiers.
- **Explicit constraints**: lean dispatch (sonnet panel, compact returns); supervisor safety posture unchanged.

## Verdict: APPROVE (approve-with-changes pre-fold; all changes folded in-session)
Panel: qa-specialist 0.88 + security-specialist 0.92 (ensemble, both sonnet). Weighted ~0.90.
Blocking: 0. Advisory: 5, ALL folded in-session: qa F1 MED ==-boundary test pinning '<='; qa F2 LOW stdout-slot detection test; qa F3 LOW + sec F1 MED (convergent) no-slot-remaining guard — skip the wasted sleep and return honest 'usage-limit' outcome instead of masking 'max-sessions', + interaction test at max_sessions=1; qa F4 LOW DST-safe tomorrow via mktime mday+1 renormalization; sec F2 LOW _MODEL_RE first char anchored alphanumeric (blocks 'MODEL: -h' argv shaping), + test. Discarded/corrected: qa's regression-ledger-already-covers claim was false — 2 ledger entries written in the fold.
Safety posture verified unchanged by security trust-boundary table: no --bare, caps, clean-tree preflight, control-char guard all intact; MODEL value rides as a discrete argv element (REVIEW.md rule 19 satisfied); malformed reset text cannot produce zero/negative/unbounded sleep (None -> 1h fallback, capped retries).
Confidence annotation: 0 speculative (<0.80), 0 unscored. Post-fold: 60/60 tests, ruff format+check clean.
Model tiers: qa-specialist:sonnet, security-specialist:sonnet (lean-dispatch policy; facilitator-equivalent = Fable main loop).

---

## Turn 6 — facilitator (reflection)
*2026-06-12T23:55:08.672279+00:00 | confidence: 0.8*
*tags: reflection, reflection-deferral*

Reflection round deferred per lean-dispatch policy (autonomous session; specialist critiques captured in proposal events; cost discipline). Education gate deferred to the open cohort per auth E.

---
