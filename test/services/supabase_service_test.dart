import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/config/environment.dart';
import 'package:agentic_journal/services/supabase_service.dart';

void main() {
  group('SupabaseService - unconfigured', () {
    late SupabaseService service;

    setUp(() {
      // Unconfigured environment — no Supabase URL or anon key.
      service = SupabaseService(
        environment: const Environment.custom(
          supabaseUrl: '',
          supabaseAnonKey: '',
        ),
      );
    });

    test('isConfigured returns false when environment is empty', () {
      expect(service.isConfigured, false);
    });

    test('signUp returns null when not configured', () async {
      final result = await service.signUp(
        email: 'test@example.com',
        password: 'password123',
      );
      expect(result, isNull);
    });

    test('signIn returns null when not configured', () async {
      final result = await service.signIn(
        email: 'test@example.com',
        password: 'password123',
      );
      expect(result, isNull);
    });

    test('signOut is a no-op when not configured', () async {
      // Should not throw.
      await service.signOut();
    });

    test('currentUser returns null when not configured', () {
      expect(service.currentUser, isNull);
    });

    test('isAuthenticated returns false when not configured', () {
      expect(service.isAuthenticated, false);
    });

    test('onAuthStateChange returns empty stream when not configured', () {
      final stream = service.onAuthStateChange;
      expectLater(stream, emitsDone);
    });

    test('accessToken returns null when not configured', () {
      expect(service.accessToken, isNull);
    });

    test('client returns null when not configured', () {
      expect(service.client, isNull);
    });
  });

  group('SupabaseService - configured environment', () {
    late SupabaseService service;

    setUp(() {
      // Configured environment — has URL and anon key.
      // Note: We can't test actual Supabase calls without the initialized
      // client, but we can verify the service correctly reports isConfigured.
      service = SupabaseService(
        environment: const Environment.custom(
          supabaseUrl: 'https://test.supabase.co',
          supabaseAnonKey: 'test-anon-key',
        ),
      );
    });

    test('isConfigured returns true with valid environment', () {
      expect(service.isConfigured, true);
    });
  });
}
