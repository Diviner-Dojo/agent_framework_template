# Build Status

> Read at session start; update before compaction.
> Last updated: 2026-05-27 — **NEW: async collaboration-loop (ADR-0019) REVIEWED + COMMITTED** (`915c142` + spec-complete `52d51eb` on `feat/async-collab-loop`). Plus prior parked threads (`/distribute`, ADR-0018 session-wrapup, META-REVIEW).

## ⮕ NEXT SESSION — START HERE

### ✅ DONE this session (2026-05-27) — async collaboration-loop (ADR-0019)
Full workflow completed end-to-end: `/review` (`DISC-20260526-161231`, report `docs/reviews/REV-20260526-161231.md`, **approve-with-changes, 0 blocking**, panel security/qa/architecture/docs-knowledge) → 4 advisories applied (shim untrusted-input docstrings; skill count corrected 17/18→**19** across FRAMEWORK_SPECIFICATION + 2 presentation HTMLs; `test_poll_mode_dispatches_to_poll`; `@pytest.mark.regression` on `test_error_message_never_contains_topic_value`) → quality gate **7/7**, 112 tests → education gate **7/7 mastery** (`/walkthrough` `DISC-20260526-164119` + `/quiz` `DISC-20260526-164631`) → **committed `915c142`** (staged my files only, explicit add) + spec marked complete `52d51eb`. SPEC-20260525-233208 status: complete. **Commit note:** used `git commit --no-verify` (developer-authorized) for `915c142` — the review-existence check false-negatived on a midnight rollover (review dated 2026-05-26, commit on 2026-05-27); all other gate checks passed 6/6.
**Deferred (optional, non-blocking, in the REV report):** 3 speculative advisories (poll-`since` comment; `match_choice` empty-list test; stronger ask-error type-name assertion) + arch's optional SPEC R3 superseding note.
**Latent framework bug surfaced (separate fix):** the `/review` self-healing query errors with `IndexError` on the `v_rule_of_three` view (column-name mismatch — expects `pattern_key`/`sighting_count`). Best-effort step, skipped gracefully.
**Not pushed** (no remote push without explicit consent); not yet merged to main. `/promote`: 3 promotion candidates surfaced.

### Parked threads (pre-existing, still open)

**Handoff artifact:** `docs/handoff/HANDOFF-20260523-161305.md` (paste-ready continuation prompt; gitignored).
**ADR-0018 is COMMITTED (`99000d5` on `feat/session-wrapup`) + LIVE** (settings.json wired + validated; hard nudge fired on this session = proven end-to-end). Remaining = non-urgent follow-ups below.

**Freshest thread — ADR-0018 "model-aware session wrap-up & handoff":**
Full workflow ran: `/plan` (SPEC-20260523-110504, approved) → spec-review (`DISC-…-190838`) → Steward gate (`DISC-…-191709`, REVISE→4 conditions folded) → `/build_module` (core `src/context_sensor.py` 92% cov, 63 tests) → checkpoint (`DISC-…-192249`) → quality gate **7/7** → `/review` (`DISC-…-224536`, **APPROVE**, report `docs/reviews/REV-20260523-224536-session-wrapup.md`). All 2 blocking review findings fixed. **Remaining (uncommitted):**
1. **Developer to commit** on `feat/distribute-command` (or a new branch) — NO push. (Files: `src/context_sensor.py`, `config/model_context_profiles.yaml`, `.claude/hooks/context-{statusline,guard}.{sh,py}`, `.claude/skills/wrapping-up-sessions/`, `.claude/commands/handoff.md`, `docs/templates/handoff-template.md`, `docs/adr/ADR-0018-*.md`, `tests/test_context_sensor.py`, edits to `.gitignore`/`pre-compact.ps1`/`CLAUDE.md`/regression-ledger.)
2. **MANUAL ACTIVATION (feature is inert until done):** add `statusLine`, a `UserPromptSubmit` hook, and the `CLAUDE_AUTOCOMPACT_*` `"env"` keys to `.claude/settings.json` (protected file → manual). `/handoff` works without this; the auto-nudge does not. Diff handed to developer at build close.
3. **Owed before `/ship`:** doc-sync (FRAMEWORK_SPECIFICATION §6/§14/§15 + 2 presentation HTMLs for the new command+skill+config); version bump v3.5→v3.6.
4. **v1.1 advisories (from /review IP):** A2 soft cap maybe too eager on 1M (revisit w/ usage data — developer chose quality-first); A3 add a liveness canary (degradation is silent); A4 instrument nudge-fired-vs-ignored (no measurement story). **v2 (separately Steward-gated):** coercive Stop-hook block.

**Prior parked thread — `/distribute`** (neither urgent). **Recommended next: finish `/distribute`** (it's bounded, and the Steward says it's the propagation channel the meta-review fixes all depend on). Concretely:
1. Fold the cheap `/distribute` must-fix from the review: **B2** (stage_branch.py:200↔218 reuse the validated doc path), **B3** (bound accept/deny fnmatch patterns), **B4** (mandate the `stage-for-manual-review` gate-bypass warning in distribute.md). Plus quick qa tests (no-DB→diverged, custodian non-dict/null, all 6 in-progress markers, commit-failure rollback).
2. **Decide B1** (the one needing developer judgment): surface per-file `value` diffs in the assessment doc now (v1 mitigation) vs. defer the full hub-side-ancestor 3-way-merge to v1.1.
3. Then `--dry-run` vs the 3 real targets → commit on branch (NO push; developer merges).
**Deferred (fresh-head decisions, Steward-gated):** meta-review items D (educator re-aim), E (verification-challenges-assumptions rule), A (domain-tiered panels); and 3 open strategic questions (below).

## Current Task: build the `/distribute` command (new framework capability)
**Branch:** `feat/distribute-command`. **Authoritative spec:** `~/.claude/plans/i-think-my-claude-md-jazzy-manatee.md` → top section "# Plan: `/distribute`".

**Status:** Plan APPROVED. Steward gate complete → verdict **REVISE** (`DISC-20260522-224424-distribute-steward-gate`, sealed). Developer **APPROVED** folding all 5 Steward revisions. Open decision **RESOLVED 2026-05-22: opt-in is a HARD GATE (skip non-opted-in targets), not a warning.** All 5 revisions **FOLDED** into the plan (`~/.claude/plans/…jazzy-manatee.md`, "Steward revisions" block + flow steps 2a/2d/2e). Next: `/build_module`.

**The 5 Steward revisions (FOLDED 2026-05-22):**
1. **Target opt-in = HARD GATE.** A target declares assent in its OWN `framework-lineage.yaml` (`custodian.accepts_distribution: true|false`, optional per-path `accept_paths`/`deny_paths`). Checked in safety preflight (2a-i); non-opted-in target is **SKIPPED on the write path** (recorded + low-priority ntfy). `--dry-run` is pure-read and still shows route `SKIPPED (opt-in absent)`. Per-instance assent token — same absolute shape as `pinned_traits`. The 3 real targets must add the flag before `/distribute` writes to them.
2. Assessment doc explicitly **ADVISORY / target-overridable** (hub verdict has no authority over the target).
3. Justify/scope the 3-agent room vs Principle #8 — fast-path obviously-inert with a single risk-referee; reserve the full room (feature-advocate + target-advocate + referee) for unmediable-candidate changes.
4. Cross-repo **confidentiality** — target context read-only in the hub room; the "ready" ntfy carries only target name + route + counts (no target-internal content).
5. Pinned-trait conflict stays an **UNMEDIABLE halt**; never downgrade to inert. (Already in design.)

**Build sequence remaining:** ~~fold~~ ✓ → ~~`/build_module`~~ ✓ → ~~tests~~ ✓ → ~~quality gate~~ ✓ → ~~`/review`~~ ✓ (REQUEST-CHANGES) → **address must-fix (NEXT, pending developer scope decision)** → `--dry-run` vs the 3 real targets → commit on branch, **NO push**, developer merges.

**`/review` complete (2026-05-23, `DISC-20260523-065026-review-distribute`, sealed; report `docs/reviews/REV-20260523-065900.md`). Verdict: REQUEST-CHANGES** (4/5 specialists request-changes; architecture approve-with-changes). Mechanical safety verified solid. Independent panel caught a Prime-Objective blind spot the build checkpoints + test fixture shared.
**Open advisory ledger (persist):**
- **B1 (Prime Objective, design)** — `value` classification trusts the target's *mutable* baseline DB as the hub-target common ancestor; a target re-baselined after a local edit (or with narrowed `tracked_paths`) gets its edit clobbered, mis-labeled "safe update", shown with no detail. *v1 mitigation: surface per-file `value` diffs in the assessment doc. v1.1: hub-side ancestor tracking / 3-way merge.* **Needs developer scope decision.**
- **B2** stage_branch.py:200↔218 — reuse validated doc path (TOCTOU). *cheap code fix.*
- **B3** bound accept/deny fnmatch patterns at load. *cheap code fix.*
- **B4** distribute.md — mandate gate-bypass WARNING header for `stage-for-manual-review` + `gate_bypassed:true` lineage field. *doc fix.*
- **B5** write **ADR-0017** (down-propagation protocol; ADR-0003 deferred this axis). *governance, owed.*
- **B6** manifest schema awareness — seed `accepts_distribution:false` in init_lineage + type-check in manifest_validate + template comment.
- **qa tests** — no-DB→diverged, custodian non-dict/null, all 6 in-progress markers, commit-failure rollback.
- **Advisory/v1.1**: Scenario D (dirty-check before forced restore), Scenario B (surface/halt-ask base), Scenario C (config-activating forces full room), CLAUDE.md pointer + FRAMEWORK_CHANGELOG entry, distribution_log schema, STEWARD_ARCHITECTURE Phase 5 superseded note.

## Framework META-REVIEW (2026-05-23, `DISC-20260523-071535-meta-review-20260523`, sealed; report `docs/sprints/META-REVIEW-20260523.md` left **status:draft** pending developer rulings)
Augmented macro/double-loop run with the **hub denominator** (cross-instance telemetry: agentic_journal 657d/3915t = ~85% of all use; VerificationPortal backend, quiet since 2026-05-16; howie newly online; template = lab). Opus panel: architecture-consultant + independent-perspective + steward.
**Steward verdict: APPROVE (0.88) — the framework is SOUND and achieving its ends** (constitutional layer works; the `/distribute` Principle-#4 catch is the proof). Panel corrected the draft on 3 counts:
1. **survival_pct demoted from headline to hypothesis** — the hub can't compute it (no column/compute/view; defined only in agentic_journal), it contradicts a recorded baseline (indep-perspective 0% vs my 11%), and a week-old synthesis called it not-yet-trustworthy. Honest finding: *we lack a trustworthy impact metric — and that IS the finding.* (Directional pattern — low survival + advisory flood + domain misfit — still corroborated across VP+IJ.)
2. **Education re-aim = ADR-0012 (already accepted; educator already rebuilt).** Developer's reframe CONFIRMS it; real gap is propagation/gate-invocation downstream; "possibility-space" framing may EXTEND ADR-0012. Steward affirmed it in full as the most important (values-level) finding.
3. **Draft measured mechanics, not ends.** The only real ends-test (education gate) had to be human-supplied → the instrument can't tell slack from values-failure alone. Recursive: meta-review.md ITSELF queries hub-absent columns (latent bug, swallowed by `except`).
**Steward sequencing:** F (finish /distribute) → B (survival metric + schema sync) → A (domain-tiered *selection-sets*, not new agents). **Gate-required (directions pre-approved, implementations gated):** D educator re-aim, E "verification must challenge its own assumptions" rule (argue prompt-vs-rule per #8), A dispatch-defaults.
**3 open strategic questions for the developer (fresh head):** (1) is 90% finding-discard even bad — what's the *right* survival rate? (2) is the whole apparatus overfit to agentic_journal? (3) **did framework OVERHEAD stall VerificationPortal** (went quiet 2026-05-16)? — Steward calls this a Prime-Objective question worth a focused dispatch.
**Honesty edit owed if report is finalized:** name the advisory flood (5.5:1, ~6% survival) as *values-adjacent* drift (process-for-its-own-sake, PHILOSOPHY.md:5), not pure execution slack.
**Memory updated:** `user_education_perspective.md` deepened (possibility-space + manager↔agent comprehension gap + Principle-#7 stakes).
**Not yet done (deferred, low-load):** the narrative slice (journey.md chapter + current-arc.md) — optional re-entry nicety; BUILD_STATUS covers re-entry.

**BUILD COMPLETE (2026-05-23, `DISC-20260523-061604-build-distribute`, sealed).** `/build_module` produced: `scripts/distribute/{__init__,_git_utils,repo_safety_check,change_package,stage_branch}.py` + `.claude/commands/distribute.md` + `tests/test_distribute.py` (32 tests, all pass). Quality gate **7/7** (coverage ≥80%, lint+format clean). 3 checkpoints fired: qa+security on `repo_safety_check` (REVISE→resolved: fail-closed git-dir sentinel, OSError wrap, malformed-YAML catch, ACE docstring); security+architecture on `stage_branch` (REVISE→resolved: validate base+original_branch refs, try/finally rollback, source-side path containment, shared `_git_utils`, public `detect_base_branch`); security on `distribute.md` (APPROVE 0.92). Round-2 confirmations skipped (no SendMessage continuation; fixes verbatim). Reflections deferred (cost; critiques captured in transcript). **Open advisory for /review:** confirm `stage-for-manual-review` can't promote a RED-gate branch to "ready".

**Reuse (don't rebuild):** `scripts/lineage/drift.py` (`drift_scan` + pinned-trait match), `scripts/lineage/manifest.py`, `scripts/spawn_project.py` (`FRAMEWORK_DIRS`/`FILES`, cross-repo `subprocess`), capture pipeline, `scripts/notify.py` + `ask_developer.py`, `scripts/quality_gate.py`, analyze-project/batch-evaluate patterns.

## Async loop state
- state: **closed** — do NOT re-arm next session (no Monitor was armed this session).
- resume recipe (if ever re-armed): `python scripts/collab_loop.py check 48h <choices>` then arm a persistent Monitor on `… poll <choices>` (check-before-poll, Lesson 1 / ADR-0019).
- monitor: none
- pending question: none

## Gotchas
- **PowerShell is sandbox-blocked here — use the Bash tool** (git-bash, `/c/...` paths).
- **Review-existence check is date-scoped** (`REV-<today>*.md`, local+UTC) — a `/review` done before midnight false-negatives on a next-day commit; can't pass `--skip-reviews` through `git commit` (hook doesn't proxy it) and the 5-min verification-cache window does NOT suppress the hard check. Resolve with developer-authorized `--no-verify` or a today-dated review note.
- The pre-push hook over-matches "main" in a refspec — push feature branches with clean refspecs; never push to main; **pushing is prohibited without explicit developer confirmation.**
- Targets are separate repos at `C:\Work\AI\{howie_family_wiki,agentic_journal,VerificationPortal}` — operate via absolute paths + `git -C`.

## Previous Session (2026-05-20) — Token-efficiency restructure (ADR-0016), DONE
Always-loaded corpus 22K→~3.8K tok/turn; CLAUDE.md 432→106 ln; 11 rules→skills, 3 path-scoped; 95% confidence gate added; HTML guides → v3.5 + POC banner + "Getting the Most Out of It" pitfalls slide. Merged to private `main` (8336988); promoted to public Diviner-Dojo via **PR #97 (merged)**; public + private + local `main` all content-synced. Parked Phases 3-4/6-7 (tooling / CLI offload / `route.py` deterministic routing / `/retro` consolidate). **Phase 5 co-migration is now SUBSUMED by `/distribute`.**
