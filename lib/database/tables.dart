// coverage:ignore-file — drift table schema definitions, no executable logic.
// ===========================================================================
// file: lib/database/tables.dart
// purpose: drift table definitions for the local SQLite database.
//          These mirror the Supabase PostgreSQL schema for sync compatibility.
//
// Why drift tables?
//   drift uses these Dart class definitions to:
//   1. Generate the actual SQLite CREATE TABLE statements
//   2. Generate type-safe Dart data classes for each row
//   3. Generate query builders for type-safe CRUD operations
//
// After changing these definitions, run:
//   dart run build_runner build --delete-conflicting-outputs
// ===========================================================================

import 'package:drift/drift.dart';

/// Represents a single journaling session (one conversation).
/// A user triggers the assistant → conversation happens → session closes.
///
/// Think of this like a SQL table definition:
///   CREATE TABLE journal_sessions (
///     session_id TEXT PRIMARY KEY,
///     start_time TEXT NOT NULL,
///     ...
///   );
class JournalSessions extends Table {
  // Client-generated UUID — no server round-trip needed for creation.
  // This is the primary key, set by the app when creating a new session.
  TextColumn get sessionId => text()();

  // When the session started and ended (stored as UTC ISO 8601 text).
  // start_time is always set on creation; end_time is set when session closes.
  DateTimeColumn get startTime => dateTime()();
  DateTimeColumn get endTime => dateTime().nullable()();

  // IANA timezone string (e.g., "America/Denver") for display purposes.
  // Stored so we can show the user what timezone they were in when journaling.
  TextColumn get timezone => text().withDefault(const Constant('UTC'))();

  // AI-generated summary of the session (created on session end).
  // In Phase 1, this is a simple first-sentence extraction.
  // In Phase 3+, this will be Claude-generated.
  TextColumn get summary => text().nullable()();

  // AI-inferred mood tag(s), stored as JSON array string: '["happy","tired"]'
  // Nullable in Phase 1 (no AI tagging). Populated in Phase 3.
  TextColumn get moodTags => text().nullable()();

  // AI-extracted people mentioned, stored as JSON array string: '["Mike","Sarah"]'
  TextColumn get people => text().nullable()();

  // AI-extracted topic/theme tags, stored as JSON array string
  TextColumn get topicTags => text().nullable()();

  // Sync tracking — tracks whether this session has been uploaded to Supabase.
  // Values: 'PENDING' | 'SYNCED' | 'FAILED'
  // In Phase 1, everything stays PENDING (no sync implemented yet).
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();
  DateTimeColumn get lastSyncAttempt => dateTime().nullable()();

  // Whether this session was resumed after being initially ended.
  // Set to true by SessionDao.resumeSession(). Default false for new sessions.
  BoolColumn get isResumed => boolean().withDefault(const Constant(false))();

  // How many times this session has been resumed.
  // Incremented by SessionDao.resumeSession() each time.
  IntColumn get resumeCount => integer().withDefault(const Constant(0))();

  // Path to the raw audio WAV file for this session (E7 — ADR-0024).
  // Stored as an absolute path to the app documents directory.
  // Null when no audio was recorded (e.g., text-only sessions).
  TextColumn get audioFilePath => text().nullable()();

  // Journaling mode for this session (E14 — ADR-0025).
  // Values: 'free', 'gratitude', 'dream_analysis', 'mood_check_in'.
  // Null means free mode (backward compatible with pre-E14 sessions).
  TextColumn get journalingMode => text().nullable()();

  // Location data (Phase 10 — ADR-0019).
  // Coordinates are reduced to 2 decimal places (~1.1km) before storage
  // as a deliberate privacy tradeoff. Only locationName syncs to cloud;
  // raw coordinates remain local-only.
  RealColumn get latitude => real().nullable()();
  RealColumn get longitude => real().nullable()();
  RealColumn get locationAccuracy => real().nullable()();
  TextColumn get locationName => text().nullable()();

  // Standard timestamps — createdAt defaults to current time,
  // updatedAt should be set manually whenever the record is modified.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  // Tell drift which column(s) form the primary key.
  // Using a Set rather than an auto-increment integer because
  // UUIDs are generated client-side for offline-first compatibility.
  @override
  Set<Column> get primaryKey => {sessionId};
}

/// Individual messages within a session (the conversation transcript).
/// Each message is either from the USER, the ASSISTANT, or the SYSTEM.
///
/// Messages are ordered by timestamp within a session to reconstruct
/// the conversation in the correct order.
class JournalMessages extends Table {
  // Client-generated UUID for this message
  TextColumn get messageId => text()();

  // Foreign key to JournalSessions — links this message to its session.
  // The .references() call tells drift about the relationship (for documentation
  // and potential future foreign key enforcement).
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  // Who sent this message.
  // Values: 'USER' | 'ASSISTANT' | 'SYSTEM'
  // USER = typed/spoken by the human
  // ASSISTANT = generated by the journaling agent
  // SYSTEM = internal messages (e.g., session start/end markers)
  TextColumn get role => text()();

  // The actual message content — the text of what was said
  TextColumn get content => text()();

  // When this message was sent (UTC).
  // Used for ordering messages within a session.
  DateTimeColumn get timestamp => dateTime()();

  // How the user entered this message (for analytics/UX decisions).
  // Values: 'TEXT' | 'VOICE'
  // Phase 1 only uses TEXT. Phase 2 adds VOICE via speech_to_text.
  TextColumn get inputMethod => text().withDefault(const Constant('TEXT'))();

  // === Future fields (nullable, populated by AI processing in Phase 3+) ===

  // Named entities extracted from this message (JSON)
  TextColumn get entitiesJson => text().nullable()();

  // Sentiment score (-1.0 to 1.0, nullable)
  RealColumn get sentiment => real().nullable()();

  // Reference to an embedding vector (stored separately or in Supabase pgvector)
  TextColumn get embeddingId => text().nullable()();

  // Reference to a photo attached to this message (Phase 9 — ADR-0018).
  // When set, this message represents a photo entry in the conversation.
  TextColumn get photoId => text().nullable()();

  // Reference to a video attached to this message (Phase 12 — ADR-0021).
  // When set, this message represents a video entry in the conversation.
  TextColumn get videoId => text().nullable()();

  @override
  Set<Column> get primaryKey => {messageId};
}

/// Calendar events extracted from conversation (Phase 11 — ADR-0020).
///
/// Each event is associated with a session and tracks both its lifecycle
/// state (pending/confirmed/failed/cancelled) and cloud sync state
/// (pending/synced/failed) as independent state machines.
class CalendarEvents extends Table {
  /// Client-generated UUID — primary key.
  TextColumn get eventId => text()();

  /// Foreign key to JournalSessions — links this event to its session.
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  /// User ID for RLS and cloud sync.
  TextColumn get userId => text().nullable()();

  /// Event title extracted by the AI.
  TextColumn get title => text()();

  /// Event start time (ISO 8601 UTC).
  DateTimeColumn get startTime => dateTime()();

  /// Event end time (nullable — reminders may not have an end time).
  DateTimeColumn get endTime => dateTime().nullable()();

  /// Google Calendar event ID — set after successful creation.
  TextColumn get googleEventId => text().nullable()();

  /// Event lifecycle state (ADR-0020 §5).
  /// Values: 'PENDING_CREATE' | 'CONFIRMED' | 'FAILED' | 'CANCELLED'
  TextColumn get status =>
      text().withDefault(const Constant('PENDING_CREATE'))();

  /// Cloud sync state — independent from lifecycle status (ADR-0020 §5).
  /// Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();

  /// The raw user message that triggered this event extraction.
  TextColumn get rawUserMessage => text().nullable()();

  /// Standard timestamps.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {eventId};
}

/// Photos attached to journal sessions (Phase 9 — ADR-0018).
///
/// Each photo is associated with a session and optionally linked to a
/// message via [messageId]. Photos are stored on-device as JPEG files
/// with EXIF metadata stripped for privacy. Cloud sync uploads to
/// Supabase Storage.
class Photos extends Table {
  // Client-generated UUID — primary key.
  TextColumn get photoId => text()();

  // Foreign key to JournalSessions — links this photo to its session.
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  // Optional link to the JournalMessage that represents this photo.
  // A photo message has role=USER, inputMethod=PHOTO, content="[Photo]".
  TextColumn get messageId => text().nullable()();

  // Relative path within app support directory (e.g., "photos/uuid/uuid.jpg").
  TextColumn get localPath => text()();

  // Supabase Storage URL — set after successful upload.
  TextColumn get cloudUrl => text().nullable()();

  // User-provided or voice-captured description of the photo.
  TextColumn get description => text().nullable()();

  // When the photo was taken or added to the session.
  DateTimeColumn get timestamp => dateTime()();

  // Sync tracking — matches session sync pattern (ADR-0012).
  // Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();

  // Image dimensions after processing (nullable until processing completes).
  IntColumn get width => integer().nullable()();
  IntColumn get height => integer().nullable()();

  // File size in bytes after processing.
  IntColumn get fileSizeBytes => integer().nullable()();

  // Standard timestamps.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {photoId};
}

/// Videos attached to journal sessions (Phase 12 — ADR-0021).
///
/// Each video is associated with a session and optionally linked to a
/// message via [messageId]. Videos are stored on-device as MP4 files
/// with container metadata stripped for privacy. Cloud sync is
/// feature-flagged off at launch (local-only).
class Videos extends Table {
  // Client-generated UUID — primary key.
  TextColumn get videoId => text()();

  // Foreign key to JournalSessions — links this video to its session.
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  // Optional link to the JournalMessage that represents this video.
  TextColumn get messageId => text().nullable()();

  // Relative path within app support directory (e.g., "videos/uuid/uuid.mp4").
  TextColumn get localPath => text()();

  // Relative path to thumbnail JPEG (e.g., "videos/uuid/uuid_thumb.jpg").
  TextColumn get thumbnailPath => text()();

  // Supabase Storage URL — set after successful upload (deferred).
  TextColumn get cloudUrl => text().nullable()();

  // User-provided or voice-captured description of the video.
  TextColumn get description => text().nullable()();

  // Recording duration in seconds.
  IntColumn get durationSeconds => integer()();

  // When the video was recorded or added to the session.
  DateTimeColumn get timestamp => dateTime()();

  // Sync tracking — matches session sync pattern (ADR-0012).
  // Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();

  // Video dimensions after processing (nullable until processing completes).
  IntColumn get width => integer().nullable()();
  IntColumn get height => integer().nullable()();

  // File size in bytes after processing.
  IntColumn get fileSizeBytes => integer().nullable()();

  // Standard timestamps.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {videoId};
}

// ===========================================================================
// Pulse Check-In tables (ADHD Roadmap Phase 1 — ADR-0032)
// ===========================================================================

/// Questionnaire templates — instrument definitions (WHO-5, PHQ-2, custom, etc.).
///
/// Each template holds the scale configuration and metadata. System defaults
/// ([isSystemDefault] = true) cannot be deleted via the DAO — only deactivated.
/// User-defined templates ([isSystemDefault] = false) can be deleted.
///
/// See: ADR-0032 (Pulse Check-In schema), SPEC-20260302-ADHD Phase 1 Task 1.
class QuestionnaireTemplates extends Table {
  /// Auto-increment primary key.
  IntColumn get id => integer().autoIncrement()();

  /// Short display name (e.g., "Pulse Check-In").
  TextColumn get name => text()();

  /// Optional longer description shown in settings.
  TextColumn get description => text().nullable()();

  /// Instrument code identifying the source instrument (e.g., 'who-5', 'phq-4',
  /// 'custom'). Used for license tracking — see ADR-0032 §License Decision.
  /// System default uses 'custom' (mixed instruments — see SPEC §Default Question Set).
  TextColumn get instrumentCode =>
      text().withDefault(const Constant('custom'))();

  /// Instrument version string (e.g., '1998', '2012', '1.0.0').
  /// Used for license tracking and reproducibility of historical scores.
  TextColumn get version => text().withDefault(const Constant('1.0.0'))();

  /// License information for the source instrument.
  /// WHO-5: 'CC BY-NC-SA 3.0 — Psychiatric Centre North Zealand'.
  /// Null for public domain or custom instruments.
  /// INVARIANT: Must be populated for any copyrighted instrument before shipping
  /// to users. See ADR-0032 §License Decision.
  TextColumn get licenseInfo => text().nullable()();

  /// True for the built-in default template. System defaults cannot be deleted.
  BoolColumn get isSystemDefault =>
      boolean().withDefault(const Constant(false))();

  /// Whether this template is available for selection. Deactivated templates
  /// are hidden from the mode picker but retained for historical response data.
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();

  /// Minimum scale value (e.g., 1 for a 1-10 scale, 0 for a 0-10 scale).
  IntColumn get scaleMin => integer().withDefault(const Constant(1))();

  /// Maximum scale value (e.g., 10, 100).
  IntColumn get scaleMax => integer().withDefault(const Constant(10))();

  /// Display order in template list (ascending).
  IntColumn get sortOrder => integer().withDefault(const Constant(0))();

  /// Standard timestamps.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();
}

/// Individual questionnaire items (questions) belonging to a template.
///
/// Each item has a question text, endpoint labels, and an optional reverse-
/// scoring flag. Reverse-scored items use `scaleMax + scaleMin - rawValue`
/// when computing the composite score.
///
/// See: ADR-0032 §Composite Score Formula.
class QuestionnaireItems extends Table {
  /// Auto-increment primary key.
  IntColumn get id => integer().autoIncrement()();

  /// Foreign key to [QuestionnaireTemplates].
  IntColumn get templateId =>
      integer().references(QuestionnaireTemplates, #id)();

  /// The question text displayed to the user.
  TextColumn get questionText => text()();

  /// Label for the low end of the scale (e.g., "Very low", "Not at all").
  TextColumn get minLabel => text().nullable()();

  /// Label for the high end of the scale (e.g., "Excellent", "Extremely").
  TextColumn get maxLabel => text().nullable()();

  /// True if high raw values indicate negative well-being (e.g., anxiety).
  /// Composite score uses: scaleMax + scaleMin - rawValue for reversed items.
  /// INVARIANT: formula uses scaleMax+scaleMin-raw, NOT scaleMax+1-raw.
  /// The +1 variant is only valid when scaleMin=1 and must not be used.
  BoolColumn get isReversed => boolean().withDefault(const Constant(false))();

  /// Display order within the template (ascending).
  IntColumn get sortOrder => integer().withDefault(const Constant(0))();

  /// Whether this item is active in the current template. Deactivated items
  /// are hidden from check-ins but retained for historical answer data.
  BoolColumn get isActive => boolean().withDefault(const Constant(true))();
}

/// A completed check-in response — one per check-in session.
///
/// Links to the journal session that triggered the check-in and the template
/// used. [compositeScore] is null when all items were skipped (no score
/// computed). Partial completion also leaves [compositeScore] null.
///
/// See: ADR-0032 §Composite Score Formula (edge cases).
class CheckInResponses extends Table {
  /// Auto-increment primary key.
  IntColumn get id => integer().autoIncrement()();

  /// Foreign key to [JournalSessions] — the session that contained this check-in.
  TextColumn get sessionId => text().references(JournalSessions, #sessionId)();

  /// Foreign key to [QuestionnaireTemplates] — which template was used.
  IntColumn get templateId =>
      integer().references(QuestionnaireTemplates, #id)();

  /// When the check-in was completed.
  DateTimeColumn get completedAt => dateTime()();

  /// Composite score (0.0–100.0), scaled from mean of all non-null answered
  /// items. Null if all items were skipped or check-in was abandoned.
  /// Formula: (mean_scored_value - scaleMin) / (scaleMax - scaleMin) * 100
  RealColumn get compositeScore => real().nullable()();

  /// Cloud sync state — matches session sync pattern (ADR-0012).
  /// Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();
}

/// Individual answers within a check-in response — one per questionnaire item.
///
/// [value] is null when the item was skipped (explicit skip, non-numeric input
/// after re-prompt, silence timeout, or out-of-range after re-prompt).
/// Skipped items are excluded from the composite score denominator.
///
/// INVARIANT: Only one [CheckInAnswer] per (responseId, itemId) pair.
class CheckInAnswers extends Table {
  /// Auto-increment primary key.
  IntColumn get id => integer().autoIncrement()();

  /// Foreign key to [CheckInResponses].
  IntColumn get responseId => integer().references(CheckInResponses, #id)();

  /// Foreign key to [QuestionnaireItems].
  IntColumn get itemId => integer().references(QuestionnaireItems, #id)();

  /// The user's raw answer value. Null if the item was skipped.
  IntColumn get value => integer().nullable()();
}

/// Tasks created from conversation or the Tasks screen (Phase 13).
///
/// Each task is optionally associated with a session (tasks created from
/// the Tasks screen have no session). Tasks are local-first and auto-sync
/// to Google Tasks when connected.
///
/// Lifecycle states (status column):
///   PENDING_CREATE → ACTIVE (confirmed / synced to Google Tasks)
///   ACTIVE → COMPLETED (user marked done)
///   PENDING_CREATE → FAILED (sync error)
///
/// Sync states (syncStatus column) — independent from lifecycle:
///   PENDING → SYNCED (on successful Google Tasks API call)
///   PENDING → FAILED (on sync error)
class Tasks extends Table {
  /// Client-generated UUID — primary key.
  TextColumn get taskId => text()();

  /// Foreign key to JournalSessions — nullable (tasks from Tasks screen
  /// have no session).
  TextColumn get sessionId =>
      text().nullable().references(JournalSessions, #sessionId)();

  /// User ID for RLS and cloud sync.
  TextColumn get userId => text().nullable()();

  /// Task title (non-empty, max 200 chars).
  TextColumn get title => text()();

  /// Optional notes / details for the task.
  TextColumn get notes => text().nullable()();

  /// Due date (nullable — many tasks are open-ended).
  DateTimeColumn get dueDate => dateTime().nullable()();

  /// Google Tasks task ID — set after successful creation.
  TextColumn get googleTaskId => text().nullable()();

  /// Google Tasks task list ID (the "Agentic Journal" list).
  TextColumn get googleTaskListId => text().nullable()();

  /// Task lifecycle state.
  /// Values: 'PENDING_CREATE' | 'ACTIVE' | 'COMPLETED' | 'FAILED'
  TextColumn get status =>
      text().withDefault(const Constant('PENDING_CREATE'))();

  /// Cloud sync state — independent from lifecycle status.
  /// Values: 'PENDING' | 'SYNCED' | 'FAILED'
  TextColumn get syncStatus => text().withDefault(const Constant('PENDING'))();

  /// The raw user message that triggered this task extraction.
  TextColumn get rawUserMessage => text().nullable()();

  /// When the task was marked as completed.
  DateTimeColumn get completedAt => dateTime().nullable()();

  // -------------------------------------------------------------------------
  // Local notification fields (ADR-0033 — Scheduled Local Notifications)
  // -------------------------------------------------------------------------

  /// Exact date-time at which the OS notification should fire.
  ///
  /// Distinct from [dueDate] which is date-only for display purposes.
  /// Null when no notification has been scheduled for this task.
  /// Only set when the user supplies an explicit time; date-only tasks
  /// do NOT auto-schedule a notification.
  DateTimeColumn get reminderTime => dateTime().nullable()();

  /// ID of the scheduled OS notification (flutter_local_notifications).
  ///
  /// Stored so the notification can be cancelled on task completion
  /// or deletion. Null when no notification is scheduled.
  /// Range: 1000–1999 (task namespace — see ADR-0033 §Notification ID Namespace).
  IntColumn get notificationId => integer().nullable()();

  /// True when this task was created by a pure reminder phrase
  /// ("give cat meds in an hour") with no project/action context.
  ///
  /// Quick-reminder tasks may be surfaced in a separate "Reminders"
  /// section of the Tasks screen rather than the main task list.
  BoolColumn get isQuickReminder =>
      boolean().withDefault(const Constant(false))();

  /// Standard timestamps.
  DateTimeColumn get createdAt => dateTime().withDefault(currentDateAndTime)();
  DateTimeColumn get updatedAt => dateTime().withDefault(currentDateAndTime)();

  @override
  Set<Column> get primaryKey => {taskId};
}
