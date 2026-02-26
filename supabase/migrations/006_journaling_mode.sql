-- Migration: Add journaling_mode column to journal_sessions
-- Enhancement: E14 (Journaling Mode Templates — ADR-0025)
-- Date: 2026-02-26
--
-- Stores the activity-scoped journaling mode for each session.
-- Values: 'free', 'gratitude', 'dream_analysis', 'mood_check_in'
-- NULL means free mode (backward compatible with pre-E14 sessions).

ALTER TABLE journal_sessions
  ADD COLUMN IF NOT EXISTS journaling_mode TEXT;
