---
description: "DEPRECATED ALIAS for /apply-framework. /distribute became a misnomer once the command also applies the framework greenfield (ADR-0021). Use /apply-framework."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "<target-path> [--deploy] [--adr ADR-NNNN | --changelog-since YYYY-MM-DD] [--assent-human \"Name\"]"
---

# /distribute — DEPRECATED ALIAS → use `/apply-framework`

`/distribute` was the down-propagation-only command (hub → a framework-carrying derived project). It
has been **superseded by `/apply-framework`** (ADR-0021), which unifies it with greenfield apply behind
one presence-routing front-end and gates deploy on an up-front value/risk assessment. The name
`/distribute` became a misnomer the moment the command could also *apply* the framework to a project
that never had it.

> **Do this:** run **`/apply-framework <target-path>`** and follow `.claude/commands/apply-framework.md`.
> The old `/distribute` UPDATE behavior is exactly the **UPDATE route** there (present-lineage target →
> `compute_package` → clean-tree-gated deploy onto a `framework/update-<date>` branch). Nothing about the
> opt-in HARD GATE, the B1 mechanical floor, confidentiality, or never-push/never-merge has changed.

Kept (not deleted) so existing references resolve and the rename is discoverable (Principle #5). All
behavior now lives in `apply-framework.md` + `scripts/distribute/` (the package keeps its name).
