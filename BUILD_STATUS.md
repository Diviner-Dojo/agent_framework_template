# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-05-24 — **`/apply-framework` BUILD COMPLETE** (SPEC-20260524-203931, ADR-0021 — drafted as ADR-0019, renumbered at merge). Quality gate 7/7, 114 tests (41 new), discussion `DISC-20260524-212509-build-apply-framework` sealed. **NOT committed/pushed — `/review` + education gate + commit are the developer's next steps.** Full re-entry brief: `docs/handoff/RESUME-apply-framework-build.md`. (Prior `/distribute` B1-floor work below is the committed base this built on.)

## ⮕ CURRENT — /distribute B1 mechanical floor + interpreted assessment (feat/distribute-b1-floor)

**Status: built, reviewed, re-confirmed APPROVE, committed (NO push — developer is merge authority).**
`SPEC-20260523-100224` implemented: R1 `value-unverified` mechanical floor; R2 `OverwriteDiff`/`triage_diff`
(new `scripts/distribute/assessment.py`); R3/R3a/R5/R6/R7 doc orchestration (`distribute.md`); R4 pure
`reclassify_route` + escalate-only `stage(exclude_paths=…)`; R8 secret-scrub; R9 **ADR-0017** (down-propagation
protocol, clears review B5). Review `REV-20260523-125823`: REQUEST-CHANGES → **APPROVE** — all 4 blocking
findings fixed and **independently re-confirmed** (qa-specialist + independent-perspective, reading worktree
paths). Original review's must-fix carry-overs **B2** (TOCTOU doc-path single-resolve), **B3** (`_bound_patterns`
500/500), **B4** (gate-bypass ⚠️ header) also folded. Quality gate **7/7**, 73 tests, coverage ≥80%.

**Open v1.1 advisories (carry forward):** (a) hub-side ancestor tracking / 3-way merge so a *proven-safe*
overwrite can resolve back to silent `value` (the deferred half of B1); (b) `stage()` backstop covers an
orchestrator that *forgets to halt* an escalated file but not one that *never populates* `exclude_paths` (only
relevant if orchestration is ported to Python); (c) disclaimer-exhaustion at scale — surface a secondary
"M are behavioral" count; (d) shared `secret_patterns` module vs. the `scripts/→.claude/hooks` `sys.path` import.

**Next after merge:** `--dry-run` vs the 3 real targets (each must first add `custodian.accepts_distribution`
— opt-in HARD GATE); then doc-sync (FRAMEWORK_SPECIFICATION + presentations) + version bump at `/ship`.

## ⮕ NEXT — /apply-framework unified command (SPEC-20260524-203931, APPROVED, ready to build)

**Cleared for `/build_module`.** Unifies `/distribute` (UPDATE) + `/onboard` (APPLY) into ONE command:
point at any project → UPDATE if it has the framework, APPLY if not → up-front value/risk report → deploy
gated on a clean tree, dedicated back-out branch, never push/auto-merge, one target at a time.
- **Gate trail:** design review `DISC-20260524-204142` (4 specialists, REVISE → mechanical fixes folded)
  → Steward gate `DISC-20260524-205732` (**APPROVE 0.86**) → **developer Principle-#7 APPROVED 2026-05-24**.
- **Settled decisions:** consent = **write a human-authored assent stub INTO the target** (named human +
  `accepts_distribution:true`, FAIL CLOSED); architecture = **two engines + shared shell** behind an injected
  `Baseline` protocol (`LineageBaseline`/`OnDiskBaseline`), one floor primitive tested against both; name =
  **`/apply-framework`** (`/onboard` → thin alias to the deeper takeover).
- **4 Steward conditions to honor in the build (already in the spec ACs):** (1) successor ADR records the
  inversion insight (lineage-absence inversely correlated with ownership → APPLY needs the strongest assent);
  (2) assent stub fail-closed (`primary_human:null` blocks); (3) stub written on the deploy branch so back-out
  reverts it; (4) `baseline_gate_green` on APPLY defaults to skip + distinct logged confirm-to-run.
- **Build base:** `feat/distribute-b1-floor` (reuses the B1 work `ef9a485` — change_package/assessment/
  stage_branch/repo_safety_check). New: router, `OnDiskBaseline`+`compute_greenfield_package`,
  `build_assess_report`+section-builders, feature/change interpretation, decomposed safety checks, the assent
  deploy-step-zero, the successor ADR (supersedes ADR-0017), and the full test suite incl. `greenfield_env`.

## Earlier context (ADR-0016 restructure, 2026-05-20)

**Token-efficiency restructure (ADR-0016) — executed, quality-gate-clean, awaiting commit gate.**

Branch: `chore/template-version-bump-3.5`. Plan file: `~/.claude/plans/i-think-my-claude-md-jazzy-manatee.md` (the authoritative spec for this work). Ratifying deliberation: `DISC-20260520-161826-efficiency-ledger-ratification` (panel ratified, no dissent).

**Done this session:**
- **CLAUDE.md**: 432 → 106 lines (~8.9K → ~3K tok). Added Always-On Invariants, Workflow Sequencing (incl. the ~95% confidence gate), a keyword-rich Rules Index, and docs/ pointers. Version bumped v3.4 → v3.5 (sync with pyproject).
- **Always-loaded footprint**: ~22K → ~3.8K tokens/turn (~83% cut); re-paid per specialist dispatch, so the real saving is larger.
- **Rules relocated**: `autonomous_workflow` kept always-loaded; `coding_standards`/`testing_requirements`/`security_baseline` **path-scoped** (`paths:` frontmatter); the other **11 rules → on-demand skills** under `.claude/skills/` (recovering-from-failures, notifying-the-developer, cross-agent-dispatch, multi-instance-dispatch, syncing-framework-docs, handling-micro-fixes, selecting-review-gates, searching-prior-art, running-build-checkpoints, committing-changes, documenting-decisions). NOTE: `commit_protocol` + `documentation_policy` were "CUT" in the ledger but conservatively converted to skills (no content loss) — flagged for /review.
- **docs/ created** (homes for content cut from CLAUDE.md): AGENT_ARCHITECTURE.md, CAPTURE_PIPELINE.md, HOOKS.md.
- **Confidence gate (Phase 2)**: always-on invariant in CLAUDE.md + formal Confidence Check in `/plan` (rule #5) and `/build_module` (build-start). Override + micro-fix exemptions included.
- **14 stale references repointed** to skills (build_module, ship, autonomous_workflow, facilitator, 2 skills, pre-commit-gate.sh). The functional break (build_module pre-flight existence check) is fixed.
- **ADR-0016** written (`scope: framework`, refs the DISC id).
- **Quality gate: 6/6 PASS** (formatting, lint, tests, coverage, ADRs, regression ledger; review-existence skipped pending /review).

**Status (2026-05-20, updated):** Developer replied GO. `/review` ran (REV-20260520-175237, APPROVE-WITH-CHANGES; blocking FRAMEWORK_SPECIFICATION corpus-drift finding fixed). Committed **1c4fe0c** to the branch (NOT pushed). Close-out done: FRAMEWORK_CHANGELOG propagation entry, adoption-log capture of the 7 Phase 0a candidates (+counts), FRAMEWORK_SPECIFICATION link fixes; validation passed (all 17 skills have valid frontmatter; 3 path-scoped rules' globs correct; tree clean of stale refs). Validation fidelity note: config correctness + the live skill-index were verified; the harness's *runtime* deferral of path-scoped rules / on-demand skill bodies is per Anthropic spec but not directly observable in one session — Phase 5 will exercise it. **Next: developer to choose push/PR vs Phase 5 (Howie co-migration first).** Won't-fix: upgrade-prompt doc paths (historical migration guide, like an ADR).

## Pending follow-on (approved, not yet executed)
- **Phase 3**: tooling hygiene — verify/disable the `sqlite` MCP (confirm no dependents first); de-dupe the 8× pre-flight Python block into `scripts/preflight.py`.
- **Phase 4**: offload deterministic in-context work to CLI/hooks (ADR supersession graph, adoption rule-of-three counter, coverage-gap report, spec-status, frontmatter validation).
- **Phase 5**: co-migrate howie / agentic_journal / VerificationPortal (content-analysis FIRST, preserve their domain rules/agents).
- **Phase 6**: `scripts/route.py` deterministic dispatch routing (sole authority; via /plan + /review). Structural win (ends risk→specialist table triplication), modest token win.
- **Phase 7**: `/retro` non-destructive consolidate cadence.
- **ADR-0016 follow-ups**: update `docs/FRAMEWORK_SPECIFICATION.md` (rule count 15→4 always-loaded + skills count) + presentations via the `syncing-framework-docs` skill; add an entry to `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`; log the Phase 0a adoption candidates to `memory/lessons/adoption-log.md`.

## Carried-forward architectural debt (from prior sessions)
- arch-F2 `/promote --list-promoted`; arch-F3 canary contract enforceability; arch-F5 swallow-and-warn ADR; confabulation/dispatch-grounding fix (DISC-20260516-062518); quality_gate `_parse_regression_ledger` table-distinction refactor; presentation slide 3 Prime Objective element.

## Previous Session (2026-05-16)

**PR #7 merged** (`35d4fab` on main): Phase 0 + spawn fix + Path 4 (Prime Objective / ADR-0015) + docs sync. ADR-0015 propagation pushed to `~/.claude/shared-memory/` at `c9ae948`. **Phase 0 education gate COMPLETE** (EDU-20260516-phase0, 4/4 in `education_results`). Post-merge triage: 6 commits stacked on `chore/post-merge-triage` (B1 /conversation, B2 /status, B3 efficiency_report, C2 telemetry prompt, Cat D adoption-brief snapshot, defer-Phase-1). **Phase 1 deferred** (`SPEC-20260516-045622` → `status: deferred`; rationale: cost-reduction rationale structurally weak, build when Howie drives real demand). Discards: copilot-adaptation-guide, session narrative, phase1-handoff, phase-1-kickoff-prompt. Open then: push triage branch + open PR; local cleanup after merge.

## Previous Session (2026-05-15)
(See git history `cf3d7da` and earlier — Phase 0 build + review + commit narrative.)
