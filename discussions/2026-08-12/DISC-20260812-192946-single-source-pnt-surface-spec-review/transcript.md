---
discussion_id: DISC-20260812-192946-single-source-pnt-surface-spec-review
started: 2026-08-12T19:30:00.151815+00:00
ended: 2026-08-12T19:43:34.097892+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist]
total_turns: 9
---

# Discussion: DISC-20260812-192946-single-source-pnt-surface-spec-review

## Turn 1 — facilitator (evidence)
*2026-08-12T19:30:00.151815+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Resume from HANDOFF-20260810-instruments-first-wave4.md ('resume here'). Handoff item 3: 'Phase B continues — the burden advisory (+115% five-command chain) is the real target now', per-file measurement first. This spec is that slice.
- **Files/scope**: SPEC-20260812-122753 — dedup the paths-not-taken instruction surface across .claude/commands/{build_module,review,walkthrough}.md + one new pointer-integrity test; ship the missing intent-to-add reversal (REV-20260809-222916 Advisory 3, HIGH).
- **Developer-stated motivation**: extrapolated from the record, sources named: REV-20260809-222916 Advisory 4 (the onerous half 'is the half that broke'), the developer's verbatim steer 'I don't want to make it onerous and hard-gating', and the handoff's build queue. The developer did not speak in this session beyond 'resume here'.
- **Explicit constraints**: measurement-thinner veto; no guard or measured sentence lost, only de-duplicated; educator.md/quiz.md untouched (AC12); never push/merge/propagate; the two deeper burden cuts are developer forks, not scope.

---

## Turn 2 — facilitator (decision)
*2026-08-12T19:30:22.224305+00:00 | confidence: 0.8*
*tags: path-not-taken, spec*

## Path Not Taken
- **Decision**: where the single-sourced content lives
- **Chosen**: existing files stay authoritative (build_module.md Step 6.5 for the intent-to-add rationale; review.md Step 10 for the consequences); pointers by exact heading
- **Rejected**: a new verifying-paths-not-taken skill as the shared home
- **Why rejected**: adds a file and a skill-load indirection to shrink a chain measured by its loaded words; walkthrough Step 2a already established the point-at-the-contract pattern; a skill would be a THIRD location for content that currently has two
- **Files**: .claude/commands/review.md, .claude/commands/walkthrough.md, .claude/commands/build_module.md
- **Falsifier**: verifying-paths-not-taken

---

## Turn 3 — facilitator (decision)
*2026-08-12T19:30:22.346353+00:00 | confidence: 0.8*
*tags: path-not-taken, spec*

## Path Not Taken
- **Decision**: whether this slice relocates the critic-authored provenance narratives (Measured 2026-08-09 ..., an earlier version of this paragraph ...) out of the command files
- **Chosen**: leave every provenance narrative in place, verbatim
- **Rejected**: moving them to a referenced record (ADR appendix or docs/ note) with one-line pointers, recovering ~1500 words
- **Why rejected**: they are in-place regression guards written by blind reviewers, addressed to the future editor of THAT file; moving them where that editor will not see them reverses a reviewed decision — a developer fork, posed at this spec's approval gate instead
- **Files**: .claude/commands/review.md, .claude/commands/build_module.md, .claude/commands/walkthrough.md
- **Falsifier**: Measured 2026-08-09 over all 143 non-merge commits

---

## Turn 4 — facilitator (decision)
*2026-08-12T19:30:22.469455+00:00 | confidence: 0.8*
*tags: path-not-taken, spec*

## Path Not Taken
- **Decision**: whether this slice also dedups the tutor-loop dual specification (educator.md section 2 vs quiz.md Step 2)
- **Chosen**: neither file is touched
- **Rejected**: compressing quiz.md Step 2 to a dispatch wrapper that defers to the educator charter (~1000+ words)
- **Why rejected**: both files serve the AC12 human-facing education surface, where net thinning is barred without a named replacement and the developer's explicit say; the Wave-3 inverted-Blooms defect lived exactly in the charter-command seam, so thinning either side of that seam needs its own reviewed slice
- **Files**: .claude/commands/walkthrough.md, .claude/commands/review.md
- **Falsifier**: .claude/agents/educator.md section 2

---

## Turn 5 — facilitator (decision)
*2026-08-12T19:30:22.594066+00:00 | confidence: 0.8*
*tags: path-not-taken, spec*

## Path Not Taken
- **Decision**: how commands share one block's text
- **Chosen**: prose pointers naming file + exact heading, pinned by a heading-existence test
- **Rejected**: a transclusion/include mechanism for command markdown
- **Why rejected**: no such machinery exists in the repo; inventing an instruction-file preprocessor to save ~700 words fails the growth-side brake (PHILOSOPHY.md, Growth has a brake) and creates a new unreviewed execution surface
- **Files**: .claude/commands/review.md, .claude/commands/walkthrough.md, .claude/commands/build_module.md
- **Falsifier**: {{include

---

## Turn 6 — architecture-consultant (critique)
*2026-08-12T19:40:21.057414+00:00 | confidence: 0.85*
*tags: spec-review, slice-e*

Verdict: REVISE (confidence 0.85). Spec review of SPEC-20260812-122753.

Alignment verified: ADR-0016 + ADR-0034 §8 directly license the design (Step 10 already framed as the interface); walkthrough.md:137-144 already states the pointer pattern; no leak into the two out-of-scope forks; pointer directions correct; R1's safety-imperatives-stay-in-place split is right.

Findings:
1. Severity: HIGH — BLOCKING. R3 as worded collides with two pins the spec's Context list missed: tests/test_education_gate.py:2804-2834 (test_a_refuted_claim_is_surfaced_first; test_a_refuted_claim_leaves_the_gate_completable) require "Principle #5" and the surfaced-first / never-taught-as-fact phrases INSIDE walkthrough.md's own REFUTED subsection; in the live file (walkthrough.md:191-198) the citation is interleaved inside the second rule bullet, so "drop the justification, keep the rules" is not a clean textual cut. Fix: treat the two one-line rule imperatives like R1's safety-critical lines — keep verbatim in-place at both sites; point away only the extended elaboration; add both test names to the Context pin list.
2. Severity: MEDIUM — ADVISORY. R4's pointer targets "Step 10 item 5" — finer than any heading; R5's heading-existence test cannot detect list reordering. Fix: word the pointer at heading level, or extend the test to pin a stable phrase ("MECHANICALLY-CLEAR may never be promoted to VERIFIED").
3. Severity: LOW — ADVISORY. R1's "keeps" list omits the committing-changes cross-reference sentence (review.md:533-534 vs build_module.md:270-272); either add it to the list or let R6's line accounting decide its disposition.
4. Severity: INFO. AC2's premise is right in substance but `grep -c 'named 14 paths'` returns 1 not 2 — the phrase line-wraps in build_module.md:273-274. Use a whitespace-tolerant match.

Strengths: authoritative-copy choices grounded in who-reads-when; honest 500-900w recalibration; R7 halt-don't-cut. Verified: line refs accurate; git reset = 0 hits in both files; refuted-at-gate write_event block byte-identical at both sites; three-site two-vocabulary duplication confirmed.

---

## Turn 7 — qa-specialist (critique)
*2026-08-12T19:40:21.561639+00:00 | confidence: 0.88*
*tags: spec-review, slice-e*

Verdict: REVISE (confidence 0.88). Spec review of SPEC-20260812-122753. Every claim verified against the live suite and a throwaway git repo.

Findings:
1. Severity: CRITICAL — BLOCKING. tests/test_paths_not_taken.py is never named in the spec, yet it pins the SAME review.md sections R1/R4 edit, at sentence-level rigor: :1189-1219 requires a literal "Principle #5" within 600 chars of any "recorded complete" match in Step 10; :1135-1174 pins the instrument-failure loud-not-blocking arm; :721-765 requires >=2 full enumerations of the five RECORD_STATUSES in review.md, one before and one after the Step 10 heading. Fix: add the file to the Risk mitigation (grep removals against BOTH test files), to AC6's additive-only clause, and to Dependencies; baseline pytest run before editing review.md.
2. Severity: HIGH — BLOCKING. R3's planned removal collides with test_education_gate.py:2823-2834: the bare "Principle #5" citation and a "never blocks"-class sentence are pinned inside walkthrough's REFUTED subsection; the steer quote itself is NOT pinned (safe to drop). R3 must state what survives explicitly.
3. Severity: HIGH — BLOCKING. AC1 (grep -c 'git reset' >= 1) passes vacuously: verified in a throwaway repo that a bare `git reset -q` matches the grep AND silently unstages unrelated staged work in an entangled tree; the scoped `git reset -q -- <paths>` form verified correct (sibling staged changes intact). R2 also names no capture command for the previously-untracked paths. Fix: AC1 requires the literal scoped pattern `git reset -q -- `; R2 names `git status --porcelain --untracked-files=all` run BEFORE --intent-to-add as the capture; gate on the throwaway-repo verification.
4. Severity: MEDIUM — BLOCKING. AC2's literal command does not reproduce its own premise: grep -c 'named 14 paths' -> 0 in build_module.md (line-wrapped), 1 in review.md. Fix: non-wrapping token ("named 14") or wrap-folding check.
5. Severity: MEDIUM — ADVISORY (escalates to BLOCKING if R5 ships as cited). R5 cites the demonstrated-weakest pin pattern (whole-file substring, test_education_gate.py:2611-2621) whose own file records three green-under-mutation escapes of exactly this shape (:327-340). Fix: anchored line-start markdown-heading parse; AC4's mutation renames ONLY the heading line, leaving echoes intact.
6. Severity: MEDIUM — BLOCKING. AC5 has no pass state for the outcome R7 sanctions: a compliant HALT below 500 words leaves AC5 unmet — an incentive to violate the measurement-thinner veto to force AC5 green. Fix: AC5 = >=500 net reduction OR a recorded HALT naming the achieved number and the blocking pinned/measured sentences.
7. Severity: LOW — ADVISORY. AC7 sets no minimum bar for the critic "citing" the table; require >=1 named line-mapping + row-count parity vs the diff.
8. Severity: LOW — ADVISORY. AC3 premise verified (2 occurrences: review.md:1132, walkthrough.md:201); define the check as grep -c "refuted-at-gate" across both files == 1.

Strengths: spec's measure-don't-assert style made mechanical verification possible; R2's intended scoped-reset design is empirically sound — the gap is AC1's enforcement, not the idea.

---

## Turn 8 — independent-perspective (critique)
*2026-08-12T19:40:21.746802+00:00 | confidence: 0.82*
*tags: spec-review, slice-e, independent-analyst*

Verdict: APPROVE_WITH_ADVISORIES (no blocking findings; confidence 0.82). Independent Analyst instance. All headline numbers re-derived exactly (8,794 at 31bfe09; 20,510 at HEAD); Advisory 3 confirmed open (git reset = 0 hits both files); all four Paths Not Taken checked for straw men — none found; both engineering falsifiers verified absent from the tree; the developer steer quote verified real across 5 artifacts.

Findings:
1. Severity: MEDIUM — ADVISORY. The instrument conflates words-on-disk with per-run burden: no single run loads 20,510 words. The sharper burden number is review.md alone — 4,674 -> 8,937 (+91%), the largest never-skippable single-run load. Fix: report BOTH numbers at approval (chain total = maintenance metric; largest single-run load = burden metric).
2. Severity: MEDIUM — ADVISORY. R1's pointer is cold for the small-change workflow class: CLAUDE.md's 1-2-file path never invokes /build_module, so review.md's pointer targets a file that workflow never loads. Fix: accept the trade-off explicitly, and keep review.md's stub self-sufficient (the one-sentence why stays in-place; the pointer is depth, not correctness).
3. Severity: LOW/MEDIUM — ADVISORY. AC5's 500 floor sits at the bottom of the 500-900 projection and it is unstated whether R2's ADDED reversal text is netted out. Fix: state gross-vs-net explicitly and recompute the floor as net.
4. Severity: MEDIUM — ADVISORY. Steelman: ship R2 alone as a micro-fix and fold R1/R3/R4 into the same developer fork as the two deferred cuts — the full high-risk process cost is being paid mostly for the 4% recovery, not the urgent fix. The scoping choice (proceed as scoped vs consolidate the whole burden question into one fork) is itself a developer decision the spec makes implicitly. Fix: pose it at the approval gate; either answer defensible.
5. Severity: LOW — ADVISORY. Second consecutive small heavily-gated Phase B slice against a much larger named problem; "sensing without acting" is already an open MEDIUM advisory. Fix: on landing, record Advisory 4 as "PARTIALLY MITIGATED — Xw of 11,716w recovered across N slices" in BUILD_STATUS and keep the running tally visible across slices.
6. Severity: INFO. Strongest justification for R1/R3/R4 is drift-prevention, not yield: the two "identical" intent-to-add blocks have ALREADY diverged (throwaway-repo measurement vs Step-0 scope note). Lead the Goal with that; it survives the "only 4%" critique unconditionally.

Consensus check: isolated instance, no other findings seen. Flag to facilitator: the spec's self-disclosed weak yield must not be treated as having settled the worth-the-process-cost question — weigh finding 4 independently.

---

## Turn 9 — facilitator (synthesis)
*2026-08-12T19:43:34.097892+00:00 | confidence: 0.86*

## Request Context
- **What was requested**: Resume per HANDOFF-20260810-instruments-first-wave4.md item 3 — Phase B burden reduction (+115% five-command chain, REV-20260809-222916 Advisory 4), per-file measurement first.
- **Files/scope**: SPEC-20260812-122753 — single-source the paths-not-taken instruction surface across .claude/commands/{build_module,review,walkthrough}.md + one new pointer-integrity test; ship the missing intent-to-add reversal (Advisory 3, HIGH).
- **Developer-stated motivation**: extrapolated from the record (named sources: the burden advisory; the verbatim steer "I don't want to make it onerous and hard-gating"; the handoff build queue). Developer said only "resume here" this session.
- **Explicit constraints**: measurement-thinner veto; no guard or measured sentence lost; educator.md/quiz.md untouched; deeper cuts deferred to developer forks.

## Synthesis
Panel: architecture-consultant REVISE 0.85 (1 blocking) · qa-specialist REVISE 0.88 (4 blocking + 1 escalatable) · independent-perspective no-blockers 0.82 (6 advisories). Convergent theme: the spec's pin audit was incomplete and its ACs were gameable as literally worded; no reviewer disputed the design (authoritative-copy choices, pointer pattern, out-of-scope boundary all verified against ADR-0016/ADR-0034 and the live files).

Blocking findings, all addressed in rev 2 of the spec:
1. (qa CRITICAL) tests/test_paths_not_taken.py pins the same review.md sections R1/R4 edit and was never named — added to Context pin enumeration, Risk mitigation (baseline BOTH test files), AC6 additive-only clause, and Dependencies. Includes the >=2 RECORD_STATUSES-enumerations constraint now hard-limited in R4.
2. (arch HIGH + qa HIGH, convergent) R3's "drop the justification" collides with pinned sentences inside walkthrough's REFUTED subsection (bare "Principle #5", never-blocks phrases, surfaced-first phrases). R3 rewritten with an explicit RETAINS list (imperatives + citation stay in-place at both sites, like R1's safety split); only the extended elaboration + the duplicated write_event block move to a pointer. Steer quote verified unpinned — safe to single-source.
3. (qa HIGH) AC1 was vacuously satisfiable by an unsafe bare `git reset` (empirically shown to unstage unrelated work). AC1 now requires the literal scoped `git reset -q -- ` pattern + the named capture command (`git status --porcelain --untracked-files=all` before --intent-to-add) + throwaway-repo verification recorded; R2 rewritten accordingly.
4. (qa MEDIUM) AC2's grep could not see its own premise (line-wrap). AC2 now uses the non-wrapping token "named 14" with a wrap-tolerant check.
5. (qa MEDIUM) AC5 had no pass state for a compliant R7 HALT. AC5 now passes on >=400 net reduction OR a recorded HALT naming the blocking sentences; R7 recomputed net-of-R2 (panel: 500-900 was gross).
6. (qa MEDIUM-HIGH advisory, adopted) R5 now mandates anchored line-start heading parsing + echo-proof mutation (rename only the heading line), citing the three recorded green-under-mutation escapes of the substring pattern.

Advisories adopted: dual-metric framing (chain total = maintenance; review.md 8,937w +91% = per-run burden) now leads the Goal with drift-prevention as the unconditional warrant (the two intent-to-add copies HAVE already diverged); committing-changes cross-ref sentence added to R1's keeps list; cold-pointer trade-off on the small-change path accepted explicitly in Risk; new R8 keeps a cumulative Advisory-4 tally in BUILD_STATUS ("PARTIALLY MITIGATED — Xw of 11,716 across N slices") against the open sensing-without-acting advisory; AC7 hardened (named line-mapping + row-count parity); AC3 check defined as the tag grep.

Advisory carried to the developer, not decided here (independent-perspective F4): the scoping fork — proceed as scoped vs ship R2 alone as a micro-fix and fold the dedup into the same developer conversation as the two deferred cuts (provenance-narrative relocation ~1,500w; tutor-side dedup ~1,000+w). Posed at the approval gate with no recommended answer, per the high-risk grill rule.

Spec status: reviewed. reviewed_by: [architecture-consultant, qa-specialist, independent-perspective]. Developer approval (Step 8) PENDING — nothing is built until it arrives.

---
