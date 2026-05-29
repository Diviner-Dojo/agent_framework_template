---
discussion_id: DISC-20260523-191709-session-wrapup-steward-gate
started: 2026-05-23T19:17:28.205429+00:00
ended: 2026-05-23T19:19:37.797741+00:00
agents: [facilitator, steward]
total_turns: 2
---

# Discussion: DISC-20260523-191709-session-wrapup-steward-gate

## Turn 1 — facilitator (evidence)
*2026-05-23T19:17:28.205429+00:00 | confidence: 0.8*
*tags: context-brief, steward-gate*

## Request Context
- **What was requested**: Steward gate for SPEC-20260523-110504 (model-aware session wrap-up + handoff, ADR-0018) — a framework-evolution change that alters the DEFAULT behavior of every session and adds an auto-launch-a-fresh-agent capability.
- **Files/scope**: New config + src/context_sensor.py + thin hooks + wrapping-up-sessions skill + /handoff command; modifies default session lifecycle. Spec already passed specialist spec-review (DISC-20260523-190838, sealed): architecture APPROVE-WITH-CHANGES, security+qa REVISE, all blocking findings folded.
- **Developer-stated motivation**: Long sessions degrade (context rot) and cost more per turn; framework only reacts at lossy ~83% auto-compaction. Wants proactive, model-aware, clean handoffs as default.
- **Explicit constraints**: Developer LOCKED auto-launch as the DEFAULT trigger action. The security review elevated a consent concern: auto-launch-by-default spawns OS processes and continues work autonomously, which touches Prime Objective clause (c) (per-instance human-authored assent) and Principle #7 (human approval). Mitigation already in spec: a SEPARATE explicit ALLOW_AUTO_LAUNCH_SESSION key (distinct from the general autonomous-auth gate) + MAX_AUTO_LAUNCH_DEPTH=1. The Steward must rule whether the default-auto-launch posture, as gated, is consistent with PHILOSOPHY.md or requires revision.

---

## Turn 2 — steward (decision)
*2026-05-23T19:19:37.797741+00:00 | confidence: 0.88*
*tags: steward-gate, verdict, revise, prime-objective*

## Steward verdict: REVISE (0.88)

Intent + mechanism are sound and mission-aligned (serves contributors: preserves reasoning quality, cuts per-turn cost; not process-for-its-own-sake). The dual-key consent (Autonomous Execution Authorization + separate ALLOW_AUTO_LAUNCH_SESSION) IS consistent with Prime Objective (c) and Principle #7 — both keys are human-authored per-instance assents, and the launch inherits all Prohibited Actions (no push/main/merge), so value cannot escape to a third party or to main without a fresh human act. This is the in-session analogue of /distribute's 'push the proposal, pull the apply.' The default does NOT need demoting to offer-only for the developer's own consented sessions.

REVISE (not APPROVE) because the spec prose lets 'default' read as 'framework ships spawning by default' (mechanism B) when R7 actually implements 'auto-launch only when both consent keys present' (mechanism A). On a high-risk, default-changing, DISTRIBUTED capability that ambiguity is unacceptable.

**4 conditions (all before /build_module; does NOT need to return to Steward after folding):**
1. **Disambiguate 'default' (blocking):** shipped/fresh-clone/non-opted-in posture = handoff + OFFER; auto-launch is operative ONLY when BOTH consent keys present (both human-authored). Rewrite Goal/Context prose; ADR-0018 records the consent-default decision + why (b)/(c) require it.
2. **Distribution must not flip the consent default (blocking, clause c):** /distribute NEVER stages or sets either consent key in a target; the derived project's human authors both keys themselves. Name ALLOW_AUTO_LAUNCH_SESSION + the per-model threshold numbers as pinned-trait candidates. ADR Consequence.
3. **Handoff preserves lineage + open obligations (blocking, Principles #1/#2/#4/#6):** R6 template MUST carry active DISC/SPEC/ADR IDs (have), open /review advisories, un-completed education-gate deferrals, and an explicit 'continuation inherits CLAUDE.md and MUST run /review before any commit.' Add an AC asserting the template renders these. A continuation bypassing capture/review must be structurally impossible.
4. **v2 coercion behind its own future Steward gate (Principle #8):** ADR-0018 states the coercive Stop-hook (v2) is NOT authorized by this gate; it returns for a separate Steward gate + developer approval when proposed.

Governance path confirmed correct: spec-review (done) -> THIS Steward gate -> developer approval (Principle #7) -> /build_module -> quality gate -> /review -> doc-sync. ADR-0018 right home (0017 owed to /distribute). Record consent-default + v2-deferral as ADR content (Principle #5). Non-blocking: A-ARCH-6 multi-worktree session_id resolution worth a memory/bugs/ regression note.

---
