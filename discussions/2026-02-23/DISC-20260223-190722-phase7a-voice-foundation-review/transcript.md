---
discussion_id: DISC-20260223-190722-phase7a-voice-foundation-review
started: 2026-02-23T19:11:08.123410+00:00
ended: 2026-02-23T19:11:44.323590+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist, ux-evaluator]
total_turns: 5
---

# Discussion: DISC-20260223-190722-phase7a-voice-foundation-review

## Turn 1 — architecture-consultant (proposal)
*2026-02-23T19:11:08.123410+00:00 | confidence: 0.88*
*tags: architecture, phase7a, voice*

Architecture review: 7 findings (2 medium, 3 low, 2 info). Key: (1) ModelDownloadService instantiated inline in _startRecording bypasses provider container [M]; (2) sttModelReadyProvider duplicates file-existence logic from ModelDownloadService [M]; (3) TTS ref.listen side effect inside _buildInputField method [L]; (4) Empty SHA-256 checksums [L]; (5) Double stop() in TTS dispose [L]; (6) AudioFocusService implemented but never wired into recording flow [L]; (7) voiceModeEnabledProvider not persisted across restarts [Info]. Strengths: clean module boundaries, correct dependency direction, platform channel consistency with AssistantRegistrationService, well-justified coverage:ignore markers, inputMethod threading is minimal-change.

---

## Turn 2 — qa-specialist (proposal)
*2026-02-23T19:11:15.507447+00:00 | confidence: 0.88*
*tags: qa, testing, phase7a, voice*

QA review: 10 findings (1 high, 6 medium, 3 low). Key: (1) wasVoiceInput logic bug — _isRecording already false when _sendMessage runs after endpoint auto-stop, voice messages always stored as TEXT [H]; (2) Model download dialog retry+completion flows untested [M]; (3) isOnWifi() testable but has zero tests [M]; (4) _startRecording race: no guard against double-tap during async init [M]; (5) TTS speak() called before initialize() — error silently swallowed, isSpeaking state leak [M]; (6) downloadProgress stream should test broadcast behavior [M]; (7) stopListening race with async _startAudioCapture [M]; (8) No tests for _previousTranscriptId dedup guard [L]; (9) Zero voice-specific widget tests for mic/stop/recording UI states [L]; (10) Double stop() in TTS dispose [L]. Strengths: coverage:ignore principled, AudioFocusService tests thorough, SpeechResult equality tests correct, mock implementations faithful, test isolation clean.

---

## Turn 3 — security-specialist (proposal)
*2026-02-23T19:11:23.008294+00:00 | confidence: 0.87*
*tags: security, phase7a, voice, supply-chain*

Security review: 5 findings (1 high, 1 medium, 3 low). Key: (1) Empty SHA-256 checksums — model files downloaded from HuggingFace with no integrity verification, loaded directly into sherpa_onnx native FFI runtime, could enable code execution via crafted ONNX model [H/A08:2021]; (2) Resume-on-partial path has no integrity check on existing bytes [M/A08:2021]; (3) foregroundServiceType=microphone on Activity instead of Service element [L/A05:2021]; (4) TTS catch-all swallows errors with no logging [L/A09:2021]; (5) Platform channel arguments cast without type guard [L/A01:2021]. Trust boundary analysis: HuggingFace CDN → file → sherpa_onnx FFI is the meaningful gap. Audio pipeline is process-local, no interception risk. Storage location correct (app-private). HTTPS throughout.

---

## Turn 4 — ux-evaluator (proposal)
*2026-02-23T19:11:28.806136+00:00 | confidence: 0.87*
*tags: ux, accessibility, phase7a, voice*

UX review: 11 findings (4 high, 5 medium, 2 low). Key: (1) 5-8s STT initialization after download has NO loading indicator — user sees frozen screen [H]; (2) TTS never initialized before use — speak silently fails; no speaking indicator; no interrupt [H]; (3) Back navigation during recording loses utterance with no warning [H]; (4) Disabled Download on Wi-Fi button implies deferred action but has no auto-detect [H]; (5) Indeterminate progress bar shown on failure state contradicts error text [M]; (6) Mic/stop/send buttons have no accessibility tooltips — screen readers announce bare Button [M]; (7) Recording indicator relies on color alone (red) — inaccessible [M]; (8) wasVoiceInput bug — voice messages always logged as TEXT [M]; (9) Disabled button label confusing [M]; (10) No proactive download from Settings [L]; (11) Model status row lacks Semantics label [L]. Strengths: multi-cue recording state, escalating thinking indicator, WiFi gating UX, auto-stop on endpoint, PopScope confirmation, good settings card positioning.

---

## Turn 5 — facilitator (synthesis)
*2026-02-23T19:11:44.323590+00:00 | confidence: 0.87*
*tags: blocking:5, advisory:15*

SYNTHESIS: Phase 7A Voice Foundation Review

VERDICT: APPROVE WITH CHANGES

BLOCKING FINDINGS (5):
1. [SHA-256 checksums empty] Model files downloaded from HuggingFace with no integrity verification. ONNX files loaded into native FFI runtime — supply chain risk. Populate checksums and implement streaming SHA-256 verification. (security-specialist HIGH, architecture-consultant LOW)
2. [wasVoiceInput logic bug] _isRecording is already false when _sendMessage runs after endpoint auto-stop. Voice messages always stored as inputMethod=TEXT. Need separate _lastInputWasVoice flag. (qa-specialist HIGH, ux-evaluator MEDIUM)
3. [TTS never initialized] FlutterTextToSpeechService.initialize() never called. speak() throws StateError, silently swallowed. TTS will never work. Add lazy init in _speakAssistantMessage. (ux-evaluator HIGH, qa-specialist MEDIUM)
4. [STT init loading indicator] 5-8s model load after download has no UI feedback. User sees frozen screen. Show spinner during initialize(). (ux-evaluator HIGH)
5. [Accessibility: no tooltips on action buttons] Mic/stop/send buttons have no tooltip — screen readers announce bare Button. Add tooltip to all three states. (ux-evaluator MEDIUM, cross-cutting)

ADVISORY FINDINGS (15):
6. ModelDownloadService instantiated inline, should be provider (arch)
7. sttModelReadyProvider duplicates file list from ModelDownloadService (arch)
8. TTS ref.listen inside _buildInputField instead of build() (arch)
9. AudioFocusService never wired into recording flow (arch)
10. voiceModeEnabledProvider not persisted (arch info)
11. Double stop() in TTS dispose (arch+qa)
12. Download dialog retry/completion flows untested (qa)
13. isOnWifi() testable but untested (qa)
14. _startRecording double-tap race condition (qa)
15. Zero voice-specific widget tests (qa)
16. foregroundServiceType=microphone on Activity not Service (security)
17. Disabled Download on Wi-Fi button misleading (ux)
18. Indeterminate progress bar on failure state (ux)
19. Recording indicator color-only (ux)
20. Back navigation during recording loses utterance (ux)

CONFIDENCE: 0.87
RISK: Medium

---
