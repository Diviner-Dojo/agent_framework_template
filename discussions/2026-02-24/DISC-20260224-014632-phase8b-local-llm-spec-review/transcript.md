---
discussion_id: DISC-20260224-014632-phase8b-local-llm-spec-review
started: 2026-02-24T01:49:51.729258+00:00
ended: 2026-02-24T01:52:19.803398+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 4
---

# Discussion: DISC-20260224-014632-phase8b-local-llm-spec-review

## Turn 1 — architecture-consultant (critique)
*2026-02-24T01:49:51.729258+00:00 | confidence: 0.88*
*tags: spec-review, architecture, phase8b*

APPROVE-WITH-CHANGES. 10 findings (2 blocking, 8 advisory). BLOCKING: (1) AgentRepository provider rebuild loses localLlmLayer — mutable field on provider-managed object is fragile; must use constructor injection or stable instance. (2) SHA-256 verification for 380MB GGUF uses readAsBytes() which would OOM; must use chunked hashing via openRead(). ADVISORY: (3) LocalLlmException should be defined in local_llm_service.dart. (4) Clarify LocalLlmException recovery behavior (model unload on OOM?). (5) Keep generateStream() private, not on abstract interface. (6) Model download service duplication OK at this scale. (7) PersonalityConfig needs toJson/fromJson/==/hashCode for SharedPreferences serialization. (8) Define custom prompt sanitization rules precisely. (9) llamadart dependency rationale should be documented. (10) Runtime memory guard for loadModel().

---

## Turn 2 — security-specialist (critique)
*2026-02-24T01:49:59.856338+00:00 | confidence: 0.88*
*tags: spec-review, security, phase8b*

REQUEST-CHANGES. 6 findings (2 blocking, 4 advisory). BLOCKING: (1) SHA-256 checksum must be non-empty and pre-verified before shipping — existing ModelDownloadService has empty placeholders that must not be copied. Add acceptance criterion requiring non-empty SHA-256 constant. (2) Custom prompt isolation boundary lacks structural enforcement — ClaudeApiLayer should structurally prohibit systemPrompt parameter; add test asserting no prompt-derived content leaks via allMessages on layer-transition fallback. ADVISORY: (3) Pin llamadart to exact 0.6.2 (no caret) — spec text says pin but pubspec shows ^0.6.2. Document bundled llama.cpp version. (4) SharedPreferences stores personality in cleartext — acceptable for now but note migration path to flutter_secure_storage if custom prompt is classified as health data. (5) Extend sanitization to normalize ChatML role markers. (6) Ensure loadModel() wraps native calls and converts all failures to LocalLlmException.

---

## Turn 3 — qa-specialist (critique)
*2026-02-24T01:50:05.410012+00:00 | confidence: 0.88*
*tags: spec-review, qa, phase8b*

APPROVE-WITH-CHANGES. 10 findings (2 blocking, 8 advisory). BLOCKING: (1) Fallback tests must cover all 4 AgentRepository methods (getGreeting, getFollowUp, generateSummary, getResumeGreeting) with ThrowingLocalLlmLayer — not just getGreeting. (2) PersonalityConfig sanitization needs boundary tests (exactly 500 chars, 501 chars, only control chars) plus corrupted-JSON recovery test for PersonalityNotifier. ADVISORY: (3) Clarify personality capture timing (construction vs session lock). (4) isOnWifi needs 3 explicit test variants. (5) All LocalLlmLayer tests must assert response.layer == AgentLayer.llmLocal. (6) Two tests needed for with/without custom personality prompt injection. (7) Spec must note pump() not pumpAndSettle for download dialog progress tests. (8) Clarify which method (generate vs generateStream) LocalLlmLayer uses internally. (9) Mock design for generateStream needs guidance. (10) SharedPreferences.setMockInitialValues required per test.

---

## Turn 4 — facilitator (synthesis)
*2026-02-24T01:52:19.803398+00:00 | confidence: 0.9*
*tags: spec-review, synthesis, phase8b*

3 specialists reviewed the Phase 8B spec. 26 total findings (6 blocking, 20 advisory). All 6 blocking findings addressed in spec revision: (1) AgentRepository localLlmLayer changed from mutable field to constructor injection — fixes provider rebuild loss. (2) SHA-256 checksum required non-empty and pre-verified — no empty placeholders. (3) Chunked SHA-256 hashing via openRead() — prevents 380MB OOM from readAsBytes(). (4) ClaudeApiLayer prompt isolation structurally enforced — prohibit systemPrompt parameter + test for allMessages leakage. (5) Fallback tests cover all 4 AgentRepository methods with ThrowingLocalLlmLayer. (6) PersonalityConfig sanitization boundary tests + corrupted JSON recovery added. Additional revisions: generateStream kept private (not on abstract interface), LocalLlmException defined in local_llm_service.dart, personality captured at construction time (immutable), llamadart pinned exact 0.6.2 (no caret), SharedPreferences health-data migration note added. 14 advisory findings noted for implementation attention: runtime memory guard, ChatML marker sanitization, isOnWifi test variants, pump() for dialog tests, etc.

---
