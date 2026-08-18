# Build Status

## Async loop state
- state: **armed**
- resume recipe: `python scripts/collab_loop.py check 48h` then arm a persistent Monitor on `python scripts/collab_loop.py poll`
- monitor: **none armed** as of 2026-08-14 (slice E poller stopped after the developer answered
  at desk; `say` ack sent. Re-arm only after `check`, exactly ONE poller).
- pending question: none. **Slice E RESOLVED in-conversation 2026-08-14: "Proceed as scoped"**
  (supersedes the 2026-08-12 ntfy ask). Session queue locked by the developer, same
  conversation: BOTH deeper burden cuts queued as future gated slices (tutor-loop dedup +
  narrative relocation, each own /plan + panel + his approval + education gate);
  ADR-0034/0035 = TEACH FIRST then he decides approval and runs the clear himself;
  plus /retro, the two ADR-0033 round-5 decisions, and the S8 propagation prerequisites
  (tests/ into FRAMEWORK_PATHS + nine-principle reconciliation prep — NO propagation).
  Education-debt backlog (7 old gates) explicitly NOT queued this session.
- context: 2026-08-14 interactive→long session, branch `feat/framework-v4-instruments-first`.
- **DEVELOPER CONNECTIVITY IS INTERMITTENT (beach, 2026-08-08/09).** Do not block on replies;
  extrapolate from the record, NAME what you extrapolated from, and batch anything that genuinely
  needs him. ntfy is THE channel when he is away. Do not ask in IDE chat.
  Every question/approval goes out via `collab_loop.py ask` with tap-to-answer choices; answer
  every inbound reply. Ping on: slice verdicts, genuine forks, wave completion. Not every step.
- known ops gotcha (cost a live handoff 2026-08-07): a stale phone subscription presents as a
  "connection error" while the server is healthy — **resubscribe first**. `say` printing
  `said OK` verifies PUBLISH ONLY, never receipt; confirm with a real round trip.

## ⮕ NEXT SESSION

> **DECK PROMOTION THREAD (2026-08-18) — ✅ COMPLETE THROUGH PUSH (developer-ordered).**
> Adopter-first rewrite of both public decks promoted onto the live paths (17+20 slides),
> reviewed and pushed to PR #110. `/review` DISC-20260818-200843 (ensemble, 2 specialists):
> ux-evaluator 0.83 + docs-knowledge 0.88, both approve-with-changes → **verdict
> approve-with-changes, `docs/reviews/REV-20260818-131919.md`**. Both HIGHs (expand-panel
> clipping at 200% zoom; risk-table floor-vs-target inversion on the Critical row), all 3
> docs MEDIUMs (quiz Bloom weighting; slide-6→7 ref; gate-before-review flow order) + INFO
> pointer FIXED pre-commit; guard 23/23 after fixes; gate green. **OPEN ADVISORIES (6, ux
> polish batch):** keyboard access on expand widgets; --text-muted contrast <4.5:1 at small
> sizes; emoji aria-hidden; nav boundary feedback; scrollTop reset on revisit; how-to
> closing return-CTA. Hooks denominator still the developer's open decision (decks state no
> count). **Developer merges PR #110 himself:**
> https://github.com/Diviner-Dojo/agent_framework_template/pull/110
>
> **If resuming the PROMOTION thread instead:** start at
> `docs/handoff/HANDOFF-20260818-promotion-branch-ready-awaiting-push.md` (newest for that
> thread; the prior `…b2-committed-promotion-next.md` still exists beside it), then
> `docs/reviews/REV-20260818-004500.md` and `docs/adr/ADR-0036-retire-framework-md-one-constitution.md`.
> **B2 IS DONE AND COMMITTED (`8033191`)** — `FRAMEWORK.md` deleted, `/seed` inlines the seven,
> ADR-0036 written, reviewed by a 3-specialist panel at approve-with-changes with all three
> BLOCKING findings fixed before the commit. Education gate cleared. Suite 2944/exit 0, gate
> 8/8/exit 0. **62 ahead of `upstream/main`, 0 behind. Nothing pushed.**
>
> **NEXT: the CORE-only promotion branch.** ⛔ HARD REQUIREMENT found in review — public
> `CLAUDE.md` carries **nine** principles, public `PHILOSOPHY.md` says "eight", and **ADR-0031
> was never promoted** (newest public ADR is 0028). The PR must carry `CLAUDE.md` +
> `PHILOSOPHY.md` + ADRs 0029–0036, or deleting `FRAMEWORK.md` leaves the public template
> strictly worse. Size with **two-dot** (three-dot lies); verify no SKIN leak.
>
> **Open advisories are NOT closed** — H2 is a derived-project push-blocker; `agentic_journal`
> carries **9** principles and `VerificationPortal` **10** (measured, after four artifacts said
> "eight" without anyone counting).

**The v4 RECONCILIATION IS RETIRED.** Read `docs/adr/ADR-0032-retire-v4-reconciliation-instruments-first.md`,
then `docs/reviews/REV-20260807-164855.md`. ADR-0031 is **superseded, never deleted** (Principle #4) —
its wrong-merge-base story and "performed honesty displacing the real check" finding are its value.
Branch `claude/framework-modernization-opus-tr3ce9` is a REFERENCE to mine, **never a merge target**.

**Approach (developer-decided 2026-08-07): ablate `main` IN PLACE, machinery live, vertical slices,
each blind-reviewed by a critic that never sees the builder's reasoning.** Three decisions:
(a) **INSTRUMENTS FIRST, then delete** — measured deletable scaffolding is **under 4%** of the
9,202-line instruction surface, while the measurement layer was found broken;
(b) education KEEPS walkthrough+quiz and **fixes the self-grading defect** (98.2% pass rate is
graded by the same model that teaches — it measures activity, not comprehension);
(c) telemetry builds **toward the Layer B dashboard**, not quarantined.

Working branch `feat/framework-v4-instruments-first`. **Nothing pushed, merged, or propagated.**

**COMMITTED (12 + Wave 3 slices, gate green 8/8):** Waves 1/1b/1c/1d + 2/2b — ADR-0032, the
seven-principle constitution, broken instrument SQL, the context-sensor resolver, Layer 1
integrity, the collab_loop allow-list + forged `REPLY-MATCH`, the yield-loop reader, the cap
recalibration (ADR-0033), the `--rebaseline` CLI test, test isolation, and the
context-countdown removal. **Wave 3 committed 2026-08-09** (per-slice commits; see Current
Session). `.claude/settings.json` is the ONLY path left uncommitted — it carries the
developer-parked Stop hook and is excluded from every commit on purpose.

**WAVE 3 — built + blind-reviewed + Steward-gated + independently verified + committed.**
Four slices, each blind-reviewed by a critic that never saw the builder's reasoning:
- **A — education gate rebuilt as a TUTOR.** Fixed a 21-day-live 3-way INVERTED Bloom's ratio:
  `educator.md` charters 30% Understand/Apply · 70% Analyze/Evaluate, while `/quiz` and
  `selecting-review-gates` both ORDERED the inverse — the dispatching command commanded the agent
  to do the opposite of its own charter, which is the syntax-quiz feeling the developer objects to,
  mechanically enforced. `educator.md` won. Grade-centric assessment replaced by a re-teach loop
  (on a miss, re-explain from a different ENTRY POINT, never a synonym swap, and ask again).
- **B — the education deferral backlog is surfaced** at session start. 7 gates open, six ~60 days
  old, and NOTHING under `.claude/` read the registry. Informational only — deliberately NOT a gate
  (`governance-mechanisms.md` Row 6 rules that turning it into a build condition needs its own
  `/plan` + Steward gate).
- **C — paths not taken** (`ADR-0034`, `scripts/verify_paths_not_taken.py`, ~1250 lines).
  Builders record the alternative AT THE MOMENT OF THE CHOICE; a script re-checks the claims against
  the diff. Steward-gated REVISE → APPROVE.
- **The seam** — `/walkthrough` + `/quiz` consume C's verification handoff.

**⮕ NEXT, in order:** (1) ~~independent verification + REV + per-slice commits~~ **DONE 2026-08-09**
(REV-20260809-222916; verification checks a-d all PASS, commands + exit codes in the REV);
(2) **developer decisions** — the `.claude/settings.json` SessionStart matcher edit
(`"resume|compact"` → `"startup|resume|compact"`; B's nudge is INVISIBLE on fresh sessions until
then), the unreviewed Stop hook in the same file, Principle #6 approval of ADR-0034, and the
tutor-asymmetry question (REV Advisory 1 — posed to the developer, unanswered); (3) **Phase B
deletion**, per-file must-preserve checks — see the measured corrections below; (4) the
developer's 7-question bar; (5) S8 propagation — **BLOCKED on per-instance approval, every time.**

**⚠ PHASE B: TWO CARRIED NUMBERS ARE WRONG.** Measured 2026-08-08, exit codes checked:
the Persona Bias Safeguard is **37 lines across 10 files, not 27** (`project-analyst.md`'s is 8
lines, not the uniform 3 — so "zero couplings" needs a per-file check, not an extrapolation);
`/distribute` is **17 lines, not 21**. Confirmed as stated: the ordering mandate is in 10 of 12
agent files (absent from `facilitator.md`, `steward.md`); `grill-yourself` is installed 0/4 while
its sibling `grill-me` is 3/4 — the contrast is the evidence, not the zero.
**And the scope limit is softer than feared:** both thresholds named as must-preserve are ALREADY
duplicated outside the Domain Lens block (`ux-evaluator.md:22` → also `:59`/`:62`;
`history-analyst.md:19` → also `:37`). That does not retire the constraint — it means slice D must
check it PER FILE rather than assume it from those two specimens. Detail in the scratchpad note.

**⚠ FOUR DEFECTS FOUND BY USING THE FRAMEWORK, NOT SURVEYING IT** — all the same shape, *a mechanism
reporting success it never verified*: `PROTECTED_PATTERNS` is wired on `Write|Edit` only so `Bash`
routes around it (a subagent truncated a sealed `events.jsonl`; no pre-existing history lost);
`collab_loop say` prints `said OK` for PUBLISH, never receipt; a closed question's allow-list latches
and silently discards all later developer free-text; and a newline in a choice label **forges a
`REPLY-MATCH: Approve` line** — a forged human approval the goal-loop gate would honour.
**⚠ Plus a structural one (S11, not yet built):** agent tests have twice contaminated PRODUCTION
state — a sealed Layer 1 file and the live channel lockfile. There is no test/production isolation.
**⚠ Derived-project gaps:** `dan_research_karpathy_wiki` carries `validate_tool_use.py` with **no
`PreToolUse` block at all**; `.git/hooks/pre-commit` exists in 1 of 4 (the template's copy is
untracked, so it has never been able to propagate); all four still carry the NINE-principle
numbering, which must be reconciled before the renumbered layer propagates.
**⚠ Steer by `memory/project_north_star_memory_scaffolding.md`** — the framework is the prototype of a
memory prosthesis with *passive* capture; the test is not only "does the model still need this" but
"does this serve a memory a human can rely on across years." Where those disagree, surface it.

## Current Session (2026-08-16, interactive — THREE BLOCKING DECISIONS ANSWERED)

**✅ DEVELOPER DECISIONS (AskUserQuestion, 2026-08-16) — all three handoff-owed items answered:**
1. **Session start: the slice E education gate.** `/walkthrough` on the slice E surfaces;
   walkthrough-only per the 2026-08-14 lightweight steer; **only he runs the clear.**
2. **⮕ VERSION NAMED: `v3.6` — AND APPLIED 2026-08-16.** Continue the 3.x line. Rationale:
   `v3.5` is the live public identity, the instruments-first work is evolutionary rather than a
   redesign, and reusing "v4" would resurrect a name **ADR-0032 explicitly retired**. The branch
   name `feat/framework-v4-…` is historical, not a version claim. **This unblocks `/ship`.**

**✅ v3.6 APPLIED — all live surfaces agree; suite 2944 passed / 3 skipped / exit 0 (identical
to the pre-change baseline).** Bumped via the canonical `scripts/bump_version.py --minor`
(3.5.0 → 3.6.0; it owns `pyproject.toml` ONLY — every other surface is manual per the
`syncing-framework-docs` sync table): `CLAUDE.md:7`, `docs/FRAMEWORK_SPECIFICATION.md`
frontmatter + title + `last_updated` + a new dated v3.6 changelog row, the presentation
`<title>`/badge/footer, and the how-to-use footer. The 2026-05-16 v3.5 changelog row is HISTORY
and was left; the `3.5rem` CSS hits are false positives.

**⚠ THE HANDOFF'S VERSION FRAMING WAS WRONG ON ONE OF ITS FOUR, and the error was in the
direction of doing unnecessary damage.** It listed `framework-lineage.yaml`'s
`1.0.0+upstream.2.1.0` as a fourth disagreeing version name. **Measured: it is not a version
claim at all — it is a derivation fingerprint.** `scripts/lineage/init_lineage.py:123` hardcodes
`f"1.0.0+upstream.{template_version}"`; the `1.0.0` is a bootstrap constant and **no code path
anywhere bumps `instance.version`**. The file is also **byte-identical on `upstream/main`**, so
editing it would have manufactured a promotion diff for nothing. **Left untouched deliberately.**
An earlier note in this block proposed `1.1.0+upstream.2.2.0` — that was invented lineage
semantics and is retracted. Do not "fix" this file without a Steward-gated decision on what
instance.version is FOR.

**⏳ PROPAGATION PREREQUISITES — 2 of 3 DONE, 1 BLOCKED ON A DEVELOPER FORK (2026-08-16).**
Suite 2944 passed / 3 skipped / exit 0 (unchanged). 9 files, uncommitted, **`/review` owed
before commit** — it touches `scripts/` and `tests/`, so it is NOT docs/config-only.

- **✅ Nine-principle reconciliation (template-local instalment).** Far bigger than the handoff
  implied: the debt was **not only in the derived projects**. The template's own agent-facing
  commands cited retired numbers (`goal-loop.md` cited **#9** for the design-fork stop and **#4**
  for builder≠checker; `apply-framework.md` cited retired **#8** twice), and
  `FRAMEWORK_SPECIFICATION.md` — the authoritative doc that **propagates** — still enumerated all
  **nine** principles under the old numbering, as did the stakeholder deck. Rewritten to the seven
  with a **renumbering map** and both retirements recorded rather than dropped (Principle #4's
  logic applied to principles), preserving the external attribution on retired #8. Also synced:
  `STEWARD_ARCHITECTURE.md`, both presentation HTMLs, and docstrings in `scripts/distribute/` +
  `scripts/telemetry/` (scripts/ propagates, so stale citations there travel).
  **`tests/test_constitution_consistency.py` already carried a `KNOWN_STALE_CITATIONS` debt
  register for exactly this** — 6 files re-measured to zero and their entries DELETED; the guard
  forbids widening, so it was re-measured, never loosened.
- **⚠ The spec's entry was KEPT at (1,2) — all three remaining hits are DETECTOR FALSE
  POSITIVES**, a fifth+ specimen of this effort's recurring class: L1332 is the retirement NOTE
  itself ("was Principle #8 until v3.6"); L576/L1262 each name TWO concepts on one line, so the
  keyword heuristic expects the education slot (#5) while the line correctly cites #3. Registered
  with that reason rather than deleted, and **the prose must NOT be reworded to appease it**.
- **⚠ TWO GUARDS CAUGHT ME, both legitimately.** `TestPluralityLanded` fired because my Principle-3
  note PARAPHRASED the panel-size floor — the floors have a single normative home and every
  restatement must match verbatim; fixed by quoting all three lines.
  **CORRECTED 2026-08-17 — this named the wrong guard.** The one that fired was
  `test_plurality_floors_do_not_drift`, the NUMERIC check, which scans every live file
  mentioning "plurality" and compares tier→number pairs.
  `test_every_restatement_of_the_block_is_verbatim` could not have fired: it only inspects
  files carrying the `### Panel size — review plurality` heading, and the spec had no such
  heading, which is precisely why its copy was a third **unguarded** one. Both halves are
  closed now — the spec carries the heading AND a byte-identical block (all three copies
  sha256 `13bc3955…`), so the verbatim guard watches it for the first time. `TestConceptBindingCoverage`
  fired at 82.5% against an 85% floor because corrected-but-BARE citations are uncheckable; fixed
  by adding concept anchors from the guard's own `CONCEPT_KEYWORDS` vocabulary. Both are the
  "a bare number is not a checkable claim" mechanism working.
- **✅ False `security_baseline` sentence — spec synced.** `FRAMEWORK_SPECIFICATION.md`'s
  secret-detection sections described *what is scanned* and never what the hook **decides**. Now
  carries all four measured limits: it emits **`ask`, not `deny`** (and `ask` is the weaker
  decision under `bypassPermissions`, which our own supervisor runs); it **never sees a commit**
  (wired on `Write|Edit`, not `Bash`); test files are exempt **outright** with the literal
  `TEST_FILE_PATTERNS` cited rather than glossed; and 12 regexes are a list that ends. Named
  plainly as defence-in-depth, **not a secret-scanning gate**.
- **⛔ `tests/` into `FRAMEWORK_PATHS` — CLOSED AS MIS-SCOPED (developer decision, 2026-08-16).
  The advisory is wrong as literally worded, and it was never a promotion blocker.** Do NOT add
  the bare prefix. Three measurements, each re-runnable:
  1. **`FRAMEWORK_PATHS` drives BOTH drift detection AND the propagation offer set**
     (`scripts/lineage/manifest.py:21`; consumed by `_utils.collect_framework_files`,
     `drift.py:109`, and `change_package.greenfield_offer_set`). Adding a prefix is not cosmetic.
  2. **Size is not the obstacle**: corpus 191 → 241 files against `MAX_GREENFIELD_OFFER = 5000`.
  3. **Coupling IS the obstacle, and it is worse than the `src/` half.** **19 of 49** test files
     are template-coupled: 7 import from `src/` (which does NOT propagate — they would ship with
     no subject), and **12 more assert on `CLAUDE.md` / `PHILOSOPHY.md` / `BUILD_STATUS.md` /
     `REVIEW.md` / `framework-lineage.yaml`**, every one of which a derived project customizes.
     Wholesale propagation ships **39% of the suite** in a state that fails or falsely passes.
  **Why it is not a promotion prerequisite:** `FRAMEWORK_PATHS` governs `/apply-framework` →
  **derived projects**. The public promotion is a git push of the whole tree, so `tests/` travels
  regardless of this constant. Propagation to the four derived projects is a separate action,
  per-instance gated, and is not happening today. **The underlying ADR-0028 concern — guard tests
  must travel with the capability they guard, or defects ship unguarded — remains REAL and is now
  owned by the propagation effort, not by the PR.** Options costed and parked: move portable
  guards to `tests/framework/` (cleanest, ~30-file move, re-points every cited pytest node id);
  an explicit exclusion register + rot-guard in the `KNOWN_STALE_CITATIONS` idiom; or an
  `/apply-framework` check that reports missing guard tests. **Caveat on the number: "portable"
  is a PROXY** (src-import + SKIN-filename scan) — some of the 30 may be coupled in ways the scan
  cannot see, so re-measure before acting on it.

**⛔ /review VERDICT: approve-with-changes — `docs/reviews/REV-20260816-194513.md`.** Panel of 3
(high-risk floor 2), none shown the build reasoning: docs-knowledge APPROVE_WITH_ADVISORIES 0.90 /
qa-specialist APPROVE_WITH_ADVISORIES 0.93 / independent-perspective **REVISE 0.86**. 3 blocking,
6 advisory, 0 speculative. **NOT COMMITTED — the 10 files remain uncommitted pending the fixes.**

**What the panel CONFIRMED** (so this is not a rewrite): every renumbered citation correct against
CLAUDE.md, verified two independent ways; **the guard was not weakened and this was MUTATION-PROVEN**
— three injected violations each went RED with the correct assertion message, restored byte-for-byte
with sha256 verification, GREEN after, tree clean; exemption surface SHRANK (6 entries deleted, 1
tightened; `MIN_CONCEPT_COVERAGE` NOT lowered, `CONCEPT_KEYWORDS` NOT touched; coverage 86.8→87.3 by
un-exempting files); the security correction accurate against `validate_tool_use.py:1518-1529` and
`:1379-1381`; **the tests/ deferral held under attack** with a measurement I had not made —
`git ls-tree -r upstream/main -- tests/` = 36 files, tests/ is ALREADY public.

**⚠ META-FINDING (the most important line): "the boundary tracked what the tooling made LOUD."**
Every out-of-range citation (#8/#9) was fixed; every concept-mismatch one was not. Scope drawn by
the detector rather than by the change's blast radius. **THE CLEAN TELL — a contradiction inside my
own reasoning:** `FRAMEWORK.md` was excused as "does not propagate" while `tests/` was deferred
BECAUSE "the promotion pushes the whole tree." Both in artifacts this change touched; only one can
be true. No single context catches that — direct evidence for Principle #3.

**3 BLOCKING, all facilitator-verified:** B1 `selecting-review-gates/SKILL.md:46-47` still publishes
the retired four-step hard gate + the invented third non-declinable class this change's own prose
says was struck (fixed in the consumer, left in the NORMATIVE SOURCE; ships to 4 derived projects).
B2 `FRAMEWORK.md` publishes a complete competing EIGHT-principle constitution, is on `upstream/main`,
and `seed.md:31` copies it into every new project. B3 — see the measured residue below;
`scripts/goal_loop.py:1360` — the driver implementing builder≠checker — still cites #4 while its
command was fixed to #3. **FIXED 2026-08-17** (driver now cites #3; its `KNOWN_STALE_CITATIONS`
entry retired).

**⮕ RESIDUE DISCLOSURE — RE-MEASURED 2026-08-18 after the B2 deletion.** The 2026-08-17
version of this table was stale *in its own commit*: it counted `FRAMEWORK.md`, the file the
same change deletes. Caught by the review panel (advisory A2), not by me. Live numbers:

| channel | count |
|---|---|
| wrong-but-in-range citations remaining | **12** across 12 files |
| propagate via `/apply-framework` (`FRAMEWORK_PATHS`) | 9 |
| already published on `upstream/main` | 8 |
| **union — travels on at least one channel** | **10** |
| travels on neither | 2 (`docs/education/CONTRACTS.md`, `docs/education/gates.yaml`) |

Superseded figures, kept so a stale citation can be re-pointed: 2026-08-17 said 13 / 9 / 9 /
union 11 / 2, and the handoff before it said "10 propagate". Each was measured at the time and
each went stale within a day. A further 2 hits in `docs/FRAMEWORK_SPECIFICATION.md` are declared
detector false positives and must NOT be reworded to appease the keyword heuristic.

**⮕ REVIEW OUTCOME — `REV-20260818-004500` (3-specialist ensemble panel, high risk).**
Verdict **approve-with-changes**. THREE BLOCKING, all fixed before commit, two of them defects
in `ADR-0036` itself. What the panel confirmed sound: no content lost from the deleted file,
zero live dangling references, `/seed` verification executed and correct, exemption surface
genuinely shrank (`out_of_range` now 0), no threshold lowered, coverage figures reproduce
exactly, mutations RED-then-clean-restore.

**META-FINDING — carry this forward:** *the author reproduced the exact defect class the author
had just finished cataloguing, twice, in the artifacts written to fix it* — a false
`FRAMEWORK_PATHS` claim in the ADR (after having read the correct list earlier the same
session), and three dangling pointers mandated by the same `/seed` step that forbids dangling
pointers. Fluency with a failure mode is not immunity to it.

**⮕ OPEN ADVISORIES (not closed by this change):**
- **H2 — DERIVED-PROJECT PUSH-BLOCKER.** `PHILOSOPHY.md` is **not** in `FRAMEWORK_PATHS`, so
  `/apply-framework` can never deliver it; 8 citations in files that DO propagate point at its
  *Growth has a brake* section. Distinct from the public-repo channel and still unresolved.
- **PROMOTION REQUIREMENT (from the corrected ADR).** Public `CLAUDE.md` carries **nine**
  principles, public `PHILOSOPHY.md` says "eight", and **ADR-0031 was never promoted** (newest
  public ADR is 0028). Promoting the `FRAMEWORK.md` deletion ALONE would leave the public
  template strictly worse. The promotion must carry `CLAUDE.md` + `PHILOSOPHY.md` + ADRs
  0029–0036.
- **DERIVED CONSTITUTIONS MEASURED 2026-08-18** — `agentic_journal` **9**, `VerificationPortal`
  **10**, template **7**. Every prior artifact said "eight"; nobody had counted, and the two
  inlined constitutions did not drift to the same place. Strongest evidence for the deferred
  generated-block alternative (ADR-0036 Alternatives).
- **H1** — the rewritten separation guard goes vacuous on an empty register; behavioural
  replacement is ~3 lines.
- **H3 / generated block** — deferred, not rejected (developer scoped this change to blockers).
- **A1** — `PHILOSOPHY.md`'s new attribution names `ANALYSIS-20260219-043657`, never committed.
- **A3** — register reason-line cites L576/L1262/L1332; actual **581/1267/1337**.
- **A5** — `/seed`'s verbatim check is a line-count regex; measured to over-count on real
  derived `CLAUDE.md` files (30 vs 7), so it is weaker than the panel described.
- **A6** — education-gate clearance records only an agent session id.
- **A7, A8, A9** — see `docs/reviews/REV-20260818-004500.md`.

**⮕ DEVELOPER DECISIONS (2026-08-16/17):**
- **Derived-project exposure → FOLD INTO THE PROPAGATION EFFORT, do not touch now.** Measured
  read-only: **agentic_journal and VerificationPortal BOTH already carry the retired EIGHT-principle
  constitution AND the hard-gate education model.** Not a PR risk — present state. No writes made.
- **`FRAMEWORK.md` → he asked for a recommendation; criterion "evolve elegantly without confusion."
  MY RECOMMENDATION ON RECORD: DELETE it and rewire `/seed`.** Warrant: superseding leaves the most
  authoritative filename in the repo containing only a pointer; fixing in place keeps the
  constitution in two files, which is exactly what let them drift for 4 months undetected. End
  state: `CLAUDE.md` = the constitution, `PHILOSOPHY.md` = the philosophy (its §76 "Relationship to
  the seven principles" is already current). **The real cost, named: `seed.md:93` DELEGATES
  ("References FRAMEWORK.md for universal principles"), so deleting without rewiring leaves seeded
  projects with NO constitution** — the rewire is that `/seed`'s generated CLAUDE.md inherits the
  seven inline. Needs an ADR (Principle #4: retirement recorded with a reference) and a
  **`/plan` + Steward gate** — NOT a tail-end edit. **Not yet decided by him.**
- **B1 is NOT a decision** — Principle #5 and ADR-0035 are both already ratified by him and his
  verbatim steer is "I don't want to make it onerous and hard-gating." The skill is a surface where
  that decision never landed. Applying it is bookkeeping; only "does the normative review-gate source
  need a Steward gate" is a real question.

**⛔ B4 — FOUND AFTER THE REVIEW (2026-08-17), BLOCKS THE PUSH: the reconciliation created
DANGLING REFERENCES on the public template.** `framework-lineage.yaml` pins `PHILOSOPHY.md` as
*"Private fork mission statement — not applicable to public template"*, and the public copy is
stale — **88 lines, "Relationship to the EIGHT principles", NO `Growth has a brake` section**
(local: 110 lines, seven principles, section present). Every retired-#8 citation this change
re-pointed targets `PHILOSOPHY.md § Growth has a brake`: `apply-framework.md` ×2,
`change_package.py` ×2, `dashboard.py` ×3, `STEWARD_ARCHITECTURE.md`, and the spec's renumbering
map + pattern table. **All CORE files that promote; the target does not reach the public repo.**
Same defect class this effort keeps finding — a pointer asserting something exists where it does
not — introduced by the fix for that class. The panel missed it because none of the three was
asked about promotion mechanics.

**⮕ B4 ROOT CAUSE (measured 2026-08-17): the pin is a WHOLE-FILE lock applied to fix a TWO-LINE
divergence.** The two files are structurally identical — same title, sections and order. Only two
differences exist: the principles section (seven + `Growth has a brake` vs eight), and **two
sentences** of private-fork positioning in "Who we are" (*"a private exploration space forked
from…"* / *"We do not own the public repo. We are its first follower and gatekeeper"*). So
`PHILOSOPHY.md` **IS propagated — it is on the public repo. It is not SYNCED.** The pin froze the
whole file to protect 2 lines, and 4 months of universal philosophy updates never reached the
public template. The pin's reason is accurate about 2 lines and wrong about the other 108.

**✅ DEVELOPER ACCEPTED THIS RECOMMENDATION 2026-08-17 ("ok, I accept your recommendation").** That
is Principle #6 approval of the DIRECTION; the Steward gate still runs FIRST (lineage change) and
`/review` after, because the recommendation he accepted explicitly included both. NOT STARTED — the
hard context checkpoint had fired; nothing was edited. Execution order for next session is in the
handoff.

**RECOMMENDATION (ACCEPTED): move the two private-fork sentences out (fork-positioning is project
state, not philosophy — `CLAUDE.md` or `BUILD_STATUS.md`), then RETIRE THE PIN.** `PHILOSOPHY.md`
becomes ordinary CORE that syncs both directions. **This resolves B4 and B2 together: B4 evaporates
(the citations resolve on the public tree), and B2's delete-`FRAMEWORK.md` recommendation is
RESTORED** — end state `CLAUDE.md` = constitution, `PHILOSOPHY.md` = philosophy, both public, both
synced. **Cost:** retiring a pinned trait is a lineage change = **Steward gate + ADR**. **Rejected:**
hand-editing the 2 sentences out at each promotion — works once, forgotten by the third time.

**⏳ Flagged, not changed:** `scripts/distribute/repo_safety_check.py:400`
`build_assent_stub(template_version: str = "3.5.0")` is now stale — but it has **no production
caller** (grep: tests only), so the default is dormant. Changing a signature nothing exercises
was out of scope; fold it into `/ship` or the propagation prerequisites.
3. **⛔ THE TWO DEEPER BURDEN-CUT SLICES ARE DROPPED AS SCOPED** — reverses the 2026-08-14
   queue decision on evidence that landed after it. Warrant: slice E's dedup recovered **306
   gross words** while the mandated safety work cost **~1,092** → net **+786**; dedup does not
   pay for itself at this granularity (R8 tally). **The one piece that survives** is the
   walkthrough-only-default policy line, to be folded into a much smaller change rather than
   carried by the tutor-loop dedup slice. Narrative relocation: dropped.

## Previous Session (2026-08-12 -> 08-15, autonomous->interactive — SLICE E BUILT+COMMITTED; PRESCRIPTIVENESS ASSESSED; **PUBLIC REPO RECONCILED**)

**✅ RECONCILIATION WITH THE PUBLIC REPO — DONE. This was a hidden blocker, not a chore.**
Measured at the start of the push planning: local `main` was 30 ahead of `upstream/main`
**but `upstream/main` was 21 AHEAD of local main**, on a merge-base of `af3fd10` (2026-06-22).
Promoting on that base is the exact failure that got ADR-0031 retired. Two merges, both local,
nothing pushed:
- `ee59c90` — `upstream/main` -> `main`. Five conflicts. `scripts/stop_hook.py` and
  `tests/test_stop_hook.py` were **add/add**: BOTH repos implemented ADR-0023 independently,
  ours a strict superset (same hook + the SPEC-20260716-093231 telemetry kick). Only 5
  upstream lines dropped, all superseded equivalents. `tests/test_quality_gate.py` upstream
  side was literally EMPTY. `docs/FRAMEWORK_SPECIFICATION.md` was the only judgment call and
  **NEITHER side was right** — resolved by MEASURING (upstream correct on 25 commands and
  8 hooks/13 files; ours correct on the gate's substance; both numbers stale — measured 8
  checks). Conflicts resolved hunk-by-hunk, never `checkout --ours`, so auto-merged upstream
  content survived.
- `989b854` — reconciled `main` -> the feature branch. Overlap was only 3 files.
  `.claude/settings.json` resolved **by the developer** (protected file, ADR-0018): upstream's
  block structure incl. the `"matcher": ""` our side lacked, his own `timeout: 680`. Verified
  JSON-parses, Stop wired, SessionStart matcher preserved.

**Result: `upstream/main ahead of feature` = 0, `ahead of main` = 0. Merge-base is now
`e4c8d73` (2026-07-11), not June. Honest two-dot promotion size: 203 files, +54,366/-993.**

**⚠ THE MERGE SURFACED REAL DEBT and a guard caught it:** upstream's docs cite the OLD
nine-principle numbering. `TestCitationNumbering` went red on 4 citations — fixed to the seven
(#7->#6 for the human gate; #4->#3 x3 for "generator is never the sole evaluator"). **This is
a first LOCAL instalment of the nine-principle reconciliation the four derived projects still
owe before the renumbered layer can propagate.** Also learned: anchoring a citation needs the
LITERAL character — the HTML entity `&ne;` does not bind, the scanner reads source text.

**⚠ SEPARATE FINDING — prose/config disagreement, NOT caused by the merge:**
`ALLOW_AUTO_LAUNCH_SESSION` is absent from `.claude/settings.json` on HEAD, `main` AND
`upstream/main`. It exists only on the unmerged branch `feat/pricing-discover-propose-approve`
(`dbd3c56`, 2026-06-10). CLAUDE.md records the opt-in as **CONSENTED 2026-06-07** with "the
durable signal lives in the settings.json env block" — so the consent is recorded in prose
while the config that honours it has never reached a mainline branch, and auto-launch has been
inert the whole time. Same shape as this effort's recurring finding. **Raise at /retro.**

**✅ PRESCRIPTIVENESS ASSESSMENT (`docs/research/prescriptiveness-assessment-2026-08-15.md`,
commit `15e4f4d`).** The developer's original thesis — "too prescriptive for Opus 5 / Fable" —
had never been tested; the <4% figure measured VOLUME, a different property. Measured:
prescriptiveness is **5.5x denser in the dispatching commands than in the agent charters**
(2.38 vs 0.43 absolute modals per 1k words; **14 of 24 commands** carry a CRITICAL BEHAVIORAL
RULES block, **0 of 12 agents** do). Four file-count ceremony ladders with four disagreeing
thresholds (3/2/5/3). **v4 decision C6 — "match ceremony to stakes", commands available not
mandatory — was already made and then LOST** when ADR-0032 retired the reconciliation over its
merge base; the ladder is live by accident. Report names what must NOT be cut (plurality
floor, seven principles, the two non-declinable classes, every "Measured ..." sentence) and
states its own limit: counted markers, not measured harm.

## Previous Session block (same effort, 2026-08-12 -> 08-14)

**✅ SLICE E BUILT + PANEL-REVIEWED + REVISED. NOT COMMITTED.** Build discussion
`DISC-20260815-060545-build-single-source-pnt-surface` (sealed, 10 events, 2 path-not-taken
records both MECHANICALLY-CLEAR). Panel of 3 blind critics, none shown the build reasoning:
architecture **REVISE 0.82** / independent-perspective **REVISE 0.84** / qa
**APPROVE_WITH_ADVISORIES 0.90**. All blocking findings fixed in a revision pass; full suite
**2944 passed / 3 skipped / exit 0**, quality gate **8/8 exit 0**.

**⚠ ADVISORY 4 (burden) — PARTIALLY MITIGATED: −0 of 11,716 words recovered across 1 Phase B
slice. The chain GREW +786 (20,510 → 21,296).** R8 cumulative tally starts here and must be
carried forward by every later burden slice. Honest breakdown: the dedup itself recovered
**306 gross words**, but R2 (the mandated Advisory-3 reversal, unconditional) cost ~744, and the
panel-driven safety fix below cost a further ~348. **This slice made the burden metric worse.**
It is recorded as a PARTIAL MITIGATION with a negative number rather than as "Advisory 4:
handled" — which is precisely what R8 exists to prevent. The drift fix and Advisory 3 closure,
which were the unconditional half, both landed.

**⚠ THE PANEL CAUGHT A SAFETY GAP INSIDE THE SAFETY FIX — the most important result of the slice.**
`git add --intent-to-add --all` does not only register untracked paths: it promotes a
worktree DELETION of a tracked file to a **staged deletion**, which a `??`-scoped reset cannot
reach. Reproduced independently on a throwaway repo: after `-N` the index carried
`0	1	sibling.txt`, the shipped `??`-scoped reversal left it there, and a plain `git commit -m`
— **no `-a` involved** — committed the unrelated deletion. The retained measured sentence
"*after it, `git diff --cached --numstat` is EMPTY and `git commit -m` refuses*" is FALSE in that
state, and the slice had just re-scoped it to its only surviving copy. Both fences now capture
` D` paths as well as `??`, reverse both, and end with a `git diff --cached --numstat` verify
step; the EMPTY claim is qualified to the tree it was measured in. **Guarded by a new additive
class `TestTheIntentToAddIsReversed` (3 regression tests × 2 files)** — before it,
`git grep "git reset" -- tests/` returned NOTHING, so the entire Advisory-3 closure was
unpinned while the pointer prose around it was pinned.

**Other panel fixes:** the new test's `subsection()` helper was fence-blind (a `#` bash comment
at column 0 read as a heading) and returned **194 chars of a multi-hundred-line section** — now
fence-aware, returns 7,541; `POINTER_FLOOR` was 3 against an actual 4 (a reviewer deleted R3's
whole cross-file pointer and the suite stayed green) — now 4 plus a named per-requirement pin;
**R4 was self-refuting** — it restated `MECHANICALLY-CLEAR may never be promoted to VERIFIED`
verbatim while claiming it was "stated once", taking the count 1→2 — now back to 1 and guarded
by `test_the_stable_phrase_is_stated_once_not_restated_beside_its_pointer`; content anchors now
pin that a pointer's TARGET CONTENT survives, not merely its heading.

**⏳ OPEN ADVISORY carried (not built, out of R2's literal scope):** `review.md` Step 10
obligation 1 mandates re-running the checker — including its `git add --intent-to-add --all` —
at the education gate, the point **closest to the commit**, and specifies no reversal there.
R2 scoped itself to "both `git add --intent-to-add --all` lines" and there are exactly two in
fences; this third site is a re-run instruction. Raise at `/retro` or scope a follow-up.


> Branch `feat/framework-v4-instruments-first`, 23 ahead of main. **Nothing pushed, merged, or
> propagated. Nothing committed yet this session** (uncommitted: SPEC-20260812 spec, two ADR
> status stamps, gates.yaml add+clear, BUILD_STATUS, gate-log lines — ride on slice E's commit).

**✅ BURDEN MEASURED + SLICE E SPEC'D + PANEL-REVIEWED + DEVELOPER-APPROVED.** Chain 20,510w
(+133%); per-run metric review.md 8,937w (+91%). SPEC-20260812-122753 `approved` ("Proceed as
scoped", in-conversation 2026-08-14). Panel: arch REVISE 0.85 / qa REVISE 0.88 (CRITICAL:
test_paths_not_taken.py pins missing from draft) / independent 0.82; all blockers fixed rev 2.
DISC-20260812-192946 sealed (9 events, 4 PNT records). Build NOT started.

**✅ DEVELOPER SESSION-QUEUE DECISIONS (AskUserQuestion, 2026-08-14):** BOTH deeper burden cuts
queued as future gated slices (tutor-loop dedup; narrative relocation); teach-first on ADRs;
extras = /retro + ADR-0033 decisions + propagation prerequisites. **Education-debt backlog (7
old gates) explicitly NOT queued.**

**✅ ADR-0035 EDUCATION GATE: TAUGHT AND CLEARED; ADR-0034 + ADR-0035 ACCEPTED (Principle #6,
"Approve both", 2026-08-14).** Walkthrough sealed `DISC-20260815-014203-walkthrough-i-clear-it-
adr-0035` (Step 2a checker re-run reproduced exit 1; both CONTRADICTED reader-verified FALSE —
specimens 3+4). Checkpoints: #2 demonstrated first ask; #3 after one failure-mode-first re-teach;
#1 unanswered (became the steer). Quiz SKIPPED at his election (recorded depth agreement). Gate
`EDU-20260814-adr-0035-i-clear-it` registered + CLEARED — I ran the clear on his explicit
written order ("Run ... for me"); his instruction is the authorizing act, verbatim in transcript.

**⚠ DEVELOPER STEER (load-bearing, captured turn 4 + memory `feedback_education_gate_lightweight`):**
"too much process around the education gate ... 'clear it' / 'yes, everywhere' meant LESS
burdensome, not more ... might want to clear without the quiz." Agreed response: agent-side
machinery ≠ his burden; his clear is sovereign; **walkthrough-only clearing becomes the
recognized default for ordinary changes (quiz on request / two ratified classes) — goes into
the tutor-loop dedup slice spec, pending his approval. Check every future education-surface
slice against this steer FIRST.**

**✅ ADR-0033 ROUND-5 DECISIONS ANSWERED (developer, in-conversation 2026-08-14):**
`handoff_artifact_write` term stays **MAX** (worst-case reserve; a handoff that doesn't fit is
a broken thread); BUILD_STATUS cap-3 stays **ADVISORY** (existing tripwire test suffices; no
auto-trimmer). Both confirm shipped behavior — no code change; record the pair in ADR-0033's
round-5 note when a slice next touches it.

**⏳ NEXT IN ORDER:** (2) ~~/build_module slice E~~ **DONE 2026-08-15, panel-reviewed + revised,
AWAITING COMMIT** (uncommitted riders ride with it: ADR-0034/0035 status stamps, gates.yaml,
SPEC, BUILD_STATUS, metrics);
(3) /retro (formally owed — 4 false-refutation specimens; also first-ever retro; ADD the
slice-E items: the R8 negative tally, the `-N` deletion hazard as a fifth "mechanism claiming
more than it verified" specimen, and the Step 10 third-`-N`-site advisory); (4)
propagation prerequisites (tests/ into FRAMEWORK_PATHS + nine-principle reconciliation prep;
NO propagation); (5) /plan the two deeper-cut slices incl. the walkthrough-only-default policy.

## Previous Session (2026-08-09, autonomous — WAVE 3 VERIFIED INDEPENDENTLY + REV + COMMITTED PER SLICE)

> Branch `feat/framework-v4-instruments-first`. **Nothing pushed, merged, or propagated.**
> Fresh context (took part in neither the builds, the panel, the fixes, nor their orchestration).

**✅ INDEPENDENT VERIFICATION (Principle #3 closure of the panel-fixer round) — all four PASS,
each with a command and exit code, recorded in `docs/reviews/REV-20260809-222916.md`:**
(a) ADR-0033 `-` lines all stale figures with `(SUPERSEDED)` markers or sentences reproduced in
their round-5 replacements; no argument/objection/concession removed. (b) `git diff --
tests/test_context_sensor.py` EMPTY (0 bytes); only modified test file is purely additive.
(c) The seam critic's defeats re-run at byte level against live `walkthrough.md` — two rewordings
+ struck sentence in **bold** and *italics*, ALL FOUR RED (pytest exit 1 each), file restored by
reverse-edit, sha256 byte-identical, guard green after. (d) Measurement-thinner veto does NOT
fire: round-5 re-measurements are denser; review.md's "zero hits" → 11 hits independently
reproduced (8 walkthrough + 3 quiz, exit 0). Suite re-measured: **597 passed, 1 skipped, exit 0**
— identical to stop time.

**✅ REV-20260809-222916 WRITTEN** — 4-reviewer panel carried (seam-critic REVISE, qa
APPROVE_WITH_ADVISORIES, architecture REVISE, independent-perspective REVISE), 6 open advisories
carried (tutor asymmetry HIGH parked with developer; tests/ not in FRAMEWORK_PATHS HIGH;
intent-to-add reversal HIGH; burden +115% MEDIUM; zero-work path MEDIUM; sensing-without-acting
MEDIUM), plus a FRESH `Paths Not Taken — Verification Handoff` block: checker re-run on the whole
Wave 3 diff, exit 2 COVERAGE GAP, 7 records (5 MECHANICALLY-CLEAR / 2 CONTRADICTED-IN-PROSE,
0 hard refutations), 13 files unspoken-for (expected: only slice C wrote records). Step 10
vocabulary copy re-verified CLOSED (now pinned); /quiz Step 2a fallback re-verified PARTIAL
(instruction-level filter, mechanically still unscoped).

**✅ QUALITY GATE 8/8 PASS (exit 0), then WAVE 3 COMMITTED in slice order** (each commit through
the full pre-commit gate): ADR-0033 round 5 + config → slice C (paths not taken + ADR-0034 +
sealed DISC) → slice A (tutor + seam + SKILL) → slice B (backlog surfacing + registry header
preservation) → REV + housekeeping. `.claude/settings.json` deliberately excluded (developer's
parked Stop-hook decision).

**✅ EDUCATION GATE COMPLETE — awaiting the developer's own clear.** `/walkthrough` sealed
(`DISC-20260810-173821`) + `/quiz` sealed (`DISC-20260810-181205`): 9/9 concepts demonstrated
(8 first ask, 1 after a concrete-trace re-teach of PHANTOM semantics), 13 per-attempt rows in
`education_results` under session `EDU-20260810-wave3-sliced`, verbatim answers all in Layer 1.
Gate `EDU-20260810-wave3-sliced` registered OPEN; under "I clear it" only the developer runs the
clear (command handed to him in-session).
**✅ TUTOR-ASYMMETRY ADVISORY RESOLVED (developer, Q9): WATCH with conditions, do not build now**
("empty governance" risk). Conditions captured as a decision event in the sealed quiz discussion:
per-attempt verbatim capture continues with fidelity; the question MUST travel with any
propagation to derived projects; named signal = every gate reading demonstrated-first-ask in
/retro. The "I clear it" BUILD (item 1) is unchanged by this — it proceeds.
**⚠ TWO checker-contract false-refutation specimens now on record** (ADR-0034's own
loosen-the-checker trigger names two as the threshold): the docstring CONTRADICTED case (in
ADR-0034) and slice D record 5's PHANTOM on a truthful no-change record. Raise at /retro: records
about decisions NOT to change a file need a Files-convention or status arm the coverage contract
currently lacks.

**✅ THE "I CLEAR IT" BUILD IS DONE — built, twice-blind-reviewed, Steward-gated, committed.**
ADR-0035 (proposed — Principle #6 developer approval PENDING, asked). No agent surface instructs
running `clear` (relation guard, mutation-proven incl. two critic-authored escapes); ingest
writes additive `clear_eligible` marker (status stays open; validator rejects it on cleared
gates; library-only, not CLI-exposed); backlog separates "paid, awaiting YOUR clear" from unpaid;
`list --eligible` re-prints the paste; CONTRACTS.md v1.1 formal revision + §4 wire-compatible
tier (consumer-visible vocabulary moves need a named carrier); `/retro` wires the Q9 zero-miss
signal (live: 8/10 newest sessions zero-miss); cross-project FRAMEWORK_CHANGELOG board revived
with the notification + Q9 rider. REV-20260811-154157 (approve-with-changes — floored by checker
exit 1 that is TWO FALSE REFUTATIONS of truthful records, specimens 3+4).
**⚠ /retro ITEM, now FORMALLY OWED (threshold was 2, we have 4): loosen the checker's
false-refutation arms** — docstring-body prose read as code (COMMENT_PREFIXES prefix test, needs
ast/tokenize), PHANTOM on no-change records, falsifier collisions across sibling records.
**⏳ OWED: the education gate on THIS slice** (non-declinable) — under its own rule: taught, then
the developer clears.

**✅ PHASE B SLICE D COMMITTED (`e618021`)** — the effort's first deletion, blind-reviewed:
69 lines shipped (ordering-mandate sentence ×10; all 10 Persona Bias blocks, zero couplings
verified per file; `/distribute` retired with its registry entry, ratchet mutation-proven
RED→GREEN). **The critic REVERSED the grill-yourself deletion pre-commit**: its 0/4-installs
warrant was confounded (created 2026-07-02, last propagation 2026-06-14 — the zero was
calendar-guaranteed), no instrument observes skill invocation, and the tree's own disposition
says human-facing/RESTORE. Reversal recorded append-only in DISC-20260810-054940 (6 records).
REV-20260810-064900. The consent invariant ("never set by the propagation command") now lives
natively in `/apply-framework` Rule 3 (critic F4).

## Retention

Older sessions are trimmed to the documented cap of **3** `## Previous Session` blocks.
Trimmed 2026-08-16: the 2026-08-08/09 block (Wave 3 built + blind-reviewed + Steward-gated — fully
recorded in ADR-0034, REV-20260809-222916, REV-20260810-064900 and their sealed discussions) and
the 2026-08-06/07 block (V4 reconciliation P2.5 AC7 dispositions + the R-B3 REVISE — fully recorded
in `docs/sprints/PROPOSAL-20260806-ac7-dispositions.md`, `docs/reviews/REV-20260807-063650.md`, and
ADR-0031/ADR-0032). Note the tripwire was GREEN at trim time — this trim honoured the **count**
cap, not a size threshold. Trimmed 2026-08-12: the 2026-08-05 block (V4 reconciliation P0-P2 + Steward gates 1-3 — fully recorded in SPEC-20260805-210524 rev 4, ADR-0031, REV-20260805-213438, and their sealed discussions). Earlier trim 2026-08-09 (second trim, same day): the 2026-07-16/17 -> 08-05 block (Waves 1+2 built/reviewed/merged -- fully recorded in PR #12/#13, REV-20260717-221500, f5e98da). Earlier trim: the 2026-07-16/17 (Wave 2 `/plan`), 2026-06-28→07-02 (goal-loop
hardening ADR-0028 + 3c suchness) and 2026-06-27 (backflow Thread B) blocks. Nothing is lost —
those sessions are in git history, their ADRs, and their REV reports; this file is
session-scoped working state, not a record.

**Why the cap is load-bearing and not housekeeping:** `BUILD_STATUS.md` is a *measured term* in
ADR-0033's handoff-cost derivation (`build_status_read`), and
`tests/test_context_sensor.py::TestNoQualityCliffClaimSurvives::test_the_config_derivation_executes_to_the_live_caps`
fires when the live subtotal reaches the stated HANDOFF total. It DID fire on 2026-08-09 when
this session's entry was added (subtotal 21,616 against a stated 20,568). Trimming to the cap is
the intended remedy; raising the RESERVE is a separate decision that requires re-checking the
headroom of all four profiles.
