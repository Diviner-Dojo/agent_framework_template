---
discussion_id: DISC-20260526-164631-quiz-collab-loop
started: 2026-05-26T16:48:51.115890+00:00
ended: 2026-05-28T01:58:55.721497+00:00
agents: [educator, facilitator]
total_turns: 2
---

# Discussion: DISC-20260526-164631-quiz-collab-loop

## Turn 1 — educator (proposal)
*2026-05-26T16:48:51.115890+00:00 | confidence: 0.9*
*tags: quiz, education, blooms-taxonomy*

QUIZ-20260526-001 (collab_loop.py / ADR-0019, Tier 2, 7 Q, pass 70%=5/7, open-book). Bloom dist: understand 2, apply 2, analyze 2, evaluate 1.

Q1 [Understand/conceptual, C1]: allow-list in code vs rule-only — what the distinction means + why 'leave enforcement to the consuming agent' was rejected. RUBRIC: rule states intent but can't enforce itself; code path (match_choice -> _classify_reply_payload -> INVALID) runs regardless of whether caller remembers; 'a rule without a code tripwire is an open boundary'.
Q2 [Understand/conceptual, C2]: empty-title rule — why a titled MAIN message must be filtered + what bad outcome it prevents. RUBRIC: agent always titles MAIN outbound; unfiltered -> agent reads its own question as a reply (answers its own questions / output becomes input -> could trigger gated action with no human).
Q3 [Apply, C4]: 6h-AFK scenario, teammate says 'just start poll, it'll pick up the 2pm reply' — correct? + correct recovery sequence. RUBRIC: teammate WRONG; poll baselines since=now so the 2pm reply is in the past, invisible forever; run check <window covering gap> first (one-shot lookback) THEN arm poll.
Q4 [Apply/debug-scenario, C1]: tapped 'Yes' but log shows REPLY-INVALID — root cause + what validation did + what to check. RUBRIC: match is case-insensitive+trimmed but EXACT vs canonical label; button POSTed a string != the choices entry (case/typo/whitespace); INVALID path discarded raw text; check the choices passed to ask vs the button POST body.
Q5 [Analyze/change-impact, C3]: contributor swaps type(exc).__name__ -> str(exc) for debugging — which property breaks + mechanism + consequence. RUBRIC: breaks topic-slug confidentiality (slug is only auth); urllib str(exc) embeds the full URL incl. the interpolated slug; slug lands in stdout/transcript -> anyone reading the log gets the credential.
Q6 [Analyze/conceptual, C1]: why is rule-only an 'open' boundary — what goes wrong even when everyone follows the rule + why the tripwire belongs at poll/check. RUBRIC: rule has no enforcement at execution moment; new contributor / context where rule not loaded / a 'just monitoring' poll-without-choices; data crosses boundary regardless; poll/check is where untrusted data first enters the agent's context, so validate AT crossing or never reliably.
Q7 [Evaluate/change-impact, C1+C4]: deploy-approval team wants poll with no choices + inspect raw REPLY text (options unknown at runtime) — evaluate. RUBRIC: conflicts with invariant 'act on matched label, never raw text'; raw unauthenticated text reaches context (injection e.g. 'approve AND delete backups'); fix: compute the valid set before arming, pass as choices, act only on REPLY-MATCH; if truly unknowable, escalate to security-specialist — don't inspect raw text.

Partial credit (0.5) allowed on Q3/Q5/Q7 for right-direction-but-missing-a-component. Full rubric + scoring guide in transcript.

---

## Turn 2 — facilitator (synthesis)
*2026-05-28T01:58:55.721497+00:00 | confidence: 0.95*
*tags: quiz, results, education*

Quiz results: 100% (7/7, PASS — threshold 70%). Mastery tier. Breakdown by Bloom's: understand 2/2, apply 2/2, analyze 2/2, evaluate 1/1. All four trust-boundary concepts demonstrated in the developer's own words. Strengths: exceeded rubric on Q4 (inferred that REPLY-INVALID rather than REPLY: proves choices were armed but mismatched; correctly ruled out case/whitespace and missing-allow-list) and Q6 ('prompt-injection exposure happens at ingestion, not at the decision' — the precise reason a rule-only boundary is open). Q3/Q7 correctly added 'pass the choices so match_choice enforces' and 'hold the guarded action until a *-MATCH'. Gaps: none. Education gate CLEARED for ADR-0019 commit.

---
