# AI-Native Agentic Development Framework — Project Template

A structured, multi-agent development framework for Claude Code that transforms AI-assisted development from unstructured "vibe coding" into a disciplined, self-improving engineering methodology.

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize the metrics database
```bash
python scripts/init_db.py
```

### 3. Run the Todo API (test project)
```bash
uvicorn src.main:app --reload
```

### 4. Run tests
```bash
pytest tests/ -v
```

### 5. Try the framework commands
In Claude Code:
- `/review src/` — Run a multi-agent code review
- `/deliberate "topic"` — Start a structured discussion
- `/plan "feature"` — Plan a feature with spec-driven development
- `/walkthrough src/routes.py` — Get a guided code walkthrough
- `/quiz src/routes.py` — Take a comprehension quiz

## Directory Structure

```
.claude/
  agents/       — 8 specialist agent definitions
  commands/     — 10 workflow commands (/review, /deliberate, /plan, etc.)
  rules/        — 5 auto-loaded standards (all agents inherit these)
  skills/       — 5 reference knowledge playbooks

docs/
  adr/          — Architecture Decision Records
  reviews/      — Review reports from /review
  sprints/      — Sprint plans, retrospectives, meta-reviews
  templates/    — Reusable artifact templates

discussions/    — Layer 1: Immutable discussion capture (events.jsonl + transcript.md)
memory/         — Layer 3: Curated knowledge (human-approved patterns and rules)
metrics/        — Layer 2: SQLite relational index (evaluation.db)
scripts/        — Capture pipeline utilities (Python)

src/            — Application source code (Todo API test project)
tests/          — Test suite
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

## Key Concepts

- **Coopetition**: Agents share goals but have different professional priorities — natural productive tension without manufactured opposition
- **Four-Layer Capture**: Immutable files → SQLite index → Curated memory → Optional vector search
- **Education Gates**: Walkthrough → Quiz → Explain-back → Merge
- **Nested Loops**: Micro (per-discussion) → Meso (per-sprint /retro) → Macro (quarterly /meta-review)
- **Spec-Driven Development**: Every significant change starts with an approved spec

## Framework Spec

See the full framework specification: `AI_Native_Agentic_Development_Framework_v2.1.md`
