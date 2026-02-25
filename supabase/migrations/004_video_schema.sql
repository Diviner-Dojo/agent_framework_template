-- ===========================================================================
-- file: supabase/migrations/004_video_schema.sql
-- purpose: Cloud-side videos table and storage bucket configuration.
--          Mirrors the local drift Videos table with RLS policies.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor after 003.
--
-- Note: Video sync is feature-flagged OFF at launch (ADR-0021 §3).
--       This migration is written now for future enablement once metadata
--       stripping is validated in production.
--
-- See: ADR-0021 (Video Capture Architecture)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Videos table
-- ---------------------------------------------------------------------------

CREATE TABLE videos (
    video_id         UUID PRIMARY KEY,
    session_id       UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES auth.users(id),
    message_id       UUID REFERENCES journal_messages(message_id) ON DELETE SET NULL,
    local_path       TEXT NOT NULL,
    thumbnail_path   TEXT NOT NULL,
    cloud_url        TEXT,
    description      TEXT,
    duration_seconds INTEGER NOT NULL,
    timestamp        TIMESTAMPTZ NOT NULL,
    sync_status      TEXT NOT NULL DEFAULT 'PENDING',
    width            INTEGER,
    height           INTEGER,
    file_size_bytes  INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add video_id column to journal_messages for local cross-reference.
ALTER TABLE journal_messages ADD COLUMN IF NOT EXISTS video_id UUID;

-- Update input_method constraint to include VIDEO.
ALTER TABLE journal_messages DROP CONSTRAINT IF EXISTS journal_messages_input_method_check;
ALTER TABLE journal_messages ADD CONSTRAINT journal_messages_input_method_check
    CHECK (input_method IN ('TEXT', 'VOICE', 'PHOTO', 'VIDEO'));

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Videos within a session (primary query pattern).
CREATE INDEX idx_videos_session ON videos(session_id, timestamp ASC);

-- Videos by user (supports O(1) RLS policy evaluation).
CREATE INDEX idx_videos_user ON videos(user_id);

-- Unsynced videos for sync logic.
CREATE INDEX idx_videos_sync ON videos(sync_status) WHERE sync_status != 'SYNCED';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE videos ENABLE ROW LEVEL SECURITY;

-- Users can only CRUD their own videos.
CREATE POLICY "Users can CRUD their own videos"
    ON videos FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Storage bucket for video files (deferred — feature-flagged off at launch)
-- ---------------------------------------------------------------------------

-- Create the private bucket for journal videos.
-- 500 MB limit per file, video MIME types only.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'journal-videos',
    'journal-videos',
    false,
    524288000,  -- 500 MB max file size
    ARRAY['video/mp4', 'video/quicktime', 'video/x-matroska', 'video/webm']
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Users can only manage files in their own directory.
CREATE POLICY "Users can upload their own videos"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'journal-videos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "Users can read their own videos"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'journal-videos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "Users can delete their own videos"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'journal-videos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );
