---
id: SPEC-20260715-062207
title: RepoCademy education-gate plumbing (registry + ingest chokepoint + contracts)
status: approved
type: feature
created: 2026-07-15
approved_by: developer (plan-mode approval, 2026-07-15 session)
discussion: DISC pending (build discussion created at build start)
related_adr: ADR-0029
scope_note: Repo-side half of the RepoCademy system; the client app lives in insight_journal (see its SPEC-20260715-repocademy).
---

# RepoCademy Education-Gate Plumbing

## Request Context

The developer wants to clear education gates by voice — listening to chaptered
walkthrough courses of a repo (this one first) on walks/treadmill via a new
"RepoCademy" module in their insight_journal app, with sessions formally logged
so Principle #6 gates officially clear. Design was settled in an approved plan +
a 9-question grill session (see insight_journal
`brainstorms/2026-07-15-repocademy-integration.md`). This spec covers only the
**framework-repo side**: the structured gate registry, the session-transcript
ingest chokepoint, and the integration contracts. Explicit constraint: session
transcripts are untrusted input; ingest must validate before any write and be
idempotent.

## Problem

1. Education-gate deferrals are narrative-only (BUILD_STATUS.md prose) — nothing
   machine-readable exists for a client to discover "which gates are open."
2. Nothing can turn an externally-produced walkthrough/quiz session into the
   formal record (Layer-1 discussion + `education_results` rows) that clears a
   gate. `/quiz` does this interactively; a voice client cannot.

## Requirements

- **R1** `docs/education/gates.yaml` — structured registry: gate_id, title,
  origin, scope (files/adrs/spec), reason_deferred, status
  (open|cleared|re-deferred), deferral history, cleared_by/cleared_at/
  discussion_id. Seeded from BUILD_STATUS.md deferral archaeology.
- **R2** `scripts/education/gate_registry.py` — load/validate/save library +
  CLI (`list`, `add`, `clear`, `re-defer`). Validation fails closed.
- **R3** `scripts/education/ingest_walkthrough_session.py` — THE chokepoint:
  session-transcript JSON (contract v1) → validate everything → create
  discussion + write events + record `education_results` rows + flip registry.
  All-or-nothing (validate-then-write), idempotent per session_id (re-run =
  no-op), enums whitelisted against `record_education.py`'s CHECK constraints,
  scores must be in [0,1], no transcript content ever interpolated into
  shell/SQL (library calls + parameterized SQL only).
- **R4** `docs/education/CONTRACTS.md` — versioned transcript-JSON v1 spec +
  chapter/course format + knowledge-note format (what insight_journal builds
  against).
- **R5** Gate-cleared rule: narration completed AND quiz average ≥ threshold
  (default 0.70) AND explain-back passed. Learn-mode sessions never touch the
  registry.
- **R6** Event/row mapping (canonical): narration→educator/proposal +
  understand/walkthrough/1.0/true; Q&A→developer/question + educator/evidence;
  quiz item→question/evidence/critique events + per-item education row;
  explain-back trio + evaluate/explain-back row; deferral→facilitator/decision +
  registry re-defer entry; closing facilitator/synthesis.
- **R7** Tests ship in the same change (safety-relevant ingest boundary):
  registry validation, transcript validation rejections, synthetic end-to-end
  ingest asserting events.jsonl + education_results + registry flip, and
  idempotent re-run.

## Non-goals

- The Flutter client, Supabase schema, watcher handler (follow-up phases).
- Course generation (client-side).
- Auto-closing gates without the pass rule; auto-merging anything.

## iOS Parity

Not applicable — Python repo-side tooling only. (The client spec in
insight_journal carries the iOS Parity classification.)

## Acceptance Criteria

- AC1 `gate_registry.py list` shows seeded open gates; add/clear/re-defer
  round-trip preserves history; invalid statuses/ids rejected.
- AC2 Ingest of a valid synthetic gate-mode transcript creates the discussion
  dir + events.jsonl with the R6 mapping, inserts the expected
  `education_results` rows, and flips the gate to `cleared` with
  cleared_by=session_id.
- AC3 Re-running the same transcript is a no-op (detected via existing
  education_results session_id) and exits 0 with an "already ingested" notice.
- AC4 Transcripts with bad enum values, out-of-range scores, wrong
  contract_version, or malformed session_id are rejected with NO partial
  writes.
- AC5 A learn-mode transcript ingests without touching gates.yaml.
- AC6 A failing quiz (avg < threshold) ingests fully but does NOT clear the
  gate (stays open, attempt recorded).
- AC7 Quality gate passes; new-code coverage ≥ 80%.
