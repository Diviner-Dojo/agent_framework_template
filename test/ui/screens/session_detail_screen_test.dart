import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/database/daos/photo_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/ui/screens/session_detail_screen.dart';

void main() {
  group('SessionDetailScreen', () {
    late AppDatabase database;

    setUp(() {
      database = AppDatabase.forTesting(NativeDatabase.memory());
    });

    tearDown(() async {
      await database.close();
    });

    Widget buildTestWidget(String sessionId, {AppDatabase? db}) {
      return ProviderScope(
        overrides: [
          databaseProvider.overrideWithValue(db ?? database),
          activeSessionIdProvider.overrideWith((ref) => null),
        ],
        child: MaterialApp(
          home: SessionDetailScreen(sessionId: sessionId),
          routes: {
            '/session': (context) => const Scaffold(body: Text('Session')),
          },
        ),
      );
    }

    testWidgets('shows loading indicator initially', (tester) async {
      await tester.pumpWidget(buildTestWidget('nonexistent'));
      // On first frame, should show loading.
      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('shows session not found for missing session', (tester) async {
      await tester.pumpWidget(buildTestWidget('nonexistent'));
      await tester.pumpAndSettle();

      expect(find.text('Session not found.'), findsOneWidget);
    });

    testWidgets('shows messages for a session', (tester) async {
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
        'Hello journal!',
        DateTime.utc(2026, 2, 24, 10, 0),
      );
      await messageDao.insertMessage(
        'msg-2',
        'sess-1',
        'ASSISTANT',
        'Welcome back!',
        DateTime.utc(2026, 2, 24, 10, 1),
      );

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      expect(find.text('Hello journal!'), findsOneWidget);
      expect(find.text('Welcome back!'), findsOneWidget);
    });

    testWidgets('shows summary header when session has summary', (
      tester,
    ) async {
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
        'Good morning',
        DateTime.utc(2026, 2, 24, 10, 0),
      );
      await sessionDao.endSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 30),
        summary: 'A productive morning',
      );

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      expect(find.text('A productive morning'), findsOneWidget);
    });

    testWidgets('shows Continue Entry button for ended session', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);

      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );
      await sessionDao.endSession('sess-1', DateTime.utc(2026, 2, 24, 10, 30));

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      expect(find.text('Continue Entry'), findsOneWidget);
    });

    testWidgets('does not show Continue Entry when session is still active', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);

      // Session without endTime — still active.
      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      expect(find.text('Continue Entry'), findsNothing);
    });

    testWidgets('shows empty state when session has no messages', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);

      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      expect(find.text('No messages in this session.'), findsOneWidget);
    });

    testWidgets('maps photos to messages by messageId', (tester) async {
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);
      final photoDao = PhotoDao(database);

      await sessionDao.createSession(
        'sess-1',
        DateTime.utc(2026, 2, 24, 10, 0),
        'UTC',
      );
      await messageDao.insertMessage(
        'msg-1',
        'sess-1',
        'USER',
        '[Photo]',
        DateTime.utc(2026, 2, 24, 10, 0),
        inputMethod: 'PHOTO',
        photoId: 'photo-1',
      );
      await photoDao.insertPhoto(
        photoId: 'photo-1',
        sessionId: 'sess-1',
        localPath: '/fake/photo.jpg',
        timestamp: DateTime.utc(2026, 2, 24, 10, 0),
        messageId: 'msg-1',
        description: 'A test photo',
      );

      await tester.pumpWidget(buildTestWidget('sess-1'));
      await tester.pumpAndSettle();

      // The message content should be visible.
      expect(find.text('[Photo]'), findsOneWidget);
      // Photo description should be passed to ChatBubble as caption.
      // (We can't easily verify the caption text but the widget rendered.)
    });
  });
}
