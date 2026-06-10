---
spec_id: SPEC-20260610-005602
title: "Layer B Phase 4 Unit 4.1 — hook-health chip (read-only self-monitoring)"
type: spec
status: complete
risk_level: medium
intake_ids: []
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260610-005705-hook-health-chip-spec-review
completed_at: 2026-06-10
completed_commit:
---

## Goal
A small status chip in the live dashboard shell showing whether the framework's
Claude Code hooks are configured and their script files present, with **honest,
narrowly-labelled recency evidence** (the pre-commit quality gate's last run).
The gatekeeper sees at a glance "the enforcement layer is wired" vs "something
is missing" — without the dashboard ever executing or touching a hook.

## Context
- Parent spec **SPEC-20260607-183136** R6 names "hook-health self-monitoring" as a
  Phase 4 surface; §Internal Phasing line 229 lists "hook-health chip" first.
- The dashboard's Steward conditions make this the most safety-sensitive Phase 4
  unit: **AC1** (no hook starts the server), **AC3** (no-inject: importing the
  server pulls no `hooks`/`settings` *module*; every endpoint leaves
  `.claude/hooks/` + `settings.json` **byte-unchanged**), **R9** (display-parity
  only). The chip must be a pure *observer* of hook wiring.
- Established seams to reuse (Phase 1-3 precedent):
  - **R14 purity split**: pure model/render in `src/telemetry/`, file IO at the
    transport layer (`scripts/telemetry/dashboard_server.py`).
  - **weekly_panel_html precedent**: the server computes transport-side data,
    renders via a public `src/telemetry/dashboard.py` helper, and passes
    pre-rendered HTML into `render_live_fragment(...)` — the fragment renderer
    stays pure and ignorant of IO.
  - **ADR-0020 honesty discipline**: absence is typed and labelled, never a
    fabricated "all good". One activity signal (gate log) must not be presented
    as "all hooks firing".
- Read-only signals available today (investigated this session):
  - `.claude/settings.json` top-level `"hooks"` key — the configured hook
    inventory (events → commands referencing `.claude/hooks/<script>` files).
    **Real layout note (qa F1)**: `statusLine` is a TOP-LEVEL SIBLING of
    `"hooks"`, NOT nested inside it. It is **intentionally excluded** from this
    unit's health claim — it is a context sensor, not an enforcement hook; the
    chip's claim is scoped to the `"hooks"` block only.
  - `.claude/hooks/*` script files — presence on disk.
  - `metrics/quality_gate_log.jsonl` — one JSON object per line with a
    `timestamp` field; the last entry is evidence the pre-commit-gate hook's
    underlying gate last ran. (Other hooks leave only ephemeral `.state` files —
    NOT used this unit; per-session, unreliable as health evidence.)

## Requirements
- **R-4.1.1 — Pure check module** `src/telemetry/hooks_health.py` (stdlib-only
  imports; no IO; no `scripts.*` imports; never executes anything):
  - `HookConfigParse` frozen dataclass (arch F1): `script_refs: tuple[str, ...]`
    (deduplicated `.claude/hooks/` script file **basenames**, first-seen order),
    `hook_count: int` (total hook command entries).
  - `parse_hook_script_refs(settings_text: str | None) -> HookConfigParse` —
    pure. Walks ONLY the top-level `"hooks"` key (statusLine intentionally out
    of scope, see Context). **Extraction strategy pinned (qa F2)**: a path-
    pattern match (regex of the form `\.claude/hooks/([A-Za-z0-9_.\-]+)`)
    applied to each `command` string — covers BOTH production command forms
    (`bash .claude/hooks/x.sh` and
    `powershell -ExecutionPolicy Bypass -File .claude/hooks/y.ps1`) by
    construction. **Basename-only, minimum disclosure (security F1)**: only the
    final path component is captured; the full command string is NEVER stored,
    returned, or rendered. `script_refs` is deduplicated (qa F5). A command
    with no `.claude/hooks/` reference still counts toward `hook_count`.
    Malformed JSON, `None` text, missing/empty/`null`/non-dict `"hooks"` →
    `hook_count == 0` (→ `not_configured`), never a raise (qa F8).
  - `HookHealthReport` frozen dataclass: `status`, `hooks_configured: int`,
    `scripts_missing: tuple[str, ...]` (deduplicated basenames),
    `last_gate_run: datetime | None` (tz-aware when present; `None` = no run
    observed).
  - Status constants: `HOOK_STATUS_OK` ("ok": ≥1 hook configured, no referenced
    script missing), `HOOK_STATUS_MISSING_SCRIPTS` ("missing_scripts"),
    `HOOK_STATUS_NOT_CONFIGURED` ("not_configured").
  - `assess_hook_health(parsed: HookConfigParse, missing: tuple[str, ...],
    last_gate_run: datetime | None) -> HookHealthReport` — pure assembly from
    already-resolved facts (arch F2 shape).
- **R-4.1.2 — Transport loader** in `scripts/telemetry/dashboard_server.py`:
  **public** `load_hook_health(repo_root: Path) -> HookHealthReport` (arch F3 —
  matches the `load_weekly_trends` precedent: direct unit tests + route
  consumer). Reads `settings.json` text (missing/unreadable → `None`); stats
  each ref as `hooks_dir / Path(ref).name` — **basename re-normalized at the
  stat site so no path component from config can escape `.claude/hooks/`
  (security F2)**; reads the gate-log recency evidence with a **bounded tail
  read (arch F4 / security F4)**: seek to the last `_GATE_LOG_TAIL_BYTES`
  (named constant, 4096) of `metrics/quality_gate_log.jsonl`, scan the lines in
  that window BACKWARD for the last **well-formed** entry — defined (qa F4) as
  valid JSON object with a `"timestamp"` key parseable as an ISO-8601 datetime;
  the parsed datetime MUST be tz-aware (naive timestamps are treated as
  malformed). Trailing malformed lines fall back to the previous well-formed
  entry within the window (definite contract, not implementation choice); no
  well-formed entry in the window / missing file → `None`. **Strictly
  read-only**: `open`-for-read + `is_file` only; never executes a hook, never
  opens for write, never imports a hook module. Per-poll cost bounded by
  construction (one small JSON read + ~10 stats + one ≤4KB tail).
- **R-4.1.3 — Render** via a public `render_hook_health_chip(report) -> str` in
  `src/telemetry/dashboard.py` (weekly precedent): a compact chip element
  rendered into the live fragment header area. `render_live_fragment` gains
  `hook_health_chip_html: str = ""` (default empty = absent, additive contract;
  existing callers unaffected). All dynamic fields `_esc`'d **inside
  `render_hook_health_chip`** (security F3); the `render_live_fragment`
  docstring documents the pre-rendered-HTML caller contract: only HTML produced
  by a `src.telemetry.dashboard` render helper may be passed. Status copy from
  a static `_HOOK_HEALTH_STATUS_LABEL` map co-located with `_LANE_STATUS_LABEL`
  in `dashboard.py` (arch F5 — model owns the vocabulary constants, render owns
  the manager-facing copy); no JS, no new static assets, no CSP change.
- **R-4.1.4 — Honesty (ADR-0020)**:
  - Recency line is narrowly labelled — "quality gate last ran <UTC label>" /
    "no quality-gate run observed" — NEVER "hooks last fired" (the log
    evidences exactly one hook's underlying gate).
  - `not_configured` renders an honest absence chip ("Hooks: not configured"),
    not an error and not silence.
  - `missing_scripts` names the count and the missing file basenames in the
    title attribute / accessible text, plain language for the
    manager-gatekeeper.
- **R-4.1.5 — Invariant preservation**: AC3(a) static import allowlist — any
  allowlist-test update for `src.telemetry.hooks_health` is made **explicitly
  and documented as intentional** (security F5), plus a DIRECT purity test for
  the new module (qa F6, mirroring the failures/drift/live/weekly precedent);
  AC3(b) behavioral byte-unchanged test stays green and is the authoritative
  guard that the loader never mutates `.claude/`; AC1 grep/test untouched.

## Constraints
- Never execute hooks or any subprocess; never write to `.claude/` or
  `metrics/`; never import `.claude/hooks/` Python modules (AC1/AC3/R9).
- Pure/transport split per R14; single render path per R15.
- Stack: Python 3.11+, pytest, ruff; coverage ≥80%; no new dependencies, no
  new frontend assets (server-rendered HTML chip only — no SHA-384 re-pin).
- Compute-don't-store (ADR-0013): no DB columns; the report is derived per
  request and persisted nowhere.
- Windows-first repo: settings.json read with `encoding="utf-8"`; path checks
  via `pathlib`.
- **Rule-of-Three watchpoint (arch F6)**: `hook_health_chip_html` is the SECOND
  additive HTML param on `render_live_fragment`. If a Phase 4/5 unit adds a
  THIRD, fold all extras into one composition shape at that build — not now.

## Acceptance Criteria
- [ ] AC-U1: `parse_hook_script_refs` against a fixture mirroring the REAL
      settings layout — `statusLine` as a TOP-LEVEL sibling of `"hooks"`
      (asserted NOT counted: intentional exclusion), PreToolUse matcher lists,
      UserPromptSubmit global list, BOTH command forms (`bash …` and
      `powershell … -File …` — same extracted basename), and a command
      carrying a mock token, asserting the token appears in NO output field
      (security F1).
- [ ] AC-U2: malformed JSON, `None` text, missing `"hooks"` key, empty
      `"hooks"` block, `"hooks": null`, and a hooks block whose commands
      reference no script file each map to the correct status without raising.
- [ ] AC-U3: referenced-but-absent script yields `missing_scripts` with the
      basename carried; mixed present/absent handled; TWO hooks referencing the
      SAME absent script yield the basename exactly once (deduplicated) while
      `hooks_configured` still counts both commands (qa F5).
- [ ] AC-U4: chip renders all three statuses with correct class + label;
      injection round-trip on a hostile script name asserted escaped INSIDE
      `render_hook_health_chip` (security F3); recency copy uses the narrow
      "quality gate last ran" framing; `last_gate_run=None` renders the honest
      "no quality-gate run observed".
- [ ] AC-U5: `render_live_fragment` default (`""`) renders NO chip markup;
      non-empty chip HTML appears in the fragment EXACTLY once, asserted with
      `fragment.count(marker) == 1` — not `in` (qa F7).
- [ ] AC-U6: transport `load_hook_health` against a `tmp_path` fixture tree:
      happy path; missing settings; missing log; log whose trailing lines are
      malformed (falls back to the last well-formed entry — definite contract);
      log with ONLY malformed lines → `None`; returned datetime is tz-aware
      (qa F4); a config ref containing `../` does not stat outside
      `.claude/hooks/` and surfaces only the basename (security F2); missing
      scripts; fixture tree byte-unchanged asserted in at least one test.
- [ ] AC-U7: `/fragments/live` via TestClient carries the chip — response body
      contains the chip marker with `count == 1` (confirms `load_hook_health`
      ran, qa F3); the existing AC3(b) byte-unchanged behavioral test still
      passes with the new read path exercised.
- [ ] AC-U8: regression-ledger entry; quality gate 7/7.
- [ ] AC-U9: direct purity test — importing `src.telemetry.hooks_health` in a
      clean state pulls no third-party module (stdlib-only delta, qa F6); any
      AC3(a) allowlist change is explicit + commented as intentional
      (security F5).

## Risk Assessment
- **Reading developer config from a server route** — mitigated: read-only,
  loopback-only server, generic error handling already wraps the fragment
  route; settings content is never echoed raw — only counts, status, and
  script file *basenames* reach HTML; full command strings never leave the
  parser (security F1).
- **False confidence** — the chip could be read as "all hooks executed
  recently". Mitigated by R-4.1.4 narrow labelling (config-presence is the
  claim; gate-log recency is the only activity claim, named as such).
- **Per-poll IO growth** — bounded by construction (≤4KB tail read + ~10
  stats); same order as the accepted per-poll weekly DB read.
- **Schema drift in settings.json hooks block** — parser is tolerant; any
  unrecognized shape degrades to honest `not_configured`/count-only, never a
  crash (fragment route also has a generic catch).

## Affected Components
- `src/telemetry/hooks_health.py` (NEW — pure model)
- `src/telemetry/dashboard.py` (chip renderer + `render_live_fragment` param)
- `scripts/telemetry/dashboard_server.py` (transport loader + fragment wiring)
- `tests/test_telemetry.py` (pure + render tests)
- `tests/test_dashboard_server.py` (transport + endpoint tests)
- `memory/bugs/regression-ledger.md` (ledger entry)

## Dependencies
- Depends on: SPEC-20260607-183136 Phases 1-3 (live shell, fragment seam,
  weekly_panel_html precedent) — all committed.
- Depended on by: Phase 4 Units 4.2-4.4 + Phase 5 only via the shared fragment
  surface (no API coupling; chip param is additive).
