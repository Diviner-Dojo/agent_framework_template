---
spec_id: SPEC-20260716-233400
title: "Green-able quality gate + stack-aware profiles + harness-ergonomics riders (Wave 2)"
type: spec
status: complete
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260717-063527-greenable-gate-stack-profiles-spec-review
intake_ids: ["triage #2 + #9 + #14 (brainstorms/2026-07-15-review-triage.md)", "perf review P0·#2 + #7 (docs/research/framework-performance-review-2026-07-14.md)", "gap-analysis synth §1.2/§2.6"]
completed_at: 2026-07-17
completed_commit: f5e98da
---

> rev 2 — folds the spec-review panel's findings (2 security BLOCKING, 3 qa BLOCKING,
> 1 arch BLOCKING, plus cheap advisories). Panel verdicts: security approve-with-changes 0.82,
> arch approve-with-changes 0.78, qa approve-with-changes 0.78.
>
> **Post-/review scope honesty (2026-07-17, independent-perspective fold):** this build
> resolves the LINT/FORMAT attrition of the cited evidence (VP lint 0/330) and the
> wrong-tool problem (ruff-on-Dart, wiki fork). It does NOT resolve AJ's coverage-hang
> abandonment (the shipped `flutter-dart` profile disables coverage — the hang is a
> derived-project deployment concern) or VP's coverage-threshold erosion (`fail_under`
> 80→40; coverage is deliberately excluded from baselining per R1.5 — the profile's
> `fail_under` is review-gated but nothing forces an honest value). Both are carried,
> not solved. Also noted: the argv[0] allow-list is anti-typo/anti-substitution, NOT a
> sandbox — the real containment boundary for profile commands is the R1.3a review gate
> (see the gate_profiles.yaml header).

## Goal

Make a RED quality gate mean exactly one thing — **new debt introduced by this change** — and make
the gate fit the project's stack instead of fighting it. Three paired pieces, one build in
`scripts/quality_gate.py`:

1. **Green-able gate (triage #2)**: a committed debt **baseline** so pre-existing lint/format
   violations report as tracked debt (WARN + count), while any NEW violation still fails RED.
2. **Stack-aware profiles (triage #9)**: gate profiles (`python-fastapi` / `flutter-dart` /
   `markdown-corpus`) selecting which checks run and with which commands, so derived projects stop
   forking (`--scope wiki`) or abandoning checks (AJ coverage).
3. **Harness-ergonomics riders (triage #14)**: one-line greppable `ERROR <check>: <reason>`
   failures, machine-readable aggregates in the existing JSONL log (additive), and a `--fast`
   deterministic test-sampling flag for mid-build iteration.

## Context

Evidence (2026-07-14 performance review, 4-repo audit):
- VP: gate red **282/330 runs (85.5%)**; lint passed **0/330**; coverage `fail_under` lowered
  80→40 because 80 "was always `--skip`'d → guarded nothing"; `--no-verify` habituation.
- AJ (Flutter): red 556/1106 (50.3%); `ruff` fired on **Dart** (255 format / 191 lint fails);
  the 80% coverage gate was abandoned (15–20 min hangs in the Windows pre-commit subprocess).
- Wiki (markdown corpus): forked `quality_gate.py --scope wiki` because the Python gate never
  fit a markdown corpus.
- A permanently-red gate has zero signal value and actively trains bypass. This work is the
  explicit **precondition for reward-hacking canaries (triage #5)** — you cannot red-team a
  reward function that is already defeated by attrition.

Prior art consulted (searching-prior-art):
- The wiki's `--scope` fork and AJ's abandonment are the two live workarounds profiles replace.
- `memory/bugs/regression-ledger.md` embedded note: `_parse_regression_ledger()` cannot parse
  Known-Broken-Approaches rows (different 6-column schema) — earmarked for "a future
  quality_gate.py refactor". **Scope-fenced below** (must not regress; fixing it is optional).
- Gate-log JSONL (`metrics/quality_gate_log.jsonl`) now has telemetry consumers
  (`_build_outcome_record`, dashboard) — schema changes must be **additive only**.
- Education-gate checks landed in `quality_gate.py` on 2026-07-15 (commit 1d5c0f0) — profiles
  must compose with them, not bypass them.

## Requirements

### R1 — Debt baseline (green-able mechanism)
- R1.0 **Scope (arch A1)**: baselining in THIS build applies to the `python-fastapi` profile's
  ruff-based checks only. On other profiles the baseline mechanism explicitly no-ops with one
  `WARN baseline: not supported for profile <name>` line (never a crash, never a silent no-op).
  Dart/markdown baselining is a follow-on triage item, scope-fenced like the ledger-parser gap.
- R1.1 A committed baseline file `config/gate_baseline.json` records known pre-existing debt as
  **stable fingerprints** (per finding: check name, POSIX-normalized file path via
  `Path.as_posix()` (qa 4), rule/code — never line numbers, which drift). Fingerprints are
  extracted from `ruff check --output-format=json` / `ruff format --check` structured output,
  never scraped from human-format text (qa 3). Absent file == empty baseline (current template
  behavior unchanged).
- R1.1a **Corrupt baseline fails closed (qa 1)**: a baseline file that exists but is invalid
  (malformed JSON, non-dict shape, unknown schema version) → `ERROR baseline: <reason>`,
  non-zero exit. NEVER silently treated as empty — that would mask real debt as new-free.
- R1.2 Lint and format checks compare current findings against the baseline by **fingerprint
  set-membership, never by count (security F2)**: findings present in the baseline → reported as
  `WARN <check>: N baselined debt item(s)` and do NOT fail the gate; any fingerprint NOT in the
  baseline → `ERROR` and RED regardless of whether the total count shrank (a 1-for-1 swap of an
  old finding for a new one MUST fail).
- R1.3 **Ratchet down, never up**: if current debt ⊂ baseline (proper subset), the run reports
  the burn-down and `--fix`/`--shrink-baseline` rewrites the baseline to the smaller set. The
  baseline is NEVER grown implicitly.
- R1.3a **Out-of-band edits are review-gated (security F1)**: `config/gate_baseline.json` and
  the profiles config are added to `check_review_existence`'s review-triggering paths, so a
  direct Edit of the baseline (bypassing `--rebaseline`) cannot commit without a `/review` —
  the human gate is enforced by the gate itself, not just by behavioral instruction.
- R1.4 **Rebaseline is human-gated**: growing or creating the baseline requires an explicit
  `--rebaseline` flag, prints a "requires developer consent" notice, and writes a distinguishable
  `rebaseline: true` field into the gate-log record. The agent must never run `--rebaseline`
  autonomously (documented in the file header + CLAUDE.md gate section) — the baseline is part of
  the reward function (Principle #7 surface; canaries #5 will probe it).
- R1.5 Checks other than lint/format (tests, coverage, ADR, reviews, regression, education) are
  NOT baselined — they are pass/fail signal, not attritional debt. (Coverage debt is handled by
  profiles via per-profile thresholds, not by fingerprint baselining.)

### R2 — Stack-aware profiles
- R2.1 A committed `config/gate_profiles.yaml` declares available profiles. Each profile lists,
  per check: enabled/disabled, the command to run (argv list, never shell strings), and
  thresholds (e.g. coverage `fail_under`). Ships with three profiles: `python-fastapi` (the
  current behavior, byte-for-byte default), `flutter-dart` (dart format / dart analyze /
  flutter test), `markdown-corpus` (corpus checks only: ADR completeness, review existence,
  regression ledger, BUILD_STATUS freshness, promotion backlog; no ruff/pytest/coverage).
- R2.2 Selection order: `--profile <name>` flag > `profile:` key in the config file > stack
  auto-detect (`pubspec.yaml` → flutter-dart; `pyproject.toml` → python-fastapi; neither →
  markdown-corpus) with the detected choice printed once. **Auto-detect guard (security F6)**:
  if auto-detect lands on `markdown-corpus` while `.py` files exist under `src/`/`scripts/`,
  print a loud one-line warning (deleting `pyproject.toml` must not silently disable code checks).
- R2.3 Unknown or malformed profile → **fail closed** with a single `ERROR profile: <reason>`
  line (never silently fall back to python).
- R2.4 Framework-integrity checks (ADR completeness, review existence, regression ledger,
  education gates, BUILD_STATUS freshness, subscription-fee guard, promotion backlog) are
  **mandatory in every profile** — a profile can only vary stack checks (format, lint, tests,
  coverage), never disable Principle-#4/#6 enforcement. **Enforced in code (security F4)**:
  integrity checks run unconditionally; the profile schema has no key that can name or disable
  them, and a profile file attempting to do so has no effect (asserted by test, see AC5).
- R2.5 With no config file and no flags on this repo, behavior and summary output are unchanged
  (backward compatible; pre-commit hook and its 5-minute verification cache untouched).
- R2.6 Profile commands run via the existing `_run()` (list-argv `subprocess`, no `shell=True`;
  this single seam is also the test mock target — qa 6); profile-file content is data, never
  interpolated into a shell string. **Executable allow-list (security F3)**: a profile command's
  argv[0] must be one of an allow-listed set (`ruff`, `pytest`, `coverage`, `python`, `dart`,
  `flutter`) or the check fails closed — the config declares arguments, not arbitrary programs.
  Trust boundary documented in the profile file header: running the gate executes
  profile-declared commands; review `gate_profiles.yaml` before running the gate on any
  external repo.

### R3 — Harness-ergonomics riders
- R3.1 Every failing check emits exactly one stderr-greppable line of the form
  `ERROR <check>: <reason>` (in addition to the human summary). WARN lines follow the same
  one-line convention.
- R3.2 The existing JSONL gate-log record gains additive fields only: `profile`,
  `baseline_debt_count`, `rebaseline` (bool), `fast` (bool). A test pins the presence of every
  pre-existing field (telemetry-consumer contract).
- R3.3 `--fast`: deterministic test sampling for mid-build iteration — selects a stable subset of
  test files by content-independent ordering (e.g. sorted-path stride or stable hash), same
  subset for the same file list on every run, target ≤25% of full-suite wall time. `--fast` runs
  are marked `fast: true` in the log, print a "NOT a commit gate" notice, and the pre-commit hook
  never passes the flag. **`--fast` runs never refresh the pre-commit 5-minute verification
  cache (security F5)** — a sampled run must not stand in as commit-time verification.
- R3.4 Compact stdout: per-check one-line results (as today) — no multi-page dumps; failing
  tool output is truncated to the last 20 lines with a pointer to rerun the underlying command.
- R3.5 The `testing-playbook` skill gains a short section documenting the conventions in R3.1–R3.4
  for derived projects.

## Constraints

- Profile config format is **YAML via the already-imported `yaml.safe_load`** (arch A2 /
  security F7): `quality_gate.py:23` already imports PyYAML unconditionally (pinned dep), so
  the earlier "stdlib-only" framing was factually wrong for this file — no constrained parser,
  no build-time format fork. No NEW dependencies beyond what the script already imports.
- Do not regress `_parse_regression_ledger()`'s documented limitation (Known-Broken rows); fixing
  it is OPTIONAL scope, only if trivially adjacent, else untouched.
- Do not modify `.claude/hooks/pre-commit-gate.sh` semantics (verification-cache window, no
  `--skip-reviews` passthrough — both documented Known Limitations stay as-is).
- Gate-log JSONL: additive fields only (R3.2); never rename/remove existing fields.
- CORE artifact: mechanism + all three shipped profiles propagate via /apply-framework;
  a derived project's chosen `profile:` value and its baseline contents are SKIN.
- This repo's gate must remain 7/7 green with zero config after the change (dogfooding proof of
  R2.5).
- No new runtime dependencies; no network access from the gate.

## Acceptance Criteria

- [ ] AC1: (python-fastapi profile) Seed a temp project with 3 pre-existing lint violations + a
  baseline containing them → lint check WARNs (count=3) and the gate passes; add 1 new violation
  → gate fails RED and the `ERROR lint:` line names only the new finding's fingerprint.
- [ ] AC2: **Set-membership, incl. the swap case (security F2)**: with current debt {A,B} ⊂
  baseline {A,B,C}, the run reports burn-down and `--shrink-baseline` rewrites to {A,B}; with a
  1-for-1 swap ({A,B,D} vs baseline {A,B,C}, counts equal) the gate fails RED on D. The baseline
  never grows without `--rebaseline`.
- [ ] AC3: `--rebaseline` writes the new baseline, prints the human-consent notice, and the log
  record has `rebaseline: true`. Without the flag, a grown-debt state fails RED.
- [ ] AC3a: **Corrupt baseline fails closed (qa 1)**: existing-but-malformed baseline (invalid
  JSON / non-dict / 0-byte) → `ERROR baseline: <reason>` + non-zero exit, never treated as empty.
- [ ] AC3b: **Out-of-band edit is review-gated (security F1)**: with `config/gate_baseline.json`
  staged and no matching review, `check_review_existence` fails (test), so a direct baseline
  edit cannot commit unreviewed.
- [ ] AC4: Profile selection precedence (flag > config > auto-detect) verified by tests; unknown
  profile name AND present-but-empty/malformed profile file (qa 5) each fail closed with one
  `ERROR profile:` line and non-zero exit; the markdown-corpus-with-.py-files warning fires (F6).
- [ ] AC5: `flutter-dart` profile (mocked at the `_run()` seam — qa 6) invokes dart/flutter argv
  lists and does NOT invoke ruff/pytest; `markdown-corpus` runs only corpus checks. Both still
  run every mandatory framework-integrity check, AND a profile file attempting to disable an
  integrity check has no effect (R2.4/F4). A profile command with a non-allow-listed argv[0]
  fails closed (F3). Baseline on flutter-dart emits the R1.0 not-supported WARN (A1).
- [ ] AC6: On this repo with no config/flags: profile resolves to `python-fastapi`, all current
  checks run, summary output matches a **golden fixture captured from pre-change `main` before
  the build starts** (`tests/fixtures/gate_summary_golden.txt` — qa 2), gate 7/7 green
  (backward-compat test + live run).
- [ ] AC7: Forcing each check to fail in tests yields exactly one `ERROR <check>: <reason>` line
  per failure, machine-greppable (`^ERROR \w+: `).
- [ ] AC8: `--fast` selects a deterministic subset (same subset across two runs; changes only when
  the test-file list changes), marks the log `fast: true`, prints the not-a-commit-gate notice;
  the pre-commit hook path is verified to never pass `--fast`.
- [ ] AC9: A schema-pin test asserts every pre-existing gate-log field is still present and the
  four new fields are additive.
- [ ] AC10: Full existing test suite passes; coverage ≥80% including the new code.

## Risk Assessment

- **Gate is the reward function** (highest-stakes surface in the repo): a bug that silently
  baselines NEW debt would convert the gate from defeated-by-attrition to defeated-by-design.
  Mitigations: R1.4 human-gated rebaseline, fingerprints reviewed as committed diffs, AC1/AC3,
  and triage #5 canaries will probe exactly this surface next.
- **Backward compatibility**: derived projects and the pre-commit hook call today's CLI. Mitigation:
  R2.5 zero-config equivalence + AC6 + additive-only log schema (AC9).
- **Fingerprint stability**: line-number-based fingerprints would churn on every edit. Mitigation:
  R1.1 excludes line numbers (file + rule code + [normalized message]); accepted trade-off: two
  identical violations in one file collapse to one fingerprint (documented).
- **Windows subprocess hangs** (AJ evidence): profile commands inherit `_run()`'s existing
  timeout discipline; `--fast` reduces mid-build wall time — the pre-commit full run is unchanged
  (fixing AJ's hang is a derived-project deployment concern, not template scope).
- **Scope creep**: three triage items in one build. Bounded by: single file + config + tests +
  two docs; the regression-ledger parser fix explicitly optional; debt burn-down execution in
  VP/AJ is deployment work, NOT this build.

## Affected Components

- `scripts/quality_gate.py` — profiles, baseline, ergonomics (main change)
- `config/gate_profiles.yaml` (or `.json`) — NEW, committed, CORE
- `config/gate_baseline.json` — NEW mechanism; not committed here (template has zero debt), format
  documented in the profile file header + testing-playbook
- `tests/test_quality_gate.py` — new coverage for R1–R3
- `.claude/skills/testing-playbook/SKILL.md` — R3.5 conventions section
- `CLAUDE.md` — one-line update to the Quality & Commit Gates section (profile + baseline mention)
- `docs/CAPTURE_PIPELINE.md`, `docs/HOOKS.md`, `docs/FRAMEWORK_SPECIFICATION.md` (arch A4) —
  only where the log schema / check list is actually documented (verify at build,
  syncing-framework-docs)
- `check_review_existence` path list — extended to cover the two gate config files (R1.3a)

## Dependencies

- Depends on: nothing new (stdlib only). Education-gate checks (1d5c0f0) already in main — compose.
- Depended on by: triage #5 reward-hacking canaries (gated on this); derived-project debt
  burn-downs in VP + agentic_journal (deployment follow-ons); wiki fork retirement.
