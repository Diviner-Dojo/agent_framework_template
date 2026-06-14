"""Route detection for ``/apply-framework`` — the presence-routing front-end (R1).

One command points at any project path and figures out whether the framework is already there:

- **framework present** (a valid ``framework-lineage.yaml`` exists) → ``update`` (the existing
  ``/distribute`` B1 down-propagation path).
- **no lineage, but N pre-existing framework-path files** → ``partial`` (treat with care — the
  project may be a manual/abandoned adoption; an overwrite could clobber authored work).
- **no framework at all** → ``greenfield`` APPLY.

The route is reported as a **spectrum**, not a binary label, so the human sees how confident the
detection is. Detection is **fail-closed** (R1): a malformed/empty ``framework-lineage.yaml``
raises (it never silently falls through to APPLY, the weakest-consent route), and a missing target
raises (it never classifies a non-existent directory). The router itself is **read-only** — it is
part of the ASSESS phase and has no write path.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Ensure project root is on sys.path for both CLI and module usage.
_PROJECT_ROOT = Path(__file__).parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.lineage._utils import collect_framework_files  # noqa: E402
from scripts.lineage.manifest import manifest_read  # noqa: E402

MANIFEST_NAME = "framework-lineage.yaml"

ROUTE_UPDATE = "update"
ROUTE_PARTIAL = "partial"
ROUTE_GREENFIELD = "greenfield"


@dataclass
class RouteReport:
    """The detected route for one target — reported as a spectrum (R1).

    Attributes:
        target_path: Absolute path of the target repository.
        route: One of :data:`ROUTE_UPDATE` / :data:`ROUTE_PARTIAL` / :data:`ROUTE_GREENFIELD`.
        has_lineage: True iff a valid ``framework-lineage.yaml`` was found.
        preexisting_framework_files: Framework-path files found when there is no lineage (drives
            the ``partial`` distinction); empty on the update and pure-greenfield routes.
        label: Human-readable spectrum string for the assess report and session output.
    """

    target_path: str
    route: str
    has_lineage: bool
    label: str
    preexisting_framework_files: list[str] = field(default_factory=list)

    @property
    def is_greenfield_engine(self) -> bool:
        """True when the APPLY (greenfield) classification engine should run.

        Both ``greenfield`` and ``partial`` lack lineage, so both use the ``OnDiskBaseline`` engine
        (:func:`scripts.distribute.change_package.compute_greenfield_package`); ``partial`` only
        differs in that the report warns about the pre-existing framework files it found.
        """
        return self.route in (ROUTE_GREENFIELD, ROUTE_PARTIAL)


def detect_route(target_path: Path | str) -> RouteReport:
    """Detect the apply-or-update route for a target, reported as a spectrum (R1).

    Args:
        target_path: Path to the target repository root.

    Returns:
        A :class:`RouteReport`.

    Raises:
        FileNotFoundError: If the target path does not exist or is not a directory (fail closed —
            never classify a non-existent directory).
        ValueError: If a ``framework-lineage.yaml`` exists but is empty or malformed (fail closed —
            never silently fall through to the weakest-consent APPLY route on a corrupt manifest).
    """
    target = Path(target_path).resolve()
    if not target.is_dir():
        raise FileNotFoundError(f"target path is not a directory: {target}")

    manifest_path = target / MANIFEST_NAME
    if manifest_path.exists():
        try:
            manifest_read(manifest_path)
        except (ValueError, OSError, yaml.YAMLError) as exc:
            raise ValueError(
                f"{MANIFEST_NAME} at {target} is present but unreadable ({exc}); refusing to "
                "route — fail closed rather than silently treat a corrupt manifest as greenfield"
            ) from exc
        return RouteReport(
            target_path=str(target),
            route=ROUTE_UPDATE,
            has_lineage=True,
            label="framework present (UPDATE)",
        )

    preexisting = sorted(collect_framework_files(target).keys())
    if preexisting:
        return RouteReport(
            target_path=str(target),
            route=ROUTE_PARTIAL,
            has_lineage=False,
            label=(
                f"no lineage, and found {len(preexisting)} pre-existing framework-path file(s) "
                "(partial — treat with care)"
            ),
            preexisting_framework_files=preexisting,
        )

    return RouteReport(
        target_path=str(target),
        route=ROUTE_GREENFIELD,
        has_lineage=False,
        label="no framework (greenfield APPLY)",
    )


def main() -> None:
    """CLI entry point — print the detected route for a target path."""
    parser = argparse.ArgumentParser(description="Detect the /apply-framework route for a target")
    parser.add_argument("target", help="Path to the target repository root")
    args = parser.parse_args()

    try:
        report = detect_route(args.target)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ROUTE ERROR (fail closed): {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"Target:        {report.target_path}")
    print(f"Route:         {report.route}")
    print(f"Has lineage:   {report.has_lineage}")
    print(f"Spectrum:      {report.label}")
    if report.preexisting_framework_files:
        print(f"Pre-existing framework files: {len(report.preexisting_framework_files)}")


if __name__ == "__main__":
    main()
