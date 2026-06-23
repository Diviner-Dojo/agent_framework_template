# loops/contracts/ — goal-contract instances (SKIN, project-local)

The actual `GOAL-YYYYMMDD-HHMMSS-slug.md` contracts this project runs `/goal-loop` against.
Authored via the `authoring-goal-contracts` skill (never hand-filled from blank), or emitted
by `/plan` from an approved spec's acceptance criteria (`derived_from: SPEC-…`).

## Propagation contract (SKIN)
This directory is **SKIN**: `/apply-framework` **never overwrites** it. Your goal contracts
are project-specific work product and belong to this project.

## Lifecycle
- A contract is the loop's working artifact. For a `derived_from` contract, the SPEC is the
  upstream source of truth and the contract is a single-direction projection of it.
- On completion, the contract is sealed alongside the run's discussion
  (`DISC-…-loop-<slug>`); lifecycle completion writes back to the originating spec when there
  is one.

See `docs/templates/goal-contract-template.md` for the schema and ADR-0026 for the design.
