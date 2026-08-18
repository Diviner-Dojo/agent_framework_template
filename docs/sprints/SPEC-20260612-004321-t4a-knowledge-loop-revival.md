---
spec_id: SPEC-20260612-004321
title: "T4-A — Knowledge-loop revival (P1 read-path + P2 capture/severity fix + P3 usable /promote)"
type: spec
status: complete
risk_level: medium
reviewed_by: [qa-specialist, architecture-consultant, docs-knowledge]
discussion_id: DISC-20260612-004557-t4a-knowledge-loop-spec-review
intake_ids: [SPEC-20260610-205507-D8, ANALYSIS-20260610-205507-fable-framework-audit-P1, ANALYSIS-20260610-205507-fable-framework-audit-P2, ANALYSIS-20260610-205507-fable-framework-audit-P3]
parent_spec: SPEC-20260610-205507
adr: ADR-0022
completed_at: 2026-07-06
completed_commit: 6dea657
status_note: "stamped complete post-hoc 2026-07-16 during the wave-2 spec-budget check (shipping evidence: git log; part of triage #11 bookkeeping debt)"
---

## Goal

Revive the framework's knowledge loop — the highest-leverage Track-4 batch (D8, greenlit
to its Steward gate). The audit (`ANALYSIS-20260610-205507-fable-framework-audit.md`,
14/14 spot-verified) found the loop is **write-only**: every command pays the full capture
ceremony, but the read side never fires, half the captured findings are scaffold noise, and
the severity ladder is a parsing artifact (53 "critical" vs 1 "high"). This spec makes four
months of capture start paying rent, in three sub-units on one branch (`feat/t4a-knowledge-loop`).

## Ground truth (verified against the live `metrics/evaluation.db`, 2026-06-12)

- **findings**: 396 rows. severity = {medium 243, low 65, **critical 53**, info 34, **high 1**}.
- The 53 "critical" rows are dominated by review-**scaffold** summaries — e.g. `## Findings`,
  `QA Review: 5 findings`, `Security Review: 5 findings`, `8 findings (1 HIGH blocking, …)`,
  `Validation pass complete`, `Architecture Review (confidence: 0…`, `Verdict: approve-with-changes`.
- **Root cause A (severity)**: `extract_findings._classify_severity` matches `_SEVERITY_PATTERNS`
  substrings against the **full event content** (`content_lower`), critical-tier first, first-match-wins.
  Any event whose body mentions `injection` / `security vulnerability` / `data loss` anywhere →
  `critical`; `high` (which needs the more specific `sql injection`) is starved → 1 row.
- **Root cause B (boilerplate)**: `_is_verdict_boilerplate` (added 2026-05-29, F2) catches
  `Verdict:` headers, round markers, confidence-only, and bare verdict tokens — but NOT
  review-scaffold lines (section headers, count summaries, per-agent review headers, scan/
  walkthrough scaffolds). 137 summaries still match `approve%`/`verdict%`/`revise%`/`round %`,
  and the scaffold lines above are not caught at all. The filter is too narrow, and it never
  ran against rows inserted before it existed.
- **Read path dead**: `searching-prior-art` greps only `memory/{projects,patterns}`,
  `memory/bugs/regression-ledger.md`, `docs/adr/` — never the 113 transcripts or the 396-row
  `findings` table. `/review` has no "prior findings on these files" pre-read.
- **Promote unusable**: `/promote` Step 1 lists candidates as `pattern_hash={fp[:12]}…` (opaque
  hex). `promotion_candidates.finding_pattern` == `pattern_sightings.pattern_hash`; the
  human-readable text lives in `pattern_sightings.summary` and is never joined. 19 pending
  candidates, 0 ever promoted; `decisions`=0; `reflections` 12/12 unpromoted.

## Constraints (load-bearing)

- **C1 — regression tests are frozen (testing_requirements.md).** `tests/test_extract_findings_verdict_filter.py`
  asserts `extract_findings` returns and stores **0** findings for verdict-only discussions
  and the substantive-only count for mixed ones. Therefore new boilerplate stays **dropped at
  extract time** (NOT inserted-then-flagged) — flipping drop→flag would change those counts and
  weaken a regression test, which requires explicit developer approval (developer is AFK).
  Broadening `_is_verdict_boilerplate` only **adds** True cases; every existing parametrized
  case (`_BOILERPLATE_SUMMARIES` all-True, `_SUBSTANTIVE_SUMMARIES` all-False) must stay green.
- **C2 — flag, never delete (audit P2).** The 199-ish existing noise rows are corrected by a
  one-time **backfill** that sets a new `is_noise` flag and re-derives severity in place — no row
  is deleted. The audit trail (raw_excerpt, original row) is preserved.
- **C3 — events.jsonl is framework-agent-written.** Residual filter evasion is a quality, not a
  security, concern (per the existing extract_findings comment + REV-20260529-054131 A3). No new
  trust boundary is introduced; the severity rubric is a prompt-level quality aid, not a gate.
- **C4 — additive, idempotent migration.** `is_noise` is added via guarded `ALTER TABLE ADD
  COLUMN … DEFAULT 0`; init_db gains the column in the canonical schema. Re-running migration or
  backfill is a no-op. Derived projects' existing DBs upgrade on next init/backfill.
- **C5 — ADR required (ADR-0022).** The `is_noise` schema extension and the `_classify_severity`
  rework are persistent, multi-project decisions not covered by any existing ADR (ADR-0011 covers
  knowledge-base layers, not the findings schema or classification logic). A minimal ADR-0022 is
  required: context (53-critical skew), decision (is_noise flag + reclassify), constraint C2
  (flag-never-delete) as a consequence, and a derived-project migration note.

## Requirements

### P1 — Reconnect the knowledge read-path  (size S)

- **R1.1** Extend `.claude/skills/searching-prior-art/SKILL.md` with two new search locations
  (and add sequential numbering to the existing four entries so "search in order" has a
  canonical sequence): (5) **Captured findings** — a copy-paste `sqlite3` snippet querying
  non-noise `findings` (`WHERE is_noise = 0`) by category/keyword, returning `severity,
  category, summary, discussion_id`. Graceful degrade: wrap the snippet in a
  `try/except sqlite3.OperationalError` that retries without the `is_noise` filter if the
  column doesn't exist yet (pre-migration DB returns all findings); if the findings table is
  absent, skip silently with an `[info]` note. (6) **Discussion transcripts** —
  `grep -ril "<keyword>" discussions/*/transcript.md`. Keep the "quick grep is sufficient /
  does not block" guidance intact.
- **R1.2** Add a ≤5-line **"Prior findings on these files"** pre-read step to
  `.claude/commands/review.md`, before the specialist dispatch: a `sqlite3` snippet that lists
  recent non-noise findings whose `raw_excerpt`/`summary` reference any file under review (LIKE
  match on basename), so reviewers see what prior reviews already flagged. Read-only; degrades
  gracefully if the DB, table, or `is_noise` column is absent — wrap in a single
  `try/except sqlite3.OperationalError` that catches both absent-table and absent-column cases
  (both raise `OperationalError`), printing an `[info]` skip notice. Matches promote.md's
  existing `OperationalError` guard pattern.

### P2 — Clean the capture stream + severity calibration  (size M)

- **R2.1 — `is_noise` column.** Add `is_noise INTEGER NOT NULL DEFAULT 0` to the `findings`
  schema in `scripts/init_db.py`. Provide an idempotent in-place migration: check
  `PRAGMA table_info(findings)` and issue `ALTER TABLE findings ADD COLUMN is_noise INTEGER
  NOT NULL DEFAULT 0` if the column is absent. Wrap the ALTER in a
  `try/except sqlite3.OperationalError` that treats "duplicate column name" as success — this
  closes the PRAGMA-check/ALTER race window (both a guard and a defensive belt-and-suspenders
  measure; concurrency is near-zero but the pattern is a 1-line close). Run the migration on
  its own connection in autocommit, not nested inside the backfill's data-mutation transaction.
  (No CHECK constraint change to `severity`.)
- **R2.2 — Broaden the boilerplate predicate.** Extend `_is_verdict_boilerplate` in
  `scripts/extract_findings.py` with **principled, named** scaffold categories (not sample-fit):
  (a) markdown section headers that are pure scaffolding (`^#{1,6}\s*(findings|verdict|summary|
  recommendation[s]?|blocking|advisor(y|ies))\s*$`); (b) finding-count summaries
  (`^\s*\d+\s+findings?\b…`); (c) per-agent review headers (`^\s*(qa|security|architecture|
  performance|ux|docs?|independent[- ]perspective)[\w /-]*\breview\b\s*[:(]`); (d) process-scaffold
  lines (`validation pass complete`, `guided walkthrough…`, `walkthrough for…`). Each category is
  a separate named, commented regex. **All existing parametrized cases must stay green** — the new
  patterns must not match any `_SUBSTANTIVE_SUMMARIES` entry (verified by extending the existing
  test file, not editing its catalogues). Explicitly verify category (d) patterns do not match
  entries containing `validation` or `pass` as ordinary English words (e.g. "Missing validation
  on the discussion_id parameter").
- **R2.3 — Honest severity.** Rework `_classify_severity` so the histogram reflects real risk:
  (1) **explicit marker wins** — if the content carries an explicit specialist severity label
  (`Severity: HIGH`, `[CRITICAL]`, `**HIGH**:`, `(severity: medium)`), parse and trust it;
  (2) **fall back** to keyword heuristics scanning **the summary** (the topical first sentence),
  not the whole body, using **word-boundary** matches and **highest-tier-wins** (scan all tiers,
  return the most severe match) rather than dict-order-first-match; (3) default `medium` when
  nothing matches. Refine `_SEVERITY_PATTERNS` so single ambiguous tokens (`injection` alone)
  don't force `critical` — require the qualified phrase (`injection vulnerability`, `sql injection`,
  `command injection`) for critical; bare `injection`/`auth`/`race condition` map to high/medium.
- **R2.4 — Backfill (flag + recalibrate, never delete).** New `scripts/backfill_finding_noise.py`:
  for every existing finding, set `is_noise = _is_verdict_boilerplate(summary)`; for non-noise
  rows, recompute `severity` via the new `_classify_severity` (reading `raw_excerpt` as the content
  proxy, summary as the topical line). `--dry-run` prints the before/after severity histogram and
  noise count; default applies. **Idempotency**: the UPDATE is delta-gated — only rows where the
  derived `is_noise` or `severity` value differs from the stored value are touched, so a second
  run issues zero DB writes. Compact stdout (counts only). Imports `_is_verdict_boilerplate` and
  `_classify_severity` from `extract_findings` directly (single source of truth — no
  re-implementation). These are intentionally private-symbol cross-imports; add a one-line
  comment above each function in `extract_findings.py` noting it is imported by
  `backfill_finding_noise.py` so future refactors don't silently break the dependency.
- **R2.5 — Downstream consumers honor `is_noise`.** `mine_patterns.py` excludes noise findings
  by adding `AND f.is_noise = 0` to BOTH query branches: the `discussion_id` path (line ~55)
  and the `--all` LEFT JOIN path (lines ~61-65). Both select from `findings f` and both must
  get the filter — the spec's "the WHERE clause" covers both. `knowledge_dashboard.py`
  counts/severity-buckets non-noise findings (and reports the noise count as a distinct line).
- **R2.6 — Shared severity-calibration rubric (prompt-level).** New
  `.claude/skills/severity-calibration/SKILL.md` defining all five tiers with:
  (1) a one-sentence scope test per tier — CRITICAL = active exploitability or data loss in
  the current code path; HIGH = plausible exploitability or correctness bug with user-visible
  consequence; MEDIUM = code smell, maintainability, or theoretical risk; LOW = style, minor
  improvement; INFO = observation with no action required;
  (2) one concrete named example per tier drawn from the framework's own finding history;
  (3) the explicit tie-break rule: ambiguous cases default DOWN (if the finding could be HIGH
  or MEDIUM, mark it MEDIUM — asymmetric anchoring prevents severity inflation);
  (4) the instruction that specialist findings state an explicit `Severity: <tier>` marker
  so R2.3's marker-parse can consume it.
  Reference the skill from `.claude/commands/review.md` and the `selecting-review-gates` skill
  so findings carry honest severity **at the source**. This is the audit's "shared
  severity-calibration rubric … as a prompt-level fix riding P2."

### P3 — Make /promote usable and triggered  (size S)

- **R3.1 — Human-readable queue.** `/promote` Step 1 query joins a representative
  `pattern_sightings.summary` per candidate using a correlated single-row subquery:
  `(SELECT summary FROM pattern_sightings WHERE pattern_hash = pc.finding_pattern ORDER BY id
  LIMIT 1) AS summary` — this ensures one row per candidate regardless of sighting count (a
  candidate with N>1 sightings would otherwise multiply to N display rows). Display format:
  `[category] "<summary>"  (N sightings, first…last)`. Keep the integer `id` shown (Step 4
  still needs it). Keep the `OperationalError` graceful-degrade.
- **R3.2 — Quality-gate advisory.** New advisory check `check_promotion_backlog()` in
  `scripts/quality_gate.py` (modeled exactly on `check_build_status_freshness`: NOT in
  `_CHECK_NAMES`, always returns True, calls `_warn`). Wire-up: called **unconditionally** in
  `main()` after the existing advisory checks (~line 716), return value discarded (NOT appended
  to `results`, NOT incrementing `total`), no `--skip-*` flag. Warns when **pending candidates
  (`promoted=0`) > N** (N=5 default constant) **OR** the freshest signal of promotion/retro
  activity is **> 30 days** old (max of `promotion_candidates.promoted_at` and
  `reflections.created_at`; treat empty as stale-but-quiet → warn only on the count trigger to
  avoid a false alarm on a fresh repo). Degrades silently if the DB/tables are absent.

## Acceptance Criteria

- **AC1** `searching-prior-art` documents the 2 new read locations with runnable snippets and
  sequential numbering on all 6 entries; both new snippets degrade gracefully on absent/pre-migration
  DB (no column = retry without filter; no table = `[info]` skip). `/review` runs the prior-findings
  pre-read; a `try/except sqlite3.OperationalError` guard catches absent-table and absent-column and
  prints an `[info]` skip notice rather than failing.
- **AC2** `_is_verdict_boilerplate` returns True for the new scaffold catalogue AND every legacy
  `_BOILERPLATE_SUMMARIES` case; returns False for every `_SUBSTANTIVE_SUMMARIES` case. New
  parametrized cases added; the existing catalogues are not edited. The test run explicitly covers
  that category (d) patterns do not match `_SUBSTANTIVE_SUMMARIES` entries containing `validation`
  or `pass` as ordinary English words.
- **AC3** On a synthetic fixture, `_classify_severity`: (a) honors an explicit `Severity:` marker;
  (b) does not return `critical` for a finding whose summary is topical-but-benign yet whose body
  mentions `injection`; (c) returns `high` for `race condition`/`unhandled error`-class summaries.
- **AC4** `init_db` creates `findings.is_noise`; the migration is idempotent (running twice =
  no error, no dup column — the `try/except OperationalError` on the ALTER makes it race-safe);
  a pre-migration DB gains the column.
- **AC5** `backfill_finding_noise.py --dry-run` reports a histogram; applied, it (i) flags the
  scaffold rows `is_noise=1`, (ii) leaves row count unchanged (no deletes), (iii) reduces
  `critical` to a defensible count, (iv) is idempotent — **a second run produces zero DB writes**
  (asserted by checking `conn.total_changes` before and after, or equivalent). A regression test
  asserts no-delete + idempotency on a seeded DB.
- **AC6** `mine_patterns` produces no sighting from an `is_noise=1` finding (regression test covers
  both the `discussion_id` and `--all` code paths).
- **AC7** `/promote` Step 1 shows human-readable summaries (no bare hex); query is valid SQL
  against the canonical schema and returns exactly one row per candidate regardless of sighting count.
- **AC8** `check_promotion_backlog` is advisory (gate stays green), warns on the count trigger,
  and is silent on a fresh/empty DB. In `main()`, the function is called unconditionally after the
  existing advisory checks — its return value is NOT appended to `results`, does NOT increment
  `total`, and there is no `--skip-*` flag. Covered in `tests/test_quality_gate.py` by asserting
  both the warn behavior AND the non-blocking wire-up (gate exit code remains 0 when warned).
- **AC9** Quality gate 7/7 (coverage ≥80% on changed Python); ruff clean; full suite green
  (no existing regression test weakened).
- **AC10** `severity-calibration/SKILL.md` exists and defines all five severity tiers with
  one-sentence scope tests, concrete examples, and the default-down rule. `.claude/commands/review.md`
  and `.claude/skills/selecting-review-gates/SKILL.md` each contain a reference to
  `severity-calibration` (verifiable by grep).

## Out of scope (parked, dated note)

- Re-mining historical `pattern_sightings` that were derived from now-flagged noise findings
  (existing sightings stay; only **new** mining honors `is_noise`). Cleaning historical sightings
  is a follow-on if the 19 pending candidates prove polluted after backfill — note for the
  developer at the post-backfill candidate review.
- Actually promoting any of the 19 candidates (that is a `/promote` run = human approval,
  Principle #7 — not this build).
- `/retro` ever-zero-runs (T4-A reconnects the read path that `/retro` would consume; running
  `/retro` is a separate operation).

## Verification Notes

- Run `backfill_finding_noise.py --dry-run` against a **copy** of the live DB during build to
  confirm the new severity distribution is sane before any guidance about "defensible count".
- The live `metrics/evaluation.db` is runtime data (not committed). The backfill against the real
  DB is a runtime operation; tests run against seeded `tmp_path` DBs only.
