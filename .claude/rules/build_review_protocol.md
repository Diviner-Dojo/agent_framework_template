# Build Review Protocol

Enforces Principle #4 (independence prevents confirmation loops) within `/build_module` execution.

Mid-build checkpoint reviews ensure that the agent generating code is not the sole evaluator during builds, not just at commit time.

## Checkpoint Triggers

After generating code for a build task, the facilitator evaluates whether the task matches any trigger category. If it does, a checkpoint fires.

| Trigger Category | Condition | Specialists (2 max) |
|---|---|---|
| **New module** | 2+ new files created under `src/` | architecture-consultant, qa-specialist |
| **Architecture choice** | Pattern selection, abstraction layer, dependency direction | architecture-consultant, independent-perspective |
| **Database schema** | New/modified SQLAlchemy models, Alembic migrations | performance-analyst, security-specialist |
| **Security-relevant** | Auth, encryption, token handling, input validation | security-specialist, architecture-consultant |
| **API routes** | New FastAPI endpoints, middleware, dependency injection | architecture-consultant, qa-specialist |
| **External API** | HTTP clients, third-party service integrations | security-specialist, performance-analyst |
| **UI flow / user-facing changes** | New user-facing pages, navigation changes, state feedback | ux-evaluator, qa-specialist |

If a task matches multiple categories, the facilitator selects the **two most relevant specialists** — never more than two per checkpoint. Priority order when categories overlap: security-relevant always claims one slot; the other slot goes to the highest-specificity remaining category.

**Cost rationale**: Checkpoints use sonnet-tier dispatch (not the agent's default tier) because the 200-word response cap and focused scope make full-tier unnecessary. This is an intentional cost optimization, not an error.

## Exempt Tasks (No Checkpoint)

- Project scaffolding (directory creation, initial config)
- Dependency configuration (pyproject.toml, requirements.txt changes only)
- Pure test writing (no production code changes)
- Theme, style, or cosmetic UI-only changes
- Documentation and comment updates
- Final verification / quality gate runs

## Checkpoint Protocol

### Round 1
1. Facilitator dispatches exactly 2 specialists in parallel via `Task()`.
2. Each specialist reviews the task's code and responds with:
   - **APPROVE**: No concerns. Under 200 words.
   - **REVISE**: Specific, actionable change request. Under 200 words.
3. Facilitator captures both responses via `write_event.py` with tags `checkpoint,task-N`.
4. If both APPROVE → continue to next task.
5. If any REVISE → implement the requested changes.

### Round 2 (max)
6. After implementing revisions, re-dispatch **only** the specialist(s) who requested REVISE.
7. Specialist responds APPROVE or REVISE (under 200 words).
8. If APPROVE → continue.
9. If still REVISE → capture the unresolved concern with `risk_flags: ["unresolved-checkpoint"]`, log it, and continue. Flag for developer in the build summary.

### Hard Limit
- **NEVER exceed 2 checkpoint iterations per task.** After Round 2, the build continues regardless. Unresolved concerns are surfaced in the build summary, not blocked on.

## Specialist Prompt Template

When dispatching a checkpoint specialist, use this prompt structure:

```
Build Checkpoint Review: <discussion_id>
Task: <task number and title>
Trigger: <trigger category>

Review this code from your specialist perspective. This is a mid-build checkpoint, not a full review.

Focus on:
- Whether the implementation approach is sound
- Whether it aligns with existing ADRs and patterns
- Any risks that would be expensive to fix later

<code content or file paths>

Respond with APPROVE or REVISE (under 200 words).
```

## Capture

All checkpoint events go into the build's discussion (created at build start):
- Specialist responses → `write_event.py` with intent `critique`, tags `checkpoint,task-N`
- Bypass notes (exempt tasks) → `write_event.py` with intent `decision`, tags `checkpoint-bypass,task-N`
- Unresolved concerns → `write_event.py` with intent `critique`, tags `checkpoint,task-N`, risk_flags `unresolved-checkpoint`
