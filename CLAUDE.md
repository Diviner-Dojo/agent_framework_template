# Project Constitution

**Framework**: AI-Native Agentic Development Framework v4.0
**Stack**: Python 3.11+, pytest, ruff · **Coverage target**: ≥80%

## Why this file is short

v3 of this framework was ~9,000 lines of instruction written for models that
needed to be told how to think. Opus 5 does not. What remains here is the part
no model capability replaces: **what must persist after the context window
ends, and what a human must decide.**

Before adding a rule here, check whether the model already does it. Usually it
does, and the rule will only cost tokens arbitrating against instincts that
were already correct. See ADR-0029.

## Prime Objective

The framework serves its contributors and users. Its reasoning, memory, and
evolution must never accumulate value at their expense.

A design **refuses extraction** iff: every contributor retains attribution; no
one performs labor whose benefit accrues primarily to a third party without
consent; and the framework does not absorb value from derivatives without
per-instance human assent.

Enforcement is **human-mediated** at every gate. This objective is limited by
the model provider — users needing stronger guarantees should run on
infrastructure they control.

## Principles

1. **Reasoning is the primary artifact.** Code is output. Every significant
   decision traces to the discussion that produced it.
2. **Capture is automatic.** Enforced by scripts and hooks, not by instruction.
   A decision that exists only in a context window did not happen.
3. **The generator is never the sole evaluator.** Independent review means a
   *separate context* that did not see the reasoning behind the code — an
   information property, not a personality.
4. **ADRs are never deleted.** Superseded, with a reference to the replacement.
5. **Understanding is offered before merge, never withheld.** See below.
6. **Curated memory needs human approval.** Nothing reaches `memory/`
   automatically.

## Understanding before merge

The developer's grasp of their own codebase is what this framework protects.
It is not a test or a barrier — the goal is that you can make the *next*
decision well.

`scripts/assess_risk.py` scores each change from the diff and picks a depth:

| Depth | What you get |
|---|---|
| `light` | Three lines: what changed, why it matters, what to watch. |
| `standard` | The concept you now need, the tradeoff that was live, the thing most likely to bite you. One question back. |
| `deep` | The above, plus a walkthrough and a conversation until it's yours. |

**You can always say "skip."** The skip is recorded, never blocked. Deferred
briefings accumulate in the ledger and surface in `/status` — honest, not
punitive. A framework that stops you from shipping has failed at its purpose.

Run `/teach` any time, on anything, whether or not a gate fired.

## Workflow

Match ceremony to stakes. There is no fixed ladder.

- **Anything touching `src/`** gets `/review` before commit — Principle #3.
- **Architectural or hard-to-reverse decisions** get `/decide` (ADR + captured
  reasoning) before implementation, not after.
- **Everything else**: build it, run the quality gate, commit.

Deliver what was asked, at the scope intended. Make routine judgment calls
yourself; check in when different readings lead to materially different work.
If the request seems mistaken, say so in a sentence and continue as asked.

## Gates

`python scripts/quality_gate.py` — formatting, lint, tests, coverage ≥80%,
ADR completeness, review existence. `--fix` remediates. Runs on pre-commit.

Autonomous sessions run the full workflow without asking per step. They never
skip `/review`, never skip capture, never push, and never auto-merge. Pushing
always needs explicit per-instance confirmation.

## Delegation

Delegate to a subagent only for genuinely independent, sizeable tracks of work
— a wide multi-file investigation, or a review that must not see the
generation reasoning. Do not delegate what you can finish in a handful of tool
calls, and do not use subagents to double-check your own work. Prefer one
agent over several.

Five agents, each a distinct thing to *look for* rather than a persona:
`code-reviewer`, `security-reviewer`, `architecture-reviewer`, `contrarian`,
`educator`.

## Layout

```
.claude/{commands,agents,skills,hooks}/
docs/adr/        — decision record (immutable; superseded, never deleted)
docs/reviews/    — review reports
discussions/     — Layer 1: raw captured reasoning (sealed on close)
metrics/         — Layer 2: evaluation.db + JSONL trends
memory/          — Layer 3: curated, human-approved knowledge
scripts/         — capture pipeline, quality gate, risk scoring
assertion_store/ + mcp_server/ — sourced-assertion memory (ADR-0014)
src/ tests/      — application + test suite
```

**IDs**: `DISC-YYYYMMDD-HHMMSS-slug` · `ADR-NNNN` · `REV-YYYYMMDD-HHMMSS`
**Artifacts**: YAML frontmatter + Markdown body.

## Known limitations

- The pre-commit hook cannot bypass the review-existence check from `git commit`
  arguments.
- The MCP server requires thread-local SQLite connections; `Substrate._get_conn()`
  is authoritative. Regression test: `tests/test_mcp_server.py::TestThreadLocalIsolation`.
- `EMBEDDING_DIM = 384` is baked into the `assertion_vecs` schema. Changing the
  embedding model requires a migration and full re-embedding (ADR-0014).

## Pointers

`PHILOSOPHY.md` — why the framework works the way it does
`docs/adr/ADR-0029-*` — what v4 deleted from v3, and why
`docs/CAPTURE_PIPELINE.md` — scripts, schema, cost model
