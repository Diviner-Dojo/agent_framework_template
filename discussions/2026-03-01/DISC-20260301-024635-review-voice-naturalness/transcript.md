---
discussion_id: DISC-20260301-024635-review-voice-naturalness
started: 2026-03-01T02:51:07.233368+00:00
ended: 2026-03-01T02:51:53.781011+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 4
---

# Discussion: DISC-20260301-024635-review-voice-naturalness

## Turn 1 — qa-specialist (proposal)
*2026-03-01T02:51:07.233368+00:00 | confidence: 0.87*
*tags: qa, blocking:1, advisory:6*

QA Review — Voice Naturalness (7 findings, 25 tests reviewed)

BLOCKING:
- (High) stop() does not cancel _commitDelayTimer or _turnCompletionTimer — dangling timer can call _commitUserTurn on stale/idle session after stop()

ADVISORY:
- (Medium) Idle timer guard test is thin — only verifies negative case, does not confirm flag resets on isFinal
- (Medium) No integration test for ◐ (deliberating) marker path — only ○ has behavioral test
- (Low) stripMarkdown regex does not handle multi-line bold/italic spans (dotAll not set)
- (Low) Combined markdown test uses contains() not equals() — loose assertions
- (Low) No test for timer-cancellation R9 behavior (second result cancels pending commit)
- (Low) Timer-based tests use real delays — flaky risk on loaded CI

STRENGTHS: computeCommitDelay boundary values correctly tested at fenceposts; parseTurnMarker whitespace test; enableThinkingSound consistently applied in all 3 test files; SpeechResult equality+hashCode correctly includes confidence; dispose() cancels all timers.

---

## Turn 2 — architecture-consultant (proposal)
*2026-03-01T02:51:22.752338+00:00 | confidence: 0.88*
*tags: architecture, blocking:2, advisory:6*

Architecture Review — Voice Naturalness (8 findings)

BLOCKING:
- (High) stop() does not cancel _commitDelayTimer, _turnCompletionTimer, or call _stopThinkingSound() — state machine invariant violation
- (High) pause() has same gap — pending timers fire during paused state causing illegal transitions

ADVISORY:
- (Medium) _commitUserTurn needs phase guard — Timer callback runs async without checking current phase, risk of stale-state processing
- (Medium) SpeechResult confidence=0.0 default causes 1200ms delay for sherpa_onnx (offline STT) — UX regression for offline users. Consider sentinel value or zero-maps-to-zero.
- (Medium) _startThinkingSound .then() chain reads _thinkingPlayer field (can be reassigned) — capture in local variable instead
- (Low) No ADR for turn-completeness marker protocol between Edge Function and client
- (Low) enableThinkingSound constructor parameter follows existing silenceTimeoutSeconds pattern — acceptable
- (Info) Markdown stripping placement in onAssistantMessage is correct — static recovery strings don't need it

STRENGTHS: State machine external API (VoiceOrchestratorState, VoiceLoopPhase) unchanged; clean backward compat on SpeechResult; graceful fallback on turn markers (R28); dispose() is comprehensive; turn-completion re-prompt cancellation on new speech (R26).

---

## Turn 3 — docs-knowledge (proposal)
*2026-03-01T02:51:36.400911+00:00 | confidence: 0.88*
*tags: docs, blocking:0, advisory:6*

Docs/Knowledge Review — Voice Naturalness (6 findings)

ADVISORY:
- (Medium) No ADR-0028 for voice naturalness behavioral decisions — SPEC is sprint plan not decision record. Covers: marker protocol, confidence tiers, thinking sound replacement, idle timer guard.
- (Medium) SPEC-20260228 R27 references wrong Edge Function filename (claude-chat vs claude-proxy) — implementation is correct but SPEC is stale
- (Low) llmThinking constant doc comment now inaccurate — says 'spoken' but orchestrator replaced with chime, constant retained only for UI widget
- (Low) Constructor missing doc comment explaining enableThinkingSound parameter purpose
- (Low) CLAUDE.md directory layout missing assets/ entry
- (Low) File-level banner references ADR-0015 only — should also reference ADR-0016

STRENGTHS: @visibleForTesting methods all have doc comments explaining 'why' with spec refs; R1-R29 inline requirement traceability excellent; voice_recovery_messages.dart section comments clear; edge function prompt well-commented with concrete examples; test groups tagged with SPEC task numbers.

---

## Turn 4 — facilitator (synthesis)
*2026-03-01T02:51:53.781011+00:00 | confidence: 0.88*
*tags: blocking:2, advisory:14*

SYNTHESIS — Voice Naturalness Review

Verdict: approve-with-changes (2 blocking findings, 14 advisory)

BLOCKING (must fix):
1. stop() missing timer cancellation — _commitDelayTimer, _turnCompletionTimer, and _stopThinkingSound() not called in stop(). Dangling timers fire on idle orchestrator. (QA + Architecture consensus)
2. pause() missing timer cancellation — same gap as stop(). Pending timers fire during paused state causing illegal state transitions. (Architecture)

Recommended fix: 3 lines in stop(), 3 lines in pause(), plus a phase guard at top of _commitUserTurn().

ADVISORY (non-blocking):
- Add ◐ integration test
- Add timer-cancellation R9 test
- Strengthen idle timer guard test (verify flag reset)
- Phase guard in _commitUserTurn for defensive coding
- Consider sentinel for confidence=0.0 vs offline engines
- Capture _thinkingPlayer in local variable in .then() chain
- Create ADR-0028 for voice naturalness decisions
- Fix SPEC R27 edge function filename
- Update llmThinking doc comment
- Add constructor doc comment
- Add assets/ to CLAUDE.md
- Update file banner ADR references
- Document stripMarkdown multi-line limitation

Education gate: not needed (low conceptual complexity, established patterns)

---
