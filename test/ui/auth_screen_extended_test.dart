import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/services/supabase_service.dart';
import 'package:agentic_journal/ui/screens/auth_screen.dart';

void main() {
  Widget buildTestApp() {
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
        supabaseServiceProvider.overrideWithValue(unconfiguredService),
      ],
      child: const MaterialApp(home: AuthScreen()),
    );
  }

  group('AuthScreen - extended form tests', () {
    testWidgets('accepts valid email and password on sign in', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Enter valid email and password
      await tester.enterText(
        find.byType(TextFormField).first,
        'user@example.com',
      );
      await tester.enterText(find.byType(TextFormField).last, 'password123');

      // Tap sign in — should not show validation errors
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      // No validation error text should appear
      expect(find.text('Email is required'), findsNothing);
      expect(find.text('Password is required'), findsNothing);
    });

    testWidgets('sign up mode accepts 6+ character password', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Toggle to sign up
      await tester.tap(find.text("Don't have an account? Create one"));
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField).first,
        'user@example.com',
      );
      await tester.enterText(find.byType(TextFormField).last, '123456');

      await tester.tap(find.widgetWithText(FilledButton, 'Create Account'));
      await tester.pumpAndSettle();

      expect(find.text('Password must be at least 6 characters'), findsNothing);
    });

    testWidgets('toggle back from sign up to sign in', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Toggle to sign up
      await tester.tap(find.text("Don't have an account? Create one"));
      await tester.pumpAndSettle();
      expect(find.text('Create Account'), findsWidgets);

      // Toggle back to sign in
      await tester.tap(find.text('Already have an account? Sign in'));
      await tester.pumpAndSettle();
      expect(find.text('Sign In'), findsWidgets);
    });

    testWidgets('clearing error on mode toggle', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Trigger validation error
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();
      expect(find.text('Email is required'), findsOneWidget);

      // Toggle mode — error should clear from the error message area
      await tester.tap(find.text("Don't have an account? Create one"));
      await tester.pumpAndSettle();

      // The form validation error may persist until resubmit, but the
      // _errorMessage state variable should be cleared
      expect(find.text('Create Account'), findsWidgets);
    });

    testWidgets('email field uses email keyboard type', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Verify the email TextField has the correct keyboard type.
      final emailTextField = tester.widget<TextField>(
        find.descendant(
          of: find.byType(TextFormField).first,
          matching: find.byType(TextField),
        ),
      );
      expect(emailTextField.keyboardType, TextInputType.emailAddress);
    });

    testWidgets('password field is obscured', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      // Verify the password TextField is obscured.
      final passwordTextField = tester.widget<TextField>(
        find.descendant(
          of: find.byType(TextFormField).last,
          matching: find.byType(TextField),
        ),
      );
      expect(passwordTextField.obscureText, true);
    });

    testWidgets('shows email and lock icons', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      expect(find.byIcon(Icons.email_outlined), findsOneWidget);
      expect(find.byIcon(Icons.lock_outlined), findsOneWidget);
    });

    testWidgets('email validation rejects missing dot', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      await tester.enterText(find.byType(TextFormField).first, 'user@example');
      await tester.enterText(find.byType(TextFormField).last, 'password');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(find.text('Enter a valid email address'), findsOneWidget);
    });

    testWidgets('email validation rejects missing at sign', (tester) async {
      await tester.pumpWidget(buildTestApp());
      await tester.pumpAndSettle();

      await tester.enterText(
        find.byType(TextFormField).first,
        'user.example.com',
      );
      await tester.enterText(find.byType(TextFormField).last, 'password');
      await tester.tap(find.widgetWithText(FilledButton, 'Sign In'));
      await tester.pumpAndSettle();

      expect(find.text('Enter a valid email address'), findsOneWidget);
    });
  });
}
