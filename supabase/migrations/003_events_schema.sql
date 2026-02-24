-- ===========================================================================
-- file: supabase/migrations/003_events_schema.sql
-- purpose: Cloud-side calendar_events table mirroring the local drift
--          CalendarEvents table. Provides cloud backup for event records.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor after 002.
--
-- See: ADR-0020 (Google Calendar Integration)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Calendar events table
-- ---------------------------------------------------------------------------

CREATE TABLE calendar_events (
    event_id         UUID PRIMARY KEY,
    session_id       UUID NOT NULL REFERENCES journal_sessions(session_id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES auth.users(id),
    title            TEXT NOT NULL,
    start_time       TIMESTAMPTZ NOT NULL,
    end_time         TIMESTAMPTZ,
    google_event_id  TEXT,
    status           TEXT NOT NULL DEFAULT 'PENDING_CREATE'
        CHECK (status IN ('PENDING_CREATE', 'CONFIRMED', 'FAILED', 'CANCELLED')),
    sync_status      TEXT NOT NULL DEFAULT 'SYNCED',
    raw_user_message TEXT NOT NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Events within a session (primary query pattern).
CREATE INDEX idx_calendar_events_session ON calendar_events(session_id, created_at ASC);

-- Events by user (supports O(1) RLS policy evaluation).
CREATE INDEX idx_calendar_events_user ON calendar_events(user_id);

-- Pending events for sync logic.
CREATE INDEX idx_calendar_events_sync ON calendar_events(sync_status)
    WHERE sync_status != 'SYNCED';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE calendar_events ENABLE ROW LEVEL SECURITY;

-- Users can only CRUD their own calendar events.
CREATE POLICY "Users can CRUD their own calendar events"
    ON calendar_events FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
