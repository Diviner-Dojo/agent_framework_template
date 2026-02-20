import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/auth_screen.dart';

void main() {
  /// Build the auth screen in a test environment.
  Widget buildTestApp({SupabaseService? supabaseService}) {
    final unconfiguredService = SupabaseService(
      environment: const Environment.custom(
        supabaseUrl: '',
        supabaseAnonKey: '',
      ),
    );

    return ProviderScope(
      overrides: [
        environmentProvider.overrideWithValue(
          const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
        ),
        supabaseServiceProvider.overrideWithValue(
          supabaseService ?? unconfiguredService,
        ),
      ],
      child: MaterialApp(
        home: const AuthScreen(),
        routes: {'/settings': (context) => const Scaffold()},
      ),
    );
  }

  group('AuthScreen', () {
    testWidgets('renders sign in form by default', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      expect(find.text('Sign In'), findsWidgets); // title + button
      expect(find.text('Email'), findsOneWidget);
      expect(find.text('Password'), findsOneWidget);
      expect(find.text('Skip'), findsOneWidget);
    });

    testWidgets('toggles to sign up mode', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Find and tap the toggle button
      await tester.tap(find.text("Don't have an account? Create one"));
      await tester.pumpAndSettle();

      expect(find.text('Create Account'), findsWidgets);
      expect(find.text('Already have an account? Sign in'), findsOneWidget);
    });

    testWidgets('validates empty email', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Tap sign in without entering anything
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(find.text('Email is required'), findsOneWidget);
    });

    testWidgets('validates invalid email format', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).first, 'notanemail');
      await tester.enterText(find.byType(TextFormField).last, 'password123');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(find.text('Enter a valid email address'), findsOneWidget);
    });

    testWidgets('validates empty password', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField).first,
        'test@example.com',
      );
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(find.text('Password is required'), findsOneWidget);
    });

    testWidgets('validates short password in sign up mode', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Switch to sign up mode
      await tester.tap(find.text("Don't have an account? Create one"));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField).first,
        'test@example.com',
      );
      await tester.enterText(find.byType(TextFormField).last, '12345');
      await tester.tap(find.widgetWithText(FilledButton, 'Create Account'));
      await tester.pumpAndSettle();

      expect(
        find.text('Password must be at least 6 characters'),
        findsOneWidget,
      );
    });

    testWidgets('skip button pops the screen', (tester) async {
      var popped = false;
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
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
          ],
          child: MaterialApp(
            home: Builder(
              builder: (context) => Scaffold(
                body: ElevatedButton(
                  onPressed: () async {
                    await Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => const AuthScreen()),
                    );
                    popped = true;
                  },
                  child: const Text('Go to Auth'),
                ),
              ),
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      // Navigate to auth screen
      await tester.tap(find.text('Go to Auth'));
      await tester.pumpAndSettle();

      // Tap skip
      await tester.tap(find.text('Skip'));
      await tester.pumpAndSettle();

      expect(popped, true);
    });

    testWidgets('shows Cloud Sync header text', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      expect(find.text('Cloud Sync'), findsOneWidget);
      expect(
        find.textContaining('Sign in to sync your journal entries'),
        findsOneWidget,
      );
    });
  });
}
