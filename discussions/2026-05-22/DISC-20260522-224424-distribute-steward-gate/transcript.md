---
discussion_id: DISC-20260522-224424-distribute-steward-gate
started: 2026-05-22T22:44:52.386041+00:00
ended: 2026-05-22T22:46:31.718054+00:00
agents: [facilitator, steward]
total_turns: 3
---

# Discussion: DISC-20260522-224424-distribute-steward-gate

## Turn 1 — facilitator (evidence)
*2026-05-22T22:44:52.386041+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Steward gate before building a new reusable /distribute command that propagates framework updates from the hub to derived projects (firmware-update style): assess fit/harm per target in the target's loaded context, stage on an isolated branch, notify; only involve the human when risk can't be mediated.
- **Files/scope**: new .claude/commands/distribute.md + scripts/distribute/{repo_safety_check,change_package,stage_branch}.py; reuses lineage/drift, spawn_project, capture pipeline, notify/ask_developer, quality_gate. Approved plan exists.
- **Developer-stated motivation**: keep derived projects in sync in an orderly way (e.g. broadcast the ntfy remote-approval feature) without manual round-trips; be involved only when risk is unmediable.
- **Explicit constraints**: 'push the proposal, pull the apply' — nothing auto-merges to a target's main; human is always the merge authority; pinned_traits are absolute (never overwritten); harm/quality-gate detection before staging; least-complex intervention (Principle #8).

---

## Turn 2 — steward (decision)
*2026-05-22T22:46:31.606023+00:00 | confidence: 0.86*
*tags: steward-gate, verdict:revise*

REVISE (0.86). Extraction analysis CLEARS: hub->target flow cannot trip Prime Objective (c); staged-not-merged keeps the labor of adoption with the party who benefits; attribution preserved via distribution_log. But 2 consent gaps remain (cheap, load-bearing for 'distribute not concentrate'):
(1) TARGET OPT-IN — a target should declare in its OWN manifest whether it accepts distribution at all (e.g. custodian.accepts_distribution: true/false, or per-path allow/deny). Staging unrequested branches into a repo that never asked is divergence-pressure even unmerged; it makes 'do nothing' require active refusal. Per-instance assent applied symmetrically = the target consents to BEING a distribution target, not just to each merge.
(2) ASSESSMENT DOC must be explicitly ADVISORY / target-overridable — the hub verdict has no authority over the target; the human-merge gate is what preserves autonomy; say so plainly.
Plus: (3) justify the 3-agent room vs Principle #8, or fast-path obviously-inert + reserve the room for unmediable-candidates; (4) cross-repo CONFIDENTIALITY — target context read-only in the hub room, 'ready' ntfy carries no target-internal content; (5) keep pinned-trait conflict as an UNMEDIABLE halt, never downgrade to inert. Does NOT authorize build; developer approval gates next (Principle #7).

---

## Turn 3 — facilitator (synthesis)
*2026-05-22T22:46:31.718054+00:00 | confidence: 0.85*
*tags: synthesis, steward-gate*

## Request Context
- Steward gate on the proposed /distribute capability before build.
- Constraints: push-proposal/pull-apply; pinned_traits absolute; human is merge authority; least-complex (Principle #8).

## Synthesis — verdict REVISE
The hub->target direction is benign on extraction; the design's spine (push-proposal/pull-apply, pinned-traits-absolute, harm-detection, human-as-merge-authority) is the right shape and improves on STEWARD_ARCHITECTURE 7.3. Five required revisions before build; the load-bearing one is TARGET OPT-IN (symmetric consent — a target consents to BEING a distribution target via its own manifest, not just to each merge). Recommend folding all 5 into the design, then developer approval (Principle #7) -> /build_module. Next: developer decision.

---
