---
proposal_id: PROPOSAL-20260806-ac7-dispositions
title: "AC7 dispositions — every main-only file under scripts/, .claude/ and docs/"
type: proposal
status: revise-pending
date: 2026-08-06
approved_by: developer
approved_date: 2026-08-06
approval_suspended: 2026-08-07
review_id: REV-20260807-063650
spec_id: SPEC-20260805-210524
adr_id: ADR-0031
discussion_id: DISC-20260806-055721-v4-reconciliation
decision_makers: [developer]
risk_level: critical
---

> ## ⛔ APPROVAL SUSPENDED 2026-08-07 — R-B3 returned REVISE 4/4 with 8 BLOCKING findings.
> **Do not execute §9 against this revision.** See `docs/reviews/REV-20260807-063650.md`.
> Known-wrong in this text: `src/telemetry/` is **16 files / 6,153 lines**, not 17 / 1,412
> (so C1 is **7,565 lines**, not 2,824, and D2 is **21** files, not 22); §2.1's "instruction
> surface still shrinks" is measured against `main`, not the v4 base — base-relative it is a
> **5.3× re-inflation** (866 → ~4,559); most §5.3 R-B4 "retained reader" claims do not hold;
> AC12 is contradicted and never mentioned; **44 `discussions/` files are undispositioned,
> which makes the merged tree fail AC2's own new tethering check**. Requires rev 2 and
> developer **re-approval** — the original approval preceded this review.
>
> **Superseded status line: APPROVED by the developer 2026-08-06 (Principle #7 / merged #6).**
> All six contested calls (§4) are decided, and the seven-principle constitution
> (ADR-0031 Decision 6) is **ratified as written**. This becomes **ADR-0031 Appendix B**,
> seeded at merge into `docs/education/dispositions.md` as the live referent — the ADR is
> immutable under Principle #4, so the live list lives outside it (same pattern as
> Appendix A → `governance-mechanisms.md`).
>
> **Still required before AC9:** R-B3 independent-context review of this classification. It
> has not run. Approval of the dispositions is not a substitute for it.

## 0. How to read this

§4 holds the six calls that needed a developer decision; all are now answered, each with the
reasoning that produced it. §1 is method, §2 is the outcome, §3 is four defects found in the
acceptance criteria themselves, §5–§8 are the full per-file tables, §9 is the work this
authorises.

## 1. Method

### 1.1 The test order (locked by SPEC §3.4 → §3.1, plus the north star)

Each file was put through four questions **in this order**:

1. **Which surface does it serve?** — model-facing scaffolding (delete; deleting it is what
   un-inhibits the model) or human-facing handholding (keep; no model capability replaces
   it). SPEC §3.4 / ADR-0031 Decision 5.
2. **Which bucket?** — Scaffolding (tells the model *how to think* → delete) · Governance
   (constrains *what may happen to the human* → keep) · Instruments (tells *us* whether a
   deletion was right → keep). SPEC §3.1.
3. **If Instrument, does it clear R-B1…R-B5?** — traceable to a pre-existing artifact;
   arrives with its test module; independently reviewed; **names a retained reader exercised
   by that test** (R-B4); adds nothing to the always-loaded read surface (R-B5).
4. **The north-star test** — *does this serve a memory a human can rely on across years?*
   From `memory/project_north_star_memory_scaffolding.md`. **Where question 4 and questions
   1–3 disagreed, the file went to §4 instead of being decided quietly** — the instruction
   carried in the P2 handoff, and the reason §4 exists.

### 1.2 Disposition vocabulary

| Verdict | Meaning |
|---|---|
| **RESTORE** | Ported onto the v4 base as part of P3. |
| **STAYS DELETED** | Not carried forward. **Every row names its replacement or records the retirement explicitly** — SPEC C7's rule that *silence is not a disposition*. |

### 1.3 Provenance of every number, and two corrections

All counts were produced by command against `main` and
`claude/framework-modernization-opus-tr3ce9`, not transcribed from prior documents.

```powershell
$v4='claude/framework-modernization-opus-tr3ce9'
$mo = Compare-Object (git ls-tree -r --name-only main) (git ls-tree -r --name-only $v4) `
        -PassThru | Where-Object { $_.SideIndicator -eq '<=' }
# per-file: @(git show "main:$f").Count
```

**Correction 1 — a wrong line-count method, caught by reconciliation.** The first pass used
`git show <f> | Measure-Object -Line`, which silently **drops blank lines**; it reported
`goal_loop.py` at 1,428 against the spec's 1,704. Every per-file number here comes from the
re-run, and the totals (25 files / **10,297** lines under `scripts/`; 66 `.claude/`; 21
`docs/`) now match SPEC §6.6 and AC7 exactly.

**Correction 2 — the generator asserted a disposition from a document instead of measuring it,
and the developer caught it.** The first draft of C6 recommended deleting `/plan` and
`/build_module`, reasoning from v4's *"match ceremony to stakes, there is no fixed ladder."*
No measurement was taken. The developer's challenge — *"I think my projects use build_module
all the time"* — prompted one, and it reversed the recommendation outright (§4, C6: 212 SPEC
artifacts across four derived projects, 64 in the last 60 days).

**This is the third instance of the same failure class inside this reconciliation** — after
rev 1's wrong merge-base and Correction 1 above — and the second time the catch came from an
independent reader rather than the generator. It is direct evidence for merged Principle #3
and for the plurality disposition in ADR-0031 Decision 6, and it should be cited in the
ADR's Consequences alongside the other two.

It also demonstrates the hub standard (`memory/feedback_template_is_the_hub.md`) doing real
work: `/build_module` is used lightly in this template and heavily in the projects the
template exists to serve. Judging it by template-local activity would have deleted it.

## 2. Outcome

**AC7 scope as written: 112 files, 20,502 lines.**

| Surface | Files | Lines | RESTORE | STAYS DELETED |
|---|---:|---:|---:|---:|
| `scripts/` | 25 | 10,297 | 18 files / 8,099 | 7 files / 2,198 |
| `.claude/` | 66 | 7,231 | 36 files / 4,037 | 30 files / 3,194 |
| `docs/` | 21 | 2,974 | 21 files / 2,974 | — |
| **Total** | **112** | **20,502** | **75 / 15,110** | **37 / 5,392** |

Plus 22 files outside AC7's stated scope (D2), all RESTORE: `src/telemetry/` (17),
`src/context_sensor.py` (1), `loops/` (4).

### 2.1 The re-inflation reckoning (R3), stated plainly

**The merged tree carries back 74% of the main-only surface by line count.** This is not a
small add-back, and the spec should stop implying otherwise. Recorded here rather than
softened, because R3 named re-inflation as a live risk and the honest answer is that the
reconciliation is large.

What makes it defensible is **where** the lines land, not the total:

| Category | Lines | Why it is not re-inflation |
|---|---:|---|
| Immutable records (`docs/`) | 2,974 | Never loaded into context (R-B5); Principle #4 protects them |
| Instrumented code with tests + named readers | 4,819 | Each clears R-B1…R-B5; each arrives with its test module |
| Capabilities restored on measured usage | 3,318 | `/plan`+`/build_module` (212 specs), `ux-evaluator` (4th-most-used in Insight Journal), `/analyze-project` loop |
| Telemetry render layer (C1) | 2,824 | Restored on a recorded developer goal that R-B4 did not anticipate |
| `/goal-loop` (C3) | 1,704+ | Restored on the bucket test, against the spec's own pre-declaration |
| Governance, hooks, reference playbooks | ~1,700 | Cherny's explicit keep-list + the "plain specs → rich references" shift |

**And the instruction surface — the thing ADR-0030's thesis is actually about — still shrinks.**
Of `.claude/`'s 7,231 lines, **3,194 stay deleted**. The deletions concentrate exactly where
the thesis aims: dispatch protocols, orchestration ladders, prior-art procedures, ADR-writing
craft, micro-fix sizing. What survives is reference material, governance, and human-facing
gates.

**Falsifier F-A now has real stakes.** If subagent-call share does not fall materially after a
merge that restores this much, v4's core productivity claim is in trouble — and the sensor
restored in §5.3 is what will say so.

## 3. Four defects found in the acceptance criteria themselves

**D1 — AC7's `docs/` scope contradicts its own count.** AC7 says *"`docs/` (21 files,
excluding adr/ and reviews/)"*. The main-only `docs/` set **is** 21 files, but that includes
1 `adr/` file and 10 `reviews/` files; excluding them leaves **10**.
**Fix (approved): drop the exclusion, keep the count.** Excluding them would discard the
record of ten independent reviews, in a reconciliation whose central argument is that
independent review is what caught its own errors. §7 dispositions all 21.

**D2 — AC7's scope misses 22 live main-only files.** `src/telemetry/` (17), `src/context_sensor.py`
(the file **F1 was found in**), `loops/` (4). **Fix: extend AC7's scope sentence to `src/` and
`loops/`.** All 22 are dispositioned in §5.4 / §5.8.

**D3 — v4's retained code carries stale references to what v4 deleted.** Checked carefully
because it initially looked like breakage; **it is not.** A scan of every `.py` file on the v4
base found **zero real import statements** referencing main-only modules. What exists:

- Comments/docstrings in v4's `quality_gate.py`, `notify.py`, `close_discussion.py`,
  `init_db.py`, `pipeline_utils.py` and four test modules cite `src/context_sensor.py`,
  `ingest_token_usage.py`, `unify_sightings.py` as regression precedents.
- `pyproject.toml` keeps two `per-file-ignores` entries for test files v4 deleted.
- `scripts/extract_findings.py` has a live branch keyed to `agent == "facilitator"`.

Most self-resolve now that the referenced files are restored. **Fix: AC9 gains a check that
the merged tree contains no config entry or code branch naming a file it does not contain.**

**D4 — v4's `/review` advertises a `--deep` flag with nothing behind it.** `argument-hint:
"[file/dir] [--deep]"`, but `--deep` is what dispatched `history-analyst`, which v4 deleted.
A prose guarantee with no mechanism — the `--rebaseline` defect class, inside the review
command. **Fix (approved, per C5): remove `--deep` from the argument-hint** rather than
restore 109 lines to justify a flag. Least-complex intervention — retired main Principle #8's
brake doing work from its new home in `PHILOSOPHY.md`.

## 4. The six contested calls — DECIDED

### C1 — Telemetry dashboards → **RESTORE all 19** (2,824 lines)

`scripts/telemetry/dashboard.py` (419) · `dashboard_server.py` (993) · `src/telemetry/` (17
files, 1,412)

**The tension.** R-B4 — added after the Steward gate as the discriminating bound — says
*"Pure measurement with no retained reader is a dashboard, and the ~13,000 lines of dashboards
correctly stayed deleted."* Against it, `memory/project_telemetry_dashboard_northstar.md`:
*"The whole point of the Telemetry & Oversight component is a powerful Layer B DASHBOARD for
understanding AI use; A1/A2/A3 are the data foundation."*

**Decision: the north star governs.** Under R-B4 alone, deleting the dashboard deletes the
point of the component and keeps only its foundation.

**⚠ Required in the same change — R-B4 gains an explicit carve-out naming ADR-0020.** As
written, R-B4 silently overrides a recorded developer goal, which is the same shape as the
constitution being amended as a side effect of base selection — the thing the Steward gate
caught. The carve-out must state that a render layer whose *stated purpose* is the read-out of
a recorded telemetry goal is not what R-B4's "dashboard" clause excludes, and that the clause
still governs unnamed dashboards. Without this, ADR-0031 ships a bound that contradicts an
approved disposition.

### C2 — Knowledge-pipeline read-outs → **split** (481 restore / 588 delete)

**RESTORE:** `check_stale_adoptions.py` (164) — guards the Rule-of-Three adoption ledger;
`/meta-review` (317) — the only quarterly framework-evaluation artifact class, and the
`memory/project_karpathy_wiki_central_brain.md` hub loop runs through it.

**STAYS DELETED:** `knowledge_dashboard.py` (253), `efficiency_report.py` (176),
`/knowledge-health` (66). **Replacement: v4's `/retro`**, which already reads `mine_patterns`,
`compute_agent_effectiveness`, `audit_calibration` and the briefing ledger.

**The line drawn:** files that *maintain* the memory are kept; files that merely *display* it
are replaced by `/retro`. This was the weakest call in the set (confidence 0.72) and is the
first candidate for revisiting if F-C surfaces something at P6.

### C3 — `/goal-loop` → **RESTORE** (3,645 lines incl. the 1,704-line driver)

`scripts/goal_loop.py` · `/goal-loop` · `orchestrating-goal-loops` ·
`authoring-goal-contracts` · `loops/` (4 files) · `tests/test_goal_loop.py`

**Decision: the bucket test wins over SPEC §6.6's pre-declaration.** §6.6 declared it
"stays deleted" on a size-and-usage argument. But by the classifier the same spec makes
authoritative, `goal_loop.py` is **governance, not scaffolding**: a deterministic driver owns
control flow and **the builder is never the judge** (ADR-0026) — both constraints on what the
model may do, and §3.2 gives enforcement the benefit of the doubt. Supporting:
`memory/project_goal_loop_goal_generation_vision.md` records a live Phase-2 plan;
`memory/reference_gulli_agentic_design_patterns.md` records independent external validation of
the builder≠judge design (Gulli Ch. 11).

**Recorded for the ADR:** SPEC §6.6 must be amended, not quietly overridden. It is a case of
the spec pre-deciding something its own classifier disagreed with — worth keeping visible,
because it is the second such case in this document (C6 is the other).

### C4 — `git_visualize.py` → **STAYS DELETED** (931 lines)

**Verified:** v4 has `/status`, and it does **not** use this script — it runs `git status`,
`assess_risk.py`, and the briefing ledger. The script is orphaned on the base.
**Replacement: v4's `/status`.** The north-star test does not rescue it: an interactive
browser view of branch state *now* is not a memory relied on across years. Cheapest reversal
in the set.

### C5 — Framework-evolution read-out → **RESTORE `steward` + `/lineage`** (245 lines)

**This resolves SPEC C7.** The lineage engine survives on v4 (`scripts/lineage/`, live caller
in `scripts/distribute/change_package.py`, `tests/test_lineage.py`); what had no home was the
**read-out** — nothing reported drift, and no artifact class recorded a framework-evolution
decision, right as P6 pushes a re-constituted framework into three derived projects.

**The decisive argument is inside ADR-0031 itself:** the Steward gate is what caught the
constitution being silently rewritten — nine principles cut to six as a side effect of base
selection — which four panel reviewers and the generator all missed.

`history-analyst.md` (109) **stays deleted**; instead **`--deep` is removed from v4's
`/review` argument-hint** (D4).

### C6 — `/plan` + `/build_module` → **RESTORE both; drop only the rigid ladder**

**RESTORE:** `/plan` (257), `/build_module` (268), `running-build-checkpoints` skill (89).
**STAYS DELETED:** `.claude/rules/autonomous_workflow.md` (75) — its fixed "3+ files ⇒ `/plan`"
file-count triggers are replaced by v4's *"match ceremony to stakes."* The commands become
**available rather than mandatory.**

**The measurement that reversed the first recommendation:**

| Derived project | SPEC artifacts | Last 60 days | `build_module.md` installed |
|---|---:|---:|---|
| agentic_journal | 157 | 22 | yes |
| VerificationPortal | 47 | 42 | yes |
| howie_family_wiki | 6 | 0 | yes |
| dan_research_karpathy_wiki | 2 | 0 | yes |
| **Total** | **212** | **64** | **4 / 4** |

Newest spec: 2026-08-05. Also 206 discussion files in agentic_journal and 74 in
VerificationPortal reference `build_module`.

**Why the first recommendation was wrong.** `/plan` and `/build_module` are two things under
one name, and they fall on opposite sides of this reconciliation:

- **The ladder — model-facing.** "First `/plan`, then `/build_module`, then the gate, then
  `/review`." Instruction telling the model what order to work in. This is what v4's evidence
  actually targets, and it is what is being dropped.
- **The artifact and the gates — human-facing.** The `SPEC-*` file is a written contract of
  what is being built and what "done" means, **approved by the developer before code exists**.
  The mid-build checkpoints put two specialists in front of the work while it can still cheaply
  change — they caught 6 findings in the Wave 2 build alone. Neither is the model being told
  how to think.

The first draft collapsed both into one verdict, weighting the ladder and never measuring the
artifact. Deleting them would have meant no command produces a `SPEC-*`, so scope approval
moves to review time — after the code exists — and `docs/sprints/` stops growing, taking with
it the answer to *"why was this built this way, and what did we agree done meant?"* That is a
direct hit on the north star.

### C7 (not contested, recorded for completeness) — `/onboard` → **STAYS DELETED** (95 lines)

ADR-0021 marks it *superseded-but-retained*. **Verified:** v4's `/apply-framework` does not
reference it, so no dangling reference is created. Retirement recorded explicitly; ADR-0021
survives as the record. Low-stakes and trivially reversible if the deep-takeover path is
wanted later.

## 5. `scripts/` — 25 files, 10,297 lines

### 5.1 RESTORE — mandated by an existing acceptance criterion (5 files, 1,816)

| File | Lines | AC | Bucket |
|---|---:|---|---|
| `education/__init__.py` | 5 | AC5a | Governance |
| `education/gate_registry.py` | 526 | AC5a, AC13e | Governance |
| `education/ingest_walkthrough_session.py` | 857 | AC5a, AC5b | Governance — deterministic sole writer across the phone trust boundary |
| `stop_hook.py` | 317 | AC3 | Governance + Instrument |
| `queue_stop_notify.py` | 111 | AC3 | Governance — ntfy driver |

### 5.2 RESTORE — education recording (1 file, 94)

`record_education.py` (94) — writes education-gate results to Layer 2. Without it AC13's
explain-back has nowhere to land.

### 5.3 RESTORE — instruments clearing R-B1…R-B5 (6 files, 2,498)

| File | Lines | R-B1 traceability | R-B4 retained reader | Test module |
|---|---:|---|---|---|
| `telemetry/__init__.py` | 6 | ADR-0020 | package | — |
| `telemetry/call_log.py` | 329 | ADR-0020, ADR-0013 | `analyze_cost.py`; F-A/F-D | `test_call_log.py` |
| `telemetry/analyze_cost.py` | 368 | ADR-0020 A1 | `/retro`; F-D | `test_telemetry.py` |
| `telemetry/analyze_failures.py` | 594 | ADR-0020 A2 | `/retro`; F-B | `test_telemetry_hooks_health.py` |
| `telemetry/analyze_value.py` | 499 | ADR-0020 A3 | `/retro`; F-A | `test_telemetry_weekly.py` |
| `ingest_token_usage.py` | 702 | ADR-0031 §2 names it | `v_token_efficiency` view | `test_ingest_token_usage.py` |

ADR-0031 §4.1 already commits to re-establishing the sensor. The three analyzers are here
because **without a retained reader the sensor fails its own R-B4 bound** — restoring a sensor
and deleting every reader would reproduce the exact defect ADR-0030 is criticised for.

### 5.4 RESTORE — memory-substrate maintenance (2 files, 411) *(north-star driven)*

| File | Lines | Why |
|---|---:|---|
| `unify_sightings.py` | 266 | Deduplicates Layer-2 sightings; v4's own `pipeline_utils.py` still documents a shared-normalisation contract with it |
| `enforce_forgetting_curve.py` | 145 | Ages curated memory so Layer 3 stays trustworthy rather than merely large |

**The clearest case where the north-star test and the model-need test agree against ADR-0030's
instinct:** the model needs neither, but a memory prosthesis that never dedupes and never
forgets degrades into an unsearchable pile. Both are cheap, tested, and add nothing to the
always-loaded surface.

### 5.5 RESTORE — approved contested calls (4 files, 3,280)

| File | Lines | Call |
|---|---:|---|
| `telemetry/dashboard.py` | 419 | C1 |
| `telemetry/dashboard_server.py` | 993 | C1 |
| `check_stale_adoptions.py` | 164 | C2 |
| `goal_loop.py` | 1,704 | C3 |

### 5.6 STAYS DELETED (7 files, 2,198)

| File | Lines | Replacement / recorded retirement |
|---|---:|---|
| `backfill_findings.py` | 93 | One-time migration, already applied. R-B1 fails — answers no forward question. |
| `backfill_finding_noise.py` | 123 | as above |
| `backfill_turn_content.py` | 123 | as above |
| `session_supervisor.py` | 499 | SPEC §10 declines to re-arm its `bypassPermissions` auto-launch, leaving no live caller. **Retirement recorded:** autonomous cross-session continuation is not a capability of the merged tree. Annotate `memory/project_autonomous_continuation_supervisor.md` as describing a retired capability. |
| `git_visualize.py` | 931 | C4 — v4's `/status` |
| `knowledge_dashboard.py` | 253 | C2 — v4's `/retro` |
| `efficiency_report.py` | 176 | C2 — v4's `/retro` |

⚠ **Carried risk for P6, not P3:** a derived project whose `evaluation.db` predates the three
backfill migrations has no path to the current schema once they are gone. Flagged for the
`/apply-framework` run — either re-generate a migration then, or accept that derived DBs
re-baseline. Recorded so it is not discovered at distribution time.

### 5.7 Outside AC7's stated scope (D2) — all RESTORE

| Path | Files | Lines | Why |
|---|---:|---:|---|
| `src/context_sensor.py` | 1 | — | ADR-0031's Alternatives already rejects *"delete the wrap-up/context-sensor machinery entirely, as v4 did"* — *"the remedy for a miscalibrated instrument is calibration."* **F1 was found here.** |
| `src/telemetry/` | 17 | 1,412 | C1 |
| `loops/` | 4 | — | C3 |

## 6. `.claude/` — 66 files, 7,231 lines

### 6.1 Agents (11 files, 1,705) — 3 restore / 8 delete

| File | Lines | Disposition | Replacement / reason |
|---|---:|---|---|
| `ux-evaluator.md` | 139 | **RESTORE** | Hub standard: **4th-most-used agent in Insight Journal** (`memory/project_verification_portal.md`). Template-local disuse is the wrong denominator. |
| `project-analyst.md` | 277 | **RESTORE** | Powers `/analyze-project`; the hub-pulls topology in `memory/project_karpathy_wiki_central_brain.md` is live |
| `steward.md` | 152 | **RESTORE** | C5 |
| `architecture-consultant.md` | 94 | STAYS DELETED | Renamed, not lost → v4 `architecture-reviewer` |
| `qa-specialist.md` | 103 | STAYS DELETED | → v4 `code-reviewer` |
| `security-specialist.md` | 100 | STAYS DELETED | → v4 `security-reviewer` |
| `independent-perspective.md` | 230 | STAYS DELETED ⚠ | → v4 `contrarian`. **Conditional — see §6.6(a),(b)** |
| `facilitator.md` | 276 | STAYS DELETED | Already decided: `memory/project_model_tiering_dispatch_policy.md` — *"orchestrates in main loop (never dispatch facilitator as subagent)."* Replacement: the main loop. |
| `docs-knowledge.md` | 133 | STAYS DELETED | → `/decide` + `/remember` carry the documentation duty inline |
| `performance-analyst.md` | 92 | STAYS DELETED | → v4's `code-reviewer` charter explicitly lists *"performance"* |
| `history-analyst.md` | 109 | STAYS DELETED | C5 / D4 — `--deep` removed from `/review` instead |

### 6.2 Commands (20 files, 2,981) — 10 restore / 10 delete

**RESTORE (1,794)**

| File | Lines | Why |
|---|---:|---|
| `plan.md` | 257 | C6 — 212 SPEC artifacts across derived projects |
| `build_module.md` | 268 | C6 |
| `meta-review.md` | 317 | C2 |
| `analyze-project.md` | 326 | Live adoption loop (`project_karpathy_wiki_central_brain`) |
| `evaluate-repo-security.md` | 162 | §3.2 + Cherny's keep-list: *"safety and permissions and static analysis"* |
| `batch-evaluate.md` | 122 | Closes the Rule-of-Three adoption ledger |
| `goal-loop.md` | 112 | C3 |
| `discover-projects.md` | 97 | Feeds the adoption loop |
| `lineage.md` | 93 | C5 |
| `handoff.md` | 40 | ADR-0031 Alternatives already rejects deleting the wrap-up machinery |

**STAYS DELETED (1,187)** — every row names its replacement

| File | Lines | Replacement / recorded retirement |
|---|---:|---|
| `conversation.md` | 249 | Cross-project messaging; **retirement recorded** — no live use since 2026-06 |
| `deliberate.md` | 216 | Model-facing orchestration scaffolding; `/decide` captures the reasoning |
| `seed.md` | 179 | `/apply-framework` greenfield path (ADR-0021) |
| `promote.md` | 144 | v4 `/remember` — verified equivalent (same human gate, same provenance frontmatter) |
| `quiz.md` | 100 | v4 `/teach` |
| `onboard.md` | 95 | C7 — retirement recorded; no dangling reference from `/apply-framework` |
| `walkthrough.md` | 75 | v4 `/teach` (`deep` depth *is* the walkthrough) |
| `knowledge-health.md` | 66 | C2 — v4's `/retro` |
| `spawn-project.md` | 42 | ⚠ `scripts/spawn_project.py` survives — see §6.6(c) |
| `distribute.md` | 21 | Deprecated alias; v4 ships `/apply-framework` directly |

### 6.3 Skills (23 files, 1,994) — 14 restore / 9 delete

**RESTORE (1,294)**

| File | Lines | Bucket / why |
|---|---:|---|
| `selecting-review-gates/` | 88 | **AC7 names this individually.** Governance — the home of review plurality, §6.6(a) |
| `recovering-from-failures/` | 128 | The 8 named failure classes; human-facing + governance |
| `testing-playbook/` | 128 | *Reference* — the "plain specs → rich references" shift argues **for** these |
| `authoring-goal-contracts/` | 120 | C3 |
| `orchestrating-goal-loops/` | 105 | C3 |
| `grill-yourself/` | 99 | Human-facing; pairs with `grill-me`, which v4 keeps |
| `collaborating-async/` | 96 | Governance — untrusted-reply allow-list; `TestSinglePollerDiscipline` (AC3) guards a real bug (`memory/feedback_ntfy_one_monitor_at_a_time.md`) |
| `python-project-patterns/` | 94 | Reference |
| `performance-playbook/` | 92 | Reference |
| `running-build-checkpoints/` | 89 | C6 — the mid-build specialist gate |
| `committing-changes/` | 85 | Governance — regression-ledger + review sequence |
| `security-checklist/` | 60 | Cherny keep-list |
| `syncing-framework-docs/` | 57 | Cheap guard against exactly the count-string rot AC14 is repairing |
| `wrapping-up-sessions/` | 53 | Rides with `/handoff` |

**STAYS DELETED (700)**

| File | Lines | Replacement / reason |
|---|---:|---|
| `adr-writing/SKILL.md` + `template.md` | 169 | v4's `/decide` carries the template inline |
| `orchestrating-lean-dispatch/` | 103 | Model-facing token-routing scaffolding |
| `searching-prior-art/` | 98 | v4's `/decide` embeds the prior-art grep inline |
| `cross-agent-dispatch/` | 96 | Model-facing dispatch protocol; v4's `/review` dispatches directly |
| `multi-instance-dispatch/` | 69 | ⚠ **Conditional** — plurality-bearing, §6.6(a) |
| `feature-status-registry/` | 67 | Derived-project pattern; **retirement recorded** |
| `handling-micro-fixes/` | 53 | Merged Principle #7 already exempts micro-fixes |
| `documenting-decisions/` | 45 | → `/decide` + `/remember` |

### 6.4 Rules (4 files, 205) — 1 restore / 3 delete

| File | Lines | Disposition |
|---|---:|---|
| `security_baseline.md` | 35 | **RESTORE — AC7 names this individually.** The strongest keep-case in the external evidence: Cherny's ablation explicitly preserves *"safety and permissions and static analysis."* Deleting it deletes the one category the source says to keep. |
| `autonomous_workflow.md` | 75 | STAYS DELETED (C6). Its file-count ladder → v4's *"match ceremony to stakes."* **Its one governance paragraph already has a home:** v4's `/retro` states *"Proposals are communication, not instructions… Making those edits off your own proposal would be self-modification"* — the ADR-0024 calibration-loop human gate, preserved. |
| `testing_requirements.md` | 64 | STAYS DELETED → `testing-playbook` (restored) + the gate's coverage floor |
| `coding_standards.md` | 31 | STAYS DELETED → `ruff` (deterministic) + `python-project-patterns` (reference) |

### 6.5 Hooks (8 files, 346) — **RESTORE all 8**

`session-start.ps1` (161) · `release_lock.py` (53) · `context_guard.py` (46) ·
`pre-compact.ps1` (35) · `context_statusline.py` (34) · `context-guard.sh` (6) ·
`context-statusline.sh` (6) · `post-tool-use-unlock.sh` (5)

The first six are the context-sensor / wrap-up machinery whose deletion ADR-0031 already
rejects in Alternatives Considered. **F1 — the ~5× premature wrap-up firing on every session,
every frontier model, in this repo and all three derived projects — was found in this code and
would have been undetectable without it.** The last two are the ntfy single-poller lock.

⚠ **AC11 applies:** `.claude/hooks/` is in `PROTECTED_PATTERNS` on the v4 base, and **the
pattern must not be removed to unblock this** (§3.2). The developer hand-applies these eight
files alongside `settings.json` (AC6).

### 6.6 Three conditions attached to the "stays deleted" rows

**(a) Plurality must land before `independent-perspective` and `multi-instance-dispatch` are
deleted.** AC7: *"Plurality is explicitly in scope and may not be dissolved into a group
disposition."* v4's `/review` says *"Most changes need one or two"* and its `CLAUDE.md` says
*"Prefer one agent over several."* **Required in the same change:** `selecting-review-gates`
(restored) states the panel size for critical-risk changes; v4's `/review` cross-references
it; the "prefer one agent" line is scoped to ordinary delegation. Without this, deleting these
two files silently makes the merged tree single-reviewer — on the one mechanism ADR-0031
credits with catching this reconciliation's critical findings.

**(b) `contrarian` must absorb what `independent-perspective` carried.** Verify before
deleting, not after.

**(c) `scripts/spawn_project.py` survives with no command in front of it.** Same shape as C7:
engine kept, read-out deleted. **Fix: document the greenfield path in `/apply-framework`** —
3 lines, no new capability.

## 7. `docs/` — 21 files, 2,974 lines — **RESTORE all 21**

Uncontested. Every file is a **record** — what both the north-star test and Principle #4
protect most directly — and none of it is loaded into context (R-B5), so restoring costs
nothing at runtime.

| Group | Files | Lines | Note |
|---|---:|---:|---|
| `adr/ADR-0029-repocademy-education-gates.md` | 1 | 227 | AC4: keeps its number; referenced by `CONTRACTS.md`, the cross-repo contract `insight_journal` builds against |
| `reviews/REV-*` | 10 | 1,105 | The independent-review record, 2026-06-12 → 2026-07-17 |
| `education/` (`CONTRACTS.md`, `gates.yaml`, fixture) | 3 | 583 | AC5a mandates |
| `sprints/` (3 SPEC, 2 PROMPT, 1 PROPOSAL, 1 WORKITEMS) | 7 | 1,059 | Includes the specs for the two waves AC2/AC3 are porting |

Per D1 this includes the `adr/` and `reviews/` files AC7's parenthetical said to exclude.

## 8. Test modules — AC9 (18 modules + 1 fixture)

Every test follows its subject. **R-B2 holds throughout: no file in §5 is restored without its
test module.**

| Test module | Follows | Verdict |
|---|---|---|
| `test_stop_hook.py` | AC3 | RESTORE — **unmodified**; AC3 makes it the specification |
| `test_gate_registry.py`, `test_ingest_walkthrough_session.py`, `test_record_education.py` | §5.1/§5.2 | RESTORE |
| `test_call_log.py`, `test_ingest_token_usage.py`, `test_telemetry.py`, `test_telemetry_hooks_health.py`, `test_telemetry_weekly.py` | §5.3 | RESTORE |
| `test_unify_sightings.py`, `test_enforce_forgetting_curve.py` | §5.4 | RESTORE |
| `test_dashboard_server.py`, `test_telemetry_donut.py` | C1 | RESTORE |
| `test_goal_loop.py` | C3 | RESTORE |
| `test_context_sensor.py` | §5.7 | RESTORE |
| `test_agent_frontmatter.py` | §6.1 | RESTORE — retarget to the merged agent roster |
| `test_backfill_finding_noise.py` | §5.6 | DROP with its subject |
| `test_session_supervisor.py` | §5.6 | DROP with its subject |
| `tests/fixtures/gate_summary_golden.txt` | AC2 | RESTORE — the AC2 golden fixture |

**16 of 18 modules restored; 2 dropped with their subjects.** AC9's requirement is satisfied
by enumeration.

## 9. What this authorises, and what it does not

**Authorised (P3):**

1. Branch off the v4 base; execute the dispositions above in small reviewed commits.
2. Amend the artifacts to match: **SPEC §6.6** (the `/goal-loop` pre-declaration is reversed),
   **AC7** (D1 count, D2 scope), **AC9** (D3 dangling-reference check), **R-B4** (C1's ADR-0020
   carve-out), **AC14** (seven principles ratified as written — no further change).
3. Record C1–C6 with their reasoning into `DISC-20260806-055721-v4-reconciliation` (left open
   deliberately for exactly this).
4. Apply the §6.6 conditions (a)–(c) and the D4 `--deep` removal **in the same change** as the
   deletions they condition.

**Not authorised — still required:**

- **R-B3 independent-context review of this classification, before AC9.** Developer approval
  of the dispositions is not a substitute; the two answer different questions.
- Any push, merge, or propagation (AC10). **P5 public promotion and P6 distribution remain
  separately gated**, and AC13c blocks both on unresolved explain-back items.

**Two items deferred to P6 rather than silently dropped:** the backfill-migration path for
derived projects with older `evaluation.db` schemas (§5.6), and C2's read-out split, which is
the first thing to revisit if F-C surfaces a regression at the correct measurement site.
