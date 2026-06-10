---
spec_id: SPEC-20260610-035920
title: "--render-static export mode + legacy one-shot CLI retirement (Phase 5 Unit 5.1)"
type: spec
status: complete
risk_level: medium
reviewed_by: [architecture-consultant, qa-specialist, security-specialist]
discussion_id: DISC-20260610-040022-render-static-export-spec-review
intake_ids: []
completed_at: 2026-06-10
completed_commit: c5a9cf2
---

## Goal

Give `scripts/telemetry/dashboard_server.py` a one-shot `--render-static` CLI mode that
writes the full retrospective dashboard as a static HTML artifact — no server, no
standing process — and retire the legacy one-shot CLI in `scripts/telemetry/dashboard.py`
so the daemon script is the single telemetry entry point (parent spec
SPEC-20260607-183136 R4 + arch F5 disposition). Final unit of the Phases 3–5 directive.

## Context

- **R4 (parent spec):** "a thin one-shot CLI mode on the same read-side functions that
  writes a static HTML artifact (today's behavior) for headless/derived instances with
  no standing-process option. No server required."
- **R15 (single render path):** the static document and the live retrospective view must
  compose from the SAME `src/telemetry/dashboard.py` helpers. Today both already call
  `render_dashboard_html(assemble_dashboard_data(...))` — the export mode must reuse
  exactly that path, never a parallel one.
- **arch F5 disposition (REV-20260607-200447 indep #3):** `scripts/telemetry/dashboard.py`
  "retires INTO --render-static mode" — its dual existence as a second functional static
  entry point ends with this unit. The module SURVIVES as the read-side loader library
  (`assemble_dashboard_data`, `load_weekly_trends`, `load_cost_report`,
  `load_drift_inputs`, `_connect_readonly` are imported by the server); only its CLI
  surface (`main()`, argparse, webbrowser/tempfile usage, `if __name__` block) is removed.
- **Carried sec note (REV-20260610-030010 sec F1 sibling-pattern):** legacy `main()` still
  prints `str(exc)` on `sqlite3.OperationalError` — a latent raw-error passthrough. Its
  removal with the CLI is the fix; the new export path must use the sanitized copy already
  pinned in `print_console_summary`.
- **Prior art:** ntfy-slug ledger guard (never print `str(exc)` on paths that could embed
  secrets); `--summary` (Unit 4.3) established the one-shot-mode shape on the daemon CLI
  (digest-and-exit, honest missing-DB copy, sanitized OperationalError copy, no-mutation
  test). Developer decision #6: the artifact is written to the OS temp dir so personal
  cost/fee figures never enter the repo tree (`.gitignore` line 44 keeps the defensive
  entry).

## Requirements

- **U1 — `--render-static` flag** on `scripts/telemetry/dashboard_server.py`: assemble
  `DashboardData` via the existing `assemble_dashboard_data` (read-only), render via the
  existing `render_dashboard_html`, write `telemetry_dashboard.html` to the OS temp dir,
  print the artifact-mode console summary (`render_console_summary(data,
  output_path=str(out))`, which includes the `Dashboard: <path>` line), then exit. No
  server start, no port bind, no DB write. (`assemble_dashboard_data` is already
  imported by `dashboard_server.py` for the retrospective route — no new loader import;
  only `render_dashboard_html` may be new. Avoid an F811 re-add — arch fold.)
- **U2 — Browser behavior:** after a successful export, open the artifact
  (`webbrowser.open(out_path.as_uri())`) unless `--no-open` is passed — `--no-open` now
  documents that it applies to both server mode and export mode. **Invariant pin (sec
  F2):** `webbrowser.open` is safe here ONLY because `out_path` is a constant temp-dir
  path; any future `--out` affordance must re-review this surface.
- **U3 — One-shot modes are mutually exclusive:** `--summary` and `--render-static` live
  in an argparse mutually-exclusive group; passing both is a CLI error (exit code 2),
  not a silent precedence.
- **U4 — Honest absence + sanitized errors:** missing DB file prints the same
  plain-language copy shape as `print_console_summary` ("No telemetry database found at
  <path>. To initialize it, run: python scripts/init_db.py"), writes NO file, opens NO
  browser. `sqlite3.OperationalError` from the assembler prints the sanitized
  path-only copy (never `str(exc)`), writes NO file, opens NO browser.
- **U5 — Legacy CLI retirement:** remove `main()`, the `if __name__ == "__main__"` block,
  `DASHBOARD_FILENAME`, and the now-unused imports (`argparse`, `tempfile`, `webbrowser`,
  `render_console_summary`, `render_dashboard_html`) from `scripts/telemetry/dashboard.py`.
  Update its module docstring (arch fold): the line-1 identity becomes "Read-side
  loader library for the Telemetry Layer B dashboard"; remove the Usage block; add one
  sentence pointing CLI users at `python scripts/telemetry/dashboard_server.py
  --render-static` / `--summary`. `DASHBOARD_FILENAME` moves to `dashboard_server.py`
  (the only consumer post-retirement).
- **U6 — Test migration:** the legacy CLI tests in `tests/test_telemetry.py`
  (`test_main_no_open_writes_file_without_opening`, `test_main_opens_browser_without_no_open`,
  `test_no_slug_or_env_leak_on_no_db_path`) migrate to `--render-static` equivalents in
  `tests/test_dashboard_server.py` (semantics preserved, including the NTFY_TOPIC
  no-leak assertion).
- **U7 — Regression-ledger entry** naming the two closed doors: (a) a second static entry
  point on `scripts/telemetry/dashboard.py` (retirement pin), (b) the `str(exc)`
  passthrough on the export path. The (b) entry cites the AC5 sentinel-probe test
  function as the pinning test and `scripts/telemetry/dashboard.py:443` as the removed
  defect site (the legacy `OperationalError` branch was untested — qa fold).

## Constraints

- **R8/R13 inherited:** export mode binds nothing and performs no outbound IO beyond the
  local file write + `webbrowser.open` of a `file://` URI.
- **R10:** DB opened read-only by the assembler; export mode never calls
  `init_db`/analyzers; a no-mutation test mirrors the `--summary` AC5 parity test.
- **R11:** no new escaping logic — the artifact is `render_dashboard_html` output, whose
  escaping discipline is already pinned by the existing renderer tests.
- **No output-path flag (closed door):** the artifact path is fixed to
  `<tempdir>/telemetry_dashboard.html` (developer decision #6 — personal cost figures
  never enter the repo tree; an `--out` flag would add an arbitrary-write affordance for
  zero current need). A future headless consumer that needs a custom path should add
  `--out` with an explicit review of the decision-#6 trade-off, not silently relocate the
  default.
- **Fixed temp filename trade-off acknowledged (sec F1, A05):** a predictable name in a
  shared temp dir permits symlink-follow overwrite / co-tenant reads on multi-user
  systems. Accepted under the personal-machine deployment assumption (pre-existing
  legacy behavior carried forward). **Re-review trigger:** a shared-machine deployment
  context — switch to a non-predictable `tempfile.NamedTemporaryFile(delete=False,
  suffix=".html")` path at that point.
- **RenderMode enum NOT triggered (4.3 arch F1 watchpoint closed for this unit):**
  `render_console_summary` keeps exactly its two existing modes (`output_path=None`
  summary-only; `output_path=str` artifact). `--render-static` REUSES the artifact mode —
  no third renderer mode emerges, so the enum stays unbuilt (Principle #8). Trigger
  remains: a genuinely third output mode on the renderer.
- **Known-broken (ledger):** never print `str(exc)` in CLI error paths (slug/raw-error
  leak class).
- **Import-stripping gotcha (sessions 22/23):** the PostToolUse auto-format hook strips
  imports unused at edit time — when moving `DASHBOARD_FILENAME` + adding `tempfile` to
  `dashboard_server.py`, add imports AFTER their consumers exist; grep-verify after.

## Acceptance Criteria

- [ ] **AC1** `python scripts/telemetry/dashboard_server.py --render-static --no-open`
      with a populated DB writes `<tempdir>/telemetry_dashboard.html` whose content is
      `render_dashboard_html(assemble_dashboard_data(...))` output, prints the console
      summary including the `Dashboard: <path>` line, starts no server, and exits 0.
- [ ] **AC1a (qa F4)** `--render-static --no-open` on an initialized-but-empty DB
      (tables exist, no analyzer rows) writes a valid HTML file with the honest
      absence-state tiles, prints "not yet run" summary lines, and exits 0 — no crash.
- [ ] **AC2 (AC12 parent — byte-identical parity)** a test monkeypatches
      `dashboard_server.assemble_dashboard_data` to return one fixed `DashboardData` and
      asserts the bytes written by `--render-static` equal the body returned by
      `GET /fragments/retrospective` exactly (single render path, R15). **Determinism
      pin (qa F1):** the monkeypatched assembler IGNORES its `generated_label` argument
      and returns the fixed `DashboardData` unchanged — `render_dashboard_html` embeds
      only `data.generated_label`, so the clock-derived labels on the two paths cannot
      diverge into the rendered bytes.
- [ ] **AC3** without `--no-open`, the export opens `out_path.as_uri()` via
      `webbrowser.open` (monkeypatched probe); with `--no-open`, no browser call occurs.
- [ ] **AC4** missing DB file: prints the plain-language init copy, writes no file, opens
      no browser, exits 0 (informational absence, not a crash).
- [ ] **AC5** `sqlite3.OperationalError` from the assembler: printed message contains the
      DB path but NOT the exception text (probe with a sentinel message), writes no file,
      opens no browser.
- [ ] **AC6** `--summary --render-static` together exit with argparse error (code 2).
- [ ] **AC6a (qa F3)** `--render-static --port 9999` is accepted-and-ignored: exits 0
      after writing the file; the test asserts `run_server` was never called.
- [ ] **AC7** no-mutation (qa F2 shape): schema snapshot + row counts unchanged
      before/after the run (same pattern as
      `test_print_console_summary_does_not_mutate_database`) AND the `.db` file hash is
      unchanged. `-wal`/`-shm` sizes are NOT strictly asserted — a read-only open in WAL
      mode may legitimately create/touch the sidecars.
- [ ] **AC8 (qa F6 shape; amended by ux CP2 fold)** `assert not hasattr(dash, "main")`
      after import; the ONLY `__main__` block allowed is a signpost that prints the
      replacement command (`dashboard_server.py --render-static`) and never renders,
      writes, or opens anything (pinned by forbidding `webbrowser`/`tempfile`/`argparse`
      in the source — a stale alias gets a pointer, not a silent no-op); the loader surface
      (`assemble_dashboard_data`, `load_weekly_trends`, `load_cost_report`,
      `load_drift_inputs`) remains importable (existing import sites stay green).
- [ ] **AC9** the NTFY_TOPIC no-leak assertion migrates: with `NTFY_TOPIC` set and a
      missing DB, `--render-static` output never contains the slug value.
- [ ] **AC10** regression-ledger entry added (two doors, U7, citing the AC5 test
      function + the removed defect site) and quality gate passes 7/7.
- [ ] **AC11 (arch F-MED)** `docs/FRAMEWORK_SPECIFICATION.md` and
      `docs/CAPTURE_PIPELINE.md` contain no remaining
      `python scripts/telemetry/dashboard.py` invocation lines; any surviving prose
      reference to that module describes it as the read-side loader library, not a CLI
      (verify with `grep -rn "python scripts/telemetry/dashboard.py" docs/` —
      historical review/spec artifacts are immutable and exempt).

## Risk Assessment

- **Removing a public-ish CLI someone scripts against** — LOW: the framework's own docs
  point at the dashboard daemon; ADR-0020 pointer in CLAUDE.md names
  `dashboard_server.py`. Mitigation: docstring of the retired module names the
  replacement command.
- **Parity test brittleness** (clock label) — mitigated by monkeypatching the assembler
  so both paths see the identical `DashboardData` including `generated_label`.
- **Import-strip hook reintroducing NameErrors** — named in Constraints; grep-verify.
- **Doc drift** — parent spec Phase 5 bullet + ADR-0020 pointer reference the old script;
  check `docs/` references to `scripts/telemetry/dashboard.py` at build time and update
  stale run instructions (CAPTURE_PIPELINE.md / README if they name the legacy command).

## Affected Components

- `scripts/telemetry/dashboard_server.py` — `--render-static` flag, export function,
  `DASHBOARD_FILENAME`, mutually-exclusive group, docstring Usage block.
- `scripts/telemetry/dashboard.py` — CLI retirement; docstring rewrite (loader library).
- `tests/test_dashboard_server.py` — new export-mode tests (AC1–AC7, AC9).
- `tests/test_telemetry.py` — legacy CLI tests removed/migrated; AC8 pin added.
- `memory/bugs/regression-ledger.md` — U7 entry.
- Possible doc touch-ups where the legacy command is named (Risk #4).

## Dependencies

- Depends on: existing `assemble_dashboard_data` / `render_dashboard_html` /
  `render_console_summary` (unchanged); `--summary` mode shape (Unit 4.3).
- Depended on by: nothing — this is the terminal unit of SPEC-20260607-183136 Phase 5;
  its completion closes the parent spec's phasing backlog.
