# AI-Native Agentic Development Framework — Project Template

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A structured, multi-agent development framework for Claude Code that transforms AI-assisted development from unstructured "vibe coding" into a disciplined, self-improving engineering methodology.

## Prerequisites

Install these tools before using the framework:

| Tool | Required | What It Does | Get It |
|------|----------|-------------|--------|
| **Python 3.11+** | Yes | Runtime for the framework and your application | [python.org](https://www.python.org/downloads/) |
| **Git** | Yes | Version control — the framework uses branches, hooks, and commit gates | [git-scm.com](https://git-scm.com/downloads) |
| **Claude Code** | Yes | The CLI that runs all 11 agents and 16 commands | [claude.com/claude-code](https://claude.com/claude-code) |
| **VS Code** | Recommended | Editor with Claude Code integration | [code.visualstudio.com](https://code.visualstudio.com/) |
| **GitHub CLI (`gh`)** | Optional | Used by `/discover-projects`, `/ship`, and PR workflows | [cli.github.com](https://cli.github.com/) |

## Quick Start

This is a **framework template**, not a standalone application. It provides the agentic development infrastructure — agents, commands, rules, hooks, and capture pipelines — that you build your project on top of.

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize the metrics database
```bash
python scripts/init_db.py
```

### 3. Run tests
```bash
pytest tests/ -v
```

### 4. Start building
Add your application code to `src/` and your tests to `tests/`, then use the framework commands in Claude Code:
- `/review src/` — Run a multi-agent code review
- `/plan "feature"` — Plan a feature with spec-driven development
- `/build_module` — Build a module from a spec with integrated quality gates
- `/deliberate "topic"` — Start a structured discussion
- `/walkthrough src/routes.py` — Get a guided code walkthrough
- `/quiz src/routes.py` — Take a comprehension quiz
- `/analyze-project owner/repo` — Analyze an external project for patterns worth adopting
- `/lineage` — Check framework lineage and drift status
- `/ship 1.0.0` — Run the full release workflow

See all 16 commands in `.claude/commands/`.

## Directory Structure

```
.claude/
  agents/       — 11 specialist agent definitions
  commands/     — 16 workflow commands (/review, /deliberate, /plan, etc.)
  rules/        — 7 auto-loaded standards (all agents inherit these)
  skills/       — 5 reference knowledge playbooks
  hooks/        — Automated lifecycle hooks (locking, secrets, formatting, session)
  custodian/    — Steward lineage tracking (append-only event log)

docs/
  adr/          — Architecture Decision Records
  reviews/      — Review reports from /review
  sprints/      — Sprint plans, retrospectives, meta-reviews
  templates/    — Reusable artifact templates

discussions/    — Layer 1: Immutable discussion capture (events.jsonl + transcript.md)
memory/         — Layer 3: Curated knowledge (human-approved patterns and rules)
metrics/        — Layer 2: SQLite relational index (evaluation.db)
scripts/        — Capture pipeline utilities (Python)
  lineage/      — Lineage tracking utilities (drift detection, manifest)

src/            — Your application source code (empty in template)
tests/          — Test suite
framework-lineage.yaml  — Lineage manifest (project-template relationship)
```

## The Agent Panel

| Agent | Priority | When Activated |
|-------|----------|---------------|
| **Facilitator** | Orchestration, synthesis | Every workflow |
| **Architecture Consultant** | Structural alignment, drift | Architecture changes, new modules |
| **Security Specialist** | Vulnerabilities, threats | Auth, API, data handling |
| **QA Specialist** | Test coverage, reliability | Every code review |
| **Performance Analyst** | Efficiency, scalability | Data processing, DB, API |
| **Docs/Knowledge** | Documentation, ADRs | Every review (light), arch changes (full) |
| **Educator** | Developer understanding | Every merge gate |
| **Independent Perspective** | Anti-groupthink | Medium/high risk changes |
| **UX Evaluator** | Interaction flow, accessibility | User-facing changes |
| **Project Analyst** | External project scouting | /analyze-project workflows |
| **Steward** | Framework lineage, drift tracking | Template/fork management |

## Key Concepts

- **Coopetition**: Agents share goals but have different professional priorities — natural productive tension without manufactured opposition
- **Four-Layer Capture**: Immutable files → SQLite index → Curated memory → Optional vector search
- **Education Gates**: Walkthrough → Quiz → Explain-back → Merge
- **Nested Loops**: Micro (per-discussion) → Meso (per-sprint /retro) → Macro (quarterly /meta-review)
- **Spec-Driven Development**: Every significant change starts with an approved spec
- **Lineage Tracking**: Steward agent tracks project-to-template relationships via `framework-lineage.yaml`, detecting drift and managing divergences
- **Build Review Protocol**: Mid-build checkpoint reviews enforce independence (Principle #4) during `/build_module` execution

## External Project Analysis & Attribution

The `/analyze-project` command lets you study external projects (public GitHub repos or local codebases) to discover architectural patterns worth adopting. The framework extracts **ideas and design patterns**, not code — and attributes everything back to the source.

- Every adopted pattern is permanently linked to its source project in `memory/lessons/adoption-log.md`
- License checks run before analysis begins, with risk-appropriate framing (permissive, copyleft, or unlicensed)
- The Rule of Three requires patterns to appear in 3+ independent projects before priority consideration
- Target projects are read-only — never modified during analysis

See `/discover-projects` to find candidates and `/analyze-project` to run the analysis.

## Framework Spec

See the full framework specification: [`docs/FRAMEWORK_SPECIFICATION.md`](docs/FRAMEWORK_SPECIFICATION.md)
