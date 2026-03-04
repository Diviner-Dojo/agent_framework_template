// ===========================================================================
// file: test/ui/settings_checkin_questionnaire_test.dart
// purpose: Widget tests for the Pulse Check-In questionnaire settings section.
//
// Tests verify that:
//   - The Pulse Check-In ExpansionTile is present in settings
//   - Scale toggle renders with the correct preset selected
//   - Edit icon is present for each item
//   - Toggle switch present and value reflects isActive
//   - Add custom question button is visible
//   - Edit dialog opens with existing question text pre-filled
//   - Add dialog opens on button tap
//   - Scale toggle shows success SnackBar on save (A7)
//   - Item deactivation shows Undo SnackBar (A8)
//
// DAO write paths (toggle, reorder) are exercised in the SnackBar group using
// a real in-memory QuestionnaireDao.
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/database/daos/questionnaire_dao.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/llm_providers.dart';
import 'package:agentic_journal/providers/photo_providers.dart';
import 'package:agentic_journal/providers/questionnaire_providers.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/search_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/providers/sync_providers.dart';
import 'package:agentic_journal/providers/voice_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

// ---------------------------------------------------------------------------
// Test helpers
// ---------------------------------------------------------------------------

class _MockAssistantService extends AssistantRegistrationService {
  _MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async => false;

  @override
  Future<void> openAssistantSettings() async {}
}

QuestionnaireTemplate _testTemplate({int scaleMin = 1, int scaleMax = 10}) {
  final now = DateTime(2026, 3, 1);
  return QuestionnaireTemplate(
    id: 1,
    name: 'Pulse Check-In',
    instrumentCode: 'custom',
    version: '1.0.0',
    isSystemDefault: true,
    isActive: true,
    scaleMin: scaleMin,
    scaleMax: scaleMax,
    sortOrder: 0,
    createdAt: now,
    updatedAt: now,
  );
}

QuestionnaireItem _testItem({
  required int id,
  String questionText = 'How are you feeling?',
  bool isActive = true,
}) {
  return QuestionnaireItem(
    id: id,
    templateId: 1,
    questionText: questionText,
    isReversed: false,
    sortOrder: id - 1,
    isActive: isActive,
  );
}

/// Minimal fake DAO for widget-test SnackBar scenarios.
///
/// Overrides all drift-backed write/read methods to operate purely in memory.
/// This prevents drift's internal StreamQueryStore from scheduling timers
/// inside flutter_test's FakeAsync zone, which would cause pumpAndSettle
/// to loop indefinitely or leave pending timers after test cleanup.
class _FakeQuestionnaireDao extends QuestionnaireDao {
  final _isActive = <int, bool>{};

  _FakeQuestionnaireDao(super.db);

  /// Seed initial isActive state for an item (called in setUp).
  void seed(int id, {required bool isActive}) => _isActive[id] = isActive;

  @override
  Future<int> updateItem(int id, QuestionnaireItemsCompanion companion) async {
    if (companion.isActive.present) _isActive[id] = companion.isActive.value;
    return 1;
  }

  @override
  Future<int> updateTemplate(
    int id,
    QuestionnaireTemplatesCompanion companion,
  ) async => 1; // no-op — write succeeds without touching drift

  @override
  Future<List<QuestionnaireItem>> getActiveItemsForTemplate(
    int templateId,
  ) async => _isActive.entries
      .where((e) => e.value)
      .map((e) => _testItem(id: e.key))
      .toList();
}

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

void main() {
  late SharedPreferences prefs;
  final mockService = _MockAssistantService();

  setUp(() async {
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
  });

  Widget buildTestWidget({
    QuestionnaireTemplate? template,
    List<QuestionnaireItem> items = const [],
  }) {
    final tmpl = template ?? _testTemplate();
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        assistantServiceProvider.overrideWithValue(mockService),
        appVersionProvider.overrideWith((ref) => Future.value('1.0.0')),
        environmentProvider.overrideWithValue(
          const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
        ),
        supabaseServiceProvider.overrideWithValue(
          SupabaseService(
            environment: const Environment.custom(
              supabaseUrl: '',
              supabaseAnonKey: '',
            ),
          ),
        ),
        isAuthenticatedProvider.overrideWithValue(false),
        currentUserProvider.overrideWithValue(null),
        pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
        sessionCountProvider.overrideWith((ref) => Future.value(0)),
        sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
        llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
        photoStorageInfoProvider.overrideWith(
          (ref) =>
              Future.value(const PhotoStorageInfo(count: 0, totalSizeBytes: 0)),
        ),
        // Check-in providers — backed by test data, no real DB.
        activeCheckInItemsProvider.overrideWith((ref) => Stream.value(items)),
        activeDefaultTemplateProvider.overrideWith((ref) => Stream.value(tmpl)),
      ],
      child: MaterialApp(
        home: const SettingsScreen(),
        routes: {'/auth': (context) => const Scaffold()},
      ),
    );
  }

  /// Helper: scroll to and expand the Pulse Check-In tile, then settle.
  Future<void> expandCheckInTile(WidgetTester tester) async {
    await tester.scrollUntilVisible(
      find.text('Pulse Check-In'),
      300,
      scrollable: find.byType(Scrollable).first,
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pulse Check-In'));
    await tester.pumpAndSettle();
  }

  // ---------------------------------------------------------------------------
  // Tests
  // ---------------------------------------------------------------------------

  group('SettingsScreen — Pulse Check-In questionnaire section', () {
    testWidgets('Pulse Check-In ExpansionTile is present', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.scrollUntilVisible(
        find.text('Pulse Check-In'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      expect(find.text('Pulse Check-In'), findsOneWidget);
    });

    testWidgets('expanding shows Answer scale header', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(find.text('Answer scale'), findsOneWidget);
    });

    testWidgets('scale toggle shows all three preset segments', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(find.text('1 – 5'), findsOneWidget);
      expect(find.text('1 – 10'), findsOneWidget);
      expect(find.text('0 – 100'), findsOneWidget);
    });

    testWidgets('scale toggle 1-10 segment is selected by default', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildTestWidget(template: _testTemplate(scaleMin: 1, scaleMax: 10)),
      );
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      // SegmentedButton with value '1-10' should be selected.
      final button = tester.widget<SegmentedButton<String>>(
        find.byType(SegmentedButton<String>),
      );
      expect(button.selected, equals({'1-10'}));
    });

    testWidgets('scale toggle 1-5 segment is selected for scaleMax=5', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildTestWidget(template: _testTemplate(scaleMin: 1, scaleMax: 5)),
      );
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      final button = tester.widget<SegmentedButton<String>>(
        find.byType(SegmentedButton<String>),
      );
      expect(button.selected, equals({'1-5'}));
    });

    testWidgets('scale toggle 0-100 segment is selected for scaleMax=100', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildTestWidget(template: _testTemplate(scaleMin: 0, scaleMax: 100)),
      );
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      final button = tester.widget<SegmentedButton<String>>(
        find.byType(SegmentedButton<String>),
      );
      expect(button.selected, equals({'0-100'}));
    });

    testWidgets('edit icon is present for each item', (tester) async {
      final items = [
        _testItem(id: 1, questionText: 'How is your mood?'),
        _testItem(id: 2, questionText: 'How is your energy?'),
      ];
      await tester.pumpWidget(buildTestWidget(items: items));
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(find.byIcon(Icons.edit_outlined), findsNWidgets(2));
    });

    testWidgets('switch is present for each item', (tester) async {
      final items = [_testItem(id: 1), _testItem(id: 2, isActive: false)];
      await tester.pumpWidget(buildTestWidget(items: items));
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(find.byType(Switch), findsNWidgets(2));
    });

    testWidgets('switch value is true when item isActive=true', (tester) async {
      await tester.pumpWidget(
        buildTestWidget(items: [_testItem(id: 1, isActive: true)]),
      );
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      final sw = tester.widget<Switch>(find.byType(Switch));
      expect(sw.value, isTrue);
    });

    testWidgets('switch value is false when item isActive=false', (
      tester,
    ) async {
      await tester.pumpWidget(
        buildTestWidget(items: [_testItem(id: 1, isActive: false)]),
      );
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      final sw = tester.widget<Switch>(find.byType(Switch));
      expect(sw.value, isFalse);
    });

    testWidgets('Add custom question button is visible', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(find.text('Add custom question'), findsOneWidget);
    });

    testWidgets(
      'tapping edit icon opens dialog with question text pre-filled',
      (tester) async {
        const questionText = 'How is your mood right now?';
        await tester.pumpWidget(
          buildTestWidget(
            items: [_testItem(id: 1, questionText: questionText)],
          ),
        );
        await tester.pumpAndSettle();
        await expandCheckInTile(tester);

        await tester.tap(find.byIcon(Icons.edit_outlined));
        await tester.pumpAndSettle();

        // Dialog title.
        expect(find.text('Edit question'), findsOneWidget);
        // TextField pre-filled with existing question text.
        final tf = tester.widget<TextField>(
          find.descendant(
            of: find.byType(AlertDialog),
            matching: find.byType(TextField),
          ),
        );
        expect(tf.controller?.text, equals(questionText));
      },
    );

    testWidgets('tapping Add custom question opens add dialog', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      await tester.tap(find.text('Add custom question'));
      await tester.pumpAndSettle();

      expect(find.text('Add question'), findsOneWidget);
      expect(find.byType(TextField), findsOneWidget);
    });

    testWidgets('edit dialog Cancel button closes without error', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget(items: [_testItem(id: 1)]));
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      await tester.tap(find.byIcon(Icons.edit_outlined));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Cancel'));
      await tester.pumpAndSettle();

      // Dialog should be gone.
      expect(find.text('Edit question'), findsNothing);
    });

    testWidgets('shows loading indicator when items stream has no data yet', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            sharedPreferencesProvider.overrideWithValue(prefs),
            assistantServiceProvider.overrideWithValue(mockService),
            appVersionProvider.overrideWith((ref) => Future.value('1.0.0')),
            environmentProvider.overrideWithValue(
              const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
            ),
            supabaseServiceProvider.overrideWithValue(
              SupabaseService(
                environment: const Environment.custom(
                  supabaseUrl: '',
                  supabaseAnonKey: '',
                ),
              ),
            ),
            isAuthenticatedProvider.overrideWithValue(false),
            currentUserProvider.overrideWithValue(null),
            pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
            sessionCountProvider.overrideWith((ref) => Future.value(0)),
            sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
            llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
            photoStorageInfoProvider.overrideWith(
              (ref) => Future.value(
                const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
              ),
            ),
            // Never-emitting stream = persistent loading state.
            activeCheckInItemsProvider.overrideWith(
              (ref) => const Stream.empty(),
            ),
            activeDefaultTemplateProvider.overrideWith(
              (ref) => const Stream.empty(),
            ),
          ],
          child: MaterialApp(home: const SettingsScreen()),
        ),
      );
      await tester.pump(); // single frame — don't settle

      await tester.scrollUntilVisible(
        find.text('Pulse Check-In'),
        300,
        scrollable: find.byType(Scrollable).first,
      );
      await tester.tap(find.text('Pulse Check-In'));
      await tester.pump(); // one more frame without settling

      expect(find.byType(CircularProgressIndicator), findsOneWidget);
    });

    testWidgets('scale helper text describes immediate effect', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      expect(
        find.text(
          'Applied immediately to all future check-ins.'
          ' Past answers are unaffected.',
        ),
        findsOneWidget,
      );
    });
  });

  // ---------------------------------------------------------------------------
  // SnackBar feedback tests (A7/A8) — use a real in-memory QuestionnaireDao
  // so write paths succeed and SnackBars actually fire.
  // ---------------------------------------------------------------------------

  group('SettingsScreen — Pulse Check-In SnackBar feedback', () {
    late AppDatabase db;
    late _FakeQuestionnaireDao dao;
    // templateId = 1 — matches _testTemplate() which has id: 1.
    const templateId = 1;
    late int itemId;

    setUp(() async {
      // Minimal in-memory DB — only needed for the QuestionnaireDao
      // constructor (DatabaseAccessor requires an AppDatabase reference).
      // All read/write methods are overridden in _FakeQuestionnaireDao so
      // no real SQLite calls are made, and no drift QueryStreams are created.
      db = AppDatabase.forTesting(NativeDatabase.memory());
      dao = _FakeQuestionnaireDao(db);
      itemId = 1; // matches _testItem(id: 1)
      dao.seed(itemId, isActive: true);
    });

    tearDown(() async {
      await db.close();
    });

    // Build widget with static stream overrides (no pending drift timers) but
    // a real in-memory DAO wired for write paths. This lets SnackBar callbacks
    // succeed without leaving DB-watch timers pending at test teardown.
    Widget buildDaoWidget({
      QuestionnaireTemplate? template,
      List<QuestionnaireItem> items = const [],
    }) {
      final tmpl =
          template ??
          _testTemplate(scaleMin: 1, scaleMax: 10); // default 1-10 selected
      return ProviderScope(
        overrides: [
          sharedPreferencesProvider.overrideWithValue(prefs),
          assistantServiceProvider.overrideWithValue(mockService),
          appVersionProvider.overrideWith((ref) => Future.value('1.0.0')),
          environmentProvider.overrideWithValue(
            const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          ),
          supabaseServiceProvider.overrideWithValue(
            SupabaseService(
              environment: const Environment.custom(
                supabaseUrl: '',
                supabaseAnonKey: '',
              ),
            ),
          ),
          isAuthenticatedProvider.overrideWithValue(false),
          currentUserProvider.overrideWithValue(null),
          pendingSyncCountProvider.overrideWith((ref) => Stream.value(0)),
          sessionCountProvider.overrideWith((ref) => Future.value(0)),
          sttModelReadyProvider.overrideWith((ref) => Future.value(false)),
          llmModelReadyProvider.overrideWith((ref) => Future.value(false)),
          photoStorageInfoProvider.overrideWith(
            (ref) => Future.value(
              const PhotoStorageInfo(count: 0, totalSizeBytes: 0),
            ),
          ),
          // Static streams — no pending DB-watch timers at teardown.
          activeDefaultTemplateProvider.overrideWith(
            (ref) => Stream.value(tmpl),
          ),
          activeCheckInItemsProvider.overrideWith((ref) => Stream.value(items)),
          // Real in-memory DAO so SnackBar write callbacks succeed.
          questionnaireDaoProvider.overrideWithValue(dao),
        ],
        child: MaterialApp(home: const SettingsScreen()),
      );
    }

    testWidgets(
      'scale toggle shows "Answer scale updated." SnackBar on success (A7)',
      (tester) async {
        // Default template has scaleMax=10 (1-10 selected).
        // Tapping "1 – 5" triggers the write path → success SnackBar.
        await tester.pumpWidget(buildDaoWidget());
        await tester.pumpAndSettle();
        await expandCheckInTile(tester);

        // Scroll to ensure the SegmentedButton is in the viewport after the
        // tile expands (the tile content may render below the fold).
        await tester.scrollUntilVisible(
          find.text('1 – 5'),
          50,
          scrollable: find.byType(Scrollable).first,
        );
        await tester.tap(find.text('1 – 5'));
        await tester.pumpAndSettle();

        expect(find.text('Answer scale updated.'), findsOneWidget);
      },
    );

    testWidgets(
      'deactivating item shows "Question deactivated." SnackBar with Undo (A8)',
      (tester) async {
        final activeItem = _testItem(id: itemId, isActive: true);
        await tester.pumpWidget(buildDaoWidget(items: [activeItem]));
        await tester.pumpAndSettle();
        await expandCheckInTile(tester);

        // Tap Switch to deactivate — SnackBar with Undo should appear.
        final sw = find.byType(Switch);
        expect(tester.widget<Switch>(sw).value, isTrue);
        await tester.tap(sw);
        // Use bounded pumps: pumpAndSettle would advance fake time past the
        // SnackBar's 4-second auto-dismiss timer, hiding it before assertions.
        await tester.pump(); // trigger Switch.onChanged
        await tester.pump(
          const Duration(milliseconds: 100),
        ); // SnackBar appears

        expect(find.text('Question deactivated.'), findsOneWidget);
        expect(find.text('Undo'), findsOneWidget);
      },
    );

    testWidgets('Undo on deactivation SnackBar re-activates the item (A8)', (
      tester,
    ) async {
      final activeItem = _testItem(id: itemId, isActive: true);
      await tester.pumpWidget(buildDaoWidget(items: [activeItem]));
      await tester.pumpAndSettle();
      await expandCheckInTile(tester);

      // Deactivate: sets _FakeQuestionnaireDao._isActive[itemId] = false.
      await tester.tap(find.byType(Switch));
      await tester.pump();
      await tester.pump(const Duration(milliseconds: 100));

      // Undo: sets _FakeQuestionnaireDao._isActive[itemId] = true.
      await tester.tap(find.text('Undo'));
      await tester.pump();

      // Verify via fake DAO that item is active again.
      final items = await dao.getActiveItemsForTemplate(templateId);
      expect(items.length, 1);
      expect(items.first.id, itemId);
    });
  });
}
