---
adr_id: ADR-0016
title: "Progressive-disclosure restructuring of the always-loaded instruction corpus"
status: accepted
date: 2026-05-20
decision_makers: [facilitator, architecture-consultant, docs-knowledge, security-specialist]
discussion_id: DISC-20260520-161826-efficiency-ledger-ratification
supersedes: null
risk_level: high
scope: framework
confidence: 0.85
tags: [token-efficiency, progressive-disclosure, claude-md, rules, skills]
---

## Context

The always-loaded instruction corpus — `CLAUDE.md` (~8.9K tokens) plus 15 `.claude/rules/*.md` files (~13.1K tokens) ≈ **22K tokens** — loads on every turn and is **re-paid in every dispatched specialist's context window** (custom subagents inherit the full corpus; only built-in Explore/Plan skip it). Authoritative Anthropic guidance: keep CLAUDE.md under ~200 lines; rules without `paths:` frontmatter load every session, rules with `paths:` load only when matching files are touched; skills load on-demand; `@imports` do not reduce context; instructions that *must* run belong in hooks. The AI cost model is shifting from unlimited tokens toward near-cost, and this framework is a hub whose efficiency compounds across three derived projects.

Verified in Phase 0b: enforcement is **mechanical** (hooks, `quality_gate.py`, capture scripts never read the rules `*.md` files), so relocating rule *text* changes zero enforcement. A per-item cost/value ledger was built and **ratified by an independent panel** (architecture-consultant, docs-knowledge, security-specialist) in DISC-20260520-161826 with no dissent on the core reduction.

## Decision

Restructure the always-loaded corpus via progressive disclosure (target ~22K → ~2K tokens/turn):

- **Slim `CLAUDE.md`** from 432 → ~170 lines; add an **Always-On Invariants** block, a **Workflow Sequencing** block (including a ~95%-confidence ask-before-building gate), and a keyword-rich **Rules Index**.
- **KEEP always-loaded:** `autonomous_workflow` (compressed) — the anti-skip gate has no mechanical enforcer.
- **PATH-SCOPE** (load on matching files): `coding_standards` (`**/*.py`), `testing_requirements` (`tests/**`), `security_baseline` (`src/**` + `scripts/**`).
- **SKILL (on-demand):** `failure_taxonomy`, `notification_protocol`, `cross_agent_dispatch_protocol`, `multi_instance_protocol`, `framework_doc_sync`, `micro_fix_protocol`, `review_gates` (shared by /review, /ship, /retro), `pre_build_search` (shared by /plan, /build_module).
- **FOLD:** `build_review_protocol` → `/build_module` (single owner).
- **CUT to a pointer:** `commit_protocol` (hook-enforced), `documentation_policy` (duplicated; pointer names its two cross-refs).
- **Promote security invariants** (trust-boundary sanitization; untrusted out-of-band reply handling) into Always-On Invariants *before* deferring their source rules.
- **Move** the agent-roster table + capture-pipeline DAG to `docs/` (AGENT_ARCHITECTURE.md, CAPTURE_PIPELINE.md, HOOKS.md), referenced by pointer.

Co-migration to derived projects follows in a later phase, preserving each project's domain rules/agents.

## Alternatives Considered

### Alternative 1: Trim only obvious bloat, keep everything always-loaded (~25% cut)
- **Pros**: lowest risk, minimal behavioral change.
- **Cons**: leaves ~16K tokens/turn on the table, re-paid per dispatch; no progressive disclosure.
- **Reason rejected**: under-serves the efficiency goal the cost model now demands.

### Alternative 2: `@`-import the rules from a slim CLAUDE.md
- **Pros**: organizational tidiness.
- **Cons**: Anthropic docs confirm `@`-imports still load at launch — zero token savings.
- **Reason rejected**: does not reduce context.

### Alternative 3: Convert ALL rules to skills, including `autonomous_workflow`
- **Pros**: maximal per-turn reduction.
- **Cons**: the anti-skip gate has no mechanical enforcer; deferring it re-opens the Principle #4 bypass it was written to prevent.
- **Reason rejected**: unsafe — it shapes a gating decision before any command/hook fires.

## Consequences

### Positive
- ~90% cut to always-loaded tokens, multiplied across every specialist dispatch and every derived project; better instruction adherence (shorter files); ends the risk→specialist table triplication (via the `route.py` pilot, Phase 6).

### Negative
- Relocated rules depend on the model summoning them when relevant; mitigated by a keyword-rich Rules Index, always-loaded invariants for safety-critical lines, and cold-start entries for failure recovery.
- More skill files to maintain; offset by single-source-of-truth gains.

### Neutral
- Mechanical enforcement (hooks/quality_gate/capture) is unchanged.
- ADRs and docs written before 2026-05-20 reference several rules by their former `.claude/rules/` paths; those files were relocated to `.claude/skills/` (or path-scoped) by this ADR. Historical ADRs are NOT edited (Principle #5) — map old rule filenames to skill slugs via the FRAMEWORK_SPECIFICATION §14 "Skill Reference Documents" table. `memory/lessons/adoption-log.md` and `FRAMEWORK.md` retain historical paths for the same reason.

## Linked Discussion
See: discussions/2026-05-20/DISC-20260520-161826-efficiency-ledger-ratification/
