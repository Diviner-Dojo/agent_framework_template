---
discussion_id: DISC-20260520-161826-efficiency-ledger-ratification
started: 2026-05-20T16:19:02.602212+00:00
ended: 2026-05-20T16:22:00.736470+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260520-161826-efficiency-ledger-ratification

## Turn 1 — facilitator (evidence)
*2026-05-20T16:19:02.602212+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Ratify the per-item cost/value ledger for slimming the always-loaded instruction corpus (CLAUDE.md + .claude/rules), adopting progressive disclosure, adding a ~95%-confidence ask-before-building gate, moving token-heavy work to CLI, and co-migrating 3 derived projects.
- **Files/scope**: CLAUDE.md (~8.9K tok) + 15 .claude/rules files (~13.1K tok) = ~22K always-loaded tokens/turn, re-paid per specialist dispatch. Ledger dispositions: KEEP / PATH-SCOPE / SKILL / FOLD / CUT. Affects template + howie + agentic_journal + VerificationPortal.
- **Developer-stated motivation**: AI cost model shifting from unlimited tokens toward near-cost; invest now so future framework work compounds efficiency gains.
- **Explicit constraints**: judge load-bearing by derived-project usage (not template-local); keep steward (owns lineage); least-complex intervention first (Principle #8); preserve capture/governance integrity; honest reporting.

---

## Turn 2 — architecture-consultant (critique)
*2026-05-20T16:22:00.423905+00:00 | confidence: 0.82*
*tags: ratification, architecture*

RATIFY-WITH-CHANGES. FOLD cluster needs revision: review_gates has 3 consumers (/review, /ship, /retro) and pre_build_search has 2 (/plan, /build_module) -- folding into one command creates command-to-command coupling. Make both SKILLs that all consumers load. Only build_review_protocol is single-owner -- fold OK. route.py RATIFIED but must become the SOLE dispatch authority (delete the duplicated tables in facilitator.md and review.md to actually kill drift). Roster + capture-DAG to docs RATIFIED (use live links).

---

## Turn 3 — docs-knowledge (critique)
*2026-05-20T16:22:00.521456+00:00 | confidence: 0.82*
*tags: ratification, knowledge-flow*

RATIFY-WITH-CHANGES. Rules Index needs richer entries for 3 rules: failure_taxonomy (list the 8 failure-class names as keywords -- retrieval triggers on the symptom, not the word taxonomy), review_gates (signal risk-tier/specialist-selection lives there), cross_agent_dispatch (surface dispatch-request/dispatch-decision tags). Always-On Invariants must carry failure_taxonomy name+path+trigger for cold-start with no active command. documentation_policy CUT pointer must name its 2 cross-refs (review_gates ADR-scope, framework_doc_sync sync-table). Lineage preserved if the ADR references this DISC id.

---

## Turn 4 — security-specialist (critique)
*2026-05-20T16:22:00.627017+00:00 | confidence: 0.88*
*tags: ratification, security*

RATIFY-WITH-CHANGES. The two promoted invariants (trust-boundary sanitization; untrusted-reply allow-list) are the correct always-on lines. Consider promoting a third coding-refusal -- no raw DB errors to API consumers -- or accept residual risk. PATH-SCOPE security_baseline should cover scripts/** as well as src/** (scripts can introduce HTTP calls); CORS/auth/rate-limit lines create a narrow blind spot only if a security review runs entirely on non-src files. Deferring notification_protocol is SAFE: the untrusted-reply invariant is promoted to always-loaded CLAUDE.md and inherited by all specialists -- this validates the current async ntfy usage.

---

## Turn 5 — facilitator (synthesis)
*2026-05-20T16:22:00.736470+00:00 | confidence: 0.85*
*tags: synthesis*

## Request Context
- What was requested: ratify the cost/value ledger for slimming the always-loaded corpus.
- Files/scope: CLAUDE.md + 15 rules (~22K tok/turn, re-paid per specialist dispatch); template + 3 derived projects.
- Motivation: AI cost shifting toward near-cost; invest now to compound gains.
- Constraints: derived-usage as load-bearing test; least-complex first; preserve governance; honest reporting.

## Synthesis -- ledger RATIFIED-WITH-CHANGES (no objection to the core reduction)
1. review_gates -> SKILL shared by /review,/ship,/retro (NOT fold -- avoids command coupling).
2. pre_build_search -> SKILL shared by /plan,/build_module (NOT fold).
3. build_review_protocol -> FOLD into /build_module (single-owner, confirmed).
4. route.py must be the SOLE dispatch authority -- delete duplicated tables from facilitator.md and review.md.
5. Rules Index: richer entries for failure_taxonomy (8 class names), review_gates, cross_agent_dispatch.
6. failure_taxonomy name+path+trigger in Always-On Invariants for cold-start retrieval.
7. PATH-SCOPE security_baseline over src/** AND scripts/**.
8. documentation_policy CUT pointer must name its 2 cross-refs.
9. Optional: promote a no-raw-DB-errors invariant or accept residual risk.
10. ADR must reference this DISC id (Principle #1 lineage).
Convergent verdict, no genuine dissent. Security confirmed current async ntfy usage is safe.

---
