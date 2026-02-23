---
discussion_id: DISC-20260222-233425-phases-6-11-plan-review
started: 2026-02-22T23:34:37.943631+00:00
ended: 2026-02-22T23:39:48.201182+00:00
agents: [architecture-consultant, facilitator, independent-perspective, performance-analyst, security-specialist, ux-evaluator]
total_turns: 7
---

# Discussion: DISC-20260222-233425-phases-6-11-plan-review

## Turn 1 — facilitator (proposal)
*2026-02-22T23:34:37.943631+00:00 | confidence: 0.8*
*tags: plan-review, phases-6-11*

Initiating structured dialogue review of Phases 6-11 project plan. Plan covers: Phase 6 (session management UX), Phase 7 (voice mode), Phase 8 (local LLM + personality), Phase 9 (photo integration), Phase 10 (location awareness), Phase 11 (Google Calendar). Five specialists dispatched: architecture-consultant, security-specialist, performance-analyst, independent-perspective, ux-evaluator. Goal: assess plan quality, identify risks, build integration approach.

---

## Turn 2 — architecture-consultant (critique)
*2026-02-22T23:38:52.659297+00:00 | confidence: 0.8*
*tags: plan-review, architecture*

12 findings across architecture, schema, boundaries, and complexity. HIGH: (1) ADR-0006 Layer C redefinition collision — existing Layer C is memory recall, not local LLM; needs four-layer or sub-strategy redesign. (2) RAM pressure from concurrent Whisper+Qwen models underestimated as Medium, should be High. (3) AgentRepository exceeds design scope — codebase itself recommended extraction at line 18-19. MEDIUM: (4) Phase 9 splits one logical schema change across v3+v4 unnecessarily. (5) Supabase schema sync strategy underspecified. (6) Voice loop orchestration will bloat SessionNotifier. (7) Phase 7 XL estimate realistic but Task 7.9 (session resume) is independent and should be split out. (8) AgentLayer enum needs llmLocal value. (9) Calendar intent detection conflicts with existing IntentClassifier. LOW: (10) Model download is unproxied external dependency. (11) Missing ADR for permission management. (12) Personality config in SharedPreferences vs drift inconsistency. Phase 11 may be underscoped — OAuth alone routinely consumes a full sprint.

---

## Turn 3 — security-specialist (critique)
*2026-02-22T23:39:04.384436+00:00 | confidence: 0.8*
*tags: plan-review, security*

10 findings across 6 trust boundaries. HIGH: (1) Model download checksum source unspecified — MITM risk on 2GB Hugging Face download, SHA-256 must be hardcoded in binary. (2) Location data synced at full GPS precision to Supabase — GDPR risk, recommend precision reduction to 1km and opt-in default. (3) Photo EXIF metadata not stripped — leaks GPS coordinates even when location feature is disabled. (4) Google OAuth scope underspecified — full calendar vs minimal events-only scope. MEDIUM: (5) Personality customPromptOverride in SharedPreferences modifiable on rooted devices. (6) Audio buffer lifecycle unspecified for sherpa_onnx continuous STT. (7) Storage exhaustion during model download could leave truncated files loaded by native parser. (8) Photo localPath from Supabase sync is path traversal risk if used directly. LOW: (9) Foreground service type microphone needed for background STT on Android 10+. (10) Custom prompt override must not leak to Claude API server-side system prompt.

---

## Turn 4 — performance-analyst (critique)
*2026-02-22T23:39:17.118572+00:00 | confidence: 0.8*
*tags: plan-review, performance*

9 findings. CRITICAL: (1) Memory coexistence — Whisper + Qwen + Flutter on 6GB device leaves 300-500MB margin, dangerously thin. Must constrain Whisper to base.en variant. (2) Voice loop latency chain — realistic 7-11s dead silence per turn with GPU, 10-18s on CPU. Must implement streaming TTS from LLM tokens and reduce silence timeout. HIGH: (3) 2GB model download needs WiFi-only gate, resume via dio Range headers, storage check. (4) No isolate strategy — llamadart and sherpa_onnx FFI calls may block Dart isolate. Must verify FFI binding types before Phase 7-8. (5) Battery drain from continuous STT needs audio focus handling for phone calls and navigation conflicts. MEDIUM: (6) Photo sync N+1 pattern — parallelize uploads within sessions. (7) Landing page watchAllSessions() with no LIMIT grows linearly. (8) GPS cold start 5s timeout — use getLastKnownPosition() first. (9) Local photo storage unbounded — needs eviction policy or cloud-only-after-sync option. Critical path: benchmark llamadart on target device BEFORE writing voice loop code.

---

## Turn 5 — independent-perspective (critique)
*2026-02-22T23:39:28.852980+00:00 | confidence: 0.8*
*tags: plan-review, independent*

8 hidden assumptions identified, 5 pre-mortem scenarios, 4 alternative perspectives. KEY ASSUMPTIONS CHALLENGED: (1) sherpa_onnx and llamadart stability assumed from pub.dev scores — llamadart is pre-1.0 (0.6.2), API can break in minor versions. (2) Android audio focus conflicts with navigation apps not mentioned — high likelihood during driving. (3) 2s silence heuristic presented as settled but needs VAD-based detection (sherpa_onnx supports this natively). (4) Deferred education gates (Phases 3,4,5) creating compounding knowledge gap. (5) Google OAuth verification process for Calendar scope not acknowledged. ALTERNATIVES PROPOSED: (A) Split Phase 7 into 7A (push-to-talk validation) and 7B (continuous mode) to derisk native integration. (B) Defer Phase 8 entirely — validate voice mode with Claude API first before committing to on-device LLM. (C) Consider 1B parameter model for 2-3s inference instead of 3B at 5-10s. (D) Use sherpa_onnx VAD instead of timer-based silence detection. PRE-MORTEM: sherpa_onnx native build failure blocks entire voice vision with no fallback STT package.

---

## Turn 6 — ux-evaluator (critique)
*2026-02-22T23:39:41.753650+00:00 | confidence: 0.8*
*tags: plan-review, ux*

11 findings across voice UX, navigation, accessibility, multimodal flows. CRITICAL: (1) Voice mode error paths completely unspecified — STT failure, LLM timeout, TTS crash all leave user stranded while driving with no verbal recovery. (2) Discard action has no verbal path — contradicts zero-touch claim. HIGH: (3) Model download UX missing cellular warning, wrong lifecycle timing (should be post-first-session), no verbal fallback announcement. (4) 3-level drill-down (month->day->session) triples navigation depth — recommend flat list with sticky headers instead. (5) 2s silence threshold wrong for driving — recommend 3.5s default with VAD, user-configurable. (6) Verbal close command fuzzy matching risks false positives mid-sentence — use LLM intent detection instead. (7) Photo capture fundamentally incompatible with hands-free driving — must be explicitly scoped as text-mode-only. MEDIUM: (8) Calendar OAuth interrupts voice session with no recovery path. (9) No accessibility section — missing Semantics wrappers, no deaf user path. (10) Layer fallback changes personality mid-session — lock layer per session. LOW: (11) Silent empty session discard should show brief SnackBar feedback.

---

## Turn 7 — facilitator (synthesis)
*2026-02-22T23:39:48.201182+00:00 | confidence: 0.8*
*tags: plan-review, synthesis*

SYNTHESIS: 5 specialists produced 50 findings across architecture, security, performance, UX, and risk. The plan is well-researched with strong package selection rationale and honest risk identification. However, 8 cross-cutting themes emerged requiring plan revision before implementation begins. See full synthesis in discussion transcript.

---
