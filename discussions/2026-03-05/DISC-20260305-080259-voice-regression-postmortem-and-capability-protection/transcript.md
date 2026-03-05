---
discussion_id: DISC-20260305-080259-voice-regression-postmortem-and-capability-protection
started: 2026-03-05T08:03:17.832383+00:00
ended: 2026-03-05T08:12:44.466595+00:00
agents: [architecture-consultant, facilitator, independent-perspective]
total_turns: 4
---

# Discussion: DISC-20260305-080259-voice-regression-postmortem-and-capability-protection

## Turn 1 — facilitator (evidence)
*2026-03-05T08:03:17.832383+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Post-mortem of voice STT regression (all three STT engines broken after Deepgram was added as default) + plan to (1) stabilize the working voice baseline, (2) understand the architectural flaw that allowed experimental code to destroy proven functionality, and (3) enhance the agentic framework itself to prevent this pattern from recurring — without separate environments (DEV/UAT).
- **Files/scope**: lib/providers/voice_providers.dart, lib/services/deepgram_stt_service.dart, lib/services/speech_recognition_service.dart, supabase/functions/deepgram-proxy/index.ts, integration_test/voice_mode_test.dart, and the framework planning/review workflow itself.
- **Developer-stated motivation**: Voice was fully working (speech_to_text + sherpa_onnx) before Deepgram was introduced. After Deepgram was added as the default STT engine, all three engines stopped working on physical device. The developer wants to understand WHY this happened at the architectural and methodological level, stabilize what worked before, and make the framework safe for 'creative semi-technical people to experiment without destroying proven infrastructure'.
- **Explicit constraints**: No separate DEV/UAT environments. The framework must be self-contained. Deepgram is acceptable to be off the table for now. The framework must inoculate proven capabilities from experimental additions. Target audience is creative non-engineers with structural thinking who need to safely actuate ideas.

---

## Turn 2 — architecture-consultant (critique)
*2026-03-05T08:11:27.215124+00:00 | confidence: 0.92*
*tags: architecture, cpp, resource-lifecycle, missing-adr*

## Findings

### Finding 1 (Medium — Factual Error in Post-Mortem)
The spec states AudioRecorder starts BEFORE WebSocket, but code shows WebSocket connects first (line 123), recorder starts after (lines 191-206). The bug analysis conclusion is still correct — the issue is onDone lacking recorder cleanup — but the described sequence is wrong. Post-mortem is a permanent artifact. Correct to: 'DeepgramSttService._connectAndCapture() registers an onDone handler on the WebSocket that sets _isListening=false without stopping the AudioRecorder. When WebSocket closes with 401, recorder continues running because subsequent stopListening()/dispose() calls guard on _isListening and skip cleanup.'

### Finding 2 (High — Blocking: Missing ADR)
CPP introduces a significant framework methodology change governing all future feature development (C2 quality gate enforcement, C3 review gate modification, C5 two-PR rule). Per CLAUDE.md Architectural Gates: any architectural change requires an ADR. Add ADR-0035 documenting the CPP decision, no-separate-environments constraint, and alternatives considered. Spec already contains this material — needs formalization.

### Finding 3 (Medium — C2 False Positive Risk)
C2 quality gate check is significantly more complex than spec suggests. Simplify: grep-based heuristic detecting 'return SttEngine.*' or 'return TtsEngine.*' pattern changes in *_providers.dart files. Consider WARNING vs BLOCKING — C5 is the primary enforcement, C2 is safety net.

### Finding 4 (Medium — Semantic Conflict in BUILD_STATUS.md)
Adding Proven Baseline to BUILD_STATUS.md puts persistent state in an ephemeral document (CLAUDE.md defines BUILD_STATUS.md as session-scoped working state). Proven Baseline should live entirely in CAPABILITY_STATUS.md (add Last-verified-commit column). BUILD_STATUS.md can reference it.

### Finding 5 (Low — ADR-0031 Contradiction)
ADR-0031 (status: accepted) designates Deepgram as primary STT. A1 reverts that. ADR-0031 should be amended or superseded. Add amendment section or create new ADR superseding the primary designation while retaining Deepgram as available engine.

### Finding 6 (Low — C5 Enforcement Gap)
Two-PR convention relies on agent + review enforcement — same gap that allowed PR #72. A single PR could add implementation, update CAPABILITY_STATUS.md to PROVEN, and change default simultaneously. Spec should document this known enforcement gap explicitly.

### Finding 7 (Info — Settings Label)
settings_screen.dart labels Deepgram as 'Deepgram Nova-3 (Recommended).' A4 must explicitly remove Recommended and replace with Experimental.

### Finding 8 (Medium — Interface Contract Underspecified)
SpeechRecognitionService interface defines dispose() and stopListening() but provides no guarantee about OS resource cleanup under abnormal termination. Future implementations could make the same mistake. Add doc comments explicitly stating: Implementations MUST release all OS resources unconditionally in dispose() regardless of isListening.

## Verdict: approve-with-changes
Address Finding 2 (ADR required) and Finding 4 (Proven Baseline in CAPABILITY_STATUS.md) as blocking. Correct Finding 1 post-mortem text. Others advisory.

---

## Turn 3 — independent-perspective (critique)
*2026-03-05T08:12:07.794099+00:00 | confidence: 0.82*
*tags: anti-groupthink, hidden-assumptions, pre-mortem, alternative-perspectives*

## Hidden Assumptions

1. **Interface flaw treated as documentation gap, not contract gap.** The SpeechRecognitionService abstract contract says nothing about OS resources under abnormal termination. The spec addresses this with documentation only; the interface design flaw remains.

2. **CAPABILITY_STATUS.md assumes someone will update it.** No enforcement mechanism exists to keep the table accurate. On a project with 262 open advisories, manually-maintained state goes stale. Stale PROVEN status is more dangerous than no status — it creates false confidence that short-circuits investigation.

3. **Two-PR convention assumes provider default is the only promotion vector.** A capability can become effectively primary via settings UI label, documentation, or feature flag — without a provider default change. C2 through C5 would all miss this.

4. **Regression test for mic leak assumed untestable.** The regression ledger already acknowledges 'OS-level, not testable in flutter test.' B3 requirement conflicts with this acknowledgment.

5. **PROVEN assumed to mean worked-in-the-past, not works-now.** BUILD_STATUS.md shows Voice/STT: Needs test on physical device. No active confirmation speech_to_text works right now.

6. **CPP addresses promotion of the bug, not introduction.** C2 detects default changes. The microphone leak was introduced in the same commit as DeepgramSttService — before any default change. CPP would not have caught the introduction of the latent bug, only its promotion.

## Pre-Mortem Scenarios

**Scenario 1 (Medium/High): CAPABILITY_STATUS.md goes stale and creates false confidence**
After a transitive dependency update (e.g., record package changes behavior on new Android API level), a PROVEN capability breaks silently. C2 sees PROVEN status, issues no warning. Developer trusts the table. Mitigation: Add last_device_verified timestamp per capability. Quality gate warns if timestamp older than 30 days.

**Scenario 2 (Low/High): New STT engine bypasses C5 via feature flag, not provider default**
Engineer exposes new engine via feature flag or settings UI ordering, not through SttEngine enum. Two-PR convention does not apply. New engine ships as primary for flag-holders before device testing. Mitigation: Broaden CPP definition of 'default change' to include any change that promotes a capability to primary user experience path.

**Scenario 3 (Medium/High): Interface fix not done — pattern re-emerges in third service**
A fourth STT implementation is added. New implementor reads the abstract interface, sees dispose() and stopListening(), makes the same mistake. .claude/rules/ documentation does not protect against implementors who do not read the rules. Mitigation: Strengthen interface contract in code, not just documentation (see Alternative 1 below).

**Scenario 4 (Low/Medium): C2 produces false negative from diff matching wrong file**
Default changes inside a test build() override, a copy in a feature branch, or a different provider file. Diff-based check does not match pattern. Gate silently passes. Mitigation: Add an explicit test that asserts the default value of sttEngineProvider with empty SharedPreferences — would fail if changed.

**Scenario 5 (Medium/High): Device test requirement exists in policy but Voice/STT stays Needs-test**
Stabilization PR merged without completed device test (same failure as the original incident). CAPABILITY_STATUS.md marks speech_to_text as PROVEN based on history rather than current verification. Policy and reality diverge.

## Alternative Perspectives

**Alternative 1: Fix interface contract in code, not documentation**
Add releaseHardware() as a required abstract method: 'Must be safe to call in any state — do not gate on isListening.' Orchestrator and provider disposal call releaseHardware() in addition to stopListening(). Makes correct behavior the path of least resistance. Future implementors cannot implement the interface without confronting the unconditional release contract.

**Alternative 2: device_test_results.json instead of CAPABILITY_STATUS.md**
Machine-readable file updated only by explicit 'scripts/record_device_test.py --capability speech_to_text --result pass' command. Quality gate checks timestamp freshness per capability. Harder to forget than editing a markdown table. Provides audit trail.

**Alternative 3: Assert default in provider code**
Add CPP-GATE comment + assert in SttEngineNotifier.build() asserting the default is speechToText. Any default change requires modifying the assertion — making it deliberate and visible.

## Consensus Check
The CPP controls are all documentation-or-process level interventions. None enforce the resource lifecycle invariant in code. None prevent a future implementor from making the same mistake without a default change. The spec correctly identifies two root causes but proposes predominantly process fixes for the methodological flaw while addressing the architectural interface flaw with documentation only. A team reviewing this without independent perspective would likely miss this asymmetry — the CPP controls are clearly better than nothing and the framing as 'two root causes' makes it appear both are addressed equally.

## Strengths
Two-PR convention creates a natural pause even with imperfect enforcement. Post-mortem correctly traces causal chain through flag-clearing behavior. CAPABILITY_STATUS.md creates shared vocabulary for capability stability discussions. Correct resistance to environment separation.

---

## Turn 4 — facilitator (synthesis)
*2026-03-05T08:12:44.466595+00:00 | confidence: 0.9*
*tags: blocking:2, advisory:8*

## Request Context
- **What was requested**: After all three STT engines were broken by a microphone resource leak introduced by Deepgram's WebSocket 401 failures, the developer requested: (1) immediate stabilization reverting to the last known-working baseline, (2) a framework-level Capability Protection Protocol to prevent experimental capabilities from silently breaking proven ones. Explicit constraint: no separate environments (DEV/UAT) — the agentic framework itself must self-contain this protection.
- **Files/scope**: SPEC-20260305-080259-voice-stabilization-and-capability-protection.md covering post-mortem, Parts A/B/C requirements
- **Developer-stated motivation**: 'What was the flaw in our approach that led to an architecture where the addition of something new would harm the existing and proven code. I want this framework to be the place where creative people can actuate their ideas without exploration destroying their progress.'
- **Explicit constraints**: No DEV/UAT environment separation. Framework must be self-contained.

## Synthesis

### Blocking Items (Must address before implementation)

**B1 — ADR-0035 Required (architecture-consultant Finding 2)**
The CPP is a significant framework methodology change. CLAUDE.md Architectural Gates requires an ADR for any architectural change. Add ADR-0035 documenting: the CPP decision, the no-separate-environments constraint, and alternatives considered (environment separation rejected by developer, runtime feature flags, per-capability test suites). The spec already contains this content — formalization needed.

**B2 — Proven Baseline belongs in CAPABILITY_STATUS.md only (architecture-consultant Finding 4)**
Putting persistent state in BUILD_STATUS.md (defined in CLAUDE.md as 'session-scoped ephemeral working state') creates a semantic conflict and causes data loss during context compaction. The Proven Baseline must live entirely in CAPABILITY_STATUS.md (add Last-verified-commit column). BUILD_STATUS.md can reference CAPABILITY_STATUS.md but must not duplicate persistent state.

### Key Advisory Items

**A1 — Post-mortem sequence error (architecture-consultant Finding 1)**
Spec incorrectly states AudioRecorder starts before WebSocket. The WebSocket connects first; the bug is in the onDone handler. Correct the post-mortem text before closing.

**A2 — Interface contract must be strengthened in code (both specialists, architecture-consultant Finding 8 + independent-perspective Alternative 1)**
Both specialists identified that documenting a rule in .claude/rules/ does not protect future implementors. The SpeechRecognitionService abstract interface should have explicit doc comments on dispose() and stopListening() stating the OS resource invariant. The independent-perspective agent proposed adding a releaseHardware() method as a hard-coded requirement — this is stronger and worth considering for the next implementation sprint.

**A3 — CAPABILITY_STATUS.md staleness risk (independent-perspective Scenario 1)**
Add last_device_verified timestamp per capability. Quality gate or hook warns if timestamp older than 30 days. Without this, a stale PROVEN status is more dangerous than no status.

**A4 — C2 simplification (architecture-consultant Finding 3)**
Quality gate default-change check should be grep-based heuristic (detect 'return SttEngine.*' changes in *_providers.dart), not full semantic analysis. Should be WARNING not BLOCKING since C5 is the primary enforcement.

**A5 — C5 enforcement gap must be documented (both specialists)**
The two-PR convention has a known enforcement gap: a single PR could add implementation, update CAPABILITY_STATUS.md to PROVEN, and change default simultaneously, defeating C2. The spec should explicitly acknowledge this rather than implying hard enforcement.

**A6 — ADR-0031 requires amendment (architecture-consultant Finding 5)**
ADR-0031 designates Deepgram as primary. Part A1 reverts that. ADR-0031 must be amended or superseded to maintain decision lineage (Principle #5).

**A7 — CPP only protects against promotion, not introduction (independent-perspective core insight)**
The microphone leak was introduced in the same commit as DeepgramSttService — before any default change. The CPP controls (C2–C5) would not have caught the introduction of the latent bug, only its promotion. This is a known limitation that should be documented. The interface fix (A2) partially addresses this.

**A8 — Provider default assertion test (independent-perspective Alternative 3)**
Add a test that asserts the default value of sttEngineProvider with empty SharedPreferences. This would fail if the default is changed without updating the test — a machine-enforceable gate complementing the grep-based C2.

### Resolution Summary
Spec approved with modifications. Parts A and B can proceed immediately after fixing the post-mortem text and confirming CAPABILITY_STATUS.md is the authoritative location for proven baseline data. ADR-0035 should be drafted as part of Part C implementation. The CPP design is sound and appropriately scaled — markdown + grep + convention is the right level of intervention per Principle #8.

---
