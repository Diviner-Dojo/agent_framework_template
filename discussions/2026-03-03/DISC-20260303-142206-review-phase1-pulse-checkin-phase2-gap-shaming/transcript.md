---
discussion_id: DISC-20260303-142206-review-phase1-pulse-checkin-phase2-gap-shaming
started: 2026-03-03T14:22:25.212915+00:00
ended: 2026-03-03T14:37:34.570034+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 12
---

# Discussion: DISC-20260303-142206-review-phase1-pulse-checkin-phase2-gap-shaming

## Turn 1 — facilitator (evidence)
*2026-03-03T14:22:25.212915+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Review Phase 1 (Pulse Check-In) and Phase 2A/B (gap-shaming removal, recovery flow) implementation across 15 files before committing to develop/adhd-roadmap
- **Files/scope**: lib/database/daos/questionnaire_dao.dart, lib/services/checkin_score_service.dart, lib/services/questionnaire_defaults.dart, lib/services/numeric_parser_service.dart, lib/providers/questionnaire_providers.dart, lib/ui/widgets/pulse_check_in_summary.dart, lib/ui/widgets/pulse_check_in_widget.dart, lib/database/tables.dart, lib/database/app_database.dart, lib/layers/claude_api_layer.dart, lib/layers/local_llm_layer.dart, lib/layers/rule_based_layer.dart, lib/ui/screens/journal_session_screen.dart, lib/ui/screens/session_detail_screen.dart, lib/ui/screens/session_list_screen.dart
- **Developer-stated motivation**: ADHD Roadmap Phase 1 — 6-item Pulse Check-In questionnaire with composite score, text-mode slider UI, voice-mode TTS/STT flow. Phase 2A removes gap-shaming context injection from all AI layers. Phase 2B adds non-shaming recovery banner after 3+ day gap (computed silently, no mention of gap duration).
- **Explicit constraints**: Clinical UX constraints from CLAUDE.md — never mention missed days/gaps/absence duration, no streaks, reminders must not escalate, AI uses epistemic humility framing. ADHD-informed UX design.

---

## Turn 2 — architecture-consultant (proposal)
*2026-03-03T14:28:11.248931+00:00 | confidence: 0.87*
*tags: architecture, round1*

## Architecture Review — Phase 1 Pulse Check-In + Phase 2A/B

**Verdict: APPROVE-WITH-CHANGES** | Confidence: 0.87

### Alignment
Implementation aligns well with ADR-0032 intent. CheckInNotifier boundary ('SessionNotifier NOT extended') correctly respected. N+1 avoidance via IN-clause in getAllResponsesForSession is good. Phase 2A gap-shaming removal is thorough across all three conversation layers.

### Blocking Finding
**F1 — _NumericParserAdapter Reimplements NumericParserService (Duplicated Logic)**
- Location: lib/providers/questionnaire_providers.dart:424-477
- _NumericParserAdapter duplicates numeric parsing from scratch (53 lines) rather than importing NumericParserService. The comment claims circular import concern but no circular dependency exists. The adapter is a SUBSET of NumericParserService — it lacks decimal rejection, explicit skip detection, compound word handling ('twenty one'→21), and STT homophone correction ('too'→2, 'ate'→8). Voice users parsing word-form inputs will get different behavior than text users.
- Fix:  — one line. Update handleVoiceAnswer to call parser.parse() directly.

### Advisory Findings
**F2** — Two bare  blocks in _speakAcknowledgement and _acknowledgeOrchestrator. Coding standards require specific exception types. Change to .

**F3** — _isRecoveryBannerDismissed is widget-local bool. Banner reappears on every navigation cycle back to list screen. Upgrade to StateProvider or SharedPreferences in a future iteration. Advisory for Phase 2B scope.

**F4** — _maybeStartCheckIn postFrameCallback timing: assessed safe. Async window during template load is negligible; text input is hidden while isActive=false.

**F5 (Medium)** — ADR-0032 schema diverges from as-built (questionnaire_items vs questionnaire_questions, template-level scale vs per-item, normalized CheckInAnswers vs embedded rows). ADR status is 'proposed'. Should be updated to 'accepted' with implementation notes before merge.

**F6** — user_checkin_config absent from v10 migration (intentional deferral to Task 8/schema v11). Confirm Task 8 uses v11.

**F7** — Migration  pattern is correct per existing v2-v9 chain. Verified.

**F8** — Clinical UX compliance: gap-shaming removal complete and consistent across all three layers. Recovery banner never reveals duration. Closing copy ('Saved. That\'s enough.') is non-evaluative. Compliant.

---

## Turn 3 — security-specialist (proposal)
*2026-03-03T14:28:31.962633+00:00 | confidence: 0.91*
*tags: security, round1*

## Security Review — Phase 1 Pulse Check-In + Phase 2A/B

**Verdict: APPROVE-WITH-ADVISORY-CHANGES** | Confidence: 0.91

No blocking security findings. All new code uses drift type-safe API; no raw SQL string interpolation; atomic transaction for response+answers; health data boundaries correctly scoped to local-only SQLite; no remote attack surface introduced.

### Advisory Findings

**SF1 (Medium)** — Unencrypted health data. Mental health time-series data (mood, anxiety, energy, focus, emotion regulation, sleep) stored in plaintext SQLite. android:allowBackup=false reduces most common extraction vector. Phase 4 SQLCipher encryption planned. Finding: escalate from 'planned' to 'scheduled' — add binding note to ADR-0032. Not blocking given documented known limitation and local-only Phase 1 posture.

**SF2 (Low) — syncStatus inline literal at write site**
questionnaire_providers.dart line 352 writes syncStatus: const Value('PENDING') directly rather than using CheckInSyncStatus.pending constant defined in questionnaire_dao.dart. One-line fix prevents future typo-introduced orphaned records. Should be fixed before sync implementation begins.

**SF3 (Low)** — AppLogger ring buffer copied to clipboard via diagnostics screen. No check-in health values currently logged, but voice acknowledgement 'Got it, VALUE.' is a TTS path near logging infrastructure. Establish code review note: CheckInNotifier methods are health-data paths and must not log item values or composite scores.

**SF4 (Low)** — WHO-5 sleep item ships under CC BY-NC-SA 3.0 with no in-app attribution UI. licenseInfo field stored but never displayed. Pre-distribution gate required: add About/Licenses screen or replace item before commercial distribution.

**SF5 (Low) — Missing UNIQUE constraint on (response_id, item_id)**
CheckInAnswers table has no database-level uniqueness enforcement on (response_id, item_id). Application-level invariant documented in comment but not enforced. A retry or race condition could insert duplicate answers, silently inflating composite scores. Add unique index before trend view is built on top of this data.

### Trust Boundary Assessment
- User input -> NumericParserService: well-protected (range/type validation)
- CheckInNotifier -> QuestionnaireDao -> SQLite: drift type-safe throughout, no injection
- SQLite -> UI: no user-controlled content rendered as question text; score via toStringAsFixed safe
- No health data crosses network in Phase 1 (syncStatus permanently PENDING)

---

## Turn 4 — qa-specialist (proposal)
*2026-03-03T14:28:57.465227+00:00 | confidence: 0.88*
*tags: qa, round1*

## QA Review — Phase 1 Pulse Check-In + Phase 2A/B

**Verdict: REQUEST-CHANGES** | Confidence: 0.88

Two blocking findings. Test coverage for new production features is solid on happy paths but has critical gaps on regression tagging and the untested Phase 2B banner.

### BLOCKING Findings

**QF1 (High) — LLM-Layer Gap Removal Regression Not Tagged**
gap_shaming_removal_test.dart covers RuleBasedLayer only and is tagged @Tags(['regression']). local_llm_layer_test.dart Phase 2A tests (lines 118-154) are NOT tagged. No regression-ledger entry exists for the gap-shaming removal behavioral change. Required by commit protocol Step 1.5 and testing_requirements.md.
Fix: Add @Tags(['regression']) library annotation to local_llm_layer_test.dart OR extract Phase 2A tests into a second regression file. Add ledger entry to memory/bugs/regression-ledger.md.

**QF2 (High) — Phase 2B Recovery Banner Entirely Untested**
_isRecoveryBannerDismissed state, daysSinceLast >= 3 condition, dismiss paths, CTA button — all live production code with zero widget test coverage. ADHD clinical UX feature (non-shaming recovery flow) — a regression here would silently re-introduce problematic UI.
Fix: Add widget tests to test/ui/session_list_screen_test.dart: (1) banner shown when session > 3 days ago, (2) dismissed by close button, (3) dismissed by Just browse, (4) not shown when gap < 3 days.

### Advisory Findings

**QF3 (Medium)** — _NumericParserAdapter in providers file is a private reimplementation of NumericParserService (no circular import actually exists — the claim in the comment is incorrect). handleVoiceAnswer word-form parsing is exercised only through excluded integration tests. Either replace adapter with NumericParserService import or add unit test for handleVoiceAnswer with mocked TTS.

**QF4 (Medium)** — No FK constraint test: no test verifies that saveCheckInResponse fails when sessionId does not exist in journal_sessions. Confirm whether drift in-memory NativeDatabase enables FK enforcement by default.

**QF5 (Medium)** — NumericParserService missing STT homophone tests: 'ate'->8, 'too'->2, 'twenty one'->21 (compound word), and 'nein'->9 (in-range on 1-10) are all untested production paths.

**QF6 (Low)** — migration_v6_test.dart test named 'session_id index exists on check_in_responses' does not actually verify index existence — only tests null lookup. Rename to match what is asserted.

**QF7 (Low)** — flagParseError on inactive state test asserts returnsNormally but does not assert the resulting state value of lastParseError. Strengthen assertion.

### Strengths
- all-skipped save suppression: correctly asserts isSaved=false, compositeScore=null, isActive=false
- Idempotency coverage: 3 distinct variants
- Acceptance criteria test: closeTo(68.5, 0.2) — correct tolerance, correct spec value
- gap_shaming_removal_test.dart regression tag correctly applied with anti-deletion warning
- check_in_notifier_test uses real DAOs with in-memory DB — avoids over-mocking

---

## Turn 5 — independent-perspective (proposal)
*2026-03-03T14:29:25.141808+00:00 | confidence: 0.82*
*tags: independent, round1*

## Independent Perspective — Phase 1 + Phase 2A/B

**Verdict: REQUEST-CHANGES** | Confidence: 0.82

Surfacing hidden assumptions and constraint violations that may not be visible from within the implementation frame.

### BLOCKING Findings

**IB1 — Recovery Banner Implies Gap Awareness (ADHD Clinical UX Violation)**
The banner exists IFF daysSinceLast >= 3. The user does not see the number, but the banner's conditional existence communicates temporal tracking non-verbally. CLAUDE.md says 'not even implicitly.' A user who journals every 5 days will see the recovery banner on every session — it becomes a Pavlovian cue for 'I was away.' The constraint is violated by the trigger mechanism, not the copy.
Fix: Decouple trigger from gap detection. Show the banner based on session count (e.g., first session of the day) or randomly (10-25% of opens). 'Good to see you' becomes always true rather than conditionally true after absence.

**IB2 — Widget-Local Dismissal Causes Banner Re-escalation**
_isRecoveryBannerDismissed is widget-local bool. A user who dismisses and navigates Back to the list will see the banner again immediately. CLAUDE.md: 'Reminders must not escalate after dismissal.' This is a direct constraint violation, not an edge case.
Fix (5-line): Persist dismissal for current calendar day using SharedPreferences or app-level Riverpod StateProvider. Widget-local state is insufficient for a dismissible reminder.

**IB3 — ADR-0032 Status 'proposed' But Implementation Deviates Significantly**
ADR-0032 describes questionnaire_questions (actual: questionnaire_items), per-item scaleMin/scaleMax (actual: template-level), embedded rawValue in checkin_responses (actual: normalized CheckInAnswers table), user_checkin_config in v10 (actual: deferred). Status is 'proposed' — not 'accepted'. An ADR in proposed status describing a schema materially different from the implementation violates CLAUDE.md Principle 1 (every decision must be traceable). Must be updated to 'accepted' with as-built schema before merge.

### Advisory Findings

**IA1** — Partial score displays as XX/100 without incompleteness signal. User answering 1 of 6 items sees '100/100'. Psychometrically ambiguous. Consider suppressing score when fewer than 4 items answered, or displaying '~69/100 (partial)'.

**IA2** — v9->v10 migration not wrapped in explicit transaction. Mid-migration crash could leave schemaVersion=10 with missing tables — boot loop on next launch. Wrap in database.transaction().

**IA3** — 3-day recovery banner threshold has no cited evidence basis in referenced instruments (EMA, WHO-5, GAD-2). For weekly journalers, fires every session. Mark as engineering heuristic pending user research.

**IA4** — WHO-5 sleep item ships unconditionally. No enforcement gate prevents release without license filing. Consider runtime feature flag defaulting to false.

### Hidden Assumptions
A1: Absence of gap number is sufficient to avoid implicit shaming (FALSE — banner presence communicates tracking)
A2: Users navigate linearly (FALSE — Back navigation creates re-escalation)
A3: 3-day threshold is meaningful (UNVERIFIED — no evidence basis)
A4: Partial denominator produces epistemically valid '69/100' (QUESTIONABLE — user interprets as complete score)
A5: ADR describes as-built (FALSE — material divergence)
A6: Migration is crash-safe without explicit transaction (UNVERIFIED)

---

## Turn 6 — architecture-consultant (critique)
*2026-03-03T14:31:38.522658+00:00 | confidence: 0.91*
*replying to turn 2*
*tags: architecture, round2*

## Round 2 — Architecture-Consultant Revisions

All three contested findings revised to BLOCKING after re-examination.

**IB1: REVISE to blocking.** My Round 1 analysis focused on banner *content* — copy is safe. Independent-perspective targets a different layer: the banner's *conditional existence* is the signal. CLAUDE.md 'not even implicitly' was written to cover exactly this — things that communicate gap awareness through conditional presence. A user who journals irregularly will pattern-match banner=I was away. Two compliant alternatives: (1) show banner universally (every session, not gap-conditioned), or (2) remove banner and surface Quick Check-In via existing FAB long-press.

**IB2: REVISE to blocking.** Widget-local _isRecoveryBannerDismissed resets on widget rebuild (orientation, theme, Navigator rebuild scenarios). 'Reminders must not escalate after dismissal' — reappearing after explicit dismiss is escalation. Fix: Riverpod StateProvider scoped to app session, or SharedPreferences with date key.

**IB3: REVISE to blocking.** ADR-0032 status 'proposed' describes a materially different schema (questionnaire_questions vs questionnaire_items, per-item scale vs template-scale, embedded rawValue vs normalized CheckInAnswers, user_checkin_config in v10 vs deferred). CLAUDE.md Principle 1: every decision must be traceable. A developer reading ADR-0032 would implement a different schema. Must be updated to 'accepted' with as-built schema before merge.

---

## Turn 7 — qa-specialist (critique)
*2026-03-03T14:31:47.343326+00:00 | confidence: 0.91*
*replying to turn 4*
*tags: qa, round2*

## Round 2 — QA-Specialist Revisions

**QF3: REVISE to blocking.** _NumericParserAdapter at providers:424-477 is missing decimal rejection, STT homophones (too/for/ate/won/nein), compound word forms (twenty one), and numbers 11-100. The circular-import claim in the comment is incorrect — NumericParserService is a stateless pure service with no Riverpod dependencies. Voice-mode users receive silently wrong null results for inputs text-mode handles correctly. Silent parsing divergence between input modes is behavioral correctness, not style. Upgrading to blocking.

**QF1 and QF2: CONFIRM both stand.** QF1 (missing regression tag) is a documented project requirement per testing_requirements.md. QF2 (recovery banner untested) stands — and given IB1/IB2 being upgraded to blocking, QF2 is even more critical: the banner needs design fixes AND tests.

---

## Turn 8 — facilitator (synthesis)
*2026-03-03T14:32:32.039676+00:00 | confidence: 0.89*
*tags: blocking:6, advisory:10*

## Request Context
- **What was requested**: Review Phase 1 (Pulse Check-In) and Phase 2A/B (gap-shaming removal, recovery banner) implementation across 15 files before committing to develop/adhd-roadmap
- **Files/scope**: questionnaire_dao.dart, checkin_score_service.dart, questionnaire_defaults.dart, numeric_parser_service.dart, questionnaire_providers.dart, pulse_check_in_summary.dart, pulse_check_in_widget.dart, tables.dart, app_database.dart, claude_api_layer.dart, local_llm_layer.dart, rule_based_layer.dart, journal_session_screen.dart, session_detail_screen.dart, session_list_screen.dart
- **Developer-stated motivation**: ADHD Roadmap Phase 1 — Pulse Check-In questionnaire with composite score. Phase 2A removes gap-shaming from AI layers. Phase 2B adds non-shaming recovery banner.
- **Explicit constraints**: CLAUDE.md clinical UX — never mention gaps/absence even implicitly. Reminders must not escalate after dismissal.

## Synthesis

**Overall Verdict: REQUEST-CHANGES** — 4 blocking findings confirmed by 2+ specialists each (after round 2 revision). 10 advisory findings.

### BLOCKING FINDINGS (must be resolved before merge)

**B1 — Recovery Banner Violates 'Not Even Implicitly' Constraint** [IP-IB1, Arch-IB1-revised]
session_list_screen.dart:74-79 shows banner IFF daysSinceLast >= 3. Copy is safe but conditional existence communicates gap awareness. CLAUDE.md: 'never mention missed days, gaps, or absence duration — not even implicitly.' The banner trigger mechanism is the violation. Fix: either show banner universally (every session) or remove banner and use existing FAB long-press for Quick Check-In entry.

**B2 — Banner Dismissal Re-escalates on Back Navigation** [IP-IB2, Arch-IB2-revised]
_isRecoveryBannerDismissed is widget-local bool. Resets on navigation cycle/rebuild. CLAUDE.md: 'Reminders must not escalate after dismissal.' Fix: persist dismissal in app-level Riverpod StateProvider or SharedPreferences date key.

**B3 — _NumericParserAdapter Duplicates NumericParserService with Reduced Capability** [Arch-F1, QA-QF3-upgraded]
questionnaire_providers.dart:424-477 reimplements parsing (53 lines) missing decimal rejection, STT homophones, compound words, and numbers 11-100. Circular import claim in comment is incorrect — NumericParserService has no Riverpod deps. Voice users get silently wrong null results for inputs text-mode handles. Fix: replace with 

**B4 — LLM-Layer Gap Removal Regression Not Tagged + Missing Ledger Entry** [QA-QF1]
local_llm_layer_test.dart Phase 2A tests (lines 118-154) not tagged @Tags(['regression']). No ledger entry in memory/bugs/regression-ledger.md for Phase 2A gap-shaming removal. Required by testing_requirements.md and commit protocol Step 1.5. Fix: add library-level @Tags(['regression']) to local_llm_layer_test.dart and add ledger entry.

**B5 — ADR-0032 Status 'proposed' with Material Schema Divergence** [IP-IB3, Arch-IB3-revised]
ADR describes questionnaire_questions/per-item-scale/embedded-rawValue schema; implementation has questionnaire_items/template-scale/normalized-CheckInAnswers. Status 'proposed' on implemented and depended-upon code. CLAUDE.md Principle 1: every decision must be traceable. Fix: update ADR-0032 to status 'accepted' with as-built schema before merge.

**B6 — Phase 2B Recovery Banner Entirely Untested** [QA-QF2]
_isRecoveryBannerDismissed state, daysSinceLast >= 3 trigger, dismiss paths — zero widget tests. Note: B1/B2 require design changes to the banner; tests should be written after the design change is resolved.

### ADVISORY FINDINGS (non-blocking)

A1 [Arch-F2] — Bare catch blocks: use  per coding standards
A2 [Security-SF2] — Use CheckInSyncStatus.pending constant in _saveResponse() instead of inline 'PENDING'
A3 [Security-SF5] — Add UNIQUE constraint on (response_id, item_id) in check_in_answers before sync phase
A4 [Security-SF1] — Encryption gap: link Phase 4 SQLCipher plan formally to ADR-0032 health data section
A5 [Security-SF4] — WHO-5 CC BY-NC-SA 3.0: add attribution UI or replace item before commercial distribution
A6 [QA-QF4] — Add FK constraint negative test for nonexistent sessionId
A7 [QA-QF5] — Add STT homophone tests: 'ate'->8, 'too'->2, 'twenty one'->21
A8 [IP-IA1] — Partial score (1-of-6 items) displays as XX/100 without incompleteness signal
A9 [IP-IA2] — v9->v10 migration not wrapped in explicit transaction (mid-migration crash safety)
A10 [IP-IA3] — 3-day recovery banner threshold has no evidence basis

---

## Turn 9 — architecture-consultant (reflection)
*2026-03-03T14:37:05.556210+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

In Round 1, I focused on banner *content* — verifying the copy was non-shaming — and did not examine the banner's *conditional existence* as a signal. The 'not even implicitly' constraint in CLAUDE.md explicitly covers implicit communication, and a gap-conditioned banner is exactly that mechanism. I caught the schema divergence in F5 but initially classified it as advisory rather than blocking; it took independent-perspective to surface the Principle 1 traceability violation clearly enough to justify blocking status. I also did not independently verify the circular-import claim in the _NumericParserAdapter comment — I accepted it at face value and issued an advisory rather than probing the dependency graph first.

## Candidate Improvement Rule

When reviewing ADHD clinical UX constraints, evaluate conditional UI presence as a potential violation, not only UI copy. Any widget that renders IFF a gap/absence/streak condition is true communicates that condition non-verbally regardless of what the text says. The check should be: 'does this element's existence depend on tracking user absence?' If yes, treat as implicit gap-shaming regardless of copy safety.

## Confidence Calibration
Original: 0.87, Revised: 0.83, Delta: -0.04

---

## Turn 10 — qa-specialist (reflection)
*2026-03-03T14:37:19.308510+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

The two most significant gaps were detection failures that only surfaced in Round 2 after architecture-consultant and independent-perspective escalated. I initially classified the recovery banner's daysSinceLast >= 3 trigger and the widget-local dismissal state as advisories — both are direct, named violations of CLAUDE.md constraints. I should have recognized these as blocking on first contact with the constraint text, not required prompting from other specialists. Additionally, I noted the _NumericParserAdapter duplication as advisory in Round 1 and only upgraded it to blocking after architecture-consultant confirmed the circular import claim was false. I should have independently verified that import claim before Round 1 output.

## Candidate Improvement Rule

Clinical UX Constraint Scan Before Scoring: When any reviewed file touches greeting logic, gap detection, session history display, or reminder/banner visibility, apply a dedicated constraint checklist pass against the four named CLAUDE.md clinical UX constraints before assigning any severity. Any line that conditions UI presence on session-gap duration or resets dismissal state without persistence is a blocking violation — not a candidate for advisory classification.

## Confidence Calibration
Original: 0.91, Revised: 0.82, Delta: -0.09

---

## Turn 11 — security-specialist (reflection)
*2026-03-03T14:37:26.392130+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

The recovery banner's conditional existence as an implicit gap signal only surfaced after independent-perspective framed it as 'does this element's existence reveal temporal tracking?' The implicit-shaming analysis required thinking non-verbally, which is harder to catch when reviewing individual lines than stepping back at the system level. I also did not flag the v9-to-v10 migration's missing explicit transaction — a crash-safety risk that only independent-perspective surfaced. Next time: lead with 'what does the conditional existence of this UI element communicate?' before analyzing its copy.

## Candidate Improvement Rule

Clinical UX Constraint Check: Conditional Presence as Implicit Signal. When reviewing any UI element gated on a user behavioral metric (session gap, streak count, usage frequency), classify the trigger condition itself as a potential constraint violation — not just the copy it produces. Ask: 'Does the existence of this element reveal that temporal tracking is occurring?' If yes, treat as violation of 'not even implicitly' regardless of whether a number or label is shown.

## Confidence Calibration
Original: 0.91, Revised: 0.88, Delta: -0.03

---

## Turn 12 — independent-perspective (reflection)
*2026-03-03T14:37:34.570034+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed

Two gaps stand out on fresh examination:

Dismissal state is ephemeral and untested. The recovery banner (_isRecoveryBannerDismissed) lives in widget state. Every app relaunch after a 3-day gap re-shows the banner. The consecutiveDismissals column defined in ADR-0032/user_checkin_config is not wired here, and no tests cover banner appearance, dismissal, or re-appearance behavior.

progressLabel off-by-one at completion boundary. progressLabel returns '(currentStepIndex + 1) of (items.length)'. When currentStepIndex == items.length (isComplete), this yields '7 of 6' for a 6-item set. The widget guards on isComplete before reaching the slider branch, but the getter itself is not guarded. Any future caller reading progressLabel after completion will get an erroneous string.

## Candidate Improvement Rule

Recovery/re-engagement UI must be tested for both appearance and non-appearance with time-controlled sessions. Any widget that conditionally renders based on elapsed time since a prior event must have tests that inject a controllable DateTime and verify: (a) appears when threshold met, (b) does not appear below threshold, (c) dismissal suppresses within session, (d) persistence behavior matches spec.

## Confidence Calibration
Original: 0.72, Revised: 0.68, Delta: -0.04

---
