// ===========================================================================
// file: integration_test/smoke_test.dart
// purpose: On-device smoke tests that verify all critical features survived
//          the build. Launches the real app (no mocks) on a physical device.
//
// Run: flutter test integration_test/smoke_test.dart -d <device-id>
//
// All checks run in a single testWidgets because integration tests tear down
// the widget tree between testWidgets calls. Since we bootstrap the real app
// once, all assertions must live in one continuous test.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

import 'package:agentic_journal/main.dart' as app;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('smoke test: all critical features present', (tester) async {
    // =======================================================================
    // 1. App launches without crashing
    // =======================================================================
    app.main();
    await tester.pumpAndSettle(const Duration(seconds: 10));

    // First launch shows onboarding. Complete it so we can access the main app.
    final skipButton = find.text('Skip');
    if (skipButton.evaluate().isNotEmpty) {
      await tester.tap(skipButton);
      await tester.pumpAndSettle(const Duration(seconds: 10));
    }

    // After onboarding's "Skip", we land on the journal session screen
    // (onboarding auto-starts a session). End it to get to the session list.
    if (find.text('Journal Entry').evaluate().isNotEmpty) {
      final backButton = find.byIcon(Icons.arrow_back);
      if (backButton.evaluate().isNotEmpty) {
        await tester.tap(backButton);
        await tester.pumpAndSettle();

        // Tap "End" in the confirmation dialog.
        final endButton = find.text('End');
        if (endButton.evaluate().isNotEmpty) {
          await tester.tap(endButton);
          await tester.pumpAndSettle(const Duration(seconds: 10));
        }

        // If a "Done" button appears (closing summary), tap it.
        final doneButton = find.text('Done');
        if (doneButton.evaluate().isNotEmpty) {
          await tester.tap(doneButton);
          await tester.pumpAndSettle();
        }
      }
    }

    // Now we should be on the session list screen.
    expect(find.text('Agentic Journal'), findsOneWidget);

    // =======================================================================
    // 2. Settings screen: all cards present
    // =======================================================================
    // Navigate to settings via the gear icon.
    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();

    expect(find.text('Settings'), findsOneWidget);

    final scrollable = find.byType(Scrollable).first;

    for (final title in [
      'Digital Assistant',
      'Voice',
      'Conversation AI',
      'Cloud Sync',
      'Location',
      'Calendar',
      'Data Management',
      'About',
    ]) {
      await tester.scrollUntilVisible(
        find.text(title),
        200,
        scrollable: scrollable,
      );
      expect(find.text(title), findsOneWidget, reason: '$title card missing');
    }

    // =======================================================================
    // 3. Settings: Local AI status row exists
    // =======================================================================
    // Scroll back up to see the Conversation AI card.
    await tester.scrollUntilVisible(
      find.text('Conversation AI'),
      -500,
      scrollable: scrollable,
    );
    await tester.pumpAndSettle();

    final localAiReady = find.text('Local AI: Ready');
    final localAiNotDownloaded = find.text('Local AI: Not downloaded');
    expect(
      localAiReady.evaluate().isNotEmpty ||
          localAiNotDownloaded.evaluate().isNotEmpty,
      isTrue,
      reason: 'Expected "Local AI: Ready" or "Local AI: Not downloaded"',
    );

    // =======================================================================
    // 4. Settings: Google Calendar section exists
    // =======================================================================
    await tester.scrollUntilVisible(
      find.text('Calendar'),
      200,
      scrollable: scrollable,
    );
    await tester.pumpAndSettle();

    final connectButton = find.text('Connect Google Calendar');
    final calendarConnected = find.text('Google Calendar: Connected');
    expect(
      connectButton.evaluate().isNotEmpty ||
          calendarConnected.evaluate().isNotEmpty,
      isTrue,
      reason: 'Expected calendar connect button or connected status',
    );

    // =======================================================================
    // 5. Settings: Cloud Sync sign-in navigates to auth
    // =======================================================================
    await tester.scrollUntilVisible(
      find.text('Cloud Sync'),
      -500,
      scrollable: scrollable,
    );
    await tester.pumpAndSettle();

    final signInButton = find.text('Sign In');
    // Only test auth flow if not already signed in.
    if (signInButton.evaluate().isNotEmpty) {
      await tester.tap(signInButton);
      await tester.pumpAndSettle();

      // Verify the auth screen loaded.
      expect(find.text('Cloud Sync'), findsOneWidget);
      expect(find.text('Email'), findsOneWidget);

      // ===================================================================
      // 6. Auth screen: shows config error
      // ===================================================================
      final emailField = find.byType(TextFormField).first;
      await tester.enterText(emailField, 'test@example.com');

      final passwordField = find.byType(TextFormField).last;
      await tester.enterText(passwordField, 'password123');
      await tester.pumpAndSettle();

      // Tap the Sign In submit button.
      final submitButton = find.widgetWithText(FilledButton, 'Sign In');
      await tester.tap(submitButton);
      await tester.pumpAndSettle(const Duration(seconds: 5));

      // Verify the "not configured" error appears.
      expect(
        find.textContaining('Cloud sync is not configured'),
        findsOneWidget,
        reason: 'Expected Supabase not-configured error message',
      );

      // Navigate back to settings.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();
    }

    // Navigate back to session list.
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();

    // =======================================================================
    // 7. Journal session: start, send, receive
    // =======================================================================
    expect(find.text('Agentic Journal'), findsOneWidget);

    final fab = find.byType(FloatingActionButton);
    expect(fab, findsOneWidget);
    await tester.tap(fab);
    await tester.pumpAndSettle(const Duration(seconds: 5));

    // Should now be on the journal session screen.
    expect(find.text('Journal Entry'), findsOneWidget);

    // =======================================================================
    // 7b. Layer indicator chip is visible
    // =======================================================================
    final claudeChip = find.text('Claude');
    final offlineChip = find.text('Offline');
    final localLlmChip = find.text('Local LLM');
    expect(
      claudeChip.evaluate().isNotEmpty ||
          offlineChip.evaluate().isNotEmpty ||
          localLlmChip.evaluate().isNotEmpty,
      isTrue,
      reason:
          'Expected layer indicator chip ("Claude", "Offline", or "Local LLM")',
    );

    // Type a message.
    final textField = find.byType(TextField);
    expect(textField, findsOneWidget);
    await tester.enterText(textField, 'Hello, this is a smoke test.');
    await tester.pumpAndSettle();

    // Tap the send button.
    await tester.tap(find.byIcon(Icons.send));
    await tester.pumpAndSettle(const Duration(seconds: 15));

    // Verify the user's message appears.
    expect(
      find.textContaining('Hello, this is a smoke test.'),
      findsOneWidget,
      reason: 'User message should appear in the chat',
    );

    // =======================================================================
    // 8. Session persists after end
    // =======================================================================
    // End the session via the overflow menu.
    await tester.tap(find.byIcon(Icons.more_vert));
    await tester.pumpAndSettle();

    await tester.tap(find.text('End Session'));
    await tester.pumpAndSettle(const Duration(seconds: 10));

    // Wait for closing summary, then tap Done.
    final doneButton = find.text('Done');
    if (doneButton.evaluate().isNotEmpty) {
      await tester.tap(doneButton);
      await tester.pumpAndSettle();
    } else {
      // If no Done button, just go back.
      await tester.tap(find.byIcon(Icons.arrow_back));
      await tester.pumpAndSettle();
    }

    // Verify we're back on the session list and it's not empty.
    expect(find.text('Agentic Journal'), findsOneWidget);
    expect(
      find.text('No journal sessions yet').evaluate().isEmpty,
      isTrue,
      reason: 'Session list should not be empty after ending a session',
    );

    // =======================================================================
    // 9. Developer Diagnostics screen
    // =======================================================================
    await tester.tap(find.byIcon(Icons.settings));
    await tester.pumpAndSettle();

    final settingsScrollable = find.byType(Scrollable).first;

    // Scroll to the Developer Diagnostics entry in the About section.
    await tester.scrollUntilVisible(
      find.text('Developer Diagnostics'),
      200,
      scrollable: settingsScrollable,
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Developer Diagnostics'));
    await tester.pumpAndSettle();

    // Verify we're on the diagnostics screen.
    expect(find.text('Developer Diagnostics'), findsOneWidget);
    expect(find.text('Run Diagnostics'), findsOneWidget);

    // Run diagnostics.
    await tester.tap(find.text('Run Diagnostics'));
    await tester.pumpAndSettle(const Duration(seconds: 15));

    // Verify result cards appeared (check for at least one known check name).
    expect(
      find.text('Environment Config'),
      findsOneWidget,
      reason: 'Expected Environment Config result card',
    );

    // Navigate back to settings, then session list.
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.arrow_back));
    await tester.pumpAndSettle();
  });
}
