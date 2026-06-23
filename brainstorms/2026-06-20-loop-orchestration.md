# Grill: Goal-Driven Loop Orchestration (hub capability)

> Status: COMPLETE (Q1–Q22 resolved — full design settled)
> Started: 2026-06-20 · Last updated: 2026-06-20
> Next: fold into a sharp spec → run full `/deliberate` (steward in the room, agent-def change) → likely an ADR.

## Highlights
- Designing a goal-driven loop-orchestration capability for the framework, at the HUB level (propagates to Insight Journal, VerificationPortal, Howie via /apply-framework).
- Grounded in the 2026 "loop engineering" landscape: Berman Loop Library, Ralph loop, Claude Code `/goal`, anatomy = trigger → action → verify → stop.
- Core insight: the framework already owns ~80% of the primitives (`/loop`, Workflow tool, quality_gate as deterministic verify, maker/checker = Principle #4, session_supervisor ≈ Ralph). The missing piece is an explicit GOAL + TERMINATION contract and a facilitator that iterates build→verify→refine until the contract is met.
- **Settled architecture (Q1–Q12):** Shape = conductor over existing commands. Deliverables = goal-contract artifact + thin command + loop skill + 1-subsection facilitator delta (answers user Q1: yes, surgically — 1 agent, 10 specialists unchanged). 7-field goal contract, guided/example-rich authoring (grill-me-flavored). Substrate = facilitator+skill spine (Workflow muscle, /loop trigger). Two-tier verify (gate+checker every tick; full /review only at end). Stop ladder (goal_met vs backstop→park) with overridable defaults. Autonomy governed by EXISTING authorization; **NTFY gate parity is load-bearing** (transport-agnostic gates, security allow-list, timeout→park, one-poller). Capture = 1 discussion/run. Dual-purpose `loops/` recipe library grown by promotion.
- This grill resolves the design; output feeds a full /deliberate (steward in the room, since agent definitions are touched) → likely an ADR.

## Key decisions
- **Shape (A) — Conductor over existing commands.** The loop is a thin, goal-driven controller that drives the existing `/plan → /build_module → quality_gate → /review` cycle toward a goal contract and decides when "done" is reached. Steps don't change; the loop holds the goal + stop conditions. Door left open to evolve toward hybrid (C) later. Rationale: least-complex intervention (Principle #8), reuses existing machinery, keeps capture/review/sequencing intact so the steward can bless it.
- **Altitude: hub capability.** Designed from the start as a framework feature derived projects inherit (facilitator delta + loop skill propagate via /apply-framework).
- **Deliverable set (4 layered pieces):** (1) goal-contract artifact format, (2) a new thin command as user entry point, (3) a loop-orchestration skill holding the tick procedure (loadable by the facilitator), (4) a light facilitator definition delta ("loop mode"). Mirrors `/build_module` (command) → `running-build-checkpoints` (skill). Isolates the only agent-definition change to one reviewable delta.
- **Goal-contract schema (7 fields):** `goal`, `success_criteria`, `verify`, `termination`, `non_goals`, `anchor_context`, `autonomy_level`. ID `GOAL-YYYYMMDD-HHMMSS-slug`. Load-bearing trio = success_criteria + verify + termination (makes "done" machine-decidable, not self-graded).
- **Guided authoring is MANDATORY (load-bearing).** The goal contract is never a blank template — it is authored through a guided, example-rich interview where the system proposes recommended criteria WITH examples and the user reacts. This is the user's original "Grill Me as a guide" intuition made concrete: grill-me's discipline (one question, recommended answer, worked examples) becomes the goal-authoring front-end. Driven by user being a manager-gatekeeper who must make good criteria choices without authoring cold. Connects to education perspective (teach the gatekeeper) and feedback_teach_dont_dump.

- **Authoring mechanism = (B) dedicated goal-authoring interview** that borrows grill-me's discipline (one question, recommended answer, worked example per field) but is specialized to elicit the 7 fields and emit a structured `GOAL-…` contract. Lives as a step inside the loop skill (or thin sub-skill). Natural home for an example library (bank of "good criterion" examples per domain the interview draws from). Rationale: grill-me's interview pattern is right; its freeform-brainstorm OUTPUT is wrong shape — a loop needs a machine-readable contract.
- **Worked reference example captured:** GOAL-…-api-rate-limit (FastAPI rate limiter) demonstrating verifiable criteria, deterministic-vs-judge verify split, the 4-rung termination ladder, non_goals, anchor_context, L2 autonomy. Three coaching principles the interview must teach: (1) verifiable-not-vibes, (2) deterministic-first/judge-sparingly, (3) termination is a ladder not one rule.

- **Execution substrate = (A) facilitator + loop skill is the conductor spine; (B) Workflow tool is optional muscle for parallel maker/checker fan-out on heavy ticks; (C) harness /loop is the optional trigger/scheduling layer.** Mapped to anatomy: Trigger → /loop or event or manual run; Action → facilitator+skill; Verify → quality_gate + checker agent (parallel via Workflow when worth it); Stop → termination ladder evaluated by conductor. Keeps per-tick reasoning captured + human-legible (non-negotiable) while reaching for Workflow robustness when needed.

- **Verify cadence = two-tier, full review ONLY at the end.** Every tick: `quality_gate.py` (deterministic) + ONE independent checker agent reviewing only the delta (checker ≠ builder → Principle #4 holds inside the loop; qa-specialist default, domain-swapped). Full specialist `/review` panel runs ONLY at the goal-met candidate (the end) — NOT at intermediate/risk-triggered milestones (user simplified this). Rationale: bounded per-tick cost + continuous independence + `/review` reused exactly as the merge gate.

- **Stop semantics + defaults.** Good exit (`goal_met`): all criteria green → full `/review` → pass → HALT and present ready-to-merge result for human approval (no push, no auto-merge); review-blockers → become new criteria, loop continues if iterations remain, else backstop halt. Backstop exits (`max_iterations`/`no_progress`/`budget`): HALT + structured loop report (tried / still-red / why-stopped), hand back to human, never silent-continue/push/merge. Defaults (interview-proposed, overridable): max_iterations=8, no_progress=2 consecutive ticks on same red criterion, budget=run token target or 200k. Bakes non-negotiables into control flow → steward-signable.

- **Autonomy mapping (governed by EXISTING authorization, no parallel system).** L1 report-only = always allowed (plan + first-tick diff, stop for approval, no commits). L2 assisted = requires Autonomous Execution Authorization block ACTIVE (commits per tick without per-step asking, halts at goal-met for merge approval, never pushes). L3 unattended/cross-session = requires block AND ALLOW_AUTO_LAUNCH_SESSION + MAX_AUTO_LAUNCH_DEPTH=1, reuses ADR-0018 session_supervisor. Loop NEVER expands authority; all prohibited actions (push, auto-merge, settings.json edits) stay prohibited at every level.
- **NTFY gate parity is LOAD-BEARING (user: "the whole point").** The loop's human-approval gates must work through the ntfy loop so an AFK user approves from their phone, treated EXACTLY as if sitting at the computer. Design: gates are TRANSPORT-AGNOSTIC — AskUserQuestion at the computer, `collab_loop.py` ask/poll over ntfy when AFK — same decision points, same bounded choices, resume on the matched choice label. Three constraints ride along: (1) SECURITY ASTERISK (always-on invariant, non-negotiable): ntfy replies are unauthenticated → validate against a fixed allow-list, act on the matched LABEL not raw text, never print the topic slug; blast radius already bounded (no reply, even spoofed, can trigger push/auto-merge — prohibited at every level). (2) TIMEOUT: on an approval/design gate with no valid reply within the 1-hour window, the loop PARKS (halt + preserve state + loop report), never guesses; resumes on reply (check-before-poll). (3) OPERATIONAL: exactly ONE collab_loop poll Monitor at a time (memory feedback_ntfy_one_monitor_at_a_time); milestone `say` updates for phone-followable progress.

- **Gate design CONFIRMED + chattiness = (A).** Transport-agnostic gates (AskUserQuestion at computer / collab_loop ask-poll AFK) with the 3 constraints (security allow-list, timeout→park, one-poller+milestone-say) all accepted. Chattiness: loop decides routine in-tick choices autonomously at L2/L3; ntfy only for real gates (approvals, design forks, blockers). Pinging for micro-choices defeats run-while-you-sleep.

- **Facilitator delta = ONE pointer-subsection (~15-20 lines), not a rewrite. ANSWERS USER Q1.** New subsection "Goal-Seeking Loop Mode": names capability, states directive shift (in loop mode the goal contract is north star; iterate build→verify→refine until criteria met, not single-pass synthesis), points to the loop skill for procedure, reaffirms non-negotiables hold inside the loop (per-tick capture, Principle #4 independence, transport-agnostic gates, no push/auto-merge). All operational procedure lives in the SKILL. Exactly ONE agent changes (facilitator); the 10 specialists DO NOT change. Runs in the MAIN loop wearing the facilitator hat (per model-tiering policy: orchestrator never a dispatched subagent), dispatching cheap builder/checker specialists per tick.

- **Capture = one discussion per loop run, reusing existing pipeline.** `DISC-…-loop-<slug>` created at kickoff; goal contract is `turn_id=1` (same slot as the /deliberate context-brief); each tick appends events (builder turn, checker turn, gate result, termination decision, ntfy gate prompts/replies-by-label); `close_discussion` at loop end → sealed transcript + SQLite ingest. Nothing new to build; Principle #2 holds by construction; whole goal's reasoning trail lives in one place (feeds retro/meta-review).

- **Example/recipe library = one dual-purpose `loops/` library.** Recipe files = goal-contract templates (verify/stop pre-filled) + attribution + tier/mode tags (à la Berman). Purpose 1: seeds the guided authoring interview with proven per-domain example criteria. Purpose 2: directly-instantiable reusable loop recipes (docs-sweep, coverage-raise, regression-ledger-sweep, dependency-update, flaky-test-hunt — governance-flavored). Grows via human-approved PROMOTION of successful loop runs (reuse `/promote` + Layer-3 pattern; operate-then-formalize). Ships with a starter set adapted from proven loop-engineering patterns. Hub leverage: recipes shareable across derived projects.

- **Command name = `/goal-loop`** (developer choice; hyphen style consistent with harness commands like /code-review, /analyze-project). The goal CONTRACT is the noun; `/goal-loop` is the verb-phrase that pursues it.
- **PROACTIVE SUGGESTION is a requirement (developer: "I want this framework to suggest using it if it will help").** The framework should recognize when a task would benefit from a goal-loop and SUGGEST `/goal-loop` — make it an offered affordance, not a tool the developer must remember. Mechanism TBD (Q14).

- **Suggestion mechanism = prompt-level routing heuristic in CLAUDE.md Workflow Sequencing (+ a `/plan`-end nudge), suggest-never-impose.** Triggers (all three): (1) verifiable done-state (machine-checkable criteria), (2) iterative convergence expected (multiple build→verify cycles, not one-shot), (3) not a micro-fix. Counter-trigger: vague/unverifiable goal → suggest grill-me/`/plan` to sharpen FIRST, not a loop. Offered at task intake via AskUserQuestion (computer) / ntfy (AFK): "good /goal-loop candidate — run as loop or step-by-step?"; developer decides; never auto-starts. Prompt-level (not a hook) because it's a judgment call best made by the orchestrating model reading the task; a mechanical hook would over-fire (Principle #8).

## Key decisions (continued)
- **Hub propagation CORE/SKIN split SETTLED.** CORE (additive via /apply-framework): `/goal-loop` command + loop skill + facilitator loop-mode subsection + goal-contract schema/template + CLAUDE.md suggestion heuristic + ladder/autonomy DEFAULTS + starter recipe set. SKIN (never overwritten): project-promoted recipes, goal-contract instances, per-project overrides of defaults, the project's Autonomous Execution Authorization content (goal-loop just READS it). Namespacing: `loops/starter/` (CORE, additive-merge) vs `loops/local/` (SKIN, never touched); apply-framework treats `loops/` as additive-merge NOT replace (pre-empts update35 ID-collision lesson).
- **Cost / model-tiering SETTLED.** Conductor (facilitator-in-main-loop) = session top-tier (orchestrate/judge/terminate only); builder per tick = sonnet; checker per tick = sonnet (opus only for enforcement-security-critical criteria); search = haiku; deterministic verify (quality_gate) = free. Loop AMPLIFIES lean-dispatch value (build+check repeats every tick → cheap-tier savings compound). Cost visibility: (1) `loop-cost`-style pre-run estimate ≈ (build+check per tick)×expected-iterations+overhead, surfaced before launch to set the budget rung; (2) per-tick/per-goal cost captured into telemetry Layer 2 → feeds the dashboard north-star (cost-per-goal, value-vs-subscription).
- **Goal-size + spec seam SETTLED.** Goal contract = lightweight, verification-first sibling of a `/plan` spec. Routing mirrors existing Workflow Sequencing: BIG/novel/architectural → `/plan` first → spec's acceptance criteria SEED the goal contract's success_criteria (`/plan` emits a goal contract, no duplication) → `/goal-loop`. SMALL/convergent → author goal contract directly → `/goal-loop`. Runtime guard: non-convergence within the ladder → PARK + recommend decomposition (`/plan` or sequential sub-goals/child contracts), never thrash.
- **Out-of-scope guard SETTLED.** Authoring interview runs an "is this even loop-shaped?" check FIRST and fails fast, refusing to emit a contract for: (1) no verifiable criterion possible (subjective/aesthetic) → route to grill-me/`/plan` to sharpen or accept it's human-judgment; (2) design/exploration not build→verify → `/deliberate` or `/plan`; (3) done-state only verifiable via a prohibited/irreversible action (deploy/push/merge/external) → human gate / out of scope. Critical-risk goals (auth/data/infra) = IN scope but forced L1/human-gated + mandatory full review (gated hard, not refused). "Sometimes the best help is: a loop is the wrong tool — do this instead." Protects steward concern (loop never launders unverifiable/unsafe work).
- **Resumability SETTLED.** Loop state lives OUTSIDE the conversation (Ralph lesson). Durable spine: goal contract (`GOAL-…` file, immutable north star) + a small loop-state record rewritten each tick (iteration, per-criterion green/red, ladder counters, last action+result — mirrors /deliberate state.json + grill-me checkpoint) + discussion events (full trail). On context compaction OR fresh session: conductor reconstructs from {contract + loop-state + recent events} and continues — never restarts, never re-does a green criterion. L3 cross-session: loop-state = the rolling handoff payload session_supervisor already passes between `claude -p` runs (+ BUILD_STATUS loop-state resume anchor, ADR-0019).
- **Education gate SETTLED + STRENGTHENED.** Goal-met → full `/review` → education gate → human merge approval (loop never auto-merges, so the gate always gets its turn). Interactive: walkthrough teaches the CONCEPTS/possibility-space of what the loop built (not syntax) → quiz/explain-back → approve. AFK: result parks at the human-approval gate; education DEFERRED to next interactive session + logged (Principle #6); nothing merges until BOTH /review and education clear. **DEVELOPER WENT FURTHER: the walkthrough is REQUIRED / never-skippable for goal-loops, even low-risk ones** — because code may be produced unwatched, so the loop must convert speed into COMPREHENSION gain, not comprehension debt. This is the safeguard against the loop widening the manager↔agent comprehension gap (ties to user_education_perspective + feedback_teach_dont_dump). Steward will care about this specifically.
- **Trigger scope SETTLED.** v1 = manual `/goal-loop <contract>` + the proactive suggestion only. Scheduled/event triggers (cron/CI-failure/PR-comment) = deliberate PHASE 2 (purely additive via /loop/CronCreate/hooks; deferring costs nothing, keeps the steward's first review focused on the engine not the automation blast radius). Prove convergence before automating unattended firing.
- **Build phasing SETTLED.** Phase 1 MVP = goal-contract schema + guided authoring interview (+ gatekeeper check + `loops/starter/` set) + thin `/goal-loop` command + loop-orchestration skill (build→verify→refine, two-tier verify, ladder, park) + facilitator loop-mode subsection + capture (1 discussion/run + loop-state) + L1/L2 autonomy under existing block + transport-agnostic gates wired to EXISTING `collab_loop` (ntfy approval day one) + model tiering + CLAUDE.md suggestion heuristic + goal-met→/review→required-education→approval. Phase 2 = scheduled/event triggers + L3 unattended via session_supervisor + loop-cost estimate + per-goal telemetry + /promote recipe-growth. Phase 3 = CORE/SKIN packaging into /apply-framework + rollout to IJ/VP/Howie. Phase 1 = smallest steward-approvable, genuinely-usable slice; later phases purely additive.

## Open threads
- NONE — design complete (Q1–Q22).

## Next steps (forward path)
1. Fold these decisions into a sharp implementation spec (Phase-1 MVP scope).
2. Run full `/deliberate` (steward + architecture-consultant + independent-perspective + qa). Genuine fork to argue: is the facilitator delta truly minimal-enough, or does loop-mode need more in the definition?
3. Steward gate (APPROVE/REVISE/DEFER/DECLINE vs PHILOSOPHY.md) on the agent-definition change.
4. Developer approval (Principle #7).
5. Likely an ADR (framework-scope) → Phase-1 build via /plan → /build_module.

## Flagged for others
- **Steward:** must gate the facilitator definition change (framework evolution) AND the "education walkthrough required even for low-risk loops" stance.
- **Developer:** final Principle #7 approval of the agent-def change; validate the ladder default NUMBERS (max_iter=8 / no_progress=2 / budget=200k) against a real run before locking them.

## Context note
- 2026-06-20: soft nudge (~102k) → continued. HARD threshold (~132k of a ~200k-profiled sensor; running on 1M Opus) fired after Q12 → checkpointed + offered pause; developer chose CONTINUE → completed Q13–Q22 same session. Grill COMPLETE, fully disk-backed.

## Flagged for others
- (none yet)

## Q&A log
### Session 1 — 2026-06-20
**Q:** What is this loop's fundamental relationship to your existing workflow? (A) Conductor over existing commands / (B) New autonomous track / (C) Hybrid. Recommended (A) as spine with door to (C).
**A:** agree

**Q:** What's the deliverable set + primary entry point? Recommended 4 layered pieces: (1) goal-contract artifact format, (2) thin new command, (3) loop-orchestration skill (tick procedure), (4) light facilitator delta. Mirrors command→skill pattern; isolates the agent-def change.
**A:** agree

**Q:** What fields does the goal contract carry? Recommended 7-field schema (goal, success_criteria, verify, termination, non_goals, anchor_context, autonomy_level) with success_criteria+verify+termination as load-bearing trio.
**A:** I agree, but I am going to need help, with examples, that walks me throught these factors. We really need to help the user make the best choices in this regard.

**Q:** How is the goal contract authored? (A) reuse grill-me as-is, or (B) dedicated goal-authoring interview that borrows grill-me's discipline but emits a structured GOAL artifact (recommended B; natural home for an example library).
**A:** agree

**Q:** What drives the loop's ticks? (A) facilitator+skill conductor / (B) Workflow tool engine / (C) harness /loop. Recommended A as spine, B as optional muscle, C as optional trigger layer.
**A:** yes

**Q:** How much verification per tick + how is independence enforced? Recommended two-tier: deterministic gate + single independent checker every tick; full /review panel at goal-met (and risk milestones).
**A:** I agree.  I only want the full review at the end

**Q:** Stop semantics + ladder defaults? Recommended distinct good-exit (goal_met→full review→present for approval, no push/merge) vs backstop-exit (halt+loop report, hand back) behaviors; defaults max_iter=8, no_progress=2, budget=token-target/200k, all overridable.
**A:** agree

**Q:** Does the loop's autonomy_level map onto the EXISTING Autonomous Execution Authorization (L1 always / L2 needs block active / L3 needs block + ALLOW_AUTO_LAUNCH), with no new autonomy surface?
**A:** ok, but this needs to be something that works with the NTFY loop, allowing me to approve through that mechanism.  In fact, it needs to treat the NTFY loop EXACTLY like I was sitting at my computer.  That is the whole point

**Q:** Confirm transport-agnostic gates + 3 ntfy constraints (security allow-list, timeout→park, one-poller+milestone-say); and chattiness on routine in-tick decisions: (A) autonomous, ntfy only for real gates, or (B) ntfy more liberally?
**A:** agree, and A

**Q:** Is the facilitator delta a single pointer-subsection ("Goal-Seeking Loop Mode", procedure in the skill, runs in main loop, 10 specialists unchanged) — or a deeper redefinition?
**A:** agree

**Q:** Capture model — one discussion per loop run (goal contract = turn 1, ticks as events, close at end) reusing the existing pipeline, vs separate run-log?
**A:** agree

**Q:** Example/recipe library — one dual-purpose `loops/` library (powers authoring + directly instantiable Berman-style recipes), grown by human-approved promotion of successful runs, with a starter set? Or keep examples and recipe catalog separate?
**A:** agree

**Q:** What do we name the command? Candidates /pursue, /goal, /chase, /seek, /converge. Recommended /pursue (verb convention, avoids shadowing harness /goal).
**A:** Let's call it "\goal-loop", and I want this framework to suggest using it if it will help.

**Q:** How should the framework suggest /goal-loop? Recommended prompt-level routing heuristic in CLAUDE.md Workflow Sequencing (+ /plan nudge), gated on 3 triggers (verifiable done-state + iterative convergence + not-micro-fix), suggest-never-impose. More assertive (hook) or more passive (only on ask)?
**A:** agree

**Q:** CORE vs SKIN split for hub propagation? Recommended: CORE (command/skill/facilitator-subsection/schema/suggestion-heuristic/defaults/starter-recipes) additive; SKIN (promoted recipes/instances/overrides/authorization-content) never overwritten; `loops/starter/` vs `loops/local/` namespacing + additive-merge.
**A:** agree

**Q:** Model tiering (conductor top-tier; build/check sonnet; search haiku; gate free) + pre-run loop-cost estimate + per-goal cost into telemetry?
**A:** agree

**Q:** Goal-contract↔/plan-spec seam (lightweight sibling; big→/plan seeds contract; small→author directly) + non-convergence parks with decomposition recommendation?
**A:** agree

**Q:** Out-of-scope "too-vague-to-loop" guard — authoring interview refuses to emit a contract for (1) no verifiable criterion, (2) design/exploration, (3) done-state needs prohibited/irreversible action; critical-risk = in-scope-but-max-gated?
**A:** agree

**Q:** Resumability — durable loop-state record each tick + reconstruct-on-reset (compaction/session boundary); L3 reuses session_supervisor with loop-state as handoff?
**A:** agree

**Q:** Education gate preserved (goal-met→/review→education→merge; AFK defers+logs; nothing merges until both clear)? And go further — walkthrough REQUIRED/never-skippable even for low-risk loops given unwatched-production risk?
**A:** agreee

**Q:** Trigger scope for v1 — manual /goal-loop + suggestion only, with scheduled/event triggers as deliberate Phase 2?
**A:** agree

**Q:** Build phasing — Phase 1 MVP (schema+authoring+command+skill+facilitator-subsection+capture+L1/L2+collab_loop gates+tiering+suggestion+review/education) / Phase 2 (triggers, L3, loop-cost+telemetry, /promote growth) / Phase 3 (CORE-SKIN hub propagation). Agree + Phase-1 boundary?
**A:** agree
