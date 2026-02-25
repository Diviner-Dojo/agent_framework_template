---
spec_id: SPEC-20260225-160000
title: "Phase 12: Video Capture"
status: reviewed
risk_level: high
reviewed_by: [architecture-consultant, security-specialist, performance-analyst, independent-perspective]
discussion_id: DISC-20260225-030758-video-capture-architecture
---

## Goal

Add video recording and gallery pick to journal entries, with local playback, metadata stripping for privacy, and thumbnail generation. Cloud sync is deferred (feature-flagged off) until metadata stripping is validated in production.

## Context

Phase 9 (ADR-0018) delivered photo capture with EXIF stripping, background isolate processing, drift schema, Supabase Storage sync, and cascade delete. Phase 12 extends this with video, which introduces fundamentally different constraints: videos are 100-1000x larger than photos, can't be cheaply re-encoded to strip metadata, and require playback infrastructure.

ADR-0021 documents all architectural decisions from the deliberation (DISC-20260225-030758-video-capture-architecture). The independent-perspective agent raised the dependency spike as a prerequisite — `video_player`, `video_thumbnail`, and `ffmpeg_kit_flutter` must compile on the Galaxy S21 Ultra before feature code is written.

**Current state:** Schema v5, 80.1% coverage, Photos table + PhotoDao + PhotoService established.

### Key Constraints

- Videos are local-only at launch (cloud sync feature-flagged off per ADR-0021 §3)
- Metadata stripping required before local storage (GPS privacy — ADR-0021 §3)
- 60-second recording cap (ADR-0021 §2)
- STT must be paused during video recording (ADR-0021 §7)

## Requirements

### Functional

1. **Video recording** via device camera with 60s duration cap
2. **Video gallery pick** from device gallery
3. **Metadata stripping** of GPS/device info from video files before storage
4. **Thumbnail generation** at 320x180 JPEG for session timeline display
5. **Video playback** in full-screen modal when thumbnail tapped
6. **Video attachment** to journal sessions with chat message entry ("[Video]")
7. **Capture sheet** extended with "Record Video" and "Choose Video" options
8. **Storage management** with 2GB warning threshold
9. **Cascade delete** — session deletion removes video files + thumbnails + DB records

### Non-Functional

- Metadata stripping runs in background isolate (no UI jank)
- Thumbnail generation runs in background isolate
- Video playback uses static thumbnails in list (no auto-init controllers)
- File paths validated via UUID regex (path traversal prevention)
- STT paused during video recording (audio focus conflict prevention)

## Tasks

### Task 1: Dependency Spike

Add `video_player`, `video_thumbnail`, and `ffmpeg_kit_flutter` (min-GPL) to `pubspec.yaml`. Verify Android build compiles on Galaxy S21 Ultra. This follows the ADR-0015 precedent for dependency validation before feature code.

**Acceptance criteria:**
- [ ] `flutter build apk --debug` succeeds with all three packages
- [ ] No Gradle dependency conflicts

### Task 2: Schema v6 Migration — Videos Table

Add `Videos` drift table definition in `tables.dart`. Add nullable `videoId` column to `JournalMessages`. Create schema v6 migration in `app_database.dart`. Run `build_runner` to regenerate.

**Acceptance criteria:**
- [ ] `Videos` table with columns per ADR-0021 §1
- [ ] `JournalMessages.videoId` nullable column added
- [ ] Schema v6 migration creates table and adds column
- [ ] `build_runner` generates successfully

### Task 3: VideoDao

Create `lib/database/daos/video_dao.dart` with constructor-injected `AppDatabase` (ADR-0007 pattern). Methods parallel `PhotoDao`:

- `insertVideo(...)` — insert a new video record
- `getVideoById(String videoId)` — single video lookup
- `getVideosForSession(String sessionId)` — all videos for a session, ordered by timestamp
- `watchVideosForSession(String sessionId)` — reactive stream
- `updateCloudUrl(String videoId, String cloudUrl)` — after sync
- `updateSyncStatus(String videoId, String status)` — sync tracking
- `getVideosToSync()` — pending/failed videos
- `deleteVideo(String videoId)` — single delete
- `deleteVideosBySession(String sessionId)` — cascade step
- `getVideoCount()` — total count
- `getTotalVideoSize()` — sum of fileSizeBytes

Add `videoDaoProvider` to `database_provider.dart`.

**Acceptance criteria:**
- [ ] All methods implemented with type-safe drift queries
- [ ] Provider registered in database_provider.dart
- [ ] Unit tests in `test/database/video_dao_test.dart`

### Task 4: VideoService

Create `lib/services/video_service.dart` with:

- Named constants: `maxDurationSeconds = 60`, `maxFileSizeBytes = 100MB`, `thumbnailWidth = 320`, `thumbnailHeight = 180`, `thumbnailQuality = 70`
- `recordVideo()` — `image_picker.pickVideo(source: camera, maxDuration: 60s)`
- `pickFromGallery()` — `image_picker.pickVideo(source: gallery)`
- `processAndSave(File rawFile, String sessionId, String videoId)` — strip metadata via ffmpeg, generate thumbnail, save both to canonical paths. Returns `ProcessedVideo` result object.
- `canonicalVideoPath(baseDir, sessionId, videoId)` — UUID-validated path
- `canonicalThumbnailPath(baseDir, sessionId, videoId)` — UUID-validated path
- `deleteVideoFile(String localPath)` — boundary-checked deletion
- `deleteSessionVideos(String sessionId)` — remove entire `videos/{sessionId}/` dir
- `calculateTotalSize()` — total video storage on disk

Metadata stripping and thumbnail generation run in `Isolate.run()`.

**Acceptance criteria:**
- [ ] Metadata stripping via ffmpeg_kit_flutter (-map_metadata -1 -codec copy)
- [ ] Thumbnail at 320x180 JPEG 70%
- [ ] UUID regex validation on all path construction
- [ ] Background isolate processing
- [ ] Unit tests in `test/services/video_service_test.dart`

### Task 5: Video Providers

Create video-related Riverpod providers in `lib/providers/video_providers.dart`:

- `videoServiceProvider` — provides VideoService instance
- `sessionVideosProvider` — `StreamProvider.family` watching videos for a session
- `allVideosProvider` — stream of all videos (for future gallery)

Wire video into `SessionNotifier`:
- Add `attachVideo(File rawFile)` method (parallel to existing photo attachment flow)
- Creates "[Video]" message with `inputMethod: 'VIDEO'`, links via `videoId`
- Pauses STT if voice mode active before camera access

**Acceptance criteria:**
- [ ] Providers registered and functional
- [ ] `attachVideo()` creates message + video record
- [ ] STT paused during video capture

### Task 6: Capture Sheet Extension

Extend `lib/ui/widgets/photo_capture_sheet.dart`:

- Rename enum to `MediaSource` with values: `photoCamera`, `photoGallery`, `videoCamera`, `videoGallery`
- Add "Record Video" and "Choose Video from Gallery" options to the bottom sheet
- Rename function to `showMediaCaptureSheet()`

**Acceptance criteria:**
- [ ] Four options shown in bottom sheet
- [ ] Existing photo functionality unchanged
- [ ] Widget test in existing `test/ui/widgets/photo_capture_sheet_test.dart` (extended)

### Task 7: Video Player Widget

Create `lib/ui/widgets/video_player_widget.dart`:

- Stateful widget that owns `VideoPlayerController` lifecycle
- Play/pause button overlay
- Progress indicator
- Full-screen modal presentation
- Disposes controller on close

**Acceptance criteria:**
- [ ] Controller initialized on widget init, disposed on dispose
- [ ] Play/pause toggle works
- [ ] Progress bar shows position

### Task 8: Session Screen Integration

Wire video into `lib/ui/screens/journal_session_screen.dart`:

- Handle `MediaSource.videoCamera` and `MediaSource.videoGallery` from capture sheet
- Show video thumbnail with play overlay in chat message list
- Tap thumbnail opens `VideoPlayerWidget` in modal
- Pause STT before video recording, resume after

**Acceptance criteria:**
- [ ] Video capture works from session screen
- [ ] Thumbnail displays inline in chat
- [ ] Tap opens full-screen player
- [ ] STT correctly paused/resumed

### Task 9: Supabase Migration

Create `supabase/migrations/004_video_schema.sql` (or next available number):

- `videos` table mirroring drift schema with RLS
- `journal-videos` storage bucket (private, 500MB limit, video MIME types)
- Storage RLS policies (same pattern as journal-photos)
- Add `video_id` column to `journal_messages`

Note: Sync implementation is deferred (feature-flagged off). Migration is written now for future enablement.

**Acceptance criteria:**
- [ ] SQL migration creates table, indexes, RLS policies, and bucket
- [ ] RLS scopes to user's own data

### Task 10: Cascade Delete Extension

Extend `SessionDao.deleteSessionCascade()` with optional `VideoDao?` and `VideoService?` parameters. Delete video files + DB records as part of session cascade.

**Acceptance criteria:**
- [ ] Video files and thumbnails deleted on session delete
- [ ] Video DB records deleted on session delete
- [ ] Backward compatible (existing callers without video params still work)

## Risk Assessment

- **Dependency spike failure**: `ffmpeg_kit_flutter` may have Gradle conflicts with existing dependencies. Mitigation: spike is Task 1, before any feature code.
- **ffmpeg_kit_flutter maintenance**: Package has reduced activity. Mitigation: documented in ADR-0021 with platform channel fallback path.
- **Storage pressure**: Videos are 50-80MB each. Mitigation: 60s cap, 2GB warning, cleanup UI.
- **Audio focus conflict**: Camera vs STT mic access. Mitigation: explicit pause/resume (Task 5, Task 8).

## Affected Components

| File | Change |
|---|---|
| `pubspec.yaml` | Add video_player, video_thumbnail, ffmpeg_kit_flutter |
| `lib/database/tables.dart` | Add Videos table, videoId to JournalMessages |
| `lib/database/app_database.dart` | Schema v6 migration |
| `lib/database/daos/video_dao.dart` | **New** — Video CRUD |
| `lib/services/video_service.dart` | **New** — Capture, process, strip, thumbnail |
| `lib/providers/video_providers.dart` | **New** — Riverpod providers |
| `lib/providers/database_provider.dart` | Add videoDaoProvider |
| `lib/ui/widgets/photo_capture_sheet.dart` | Extend with video options |
| `lib/ui/widgets/video_player_widget.dart` | **New** — Playback widget |
| `lib/ui/screens/journal_session_screen.dart` | Wire video capture + display |
| `lib/providers/session_providers.dart` | Add attachVideo() |
| `supabase/migrations/004_video_schema.sql` | **New** — Cloud schema + bucket |
| `android/app/src/main/AndroidManifest.xml` | Add READ_MEDIA_VIDEO permission |

## Dependencies

- ADR-0021 (Video Capture Architecture) — accepted
- ADR-0018 (Photo Storage Architecture) — baseline being extended
- Phase 9 photo infrastructure — established patterns to follow
