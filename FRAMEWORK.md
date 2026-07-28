# AI-Native Agentic Development Framework v4.0

> Universal framework principles — applies to any project using the framework.
> Project configuration lives in `CLAUDE.md`. Values live in `PHILOSOPHY.md`.
> The v3→v4 rationale lives in ADR-0029.

## The distinction this framework is built on

Everything here is either **scaffolding** or **governance**.

**Scaffolding** compensates for what a model cannot do. Reasoning procedures,
mandated verification steps, context management, orchestration protocols. It is
correct when written and decays as models improve — eventually costing more in
tokens and instruction conflict than it returns.

**Governance** constrains what may happen to the human. Capture, immutable
decision history, human approval for durable memory, independent evaluation,
understanding before merge. It does not decay. It becomes more necessary as
capability grows, because a faster agent can outrun its owner's understanding
faster.

v4 deleted the scaffolding and kept the governance. Apply the same test to
anything you add: *does this exist because the model was weak?*

## Principles

1. **Reasoning is the primary artifact.** Code is output. Every significant
   decision traces to the discussion that produced it.
2. **Capture is automatic.** Enforced by scripts and hooks, never by asking the
   model to remember. A decision that exists only in a context window did not
   happen.
3. **The generator is never the sole evaluator.** Independent review means a
   separate context that never saw the generation reasoning — an information
   property, not a personality.
4. **ADRs are never deleted.** Superseded, with a pointer to the replacement.
5. **Understanding is offered before merge, never withheld.**
6. **Curated memory needs human approval.**

## Where guarantees live

A guarantee written in prose is a request. A guarantee written in code is a
guarantee. Anything load-bearing belongs in `scripts/` or `.claude/hooks/`.

| Mechanism | Guarantees |
|---|---|
| `scripts/create_discussion.py`, `write_event.py`, `close_discussion.py` | Reasoning is recorded and sealed |
| `scripts/quality_gate.py` | Format, lint, tests, coverage, ADR completeness, review existence |
| `scripts/assess_risk.py` | Briefing depth is chosen by the diff, not by mood |
| `scripts/briefing.py` | Teaching and deferrals are both recorded |
| `.claude/hooks/pre-commit-gate.sh` | The gate cannot be forgotten |
| `.claude/hooks/validate_tool_use.py` | Protected files; secret detection |
| `.claude/hooks/pre-push-main-blocker.sh` | No accidental push to main |

The markdown in `.claude/commands/` and `.claude/agents/` describes intent and
sequencing. It does not enforce anything, and should not pretend to.

## Capture stack

- **Layer 1 — `discussions/`** — raw events and transcripts, sealed on close.
  Canonical. Everything downstream is a vehicle for engaging with this, never a
  replacement for it.
- **Layer 2 — `metrics/evaluation.db`** — relational index for querying.
- **Layer 3 — `memory/`** — curated, human-approved. Entry requires `/remember`.

Derived artifacts carry a pointer back to their source: ADRs cite
`discussion_id` (the quality gate enforces this), reviews cite findings,
promoted memory cites `sources`. A claim whose provenance cannot be traced has
lost the property that made it trustworthy — repair the pointer or withhold
the promotion.

## Understanding before merge

`scripts/assess_risk.py` scores each diff and selects a depth: `light`,
`standard`, or `deep`. `/teach` delivers it, aimed at the **next decision** the
developer will face rather than at comprehension for its own sake.

The developer may always decline. The decline is recorded, never blocked, and
carries no score or failure state — the ledger has no column that could grade a
person. Deferred briefings surface in `/status` as information.

A gate that stops someone from shipping has failed at this framework's purpose.

## Agents

Five, each defined by a distinct thing to look for rather than by a persona.
The value is the independent context, not the character.

| Agent | Looks for |
|---|---|
| `code-reviewer` | correctness, edge cases, coverage, performance |
| `security-reviewer` | trust boundaries, authz, injection, secrets |
| `architecture-reviewer` | boundaries, coupling, drift, premature structure |
| `contrarian` | the unconsidered alternative, the buried assumption |
| `educator` | the load-bearing idea, taught for the next decision |

Delegate for genuinely independent, sizeable work. Do not delegate what you can
finish in a handful of tool calls, and do not use subagents to double-check
your own work.

## Commands

| Command | Purpose |
|---|---|
| `/teach` | Brief the developer, risk-scaled and skippable |
| `/review` | Independent evaluation, captured |
| `/decide` | ADR plus the reasoning behind it |
| `/remember` | Promote to curated memory (human gate) |
| `/status` | Tree, current risk, briefing ledger |
| `/retro` | Look back; produce proposals, never self-applied edits |
| `/ship` | Gate, version, changelog, tag |
| `/apply-framework` | Assess and deploy onto another project |

## Framework evolution

Changing a rule, a gate, or the framework's own definition is a **developer
action**. An agent may observe, gather evidence, and propose — it may not edit
a classifier surface or a governance rule off its own proposal. That would be
self-modification, and the human gate is the point.

## Conventions

**IDs**: `DISC-YYYYMMDD-HHMMSS-slug` · `ADR-NNNN` · `REV-YYYYMMDD-HHMMSS`
**Artifacts**: YAML frontmatter + Markdown body.
