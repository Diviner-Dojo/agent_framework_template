"""Structured education-gate registry (docs/education/gates.yaml).

Gives Principle #6 deferrals a machine-readable home so external clients
(RepoCademy) can discover open gates and the ingest chokepoint can flip them.
Previously deferrals lived only as BUILD_STATUS.md prose (ADR-0029).

Usage:
    python scripts/education/gate_registry.py list [--status open|cleared|re-deferred]
    python scripts/education/gate_registry.py add --title T [--origin manual] \
        [--reason R] [--files a.py,b.py] [--adrs ADR-0001] [--spec SPEC-...]
    python scripts/education/gate_registry.py clear GATE-0001 --session VWALK-... \
        [--discussion DISC-...]
    python scripts/education/gate_registry.py re-defer GATE-0001 --reason R
"""

import argparse
import os
import re
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
REGISTRY_PATH = PROJECT_ROOT / "docs" / "education" / "gates.yaml"

REGISTRY_VERSION = 1
VALID_STATUSES = {"open", "cleared", "re-deferred"}
VALID_ORIGINS = {"review", "build", "spec", "retro", "manual"}
GATE_ID_RE = re.compile(r"^GATE-\d{4}$")
SESSION_ID_RE = re.compile(r"^VWALK-\d{8}-\d{6}$")


class RegistryError(ValueError):
    """Raised when the registry file or an operation on it is invalid."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def validate_registry(registry: dict[str, Any]) -> None:
    """Validate the full registry structure; raise RegistryError on any defect.

    Args:
        registry: Parsed registry mapping.
    """
    if not isinstance(registry, dict):
        raise RegistryError("Registry root must be a mapping")
    if registry.get("version") != REGISTRY_VERSION:
        raise RegistryError(f"Unsupported registry version: {registry.get('version')!r}")
    gates = registry.get("gates")
    if not isinstance(gates, list):
        raise RegistryError("Registry 'gates' must be a list")

    seen_ids: set[str] = set()
    for gate in gates:
        if not isinstance(gate, dict):
            raise RegistryError("Each gate must be a mapping")
        gate_id = gate.get("gate_id", "")
        if not isinstance(gate_id, str) or not GATE_ID_RE.match(gate_id):
            raise RegistryError(f"Invalid gate_id: {gate_id!r}")
        if gate_id in seen_ids:
            raise RegistryError(f"Duplicate gate_id: {gate_id}")
        seen_ids.add(gate_id)
        if gate.get("status") not in VALID_STATUSES:
            raise RegistryError(f"{gate_id}: invalid status {gate.get('status')!r}")
        if gate.get("origin") not in VALID_ORIGINS:
            raise RegistryError(f"{gate_id}: invalid origin {gate.get('origin')!r}")
        if not isinstance(gate.get("title"), str) or not gate["title"].strip():
            raise RegistryError(f"{gate_id}: title is required")
        scope = gate.get("scope", {})
        if not isinstance(scope, dict):
            raise RegistryError(f"{gate_id}: scope must be a mapping")
        for key in ("files", "adrs"):
            value = scope.get(key, [])
            if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
                raise RegistryError(f"{gate_id}: scope.{key} must be a list of strings")
        if gate.get("status") == "cleared":
            cleared_by = gate.get("cleared_by", "")
            if not isinstance(cleared_by, str) or not SESSION_ID_RE.match(cleared_by):
                raise RegistryError(f"{gate_id}: cleared gate needs a valid cleared_by session id")
        deferrals = gate.get("deferrals", [])
        if not isinstance(deferrals, list):
            raise RegistryError(f"{gate_id}: deferrals must be a list")


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    """Load and validate the registry from disk.

    Args:
        path: Registry YAML path.

    Returns:
        The validated registry mapping.
    """
    if not path.exists():
        raise RegistryError(f"Registry not found: {path}")
    with open(path, encoding="utf-8") as f:
        registry = yaml.safe_load(f)
    validate_registry(registry)
    return registry


def save_registry(registry: dict[str, Any], path: Path = REGISTRY_PATH) -> None:
    """Validate then atomically write the registry to disk.

    Args:
        registry: Registry mapping to persist.
        path: Registry YAML path.
    """
    validate_registry(registry)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            yaml.safe_dump(registry, f, sort_keys=False, allow_unicode=True)
        os.replace(tmp_name, path)
    except OSError:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def get_gate(registry: dict[str, Any], gate_id: str) -> dict[str, Any]:
    """Return the gate with the given id.

    Args:
        registry: Loaded registry.
        gate_id: Gate identifier (GATE-NNNN).
    """
    for gate in registry["gates"]:
        if gate["gate_id"] == gate_id:
            return gate
    raise RegistryError(f"Gate not found: {gate_id}")


def next_gate_id(registry: dict[str, Any]) -> str:
    """Return the next sequential GATE-NNNN id."""
    highest = 0
    for gate in registry["gates"]:
        highest = max(highest, int(gate["gate_id"].split("-")[1]))
    return f"GATE-{highest + 1:04d}"


def add_gate(
    registry: dict[str, Any],
    title: str,
    origin: str = "manual",
    reason_deferred: str = "",
    files: list[str] | None = None,
    adrs: list[str] | None = None,
    spec: str | None = None,
) -> dict[str, Any]:
    """Append a new open gate to the registry (does not save).

    Args:
        registry: Loaded registry (mutated in place).
        title: Human-readable gate title.
        origin: One of VALID_ORIGINS.
        reason_deferred: Why the gate was deferred at creation time.
        files: Scope file paths.
        adrs: Scope ADR ids.
        spec: Scope spec id.

    Returns:
        The new gate mapping.
    """
    if origin not in VALID_ORIGINS:
        raise RegistryError(f"Invalid origin: {origin!r}")
    if not title.strip():
        raise RegistryError("Gate title is required")
    gate = {
        "gate_id": next_gate_id(registry),
        "title": title.strip(),
        "created_at": _utc_now(),
        "origin": origin,
        "scope": {"files": files or [], "adrs": adrs or [], "spec": spec},
        "reason_deferred": reason_deferred,
        "status": "open",
        "deferrals": [],
        "attempts": [],
        "cleared_by": None,
        "cleared_at": None,
        "discussion_id": None,
    }
    registry["gates"].append(gate)
    return gate


def record_attempt(
    registry: dict[str, Any],
    gate_id: str,
    session_id: str,
    quiz_average: float | None,
    passed: bool,
) -> dict[str, Any]:
    """Record a clearing attempt on a gate (does not save, does not flip status).

    Args:
        registry: Loaded registry (mutated in place).
        gate_id: Target gate.
        session_id: VWALK session id of the attempt.
        quiz_average: Average quiz score, if a quiz ran.
        passed: Whether the attempt met the gate-cleared rule.
    """
    if not SESSION_ID_RE.match(session_id):
        raise RegistryError(f"Invalid session id: {session_id!r}")
    gate = get_gate(registry, gate_id)
    gate.setdefault("attempts", []).append(
        {
            "session_id": session_id,
            "date": _utc_now(),
            "quiz_average": quiz_average,
            "passed": passed,
        }
    )
    return gate


def clear_gate(
    registry: dict[str, Any],
    gate_id: str,
    session_id: str,
    discussion_id: str | None = None,
) -> dict[str, Any]:
    """Mark a gate cleared (does not save).

    Args:
        registry: Loaded registry (mutated in place).
        gate_id: Target gate.
        session_id: VWALK session id that cleared it.
        discussion_id: Discussion carrying the evidence.
    """
    if not SESSION_ID_RE.match(session_id):
        raise RegistryError(f"Invalid session id: {session_id!r}")
    gate = get_gate(registry, gate_id)
    if gate["status"] == "cleared":
        raise RegistryError(f"{gate_id} is already cleared (by {gate.get('cleared_by')})")
    gate["status"] = "cleared"
    gate["cleared_by"] = session_id
    gate["cleared_at"] = _utc_now()
    gate["discussion_id"] = discussion_id
    return gate


def redefer_gate(registry: dict[str, Any], gate_id: str, reason: str) -> dict[str, Any]:
    """Formally re-defer a gate with rationale (Principle #6; does not save).

    Args:
        registry: Loaded registry (mutated in place).
        gate_id: Target gate.
        reason: Documented rationale for the re-deferral.
    """
    if not reason.strip():
        raise RegistryError("A re-deferral requires a documented reason (Principle #6)")
    gate = get_gate(registry, gate_id)
    if gate["status"] == "cleared":
        raise RegistryError(f"{gate_id} is cleared; nothing to re-defer")
    gate["status"] = "re-deferred"
    gate.setdefault("deferrals", []).append({"date": _utc_now(), "reason": reason.strip()})
    return gate


def _cmd_list(args: argparse.Namespace) -> None:
    registry = load_registry(args.registry)
    gates = registry["gates"]
    if args.status:
        gates = [g for g in gates if g["status"] == args.status]
    if not gates:
        print("No gates match.")
        return
    for gate in gates:
        scope_bits = gate["scope"]["files"] + gate["scope"]["adrs"]
        if gate["scope"].get("spec"):
            scope_bits.append(gate["scope"]["spec"])
        scope = ", ".join(scope_bits[:4]) or "(no scope listed)"
        print(f"{gate['gate_id']}  [{gate['status']:<11}]  {gate['title']}")
        print(f"    origin: {gate['origin']} · scope: {scope}")
        if gate["status"] == "cleared":
            print(f"    cleared by {gate['cleared_by']} at {gate['cleared_at']}")


def _cmd_add(args: argparse.Namespace) -> None:
    registry = load_registry(args.registry)
    files = [f.strip() for f in args.files.split(",") if f.strip()] if args.files else []
    adrs = [a.strip() for a in args.adrs.split(",") if a.strip()] if args.adrs else []
    gate = add_gate(
        registry,
        title=args.title,
        origin=args.origin,
        reason_deferred=args.reason or "",
        files=files,
        adrs=adrs,
        spec=args.spec,
    )
    save_registry(registry, args.registry)
    print(f"Added {gate['gate_id']}: {gate['title']}")


def _cmd_clear(args: argparse.Namespace) -> None:
    registry = load_registry(args.registry)
    gate = clear_gate(registry, args.gate_id, args.session, args.discussion)
    save_registry(registry, args.registry)
    print(f"Cleared {gate['gate_id']} (by {args.session})")


def _cmd_redefer(args: argparse.Namespace) -> None:
    registry = load_registry(args.registry)
    gate = redefer_gate(registry, args.gate_id, args.reason)
    save_registry(registry, args.registry)
    print(f"Re-deferred {gate['gate_id']} ({len(gate['deferrals'])} deferral(s) on record)")


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Education-gate registry")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH, help="Registry path")
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List gates")
    p_list.add_argument("--status", choices=sorted(VALID_STATUSES), default=None)
    p_list.set_defaults(func=_cmd_list)

    p_add = sub.add_parser("add", help="Add an open gate")
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--origin", choices=sorted(VALID_ORIGINS), default="manual")
    p_add.add_argument("--reason", default="")
    p_add.add_argument("--files", default="")
    p_add.add_argument("--adrs", default="")
    p_add.add_argument("--spec", default=None)
    p_add.set_defaults(func=_cmd_add)

    p_clear = sub.add_parser("clear", help="Mark a gate cleared")
    p_clear.add_argument("gate_id")
    p_clear.add_argument("--session", required=True, help="VWALK-... session id")
    p_clear.add_argument("--discussion", default=None)
    p_clear.set_defaults(func=_cmd_clear)

    p_redefer = sub.add_parser("re-defer", help="Formally re-defer a gate")
    p_redefer.add_argument("gate_id")
    p_redefer.add_argument("--reason", required=True)
    p_redefer.set_defaults(func=_cmd_redefer)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
