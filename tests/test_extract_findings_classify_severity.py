"""Tests for AC2 (new scaffold boilerplate patterns) and AC3 (_classify_severity rework).

AC2: R2.2 broadened _is_verdict_boilerplate — new scaffold categories must be detected,
     and category (d) patterns must NOT match 'validation'/'pass' as ordinary English.
AC3: R2.3 reworked _classify_severity — explicit markers, body-isolation, highest-tier-wins.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

TEMPLATE_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts.extract_findings import _classify_severity, _is_verdict_boilerplate  # noqa: E402

# ---------------------------------------------------------------------------
# AC2 — new scaffold boilerplate patterns (R2.2)
# ---------------------------------------------------------------------------

_NEW_SCAFFOLD_BOILERPLATE = [
    # (a) Markdown section headers
    "## Findings",
    "### Verdict",
    "## Summary",
    "## Recommendations",
    "## Blocking",
    "## Advisories",
    # (b) Finding-count summaries
    "8 findings (1 HIGH blocking, 7 advisory)",
    "3 findings",
    # (c) Per-agent review headers
    "Security Review: 5 findings",
    "QA Review: 5 findings",
    "Architecture Review (confidence: 0.91):",
    "Performance Review:",
    "Independent-Perspective Review:",
    # (d) Process-scaffold lines
    "Validation pass complete",
    "Guided walkthrough for scripts/extract_findings.py",
    "Walkthrough for src/api.py",
    "Scan complete",
]

# These must NOT be filtered (the new patterns must not over-reach into ordinary prose).
_STILL_SUBSTANTIVE = [
    # category (d): ordinary English "validation" / "pass" mid-sentence
    "Missing validation on the discussion_id parameter allows path traversal",
    "Tests fail when the DB path is missing — the FileNotFoundError is unhandled",
    # Existing _SUBSTANTIVE_SUMMARIES must remain unaffected
    "REVISE: tests/ classification gap — /review required for tests changes",
    "APPROVE: All subprocess calls use list-form arguments (no shell=True)",
    "Race condition in the connection pool under concurrent writes",
    "FAIL: coverage dropped below the 80% threshold on the new module",
]


@pytest.mark.parametrize("summary", _NEW_SCAFFOLD_BOILERPLATE)
def test_new_scaffold_boilerplate_is_detected(summary: str) -> None:
    """AC2: new R2.2 scaffold categories return True from _is_verdict_boilerplate."""
    assert _is_verdict_boilerplate(summary) is True


@pytest.mark.parametrize("summary", _STILL_SUBSTANTIVE)
def test_new_scaffold_does_not_over_filter_substantive(summary: str) -> None:
    """AC2: category (d) patterns do not match 'validation'/'pass' as ordinary English."""
    assert _is_verdict_boilerplate(summary) is False


# ---------------------------------------------------------------------------
# AC3 — _classify_severity rework
# ---------------------------------------------------------------------------


def test_explicit_severity_marker_wins_over_heuristics() -> None:
    """AC3a: explicit 'Severity: HIGH' marker takes precedence over keyword heuristics."""
    content = "Severity: HIGH\nThis finding mentions injection in passing — no real risk."
    summary = "This finding mentions injection in passing — no real risk."
    assert _classify_severity(content, summary) == "high"


def test_explicit_critical_bracket_marker_parsed() -> None:
    """AC3a: [CRITICAL] bracket-form marker is parsed and trusted."""
    content = "[CRITICAL] Authentication bypass via unsanitized header"
    summary = "Authentication bypass via unsanitized header"
    assert _classify_severity(content, summary) == "critical"


@pytest.mark.regression
def test_body_injection_does_not_force_critical_when_summary_benign() -> None:
    """AC3b: full body mentioning 'injection' does not classify critical when summary is benign.

    Under the old code (any(p in content_lower for p in patterns)), any event body
    containing the word 'injection' anywhere — even "no injection risk" — was classified
    critical. This test would FAIL under that logic.
    """
    content = "No injection vulnerability was found in this path. The auth code is safe."
    summary = "No vulnerability was found in this path"
    result = _classify_severity(content, summary)
    assert result != "critical", f"Expected not-critical, got {result!r}"


def test_race_condition_in_summary_is_high() -> None:
    """AC3c: 'race condition' in summary maps to high severity."""
    summary = "Race condition in the connection pool under concurrent writes"
    assert _classify_severity(summary, summary) == "high"


def test_unhandled_error_in_summary_is_high() -> None:
    """AC3c: 'unhandled error' in summary maps to high."""
    # Note: "data loss" would escalate to critical — use a clean high-tier summary.
    summary = "Unhandled error in the retry loop leaves the connection pool in a bad state"
    assert _classify_severity(summary, summary) == "high"


def test_default_medium_when_no_match() -> None:
    """AC3: default to medium when neither marker nor keyword matches."""
    assert (
        _classify_severity("Improve the docstring for clarity.", "Improve the docstring")
        == "medium"
    )


def test_explicit_medium_marker_wins_over_high_body_keyword() -> None:
    """AC3a: '(severity: medium)' marker wins even when body contains a high-tier keyword."""
    content = (
        "(severity: medium) The error handling path could be cleaner; no race condition risk."
    )
    summary = "The error handling path could be cleaner"
    assert _classify_severity(content, summary) == "medium"


def test_bold_severity_marker_standalone_parsed() -> None:
    """**HIGH** (no trailing colon/whitespace) is recognized as an explicit marker.

    Regression guard: the original _EXPLICIT_SEVERITY_RE terminal (?:\\]|\\*{0,2}[:\\s]|$)
    required a colon or whitespace after the closing stars, so bare **HIGH** at
    end-of-string was silently missed. Fixed in ADR-0022 by allowing ($) in the
    closing group.
    """
    assert _classify_severity("**HIGH**", "**HIGH**") == "high"
    assert _classify_severity("**CRITICAL**", "**CRITICAL**") == "critical"


@pytest.mark.regression
@pytest.mark.parametrize(
    ("content", "expected"),
    [
        # qa F2 fold (DISC-20260612-144008): every documented marker form, pinned.
        ("**HIGH**: title text follows", "high"),
        ("*LOW*: cosmetic nit", "low"),
        ("severity=medium", "medium"),
        ("Severity: HIGH", "high"),
        ("[CRITICAL] auth bypass", "critical"),
        ("[HIGH: detail inside brackets]", "high"),
        # Trailing-punctuation forms — silently unparsed before the
        # REV DISC-20260612-144008 closing-class widening.
        ("(severity: medium)", "medium"),
        ("Rated Severity: high, fix before merge", "high"),
        ("severity: low.", "low"),
    ],
)
def test_explicit_marker_form_variants_parse(content: str, expected: str) -> None:
    """qa F2: each marker form the regex claims to support has a pinning case.

    A benign summary is passed so a regex miss falls through to default-medium —
    any non-medium expectation therefore proves the MARKER matched, not a keyword.
    """
    assert _classify_severity(content, "benign words only") == expected


def test_highest_tier_wins_when_summary_has_multiple_tier_keywords() -> None:
    """qa F5: with no explicit marker, the highest matching tier wins.

    'security' alone maps critical-tier keywords? No — 'race condition' is high;
    'minor' is info-tier. A summary carrying both must classify at the higher tier.
    """
    summary = "Race condition in the pool; a minor cleanup is also possible"
    assert _classify_severity(summary, summary) == "high"
