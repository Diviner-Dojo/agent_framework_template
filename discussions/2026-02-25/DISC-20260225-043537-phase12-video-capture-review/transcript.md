---
discussion_id: DISC-20260225-043537-phase12-video-capture-review
started: 2026-02-25T04:42:16.096641+00:00
ended: 2026-02-25T04:43:04.548236+00:00
agents: [architecture-consultant, facilitator, independent-perspective, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260225-043537-phase12-video-capture-review

## Turn 1 — qa-specialist (proposal)
*2026-02-25T04:42:16.096641+00:00 | confidence: 0.87*
*tags: review, qa, phase12*

Verdict: APPROVE-WITH-CHANGES (confidence 0.87). 9 findings across Phase 12 video capture code.

HIGH SEVERITY:
1. deleteVideoFile() boundary check has no test coverage — the containment guard that prevents path-traversal deletion is untested. Risk: regression could silently disable the safety check.
2. attachVideo() in SessionNotifier is completely untested — this is the primary integration point wiring VideoService + VideoDao + MessageDao together. No test verifies the happy path, error handling, or state updates.

MEDIUM SEVERITY:
3. calculateTotalSize() in video_providers_test.dart is untested — the VideoStorageInfo computation (sum of fileSizeBytes, formatting, warning threshold) has zero coverage.
4. VideoPlayerScreen has no widget tests — controller lifecycle (init, dispose, error state, play/pause toggle) is unverified.
5. ChatBubble video branch untested — the new videoThumbnailPath/videoDuration/onVideoTap parameters and thumbnail rendering with play overlay have no widget test.
6. Weak path assertions in canonicalVideoPath tests — tests check path.contains() rather than exact expected structure, allowing false positives.

LOW SEVERITY:
7. getVideosToSync missing all-synced edge case test.
8. deleteSessionVideos UUID guard untested.
9. _makeRelativePath untested — private helper in SessionNotifier that strips base directory prefix.

---

## Turn 2 — security-specialist (proposal)
*2026-02-25T04:42:26.372290+00:00 | confidence: 0.88*
*tags: review, security, phase12*

Verdict: APPROVE-WITH-CHANGES (confidence 0.88). 5 findings across Phase 12 video capture code.

MEDIUM SEVERITY:
1. Relative paths passed to VideoPlayerController without resolution — localPath and thumbnailPath are stored as relative paths in the DB (e.g., videos/sessionId/videoId.mp4) but UI code passes them directly to File() and Image.file(). VideoPlayerController.file(File(relativePath)) will fail on all devices because the working directory is not the app support directory. This affects chat_bubble.dart (thumbnail) and video_player_widget.dart (playback). Fix: resolve paths against applicationSupportDirectory before passing to File().
2. Stream-level GPS metadata on iOS .mov files survives -map_metadata -1 — FFmpeg's -map_metadata -1 strips container-level metadata but iOS QuickTime .mov files embed GPS coordinates at the stream/track level. A determined adversary could extract location data from synced videos. Mitigation: add -map_metadata:s -1 flag or document as known limitation in ADR-0021.

LOW SEVERITY:
3. Missing UPDATE policy on storage.objects in Supabase migration 004 — INSERT, SELECT, DELETE policies exist but no UPDATE policy. If sync retry needs to overwrite a partially uploaded video, it will be blocked by RLS.
4. Case-insensitive filesystem edge case in deleteVideoFile — the canonical path containment check uses string startsWith which is case-sensitive, but macOS/Windows filesystems are case-insensitive. An attacker could craft a path with different casing to bypass the check. Low risk because paths are UUID-generated.
5. _makeRelativePath fallback returns absolute path — if the path doesn't start with the base directory, it returns the original absolute path, which gets stored in DB. This creates inconsistent path formats in the database.

---

## Turn 3 — architecture-consultant (proposal)
*2026-02-25T04:42:38.197168+00:00 | confidence: 0.88*
*tags: review, architecture, phase12*

Verdict: APPROVE-WITH-CHANGES (confidence 0.88). 7 findings across Phase 12 video capture code.

MEDIUM SEVERITY:
1. _getBaseDirPath() and _makeRelativePath() in SessionNotifier belong in VideoService — these path resolution helpers are domain logic (video file storage conventions) placed in the state management layer. PhotoService handles its own paths; VideoService should too. This creates coupling between SessionNotifier and the storage directory structure. Fix: move to VideoService and expose as public methods.
2. ProcessedVideo.durationSeconds hardcoded to 0 in VideoService.processAndSave(), and _handleVideoCapture in journal_session_screen.dart never extracts or passes duration to attachVideo(). The duration badge in ChatBubble will show 0:00 for every video, making the UI feature meaningless. Fix: extract duration from video metadata via FFmpegKit probe or video_player initialization.
3. Asymmetric photo/video indexing in journal_session_screen.dart — photos use a Map<String, Photo> keyed by messageId but videos use a Map<String, Video> also keyed by messageId. The ChatBubble rendering uses dynamic casts (as Photo, as Video) to distinguish types. This is fragile and will break if a message has both photo and video. Fix: use a sealed MediaAttachment type or separate named parameters.

LOW SEVERITY:
4. Photo path generation uses raw Uuid().v4() while video uses generateUuid() utility — inconsistent UUID generation across the two media types.
5. deleteVideoFile receives relative paths from DB but the containment check expects absolute paths — the method will always fail the startsWith check for DB-sourced paths.
6. Videos table thumbnailPath is non-nullable — correct design decision (thumbnails always generated on capture) but noted for completeness.
7. Video constants (maxDurationSeconds, maxFileSizeBytes, etc.) are public top-level — should be private or scoped to VideoService since they are implementation details.

---

## Turn 4 — independent-perspective (proposal)
*2026-02-25T04:42:47.751302+00:00 | confidence: 0.82*
*tags: review, independent, phase12, blocking*

Verdict: REQUEST-CHANGES (confidence 0.82). 2 blocking findings, 3 non-blocking.

BLOCKING:
1. Relative paths stored in DB passed directly to File() in UI — the video feature will silently fail for ALL users on ALL devices. localPath is stored as a relative path (e.g., videos/{sessionId}/{videoId}.mp4) in the Videos table, but chat_bubble.dart passes it directly to Image.file(File(thumbnailPath)) and video_player_widget.dart receives it as-is for VideoPlayerController.file(File(videoPath)). File() with a relative path resolves against the process working directory, NOT the app support directory. Thumbnails will show broken images, playback will show error state. This is not an edge case — it affects 100% of captured videos. All 3 other specialists also flagged this issue. Fix: resolve all DB paths against applicationSupportDirectory before passing to File constructors.

2. SessionDetailScreen does not display videos — the read-only session detail view (shown when viewing past journal sessions) has no video rendering logic. Past sessions with attached videos will show message text like [Video] as plain text with no thumbnail or playback capability. The feature is half-integrated: capture works but review does not.

NON-BLOCKING:
3. durationSeconds permanently 0 — ProcessedVideo always returns 0, _handleVideoCapture never passes duration. Every video shows 0:00 duration badge. Cosmetic but misleading.
4. deleteVideoFile broken for relative paths from DB — containment check compares relative path against absolute base directory, always fails. Dead code path.
5. Thumbnail generation failure silently discards the entire video — if video_thumbnail throws, processAndSave catches, deletes the saved video file, and rethrows. User loses their recording with no recovery option. Should save video without thumbnail as fallback.

---

## Turn 5 — facilitator (synthesis)
*2026-02-25T04:43:04.548236+00:00 | confidence: 0.86*
*tags: review, synthesis, blocking:2, advisory:10*

Phase 12 Video Capture Review Synthesis — Verdict: REQUEST-CHANGES

4 specialists dispatched (qa-specialist, security-specialist, architecture-consultant, independent-perspective). All returned findings. Consensus on 2 blocking issues, 10 advisory items.

BLOCKING (2 — must fix before merge):
B1. Relative path resolution failure (all 4 specialists flagged): localPath and thumbnailPath stored as relative paths in Videos table but passed directly to File() in chat_bubble.dart and video_player_widget.dart. File(relativePath) resolves against process CWD, not app support dir. Result: 100% of video thumbnails show broken images, 100% of video playback fails. Fix: resolve paths against applicationSupportDirectory before constructing File objects.
B2. SessionDetailScreen missing video display (independent-perspective): Past sessions with videos show [Video] as plain text — no thumbnail, no playback. Capture works but review of past sessions does not.

ADVISORY (10 — should fix, do not block merge):
A1. durationSeconds permanently 0 (architecture-consultant, independent-perspective): ProcessedVideo.durationSeconds hardcoded to 0, never extracted from video metadata. Duration badge shows 0:00 for all videos.
A2. deleteVideoFile broken for relative paths (architecture-consultant, independent-perspective, security-specialist): Containment check compares relative DB path against absolute base dir — always fails.
A3. _getBaseDirPath/_makeRelativePath in wrong layer (architecture-consultant): Path resolution helpers are in SessionNotifier but should be in VideoService per PhotoService pattern.
A4. Stream-level GPS metadata survives -map_metadata -1 on iOS .mov (security-specialist): Document in ADR-0021 or add -map_metadata:s -1 flag.
A5. Missing UPDATE storage.objects RLS policy in 004_video_schema.sql (security-specialist).
A6. attachVideo() untested (qa-specialist): Primary integration point has zero test coverage.
A7. deleteVideoFile() boundary check untested (qa-specialist): Security-critical containment guard has no tests.
A8. VideoPlayerScreen has no widget tests (qa-specialist).
A9. ChatBubble video branch untested (qa-specialist).
A10. Thumbnail failure silently discards video (independent-perspective): User loses recording with no recovery.

Strengths: FFmpegKit.executeWithArguments() correctly prevents command injection. UUID regex path validation is sound. MediaSource enum cleanly extends photo capture. STT pause/resume during recording handles audio focus. Drift schema and DAO follow established patterns faithfully. Provider structure mirrors photo_providers correctly.

---
