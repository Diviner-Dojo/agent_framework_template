---
discussion_id: DISC-20260607-065118-telemetry-layer-b-dashboard-spec-review
started: 2026-06-07T06:51:30.369069+00:00
ended: 2026-06-07T06:59:01.120028+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 6
---

# Discussion: DISC-20260607-065118-telemetry-layer-b-dashboard-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-07T06:51:30.369069+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Run the Layer B /plan (full cycle) for the telemetry north-star dashboard: a static HTML infographic generated locally at read-time from metrics/evaluation.db + config, rendering the existing A1/A2/A3 honest Layer-A outputs (NOT new measurement). Form factor is already Steward-APPROVED (DISC-20260607-063709, 0.88) and must not be re-litigated.
- **Files/scope**: NEW scripts/telemetry/dashboard.py (thin render layer mirroring scripts/git_visualize.py / the /status precedent); tests in tests/test_telemetry.py; .gitignore + ADR-0020 + regression-ledger edits. Reuses analyze_cost/analyze_failures/analyze_value assembly functions. Spec: docs/sprints/SPEC-20260607-064958-telemetry-layer-b-dashboard.md.
- **Developer-stated motivation**: The whole point of the Telemetry & Oversight component is a powerful Layer B dashboard for understanding the developer's AI use; A1/A2/A3 were the data foundation, now complete. Developer is on a Claude Code subscription + individual account (local-only, no billing API).
- **Explicit constraints**: 5 Steward BLOCKING conditions the /plan + its /review must each demonstrate: (1) compute-don't-store inviolable (derive at render, persist nothing, reuse Layer-A, no parallel computation); (2) aggregates-only, no transcript free-text, ntfy topic slug NEVER printed incl. error paths; (3) no telemetry into any live agent prompt (render-only); (4) honest-absence as first-class visual states, visually distinct from a true zero (/review must specifically probe this — highest-risk axis for a visual surface); (5) no secrets in the artifact. Plus 2 Principle-#7 developer decisions, RESOLVED in this /plan: (6) output to OS temp dir like /status (never in repo); (7) feature scope = full A1+A2+A3 static, no standing process/live-refresh.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-07T06:54:56.057461+00:00 | confidence: 0.86*
*tags: architecture, boundary, blocking, compute-dont-store*

Verdict: APPROVE-WITH-CHANGES (0.86). Boundary discipline exemplary; thin render script over read-side Layer-A functions, mirrors /status, persists nothing, aligns ADR-0013/0020.
- BLOCKING 1 (coupling / fork-a-second-path): the named CLI orchestrators are NOT symmetric. analyze_value() RETURNS its result objects (consumable), but analyze_cost()/analyze_failures() WRITE to the DB, print, and return only an int summary dict. The dashboard must therefore consume the READ-SIDE functions only: load_cost_rows -> build_cost_report (A1); load_failure_signals -> rank_failures (A2); analyze_value(...) returned objects (A3). It must NEVER call analyze_cost()/analyze_failures() (they mutate DB -> violate R8/C1). Pin this in the spec; R5 fidelity test asserts equality vs the read-side functions with an identical load_pricing() table. A2 must mirror the CLI's post-run report = full stored corpus via load_failure_signals, not only freshly-detected.
- ADVISORY 2: read-only DB must TOLERATE missing telemetry tables (fresh clone / analyzers never run) -> map to the honest-absence state via try/except sqlite3.OperationalError; do NOT call init_db() from the dashboard (it writes). Makes R8 and R3 consistent.
- ADVISORY 3: name the INTENTIONAL divergence from /status: git_visualize.py interpolates raw into innerHTML (safe for git data); the dashboard renders server-side and html.escapes (C6). Mirror the precedent for STRUCTURE only (gather -> one HTML string -> temp write -> webbrowser.open -> --no-open).
- INFO 4: pre-existing Task-vs-Agent doc drift in CLAUDE.md vs ADR-0020; no action here.

---

## Turn 3 — security-specialist (critique)
*2026-06-07T06:55:08.815844+00:00 | confidence: 0.91*
*tags: security, xss, escaping, no-slug, blocking*

Verdict: APPROVE-WITH-CHANGES (0.91). Five Steward conditions map onto the right attack surfaces; _otel_estimate hardening + notify.py slug protection are solid precedents. Confirmed by construction: the slug lives only in .env -> os.environ -> notify.py memory; it is NEVER written to evaluation.db, config/, or data/, so the dashboard input set is provably slug-free.
- BLOCKING 1 (A03 Injection / stored XSS): do NOT copy git_visualize.py's innerHTML / JS-string-concat pattern for Layer-A strings. That is safe there (git plumbing output) but FailureSignal.signature/.detail and dispatch.subagent_type are transcript-shaped. Discipline: html.escape() in PYTHON on every string field before interpolation; render values as textContent not innerHTML. Escape FailureSignal.signature/detail/failure_type/tier, DivergenceResult.reason/source_label, IndependentEstimate.source_label, LeverageResult.reason/note. Injection test must target the transcript  field feeding FailureSignal.signature (retry-loop signature = tool_name:hash), not only .detail. Numbers need no escaping.
- ADVISORY 2 (Low, accepted): predictable temp path (%TEMP%/telemetry_dashboard.html) -> local-only TOCTOU; matches /status precedent + OS ACLs/FDE mitigate; .gitignore defensive entry proportionate.
- ADVISORY 3: no-slug test = behavioral: inject a known fake NTFY_TOPIC, force an error path (unreadable db_path), capture stdout+stderr, assert the fake slug value is absent. Confirm the generator never imports/calls notify.py.
- ADVISORY 4: subscription.yaml plan_label/effective_date are user-controlled strings -> escape uniformly with C6 (self-XSS, zero blast radius, but keep escaping uniform).

---

## Turn 4 — qa-specialist (critique)
*2026-06-07T06:55:26.947243+00:00 | confidence: 0.87*
*tags: qa, testability, transport-fidelity, honest-absence, blocking*

Verdict: APPROVE-WITH-CHANGES (0.87). Existing env fixture (tmp_path DB, monkeypatched roots) + _table_row_counts helper are directly reusable; honest-absence type system is well-shaped for testing.
- BLOCKING 1 (R5 transport-fidelity under-specified, would allow a no-op test): (a) require a PURE assemble_dashboard_data(db_path, pricing, subscription_path, otel_path) -> DashboardData that returns the assembled dataclasses with NO HTML and NO I/O writes; (b) a test compares it field-by-field against build_cost_report / rank_failures / analyze_value on the same fixture: CostReport.total_cost_usd, coverage_pct, is_fully_covered, every by_tier TierCost.cost_usd; LeverageResult.configured/leverage_cumulative/leverage_per_month; both DivergenceResult.available/divergence_pct/direction. This also gives escaping + ASCII tests a clean input without brittle HTML parsing.
- BLOCKING 2 (C4 honest-absence): require ONE test per absence state (fee-not-configured; OTel-not-yet-active; --since-skipped attribution; analyzer-not-yet-run; unknown-tier remainder), each asserting a distinct non-numeric marker (named CSS class / data-attribute / literal token), never a numeric 0.
- ADVISORY 3: parametrize the escaping test over ALL string fields (add DivergenceResult.reason + source_label), not just failure detail/signature.
- ADVISORY 4: drop the weak grep-guard option; no-slug test must be behavioral (pattern: test_collab_loop TestHttpGetNeverPrintsTopic).
- ADVISORY 5: no-persistence test stronger than row-count: schema-unchanged check (sqlite_master) + open DB via file:...?mode=ro URI (read-only enforced at runtime).
- ADVISORY 6: ASCII-summary test parametrized across states (present / fee-not-configured / no-failures) — prior 3x cp1252 em-dash class.
- ADVISORY 7: clarify the signal distinguishing analyzer-not-yet-run (no watermark row) from true-zero-failures (watermark present, 0 rows); test each renders a distinct state.

---

## Turn 5 — ux-evaluator (critique)
*2026-06-07T06:55:41.693052+00:00 | confidence: 0.88*
*tags: ux, honest-absence, emotional-design, plain-language, blocking*

Verdict: APPROVE-WITH-CHANGES (0.88). Typed-absence data model is excellent; the gap is the PRESENTATION-layer requirements, which is exactly what spec review should catch before build. The right copy already exists in the A3 CLI (_print_leverage / _print_divergence) and just needs to be REQUIRED in the spec.
- BLOCKING 1 (C4, WCAG 1.4.1): R3 does not define what visually-distinct MEANS, so the build could satisfy the letter with a grey n/a box that still reads as nothing-here-probably-fine. Add R3a Absence-state visual+copy spec: (1) absence tiles use a distinct container (dashed border / muted bg) NOT used by data tiles; distinction conveyed by shape/border/icon, not color alone; (2) each absence tile carries a plain-language sentence: What-is-absent. Why. Action-if-any; (3) true-zero (analyzer ran, found nothing) uses the NORMAL data tile + copy (No failure signals detected), NOT the absence style; (4) analyzer-not-yet-run is a distinct absence tile (No data yet. Run scripts/telemetry/analyze_failures.py); (5) reviewability gate: PR/build close must include a screenshot showing each absence state from a fixture run (C4 not auto-testable on sight).
- BLOCKING 2 (emotional design / plain-language for the manager-gatekeeper): decontextualized dollar/multiple figures mislead. Require: A1 legend verbatim-or-equivalent (These figures show what the same tokens would cost at API pay-per-use prices - not what you paid on your subscription); A3 primary label 'List-price-equivalent multiple' (NOT 'leverage'/'value'); a one-line legend explaining the multiple; acceptance criterion: panel understandable without knowing 'coverage pct' / 'list-price-equivalent'.
- ADVISORY 1: OTel affordance must be a live <a> hyperlink (new tab), not plain text.
- ADVISORY 2: A2 panel leads with a one-line status (N signals detected / No failure signals detected - all good) before the detail table.
- ADVISORY 3: define the 5-6 console summary lines (path; cost+coverage; failures; multiple; OTel status; optional advisory) - no figures needing explanation.
- FLOW: add a named test - empty DB renders every panel in its absence state, not a blank page (first-run).

---

## Turn 6 — facilitator (synthesis)
*2026-06-07T06:59:01.120028+00:00 | confidence: 0.88*

## Request Context
- **What was requested**: Layer B /plan for the telemetry north-star dashboard - a static HTML infographic generated locally at read-time from evaluation.db + config, rendering the existing A1/A2/A3 honest Layer-A outputs (NOT new measurement). Form factor Steward-APPROVED (DISC-20260607-063709, 0.88), not re-litigated.
- **Files/scope**: SPEC-20260607-064958; NEW scripts/telemetry/dashboard.py + a pure src/telemetry/ assembly/format module; tests in tests/test_telemetry.py; .gitignore + ADR-0020 + regression-ledger edits.
- **Developer-stated motivation**: the dashboard is the whole point of the Telemetry component; A1/A2/A3 were the data foundation, now complete. Local-only data (subscription + individual account).
- **Explicit constraints**: 5 Steward BLOCKING conditions + 2 Principle-#7 developer decisions (resolved: temp-dir output like /status; full A1+A2+A3 static scope).

## Synthesis
Panel: architecture-consultant 0.86, security-specialist 0.91, qa-specialist 0.87, ux-evaluator 0.88 - ALL APPROVE-WITH-CHANGES. 5 BLOCKING findings, all FOLDED into the spec; 0 unresolved blocking.

BLOCKING folded:
1. (arch) Dashboard must consume READ-SIDE functions only (load_cost_rows->build_cost_report, load_failure_signals->rank_failures, analyze_value returned objects); NEVER analyze_cost()/analyze_failures() (they mutate DB/print/return only int summaries) -> R7 rewritten; new read-side-only acceptance test.
2. (security) No copying git_visualize.py innerHTML/raw-concat; html.escape in Python + textContent, enumerated fields, injection test targets the tool-name feeding FailureSignal.signature -> C6 rewritten.
3. (qa) R5 was a no-op risk -> added R5a: pure assemble_dashboard_data(...)->DashboardData seam (no HTML/IO) + field-level fidelity test enumerating exact fields.
4. (qa+ux) Honest-absence under-tested/under-specified -> R3a absence visual+copy spec (distinct container not color-alone/WCAG 1.4.1; plain-language sentence; true-zero uses data tile; not-yet-run distinct; OTel = live <a>; screenshot reviewability gate) + one-test-per-state + true-zero-vs-not-run + empty-DB first-run criteria.
5. (ux) Emotional design / plain-language for the manager-gatekeeper -> R2a: A1 pay-per-use legend; A3 label 'List-price-equivalent multiple' + legend; understandable-without-jargon criterion.

Advisories folded: read-only tolerates missing tables -> not-yet-run absence, no init_db() (R8, ?mode=ro URI); no-slug behavioral test (drop grep-guard); subscription plan_label/effective_date escaped; ASCII summary parametrized across states; defined the 5-6 console summary lines; A2 headline status before detail table; strong no-persistence (schema + row counts). Security confirmed the slug is provably absent from all dashboard inputs by construction; temp-path TOCTOU accepted (Low, matches precedent). Spec status -> reviewed.

---
