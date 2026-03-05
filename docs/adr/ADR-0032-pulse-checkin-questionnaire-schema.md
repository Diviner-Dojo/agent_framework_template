---
adr_id: ADR-0032
title: "Pulse Check-In Questionnaire Schema: Four-Table Design"
status: accepted
date: 2026-03-03
accepted_date: 2026-03-03
risk_level: medium
confidence: 0.88
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
questionnaire_templates  — instrument definitions with template-level scale (scaleMin/scaleMax)
questionnaire_items      — individual items per template (not questionnaire_questions)
checkin_responses        — one per check-in session (not per-question)
check_in_answers         — per-item answers linked to checkin_responses
```

Note: `user_checkin_config` (Task 8, Phase 1 Task 8) is defined in ADR but deferred to
schema v11. The four tables above are implemented in schema v10.

The schema is implemented as drift `Table` classes with type-safe DAOs. The composite
score formula's canonical source is in `CheckInScoreService` (Dart), not the database.
Scores are persisted to `checkin_responses.compositeScore` after calculation.

**Key deviations from initial proposal** (documented here per Principle 1 traceability):
1. Table `questionnaire_questions` was renamed to `questionnaire_items` in implementation.
2. Scale (`scaleMin`/`scaleMax`) is on `questionnaire_templates` (template-level), not per-item. Items share the template scale.
3. `checkin_responses` is one row per check-in session (not one row per question). Individual answers are normalized into `check_in_answers` (a separate table with one row per item).
4. `CheckInAnswers.value` is nullable (null = skipped item). No `rawValue` column.
5. `user_checkin_config` is deferred to schema v11 (Phase 1 Task 8).

## Schema Definition (As-Built — schema v10)

### `questionnaire_templates`

```dart
class QuestionnaireTemplates extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get name => text()();                      // e.g., "Pulse Check-In"
  TextColumn get description => text().nullable()();
  TextColumn get instrumentCode =>
      text().withDefault(const Constant('custom'))();   // 'who-5', 'phq-4', 'custom'
  TextColumn get version =>
      text().withDefault(const Constant('1.0.0'))();
  TextColumn get licenseInfo => text().nullable()();    // CC BY-NC-SA 3.0 for WHO-5
  BoolColumn get isSystemDefault =>
      boolean().withDefault(const Constant(false))();
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();
  IntColumn get scaleMin => integer().withDefault(const Constant(1))();
  IntColumn get scaleMax => integer().withDefault(const Constant(10))();
  IntColumn get sortOrder => integer().withDefault(const Constant(0))();
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}
```

### `questionnaire_items` (was `questionnaire_questions` in proposal)

```dart
class QuestionnaireItems extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get templateId =>
      integer().references(QuestionnaireTemplates, #id)();
  TextColumn get questionText => text()();
  TextColumn get minLabel => text().nullable()();       // e.g., "Very low"
  TextColumn get maxLabel => text().nullable()();       // e.g., "Excellent"
  BoolColumn get isReversed =>
      boolean().withDefault(const Constant(false))();   // was reverseScored
  IntColumn get sortOrder => integer().withDefault(const Constant(0))();
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();
  // Note: scale is on the template, not per-item. Items inherit template scaleMin/scaleMax.
}
```

### `check_in_responses` — one row per check-in session

```dart
class CheckInResponses extends Table {
  IntColumn get id => integer().autoIncrement()();
  TextColumn get sessionId =>
      text().references(JournalSessions, #sessionId)();
  IntColumn get templateId =>
      integer().references(QuestionnaireTemplates, #id)();
  DateTimeColumn get completedAt => dateTime()();
  RealColumn get compositeScore => real().nullable()(); // null if all items skipped
  TextColumn get syncStatus =>
      text().withDefault(const Constant('PENDING'))();  // PENDING | SYNCED | FAILED
}
```

### `check_in_answers` — one row per item per check-in

```dart
class CheckInAnswers extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get responseId =>
      integer().references(CheckInResponses, #id)();
  IntColumn get itemId =>
      integer().references(QuestionnaireItems, #id)();
  IntColumn get value => integer().nullable()();        // null = skipped
  // INVARIANT: Only one (responseId, itemId) pair per check-in.
  //            Enforced at application layer (no DB UNIQUE constraint yet — see advisory A2).
}
```

### `user_checkin_config` (deferred to schema v11 — Phase 1 Task 8)

Defined in ADR but not yet implemented. Will contain: userId, templateId, isEnabled,
reminderHour, reminderMinute, reminderDays, consecutiveDismissals, updatedAt.
`consecutiveDismissals` enforces the ADHD UX constraint: auto-disable reminders after
3 consecutive dismissals.

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
must NOT be used here. The general formula uses `QuestionnaireTemplate.scaleMin`
and `scaleMax` (template-level), passed to `CheckInScoreService` at call time.
Items with `isReversed = true` use this formula; others use the raw value directly.

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
