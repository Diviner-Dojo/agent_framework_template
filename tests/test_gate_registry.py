"""Tests for scripts/education/gate_registry.py."""

from __future__ import annotations

import copy
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from scripts.education.gate_registry import (
    DEFAULT_REGISTRY_PATH,
    add_gate,
    backlog_summary,
    build_parser,
    clear_command_for,
    clear_gate,
    get_gate,
    list_gates,
    load_registry,
    main,
    mark_clear_eligible,
    re_defer_gate,
    read_header,
    save_registry,
    validate_registry,
)

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "education" / "gate_registry.py"


def _valid_gate(gate_id: str = "EDU-20260610-unit-4-1", status: str = "open") -> dict[str, Any]:
    """Return a minimal valid gate mapping."""
    cleared_by = None
    if status == "cleared":
        cleared_by = {
            "session_id": "QUIZ-1",
            "discussion_id": "DISC-1",
            "cleared_at": "2026-06-11T00:00:00+00:00",
        }
    return {
        "gate_id": gate_id,
        "created_at": "2026-06-10",
        "origin": "REV-20260610-012629",
        "scope": {"files": ["src/telemetry/dashboard.py"], "adrs": ["ADR-0020"], "spec": None},
        "reason_deferred": "deferred to next interactive session",
        "status": status,
        "cleared_by": cleared_by,
    }


def _valid_registry(gates: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Return a valid registry mapping."""
    return {"version": 1, "gates": gates if gates is not None else [_valid_gate()]}


@pytest.fixture()
def registry_path(tmp_path: Path) -> Path:
    """Write a valid registry to a temp file and return its path."""
    path = tmp_path / "gates.yaml"
    save_registry(_valid_registry(), path)
    return path


# --------------------------------------------------------------------------- #
# load / validate — happy path
# --------------------------------------------------------------------------- #
class TestLoadValidateHappyPath:
    def test_round_trip(self, registry_path: Path) -> None:
        reg = load_registry(registry_path)
        assert reg["version"] == 1
        assert len(reg["gates"]) == 1
        assert reg["gates"][0]["gate_id"] == "EDU-20260610-unit-4-1"

    def test_seeded_registry_loads(self) -> None:
        """The real seeded gates.yaml passes the loader/validator."""

        reg = load_registry(DEFAULT_REGISTRY_PATH)
        ids = {g["gate_id"] for g in reg["gates"]}
        assert "EDU-20260610-unit-4-1" in ids
        assert "EDU-20260627-d2-backflow-patterns" in ids
        # Every gate carries a valid status. This line originally read
        # `all(status == "open")` — a snapshot of the seeded file posing as an
        # invariant, which went red the first time `clear` was used for real
        # (EDU-20260810-wave3-sliced, cleared by the developer 2026-08-10).
        # Clearing is the registry working, not a corruption.
        assert all(g["status"] in {"open", "cleared"} for g in reg["gates"])
        # A cleared gate must carry its clearing provenance, not just the label —
        # stronger than the line it replaces for the arm that now exists.
        for g in reg["gates"]:
            if g["status"] == "cleared":
                cleared_by = g.get("cleared_by") or {}
                assert cleared_by.get("session_id") and cleared_by.get("discussion_id"), (
                    f"{g['gate_id']} is cleared but carries no session/discussion provenance"
                )

    def test_validate_registry_returns_same_object(self) -> None:
        reg = _valid_registry()
        assert validate_registry(reg) is reg


# --------------------------------------------------------------------------- #
# validation failure modes
# --------------------------------------------------------------------------- #
class TestValidationFailures:
    def test_root_not_mapping(self) -> None:
        with pytest.raises(ValueError, match="root must be a mapping"):
            validate_registry([1, 2, 3])

    def test_missing_version(self) -> None:
        with pytest.raises(ValueError, match="missing required key: version"):
            validate_registry({"gates": []})

    def test_missing_gates(self) -> None:
        with pytest.raises(ValueError, match="missing required key: gates"):
            validate_registry({"version": 1})

    def test_non_int_version(self) -> None:
        with pytest.raises(ValueError, match="version must be an int"):
            validate_registry({"version": "1", "gates": []})

    def test_bool_version_rejected(self) -> None:
        # bool subclasses int — must be rejected.
        with pytest.raises(ValueError, match="version must be an int"):
            validate_registry({"version": True, "gates": []})

    def test_gates_not_list(self) -> None:
        with pytest.raises(ValueError, match="gates must be a list"):
            validate_registry({"version": 1, "gates": {}})

    def test_gate_not_mapping(self) -> None:
        with pytest.raises(ValueError, match="gate must be a mapping"):
            validate_registry({"version": 1, "gates": ["nope"]})

    def test_missing_required_gate_key(self) -> None:
        gate = _valid_gate()
        del gate["origin"]
        with pytest.raises(ValueError, match="missing required keys.*origin"):
            validate_registry(_valid_registry([gate]))

    def test_unknown_gate_key(self) -> None:
        gate = _valid_gate()
        gate["bogus"] = 1
        with pytest.raises(ValueError, match="unknown keys.*bogus"):
            validate_registry(_valid_registry([gate]))

    def test_bad_gate_id_charset(self) -> None:
        gate = _valid_gate(gate_id="bad id!")
        with pytest.raises(ValueError, match="invalid gate_id"):
            validate_registry(_valid_registry([gate]))

    def test_bad_status_enum(self) -> None:
        gate = _valid_gate()
        gate["status"] = "closed"
        with pytest.raises(ValueError, match="invalid status"):
            validate_registry(_valid_registry([gate]))

    def test_duplicate_gate_id(self) -> None:
        gate1 = _valid_gate()
        gate2 = _valid_gate()
        with pytest.raises(ValueError, match="duplicate gate_id"):
            validate_registry(_valid_registry([gate1, gate2]))

    def test_non_str_created_at(self) -> None:
        gate = _valid_gate()
        gate["created_at"] = 20260610
        with pytest.raises(ValueError, match="created_at must be a string"):
            validate_registry(_valid_registry([gate]))

    def test_non_str_branch(self) -> None:
        gate = _valid_gate()
        gate["branch"] = 123
        with pytest.raises(ValueError, match="branch must be a string"):
            validate_registry(_valid_registry([gate]))

    def test_scope_not_mapping(self) -> None:
        gate = _valid_gate()
        gate["scope"] = ["files"]
        with pytest.raises(ValueError, match="scope must be a mapping"):
            validate_registry(_valid_registry([gate]))

    def test_scope_missing_key(self) -> None:
        gate = _valid_gate()
        del gate["scope"]["spec"]
        with pytest.raises(ValueError, match="scope missing required keys.*spec"):
            validate_registry(_valid_registry([gate]))

    def test_scope_unknown_key(self) -> None:
        gate = _valid_gate()
        gate["scope"]["extra"] = 1
        with pytest.raises(ValueError, match="scope has unknown keys.*extra"):
            validate_registry(_valid_registry([gate]))

    def test_scope_files_not_list(self) -> None:
        gate = _valid_gate()
        gate["scope"]["files"] = "a.py"
        with pytest.raises(ValueError, match="scope.files must be a list"):
            validate_registry(_valid_registry([gate]))

    def test_scope_adrs_not_list(self) -> None:
        gate = _valid_gate()
        gate["scope"]["adrs"] = "ADR-0020"
        with pytest.raises(ValueError, match="scope.adrs must be a list"):
            validate_registry(_valid_registry([gate]))

    def test_scope_spec_bad_type(self) -> None:
        gate = _valid_gate()
        gate["scope"]["spec"] = 42
        with pytest.raises(ValueError, match="scope.spec must be a string or null"):
            validate_registry(_valid_registry([gate]))

    def test_cleared_status_requires_cleared_by(self) -> None:
        gate = _valid_gate(status="cleared")
        gate["cleared_by"] = None
        with pytest.raises(ValueError, match="requires a cleared_by record"):
            validate_registry(_valid_registry([gate]))

    def test_cleared_by_not_mapping(self) -> None:
        gate = _valid_gate()
        gate["cleared_by"] = "someone"
        with pytest.raises(ValueError, match="cleared_by must be a mapping or null"):
            validate_registry(_valid_registry([gate]))

    def test_cleared_by_missing_keys(self) -> None:
        gate = _valid_gate(status="cleared")
        gate["cleared_by"] = {"session_id": "s"}
        with pytest.raises(ValueError, match="cleared_by missing keys"):
            validate_registry(_valid_registry([gate]))

    def test_cleared_by_unknown_keys(self) -> None:
        gate = _valid_gate(status="cleared")
        gate["cleared_by"]["who"] = "x"
        with pytest.raises(ValueError, match="cleared_by has unknown keys.*who"):
            validate_registry(_valid_registry([gate]))

    def test_load_empty_file(self, tmp_path: Path) -> None:
        path = tmp_path / "empty.yaml"
        path.write_text("", encoding="utf-8")
        with pytest.raises(ValueError, match="empty"):
            load_registry(path)

    def test_load_missing_file(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_registry(tmp_path / "nope.yaml")

    def test_load_corrupt_yaml(self, tmp_path: Path) -> None:
        path = tmp_path / "corrupt.yaml"
        path.write_text("version: 1\ngates: [unclosed\n  - :bad", encoding="utf-8")
        with pytest.raises(ValueError, match="not valid YAML"):
            load_registry(path)


# --------------------------------------------------------------------------- #
# add / clear / re-defer transitions
# --------------------------------------------------------------------------- #
class TestTransitions:
    def test_add_gate(self) -> None:
        reg = _valid_registry([])
        gate = add_gate(
            reg,
            gate_id="EDU-20260627-d2-backflow-patterns",
            created_at="2026-06-27",
            origin="docs/education/WALKTHROUGH-20260627-d2-backflow-patterns.md",
            reason_deferred="awaiting explain-back",
            adrs=["ADR-0022", "ADR-0023"],
            branch="feat/d2-backflow-patterns",
        )
        assert gate["branch"] == "feat/d2-backflow-patterns"
        assert gate["scope"]["files"] == []
        assert gate["scope"]["adrs"] == ["ADR-0022", "ADR-0023"]
        assert gate["cleared_by"] is None
        assert len(reg["gates"]) == 1
        validate_registry(reg)

    def test_add_duplicate_rejected(self) -> None:
        reg = _valid_registry()
        with pytest.raises(ValueError, match="already exists"):
            add_gate(
                reg,
                gate_id="EDU-20260610-unit-4-1",
                created_at="2026-06-10",
                origin="REV",
                reason_deferred="dup",
            )

    def test_add_bad_id_rejected(self) -> None:
        reg = _valid_registry([])
        with pytest.raises(ValueError, match="invalid gate_id"):
            add_gate(
                reg,
                gate_id="bad id",
                created_at="2026-06-10",
                origin="REV",
                reason_deferred="x",
            )

    def test_clear_gate(self) -> None:
        reg = _valid_registry()
        gate, changed = clear_gate(reg, "EDU-20260610-unit-4-1", "QUIZ-9", "DISC-9")
        assert changed is True
        assert gate["status"] == "cleared"
        assert gate["cleared_by"]["session_id"] == "QUIZ-9"
        assert gate["cleared_by"]["discussion_id"] == "DISC-9"
        assert gate["cleared_by"]["cleared_at"]  # auto-filled
        validate_registry(reg)

    def test_clear_gate_explicit_timestamp(self) -> None:
        reg = _valid_registry()
        _gate, changed = clear_gate(
            reg, "EDU-20260610-unit-4-1", "S", "D", cleared_at="2026-07-01T12:00:00+00:00"
        )
        assert changed is True
        assert get_gate(reg, "EDU-20260610-unit-4-1")["cleared_by"]["cleared_at"] == (
            "2026-07-01T12:00:00+00:00"
        )

    def test_double_clear_is_idempotent_noop(self) -> None:
        reg = _valid_registry()
        gate1, changed1 = clear_gate(reg, "EDU-20260610-unit-4-1", "S1", "D1")
        assert changed1 is True
        original = copy.deepcopy(gate1["cleared_by"])
        gate2, changed2 = clear_gate(reg, "EDU-20260610-unit-4-1", "S2", "D2")
        assert changed2 is False
        # The original cleared_by must be untouched (no overwrite by the second call).
        assert gate2["cleared_by"] == original

    def test_clear_unknown_gate_raises(self) -> None:
        reg = _valid_registry()
        with pytest.raises(KeyError, match="no gate with gate_id"):
            clear_gate(reg, "EDU-does-not-exist", "S", "D")

    def test_re_defer(self) -> None:
        reg = _valid_registry([_valid_gate(status="cleared")])
        gate = re_defer_gate(reg, "EDU-20260610-unit-4-1", "reopened: scope changed")
        assert gate["status"] == "re-deferred"
        assert gate["reason_deferred"] == "reopened: scope changed"
        assert gate["cleared_by"] is None
        validate_registry(reg)

    def test_re_defer_unknown_gate_raises(self) -> None:
        reg = _valid_registry()
        with pytest.raises(KeyError):
            re_defer_gate(reg, "nope", "x")

    def test_clear_then_re_defer_then_clear(self) -> None:
        reg = _valid_registry()
        clear_gate(reg, "EDU-20260610-unit-4-1", "S1", "D1")
        re_defer_gate(reg, "EDU-20260610-unit-4-1", "reopened")
        assert get_gate(reg, "EDU-20260610-unit-4-1")["status"] == "re-deferred"
        _gate, changed = clear_gate(reg, "EDU-20260610-unit-4-1", "S2", "D2")
        assert changed is True
        assert get_gate(reg, "EDU-20260610-unit-4-1")["status"] == "cleared"


# --------------------------------------------------------------------------- #
# query
# --------------------------------------------------------------------------- #
class TestQuery:
    def test_list_all(self) -> None:
        reg = _valid_registry([_valid_gate("g1"), _valid_gate("g2", status="cleared")])
        assert len(list_gates(reg)) == 2

    def test_list_filtered(self) -> None:
        reg = _valid_registry([_valid_gate("g1"), _valid_gate("g2", status="cleared")])
        open_gates = list_gates(reg, status="open")
        assert [g["gate_id"] for g in open_gates] == ["g1"]

    def test_list_bad_status(self) -> None:
        reg = _valid_registry()
        with pytest.raises(ValueError, match="invalid status filter"):
            list_gates(reg, status="bogus")

    def test_get_gate_missing(self) -> None:
        reg = _valid_registry()
        with pytest.raises(KeyError):
            get_gate(reg, "missing")


# --------------------------------------------------------------------------- #
# atomic save
# --------------------------------------------------------------------------- #
class TestAtomicSave:
    def test_save_creates_no_stray_temp(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        save_registry(_valid_registry(), path)
        assert path.exists()
        # No leftover temp files in the directory.
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "gates.yaml"]
        assert leftovers == []

    def test_save_is_atomic_replace(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """If os.replace fails, the original file is preserved and no temp remains."""
        import scripts.education.gate_registry as mod

        path = tmp_path / "gates.yaml"
        save_registry(_valid_registry([_valid_gate("original")]), path)

        def _boom(src: str, dst: str) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr(mod.os, "replace", _boom)
        with pytest.raises(OSError, match="replace failed"):
            save_registry(_valid_registry([_valid_gate("new")]), path)
        # Original content intact; no stray temp file.
        reg = load_registry(path)
        assert reg["gates"][0]["gate_id"] == "original"
        leftovers = [p.name for p in tmp_path.iterdir() if p.name != "gates.yaml"]
        assert leftovers == []

    def test_save_rejects_invalid_registry(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        bad = {"version": 1, "gates": [_valid_gate(gate_id="bad id")]}
        with pytest.raises(ValueError):
            save_registry(bad, path)
        assert not path.exists()

    def test_saved_yaml_quotes_dates_as_strings(self, tmp_path: Path) -> None:
        """created_at must persist as a string, not a YAML date scalar."""
        path = tmp_path / "gates.yaml"
        save_registry(_valid_registry(), path)
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert isinstance(raw["gates"][0]["created_at"], str)


# --------------------------------------------------------------------------- #
# comment-header preservation
#
# yaml.safe_dump cannot round-trip comments. Before read_header() existed, the first
# `clear` on the live registry deleted every line above `version:`, taking the seeding
# provenance with it. Reproduced 2026-08-09 against commit 31bfe09 on scratch copies: that
# commit's 16-line header went to 0 (the command is in read_header's docstring). 16 is that
# commit's header length, not a constant -- the invariant these tests pin is that ANY
# header survives a write, and they pin it without needing git. They fail if that regresses.
# --------------------------------------------------------------------------- #
HEADER = "# Education Gate Registry\n#\n# Seeded from archaeology; do not lose this.\n"


class TestHeaderPreservation:
    def test_read_header_returns_the_leading_comment_block(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text(HEADER + "version: 1\ngates: []\n", encoding="utf-8")
        assert read_header(path) == HEADER

    def test_read_header_on_missing_file_is_empty(self, tmp_path: Path) -> None:
        assert read_header(tmp_path / "nope.yaml") == ""

    def test_read_header_does_not_invent_one(self, tmp_path: Path) -> None:
        """A file with no leading comment must not gain a header on save."""
        path = tmp_path / "gates.yaml"
        path.write_text("version: 1\ngates: []\n", encoding="utf-8")
        assert read_header(path) == ""

    def test_read_header_ignores_comments_below_the_body(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text("version: 1\n# not a header\ngates: []\n", encoding="utf-8")
        assert read_header(path) == ""

    def test_save_preserves_an_existing_header(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text(HEADER + "version: 1\ngates: []\n", encoding="utf-8")
        save_registry(_valid_registry(), path)
        assert path.read_text(encoding="utf-8").startswith(HEADER)

    def test_save_does_not_duplicate_the_header(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text(HEADER + "version: 1\ngates: []\n", encoding="utf-8")
        for _ in range(3):
            save_registry(_valid_registry(), path)
        assert path.read_text(encoding="utf-8").count("# Education Gate Registry") == 1

    def test_saved_file_with_header_still_loads(self, tmp_path: Path) -> None:
        path = tmp_path / "gates.yaml"
        path.write_text(HEADER + "version: 1\ngates: []\n", encoding="utf-8")
        save_registry(_valid_registry(), path)
        assert load_registry(path)["gates"][0]["gate_id"] == _valid_gate()["gate_id"]

    def test_clear_via_cli_preserves_the_header(self, tmp_path: Path) -> None:
        """The end-to-end shape: the documented `clear` command is non-destructive."""
        path = tmp_path / "gates.yaml"
        path.write_text(HEADER + "version: 1\ngates: []\n", encoding="utf-8")
        save_registry(_valid_registry(), path)
        rc = main(
            [
                "--registry",
                str(path),
                "clear",
                "--gate-id",
                _valid_gate()["gate_id"],
                "--session-id",
                "QUIZ-1",
                "--discussion-id",
                "DISC-1",
            ]
        )
        assert rc == 0
        text = path.read_text(encoding="utf-8")
        assert text.startswith(HEADER)
        assert load_registry(path)["gates"][0]["status"] == "cleared"


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
class TestCli:
    def test_build_parser_smoke(self) -> None:
        parser = build_parser()
        args = parser.parse_args(["list", "--status", "open"])
        assert args.command == "list"
        assert args.status == "open"

    def test_cli_list(self, registry_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(["--registry", str(registry_path), "list"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "EDU-20260610-unit-4-1" in out
        assert "1 gate(s)." in out

    def test_cli_list_status_filter_empty(
        self, registry_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(["--registry", str(registry_path), "list", "--status", "cleared"])
        assert rc == 0
        assert "No gates (status=cleared)." in capsys.readouterr().out

    def test_cli_add(self, registry_path: Path) -> None:
        rc = main(
            [
                "--registry",
                str(registry_path),
                "add",
                "--gate-id",
                "EDU-20260701-new",
                "--created-at",
                "2026-07-01",
                "--origin",
                "REV-x",
                "--reason",
                "new deferral",
                "--file",
                "src/a.py",
                "--adr",
                "ADR-0099",
                "--spec",
                "SPEC-1",
            ]
        )
        assert rc == 0
        reg = load_registry(registry_path)
        gate = get_gate(reg, "EDU-20260701-new")
        assert gate["scope"]["files"] == ["src/a.py"]
        assert gate["scope"]["adrs"] == ["ADR-0099"]
        assert gate["scope"]["spec"] == "SPEC-1"

    def test_cli_clear_and_idempotent(
        self, registry_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(
            [
                "--registry",
                str(registry_path),
                "clear",
                "--gate-id",
                "EDU-20260610-unit-4-1",
                "--session-id",
                "QUIZ-1",
                "--discussion-id",
                "DISC-1",
            ]
        )
        assert rc == 0
        assert "Cleared gate" in capsys.readouterr().out
        assert get_gate(load_registry(registry_path), "EDU-20260610-unit-4-1")["status"] == (
            "cleared"
        )
        # Second clear is a no-op.
        rc2 = main(
            [
                "--registry",
                str(registry_path),
                "clear",
                "--gate-id",
                "EDU-20260610-unit-4-1",
                "--session-id",
                "QUIZ-2",
                "--discussion-id",
                "DISC-2",
            ]
        )
        assert rc2 == 0
        assert "already cleared" in capsys.readouterr().out

    def test_cli_re_defer(self, registry_path: Path) -> None:
        rc = main(
            [
                "--registry",
                str(registry_path),
                "re-defer",
                "--gate-id",
                "EDU-20260610-unit-4-1",
                "--reason",
                "reopened",
            ]
        )
        assert rc == 0
        gate = get_gate(load_registry(registry_path), "EDU-20260610-unit-4-1")
        assert gate["status"] == "re-deferred"
        assert gate["reason_deferred"] == "reopened"

    def test_cli_error_returns_2(
        self, registry_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = main(
            [
                "--registry",
                str(registry_path),
                "clear",
                "--gate-id",
                "EDU-missing",
                "--session-id",
                "S",
                "--discussion-id",
                "D",
            ]
        )
        assert rc == 2
        assert "error:" in capsys.readouterr().err

    def test_cli_via_subprocess(self, registry_path: Path) -> None:
        """End-to-end invocation of the module as a script."""
        result = subprocess.run(
            [sys.executable, str(MODULE_PATH), "--registry", str(registry_path), "list"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        assert "EDU-20260610-unit-4-1" in result.stdout


# --------------------------------------------------------------------------- #
# clear_eligible — the additive ADR-0035 marker (F1) and its command (F6)
#
# "I clear it": the ingest may not clear, so eligibility must live SOMEWHERE
# durable or the registry cannot tell paid-but-unclaimed from unpaid debt. It
# lives here, as an optional additive gate field; status stays open and
# cleared/cleared_by remain reachable only through the developer's clear.
# --------------------------------------------------------------------------- #
def _eligible_gate(gate_id: str = "EDU-20260610-unit-4-1") -> dict[str, Any]:
    gate = _valid_gate(gate_id)
    gate["clear_eligible"] = {
        "session_id": "GATE-S1",
        "discussion_id": "DISC-S1",
        "eligible_at": "2026-08-11T00:00:00+00:00",
    }
    return gate


class TestClearEligibleValidation:
    def test_marker_accepted_on_open_gate(self) -> None:
        validate_registry(_valid_registry([_eligible_gate()]))

    def test_marker_accepted_on_re_deferred_gate(self) -> None:
        gate = _eligible_gate()
        gate["status"] = "re-deferred"
        validate_registry(_valid_registry([gate]))

    def test_marker_rejected_on_cleared_gate(self) -> None:
        """Eligible is NOT cleared — a marker surviving the clear is the drift risk."""
        gate = _valid_gate(status="cleared")
        gate["clear_eligible"] = {
            "session_id": "S",
            "discussion_id": "D",
            "eligible_at": "2026-08-11T00:00:00+00:00",
        }
        with pytest.raises(ValueError, match="cleared gate may not carry"):
            validate_registry(_valid_registry([gate]))

    def test_marker_missing_key_rejected(self) -> None:
        gate = _eligible_gate()
        del gate["clear_eligible"]["eligible_at"]
        with pytest.raises(ValueError, match="clear_eligible missing keys"):
            validate_registry(_valid_registry([gate]))

    def test_marker_unknown_key_rejected(self) -> None:
        gate = _eligible_gate()
        gate["clear_eligible"]["who"] = "x"
        with pytest.raises(ValueError, match="clear_eligible has unknown keys"):
            validate_registry(_valid_registry([gate]))

    def test_marker_non_mapping_rejected(self) -> None:
        gate = _valid_gate()
        gate["clear_eligible"] = "yes"
        with pytest.raises(ValueError, match="clear_eligible must be a mapping or null"):
            validate_registry(_valid_registry([gate]))

    def test_marker_non_string_value_rejected(self) -> None:
        gate = _eligible_gate()
        gate["clear_eligible"]["session_id"] = 7
        with pytest.raises(ValueError, match="clear_eligible.session_id must be a string"):
            validate_registry(_valid_registry([gate]))


class TestMarkClearEligible:
    @pytest.mark.regression
    def test_mark_sets_marker_and_touches_nothing_else(self) -> None:
        """The additive contract: status/cleared_by unchanged, marker present."""
        reg = _valid_registry()
        gate, changed = mark_clear_eligible(reg, "EDU-20260610-unit-4-1", "S1", "D1")
        assert changed is True
        assert gate["status"] == "open"
        assert gate["cleared_by"] is None
        assert gate["clear_eligible"]["session_id"] == "S1"
        assert gate["clear_eligible"]["discussion_id"] == "D1"
        assert gate["clear_eligible"]["eligible_at"]
        validate_registry(reg)

    def test_later_session_overwrites(self) -> None:
        reg = _valid_registry()
        mark_clear_eligible(reg, "EDU-20260610-unit-4-1", "S1", "D1")
        mark_clear_eligible(reg, "EDU-20260610-unit-4-1", "S2", "D2")
        assert get_gate(reg, "EDU-20260610-unit-4-1")["clear_eligible"]["session_id"] == "S2"

    def test_noop_on_cleared_gate(self) -> None:
        reg = _valid_registry([_valid_gate(status="cleared")])
        gate, changed = mark_clear_eligible(reg, "EDU-20260610-unit-4-1", "S", "D")
        assert changed is False
        assert "clear_eligible" not in gate
        validate_registry(reg)

    def test_unknown_gate_raises(self) -> None:
        with pytest.raises(KeyError):
            mark_clear_eligible(_valid_registry(), "nope", "S", "D")

    @pytest.mark.regression
    def test_clear_removes_the_marker(self) -> None:
        """cleared_by subsumes it; a surviving marker would read as a second claim."""
        reg = _valid_registry([_eligible_gate()])
        gate, changed = clear_gate(reg, "EDU-20260610-unit-4-1", "GATE-S1", "DISC-S1")
        assert changed is True
        assert "clear_eligible" not in gate
        validate_registry(reg)

    @pytest.mark.regression
    def test_re_defer_removes_the_marker(self) -> None:
        """A re-deferred gate is unpaid again; a stale marker invites a bad paste."""
        reg = _valid_registry([_eligible_gate()])
        gate = re_defer_gate(reg, "EDU-20260610-unit-4-1", "reopened")
        assert "clear_eligible" not in gate
        validate_registry(reg)


class TestClearCommandFor:
    def test_no_marker_no_command(self) -> None:
        assert clear_command_for(_valid_gate()) is None

    def test_default_registry_omits_the_flag(self) -> None:
        cmd = clear_command_for(_eligible_gate(), DEFAULT_REGISTRY_PATH)
        assert cmd == (
            "python scripts/education/gate_registry.py clear "
            "--gate-id EDU-20260610-unit-4-1 --session-id GATE-S1 --discussion-id DISC-S1"
        )
        assert clear_command_for(_eligible_gate(), None) == cmd

    @pytest.mark.regression
    def test_non_default_registry_is_pinned_and_quoted(self, tmp_path: Path) -> None:
        """F6: a command minted against another registry must never silently
        mutate the default one — and repo paths here contain spaces, so quote."""
        other = tmp_path / "gates.yaml"
        cmd = clear_command_for(_eligible_gate(), other)
        assert cmd is not None
        assert f'--registry "{other.resolve()}"' in cmd
        assert cmd.index("--registry") < cmd.index("clear --gate-id")


class TestBacklogSeparatesEligible:
    @pytest.mark.regression
    def test_eligible_gates_get_their_own_bucket(self) -> None:
        """F1: a paid gate must not render as unpaid debt in PROCESS HEALTH."""
        reg = _valid_registry([_valid_gate("EDU-unpaid"), _eligible_gate("EDU-paid")])
        lines = backlog_summary(reg, today=None)
        assert len(lines) == 6
        # The unpaid rendering counts ONLY the unpaid gate...
        assert "1 education gate(s) deferred and never cleared" in lines[0]
        assert "EDU-unpaid" in lines[0]
        # ...and the eligible bucket asks for the paste, not for re-learning.
        assert "1 education gate(s) CLEAR-ELIGIBLE" in lines[4]
        assert "EDU-paid" in lines[4]
        assert "awaiting YOUR clear" in lines[4]
        assert "list --eligible" in lines[5]

    def test_all_eligible_renders_only_the_eligible_bucket(self) -> None:
        reg = _valid_registry([_eligible_gate("EDU-paid")])
        lines = backlog_summary(reg, today=None)
        assert len(lines) == 2
        assert "CLEAR-ELIGIBLE" in lines[0]
        assert "list --eligible" in lines[1]

    def test_no_marker_rendering_is_unchanged_four_lines(self) -> None:
        lines = backlog_summary(_valid_registry([_valid_gate("EDU-a")]), today=None)
        assert len(lines) == 4


class TestCliListEligible:
    def _seeded(self, tmp_path: Path) -> Path:
        path = tmp_path / "gates.yaml"
        save_registry(
            _valid_registry([_valid_gate("EDU-unpaid"), _eligible_gate("EDU-paid")]), path
        )
        return path

    @pytest.mark.regression
    def test_list_eligible_reprints_the_developer_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """The paste is recoverable days later — eligibility does not die with the
        ingest's console (F1), and the non-default registry is pinned (F6)."""
        path = self._seeded(tmp_path)
        rc = main(["--registry", str(path), "list", "--eligible"])
        assert rc == 0
        out = capsys.readouterr().out
        assert "EDU-paid" in out
        assert "EDU-unpaid" not in out
        assert "clear --gate-id EDU-paid --session-id GATE-S1 --discussion-id DISC-S1" in out
        assert f'--registry "{path.resolve()}"' in out
        assert "developer" in out.lower()

    def test_list_eligible_empty(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = tmp_path / "gates.yaml"
        save_registry(_valid_registry([_valid_gate("EDU-unpaid")]), path)
        rc = main(["--registry", str(path), "list", "--eligible"])
        assert rc == 0
        assert "No clear-eligible gates." in capsys.readouterr().out
