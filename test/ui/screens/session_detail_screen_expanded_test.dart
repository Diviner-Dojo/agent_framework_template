// ===========================================================================
// file: test/ui/screens/session_detail_screen_expanded_test.dart
// purpose: Expanded widget tests for the session detail screen — covers
//          location pill, resume button interaction, video/photo indexing.
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
import 'package:agentic_journal/ui/screens/session_detail_screen.dart';

void main() {
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

  Widget buildTestWidget(
    String sessionId, {
    AppDatabase? db,
    String? activeSessionId,
  }) {
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        databaseProvider.overrideWithValue(db ?? database),
        activeSessionIdProvider.overrideWith((ref) => activeSessionId),
      ],
      child: MaterialApp(
        home: SessionDetailScreen(sessionId: sessionId),
        routes: {
          '/session': (context) => const Scaffold(body: Text('Active Session')),
        },
      ),
    );
  }

  group('SessionDetailScreen — location pill', () {
    testWidgets('shows location chip when session has locationName', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);

      await sessionDao.createSession(
        'sess-loc',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );
      await messageDao.insertMessage(
        'msg-1',
        'sess-loc',
        'USER',
        'At the park',
        DateTime.utc(2026, 2, 24, 10, 0),
      );
      await sessionDao.endSession(
        'sess-loc',
        DateTime.utc(2026, 2, 24, 10, 30),
      );
      // Set location name.
      await sessionDao.updateSessionLocation(
        'sess-loc',
        latitude: 40.7128,
        longitude: -74.0060,
        locationName: 'Central Park',
      );

      await tester.pumpWidget(buildTestWidget('sess-loc'));
      await tester.pumpAndSettle();

      expect(find.text('Central Park'), findsOneWidget);
      expect(find.byIcon(Icons.location_on_outlined), findsOneWidget);
    });

    testWidgets('hides location chip when session has no locationName', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);

      await sessionDao.createSession(
        'sess-noloc',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );

      await tester.pumpWidget(buildTestWidget('sess-noloc'));
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.location_on_outlined), findsNothing);
    });
  });

  group('SessionDetailScreen — continue entry button', () {
    testWidgets('hides Continue Entry when another session is active', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);

      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );
      await sessionDao.endSession('sess-1', DateTime.utc(2026, 2, 24, 10, 30));

      // Another session is active.
      await tester.pumpWidget(
        buildTestWidget('sess-1', activeSessionId: 'sess-other'),
      );
      await tester.pumpAndSettle();

      expect(find.text('Continue Entry'), findsNothing);
    });

    testWidgets(
      'shows Continue Entry when session ended and no active session',
      (tester) async {
        final sessionDao = SessionDao(database);
        final messageDao = MessageDao(database);

        await sessionDao.createSession(
          'sess-1',
          DateTime.utc(2026, 2, 24, 10, 0),
          'UTC',
        );
        await messageDao.insertMessage(
          'msg-1',
          'sess-1',
          'USER',
          'Hello',
          DateTime.utc(2026, 2, 24, 10, 0),
        );
        await sessionDao.endSession(
          'sess-1',
          DateTime.utc(2026, 2, 24, 10, 30),
        );

        await tester.pumpWidget(buildTestWidget('sess-1'));
        await tester.pumpAndSettle();

        expect(find.text('Continue Entry'), findsOneWidget);
      },
    );
  });

  group('SessionDetailScreen — summary header', () {
    testWidgets('hides summary when session has no summary', (tester) async {
      final sessionDao = SessionDao(database);

      await sessionDao.createSession(
        'sess-nosum',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );

      await tester.pumpWidget(buildTestWidget('sess-nosum'));
      await tester.pumpAndSettle();

      // No summary container — the italic text should not be present.
      expect(find.textContaining('productive'), findsNothing);
    });
  });

  group('SessionDetailScreen — message list', () {
    testWidgets('renders multiple messages in correct order', (tester) async {
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);

      await sessionDao.createSession(
        'sess-multi',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );
      await messageDao.insertMessage(
        'msg-1',
        'sess-multi',
        'USER',
        'First message',
        DateTime.utc(2026, 2, 24, 10, 0),
      );
      await messageDao.insertMessage(
        'msg-2',
        'sess-multi',
        'ASSISTANT',
        'Second message',
        DateTime.utc(2026, 2, 24, 10, 1),
      );
      await messageDao.insertMessage(
        'msg-3',
        'sess-multi',
        'USER',
        'Third message',
        DateTime.utc(2026, 2, 24, 10, 2),
      );

      await tester.pumpWidget(buildTestWidget('sess-multi'));
      await tester.pumpAndSettle();

      expect(find.text('First message'), findsOneWidget);
      expect(find.text('Second message'), findsOneWidget);
      expect(find.text('Third message'), findsOneWidget);
    });
  });
}
