---
adr_id: ADR-0024
title: "Raw Audio Preservation for STT Recovery"
status: accepted
date: 2026-02-26
decision_makers: [architect, facilitator]
discussion_id: null
supersedes: null
risk_level: medium
confidence: 0.85
tags: [audio, stt, resilience, storage]
---

## Context

The current voice pipeline (ADR-0015) streams PCM16 audio directly to the sherpa_onnx recognizer without preserving the raw audio. If STT fails mid-session (model crash, corruption, OOM), the audio is lost permanently — the user's spoken words cannot be recovered.

For a journaling app where user content is the primary artifact, this data loss is unacceptable. We need a "black box" recording that survives STT failures.

Constraints:
- Audio must be saved before/during transcription, not after (defeats the purpose)
- Must not degrade STT latency (the tee must be non-blocking)
- Storage format must be simple and recoverable (no proprietary containers)
- Cloud sync of audio is impractical on Supabase free tier (25MB/session at 16kHz PCM16)

## Decision

Save raw audio to a WAV file in the app documents directory during transcription using a tee pattern on the PCM16 byte stream.

### Storage
- Location: `{appDocumentsDir}/audio/{sessionId}.wav`
- Format: WAV (RIFF/PCM16, 16kHz, mono) — identical to STT input, no transcoding
- Lifecycle: file created at session start, WAV header finalized at session end
- Linked via nullable `audio_file_path` column on `journal_sessions` table

### AudioFileService API
- `startRecording(sessionId)` — creates WAV file, writes 44-byte header placeholder
- `writeChunk(List<int> pcm16Bytes)` — appends raw PCM16 data (non-blocking)
- `stopRecording()` — patches WAV header with final data size, closes file, returns path
- `deleteRecording(sessionId)` — cleanup helper for pruning

### Integration
- `SpeechRecognitionService._processAudioChunk()` tees PCM16 bytes to AudioFileService before Float32 conversion
- The tee is optional (nullable AudioFileService parameter) — STT works without it

### Cleanup Policy
- Audio files for sessions older than 30 days can be pruned (configurable, not implemented in this sprint)
- No automatic deletion — user controls retention

## Alternatives Considered

### Alternative 1: Opus/AAC compressed audio
- **Pros**: ~10x smaller files, standard playback support
- **Cons**: Requires transcoding during recording (adds latency), more complex header
- **Reason rejected**: Transcoding adds CPU load during the latency-sensitive STT pipeline. WAV is zero-cost to write and matches the STT input format exactly.

### Alternative 2: Cloud storage of audio
- **Pros**: Backup and cross-device access
- **Cons**: 25MB+ per 10-minute session at 16kHz PCM16; exceeds Supabase free tier limits rapidly
- **Reason rejected**: Cost-prohibitive for free tier. Audio stays local-only. Can revisit with compression + paid tier.

### Alternative 3: Record only on STT failure
- **Pros**: Saves storage for successful sessions
- **Cons**: Cannot predict STT failure in advance; by the time failure is detected, audio is already lost
- **Reason rejected**: Defeats the purpose — the whole point is pre-failure preservation.

## Consequences

### Positive
- User audio is never permanently lost due to STT failure
- WAV format is universally readable — manual recovery is trivial
- Zero transcoding overhead (PCM16 written as-is)
- Tee pattern is non-intrusive to existing STT pipeline

### Negative
- Storage cost: ~1.9MB/minute at 16kHz PCM16 mono (~19MB for a 10-minute session)
- Requires schema migration (v7) for `audio_file_path` column
- Cleanup policy needs implementation in a future sprint

### Neutral
- Audio files are not synced to cloud — local-only storage
- Schema migration is additive (nullable column) — no data loss risk
