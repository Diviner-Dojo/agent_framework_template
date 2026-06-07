---
review_id: REV-20260606-223941
discussion_id: DISC-20260606-223941-review-telemetry-value-crosscheck-a3
date: 2026-06-06
risk_level: medium
verdict: approve-with-changes
panel: [qa-specialist, security-specialist, architecture-consultant, independent-perspective]
blocking_findings: 1
advisory_findings: 9
reviewed_files:
  - src/telemetry/value.py
  - src/telemetry/__init__.py
  - scripts/telemetry/analyze_value.py
  - config/subscription.yaml.example
  - .gitignore
  - scripts/quality_gate.py
  - tests/test_telemetry.py
  - docs/adr/ADR-0020-telemetry-oversight-component.md
  - memory/projects/_self.md
  - memory/bugs/regression-ledger.md
---

# Review — Telemetry Layer A3 (value-vs-subscription leverage + estimate cross-check)

## Verdict: APPROVE-WITH-CHANGES

One BLOCKING finding (fixed in-session with a regression test) and nine advisory findings
(cheap ones fixed; three framing/presentation decisions flagged for the developer / Layer B).
Post-fix: quality gate **7/7**, `value.py` 100% coverage, `analyze_value.py` 88%, **113 tests pass**.

Panel (all Sonnet; facilitator Opus): qa-specialist 0.88, security-specialist 0.92,
architecture-consultant 0.86, independent-perspective 0.82.

## Required changes (blocking) — RESOLVED

**B1 — `--since` scope mismatch (independent-perspective).** A1's cost was loaded from the full
stored `discussion_model_tokens` table (all-time, ignoring `--since`), while the attribution
baseline was recomputed live from `_collect_messages(session_paths, since)` which honours
`--since`. So `analyze_value --since <date>` compared an all-time A1 against a filtered baseline —
two different token populations — and printed a numerically false divergence under an advertised
flag, violating the same "no silent window mismatch" discipline the leverage time-basis enforces.

*Fix:* when `since` is set, the attribution cross-check now returns typed absence
(`available=False`) with an explicit reason; the default no-`--since` run is unchanged. Regression
test `test_analyze_value_since_skips_attribution_crosscheck`. Verified live: `--since` now prints
"unavailable" with the reason instead of a fabricated number.

## Recommended improvements — RESOLVED in-session

- **A-IP-B (independent-perspective) — misleading "flaw/divergence" wording.** "our estimate is 70%
  lower; implicates attribution" reads as "A1 is wrong by 70%", when it is actually *coverage*
  (the 70% is activity outside any discussion window — not an error). The attribution print is now
  a coverage frame: "$X of measured spend is attributed to captured discussions, out of $Y total
  ⇒ captured discussions cover Z% of measured AI spend (the rest is activity outside any discussion
  window, not an error)". The signed-divergence frame is kept only for the pricing/OTel source,
  where a divergence genuinely warrants attention.
- **A-ARCH-2 — `FLAW_*` constants not in package `__all__`.** Added `FLAW_ATTRIBUTION` /
  `FLAW_PRICING` to `src/telemetry/__init__.py` exports for surface symmetry.
- **A-QA-1..4 — test-completeness gaps.** Added: negative-OTel-cost → typed absence;
  `window_months=0` boundary; `_baseline_estimate({})` empty-messages absence; and a
  `divergence_pct is None` assertion on the unusable-independent parametrize.

## Accepted as documented low-risk (security) — no code change

A3 is a read-only, local, single-developer tool (no network, no SQL write, no credential).
Security verdict APPROVE 0.92, no blocking. Each finding carries the specialist's own exception:
- **S1 (Med) `--otel` containment is to the `data/` subtree, not the single fixed file** —
  intentional: `--otel` supports an alternate JSONL within `data/` (the test-injection pattern).
- **S2 (Low) `--subscription` has no path containment** — `yaml.safe_load` + only a positive float
  extracted; a developer passing `--subscription /etc/passwd` attacks themselves. (Containment to
  `config/` would break the tmp-path test pattern.)
- **S3 (Low) TOCTOU** between `_is_within` and `open()` — academic on Windows (symlink creation
  needs privilege).
- **S4 (Low) staged-fee advisory** reads the working-tree value but checks staged presence —
  cosmetic message mismatch; the gate always warns when the file is staged and never crashes.

## Flagged for the developer / Layer B — NOT changed (framing & design decisions)

These are interpretive/presentation choices the gatekeeper should own; the data shapes are correct.
- **A-IP-C — leverage framing.** The cumulative multiple is printed first and is unbounded (grows
  with the window); the per-month figure (the apples-to-apples one, since the fee is monthly) is
  second and goes `n/a` when the window is unknown. Consider leading with per-month, and consider
  naming it a "list-price-equivalent multiple" rather than "leverage/value" (API list price is not
  the counterfactual for someone who chose a subscription *because* it is cheaper at their volume).
- **A-IP-D — OTel perpetual absence.** The pricing cross-check will read "unavailable" on virtually
  every run (the export must be enabled). On the Layer B dashboard, present it as an "enable OTel to
  activate" affordance rather than a permanent "unavailable" row that trains the eye to ignore it.
- **A-IP-E — baseline `scope_coverage_pct`.** Hardcoded 100 (correct in the scope-overlap sense);
  the baseline's own pricing-coverage is a separate axis, left as-is.

## Strengths

- Typed honest-absence is rigorous and consistent (`available=False`/`divergence_pct=None`, never a
  misleading `0.0`; `configured=False` with a `reason`) — the panel singled this out as rare and
  correct.
- The attribution baseline genuinely shares A1's pricing path (`build_cost_report` + same
  `PricingTable`), so the comparison is an attribution-only signal — reuse-not-fork verified.
- External OTel ingest is hardened at the boundary: containment-before-existence-probe (no existence
  oracle), 100 MB cap, tolerant reader, bool/numeric coercion, and it refuses to re-cost OTel tokens
  with our own table (which would destroy independence).
- compute-don't-store is upheld with a real regression guard (before/after row-count snapshot + no
  A3 table).
- `bool` rejection in `_coerce_fee` (guards `float(True) == 1.0`) — careful denominator hygiene.

## Education gate

**Recommended** (medium risk, new module). Run `/walkthrough` + `/quiz` interactively with the
developer when they return — teach the gatekeeper the *concepts* (coverage-vs-divergence framing,
typed honest-absence, the `--since` scope trap, leverage time-basis) per the teach-don't-dump
approach, not a doc dump. Do **not** commit before the education gate.
