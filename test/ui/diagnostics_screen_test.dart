import 'dart:async';

import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/app_logger.dart';
import 'package:agentic_journal/services/connectivity_service.dart';
import 'package:agentic_journal/ui/screens/diagnostics_screen.dart';

/// A ConnectivityService that always reports offline (no platform channel).
class _FakeConnectivityService extends ConnectivityService {
  _FakeConnectivityService()
    : super(
        connectivityStream:
            StreamController<List<ConnectivityResult>>.broadcast().stream,
      );

  @override
  bool get isOnline => false;
}

void main() {
  late SharedPreferences prefs;
  late ConnectivityService fakeConnectivity;

  setUp(() async {
    AppLogger.clear();
    SharedPreferences.setMockInitialValues({});
    prefs = await SharedPreferences.getInstance();
    fakeConnectivity = _FakeConnectivityService();
  });

  Widget buildTestWidget() {
    return ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        connectivityServiceProvider.overrideWithValue(fakeConnectivity),
        agentRepositoryProvider.overrideWithValue(AgentRepository()),
      ],
      child: const MaterialApp(home: DiagnosticsScreen()),
    );
  }

  group('DiagnosticsScreen', () {
    testWidgets('renders title and Run Diagnostics button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Developer Diagnostics'), findsOneWidget);
      expect(find.text('Run Diagnostics'), findsOneWidget);
    });

    testWidgets('shows log buffer section', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Log Buffer'), findsOneWidget);
      expect(find.text('Copy Log'), findsOneWidget);
    });

    testWidgets('shows empty log message when no entries', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(
        find.text('No log entries yet. Start using the app to see logs.'),
        findsOneWidget,
      );
    });

    testWidgets('shows log entries when present', (tester) async {
      AppLogger.i('test', 'Hello from test');
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.textContaining('test: Hello from test'), findsOneWidget);
    });

    testWidgets('Run Diagnostics shows result cards', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Run Diagnostics'));
      await tester.pumpAndSettle();

      // Results section should appear.
      expect(find.text('Results'), findsOneWidget);

      // Should show the first few check names (visible without scrolling).
      expect(find.text('Environment Config'), findsOneWidget);
      expect(find.text('Network Connectivity'), findsOneWidget);

      // Scroll down to see remaining results.
      final scrollable = find.byType(Scrollable).first;
      await tester.scrollUntilVisible(
        find.text('SharedPreferences'),
        200,
        scrollable: scrollable,
      );
      expect(find.text('SharedPreferences'), findsOneWidget);
    });

    testWidgets('Re-run button appears after running diagnostics', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Run Diagnostics'));
      await tester.pumpAndSettle();

      expect(find.text('Re-run Diagnostics'), findsOneWidget);
    });

    testWidgets('Copy Log copies to clipboard', (tester) async {
      AppLogger.i('test', 'clipboard test');

      // Track clipboard writes.
      String? clipboardData;
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(
        SystemChannels.platform,
        (MethodCall methodCall) async {
          if (methodCall.method == 'Clipboard.setData') {
            final args = methodCall.arguments as Map;
            clipboardData = args['text'] as String?;
          }
          return null;
        },
      );

      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Copy Log'));
      await tester.pumpAndSettle();

      expect(clipboardData, contains('clipboard test'));
      expect(find.text('Log copied to clipboard'), findsOneWidget);
    });
  });
}
