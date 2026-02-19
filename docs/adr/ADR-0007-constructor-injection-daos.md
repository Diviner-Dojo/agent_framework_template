---
adr_id: ADR-0007
title: "Constructor-Injection DAOs over drift @DriftAccessor Mixin"
status: accepted
date: 2026-02-19
decision_makers: [architecture-consultant, facilitator]
discussion_id: DISC-20260219-175738-phase1-spec-review
supersedes: null
risk_level: low
confidence: 0.88
tags: [drift, dao, testing, dependency-injection, database]
---

## Context

drift (the SQLite ORM used for local storage, per ADR-0002) provides a standard `@DriftAccessor` mixin pattern for Data Access Objects. This pattern tightly couples DAOs to the generated database class via Dart mixins and code generation.

During Phase 1 spec review, the architecture consultant identified that DAO testability is a critical requirement — every DAO method must be unit-testable against an in-memory database without mocking the ORM layer. The spec requires `AppDatabase.forTesting(NativeDatabase.memory())` as the test isolation pattern.

## Decision

Use **standalone classes with constructor-injected `AppDatabase`** instead of drift's `@DriftAccessor` mixin pattern for all DAOs.

```dart
// CHOSEN: Constructor injection
class SessionDao {
  final AppDatabase _db;
  SessionDao(this._db);
  // methods use _db.journalSessions, _db.select(), etc.
}

// REJECTED: @DriftAccessor mixin
// @DriftAccessor(tables: [JournalSessions])
// class SessionDao extends DatabaseAccessor<AppDatabase> with _$SessionDaoMixin {
//   SessionDao(super.db);
// }
```

## Alternatives Considered

### Alternative 1: @DriftAccessor Mixin (drift convention)
- **Pros**: Standard drift pattern, well-documented, auto-generates query accessors, less boilerplate
- **Cons**: Tighter coupling to generated code; `DatabaseAccessor` base class adds an abstraction layer that obscures the query construction; all online examples use this pattern which may confuse agents looking at drift documentation
- **Reason rejected**: Constructor injection is simpler, makes the `AppDatabase` dependency explicit, and directly enables `AppDatabase.forTesting()` without any adapter layer

### Alternative 2: Repository pattern with DAO as internal implementation
- **Pros**: Additional abstraction layer between business logic and data access; repositories could swap out DAOs for mock implementations
- **Cons**: Over-engineering for Phase 1; adds a layer that provides no value until sync is implemented in Phase 4
- **Reason rejected**: Principle #8 (least-complex intervention first); the repository layer will be introduced in Phase 4 when sync requires orchestration between local and remote data sources

## Consequences

### Positive
- DAOs are trivially testable via `AppDatabase.forTesting(NativeDatabase.memory())`
- Explicit dependency makes the coupling visible and the data flow traceable
- No generated DAO code to debug — only the table classes are generated
- Pattern is familiar to developers from Python/FastAPI dependency injection

### Negative
- Diverges from drift's documented convention — agents and developers reading drift examples will find the mixin pattern everywhere
- Slightly more boilerplate (must manually reference `_db.journalSessions` instead of getting auto-generated accessors)
- Future DAOs must follow this pattern for consistency, even if a developer familiar with drift would prefer mixins

### Neutral
- This decision does not affect the database schema, migration strategy, or query capabilities — only the Dart class structure of DAOs
- The decision is easily reversible (DAOs can be rewritten to use @DriftAccessor) without changing any caller code, since the public API is the same

## Linked Discussion
See: discussions/2026-02-19/DISC-20260219-175738-phase1-spec-review/
