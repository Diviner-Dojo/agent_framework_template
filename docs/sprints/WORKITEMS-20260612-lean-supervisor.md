# Work items — lean supervisor + token efficiency (developer-approved 2026-06-12)

> Queued from the Session-32/33 interactive review of the overnight runs. Execute at the
> NEXT QUIET BOUNDARY (current supervisor chain stopped or between runs) — NOT while a
> headless run is mid-flight (working-tree contention). Items 1–2 precede any relaunch;
> 3–4 ride along. Then fold all four lessons into
> `.claude/skills/orchestrating-lean-dispatch/SKILL.md` (developer approved the fold).

## 1. BUILD_STATUS archival (biggest recurring win — do FIRST)
Every session (headless or interactive) reads BUILD_STATUS; it is ~35k tokens of session
history. Move everything below the top ~3 session blocks into
`memory/archive/build-status/BUILD_STATUS-archive-<date>.md` (allowed write target),
keep a pointer line. Live file target: a few hundred lines. Docs-only change.
Recurring saving: tens of k tokens × every future session.

## 2. session_supervisor.py resilience + tiering (small-change workflow: gate + /review)
- (a) **Sleep-until-reset**: detect the usage-limit kill (output contains
  "hit your session limit" + "resets <time>"), parse the reset time, sleep until then
  + 5 min, RETRY the same session instead of stopping. Cap retries (e.g. 3).
  Evidence: 2× overnight/morning chains died at 17:47 and 07:46 on this; each kill
  wasted a full session startup tax.
- (b) **Turn-budget awareness**: pass the remaining-turn count into the injected prompt
  ("you have N turns; checkpoint + emit SUPERVISOR_ROLL before N-10") so sessions
  never run silent into the cap (the 80-turn clip on 2026-06-12 07:09 produced a
  no-sentinel stop).
- (c) **Per-run model tiering**: support a `MODEL: sonnet|fable` line in the rolling
  handoff's NEXT RUN header; supervisor passes `--model` to `claude -p`. Mechanical
  phases (e.g. Phase 4 manifests) run sonnet; judgment-dense phases (Phase 6 deploy)
  run top-tier. Quality floor unchanged: deterministic quality gate + specialist
  reviews + opus Steward run regardless of the orchestrator tier.

## 3. Script the per-phase ceremony (rung 1 of the dispatch ladder)
One-time scripts to replace recurring model turns: REV-report scaffolder (template +
frontmatter from discussion state), fold-bookkeeping helper, single-command
"synthesis+yield+close" wrapper. Each currently costs model turns in EVERY phase.

## 4. Fold lessons 1–3 + the fewer-longer-sessions/cache rationale into
`orchestrating-lean-dispatch/SKILL.md` (one fresh `claude -p` per 50 turns re-reads
everything cold; one 200-turn session reuses its prompt cache — prefer long sessions,
protect them from limit-kills). Skill edit = framework evolution follow-up; developer
approval ALREADY RECORDED 2026-06-12 (this file is the record); Steward ratifies as-built.

## Relaunch decision (recorded)
Developer asked whether to stop the in-flight Run-1 session and relaunch under this
approach — decision: NO; let Run 1 finish (startup tax already paid, fresh quota),
apply items 1–2 at the next chain stop, then relaunch remaining runs tiered per 2(c).
