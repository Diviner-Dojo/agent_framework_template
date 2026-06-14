"""Telemetry & Oversight — Layer A pure logic (pricing + cost aggregation).

This package holds the *pure*, side-effect-free logic of the telemetry
component so it is fully unit-testable and counted by the coverage gate. The
I/O orchestration (transcript scanning, SQLite writes) lives in
``scripts/telemetry/`` behind the transport-fidelity boundary.

See docs/sprints/SPEC-20260605-211756-telemetry-oversight.md and ADR-0013.
"""

from src.telemetry.value import (
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

__all__ = [
    "FLAW_ATTRIBUTION",
    "FLAW_PRICING",
    "DivergenceResult",
    "IndependentEstimate",
    "LeverageResult",
    "SubscriptionFee",
    "cross_check",
    "leverage",
    "load_subscription_fee",
]
