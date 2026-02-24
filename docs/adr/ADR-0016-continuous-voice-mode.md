---
adr_id: ADR-0016
title: "Continuous Voice Mode — Phase 7B Architecture Decisions"
status: accepted
date: 2026-02-23
decision_makers: [facilitator, architecture-consultant]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [voice, continuous-mode, state-machine, tts, stt, phase-7b]
---

## Context

Phase 7A (ADR-0015) delivered push-to-talk voice input. Phase 7B extends this to continuous voice mode — a hands-free listen-process-speak-listen loop for walk-and-talk journaling. This required several architectural decisions about state management, command handling, TTS strategy, and session lifecycle that go beyond ADR-0015's push-to-talk scope.

## Decision

### 1. Callback-based VoiceSessionOrchestrator (vs full Riverpod state machine)

The orchestrator receives `SendMessageCallback`, `SessionActionCallback`, and `ResumeSessionCallback` from the UI layer rather than depending on `SessionNotifier` directly. This avoids circular provider dependencies: `SessionNotifier` depends on `AgentRepository`, while the orchestrator needs to send messages through `SessionNotifier`. Callbacks break the cycle without introducing a mediator pattern.

**Alternative rejected**: Full Riverpod StateNotifier for the orchestrator. This would create a provider dependency cycle (`sessionNotifierProvider` → `agentRepositoryProvider` → `voiceOrchestratorProvider` → `sessionNotifierProvider`). Riverpod's acyclic dependency graph would require splitting SessionNotifier, which is disproportionate for a single consumer.

### 2. ValueNotifier for voice state (vs StateNotifier)

`VoiceOrchestratorState` is emitted via `ValueNotifier<VoiceOrchestratorState>` rather than a Riverpod `StateNotifier`. Since the orchestrator is not a Riverpod provider (see §1), `ValueNotifier` provides the lightest reactive primitive that Flutter widgets can consume via `ValueListenableBuilder`. This keeps the orchestrator framework-agnostic and testable without a `ProviderContainer`.

**Alternative rejected**: `StateNotifier` (from Riverpod). Would require the orchestrator to be a Riverpod provider, reintroducing the circular dependency from §1. Also, `StateNotifier` is deprecated in favor of `Notifier` in Riverpod 2.x.

### 3. VoiceCommandClassifier as separate concern

Voice command detection (`VoiceCommandClassifier`) is a standalone class rather than inline logic in the orchestrator. Commands (end session, discard, undo) require pattern matching with confidence scoring and evolving vocabulary. Separating the classifier enables:
- Independent unit testing of command patterns
- Future expansion to new commands without touching orchestrator state logic
- Potential replacement with an ML-based classifier without architectural change

### 4. Sentence-splitting TTS with per-sentence error handling

Long assistant responses are split into sentences (`splitIntoSentences`) and spoken sequentially. This reduces perceived latency — the first sentence begins playing while the rest are queued. Each sentence has independent error handling: a TTS failure on sentence N stops playback but does not crash the orchestrator or lose the remaining text.

**Alternative rejected**: Speak the entire response as one TTS call. Acceptable for short responses, but multi-sentence responses produce noticeable delays before the user hears anything. The sentence-splitting approach is a ~20-line addition with measurable UX improvement.

### 5. Two-tier end-session detection (strong: immediate, moderate: confirmation)

Voice commands use a confidence threshold (`_highConfidenceThreshold = 0.8`) to decide between immediate execution and verbal confirmation:
- **Strong match** (≥ 0.8): Execute immediately (e.g., clear "stop session" utterance)
- **Moderate match** (< 0.8): Request verbal confirmation before executing

Discard commands always require confirmation regardless of confidence, because the action is destructive and irreversible.

A bounded confirmation timeout (`_confirmationTimeoutSeconds = 10`) prevents ambient noise from accidentally confirming a pending command.

### 6. Undo window for message send (5-second timer)

After ending a session via voice, a 5-second undo window allows the user to say "undo" to reopen the session. The `_lastClosedSessionId` is retained until the timer expires or the session is successfully reopened. This mirrors the "undo send" pattern familiar from messaging apps, adapted for voice interaction where mis-commands are more likely than in touch interfaces.

## Alternatives Considered

### Alternative 1: Full Riverpod StateNotifier for orchestrator
- **Pros**: Automatic dependency tracking, consistent with other providers
- **Cons**: Creates circular dependency cycle between SessionNotifier and orchestrator
- **Reason rejected**: Riverpod's acyclic graph would require splitting SessionNotifier disproportionately for a single consumer (§1)

### Alternative 2: Whole-response TTS (no sentence splitting)
- **Pros**: Simpler implementation, no split-point regex
- **Cons**: Noticeable latency delay before user hears anything on multi-sentence responses
- **Reason rejected**: Sentence splitting is ~20 lines with measurable UX improvement for hands-free use (§4)

### Alternative 3: Fixed confidence threshold (no two-tier detection)
- **Pros**: Simpler command execution path
- **Cons**: Either too many false-positive commands (low threshold) or too many confirmation prompts (high threshold)
- **Reason rejected**: Two-tier approach adapts naturally to STT confidence, balancing speed and safety (§5)

## Consequences

### Positive
- Orchestrator is testable without Riverpod infrastructure
- Callback pattern allows the UI to wire any state management approach
- Sentence-splitting measurably reduces perceived TTS latency
- Two-tier confidence prevents both false-positive commands and excessive confirmation prompts
- Undo window reduces cost of voice command misrecognition

### Negative
- Callback wiring is manual (UI must set `onSendMessage`, `onEndSession`, etc.)
- `ValueNotifier` doesn't participate in Riverpod's dependency graph (no automatic provider rebuilds)
- Sentence-splitting adds complexity to TTS flow and requires a split-point regex

### Neutral
- The orchestrator manages both push-to-talk and continuous mode in one class; a future split may be warranted if the modes diverge further
- Confirmation timeout of 10s is a tunable constant, not user-configurable

## Linked Discussion
See: ADR-0015 (Voice Mode Architecture — Push-to-Talk Foundation)
