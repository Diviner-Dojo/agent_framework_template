"""Tests for the Phase 4 Unit 4.1 hook-health chip (SPEC-20260610-005602).

Pure-model tests (``parse_hook_script_refs`` / ``assess_hook_health``) plus
render tests (``render_hook_health_chip`` / the ``render_live_fragment`` chip
seam). The transport loader tests (``load_hook_health``, the bounded gate-log
tail, the ``/fragments/live`` endpoint) live in ``tests/test_dashboard_server.py``
(AC-U6/AC-U7) because they exercise the IO half of the R14 split.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from src.telemetry.dashboard import render_hook_health_chip, render_live_fragment
from src.telemetry.hooks_health import (
    HOOK_HEALTH_STATUSES,
    HOOK_STATUS_MISSING_SCRIPTS,
    HOOK_STATUS_NOT_CONFIGURED,
    HOOK_STATUS_OK,
    HookConfigParse,
    HookHealthReport,
    assess_hook_health,
    parse_hook_script_refs,
)
from src.telemetry.live import empty_state

# Realistic settings fixture (spec qa F1): matcher lists, a no-matcher
# UserPromptSubmit entry, a powershell -File command form, and statusLine as a
# TOP-LEVEL SIBLING of "hooks" (the real layout — NOT nested inside it).
_REAL_SHAPE_SETTINGS = json.dumps(
    {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Write|Edit",
                    "hooks": [
                        {
                            "type": "command",
                            "command": "bash .claude/hooks/pre-tool-use-validator.sh",
                        }
                    ],
                },
                {
                    "matcher": "Bash",
                    "hooks": [
                        {"type": "command", "command": "bash .claude/hooks/pre-commit-gate.sh"}
                    ],
                },
            ],
            "UserPromptSubmit": [
                {"hooks": [{"type": "command", "command": "bash .claude/hooks/context-guard.sh"}]}
            ],
            "PreCompact": [
                {
                    "matcher": "auto|manual",
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "powershell -ExecutionPolicy Bypass -File "
                                ".claude/hooks/pre-compact.ps1"
                            ),
                        }
                    ],
                }
            ],
        },
        "statusLine": {
            "type": "command",
            "command": "bash .claude/hooks/context-statusline.sh",
        },
    }
)


def test_parse_real_layout_extracts_basenames_and_excludes_statusline() -> None:
    # AC-U1: the parser walks ONLY the "hooks" block; statusLine's script is
    # intentionally excluded from the health claim.
    parsed = parse_hook_script_refs(_REAL_SHAPE_SETTINGS)
    assert parsed.hook_count == 4
    assert parsed.script_refs == (
        "pre-tool-use-validator.sh",
        "pre-commit-gate.sh",
        "context-guard.sh",
        "pre-compact.ps1",
    )
    assert "context-statusline.sh" not in parsed.script_refs


def test_parse_powershell_and_bash_forms_extract_same_way() -> None:
    # AC-U1 (spec qa F2): the -File flag form and the bash form both yield the
    # bare basename — the pinned path-pattern strategy is form-agnostic.
    text = json.dumps(
        {
            "hooks": {
                "A": [{"hooks": [{"type": "command", "command": "bash .claude/hooks/x.sh"}]}],
                "B": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": (
                                    "powershell -ExecutionPolicy Bypass -File .claude/hooks/x.ps1"
                                ),
                            }
                        ]
                    }
                ],
            }
        }
    )
    parsed = parse_hook_script_refs(text)
    assert parsed.script_refs == ("x.sh", "x.ps1")
    assert parsed.hook_count == 2


@pytest.mark.regression
def test_parse_never_propagates_command_content() -> None:
    # Regression (spec security F1 — minimum disclosure): a command embedding
    # a token must leak NONE of it into the parse result; only the script
    # basename survives the parser.
    token = "tk-SECRETVALUE12345"
    text = json.dumps(
        {
            "hooks": {
                "PreToolUse": [
                    {
                        "hooks": [
                            {
                                "type": "command",
                                "command": f"bash .claude/hooks/notify.sh --topic {token}",
                            }
                        ]
                    }
                ]
            }
        }
    )
    parsed = parse_hook_script_refs(text)
    assert parsed.script_refs == ("notify.sh",)
    assert token not in repr(parsed)


@pytest.mark.parametrize(
    "settings_text",
    [
        None,
        "not json at all {",
        json.dumps({"hooks": None}),
        json.dumps({"hooks": {}}),
        json.dumps({"hooks": 5}),
        json.dumps({}),
        json.dumps([1, 2, 3]),
    ],
)
def test_parse_malformed_inputs_yield_not_configured_shape(settings_text: str | None) -> None:
    # AC-U2 (incl. spec qa F8 `"hooks": null`): every malformed/absent shape
    # is the honest not-configured input state — never a raise.
    assert parse_hook_script_refs(settings_text) == HookConfigParse(script_refs=(), hook_count=0)


def test_parse_command_without_script_ref_still_counts() -> None:
    # AC-U2: an inline command (no .claude/hooks/ reference) still counts
    # toward hooks_configured — the chip claims "entries configured", not
    # "scripts referenced".
    text = json.dumps({"hooks": {"A": [{"hooks": [{"type": "command", "command": "echo hi"}]}]}})
    parsed = parse_hook_script_refs(text)
    assert parsed.hook_count == 1
    assert parsed.script_refs == ()


def test_parse_deduplicates_first_seen_order() -> None:
    # AC-U3 dedup prong (spec qa F5): two commands referencing the same script
    # yield the basename once, first-seen order preserved; hook_count still
    # counts every command entry.
    text = json.dumps(
        {
            "hooks": {
                "A": [{"hooks": [{"type": "command", "command": "bash .claude/hooks/same.sh"}]}],
                "B": [
                    {"hooks": [{"type": "command", "command": "bash .claude/hooks/other.sh"}]},
                    {"hooks": [{"type": "command", "command": "bash .claude/hooks/same.sh"}]},
                ],
            }
        }
    )
    parsed = parse_hook_script_refs(text)
    assert parsed.script_refs == ("same.sh", "other.sh")
    assert parsed.hook_count == 3


def test_assess_status_mapping_covers_all_three_statuses() -> None:
    # AC-U2/AC-U3: zero hooks -> not_configured; any missing -> missing_scripts
    # (dedup carried through unchanged); none missing -> ok.
    none = assess_hook_health(HookConfigParse((), 0), (), None)
    assert none.status == HOOK_STATUS_NOT_CONFIGURED
    assert none.hooks_configured == 0
    missing = assess_hook_health(HookConfigParse(("a.sh", "b.sh"), 3), ("b.sh",), None)
    assert missing.status == HOOK_STATUS_MISSING_SCRIPTS
    assert missing.scripts_missing == ("b.sh",)
    assert missing.hooks_configured == 3
    ok = assess_hook_health(HookConfigParse(("a.sh",), 2), (), None)
    assert ok.status == HOOK_STATUS_OK
    assert set(HOOK_HEALTH_STATUSES) == {none.status, missing.status, ok.status}


@pytest.mark.regression
def test_hooks_health_module_import_graph_is_pure() -> None:
    # Regression (AC-U9, spec qa F6 + security F5): src/telemetry/hooks_health
    # must pull nothing beyond stdlib — mirrors the live.py purity guard in
    # tests/test_telemetry.py. This is what keeps the parent spec's AC3(a)
    # import allowlist trivially true for the new module.
    import importlib
    import sys

    for name in list(sys.modules):
        if name == "src.telemetry.hooks_health":
            del sys.modules[name]
    before = set(sys.modules)
    importlib.import_module("src.telemetry.hooks_health")
    pulled = set(sys.modules) - before
    forbidden_prefixes = ("scripts",)
    offenders = [
        name
        for name in pulled
        if any(name.startswith(p + ".") or name == p for p in forbidden_prefixes)
    ]
    assert offenders == [], f"hooks_health import graph leaked transport modules: {offenders}"


def _hook_report(
    status: str = HOOK_STATUS_OK,
    hooks_configured: int = 8,
    scripts_missing: tuple[str, ...] = (),
    last_gate_run: datetime | None = None,
) -> HookHealthReport:
    return HookHealthReport(
        status=status,
        hooks_configured=hooks_configured,
        scripts_missing=scripts_missing,
        last_gate_run=last_gate_run,
    )


def test_chip_ok_state_carries_count_and_narrow_recency() -> None:
    # AC-U4: ok chip carries the count, the OK label, and the NARROW recency
    # framing — the copy names the quality gate, never "hooks last fired"
    # (ADR-0020: one activity signal must not widen into an all-hooks claim).
    chip = render_hook_health_chip(
        _hook_report(last_gate_run=datetime(2026, 6, 10, 0, 30, tzinfo=UTC))
    )
    assert 'data-hook-health="ok"' in chip
    assert "Hooks: 8 configured" in chip
    assert "quality gate last ran 2026-06-10 00:30 UTC" in chip
    assert "hooks last fired" not in chip.lower()


def test_chip_missing_scripts_names_are_visible_text() -> None:
    # AC-U4 + ux checkpoint fold (WCAG 1.3.1): the missing basenames are
    # VISIBLE text, not title-attribute-only — a keyboard/touch reader gets
    # the actionable detail without hover.
    chip = render_hook_health_chip(
        _hook_report(status=HOOK_STATUS_MISSING_SCRIPTS, scripts_missing=("gone.sh", "lost.ps1"))
    )
    assert 'data-hook-health="missing_scripts"' in chip
    assert "Hooks: 2 of 8 hook scripts missing" in chip
    assert '<span class="hook-chip__missing">Missing: gone.sh, lost.ps1</span>' in chip


def test_chip_not_configured_is_honest_absence() -> None:
    # AC-U4 (ADR-0020): not_configured renders an explicit honest chip and the
    # no-run recency copy — never silence, never an error tile.
    chip = render_hook_health_chip(
        _hook_report(status=HOOK_STATUS_NOT_CONFIGURED, hooks_configured=0)
    )
    assert 'data-hook-health="not_configured"' in chip
    assert "Hooks: not configured" in chip
    assert "no quality-gate run observed" in chip


@pytest.mark.regression
def test_chip_escapes_hostile_script_name() -> None:
    # Regression (AC-U4 injection round-trip, spec security F3): escaping
    # happens INSIDE the helper — a hostile basename cannot open a tag in any
    # of the chip's interpolation sites (visible span, summary, title).
    hostile = "<script>alert(1)</script>.sh"
    chip = render_hook_health_chip(
        _hook_report(status=HOOK_STATUS_MISSING_SCRIPTS, scripts_missing=(hostile,))
    )
    assert "<script>" not in chip
    assert "&lt;script&gt;" in chip


def test_live_fragment_default_renders_no_chip() -> None:
    # AC-U5: the empty-string default is the no-chip contract — existing
    # callers and fragment tests are unaffected by the new parameter.
    fragment = render_live_fragment(empty_state())
    assert "hook-chip" not in fragment
    assert "data-hook-health" not in fragment


def test_live_fragment_chip_appears_exactly_once_and_first() -> None:
    # AC-U5 (spec qa F7): asserted with count() == 1, not `in` — and the chip
    # composes FIRST inside the section (precondition-banner placement).
    chip = render_hook_health_chip(_hook_report())
    fragment = render_live_fragment(empty_state(), hook_health_chip_html=chip)
    assert fragment.count('data-hook-health="ok"') == 1
    assert fragment.index("hook-chip") < fragment.index("runway")
