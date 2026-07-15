"""Tests for scripts/education/gate_registry.py."""

import pytest
import yaml

from scripts.education.gate_registry import (
    RegistryError,
    add_gate,
    clear_gate,
    get_gate,
    load_registry,
    next_gate_id,
    record_attempt,
    redefer_gate,
    save_registry,
    validate_registry,
)


def _minimal_registry() -> dict:
    return {
        "version": 1,
        "gates": [
            {
                "gate_id": "GATE-0001",
                "title": "Test gate",
                "created_at": "2026-07-15T00:00:00+00:00",
                "origin": "build",
                "scope": {"files": ["a.py"], "adrs": [], "spec": None},
                "reason_deferred": "testing",
                "status": "open",
                "deferrals": [],
                "attempts": [],
                "cleared_by": None,
                "cleared_at": None,
                "discussion_id": None,
            }
        ],
    }


@pytest.fixture()
def registry_path(tmp_path):
    """A valid registry file on disk."""
    path = tmp_path / "gates.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(_minimal_registry(), f)
    return path


class TestValidation:
    def test_valid_registry_passes(self):
        validate_registry(_minimal_registry())

    def test_wrong_version_rejected(self):
        registry = _minimal_registry()
        registry["version"] = 99
        with pytest.raises(RegistryError, match="version"):
            validate_registry(registry)

    def test_bad_gate_id_rejected(self):
        registry = _minimal_registry()
        registry["gates"][0]["gate_id"] = "GATE-1"
        with pytest.raises(RegistryError, match="gate_id"):
            validate_registry(registry)

    def test_duplicate_gate_id_rejected(self):
        registry = _minimal_registry()
        registry["gates"].append(dict(registry["gates"][0]))
        with pytest.raises(RegistryError, match="Duplicate"):
            validate_registry(registry)

    def test_bad_status_rejected(self):
        registry = _minimal_registry()
        registry["gates"][0]["status"] = "done"
        with pytest.raises(RegistryError, match="status"):
            validate_registry(registry)

    def test_bad_origin_rejected(self):
        registry = _minimal_registry()
        registry["gates"][0]["origin"] = "vibes"
        with pytest.raises(RegistryError, match="origin"):
            validate_registry(registry)

    def test_cleared_without_session_rejected(self):
        registry = _minimal_registry()
        registry["gates"][0]["status"] = "cleared"
        with pytest.raises(RegistryError, match="cleared_by"):
            validate_registry(registry)

    def test_missing_title_rejected(self):
        registry = _minimal_registry()
        registry["gates"][0]["title"] = "  "
        with pytest.raises(RegistryError, match="title"):
            validate_registry(registry)


class TestRoundTrip:
    def test_load_save_round_trip(self, registry_path):
        registry = load_registry(registry_path)
        save_registry(registry, registry_path)
        reloaded = load_registry(registry_path)
        assert reloaded == registry

    def test_load_missing_file(self, tmp_path):
        with pytest.raises(RegistryError, match="not found"):
            load_registry(tmp_path / "nope.yaml")

    def test_save_rejects_invalid(self, registry_path):
        registry = load_registry(registry_path)
        registry["gates"][0]["status"] = "bogus"
        with pytest.raises(RegistryError):
            save_registry(registry, registry_path)
        # File on disk is untouched (atomic write never happened).
        assert load_registry(registry_path)["gates"][0]["status"] == "open"


class TestOperations:
    def test_next_gate_id_increments(self):
        registry = _minimal_registry()
        assert next_gate_id(registry) == "GATE-0002"

    def test_add_gate(self, registry_path):
        registry = load_registry(registry_path)
        gate = add_gate(registry, "New gate", origin="review", files=["b.py"])
        assert gate["gate_id"] == "GATE-0002"
        assert gate["status"] == "open"
        save_registry(registry, registry_path)
        assert len(load_registry(registry_path)["gates"]) == 2

    def test_add_gate_bad_origin(self):
        with pytest.raises(RegistryError, match="origin"):
            add_gate(_minimal_registry(), "X", origin="nope")

    def test_add_gate_empty_title(self):
        with pytest.raises(RegistryError, match="title"):
            add_gate(_minimal_registry(), "   ")

    def test_clear_gate(self, registry_path):
        registry = load_registry(registry_path)
        gate = clear_gate(registry, "GATE-0001", "VWALK-20260715-063000", "DISC-X")
        assert gate["status"] == "cleared"
        assert gate["cleared_by"] == "VWALK-20260715-063000"
        assert gate["discussion_id"] == "DISC-X"
        save_registry(registry, registry_path)

    def test_clear_already_cleared_rejected(self):
        registry = _minimal_registry()
        clear_gate(registry, "GATE-0001", "VWALK-20260715-063000")
        with pytest.raises(RegistryError, match="already cleared"):
            clear_gate(registry, "GATE-0001", "VWALK-20260715-063001")

    def test_clear_bad_session_id(self):
        with pytest.raises(RegistryError, match="session"):
            clear_gate(_minimal_registry(), "GATE-0001", "not-a-session")

    def test_redefer_requires_reason(self):
        with pytest.raises(RegistryError, match="reason"):
            redefer_gate(_minimal_registry(), "GATE-0001", "   ")

    def test_redefer_records_history(self):
        registry = _minimal_registry()
        gate = redefer_gate(registry, "GATE-0001", "low energy today")
        assert gate["status"] == "re-deferred"
        assert gate["deferrals"][-1]["reason"] == "low energy today"

    def test_redefer_cleared_rejected(self):
        registry = _minimal_registry()
        clear_gate(registry, "GATE-0001", "VWALK-20260715-063000")
        with pytest.raises(RegistryError, match="cleared"):
            redefer_gate(registry, "GATE-0001", "why not")

    def test_record_attempt(self):
        registry = _minimal_registry()
        gate = record_attempt(registry, "GATE-0001", "VWALK-20260715-063000", 0.6, False)
        assert gate["attempts"][-1]["quiz_average"] == 0.6
        assert gate["attempts"][-1]["passed"] is False

    def test_get_gate_missing(self):
        with pytest.raises(RegistryError, match="not found"):
            get_gate(_minimal_registry(), "GATE-9999")


class TestCli:
    def _run(self, monkeypatch, registry_path, *argv):
        import sys

        from scripts.education import gate_registry as module

        monkeypatch.setattr(
            sys, "argv", ["gate_registry.py", "--registry", str(registry_path), *argv]
        )
        module.main()

    def test_cli_list(self, monkeypatch, registry_path, capsys):
        self._run(monkeypatch, registry_path, "list")
        out = capsys.readouterr().out
        assert "GATE-0001" in out and "Test gate" in out

    def test_cli_list_status_filter_empty(self, monkeypatch, registry_path, capsys):
        self._run(monkeypatch, registry_path, "list", "--status", "cleared")
        assert "No gates match" in capsys.readouterr().out

    def test_cli_add(self, monkeypatch, registry_path, capsys):
        self._run(
            monkeypatch,
            registry_path,
            "add",
            "--title",
            "CLI gate",
            "--origin",
            "review",
            "--files",
            "a.py,b.py",
            "--adrs",
            "ADR-0001",
        )
        assert "GATE-0002" in capsys.readouterr().out
        gate = get_gate(load_registry(registry_path), "GATE-0002")
        assert gate["scope"]["files"] == ["a.py", "b.py"]

    def test_cli_clear_and_list_shows_evidence(self, monkeypatch, registry_path, capsys):
        self._run(
            monkeypatch, registry_path, "clear", "GATE-0001", "--session", "VWALK-20260715-063000"
        )
        self._run(monkeypatch, registry_path, "list")
        out = capsys.readouterr().out
        assert "cleared by VWALK-20260715-063000" in out

    def test_cli_redefer(self, monkeypatch, registry_path, capsys):
        self._run(monkeypatch, registry_path, "re-defer", "GATE-0001", "--reason", "next walk")
        assert "Re-deferred GATE-0001" in capsys.readouterr().out
        assert load_registry(registry_path)["gates"][0]["status"] == "re-deferred"


class TestShippedRegistry:
    def test_shipped_gates_yaml_is_valid(self):
        """The seeded docs/education/gates.yaml must always validate."""
        registry = load_registry()
        assert registry["version"] == 1
        assert any(g["gate_id"] == "GATE-0004" for g in registry["gates"])
