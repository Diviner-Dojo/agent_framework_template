---
adr_id: ADR-0034
title: "Paths not taken: builders record the alternative at the moment of the choice, and a script — not a briefing agent's diligence — is what can refute the record"
status: accepted  # Principle #6 developer approval given in-conversation 2026-08-14 ("Approve both"), after the Wave 3 education gate (9/9) and the 2026-08-14 ADR-0035 walkthrough covering this ADR's checker failure modes
date: 2026-08-09
decision_makers: [developer, slice-c-builder]
decision_provenance: >-
  The DESIGN is the developer's and is quoted verbatim in Context ("Builders record;
  briefing agent verifies", docs/handoff/HANDOFF-20260808-instruments-first-wave2.md
  lines 145-149). The MECHANISM — the six-field record, the Falsifier field, the four
  exit codes, the Layer 1 store, the coverage proxy and its thresholds — is the
  builder's elaboration of that steer and has NOT been individually approved. Where
  this document says "the developer chose", it means the first; everywhere else,
  read "the builder chose, extrapolating from the steer".
discussion_id: DISC-20260809-121029-paths-not-taken-steward-revise-closure
discussion_provenance: >-
  PRESENT as of 2026-08-09, and it was ABSENT when this ADR was first written —
  the Steward's Condition 4. PHILOSOPHY.md's suchness invariant says a derived
  artifact may not sever its own provenance, and a governance mechanism about
  capturing reasoning had shipped without capturing its own. The discussion above
  holds 7 `path-not-taken` records: the four design-time alternatives argued in
  "Alternatives Considered" below (the `paths-not-taken/` ledger, prose-alone, the
  ADR alternatives section, "the briefing agent asks the builder"), plus the three
  weighed while closing the Steward's conditions. Measured — `--list-sources` now
  reports `1 discussion(s) hold path-not-taken records ... (7 record(s))`, exit 0,
  where it previously printed "no discussion ... holds a single record". The
  records were written through `scripts/write_event.py` and none was tuned to make
  the run pass; see "The first real exercise" below for the verdict it produced.
steward_gate: >-
  APPROVE, rendered 2026-08-09, after a REVISE on 2026-08-09 carrying four
  conditions — all four re-verified against the tree by the Steward itself, not
  accepted from the builder's account. Each is recorded in "Status of this
  decision" below. The re-gate re-ran the fabricated-record probe with a FRESH
  falsifier (`_PROBE_CACHE_SINGLETON_QZX`, deliberately not the token the module
  docstring now documents): the fabrication still passes — it always will — but
  the headline now prints `MECHANICALLY-CLEAR` with the caveat naming that exact
  case, in text mode, in `--json`, and on stderr. On Condition 4 the Steward
  checked whether the self-exercise had been TUNED to pass and found it had not:
  the run returned `COVERAGE GAP`, exit 2, 5 MECHANICALLY-CLEAR / 2
  CONTRADICTED-IN-PROSE / 11 UNRECORDED on an independently constructed diff.
  TWO CONDITIONS RIDE ON THE APPROVAL, both corrections of record rather than
  design changes, and both applied in this same round: (1) the script's own
  module docstring claimed Principle #2 while the ADR retracted it — fixed, with
  the zero-invocation grep quoted in place and pinned by
  `tests/test_paths_not_taken.py::TestTheScriptDoesNotClaimAutomaticEnforcement`;
  (2) this field, which previously said the Steward had not re-gated.
  STILL OUTSTANDING and NOT implied by this field: developer approval under
  Principle #6, and `/review`, which the Steward states plainly it is not — this
  is a high-risk governance surface, so the `selecting-review-gates` floor of at
  least two independent specialists applies.
spec_id:
supersedes:
extends:
scope: framework
risk_level: high
confidence: 0.70
tags: [paths-not-taken, capture, principle-2, principle-3, verification, education-gate, falsifiability, review, build-module, plan, instruments-first]
---

## Context

### What landed, measured

Slice C on `feat/framework-v4-instruments-first` adds one mandatory workflow step to two
commands, one instruction to a third, one enforcement script, and one guard suite.

```
$ git diff --stat -- .claude/commands/plan.md .claude/commands/build_module.md .claude/commands/review.md
 .claude/commands/build_module.md | 141 ++++++++++++++++++-
 .claude/commands/plan.md         |  65 +++++++++
 .claude/commands/review.md       | 284 ++++++++++++++++++++++++++++++++++++++-
 3 files changed, 482 insertions(+), 8 deletions(-)          [exit 0]

$ wc -l scripts/verify_paths_not_taken.py tests/test_paths_not_taken.py
  1217 scripts/verify_paths_not_taken.py
  2275 tests/test_paths_not_taken.py                          [exit 0]
# (1099 / 2127 before the Steward-condition round; re-measured 2026-08-09)

$ git status --porcelain     # both new files are ADDED, not modified
A  scripts/verify_paths_not_taken.py
A  tests/test_paths_not_taken.py                              [exit 0]
```

The surfaces, by name:

| Command | Surface added | Kind |
|---|---|---|
| `/plan` | `## Paths Not Taken` spec section + Step 3.6 (copy each block into Layer 1) + Step 7 item 5 (state the discussion id) | instruction |
| `/build_module` | Behavioural rule 9 + Step 3a.5 (record while deciding) + Step 6.5 (self-check) + Step 8 item 4 | **mandatory step** |
| `/review` | Behavioural rule 6 + Step 6.4 (run the checker) + Step 7 handoff block + Step 9 item 5 + Step 10 briefing-agent contract | **mandatory step** |
| `scripts/verify_paths_not_taken.py` | the checker: four exit codes, five problem kinds | enforcement |
| `tests/test_paths_not_taken.py` | 169 tests | guard |

### The decision as the developer made it

Verbatim, from `docs/handoff/HANDOFF-20260808-instruments-first-wave2.md` lines 145-149
(§ *3b — Paths not taken*):

> Developer chose **"Builders record; briefing agent verifies"**: builders state the alternatives
> they weighed *while deciding*, and the briefing agent checks those claims against the actual diff
> before teaching them — so a tidy-but-false story gets caught. Today's best example only exists
> because it was narrated in passing (three failed rounds patching a command-text guard → change
> the architecture).

That is one sentence with two halves, and the second half is the load-bearing one. It sits inside
the developer's larger steer about the education gate, quoted in the same handoff at lines 96-101:
*"I want the AI to teach me what it builds and what the tradeoffs were (paths not taken)."* The
tradeoffs are the payload; the verification is what makes the payload worth teaching.

### The motivating specimen — ANECDOTE, labelled as one

The best path-not-taken in this repository exists only because someone narrated it in conversation:
**three failed rounds patching a command-text guard, ending in "change the architecture, don't
patch it a fourth time."** Nothing captured it. No spec section, no ADR, no Layer 1 event. It
survived by luck, and the shape of it — three attempts at the wrong level of the problem before
the level itself was questioned — is exactly the reasoning Principle #1 calls the primary artifact.

**This is an anecdote and is not offered as evidence of a rate.** One un-captured decision does not
establish how often decisions go un-captured; nobody has counted, and by construction nobody can
count the ones that were never written down. What it establishes is that the failure mode is real
and that the framework had no mechanism against it. The residue of that episode is visible in the
shipped code — `COMMAND_TEXT_RE` is the first of four taught-good falsifier examples in
`/build_module` Step 3a.5, and it is the fixture literal throughout `tests/test_paths_not_taken.py`
— but the decision itself is nowhere in the record. Its ADR does not exist. That is the gap.

### Why this ADR is owed, and why now

Under CLAUDE.md this is Framework Evolution (agent/command/rule change), and under the
`documenting-decisions` skill a new mandatory workflow step is ADR-worthy on its own. But the
sharper reason is perishability: **the rationale currently lives only inside command prose.** The
argument for why Step 3a.5 fires inside the per-task loop rather than as a closing summary, and why
`Falsifier` is a field at all, is written in `.claude/commands/build_module.md` — a file whose whole
purpose is to be edited. A future editor tightening the command for length has no signal that those
paragraphs are the decision rather than the explanation. A blind critic flagged the absence as a
real gap. `tests/test_paths_not_taken.py` pins the *structure* of that prose against the checker,
but a test cannot hold a rationale; it can only notice when one disappears.

## Decision

### 1. Builders record the alternative at the moment of the choice — never afterwards

`/build_module` Step 3a.5 fires the moment one implementable option is picked over another, before
Step 3b's checkpoint evaluation, inside the per-task loop. `/plan` writes its blocks in the same
pass that discards each option. Both commands state the reason in the same words: an "alternatives
considered" section written after the work is a **reconstruction**, and the rejected option comes
back through the lens of the one that shipped — tidier, weaker, more obviously wrong than it was.

The timing is not a style preference; it is the mechanism. `tests/test_paths_not_taken.py::
TestTheInstructionLandsAtTheMomentOfDecision` (5 tests) asserts the step's *position* in the file
rather than its wording, so an editor may rewrite the paragraph but cannot relocate it to the end
of the build without going red.

### 2. The record has six fields, and one of them is an invention

```
## Path Not Taken
- **Decision**:     what was being decided, one line
- **Chosen**:       what was actually implemented
- **Rejected**:     the specific other option that was implementable
- **Why rejected**: the reason, at the time
- **Files**:        repo-relative paths the decision lands in
- **Falsifier**:    a literal string that WOULD appear in the added lines if the rejected option had shipped
```

Measured from the module — `python -c "import verify_paths_not_taken as v; print(v.REQUIRED_FIELDS)"`
returns exactly `('decision', 'chosen', 'rejected', 'why rejected', 'files', 'falsifier')`, six
fields, exit 0.

Five of those fields are what any "alternatives considered" section carries. **`Falsifier` is the
one that makes the record checkable by something other than a reader's goodwill.** It converts a
narrative claim into a testable one: if the rejected approach had been built, this token would be
in the added lines; it is not there, so it was not built. The builder is being asked to name, in
advance, the evidence that would prove them a liar.

A corollary the commands state explicitly and this ADR endorses: **if you cannot name a falsifier,
that is information.** The "alternative" may not have been a live option. Say so in `Why rejected`
rather than inventing a token — a fabricated falsifier is worse than an absent record, because it
survives the mechanical check and is then taught to the developer as fact.

### 3. The verification half is a SCRIPT — but a script nothing invokes, and that is NOT Principle #2

Principle #2 says *capture is automatic, enforced by scripts and hooks, not by instruction — a
decision that exists only in a context window did not happen.* An earlier draft of this section
claimed the mechanism satisfies it. **It does not, and the claim is withdrawn.** Measured
2026-08-09:

```
$ grep -c "verify_paths_not_taken" scripts/quality_gate.py     -> 0
$ grep -rc "verify_paths_not_taken" .claude/hooks/             -> 0 hits
$ grep -c "verify_paths_not_taken" .claude/settings.json       -> 0
```

Nothing invokes this script. It runs when an agent reading `/review` Step 6.4 or `/build_module`
Step 6.5 chooses to run it. **A script reached only when an agent remembers to reach it is an
instruction written in Python** — the same capture-by-diligence Principle #2 rejects, wearing a
`.py` extension. What the script genuinely contributes is narrower and still worth having: its
verdict is **deterministic and re-runnable by anyone**, so once it runs, the judgement of whether a
record is refuted stops being the builder's word. That is a Principle #3 contribution (a separate
evaluator), not a Principle #2 one, and the two should not be conflated again.

The Steward did **not** require the hook, and this ADR does not propose it: *"gating a commit on a
first-day instrument is how instruments get disabled in week two."* It is recorded as owed work in
"Alternatives Considered" and in the limitations below, not as done work.

Four exit codes, and the module docstring calls them the contract:

| Exit | Meaning | Consequence in `/review` Step 6.4 |
|---|---|---|
| 0 | **MECHANICALLY-CLEAR** — every record structurally checkable, located, falsifier absent from code. **Not "VERIFIED"; see below** | continue |
| 1 | VERIFICATION FAILED — a `CONTRADICTED`, `PHANTOM`, or `UNFALSIFIABLE` record | verdict floored at `approve-with-changes`; one `critique` finding per failed record; claim quarantined from teaching |
| 2 | COVERAGE GAP — records held up, but high-churn files nobody spoke for | advisory; `UNRECORDED` list handed to the briefing agent |
| 3 | INSTRUMENT FAILURE — evidence unreadable | HALT. Never conflated with 0 |

**Exit 0 is called MECHANICALLY-CLEAR, and it used to be called VERIFIED.** The Steward did not
argue about this; it ran it. It authored one wholly fabricated record — written after the fact,
with a straw-man alternative (a module-level global dict, "rejected" because
`.claude/rules/coding_standards.md` bans global mutable state, which was obvious before any work
began) and a falsifier invented to be absent by construction (`_STATUS_REGISTRY_GLOBAL`) — and
checked it against this script's own 1099-line diff. Reproduced here before changing anything:

```
$ python scripts/verify_paths_not_taken.py --events <fabricated>.jsonl --diff script.diff
PATHS_NOT_TAKEN: VERIFIED -- 1 record(s) checked, 1 of 1 changed file(s) qualified   [exit 0]
```

The design *knew* this — `test_a_precise_but_wrong_falsifier_passes` and
`test_a_semantically_false_record_with_a_clean_falsifier_passes` are executable statements of it,
and the module docstring said exit 0 means "nothing refuted *in code*". **The defence lived in the
prose and was contradicted by the output string.** The word the tool PRINTED was `VERIFIED`, and
that word is what propagates: into `verifier_exit_code`, into the review report, into what a
developer is taught. That reproduces `REV-20260807-063650`'s meta-finding — *"performed honesty
that displaces the real check"* — inside the headline verdict of the mechanism built to prevent it.

`/review` already carried the honest term, `MECHANICALLY-CLEAR`, for the per-record status, and the
script did not know that word (`grep -c` → 0). It is now the exit-0 verdict, exported as
`VERDICT_WORDS`, printed with a `CLEAR_CAVEAT` string in the text render, the `--json` payload and
on stderr. `VERIFIED` remains a live word in exactly one place — the *reader's* per-claim verdict at
`/review` Step 10 obligation 5, awarded only after someone opens the diff and asks whether the code
is the rejected approach under another name. **`MECHANICALLY-CLEAR` may never be promoted to
`VERIFIED` by copying it across**; the two layers are stated as two in the command.

Exit 3 existing as a separate code is the smallest and most important design element here. A
verifier that cannot read its own evidence and reports "clean" is precisely the defect the whole
mechanism exists to prevent, and `TestInstrumentFailureIsNeverSilence` (4 tests) exercises three
shapes of unreadable evidence.

### 4. Why the verification half is load-bearing — the failure mode this repo has already named

A builder's self-reported "alternatives considered" is the *canonical* comfortable fiction: it is
written by the party it flatters, and until now nothing read it back. This repository's own review
record names the exact failure mode. From `docs/adr/ADR-0032-retire-v4-reconciliation-instruments-first.md`
line 110, quoting the meta-finding of `REV-20260807-063650` (`grep -n "performed honesty"` on that
file returns exactly that one line, exit 0):

> **performed honesty that displaces the real check**

The finding as originally written (`discussions/2026-08-07/DISC-20260807-180721-review-rb3-ac7-dispositions-transcribed/transcript.md`
line 346) is sharper still: *"A reader who trusts section 2.1 because it sounds uncomfortable will
not check its baseline — and its baseline was chosen in the direction the answer needed."*

An unverified "paths not taken" section is that failure mode with a dedicated heading. It reads as
candour, it is authored by the party being assessed, and it displaces the check it appears to be.
**A check that cannot fail builds the fiction; it does not catch it.** That is why
`tests/test_paths_not_taken.py` spends 27 tests (`TestTheCheckerFails`) on the arms where the
checker says NO, and states the reason in its own docstring: *"A checker that only has passing tests
is a checker nobody has seen say no."*

### 5. The three cases, and which are actually caught

Three failure cases were named as the target. **The script reaches roughly two and a half.** The
split is stated here at full honesty because upgrading a partial check into a complete one is the
same defect as an unfalsifiable claim about the code.

**Case 1 — a claimed alternative the diff contradicts. PARTIALLY CAUGHT.**
`CONTRADICTED` fires when the record's `Falsifier` string appears in an added **code** line inside
one of the record's own `Files`. `PHANTOM` fires when the record's `Files` name nothing the diff
touched — the location half of the same case, and fully mechanical. What is *not* caught is the
semantic contradiction: `TestTheCheckersHonestLimits::test_a_semantically_false_record_with_a_clean_falsifier_passes`
asserts that a record claiming "we rejected an in-process cache" passes green while the diff adds a
plain dict that is one. No string comparison can see that, and the test exists so that the day
someone claims it can, they must delete an assertion to say so.

Two further reductions on case 1, both real:

- **A precise-but-wrong falsifier passes.** `test_a_precise_but_wrong_falsifier_passes`: a record
  whose falsifier reads `Comand_Text_RE` against a diff adding `COMMAND_TEXT_RE` exits 0. The
  structural check cannot tell a plausible-looking wrong token from a right one.
- **CONTRADICTED is switched off for prose, and in this repo prose is the majority case.**
  Re-measured independently for this ADR (`git log --no-merges --numstat --format=%H`, exit 0,
  file-touches with binary `-`/`-` rows dropped): **143** non-merge commits reachable from HEAD,
  **1509** file-touches, median per-file churn **44**; **891** touches (59.0%) reach the
  `DEFAULT_MIN_CHANGED_LINES` threshold of 20, and of those **577 — 64.8% — carry a prose suffix**
  (`.md`, `.markdown`, `.rst`, `.txt`). Those figures reproduce the script's own docstring numbers
  exactly. Since `is_prose_line()` downgrades a falsifier hit in a prose file (or in a comment) to
  the advisory `CONTRADICTED-IN-PROSE`, **the only check that tests a record's TRUTH is off for
  about two thirds of the file-touches it would otherwise judge, and off entirely on a
  markdown-only governance change.** That trade is deliberate — see Alternatives — but exit 0 on
  such a change means "nothing was structurally broken and nothing was refuted *in code*", never
  "no record was refuted".

**Case 2 — an unfalsifiable claim. CAUGHT, structurally.**
`UNFALSIFIABLE` fires on a missing or blank required field, on a `Files` list with nothing
path-shaped in it, on a falsifier shorter than `MIN_FALSIFIER_LENGTH` (**4**), or on one drawn from
`VAGUE_FALSIFIERS` (**15** entries — `n/a`, `none`, `the alternative`, `a different approach`, `see
above`, …). Values read from the module, exit 0. This catches the record nobody could ever check.
It does not grade prose, and by design it does not try: the docstring says the list is "meant to
catch the shrug, not to grade prose. Anything longer starts refusing honest records."

**Case 3 — a decision in the diff with NO alternative recorded. NOT CAUGHT. A PROXY.**
This is the weakest of the four kinds and the script says so in capital letters. `UNRECORDED` flags
a **file** whose churn reaches the threshold and which no record names, minus `DEFAULT_EXCLUDES`
(`discussions/*`, `docs/reviews/*`, `metrics/*`, `BUILD_STATUS.md`). The checker cannot see
decisions; it sees files.
`TestTheCheckersHonestLimits::test_a_decision_inside_a_small_hunk_is_never_flagged` pins the miss: a
real design choice inside a three-line hunk is invisible. And the converse holds — a 400-line
mechanical rename is flagged though it decided nothing. **Read exit 2 as "these files were never
spoken for", never as "these files contain unrecorded decisions."** The judgement is handed to the
briefing agent (Step 10, obligation 4), which is the only reader that can open the file.

Summary, stated once so it cannot be softened by paraphrase:

| Case | Mechanically caught? |
|---|---|
| 1 — claimed alternative the diff contradicts | **Partially.** Literal falsifier in code lines, plus the location half (`PHANTOM`). Not semantics, not a wrong-but-precise token, not prose files (64.8% of qualifying touches here). |
| 2 — unfalsifiable claim | **Yes**, structurally: missing field, unusable `Files`, falsifier < 4 chars or in the 15-entry vague list. Not "weak but checkable". |
| 3 — decision with no record | **No.** A churn proxy over files, advisory only. |

### 6. Layer 1 is the store — no new ledger, no fourth artifact

The records are written with `scripts/write_event.py` into the existing discussion, tagged
`path-not-taken`, and read back **by tag** rather than by agent or intent — so any workflow can
contribute one without the checker learning about it. `/plan` Step 3.6 copies its spec blocks into
Layer 1 for the same reason: *"The spec's `## Paths Not Taken` blocks live in a document that can be
edited without trace."*

Reuse over invention. The capture stack already exists, already runs on every `/plan`, `/review`
and `/build_module`, is already append-only, and already reaches Layer 2 (`turns.tags`) where the
records are queryable. A new ledger would have needed its own writer, its own immutability story,
its own gate integration and its own propagation path — four new things to keep honest, for a
payload the existing four-layer stack was built to hold.

One measured detail that made this cheap rather than merely tidy: the records use the `decision`
intent, and `decision` is not a finding intent. `scripts/extract_findings.py` line 253 sets
`finding_intents = {"critique", "proposal"}` (exit 0), so a path-not-taken record adds nothing to a
review's finding counts and cannot inflate them. When `/review` Step 6.4 *does* want a failure to
become a finding, it writes a `critique` event with an explicit severity marker — deliberately
using one of the five words `_EXPLICIT_SEVERITY_RE` parses, because `blocking` is not one of them
and falls through to `medium`.

### 7. `--list-sources` — the entry point, added because the mechanism did not have one

The check needs the `/plan` and `/build_module` discussion ids, and nothing in the workflow
guaranteed a reviewer was handed them. The documented fallback (`verifier_exit_code: NOT RUN`) is
frictionless, so **`NOT RUN` would have been the path of least resistance for every build-driven
review, and the check would have become prose while still reading as a mechanism.**
`--list-sources` prints every discussion that actually holds records, newest first, with counts.

It deliberately does **not** auto-select. Verifying an unrelated older discussion against today's
diff would report its truthful records as `PHANTOM` — a blocking verdict against honest work, which
is this instrument's worst possible failure. `TestTheMechanismHasAWorkingEntryPoint` carries 11
tests.

When this ADR was first written, `--list-sources` printed *"no discussion under discussions/ holds a
single 'path-not-taken' record"*, exit 0 — the correct state on the day a mechanism ships, and the
single largest reason `confidence` was 0.64. It no longer does:

```
$ python scripts/verify_paths_not_taken.py --list-sources
1 discussion(s) hold path-not-taken records (newest first):
  2026-08-09  DISC-20260809-121029-paths-not-taken-steward-revise-closure  (7 record(s))
Pass the ids belonging to THIS change with --discussion. ...                  [exit 0]
```

That is still one discussion, written by this slice about itself. It is the signal to keep
watching: if the count is still 1 in a month, no *build* has used the mechanism and it has decayed
into prose.

### 7a. The first real exercise — run on this slice, reported unflattering

The Steward's Condition 4 asked for exactly this and warned against exactly the obvious
temptation: *"do not tune the records until it goes green."* Seven records were written through
`scripts/write_event.py` — the four design alternatives, and three weighed while closing the
Steward's conditions — and the checker was run against this slice's own diff:

```
$ { git diff HEAD -- scripts/verify_paths_not_taken.py tests/test_paths_not_taken.py \
      .claude/commands/review.md .claude/commands/build_module.md ;
    git diff --no-index /dev/null docs/adr/ADR-0034-...md ; } > slice.diff
$ python scripts/verify_paths_not_taken.py \
    --discussion DISC-20260809-121029-paths-not-taken-steward-revise-closure --diff slice.diff

PATHS_NOT_TAKEN: COVERAGE GAP -- 7 record(s) checked, 5 of 5 changed file(s) qualified   [exit 2]
  5 x MECHANICALLY-CLEAR
  2 x CONTRADICTED-IN-PROSE   (advisory)
  1 x UNRECORDED  tests/test_paths_not_taken.py changed 2275 lines and no record names it
```

**Exit 2, not exit 0, and the records were not touched afterwards.** Three things it establishes,
none of which the test suite could:

1. **The `UNRECORDED` flag is correct.** Real test-design decisions were made in
   `tests/test_paths_not_taken.py` this round — scoping the "no `VERIFIED`" assertion to the
   *headline* line rather than the whole render (the caveat legitimately contains the string
   "not VERIFIED", so a blanket search would have forbidden the sentence doing the work), and
   guarding the removed education-gate block by requiring every surviving "recorded complete" to
   sit inside a window naming Principle #5. Neither was recorded. The coverage proxy — the weakest
   of the four checks, an advisory over churn — caught a genuine gap on its first real outing.
2. **No record was added in response.** Writing a path-not-taken record *because a checker asked
   for one* is a reconstruction written through the lens of what shipped, which is the precise
   defect Step 3a.5's timing rule exists to prevent. Closing exit 2 that way would have been
   Condition 1's defect in a new costume. The honest disposition is: the gap is real, it is
   reported, and the next build records at the moment of the choice.
3. **Both `CONTRADICTED-IN-PROSE` advisories are the prose carve-out doing its job, visibly.** The
   record rejecting *prose-alone* names the falsifier `the briefing agent checks the claims against
   the diff`, and that sentence appears in this ADR's own Alternatives section — as a *quotation of
   the rejected option*, not as the option shipping. The record rejecting the education-gate
   completion block names `cannot be recorded complete`, which appears in `/review` as a quotation
   inside the passage that repudiates it. A bare substring test would have blocked both truthful
   records; the advisory kind is why it did not. This is the 64.8% hole and the reason for it, in
   one run.

### 8. The briefing agent verifies — an interface, not an implementation

`/review` Step 7 writes a `## Paths Not Taken — Verification Handoff` block into
`docs/reviews/REV-<ts>.md` with fixed keys (`discussion_ids`, `diff_command`, `verifier_exit_code`,
`records_checked`, `records_refuted`, `files_unspoken_for`, plus verbatim claims and verbatim
problems). Step 10 defines what the briefing agent must do with it, and **defines only the
interface** — what it receives and what it must check — saying nothing about how the education gate
is built, so the contract survives a rebuild of that side (which is in progress in this same wave).

The five obligations, of which the first is the one that matters: **re-run the checker; do not trust
the copied exit code.** The report is a transcript written by the party being checked; the script is
the evidence. `TestTheBriefingAgentContract` carries 7 tests.

### 9. Status of this decision, and the gates it has and has not passed

Stated exactly, because getting this wrong is how an ADR manufactures its own approval:

1. **`status: proposed`.** Not accepted.
2. **The developer chose the DESIGN.** His words are on record, verbatim, quoted in Context —
   "Builders record; briefing agent verifies." That is a real decision by the human, not an
   extrapolation.
3. **The developer has NOT approved the implementation.** The six-field record, the `Falsifier`
   field, the four exit codes, the churn threshold of 20, `DEFAULT_EXCLUDES`, the prose carve-out,
   and the Step 10 contract are the builder's elaboration of the steer. **This ADR does not itself
   constitute developer approval of any of it.** Principle #6 and the Framework Evolution path both
   require a human, and neither is satisfied by a document the agent wrote.
4. **The Steward gate returned REVISE, not APPROVE, and this section previously said PENDING.**
   That is no longer true and the field has been corrected. The Steward gated the mechanism against
   `PHILOSOPHY.md`, did **not** decline it — three of its five weighings cut for approval, including
   "Growth has a brake" (measured: ~483 executable lines, 15 flat functions, stdlib only, no new
   artifact type), Principle #1, and the Prime Objective — and returned four conditions. All four
   were closed in this round:

   | # | Condition | Disposition |
   |---|---|---|
   | 1 | Retire `VERIFIED` as the exit-0 verdict | **Closed.** `MECHANICALLY-CLEAR` + `CLEAR_CAVEAT`; every downstream consumer (script, `/review`, `/build_module`, guards, this ADR) updated; new guards mutation-tested. § 3. |
   | 2 | Emit per-record status, or drop it from the contract | **Closed by emitting.** `verify()` returns `record_status` (one entry per record, five-word vocabulary), rendered in both modes; `TestCommandsAndCheckerAgree` gained 4 tests where it had **zero** coverage of that vocabulary. |
   | 3 | Remove the education-gate completion block, or take it to the developer | **Closed by removal.** It invented a third non-declinable briefing class where Principle #5 names two. The guard that *required* it is inverted. The BUILD-side friction the Steward explicitly excluded (`/build_module` rule 9, Step 3a.5) is untouched. |
   | 4 | Give this ADR its provenance, and exercise the instrument on itself | **Closed.** `discussion_id` is set; 7 real records written; the run reported at § 7a, exit 2, unflattering and untuned. |

   **REVISE closed is not APPROVE granted.** The Steward has not re-gated the result of this round,
   and a later verdict that changes the decision should supersede this ADR rather than rewrite it
   (Principle #4).
5. **The Steward's non-blocking observation is accepted and recorded, not fixed.** Nothing invokes
   the script (0 hits in `scripts/quality_gate.py`, `.claude/hooks/`, `.claude/settings.json`).
   Section 3 no longer claims this satisfies Principle #2; a script an agent must remember to run is
   an instruction written in Python. The Steward explicitly did not require the hook.
6. **`/review` has not run on this slice.** The newest review on disk is `REV-20260808-150325`,
   which covers slices S3/S5b/S5c/S7/S11 and does not mention this work.

## Alternatives Considered

### Prose instruction alone — "the briefing agent checks the claims against the diff"

- **Pros**: zero new code, zero new failure surface, no propagation obligation, no false positives
  by construction. It is also *literally what the developer asked for* — his sentence describes an
  agent checking, not a script.
- **Cons**: it is capture-by-diligence, which Principle #2 exists to reject in exactly these words:
  *"enforced by scripts and hooks, not by instruction."* An instruction that is skipped leaves no
  trace, so "the check ran and passed" and "the check never ran" produce identical artifacts. And
  the artifact under scrutiny is a self-report, so the failure mode is not laziness — it is that a
  well-written false record is *pleasant to read*, and a reader with no independent evidence has
  nothing to push against.
- **Reason rejected**: a check that cannot fail builds the fiction rather than catching it. The
  script's contribution is not that it is smarter than the agent — it is emphatically not; it does
  string matching. Its contribution is that its verdict is **deterministic and re-runnable by
  anyone**, so the judgement of whether a claim is true stops being the builder's word.
- **Partially retained, and honestly so**: Step 10's briefing-agent obligations *are* prose, enforced
  by an agent following instructions. Only obligation 1 is script-enforced. `/review` states the
  split rather than hiding it, and this ADR endorses that framing: the value of the mechanical half
  is that the parts an agent could quietly skip are the parts it cannot quietly get wrong.

### A new artifact type — a `paths-not-taken/` ledger with its own writer and schema

- **Pros**: a single canonical home, greppable by shape, easy to render; no dependence on discussion
  hygiene; no risk of a record being buried in a long transcript.
- **Cons**: four new obligations at once — a writer, an immutability guarantee, gate integration,
  and a propagation path into derived projects — plus a fifth source of truth to reconcile against
  Layer 1 when the two disagree. The framework already carries the lesson that a second store of the
  same facts becomes a distrusted cache (`loops/.state`, ADR-0026).
- **Reason rejected**: reuse over invention. Layer 1 is append-only, already written on every
  workflow, already flows to Layer 2 where `turns.tags` makes the records queryable, and already
  propagates. Reading by **tag** rather than by agent or intent means any future workflow can
  contribute a record without the checker being taught about it.

### Make the ADR "Alternatives Considered" section carry it

- **Pros**: the section already exists, is already required by the quality gate
  (`scripts/quality_gate.py::check_adrs` requires the literal `## Alternatives Considered`
  heading), and is already reviewed. Zero new machinery.
- **Cons**: three that are each disqualifying. **(a) Wrong altitude** — ADRs record architectural
  decisions; the specimen this mechanism exists for ("three failed rounds patching a command-text
  guard") is an implementation-level choice that would never have earned an ADR, and the
  implementation level is where most decisions live. **(b) Wrong time** — an ADR is written after
  the work, which makes its alternatives section a reconstruction by definition; that reconstruction
  is the exact defect Step 3a.5's timing rule targets. **(c) Unverifiable** — an ADR's alternatives
  are prose with no field a checker can act on. Adding a `Falsifier` to every ADR alternative would
  be inventing this mechanism inside a document type that fires too late and too rarely.
- **Reason rejected**: it would put the record where it is safest to write and least possible to
  check. Note the self-application: *this* ADR's own Alternatives section is unverified prose, and
  the argument above is precisely why that is not good enough for build-time decisions.

### "The briefing agent asks the builder" — REJECTED, and the reason generalises

- **Pros**: cheap, conversational, no tooling, and it feels like verification.
- **Cons**: it is self-report verifying self-report. The builder that wrote the tidy story answers
  the question about the tidy story, from the same context that produced it. It fails Principle #3
  as an **information** property — *"a separate context that did not see the reasoning behind the
  code"* — because there is no separate context involved at all. Worse, it produces a *transcript
  of a verification*, which is more convincing than no verification and carries no more evidence.
- **Reason rejected**: this is the highest-value rejection in the set, because it is the design the
  mechanism most easily decays into. Step 10 obligation 1 is written specifically against it —
  *"Re-run the checker. Do not trust the copied exit code"* — and the same instinct is why
  `/build_module` Step 6.5's self-check is explicitly **not the gate**: *"a builder checking its own
  work is the generator evaluating itself."*

### Refuse a falsifier that appears anywhere in the added lines, including comments and markdown

- **Pros**: `CONTRADICTED` would then cover 100% of qualifying file-touches instead of ~35%, and the
  64.8% prose hole measured above would not exist.
- **Cons**: it refutes the commonest honest artifact there is. Writing a comment that explains *why*
  you rejected an approach is practice this framework encourages, and a bare substring test turns
  that comment into a blocking finding against your own truthful record.
- **Reason rejected**: **a false refutation of a truthful record is the outcome that teaches people
  to stop recording**, and a mechanism nobody feeds is worth less than no mechanism. The chosen
  design reports `CONTRADICTED-IN-PROSE` as advisory instead, and hands the judgement to the
  briefing agent. `TestATruthfulRecordIsNotMechanicallyRefuted` — the single largest class in the
  suite at **33 tests** — is entirely about this direction. The cost is a genuine false negative of
  measured size, stated wherever the trade appears rather than left to be discovered.

### Block the commit on exit 1 (wire the checker into the pre-commit hook or the quality gate)

- **Pros**: real teeth. Today, consequences 1-4 in `/review` Step 6.4 are applied by the facilitator
  running the command — nothing in the hook or the gate reads the exit code.
- **Cons**: a hook change is a developer action, and gating a commit on a first-day instrument with
  a known false-positive surface (`PHANTOM` on any diff taken without `git add --intent-to-add`) is
  how the instrument gets disabled in week two.
- **Reason rejected — deferred, not refused.** Recorded as owed work rather than done work.
  `/review` states the limit in its own text: *"Making exit 1 block a commit is a hook change, and a
  hook change is a developer action."*

### Auto-select the discussions in `--list-sources`

- **Pros**: removes the last manual step; the reviewer types one command.
- **Cons**: checking every discussion ever written against today's diff reports old, truthful
  records as `PHANTOM`.
- **Reason rejected**: same principle as the prose carve-out — never block honest work. The listing
  removes the *excuse* that the ids could not be found; it does not remove the reviewer's job of
  knowing which change they are reviewing.

### Exclude `tests/*` from the coverage proxy

- **Pros**: re-measured for this ADR over the last 30 non-merge commits
  (`git log --no-merges --numstat --format=%H -30`, exit 0; **155** touches reach the churn
  threshold), `tests/` is the single largest remaining category — **26** of 155, exactly tied with
  `discussions/` (26), against `docs/reviews/` 13, `docs/adr/` 10, `docs/sprints/` 7 and
  `BUILD_STATUS.md` 5. Excluding it would make exit 2 rarer still.
- **Cons**: "a test file cannot hold a design decision" is false in this repo specifically —
  `tests/test_paths_not_taken.py`'s own header records choosing relation-assertions over
  literal-assertions and keeping two literal exceptions deliberately. That is a path not taken,
  living in `tests/`.
- **Reason rejected**: excluding the tree would tell every builder that test-design choices never
  need recording. For the same reason `docs/` is excluded only at `docs/reviews/` (generated
  output); `docs/adr/` and `docs/sprints/` stay in scope because they are where design decisions are
  supposed to land.

## Consequences

### Positive

- **A build's decision space becomes an artifact rather than a memory.** The specimen in Context
  survived by luck; the next one does not have to.
- **The self-report acquires an adversary.** `CONTRADICTED`, `PHANTOM` and `UNFALSIFIABLE` are three
  ways a builder's own story can be told it is wrong, by something that did not read the story.
- **The evidence is re-runnable by anyone.** The handoff block carries `diff_command` precisely so
  the briefing agent can reproduce the run instead of trusting the number.
- **A vacuous pass is visible.** `verify()` emits `VACUOUS_NOTE` when zero records were checked and
  zero files qualified, and `/review` invokes `--json`, so the note is written into the result
  payload *and* echoed to stderr — because a note only the text renderer prints is absent exactly
  where it was needed. `TestTheAntiVacuityNoteReachesTheModeReviewRuns`, 3 tests.
- **The instrument ships with its proof.** Per `testing_requirements.md` ("ship the proof with the
  capability"), the guards landed in the same change: `python -m pytest tests/test_paths_not_taken.py -q`
  → **169 passed in 8.45s**, exit 0 (163 before the Steward-condition round). Of those, 27 exercise
  the checker saying NO (`TestTheCheckerFails`), 33 the false-positive arms
  (`TestATruthfulRecordIsNotMechanicallyRefuted`), 16 the coverage-proxy tuning, 16 the
  command/checker agreement (11 before; the 5 added are Conditions 1-2), 11 the entry point, 8 the
  briefing contract, and **5 assert gaps on purpose** (`TestTheCheckersHonestLimits`).
- **The honest limits are executable.** Those 5 gap-asserting tests exist so that a later overclaim
  of full coverage must delete an assertion to be made — the overclaim becomes visible in a diff
  rather than buried in a paragraph.

### Negative / limitations (honest)

- **A text-level check proves a mechanism is STATED, never that a model followed it.** Sixteen of the
  169 tests (`TestCommandsAndCheckerAgree`) read command markdown and assert it still says what the
  checker does. That guards drift between two documents. It cannot observe whether any agent
  actually fired Step 3a.5 at the moment of a choice — and Step 3a.5 firing *at that moment* is the
  entire mechanism. The framework has no instrument for this and this ADR does not claim one.
- **The coverage proxy is a heuristic over churn, not semantics.** It counts changed lines per file.
  A decision in a three-line hunk is invisible (pinned by a test); a mechanical rename is flagged
  though it decided nothing. Exit 2 means "these files were never spoken for". The threshold of 20
  is a judgement — evidenced, and re-derived independently for this ADR from
  `git log --no-merges --numstat --format=%H` (exit 0) rather than quoted from the script: median
  per-file churn is **44** over **1509** touches, and a threshold of 20 selects **891/1509 =
  59.0%**, against 5 → **1264/1509 = 83.8%** and 50 → **725/1509 = 48.0%**. Still a judgement, and
  a judgement about *this* corpus. **JUDGMENT: a derived project with a different churn profile
  should re-measure before trusting it.**
- **Nothing verifies that a recorded alternative was genuinely weighed rather than reconstructed
  afterwards.** This is the deepest limitation and no part of the design addresses it. A builder who
  writes all six fields in a closing sweep, inventing a plausible falsifier that happens to be
  absent, passes every mechanical check. `test_a_precise_but_wrong_falsifier_passes` and
  `test_a_semantically_false_record_with_a_clean_falsifier_passes` are the executable statements of
  it. The only defence is Step 10 obligation 3 — *"test whether the rejected option was ever real…
  a straw man passes every mechanical check ever written"* — which is a human/agent judgement, not a
  check.
- **`CONTRADICTED` is off for ~65% of this repo's qualifying file-touches** (577 of 891, measured
  above). On a markdown-only governance change — which is most of what this repo does — it is off
  entirely, and exit 0 means only "nothing structurally broken, nothing refuted *in code*".
- **Nothing invokes the script at all, so this is NOT Principle #2 capture.** Not just "nothing
  enforces the exit code" — nothing *runs* it. Measured 2026-08-09:
  `grep -c "verify_paths_not_taken" scripts/quality_gate.py` → **0**; `.claude/hooks/` → **0 hits**;
  `.claude/settings.json` → **0**. The script executes only when an agent reading `/review`
  Step 6.4 or `/build_module` Step 6.5 chooses to run it, and consequences 1-4 are likewise applied
  by that agent. **A script reached only when an agent remembers to reach it is an instruction
  written in Python.** An earlier draft of section 3 described this as satisfying Principle #2; the
  claim is withdrawn. What it does deliver is a Principle #3 property — a deterministic, re-runnable
  evaluator separate from the builder — which is real but is a different principle and a smaller
  one. Wiring the hook is deferred on the Steward's own reasoning ("gating a commit on a first-day
  instrument is how instruments get disabled in week two"), and is a developer action.
- **The education-gate half is not wired.** `/review` Step 10 defines the briefing agent's contract,
  and as of 2026-08-09 nothing on that side consumes it. Re-run for this ADR:
  `grep -rn "docs/reviews\|Verification Handoff\|path-not-taken\|Paths Not Taken" .claude/commands/walkthrough.md .claude/commands/quiz.md .claude/agents/educator.md scripts/education/`
  returns **zero hits, exit 1**. A *case-insensitive* re-run finds one uncommitted prose mention
  added by the concurrent education-gate slice (`.claude/commands/walkthrough.md:73`, "record of the
  paths not taken"), which is encouraging but is not the handoff block, the heading, or the tag.
  **The loop closes today only because Step 10 makes `/review` state the report path when it
  recommends the gate — a dependency on a human or agent reading a path out of command output.**
  That is owed work, not done work.
- **The guard does not travel with the thing it guards.** Measured at the definition
  (`grep -n "FRAMEWORK_PATHS" scripts/lineage/manifest.py` → line 21, exit 0; the list spans lines
  21-27): `FRAMEWORK_PATHS = ['.claude/', 'scripts/',
  'CLAUDE.md', 'docs/templates/', 'docs/adr/']`, exit 0. So `/apply-framework` propagates the
  command prose *and* `scripts/verify_paths_not_taken.py` into every derived project, but `tests/`
  is not in that set — **a derived project receives the mechanism and not the drift detector.**
  Same standing limitation as `tests/test_command_sql.py`, same two fixes (add the file to
  `FRAMEWORK_PATHS`, or move the assertions into a `scripts/` module), both requiring developer
  sign-off. Read a green run here as evidence about the hub only.
- **The mechanism has now been exercised exactly once, on itself, and never on a real build.**
  `--list-sources` returns **1** discussion (7 records) where it returned zero, and the run is
  reported in full at § 7a: exit 2, one correct `UNRECORDED`, two `CONTRADICTED-IN-PROSE`
  advisories. That is a genuine first outing and it moved `confidence` from 0.64 to 0.70 — no
  further, because a slice checking its own diff is the weakest possible sample: the same context
  wrote the records and the checker, so it cannot show the mechanism working across the context
  boundary it exists to police. **Every claim here about behaviour under a real build still comes
  from tests and from reading the code.**
- **A documented false-positive class was observed firing, on this very change.** Re-running the
  Steward's fabricated-record probe against the *post-fix* diff of
  `scripts/verify_paths_not_taken.py` returned `PATHS_NOT_TAKEN: VERIFICATION FAILED`, exit 1,
  `CONTRADICTED` — because the docstring paragraph that now *documents the probe* adds a line
  containing the probe's falsifier (`_STATUS_REGISTRY_GLOBAL`). The line lives inside a `"""`
  docstring, but it does not itself begin with `"""`, so `is_prose_line` reads it as code and the
  prose carve-out never applies. **A truthful record was refuted by the act of documenting it** —
  precisely the "string matching cannot see scope" limit the module docstring named, now with a
  measurement attached. The root cause is narrow and worth stating: `COMMENT_PREFIXES` is a
  *prefix* test, so it reaches the opening line of a multi-line string and none of the body. A real
  fix needs `ast`/`tokenize`, not a longer prefix tuple, and that is deferred rather than done.
  Against the unmodified pre-fix diff the same probe returns `MECHANICALLY-CLEAR`, exit 0.
- **The exit-0 verdict was wrong for the first day of this mechanism's life, and only an
  adversarial reader caught it.** 163 tests then, 5 of them asserting the honest limits on purpose, a
  module docstring stating the limit correctly — and the headline still printed `VERIFIED` for a
  fabricated record. **JUDGMENT: the guards were pointed at the checker's logic and not at the
  words it emits, and the words are the part that reaches a human.** The four new
  `TestCommandsAndCheckerAgree` tests are the correction; whether that class of defect is now
  covered generally, rather than at this one site, is unproven.
- **A new mandatory step is a new place for the workflow to fail.** `/build_module` behavioural rule
  9 and `/review` behavioural rule 6 are pass/fail; a build that skips Step 3a.5 is a workflow
  failure. Whether the added friction is worth the record is a question only real use answers, and
  `--list-sources` returning nothing for a month is the signal that the answer was no.

### Neutral

- **`NOT RUN` is a legitimate, honest value** for a small change that ran without `/plan` and
  `/build_module` (CLAUDE.md's 1-2 file path). `/review` requires the reason and the
  `--list-sources` count alongside it, which makes the skip falsifiable. But if `NOT RUN` is what
  gets written most weeks, the mechanism has become prose — raise it at `/retro`.
- **`decision`-intent records add nothing to finding counts** (`finding_intents = {"critique",
  "proposal"}`, `scripts/extract_findings.py:253`). Recording more paths does not make a review look
  worse.
- **`discussions/*` is excluded from the coverage proxy to close a self-inflicted loop**: Layer 1
  grows *because* builders write records, so writing more records pushed `events.jsonl` over the
  churn threshold and got it reported unspoken-for. A proxy that penalises the behaviour it exists
  to encourage is inverted, not merely noisy.
- **The `git add --intent-to-add --all` line is mandatory and narrowly scoped.** `git diff` never
  shows untracked files, so without it every record about a NEW file is falsely `PHANTOM`. The
  commands bound the verb explicitly: after it, `git diff --cached --numstat` is empty and
  `git commit -m` refuses — but `git commit -am` *does* commit the file in full, so it must never be
  followed by `commit -a`. `TestTheIntentToAddLineIsBounded`, 3 tests.

## What would change this decision

- **`--list-sources` still returning zero after a month of builds.** Then builders are not
  recording, and the mechanism is prose with a script attached. That is a `/retro` item, and the
  honest response is to remove it rather than leave an inert instrument that reads as a gate.
- **A `PHANTOM` or `CONTRADICTED` verdict against a record that turns out to be true.** The false-
  positive direction is the one that kills adoption. Two false refutations of honest work would
  justify loosening the checker, not the recorders.
- **A real `CONTRADICTED` on a code change.** That would be the first evidence the mechanism catches
  what it was built for, and would raise confidence materially.
- **The education-gate side consuming the handoff block.** Until then the "briefing agent verifies"
  half of the developer's sentence is delivered by hand.
- **A different corpus.** Every threshold here (20 lines, 4 characters, the exclude set) is measured
  against this repo's 143 commits. A derived project should re-measure.

## Linked Records

- **Developer's decision, verbatim** — `docs/handoff/HANDOFF-20260808-instruments-first-wave2.md`
  lines 145-149 (§ *3b — Paths not taken*); the surrounding education-gate steer at lines 96-101.
- **The failure mode this mechanism targets** — `REV-20260807-063650`'s meta-finding, *"performed
  honesty that displaces the real check"*, anchored at `docs/adr/ADR-0032-retire-v4-reconciliation-instruments-first.md`
  line 110 and transcribed in full at
  `discussions/2026-08-07/DISC-20260807-180721-review-rb3-ac7-dispositions-transcribed/transcript.md`
  line 346.
- **Implementation** — `scripts/verify_paths_not_taken.py` (1217 lines; the module docstring is the
  authoritative statement of what it can and cannot decide).
- **Guards** — `tests/test_paths_not_taken.py` (2275 lines, 169 tests). The honest limits are
  `TestTheCheckersHonestLimits`; the false-positive arms are
  `TestATruthfulRecordIsNotMechanicallyRefuted`.
- **Surfaces** — `.claude/commands/plan.md` (§ *Paths Not Taken*, Step 3.6, Step 7),
  `.claude/commands/build_module.md` (rule 9, Step 3a.5, Step 6.5, Step 8),
  `.claude/commands/review.md` (rule 6, Step 6.4, Step 7 handoff, Step 9, Step 10).
- **Principles engaged** — #1 (reasoning is the primary artifact), #2 (capture is automatic,
  enforced by scripts not instruction), #3 (the generator is never the sole evaluator), #6 (curated
  memory needs human approval — why the Steward gate and developer approval are pending, not
  assumed).
- **Related ADRs** — ADR-0032 (instruments-first; source of the meta-finding), ADR-0029 (education
  gates), ADR-0026 (why a second store of the same facts becomes a distrusted cache).
