---
adr_id: ADR-0021
title: "Video Capture Architecture — Recording, Storage, and Sync"
status: accepted
date: 2026-02-25
decision_makers: [developer, facilitator, architecture-consultant, security-specialist, performance-analyst, independent-perspective]
discussion_id: DISC-20260225-030758-video-capture-architecture
supersedes: null
risk_level: high
confidence: 0.90
tags: [architecture, video, storage, privacy, metadata, sync, supabase, ffmpeg]
---

## Context

Phase 12 adds video capture to journal entries, extending the photo integration established in Phase 9 (ADR-0018). Users can record short videos or pick from gallery to attach visual moments to sessions. This requires decisions on:

- How to structure video data (extend Photos table vs. separate table)
- How to handle GPS metadata embedded in video containers (privacy)
- Duration and file size limits (storage management)
- Cloud sync strategy (videos are 100-1000x larger than photos)
- Video playback dependency selection
- Thumbnail generation for the session timeline UI

The app already has a mature photo pipeline: `image_picker` for capture, `image` package for EXIF stripping via re-encoding in a background isolate, drift `Photos` table with `PhotoDao`, Supabase Storage `journal-photos` bucket, and sync tracking. Video must integrate with this existing infrastructure without regressing it.

Key constraint: unlike photos, videos cannot be cheaply re-encoded on-device to strip metadata. A 60-second 1080p video is 50-80MB — re-encoding would consume significant CPU, battery, and time. This breaks the assumption underlying ADR-0018 §1 (EXIF stripping is "free" because re-encoding is already needed for resize).

## Decision

### 1. Separate `Videos` Table with Dedicated `VideoDao`

Create a new `Videos` drift table rather than extending the `Photos` table with a `mediaType` discriminator. Schema v6 migration.

**Videos table columns:**
- `videoId` (TEXT PK, client-generated UUID)
- `sessionId` (TEXT FK to JournalSessions)
- `messageId` (TEXT nullable — links to the JournalMessage representing this video)
- `localPath` (TEXT — relative path to video file)
- `thumbnailPath` (TEXT — relative path to thumbnail JPEG)
- `cloudUrl` (TEXT nullable — set after successful upload)
- `description` (TEXT nullable — user caption)
- `durationSeconds` (INTEGER — recording duration)
- `fileSizeBytes` (INTEGER nullable — set after processing)
- `width` (INTEGER nullable)
- `height` (INTEGER nullable)
- `syncStatus` (TEXT, default 'PENDING')
- `createdAt`, `updatedAt` (DATETIME)

Additionally, a nullable `videoId` column added to `JournalMessages` (parallel to existing `photoId`).

**Rationale**: The `CalendarEvents` table in Phase 11 established the pattern — logically distinct entities get their own table and DAO, even when they share common columns with existing tables. Extending `Photos` with a discriminator would require all 14 `PhotoDao` methods to add `mediaType` filtering, creating silent correctness risk. Every existing caller of `getAllPhotos()` or `getPhotosForSession()` would return videos interleaved with photos unless explicitly filtered — a regression that has no compile-time guard.

### 2. Duration and Size Limits

- **60-second recording cap** enforced at the recording layer via `image_picker`'s `maxDuration` parameter. This keeps file sizes in the 50-80MB range (H.264 1080p/30fps).
- **100MB post-capture size cap** enforced in `VideoService.processAndSave()`. Files exceeding this limit are rejected with a typed error.
- **2GB storage budget warning** — the app warns the user when total video storage approaches 2GB and offers cleanup of oldest videos.

Limits are defined as named constants in `VideoService`, co-located with processing logic (parallel to `_maxDimension` and `_jpegQuality` in `PhotoService`).

### 3. Metadata Stripping via `ffmpeg_kit_flutter` (Phased Sync)

Use `ffmpeg_kit_flutter` min-GPL package for metadata stripping without re-encoding:

```
-i input.mp4 -map_metadata -1 -c:v copy -c:a copy output.mp4
```

This strips all moov atom metadata (GPS coordinates, device info, timestamps) while preserving video/audio quality and file size.

**Phased sync approach:**
- **Phase 1 (launch)**: Video files are local-only. `ffmpeg_kit_flutter` strips metadata before local storage. Cloud sync for video is feature-flagged off.
- **Phase 2 (future)**: Cloud sync enabled after stripping is validated in production. The upload code path is gated — unreachable unless `stripMetadata()` has completed successfully on the file. A load-bearing unit test enforces this gate.

**Privacy rationale**: ADR-0018 §1 strips all EXIF from photos. ADR-0019 §2 excludes coordinates from cloud sync. Accepting GPS metadata in video files while stripping it from photos would create an inconsistency in the privacy model. A user relying on photo EXIF stripping would reasonably expect the same for video.

**Binary size impact**: `ffmpeg_kit_flutter` min-GPL adds approximately 8-12MB to the APK. This is the cost of maintaining the project's documented privacy posture.

**Maintenance risk**: `ffmpeg_kit_flutter` has reduced maintenance activity. If it becomes unmaintained, the fallback is a platform channel to Android's `MediaMuxer` for selective metadata stripping, or accepting the residual risk with a documented decision update to this ADR.

**Scope constraint**: `ffmpeg_kit_flutter` is used ONLY for metadata stripping. No other ffmpeg capabilities (transcoding, trimming, effects) should be adopted without a separate ADR.

### 4. Separate `journal-videos` Supabase Storage Bucket

Create a new Supabase Storage bucket rather than extending `journal-photos`:

- **Bucket**: `journal-videos`
- **Public**: false
- **File size limit**: 500MB (accommodates up to ~5 minutes if limits are relaxed later)
- **Allowed MIME types**: `['video/mp4', 'video/quicktime']`
- **RLS**: Same pattern as `journal-photos` — users can only CRUD files in their own directory segment

**Rationale**: Photos and videos have fundamentally different size envelopes (10MB vs. 150+MB). Sharing a bucket would require raising the photo bucket's file size limit to accommodate video, weakening protection against photo size abuse. Independent buckets allow independent policy configuration.

**Sync implementation**: Add `syncPendingVideos()` and `uploadSessionVideos()` methods to `SyncRepository`. `VideoDao?` injected via optional parameter, consistent with how `PhotoDao?` and `CalendarEventDao?` are currently injected. Storage path: `{userId}/videos/{videoId}.mp4`.

**Upload strategy**: Videos must NOT use `readAsBytes()` (which loads the entire file into the Dart heap). Use Supabase Storage's `upload(path, file)` which streams from a `File` object. Upload concurrency for video is limited to 1 (sequential), WiFi-only by default.

### 5. `video_player` for Playback

Use `video_player` (Flutter team, `^2.9.1`) for video playback.

**UI pattern**: In the session chat list, show a static thumbnail image with a play overlay icon. Only initialize `VideoPlayerController` when the user taps to play. Use a modal/full-screen player for playback. Dispose the controller immediately on close.

**Rationale**: ADR-0018 §2 established the precedent of preferring Flutter built-ins over third-party wrappers (`InteractiveViewer` over `photo_view`). `chewie` wraps `video_player` with minimal benefit beyond what a ~50-line custom `VideoPlayerWidget` provides. `media_kit` adds 30-40MB binary for capabilities (hardware decoding, subtitle support, broad format support) the app does not need — device-recorded MP4s are handled natively by `video_player`.

### 6. `video_thumbnail` for Thumbnail Generation

Use `video_thumbnail` package for on-capture thumbnail generation:

- **Resolution**: 320x180 pixels
- **Format**: JPEG at 70% quality (~15-25KB per thumbnail)
- **Storage**: `videos/{sessionId}/{videoId}_thumb.jpg` (under the videos directory, NOT photos)
- **Timing**: Generated in a background `Isolate.run()` call as part of the video processing pipeline, before returning to the caller

`VideoService.canonicalThumbnailPath()` follows the UUID regex validation pattern from `PhotoService.canonicalPath()`.

### 7. Audio Focus Interaction with Voice Mode

When video recording begins during an active voice session:
- Pause STT listener (`stopListening()`) before starting camera audio capture
- Resume STT after video recording completes
- Video capture pauses voice mode; it does not resume automatically

This eliminates concurrent microphone access conflicts between the STT service (`record` package) and the camera's audio track.

### 8. File Storage Layout

Videos and thumbnails stored in `getApplicationSupportDirectory()`:
```
videos/{sessionId}/{videoId}.mp4       — processed video (metadata stripped)
videos/{sessionId}/{videoId}_thumb.jpg — thumbnail JPEG
```

Path construction validated by `VideoService.canonicalVideoPath()` and `VideoService.canonicalThumbnailPath()`, both using UUID regex validation identical to `PhotoService.canonicalPath()`.

Cascade delete: `VideoService.deleteSessionVideos()` removes the entire `videos/{sessionId}/` directory (both video files and thumbnails). `VideoDao.deleteVideosBySession()` removes DB records. Both called from `SessionDao.deleteSessionCascade()` with optional `VideoDao?` and `VideoService?` parameters.

## Alternatives Considered

### Alternative 1: Extend Photos Table with `mediaType` Discriminator
- **Pros**: Fewer files to create, single DAO, single sync path
- **Cons**: All 14 PhotoDao methods need mediaType filtering; `getAllPhotos()` returns videos (crashes `Image.file()`); nullable video-specific columns pollute photo schema; no compile-time enforcement of filter
- **Reason rejected**: Creates silent correctness risk. Established project pattern (CalendarEvents in Phase 11) uses separate tables for distinct entities.

### Alternative 2: Video as Opaque File Attachment (Native Player via Intent)
- **Pros**: Eliminates `video_player` and `video_thumbnail` dependencies entirely; minimal APK impact; leverages native video player quality
- **Cons**: No in-app playback experience; breaks the immersive journal reading flow; can't show inline thumbnails in chat timeline
- **Reason rejected**: Valid MVP simplification but sacrifices too much UX polish. May be offered as a fallback if `video_player` has compatibility issues.

### Alternative 3: Defer Video, Extend Voice Notes Instead
- **Pros**: Voice notes are 1-2MB for 60s (vs. 30-60MB for video); `record` package already a dependency; compatible with voice-first interaction model
- **Cons**: Voice notes solve a different problem ("audio I can't transcribe") than video ("visual moment capture"); the user explicitly requested video
- **Reason rejected**: Different feature serving a different use case. Voice notes could be added separately in a future phase.

### Alternative 4: Single `journal-media` Supabase Bucket
- **Pros**: Simpler bucket management, single set of RLS policies
- **Cons**: Shared file size limit means raising photo limit to accommodate video; video MIME types accepted in what was a photos-only bucket; name becomes a misnomer
- **Reason rejected**: Independent buckets allow independent size/MIME/RLS policies per content type. Follows the CalendarEvents precedent of separate infrastructure per entity type.

### Alternative 5: Accept GPS Metadata Risk (Document Only)
- **Pros**: No `ffmpeg_kit_flutter` dependency; no binary size increase; simpler processing pipeline
- **Cons**: Directly contradicts ADR-0018 (photo EXIF stripping) and ADR-0019 (coordinate exclusion from cloud); creates inconsistent privacy model
- **Reason rejected**: Unacceptable privacy regression. The project's established posture is strip-before-storage.

## Consequences

### Positive
- Privacy model remains consistent: metadata stripped from both photos and videos before storage
- `PhotoDao` and all existing photo queries remain unchanged (no regression risk)
- Independent Supabase bucket allows video-appropriate size limits without affecting photos
- Phased sync approach allows shipping video capture quickly (local-only) while deferring cloud complexity
- Background isolate processing keeps UI responsive during metadata strip + thumbnail generation

### Negative
- APK size increases ~15MB (`video_player` ~2MB + `video_thumbnail` ~5MB + `ffmpeg_kit_flutter` min-GPL ~8MB)
- Video files are large (50-80MB each) — storage management becomes important
- `ffmpeg_kit_flutter` has maintenance risk (reduced community activity)
- Cloud sync for video is deferred to Phase 2 — videos are initially local-only and not backed up

### Neutral
- `image_picker` (already a dependency) supports `pickVideo()` with `maxDuration` parameter — no new dependency for capture
- The separate Videos table adds one drift table definition and one DAO file — consistent with the project's one-DAO-per-entity pattern
- Video playback in the journal uses a modal/full-screen approach (same pattern as photo viewing)

## Prerequisites

1. **Dependency spike**: Validate that `video_player`, `video_thumbnail`, and `ffmpeg_kit_flutter` all compile cleanly in an Android build on the Galaxy S21 Ultra before implementing any feature code. This follows the ADR-0015 precedent (STT dependency spike).
2. **Supabase migration**: `004_video_schema.sql` (or next available number) for the cloud-side Videos table and `journal-videos` storage bucket.

## Linked Discussion

See: discussions/2026-02-25/DISC-20260225-030758-video-capture-architecture/

## References

- ADR-0018: Photo Storage Architecture (baseline being extended)
- ADR-0019: Location Privacy Architecture (privacy posture precedent)
- ADR-0004: Offline-First Architecture (storage constraints, sync pattern)
- ADR-0012: Optional Auth with Upload-Only Cloud Sync (sync pattern)
- ADR-0007: DAO Constructor Injection (one DAO per entity)
- ADR-0015: Voice Mode Architecture (dependency spike precedent)
