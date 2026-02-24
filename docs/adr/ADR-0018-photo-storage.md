---
adr_id: ADR-0018
title: "Photo Storage Architecture — Camera Integration and Image Management"
status: accepted
date: 2026-02-24
decision_makers: [developer]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [architecture, photos, storage, camera, exif, privacy, supabase]
---

## Context

Phase 9 adds photo capture to journal entries. Users can attach photos (camera or gallery) to sessions. This requires decisions on:

- How to strip EXIF metadata (privacy — GPS coordinates, device info)
- How to display full-screen photos with zoom
- Where to store photos on-device
- How to structure file paths (security — path traversal prevention)
- How to sync photos to the cloud
- How to handle cascade deletion (session delete must clean up photos)

The app already stores STT models and LLM models in `getApplicationSupportDirectory()` (Phases 7-8). Photos follow the same pattern.

## Decision

### 1. EXIF Stripping via `image` Package (Pure Dart)

Use the `image` package (pure Dart, no platform dependencies) to process photos. Re-encoding the image via `decodeImage` → `encodeJpg` inherently strips all EXIF metadata (GPS, device info, timestamps). This same processing pass handles resize and compression, avoiding a second pass.

**Rejected alternative**: `native_exif` — platform-dependent (Android/iOS native code), only strips EXIF without resize/compress benefit. Since we re-encode anyway for resize, the EXIF strip is free.

### 2. `InteractiveViewer` for Full-Screen Zoom

Use Flutter's built-in `InteractiveViewer` widget for pinch-to-zoom photo viewing. Combined with `Hero` animation for smooth transition from thumbnail to full-screen.

**Rejected alternative**: `photo_view` package — unnecessary third-party dependency for functionality Flutter provides natively. `InteractiveViewer` handles pan, zoom, and double-tap-to-zoom with less dependency surface.

### 3. Storage in `getApplicationSupportDirectory()/photos/`

Photos stored in the app-private support directory:
- Auto-cleaned on app uninstall (no orphaned files)
- Not visible in device gallery (private journal content)
- Matches the existing pattern for STT models (`stt_models/`) and LLM models (`llm_models/`)
- Not included in device backups by default

### 4. Canonical Path with UUID Validation

File paths follow `photos/{sessionId}/{photoId}.jpg` structure. Both `sessionId` and `photoId` are validated against a UUID regex (`^[a-f0-9\-]+$`) before path construction. This prevents path traversal attacks where malicious IDs like `../../etc/passwd` could escape the photos directory.

### 5. Supabase Storage — Private Bucket `journal-photos`

Cloud sync uploads to a Supabase Storage bucket with path `journals/{userId}/photos/{photoId}.jpg`. Row Level Security ensures users can only access their own photos. Upload is per-photo with sync status tracking (PENDING/SYNCED/FAILED), matching the session sync pattern from ADR-0012.

### 6. Cascade Delete via Optional Parameters

Extend `SessionDao.deleteSessionCascade` with optional `PhotoDao?` and `PhotoService?` parameters. When provided, the cascade deletes photo files from disk, then photo DB records, then messages, then the session — all in a transaction. The parameters are optional for backward compatibility (existing callers without photo support continue to work).

### 7. Photo Processing in Background Isolate

Image decode, resize (max 2048px longest edge), and JPEG re-encode (85% quality) run inside `Isolate.run()` to avoid janking the UI thread. The `image` package's decode/encode operations are CPU-intensive and must not block the main isolate.

### 8. Photos Table Schema

A `Photos` table in drift with:
- `photoId` (PK, client-generated UUID)
- `sessionId` (FK to JournalSessions)
- `messageId` (nullable — links to the JournalMessage that represents this photo)
- `localPath` (relative path within app support directory)
- `cloudUrl` (nullable — set after successful upload)
- `description` (nullable — voice-captured or user-typed caption)
- `timestamp` (when the photo was taken/added)
- `syncStatus` (PENDING/SYNCED/FAILED, default PENDING)
- `width`, `height`, `fileSizeBytes` (nullable — set after processing)
- `createdAt`, `updatedAt`

Additionally, a nullable `photoId` column added to `JournalMessages` to link photo messages to their photo records.

## Alternatives Considered

### Alternative 1: Store Photos in Gallery / External Storage
- **Pros**: User can access photos outside the app, easier sharing
- **Cons**: Journal photos are private content, survives app uninstall (privacy concern), requires WRITE_EXTERNAL_STORAGE permission
- **Reason rejected**: Journal photos should be private and auto-cleaned on uninstall

### Alternative 2: Store Photos as BLOBs in SQLite
- **Pros**: Single database file, atomic backup, no file management
- **Cons**: SQLite performance degrades with large BLOBs, database file size grows unbounded, can't stream/lazy-load
- **Reason rejected**: File-based storage is the standard pattern for images; SQLite BLOBs are inappropriate for media files

### Alternative 3: Cloud-Only Storage (No Local Copy)
- **Pros**: No local disk management, simpler deletion
- **Cons**: Violates offline-first architecture (ADR-0004), photos unavailable without network
- **Reason rejected**: Offline-first is a non-negotiable architectural principle

## Consequences

### Positive
- EXIF stripping is automatic and complete (re-encoding strips all metadata)
- No additional platform-specific dependencies for image viewing
- Storage pattern is consistent with existing model storage
- Path traversal protection prevents file system attacks
- Cascade delete prevents orphaned files
- Background isolate processing keeps UI responsive

### Negative
- Re-encoding for EXIF strip means slight quality loss (JPEG 85% is visually indistinguishable)
- Local photo storage increases app disk usage (mitigated by compression and storage management UI)
- Two-step deletion required (files + DB records) adds complexity

### Neutral
- `image` package is a well-maintained, widely-used pure Dart library
- Photo sync follows the same PENDING/SYNCED/FAILED pattern as session sync
