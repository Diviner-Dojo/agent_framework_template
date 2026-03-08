"""Lineage tracking utilities for the Steward agent.

Provides manifest CRUD, drift detection, and lineage initialization
for tracking framework evolution across derived projects.
"""

from scripts.lineage.drift import compute_divergence_distance, drift_report, drift_scan
from scripts.lineage.init_lineage import lineage_init
from scripts.lineage.manifest import manifest_read, manifest_update_drift, manifest_validate

__all__ = [
    "drift_report",
    "drift_scan",
    "compute_divergence_distance",
    "lineage_init",
    "manifest_read",
    "manifest_update_drift",
    "manifest_validate",
]
