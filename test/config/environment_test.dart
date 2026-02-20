import 'package:flutter_test/flutter_test.dart';
import 'package:agentic_journal/config/environment.dart';

void main() {
  group('Environment', () {
    test('default constructor has empty values (no --dart-define)', () {
      const env = Environment();
      expect(env.isConfigured, isFalse);
    });

    test('isConfigured returns true when URL and anon key are set', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: 'test-key-123',
      );
      expect(env.isConfigured, isTrue);
    });

    test('isConfigured returns false when URL is empty', () {
      final env = Environment.custom(
        supabaseUrl: '',
        supabaseAnonKey: 'test-key-123',
      );
      expect(env.isConfigured, isFalse);
    });

    test('isConfigured returns false when anon key is empty', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: '',
      );
      expect(env.isConfigured, isFalse);
    });

    test('isSecure returns true for https URL', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: 'key',
      );
      expect(env.isSecure, isTrue);
    });

    test('isSecure returns false for http URL', () {
      final env = Environment.custom(
        supabaseUrl: 'http://abc.supabase.co',
        supabaseAnonKey: 'key',
      );
      expect(env.isSecure, isFalse);
    });

    test('isSecure returns true for empty URL (not configured)', () {
      final env = Environment.custom(supabaseUrl: '', supabaseAnonKey: '');
      // Empty URL is "secure" because it's not configured — no insecure call possible.
      expect(env.isSecure, isTrue);
    });

    test('claudeProxyUrl builds correct Edge Function URL', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: 'key',
      );
      expect(
        env.claudeProxyUrl,
        'https://abc.supabase.co/functions/v1/claude-proxy',
      );
    });

    test('claudeProxyTimeout defaults to 30 seconds', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: 'key',
      );
      expect(env.claudeProxyTimeout, const Duration(seconds: 30));
    });

    test('claudeProxyTimeout can be customized', () {
      final env = Environment.custom(
        supabaseUrl: 'https://abc.supabase.co',
        supabaseAnonKey: 'key',
        claudeProxyTimeoutSeconds: 60,
      );
      expect(env.claudeProxyTimeout, const Duration(seconds: 60));
    });
  });
}
