import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/models/sync_status.dart';

void main() {
  group('SyncStatus.fromString', () {
    test('converts PENDING to SyncStatus.pending', () {
      expect(SyncStatus.fromString('PENDING'), SyncStatus.pending);
    });

    test('converts SYNCED to SyncStatus.synced', () {
      expect(SyncStatus.fromString('SYNCED'), SyncStatus.synced);
    });

    test('converts FAILED to SyncStatus.failed', () {
      expect(SyncStatus.fromString('FAILED'), SyncStatus.failed);
    });

    test('is case insensitive', () {
      expect(SyncStatus.fromString('pending'), SyncStatus.pending);
      expect(SyncStatus.fromString('Synced'), SyncStatus.synced);
      expect(SyncStatus.fromString('failed'), SyncStatus.failed);
    });

    test('defaults to pending for unknown values', () {
      expect(SyncStatus.fromString('UNKNOWN_VALUE'), SyncStatus.pending);
      expect(SyncStatus.fromString(''), SyncStatus.pending);
      expect(SyncStatus.fromString('garbage'), SyncStatus.pending);
    });
  });

  group('SyncStatus.toDbString', () {
    test('round-trips for each value', () {
      expect(SyncStatus.pending.toDbString(), 'PENDING');
      expect(SyncStatus.synced.toDbString(), 'SYNCED');
      expect(SyncStatus.failed.toDbString(), 'FAILED');
    });

    test('fromString and toDbString are symmetric', () {
      for (final status in SyncStatus.values) {
        final dbString = status.toDbString();
        final roundTripped = SyncStatus.fromString(dbString);
        expect(roundTripped, status);
      }
    });
  });
}
