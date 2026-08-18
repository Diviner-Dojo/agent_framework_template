---
discussion_id: DISC-20260809-121029-paths-not-taken-steward-revise-closure
started: 2026-08-09T12:12:11.758888+00:00
ended: 2026-08-09T12:14:54.434162+00:00
agents: [slice-c-builder]
total_turns: 6
---

# Discussion: DISC-20260809-121029-paths-not-taken-steward-revise-closure

## Turn 1 — slice-c-builder (decision)
*2026-08-09T12:12:11.758888+00:00 | confidence: 0.7*
*tags: path-not-taken, adr-0034, steward-condition-4*

Design-time alternatives for the paths-not-taken mechanism, transcribed into Layer 1 as the
provenance ADR-0034 shipped without. These four were weighed when the mechanism was designed and
are argued at length in ADR-0034's "Alternatives Considered"; recording them here is what the
Steward's Condition 4 asked for, and it is also the mechanism's first real exercise.

## Path Not Taken
- **Decision**: where a path-not-taken record is stored
- **Chosen**: existing Layer 1 discussion events, tagged path-not-taken and read back BY TAG
- **Rejected**: a new paths-not-taken/ ledger with its own writer, schema and directory
- **Why rejected**: it would have added four obligations at once (a writer, an immutability
  guarantee, gate integration, a propagation path into derived projects) plus a fifth source of
  truth to reconcile against Layer 1. ADR-0026 already carries the lesson from loops/.state that a
  second store of the same facts degrades into a distrusted cache. HONEST NOTE ON THIS FALSIFIER:
  it is medium strength, not strong. A ledger design would almost certainly need a directory
  constant, but the exact spelling is my reconstruction of a design that was never written, which
  is the "precise but wrong falsifier" class the checker cannot tell from a correct one.
- **Files**: scripts/verify_paths_not_taken.py
- **Falsifier**: PATHS_NOT_TAKEN_DIR

---

## Turn 2 — slice-c-builder (decision)
*2026-08-09T12:12:42.459606+00:00 | confidence: 0.55*
*tags: path-not-taken, adr-0034, steward-condition-4*

## Path Not Taken
- **Decision**: whether the verification half is a script or an instruction
- **Chosen**: a script (scripts/verify_paths_not_taken.py) whose verdict is deterministic and
  re-runnable by anyone, invoked from /review Step 6.4
- **Rejected**: prose alone -- "the briefing agent checks the claims against the diff"
- **Why rejected**: that is capture-by-diligence, and a skipped instruction leaves no trace, so
  "the check ran and passed" and "the check never ran" produce identical artifacts. HONEST NOTE ON
  THIS FALSIFIER: it is WEAK, and weak for a structural reason worth stating rather than hiding.
  The rejected option is an ABSENCE -- prose-alone ships by the script NOT existing -- and an
  absence has no literal that "would appear in the added lines". The best available literal is the
  sentence the prose-only design would have carried, which is why the record names it.
- **Files**: .claude/commands/review.md, docs/adr/ADR-0034-paths-not-taken-builders-record-briefing-agent-verifies.md
- **Falsifier**: the briefing agent checks the claims against the diff

---

## Turn 3 — slice-c-builder (decision)
*2026-08-09T12:13:15.594221+00:00 | confidence: 0.75*
*tags: path-not-taken, adr-0034, steward-condition-4*

## Path Not Taken
- **Decision**: which existing artifact carries a build's rejected alternatives
- **Chosen**: a per-decision record written into Layer 1 at the moment of the choice
- **Rejected**: the ADR "## Alternatives Considered" section, which already exists and is already
  required by scripts/quality_gate.py::check_adrs
- **Why rejected**: three reasons, each disqualifying. Wrong altitude -- the motivating specimen
  (three failed rounds patching a command-text guard) is an implementation choice that would never
  have earned an ADR, and the implementation level is where most decisions live. Wrong time -- an
  ADR is written after the work, so its alternatives section is a reconstruction by definition,
  which is the exact defect the timing rule targets. Unverifiable -- an ADR's alternatives are
  prose with no field a checker can act on. Self-application, stated because it cuts against me:
  ADR-0034's own Alternatives section is unverified prose, and this record is the argument for why
  that is not good enough for build-time decisions.
- **Files**: .claude/commands/build_module.md
- **Falsifier**: ## Alternatives Considered

---

## Turn 4 — slice-c-builder (decision)
*2026-08-09T12:13:38.135701+00:00 | confidence: 0.8*
*tags: path-not-taken, adr-0034, steward-condition-4*

## Path Not Taken
- **Decision**: how the briefing agent establishes whether a recorded claim is true
- **Chosen**: re-run the checker against the diff, and do not trust the report's copied exit code
- **Rejected**: the briefing agent asks the builder whether the record is accurate
- **Why rejected**: it is self-report verifying self-report. The builder that wrote the tidy story
  answers the question about the tidy story from the same context that produced it, so it fails
  Principle #3 as an INFORMATION property -- there is no separate context involved at all. Worse,
  it produces a transcript of a verification, which reads as more convincing than no verification
  while carrying no more evidence. This is the highest-value rejection in the set because it is the
  design the mechanism most easily decays into.
- **Files**: .claude/commands/review.md
- **Falsifier**: ask the builder

---

## Turn 5 — slice-c-builder (decision)
*2026-08-09T12:14:06.866559+00:00 | confidence: 0.85*
*tags: path-not-taken, steward-condition-1, steward-condition-2*

Closure-round decisions, weighed while making the four Steward-mandated changes.

## Path Not Taken
- **Decision**: what the exit-0 verdict prints, after the Steward's probe showed a wholly
  fabricated record printing "PATHS_NOT_TAKEN: VERIFIED", exit 0
- **Chosen**: rename the verdict to MECHANICALLY-CLEAR -- the word /review Step 7 already used --
  and add a CLEAR_CAVEAT string carried in the text render, the --json payload, and stderr
- **Rejected**: keep printing VERIFIED and attach the caveat sentence beside it
- **Why rejected**: the Steward's finding was precisely that the WORD is what propagates, into
  verifier_exit_code, into the review report, and into what a developer is taught. A correct
  disclaimer under an incorrect headline is the same defect one layer out -- REV-20260807-063650's
  "performed honesty that displaces the real check". Also rejected: inventing a fresh word such as
  NO-REFUTATION, because /review already carried MECHANICALLY-CLEAR and a second vocabulary for one
  fact is the drift this suite exists to catch.
- **Files**: scripts/verify_paths_not_taken.py
- **Falsifier**: EXIT_OK: "VERIFIED"

## Path Not Taken
- **Decision**: how a record that draws several problem kinds is reported per-record
- **Chosen**: worst-first, via an explicit STATUS_PRECEDENCE tuple
- **Rejected**: report whichever kind appears first in the record's problems list
- **Why rejected**: that order is an artefact of the code path, not a severity judgement. A record
  CONTRADICTED in one of its files and only CONTRADICTED-IN-PROSE in another would be reported as
  the advisory, which launders a refutation into a footnote at exactly the handoff the briefing
  agent reads. Guarded by test_a_blocking_kind_outranks_an_advisory_one_on_the_same_record, which
  was mutation-tested: reversing the precedence turns it RED.
- **Files**: scripts/verify_paths_not_taken.py
- **Falsifier**: problems[0].kind

---

## Turn 6 — slice-c-builder (decision)
*2026-08-09T12:14:54.434162+00:00 | confidence: 0.8*
*tags: path-not-taken, steward-condition-3*

## Path Not Taken
- **Decision**: what to do with the education-gate completion block the Steward flagged
- **Chosen**: remove it, and replace it with a surface-first-and-capture obligation, stating in
  place why Principle #5's two non-declinable classes are the whole list
- **Rejected**: leave the block in the command and take it to the developer as an open question
- **Why rejected**: leaving it in place makes "the gate stays" the default while the question is
  open, and the developer's steer on this exact surface was verbatim "I don't want to make it
  onerous and hard-gating". Removal is one edit to reverse; a hard gate on a HUMAN that shipped is
  not. The distinction the Steward drew is preserved deliberately: the BUILD-side friction
  (/build_module behavioural rule 9, Step 3a.5) falls on the agent and was left untouched.
- **Files**: .claude/commands/review.md
- **Falsifier**: cannot be recorded complete

---
