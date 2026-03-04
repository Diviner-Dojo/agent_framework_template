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
  group('SessionDetailScreen', () {
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

    Widget buildTestWidget(String sessionId) {
      return UncontrolledProviderScope(
        container: ProviderContainer(
          overrides: [
            databaseProvider.overrideWithValue(database),
            // themeProvider depends on sharedPreferencesProvider — override
            // it so the theme notifier can initialize without throwing.
            sharedPreferencesProvider.overrideWithValue(prefs),
            agentRepositoryProvider.overrideWithValue(AgentRepository()),
          ],
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

    // -----------------------------------------------------------------------
    // Tag editing (Phase 4A)
    // -----------------------------------------------------------------------

    group('Tag editing', () {
      testWidgets('shows tag chips when session has all three tag types', (
        tester,
      ) async {
        final sessionDao = SessionDao(database);
        final now = DateTime.now().toUtc();
        await sessionDao.createSession('tag-session', now, 'UTC');
        await sessionDao.endSession(
          'tag-session',
          now.add(const Duration(minutes: 5)),
          moodTags: '["happy","tired"]',
          people: '["Alice"]',
          topicTags: '["work"]',
        );

        await tester.pumpWidget(buildTestWidget('tag-session'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(InputChip, 'happy'), findsOneWidget);
        expect(find.widgetWithText(InputChip, 'tired'), findsOneWidget);
        expect(find.widgetWithText(InputChip, 'Alice'), findsOneWidget);
        expect(find.widgetWithText(InputChip, 'work'), findsOneWidget);
      });

      testWidgets('deletes a tag chip when delete button tapped', (
        tester,
      ) async {
        // Use one mood chip so the delete-button finder is unambiguous.
        final sessionDao = SessionDao(database);
        final now = DateTime.now().toUtc();
        await sessionDao.createSession('delete-tag-session', now, 'UTC');
        await sessionDao.endSession(
          'delete-tag-session',
          now.add(const Duration(minutes: 5)),
          moodTags: '["happy"]',
        );

        await tester.pumpWidget(buildTestWidget('delete-tag-session'));
        await tester.pumpAndSettle();
        expect(find.widgetWithText(InputChip, 'happy'), findsOneWidget);

        // The delete button has tooltip 'Remove happy' (set via
        // deleteButtonTooltipMessage on the InputChip).
        await tester.tap(find.byTooltip('Remove happy'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(InputChip, 'happy'), findsNothing);
      });

      testWidgets('adds a new tag via the add button and dialog', (
        tester,
      ) async {
        final sessionDao = SessionDao(database);
        final now = DateTime.now().toUtc();
        await sessionDao.createSession('add-tag-session', now, 'UTC');

        await tester.pumpWidget(buildTestWidget('add-tag-session'));
        await tester.pumpAndSettle();
        // No chips yet.
        expect(find.byType(InputChip), findsNothing);

        // Tap the first "+" add IconButton (Mood row — first of the three).
        await tester.tap(find.byIcon(Icons.add).first);
        await tester.pumpAndSettle();
        expect(find.text('Add tag'), findsOneWidget);

        await tester.enterText(find.byType(TextField), 'energized');
        await tester.tap(find.text('Add'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(InputChip, 'energized'), findsOneWidget);
      });

      testWidgets('edits an existing tag by tapping the chip', (tester) async {
        final sessionDao = SessionDao(database);
        final now = DateTime.now().toUtc();
        await sessionDao.createSession('edit-tag-session', now, 'UTC');
        await sessionDao.endSession(
          'edit-tag-session',
          now.add(const Duration(minutes: 5)),
          moodTags: '["happy"]',
        );

        await tester.pumpWidget(buildTestWidget('edit-tag-session'));
        await tester.pumpAndSettle();
        expect(find.widgetWithText(InputChip, 'happy'), findsOneWidget);

        // Tap the chip to open the edit dialog.
        await tester.tap(find.widgetWithText(InputChip, 'happy'));
        await tester.pumpAndSettle();
        expect(find.text('Edit tag'), findsOneWidget);

        // Replace pre-filled 'happy' with 'joyful'.
        await tester.enterText(find.byType(TextField), 'joyful');
        await tester.tap(find.text('Save'));
        await tester.pumpAndSettle();

        expect(find.widgetWithText(InputChip, 'joyful'), findsOneWidget);
        expect(find.widgetWithText(InputChip, 'happy'), findsNothing);
      });
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

    // -----------------------------------------------------------------------
    // Message editing (Phase 4F — voice transcription correction)
    // -----------------------------------------------------------------------

    group('Message editing', () {
      testWidgets(
        'long-press on USER bubble opens edit sheet with pre-filled text (regression)',
        (tester) async {
          // Regression guard: long-press on USER ChatBubble must open edit sheet.
          // @Tags(['regression']) — ledger entry: memory/bugs/regression-ledger.md 2026-03-04
          final sessionDao = SessionDao(database);
          final messageDao = MessageDao(database);
          final now = DateTime.now().toUtc();

          await sessionDao.createSession('edit-session', now, 'UTC');
          await messageDao.insertMessage(
            'msg-user',
            'edit-session',
            'USER',
            'Shawn helped me today.',
            now,
          );

          await tester.pumpWidget(buildTestWidget('edit-session'));
          await tester.pumpAndSettle();

          expect(find.text('Shawn helped me today.'), findsOneWidget);

          // Long-press the USER bubble.
          await tester.longPress(find.text('Shawn helped me today.'));
          await tester.pumpAndSettle();

          // Edit sheet should open with "Edit message" title.
          expect(find.text('Edit message'), findsOneWidget);

          // The TextField should be pre-filled with the original content.
          expect(
            tester.widget<TextField>(find.byType(TextField)).controller?.text,
            'Shawn helped me today.',
          );
        },
      );

      testWidgets('saving edit updates message content in UI', (tester) async {
        final sessionDao = SessionDao(database);
        final messageDao = MessageDao(database);
        final now = DateTime.now().toUtc();

        await sessionDao.createSession('edit-save-session', now, 'UTC');
        await messageDao.insertMessage(
          'msg-edit',
          'edit-save-session',
          'USER',
          'Shawn helped me today.',
          now,
        );

        await tester.pumpWidget(buildTestWidget('edit-save-session'));
        await tester.pumpAndSettle();

        // Open the edit sheet.
        await tester.longPress(find.text('Shawn helped me today.'));
        await tester.pumpAndSettle();

        // Clear and type corrected text.
        final textField = find.descendant(
          of: find.byType(BottomSheet),
          matching: find.byType(TextField),
        );
        await tester.enterText(textField, 'Sean helped me today.');
        await tester.tap(find.text('Save'));
        await tester.pumpAndSettle();

        // Updated content should appear in the transcript; old content gone.
        // Note: summary header may also show corrected content after AI regen,
        // so we use findsOneWidget on the bubble specifically and check old is gone.
        expect(find.text('Sean helped me today.'), findsAtLeastNWidgets(1));
        expect(find.text('Shawn helped me today.'), findsNothing);
      });

      testWidgets(
        'ASSISTANT bubbles are not long-press editable (no edit sheet)',
        (tester) async {
          final sessionDao = SessionDao(database);
          final messageDao = MessageDao(database);
          final now = DateTime.now().toUtc();

          await sessionDao.createSession('no-edit-session', now, 'UTC');
          await messageDao.insertMessage(
            'msg-assistant',
            'no-edit-session',
            'ASSISTANT',
            'How was your day?',
            now,
          );

          await tester.pumpWidget(buildTestWidget('no-edit-session'));
          await tester.pumpAndSettle();

          await tester.longPress(find.text('How was your day?'));
          await tester.pumpAndSettle();

          // Edit sheet should NOT appear.
          expect(find.text('Edit message'), findsNothing);
        },
      );
    });
  });
}
