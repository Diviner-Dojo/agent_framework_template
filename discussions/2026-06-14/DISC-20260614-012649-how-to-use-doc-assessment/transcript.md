---
discussion_id: DISC-20260614-012649-how-to-use-doc-assessment
started: 2026-06-14T01:28:48.735280+00:00
ended: 2026-06-14T01:28:49.220935+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective, ux-evaluator]
total_turns: 8
---

# Discussion: DISC-20260614-012649-how-to-use-doc-assessment

## Turn 1 — facilitator (evidence)
*2026-06-14T01:28:48.735280+00:00 | confidence: 0.9*
*tags: context-brief, documentation, assessment*

CONTEXT BRIEF — Multi-agent deliberation assessing docs/how-to-use-presentation.html (16-slide HTML how-to guide). Developer request: multi-perspective ASSESSMENT (no edits) of whether the doc serves a real human, from TWO lenses (unfamiliar beginner; skeptical experienced practitioner) PLUS a load-bearing accuracy/honesty check of the doc's claims against the real codebase (syncing-framework-docs treats these HTMLs as presentation-HTMLs that must stay in sync). Panel: ux-evaluator, docs-knowledge, independent-perspective x2 (beginner + experienced role-play), architecture-consultant.

---

## Turn 2 — ux-evaluator (evidence)
*2026-06-14T01:28:48.794857+00:00 | confidence: 0.88*
*tags: ux, beginner, friction, mental-model*

BEGINNER EMOTIONAL VERDICT: mixed — visually polished and sincere, but addresses someone who already knows what an ADR / pre-commit hook / 'Layer 3' is. Highest-friction (BLOCKING): (1) slide-1 POC warning is honest but jargon-loaded ('sourced-assertion memory substrate', 'deterministic routing') — first contact is a warning a newcomer cannot parse; (2) slide 2 throws the 5-phase Seed->Anchor->Scout->Reconcile->Specify process before ever defining WHAT the framework IS — no 'what is this' anchor (the companion deck does this correctly); (3) slide 16 'first command' /review src/ is a dead end on a template whose src/ has no user code. MAJOR: 'What You Get' card leads with raw counts not capabilities; CLAUDE.md-customization guidance buried as a slide-15 anti-trap instead of a setup step; content-dense slides (8,10,15) clip below the fold on 1366x768 with no scroll affordance. Recs: add plain-language 'What is this?' slide before slide 2; de-jargon the POC warning; change the first command; move CLAUDE.md setup up; add overflow fade.

---

## Turn 3 — docs-knowledge (evidence)
*2026-06-14T01:28:48.858722+00:00 | confidence: 0.91*
*tags: docs, install-correctness, prerequisites, blocking*

BEGINNER-CAN-INSTALL-AND-RUN VERDICT: NO. Two independent BLOCKING gaps: (A) the doc never states you need an Anthropic/Claude paid account + claude login before any /command runs, and never says /commands run INSIDE the Claude Code CLI (not the shell) — the load-bearing sentence 'Claude Code: the CLI that runs all agents and commands' is buried as the 3rd sidebar bullet, styled like Python/Git; (B) slide-16 first command /review src/ targets a template src/ with only framework scaffolding, no user code -> undefined success state. Missing prerequisites/steps (verified vs requirements.txt, pyproject.toml, .env.example, init_db.py): no virtualenv step before pip install (sentence-transformers ~90MB model download, sqlite-vec native build); no claude login; no 'cp .env.example .env' (NTFY_TOPIC needed for the slide-12 AFK feature); no 'gh auth login' for /discover-projects + /ship. README prerequisite table is more complete than slide 3 but shares the shell-vs-Claude-Code ambiguity and also omits the subscription requirement. Strength: slide 8 'What Do I Do When...' is genuinely newcomer-friendly.

---

## Turn 4 — independent-perspective (evidence)
*2026-06-14T01:28:48.925262+00:00 | confidence: 0.88*
*tags: beginner, role-play, the-wall, onboarding*

BEGINNER ROLE-PLAY (reads ONLY the doc). REACHES FIRST WORKING ACTION? NO. Slides 1-2 never establish what the thing IS before handing over a 5-phase process; jargon arrives fast and undefined ('deliberate','agent panel','specialists','ADR' never expanded). Slide 3 shell commands run fine and create false confidence. THE WALL: slide 16 says my 'first command' is /review src/, so I type it in the same terminal where pytest just worked -> 'bash: /review: command not found'. Nothing in 16 slides says to launch Claude Code, log in, that it needs a paid Anthropic account, or that slash-commands run inside it. Root cause is mechanical: slides 3 and 16 put shell commands and /review in the SAME monospace code-block styling -> identical styling reads as identical execution context. The sentence that reveals the missing premise ('treating this like vanilla Claude Code', slide 15) arrives ~13 slides too late. Single most important fix: an explicit launch+login step between setup and first command, with shell vs in-Claude commands visually separated.

---

## Turn 5 — independent-perspective (evidence)
*2026-06-14T01:28:49.002497+00:00 | confidence: 0.82*
*tags: experienced, trust, over-promising, honesty*

EXPERIENCED-PRACTITIONER ROLE-PLAY. VERDICT: promising-but-rough. TRUST-EARNING (keep): slide-1 disclaimer naming specific POC subsystems (rare, anti-hype); slide-15 anti-patterns ('you pay for a framework you are not using') — a vendor describing real failure modes; coherent correctly-ordered workflow; slide 8 + cheat-sheet respect a senior's time. TRUST-LOSING: (1 HIGH) '/review ... Takes 30-90 seconds' (slide 4) is falsifiable from the deck's OWN slide 5 (4-5 parallel LLM agents + synthesis) — #1 close-the-tab item; one obviously-wrong checkable number poisons every unverifiable claim; (2 HIGH) 'Setup in 3 Minutes' measures clone+pip+pytest and silently assumes Claude Code installed+authed, exercising none of the actual value; (3 MED) '10x cheaper' — right direction, fabricated multiplier, no cite; (4 MED) slide-10 header 'The Framework Improves Itself' contradicts its own honest body (humans run /retro,/meta-review,/promote with approval); (5 MED) cross-deck principle-count seam: companion deck says '8 Non-Negotiable Principles' but this deck invokes Principle #9 (95% gate) on slide 15 and CLAUDE.md defines 9. Recs: kill/qualify hard time numbers, drop '10x', reframe slide-10 header, reconcile principle count, add one real proof artifact.

---

## Turn 6 — architecture-consultant (evidence)
*2026-06-14T01:28:49.066863+00:00 | confidence: 0.93*
*tags: accuracy, codebase-sync, stale-counts, onboard-misroute*

ACCURACY/HONESTY AUDIT vs codebase. VERDICT: mostly-accurate-minor-drift — NO fabricated capabilities (every feature described exists), but stale numbers + one mis-routed path. HONESTY FAILURES ranked: (1) /onboard mis-routes — slides 3+8 present /onboard as THE path for existing projects, but per ADR-0021 /onboard is 'superseded-but-retained'; recommended entry is /apply-framework, which the doc never mentions (most consequential). (2) quality gate 'CLAUDE.md says 7/7' actually runs 8 checks (BUILD_STATUS freshness is check 8, advisory, quality_gate.py:387). (3) stale counts (slide 3): commands 17->actual 24; skills 19->actual 22; hooks 7->actual 9 registered scripts; agents 12 correct — deck UNDER-sells. Separately CLAUDE.md Rules Index lists 13 skills vs 22 on disk (internal drift). CONFIRMED accurate: secret-detection 12 patterns (validate_tool_use.py:61), file-lock 120s (:146), auto-format, branch-protection, BUILD_STATUS auto-save, collab_loop 4 modes + two-topic ntfy, /analyze-project >=20/25 (analyze-project.md:220), v3.5, all 16 named commands exist. Omitted-but-real: /apply-framework, /seed (named as a PHASE on slide 2 yet never linked to its command), /handoff, /spawn-project, /status, /conversation, /distribute, /evaluate-repo-security. Fixes: re-route to /apply-framework; 7/7->8 checks; refresh 24/22/9 counts; reconcile counts.

---

## Turn 7 — facilitator (synthesis)
*2026-06-14T01:28:49.145987+00:00 | confidence: 0.87*
*tags: synthesis, documentation, onboarding, accuracy*

SYNTHESIS. The deck is content-rich and unusually HONEST for its genre but is a REFERENCE for insiders, not an on-ramp. Strongest signal: three panelists independently identified the SAME blocking failure. BEGINNER VERDICT: NO — two independent blocks: (A) 'The Wall' — doc never says /commands run inside Claude Code, never states the paid Anthropic account + claude login, and styles slash-commands like shell commands, so the beginner types /review in bash and gets command-not-found; (B) slide-16 first command /review src/ is a dead end on an empty template. Plus a mental-model gap (no 'what is this' before the 5-phase process; undefined jargon). EXPERIENCED VERDICT: promising-but-rough — trust won on the honest slide-1 disclaimer + slide-15 anti-patterns, lost on a few inflated/falsifiable numbers ('30-90 seconds', '3 Minutes', '10x cheaper', 'Improves Itself'). ACCURACY: mostly-accurate — zero fabricated capabilities, but /onboard mis-routes (should be /apply-framework per ADR-0021), quality gate is 8 checks not 7, and counts are stale (24 commands/22 skills/9 hooks). Points of agreement: the on-ramp (not the content) is broken; the honesty disclaimer is a genuine asset to keep. Tension: how aggressive a rewrite vs preserving the deck's voice — developer's call.

---

## Turn 8 — facilitator (decision)
*2026-06-14T01:28:49.220935+00:00 | confidence: 0.87*
*tags: decision, recommendations, prioritized*

RECOMMENDATION (assessment only; no edits applied to the live doc). Prioritized fix list. P1 UNBLOCK FIRST RUN: (1) add explicit launch+auth step — /commands run inside Claude Code, need a paid Anthropic account + claude login; (2) visually separate 'run in terminal' vs 'type inside Claude Code' code blocks; (3) change slide-16 first command off the empty template (e.g. a /deliberate that works with zero user code). P2 FIX ACCURACY DRIFT: (4) re-route existing-project guidance to /apply-framework, describe /onboard as the deep follow-on (ADR-0021); (5) quality gate 7/7 -> 8 checks (+ BUILD_STATUS freshness advisory); (6) update counts to 24 commands / 22 skills / 9 hooks + reconcile principle count 8-vs-9. P3 DEFLATE NUMBERS: '30-90 seconds', 'Setup in 3 Minutes', '10x cheaper', 'The Framework Improves Itself'. P4 MENTAL MODEL + POLISH: add a plain-language 'What is this?' slide before slide 2; move CLAUDE.md customization up to setup; expand 'ADR' on first use; add scroll/overflow affordance on slides 8/10/15; add one concrete proof artifact. Next action per developer: capture (this discussion) + produce revised sample HTML for review.

---
