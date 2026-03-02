---
adr_id: ADR-0029
title: Riverpod Provider Watching Constraints for MaterialApp initialRoute
status: accepted
date: 2026-03-02
discussion_id: DISC-20260302-031919-review-emulator-testing-and-app-fixes
supersedes: null
superseded_by: null
---

## Context

When `AgenticJournalApp.build()` used `ref.watch(onboardingNotifierProvider)` to determine the `initialRoute` for `MaterialApp`, completing onboarding caused the provider to emit a new value (`false` -> `true`). This triggered a full `MaterialApp` rebuild, which reassigned `initialRoute` on an already-mounted `Navigator`. The Navigator interpreted the changed `initialRoute` as a configuration reset, collapsing its active route stack to just the new initial route.

The symptom was a silent widget tree collapse after onboarding completion. The Claude API closing summary call, still in flight when the user navigated away from the onboarding session, would resolve during this collapsed state and produce cascading errors. Integration tests discovered this as a "zero widgets, zero errors" state after pumping on the home screen.

## Decision

**Use `ref.read` (not `ref.watch`) for any Riverpod provider whose value feeds `MaterialApp.initialRoute`.**

The `initialRoute` parameter is a one-time initialization input, not a reactive binding. Once the `Navigator` is mounted, route transitions must be managed imperatively via `Navigator.pushReplacement`, `Navigator.pushNamedAndRemoveUntil`, or `Navigator.pop` — not by rebuilding the `MaterialApp`.

This is not a Riverpod anti-pattern. `ref.read` is the correct call for values that drive initial configuration rather than live UI state. All three uses of `onboardingNotifierProvider` in `app.dart` (lines 111, 154, 182) correctly use `ref.read` because they are imperative reads in callbacks or one-time initialization, not reactive widget rebuilds.

## Consequences

- The onboarding-to-session-list transition is handled by the `ConversationalOnboardingScreen` calling `Navigator.pushReplacementNamed('/')` after `completeOnboarding()`.
- Integration tests must navigate away from the home screen immediately after onboarding ends to avoid pumping while the Claude API closing summary resolves (the response arrives on a screen with session providers, which can cause state conflicts).
- Future providers that feed `MaterialApp` configuration (e.g., theme mode, locale) should also be evaluated for whether they require `ref.read` vs `ref.watch` based on whether the `MaterialApp` can safely rebuild.

## Alternatives Considered

1. **Keep `ref.watch` and use `Navigator.key` to force Navigator recreation**: Would work but destroys all route history and active screens on every onboarding state change. Worse UX.
2. **Use `GoRouter` with redirect guards**: More idiomatic for complex routing, but a larger migration (CLAUDE.md notes this as a planned upgrade path). The current fix is minimal and correct.
3. **Debounce the provider change**: Would mask the root cause. The rebuild is the problem, not its timing.

## References

- ADR-0026: Conversational Onboarding via Real Journal Session
- `lib/app.dart:175-182` — inline comment explaining the constraint
- `memory/bugs/regression-ledger.md` — regression entry for this bug
- `test/app_routing_test.dart` — regression test
