---
discussion_id: DISC-20260224-061221-phase8b-llm-integration-review
started: 2026-02-24T06:17:55.126319+00:00
ended: 2026-02-24T06:18:40.402281+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260224-061221-phase8b-llm-integration-review

## Turn 1 — architecture-consultant (proposal)
*2026-02-24T06:17:55.126319+00:00 | confidence: 0.91*
*tags: architecture, phase8b, strategy-pattern, provider-wiring*

APPROVE WITH CHANGES. Confidence: 0.91. 6 findings: (1) MEDIUM: localLlmServiceProvider as StateProvider creates uncontrolled mutation path — document in ADR-0017 or use StateNotifier with controlled access. (2) MEDIUM: LlmModelDownloadService depends on STT model_download_service.dart for shared types — extract to dedicated file or document intent. (3) LOW: Redundant on ClaudeApiException catch blocks in all 4 AgentRepository methods — consolidate to single on Exception. (4) LOW: Filename derivation duplicated across 3 sites — expose modelFileName static getter. (5) LOW: Bare catch(e) in LlamadartLlmService stub — change to on Exception catch(e). (6) INFO: PersonalityConfig cleartext in SharedPreferences — flag for future ADR if health data classification changes. Strengths: constructor injection correct per ADR-0007, session-lock lifecycle sound, sanitization applied at both model and provider layers, coverage:ignore boundary clean, getTimeOfDay extraction minimal-DRY.

---

## Turn 2 — security-specialist (proposal)
*2026-02-24T06:18:04.022582+00:00 | confidence: 0.88*
*tags: security, prompt-injection, supply-chain, sha256*

APPROVE WITH CHANGES. Confidence: 0.88. 6 findings: (1) MEDIUM: Incomplete ChatML marker blocklist — missing [INST], <|system|>, <|start_header_id|>, ### Instruction: formats. Recommend documenting Qwen=ChatML coupling and wrapping custom prompt in labeled block. (2) MEDIUM: Size-only bypass in isModelDownloaded/llmModelReadyProvider skips SHA-256 — corrupted or replaced same-size file passes. Recommend mtime-based re-verification. (3) MEDIUM: User journal entries passed unsanitized to generateSummary LLM context — inherent LLM limitation, recommend output validation and fallback. (4) LOW: Bare catch(_) in fromJsonString swallows Error types — narrow to on FormatException. (5) LOW: _fileNameFromUrl accepts any URL without path separator assertion — pre-emptive path traversal guard. (6) LOW-INFO: STT model SHA-256 fields still empty — pre-existing debt, flag for pre-release. Trust boundaries verified: custom prompt isolation holds structurally at provider level. SHA-256 chunked verification correct. Defensive JSON deserialization sound. WiFi gate at service layer.

---

## Turn 3 — qa-specialist (proposal)
*2026-02-24T06:18:12.234711+00:00 | confidence: 0.87*
*tags: qa, testing, coverage, edge-cases*

APPROVE WITH ADVISORY. Confidence: 0.87. 8 findings: (1) MEDIUM: Missing boundary test for daysSinceLast==1 vs >=2 threshold in getGreeting. (2) MEDIUM: localLlmLayerProvider conditional logic has no unit test — service null, not loaded, loaded cases. (3) MEDIUM: Dialog error/retry flow untested — failed status UI and Retry button. (4) MEDIUM: Missing test for prefer-Claude ON + offline + local LLM available scenario. (5) LOW: sanitizeCustomPrompt truncation at 500 may split surrogate pairs — no Unicode boundary test. (6) LOW: generateSummary with empty userMessages and no allMessages untested for LocalLlmLayer. (7) LOW: setCustomPrompt with whitespace-only string untested. (8) LOW: Bare catch(_) in download dialog violates coding standard — change to on Exception. Coverage 80.7% meets gate. Sanitization tests thorough (34 tests). Fallback chain well-tested. Mock design clean. Session-lock behavior explicitly verified. coverage:ignore exclusions all justified.

---

## Turn 4 — independent-perspective (proposal)
*2026-02-24T06:18:19.912852+00:00 | confidence: 0.82*
*tags: anti-groupthink, lifecycle-gap, ram, pre-mortem*

APPROVE WITH ADVISORY. Confidence: 0.82. Key findings: (1) HIGH: Model load lifecycle gap — no code path from download completion to localLlmServiceProvider being set. Feature is structurally a no-op until wired. (2) MEDIUM: OOM risk — Qwen 0.5B needs ~570-760MB RAM loaded, no guard against simultaneous STT+LLM load on mid-range devices. (3) MEDIUM: systemPrompt field deserializable from SharedPreferences without sanitization — rooted device can replace base therapeutic prompt. (4) LOW: Resume via HTTP Range headers doesn't validate server response (206 vs 200). (5) LOW: Personality config included in Android Auto Backup by default. Hidden assumptions: llamadart API shape unverified against stubs, stub loadModel sets _isLoaded=true unconditionally. Pre-mortem: Scenario 1 (silent fallback, feature never works) is highest likelihood. Alternatives considered: lazy-load/eager-unload per session, feature-flag wrapper for stub, signed manifest for model updates. Strengths: fallback chain graceful degradation, chunked SHA-256 correct, effectiveSystemPrompt append-not-replace architecture sound, session-locked layer prevents UX failure.

---

## Turn 5 — facilitator (synthesis)
*2026-02-24T06:18:40.402281+00:00 | confidence: 0.88*
*tags: blocking:2, advisory:18*

VERDICT: approve-with-changes. 4 specialists reviewed 12 files (6 new, 6 modified). Blocking: 2. Advisory: 18.

BLOCKING FINDINGS (must fix before merge):
B1. Bare catch violations — 3 sites violate coding_standards.md: (a) local_llm_service.dart stub catch(e) → on Exception catch(e), (b) personality_config.dart fromJsonString catch(_) → on FormatException, (c) llm_model_download_dialog.dart catch(_) → on Exception. [arch F5, sec F4, qa F8]
B2. Redundant catch blocks — AgentRepository has redundant on ClaudeApiException + on Exception in all 4 methods. The ClaudeApiException clause is dead code since on Exception catches it. Consolidate to single on Exception with explanatory comment. [arch F3]

ADVISORY FINDINGS (recommended, don't block):
A1. Model load lifecycle gap — no code wires download completion to model loading in localLlmServiceProvider. Feature is structurally a no-op. [indep F1 — HIGH, but Phase 8C scope per spec]
A2. Incomplete ChatML blocklist — sanitizer covers Qwen/ChatML but misses [INST], <|system|> etc. Document Qwen coupling, consider wrapping custom prompt in labeled block. [sec F1]
A3. Size-only bypass skips SHA-256 on re-launch — corrupted same-size file passes. Consider mtime-based re-verification. [sec F2]
A4. localLlmServiceProvider as StateProvider — uncontrolled mutation path. Document in ADR-0017 or use StateNotifier. [arch F1]
A5. Missing test: localLlmLayerProvider conditional logic (null service, not loaded, loaded). [qa F2]
A6. Missing test: prefer-Claude ON + offline + local LLM available → local LLM serves. [qa F4]
A7. Missing test: daysSinceLast boundary (1 vs 2 days) in getGreeting. [qa F1]
A8. Missing test: dialog error/retry flow (failed status UI, Retry button). [qa F3]
A9. Shared download types coupled to STT model_download_service.dart — extract or document. [arch F2]
A10. Filename derivation duplicated across 3 sites. [arch F4]
A11. OOM risk — no guard against simultaneous STT+LLM model load. [indep F2]
A12. systemPrompt field deserializable without sanitization from SharedPreferences. [indep F3]
A13. Unicode surrogate pair splitting at 500-char truncation boundary. [qa F5]
A14. Empty userMessages + null allMessages in LocalLlmLayer.generateSummary untested. [qa F6]
A15. setCustomPrompt whitespace-only path untested. [qa F7]
A16. HTTP Range response not validated (206 vs 200). [indep F4]
A17. Personality config in Android Auto Backup. [indep F5]
A18. STT model SHA-256 fields still empty (pre-existing). [sec F6]

STRENGTHS: Constructor injection correct per ADR-0007. Session-lock lifecycle sound. Custom prompt isolation holds structurally. Chunked SHA-256 correct. Fallback chain graceful. Sanitization thorough (34 tests). coverage:ignore boundary clean. effectiveSystemPrompt append-not-replace design correct.

---
