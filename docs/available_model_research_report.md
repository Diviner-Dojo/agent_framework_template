# On-device small language models for budget Android in 2026

**The best realistic setup for a Flutter journaling-to-assistant app on a 3–4 GB RAM Android phone is a hybrid architecture: a tiny TFLite classifier (~15 MB) handling intent detection and entity extraction at 5–30 ms latency, paired with Qwen 2.5 0.5B or Gemma 3 1B loaded on-demand via llama.cpp for conversation and summarization.** This combination keeps peak RAM under 1.2 GB, works fully offline, and uses only Apache 2.0 / permissive-licensed components. On budget hardware (Snapdragon 600-series, MediaTek Helio), expect 8–25 tokens/second for generation—usable but noticeably slower than cloud APIs. The quality gap versus Claude is real: a 1B model produces adequate summaries and simple conversations but cannot match Claude's nuanced reasoning. The pragmatic "Tier 2.5" approach—local classifiers always on, a small local LLM for offline generation, and Claude API as a fallback for complex queries when online—delivers roughly **80% of the value at 20% of the complexity**.

---

## The brutal math of 3–4 GB RAM

On a budget Android phone with 3–4 GB total RAM, the operating system and background services consume **1.5–2 GB** before your app even launches. A Flutter app with the Dart VM adds another 100–200 MB. That leaves roughly **1–1.5 GB** for a model, its key-value cache, and the inference runtime. This constraint eliminates every model above ~1.5B parameters at 4-bit quantization and forces aggressive context-window limits.

The KV cache is the hidden budget-killer. Each token cached costs memory proportional to the model's layer count and hidden dimension. For a 1B-parameter model, 512 tokens of KV cache consume ~30–50 MB; at 2048 tokens that rises to ~120–200 MB. On a 3 GB phone, targeting **512–1024 tokens of context** is realistic. On a 4 GB phone, 1024–2048 tokens becomes feasible with a sub-1B model. Memory-mapped loading (mmap), which llama.cpp supports natively, avoids duplicating the full model weights in RAM and is essential for this tier of device.

The inference speed picture is equally constrained. Academic benchmarks from 2024–2025 show that older Armv8-A cores (Cortex-A76/A77, typical in Snapdragon 600-series and MediaTek Helio chips) deliver only **2–5 tokens/second** for a 1B Q4 model in decode mode. Newer Armv9-A cores with `smmla`/`sdot` SIMD instructions (Cortex-X4, found in Snapdragon 8 Gen 2+) achieve 15–30 tokens/second. Your users on ₹10,000–₹15,000 phones will sit squarely in the slower bracket.

---

## Which models actually fit: a ranked shortlist

After evaluating every major sub-3B model released through early 2026, only a handful fit the RAM envelope. The table below covers confirmed quantized file sizes, estimated inference RAM, and licensing.

| Model | Params | Q4 disk size | Est. RAM (512 ctx) | License | Strength |
|---|---|---|---|---|---|
| **Qwen 2.5 0.5B Instruct** | 494M | ~380 MB | ~600 MB | Apache 2.0 | Best quality-to-size; strong instruction-following; JSON output |
| **Gemma 3 1B IT (QAT int4)** | 1B | ~500 MB | ~700 MB–1 GB | Gemma Terms | Google's QAT preserves quality; 140+ languages; 32K context |
| **Llama 3.2 1B Instruct** | 1.26B | ~750 MB | ~1.0–1.2 GB | Llama Community | Knowledge-distilled from 70B; strong intent classification when fine-tuned |
| **SmolLM2 360M Instruct** | 360M | ~200 MB | ~400 MB | Apache 2.0 | Outperforms all sub-500M models; good for classification |
| **TinyLlama 1.1B** | 1.1B | ~670 MB | ~900 MB | Apache 2.0 | Fast inference; mature GGUF ecosystem; 2024-vintage quality |
| **Gemma 3 270M** | 270M | ~150 MB | ~300 MB | Gemma Terms | Ultra-light; simple classification and NER only |
| **SmolLM2 135M** | 135M | ~80 MB | ~200 MB | Apache 2.0 | Near-instant inference; intent routing only |

Two borderline models deserve mention. **Qwen 2.5 1.5B Instruct** (Q4_K_M, ~1.0 GB on disk, ~1.3–1.5 GB RAM) is the best sub-2B model in raw benchmarks—**61% MMLU, 68% HellaSwag**—and handles summarization and conversation competently. It can run on 4 GB phones with a 512-token context window and aggressive KV cache quantization, but will cause memory pressure on 3 GB devices. **SmolLM2 1.7B** matches or exceeds it on several metrics (MT-Bench 6.13, trained on 11 trillion tokens) and is equally borderline.

Models that are definitively too large include Phi-3/Phi-4 Mini (3.8B, ~2.2 GB Q4, needs ~2.5 GB RAM), Gemma 2 2B (2.6B, ~1.5 GB Q4), Llama 3.2 3B (~1.9 GB Q4), and Qwen 2.5 3B. Mistral offers nothing below 7B. Google's Gemma 3n E2B (5B total, ~2B effective) uses a novel Per-Layer Embedding architecture that reduces memory to ~2 GB, but this remains borderline for budget hardware and tooling support is still maturing.

A critical caveat: **small models are more sensitive to quantization than large ones**. Research shows Llama 3.2 1B drops from 99% accuracy at Q5 to 89% at Q4_K_M and collapses to 60% at Q3_K_M on intent classification tasks. Prefer Q4_K_M or Q5_K_M over more aggressive quantization; the disk savings of Q3 aren't worth the quality cliff at this scale.

---

## Three architectural tiers for your journaling assistant

### Tier 1: One model does everything

Deploy a single Qwen 2.5 0.5B or Gemma 3 1B that handles intent classification, entity extraction, conversation, and summarization through prompt engineering. This is the simplest architecture—one GGUF file, one llama.cpp instance, one integration path.

**Resource profile:** 380–750 MB on disk, 600 MB–1.0 GB RAM, 8–25 tokens/second on budget SoCs. Classification latency is 200–500 ms (the model must generate a structured response). Summarizing a 500-word journal entry (producing ~200 tokens) takes **10–25 seconds** on a Snapdragon 695-class chip.

**Quality reality:** A 0.5B model achieves roughly 80–85% intent classification accuracy (fine-tuned), ~70–75% NER F1, and produces basic but often imprecise summaries. A 1B model improves to ~85–90% classification accuracy and adequate short-text summarization. Neither can maintain coherent multi-turn conversation beyond 2–3 exchanges. Fine-tuning on domain-specific journaling data can close much of this gap for classification and extraction.

### Tier 2: Tiny classifier plus on-demand generator

This hybrid pairs a purpose-built TFLite classifier (TinyBERT or MobileBERT, INT8-quantized to **15–25 MB**) for intent classification and named entity recognition with a larger llama.cpp model (Qwen 2.5 1.5B or Llama 3.2 1B) loaded on-demand for generation tasks.

**Resource profile:** The classifier stays always-resident at ~50–60 MB RAM. When the user triggers a conversational or summarization feature, the generator loads in 3–8 seconds (cold start from UFS 2.1 storage) and occupies 1.0–1.4 GB. Total peak RAM: ~1.3–1.5 GB. On a 4 GB phone, this works well. On a 3 GB phone, it requires sequential loading—unloading the generator after each use.

**Quality advantage:** Classification drops from 200–500 ms (Tier 1) to **5–30 ms** because a fine-tuned BERT-class model is far more efficient for classification than prompting a generative LLM. NER accuracy also improves: specialized token-classification models trained on CoNLL-03 or SNIPS data reliably extract dates, times, and names at **85–90% F1** versus ~75% from a general-purpose 0.5B model. The generator handles conversation and summarization at the same quality as Tier 1.

**Pre-trained options exist.** TensorFlow Lite Model Maker supports text classification out of the box with MobileBERT or Average Word Vec architectures. HuggingFace's `distilbert-base-cased-finetuned-conll03-english` can be exported to ONNX and converted to TFLite for NER. Fine-tuning on the SNIPS intent dataset (which covers categories like calendar, reminder, and note-taking) maps almost directly to your use case.

### Tier 3: Local classifier plus Claude API

Keep only the TFLite classifier on-device (~30 MB disk, ~50 MB RAM) and route all generation to the Claude API. This eliminates the large model download entirely and delivers **Claude-quality conversation and summarization** with sub-3-second latency over a mobile connection.

**Cost:** At Claude 3.5 Haiku pricing ($0.80/MTok input, $4/MTok output), a typical journal interaction costs ~$0.001. For 1,000 daily active users averaging 10 interactions each, monthly API cost is roughly **$360**. The critical trade-off is **offline capability**: without connectivity, your app can classify intents and extract entities but cannot generate responses or summaries.

### The pragmatic Tier 2.5: best of all worlds

The recommended "starter" approach combines all three tiers into a graceful-degradation stack:

- **Always on:** TFLite intent classifier + NER model (~50 MB RAM). Handles routing instantly.
- **Offline generation:** Qwen 2.5 0.5B Q4 via llama.cpp (~600 MB RAM when loaded). Produces acceptable summaries and simple conversational responses.
- **Online enhancement:** When connected, route complex queries (multi-paragraph summarization, nuanced follow-up) to Claude API for dramatically better quality.

This gives users a fully functional offline experience while delivering cloud-quality results when available—and the connectivity check can happen transparently after the local classifier determines the task type.

---

## Runtime and Flutter integration: the practical path

### llama.cpp is the clear winner for this use case

Among all evaluated runtimes—llama.cpp, MLC LLM, MediaPipe, ONNX Runtime Mobile, TFLite, ExecuTorch, and Qualcomm AI Engine Direct—**llama.cpp dominates for budget Android with Flutter**. Its advantages are decisive: mmap-based loading avoids RAM duplication, the runtime binary adds only ~10–20 MB overhead, it works on any ARM Android device via pure CPU with NEON optimizations, and it has the largest ecosystem of Flutter bindings.

MLC LLM explicitly crashes on devices with less than 8 GB RAM. MediaPipe's LLM API is "intended for experimental and research use only" on Android and targets Pixel 8+ class hardware. ExecuTorch's documentation states "you will need 16GB of RAM" for its Android Llama example. Qualcomm AI Engine Direct requires proprietary SDKs and targets flagship Snapdragon SoCs with capable NPUs—budget chips have weak or absent Hexagon NPU cores.

### Flutter packages are mature enough for production

The pub.dev ecosystem now offers several viable paths to llama.cpp from Flutter:

| Package | Approach | Key strengths |
|---|---|---|
| **`llama_cpp_dart`** | dart:ffi, 3 abstraction levels | Most mature (69 likes, 950+ downloads); managed isolate for non-blocking UI; MIT license |
| **`fllama`** (Telosnex) | dart:ffi + WASM | Web + native parity; OpenAI-compatible API; GPL v2 with commercial licenses |
| **`cactus`** | Native SDK | Official Flutter package; includes LLM + speech-to-text + RAG + cloud fallback; Y Combinator–backed |
| **`flutter_gemma`** | MediaPipe wrapper | Supports Gemma 3, Qwen, DeepSeek, SmolLM via MediaPipe .task format; GPU/CPU backends |
| **`llm_toolkit`** | Multi-engine | Combines llama.cpp (GGUF) + TFLite (Gemma) + Whisper ASR + RAG + HuggingFace model download |

The **recommended integration pattern** is dart:ffi with a background isolate. The model loads on a separate Dart isolate (avoiding UI jank), calls llama.cpp's C API via FFI bindings generated by `ffigen`, and streams tokens back to the main isolate through a `SendPort`. This is the pattern used by `llama_cpp_dart`, `llamafu`, and the `edge_veda` SDK. Platform channels via MethodChannel are simpler to set up but add ~30 ms serialization overhead per call—acceptable for streaming tokens but unnecessary given mature FFI options.

For the TFLite classifier component in Tier 2/2.5, the **`tflite_flutter`** package (v0.10.0+) is well-established, production-tested, and supports GPU delegates. It coexists cleanly with llama.cpp since both are separate native libraries with no dependency conflicts.

**Cactus** deserves special attention as a newer entrant. It's the only runtime with a first-party Flutter SDK purpose-built for mobile LLM inference, with benchmarks showing Qwen3-0.6B running at 16–20 tokens/second on a Pixel 6a. It includes cloud fallback, tool calling, and speech-to-text in a single package. The risk is its relative youth and smaller community compared to llama.cpp.

---

## Licensing: stick to Apache 2.0 for simplicity

For a commercial app bundling model weights, **Apache 2.0 licensed models eliminate all legal ambiguity**. The cleanest options:

- **Qwen 2.5 0.5B / 1.5B** — Apache 2.0, no restrictions, no branding requirements
- **SmolLM2** (all sizes) — Apache 2.0, fully open including training data
- **TinyLlama 1.1B** — Apache 2.0, independently trained (not subject to Meta's Llama license)
- **IBM Granite** — Apache 2.0, enterprise-backed
- **RWKV** (all sizes) — Apache 2.0, unique RNN architecture with O(1) inference memory

Llama 3.2 1B is usable commercially but requires displaying "Built with Llama" branding in your UI and has a 700M monthly active user threshold above which you need a separate Meta license. Gemma models allow commercial use but Google's terms include a clause permitting remote restriction of usage they deem violating their Prohibited Use Policy—a provision that gives some enterprise legal teams pause. Microsoft's Phi models carry the pristine MIT license, but at 3.8B parameters they don't fit the RAM budget. **Avoid Apple's OpenELM entirely**—its Apple Sample Code License prohibits commercial redistribution.

---

## What to expect versus Claude, and where to start

A local 0.5B–1B model operating within 1 GB of RAM will produce results roughly equivalent to GPT-3.5-era quality for simple tasks—adequate intent detection, basic entity parsing, and coherent but shallow conversation. **Summarization is the biggest quality gap**: Claude can distill a 2,000-word journal session into a nuanced 3-sentence summary capturing emotional tone and key themes; a 1B model tends to produce extractive bullet points that miss subtext. Multi-turn conversation degrades after 2–3 exchanges due to the constrained context window.

However, **fine-tuning transforms the equation for structured tasks**. Research demonstrates that a fine-tuned Llama 3.2 1B achieves 99% accuracy on intent classification matching GPT-4.1, and fine-tuned BERT-class models routinely match or exceed general-purpose LLMs on NER and classification. The journaling app's four task categories (journal entry, calendar appointment, reminder, other) are well-suited to a fine-tuned classifier.

### The recommended starter approach

Start with Tier 2.5, implemented in three phases:

**Phase 1 (week 1–2):** Integrate `tflite_flutter` with a MobileBERT intent classifier fine-tuned on SNIPS or a custom dataset of your four categories. Add a rule-based date/time parser (regex + Dart's `intl` package) for the most common NER patterns. This alone covers the core routing logic with ~50 MB RAM and instant response times.

**Phase 2 (week 3–4):** Add `llama_cpp_dart` or `cactus` with Qwen 2.5 0.5B Q4_K_M as an on-demand generator. Implement lazy loading: the model downloads on first use (~380 MB) and loads into memory only when generation is requested. Wire up summarization and simple conversational prompts. Test on actual budget hardware—emulators will not reveal memory pressure.

**Phase 3 (week 5+):** Add Claude API integration as an optional enhancement. When online, route summarization and complex conversation to Claude for noticeably better quality. Store the user's connectivity preference and degrade gracefully to the local model when offline. This gives you the best quality achievable while maintaining full offline functionality.

This phased approach ships a useful product at each stage, avoids over-engineering upfront, and lets real usage data guide whether to invest in fine-tuning the local model further or leaning more heavily on cloud inference.