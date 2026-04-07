# Failure Taxonomy

> Named failure classes with recovery steps and escalation paths.
> Replaces tribal knowledge with a single reference for what can break and what to do about it.
> Inspired by Claw Code's structured failure taxonomy (ideas-only, ANALYSIS-20260407-002600-claw-code).

## Why This Exists

Unnamed failures collapse to "something went wrong." You can't build recovery habits, agent retry logic, or retrospective analysis on unnamed failures. This taxonomy gives every known failure mode a name, a recovery path, and an escalation point.

## Failure Classes

### HOOK_BLOCK

**What**: A PreToolUse hook rejects a Write/Edit operation.
**Common causes**: File is protected (.env, .git/, evaluation.db, settings.json), secret pattern detected in content, file lock held by another operation.
**Recovery**:
1. Read the hook output — it states the specific reason (protected file, secret pattern, or lock conflict)
2. If secret detected: remove the secret from content, use environment variables instead
3. If protected file: this is intentional — do not attempt to bypass
4. If lock conflict: wait 120s for auto-expiry, or check if another agent operation is in progress
**Max retries**: 1 (after fixing the content)
**Escalation**: If the hook blocks after fixing the stated cause, report to developer — the hook regex may be over-matching

### QUALITY_GATE_FAIL

**What**: `python scripts/quality_gate.py` exits non-zero.
**Common causes**: Formatting (ruff), lint errors, test failures, coverage below 80%, missing ADR, missing review report.
**Recovery**:
1. Run `python scripts/quality_gate.py --fix` to auto-remediate formatting and lint
2. If tests fail: read the test output, fix the code, re-run
3. If coverage low: add tests for uncovered paths
4. If review missing: run `/review` before committing
**Max retries**: 2 (with fixes between each)
**Escalation**: If the same check fails after 2 fix attempts, stop and diagnose — the fix may be addressing a symptom, not the root cause

### CAPTURE_PIPELINE_ERROR

**What**: A capture script (create_discussion.py, write_event.py, close_discussion.py, ingest_events.py) fails.
**Common causes**: Discussion ID not found, SQLite database locked, malformed event data, discussion already closed.
**Recovery**:
1. Check the error message for the specific script and cause
2. If discussion not found: verify the ID matches an existing directory in `discussions/`
3. If database locked: wait and retry — another script may be writing
4. If discussion already closed: you cannot write events to a closed discussion — this is by design
**Max retries**: 1
**Escalation**: If SQLite errors persist, check `metrics/evaluation.db` integrity with `python -c "import sqlite3; sqlite3.connect('metrics/evaluation.db').execute('PRAGMA integrity_check').fetchone()"`

### REVIEW_PENDING

**What**: Code changes exist but no `/review` has been run before commit.
**Common causes**: Developer or agent forgot the review step, or the change was incorrectly classified as docs-only.
**Recovery**:
1. Stop — do not commit
2. Run `/review` on the changed files
3. Address any blocking findings
4. Then proceed with commit
**Max retries**: N/A — this is a process gate, not a retryable error
**Escalation**: None — this is always recoverable by running the review

### EDUCATION_DEFERRED

**What**: An education gate (walkthrough + quiz) was required but deferred by the developer.
**Common causes**: Time pressure, low-risk assessment, developer already familiar with the code.
**Recovery**:
1. Log the deferral in the retro (automatic via capture pipeline)
2. The deferred gate must be completed before the next phase begins, or formally re-deferred with documented rationale (Principle #6)
**Max retries**: N/A — deferral is a deliberate choice, not an error
**Escalation**: If the same education gate is deferred twice consecutively, flag in the next retro as a pattern

### SESSION_STATE_LOST

**What**: BUILD_STATUS.md is stale or missing after compaction, causing the agent to lose context about in-progress work.
**Common causes**: Pre-compact hook didn't fire, agent didn't update BUILD_STATUS.md before compaction, file was accidentally overwritten.
**Recovery**:
1. Check `git log --oneline -10` for recent commit messages — they describe completed work
2. Check `discussions/` for the most recent open discussion
3. Check `docs/reviews/` for the most recent review report
4. Reconstruct the current state from these sources and update BUILD_STATUS.md
**Max retries**: N/A — this is a reconstruction task
**Escalation**: If no artifacts exist to reconstruct from, ask the developer what was in progress

### COMMIT_HOOK_FAIL

**What**: The git pre-commit hook blocks a commit.
**Common causes**: Quality gate check failed (formatting, lint, tests, coverage), or the 5-minute verification cache is stale.
**Recovery**:
1. Run `python scripts/quality_gate.py --fix` to fix formatting and lint
2. Run `python scripts/quality_gate.py` to verify all checks pass
3. Re-attempt the commit (the cache will be fresh)
**Max retries**: 2
**Escalation**: If the hook blocks after the quality gate passes cleanly, check whether the cache file (`.quality_gate_cache`) has a valid timestamp

### PUSH_BLOCKED

**What**: The pre-push hook blocks a push to main/master.
**Common causes**: Attempting to push directly to the main branch instead of using a feature branch and PR.
**Recovery**:
1. Create a feature branch: `git checkout -b feature/<description>`
2. Push the feature branch: `git push -u origin feature/<description>`
3. Create a PR via `gh pr create`
**Max retries**: N/A — this is a workflow correction, not a retry
**Escalation**: None — the hook is working as intended

## Cross-Reference: Claw Code Operational Failures

The following failure modes were documented in Claw Code's ROADMAP (22 items from autonomous development dogfooding). Entries marked with **[RELEVANT]** have analogues in our framework. Entries marked with **[NOT APPLICABLE]** address problems specific to their persistent CLI architecture.

### Relevant to Our Framework

- **Session state ambiguity** (their item #20): "working vs blocked vs finished vs truly stale" — maps to our SESSION_STATE_LOST. Their solution: machine-derived state classification. Our mitigation: BUILD_STATUS.md with incremental summary merging.
- **Opaque failure surfaces** (their item #22): Generic error messages that hide whether the fault was auth, session corruption, command dispatch, or runtime panic. Maps to our need for named failure classes (this taxonomy).
- **Stale-branch noise masking real regressions** (their item #7): Before running broad tests, check if the branch is behind main. We don't have multi-branch parallel work yet, but this is worth noting if we move toward parallel build lanes.
- **Recovery loops too manual** (their pain point #4): "restart worker, accept trust prompt, re-inject prompt, detect stale branch, retry failed startup, classify infra vs code failures manually." Maps to our recovery steps being tribal knowledge — now addressed by this taxonomy.
- **Truth split across layers** (their pain point #2): State distributed across tmux, event streams, git, tests, and plugin runtime. Analogous to our state split across BUILD_STATUS.md, discussions/, metrics/, and git — which is why we have the four-layer capture stack.

### Not Applicable to Our Framework

- Worker boot fragility (trust prompts, shell misdelivery) — specific to persistent CLI session management
- Plugin/MCP lifecycle failures — we don't manage MCP servers
- Branch lock collisions — we use sequential workflow, not parallel lanes
- Prompt misdelivery detection — our agents receive prompts via Task(), not terminal injection
- Lane event schema — specific to their multi-lane orchestration model
