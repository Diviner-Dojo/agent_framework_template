// ===========================================================================
// file: test/ui/session_detail_resume_test.dart
// purpose: Widget tests for the "Continue Entry" button on SessionDetailScreen.
//
// Verifies:
//   - Button shows for completed sessions when no session is active
//   - Button hidden when another session is active
//   - Button hidden for sessions without endTime (still active)
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart'
    show sharedPreferencesProvider;
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/session_detail_screen.dart';

void main() {
  group('SessionDetailScreen Continue Entry', () {
    late AppDatabase database;
    late SharedPreferences prefs;

    setUp(() async {
      database = AppDatabase.forTesting(NativeDatabase.memory());
      SharedPreferences.setMockInitialValues({});
      prefs = await SharedPreferences.getInstance();
    });

    tearDown(() async {
      await database.close();
    });

    Widget buildTestWidget(String sessionId, {String? activeSessionId}) {
      return UncontrolledProviderScope(
        container: ProviderContainer(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            databaseProvider.overrideWithValue(database),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
            activeSessionIdProvider.overrideWith((ref) => activeSessionId),
          ],
        ),
        child: MaterialApp(
          routes: {
            '/session': (context) =>
                const Scaffold(body: Text('Active Session Screen')),
          },
          home: SessionDetailScreen(sessionId: sessionId),
        ),
      );
    }

    testWidgets(
      'shows Continue Entry for completed session with no active session',
      (tester) async {
        final sessionDao = SessionDao(database);
        final messageDao = MessageDao(database);
        final now = DateTime.now().toUtc();

        await sessionDao.createSession('completed-1', now, 'UTC');
        await messageDao.insertMessage(
          'msg-1',
          'completed-1',
          'ASSISTANT',
          'Hello!',
          now,
        );
        await sessionDao.endSession(
          'completed-1',
          now.add(const Duration(minutes: 5)),
          summary: 'A good session',
        );

        await tester.pumpWidget(buildTestWidget('completed-1'));
        await tester.pumpAndSettle();

        expect(find.text('Continue Entry'), findsOneWidget);
      },
    );

    testWidgets('hides Continue Entry when another session is active', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);
      final now = DateTime.now().toUtc();

      await sessionDao.createSession('completed-2', now, 'UTC');
      await sessionDao.endSession(
        'completed-2',
        now.add(const Duration(minutes: 5)),
        summary: 'Another session',
      );

      await tester.pumpWidget(
        buildTestWidget('completed-2', activeSessionId: 'other-active'),
      );
      await tester.pumpAndSettle();

      expect(find.text('Continue Entry'), findsNothing);
    });

    testWidgets('hides Continue Entry for session without endTime', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);
      final now = DateTime.now().toUtc();

      // Session without endTime (still in progress).
      await sessionDao.createSession('in-progress-1', now, 'UTC');

      await tester.pumpWidget(buildTestWidget('in-progress-1'));
      await tester.pumpAndSettle();

      expect(find.text('Continue Entry'), findsNothing);
    });
  });
}
