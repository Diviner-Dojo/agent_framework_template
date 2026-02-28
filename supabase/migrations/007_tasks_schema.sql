-- ===========================================================================
-- file: supabase/migrations/007_tasks_schema.sql
-- purpose: Cloud-side tasks table mirroring the local drift Tasks table.
--          Provides cloud backup for task records.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor after 006.
--
-- See: Phase 13 plan (Google Tasks + Personal Assistant)
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- Tasks table
-- ---------------------------------------------------------------------------

CREATE TABLE tasks (
    task_id              UUID PRIMARY KEY,
    session_id           UUID REFERENCES journal_sessions(session_id) ON DELETE SET NULL,
    user_id              UUID NOT NULL REFERENCES auth.users(id),
    title                TEXT NOT NULL,
    notes                TEXT,
    due_date             TIMESTAMPTZ,
    google_task_id       TEXT,
    google_task_list_id  TEXT,
    status               TEXT NOT NULL DEFAULT 'PENDING_CREATE'
        CHECK (status IN ('PENDING_CREATE', 'ACTIVE', 'COMPLETED', 'FAILED')),
    sync_status          TEXT NOT NULL DEFAULT 'SYNCED',
    raw_user_message     TEXT,
    completed_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Indexes
-- ---------------------------------------------------------------------------

-- Tasks by user (supports O(1) RLS policy evaluation).
CREATE INDEX idx_tasks_user ON tasks(user_id);

-- Active tasks lookup.
CREATE INDEX idx_tasks_status ON tasks(status)
    WHERE status IN ('ACTIVE', 'PENDING_CREATE');

-- Due date queries.
CREATE INDEX idx_tasks_due_date ON tasks(due_date)
    WHERE due_date IS NOT NULL;

-- Pending sync.
CREATE INDEX idx_tasks_sync ON tasks(sync_status)
    WHERE sync_status != 'SYNCED';

-- ---------------------------------------------------------------------------
-- Row Level Security
-- ---------------------------------------------------------------------------

ALTER TABLE tasks ENABLE ROW LEVEL SECURITY;

-- Users can only CRUD their own tasks.
CREATE POLICY "Users can CRUD their own tasks"
    ON tasks FOR ALL
    USING (auth.uid() = user_id)
    WITH CHECK (auth.uid() = user_id);
