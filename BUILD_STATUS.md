# Build Status

> Working state for the session in progress. Keep it short — this is a handoff
> note, not a log. The durable record lives in `discussions/`, `docs/adr/`, and
> `memory/`.
>
> v3's copy grew to 155KB and was read at the start of every session. It is
> archived verbatim at `memory/archive/v3-framework/BUILD_STATUS-v3-final.md`.

## Current session (2026-07-28) — framework v4 rebuild

**Branch**: `claude/framework-modernization-opus-tr3ce9`

Rebuilt the framework from empty, separating scaffolding (instructions telling
the model how to think) from governance (constraints on what may happen to the
human). Deleted the first, strengthened the second. Full rationale in
**ADR-0029**; reasoning captured in
`DISC-20260728-071754-framework-v4-modernization`.

- Instruction surface: ~9,000 → ~900 lines. 25 commands → 8, 26 skills → 2,
  12 agents → 5, 4 rule files → 0 (folded into `CLAUDE.md`).
- New: `scripts/assess_risk.py` (deterministic briefing depth from the diff),
  `scripts/briefing.py` + `briefings` table (delivered/deferred, no score, no
  failure state).
- Restored after being wrongly cut: the two-way ntfy loop, `surface_candidates.py`.
- 534 tests pass; ruff clean on all new files; lint debt 45 → 29.

## Review complete — REVISE, remediated

`/review` ran with four independent reviewers: REV-20260728-140000,
`DISC-20260728-135213-v4-framework-review`. Verdict REVISE, nine blocking. All
nine are fixed; both developer judgment calls were decided.

**Fixed**
- **B1-B3** `assess_risk.py` git interface. Bare `git diff` compared
  working-tree-vs-index, so `/teach` reported LIGHT for a DEEP change once work
  was staged — the education gate did not work in the normal workflow. Now
  diffs against HEAD, derives new files from the selected range, folds in
  untracked files, and raises `GitUnavailable` (exit 2) instead of failing
  toward LIGHT. Tests now run against real repositories.
- **B4** `briefing.py` self-initializes instead of leaving a 0-byte DB.
- **B5** `.claude/hooks/` added to `PROTECTED_PATTERNS` — writing a hook was
  arbitrary execution on every prompt submit.
- **B6** `/apply-framework` rewired onto `scripts/distribute/`; the four
  fail-closed guards (injection framing, secret redaction, per-instance assent,
  clean tree) run again. **Developer decision: keep the capability.**
- **B7** `/decide` template now matches what the gate requires.
- **B8** seven ADRs superseded with reasons; ADR-0029 names them. ADR-0021 and
  ADR-0024 stay accepted — both are restored, not retired.
- **B9** embeddings import is genuinely lazy; the three ledger-guarded
  regression tests run again, including the thread-local one `CLAUDE.md` names.

**Measurement restored (developer decision).** `record_yield.py` and
`audit_calibration.py` are back, `briefings` gained `outcome`/`outcome_ref`/
`outcome_at`, and `briefing.py regret` answers the question ADR-0029 said it
expected to be wrong about. `/review` now writes a yield row; the
`severity-calibration` rubric is restored because without an explicit marker
`extract_findings` was labelling blocking findings `medium`. The ~13,000 lines
of dashboards stay deleted.

611 tests pass, gate 6/6 (review-existence skipped for this remediation pass).

**⮕ Next**
1. Developer applies `docs/settings-v4.patch` to `.claude/settings.json` by
   hand; the file is agent-protected by design. **Do this before merging** —
   until then five configured hooks point at deleted files.
2. Optional: a second `/review` pass over the remediation itself.
3. Non-blocking backlog in REV-20260728-140000: stale v3 docs (~3,300 lines),
   dead schema tables, `_is_retired` retires on rename, `scripts/` sits outside
   format/lint/coverage.
