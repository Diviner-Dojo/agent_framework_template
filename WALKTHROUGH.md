---
walkthrough_id: WALKTHROUGH-20260218-FULL
target: AI-Native Agentic Development Framework v2.1
audience: Developer onboarding to the framework
duration_estimate: 45-60 minutes
complexity: High (system architecture)
---

# Guided Walkthrough: AI-Native Agentic Development Framework

## Part 1: The Mental Model — What This Thing Actually Does

Before we go subsystem by subsystem, let's establish the mental model of what this framework does and why it exists.

### The Core Insight: Reasoning is the Product

This framework is built on a radical inversion: **code is the byproduct; reasoning is the primary artifact.**

In a traditional software project, you write code and hope someone documents it. In this framework, you're capturing the *thinking* that produces the code. Every decision — why you chose pattern A over pattern B, what trade-offs you made, what you learned from mistakes — is recorded immutably in the capture stack.

Why does this matter?

- **Onboarding**: New developers can see not just "what the code does" but "why we chose this approach"
- **Future modifications**: When you need to change something, you know the full reasoning history — including mistakes and dead ends
- **Accountability**: Every significant decision has a timestamp, a discussion ID, and the agents that reviewed it
- **Learning loop**: The framework analyzes its own decisions (quarterly `/meta-review`) and improves itself

This is *not* optional documentation. It's enforced at the command layer (Principle #2: "Capture must be automatic"). When you run `/review`, the entire discussion is recorded to events.jsonl before a single line of code is evaluated.

### The Quality Loop: Independence + Collaboration

Your framework also flips the review process: **independence prevents confirmation loops.**

Instead of one person writing code and another person approving it (creating a confirmation loop where both are anchored to the same solution), your framework:

1. You write code
2. The **facilitator** assesses risk and assembles a specialist team (dynamically — low-risk changes get fewer specialists)
3. **Multiple specialists analyze in parallel**, each with their own isolated context window
4. Each specialist brings a different lens (security, performance, testing, architecture, independent thinking)
5. The facilitator **synthesizes** findings from specialists who did NOT write the code
6. If genuine disagreement exists, the facilitator presents both sides with evidence — doesn't artificially resolve it

This prevents the groupthink that kills good judgment. One specialist might say "looks fine," while another (the independent-perspective agent) asks "but what if the assumption is wrong?" — and suddenly you catch a systemic risk.

The trade-off: this is more expensive (parallel specialist review costs tokens). But it's scoped by risk level — a typo fix doesn't trigger the full panel.

### The Capture Stack: Four Layers

Everything you capture flows through four layers:

```
Layer 1 (Immutable Files)
↓
events.jsonl + transcript.md
(append-only, sealed after discussion closes)
↓
Layer 2 (Relational Index)
↓
evaluation.db (SQLite)
(enables cross-discussion queries: "which patterns appear in 3+ projects?")
↓
Layer 3 (Curated Memory)
↓
memory/ directory
(human-approved patterns, rules, lessons — promoted from Layer 1 & 2)
↓
Layer 4 (Vector Store — Optional)
(scales when corpus exceeds ~1M tokens)
```

Why four layers?

- **Immutability (Layer 1)**: You can't rewrite history. A discussion sealed 3 months ago stays exactly as it was.
- **Querying (Layer 2)**: You need to ask cross-discussion questions: "Which external projects taught us the most about async patterns?"
- **Promotion (Layer 3)**: Not every discussion insight becomes permanent knowledge. Only human-approved patterns graduate to `memory/`.
- **Scaling (Layer 4)**: Eventually you'll have years of discussions. A vector store makes semantic search feasible.

This directly supports Principle #1 (reasoning is primary) and Principle #5 (ADRs are never deleted).

---

## Part 2: Agent Architecture — A Hub-and-Spoke Model

Now that you understand the philosophy, let's look at the agents that operationalize it.

### Why Agents + Why This Many?

You could implement review with a single monolithic model. But you chose **specialized agents**, each with:
- A distinct role (security specialist, performance analyst, etc.)
- A specific model tier (opus for complex reasoning, sonnet for analysis, haiku for mechanical tasks)
- Isolated context (no agent sees other agents' scratch work before generating findings)

Why? Because **specialization improves judgment and reduces cost**.

A generalist model reviewing code for "any issues" tends to flag everything (false positives) or miss specifics (false negatives). A security specialist trained on the security domain makes sharper threat assessment. A performance analyst catches O(N²) algorithms that a generalist might miss.

The isolation prevents anchoring: each agent forms independent conclusions before seeing others' findings.

### The Nine Specialists (and Why Each One)

**1. Facilitator (model: opus)** — The Orchestrator
- Role: Risk assessment, specialist team assembly, collaboration mode selection, synthesis
- Why opus (expensive): It makes judgment calls about *what to review* and *how deeply*. This requires complex reasoning about risk, business context, and team dynamics.
- Key decision: The facilitator doesn't review code directly. It manages the process.

Example: A low-risk config change gets Ensemble mode + one specialist. A security change gets Structured Dialogue mode + security-specialist + architecture-consultant + qa-specialist + independent-perspective. The facilitator chose this based on change type.

**2. Security Specialist (model: sonnet)** — Red Team Thinking
- Role: OWASP review, trust boundary analysis, auth/authz patterns, red-team thinking
- Activated when: Auth changes, API surface changes, data handling, dependency updates, user input processing
- Key decision: Uses "scoped adversarial mode" — thinks like an attacker, not a complainer
- Anti-pattern guard: Doesn't recommend OAuth2 + RBAC for single-user tools. Doesn't flag localhost-only connections as insecure. Matches security to threat model.

**3. QA Specialist (model: sonnet)** — Test Coverage + Edge Cases
- Role: Test strategy, coverage gaps, edge case identification, error handling verification
- Activated for: Every significant change (qa-specialist always participates)
- Key decision: Assesses both what's tested AND what should be tested but isn't
- Anti-pattern guard: Doesn't demand unit tests for trivial functions. Prioritizes testing where failure modes are highest-impact.

**4. Performance Analyst (model: sonnet)** — Algorithmic Efficiency
- Role: Algorithmic complexity, hot path identification, N+1 query detection, scalability assessment
- Activated when: Database changes, API endpoints, data processing, async patterns
- Key decision: Doesn't micro-optimize. Focuses on algorithmic improvements with highest ROI.
- Anti-pattern guard: Doesn't recommend caching for cold-path operations. Doesn't premature-optimize.

**5. Architecture Consultant (model: opus)** — Structural Alignment
- Role: Module boundary validation, ADR compliance, dependency analysis, architectural consistency
- Activated when: Architecture changes, new module structure, significant refactoring
- Key decision: Uses opus (expensive) because architectural decisions have long-term consequences — they warrant deep reasoning.
- Anti-pattern guard: Doesn't enforce architecture for architecture's sake. Evaluates pragmatism vs. purity.

**6. Independent Perspective (model: sonnet)** — Anti-Groupthink
- Role: Challenge assumptions, explore alternatives, pre-mortem, hidden failure modes
- Activated for: Medium+ risk changes (especially architecture)
- Key decision: Deliberately operates with minimal prior context. No anchoring to existing solutions.
- How it works: While other specialists say "this looks good," independent-perspective asks "but what if the assumption breaks?" and "have we explored alternative approaches?"
- Anti-pattern guard: Not a naysayer. Generates genuine alternatives, not just criticism.

**7. Docs-Knowledge (model: sonnet)** — Documentation Currency
- Role: ADR completeness, documentation quality, CLAUDE.md relevance, knowledge capture
- Activated for: Architecture changes, new patterns, framework updates
- Key decision: Surfaces when documentation lags behind code (or vice versa)
- Anti-pattern guard: Doesn't require documentation for every variable. Focuses on architectural decisions and major patterns.

**8. Project Analyst (model: sonnet)** — External Learning
- Role: External project pattern analysis, applicability scoring, adoption tracking
- Activated when: `/analyze-project` or `/discover-projects` commands run
- Key decision: Only agent that can spawn subagents (delegates to domain specialists for applicability assessment)
- How it works: Given an external project, scouts it, then dispatches security-specialist, qa-specialist, etc. to evaluate whether patterns are worth adopting
- Adoption logic: Patterns scored on 5 dimensions (prevalence, elegance, evidence, fit, maintenance) out of 25. Only ≥20/25 recommended. Rule of Three: patterns seen in 3+ projects get priority consideration.

**9. Educator (model: haiku)** — Knowledge Transfer
- Role: Walkthrough generation, quiz creation, mastery assessment, Bloom's taxonomy
- Activated when: Education gates fire (complex/high-risk changes before merge)
- Key decision: Uses haiku (cheap) because it's executing a known process, not discovering insights
- How it works:
  - **Walkthrough**: Progressive disclosure (overview → modules → functions → details), explaining *decisions* not *syntax*
  - **Quiz**: Bloom's taxonomy mix (60-70% Understand/Apply, 30-40% Analyze/Evaluate), at least 1 debug scenario + 1 change-impact question
  - **Explain-back**: Developer summarizes design trade-offs, failure modes, system interactions
- Anti-pattern guard: Doesn't use trick questions. Scaffolding fades as developer shows competence. Doesn't require explain-back for trivial changes.

### The Hub-and-Spoke Constraint

You have one key architectural rule: **Subagents CANNOT spawn other subagents, except project-analyst.**

Why? Because unbounded subagent spawning creates:
- Exponential context cost (10 agents spawn 10 more agents spawn 10 more...)
- Difficult-to-trace reasoning (who decided what?)
- Lost decisions (buried in nested conversations)

The exception is project-analyst because it has a *defined scope*: given an external project, scout it and dispatch specialists to evaluate applicability. The delegation is bounded and intentional.

---

## Part 3: The Rules Stack — What Agents Actually Enforce

Agents don't evaluate code in a vacuum. They evaluate against **documented standards** that are auto-loaded into every agent's context.

### Six Rules Files (Auto-Loaded Context)

**1. coding_standards.md** — Python conventions
- Python 3.11+ required
- All public functions must have type annotations
- Google-style docstrings for public functions/classes/modules
- No bare `except:` — always specific exceptions
- No mutable default arguments
- Use Pydantic at API boundaries, dataclasses internally
- Maximum function length: ~50 lines (guideline, not hard rule)

Why these standards?
- Type annotations catch errors at editor time, not runtime
- Google docstrings are parseable by documentation generators
- Specific exception handling prevents silent failures
- Pydantic at boundaries means you validate user input once, then trust internal data
- Small functions are easier to test and reason about

**2. testing_requirements.md** — pytest patterns
- >= 80% coverage target for new/modified code
- Unit tests for all business logic, integration tests for endpoints
- Edge cases always tested: empty inputs, boundary values, None, duplicates, not-found
- Tests must be deterministic (no flaky tests, no shared mutable state)
- Descriptive test names: `test_create_todo_with_empty_title_returns_422`
- Test markers: `@pytest.mark.uses_llm` (skipped by default, use `--run-llm`), `@pytest.mark.slow` (skipped by default, use `--run-slow`)

Why >= 80%?
- Below 80%, you catch most happy paths but miss error handling
- Above 90%, you're probably testing implementation details that will change
- 80% is the Goldilocks zone: catches real bugs without brittleness

**3. security_baseline.md** — Trust boundaries
- Validate all user input at API boundaries using Pydantic
- Use parameterized queries (no string interpolation in SQL)
- Never expose raw database errors to API consumers
- No secrets in source code or config files
- CORS explicitly configured (no wildcard `*`)
- Authentication required for non-public endpoints
- Rate limiting on auth endpoints
- Generic error messages to prevent information leakage

Why this baseline?
- Pydantic catches malformed input before it reaches your code
- Parameterized queries prevent SQL injection
- Hidden database errors prevent attackers from learning your schema
- Explicit CORS prevents cross-origin attacks
- Rate limiting on auth endpoints defeats brute-force attacks

**4. review_gates.md** — Quality thresholds
- Test coverage >= 80% for new/modified code
- No critical or high-severity security findings unaddressed
- All public functions must have docstrings
- All new modules must have module-level docstrings
- No failing tests
- Any architectural change requires an ADR
- Dependency additions require security-specialist review
- Medium+ risk changes require education gate (walkthrough → quiz → explain-back)

**5. commit_protocol.md** — The four-step commit dance
1. **Quality Gate** (automated pre-commit hook): formatting, linting, tests, coverage ≥ 80%
2. **Code Review** (required for code changes): `/review <files>` for multi-agent assessment
3. **Education Gate** (if recommended by review): walkthrough → quiz → explain-back
4. **BUILD_STATUS update**: Move task to "Recently Completed," update modified files

Why four steps?
- Step 1 catches mechanical errors (formatting, obvious bugs)
- Step 2 catches design issues (security, architecture, performance)
- Step 3 ensures developer understands what they wrote (Principle #6: "Education gates before merge")
- Step 4 bridges context windows (BUILD_STATUS persists state across Claude Code sessions)

**6. documentation_policy.md** — What gets documented where
- All architectural decisions → ADR in `docs/adr/`
- All multi-agent discussions → `discussions/` with events.jsonl + transcript.md
- All code reviews → review report in `docs/reviews/`
- All public APIs → docstrings in code + module-level docs
- All agent reflections → reflection files linked to discussions
- Sprint retrospectives → `docs/sprints/`

Format standard: **YAML frontmatter + Markdown body** for all artifacts.

Why this structure?
- ADRs track architectural reasoning over time (Principle #5: "never delete, only supersede")
- Discussions are immutable (Layer 1 capture)
- Review reports create accountability (Principle #4: "independence prevents confirmation loops")
- Docstrings stay with the code (developers see them immediately)
- Frontmatter enables programmatic querying (script can check `adr_id`, `status`, `date`)

### How Agents Use These Rules

When you run `/review`:
1. **Facilitator** loads all six rules files
2. Facilitator dispatches specialists (each with the same rules loaded)
3. **Security-specialist** checks code against security_baseline.md
4. **QA-specialist** checks tests against testing_requirements.md
5. **Architecture-consultant** checks module boundaries against review_gates.md (architectural gates)
6. **Docs-knowledge** checks ADRs against documentation_policy.md
7. Facilitator **synthesizes** findings into a single review report

Each agent is saying "here's what the code does" + "here's what the rules say" + "here's the gap" (if any).

The rules are never deleted (Principle #5), but they *can* be improved. If a review consistently surfaces a missing standard, it gets added to the rules files and all agents inherit it immediately.

---

## Part 4: The Capture Pipeline — How Reasoning Becomes Data

The capture pipeline is how you enforce Principle #2: "Capture must be automatic."

When you run `/review` or `/deliberate` or `/analyze-project`, here's what happens:

### Step 1: Create Discussion (create_discussion.py)
```
scripts/create_discussion.py \
  --mode "structured-dialogue" \
  --intensity "medium" \
  --risk-level "medium"
```

Creates a directory structure:
```
discussions/
  2026-02-18/
    DISC-20260218-143022-auth-refactor/
      metadata.json           ← risk_level, mode, intensity, created_at
      events.jsonl            ← append-only event log (starts empty)
```

And registers in SQLite:
```sql
INSERT INTO discussions
  (discussion_id, date, risk_level, collaboration_mode, intensity, status)
VALUES ('DISC-20260218-143022-auth-refactor', '2026-02-18', 'medium', 'structured-dialogue', 'medium', 'open')
```

**Why this structure?**
- Dated subdirectories make it easy to navigate by time
- `metadata.json` captures the *context* of the discussion (why was this medium-risk?)
- `events.jsonl` is append-only (guarantees immutability during the discussion)
- SQLite registration enables cross-discussion queries

### Step 2: Capture Each Agent Turn (write_event.py)

As each specialist analyzes and the facilitator synthesizes, every turn is captured:

```json
{
  "timestamp": "2026-02-18T14:30:45.123456",
  "agent": "security-specialist",
  "intent": "proposal",
  "content": "Found SQL injection vulnerability in user_id parameter...",
  "confidence": 0.95,
  "links": ["ADR-0003", "REV-20260215-HHMMSS"]
}
```

**Valid intents:**
- `proposal` — agent proposes a finding or recommendation
- `critique` — agent critiques a previous proposal
- `question` — agent asks a clarifying question
- `evidence` — agent provides supporting evidence (code snippet, test result, benchmark)
- `synthesis` — facilitator synthesizes multiple findings
- `decision` — decision maker affirms a decision
- `reflection` — agent reflects on the process or their own reasoning

Events are **append-only** to events.jsonl. You can never delete an event — only add new ones. This enforces Principle #5 (immutable history).

### Step 3: Close Discussion (close_discussion.py)

When the review completes:

```
scripts/close_discussion.py --discussion-id DISC-20260218-143022-auth-refactor
```

This script:

1. **Generate Transcript** (`generate_transcript.py`):
   ```
   Converts events.jsonl → transcript.md

   # Discussion: auth-refactor
   Date: 2026-02-18
   Risk Level: medium
   Mode: structured-dialogue

   ## Round 1: Security Review

   **security-specialist (proposal, confidence: 0.95)**
   Found SQL injection vulnerability in user_id parameter...

   [more events converted to readable markdown...]
   ```

2. **Ingest Events to SQLite** (`ingest_events.py`):
   ```sql
   INSERT INTO turns (discussion_id, agent, timestamp, intent, confidence, ...)
   VALUES ('DISC-...', 'security-specialist', ..., 'proposal', 0.95, ...)
   ```

   This enables queries like:
   - "Which agent has highest average confidence?"
   - "What intents do different agents favor?"
   - "What patterns appear across discussions?"

3. **Mark Closed**:
   ```sql
   UPDATE discussions SET status = 'closed' WHERE discussion_id = '...'
   ```

4. **Set Read-Only**:
   ```bash
   chmod a-w discussions/2026-02-18/DISC-.../events.jsonl
   ```

Once sealed, the discussion cannot be modified. It's immutable Layer 1.

### Step 4: Run Quality Gate (quality_gate.py)

This is the executable enforcement of the rules. It checks:

**Check 1: Formatting** — `ruff format --check`
- Enforces coding_standards.md conventions

**Check 2: Linting** — `ruff check`
- No bare except, no unused imports, no mutable defaults, etc.

**Check 3: Tests** — `pytest`
- All tests pass (no failing tests)

**Check 4: Coverage** — `pytest --cov=src --cov-fail-under=80`
- >= 80% coverage (from testing_requirements.md)

**Check 5: ADRs** — Custom check
- All ADRs have required frontmatter fields (adr_id, title, status, date, decision_makers, discussion_id)
- All ADRs have required sections (Context, Decision, Alternatives Considered, Consequences)
- Enforces documentation_policy.md

If any check fails, the commit is blocked. The quality gate is enforced **automatically** by a git pre-commit hook (`.claude/hooks/pre-commit-gate.sh`).

**Why automatic enforcement?**
- You can't accidentally commit code that doesn't meet standards
- The bar is objective (pass/fail) not subjective (opinion-based)
- Developers learn the standards immediately (hook feedback is instant)

---

## Part 5: Hooks — The Invisible Enforcers

You've implemented seven hooks that fire automatically on Claude Code events. These enforce your principles at the tool level.

### PreToolUse Hooks (Fire Before File Edits)

**1. File Locking + Secret Detection + Protected Files** (validate_tool_use.py)

When you write/edit a file:

```python
# 1. Atomic file lock (uses directory creation for atomicity)
lock_dir = Path(".claude/locks/path-to-file-being-edited.lock")
lock_dir.mkdir(parents=True, exist_ok=True)  # Creates lock
# ... do work ...
lock_dir.rmdir()  # Releases lock
```

**Why directory-based locking?**
- `mkdir` is atomic on all filesystems (POSIX + Windows)
- No race condition if multiple agents edit simultaneously
- 120-second auto-expiry prevents stale locks if an agent crashes

**2. Protected Files** — blocks edits to:
- `.env` — secrets management
- `.git/` — git internals
- `metrics/evaluation.db` — Layer 2 index
- `.claude/settings.json` — framework config

**Why block these?**
- `.env` could leak API keys
- `.git/` edits corrupt the repository
- `evaluation.db` is auto-generated (editing it is pointless)
- `.claude/settings.json` is framework configuration (should only be edited intentionally)

**3. Secret Scanning** — 12 regex patterns detected:
- API keys (generic pattern)
- AWS keys
- JWT tokens
- GitHub PATs
- Private keys
- Slack tokens
- Bearer tokens
- Anthropic API keys
- OpenAI API keys
- GCP API keys
- GCP OAuth tokens

Secret detection **flags** (doesn't hard-block) — human reviews and approves before the file is written. Test files are exempt.

**Why flag instead of block?**
- You might intentionally write a test with a fake secret (for testing secret scanning itself)
- You might store secrets in comments for documentation (bad practice, but sometimes necessary)
- Flagging prevents accidents while allowing intentional exceptions

**2. Pre-Commit Gate** (pre-commit-gate.sh)

When you run `git commit`:
- Injects reminder to run `python scripts/quality_gate.py` before committing
- Uses 5-minute cache to avoid nagging within same work session

If quality gate fails, git blocks the commit.

**3. Pre-Push Main Blocker** (pre-push-main-blocker.sh)

When you run `git push`:
- Blocks direct pushes to main/master branch
- Suggests branch-based workflow instead

**Why?** Prevents accidental push of incomplete work to main.

### PostToolUse Hooks (Fire After File Edits)

**4. Auto-Format** (auto-format.sh)

After every Write/Edit of a `.py` file:
```bash
python -m ruff format src/ tests/
python -m ruff check --fix src/ tests/
```

Enforces coding_standards.md automatically. Developer never sees "your formatting is wrong" — the formatter just fixes it.

**5. Lock Release** (release_lock.py)

After Write/Edit completes, releases the file lock.

### Session Lifecycle Hooks

**6. PreCompact** (pre-compact.ps1)

Before context compaction (when Claude Code hits token limits and needs to save state):
- Prompts you to update `BUILD_STATUS.md` with current task state
- Captures in-flight context (what you're working on, what's blocked, what's next)

**7. SessionStart** (session-start.ps1)

On session resume or post-compaction:
- Prompts you to read `BUILD_STATUS.md` to restore context
- Bridges context windows

**Why session hooks?**
- BUILD_STATUS.md is ephemeral (distinct from 4-layer capture stack)
- It preserves in-flight work (not completed decisions)
- When you resume a session, you immediately remember what you were doing

---

## Part 6: Commands — The User Interface

You've defined 12 slash commands. Each command invokes a workflow that uses the capture pipeline.

### Review & Deliberation Commands

**`/review <files>`** — Multi-agent code review
- Facilitator assesses risk
- Activates specialists dynamically (not all specialists for every change)
- Produces review report in `docs/reviews/REV-YYYYMMDD-HHMMSS.md`
- Captures discussion in `discussions/YYYY-MM-DD/DISC-.../`

**`/deliberate <topic>`** — Structured multi-agent discussion
- For architectural decisions, process improvements, not code-based
- Produces discussion transcript
- May result in ADR if major decision is made

### External Learning Commands

**`/analyze-project <path-or-github-url>`** — Evaluate external project patterns
- Project-analyst scouts the target project
- Dispatches specialists to evaluate applicability:
  - security-specialist: How do they handle auth/secrets?
  - qa-specialist: What's their testing strategy?
  - performance-analyst: What optimizations do they use?
  - architecture-consultant: How do they structure modules?
- Scores patterns on 5 dimensions (prevalence, elegance, evidence, fit, maintenance) out of 25
- Only patterns ≥ 20/25 are recommended
- Results tracked in `memory/lessons/adoption-log.md`

**`/discover-projects <search-query>`** — Find candidates on GitHub
- Searches GitHub for projects matching your domain
- Returns candidates to analyze via `/analyze-project`

### Code Generation & Planning Commands

**`/build_module <spec>`** — Generate code with integrated quality gates
- Takes a spec (natural language or structured)
- Generates code with tests
- Runs quality gate automatically
- No code is produced until quality gate passes

**`/plan <feature-or-sprint>`** — Spec-driven planning
- Takes a feature description
- Produces detailed spec with acceptance criteria
- May produce ADR if architectural decisions needed
- Captures discussion

**`/retro <sprint-name>`** — Sprint retrospective (meso loop)
- Analyzes discussions from a sprint
- Identifies patterns, improvements, lessons learned
- Updates `docs/sprints/SPRINT-NAME-retro.md`

**`/meta-review`** — Quarterly framework evaluation (macro loop)
- Evaluates the framework itself
- Assesses: agent effectiveness, rule adherence, capture quality
- May recommend changes to agents, rules, or commands
- Produces reflection in `memory/reflections/`

### Memory & Promotion Commands

**`/promote <discussion-id> <pattern-or-decision>`** — Graduate to Layer 3
- Requires human approval (Principle #7)
- Moves insight from Layer 1 (immutable discussions) to Layer 3 (curated memory)
- Updates `memory/` with pattern/decision/lesson
- Links back to discussion for traceability

**`/onboard <existing-project>`** — Integrate external project
- Initializes framework in an existing codebase
- Runs initial `/meta-review` to establish baseline
- Creates initial ADRs for major architectural decisions
- Produces onboarding report

---

## Part 7: The Application Code — The Subject

The framework also includes minimal application code (`src/`) to serve as the test subject. This is intentionally simple:

- **main.py** — FastAPI app with lifespan management
- **exceptions.py** — AppError hierarchy (NotFoundError, ValidationError, ConflictError)
- **error_handlers.py** — Centralized exception → JSON conversion
- **models.py** — Pydantic models for request/response validation
- **database.py** — SQLite layer
- **routes.py** — API endpoints (a simple Todo API)

**Why include application code?**

The framework needs a subject to review, test, and analyze. The Todo API serves this purpose. It's not the point — the framework is the point — but the framework needs something to govern.

---

## Part 8: How It All Connects — The Flow for a Code Change

Let's trace a typical code change from start to finish to see all the pieces working together.

### Scenario: You add authentication to the Todo API

**Phase 1: You Write Code**

```python
# src/auth.py (new file)
from fastapi import Depends, HTTPException
from src.models import User

async def get_current_user(token: str = Header(...)) -> User:
    # Validate token, return user
    ...

# src/routes.py (modified)
@app.post("/todos")
async def create_todo(todo: TodoCreate, user: User = Depends(get_current_user)):
    # Create todo for authenticated user
    ...
```

**Phase 2: Hooks Fire**

1. **PreToolUse: File Locking** — Lock acquired on src/auth.py
2. **PreToolUse: Secret Detection** — Token pattern detected, flagged (no hard block because it's a test)
3. **Write tool** — File written
4. **PostToolUse: Auto-Format** — ruff format + ruff check --fix run automatically
5. **PostToolUse: Lock Release** — Lock released

All automatic. No developer action needed.

**Phase 3: Developer Runs Quality Gate**

```bash
python scripts/quality_gate.py
```

Output:
```
Quality Gate
========================================
  PASS  Formatting (ruff format)
  PASS  Linting (ruff check)
  FAIL  Tests (pytest)  [no test coverage for new auth logic]
  FAIL  Coverage (>= 80%)
========================================
Quality Gate: FAILED (2/4 passed)
```

Developer writes tests. Runs quality gate again:

```
Quality Gate
========================================
  PASS  Formatting (ruff format)
  PASS  Linting (ruff check)
  PASS  Tests (pytest)
  PASS  Coverage (>= 80%)
  PASS  ADR completeness
========================================
Quality Gate: 5/5 passed
```

**Phase 4: Developer Runs `/review`**

```
/review src/auth.py src/routes.py
```

**What happens:**

1. **Facilitator** reads the changes and assesses risk:
   - "This is an authentication change" → High risk
   - Activates: security-specialist, qa-specialist, architecture-consultant, independent-perspective

2. **Create Discussion** (create_discussion.py):
   ```
   discussions/2026-02-18/DISC-20260218-153050-auth-implementation/
     metadata.json: risk_level=high, mode=structured-dialogue, intensity=high
     events.jsonl: (empty, ready to capture)
   ```

3. **Specialists Analyze in Parallel**:

   **security-specialist** (scoped adversarial mode):
   - Reviews Token validation: "Does it check expiration? Revocation?"
   - Reviews Error handling: "Are failed auth attempts logged? Rate-limited?"
   - Checks for common vulns: SQL injection in token lookup? Information leakage?
   - Produces finding: "Token not validated against revocation list — medium risk"

   **qa-specialist**:
   - Reviews test coverage: "Do we test expired tokens? Invalid tokens? Missing tokens?"
   - Checks edge cases: "What if token is empty string? Very long string? Null?"
   - Produces finding: "Missing edge case tests for invalid token formats"

   **architecture-consultant**:
   - Asks: "Should token validation be in middleware (applies to all endpoints) vs. in this endpoint?"
   - Checks: "Does this design align with ADR-0003 (auth architecture)?"
   - Produces finding: "Should be middleware, not per-endpoint, for consistency"

   **independent-perspective**:
   - Challenges assumption: "We assume token storage is secure. Is it?"
   - Explores alternatives: "Could we use OAuth2 instead of custom tokens?"
   - Pre-mortem: "What if token validation service goes down?"
   - Produces finding: "Dependency on external token validation — what's the fallback?"

4. **Write Events** (write_event.py):
   ```json
   {"timestamp": "...", "agent": "security-specialist", "intent": "proposal", "confidence": 0.90, "content": "Token not validated against revocation list..."}
   {"timestamp": "...", "agent": "qa-specialist", "intent": "proposal", "confidence": 0.95, "content": "Missing edge case tests..."}
   {"timestamp": "...", "agent": "architecture-consultant", "intent": "critique", "confidence": 0.85, "content": "Should be middleware..."}
   {"timestamp": "...", "agent": "independent-perspective", "intent": "question", "confidence": 0.75, "content": "What if token validation service goes down?..."}
   ```

5. **Facilitator Synthesizes**:
   - Deduplicates: security-specialist + qa-specialist both flagged token validation → one finding
   - Resolves contradictions: architecture-consultant's "use middleware" vs. current design → evidence-based
   - Produces overall verdict: **approve-with-changes**
   - Confidence score: 0.86 (weighted average of specialist confidences)
   - Required changes before merge:
     1. Add token revocation check (security-specialist, high severity)
     2. Add edge case tests (qa-specialist, medium severity)
     3. Move auth to middleware (architecture-consultant, medium severity)

6. **Close Discussion** (close_discussion.py):
   - Generates transcript.md (all events + synthesis in readable format)
   - Ingests events to SQLite (Layer 2 index)
   - Marks discussion closed
   - Sets events.jsonl read-only

7. **Produces Review Report** in `docs/reviews/REV-20260218-153050.md`:
   ```yaml
   ---
   review_id: REV-20260218-153050
   discussion_id: DISC-20260218-153050-auth-implementation
   risk_level: high
   collaboration_mode: structured-dialogue
   verdict: approve-with-changes
   confidence: 0.86
   agents: [facilitator, security-specialist, qa-specialist, architecture-consultant, independent-perspective]
   ---

   ## Summary
   Authentication implementation introduces high-risk changes. Specialist panel identified 3 required changes before merge.

   ## Findings by Specialist
   ### security-specialist (confidence: 0.90)
   - **High**: Token revocation not checked. Could allow use of revoked tokens.
   - Recommendation: Validate token against revocation list on each request.

   ### qa-specialist (confidence: 0.95)
   - **Medium**: Missing edge case tests (empty token, very long token, malformed token).
   - Recommendation: Add parametrized tests for invalid token formats.

   [more findings...]

   ## Required Changes Before Merge
   1. Add token revocation check (Security, high severity)
   2. Add parametrized edge case tests (Testing, medium severity)
   3. Move auth logic to middleware (Architecture, medium severity)

   ## Education Gate Recommendation
   HIGH — This is security-critical code. Recommend full education gate: walkthrough + quiz + explain-back.
   ```

**Phase 5: Developer Addresses Findings**

Developer reads the review report and makes changes:
- Adds revocation check
- Adds edge case tests
- Moves auth to middleware

Commits each change (quality gate re-runs automatically). Re-runs quality gate after all changes:

```bash
python scripts/quality_gate.py
```

All pass ✓

**Phase 6: Education Gate (If Recommended)**

Since the review recommended full education gate, developer runs:

```
/walkthrough src/auth.py
```

**Educator generates walkthrough:**

```markdown
# Walkthrough: Authentication Implementation

## Overview
You've added authentication to the Todo API using bearer tokens.

**Key Design Decision:** Token validation happens in middleware (applies to all routes) rather than per-endpoint. This ensures consistency and prevents accidentally missing auth checks on new routes.

**Why this approach?**
- Middleware runs before route handlers
- Single place to validate all tokens
- New routes inherit auth automatically (fail-safe)
- Follows ADR-0003 (centralized auth validation)

## Step 1: Token Validation Flow
[Progressive disclosure: overview → flow diagram → function details]

## Step 2: Revocation Handling
Token revocation is checked against an in-memory cache that's refreshed every 5 minutes.

**Trade-off:** 5-minute cache vs. immediate consistency
- Pro: Reduced database queries
- Con: 5-minute window where revoked tokens remain valid
- Decision: Acceptable for this use case (short-lived tokens + low impact of 5-min delay)

[more sections...]
```

Developer reads walkthrough and asks clarifying questions if needed.

Developer runs:

```
/quiz src/auth.py
```

**Educator generates quiz:**

```yaml
quiz_id: QUIZ-20260218-154200
module: auth
bloom_distribution: {understand: 7, apply: 3, analyze: 2}
pass_threshold: 0.70
```

Questions:

1. **[Understand]** Explain the data flow from a client sending a request to the token validation middleware executing. Where does the token come from? What happens if it's missing?

2. **[Apply]** Given a new endpoint `/users/{id}/profile`, trace how the auth middleware would handle it. Would a missing Authorization header cause 401 or 500?

3. **[Analyze]** Why did we choose to validate tokens in middleware instead of inside each route handler? What would break if we moved validation to individual routes?

4. **[Debug Scenario]** You see this test fail:
   ```python
   def test_expired_token_rejected():
       response = client.post("/todos", headers={"Authorization": "Bearer expired-token"})
       assert response.status_code == 401
   ```
   The test is getting 500 instead. What's the most likely cause?

5. **[Change Impact]** If we remove the revocation cache and check every token against the database on each request, what could break? (Hint: think about the request flow and database capacity.)

[more questions...]

Pass threshold: 70% (7/10 correct)

Developer answers questions. If passes, proceeds to explain-back.

```
/explain-back
```

**Prompt:**

```
Explain back to me:
1. The key design trade-off you made: Why token revocation cache (with 5-min delay) instead of immediate checking?
2. What's the failure mode if the token validation service is unavailable?
3. How does this auth system interact with the existing error handling?
```

Developer provides explanations in own words. Educator assesses understanding.

If all gates pass: ✓ Education gate complete.

**Phase 7: Commit**

Developer runs:

```bash
git commit -m "Add authentication with bearer tokens, centralized middleware validation"
```

**Pre-commit hook fires:**
1. Quality gate runs (all checks pass)
2. Pre-push blocker reminds developer to use branch-based workflow

Commit succeeds.

**Phase 8: Update BUILD_STATUS.md**

Developer updates session state:

```markdown
## Recently Completed
- [x] Add authentication with bearer tokens
  - Discussion: DISC-20260218-153050-auth-implementation
  - Review: REV-20260218-153050
  - Education: Walkthrough + Quiz + Explain-back (passed)
  - Commit: abc1234

## Modified Files
- src/auth.py (new)
- src/routes.py (modified)
- src/middleware.py (new)
- tests/test_auth.py (new)
- docs/adr/ADR-0004.md (new — auth architecture)
```

---

## Part 9: The Meta Loops — How the Framework Improves Itself

Beyond individual code changes, you've built three improvement loops:

### Micro Loop: Individual Change

(Just traced this above — /review → specialist feedback → education gate → commit)

### Meso Loop: Sprint Retrospective

At the end of a sprint, run:

```
/retro sprint-name
```

Facilitator analyzes all discussions from the sprint:
- What patterns emerged?
- Which specialists flagged the most issues?
- Did any recommendations get ignored? Why?
- What process improvements?

Produces `docs/sprints/SPRINT-NAME-retro.md` with:
- Metrics (number of changes reviewed, average risk level, average confidence)
- Patterns (e.g., "security issues appeared in 60% of API changes")
- Lessons (e.g., "independent-perspective agent caught 3 architectural issues others missed")
- Recommendations (e.g., "require architecture-consultant for any new endpoints")

### Macro Loop: Quarterly Meta-Review

Once a quarter, run:

```
/meta-review
```

Evaluates the framework itself:
- Are the 9 agents effective? Should any be added, removed, or repurposed?
- Are the 6 rules files still current? Any new standards needed?
- Is the capture pipeline working (discussions being sealed properly)?
- Are specialists over-flagging or under-flagging?

Produces reflection in `memory/reflections/` with recommendations for improving the framework.

If major changes needed (e.g., "add a new specialist for accessibility"), produces ADR in `docs/adr/`.

### External Learning Loop: Pattern Adoption

Continuously:

```
/discover-projects accessibility-testing
/analyze-project <found-project-1>
/analyze-project <found-project-2>
/analyze-project <found-project-3>
```

Patterns scored on 5 dimensions out of 25. Rule of Three: patterns appearing in 3+ projects get priority.

When a pattern scores ≥ 20/25 and appears in 3+ projects, run:

```
/promote <discussion-id> pattern-name
```

This graduates the pattern to Layer 3 (curated memory) and may trigger a new rule or agent enhancement.

**Example:** If you discover "accessibility testing" patterns in 3+ projects and they score ≥ 20/25:
1. Promote pattern to `memory/patterns/accessibility-testing.md`
2. Add accessibility checks to qa-specialist's responsibilities
3. Add "accessibility testing" standard to `testing_requirements.md`
4. All future reviews automatically include accessibility assessment

---

## Part 10: The Philosophy Behind the Design

Now that you understand each piece, let's step back and see the design principles:

### Principle 1: Reasoning is Primary

You inverted the usual software workflow. Instead of:
```
Code → (Hope for documentation) → Vague legacy knowledge
```

You build:
```
Reasoning (captured in discussions) → Code (output) → Knowledge (curated from discussions)
```

Why? Because **code tells you what was built; reasoning tells you why it was built that way.** If you need to change it in 2 years, the reasoning is more valuable than the code.

### Principle 2: Capture is Automatic

You don't *allow* discussions to go unrecorded. The capture happens at the command layer — when you run `/review`, a discussion directory is created before a single agent analyzes anything. There's no way to skip it.

Why? Because humans are bad at deciding what's worth recording. You think "oh, this small decision isn't important" — then 6 months later it's exactly what you need to know.

### Principle 3: Independence Prevents Groupthink

Most code review is serial (person A writes, person B reviews, they converge on one answer). You made it parallel (multiple agents analyze independently, then synthesize).

The independent-perspective agent specifically operates with minimal context — it's not anchored to your existing solution.

Why? Because when everyone's looking at the same code, they converge too quickly on "this looks fine." Independence preserves the chance that someone will ask "but what if the assumption breaks?" and catch a real issue.

### Principle 4: Specialization Improves Judgment

You didn't build a generalist review agent. You built 9 specialists, each trained on a domain (security, performance, testing, architecture, etc.).

Why? Because a generalist reviewing code for "any issues" tends to either over-flag (cry wolf) or under-flag (miss specifics). A specialist catches nuances.

### Principle 5: Architecture is Immutable

You don't delete ADRs. You supersede them with references. You don't rewrite discussions. You seal them after closure.

Why? Because architectural history is valuable. When you make a similar decision again in 3 years, you want to know why you chose differently before. Deleting creates amnesia.

### Principle 6: Education Gates Before Merge

You require developers to demonstrate understanding of complex code before it ships.

Why? Because code you don't understand breaks in ways you can't predict. If a developer can't explain the design trade-offs, they can't maintain it or adapt it.

### Principle 7: Promotion Requires Approval

Nothing automatically graduates from captured discussions to curated knowledge. A human has to affirm it.

Why? Because not every insight is universal. Some patterns are project-specific or temporally local. Promotion filters for knowledge that's general and durable.

### Principle 8: Least-Complex Intervention First

When improving the framework, you prefer prompt changes (cheapest, most reversible) before command changes before agent changes before architectural changes.

Why? Because **complexity has a cost**. Each additional layer of infrastructure is another thing that can break. Start simple, only escalate when proven necessary.

---

## Part 11: Summary — What You've Built

You've built a **reasoning-first development framework** that:

1. **Captures decisions immutably** across 4 layers (files → index → curated memory → vector store)
2. **Reviews code through specialized agents** that operate independently to prevent groupthink
3. **Enforces standards programmatically** via the quality gate and automated hooks
4. **Educates developers** on complex code before merge
5. **Improves itself** through micro (change), meso (sprint), and macro (quarterly) loops
6. **Learns from external projects** via pattern analysis and adoption tracking

The framework is **not** a project management tool or a code formatter. It's a system for **making your reasoning durable, testable, and reproducible**.

When you run `/review`, you're not just getting "approved" or "rejected." You're creating a timestamped, immutable record of specialist analysis that will be queryable 2 years from now. When you run `/meta-review`, the framework is reasoning about itself, not you manually reflecting.

---

## Next Steps: Verify Your Understanding

You now have a complete mental model of the framework. Let's verify it sticks:

Run the following quiz:

```
/quiz framework-architecture
```

The quiz will test:
- **Understanding**: Data flow through the capture stack, when each agent activates, what each hook prevents
- **Apply**: "If you add a new API endpoint, trace how /review would analyze it"
- **Analyze**: "Why does the project-analyst have permission to spawn subagents when other agents don't?"
- **Evaluate**: "Is 80% coverage the right threshold? Why not 75% or 90%?"
- **Debug**: "A developer runs `git push` and gets blocked. What happens next?"
- **Change Impact**: "If you remove the independent-perspective agent, what fails?"

Pass threshold: 70%

After the quiz, I'll ask you to explain back:
1. The core philosophy (why "reasoning is primary"?)
2. A design trade-off you made (e.g., why model tiering instead of single powerful model?)
3. How one subsystem reinforces another (e.g., how education gates prevent tech debt?)

---

## File References

Key files mentioned in this walkthrough:

- **`CLAUDE.md`** — Project constitution (principles, architecture)
- **`.claude/rules/*.md`** — Six rules files (auto-loaded to agents)
- **`.claude/agents/*.md`** — Nine specialist agent definitions
- **`scripts/quality_gate.py`** — Executable enforcement of rules
- **`scripts/create_discussion.py`** — Initiates capture pipeline
- **`scripts/write_event.py`** — Records individual turns
- **`scripts/close_discussion.py`** — Seals discussions immutably

---

This framework cohesively enforces 8 principles across multiple layers through a combination of agents, rules, hooks, and capture pipelines.

Now let's make sure your understanding is solid.

Ready for the quiz?
