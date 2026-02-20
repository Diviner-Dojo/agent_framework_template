import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/services/supabase_service.dart';

void main() {
  group('syncRepositoryProvider', () {
    test('creates a SyncRepository with dependencies', () {
      final db = AppDatabase.forTesting(NativeDatabase.memory());
      final unconfiguredService = SupabaseService(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(db),
          environmentProvider.overrideWithValue(
            const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          ),
          supabaseServiceProvider.overrideWithValue(unconfiguredService),
        ],
      );

      final syncRepo = container.read(syncRepositoryProvider);
      expect(syncRepo, isNotNull);

      container.dispose();
      db.close();
    });
  });

  group('pendingSyncCountProvider', () {
    test('returns 0 when not authenticated', () async {
      final db = AppDatabase.forTesting(NativeDatabase.memory());

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(db),
          isAuthenticatedProvider.overrideWithValue(false),
        ],
      );

      // Wait for the stream to emit
      final sub = container.listen(pendingSyncCountProvider, (_, __) {});
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final count = container.read(pendingSyncCountProvider);
      expect(count.value, 0);

      sub.close();
      container.dispose();
      await db.close();
    });

    test('returns count of pending sessions when authenticated', () async {
      final db = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(db);

      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.createSession(
        'session-2',
        DateTime.utc(2026, 2, 20, 1),
        'UTC',
      );

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(db),
          isAuthenticatedProvider.overrideWithValue(true),
        ],
      );

      // Wait for the stream to emit
      final sub = container.listen(pendingSyncCountProvider, (_, __) {});
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final count = container.read(pendingSyncCountProvider);
      expect(count.value, 2);

      sub.close();
      container.dispose();
      await db.close();
    });

    test('excludes synced sessions from count', () async {
      final db = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(db);

      await sessionDao.createSession(
        'session-1',
        DateTime.utc(2026, 2, 20),
        'UTC',
      );
      await sessionDao.updateSyncStatus(
        'session-1',
        'SYNCED',
        DateTime.utc(2026, 2, 20),
      );
      await sessionDao.createSession(
        'session-2',
        DateTime.utc(2026, 2, 20, 1),
        'UTC',
      );

      final container = ProviderContainer(
        overrides: [
          databaseProvider.overrideWithValue(db),
          isAuthenticatedProvider.overrideWithValue(true),
        ],
      );

      final sub = container.listen(pendingSyncCountProvider, (_, __) {});
      await Future<void>.delayed(const Duration(milliseconds: 50));

      final count = container.read(pendingSyncCountProvider);
      expect(count.value, 1);

      sub.close();
      container.dispose();
      await db.close();
    });
  });
}
