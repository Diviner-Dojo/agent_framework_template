---
discussion_id: DISC-20260606-211551-telemetry-value-crosscheck-a3-spec-review
started: 2026-06-06T21:16:03.643309+00:00
ended: 2026-06-06T21:22:56.003739+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260606-211551-telemetry-value-crosscheck-a3-spec-review

## Turn 1 — facilitator (evidence)
*2026-06-06T21:16:03.643309+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Plan telemetry Layer A3 — two local, credential-free honesty metrics (value-vs-subscription leverage + estimate cross-check) that feed the north-star Layer B dashboard. Full workflow: /plan -> Steward note -> /build_module -> /review -> commit. NO push.
- **Files/scope**: docs/sprints/SPEC-20260606-211429-telemetry-value-crosscheck-a3.md; reuses A1 (src/telemetry/{pricing,cost}.py, scripts/telemetry/analyze_cost.py, config/model_pricing.yaml); new src/telemetry/value.py + scripts/telemetry/analyze_value.py + config/subscription.yaml. Scope is A3 metrics ONLY.
- **Developer-stated motivation**: Understand-your-AI-use. Developer is on a Claude Code SUBSCRIPTION + INDIVIDUAL account, so programmatic Cost/Usage/Analytics APIs are unavailable (Admin key + real org). 'Cost API' decision SUPERSEDED. A3 reframed to local value + cross-check; direction confirmed 2026-06-06, do not re-litigate.
- **Explicit constraints**: Compute-don't-store inviolable (ADR-0013): persist token INPUTS + sub fee as config input, derive ratios/dollars/divergence at READ. No credential / no billing API / no Admin key. No telemetry into live agent prompts (Steward #3). Reuse A1, don't fork a second cost computation. Scope A3 ONLY — A-PERF2/A-ARCH1/A1.1 and Layer B/C explicitly out. Needs its own Steward note. NO push.

---

## Turn 2 — architecture-consultant (critique)
*2026-06-06T21:19:18.774291+00:00 | confidence: 0.84*
*tags: spec-review, architecture, approve-with-changes*

## Verdict: APPROVE-WITH-CHANGES (confidence 0.84)
Spec respects A1's pure/transport split; CostReport reuse seam is real; metric-1-needs-no-table is sound for compute-don't-store. Two structural items to tighten + two minor.

**F1 (Medium, coupling/drift) — 'reuse CostReport, don't fork' is asserted, not structurally enforced.** Make the pure leverage fn take a CostReport PARAMETER (e.g. leverage(report: CostReport, fee: SubscriptionFee|None) -> LeverageResult) so forking the cost math is signature-impossible. analyze_value.py must obtain its CostReport by importing load_cost_rows + build_cost_report from analyze_cost.py, NOT re-querying discussion_model_tokens. The R-A3.4 attribution baseline must share the SAME pricing path (PricingTable.cost_usd) and differ ONLY in aggregation/attribution — else a divergence conflates attribution flaw with a 2nd pricing impl. (ADR-0020 Alternative-5: no parallel cost store/computation.)

**F2 (Medium, premature-abstraction risk) — pin the R-A3.4 source-agnostic seam to a concrete shape NOW.** Two real callers (attribution baseline live + OTel honest-absence) clear Rule-of-Three's spirit IF both wired. Define an IndependentEstimate dataclass / small EstimateSource Protocol {cost_usd|None, token_basis, source_label, present:bool}; cross-check fn takes (a1_estimate, independent: IndependentEstimate|None) -> DivergenceResult. Do NOT add a registry/plugin loader/list dispatch — there are two sources, not N. Confirm the attribution baseline is fully implemented + tested on live data this slice so the seam is never single-caller.

**F3 (Low, drift/boundary) — A-ARCH1 deferral.** A3 adds a THIRD consumer of itu._ private helpers (_attribute/_collect_messages/_is_inside_projects_root) like A1/A2. Do NOT promote them this slice (that's A-ARCH1's job piecemeal). BUT: (a) define A3's OWN new __init__.py exports public-clean from the start (no underscore on anything analyze_value imports cross-module) so A3 adds zero new A-ARCH1 debt; (b) add one line to the ADR-0020 A3 note recording A3 as a 3rd consumer so A-ARCH1 has an accurate consumer count.

**F4 (Info) — metric-1-needs-no-table is sound; watch metric-2 doesn't smuggle a table.** A token-inputs table for OTel is ADR-0013-compliant IFF token inputs only, cost derived at read (like discussion_model_tokens). Prefer the no-schema-change path (read existing rows for the attribution baseline). Compute-don't-store regression guard covers both.

Strengths: pure/transport boundary load-bearing; honest-absence typed into result dataclasses; regression guard turns invariant into a test; scope discipline explicit/boundaried.

---

## Turn 3 — security-specialist (critique)
*2026-06-06T21:19:40.242327+00:00 | confidence: 0.87*
*tags: spec-review, security, approve-with-changes*

## Verdict: APPROVE-WITH-CHANGES (confidence 0.87) — NO blocking
A3 is local, single-developer, read-and-report; no network/API-key/endpoint/new derived-value writes. Threat surface = (1) crafted file at a read path, (2) accidental leak of real sub fee via git. Both low-probability locally, both have specifiable mitigations.

**F1 (Medium, A05/A03 path-traversal) — OTel ingest path needs containment.** analyze_value.py optionally ingests an OTel export file (R-A3.4). Spec specifies the ingest exists but NOT where the path comes from nor that containment is required. At build: resolve with Path.resolve() + validate inside an expected root (repo-relative data/ or _REPO_ROOT or user-configured OTEL_EXPORT_DIR); mirror ingest_token_usage._is_inside_projects_root exactly; reject outside-root with explicit error, don't silently skip. Downgrades to Low if the path is hardcoded to a fixed conventional location (e.g. data/otel_export.jsonl under _REPO_ROOT).

**F2 (Medium, A02 secrets-in-VCS) — config/subscription.yaml carries personal financial metadata.** Unlike model_pricing.yaml (reference data), the sub fee is personal/financial; the PreToolUse 12-pattern scanner does NOT catch a numeric YAML field. At build: (1) add config/subscription.yaml to .gitignore (ENFORCED, not just documented); commit config/subscription.yaml.example with placeholder monthly_fee_usd: 0.00; (2) quality_gate/precommit warn if subscription.yaml staged with non-zero/non-placeholder fee; (3) loader graceful-degradation (missing file -> 'not configured') already handles fresh-clone absence — call out in AC.

**F3 (Low, A08 unvalidated YAML) — negative/non-numeric fee.** Mirror pricing._coerce_rate exactly: float(), reject negatives, parse-failure -> honest-absence (None leverage). Add a negative-fee test (spec lists 'negative' in tests but doesn't specify behavior).

**F4 (Low, A03 JSONL parse of OTel) — bound external input.** Reuse analyze_failures._iter_records (skips bad lines, handles OSError); add a file-size cap (e.g. refuse >100MB); coerce numeric OTel fields via coerce_int/_coerce_rate; never pass an OTel string field into SQL unparameterized.

Trust boundaries: (1) subscription.yaml -> loader: yaml.safe_load + numeric coerce + neg/zero guard + graceful degrade [gaps: neg case, .gitignore]; (2) OTel file -> parser: containment + size bound + per-field coerce [GAP: containment absent — most significant]; (3) CostReport -> leverage: fully trusted, no extra validation; (4) output -> stdout/Layer B: correctly specified (plain aggregates, no transcript free-text, no topic slug).

Strengths: compute-don't-store enforced as a regression test not just docs; honest-absence first-class + testable; load_pricing graceful-degradation mandated as the loader model; no network/credential/Admin key; 'known-broken: no billing API' is good security documentation; A2's _is_inside_projects_root double-check named as the precedent (gap is only that it's not yet applied to the OTel path).

---

## Turn 4 — qa-specialist (critique)
*2026-06-06T21:20:06.250183+00:00 | confidence: 0.82*
*tags: spec-review, qa, approve-with-changes*

## Verdict: APPROVE-WITH-CHANGES (confidence 0.82) — gaps are spec-completeness; AC under-encodes the test contracts implied by requirements
Inherits A1/A2 honesty discipline well; named R-A3.6 scenarios are right. Risk: a build could satisfy the AC list while leaving meaningful paths untested.

**F1 (High, regression guard underspecified) — compute-don't-store assert is too vague to implement unambiguously.** Doesn't say which tables/columns count as a dollar/ratio, schema-introspection vs SELECT-count, which paths exercised, or fixture shape. Tighten: after analyze_value(db_path=tmp_db,...) on a populated discussion_model_tokens fixture, assert (1) no A3-added column is REAL/FLOAT other than existing token-count cols, AND (2) SELECT COUNT(*) of any stored ratio/dollar = 0; exercise BOTH leverage + cross-check paths; @pytest.mark.regression citing ADR-0013. If A3 adds NO new table, simplify to: assert init_db has no new CREATE/ALTER for A3 (state explicitly).

**F2 (High, absent result type undefined) — define the cross-check return shape for 'no independent estimate' BEFORE build.** Avoid divergence_pct=0.0+is_absent (reads as a match). Require a field (e.g. available:bool) False when absent; divergence_pct MUST be None (not 0.0). Sharpen AC: assert result.available is False AND result.divergence_pct is None when absent — not just that a string is printed.

**F3 (High, time-basis untested) — R-A3.2 honesty requirement has no AC/test.** A builder could print '666x' with no period label and nothing fails (R1 calls this a Prime-Objective failure). Add AC: result carries cost window (months/date range from CostReport) AND fee period (monthly); test asserts both non-None/non-empty; cover multi-month window + monthly fee returns BOTH a per-month and a cumulative figure, both labelled.

**F4 (Medium, negative/tiny fee) — specify behavior, not just list it.** State whether negative fee coerces to zero (->None leverage, like _coerce_rate) or raises. Add test for very-large ratio (fee near float epsilon) asserting formatting doesn't crash.

**F5 (Medium, partial OTel coverage) — None/null propagation.** OTel present but covering only a subset of A1's scope: divergence compares complete A1 vs partial independent. Add scope_coverage_pct on the divergence result (analogous to A1 coverage_pct); a comparison against a partial estimate must be labelled. (Lower priority — OTel likely absent — but model it from the start, OR only run when full-scope + report absence otherwise, stated+tested.)

**F6 (Medium, division-by-zero) — percent-delta guard.** (our-indep)/indep*100 with indep=0.0 crashes. Mirror coverage_pct's zero-denominator guard: indep=0.0 -> divergence_pct None/sentinel, not ZeroDivisionError; add test. A zero independent estimate likely signals attribution gap, not pricing flaw.

**F7 (Medium, smoke-test boundary ambiguous) — 'runs against real local data' conflicts with the A1/A2 transport-fidelity boundary.** Restate AC: a CLI integration test on a pre-seeded tmp_path DB asserts the reporter prints a leverage line + a cross-check line without crashing, leverage line contains coverage% + period label. Document a separate MANUAL live-data smoke test outside the automated suite (or mark @pytest.mark.slow/excluded).

**F8 (Medium, AC<->R-A3.6 mismatch) — 'identical estimates -> 0% divergence' is in R-A3.6 but missing from AC.** Add AC: identical A1 vs independent -> available=True, divergence_pct=0.0, direction=None (or exact_match) — unit-tested. This is the case distinguishing 'no estimate' from 'estimate matches'.

**F9 (Low, circular-import) — add a package-root import smoke test.** A1's cost.py is an A3 dependency -> circular-import risk during build. Add: from src.telemetry import <LeverageResult/CrossCheckResult> at test collection time (one assert on type name).

**F10 (Low, regression-ledger parser gotcha) — don't break the gate.** quality_gate _parse_regression_ledger treats all pipe rows as the 6-col fixed-bug format, so a Known-Broken-Approaches row triggers a spurious 'missing test file' gate fail (ledger carries this comment). Put the 'no billing API' known-broken entry in memory/projects/_self.md Solution Paths, NOT the ledger table; the compute-don't-store guard entry goes in the fixed-bugs table normally.

Strengths: inherit-don't-reimplement is right (re-impl would undermine the cross-check's independence); R-A3.3 honest-absence unambiguous at unit level; transport-fidelity boundary correctly drawn; R-A3.4 attribution-independence vs pricing-independence split prevents a vacuous cross-check; 'persist only token inputs, never an external dollar' stated correctly; @pytest.mark.regression named (gate will enforce).

---

## Turn 5 — facilitator (synthesis)
*2026-06-06T21:22:56.003739+00:00 | confidence: 0.86*

## Request Context
- **What was requested**: Plan telemetry Layer A3 — two local, credential-free honesty metrics (value-vs-subscription leverage + estimate cross-check) feeding the north-star Layer B dashboard. Then Steward note -> /build_module -> /review -> commit. NO push.
- **Files/scope**: SPEC-20260606-211429; reuses A1; new src/telemetry/value.py + scripts/telemetry/analyze_value.py + config/subscription.yaml(.example). Scope A3 metrics ONLY.
- **Developer-stated motivation**: Understand-your-AI-use; subscription+individual account ⇒ billing APIs unavailable; local value+cross-check (direction confirmed, not re-litigated).
- **Explicit constraints**: Compute-don't-store inviolable; no credential/billing API; no telemetry into live prompts; reuse A1; scope A3 only; Steward note required; NO push.

## Synthesis
All three specialists APPROVE-WITH-CHANGES (arch 0.84, security 0.87, qa 0.82). **Zero blocking findings; zero halts.** Every finding is build-readiness tightening — the direction and shape are sound. All material findings FOLDED into the spec (now status: reviewed):

**Architecture (F1/F2/F3):** (F1) leverage now takes a CostReport PARAMETER — forking the cost math is signature-impossible; transport imports load_cost_rows/build_cost_report; attribution baseline shares PricingTable.cost_usd, differs only in attribution. (F2) the independent-source seam is pinned to a concrete IndependentEstimate dataclass {cost_usd|None, token_basis, source_label, scope_coverage_pct, present} — two named callers, NO registry. (F3) A3's own __init__ exports are public-clean; A3 reuses (does not promote) the itu._ helpers; ADR-0020 note records A3 as their 3rd consumer (keeps A-ARCH1 honest, no piecemeal promotion).

**Security (F1/F2/F3/F4):** (F1) OTel ingest read from a FIXED location data/otel_export.jsonl under _REPO_ROOT (+ _is_inside_projects_root containment), collapsing the traversal surface. (F2) config/subscription.yaml gitignored; committed file is subscription.yaml.example placeholder; gate warns on a staged real fee (the 12-pattern scanner won't catch a numeric field). (F3) negative/non-numeric fee coerced to not-configured like _coerce_rate. (F4) OTel JSONL: reuse _iter_records, size-cap, coerce numerics, parameterized SQL only.

**QA (F1-F10):** regression guard made concrete (assert no REAL/FLOAT A3 column beyond token counts AND zero stored ratio/dollar rows, exercising both paths — or assert no new table); absent cross-check typed (available:bool False + divergence_pct None, never 0.0); time-basis is now an AC + tested (cost window + fee period non-empty; per-month AND cumulative labelled); div-by-zero guard (indep=0.0 -> None); identical-estimates AC; partial-OTel-scope labelled; CLI test on a pre-seeded tmp DB with the live-data smoke as a separate MANUAL gate; circular-import import test; the 'no billing API' known-broken note goes in _self.md Solution Paths NOT the ledger table (avoids the _parse_regression_ledger spurious-fail gotcha).

Net: the two metrics are well-formed and honest-by-construction (leverage needs no table; absence is typed). Remaining open items are NOT spec defects — they are the Steward note (new local source + value-vs-subscription through the extraction lens) and developer approval, both gating /build_module. Recommend: proceed to the Steward note, then developer approval, then build.

---
