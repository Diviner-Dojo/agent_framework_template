-- ===========================================================================
-- file: supabase/migrations/002_photos_schema.sql
-- purpose: Cloud-side photos table and storage bucket configuration.
--          Mirrors the local drift Photos table with RLS policies.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor after 001.
--
-- See: ADR-0018 (Photo Storage Architecture)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Photos table
-- ---------------------------------------------------------------------------

CREATE TABLE photos (
    photo_id       UUID PRIMARY KEY,
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    user_id        UUID NOT NULL REFERENCES auth.users(id),
    message_id     UUID REFERENCES journal_messages(message_id) ON DELETE SET NULL,
    local_path     TEXT NOT NULL,
    cloud_url      TEXT,
    description    TEXT,
    timestamp      TIMESTAMPTZ NOT NULL,
    sync_status    TEXT NOT NULL DEFAULT 'SYNCED',
    width          INTEGER,
    height         INTEGER,
    file_size_bytes INTEGER,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Add photo_id column to journal_messages for local cross-reference.
ALTER TABLE journal_messages ADD COLUMN IF NOT EXISTS photo_id UUID;

-- Add PHOTO as a valid input_method.
ALTER TABLE journal_messages DROP CONSTRAINT IF EXISTS journal_messages_input_method_check;
ALTER TABLE journal_messages ADD CONSTRAINT journal_messages_input_method_check
    CHECK (input_method IN ('TEXT', 'VOICE', 'PHOTO'));

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Photos within a session (primary query pattern).
CREATE INDEX idx_photos_session ON photos(session_id, timestamp ASC);

-- Photos by user (supports O(1) RLS policy evaluation).
CREATE INDEX idx_photos_user ON photos(user_id);

-- Unsynced photos for sync logic.
CREATE INDEX idx_photos_sync ON photos(sync_status) WHERE sync_status != 'SYNCED';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE photos ENABLE ROW LEVEL SECURITY;

-- Users can only CRUD their own photos.
CREATE POLICY "Users can CRUD their own photos"
    ON photos FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);

-- ---------------------------------------------------------------------------
-- Storage bucket for photo files
-- ---------------------------------------------------------------------------

-- Create the private bucket for journal photos.
-- Note: Run this via the Supabase Dashboard or storage API if SQL storage
-- management is not available in your Supabase version.
INSERT INTO storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
VALUES (
    'journal-photos',
    'journal-photos',
    false,
    10485760,  -- 10 MB max file size
    ARRAY['image/jpeg', 'image/png', 'image/webp']
)
ON CONFLICT (id) DO NOTHING;

-- Storage RLS: Users can only manage files in their own directory.
CREATE POLICY "Users can upload their own photos"
    ON storage.objects FOR INSERT
    WITH CHECK (
        bucket_id = 'journal-photos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "Users can read their own photos"
    ON storage.objects FOR SELECT
    USING (
        bucket_id = 'journal-photos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "Users can delete their own photos"
    ON storage.objects FOR DELETE
    USING (
        bucket_id = 'journal-photos'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );
