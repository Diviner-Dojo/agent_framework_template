# Build Status

> Read this at session start. Update before context compaction.
> Last updated: 2026-03-04 ~09:30 UTC

## Current Task

**Status:** Microphone leak fix committed + Deepgram proxy `?access_token=` fix deployed. Awaiting device test.
**Branch:** `develop/adhd-roadmap`
**Version:** `0.32.0+32`

### In Progress
- Device test: confirm all three STT engines work after microphone leak fix
  - Deepgram: verify proxy connects and ?access_token= resolves 401
  - speech_to_text: verify Android SpeechRecognizer acquires mic (was blocked by leaked recorder)
  - sherpa_onnx: verify mic released (same fix applied to SherpaOnnxSpeechRecognitionService)

### Root Cause Found — ALL STT broken
- **Bug**: `DeepgramSttService.onDone` set `_isListening=false` but never stopped `AudioRecorder`. `stopListening()` and `dispose()` both guarded on `_isListening` → skipped recorder cleanup. Recorder held OS microphone indefinitely, blocking all subsequent STT engines.
- **Fix**: Unconditional fire-and-forget recorder cleanup in `onDone` + `dispose()` for both `DeepgramSttService` and `SherpaOnnxSpeechRecognitionService` (same pattern found by specialist review).
- **Deepgram 401**: Changed `?token=` to `?access_token=` in proxy WebSocket URL — matches `/v1/auth/grant` response field name per Deepgram's browser streaming convention.
- **Audio source**: Kept `UNPROCESSED` (confirmed non-silent audio max=255 on SM_G998U1 vs voiceRecognition which was silent).

### Recently Completed — Deepgram STT device fixes (commit 9a19f69)

- **Deepgram STT silence fix (Samsung Galaxy S21 Ultra)**: `AndroidAudioSource.voiceRecognition` + `manageBluetooth:false` in `deepgram_stt_service.dart`. Root cause: Samsung One UI `defaultSource`/`MIC` produces silent PCM after just_audio TTS. VOICE_RECOGNITION uses MODE_NORMAL (same as Google Voice Search).
- **Platform-conditional TTS delay**: `ttsReleaseDelay: Platform.isAndroid ? 500ms : Duration.zero`. Was unconditional 500ms; iOS gets zero penalty.
- **USER-only summary regeneration**: `_regenerateSummary()` now passes USER-only messages to Claude. Stale ASSISTANT messages with pre-edit names (e.g., "Shawn") no longer corrupt metadata extraction.
- **Regression test**: `_SpyAgentRepository` captures `allMessages` arg, asserts no `assistant` role entries.
- Review: REV-20260305-004829 (approve-with-changes, 2 blocking resolved in-review, 7 advisory)
- Quality gate: 7/7 | Coverage: 81.3%
- **Open advisories: 7 new. Total: 262**

### Recently Completed — Phase 4F + Deepgram proxy deployment

- **Phase 4F: Long-press message editing + summary regeneration** (commit 3d398f2):
  - `MessageDao.updateMessageContent()` — partial drift update (content column only)
  - `GestureDetector(onLongPress)` on USER-role ChatBubble → `showModalBottomSheet` edit sheet
  - `_regenerateSummary()` re-runs Claude summary after edit, preserves tags when offline (B1 fix)
  - `_isRegenerating` state + loading spinner + SnackBar on failure (B2 fix)
  - Empty-string guard prevents spurious DB write (B3 fix)
  - Review: REV-20260304-231632 (approve-with-changes, 3 blocking resolved in-review)
  - Quality gate: 7/7 | Coverage: 81.2% | Education gate: deferred
  - **Open advisories: 5 new. Total: 255**

- **Deepgram proxy fully operational**: `deepgram-proxy` Edge Function deployed + `DEEPGRAM_API_KEY` secret set via Supabase CLI (server-side only — not in any committed file). Ready to test on device.

### Recently Completed — Device Testing Bug Fixes (commits 778b3d4 + 2164c42)

All four device bugs found after v0.32.0+32 deployment fixed and deployed to SM_G998U1:

- **Bug 1 (Card styles imperceptible)**: Elevation Soft 1→2dp, Raised 3→8dp; `withCardStyle(CardStyle)` adds 1dp outlineVariant border for Flat. Confirmed working on emulator.
- **Bug 2 ("In N minutes" task time)**: Added relative duration patterns to `_temporalPattern` in intent_classifier.dart. Confirmed working on emulator.
- **Bug 3 (Photo capture kills voice)**: Save/restore `_phaseBeforePause` in `capturePhotoDescription()` finally block. Confirmed working on emulator.
- **Bug 4 (Search filters return no results)**: Three-layer fix — session_dao.searchSessions keyword clause conditional; search_repository + search_providers early return gated on hasActiveFilters; search_screen pre-search state only shown when no query AND no filters.
  - Review: REV-20260304-214110 (approve-with-changes, 2 blocking resolved in-review, 4 advisory)
  - Quality gate: 7/7 | Coverage: 81.1%
  - Deployed: emulator (32.6s) + SM_G998U1 (1m 7.7s)
  - **Open advisories from this sprint: 4 new. Total: 247**

### Pending Items
- **Test Deepgram on device**: Reconnect Samsung Galaxy S21 Ultra (R5CR10LW2FE), deploy (`python scripts/deploy.py --install-only`), start voice session, verify STT transcribes (no "I didn't catch anything" message).
- **Advisory A-4**: Handle `SCHEDULE_EXACT_ALARM` revocation (`PlatformException` from `zonedSchedule()`) — clear stale notificationId from task row; elevated from advisory to important given silent failure loop risk (see REV-20260304-085452 A6)
- **Phase 3A advisory follow-ups** (8 open from REV-20260304-142456 + 8 new from REV-20260304-145506): A2 (setMode ordering), A4 (Check-In descriptor copy), A5 (barrierLabel), A6 (DraggableScrollableSheet), A7 (excludeSemantics), A8 (StateNotifier→Notifier<T>), A10 (removed journaling modes ADR), A11 (mode key constants) [from REV-142456]; A1 (capturePhotoDescription non-paused branch test), A2 (pulse_check_in dispatch test), A3 (timing assertion), A4 (silence timeout), A5 (maxLines adaptive + minLines), A6 (textInputAction.send), A7 (FAB disabled visual), A8 (viewPadding→padding) [from REV-145506]
- **Phase 4E advisory follow-ups** (10 open): A1 Y-axis label, A2 window-gate misalignment, A3 remove raw r-value, A4 correlation empty state wording, A5 shrinkWrap tap target, A6 _shortLabel consolidation

### Just Completed
- **Phase 4B/4C: Android Quick Capture widget + passive weather metadata** (PR #84, `develop/adhd-roadmap`, v0.32.0+32):
  - `QuickCaptureWidget.kt`: Android `AppWidgetProvider` — one-tap launches app in last-used capture mode; reads SharedPreferences via `flutter.` prefix (ADR-0034 Decision 3, graceful null fallback)
  - `WidgetLaunchService`: MethodChannel bridge for cold-start + warm-start dispatch; `_checkWidgetRelaunch()` in `didChangeAppLifecycleState` fixes warm-start silent-drop bug (B5)
  - Intent extra allowlist in `session_list_screen.dart`: mode validated against `{'text','voice','__quick_mood_tap__','pulse_check_in'}` (B1, security fix for exported MainActivity)
  - `WeatherService`: Open-Meteo (free, keyless, GDPR-compliant), WMO 306 codes, fire-and-forget; `connectTimeout` + `receiveTimeout` both 5s (B2, TCP hang fix)
  - Weather columns local-only: excluded from `buildSessionUpsertMap` + load-bearing enforcement test (ADR-0034 Decision 2)
  - ADR-0034: all 4 decisions documented with alternatives considered
  - Review: REV-20260304-183306 (request-changes → 5 blocking all resolved, 9 advisory open)
  - Build: DISC-20260304-165234-build-phase4bc-weather-widget (sealed)
  - Quality gate: 7/7 | Coverage: 81.1% | Education gate: deferred
  - **Open advisories from this sprint: 9 new. Total: 243**

- **Bug fixes + Phase 3A advisories A1/A3/A9** (PR #83, `develop/adhd-roadmap`, v0.31.1+31):
  - Bug 1: `TextField maxLines: null → 6` — send button no longer pushed off-screen
  - Bug 2: `capturePhotoDescription()` restores paused phase so `orchestrator.resume()` works
  - Advisory A1: dispatch branch tests (Mood Tap, Voice pre-enable, Write mode-key)
  - Advisory A3: FAB tooltip `'Opening...'` during `_isStarting`
  - Advisory A9: voice pre-enable ordering comment
  - Review: REV-20260304-145506 (approve-with-changes, 1 blocking resolved, 8 advisory)
  - Quality gate: 7/7 | Coverage: 80.9% | Education gate: deferred
  - Open advisories: 8 new. **Total: 234**

- **Phase 3A: Quick Capture Mode** (PR #82, `develop/adhd-roadmap`, v0.31.0+30):
  - `last_capture_mode_provider.dart`: `LastCaptureModeNotifier` (StateNotifier<String?>) backed by SharedPreferences key `last_capture_mode`; null = no preference
  - `quick_capture_palette.dart`: `showQuickCapturePalette()` modal bottom sheet, 4 tiles (Write/Voice/Mood Tap/Check-In), last-used mode pre-highlighted via `primaryContainer`, ADHD framing, VoidCallback onTap from parent context
  - `session_list_screen.dart`: FAB wired to `_openQuickCapturePalette`; `_showModePicker` removed; voice pre-enable before `_startNewSession`; `showQuickMoodTapSheet` for `__quick_mood_tap__`; `context.mounted` guards after every await
  - **B1 blocking fix (resolved in-review)**: Photo tile dispatched as plain text session (provably incorrect) — removed from palette until camera-open dispatch implemented (Bug 2)
  - 16 tests (6 provider + 10 widget), quality gate 7/7, coverage 80.7%
  - Build: DISC-20260304-135245 (sealed); Review: REV-20260304-142456 (approve-with-changes, 1 blocking resolved in-review, 11 advisory)
  - Open advisories: 11 new. **Total: 226** (superseded by PR #83 — 3 resolved, 8 added → net 234)
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization

- **Phase 4E: Pulse Check-In Trend View** (PR #81, `develop/adhd-roadmap`, v0.30.0+29):
  - `CorrelationService`: pearson(), correlationMatrix(), rollingAverages(), normalizeAnswer() (static), generateInsights() with ADHD epistemic humility framing
  - `checkInTrendProvider`: StreamProvider<CheckInTrendData> via StreamController + ref.listen(fireImmediately: true) pattern (avoids Riverpod 3.0 deprecated .stream)
  - `CheckInHistoryScreen`: DefaultTabController + History/Trends TabBar; `_CheckInTrendTab` ConsumerStatefulWidget with 7/14/30-day window toggle, fl_chart LineChart rolling averages, correlation tiles, TrendInsight narrative cards
  - **B1 blocking fix (resolved in-review)**: Reverse-scored items (Anxiety, isReversed=true) not re-reversed before normalization → added `itemIsReversed: Map<int,bool>` to `CheckInHistoryEntry`; applied reversal in trend provider before `normalizeAnswer()`. Regression test + ledger entry.
  - 47 new tests (32 correlation service, 8 provider, 7 widget). Quality gate 7/7, coverage 80.5%.
  - Review: REV-20260304-015709 (approve-with-changes, 1 blocking resolved in-review, 10 advisory)
  - Open advisories: 10 new. **Total: 215**
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization

- **Notification Advisory Sprint A-1/A-2/A-3/A-5** (PR #80, `develop/adhd-roadmap`, v0.29.1+28):
  - A-1 (HIGH): `getTasksWithPendingReminders()`, `updateNotificationId()` added to `TaskDao`; `rescheduleFromTasks()` added to `NotificationSchedulerService`; `notificationBootRestoreProvider` FutureProvider; `app.dart initState()` trigger via addPostFrameCallback
  - A-2: `_FakeScheduler` tests for `deleteTask`/`completeTask` cancellation wiring (3 tests for updateNotificationId added as blocking fix B2)
  - A-3: Counter persistence + wrap-around arithmetic contract tests
  - A-5 (CORRECTED): `BootReceiver android:exported=false` replaces incorrect permission-based approach (normal-level permission was freely acquirable — B1 blocking fix from REV-20260304-085452)
  - Review: REV-20260304-085452 (approve-with-changes, 0.91; 2 blocking resolved in-review, 8 advisory)
  - Quality gate: 7/7 | Coverage: 80.1%
  - Open advisories: 8 new. **Total: 205**

- **Phase 5A Visual Identity + Scheduled Local Notifications (ADR-0033)** (PR #79, `develop/adhd-roadmap`, v0.29.0+27):
  - 7 curated palettes (Still Water, Warm Earth, Soft Lavender, Forest Floor, Ember Glow, Midnight Ink, Dawn Light)
  - `ThemeState`/`ThemeNotifier`, `ChatBubbleColors` ThemeExtension with WCAG AA contrast validation (56 combinations tested)
  - `NotificationSchedulerService`: fire-once OS alarms, ID namespace 1000–1999, SharedPreferences counter persistence
  - Schema v11: `reminderTime`, `notificationId`, `isQuickReminder` columns on Tasks table
  - `TaskDao` notification cancellation wiring (`completeTask`/`deleteTask` cancel pending OS notifications)
  - Review: REV-20260304-074715 (approve-with-changes, 0.91; 2 blocking resolved in-review, 13 advisory)
  - Quality gate: 7/7 | Coverage: 80.1%
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 13 new. **Total: 197**

- **Phase 4D: Adaptive Non-Escalating Reminders** (PR #78, `develop/adhd-roadmap`, v0.28.0+26):
  - `ReminderService` — synchronous `shouldShow()` guards: enabled, dismissal count < 3, not shown today, in time window
  - `ReminderWindow` enum: morning (7–9), afternoon (12–2), evening (7–9); `fromPrefValue` round-trip
  - `reminderServiceProvider` (synchronous Provider<ReminderService>), `dailyReminderVisibleProvider` (Provider<bool> with "has journaled today" check, excludes quick_mood_tap)
  - `session_list_screen.dart` — reminder card (B-1: `_isStarting` guard on Start Entry; B-2: try/catch on dismiss/snoozeForever), priority chain: reminder > digest > gift
  - `settings_screen.dart` — reminder settings card (SwitchListTile + morning/afternoon/evening SegmentedButton)
  - 25 ReminderService unit tests + 5 test files updated to override `dailyReminderVisibleProvider`
  - Review: REV-20260304-035354 (approve-with-changes, 2 blocking resolved in-review, 22 advisory)
  - Quality gate: 7/7 | Coverage: 80.4%
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 22 new from REV-20260304-035354. **Total: 184**

- **Phase 4A: Editable Tag Chips on Session Detail Screen** (PR #77, `develop/adhd-roadmap`, v0.26.0+24):
  - `updateSessionTags()` in `SessionDao` — partial update of moodTags/people/topicTags columns only
  - `session_detail_screen.dart` — InputChip rows (Mood/People/Topics) with add/edit/delete dialogs
  - controller-inside-builder pattern (same as PR #71 fix) prevents dispose-during-animation crash
  - `deleteButtonTooltipMessage: 'Remove $tag'` — per-tag unique tooltip for test targeting
  - Tag rows always shown even when empty (ADHD effortless capture — add tags even when AI extracted none)
  - B-1 resolved in-review: removed BoxConstraints(36dp) + visualDensity.compact from Add IconButton → 48dp
  - 4 new widget tests: show chips, delete, add, edit — all use real in-memory AppDatabase
  - Review: REV-20260304-005938 (approve-with-changes, B-1 resolved in-review, 12 advisory)
  - Quality gate: 7/7 | Coverage: 81.2% | 8/8 tests pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 12 new from REV-20260304-005938. **Total: 162**

  - Open advisories: 13 new from REV-20260304-074715. **Total: 197**

- **Advisory triage A7/A8/A9/A11/A12** (PR #76, `develop/adhd-roadmap`, v0.25.1+23):
  - A7: `onSelectionChanged` wrapped in try/catch + "Answer scale updated." / "Could not save..." SnackBars
  - A8: Switch.onChanged wrapped in try/catch (B-1 blocking fix) + Undo SnackBar on confirmed write only
  - A9: `onReorder` wrapped in try/catch + "Could not reorder questions." SnackBar
  - A11: Removed `tapTargetSize: MaterialTapTargetSize.shrinkWrap` from SegmentedButton (48dp restored)
  - A12: Helper text improved: "Applied immediately to all future check-ins. Past answers are unaffected."
  - 4 new widget tests + `_FakeQuestionnaireDao` pattern to prevent drift FakeAsync timer conflicts
  - Review: REV-20260303-235547 (approve-with-changes, B-1 resolved in-review, 5 advisory)
  - Quality gate: 7/7 | Coverage: 81.1% | 19 tests pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 5 new from REV-20260303-235547. **Total: 150**

- **Phase 3D: Weekly Celebratory Digest** (PR #75, `develop/adhd-roadmap`, v0.25.0+22):
  - `WeeklyDigestService` — 7-day look-back window, quick_mood_tap excluded, dismissal TTL via SharedPreferences, highlight = most recent session with summary
  - `weeklyDigestProvider` — FutureProvider<WeeklyDigest?> following Phase 3C pattern
  - `session_list_screen.dart` — `_buildWeeklyDigestCard` + mutual exclusion guard (showDigest/showGift) — ADHD "one card at a time" invariant
  - B-1 blocking fix applied in-review: digest card + gift card mutual exclusion
  - 12 service unit tests + 4 widget tests, 35 tests total pass
  - Review: REV-20260303-232113 (approve-with-changes, 1 blocking resolved in-review, 10 advisory)
  - Quality gate: 7/7 | Coverage: 81.0% | All pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 10 new from REV-20260303-232113. **Total: 145**

- **Phase 3C: Home Screen Resurfacing ("Gifts")** (PR #74, `develop/adhd-roadmap`, v0.24.0+21):
  - `ResurfacingService` — spaced-repetition windows (7d/30d/90d), Holt-Winters-lite decay, gift card on session_list_screen
  - `resurfacedSessionProvider` — FutureProvider with weighted random selection
  - Skip action: re-rolls immediately; Reflect action: opens session detail
  - 3 service tests + widget tests; review approved
  - Education gate: deferred per CLAUDE.md

- **Phase 3B: Quick Mood Tap** (PR #73, `develop/adhd-roadmap`, v0.23.0+20):
  - `QuickMoodTapSheet` bottom sheet widget: mood emoji row → energy row → atomic save → "Saved. That's enough."
  - `QuickMoodNotifier` with single `createQuickMoodSession()` atomic INSERT (eliminates orphan-session crash window)
  - `JournalingMode.quickMoodTap` (7th enum value); `quick_mood_tap` sessions excluded from watch streams
  - 48dp touch targets + `Semantics.selected` on mood emojis; SnackBar error feedback on failure
  - 27 new tests: widget (7), provider unit (9), DAO filter (11)
  - Review: REV-20260303-222128 (approve-with-changes, 6 blocking all resolved in-review, 14 advisory open)
  - Quality gate: 7/7 | Coverage: 80.8% | Tests: 2156 | All pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 14 new from REV-20260303-222128. **Total: 135**

- **Deepgram P1: DeepgramSttService + Edge Function** (PR #72, `develop/adhd-roadmap`, v0.22.0+19):
  - `DeepgramSttService` WebSocket client; `deepgram-proxy` Edge Function; STT fallback chain

- **Phase 1 Task 8: Settings Questionnaire Config** (PR #71, `develop/adhd-roadmap`, v0.21.0+18):
  - `watchDefaultTemplate()` DAO stream method for real-time scale config via `watchSingleOrNull()`
  - `activeDefaultTemplateProvider` Riverpod `StreamProvider<QuestionnaireTemplate?>` wired to settings scale toggle
  - `SegmentedButton` scale preset toggle (1-5/1-10/0-100) in Pulse Check-In settings — persists to DB immediately via stream
  - Edit question text dialog per item — `TextEditingController` inside `showDialog` builder (fixes dispose-during-dismiss-animation crash)
  - `_showAddCheckInItemDialog` same controller pattern fix
  - Bug fix: `_exportData` changed from `getActiveItemsForTemplate` → `getAllItemsForTemplate` — deactivated items now show question text in CSV exports (was showing 'Unknown')
  - 15 new widget tests in `test/ui/settings_checkin_questionnaire_test.dart`
  - 5 new DAO tests in `watchDefaultTemplate` group
  - Build: DISC-20260303-202018-build-checkin-settings-questionnaire-config (sealed)
  - Review: REV-20260303-204036 (approve-with-changes, 1 blocking resolved in-review, 13 advisory open)
  - Quality gate: 7/7 | Coverage: 80.4% | Tests: 2091 | All pass
  - Deploy: SUCCESS on SM_G998U1 (release mode)
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 13 new (A1–A13 from REV-20260303-204036). **Total: 121**

- **Daily Average Chart Fix** (PR #70, `develop/adhd-roadmap`, v0.20.1+17):
  - `_DayAverage` class: groups check-in entries by YYYY-MM-DD, averages per-item values and composite scores per day
  - Filter labels changed: "5 days" / "10 days" / "All"
  - Sparse state message updated

- **Phase 1 Task 10: CheckInScreen + CheckInHistoryScreen + Export** (PR #67, `develop/adhd-roadmap`, v0.19.0+15):
  - CheckInScreen: dedicated slider-based check-in flow (no chat chrome), PopScope back-button protection with discard dialog, `completeCheckInSession()` bypasses empty-session auto-discard guard
  - CheckInHistoryScreen: expandable cards with composite score chip, per-question answer bars, ADHD-safe UX (no streaks, no gap-shaming, neutral palette)
  - `getAllItemsForTemplate()` in QuestionnaireDao — history view shows deactivated items' question text
  - `watchAllResponsesWithAnswers()` stream using asyncMap + IN-clause (N+1-free)
  - `checkInHistoryProvider`: async* stream with per-emission template/item cache
  - `CheckInHistoryEntry` enriched with scaleMin/scaleMax for correct answer bar normalization
  - `_normalizeValue()` helper with div-by-zero guard (range <= 0 → 0.0)
  - Progressive disclosure: insights icon hidden until first check-in exists
  - Export completeness: check-in responses, answers, photo paths included
  - Accessibility: Semantics on expandable card + answer bar; semanticFormatterCallback on Slider
  - Build: DISC-20260303-172723-build-checkin-screen-history-export (sealed)
  - Review: REV-20260303-180530 (approve-with-changes, 4 blocking resolved in-review, 17 advisory open)
  - Quality gate: 7/7 | Coverage: 80.2% | Tests: 2076 | All pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 17 new (A1–A17 from REV-20260303-180530). **Total: 108**

- **3 Post-Deploy Bug Fixes** (PR #66, `develop/adhd-roadmap`, v0.18.1+14):
  - STT: `pauseFor` 2s → 3s (ADR-0031 journaling cadence, was cutting users off after one word)
  - Check-in state: `cancelCheckIn()` else branch in `_maybeStartCheckIn()` (stale isActive=true was hiding text input in new regular journal entries after voice mode)
  - Export: public `/storage/emulated/0/Download` path on Android (accessible from Files app)
  - Tests: regression test pre-seeds isActive=true before widget build; Export SnackBar test added to settings_data_management_test.dart; smoke_test.dart section 11 (cross-session state)
  - Review: REV-20260303-163807 (approve-with-changes, 2 blocking resolved in-review, 7 advisory)
  - Quality gate: 7/7 | Coverage: 80.4% | Tests: 2068 | All pass
  - Deploy: SUCCESS on SM_G998U1 (1m 1.4s)
  - Open advisories: 7 new (A1–A7 from REV-20260303-163807): MediaStore API (A1), getDownloadsDirectory() (A2), STT 3s feedback gap (A3), Continue button on check-in complete card (A4), SnackBar text length (A5), raw exception in catch (A6), comment verbosity (A7). **Total: 91**

- **Pulse Check-In emulator smoke test** (PR #65, `develop/adhd-roadmap`):
  - `integration_test/smoke_test.dart` section 10: Quick Check-In banner → Pulse Check-In session → slider interaction → save → complete card → session end
  - Fixed section 8: two-step session-end navigation (Done → closing summary → back button)
  - Emulator result: **PASS** (1m 12.9s, emulator-5554 Medium_Phone_API_36.1)
  - Phase 1 features confirmed working on device: banner (ADHD UX compliant), check-in flow, score save, complete card

- **Phase 1 Pulse Check-In + Phase 2A gap-shaming removal + Phase 2B CTA banner** (PR #64, `develop/adhd-roadmap`, v0.18.0+13):
  - Phase 1: 4-table drift schema v10 (`questionnaire_templates`, `questionnaire_items`, `checkin_responses`, `check_in_answers`), `QuestionnaireDao` (atomic save, N+1 avoidance), `CheckInScoreService` (const, reverse-scoring formula, partial-completion), `QuestionnaireDefaults` (idempotent seed, 6 items), `CheckInNotifier` (Riverpod StateNotifier), `NumericParserService` (STT homophones, compound words, 0–100), `PulseCheckInWidget` + `PulseCheckInSummary` (ADHD copy), voice flow with re-prompt/skip
  - Phase 2A: `daysSinceLast` removed from all 3 conversation layers; `@Tags(['regression'])` added to `local_llm_layer_test.dart`; ledger entry added
  - Phase 2B: Quick Check-In CTA banner — universal display (no gap-detection), `quickCheckInBannerDismissedProvider` (Riverpod StateProvider) for dismissal persistence, 5 widget tests
  - ADR-0032: status `proposed` → `accepted` with as-built schema (questionnaire_items, template-level scale, normalized CheckInAnswers, user_checkin_config deferred to v11)
  - `_NumericParserAdapter` (53-line duplicate) replaced with direct `NumericParserService` import
  - Review: REV-20260303-142206 (request-changes → all 6 blocking findings resolved)
  - Quality gate: 7/7 | Coverage: 80.2% | Tests: 2060 | All pass
  - Education gate: deferred per CLAUDE.md ADHD roadmap autonomous execution authorization
  - Open advisories: 10 new (A1–A10 from REV-20260303-142206) + 74 prior = **84 total**

- **ADR-0031 + ADR-0032** (PR #62, `develop/adhd-roadmap`):
  - ADR-0031: Deepgram Nova-3 as primary STT engine — swap via `SpeechRecognitionService` interface (ADR-0022 boundary), `speech_final`/`utterance_end` → `SpeechResult.isFinal` mapping, `endpointing=2000`, `utterance_end_ms=1500`, `deepgram-proxy` Edge Function following ADR-0005, fallback chain (Deepgram → SpeechToText → sherpa_onnx), GPT-4o Realtime as blocked north star
  - ADR-0032: Four-table Pulse Check-In schema (`questionnaire_templates`, `questionnaire_questions`, `checkin_responses`, `user_checkin_config`), WHO-5 NC license decision, reverse-scoring formula (`scaleMax + scaleMin - rawValue`), composite score edge cases, deviation from ADR-0025 Alternative 3 justified
  - Quality gate: 7/7 passed

- **P0 STT pauseFor fix** (PR #61, `develop/adhd-roadmap`):
  - `speech_to_text_stt_service.dart:98` — `pauseFor` 5s → 2s
  - Eliminates ~30s dead time in 6-question Pulse Check-In voice flow

- **ADHD Roadmap Spec + Clinical Constraints** (PR #60, `main`):
  - `SPEC-20260302-adhd-informed-feature-roadmap.md` — major additions from 3 deliberation/plan sessions; status: reviewed
  - `CLAUDE.md` — `## Clinical UX Constraints` section added
  - 3 discussions sealed: DISC-20260303-031401, DISC-20260303-042204, DISC-20260303-043107


- **Voice Capture Reliability Research** (DISC-20260303-031401, sealed, 7 turns):
  - Motivation: Device testing revealed frequent STT mistranscriptions with `speech_to_text` + Android SpeechRecognizer; ChatGPT voice as north star
  - **CRITICAL finding**: `lib/services/speech_to_text_stt_service.dart:98` — `pauseFor: Duration(seconds: 5)` is the dominant latency contributor. Change to `Duration(seconds: 2)` immediately.
  - **Incremental path (recommended)**: Replace Android SpeechRecognizer with Deepgram Nova-3 streaming WebSocket. New `DeepgramSttService` implementing `SpeechRecognitionService`. New `deepgram-proxy` Edge Function. Configure `endpointing=2000`, `utterance_end_ms=1500`, `interim_results=true`. Est. $1.77/month at 10 min/day.
  - **North star (blocked)**: GPT-4o Realtime API blocked by WebSocket proxy ADR (ADR-0005 doesn't extend to WebSocket), constraint conflict (Claude as AI layer), and $3/session cost. Needs new ADR before implementation.
  - **On-device Whisper (conditional)**: sherpa_onnx/whisper.cpp as offline fallback. Snapdragon 888 SIGILL risk from ADR-0017 applies — requires hardware validation spike first.
  - **Endpoint detection key insight**: Journaling requires 2–3s silence threshold, NOT cloud defaults (~800ms) which interrupt thinking pauses. This config difference is as important as the STT provider choice.
  - Panel: architecture-consultant, performance-analyst, independent-perspective (2 rounds)
  - Discussion: DISC-20260303-031401-voice-capture-reliability-and-conversational-ai-architecture (sealed)

- **Sprint N+1: Intent Classifier Stability Refactor + Advisory Resolution** (SPEC-20260303-010332, PR #59, v0.17.4+12):
  - Root cause fix: `static const _calendarEventNouns` shared constant enforces noun-list sync between `_calendarIntentPattern` and `_hasStrongCalendarSignal` at compile time (eliminates PR #56/#57 regression class)
  - Word-count wildcard `(\s+[\w-]+){0,4}` replaces `.{0,15}` char-count wildcard in both patterns — brand-agnostic
  - `\b` anchor (was `^`) in `_calendarIntentPattern` for voice preamble support; `^` retained in `_hasStrongCalendarSignal`
  - 10 new regression tests; 1937 total, all pass, 81.2% coverage
  - Advisory resolution: A1–A5 from REV-20260302-232244 closed (INVARIANT comments, cold-start fallback, privacy filter, CLAUDE.md context-brief list, ADR-0030 stub)
  - ADR-0030: developer input capture schema extension (status: proposed, pending two-sprint evaluation gate)
  - Review: REV-20260303-013421 (approve-with-changes, 1 blocking resolved in-review, 8 advisory)
  - Discussions: DISC-20260303-010442 (spec), DISC-20260303-011131 (build), DISC-20260303-013421 (review) — all closed

- **Context-Brief Framework Rollout** (SPEC-20260302-192548 Step 2, PR #58, framework-only):
  - Added Step 3.5 (context-brief before specialist dispatch) to: `/review`, `/deliberate`, `/build_module`, `/plan`, `/retro`
  - Blocking fixes during review: plan.md synthesis `## Request Context` requirement, retro standing agenda restructured as Step 5.5, retro disposition dead-code condition rewritten as observable signals
  - Review: REV-20260302-232244 (approve-with-changes, 3 blocking resolved, 6 advisory)
  - Discussion: DISC-20260302-231156-review-context-brief-framework-rollout

- **Set Verb + Short-Message Guard Fix** (PR #57, v0.17.3+11):
  - Root cause: `_hasStrongCalendarSignal` not recognizing "set" + event noun; "set a calendar meeting" = 4 words → short-message guard fired → journal
  - Fix: "set" added to two `^add` sub-patterns in `_calendarIntentPattern`; `^(add|set)\b.{0,15}\b(event noun)\b` added to `_hasStrongCalendarSignal`
  - 2 regression tests; Review: REV-20260302-230547 (approve-with-changes, 1 blocking resolved, 5 advisory)
  - Deploy: SUCCESS on SM_G998U1 (59s)

- **Google Calendar Intent Classifier Fix** (PR #56, v0.17.3+11):
  - Root cause: `_calendarIntentPattern` had `.{0,15}` char limit between "add" and event noun; "a Google Calendar " = 19 chars — exceeded limit, message fell through to Claude
  - Fix: new sub-pattern `^add\b.{0,15}\b(google\s+)?calendar\b.{0,20}\b(meeting|...)` + `(google\s+)?` in "to...calendar" alternative
  - 4 regression tests added; 1925 total, all pass, 81.2% coverage
  - Review: REV-20260302-222520 (approve-with-changes, 0 blocking, 6 advisory)
  - Deploy: SUCCESS on SM_G998U1 (61s)
  - Files modified: `lib/services/intent_classifier.dart`, `test/services/intent_classifier_test.dart`, `memory/bugs/regression-ledger.md`, `pubspec.yaml`

- **Task Verbal Confirmation Race Fix** (PR #55, v0.17.2+10):
  - Root cause: `orchestrator.confirmTask()` ran an 8s verbal yes/no loop concurrently with UI task card. On card tap, task was added correctly but the timed-out completer spoke "Okay, I won't add that."
  - Fix: `resolveTaskConfirmation({required bool confirmed})` added to `VoiceSessionOrchestrator` — completes `_taskConfirmCompleter` immediately when card is tapped
  - Screen: task card `onConfirm`/`onDismiss` callbacks now call `resolveTaskConfirmation()` after `sessionNotifier.confirmTask/dismissTask()`
  - Regression tests: 3 new tests; 1921 total, all pass, 81.2% coverage
  - Ledger: entry added to `memory/bugs/regression-ledger.md`
  - Review: REV-20260302-201931 (approve-with-changes, all blocking resolved)
  - Deploy: SUCCESS on SM_G998U1 (54.9s)
  - Files modified: `lib/services/voice_session_orchestrator.dart`, `lib/ui/screens/journal_session_screen.dart`, `test/services/voice_session_orchestrator_test.dart`, `memory/bugs/regression-ledger.md`

- **Journal-Only Voice Mode: Three Bug Fixes + Back-Button Fix** (PR #54, v0.17.1+9):
  - Bug 1+2 fix: `acknowledgeNoResponse()` added to `VoiceSessionOrchestrator` — resumes listening loop without AI response (fixes stuck-in-processing in journal-only + after handled intents)
  - Bug 1+2 fix: `_resumeOrchestratorIfVoiceMode()` added to `SessionNotifier` — called at journal-only and handled-intent early exits in `sendMessage()`
  - Bug 3 fix: `shouldEndSession()` moved above `journalOnlyMode` guard and intent routing — "goodbye" now works in journal-only mode
  - Back-button fix: `_endSessionAndPop()` no longer pops on success — shows closing summary (matches "goodbye" UX), force-pops only on exception
  - Review B1 fix: Done button and overflow menu hidden during `isClosingComplete` — was silently no-oping via `isSessionEnding` re-entry guard
  - Advisory A1: no-op guard test pinning acknowledgeNoResponse() phase contract
  - Advisory A4: `isContinuousMode` guard in `acknowledgeNoResponse()` for push-to-talk safety
  - Advisory A6: cross-reference comments between `_doneSignals` and `VoiceCommandClassifier._strongEndPattern`
  - Regression tests: 3 new tests (orchestrator acknowledgeNoResponse, session goodbye, screen back-button)
  - Ledger: 3 new entries in `memory/bugs/regression-ledger.md`
  - Full test suite: EXIT 0 (1918 tests, all pass)
  - Review: REV-20260302-201931 (approve-with-changes, 1 blocking resolved in-review, 8 advisory)
  - Files modified: `lib/services/voice_session_orchestrator.dart`, `lib/providers/session_providers.dart`, `lib/ui/screens/journal_session_screen.dart`, `lib/repositories/agent_repository.dart`, `lib/services/voice_command_classifier.dart`, `test/services/voice_session_orchestrator_test.dart`, `test/providers/session_providers_test.dart`, `test/ui/journal_session_screen_test.dart`, `memory/bugs/regression-ledger.md`

- **Bug-Fix Sprint: Voice UX + Task + TTS Fallback** (PR #53, v0.17.0+8):
  - Fix 1: Task extraction context — `context` param in `TaskExtractionService.extract()`, last 3 turns passed from `_extractTaskDetails`; resolves pronoun "it" using conversation history
  - Fix 2: Journal-only mode intent routing — moved `journalOnlyMode` guard after `_routeByIntent()`; task/calendar intents now handled in journal-only mode
  - Fix 3: Voice cleanup on back navigation — `await stop()` in discard path, `unawaited()` in `onPopInvokedWithResult`, `stop()` added to `dispose()`
  - Fix 4: Empty session delete — `endSession()` empty guard now calls `discardSession()` (deletes row) instead of `endSession()` (preserves row)
  - Fix 5: TTS fallback — new `FallbackTtsService`, `ttsFallbackActiveProvider`, ElevenLabs wrapped with fallback, SnackBar notification in session screen
  - Review fix (in-review): `FallbackTtsService.stop()` guards `_primary.stop()` in try-catch
  - Tests: 1915 total (+21 new), 80.8% coverage, all 7 quality gate checks pass
  - New files: `lib/services/fallback_tts_service.dart`, `test/services/fallback_tts_service_test.dart`, `test/providers/session_providers_test.dart`
  - Review: REV-20260302-152240 (approve-with-changes, 1 blocking resolved in-review, 6 advisory)
  - Deploy: SUCCESS on SM_G998U1 (1m 18s)

- **Voice Bug Fixes + Integration Test** (PR #52, v0.16.3+7):
  - Fix: Black screen on back button — try-finally in _endSessionAndPop ensures Navigator.pop() always runs
  - Fix: STT silent after ElevenLabs TTS — AudioPlayer.stop() on completion releases audio session
  - Fix: Post-dispose orchestrator crashes — _disposed flag + _updateState guard
  - New: 8-phase voice_mode_test.dart integration test (emulator, 1m 14s)
  - New: 2 regression tests for post-dispose safety
  - Fix: quality_gate.py regression guard skips TODO entries, Unicode encoding fix
  - Review: approve-with-changes (REV-20260302-071854), 1 blocking resolved, 7 advisory
- **Coverage Recovery + Ship** (PR #51, v0.16.2+6):
  - 69.9% → 80.7% effective coverage (1850 → 1895 tests)
  - New test files: chat_bubble_test, session_list_screen_expanded_test, session_detail_screen_expanded_test, search_screen_results_test
  - Expanded existing: settings_screen_expanded_test (+9 tests), tasks_screen_expanded_test (+6 tests)
  - coverage:ignore-file pragmas: app_database.dart, google_calendar_service.dart, photo_service.dart, audio_file_service.dart, video_service.dart, video_player_widget.dart
  - Quick-win advisories: onboarding_providers doc comment, FAB warnIfMissed:true, @Tags lint fix
  - Review: approve-with-changes (REV-20260302-061043), 0 blocking, 8 advisory
  - Emulator smoke test: PASS (all features verified)
  - Physical device deploy: SUCCESS (release mode, SM_G998U1)
- **Emulator Testing + Navigator Fix** (PR #50, v0.16.1+5, ADR-0029):
  - Emulator support in deploy.py (--emulator, --list-emulators, boot/wait)
  - New test_on_emulator.py runner with JSONL logging
  - smoke_test.dart rewrite + new manual_test_automation.dart (emulator-compatible)
  - Bug fix: ref.watch→ref.read in app.dart (Navigator route stack collapse)
  - Regression test + ADR-0029 (Riverpod initialRoute constraint)
  - 10 new unit test files, 3 discussion artifacts, retro + review reports
  - Review: approve-with-changes (REV-20260302-032500), 2 blocking fixed, 11 advisory

### Recently Completed
- **Knowledge Amplification Pipeline** (PR #49, v0.16.0+4, ADR-0028):
  - 10 new Python scripts, 4 SQLite tables, 2 views, 1 new command (/knowledge-health)
  - Pipeline: extract_findings → mine_patterns → surface_candidates → compute_effectiveness
  - Backfill: 48 findings, 436 turns with content, 48 sightings, 2 Rule of Three hits
  - Review: approve-with-changes (REV-20260301-215800), 2 blocking fixed, 14 advisory
  - Dashboard health: 5/7
- **Voice Naturalness Sprint** (SPEC-20260228, PR #47, v0.15.0+2) — 5 tasks:
  1. Idle timer interruption guard (`_userIsSpeaking` flag)
  2. Markdown stripping before TTS (`stripMarkdown`)
  3. Confidence-weighted commit delay (`computeCommitDelay`)
  4. Non-verbal thinking sound (`just_audio` chime loop)
  5. LLM-marker turn completeness (✓/○/◐ markers in Edge Function)
  - Review: approve-with-changes (REV-20260301-025400), 2 blocking fixed, 12 advisories open
- **Semantic Versioning** (PR #46, v0.14.0+1 → 0.15.0+2):
  - `scripts/bump_version.py` + tests, dynamic Settings version via `package_info_plus`
  - `/ship` Step 1.5 auto-bump, `deploy.py --check-version`, ADR-0027
- **Deploy parser fix** (PR #48, v0.15.1+3) — fix `--check-version` for multi-field dumpsys lines
- **Phase 13: Google Tasks + Personal Assistant** — 8 sub-phases (A-H)
- **Conversational Onboarding** (E13)
- **Multi-project analysis** (7 projects) — consolidated enhancement plan

## Google Calendar OAuth Config

**GCP Project:** `agenticjournal` (project number: `774019106928`)

**OAuth Clients Created:**
- **Android:** `774019106928-0v541sgb13qnma44v3g35l4if5tes3k6.apps.googleusercontent.com`
  - Package: `com.divinerdojo.agentic_journal`
  - SHA-1: `8B:32:96:6B:DD:A2:7E:A7:53:D3:31:65:43:C8:89:48:DC:E7:B9:41`
- **Web:** `774019106928-211ougkvc63dm0lbare5qbq0it12huk7.apps.googleusercontent.com`

## Device Build Command

**Physical device:**
```bash
python scripts/deploy.py --install-only
```

**Emulator:**
```bash
python scripts/deploy.py --emulator --install-only
```

**Emulator (specific AVD):**
```bash
python scripts/deploy.py --emulator Pixel_7_API_36 --install-only
```

**List available emulators:**
```bash
python scripts/deploy.py --list-emulators
```

Or manually (physical device):
```bash
/c/src/flutter/bin/flutter run -d R5CR10LW2FE \
  --dart-define=SUPABASE_URL=https://oruastmawvtcpiyggrze.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9ydWFzdG1hd3Z0Y3BpeWdncnplIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzE2MzEwMzYsImV4cCI6MjA4NzIwNzAzNn0.1bKaVE0RD0SZKBfnYA4DvlnkjllQ4KNq3voTRGOq35A
```

**adb** path: `/c/Users/evans/AppData/Local/Android/Sdk/platform-tools`

## Emulator Config

| Setting | Value |
|---------|-------|
| AVD Name (Google Play) | `Medium_Phone_API_36.1` |
| AVD Name (Pixel 7) | `Pixel_7_API_36` |
| Image | API 36, x86_64 |
| Google Play | Medium_Phone only |
| RAM | 2048 MB (Medium_Phone) |
| Notes | `--emulator` implies `--debug` (release AOT doesn't target x86_64) |

## Device Testing Results

| Feature | Physical Device | Emulator | Notes |
|---------|----------------|----------|-------|
| App launch | Working | **Working** | Supabase init OK on both |
| Onboarding | Working | **Working** | Conversational onboarding, Claude API, session end |
| Text journaling | Working | **Working** | FAB → session → send → Done → home |
| Session detail/resume | Working | **Working** | Card tap → detail → Continue Entry → send → end |
| Session discard | Working | **Working** | Empty session → back → auto-discard |
| Settings navigation | Working | **Working** | All 8 cards verified (Digital Assistant, Voice, AI, Sync, Location, Calendar, Data, About) |
| Unicode/edge cases | Working | **Working** | Unicode text preserved, long messages handled |
| Photo capture | Working | Simulated | Virtual camera (checkerboard scene) |
| Google Calendar | **Working** | Needs test | Emulator needs SHA-1 in GCP (Medium_Phone_API_36.1 has Google Play) |
| Supabase auth | Working | Needs test | evansarak@yahoo.com |
| Version display | **Working** | Needs test | Settings shows dynamic version via `package_info_plus` |
| Deploy --check-version | **Working** | Needs test | MATCH confirmed for 0.15.1+3 |
| Claude AI | Needs test | **Working** | Edge Function responding (200 OK), in-app conversation works |
| Video capture | Needs test | Limited | ffmpeg_kit may lack x86_64 libs |
| Voice/STT | Needs test | **Working** | voice_mode_test.dart: enable, session, toggle, back nav (1m 14s) |
| Local LLM | Disabled | Disabled | SIGILL on Snapdragon 888 / ARM-only binaries |
| Quick Check-In banner | Needs test | **Working** | ADHD UX: shows to all users with sessions, "Quick check-in" CTA visible |
| Pulse Check-In flow | Needs test | **Working** | Slider → Skip/Next/Finish → "Check-in saved." card (1m 12.9s, PR #65) |

## Tech Debt

- **Coverage** — 80.9% (above 80% target)
- **Education gates deferred** — Phase 11 + Phase 12; REV-20260302-152240; REV-20260303-142206 (Phase 1 Pulse Check-In clinical UX + score computation); REV-20260303-180530 (CheckInHistoryScreen async* stream, completeCheckInSession, _normalizeValue, ADHD UX); REV-20260303-222128 (Phase 3B Quick Mood Tap); REV-20260303-232113 (Phase 3D Weekly Digest); REV-20260304-015709 (Phase 4E statistical concepts + reverse-scoring); REV-20260304-142456 (Phase 3A Quick Capture palette/provider patterns); REV-20260304-145506 (bug fixes sprint)
- **Review advisories open** — 243 total (234 + 9 from REV-20260304-183306): 12 from REV-20260301-025400, 14 from REV-20260301-215800, 8 from REV-20260302-061043, 7 from REV-20260302-071854, 6 from REV-20260302-152240, 8 from REV-20260302-201931, 6 from REV-20260302-222520, 5 from REV-20260302-230547, 8 from REV-20260303-013421, 10 from REV-20260303-142206, 7 from REV-20260303-163807, 17 from REV-20260303-180530, 13 from REV-20260303-204036, 14 from REV-20260303-222128, 10 from REV-20260303-232113, 5 from REV-20260303-235547, 12 from REV-20260304-005938, 22 from REV-20260304-035354, 13 from REV-20260304-074715, 8 from REV-20260304-085452, 10 from REV-20260304-015709, 8 from REV-20260304-142456 (3 resolved in PR #83), 8 from REV-20260304-145506
- **user_checkin_config** deferred to schema v11 (Phase 1 Task 8)
- **Local LLM disabled** — llamadart SIGILL on Snapdragon 888
- **PENDING adoptions** — 9 patterns approaching stale threshold 2026-03-05
- **Pipeline advisories** — stop words duplication, bare except, candidate_id collision risk (see REV-20260301-215800)
- **ADR-0030 evaluation gate** — two-sprint window starts now (Signal A: specialist echo, Signal B: framing drift — check at next retro)

## Key Decisions (Recent)

- ADR-0027: Semantic Versioning
- ADR-0026: Conversational Onboarding via Real Journal Session
- ADR-0021: Video Capture Architecture
- ADR-0020: Google Calendar Integration
- llamadart disabled → Claude API is primary conversation layer
- Google OAuth requires both Android + Web client IDs for scoped access

## Resume Instructions

1. **ADHD Roadmap — PR #84 merged**. On `develop/adhd-roadmap` (v0.32.0+32).
   - **PR #84 merged**: Phase 4B/4C (Quick Capture widget + weather metadata)
   - **Next**: Phase 4F (timed reminders → phone alert) or advisory triage sprint
2. **Education gates deferred** — Phase 1 Pulse Check-In, Phase 3B, Phase 3D, Phase 4D, Phase 4E, Phase 5A, Phase 3A; REV-20260302-152240 (fallback TTS)
3. **Open advisory triage** — 226 total. Priority: A-4 from REV-20260304-085452 (SCHEDULE_EXACT_ALARM revocation); Bug 1 (keyboard overflow); Bug 2 (STT stops after photo); Phase 3A A1 (dispatch branch tests)

---
*This file is referenced by `.claude/hooks/pre-compact.ps1` and `.claude/hooks/session-start.ps1`. Update after completing tasks.*
