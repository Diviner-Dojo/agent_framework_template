---
discussion_id: DISC-20260610-032113-build-live-dashboard-pip
started: 2026-06-10T03:21:30.978294+00:00
ended: 2026-06-10T03:38:40.563265+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 9
---

# Discussion: DISC-20260610-032113-build-live-dashboard-pip

## Turn 1 — facilitator (evidence)
*2026-06-10T03:21:30.978294+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Implement SPEC-20260610-031224 — Phase 4 Unit 4.4 Picture-in-Picture pop-out for the live telemetry dashboard (Document PiP API; mirror-clone design; vendored vanilla JS; own SHA-384 pin; hidden-affordance fallback). Standing developer directive 2026-06-09: Phases 3-5 autonomously, one unit per supervised session.
- **Files/scope**: NEW src/telemetry/static/dashboard-pip.js; src/telemetry/dashboard.py (button + script tag + pinned id constant + _LIVE_CSS); src/telemetry/static/README.md pin row; tests/test_dashboard_server.py + tests/test_telemetry.py; memory/bugs/regression-ledger.md.
- **Developer-stated motivation**: ambient oversight — cost/runway/failure signals visible while working in other windows.
- **Explicit constraints**: CSP byte-identical (exact-pin test); no inline script; cloneNode/importNode + replaceChildren only (never innerHTML on strings); dashboard-chart.js bytes untouched; pagehide nulls pipWindow first + afterSwap listener null-guards (sec F1); mirror listener registered ONCE at module init; static sentinel error log only; NO push.

---

## Turn 2 — facilitator (proposal)
*2026-06-10T03:21:31.095864+00:00 | confidence: 0.8*
*tags: build-plan*

Build plan: T1 NEW src/telemetry/static/dashboard-pip.js (IIFE: feature-detect reveal, requestWindow open/teardown, once-registered null-guarded afterSwap mirror, canvas bitmap copy in rAF, style copy, pip-body class). T2 src/telemetry/dashboard.py (lockstep _PIP_TOGGLE_BUTTON_ID constant + hidden button in shell-nav + script tag after dashboard-chart.js + _LIVE_CSS additions). T3 SHA-384 pin (README row + bytes). T4 tests (AC1-AC8, AC11, AC12 static/render/pin/MIME assertions + transport-fidelity docstring). T5 regression-ledger entry naming the listener-accumulation known-broken pattern. Checkpoints: CP1 after T1 (security + architecture — security-relevant JS, new static module); CP2 after T2 (ux + qa — render seam + affordance).

---

## Turn 3 — security-specialist (critique)
*2026-06-10T03:25:03.461611+00:00 | confidence: 0.97*
*tags: checkpoint, task-1*

CP1 T1 (dashboard-pip.js): APPROVE (0.97). All three sec F1 guards VERIFIED: pagehide nulls pipWindow as literal first statement; mirrorLiveSection null-guards at entry + the rAF callback carries its own independent null-check; mirror listener registered once at IIFE scope, never in openPip. String-to-markup sink audit CLEAN (no innerHTML/insertAdjacentHTML/document.write/eval; DOM population only via importNode+replaceChildren and createElement+textContent). Error-path audit CLEAN — rejection handler omits the error binding entirely (function() not function(e)) so e.message logging is structurally impossible; drawErr never referenced in the log. 1 LOW advisory: add a one-line defensive comment at the copy.textContent assignment site ('textContent, not innerHTML — text node write, not markup parsing') as proximity lint-bait for future authors. FOLDED in-build.

---

## Turn 4 — architecture-consultant (critique)
*2026-06-10T03:25:03.567941+00:00 | confidence: 0.93*
*tags: checkpoint, task-1*

CP1 T1 (dashboard-pip.js): APPROVE (0.93). Faithful to the ratified mirror-clone design; single data path; once-registered null-gated listener makes accumulation impossible by construction. Called out pipWindow.requestAnimationFrame (not window.rAF) as the most load-bearing detail in the file and CORRECT — a backgrounded main tab suspends its own rAF queue while the PiP window is always visible. Convention adherence to dashboard-chart.js exact (IIFE, var-style, handleHtmxAfterSwap filter form from the REV-20260608-042729 security F2 fold, dual afterSwap+load registration, readyState init guard). importNode over cloneNode+adopt correct (atomic adoption). Unit 5.1 bail in init() after feature-detect — right place. 1 LOW = confirmation only (pagehide ordering correct); 1 INFO = AC4 pin is a Task 3 deliverable, sequence explicitly.

---

## Turn 5 — ux-evaluator (critique)
*2026-06-10T03:32:39.669806+00:00 | confidence: 0.88*
*tags: checkpoint, task-2*

CP2 T2 (shell wiring): APPROVE (0.88). Labels plain-language correct; aria-pressed the right toggle pattern (real button = keyboard free; no focus management needed — PiP is an OS window, not a modal); pressed-state dual-channel OK (color + border change, WCAG 1.4.1); honest-absence reveal called the highest-value emotional-design decision in the unit. 1 LOW (missing-feedback, Nielsen #1): requestWindow rejection currently reverts the button SILENTLY — for a manager-gatekeeper one click with zero response reads as a broken control; console.warn is invisible to them. Remediation: transient static label on the button (+aria-live) reverting after a few seconds; purely additive to the catch block, does not touch the sentinel logic. FOLDED in-build.

---

## Turn 6 — qa-specialist (critique)
*2026-06-10T03:32:39.778025+00:00 | confidence: 0.88*
*tags: checkpoint, task-2*

CP2 T2+T4 (tests): REVISE (0.88). 10/12 ACs directly covered, AC5/AC6 correctly inherited, AC10 boundary properly scoped, AC11 first-statement extraction sound (comment-tolerant), AC7 ordering behaviorally meaningful, AC4 two-mirror right, AC8 positive+negative complete. F1 MED: the htmx:load registration in dashboard-pip.js is in NO spec requirement and NO test — either pin it (count==1 + comment) and acknowledge in spec terms, or remove it; silent unspecified registration is an invisible regression surface. F2 LOW: the use-strict anchor at split-index [1] breaks on a blank-line insertion with no contract violation; pin the opener+use-strict as one startswith unit instead. RESOLUTION: htmx:load is INTENTIONAL (defensive symmetry with dashboard-chart.js dual registration; mirror is null-gated + idempotent) — pinned by count assertion + comment; F2 fixed via startswith pin; ux LOW rejection-feedback folded in same pass.

---

## Turn 7 — qa-specialist (critique)
*2026-06-10T03:34:54.128967+00:00 | confidence: 0.96*
*tags: checkpoint, task-2, round-2*

CP2 ROUND 2: APPROVE (0.96). All three fold targets verified: F1 count-pin + rationale comment in both test and JS registration site + SPEC R4 acknowledgement; F2 startswith opener+pragma unit pin; ux fold (REJECTED_LABEL 4s null-gated revert + aria-live on the server-rendered button) present with AC1 assertion in play. SHA-384 re-pinned in lockstep (11281 bytes). No weak assertions or unanchored claims remain.

---

## Turn 8 — facilitator (synthesis)
*2026-06-10T03:38:10.951953+00:00 | confidence: 0.8*
*tags: build-summary, blocking:0, advisory:7*

Build complete: 5 tasks (T1 dashboard-pip.js, T2 shell wiring, T3 SHA-384 pin, T4 tests, T5 ledger entry), 2 checkpoints fired (CP1 sec 0.97 + arch 0.93 APPROVE — 1 LOW comment fold; CP2 ux 0.88 APPROVE + qa 0.88 REVISE round 1 -> 0.96 APPROVE round 2 — folds: htmx:load count-pin + spec R4 acknowledgement, startswith opener+pragma unit pin, transient REJECTED_LABEL rejection feedback + aria-live on the button), 0 unresolved concerns. Self-caught during build: snapshot rAF moved from the MAIN window to the PiP window (a backgrounded main tab suspends its rAF queue — and a backgrounded tab is the primary PiP use case). SHA-384 re-pinned in lockstep after folds (11281 bytes). Quality gate 7/7 (regression ledger 47 guards). Pre-existing UP038 lint at test_telemetry.py:4695 fixed in passing (int | float).

---

## Turn 9 — qa-specialist (reflection)
*2026-06-10T03:38:40.563265+00:00 | confidence: 0.92*
*tags: reflection*

## What I Missed
Flagged htmx:load registration + use-strict split-index anchor against a generic DOM-ready mental model rather than htmx's documented lifecycle; the registration was a deliberate library-contract pattern (defensive symmetry with dashboard-chart.js), not a defect.
## Candidate Improvement Rule
Before flagging event-registration ordering as a defect, verify the event's documented firing contract for the specific library in use.
## Confidence Calibration
Delta: -0.04 (Round 2 0.96 appropriate; Round 1 would have been better calibrated at 0.78)

---
