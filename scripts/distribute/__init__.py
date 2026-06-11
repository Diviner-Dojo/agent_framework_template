"""Framework distribution package — orderly propagation of framework changes to derived projects.

The ``/distribute`` capability stages framework updates into derived projects as
*unmerged, unpushed* branches plus an advisory assessment doc. The human is always
the merge authority ("push the proposal, pull the apply").

Three building blocks, composed by ``.claude/commands/distribute.md``:

- :mod:`scripts.distribute.repo_safety_check` — the skip-if-busy / opt-in HARD GATE preflight.
- :mod:`scripts.distribute.change_package` — classify offered files (value / inert /
  collision-pinned / collision-diverged) via the lineage drift engine.
- :mod:`scripts.distribute.stage_branch` — write the proposal onto a fresh branch off the
  target's main (never push, never touch main, never overwrite a pinned trait).

Non-negotiables enforced across the package:

1. **Opt-in is a hard gate** — a target must declare ``custodian.accepts_distribution: true``
   in its own ``framework-lineage.yaml`` before any write touches it.
2. **Pinned traits are absolute** — a file matching a pinned trait is dropped, never staged.
3. **Never push, never touch main** — staging branches off main and commits only to the new branch.
"""
