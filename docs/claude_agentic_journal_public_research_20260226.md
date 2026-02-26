# Agentic Journal: comprehensive technical research across six domains

**The Flutter voice-first journaling space has no direct open-source precedent, but a rich ecosystem of components exists to build one.** This investigation across GitHub repositories, on-device LLM solutions, STT engines, UX patterns, Android assistant APIs, and sync architectures reveals that the most impactful improvements come from three areas: fixing the SIGILL crash via flutter_gemma or build-flag correction, upgrading to Sherpa ONNX's built-in Silero VAD for proper endpoint detection, and adopting PowerSync for sync. The findings span 23+ GitHub projects, 9 shipped voice apps, 12+ Flutter packages for LLM inference, and 6 sync solutions — all evaluated against the constraints of a voice-first Android journaling app targeting diverse hardware.

---

## Research Area 1: No Flutter voice journal exists yet, but key reference projects emerge

Across 10 targeted GitHub searches, **no open-source Flutter app combines voice conversation loops with journal storage and AI analysis** — confirming that Agentic Journal occupies a genuine gap. However, several projects provide architectural blueprints for specific subsystems.

**FlutterVoiceFriend** (github.com/jbpassot/flutter_voice_friend, 30⭐) is the single most relevant reference. It implements a complete voice conversation loop: on-device STT (`speech_to_text`) plus cloud STT (Deepgram) → LLM processing (Langchain + OpenAI) → TTS (OpenAI voices) → auto-re-listen. Its activity-based conversation flow model — where structured "activities" guide conversation stages with prompts and responses — maps directly to journaling prompts. The dual STT strategy (on-device for speed, cloud for accuracy) matches Agentic Journal's architecture. Its license is CC BY-NC-SA 4.0 (non-commercial), so code can be studied but not reused directly.

**LiveKit Agent Starter Flutter** (71⭐, MIT license) provides a production-quality voice assistant starter with clean separation of voice, text, and video modalities. The agent framework handles conversation loops server-side with proper token management and connection state via a central controller. **Sherpa ONNX** (7,800⭐, Apache 2.0, v1.12.26 released Feb 24, 2026) provides the most complete offline voice engine with Flutter examples for streaming ASR, TTS, VAD, and speaker diarization.

| Project | Stars | Relevance | Key Pattern |
|---------|-------|-----------|-------------|
| FlutterVoiceFriend | 30 | Full voice conversation loop with dual STT | Activity-based conversation state machine |
| LiveKit Agent Starter | 71 | Production voice assistant infrastructure | Clean modality separation, MIT license |
| Sherpa ONNX | 7,800 | Offline STT/TTS/VAD engine with Flutter bindings | Streaming ASR + Silero VAD integration |
| MooDiary | 1,700 | Cross-platform diary with local AI advocacy | Privacy-first architecture patterns |
| StoryPad | 100K+ downloads | Journal UX patterns | Flutter diary UI/UX reference |
| Picovoice Porcupine | 3,000+ | Wake word detection with Flutter SDK | "Hey Journal" activation pattern |
| Alan AI Flutter SDK | 1,700 | Conversational AI SDK | Cloud-based voice commands |

The canonical voice interaction state machine discovered across projects follows: **IDLE → LISTENING → PROCESSING → RESPONDING → LISTENING (loop)**, with error branches from each state. Android's platform `speech_to_text` imposes a **~5-second silence timeout** at the OS level that cannot be changed — projects work around this by auto-restarting listening and concatenating results, or by using Sherpa ONNX which has no platform timeout.

**Gaps**: No project demonstrates voice journaling with mood analysis, pattern recognition across entries, or journal-specific AI prompting. The diary apps (MooDiary, StoryPad, DiaryVault) are all text-first with no voice capabilities.

**Recommendations**: Study FlutterVoiceFriend's conversation state machine and adapt its activity model for journaling prompts. Use LiveKit's modality separation pattern. The biggest architectural insight is that **Sherpa ONNX should replace `speech_to_text` as primary STT** for continuous journaling sessions to avoid the 5-second timeout limitation.

---

## Research Area 2: The SIGILL crash has a known cause and three viable fix paths

The Snapdragon 888's Kryo 680 cores (ARM Cortex-A78) implement **ARMv8.2-A**, supporting NEON/ASIMD, FP16, and DOTPROD instructions. The llama.cpp project's official Android docs recommend building with `-march=armv8.7a`, which emits instructions (SVE, i8mm, bf16, ls64) that the Cortex-A78 cannot execute. **GitHub issue #12393** in ggml-org/llama.cpp documents this exact crash: "Loading models results in Fatal signal 4 (SIGILL) on some Android devices" when compiled with `-march=armv8.7a`. The fix is confirmed: removing or lowering the flag eliminates the crash.

The llamadart package downloads pre-built binaries from GitHub Releases, meaning users inherit whatever build flags the maintainer used. Three fix paths exist, ranked by viability:

**Option 1 — Switch to flutter_gemma** (recommended). This package uses Google's MediaPipe GenAI SDK, which handles CPU compatibility automatically across all Android devices — **zero SIGILL risk**. It now supports **Qwen 2.5, Qwen 3 0.6B, Gemma 3, Phi-4 Mini, and DeepSeek R1** in `.task` or `.litertlm` format, with GPU acceleration and NPU support on compatible devices. Migration requires converting the model to MediaPipe format but keeps the same Qwen model family.

**Option 2 — Switch to Cactus** (best for production). This Y Combinator-backed SDK (500K+ weekly inference tasks) uses custom ARM-specific SIMD kernels explicitly optimized for Snapdragon, Exynos, and MediaTek chips. Benchmarks show **Qwen3-600m-int8 running at 16–20 tok/sec on Pixel 6a and 70+ tok/sec on Galaxy S25 Ultra**. It supports GGUF models, tool calling, RAG, and includes cloud fallback. The tradeoff is that v1 moved from GGUF to a proprietary `.cact` format.

**Option 3 — Fix llamadart build flags** (minimal change). Fork llamadart and rebuild with `-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod -DGGML_NATIVE=OFF`. This targets all ARMv8.2+ devices (Snapdragon 845+) while retaining DOTPROD optimization. The Qwen 2.5 0.5B GGUF model works unchanged. Risk: maintaining a fork across llamadart updates.

| Package | SIGILL Safe | Qwen 2.5 Support | GPU | Migration Effort |
|---------|------------|-------------------|-----|-----------------|
| flutter_gemma | ✅ Auto-handled | ✅ Direct | ✅ Yes | Medium |
| Cactus | ✅ Custom ARM kernels | ✅ GGUF | NPU | Medium |
| llamadart (fixed) | ✅ If rebuilt | ✅ Unchanged | Vulkan | Low |
| mediapipe_genai (official) | ✅ Auto-handled | ⚠️ Needs conversion | ✅ Yes | Medium |
| llama_cpp_dart | ✅ If compiled right | ✅ Any GGUF | Manual | High |

For the **Qwen 2.5 0.5B model**, aggressive quantization is unnecessary — even Q8_0 at ~530 MB fits easily in 8–12 GB RAM. **Q6_K (~420 MB) or Q8_0 (~530 MB) are recommended** since quality degradation below Q4 is disproportionate on sub-1B models. Total runtime RAM including KV cache at 2048 context: ~500–600 MB.

**MLC-LLM** (22K stars) delivers excellent performance (16 tok/sec on Snapdragon 8 Gen 2 via OpenCL GPU) but has **no Flutter bindings** — open issues #344 and #766 remain unanswered. Integration would require significant platform channel work. **Not recommended** for Flutter.

---

## Research Area 3: Sherpa ONNX is the right offline STT — enhance it with built-in VAD

The current dual-engine approach (Google on-device primary + Sherpa ONNX Zipformer fallback) is sound, but the research reveals that **Sherpa ONNX should be elevated to primary for continuous journaling sessions**, with `speech_to_text` reserved for quick interactions where the platform timeout isn't problematic.

**Whisper-based STT in Flutter** exists through several packages (whisper_flutter_new, whisper_ggml_plus, whisper_kit), but Whisper is fundamentally **batch-only** — it cannot stream. Users must record first, then transcribe. The base.en model (142 MB, ~4.3% WER) offers excellent accuracy but adds seconds of latency after each utterance. For a voice-first app where real-time transcription creates the conversational feel, **Whisper is unsuitable as primary STT**. It has value as a post-recording re-transcription engine for higher accuracy, run in the background after a journaling session ends.

**Vosk** has Flutter bindings (vosk_flutter, vosk_flutter_service) and supports streaming, but uses older Kaldi TDNN architecture. The small model (~40 MB) achieves **~15–25% WER** versus Sherpa ONNX's estimated 5–8% with modern Zipformer models. Multiple Flutter forks suggest fragmentation. **Vosk offers no advantage over the current Sherpa ONNX setup and is not recommended.**

The critical enhancement is **Silero VAD integration**, which is already built into Sherpa ONNX (no additional dependency). Current configuration recommendations for journaling:

- `threshold`: **0.3** (catches softer, reflective speech)
- `min_silence_duration`: **0.8–1.0s** (natural pauses in journaling without premature cutoff)
- `max_speech_duration`: **30s+** (journals involve long continuous speech)
- `min_speech_duration`: **0.25s** (filters non-speech sounds)

| Technology | Model Size | Streaming | WER (English) | Offline | Best For |
|-----------|-----------|-----------|--------------|---------|----------|
| speech_to_text (Google) | 0 (OS) | ✅ Real-time | ~5–10% | Partial | Quick interactions |
| Sherpa ONNX Zipformer | 15–25 MB (int8) | ✅ Real-time | ~5–8% | ✅ Full | Continuous journaling |
| Whisper base.en | 142 MB | ❌ Batch | ~4.3% | ✅ Full | Post-session cleanup |
| Vosk small | 40 MB | ✅ Streaming | ~15–25% | ✅ Full | Not recommended |
| Google Cloud STT | 0 (cloud) | ✅ Streaming | ~3–5% | ❌ | Premium accuracy tier |

**Partial result handling** should show interim text immediately in a visually distinct style (lighter opacity or italic), replacing with final text on confirmation. Update the UI every 100–200 ms rather than on every callback to prevent flickering. For `speech_to_text`, use `partialResults: true` with `ListenMode.dictation` and implement auto-restart on timeout with accumulated text across sessions.

**Recommended three-tier architecture**: Tier 1 (online) — `speech_to_text` for quick entries. Tier 2 (offline/continuous) — Sherpa ONNX with Silero VAD for journaling sessions. Tier 3 (optional) — Whisper batch re-transcription in background for accuracy improvement. Total offline package size: **~32–42 MB** (Sherpa ONNX library + Zipformer int8 model + Silero VAD).

---

## Research Area 4: Shipped apps reveal a convergence toward unified voice-plus-text interfaces

Analysis of nine shipped voice apps reveals a major industry shift: **ChatGPT unified its voice mode with text chat in November 2025**, eliminating the separate full-screen voice overlay that previously locked users out of their conversation history. This signals that the voice-first future is not voice-only — it's voice-plus-text in a single view. For Agentic Journal, this means showing real-time transcription as the user speaks, with AI responses appearing as conversational bubbles in the same scrollable view.

**Pi by Inflection** proves that a voice-first companion app succeeds with an extremely minimal UI. Its onboarding — ask name, select from 8 voices, immediately start conversation — achieves the ideal of zero-friction voice engagement. The design philosophy: "When a system is hard to approach, the design must be soft." Pi's single-screen conversation interface, warm synthetic voices, and emotional tone detection directly inform the journaling use case. It lacks journaling-specific features (no entry storage, no pattern recognition), which is precisely the gap Agentic Journal fills.

**Rosebud AI Journal** validates the AI-guided journaling model: conversational AI asks follow-up questions, provides reflections, tracks patterns across entries. Its "go deeper" button — prompting the AI to ask more probing questions — is a differentiator for therapeutic journaling. However, **user reviews report voice-to-text reliability issues with entries not saving**, teaching a critical lesson: raw voice data must always be preserved independently of AI processing. Capture first, analyze second.

**Google Gemini Live's visual design language** — from the official Google Design team — establishes the gold standard for voice state visualization. Concentrated and diffused gradients represent voice transcription. The foundational shape is the circle (simplicity, harmony, comfort). Rippling radial gradients represent voice waves. Inner motion conveys thinking. This organic, soft approach is far more appropriate for a reflective journaling context than aggressive waveforms or sharp UI elements.

Key UX decisions for Agentic Journal based on shipped app analysis:

- **Recording trigger**: Large center-bottom mic FAB that pulses/glows during recording. Tap-to-toggle with auto-endpointing (VAD detects speech end). Continuous listening as opt-in for power users.
- **Visual feedback during listening**: Soft pulsing gradient circle (Gemini-inspired), not a technical waveform. Text is the hero — transcription appears in real-time as the primary visual element.
- **AI response states**: Gentle shimmer during "thinking," streaming text for responses. Avoid aggressive loading animations that break reflective mood.
- **Error recovery**: Always preserve raw audio. Allow inline text editing of transcripts. AI post-processing cleans up transcription automatically (Reflect's pattern).
- **Onboarding**: Conversational first-run — AI greets by voice, explains in 2–3 sentences, asks an easy opener ("How was your day?"). No front-loaded permissions or settings.
- **Lock screen and background**: Recording status widget on lock screen (Reflect's pattern). Background recording support (Gemini Live's pattern). Notification controls for pause/resume.

**Gaps**: No shipped app combines all three of: voice conversation loops, structured journaling storage, and cross-entry AI pattern recognition. Concept designs on Dribbble (freud v2 AI Mental Health App by strangehelix) explore this intersection but haven't shipped.

---

## Research Area 5: VoiceInteractionService is the right path, but requires native Kotlin

The current `ACTION_ASSIST` intent filter approach is the simplest registration method, but **a voice-first app should implement the full `VoiceInteractionService`** for system-level capabilities that a simple intent cannot provide. The distinction matters significantly:

`ACTION_ASSIST` simply launches an activity when the user long-presses Home. It provides no background service, no lock screen invocation, no always-on listening, and no system-level session management. `VoiceInteractionService` is a system-bound service that runs continuously when selected as the default assistant, providing **lock screen invocation** via `onLaunchVoiceAssistFromKeyguard()`, an overlay window for showing UI on top of the current app, `AlwaysOnHotwordDetector` access, and assist data from the foreground app.

This distinction becomes critical on **Android 12+**, where microphone foreground services cannot be started from the background. VoiceInteractionService bypasses this restriction because it is system-bound and always running when selected as default assistant. This is **the strongest argument for implementing VoiceInteractionService** — it solves the background microphone access problem that plagues regular foreground services.

Open-source references for implementation include **Dicio** (github.com/Stypox/dicio-android, GPLv3) — the most complete open-source assistant using Vosk STT and OpenWakeWord — and **ArezooNazer/VoiceInteractionSample**, which combines VoiceInteractionService with Porcupine hotword detection. The AOSP test project (ToxicBakery/VoiceInteraction) provides the minimal reference implementation.

For wake word detection ("Hey Journal"), **Porcupine** (porcupine_flutter, 10K+ GitHub stars) is the production choice: >97% detection rate, ~10 KB per keyword, excellent Flutter integration via `flutter_voice_processor`, and custom wake words trainable in seconds via Picovoice Console. The tradeoff is commercial licensing beyond the free tier. **openWakeWord** is the fully free alternative but has no native Flutter package — only an Android proof-of-concept port exists, requiring custom platform channel work.

**No Flutter package exists for VoiceInteractionService.** Flutter issue #172408 documents this gap. All native Android code must be hand-written in Kotlin:

| Phase | What | Effort | Gain |
|-------|------|--------|------|
| Phase 1 (now) | Keep ACTION_ASSIST + add ROLE_ASSISTANT via RoleManager | 2–3 days | Proper role management on Android 10+ |
| Phase 2 (medium-term) | Full VoiceInteractionService in Kotlin with platform channels | 1–2 weeks | Lock screen access, system lifecycle, overlay UI |
| Phase 3 (enhancement) | Porcupine wake word inside VoiceInteractionService process | 1 week | "Hey Journal" hands-free activation |

The `ROLE_ASSISTANT` API (Android 10+, API 29) via `RoleManager` is the modern way to become the default assistant. The app must declare `ACTION_ASSIST` intent to qualify, then request the role programmatically. Android 14–15 tightened foreground service restrictions but did **not deprecate** VoiceInteractionService or ROLE_ASSISTANT — these APIs remain stable and supported, with the AOSP automotive voice interaction guide updated as recently as December 2025.

---

## Research Area 6: PowerSync with Drift is the strongest sync architecture

For a journaling app with Drift (SQLite) locally and Supabase as the backend, **PowerSync emerges as the clear recommendation**. It is a dedicated sync engine that automatically synchronizes Postgres (Supabase) with in-app SQLite, and it has first-class Flutter and Supabase support — both listed as launch partners.

The critical finding is that **PowerSync works with Drift** via `SqliteAsyncDriftConnection`. PowerSync manages the underlying SQLite database while Drift connects to it as a typed query layer, preserving your existing type-safe queries and schema. The read path streams data from Supabase Postgres to local SQLite via configurable Sync Rules (YAML-based). The write path uses a local upload queue processed by a developer-defined connector that calls Supabase APIs. Conflict resolution is custom — you implement it in your upload handler.

PowerSync's maturity comes from its origin: spun off from JourneyApps Platform with **10+ years in production**. It offers a free tier (soft limits, no credit card), usage-based Pro pricing (~$51/mo for 5K DAU), and a self-hostable Open Edition for cost control. Multiple demo apps exist (Todo, Chat, Trello clone) with extensive documentation.

**Syncable** (github.com/Mr-Pepe/syncable, 34⭐) is the lightweight alternative purpose-built for the exact Drift + Supabase stack. Tables implement a `SyncableTable` interface adding `updatedAt` and `deleted` columns, and a Postgres trigger implements last-write-wins resolution. It uses Supabase Realtime for change subscriptions and includes smart device presence tracking. The tradeoff is a single maintainer and limited feature set — but for an MVP, it's the fastest path with zero infrastructure overhead.

| Solution | Works with Drift | Supabase Integration | Sync Service Required | Maturity | Effort |
|----------|-----------------|---------------------|----------------------|----------|--------|
| PowerSync | ✅ Via bridge | ✅ First-class | Yes (cloud or self-hosted) | Very high | Medium |
| Syncable | ✅ Native | ✅ Native + Realtime | No | Low-medium | Low |
| Brick | ❌ Replaces Drift | ✅ Dedicated package | No | High | High |
| ElectricSQL | ❌ Read-path only | ✅ Any Postgres | Yes | Pivoting | N/A |
| remote_cache_sync | ✅ Via adapter | ✅ Via adapter | No | Low | Medium |

**Last-write-wins (LWW)** is the appropriate conflict resolution strategy for journaling. Entries are mostly append-only, the data is single-user, and the implementation is trivial — a Supabase Postgres trigger comparing `updated_at` timestamps. CRDTs are overkill for this use case (designed for multi-user collaborative editing). Consider field-level merge only for journal metadata (tags, mood ratings) while using LWW for content bodies.

**ElectricSQL is not suitable.** It pivoted to "Electric Next" with only read-path sync — the write path is gone, and the Dart client maintainer considers it "deprecated until previous features are reintroduced." **Brick** (by GetDutchie, featured on official Supabase blog) is a strong framework but **replaces Drift entirely** with its own ORM, requiring a full data layer rewrite.

**Recommended architecture**: PowerSync + Drift + Supabase for production, or Syncable + Drift + Supabase for MVP. Store audio files in Supabase Storage (synced separately from metadata). Use PowerSync Sync Rules to partition data per user. Add background sync via `workmanager` package for when the app is closed.

---

## Conclusion: a prioritized implementation roadmap

This research reveals that Agentic Journal's core architecture is sound, but three changes deliver outsized impact. **First, resolve the SIGILL crash** — the quickest path is forking llamadart with corrected build flags (`-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod`), but switching to flutter_gemma provides a permanent, zero-maintenance solution that also unlocks GPU acceleration. **Second, promote Sherpa ONNX to primary STT** for journaling sessions, using its built-in Silero VAD for endpoint detection, eliminating the Android 5-second silence timeout that breaks continuous journaling flow. **Third, adopt PowerSync** to replace manual Supabase sync — it integrates with Drift via `SqliteAsyncDriftConnection` and handles all sync complexity (queuing, retry, conflict detection, real-time updates) that is error-prone to build manually.

Beyond these three, the research surfaces a key strategic insight: **implement VoiceInteractionService** rather than relying on a simple ACTION_ASSIST intent. This unlocks lock screen access, system-managed lifecycle, and — critically — background microphone access that Android 12+ otherwise restricts. Combined with Porcupine wake word detection running inside the VoiceInteractionService process, this enables true hands-free "Hey Journal" activation.

The UX research confirms a design direction: follow ChatGPT's November 2025 evolution toward unified voice-plus-text, use Gemini's soft gradient visual language for voice states, adopt Pi's minimal conversational onboarding, and always preserve raw audio independently of transcription (learning from Rosebud's reliability complaints). The voice-first journaling app that combines these patterns with reliable offline-first sync does not yet exist in the open-source ecosystem — Agentic Journal occupies a genuine and validated gap.