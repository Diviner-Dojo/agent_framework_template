# Proposal — Mechanical count-drift check for framework documentation

> **Status**: DRAFT — for your review and the Steward gate. **Nothing is applied.**
> This proposes a new framework capability; per the evolution path it requires
> Steward APPROVE → your approval (Principle #7) → `/review` → implementation →
> doc sync. This file is the pre-Steward proposal artifact only.
>
> **Decision lineage**: derives from the round-2 deck-revision session of 2026-06-14
> and review `REV-20260614-023301` (DISC-20260614-023301). During that session the
> developer observed: *"we are supposed to have a hook that forces the documentation
> to be updated as this framework evolves."* Investigation found **no such mechanism
> exists** — doc-sync is enforced only by the advisory, agent-mediated
> `syncing-framework-docs` skill (fires at `/review` / `/ship` / Steward gate). The
> evidence that this is insufficient is the session itself: the framework deck had
> drifted to "8 principles / 19 skills" (actual 9 / 21), **and the round-2 edit
> intended to fix it miscounted "22 skills" (actual 21)** and listed two phantom
> skills. Countable drift slipped past a human twice in one session.

---

## 1. Problem

CLAUDE.md Principle #2 says capture/enforcement must be **automatic — "enforced at the
command/tooling layer; the model cannot opt out."** Documentation sync is the opposite:
opt-in, model-discretion. The `syncing-framework-docs` skill is a checklist; whether it
runs depends on an agent choosing to load and follow it. Nothing deterministic compares
a documented count against the real repository.

The 9 wired hooks (`pre-tool-use-validator`, `pre-commit-gate`, `pre-push-main-blocker`,
`auto-format`, `post-tool-use-unlock`, `context-guard`, `pre-compact`, `session-start`,
`context-statusline`) and `scripts/quality_gate.py` contain **no documentation-freshness
check**.

## 2. Scope — what a mechanical check can and cannot do

| Drift class | Example | Mechanically catchable? |
|---|---|---|
| **Countable** | "8 principles" when there are 9; "19 skills" when there are 21 | **Yes** — cheap, reliable |
| **Named-list** | a directory tree omitting a real command | Partially (count + name set) |
| **Semantic** | a slide describing a command's behavior that's now wrong | **No** — still needs `/review` |

The check is a **high-value floor, not a ceiling.** It must be advertised as such so it
does not create false confidence that "docs are verified."

## 3. Proposed mechanism

Two pieces, deliberately simple:

**(a) A single source of truth for counts — `scripts/framework_counts.py`.**
Computes counts from the filesystem so there is one authoritative answer:
- `agents` = `.claude/agents/*.md`
- `commands` = `.claude/commands/*.md`
- `skills` = `.claude/skills/*/SKILL.md`
- `rules` = `.claude/rules/*.md`
- `hooks` = distinct hook command entries in `.claude/settings.json`
- `principles` = enumerated items under CLAUDE.md "Non-Negotiable Principles"

**(b) A checker — `scripts/check_doc_sync.py`** that reads the **annotated** count claims
in the doc artifacts and compares them to (a), reporting any mismatch.

### Annotation, not regex-over-prose (the key design decision)

A naive "grep every number near the word *commands*" approach is brittle and would
**false-positive on intentional subset counts** — e.g. the framework deck's
"**16 Core Commands**" (a curated showcase; the true total is 24, stated separately).
This session is the proof: the only robust signal is an *authoritative* count, not every
number in prose.

So: authoritative count claims get a machine-readable marker; the checker validates
**only marked numbers** and ignores all prose.

```html
<!-- HTML decks: only this number is checked; "16 Core Commands" in a heading is ignored -->
There are <span data-fw-count="skills">21</span> on-demand skills.
```

```markdown
<!-- Markdown specs: an HTML comment marker on the line -->
- Skills: 21 on-demand skills <!-- fw-count: skills -->
```

Unmarked numbers are never checked — intentional subsets ("16 core", "top 5") stay legal.
Coverage is opt-in per number, which keeps false positives at zero at the cost of needing
the markers added once.

## 4. Where it runs

Recommend an **advisory check inside `scripts/quality_gate.py`**, mirroring the existing
**BUILD_STATUS freshness** check: it reports drift and logs to `quality_gate_log.jsonl`,
but **does not fail the gate** and **never blocks a commit**. A `--skip-doc-sync` flag and
a `--fix` mode (auto-rewrites marked numbers to the computed value) round it out.

Rationale for advisory-not-blocking: a blocking check on documentation would couple code
commits to deck edits and invite `--skip` reflexes; the goal is a reliable *signal*, not a
gate. (If experience shows drift still ships, escalating to blocking is a later, separate
decision.)

## 5. The counting-rule ambiguities this proposal must pin down

The session surfaced genuine definitional forks the check **must** resolve, or it will
itself produce wrong answers:

1. **Committed vs working-tree.** `orchestrating-lean-dispatch` exists in the working tree
   but is untracked → `ls` says 21, a fresh clone gets 20. **Proposed rule: count tracked
   (committed) files only**, since that is what a user receives. (Developer chose to ship
   the skill, so post-commit this resolves to 21.)
2. **Framework artifact vs Claude Code built-in.** `deep-research` is a Claude Code
   built-in, *not* a `.claude/skills/` entry. **Proposed rule: count only framework
   artifacts**; built-ins are documented but excluded from `.claude/` counts.
3. **Phantom references.** `severity-calibration` is referenced by `autonomous_workflow.md`
   but has no SKILL.md. The checker should additionally **flag count markers and named
   references to artifacts that do not exist** (a name-set check), catching phantoms.

## 6. Artifacts the check should cover

`docs/how-to-use-presentation.html`, `docs/diviner-dojo-framework-presentation.html`,
`docs/FRAMEWORK_SPECIFICATION.md` — the three artifacts already enumerated in the
`syncing-framework-docs` skill's sync-point table. The check **complements** that skill
(mechanizing its countable rows); it does not replace it (semantic rows still need a human).

## 7. Honest limitations

- **Markers must be added once** to existing docs (a one-time pass) or coverage is empty.
- **Semantic accuracy is out of scope** — `/review` remains the only check for "is this
  description still true."
- **`settings.json` hook counting** is interpretation-dependent (the deck counts 9 by
  including `context-statusline`; one could argue 8). The proposal must freeze one
  definition in `framework_counts.py` and document it.
- This adds maintenance surface (two scripts + markers); justified only because count-drift
  is recurrent and cheap to catch.

## 8. Evolution path (required before any of this is built)

1. **Steward gate** — evaluate against PHILOSOPHY.md (Principle #2 automatic-enforcement;
   least-complex-intervention #8 — is an advisory quality-gate check the least-complex fix
   vs a full hook?). Verdict: APPROVE / REVISE / DEFER / DECLINE.
2. **Developer approval** (Principle #7).
3. **`/plan` → `/build_module`** for the two scripts (new files under `scripts/` → full
   workflow), then **`/review`**.
4. **ADR** capturing the decision (framework-scope) + **doc sync** of the new check into
   `HOOKS.md` / quality-gate docs and the `syncing-framework-docs` skill.

---

*Prepared by the facilitator as a framework-evolution observation. Not self-applied:
modifying enforcement surfaces is a developer/Steward action, never an agent action off
its own proposal (Prime Objective — human-mediated enforcement).*
