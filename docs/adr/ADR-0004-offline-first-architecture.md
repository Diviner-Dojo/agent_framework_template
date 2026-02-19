---
adr_id: ADR-0004
title: "Offline-First with Local SQLite Source of Truth"
status: accepted
date: 2026-02-18
decision_makers: [developer]
discussion_id: null  # Pre-framework decision — documented from product brief
supersedes: null
risk_level: high
confidence: 0.90
tags: [architecture, offline-first, sqlite, sync, drift]
---

## Context

A journaling app must be available whenever the user wants to capture a thought — including on airplanes, in areas with poor connectivity, and during network outages. The app will also register as the Android default assistant, meaning it must respond instantly to the assistant gesture regardless of network state.

Sync to the cloud is needed for backup and future multi-device support, but must not block the journaling experience.

## Decision

Adopt an **offline-first architecture** where:

1. **Local drift/SQLite is the authoritative source of truth** — all reads and writes go to the local database first
2. **Cloud (Supabase) is a sync target** — a backup and eventual consistency layer, never the primary data source
3. **Sync is background and non-blocking** — WorkManager schedules sync tasks with network-available constraints
4. **Sync uses exponential backoff** — 30s → 1m → 5m on failure, with KEEP policy (don't replace pending tasks)
5. **Conflict resolution is last-write-wins** — based on `updated_at` timestamp, sufficient for single-user journaling
6. **Uploads are idempotent** — UPSERT semantics with client-generated UUIDs prevent duplicates on retry
7. **Per-session sync tracking** — each `JournalSession` carries a `syncStatus` field (PENDING/SYNCED/FAILED)

## Alternatives Considered

### Alternative 1: Cloud-First with Offline Cache
- **Pros**: Simpler sync logic, single source of truth in the cloud, real-time multi-device sync
- **Cons**: App is unusable without network; latency on every write; assistant gesture would fail offline; poor UX in low-connectivity environments
- **Reason rejected**: Fundamentally incompatible with the "journal anytime, anywhere" requirement and assistant gesture responsiveness

### Alternative 2: Hybrid (Read from cloud when available, write locally)
- **Pros**: Fresh data from cloud, local writes for offline resilience
- **Cons**: Complex read routing logic; inconsistent data views during partial sync; reads may fail or be slow on poor connections
- **Reason rejected**: Added complexity with marginal benefit for a single-user app where local data is always the most recent

### Alternative 3: CRDTs for Conflict-Free Sync
- **Pros**: Automatic conflict resolution, supports multi-device concurrent editing
- **Cons**: Significant implementation complexity, overkill for single-user journaling, CRDT libraries for Dart/Flutter are immature
- **Reason rejected**: Last-write-wins is sufficient for MVP single-user; CRDT can be evaluated if multi-device editing is added later

## Consequences

### Positive
- App works fully without network — zero degradation in core journaling experience
- Assistant gesture responds instantly (no network round-trip)
- Users in low-connectivity areas get full functionality
- Simple mental model: local DB is always current, cloud catches up eventually
- Idempotent sync with client-generated UUIDs makes retry logic trivial

### Negative
- Multi-device scenarios may see stale data until sync completes (acceptable for MVP)
- Last-write-wins can lose concurrent edits from multiple devices (mitigated: single-user for now)
- Local database size grows without cloud offloading (mitigated: journal data is small-text)
- Sync failures require UI indication so users know their data isn't backed up yet

### Neutral
- WorkManager handles platform-specific background task scheduling
- Sync status per session provides granular visibility into backup state
- Migration to more sophisticated conflict resolution is possible without changing the local-first model

## Linked Discussion
Pre-framework decision — documented from product brief (`docs/product-brief.md`, Offline-First Sync Engine section).
