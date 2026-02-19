---
id: ANALYSIS-20260219-035210-claude-agentic-framework
type: external-project-analysis
project: dralgorhythm/claude-agentic-framework
url: https://github.com/dralgorhythm/claude-agentic-framework
date: "2026-02-19"
discussion: DISC-20260219-035210-analyze-claude-agentic-framework
patterns_evaluated: 10
patterns_recommended: 4
patterns_deferred: 4
patterns_rejected: 2
---

## External Project Analysis: claude-agentic-framework

### Executive Summary

**claude-agentic-framework** is a drop-in framework for Claude Code that provides parallel agent swarms, specialized personas, 65+ reusable skills, hook-based automation, and the Beads issue tracker for multi-agent coordination. It represents a mature, production-oriented approach to multi-agent orchestration with strong emphasis on parallel execution, conflict prevention, and session management.

The framework is **complementary but architecturally different** from ours. Where our framework emphasizes *reasoning capture* and *deliberation as the primary artifact*, this framework emphasizes *shipping velocity* and *parallel execution throughput*. Key areas of interest: its hook-based automation system, swarm coordination with file locking, model-tier worker assignments, and skill auto-suggestion via hooks.

### Project Profile

| Dimension | Detail |
|-----------|--------|
| **Language** | Bash, TypeScript (hooks), Markdown (skills/agents/commands) |
| **Structure** | Pure Claude Code configuration framework (no application code) |
| **Size** | ~100 files, 65+ skills, 5 agents, 9 commands, 9 hooks |
| **Maturity** | Active development, well-documented, installable via curl |
| **License** | Not specified in repo |

### Architecture Comparison

| Aspect | Our Framework | claude-agentic-framework |
|--------|---------------|--------------------------|
| **Primary goal** | Reasoning capture, decision lineage | Shipping velocity, parallel execution |
| **Agent model** | 9 specialists + facilitator | 5 workers + 9 persona commands |
| **Collaboration** | 5-mode spectrum (Ensemble → Adversarial) | Swarm patterns (Plan → Execute → Review) |
| **Capture** | 4-layer stack (files, SQLite, memory, vector) | Beads issue tracker + git sync |
| **Quality gates** | Python script (ruff, pytest, coverage) | Hook-enforced pre-commit checks |
| **Session mgmt** | Hook-based (pre-compact, session-start) | Hook-based (session-start, stop-validator) |
| **Skills** | 6 reference playbooks | 65+ context-triggered skills |
| **Hooks** | 2 (auto-format, session continuity) | 9 hooks covering full lifecycle |
| **Model tiers** | opus/sonnet/haiku per agent | haiku (explore), sonnet (build/review), opus (architect) |

---

## Pattern Evaluations

### Pattern 1: Hook-Based File Locking for Multi-Agent Conflict Prevention

**Description**: PreToolUse hook intercepts Write/Edit operations, acquires atomic file locks via `mkdir` (race-condition safe), denies concurrent edits from different sessions, auto-expires locks after 120 seconds, and releases on session stop.

**Implementation**: `pre-tool-use-validator.sh` — ~130 lines of bash handling lock acquisition, protected file enforcement, and secret detection in a single hook.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 4 | File locking is standard in concurrent systems; hook-based is Claude Code-specific |
| Elegance | 5 | Atomic mkdir for lock acquisition is elegant and race-condition safe |
| Evidence | 4 | Well-tested in swarm workflows; automatic expiry prevents deadlocks |
| Fit | 5 | We already have hooks infrastructure; this fills a gap for multi-agent scenarios |
| Maintenance | 4 | Self-cleaning locks; only bash dependency; integrates with existing hook system |
| **Total** | **22/25** | **RECOMMENDED** |

**Recommendation**: Adopt. We don't currently have conflict prevention for concurrent agent edits. This pattern is lightweight and addresses a real gap as we scale to more complex multi-agent workflows.

---

### Pattern 2: Secret Detection in PreToolUse Hook

**Description**: Before any Write/Edit operation, scans content for 6 secret patterns (API keys, AWS keys, JWT tokens, GitHub PATs, private keys, exported secrets). Skips test files to reduce false positives. Uses `ask` permission decision to flag without hard-blocking.

**Implementation**: Integrated into `pre-tool-use-validator.sh` alongside file locking.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 5 | Standard security practice; pre-commit secret scanning is industry norm |
| Elegance | 4 | Clean regex patterns; smart test file exemption; `ask` vs `deny` is good UX |
| Evidence | 5 | 6 well-known secret patterns cover most common leaks |
| Fit | 5 | We have security baseline rules but no automated enforcement at write-time |
| Maintenance | 4 | Regex patterns may need occasional updates for new token formats |
| **Total** | **23/25** | **RECOMMENDED** |

**Recommendation**: Adopt. Our `security_baseline.md` says "No secrets in source code" but has no automated enforcement. This hook makes the rule automatic. Combine with file locking into a single PreToolUse hook.

---

### Pattern 3: Skill Auto-Suggestion via UserPromptSubmit Hook

**Description**: TypeScript hook that intercepts user prompts, matches against a `skill-rules.json` registry of keyword/intent/file patterns, and surfaces relevant skills as contextual suggestions before the agent begins work. Skills are prioritized (critical/high/medium/low).

**Implementation**: `skill-activation-prompt.ts` (~160 lines TypeScript) + `skill-rules.json` registry.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 3 | Novel for Claude Code; conceptually similar to IDE code actions |
| Elegance | 5 | Clean TypeScript implementation; regex intent matching; priority grouping |
| Evidence | 3 | Depends on quality of skill-rules.json; no metrics on suggestion acceptance |
| Fit | 4 | We have skills/playbooks but no auto-suggestion; requires TypeScript runtime |
| Maintenance | 3 | Must maintain skill-rules.json in sync with skills directory |
| **Total** | **18/25** | **DEFERRED** |

**Reasoning**: Interesting concept but adds TypeScript dependency to our Python-focused framework. The maintenance cost of keeping `skill-rules.json` in sync with skills is non-trivial. Worth revisiting when our skill library grows larger.

---

### Pattern 4: Swarm Plan → Execute → Review Pipeline

**Description**: Three-phase pipeline: `/swarm-plan` launches 3-6 parallel explorer agents for research, produces decomposed plan tracked as Beads issues. `/swarm-execute` fans out up to 8 parallel builder agents, each claiming a Bead issue. `/swarm-review` launches 5 parallel reviewers (security, perf, arch, tests, quality). Run review 2-3x until clean.

**Implementation**: Three slash commands (`swarm-plan.md`, `swarm-execute.md`, `swarm-review.md`) orchestrating 5 worker agent types with model-tier optimization.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 3 | Multi-agent swarm patterns are emerging but not yet standard |
| Elegance | 5 | Clean separation of concerns; well-defined handoff protocol between phases |
| Evidence | 3 | Documented but no performance metrics or case studies |
| Fit | 3 | Our framework has /review and /deliberate but lacks /plan→/execute pipeline |
| Maintenance | 3 | Requires Beads external dependency; complex coordination surface |
| **Total** | **17/25** | **DEFERRED** |

**Reasoning**: The three-phase pipeline is architecturally sound and our framework could benefit from a more structured plan→execute flow. However, the Beads dependency is heavy and our existing /plan and /build_module commands partially cover this. Worth studying the decomposition patterns and handoff protocols without adopting Beads.

---

### Pattern 5: Pre-Commit Quality Gate Hook

**Description**: PreToolUse hook that intercepts `git commit` commands and injects a verification reminder. Auto-detects project type (Python/TS/Go/Rust) and available quality tools. Uses a time-based state file (5-minute validity) to avoid re-checking within the same session.

**Implementation**: `pre-commit-verification.sh` — ~150 lines detecting project tooling and injecting `additionalContext`.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 5 | Pre-commit checks are universal best practice |
| Elegance | 4 | Smart auto-detection of tooling; time-based caching avoids repetition |
| Evidence | 4 | Prevents commits without quality verification |
| Fit | 5 | We have quality_gate.py but no hook to enforce running it before commits |
| Maintenance | 4 | Standard bash; project detection heuristics cover common cases |
| **Total** | **22/25** | **RECOMMENDED** |

**Recommendation**: Adopt. We already have `scripts/quality_gate.py` but nothing forces agents to run it before committing. This hook bridges that gap. Adapt to call our quality gate script directly.

---

### Pattern 6: Pre-Push Main Branch Blocker

**Description**: PreToolUse hook that detects `git push` commands targeting main/master branch and denies them with a remediation message instructing branch-based workflow.

**Implementation**: `pre-push-main-blocker.sh` — ~75 lines of bash with pattern matching for explicit and implicit push-to-main scenarios.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 5 | Branch protection is universal; hook-level enforcement is Claude Code-specific |
| Elegance | 4 | Covers multiple push patterns (explicit, implicit, with flags) |
| Evidence | 4 | Standard practice; prevents accidental force-pushes to main |
| Fit | 4 | We don't currently enforce branching strategy via hooks |
| Maintenance | 5 | Simple, stable bash script; rarely needs updates |
| **Total** | **22/25** | **RECOMMENDED** |

**Recommendation**: Adopt. Simple, low-maintenance hook that prevents a high-impact mistake. Fits our security baseline principles.

---

### Pattern 7: Session Handoff via State Files

**Description**: Session start/stop hooks maintain state in `.claude/hooks/.state/` — tracking active sessions, swarm agent count, and handoff messages between sessions. On session start, loads Beads status and detects active agents. On stop, releases locks, warns about uncommitted changes, syncs Beads.

**Implementation**: `session-start-loader.sh` + `stop-validator.sh` + `.state/handoff.json`.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 3 | Session continuity is emerging pattern; handoff.json is novel |
| Elegance | 4 | Clean JSON state files; auto-cleanup of stale sessions (24h) |
| Evidence | 3 | Depends on Beads for full value; handoff concept is promising |
| Fit | 4 | We already have session hooks; handoff mechanism would enhance them |
| Maintenance | 3 | State file management adds operational complexity |
| **Total** | **17/25** | **DEFERRED** |

**Reasoning**: We already adopted Session Continuity Hooks from our CritInsight analysis. The *handoff.json* concept adds inter-session communication but we'd need to evaluate whether this solves a real problem for our workflows. The swarm detection (counting active agents) is interesting for future multi-agent work.

---

### Pattern 8: Tiered Worker Agents with Focus Modes

**Description**: Five worker agent types (explorer, builder, reviewer, researcher, architect) each assigned a specific model tier (haiku/sonnet/opus) and tool subset. Workers support focus modes (builder: implementation/testing/refactoring; reviewer: quality/security/performance) specified in the orchestrator prompt.

**Implementation**: 5 agent markdown files with YAML frontmatter specifying `model` and `tools`.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 3 | Model-tier assignment is emerging; focus modes are novel |
| Elegance | 5 | Clean separation via frontmatter; focus modes reduce agent count |
| Evidence | 3 | Logical but no cost/performance metrics shared |
| Fit | 3 | We already have 9 specialized agents; model tiers already adopted |
| Maintenance | 5 | Minimal — markdown files with clear structure |
| **Total** | **19/25** | **DEFERRED** |

**Reasoning**: We already adopted Model-Tier Agent Assignment from the CritInsight analysis. The *focus mode* concept (one agent, multiple modes) is interesting but conflicts with our single-responsibility agent design. Our 9 agents are already specialized; combining reviewer + security into one agent with modes would lose independent perspective.

---

### Pattern 9: Comprehensive Permissions Allowlist in settings.json

**Description**: Exhaustively enumerated permissions allowlist with categorized comments. Covers 200+ specific Bash command patterns across file ops, git, GitHub CLI, Docker, Terraform, Node.js, and build tools. Includes explicit deny list for destructive operations.

**Implementation**: `.claude/settings.json` — ~260 lines of granular Bash permissions.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 4 | Best practice for Claude Code; most projects have minimal permissions |
| Elegance | 3 | Comprehensive but verbose; comment-based categorization is good |
| Evidence | 4 | Reduces permission prompts significantly; improves developer experience |
| Fit | 2 | Our framework is Python-focused; most of these are for JS/Docker/Terraform |
| Maintenance | 2 | Must maintain for each new tool/command; tends to grow unbounded |
| **Total** | **15/25** | **REJECTED** |

**Reasoning**: While comprehensive, this is mostly a convenience feature that must be customized per project. The Python-relevant subset (ruff, pytest, git) is small and we can adopt those specific permissions without the full 200+ line allowlist. The deny list pattern for destructive ops is worth noting.

---

### Pattern 10: 65+ Categorized Skills Library

**Description**: Skills organized by domain (architecture, core-engineering, design, languages, operations, product, security) with YAML frontmatter (name, description, allowed-tools) and markdown body. Each skill is a self-contained reference document covering workflows, checklists, and patterns.

**Implementation**: `~70 SKILL.md` files across 7 category directories.

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Prevalence | 3 | Large skill libraries are emerging for Claude Code frameworks |
| Elegance | 4 | Clean YAML+markdown format; good categorization; some include resources/ |
| Evidence | 3 | Breadth is impressive but unclear how often skills are actually invoked |
| Fit | 2 | Most skills are language-specific (React, Swift, Kotlin, Terraform) |
| Maintenance | 2 | 65+ files to keep current; many are generic knowledge Claude already has |
| **Total** | **14/25** | **REJECTED** |

**Reasoning**: The sheer volume is impressive but most skills duplicate knowledge Claude already possesses. Our focused playbook approach (6 skills covering security, testing, performance, patterns, ADRs) is more maintainable. The interesting insight is the *categorization scheme* and *YAML frontmatter format*, which we could adopt for our existing skills if we expand them.

---

## Cross-Pattern Insights

### Novel Patterns Worth Watching

1. **Beads Issue Tracker**: Git-native issue tracking designed for agent coordination. Interesting alternative to our discussion capture system for work item tracking. Worth watching as the ecosystem matures.

2. **Queen-Worker Swarm Pattern**: One orchestrator agent decomposes and assigns; multiple workers claim and execute in parallel. Similar to our facilitator pattern but more execution-focused.

3. **Two Hats Rule** (from code-quality): "Never mix refactoring and optimization in the same session." Simple discipline rule that could be added to our coding standards.

4. **Decision Reversibility Classification**: "Two-Way Door vs One-Way Door" framework from `/swarm-plan`. Determines required artifact depth based on decision reversibility. Aligns with our exploration intensity concept but with a different framing.

### Architectural Differences (Why We Diverge)

1. **Reasoning vs Shipping**: Their framework optimizes for code throughput; ours optimizes for decision quality. Neither is wrong — different problem spaces.

2. **Capture Model**: Their capture is in Beads (issue-level tracking). Ours is in discussions (event-level recording with JSONL). Our model captures more granular reasoning; theirs captures more actionable work items.

3. **Agent Independence**: They use focus modes (one agent, multiple personas). We use independent specialists (Principle #4: independence prevents confirmation loops). Their approach is more token-efficient; ours is more robust against bias.

### Rule of Three Tracking

| Pattern | Sightings | Projects |
|---------|-----------|----------|
| Model-Tier Agent Assignment | 3 | ContractorVerification (implied), CritInsight, claude-agentic-framework |
| Session Continuity Hooks | 3 | ContractorVerification, CritInsight, claude-agentic-framework |
| Pre-Commit Quality Enforcement | 2 | CritInsight (PostToolUse auto-format), claude-agentic-framework (PreToolUse commit gate) |
| Secret Detection at Write-Time | 1 | claude-agentic-framework |
| File Locking for Concurrency | 1 | claude-agentic-framework |
| Push-to-Main Protection | 1 | claude-agentic-framework |

**Rule of Three achieved**: Model-Tier Agent Assignment and Session Continuity Hooks have now been seen in 3 independent projects. This confirms these are real, validated patterns. Both are already adopted.

---

## Summary

| Pattern | Score | Status |
|---------|-------|--------|
| Secret Detection Hook | 23/25 | RECOMMENDED |
| File Locking Hook | 22/25 | RECOMMENDED |
| Pre-Commit Quality Gate Hook | 22/25 | RECOMMENDED |
| Pre-Push Main Blocker Hook | 22/25 | RECOMMENDED |
| Tiered Workers with Focus Modes | 19/25 | DEFERRED |
| Skill Auto-Suggestion Hook | 18/25 | DEFERRED |
| Swarm Plan→Execute→Review Pipeline | 17/25 | DEFERRED |
| Session Handoff State Files | 17/25 | DEFERRED |
| Comprehensive Permissions Allowlist | 15/25 | REJECTED |
| 65+ Skills Library | 14/25 | REJECTED |

**4 patterns recommended for adoption**, all hook-based automation that fills gaps in our current enforcement layer. The common theme: our framework has *documented standards* but this framework has *automated enforcement*. The recommended hooks bridge that gap.
