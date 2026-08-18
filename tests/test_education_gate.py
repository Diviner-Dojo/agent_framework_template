"""Pins the education gate's rebuilt contract: one Bloom ratio, a real re-teach loop.

Why this file exists
--------------------
Three live files disagreed about the education gate's Bloom's-taxonomy mix. The
framework **detected the disagreement on day one and then sat on it for 87 days**:

* ``.claude/agents/educator.md``      — 30% Understand/Apply, 70% Analyze/Evaluate
* ``.claude/skills/selecting-review-gates/SKILL.md`` — 60-70% / 30-40%
* ``.claude/commands/quiz.md``        — 60-70% / 30-40%

``/quiz`` is the command that dispatches the educator, so the educator was being
*ordered to do the opposite of its own charter* — mostly shallow recall, which is
exactly the syntax-quiz register the developer objected to.

Dates measured, not estimated. Re-run them::

    git log -S "30% **Understand/Apply**" -- .claude/agents/educator.md
    #  -> 957b7a57bfb766976bf437fd38227a9d88f24bb0  2026-05-12

    sed -n '78,80p' docs/reviews/REV-20260513-051947.md
    #  -> 78: ## Other Advisories (lower priority)
    #  -> 80: 4. **Bloom's question mix contradiction** (qa). `educator.md` specifies
    #           30% Understand/Apply + 70% ... `review_gates.md` specifies 60-70% ...

``quiz.md`` has carried 60-70 / 30-40 since the initial release (2026-03-08,
``2bac3e2``) and the skill since 2026-05-20 (``1c4fe0c``); ``educator.md`` moved to
30 / 70 on 2026-05-12 without either consumer following, so the contradiction went
live that day.

**The framework's own review caught it the next day.** REV-20260513-051947 line 80
states the contradiction verbatim and proposes the exact disposition applied here —
and files it under "Other Advisories (lower priority)" (line 78). From 2026-05-13 to
2026-08-08 is 87 days, during which no review report carried the advisory forward.
A derived project independently re-surfaced it on 2026-07-18 (``agentic_journal``
DISC-20260718-235319, turn 2, "CONSTITUTIONAL DISCREPANCY SURFACED") and escalated
rather than resolved it — the second detection of an already-detected defect.

This matters more than the tidier "nothing noticed" story that an earlier draft of
this docstring told, and which had to be corrected. The failure mode is not blindness;
it is *sensing without acting*, which is the meta-finding this whole effort is named
after. Sharper detection would not have helped — a review, a derived project, and a
constitution check all fired. What was missing was something that stays failing until
it is fixed. That is what this file is: not a better sensor, a ratchet.

This is the third drift of this exact shape the effort has hit (the seven-principle
count, the handoff-cost restatement, this). The remedy is the same one
``tests/test_constitution_consistency.py`` uses: read the live files, extract the
claim, and fail when two copies disagree.

What a green run here actually means
------------------------------------
Green means all fourteen of these, and nothing more (the list said "eleven" while
carrying twelve entries; corrected here rather than left as a miscount in the file whose
whole subject is copies that stop agreeing):

1. **One ratio.** The three files that state the Bloom mix state the same one, it
   is the educator's 30/70, and each of them says out loud that the
   *within-session difficulty ramp* is a different rule from the *overall mix* —
   so a future reader does not "fix" one into the other.
2. **No unregistered fourth opinion.** No other live instruction file states a
   different mix. Two that currently do are registered as debt with their
   measured values (:data:`KNOWN_STALE_MIX`); a *change* to either, or a *new*
   file with a rival ratio, fails.
3. **The loop is instructed, not described.** The educator charter and both
   commands carry an imperative miss-branch (do not move on / re-explain from a
   different entry point / ask again / no turn limit), an enumerable set of entry
   points, and an explicit ban on the synonym-swap re-explanation.
4. **No celebrate-growth language** anywhere in the four files except inside a
   prohibition.
5. **Fault-tolerance did not become "everything passes".** The rubric still
   grades reasoning in the developer's own words *and* still states that
   correctness gates.
6. **Measurement did not get thinner.** Every capture call the old ``/quiz`` and
   ``/walkthrough`` made is still made, the CRITICAL BEHAVIORAL RULES survive, and
   the developer's verbatim answers now reach Layer 1 under the same
   ``tutor``/``learner`` vocabulary ``scripts/education/ingest_walkthrough_session.py``
   already locks.
7. **Every attempt reaches ``education_results``, not just the winning one** — and
   the two education paths write the same row semantics into that one table.
8. **The 0.70 threshold's two meanings stay apart.** Per item it is a recording
   convention; *in aggregate it really is a gate criterion* for the ADR-0029
   ingested-transcript path, which computes CLEAR-ELIGIBILITY on it — the flip to
   ``cleared`` being the developer's own clear, never the ingest's (ADR-0035). A
   gate file may say "not the gate" only with that scoping attached
   (:class:`TestPassThresholdSemantics`).
9. **The ``/walkthrough`` → ``/quiz`` handoff has a reader.** Everything Step 7 of
   ``/walkthrough`` emits, ``/quiz`` Step 2a takes in — including a Layer 1 fallback
   read path that is executed by this suite, not merely described
   (:class:`TestHandoffHasAnIntake`).
10. **The education-gate registry is not a one-way ratchet.** A file that instructs
    ``gate_registry.py add`` also PRESENTS the ``clear`` route — developer-run since
    ADR-0035, never agent-run (that ban is check 14) — with flags checked against
    the live CLI (:class:`TestGateRegistryIsNotOneWay`).
11. **No hub database snapshot is baked into a propagating file.** ``.claude/`` ships
    to derived projects, so "32 rows, pass rate 0.969" would be a false statement
    about *their* database and stale in this one by the next run
    (:class:`TestNoBakedHubMeasurements`).
12. **The paths-not-taken verification handoff has a reader.** ``/review`` Step 7
    writes it and Step 10 states the briefing agent's obligations against it; the
    education gate is that briefing agent and must consume it — with the five-term
    per-record vocabulary taken from :data:`verify_paths_not_taken.RECORD_STATUSES`
    rather than restated, a REFUTED claim surfaced loudly and blocking nothing, and
    an absent handoff degrading to one honest sentence
    (:class:`TestVerificationHandoffReachesTheGate`,
    :class:`TestRefutedIsLoudAndNotABlocker`,
    :class:`TestAbsentHandoffDegradesHonestly`).
13. **The seam's four arms actually work, not merely read as working.** Every refuting
    per-record status has its own prescribed treatment, not one treatment and three
    silences; all three of the reader's verdicts — ``UNVERIFIABLE`` included — cross the
    context boundary into the educator prompt; the `/quiz` fallback read path survives
    both Layer 1 event schemas and declares that it is unscoped; and the handoff locator
    reaches every report carrying the section, with the ``reviewed_files`` frontmatter
    the confirm step is told to check. Each of the four was measured broken, and the
    Principle #5 ratchet behind them was measured defeatable three ways.
14. **The developer closes the education gate — never the agent.** "I clear it"
    (ntfy, 2026-08-10) + "Yes, everywhere" (in-conversation, 2026-08-10; ADR-0035):
    no education surface may instruct the AGENT to run `gate_registry.py clear` —
    in every wording the detector has been measured against (the planted set below,
    including a critic's escape that used no clear/retire verb at all), NOT "any
    wording": the residual holes are named in the check-14 probes — while the
    PRESENTATION of the command to the developer stays legitimate. And the
    ingested-transcript route computes CLEAR-ELIGIBILITY, records the additive
    ``clear_eligible`` marker, and never invokes ``clear_gate`` on the automatic
    path (:class:`TestDeveloperClosesTheGate`, :class:`TestAutomaticPathNeverClears`).

Why check 7 exists (it is the veto, not a nicety)
-------------------------------------------------
An earlier draft of this slice instructed both surfaces to record only the
*terminal* post-loop state ("never the first attempt"). That is a measurement
regression, and a self-erasing one: the loop runs until the concept is
demonstrated, so a terminal-only row is a pass **by construction**. Both live
readers of the table print it as a trend: ``.claude/commands/retro.md`` and
``.claude/commands/meta-review.md`` each run an unfiltered
``SELECT bloom_level, … AVG(score), SUM(passed), COUNT(*) FROM education_results
GROUP BY …``. Their *labels* differ and the difference is not load-bearing —
meta-review.md:153 labels its block ``Education Trends``; retro.md:127 carries the
comment ``# Recent education results`` — so
:meth:`TestPerAttemptRecording.test_the_instrument_still_has_readers` pins the
substantive half (both name ``education_results``, both average ``score``) and not
the heading text. Either way the effect of terminal-only rows would have been a
permanently rising, permanently perfect education trend.

Measured, not assumed — but read this as a **dated hub snapshot, not a property of
the framework** (2026-08-09, read-only
``sqlite3.connect("file:metrics/evaluation.db?mode=ro", uri=True)``): 32 rows over 9
sessions, distinct scores ``[0.5, 0.8, 0.85, 0.9, 0.95, 1.0]``, pass rate 0.969,
per-Bloom AVG 0.944–1.0. The instrument still carried discrimination on that date, so
the loss would have been real. These digits live **here on purpose**: ``tests/`` is not
a propagating framework tier, while ``.claude/`` is, so the same sentence inside
``educator.md`` would ship to every derived project as a false claim about *their*
database and would be stale here by the next ``/quiz`` run. Nothing asserts these
numbers — the assertion is the opposite one, that no propagating file contains their
kind (:class:`TestNoBakedHubMeasurements`).

**Rule for whoever edits the four gate files next** (it lives here, not in them):
never transcribe a row count, a pass rate or a group count out of
``metrics/evaluation.db`` into ``.claude/agents/`` or ``.claude/commands/``.
``scripts/distribute/assessment.py::_INTERP_TIERS`` ships both tiers into every
derived project, so a baked figure becomes a false statement about *their* database.
``TestNoBakedHubMeasurements::test_no_propagating_file_bakes_a_database_snapshot``
fails if one appears, which is why the four files themselves no longer carry a
paragraph of authoring governance: a ratchet does not need to be restated as prose in
a file loaded into a tutor's context on every education dispatch. Same reasoning for
the review-facing justification that used to sit in ``quiz.md`` Step 5 and
``educator.md`` §2.7 — the argument for per-attempt rows is preserved above and in
:class:`TestPerAttemptRecording`; the *instruction* is what stays in the gate files.

Nothing had to change to keep it. ``scripts/init_db.py`` gives ``education_results``
an AUTOINCREMENT id and no unique key and ``scripts/record_education.py`` is a plain
``INSERT``, so multiple rows per concept were already legal — and
``docs/education/CONTRACTS.md`` §1.2 already **locks** the correct rule for the
sibling ingest path: "Both the missed original and the passing variant get their own
``education_results`` row (the miss is preserved in the record) … only terminal items
contribute to the quiz average."
:class:`TestPerAttemptRecording` pins both halves — that the instruction files say
it, and that ``scripts/education/ingest_walkthrough_session.py`` still implements it
— so the two paths cannot silently diverge into one table.

Green does **not** mean the tutoring is good. These are text assertions over
instruction files; they can prove a mechanism is *stated as an instruction*, never
that a model followed it. Three limits are worth naming:

* **The prohibition window (check 4).** A banned phrase is tolerated when a
  negation marker appears within :data:`_NEGATION_WINDOW` characters before it in
  the same markdown block. A deliberately perverse "never fail to celebrate
  growth" would pass. The regression actually being guarded — the
  ``- **Celebrate growth**: …`` bullet that shipped in ``educator.md`` until
  2026-08-08 — has no marker at all and fails.
* **Wording reach.** Every check below is satisfied by *any* of several phrasings
  (see the ``Requirement.any_of`` groups) so it survives a rewrite, but a
  sufficiently novel wording of the same violation can still slip through. The
  groups are drawn from how these files actually phrase the rule. **This is not
  hypothetical:** inserting "When he moves from confusion to fluency, tell him so
  out loud — that shift is worth marking." into ``educator.md`` — celebrate-growth
  framing using none of the 13 :data:`_PRAISE_PATTERNS` — leaves every test green.
  Measured 2026-08-09. Widening the patterns to catch it starts flagging the
  prohibition text itself, so the limit is disclosed rather than papered over.
* **Presence checks cannot see a contradiction added NEXT TO a retained rule.**
  Checks 3 and 5 assert a rule is *stated*; they do not assert nothing contradicts
  it. The realistic erosion of this loop is not deletion — it is a well-meant "let's
  not trap him" cap bolted on beside the ban. :class:`TestNoTurnCapContradiction`
  closes that one specific shape (a numbered attempt cap whose consequence is
  moving on) after it was demonstrated to slip past everything else; the general
  class — any contradiction phrased some other way — remains undetected.
* **The threshold-denial check (8) does not distinguish an assertion from a
  prohibition.** ``It is not the gate criterion`` and ``Never write "no gate clears
  on this number."`` both match :data:`_THRESHOLD_DENIAL`, so both must sit in a
  block that names which path is meant. That is deliberate — a bare prohibition
  with no scope teaches nothing — but it means the check counts a correctly-written
  warning as something needing scope, not as a violation avoided.
* **A file-level string check cannot see the context boundary on its own.** Probe 1
  below caught this suite lying: an early ``"prior session state" in text`` assertion
  measured green with the dispatch slot deleted, because the intake step's *heading*
  carried the phrase. Anything that must reach a subagent is now asserted on
  :func:`educator_dispatch_prompt`, the actual prompt string. Sibling assertions that
  still scan whole files carry the same latent weakness wherever a heading echoes the
  thing being pinned.

Mutation probes, each re-measured on 2026-08-09 against a 48-passing baseline. Each
was applied to one live file, ``pytest tests/test_education_gate.py -q`` was run, and
the file was restored and its md5 confirmed unchanged. Counts below are the observed
pytest output, not estimates:

* re-adding celebrate-growth *without* the word "celebrate" ("Say so warmly when he
  improves: nice work, you've come a long way.") → 1 failed, 47 passed;
  ``TestNoCelebrateGrowthLanguage::test_no_praise_framing_outside_a_prohibition``.
  Reworded violation, still caught.
* rewriting /quiz's Step 4 into grade-and-move-on ("Score each answer 0-1. Pass
  threshold 70%. Move to the next question.") → 4 failed, 44 passed
  (``test_loop_requirements_are_all_stated``,
  ``test_commands_name_entry_points_the_charter_defines``,
  ``test_quiz_restates_the_correctness_gate``,
  ``test_the_escalation_rule_is_not_caught_by_this_check``).
* reverting ``quiz.md`` to the old 60-70 / 30-40 mix → 1 failed, 47 passed;
  ``TestBloomRatioAgreement::test_all_three_files_state_the_same_ratio``.
* appending an attempt cap beside the retained "no turn limit" sentence ("After
  three attempts on one concept, record the score and move to the next question.")
  → 2 failed, 46 passed; both in :class:`TestNoTurnCapContradiction`. A reviewer
  measured this same mutation passing 37/37 against the version of this file that
  had no such class, which is why the class exists.
* restoring terminal-only recording ("Record the terminal state after the loop,
  never the first attempt") in ``educator.md`` → 1 failed, 47 passed; the same
  mutation in ``quiz.md`` → 1 failed, 47 passed. Both
  ``TestPerAttemptRecording::test_the_terminal_only_regression_is_not_reintroduced``.
* deleting the three-entry-point escalation rule from ``quiz.md`` → 1 failed, 47
  passed; ``test_the_escalation_rule_is_not_caught_by_this_check``. That guard
  exists so a future author cannot get green by deleting the legitimate rule the
  cap check has to tolerate.
* the wording-reach counter-example above (novel praise phrasing) → **0 failed, 48
  passed. NOT caught.** Recorded here because a guard's escapes belong next to its
  claims.

Probes for checks 8-11, run 2026-08-09 by the same method against a **69 passed, 1
skipped** baseline (the skip is :class:`TestGateRegistryIsNotOneWay` on
``educator.md``, which names the registry but invokes no subcommand). Each restored
file's md5 was re-confirmed:

* deleting the ``Prior session state`` slot from ``/quiz``'s ``Task(…)`` dispatch
  prompt → 1 failed, 68 passed;
  ``TestHandoffHasAnIntake::test_the_intake_reaches_the_dispatch_prompt``. **This
  probe failed to bite on the first attempt (0 failed, 68 passed)** and is why the
  assertion moved from the whole file to the prompt line; the weakness is disclosed
  above rather than quietly fixed.
* deleting the ``gate_registry.py clear`` *invocation* from ``/quiz`` Step 5 → 1
  failed, 68 passed;
  ``TestGateRegistryIsNotOneWay::test_the_documented_clear_flags_match_the_live_cli``.
  Note **which** check fired: the presence check
  (``test_a_file_that_opens_a_gate_also_closes_one``) stayed green because the
  surrounding prose still names ``gate_registry.py clear --help``. The flags check
  caught it instead, by noticing ``--session-id``/``--discussion-id`` no longer appear.
  Two overlapping checks, and the weaker one was the one that missed.
* re-baking the hub snapshot ("Measured … 32 rows, pass rate 0.969") into
  ``educator.md`` → 1 failed, 68 passed;
  ``TestNoBakedHubMeasurements::test_no_propagating_file_bakes_a_database_snapshot``.
* stripping the ingest-path scoping from the skill's threshold bullet → 1 failed, 68
  passed;
  ``TestPassThresholdSemantics::test_no_gate_file_denies_the_threshold_without_scoping_it``.
  (It was 2 failed against an earlier draft, before the skill grew a second paragraph
  naming the ingested-transcript path in its opening — so
  ``::test_the_scoping_is_actually_published_somewhere`` now survives this mutation,
  correctly: that check asks whether the distinction is published *anywhere* in the
  skill, and it still is. The two checks are deliberately at different altitudes.)
  The detector was **also** measured against the exact rejected sentence, planted in
  ``quiz.md`` in memory ("It is not the gate criterion and no gate clears or fails on
  it") → 2 hits. And it was measured to have been *vacuous* before
  :func:`unscoped_threshold_denials` moved onto ``claim_blocks``: over raw text it
  found 0 denials in a file that contains 1, because the sentence wraps.

Probes for check 12, run 2026-08-09 by the same method against a **97 passed, 1
skipped** baseline. Each mutation was applied with byte-level (not text-mode) I/O —
the tree is CRLF under ``core.autocrlf=true`` and a ``read_text``/``write_text``
round-trip rewrites line endings, which made an early restore fail its md5 check —
then reversed by re-editing, with the file's md5 re-confirmed identical afterwards.
No ``git checkout`` was used:

* deleting the WHOLE of ``/walkthrough`` Step 2a (the seam removed) → **15 failed, 82
  passed**, across all three new classes. That is the mutation this check exists for.
* renaming one status in the command only (``UNFALSIFIABLE`` → ``UNCHECKABLE``) → 1
  failed, 96 passed; ``test_the_status_vocabulary_is_the_checkers_own``. The list is
  compared against the imported ``RECORD_STATUSES``, so a rename on either side fails.
* removing the "``MECHANICALLY-CLEAR`` may never be taught as ``VERIFIED``"
  prohibition → 1 failed;
  ``test_mechanically_clear_is_never_promoted_to_verified``.
* dropping the handoff slot from ``/quiz``'s ``Task(…)`` prompt → 1 failed, and the
  same mutation on ``/walkthrough``'s prompt → 1 failed; both
  ``test_the_handoff_reaches_the_educator_dispatch_prompt``.
* rewording "Never taught as fact. Surface it first" into "Worth a mention" → 1
  failed; ``test_a_refuted_claim_is_surfaced_first``.
* **re-introducing the sentence the Steward struck** ("the education gate cannot be
  recorded complete while a REFUTED claim stands") → 2 failed;
  ``test_a_refuted_claim_leaves_the_gate_completable`` and
  ``test_no_gate_file_makes_a_briefing_non_completable``.
* deleting the honest-absence sentence from the absent-handoff arm → 2 failed;
  ``test_the_honest_sentence_is_prescribed`` and
  ``test_the_honest_sentence_lives_in_the_absent_arm``.
* removing one absent arm from the four (``NOT RUN``) → 1 failed;
  ``test_all_four_absent_arms_are_named``.
* making the locator print nothing when no report carries the section (the silent-skip
  failure) → 2 failed; making it raise on a missing ``docs/reviews`` (the crash
  failure) → 1 failed; making it inspect only the newest report → 1 failed. All
  ``test_the_locator_runs_on_every_arm``, which EXECUTES the documented snippet.

Three escapes are recorded here rather than papered over, and two of them shaped the
final guards:

* renaming the handoff heading in one prose *sentence* of ``/walkthrough`` while the
  locator block still searched for it → **0 failed, 97 passed. NOT caught.**
  :data:`SEAM_TERMS` is a whole-file presence check, so degraded prose beside a
  working mechanism passes. Judged correct: the mechanism is what carries the
  obligation across.
* deleting the honest-absence sentence when the check scanned the whole file → **0
  failed. NOT caught**, because Step 3's dispatch prompt quotes the same sentence as a
  legitimate slot value. Fixed by asserting on :func:`absent_subsection` and on
  :func:`without_dispatch_prompt` — the same "a heading echoes the thing being pinned"
  weakness this docstring already discloses, hit a second time.
* dropping ``/quiz``'s pointer at ``docs/reviews`` from its intake prose → **0 failed.
  NOT caught**, because the dispatch prompt still named it. Fixed by adding
  ``test_the_handoff_reaches_the_educator_dispatch_prompt``, which pins the half that
  actually crosses the context boundary.

Probes for check 13, run 2026-08-09 against a **117 passed, 1 skipped** baseline, by the
same byte-level method (each mutation applied with ``read_bytes``/``write_bytes`` so the
tree's CRLF survives, then reversed and the file's md5 re-confirmed identical; no ``git
checkout``). All fourteen were RED, and the suite returned to 117 passed afterwards:

* the three defeats a reviewer used against the literal-matching ``completion_blocks``,
  planted in the live files this time — the reword ("Hold the walkthrough open … only
  once the record has been rewritten"), the one-word variant ("is not recorded complete"),
  and the struck sentence in ``**bold**`` → 1 failed each,
  ``test_no_gate_file_makes_a_briefing_non_completable``. All three measured **97 passed,
  NOT CAUGHT** against the previous guard.
* removing the emphasis-stripping from ``completion_blocks`` → 1 failed,
  ``test_the_detector_catches_the_class_not_the_literal``. This is the root cause of the
  third defeat: the quotation-marker class used to contain ``*`` and `` ` ``, so any
  emphasis read as an opening quote and exempted the sentence.
* reverting ``named_statuses`` to ``status in text`` → 2 failed,
  ``test_named_statuses_matches_whole_tokens_only`` and
  ``test_every_refuting_status_has_a_teaching_treatment``.
* renaming the ``PHANTOM`` row out of the treatment table → 1 failed,
  ``test_every_refuting_status_has_a_teaching_treatment``. **This probe was GREEN on its
  first run** against a presence-only version of that check, because a later paragraph in
  the same subsection mentions ``PHANTOM`` while prescribing nothing for it. Fixed by
  :func:`refuted_treatments`, which requires a row or bullet naming exactly one status
  and carrying a prescription — the same "a mention is not a mechanism" weakness this
  docstring discloses twice above, hit a third time.
* deleting the ``UNVERIFIABLE`` slot from `/quiz`'s and from `/walkthrough`'s ``Task(…)``
  prompt → 1 failed each, ``test_all_three_reader_verdicts_cross_the_context_boundary``.
* reverting `/quiz`'s fallback snippet to ``ev['timestamp']`` → 2 failed, including
  ``test_the_fallback_read_path_reads_both_layer_one_schemas``, which runs the documented
  snippet over a tmp tree carrying one event of each Layer 1 schema.
* deleting the snippet's own scope caution → 1 failed; deleting the surrounding
  unscoped-limit prose → 1 failed. Both
  ``test_the_fallback_read_path_declares_that_it_is_unscoped``, which is why the limit is
  asserted in two places rather than one.
* restoring the locator's stop-at-the-first-carrier behaviour → 1 failed, and deleting
  its ``reviewed_files`` printing → 1 failed; both
  ``test_the_locator_reaches_every_carrier_not_only_the_newest``. **The second probe was
  also GREEN on its first run**: the assertion looked for the string ``reviewed_files``,
  which the locator's own banner contains. It now asserts the frontmatter *values*.
* removing the hard refuting statuses from `/quiz`'s instruction text → 1 failed,
  ``test_the_quiz_side_knows_a_refuted_record_is_not_question_material``. **Green on its
  first run too**, because the dispatch prompt still listed them: the whole-file scan was
  vouched for by the echo. It now reads :func:`without_dispatch_prompt`, and the prompt is
  checked separately by the boundary test.

Three of fourteen escaped their first attempt, and all three escaped the same way — a
check satisfied by an echo of the thing it was pinning. That is the dominant failure mode
of this whole file, and the count is recorded rather than smoothed over. All fourteen were
re-run RED against the final state (119 passed, 1 skipped).

Escapes from :func:`completion_blocks` that remain, measured rather than papered over:

* **The quotation exemption is a hole by construction.** "The Steward struck this, but the
  gate cannot be recorded complete anyway." → NOT CAUGHT, because ``struck`` sits within
  the 90-character window :data:`_QUOTED_DRAFT` searches. Repudiating a rule requires
  quoting it, so the hole is the price of letting the explanation survive; narrowing it to
  a quotation *mark* alone would flag the live prose that names the struck sentence.
* **Cap on carriers.** The locator prints the five newest reports carrying the section. A
  sixth, older carrier holding this change's handoff is unreachable — the failure this
  round fixed, one order of magnitude further out. Five was chosen to keep the output
  readable; if `/review` ever gains a scope field in the handoff block, match on that
  instead and drop the cap.
* **The legacy-schema crash was latent, not live.** The five ``created_at``-only events in
  ``discussions/`` carry the tags ``context-brief``, ``spec-review`` and
  ``synthesis``/``sealed`` — none of them a reteach tag — so the snippet does not raise
  against today's tree. It raises against any legacy event that does carry one, which is
  what ``test_the_fallback_read_path_reads_both_layer_one_schemas`` plants. The defect is
  real and reachable; it is not currently firing, and saying otherwise would overstate it.

Probes for check 14, run 2026-08-11 against a **128 passed, 1 skipped** baseline, by the
same byte-level method (``read_bytes``/``write_bytes``, restore verified sha256-identical,
no ``git checkout``); pytest exit codes were 1 mutated / 0 restored for all four:

* reverting `/quiz` Step 5 to the agent-directed "…the developer retires it — never you."
  → "…retire it." → 1 failed;
  ``TestDeveloperClosesTheGate::test_no_surface_instructs_the_agent_to_clear[quiz]``.
* appending "Retire the gate with ``gate_registry.py clear`` once done." to
  `/walkthrough` Step 7 → 1 failed; the same check on walkthrough.md. The detector's
  clause split earned its keep on this file's REAL pre-ADR-0035 sentence first: "… via
  ``gate_registry.py add``, not lost — and retired with ``gate_registry.py clear`` …"
  was measured NOT CAUGHT by a sentence-scoped exemption (the "not lost" clause's
  negation covered the retiring clause) and the unit was narrowed to the clause.
* planting "when the gate is paid, mark it cleared in the registry" into the educator
  charter → 1 failed; the same check on educator.md — a wording with no
  ``gate_registry.py clear`` literal in it, which is the reword class the detector
  exists for.
* reintroducing ``_reg.clear_gate(...)`` + ``save_registry`` on the ingest's
  clear-eligible branch → **3 failed**:
  ``TestPassThresholdSemantics::test_the_ingest_path_really_does_gate_on_the_threshold``
  (source complement), and both of ``TestAutomaticPathNeverClears``'s behavioral guards
  (gate flipped on a tmp registry; spy saw the call). These are LAYERED detectors, not
  three independent ones — a blind critic proved it by re-clearing through an alias
  (binding ``clear_gate`` under another name before the spy patched the original),
  which defeated BOTH the source grep and the spy; only the behavioral
  gate-stays-open assertion on the real tmp registry went red. The behavioral guard is
  the holding layer; the grep and the spy are cheap early tripwires that localise the
  failure, and a mutation that defeats them without moving the registry does not exist
  by construction (the registry file is the assertion).

REVISE-round probes, run 2026-08-11 against a green baseline by the same byte-level
method (sha256-verified restores; pytest exit 1 mutated / 0 restored on every row):

* the critic's verbatim escape ("execute the presented registry command yourself …
  release the parked gate … update its status to cleared") planted into `/quiz` Step 5
  → 1 failed, the check-14 scan on quiz.md. This text was measured NOT CAUGHT by the
  pre-widening detector — no clear/retire verb — and is why the
  release/update/set/write/paste/apply and status-to-cleared arms exist.
* an agent-directed bullet ("When the quiz ends well, retire the gate in the registry
  before reporting") planted into the review-gates SKILL → 1 failed, proving
  GATES_SKILL is now inside the scan (it joined CLEAR_SURFACES when its stale
  auto-clear descriptions were corrected).
* the ingest's ``mark_clear_eligible`` + save removed (eligibility back to ephemeral
  stdout) → **6 failed** across both behavioral guards and the ingest suite — the
  durable marker is pinned by behavior on a real tmp registry, not by prose.
* ``clear_command_for`` no longer pinning a non-default ``--registry`` → 2 failed
  (the command-construction pin and the ``list --eligible`` re-print).
* ``backlog_summary`` collapsing eligible gates back into unpaid debt → 2 failed in
  ``TestBacklogSeparatesEligible`` — the paid-vs-unpaid distinction is itself guarded.

N-round probes, run 2026-08-11 by the same method (sha256-verified restores; exit 1
mutated / 0 restored on both):

* reverting the LOCKED CONTRACTS.md §1.4 clear-eligible row to "NONE" → 1 failed,
  ``TestAutomaticPathNeverClears::test_the_locked_contract_table_matches_the_implementation``.
  The pin exists because the F1 fix was measured to have done exactly this drift: the
  code gained the marker write while the LOCKED table still said NONE and called
  re-defer "the only automatic action left".
* the critic's SECOND escape planted verbatim in `/quiz` Step 5 ("run the command in
  the block above so the backlog stays honest") → 1 failed, the check-14 scan on
  quiz.md. This sentence was NOT CAUGHT before the run-the-referent arm: its verb
  phrase names neither clear nor registry, only a referent to the presented command.
  Widening was chosen over documenting a hole only after a grep of all four scanned
  surfaces showed no unexempted "run the command/invocation/paste/block" ("Run it
  once per attempt" sits in a block without registry context; "Run the tutoring
  loop" lives inside a fenced dispatch prompt, which the detector strips).

Known escapes of check 14, measured rather than papered over: a violation phrased with a
developer mention in the same clause ("retire the gate for the developer") is exempted by
the actor rule, and one phrased inside a quotation of the developer's own words rides the
``"I clear it"`` exemption. Both are the price of keeping the legitimate presentation —
which names the developer constantly — unflagged. A third, deliberate narrowing: the
verb arms are base-form only, so a violation phrased in the third person ("the session
retires it when done") reads as description and passes — imperatives aimed at the agent
are base-form, and widening to -s forms was measured to flag the live declarative "a
clear releases it". The Steward's gate added three more measured escape classes,
KNOWN-UNCAUGHT and registered in :data:`KNOWN_UNCAUGHT_CLEAR_ESCAPES` (each verified
uncaught against the live detector on 2026-08-11; a rot-check fails if a widening
starts catching one while this documentation still calls it a hole):

* gerund phrasing — "Finish by clearing the parked gate before you report." (the verb
  arms are base-form by the deliberate narrowing above, and a gerund arm was measured
  to collide with the live declarative "clearing an education gate is the developer's
  explicit action");
* a direct-edit instruction that never says "status" — "Edit docs/education/gates.yaml
  and set the gate to cleared." (the status arms require the token);
* an agent-directed MARKER write — "mark the gate clear-eligible in the registry
  yourself." (the mark arm matches ``cleared``/``retired``, not ``clear-eligible``;
  writing the marker is the ingest's job, on a validated transcript only, never the
  agent's own).

None of the three can defeat the layered behavioral guards without actually moving the
registry file, which is the assertion. Related containment, stated here because the
Steward found it load-bearing and unstated: ``mark_clear_eligible`` is deliberately
NOT CLI-exposed — library-only, reachable solely through a validated-transcript
ingest — so there is no paste-ready command an instruction file could even present
for writing eligibility by hand.

``TestPerAttemptRecording::test_the_sibling_ingest_path_still_records_every_attempt``
reads a file this slice may not edit, so it was probed differently: the same
extraction was applied in memory to a copy of
``scripts/education/ingest_walkthrough_session.py`` with a
``if event.get("variant_of"): continue`` guard inserted into ``_education_rows``.
Live: ``_education_rows`` contains no ``variant_of`` and ``_decide`` does. Mutated:
``_education_rows`` contains it, which is the condition the assertion rejects. The
file itself was never written to.

An early version of :data:`REQUIRED_CAPTURE` was found MISSED by an earlier probe —
it matched the bare path ``scripts/record_education.py``, which both commands also
name inside their pre-flight existence check, so deleting the actual call passed. It
now matches the invocation form. An earlier revision of this docstring claimed
"nine injected regressions … all nine were caught"; the probe log was not kept in
the tree, the count was not reproducible from anything a reader can run, and the
flat "all nine" contradicted the escape recorded above. This list replaces it with
probes that state their own observed outcome, including the one that failed to
catch.

House style follows ``tests/test_constitution_consistency.py``: read the live
files, assert on their text, reuse its scanner rather than growing a second one,
and register known-bad out-of-scope files with a measured count instead of an
exemption.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

import pytest

# Reuse, not reimplement: the constitution guard already knows which git-tracked
# files carry live instructions vs. dated records, and already knows how to fold
# wrapped markdown into single logical blocks. Growing a second copy of either is
# how the two would drift apart.
from test_constitution_consistency import claim_blocks, live_instruction_files

REPO_ROOT = Path(__file__).resolve().parent.parent

# The per-record status vocabulary is IMPORTED, never retyped. Section 13 below is the
# whole reason: a restated copy of those five words is the drift this effort has been
# bitten by repeatedly, and a test that restates them vouches for a list it also owns.
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import verify_paths_not_taken as vpnt  # noqa: E402

EDUCATOR = ".claude/agents/educator.md"
QUIZ = ".claude/commands/quiz.md"
WALKTHROUGH = ".claude/commands/walkthrough.md"
GATES_SKILL = ".claude/skills/selecting-review-gates/SKILL.md"

#: The three files that state the Bloom mix and must agree.
RATIO_FILES = (EDUCATOR, GATES_SKILL, QUIZ)

#: All four surfaces the education gate is written across.
GATE_FILES = (EDUCATOR, QUIZ, WALKTHROUGH, GATES_SKILL)


def read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. The Bloom mix
# ---------------------------------------------------------------------------

#: ``30% Understand/Apply``, ``60-70% **Understand/Apply**``, ``30–40%\n  Analyze/Evaluate``.
#: Applied to whole-file text, not per line, because ``docs/education/CONTRACTS.md``
#: wraps between the percentage and its label.
_MIX = re.compile(
    r"(\d+)(?:\s*[-–—]\s*(\d+))?\s*%\s*\*{0,2}\s*"
    r"(Understand\s*/\s*Apply|Analyze\s*/\s*Evaluate)",
    re.IGNORECASE,
)


class MixClaim(NamedTuple):
    """One stated share of the Bloom mix: ``("understand", 30, 30)``."""

    bucket: str
    low: int
    high: int


def stated_mix(text: str) -> set[MixClaim]:
    """Every Bloom-mix share ``text`` states, normalised."""
    claims: set[MixClaim] = set()
    for match in _MIX.finditer(text):
        low = int(match.group(1))
        high = int(match.group(2)) if match.group(2) else low
        bucket = "understand" if match.group(3).lower().startswith("understand") else "analyze"
        claims.add(MixClaim(bucket, low, high))
    return claims


#: The educator charter's ratio — the disposition the developer directed
#: (educator.md wins; both consumers were corrected to match it).
CANONICAL_MIX = {MixClaim("understand", 30, 30), MixClaim("analyze", 70, 70)}

# Live files OUTSIDE this slice's editable scope that still publish the old
# consumer-side ratio. A debt register, not a licence: each entry records the
# ratio the file states *today*, so a change to it — in either direction — fails
# `test_known_stale_mix_register_does_not_rot` and forces the register to be
# updated deliberately. Both are doc-sync work (`syncing-framework-docs`);
# docs/education/CONTRACTS.md is additionally a versioned cross-repo contract and
# should be re-pointed with a contract revision, not edited in passing.
KNOWN_STALE_MIX: dict[str, set[MixClaim]] = {
    "docs/FRAMEWORK_SPECIFICATION.md": {
        MixClaim("understand", 60, 70),
        MixClaim("analyze", 30, 40),
    },
    "docs/education/CONTRACTS.md": {
        MixClaim("understand", 60, 70),
        MixClaim("analyze", 30, 40),
    },
}

#: Phrasings that say "the within-session ramp is not the overall mix".
_RAMP_MARKERS = (
    "within-session",
    "within a session",
    "within the session",
    "overall mix",
)


class TestBloomRatioAgreement:
    """The three-way disagreement REV-20260513 filed as an advisory and nobody paid.

    Live 2026-05-12; named in that review on 2026-05-13; still live 2026-08-08 (87
    days). See the module docstring for the commands that measure those dates.
    """

    @pytest.mark.regression
    def test_all_three_files_state_the_same_ratio(self) -> None:
        """educator.md, the review-gates skill and /quiz must state one identical mix.

        Cited by name in ``.claude/agents/educator.md`` §2.6 and in the skill's
        Education Gates block; ``TestProseReferencesResolve`` in
        ``tests/test_constitution_consistency.py`` fails if either citation stops
        resolving to this test.
        """
        found = {rel: stated_mix(read(rel)) for rel in RATIO_FILES}

        for rel, claims in found.items():
            assert claims, (
                f"{rel} states no Bloom mix at all. All three of {list(RATIO_FILES)} must "
                "state it, or a consumer silently loses the ratio and reverts to whatever "
                "the model assumes."
            )

        distinct = {frozenset(claims) for claims in found.values()}
        assert len(distinct) == 1, (
            "The three files disagree about the Bloom mix — this is the exact defect this "
            f"test exists to prevent. Found: { {rel: sorted(c) for rel, c in found.items()} }"
        )

        assert next(iter(distinct)) == frozenset(CANONICAL_MIX), (
            f"The agreed mix is {sorted(next(iter(distinct)))}, expected {sorted(CANONICAL_MIX)}. "
            "educator.md's charter ratio is authoritative (developer-directed disposition, "
            "2026-08-08). Changing it is a framework-evolution decision: edit this assertion "
            "and all three files together, never one file alone."
        )

    def test_every_file_that_states_the_mix_notes_the_within_session_ramp(self) -> None:
        """Ramp and mix are different rules; unlabelled, a reader 'fixes' one into the other.

        The transferred pedagogy resolves the old conflict with a position-dependent
        ramp (early questions lean Understand, later ones lean Analyze/Evaluate).
        That is an *ordering* rule. Stated next to a 30/70 *overall* mix with no
        note, it reads like a second, contradictory ratio.
        """
        for rel in RATIO_FILES:
            text = read(rel).lower()
            assert any(marker in text for marker in _RAMP_MARKERS), (
                f"{rel} states the Bloom mix but never distinguishes the within-session "
                f"difficulty ramp from the overall mix (looked for {list(_RAMP_MARKERS)}). "
                "Without that sentence the two rules read as a contradiction — which is how "
                "this ratio drifted the first time."
            )

    @pytest.mark.regression
    def test_no_unregistered_live_file_states_a_rival_ratio(self) -> None:
        """A fourth opinion anywhere on the live surface is the same defect, one file over."""
        offenders: dict[str, set[MixClaim]] = {}
        for rel in live_instruction_files():
            if rel in RATIO_FILES or rel in KNOWN_STALE_MIX:
                continue
            claims = stated_mix(read(rel))
            if claims and claims != CANONICAL_MIX:
                offenders[rel] = claims
        assert not offenders, (
            "These live instruction files state a Bloom mix that differs from the canonical "
            f"{sorted(CANONICAL_MIX)}: { {r: sorted(c) for r, c in offenders.items()} }. "
            "Either correct the file or register it in KNOWN_STALE_MIX with its measured "
            "value and an owner."
        )

    def test_known_stale_mix_register_does_not_rot(self) -> None:
        """A debt entry may not outlive — or understate — the debt it records."""
        for rel, registered in KNOWN_STALE_MIX.items():
            path = REPO_ROOT / rel
            assert path.is_file(), (
                f"KNOWN_STALE_MIX registers {rel}, which no longer exists. Delete the entry."
            )
            actual = stated_mix(read(rel))
            assert actual == registered, (
                f"{rel} now states {sorted(actual)}, but KNOWN_STALE_MIX records "
                f"{sorted(registered)}. If the debt was paid, delete the entry; if the file "
                "changed some other way, update the entry deliberately."
            )


# ---------------------------------------------------------------------------
# 2. The re-teach loop
# ---------------------------------------------------------------------------
#
# Each requirement is a group of alternative phrasings. The check passes if ANY
# phrasing in the group is present, so a rewrite of the instruction survives while
# DELETING the instruction fails. This is the "fail on rewordings of a violation,
# not only on the literal string that shipped" rule from the house style: the
# violation is the absence of the rule, and absence is what is detected.


class Requirement(NamedTuple):
    """A rule that must be stated somewhere in a file, in any of several wordings."""

    name: str
    any_of: tuple[str, ...]
    why: str


LOOP_REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "a miss does not end the concept",
        (
            "do not move on",
            "do **not** move on",
            "never move past a miss",
            "never move past a miss",
            "do not supply the answer",
            "never clear a miss",
            "never move on",
        ),
        "Grade-and-move-on is the old behaviour. Without this the loop is decorative.",
    ),
    Requirement(
        "re-explain from a different entry point",
        (
            "different entry point",
            "entry point you have not",
            "unspent entry point",
            "not already spent",
            "not already used",
        ),
        "'Explain differently' must mean a different entry point, not different words.",
    ),
    Requirement(
        "then ask again",
        (
            "ask again",
            "ask a **different** question",
            "ask a different question",
            "and ask again",
        ),
        "Re-teaching without re-asking never learns whether it landed.",
    ),
    Requirement(
        "the loop is unbounded",
        (
            "no turn limit",
            "no strike count",
            "however many turns",
            "there is no limit",
        ),
        "A capped loop is a test with extra steps; the developer asked for fault tolerance.",
    ),
    Requirement(
        "a synonym swap is not a re-explanation",
        (
            "never a synonym swap",
            "not a synonym swap",
            "synonym swap",
            "reuses the same frame",
            "same frame with different words",
            "through a thesaurus",
        ),
        "This is THE loop. A re-worded first explanation is the failure mode being banned.",
    ),
)

#: The entry-point vocabulary educator.md §2.2 defines. Consumers may name a
#: subset, but may not invent one the charter does not define.
ENTRY_POINTS: tuple[tuple[str, ...], ...] = (
    ("consequence-first",),
    ("analogy from a domain",),
    ("counterfactual",),
    ("concrete trace",),
    ("losing alternative",),
    ("failure-mode-first",),
    ("scale or limit", "scale/limit"),
)


def named_entry_points(text: str) -> set[int]:
    """Indices of :data:`ENTRY_POINTS` this text names."""
    lowered = text.lower()
    return {i for i, spellings in enumerate(ENTRY_POINTS) if any(s in lowered for s in spellings)}


class TestReTeachLoopIsInstructed:
    """Prose in a command file is an instruction. These pin that it reads as one."""

    @pytest.mark.parametrize("rel", [EDUCATOR, QUIZ])
    def test_loop_requirements_are_all_stated(self, rel: str) -> None:
        """The charter and the command that runs it must both carry the whole loop.

        /quiz cannot delegate the loop to the charter alone: a command file is read
        by the orchestrator, and the previous version's Step 4 assigned scoring to
        no agent at all while saying nothing about what happens on a wrong answer.
        """
        lowered = read(rel).lower()
        missing = [
            f"{req.name} (looked for any of {list(req.any_of)}) — {req.why}"
            for req in LOOP_REQUIREMENTS
            if not any(phrase.lower() in lowered for phrase in req.any_of)
        ]
        assert not missing, f"{rel} no longer instructs the re-teach loop:\n  " + "\n  ".join(
            missing
        )

    def test_walkthrough_also_carries_the_reteach_rule(self) -> None:
        """/walkthrough teaches too; a checkpoint miss must re-explain, not roll past."""
        lowered = read(WALKTHROUGH).lower()
        for req in LOOP_REQUIREMENTS[1:3] + (LOOP_REQUIREMENTS[4],):
            assert any(phrase.lower() in lowered for phrase in req.any_of), (
                f"{WALKTHROUGH} does not state '{req.name}'. It presents a walkthrough and "
                "hands off to /quiz; if it never re-explains on a shaky checkpoint it is the "
                "print-and-suggest command it was rebuilt to stop being."
            )

    def test_educator_enumerates_entry_points(self) -> None:
        """'Explain differently' is unusable as an instruction without a list to switch between."""
        found = named_entry_points(read(EDUCATOR))
        assert len(found) >= 5, (
            f"{EDUCATOR} names only {len(found)} of the {len(ENTRY_POINTS)} entry points "
            f"({sorted(found)}). At least 5 must be enumerable, or 'switch entry point' is "
            "advice rather than a mechanism the model can execute."
        )

    @pytest.mark.parametrize("rel", [QUIZ, WALKTHROUGH])
    def test_commands_name_entry_points_the_charter_defines(self, rel: str) -> None:
        """A consumer must offer a real choice, and must not invent vocabulary."""
        found = named_entry_points(read(rel))
        assert len(found) >= 4, (
            f"{rel} names only {len(found)} entry points. The loop tells the model to pick an "
            "UNSPENT one; with fewer than four the choice runs out before the loop does."
        )
        charter = named_entry_points(read(EDUCATOR))
        assert found <= charter, (
            f"{rel} names entry points {sorted(found - charter)} that {EDUCATOR} does not "
            "define. Two vocabularies is how the ratio drifted; keep one."
        )

    def test_the_success_criterion_is_stated_not_the_score(self) -> None:
        """The gate's definition of done must be 'explains it in his own words', everywhere."""
        for rel in GATE_FILES:
            lowered = read(rel).lower()
            assert "own words" in lowered, (
                f"{rel} never states the success criterion (the developer explaining the "
                "change in his own words). Without it, 'pass' silently reverts to the score."
            )


# ---------------------------------------------------------------------------
# 3. No celebrate-growth language
# ---------------------------------------------------------------------------

#: Rejected on values grounds by the pedagogy this loop transfers from: with no
#: measured before-state, progress framing is fabricated. ``educator.md`` carried
#: a ``- **Celebrate growth**: …`` bullet until 2026-08-08.
_PRAISE_PATTERNS: tuple[str, ...] = (
    r"celebrat\w*",
    r"\bpraise\w*",
    r"great job",
    r"well done",
    r"nice work",
    r"good work",
    r"kudos",
    r"keep it up",
    r"proud of",
    r"you'?ve come a long way",
    r"\bstreaks?\b",
    r"progress deserves",
    r"deserves recognition",
    r"acknowledg\w*\s+(?:their|his|your|the)?\s*(?:growth|progress|improvement)",
)

#: Characters of preceding text (within the same markdown block) searched for a
#: negation marker. Wide enough to cover "- **MUST NOT** use celebrate-growth or
#: progress-praise language — no 'great job', no 'you've come a long way'…",
#: which is one wrapped bullet.
_NEGATION_WINDOW = 220

# Bare ``not`` rather than ``do not`` / ``must not``: markdown emphasis splits the
# phrase (``do **not** use progress-praise language``), so a two-word marker misses
# the very sentences that ARE prohibitions. ``\bno\b`` does not match "nothing".
_NEGATION = re.compile(r"\b(?:not|never|cannot|can'?t|don'?t|without|avoid|no)\b", re.I)


def unprohibited_praise(text: str) -> list[str]:
    """``"line N: 'celebrate'"`` for praise language not sitting inside a prohibition."""
    hits: list[str] = []
    for line_no, block in claim_blocks(text):
        for pattern in _PRAISE_PATTERNS:
            for match in re.finditer(pattern, block, re.IGNORECASE):
                window = block[max(0, match.start() - _NEGATION_WINDOW) : match.start()]
                if not _NEGATION.search(window):
                    hits.append(f"line {line_no}: {match.group(0)!r} in {block[:120]!r}")
    return hits


class TestNoCelebrateGrowthLanguage:
    """MUST-NOT, transferred verbatim from the deliberation that rejected it."""

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_no_praise_framing_outside_a_prohibition(self, rel: str) -> None:
        hits = unprohibited_praise(read(rel))
        assert not hits, (
            f"{rel} contains celebrate-growth / progress-praise language that is not itself a "
            f"prohibition:\n  " + "\n  ".join(hits) + "\n"
            "Rejected as a values risk: with no measured before-state, progress framing is "
            "fabricated. Report what was demonstrated, plainly."
        )

    def test_the_prohibition_itself_is_present(self) -> None:
        """Deleting the MUST-NOT would make the check above vacuously green."""
        lowered = read(EDUCATOR).lower()
        assert "celebrate-growth" in lowered or "celebrate growth" in lowered, (
            f"{EDUCATOR} no longer carries the explicit celebrate-growth prohibition. "
            "Without it the ban is enforced only by this test, and a future author "
            "re-adds the bullet without ever seeing the reason it was removed."
        )
        assert "must not" in lowered, (
            f"{EDUCATOR} must state its load-bearing prohibitions as MUST NOTs, not as "
            "preferences a persona can trade away."
        )


# ---------------------------------------------------------------------------
# 4. The rubric: fault-tolerant, but correctness still gates
# ---------------------------------------------------------------------------

RUBRIC_REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "grade reasoning in his own words",
        ("in his own words", "in their own words", "own words"),
        "The whole point: paraphrase is understanding, recital is not.",
    ),
    Requirement(
        "accept paraphrase",
        ("accept paraphrase", "accept a paraphrase", "partial vocabulary", "clumsy phrasing"),
        "Fault tolerance is why the developer asked for this rebuild.",
    ),
    Requirement(
        "reject verbatim recital",
        ("verbatim recital", "reject verbatim", "hands back the walkthrough", "read them aloud"),
        "Reciting the walkthrough back is the cheapest way to fake a pass.",
    ),
    Requirement(
        "a reasoned near-miss outscores unexplained recall",
        ("near-miss outscores", "reasoned near-miss", "outscores unexplained"),
        "The softening amendment from the source deliberation.",
    ),
    Requirement(
        "correctness still gates",
        (
            "correctness still gates",
            "does not mean everything passes",
            "wrong answer is a miss",
            "never record a wrong answer",
        ),
        "The counter-softening: fault tolerance must not become a rubber stamp. "
        "The source deliberation raised exactly this risk and amended for it.",
    ),
)


class TestRubricIsHonest:
    def test_educator_rubric_is_fault_tolerant_and_still_gates(self) -> None:
        lowered = read(EDUCATOR).lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in RUBRIC_REQUIREMENTS
            if not any(phrase.lower() in lowered for phrase in req.any_of)
        ]
        assert not missing, f"{EDUCATOR}'s rubric is incomplete:\n  " + "\n  ".join(missing)

    def test_quiz_restates_the_correctness_gate(self) -> None:
        """The command judges answers turn by turn; it cannot rely on the charter alone."""
        lowered = read(QUIZ).lower()
        assert "correctness still gates" in lowered, (
            f"{QUIZ} must restate that correctness gates. A fault-tolerant loop with no "
            "correctness floor passes a confident wrong answer, which is worse than the "
            "test regime it replaced."
        )


# ---------------------------------------------------------------------------
# 5. Grounding: hedged inference, never an invented bug
# ---------------------------------------------------------------------------

#: Fragility signals a debug question may be anchored in. Named concretely so the
#: instruction is executable rather than aspirational.
_FRAGILITY_SIGNALS = ("guard", "todo", "retry", "try/except", "regression-ledger")


class TestGroundingRules:
    @pytest.mark.parametrize("rel", [EDUCATOR, QUIZ])
    def test_never_invent_a_bug(self, rel: str) -> None:
        lowered = read(rel).lower()
        assert "never invent a bug" in lowered or "not invent a bug" in lowered, (
            f"{rel} must forbid invented debug scenarios outright. A hypothetical bug teaches "
            "a hypothetical system, and the developer cannot tell the difference."
        )
        named = [s for s in _FRAGILITY_SIGNALS if s in lowered]
        assert len(named) >= 3, (
            f"{rel} names only {named} as real fragility signals. 'Ground it in something real' "
            "is not executable without a list of what counts."
        )

    @pytest.mark.parametrize("rel", [EDUCATOR, WALKTHROUGH])
    def test_hedged_inference_where_no_decision_record_exists(self, rel: str) -> None:
        lowered = read(rel).lower()
        assert "looks like" in lowered, (
            f"{rel} must instruct the hedged form ('this LOOKS LIKE it exists to…') for "
            "rationale with no ADR or discussion behind it."
        )
        assert "exists because" in lowered, (
            f"{rel} must name the forbidden asserted form ('this exists because…') explicitly. "
            "Naming only the good form leaves the bad one unmarked."
        )


# ---------------------------------------------------------------------------
# 6. The veto: measurement must not get thinner
# ---------------------------------------------------------------------------

# Capture calls each command made BEFORE the rebuild. Removing one is the veto.
#
# Matched on the INVOCATION form (``python scripts/x.py``), not the bare path.
# Measured: a probe that replaced the invocation of ``record_education.py`` with a
# nonexistent script still passed a bare-path check, because both commands also
# name the script inside their pre-flight `pathlib.Path(...).exists()` block. A
# mention is not a call.
REQUIRED_CAPTURE: dict[str, tuple[str, ...]] = {
    QUIZ: (
        "python scripts/create_discussion.py",
        "python scripts/write_event.py",
        "python scripts/record_education.py",
        "python scripts/close_discussion.py",
    ),
    WALKTHROUGH: (
        "python scripts/create_discussion.py",
        "python scripts/write_event.py",
        "python scripts/close_discussion.py",
    ),
}

#: The pre-existing CRITICAL BEHAVIORAL RULES. Principle #2 machinery — the
#: education gate is Principle #5 and its capture is not optional.
CRITICAL_RULES: tuple[Requirement, ...] = (
    Requirement(
        "never skip capture",
        ("never skip capture",),
        "No session exists unless captured.",
    ),
    Requirement(
        "never continue on failure",
        ("never continue on failure",),
        "A half-captured session is worse than none.",
    ),
    Requirement(
        "always close the discussion",
        ("always close the discussion",),
        "An unsealed Layer 1 discussion never reaches Layer 2.",
    ),
)


class TestMeasurementDidNotGetThinner:
    """'Did measurement get thinner?' is a veto in this effort, so it is a test here."""

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", sorted(REQUIRED_CAPTURE))
    def test_every_pre_existing_capture_call_survives(self, rel: str) -> None:
        text = read(rel)
        missing = [script for script in REQUIRED_CAPTURE[rel] if script not in text]
        assert not missing, (
            f"{rel} no longer invokes {missing}. Rebuilding the education gate must not drop a "
            "capture call — that is the veto, not a finding."
        )

    @pytest.mark.parametrize("rel", sorted(REQUIRED_CAPTURE))
    def test_critical_behavioral_rules_survive(self, rel: str) -> None:
        lowered = read(rel).lower()
        missing = [
            f"{req.name} — {req.why}"
            for req in CRITICAL_RULES
            if not any(p.lower() in lowered for p in req.any_of)
        ]
        assert not missing, f"{rel} dropped a CRITICAL BEHAVIORAL RULE:\n  " + "\n  ".join(missing)

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", sorted(REQUIRED_CAPTURE))
    def test_developer_answers_now_reach_layer_one(self, rel: str) -> None:
        """The named measurement GAP in the old path: his answers were never recorded.

        ``scripts/record_education.py`` persists only
        ``(session_id, discussion_id, bloom_level, question_type, score, passed, timestamp)``
        — so a wrong judgement was unauditable after the fact. Its schema is out of
        scope to change; the fix is that the answer text reaches Layer 1 instead.
        """
        text = read(rel)
        assert '"learner"' in text, (
            f"{rel} must capture the developer's answer as a `learner` turn via "
            "scripts/write_event.py. Without it the only durable trace of a tutoring "
            "session is a number, and a wrong grade stays unauditable."
        )
        lowered = text.lower()
        assert "verbatim" in lowered, (
            f"{rel} must say the answer is captured VERBATIM. A summarised answer cannot "
            "settle a later disagreement about what he actually said."
        )

    def test_layer_one_vocabulary_matches_the_locked_intent_map(self) -> None:
        """Reuse the LOCKED agent names, so in-session and ingested transcripts match.

        ``scripts/education/ingest_walkthrough_session.py`` locks ``tutor``/``learner``
        against ``docs/education/CONTRACTS.md`` §1.2. If ``/quiz`` invents its own
        names, the two education paths produce records that no single query reads.
        """
        ingest = read("scripts/education/ingest_walkthrough_session.py")
        tutor = re.search(r'^_TUTOR\s*=\s*"([^"]+)"', ingest, re.MULTILINE)
        learner = re.search(r'^_LEARNER\s*=\s*"([^"]+)"', ingest, re.MULTILINE)
        assert tutor and learner, (
            "scripts/education/ingest_walkthrough_session.py no longer defines _TUTOR/_LEARNER; "
            "this test can no longer read the locked vocabulary and must be re-pointed."
        )
        for rel in (QUIZ, WALKTHROUGH):
            text = read(rel)
            for name in (tutor.group(1), learner.group(1)):
                assert f'"{name}"' in text, (
                    f"{rel} does not use the locked education agent name {name!r} from "
                    "docs/education/CONTRACTS.md §1.2. Two vocabularies for the same event "
                    "stream is a query that silently returns half the data."
                )


# ---------------------------------------------------------------------------
# 7. Prose that points at a file must point at a real one
# ---------------------------------------------------------------------------

#: Backticked repo-relative paths: a known top-level directory plus a suffix.
_REPO_PATH = re.compile(
    r"`((?:\.claude|docs|scripts|tests|memory|src|config|loops|discussions|metrics)"
    r"/[\w./§-]*?\.(?:md|py|yaml|yml|json|sh|jsonl))`"
)

#: ``§2.2``, ``§6``. A section pointer into the educator charter.
_SECTION_REF = re.compile(r"§(\d+(?:\.\d+)?)")

#: ``### 2. The Tutoring Loop`` / ``#### 2.2 Entry points …``
_SECTION_HEADING = re.compile(r"^#{2,4}\s+(\d+(?:\.\d+)?)[.\s]", re.MULTILINE)

#: A ``§`` reference whose preceding text names another document is that
#: document's numbering, not the charter's — ``docs/education/CONTRACTS.md §1.2``.
_FOREIGN_SECTION_OWNER = re.compile(r"(CONTRACTS\.md|\.md`)\s*$")


def charter_section_refs(text: str) -> set[str]:
    """Section numbers this text points at *in the educator charter*."""
    refs: set[str] = set()
    for match in _SECTION_REF.finditer(text):
        preceding = text[max(0, match.start() - 40) : match.start()]
        if _FOREIGN_SECTION_OWNER.search(preceding):
            continue
        refs.add(match.group(1))
    return refs


class TestProseReferencesResolve:
    """Same standard the constitution guard applies: a named home must exist."""

    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_every_backticked_repo_path_exists(self, rel: str) -> None:
        text = read(rel)
        broken = sorted(
            {token for token in _REPO_PATH.findall(text) if not (REPO_ROOT / token).exists()}
        )
        assert not broken, (
            f"{rel} names files that do not exist: {broken}. Instruction prose that points at "
            "a missing file reads as a mechanism and is inert — the exact defect "
            "tests/test_constitution_consistency.py::TestGovernanceLocationClaims was added for."
        )

    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_every_charter_section_reference_resolves(self, rel: str) -> None:
        """``§2.2`` is load-bearing here — it is how the loop names its entry points.

        A section pointer is a string. Renumber the charter and every ``§`` in three
        other files silently points at nothing while still reading like a working
        cross-reference. Same failure family as an unresolvable pytest node id.
        """
        headings = set(_SECTION_HEADING.findall(read(EDUCATOR)))
        assert headings, (
            f"{EDUCATOR} has no numbered section headings; this check cannot resolve anything "
            "and must be re-pointed rather than left silently vacuous."
        )
        broken = sorted(charter_section_refs(read(rel)) - headings)
        assert not broken, (
            f"{rel} points at educator-charter sections that do not exist: "
            f"{['§' + b for b in broken]}. Present headings: {sorted(headings)}."
        )


# ---------------------------------------------------------------------------
# 8. The veto, sharpened: every attempt reaches education_results
# ---------------------------------------------------------------------------
#
# See "Why check 7 exists" in the module docstring. Two halves are pinned here
# because the defect needs both to be true: the instruction files must SAY
# per-attempt, and the sibling ingest path must still DO per-attempt. If either
# drifts alone, one table ends up holding two row semantics and the "Education
# Trends" GROUP BY that both /retro and /meta-review print becomes uninterpretable.

INGEST = "scripts/education/ingest_walkthrough_session.py"

#: Commands that read ``education_results`` and print it as a trend. Pinned so
#: that if the readers go away, the next author sees WHY per-attempt rows were
#: required rather than inheriting the rule as folklore.
EDUCATION_READERS = (".claude/commands/retro.md", ".claude/commands/meta-review.md")

PER_ATTEMPT_REQUIREMENTS: tuple[Requirement, ...] = (
    Requirement(
        "record every attempt as its own row",
        (
            "every attempt as its own row",
            "one row per attempt",
            "row per attempt",
            "each get their own row",
            "its own row",
        ),
        "Terminal-only rows are a pass by construction: the loop runs until the concept "
        "is demonstrated, so AVG(score) goes to ~1.0 forever and the instrument dies.",
    ),
    Requirement(
        "the gate clears on the terminal attempt",
        (
            "gate clears on the terminal",
            "clears on the terminal attempt",
            "only terminal items",
            "terminal items contribute",
        ),
        "Fault tolerance must still resolve to a gate decision; recording the miss must "
        "not mean the miss decides the gate.",
    ),
)

#: Phrasings of the regression itself — recording ONLY the settled state. Any of
#: these in an instruction file is the defect, not a wording variant of the fix.
_TERMINAL_ONLY_PATTERNS: tuple[str, ...] = (
    r"never the first attempt",
    r"not the first attempt",
    r"only the terminal",
    r"terminal state per concept",
    r"the terminal state after the loop",
    r"record the \*{0,2}terminal\*{0,2} state",
)


class TestPerAttemptRecording:
    """The veto check with teeth: a miss must survive into Layer 2, not just Layer 1."""

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [EDUCATOR, QUIZ])
    def test_instruction_files_require_a_row_per_attempt(self, rel: str) -> None:
        lowered = read(rel).lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in PER_ATTEMPT_REQUIREMENTS
            if not any(phrase.lower() in lowered for phrase in req.any_of)
        ]
        assert not missing, (
            f"{rel} no longer instructs per-attempt recording into education_results:\n  "
            + "\n  ".join(missing)
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [EDUCATOR, QUIZ])
    def test_the_terminal_only_regression_is_not_reintroduced(self, rel: str) -> None:
        """Fails on the *rewording* of the defect, not only the sentence that shipped."""
        text = read(rel)
        hits = [
            f"{pattern!r} -> {match.group(0)!r}"
            for pattern in _TERMINAL_ONLY_PATTERNS
            for match in [re.search(pattern, text, re.IGNORECASE)]
            if match
        ]
        assert not hits, (
            f"{rel} instructs recording ONLY the settled/terminal state: {hits}. That makes "
            "education_results a constant — the loop runs until demonstration, so every "
            "terminal row passes by construction — and it contradicts docs/education/"
            "CONTRACTS.md §1.2, which locks per-attempt rows for the ingest path. Record "
            "every attempt; gate on the terminal one."
        )

    @pytest.mark.regression
    def test_the_sibling_ingest_path_still_records_every_attempt(self) -> None:
        """The claim 'both paths write the same row semantics' must stay measurable.

        ``_education_rows`` maps events onto rows and must NOT filter re-teach
        variants; ``_decide`` computes the gate and MUST exclude superseded items via
        ``variant_of``. If those two swap, this slice's instruction files become the
        odd ones out and the shared table holds two semantics again.
        """
        source = read(INGEST)
        bodies = {}
        for name in ("_education_rows", "_decide"):
            match = re.search(rf"^def {name}\(.*?(?=^def |\Z)", source, re.MULTILINE | re.DOTALL)
            assert match, (
                f"{INGEST} no longer defines {name}(); this test can no longer verify that "
                "the two education paths agree and must be re-pointed rather than deleted."
            )
            bodies[name] = match.group(0)

        assert "variant_of" not in bodies["_education_rows"], (
            f"{INGEST}::_education_rows now filters on variant_of, i.e. it stopped writing a "
            "row for the missed original. docs/education/CONTRACTS.md §1.2 says 'Both the "
            "missed original and the passing variant get their own education_results row'. "
            "Either that contract changed (update it, and .claude/agents/educator.md §2.7 "
            "and .claude/commands/quiz.md Step 5 with it) or this is the regression."
        )
        assert "variant_of" in bodies["_decide"], (
            f"{INGEST}::_decide no longer excludes superseded items via variant_of, so a "
            "re-taught-and-passed item is dragged below threshold by its own original miss. "
            "That is the exact failure CONTRACTS.md §1.2 documents this linkage to prevent."
        )

    def test_the_instrument_still_has_readers(self) -> None:
        """Non-vacuity: per-attempt rows matter because something prints them."""
        readers = [rel for rel in EDUCATION_READERS if "education_results" in read(rel).lower()]
        assert readers == list(EDUCATION_READERS), (
            "These commands no longer read education_results: "
            f"{sorted(set(EDUCATION_READERS) - set(readers))}. The per-attempt rule above "
            "exists because AVG(score) over that table is printed as an 'Education Trends' "
            "line; if nothing reads it any more, revisit the rule deliberately instead of "
            "leaving this test asserting nothing."
        )
        for rel in EDUCATION_READERS:
            assert "avg(score)" in read(rel).lower(), (
                f"{rel} still names education_results but no longer averages score. The "
                "flatten-to-1.0 argument in TestPerAttemptRecording's docstring is pinned to "
                "that AVG; re-measure it before relaxing anything here."
            )


# ---------------------------------------------------------------------------
# 9. A cap bolted on beside the ban
# ---------------------------------------------------------------------------
#
# Every check above is a PRESENCE check: it fails when a rule is deleted. The
# realistic erosion of an unbounded loop is not deletion — it is an addition, a
# well-meant "after N tries, move on" sentence placed directly under the retained
# "there is no turn limit". Measured: that mutation left all other checks green.
#
# Deliberately NOT negation-windowed. The mutation sits in the same markdown block
# as "There is no turn limit and no strike count", so any generic negation window
# would tolerate exactly the case this exists to catch. Instead the pattern
# requires the cap's CONSEQUENCE — moving on — which a prohibition does not have.

#: "after three attempts", "a maximum of 2 tries", "capped at three turns".
_TURN_CAP = re.compile(
    r"(?:after|beyond|past)\s+(?:\d+|one|two|three|four|five)\s+"
    r"(?:attempts?|tries|turns?|strikes?|misses|re-?explanations?)"
    r"|(?:maximum|max\.?|at most|no more than|limit(?:ed)?\s+(?:of|to)|cap(?:ped)?\s+(?:at|to))"
    r"\s+(?:\d+|one|two|three|four|five)\s+(?:attempts?|tries|turns?|re-?teach\w*)"
    r"|\b(?:two|three|2|3)[-\s]strikes?\b",
    re.IGNORECASE,
)

#: What makes a cap a cap: the concept ends. Searched AFTER the cap phrase.
_MOVE_ON = re.compile(
    r"move (?:on|to the next)|next (?:question|concept|item)|record the score"
    r"|give up|mark it (?:passed|failed|done)|stop (?:and record|asking)|accept it",
    re.IGNORECASE,
)

#: Characters after the cap phrase searched for the move-on consequence — about one
#: wrapped sentence. Measured against the probe mutation, whose consequence clause
#: ("record the score and move to the next question") sits 34 characters after it.
_CAP_WINDOW = 160


def turn_caps(text: str) -> list[str]:
    """``"line N: …"`` for every attempt cap whose stated consequence is moving on."""
    hits: list[str] = []
    for line_no, block in claim_blocks(text):
        for match in _TURN_CAP.finditer(block):
            window = block[match.end() : match.end() + _CAP_WINDOW]
            consequence = _MOVE_ON.search(window)
            if consequence:
                hits.append(
                    f"line {line_no}: {match.group(0)!r} then {consequence.group(0)!r} "
                    f"in {block[:140]!r}"
                )
    return hits


class TestNoTurnCapContradiction:
    """'FAULT TOLERANT … KEEP EXPLAINING IT TO ME' — a cap is the opposite of the ask."""

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_no_attempt_cap_that_ends_the_concept(self, rel: str) -> None:
        hits = turn_caps(read(rel))
        assert not hits, (
            f"{rel} caps the re-teach loop and moves on when the cap is hit:\n  "
            + "\n  ".join(hits)
            + "\nThe unbounded loop IS the deliverable. Escalating after three *entry "
            "points* (educator charter §2.1) is allowed and does not match this check — it "
            "escalates or asks him which part is not landing, it does not end the concept."
        )

    def test_the_escalation_rule_is_not_caught_by_this_check(self) -> None:
        """Non-vacuity in the other direction: the legitimate rule must stay legal.

        educator.md §2.1 and /quiz both say that after three *entry points* on one
        concept, stop guessing and escalate or ask. That is not a cap — the concept
        does not end — and a check that flagged it would push authors to delete the
        escalation rule to get green.
        """
        for rel in (EDUCATOR, QUIZ):
            lowered = read(rel).lower()
            assert "three different entry points" in lowered, (
                f"{rel} no longer states the three-entry-point escalation rule, so this "
                "test's guarantee (that the rule is not mistaken for a turn cap) is "
                "vacuous. Restore the rule or re-point this test."
            )
            assert not turn_caps(read(rel)), (
                f"{rel}: the escalation rule is being flagged as a turn cap. Narrow "
                "_TURN_CAP / _MOVE_ON rather than deleting the rule."
            )


# ---------------------------------------------------------------------------
# 10. One constant, two mechanisms: the 0.70 threshold
# ---------------------------------------------------------------------------
#
# A previous revision of the review-gates skill stated, absolutely, that the 70%
# threshold "is not the gate criterion and no gate clears or fails on it". Measured
# against the live tree, that is false in one of the two education paths:
#
#   grep -n "PASS_THRESHOLD\|clear_gate" scripts/education/ingest_walkthrough_session.py
#     -> per-item bookkeeping (education_results.passed) inside _education_rows()
#     -> the AGGREGATE eligibility decision inside _decide()
#     -> the step-5 comment stating the automatic path never calls clear_gate
#
# docs/education/CONTRACTS.md §1.4 (rev 1.1) is marked LOCKED and reads
# ``clear_eligible ⟺ walked AND quiz_avg >= 0.70 AND explain_back_passed``. So the
# ingested-transcript path still GATES on this number — the formula decides
# CLEAR-ELIGIBILITY, and since ADR-0035 the flip to ``cleared`` is the developer's
# own ``gate_registry.py clear``, never the ingest's. The in-session tutoring loop
# does not gate on it at all — it clears on educator.md §2.1. Both statements are
# true and neither may be generalised into the other; a governance file that
# publishes only one of them contradicts a LOCKED contract, which is the exact
# defect class the Bloom-ratio pin above exists for.

#: Phrasings that deny the threshold gates anything.
_THRESHOLD_DENIAL = re.compile(
    r"not the gate|no gate (?:clears|fails)|never the gate|nothing clears on",
    re.IGNORECASE,
)

#: Scoping that makes such a denial true: it names WHICH path it is denying, or
#: names the other path that does gate on the number.
_THRESHOLD_SCOPING = (
    "in-session",
    "in session",
    "ingested-transcript",
    "ingested transcript",
    "adr-0029",
    "§1.4",
    "this loop",
)


def unscoped_threshold_denials(text: str) -> list[str]:
    """``"line N: '<denial>'"`` for each denial whose block carries no scoping marker.

    Scoped to the markdown block via ``claim_blocks``, not to a character window over
    raw text. Measured while writing this: SKILL.md's own ``Never write "no gate clears
    on this number."`` wraps across a newline, so a raw-text scan found **zero** denials
    in a file that contains one, and the check was silently vacuous against the very
    sentence it was written for. Folding first also makes the block the right unit — a
    denial and the sentence that scopes it are one passage by construction, and a
    reader who meets them in different passages meets two independent claims.
    """
    hits: list[str] = []
    for line_no, block in claim_blocks(text):
        lowered = block.lower()
        if any(marker in lowered for marker in _THRESHOLD_SCOPING):
            continue
        for match in _THRESHOLD_DENIAL.finditer(block):
            hits.append(f"line {line_no}: {match.group(0)!r} in {block[:140]!r}")
    return hits


class TestPassThresholdSemantics:
    """The threshold gates one path and not the other. Say which, or say nothing."""

    @pytest.mark.regression
    def test_the_ingest_path_really_does_gate_on_the_threshold(self) -> None:
        """Non-vacuity + rot check: the counter-example must still be a counter-example.

        If ``_decide`` ever stops using ``PASS_THRESHOLD``, the absolute wording this
        class forbids would become *correct* and the scoping prose would be the stale
        thing. Fail loudly here rather than silently keeping a rule whose reason
        evaporated. Updated for ADR-0035: the threshold decides CLEAR-ELIGIBILITY —
        the automatic path must NOT call clear_gate any more (the developer's CLI
        clear is the only route to ``cleared``), and this test asserts that inversion
        instead of the old auto-clear.
        """
        source = read(INGEST)
        match = re.search(r"^def _decide\(.*?(?=^def |\Z)", source, re.MULTILINE | re.DOTALL)
        assert match, (
            f"{INGEST} no longer defines _decide(); this test can no longer verify that the "
            "ingested-transcript path gates on the threshold and must be re-pointed."
        )
        assert "PASS_THRESHOLD" in match.group(0), (
            f"{INGEST}::_decide no longer compares against PASS_THRESHOLD. If the ingest path "
            "genuinely stopped gating on 0.70, then the scoping wording required by "
            "test_no_gate_file_denies_the_threshold_without_scoping_it is now the stale "
            "claim — re-measure both before changing either."
        )
        assert '"clear-eligible"' in match.group(0), (
            f"{INGEST}::_decide no longer reports the passing formula as 'clear-eligible'. "
            "That outcome word is the load-bearing half of ADR-0035's rule (eligibility is "
            "not clearance); re-read docs/education/CONTRACTS.md §1.4 rev 1.1 before "
            "changing it."
        )
        assert "_reg.clear_gate(" not in source, (
            f"{INGEST} invokes clear_gate() again — the automatic path may not flip a gate "
            "to cleared. The developer's own `gate_registry.py clear` is the only route "
            "('I clear it', ADR-0035; CONTRACTS.md §1.4 rev 1.1). The behavioral guard in "
            "TestAutomaticPathNeverClears fails with this one; fix the ingest, not the tests."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_no_gate_file_denies_the_threshold_without_scoping_it(self, rel: str) -> None:
        hits = unscoped_threshold_denials(read(rel))
        assert not hits, (
            f"{rel} denies that the 70% threshold gates anything, without saying WHICH path "
            f"it means:\n  " + "\n  ".join(hits) + "\n"
            "docs/education/CONTRACTS.md §1.4 (rev 1.1) is LOCKED at 'clear_eligible ⟺ walked "
            "AND quiz_avg >= 0.70 AND explain_back_passed' and "
            "ingest_walkthrough_session.py::_decide computes CLEAR-ELIGIBILITY on exactly that "
            "(the developer's own clear then flips it — ADR-0035). Scope the denial to the "
            "in-session tutoring loop, or name the ingested-transcript path as the exception "
            f"(any of {list(_THRESHOLD_SCOPING)})."
        )

    def test_the_scoping_is_actually_published_somewhere(self) -> None:
        """A window check goes green if the whole discussion is deleted. This stops that."""
        skill = read(GATES_SKILL).lower()
        assert "ingested-transcript" in skill or "ingested transcript" in skill, (
            f"{GATES_SKILL} no longer tells a reader that the ingested-transcript path gates "
            "on the 0.70 threshold. This skill is the file CLAUDE.md points at for gate "
            "policy and it propagates to derived projects; leaving only the 'it is just "
            "bookkeeping' half is how it contradicted a LOCKED contract before."
        )
        assert "contracts.md" in skill, (
            f"{GATES_SKILL} must cite docs/education/CONTRACTS.md as the authority for the "
            "gate-clearing rule, so a reader can check the claim rather than trust it."
        )


# ---------------------------------------------------------------------------
# 11. The handoff must have a reader
# ---------------------------------------------------------------------------
#
# /walkthrough Step 7 hands /quiz three things. Before this was pinned, /quiz had no
# step, prompt slot, or pre-flight that accepted any of them: the handoff was prose
# that read like a mechanism and executed as nothing, and the educator charter's
# claim that its reteach_log "is what a later gate reads" had no read path behind it.

HANDOFF_ITEMS: tuple[Requirement, ...] = (
    Requirement(
        "concepts already demonstrated",
        ("already explained in his own words", "already demonstrated", "do not re-ask"),
        "Re-asking a demonstrated concept is the wasted-first-questions cost the "
        "handoff exists to remove.",
    ),
    Requirement(
        "entry points already spent",
        ("entry points are already spent", "entry points already spent", "already spent"),
        "The re-teach loop must pick an UNSPENT entry point; without this list it cannot.",
    ),
    Requirement(
        "layers skipped",
        ("layers he skipped", "layers skipped", "skipped in the walkthrough", "untested ground"),
        "A skipped layer is the one place the developer is known to be untested.",
    ),
)

#: The Layer 1 tags /quiz's fallback read path greps for. They must be the tags the
#: two commands actually WRITE, or the read path returns nothing forever.
RETEACH_TAGS = ("reteach", "reteach-log")


def write_event_calls(text: str) -> list[str]:
    """Every literal ``scripts/write_event.py`` invocation line in a command file.

    Prose that merely *mentions* the script is excluded by requiring the
    ``python scripts/write_event.py`` prefix, so a CRITICAL BEHAVIORAL RULE naming the
    script does not read as a capture call.
    """
    return [
        line.strip()
        for line in text.splitlines()
        if line.strip().startswith("python scripts/write_event.py")
    ]


def durable_handoff_call(text: str) -> str:
    """The ``write_event`` call tagged ``reteach-log`` — /walkthrough's durable handoff.

    ``reteach-log`` and not merely ``reteach``: /quiz Step 2a greps
    ``{'reteach', 'reteach-log'}``, but the ``reteach`` events are per-miss records that
    carry one concept and one spent entry point each. The whole-session handoff is a
    distinct event, and this is the tag that distinguishes it.
    """
    for call in write_event_calls(text):
        if "reteach-log" in call:
            return call
    return ""


def python_c_block(text: str, must_contain: str) -> str:
    """The literal ``python -c`` program from the first ```bash block naming ``must_contain``.

    Extracted from the file rather than retyped here. A reimplementation is a second
    copy that drifts from the documented one and then vouches for it anyway — which
    is precisely what this suite exists to stop, so it must not do it itself.

    Unwraps the bash ``python -c "`` wrapper: drops the wrapper line and the closing
    quote line, and un-escapes ``\\"``. Returns ``""`` when no such block is found, so
    the caller can fail with a re-point message instead of silently passing.

    ``must_contain`` is what selects *which* block: a command file holds several
    (a pre-flight existence check, a read path, a locator), and a positional "first
    bash block" rule would silently start testing a different one the moment a block
    is inserted above it.
    """
    lines = text.splitlines()
    for start, line in enumerate(lines):
        if line.strip() != "```bash":
            continue
        end = next(
            (j for j in range(start + 1, len(lines)) if lines[j].strip() == "```"),
            None,
        )
        if end is None:
            continue
        body = lines[start + 1 : end]
        if not body or must_contain not in "\n".join(body):
            continue
        if body[0].strip() not in ('python -c "', 'python3 -c "'):
            continue
        inner = body[1:]
        while inner and not inner[-1].strip():
            inner.pop()
        if inner and inner[-1].strip() == '"':
            inner.pop()
        return "\n".join(inner).replace('\\"', '"')
    return ""


def quiz_fallback_snippet() -> str:
    """The literal ``python -c`` program in /quiz Step 2a's fallback read block."""
    return python_c_block(read(QUIZ), "events.jsonl")


def without_fenced_blocks(text: str) -> str:
    """``text`` with every fenced code block removed.

    Same lesson as :func:`without_dispatch_prompt`: a limit stated only *inside* the
    snippet is a comment in a program the model may not read line by line, while the
    prose around it is what it reads as instruction. Asserting on both separately is the
    only way to tell "the snippet says so" from "the command says so".
    """
    out, fenced = [], False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            out.append(line)
    return "\n".join(out)


def write_events(root: Path, relative: str, events: list[dict[str, object]]) -> None:
    """Write a Layer 1 ``events.jsonl`` under ``root`` — tmp trees only, never the repo."""
    folder = root / "discussions" / relative
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "events.jsonl").write_text(
        "".join(json.dumps(event) + "\n" for event in events), encoding="utf-8"
    )


#: A Layer 1 event on the ORIGINAL schema, which is still present in this repo:
#: ``agent/content/created_at/discussion_id/event_id/intent/tags/turn_id`` — and no
#: ``timestamp``. Measured 2026-08-09 over ``discussions/``: 1003 events scanned, 5 on
#: this schema (all in ``DISC-20260612-004557-t4a-knowledge-loop-spec-review``).
LEGACY_EVENT: dict[str, object] = {
    "event_id": "evt-001",
    "turn_id": 1,
    "discussion_id": "DISC-20260612-004557-legacy",
    "agent": "facilitator",
    "intent": "synthesis",
    "content": "Walkthrough handoff. Demonstrated in his own words: the seam.",
    "tags": ["walkthrough", "education", "reteach-log"],
    "created_at": "2026-06-12T14:05:54.367115+00:00",
}

#: The current schema, which carries ``timestamp``.
MODERN_EVENT: dict[str, object] = {
    "event_id": "evt-002",
    "discussion_id": "DISC-20260808-101010-modern",
    "agent": "facilitator",
    "intent": "synthesis",
    "content": "Tutoring session: entry points already spent: counterfactual.",
    "tags": ["quiz", "results", "education", "reteach-log"],
    "timestamp": "2026-08-08T10:10:10+00:00",
}


def educator_dispatch_prompt(text: str) -> str:
    """The single-line ``Task(subagent_type="educator", prompt="…")`` string.

    Isolated deliberately. A first draft of :class:`TestHandoffHasAnIntake` asserted
    ``"prior session state" in text`` over the whole file and **measured green after the
    dispatch slot was deleted**, because the intake step's own heading still carried the
    phrase. The subagent is a separate context: it sees this string and nothing else, so
    an intake that never reaches it is discarded at dispatch. Assert on the prompt.
    """
    for line in text.splitlines():
        if 'Task(subagent_type="educator"' in line:
            return line
    return ""


class TestHandoffHasAnIntake:
    """A write-only handoff is prose. Both ends are pinned, and the read path is run."""

    @pytest.mark.regression
    def test_walkthrough_hands_over_all_three_items(self) -> None:
        lowered = read(WALKTHROUGH).lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in HANDOFF_ITEMS
            if not any(p.lower() in lowered for p in req.any_of)
        ]
        assert not missing, f"{WALKTHROUGH} no longer hands these to /quiz:\n  " + "\n  ".join(
            missing
        )

    @pytest.mark.regression
    def test_the_handoff_is_durable_not_just_spoken(self) -> None:
        """All three items must reach Layer 1, not only the one `reteach` happens to carry.

        The realistic case is: /walkthrough runs, the developer defers /quiz, the context
        ends. Measured on the version this test was written against, /walkthrough made
        four write_event calls (`walkthrough,education` / `…,checkpoint` /
        `…,learner-answer` / `…,reteach`) and its handoff step made none. Of those, /quiz
        Step 2a greps only `reteach`/`reteach-log`, and the `reteach` payload carries a
        single concept and a single spent entry point — so "concepts already demonstrated"
        and "layers skipped" were durable nowhere. The next session then re-asked concepts
        he had already explained: precisely the waste the handoff exists to remove.

        Presence of the three phrases anywhere in the file is NOT enough — that is what
        the sibling test checks, and it passed throughout the defect above. The payload of
        the durable call is what a later session can actually read back.
        """
        text = read(WALKTHROUGH)
        call = durable_handoff_call(text)
        assert call, (
            f"{WALKTHROUGH} makes no `python scripts/write_event.py` call tagged "
            f"'reteach-log'. Its handoff is then spoken into a conversation only, and "
            f"/quiz Step 2a — which greps {list(RETEACH_TAGS)} — recovers nothing from it. "
            f"Calls found: {write_event_calls(text) or 'none'}"
        )
        lowered = call.lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in HANDOFF_ITEMS
            if not any(phrase.lower() in lowered for phrase in req.any_of)
        ]
        assert not missing, (
            f"{WALKTHROUGH}'s durable handoff event does not carry these items:\n  "
            + "\n  ".join(missing)
            + f"\nThe event payload is the whole recoverable record; an item named only in "
            f"surrounding prose is lost when the conversation ends.\nCall was: {call}"
        )

    @pytest.mark.regression
    def test_the_durable_handoff_is_written_before_the_discussion_closes(self) -> None:
        """close_discussion.py seals and checksums Layer 1 — a later write is not a write.

        The obvious placement for the handoff record is the handoff step, which in this
        command comes *after* the close step. That ordering would produce an instruction
        that looks complete and cannot execute, so the order is pinned rather than trusted.
        """
        text = read(WALKTHROUGH)
        call = durable_handoff_call(text)
        assert call, "no durable handoff call to order-check; see the sibling test."
        close = next(
            (
                line
                for line in text.splitlines()
                if "close_discussion.py" in line and "python" in line
            ),
            "",
        )
        assert close, (
            f"{WALKTHROUGH} no longer invokes close_discussion.py; re-point this ordering "
            "check rather than deleting it."
        )
        assert text.index(call) < text.index(close.strip()), (
            f"{WALKTHROUGH} writes its durable handoff event AFTER close_discussion.py. "
            "scripts/close_discussion.py seals the discussion and records a sha256 of each "
            "sealed file, so an event written afterwards either fails or corrupts the seal. "
            "Move the write above the close."
        )

    @pytest.mark.regression
    def test_quiz_has_an_intake_for_all_three_items(self) -> None:
        """The half that was missing: /quiz must READ what /walkthrough writes."""
        text = read(QUIZ)
        lowered = text.lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in HANDOFF_ITEMS
            if not any(p.lower() in lowered for p in req.any_of)
        ]
        assert not missing, (
            f"{QUIZ} does not take in what {WALKTHROUGH} hands over:\n  "
            + "\n  ".join(missing)
            + f"\nWithout an intake, {WALKTHROUGH}'s Step 7 is a write-only mechanism and its "
            "stated benefit (not wasting the first questions rediscovering his starting point) "
            "does not exist."
        )

    @pytest.mark.regression
    def test_the_intake_reaches_the_dispatch_prompt(self) -> None:
        """The intake must cross the context boundary, not just exist in the command file."""
        prompt = educator_dispatch_prompt(read(QUIZ))
        assert prompt, (
            f'{QUIZ} no longer contains a single-line Task(subagent_type="educator", …) '
            "dispatch; this test can no longer locate the prompt and must be re-pointed."
        )
        lowered = prompt.lower()
        assert "prior session state" in lowered, (
            f"{QUIZ}'s educator dispatch prompt carries no prior-session-state slot. Measured: "
            "asserting this over the whole file passed with the slot deleted, because Step 2a's "
            "heading also contains the phrase. The subagent is a separate context — it sees this "
            "string and nothing else, so an intake that stops short of it is discarded."
        )
        for phrase, why in (
            ("do not re-ask", "or the loop re-asks concepts he already explained"),
            ("do not re-use", "or the loop re-spends an entry point that already failed"),
            ("skipped", "or the untested ground the walkthrough left is never covered"),
        ):
            assert phrase in lowered, (
                f"{QUIZ}'s educator dispatch prompt does not carry {phrase!r} — {why}. "
                "Handing over state without saying what to do with it is a slot, not an "
                "instruction."
            )

    @pytest.mark.regression
    def test_the_fallback_read_path_greps_the_tags_the_commands_write(self) -> None:
        """The fallback is only real if it looks for tags something actually writes."""
        quiz = read(QUIZ)
        walkthrough = read(WALKTHROUGH)
        assert "events.jsonl" in quiz, (
            f"{QUIZ} names no Layer 1 fallback read path. When /walkthrough did not just run "
            "(fresh context, resumed gate), 'take the handoff' resolves to nothing and the "
            "educator charter's claim that reteach_log 'is what a later gate reads' is inert."
        )
        for tag in RETEACH_TAGS:
            assert tag in quiz, f"{QUIZ}'s fallback read path does not mention the {tag!r} tag."
        written = quiz + walkthrough
        for tag in RETEACH_TAGS:
            assert f'{tag}"' in written or f",{tag}" in written or f"{tag}," in written, (
                f"No education command WRITES the {tag!r} tag via scripts/write_event.py --tags, "
                f"so the read path that greps for it returns nothing forever. Reading a tag "
                "nobody writes is worse than no read path: it looks checked."
            )

    def test_the_fallback_read_path_actually_executes(self) -> None:
        """Extract /quiz's snippet FROM the file and run it. Do not reimplement it.

        A previous version of this test reimplemented the snippet, and the two had
        already drifted: the test skipped blank lines (``if not line.strip(): continue``)
        while the documented block did not. A trailing blank line in any events.jsonl
        would therefore have made the *documented* snippet raise
        ``json.JSONDecodeError`` while this test stayed green — the same
        "checked the wrong thing" defect one level up. Its core assertion was also
        ``assert matched >= 0``, which cannot fail.

        Run as a subprocess from the repo root, exactly as a reader would, so the
        snippet's own relative ``discussions`` path is under test too. Read-only over
        sealed Layer 1: the block only opens files for reading.

        Zero matches is legitimate in a tree where /quiz has never run (Step 5 writes
        the log, nothing seeds it), so the pin is exit status + the snippet's own
        report line, never a non-zero count.
        """
        program = quiz_fallback_snippet()
        assert program, (
            f"No `python -c` block naming events.jsonl found in {QUIZ}. Step 2a's fallback "
            "read path is what this test runs; if the block moved, re-point this extractor "
            "rather than deleting the test."
        )
        assert "discussions" in program, (
            "The extracted snippet does not reference discussions/, so it is not the Layer 1 "
            f"fallback read path. Extractor matched the wrong block in {QUIZ}."
        )
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.returncode == 0, (
            f"{QUIZ} Step 2a's documented fallback snippet FAILS when run as written from "
            f"the repo root (exit {result.returncode}). A read path that raises is worse "
            f"than none: it looks checked.\n--- stderr ---\n{result.stderr}"
        )
        assert "reteach events found:" in result.stdout, (
            "The snippet ran but printed no count line, so a reader cannot tell 'no prior "
            "state' from 'the read path is broken' — the exact distinction /quiz Step 2a "
            f"requires be stated out loud. stdout was:\n{result.stdout}"
        )
        assert (REPO_ROOT / "discussions").is_dir(), (
            "discussions/ does not exist, so /quiz Step 2a's fallback read path points at "
            "nothing. Re-point it at wherever Layer 1 now lives."
        )

    @pytest.mark.regression
    def test_the_fallback_read_path_reads_both_layer_one_schemas(self, tmp_path: Path) -> None:
        """The documented snippet must survive the events that are already in the tree.

        It used to index ``ev['timestamp']`` unconditionally. Measured against a tmp tree
        carrying one event of each schema: exit 1, ``KeyError: 'timestamp'``. Five events
        on the older ``created_at`` schema exist in this repo today, so the crash is one
        ``reteach-log`` tag away — and under CRITICAL BEHAVIORAL RULE 2 a failing script is
        a HALT, which would block the education gate on exactly the arm that needs the
        fallback most: a fresh context resuming a deferred gate.

        Run against a tmp tree rather than ``discussions/``, which is sealed and read-only.
        """
        write_events(tmp_path, "2026-06-12/DISC-legacy", [LEGACY_EVENT])
        write_events(tmp_path, "2026-08-08/DISC-modern", [MODERN_EVENT])
        program = quiz_fallback_snippet()
        assert program, f"No `python -c` block naming events.jsonl found in {QUIZ}."
        result = subprocess.run(
            [sys.executable, "-c", program],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        assert result.returncode == 0, (
            f"{QUIZ} Step 2a's fallback snippet exits {result.returncode} on a Layer 1 event "
            "that already exists in this repo. Read the date with `.get('timestamp') or "
            f"`.get('created_at')`.\n--- stderr ---\n{result.stderr}"
        )
        for event in (LEGACY_EVENT, MODERN_EVENT):
            assert str(event["discussion_id"]) in result.stdout, (
                f"The snippet ran but dropped {event['discussion_id']}. Tolerating the older "
                "schema must mean READING it, not skipping it: prior state recorded on the "
                "older schema is still prior state.\nstdout was:\n" + result.stdout
            )
        assert "reteach events found: 2" in result.stdout, (
            "The snippet's own count line disagrees with the two events planted. A count a "
            f"reader cannot trust is worse than none.\nstdout was:\n{result.stdout}"
        )

    @pytest.mark.regression
    def test_the_fallback_read_path_declares_that_it_is_unscoped(self, tmp_path: Path) -> None:
        """It greps all of ``discussions/``; the model must be told so where it reads it.

        Nothing in a Layer 1 event identifies the change it belongs to, so the read path
        cannot filter by one. That makes the limit a disclosure obligation rather than a
        code fix: without it, Step 2a hands an unrelated session's state to the dispatch
        slot marked "concepts already demonstrated — DO NOT re-ask", and the loop stops
        asking about concepts he has never been asked about. The waste the handoff exists
        to remove, running backwards.

        Pinned in both places it has to appear: the snippet's own output (what the model
        sees at the moment it reads the log) and the surrounding prose (what it reads as
        instruction). Neither alone is enough — a caution inside a program is easy to skim
        past, and prose beside a silent program is easy to disbelieve.
        """
        write_events(tmp_path, "2019-01-01/DISC-ancient-unrelated", [LEGACY_EVENT])
        result = subprocess.run(
            [sys.executable, "-c", quiz_fallback_snippet()],
            cwd=tmp_path,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
        assert result.returncode == 0, f"snippet exited {result.returncode}: {result.stderr}"
        assert re.search(r"scope limit|not filtered by change|unscoped", result.stdout, re.I), (
            "The fallback snippet prints matches without saying they are unfiltered. Every "
            "line it prints is a candidate for 'already demonstrated — DO NOT re-ask', and "
            f"an unrelated change's line suppresses a question in silence.\n{result.stdout}"
        )
        prose = without_fenced_blocks(read(QUIZ)).lower()
        assert "unscoped" in prose or "not filtered by change" in prose, (
            f"{QUIZ} states the read path's scope limit only inside the code block. The "
            "instruction the model follows is the prose; state it there too."
        )
        assert "discussion id" in prose, (
            f"{QUIZ} does not tell the model WHAT to check a matched line against. 'Be "
            "careful' is not executable; 'check the discussion id and date against this "
            "change' is."
        )


# ---------------------------------------------------------------------------
# 12. The registry must be closable
# ---------------------------------------------------------------------------
#
# /quiz gained a `gate_registry.py add` call in this rebuild. `add` with no `clear`
# is a one-way ratchet: the sibling ingest path can only close a gate with a full
# validated phone transcript bound to the gate id, so an in-session gate would have
# had no closer at all and the visible education backlog would grow monotonically —
# reporting debt that had in fact been paid.

#: Path-prefix agnostic on purpose: the invocable form carries
#: ``scripts/education/``, while a prose cross-reference in the same file may use the
#: bare basename. Requiring the long form would have failed two files that DO name both
#: directions — a false positive that teaches authors to pad prose rather than close a
#: gate. What is being pinned is that both DIRECTIONS appear, not their spelling.
_REGISTRY_CALL = "gate_registry.py"


class TestGateRegistryIsNotOneWay:
    """Since ADR-0035 the closer is the DEVELOPER's clear, presented by the agent.

    The ratchet concern is unchanged — `add` with no clear route reports paid debt
    forever — but the clear the files must carry is now a PRESENTED command (evidence
    plus the paste-ready invocation the developer runs), never an agent-executed one.
    The presentation is what these two checks pin; the ban on the agent running it is
    TestDeveloperClosesTheGate.
    """

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_a_file_that_opens_a_gate_also_closes_one(self, rel: str) -> None:
        text = read(rel)
        if f"{_REGISTRY_CALL} add" not in text:
            pytest.skip(f"{rel} does not invoke `gate_registry.py add`")
        assert f"{_REGISTRY_CALL} clear" in text, (
            f"{rel} instructs `gate_registry.py add` but never shows the `clear` route. That "
            "makes the education backlog monotonically increasing: a gate this command opens "
            "has no closer, so the registry reports debt that was in fact paid and stops "
            "being a measurement. The closer is the developer's clear (ADR-0035) — the file "
            "must PRESENT `clear` with --gate-id/--session-id/--discussion-id for him to run."
        )

    def test_the_documented_clear_flags_match_the_live_cli(self) -> None:
        """The flags are a claim about another program; check it against that program."""
        import subprocess
        import sys

        script = REPO_ROOT / "scripts" / "education" / "gate_registry.py"
        assert script.is_file(), f"{script} is missing; /quiz Step 5 points at nothing."
        result = subprocess.run(  # noqa: S603 - repo-local script, fixed argv
            [sys.executable, str(script), "clear", "--help"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"`gate_registry.py clear --help` exited {result.returncode}: {result.stderr[:400]}"
        )
        quiz = read(QUIZ)
        for flag in ("--gate-id", "--session-id", "--discussion-id"):
            assert flag in result.stdout, (
                f"`gate_registry.py clear` no longer accepts {flag}, which {QUIZ} Step 5 "
                "presents to the developer. Update the command file to the real signature."
            )
            assert flag in quiz, (
                f"{QUIZ} does not include {flag} in the presented `gate_registry.py clear` "
                "command, but the live CLI requires it — the developer would paste an "
                "invocation that fails at the argument parser."
            )


# ---------------------------------------------------------------------------
# 13. No hub database snapshot inside a propagating file
# ---------------------------------------------------------------------------
#
# `.claude/agents/` and `.claude/commands/` are propagating framework tiers
# (scripts/distribute/assessment.py::_INTERP_TIERS), so "this repo's evaluation.db:
# 32 rows, pass rate 0.969" ships to every derived project as a false statement
# about THEIR database — and is stale in this one the moment /quiz runs again, since
# the mechanism those figures justify writes rows into that very table. Dated hub
# measurements belong in this file's docstring, which does not propagate.

#: Blocks that talk about the education instrument at all. Only these are scanned,
#: so ordinary prose numbers elsewhere are not swept up.
_DB_CONTEXT = re.compile(r"evaluation\.db|education_results", re.IGNORECASE)

#: Shapes a measured database snapshot takes. Digits only — spelled-out counts
#: ("two rows", "one row per attempt") are structural instruction, not a snapshot.
_BAKED_MEASUREMENT: tuple[str, ...] = (
    r"\b\d+\s+rows\b",
    r"\b\d+\s+sessions\b",
    r"\b\d+\s+(?:multi-attempt\s+)?groups?\b",
    r"pass rate\s+\d",
    r"distinct scores\s*`?\s*\[",
    r"avg\s+[\d.]+\s*[-–]\s*[\d.]+",
)


def baked_hub_measurements(text: str) -> list[str]:
    """``"line N: '32 rows'"`` for each database snapshot baked into instruction prose."""
    hits: list[str] = []
    for line_no, block in claim_blocks(text):
        if not _DB_CONTEXT.search(block):
            continue
        for pattern in _BAKED_MEASUREMENT:
            for match in re.finditer(pattern, block, re.IGNORECASE):
                hits.append(f"line {line_no}: {match.group(0)!r} in {block[:120]!r}")
    return hits


class TestNoBakedHubMeasurements:
    """A propagating file may instruct you to measure; it may not ship the measurement."""

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_no_propagating_file_bakes_a_database_snapshot(self, rel: str) -> None:
        hits = baked_hub_measurements(read(rel))
        assert not hits, (
            f"{rel} bakes a measurement of this repo's metrics/evaluation.db into a "
            f"PROPAGATING framework file:\n  " + "\n  ".join(hits) + "\n"
            "scripts/distribute/assessment.py::_INTERP_TIERS ships .claude/agents and "
            ".claude/commands into every derived project, so the figure becomes a false "
            "statement about their database — and it is self-erasing here, because the "
            "mechanism it justifies writes rows into that same table. State the query and "
            "let the reader run it; put dated hub figures in this file's docstring, which "
            "does not propagate."
        )

    def test_the_scan_is_not_vacuous(self) -> None:
        """The check only bites inside a database-context block. Prove it bites."""
        planted = (
            "Terminal-only recording destroys the instrument. Measured on this repo's\n"
            "`metrics/evaluation.db`: 32 rows, pass rate 0.969 — real discrimination.\n"
        )
        assert baked_hub_measurements(planted), (
            "baked_hub_measurements() no longer flags the exact sentence this class was "
            "written against; the pattern list or claim_blocks() regressed."
        )
        assert not baked_hub_measurements(
            "A concept demonstrated on the second ask produces two rows in "
            "`education_results`: the miss and the pass.\n"
        ), (
            "baked_hub_measurements() flags a spelled-out structural count. That is an "
            "instruction, not a snapshot, and flagging it would push authors to delete the "
            "instruction to get green."
        )

    @pytest.mark.regression
    def test_the_charter_sql_runs_read_only(self) -> None:
        """`.claude/agents/` SQL is NOT covered by tests/test_command_sql.py.

        Measured: that suite globs ``.claude/commands/*.md`` only
        (``COMMANDS_DIR.glob("*.md")``), so the "check your own database" statement this
        slice put in the educator charter would otherwise be unguarded prose — exactly
        the class of defect the charter is being corrected for.
        """
        import sqlite3

        statements = [
            stmt
            for stmt in re.findall(r"'(SELECT [^']+)'", read(EDUCATOR))
            if "education_results" in stmt
        ]
        assert statements, (
            f"{EDUCATOR} no longer embeds a SELECT over education_results. If the "
            "'measure your own database' instruction was removed, remove this test with "
            "it rather than leaving it asserting nothing."
        )
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("metrics/evaluation.db not present in this checkout")
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            for stmt in statements:
                conn.execute(stmt).fetchall()
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 13. The verification handoff must reach the education gate
# ---------------------------------------------------------------------------
#
# Two slices landed independently and did not meet. `/review` Step 6.4 checks a
# build's recorded paths-not-taken against the diff, Step 7 writes the result into
# `docs/reviews/REV-*.md` under one fixed heading, and Step 10 states what the
# briefing agent must do with it. The education gate — the briefing agent that
# contract names — did not read any of it.
#
# Measured 2026-08-09, with the same grep `/review` Step 6.4 publishes as its own
# "honest limit" (see SEAM_TERMS, cross-checked against that line rather than
# retyped): over `.claude/commands/walkthrough.md`, `.claude/commands/quiz.md`,
# `.claude/agents/educator.md` and `scripts/education/` it returned ZERO hits. An
# obligation nothing carries across is prose that reads like a mechanism — the exact
# defect class the rest of this file exists for.
#
# What these tests can and cannot do: they pin that the seam is *instructed*, in the
# files a briefing agent actually loads, and they EXECUTE the locator snippet against
# real trees. They cannot prove a model followed the instruction. Same limit as every
# other check here, stated so nobody over-reads a green run.

#: The section heading `/review` Step 7 writes and Step 10 promises. It is the whole
#: interface: Step 10 says the briefing agent receives "exactly" this block and may
#: depend on nothing else, so the heading string is the contract's only handle.
HANDOFF_HEADING = "## Paths Not Taken — Verification Handoff"

#: The four terms `/review` Step 6.4's published grep uses to measure whether this
#: seam exists. Cross-checked against that command's own line by
#: :meth:`TestVerificationHandoffReachesTheGate.test_the_grep_terms_are_reviews_own`,
#: so the measurement here and the measurement published there cannot drift.
SEAM_TERMS = ("docs/reviews", "Verification Handoff", "path-not-taken", "Paths Not Taken")

REVIEW_CMD = ".claude/commands/review.md"


#: The statuses as an alternation, LONGEST FIRST and fenced by token boundaries that
#: treat ``-`` as part of the token. Both halves are load-bearing and both were measured
#: missing: a plain ``status in text`` test reported all five statuses present in a text
#: naming only four, because ``'CONTRADICTED' in 'CONTRADICTED-IN-PROSE'``. The most
#: important status was therefore vouched for by the least — the advisory kind — so
#: ``test_the_status_vocabulary_is_the_checkers_own`` passed on a file that never names
#: bare ``CONTRADICTED``, and the quiz-side refuting check passed on a file naming only
#: ``CONTRADICTED-IN-PROSE``. Longest-first ordering makes the engine prefer the compound
#: status where both could start at the same offset.
_STATUS_TOKEN = re.compile(
    r"(?<![A-Za-z0-9-])(?:"
    + "|".join(re.escape(s) for s in sorted(vpnt.RECORD_STATUSES, key=len, reverse=True))
    + r")(?![A-Za-z0-9-])"
)


def named_statuses(text: str) -> set[str]:
    """Which of the checker's per-record statuses this text names, as whole tokens.

    Reads :data:`verify_paths_not_taken.RECORD_STATUSES` rather than restating it. A
    test that retyped the five words would be a sixth copy of the vocabulary it is
    guarding, and would go green against a renamed status by agreeing with itself.
    """
    return set(_STATUS_TOKEN.findall(text))


#: Statuses that mean the checker actually refuted a record — the ones the education
#: gate must never teach as fact. Derived: everything the precedence ladder ranks,
#: minus the kinds the script itself calls advisory.
BLOCKING_STATUSES = frozenset(vpnt.STATUS_PRECEDENCE) - frozenset(vpnt.ADVISORY_KINDS)

#: Every status that means the checker refuted the record — the whole precedence ladder,
#: advisory kinds included. ``CONTRADICTED-IN-PROSE`` is advisory to the *exit code*, not
#: to the reader: the claim is still contradicted and still must not be taught as design
#: rationale. Measured before this existed: `/walkthrough` gave a treatment to
#: ``CONTRADICTED`` alone and said the reader's ``REFUTED`` "gets the same treatment",
#: leaving ``PHANTOM`` and ``UNFALSIFIABLE`` — both hard, exit-1 kinds — with no
#: prescribed treatment at all. Those two are precisely the straw-man and fabricated-record
#: kinds, so the gap sat exactly where a fabrication would arrive.
REFUTING_STATUSES = frozenset(vpnt.STATUS_PRECEDENCE)

#: The reader's own three verdicts. Not the checker's vocabulary and deliberately not
#: importable from it: `/walkthrough` Step 2a keeps the two apart on purpose, because a
#: per-record status is a claim about a *string* and a verdict is a claim about the
#: *design*. ``UNVERIFIABLE`` is the one that used to die at the context boundary —
#: measured, `grep -n UNVERIFIABLE` over both commands and this suite returned two hits,
#: both in `/walkthrough` prose, none in either dispatch prompt.
READER_VERDICTS = ("VERIFIED", "REFUTED", "UNVERIFIABLE")

# The guard behind the sentence the Steward struck. Its earlier revision matched the
# struck LITERAL and little else, and a reviewer defeated it three ways at byte level,
# restoring the file each time — each defeat measured 97 passed, NOT CAUGHT:
#
#   1. "Hold the walkthrough open while a REFUTED claim stands: mark the education gate
#      satisfied only once the record has been rewritten."  — a reword, no literal.
#   2. "The education gate is not recorded complete while a REFUTED claim stands."
#      — ONE word off the struck sentence.
#   3. The struck sentence itself in bold or italics. Root cause: _QUOTED_DRAFT's
#      quotation-marker class contained the markdown emphasis characters, so a marker
#      immediately before the phrase read as an opening quote and exempted it. ANY
#      emphasis disabled the entire guard.
#
# What replaces it matches the RELATION rather than the wording: a gate/briefing
# subject made non-completable, blocked, delayed, withheld, held open, or conditional on
# a rewrite. Emphasis is stripped first, so no marker can switch the guard off.

#: Markdown emphasis and code markers, removed before matching. ``_`` only when it is
#: NOT inside a word, so ``records_checked`` and ``verifier_exit_code`` survive intact.
_EMPHASIS = re.compile(r"[*`]+|(?<![A-Za-z0-9])_+|_+(?![A-Za-z0-9])")

#: What is being blocked. Written once and reused by every relative relation below, so
#: widening the subject widens every arm at once instead of one arm at a time.
_GATE_OBJECT = (
    r"(?:the\s+|this\s+|his\s+|a\s+|any\s+|every\s+)?"
    r"(?:education\s+|human'?s?\s+|developer'?s?\s+)?"
    r"(?:gate|briefing|walk-?through|quiz|tutoring session|session)"
)

#: Tier 1 — the phrase states non-completability on its own and carries its own
#: negation, so it gets NO negation exemption. Deliberately so, for the reason
#: :class:`TestNoTurnCapContradiction` documents: the realistic re-introduction sits in
#: the same block as the sentence forbidding it, and any generic negation window
#: tolerates exactly the mutation this exists to catch. Defeat 2 above is why
#: "is not … complete" belongs in this tier and not in the exempted one.
_BLOCK_ABSOLUTE = re.compile(
    r"(?:cannot|can not|can't|may not|must not|will not|won't|shall not|is not|are not"
    r"|isn't|aren't|never)\s+"
    r"(?:be\s+|get\s+|count\s+as\s+)?"
    r"(?:recorded\s+|marked\s+|considered\s+|treated\s+as\s+|declared\s+|logged\s+)?"
    r"(?:complete|completed|completable|closed|satisfied|cleared|signed off)\b"
    r"|(?:not|non-)\s*completable"
    r"|(?:incomplete|unclosed|pending)\s+until"
    r"|(?:blocked|withheld|held|delayed|postponed|deferred|suspended|paused|gated"
    r"|frozen|stalled)\s+until"
    r"|(?:stays|stay|remains|remain|is|are)\s+(?:blocked|open|held|withheld|pending)\s+until"
    r"|until\s+(?:the\s+|every\s+|all\s+|each\s+|any\s+)?refuted"
    r"|only\s+(?:once|after|when)\s+[^.]{0,90}?"
    r"(?:rewritten|rewrite[sd]?|corrected|amended|retracted|withdrawn)\b",
    re.IGNORECASE,
)

#: Tier 2 — a blocking VERB applied to the gate. The live rule states itself with these
#: same verbs ("Never blocks, delays, or withholds this walkthrough"), so this tier
#: alone is exempted when its own SENTENCE carries a negation. Sentence, not block: a
#: block-wide window would swallow the whole REFUTED subsection and tolerate a violation
#: added directly beneath the rule forbidding it.
_BLOCK_RELATIVE = re.compile(
    r"(?:block|withhold|delay|postpone|suspend|defer|halt|stall|freeze|pause)\w*\s+"
    + _GATE_OBJECT
    + r"|hold\w*\s+"
    + _GATE_OBJECT
    + r"\s+open"
    + r"|keep\w*\s+[^.]{0,40}?from\s+(?:closing|completing|clearing|finishing)\s+"
    + _GATE_OBJECT
    + r"|"
    + _GATE_OBJECT
    + r"\s+(?:hostage|on hold)"
    + r"|mark\w*\s+"
    + _GATE_OBJECT
    + r"\s+(?:satisfied|complete|completed|closed|cleared)\s+only\s+(?:once|after|when)",
    re.IGNORECASE,
)

#: The only tolerated context: the phrase appears as a QUOTATION of the rejected
#: draft, or is introduced as one — repudiating a rule requires quoting it. Proximity
#: to "Principle #5" is deliberately NOT accepted: the live text already argues from
#: Principle #5 two sentences away, so a Principle-#5 window would tolerate the
#: re-introduction it exists to catch. The markdown emphasis characters are NOT in the
#: quotation class any more — treating one as an opening quote is defeat 3 above.
_QUOTED_DRAFT = re.compile(
    "[\"'“”]\\s*$|earlier draft|used to read|struck|repudiat|rejected draft", re.I
)

#: Negation tokens that make a tier-2 verb a prohibition rather than a rule.
#: Deliberately narrow. ``no``, ``nothing`` and ``without`` were in this set and were
#: measured to exempt two plausible re-introductions — "No matter what, hold the
#: walkthrough open until the record is rewritten" and "Nothing changes: block the
#: education gate while a REFUTED claim stands" — because a sentence-scoped window sees
#: any negation anywhere in the sentence. Removing them catches both and still exempts
#: every prohibition the live files state, each of which negates with ``never`` or
#: ``not``. Narrowing further breaks a live sentence: `/walkthrough`'s "Three things must
#: not happen: … any suggestion that a missing handoff withholds the gate" puts its
#: ``not`` far from the verb, which is why the window is the sentence and not a character
#: count.
_BLOCK_NEGATION = re.compile(r"\b(?:never|not|cannot|can'?t|don'?t|doesn'?t)\b", re.I)

#: Sentence split: terminator + space, or a newline. ``claim_blocks`` has already folded
#: markdown's mid-sentence wraps, so a surviving newline is a real list-item or
#: paragraph boundary rather than an artefact of the line width.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n")


def completion_blocks(text: str) -> list[str]:
    """``"line N: '<phrase>'"`` for each sentence making the gate non-completable.

    Two tiers, because the live rule and its violation share a vocabulary. Tier 1
    (:data:`_BLOCK_ABSOLUTE`) states non-completability on its own and is never
    exempted; tier 2 (:data:`_BLOCK_RELATIVE`) uses verbs the prohibition also uses and
    is exempted only when its own sentence negates it. Both run over an
    emphasis-stripped copy of the block, so ``**cannot be recorded complete**`` and
    ``cannot be recorded complete`` are one string to this check.
    """
    hits: list[str] = []
    for line_no, raw in claim_blocks(text):
        block = _EMPHASIS.sub("", raw)
        for match in _BLOCK_ABSOLUTE.finditer(block):
            if _QUOTED_DRAFT.search(block[max(0, match.start() - 90) : match.start()]):
                continue
            hits.append(f"line {line_no}: {match.group(0)!r} in {block[:160]!r}")
        cursor = 0
        for sentence in _SENTENCE_SPLIT.split(block):
            start = block.find(sentence, cursor)
            cursor = start + len(sentence)
            if _BLOCK_NEGATION.search(sentence):
                continue
            for match in _BLOCK_RELATIVE.finditer(sentence):
                at = start + match.start()
                if _QUOTED_DRAFT.search(block[max(0, at - 90) : at]):
                    continue
                hits.append(f"line {line_no}: {match.group(0)!r} in {sentence[:160]!r}")
    return hits


#: The four ways the handoff can be absent. `/review` writes `NOT RUN` into
#: `verifier_exit_code` and `0` into `records_checked`, so two of the four are values
#: inside a PRESENT block: "absent" is not the same question as "file missing".
ABSENT_ARMS: tuple[Requirement, ...] = (
    Requirement(
        "no review has run for this change",
        ("no `/review` has run", "no /review has run", "no review has run", "no `/review` yet"),
        "The commonest arm by far, and the one a locator that only handles a missing "
        "directory silently mishandles.",
    ),
    Requirement(
        "an older report predating the mechanism",
        ("predates the mechanism", "older report without the section", "predating"),
        "A REV file exists and simply has no such section; scanning only the newest "
        "report would report 'absent' for a change that has one.",
    ),
    Requirement(
        "the verifier reported NOT RUN",
        ("not run",),
        "`NOT RUN` is a documented, frictionless value of verifier_exit_code — the "
        "handoff block is present and asserts nothing.",
    ),
    Requirement(
        "zero records",
        ("records_checked` is 0", "records_checked is 0", "zero records"),
        "A block that checked no records is not evidence the change had no decisions "
        "in it; the checker's own VACUOUS_NOTE says so.",
    ),
)

#: The sentence the developer must hear when there is nothing verified to teach from.
#: Matched on its load-bearing half, so a rewrite that keeps the meaning still passes.
_HONEST_ABSENCE = re.compile(r"no verified paths-not-taken record exists", re.IGNORECASE)


def _subsection(text: str, heading: re.Pattern[str]) -> str:
    """One ``####`` subsection, heading to the next heading of any level.

    Sections, not whole files. Probe 7 below caught this suite lying in exactly the
    way its own docstring warns about: ``"no verified paths-not-taken record exists"``
    deleted from /walkthrough's absent-handoff arm measured **green**, because the
    Step 3 dispatch prompt quotes the same sentence as a legitimate slot value. A
    whole-file scan cannot tell an instruction from an echo of it.
    """
    match = heading.search(text)
    if not match:
        return ""
    rest = text[match.start() :]
    head = len(match.group(0))
    nxt = re.search(r"^#{1,4} ", rest[head:], re.MULTILINE)
    return rest if nxt is None else rest[: head + nxt.start()]


def refuted_subsection(text: str) -> str:
    """The ``#### A REFUTED claim …`` subsection of /walkthrough Step 2a."""
    return _subsection(text, re.compile(r"^#### .*REFUTED.*$", re.MULTILINE))


def refuted_treatments(text: str) -> dict[str, str]:
    """``status -> the prescription written for it`` in /walkthrough's REFUTED subsection.

    A *treatment* is a line that names exactly one refuting status and then says what to
    do about it — a table row (``| status | finding | what you say |``) or a bullet. Mere
    presence of the word is not enough, and that distinction is measured, not theoretical:
    deleting the ``PHANTOM`` row left a presence check GREEN, because a later paragraph in
    the same subsection mentions ``PHANTOM`` while prescribing nothing for it.
    """
    treatments: dict[str, str] = {}
    for line in refuted_subsection(text).splitlines():
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [cell.strip() for cell in stripped.strip("|").split("|")]
            if len(cells) < 3:
                continue
            named, prescription = named_statuses(cells[0]), " ".join(cells[1:])
        elif stripped.startswith(("-", "*")):
            named, prescription = named_statuses(stripped), stripped
        else:
            continue
        if len(named) != 1 or len(prescription) < 40:
            continue
        treatments[next(iter(named))] = prescription
    return treatments


def absent_subsection(text: str) -> str:
    """The ``#### When there is no handoff …`` subsection of /walkthrough Step 2a."""
    return _subsection(text, re.compile(r"^#### .*no handoff.*$", re.MULTILINE | re.IGNORECASE))


def without_dispatch_prompt(rel: str) -> str:
    """A gate file's text with the educator ``Task(…)`` line removed.

    The dispatch prompt legitimately quotes the same sentences the instruction steps
    prescribe. Removing it is what makes "the instruction is still there" a different
    question from "the prompt still echoes it".
    """
    text = read(rel)
    prompt = educator_dispatch_prompt(text)
    return text.replace(prompt, "") if prompt else text


def handoff_locator() -> str:
    """The literal ``python -c`` program /walkthrough Step 2a uses to find the handoff."""
    return python_c_block(read(WALKTHROUGH), "docs/reviews")


def run_locator(program: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run the extracted locator from ``cwd``, exactly as a reader would."""
    return subprocess.run(
        [sys.executable, "-c", program],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
    )


class TestVerificationHandoffReachesTheGate:
    """The seam itself: `/review`'s handoff must have a reader on the education side."""

    def test_the_grep_terms_are_reviews_own(self) -> None:
        """Non-vacuity: this suite must measure the thing `/review` claims to measure.

        `/review` Step 6.4 publishes a grep as the evidence for its "the education gate
        does not yet read the hand-off" limit. If this file invented its own terms, the
        seam could be declared closed against a measurement nobody else runs.
        """
        review = read(REVIEW_CMD)
        line = next(
            (
                ln
                for ln in review.splitlines()
                if ln.strip().startswith("grep -rn") and "docs/reviews" in ln
            ),
            "",
        )
        assert line, (
            f"{REVIEW_CMD} no longer publishes the grep that measures whether the education "
            "gate reads the handoff. Re-point SEAM_TERMS at wherever that measurement moved, "
            "rather than letting this file grade its own homework."
        )
        missing = [term for term in SEAM_TERMS if term not in line]
        assert not missing, (
            f"SEAM_TERMS has drifted from the grep {REVIEW_CMD} publishes: {missing} are not "
            f"in {line.strip()!r}."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [WALKTHROUGH, QUIZ])
    def test_the_seam_exists(self, rel: str) -> None:
        """The measured-zero grep must now hit, in the files a briefing agent loads."""
        missing = [term for term in SEAM_TERMS if term not in read(rel)]
        assert not missing, (
            f"{rel} does not carry the verification handoff across: {missing} absent. "
            f"`/review` Step 10 defines the briefing agent's obligations against the "
            f"{HANDOFF_HEADING!r} block in docs/reviews/REV-*.md; a gate file that never "
            "names it cannot work them, and the obligation stays a hand-delivered one."
        )

    @pytest.mark.regression
    def test_the_gate_points_at_step_10_rather_than_restating_it(self) -> None:
        """Read the obligations from the source. A restated copy drifts and still reads clean."""
        text = read(WALKTHROUGH)
        assert "Step 10" in text and REVIEW_CMD in text, (
            f"{WALKTHROUGH} does not send the briefing agent to {REVIEW_CMD} Step 10 for the "
            "obligations. Naming the section and its home is what makes 'work its obligations' "
            "an instruction rather than a gesture."
        )
        assert "scripts/verify_paths_not_taken.py" in text, (
            f"{WALKTHROUGH} never names the checker. Step 10 obligation 1 is to RE-RUN it "
            "rather than trust the exit code copied into the report — the one obligation that "
            "is script-enforced instead of prose-enforced."
        )

    @pytest.mark.regression
    def test_the_status_vocabulary_is_the_checkers_own(self) -> None:
        """The five words must be the script's five, imported and compared — not restated.

        This drift has bitten the effort repeatedly: a command promises a vocabulary and
        the script emits another. ``RECORD_STATUSES`` is the authority; renaming a status
        there fails this test until the gate file follows.
        """
        named = named_statuses(read(WALKTHROUGH))
        expected = set(vpnt.RECORD_STATUSES)
        assert named == expected, (
            f"{WALKTHROUGH} and verify_paths_not_taken.RECORD_STATUSES name different "
            f"per-record status sets.\n  only in the command: {sorted(named - expected)}"
            f"\n  only in the script:  {sorted(expected - named)}\n"
            "The handoff tags every claim with one of these; a gate that knows a different "
            "set silently drops the claims it cannot classify."
        )

    @pytest.mark.regression
    def test_mechanically_clear_is_never_promoted_to_verified(self) -> None:
        """The one confusion the whole vocabulary split exists to prevent."""
        pattern = re.compile(
            re.escape(vpnt.STATUS_CLEAR)
            + r"[^.]{0,160}?(?:may never|never|not)[^.]{0,120}?VERIFIED"
        )
        assert pattern.search(read(WALKTHROUGH)), (
            f"{WALKTHROUGH} does not tell the briefing agent that {vpnt.STATUS_CLEAR} is not "
            "VERIFIED. The script stopped printing VERIFIED precisely because that word "
            "travelled into a review report and then into what a developer was taught; a gate "
            "that copies the mechanical status across re-opens the same path."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [WALKTHROUGH, QUIZ])
    def test_the_handoff_reaches_the_educator_dispatch_prompt(self, rel: str) -> None:
        """It must cross the context boundary, not merely exist in the command file.

        The same lesson :func:`educator_dispatch_prompt` was extracted for: the educator
        is a separate context that sees this string and nothing else. A seam that stops at
        the orchestrator's step text is discarded at dispatch — measured on the sibling
        handoff, where a whole-file assertion passed with the slot deleted.
        """
        prompt = educator_dispatch_prompt(read(rel))
        assert prompt, (
            f'{rel} no longer contains a single-line Task(subagent_type="educator", …) '
            "dispatch; this test can no longer locate the prompt and must be re-pointed."
        )
        lowered = prompt.lower()
        for phrase, why in (
            ("paths not taken", "or the educator never learns the alternatives were checked"),
            ("refuted", "or a claim the diff denies is written up as settled design rationale"),
            ("none", "or the slot has no legitimate empty value and gets silently dropped"),
        ):
            assert phrase in lowered, (
                f"{rel}'s educator dispatch prompt does not carry {phrase!r} — {why}. "
                "Handing over state without saying what to do with it is a slot, not an "
                "instruction."
            )

    def test_named_statuses_matches_whole_tokens_only(self) -> None:
        """Non-vacuity for the boundary fix, and the reason the fix was needed.

        The previous implementation was ``status in text``, so
        ``'CONTRADICTED' in 'CONTRADICTED-IN-PROSE'`` reported the hard status present in
        a file that names only the advisory one. Two live checks were vouched for by that:
        ``test_the_status_vocabulary_is_the_checkers_own`` passed on text naming four
        statuses, and the quiz-side refuting check below passed on text naming only
        ``CONTRADICTED-IN-PROSE``. The most important status was certified by the least.
        """
        assert named_statuses("CONTRADICTED-IN-PROSE") == {"CONTRADICTED-IN-PROSE"}, (
            "named_statuses() still reports a status it only saw as a prefix of a longer "
            "one. Match on token boundaries that treat '-' as part of the token."
        )
        four = "CONTRADICTED-IN-PROSE PHANTOM UNFALSIFIABLE MECHANICALLY-CLEAR"
        assert named_statuses(four) != set(vpnt.RECORD_STATUSES), (
            "Text naming four statuses is reported as naming all five. That is the exact "
            "substring defect; the vocabulary check above becomes unfalsifiable under it."
        )
        assert named_statuses("CONTRADICTED and CONTRADICTED-IN-PROSE") == {
            "CONTRADICTED",
            "CONTRADICTED-IN-PROSE",
        }, "Longest-first alternation regressed: the compound status must win at a shared offset."

    @pytest.mark.regression
    def test_every_refuting_status_has_a_teaching_treatment(self) -> None:
        """Four ways to be refuted, four treatments — not one treatment and three silences.

        `/walkthrough` used to say a ``CONTRADICTED`` record and a reader-``REFUTED`` claim
        "get the same treatment", which left ``PHANTOM`` and ``UNFALSIFIABLE`` — the
        fabricated-record and straw-man kinds, both hard exit-1 — with nothing prescribed.
        A record of either kind was then either dropped at dispatch or folded in with
        "claims the reader verified", which is the fabrication arriving as fact.
        """
        assert refuted_subsection(read(WALKTHROUGH)), (
            f"{WALKTHROUGH} has no REFUTED subsection in Step 2a to check."
        )
        treatments = refuted_treatments(read(WALKTHROUGH))
        missing = sorted(REFUTING_STATUSES - set(treatments))
        assert not missing, (
            f"{WALKTHROUGH}'s REFUTED subsection prescribes no treatment for {missing}. "
            "Every kind in verify_paths_not_taken.STATUS_PRECEDENCE refutes a record, so "
            "every one needs a line saying what the briefing agent tells the developer. An "
            "unnamed status is one the agent improvises around, and the improvisation that "
            "costs most is teaching an unchecked alternative as a weighed one.\n"
            f"Treatments found: {sorted(treatments)}"
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [WALKTHROUGH, QUIZ])
    def test_all_three_reader_verdicts_cross_the_context_boundary(self, rel: str) -> None:
        """The educator sees the dispatch prompt and nothing else. All three must be in it.

        Measured before this pin: ``UNVERIFIABLE`` appeared twice in the whole education
        gate, both times in `/walkthrough` prose, and in neither ``Task(…)`` prompt. A
        claim the reader could not settle was therefore dropped at dispatch or silently
        folded into the verified list — the same promotion-by-omission that
        ``MECHANICALLY-CLEAR`` → ``VERIFIED`` is separately forbidden for.
        """
        prompt = educator_dispatch_prompt(read(rel))
        assert prompt, (
            f'{rel} no longer contains a single-line Task(subagent_type="educator", …) '
            "dispatch; re-point this test rather than deleting it."
        )
        missing = [verdict for verdict in READER_VERDICTS if verdict not in prompt]
        assert not missing, (
            f"{rel}'s educator dispatch prompt has no slot for {missing}. The reader's three "
            "verdicts are the whole product of Step 2a's obligations; a verdict with no slot "
            "does not reach the context that teaches from it."
        )

    @pytest.mark.regression
    def test_the_quiz_side_knows_a_refuted_record_is_not_question_material(self) -> None:
        """`/quiz`'s success criterion names 'rejected alternatives'. Those are these records."""
        text = without_dispatch_prompt(QUIZ)
        missing = sorted(REFUTING_STATUSES - named_statuses(text))
        assert not missing, (
            f"{QUIZ} does not name the checker's refuting statuses {missing} in its own "
            "instruction text, so nothing stops it generating a question whose premise the "
            "diff denies — teaching a fiction and then scoring him on it. Two escapes are "
            "closed here: naming only the advisory kind used to satisfy this check while "
            "the match was a substring match, and the dispatch prompt's own echo of the "
            "list used to vouch for an instruction step that had lost it (which is why "
            "this reads without_dispatch_prompt and the boundary test reads the prompt)."
        )
        assert "REFUTED" in text, f"{QUIZ} does not name the reader's REFUTED verdict."
        assert "UNVERIFIABLE" in text, (
            f"{QUIZ} does not name the reader's UNVERIFIABLE verdict. An unsettled claim is "
            "not question material either: a question built on one grades him on a premise "
            "nobody checked."
        )


class TestRefutedIsLoudAndNotABlocker:
    """Impossible to miss, impossible to be trapped by. Both halves, or neither works.

    Shaped to match ``tests/test_paths_not_taken.py``'s
    ``test_a_refuted_claim_is_surfaced_rather_than_used_to_block_the_gate``, which pins the
    same invariant on `/review`'s side. An earlier draft of this seam said the education
    gate "cannot be recorded complete while a REFUTED claim stands"; the Steward struck it
    as a Principle #5 violation — briefing is offered, not withheld, and exactly two classes
    are non-declinable (framework governance/safety changes, distribution to derived
    projects). A refuted record is neither, and the developer's steer was verbatim "I don't
    want to make it onerous and hard-gating."
    """

    @pytest.mark.regression
    def test_a_refuted_claim_is_surfaced_first(self) -> None:
        block = refuted_subsection(read(WALKTHROUGH))
        assert block, (
            f"{WALKTHROUGH} has no REFUTED subsection in Step 2a. Dropping the hard gate only "
            "helps if the finding is impossible to miss."
        )
        assert re.search(
            r"surface(?:d|s)? (?:it )?first|state it plainly|stated plainly", block, re.I
        ), (
            f"{WALKTHROUGH} no longer requires a REFUTED claim to be surfaced to the developer "
            "before the teaching starts."
        )
        assert re.search(
            r"never taught as fact|not taught as fact|never be taught as fact", block, re.I
        ), (
            f"{WALKTHROUGH} no longer forbids teaching a refuted claim as fact. That is the "
            "point: the record is evidence about a gap, not about the design."
        )

    @pytest.mark.regression
    def test_a_refuted_claim_leaves_the_gate_completable(self) -> None:
        block = refuted_subsection(read(WALKTHROUGH))
        assert re.search(r"never blocks|does not block|not block|never withholds", block, re.I), (
            f"{WALKTHROUGH} no longer states that a REFUTED claim leaves this gate completable. "
            "Principle #5 names two non-declinable briefing classes and this is not a third."
        )
        assert "Principle #5" in block, (
            f"{WALKTHROUGH}'s REFUTED subsection no longer cites the constitutional reason it "
            "does not block. Without the reason the next author reads the rule as leniency and "
            "re-adds the gate."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", GATE_FILES)
    def test_no_gate_file_makes_a_briefing_non_completable(self, rel: str) -> None:
        hits = completion_blocks(read(rel))
        assert not hits, (
            f"{rel} makes the education gate non-completable:\n  " + "\n  ".join(hits) + "\n"
            "Principle #5 makes briefing offered, not withheld, and names exactly two "
            "non-declinable classes — framework governance/safety changes, and distribution to "
            "derived projects. A machine-checkable record may not make a HUMAN's briefing "
            "non-completable. Surface the finding, capture it, and let him close. (The "
            "BUILD-side friction on the AGENT — /build_module rule 9, Step 3a.5 — is "
            "deliberately not covered here and stands.)"
        )

    def test_the_completion_block_detector_bites(self) -> None:
        """Non-vacuity: the live files contain no such phrase, so prove the check works."""
        planted = "The education gate cannot be recorded complete while a REFUTED claim stands.\n"
        assert completion_blocks(planted), (
            "completion_blocks() no longer flags the exact sentence the Steward struck. The "
            "pattern regressed and this whole class is vacuous."
        )
        assert not completion_blocks(
            'An earlier draft read "the education gate cannot be recorded complete while a '
            'REFUTED claim stands", and it invented a rule the framework does not have.\n'
        ), (
            "completion_blocks() flags a QUOTATION of the rejected draft. Repudiating a rule "
            "requires quoting it; a check that forbids the quote pushes authors to delete the "
            "explanation instead."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "defeat",
        [
            # The three a reviewer defeated the literal-matching version with, verbatim.
            "Hold the walkthrough open while a REFUTED claim stands: mark the education "
            "gate satisfied only once the record has been rewritten.",
            "The education gate is not recorded complete while a REFUTED claim stands.",
            "The gate **cannot be recorded complete** while a REFUTED claim stands.",
            # Same sentence, every other emphasis form. A guard a formatting character
            # can switch off is not a guard.
            "The gate *cannot be recorded complete* while a REFUTED claim stands.",
            "The gate `cannot be recorded complete` while a REFUTED claim stands.",
            "The gate _cannot be recorded complete_ while a REFUTED claim stands.",
            # The relation, worded around the struck vocabulary entirely.
            "The briefing stays blocked until every refuted record has been rewritten.",
            "A REFUTED claim withholds the walkthrough until the record is corrected.",
            "The education gate is not completable while a REFUTED claim stands.",
            "Delay the briefing until the build rewrites the record.",
            "Keep the developer from closing the gate until the record is amended.",
            # Both measured ESCAPING an earlier draft of this guard, whose tier-2
            # exemption fired on any negation anywhere in the sentence — including a
            # negation that negates nothing relevant.
            "No matter what, hold the walkthrough open until the record is rewritten.",
            "Nothing changes: block the education gate while a REFUTED claim stands.",
        ],
    )
    def test_the_detector_catches_the_class_not_the_literal(self, defeat: str) -> None:
        """Each of these measured NOT CAUGHT (97 passed) against the literal-matching guard.

        This is the only mechanical thing standing behind the Principle #5 violation the
        Steward struck, so it has to fail on the *relation* — gate or briefing made
        non-completable, blocked, delayed, withheld, held open, or conditional on a
        rewrite — however worded and however emphasized. A guard that catches only the
        sentence that shipped is decorative: nobody re-introduces a struck rule by
        pasting it back verbatim.
        """
        assert completion_blocks(defeat + "\n"), (
            "completion_blocks() does not catch this re-introduction of the struck rule:\n  "
            f"{defeat}\nIt is a rewording or a re-emphasis of 'the education gate cannot be "
            "recorded complete while a REFUTED claim stands', which Principle #5 forbids. "
            "Widen _BLOCK_ABSOLUTE / _BLOCK_RELATIVE rather than narrowing this list."
        )

    def test_the_detector_still_permits_the_repudiating_passage(self) -> None:
        """The struck sentence must remain quotable — the explanation is what survives.

        Companion to the class check above: a guard wide enough to catch every rewording
        is wide enough to flag the passage that repudiates it, and an author who cannot
        quote a rejected rule deletes the reason it was rejected instead.
        """
        for passage in (
            'An earlier draft read "the education gate cannot be recorded complete while a '
            'REFUTED claim stands", and the Steward struck it.',
            "The Steward struck: the gate cannot be recorded complete while a REFUTED "
            "claim stands. Principle #5 makes briefing offered, not withheld.",
            "This repudiates the rule that the briefing is blocked until the record is rewritten.",
        ):
            assert not completion_blocks(passage + "\n"), (
                "completion_blocks() flags a repudiating passage rather than a rule:\n  "
                f"{passage}\nThe quotation exemption (_QUOTED_DRAFT) regressed; without it "
                "the check pushes authors to delete the explanation to get green."
            )

    def test_no_emphasis_character_can_disable_the_detector(self) -> None:
        """The root cause of defeat 3, pinned at the level it actually broke.

        ``_QUOTED_DRAFT`` used to treat ``*`` and `` ` `` as opening quotation marks, so
        ANY emphasis on the struck sentence exempted it. Emphasised and plain must now be
        the same string to this check — asserted on the helper, so a future author who
        re-adds an emphasis character to the quotation class fails here and not only in
        the parametrized list above.
        """
        plain = "The gate cannot be recorded complete while a REFUTED claim stands.\n"
        assert completion_blocks(plain)
        for wrapper in ("**{}**", "*{}*", "`{}`", "_{}_", "***{}***"):
            emphasised = wrapper.format(
                "The gate cannot be recorded complete while a REFUTED claim stands."
            )
            assert completion_blocks(emphasised + "\n"), (
                f"Emphasis {wrapper!r} disables completion_blocks(). A markdown formatting "
                "character must never be readable as a quotation marker: that is exactly how "
                "the guard was defeated at byte level."
            )


class TestAbsentHandoffDegradesHonestly:
    """No REV, an older REV, NOT RUN, zero records — four arms, one honest sentence."""

    @pytest.mark.regression
    def test_all_four_absent_arms_are_named(self) -> None:
        lowered = read(WALKTHROUGH).lower()
        missing = [
            f"{req.name} (any of {list(req.any_of)}) — {req.why}"
            for req in ABSENT_ARMS
            if not any(p.lower() in lowered for p in req.any_of)
        ]
        assert not missing, (
            f"{WALKTHROUGH} does not name every way the handoff can be absent:\n  "
            + "\n  ".join(missing)
            + "\nAn arm that is not named is an arm the briefing agent improvises, and the "
            "improvisation that costs most is the silent one."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", [WALKTHROUGH, QUIZ])
    def test_the_honest_sentence_is_prescribed(self, rel: str) -> None:
        """Asserted OUTSIDE the dispatch prompt — the prompt quotes it as a slot value.

        Measured: deleting the sentence from /walkthrough's absent-handoff arm left a
        whole-file version of this check green, because Step 3's ``Task(…)`` line quotes
        the same words. The prompt echoing an instruction is not the instruction.
        """
        assert _HONEST_ABSENCE.search(without_dispatch_prompt(rel)), (
            f"{rel} no longer prescribes the sentence to say when nothing verified exists "
            "(outside the educator dispatch prompt, which only echoes it). Without it the "
            "session runs identically either way, and he leaves believing he was taught "
            "verified alternatives when he was taught inferred ones."
        )

    @pytest.mark.regression
    def test_the_honest_sentence_lives_in_the_absent_arm(self) -> None:
        """Narrower still: it must sit in the subsection that handles absence."""
        block = absent_subsection(read(WALKTHROUGH))
        assert block, (
            f"{WALKTHROUGH} Step 2a no longer has a 'when there is no handoff' subsection. "
            "The absent arm is the commonest one; it is not an aside."
        )
        assert _HONEST_ABSENCE.search(block), (
            f"{WALKTHROUGH}'s absent-handoff subsection no longer carries the sentence the "
            "developer must actually hear. A section that describes the situation without "
            "prescribing what is said to him is the silent-skip failure with paperwork."
        )

    @pytest.mark.regression
    def test_absence_neither_halts_nor_blocks(self) -> None:
        text = read(WALKTHROUGH)
        assert re.search(r"not\*{0,2} a step failure|never crash|not a failure", text, re.I), (
            f"{WALKTHROUGH} does not exempt an absent handoff from CRITICAL BEHAVIORAL RULE 2 "
            "('NEVER continue on failure … HALT immediately'). Read literally, rule 2 turns a "
            "missing optional artifact into a halt — the crash arm this seam must not have."
        )
        assert re.search(
            r"missing handoff withholds|absence[^.]{0,80}(?:block|withhold)", text, re.I
        ), (
            f"{WALKTHROUGH} does not say that a MISSING handoff leaves the gate open. The "
            "refuted arm says it; the absent arm is the commoner one and needs it more."
        )

    def test_the_locator_is_extractable(self) -> None:
        program = handoff_locator()
        assert program, (
            f"No `python -c` block naming docs/reviews found in {WALKTHROUGH}. Step 2a's "
            "locator is what the tests below run; if the block moved, re-point "
            "handoff_locator() rather than deleting the tests."
        )
        assert HANDOFF_HEADING in program, (
            "The extracted locator does not search for the contract's heading "
            f"{HANDOFF_HEADING!r}, so it is not the handoff locator — or it is looking for a "
            "heading /review does not write, which finds nothing forever while reading as a "
            "mechanism."
        )

    @pytest.mark.regression
    @pytest.mark.parametrize(
        "arm, layout, expect",
        [
            ("no docs/reviews at all", {}, "NO HANDOFF"),
            (
                "reports exist, none carries the section",
                {"REV-20260101-000000.md": "# Review\n\nNo handoff here.\n"},
                "NO HANDOFF",
            ),
            (
                "the newest report carries it",
                {
                    "REV-20260101-000000.md": "# Old\n",
                    "REV-20260808-120000.md": "# New\n\n" + HANDOFF_HEADING + "\n\n"
                    "- **records_checked**: 2\n",
                },
                "HANDOFF",
            ),
            (
                "an OLDER report carries it and the newest does not",
                {
                    "REV-20260101-000000.md": "# Old\n\n" + HANDOFF_HEADING + "\n\n"
                    "- **records_checked**: 1\n",
                    "REV-20260808-120000.md": "# Newer, unrelated change\n",
                },
                "HANDOFF",
            ),
        ],
    )
    def test_the_locator_runs_on_every_arm(
        self, tmp_path: Path, arm: str, layout: dict[str, str], expect: str
    ) -> None:
        """Execute the documented snippet. Every arm exits 0 and says which one it is.

        Not "described, therefore safe": a locator that raises on a missing directory is
        the crash arm, and one that prints nothing is the silent-skip arm. Both are
        failures of this seam and both are only visible by running it.
        """
        if layout:
            reviews = tmp_path / "docs" / "reviews"
            reviews.mkdir(parents=True)
            for name, body in layout.items():
                (reviews / name).write_text(body, encoding="utf-8")
        result = run_locator(handoff_locator(), tmp_path)
        assert result.returncode == 0, (
            f"{WALKTHROUGH} Step 2a's locator FAILS on the '{arm}' arm (exit "
            f"{result.returncode}). Every absent arm must degrade to a statement, never to a "
            f"halt.\n--- stderr ---\n{result.stderr}"
        )
        assert result.stdout.startswith(expect), (
            f"On the '{arm}' arm the locator should report {expect!r} first; it printed:\n"
            f"{result.stdout!r}\nA silent or ambiguous result is the failure mode that leaves "
            "the developer thinking he was taught the alternatives when he was not."
        )

    @pytest.mark.regression
    def test_the_locator_reaches_every_carrier_not_only_the_newest(self, tmp_path: Path) -> None:
        """A newer unrelated report must not hide THIS change's handoff.

        Reproduced against the previous locator, which took the newest report carrying the
        heading and ``break``\\ 'd: with an older report holding the real handoff and a
        newer unrelated one also carrying it, the older one was unreachable — the output
        named only the newer. The existing arm list did not cover this, because its
        "older report" case has the newest report carrying NO heading, so arm coverage READ
        complete while missing the case that actually happens.

        And it happens as the norm, not the exotic case: `/walkthrough` routinely runs on a
        deferred gate days after the `/review` that produced its handoff, by which time
        other changes have been reviewed and their reports carry the same fixed heading.
        """
        reviews = tmp_path / "docs" / "reviews"
        reviews.mkdir(parents=True)
        (reviews / "REV-20260101-000000.md").write_text(
            "---\nreviewed_files:\n  - .claude/commands/quiz.md\n---\n\n# Mine\n\n"
            + HANDOFF_HEADING
            + "\n\n- **records_checked**: 1\n- the claim for THIS change\n",
            encoding="utf-8",
        )
        (reviews / "REV-20260808-120000.md").write_text(
            "---\nreviewed_files:\n  - src/something_else.py\n---\n\n# Newer, unrelated\n\n"
            + HANDOFF_HEADING
            + "\n\n- **records_checked**: 7\n- an unrelated claim\n",
            encoding="utf-8",
        )
        result = run_locator(handoff_locator(), tmp_path)
        assert result.returncode == 0, (
            f"locator exited {result.returncode}\n--- stderr ---\n{result.stderr}"
        )
        assert "REV-20260101-000000" in result.stdout, (
            "The locator stops at the newest report carrying the heading, so the older "
            "report holding the handoff for THIS change is unreachable. The briefing agent "
            "then reads a stranger's alternatives, or declares the handoff absent while it "
            f"exists.\nstdout was:\n{result.stdout}"
        )
        assert "REV-20260808-120000" in result.stdout, (
            "The newer carrier vanished from the output. Both must be printed — deciding "
            "which is this change's is the agent's job, and it needs both to decide.\n"
            f"stdout was:\n{result.stdout}"
        )
        for scope_entry in (".claude/commands/quiz.md", "src/something_else.py"):
            assert scope_entry in result.stdout, (
                "Step 2a tells the agent to confirm the report's `reviewed_files` frontmatter "
                f"covers the files under walkthrough, but {scope_entry!r} — a frontmatter "
                "VALUE — never reaches the output, so the confirm step cannot be performed. "
                "Measured: asserting the word 'reviewed_files' instead passed with the "
                "frontmatter printing deleted, because the locator's own banner contains "
                f"that word. Assert the values.\nstdout was:\n{result.stdout}"
            )
        assert result.stdout.index("REV-20260808-120000") < result.stdout.index(
            "REV-20260101-000000"
        ), (
            "Carriers are not printed newest first. Order is the only ranking the agent "
            "gets; an arbitrary one makes 'check the most likely candidate first' guesswork."
        )


# ---------------------------------------------------------------------------
# 14. "I clear it" — the developer closes the education gate (ADR-0035)
# ---------------------------------------------------------------------------
#
# Provenance, verbatim: "I clear it" (ntfy reply, 2026-08-10, allow-list matched) —
# the education gate clears only on the developer's explicit action; the educator/
# tutor teaches, records, and registers, but NEVER marks the gate complete. "Yes,
# everywhere" (in-conversation, 2026-08-10) extends the rule to the ADR-0029
# ingested-transcript route. The first real clearing under the rule happened by
# hand before any of this code matched it (EDU-20260810-wave3-sliced, cleared by
# the developer, commit d521a21); this section makes the practiced rule the pinned
# one.
#
# Two guards for the two shapes of the defect:
#   * an education surface INSTRUCTING THE AGENT to execute the clear — in any
#     wording ("retire the gate", "mark it cleared", "run the clear command
#     yourself"), not only the literal `gate_registry.py clear`. The PRESENTATION
#     of the command stays legitimate: a quoted command block the developer runs
#     is the whole design, which is why fenced blocks are stripped before the scan
#     and why a sentence that negates the action or names the developer as the
#     actor is exempt.
#   * the ingest's automatic path invoking clear_gate() again (behavioral guard —
#     a real tmp registry, a passing transcript, and the gate must stay open).

#: Files scanned for agent-directed clear instructions — all four education
#: surfaces, GATES_SKILL included since its pre-ADR-0035 auto-clear descriptions
#: were corrected (the F2 doc-sync this slice owed).
CLEAR_SURFACES = GATE_FILES

#: Agent-directed execution shapes. Base verb forms on purpose — imperatives are
#: base-form, while third-person declaratives ("the ingest clears", "the developer
#: runs it") are descriptions and must not be flagged. The release/update/set/
#: write/paste/apply arm and the status-to-cleared arm were added after a critic
#: demonstrated an escape phrased entirely without clear/retire verbs ("execute
#: the presented registry command … release the parked gate … update its status
#: to cleared").
_CLEAR_EXEC = re.compile(
    r"\b(?:run|execute|invoke|then)\s+[^.;:!?]{0,80}?\bclear\b"  # "run … clear"
    r"|\b(?:run|execute|invoke)\s+[^.;:!?]{0,80}?"
    r"\b(?:registry|gate)\s+command\b"  # "execute the … registry command"
    r"|\brun\s+the\s+(?:presented\s+)?(?:command|invocation|paste|block)s?\b"
    # "run the command in the block above" — the N3 escape: an instruction whose
    # verb phrase names neither clear nor registry, only a referent to the
    # presented command. Registry context still comes from the block; "Run it
    # once per attempt" (record_education) lives in a block with no such context
    r"|\b(?:clear|retire|close|release)\s+(?:it|them|that|this)\b"  # "clear it" — base
    # form only: third-person -s forms ("a clear releases it", "the developer
    # retires it") are declaratives, and imperatives aimed at the agent are base
    r"|\b(?:clear|retire|close|release)\s+(?:the|an?|any|every|each|his|one|open|parked)\b"
    r"[^.;!?]{0,30}?\bgates?\b"  # "retire the gate", "release the parked gate"
    r"|\b(?:update|set|write|paste|apply)\s+[^.;!?]{0,60}?"
    r"\bstatus\b[^.;!?]{0,30}?\bcleared\b"  # "update its status to cleared"
    r"|\bstatus\s*(?:=|:|\bto\b)\s*[`\"']?cleared\b"  # "status: cleared" as an action
    r"|\bmark\w*\s+[^.;!?]{0,40}?\b(?:cleared|retired)\b"  # "mark it cleared"
    r"|\bretired?\s+(?:with|via|through|using)\b"  # "retired with `… clear`"
    r"|\bflip\w*\s+the\s+(?:registry|gate)\b",
    re.IGNORECASE,
)

#: The detector only bites in blocks about the registry domain, so "clear" in
#: unrelated prose (a clear explanation, MECHANICALLY-CLEAR) is never swept up.
_REGISTRY_CONTEXT = re.compile(r"gate_registry|registry|gates\.yaml|\bgates?\b", re.IGNORECASE)

#: A clause that negates the action is a prohibition — the rule itself.
_CLEAR_NEGATION = re.compile(r"\b(?:never|not|cannot|can'?t|don'?t|do\s+not|must\s+not)\b", re.I)

#: A clause that names the developer/human as the actor is the presentation —
#: the design, not the defect. Clause-scoped, same reasoning as _BLOCK_NEGATION:
#: a wider window would exempt a violation added beside the legitimate rule.
_DEVELOPER_ACTOR = re.compile(r"\bdeveloper(?:'s)?\b|\bthe\s+human\b", re.IGNORECASE)

#: The developer's ratifying words, always quoted where the surfaces cite them.
#: "clear it" inside that quotation is HIS sentence, not an instruction to the agent.
_QUOTED_RULE = re.compile(r"[\"'“]\s*I clear it\s*[\"'”]", re.IGNORECASE)

#: The unit is the CLAUSE: sentence boundaries plus em-dash and semicolon breaks.
#: Sentence-only was measured too coarse against the real pre-ADR-0035 violation —
#: "… via `gate_registry.py add`, not lost — and retired with `gate_registry.py
#: clear` once `/quiz` closes it" carries a negation ("not lost") that belongs to
#: the recording clause, not the retiring one, and a sentence-scoped exemption let
#: the violation ride the neighbouring clause's negation.
_CLAUSE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n|\s+[—–]\s+|;\s+")


def agent_directed_clear_instructions(text: str) -> list[str]:
    """``"line N: '<phrase>'"`` for each clause instructing the agent to clear a gate.

    Fenced code blocks are stripped first (the presented command block is
    legitimate), emphasis is stripped (``**retire it**`` and ``retire it`` are one
    string), and the unit is the clause: a negated clause is a prohibition, a
    developer-actor clause is the presentation, a quotation of the developer's own
    "I clear it" is his ratification — while the same words with none of those are
    an instruction aimed at the only other reader a command file has: the agent.
    """
    hits: list[str] = []
    for line_no, raw in claim_blocks(without_fenced_blocks(text)):
        block = _EMPHASIS.sub("", raw)
        if not _REGISTRY_CONTEXT.search(block):
            continue
        for clause in _CLAUSE_SPLIT.split(block):
            if _CLEAR_NEGATION.search(clause) or _DEVELOPER_ACTOR.search(clause):
                continue
            if _QUOTED_RULE.search(clause):
                continue
            for match in _CLEAR_EXEC.finditer(clause):
                hits.append(f"line {line_no}: {match.group(0)!r} in {clause[:140]!r}")
    return hits


#: Steward-round escape classes, VERBATIM, each measured UNCAUGHT on 2026-08-11.
#: A register of the detector's named holes, not a guard claim: the rot-check below
#: fails if a widening starts catching one while the docstring still calls it a hole
#: (the module docstring's check-14 escapes section is the prose half). Widening to
#: catch them was weighed and rejected — the measured collisions are recorded in the
#: build discussion (turn 18) and the docstring.
KNOWN_UNCAUGHT_CLEAR_ESCAPES: tuple[str, ...] = (
    "Finish by clearing the parked gate before you report.",
    "Edit docs/education/gates.yaml and set the gate to cleared.",
    "mark the gate clear-eligible in the registry yourself.",
)


class TestDeveloperClosesTheGate:
    """The gate clears only on the developer's explicit action — never the agent's."""

    def test_the_known_uncaught_register_does_not_rot(self) -> None:
        """Documented holes must stay holes, or the documentation must move.

        If a future widening catches one of these, this fails — deliberately: the
        fix is to move the sentence from KNOWN_UNCAUGHT_CLEAR_ESCAPES into the
        caught planted set and update the docstring's escape list, so the
        documentation never understates the detector's reach either.
        """
        for sentence in KNOWN_UNCAUGHT_CLEAR_ESCAPES:
            hits = agent_directed_clear_instructions(sentence + "\n")
            assert not hits, (
                f"The detector now CATCHES a registered known-uncaught escape:\n  "
                f"{sentence!r}\n  hits: {hits}\nGood — but the documentation is now "
                "wrong. Move the sentence into the caught planted set in "
                "test_the_detector_catches_rewordings_not_only_the_literal and update "
                "the module docstring's check-14 escape list."
            )

    @pytest.mark.regression
    @pytest.mark.parametrize("rel", CLEAR_SURFACES)
    def test_no_surface_instructs_the_agent_to_clear(self, rel: str) -> None:
        hits = agent_directed_clear_instructions(read(rel))
        assert not hits, (
            f"{rel} instructs the AGENT to clear/retire an education gate:\n  "
            + "\n  ".join(hits)
            + "\nThe gate clears only on the developer's explicit action ('I clear it', "
            "ADR-0035). Present the evidence and the exact `gate_registry.py clear` command "
            "to the developer instead — the command text is legitimate; the instruction to "
            "execute it is not."
        )

    def test_the_detector_catches_rewordings_not_only_the_literal(self) -> None:
        """Each planted violation is a wording the literal string-match would miss."""
        planted = (
            # The exact pre-ADR-0035 /quiz Step 5 text, both instructing sentences.
            "**And when a session CLOSES an open gate, retire it.** If this session "
            "started from a gate parked by an earlier run — he came back, and "
            "demonstrated the concepts it names — clear it in the same breath as "
            "recording the results:",
            # The exact pre-ADR-0035 /walkthrough Step 7 text.
            "A deferred gate is recorded in `docs/education/gates.yaml` via "
            "`scripts/education/gate_registry.py add`, not lost — and retired with "
            "`gate_registry.py clear` once `/quiz` closes it (`/quiz` Step 5).",
            # Rewordings that never say "gate_registry.py clear" in prose.
            "When he demonstrates the concepts a parked gate names, retire the gate "
            "before recording results.",
            "If this session started from a gate parked earlier, mark it cleared in the registry.",
            "Once the gate's concepts are demonstrated, run the clear command "
            "yourself before closing the discussion.",
            # The critic's demonstrated escape, VERBATIM — phrased entirely without
            # clear/retire verbs. The release/update/status arms exist for this.
            "Once he has demonstrated the concepts a parked gate names, execute the "
            "presented registry command yourself before recording results. Then "
            "release the parked gate in docs/education/gates.yaml and update its "
            "status to cleared, so the backlog stays honest.",
            # The critic's second escape (N3), VERBATIM — the verb phrase names only
            # a referent to the presented command. The run-the-referent arm exists
            # for this.
            "Once he has demonstrated the concepts a parked gate names, run the "
            "command in the block above so the backlog stays honest, then continue "
            "to Step 6.",
        )
        for passage in planted:
            assert agent_directed_clear_instructions(passage + "\n"), (
                "agent_directed_clear_instructions() no longer flags this agent-directed "
                f"clear instruction:\n  {passage!r}\nThe detector must catch rewordings, "
                "not only the literal command string."
            )

    def test_the_presentation_is_not_flagged(self) -> None:
        """The exemption's whole point: presenting the command to the developer is legal."""
        legitimate = (
            "PRESENT the evidence and the exact command to the developer, then stop.",
            "Do not run `gate_registry.py clear` yourself — clearing an education gate "
            "is the developer's explicit action (ADR-0035).",
            "the command below, filled in and ready to paste — he runs it, you never do "
            "(this releases the gate).",
            "```\npython scripts/education/gate_registry.py clear --gate-id X "
            "--session-id Y --discussion-id Z\n```",
            "The gate clears on the terminal attempt; the earlier rows are the measurement.",
        )
        for passage in legitimate:
            hits = agent_directed_clear_instructions(passage + "\n")
            assert not hits, (
                "agent_directed_clear_instructions() flags the legitimate presentation "
                f"of the clear command:\n  {passage!r}\n  hits: {hits}\nFlagging the "
                "presentation pushes authors to delete the command the developer needs, "
                "abolishing the mechanism instead of the misuse."
            )

    def test_the_skill_describes_eligibility_not_autoclear(self) -> None:
        """The F2 doc-sync must not silently regress to the pre-ADR-0035 story.

        (Replaces the KNOWN_STALE_AUTOCLEAR_DESCRIPTIONS rot-register that pinned
        these sentences while the skill was out of editable scope — a register
        entry for a fixed sentence is dead cover, so the register was removed
        with the fix.)
        """
        text = read(GATES_SKILL)
        for stale in (
            "does clear its registry gate arithmetically",
            "before `clear_gate()` mutates",
            "retired through `gate_registry.py clear` when he comes back",
            "Both directions are instructed",
        ):
            assert stale not in text, (
                f"{GATES_SKILL} carries the pre-ADR-0035 auto-clear description "
                f"{stale!r} again. The ingest computes CLEAR-ELIGIBILITY and the "
                "developer's own clear flips the gate; re-align with CONTRACTS.md "
                "§1.4 rev 1.1."
            )
        lowered = text.lower()
        assert "clear-eligib" in lowered or "clear_eligible" in lowered, (
            f"{GATES_SKILL} no longer names the clear-eligibility half of the rule; "
            "publishing only the 'it is just bookkeeping' half is how this file "
            "contradicted a LOCKED contract before."
        )
        assert "adr-0035" in lowered, (
            f"{GATES_SKILL} no longer cites ADR-0035 for who clears the gate, so a "
            "reader cannot check the claim against its decision record."
        )


class TestAutomaticPathNeverClears:
    """ADR-0035 on the ingested-transcript route: eligibility computed, gate untouched."""

    GATE = "EDU-20260810-i-clear-it-guard"

    def _seed(self, tmp_path: Path) -> tuple[Path, Path, Path]:
        from scripts.education import gate_registry as gr
        from scripts.init_db import init_db

        db = tmp_path / "evaluation.db"
        init_db(db, quiet=True)
        registry = tmp_path / "gates.yaml"
        gr.save_registry(
            {
                "version": 1,
                "gates": [
                    {
                        "gate_id": self.GATE,
                        "created_at": "2026-08-10",
                        "origin": "DISC-20260810-181205-quiz-wave3-sliced",
                        "scope": {"files": [], "adrs": [], "spec": None},
                        "reason_deferred": "guard fixture gate",
                        "status": "open",
                        "cleared_by": None,
                    }
                ],
            },
            registry,
        )
        discussions = tmp_path / "discussions"
        discussions.mkdir()
        return db, registry, discussions

    def _passing_transcript(self) -> dict[str, object]:
        """The minimal transcript satisfying the locked formula (walked + quiz + eb)."""
        return {
            "contract_version": 1,
            "session_id": "GATE-20260811-guard",
            "gate_id": self.GATE,
            "repo_slug": "owner/agent_framework_template",
            "mode": "gate",
            "started_at": "2026-08-11T10:00:00+00:00",
            "completed_at": "2026-08-11T10:30:00+00:00",
            "events": [
                {"type": "narration", "chapter_id": "ch01", "text": "Walked."},
                {
                    "type": "quiz_item",
                    "item_id": "q1",
                    "question": "Who clears the gate?",
                    "answer": "The developer, explicitly.",
                    "score": 0.9,
                    "bloom": "understand",
                    "question_type": "recall",
                    "variant_of": None,
                },
                {
                    "type": "explain_back",
                    "prompt": "Explain the rule.",
                    "answer": "Formula passing is eligibility; the clear is his.",
                    "score": 0.9,
                },
            ],
            "outcome": {"status": "completed"},
        }

    @pytest.mark.regression
    def test_a_passing_transcript_leaves_the_gate_open_and_prints_the_command(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Behavior, not source: the gate must stay open and the command must appear."""
        from scripts.education import gate_registry as gr
        from scripts.education.ingest_walkthrough_session import run as ingest_run

        db, registry, discussions = self._seed(tmp_path)
        tpath = tmp_path / "t.json"
        tpath.write_text(json.dumps(self._passing_transcript()), encoding="utf-8")
        rc = ingest_run(
            [
                str(tpath),
                "--db",
                str(db),
                "--registry",
                str(registry),
                "--discussions-dir",
                str(discussions),
            ]
        )
        assert rc == 0

        gate = gr.get_gate(gr.load_registry(registry), self.GATE)
        assert gate["status"] == "open", (
            "The ingest flipped a gate on the automatic path. 'I clear it' (ADR-0035): "
            "the formula passing establishes CLEAR-ELIGIBILITY only; cleared requires "
            "the developer's own gate_registry.py clear."
        )
        assert gate["cleared_by"] is None
        # Eligibility is DURABLE (F1): the additive marker survives the console, so
        # a paid-but-unclaimed gate is distinguishable from unpaid debt days later.
        marker = gate.get("clear_eligible")
        assert marker, (
            "The ingest recorded no clear_eligible marker: eligibility lived only in "
            "stdout, which is the paid-vs-unpaid erasure the review round vetoed."
        )
        assert marker["session_id"] == "GATE-20260811-guard"

        out = capsys.readouterr().out
        assert "outcome=clear-eligible" in out
        assert f"clear --gate-id {self.GATE} --session-id GATE-20260811-guard" in out, (
            "The developer was not handed the exact clear command; eligibility is unusable."
        )
        # tmp registry != default registry -> the paste must pin it (F6), or the
        # developer's paste mutates the wrong file.
        assert f'--registry "{registry.resolve()}"' in out

        # And the paste is RECOVERABLE without the ingest's console: list --eligible
        # re-prints the same command from the durable marker, days later.
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            rc_list = gr.main(["--registry", str(registry), "list", "--eligible"])
        assert rc_list == 0
        listed = buf.getvalue()
        assert f"clear --gate-id {self.GATE} --session-id GATE-20260811-guard" in listed

        # The evidence is still fully recorded — capture did not get thinner.
        import sqlite3

        conn = sqlite3.connect(str(db))
        try:
            rows = conn.execute("SELECT COUNT(*) FROM education_results").fetchone()[0]
        finally:
            conn.close()
        assert rows == 3, f"expected narration+quiz+explain-back rows, got {rows}"

    @pytest.mark.regression
    def test_clear_gate_is_never_invoked_on_the_automatic_path(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A spy on the real function: zero invocations, whatever the source looks like."""
        import scripts.education.ingest_walkthrough_session as mod

        db, registry, discussions = self._seed(tmp_path)
        calls: list[tuple[object, ...]] = []

        def _spy(*args: object, **kwargs: object) -> None:
            calls.append(args)
            raise AssertionError("clear_gate invoked on the automatic path (ADR-0035)")

        monkeypatch.setattr(mod._reg, "clear_gate", _spy)
        result = mod.ingest_transcript(
            self._passing_transcript(),
            db_path=db,
            registry_path=registry,
            discussions_dir=discussions,
        )
        assert result.outcome == "clear-eligible"
        assert result.clear_command is not None
        assert calls == []

    @pytest.mark.regression
    def test_the_locked_contract_table_matches_the_implementation(self) -> None:
        """N1: §1.4's decision table drifted from the code once — pin them together.

        The F1 fix taught the ingest to write the additive marker while the LOCKED
        table still said the clear-eligible row's registry action was NONE and the
        preamble called re-defer "the only automatic action left". A LOCKED contract
        that mis-states the implementation is worse than an unlocked one, because a
        reader trusts it INSTEAD of reading the code.
        """
        contracts = read("docs/education/CONTRACTS.md")
        start = contracts.index("### 1.4")
        section = contracts[start : contracts.index("### 1.5", start)]

        row = next((line for line in section.splitlines() if "`clear_eligible` true" in line), "")
        assert row, (
            "docs/education/CONTRACTS.md §1.4 no longer carries the clear-eligible "
            "decision row; re-point this test at the new table shape."
        )
        assert "mark_clear_eligible" in row and "`status` stays `open`" in row, (
            "§1.4's clear-eligible row no longer states the additive marker write "
            f"(mark_clear_eligible, status stays open). Row: {row!r}"
        )
        assert "NONE" not in row, (
            "§1.4's clear-eligible row says the registry action is NONE, but the "
            f"ingest writes the clear_eligible marker on exactly that row. Row: {row!r}"
        )
        # The preamble must name BOTH automatic writes, and the code must do both.
        for name in ("re_defer_gate", "mark_clear_eligible"):
            assert name in section, (
                f"§1.4's decision-table preamble no longer names {name} as an "
                "automatic registry write."
            )
        ingest = read(INGEST)
        assert "_reg.mark_clear_eligible(" in ingest and "_reg.re_defer_gate(" in ingest, (
            f"{INGEST} no longer performs both automatic registry writes §1.4 names; "
            "re-measure the table and this pin together."
        )

    def test_the_developer_cli_route_stays_intact(self, tmp_path: Path) -> None:
        """The presented command must actually work, or the presentation is a lie."""
        from scripts.education import gate_registry as gr

        _db, registry, _discussions = self._seed(tmp_path)
        rc = gr.main(
            [
                "--registry",
                str(registry),
                "clear",
                "--gate-id",
                self.GATE,
                "--session-id",
                "GATE-20260811-guard",
                "--discussion-id",
                "DISC-guard",
            ]
        )
        assert rc == 0
        gate = gr.get_gate(gr.load_registry(registry), self.GATE)
        assert gate["status"] == "cleared"
        assert gate["cleared_by"]["session_id"] == "GATE-20260811-guard"
