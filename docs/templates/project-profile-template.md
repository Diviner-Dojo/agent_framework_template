---
project_name: "[Project Name]"
source: "[GitHub URL or local path]"
analyzed: "[YYYY-MM-DD]"
analysis_id: "[ANALYSIS-YYYYMMDD-HHMMSS-slug]"
tags: []
---

## Overview

[One-paragraph summary of what this project does, its tech stack, and why it was analyzed.]

## Technology Grid

| Dimension | Value |
|-----------|-------|
| Language | |
| Framework | |
| Database | |
| Testing | |
| CI/CD | |
| Deployment | |

## Notable Patterns

[Patterns discovered during analysis, scored on the 5-dimension rubric.]

## Solution Paths

Document HOW this project solved specific problems. Each entry captures the journey, not just the destination.

### Format

```
### [domain/sub-concept] — [Short title]

**Problem**: What needed solving
**Tried**: What approaches were attempted (including failures)
**Chosen**: What approach was ultimately used and why
**Evidence**: Where in the codebase this can be seen (file paths, PRs, commits)
**Tags**: [domain/sub-concept, domain/sub-concept]
```

### Example

```
### auth/session-management — Stateless JWT with refresh rotation

**Problem**: Needed session management without server-side state
**Tried**: Server-side sessions (rejected: scaling complexity), opaque tokens with Redis (rejected: infrastructure overhead)
**Chosen**: Stateless JWT with short-lived access tokens (15min) and rotating refresh tokens stored in httpOnly cookies
**Evidence**: src/auth/jwt_handler.py, PR #142, ADR-0023
**Tags**: [auth/session-management, security/token-handling]
```

## Applicability Assessment

[How relevant are this project's patterns to our work? What's directly adoptable vs. needs adaptation?]
