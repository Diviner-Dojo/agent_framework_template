import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:drift/native.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';

/// A mock assistant service for testing.
class _MockAssistantService extends AssistantRegistrationService {
  bool isDefaultReturn;

  _MockAssistantService({this.isDefaultReturn = false})
    : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async => isDefaultReturn;

  @override
  Future<void> openAssistantSettings() async {}
}

void main() {
  group('lastSessionDateProvider', () {
    test('returns null when no sessions exist', () async {
      final db = AppDatabase.forTesting(NativeDatabase.memory());

      final container = ProviderContainer(
        overrides: [databaseProvider.overrideWithValue(db)],
      );

      final date = await container.read(lastSessionDateProvider.future);
      expect(date, isNull);

      container.dispose();
      await db.close();
    });

    test('returns most recent session start time', () async {
      final db = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(db);

      final older = DateTime.utc(2026, 2, 18);
      final newer = DateTime.utc(2026, 2, 20);
      await sessionDao.createSession('s1', older, 'UTC');
      await sessionDao.createSession('s2', newer, 'UTC');

      final container = ProviderContainer(
        overrides: [databaseProvider.overrideWithValue(db)],
      );

      final date = await container.read(lastSessionDateProvider.future);
      expect(date, newer);

      container.dispose();
      await db.close();
    });
  });

  group('isDefaultAssistantProvider', () {
    test('returns false when service returns false', () async {
      final container = ProviderContainer(
        overrides: [
          assistantServiceProvider.overrideWithValue(
            _MockAssistantService(isDefaultReturn: false),
          ),
        ],
      );

      final result = await container.read(isDefaultAssistantProvider.future);
      expect(result, false);

      container.dispose();
    });

    test('returns true when service returns true', () async {
      final container = ProviderContainer(
        overrides: [
          assistantServiceProvider.overrideWithValue(
            _MockAssistantService(isDefaultReturn: true),
          ),
        ],
      );

      final result = await container.read(isDefaultAssistantProvider.future);
      expect(result, true);

      container.dispose();
    });
  });
}
