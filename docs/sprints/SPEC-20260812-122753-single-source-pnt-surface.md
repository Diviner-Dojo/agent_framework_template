---
spec_id: SPEC-20260812-122753
title: "Slice E — single-source the paths-not-taken instruction surface; ship the missing intent-to-add reversal"
type: spec
status: complete
approved: developer, in-conversation, 2026-08-14 — "Proceed as scoped" (AskUserQuestion; supersedes the 2026-08-12 ntfy ask)
risk_level: high
reviewed_by: [architecture-consultant, qa-specialist, independent-perspective]
intake_ids: []
discussion_id: DISC-20260812-192946-single-source-pnt-surface-spec-review
build_discussion_id: DISC-20260815-060545-build-single-source-pnt-surface
build_review_id: REV-20260815-114838
completed_at: 2026-08-15
completed_commit: f4f41b3
completion_note: >
  AC1-AC4, AC6-AC8 PASS. AC5 satisfied as a recorded R7 HALT, not as a reduction: the chain
  grew +786 words (20,510 -> 21,296). No pinned or measured sentence was cut to chase the
  floor. Panel REVISE/REVISE/APPROVE_WITH_ADVISORIES; 5 blocking findings fixed in a revision
  pass, the largest being a staged-deletion hazard inside R2's own reversal. One HIGH advisory
  carried, not built: review.md Step 10 obligation 1 re-runs `-N` at the education gate with no
  reversal specified (outside R2's literal two-fence scope).
---

## Goal

Two goals on the same lines, and the first is the unconditional one:

1. **Stop a live drift.** The MANDATORY `--intent-to-add` rationale block exists twice and the
   copies have **already diverged** (build_module's carries the throwaway-repo measurement and
   the byte-size retraction; review's carries the Step-0 scope note). Single-source each
   duplicated paths-not-taken block to one authoritative copy — losing **zero** guard
   sentences and **zero** measured sentences — so the "why" of a safety-critical mandate
   cannot silently fork again. And ship the reversal instruction that REV-20260809-222916
   Advisory 3 (HIGH) found missing next to both `git add --intent-to-add --all` mandates.
2. **Recover words from the burden** (REV-20260809-222916 Advisory 4). Two metrics, kept
   distinct (panel finding — do not conflate them): the **maintenance metric** is the chain
   total, 8,794 → **20,510 words at HEAD (+133%)** vs pre-Wave-3 `31bfe09`; the **per-run
   burden metric** is the largest never-skippable single load, `review.md` alone at
   4,674 → **8,937 words (+91%)** — no single run ever loads the chain total. This slice's
   honest yield is small on both (≈3–4 %); the drift fix, not the yield, is why it is worth
   its process cost.

## Context

Fresh per-file measurement (2026-08-12, reproduced the advisory's 8,794 exactly at `31bfe09`):

| File | 31bfe09 | HEAD | Δ |
|---|---|---|---|
| `.claude/commands/plan.md` | 1,598 | 2,211 | +613 |
| `.claude/commands/build_module.md` | 1,700 | 3,346 | +1,646 |
| `.claude/commands/review.md` | 4,674 | 8,937 | +4,263 |
| `.claude/commands/walkthrough.md` | 342 | 3,012 | +2,670 |
| `.claude/commands/quiz.md` | 480 | 3,004 | +2,524 |
| **chain total** | **8,794** | **20,510** | **+11,716 (+133%)** |

Duplication found (word counts approximate, line-verified):

1. **The measured `--intent-to-add` rationale block** is near-verbatim twice:
   `build_module.md:258-276` (~250 w) and `review.md:527-537` (~180 w). Neither copy carries
   the reversal (`grep -c 'git reset'` → 0 in both) — that is Advisory 3 (HIGH), still open;
   this review's own checker run needed `git reset -q -- <the previously-untracked paths>`.
2. **The REFUTED-claim consequences** (the two rules, the `refuted-at-gate` `write_event`
   command, and the Principle #5 two-classes justification with the verbatim developer steer
   quote) appear in both `review.md` Step 10 (contract) and `walkthrough.md` Step 2a.
3. **The two-vocabulary explanation** (script statuses vs reader verdicts;
   MECHANICALLY-CLEAR may never be promoted to VERIFIED) appears three times: `review.md`
   Step 6.4 exit-0 bullet (provenance/history arm), `review.md` Step 10 item 5 (contract arm),
   `walkthrough.md` Step 2a (consumer arm).

Prior art: ADR-0016 (progressive disclosure) is the precedent for moving detail out of
always-read surfaces; `walkthrough.md` Step 2a itself states the governing rule ("a second
copy drifts from the contract it claims to implement — do not restate that list here");
the regression ledger's allowlist pattern (2026-06-06 row) gives the complementary rule:
where duplication is *intentional*, a sync test pins it — where it is not, single-source it.

**Load-bearing constraint (drafting + panel-completed enumeration):** TWO test files pin the
duplicated sentences at mutation-proven sentence level, and the builder must baseline and
re-grep against BOTH before removing anything:

- `tests/test_education_gate.py`: the walkthrough vocabulary paragraph is compared against
  the imported `RECORD_STATUSES`; the "MECHANICALLY-CLEAR may never be taught as VERIFIED"
  sentence; the UNVERIFIABLE slots in both `Task(...)` prompts; the handoff heading; AND
  (panel finding, missed in drafting) `test_a_refuted_claim_is_surfaced_first` +
  `test_a_refuted_claim_leaves_the_gate_completable` (≈:2804–2834), which require the literal
  `Principle #5` citation, a `never blocks`-class sentence, and the surfaced-first /
  never-taught-as-fact phrases INSIDE walkthrough.md's own REFUTED subsection.
- `tests/test_paths_not_taken.py` (panel finding — absent from the draft): pins the SAME
  `review.md` sections R1/R4 edit — a literal `Principle #5` within 600 chars of any
  `recorded complete` match in Step 10 (≈:1189–1219); the instrument-failure
  loud-not-blocking arm (≈:1135–1174); and **≥2 full enumerations of the five
  `RECORD_STATUSES` in `review.md`, one before and one after the Step 10 heading**
  (≈:721–765) — so the R4 dedup may not collapse the status enumerations.

The dedup must work AROUND the pins: pinned sentences stay where the tests read them. The
developer steer quote itself is NOT pinned anywhere (verified: it appears only in test
docstrings, never an assertion) — it is safe to single-source. Consequence, stated
honestly: this slice recovers roughly **500–900 words (~3–4 % of the chain)**, not the bulk
of the +115 %. The bulk sits in (a) the tutor-loop dual specification
(`educator.md` §2 ≈1,818 w + `quiz.md` Step 2 ≈1,308 w), which is AC12 human-facing surface,
and (b) the critic-authored provenance narratives ("Measured 2026-08-09 …", "an earlier
version of this paragraph …", ≈1,500 w), which are in-place regression guards written by
blind reviewers. Thinning either reverses reviewed decisions — **a developer fork, posed at
this spec's approval gate, deliberately not scoped here.**

## Requirements

- **R1 — single-source the intent-to-add rationale.** `build_module.md` Step 6.5 keeps the
  full measured block (the "2+ new files under src/" trigger is where false-PHANTOM risk is
  born). `review.md` Step 6.4 keeps, self-sufficiently (the pointer is depth, never
  correctness — panel: the small-change workflow never loads `build_module.md` at all, so
  the pointer is cold for that class; accepted trade-off): the MANDATORY imperative line,
  the one-sentence why (untracked files invisible → false PHANTOM), the "never follow with
  `commit -a`" safety sentence, the `committing-changes` Step 1.8 cross-reference sentence
  (staging governance stays visible at both sites), the reversal (R2), and an explicit
  pointer to `build_module.md` Step 6.5 for the full measured rationale. Safety-critical
  imperatives stay in-place at BOTH sites; only rationale/measurement narrative is
  single-sourced.
- **R2 — ship the reversal (Advisory 3, HIGH).** Adjacent to BOTH `git add --intent-to-add
  --all` lines: FIRST capture the previously-untracked paths with
  `git status --porcelain --untracked-files=all` (run BEFORE `--intent-to-add`), then after
  the diff is handed to the checker, un-register exactly those paths with the SCOPED form
  `git reset -q -- <the captured paths>` — never bare `git reset` and never `.` (panel
  verified empirically: the bare form silently unstages unrelated staged work in an
  entangled tree; the scoped form leaves sibling staged changes intact). The builder
  re-verifies the mechanics on a throwaway repo and records commands + outputs in the build
  discussion; AC1 is not satisfiable without that record.
- **R3 — single-source the REFUTED-claim consequences.** `review.md` Step 10's contract is
  authoritative (it already declares itself the interface). `walkthrough.md` Step 2a's
  REFUTED subsection RETAINS, verbatim and in-place (all pinned or load-bearing): the
  four-status "what you say" table, the UNVERIFIABLE treatment, the two one-line rule
  imperatives ("never taught as fact — surfaced first, stated plainly"; "never blocks,
  delays, or withholds… and never keeps the developer from closing the gate"), the bare
  `Principle #5` citation inside that subsection, and every sentence matched by
  `test_a_refuted_claim_is_surfaced_first` / `test_a_refuted_claim_leaves_the_gate_completable`.
  What moves to a pointer (naming `review.md` Step 10's contract subsection by exact
  heading): the EXTENDED justification only — the two-classes elaboration beyond the bare
  citation, the steer-quote elaboration (unpinned, verified), and the duplicated
  `refuted-at-gate` `write_event` block (the authoritative copy stays in the contract).
- **R4 — dedup the two-vocabulary explanation to its two load-bearing arms.** The contract
  arm (Step 10) and the test-pinned consumer paragraph (walkthrough) stay. The third
  restatement inside Step 6.4's exit-0 bullet keeps ONLY its provenance half (why `VERIFIED`
  was retired, the 2026-08-09 experiment) and points to the contract subsection for the
  two-layer rule. Two hard limits (panel): the pointer targets a STABLE PHRASE
  ("MECHANICALLY-CLEAR may never be promoted to VERIFIED"), pinned by R5's test — never a
  list-item number; and `review.md` must retain ≥2 full enumerations of the five
  `RECORD_STATUSES`, one before and one after the Step 10 heading
  (`tests/test_paths_not_taken.py` ≈:721–765 fails otherwise).
- **R5 — pointer integrity is tested.** Every pointer added by R1/R3/R4 names file + exact
  heading (plus the R4 stable phrase). A new test asserts each pointed-to heading exists in
  the pointed-to file **as an anchored line-start markdown heading** (`^#{1,6} <exact text>`
  match — NOT a whole-file substring check, which is the demonstrated-weakest pattern in
  `tests/test_education_gate.py`, with three recorded green-under-mutation escapes of that
  shape), and that the R4 stable phrase exists in the contract subsection. Mutation proof:
  rename ONLY the heading line while leaving any echo of its text elsewhere in the file
  untouched → test must go RED (proves the check is not vouched for by an echo).
- **R6 — line accounting.** The builder produces a table mapping every removed line to its
  surviving authoritative line (or marking it a pure pointer insertion), captured in the
  build discussion. The blind critic verifies the table against the diff. Any removed line
  with no surviving copy fails the slice.
- **R7 — the number is recorded, net and honestly.** Before/after chain word count (same
  method as the table above) written into the build discussion, as a NET figure — R2's
  added reversal text and R5's pointer insertions count against the dedup (panel: the
  500–900 projection was gross-of-R2; net expectation is ≈400–800). Floor: ≥400 words net
  reduction; if the achievable net lands below that after respecting the pins, HALT and
  report the achieved number plus the specific pinned/measured sentences blocking further
  reduction, rather than cutting one of them to hit the number. A compliant HALT is a
  passing terminal state for AC5, not a failure.
- **R8 — the running tally survives the slice.** On landing, record Advisory 4's status in
  BUILD_STATUS as "PARTIALLY MITIGATED — <net words> of 11,716 recovered across <N> Phase B
  slices", cumulative across slices, so individually-honest small wins cannot read in
  aggregate as "Advisory 4: handled" ("sensing without acting" is an open advisory in this
  repo; this is its antidote for this thread).

## Constraints

- No vocabulary changes: `RECORD_STATUSES`, the reader verdicts, and every status word stay
  byte-identical. Consumer-visible vocabulary moves need a named carrier (CONTRACTS.md §4).
- `educator.md` and `quiz.md` are NOT touched (AC12 human-facing surface; any tutor-side
  dedup is a separate slice behind a developer decision).
- No transclusion/include machinery is invented for command files.
- `docs/education/CONTRACTS.md` untouched. No existing `docs/adr/` file edited.
- Tests: no existing assertion weakened or deleted; `tests/` changes are additive.
- Every "Measured …" sentence and every "do not restore …" warning in the touched sections
  survives verbatim in exactly one location (the measurement-thinner veto applies to prose
  guards too).
- House rules: no commit/push/merge/branch ops by dispatched agents; no
  `.claude/settings.json` edits; nothing truncated under `discussions/`; read-only SQL on
  `metrics/evaluation.db`; agent tests write only to `tmp_path`.

## Acceptance Criteria

- [ ] AC1: the literal SCOPED pattern `git reset -q -- ` appears ≥ 1 time in
      `build_module.md` AND in `review.md`, each within the intent-to-add code fence, with
      the R2 capture command (`git status --porcelain --untracked-files=all`) preceding the
      `--intent-to-add` line (Advisory 3 closed at both sites; a bare `git reset` does NOT
      satisfy this — panel verified it silently unstages unrelated work). The builder's
      throwaway-repo verification (commands + outputs) is in the build discussion.
- [ ] AC2: the non-wrapping token `named 14` appears exactly **once** across the two command
      files, measured with a wrap-tolerant check (read file, collapse whitespace, count) —
      the draft's `named 14 paths` grep was line-wrap-broken (returned 1, not the true 2).
- [ ] AC3: `grep -c "refuted-at-gate"` summed across `review.md` + `walkthrough.md` equals
      **1** (currently 2: review.md:1132, walkthrough.md:201); walkthrough retains its
      four-status table and every sentence named in R3's RETAINS list.
- [ ] AC4: new pointer-integrity test exists, green, anchored per R5, and demonstrated RED
      under the echo-proof mutation (rename only the heading line, leave echoes) — mutation
      run recorded with exit codes in the build discussion.
- [ ] AC5: NET chain word-count reduction ≥400 vs the 20,510 baseline (before/after + net
      arithmetic in the build discussion), **OR** a recorded R7 HALT naming the achieved
      number and the specific pinned/measured sentences blocking further reduction. Both are
      passing states; cutting a pinned or measured sentence to reach the number is the only
      failing state.
- [ ] AC6: full suite green (`pytest` exit 0); `tests/test_education_gate.py` AND
      `tests/test_paths_not_taken.py` each unmodified or additive-only
      (`git diff -U0 <file> | grep '^-'` empty).
- [ ] AC7: line-accounting table present in the build discussion; the blind critic's verdict
      names at least one specific line-mapping from it AND confirms row-count parity against
      the diff's actual removed-line count (a one-line acknowledgment does not satisfy this).
- [ ] AC8: quality gate 8/8 PASS (exit 0).

## Risk Assessment

- **A pointer hides a guard at the moment it is needed** (runner does not follow it).
  Mitigation: R1/R3 keep every safety-critical imperative in-place at the point of use;
  only rationale narrative is single-sourced — the same split Step 10's contract already
  practices.
- **False dedup** — two blocks that look alike but differ in one load-bearing clause
  (the two intent-to-add blocks already differ: build_module's carries the throwaway-repo
  measurement and the byte-size retraction; review's carries the Step-0 scope note).
  Mitigation: R6 line accounting + blind critic; diff-level, not memory-level, comparison.
- **Breaking the test pins.** Mitigation: builder baselines
  `pytest tests/test_education_gate.py tests/test_paths_not_taken.py -q` BEFORE editing any
  command file; every sentence to be removed is grepped against BOTH test files (and the rest
  of `tests/`) first; AC6 covers both files additively.
- **The cold pointer on the small-change path** (accepted, panel finding): the 1–2-file
  workflow never loads `build_module.md`, so R1's pointer is genuinely foreign there.
  Accepted because review.md's stub stays self-sufficient for correctness — the pointer buys
  depth, not safety.
- **Scope creep into the fork** (tutor-side, provenance narratives). Mitigation: named
  out-of-scope constraints + paths-not-taken records below; the fork is posed to the
  developer at approval, not decided here.

## Affected Components

- `.claude/commands/build_module.md` (R1, R2)
- `.claude/commands/review.md` (R1, R2, R3-authoritative-side, R4)
- `.claude/commands/walkthrough.md` (R3-pointer-side)
- `tests/test_command_pointer_integrity.py` (new, R5) — or an additive class in
  `tests/test_education_gate.py`; builder's call, recorded either way

## Paths Not Taken

## Path Not Taken
- **Decision**: where the single-sourced content lives
- **Chosen**: existing files stay authoritative (`build_module.md` Step 6.5 for the
  intent-to-add rationale; `review.md` Step 10 for the consequences); pointers by exact heading
- **Rejected**: a new `verifying-paths-not-taken` skill as the shared home
- **Why rejected**: it adds a file and a skill-load indirection to shrink a chain we are
  measuring by its loaded words; walkthrough Step 2a already established the
  point-at-the-contract pattern, and a skill would be a THIRD location for content that
  currently has two
- **Files**: .claude/commands/review.md, .claude/commands/walkthrough.md, .claude/commands/build_module.md
- **Falsifier**: verifying-paths-not-taken

## Path Not Taken
- **Decision**: whether this slice relocates the critic-authored provenance narratives
  ("Measured 2026-08-09 …", "an earlier version of this paragraph …") out of the command files
- **Chosen**: leave every provenance narrative in place, verbatim
- **Rejected**: moving them to a referenced record (ADR appendix or docs/ note) with one-line
  pointers, recovering ≈1,500 words
- **Why rejected**: they are in-place regression guards written by blind reviewers ("do not
  restore" addressed to the future editor of THAT file); moving them where that editor will
  not see them reverses a reviewed decision — a developer fork, posed at this spec's
  approval gate instead
- **Files**: .claude/commands/review.md, .claude/commands/build_module.md, .claude/commands/walkthrough.md
- **Falsifier**: Measured 2026-08-09 over all 143 non-merge commits

## Path Not Taken
- **Decision**: whether this slice also dedups the tutor-loop dual specification
  (`educator.md` §2 vs `quiz.md` Step 2)
- **Chosen**: neither file is touched
- **Rejected**: compressing `quiz.md` Step 2 to a dispatch wrapper that defers to the
  educator charter (≈1,000+ words)
- **Why rejected**: both files serve the AC12 human-facing education surface, where net
  thinning is barred without a named replacement and the developer's explicit say; the
  Wave-3 inverted-Bloom's defect lived exactly in the charter↔command seam, so thinning
  either side of that seam needs its own reviewed slice
- **Files**: .claude/commands/walkthrough.md, .claude/commands/review.md
- **Falsifier**: .claude/agents/educator.md section 2

## Path Not Taken
- **Decision**: how commands share one block's text
- **Chosen**: prose pointers naming file + exact heading, pinned by a heading-existence test
- **Rejected**: a transclusion/include mechanism for command markdown
- **Why rejected**: no such machinery exists in the repo; inventing an instruction-file
  preprocessor to save ~700 words fails the growth-side brake (PHILOSOPHY.md "Growth has a
  brake") and creates a new unreviewed execution surface
- **Files**: .claude/commands/review.md, .claude/commands/walkthrough.md, .claude/commands/build_module.md
- **Falsifier**: {{include

## Dependencies

- Depends on: REV-20260809-222916 (Advisories 3 + 4 are the warrant); the live
  `verify_paths_not_taken.py` mechanism (ADR-0034); `tests/test_education_gate.py` AND
  `tests/test_paths_not_taken.py` pins (both are constraints on every edit this spec makes).
- Depended on by: any later burden slices (the two forks named above), which reuse R6's
  line-accounting pattern and R5's pointer-integrity test.
