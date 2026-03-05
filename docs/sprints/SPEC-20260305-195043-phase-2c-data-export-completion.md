---
spec_id: SPEC-20260305-195043
title: "Phase 2C: Data Export Completion"
status: reviewed
risk_level: low
parent_spec: SPEC-20260302-adhd-informed-feature-roadmap
reviewed_by: [qa-specialist, architecture-consultant]
discussion_id: DISC-20260305-195130-phase-2c-data-export-completion-spec-review
---

## Goal

Complete the partial data export implementation so that all user data — sessions,
messages, check-in responses, photos, **and videos** — is included in the export JSON.
Fix the conditional-omission bug where `check_ins` and `photos` keys are silently
dropped from the session object when empty, making the schema unstable across users.

## Context

Export to the public Downloads folder was introduced in v0.18.1+14. At that time,
check-in responses, photos, and videos were missing. A subsequent sprint added
check-in responses and photos, but conditionally (`if (xxx.isNotEmpty)`), meaning
the schema varies depending on whether the user has check-ins or photos. Videos
were never added despite `VideoDao.getVideosForSession()` existing. This is the
final gap in Phase 2C from SPEC-20260302-adhd-informed-feature-roadmap.

**Implementation status entering this sprint:**
- ✅ Sessions, messages, mood/topic tags, journaling mode
- ✅ Check-in responses with per-item answers and question text (nested per-session, conditional)
- ✅ Photos with local path, timestamp, optional description (nested per-session, conditional)
- ❌ Videos: `VideoDao.getVideosForSession()` exists but never called in `_exportData()`
- ❌ Empty-array stability: `if (checkInsJson.isNotEmpty)` omits the key entirely

**Tasks are NOT in scope.** The acceptance criteria in the parent spec does not list
tasks, and `TaskDao` does not expose a `getTasksForSession()` method. Deferring tasks
to a future sprint avoids schema churn.

## Requirements

1. Call `videoDao.getVideosForSession()` for each session in `_exportData()` and
   include the results under a `videos` key in the session's export object.
2. Always include `check_ins`, `photos`, and `videos` keys in every session's export
   object, even when the corresponding list is empty (`[]`).
3. Video export schema per-entry:
   - Required: `video_id`, `local_path`, `thumbnail_path`, `duration_seconds`,
     `timestamp` (UTC ISO 8601). Note: `thumbnail_path` is non-nullable in the DB
     so it is always included (no null guard). Use `timestamp` and `local_path` to
     match existing photo/message export field naming convention.
   - Optional (include only when non-null): `description`, `width`, `height`,
     `file_size_bytes`.

## Constraints

- **No schema migration required.** Video table and DAO already exist.
- **No new providers.** `videoDaoProvider` already exists in `database_provider.dart`.
- **No breaking change to existing export fields.** Only additions.
- **File:** `lib/ui/screens/settings_screen.dart` — `_exportData()` method only.
  No other files need changes beyond tests.
- **Nested structure preserved.** Photos and check-ins are already nested under each
  session object; videos follow the same pattern. Top-level flat arrays (spec schema
  example) are not required by the acceptance criteria — nested is acceptable.

## Acceptance Criteria

- [ ] `check_ins` key is present in every session's export object, even when empty (`[]`).
- [ ] `photos` key is present in every session's export object, even when empty (`[]`).
- [ ] `videos` key is present in every session's export object, even when empty (`[]`).
- [ ] A session with one video produces a `videos` array with `video_id`, `local_path`,
      `thumbnail_path`, `duration_seconds`, and `timestamp` fields.
- [ ] Export with 0 check-ins, 0 photos, and 0 videos produces valid JSON (all three
      keys present as empty arrays).
- [ ] Widget test: export with a seeded video produces correct `videos` JSON
      (`video_id`, `local_path`, `thumbnail_path`, `duration_seconds`, `timestamp`).
      Requires `videoDaoProvider.overrideWithValue(VideoDao(database))` in test
      ProviderContainer overrides.
- [ ] Widget test: export with no check-ins/photos/videos produces empty arrays
      (not missing keys). Same `videoDaoProvider` override required.

## Risk Assessment

- **Low risk.** Adding fields to an existing export function. No database schema changes,
  no new providers, no new navigation, no new UI widgets.
- **Performance**: Video query is a single indexed lookup per session (same as photos).
  No concern for the target size (100 sessions, 30 videos < 5s).
- **Regression**: The existing `settings_data_management_test.dart` only tests that a
  SnackBar appears after tapping Export — it doesn't assert JSON structure. New tests
  will be unit tests against the DAO layer, not widget tests.

## Affected Components

| File | Change |
|------|--------|
| `lib/ui/screens/settings_screen.dart` | `_exportData()`: add video export, remove conditional key omission |
| `test/ui/settings_data_management_test.dart` | Add export structure tests (or new test file) |

## Dependencies

- `VideoDao.getVideosForSession()` — exists, no changes needed
- `videoDaoProvider` — exists in `database_provider.dart`
- No ADR required (no architectural change)
