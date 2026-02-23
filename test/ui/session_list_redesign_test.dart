import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/ui/screens/session_list_screen.dart';

void main() {
  group('SessionListScreen redesign', () {
    late AppDatabase database;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
    });

    tearDown(() async {
      await database.close();
    });

    Future<ProviderContainer> buildTestWidget(WidgetTester tester) async {
      late ProviderContainer container;

      await tester.pumpWidget(
        UncontrolledProviderScope(
          container: container = ProviderContainer(
            overrides: [
              databaseProvider.overrideWithValue(database),
              agentRepositoryProvider.overrideWithValue(AgentRepository()),
            ],
          ),
          child: MaterialApp(
            routes: {
              '/': (_) => const SessionListScreen(),
              '/session': (_) => const Scaffold(body: Text('Active Session')),
              '/session/detail': (_) =>
                  const Scaffold(body: Text('Session Detail')),
              '/settings': (_) => const Scaffold(body: Text('Settings')),
              '/search': (_) => const Scaffold(body: Text('Search')),
            },
          ),
        ),
      );
      await tester.pumpAndSettle();
      return container;
    }

    testWidgets('shows empty state when no sessions exist', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      expect(find.text('No journal sessions yet'), findsOneWidget);
      expect(find.text('Tap + to start your first entry.'), findsOneWidget);
    });

    testWidgets('shows month-year header when sessions exist', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create sessions in February 2026.
      final sessionDao = SessionDao(database);
      await sessionDao.createSession(
        's1',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 20, 10, 30),
        summary: 'First session',
      );

      await tester.pumpAndSettle();

      // Should show February 2026 header.
      expect(find.text('February 2026'), findsOneWidget);
    });

    testWidgets('groups sessions by different months', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      // Create sessions in two different months.
      final sessionDao = SessionDao(database);
      await sessionDao.createSession(
        's1',
        DateTime.utc(2026, 1, 15, 10, 0),
        'UTC',
      );
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 1, 15, 10, 30),
        summary: 'January session',
      );
      await sessionDao.createSession(
        's2',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );
      await sessionDao.endSession(
        's2',
        DateTime.utc(2026, 2, 20, 10, 30),
        summary: 'February session',
      );

      await tester.pumpAndSettle();

      // Both month headers should appear (newest first).
      expect(find.text('February 2026'), findsOneWidget);
      expect(find.text('January 2026'), findsOneWidget);
    });

    testWidgets('session cards show summary text', (tester) async {
      final container = await buildTestWidget(tester);
      addTearDown(container.dispose);

      final sessionDao = SessionDao(database);
      await sessionDao.createSession(
        's1',
        DateTime.utc(2026, 2, 20, 10, 0),
        'UTC',
      );
      await sessionDao.endSession(
        's1',
        DateTime.utc(2026, 2, 20, 10, 30),
        summary: 'Talked about work stress',
      );

      await tester.pumpAndSettle();

      expect(find.text('Talked about work stress'), findsOneWidget);
    });
  });

  group('watchSessionsPaginated', () {
    test('returns correct number of sessions', () async {
      final database = AppDatabase.forTesting(NativeDatabase.memory());
      final sessionDao = SessionDao(database);

      // Create 5 sessions.
      for (int i = 0; i < 5; i++) {
        await sessionDao.createSession(
          's$i',
          DateTime.utc(2026, 2, 20 + i),
          'UTC',
        );
      }

      // Paginate to 3.
      final sessions = await sessionDao.watchSessionsPaginated(3).first;
      expect(sessions.length, 3);
      // Should be newest first.
      expect(sessions[0].sessionId, 's4');
      expect(sessions[1].sessionId, 's3');
      expect(sessions[2].sessionId, 's2');

      await database.close();
    });
  });

  group('paginatedSessionsProvider', () {
    test('default page size is 50', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      expect(container.read(sessionPageSizeProvider), 50);
    });

    test('incrementing page size works', () {
      final container = ProviderContainer();
      addTearDown(container.dispose);

      container.read(sessionPageSizeProvider.notifier).state += 50;
      expect(container.read(sessionPageSizeProvider), 100);
    });
  });
}
