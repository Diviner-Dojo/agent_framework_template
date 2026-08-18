---
discussion_id: DISC-20260818-003503-review-b2-framework-md-retirement-and-tier1-fixes
started: 2026-08-18T00:55:11.567006+00:00
ended: 2026-08-18T00:55:11.753403+00:00
agents: [docs-knowledge, facilitator, independent-perspective, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260818-003503-review-b2-framework-md-retirement-and-tier1-fixes

## Turn 1 — qa-specialist (critique)
*2026-08-18T00:55:11.567006+00:00 | confidence: 0.82*
*tags: review, guard, mutation-test, self-review-hazard*

Guard review, mutation-tested. MEDIUM: the rewritten test_count_and_citation_registers_stay_separate no longer catches a KNOWN_STALE_COUNTS whose keyset is DERIVED from KNOWN_STALE_CITATIONS while remaining a distinct correctly-typed dict; demonstrated by direct execution (OLD assertion FAILED=caught, NEW assertion PASSED=missed). Also judged the deletion of the old assertion legitimate: it failed precisely when debt was paid off, and was already unsatisfiable on a correctly-drained tree. LOW: the FRAMEWORK_SPECIFICATION register reason-line cites L576/L1262; measured actual hits are L581/L1267, drifted by 5 - an unmeasured line-number claim inside the module whose stated ethos is measured-not-claimed. CONFIRMED SOUND: all five register deletions verified genuine by independent grep, not merely dropped from the allowlist; docstring coverage 58/67=86.6% and the nine unchecked lines across six files reproduce exactly; two injected mutations (out-of-range citation, competing principle list) went RED with correct actionable messages and restored byte-clean with empty git diff; 23 passed exit 0.

---

## Turn 2 — docs-knowledge (critique)
*2026-08-18T00:55:11.626166+00:00 | confidence: 0.9*
*tags: review, docs, content-loss, dangling-citation, attribution*

Documentation review of the FRAMEWORK.md retirement. NO BLOCKING. Content-loss check exhaustive and CLEAN: every section of the deleted 195-line file (principles, agent roster, orchestration rules, model override, cross-agent protocols, collaboration modes, exploration intensity, four-layer stack, capture pipeline, commit protocol, external analysis, ID conventions, directory layout, invocation pattern, framework evolution) verified present and in most cases more current in CLAUDE.md / docs/AGENT_ARCHITECTURE.md / docs/CAPTURE_PIPELINE.md. Dangling-reference sweep across the live surface CLEAN - only seed.md's intentional retirement notes. /seed verified correct end to end by EXECUTING the new verification command against a real CLAUDE.md: returns exactly 7. All four ADR-0036 factual claims independently verified TRUE (ADR-0065 never existed; eight principles incl. retired slots 3 and 8; education clause contradicts current Principle 5 + ADR-0035; present on upstream/main). No ADR numbering collision. MEDIUM: the NEW PHILOSOPHY.md attribution cites ANALYSIS-20260219-043657, an artifact never committed (confirmed via git log --all) - the fix for an attribution finding rests on a citation to a nonexistent file, in the file whose job is durable attribution, and is a fresh instance of the very defect class this change's own walkthrough taught. LOW: ADR-0036 discussion_id blank. STRENGTH: /seed's replacement of a file-existence check with a content-shape check is stronger than what it replaced.

---

## Turn 3 — independent-perspective (critique)
*2026-08-18T00:55:11.689817+00:00 | confidence: 0.88*
*tags: review, blocking, anti-groupthink, false-claim, alternatives, consensus-check*
*risk flags: blocking-findings, unresolved-b4*

Anti-groupthink review. NOT CLEAN - THREE BLOCKING. B1: /seed mandates inlining a principles block citing three things that do not exist in a fresh seed - ADR-0031 (seeded docs/adr/ scaffolded empty), PHILOSOPHY.md Growth-has-a-brake (sourced from shared-memory which has NO PHILOSOPHY.md on this machine; the || true swallows it), and .claude/skills/selecting-review-gates (scaffold creates agents/commands/hooks/rules, no skills/) - and the verification returns 7 and reports GREEN anyway; the command's own prose forbids exactly this, so the rule was applied to one pointer and not the three it introduced. B2: ADR-0036's load-bearing safety claim 'CLAUDE.md is not in FRAMEWORK_PATHS' is FALSE - manifest.py:24 lists it as item 3 - structurally the identical error form as the 'does not propagate' clean tell the same ADR spends six lines dissecting. B3: the ADR cites REV-20260816-194513, a review predating the change that explicitly left B2 unresolved; no review had seen the deletion, the /seed rewire or the guard rewrite. HIGH: the rewritten separation guard goes VACUOUS when the register empties (all() over {} is True) and the rot test drives it toward empty - verdict 'legitimate correction, incomplete replacement'. HIGH: PHILOSOPHY.md is not in FRAMEWORK_PATHS so /apply-framework can never deliver it, while 8 propagating files now cite its Growth-has-a-brake section; measured absent from upstream/main, agentic_journal and VerificationPortal. HIGH: the claimed positive 'public template stops publishing two contradictory lists' is false - public CLAUDE.md has NINE, public PHILOSOPHY.md says eight, ADR-0031 was never promoted, newest public ADR is 0028. THE CASE AGAINST: the shared file drifted four months and WAS CAUGHT by a guard with a register and an owner; the two projects carrying INLINED constitutions drifted to the retired model and were caught only by an ad-hoc sweep with no guard, no register, no owner - this change generalises the UNDETECTED failure mode and retires the DETECTED one. Names a skipped fourth alternative (generate the block from canonical source + record sha256 in framework-lineage.yaml so /apply-framework reports 'N revisions behind' as a human-gated offer, ~40 lines) and shows the ADR's three listed alternatives are a false trichotomy since all three KEEP FrameworkMd. CONSENSUS CHECK: the prior panel's meta-finding now appears verbatim in three artifacts while the measurement it refers to went stale in the same commit - quoting a critique three times reads as having answered it.

---

## Turn 4 — facilitator (synthesis)
*2026-08-18T00:55:11.753403+00:00 | confidence: 0.9*
*tags: synthesis, verdict, approve-with-changes, meta-finding*

VERDICT: approve-with-changes. All three BLOCKING findings independently re-verified by the author against the source of truth before fixing - CLAUDE.md IS item 3 of FRAMEWORK_PATHS (manifest.py:24); shared-memory has FRAMEWORK.md present at 12706 bytes and NO PHILOSOPHY.md; seed.md scaffolded no skills/ directory. All three FIXED: /seed Step 1 now hard-fails on a missing philosophy or cited section and refuses a retired FRAMEWORK.md mechanically rather than by prose (Principle #2), Step 2 scaffolds skills/ as required, Step 5 carries a re-pointing table rendering ADR-0031 as upstream provenance, Step 10 gained a pointer-resolution check; ADR-0036's two false claims corrected IN PLACE WITH THE CORRECTION RECORDED rather than silently edited (Principle #1), converting the public-repo claim into a promotion REQUIREMENT that CLAUDE.md + PHILOSOPHY.md + ADRs 0029-0036 must travel with the deletion; this review written and cited. The deferred generated-block alternative is recorded in ADR-0036 Alternatives as DEFERRED NOT REJECTED with the review's evidence undiluted, per the developer's decision to scope this change to the blocking items. META-FINDING: the author reproduced the exact defect class the author had just finished cataloguing, twice, in the artifacts written to fix it - and had already measured the correct FRAMEWORK_PATHS data earlier in the same session. Fluency with a failure mode is not immunity to it. H1/H2/H3 and A1-A9 carried forward as OPEN advisories, not closed; H2 (PHILOSOPHY.md unreachable by /apply-framework) is flagged a derived-project push-blocker.

---
