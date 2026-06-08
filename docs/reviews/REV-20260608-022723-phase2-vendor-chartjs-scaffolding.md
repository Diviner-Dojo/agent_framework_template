---
review_id: REV-20260608-022723
discussion_id: DISC-20260608-022723-phase-2-vendor-chartjs-scaffolding
pr_id: ""
risk_level: low
collaboration_mode: ensemble
exploration_intensity: medium
agents_activated: [qa-specialist, security-specialist]
reviewed_files:
  - src/telemetry/static/chart.umd.min.js
  - src/telemetry/static/README.md
  - src/telemetry/static/LICENSE-chart.js.txt
  - tests/test_dashboard_server.py
  - memory/bugs/regression-ledger.md
rounds: 1
consensus_reached: true
verdict: approve
confidence: 0.92
review_duration_minutes: 15
---

## Summary

Phase 2 first-slice vendoring of Chart.js v4.4.7 (UMD build, 205,615 bytes) into
`src/telemetry/static/` with two-mirror integrity verification at vendoring
time, README pin-table update, MIT-license companion file, and three new
regression guards (one new for Chart.js + one new for the License companion +
two strengthened existing pairs for both htmx and Chart.js). Originated as a
**scaffolding-only** slice — the consuming `<script>` tag and chart markup
land in the next slice — which keeps the asset under integrity-pin discipline
from day one without shipping dead-weight browser load. Both specialists
returned APPROVE-WITH-CHANGES with 0 BLOCKING / 5 findings; 4 of the 5 cohere
as a single supply-chain hardening cohort and were folded in-session, leaving
the slice at consensus APPROVE.

## Request Context

- **What was requested**: Phase 2 first slice of the Layer B live dashboard (per SPEC-20260607-183136 Phase 2 in the existing Layer B dashboard daemon spec) — vendor Chart.js 4.4.7 into `src/telemetry/static/`, update the README pin table, and add static-mount + SHA-384 regression tests mirroring the existing htmx vendoring pattern.
- **Files/scope**: `src/telemetry/static/chart.umd.min.js` (NEW, 205,615 bytes); `src/telemetry/static/README.md` (modified); `src/telemetry/static/LICENSE-chart.js.txt` (NEW, in-session fold); `tests/test_dashboard_server.py` (modified — new constant + 3 new test functions + 2 strengthened existing tests); `memory/bugs/regression-ledger.md` (new fold-cohort row).
- **Developer-stated motivation**: Rolling supervisor handoff explicitly asks for Phase 2 (per-turn cost chart + weekly trends via vendored Chart.js per spec R11a — NO CDN, NO npm build). Vendoring-only slice scoped down by facilitator judgment to keep the unit small + verifiable in one supervised session while still being a real Phase 2 building block.
- **Explicit constraints**: NO CDN at runtime (R11a); NO npm/Node build step; pinned-version + SHA-384 discipline (mirror htmx vendoring); two-mirror integrity cross-check before publishing the pin; no production code logic change in this slice; supervised headless session — `/review` runs before any commit touching `src/`.

## Findings by Specialist

### QA Specialist

Confidence: **0.92** — Test contract is strictly equivalent to the htmx pattern. SHA-384 guard is sound. 0 BLOCKING.

- **F1 MED (FOLDED IN-SESSION)** — README pin string and the module-level `_CHARTJS_SHA384_PIN` constant are two independent sources of truth that can silently diverge. A re-vendor that updates one but not the other passes the existing SHA-guard (which only checks file→constant, not constant↔README) while leaving the human-readable and machine-enforced contracts inconsistent. **Fix:** new `_read_sha384_pin_from_readme(asset_filename)` helper parses the README pin-table row by matching the asset filename as inline code (`` ` ``-wrapped, so a paragraph mention cannot false-match) and extracts the `sha384-...` integrity cell; both SHA-384 regression tests now also assert `_*_SHA384_PIN == _read_sha384_pin_from_readme(...)`. Applied symmetrically to **both** htmx and Chart.js — the existing htmx test inherited the strengthening for free.
- **F2 LOW (FOLDED IN-SESSION)** — The served-tests assert HTTP 200 and a banner string but do NOT assert `Content-Type`. A StaticFiles misconfig serving the file as `text/plain` or `application/octet-stream` would pass the body check but browsers under strict MIME sniffing refuse to execute the script, breaking the next slice's `<script src="...">` load. **Fix:** added `assert "javascript" in r.headers.get("content-type", "").lower()` to **both** the new `test_static_chartjs_asset_is_served` and the existing `test_static_htmx_asset_is_served`. One-line per test, paired with a helpful failure message that echoes the actual content-type.
- **F3 LOW (NO ACTION — INFORMATIONAL)** — Specialist confirmed the file-absent case is adequately covered by `is_file()` in the SHA-384 guard + the `200` assert in the served-test acting together. Documented in the report for transparency.

### Security Specialist

Confidence: **0.91** — Supply-chain discipline is solid for a localhost developer tool. 0 BLOCKING / 2 LOW, both folded in-session.

- **F1 LOW (FOLDED IN-SESSION — OWASP A08:2021)** — Provenance gap: the MIT copyright header in the minified file's first comment block satisfies the legal minimum, but it is embedded in a 205-KB minified blob and is easy to overlook; a future re-minification pass that strips header comments would silently drop the notice. **Fix:** added `src/telemetry/static/LICENSE-chart.js.txt` containing the verbatim MIT License text from the upstream `v4.4.7` tag + a provenance footer pointing at the GitHub release tag and at the JS file it accompanies; new `@pytest.mark.regression test_chartjs_license_companion_file_present` asserts the file exists, carries the canonical MIT phrase `"Permission is hereby granted"`, names `"Chart.js Contributors"`, AND the README pin table references the companion via a relative link.
- **F2 LOW (FOLDED IN-SESSION — OWASP A08:2021)** — The README's two-mirror cross-check claim was epistemically over-stated. unpkg and jsDelivr share the npm registry as their common upstream, so a registry-level compromise (malicious publish of `chart.js@4.4.7`, or a registry substitution) would produce identical tampered bytes on **both** CDNs. The check is CDN-side consistency evidence, not independent upstream verification. **Fix:** rewrote the README "two-mirror cross-check" section to (a) state explicitly what the check does and does NOT prove, (b) name git history + the SHA-384 pin as the primary integrity anchors, (c) cite the upstream GitHub release tag (`https://github.com/chartjs/Chart.js/releases/tag/v4.4.7`) as the independent trust root with a different upstream from npm. The `_CHARTJS_SHA384_PIN` constant docstring carries the same clarification at the source.

### Strengths (cross-specialist)

- SHA-384 regression test makes integrity a CI gate, not a manual procedure — substantially better than most vendoring implementations.
- `script-src 'self'` CSP cleanly covers the future `<script src="/static/chart.umd.min.js">` without modification — same-origin scripts already permitted.
- Decision to NOT ship the `<script>` tag in this slice is correct security + QA posture — no pre-load attack surface, no dead-weight load, integrity-pin discipline still applies from day one.
- The banner-in-first-256-bytes assertion is a small improvement over the htmx pattern's "scan full text" check.
- Module-level constant has a substantive docstring explaining the two-mirror provenance and (after the fold) its corrected accuracy framing.

## Required Changes Before Merge

**None.** All 5 actionable findings were folded in-session (4 MED+LOW addressed; 1 LOW informational confirmed-as-covered). The 3 net-new + 2 strengthened existing regression guards interlock so a re-vendor that updates one source of truth without updating the others fails a different guard.

## Recommended Improvements (Non-Blocking)

**None remaining** beyond the in-session fold. The supply-chain discipline is consistent and machine-enforced; the next slice (script tag + per-turn cost chart consuming Chart.js) inherits all five guards.

## Speculative Findings — Lower Confidence

**None.** Both specialists scored ≥ 0.90.

## Discarded Findings

**None.** All findings verified against actual code.

## Developer Assessment (Counterfactual)

- Both specialists' folded findings would have plausibly slipped past a same-author re-read (the README/constant divergence in particular is an "obviously fine until it isn't" trap; the two-mirror over-statement is a worse-than-useless documentation accuracy issue precisely because it sounds authoritative).
- The MIT companion-file finding is the textbook value-add of an independent security review — easy to miss, easy to defer, but cheap to do correctly at vendoring time and expensive to retrofit later.

## Education Gate

- **Required**: no
- **Rationale**: Vendoring slice with zero production code logic change; the patterns (SHA-384 pinning, README pin tables, license companions) are already documented in the existing htmx vendoring discipline and have been quizzed previously. The interlock between the README/constant/license-companion guards is a small extension of an existing pattern, not a new concept.
- **Mastery tier**: N/A
- **If a walkthrough is desired later**: focus on `_read_sha384_pin_from_readme` — its inline-code-fence matcher rule is the load-bearing detail that prevents a paragraph mention of the filename from false-matching the row.

## Convergence Note

qa-specialist and security-specialist hit **orthogonal surfaces** rather than the same one. QA on test-contract correctness (assertion completeness + sources-of-truth divergence prevention); security on provenance completeness + documentation accuracy. The four folded findings cohere as a single supply-chain hardening cohort whose changes **interlock**: the LICENSE file is asserted by a test AND referenced from the README; the README pin is parsed by a helper that the SHA-384 guard uses; the SHA-384 guard asserts both file→constant and constant↔README — so a future change that updates one source of truth without the others fails a different guard than the one closest to the change. This is the load-bearing property a fold cohort should have, and it emerged from independent specialist analysis rather than a planned harmonisation.

## Phase-2 Burndown

This slice opens Phase 2 of the Layer B live dashboard. The REV-20260607-200447 advisory backlog (21 findings, opened with the Phase 1 ship) is **fully drained** (the arch F2 event-source seam, the last originating advisory, was completed by supervised session 3 and committed as `5bfd478`). The next Phase 2 unit is the per-turn cost chart itself — script tag in the live shell + chart markup in the live fragment + chart data shape baked as a JSON literal (per spec R11a). This vendoring slice is the substrate it builds on.
