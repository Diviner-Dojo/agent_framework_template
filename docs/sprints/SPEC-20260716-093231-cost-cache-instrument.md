---
spec_id: SPEC-20260716-093231
title: "Cost/cache instrument — durable per-call token log + cache-read ratio + auto-run seam"
type: spec
status: complete
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260716-163352-cost-cache-instrument-spec-review
build_discussion_id: DISC-20260716-172245-build-cost-cache-instrument
intake_ids: ["2026-07-14 perf review P1·#3", "gap-analysis synthesis §2.5/§2.7", "triage item #1 (brainstorms/2026-07-15-review-triage.md)"]
completed_at: 2026-07-16
completed_commit: efc1b5f
---

> rev 2 — folds the spec-review panel's findings (1 security BLOCKING, 3 qa BLOCKING,
> arch advisories). Panel verdicts: arch approve-with-changes 0.82, security
> approve-with-changes 0.82, qa approve-with-changes 0.78.

## Goal

Make the framework's token/cost sensing actually produce data. Three deliverables:

1. **Durable per-call token log** — one JSONL line per model call (assistant message) with
   `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`,
   and the `cache_read / total_input` ratio, deduped by message id, appended to
   `metrics/model_call_log.jsonl` (gitignored — see Constraints).
2. **Cache-read ratio in the cost report** — `src/telemetry/cost.py` computes
   `cache_read / (input + cache_read + cache_creation)` **per tier and overall** (pure
   properties on the existing `TierCost`/`CostReport` objects — the report groups by tier,
   not model; computed at read time, never stored in the DB — ADR-0013).
3. **Auto-run seam** — `scripts/stop_hook.py` kicks the instrument on turn end as a
   **timeout-bounded subprocess** (`subprocess.run([sys.executable, <call_log.py>, "--from-hook"],
   timeout=<budget>, capture_output=True)`), reusing the R6 CLI as the entry point. The
   subprocess boundary is load-bearing: it gives a cross-platform hard time-box (no SIGALRM
   on Windows), keeps the hook's import/fault surface unchanged, and makes stdout pollution
   of the hook's decision channel structurally impossible. The `Stop` hook entry in
   `.claude/settings.json` is a **developer-applied manual edit** (protected file; ADR-0018
   precedent) — the spec ships the exact snippet. Until wired,
   `python scripts/telemetry/call_log.py` works as a manual runner.

## Context

The 2026-07-14 performance review (P1·#3): *"All token/cost telemetry is NULL across VP's
617 commits… Capture the three usage numbers per call and log `cache_read / total`. That one
ratio is the leading indicator the synthesis §2.5 says you're blind to."* Triage verdict:
ADOPT NOW, wave 1 (developer-approved 2026-07-15).

Scouting (2026-07-16) found the failure is **pipeline-not-running, not missing writers**:
- `scripts/ingest_token_usage.py` already parses all three token fields per message
  (`MessageRecord`, `_parse_message_line`); `analyze_cost.py` writes per-(discussion, model)
  aggregates to `discussion_model_tokens` with watermark incrementality (`telemetry_run_state`).
- Nothing invokes these on any schedule; `stop_hook.py` (ADR-0023) exists but has **no `Stop`
  entry in `.claude/settings.json`** — the wiring was never applied.
- No cache ratio is computed anywhere; per-call granularity exists only in `~/.claude`
  transcripts, which are pruned over time — the per-call record is currently ephemeral.

Developer pinned scope (2026-07-16, AskUserQuestion): per-call JSONL + Stop-hook auto-run +
lean /plan. **Anti-bloat corollary (ratified):** dashboard extension stays FROZEN — this is
sensor-only; no new panels, no new tables.

## Requirements

- **R1 (emitter):** New `scripts/telemetry/call_log.py`. Reuses `ingest_token_usage`
  transcript discovery + parsing (public A-ARCH1 helpers; no re-implementation of path
  logic). Appends one JSON object per new assistant message:
  `{ts, session_id, source_kind: main|subagent, model, input_tokens,
  cache_read_input_tokens, cache_creation_input_tokens, output_tokens, cache_read_ratio,
  message_id}`.
  - `source_kind` comes from a new field on `MessageRecord` populated inside
    `parse_session_dir`/`_iter_jsonl_files` (which already distinguish `subagents/`) — the
    emitter must NOT re-derive it from path inspection (parser owns path knowledge).
  - Ratio denominator = `input + cache_read + cache_creation`. Emit `null` when the
    denominator is 0 **or when any component is `None`** — `None` = unknown is never
    silently treated as 0 (repo honest-null convention).
  - The ratio field is a recomputable grep convenience (docstring notes this), not a stored
    derived metric in the ADR-0013 sense; dollars are never logged.
  - Docstring also notes: fields are opaque transcript-derived strings — future consumers
    parse with `json.loads` only, never string-interpolate into shell/path/eval; and
    deleting the JSONL does NOT rebuild it (dedup state lives in the DB).
- **R2 (dedup + incrementality):** Never logs the same `message_id` twice across runs.
  State = a `{watermark_ts, boundary_message_ids}` record in `telemetry_run_state`
  (new key, `analyze_cost` pattern): each run scans only messages with `ts >= watermark_ts`,
  dedupes ties at the boundary against `boundary_message_ids`, then persists the new
  boundary. As built (stronger than this prose): the watermark trails the newest logged
  message by `FLUSH_LAG_SECONDS` and the id set covers that whole trailing window, so
  late-flushed transcript lines within the window are caught, not just exact-tie ids. The emitter must never re-read the whole JSONL to rebuild the seen-set
  (O(file) growth — the objection ADR-0020 Alt-4 was rejected on). The load-bearing tie
  case: a message whose `ts` equals the stored watermark with a previously-unseen
  `message_id` MUST still be logged (a strict `>` selector would silently skip it).
- **R3 (ratio in cost report):** `src/telemetry/cost.py` exposes **per-tier** and overall
  `cache_read_ratio` as pure properties on `TierCost`/`CostReport`. No schema change;
  `None` (honest absence) when the denominator is 0 — never a fabricated `0.0`.
- **R4 (auto-run):** `stop_hook.py` runs the telemetry kick on Stop, structured as follows:
  - (a) **Placement/precedence:** the kick runs independently of the ntfy-intent logic
    (which stays byte-for-byte untouched), but `STOP_HOOK_DISABLE=1` remains the master
    off-switch for the ENTIRE hook including telemetry (docstring guarantee preserved);
    `STOP_HOOK_TELEMETRY_DISABLE=1` disables only the kick.
  - (b) **Throttle:** skip if the last ATTEMPT is younger than a floor (default 10 min).
    The stamp is written eagerly at attempt start (a persistently broken ingest costs at
    most one budget per floor, never one per turn; no data is lost — the watermark advances
    only on success). Throttle state lives under `.claude/hooks/.state/`; reads are wrapped
    in the kick's fail-silent contract (parse failure ⇒ eligible to run); writes are atomic
    (write-tmp + `os.replace`).
  - (c) **Time-box:** the kick invokes the R6 CLI via `subprocess.run(..., timeout=<budget>,
    capture_output=True)` (default ≤15 s). Inside `call_log.py`, the scan loop ALSO checks a
    cooperative deadline between transcript files (deterministically unit-testable with a
    fake clock); the subprocess timeout is the hard backstop for a blocked call.
  - (d) **Output contract:** the kick never writes to the hook's stdout — child output is
    captured and discarded (error paths print exception TYPE only to stderr; no-slug). The
    hook's stdout remains reserved for exactly one JSON decision object.
  - (e) **Fail-silent:** any exception (including `TimeoutExpired`) is caught; the hook
    always proceeds and exits 0.
- **R5 (settings snippet):** The spec/PR delivers the exact `"Stop"` hooks block for the
  developer to paste into `.claude/settings.json` (timeout sized to the R4 budget + the
  existing ntfy wait budget: the parked draft uses 660 — see REV-20260613 finding 4).
- **R6 (manual runner):** `python scripts/telemetry/call_log.py` runs one incremental pass
  standalone with an ASCII-only one-line stdout summary (calls logged, batch cache ratio,
  watermark advanced-to). With `--from-hook`, the summary goes to stderr and stdout stays
  silent (defense in depth behind the subprocess capture).
- **R7 (tests):** pytest coverage following `tests/test_telemetry.py` patterns — fake
  transcripts in tmp dirs, monkeypatched roots, never live `~/.claude`. Write-side isolation:
  the JSONL output path AND throttle state path are monkeypatchable module-level constants
  overridden to `tmp_path` in every test (`stop_hook.STATE_FILE` pattern). Must cover:
  dedup across runs incl. the watermark-tie case; ratio math incl. zero-denominator AND
  `None`-component honesty (parametrized separately); symlink-escape guard; cooperative
  deadline (fake clock jumps mid-loop ⇒ N of M files processed, no real sleeps/threads);
  hook subprocess invocation (mocked `subprocess.run`, assert timeout + captured output +
  args); throttle eager-stamp incl. failed-run case; both disable flags; truncated trailing
  JSONL line tolerated (emitter appends cleanly after it); ASCII round-trip of all new
  console output (cp1252 class — 4 prior recurrences); stdout-purity (AC11).

## Constraints

- **No DB schema change** beyond the additive `MessageRecord` field (a dataclass, not DDL).
  `discussion_model_tokens` and `turns` columns are untouched. (Avoids the `_migrations`
  DDL-allowlist surface — regression ledger 2026-06-05/06.)
- **`metrics/model_call_log.jsonl` is gitignored.** It grows per call (the historical corpus
  is ~265M tokens); committing it would bloat the repo and worsen the shared-bookkeeping
  noise-carry problem (`quality_gate_log.jsonl` precedent). Durability = survives transcript
  pruning on the operator's machine; Layer-2 committed artifacts remain the DB aggregates.
  Divergence from ADR-0020's "new granularity = new table" precedent is recorded as an
  implementation note appended to ADR-0020 (see Affected Components).
- **No dollars in the log.** Cost is computed at read time from `model_pricing.yaml`
  (ADR-0013 compute-don't-store); a logged dollar would go stale on repricing. The ratio is
  a pure token-count derivation and is exempt (it can never drift).
- **Concurrent writers: accepted risk, stated.** Two simultaneous sessions can both pass the
  throttle and append concurrently; mitigation is per-line flush appends and reader-side
  corrupt-line tolerance (single-developer machine; an interleaved line is skipped like any
  corrupt line). No cross-process lock is added (sensor-only scope).
- **`stop_hook.py` invariants are load-bearing** (its docstring + regression ledger
  2026-06-07): allow-list reply injection, single-poller lock, no-slug, ASCII console,
  one-shot intent deletion, stdout reserved for the single JSON decision object. The
  telemetry kick must not touch any of them.
- **No `.claude/settings.json` edit by the agent** (protected file; PreToolUse validator).
  R5 is a handed-to-developer snippet, exactly like the ADR-0018 `ALLOW_AUTO_LAUNCH_SESSION`
  opt-in.
- **Dashboard FROZEN** — no render/panel work; `dashboard_server.py` untouched.
- **Symlink guard:** every transcript file the emitter opens re-checks
  `is_inside_projects_root` (regression ledger 2026-06-06, two prior escapes in A2).
- **Windows-first:** ASCII-only console output; `pathlib`; no POSIX-only calls (hence the
  subprocess time-box, not SIGALRM).
- **Double-parse accepted:** if the kick also triggers `analyze_cost`, both passes are
  watermark-bounded so the incremental corpus is small; a single shared
  `collect_messages` pass is a permitted build-time optimization, not a requirement.

## Acceptance Criteria

- [ ] AC1: A fake-transcript run produces one JSONL line per assistant message with all
      three input-side token fields, `output_tokens`, `cache_read_ratio`, `message_id`,
      and `source_kind` (main vs subagent) taken from `MessageRecord`, not path parsing.
- [ ] AC2: Running the emitter twice over the same corpus appends zero duplicate
      `message_id` lines — including the tie case: a message with `ts` EQUAL to the stored
      watermark and an unseen `message_id` is still logged (strict `>` would skip it), and
      the seen-set is never rebuilt by re-reading the whole JSONL. Carve-out (reviewed,
      accepted): a corrupted state blob triggers exactly ONE full re-log — duplicates, not
      loss; readers dedup by `message_id` (see the module docstring's accepted bounds).
- [ ] AC3: `cache_read_ratio` is `null`/`None` (not `0.0`) both when the denominator is 0
      and when any component is `None` (parametrized separately), in the JSONL line and the
      cost report.
- [ ] AC4: `src/telemetry/cost.py` reports **per-tier** (`TierCost`) and overall
      (`CostReport`) cache-read ratio; DB row counts and schema unchanged by report
      building (existing compute-don't-store guard still green).
- [ ] AC5: With a queued ntfy intent AND the telemetry kick both active, `stop_hook.py`
      preserves the intent one-shot behavior (existing tests stay green) and the telemetry
      failure path cannot make the hook exit non-zero or print a slug.
- [ ] AC6: Throttle: two back-to-back hook invocations within the floor run the ingest once,
      and a FAILED run still stamps the throttle (eager). Time-box: (i) unit — a fake clock
      jumping past the cooperative deadline mid-loop stops after N of M files with no real
      sleeps or orphaned threads; (ii) hook — mocked `subprocess.run` is invoked with the
      budget as `timeout` and captured output, and `TimeoutExpired` is swallowed.
      Kill-switches: `STOP_HOOK_TELEMETRY_DISABLE=1` skips the kick;
      `STOP_HOOK_DISABLE=1` skips the entire hook including the kick.
- [ ] AC7: A symlinked transcript pointing outside `~/.claude/projects` is skipped, not read.
- [ ] AC8: All new console output round-trips through `ascii` and `cp1252` encodings.
- [ ] AC9: `metrics/model_call_log.jsonl` is matched by `.gitignore` (test asserts).
- [ ] AC10: Quality gate 7/7 (coverage ≥80%) on the branch.
- [ ] AC11: **Stdout purity** — with a matched-reply intent and the telemetry kick both
      active in one hook run, the hook's stdout contains exactly one JSON object,
      byte-identical to the no-telemetry case.
- [ ] AC12: A truncated trailing line in an existing `model_call_log.jsonl` (killed writer)
      does not crash the emitter; new lines append cleanly after it.

## Risk Assessment

- **Hook path regression** (medium): stop_hook.py carries security invariants; mitigated
  structurally by the subprocess boundary (import surface + stdout channel unchanged by
  construction), AC5/AC11, and the existing test suite.
- **Runaway growth of the JSONL** (low): gitignored; append-only; size note in the module
  docstring; rotation deliberately deferred (YAGNI — revisit when the file exceeds ~50 MB).
- **Stop-hook latency** (medium): every turn end pays a file-stat throttle check; a full
  ingest runs at most once per floor and is hard-bounded by the subprocess timeout. Worst
  case adds ≤15 s to one turn end per 10 min.
- **Double-write vs analyze_cost** (low): independent watermark keys, no shared mutable
  state; double parse accepted per Constraints.
- **The wiring never gets applied** (medium — the exact failure being fixed): mitigated by
  R6 manual runner + the PR/education step explicitly handing the developer the one-line
  settings edit, and BUILD_STATUS carrying it as an open obligation until applied.

## Affected Components

- `scripts/telemetry/call_log.py` (new — emitter + CLI, `--from-hook` mode)
- `scripts/ingest_token_usage.py` (additive `MessageRecord.source_kind` field)
- `src/telemetry/cost.py` (per-tier + overall ratio properties)
- `scripts/stop_hook.py` (telemetry kick: throttle + subprocess, additive)
- `.gitignore` (one line)
- `docs/adr/ADR-0020-telemetry-oversight-component.md` (implementation note: per-call
  JSONL-vs-table decision — arch ADVISORY-1)
- `tests/test_call_log.py` (new — emitter/ratio tests co-located with the new module) /
  `tests/test_stop_hook.py` (autouse telemetry isolation fixture + kick tests)
- Handed to developer, not agent-applied: `.claude/settings.json` `Stop` block

## Dependencies

- Depends on: `scripts/ingest_token_usage.py` public helpers (A-ARCH1),
  `telemetry_run_state` watermark table (ADR-0020 A1), `scripts/stop_hook.py` (ADR-0023).
- Depended on by: triage #5 canaries + #7 calibration read-back (need real cost data),
  Telemetry dashboard un-freeze (gated on this sensor existing), #14 greppable-logs rider.
