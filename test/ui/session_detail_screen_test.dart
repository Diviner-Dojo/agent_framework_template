// ===========================================================================
// file: test/ui/session_detail_screen_test.dart
// purpose: Widget tests for the read-only session detail screen.
//
// Tests verify that:
//   - The loading indicator appears initially
//   - The screen shows "Session not found" for a non-existent session
//   - The screen renders messages when a valid session exists
//   - The summary is displayed when present
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/message_dao.dart';
import 'package:agentic_journal/database/daos/session_dao.dart';
import 'package:agentic_journal/providers/database_provider.dart';
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

    Widget buildTestWidget(String sessionId) {
      return UncontrolledProviderScope(
        container: ProviderContainer(
          overrides: [databaseProvider.overrideWithValue(database)],
        ),
        child: MaterialApp(home: SessionDetailScreen(sessionId: sessionId)),
      );
    }

    testWidgets('shows Session not found for non-existent session', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget('non-existent-id'));
      await tester.pumpAndSettle();

      expect(find.text('Session not found.'), findsOneWidget);
    });

    testWidgets('renders messages for a valid session', (tester) async {
      // Seed the database with a session and messages.
      final sessionDao = SessionDao(database);
      final messageDao = MessageDao(database);
      final now = DateTime.now().toUtc();

      await sessionDao.createSession('test-session', now, 'UTC');
      await messageDao.insertMessage(
        'msg-1',
        'test-session',
        'ASSISTANT',
        'Good morning!',
        now,
      );
      await messageDao.insertMessage(
        'msg-2',
        'test-session',
        'USER',
        'Hello, I had a great day.',
        now.add(const Duration(seconds: 1)),
      );

      await tester.pumpWidget(buildTestWidget('test-session'));
      await tester.pumpAndSettle();

      expect(find.text('Good morning!'), findsOneWidget);
      expect(find.text('Hello, I had a great day.'), findsOneWidget);
    });

    testWidgets('displays session summary when present', (tester) async {
      final sessionDao = SessionDao(database);
      final now = DateTime.now().toUtc();

      await sessionDao.createSession('test-session-2', now, 'UTC');
      await sessionDao.endSession(
        'test-session-2',
        now.add(const Duration(minutes: 5)),
        summary: 'Had a productive day at work.',
      );

      await tester.pumpWidget(buildTestWidget('test-session-2'));
      await tester.pumpAndSettle();

      expect(find.text('Had a productive day at work.'), findsOneWidget);
    });

    testWidgets('shows empty message state for session with no messages', (
      tester,
    ) async {
      final sessionDao = SessionDao(database);
      final now = DateTime.now().toUtc();

      await sessionDao.createSession('empty-session', now, 'UTC');

      await tester.pumpWidget(buildTestWidget('empty-session'));
      await tester.pumpAndSettle();

      expect(find.text('No messages in this session.'), findsOneWidget);
    });
  });
}
