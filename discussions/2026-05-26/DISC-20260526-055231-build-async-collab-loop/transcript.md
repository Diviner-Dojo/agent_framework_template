---
discussion_id: DISC-20260526-055231-build-async-collab-loop
started: 2026-05-26T05:52:54.278902+00:00
ended: 2026-05-26T14:45:45.711711+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, security-specialist, steward]
total_turns: 10
---

# Discussion: DISC-20260526-055231-build-async-collab-loop

## Turn 1 — facilitator (evidence)
*2026-05-26T05:52:54.278902+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Build the async human-in-the-loop ntfy collaboration loop per SPEC-20260525-233208 (status: reviewed). Implement the binding /plan resolutions R1-R8. Stage only my own files (tree has unrelated distribute work).
- **Files/scope**: scripts/collab_loop.py (new canonical two-way tool); scripts/ask_developer.py (demote to thin single-topic shim reusing collab_loop's pure parse); scripts/notify.py (ASCII-title sanitize guard); .claude/rules/async_collaboration.md (new auto-loaded rule w/ mandatory allow-list clause); .env.example (reply topic); committing-changes + notifying-the-developer skills; docs/adr/ADR-0019; tests/test_collab_loop.py; 2 presentation HTMLs (doc sync); regression-ledger entries.
- **Developer-stated motivation**: Autonomous agent works for hours AFK, surfacing only gating decisions to the phone with one-tap answers; unattended multi-step build proceeds without skipping workflow steps.
- **Explicit constraints**: R1 collab_loop is the single two-way tool, ask_developer becomes a thin shim (preserves its one caller distribute.md + 17 tests). R2 validate topic+server+reply_topic, reuse notify root-relative .env, fail closed never print topic. R3 allow-list clause mandatory in rule (matched label not raw text). R4 pure-function seams. R5 never-print-topic regression tests (type(e).__name__ not str(e)). R6 ASCII-title guard at notify layer. R7 ADR-0019. Stdlib-only. Stage only my own files.

---

## Turn 2 — facilitator (proposal)
*2026-05-26T05:53:05.823154+00:00 | confidence: 0.8*
*tags: build-plan*

Build plan (11 tasks). CORE (checkpoint fires — security-relevant + new module + reconciliation):
T1 scripts/collab_loop.py — canonical two-way loop: ask/say/poll/check + pure seams resolve_config()/parse_ntfy_stream()/classify_message()/parse_reply_text(); imports validate_topic/validate_server/send_notification/_load_env from notify (R1,R2,R4). say delegates to notify.send_notification (shared primitive); ask uses ntfy JSON-publish for <=3 action buttons.
T2 scripts/ask_developer.py — demote to thin single-topic legacy shim; fetch_reply reuses collab_loop.parse_ntfy_stream (removes the genuine parse duplication); public API (ask/send_question/fetch_reply/_topic_and_server/main) preserved so distribute.md + 17 tests stay green (R1).
T3 scripts/notify.py — ensure_ascii_title() sanitize guard applied to header Title; preserves never-raises contract (R6).
T4 .claude/rules/async_collaboration.md — auto-loaded; Part 2 protocols + MANDATORY allow-list clause (matched label not raw reply text) + Part 3 loop-mechanics lessons + Async-loop-state convention (R3).
EXEMPT (docs/tests/config):
T5 .env.example reply-topic note. T6 committing-changes skill: Lesson 11 (stage-only-your-files/never git add -A). T7 notifying-the-developer skill: collab_loop two-way ref + ASCII-title + re-point. T8 docs/adr/ADR-0019 (R7). T9 tests/test_collab_loop.py (~20 blocking + advisory; R5 regression x2; all 17 ask_developer tests stay green). T10 regression-ledger entries. T11 doc sync: diviner-dojo + how-to-use HTMLs.
NOTE: distribute.md NOT edited (untracked/not-mine; shim preserves its ask() import). BUILD_STATUS.md NOT edited (pre-existing dirty/not-mine); Async-loop-state convention documented in the rule instead.

---

## Turn 3 — facilitator (evidence)
*2026-05-26T05:55:53.840819+00:00 | confidence: 0.8*
*tags: prior-art, enrichment*

## Pre-build enrichment (prior art)
- regression-ledger.md:34 — src/context_sensor.py UnicodeEncodeError (2026-05-23, Schema/Serialization Drift): a non-ASCII char (U+26A0) in a statusLine string crashed the hook on Windows cp1252. Fix pattern: ASCII-only display; emoji safe ONLY when emitted via json.dumps(ensure_ascii=True). DIRECTLY informs R6: collab_loop.ask puts title in a json.dumps payload (latin-1-safe); ONLY notify.send_notification's HTTP-header Title path needs the ASCII sanitize guard. context_sensor's test_display_is_ascii_encodable is the precedent test shape.
- ADR-0018 (model-aware-session-wrapup): structural precedent — one coverage-measured core module owns the logic, thin wrappers, pure-function seams. ADR-0019 mirrors it.
- Ledger format caveat: quality_gate._parse_regression_ledger parses every pipe row in the FIXED-BUG table as 6-col (cell[4]=test path). New regression entries go there with a real test path; the Known-Broken section must NOT get new rows (spurious gate failure).
- No known-broken approach for ntfy two-way loops; novel-domain build.

---

## Turn 4 — security-specialist (critique)
*2026-05-26T06:07:46.699235+00:00 | confidence: 0.88*
*tags: checkpoint, task-core*

## Checkpoint Round 1: REVISE (confidence 0.88)
F1 [Medium, BLOCKING, A03/A04] Allow-list (R3) is articulated in the rule but NOT enforced in code. _emit (collab_loop.py:264) and check (:393) print raw reply text verbatim (REPLY:/ANSWER:). An attacker with the slug can publish text that masquerades as a developer choice or carries prompt-injection into the agent's stdout/context. Fix at the boundary: compare trimmed reply to the outstanding question's allow-list; emit a canonical matched label on hit and a non-revealing 'ignored' marker on miss (do NOT print the raw invalid text). Encode open-free-text mode distinctly so consumers know which mode applies. Mechanical, stdlib-only.
F2 [Low, A02] notify.py:191-194 except branches log str(e) which (for URLError) embeds the full URL incl. the topic slug at DEBUG. Fix: log type(e).__name__ only (mirror collab_loop's pattern).
STRENGTHS: R5 never-print-topic implemented rigorously in collab_loop (type(exc).__name__ + source label, never str(exc) or URL; resolve_config messages reference env-var names/patterns only). validate_since gates the only argv->URL value. ensure_ascii_title at the correct header-construction point. json.dumps body safe. Rule articulation of trust boundary is clear — the gap is enforcement, not wording.

---

## Turn 5 — architecture-consultant (critique)
*2026-05-26T06:07:56.947577+00:00 | confidence: 0.88*
*tags: checkpoint, task-core*

## Checkpoint Round 1: REVISE (confidence 0.88)
ALIGNMENT: dependency direction notify<-collab_loop<-ask_developer, no cycle. Pure seams (resolve_config/parse_ntfy_stream/classify_message/parse_reply_text) are genuine de-duplication; ask_developer.fetch_reply delegates parse and adds only its single-topic echo-by-title filter (legitimately shim-local). Reconciliation is HONEST: one inbound-ask implementation, not two.
F1 [High, BLOCKING, missing-adr] ADR-0019 cited in 4 places (collab_loop.py:8, ask_developer.py:7, async_collaboration.md:2, CLAUDE.md:89) but docs/adr/ADR-0019-*.md does not exist — dangling pointers; quality_gate ADR-completeness will block. Author ADR-0019 before commit: two-topic architecture, collab_loop canonical + shim contract, notify validation as shared base, always-loaded-vs-on-demand decision.
F2 [Medium, governance] Adding async_collaboration as always-loaded edits the constitution (CLAUDE.md Rules Index) + adds permanent per-turn context cost across derived projects = framework evolution. CLAUDE.md Framework Evolution requires a Steward gate before developer approval (Principle #7). Confirm/run the gate; record the outcome in ADR-0019. R3 (allow-list must never be missed) is a credible justification for always-on over on-demand, but the trade-off vs ADR-0016 belongs explicitly in the ADR / Steward decision, not implicitly.
STRENGTHS: always-loaded cost is proportionate (rule <90 lines) and ADR-0016 itself says promote security invariants to always-on. require_reply=False shim path avoids forking validation. _http_get type-only logging is a correct deliberate choice.

---

## Turn 6 — steward (decision)
*2026-05-26T06:10:36.506274+00:00 | confidence: 0.82*
*tags: checkpoint, task-core, steward-gate, framework-evolution*

## Steward Gate: REVISE (confidence 0.82) — tier correction, not rejection
The always-loaded RULE over-pays and DUPLICATES an existing control. The untrusted-reply allow-list already lives in CLAUDE.md Always-On Invariants line 25 (loaded every turn) AND the notifying-the-developer skill. The new 88-line rule is a THIRD copy of the safety mandate bolted onto a first copy of operational protocol. Only ~10 lines (the allow-list mandate + never-print-topic) clear ADR-0016's always-on bar ('no mechanical enforcer, gates a decision before any command fires'); the ~75 lines of channel mechanics / mode table / 7 protocols / resume discipline are procedural skill content (sibling of notifying-the-developer + wrapping-up-sessions), which ADR-0016 keeps on-demand.
RECOMMENDATION:
1. Convert .claude/rules/async_collaboration.md -> .claude/skills/collaborating-async/SKILL.md (on-demand, keyword-rich description: /loop, ScheduleWakeup, brb/afk, arm/close the loop). Move channel mechanics, collab_loop mode table, Protocols 1-7, check-before-poll resume, BUILD_STATUS resume-anchor block there.
2. Do NOT add a second always-loaded rule. Extend Always-On Invariants line 25 with the two missing clauses: (a) act on the MATCHED CHOICE LABEL, never raw reply text; non-matching reply triggers NO gated action; (b) never print the topic slug incl. error paths. Point line 25 at the new skill.
3. Dedupe: skill references the invariant, doesn't restate all 4 items.
4. Preserves R3 FULLY — control is auto-loaded as invariant lines (stronger than burying in an 88-line rule), per-turn cost drops from ~88 lines to ~2.
5. Record in ADR-0019: always-on rule declined in favor of always-on invariant lines + on-demand skill (cite ADR-0016 bar + Principle #8).
GATE SEQUENCING: this REVISE requires DEVELOPER APPROVAL before the revised form goes to /review + doc sync (Principle #7). syncing-framework-docs: FRAMEWORK_SPECIFICATION skill table needs the new collaborating-async slug.

---

## Turn 7 — security-specialist (critique)
*2026-05-26T14:15:24.587206+00:00 | confidence: 0.97*
*tags: checkpoint, task-core, round-2*

## Checkpoint Round 2: APPROVE (confidence 0.97)
F1 (allow-list enforcement) RESOLVED: match_choice/_classify_reply_payload enforce the allow-list at the inbound boundary; on a miss the raw reply text is discarded before any print ('(unrecognized reply ignored)'), and a match returns the canonical allow-list label, never attacker text. poll + check thread choices through. The impersonation/injection vector (raw reply reaching agent stdout/context and influencing action) is CLOSED.
F2 (str(e) topic leak) RESOLVED: all error branches log type(e).__name__ only — notify.py (2), ask_developer.py fetch_reply, collab_loop.py _http_get (2) + ask. No str(exc)/repr(exc) path can embed the URL-encoded topic.
RESIDUAL (non-blocker): ask_developer.fetch_reply returns the raw free-text body without allow-list validation — consistent with its deprecated single-topic free-text shim design; the always-on invariant binds its callers. Worth a one-line known-limitation note in the collaborating-async skill.

---

## Turn 8 — architecture-consultant (critique)
*2026-05-26T14:15:31.915143+00:00 | confidence: 0.95*
*tags: checkpoint, task-core, round-2*

## Checkpoint Round 2: APPROVE (confidence 0.95)
F1 (ADR-0019) RESOLVED: ADR-0019 is complete + accurate — two-topic architecture, collab_loop-canonical + ask_developer shim contract with explicit dependency direction (notify <- collab_loop <- ask_developer), shared validation base, the five pure seams, and the tier decision with the Steward REVISE rationale recorded faithfully. Alternatives section closes the decision trail (incl. the rejected always-loaded-rule option).
F2 (Steward gate / tier) RESOLVED + structurally sound: async_collaboration.md confirmed deleted; Always-On Invariant line 25 now carries the matched-label + never-print-topic clauses inline (R3 always-on at ~2 lines); collaborating-async registered on-demand as the sibling of notifying-the-developer/wrapping-up-sessions; no second always-loaded rule; ADR-0016 cost model honored; the skill cross-references the invariant (correct reconciliation pattern). No dangling ADR-0019 references or structural drift. Reconciliation remains honest (one inbound-ask implementation).

---

## Turn 9 — docs-knowledge (evidence)
*2026-05-26T14:45:29.930823+00:00 | confidence: 0.8*
*tags: doc-sync, framework-evolution*

## Doc sync complete (confidence 0.96)
Synced all 3 artifacts (syncing-framework-docs), minimal/faithful, no version bump:
- FRAMEWORK_SPECIFICATION.md: skill count 17->18 (added collaborating-async row); new sub-section 'Push Notifications & Async Collaboration (ADR-0019)' (collab_loop.py 4 modes + notify.py + ask_developer shim + two-topic model + 2 always-on invariants); §15 implemented table 17->18; Appendix C directory + scripts/collab_loop.py; Document History row for ADR-0019.
- how-to-use-presentation.html: new Slide 12 'Working While You're AFK' (4-step flow, two-topic, 4 modes, security card); slides 12-15 renumbered 13-16; totalSlides 15->16; nav + progress updated; 'What You Get' 17->18 skills.
- diviner-dojo-framework-presentation.html: Slide 8 (Hooks) added 'Async Autonomy (ADR-0019)' card (no existing content modified).
PRE-EXISTING stale items (NOT changed, out of scope; flag to developer): (1) diviner-dojo Slide 7 says '16 Commands' vs 17 elsewhere; (2) FRAMEWORK_SPEC §1 body still says 'v3.4' while frontmatter says v3.5.

---

## Turn 10 — facilitator (synthesis)
*2026-05-26T14:45:45.711711+00:00 | confidence: 0.8*
*tags: build-summary, blocking:3, advisory:2*

Build complete: 11 tasks, 1 checkpoint fired (security + architecture, 2 rounds, REVISE-resolved), 0 unresolved concerns. Plus a Steward gate (framework evolution) that returned REVISE and was developer-approved.

DELIVERED:
- scripts/collab_loop.py — canonical two-way ntfy loop (ask/poll/check/say) with pure seams (resolve_config, parse_ntfy_stream, classify_message, parse_reply_text, match_choice). Allow-list enforced IN CODE at the poll/check boundary (REPLY-MATCH / REPLY-INVALID; raw adversarial text never surfaced).
- scripts/ask_developer.py — demoted to thin single-topic free-text shim delegating config+parse to collab_loop (one inbound-ask impl; 17 existing tests stay green).
- scripts/notify.py — ensure_ascii_title guard on the HTTP-header Title (never-raises preserved); except branches log type(e).__name__ only (no topic leak).
- .claude/skills/collaborating-async/ — on-demand skill (Steward REVISE: NOT an always-loaded rule). CLAUDE.md Always-On Invariant extended with matched-label + never-print-topic clauses (R3 always-on at ~2 lines vs ~88).
- docs/adr/ADR-0019 (R7); committing-changes Lesson 11 (stage-only-your-files); notifying-the-developer updated; regression-ledger +2 (topic-leak Trust Boundary Gap, ascii-title Schema/Serialization Drift); doc sync across FRAMEWORK_SPECIFICATION + 2 presentation HTMLs.

GATES: ruff clean; 111 tests pass (collab_loop 61 + notify 33 + ask_developer 17); quality gate 7/7 (coverage >=80%, 18 ADRs, 7 regression guards). BUILD_STATUS freshness WARN is intentional (not-mine dirty file; Async-loop-state convention documented in the skill).

NOT DONE (deferred): .env.example reply-topic note (blocked by protected-file guard — guidance lives in the skill); /review + commit + education gate are the next workflow steps. Spec left at status:reviewed (mark complete post-commit). Reflections from REVISE specialists deferred under context wrap-up.

CONSTRAINT HONORED: only my own files touched; distribute.md NOT edited (shim preserves its ask() import); BUILD_STATUS.md / .claude/settings.json / metrics/* / distribute work all left unstaged.

---
