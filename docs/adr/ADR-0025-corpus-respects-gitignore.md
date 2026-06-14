---
adr_id: ADR-0025
title: "Framework corpus builder respects .gitignore — git ls-files enumeration, non-git fallback, fail-loud cap, and untracked-value warning"
status: accepted
date: 2026-06-13
decision_makers: [facilitator, architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260614-021541-corpus-respects-gitignore-spec-review
supersedes:
scope: framework
risk_level: medium
confidence: 0.86
tags: [apply-framework, distribute, lineage, drift, corpus, gitignore, prime-objective, fail-loud, b1]
---

> **Numbering note (2026-06-13).** Authored on `fix/corpus-respects-gitignore`, branched from
> `main`, where the latest ADR is ADR-0021. ADR-0022 (findings-schema), ADR-0023 (one-shot stop
> hook), and ADR-0024 (confidence-calibration loop) exist on feature branches not yet merged to
> `main` and are referenced by CLAUDE.md. This ADR takes **0025** to sit above all of them and
> avoid a collision when those branches merge.

## Context

`/apply-framework` "failed to add the value that lives in the framework" to a derived project
(`dan_research_karpathy_wiki`); afterward `/status` failed on that target because its backing
script (`scripts/git_visualize.py`) had never been deployed.

The root cause is in the **corpus enumerator**, the single source of truth for "what is the
framework." `scripts/lineage/_utils.py::collect_framework_files()` walked each `FRAMEWORK_PATHS`
prefix (`​.claude/`, `scripts/`, `CLAUDE.md`, `docs/templates/`, `docs/adr/`) with `rglob("*")`
and excluded **nothing**. Measured in the hub: the raw corpus was **11,234** files, of which
**10,948** were gitignored external-repo clones left under `.claude/worktrees/external-analysis/`
by `/analyze-project`, plus **117** other junk files (`__pycache__/*.pyc`, `.claude/hooks/.state/*`,
`settings.local.json`, `.claude/custodian/lineage-events.jsonl`, `context-occupancy*.json`).

`greenfield_offer_set()` sorts the corpus and caps it at `MAX_GREENFIELD_OFFER = 5000`. Because
`.claude/` sorts before `scripts/`/`docs/` and `.claude/worktrees/` alone exceeds the cap, the
iterator **never reached `scripts/` or `docs/`** — so the greenfield APPLY route offered none of
the framework's actual value, and the cap was hit **silently**. This is a Prime-Objective failure:
the value the framework exists to deliver to contributors was withheld with no signal.

`collect_framework_files` is imported by four callers — `change_package.py`, `router.py`,
`drift.py`, `init_lineage.py` — so the defect also inflated drift detection: every gitignored junk
file was reported as a spurious `added` drift, inflating `divergence_distance`.

## Decision

Make the corpus enumerator exclude what git already excludes, and convert the silent failure modes
into loud ones. The change is strictly **upstream of the B1 mechanical safety floor** (ADR-0017 /
ADR-0021): it changes *which files enter the corpus*, never how an offered file is classified —
the consent guarantee (`_classify` → `value-unverified`) is untouched.

1. **Git is the source of truth (preferred path).** When `project_root` is a git repo (probed
   explicitly with `git rev-parse --is-inside-work-tree`), enumerate tracked files via
   `git -C <root> ls-files -z -- <prefix>`. This structurally excludes worktrees, `__pycache__`,
   `.pyc`, local state, etc. with no hand-maintained list to drift. A failure of `ls-files`
   **after a positive probe** is a real error in a known repo and is **raised** (fail loud), never
   silently degraded to the fallback.

2. **Non-git fallback (mandatory).** When the probe says not-a-repo (a greenfield APPLY to a fresh
   directory; a missing git binary, caught as `OSError`), fall back to the `rglob` walk plus a
   denylist of *framework-shaped* junk applied to the forward-slash-normalized key. This denylist
   is **best-effort for genuinely non-git roots only** — it is NOT a general `.gitignore` emulation
   and cannot know a target's project-specific ignores. A real git target always takes path 1.

3. **Argument-injection closed.** `collect_framework_files` resolves `project_root` to an absolute
   path internally before building any git argv (an absolute path cannot begin with `-`), with a
   belt-and-suspenders leading-dash guard. The CLI path passes an unresolved root, so the invariant
   lives in the util, not the callers. Output is parsed by NUL-splitting (`-z`), never `splitlines`.

4. **Fail-loud cap (R4).** In `greenfield_offer_set`, an oversize corpus (`len > cap`) **raises
   `ValueError`** rather than truncating; a suspiciously **empty** corpus emits `warnings.warn`.
   The cap's role shifts from a *silent absorber of pollution* (the bug) to a *fail-loud bound on a
   legitimately-large corpus* (cf. ADR-0021 §7, where the cap was introduced as a safety bound
   against a pathological hub turning an APPLY into an unbounded copy).

5. **Untracked-value warning (R3).** `collect_framework_files` stays a pure enumerator
   (`dict[str, str]`, callers unchanged); a sibling `list_untracked_framework_files()` reports
   framework-path files git is neither tracking nor ignoring. The **apply layer**
   (`greenfield_offer_set`) warns loudly, naming them — they will not propagate until committed.
   The warn decision lives at the apply layer so drift/router/init_lineage do not pay for it.

## Consequences

**Positive.** The hub corpus drops from 11,234 to ~161 files; `scripts/` and `docs/` (incl.
`git_visualize.py`) are offered, so the value lands. The cap is no longer reachable by gitignored
content. Drift detection is more accurate (junk no longer reported as `added`; `divergence_distance`
drops for any target that carried junk under framework paths — an improvement, not a regression).
All four callers benefit from one fix. The whole bug *class* (silent truncation, silent omission)
is closed by fail-loud + warn.

**Negative / trade-offs.** `git ls-files` couples "what propagates" to "what is committed": new but
uncommitted framework work will not propagate until committed. This is mitigated by R3's loud
warning and a **commit-before-distribute** discipline — accepted as the right default (an announced
omission beats a silent one). The non-git fallback denylist can drift from a target's real ignores,
but a real git target never reaches it.

**Open hygiene item (not part of this decision).** `.claude/custodian/lineage-events.jsonl` is
*tracked* in the hub, so the git path ships it while the fallback denylist would exclude it. Whether
that runtime append-log should be tracked at all is a separate hygiene question; the B1 floor
classifies it safely downstream regardless.

## Alternatives Considered

1. **Raise the 5000 cap.** Rejected — it masks the bug: a polluted corpus would still bury
   `scripts/`/`docs/` (just at a higher bound), and the cap exists precisely as a safety bound
   against an unbounded APPLY (ADR-0021 §7). The cap is not the lever; the corpus definition is.
2. **Hand-maintained exclusion list as the primary mechanism (rglob + denylist everywhere).**
   Rejected as the primary path — a denylist drifts from git's actual ignores and must be updated
   by hand forever. Retained only as the *fallback* for genuinely non-git roots, where git's
   ignore information is unavailable.
3. **Fix per-caller (filter in `greenfield_offer_set` only).** Rejected — `collect_framework_files`
   is the single source of truth shared by four callers; filtering in one leaves drift/router/
   init_lineage still enumerating junk (drift would keep reporting spurious `added` rows). Fixing
   the shared util fixes all four consistently.
4. **Change `collect_framework_files`'s return type to carry the untracked set.** Rejected — it
   would touch all four callers for a concern only the apply route needs. Chose a sibling
   `list_untracked_framework_files()` instead, keeping the enumerator's `dict[str, str]` contract
   and the warn decision at the apply layer.
5. **Silently truncate / silently omit (status quo).** Rejected — silence is the defect. Fail-loud
   (`ValueError` on oversize, `warnings.warn` on empty/untracked) converts every failure mode into
   an announced one.

## Relationship to other ADRs

- **ADR-0016 (progressive-disclosure corpus):** consistent — narrowing the enumerated corpus to
  what git tracks is corpus discipline, not a disclosure-policy change.
- **ADR-0017 / ADR-0021 (down-propagation / apply unification, B1 floor):** this change is strictly
  upstream of `_classify`; the floor and the `value-unverified` consent guarantee are unchanged.
- **Fail-loud discipline:** consistent with the framework's established `KeyError`-over-silent
  pattern (e.g. telemetry `DRIFT_REMEDIATION_HINTS`).

## Verification

Regression + edge tests in `tests/test_lineage.py::TestCorpusRespectsGitignore` and
`tests/test_distribute.py` (`TestOfferSetCapGuard`, `TestRouterExcludesTargetGitignore`, updated
`TestGreenfieldFloor`): gitignored junk excluded; cap unreachable by gitignored content; non-git
fallback excludes each junk shape; git-not-on-PATH falls back; git-path vs fallback key-sets equal;
untracked detection; oversize raises / empty warns / untracked warns; target-side enumeration
excludes the target's own gitignore. Ledger: `memory/bugs/regression-ledger.md`.
