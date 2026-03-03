---
spec_id: SPEC-20260302-ADHD
title: "ADHD-Informed Feature Roadmap + Pulse Check-In Questionnaire"
status: reviewed
risk_level: medium
reviewed_by: [architecture-consultant, qa-specialist, docs-knowledge]
discussion_id: DISC-20260303-043107-adhd-roadmap-spec-review
related_discussions:
  - DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture
  - DISC-20260303-042204-voice-improvements-adhd-spec-integration
required_adrs:
  - id: ADR-0031
    title: "Deepgram Nova-3 STT Integration"
    status: not-written
    blocks: "Phase 1 P1 — Deepgram streaming STT implementation"
  - id: ADR-0032
    title: "Pulse Check-In Questionnaire Schema"
    status: not-written
    blocks: "Phase 1 Task 1 — 4 Drift tables + DAO"
---

## Goal

Make the Agentic Journal more useful for adults with ADHD by implementing features informed by clinical evidence, behavioral science, and ecological momentary assessment (EMA) research. The first deliverable is a Pulse Check-In Questionnaire; subsequent phases address broader ADHD-specific friction points identified through gap analysis.

## Context

A comprehensive research report ("Designing for the ADHD Mind") was analyzed against the current app. The report synthesizes clinical evidence, behavioral science, competitive analysis of 9 products, and technical architecture research. The analysis revealed that the app is well-aligned in several areas (voice-first, offline-first, no streaks, layered AI) but has meaningful gaps in capture friction, emotional state tracking, gap-shaming, and data sovereignty.

**Core thesis from the research**: *Capture must be nearly effortless in the moment, while structure and value emerge later through gentle automation, retrieval, and resurfacing.*

### What the App Already Gets Right

- Voice-first capture with multiple STT tiers (Google online, Sherpa-ONNX offline) — *endpoint detection requires tuning for journaling cadence; see Voice Capture Prerequisites in Phase 1*
- Offline-first, privacy-respecting (local SQLite source of truth, opt-in cloud sync)
- No streaks or gap-shaming calendars (report lists these as anti-features)
- Progressive disclosure (search/gallery/tasks icons hidden until content exists)
- AI is layered (rule-based always available, Claude when online)
- Auto-generated summaries, intent classification, Android assistant registration
- Multiple journaling modes (free, gratitude, dream, mood check-in)

### Phase Rationale

Phase 1 (Pulse Check-In, 9 tasks + 4 tables) precedes Phase 2 (3 quick wins) for build dependency reasons, not priority reasons. Phase 1 establishes the data model and journaling mode infrastructure that Phases 3 and 4 build on. Phase 2 quick wins are high-value but low-infrastructure — 2A (gap-shaming removal) and 2B (recovery flow) can be shipped in parallel with Phase 1 tasks at any time without Phase 1 being complete. The ordering reflects dependency, not urgency.

### Research Sources

- [EMA Mood Assessment Handbook](https://jruwaard.github.io/aph_ema_handbook/mood.html)
- [PHQ-4 factor structure in ADHD adults](https://pmc.ncbi.nlm.nih.gov/articles/PMC10375022/)
- [WHO-5 Well-Being Index systematic review](https://karger.com/pps/article/84/3/167/282903/)
- [Brief Emotion Dysregulation Scale (BEDS)](https://pmc.ncbi.nlm.nih.gov/articles/PMC10518026/)
- [EMA in ADHD — protocol study](https://pmc.ncbi.nlm.nih.gov/articles/PMC10546102/)
- [PHQ screeners (public domain)](https://www.phqscreeners.com/)

---

## License Notes

| Instrument | License | Commercial Use | Action Required |
|---|---|---|---|
| **PHQ-4** | Public domain | Unrestricted | None |
| **EMA Circumplex** | Standard research method | Unrestricted | None |
| **BEDS** | Research instrument | Review needed | Verify before shipping |
| **WHO-5** | CC BY-NC-SA 3.0 | **Restricted** | See below |

**WHO-5 CC BY-NC-SA 3.0 — NC clause risk**: The NonCommercial clause prohibits use "primarily intended for or directed towards commercial advantage or private monetary compensation." For any commercial or freemium distribution, a formal license request to the rights holder is required:

- Rights holder: Psychiatric Centre North Zealand (Region Hovedstadens Psykiatri)
- License request: https://www.psykiatri-regionh.dk/who-5/who-5-questionnaire-translations/
- Submit before Task 2 (seed defaults) ships to users

**Contingency**: If commercial license is not granted, replace the WHO-5 items (sleep quality, energy) with custom questions that do not derive from the instrument. The composite score formula and VAS design remain unaffected. Flag this decision in ADR-0032.

---

## ADRs Required Before Implementation

These ADRs must be written and approved before the tasks they gate are started. Both are currently **not written**.

| ADR | Title | Gates | Why ADR-level |
|---|---|---|---|
| **ADR-0031** | Deepgram Nova-3 STT Integration | Phase 1 P1 | Voice engine swap — same category as ADR-0022; must scope Deepgram `speech_final`/`utterance_end` → `SpeechResult.isFinal` mapping and endpoint detection config rationale |
| **ADR-0032** | Pulse Check-In Questionnaire Schema | Phase 1 Task 1 | New 4-table Drift schema — same category as ADR-0018/0019/0020/0021/0024; must cover WHO-5 licensing decision, sync strategy for clinical-scale data (ADR-0004/0012), composite score formula canonical source, and QuestionnaireTemplates table justification (deviation from ADR-0025 §Rejected Alternative 3) |

---

## Phase 1: Pulse Check-In Questionnaire (Build First)

### Research Foundation

Default questions draw from validated, freely-licensed instruments:

| Instrument | Items | Focus | License |
|---|---|---|---|
| **PHQ-4** | 4 | Depression + Anxiety | Public domain |
| **WHO-5** | 5 | Positive well-being | CC BY-NC-SA 3.0 |
| **EMA Circumplex** | 2 axes | Valence + Arousal | Standard research method |
| **BEDS** | 12 | Emotion dysregulation | Research instrument |

Key EMA design principles:
- VAS 1-10 is standard for daily momentary assessment — validated, fast, low cognitive load
- Measures should take < 2 minutes — longer = lower compliance, especially for ADHD
- "Right now" framing reduces recall bias vs. "over the past 2 weeks"
- Positive framing reduces avoidance

### Design Decisions

- **Scale**: 1-10 default, configurable to 1-100 per template
- **Item count**: 6 default items (~60 seconds)
- **Integration**: New journaling mode (fits existing `JournalingMode` enum architecture)
- **Admin**: Collapsible settings section in existing settings screen

### Default Question Set (6 items)

| # | Question | Low (1) | High (10) | Source | Reversed? |
|---|----------|---------|-----------|--------|-----------|
| 1 | How would you rate your overall mood right now? | Very low | Excellent | Circumplex valence | No |
| 2 | How is your energy level? | Depleted | Fully energized | Circumplex arousal / WHO-5 | No |
| 3 | How anxious or worried do you feel? | Not at all | Extremely | GAD-2 / PHQ-4 | **Yes** |
| 4 | How well can you focus right now? | Can't concentrate | Laser focused | ADHD-specific | No |
| 5 | How well are you managing your emotions? | Overwhelmed | In control | BEDS | No |
| 6 | How well did you sleep last night? | Terribly | Great | WHO-5 item 4 | No |

**Reverse-scored items** (anxiety): high raw value = negative well-being. For composite score, inverted as `scaleMax + scaleMin - raw_value`. (On the default 1-10 scale: `10 + 1 - raw` = same as `11 - raw`. On a 1-100 scale: `100 + 1 - raw`. On a 0-10 scale: `10 + 0 - raw = 10 - raw`. Note: `scaleMax + 1 - raw` is incorrect for scales where `scaleMin ≠ 1`.)

**Composite score**: Average of all active items (after reversals), scaled to 0-100 as `(mean - scaleMin) / (scaleMax - scaleMin) * 100`.

**Edge cases — must be handled before Task 4**:
- **Partial completion**: no save unless all active items are answered. If session is abandoned mid-flow, no `CheckInResponse` is persisted. Future partial-save support is reserved by making `compositeScore` and `CheckInAnswer.value` nullable in the schema.
- **All items deactivated**: `computeCompositeScore([])` returns `null`, never `NaN` or `0`.
- **Single item**: composite is just that item's scaled value (formula holds).
- **Out-of-range input**: numeric parser returns `null` for out-of-range values; voice flow re-prompts once with range reminder.

### UX Design

**Voice Mode Flow**:
1. Agent: "Let's do a quick check-in. I'll ask you 6 questions — just give me a number from 1 to 10."
2. Agent reads question + endpoint labels
3. User says a number → agent acknowledges briefly: "Got it, 7." → next question
4. After all items: summary of all scores. "Want to talk about any of these?" → optional free journal

**Voice Error Branches (must be implemented in Task 4)**:

| User response | Behavior |
|---|---|
| Non-numeric ("I feel terrible") | Re-prompt once: "Just a number from 1 to 10 — how would you rate it?" If still non-numeric → treat as skip (null answer), move on |
| Out-of-range ("eleven", "zero") | Re-prompt once with range: "That's outside the 1-to-10 range. What number from 1 to 10?" If still out-of-range → treat as skip |
| "skip" / "I don't know" / "pass" | Accept immediately as null answer, acknowledge: "No problem, moving on." → next question |
| Silence timeout (no speech detected) | Treat as skip after one re-prompt: "Take your time — or say skip if you'd rather move on." |

Skipped items: recorded as `CheckInAnswer` with `value = null`. Skipped items excluded from composite calculation (denominator = answered items only, not total items). If all items skipped → no `CheckInResponse` saved.

**Visual Mode Flow**:
1. Single scrollable screen with 6 slider controls (or segmented 1-10 buttons)
2. Each item shows question text + endpoint labels + current value
3. Large "Save" button at bottom
4. After save: summary card + optional "Add a note?"

### Voice Capture Prerequisites (Complete Before Tasks 1–9)

Phase 1's Voice Mode Flow — agent reads a question, user replies with a number, agent acknowledges and moves on — is the primary ADHD delivery path for the Pulse Check-In. It depends directly on reliable STT. Device testing revealed two problems that, if unaddressed, violate the spec's own EMA compliance constraint (< 2 minutes, see Research Foundation above): a 5-second silence timeout that adds 30+ seconds of dead time across a 6-question check-in, and Android's cloud STT defaults tuned for command speech (~800ms endpoint detection) rather than journaling cadence (2–3s thinking pauses).

These prerequisites also unblock Phase 3A (Quick Capture Mode). The "10-Second Promise" cannot be kept if voice transcription takes 5+ seconds per turn.

See: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture (sealed, 7 turns, 3 specialists)

---

**P0 — STT Pause Timeout Fix (Immediate — 1 line, no ADR required)**

`lib/services/speech_to_text_stt_service.dart:98` — change `pauseFor: Duration(seconds: 5)` to `pauseFor: Duration(seconds: 2)`.

This is a tuning constant within the ADR-0022 implementation boundary, not an architectural decision. The 5-second value is Google's default for command-style assistants; 2 seconds is appropriate for journaling. Ship this before building Tasks 3–6.

---

**P1 — Deepgram Nova-3 Streaming STT (Next Sprint — requires ADR-0031 before implementation)**

Replace Android SpeechRecognizer with Deepgram Nova-3 as the primary online STT engine. sherpa_onnx offline fallback is retained (ADR-0022 §3 offline contract preserved).

**Prerequisite**: Write and approve `docs/adr/ADR-0031-deepgram-stt-integration.md` before writing any P1 code. This is a voice engine swap — the same category that produced ADR-0022. The ADR must capture: endpoint detection rationale (journaling cadence vs. cloud defaults), the ADHD thinking-pause clinical link, sherpa_onnx fallback retention, and P2 as a deferred alternative.

Implementation tasks:
- New: `lib/services/deepgram_stt_service.dart` — implements `SpeechRecognitionService` (ADR-0022 swap interface)
- New: `supabase/functions/deepgram-proxy/` — follows ADR-0005 security proxy pattern
- Config: `endpointing=2000`, `utterance_end_ms=1500`, `interim_results=true`, `vad_events=true`
- Update `voice_providers.dart` engine-selection to include Deepgram tier

Build and test Task 6 (Numeric Parser) against the Deepgram engine — not against Android SpeechRecognizer — to avoid re-validation rework.

**ADR-0031 must also scope**: the mapping of Deepgram's `speech_final` / `utterance_end` WebSocket events onto `SpeechResult.isFinal` in the `SpeechRecognitionService` interface. These do not map cleanly onto the current `SpeechResult` model (which uses Android's native `isFinal` flag). The `VoiceSessionOrchestrator` state machine depends on `isFinal` semantics — failing to resolve this mapping in the ADR will cause orchestrator state bugs mid-implementation. (ADR refs: ADR-0022, ADR-0016)

---

**P2 — GPT-4o Realtime (Future — Blocked, no implementation commitment)**

GPT-4o Realtime API offers end-to-end audio processing with <300ms response latency and model-based endpoint detection. It would close most of the gap to ChatGPT voice naturalness. Not pursued until:

1. A WebSocket proxy ADR is written and approved (ADR-0005 scope is HTTP-only; persistent WebSocket connections require a new decision record)
2. Cost model validated (~$3/session vs. ~$0.06/session for Deepgram + Claude)

Documented here as a known future option from the deliberation, not a roadmap commitment.

---

### Implementation Tasks

**Task 1: Data Model — 4 New Drift Tables** *(requires ADR-0032 before starting)*
- `QuestionnaireTemplates` — id, name, description, isSystemDefault, isActive, scaleMin, scaleMax, sortOrder, timestamps
- `QuestionnaireItems` — id, templateId (FK), questionText, minLabel, maxLabel, isReversed, sortOrder, isActive
- `CheckInResponses` — id, sessionId (FK), templateId (FK), completedAt, `compositeScore REAL nullable` (null if all items skipped), syncStatus
- `CheckInAnswers` — id, responseId (FK), itemId (FK), `value INTEGER nullable` (null if item was skipped)
- File: `lib/database/tables.dart`
- New DAO: `lib/database/daos/questionnaire_dao.dart`
- **Nullable rationale**: `compositeScore` and `value` are nullable to support skipped items (voice flow error branch) and future partial-save capability without a migration. See composite score edge cases above.

**Task 2: Seed Default Template**
- New: `lib/services/questionnaire_defaults.dart`
- Seeds 6 default items on first launch / empty DB
- System defaults: `isSystemDefault: true`, cannot be deleted (only deactivated)

**Task 3: JournalingMode Extension**
- Add `pulseCheckIn` to enum in `lib/models/journaling_mode.dart`
- Add `displayName`, `systemPromptFragment`, `toDbString`, `fromDbString`
- **`systemPromptFragment` must be empty or minimal** — pulse check-in is form-driven (CheckInNotifier drives questions), not LLM-prompt-driven. The LLM is only invoked for the optional free-journal step at the end. Do NOT write a prompt fragment that implies the LLM reads the questions; document this explicitly in the code comment.
- **Update `test/models/journaling_mode_test.dart`**: change `hasLength(5)` → `hasLength(6)`. Add assertions for `pulseCheckIn.displayName`, `pulseCheckIn.toDbString()`, `pulseCheckIn.fromDbString()` round-trip, and `systemPromptFragment` (empty string or explicit marker). This test will fail the quality gate if not updated as part of Task 3.

**Task 4: Check-In Flow Provider** *(architecture boundary — do NOT add check-in state to SessionNotifier)*
- Create `CheckInNotifier` + `CheckInState` in `lib/providers/questionnaire_providers.dart`
- `CheckInState` owns: `activeQuestionnaireItems`, `currentCheckInStep`, `checkInAnswers`, `isActive`
- `SessionNotifier` retains only: `journalingMode` (already present) + a `bool isCheckInActive` flag. Coordination happens via session ID, not shared state. This matches the pattern used for task and calendar providers.
- **Voice mode**: `CheckInNotifier` drives question sequencing; speaks question text via TTS; waits for numeric response from STT; handles error branches (see Voice Error Branches table above); calls `SessionNotifier.resumeOrchestrator()` equivalent after each answer so the voice loop doesn't get stuck in processing
- **Text mode**: `CheckInNotifier` exposes current question index to `pulse_check_in_widget.dart`
- After last item: compute composite (using corrected formula), save `CheckInResponse` via DAO, emit summary state
- **Test isolation**: use `ProviderContainer` override + `AppDatabase.forTesting(NativeDatabase.memory())` — same pattern as existing session provider tests

**Task 5: Visual Mode — Slider UI Widget**
- New: `lib/ui/widgets/pulse_check_in_widget.dart`
- Material 3 Slider with endpoint labels, progress indicator ("3 of 6")

**Task 6: Voice Mode — Numeric Parser**
- New: `lib/services/numeric_parser_service.dart` (stateless, no dependencies — same structural category as `intent_classifier.dart` and `voice_command_classifier.dart`)
- Parse spoken numbers and validate against scale range. Returns `int?` (null = parse failure or out-of-range)

**Full input contract (test against all rows)**:

| Input | Expected | Notes |
|---|---|---|
| `"7"` | `7` | Digit string |
| `"seven"` | `7` | Word form |
| `"um, like a 7"` | `7` | Hedged digit |
| `"ten"` | `10` | Upper bound (1-10) |
| `"ten out of ten"` | `10` | Qualified word form |
| `"about a six"` | `6` | Hedged word form |
| `"I'd say a seven"` | `7` | Conversational form |
| `"zero"` | `null` | Out of range (min=1) |
| `"eleven"` | `null` | Out of range (max=10) |
| `"six point five"` | `null` | Decimal — reject, do not round |
| `"I don't know"` | `null` | Explicit uncertainty |
| `"skip"` | `null` | Explicit skip |
| `""` | `null` | Empty string |
| `"  "` | `null` | Whitespace only |

Note: The parser is scale-aware — out-of-range is determined by the active template's `scaleMin`/`scaleMax`, not hardcoded 1-10. Build and validate against Deepgram STT output (P1) before finalizing the hedged-speech patterns.

**Task 7: Summary Display**
- New: `lib/ui/widgets/pulse_check_in_summary.dart`
- Compact results card in chat transcript and session detail screen

**Task 8: Settings — Questionnaire Config**
- Collapsible section in `lib/ui/screens/settings_screen.dart`
- Template selector, scale toggle, question list with enable/disable/edit/reorder/add

**Task 9: Mode Selector Integration**
- Add `pulseCheckIn` to mode selection UI
- New: `lib/providers/questionnaire_providers.dart`

### Key Files

| File | Action |
|---|---|
| `lib/database/tables.dart` | Add 4 tables |
| `lib/database/daos/questionnaire_dao.dart` | **New** |
| `lib/models/journaling_mode.dart` | Add enum value + prompt |
| `lib/services/questionnaire_defaults.dart` | **New** |
| `lib/services/numeric_parser.dart` | **New** |
| `lib/providers/session_providers.dart` | Extend flow |
| `lib/providers/questionnaire_providers.dart` | **New** |
| `lib/ui/widgets/pulse_check_in_widget.dart` | **New** |
| `lib/ui/widgets/pulse_check_in_summary.dart` | **New** |
| `lib/ui/screens/journal_session_screen.dart` | Integrate |
| `lib/ui/screens/session_detail_screen.dart` | Show results |
| `lib/ui/screens/settings_screen.dart` | Config section |

### Acceptance Criteria (Phase 1)

- [ ] All 4 Drift tables exist and migrate cleanly from a fresh database (no migration errors)
- [ ] Default 6-item template seeds on first launch; `isSystemDefault: true` items cannot be deleted via DAO
- [ ] `pulseCheckIn` selectable from mode picker; `journaling_mode_test.dart` passes with updated `hasLength(6)`
- [ ] Composite score: `[8,6,3,7,5,9]` with Q3 reversed on 1-10 scale → `(8+6+(11-3)+7+5+9)/6 = 7.17` → scaled 0-100 = `68.5` (verify formula: `(mean - 1) / 9 * 100`)
- [ ] Composite score: all items answered `1` → `0.0`; all answered `10` → `100.0`
- [ ] Composite score: empty active item list → `null`, not `NaN` or `0`
- [ ] Numeric parser: all 14 contract rows pass (see Task 6 table)
- [ ] Voice mode: 6-question flow completes in < 2 minutes with P0 pauseFor fix applied
- [ ] Voice mode: non-numeric response triggers re-prompt; second non-numeric treats as skip
- [ ] Voice mode: "skip" response immediately records null answer and advances
- [ ] Summary card renders in both chat transcript and session detail screen
- [ ] Settings: item enable/disable, reorder, and add custom item all persist across app restart
- [ ] Quality gate: `python scripts/quality_gate.py` passes — >= 80% coverage, zero `dart analyze` errors
- [ ] P0 (pauseFor 5s → 2s) shipped; P1 blocked until ADR-0031 approved

### Verification

- **Unit**: composite score (all edge cases above), numeric parser (full 14-row contract), reverse-scoring formula (`scaleMax + scaleMin - raw_value`)
- **DAO**: CRUD on all 4 tables (in-memory drift DB); `getActiveTemplate()` returns system default; items ordered by `sortOrder`; `saveCheckInResponse()` retrievable by `sessionId`; system default delete is rejected/noop; inserting duplicate `CheckInAnswer` (same `responseId` + `itemId`) is rejected
- **Widget**: slider UI, summary card, progress indicator ("3 of 6")
- **Integration**: voice-mode end-to-end flow (mock STT), including all error branches (non-numeric, out-of-range, skip)
- **Manual**: emulator test in both voice and text modes; verify < 2-minute completion with P0 fix
- **Quality gate**: `python scripts/quality_gate.py` — all checks pass, >= 80% coverage

---

## Phase 2: Quick Wins (Low Effort, High Impact)

### 2A: Remove Gap-Shaming from AI Greetings

**Problem**: All 3 AI layers compute `daysSinceLast` and inject it into greetings. The research report identifies that even gentle mentions of absence duration trigger shame and avoidance spirals in ADHD users.

**Fix**: Remove `daysSinceLast` from greeting logic. Replace with present-focused greetings: "Good to see you. What's on your mind?"

**Files**:
- `lib/layers/claude_api_layer.dart:68-82` — remove `days_since_last` context
- `lib/layers/rule_based_layer.dart:180-183` — remove `daysSinceLastSession` greeting
- `lib/layers/local_llm_layer.dart:55-62` — remove "It's been N days" injection
- `lib/models/personality_config.dart` — audit system prompt

### 2B: Recovery Flow After Gaps

**Problem**: No special handling when user returns after days away.

**Fix**: After 3+ day gap (computed silently — never shown to user), display a two-button choice on the home screen: "Quick check-in" or "Just browse." Never mention duration of absence.

**Files**: `lib/ui/screens/session_list_screen.dart`, `lib/providers/session_providers.dart`

### 2C: Data Export

**Problem**: No export feature exists. The research report calls missing export a "documented trust-breaker" for user trust and data sovereignty.

**Fix**: Add full data export (JSON and/or plain text) to settings. Include sessions, messages, photos, tags, tasks, check-in responses.

**File**: `lib/ui/screens/settings_screen.dart`

---

## Phase 3: Engagement & Retention Features

### 3A: Quick Capture Mode (The "10-Second Promise")

**Dependency — Voice path blocked until P0 + P1 complete**: The "10-Second Promise" cannot be kept if voice transcription takes 5+ seconds per turn or produces frequent mistranscriptions. P0 (pauseFor fix) can be shipped immediately. P1 (Deepgram) requires ADR-0031 first. Do not implement the voice capture mode of 3A until both prerequisites are done.

**Problem**: Every capture requires starting a full AI conversation session. ADHD initiation difficulty (the #1 clinical barrier) makes this a friction barrier.

**Design**: One-tap capture palette on home screen with large buttons: Text, Voice, Photo, Mood Tap, Pulse Check-In. Each opens an immediately active capture state with autosave. A single word, emoji, or 5-second voice clip is treated as "complete." Minimum viable entries are first-class journal entries. Last-used mode is remembered as default.

**Files**: `lib/ui/screens/session_list_screen.dart` (home screen FAB replacement), new quick capture widgets

### 3B: Quick Mood Tap

**Problem**: Mood Check-In mode is a full 3-step AI conversation. Too heavy for "just log how I feel right now."

**Design**: Two-axis grid (energy x pleasantness) or simple emoji row. Tap a cell or emoji, auto-save, done. ~3 seconds. Optionally expandable: "Want to add a note about why?"

**Files**: New mood tap widget, integrates with quick capture palette

### 3C: Home Screen Resurfacing ("Gifts")

**Problem**: Past entries are invisible unless explicitly searched. ADHD "object permanence failure" means out of sight = out of mind. The research identifies resurfacing as the primary retention mechanism for ADHD users — more effective than reminders or streaks.

**Design**: Single resurfaced entry card on home screen. "Skip" and "Reflect on this" actions. Algorithm: surface entries from ~1 week, 1 month, 3 months ago (spaced repetition-inspired). Never resurface entries the user has excluded. Never resurface negative-tagged entries without opt-in. One entry at a time — never overwhelm.

**Files**: `lib/ui/screens/session_list_screen.dart`, new resurfacing service

### 3D: Weekly Celebratory Digest

**Problem**: No periodic re-engagement touchpoint.

**Design**: Weekly card or local notification (opt-in): "This week you captured 3 moments — nice." Focus on what WAS captured, never mention what was missed. Include one resurfaced moment from the week. No mention of streaks, consistency, or missed days.

**Files**: New digest service + optional notification integration

---

## Phase 4: Polish & Configurability

### 4A: Tag Editing

**Problem**: AI auto-extracts tags (mood, people, topics) but users can't correct, add, or remove them.

**Fix**: Add editable tag chips on session detail screen. Tap to edit, "x" to remove, "+" to add.

**File**: `lib/ui/screens/session_detail_screen.dart`

### 4B: Android Home Screen Widget

**Design**: Tap opens directly into last-used capture mode. No content preview on widget for privacy. Matches report's recommendation for OS-level entry points.

**Files**: Android native widget code (`android/`) + Flutter platform channel

### 4C: Passive Metadata — Weather

**Design**: Auto-capture weather at session start using existing location data. Enriches retrieval without adding any friction. Store as additional fields on `JournalSessions`.

**Files**: New weather service, `lib/database/tables.dart` (add weather columns)

### 4D: Adaptive Non-Escalating Reminders

**Design**: Context-sensitive to time of day and recent usage patterns. "Snooze forever" is a first-class option. If user dismisses 3 prompts in a row, auto-disable that prompt type. Never escalate after non-response — the research is explicit that escalation triggers alert fatigue.

**Files**: New reminder service + notification scheduling

### 4E: Pulse Check-In Trend View

**Design**: Line charts per dimension over time using check-in data. Correlation signals presented with epistemic humility: "possible relationship" language, confidence bands, missing-data warnings, plain-language disclaimers. Never ranking "best/worst days." Never diagnostic.

**Files**: New trend screen (likely using `fl_chart` or similar charting package)

### 4F: GPT-4o Realtime End-to-End Audio (Blocked — future north star)

**Design**: Replace the STT → Claude → TTS pipeline with GPT-4o Realtime API's persistent WebSocket audio channel. Offers model-based endpoint detection (eliminates silence timeout tuning), <300ms first-word latency, and native turn-taking that handles mid-thought pauses. Closest implementation of ChatGPT voice naturalness.

**Hard blockers — do not implement until both are resolved**:
1. WebSocket proxy ADR: ADR-0005 scope is HTTP-only. A new decision record is required before any WebSocket-based architecture is implemented.
2. Cost model: ~$3/session (vs. ~$0.06/session for Deepgram + Claude). Requires user-facing disclosure and explicit opt-in.

**Note**: The STT and AI layers would need to be unified (GPT-4o model for voice conversations), which requires a deliberate architectural decision about the hybrid Claude/GPT-4o model boundary. Do not underestimate this constraint.

---

## Design Principles (Apply Throughout All Phases)

These principles from the research report apply as constraints across ALL feature work:

1. **Microcopy is clinical**: Never mention missed days or gaps. Celebrate what exists, don't evaluate what's missing. Confirmations should be warm and final: "Saved. That's enough." Voice reliability is part of this contract — STT mistranscriptions that mangle a user's words are a form of friction that violates the "effortless" standard just as much as gap-shaming copy does.
2. **No streaks, no gap-shaming**: Already absent from the app — preserve this. Never add visible streaks or gap-shaming calendars.
3. **AI is opt-in**: Every AI feature must be explicitly enabled. Every AI output gets "Why?" and "Edit/Remove" affordances. Present outputs as suggestions with uncertainty.
4. **Epistemic humility**: Correlations framed as possibilities, never diagnosis or causation. Include missing-data warnings and plain-language disclaimers.
5. **Privacy-maximizing defaults**: Local-only storage, no account required, full export/delete always available. Cloud sync and AI processing are opt-in only.
6. **Adaptive, never escalating**: Reminders that respect dismissal patterns. Alert fatigue is a documented risk.
7. **Structure emerges later**: Don't ask users to organize at capture time. Tags, themes, and patterns should come from gentle automation, not capture-time decisions.

---

## Anti-Features (Deliberately Excluded)

Per the research report's competitive analysis and clinical evidence:

- Visible streaks and gap-shaming calendars
- Mandatory capture-time tagging
- AI enabled by default
- Complex onboarding questionnaires
- Social features, public sharing, or therapist-like AI chat
- Ranking "best/worst" days
- Escalating reminders after non-response
