---
discussion_id: DISC-20260524-205732-framework-apply-unification-steward-gate
started: 2026-05-24T20:57:42.145012+00:00
ended: 2026-05-24T20:59:47.887322+00:00
agents: [facilitator, steward]
total_turns: 2
---

# Discussion: DISC-20260524-205732-framework-apply-unification-steward-gate

## Turn 1 — facilitator (evidence)
*2026-05-24T20:57:42.145012+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- What was requested: Steward gate on SPEC-20260524-203931 — unify /distribute + /onboard into ONE command (UPDATE if framework present, APPLY if absent) with an up-front value/risk report; deploy gated on clean tree, dedicated back-out branch, never push/auto-merge, one target at a time.
- Files/scope: SPEC-20260524-203931 (status: reviewed); follows the 4-specialist design review DISC-20260524-204142 (verdict REVISE, mechanical fixes folded). Reuses ef9a485 distribute scripts + /onboard.
- Developer-stated motivation: one mental model for applying/updating the framework; core fear is clobbering authored work downstream.
- Explicit constraints / developer decisions to ratify: (R8 consent) developer chose option (ii) — write a human-authored assent artifact INTO the target as deploy step zero, converging greenfield + update on ONE consent record (the design review flagged that lineage-ABSENCE is inversely correlated with ownership, so APPLY must not infer consent from the act of pointing); (R10 architecture) adopted (b) one command + report front-end + shared floor, with UPDATE and APPLY as separate engines behind an injected Baseline. Both are framework evolution touching propagation AND onboarding. Open: R9 naming (/apply-framework + /onboard as thin alias).

---

## Turn 2 — steward (decision)
*2026-05-24T20:59:47.887322+00:00 | confidence: 0.86*
*tags: steward-gate, approve, prime-objective, consent, framework-evolution*

VERDICT: APPROVE (0.86), conditional on folding conditions 1-4 before /build_module; Principle #7 developer approval still required downstream. Ratified: (1) the unification is correct — it unifies only the genuinely-shared command shell + report front-end + floor primitive, and keeps UPDATE/APPLY as separate reasoning engines (R10), honoring not overriding their difference. (2) R8 option (ii) APPROVED against ADR-0015: writing a human-authored assent stub (the existing custodian block shape) into the target as deploy step zero satisfies refuse-extraction (a) attribution, (b) no third-party-benefiting labor without consent, (c) per-instance human-authored assent; option (i) pointing=consent FAILS test (c) because lineage-absence is inversely correlated with ownership. (3) R10 two-engines-shared-shell APPROVED (Principle #8 where it matters; floor by-construction preserved on both routes per #4). (4) R9 successor-ADR + /onboard-as-alias APPROVED (Principle #5). CONDITIONS to fold: (1) successor ADR records the inversion insight (lineage-absence inversely correlated with ownership -> APPLY needs the STRONGEST explicit assent) as first-class rationale; (2) assent stub must require a NAMED human + accepts_distribution:true and FAIL CLOSED — primary_human:null (the init_lineage default) must NOT satisfy the APPLY preflight (AC: null blocks, named passes); (3) the stub write executes INSIDE the branched deploy and obeys the clean-tree gate, so back-out (delete branch) reverts the stub (AC: after deletion the target carries no new custodian stub); (4) baseline_gate_green on APPLY defaults to skip, confirm-to-run as a DISTINCT logged operator act separate from the deploy confirmation (explicit AC). LEAN (developer call, not a condition): name /apply-framework, record final name + alias-vs-retire in the successor ADR.

---
