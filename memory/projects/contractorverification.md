---
project_name: "VerificationPortal (ContractorVerification)"
source: "c:/Work/AI/VerificationPortal"
analyzed: "2026-04-06"
prior_analyses: ["2026-02-19"]
analysis_count: 2
tags: [python, fastapi, playwright, scraping, saas, multi-tenant, framework-derivative]
---

## Overview

Automated professional license and credential verification across 51 US state portals. Python 3.12, FastAPI, Playwright (Chromium), SQLAlchemy, Celery+Redis, Ollama (llama3.2:3b). Multi-tenant SaaS with API key auth, credit billing, batch CSV processing. ~27,200 LOC in src/. Full framework adoption at v3.4 with 4 project-specific agents added on top of the 12 framework agents (16 total). The most pattern-rich project analyzed — 10 patterns at or above the adoption threshold.

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | Python 3.12 |
| Framework | FastAPI, Celery |
| Database | SQLAlchemy (SQLite dev / SQL Server prod), Redis |
| Testing | pytest, Playwright |
| CI/CD | GitHub Actions |
| Deployment | Docker, devcontainer |

## Notable Patterns (New — April 2026)

| Pattern | Score | Status |
|---------|-------|--------|
| Stop Event Hooks (mypy + pytest) | 22/25 | ADOPT |
| Feature Status Registry (FEATURE_STATUS.md) | 22/25 | ADOPT |
| Per-Resource Circuit Breaker | 22/25 | ADOPT |
| Domain-Specific PostToolUse Validation Hook | 21/25 | ADOPT |
| /ship Command with Auto Classification | 20/25 | ADOPT |
| Project-Scoped MCP Configuration (.mcp.json) | 20/25 | ADOPT |
| Acceptance Criteria Document (ACCEPTANCE.md) | 20/25 | ADOPT |
| Agent Notes as Failure Log (AGENT_NOTES.md) | 20/25 | ADOPT |
| .claude/docs/ Agent-Targeted Onboarding | 20/25 | ADOPT |
| /evaluate-repo-security Command | 19/25 | ADOPT |
| /onboard Command (Takeover Protocol) | 19/25 | ADOPT |
| Education Gate Manifest Template | 19/25 | ADOPT |
| Plan-Reviewer Agent | 19/25 | ADOPT |
| Batch Checkpoint State | 18/25 | DEFER |
| Path-Scoped Copilot Instructions | 17/25 | DEFER |

## Solution Paths

### infra/windows-async — Windows Proactor Loop for Playwright + FastAPI

**Problem**: uvicorn direct launch on Windows hangs Chromium processes
**Tried**: Standard uvicorn startup
**Chosen**: runserver.py that explicitly sets `asyncio.WindowsProactorEventLoopPolicy()` before starting uvicorn
**Evidence**: runserver.py, docs/AGENT_NOTES.md, .github/copilot-instructions.md
**Tags**: [infra/windows-async, infra/playwright-setup]

### data/config-reload — Config Cache Busting via mtime

**Problem**: Hot-reloading JSON configs without restarting the service
**Tried**: File watchers (complex), manual restart
**Chosen**: Cache keyed by (path, mtime) — touching the file busts the cache without a restart
**Evidence**: src/core/config/loader.py, PROJECT_REFERENCE.md
**Tags**: [data/config-reload, infra/hot-reload]

### scraping/blocked-sites — Guided Discovery Session Protocol

**Problem**: CAPTCHA/SPA sites that block autonomous browser automation
**Tried**: Full automation with stealth headers
**Chosen**: Human-AI collaboration protocol — human navigates and captures DOM, AI guides selector identification from captured HTML. 4-phase session protocol.
**Evidence**: .claude/agents/state-config-builder.md (Guided Session Mode)
**Tags**: [scraping/blocked-sites, agent-workflow/human-ai-collaboration]

### security/compliance-review — Systematic ToS/robots.txt Review

**Problem**: Legal exposure from automated scraping before reviewing ToS
**Tried**: Ad-hoc ToS reading
**Chosen**: Systematic 3-step review (gather ToS/robots.txt, analyze for prohibitions, document evidence per state) stored in docs/compliance/{STATE}/
**Evidence**: docs/STATE_TOS_REVIEW.md, docs/compliance/
**Tags**: [security/compliance-review, scraping/legal-compliance]

### scraping/stealth-tiers — Per-State Stealth Tier Matrix

**Problem**: Different portals require different anti-detection levels — max stealth everywhere wastes resources
**Tried**: Uniform stealth configuration
**Chosen**: Tier classification (1=Static, 2=SPA, 3=Salesforce, 4=Complex) with tiered argument sets
**Evidence**: docs/STATE_STEALTH_MATRIX.md, src/core/stealth.py
**Tags**: [scraping/stealth-tiers, infra/resource-optimization]

## Applicability Assessment

The most pattern-rich project across all analyses. Its maturity as a framework derivative demonstrates that the template works in production. Key innovations: Stop hooks, domain-specific validation hooks, .mcp.json for direct DB queries, AGENT_NOTES.md as persistent failure log, and the /ship command with auto change classification. All are directly portable to the template.
