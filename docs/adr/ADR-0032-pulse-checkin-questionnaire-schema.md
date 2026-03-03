---
adr_id: ADR-0032
title: "Pulse Check-In Questionnaire Schema: Four-Table Design"
status: proposed
date: 2026-03-03
risk_level: medium
confidence: 0.82
tags: [database, schema, pulse-checkin, adhd-roadmap, drift]
discussion_id: DISC-20260303-043107-adhd-roadmap-spec-review
supersedes: null
superseded_by: null
decision_makers: [Developer]
required_before: SPEC-20260302-adhd-informed-feature-roadmap Phase 1 Task 1
---

## Context

The ADHD Feature Roadmap (SPEC-20260302-adhd-informed-feature-roadmap) introduces the
Pulse Check-In: a brief (≤2-minute) adaptive mood/energy assessment using validated
psychometric instruments. Implementation requires a schema that can:

1. Store multiple questionnaire templates (WHO-5, PHQ-2, GAD-2, custom, future instruments)
2. Track individual question responses linked to journal sessions
3. Record composite scores and support AI correlation analysis
4. Support per-user customization of notification schedules and preferred instruments
   (Phase 1 Task 8)
5. Accommodate instrument versioning and license management

**Deviation from ADR-0025 §Alternative 3**: ADR-0025 rejected "mode as a separate table"
for `JournalingMode`. That rejection was correct for 4 static, rarely-changing modes.
The `questionnaire_templates` table in this ADR IS warranted because:
- Instruments have version numbers and external license metadata that must be stored
- Task 8 adds row-level user configuration (per-instrument enable/disable, custom schedules)
  that requires foreign key references from `user_checkin_config` to `questionnaire_templates`
- New instruments will be added over time; a table row is the appropriate extension point,
  not a Dart enum value

## Decision

**Implement a four-table schema in the drift AppDatabase:**

```
questionnaire_templates  — instrument definitions (WHO-5, PHQ-2, etc.)
questionnaire_questions  — individual items per template
checkin_responses        — per-session, per-question answers
user_checkin_config      — per-user notification and instrument preferences (Task 8)
```

The schema is implemented as drift `Table` classes with type-safe DAOs. The composite
score formula's canonical source is in `CheckInScoreService` (Dart), not the database.
Scores are persisted to `checkin_responses.compositeScore` after calculation.

## Schema Definition

### `questionnaire_templates`

```dart
class QuestionnaireTemplates extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get instrumentCode => text()(); // 'WHO-5', 'PHQ-2', 'GAD-2', 'custom'
  TextColumn get version => text()();        // '1998', '2012', '1.0.0'
  TextColumn get displayName => text()();
  TextColumn get description => text().nullable()();
  IntColumn get itemCount => integer()();
  RealColumn get minScore => real()();
  RealColumn get maxScore => real()();
  TextColumn get licenseInfo => text().nullable()(); // CC BY-NC-SA 3.0 for WHO-5
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();
}
```

### `questionnaire_questions`

```dart
class QuestionnaireQuestions extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get templateId => integer().references(QuestionnaireTemplates, #id)();
  IntColumn get orderIndex => integer()();  // 1-based display order
  TextColumn get questionText => text()();
  IntColumn get scaleMin => integer()();    // e.g., 0
  IntColumn get scaleMax => integer()();    // e.g., 4
  BoolColumn get reverseScored => boolean().withDefault(const Constant(false))();
  TextColumn get minLabel => text().nullable()(); // e.g., "All of the time"
  TextColumn get maxLabel => text().nullable()(); // e.g., "At no time"
}
```

### `checkin_responses`

```dart
class CheckInResponses extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get sessionId => text().references(JournalSessions, #id)();
  IntColumn get templateId => integer().references(QuestionnaireTemplates, #id)();
  IntColumn get questionId => integer().references(QuestionnaireQuestions, #id)();
  IntColumn get rawValue => integer().nullable()(); // null if skipped
  RealColumn get compositeScore => real().nullable()(); // null until all Qs answered
  DateTimeColumn get answeredAt => dateTime()();
}
```

**Note on `compositeScore`**: The composite score is written to each row in the response
group after the final question is answered (or after the session ends with partial
completion). Partial completion (fewer than `itemCount` non-null answers) does NOT produce
a composite score — the field remains null. This enables AI correlation queries to
distinguish "completed check-in" from "partially completed check-in."

### `user_checkin_config`

```dart
class UserCheckinConfig extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get userId => text()(); // Supabase auth user ID
  IntColumn get templateId => integer().references(QuestionnaireTemplates, #id)();
  BoolColumn get isEnabled => boolean().withDefault(const Constant(true))();
  IntColumn get reminderHour => integer().nullable()();   // 0–23, null = no reminder
  IntColumn get reminderMinute => integer().nullable()(); // 0–59
  TextColumn get reminderDays => text().nullable()();     // JSON array, e.g. ["Mon","Wed","Fri"]
  IntColumn get consecutiveDismissals => integer().withDefault(const Constant(0))();
  // Auto-disable after 3 consecutive dismissals (ADHD UX constraint)
  DateTimeColumn get updatedAt => dateTime()();
}
```

## Composite Score Formula

The composite score formula is the canonical computation in `CheckInScoreService`:

```
scoredValue(q) = reverseScored
    ? (q.scaleMax + q.scaleMin - rawValue)
    : rawValue

compositeScore = sum(scoredValue(q) for all non-null responses)
```

**Reverse-scoring formula**: `scaleMax + scaleMin - rawValue`
This is the general formula valid for any scale. For WHO-5 (0–4 scale):
`scaleMax + scaleMin - rawValue = 4 + 0 - rawValue = 4 - rawValue`

The `+1` variant (`scaleMax + 1 - rawValue`) is only valid when `scaleMin = 1` and
must NOT be used here. The general formula is stored in `QuestionnaireQuestions.scaleMin`
and `scaleMax` per-question, not hardcoded in `CheckInScoreService`.

**Edge cases**:
- Empty response list → `compositeScore = null` (not 0)
- All responses null (all skipped) → `compositeScore = null`
- Partial completion → `compositeScore = null` (per above)
- All questions answered (none null) → `compositeScore = sum(scoredValues)`

`CheckInScoreService.computeScore(List<CheckInResponseCompanion>)` is a pure function
(stateless) — no database access, no side effects. Tests verify the formula against
published WHO-5 scoring tables.

## WHO-5 License Decision

The WHO-5 Well-Being Index is published by the Psychiatric Centre North Zealand under
**CC BY-NC-SA 3.0**. The NC (NonCommercial) clause blocks use in commercial or freemium
distribution without a license request.

**Decision**: Proceed with WHO-5 implementation. Mitigation:
1. Track WHO-5 usage via `questionnaire_templates.licenseInfo` field.
2. Before any commercial distribution (App Store paid, freemium with in-app purchase,
   or enterprise license), request permission from Psychiatric Centre North Zealand.
3. The `instrumentCode` and template table design isolates WHO-5 as a swappable row —
   if the license request is denied or delayed, WHO-5 items can be replaced with
   equivalent custom questions without schema changes.

PHQ-2 and GAD-2 are published by Pfizer and in the public domain for clinical and
research use; no commercial restriction applies.

## Sync Strategy

Check-in response data is clinical-grade and follows the same sync constraints as
journal entries (ADR-0004, ADR-0012):
- Local-first: all writes go to the local drift database first
- Async background sync to Supabase via the existing sync infrastructure
- Row-level Supabase RLS: `user_id` column on all tables; users access only their own data
- `user_checkin_config` includes `userId` for RLS enforcement

`questionnaire_templates` and `questionnaire_questions` are seeded locally (bundled with
the app). They are not synced from Supabase — the app ships with the instrument definitions.
Updates to instruments (new versions, new instruments) are delivered via app updates.

## Alternatives Considered

### A. Single `checkin_sessions` table with JSON blob for responses
Rejected. JSON blobs break the ability to query individual question-level responses for
AI correlation analysis (e.g., "is energy low on Wednesdays?" requires per-question,
per-day queries). The four-table design enables these queries with standard SQL JOINs.

### B. Extend `journal_sessions` with check-in columns
Rejected. Check-ins are an independent clinical instrument with their own scoring logic,
versioning, and potential for completion independent of a journal session. Mixing them
into `journal_sessions` creates a coupling that would complicate Phase 3 AI correlation
queries and Phase 4 data export.

### C. Encode instruments as Dart enums (ADR-0025 pattern)
Rejected for this use case. ADR-0025 correctly used a Dart enum + TEXT column for
`JournalingMode` because modes are static, have no external metadata, and don't require
per-user row-level configuration. Questionnaire instruments require:
- Version metadata (which revision of WHO-5?)
- License metadata (NC clause tracking)
- Per-user enable/disable config via foreign key
- Addition of new instruments without app code changes
These requirements mandate a database table, not an enum.

### D. Separate database for clinical data
Rejected. The operational complexity of managing two drift databases outweighs the
isolation benefit at this scale. RLS policies on Supabase provide the necessary access
control. Revisit if clinical data ever requires HIPAA compliance controls (would require
an ADR at that time).

## Consequences

**If implemented:**
- Phase 1 of SPEC-20260302-adhd-informed-feature-roadmap can proceed.
- WHO-5, PHQ-2, and custom instruments are immediately storable.
- AI correlation analysis (Phase 2) has per-question response data available for queries.
- Schema is extensible: new instruments add rows to `questionnaire_templates` and
  `questionnaire_questions` without migrations.
- Task 8 user configuration is unblocked (`user_checkin_config` table ready).

**Schema migration**: New `AppDatabase` migration version required. Existing users with
no check-in data will migrate seamlessly (additive-only schema change).

**If deferred:**
- Phase 1 is blocked. No check-in data can be persisted.
- The Pulse Check-In UI (Phase 1 Tasks 3–7) cannot be tested end-to-end.

## Linked Discussion

- DISC-20260303-043107-adhd-roadmap-spec-review
- SPEC-20260302-adhd-informed-feature-roadmap — Phase 1 (Tasks 1–9)
- ADR-0025 — JournalingMode enum (Alternative 3 rejection rationale)
- ADR-0004 — Local-first sync architecture
- ADR-0012 — Supabase sync strategy
