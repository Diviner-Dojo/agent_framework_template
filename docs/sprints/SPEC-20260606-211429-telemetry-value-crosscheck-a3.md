---
spec_id: SPEC-20260606-211429
title: "Telemetry Layer A3 — value-vs-subscription leverage + estimate cross-check (local, no billing API)"
type: spec
status: complete
risk_level: medium
intake_ids: []
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260606-211551-telemetry-value-crosscheck-a3-spec-review
completed_at: 2026-06-06
completed_commit: a639903
---

## Goal
Add two **local, credential-free honesty metrics** to the Telemetry & Oversight component (Layer A, third slice — "A3") that turn A1's bottom-up dollar cost into something a developer can actually *reason about*:

1. **Value-vs-subscription leverage** — A1's API-equivalent cost (≈$666 to date) divided by the developer's flat monthly subscription fee → "the framework drew **N× its subscription cost** in API-equivalent compute." A real understand-your-AI-use number that answers "is this worth it?"
2. **Estimate cross-check (trust calibration)** — A1's bottom-up estimate vs an **independent estimate of the same tokens**. Divergence is surfaced as a first-class honesty metric: it means our pricing/attribution model is wrong somewhere, the same discipline as A1's coverage% but pointed model-vs-model instead of token-vs-token.

Both feed the north-star **Layer B dashboard**; A3 is data-foundation, not the dashboard itself.

## Context
- **Billing reality (resolved 2026-06-06, developer-confirmed):** the developer runs the framework on a **Claude Code subscription (flat fee)** under an **individual account** ("Dan's Individual Org", Members: 1, API plan, $10.90 credits barely touched). The programmatic **Cost API**, **Usage report**, and **Claude Code Analytics API** are *all* unavailable — each requires an Admin key (`sk-ant-admin…`) + a real multi-member organization. The earlier captured decision "A3 data source = programmatic Cost API" is **SUPERSEDED**: on a subscription the Cost API reads ≈$0 for these tokens; there is no per-token "actual" to reconcile against.
- **Direction CONFIRMED (developer, 2026-06-06):** path (a) = *local value + cross-check*, no credential, privacy-clean — explicitly **not** the metered-API-key path. Do not re-litigate.
- **A1 already exists and is committed** (`ed93448`): `src/telemetry/{pricing,cost}.py` compute per-tier dollar cost at read time from `config/model_pricing.yaml` × captured token rows, with an honest token-weighted `coverage_pct` and an "unknown tiers are never zero-rated" rule. Live: opus $632–642 + sonnet $24 ≈ **$666 over ~265M tokens at 100% coverage**.
- **ADR-0013 (ratified accepted, amended by ADR-0020) — compute-don't-store** is inviolable here: the database stores token **inputs** only; every dollar figure is derived at analysis time. A3 must not break this.

### Prior art (informs, does not gate)
- `src/telemetry/cost.py`: `build_cost_report(rows, pricing) -> CostReport`; `CostReport.total_cost_usd`, `.coverage_pct`, `.is_fully_covered`, `.by_tier`. Reuse directly — A3's leverage metric is a pure read over a `CostReport`.
- `src/telemetry/pricing.py`: `PricingTable`, `load_pricing(path)`, `TierRates`, `UNKNOWN_TIER`. The "missing/malformed file → empty table → all-`unknown` (honest), never crash" pattern is the model for loading A3's new config input.
- `scripts/telemetry/analyze_cost.py`: `load_cost_rows(conn, …)` materializes stored breakdown rows as `ModelTokenRow`s; watermark + idempotent DELETE-then-INSERT transport patterns. Mirror for any A3 ingest.
- A1 `/review` (`REV-20260606-070226`) established: coverage as a token denominator; honest absence over false confidence. A3 inherits this — a cross-check with **no independent data for a window must report the gap, never fabricate a match.**

## Requirements

### R-A3.1 — Subscription-fee config input
- A new config input carries the developer's flat subscription fee (`config/subscription.yaml`: `monthly_fee_usd`, `currency`, `plan_label`, `effective_date`). It is a **plain config input**, never persisted to the database.
- **Secrets/privacy enforcement (security F2):** the real fee is personal financial metadata and the PreToolUse 12-pattern scanner does **not** catch a numeric YAML field. Therefore: `config/subscription.yaml` is added to `.gitignore` (enforced, not just documented); the **committed** file is `config/subscription.yaml.example` with a placeholder (`monthly_fee_usd: 0.00  # set locally`). The build adds a `quality_gate.py` (or pre-commit) warning if `config/subscription.yaml` is staged with a non-zero/non-placeholder fee. The loader's "missing file → not configured" path (below) covers the fresh-clone / gitignored-absent case — this is called out as an acceptance criterion.
- Loader follows the `load_pricing` discipline (and `pricing._coerce_rate`): missing/malformed/zero/**negative**/non-numeric fee → metric reports "subscription fee not configured" and the leverage ratio is `None` (honest absence), never a crash and never a fabricated or negative denominator. A negative fee is coerced to the not-configured state (security F3), exactly as `_coerce_rate` clamps negative rates.

### R-A3.2 — Value-vs-subscription leverage (pure, read-side)
- Pure logic in `src/telemetry/` computes leverage from an existing `CostReport` + the configured fee. **No new database table; no stored dollar or ratio** — derived at read, satisfying compute-don't-store by construction.
- **Structural reuse enforcement (architecture F1):** the pure function takes the `CostReport` **as a parameter** — `leverage(report: CostReport, fee: SubscriptionFee | None) -> LeverageResult` — so it loads nothing and forking the cost math is signature-impossible. The transport (`analyze_value.py`) obtains the A1 estimate by importing `load_cost_rows` + `build_cost_report` from `analyze_cost.py` (or a shared helper); it does **not** re-query `discussion_model_tokens` or re-implement cost math.
- Handles: fee unset/zero/negative → `None` leverage with an explanatory reason; partial coverage → leverage is reported against `total_cost_usd` (priced tokens only) with the coverage% carried alongside so the figure is never read as more complete than it is.
- **A time basis is explicit and honest (qa F3):** the `LeverageResult` carries both the **cost window** (months / date range derivable from the cost scope) and the **fee period** (`monthly`); the leverage line states both (e.g. "$666 API-equivalent over ~N months vs $X/mo ⇒ M×/mo" — reporting **both** a per-month and a cumulative figure, each labelled). The spec **forbids** silently comparing a multi-month cumulative cost to a single month's fee without labelling it. Both fields must be non-None/non-empty whenever a leverage figure is produced.

### R-A3.3 — Estimate cross-check (pure divergence logic)
- Pure logic in `src/telemetry/` takes A1's bottom-up estimate and an **independent estimate of the same scope** and returns a structured `DivergenceResult`: absolute delta, percent delta, a direction (our estimate higher/lower), and a classification of *what* the divergence implicates (attribution vs pricing) where the inputs allow that to be distinguished.
- **Concrete seam, pinned now (architecture F2):** the independent estimate is carried by an `IndependentEstimate` dataclass (or a small `EstimateSource` Protocol) of shape `{cost_usd: float | None, token_basis, source_label: str, scope_coverage_pct: float, present: bool}`. The cross-check signature is `cross_check(a1_estimate, independent: IndependentEstimate | None) -> DivergenceResult`. **No registry / plugin loader / `list[EstimateSource]` dispatch** — there are exactly two sources (R-A3.4), not N.
- **Honest absence is mandatory, and typed (qa F2):** the result has an explicit `available: bool` that is `False` when no independent estimate exists; in that state `divergence_pct is None` (never `0.0`, which a consumer would misread as a match). Absence is a first-class state, not a zero and not a silent skip.
- **Division-by-zero guard (qa F6):** when the independent estimate is `0.0`, `divergence_pct` is `None` (mirroring `CostReport.coverage_pct`'s zero-denominator guard), never a `ZeroDivisionError`; a zero independent estimate is classified as an attribution gap, not a pricing flaw.
- **Identical estimates (qa F8):** when A1 and the independent estimate match for a scope, the result is `available=True`, `divergence_pct=0.0`, `direction=None` (or an `exact_match` variant) — distinguishing "estimate matches" from "no estimate available".
- **Partial-scope honesty (qa F5):** the `IndependentEstimate.scope_coverage_pct` records what fraction of A1's scope the independent source covers; a divergence computed against a partial estimate is labelled partial (analogous to A1's `coverage_pct`). The OTel source only contributes a pricing cross-check at the scope it actually covers; outside that scope the result reports absence.

### R-A3.4 — Independent estimate source(s), local-only
Exactly two fully-local independent sources are wired this slice (no registry — architecture F2); the cross-check logic (R-A3.3) is source-shaped via `IndependentEstimate`.
- **Always-available baseline (no new data needed) — ships live this slice:** an independent recomputation of the *same captured tokens* by a path that does **not** share A1's discussion-window attribution — e.g. aggregating the raw token-capture rows directly — so a divergence isolates an **attribution** flaw. It shares the **same pricing path** (`PricingTable.cost_usd`) and differs *only* in the aggregation/attribution step (architecture F1) — otherwise the divergence would conflate an attribution flaw with a second pricing implementation. This must run on the existing $666 dataset today (it is what keeps the seam from being single-caller).
- **Independent pricing cross-check (when source present):** Claude Code's own emitted cost/token telemetry via the **OpenTelemetry export** (`code.claude.com/docs/en/monitoring-usage`: `claude_code.token.usage`, `claude_code.cost.usage`) when the developer has it enabled — tests **pricing** independently because Claude Code prices with its own table. If absent (the likely case for the historical window), the cross-check reports its absence per R-A3.3.
- **External-source ingest hardening (security F1, F4):** the OTel export is read from a **fixed conventional location** (`data/otel_export.jsonl` under `_REPO_ROOT`) rather than an arbitrary user-supplied path, collapsing the traversal surface; the read still resolves with `Path.resolve()` and validates containment via the `ingest_token_usage._is_inside_projects_root` pattern, refuses files over a size cap (e.g. 100 MB), and reuses the `analyze_failures._iter_records` bad-line/OSError-tolerant reader. Numeric OTel fields are coerced via `coerce_int`/`_coerce_rate`; no OTel string field is ever interpolated into SQL (parameterized only). Persist only token **inputs** from any external source; **never** persist an externally-reported dollar figure as if it were ours.

### R-A3.5 — Surfacing
- A read-side reporter (CLI in `scripts/telemetry/`, mirroring `analyze_cost`'s `_print_report`) prints both metrics with their honesty caveats: leverage with its coverage% and time basis; cross-check with its divergence (or its explicit absence) and which flaw class it implicates.
- Output is plain aggregates suitable to become a Layer B dashboard panel later (Steward condition #2: schema-constrained aggregates, no transcript free-text; topic slug never printed — applies if/when this feeds Layer C).

### R-A3.6 — Tests + gate
- Pure logic unit-tested to the project's standard (coverage ≥80% overall; A1's pure modules sit ≥98%). Cover, each with a **meaningful assertion** (not "no exception"):
  - fee unset / zero / **negative** (→ not-configured, `None` leverage) / **near-float-epsilon** (very large ratio, asserts formatting doesn't crash); malformed config.
  - leverage **time-basis** present: `LeverageResult` cost-window and fee-period fields non-None/non-empty; multi-month window returns both per-month and cumulative, labelled (qa F3).
  - cross-check: zero independent data → `available is False` **and** `divergence_pct is None` (qa F2); attribution divergence > 0 on the live baseline; **identical estimates** → `available=True, divergence_pct=0.0, direction=None` (qa F8); independent estimate `0.0` → `divergence_pct is None`, no `ZeroDivisionError` (qa F6); partial OTel scope → labelled partial (qa F5).
- **Compute-don't-store regression guard (architecture F1, qa F1)** — `@pytest.mark.regression`, comment citing ADR-0013: after `analyze_value(db_path=tmp_db, …)` over a populated `discussion_model_tokens` fixture exercising **both** the leverage and cross-check paths, assert (1) no A3-added column is `REAL`/`FLOAT` other than the existing token-count columns, **and** (2) `SELECT COUNT(*)` of any stored ratio/dollar value is 0. **If A3 adds no new table at all** (preferred), the guard instead asserts `init_db.py` introduces no new `CREATE TABLE`/`ALTER TABLE` for A3.
- **Circular-import guard (qa F9):** a collection-time `from src.telemetry import <public A3 dataclasses>` import test (A1's `cost.py` is an A3 dependency).
- Transport/ingest exercised behind the transport-fidelity boundary (integration tests with tmp fixtures / monkeypatched roots), consistent with A1/A2. **The CLI acceptance test runs against a pre-seeded `tmp_path` DB** (asserts a leverage line + a cross-check line print without crashing, leverage line carries coverage% + period label). The live-`~/.claude` / live-`$666`-data / live-OTel smoke is a **manual** gate outside the automated suite (qa F7), labelled as such.
- `python scripts/quality_gate.py` 7/7 before `/review`.

## Constraints
- **Compute-don't-store is inviolable (ADR-0013):** persist token **inputs** and the subscription fee as a **config input** only; derive every ratio and dollar/divergence figure at read. **A `pytest.mark.regression` guard must assert no A3 code path writes a dollar amount or a ratio into the database.**
- **No new credential, no network billing call, no Admin key, no metered API key.** Local sources only.
- **No telemetry into any live agent prompt** (Steward condition #3, KV-cache integrity). A3 is read/report-only.
- **Reuse, don't re-implement** A1's `pricing`/`cost` modules and the `scripts/telemetry` transport patterns; do not fork a second cost computation. Enforced structurally (architecture F1): pure leverage takes a `CostReport` parameter; transport imports `load_cost_rows`/`build_cost_report`; the attribution baseline shares `PricingTable.cost_usd`.
- **Public-surface hygiene (architecture F3):** A3's own new exports in `src/telemetry/__init__.py` are public-clean from the start (no underscore on anything `analyze_value.py` imports cross-module). A3 continues to **reuse** the existing `ingest_token_usage._` private helpers as A1/A2 do — it does **not** promote them (that is A-ARCH1's job, out of scope). The ADR-0020 A3 note records A3 as a *third* consumer of those private helpers so A-ARCH1 has an accurate consumer count when decided.
- **Scope is A3 metrics ONLY.** Explicitly **out of scope** (their own later slices, do not fold in): A-PERF2 (`_detect_for_session` → `os.scandir`), A-ARCH1 (full public-surface decision), A1.1 (cost-path session-keyed watermark / session storage dimension). Layer B (viewer) and Layer C (ntfy digest) remain separately Steward-gated.
- **Known-broken approach to avoid:** treating any Anthropic billing/usage/analytics API as a data source (individual account ⇒ unavailable; would read ≈$0 on a subscription anyway). **Record it in `memory/projects/_self.md` Solution Paths, NOT the regression-ledger Known-Broken-Approaches table** — `quality_gate._parse_regression_ledger` reads every pipe row as the 6-column fixed-bug format and a known-broken row there triggers a spurious "missing test file" gate failure (qa F10, per the existing ledger comment). The compute-don't-store regression-test entry goes in the ledger fixed-bugs table normally.
- Steward note required before build (new local telemetry/observability source + the value-vs-subscription framing through the extraction lens; compute-don't-store reaffirmed).

## Acceptance Criteria
- [ ] Subscription fee loads from a config input with the `load_pricing`/`_coerce_rate` discipline; unset/zero/negative/non-numeric → honest "not configured" (`None` leverage), never a crash or a fabricated/negative denominator. `config/subscription.yaml` is gitignored; `config/subscription.yaml.example` is the committed placeholder; a gate/pre-commit warning fires if a real fee is staged.
- [ ] Leverage computed purely at read from an existing `CostReport` parameter + fee, with **no new stored dollar/ratio**. The `LeverageResult` carries coverage% **and** a non-empty time basis (cost window + fee period); a multi-month window reports both per-month and cumulative figures, each labelled.
- [ ] Cross-check returns a structured `DivergenceResult` (delta, %, direction, flaw class) for the always-available attribution baseline on the live $666 dataset (baseline shares `PricingTable.cost_usd`; differs only in attribution).
- [ ] Cross-check absent state: `available is False` **and** `divergence_pct is None` when no independent source — verified by test; identical estimates → `available=True, divergence_pct=0.0, direction=None`; independent estimate `0.0` → `divergence_pct is None` (no `ZeroDivisionError`).
- [ ] A read-side CLI prints both metrics with honesty caveats; a CLI integration test on a pre-seeded `tmp_path` DB asserts both lines print (leverage line carries coverage% + period); the live-data smoke is a separate manual gate.
- [ ] `@pytest.mark.regression` guard proves no A3 path persists a dollar figure or ratio (or that A3 adds no new table) — compute-don't-store; plus a collection-time package-root import test (circular-import guard).
- [ ] `quality_gate.py` 7/7; coverage ≥80%; A3 pure logic ≥ the A1/A2 bar.
- [ ] ADR-0020 gets an A3 implementation note (local source, the superseded-Cost-API rationale, the two metrics, compute-don't-store reaffirmation, A3-as-third-consumer of the `itu._` helpers).

## Risk Assessment
- **R1 — Misleading leverage number (cumulative cost ÷ one month's fee).** *Mitigation:* R-A3.2 mandates an explicit, labelled time basis; the figure carries coverage% and period. A leverage number read as more authoritative than it is would itself be a Prime-Objective honesty failure.
- **R2 — Cross-check has no independent data for the historical window** (OTel almost certainly wasn't enabled for the $666). *Mitigation:* the always-available local attribution baseline (R-A3.4) guarantees a real cross-check today; the OTel pricing cross-check degrades to honest absence (R-A3.3) until enabled going forward. This is acceptable and is itself the honest story.
- **R3 — Compute-don't-store erosion** (tempting to cache a dollar/ratio). *Mitigation:* the R-A3.6 regression guard + the metric-1-needs-no-table design make storing a derived figure a test failure, not a judgement call.
- **R4 — Independent estimate isn't truly independent** (if it reuses A1's exact attribution + pricing it can't surface anything). *Mitigation:* R-A3.4 separates an attribution-independent baseline (different aggregation path, same pricing) from a pricing-independent source (OTel, its own pricing); the divergence's flaw-class classification depends on which independence holds.
- **R5 — Scope creep into deferred advisories / Layer B.** *Mitigation:* Constraints fix the boundary explicitly.

## Affected Components
- `config/subscription.yaml.example` (NEW, committed) — placeholder flat-fee config input; real `config/subscription.yaml` is gitignored and set locally.
- `.gitignore` — add `config/subscription.yaml`.
- `src/telemetry/value.py` (NEW, pure) — `leverage(report, fee)`, `cross_check(a1_estimate, independent)`, and the `LeverageResult` / `DivergenceResult` / `IndependentEstimate` / `SubscriptionFee` dataclasses. (Final module name/split decided at build; keep pure logic out of `scripts/`.)
- `src/telemetry/__init__.py` — export A3's new public surface, public-clean (no underscores on cross-module imports).
- `scripts/telemetry/analyze_value.py` (NEW, transport/CLI) — import `load_cost_rows`/`build_cost_report` for the A1 estimate; compute the attribution baseline; optionally ingest OTel token inputs from the fixed `data/otel_export.jsonl` (containment + size-cap + tolerant reader); print both metrics.
- `scripts/quality_gate.py` (or a pre-commit step) — warn if `config/subscription.yaml` is staged with a non-placeholder fee.
- `scripts/init_db.py` — only if an external-source token-inputs table is genuinely needed (token inputs only); **prefer no schema change** (baseline reads existing rows).
- `tests/test_telemetry.py` — A3 unit + integration tests incl. the compute-don't-store regression guard + circular-import guard.
- `docs/adr/ADR-0020-telemetry-oversight-component.md` — A3 implementation note (incl. A3-as-third-consumer of `itu._` helpers).
- `memory/bugs/regression-ledger.md` — fixed-bugs entry for the compute-don't-store guard. The "no billing API" known-broken approach goes in `memory/projects/_self.md` Solution Paths (qa F10), **not** the ledger table.

## Dependencies
- **Depends on:** A1 (`src/telemetry/{pricing,cost}.py`, `scripts/telemetry/analyze_cost.py`, `config/model_pricing.yaml`) — committed `ed93448`. ADR-0013 (compute-don't-store) + ADR-0020.
- **Depended on by:** Layer B dashboard (north star) — A3 is one of its data panels. Layer C digest (aggregates-only) may later surface the leverage/divergence numbers.
- **Gated by:** its own Steward note (new local source + extraction-lens framing) before `/build_module`; developer approval of this spec (Principle #7 / confidence gate).
