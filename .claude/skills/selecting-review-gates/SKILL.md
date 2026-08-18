---
name: selecting-review-gates
description: Risk tiers (low/medium/high/critical), the specialist-selection matrix, minimum quality thresholds, and the advisory-finding lifecycle. Use when running /review, /ship, or /retro to assess change risk, pick the specialist panel, set the collaboration mode, or track and escalate advisory findings.
---

# Review Gates

## Severity Calibration

For consistent severity classification, use the `.claude/skills/severity-calibration/SKILL.md`
rubric. Specialists must state an explicit `Severity: <tier>` marker on each finding so the
capture pipeline can parse it. When in doubt, default down (see the skill for the default-down
rule and concrete tier examples).

## Minimum Quality Thresholds
- Test coverage >= 80% for new and modified code
- No critical or high-severity security findings left unaddressed
- All public functions must have docstrings
- All new modules must have module-level docstrings
- No failing tests in the test suite
- Data displayed in the UI that is provably incorrect at implementation time (not hypothetically incorrect under edge conditions) must be classified as blocking regardless of whether it affects core functionality

## Architectural Gates
- Any architectural change requires an ADR in `docs/adr/`
- New module boundaries require architecture-consultant review
- Dependency additions require security-specialist review
- New external dependency integrations (OS APIs, hardware, network services) must define an abstract interface enabling test substitution

## Education Gates

**The in-session gate is a tutoring loop, not a pass threshold.** It clears when the
developer can explain the change *and its rejected alternatives* in his own words —
however many turns that takes. A session that ends in a score has failed the gate even
when the score is high. The mechanism lives in `.claude/agents/educator.md` §2 (the loop,
the entry points, the rubric) and is driven by `/walkthrough` and `/quiz`.

**Read "in-session" as load-bearing, not as filler.** There is a second education path —
the ADR-0029 ingested-transcript path, where a phone-side session is validated and
replayed — and *that* one gates arithmetically, on the 0.70 threshold: the formula
decides CLEAR-ELIGIBILITY, and the flip to `cleared` is the developer's own
`gate_registry.py clear`, never the ingest's ("I clear it", ADR-0035). The two are
described separately in the pass-threshold bullet below. Do not collapse them: a
statement true of one is false of the other, and a governance file that publishes only
one half contradicts a LOCKED contract.

- Required for all complex or high-risk changes before merge
- Four-step gate: walkthrough → quiz → explain-back → merge
- **On a miss, re-explain from a different entry point and ask again.** Never grade and
  move on; never re-word the same frame and call it a re-explanation
  (`.claude/agents/educator.md` §2.2 enumerates the entry points)
- Bloom's level mix: 30% Understand/Apply, 70% Analyze/Evaluate/Create. This is the
  **overall mix** for a session. Difficulty *also* ramps **within-session** (Understand
  first, Analyze and Evaluate later) — that within-session ordering rule is not a second,
  different ratio, and neither should be "fixed" into the other
- Quiz pass threshold: 70% — **two different mechanisms use this one number. Keep them
  apart:**
  - **Per item**, it is a recording convention: it sets `education_results.passed`, which
    is bookkeeping for trend analysis. It is **not** the criterion for the *in-session
    tutoring loop* below — that one clears when he explains the change and its rejected
    alternatives in his own words (`.claude/agents/educator.md` §2.1), however many turns
    that takes, and never on a percentage
  - **In aggregate, it IS a gate criterion — for the other path.** The ingested-transcript
    path (ADR-0029) gates a real registry gate on it: `docs/education/CONTRACTS.md` §1.4
    (rev 1.1) is LOCKED at `clear_eligible ⟺ walked AND quiz_avg >= 0.70 AND
    explain_back_passed`, and `scripts/education/ingest_walkthrough_session.py::_decide`
    computes exactly that. The formula's verdict is CLEAR-ELIGIBILITY — the ingest
    records an additive `clear_eligible` marker on the gate, and the flip to `cleared`
    is the developer's own `gate_registry.py clear`, never the ingest's (ADR-0035).
    **Never write "no gate clears on this number."** The number still decides the gate —
    eligibility is the gate decision; the developer's clear is its enactment. Check it
    wherever you are reading this, rather than trusting a line number that will have
    moved:
    `grep -n "PASS_THRESHOLD\|clear_gate" scripts/education/ingest_walkthrough_session.py`.
    The hits inside `_decide` are the aggregate eligibility decision; the `clear_gate`
    hits are the docstring and step-5 comment stating that the automatic path never
    calls it
  - `tests/test_education_gate.py::TestPassThresholdSemantics` pins this distinction
- At least 1 debug scenario and 1 change-impact question per quiz — the debug scenario
  must be grounded in a real fragility signal present in the source (a guard, a `TODO`,
  retry logic, a regression-ledger row). Never invent a bug
- Educational intensity adapts to demonstrated competence (scaffolding fades)
- The developer may stop or defer at any point, with no penalty framing. A deferral is
  recorded in `docs/education/gates.yaml` via `scripts/education/gate_registry.py add`,
  never dropped — **and when he comes back and demonstrates it, `/quiz` Step 5 presents
  the evidence and the exact `gate_registry.py clear` command, and the developer retires
  it himself ("I clear it", ADR-0035).** A registry that only ever gains rows is not a
  measurement: it reports debt that has in fact been paid, and the backlog it feeds stops
  meaning anything. The registering direction is agent bookkeeping; the clearing
  direction is presented in `/quiz` Step 5 for the developer to run — never run by the
  agent

**Any other file that restates the Bloom mix must restate the same ratio — and as of
2026-08-09 two still do not.** Measured with
`grep -n 'Understand/Apply\|Analyze/Evaluate' docs/education/CONTRACTS.md docs/FRAMEWORK_SPECIFICATION.md`:
`docs/education/CONTRACTS.md` (line 321) and `docs/FRAMEWORK_SPECIFICATION.md` (line 892)
still publish the superseded consumer-side ratio, and CONTRACTS.md attributes it to a
`review_gates.md` rule that no longer exists (`.claude/rules/` holds four files, none of
them that one). Both are outside the change that corrected the ratio here. Both are
registered with their measured values in the `KNOWN_STALE_MIX` register in
`tests/test_education_gate.py`, so editing either fails
`TestBloomRatioAgreement::test_known_stale_mix_register_does_not_rot` rather than drifting
quietly — but the register only *records* the debt, it does not pay it. **Until it is
paid, this block and `.claude/agents/educator.md` §2.6 override both**, and a derived
project that received CONTRACTS.md has the stale number. Paying it is doc-sync work
(`syncing-framework-docs`); CONTRACTS.md is a versioned cross-repo contract and should be
re-pointed with a contract revision, not edited in passing.

`tests/test_education_gate.py::TestBloomRatioAgreement` fails if this skill,
`.claude/agents/educator.md` and `.claude/commands/quiz.md` disagree, or if a *new* file
joins the two stale ones above.

Those three files **did** disagree — `/quiz` was ordering the educator to do the opposite
of its own charter — and the reason to pin it mechanically is not that the disagreement
was invisible. It was *seen, and not acted on*. Measured: `git log -S "30% **Understand/Apply**"
-- .claude/agents/educator.md` returns `957b7a5`, 2026-05-12, the day the charter moved to
30/70 without its two consumers following. `docs/reviews/REV-20260513-051947.md` line 80
names the contradiction verbatim the very next day and proposes the exact disposition
applied here — under the heading **"Other Advisories (lower priority)"** at line 78. It
stayed live there until 2026-08-08: 87 days.

That is the point, and it is a stronger argument than "nothing noticed" would have been.
A review caught it in one day; it was filed as a lower-priority advisory and then no
review report carried it forward — the Tracking Rules below require exactly that
carry-forward, and `/retro`'s stale-advisory flag (> 2 sprints) is exactly what should
have caught the silence. Detection was never the failing part; *acting* on detection was.
An advisory is a note that depends on someone re-reading it. A test is a ratchet that does
not. Where a finding names a contradiction between two live files, prefer the ratchet.

## Review Activation

### Review plurality — the normative home

Principle #3 requires only *a* separate context. Plurality — *several* independent contexts, not
one — is a stronger property, and **this skill is where it is written down**. ADR-0031 Decision 6
retired the posture half of the old "collaboration precedes adversarial rigor" principle and moved
plurality into review dispatch so it could not be lost; `PHILOSOPHY.md` (*Growth has a brake*)
records why it was worth keeping. The one-reviewer-out-of-four count quoted below is not an
estimate: it is the figure recorded in ADR-0031, Appendix A (retained governance mechanisms).

### Panel size — review plurality

- **Critical risk: at least 3 independent specialists**, each dispatched in a separate context,
  none of which sees another's findings before submitting its own.
- **High risk: at least 2.**
- **Medium / Low risk: 1 is sufficient.**

Why the floor exists: this framework's two most serious findings — a wrong merge base, and a
constitution being silently rewritten — were each caught by exactly **one** reviewer out of four.
A single reviewer's blind spot becomes the project's. "Prefer one agent over several" governs
ordinary delegation; it does not govern review panels.

**These are floors, not targets.** The Agent Count column below already satisfies them; the
domain-specialist triggers add specialists *on top of* the floor rather than replacing it.
Dropping below a floor is a decision to record with a reason, never a default to fall into.

**Where the integers came from, stated exactly.** ADR-0031 Decision 6 ratified that plurality is
retained as a *dispatch* concern and that panel size lives here and in `/review`. It does **not**
state a number, and neither does ADR-0032 — the integers above were chosen by the slice that
landed the mechanism. Read them as a deliberately conservative red line under the tier table
rather than as a ratified target: they are the level below which a panel must never fall, not the
level to aim for. Raising or lowering one is a Framework Evolution change (Steward gate, then
developer approval), and `TestPluralityLanded::test_selecting_review_gates_states_numeric_panel_floors`
pins them so that change is a visible edit to an assertion rather than a quiet edit to prose.

**Any other file that restates these floors must restate them identically.** `/review` — the
command that actually dispatches the panel — carries a byte-identical copy of the block above
(its heading through "…it does not govern review panels."), so a dispatcher reading only the
command still sees the floor. Two copies of a safety number is how a floor quietly becomes two
floors, so every claim in this paragraph is checked by
`tests/test_constitution_consistency.py`, not merely asserted here:

- `tests/test_constitution_consistency.py::TestPluralityLanded::test_plurality_floors_do_not_drift`
  fails if any live file states a different number for a risk tier.
- `TestPluralityLanded::test_every_restatement_of_the_block_is_verbatim` fails if a restating
  file's copy differs from this one by a single byte, and fails if `/review` stops carrying it
  at all — so "byte-identical" is measured rather than claimed.
- `TestGovernanceLocationClaims::test_governance_claims_name_files_that_contain_the_mechanism`
  fails if `CLAUDE.md` or `PHILOSOPHY.md` names a home that does not carry the block.
- `TestProseReferencesResolve::test_cited_pytest_node_ids_exist` fails if any test name in this
  list stops resolving — these bullets are themselves a claim about where enforcement lives, and
  are held to the same standard as any other location claim.

### Risk Tiers and Agent Selection

| Risk | Mode | Agent Count | Mandatory Agents | Examples |
|---|---|---|---|---|
| Low | Ensemble | 2-3 | qa-specialist + 1 domain specialist | Docs, config, simple fixes |
| Medium | Structured Dialogue | 3-4 | qa-specialist, architecture-consultant + 1-2 domain | New features, refactoring, dependency updates |
| High | Dialectic or Adversarial | 4-5 | qa-specialist, architecture-consultant, security-specialist, independent-perspective | Security code, architecture changes, API contracts |
| Critical | Adversarial | 5-6 | Full panel | Auth, payments, data migration, infrastructure |

### Domain Specialist Triggers

| Change Type | Specialist to Include |
|---|---|
| Database, ORM, migrations | performance-analyst |
| API routes, middleware | architecture-consultant |
| Network, auth, API security | security-specialist |
| New module or significant feature | architecture-consultant, docs-knowledge |
| UI/UX with accessibility concerns | ux-evaluator, qa-specialist |
| UI files (3+ files touching `*.html`, `*.css`, `*.js`, `*.tsx`, `*.vue`, or other frontend assets) | ux-evaluator |
| External API integration | security-specialist, performance-analyst |
| Framework infrastructure (.claude/, scripts/) | docs-knowledge |

The facilitator assesses risk and selects specialists per the table above.

## Advisory Lifecycle

Advisory findings (non-blocking recommendations) follow a structured lifecycle to prevent accumulation and ensure valuable suggestions aren't lost.

### States

1. **Open** — Finding raised during review, not yet addressed
2. **Accepted** — Developer acknowledges and plans to address
3. **Deferred** — Intentionally postponed with justification (must include target date or trigger)
4. **Resolved** — Finding addressed in a subsequent commit
5. **Declined** — Developer decides not to address, with rationale recorded

### Tracking Rules

- Advisories persist in the review report where they were raised
- Advisory findings must be carried forward in the next review report as "open advisories" until either resolved or formally accepted as known limitations. Each review report must include a tally of open advisories from prior phases.
- Advisories with 3+ recurrences across reviews trigger promotion to **blocking** in subsequent reviews (Rule of Three)
- The `/retro` command aggregates open advisories and flags stale ones (> 2 sprints old)
- Declined advisories require a one-sentence rationale to prevent knowledge loss

### Escalation

An advisory escalates to blocking when:
- The same pattern appears in 3+ independent reviews
- A related bug is found in production (post-incident)
- The advisory addresses a security concern that increases in severity
