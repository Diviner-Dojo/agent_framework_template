-- ===========================================================================
-- file: supabase/migrations/001_initial_schema.sql
-- purpose: Cloud-side tables that mirror the local drift schema.
--          Includes RLS policies so each user can only access their own data.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor.
--
-- See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
-- ===========================================================================

-- Enable pgvector extension for future RAG / semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable full-text search via trigram matching
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ---------------------------------------------------------------------------
-- Tables
-- ---------------------------------------------------------------------------

CREATE TABLE journal_sessions (
    session_id     UUID PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES auth.users(id),
    start_time     TIMESTAMPTZ NOT NULL,
    end_time       TIMESTAMPTZ,
    timezone       TEXT NOT NULL DEFAULT 'UTC',
    summary        TEXT,
    mood_tags      JSONB DEFAULT '[]'::jsonb,
    people         JSONB DEFAULT '[]'::jsonb,
    topic_tags     JSONB DEFAULT '[]'::jsonb,
    sync_status    TEXT NOT NULL DEFAULT 'SYNCED',  -- cloud copy is always "synced"
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE journal_messages (
    message_id     UUID PRIMARY KEY,
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    role           TEXT NOT NULL CHECK (role IN ('USER', 'ASSISTANT', 'SYSTEM')),
    content        TEXT NOT NULL,
    timestamp      TIMESTAMPTZ NOT NULL,
    input_method   TEXT NOT NULL DEFAULT 'TEXT' CHECK (input_method IN ('TEXT', 'VOICE')),
    entities_json  JSONB,
    sentiment      DOUBLE PRECISION,
    embedding_id   UUID,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Future: embeddings table for RAG
CREATE TABLE entry_embeddings (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    chunk_text     TEXT NOT NULL,
    embedding      vector(1536),  -- dimensions match the embedding model used
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Primary query pattern: user's sessions by date
CREATE INDEX idx_sessions_user_date ON journal_sessions(user_id, start_time DESC);

-- Messages within a session, ordered chronologically
CREATE INDEX idx_messages_session ON journal_messages(session_id, timestamp ASC);

-- Partial index for unsynced sessions (used by sync logic)
CREATE INDEX idx_sessions_sync ON journal_sessions(sync_status) WHERE sync_status != 'SYNCED';

-- Full-text search on message content via trigram
CREATE INDEX idx_messages_content_trgm ON journal_messages USING gin(content gin_trgm_ops);

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE journal_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE journal_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE entry_embeddings ENABLE ROW LEVEL SECURITY;

-- Users can only CRUD their own sessions
CREATE POLICY "Users can CRUD their own sessions"
    ON journal_sessions FOR ALL
    USING (auth.uid() = user_id);

-- Users can only CRUD messages belonging to their own sessions
CREATE POLICY "Users can CRUD messages in their own sessions"
    ON journal_messages FOR ALL
    USING (
        session_id IN (
            SELECT session_id FROM journal_sessions WHERE user_id = auth.uid()
        )
    );

-- Users can only CRUD embeddings for their own sessions
CREATE POLICY "Users can CRUD embeddings for their own sessions"
    ON entry_embeddings FOR ALL
    USING (
        session_id IN (
            SELECT session_id FROM journal_sessions WHERE user_id = auth.uid()
        )
    );
