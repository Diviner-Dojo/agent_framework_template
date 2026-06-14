"""Report value-vs-subscription leverage + estimate cross-check (telemetry A3).

The I/O / transport layer for A3's two local honesty metrics. The pure math
lives in ``src/telemetry/value.py``; this module only *assembles inputs* and
prints. It is **read-only and persists nothing** (ADR-0013 compute-don't-store;
A3 adds no table) — every dollar/ratio/divergence is derived here at read time.

Inputs assembled:

* **A1 cost report** — loaded from the already-stored ``discussion_model_tokens``
  rows (``analyze_cost.load_cost_rows`` + ``build_cost_report``); no transcript
  re-parse, no forked cost computation (the same A1 path).
* **Attribution baseline** (always-available independent estimate) — an
  *un-windowed* per-model aggregation of every transcript message, priced with
  the **same** ``PricingTable``. It differs from A1 only in that it skips the
  discussion-window attribution step, so the divergence isolates how much of the
  developer's total token spend A1 attributes to captured discussions (an
  attribution/coverage signal, ``flaw_class = "attribution"``).
* **OpenTelemetry export** (independent *pricing* estimate, when present) — read
  from the fixed local file ``data/otel_export.jsonl`` (Claude Code's own
  ``claude_code.token.usage`` / ``claude_code.cost.usage``). Absent for most
  developers (export must be enabled), in which case the cross-check reports its
  absence honestly rather than fabricating a match.

Transport-fidelity boundary: live ``~/.claude`` discovery and a live OTel
endpoint are not unit-tested; the OTel parser is exercised with tmp fixtures.

Usage:
    python scripts/telemetry/analyze_value.py
    python scripts/telemetry/analyze_value.py --since YYYY-MM-DD
    python scripts/telemetry/analyze_value.py --subscription path/to/subscription.yaml
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.telemetry.analyze_cost import load_cost_rows  # noqa: E402
from src.telemetry.cost import CostReport, ModelTokenRow, build_cost_report  # noqa: E402
from src.telemetry.pricing import UNKNOWN_TIER, PricingTable, load_pricing  # noqa: E402
from src.telemetry.value import (  # noqa: E402
    FLAW_ATTRIBUTION,
    FLAW_PRICING,
    DivergenceResult,
    IndependentEstimate,
    LeverageResult,
    SubscriptionFee,
    cross_check,
    leverage,
    load_subscription_fee,
)

DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"
DATA_DIR = _REPO_ROOT / "data"
#: Fixed conventional location for the OTel export (NOT user-supplied, so the
#: path-traversal surface collapses to a symlink swap, guarded below).
OTEL_EXPORT_PATH = DATA_DIR / "otel_export.jsonl"
#: Refuse to read an OTel file larger than this (defensive bound, security F4).
OTEL_MAX_BYTES = 100 * 1024 * 1024
_DAYS_PER_MONTH = 30.44

# OTel attribute values for token kinds (Claude Code's claude_code.token.usage).
_OTEL_TOKEN_KINDS = {
    "input",
    "output",
    "cacheread",
    "cachecreation",
    "cache_read",
    "cache_creation",
}


def _is_within(path: Path, root: Path) -> bool:
    """Return True iff ``path`` resolves to inside ``root`` (symlink-safe)."""
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False


def _load_a1_report(conn: sqlite3.Connection, pricing: PricingTable) -> CostReport:
    """Build A1's cost report from the stored breakdown rows (no re-parse)."""
    return build_cost_report(load_cost_rows(conn), pricing)


def _window_months(messages: dict[str, itu.MessageRecord]) -> float | None:
    """Return the span of message timestamps in months, or ``None``.

    The leverage time basis (Steward binding condition): a labelled per-month
    figure requires knowing how long the cost accrued over. ``None`` when there
    are too few timestamps to span a window.
    """
    stamps = [m.timestamp for m in messages.values() if m.timestamp is not None]
    if len(stamps) < 2:
        return None
    span_days = (max(stamps) - min(stamps)).total_seconds() / 86400.0
    if span_days <= 0:
        return None
    return span_days / _DAYS_PER_MONTH


def _baseline_estimate(
    messages: dict[str, itu.MessageRecord], pricing: PricingTable
) -> IndependentEstimate:
    """Independent attribution baseline: un-windowed per-model cost of all tokens.

    Aggregates every message per ``model`` with **no** discussion-window
    attribution, then prices with the same table. Covers all of A1's scope (every
    windowed token is also here), so ``scope_coverage_pct`` is 100; the *signal*
    is the divergence, which measures the un-attributed share of total spend.
    """
    buckets: dict[str, dict[str, int]] = defaultdict(lambda: {"in": 0, "out": 0, "cr": 0, "cc": 0})
    for message in messages.values():
        model_id = message.model or UNKNOWN_TIER
        bucket = buckets[model_id]
        bucket["in"] += message.input_tokens or 0
        bucket["out"] += message.output_tokens or 0
        bucket["cr"] += message.cache_read_tokens or 0
        bucket["cc"] += message.cache_create_tokens or 0
    if not buckets:
        return IndependentEstimate(
            present=False,
            cost_usd=None,
            token_basis=0,
            source_label="attribution-baseline",
            scope_coverage_pct=0.0,
            flaw_class=FLAW_ATTRIBUTION,
        )
    rows = [
        ModelTokenRow(
            discussion_id="(all)",
            model_id=model_id,
            tier=pricing.resolve_tier(None if model_id == UNKNOWN_TIER else model_id),
            tokens_in=b["in"],
            tokens_out=b["out"],
            cache_read_tokens=b["cr"],
            cache_create_tokens=b["cc"],
        )
        for model_id, b in buckets.items()
    ]
    report = build_cost_report(rows, pricing)
    return IndependentEstimate(
        present=True,
        cost_usd=report.total_cost_usd,
        token_basis=report.total_tokens,
        source_label="attribution-baseline (un-windowed, all transcript tokens)",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_ATTRIBUTION,
    )


def _otel_estimate(path: Path = OTEL_EXPORT_PATH) -> IndependentEstimate:
    """Independent *pricing* estimate from Claude Code's OTel export, if present.

    Hardened external-source ingest (security F1/F4): the path is fixed (not
    user-supplied); it must resolve inside ``data/``; the file must be under the
    size cap; parsing is bad-line tolerant; only Claude Code's *reported cost* is
    used (read at runtime, never persisted). Absence — the common case, since the
    OTel export must be explicitly enabled — yields ``present=False`` so the
    cross-check reports honest absence rather than a fabricated match.
    """
    absent = IndependentEstimate(
        present=False,
        cost_usd=None,
        token_basis=0,
        source_label="otel",
        scope_coverage_pct=0.0,
        flaw_class=FLAW_PRICING,
    )
    if not _is_within(path, DATA_DIR):
        # Refuse a path that resolves outside data/ (symlink swap, or a
        # user-supplied --otel path) BEFORE any existence probe, so the tool
        # never leaks whether an out-of-bounds path exists.
        return absent
    if not path.exists() or not path.is_file():
        return absent
    try:
        if path.stat().st_size > OTEL_MAX_BYTES:
            return absent
    except OSError:
        return absent

    cost_usd = 0.0
    tokens = 0
    saw_cost = False
    try:
        with path.open(encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue  # tolerant: skip a malformed line
                if not isinstance(record, dict):
                    continue
                metric = str(record.get("metric") or record.get("name") or "")
                value = record.get("value")
                if not isinstance(value, int | float) or isinstance(value, bool):
                    continue
                if "cost" in metric:
                    cost_usd += float(value)
                    saw_cost = True
                elif "token" in metric:
                    attrs = record.get("attributes")
                    kind = ""
                    if isinstance(attrs, dict):
                        kind = str(attrs.get("type") or "").replace("-", "").lower()
                    if not kind or kind in _OTEL_TOKEN_KINDS:
                        tokens += int(value)
    except OSError:
        return absent

    if not saw_cost:
        # Tokens but no reported cost: we cannot form an independent *pricing*
        # estimate (re-costing with our own table would not be independent), so
        # report absence honestly.
        return absent
    return IndependentEstimate(
        present=True,
        cost_usd=cost_usd,
        token_basis=tokens,
        source_label="otel (claude_code.cost.usage)",
        scope_coverage_pct=100.0,
        flaw_class=FLAW_PRICING,
    )


def assemble_value_inputs(
    conn: sqlite3.Connection,
    *,
    pricing: PricingTable,
    project_root: Path | None = None,
    since: object | None = None,
    subscription_path: Path | None = None,
    otel_path: Path = OTEL_EXPORT_PATH,
    a1_report: CostReport | None = None,
) -> dict[str, object]:
    """Assemble A3 inputs + compute both metrics — read-only, no init_db, no print.

    The single read-only computation path for Layer A3, shared by the CLI
    orchestrator (:func:`analyze_value`) and the Layer B dashboard so neither
    forks a second cost/leverage path (ADR-0020 single-path discipline). A1 comes
    from the stored breakdown rows on ``conn`` (no transcript re-parse for cost);
    the attribution baseline is read live from the transcripts. This function
    **writes nothing** — it never calls ``init_db`` and only reads ``conn`` — so a
    caller may pass a ``file:...?mode=ro`` connection.

    Args:
        conn: An open SQLite connection (may be read-only) to load A1 from.
        pricing: Resolved pricing table.
        project_root: Project whose transcripts feed the attribution baseline
            (defaults to the framework root used by ``ingest_token_usage``).
        since: Ignore messages older than this timestamp (passed to the parser);
            when set, the attribution cross-check reports typed absence (the
            all-time stored A1 and a windowed baseline are different token
            populations — the same honesty guard A3's CLI enforces).
        subscription_path: Subscription-fee config path (defaults to the
            gitignored ``config/subscription.yaml``).
        otel_path: OTel export path (defaults to ``data/otel_export.jsonl``).
        a1_report: A precomputed A1 :class:`CostReport` to reuse (the dashboard
            builds one for its cost panel); built from ``conn`` when ``None`` so
            the A1 figure is a single source of truth across callers.

    Returns:
        A dict carrying ``leverage`` (:class:`LeverageResult`), ``attribution``
        and ``pricing`` (:class:`DivergenceResult`), ``messages`` (count),
        ``a1_cost_usd``, and ``a1_report`` (:class:`CostReport`). Nothing is
        persisted.
    """
    project_root = project_root or itu.PROJECT_ROOT
    fee: SubscriptionFee | None = load_subscription_fee(subscription_path)

    # Independent attribution baseline needs the transcripts; A1 comes from the DB.
    messages: dict[str, itu.MessageRecord] = {}
    if itu.CLAUDE_PROJECTS_ROOT.exists():
        session_paths = itu.discover_session_dirs(project_root)
        if session_paths:
            messages = itu.collect_messages(session_paths, since)

    report = a1_report if a1_report is not None else _load_a1_report(conn, pricing)

    window_months = _window_months(messages)
    lev: LeverageResult = leverage(report, fee, window_months=window_months)
    # Honesty guard (review BLOCKING): A1 is loaded from the full stored
    # breakdown (all-time), but the baseline is recomputed live and honours
    # ``since``. Comparing all-time A1 against a ``--since``-filtered baseline
    # would divide two different token populations and print a false divergence.
    # When ``since`` is set the windows are not provably identical, so the
    # attribution cross-check reports typed absence rather than a fabricated
    # number (the same discipline the leverage time-basis enforces).
    if since is None:
        baseline = _baseline_estimate(messages, pricing)
    else:
        baseline = IndependentEstimate(
            present=False,
            cost_usd=None,
            token_basis=0,
            source_label=(
                "attribution baseline skipped: --since filters the live baseline but not the "
                "all-time stored A1 cost, so the compared windows would differ"
            ),
            scope_coverage_pct=0.0,
            flaw_class=FLAW_ATTRIBUTION,
        )
    attribution: DivergenceResult = cross_check(report, baseline)
    otel = _otel_estimate(otel_path)
    pricing_check: DivergenceResult = cross_check(report, otel)
    return {
        "leverage": lev,
        "attribution": attribution,
        "pricing": pricing_check,
        "messages": len(messages),
        "a1_cost_usd": report.total_cost_usd,
        "a1_report": report,
    }


def analyze_value(
    *,
    db_path: Path = DB_PATH,
    project_root: Path | None = None,
    since: object | None = None,
    subscription_path: Path | None = None,
    otel_path: Path = OTEL_EXPORT_PATH,
    pricing: PricingTable | None = None,
) -> dict[str, object]:
    """Assemble inputs, compute both metrics, print, and return a summary.

    The CLI orchestrator: it ensures the schema (``init_db``), opens a connection,
    delegates the read-only assembly to :func:`assemble_value_inputs` (the shared
    single path), prints the report, and returns the summary.

    Args:
        db_path: SQLite database path (injectable for tests).
        project_root: Project whose transcripts to scan for the baseline.
        since: Ignore messages older than this timestamp (passed to the parser).
        subscription_path: Subscription-fee config path (defaults to the gitignored
            ``config/subscription.yaml``).
        otel_path: OTel export path (defaults to the fixed ``data/otel_export.jsonl``).
        pricing: Pricing table (defaults to loading the YAML).

    Returns:
        A summary dict carrying the :class:`LeverageResult` and both
        :class:`DivergenceResult` objects plus counts — nothing is persisted.
    """
    project_root = project_root or itu.PROJECT_ROOT
    pricing = pricing or load_pricing()

    if not db_path.exists():
        print(f"SQLite database not found at {db_path}. Run scripts/init_db.py first.")
        return {"leverage": None, "attribution": None, "pricing": None, "messages": 0}
    init_db(db_path, quiet=True)

    conn = sqlite3.connect(str(db_path))
    try:
        result = assemble_value_inputs(
            conn,
            pricing=pricing,
            project_root=project_root,
            since=since,
            subscription_path=subscription_path,
            otel_path=otel_path,
        )
    finally:
        conn.close()

    _print_report(result["leverage"], result["attribution"], result["pricing"])
    return result


def _fmt_ratio(value: float | None) -> str:
    """Format a leverage multiple, or a clear placeholder when absent."""
    return f"{value:,.2f}x" if value is not None else "n/a"


def _print_leverage(lev: LeverageResult) -> None:
    """Print the list-price-equivalent multiple, leading with the per-month figure.

    Named "list-price-equivalent multiple", not "leverage/value" (developer
    decision): the API list price is not the subscription user's counterfactual —
    they chose a flat plan *because* it is cheaper at their volume. The per-month
    multiple leads because it is the apples-to-apples comparison against a monthly
    fee; the cumulative multiple (which grows unbounded with the window) is shown
    second as supporting context.
    """
    print("== List-price-equivalent vs subscription ==")
    if not lev.configured:
        print(f"  list-price-equivalent multiple: n/a - {lev.reason}")
        print(f"  (A1 cost so far: ${lev.total_cost_usd:,.2f}, coverage {lev.coverage_pct}%)")
        return
    print(
        f"  list-price-equivalent compute: ${lev.total_cost_usd:,.2f} "
        f"(coverage {lev.coverage_pct}% of billable tokens)"
    )
    print(f"  subscription fee:    ${lev.monthly_fee_usd:,.2f}/{lev.fee_period}")
    if lev.leverage_per_month is not None and lev.window_months is not None:
        print(
            f"  per-month multiple (over ~{lev.window_months:.1f} months): "
            f"{_fmt_ratio(lev.leverage_per_month)}/mo"
        )
    else:
        print(f"  per-month multiple: n/a - {lev.note or 'cost window unknown'}")
    print(f"  cumulative over the window: {_fmt_ratio(lev.leverage_cumulative)}")


def _print_divergence(title: str, dv: DivergenceResult) -> None:
    """Print one cross-check, surfacing honest absence explicitly.

    The two sources are framed differently on purpose (review finding): the
    attribution source is a **coverage** measure (what share of total spend is
    attributed to captured discussions — the remainder is not an error), so a
    signed "divergence/flaw" frame would misread as "A1 is wrong". The pricing
    source is a genuine divergence (our estimate vs an independently-priced one),
    so the signed frame is correct there.
    """
    print(f"== {title} ==")
    if not dv.available:
        # The OTel pricing source is "off until enabled", not a failure — present
        # it as an affordance rather than a perpetual dead "unavailable" row
        # (developer decision). Other absences keep the literal honest wording.
        if (dv.source_label or "").startswith("otel"):
            print(
                "  not yet active - enable Claude Code's OpenTelemetry export to turn on this "
                "independent pricing cross-check (code.claude.com/docs/en/monitoring-usage)"
            )
            return
        print(f"  cross-check: unavailable - {dv.reason}")
        if dv.source_label:
            print(f"  ({dv.source_label})")
        if dv.independent_cost_usd is not None:
            print(f"  (independent source reported ${dv.independent_cost_usd:,.2f})")
        return
    if dv.flaw_class == FLAW_ATTRIBUTION and dv.our_cost_usd <= dv.independent_cost_usd:
        coverage = (
            dv.our_cost_usd / dv.independent_cost_usd * 100.0 if dv.independent_cost_usd else 0.0
        )
        print(
            f"  ${dv.our_cost_usd:,.2f} of measured spend is attributed to captured discussions, "
            f"out of ${dv.independent_cost_usd:,.2f} total"
        )
        print(
            f"  => captured discussions cover {coverage:.1f}% of measured AI spend "
            "(the rest is activity outside any discussion window, not an error)"
        )
        return
    arrow = {"ours_higher": "higher than", "ours_lower": "lower than", None: "exactly matches"}[
        dv.direction
    ]
    pct = "0.00%" if dv.divergence_pct == 0.0 else f"{dv.divergence_pct:+.2f}%"
    print(
        f"  our estimate ${dv.our_cost_usd:,.2f} is {arrow} the independent "
        f"${dv.independent_cost_usd:,.2f} ({pct})"
    )
    print(f"  source: {dv.source_label}")


def _print_report(
    lev: LeverageResult, attribution: DivergenceResult, pricing_check: DivergenceResult
) -> None:
    """Print both A3 metrics with their honesty caveats."""
    _print_leverage(lev)
    _print_divergence("Estimate cross-check - attribution", attribution)
    _print_divergence("Estimate cross-check - pricing (OpenTelemetry)", pricing_check)


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Report value-vs-subscription leverage + estimate cross-check (telemetry A3)."
    )
    parser.add_argument("--since", default=None, help="Ignore messages before YYYY-MM-DD (UTC).")
    parser.add_argument(
        "--subscription", default=None, help="Path to the subscription-fee YAML config."
    )
    parser.add_argument("--otel", default=None, help="Path to an OTel export JSONL file.")
    args = parser.parse_args()

    analyze_value(
        since=itu.parse_since(args.since),
        subscription_path=Path(args.subscription) if args.subscription else None,
        otel_path=Path(args.otel) if args.otel else OTEL_EXPORT_PATH,
    )


if __name__ == "__main__":
    main()
