---
analysis_id: "ANALYSIS-20260226-162550-powersync-dart"
discussion_id: "DISC-20260226-162550-analyze-powersync-dart"
target_project: "https://github.com/powersync-ja/powersync.dart"
target_language: "Dart (Flutter)"
target_stars: ~400
agents_consulted: [project-analyst, architecture-consultant, performance-analyst, security-specialist]
patterns_evaluated: 7
patterns_recommended: 4
patterns_deferred: 1
analysis_date: "2026-02-26"
license: "Apache 2.0"
license_constraint: "Permissive — code adaptation allowed"
---

## Project Profile

- **Name**: PowerSync Dart (powersync.dart)
- **Source**: https://github.com/powersync-ja/powersync.dart
- **Tech Stack**: Dart/Flutter, SQLite, Supabase integration, Drift bridge
- **Domain**: Offline-first sync architecture for mobile apps
- **Maturity**: Production SDK, well-documented, active maintenance

## Synthesis

7 patterns identified. ADOPT: PowerSync+Drift bridge (`SqliteAsyncDriftConnection`), SupabaseConnector `fatalResponseCodes`, `Table.localOnly()` for CalendarEvents, `waitForFirstSync()`. DEFER: `trackPreviousValues` (multi-device not yet needed).

Key conditions: background sync strategy must be decided first; `forTesting()` pattern redesign required.

## Pattern Recommendations

### ADOPT

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| PowerSync + Drift bridge | 21/25 | E15 | P2 |
| SupabaseConnector fatalResponseCodes | 22/25 | E16 | P2 |
| Table.localOnly() | 20/25 | — | P2 |
| waitForFirstSync() | 20/25 | — | P2 |

**PowerSync + Drift Bridge**: `SqliteAsyncDriftConnection` wraps PowerSync's SQLite database as Drift's backing connection. Drift remains the query layer; PowerSync becomes the transport layer. All 3 specialists converged on this recommendation.

Blocking conditions before adoption:
1. **Background sync strategy**: PowerSync's sync isolate dies when app backgrounds. Need `flutter_workmanager` or accept foreground-only sync.
2. **`forTesting()` redesign**: `AppDatabase.forTesting(NativeDatabase.memory())` won't work for synced tables. Need PowerSync test mode.
3. **`CalendarEvents` as `Table.localOnly()`**: Device-sourced data should NOT sync to Supabase.

**SupabaseConnector fatalResponseCodes**: Classify Postgres error codes (class 22, 23, 42501) as fatal — discard rather than retry. Without this, RLS violations cause infinite retry loops. All 3 specialists converged independently.

**Table.localOnly()**: CalendarEvents are device-sourced and should never sync. PowerSync's `localOnly` table flag prevents sync without requiring separate database.

**waitForFirstSync()**: Block UI until initial sync completes on first launch. Prevents showing stale/empty data.

### DEFER

| Pattern | Score | Enhancement | Priority |
|---------|-------|-------------|----------|
| trackPreviousValues | 17/25 | — | — |

**trackPreviousValues**: Multi-device conflict detection via field-level change tracking. Not needed until multi-device sync is implemented.

## License Impact

Apache 2.0 — Permissive. Code patterns and SupabaseConnector implementation can be directly adapted from PowerSync demo apps.

## Adoption Log Entries

All entries logged to `memory/lessons/adoption-log.md` with `Source: powersync`.

---

*See also: `docs/consolidated-enhancement-plan.md` for full implementation details and roadmap.*
