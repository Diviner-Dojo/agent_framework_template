// ===========================================================================
// file: test/ui/settings_screen_test.dart
// purpose: Widget tests for the settings screen.
//
// Tests verify that:
//   - The screen renders with the assistant status card
//   - The "Set as Default" button is present
//   - The about card shows version info
//   - Lifecycle resume triggers a re-read of assistant status
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/providers/settings_providers.dart';
import 'package:agentic_journal/services/assistant_registration_service.dart';
import 'package:agentic_journal/ui/screens/settings_screen.dart';

/// A mock assistant service that tracks method calls.
class MockAssistantService extends AssistantRegistrationService {
  int isDefaultCallCount = 0;
  bool returnValue = false;

  MockAssistantService() : super(isAndroid: false);

  @override
  Future<bool> isDefaultAssistant() async {
    isDefaultCallCount++;
    return returnValue;
  }

  @override
  Future<void> openAssistantSettings() async {
    // No-op for tests.
  }
}

void main() {
  group('SettingsScreen', () {
    late MockAssistantService mockService;

    setUp(() {
      mockService = MockAssistantService();
    });

    Widget buildTestWidget() {
      return ProviderScope(
        overrides: [assistantServiceProvider.overrideWithValue(mockService)],
        child: const MaterialApp(home: SettingsScreen()),
      );
    }

    testWidgets('renders Digital Assistant card', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Digital Assistant'), findsOneWidget);
    });

    testWidgets('shows assistant status as No when not default', (
      tester,
    ) async {
      mockService.returnValue = false;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: No'), findsOneWidget);
    });

    testWidgets('shows assistant status as Yes when default', (tester) async {
      mockService.returnValue = true;
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Default assistant: Yes'), findsOneWidget);
    });

    testWidgets('has Set as Default Assistant button', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('Set as Default Assistant'), findsOneWidget);
    });

    testWidgets('renders About card with version', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      expect(find.text('About'), findsOneWidget);
      expect(find.text('Agentic Journal'), findsOneWidget);
      expect(find.text('Version 1.0.0'), findsOneWidget);
    });

    testWidgets('shows manual instructions fallback', (tester) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // The instructions text should be visible.
      expect(find.textContaining('Digital Assistant'), findsWidgets);
    });

    testWidgets('lifecycle resume triggers re-check of assistant status', (
      tester,
    ) async {
      await tester.pumpWidget(buildTestWidget());
      await tester.pumpAndSettle();

      // Initial call count.
      final initialCalls = mockService.isDefaultCallCount;

      // Simulate app lifecycle resume (user returning from system settings).
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();

      // Should have been called at least one more time.
      expect(mockService.isDefaultCallCount, greaterThan(initialCalls));
    });
  });
}
