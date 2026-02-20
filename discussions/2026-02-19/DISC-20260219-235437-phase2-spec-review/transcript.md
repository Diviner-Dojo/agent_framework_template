---
discussion_id: DISC-20260219-235437-phase2-spec-review
started: 2026-02-19T23:54:47.626100+00:00
ended: 2026-02-19T23:59:48.171782+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260219-235437-phase2-spec-review

## Turn 1 — facilitator (proposal)
*2026-02-19T23:54:47.626100+00:00 | confidence: 0.85*
*tags: spec, phase2, draft*

DRAFT Phase 2 spec: SPEC-20260220-000100 — Android Assistant Registration, Settings, and Onboarding. 10 tasks covering: dependencies, AndroidManifest intent filters, Kotlin platform channel, Flutter service wrapper, onboarding state management, settings screen, onboarding screen, navigation/intent routing, tests, final verification. 2 stretch goals: voice input and ConversationAgent interface extraction. Full spec at docs/sprints/SPEC-20260220-000100-phase2-assistant-registration.md

---

## Turn 2 — architecture-consultant (critique)
*2026-02-19T23:56:32.710207+00:00 | confidence: 0.82*
*tags: spec, phase2, architecture*

Confidence: 0.82. BLOCKING: (1) HIGH — assistant-launch detection in app.dart lacks a concrete widget lifecycle anchor. wasLaunchedAsAssistant() is called 'on app start' but spec doesn't specify WHERE — must be called exactly once in ConsumerStatefulWidget.initState() with a _checked guard, not in build(). Hot-reload or widget rebuilds will produce intermittent failures. ADVISORY: (1) MEDIUM — no ADR for platform channel pattern; recommend ADR-0012 covering channel naming, primitive-types-only rule, iOS no-op stub pattern. (2) MEDIUM — dual-provider inconsistency: hasCompletedOnboardingProvider reads from SharedPreferences directly while onboardingNotifierProvider manages state separately. Widget watching hasCompleted won't rebuild when notifier fires. Should remove hasCompleted or delegate to notifier.select(). (3) LOW — static _channel field on non-static class conflicts with constructor-injection (ADR-0007). (4) LOW — ConversationAgent interface in lib/repositories/ is misplaced; belongs in lib/agents/ or lib/domain/. Verdict: request-changes.

---

## Turn 3 — security-specialist (critique)
*2026-02-19T23:56:39.631566+00:00 | confidence: 0.82*
*tags: spec, phase2, security*

Confidence: 0.82. BLOCKING: (1) MEDIUM — Spec does not explicitly verify android:allowBackup=false is preserved in AndroidManifest.xml. Must add verification step in Task 2 and a grep check in Task 10. Security baseline requires this as a hard rule. ADVISORY: (1) LOW — wasLaunchedAsAssistant flag has same lifecycle race noted by arch; call exactly once in top-level provider. (2) LOW — voice-transcribed text (stretch) should be treated as untrusted user input. Trust boundaries: platform channel is appropriately narrow (3 read-only methods, primitive types only, OS-sourced data). Intent filter is safe — ACTION_ASSIST is brokered by Android OS, not directly callable by third-party apps. SharedPreferences onboarding flag tampering consequence is negligible. Verdict: approve-with-changes.

---

## Turn 4 — qa-specialist (critique)
*2026-02-19T23:56:47.019172+00:00 | confidence: 0.82*
*tags: spec, phase2, qa*

Confidence: 0.82. BLOCKING: (1) HIGH — No test file for app.dart routing logic. Onboarding redirect and assistant-launch detection are the most complex new behaviors and have zero test coverage in the spec. Must add test/app_routing_test.dart. (2) HIGH — Platform.isAndroid is false in flutter test, which means every AssistantRegistrationService method short-circuits before touching the channel. Spec must prescribe either (a) inject Platform as a dependency, or (b) test internal channel helpers separately. Current design makes core channel behavior untestable. ADVISORY: (1) MEDIUM — onboarding tests miss idempotency (double-call) and provider override verification. (2) MEDIUM — settings screen tests only check presence, not behavior. Should test didChangeAppLifecycleState refresh of isDefaultAssistantProvider. (3) LOW — onboarding interrupted mid-flow (back out on Page 2) has no test scenario. (4) LOW — SharedPreferences.setMockInitialValues({}) needed in setUp(). Verdict: request-changes.

---

## Turn 5 — facilitator (synthesis)
*2026-02-19T23:59:48.171782+00:00 | confidence: 0.85*
*tags: spec, phase2, synthesis*

SYNTHESIS: Phase 2 spec reviewed by 3 specialists. 4 blocking findings addressed: (1) assistant-launch lifecycle anchor — wasLaunchedAsAssistant() now called exactly once in initState() with _assistantLaunchChecked guard; (2) allowBackup verification — explicit grep check added to Task 2 and Task 10; (3) missing routing tests — test/app_routing_test.dart added with 4 scenarios; (4) untestable service — AssistantRegistrationService refactored with injectable isAndroid and channel parameters. 5 advisory findings incorporated: dual-provider removed (single onboardingNotifierProvider), ConversationAgent interface moved to lib/agents/, test improvements (idempotency, lifecycle, mid-flow exit, setMockInitialValues). Spec status updated to reviewed. Ready for developer approval.

---
