---
analysis_id: "ANALYSIS-20260219-042113-self-learning-agent"
discussion_id: "DISC-20260219-041249-analyze-self-learning-agent"
target_project: "https://github.com/daegwang/self-learning-agent"
target_language: "TypeScript"
target_stars: 2
agents_consulted: [project-analyst, architecture-consultant, security-specialist, docs-knowledge]
patterns_evaluated: 7
patterns_recommended: 2
analysis_date: "2026-02-19"
---

## Project Profile

- **Name**: self-learning-agent (slagent)
- **Source**: https://github.com/daegwang/self-learning-agent
- **Tech Stack**: TypeScript 5.4, Node.js ESM, zero runtime dependencies, filesystem-based storage (JSONL + JSON)
- **Size**: ~4,014 LOC across 20 source files in 7 subdirectories
- **Maturity**: v0.1.0, single git commit, no tests, no CI/CD, no ADRs, no CHANGELOG. Well-written README. Published to npm. Launched prototype, not production system.
- **AI Integration**: None in the codebase itself. The project IS tooling for AI agents but has no AI-assisted development artifacts (.claude/, CLAUDE.md, etc.).

### Tech Stack Details

- Runtime: Node.js ESM with NodeNext module resolution
- Language: TypeScript 5.4, strict mode, targeting ES2022
- Dependencies: Zero runtime deps. Only devDependencies: `typescript ^5.4.0`, `@types/node ^20.11.0`
- Storage: Filesystem-based — JSONL for events, JSON for state, no database
- AI invocation: Child process spawn of `claude` or `codex` CLI binaries

### Key Files Examined

| File | Significance |
|------|-------------|
| `src/analyzer/context-builder.ts` | Token budget allocation + priority-based event compression + secret redaction |
| `src/rules/patcher.ts` | Backup-before-modify + atomic revert + conflict detection |
| `src/types.ts` | Rule status lifecycle state machine (proposed/approved/applied/rejected/reverted) |
| `src/adapter/registry.ts` | Adapter registry pattern for multi-agent observation |
| `src/adapter/types.ts` | Adapter interface definition |
| `src/watcher/bootstrap.ts` | Git history bootstrapping as session reconstruction |
| `src/analyzer/reviewer.ts` | LLM response parsing, stdin-based prompt delivery |
| `src/watcher/signals.ts` | User intervention detection via timing gaps |
| `src/store/index.ts` | Filesystem store with retention/pruning |
| `src/watcher/ignore.ts` | Custom gitignore-compatible pattern matcher |
| `README.md` | Storage layout documentation, config schema table |

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.87)

Surveyed the full project. Identified 6 candidate patterns and 4 anti-patterns. The project is a filesystem watcher daemon that observes AI coding agent sessions (Claude, Codex), detects failures and user interventions, sends session context to an AI reviewer, and proposes rule updates to agent instruction files (CLAUDE.md, AGENTS.md). Notable design choices: zero runtime dependencies (all storage is filesystem-based), AI invocation via child process spawn rather than SDK, and a typed adapter registry for multi-agent-tool observation.

The project's core value proposition — automated learning from coding sessions — is interesting but orthogonal to our framework. The implementation patterns, however, contain some transferable techniques.

### Architecture Consultant (confidence: 0.82)

Evaluated 5 patterns. Primary finding: Backup-Before-Modify with Atomic Revert (21/25) fills a real gap. We write to `.claude/rules/`, `CLAUDE.md`, and `memory/` with no rollback path beyond manual `git checkout`. The pattern is three Python functions (~50 lines total). Also evaluated Token Budget Allocation (19/25, deferred — our prompts don't overflow yet) and Rule Status Lifecycle (18/25, deferred — useful concept but low priority). Rejected Adapter Registry (17/25, wrong problem domain) and Git History Bootstrapping (11/25, not applicable).

### Security Specialist (confidence: 0.88)

Primary finding: Redact-Before-AI-Send (22/25) addresses a critical gap. Our `/analyze-project` reads external project files and sends content raw to specialist agents. Those files can contain API keys, AWS credentials, GitHub PATs, Slack tokens, PEM blocks. The slagent redactor has 9 regex patterns with key-name preservation (shows `API_KEY= [REDACTED]` not just `[REDACTED]`). This is DISTINCT from our existing PreToolUse write-time secret detection — that prevents writing secrets to disk; this prevents sending secrets to the LLM. Also flagged path traversal vulnerability in `patcher.ts` — AI-generated `targetFile` joined to cwd without validation.

### Documentation & Knowledge (confidence: 0.79)

Near-threshold finding: Storage Layout Documentation (19/25). Our `CLAUDE.md` documents the four-layer architecture conceptually but omits concrete storage formats. New users must read scripts to understand the data model. The slagent README's storage layout section is well-structured and could serve as a model for adding a "Storage Formats" section to our CLAUDE.md documenting events.jsonl field schema, discussion directory lifecycle, and SQLite table structure.

---

## Pattern Scorecard

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|---------|
| Redact-Before-AI-Send | 5 | 4 | 4 | 5 | 4 | 22/25 | **ADOPT** |
| Backup-Before-Modify with Atomic Revert | 4 | 5 | 3 | 5 | 4 | 21/25 | **ADOPT** |
| Storage Layout Documentation | 4 | 4 | 3 | 4 | 4 | 19/25 | DEFER |
| Token Budget Allocation | 4 | 4 | 3 | 4 | 4 | 19/25 | DEFER |
| Rule Status Lifecycle (reverted state) | 3 | 4 | 3 | 4 | 4 | 18/25 | DEFER |
| Adapter Registry | 3 | 4 | 3 | 3 | 4 | 17/25 | SKIP |
| Git History Bootstrapping | 2 | 3 | 2 | 2 | 2 | 11/25 | SKIP |

No Rule of Three bonuses apply — all patterns are first sightings in our adoption log.

---

## Recommended Adoptions

*Only patterns scoring >= 20/25.*

### Redact-Before-AI-Send (Score: 22/25)

- **What**: Before sending external file content to AI specialist agents, apply regex-based redaction for 9 secret types (API keys, AWS credentials, GitHub PATs, Slack tokens, PEM blocks, Bearer headers, generic hex secrets, base64 high-entropy strings, connection strings). Preserve variable/key names for debugging context (`API_KEY= [REDACTED]` not just `[REDACTED]`).
- **Where it goes**: `scripts/redact_secrets.py` — utility function called by `/analyze-project` during prompt assembly. Also augment existing `.claude/hooks/detect_secrets.py` with Slack (xox*) and Bearer header patterns.
- **Why it scored high**: Prevalence 5 (every project that sends external content to LLMs faces this), Fit 5 (drops directly into our existing analyze-project prompt assembly). This is DISTINCT from our adopted PreToolUse write-time detection — that prevents writing secrets; this prevents sending secrets.
- **Implementation notes**: One Python function (~30 lines), 9 compiled regex patterns. Apply before any external file content is assembled into specialist agent prompts. Must include tests for each pattern type plus key-name preservation behavior.
- **Sightings**: 1 (first sighting; related "Secret Detection in PreToolUse Hook" is a different pattern — write-time vs. send-time)

### Backup-Before-Modify with Atomic Revert (Score: 21/25)

- **What**: Before writing to framework files (.claude/rules/, CLAUDE.md, memory/), copy the current file to a timestamped backup. Provide `restore_latest()` to find and restore the most recent backup, and `detect_conflicts()` to pre-check whether target content still exists before patching.
- **Where it goes**: `scripts/backup_utils.py` — utility providing `backup_file()`, `restore_latest()`, `detect_conflicts()`. Called by `/promote` and any framework file modification workflow.
- **Why it scored high**: Elegance 5 (three functions, ~50 lines total), Fit 5 (we write to framework files with no rollback path beyond manual git checkout).
- **Implementation notes**: Security precondition — validate target path is within project root using `pathlib.Path.resolve()` before any file operation (addresses path traversal anti-pattern found in source). Retention: tie to existing review retention policy (90 days). Backup location: `.claude/hooks/.backups/` (gitignored).
- **Sightings**: 1 (first sighting)

---

## Anti-Patterns & Warnings

### Path Traversal in AI-Generated File Targets

- **What**: `resolveRulePath()` joins `cwd` with AI-generated `rule.targetFile` without path containment validation
- **Where seen**: `src/rules/patcher.ts:18-24`
- **Why it's bad**: A manipulated AI response suggesting `../../.bashrc` resolves outside the project directory. Could write to arbitrary filesystem locations.
- **Our safeguard**: If we adopt Backup-Before-Modify, mandate `pathlib.Path.resolve()` containment check. Our existing `validate_tool_use.py` hook already blocks writes to `.env` and `.git/` but doesn't do general path containment.

### Zero Tests on Security-Critical Code

- **What**: No test files exist anywhere in the project. LLM response parsing, file writing, and secret detection regex patterns are completely untested.
- **Where seen**: Entire project
- **Why it's bad**: The most brittle and security-sensitive code paths have zero regression protection.
- **Our safeguard**: Our testing requirements mandate >= 80% coverage. Any patterns we adopt must include tests.

### Bare `catch {}` Throughout

- **What**: `catch { /* skip */ }`, `catch { return [] }`, `catch { }` — errors swallowed silently in polling and store code
- **Where seen**: `src/adapter/claude.ts`, `src/store/index.ts`, `src/watcher/index.ts`
- **Why it's bad**: Silent failures in file operations mask data loss and corruption.
- **Our safeguard**: Our coding standards prohibit bare `except:`. Any adopted code must always log suppressed errors at minimum DEBUG level.

### Flat File Store with O(n) Scan

- **What**: `getRecentSessions()` reads all JSON files, parses each, sorts, and slices. No index.
- **Where seen**: `src/store/index.ts:61-76`
- **Why it's bad**: Degrades with hundreds of sessions. O(n) parse on every query.
- **Our safeguard**: Our SQLite Layer 2 correctly solves this. This observation validates our architectural choice.

---

## Deferred Patterns

### Storage Layout Documentation (Score: 19/25)

- **What**: Add concrete storage format documentation to CLAUDE.md — events.jsonl field schema, discussion directory lifecycle, SQLite table structure
- **Why deferred**: Evidence 3 (documentation format, not a code pattern), and one point below threshold
- **Revisit if**: New contributors report confusion about data model, or onboarding friction is observed

### Token Budget Allocation (Score: 19/25)

- **What**: Divide token budget across content categories (events 40%, instructions 30%, system 20%, rules 10%) with failure-priority sort within event budget
- **Why deferred**: Our prompts don't currently overflow. The failure-priority sort applies to streaming event logs, not our structured discussion artifacts
- **Revisit if**: Specialist agent prompts hit truncation errors, or discussions grow beyond ~100 events

### Rule Status Lifecycle — `reverted` State (Score: 18/25)

- **What**: Add REVERTED status to adoption log entries, tracking patterns that were adopted and then found harmful and removed
- **Why deferred**: Low priority — we haven't yet had an adoption we needed to revert. Documentation format change, not a code change
- **Revisit if**: We revert an adopted pattern and discover the log can't represent that state

---

## Specialist Consensus

- **Agents that agreed**: All 3 specialists converged on the negative finding — the project's complete lack of tests on security-critical code is notable and reinforces our testing requirements. All agreed our SQLite Layer 2 is the correct alternative to flat file stores.
- **Notable disagreements**: Architecture-consultant and security-specialist disagreed on Backup-Before-Modify scope. Architecture rates adoption cost Low; security requires path containment validation as a precondition. Resolved: adopt with mandatory path validation.
- **Strongest signal**: Redact-Before-AI-Send (22/25) is the highest-value finding. It addresses a real, unmitigated gap in our `/analyze-project` workflow — external file content is currently sent raw to specialist agents with no secret filtering.
