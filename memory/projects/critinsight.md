---
project_name: "CritInsight"
source: "c:/Work/AI/critinsight"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [python, fastapi, nl-to-sql, llm-pipeline, safety-validation, framework-derivative]
---

## Overview

NL-to-SQL analytics system that converts natural language questions into safe, validated SQL queries. Python 3.12, FastAPI, LiteLLM + Instructor, SQLAlchemy 2.0 (async), LanceDB/pgvector, sqlglot, Streamlit. ~10,000 LOC with 1,063 tests. Code-complete MVP with NLSpec-driven architecture — specs precede code, functioning as executable requirements. Three purpose-built subagents (component-builder opus, safety-auditor sonnet, test-runner haiku).

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Python 3.12 |
| Framework | FastAPI, Streamlit |
| Database | SQLAlchemy 2.0 (async, multi-dialect), LanceDB/pgvector |
| Testing | pytest (1,063 tests) |
| CI/CD | None |
| Deployment | Not yet deployed |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Inline "Why" Decision Rationale | 22/25 | ADOPT |
| NLSpec Component Format | 20/25 | DEFER (extract sub-patterns) |
| Haiku-Tier for Mechanical Tasks | 19/25 | DEFER |
| Component Verification Checklist | 18/25 | DEFER |
| Graceful Decline with Persona Language | 17/25 | REJECT |
| Progressive Temperature on Retry | 17/25 | REJECT |
| Holdout Validation Scenarios | 16/25 | DEFER |
| Subagent Delegation Guide | 15/25 | REJECT |

## Solution Paths

### llm/structured-output — Instructor .create() API vs __call__

**Problem**: Small LLMs (gemma3:4b) fail tool-call structured output
**Tried**: Direct `__call__` API on Instructor
**Chosen**: Explicit `.create()` method + list coercion validators for fields that LLMs return as JSON strings instead of lists
**Evidence**: BUILD_STATUS.md
**Tags**: [llm/structured-output, llm/small-model-compat]

### data/sql-transformation — MSSQL Row Limiting

**Problem**: Injecting row limits into MSSQL queries
**Tried**: Wrapping queries in `SELECT TOP N FROM (...) AS limited` — breaks for unnamed columns
**Chosen**: Direct TOP N injection into the SELECT clause
**Evidence**: BUILD_STATUS.md
**Tags**: [data/sql-transformation, data/dialect-specific]

### config/settings-loading — Pydantic Settings YAML Override Precedence

**Problem**: Python default values in Settings classes overriding YAML file values
**Tried**: Standard Pydantic Settings with YAML source
**Chosen**: Loading YAML at runtime with explicit source ordering and `extra="ignore"` for forward compatibility
**Evidence**: BUILD_STATUS.md
**Tags**: [config/settings-loading, config/pydantic-patterns]

### safety/schema-agnostic — No Hardcoded Schema References

**Problem**: Building a product that works for any database schema
**Tried**: Schema-specific queries
**Chosen**: Centralize all schema references through RAG retrieval layer — nothing in the pipeline is hardcoded. Enforced in CLAUDE.md checklist and safety-auditor agent.
**Evidence**: CLAUDE.md, src/core/safety/
**Tags**: [safety/schema-agnostic, data/abstraction-layer]

## Applicability Assessment

CritInsight's primary contribution is the inline "Why" decision rationale pattern — a zero-cost writing convention that fills the gap between formal ADRs and undocumented minor decisions. Its NLSpec format has three extractable sub-patterns (GIVEN/WHEN/THEN behavioral pseudocode, binary Acceptance Criteria, Non-Goals sections) applicable to ADR templates and education gate design. The holdout validation concept is a future candidate when the framework develops measurable behavioral outcomes.
