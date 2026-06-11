---
discussion_id: DISC-20260611-182734-review-apply-framework-unification-commit
started: 2026-06-11T18:27:52.074777+00:00
ended: 2026-06-11T20:08:05.863592+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 8
---

# Discussion: DISC-20260611-182734-review-apply-framework-unification-commit

## Turn 1 — facilitator (evidence)
*2026-06-11T18:27:52.074777+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Phase 1 (D1 execution) of SPEC-20260610-205507: finish + merge the distribute-b1-floor worktree. This /review covers the ~1,250-line /apply-framework unification build (SPEC-20260524-203931, ADR-0021) before it is committed on feat/distribute-b1-floor.
- **Files/scope**: 12 modified + 3 new files in .claude/worktrees/distribute-b1-floor/: scripts/distribute/{router.py(new),assessment.py,change_package.py,repo_safety_check.py,stage_branch.py}, tests/test_distribute.py (+445 lines), .claude/commands/{apply-framework.md(new),distribute.md,onboard.md}, docs/adr/ADR-0021(new, renumbered from draft ADR-0019)+ADR-0017, SPEC stamp, regression-ledger entry.
- **Developer-stated motivation**: D1 APPROVED 2026-06-11 — closes the ADR-0017 numbering gap and unblocks all satellite deploys (D2-D6). The build itself was spec-reviewed (DISC-20260524-204142) and Steward-gated (DISC-20260524-205732, APPROVE 0.86) in May; this is the pre-commit /review the workflow requires.
- **Explicit constraints**: Never push; merge to main is the developer's act (ntfy matched-label gate); Layer 1 discussions are immutable (renumber note added to ADR-0021 instead); docs/handoff/ and metrics/quality_gate_log.jsonl excluded from the commit.

---

## Turn 2 — qa-specialist (proposal)
*2026-06-11T18:39:01.091967+00:00 | confidence: 0.91*
*tags: review, qa*

VERDICT: approve-with-changes, confidence 0.91. Test suite comprehensive (114 tests, 21 classes); floor proven on BOTH baselines; regression tests faithful to ledger. F1 LOW: apply_assent_preflight parametrize missing non-string primary_human rows (int/bool). F2 LOW: MAX_EXTRA_FILE_BYTES cap untested + no direct extra_files traversal test (shared-primitive coverage via _resolve_within exists). F3 LOW: test_pinned_existing_file_not_overwritten_on_branch name asserts the OPPOSITE of what it checks (hub version IS staged) - rename. F4 LOW(0.72): no end-to-end partial-route floor test. F5 INFO: update_consent non-dict non-None inputs untested. Strengths: deploy isolation proven end-to-end; never-push spy genuine; fence-escape test uses exact escape string; isolation clean.

---

## Turn 3 — security-specialist (proposal)
*2026-06-11T18:39:01.158767+00:00 | confidence: 0.88*
*tags: review, security, adversarial*

VERDICT: request-changes, confidence 0.88. F1 BLOCKING (0.97, empirically verified): Unicode invisible-char bypass of apply_assent_preflight - primary_human='​' (ZWSP, also FEFF/ZWNJ/ZWJ/soft-hyphen/directional marks) passes 'not human.strip()' since Python str.strip() only strips whitespace-category chars; consent gate satisfied by a visually-blank non-name; undermines Prime Objective (c). Fix: require >=1 printable non-whitespace non-control char (unicodedata category not in Z*/C*). F2 HIGH (0.93): _read_text follows symlinks on ASSESS read path - target symlink at framework path pulls off-tree content into agent prompts pre-redaction (documented v1.1 deferral; recommend minimal is_symlink guard now). F3 MED: redact_secrets misses unquoted secrets (AWS_SECRET_KEY=..., password: x) - PRE-EXISTING hub-wide SECRET_PATTERNS limitation, more material on APPLY; docstring note. F4 MED: wrap_data_only neutralizes END fence but not BEGIN - forged second block opening can bias free-text interpretation (escalate-only bridge still holds routing). F5 LOW: stage() has no mechanical consent parameter - APPLY consent is command-prose-enforced (acceptable for agent-operated workflow, named for transparency). F6 LOW: baseline_gate_green default-skip prose-only (documented, acceptable). F7 INFO: git add -A window. Strengths: is-True strict bools correct; _resolve_within blocks 6 attack vectors; ref-name validation solid; escalate-only bridge normalized; redact fails closed; router fails closed; stub-on-branch back-out atomic.

---

## Turn 4 — architecture-consultant (proposal)
*2026-06-11T18:39:25.694963+00:00 | confidence: 0.91*
*tags: review, architecture*

VERDICT: approve-with-changes, confidence 0.91. ADR-0021's 8 decisions map cleanly to code; supersession chain 0017->0021 clean; renumbering note adequate; Baseline Protocol seam genuinely route-agnostic (no isinstance leaks); recomposed repo_safety_check behaviorally identical to fused gate; single-sourcing of consent-critical sections real (test-validated). F1 MED (0.82): compute_greenfield_package->stage consent precondition is prose-only - no structural marker forces a future orchestrator through the R8 preflight (consent is a DEPLOY-layer gate so a compute-layer sentinel may be wrong layer; acceptable as documented debt). F2 MED (0.79): _section_counted_disclaimer counts len(overwrite_diffs) not len(package.requires_interpretation) - equal today, diverges if a caller passes filtered diffs; derive from package or assert equality. F3 LOW: RouteReport.preexisting_framework_files intentionally unpopulated on UPDATE (docstring adequate). F4 LOW: sys.path mutation at import for SECRET_PATTERNS (contained for framework-internal tool). F5 LOW: COMMIT_TRAILER hardcodes stale model name, no comment explaining freeze. F6 INFO: section-builders 2-caller abstraction correctly exempted from Rule of Three (consent-critical single-sourcing). Strengths: dependency direction correct throughout; command-layer coherent (no stale /distribute-as-primary refs).

---

## Turn 5 — independent-perspective (proposal)
*2026-06-11T18:39:25.765097+00:00 | confidence: 0.84*
*tags: review, independent-perspective, anti-groupthink*

VERDICT: approve-with-changes, confidence 0.84 (Independent Analyst). F1 BLOCKING (0.97, process not code): regression-ledger.md merge conflict - branch version predates main's ~19 post-May-24 entries (telemetry/collab-loop/quality-gate canary contracts); branch-side resolution silently destroys institutional memory. REQUIRED: manual merge keeping ALL main entries + the branch's B1-greenfield row. F2 HIGH (0.92): onboard.md conflicts at merge - branch version is the correct superset (supersession notice + full protocol); resolve branch-side. F3 HIGH (0.78): ADR-0021 Consequences does not record the --assent-human residual gap: the gate validates the string syntactically (non-null), not that a human was present per-instance; an autonomous session inheriting a typed name satisfies it. Add to Negative consequences. F4 MED (0.71): COMMIT_TRAILER stale 'Claude Opus 4.7 (1M context)' baked into future distribution commits. F5 MED (0.68): partial route = greenfield engine + warning label only, yet partial targets (most authored content at framework paths) are the HIGHEST-risk overwrite targets; consider a stronger gate (e.g. --partial-reviewed enumeration) before first real satellite deploy - design fork for developer/Steward at D4 time. F6: symlink ASSESS read - documented v1.1 deferral (known, not new). F7 INFO: SECRET_PATTERNS import failure only surfaces at DEPLOY; warn at ASSESS. Verified NOT stale: scripts/lineage contracts (collect_framework_files/hash_file/manifest_read/drift_scan/FileDrift) all hold on today's main - imports survive merge.

---

## Turn 6 — facilitator (critique)
*2026-06-11T18:39:59.389870+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: sec-F1 ZWS consent bypass VERIFIED TRUE by independent facilitator reproduction (apply_assent_preflight chr(0x200B) -> ok=True; FEFF -> ok=True; via build_assent_stub -> ok=True). sec-F2 symlink read path verified by specialist empirical test; consistent with code (_read_text uses Path.read_text, no is_symlink check). arch-F2 disclaimer count source verified against assessment.py (both assemblers count caller-supplied overwrite_diffs). indep-F1 ledger divergence verified (branch ledger predates ~19 main entries). indep verified lineage import contracts HOLD on today's main. COMMIT_TRAILER not pinned by any test. 0 findings discarded; all verifiable findings verified true or judgment-dependent-inconclusive. Verdict: 1 BLOCKING code fix (sec F1) + 1 BLOCKING merge-process requirement (indep F1) + fold set accepted.

---

## Turn 7 — facilitator (evidence)
*2026-06-11T18:42:48.268997+00:00 | confidence: 0.8*
*tags: session-checkpoint*

SESSION CHECKPOINT (usage limit): review pauses mid-fold. Folded+verified so far: sec-F1 ZWS/invisible-Unicode consent bypass fix (_is_meaningful_name in repo_safety_check.py, applied in apply_assent_preflight + build_assent_stub; empirically re-verified blocked; note: PostToolUse formatter stripped the unicodedata import once before the consumer existed - re-added). Remaining fold set + synthesis + REV report are enumerated in the session handoff; this discussion stays in_progress and is picked up by the /review resumption check.

---

## Turn 8 — facilitator (synthesis)
*2026-06-11T20:08:05.863592+00:00 | confidence: 0.88*
*tags: synthesis, blocking:2, advisory:14, speculative:2, model-tier:sonnet*

## Request Context
- **What was requested**: Pre-commit /review of the /apply-framework unification build (~1,250 lines, SPEC-20260524-203931, ADR-0021) in worktree distribute-b1-floor — Phase 1 (D1) of SPEC-20260610-205507.
- **Files/scope**: 15 files — scripts/distribute/{router.py(new), assessment.py, change_package.py, repo_safety_check.py, stage_branch.py}, tests/test_distribute.py, .claude/commands/{apply-framework.md(new), distribute.md, onboard.md}, docs/adr/ADR-0021(new)+ADR-0017, SPEC stamp, regression-ledger entry, BUILD_STATUS line.
- **Developer-stated motivation**: D1 APPROVED 2026-06-11 — closes the ADR-0017 numbering gap, unblocks all satellite deploys (D2–D6).
- **Explicit constraints**: never push; merge to main only on matched ntfy merge-now; Layer-1 discussions immutable (renumber note in ADR-0021); gate-log + docs/handoff excluded from commit.

SYNTHESIS (post-fold). Panel: qa 0.91 AWC, security 0.88 RC, architecture 0.91 AWC, independent-perspective 0.84 AWC; all dispatched model=sonnet per the Fable tiering policy; facilitator role held by the main session.

BLOCKING (2, both resolved): sec-F1 invisible-Unicode consent bypass — FIXED (_is_meaningful_name, unicodedata category not Z*/C*, wired into apply_assent_preflight + build_assent_stub) + regression-pinned (ZWS/FEFF/ZWNJ+ZWJ/soft-hyphen/mixed parametrize rows, escaped source); indep-F1 regression-ledger merge hazard — encoded as a REQUIRED merge resolution (UNION: all main entries + branch B1-greenfield row), not a code change.

FOLDED ADVISORY (this session): sec-F4 BEGIN-fence neutralization in wrap_data_only + test; sec-F2 file-level symlink refusal in _read_text + skip-aware test (parent-dir containment stays v1.1, deferred line updated in apply-framework.md); arch-F2 disclaimer count now derived from package.requires_interpretation in BOTH assemblers; indep-F3 --assent-human residual-gap bullet added to ADR-0021 Negative consequences; arch-F5/indep-F4 COMMIT_TRAILER model-agnostic + rationale comment; qa-F1/F2/F4/F5 + sec-F1/F4 test pins (preflight non-str rows, update_consent non-dict, oversized-extra-file rollback, extra_files path-escape rollback, partial-route floor, BEGIN-fence case, symlink guard); qa-F3 test renamed to assert what it checks (value_unverified_existing_file_is_staged_on_branch_for_human_review).

DEFERRED-AS-ADVISORY (tracked in BUILD_STATUS, not folded): (1) consent sentinel at stage() (sec-F5/arch-F1) — command-prose enforced; compute-layer sentinel judged wrong layer; documented debt. (2) redact_secrets unquoted-pattern gap (sec-F3) — PRE-EXISTING hub-wide SECRET_PATTERNS limitation, fix belongs in a hub-wide pass. (3) sys.path import fragility + ASSESS-time warning for SECRET_PATTERNS import failure (arch-F4/indep-F7). (4) partial-route stronger gate (indep-F5) — DESIGN FORK for developer/Steward at D4 time; noted for the SPEC D4 row.

SPECULATIVE (2, <0.80): indep-F5 partial-route gate (0.68) — captured as the D4 design fork above; qa-F4 partial-route e2e coverage (0.72) — now partially addressed by test_partial_route_floor_holds.

DISCARDED: 0. Verification: facilitator independently reproduced sec-F1 pre-fix and re-verified blocked post-fix; suite 126 passed; worktree quality gate 7/7 post-fold.

VERDICT: approve (panel approve-with-changes; all blocking + folded advisory resolved; 0 blocking remaining). Education gate: DEFER formally (developer AFK) — scope: router.py route spectrum, Baseline protocol seam, consent inversion (APPLY assent stub vs UPDATE opt-in); Bloom Understand/Analyze; runs next interactive session.

---
