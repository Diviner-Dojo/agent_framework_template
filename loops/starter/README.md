# loops/starter/ — CORE recipe library (additive-merge)

Battle-tested, governance-flavored **goal-contract recipes** shipped with the framework.
Two jobs (one artifact, per ADR-0026 / SPEC-20260621-064937 R12):

1. **Seed the authoring interview** — the `authoring-goal-contracts` skill draws proven
   per-domain example criteria from here when proposing a contract.
2. **Directly instantiable** — copy a recipe into `../contracts/`, fill the blanks, run
   `/goal-loop`.

## Propagation contract (CORE)
This directory is **CORE**: `/apply-framework` propagates it to derived projects
**additively** (new starter recipes are added, never overwriting a project's own). It is
namespaced apart from `../local/` (project-promoted recipes, SKIN) specifically to avoid
the ID-collision class seen in past distributions. Treat `loops/` as **additive-merge,
never replace**.

## Recipe shape
A recipe is a goal-contract template (see `docs/templates/goal-contract-template.md`) with
`verify` / `termination` pre-filled for a common convergent task, plus attribution and a
short "use this when". Starter recipes land in task T7 of the Phase-1 build
(e.g. `docs-sweep`, `coverage-raise`, `regression-ledger-sweep`).

## Growing the library
When a `/goal-loop` run succeeds well, promote its contract into a reusable recipe via
`/promote` (Layer-3, human-approved). Project-authored recipes live in `../local/` (SKIN),
not here.
