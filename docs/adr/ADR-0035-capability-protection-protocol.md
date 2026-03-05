---
adr_id: ADR-0035
title: "Capability Protection Protocol (CPP)"
status: accepted
date: 2026-03-05
authors: [facilitator]
decision_makers: [Developer]
discussion_id: DISC-20260305-080259-voice-regression-postmortem-and-capability-protection
supersedes: []
superseded_by: []
related:
  - ADR-0015  # Voice Mode Architecture
  - ADR-0022  # Voice Engine Swap Pattern
  - ADR-0031  # Deepgram STT Integration (default reverted)
spec: SPEC-20260305-080259-voice-stabilization-and-capability-protection
---

## Context

On 2026-03-03, commit `328ec44` (PR #72) introduced `DeepgramSttService` and simultaneously
changed the production default STT engine from the proven `speechToText` to the new,
unproven `deepgram`. The Deepgram proxy had never been device-tested before becoming the
default. Its WebSocket 401 failures triggered a latent microphone resource leak in
`onDone`/`dispose()` that blocked ALL three STT engines (Deepgram, speech_to_text,
sherpa_onnx) from acquiring the OS microphone. Voice mode was completely non-functional
from PR #72 through commit `e1ad873` (2026-03-05) — a regression that persisted across
11 subsequent PRs and was only discovered during physical device testing.

The framework had gates for many things (review, quality gate, education gate) but had
no gate specifically for: **"this new capability is about to become the default for
something that was previously working."** Adding an option and replacing the working
default were treated identically. They are not the same risk.

**Explicit constraint from the developer**: Environment separation (DEV/UAT staging) is
rejected as a mitigation strategy. The agentic development framework itself must manage
this complexity within a single-environment project structure.

## Decision

Introduce the **Capability Protection Protocol (CPP)** — a set of lightweight conventions,
quality gate checks, and review triggers that prevent experimental capabilities from
silently replacing proven ones.

### The Two-PR Pattern (C5)

New capabilities MUST be added as alternatives with the existing proven capability
remaining the default. **You cannot change a provider default in the same PR that
introduces the new implementation.**

- **PR N**: Add implementation (service class, tests, provider case). Default unchanged.
  Add to `CAPABILITY_STATUS.md` as `EXPERIMENTAL`.
- **PR N+1**: After confirmed device testing, change the default. Update
  `CAPABILITY_STATUS.md` to `PROVEN`. Reference device, OS version, and date.

### CAPABILITY_STATUS.md Registry (C1)

A structured markdown table at the project root tracking capability verification status:
- `PROVEN`: Device-verified, working end-to-end on physical hardware
- `EXPERIMENTAL`: Implemented but not fully device-tested, or tested with known failures
- `BROKEN`: Known non-functional; awaiting fix

Includes `Last verified` (date) and `Verified on` (device + OS version) per capability.
If a PROVEN capability's `Last verified` date is older than 30 days, treat as UNCONFIRMED.

### Quality Gate Default-Change Warning (C2)

`scripts/quality_gate.py` detects when a Riverpod provider's default return value changes
(via grep on git diff). If the new default is listed as `EXPERIMENTAL` in
`CAPABILITY_STATUS.md`, it emits a **warning** (not a hard block) requiring explicit
acknowledgment. The warning is a safety net; C5 is the primary enforcement mechanism.

### Review Gate Default-Change Trigger (C3)

Any PR that changes a default value in a Riverpod provider (detected via regex in the diff)
automatically adds `independent-perspective` to the specialist review panel. The
independent-perspective agent is specifically asked: "Does this change replace a proven
capability with an unproven one? What is the rollback plan?"

### OS Resource Lifecycle Invariant (B)

Codified in the `SpeechRecognitionService` abstract interface doc comments:
- `dispose()` MUST release OS resources unconditionally, regardless of `isListening`
- `onDone`/`onError` stream callbacks MUST release OS resources before modifying state flags
- New service implementations CANNOT start OS resources before confirming the connection
  they depend on is open

### ADR-0031 Amendment

ADR-0031 designated Deepgram as the primary STT engine. That designation is hereby
superseded: the STT default reverts to `speechToText` (the proven baseline) as of
commit following `e1ad873`. Deepgram remains available as an EXPERIMENTAL opt-in
engine. ADR-0031's decision lineage is preserved; this ADR records the revert.

## Alternatives Considered

### Alternative 1: Environment Separation (DEV/UAT)
Maintain separate environments where experimental features are deployed to DEV before
promoting to production. **Rejected**: The developer explicitly ruled this out. The
agentic framework must be self-contained. Environment separation pushes complexity into
deployment infrastructure where it is harder to audit and maintain.

### Alternative 2: Runtime Feature Flags
Gate experimental capabilities behind feature flags checked at runtime. **Rejected**:
Adds runtime complexity, requires a feature flag service or config mechanism, and
doesn't prevent the latent bug class (a feature flag doesn't enforce the OS resource
lifecycle invariant). The Two-PR pattern achieves the same isolation with less machinery.

### Alternative 3: Per-Capability Test Suites
Require a separate test suite per capability that must pass before promotion.
**Partially adopted**: The regression test requirement from the testing standards already
mandates regression tests for bug fixes. The CPP adds CAPABILITY_STATUS.md verification
and the Two-PR pattern on top of the existing test requirements.

### Alternative 4: `releaseHardware()` required interface method
Add a new `releaseHardware()` abstract method to `SpeechRecognitionService` that must
be called unconditionally and cannot be gated on any flag. **Deferred**: This is stronger
than the current documentation-level fix but requires all existing implementations to
be updated. The current approach (doc comment invariant + rule in `.claude/rules/`) is
lighter and sufficient for the current three-implementation scope. Revisit at 5+
implementations.

## Consequences

### Positive
- Experimental capabilities can no longer silently become production defaults without
  explicit two-step promotion
- The `CAPABILITY_STATUS.md` registry gives the team a shared vocabulary for capability
  maturity without requiring code audits
- The quality gate warning makes default changes visible in CI output
- The `independent-perspective` review trigger ensures at least one reviewer asks
  specifically about rollback plans before any default change lands

### Negative
- Every new capability requires two PRs to reach default status, adding process overhead
- `CAPABILITY_STATUS.md` is manually maintained and can go stale (mitigated by the
  30-day staleness warning)
- The Two-PR convention is enforced by review and quality gate warning, not by a
  compile-time mechanism — a determined agent could defeat it by updating
  `CAPABILITY_STATUS.md` to `PROVEN` in the same PR as the default change

### Known Enforcement Gap
The Two-PR convention does not have a mechanical compile-time enforcer. A single PR
could add implementation, mark the capability as `PROVEN` in `CAPABILITY_STATUS.md`,
and change the default simultaneously — defeating C2. The mitigation is: C2 makes the
change visible; the independent-perspective reviewer is specifically tasked with
catching this; and the provider default assertion test (see `test/providers/
voice_providers_test.dart`) would fail if the default changes without a test update.
This gap is accepted per Principle #8 (least-complex intervention first).

## References

- SPEC-20260305-080259: Full post-mortem and requirements
- DISC-20260305-080259: Specialist review discussion (architecture-consultant +
  independent-perspective findings)
- `CAPABILITY_STATUS.md`: Live capability registry
- `memory/bugs/regression-ledger.md`: Microphone leak post-mortem entry (2026-03-05)
- `.claude/rules/capability_protection.md`: Protocol enforcement rules
