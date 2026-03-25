---
discussion_id: DISC-20260315-165653-feature-discovery-guidance-deliberation
started: 2026-03-15T16:57:06.346858+00:00
ended: 2026-03-15T17:01:14.319673+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective, ux-evaluator]
total_turns: 7
---

# Discussion: DISC-20260315-165653-feature-discovery-guidance-deliberation

## Turn 1 — facilitator (evidence)
*2026-03-15T16:57:06.346858+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Developer wants the framework AI to know about its own features and suggest them to users, making the framework easier to use. It should answer questions about how to use the framework and suggest things while it is being used.
- **Files/scope**: Proposed new files: .claude/rules/feature_discovery_guidance.md, .claude/skills/framework-guide/SKILL.md, .claude/commands/guide.md. Affects CLAUDE.md, FRAMEWORK_SPECIFICATION.md, and doc sync artifacts.
- **Developer-stated motivation**: The framework has 17 commands, 11 agents, 7 skills, 11 rules, and 7 hooks but no mechanism to help users discover or learn about them interactively. Users must read large documents to understand what is available.
- **Explicit constraints**: Must not annoy people. Must be toggleable (can be turned off). Should answer questions when asked AND suggest things proactively while working.

---

## Turn 2 — architecture-consultant (proposal)
*2026-03-15T16:59:59.030255+00:00 | confidence: 0.82*
*tags: deliberation, architecture, feature-discovery*

## Architecture Analysis

### Findings

**Finding 1 (Medium — drift)**: The proposed rule introduces a NEW rule archetype — 'advisory nudge' — with no precedent among the 11 existing rules (which are all gates, standards, protocols, or policies). This requires explicit ADR documentation.

**Finding 2 (Medium — pattern-inconsistency)**: The toggle mechanism has no precedent in the framework. Rules are loaded or not loaded — there is no conditional activation pattern. Simplest toggle: conversational (user says 'turn off guidance', model respects it). No infrastructure needed.

**Finding 3 (Low — coupling)**: The skill creates maintenance coupling — every command/rule/agent change requires updating the guide. Must be added to framework_doc_sync.md sync points.

**Finding 4 (Low — overlap)**: Minimal overlap with existing rules. Commit_protocol and autonomous_workflow remind about process gates; the proposed rule reminds about feature availability. Different categories. But the rule should explicitly scope itself to feature discovery and exclude process enforcement.

**Finding 5 (Info)**: /onboard and /guide are complementary. Cross-reference them in both directions.

### Key Recommendation
Start with Skill + Command only (Phase 1). Defer the proactive Rule to Phase 2 after observing whether users need proactive nudges. The rule carries the most architectural novelty and risk. This aligns better with Principle #8 and the philosophy of 'promotion is earned.'

Requires ADR for the full system, especially if Phase 2 proceeds.

---

## Turn 3 — ux-evaluator (proposal)
*2026-03-15T17:00:14.819000+00:00 | confidence: 0.88*
*tags: deliberation, ux, feature-discovery*

## UX Analysis

### Blocking Findings

**Finding 1 (HIGH — emotional-design)**: The 'User creates 3+ files without /plan' trigger fires when the user is IN FLOW and making autonomous decisions. Interrupting productive flow with 'have you considered /plan?' is supervision, not discovery. This is the highest-risk Clippy vector. REMOVE this trigger entirely.

**Finding 2 (HIGH — emotional-design)**: The 'Tip: ...' format introduces a second voice inside the agent's response. It signals a help system interjecting itself. Replace with contextual integration — weave suggestions into the natural response as closing sentences in a single voice. Example: 'If this grows beyond two files, /plan will give you specialist design review before you write code.'

### Advisory Findings

**Finding 3 (Medium — cognitive-load)**: BUILD_STATUS.md toggle is session-scoped and resets. Users who turn off tips must do so again each session. Separate session silencing from persistent opt-out (user memory).

**Finding 4 (Medium — dead-end)**: First-session 'mention /guide' is a pointer to a pointer. Instead, name the top 3 commands directly: '/plan, /review, and /build_module are the most important for daily work.'

**Finding 5 (Medium — accessibility)**: No expertise-level adaptation. Experts get novice tips. Use a minimal signal (prior discussion count) to suppress introductory tips for established users.

**Finding 6 (Low — cognitive-load)**: The 'commit without /review' trigger duplicates the pre-commit hook enforcement. Remove — don't add a parallel soft reminder alongside an existing hard block.

**Finding 7 (Low — platform-violation)**: /guide naming risks confusion with /onboard and /walkthrough. Document the distinction explicitly.

### Strongest Triggers
- 'How do I...' question detection — zero Clippy risk, user invited the response
- Steward gate trigger (modifying agent/rule files) — high-stakes, non-obvious consequence

---

## Turn 4 — independent-perspective (proposal)
*2026-03-15T17:00:28.376173+00:00 | confidence: 0.82*
*tags: deliberation, anti-groupthink, feature-discovery*

## Independent Analysis

### Blocking Finding

**Synchronization hazard in separate knowledge base.** Creating a SKILL.md that manually describes framework features introduces a second source of truth that WILL drift. This contradicts framework_doc_sync.md philosophy. If a knowledge base is created, it must be generated from actual framework files or kept to synthesized intent-layer only (not mirroring the spec).

### Advisory Findings

1. **Try session-start hook enhancement first (Principle #8).** Add a capabilities summary to session-start output and a 'Quick Start' section to CLAUDE.md. This is 2 lines of change vs. 3 new files. Measure whether it resolves the problem before building more.

2. **Separate reactive from proactive, start reactive only.** /guide command (reactive) is low-risk and clearly useful. Proactive rule carries Clippy risk and should be deferred until reactive proves its value.

3. **Validate the problem with evidence.** Is there a documented session where a user struggled because they didn't know about a command? The framework's own principles demand diagnosis before prescription.

4. **If proactive suggestions are built, scope to session-start only.** Mid-workflow suggestions are highest-risk, lowest-value.

### Alternative: Dynamic Command Inventory
Instead of hand-maintained SKILL.md, a /guide command that reads .claude/commands/ directory and parses frontmatter descriptions would be ~15 lines, always in sync, and zero maintenance. The AI already knows all features from CLAUDE.md — the gap is surfacing, not knowledge.

### Key Observation
The proposal has been architected (rule + skill + command) BEFORE the team validated the problem statement. This is a solution looking for validation rather than a problem looking for a solution. Questions to answer first: (1) Is there evidence users fail to discover features? (2) At what point do they fail? (3) What is the simplest intervention for that specific failure point?

---

## Turn 5 — docs-knowledge (proposal)
*2026-03-15T17:00:36.530914+00:00 | confidence: 0.82*
*tags: deliberation, documentation, feature-discovery*

## Knowledge Architecture Analysis

### High-Severity Findings

**Finding 1 (High — missing-adr)**: This is an architectural decision requiring an ADR. The choice between duplicate, pointer, or generated index for the skill has lasting maintenance consequences. Write ADR before implementation.

**Finding 2 (High — self-healing)**: framework_doc_sync.md MUST be updated to include the new skill as a sync target. Without this, drift is certain. This is a blocking dependency.

### Medium-Severity Findings

**Finding 3 (Medium — claude-md-update)**: CLAUDE.md command count, directory layout, and skills section description all need updating together, not as post-hoc steps.

**Finding 4 (Medium — knowledge-stuck)**: The toggle mechanism is architecturally unresolved. No framework mechanism exists for toggling individual rules at runtime. Two realistic options: (a) opt-in flag in CLAUDE.md, or (b) remove the rule entirely and make guidance pull-based via /guide command only.

**Finding 5 (Medium — undiscoverable)**: Follow the established skill pattern — synthesized compact intent index, not a mirror of the spec. The skill's value is the INTENT layer ('when would I want this?') that CLAUDE.md does not provide.

### Key Verdicts on Questions Posed

- Drift risk: Real but manageable IF framework_doc_sync.md is updated (blocking)
- Duplicate vs pointer: Use synthesized intent index (established skill pattern)
- Overlap with CLAUDE.md: Yes, but skill adds intent layer ('when/why') that CLAUDE.md lacks
- Layer classification: Framework infrastructure, NOT Layer 3 curated memory
- Staleness prevention: Only reliable method is inclusion in framework_doc_sync.md

### Strengths
The three-artifact proposal cleanly separates behavioral trigger, knowledge base, and explicit invocation. The developer's 'must not annoy' constraint forces pull-based design. Deliberating before implementing is exactly right.

---

## Turn 6 — facilitator (synthesis)
*2026-03-15T17:01:06.979741+00:00 | confidence: 0.85*
*tags: synthesis, feature-discovery*

## Request Context
- **What was requested**: Developer wants the framework AI to know about its own features and suggest them to users, making the framework easier to use
- **Files/scope**: Proposed Rule + Skill + Command architecture for feature discovery and guidance
- **Developer-stated motivation**: Framework has 17 commands, 11 agents, 7 skills, 11 rules, 7 hooks but no interactive discovery mechanism
- **Explicit constraints**: Must not annoy people. Must be toggleable. Should answer questions AND suggest proactively.

## Synthesis

### Team Consensus: The Problem is Real, the Original Architecture is Too Much

All four specialists agree: the discoverability gap is genuine. A framework with 17 commands and 11 agents needs a way for users to find what they need. However, three of four specialists recommend a PHASED approach that starts simpler than the proposed Rule + Skill + Command architecture.

### Points of Agreement (All 4 Specialists)

1. **The /guide command is valuable and low-risk.** A reactive, user-initiated command that answers framework questions is unanimously supported.
2. **The proactive rule should be deferred.** Architecture-consultant, ux-evaluator, and independent-perspective all recommend shipping the reactive component first and adding proactive suggestions only if evidence shows they are needed. The rule introduces a new archetype ('advisory nudge') with no precedent.
3. **A hand-maintained SKILL.md creates sync risk.** Docs-knowledge and independent-perspective both flag that a separate knowledge base will drift from the actual framework files. The skill should be synthesized intent-layer only (not mirroring the spec) and must be added to framework_doc_sync.md.
4. **An ADR is required.** Docs-knowledge rates this as high-severity. Architecture-consultant concurs.

### Points of Disagreement

**How to build the /guide command's knowledge:**
- Independent-perspective advocates a dynamic approach (read .claude/commands/ directory, parse frontmatter) — always in sync, zero maintenance
- Docs-knowledge advocates a synthesized intent index — the skill adds 'when would I want this?' layer that raw directory listing cannot provide
- Both positions have merit. The intent-layer value is real but so is the sync risk.

**Resolution**: A hybrid approach — /guide dynamically reads command descriptions for the reference table, but the SKILL.md provides the synthesized intent index and workflow recipes that cannot be generated from frontmatter alone. This minimizes manual maintenance while preserving the high-value intent layer.

### Blocking Findings (Must Address Before Implementation)

1. **Remove file-count trigger and commit-without-review trigger** from the proactive rule (UX: HIGH severity — Clippy risk, duplicates existing enforcement)
2. **Replace 'Tip: ...' format** with contextual integration in natural response voice (UX: HIGH severity — second-voice problem)
3. **Add guide skill to framework_doc_sync.md** sync points (Docs: HIGH severity — drift is certain without this)
4. **Write an ADR** before implementation (Docs: HIGH severity — architectural pattern addition)

### Advisory Findings (Note but Don't Block)

5. Separate session-scoped and persistent toggle mechanisms (UX)
6. First-session tip should name top 3 commands, not just point to /guide (UX)
7. Add expertise-level signal to suppress novice tips for established users (UX)
8. Cross-reference /guide with /onboard and /walkthrough (Architecture)
9. Validate the problem with evidence before building the proactive layer (Independent)
10. Consider session-start hook enhancement as the simplest first intervention (Independent)

### Revised Recommendation

**Phase 0 (Immediate, minimal)**: Enhance the session-start hook to mention '/guide' and key commands. Add a 'Quick Start' section to CLAUDE.md. Zero new files.

**Phase 1 (Build)**: Create the /guide command + framework-guide skill (synthesized intent index). Write ADR. Update framework_doc_sync.md. This delivers the core reactive discovery value.

**Phase 2 (Deferred, evidence-gated)**: If Phase 1 proves insufficient after real usage, add the proactive guidance rule — but only with the safe triggers (question detection, Steward gate warning) and contextual integration format (no 'Tip:' prefix). The file-count and commit-without-review triggers are permanently excluded.

### Confidence: 0.85
The team is aligned on direction. The main uncertainty is whether Phase 1 alone will be sufficient or whether Phase 2 will eventually be needed.

---

## Turn 7 — facilitator (decision)
*2026-03-15T17:01:14.319673+00:00 | confidence: 0.85*
*tags: decision, feature-discovery*

## Decision

The team recommends a PHASED approach rather than the original three-layer architecture:

**Phase 0**: Enhance session-start hook + add Quick Start to CLAUDE.md (minimal intervention)
**Phase 1**: Build /guide command + framework-guide skill (reactive discovery)
**Phase 2**: Deferred — add proactive guidance rule only if Phase 1 proves insufficient

Key constraints on Phase 2 (if ever built):
- Only safe triggers: question detection, Steward gate warning
- Contextual integration format (no 'Tip:' prefix)
- File-count and commit-without-review triggers permanently excluded
- ADR required before Phase 2 proceeds

This decision requires developer approval before implementation begins.

---
