---
description: "Run an adaptive tutoring session on a change until the developer can explain it in his own words. Education gate step 2."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task", "Write"]
argument-hint: "[file or directory to be tutored on]"
---

# Adaptive Tutoring Session (Education Gate Step 2)

Delegate to the educator agent to run a **tutoring loop** — not to administer a test.

The questionnaire stays: questions are how the gap gets found. What changed is what
happens on a wrong answer. **A miss re-teaches from a different angle and asks again.**

> **Success criterion: the session ends when the developer can explain the change and
> its rejected alternatives in his own words — however many turns that takes. A session
> that ends in a score has failed, even if the score is high.**

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: The educator's question set, **every developer answer**, every
   re-teach, and the facilitator's closing summary MUST be recorded via
   `scripts/write_event.py`. No session exists unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed.
3. **ALWAYS close the discussion**: Every session MUST end with `scripts/close_discussion.py`, even if abandoned.
4. **NEVER move past a miss.** No "let's come back to that", no supplying the answer and
   asking him to confirm it, no silent scoring. Step 4 below is the mechanism; running
   Step 3 and skipping Step 4 is the failure this command was rebuilt to prevent.
5. **NEVER end on a score.** The closing report states what he demonstrated and what is
   still open. It does not rank, grade the person, or praise progress.

## Pre-Flight Checks

Before starting, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('.claude/agents/educator.md').exists():
    errors.append('Missing educator agent definition: .claude/agents/educator.md')
if not pathlib.Path('scripts/record_education.py').exists():
    errors.append('Missing education recording script: scripts/record_education.py')
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
python scripts/create_discussion.py "quiz-<slug>" --risk low --mode ensemble
```

Store the returned discussion ID.

### Step 2: Intake prior session state, then generate the opening question set

#### Step 2a — Take the handoff BEFORE you generate anything

This step is the reader for `/walkthrough` Steps 6-7 (Step 6 writes the durable record,
Step 7 speaks it) and for the educator's `reteach_log` output block. Without it the loop
restarts from zero every session and re-spends entry points that already failed, which is
the waste all of those exist to prevent. Collect four things:

1. **Concepts he already explained in his own words** — do **not** re-ask them. Reuse
   them as the analogy source for a harder concept instead.
2. **Entry points already spent, per concept** — do **not** re-use one. The re-teach
   loop (Step 4) picks an unspent one; it cannot do that without this list.
3. **Layers he skipped in the walkthrough** — untested ground. Cover it first.
4. **The paths-not-taken verification handoff**, which is what "its rejected alternatives"
   in this command's success criterion actually refers to. `/walkthrough` Step 2a locates
   `docs/reviews/REV-*.md`, section `## Paths Not Taken — Verification Handoff`, works
   `/review` Step 10's obligations against it, and captures the reader's per-claim verdicts
   under the `path-not-taken-verification` tag. Take those verdicts. If `/walkthrough` did
   not run, do Step 2a yourself — it is written to be run from either command.

   Three consequences, all non-negotiable. **A refuted record is never the premise of a
   question** — refuted meaning any of the checker's four refuting per-record statuses
   (`CONTRADICTED`, `PHANTOM`, `UNFALSIFIABLE`, or the advisory `CONTRADICTED-IN-PROSE`), or
   any claim the reader marked `REFUTED`. Asking him to explain a rejection the code
   contradicts teaches him a fiction and then scores him on it; asking him to explain a
   `PHANTOM` or `UNFALSIFIABLE` record asks him to reason about an alternative that was
   never really weighed. Ask about the gap instead — what the record said, what the code
   does. **A claim the reader marked `UNVERIFIABLE` is not question material either**: it
   was not settled, so a question built on it grades him on an unchecked premise. Name it
   as unconfirmed if it comes up, and take question material from the reader-`VERIFIED`
   claims. And **a REFUTED claim leaves this
   session completable**: it never withholds, postpones or fails it. Principle #5 makes the
   education gate offered, not withheld, and names exactly two non-declinable classes
   (framework governance/safety changes, and distribution to derived projects); a refuted
   record is neither, and the developer's steer here was verbatim *"I don't want to make it
   onerous and hard-gating."* If **no** handoff exists —
   no `/review` yet, an older report without the section, `NOT RUN`, or zero records — say
   the one sentence out loud (*"no verified paths-not-taken record exists for this change;
   the alternatives below are read from the diff and the ADRs instead"*) and continue with
   hedged rationale. Never crash on the missing file, and never let its absence pass in
   silence.

If `/walkthrough` just ran, it hands these over directly; take them as given. If it did
not — a fresh context, a resumed gate, a session started straight at `/quiz` — read the
durable record instead of guessing. `/walkthrough` Step 6 and Step 5 below both write the
reteach log into Layer 1, so it is greppable:

```bash
python -c "
import json, pathlib
SHOW = 10
found = []
for path in sorted(pathlib.Path('discussions').glob('*/*/events.jsonl')):
    for line in path.read_text(encoding='utf-8', errors='replace').splitlines():
        if not line.strip():
            continue
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if {'reteach', 'reteach-log'} & set(ev.get('tags') or []):
            when = (ev.get('timestamp') or ev.get('created_at') or '')[:10]
            found.append((when, ev.get('discussion_id') or path.parent.name, ev.get('content') or ''))
found.sort(key=lambda row: row[0], reverse=True)
for when, discussion, content in found[:SHOW]:
    print(when or '(undated)', discussion, '|', content[:300])
print('reteach events found:', len(found), '- shown:', min(len(found), SHOW), 'newest first')
print('SCOPE LIMIT: this log is NOT filtered by change, file or session.')
print('Take a line as prior state ONLY after checking its discussion id is this change.')
"
```

**State which of the two you got, out loud, before dispatching.** `0` events means "no
prior state recorded" — it does not mean "no read path", and it must not be reported as
having checked nothing. Nothing seeds this log, so it stays empty until a `/walkthrough`
or `/quiz` session in this project has written to it.

**The read path is unscoped, and that is a limit you must apply, not one the snippet
applies for you.** It greps `discussions/` whole; a `reteach-log` line from an unrelated
change months ago is indistinguishable, to the grep, from this change's handoff. Two events
carry no change identity at all, so nothing mechanical can separate them. Before any line
becomes "concepts already demonstrated — DO NOT re-ask", check its discussion id and date
against the change you were asked to tutor, and drop the ones that do not match. Feeding an
unrelated session's state into the Step 2b slots suppresses questions he has never been
asked — the same waste the handoff exists to remove, running in reverse.

Two event schemas exist in Layer 1: older events carry `created_at` and no `timestamp`, and
both schemas are live in trees this command runs in. The snippet reads either, and skips a
line it cannot parse rather than dying on it. Do not "simplify" it back to `ev['timestamp']`
— that raises `KeyError` on the older schema and, under CRITICAL BEHAVIORAL RULE 2, halts
the whole gate over a read path that had nothing to say in the first place. Count the older
schema in your own tree before assuming it is absent:
`grep -L timestamp discussions/*/*/events.jsonl`.

#### Step 2b — Dispatch

Dispatch to the educator agent. The educator's own charter (`.claude/agents/educator.md`
§2) is authoritative for the loop, the entry points, the rubric and the grounding rules —
this prompt sets the assignment, it does not restate the pedagogy. Pass the Step 2a
findings through; the slots are required, and `none` is a legitimate value that means you
looked:

```
Task(subagent_type="educator", prompt="Run the tutoring loop from your charter section 2 on the following change. Produce the OPENING question set only — the loop will add more as it runs.\n\nRequirements:\n- 6-10 opening questions\n- Bloom's level mix: 30% Understand/Apply, 70% Analyze/Evaluate/Create (overall mix; order them so difficulty ramps within the session — that ramp is not a different ratio)\n- At least 1 debug scenario question, grounded in a REAL fragility signal present in the source (a guard, a TODO, retry logic, a try/except, a regression-ledger row). Never invent a bug.\n- At least 1 change-impact question\n- Where no ADR or discussion records the rationale, hedge it out loud ('this LOOKS LIKE it exists to...'), never assert it\n- Tag each question with Bloom's level and question type\n- For each question give the rubric: what a reasoning-in-his-own-words answer contains, and which CONCEPT a miss would trace back to\n- For each question, list two entry points you would re-teach from if it misses\n\nPrior session state (from /walkthrough Step 7, or from the Layer 1 reteach log; write 'none' where there is none — never omit a slot):\n- Concepts already demonstrated in his own words — DO NOT re-ask these: <list|none>\n- Entry points already spent, per concept — DO NOT re-use these: <list|none>\n- Walkthrough layers skipped, i.e. untested ground to cover first: <list|none>\n- Paths-not-taken verification handoff (docs/reviews/REV-... section 'Paths Not Taken — Verification Handoff', or 'no verified paths-not-taken record exists for this change'): <report path|none>. Reader-VERIFIED claims, usable as question material: <list|none>. REFUTED claims (per-record status CONTRADICTED, PHANTOM, UNFALSIFIABLE or CONTRADICTED-IN-PROSE, or the reader's own REFUTED verdict) — do NOT ask him to explain any of these as though true; ask about the gap between the record and the code instead: <list|none>. UNVERIFIABLE claims, i.e. the reader could not settle them either way — do NOT build a question on one and do NOT treat one as verified; name it unconfirmed if it comes up: <list|none>\n\nCode:\n<code content>")
```

**Capture the generated set**:
```
python scripts/write_event.py "<discussion_id>" "educator" "proposal" "<question set with rubrics, concepts and planned entry points>" --confidence <score> --tags "quiz,education,blooms-taxonomy"
```

### Step 3: Ask — one question at a time

Ask **one** question, then stop and wait. Never dump the whole set. This is "open book":
the developer may read the code, the ADRs and the project profiles — but he must explain
in his own words, not read them aloud.

Capture the exchange as it happens, using the turn shape `docs/education/CONTRACTS.md`
§1.2 already locks for education transcripts, so an in-session loop and an ingested
phone transcript land as the same kind of Layer 1 record:

```
python scripts/write_event.py "<discussion_id>" "tutor" "question" "<the question as asked>" --tags "quiz,education,tutor-turn"
python scripts/write_event.py "<discussion_id>" "learner" "evidence" "<the developer's answer, verbatim>" --tags "quiz,education,learner-answer"
```

His **actual answer text** goes into that second event verbatim. Nothing else in the
stack stores it — `education_results` keeps only a number, so a wrong judgement is
unauditable unless this event exists.

### Step 4: On a miss — RE-TEACH, then ask again

Judge against the rubric: *demonstrated* or *miss*. A reasoned near-miss outscores
unexplained recall, **but correctness still gates** — a confident, well-argued, wrong
answer is a miss.

On **demonstrated**: record it (Step 5) and go to the next concept.

On **miss**, loop:

1. Identify the **concept** the miss traces to — usually not the concept the question
   was nominally about.
2. Pick an **entry point you have not already spent on this concept** (educator charter
   §2.2: consequence-first, analogy from a domain he already owns, counterfactual,
   concrete trace of one real value, the losing alternative's point of view,
   failure-mode-first, scale/limit). **A re-explanation that reuses the same frame with
   different words is not a re-explanation.**
3. Re-explain from there, then ask a **different** question on the same concept from
   that angle.
4. Capture the re-teach and the next answer:
   ```
   python scripts/write_event.py "<discussion_id>" "tutor" "critique" "miss on <concept>; re-teaching from entry point <name>; entry points already spent: <list>" --tags "quiz,education,reteach"
   ```
5. **Record the miss as its own `education_results` row** (Step 5) before asking again.
   Do not wait for the loop to settle and write only the winning attempt — the miss is
   the measurement.
6. Return to judging. **There is no turn limit and no strike count.**

If the same concept misses from **three different entry points**, stop guessing: either
dispatch the specialist the educator names (`dispatch_request` in its output) to explain
that concept directly, or ask the developer which part is not landing and pick the next
entry point from his answer. Capture either as a `question` turn.

The developer may say **stop / enough / later** at any time. Honour it immediately, with
no penalty framing. Go to Step 5 and record the honest state.

### Step 5: Record Results

Record **one row per attempt**, in the order the attempts happened — the miss *and* the
re-taught pass each get their own row. **The gate clears on the terminal attempt**; the
earlier rows are the measurement and must not be collapsed into it.

```
python scripts/record_education.py "<session_id>" "<discussion_id>" "<bloom_level>" "<question_type>" <score> <passed>
```
Run it once per attempt. A concept demonstrated on the second ask therefore produces two
rows: the miss (`passed` false) and the pass.

This is the rule `docs/education/CONTRACTS.md` §1.2 already locks for the
ingested-transcript path, so both education paths write one row semantics into one table.
Terminal-only rows would flatten the "Education Trends" average `/retro` and
`/meta-review` print to ~1.0 by construction, since this loop runs until the concept is
demonstrated — **the misses are the only variance the instrument has.**

**"M reached on the first ask, K after re-teaching" is NOT queryable from Layer 2 — write
it as prose below or it is lost.** `record_education.py` persists `id, session_id,
discussion_id, bloom_level, question_type, score, passed, timestamp` and nothing else — no
concept identity, no supersession link. Two rows sharing a session, a Bloom level and a
question type are therefore indistinguishable from two unrelated questions that share both
labels, and row order does not rescue it: consecutive ids routinely belong to different
concepts. The authoritative re-teach record is the Layer 1 `reteach` event (Step 4) and
the synthesis event below, where the concept *names* survive.

A concept the developer stopped on records as not passed. That is an **open gate, not a
verdict on him** — park it so it is not lost:
```
python scripts/education/gate_registry.py add --gate-id "EDU-<YYYYMMDD>-<slug>" --created-at "<YYYY-MM-DD>" --origin "<discussion_id>" --reason "<what is still open and which entry point to try next>" --file "<path>"
```
(`--gate-id`, `--created-at`, `--origin` and `--reason` are all required; `--file`,
`--adr`, `--spec` and `--branch` are optional and `--file`/`--adr` repeat. Verified
against `gate_registry.py add --help` in this repo — re-check before use in a derived
project, whose copy may differ.)

**And when a session CLOSES an open gate, the developer retires it — never you.** The
gate clears only on the developer's explicit action ("I clear it", ADR-0035): the tutor
teaches, records, and registers, but the registry flip that says the debt is paid belongs
to the developer who paid it. If this session started from a gate parked by an earlier
run — he came back, and demonstrated the concepts it names — do **not** run
`gate_registry.py clear` yourself, in this step or any other. PRESENT the evidence and
the exact command, and stop short of running it:

- the sealed discussion id(s) and the session id that hold the demonstration,
- what he demonstrated, concept by concept, one line each,
- the command below, filled in and ready to paste — he runs it, you never do:

```
python scripts/education/gate_registry.py clear --gate-id "EDU-<YYYYMMDD>-<slug>" --session-id "<session_id>" --discussion-id "<discussion_id>"
```
(All three flags are required; `--cleared-at` is optional and defaults to now UTC.
Verified against `gate_registry.py clear --help` in this repo — re-check in a derived
project. `gate_registry.py list --status open` shows what is currently parked.)

`add` without `clear` is still a one-way ratchet: the education backlog only ever grows
until a clear releases it, so it reports debt that has in fact been paid and stops being
a measurement of anything. The release is now the DEVELOPER'S clear, made on the evidence
you present — and that is the point, not a bottleneck. A tidy backlog bought by an agent
clearing unpaid gates is the defect this rule abolishes: a registry the tutor can flip
measures the tutor's tidiness, not the developer's understanding. Present the command
only for a gate whose named concepts were actually demonstrated here; a gate he stopped
on again stays open, with no command presented, because nothing downstream can tell a
paid gate from a tidied one.

Capture the session shape as a facilitator event — the part `education_results` cannot
hold:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "Tutoring session: <N> concepts, <M> reached on the first ask, <K> after re-teaching. Per re-taught concept: <concept> -> entry points spent <list> -> <demonstrated|stopped|escalated>. Demonstrated in own words: <list>. Still open: <list, with the next entry point to try>." --confidence 0.9 --tags "quiz,results,education,reteach-log"
```

### Step 6: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

### Step 7: Report

Report plainly, in this order:

- **What he can now explain in his own words** — quote him.
- **What is still open**, and the entry point to start from next time.
- **How the understanding was reached** — which concepts needed re-teaching and from
  which angles. This is the useful signal for the next gate.
- If anything is open, offer to continue now or resume later. Do not require either.

Do **not** report an overall percentage as the outcome, do **not** rank the session, and
do **not** use progress-praise language ("great job", "you've come a long way", streaks).
The per-item scores exist in `education_results` for trend analysis; they are not the
result of this command.
