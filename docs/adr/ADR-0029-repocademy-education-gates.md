---
adr_id: ADR-0029
title: "RepoCademy: voice-cleared education gates via a structured registry + transcript-ingest chokepoint"
status: accepted
date: 2026-07-15
decision_makers: [developer, orchestrator]
discussion_id: DISC-20260715-062334-build-repocademy-gate-plumbing
spec_id: SPEC-20260715-062207
supersedes:
extends:
scope: hybrid
risk_level: medium
confidence: 0.9
tags: [education-gate, principle-6, voice, repocademy, capture-pipeline, trust-boundary]
---

## Context

Principle #6 requires walkthrough → quiz → explain-back before merge, but the
gate machinery assumed the developer at a keyboard. In practice gates pile up as
deferrals: autonomous build sessions logged "EDUCATION GATE DEFERRED" as
BUILD_STATUS.md prose (the telemetry-dashboard cohort 3.x/4.1–4.4/5.1, the
distribute-B1 merge, the D2-backflow explain-back), with **no structured,
machine-readable record** of what is owed. Separately, the developer wants to
clear gates by voice — listening to chaptered repo walkthroughs on walks via a
new "RepoCademy" module in their insight_journal app (Flutter; it already has
the proven voice stack, a read-only `GithubCodeService`, and Supabase sync),
asking questions aloud, taking a conversational quiz, all formally logged.

Design was settled in an approved plan plus a 9-question grill session
(decisions D1–D9, checkpointed in insight_journal
`brainstorms/2026-07-15-repocademy-integration.md`). Key cross-repo facts: the
app's GitHub client is deliberately read-only (its ADR-0070 firewall), and the
framework already runs a watcher that polls Supabase and dispatches work.

## Decision

1. **The contract is the integration point, not the client.** A versioned
   **session-transcript JSON (v1)** — `docs/education/CONTRACTS.md` — is the
   only coupling between clients (phone app, future laptop CLI, plain chat)
   and the gate machinery.
2. **Structured gate registry**: `docs/education/gates.yaml`
   (managed by `scripts/education/gate_registry.py`) replaces prose-only
   deferrals. Gates carry scope (files/ADRs/spec), deferral history with
   rationale (Principle #6's "formally re-deferred" now has a home), attempts,
   and cleared_by/cleared_at/discussion_id evidence pointers.
3. **One ingest chokepoint**: `scripts/education/ingest_walkthrough_session.py`
   turns a transcript into the same formal record `/quiz` produces — a Layer-1
   discussion (create → events → sealed), `education_results` rows (enums
   matching the existing CHECK constraints), and a registry flip when the
   gate-cleared rule holds (narration completed AND quiz avg ≥ threshold
   [default 0.70] AND explain-back passed AND no deferral). Transcripts are
   **untrusted at the boundary**: validate-everything-then-write, enum
   whitelists, score range checks, length caps, idempotency per session_id,
   no transcript content in shell/SQL sinks (library calls + parameterized SQL).
4. **Evidence flow keeps humans in the loop — and the human merge is the
   certification.** Transcript grades are client-asserted (the client's LLM
   graded the spoken answers), so ingest performs registration, not
   certification: the developer reviewing and merging the evidence PR (or
   knowingly running ingest locally) is the load-bearing Principle #6 step,
   exactly as `/quiz` relies on the developer answering honestly. Guards that
   keep the registration honest: pass_threshold floored at 0.5 (not
   client-nullable), claimed quiz average cross-checked against the grade
   events, full transcript preserved verbatim in the sealed discussion for
   audit. The phone never gets GitHub write credentials; the watcher
   dispatches a desk-side agent to run ingest and open the evidence PR.
   (Client + watcher handler are follow-up specs; this ADR lands the repo-side
   plumbing they target.)

## Consequences

- Education gates become **queryable and clearable from anywhere** that can
  produce a valid transcript; `/quiz` remains fully supported and unchanged.
- Deferral debt is now visible (`gate_registry.py list --status open`) and
  auditable (per-gate history), closing a real Principle #6 enforcement gap.
- A new trust boundary exists (transcripts). It ships with same-change tests
  (per testing_requirements' safety-critical rule): validation rejections,
  end-to-end synthetic ingest, idempotent re-run, no-partial-write on reject.
- Narration completion is recorded as an `education_results` row
  (understand/walkthrough/1.0), making "walked" queryable — an additive
  extension of the existing quiz-only precedent.
- Follow-ups tracked in the insight_journal spec: RepoCademy MVP module,
  foreground-service phase (screen-off), backpacking mode (desk-built course
  bundles + offline store-and-forward), offline-TTS research workstream.

## Alternatives Considered

- **Standalone spawned app** — rejected: the extraction list was ~60% of
  insight_journal's services; module-in-journal with extraction-ready
  boundaries wins on time-to-value (grill Q&A, plan discussion).
- **In-app GitHub write service** for gate evidence — rejected: breaches the
  app's read-only firewall and puts write credentials on a phone; the
  Supabase-relay + watcher path reuses existing, human-gated machinery.
- **Per-client ingest logic** (app writes SQLite/discussions directly) —
  rejected: N clients × capture rules = drift; one chokepoint keeps Principle
  #2 (capture is automatic, enforced at the tooling layer) true.
