---
discussion_id: DISC-20260313-201134-review-blueprint-adoption-spec-review
started: 2026-03-13T20:11:46.031270+00:00
ended: 2026-03-13T20:17:49.334817+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260313-201134-review-blueprint-adoption-spec-review

## Turn 1 — facilitator (evidence)
*2026-03-13T20:11:46.031270+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Enhance the /review command and add supporting agents by adopting high-value patterns from the DIY Code Review Blueprint v2.1. Five phases: (1) PR-aware scope detection + confidence filtering + eligibility check, (2) new cr-validator agent + validation pass, (3) REVIEW.md convention + cr-compliance agent, (4) cr-history agent + self-healing doc suggestions, (5) --cost and --deep flags for model routing.
- **Files/scope**: .claude/commands/review.md (major update), 3 new agents (cr-validator, cr-compliance, cr-history), new REVIEW.md file, CLAUDE.md update
- **Developer-stated motivation**: Reduce false positives in reviews, automate scope detection, add validation/compliance layers. Blueprint analysis identified gaps vs Anthropic managed Code Review.
- **Explicit constraints**: No agent duplication (reuse existing specialists), no storage duplication (use existing capture pipeline), no cr-synthesizer or cr-quiz-generator (existing commands handle those), Principle #8 compliance (command changes before agent changes)

---

## Turn 2 — architecture-consultant (critique)
*2026-03-13T20:14:19.842843+00:00 | confidence: 0.82*
*tags: spec-review, architecture*

Verdict: approve-with-changes (confidence 0.82). BLOCKING: (1) cr-validator at Opus tier is inconsistent with model tier policy - validation is evaluation not generation, should be Sonnet. (2) REVIEW.md convention introduces a 4th rule source without an ADR - requires ADR-0004 or relocation to .claude/rules/. ADVISORY: (3) cr- prefix naming inconsistent with existing agent names - suggest finding-validator, compliance-auditor, history-analyst. (4) --cost override semantics need documentation and Task tool model param support verification. (5) recurring_patterns view does not exist - actual view is v_rule_of_three. (6) CLAUDE.md sections needing update not enumerated. (7) --comment flag referenced but not in scope - creates ambiguity in R1.2.

---

## Turn 3 — qa-specialist (critique)
*2026-03-13T20:14:29.781391+00:00 | confidence: 0.88*
*tags: spec-review, qa*

Verdict: request-changes (confidence 0.88). BLOCKING: (1) No test strategy section - build team cannot determine what done looks like. (2) Confidence filtering behavior undefined when confidence absent or all findings filtered. (3) Already-reviewed PR detection mechanism unspecified - criterion untestable. ADVISORY: (4) --cost low model routing unverifiable as acceptance criterion. (5) cr-validator failure modes unspecified (timeout, error, unexpected format). (6) REVIEW.md absence behavior undefined for cr-compliance. (7) Self-healing step degradation unspecified (empty view, DB failure, output format). (8) Already-reviewed detection mechanism not defined. (9) cr-history requires fixture git repo for deterministic tests. (10) Agent frontmatter schema has no automated validation. 12 edge cases enumerated including empty repo, detached HEAD, empty PR diff, binary-only changes, flag interaction (--deep + --cost low).

---

## Turn 4 — security-specialist (critique)
*2026-03-13T20:14:41.855895+00:00 | confidence: 0.87*
*tags: spec-review, security*

Verdict: approve-with-changes (confidence 0.87). BLOCKING: (1) Shell injection risk in Phase 1 scope detection - branch names/PR titles from gh/git output could contain metacharacters, must be treated as untrusted with positional args or allowlist validation. (2) Prompt injection via REVIEW.md - contents passed verbatim into agent prompts, must use structured delimiters and explicit framing instruction. ADVISORY: (3) Already-reviewed check must be advisory only, never a security gate. (4) cr-validator receives specialist findings as unstructured input - should require JSON structured data to reduce prompt injection surface. (5) --cost low silently downgrades security analysis on high-risk changes - should warn or exempt security-specialist from downgrade on High/Critical risk. Trust boundaries mapped: CLI output to scope detection, REVIEW.md to prompt, specialist findings to validator, SQLite patterns to suggestions.

---

## Turn 5 — facilitator (synthesis)
*2026-03-13T20:17:49.334817+00:00 | confidence: 0.85*
*tags: blocking:7, advisory:5*

## Request Context
- **What was requested**: Enhance /review command and add supporting agents by adopting patterns from DIY Code Review Blueprint v2.1. Five phases covering scope detection, validation, compliance, history, and cost routing.
- **Files/scope**: .claude/commands/review.md, 3 new agents (finding-validator, compliance-auditor, history-analyst), REVIEW.md, ADR-0004, CLAUDE.md update
- **Developer-stated motivation**: Reduce false positives, automate scope detection, add validation/compliance layers based on blueprint gap analysis.
- **Explicit constraints**: No agent duplication, no storage duplication, Principle #8 compliance, backward compatibility.

## Synthesis

Three specialists reviewed the spec. 7 blocking findings addressed, 5 advisory items tracked.

### Blocking Findings Addressed:
1. **cr-validator model tier** (arch): Downgraded from Opus to Sonnet. Validation is evaluation, not generation.
2. **Missing ADR for REVIEW.md** (arch): Added R3.0 requiring ADR-0004 before implementation.
3. **Agent naming inconsistency** (arch): Renamed cr-validator/cr-compliance/cr-history to finding-validator/compliance-auditor/history-analyst per existing convention.
4. **No test strategy** (qa): Added Test Strategy section with automated, manual checklist, and smoke test categories.
5. **Confidence filtering undefined edge cases** (qa): Added behavior for missing confidence (retain as unscored), all-filtered case, and capture-vs-synthesis layer distinction.
6. **Shell injection in scope detection** (sec): Added R1.1a requiring input sanitization with allowlist validation.
7. **Prompt injection via REVIEW.md** (sec): Added XML delimiter framing defense to R3.3.

### Additional Spec Changes:
- Fixed recurring_patterns reference to v_rule_of_three (actual view name)
- Added R2.5 for validator timeout/error graceful degradation
- Added R3.5 for REVIEW.md absence handling
- Added --cost low warning for High/Critical risk reviews
- Added facilitator exemption from cost-tier downgrade
- Added synthesis logging of model tiers for verification
- Clarified already-reviewed check mechanism and advisory-only nature
- Added 20 acceptance criteria (up from 12)

---
