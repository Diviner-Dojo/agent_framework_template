---
discussion_id: DISC-20260227-233013-timezone-tts-voice-fixes
started: 2026-02-27T23:33:11.262316+00:00
ended: 2026-02-27T23:36:47.784524+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 4
---

# Discussion: DISC-20260227-233013-timezone-tts-voice-fixes

## Turn 1 — qa-specialist (proposal)
*2026-02-27T23:33:11.262316+00:00 | confidence: 0.87*
*tags: qa, coverage, test-gaps*

Coverage assessment: (1) MEDIUM: timezone parameter in EventExtractionService.extract() never exercised in tests - no test passes timezone arg or verifies prompt contains IANA string. (2) MEDIUM: ClaudeApiLayer.getGreeting() voice mode fast-path has no test. (3) LOW: TtsRateNotifier has no tests for default value or persistence round-trip. (4) LOW: Weak conditional assertion in calendar test (line 417-439). Edge cases: timezone abbreviation fallback ambiguity (CST=UTC-6 or UTC+8), no TTS rate range validation.

---

## Turn 2 — security-specialist (proposal)
*2026-02-27T23:33:17.974780+00:00 | confidence: 0.88*
*tags: security, prompt-injection, privacy*

Security assessment: (1) MEDIUM - Prompt Injection: timezone string from FlutterTimezone interpolated directly into LLM prompt without sanitization. Rooted device could inject crafted timezone. Recommend regex allowlist validation (^[A-Za-z0-9_\-+/]{1,64}$). Blast radius limited by strict JSON output validation. (2) LOW - Mislabeling: AgentLayer.llmRemote on canned response misleads telemetry. (3) LOW - Privacy: IANA timezone stored in DB and synced to Supabase adds location fingerprint. Verify RLS coverage. Trust boundary analysis: OS→App (timezone read) not validated, App→EdgeFunction (prompt) not sanitized, LLM→App (response) well-defended with strict validation.

---

## Turn 3 — architecture-consultant (proposal)
*2026-02-27T23:33:22.700464+00:00 | confidence: 0.82*
*tags: architecture, layer-pattern, routing*

Architecture assessment: (1) MEDIUM - Pattern inconsistency: ClaudeApiLayer.getGreeting() short-circuit duplicates RuleBasedLayer logic and mislabels as llmRemote. ADR-0017 assigns routing to AgentRepository. Recommend moving short-circuit to AgentRepository.getGreeting() with ruleBasedLocal label. (2) LOW - deviceTimezoneProvider uses correct FutureProvider pattern, consistent with llmModelPathProvider. Riverpod caches result. Add comment clarifying cache behavior. (3) LOW - getResumeGreeting() already has same mislabeling pattern (pre-existing). (4) INFO - Three-layer architecture holding well overall.

---

## Turn 4 — facilitator (synthesis)
*2026-02-27T23:36:47.784524+00:00 | confidence: 0.9*
*tags: blocking:0, advisory:3*

Three bug fixes reviewed: (1) Calendar timezone — IANA timezone threading from FlutterTimezone through extraction + Google Calendar. Two specialist findings addressed: timezone sanitization regex added to prevent prompt injection (security-specialist), and architectural placement of voice greeting short-circuit moved from ClaudeApiLayer to AgentRepository with correct ruleBasedLocal label (architecture-consultant). (2) TTS speed — default rate bumped 0.85→1.0. (3) Voice mode greeting — canned brief response in voice mode. All blocking findings resolved: timezone sanitization added, AgentLayer mislabeling fixed, missing tests added (sanitizeTimezone, timezone prompt, voice greeting, TtsRateNotifier). 12 new tests, 1413 total passing. Verdict: approve.

---
