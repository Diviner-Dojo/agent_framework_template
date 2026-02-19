---
description: "Onboard an existing project into the framework. Implements the 'takeover' protocol: codebase mapping, reverse-engineered ADRs, standards proposal, stabilization, and debt ledger."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[project path to onboard]"
---

# Existing Project Onboarding (Takeover Protocol)

You are acting as the Facilitator. This protocol brings an existing codebase into the framework without rewriting everything.

## Step 1: Codebase Mapping

Analyze the project structure:
1. Map the directory structure and identify modules
2. Identify dependencies between modules
3. Identify risk zones: high complexity, low test coverage, frequent changes
4. List the tech stack: languages, frameworks, databases, tools
5. Check for existing CI/CD configuration
6. Check for existing tests and their coverage

Present the mapping to the developer for validation.

## Step 2: Reverse-Engineered ADRs

Analyze the existing architecture and create baseline ADRs:
1. Read the main modules and identify architectural patterns in use
2. For each significant pattern, create an ADR documenting:
   - What appears to be the current approach
   - Why it was likely chosen (best guess from code evidence)
   - Mark with: "Based on code analysis, this appears to be the rationale..."
3. Save ADRs to `docs/adr/ADR-NNNN-<slug>.md`
4. Present to developer for correction and approval

## Step 3: Standards Proposal

Based on the codebase analysis, propose realistic standards:
1. Coding standards calibrated to what the codebase currently does (don't impose standards it can't meet)
2. Testing requirements based on current coverage
3. Documentation policy based on current documentation level
4. Security baseline based on current security practices
5. Save proposed standards for developer review

## Step 4: Stabilize (First Sprint)

1. Set up `CLAUDE.md` with project-specific constitution
2. Set up `.claude/rules/` with the approved standards
3. Set up `.claude/agents/` with the core agent roster
4. Set up `metrics/evaluation.db` via `python scripts/init_db.py`
5. Ensure tests run and pass (fix broken tests)
6. Set up minimum review pipeline (ensemble mode for all changes)

## Step 5: Debt Ledger

1. Tag all known issues identified during mapping
2. Classify using Fowler's Technical Debt Quadrant:
   - Prudent Deliberate: Known trade-offs (document in ADR)
   - Prudent Inadvertent: Issues discovered through analysis
   - Reckless Deliberate: Shortcuts without documentation (high priority)
   - Reckless Inadvertent: Issues from ignorance (highest priority — education gap)
3. Prioritize by impact: production risk > developer friction > architectural drift
4. Save debt ledger to `docs/debt-ledger.md`

## Step 6: Gradual Enforcement (Boy Scout Rule)

Explain to the developer:
- Strict gates only apply to **changed areas** — no need to fix the whole codebase
- Every PR leaves touched code slightly better than it found it
- Enforcement coverage expands naturally over time
