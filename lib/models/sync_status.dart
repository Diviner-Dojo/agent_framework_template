// ===========================================================================
// file: lib/models/sync_status.dart
// purpose: Enum representing the sync state of a journal session.
//          Phase 1 only uses PENDING (no sync implemented yet).
//          Phase 4 will add Supabase sync and use all three values.
// ===========================================================================

/// Tracks whether a journal session has been synced to the cloud.
///
/// The sync_status column in journal_sessions stores these as uppercase
/// strings ('PENDING', 'SYNCED', 'FAILED'). This enum provides type-safe
/// conversion between Dart code and the SQLite string values.
enum SyncStatus {
  pending,
  synced,
  failed;

  /// Convert from the string stored in SQLite (e.g., 'PENDING').
  ///
  /// Defaults to [pending] for any unrecognized value — this is a safe
  /// fallback because a PENDING record will simply be retried on next sync.
  static SyncStatus fromString(String value) {
    switch (value.toUpperCase()) {
      case 'SYNCED':
        return SyncStatus.synced;
      case 'FAILED':
        return SyncStatus.failed;
      case 'PENDING':
      default:
        return SyncStatus.pending;
    }
  }

  /// Convert to the uppercase string format stored in SQLite.
  ///
  /// Example: SyncStatus.pending.toDbString() → 'PENDING'
  String toDbString() => name.toUpperCase();
}
