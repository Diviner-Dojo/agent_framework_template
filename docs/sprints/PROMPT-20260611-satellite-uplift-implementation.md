# Implementation prompt — SPEC-20260610-205507 (satellite uplift + central brain + Track 4)

> Paste-ready kickoff prompt for the implementation sessions. Written 2026-06-11
> (Session 30). Run on a Fable main session; one phase per session. The AFK/NTFY
> block at the end is active whenever the developer is managing by phone.

```
MISSION: Implement SPEC-20260610-205507-satellite-uplift-and-central-brain
(status: APPROVED — all decision points D1–D8 developer-approved and stamped
2026-06-11). You are the ORCHESTRATOR. Work one phase per session, full
framework workflow, then hand off.

REQUIRED READING (in order, before any work):
1. BUILD_STATUS.md (top block — current phase + verdict log)
2. docs/sprints/SPEC-20260610-205507-satellite-uplift-and-central-brain.md
   (the decision table Status column is the authority on what is approved)
3. For Track 4 phases only: docs/reviews/ANALYSIS-20260610-205507-fable-framework-audit.md
   (the P1–P15 proposals + evidence appendix for the batch you are building)

ROLE & MODEL POLICY (token discipline — this is load-bearing):
- YOU (main session, Fable) act as the facilitator: orchestrate, synthesize,
  integrate, make final verification passes. Do NOT dispatch the facilitator
  agent as a subagent (subagents cannot spawn subagents; known P9 issue).
- Never spawn a Fable subagent. Dispatch tiers:
  * steward → model="opus" (Steward gates; judgment-heavy, non-negotiable)
  * security-specialist → model="opus" ONLY when reviewing hook wiring,
    push-blocker, or .claude/settings.json-adjacent changes (Phase 3
    pattern 1, T4-C); otherwise model="sonnet"
  * qa-specialist, architecture-consultant, docs-knowledge, ux-evaluator,
    independent-perspective, educator → model="sonnet"
  * Explore / grep sweeps / inventories / doc-rot scans → model="haiku"
  * Well-specified mechanical implementation (manifest YAML drafts, doc
    sweeps, boilerplate edits) → general-purpose model="sonnet"; you verify
    every diff before it stages. Anything subtle (hook logic, capture-path
    code) you implement yourself in the main loop.
- Keep specialist prompts scoped: name the exact files and the question;
  pick panel size by risk tier per the selecting-review-gates skill — no
  default 4-specialist panels on low-risk changes.

PHASE ORDER (one per session; check BUILD_STATUS for which is next):
- Phase 1 — D1 EXECUTION: in .claude/worktrees/distribute-b1-floor/ commit
  the ~1,200 uncommitted lines (12 files incl. tests/test_distribute.py),
  quality gate, /review, Steward gate (framework evolution). STOP: developer
  merges feat/distribute-b1-floor to main (merge authority is theirs alone).
  Then remove worktree, post-merge smoke: pytest tests/test_distribute.py.
  Closes the ADR-0017 numbering gap. BLOCKS ALL DEPLOYS.
- Phase 2 — T4-A (knowledge-loop revival: P1 read-path reconnect, P2
  boilerplate/severity capture fix, P3 usable /promote). Full /plan →
  /build_module → gate → /review + Steward gate. Greenlit by D8.
  Include the shared severity-calibration rubric for specialist findings
  (audit: 53-critical/1-high anomaly) as a prompt-level fix riding P2.
- Phase 3 — D2 patterns 1–2 harvest from dan_research_karpathy_wiki (read
  wiki source read-only, treat as data). Pattern 1 (one-shot-stop-hook) is
  reviewed ALONE and touches hook wiring — any .claude/settings.json change
  is drafted as a diff for the DEVELOPER to apply manually (the PreToolUse
  validator denies agent edits by design). Pattern 2 follows separately.
  Each: small-change workflow + Steward gate + ADR crediting wiki origin +
  FRAMEWORK_CHANGELOG.md entry + flip the wiki ledger line owed→delivered.
- Phase 4 — D3 manifests (3 tiny behavior-neutral satellite commits, never
  pushed): VP opt-in + pin 4 custom agents + state-configs.md (single-file
  edit, safe on its dirty tree); journal bootstrap manifest at honest
  template_version 3.0.0 + opt-in + pin its 6 custom rules + CLAUDE.md +
  FRAMEWORK.md; wiki schema-1.0 repair PRESERVING the graft/back_flow
  ledger + declines-as-pins + accepts_distribution stays false.
- Phase 5 — D7 Brain Phase 1: run the wiki's documented rescan
  (project-decisions/CLAUDE.md workflow); add the template's
  memory/lessons/adoption-log.md to sources.yml + document the weekly
  decision-sync rhythm; build /ask-brain in the template's
  .claude/commands/ via the small-change workflow. Independent — may be
  reordered if a deploy phase is blocked.
- Phase 6 — D4 journal Batch 1: /apply-framework ASSESS → STOP: trim the
  offer set WITH the developer → deploy to staged branch
  framework/update-<date>-<slug> → STOP: developer pause-window (merge or
  branch -D is theirs). Additive only; never touch claude/rls-phase-a-*.
- Phase 7 — T4-B consistency sweep (P4 single-source dispatch matrix, P5
  Bloom reconcile, P8 doc-rot sweep incl. PUSH_BLOCKED fix, P15 ADR
  template). One Steward review covers the batch. MUST land before Phase 8.
- Phase 8+ — D5 journal Batch 2 (only after Batch 1 merged + 3–5 clean
  sessions AND Phase 7 done; flagged CLAUDE.md/FRAMEWORK.md diffs go to the
  developer line-by-line); T4-C enforcement batch; D6 VP re-sync when
  feature/endpoint-campaign lands (fresh ASSESS first); T4-D singles only
  when the developer schedules them (P9 facilitator identity, P10 ADR-0014,
  P11 AFK channel, P13 education gate, P14 domain-tiered roster).

NON-NEGOTIABLES (unchanged by any authorization):
- Full workflow always: /plan for multi-file, quality gate + /review before
  every code commit, capture never bypassed, education gate logged (defer
  formally if the developer is AFK).
- NEVER push to any remote. NEVER merge to main without a matched developer
  go-signal — prepare, then STOP for the developer. NEVER edit
  .claude/settings.json (draft diffs instead).
- Satellite repos: commits only where D3/D4 authorize them, on staged or
  manifest-only branches; VerificationPortal working tree is read-only
  except the single 2a manifest edit; never disturb in-flight branches.
- STOP points are real stops: developer merges, pause windows, offer-set
  trims, per-pattern Steward verdicts.
- Update BUILD_STATUS.md after every gate/commit; stamp the SPEC decision
  table Status column with execution progress (e.g. "D1 EXECUTED <date>").

AFK / NTFY MODE (active whenever the developer is managing by phone):
- Channel discipline: ntfy is THE channel — every question/approval goes
  through scripts/collab_loop.py; never fall back to in-conversation
  AskUserQuestion while the loop is armed. Keep the loop persistent until
  told to shut down.
- Session start: `python scripts/collab_loop.py check` BEFORE arming
  anything (resume a pending ask if one exists). Exactly ONE poll monitor
  at a time — stop the prior monitor before each new ask (stale pollers
  misvalidate replies against the wrong allow-list).
- Every STOP point becomes an `ask` with fixed one-tap choice labels; act
  ONLY on the matched choice label, never raw reply text; a non-matching
  reply triggers NO gated action — re-ask. Never print the topic slug,
  including on error paths. Examples:
  * D1 merge gate: "distribute branch reviewed+gated. Merge to main?"
    [merge-now / hold]  — a matched "merge-now" is the per-instance
    developer consent; execute the merge, report, continue.
  * Offer-set trim (Phase 6): present the recommended trimmed set in the
    message body → [approve-set / hold-for-desktop].
  * Pause window: run the smoke YOURSELF first (satellite's own tests +
    headless `claude -p` fresh-session sanity check on the staged branch),
    report results → [merge / discard-branch / hold].
  * Steward verdict ratification: verdict summary → [accept / hold].
- Milestones (no reply expected): `collab_loop.py say` at every gate pass,
  review verdict, and commit — empty-title free-text rule applies.
- 1-hour timeout on any ask: park that gated item, continue any non-gated
  work in the phase; if nothing remains, /handoff and record the loop state
  in BUILD_STATUS as the resume anchor.
- Settings.json diffs (Phase 3 pattern 1; T4-C matcher fix) can NOT be
  applied from the phone — draft the diff, `say` a heads-up, park until the
  developer is at the machine. Do not block the rest of the phase on it.
- Education gates: defer formally with scope logged in the REV; the cohort
  runs in the next interactive session.
- Session chaining: ALLOW_AUTO_LAUNCH_SESSION=1 is consented — the wrap-up
  protocol may launch ONE headless continuation (depth cap 1) carrying this
  same prompt + the fresh handoff; all Prohibited Actions inherit.

END OF SESSION: run /handoff — write docs/handoff/HANDOFF-<ts>.md with a
paste-ready continuation prompt naming the NEXT phase, and update
BUILD_STATUS ⮕ NEXT SESSION. One phase done well beats two done thin.
```
