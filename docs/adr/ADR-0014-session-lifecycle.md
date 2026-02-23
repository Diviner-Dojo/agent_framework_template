---
adr_id: ADR-0014
title: "Session Lifecycle: Delete, Discard, and Resume"
status: accepted
date: 2026-02-23
decision_makers: [facilitator, architecture-consultant, qa-specialist]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [session-management, ux, database, schema]
---

## Context

Phase 5 completed search and memory recall, but users have no way to:
1. **Delete** past sessions they no longer want
2. **Discard** accidental or empty sessions without saving
3. **Resume** a past journal entry to continue writing

These are the most pressing UX gaps. The app stores personal journal data locally with optional cloud sync, so lifecycle operations must consider both local and remote implications.

## Decision

### Delete Strategy: Hard Delete (No Soft Delete)
Sessions and messages are permanently removed from the local SQLite database. No `is_deleted` column or tombstone records.

**Cascade**: Application-level delete (messages first, then session). Drift's `references()` is documentation-only; `PRAGMA foreign_keys` is not enabled. The DAO enforces delete order.

**Cloud sync limitation**: Sessions with `syncStatus = 'SYNCED'` are deleted locally only. The Supabase copy persists until a dedicated Edge Function for remote deletion is implemented (deferred to a future phase).

### Empty Session Auto-Discard
When `endSession()` is called and the session has zero USER messages (only the ASSISTANT greeting), the session is automatically discarded instead of generating a summary. A `wasAutoDiscardedProvider` signals the UI to show a SnackBar notification.

### Resume Semantics
Resuming a past session:
- Preserves the original `startTime` (no timestamp reset)
- Clears `endTime` (session is active again)
- Sets `isResumed = true` and increments `resumeCount`
- Reverts `syncStatus` to `'PENDING'` (resumed content needs re-sync)
- Loads existing messages into the conversation context
- A fixed resume greeting replaces the normal time-of-day greeting (Layer A only for Phase 6)

### Schema Changes (v1 -> v2)
Two new columns on `journal_sessions`:
- `is_resumed` (BOOLEAN, default false)
- `resume_count` (INTEGER, default 0)

New index: `idx_sessions_start_time_desc` on `start_time DESC` for paginated landing page queries.

## Alternatives Considered

### Alternative 1: Soft Delete with `is_deleted` Column
- **Pros**: Recoverable deletes, simpler cloud sync reconciliation
- **Cons**: Every query needs `WHERE is_deleted = false`, increases query complexity, storage bloat for personal journal
- **Reason rejected**: Personal journal has no compliance/audit needs. Hard delete is simpler and users expect "delete" to mean delete.

### Alternative 2: Database-Level Cascade (`PRAGMA foreign_keys = ON`)
- **Pros**: Automatic cascading, enforced referential integrity
- **Cons**: Drift doesn't enable PRAGMA by default; enabling it requires custom setup and risks breaking existing data patterns. Application-level cascade is explicit and testable.
- **Reason rejected**: Unnecessary complexity. Application-level cascade with DAO methods is sufficient and more testable.

### Alternative 3: Overload `startSession()` for Resume
- **Pros**: Single entry point for session creation
- **Cons**: Different semantics (load existing messages, preserve startTime, increment count) would make startSession() complex with branching logic
- **Reason rejected**: Separate `resumeSession()` method is clearer and more maintainable.

## Consequences

### Positive
- Users can manage their journal data (delete unwanted entries, discard mistakes)
- Empty sessions don't clutter the session list
- Resume enables multi-sitting entries without starting over
- Schema v2 migration is additive (new columns with defaults) — safe upgrade

### Negative
- Cloud-synced sessions persist in Supabase after local delete (data asymmetry until remote delete Edge Function is built)
- Resume changes syncStatus, triggering re-upload of the full session on next sync

### Neutral
- Hard delete is irreversible — UI must confirm before executing
- The `is_resumed` and `resume_count` columns are metadata for analytics; they don't change core session behavior
