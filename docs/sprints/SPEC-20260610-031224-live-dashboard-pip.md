---
spec_id: SPEC-20260610-031224
title: "Picture-in-Picture pop-out for the live telemetry dashboard (Phase 4 Unit 4.4)"
type: spec
status: complete
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260610-031327-live-dashboard-pip-spec-review
intake_ids: []
completed_at: 2026-06-10
completed_commit:  # stamped retroactively once the unit commit SHA exists
---

## Goal

Let the gatekeeper pop the live telemetry view into a small floating
always-on-top window (Document Picture-in-Picture API) so session cost,
runway, and failure signals stay visible while they work in other windows.
The dashboard's value proposition is ambient oversight; a tab buried behind
an editor delivers none of it.

## Context

- Parent spec: SPEC-20260607-183136 §Internal Phasing — "Phase 4 —
  Self-monitoring + extras: hook-health chip; model-cost donut; CLI inline
  summary; **Picture-in-Picture**."
- The live shell (`render_live_shell_html`, `src/telemetry/dashboard.py`)
  polls `/fragments/live` every 3 s via htmx `outerHTML` swap. Chart init
  lives in the vendored first-party `/static/dashboard-chart.js`, which
  re-initialises on every `htmx:afterSwap` (the swap destroys the canvases).
- CSP is strict and PINNED BY TEST (`test_security_headers_pin_exact_csp`):
  `script-src 'self'` — NO inline script, NO CDN; `style-src` permits inline
  `<style>`; `frame-ancestors 'none'`; `object-src 'none'`. The CSP string
  must NOT change for this unit.
- Vendoring discipline: every file in `src/telemetry/static/` has a SHA-384
  pin row in `src/telemetry/static/README.md` plus a `_*_SHA384_PIN` test
  constant in `tests/test_dashboard_server.py` (supply-chain freeze, not
  browser SRI). A NEW static file gets its own pin row + pin test.
- Browser support: the Document PiP API (`window.documentPictureInPicture`)
  is Chromium-only (Chrome/Edge 116+). Firefox/Safari users must see an
  honest absence — the affordance stays hidden, never a broken button.
- Prior art searched (memory/projects, regression ledger, ADRs): no PiP or
  pop-out solution paths exist; governing prior decisions are the CSP
  vendored-init fork (2026-06-07, option (a) VENDORED-INIT) and the SHA-384
  pin discipline — both honoured here.

## Design decision — mirror-clone, not a second data path

The PiP window content is a **read-only mirror of the main window's live
section**, updated by cloning the freshly swapped `#live-section` node into
the PiP document on each `htmx:afterSwap`:

- **Single data path (R15 spirit)**: the main window remains the ONLY
  fetcher of `/fragments/live`. The PiP window runs no htmx, no fetch loop,
  no timers of its own — closing it cannot leak a poller, and the daemon
  sees no additional request load.
- **htmx untouched**: the live section node never leaves the main document
  (moving it into another document would detach htmx's processed-node state
  and kill the polling trigger — the known-fragile alternative).
- **Charts mirror as bitmaps**: cloned `<canvas>` nodes are blank by spec;
  after cloning, the script copies pixels from each main-window canvas via
  `drawImage` inside a `requestAnimationFrame` callback (runs after
  `dashboard-chart.js`'s same-event re-init because script load order =
  listener registration order; rAF tolerates Chart.js's async first paint).
  A mid-animation snapshot is acceptable — the next 3 s swap refreshes it.
- **Styles**: the PiP document `<head>` receives a copy of the main
  document's `<style>` element text at open time (Document PiP inherits the
  opener's CSP; inline `<style>` is already permitted). The PiP `<body>`
  gets a `pip-body` class so a narrow-window single-column override
  (`.pip-body .live-section{grid-template-columns:1fr}`) can live in
  `_LIVE_CSS` without affecting the main view. Both the override and the
  button styling go in `_LIVE_CSS`, NOT the shared `_CSS` — they can only
  ever activate from the live shell, and `_CSS` keeps its "rules consumed
  by both views" invariant (spec-review arch F2).
- **No string-HTML sink** (spec-review sec Q1 guard): the PiP document is
  populated EXCLUSIVELY via `cloneNode`/`importNode` + `replaceChildren`
  of nodes the main document already rendered through `_esc`. The script
  never calls `innerHTML =` or `insertAdjacentHTML` on any string — there
  is no payload-derived string-to-markup path anywhere in the file.

## Requirements

- **R1 — Pop-out affordance**: the live shell header (`shell-nav`) gains a
  `<button>` with a Python-side pinned id (constant in
  `src/telemetry/dashboard.py`, mirrored as a literal in the JS and anchored
  by regression tests — the existing three-location lockstep convention; the
  constant carries the same lockstep comment header as `_PER_TURN_COST_*`,
  arch F3). Server-rendered with the `hidden` attribute.
- **R2 — Honest absence**: a NEW first-party `/static/dashboard-pip.js`
  (IIFE, strict mode, no globals) reveals the button ONLY when
  `'documentPictureInPicture' in window`. On unsupported browsers the
  button stays hidden — no dead control, no error.
- **R3 — Open behavior**: clicking the button (user gesture, as the API
  requires) calls `documentPictureInPicture.requestWindow(...)` with a
  compact default size, copies styles, seeds the initial clone of
  `#live-section`, and flips the button into its "close" state (text +
  `aria-pressed`). If `requestWindow` rejects (e.g. `NotAllowedError` when
  another PiP window is already open), the button reverts and the failure is
  non-fatal (no uncaught rejection). The rejection handler logs a STATIC
  sentinel string only — never `e.message`. Visible feedback is a transient
  STATIC button label ("Pop-out unavailable right now", reverting after a
  few seconds; the button is `disabled` during the window so a rapid
  re-click cannot re-trigger a doomed request — REV ux F3) — never
  rejection-derived text (sec F2 + CP2 ux fold). SR announcement goes
  through a visually-hidden `role="status"` span next to the button, NOT
  `aria-live` on the button itself (double-announcement, REV ux F1 /
  WCAG 4.1.3). The PiP window gets `document.title = "Telemetry live"`
  (REV ux F2, multi-monitor anchor).
- **R4 — Mirror updates**: while the PiP window is open, each
  `htmx:afterSwap` targeting `#live-section` replaces the PiP container's
  content with a fresh clone + canvas bitmap copy. No independent polling.
  An `htmx:load` companion registration (same handler) is deliberate
  defensive symmetry with `dashboard-chart.js` — some htmx versions fire
  `htmx:load` for certain swap variants; the mirror is idempotent and
  null-gated, and both registrations are count-pinned by test (CP2 qa F1).
- **R5 — Lifecycle symmetry**: closing the PiP window (its `pagehide`) or
  clicking the toggle again tears down: close the window if open, drop the
  clone listener's active state, restore the button to "pop out". No
  listener accumulation across repeated open/close cycles. **The `pagehide`
  handler's FIRST synchronous action is nulling the module-scoped
  `pipWindow` reference, and the `htmx:afterSwap` mirror listener guards on
  `pipWindow` being non-null at the top of its body before any DOM access**
  — closing the close-during-swap race that would otherwise leave a stale
  handle and accumulate listeners (sec F1, BLOCKING fold). The mirror
  listener is registered ONCE at module init (always-on, gated by the null
  check), not re-registered per open — accumulation is impossible by
  construction.
- **R6 — Vendoring discipline**: `dashboard-pip.js` gets a README pin row
  (first-party, version, byte size, `sha384-...`) and a
  `_DASHBOARD_PIP_JS_SHA384_PIN` test mirroring the existing pin tests.
  `dashboard-chart.js` is NOT modified (its pin is untouched).
- **R7 — CSP invariant**: zero inline `<script>` anywhere; the CSP string
  is byte-identical before and after this unit.
- **R8 — Script wiring**: the shell loads `/static/dashboard-pip.js` with
  `defer`, ordered AFTER `dashboard-chart.js`. The listener-order dependency
  is documented in BOTH file headers (`dashboard-pip.js` points back at
  `dashboard-chart.js`'s afterSwap registration, and the shell's docstring
  notes the order is load-bearing — arch F1) and pinned by an order test.

## Constraints

- No server/route changes; `scripts/telemetry/dashboard_server.py` is
  untouched except — nothing. (StaticFiles already serves the directory.)
- Vanilla JS only — no new third-party assets.
- Known-broken approach to avoid: moving the live htmx element into the PiP
  document (breaks the polling trigger); independent fetch loop in the PiP
  window (second data path, leak-prone lifecycle) — rejected above.
- The PostToolUse auto-format hook strips imports unused at edit time —
  (re)add Python imports AFTER their consumers exist (sessions 22/23 gotcha).
- Regression-ledger entry must avoid literal pipe characters inside backticks
  (parser gotcha, sessions 18/19).

## Acceptance Criteria

- [ ] AC1: `render_live_shell_html` output contains the pop-out `<button>`
  with the pinned id, `hidden` attribute present, inside `shell-nav`
  (render test).
- [ ] AC2: the shell contains the EXACT tag
  `<script src="/static/dashboard-pip.js" defer></script>` (full-tag pin
  guards the `defer` attribute — qa F2) AND the index of the
  `dashboard-chart.js` tag is strictly less than the index of the
  `dashboard-pip.js` tag (order-pinning assertion mirroring
  tests/test_telemetry.py L4936+ — arch F1).
- [ ] AC3: `src/telemetry/static/dashboard-pip.js` exists, is non-empty,
  and STARTS WITH the exact IIFE opener form used by `dashboard-chart.js`
  (comment banner then `(function () {` + `"use strict"` — a
  starts-after-banner anchor, not a floating substring; qa F1), and
  contains the literal button id and `live-section` id (three-location
  lockstep anchor test).
- [ ] AC4: `_DASHBOARD_PIP_JS_SHA384_PIN` matches both the file bytes and
  the README pin-table row via the existing `_read_sha384_pin_from_readme`
  two-mirror cross-check (mirrors
  `test_vendored_dashboard_chart_sha384_matches_readme_pin` exactly — sec F3).
- [ ] AC5: the CSP header string is unchanged (existing exact-pin test still
  passes; no test edit).
- [ ] AC6: `dashboard-chart.js` bytes unchanged (existing pin test passes
  unmodified).
- [ ] AC7: the JS file contains the feature-detect guard
  (`documentPictureInPicture` literal) BEFORE any `requestWindow` call
  site, AND a `catch` (either `.catch(` or `} catch`) appears within the
  `requestWindow` call's enclosing statement region (qa F4) — static
  content assertions; behavioral fallback is browser-verified.
- [ ] AC8: `_LIVE_CSS` (not the shared `_CSS` — arch F2) contains the
  `.pip-body` single-column override and the button styling
  (render/content tests).
- [ ] AC9: regression-ledger entry added naming the known-broken pattern
  explicitly: listener accumulation on repeated PiP open/close in
  `src/telemetry/static/dashboard-pip.js` — the afterSwap mirror listener
  must be registered once at module init and gated by the null check, never
  re-registered per `openPip()`; verification = manual checklist in this
  spec's Verification Notes (browser-only) (qa F3). Quality gate 7/7.
- [ ] AC10: **declared test boundary** — pytest cannot execute browser JS;
  PiP open/mirror/close behavior and the unsupported-browser fallback are
  verified by (a) static content assertions above, (b) JS code review at
  checkpoints, and (c) the manual browser checklist PRE-SEEDED in
  Verification Notes below (qa AC10 gap — the checklist exists at spec
  time, not as a build-time placeholder). This boundary is stated in the
  test module docstring (transport-fidelity disclosure).
- [ ] AC11: static content assertions anchor the sec F1 guards — the JS
  contains the `pipWindow` null-assignment inside the `pagehide` handler
  body and a null-check guard at the top of the afterSwap mirror listener
  (sec F1, BLOCKING fold).
- [ ] AC12: `test_static_dashboard_pip_asset_is_served` — GET
  `/static/dashboard-pip.js` returns 200, the first-party banner, and a
  `javascript` MIME type, mirroring the existing three-assertion pattern
  (qa F5).

## Risk Assessment

- **Chromium-only API** → mitigated by feature-detect + hidden affordance
  (R2); the dashboard remains fully usable without PiP.
- **Listener leak across open/close cycles** → R5 + a single module-scoped
  active-state object; reviewed at checkpoint (cannot be pytest-verified).
- **Canvas bitmap copy races chart init** → rAF after the same-event
  listener chain; worst case is a one-cycle-stale or blank chart snapshot,
  refreshed ≤3 s later — degraded, never wrong data.
- **Supply-chain/pin drift** → AC4/AC6 make any byte change loud.
- **XSS surface unchanged**: the PiP document receives only cloned nodes
  that the main document already rendered through `_esc` — no new
  interpolation sink; no payload-origin string is used as a key or selector.

## Affected Components

- NEW `src/telemetry/static/dashboard-pip.js`
- `src/telemetry/dashboard.py` — shell button + script tag + pinned id
  constant + CSS additions
- `src/telemetry/static/README.md` — pin row
- `tests/test_dashboard_server.py` — pin test + wiring/order tests
- `tests/test_telemetry.py` — shell render tests (button, hidden attr, CSS)
- `memory/bugs/regression-ledger.md` — ledger entry

## Dependencies

- Depends on: Phase 1 live shell + Phase 2 chart init conventions (landed).
- Depended on by: nothing — Unit 5.1 (`--render-static`) is independent
  (static export has no live section; PiP code must not assume it runs
  outside the live shell — the JS bails when the button/section is absent).

## Verification Notes — manual browser checklist (AC10)

Run in Chromium ≥116 against a live daemon (`python
scripts/telemetry/dashboard_server.py`), plus one non-Chromium browser:

- [ ] Unsupported browser (Firefox/Safari): button never appears; no
  console errors; dashboard fully functional.
- [ ] Supported browser: button appears; click opens the PiP window with
  styled, current live content; charts show as bitmap snapshots.
- [ ] Mirror updates: PiP content refreshes within ~3 s of the main view;
  no duplicate `/fragments/live` requests in the Network tab (single data
  path preserved).
- [ ] Repeated open/close ×5: exactly one mirror update per swap after the
  final open (no listener accumulation — getEventListeners or visible
  double-flash check); button text/aria-pressed correct each cycle.
- [ ] Close during a swap cycle (rapid close right after a 3 s tick): no
  console error; reopen works cleanly (sec F1 race).
- [ ] Second `requestWindow` while a PiP is open (double-click race):
  rejection handled; static sentinel log only; button state consistent.
- [ ] htmx 500 honest-error fragment swapped in while PiP open: mirror
  shows the error fragment; verify no TypeError in the CONSOLE, not just
  no visual corruption (REV qa F3).
- [ ] Charts in loading/absent state (fresh DB): zero canvases — mirror
  no-ops without TypeError.
- [ ] MAIN window closed/navigated with PiP open: PiP window closes or
  inert-without-errors (opener-gone path; browser auto-closes Document PiP
  with its opener — verify no error spew first).
- [ ] `prefers-reduced-motion`: PiP mirror respects the main view's
  reduced-motion rendering (snapshots of non-animated charts).
- [ ] Screen reader (NVDA+Chrome): no double announcement on open/close
  label changes; the rejected-transient message announces exactly once via
  the `role="status"` span (REV ux F1).
