---
title: Governance Mechanisms — the live list
status: partial
created: 2026-08-07
maintained_by: developer
---

# Governance Mechanisms — the live list

This is the list of mechanisms that actually constrain what the agent can do, written so you can
**explain each one out loud without notes**. That is the whole point: if you can only recite a row,
you have not passed the education gate on it.

## How to read a row

Every row has three parts, and **all three are required for an explain-back to count**:

1. **What it stops** — in plain language.
2. **How it stops it** — the mechanism, not the intention.
3. **Where it leaks** — the weakness. A row without a stated weakness is a row that will be
   believed further than it deserves. If you explain a mechanism as stronger than it is, you have
   correctly explained something untrue, which is worse than not knowing it.

## Status of this file — read before trusting it

Four documents already name this file as the live referent for governance explain-backs
(`docs/adr/ADR-0031-…:454`, `docs/sprints/SPEC-20260805-210524-…:506`,
`docs/sprints/PROPOSAL-20260806-…:33`, and `BUILD_STATUS.md`). **Line numbers rot**, and this
sentence proves it: on 2026-08-07 all four landed exactly; re-measured 2026-08-08 the first three
still do and the `BUILD_STATUS.md` one had moved from `:94` to `:128`, because that file is rewritten
every session. The number is therefore dropped rather than refreshed — a line number into a
session-scoped file is not a citation. Re-locate all four with
`grep -rn "governance-mechanisms" docs/ BUILD_STATUS.md`.
**Until 2026-08-07 it did not
exist** — the plan that was supposed to seed it (ADR-0031's Appendix A, "seeded from this appendix
at merge") was retired by ADR-0032 before the merge happened, so the seeding never occurred.

It is being started here with **six rows**: two from the slice that noticed the file was missing and
the round that followed it, and four added on 2026-08-07 by the round that went through the
framework's guard *prose* looking for claims the guard *code* does not make. It is deliberately
**not** backfilled with rows nobody has re-verified. A list that looks complete but contains
unverified rows is the exact failure this file exists to prevent. Rows get added as their mechanism
is measured, not as it is remembered.

**Rows 3–6 exist because their prose was found to be false, not because the mechanisms were new.**
That is worth saying plainly, because it is the pattern this file is really about. In every one of
the four cases the code was the *more honest* of the two artifacts, and the write-up had drifted
into describing an intention:

| Row | What the prose claimed | What the code did |
|---|---|---|
| 3 | the hook "blocks commits" containing secrets | it **asks**, on file writes only, never on a commit, and skips test files |
| 4 | the ledger guard proves a fixed bug still has a test | it only checked that a **filename** existed |
| 5 | growing the debt baseline "requires developer consent" | the consent was a sentence in a `--help` string; the file it guards **has never existed** |
| 6 | "education gates" run in every quality-gate profile | there is **no education check in the gate at all** |

**And then the rows did it again — six times so far, which is the most useful thing in this file.**

| # | Where | What the write-up did | Caught by |
|---|---|---|---|
| 1 | Row 4, first draft | Called its one real finding a *missing guard* and the red proof the *protection was absent*. Neither was true: the guard had been renamed and still runs. | Round-2 review, same day |
| 2 | Row 5, first draft | Asserted "no flag combination can grow the baseline" — a claim about `main()` — while the change **deleted** the only test that drove `--rebaseline` through `main()`. Restoring the literal defect left the suite **163/163 green**. | Round-2 critic, by mutation |
| 3 | Row 6, first draft | Gave `grep -n -i education scripts/quality_gate.py` as the evidence command; the prose that same change added to the docstring made it return 10 hits. The verification command was invalidated by the fix it was verifying. | Round-3 review |
| 4 | Row 5, second draft | Said `_check_against_baseline` "has never run outside its own tests" and called the mechanism "entirely unexercised". **`--rebaseline` runs it** — the one invocation the row is about. The row's own CLI test already asserted the RED that only that path produces. | Round-4 fixer, by spying on the function through `main()` |
| 5 | Row 6, second draft | The *correction* to #3 recorded "10 hits" at two line numbers. One day later: **11 hits**, both line numbers wrong. Nothing regressed; the file grew. | Round-4 fixer, by re-running the command |
| 6 | Row 5 leak 4, first draft | Reported "there were five" carriers and attributed the figure to a `grep` that returns **59 hits in 15 files**. The filter that yields five was applied in someone's head, not in the command. | Round-4 fixer, by running the command as written |

Read #2 twice. Row 4 states, in bold, *"a test that stays green when you break the thing it guards is
not evidence"* — and Row 5, in the same change, on the same day, moved a guarantee out of a test and
into a docstring. The drift is not a thing that happened once to old prose; it is what writing up
your own mechanism does to you, in the document whose entire subject is that failure. Rows are only
trustworthy to the extent someone re-measured them **after** they were written — and the only
measurement that counts is one that could have come out the other way.

**And read #4–#6 together, because they name the two shapes the drift actually takes**, and neither
is carelessness:

- **A true statement generalised one step too far** (#4). "With no baseline file the ordinary path
  runs" was checked, and was true — for the run that was checked. "So the comparison never runs" was
  never checked; it was inferred. *When you write "X never runs", spy on X; do not reason about the
  guard condition.*
- **Evidence that decays faster than the claim it supports** (#5, #6, and the `BUILD_STATUS.md` line
  number above). Counts and line numbers into files that are edited daily go stale in hours, which
  makes the row look verified while being unverifiable. *Prefer a decomposition, a ratio, or a file
  list to a count; and prefer a command whose output you have actually seen to one you believe.*

---

## Row 1 — Destructive-shell-command guard

*(`.claude/hooks/validate_tool_use.py` → `check_bash_command`; added 2026-08-07)*

> ### Read this before the rest of the row: what this mechanism claims to be
>
> **This guard is disclosed defence-in-depth. It raises the cost of a careless act. It is *not* a
> boundary, and nothing here — including your explain-back — may describe it as one.**
>
> That is a deliberate retraction, and it is the most important thing in this file. Three separate
> reviews each found a fresh way around this guard: shell grouping `( … )`, `&&` and `;` chaining,
> `bash -lc`, a mis-parsed `robocopy` destination, SQL spellings it could not read. Every fix was
> correct. Every round found more. **At some point the pattern stops being a list of bugs and
> becomes the finding:** you cannot work out what a shell command will do by reading its text,
> because a shell can spell any act an unbounded number of ways. A guard that keeps announcing it
> has closed the class *is itself* the "the write-up says more than the code does" failure this
> whole document exists to stamp out.
>
> So the verb tables have **stopped growing**. The fixes in the fourth round are parser repairs
> (the checker was skipping past the real command word), not new dangerous words.
>
> **The thing that actually answers "has my record been altered?" is Row 2, not this row.** Row 2
> compares bytes instead of predicting commands, so it cannot be out-spelled, and it works whether
> or not anyone wires this guard up. If you only have room to remember one mechanism, remember
> that one.

**What it stops.** The agent running a *shell command* that wipes out something the project cannot
get back: the discussion logs in `discussions/`, the metrics database, the `.git` folder, or the
settings and hook files that decide what the agent is allowed to do in the first place.

**Why it was added — this is not hypothetical.** On 2026-08-07 a subagent working in this repo
emptied a sealed discussion log with `: > …/events.jsonl` and ran `DELETE` statements against
`metrics/evaluation.db`. Both of those paths were *already* on the protected list. Nothing stopped
either one. The reason is worth understanding, because it is the general shape of this class of
bug: **the protection was attached to the wrong door.** The old check only ran when the agent used
the file-editing tools (`Write`/`Edit`). Running a shell command is a different tool (`Bash`), and
that door had no check on it at all. The list of protected files was correct; it simply was not
consulted on the route the agent actually took.

**How it stops it.** Before any shell command runs, the hook reads the text of the command and
looks for a destructive shape aimed at a protected path — a `>` redirect, `rm`, `mv`, `cp` onto,
`tee`, `chmod`, `sed -i`, a `python -c` or heredoc that writes or deletes, or a `sqlite3`
statement that deletes rows or drops tables. **It also has to know the other shell.** This machine's
primary shell is PowerShell, and the agent has a separate `PowerShell` tool alongside `Bash`, so the
same list exists a second time in Windows spelling: `Remove-Item`, `Move-Item`, `Rename-Item`,
`Clear-Content`, `Set-Content`, `Out-File`, `Copy-Item` onto a protected path, and the `cmd`
builtins `del`, `erase`, `rd`. This is not a footnote — a review of the first version of this guard
ran twenty PowerShell and `cmd` destructive commands through it and **all twenty were allowed**,
including a literal `Remove-Item -Recurse -Force discussions\2026-08-07`. The guard knew only the
shell the agent was *not* using.

**And knowing the words was still not enough.** A second review found that
`powershell -Command "Clear-Content …/events.jsonl"` was allowed *even after* the Windows verbs
were added — because the destructive verb was sitting inside a quoted argument to `powershell`,
and the only command word the checker ever saw was `powershell` itself. On a machine whose primary
shell tool **is** PowerShell, that is the most natural way to run anything, so the entire guard was
routed around by one word. The guard now **unwraps** `powershell -Command`, `pwsh -c`, `cmd /c`,
`bash -c`/`sh -c`, and base64 `powershell -EncodedCommand`, and re-checks what is inside. The
lesson is the one worth carrying: *the first fix was to a symptom of the same bug the second fix
found* — a checker that looks at the outermost word will keep being defeated by one more layer of
wrapping, and each time it looks like a new bug.

If it finds a destructive shape it returns a decision. **Read the third column: neither decision
means what its name suggests on its own.**

| Decision | What it actually does | The catch — do not state the row without it |
|---|---|---|
| **deny** | The command does not run. | There is **no override in-session**. The agent cannot force it through, and neither can you without editing the guard or running the command yourself. A false positive is therefore an unrecoverable cost, not an inconvenience. |
| **ask** | The command is paused and handed to a human. | **We have not verified that a human is always there.** The code's own comment says it: `ask` has not been tested under `--permission-mode bypassPermissions`, and this framework runs exactly those sessions (`scripts/session_supervisor.py`). Treat `ask` as **"probably stops it"** — that is the code's phrase, not a softening of it. `.env` and the whole `UPDATE`/`INSERT` class rest on `ask` alone. |

> **Why that second row is worded that way.** An earlier version of this table said `ask` means
> "the command is paused and handed to you to approve" — full stop. That is a *stronger* guarantee
> than the code believes it has, in the one file whose stated purpose is that a row without its
> weakness gets believed further than it deserves. If you had explained that row back, you would
> have correctly explained something untrue. The code was the more honest of the two; the table has
> been brought down to meet it.

There is a third decision, and it is the easiest to misread: for SQL the guard **cannot read**
(`sqlite3 metrics/evaluation.db < wipe.sql` — the statements live in a file the hook never opens)
it returns `ask`. That `ask` means **"nobody read this"**, not "this was checked and found safe".

**The line between deny and ask was drawn by measurement, not taste.** An earlier draft denied
*all* database writes. Running that draft against every command in this repo's own documentation
showed it would have blocked `/promote`, which legitimately runs `UPDATE` on the metrics database.
A second draft denied all writes under `discussions/`; measurement showed it would have broken
`/review`, `/deliberate` and `/analyze-project`, all of which write a `state.json` file inside a
discussion folder. Both were corrected. This matters more than it sounds: **a guard that blocks
ordinary work gets switched off by the first person it annoys, and a switched-off guard is exactly
the same as no guard.**

**What it was measured against — and how to re-run it.** The corpus is every fenced
` ```bash / ```sh / ```powershell / ```python ` block in this repo's own
`.claude/{commands,skills,rules,agents}/**/*.md` plus `CLAUDE.md`, plus every line of
`.claude/hooks/*.sh` — 68 markdown files and 7 hook scripts, excluding `.claude/worktrees/`
(vendored third-party repos, not our instructions). Counted two ways, because a multi-line inline
`python` block is one command, not five: **1,699 individual lines** (24 name a protected path) and
**184 whole blocks** (18 name a protected path). Against that corpus the guard **denies 0** on both
counts, and **asks about 2** of the 184 blocks — both of which are the `/promote` database update, a
step that already requires human approval under Principle #6. (The per-line count asks about 0,
because splitting a `python -c` block into separate lines leaves no line that still reads as a SQL
statement — which is itself worth noticing: *how you slice the corpus changes the answer*, so the
slicing is stated rather than assumed.) Widening the verb list to PowerShell and `cmd` added **zero** new
denials and **zero** new asks against the same corpus, which is the evidence that the Windows half
was pure gain rather than a trade against ordinary work.

> An earlier draft of this row cited "1,888 command entries, 83 naming a protected path" without
> stating which files it counted. That corpus could not be reconstructed, so the figures above
> replace it — measured, with the corpus written down so you or anyone else can re-run it. **A
> number whose corpus is unstated is not a measurement.** The `denies 0 / asks 2` result did
> reproduce.

**Re-measured after the second round of fixes** (wrapper unwrapping, `cd` resolution, removing the
append carve-out, matching `New-Item`'s file form, flagging unreadable SQL). Every one of those
*widened* what the guard refuses, and widening a refusal set is precisely how a guard starts
blocking ordinary work and gets switched off — so the corpus was re-run rather than assumed: same
68 markdown files, 7 hook scripts, 184 blocks, 1,699 lines, still **18 blocks / 24 lines** naming a
protected path, and still **denies 0, asks 2** (both `/promote`) on blocks and **denies 0, asks 0**
on lines. **Zero new denials.** That number is the whole argument for the stricter rules: the guard
got stricter against the bypass shapes and no stricter at all against this repo's documented work.

**Re-measured again after the third round** (the inline-python attribution fix in leak 5, which
*narrows* what the guard refuses rather than widening it). The headline result reproduces on the
current code: **denies 0, asks 2** across blocks — both of them the `/promote` `UPDATE`, which
already needs human approval under Principle #6 — and **denies 0, asks 0** across lines. But read
the next sentence rather than the numbers above it: **rebuilding the corpus from the description in
this row did not reproduce the corpus counts.** The file counts did (68 markdown files, 7 hook
scripts, both exact); the slicing did not — this re-run found 177 fenced blocks and 1,993 non-blank
lines against the recorded 184 and 1,699, because the description does not pin down whether hook
script lines count as "blocks", whether blank and comment lines are dropped, or whether a ` ```pwsh `
fence is included. The earlier counts are **left as recorded rather than overwritten**, because a
number measured by someone else with a slicing I cannot reconstruct is not mine to correct — and
the point of this paragraph is that *"denies 0" survived a rule change and a re-implementation of
the corpus, while the corpus size did not survive being described in prose*. A corpus is only
reproducible if the slicing is written down as code, not as a sentence.

**Where it leaks.** Six places. The word doing the work in that sentence is **known** — the last
time this row named a closed set of leaks it said "four", and the very next review found a fifth
that was wider than any of the four. Treat the count as "what we have caught ourselves at so far",
not as a boundary:

1. **It reads text, it is not a wall.** It matches the *words of the command*. Anyone — including
   the agent — can get past it by hiding the path: putting it in a variable, encoding it, using a
   wildcard that only becomes the real path when the command runs, or simply putting the
   destructive line inside a script and running the script. It raises the cost of an accident. It
   does not make destruction impossible, and it is not a sandbox.
2. **A relative path defeats it completely, and on this machine that is not theoretical.** The
   guard matches paths by *name*. But a shell has a current directory, and a path can be relative
   to it. `cd discussions/2026-08-07 && rm -rf DISC-1` **is** now caught, because both halves are
   in one command string and the guard joins them. What is **not** caught — and cannot be — is the
   same thing split across two tool calls. Both the `Bash` and `PowerShell` tools state that the
   working directory **persists between calls**, so `cd discussions/2026-08-07` in one call and
   plain `rm -rf DISC-1` in the next gets through: the second command's text names nothing
   protected, and this hook sees one command at a time with no memory of where the shell is
   standing. *No amount of reading command text fixes this.* It is the clearest illustration of
   why the whole mechanism is a guard rail and not a sandbox.
2b. **The checker used to skip past the real command word — and that defeated the whole table at
   once.** A fourth review found that shell *grouping and control flow* routed around every verb
   in it, with the protected path spelled out in full and nothing hidden. Measured as ALLOW before
   the fix: `( rm -rf discussions/2026-08-07 )`, `{ rm -rf …; }`,
   `for f in 1; do rm -rf …; done`, the `while` / `until` / `if` spellings of the same,
   `1 | ForEach-Object { Remove-Item -Recurse -Force … }`, `foreach ($i in 1) { … }`,
   `try { … } catch { }`, `1 | % { Clear-Content …/events.jsonl }`, and
   `if ($true) { Clear-Content …/events.jsonl }`. The cause was one line: the guard took the
   **first word of the command** as *the* command, so a leading `do`, `then`, `try`, `(` or
   `ForEach-Object` stood in front of `rm` and hid it. Every verb was on the table; the parser
   never got that far. Also fixed: `bash -lc '…'` (the `-c` fused into a flag cluster, so the
   payload was never unwrapped), and `robocopy SOURCE DEST *.jsonl`, which names its destination
   **second**, not last — so a verb that was *on* the table allowed exactly the write it was added
   to catch.

   **Why this one is worth understanding and the next one may not be.** These were parser repairs,
   not new words — and the set they close (shell *reserved words*) is genuinely finite, because
   the two shell grammars define it. That is the opposite of the verb tables in the next leak,
   which are bounded only by imagination. It is also the third consecutive round in which "the
   outermost word fooled the checker" produced a bypass that looked like a brand-new bug. **Assume
   there is a fourth spelling nobody has thought of, and rely on Row 2 for the guarantee.**

3. **The list of dangerous words is a list, and lists end.** The guard recognises destruction by
   matching a *verb* against a fixed table — **42 command words** today (37 entries across the two
   verb tables, plus `sed`, `git`, `find`, and `New-Item`/`ni` handled as special cases) plus 5
   destructive `git` subcommands. A verb nobody thought to add is invisible, no matter how
   obviously destructive it is. Known-missing today: PowerShell's .NET escape hatch
   (`[System.IO.File]::Delete('…')`), `Invoke-Expression`/`iex` on a string built at runtime,
   `Start-Process`, and cmdlet aliases nobody listed. (`cmd /c` and `New-Item -Force` were on this
   list in the previous version and are now handled — which is the point: **the list of known gaps
   is itself a list that ends**.)

   **Four more are known, reachable, and were left open on purpose in the fourth round.** This is
   a change of policy, so it is written down rather than left to be inferred: `perl -i` is
   unmatched while `sed -i` is matched; `chmod`'s Windows twins (`attrib -r`,
   `Set-ItemProperty -Name IsReadOnly`) are unmatched — *including the PowerShell primitive for
   un-sealing a sealed `events.jsonl`*; `Path.replace` is unmatched while `Path.rename` and
   `os.replace` are matched; and `eval`, background `&` placement, here-strings, PowerShell
   splatting and profile aliases are untested. Each is a one-line fix. **Fixing them is what was
   declined**, because every one would add an entry to a closed enumeration and thereby re-inflate
   the claim the box at the top of this row retracts — and the fourth round would have ended the
   way the first three did, announcing a class was closed that is not closable. Note the one that
   stings: un-sealing a record is *not* refused here.

   **This is where that sentence used to overclaim, and the correction is the point.** It said
   un-sealing was "caught after the fact by Row 2, which reports a sealed record that stopped being
   sealed". Row 2 did report that — as **CHANGED**, which is exactly why it also reported 236 of
   this repo's 278 untouched records as CHANGED on any checkout without the metrics database (see
   Row 2). Row 2 now treats a lost read-only bit as a **warning about metadata, not evidence about
   bytes**, and cannot report it at all when the database is absent. The accurate version is
   narrower and still worth having: *un-sealing is not refused and is not by itself a red; what
   Row 2 catches is any change to the bytes — including the change the un-sealing was performed in
   order to make.* Un-sealing is a step, not the act. **Detection beats prediction on the act, not
   on the preparation**, and the earlier sentence quietly claimed both.

   This is the *general* version of the bug that caused both the
   PowerShell gap and the `powershell -Command` gap: **the guard's coverage is exactly as wide as
   somebody's imagination on the day they wrote the list**, and nothing tells you when it has gone
   stale. If you remember one limitation beyond "it reads text", remember this one.
4. **There is SQL it cannot read.** `sqlite3 metrics/evaluation.db "DELETE FROM findings"` is
   caught, because the statement is right there in the text. `sqlite3 metrics/evaluation.db <
   wipe.sql` and `sqlite3 … ".read wipe.sql"` are not — the statements are in a file the hook never
   opens. Those now return `ask`, but re-read that as **"nobody read this"**, because that is
   literally all it means. The file could be a report or it could be the incident.
5. **It can be wrong in both directions, and being wrong one way is unrecoverable.** Path matching
   is by whole path *component*, so `my-discussions-notes/` is correctly left alone — but a scratch
   copy of the database at `/tmp/backup/metrics/evaluation.db` would still be refused, and
   `deny` has **no override**. The refusal message names the exact token that matched so you can
   see the misfire; the only remedy is that you run the command yourself.

   **This is not only a lookalike-path problem — and the real instance was worse.** A review
   measured the `python -c` branch and found it denied *read-only analysis*. The rule asked two
   **separate** questions — "does this bit of python contain a writing verb anywhere?" and "does
   the command mention a protected path anywhere?" — and refused when both were true. It never
   checked the one thing that matters: **whether the write was aimed at the protected path.** Six
   ordinary read-only commands were refused:

   | Command | Why it was refused | What it actually did |
   |---|---|---|
   | `shutil.copy('metrics/evaluation.db','/tmp/scratch.db')` | mentions the database; `copy` is a writing verb | **copies the database out to scratch — the exact idiom this repo's own task briefs tell you to use** so analysis never touches Layer 2 |
   | `sqlite3.connect('file:metrics/evaluation.db?mode=ro', uri=True)` … `open('/tmp/o.json','w').write(...)` | mentions the database; `.write(` is a writing verb | opens the database **read-only** and writes its *report* to `/tmp` |
   | same, ending `csv.writer(open('/tmp/o.csv','w'))` | same | same |
   | `sys.stdout.write(open('discussions/a/events.jsonl').read())` | mentions `discussions/`; `.write(` | **prints a file to the screen** |
   | `open('/tmp/out.txt','w').write(str(count_of_files_under_discussions))` | mentions `discussions/`; `.write(` | counts files and writes the number to `/tmp` |
   | the same command written as a heredoc | same | same |

   Every one of those has a shell twin — `cp metrics/evaluation.db /tmp/backup.db` — that the
   guard **allowed**. So the same act got two different verdicts depending on which language you
   wrote it in, and the stricter of the two had no override. That is not a stricter guard; it is a
   guard that teaches you to route around it, which is the failure mode this row keeps naming.
   **It has been fixed**: the guard now finds each writing call and checks *the operand that call
   actually writes to* — the thing before the dot in `Path(...).write_text()`, the **last**
   argument of `shutil.copy` (the first is only read), the **first** argument of `open(..., 'w')`.
   A protected path anywhere else in the program is no longer a hit.

   Two things remain, and both are the same shape as leak 3: the list of python writing verbs is
   **also a list that ends** (`os.open`, `zipfile.ZipFile(p,'w')`, and `import shutil as sh` are
   not recognised); and when the target is a *variable* rather than a written-out path, the guard
   follows it back exactly one step and no further — if it still cannot tell, it returns `ask`, which
   here means **"we could not work out what this writes to"**, not "this is fine". Re-read the
   `ask` row of the table above before treating that as safety.

   The general lesson is worth more than the fix: **a guard that checks "are these two things both
   present?" is not checking "is this thing doing that to that thing?"** The first is easy to write
   and looks identical to the second on the days when nothing legitimate is happening.
6. **It is switched off right now** *(true as of 2026-08-07 — check before repeating it)*. The
   guard only runs if `.claude/settings.json` tells the shell tools to call the validator, and it
   must name **both** of them — `"matcher": "Bash|PowerShell"`. Wiring only `Bash` would leave the
   `PowerShell` tool completely unrouted, which on this machine is the larger half of the hole:
   the code would know the Windows verbs and never be asked about them. That file is protected on
   purpose — the agent cannot edit it, you apply it by hand:

   ```json
   {
     "matcher": "Bash|PowerShell",
     "hooks": [
       { "type": "command", "command": "bash .claude/hooks/pre-tool-use-validator.sh", "timeout": 5 }
     ]
   }
   ```

   Add that as a new entry in `hooks.PreToolUse` (today that array has a `Write|Edit` entry, which
   is where the validator currently sits, and a `Bash` entry that runs two *other* hooks and never
   calls the validator). **Until you paste that in, every word above describes code that never
   runs.** This is the single most important sentence in this row, and the one most likely to be
   dropped when the row is summarised.

   And it is **five checkouts, not one file** — measured read-only on 2026-08-07, and the fourth
   one is worse than the other three:

   | Checkout | Its `validate_tool_use.py` | Validator wired on |
   |---|---|---|
   | this template | 1,533 lines (has the guard) | `Write\|Edit` only — **shell tools unrouted** |
   | `agentic_journal` | 235 lines (no guard) | `Write\|Edit` only |
   | `VerificationPortal` | 232 lines (no guard) | `Write\|Edit` only |
   | `howie_family_wiki` | 232 lines (no guard) | `Write\|Edit` only |
   | `dan_research_karpathy_wiki` | 232 lines (no guard) | **nothing — it has no `PreToolUse` key at all** |

   All five rows were re-verified read-only on 2026-08-07. Three corrections to the previous
   version of this table, all of the same kind — *a number or a word that was right when written
   and silently went stale or was never checked*:

   - **this template is now 1,533 lines, not 1,055.** The guard has been through four rounds of
     fixes since that figure was written. A line count in a table is a fact with a short shelf
     life — this one went stale *twice inside the session that corrected it*, which is why it is
     now pinned by a test (`test_the_template_line_count_in_the_table_is_current`) that fails the
     moment the file and this row disagree. That is the general remedy for every rotting number in
     this file: not more care, but a check that fails out loud. It is kept here at all only
     because it is the quickest way to see at a glance which checkouts have the guard and which
     have the 232-line original.
   - **`dan_research_karpathy_wiki` does not have an *empty* `PreToolUse` array — it has no
     `PreToolUse` key at all.** The conclusion is unchanged (its validator never runs, on any
     tool), but the earlier wording was disproved by *this row's own re-run command*, which prints
     `None`, not `[]`. Worth pausing on: the command that refutes the claim was printed directly
     beneath it, and nobody ran it. That is what "measured" has to mean — not "plausible enough to
     write down next to a command".
   - the three middle rows each *do* have a second `Bash` matcher in their settings, but it runs
     other hooks and **never calls the validator**, so "`Write|Edit` only" is correct for the
     validator and is what this column means.

   So the four derived projects do not have this guard at all yet, and the last one does not even
   run the older validator on file writes. Wiring *this* checkout fixes one fifth of the problem;
   the other four need the guard propagated **and** wired. Re-run the measurement rather than
   trusting the table: `python -c "import json;d=json.load(open(r'<repo>/.claude/settings.json'));
   print(d.get('hooks',{}).get('PreToolUse'))"` — and if it prints `None`, that means the key is
   absent, which is a *different* state from an empty list even though both mean "never runs".

**One-sentence explain-back you should be able to give:** *"The protected-file list was only
checked when the agent edited a file, not when it ran a shell command, so a shell command could
delete anything; we now also read the command text — in both Bash and PowerShell spelling, inside
`powershell -Command`/`cmd /c`/`bash -lc` wrappers, and now past a leading `do`/`then`/`try`/`(`
that used to hide the real command — and refuse the destructive shapes it recognises. But it is
pattern-matching against a finite list of dangerous words and it is **defence-in-depth, not a
boundary**: three rounds of review each found a new way around it, some known ways are still open
on purpose, it cannot see a relative path left over from a `cd` in an earlier call, `ask` only
probably stops anything in a headless session, and it does nothing at all until both shell tools
are wired to the validator in settings.json. **The mechanism that actually tells me whether a
sealed record was altered is the Layer 1 integrity check in Row 2, which compares stored hashes
instead of guessing at commands — that one works no matter how the change was made, and it does
not depend on the settings.json wiring.**"*

> **Why that sentence changed.** The previous version ended "…and deny the irreversible things
> while asking about the rest." A review then measured `for f in 1; do rm -rf discussions/…; done`
> and `1 | ForEach-Object { Remove-Item -Recurse -Force discussions/… }` as **allowed**. Anyone
> who explained that row back would have confidently stated that shell deletion of Layer 1 is
> refused, while an ordinary loop — in the shell this machine actually uses — was not. Those two
> shapes are fixed now, but the sentence has been rewritten to stop making the *kind* of claim
> that keeps turning out to be false, rather than being re-issued with two more exceptions
> patched into it.

---

## Row 2 — Layer 1 sealed-record integrity check

*(`scripts/verify_layer1_integrity.py`, wired into `scripts/quality_gate.py` as
`check_layer1_integrity`; added 2026-08-07)*

**What it does.** It answers a question you could not ask before: **"has my record been altered?"**
When a discussion is sealed, a `sha256` fingerprint of its `events.jsonl` and `transcript.md` is
written to an append-only list. The quality gate re-computes those fingerprints and reports any
sealed record whose bytes no longer match.

**Why it exists — and why it is a *different kind* of mechanism from Row 1.** On 2026-08-07 a
subagent truncated a sealed `events.jsonl` in this repository to zero bytes. Two things about that
are worth sitting with:

- The file **was already read-only on disk** (`IsReadOnly=True`, measured). The read-only bit is a
  speed bump, not a seal.
- The quality gate **had never once looked at Layer 1.** Measured:
  `grep -n "events.jsonl" scripts/quality_gate.py` exited `1` — no match, anywhere, ever. The
  layer the whole framework calls its canonical record was the one layer nothing checked.

Row 1's approach is to *predict*, from the text of a command, whether it will destroy something.
Three rounds of review showed that cannot be finished. Row 2 takes the opposite approach and **does
not look at commands at all.** It looks at the bytes, before and after. So it reports a change
identically whether it arrived via `rm`, an editor, a Python script, a `git` operation, a
background process, or a subagent nobody was watching — including through every bypass Row 1 does
not know about yet, and every one nobody has invented.

That is the lesson worth taking from this row: **a control that checks the outcome cannot be
out-spelled by the input.** Row 1 has to be right about an unbounded number of command spellings.
Row 2 has to be right about one comparison.

**Three states, not two — and the third one is the honest part.** A check that only says
"intact / not intact" has to lie about records it has never seen, and that lie always resolves
toward "fine".

| State | What it means | What the gate does |
|---|---|---|
| **CHANGED SINCE SEALING** | Something is true about the **bytes**: they no longer match the fingerprint, or the file is gone from disk, or the list holds two conflicting fingerprints for it, or git holds a committed version that this is not. | **Fails the gate.** There is no benign reading of this. |
| **UNKNOWN** | Sealed on disk, but no fingerprint — never baselined. | **Warns.** An *absence of evidence*: not a pass, not a failure. |
| **VERIFIED** | A fingerprint exists and the bytes still match it. | Passes. |

Plus a flag cutting across all three: **SUSPECT**. A record can be frozen without ever having been
correct. Exactly one such record exists in this repository today — the truncated one — and the
check refuses to fold it into the "intact" total. **"Unchanged since we started watching" and
"known good" are different claims**, and this is where that distinction earns its keep.

> ### The word "bytes" in that first row was bought, not free — read this one
>
> An earlier version of this table said CHANGED had no benign reading, and that sentence was
> **false**, in the direction that matters most: it was false on *your* machine the first time you
> cloned the repo.
>
> The check used to decide what to look at by asking "is this record sealed *right now*?" — and
> "sealed" means either a row in `metrics/evaluation.db` or the read-only bit on the file. Neither
> of those survives a checkout. `git check-ignore -v metrics/evaluation.db` prints
> `.gitignore:13:*.db`, so **the database is not in git at all**, and git does not carry the
> read-only bit either. So on a fresh clone, a worktree, a CI runner, or any of the four derived
> projects, almost nothing looks sealed — and every fingerprinted record that no longer looked
> sealed was reported as **CHANGED**. Measured on this repository: **236 of 278 byte-identical
> records reported CHANGED**, with the reason "sealed record is no longer sealed". The 42 that
> survived were the 21 read-only directories × 2 files. Not one byte had moved.
>
> That is worse than a bug, and the reason is the whole argument for this row: **a detective
> control's only asset is that it cannot be argued with.** A red that is wrong 236 times out of 278
> teaches everyone who sees it that the red means nothing — and then the one that is real is dropped
> along with the rest.
>
> The fix is a change of premise, not a patch: **a record is watched because it is in the
> fingerprint list, full stop.** It is hashed and compared no matter what the seal metadata says
> about it today. Losing the read-only bit or the database row is now a **separate, never-fatal
> signal** ("no longer sealed"), because it is a fact about metadata and says nothing whatever about
> the bytes — and it is suppressed entirely when the database cannot be read at all, since then it
> is not a measurement, just an absence.
>
> **What that costs, stated plainly rather than left to be discovered:** un-sealing a record no
> longer turns the gate red by itself. What still turns it red is any change to the bytes, before or
> after the un-sealing — including a change the un-sealing was performed in order to make. The
> guarantee is about content, and it is now stated as a guarantee about content.

**Why UNKNOWN warns instead of failing.** On the day this ships *nothing* has a fingerprint, so
every sealed record is UNKNOWN. Failing there would turn the gate red on day one here and in every
derived project — and a gate that is red for reasons you cannot fix is a gate people learn to
ignore, which is the same failure mode Row 1 keeps naming. Only positive evidence of change turns
it red.

**Where the fingerprints live, and why not somewhere more obvious.** In
`metrics/layer1_manifest.jsonl`, a repo-level append-only file.

- **Not a file inside the discussion folder.** A fingerprint stored next to the thing it guards is
  removed or rewritten by the very same `rm -rf`, `git checkout` or regeneration that damages the
  record. *A witness you can edit in the same gesture as the evidence is not a witness.*
- **Not only the metrics database.** Measured: `.gitignore` line 13 matches `*.db`, so
  `metrics/evaluation.db` is **not tracked by git**. Fingerprints kept only there would have no
  independent history to check them against, and a binary file's changes are invisible in review.
  The manifest is tracked, so each entry appears in `git diff` as a readable line and
  `git log -p metrics/layer1_manifest.jsonl` is a second, separate record of the same claims.
- **First entry wins.** A sealed record's fingerprint never legitimately changes, so nothing in the
  tooling can overwrite one; re-running the baseline only adds entries for records that have none.
  Appending a second, different fingerprint for the same record is reported as a **conflict** —
  counted as CHANGED — rather than quietly accepted as an update.

**What it still cannot do — say this whenever you say the rest.**

1. Someone who edits a sealed record **and** hand-edits its fingerprint line will read as VERIFIED.
   The cost is two coordinated edits in two places instead of one, and the second shows up in
   `git diff`. The check itself cannot see it.
2. Someone who also rewrites git history defeats the git cross-check below. Nothing kept on this
   machine survives that. **The fix is a copy this machine cannot write** — a push to a remote, a
   signed tag, an external log. That does not exist yet, and this sentence is here so its absence
   is not mistaken for its presence.
3. **Detection is not prevention.** It tells you a record changed. It does not stop the change and
   cannot bring the original bytes back — recovery depends on git history or a backup.
4. Anything sealed before it was ever baselined is frozen *as it is now*. See SUSPECT above.
5. **It watches the fingerprint list, so a record that was never fingerprinted is not watched.**
   That is not a hole so much as the shape of the thing — it is what UNKNOWN exists to say out
   loud — but it is worth saying next to points 1–4, because the fix for the 236/278 false red made
   the fingerprint list the *only* thing that decides what is under watch. A record deleted before
   it was ever baselined leaves no trace here at all. `--baseline` runs on every close, so the
   window is one unclosed discussion wide; the window is not zero.
6. **"No longer sealed" is reported, and no longer fails.** If someone strips the read-only bit or
   drops the closed row, you get a warning line, not a red gate — and if the metrics database is
   missing you do not even get the warning, because the question cannot be asked. What you still
   get, in every one of those cases, is the byte comparison.

**A second, independent witness: git.** A sealed record git reports as modified has changed since
it was committed — detectable **with no fingerprint at all**, so it catches damage predating this
mechanism. Measured here: of 140 sealed `events.jsonl`, **136 are tracked and 136 of 136 match
their committed blob exactly; 0 differ; 4 are untracked** (three created that day, one of them the
truncated record). Zero noise, so if it ever fires it means something. If git is unavailable the
report says **"DID NOT RUN"** rather than implying a clean result — absence of a check must never
read as absence of a problem.

> **And this witness told a lie too, in the narrowest possible window.** The check used to work out
> "does this differ from the committed version?" by reading git's short status *code* for the file
> and treating anything that was not the code for "untracked" as "differs". A file you have just
> `git add`-ed has the code `A ` — **added**, not modified — so staging a brand-new sealed
> discussion made both of its files report *"differs from its committed git blob"*, for files that
> **have no committed blob at all** and matched their fingerprint byte for byte. Reproduced
> end-to-end: before `git add discussions`, `PASS Layer 1 integrity (2 sealed record(s) verified)`;
> after it, `FAIL … 2 sealed record(s) CHANGED since sealing`.
>
> That window is not obscure — it is *the* window. The commit-time gate reads
> `git diff --cached --name-only` to find what you are committing, so the gate is **designed** to
> run after you stage. Sealing a discussion and committing it, the single most ordinary thing you
> can do with Layer 1, went red.
>
> The lesson repeats Row 1's, from the other side: **the fix was to stop inferring the answer and
> ask git the question.** The check now asks git directly which paths actually have a version in
> `HEAD` (`git ls-tree -r HEAD -- discussions`). No committed version means *uncorroborated* — no
> second witness exists — which is honest. Only a file git genuinely holds a committed version of
> can be said to differ from it.

**What was measured, and how to re-run it.** Against this repository as it stands: **174**
discussion directories, **161** with an `events.jsonl`, **140** sealed (sealed means the metrics DB
marks it closed *or* the file is read-only on disk — measured, the 21 read-only ones are a strict
subset of the 140 closed ones), giving **278** sealed files under watch. A first run reports
**278 UNKNOWN, 0 CHANGED, 1 SUSPECT** and exits **0** — the day-one behaviour above. After
baselining: **278 appended, 278 VERIFIED, 1 SUSPECT, 8 uncorroborated by git**, still exit `0`.
Baselining rewrote no history and blessed nothing: the truncated record is frozen *and* reported
as SUSPECT.

**The measurement that mattered most is the one taken with the database taken away** — because that
is the state every clone, worktree, CI runner and derived project is in, and it is the state nobody
had run the check in. Fingerprint this repo into a scratch list, then re-verify with the database
path pointed at a file that does not exist:

```bash
python scripts/verify_layer1_integrity.py --baseline --manifest /tmp/base.jsonl --no-git
python scripts/verify_layer1_integrity.py --manifest /tmp/base.jsonl --db /tmp/nope.db --no-git
```

Before the fix that second line printed **`CHANGED 236 / VERIFIED 42`**. It now prints
**`CHANGED 0 / VERIFIED 278`**, plus the line
`seal-state check  DID NOT RUN (metrics/evaluation.db absent or has no 'discussions' table)` — the
same discipline as git's "DID NOT RUN": a check that could not run says so instead of contributing
a number. A database that exists but has no `discussions` table gives the identical result, and that
matters because the code reaches it by a different route (it swallows the SQL error).

Re-run the ordinary case yourself — both commands only read:

```bash
python scripts/verify_layer1_integrity.py             # verify + report
python scripts/verify_layer1_integrity.py --baseline  # fingerprint anything not yet recorded
```

**How it was proved to actually work.** A test copies a **real** sealed record into a scratch
directory, baselines it, truncates it exactly the way the 2026-08-07 incident did, and asserts the
check goes red — plus a clean tree going green and a never-baselined tree doing neither. The suite
is **49 tests** (`pytest tests/test_layer1_integrity.py -q` → `49 passed`), of which **9 were added
by the round that found the two defects above**: five pinning that a fingerprinted record with no
database still reads VERIFIED (one of them over this repository's own 278 real records), and four
pinning git's short status codes — `A ` and `AM` are *uncorroborated*, only ` M` is CHANGED.

Two of the nine are the ones worth understanding, because they are the ones guarding against the
fix having been a cheat: **a tamper and a deletion must still be caught with no database at all.**
Making a false red go away by going blind would have been the easier fix and a far worse one.

Both defects were then confirmed *in reverse*: each pre-fix behaviour was restored one at a time in
a scratch copy of the source and the new tests re-run. The enumeration mutation reproduced
`AssertionError: 236/278 byte-identical records reported CHANGED with no DB` and failed all five;
the git mutation failed three of four — passing exactly the ` M` case, which is the one the old code
got right and the reason nobody noticed. **A test that stays green when you break the thing it
guards is not evidence.**

> Two numbers in this paragraph were corrected rather than carried forward. The suite was recorded
> as **39 tests**; it held **40** immediately before this round (49 now, minus the 9 added), so the
> recorded figure had already drifted by one and the drift cannot be accounted for — it is flagged
> here rather than quietly overwritten. And the earlier claim that **22 deliberate breakages** were
> applied with 0 survivors was **not re-run** this round; two targeted mutations were, and only
> those two are claimed above. A measurement you did not take is not a measurement you have.

**One-sentence explain-back you should be able to give:** *"Layer 1 is the canonical record, but
nothing ever checked it — the quality gate had literally no reference to `events.jsonl`, and a
sealed, read-only discussion log was truncated to zero bytes with nothing objecting. So when a
discussion is sealed we now store a hash of it in an append-only list kept outside the discussion
folder, and the gate re-hashes and compares: **a record is watched because it is on that list, and
red means its bytes moved** — never merely that it stopped looking sealed, because sealed-ness lives
in a gitignored database and a file bit that no clone carries, and reporting that as damage marked
236 of our 278 untouched records CHANGED on any fresh checkout. One that was never baselined only
warns, and one that was already damaged before we started watching is frozen but flagged suspect
rather than counted as intact. Unlike the shell guard in Row 1 it doesn't try to guess what a
command will do, so it catches a change however it was made and it works even though the
settings.json wiring is still missing — but it tells me afterwards rather than preventing it, it
only watches what has been fingerprinted, and someone who edits both the record and its hash line,
or who rewrites git history, still gets past it."*

> **Why that sentence changed.** The previous version said only "a record whose bytes changed since
> sealing fails the gate", which described what the code was *meant* to do rather than what it did:
> it also failed on a record that had merely stopped being classified as sealed, and that is the
> normal state of every record on every clone. Both this row's table and the code's own docstring
> said "there is no benign reading of this" about a verdict that was benign 236 times out of 278.
> The claim has been brought down to the thing the code can actually back — and the sentence now
> carries the limit ("only watches what has been fingerprinted") that the narrower claim implies.

---

## Row 3 — Secret scan on file writes

*(`.claude/hooks/validate_tool_use.py` → `SECRET_PATTERNS` / `detect_secret`; row added 2026-08-07)*

> ### Read this first: it does not do the thing it was written down as doing
>
> `.claude/rules/security_baseline.md` said, in full: *"The PreToolUse hook scans for 12 secret
> patterns and **blocks commits** containing them."* Both halves are false. It does not block, and
> it never sees a commit. That single sentence is the clearest example in this repo of the failure
> this document exists to stop: a developer who explained it back accurately would have stated a
> guarantee — *"secrets can't get into my commits"* — that nothing in the repo provides.

**What it stops.** You (or the agent) **typing an API key into a source file**. When a file is
written or edited, the hook reads the content being written and matches 12 regexes: AWS `AKIA…`
keys, GitHub `ghp_…` tokens, `sk-ant-…` and `sk-proj-…`, Google `AIzaSy…` and `ya29.…`, Slack
`xox…`, JWTs, PEM `-----BEGIN … PRIVATE KEY-----` headers, bearer tokens, `export SECRET=…`, and a
generic `api_key = "…20+ chars…"` assignment shape.

**How it stops it — and this is the whole weakness.** It returns `permissionDecision: "ask"`. Go
back and read the `deny`/`ask` table in Row 1, because every word of it applies here: `ask` hands
the decision to a human, has **not** been verified to stop anything under
`--permission-mode bypassPermissions`, and this framework runs exactly those sessions. There is no
`deny` anywhere in the secret path.

**Where it leaks.** Four places. The first three were measured on 2026-08-07 by feeding real
payloads to `.claude/hooks/validate_tool_use.py` on stdin and reading the decision back:

| Probe | Result |
|---|---|
| `Write` `src/leak.py` containing an AWS key + a `ghp_` token | `permissionDecision: "ask"` — **not** `deny` |
| `Bash` `git commit -m 'add key'` | **no decision at all** — the commit is not inspected |
| `Write` `tests/test_leak.py`, byte-identical secret | **no decision at all** — test files are exempt |

1. **It asks; it does not block.** See above.
2. **It is on the wrong door for commits.** The hook is wired on the `Write|Edit` matcher. `git
   commit` is the `Bash` tool, and that matcher runs `pre-commit-gate.sh` and
   `pre-push-main-blocker.sh` — **neither of which reads file contents**. So a secret that arrives
   by any route other than the agent typing it into a `Write` (a shell heredoc, a generated file, a
   `.env` copied in, a file written before the hook existed) reaches your commit with nothing having
   looked at it. This is the same bug shape as Row 1's origin: *the protection was attached to the
   wrong door.*
3. **Test files are exempt outright.** `is_test_file()` returns before the scan for `test_*.py`,
   `*_test.py`, anything under `tests/`, `*.test.ts`, `*.spec.tsx`. The exemption is defensible —
   test fixtures are full of fake keys and an `ask` on every one of them would get the hook switched
   off — but it means *"the repo scans for secrets"* is false for a whole directory tree, and it was
   never stated next to the claim.
4. **12 regexes are a list, and lists end.** Same lesson as Row 1 leak 3. A base64 blob, a key split
   across two string literals, an unlisted vendor's format, or a credential assembled at runtime is
   invisible. And the generic pattern cuts the other way too: `password = "correct-horse-battery"`
   in a docstring will `ask`, so the noise is real.

**What would actually be a gate.** A content scanner in the pre-commit hook (`gitleaks`,
`git secrets`) reading the **staged diff**, which is the only place the whole commit is visible.
That does not exist in this repo. This row says so rather than leaving the gap to be discovered.

> ### ⚠ Owed — the false sentence was fixed in 1 repo of 5
>
> The correction landed in this template's `.claude/rules/security_baseline.md`. The **verbatim**
> original line is still live in all four derived projects. Measured read-only 2026-08-08 with
> `grep -n "12 secret patterns" <repo>/.claude/rules/security_baseline.md`:
>
> | Repo | Line |
> |---|---|
> | `agentic_journal` | 19 |
> | `VerificationPortal` | 24 |
> | `howie_family_wiki` | 18 |
> | `dan_research_karpathy_wiki` | 24 |
>
> **The table lives here and not in the rule, and that is not a filing preference.** The first
> attempt put it inside `.claude/rules/security_baseline.md` — where the correction is — and
> `tests/test_template_neutrality.py` went **red** on it: `.claude/rules/` is CORE and propagates
> verbatim, so naming a specific project in it would ship a hub-only survey into every downstream
> repo. The rule now carries the *obligation* in project-neutral form (plus a `grep` a reader can run
> on their own copy) and points here for the measured detail. Worth noting as a live example of a
> guard doing its job on this very change, four minutes after being written about.
>
> Those repos were outside this change's write scope, so this is recorded as a **propagation-slice
> obligation** rather than left to be rediscovered. It matters more than the equivalent note in Row
> 5: Row 5's bookkeeping is for a mechanism no project has ever switched on, while this one is the
> mechanism with the widest blast radius — four teams currently hold a written guarantee that
> secrets cannot reach their commits. When propagating, **re-measure each repo's own
> `validate_tool_use.py` first**: the pattern count and the `ask`/`deny` decision are per-repo
> facts, and pasting this row's numbers without checking would repeat the original error in a new
> place.
>
> **Also owed, in this repo:** `docs/FRAMEWORK_SPECIFICATION.md` was not synced when the rule
> changed, though the `syncing-framework-docs` skill fires on `.claude/rules/` edits. Its
> secret-detection sections — `:574`, `:642`, `:1086` — all describe *what is scanned* and none of
> them says the decision is `ask` rather than `deny`. `:708` mentions it, but only as an open risk
> item (R2, "uses `ask` instead of `deny`"), which reads as a proposal for the future rather than a
> description of today. The `ask`/`deny` half is the misleading half; the spec currently states
> only the other one.

**One-sentence explain-back you should be able to give:** *"If I type an API key into a source file,
a hook matching 12 patterns will pause and ask me about it — that's all it does. It doesn't block,
it's attached to file writes rather than to commits so it never sees `git commit` at all, it skips
every test file, and it only knows 12 shapes. So nothing in this repo stops a secret being
committed; the honest claim is that it catches the careless paste into `src/`, and if I want a real
gate it has to read the staged diff in the pre-commit hook, which we have not built."*

---

## Row 4 — Regression-ledger guard verification

*(`scripts/quality_gate.py` → `check_regression_ledger`; mechanism pre-existing, verification added
2026-08-07)*

**What it claims to stop.** A fixed bug coming back. `memory/bugs/regression-ledger.md` is a table:
each row names a bug, the file it was in, the test file that now guards it, and **the test function**
that does the guarding. The quality gate reads that table and is supposed to check the guards are
really there.

**What it actually checked until 2026-08-07: the filename.** The parser read the Test Function
column into its entry dict — and then no line of code ever read that value. Only
`test_file.exists()` was checked. So **deleting the named guard function, while leaving the file in
place, passed the gate silently.** The ledger's entire promise rested on a file continuing to exist,
which is the one thing that survives almost any edit.

This is worth sitting with, because the defect is not a missing feature — it is a value that was
carefully parsed, stored, and then ignored. The code *looked* like it verified functions.

**What it does now.** For each row it extracts the pytest identifiers named in the Test Function
cell and requires each to be **really defined** in the named file as a `def` or a `class`. Severity
is split on purpose:

| Finding | Verdict | Why |
|---|---|---|
| Guard defined in a **different** test file | **WARN** | The guard was *found*, so it demonstrably still runs; only the bookkeeping is stale. Turning that red blocks the build for a defect that costs nothing at runtime. |
| **No function or class of that name is defined anywhere under `tests/`** | **FAIL** | This fires on a guard that was **deleted** *and* on a guard that was **renamed**, and the check cannot tell them apart. It means "the ledger names something that no longer exists — go look", not "the protection is gone". |
| Named test file missing | **FAIL** | Unchanged from before. |

**Read the red verdict literally, because that is the part that bit.** The check knows one thing:
whether a `def`/`class` with that exact name exists. Deletion and rename are *the same observation*
from where it stands — a rename leaves nothing behind for it to follow. So the honest sentence is
"this name is defined nowhere", and everything past that is a human's job. It is still right to go
red: a ledger row pointing at a name nothing defines needs a person to look at it. What is not right
is telling that person the protection is absent, because it may well be running under another name.

**A definition, not a mention — and why that cuts both ways.** A substring search would not do, and
the reason is a real case in this repo: `test_no_slug_or_env_leak_on_no_db_path` still appears in
`tests/test_dashboard_server.py` — inside a **docstring** recording that the test was migrated and
renamed. Any check matching text would have called that guard present. Only a `def`/`class` binding
counts. But notice what that same docstring *is*: the surviving evidence of a rename. Refusing to
read it is correct (prose is not a guarantee) and is exactly why a rename is invisible here. The
strictness that makes the check trustworthy is the same strictness that makes its red ambiguous.

**Where it leaks — say these whenever you say the rest.**

1. **It proves a function exists, not that it guards anything.** A test named `test_guard_holds`
   whose body is `assert True` passes this check completely. The link between the bug and the test
   is a human claim in a table; this only stops the claim from pointing at nothing.
2. **A rename is indistinguishable from a deletion**, and both go red. This is the leak with actual
   evidence behind it — it is the *only* thing the check has ever found here (see below). A guard
   that is renamed, or moved into another file under a new name, vanishes from this check's view
   entirely, and the red it produces reads like lost protection when it is stale bookkeeping. Do
   not skip this one when you explain the row: it is the failure mode you will actually meet.
3. **The cell is prose, so the parse is deliberately conservative.** Ledger cells carry parenthetical
   asides ("(also `test_x` in tests/test_other.py)"). Those are dropped rather than parsed — a
   looser variant (keep parentheticals, drop the identifier filter) was measured on 2026-08-07
   producing **19** not-found hits of which **18** were prose fragments (`also`, `in`, `and`, and
   bare paths like `tests/test_dashboard_server.py`) and exactly 1 a real identifier. A check that
   invents red gets switched off.

   **The cost, as a number, because this document's standard is numbers.** Measured 2026-08-08 on
   this repo's ledger: **12 guard identifiers across 4 ledger rows are named only inside a
   parenthetical**, against **298** that are verified — so **310 named, 298 checked, 12 invisible
   (3.9%)**. The hole is live, and it is currently costing nothing: all 12 were separately confirmed
   to be really defined under `tests/`, so there is no guard hiding in the blind spot **today**.
   Both halves of that matter — "the parse skips some" is the design, "none of the skipped ones is
   missing right now" is the state, and only the second one expires. Re-measure with:

   ```bash
   python - <<'PY'
   import re, sys; sys.path.insert(0, "scripts")
   import quality_gate as q
   entries = q._parse_regression_ledger()
   strict = paren_only = 0
   for e in entries:
       cell = e["test_function"]
       kept = q._parse_guard_names(cell)
       strict += len(kept)
       inside = [s for a in re.findall(r"\(([^)]*)\)", cell)
                 for t in re.split(r"[;,\s]+", a)
                 for s in re.sub(r"\[.*?\]$", "", t.strip()).split("::")
                 if s and q._LEDGER_GUARD_IDENT.match(s)]
       paren_only += len({n for n in inside} - set(kept))
   print("verified:", strict, "| parenthetical-only, unverified:", paren_only)
   PY
   ```
4. **`--skip-regression` turns the whole thing off**, and the ledger is a hand-maintained file: a bug
   fixed without an entry is invisible here. This checks the table against the code; nothing checks
   reality against the table.

**Measured on this repo the first time it ran** (2026-08-07): 59 ledger entries, **298 guard
identifiers** checked, **9 misfiled** (right guard, wrong file — WARN), and **1 name defined
nowhere** — which turned out to be a rename, not a missing guard:

- `memory/bugs/regression-ledger.md:47` names `test_no_slug_or_env_leak_on_no_db_path`.
- No `def` of that name exists anywhere under `tests/`, so the gate goes **red**.
- The protection it describes (spec C2: the ntfy topic slug must never reach stdout/stderr) **is
  still running**, in `tests/test_dashboard_server.py` as
  `test_main_render_static_missing_db_no_file_no_browser_no_slug` — marked `@pytest.mark.regression`,
  docstringed *"Migrated from the retired legacy CLI test `test_no_slug_or_env_leak_on_no_db_path`"*,
  and asserting `"secret-slug-do-not-print" not in (captured.out + captured.err)` — the identical
  property.

So the first thing the fixed check ever found is **one stale ledger row for a renamed-and-migrated
guard whose protection still runs** — a real defect in the ledger, correctly flagged, and *not* a
missing test. An earlier draft of this row called it "1 genuinely missing … a true positive", which
is the mistake this whole file exists to catch: it would have been explained back fluently and been
wrong about the one case anybody will ever look at.

> ### ✅ Resolved 2026-08-08 — the blocker this row disclosed has been cleared
>
> **This block previously read "⚠ Open blocker — this check is currently holding the commit path
> red".** It is kept, rather than deleted, because the disclosure and its resolution are the same
> story: the check found a real stale ledger row, a human applied the one-line edit, and the gate
> went green on it. Deleting the record would leave the row reading as though nothing had ever been
> caught.
>
> What was owed: *in `memory/bugs/regression-ledger.md` line 47, replace
> `test_no_slug_or_env_leak_on_no_db_path` with
> `test_main_render_static_missing_db_no_file_no_browser_no_slug`.* That edit has been applied
> (`git diff memory/bugs/regression-ledger.md` shows exactly that one substitution, and nothing
> else).
>
> Measured 2026-08-08 against the live tree — `python -c "import sys; sys.path.insert(0,'scripts');
> import quality_gate as q; print(q.check_regression_ledger())"`:
>
> - **`PASS Regression ledger (298 guard(s))`**, function returns `True`. The regression check is no
>   longer red.
> - The finding dropped from FAIL to WARN exactly as the 2026-08-07 scratch measurement predicted
>   (`ledger says tests/test_telemetry.py, actually in tests/test_dashboard_server.py`), taking the
>   misfiled count from **9 to 10**. A prediction made from a scratch copy and then confirmed
>   against the real tree is the strongest single piece of evidence in this row.
>
> Correcting the Test File column as well is optional bookkeeping that would clear that WARN too.
>
> **Scope of this "resolved".** It says the *regression-ledger check* passes. It does not claim the
> whole gate is green: this tree is being edited by several concurrent workstreams, so
> `python scripts/quality_gate.py`'s overall exit code is a fact about the tree at the moment you
> run it, not a fact about this row. Run it yourself before committing.
>
> **The instruction that still stands: do not resolve a ledger red with `--skip-regression`.** The
> check just did its job. This one was cleared by fixing the ledger, which is the only way it should
> ever be cleared.

**How it was proved to actually fail.** In a scratch copy (`tmp_path` — nothing written into the
repo): a ledger entry plus its test file, guard present → green; the **same file with the guard
function deleted** → red with `Undefined guard: test_guard_holds`. Then the shipped code was mutated
and the whole `tests/test_quality_gate.py` suite re-run — measured 2026-08-07 against a 163-passing
baseline:

| Mutation | Result |
|---|---|
| Restore the never-read-the-function behaviour | **5 failed**, 158 passed |
| Turn the definition check back into a substring search (`return name in source`) | **2 failed**, 161 passed |
| Restore the old overclaiming failure text (`Missing guard: … not defined anywhere`) | **2 failed** |

*A test that stays green when you break the thing it guards is not evidence.* The third row is worth
noticing: the wording is now pinned by a test, because on this mechanism the wording **was** the
defect — the code was already right.

**One-sentence explain-back you should be able to give:** *"Every fixed bug is supposed to have a
named test that stops it coming back, and the gate is supposed to check that. It was only checking
that the test **file** existed — so you could delete the guard function itself and stay green. It now
checks the function is really defined: it warns if the guard turns up in a different file, and goes
red if no function of that name exists anywhere. Red does **not** mean the protection is gone — it
means the ledger names something that no longer exists, and a rename looks exactly the same as a
deletion from where the check is standing. That is not theoretical: the one thing it has ever caught
here was a renamed test whose protection is still running under its new name. And it still cannot
tell me whether the test tests anything — an empty test with the right name passes."*

---

## Row 5 — The debt baseline, and who is allowed to grow it

*(`scripts/quality_gate.py` → `_baseline_write_plan`, `config/gate_baseline.json`; row added
2026-08-07)*

**What it is for.** When the framework is applied to a repo that already has lint and formatting
debt, a gate that goes red on day one gets switched off. The baseline records existing debt as
fingerprints; those findings **warn**, while any **new** finding still fails red. It makes the gate
adoptable without making it meaningless.

**Read this before anything else in the row: the file has never existed.** Measured 2026-08-07 and
re-measured 2026-08-08 — `config/gate_baseline.json` is absent from this template *and from all four
derived projects*. So **no recorded debt has ever been compared against** — which is exactly why the
next paragraph mattered enough to fix.

> **Correction, 2026-08-08 — and it is the fourth time this file has caught itself.** The two
> sentences that used to sit here read: *"With no baseline file the format and lint checks take
> their ordinary path, so the comparison function `_check_against_baseline` has never run outside
> its own tests. This is a shipped, specified, tested, and entirely unexercised mechanism."* The
> first half is true **only for an ordinary run**. `quality_gate.py` collects fingerprints whenever
> `baseline or args.rebaseline`, and having them routes format *and* lint through
> `_check_against_baseline` — so **`--rebaseline` on a repo with no baseline file runs the
> comparison**, against an empty set, and prints every finding as "N NEW finding(s) not in baseline"
> when there is no baseline at all. Same RED verdict as ordinary lint; misleading words.
>
> Two things make this worth reading rather than just fixing. First, `--rebaseline` is *the one
> invocation this entire row is about*, so the row was most wrong exactly where it was most load-
> bearing. Second, **the contradiction was already sitting in the row's own evidence**: the CLI test
> celebrated four paragraphs below, `test_rebaseline_through_main_creates_no_baseline_file`, asserts
> `exit 1` with the comment *"still RED"* — an outcome only reachable through the comparison this
> paragraph said had never run. Nobody had to find new information; someone had to read the test
> against the prose. That is now the cheapest available check on any row here.
>
> Both halves are pinned at the CLI by
> `tests/test_quality_gate.py::TestWhichPathRunsWhenNoBaselineFileExists`, which spies on
> `_check_against_baseline` and asserts it runs with `--rebaseline` and does **not** without.
> Mutation-proven in a scratch copy: making the old prose true (collect fingerprints only when a
> baseline file exists) → 2 failed; making the comparison always run → 1 failed.

Re-check it with the command that actually covers the claim. An earlier draft of this row said
"re-check with `ls config/gate_baseline.json`", which only ever looks at **one** of the five repos
the sentence above is about — a verification command that does not verify what it is attached to, in
the document whose entire thesis is that re-runnable measurement beats memory. Run this instead,
from the directory holding all five checkouts (`C:/Work/AI` on this machine):

```bash
for r in "AI Gen Framework Research/agent_framework_template" agentic_journal \
         VerificationPortal howie_family_wiki dan_research_karpathy_wiki; do
  printf '%-58s ' "$r"
  ls "$r/config/gate_baseline.json" >/dev/null 2>&1 && echo PRESENT || echo ABSENT
done
```

Measured 2026-08-08: **ABSENT in all five.**

**The consent rule was protecting a phantom, and it was not a rule.** Growing the baseline means
changing what the gate accepts — the agent's own pass/fail criterion, a reward-function surface
under the Prime Objective's rule that enforcement is human-mediated at every gate. The protection
was `--rebaseline`'s help text: *"DEVELOPER-CONSENT ACTION: the
agent must never run this autonomously."* Meanwhile `main()` called `_write_baseline(current_fps)`
the moment the flag appeared. **The only thing between an autonomous agent and re-cutting its own
success criterion was a sentence, inside the tool, asking it not to.** A rule addressed to the actor
it is meant to bind, enforced by nothing, is not a control — it is a note.

**Why the obvious fix does not work, and this is the useful part.** The natural instinct is "prompt
for confirmation — an agent has no terminal, so it will be refused." That was **measured and it is
false**: `sys.stdin.isatty()` returns `True` inside this agent's own `Bash` *and* `PowerShell`
tools. A TTY check would have refused nobody and read, in the write-up, exactly like a control.
*The assumption that would have shipped a decorative guard was one command away from being tested.*

**What was done instead.** The consent is now a property of the code rather than a request:

- `_baseline_write_plan` is the **single** decision point for every baseline write, and every set it
  returns is a **subset of the baseline that already exists**. No flag, and no combination of flags,
  can make the gate add a fingerprint.
- `--fix` / `--shrink-baseline` ratchet **down** only.
- `--rebaseline` **proposes**: it prints the exact file a developer would have to commit, and writes
  nothing.
- Growing the baseline therefore means a human committing `config/gate_baseline.json` — and
  `check_review_existence` treats that path (and `config/gate_profiles.yaml`) as a code change
  requiring a same-day `/review`.

**And then this row did the same thing the four rows above it were written about — read this, it is
the most useful paragraph in the file.** The fix was real: `main()` genuinely stopped writing. But
the fix *also deleted* the only test that drove `--rebaseline` end-to-end through `main()`
(`test_rebaseline_writes_notice_and_log_flag`, which asserted the old "writes the baseline"
contract) and replaced it with unit tests on the pure helper `_baseline_write_plan`. Those helper
tests are good — they cover all 8 flag combinations, which one end-to-end run cannot. But the
guarantee in the bullet above is a claim about **`main()`**, and after the swap `main()`'s
`--rebaseline` branch was executed by **zero** tests: `grep -n '"--rebaseline"' tests/*.py` returned
nothing.

A reviewer proved the consequence rather than arguing it. In a scratch copy of the tree he restored
the literal pre-fix defect — `_write_baseline(current_fps)` immediately after
`_print_baseline_proposal(current_fps)` in `main()` — and ran the suite: **163 passed, exit 0.** The
guard had been moved out of a test and into a docstring. That is precisely the rule stated one row
above (*"a test that stays green when you break the thing it guards is not evidence"*), broken by
this row, in the same change, on the same day. **Three times now** this file has caught its own
write-up overstating its own code; the drift is not a thing that happened to old prose.

**What the guarantee rests on now** (added 2026-08-08): a CLI-level class,
`tests/test_quality_gate.py::TestRebaselineWritesNothingThroughMain`, which drives the real `main()`
with real `argv` inside a `tmp_path` sandbox — `GATE_BASELINE_FILE` is repointed, so even a
reintroduced write lands in tmp and never in the repo. Three tests: no baseline file is created from
nothing; an existing baseline stays **byte-identical**; and all 8 flag combinations run through
`main()`, asserting both that the on-disk baseline never becomes a superset of what was there before
**and** that the four `--rebaseline` combinations leave the file byte-identical. Each also asserts
the proposal actually printed, so none can pass vacuously by never reaching the branch.

Mutation-proven the way Row 4 requires — defect restored in a **scratch copy** of the tree, nothing
written into the repo, full `tests/test_quality_gate.py` re-run each time:

| Tree | Result |
|---|---|
| Pristine scratch copy | **173 passed**, exit 0 |
| **M1**: `_write_baseline(current_fps)` restored after `_print_baseline_proposal(current_fps)` in `main()` | **7 failed**, 166 passed, exit 1 |
| M1, with the CLI class deselected (`--deselect …::TestRebaselineWritesNothingThroughMain`) | **1 failed**, 166 passed, exit 1 |
| M1 against the pre-2026-08-08 tree (the critic's original measurement) | **163 passed**, exit 0 |
| **M2**: `if rebaseline: return None` deleted from `_baseline_write_plan` | **4 failed**, 169 passed, exit 1 |
| **M5**: fingerprints collected only when a baseline file exists (i.e. the retracted prose made true) | **2 failed**, 171 passed, exit 1 |
| **M6**: fingerprints always collected (comparison always runs) | **1 failed**, 172 passed, exit 1 |

The third row is the load-bearing one, and **its meaning changed between 2026-08-08 measurements —
which is itself the finding.** It first read "165 passed, exit 0 — *nothing else in the suite
notices*", the sharpest evidence that the CLI class was carrying the guarantee alone. Re-run after
`TestWhichPathRunsWhenNoBaselineFileExists` was added, it is 1 failed: that class asserts no baseline
file is created and so independently catches M1. The guarantee is now doubly held, and the earlier
sentence is retracted rather than left standing. **The number of tests that catch a mutation is a
measurement with a shelf life** — re-run it before quoting it, exactly like every other figure here.
(The pre-2026-08-08 row still reconciles: 163 + 2 helper cases + 6 CLI cases + 2 path cases = 173.)

**M2 was found while writing this row, and it is the same lesson one notch finer.** "Cannot GROW the
baseline" and "writes NOTHING" are two different guarantees, and this row's own bullets make both.
Deleting the `--rebaseline` veto from the helper leaves the first intact — the plan falls through to
`baseline & current`, which is a *subset* — while breaking the second: `--rebaseline
--shrink-baseline` would write. On the first pass **nothing caught it**: 171/171 green, because the
existing helper test only ever passed a `current` containing new debt, where the plan is `None` for
an unrelated reason. Both classes were tightened (the helper test now parametrizes `current` over
new-debt / resolved-debt / all-resolved; the CLI test asserts byte-identity, not just non-growth),
and M2 now fails 2 tests in each. *A test can be about the right thing and still pass for the wrong
reason.*

**Where it leaks — this is not a wall.**

1. **The agent can still write the file directly.** Nothing at the filesystem level stops a `Write`
   to `config/gate_baseline.json`. What stops it is the review gate on that path plus a diff of
   sorted, human-readable fingerprints. What was removed is the *sanctioned one-flag route* and the
   gate's own ability to grow its baseline.
2. **`--skip-reviews` exists**, so the review gate that now carries the consent is itself bypassable
   from the command line (though not from the `git commit` hook — see CLAUDE.md's Known
   Limitations).
3. **It guards a mechanism nobody has switched on.** Until some project actually commits a baseline,
   this row describes a control over an unused path. That is stated rather than left implied.
4. **The disproven consent model is still taught in several live places.** An earlier version of this
   leak named two of them; the table below has five. **Both figures are counts of *instructional*
   carriers, and the row previously attributed them to a command that does not produce them** — a
   third corrected-evidence-command defect in this file, so it is fixed in place rather than
   swapped. `grep -rn "rebaseline" --include="*.md" .` excluding `discussions/` returns **63 hits
   across 15 files** (measured 2026-08-08, after this round of edits), because it also sweeps up *dated records* — reviews,
   handoffs, the regression ledger — which correctly state what was believed on their own date and
   must not be rewritten. Filter those out and read what is left:

   ```bash
   grep -rln "rebaseline" --include="*.md" . \
     | grep -vE "^\./(discussions|docs/reviews|docs/handoff|memory)/"
   ```

   Measured 2026-08-08: **10 files** — the 5 instructional carriers tabled below, plus five that
   are *not* carriers and are listed so nobody re-audits them: `docs/CAPTURE_PIPELINE.md` (names the
   log **field**, makes no consent claim), this file, `docs/adr/ADR-0031-…` (immutable, and already
   hedged "*audit trail today*"), `docs/sprints/PROPOSAL-20260806-…` (cites `--rebaseline` as the
   name of the defect *class*), and `docs/sprints/SPEC-20260805-210524-…` (which already **corrects**
   the lock claim: "*`--rebaseline` is not a lock*"). **Read the hits; do not count them** — and note
   that editing *this* file moves the hit count, so re-measure rather than inheriting 63.

   | Carrier | Line | What it still says | Status |
   |---|---|---|---|
   | `.claude/skills/testing-playbook/SKILL.md` | 126–127 *(pre-fix)* | "`--rebaseline` is a developer-consent action the agent must never run autonomously" | **FIXED 2026-08-08** — corrected text in the "Debt baseline" bullet (`:122–147` as of this edit); the retraction is stated in place so the old wording is not simply deleted. Locate it with `grep -n rebaseline`, not by line |
   | `CLAUDE.md` | 47 | "**`--rebaseline` is developer-consent only — the agent must NEVER run it autonomously**" | **still live** |
   | `docs/sprints/SPEC-20260716-233400-…` | 96–97, 179–180 | AC3: "`--rebaseline` **writes** the new baseline"; "the agent must never run `--rebaseline`" | **still live** |
   | `BUILD_STATUS.md` | 142 | "CLAUDE.md gate section (+ NEVER-run-`--rebaseline` invariant)" | **still live** |
   | `docs/adr/ADR-0032-…` | 1428 | "creating it is `--rebaseline`, a **developer-consent action the agent must never run**" | **must NOT be edited** — ADRs are immutable under Principle #4 ("ADRs are never deleted"); an ADR is superseded with a reference to its replacement, never rewritten |

   The one that mattered most was the skill, because it is the artifact addressed to **derived
   projects** — a developer reading it would have explained the mechanism back fluently, in the
   framework's own words, and been wrong. That is the failure this whole file exists to prevent, and
   it was sitting inside the change that was fixing the identical failure elsewhere. The remaining
   live carriers are recorded here with line numbers so the propagation slice can clear them rather
   than rediscover them.

   Re-measure before acting; line numbers rot:
   `grep -rn "rebaseline" --include="*.md" . | grep -v "^./discussions/"`.

**One-sentence explain-back you should be able to give:** *"The debt baseline is the list of existing
problems the gate agrees to only warn about, so growing it is the agent editing its own pass mark.
The rule said that needed my consent, but the rule was only a sentence in the tool's help text while
the code wrote the file on request — and the file it was protecting has never existed in any of our
five repos. Now the gate can only ever shrink that list; `--rebaseline` just prints what I'd have to
commit myself, and committing it needs a review. And I know that's still true today rather than
just believing it, because tests actually run the flag through the real command line and go
red if the write comes back — which is the part the first version of this fix got wrong: it deleted
the only test of the flag and left the promise sitting in a comment. One thing I'd have got wrong
until yesterday: I'd have said the comparison code never runs because we have no baseline file. It
does — `--rebaseline` runs it against an empty list, and calls everything it finds 'new, not in
baseline' when there is no baseline. It's still not a wall — the
agent could write the file like any other file — but the gate can no longer grow its own baseline,
and I checked that an 'are you a human at a terminal?' prompt would have caught nobody, because the
agent's shell reports a terminal."*

---

## Row 6 — The education gate (the one that is NOT enforced)

*(`docs/education/gates.yaml` + `scripts/education/gate_registry.py`, ADR-0029; row added
2026-08-07)*

This row is here because a claim was **removed** from a config file, and a removal leaves nothing
behind to explain.

**The claim that was false.** `config/gate_profiles.yaml` listed "education gates" among the
framework-integrity checks that "run unconditionally in every profile". `main()` runs eleven checks
— eight that can turn the gate red plus three that only warn — and **none of them is an education
check**. Anyone reading that config comment would have concluded the framework enforces the
education gate (Principle #5) at the quality gate. It does not enforce it anywhere.

**How to verify that yourself — and a caution about the command this row used to give.** The
original wording was: *"Measured: `grep -n -i education scripts/quality_gate.py` returns **only**
`--cov` / `--include` path arguments for coverage."* That is **no longer true, and it was the same
change that broke it**: the honest paragraph added to `quality_gate.py`'s module docstring contains
the word "education", as do two later comments. The evidence command was invalidated by the prose
written to fix the same claim — a small, perfect specimen of what this document is about, so it is
corrected here rather than quietly swapped.

**And then the correction rotted too, within a day.** The replacement recorded "**10 hits, 3 of them
prose**" at lines `:944` and `:1042`. Re-measured 2026-08-08 after the next round of edits to the
same file: **11 hits**, and both line numbers are wrong (the prose now sits at `:27`, `:993`,
`:1091`). Nothing was reverted — the file simply grew. **A count and a line number are the two most
perishable things you can put in a row**, so state the *decomposition* instead, which survives the
file moving underneath it:

```bash
grep -ci education scripts/quality_gate.py                              # total
grep -i education scripts/quality_gate.py | grep -c  "scripts/education" # coverage args
grep -i education scripts/quality_gate.py | grep -vc "scripts/education" # prose
```

Measured 2026-08-08: **11 total = 8 coverage-path arguments + 3 lines of prose saying there is no
education check.** If the third number ever exceeds the second, that is prose growth, not a gate.

Grep for the *checks the gate actually calls* instead, which is what the claim is really about:

```bash
grep -nE "\bcheck_[a-z_0-9]+\(" scripts/quality_gate.py | grep -v ":def "
```

Measured 2026-08-08: **15 call sites → 11 distinct checks** — `check_formatting`, `check_linting`,
`check_tests`, `check_coverage` (or `check_profile_command` standing in for any of the four),
`check_adrs`, `check_review_existence`, `check_regression_ledger`, `check_layer1_integrity` (the
eight that can go red), plus `check_build_status_freshness`,
`check_subscription_fee_not_staged`, `check_promotion_backlog` (the three advisories). **No
education check appears in that list**, which is the claim, stated as something a reader can falsify
in one command.

**What actually exists.** Principle #5, “Understanding before merge” (walkthrough → quiz →
explain-back → merge), is a **human
discipline**, plus bookkeeping for the times it is skipped: `docs/education/gates.yaml` records
*deferred* gates, and `scripts/education/gate_registry.py` lists / adds / clears / re-defers them.
ADR-0029 is explicit that adding a gate to that registry is a **required manual step**. So:

- Nothing fails if an education gate is skipped.
- Nothing **warns** either.
- Nothing notices. The registry only knows about deferrals somebody chose to write down.

**Why it was not simply implemented.** Adding a check that reads `gates.yaml` and warns on open
gates is a small piece of code and a large governance change — it would turn a human learning
obligation into a build condition. That needs its own `/plan` and a Steward gate, not a quiet
inference from a stale config comment. The honest interim state is: **the claim is withdrawn, the
gap is named, and the decision to close it belongs to a human.**

**Where it leaks.** Everywhere — that is the point of the row. The one thing that does work is that
open deferrals are *queryable* (`python scripts/education/gate_registry.py list --status open`), so
the debt is visible if you look. Visibility that depends on somebody choosing to look is the weakest
class of control in this file, and it is the only one operating here.

**One-sentence explain-back you should be able to give:** *"The education gate is the rule that I get
a walkthrough and have to explain the change back before it merges. It is enforced by us, not by the
tooling — the quality gate has no education check at all, despite a config comment that said it ran
in every profile. What exists is a registry of gates we deferred, which somebody has to add to by
hand, and I can list the open ones. So if we skip an education gate, nothing anywhere will object."*
