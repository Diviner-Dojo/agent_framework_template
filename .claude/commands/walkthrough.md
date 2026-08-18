---
description: "Teach a change to the developer — decision landscape, invariants, diagnostics — with checkpoints, not a wall of text. Education gate step 1."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task"]
argument-hint: "[file or directory to walk through]"
---

# Guided Walkthrough (Education Gate Step 1)

Delegate to the educator agent to produce a guided reading path — then **teach it**.

A walkthrough is not a document handed over. It is delivered in layers, each ending in a
checkpoint question, and a shaky checkpoint is re-explained from a different angle before
moving on. The same loop `/quiz` runs, at lower intensity: this step is where the
developer's actual starting point gets discovered, so `/quiz` does not waste its first
three questions finding it.

> **What this step owes the developer: the decisions, the alternatives that lost and why,
> and what breaks if the invariants are violated. Not a narration of the code.**

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: The educator's walkthrough output, **every checkpoint answer**,
   any re-explanation, and **the Step 6 handoff record** MUST be written via
   `scripts/write_event.py` before the discussion closes. No walkthrough exists unless
   captured, and a handoff only spoken aloud is not captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed.
3. **ALWAYS close the discussion**: Every walkthrough MUST end with `scripts/close_discussion.py`, even if abandoned.
4. **NEVER deliver it as one block.** Steps 4-5 are the mechanism. Pasting the whole
   walkthrough and asking "any questions?" is the failure this command was rebuilt to
   prevent — it produces agreement, not understanding.

## Pre-Flight Checks

Before starting the walkthrough, verify the target file(s) exist and prerequisites are available:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('.claude/agents/educator.md').exists():
    errors.append('Missing educator agent definition: .claude/agents/educator.md')
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the target file or directory specified by the user does not exist, tell the developer and ask for the correct path.

## Workflow

### Step 1: Create Discussion

```
python scripts/create_discussion.py "walkthrough-<slug>" --risk low --mode ensemble
```

Store the returned discussion ID.

### Step 2: Gather the decision record — before reading any code

The walkthrough's primary source is the reasoning, not the diff. Collect, in this order:

1. The ADR(s) in `docs/adr/` governing the change — and specifically the **alternatives
   they record as considered and declined**.
2. The originating discussion in `discussions/` — what was actually argued.
3. The **record of the paths not taken**, taken through Step 2a below — not from the
   builder's own note. A self-reported "alternatives considered" is written by the party
   it flatters; Step 2a is where it arrives checked, or is honestly declared absent.
4. `memory/bugs/regression-ledger.md` rows touching the affected files.

**Where you find no decision record, say so and hedge the rationale out loud** — "this
LOOKS LIKE it exists to…", never "this exists because…". A confident invented rationale is
worse than an admitted gap, because he cannot tell the two apart.

### Step 2a: Take the verification handoff — the alternatives are Layer 1, not an appendix

The recorded paths not taken are **the trade-off content of this walkthrough**. They belong
in Layer 1 of the Three-Layer Knowledge Model (Decision Landscape, ~50% of the Step 3
dispatch), not bolted on afterwards: "what it builds and what the trade-offs were" is the
whole ask this gate answers, and a `## Path Not Taken` record is where the trade-offs are
written down.

They do not arrive on the builder's word. `/review` Step 6.4 checks each record against the
diff that shipped and Step 7 writes the result into the review report under one fixed
heading, `## Paths Not Taken — Verification Handoff`. List **every** report carrying it,
newest first — the newest is not automatically yours:

```bash
python -c "
import pathlib
HEADING = '## Paths Not Taken — Verification Handoff'
folder = pathlib.Path('docs/reviews')
reports = sorted(folder.glob('REV-*.md')) if folder.is_dir() else []
carriers = []
for report in reversed(reports):
    text = report.read_text(encoding='utf-8', errors='replace')
    if HEADING in text:
        carriers.append((report, text))
if not carriers:
    print('NO HANDOFF: no docs/reviews/REV-*.md carries the section.')
else:
    print('HANDOFF:', len(carriers), 'report(s) carry the section, newest first.')
    print('The newest is NOT automatically this change; match reviewed_files yourself.')
    for report, text in carriers[:5]:
        front = text.split('---')[1] if text.startswith('---') else ''
        scope, grab = [], False
        for ln in front.splitlines():
            if ln.startswith('reviewed_files'):
                grab = True
            elif grab and not (ln.startswith(' ') or ln.startswith('-')):
                grab = False
            if grab:
                scope.append(ln)
        print()
        print('--- REPORT:', report)
        print('\n'.join(scope) if scope else 'reviewed_files: (absent from frontmatter)')
        print(text[text.index(HEADING):])
"
```

Then confirm **which** of the reports it printed is the one for **this** change — the
`reviewed_files` block printed above each handoff must cover the files you were asked to
walk through. A report about some other change is not a handoff for this one, however
recent: skip it and read the next. If none of them covers your files, there is no handoff
for this change — treat it as absent (below). Scanning only the newest carrier is the
failure this loop exists to prevent, and the deferred-gate case makes it the normal one,
not the exotic one: `/walkthrough` routinely runs days after the `/review` that produced
its handoff, by which time newer reports for unrelated changes carry the same heading.

**Work its obligations, and read them from the source.** `/review` Step 10, subsection *The
briefing agent's verification obligation (contract)*, in `.claude/commands/review.md`, is
authoritative for what must happen before any recorded claim is taught. Open that file and
work the numbered list as written there — including re-running
`scripts/verify_paths_not_taken.py` rather than trusting the exit code copied into the
report, and emitting the reader's per-claim verdict. Do **not** restate that list here or
from memory: a second copy drifts from the contract it claims to implement, and a drifted
copy still reads like compliance. You are the briefing agent that contract names.

Two vocabularies meet in that block and must not be collapsed. The verifier tags each claim
with a **per-record status** — `MECHANICALLY-CLEAR` when it could not refute it, or
`CONTRADICTED` / `PHANTOM` / `UNFALSIFIABLE` / `CONTRADICTED-IN-PROSE` when it could — and
those are claims about whether a *string* was present. Your verdict is the reader's:
`VERIFIED`, `REFUTED`, `UNVERIFIABLE`. `MECHANICALLY-CLEAR` may never be taught as
`VERIFIED` by copying it across; a record is only `MECHANICALLY-CLEAR` because a string
search found nothing, and a fabricated alternative passes that exactly as a true one does.
Take each record's **status** from the run, never from this file. The vocabulary is named
here only so you recognise it; its authority is `RECORD_STATUSES` in
`scripts/verify_paths_not_taken.py`, and `tests/test_education_gate.py` fails if this
paragraph and that tuple stop naming the same set.

Capture what the obligations produced, before teaching from any of it:

```
python scripts/write_event.py "<discussion_id>" "educator" "decision" "Verification handoff: <report path|absent, with which arm>. Re-ran the checker: <verdict + exit code|not possible, why>. Per-claim reader verdicts: <claim -> VERIFIED|REFUTED|UNVERIFIABLE, with the evidence line>." --tags "walkthrough,education,path-not-taken-verification"
```

#### A REFUTED claim — impossible to miss, and impossible to be trapped by

A claim the diff denies is not teaching material about the design. It is teaching material
about the gap, and the gap is more instructive than either side of it. **Every refuting
per-record status, and your own `REFUTED` verdict, gets the two rules below** — what differs
is the sentence you say, because a record can be refuted in four different ways:

| Per-record status | What the checker found | What you say |
|---|---|---|
| `CONTRADICTED` | the diff does the thing the record says was rejected | the record, then the line that does it |
| `PHANTOM` | the record's subject is nowhere in the diff | that the alternative was recorded against code that never shipped, so the trade-off it claims was never made |
| `UNFALSIFIABLE` | the record is phrased so that nothing could refute it | that it is unfalsifiable and therefore teaches nothing — a straw-man or an invented alternative lands here, and is exactly why this status exists |
| `CONTRADICTED-IN-PROSE` | only the surrounding prose contradicts it (an advisory kind — the checker still exits 0) | the same gap, said as advisory rather than hard |

Your own third verdict has a treatment too, and it is the one most easily lost.
`UNVERIFIABLE` — you could not settle the claim either way, from the diff, the ADRs or a
re-run of the checker — is neither a quiet promotion to `VERIFIED` nor a silent drop. Say
it out loud: *"the record claims X; I could not check it against what shipped, so treat it
as unconfirmed."* An unchecked claim taught as a checked one is the same fabrication risk
`PHANTOM` and `UNFALSIFIABLE` exist to catch, arriving through the reader instead of the
checker. It carries the two rules below as well: surfaced, and blocking nothing.

Two rules, and they do not pull against each other:

- **Never taught as fact.** Surface it first — before Layer 1, not buried inside it — and
  state it plainly: *"before anything else: the build recorded that it rejected X; the code
  does X, and here is the line."* Then teach what the diff actually does.
- **Never blocks, delays, or withholds this walkthrough, and never keeps the developer from
  closing the gate.** Principle #5 makes the education gate offered, not withheld, and a
  refuted path-not-taken record is not one of the two classes where skip is unavailable.
  Rewriting the record is owed work, tracked through the finding you capture as the contract
  specifies — never by holding a human's briefing hostage to it.

Which two classes those are, why a refuted record is neither, and the developer's verbatim
steer behind the rule are stated once, in `.claude/commands/review.md`, section
`The briefing agent's verification obligation (contract)`. So is the `write_event` call
that captures the finding, with the severity marker it must carry. Capture it as that
contract specifies; do not re-derive either from a copy here, for the same reason Step 2a
gives above — a second copy drifts from the contract it claims to implement.

#### When there is no handoff — one honest sentence, then carry on

Five situations are all the same situation: no `/review` has run for this change; every
report predates the mechanism and has no such section; the locator printed carriers but none
of their `reviewed_files` covers the files you were asked to walk through;
`verifier_exit_code` reads `NOT RUN`; or `records_checked` is 0. Each gets the same
sentence, said out loud before Layer 1 —

> No verified paths-not-taken record exists for this change; the trade-offs below are read
> from the diff and the ADRs instead.

— and then the walkthrough runs anyway, on the ADRs, the discussion and the diff gathered in
Step 2, with every rationale hedged as Step 2 requires. Three things must not happen: an
error that halts the walkthrough over a file that was never promised to exist, a silent skip
that leaves him believing he was taught verified alternatives when he was taught inferred
ones, and any suggestion that a missing handoff withholds the gate. `verifier_exit_code: 3`
differs in one respect only — the checker could not read its own evidence, so say *that*
instead, and never report it as a clean run.

An absent handoff is **not** a step failure under CRITICAL BEHAVIORAL RULE 2. Nothing
errored; there was simply nothing to consume, and the snippet above exits 0 saying so.
Rule 2 fires when a script or dispatch actually fails.

### Step 3: Read and Dispatch

1. Read the specified file(s) or directory
2. Dispatch to the educator agent:

```
Task(subagent_type="educator", prompt="Generate a guided walkthrough for the following change, using the Three-Layer Knowledge Model from your charter: decision landscape (~50%), invariants and failure modes (~35%), diagnostic knowledge (~15%).\n\nDeliver it as THREE separately-presentable segments, one per layer, each ending with ONE checkpoint question that requires the developer to use the idea rather than agree with it. For each checkpoint, state the concept a miss would trace to and two entry points to re-explain from.\n\nDo NOT narrate code line by line. Name every alternative that was considered and declined, and why. Where no ADR or discussion records a rationale, hedge it explicitly ('this LOOKS LIKE it exists to...') rather than asserting it. Ground any fragility claim in a signal actually present in the source.\n\nVerified paths not taken (Step 2a — these are Layer 1's trade-off material; the slot is required and 'no verified paths-not-taken record exists for this change' is a legitimate value that means you looked):\n- Handoff report: <docs/reviews/REV-... path|none, with which absent arm>\n- Claims the reader marked VERIFIED, each with its evidence line: <list|none>\n- Claims REFUTED — per-record status CONTRADICTED, PHANTOM, UNFALSIFIABLE or CONTRADICTED-IN-PROSE, or the reader's own REFUTED verdict: <list|none>. Teach NO refuted claim as fact — state the record, state what the code does, name the line. Surface these before Layer 1; they do not block or delay anything.\n- Claims the reader marked UNVERIFIABLE, i.e. could not be settled either way: <list|none>. Teach each as unconfirmed and say so; never promote one to VERIFIED and never drop one silently.\n\nDecision record found:\n<ADRs, discussion, regression-ledger rows — or an explicit statement that none exists>\n\nCode:\n<code content>")
```

### Step 4: Capture

Record the educator's walkthrough output:
```
python scripts/write_event.py "<discussion_id>" "educator" "proposal" "<walkthrough content>" --confidence <score> --tags "walkthrough,education"
```

### Step 5: Teach it — one layer at a time

**If Step 2a produced a REFUTED claim, or produced no handoff at all, say so before the
first layer** — the refutation in the words Step 2a specifies, or the one absent-handoff
sentence. Neither is a reason to stop, shorten, or postpone what follows; both are the
first thing he hears so nothing later rests on a claim he was never told was broken.

Present **one layer**, then ask its checkpoint question and wait. Do not present the next
layer until this one has landed.

Capture each exchange in the turn shape `docs/education/CONTRACTS.md` §1.2 locks for
education transcripts, so this step and `/quiz` produce homogeneous Layer 1 records:

```
python scripts/write_event.py "<discussion_id>" "tutor" "question" "<checkpoint question>" --tags "walkthrough,education,checkpoint"
python scripts/write_event.py "<discussion_id>" "learner" "evidence" "<the developer's answer, verbatim>" --tags "walkthrough,education,learner-answer"
```

On a shaky or recited answer, **re-explain from a different entry point** — consequence-first,
analogy from a domain he already owns, counterfactual, concrete trace of one real value,
the losing alternative's point of view, failure-mode-first, scale/limit (educator charter
§2.2) — and ask again. **A re-explanation that reuses the same frame with different words
is not a re-explanation.** Capture it:

```
python scripts/write_event.py "<discussion_id>" "tutor" "critique" "checkpoint miss on <concept>; re-explaining from entry point <name>" --tags "walkthrough,education,reteach"
```

He may ask to skip ahead, go deeper, or stop. Honour it immediately — this step is
offered, not imposed. Record what was skipped so `/quiz` knows it is untested ground.

### Step 6: Write the handoff to Layer 1, THEN close

The handoff in Step 7 is spoken into a conversation that may not outlive it — `/quiz` can
run days later in a fresh context. Step 5's `reteach` events carry only one of the three
items (a concept and a spent entry point); the `checkpoint` and `learner-answer` events
carry none of them, and `/quiz` Step 2a does not grep those tags. So write all three here,
while the discussion is still open:

```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "Walkthrough handoff. Demonstrated in his own words (do NOT re-ask): <list|none>. Entry points already spent, per concept (do NOT re-use): <concept -> entry points|none>. Layers skipped, i.e. untested ground to cover first: <list|none>. Rationale hedged where the decision record was thin: <list|none>." --confidence 0.9 --tags "walkthrough,education,reteach-log"
```

The `reteach-log` tag is load-bearing, not decorative: `/quiz` Step 2a greps exactly
`{'reteach', 'reteach-log'}`, so an event tagged anything else is invisible to the intake
however complete its contents.

Only then close — `close_discussion.py` seals and checksums the record, so nothing can be
added afterwards:

```
python scripts/close_discussion.py "<discussion_id>"
```

### Step 7: Hand off to `/quiz` with what you learned

Do not simply suggest `/quiz`. Hand it the session state, so the tutoring loop starts
where this one ended rather than from zero. **`/quiz` Step 2a is the intake for exactly
these three items** — it takes them before it generates a single question, and its Step 2b
dispatch prompt has a required slot for each. Emit all three, using `none` where there is
nothing, so the slots can be filled without inference:

1. Which concepts he **already explained in his own words** here — `/quiz` will not re-ask
   these.
2. Which concepts needed re-explaining, and **which entry points are already spent** on
   each — `/quiz` must pick unspent ones. Name them as they are spelled in educator charter
   §2.2, because that is what Step 2a matches against.
3. Which layers he skipped — untested ground `/quiz` covers first — and where the decision
   record was thin enough that the rationale had to be hedged.

If the conversation ends before `/quiz` runs, this handoff is not lost — but only because
Step 6 wrote all three items to Layer 1 under the `reteach-log` tag that `/quiz` Step 2a
greps. Speaking them here is the fast path; Step 6 is the durable one. If Step 6 was
skipped, the next session recovers only the entry points spent on misses and will re-ask
concepts he has already demonstrated.

Then offer `/quiz`, and accept "not now" without pressing. A deferred gate is recorded in
`docs/education/gates.yaml` via `scripts/education/gate_registry.py add`, not lost. When a
later `/quiz` closes it, the gate is not retired by the agent: `/quiz` Step 5 presents the
evidence and the exact `gate_registry.py clear` command to the developer, and the
developer runs it himself — clearing is his explicit action, never the tutor's
("I clear it", ADR-0035).
