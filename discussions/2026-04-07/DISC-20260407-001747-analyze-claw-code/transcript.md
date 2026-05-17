---
discussion_id: DISC-20260407-001747-analyze-claw-code
started: 2026-04-07T00:25:34.511302+00:00
ended: 2026-04-07T00:28:10.715264+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective, performance-analyst, project-analyst, qa-specialist, security-specialist]
total_turns: 8
---

# Discussion: DISC-20260407-001747-analyze-claw-code

## Turn 1 — project-analyst (proposal)
*2026-04-07T00:25:34.511302+00:00 | confidence: 0.8*
*tags: scout-report, phase-1*

Scout report: Claw Code (ultraworkers/claw-code) - Rust/Python clean-room rewrite of Claude Code agent harness. 60K Rust LOC, 9 crates, 3.8K test LOC. 292 commits over 4 days by 3 authors. Key patterns: deterministic mock Anthropic service, recovery-as-data, composable policy engine, typed quality levels (GreenContract), incremental summary merging, parse-dont-validate with error accumulation, structured failure taxonomy. Anti-patterns: git marked as read-only-safe, no LICENSE file, hollow Python reference layer, string-prefix path boundary check. 6 specialists dispatched for co-review.

---

## Turn 2 — architecture-consultant (proposal)
*2026-04-07T00:25:46.419263+00:00 | confidence: 0.8*
*tags: co-review, architecture*

Confidence 0.82. Typed task packets and composable policy engine are conceptually applicable. Worker lifecycle and MCP lifecycle state machines solve problems we dont have. Parse-dont-validate newtype pattern is language-agnostic and directly applicable. Policy engine And/Or combinators are novel but premature for our scale.

---

## Turn 3 — security-specialist (proposal)
*2026-04-07T00:25:46.478442+00:00 | confidence: 0.8*
*tags: co-review, security*

Confidence 0.85. Hook-override pathway and rule DSL (tool(pattern) format) cleaner than our current hook model. Bash read-only heuristic marking git as safe is ACTIVELY DANGEROUS - do not emulate. String-prefix workspace boundary check is exploitable. Permission tier model (allow/deny/ask) is well-structured.

---

## Turn 4 — performance-analyst (proposal)
*2026-04-07T00:25:46.539554+00:00 | confidence: 0.8*
*tags: co-review, performance*

Confidence 0.80. Summary compression budget concept most applicable performance pattern. Rust/Python split teaches nothing - our bottleneck is API latency not runtime. Session rotation 256KB cap is context-specific to persistent CLI.

---

## Turn 5 — qa-specialist (proposal)
*2026-04-07T00:25:46.601289+00:00 | confidence: 0.8*
*tags: co-review, qa*

Confidence 0.90. Deterministic mock Anthropic service is the most novel applicable pattern - real HTTP server returning scripted responses based on scenario ID. One-claim-per-test with given/when/then immediately adoptable. 12 scripted test scenarios demonstrate thorough coverage approach.

---

## Turn 6 — docs-knowledge (proposal)
*2026-04-07T00:25:46.662248+00:00 | confidence: 0.8*
*tags: co-review, docs*

Confidence 0.78. Incremental summary merging for BUILD_STATUS.md is low-cost and directly applicable. PARITY.md as machine-readable checklist is interesting but context-specific. ROADMAP 22 operational failure items are primary source material for autonomous dev failures.

---

## Turn 7 — independent-perspective (proposal)
*2026-04-07T00:25:46.723040+00:00 | confidence: 0.8*
*tags: co-review, independent*

Confidence 0.88. Recovery-as-data is most underrated finding. ROADMAP 22 operational failure items more valuable than the code. GreenContract concept bridges our binary quality gate toward ordered model. Policy engine is premature for our scale - defer.

---

## Turn 8 — facilitator (synthesis)
*2026-04-07T00:28:10.715264+00:00 | confidence: 0.8*
*tags: synthesis, scoring*

Analysis of Claw Code (ultraworkers/claw-code) complete. 13 patterns evaluated, 4 recommended for adoption (ideas-only due to license), 6 deferred, 3 skipped. Strongest signal: deterministic mock Anthropic service (21/25, 3-specialist consensus). Named failure taxonomy (22/25), incremental summary merging (21/25), and parse-dont-validate (21/25) also recommended. 3 anti-patterns flagged: git-as-safe heuristic (dangerous), string-prefix path check (exploitable), hollow reference layer (misleading). License status: NO LICENSE FILE despite website claiming MIT - all recommendations scoped to ideas-only.

---
