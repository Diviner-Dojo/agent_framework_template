# AI-Native Agentic Development Framework

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)

A framework for Claude Code that keeps two things true as an AI agent writes
your codebase: **the reasoning survives**, and **you still understand your own
system**.

## What it is for

Frontier models can now build a great deal, quickly. That creates a problem the
speed itself cannot solve: the reasoning behind a change lives in a context
window that ends, and the developer's grasp of their own codebase quietly falls
behind the code.

This framework is a small amount of machinery aimed at exactly those two
problems. It does not tell the model how to think — v4 deleted all of that,
because current models do it better unprompted (see ADR-0029). What remains is
what no model capability replaces:

- **Reasoning is captured automatically**, by scripts and hooks rather than by
  asking the model to remember.
- **Decisions become immutable ADRs**, superseded but never deleted.
- **Code is reviewed by a context that did not write it.**
- **You get taught your own codebase**, at a depth chosen by how risky the
  change actually is — and you can always decline.

## Install

```bash
pip install -r requirements.txt
python scripts/init_db.py
pytest tests/ -q
```

## Use

| Command | What it does |
|---|---|
| `/teach` | Brief you on a change, scaled to its risk |
| `/review` | Independent multi-agent review, captured |
| `/decide` | Write an ADR with the reasoning behind it |
| `/remember` | Promote a lesson into curated memory |
| `/status` | Working tree, current risk, briefing ledger |
| `/retro` | Look back and propose changes |
| `/ship` | Gate, version, changelog, tag |
| `/apply-framework` | Put this framework on another project |

## The education gate

This is the part most worth explaining, because it is easy to build badly.

Every change is scored from its diff by `scripts/assess_risk.py` — new source
files, security-relevant paths, schema and dependency changes, size, reach. The
score picks a depth:

- **light** — three lines: what changed, why it matters, what to watch.
- **standard** — the concept you now need, the tradeoff that was live, the
  thing most likely to bite you. One real question back.
- **deep** — the above, plus a walkthrough until you can explain it back.

The aim is never to test you. It is that when you next make a decision near
this code, you already know what you need to know.

**You can always skip.** The skip is recorded, never blocked, and there is no
score and no failure state — the ledger has no column that could grade you.
Deferred briefings show up in `/status` as information, not as a debt. A gate
that stops you shipping has failed at its purpose.

## Structure

```
.claude/
  commands/   — 8 workflow commands
  agents/     — 5 review agents, each a distinct thing to look for
  skills/     — 2 reference protocols
  hooks/      — commit gate, protected files, secret detection

docs/adr/     — decision record (immutable)
docs/reviews/ — review reports
discussions/  — Layer 1: raw captured reasoning
metrics/      — Layer 2: SQLite index
memory/       — Layer 3: curated, human-approved knowledge
scripts/      — capture pipeline, quality gate, risk scoring
src/ tests/   — your code
```

## Design

The framework is built on one distinction, and it is worth internalizing before
extending anything:

**Scaffolding** compensates for what a model cannot do. It is correct when
written and decays as models improve, eventually costing more in tokens and
instruction conflict than it returns.

**Governance** constrains what may happen to the human. It does not decay — it
matters *more* as capability grows, because a faster agent outruns its owner's
understanding faster.

Before adding anything here, ask: *does this exist because the model was weak?*
If yes, it will expire. Write it so it is easy to delete.

`PHILOSOPHY.md` covers why. `FRAMEWORK.md` covers what. `ADR-0029` covers what
v4 removed from v3 and the arguments against doing so.

## License

Apache 2.0. Patterns adopted from external projects are attributed in
`memory/lessons/adoption-log.md`.
