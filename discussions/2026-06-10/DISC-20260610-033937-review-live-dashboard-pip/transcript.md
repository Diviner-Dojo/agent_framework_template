---
discussion_id: DISC-20260610-033937-review-live-dashboard-pip
started: 2026-06-10T03:39:51.203209+00:00
ended: 2026-06-10T03:47:43.979653+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 11
---

# Discussion: DISC-20260610-033937-review-live-dashboard-pip

## Turn 1 — facilitator (evidence)
*2026-06-10T03:39:51.203209+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Full multi-agent review of Phase 4 Unit 4.4 — Picture-in-Picture pop-out for the live telemetry dashboard (SPEC-20260610-031224 complete; build DISC-20260610-032113 sealed with 2 checkpoints resolved). Standing developer directive 2026-06-09: Phases 3-5 autonomously, /review mandatory before commit.
- **Files/scope**: src/telemetry/static/dashboard-pip.js (NEW vendored first-party JS), src/telemetry/dashboard.py (shell button + script tag + _LIVE_CSS + _PIP_TOGGLE_BUTTON_ID), src/telemetry/static/README.md (pin row), tests/test_dashboard_server.py (pin/served/content-contract tests + module-docstring boundary), tests/test_telemetry.py (shell render tests), memory/bugs/regression-ledger.md (entry 47).
- **Developer-stated motivation**: ambient oversight — cost/runway/failure signals visible while the developer works in other windows.
- **Explicit constraints**: CSP byte-identical (exact-pin test untouched); no inline script; dashboard-chart.js bytes untouched; mirror-clone single-data-path design ratified at spec review; NO push.

---

## Turn 2 — qa-specialist (proposal)
*2026-06-10T03:42:53.383830+00:00 | confidence: 0.88*
*tags: review, qa*

VERDICT: APPROVE-WITH-CHANGES (0.88). 0 BLOCKING. qa F1 ADVISORY/MED (weak-assertion): served-test banner check ('dashboard-pip.js' in first 512 bytes) passes on a 404 body echoing the path — add r.text.startswith('/*!') content pin (defense-in-depth next to the SHA test). qa F2 ADVISORY/LOW: the rAF callback's inner null-guard is not independently anchored — add a count-based anchor (if (pipWindow === null) appears >= 2: mirror entry + rAF). qa F3 ADVISORY/LOW: annotate the 500-fragment checklist item 'verify no TypeError in console, not just no visual corruption'. qa F4 ADVISORY/LOW: PASSING CHECK documented — ledger row 47 parseable (6 cells, no literal pipes in backticks), known-broken pattern explicitly named, test refs correct. STRENGTHS: two-mirror pin; listener count-pins as static-level accumulation guards; full-tag defer pin; honest AC10 boundary + pre-seeded checklist; error-binding omission = security-by-construction.

---

## Turn 3 — architecture-consultant (proposal)
*2026-06-10T03:42:53.539388+00:00 | confidence: 0.92*
*tags: review, architecture*

VERDICT: APPROVE (0.92). 0 BLOCKING. All four CP1/spec arch decisions land verbatim (load-order pinned both ends + test; .pip-body in _LIVE_CSS with presence+absence test; lockstep comment header on the constant; mirror-clone single data path). Dependency direction correct (renderer owns constants; JS consumes; server untouched). Unit 5.1 forward-compat enforced by code (init() bails absent button/section). arch F1 ADVISORY/LOW: Rule-of-Three WATCHPOINT — 4th script tag, 3 order-coupled; do NOT fold yet; a 5th tag triggers a _LIVE_SHELL_SCRIPTS tuple with order-semantics docstring. arch F2 ADVISORY/LOW: if a second PiP constant ever lands server-side, add a section banner. STRENGTHS: three-channel redundancy on the load-order coupling; door-closing presence+absence CSS test; single-gate pipWindow state (one variable, three readers).

---

## Turn 4 — security-specialist (proposal)
*2026-06-10T03:43:21.256667+00:00 | confidence: 0.96*
*tags: review, security*

VERDICT: APPROVE (0.96). 0 BLOCKING. sec F1 (spec-review BLOCKING) RESOLVED + machine-anchored: pagehide nulls first (AC11 test), mirror entry guard, rAF re-check — close-during-rAF sub-race also closed. sec F2 ADVISORY/LOW confirmed NO-HAZARD: the 4s revert setTimeout is null-guarded — a PiP opened within the window correctly skips the revert. sec F3 INFO: pin test verified three-way (file bytes, test constant, README row) — intact, value matches. sec F4 verified clean by full read: no innerHTML/insertAdjacentHTML/document.write/eval; only textContent writes of static constants + className of a hardcoded constant; post-CP folds introduced no new sink; rejection error object discarded at the catch boundary (binding omitted). CSP inherited by the PiP context per Document PiP spec; no directive change needed. TRUST BOUNDARY: main-doc rendered DOM -> PiP via importNode/replaceChildren, sanitized upstream at _esc — no new raw-string path.

---

## Turn 5 — ux-evaluator (proposal)
*2026-06-10T03:43:21.392434+00:00 | confidence: 0.87*
*tags: review, ux*

VERDICT: APPROVE-WITH-CHANGES (0.87). 0 BLOCKING. ux F1 ADVISORY/MED (accessibility): aria-live=polite on the BUTTON double-announces every label change on NVDA+Chrome / VoiceOver (button name-change announcement + live region) — replace with a visually-hidden role=status span in the nav (WCAG 4.1.3 Status Messages pattern); button label still changes for sighted users; span carries the transient rejected message. ux F2 ADVISORY/LOW: PiP window title never set — win.document.title = 'Telemetry live' (one line) anchors the floating window for multi-monitor ambient oversight (Nielsen #6). ux F3 ADVISORY/LOW: during the 4s rejected transient the button is re-clickable (interaction trap for rapid re-clickers) — disable for the window, re-enable in the timeout. CHECKLIST: add an SR step (no double announcement on open/close). STRENGTHS: microcopy honest + blame-free, well-calibrated 4s; honest-absence textbook; mirror inherits the main view's loading/absence states (no blank rectangle); static REJECTED_LABEL = correct security+UX call; <200ms requestWindow gap needs no spinner.

---

## Turn 6 — facilitator (critique)
*2026-06-10T03:45:45.045942+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 11 verified, 2 inconclusive (arch F1 watchpoint + ux F1 SR-behavior claim — judgment/browser-dependent, retained), 0 discarded. Every file:line-specific claim checked against the working tree during fold application: qa F1 weak banner assertion existed as claimed (fixed); qa F2 rAF inner guard was unanchored (count anchor added); ux F1 aria-live=polite was on the button (replaced with role=status sr-only span + _PIP_STATUS_ID lockstep constant); ux F2 title unset (PIP_WINDOW_TITLE added); ux F3 re-click trap existed (disabled during the 4s transient, removeAttribute in the timeout); sec F1/F3/F4 confirmations matched the final bytes. SHA-384 re-pinned post-fold (12274 bytes, 1Xjx...). All 8 pip-scoped tests pass post-fold.

---

## Turn 7 — facilitator (synthesis)
*2026-06-10T03:46:02.368066+00:00 | confidence: 0.91*
*tags: blocking:0, advisory:11, speculative:0, model-tiers:all-default-medium*

## Request Context
- **What was requested**: Full multi-agent review of Phase 4 Unit 4.4 — Picture-in-Picture pop-out (SPEC-20260610-031224), per the standing 2026-06-09 autonomous Phases 3-5 directive (review mandatory before commit).
- **Files/scope**: src/telemetry/static/dashboard-pip.js (new), src/telemetry/dashboard.py, src/telemetry/static/README.md, tests/test_dashboard_server.py, tests/test_telemetry.py, memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: ambient oversight — signals visible while working in other windows.
- **Explicit constraints**: CSP byte-identical; no inline script; dashboard-chart.js untouched; mirror-clone single data path; NO push.

## Synthesis
4-specialist panel: qa 0.88 AWC + arch 0.92 APPROVE + sec 0.96 APPROVE + ux 0.87 AWC; weighted ~0.91. 0 BLOCKING. 6 FOLDED IN-SESSION: qa F1 (served-test startswith('/*!') content pin), qa F2 (count anchor pinning the rAF inner null-guard), qa F3 (checklist console-TypeError annotation), ux F1 MED (aria-live button -> visually-hidden role=status span, new _PIP_STATUS_ID three-location lockstep, WCAG 4.1.3; SR checklist step added), ux F2 (PIP_WINDOW_TITLE 'Telemetry live'), ux F3 (button disabled during the 4s rejected transient). 4 CONFIRMED NO-ACTION/INFO: sec F2 (setTimeout revert null-guard sound), sec F3 (three-way pin intact), qa F4 (ledger row parseable + actionable), arch F2 (section banner only if a 2nd PiP constant lands). 1 DEFERRED-AS-ADVISORY: arch F1 LOW Rule-of-Three WATCHPOINT — 4th script tag in the shell; a 5th triggers a _LIVE_SHELL_SCRIPTS tuple fold (do not fold now, Principle 8). sec F1 from the spec review verified RESOLVED + machine-anchored. SHA-384 re-pinned post-fold (12274 bytes). Confidence annotation: 0 speculative (<0.80), 0 unscored. Model tiers: qa-specialist:default, architecture-consultant:default, security-specialist:default, ux-evaluator:default (--cost medium).

---

## Turn 8 — qa-specialist (reflection)
*2026-06-10T03:47:43.500596+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Did not verify whether the test environment stubs requestAnimationFrame before rating the rAF-guard finding (could have shifted severity).
## Candidate Improvement Rule
Before classifying a DOM-timing assertion finding, confirm whether the test setup already provides the relevant global stub; if so, redirect toward assertion specificity.
## Confidence Calibration
Original: 0.88, Revised: 0.83, Delta: -0.05

---

## Turn 9 — architecture-consultant (reflection)
*2026-06-10T03:47:43.659636+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Did not trace whether the conditional-guard finding duplicated an upstream rendering decision (would elevate Low to Medium coupling); did not document the explicit act-threshold on the Rule-of-Three watchpoint (now recorded: a 5th script tag acts).
## Candidate Improvement Rule
Before rating a conditional guard Low, verify the guarded branch does not duplicate an upstream decision; always pin the numeric act-threshold on deferred watchpoints.
## Confidence Calibration
Original: 0.92, Revised: 0.87, Delta: -0.05

---

## Turn 10 — security-specialist (reflection)
*2026-06-10T03:47:43.813648+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
(FACILITATOR NOTE: this reflection references WebSocket reconnect logic that does NOT exist in this unit — the dashboard polls via htmx; the improvement rule is retained as generic guidance but the specific miss is a hallucinated surface and was verified non-applicable.) Did not explicitly record that the unit has no reconnect/fallback URL surface at all.
## Candidate Improvement Rule
For any live-dashboard transport, explicitly confirm reconnect/fallback URLs (if any) are compile-time constants or same-origin-validated — and record the absence of the surface when none exists.
## Confidence Calibration
Original: 0.96, Revised: 0.93, Delta: -0.03

---

## Turn 11 — ux-evaluator (reflection)
*2026-06-10T03:47:43.979653+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Flagged the rejected-transient re-click trap but did not trace the keyboard path as a discrete finding (focus remains on the trigger; Enter re-triggers). The disabled-during-transient fold incidentally closes the keyboard vector too.
## Candidate Improvement Rule
When flagging a re-trigger trap, trace pointer AND keyboard paths explicitly; an Escape-to-trigger in the same tab-stop chain warrants its own remediation step.
## Confidence Calibration
Original: 0.87, Revised: 0.82, Delta: -0.05

---
