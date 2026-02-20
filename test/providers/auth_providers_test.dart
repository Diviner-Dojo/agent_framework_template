import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/providers/auth_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/services/supabase_service.dart';

void main() {
  group('Auth providers - unconfigured', () {
    late ProviderContainer container;

    setUp(() {
      final unconfiguredService = SupabaseService(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );

      container = ProviderContainer(
        overrides: [
          environmentProvider.overrideWithValue(
            const Environment.custom(supabaseUrl: '', supabaseAnonKey: ''),
          ),
          supabaseServiceProvider.overrideWithValue(unconfiguredService),
        ],
      );
    });

    tearDown(() {
      container.dispose();
    });

    test('supabaseServiceProvider returns unconfigured service', () {
      final service = container.read(supabaseServiceProvider);
      expect(service.isConfigured, false);
    });

    test('isAuthenticatedProvider returns false when unconfigured', () {
      final isAuth = container.read(isAuthenticatedProvider);
      expect(isAuth, false);
    });

    test('currentUserProvider returns null when unconfigured', () {
      final user = container.read(currentUserProvider);
      expect(user, isNull);
    });
  });

  group('Auth providers - overridden values', () {
    test('isAuthenticatedProvider can be overridden to true', () {
      final container = ProviderContainer(
        overrides: [isAuthenticatedProvider.overrideWithValue(true)],
      );

      expect(container.read(isAuthenticatedProvider), true);
      container.dispose();
    });

    test('isAuthenticatedProvider can be overridden to false', () {
      final container = ProviderContainer(
        overrides: [isAuthenticatedProvider.overrideWithValue(false)],
      );

      expect(container.read(isAuthenticatedProvider), false);
      container.dispose();
    });
  });
}
