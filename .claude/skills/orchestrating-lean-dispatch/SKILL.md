---
name: orchestrating-lean-dispatch
description: Get Fable-level quality while spending Fable tokens ONLY on orchestration, judgment, synthesis, and verification. Use whenever a Fable (or top-tier) main session runs a multi-step workflow — especially autonomous/overnight sessions — to push every delegable token down to cheaper models or deterministic CLI tools. Developer-approved 2026-06-11 (Principle #6); Steward as-built APPROVE 0.86 (Run 0, 2026-06-12). Session-chain economics fold approved 2026-06-12 (WORKITEMS-20260612-lean-supervisor); Steward ratifies as-built.
---

# Orchestrating Lean Dispatch

**Goal: Fable-level quality, minimum Fable tokens.** The top-tier model's value is judgment —
decomposition, risk calls, synthesis, final verification. Everything else is delegable. Treat the
main-loop context window as the scarcest resource in the system.

## The dispatch ladder (cheapest tool that preserves quality wins)

> The tier-to-task bindings below mirror the canonical model-tiering dispatch policy
> (SPEC-20260610-205507). That SPEC is the single source of truth — if tiers shift, update it
> first; this skill defers to it rather than competing with it.

1. **Deterministic CLI / script (zero model tokens).** If a step is mechanical and repeatable —
   capture events, gates, transcript generation, git mechanics, log parsing, conflict unions —
   it must be a script, not a model turn. If the script doesn't exist and the task will recur,
   **Fable writes the script once** (small, tested), then every future run pays zero tokens.
   This is least-complex intervention first (`PHILOSOPHY.md`, *Growth has a brake*) applied to token spend.
2. **haiku** — search, inventories, grep sweeps, doc-rot scans, "find all X" fan-outs.
3. **sonnet** — specialist reviews (qa/arch/security non-enforcement/indep/docs/ux), well-specified
   mechanical implementation (manifest YAML, doc sweeps, boilerplate edits, test scaffolds).
4. **opus** — ONLY steward gates and security review of hook-wiring / push-blocker /
   settings.json-adjacent changes. Non-negotiable judgment seats.
5. **Fable (main loop)** — orchestration, risk-tier calls, design forks, synthesis events,
   REV reports, **verifying every cheap-model diff before it stages**, and subtle implementation
   (hook logic, capture-path code, consent/safety code) that cheaper tiers get wrong.
   **Never spawn a Fable subagent. Never dispatch the facilitator as a subagent** — in a Fable
   session the main loop *is* the facilitator-equivalent per the tiering policy, so orchestration
   stays in-loop (this is consistent with, not a contradiction of, the facilitator-as-sole-orchestrator rule).

## The generation/verification asymmetry (the core trick)

Verifying a diff costs a fraction of generating it. Default shape: **sonnet generates → Fable
reads the diff and judges**. Quality stays at the verifier's level as long as the verifier is
strong and the task was scoped tightly enough that a wrong diff is *visible* in the diff.
Corollary: if Fable can't verify it by inspection (subtle state, security boundary, consent
logic), Fable implements it directly — delegation there is false economy.

## Scoping rules for every dispatch

- Name the **exact files** (worktree-absolute paths if a worktree is involved — agents reading
  main-checkout paths get stale files) and the **exact question**. No "review this area".
- Panel size by risk tier (selecting-review-gates) — no default 4-specialist panels on low risk.
- Demand **compact structured returns** (verdict / confidence / findings list), never transcripts.
  The orchestrator captures the structured return via `write_event` — that captured return **is**
  the reasoning artifact (Principles #1/#2); only the surrounding conversational prose is throwaway.
- One dispatch, one concern. A specialist asked two questions answers both badly.

## Main-loop context hygiene (protect the window)

- **Grep before Read; Read line-ranges, never whole large files.** Digest tool output into
  BUILD_STATUS as dated observations — never paste logs/dumps.
- Keep a **stable prompt prefix** (BUILD_STATUS top block) for cache hits; append, don't rewrite.
- **One phase per session**, then `/handoff` with a paste-ready prompt; chain via the external
  supervisor (`scripts/session_supervisor.py`, rolling handoffs) — NEVER self-spawn a continuation
  from a dying session (known wedge). Fresh context beats degraded context.
- Batch independent tool calls in one message; let scripts do multi-step sequences in one call.

## Session-chain economics (folded 2026-06-12 from the overnight-chain post-mortem)

The unit of cost in a supervisor chain is not the turn — it is the **session startup tax**:
every fresh `claude -p` re-reads CLAUDE.md, rules, BUILD_STATUS, and the handoff cold, while a
long-lived session reuses its prompt cache. One 200-turn session is dramatically cheaper than
four 50-turn sessions doing the same work. Consequences:

1. **Prefer fewer, longer sessions; protect them from limit-kills.** A usage-limit kill
   ("hit your session limit · resets <time>") wastes a full startup tax AND strands mid-phase
   state. The supervisor sleeps until the advertised reset + 5 min and retries (capped) instead
   of treating it as a hard error — never burn the post-reset window by stopping the chain.
2. **Never run silently into the turn cap.** A session clipped at `--max-turns` dies with no
   sentinel and stops the chain. The supervisor injects the cap into the prompt; the session must
   checkpoint (update the handoff in place) and emit `SUPERVISOR_ROLL` ~10 turns before the cap.
3. **Tier the orchestrator per run, not per chain.** The rolling handoff's NEXT RUN header
   carries a `MODEL: sonnet|fable` line (supervisor passes `--model`). Mechanical phases
   (manifest edits, doc sweeps) run sonnet; judgment-dense phases (deploys, design forks) run
   top tier. The quality floor is unchanged either way: the deterministic quality gate,
   specialist reviews, and the opus Steward run regardless of the orchestrator tier.
   **The `MODEL:` line tiers the orchestrator only; it has no authority over the quality
   floor, which is set by command definitions the orchestrator cannot rewrite mid-chain**
   (Steward condition 2, DISC-20260613-000652 — the floor is structurally independent of
   agent-authored handoff text, and the line can only select within the bounded cost set,
   never address the review panel).
4. **Keep the session-start read-set lean.** BUILD_STATUS is read by EVERY session — keep only
   the top ~3 session blocks live and archive the rest to `memory/archive/build-status/`
   (pointer line in the live file). A bloated BUILD_STATUS (~35k tokens, 2026-06-12) exhausted a
   headless session's context before it reached its work.
5. **Script the per-phase ceremony (ladder rung 1).** REV-report scaffolding, fold bookkeeping,
   synthesis+yield+close sequences recur EVERY phase — each is a one-time script, not recurring
   model turns. If you catch yourself doing the same multi-turn ceremony a second time, write
   the script before the third (Rule of Three applied to turns).

## Known traps

- A "quick look" at a big file costs more than a haiku dispatch that returns 10 lines.
- Cheap-model output that *looks* right but wasn't diff-verified by the orchestrator is the #1
  quality leak — the whole pattern collapses without the verification pass.
- Scripts that print verbosely burn the window on success noise — scripts must print compact
  status lines (`PASS x/y`, IDs, counts), details to files.
- The PostToolUse formatter strips imports unused at edit time — add imports AFTER consumers exist.
