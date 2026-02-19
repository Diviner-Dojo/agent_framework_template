---
last_updated: "2026-02-19"
total_analyses: 3
patterns_evaluated: 26
patterns_adopted: 5
patterns_deferred: 9
patterns_rejected: 7
---

# Adoption Log (Learning Ledger)

This file tracks patterns discovered across external project analyses (`/analyze-project`). It serves as the template's learning memory — accumulating evidence across multiple reviews to identify which patterns are worth adopting.

## How This Works

1. Each `/analyze-project` run evaluates an external project and scores its patterns
2. Patterns scoring >= 20/25 are recommended for adoption
3. Patterns scoring 15-19 are deferred — tracked here for future consideration
4. Patterns scoring < 15 are rejected but noted briefly
5. **Rule of Three**: When a pattern is seen in 3+ independent projects, it gets +2 bonus to its score. Three sightings confirm a pattern is real, not coincidental.

## How to Read Entries

Each entry records:
- **Pattern name** and description
- **Source**: Which project(s) it was seen in
- **Score**: 5-dimension score (prevalence, elegance, evidence, fit, maintenance) out of 25
- **Sightings**: How many independent projects exhibit this pattern
- **Status**: ADOPTED / DEFERRED / REJECTED
- **Location**: Where it was placed in our project (if adopted)

## Pattern Log

*Entries are added by `/analyze-project` as patterns are evaluated.*
*Most recent entries appear at the top.*

### Pattern: Secret Detection in PreToolUse Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 23/25 (prevalence:5, elegance:4, evidence:5, fit:5, maintenance:4)
- **Status**: RECOMMENDED (pending implementation)
- **Decision**: Scans Write/Edit content for 6 secret patterns (API keys, AWS keys, JWT, GitHub PATs, PEM keys, exported secrets). Our security_baseline.md says "No secrets in code" but has no automated enforcement. This hook makes it automatic.
- **Date**: 2026-02-19

### Pattern: Hook-Based File Locking for Multi-Agent Conflict Prevention
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:4, fit:5, maintenance:4)
- **Status**: RECOMMENDED (pending implementation)
- **Decision**: Atomic lock via mkdir, 120s auto-expiry, session-based ownership. Prevents concurrent agent edits. Fills gap for multi-agent scenarios as we scale.
- **Date**: 2026-02-19

### Pattern: Pre-Commit Quality Gate Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 2 (also seen as PostToolUse Auto-Format in CritInsight)
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:5, maintenance:4)
- **Status**: RECOMMENDED (pending implementation)
- **Decision**: Intercepts git commit, injects verification reminder. We have quality_gate.py but nothing forces running it before commits. Adapt to call our quality gate script.
- **Date**: 2026-02-19

### Pattern: Pre-Push Main Branch Blocker
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:4, maintenance:5)
- **Status**: RECOMMENDED (pending implementation)
- **Decision**: Denies git push to main/master with remediation instructions. Simple, low-maintenance, prevents high-impact mistakes.
- **Date**: 2026-02-19

### Pattern: Tiered Workers with Focus Modes
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 19/25 (prevalence:3, elegance:5, evidence:3, fit:3, maintenance:5)
- **Status**: DEFERRED
- **Reason**: We already have 9 specialized agents with model tiers. Focus modes conflict with single-responsibility agent design (Principle #4).
- **Revisit if**: Agent count becomes unwieldy or token costs justify consolidation

### Pattern: Skill Auto-Suggestion via UserPromptSubmit Hook
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 18/25 (prevalence:3, elegance:5, evidence:3, fit:4, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Interesting concept but adds TypeScript dependency; skill-rules.json must stay in sync with skills directory
- **Revisit if**: Our skill library grows past 10+ playbooks

### Pattern: Swarm Plan→Execute→Review Pipeline
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 17/25 (prevalence:3, elegance:5, evidence:3, fit:3, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Architecturally sound but requires Beads external dependency. Our /plan and /build_module partially cover this. Study decomposition patterns without adopting Beads.
- **Revisit if**: We need structured multi-agent execution workflows

### Pattern: Session Handoff via State Files
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 17/25 (prevalence:3, elegance:4, evidence:3, fit:4, maintenance:3)
- **Status**: DEFERRED
- **Reason**: We already have session continuity hooks. Handoff.json adds inter-session comms but unclear if we need it yet.
- **Revisit if**: Multi-agent workflows require explicit session-to-session handoff

### Pattern: Comprehensive Permissions Allowlist
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 15/25 (prevalence:4, elegance:3, evidence:4, fit:2, maintenance:2)
- **Status**: REJECTED
- **Reason**: Mostly JS/Docker/Terraform-focused; must be customized per project. Python-relevant subset is small.

### Pattern: 65+ Categorized Skills Library
- **First seen**: claude-agentic-framework (2026-02-19)
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 1
- **Score**: 14/25 (prevalence:3, elegance:4, evidence:3, fit:2, maintenance:2)
- **Status**: REJECTED
- **Reason**: Most skills duplicate knowledge Claude already has. Our focused 6-playbook approach is more maintainable. Categorization scheme is worth noting.

### Pattern: Model-Tier Agent Assignment [RULE OF THREE ACHIEVED]
- **Third sighting**: claude-agentic-framework (2026-02-19) — explicit model: field in agent YAML frontmatter
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 3 (ContractorVerification, CritInsight, claude-agentic-framework)
- **Score**: 22/25 + 2 (Rule of Three bonus) = 24/25
- **Status**: ADOPTED (confirmed by Rule of Three)
- **Note**: Pattern validated across 3 independent projects. Confirmed as industry-standard practice for Claude Code frameworks.

### Pattern: Session Continuity Hooks [RULE OF THREE ACHIEVED]
- **Third sighting**: claude-agentic-framework (2026-02-19) — session-start-loader.sh + stop-validator.sh
- **Analysis**: ANALYSIS-20260219-035210-claude-agentic-framework
- **Sightings**: 3 (ContractorVerification, CritInsight, claude-agentic-framework)
- **Score**: 21/25 + 2 (Rule of Three bonus) = 23/25
- **Status**: ADOPTED (confirmed by Rule of Three)
- **Note**: Pattern validated across 3 independent projects. Confirmed as essential for agent workflow continuity.

### Pattern: PostToolUse Auto-Format Hook
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 24/25 (prevalence:5, elegance:5, evidence:4, fit:5, maintenance:5)
- **Status**: ADOPTED
- **Location**: `.claude/hooks/auto-format.sh` + `.claude/settings.json`
- **Decision**: Automates ruff formatting after every file edit. Zero cognitive overhead, set-and-forget. We already use ruff; this makes it automatic.
- **Date**: 2026-02-19

### Pattern: Model-Tier Agent Assignment
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 22/25 (prevalence:4, elegance:5, evidence:3, fit:5, maintenance:5)
- **Status**: ADOPTED
- **Location**: `.claude/agents/*.md` (all 9 agent files)
- **Decision**: Assigns opus to facilitator/architecture-consultant, sonnet to analysis agents, haiku to educator. Cost optimization with one-line-per-file change. 3/5 specialists converged.
- **Date**: 2026-02-19

### Pattern: Session Continuity Hooks
- **First seen**: ContractorVerification (2026-02-19) as "Session Initialization Protocol"
- **Also seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight (adopted), ANALYSIS-20260219-010900-contractor-verification (deferred as "Session Initialization Protocol")
- **Sightings**: 2
- **Score**: 21/25 (prevalence:5, elegance:4, evidence:3, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Location**: `.claude/hooks/pre-compact.ps1` + `.claude/hooks/session-start.ps1` + `BUILD_STATUS.md` + `.claude/settings.json`
- **Decision**: 2nd sighting of session persistence pattern. CritInsight's hook-based implementation is more mature than ContractorVerification's manual approach. Solves real problem of context loss across sessions. 4/5 specialists converged.
- **Supersedes**: "Session Initialization Protocol" (DEFERRED) — now ADOPTED with automated hooks.
- **Date**: 2026-02-19

### Pattern: Spec-to-Code Mapping Table
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 19/25 (prevalence:4, elegance:4, evidence:3, fit:4, maintenance:4)
- **Status**: DEFERRED
- **Reason**: Useful navigation aid but project is small enough that it's not yet needed
- **Revisit if**: Project grows to 10+ source modules or NLSpec-style specifications are added

### Pattern: Protocol-Based DI with Factory
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 19/25 (prevalence:5, elegance:4, evidence:5, fit:2, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Our project at ~345 LOC source would be over-engineered with full protocol DI
- **Revisit if**: We add 3+ components that need decoupling

### Pattern: Pipeline Context Object
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 16/25 (prevalence:4, elegance:4, evidence:3, fit:2, maintenance:3)
- **Status**: DEFERRED
- **Reason**: Our framework uses a simpler sequential approach; no multi-stage processing pipeline yet
- **Revisit if**: We build a multi-stage processing pipeline

### Pattern: Build Levels (L0/L1/L2)
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 14/25 (prevalence:3, elegance:4, evidence:2, fit:2, maintenance:3)
- **Status**: REJECTED
- **Reason**: Requires restructuring module hierarchy. Optimized for greenfield AI-built projects. Not justified at current project size.

### Pattern: 5-Layer Safety Validation
- **First seen**: CritInsight (2026-02-19)
- **Analysis**: ANALYSIS-20260219-033023-critinsight
- **Sightings**: 1
- **Score**: 13/25 (prevalence:3, elegance:4, evidence:2, fit:1, maintenance:3)
- **Status**: REJECTED
- **Reason**: Domain-specific to SQL validation. No multi-stage validation pipeline in our project to apply it to.

### Pattern: Custom Exception Hierarchy with HTTP Status Mapping
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 23/25 (prevalence:5, elegance:4, evidence:5, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Location**: `src/exceptions.py` + `src/error_handlers.py`
- **Decision**: Fills a concrete gap. Routes used bare HTTPException with no error_code, no structured details, no centralized logging. Three specialists converged on this recommendation.
- **Date**: 2026-02-19

### Pattern: Quality Gate Script
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 22/25 (prevalence:5, elegance:4, evidence:4, fit:5, maintenance:4)
- **Status**: ADOPTED
- **Location**: `scripts/quality_gate.py`
- **Decision**: Framework documents quality standards in 3 rules files but had no automated enforcement. Quality gate converts documented-but-unenforced standards into executable validation.
- **Date**: 2026-02-19

### Pattern: Session Initialization Protocol
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 18/25 (prevalence:3, elegance:4, evidence:3, fit:5, maintenance:3)
- **Status**: SUPERSEDED by "Session Continuity Hooks" (ADOPTED, 21/25)
- **Decision**: Originally deferred due to maintenance concerns. CritInsight's hook-based implementation (2nd sighting) solved the maintenance problem with automated PreCompact/SessionStart hooks. Adopted as "Session Continuity Hooks" above.

### Pattern: Four-Phase Implementation Protocol with Self-Grading
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 17/25 (prevalence:3, elegance:4, evidence:3, fit:3, maintenance:4)
- **Status**: DEFERRED
- **Decision**: Overlaps with existing education gates. Self-grading conflicts with Principle #4. Could be reframed as pre-review self-check.
- **Revisit if**: Agents demonstrate premature completion patterns

### Pattern: Config-Driven Pydantic SelectorSpec
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 16/25 (prevalence:3, elegance:5, evidence:5, fit:1, maintenance:2)
- **Status**: REJECTED
- **Decision**: Elegant design but deeply domain-specific. No resource location problem in our framework.

### Pattern: Stuck Record Recovery at Startup
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 16/25 (prevalence:4, elegance:3, evidence:4, fit:2, maintenance:3)
- **Status**: REJECTED
- **Decision**: Standard for stateful processing systems but our Todo API has no long-running operations.

### Pattern: AI-Powered Config Auto-Repair
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 15/25 (prevalence:2, elegance:4, evidence:3, fit:3, maintenance:3)
- **Status**: REJECTED
- **Decision**: Architecturally interesting but no configs to degrade and no health monitoring to detect degradation.

### Pattern: Version Bump Discipline
- **First seen**: ContractorVerification (2026-02-19)
- **Analysis**: ANALYSIS-20260219-010900-contractor-verification
- **Sightings**: 1
- **Score**: 13/25 (prevalence:4, elegance:2, evidence:3, fit:1, maintenance:3)
- **Status**: REJECTED
- **Decision**: Unnecessary ceremony for a framework template that is not a deployed service.
