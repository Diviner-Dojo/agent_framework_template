---
discussion_id: DISC-20260518-054456-notification-protocol-baked-in
started: 2026-05-18T05:45:19.562480+00:00
ended: 2026-05-18T05:55:35.459825+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist, security-specialist]
total_turns: 11
---

# Discussion: DISC-20260518-054456-notification-protocol-baked-in

## Turn 1 — facilitator (evidence)
*2026-05-18T05:45:19.562480+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Bake into the framework the same ntfy two-way feedback loop the developer built in their other project (Howie Family Wiki) — outbound notify + inbound 'ask the developer' so an autonomous/stopped session can prompt the developer's phone and resume on reply.
- **Files/scope**: 4 files — scripts/ask_developer.py (new, ported verbatim from Howie with template-generic strings), tests/test_ask_developer.py (new, 17 tests passing), .claude/rules/notification_protocol.md (new), CLAUDE.md (paragraph added under Push Notifications referencing the inbound flow + rule).
- **Developer-stated motivation**: 'I want something baked into this framework' so derived projects inherit the feedback loop. Developer explicitly asked to mirror the other project's pattern verbatim (vs. designing a new polling approach) so this version is a known-working copy.
- **Explicit constraints**: Mirror the other project verbatim (single design choice the developer made via AskUserQuestion); template-generic wording (no Howie-specific PII line).

---

## Turn 2 — qa-specialist (proposal)
*2026-05-18T05:49:04.975689+00:00 | confidence: 0.84*
*tags: qa, blocking:2, advisory:4*

## QA Review: ask_developer ntfy two-way feedback loop

Test coverage is solid for fetch_reply (7 tests, all branches) and _topic_and_server (3 tests). Three genuine gaps: weak call-argument assertions in send_question, brittle time.time() call-count assumption in timeout test, and untested network-failure path in CLI.

### Finding 1 — Weak call-argument assertions in send_question tests (HIGH, conf 0.92)
Location: tests/test_ask_developer.py:59-72 (TestSendQuestion)
Both send_question tests check return value but never assert what args were passed to send_notification. A refactor that drops tags=QUESTION_TAG would pass both tests while silently breaking the echo-filter contract.
Recommendation: add mock.assert_called_once_with(question, title=QUESTION_TITLE, priority='high', tags=QUESTION_TAG).
Rule: REVIEW.md §15.

### Finding 2 — Brittle time.time() call-count assumption in timeout test (HIGH, conf 0.88)
Location: tests/test_ask_developer.py:175-191 (TestAsk.test_returns_none_on_timeout)
times = iter([1000, 1000, 9999, 9999, 9999]) — works only because the implementation makes exactly 3 calls to time.time() in a specific order. Adding any time.time() call (e.g., logging) would exhaust the iterator and raise StopIteration mid-test.
Recommendation: replace with side_effect=lambda: 9999 after first call, or use freezegun-style approach.

### Finding 3 — Untested CLI network-failure path (MEDIUM, conf 0.85)
Location: tests/test_ask_developer.py:194-217
main() lets RuntimeError from send_question propagate as exit 1, but timeout returns 2. Distinct exit-code behaviors are untested.
Recommendation: add test_main_exits_nonzero_on_network_error.

### Finding 4 — Empty-question edge case untested (MEDIUM, conf 0.76)
Location: scripts/ask_developer.py:74-93 (send_question)
send_question('') publishes empty body. Echo filter skips empty bodies — but reply still arrives. Contract is undocumented.

### Finding 5 — Dead import io / sentinel (LOW, conf 0.95)
Location: tests/test_ask_developer.py:5, 221
import io is never used; _ = io sentinel suppresses the lint warning. Carried verbatim from Howie. Remove both.

### Finding 6 — Rule's write_event.py CLI example may drift (LOW, conf 0.72)
Location: notification_protocol.md:91-96
Documented timeout-logging example references write_event.py CLI; no test guards against signature drift. Worth verifying current signature matches.

### Strengths
- fetch_reply has thorough branch coverage (echo, malformed JSON, empty bodies, network errors, non-message events)
- sleep injection in ask() is a clean testability seam
- monkeypatch usage is consistent and per-test scoped
- _fake_response helper cleanly reproduces ntfy NDJSON streaming

---

## Turn 3 — security-specialist (proposal)
*2026-05-18T05:49:22.976450+00:00 | confidence: 0.82*
*tags: security, blocking:1, advisory:3*

## Security Review: ask_developer + notification_protocol rule

Bidirectional channel over public relay; topic slug is sole access control. Outbound carries information-disclosure risk; inbound is higher risk (any party with topic can inject replies that drive agent decisions). Module is defensively coded; protocol rule's caller guidance is incomplete.

### Finding 1 — Reply text returned as unvalidated free text, caller guidance incomplete (HIGH, conf high)
OWASP: A03 Injection / A04 Insecure Design
Location: scripts/ask_developer.py (return of ask()/fetch_reply()); .claude/rules/notification_protocol.md
Attack: anyone with topic slug posts crafted reply. Agent receives plain str. Caller passing it to subprocess/eval/exec/SQL/file-path executes attacker content. Rule mentions defaults-on-timeout but does NOT explicitly prohibit passing replies to code-execution sinks.
Recommendation: rule must add explicit prohibition — 'Never pass reply text to subprocess args, eval, exec, SQL templates, file paths, or any code-execution sink. Apply allow-list validation before using reply text to select among a fixed set of options.' Optionally add choices: list[str] | None parameter to ask() that rejects out-of-list replies.

### Finding 2 — Topic slug injected into URL path without validation (MEDIUM, conf high)
OWASP: A03 (SSRF-adjacent)
Location: scripts/ask_developer.py URL construction f'{server}/{topic}/json?poll=1&since={since}'; scripts/notify.py equivalent
Attack: malicious/misconfigured .env sets NTFY_TOPIC=legitimate-topic@evil.com or NTFY_TOPIC=../../../admin — request escapes intended server.
Recommendation: validate NTFY_TOPIC against ^[a-zA-Z0-9_-]{1,64}$ before use; validate NTFY_SERVER against allowlist of trusted hostnames; reject values containing @, /, ?, %.

### Finding 3 — Echo filter bypassable by title spoofing (LOW advisory)
Location: scripts/ask_developer.py echo-filter
Attacker posts message with title != 'Claude needs input'. Filter only suppresses outbound echoes, not injections.
Recommendation: acceptable for stated purpose. For sensitive contexts, document in rule that derived projects should add nonce/HMAC: embed random token in question, require reply to include it.

### Finding 4 — Question text in cleartext to public relay — confidentiality warning buried (LOW advisory)
OWASP: A02
Location: notification_protocol.md Confidentiality section
The 'derived projects must add domain-specific exclusions' instruction is correct but a trailing note. Elevate to bold warning at section top: 'Question text is published in cleartext to ntfy.sh. Never include file paths, error messages, internal IDs, PII, or secrets.'

### Trust Boundaries
- Developer → ntfy.sh (outbound): question body effectively public to anyone with topic
- ntfy.sh → agent (inbound): HIGHEST risk; no validation at boundary; trust delegated to callers
- .env → URL constructor: env-controlled values cross into HTTP construction without validation

### Strengths
- stdlib-only design limits attack surface
- Echo filter on title correctly prevents self-action loop
- Best-effort failure posture prevents DoS-of-relay stalling autonomous execution
- Rule correctly treats topic as a secret stored in .env
- Test coverage of malformed JSON and echo filtering matches the trust surface

---

## Turn 4 — architecture-consultant (proposal)
*2026-05-18T05:49:38.844474+00:00 | confidence: 0.82*
*tags: architecture, blocking:0, advisory:4*

## Architecture Review: ntfy two-way primitive

Structural design sound — clean layering, correct dependency direction, appropriate co-location with capture pipeline scripts. Two medium findings: missing ADR for the HITL primitive, and rule references template-undefined primitives (/loop, ScheduleWakeup).

### Finding 1 — No ADR for ntfy two-way HITL coordination primitive (MEDIUM, conf moderate)
Location: docs/adr/ (absent)
Introduces HITL coordination primitive with load-bearing default-on-timeout policy, baked into framework-wide auto-loaded rule. No ADR documents why 1-hour timeout vs halt-and-write-to-BUILD_STATUS, why ntfy (vs SMS/email/webhook), why script primitive vs MCP tool. Push notifications (outbound only, v3.4) also had no ADR — this compounds the gap.
Recommendation: add ADR-NNNN-ntfy-two-way-coordination.md covering context, decision, alternatives, consequences. ~300 words.

### Finding 2 — Rule references /loop and ScheduleWakeup not in template (MEDIUM, conf moderate)
Location: .claude/rules/notification_protocol.md:37, 38, 53, 59; scripts/ask_developer.py:13
Rule cites '/loop mode' and 'ScheduleWakeup cycle' as primary use cases. Neither exists in this template (no /loop command in .claude/commands/, no ScheduleWakeup tool). These are derived-project (Howie) primitives leaking into template wording.
Recommendation: reframe generically — 'any autonomous polling loop', 'any scheduled callback', 'background tasks from cron/CI' — OR explicitly mark as derived-project extensions ('if your project defines a /loop command').

### Finding 3 — Function length clean (LOW info)
ask=30 lines, main=38, fetch_reply=30. All within 50-line guideline.

### Finding 4 — Docstring style inconsistency (LOW)
Location: scripts/ask_developer.py:74-94 (send_question), 97-127 (fetch_reply)
ask() has full Args/Returns; send_question and fetch_reply have prose-style docstrings without Args/Returns/Raises sections. 'Raises RuntimeError' in send_question is in body, not Raises: block.
Recommendation: add Google-style sections for consistency.

### Architectural Alignment Check
- CLAUDE.md 'Push Notifications' section: extension, not parallel — good
- Principle #8 (least-complex intervention first): script + rule = correct level
- Framework rule scope: opt-in by NTFY_TOPIC config (functions raise/return False without it). Derived projects without ntfy pay zero cost.
- Dependency direction: ask_developer → notify (correct — two-way composes on one-way)
- Module co-location in scripts/: appropriate alongside capture-pipeline utilities

### Strengths
- Sleep injection seam without mock framework
- Echo filter by title is elegant for round-trip on public relay
- Opt-in by NTFY_TOPIC keeps rule inert without setup
- AskUserQuestion vs ntfy disambiguation in rule is explicit and well-reasoned
- stdlib-only contract mirrors notify.py — preserves framework no-pip posture for notification subsystem

---

## Turn 5 — docs-knowledge (proposal)
*2026-05-18T05:49:56.092877+00:00 | confidence: 0.83*
*tags: docs, blocking:0, advisory:3*

## Docs/Knowledge Review: notification protocol baked into template

Rule itself is the strongest piece — well-structured, example-rich, covers triggers/AFK/echo/timeout/confidentiality. ask_developer.py module docstring matches notify.py style. CLAUDE.md paragraph is tight with correct cross-reference. Three sync/discovery gaps.

### Finding 1 — .env.example does not mention ask flow (LOW, conf 0.90)
Location: .env.example lines 13-26
Comment block under 'Push Notifications' describes NTFY_TOPIC as enabling notifications only. Derived-project developer reading setup docs gets no signal that same topic powers inbound ask flow. Rule defers to .env.example for setup but .env.example describes only half the capability.
Recommendation: add one line: '# The same NTFY_TOPIC also powers the two-way ask flow (scripts/ask_developer.py).'

### Finding 2 — FRAMEWORK_SPECIFICATION.md rule count + changelog stale (LOW, conf 0.88)
Location: docs/FRAMEWORK_SPECIFICATION.md line 1478; rules directory listing section
Changelog last records '13 rules (+1)' as of v3.4. Rules directory now has 15 (added failure_taxonomy.md + notification_protocol.md). v3.5 bump (current branch) has no changelog row.
Recommendation: add v3.5 changelog row noting new rule (now 15 rules, +2 since v3.4). Update rule count in implementation status / directory tree sections. Per framework_doc_sync.md, this is a documented sync requirement.

### Finding 3 — No ADR for ntfy two-way HITL coordination (LOW, conf 0.72)
Location: docs/adr/
Push notifications (outbound only, v3.4) added without ADR. Inbound ask flow is qualitatively different — coordination primitive with hard 1-hour blocking cap and 'proceed with documented default' contract. Rationale (vs local webhook, vs always-AskUserQuestion, vs skipping HITL) lives only in CLAUDE.md mechanics, not motivation. Template-is-the-hub: derived projects will ask 'why ntfy and not X?' with no answer.
Recommendation: ADR-0016 covering context (autonomous loops need HITL), decision (ntfy + BYOK topic + stdlib-only), alternatives (AskUserQuestion sync-only, local webhook requires setup, BUILD_STATUS too slow), consequences (public-relay confidentiality, 1-hour cap, derived projects add domain exclusions). 300 words.

### Section Name (advisory)
'Push Notifications' is underdescriptive for two-way capability. Consider 'Push Notifications and Out-of-Band Asks' or 'Developer Notifications (ntfy.sh)'. Low urgency — cross-reference to rule is findable.

### Framework-Doc-Sync Impact
Per framework_doc_sync.md, .claude/rules/ changes trigger FRAMEWORK_SPECIFICATION.md + presentation HTMLs review. Spec changelog and rule count stale (Finding 2). Presentation HTMLs likely contain rule count stat — worth checking before merge, secondary to spec.

### Strengths
- Rule's 'When NOT to Use' section explicitly names AskUserQuestion with 'last few turns' heuristic — exactly the disambiguation derived-project agents need
- Non-blocking two-call pattern (send_question/fetch_reply) is documented in both rule and module docstring
- Confidentiality section's invitation to derived projects to 'add their own domain-specific exclusions' is right Template-is-the-Hub move
- ask_developer.py docstring style consistent with notify.py
- Discovery chain CLAUDE.md → rule → script is complete and navigable; every cross-reference bidirectional except the .env.example gap

---

## Turn 6 — facilitator (critique)
*2026-05-18T05:52:39.645302+00:00 | confidence: 0.8*
*tags: finding-verification*

## Finding Verification Pass

Verified location-specific findings against actual code.

### Verified TRUE (15 of 17 findings)
- QA F1 (call-args missing in send_question tests): tests/test_ask_developer.py:59-72 confirmed no .assert_called_with()
- QA F2 (time.time iter brittleness): confirmed times=iter([1000,1000,9999,...]) pattern at line 179
- QA F3 (CLI network-failure path untested): TestMainCli only covers success + timeout
- QA F4 (empty question edge case): no empty-string test in TestSendQuestion
- QA F5 (dead 'import io' / sentinel): import io at line 5 + _ = io at line 221; io appears in NO other test code
- Sec F2 (NTFY_TOPIC URL injection): confirmed — notify.py and ask_developer.py interpolate topic into URL with no validation
- Sec F3 (echo filter title-only): confirmed — filter only checks msg.get('title') == question_title
- Sec F4 (confidentiality warning buried): confirmed — exclusion list is at section bottom
- Arch F1 / Docs F3 (no ADR for ntfy): confirmed — no ADR in docs/adr/ for notify or ask_developer
- Arch F2 (/loop and ScheduleWakeup undefined in template): VERIFIED — no /loop in .claude/commands/; ScheduleWakeup references in framework files only exist in the 3 files added by this commit (CLAUDE.md context-brief, ask_developer.py docstring, notification_protocol.md). All other references are in .claude/worktrees/external-analysis/ (third-party scout material, not template-native).
- Arch F3 (function length under 50 lines): confirmed
- Arch F4 (docstring style inconsistency): confirmed — send_question and fetch_reply lack Args/Returns/Raises sections
- Docs F1 (.env.example does not mention ask flow): confirmed — .env.example lines 13-26 describe NTFY_TOPIC for notifications only
- Docs F2 (FRAMEWORK_SPECIFICATION.md rule count stale): VERIFIED — line 1015 says 'All agents inherit 13 rule files', actual count is 15 (failure_taxonomy.md + notification_protocol.md added since); line 1478 changelog has no v3.5 row

### Inconclusive (1 finding)
- Sec F1 (rule's caller-guidance on reply text): the rule does describe replies as developer input but does not contain an explicit prohibition on passing to subprocess/eval/SQL/etc. Judgment-dependent on what counts as 'sufficient' caller guidance for a template-wide rule.

### Discarded (0 findings)
None. All location-specific findings verified.

### NEW finding promoted from verification (facilitator)
**FACILITATOR-F1 (HIGH/BLOCKING) — Rule's write_event.py example would fail if copy-pasted**
Location: .claude/rules/notification_protocol.md:91-97 (Timeout Behavior section)
The example shows: python scripts/write_event.py <discussion_id> --agent <your_agent> --intent decision --tags ... --content ...
The actual write_event.py CLI takes them as POSITIONAL args: python scripts/write_event.py <discussion_id> <agent> <intent> <content> --tags ...
A developer following the rule's timeout-logging procedure verbatim will hit argparse error 'unrecognized arguments'. The rule is auto-loaded into every session AND every derived project. The example is the only canonical timeout-recovery procedure the rule documents.
Recommendation: fix the example to match actual CLI signature (positional discussion_id, agent, intent, content; --tags as flag).

Confirmed via 'python scripts/write_event.py --help'.

---

## Turn 7 — facilitator (synthesis)
*2026-05-18T05:54:15.569000+00:00 | confidence: 0.83*
*tags: blocking:4, advisory:9, speculative:0, model-tiers:qa:sonnet+sec:sonnet+arch:opus+docs:sonnet+facil:opus*

## Request Context
- **What was requested**: Bake the ntfy two-way feedback loop (outbound notify + inbound ask) into the framework template, mirroring the developer's other project (Howie Family Wiki) so derived projects inherit it.
- **Files/scope**: scripts/ask_developer.py (new), tests/test_ask_developer.py (new, 17 passing), .claude/rules/notification_protocol.md (new, auto-loaded), CLAUDE.md (paragraph added).
- **Developer-stated motivation**: Reusable HITL primitive for autonomous workflows / ScheduleWakeup loops / AFK sessions.
- **Explicit constraints**: Mirror the other project verbatim; template-generic wording.

## Verdict: approve-with-changes

4 blocking findings before merge:
1. Rule's write_event.py CLI example is broken (named flags vs positional args). Auto-loaded rule + only canonical timeout-recovery procedure = highest-reach defect.
2. send_question tests lack call-argument assertions — refactor that drops tags= would silently break echo filter.
3. NTFY_TOPIC and NTFY_SERVER interpolated into URL without validation (SSRF-adjacent via malicious .env).
4. Rule lacks explicit caller-guidance on the untrusted-reply trust boundary — should prohibit passing replies to subprocess/eval/SQL/file-path sinks.

9 advisory improvements (test brittleness, dead import, derived-project leakage of /loop/ScheduleWakeup, .env.example sync, confidentiality warning placement, FRAMEWORK_SPECIFICATION rule count + v3.5 changelog, docstring style consistency, ADR for ntfy two-way HITL).

## Confidence Annotation
0 findings in speculative section (confidence < 0.80). 4 findings retained without per-finding confidence scores (specialist findings were group-scored). Promoted facilitator finding (F1, broken CLI example) verified mechanically via 'python scripts/write_event.py --help' — verified confidence 1.00.

## Model Tiers
qa-specialist:sonnet, security-specialist:sonnet, architecture-consultant:opus, docs-knowledge:sonnet, facilitator:opus.

## Counterfactual
F1 (broken CLI example): facilitator-found via verification, not specialist-originated — would-have-missed without the verification step.
F3 (URL validation): inherited gap from verbatim port — would-have-missed.
F4 (reply trust boundary): rule wording sounded sufficient until security lens parsed for what was NOT said — would-have-missed.
F2 (call-arg assertions): standard test pattern — would-have-caught.

Net: 3 of 4 blocking findings were would-have-missed. Verification pass added one. Report: docs/reviews/REV-20260518-054500.md

---

## Turn 8 — qa-specialist (reflection)
*2026-05-18T05:55:19.727763+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I flagged the rule example as potentially drifting but treated it as advisory. I did not verify the actual CLI signature of write_event.py before assigning severity. Had I run a quick grep against the script's argument parser, I would have confirmed the positional-vs-named mismatch immediately and classified it blocking myself.

## Candidate Improvement Rule
When a test or documentation artifact contains a shell command example (subprocess call, CLI invocation, bash snippet), cross-check it against the target script's argument parser before assigning severity. A drifted example is always at least medium; a broken one is blocking.

## Confidence Calibration
Original: 0.84, Revised: 0.76, Delta: -0.08

---

## Turn 9 — security-specialist (reflection)
*2026-05-18T05:55:24.981990+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I failed to cross-check the URL injection gap against the existing scripts/notify.py — a parallel vector in production code that was more exploitable than the rule file's guidance text. More critically, I did not consider the rule file itself as a prompt-injection surface: auto-loaded rules become part of every session's context window, meaning adversarially crafted content in a rule file could influence model behavior across all workflows, not just the notification path. That meta-level attack vector (rule-as-prompt-injection) should have been my first check, not an afterthought.

## Candidate Improvement Rule
For rule files that are auto-loaded into every session: treat the rule file's own content as a trust boundary. Verify that no user-controlled or externally-sourced string can reach the rule file at write time, and flag any rule that embeds runtime values (topics, URLs, tokens) as a potential prompt-injection staging point.

## Confidence Calibration
Original: 0.82, Revised: 0.71, Delta: -0.11

---

## Turn 10 — architecture-consultant (reflection)
*2026-05-18T05:55:30.754324+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
I caught the dangling /loop and ScheduleWakeup references but didn't go further and ask the structural question: what is the migration story? A primitive ported from a derived project arrives with assumed scaffolding (commands, agents, runtime loops). I flagged the symptom (missing referents) but didn't recommend a 'ported-primitive completeness checklist' — the rule should either (a) ship its dependencies, (b) document them as a separate prerequisite ADR, or (c) be marked experimental until the surrounding scaffolding lands. I also didn't check whether ask_developer.py had any callers in the template — orphan tooling is a drift signal I should have surfaced as a distinct finding rather than folded into the rule-reference issue.

## Candidate Improvement Rule
When reviewing a primitive ported from a derived project to the template, enumerate every named entity it references (commands, agents, scripts, runtime loops) and verify each exists in the template. Missing referents are blocking, not advisory — a primitive that documents non-existent infrastructure is a broken contract for downstream forks.

## Confidence Calibration
Original: 0.82, Revised: 0.78, Delta: -0.04

---

## Turn 11 — docs-knowledge (reflection)
*2026-05-18T05:55:35.459825+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The write_event.py CLI example inside the rule file contained a broken argument syntax. I reviewed the rule's prose, structure, and knowledge-flow implications — but I did not verify that embedded runnable examples were syntactically correct against the actual script interface. This is a knowledge-quality failure: a broken example is worse than no example. Verifying that code examples inside rules actually match the tool's interface is squarely a knowledge concern, not just a QA concern — incorrect examples corrupt the Layer 1-to-Layer 3 knowledge flow by encoding wrong patterns as authoritative.

## Candidate Improvement Rule
When reviewing any rule or documentation file that contains runnable CLI examples or code snippets, cross-reference each example's arguments and flags against the actual script or tool's current interface. A broken example is a documentation defect with blocking severity — it actively misleads the reader it was meant to help.

## Confidence Calibration
Original: 0.83, Revised: 0.70, Delta: -0.13

---
