-- ===========================================================================
-- file: supabase/migrations/005_session_columns.sql
-- purpose: Add missing columns to journal_sessions that were added to the
--          local drift schema but never propagated to Supabase.
--
-- Columns:
--   - is_resumed:    Whether the session was resumed (ADR resume support)
--   - resume_count:  Number of times the session was resumed
--   - location_name: Human-readable location name (ADR-0019 §3)
--                    Coordinates intentionally excluded from cloud.
--
-- Usage: Run this SQL in the Supabase Dashboard SQL editor after 004.
-- ===========================================================================

ALTER TABLE journal_sessions
    ADD COLUMN IF NOT EXISTS is_resumed    BOOLEAN DEFAULT false,
    ADD COLUMN IF NOT EXISTS resume_count  INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS location_name TEXT;
