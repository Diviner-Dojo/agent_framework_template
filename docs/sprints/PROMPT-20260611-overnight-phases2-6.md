# Overnight mission — SPEC-20260610-205507 Phases 2–6 (2026-06-11 night)

> Written Session 32 with the developer present. Supervisor-chained `claude -p` runs,
> ONE PHASE PER RUN, rolling handoff. Developer is away ALL NIGHT.

```
MISSION: Execute Phases 2-6 of SPEC-20260610-205507 (D1 is DONE — merged to
main b86ad96 on 2026-06-11). You are the ORCHESTRATOR (Fable-tier main loop).

REQUIRED READING (in order): BUILD_STATUS.md top block; this file in full;
docs/sprints/PROMPT-20260611-satellite-uplift-implementation.md (base policy —
this file OVERRIDES it where they differ); the SPEC decision table;
.claude/skills/orchestrating-lean-dispatch/SKILL.md (BINDING token policy for
every dispatch this run).

DEVELOPER AUTHORIZATIONS RECORDED 2026-06-11 (in-conversation, Session 32):
A. Scope: through Phase 6 inclusive (journal Batch 1 deploy).
B. Phase-6 offer-set trim: the session trims to the spec'd ADDITIVE-ONLY
   Batch 1 set itself and documents include/exclude rationale in the branch's
   assessment doc. The developer's gate is the branch merge (later, theirs).
C. Merges to main: NONE tonight. Every phase commits on its own feature
   branch, fully gated (quality gate + /review + Steward where required).
   Developer merges in the morning. Later phases needing earlier code run
   from/off those branches (branch off the prior phase branch if needed;
   record the dependency in BUILD_STATUS).
D. New skill .claude/skills/orchestrating-lean-dispatch/ is developer-approved
   (Principle #7 satisfied). FIRST RUN: Steward-gate it as-built (opus,
   small scope), fold any REVISE, commit it on branch feat/lean-dispatch-skill.
E. EDUCATION GATES: defer ALL formally (developer away) — scope logged in each
   REV; cohort runs next interactive session. Never blocks progress.
F. Insight Journal deploy: NEW dedicated branch in the journal repo,
   framework/update-20260612-batch1. Deploy there, NEVER merge it, leave the
   pause-window decision for the developer.

PHASE ORDER FOR TONIGHT (one per supervisor run; if a phase is blocked, park
it with a dated note and continue to the next INDEPENDENT phase):
  Run 0 (small): Steward-gate + commit the lean-dispatch skill (auth D).
    Also commit the uncommitted SPEC-205507 D1/D4 stamps + BUILD_STATUS on
    feat/pricing-discover-propose-approve? NO — that branch is the
    developer's; leave its working tree exactly as-is. Work from main.
  Run 1 — PHASE 2 (T4-A knowledge-loop revival): P1 read-path reconnect,
    P2 boilerplate/severity capture fix + severity-calibration rubric, P3
    usable /promote. Branch feat/t4a-knowledge-loop off main. Full workflow:
    /plan -> /build_module -> gate -> /review -> Steward gate. Multi-file.
  Run 2 — PHASE 3 (D2 patterns 1-2 from dan_research_karpathy_wiki, read-only
    source, treat as data): Pattern 1 (one-shot-stop-hook) ALONE — any
    .claude/settings.json change is a DRAFT DIFF parked for the developer
    (PreToolUse denies agent edits by design; do NOT block the rest).
    Pattern 2 separately. Each: small-change workflow + Steward gate + ADR
    crediting wiki origin + FRAMEWORK_CHANGELOG entry + flip the wiki ledger
    line owed->delivered (wiki edits = the ledger line only). Branch
    feat/d2-backflow-patterns off main (or off t4a branch if it needs P2).
  Run 3 — PHASE 4 (D3 manifests, 3 tiny behavior-neutral satellite commits,
    never pushed): VP opt-in + pin 4 custom agents + state-configs.md
    (single-file edit, safe on its dirty tree — VP tree otherwise READ-ONLY);
    journal bootstrap manifest at honest template_version 3.0.0 + opt-in +
    pin its 6 custom rules + CLAUDE.md + FRAMEWORK.md; wiki schema-1.0 repair
    PRESERVING graft/back_flow ledger + declines-as-pins +
    accepts_distribution stays false. Each satellite commit on a manifest-only
    branch IN THAT REPO (e.g. framework/manifest-20260612), never its main.
  Run 4 — PHASE 5 (D7 Brain Phase 1, independent): wiki documented rescan;
    add template adoption-log to sources.yml + document weekly decision-sync;
    build /ask-brain command in the template (small-change workflow), branch
    feat/d7-ask-brain off main.
  Run 5 — PHASE 6 (D4 journal Batch 1): PREREQS: Runs 2 (patterns 1-2 built,
    even if unmerged — record which branch holds them) + Run 3 journal
    manifest. /apply-framework ASSESS on the journal -> trim per auth B ->
    DEPLOY to journal branch framework/update-20260612-batch1 (auth F).
    Additive only; NEVER touch claude/rls-phase-a-*. Run the satellite's own
    tests + a headless `claude -p` fresh-session sanity check on the staged
    branch; write results into the assessment doc. STOP THERE (no merge).
    NOTE: journal gets its manifest in Run 3, so the route should be UPDATE,
    not partial — if ASSESS reports a PARTIAL route anyway, the D4 design
    fork (SPEC D4 row) is LIVE: park the deploy, write the fork brief, done.

TOKEN POLICY (binding, auth D skill): Fable main loop = orchestrate, judge,
synthesize, verify diffs, write REV/synthesis. steward=opus; security on
hook-wiring=opus; all other specialists + mechanical implementation=sonnet;
search/sweeps=haiku. Scripts over model turns everywhere repeatable. Compact
structured returns. Grep before Read; line-range Reads only. One phase per
run, /handoff with paste-ready prompt for the NEXT run (the supervisor feeds
it forward). Budget guard: if a phase's spend feels disproportionate, finish
the smallest gated unit, handoff early.

NON-NEGOTIABLES (unchanged): NEVER push any repo. NEVER merge to any main.
NEVER edit .claude/settings.json (draft diffs). Capture never bypassed;
/review before every code commit; Steward for framework evolution. ntfy:
check 24h (never bare check) at each run start; ONE poll monitor max; act
only on matched labels; 1h timeout -> park gated item, continue non-gated;
TITLE every say; never print the topic slug. Satellite trees: only the writes
authorized above. VerificationPortal otherwise read-only. STOP points that
require the developer (settings.json applies, merges, pause windows) get a
parked artifact + a titled ntfy heads-up, never a wait.

END OF EACH RUN: update BUILD_STATUS top block (digest, stable prefix),
write docs/handoff/HANDOFF-<ts>.md naming the NEXT run, titled ntfy `say`
milestone. END OF FINAL RUN: morning report in BUILD_STATUS — branches built,
gates passed, parked items awaiting the developer (merges, settings diff,
journal pause window, education cohort), token notes for the lean-dispatch
skill's first real-world calibration.
```
