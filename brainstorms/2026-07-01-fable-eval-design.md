# Grill: Fable Eval Suite Design (inverted — Dan grills Fable)

> Status: complete
> Started: 2026-07-01 · Last updated: 2026-07-01

## Highlights
Session designed the eval harness + Fable 5 gold baseline for
agent_framework_template before Fable's July 7, 2026 sunset. Nine taxonomy
questions walked and resolved; all recommendations accepted (Q8 amended the
teaching format). Side artifact: the grill-yourself skill was born from this
session's inverted-grill pattern and is the bundled worked example's origin.
The week's budget law is perishability triage: Fable authors judgment
(tasks, manifests, rubrics, golds, decoys, vault, taxonomy); Sonnet builds
plumbing (harness code) after July 7.

## Key decisions
- Q1 VALIDITY — Bare-model control condition: every task runs framework-on
  AND framework-off, creating a 2×2 of model × scaffolding. Separates
  prompt failure from model incapacity. Runs only on non-Fable models (no
  pre-sunset cost). Doubles as quantified marketing evidence the template
  lifts weaker models.
- Q2 CHECKER CEILING — Rubrics are checklists of observable facts (Y/N),
  not quality adjectives; Fable's judgment is encoded into rubrics so a
  weaker judge only audits presence/absence. Fable authors 2–3 decoy
  transcripts per task (plausible-but-flawed, known defects) as a permanent
  judge-calibration set; if a judge can't score gold above decoys, that
  task's scores are flagged untrustworthy. Judging is gold-blind by default
  (judge sees rubric + candidate only).
- Q3 GROUND TRUTH — manifest.json per synthetic task lists planted flaws;
  the manifest is ground truth, not Fable's transcript. Fable's golden run
  is scored honestly against its own manifest (4-of-5 stays 4-of-5);
  future models can legitimately beat gold. Manifests self-heal: genuine
  accidental flaws found by candidates get appended with dated annotations.
  Spoke tasks use Dan's commit history / hand-verified lineage as truth.
  Dan's verification burden: ~15 min/task skimming manifests, same evening
  each batch is authored.
- Q4 GOODHART — Task split is 3 dev + 2 vault per command. Vault is
  authored and gold-baselined before July 7, gitignored in the public repo
  (alongside tasks-private/), opened only at declared milestones
  (post-audit, then quarterly). Vault tasks are distributionally similar
  but not derivative. Post-Fable canary protocol: Sonnet mints fresh tasks
  (no frontier gold) to detect benchmark-shaped overfitting. Vault is a
  smoke alarm, not a thermometer.
- Q5 SIGNAL VS. NOISE — Candidates get k=3 runs per task; harness reports
  median + range + flaw-detection RATE (reliability as its own column).
  Tiering rule: only trust differences with non-overlapping ranges;
  overlap means "use the cheaper model." Fable golds get k=2; agreement →
  enshrine better transcript; divergence → task-lint signal (tighten or
  flag the task). README must state the full run matrix explicitly so
  future-Dan doesn't quietly drop to k=1.
- Q6 CONSUMER — Four named consumers, each a first-class README section
  with its own emitted view: (1) tiering config (model_context_profiles
  .yaml): per-command granularity, cost beside capability, overlap rule
  drives routing; (2) audit regression gate: dev-set only, fast, delta-
  focused; (3) public marketing: public synthetic tasks only, stranger-
  reproducible, no cherry-picking; (4) future-model adoption: one-hour
  re-tier decision for new models. Any harness feature serving none of the
  four gets cut.
- Q7 OPPORTUNITY COST — Perishability triage is the budget law.
  Fable-only: tasks, manifests, checklist rubrics, golden runs, decoys,
  vault, grill-yourself taxonomy. Deferred to Sonnet post-July-7: ALL of
  Phase 4 (run_eval.py, judge plumbing, per-consumer views, README,
  scaffolding). Depth over breadth: full treatment for /review,
  /deliberate, security-specialist; if short, /goal-loop and /plan drop to
  2 tasks and qa-specialist drops before any decoy/vault task for a
  covered command. Reclaimed budget: ~1.5 evenings to a lineage-engine
  grill-me (temp tables, dynamic SQL, SSIS variable passing → ADRs +
  spec; Fable designs, Sonnet implements); ~0.5 evening to grill-yourself
  skill. Full template prompt audit explicitly deferred past July 7
  (Sonnet recovers ~80%).
- Q8 STALENESS — Every golden run records the template's git commit hash
  in summary.md. Framework-on golds are versioned photographs; at major
  version bumps they retire to history (archival record of frontier
  performance on template v1.x) rather than being discarded. Regression
  gate's same-model before/after diffs are the drift alarm. Frozen
  fixtures, manifests, and the bare-model track are inherently
  version-proof.
- Q9 LEAKAGE — Public tasks will eventually enter training data. Vault
  and spoke tasks never publish. For models released after the benchmark
  went public, treat public-task scores as suspect-high and let the vault
  cast the deciding vote (one line in README). Optional technical layer
  (not yet reviewed): canary strings in fixtures; public-vs-vault score
  gap as a contamination signal.
- FORMAT — grill-yourself uses THREE altitudes: (1) one-sentence headline,
  (2) plain-language layer (stakes, category, analogy), (3) technical
  layer on request. Never require the user to ask for simplification
  twice. "Explain" is a first-class verdict beside accept/amend/dig.
  Teaching is an explicit goal: name taxonomy categories aloud; success
  includes the user anticipating questions unaided.

## Open threads
- Execute the eval build itself (see HANDOFF-fable-eval-mission.md) —
  perishable work must complete before July 7, 2026.
- Q9's technical layer (canary strings, contamination-gap detection) was
  deferred to "tomorrow" and never reviewed; fold into README when the
  harness is built post-sunset.
- Polish pass on grill-yourself taxonomy wording after sleep.
- Lineage-engine grill-me session (~1.5 evenings) not yet scheduled.

## Flagged for others
- (none)

## Q&A log
### Session 1 — 2026-07-01
**Q1 (validity):** Sonnet 2.8 vs Fable 4.6 — prompt failure or model
incapacity? Design can't distinguish. **A:** "Accept, sorry"
**Q2 (checker ceiling):** Post-July-7 judge is weaker than the gold author
— can it recognize frontier quality? **A:** "Accept"
**Q3 (ground truth):** If gold transcripts are the answer key, Fable's
misses become baked-in truth. **A:** "Accept."
**Q4 (Goodhart):** The audit loop will tune the template against the eval.
**A:** "Accept."
**Q5 (signal vs. noise):** Single runs may measure dice rolls, including
Fable's own golds. **A:** "Accept."
**Interlude:** Dan requested slow-walk simplification; two-altitude
teaching adopted as default; grill-yourself skill scoped. Dan's framing:
frontier engagement transfers — the skill should teach, not just serve.
**Q6 (consumer):** Who reads the scores and what decision changes?
**A:** "Accept."
**Q7 (opportunity cost):** Is the eval worth its Fable-hours vs. the
lineage engine? **A:** "Accept."
**Q8 (staleness):** Do golds rot as the template evolves? **A:** "Except
however..." — amended: add a first-tier one-line headline above the
plain-language layer; three altitudes become the default. Q8
recommendation itself accepted.
**Q9 (leakage):** Does publishing the exam let future models study it?
**A:** Accepted at headline level; technical layer deferred.
