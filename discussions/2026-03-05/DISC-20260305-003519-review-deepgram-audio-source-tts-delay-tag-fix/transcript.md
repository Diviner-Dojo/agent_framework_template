---
discussion_id: DISC-20260305-003519-review-deepgram-audio-source-tts-delay-tag-fix
started: 2026-03-05T00:35:36.140738+00:00
ended: 2026-03-05T00:48:27.337543+00:00
agents: [facilitator, performance-analyst, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260305-003519-review-deepgram-audio-source-tts-delay-tag-fix

## Turn 1 — facilitator (evidence)
*2026-03-05T00:35:36.140738+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix Deepgram STT not transcribing on Samsung Galaxy S21 Ultra (Android 14) after ElevenLabs TTS playback; fix USER-only messages for metadata regeneration after message edit
- **Files/scope**: lib/services/deepgram_stt_service.dart (AndroidAudioSource.voiceRecognition + manageBluetooth:false), lib/providers/voice_providers.dart (ttsReleaseDelay 150ms→500ms), lib/ui/screens/session_detail_screen.dart (_regenerateSummary USER-only filter)
- **Developer-stated motivation**: Three device testing bugs: (1) Deepgram STT listens but never transcribes — silence timer fires every 15s; (2) Tag extraction uses stale ASSISTANT messages after user corrects a name in their transcript; (3) Audio mode conflict between just_audio TTS and AudioRecord
- **Explicit constraints**: Must not break existing emulator test (Listening state shows, no WebSocket errors); must not require PROXY_ACCESS_KEY change; Samsung S21 Ultra (Android 14, One UI) specific audio routing issue

---

## Turn 2 — qa-specialist (proposal)
*2026-03-05T00:41:13.647811+00:00 | confidence: 0.82*
*tags: f1:blocking, f2:advisory, f3:advisory, f4:advisory*

## QA Review: Deepgram Audio Source + TTS Delay + TAG Fix

**Confidence: 0.82**

### F1 — HIGH (Blocking): No Regression Test for USER-only Filter in _regenerateSummary
session_detail_screen.dart _regenerateSummary() now filters to USER-only messages before passing to generateSummary(). This is the key correctness fix, but there is no regression test verifying that allMessages contains no ASSISTANT role entries after a message edit. A mock AgentRepository must capture the allMessages argument and assert no 'assistant' role entries exist. Without this test, the fix is invisible to the regression suite and a future refactor could silently re-introduce ASSISTANT messages corrupting metadata extraction.

### F2 — MEDIUM (Advisory): Missing Regression Ledger Entries for Two New Bugs
Two new bugs were diagnosed and fixed this session: (1) Deepgram AudioSource silence on Samsung after TTS; (2) ttsReleaseDelay increased to 500ms. Neither has a ledger entry in memory/bugs/regression-ledger.md. Per commit_protocol.md Step 1.5, every bug fix requires a ledger entry documenting root cause, fix, and test location.

### F3 — MEDIUM (Advisory): Empty userMessages Guard Needs Comment
session_detail_screen.dart line ~470: 'if (userMessages.isEmpty) return;' — the caller's finally block resets _isRegenerating, so this early return is safe. But the comment does not exist and readers will wonder if the finally block is bypassed. Add: '// Safe early return: caller finally block handles _isRegenerating reset.'

### F4 — LOW (Advisory): Weak Assertion in Message Editing Widget Test
session_detail_screen_test.dart:309: findsAtLeastNWidgets(1) on 'Sean helped me today.' This could mask duplicate rendering (same text appearing in both bubble and summary header). Scope the finder to a ChatBubble descendant or use findsOneWidget to make the assertion precise.

---

## Turn 3 — performance-analyst (proposal)
*2026-03-05T00:41:26.208476+00:00 | confidence: 0.87*
*tags: f1:advisory, f2:blocking, f3:advisory, f4:advisory, f5:advisory*

## Performance Review: Deepgram Audio Source + TTS Delay + TAG Fix

**Confidence: 0.87**

### F1 — LOW (Advisory): Double getMessagesForSession Queries in _regenerateSummary
_regenerateSummary() calls getMessagesForSession() once for userMessages (filter WHERE role='USER') and a second time for allMessages (same call, then .toList()). At current message volumes this is negligible (<100ms). Consider a single query with in-memory partition if latency budgets tighten, but no action required now.

### F2 — MEDIUM (Blocking): ttsReleaseDelay Unconditional on Platform
voice_providers.dart ttsReleaseDelay: const Duration(milliseconds: 500) fires on all platforms. The root cause (just_audio MODE_NORMAL vs AudioRecord conflict) is Android-specific. On iOS, an unconditional 500ms delay adds latency with no benefit. dart:io is already imported. Fix: ttsReleaseDelay: Platform.isAndroid ? const Duration(milliseconds: 500) : Duration.zero

### F3 — LOW (Advisory): Disabled Noise Suppression Upstream Load
echoCancel/noiseSuppress/autoGain all false in RecordConfig. This sends raw ambient audio to Deepgram rather than pre-processed audio. Deepgram's server-side nova-3 model handles this well; accept as intentional tradeoff per ADR-0031.

### F4 — LOW (Advisory): Combined stopListening + ttsReleaseDelay = 1000ms Dead Time per Turn
stopListening() has a hardcoded 500ms Deepgram CloseStream flush delay. ttsReleaseDelay adds another 500ms. Total dead time at each turn boundary is ~1000ms on Android. This is acceptable for journaling cadence but worth tracking if response latency becomes a complaint.

### F5 — LOW (Advisory): Double Iteration for userMessages/allMessages
_regenerateSummary builds userMessages (filtered list) then passes it as both userMessages and allMessages to generateSummary(). The second reference is a no-op copy. Sub-millisecond, no action needed.

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T00:48:27.337543+00:00 | confidence: 0.9*
*tags: blocking:2, advisory:7, verdict:approve-with-changes*

## Request Context
- **What was requested**: Fix Deepgram STT not transcribing on Samsung Galaxy S21 Ultra (Android 14) after ElevenLabs TTS playback; fix USER-only messages for metadata regeneration after message edit; increase TTS release delay for audio routing
- **Files/scope**: lib/services/deepgram_stt_service.dart, lib/providers/voice_providers.dart, lib/ui/screens/session_detail_screen.dart
- **Developer-stated motivation**: Three device testing bugs: (1) Deepgram STT listens but never transcribes on Samsung One UI after TTS; (2) metadata extraction uses stale ASSISTANT messages after user corrects a transcript; (3) audio focus release timing too aggressive
- **Explicit constraints**: Must not break emulator test; must not require proxy changes; Samsung S21 Ultra (Android 14) audio routing specific

## Verdict: Approve with Changes

**Changes resolved in-review: 2 blocking fixed before commit.**

### Blocking Findings (2 — all resolved)

**B1 (QA)**: No regression test for USER-only filter in _regenerateSummary. **RESOLVED**: Added _SpyAgentRepository subclass and testWidgets regression test '_regenerateSummary passes only USER messages to generateSummary (regression)' in test/ui/session_detail_screen_test.dart. Test captures allMessages arg and asserts no 'assistant' role entries. 12/12 tests pass.

**B2 (Performance)**: ttsReleaseDelay 500ms unconditional on all platforms. **RESOLVED**: Changed to Platform.isAndroid ? const Duration(milliseconds: 500) : Duration.zero in voice_providers.dart. iOS gets Duration.zero (no penalty).

### Advisory Findings (7 open)

**A1 (QA)**: Missing regression ledger entries for two new bugs. RESOLVED: Added rows for Deepgram audio source fix and ttsReleaseDelay platform guard to memory/bugs/regression-ledger.md.

**A2 (QA)**: userMessages.isEmpty early return lacked explanation comment. RESOLVED: Added '// Safe early return: caller's finally block resets _isRegenerating.' comment.

**A3 (QA-LOW)**: findsAtLeastNWidgets(1) assertion in session_detail_screen_test.dart:309 may mask duplicate rendering. Advisory — acceptable given summary+bubble can both show corrected text.

**A4 (Performance-LOW)**: Double getMessagesForSession calls in _regenerateSummary. Negligible at current scale. Advisory — consider single-pass partition if latency budget tightens.

**A5 (Performance-LOW)**: Disabled noise suppression (echoCancel/noiseSuppress=false) sends raw ambient audio to Deepgram. Accepted as intentional tradeoff — Deepgram nova-3 handles server-side noise reduction per ADR-0031.

**A6 (Performance-LOW)**: Combined stopListening 500ms + ttsReleaseDelay 500ms = ~1000ms dead time per turn on Android. Acceptable for journaling cadence. Track if users report response latency.

**A7 (Performance-LOW)**: Double iteration for userMessages/allMessages (same filtered list). Sub-millisecond, no action needed.

### Strengths
- AndroidAudioSource.voiceRecognition is the correct STT source — same as Google Voice Search, avoids MODE_IN_COMMUNICATION conflict with just_audio
- manageBluetooth:false prevents Bluetooth SCO negotiation (also requires MODE_IN_COMMUNICATION) — complete fix
- USER-only allMessages filter is architecturally clean and well-commented
- _SpyAgentRepository test subclass is a clean pattern without mocking libraries
- Comment in deepgram_stt_service.dart explains Samsung-specific reasoning clearly

### Education Gate
Medium risk. Education gate deferred per CLAUDE.md ADHD roadmap autonomous execution authorization. No blocking conceptual gaps identified.

---
