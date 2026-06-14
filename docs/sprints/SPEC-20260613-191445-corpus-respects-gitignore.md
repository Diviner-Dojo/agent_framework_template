---
spec_id: SPEC-20260613-191445
title: "Framework corpus builder respects .gitignore (so /apply-framework propagates value to every target)"
type: spec
status: reviewed
risk_level: medium
reviewed_by: [architecture-consultant, qa-specialist, security-specialist]
discussion_id: DISC-20260614-021541-corpus-respects-gitignore-spec-review
intake_ids: []
completed_at:
completed_commit:
---

## Goal
Make the framework corpus enumerator (`collect_framework_files`) exclude what git already
excludes, so `/apply-framework` actually offers the framework's value (`scripts/`, `docs/`,
ADRs) to every target — and so a future uncommitted framework file is never *silently*
withheld. Eliminate the whole bug class with fail-loud guards instead of silent truncation.

## Context
`/apply-framework` "failed to add the value that lives in the framework" to
`dan_research_karpathy_wiki`; afterward `/status` failed on the target because its backing
script (`git_visualize.py`) was never deployed.

**Root cause (confirmed empirically, 2026-06-13):** `scripts/lineage/_utils.py`
`collect_framework_files()` walks each `FRAMEWORK_PATHS` prefix with `rglob("*")` and
excludes **nothing**. Measured in the hub right now: raw corpus = **11,234** files, of which
**10,948** are gitignored external-repo clones left under `.claude/worktrees/external-analysis/`
by `/analyze-project` (2026-05-15), plus **117** other junk files (`__pycache__/*.pyc`,
`.claude/hooks/.state/*`, `settings.local.json`, `lineage-events.jsonl`,
`context-occupancy*.json`). `greenfield_offer_set()` sorts the corpus and caps at
`MAX_GREENFIELD_OFFER = 5000`; `.claude/` sorts before `scripts/`/`docs/`, and
`.claude/worktrees/` alone exceeds the cap — so the iterator **never reaches `scripts/` or
`docs/`**. Nothing of value is offered, and the cap is hit silently.

**Prior art / constraints already in place:**
- **ADR-0017** (down-propagation protocol) and **ADR-0021** (framework-apply unification)
  govern this path. `change_package.py` carries a **B1 mechanical safety floor**
  (regression-ledger 2026-05-23 / 2026-05-24) that classifies unprovable overwrites as
  `value-unverified` (staged + always surfaced). **This fix is *upstream* of the B1 floor —
  a corpus-definition change — and must not alter floor behavior.**
- Fail-loud-over-silent is an established framework discipline (e.g. `DRIFT_REMEDIATION_HINTS[kind]`
  raises `KeyError` rather than `.get()` silently blanking).

**Blast radius:** `collect_framework_files` is the single source of truth, imported by FOUR
callers — `scripts/distribute/change_package.py`, `scripts/distribute/router.py`,
`scripts/lineage/drift.py`, `scripts/lineage/init_lineage.py`. Fixing it at the source fixes
all four consistently (the desired outcome), but the design must keep drift detection,
manifest baselining, and both distribute routes correct.

> **Revised after specialist review (DISC-20260614-021541, unanimous APPROVE-WITH-CHANGES).**
> Blocking folds: SEC `.resolve()` invariant (R1), QA cap-signal contract (R4) + target-side
> test (R5), ARCH warn-relocation (R3) + explicit git probe (R1).

1. **R1 — Respect git's exclusions (preferred path).** When `project_root` is a git repo,
   enumerate each framework path via `git ls-files` (tracked files only). Mandatory details:
   - **Explicit repo probe** (ARCH): decide repo-vs-non-repo with
     `git -C <root> rev-parse --is-inside-work-tree`. A non-zero/error on the **probe** → not a
     repo → R2 fallback (legitimate). A non-zero/error on **`ls-files` after a positive probe**
     → **fail loud** (raise), do NOT silently degrade to the predicate.
   - **`.resolve()` invariant** (SEC, BLOCKING): `collect_framework_files` resolves
     `project_root` to an absolute path *internally* before constructing any git argv — an
     absolute path cannot begin with `-`, closing argument-injection (a `project_root` string
     beginning with `-` would be read as a git flag). `change_package.py`'s CLI path passes an
     unresolved `Path(template_root)`, so the invariant must live in the util, not the callers.
     Add a belt-and-suspenders leading-dash guard.
   - **Safe invocation** (SEC): `["git", "-C", root_str, "ls-files", "-z", "--", prefix]`,
     `subprocess.run(..., capture_output=True, timeout=15)`, no `shell`. Parse the output by
     splitting on `b"\x00"` (the `-z` NUL delimiter) — **never** `splitlines()` (a filename with
     an embedded newline could smuggle a fake corpus entry). Catch `OSError`/`TimeoutExpired`
     (covers git-not-on-PATH, which raises `FileNotFoundError`, not a non-zero exit) → fallback.
   - Hashing of the resulting files is unchanged. File-type framework paths (e.g. `CLAUDE.md`)
     are enumerated via `git ls-files -- CLAUDE.md` (single entry), preserving the current
     `is_file()` behavior.
2. **R2 — Non-git fallback (required, not optional).** When the probe says `project_root` is NOT
   a git repo, fall back to the existing `rglob("*")` walk **plus** a single EXCLUDE predicate
   applied to the **forward-slash-normalized** relative key in ONE place (SEC — not the raw
   `relative_to()` output): starts-with `.claude/worktrees/`; contains `/__pycache__/` or
   endswith `.pyc`; starts-with `.claude/hooks/.state/`; endswith `settings.local.json`;
   == `.claude/custodian/lineage-events.jsonl`; basename startswith `context-occupancy`. Both
   paths must produce the same forward-slash relative **key set**. The predicate is a
   best-effort exclusion of *framework-shaped* junk for genuinely-non-git roots — it is NOT a
   general `.gitignore` emulation and cannot know a target's project-specific ignores (a real
   git target always takes R1, never the predicate; see ADR scope note).
3. **R3 — Surface withheld value (untracked-but-wanted), warn at the apply layer** (ARCH —
   relocated out of the low-level util). `collect_framework_files` **detects** untracked
   (not-ignored) files under the framework paths on the git path and **returns** them alongside
   the hash map (it has the git info cheaply); it does NOT print. The **apply/distribute layer**
   (`greenfield_offer_set` / `/apply-framework` orchestration) emits the LOUD warning naming the
   files — they will NOT propagate until committed. (Live example today:
   `.claude/skills/orchestrating-lean-dispatch/SKILL.md` is untracked.) drift/router/init_lineage
   may ignore the untracked set (one-line). Return shape (hashes + untracked) finalized at build
   as a small dataclass or `(hashes, untracked)` tuple.
4. **R4 — Symmetric cap guard, with pinned signals** (QA — BLOCKING). In `greenfield_offer_set()`
   (the cap site — NOT the shared util, since drift passes a legitimately-narrowed `tracked_paths`):
   - oversize (`len(corpus) > cap`) → **raise `ValueError`** (never silently truncate);
   - suspiciously empty (the hub's full corpus resolves to 0 files) → **`warnings.warn(...)`**
     (an anomaly needing attention, not a crash).
5. **R5 — Regression tests** (QA — concrete list; reuse `_init_repo`/`_g`/`_commit_all` fixtures).
   Mandatory `@pytest.mark.regression` for the confirmed bug; ledger entry written **before**
   commit. Cover: (a) gitignored junk dir under `.claude/` absent from output and unable to reach
   the cap [regression]; (b) untracked-but-wanted file is returned and triggers the apply-layer
   warning, and does NOT fire for gitignored files; (c) non-git fallback excludes junk —
   **parametrized over all 6 sub-conditions**; (d) target-side enumeration (`router.py`, root =
   target, as a **real git repo**) excludes the target's own gitignored junk and does not trigger
   a spurious `ROUTE_PARTIAL`; (e) `drift_scan` no longer reports gitignored junk as `added`
   (divergence-distance shift); plus edge cases — empty repo → `{}`; `CLAUDE.md` file-type path
   collected exactly once; git-not-on-PATH (`FileNotFoundError`) → fallback, no crash; non-zero
   exit on a non-git dir with git present → fallback; tracked symlink listed as its own entry;
   git-path vs fallback **key sets equal**. Update the weak `test_offer_set_is_bounded_and_sorted`
   to assert `cap_hit is False` on a clean corpus.
6. **R6 — ADR.** Framework-scoped ADR documenting the corpus-definition change, its relationship
   to ADR-0016/0017/0021 and the B1 floor, the fail-loud decisions, the **cap's role shift**
   (from "silent pollution absorber" to "fail-loud bound on a legitimately-large corpus" — vs
   ADR-0021 §7), and the **honest scope of the fallback denylist** (framework-shaped junk only).

## Constraints
- **Must not alter the B1 safety floor** (`change_package._classify`) or its
  `value-unverified` routing — this change is strictly upstream (which files enter the corpus).
- `git ls-files` must run with `-C <project_root>` (NOT the process cwd) — `collect_framework_files`
  is called with the **target** as root in `router.py`, not only the hub.
- Cross-platform: outputs must be forward-slash normalized (git already emits forward slashes;
  the rglob path already does `.replace("\\", "/")`).
- Subprocess discipline (`security_baseline`): construct the git argv as a list (no shell), do
  not interpolate untrusted strings; treat a non-zero git exit as "not a git repo / fall back",
  never crash the caller.
- Regression-ledger rows: no literal `|` inside backticks (parser gotcha).
- **Known-broken to avoid:** do not "fix" this by raising the 5000 cap — that masks the bug
  (a polluted corpus would still bury `scripts/`); the cap is a safety bound, not the lever.

## Acceptance Criteria
- [ ] After fix, from hub root: `collect_framework_files(Path('.'))` contains **0** files under
      `.claude/worktrees/` and **0** junk files; `greenfield_offer_set('.')` has `cap_hit == False`.
- [ ] `scripts/` and `docs/` files ARE present in the offer set (the value lands).
- [ ] Greenfield apply against a target classifies `scripts/git_visualize.py` as offerable
      (the original `/status` failure cannot recur via missing-from-offer).
- [ ] `collect_framework_files` returns the untracked-but-wanted set; the apply layer warns
      loudly naming those files, and does NOT warn for gitignored files (R3).
- [ ] On a non-git `project_root`, enumeration still excludes the junk via the predicate (R2),
      and a real git target always takes the R1 path.
- [ ] `project_root` is `.resolve()`d internally before any git argv; a leading-dash path is
      rejected (SEC-BLOCKING). git output is NUL-split, not line-split.
- [ ] An `ls-files` failure *after* a positive repo probe raises (fail loud); a missing git
      binary / non-repo falls back without crashing (R1).
- [ ] `len(corpus) > cap` raises `ValueError`; an empty hub corpus emits `warnings.warn` (R4).
- [ ] All four callers (`change_package`, `router`, `drift`, `init_lineage`) still pass their
      existing tests; drift/manifest behavior is unchanged except for the now-absent junk.
- [ ] New regression test (R5) added and listed in `memory/bugs/regression-ledger.md`.
- [ ] Quality gate passes (ruff, pytest, coverage ≥80%); `/review` completed; ADR written.

## Risk Assessment
- **Silent value-withholding (the meta-risk this fix is about):** the git-ls-files approach
  couples "what propagates" to "what's committed." Mitigation: R3 loud warning + documented
  "commit before distribute" discipline.
- **Breaking drift/manifest:** changing the shared util alters what drift/init_lineage see.
  Mitigation: the hub manifest is already clean (0 junk entries — verified), so no manifest
  regeneration is needed; run the full lineage/distribute test suites in `/review`.
- **Non-git target crash:** if the git path ran unconditionally it would break greenfield
  non-git applies. Mitigation: R2 fallback is mandatory and tested.
- **Subprocess/security:** git invoked on a caller-supplied root. Mitigation: argv list, no
  shell, bounded handling of non-zero exit.

## Affected Components
- `scripts/lineage/_utils.py` — `collect_framework_files` (primary: git-probe + ls-files path +
  `.resolve()` invariant + non-git fallback; **return shape grows to carry the untracked set** —
  the 4 callers that ignore it stay one-line)
- `scripts/distribute/change_package.py` — `greenfield_offer_set` (R4 cap signals: ValueError /
  warn) + the apply-layer untracked warning (R3)
- `scripts/distribute/router.py`, `scripts/lineage/drift.py`, `scripts/lineage/init_lineage.py` —
  callers; updated only if the return-shape change requires it (no behavior change intended)
- `tests/test_distribute.py` and `tests/test_lineage.py` — regression + edge-case tests (R5, ~11)
- `docs/adr/ADR-00NN-*.md` — new framework-scoped ADR (R6)
- `memory/bugs/regression-ledger.md` — ledger entry (note the divergence-distance baseline drop)
- (Optional, separate hygiene) delete `.claude/worktrees/external-analysis/*` — now non-load-bearing

## Dependencies
- Depends on: ADR-0016 (progressive-disclosure corpus), ADR-0017 (down-propagation), ADR-0021
  (apply unification); the existing B1 floor.
- Depended on by: `/apply-framework`, `/lineage`, drift scans, `init_lineage` — every project
  that consumes or is measured by the framework.
