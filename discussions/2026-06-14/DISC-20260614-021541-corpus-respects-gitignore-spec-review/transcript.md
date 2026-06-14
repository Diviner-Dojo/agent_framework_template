---
discussion_id: DISC-20260614-021541-corpus-respects-gitignore-spec-review
started: 2026-06-14T02:15:54.607240+00:00
ended: 2026-06-14T02:20:39.774840+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260614-021541-corpus-respects-gitignore-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-14T02:15:54.607240+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix the framework corpus builder to respect .gitignore so /apply-framework propagates real value (scripts/, docs/, ADRs) to every target. Empirically-confirmed defect: collect_framework_files() rglob walk sweeps 10,948 gitignored worktree clones + 117 junk files into an 11,234-file corpus; the 5000 greenfield cap is exhausted inside .claude/worktrees/ before scripts/ or docs/ are reached, so no value lands and /status later fails (git_visualize.py never deployed).
- **Files/scope**: SPEC-20260613-191445. Primary: scripts/lineage/_utils.py collect_framework_files (git ls-files path + non-git rglob+exclude fallback + untracked-warn). Also scripts/distribute/change_package.py greenfield_offer_set (symmetric cap guard). Shared util has FOUR callers (change_package, router, drift, init_lineage) — all must stay correct. New ADR + regression test.
- **Developer-stated motivation**: /apply-framework must actually deliver the framework's value to derived projects (Prime Objective: value must reach contributors, not be silently withheld). Developer explicitly chose the FULL fix incl. the untracked-warn and symmetric cap hardening, not the minimal version.
- **Explicit constraints**: Must NOT alter the B1 safety floor (this is strictly upstream, corpus-definition). git ls-files must run with -C <project_root> (target, not cwd). Non-git fallback is mandatory (greenfield non-git targets). Do not 'fix' by raising the cap. Framework tooling -> ADR + /review before commit, own branch off main.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-14T02:19:47.340645+00:00 | confidence: 0.82*
*tags: spec-review, architecture, approve-with-changes, blast-radius*

APPROVE-WITH-CHANGES (conf 0.82). Boundary choice CORRECT: fix the shared util (single source of truth); all 4 callers WANT gitignore-excluded enumeration. Decisive: drift.py currently mis-reports every gitignored junk file as drift_status='added', inflating divergence_distance — the fix makes drift MORE correct, not broken. Findings: [ADVISORY] R3 untracked-warn is a concerns inversion — collect_framework_files is a pure enumerator with 4 callers; 3 (drift/router/init_lineage) don't want an apply-specific stderr warning. RETURN the untracked set from the util; WARN at the apply/distribute layer. [ADVISORY] Make the git-repo probe EXPLICIT (rev-parse --is-inside-work-tree): non-zero on the PROBE -> fallback (legit); non-zero on ls-files AFTER a positive probe -> fail loud, do NOT silently degrade to the predicate (that would be a silent failure in a fail-loud spec). [ADVISORY] The non-git fallback predicate is a hardcoded denylist that cannot match a TARGET's own .gitignore; scope the claim honestly in the ADR; R5(d) should test the target as a REAL git repo (the actual router.py path). [NIT] Keep the R4 empty-corpus guard in greenfield_offer_set, NOT the util — drift legitimately passes a narrowed tracked_paths that may resolve to few/zero files. [NIT-info] Add R5(e): drift_scan no longer reports junk as 'added'; note the divergence-distance baseline DROP in the ledger so it isn't read as a regression. ADR should record the cap's role shift: from 'silent pollution absorber' to 'fail-loud bound on a legitimately-large corpus' (vs ADR-0021 section 7). No contradiction with ADR-0016/0017/0021 or the B1 floor.

---

## Turn 3 — qa-specialist (critique)
*2026-06-14T02:20:01.004934+00:00 | confidence: 0.88*
*tags: spec-review, qa, approve-with-changes, blocking, test-strategy*

APPROVE-WITH-CHANGES (conf 0.88). 3 BLOCKING gaps before build: (1) regression test + ledger entry are MANDATORY for this confirmed bug and currently absent — need a @pytest.mark.regression test that FAILS under old code, PASSES under fix (temp git repo, gitignored worktrees junk >5000 files, committed scripts/sentinel.py; assert sentinel present + no worktrees path + cap_hit False). (2) R4 cap-guard interface contract is AMBIGUOUS ('raises/warns') — implementer+reviewer will diverge; pin exact signals: oversize -> raise ValueError; empty -> warnings.warn (empty is an anomaly not a crash). (3) target-side enumeration via router.py:107 (root=target) has ZERO tests — the most user-relevant caller. Edge cases to cover: empty repo (ls-files exit 0, returns {}); CLAUDE.md as a FILE-type framework_path (git ls-files -- CLAUDE.md); git NOT on PATH raises FileNotFoundError (NOT non-zero exit) — must catch OSError; symlinks (ls-files lists the symlink, not target contents). Parametrize the 6 R2 fallback sub-conditions (one test each, else 5 untested). Assert KEY SETS equal across git-path vs fallback (order may differ; greenfield_offer_set sorts at caller). Update existing weak test_offer_set_is_bounded_and_sorted to assert cap_hit is False on clean corpus. 11-test concrete list provided. Strong existing fixture infra (_init_repo/_g/_commit_all) to reuse. Coverage stays >=80% with these.

---

## Turn 4 — security-specialist (critique)
*2026-06-14T02:20:17.296423+00:00 | confidence: 0.87*
*tags: spec-review, security, approve-with-changes, blocking, subprocess-boundary*

APPROVE-WITH-CHANGES (conf 0.87). Subprocess discipline (argv list, no shell) is the right posture and already specified; git ls-files (allowlist) over rglob (denylist) is structurally stronger. [BLOCKING] Finding 1 (A03 Injection): collect_framework_files must call project_root.resolve() INTERNALLY before building the git argv — a project_root whose string begins with '-' becomes a git flag (arg injection). change_package.py:526 passes Path(template_root) from a raw argparse string WITHOUT resolving; router.py:107 is safe (resolves). Make .resolve() an internal invariant of the util, plus a belt-and-suspenders leading-dash guard. [ADVISORY] Use -z (NUL-delimited) and split on b'\x00' — NEVER splitlines() (a filename with an embedded newline on linux/macOS could smuggle a fake corpus entry). [ADVISORY] Apply the R2 denylist predicate to the forward-slash-NORMALIZED key in ONE explicit place, not the raw relative_to() output (Windows backslash gap). Safe invocation: cmd=['git','-C',root_str,'ls-files','-z','--',prefix] with timeout=15, catch (OSError, TimeoutExpired) -> fallback, returncode!=0 -> fallback. Dismissed as NON-issues: fail-open on git error is NOT a security downgrade (attacker controlling git already owns the FS; R4 cap guard covers the reliability angle); ls-files cannot emit ../ traversal paths (git model); submodules not recursed by default. Residual NIT: a tracked symlink pointing outside the tree would be hashed by target — fine for single-developer local tooling (resolve().is_relative_to guard if ever multi-tenant).

---

## Turn 5 — facilitator (synthesis)
*2026-06-14T02:20:39.774840+00:00 | confidence: 0.86*

## Request Context
- **What was requested**: Make collect_framework_files() respect .gitignore so /apply-framework propagates real value (scripts/, docs/) to every target; full hardening (untracked-warn + symmetric cap guard) per developer.
- **Files/scope**: scripts/lineage/_utils.py (shared util, 4 callers) + scripts/distribute/change_package.py greenfield_offer_set; new regression tests + ADR + ledger entry.
- **Developer-stated motivation**: value must actually reach derived projects (Prime Objective); not be silently withheld.
- **Explicit constraints**: must NOT touch the B1 safety floor (upstream-only change); git -C <root> not cwd; non-git fallback mandatory; do not raise the cap.

## Synthesis
Unanimous APPROVE-WITH-CHANGES (arch 0.82, qa 0.88, sec 0.87). No REVISE — all changes are spec-clarifications + implementation constraints, not redesign. Convergent strong points: (a) fixing the shared util is the correct boundary; arch confirmed all 4 callers WANT the clean enumeration (drift currently inflates divergence_distance with junk 'added' rows). (b) The B1 floor is untouched (strictly upstream).

Folding the following into the spec (status -> reviewed):
1. [SEC-BLOCKING] .resolve() project_root internally before the git argv (arg-injection via leading-dash root; change_package CLI path doesn't resolve). + leading-dash guard.
2. [SEC] -z NUL-delimited parse (never splitlines); predicate on forward-slash-normalized key in one place; timeout=15 + catch OSError/TimeoutExpired -> fallback.
3. [ARCH] R3 untracked-warn moves OUT of the low-level util: the util RETURNS the untracked set; the apply/distribute layer warns. drift/router/init_lineage don't pay for an apply concern.
4. [ARCH] Explicit git-repo probe (rev-parse --is-inside-work-tree): probe-fail -> fallback; ls-files-fail after positive probe -> fail loud (no silent degrade).
5. [QA-BLOCKING] Pin R4 signals: oversize -> raise ValueError; empty -> warnings.warn. Guard lives in greenfield_offer_set, not the util.
6. [QA-BLOCKING] Add target-side router.py test + the full 11-test list (empty repo, CLAUDE.md file-type path, git-not-on-PATH FileNotFoundError, symlink, parametrized 6 fallback sub-conditions, key-set equality git-vs-fallback). Regression test + ledger entry mandatory before commit.
7. [ARCH-NIT] Add R5(e) drift assertion (junk no longer 'added'); note divergence-distance DROP in ledger. ADR records cap role shift (silent absorber -> fail-loud bound) + honest scope of the fallback denylist.
Return-shape decision for the util: change collect_framework_files to return a small result carrying both the hash dict AND the untracked list (keeps detection where the git info is cheap, moves the warn decision to the caller) — to be finalized at build time as either a dataclass or a (hashes, untracked) tuple; callers that ignore untracked stay one-line.

---
