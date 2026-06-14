---
discussion_id: DISC-20260610-031327-live-dashboard-pip-spec-review
started: 2026-06-10T03:13:40.107987+00:00
ended: 2026-06-10T03:20:24.095096+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260610-031327-live-dashboard-pip-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-10T03:13:40.107987+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 4 Unit 4.4 of the Layer B live dashboard — pop the live view into a floating always-on-top window via the Document Picture-in-Picture API; vanilla JS vendored under script-src 'self' (NO inline script; a new static file gets its own SHA-384 pin row + pin test); graceful fallback when the API is absent (honest-absence: hidden affordance, not a broken button). Standing developer directive 2026-06-09: run Phases 3-5 to completion autonomously, one bounded unit per supervised session.
- **Files/scope**: NEW src/telemetry/static/dashboard-pip.js; src/telemetry/dashboard.py (shell button + script tag + pinned id + CSS); src/telemetry/static/README.md pin row; tests/test_dashboard_server.py + tests/test_telemetry.py; regression ledger. Spec: SPEC-20260610-031224.
- **Developer-stated motivation**: ambient oversight — the dashboard only delivers value if cost/runway/failure signals stay visible while the developer works in other windows.
- **Explicit constraints**: CSP string must not change (pinned by test); no inline script; no CDN; dashboard-chart.js bytes untouched (pin preserved); no server/route changes; NO push.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-10T03:16:37.049004+00:00 | confidence: 0.86*
*tags: spec-review, architecture*

VERDICT: APPROVE-WITH-CHANGES (0.86). Mirror-clone design is the correct boundary and respects R15 (PiP is a projection, not a parallel renderer); rejection rationale for node-move + independent-fetch alternatives technically correct. FINDINGS: arch F1 ADVISORY/MED (coupling) — AC2 must require a pinned-order render assertion (chart_init_idx < pip_idx) mirroring tests/test_telemetry.py:4942-4946, plus a header comment in dashboard-pip.js pointing back at the order dependency so the contract is reachable from both ends. arch F2 ADVISORY/LOW (pattern) — .pip-body override + button styling belong in _LIVE_CSS, NOT shared _CSS (retrospective render never activates them; _CSS invariant = rules that apply to both views); update AC8 to say _LIVE_CSS explicitly. arch F3 ADVISORY/LOW (drift) — new pinned button id constant carries the same three-location-lockstep comment header convention as _PER_TURN_COST_* (dashboard.py:1464-1476). arch F4 INFO — Unit 5.1 forward-compat already correctly handled by bail-when-absent. STRENGTHS: CSP fork honoured; vendoring discipline identical to dashboard-chart.js; AC10 transport-fidelity disclosure is the right operational honesty.

---

## Turn 3 — security-specialist (critique)
*2026-06-10T03:16:50.950236+00:00 | confidence: 0.88*
*tags: spec-review, security*

VERDICT: APPROVE-WITH-CHANGES (0.88). FINDINGS: sec F1 BLOCKING/HIGH (A03 stale-window reference) — spec must require the PiP pagehide handler to null the pipWindow reference SYNCHRONOUSLY as its first action, and the htmx:afterSwap mirror listener to guard on pipWindow !== null at entry; without both, a close-during-swap race leaves a non-null handle and repeated open/close cycles accumulate listeners (contradicts R5). Add as explicit AC with static content assertions (grep for the null-assignment + the guard). sec F2 ADVISORY/MED (A05 error-text leakage pattern) — requestWindow rejection handler must log a STATIC sentinel string only, never e.message; no error copy reaches visible UI; add one-line spec note in R3. sec F3 ADVISORY/LOW (A08) — pin discipline correctly specified; confirm build uses _read_sha384_pin_from_readme two-mirror cross-check identically to the chart pin test. DIRECTED ANSWERS: PiP window inherits opener CSP by spec (same-origin auxiliary context) — style-src inline already permitted; mirror-clone via cloneNode/importNode + replaceChildren introduces NO new interpolation sink PROVIDED no innerHTML/insertAdjacentHTML path on payload-derived strings is introduced — anchor that as an explicit constraint. NO CSP directive change needed (no new fetch/frame/plugin surface); byte-identical CSP is the correct call. Leaving dashboard-chart.js untouched is right (avoids coordinated pin churn). TRUST BOUNDARIES: main doc -> PiP via importNode SAFE; rejection path -> console SAFE if static string; pipWindow handle post-pagehide is the live gap (F1).

---

## Turn 4 — qa-specialist (critique)
*2026-06-10T03:17:06.756284+00:00 | confidence: 0.88*
*tags: spec-review, qa*

VERDICT: APPROVE-WITH-CHANGES (0.88). FINDINGS: qa F1 BLOCKING/MED (weak-assertion) — AC3's 'parses as an IIFE' substring checks are theater (pytest cannot parse JS); reword to 'starts with the exact IIFE opener form mirroring dashboard-chart.js' and keep the lockstep id anchors (the valuable part). qa F2 BLOCKING/MED (weak-assertion) — AC2 must pin the EXACT full tag form '<script src="/static/dashboard-pip.js" defer></script>' (guards the defer attribute, which the listener-order guarantee depends on) AND then the chart_idx < pip_idx order comparison, mirroring test_telemetry.py L4936+. qa F3 BLOCKING/HIGH (missing-regression) — the regression-ledger entry must NAME the known-broken pattern: listener accumulation on repeated PiP open/close (each open must reuse/remove the prior afterSwap listener), file dashboard-pip.js, verification = manual checklist in the spec Verification Notes (browser-only) — so the known-broken approach is machine-findable even without a pytest guard. qa F4 ADVISORY/LOW — add static assertion that a catch wraps the requestWindow call site; name the 'second requestWindow while one is open (NotAllowedError)' scenario in the manual checklist. qa F5 ADVISORY/LOW — add test_static_dashboard_pip_asset_is_served (status 200 + banner + MIME 'javascript' in content-type) mirroring L707-723. AC10 BOUNDARY: honestly drawn, genuine improvement over smoke-test-fidelity antipattern; gap = checklist is a placeholder — pre-seed it at spec time with the 4 missed edge cases: (1) listener accumulation cycles, (2) PiP open while htmx 500 honest-error fragment swaps in (afterSwap fires with non-data node; mirror must tolerate missing canvases), (3) zero-canvas loading/absent state (drawImage loop must no-op, not TypeError), (4) MAIN window pagehide with PiP open (opener DOM refs invalid; R5 only covers PiP-side pagehide).

---

## Turn 5 — facilitator (synthesis)
*2026-06-10T03:20:24.095096+00:00 | confidence: 0.9*

## Request Context
- **What was requested**: Phase 4 Unit 4.4 — Picture-in-Picture pop-out for the Layer B live telemetry dashboard via the Document PiP API; vendored vanilla JS under script-src 'self'; own SHA-384 pin; graceful hidden-affordance fallback. Standing 2026-06-09 developer directive: Phases 3-5 autonomously, one unit per session.
- **Files/scope**: SPEC-20260610-031224 (NEW dashboard-pip.js; dashboard.py shell button + script tag + pinned id + _LIVE_CSS; README pin row; tests; ledger).
- **Developer-stated motivation**: ambient oversight — signals visible while working in other windows.
- **Explicit constraints**: CSP byte-identical; no inline script; dashboard-chart.js untouched; no server changes; NO push.

## Synthesis
3-specialist panel: arch 0.86 AWC + sec 0.88 AWC + qa 0.88 AWC. Design RATIFIED: mirror-clone (main window sole fetcher; PiP = cloned DOM + canvas bitmap copy per htmx:afterSwap) over node-move (kills htmx polling) and independent-fetch (second data path, leak-prone) — all three specialists endorsed the boundary. 4 BLOCKING folded into the spec: sec F1 (pagehide nulls pipWindow synchronously FIRST + afterSwap listener null-guards at entry; listener registered ONCE at module init — new AC11 static assertions); qa F1 (AC3 IIFE substring theater -> exact opener-form anchor); qa F2 (AC2 pins full '<script src defer>' tag form + chart_idx < pip_idx order, converges with arch F1); qa F3 (ledger entry must NAME the listener-accumulation known-broken pattern). 7 advisories folded: arch F2 (CSS into _LIVE_CSS not shared _CSS, AC8), arch F3 (lockstep comment header on the new constant, R1), sec F2 (static sentinel log, never e.message, R3), sec F3 (AC4 names _read_sha384_pin_from_readme), sec Q1 guard (no innerHTML/insertAdjacentHTML anywhere — cloneNode/importNode + replaceChildren only, Design section), qa F4 (catch-near-requestWindow static assertion, AC7), qa F5 (MIME-type served test, new AC12). AC10 checklist PRE-SEEDED with 10 browser scenarios incl. the 4 qa edge cases (500-fragment swap, zero-canvas, main-window pagehide, open/close cycles). arch F4 INFO confirmed no-action (Unit 5.1 independence via bail-when-absent). Spec status -> reviewed; 12 ACs. No CSP change; dashboard-chart.js pin untouched.

---
