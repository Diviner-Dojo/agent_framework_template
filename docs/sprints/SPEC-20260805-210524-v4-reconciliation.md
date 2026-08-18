---
spec_id: SPEC-20260805-210524
title: "v4 reconciliation — judgment-gated add-back of waves 1-2 + RepoCademy onto the v4 base"
type: spec
status: draft
risk_level: critical
reviewed_by: [architecture-consultant, security-specialist, qa-specialist, independent-perspective]
discussion_id: DISC-20260806-055721-v4-reconciliation
intake_ids: ["docs/handoff/HANDOFF-20260805-v4-reconciliation.md", "ADR-0029-framework-v4-scaffolding-removal (v4 branch, renumbered ADR-0030 here)", "REV-20260728-140000 (v4 branch)", "Boris Cherny / YC Startup School 2026 (https://youtu.be/qyPCVqFUyDo)", "Anthropic context-engineering post 2026-07-24 (six shifts)"]
completed_at:
completed_commit:
---

> **rev 4 — folds Steward gates 2 and 3.** Gate 2 (REVISE, 0.85) found that rev 3 had
> populated `discussion_id` while both referenced discussions were **zero bytes** — the F2
> defect one level up — that the seven principles existed only as a construction rule so AC14
> had no referent, that ADR-0031 retired main Principle #3 and then cited "Principle #3" as its
> own strongest evidence, and that F2's fix and R7's interim default were **prose with no
> acceptance criterion**. All cleared: discussions populated (10 + 6 events, one sealed, one
> deliberately left open); authoritative seven-row principle table; the #3 retirement split into
> *posture* (retired) and **plurality** (kept, now AC7-scoped and in Appendix A); AC2 tightened
> to a **tethering** check; AC14 unconditional; new AC15. Gate 3 (REVISE, 0.86) closed the loop
> — all four blockers verified cleared, remaining items mechanical, **no further Steward cycle
> required**: the decision table had been structurally broken by an inserted prose block
> (the #8 row orphaned), principle citations were half-re-pointed and ambiguous, plurality was
> asserted into AC7 without being in it, and §5's F2 prose contradicted AC2/AC14. All fixed here.
>
> **rev 3 — folds the Steward gate (REVISE, 3 blocking + 6 required).** The gate's first
> blocking finding is the one that matters: **the constitution was an undispositioned collision
> surface.** Both trees edited `CLAUDE.md`/`PHILOSOPHY.md` and rev 2 named neither file
> anywhere, so taking v4 as the base would have cut nine Non-Negotiable Principles to six with
> nobody deciding it — including #9 (clarify before acting), which is also the developer's
> standing mandatory instruction. Resolved per-principle by the developer → **seven principles**
> (ADR-0031 Decision 6, AC14). Also folded: AC13 made capable of failing (AC13a-c), the
> instrument bound given a discriminating test (R-B4/R-B5), the base-selection claim narrowed to
> what was measured (§3.3 whole-tree table), disposition extended to the 87 prose files (AC7),
> the interim briefing safeguard converted from a request to a default (R7), F2 recorded, and
> C7/C8 added.
>
> **rev 2 — folds the spec-review panel (4/4 REVISE on rev 1).** Rev 1 claimed to be
> *evidence-gated*. The panel established that it was not: no acceptance criterion was
> contingent on the proposed measurement, the measurement site was the wrong one, the
> chosen A/B task was not equivalent across trees, and the v4 arm had no instrument to
> measure with. Two load-bearing numbers in rev 1 were also wrong. **Developer decision
> (2026-08-05): proceed judgment-gated and label it honestly** — §4 is rewritten from a
> gate into continuous instrumentation plus named falsifiers.
>
> **Corrections carried from rev 1, recorded because the error is instructive:**
> rev 1's §3.3 measured v4's gate delta against `e4c8d73` (public upstream) while stating
> it was against the common ancestor. `e4c8d73` is not an ancestor of `main`. Corrected
> figures are in §3.3. Rev 1 also asserted the A/B task's files were byte-identical across
> trees; three of four differ (§4.3). Both claims were asserted from documents rather than
> checked with a command — in a spec whose argument is that claims should be measured.

## 1. Goal

Reconcile the offline v4 rebuild (`claude/framework-modernization-opus-tr3ce9`, HEAD
`50e9d32`) with private `main` (`c7bcc86`, v3.5), producing a single framework that works
well with Opus 5 / Fable 5 without imposing scaffolding costs on them.

The result is then promoted to the public upstream and distributed to the derived projects,
deliberately exercising `/apply-framework` as a test of the distribution mechanism.

## 2. Evidence base

The v4 thesis is externally corroborated, and the corroboration is specific.

**Supporting.** Anthropic deleted >80% of Claude Code's system prompt for Opus 5 / Fable 5
with no measurable loss on coding evals, and published six shifts: rules→judgment,
examples→interface design, upfront instructions→progressive disclosure, repetition→tool
descriptions, manual memory→auto-memory, plain specs→rich references. Boris Cherny's method
is an **ablation** — "delete the entire system prompt and then bring it back line by line to
figure out the impact of each individual line" — on a recurring cadence ("every 6 months
delete your CLAUDE.md"). `CLAUDE_CODE_SIMPLE=1` strips all system prompts as an ablation
instrument.

**What that guidance explicitly keeps:** "safety and permissions and static analysis", and
"give the model a way to verify the output of its work so it doesn't get stuck" — *external
deterministic* verification. What it deletes is instruction telling the model to
*self*-verify.

**Counter-evidence.** Community reports following the Claude 5 releases include agents
working around deliberate hook controls, a model circumventing a regex-based git-checkout
ban by changing directory, and 30-40% output-length inflation at equal prompts. **These are
uncited community reports, not measured findings, and are weighted accordingly** — they
motivate a retention presumption (§3.2), not a conclusion. The on-repo instance is stronger
and is what the presumption actually rests on: REV-20260728-140000 B6 found four fail-closed
guards moved from code into prose (since remediated on the v4 HEAD in `0906c41`; cited as
precedent, not as an open defect).

**Transferability limit (panel finding, accepted).** Anthropic's ablation was run by a
product team against internal eval suites at scale, on *their own* system prompt. What is
being deleted here is a third-party layer stacked on an already-ablated prompt, and this
repo cannot reproduce that method at any phase of this plan. The external evidence is
therefore treated as **directional and unverified-for-this-context**, not as proof. §4 says
what would change our mind instead of pretending to have measured.

## 3. Decision framework

### 3.1 The classifier gains a third bucket

v4 sorts every file by "does this exist because the model was weak?" into **scaffolding**
(delete) and **governance** (keep). That binary is what allowed the rebuild to sever
`record_yield.py`, `ingest_token_usage.py`, and the `briefings` outcome column — all caught
only at review. This spec adds a third:

| Bucket | Test | Disposition |
|---|---|---|
| **Scaffolding** | Tells the model *how to think* | Delete |
| **Governance** | Constrains *what may happen to the human* | Keep; prefer deterministic code over prose |
| **Instruments** | Tells *us* whether a deletion was right | Keep |

**Bounds on the third bucket** (tightened after review, because "an instrument must name its
question" is a documentation requirement, not a test):

- **R-B1** The question an instrument answers must be **traceable to a pre-existing
  artifact** — an ADR, a CLAUDE.md pointer, or a REV finding — not authored during the
  restoration to justify it.
- **R-B2** An instrument must arrive **with its test module**. Code without its safety tests
  is not an instrument; it is an unverified restoration.
- **R-B3** The classification is **reviewed by an independent context** before AC9, the same
  way code changes are.
- **R-B4** *(added after the Steward gate — the discriminating bound.)* An instrument must name
  a **retained reader** of its output, and that read must be exercised by the R-B2 test module.
  Pure measurement with no retained reader is a dashboard, and the ~13,000 lines of dashboards
  correctly stayed deleted. This is what separates the genuine cases —`record_yield.py` (read
  by `compute_agent_effectiveness.py`), `briefings.outcome` (joined by `/retro`),
  `ingest_token_usage.py` (read by the `v_token_efficiency` view) — from everything else.
- **R-B5** An instrument **adds nothing to the model's always-loaded read surface.** If keeping
  it costs context every session, it is not free and must be justified as governance instead.
- **Amendment to R-B1:** an ADR superseded by ADR-0030 is **not by itself** sufficient
  traceability. ADR-0030 supersedes seven ADRs, so "has a pre-existing ADR" would admit
  essentially the entire deleted set — rev 1's bound admitted anything with an authored
  question; rev 2's admitted anything with a superseded ADR. Both failed in the same direction.
  R-B4 is the bound that actually discriminates.

**Note on the motivating examples.** `audit_calibration.py` is cited in ADR-0030's own
amendment as an over-deletion, but the panel is right that it fits the *existing* governance
test — its loss was a per-directory sweep, a process failure, not a taxonomy gap. The genuine
third-bucket cases are `record_yield.py`, `ingest_token_usage.py`, and `briefings.outcome`:
pure measurement that gates nothing and instructs no model reasoning.

### 3.2 Enforcement gets the benefit of the doubt — in both directions

Any candidate whose function is fail-closed enforcement is retained unless positively shown
redundant.

**This applies to v4's enforcement too, not only main's.** v4 is the base and has *stronger*
protection than main in at least one place: `.claude/hooks/` is in `PROTECTED_PATTERNS` (the
B5 remediation). The add-back writes into that directory, so the merge's cheapest unblock is
deleting the pattern — silently reverting B5 at the moment the tree has six named-but-absent
hook paths. See AC11.

### 3.3 Direction: v4 is the base

**Corrected measurement.** Against the true common ancestor `af3fd10`
(`git merge-base main claude/framework-modernization-opus-tr3ce9`):

| Tree | `scripts/quality_gate.py` vs `af3fd10` |
|---|---|
| v4 (`50e9d32`) | **+123 / −5** |
| main (`c7bcc86`, incl. Wave 2) | **+929 / −50** |

Verify: `git diff --numstat af3fd10 50e9d32 -- scripts/quality_gate.py`

**Whole-tree, from the same ancestor** (M6 — the Steward's finding that rev 2 repeated rev 1's
inferential shape, generalising one file to a tree):

| Tree | whole-tree vs `af3fd10` |
|---|---|
| v4 (`50e9d32`) | 194 files, **+6,875 / −37,343** |
| main (`c7bcc86`) | 136 files, **+16,768 / −472** |

**v4 is the larger divergence**, by files and by an order of magnitude in deletions. Those
37,343 deletions are precisely the surface this reconciliation must re-decide (§6.6).

So the claim is narrowed to what was measured: **v4-as-base minimises the port surface on
`scripts/quality_gate.py`, the one file both trees edited heavily.** It does *not* establish
that v4 minimises the merge surface overall — the opposite is true by line count. The base
choice rests on the separate argument that deletions-to-re-decide is a different and more
tractable cost than lines-to-port, and on ADR-0030's reasoning that you cannot discover a
command is unnecessary by editing it. That argument survives; the arithmetic does not support
more than it says.

Rev 1 additionally called the two deltas "orthogonal" and the port "a ~90-line
three-way merge"; both are withdrawn. The deltas overlap, and there is a genuine collision:
**both trees independently added `check_promotion_backlog()`** (main `:1035`, v4 `:504`;
absent from `af3fd10`), main's being a superset that adds `_emit_warn_line` calls. That
requires an explicit which-version-wins decision, not a mechanical merge.

Base selection is a **judgment call informed by merge surface**, not a measured outcome. It
is not treated as settled-by-evidence, because it was not.

### 3.4 Two surfaces: model-facing scaffolding vs human-facing handholding

**Developer requirement, stated 2026-08-05:** *"I need this framework to work well with the
new models, but also maintain my ability to keep it in my head... I oscillate between states
of having a great deal of attention, to be my normal ADHD self, and needing a lot of
hand-holding. I don't want to lose the hand-holding, but I also don't want to inhibit the
creativity of the model."*

These are **two different surfaces**, and rev 1 (following ADR-0030) conflated them:

- **Model-facing scaffolding** — instructions telling the model *how to think*: collaboration
  modes, exploration-intensity dials, Domain Lens reasoning sequences, mandated
  self-verification. This is what §2's evidence says to delete, and deleting it is what
  un-inhibits the model.
- **Human-facing handholding** — the framework explaining things *to the developer*:
  walkthroughs, the education gate, briefings, plain-language summaries, one-step pacing.

They share no code and do not trade off against each other. They only looked like one dial
because ADR-0030 deleted ~90% of everything at once and both categories were inside that 90%.
**Deleting the first does not require thinning the second.**

Therefore, in addition to the §3.1 bucket test, every deletion candidate must first answer:
**which surface does this serve?** A file that explains the system to the human is not
scaffolding at any model capability, by the same argument ADR-0030 uses for code that
persists state after the context window ends.

This is a **requirement with acceptance criteria** (AC12, AC13), not a caveat. Rev 1 recorded
it as a risk; that was the wrong weight.

**Deferred implementation, deliberately.** The follow-on this requirement points to —
capacity-adaptive briefing depth (§9) — is *new work*, not reconciliation. It is recorded
here and built immediately after merge, so that combining two frameworks and inventing a
third capability do not happen in the same change. The interim protection is AC12: the
human-facing surfaces are retained intact through the merge, so the developer is never worse
off than under v3.5 while the follow-on is pending.

## 4. Measurement: continuous instrumentation, not a gate

**Developer decision (2026-08-05, locked): judgment-gated.** Rev 1's A/B is withdrawn as an
acceptance gate. The panel's assessment, which this spec accepts:

- With N=1 per arm, three of four proposed metrics (output tokens, turn count, rework loops,
  wall-clock) could detect only an order-of-magnitude effect. Only **subagent-call share**
  carried structural signal, because it is driven by workflow rules rather than stochastic
  execution.
- The chosen task was **not equivalent** across trees. Verified: `assertion_store/embeddings.py`,
  `mcp_server/server.py`, and `tests/test_mcp_server.py` all differ (v4 had already fixed the
  eager-import bug that makes those tests skip on main), so the task was strictly easier on
  v4 for reasons unrelated to the thesis. `assertion_store/substrate.py` is identical.
- The **v4 arm had no instrument**: no `scripts/telemetry/`, no `stop_hook.py`, no
  `metrics/model_call_log.jsonl`.
- Neither tree's gate measures coverage for `assertion_store/` or `mcp_server/` at all, so
  "gate-green" was undefined for the task, and defining it required editing the one file the
  task design forbade touching.
- The **measurement site was wrong**. This framework is a hub; its artifacts are properly
  judged against derived-project usage, not template-local activity. Rev 1 measured the
  workshop, not the tools in use.

Spending weeks to earn a probable "inconclusive" buys false confidence, not information.

### 4.1 What is kept

**Continuous instrumentation, gating nothing.** `metrics/model_call_log.jsonl` already holds
**1,411 records at rev-1 authoring time across 20 sessions, 2026-06-23 → 2026-08-04**, with
`source_kind` separating main-loop from subagent calls. The file is a live, growing stream —
it had grown to 1,424 by the time the panel checked, which is itself the reason any figure
quoted from it must carry the query that produced it, not a hand-transcribed number.

The sensor is retained and re-established on the merged tree (§6.2) so that in six months
there is a record of what actually happened. That is the honest version of the falsification
plan ADR-0030 said it wanted.

### 4.2 Named falsifiers (what would change our mind)

Recorded so this decision is revisable rather than merely asserted:

- **F-A** Subagent-call share does not fall materially after the merge. v4's central
  productivity claim is that it removes dispatch overhead; if the share is unchanged in real
  work, that claim is wrong.
- **F-B** Deferred briefings accumulate faster than v3.5's deferred education gates did.
  That would mean the leaner education path degraded the human's understanding — the one
  thing the framework exists to protect.
- **F-C** A derived project's `/apply-framework` run (P6) surfaces capability regressions
  that template-local work did not. This is the measurement site the panel identified;
  P6 is where it actually gets tested.
- **F-D** `metrics/model_call_log.jsonl` shows no reduction in output tokens per session at
  comparable work over a trailing quarter.

None of these gates this work. Each has a named owner phase and is recorded in ADR-0031.

### 4.3 Deferred probes

- `CLAUDE_CODE_SIMPLE=1` ablation arm — answers "is v4 *itself* still over-scaffolded?"
- `opus_1m` absolute-cap recalibration (§5, F1a).

## 5. Findings produced during this work

**F1 — the context sensor was miscalibrated by ~5×, silently.**
`config/model_context_profiles.yaml` mapped no Claude 5 model, so `claude-opus-5`,
`claude-fable-5`, `claude-sonnet-5`, and `claude-opus-4-8` all fell through to
`defaults.profile: haiku_200k` — fail-safe by design (ADR-0018 AC-8), but measuring a
1M-window model against a 200K window. Observed live: a hard wrap-up order at ~131K resident
context, ~13% of the actual window. This fired on every session, on every frontier model, in
this repo **and in all three derived projects**. Fixed 2026-08-05 (four map entries, the
file's own documented maintenance action); verified by resolution test.

F1 is the specimen case for §3.1: an instrument correct when written that became a large
invisible productivity tax. v4's disposition — delete the wrap-up protocol wholesale
(supersedes ADR-0018) — removes the tax *and* the sensor. The third bucket says
**recalibrate**.

**F1a — carried.** Even corrected, `opus_1m` binds at `soft_abs_cap_tokens: 140000` /
`hard 180000` — 14%/18% of a 1M window, set 2026-05-23 against Opus 4.7. Plausibly still
conservative. Deferred to §4.3.

**F2 — the quality gate does not enforce what `PHILOSOPHY.md` says it enforces.**
`PHILOSOPHY.md` states that ADRs cite their `discussion_id` "*and the quality gate enforces
this today*". It does not. `check_adrs` computes
`missing_fields = required_fields - set(frontmatter.keys())` — **key presence only**. An empty
value passes. Verified live: ADR-0031 passed the gate with `discussion_id:` blank, which is
also how all three artifacts of this reconciliation came to be untethered from Layer 1 until
the Steward caught it.

Not fixed on `main`, deliberately — editing the gate now enlarges the very merge surface §6.1
is trying to keep small. **Disposition: the fix lands with the Wave-2 gate port (AC2 scope) as a
*tethering* check — `discussion_id` non-empty **and** resolving to a discussion directory with a
non-empty `events.jsonl`.** A non-empty-*value* check would not have been sufficient: rev 3
populated the field while both referenced discussions were zero bytes, so the artifacts remained
untethered while passing. The defect being fixed is untethered artifacts, not blank fields.

**Independently of whether that code lands, AC14 corrects `PHILOSOPHY.md`'s sentence
unconditionally** — the merged tree must not ship a claim of enforcement the code does not
perform. This is the same prose-guarantee failure as the `--rebaseline` "lock" (§6.1), located
in the constitution rather than the spec.

## 6. Collision dispositions

### 6.1 C1 — `scripts/quality_gate.py`

Port Wave 2 (profiles + debt baseline + ergonomics) onto v4's gate. Wave 2 is deterministic
reward-function code — governance by v4's own test, and precisely the external verification
§2's guidance keeps.

- **Duplicate function.** Reconcile the independently-added `check_promotion_backlog()`
  (§3.3); decide explicitly whether main's `_emit_warn_line` extension is kept.
- **Inherited defect, tracked not silently adopted.** v4's `_is_retired` retires ledger
  entries on `git mv` and fails open on malformed `file` cells (REV-20260728-140000 nb#4).
- **Correction to rev 1: `--rebaseline` is not a lock.** It is a `store_true` flag whose
  consent requirement lives in a docstring, argparse help, a warning printed *after* the
  baseline is rewritten, and a log field. `python scripts/quality_gate.py --rebaseline` exits
  0 today. The honest description is a **reward-function audit trail**. Rev 1 called it a
  lock; that is exactly the prose-guarantee failure this spec exists to prevent. See AC2.

### 6.2 C2 — the Stop hook and the cost sensor

v4 deleted `scripts/stop_hook.py` (317 lines) **and configures no Stop hook**, while
retaining `collab_loop.py`, `ask_developer.py`, `notify.py` — so the restored ntfy loop lost
its automatic driver. `scripts/collab_loop.py` is byte-identical across trees, so
`match_choice` is available on the v4 base at zero cost.

Both the ntfy loop (human I/O, orthogonal to model capability) and the cost sensor
(§4.1 instrument) are re-established. **`tests/test_stop_hook.py` is the specification** —
see AC3.

### 6.3 C3 — ADR-0029 ID collision

**Developer decision (locked):** v4's `ADR-0029-framework-v4-scaffolding-removal` →
**ADR-0030**; this reconciliation is **ADR-0031**. main's ADR-0029 (RepoCademy) keeps its
number: older (07-14 vs 07-28), already merged, and referenced by `docs/education/CONTRACTS.md`,
the versioned contract `insight_journal` builds RepoCademy Phase 1/2 against.

**Corrected count:** renumbering touches **23 files** in the v4 tree excluding sealed
discussions (24 including them; sealed discussions are immutable under merged Principle #4 (ADRs/records are never deleted) and are
not edited). Rev 1 said 13.
Verify: `grep -rl "ADR-0029" --include="*.md" --include="*.py" --include="*.yaml" . | grep -v "^./discussions/"`

### 6.4 C4 — education

Complementary, not competing. **RepoCademy (main)** answers *which gates are open and how a
clearing is proven across a trust boundary*; **v4** answers *how deep should this briefing be
and was it delivered or deferred*. Both are governance-by-code. The overlap is narrow: two
ledgers of deferred education.

The entire RepoCademy trust boundary is **absent from the v4 base** — no `scripts/education/`,
no `gates.yaml`, no `CONTRACTS.md`, no `tests/test_ingest_walkthrough_session.py`. See
AC5a/5b/5c.

### 6.5 C5 — `.claude/settings.json`

`docs/settings-v4.patch` is stale. It targets a `Stop` block with `"matcher": ""` and
`timeout: 660`; the live file has no matcher and `timeout: 680`.

**Corrections to rev 1:** the patch does not fail cleanly — `patch --dry-run -p0` applies
hunk #1 and fails hunk #2, so a partial application strips `statusLine` (the F1 instrument's
display) and leaves a `.rej`. And rev 1 named the *milder* failure mode. The worse one, from
REV-20260728-140000 B5: a missing `bash` hook exits 127 (fails open), but a missing
`python scripts/stop_hook.py` exits 2, which for a Stop hook means **block-stoppage plus
stderr injected into context every turn**. Six hook paths are dangling on the v4 tree, not
five.

A fresh patch is regenerated against the current file, downstream of C2. `settings.json` is
agent-protected: the developer applies it by hand.

### 6.6 C6 — the unclassified remainder (new)

**25 files / 10,297 lines** exist under `scripts/` on main and not in v4 — including
`scripts/telemetry/` (ADR-0020), which rev 1 never mentioned in any section, including
out-of-scope. Rev 1 disposed only of the five named collision surfaces plus the three items
REV already caught, which is why it could not substantiate its own claim not to be
re-inflating.
Verify: `comm -23 <(find scripts -name '*.py' | sort) <(cd $V4 && find scripts -name '*.py' | sort)`

Every one of these files gets an explicit disposition — bucket + traceable question, or
"stays deleted, no question found" — published as an appendix to ADR-0031. Known shape:
`goal_loop.py` (1,704 lines) stays deleted, explicitly re-affirmed rather than left silently
undecided; `git_visualize.py` (931 lines) is a human-facing convenience tool that fits none
of the three buckets cleanly and needs a stated call.

### 6.7 C7 — the framework-evolution read-out (new, M9)

The lineage *engine* survives the merge with a live caller — verified:
`scripts/distribute/change_package.py` imports `scripts/lineage/`, and `tests/test_lineage.py`
is present in both trees. REV-20260728-140000's B6 note that `scripts/lineage/` was orphaned is
no longer true on the v4 HEAD.

What is lost without a decision is the **read-out**: v4 has no `steward` agent, no `/lineage`,
no `/promote`, and no Framework Evolution section in `CLAUDE.md`. So nothing reports drift to
the developer, and no artifact class records a framework-evolution decision — at exactly the
moment P6 pushes a re-constituted framework into three derived projects.

**This ADR is itself the counter-example**: the Steward gate is what caught the constitution
being silently rewritten (§6.8 / ADR-0031 Decision 6). A merged framework with no Steward and
no framework-evolution artifact class would not have caught it.

Disposition required before P6, under AC7's rule that silence is not a disposition: name who
reports lineage drift and which artifact class records a framework-evolution decision on the
merged tree — or record the retirement of both explicitly.

### 6.8 C8 — the constitution (new; Steward BLOCKING-1)

`CLAUDE.md` and `PHILOSOPHY.md` were edited on **both** sides (v4 `+120/−109` and `+102/−21`;
main `+1/0` and `+33/0`) and rev 2 named neither file in any section, including out-of-scope.
Taking v4 as the base would have reduced nine Non-Negotiable Principles to six with nobody
deciding it.

Resolved per-principle by the developer 2026-08-05 → **seven principles**; the decision table
and rationale are ADR-0031 Decision 6, enforced by AC14.

## 7. Acceptance criteria

- **AC1** Reconciliation branch off the v4 base; `main` untouched until an explicit developer
  merge decision.
- **AC2** Wave 2 gate ported; golden-fixture, swap-case, and baseline-ratchet tests green.
  The `--rebaseline` consent requirement is described honestly as an audit trail **or** a
  denial mechanism is implemented and asserted by a test — not documented as a lock it is not.
  **Additionally (F2), `check_adrs` gains a tethering check with a test:** `discussion_id` must
  be non-empty **and** must resolve to a discussion directory containing a non-empty
  `events.jsonl`. A non-empty-value check alone would not have caught this reconciliation's own
  defect — rev 3 populated the field while the referenced discussions were zero bytes.
- **AC3** A Stop hook exists carrying both the ntfy flow and the telemetry kick, **and
  `tests/test_stop_hook.py` is restored unmodified and green**, including
  `TestAllowListInjection`, `TestSinglePollerDiscipline`, `TestNoSlugAndAsciiInvariants`. Any
  leaner reimplementation is written against that test file; the test is not rewritten to fit
  the implementation.
- **AC4** ADR renumbering complete across all 23 files; no dangling `ADR-0029` reference;
  `CONTRACTS.md` cross-repo reference intact.
- **AC5a** `scripts/education/`, `gates.yaml`, `CONTRACTS.md`, `docs/education/fixtures/`,
  `tests/test_ingest_walkthrough_session.py`, `tests/test_gate_registry.py` restored and green.
- **AC5b** The deterministic ingest remains the **sole writer** of any artifact derived from
  phone-generated content, whichever ledger is authoritative; the "reader" is read-only in
  code, not by convention.
- **AC5c** If `gates.yaml`'s schema or writer topology changes, `CONTRACTS.md`
  `contract_version` is bumped and flagged as breaking for `insight_journal`.
- **AC6** Fresh `settings-v4.patch` generated against the current file, verified to apply
  cleanly, confirmed to preserve the Stop block, **and confirmed that every hook path named in
  the merged `settings.json` resolves to an existing file**.
- **AC7** Every main-only file under `scripts/` (25 files), **`.claude/` (66 files — 23 skills,
  20 commands, 11 agents, 8 hooks, 4 rules), and `docs/` (21 files, excluding adr/ and
  reviews/)** carries a published disposition. Group granularity is acceptable, with **named
  individual dispositions** for at minimum `.claude/rules/security_baseline.md`, the Always-On
  Invariants block, the cross-agent dispatch protocols, **`.claude/commands/review.md`, and
  `.claude/skills/selecting-review-gates/`**. The classification is reviewed by an independent
  context (R-B3).
  **Plurality is explicitly in scope and may not be dissolved into a group disposition.** The
  merged tree must state the review panel size for critical-risk changes, and must scope v4's
  "prefer one agent over several" to ordinary delegation so it cannot be read as governing
  review panels. ADR-0031 Decision 6 retires main #3's *posture* half while keeping plurality
  as a dispatch concern; without this clause that keeping is an assertion with no criterion —
  the same prose-commitment defect this spec exists to prevent, applied to the one mechanism
  the ADR credits with catching both of this reconciliation's critical findings.
  *Rationale (M4): the instruction surface is the entire subject of ADR-0030 and the only
  surface where a deletion is silent — an absent skill produces no import error. Rev 2 required
  disposition of the 25 scripts and left 87 prose files unaddressed, which is the weaker half
  of the requirement.*
- **AC8** ADR-0031 records the reconciliation, the §3.1 taxonomy change, the §4.2 falsifiers,
  and the §5 findings — including that base selection was a judgment call.
- **AC9** Full suite green and quality gate green. `pytest` collects the **18 test modules**
  present on main and absent on the v4 base, or each omission is explicitly dispositioned.
- **AC10** No push, no merge, no propagation without explicit per-instance developer
  confirmation.
- **AC11** `.claude/hooks/` remains in `PROTECTED_PATTERNS` on the merged tree, asserted by a
  test. Restored hook files are applied by the developer by hand alongside `settings.json`.
- **AC12** **No net thinning of the human-facing surface** (§3.4). The merged tree retains, at
  no less capability than the better of the two trees: `/teach` + `scripts/assess_risk.py` +
  `scripts/briefing.py` (v4), the `educator` agent, `/walkthrough` + `/quiz` (main), and the
  RepoCademy registry + ingest (AC5a). Any human-facing surface *not* carried forward is
  listed explicitly with its replacement named — silence is not a disposition.
- **AC13** The post-merge education gate is passed on the reconciliation itself and includes an
  **explain-back check in production form** — the developer states, in their own words and as a
  written artifact captured to Layer 1, why each retained governance mechanism exists.
  Multiple-choice recognition does not satisfy it. Prerequisites and consequence:
  - **AC13a** ADR-0031 Appendix A carries the **closed enumeration** of retained governance
    mechanisms, seeded at merge into `docs/education/governance-mechanisms.md` as the live
    referent (the ADR is immutable; several rows are contingent on AC2/AC3/AC5a/AC11).
    Rows carrying a known weakness are marked, and an explain-back on such a row is satisfied
    **only if the developer can also state the weakness** — otherwise the criterion certifies a
    false belief.
  - **AC13b** **A mechanism that cannot be explained is a defect in the mechanism, not in the
    developer.** On a failed explain-back, after a fair re-teach, exactly one of three must
    happen before the item is resolved: (1) the mechanism is **simplified** until it can be
    explained; (2) its **documentation is rewritten** and the explain-back re-attempted; or
    (3) it is **explicitly retired by a recorded developer decision**. It is **never removed
    automatically**, and never on the basis of a single failed attempt — the explain-back
    signal varies with the developer's attention state (§3.4), and using a variable signal to
    trigger irreversible removal of a safeguard would invert the requirement this spec exists
    to serve.
  - **AC13c** Unresolved AC13 items **block P5 (public promotion) and P6 (distribution)** —
    the two classes where merged Principle #5's hybrid makes skip unavailable (ADR-0031 Decision 6).
    They do not block ordinary work.
  - Rationale: this makes "the developer cannot follow this" an alarm about framework
    complexity — the retired main Principle #8 brake, relocated to `PHILOSOPHY.md` by the same decision
    record — rather than a judgement about the developer.
  - **AC13d** **The explain-back is judged by an independent context**, not self-assessed —
    the `educator` agent or a non-participating specialist. Self-assessment here is the
    generator-evaluating-itself shape merged Principle #3 forbids.
  - **AC13e** **Open AC13 items are enrolled in the `gates.yaml` registry** (AC5a) and surfaced
    by `/status`, so "unresolved" is visible rather than merely tolerated. Without a ledger,
    13b's non-removal rule would let items accumulate invisibly — the exact failure mode
    RepoCademy was built to end.
- **AC14** **The constitution is a dispositioned collision surface.** The merged tree ships one
  reconciled `CLAUDE.md` + `PHILOSOPHY.md` implementing the seven-principle list decided
  per-item by the developer (ADR-0031 Decision 6): #9 kept unchanged, #6 in its hybrid form,
  #3 retired, #8 moved to `PHILOSOPHY.md`. No principle is added, removed, or reworded outside
  that record. Internal principle-number citations across `CLAUDE.md`, `PHILOSOPHY.md`,
  ADR-0031, **this spec**, and REV-20260805-213438 are re-pointed to the merged numbering
  (ADR-0031 Decision 6
  carries the authoritative seven-row table). **Count strings are in scope and must all read
  "seven"** — including main's `PHILOSOPHY.md:76` and `:99`, which already say *"eight"* against
  a nine-principle `CLAUDE.md`, proving these strings rot undetected. `PHILOSOPHY.md`'s refusal
  list is re-pointed per ADR-0031 Decision 6 so "authoritative single-source answers" retains a
  paired principle.
  **Unconditionally in scope (F2):** `PHILOSOPHY.md`'s claim that the quality gate enforces ADR
  `discussion_id` citation is corrected to match what the code actually does. The merged tree
  must not ship a false enforcement claim regardless of whether AC2's code fix lands.
- **AC15** **The interim briefing safeguard is a default, not a request** (§8 R7): for the
  merge→§9 window, `assess_risk.py` floors briefing depth at `standard`, and `/teach` asks one
  capacity question before selecting depth. Asserted by a test. Rev 3 argued this correctly and
  then left the remedy as prose in a Risks section, which is the defect class this spec exists
  to prevent.
## 8. Risks

- **R1 — this is a judgment call.** The panel established that rev 1's evidence framing did
  not gate anything. Rather than repair it into a weak experiment, the decision is recorded as
  judgment with named falsifiers (§4.2). The risk is that judgment is wrong and the falsifiers
  are checked too late.
- **R2 — the measurement site is deferred to P6.** Derived-project usage is the correct
  denominator, and it is not consulted until after merge. This is a real ordering weakness,
  accepted so the framework is not distributed mid-reconciliation.
- **R3 — re-inflation.** Mitigated by R-B1/R-B2/R-B3 and AC7, which force the 10,297-line
  remainder to be dispositioned rather than left unaddressed.
- **R4 — v4 drift.** Offline-built and stale; main keeps moving. Mitigation: no further
  feature work on main during reconciliation.
- **R5 — `settings.json` + hooks.** Manual, protected, merge-blocking steps outside agent
  control, now covering both files (§3.2, AC11).
- **R6 — `PROTECTED_PATTERNS` is enforced only on the `Write|Edit` matcher.** `Bash(*)` routes
  around it (`cp`, `sed -i`, `tee`, `python -c`), and `pre-push-main-blocker.sh` allows any
  `cd`-prefixed push by design — the same shape as the counter-evidence in §2. Pre-existing on
  both trees, not a merge regression. Recorded so §3.2 is not read as a stronger guarantee than
  the code provides.
- **R7 — legibility (now a requirement, §3.4; residual risk only).** The developer is the
  gatekeeper, and merged Principle #6 approval requires them to understand what they are approving.
  Rev 1 framed the model/human tradeoff as an unresolved tension; §3.4 establishes there is no
  tradeoff, because the two surfaces are separable. The **residual** risk is narrower and
  real: between merge and the §9 follow-on, briefing depth is still chosen from change-risk
  alone, so a high-risk change landing on a low-capacity day is under-served.

  **The interim mitigation is a default, not a request (M7).** Rev 2 said depth "is raised on
  request at any time" — but on a low-capacity day the developer is *least* likely to make the
  request; that is the definition of the condition. Relying on it is a prose guarantee
  protecting merged Principle #6 approval capacity, which ADR-0030's own mechanism corollary forbids.
  So for the merge→§9 window: **briefing depth floors at `standard`**, and `/teach` asks one
  capacity question before selecting depth. A few lines in `assess_risk.py`, and it converts
  the safeguard from something the developer must remember into something that happens.

  Remaining mitigations: AC12 (no net thinning), AC13 (explain-back). **On a low-capacity day
  the answer is never "skip the gate"; it is "hold more of the thread."**

## 9. Named follow-on: capacity-adaptive briefing depth

Recorded here as a committed next step, **not** built in this reconciliation (§3.4).

**The gap.** v4's `scripts/assess_risk.py` derives briefing depth (light / standard / deep)
from the diff alone. That is one input. The developer's requirement establishes a second:
their current capacity, which oscillates. The same change warrants a different briefing on a
piercing-focus day than on a scattered one, and the framework can neither know this nor ask.

**The shape.** Change-risk becomes the **floor**, not the answer. Depth is adjustable at
request time in either direction ("full walkthrough" / "three lines, I'm on fumes"), the
choice is recorded rather than judged, and no path reduces depth below the risk floor without
recording a deferral. Raising depth is always free.

**Sequencing.** Immediately after P4 (merge to private main), and **before P6**
(`/apply-framework` distribution to derived projects) — distribution is precisely when the
developer most needs to hold the system in their head, and it is the point of highest
irreversibility.

**Falsifier F-B watches this**: if deferred briefings accumulate faster than v3.5's deferred
education gates did, the leaner education path is degrading understanding and this follow-on
is urgent rather than merely queued.

## 10. Out of scope

- `opus_1m` cap recalibration (F1a) and the `CLAUDE_CODE_SIMPLE=1` arm (§4.3).
- Wave-2.1 (gate file split) and wave-3.
- `scripts/session_supervisor.py` auto-launch: dispositioned under AC7 like every other
  main-only script, but its `bypassPermissions` behaviour is **not** re-armed as part of this
  work.
- Public promotion (P5) and `/apply-framework` distribution (P6) — separate developer-gated
  phases after merge and at least one live-fire task.
