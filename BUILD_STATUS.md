# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-05-20 (token-efficiency restructure executed; awaiting commit-gate GO/HOLD via ntfy)

## Current Task

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

**Awaiting:** developer GO/HOLD via ntfy (background poll `boko19fjq`). GO ⇒ run the required `/review`, commit-on-pass to the branch (NO push). HOLD ⇒ stop for developer diff inspection. Default after 1h = HOLD.

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
