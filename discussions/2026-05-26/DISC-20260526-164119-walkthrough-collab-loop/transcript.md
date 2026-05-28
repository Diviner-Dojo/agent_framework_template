---
discussion_id: DISC-20260526-164119-walkthrough-collab-loop
started: 2026-05-26T16:43:48.362126+00:00
ended: 2026-05-26T16:43:48.362126+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260526-164119-walkthrough-collab-loop

## Turn 1 — educator (proposal)
*2026-05-26T16:43:48.362126+00:00 | confidence: 0.9*
*tags: walkthrough, education*

Guided walkthrough of scripts/collab_loop.py (education gate step 1, ADR-0019, Tier 2). Progressive disclosure: problem -> module structure (notify <- collab_loop <- ask_developer) -> 4 load-bearing trust-boundary concepts -> pure-function seams.

CONCEPT 1 - Allow-list enforced IN CODE: ntfy relay is public; topic slug is the only auth, so any reply is unauthenticated. Chain: match_choice (case-insensitive exact match -> canonical label or None) -> _classify_reply_payload (MATCH:<canonical> / INVALID:'(unrecognized reply ignored)' - raw text discarded here) -> _emit/check (print canonical label or the static INVALID string; attacker text never hits stdout/context). A rule without a code tripwire is an open boundary (security review rejected rule-only). Residual risk: open free-text mode (no choices) prints REPLY:<raw text> by design - caller's responsibility; gating decisions MUST pass choices.

CONCEPT 2 - Empty-title free-text rule (classify_message): agent outbound on MAIN is ALWAYS titled; developer free-text typed in the app has no title. require_empty_title=True on MAIN -> titled msg = skip-titled (own echo), empty-title = emit (developer). REPLY topic: every msg is an answer. Break it (publish to MAIN untitled) and the poller answers its own questions. say() reuses notify.send_notification so the title invariant can't be forgotten via a parallel path.

CONCEPT 3 - Never-print-topic / why str(exc) is the trap: slug is a secret; a urllib exception's str() embeds the full request URL incl. the slug. Confirmed regression from the originating project. Every handler prints type(exc).__name__ + a static source label (reply/main/ask), never str(exc)/URL/topic. Watch for str(exc)/print(exc) in any future error path.

CONCEPT 4 - check-before-poll resume: poll() baselines since=now at launch, so a reply sent before the Monitor was armed is invisible to it forever (#1 cause of 'agent ignored my reply'). check <window> is the one-shot lookback that recovers backlog (one seen set across both topics). Correct resume: check <window> THEN arm poll. Baseline-at-launch is intentional (avoids unbounded re-surfacing); seen set doesn't persist across restarts, which is why check must come first.

PURE-FUNCTION SEAMS: classify_message, parse_ntfy_stream, match_choice, _classify_reply_payload, validate_since are pure (no I/O) and hold the security-critical logic -> unit-testable without a live ntfy service; I/O isolated in _http_get/_post_json + injected sleep/emit_fn (mirrors ADR-0018). Lets an unattended agent verify itself.

Concept-check preview: developer should explain back (1) why rule-only is insufficient + what the code does to block adversarial replies; (2) how titled-vs-empty distinguishes agent from developer + the untitled-MAIN failure; (3) why type(exc).__name__ not str(exc); (4) why poll misses pre-arm replies + the check-then-poll sequence.

---
