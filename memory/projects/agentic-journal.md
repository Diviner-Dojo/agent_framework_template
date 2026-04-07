---
project_name: "Agentic Journal"
source: "c:/Work/AI/agentic_journal"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-28", "2026-03-09"]
analysis_count: 3
tags: [flutter, dart, mobile, journaling, adhd, supabase, framework-derivative]
---

## Overview

Flutter/Dart journaling app and the first real-world project built on this framework (derivative of template v2.1). ~115k LOC, 61 ADRs, 100+ discussions. Multi-tenant with Supabase backend, Claude API via Edge Functions, Riverpod state management. Designed as an ADHD-supportive daily journal with AI-powered reflection. The most mature and actively evolved derivative project — its innovations have driven significant framework improvements upstream.

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Dart 3.x |
| Framework | Flutter, Riverpod, GoRouter |
| Database | SQLite (drift) + Supabase (cloud) |
| Testing | Flutter test, integration_test |
| CI/CD | None (manual) |
| Deployment | iOS/Android via Flutter |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Standing Documents for Specialist Domains | 23/25 | ADOPT |
| Regression Diagnosis SOP (root-cause taxonomy) | 21/25 | ADOPT |
| Agent Self-Evaluation Protocol | 20/25 | ADOPT |
| Strategic Education Gates (ADR-0059) | 19/25 | ADOPT |
| Orientation Documents (current-arc.md) | 18/25 | ADOPT |
| Deploy-Safety Hook Pattern | 18/25 | ADOPT (pattern) |
| Spec Closure Check (session-start 5b) | 18/25 | ADOPT |
| UX Subagent Chunking Pattern | 16/25 | ADOPT (facilitator section) |
| /watcher Autonomous Pipeline | 16/25 | DEFER |
| /status Dashboard | 16/25 | DEFER |
| /journal-review Pipeline | 14/25 | REJECT |

## Solution Paths

### agent-workflow/conformity-filter — Synthesis dropping unique specialist voices

**Problem**: Multi-agent synthesis was systematically dropping findings from the three most unique voices (security 0%, UX 0%, independent-perspective 0% survival)
**Tried**: Standard synthesis (aggregate and summarize all findings)
**Chosen**: Survival Rate Checkpoint — explicit per-agent audit before finalizing synthesis, with measurement baselines and SQL queries for retro tracking
**Evidence**: memory/decisions/peer-eval-baselines.md, 185 discussions analyzed
**Tags**: [agent-workflow/conformity-filter, agent-workflow/synthesis-quality]

### education/strategic-knowledge — Teaching knowledge that outlasts refactors

**Problem**: Education gates testing implementation details that AI makes irrelevant — code-focused walkthroughs decay with every refactor
**Tried**: Code-focused walkthroughs testing data flow and implementation details
**Chosen**: Three-Layer Knowledge Model (landscape 50% → invariant 35% → diagnostic 15%) with Bloom's redistribution (70% Analyze/Evaluate/Create). Educator draws from ADRs and technology grid profiles, not code.
**Evidence**: ADR-0059, .claude/agents/educator.md
**Tags**: [education/strategic-knowledge, agent-workflow/educator-design]

### regression/diagnosis-discipline — Write the ledger before the commit

**Problem**: Regression knowledge siloed in git history; free-form ledger entries without structure
**Tried**: Reading git log to reconstruct root causes; unstructured ledger entries
**Chosen**: Named root-cause taxonomy (9 classes) + structured ledger fields (7 mandatory) + write-before-commit sequencing
**Evidence**: memory/patterns/regression-diagnosis-sop.md
**Tags**: [regression/diagnosis-discipline, testing/regression-prevention]

### session/orientation — 90-second resume after long gaps

**Problem**: Losing the thread after days/weeks away from the project — BUILD_STATUS.md tracks tasks but not "what matters right now"
**Tried**: Manual BUILD_STATUS.md updates
**Chosen**: current-arc.md (5-section 90-second orientation) + journey.md (narrative project history). Designed as ADHD support: "The fear of losing the thread is not an information problem — it's a retrieval design problem."
**Evidence**: memory/decisions/current-arc.md, memory/journey.md
**Tags**: [session/orientation, session/adhd-support]

### capture/spec-closure — Making completed features visible to status tooling

**Problem**: Specs marked "complete" without closure fields → Feature Timeline required git archaeology
**Tried**: Manual status updates in BUILD_STATUS.md
**Chosen**: close_spec.py (post-commit, captures SHA) + session-start check 5b (surfaces unclosed complete specs). Commit SHA cannot exist before the commit, so closure must be an explicit post-commit step.
**Evidence**: scripts/close_spec.py, .claude/hooks/session-start.ps1 check 5b
**Tags**: [capture/spec-closure, session/status-tracking]

## Applicability Assessment

The most prolific source of adoptable patterns across all analyzed projects. Its innovations in standing documents, regression diagnosis, agent self-evaluation, and strategic education gates are all directly applicable to the framework template. The Supabase-specific patterns (/watcher, /journal-review, /status) are not portable but represent an aspirational architecture for cloud-connected framework derivatives.
