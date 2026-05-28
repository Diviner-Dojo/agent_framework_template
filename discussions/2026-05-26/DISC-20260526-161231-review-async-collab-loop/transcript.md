---
discussion_id: DISC-20260526-161231-review-async-collab-loop
started: 2026-05-26T16:13:04.388464+00:00
ended: 2026-05-26T16:23:47.341210+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist, security-specialist]
total_turns: 8
---

# Discussion: DISC-20260526-161231-review-async-collab-loop

## Turn 1 — facilitator (evidence)
*2026-05-26T16:13:04.388464+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: /review the async human-in-the-loop ntfy collaboration loop on branch feat/async-collab-loop; address blocking findings, then (later) education gate + commit. Built, gate-green (7/7), mid-build-checkpoint-approved (security+architecture Round 2 APPROVE 0.97/0.95), not yet reviewed or committed.
- **Files/scope**: scripts/collab_loop.py (new canonical two-way loop), scripts/ask_developer.py (M - reduced to thin shim), scripts/notify.py (M - ensure_ascii_title guard + type-name-only error logging), tests/test_collab_loop.py (new), tests/test_notify.py (M - ascii regression), .claude/skills/collaborating-async/SKILL.md (new), CLAUDE.md (M - always-on invariant + skills index), docs/adr/ADR-0019, docs/sprints/SPEC-20260525-233208 (reviewed + R1-R8 resolutions).
- **Developer-stated motivation**: Capability authored from a real agentic_journal session where a HIGH-risk multi-file feature was built end-to-end while the developer was AFK, answering ~5 gating questions by tapping phone buttons. Lets an autonomous agent keep building while surfacing only gating decisions.
- **Explicit constraints**: Confirm (1) untrusted-reply allow-list enforced IN CODE at the poll/check boundary (match_choice -> REPLY-MATCH/REPLY-INVALID; raw adversarial text never surfaced); (2) never-print-topic-slug on ALL error paths; (3) ask_developer shim keeps its 17 tests green; (4) ASCII-title guard in notify.py. Binding spec resolutions R1-R8 supersede the spec's verbatim reference impl where they differ.

---

## Turn 2 — security-specialist (proposal)
*2026-05-26T16:21:02.717466+00:00 | confidence: 0.91*
*tags: security, trust-boundary, allow-list, verdict:approve-with-changes, blocking:0, advisory:2*

Verdict: APPROVE-WITH-CHANGES (confidence 0.91). Trust boundary correctly enforced in code.
- CONFIRMED CLOSED: never-print-topic on ALL traced error paths (collab_loop _http_get HTTPError+bare Exception, ask failure, resolve_config RuntimeError; notify URLError+Exception; ask_developer fetch_reply). All print type(exc).__name__ + source label, never str(exc)/URL/topic. (conf 0.95)
- CONFIRMED: allow-list mechanical at _classify_reply_payload — non-match yields static '(unrecognized reply ignored)', raw adversarial text never reaches stdout. Open free-text mode surfaces raw text by design, correctly disclosed in ADR Consequences. (conf 0.90)
- CONFIRMED: URL-injection closed on all argv/env paths (validate_topic/server/since before interpolation).
- F1 (Medium advisory, conf 0.82): ask_developer.py:130-135 fetch_reply (and ask()) return raw out-of-band text with no in-function allow-list and no docstring disclosure of the untrusted-reply invariant. The one real caller (distribute.md) does its own allow-list check, so not a current exploit — but a silent trap for future callers. Fix: add a Returns note stating the text is UNTRUSTED and the caller MUST validate against a fixed allow-list; optionally add an optional choices= param mirroring collab_loop.check.
- F2 (Low advisory, conf 0.75): poll() since=str(int(time.time())) at collab_loop.py:390 is not run through validate_since (safe by construction — internally generated, not user-supplied). Add a one-line comment to prevent a future refactor turning it into an injection gap.

---

## Turn 3 — qa-specialist (proposal)
*2026-05-26T16:21:02.798724+00:00 | confidence: 0.91*
*tags: qa, testing, coverage:91.7, tests:111-pass, verdict:approve-with-changes, blocking:0, advisory:3*

Verdict: APPROVE-WITH-CHANGES (confidence 0.91). Ran the suite: 111 passed (collab_loop 61 + notify 33 + ask_developer 17), 0 failed; regression marker run 3 passed; combined coverage 91.7% (>80% gate). All 17 legacy ask_developer tests green after the shim refactor.
- CONFIRMED: R4 pure seams all covered incl. the load-bearing whitespace-only-title boundary; never-print-topic regressions on BOTH error branches assert slug-absent AND a WARN still prints; ASCII-title regression asserts the Title header is latin-1-encodable; dedup-across-both-topics uses a ==1 count assertion; ask payload (buttons->reply topic, body==label, <=3 cap) tested; _classify_reply_payload miss asserts adversarial text ABSENT (correct boundary assertion). R8 AC mapping honored.
- VERIFIED: all 3 regression tests would fail under the old buggy code (str(exc)[:120] leak x2; UnicodeEncodeError).
- F1 (advisory, 0.75): match_choice has no empty-choices-list test (covered transitively via _classify_reply_payload open-mode).
- F2 (advisory, 0.72): ask error-path test asserts '(ask)' label but not the exception type-name explicitly (weaker than the _http_get regression pattern).
- F3 (advisory, 0.85): main() poll-mode dispatch (lines 478-479) is untested — only say/ask/check/config-failure covered. Add test_poll_mode_dispatches_to_poll (~3 lines). Most worthwhile of the three.
- Isolation/determinism sound (injected sleep/emit_fn/max_iterations; no live network; monkeypatch env).

---

## Turn 4 — architecture-consultant (proposal)
*2026-05-26T16:21:02.867650+00:00 | confidence: 0.88*
*tags: architecture, boundaries, shim, adr-fidelity, verdict:approve-with-changes, blocking:0, advisory:0, info:3*

Verdict: APPROVE-WITH-CHANGES (confidence 0.88). Textbook module-boundary consolidation; matches ADR-0019 + R1-R8 with high fidelity.
- CONFIRMED: dependency chain notify <- collab_loop <- ask_developer is acyclic (read imports directly; the only 'from scripts.notify' in notify.py is a docstring example). No reimplementation: resolve_config calls notify validators; ask_developer delegates resolve_config + parse_ntfy_stream and keeps ONLY its single-topic echo-by-title filter. sys.path shims are idempotent, no cycle.
- CONFIRMED: R4 pure seams genuinely pure; check no longer inlines _emit's parse (the specific R4 duplication concern is gone — both poll and check consume _iter_replies/classify_message). The one mutation (seen in _iter_replies) is correctly an impure helper, documented.
- CONFIRMED: shim preserves observable behavior (signatures, 1h timeout, echo filter, errors-as-no-reply); distribute.md:183-203 branches only on validated token. Steward-gate tier decision (skill + always-on invariant, no async_collaboration.md rule) is consistent with what shipped (Principle #8 + ADR-0016).
- Function length/nesting/magic-numbers/docstrings all satisfy REVIEW.md 1-4,21-23.
- F1 (Info): SPEC R3 still says 'in the rule' but ADR moved enforcement to code+invariant — intentional & traced in the ADR; optional one-line superseding note in the spec for self-consistency.
- F2 (Info): confirm the boundary tests (raw-text-never-surfaced) carry the regression marker.
- F3 (Info): validate_since '^\d+[smhd]?$' is the union of R6's two alternatives — acceptable simplification within R6's safety envelope.

---

## Turn 5 — docs-knowledge (proposal)
*2026-05-26T16:21:02.950809+00:00 | confidence: 0.92*
*tags: docs, knowledge, doc-sync, adr-quality, verdict:approve-with-changes, blocking:0, advisory:1*

Verdict: APPROVE-WITH-CHANGES (confidence 0.92). Knowledge chain complete & resolvable (DISC-003910 spec-review -> SPEC -> DISC-055231 build -> ADR-0019 -> ledger -> skill -> CLAUDE.md invariant). ADR-0019 is high-quality (all sections, Steward-gate tier decision recorded with rationale/confidence/risk). collaborating-async skill self-contained, correctly states allow-list is an always-on invariant (not duplicated), flags the ask_developer free-text limitation. CLAUDE.md invariant extension + Rules Index addition precise. Both regression-ledger entries well-formed with verified test refs.
- F1 (advisory, 0.95): diviner-dojo presentation line 1914 still reads '17 on-demand skills' — not bumped by this change's doc-sync. (Facilitator verification refined the target: see facilitator verification event.)
- F2 (pre-existing, out of scope): FRAMEWORK_SPECIFICATION frontmatter v3.5 vs body 'v3.4'; diviner-dojo '16 Commands'/'17 slash commands' vs 23 actual — all pre-existing, NOT introduced by this change.
- Note (advisory, echoes architecture F2): TestResolveConfig::test_error_message_never_contains_topic_value is not tagged @pytest.mark.regression though R5 framed it as a regression guard.

---

## Turn 6 — facilitator (critique)
*2026-05-26T16:21:19.604404+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 9 verified, 1 refined, 0 discarded.

VERIFIED true:
- qa test counts: independently ran the suite -> 111 passed (61+33+17), 0 failed, in 0.13s. Matches.
- security never-print-topic trace: confirmed every error path in collab_loop.py / notify.py / ask_developer.py prints type(exc).__name__ + source label, never str(exc)/URL/topic.
- security F1: ask_developer.py:130-136 fetch_reply returns raw body; ask() returns raw reply; no in-function allow-list, no docstring disclosure. VERIFIED.
- security F2: collab_loop.py:390 poll since not validated (safe by construction). VERIFIED.
- qa F1/F3: TestMatchChoice (no empty-list case) + TestMain (no poll-mode dispatch test) VERIFIED against tests/test_collab_loop.py.
- arch: dependency chain acyclic + no reimplementation + check no longer inlines _emit parse. VERIFIED by reading imports + seams.
- ledger entries + test refs exist. VERIFIED.
- docs/arch note: TestResolveConfig::test_error_message_never_contains_topic_value lacks @pytest.mark.regression. VERIFIED.

REFINED (docs-knowledge F1 — skill count): docs-knowledge recommended bumping diviner-dojo '17' -> '18'. Verification against HEAD shows the true target is 19, not 18: HEAD had 18 skill DIRS but docs said '17' (pre-existing -1 undercount). This branch adds collaborating-async (untracked) -> 19 actual dirs. The doc-sync bumped FRAMEWORK_SPECIFICATION + how-to-use 17->18 (still -1 vs the real 19) and folded an ADR-0019 skill into the 'ADR-0016 relocated' bucket (6+12=18 != 19). diviner-dojo line 1914 stayed at 17 (-2). Honest resolution: the off-by-one is PRE-EXISTING (carried forward), but since this change edits exactly the skill-count lines, reconciling all four to 19 is the right cheap fix; at minimum bump diviner-dojo so it isn't a double-straggler. Non-blocking either way.

---

## Turn 7 — facilitator (synthesis)
*2026-05-26T16:22:09.458605+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:10, speculative:3, verdict:approve-with-changes, model-tiers:facilitator-opus;specialists-default-medium*

## Request Context
- What was requested: /review the async ntfy collaboration loop on branch feat/async-collab-loop; address blocking findings then (later) education gate + commit.
- Files/scope: scripts/collab_loop.py (new), ask_developer.py (shim), notify.py (ascii guard + log fix), tests/test_collab_loop.py (new), tests/test_notify.py, .claude/skills/collaborating-async/SKILL.md, CLAUDE.md, ADR-0019, SPEC-20260525-233208.
- Developer-stated motivation: autonomous agent keeps building while developer is AFK, answering only gating decisions via one-tap phone buttons.
- Explicit constraints: confirm allow-list enforced in code at poll/check boundary; never-print-topic on all error paths; ask_developer shim keeps 17 tests green; ASCII-title guard.

VERDICT: approve-with-changes (confidence 0.90). ZERO blocking findings — every finding is advisory/info. The four developer-named constraints are all CONFIRMED met (allow-list mechanical at _classify_reply_payload; never-print-topic exhaustively traced; 111 tests pass incl. 17 legacy ask_developer; ASCII guard closed on both paths).

Panel + confidence: security-specialist 0.91, qa-specialist 0.91, architecture-consultant 0.88, docs-knowledge 0.92.

Top recommended (cheap, high-value, non-blocking): (1) security F1 — disclose untrusted-reply invariant in ask_developer fetch_reply/ask docstrings (future-caller trap); (2) docs — reconcile skill count to the true 19 across synced docs (diviner-dojo line 1914 '17', FRAMEWORK_SPECIFICATION + how-to-use '18'); (3) qa F3 — add test_poll_mode_dispatches_to_poll (~3 lines, only untested dispatch branch).

Confidence annotation: 3 findings in speculative section (conf < 0.80): security F2 (0.75 poll-since comment), qa F1 (0.75 match_choice empty-list test), qa F2 (0.72 ask-error type-name assertion). 0 unscored (architecture's 3 are Info-level under overall 0.88).

Finding verification: 9 verified, 1 refined (skill-count target is 19 not 18), 0 discarded.

Model tiers: facilitator:opus (exempt); security-specialist/qa-specialist/architecture-consultant/docs-knowledge ran at definition-default tiers under medium (default) cost routing — not overridden.

Education gate: recommended (medium-risk framework capability crossing a security trust boundary) — /walkthrough + /quiz on scripts/collab_loop.py, Tier 2.

---

## Turn 8 — facilitator (evidence)
*2026-05-26T16:23:47.341210+00:00 | confidence: 0.8*
*tags: reflections-deferred, self-healing-skipped*

Specialist reflections (Step 7c) DEFERRED for cost (non-blocking per /review protocol; consistent with prior sessions). Critiques are fully captured in the proposal + verification events above. Self-healing recurring-pattern query (Step 7a) skipped: v_rule_of_three view column-name mismatch raised IndexError (best-effort step, latent bug — query expects pattern_key/sighting_count columns the view does not expose).

---
