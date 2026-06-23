---
discussion_id: DISC-20260623-042616-walkthrough-goal-loop-phase1-education
started: 2026-06-23T04:31:13.389086+00:00
ended: 2026-06-23T04:31:13.389086+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260623-042616-walkthrough-goal-loop-phase1-education

## Turn 1 — educator (proposal)
*2026-06-23T04:31:13.389086+00:00 | confidence: 0.91*
*tags: w, a, l, k, t, h, r, o, u, g, h, ,, e, d, u, c, a, t, i, o, n, ,, g, o, a, l, -, l, o, o, p, ,, v, e, r, i, f, i, e, r, -, i, n, t, e, g, r, i, t, y*

# Education Gate Walkthrough — scripts/goal_loop.py — /goal-loop Phase 1 (ADR-0026)
## Required merge gate R11 (never skippable). Bloom Understand→Analyze, Tier 2.

## Opening Frame
goal_loop.py exists because a loop that can measure its own success can also lie about it — and an automated loop that lies about success is more dangerous than one that fails. Every design decision traces to that threat (the deliberation "verifier-integrity" headline).

## Concept 1 — Verifier-Integrity Model (R5): the heart. Three composing defenses.
- **R5.2 green-only-via-verify**: a criterion turns green ONLY when a deterministic Verifier/quality_gate returns true, or the independent llm-judge checker returns a parseable {"green":true}. Never from prose, a contract line, anchor_context, a model turn, or an ntfy reply. Fail-closed: unparseable verdict → RED (parse_judge_verdict). Spot-the-gaming: a criterion whose verify is `echo "done"` is NOT caught by R5.2 — R5.2 guarantees green flows through verify, not that verify is meaningful. Residual risk → R12 authoring coaching ("prefer verify the builder cannot edit") + the R11 walkthrough human backstop.
- **R5.1 tamper tripwire**: tamper_tripwire + verify_command_targets + _SENSITIVE_PATH_RE. If a tick's diff touches the test/verifier surface (tests/, conftest, pyproject, .coveragerc, quality_gate.py, goal_loop.py itself, a coverage pragma, or the file a criterion's verify names) → a HUMAN GATE fires before the tick can count. B3 fold: deletions/renames covered via parse_unified_diff (a/ headers + rename lines) + `git diff --name-status`. Coverage pragmas scanned in added lines. Spot-the-gaming: adding `# pragma: no cover` to a failing line trips the gate.
- **R5.4 goal-met re-verify**: at candidate goal-met, re-verify ALL criteria against the CUMULATIVE working-tree delta (diff_source.tick_diff()), not stale per-criterion greens and not an empty diff (B1 fold — empty delta makes an honest checker livelock-red or rubber-stamp). Catches a green from tick 2 that tick 5 silently broke.
- **Composition**: R5.2 narrows the channel green enters; R5.1 stops widening it by editing the verifier; R5.4 verifies the final exit against real current state. Contract-level guards (validate_contract): all-judge rejected, judge-fraction cap (default 0.5), llm-judge must be checker-owned. "A loop must not be sole judge of its own work."

## Concept 2 — Driver/Seam Split: control flow is CODE, not prose.
A model following prose under context pressure is not a reliable keeper of safety-critical state (compaction/resumption erode it). scripts/goal_loop.py owns deterministically: tick counter, termination ladder (max_iter/no_progress/budget), loop-state + integrity hash, re-verify-on-reconstruct, park-and-report. The model is invoked ONLY for build, judge (as independent checker), gate-routing — through seams Verifier/ModelInvoker/GateRouter/DiffSource/AuthAffirmer. The conductor NEVER marks a criterion green. Seam split → control flow unit-tested with fakes (AC1–AC12), no AI. Spot-the-gaming: build text "mark Criterion C green" is irrelevant — the driver ignores prose; only the subsequent Verifier/judge call sets state.

## Concept 3 — Fail-Closed Autonomy (R10).
L1 report-only (no commits, safe fallback) vs L2 commit-capable (opt-in, narrowly scoped to an authorized feature branch). FailClosedAuthAffirmer: main hard-excluded at construction (can't reach L2 even if listed). L2 re-affirmed EVERY tick — revoked mid-run → park (not crash, not silent-continue). Initial non-affirmation → drop to L1 report-only (not crash). Hard invariants at every level: never push, never auto-merge, never self-approve /review — enforced by ABSENCE of any such code path (no `if authorized: push()`), ceiling is a local commit on a scoped branch then a human merge gate.

## Concept 4 — Loop-State Untrusted on Read (R7).
loops/.state/<goal-id>.json is mutable → never trust it; re-derive trust on read. Integrity hash (SHA-256 of content) embedded on write, recomputed on read → mismatch parks immediately. Atomic write (temp + os.replace) eliminates torn writes. reconstruct: deterministic/quality_gate criteria RE-RUN from scratch (cheap); llm-judge greens trusted ONLY if corroborated by an append-only checker event (checker_greens_from_events) else reset to red and re-judged. The append-only discussion is the tiebreaker over the mutable loop-state. Spot-the-gaming: hand-editing the file to mark Criterion C green fails the hash; even with a forged hash, reconstruct re-runs the check (red) or finds no corroborating checker event.

## Summary — invariants that must hold
1. Conductor never marks green — only Verifier / ModelInvoker.judge.
2. Tamper tripwire sees ALL touched paths incl. deletions/renames.
3. Goal-met re-verify runs against a non-empty cumulative delta.
4. Loop-state always read with integrity verification before acting.
5. L2 checked every tick; main hard-excluded at construction.
Failure mode if violated: loop reports SUCCESS while having gamed its verifier / committed off-scope / resumed from tampered state — silent on the outside, which is why each invariant has a named defense. Regression-ledger root-cause class for all goal-loop canaries: Trust Boundary Gap.

## Quiz seeds (Analyze level) — answers withheld; see /quiz
1. Criterion C1 verify=`python scripts/check_endpoints.py` but that script always exits 0; builder doesn't touch it. Which R5 defense applies? Does the tripwire fire? Does goal-met re-verify catch it? Right mitigation?
2. Loop paused; someone hand-edits loop-state to mark an llm-judge Criterion B green (never checker-verified). First thing driver does on read? If hash also forged? What does reconstruct do to B? Authoritative source — file or events — and why?
3. All-judge documentation contract. What happens at load time and why? Minimum change to make it valid? What risk does the deterministic anchor guard against for a subjective task? ADR record?
4. Original goal-met re-verify ran against Diff((),()) (empty). Why does that defeat R5.4 (two failure modes)? Correct delta + function? Blocking-fix vs Phase-2-defer reasoning? Root-cause class?


---
