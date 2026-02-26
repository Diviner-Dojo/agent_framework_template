---
adr_id: ADR-0026
title: "Conversational Onboarding via Real Journal Session"
status: accepted
date: 2026-02-26
decision_makers: [facilitator, architecture-consultant, ux-evaluator, qa-specialist]
discussion_id: DISC-20260226-224410-e13-conversational-onboarding-build
supersedes: null
risk_level: low
confidence: 0.90
tags: [onboarding, ux, journaling-mode]
---

## Context

The initial onboarding was a 3-page static PageView wizard that introduced the app concept, guided the user to set up the assistant gesture, and offered a "Begin Journaling" button. This approach had two problems:

1. It didn't demonstrate the app's core value — conversational journaling. Users saw static text cards instead of experiencing the product.
2. The assistant setup page was redundant — the same functionality already exists in Settings.

E13 (Sprint N+3) replaces the static wizard with a conversational first session that lets users experience the product immediately while capturing their first journal entry.

## Decision

Onboarding IS a real journal session. The `ConversationalOnboardingScreen` is a thin wrapper that:

1. Calls `startSession(journalingMode: 'onboarding')` to create a real DB session.
2. Immediately navigates to the existing `/session` route (`JournalSessionScreen`).
3. The session screen handles the full conversation — voice, text, greeting, follow-ups, ending — with no onboarding-specific UI duplication.

The `onboarding` journaling mode (ADR-0025 extension) provides mode-specific prompts through all 3 conversation layers + the Edge Function. The `RuleBasedLayer` has a warm onboarding-specific greeting for offline fallback.

Onboarding completion is triggered by `endSession()`, which checks `state.journalingMode == 'onboarding'` and calls `completeOnboarding()` via SharedPreferences. This works for both the normal end path and the empty-session guard path.

The old `OnboardingScreen` (static wizard) is deleted. The assistant gesture setup is available exclusively through Settings.

## Alternatives Considered

### Alternative 1: Custom Onboarding Chat UI
- **Pros**: Full control over the onboarding-specific UX; could add onboarding-only UI elements (progress indicators, tips)
- **Cons**: Duplicates the entire session screen; doubles maintenance surface; diverges from the real product experience
- **Reason rejected**: The existing session screen already handles everything needed. Duplication violates the least-complex intervention principle.

### Alternative 2: Enhanced Static Wizard + Session
- **Pros**: Keeps the assistant setup guidance; familiar onboarding pattern
- **Cons**: Still doesn't demonstrate the core product; assistant setup is already in Settings; adds an unnecessary step before the user can journal
- **Reason rejected**: The wizard pages didn't add value beyond what Settings already provides.

### Alternative 3: Hybrid — One Welcome Page + Session
- **Pros**: Brief intro before jumping into conversation; could show a tip about voice mode
- **Cons**: Extra navigation step; the onboarding greeting itself can welcome the user and mention voice mode
- **Reason rejected**: The onboarding prompt template already covers the welcome and voice/text explanation in Steps 1-2, making a separate welcome page redundant.

## Consequences

### Positive
- Users experience the core product immediately on first launch
- First journal entry is saved automatically — users see value from minute one
- No duplicated UI code — the session screen handles everything
- Offline-capable — RuleBasedLayer provides an onboarding-specific greeting
- Safe fallback — if the user kills the app mid-onboarding, next launch retries onboarding

### Negative
- No explicit assistant gesture setup guidance during onboarding — users must discover Settings
- The brief loading spinner (< 1 second) before the session screen could feel abrupt
- If `startSession()` fails on first launch, the user lands on an empty session list with no guidance (mitigated by SnackBar message suggesting app restart)

### Neutral
- The `onboarding` journaling mode is a regular enum value — it appears in mode selection lists unless filtered out (currently not user-selectable since mode selection UI uses a hardcoded list)
- The onboarding session is a normal session record in the database — it shows up in the session list like any other entry

## Linked Discussion
See: discussions/2026-02-26/DISC-20260226-224410-e13-conversational-onboarding-build/
