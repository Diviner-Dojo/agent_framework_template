// ===========================================================================
// file: test/helpers/test_providers.dart
// purpose: Shared test infrastructure for Riverpod provider tests.
//
// Provides reusable fakes, mock factories, and ProviderContainer builders
// to reduce boilerplate across test files.
//
// Usage:
//   import '../helpers/test_providers.dart';
//
//   final container = createTestContainer();
//   // ... use container in tests ...
//   container.dispose();
// ===========================================================================

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/database/app_database.dart';
import 'package:agentic_journal/providers/calendar_providers.dart';
import 'package:agentic_journal/providers/database_provider.dart';
import 'package:agentic_journal/providers/onboarding_providers.dart';
import 'package:agentic_journal/providers/session_providers.dart';
import 'package:agentic_journal/repositories/agent_repository.dart';
import 'package:agentic_journal/services/connectivity_service.dart';
import 'package:agentic_journal/services/google_auth_service.dart';

/// Create an in-memory [AppDatabase] for tests.
///
/// Each call returns a fresh database instance with all migrations applied.
/// The caller is responsible for calling [AppDatabase.close] in tearDown.
AppDatabase createTestDatabase() {
  return AppDatabase.forTesting(NativeDatabase.memory());
}

/// Create a [ProviderContainer] with standard test overrides.
///
/// Overrides:
///   - [databaseProvider] → in-memory database
///   - [agentRepositoryProvider] → Layer A only (no services)
///   - [connectivityServiceProvider] → offline by default
///   - [sharedPreferencesProvider] → mock initial values
///   - [googleAuthServiceProvider] → fake (no platform channels)
///   - [isGoogleConnectedProvider] → starts disconnected
///
/// Additional overrides can be passed via [extraOverrides].
Future<({ProviderContainer container, AppDatabase database})>
createTestContainer({
  List<Override> extraOverrides = const [],
  GoogleAuthService? googleAuthService,
  bool isGoogleConnected = false,
}) async {
  SharedPreferences.setMockInitialValues({});
  final prefs = await SharedPreferences.getInstance();
  final database = createTestDatabase();

  final container = ProviderContainer(
    overrides: [
      databaseProvider.overrideWithValue(database),
      agentRepositoryProvider.overrideWithValue(AgentRepository()),
      connectivityServiceProvider.overrideWithValue(ConnectivityService()),
      sharedPreferencesProvider.overrideWithValue(prefs),
      deviceTimezoneProvider.overrideWith((ref) async => 'America/New_York'),
      googleAuthServiceProvider.overrideWithValue(
        googleAuthService ?? fakeGoogleAuthService(),
      ),
      isGoogleConnectedProvider.overrideWith(
        (ref) => FakeGoogleConnectionNotifier(isGoogleConnected),
      ),
      ...extraOverrides,
    ],
  );

  return (container: container, database: database);
}

/// Create a fake [GoogleAuthService] with injectable callables.
///
/// All operations default to no-op. Pass specific callables to test
/// individual sign-in/sign-out flows.
GoogleAuthService fakeGoogleAuthService({
  GoogleSignInFn? signIn,
  GoogleSignOutFn? signOut,
  GoogleDisconnectFn? disconnect,
  GoogleIsSignedInFn? isSignedIn,
  GoogleAuthClientFn? getAuthClient,
  GoogleSignInSilentlyFn? signInSilently,
}) {
  return GoogleAuthService(
    signIn: signIn ?? () async => null,
    signOut: signOut ?? () async => null,
    disconnect: disconnect ?? () async => null,
    isSignedIn: isSignedIn ?? () async => false,
    getAuthClient: getAuthClient ?? () async => null,
    signInSilently: signInSilently ?? () async => null,
  );
}

/// A fake [GoogleConnectionNotifier] that allows controlling state in tests.
class FakeGoogleConnectionNotifier extends GoogleConnectionNotifier {
  FakeGoogleConnectionNotifier(bool initialState)
    : super(fakeGoogleAuthService()) {
    state = initialState;
  }

  /// Manually set the connection state for testing.
  void setConnected(bool connected) {
    state = connected;
  }
}

/// A fake [GoogleSignInAccount] for testing.
class FakeGoogleSignInAccount implements GoogleSignInAccount {
  @override
  String get displayName => 'Test User';
  @override
  String get email => 'test@example.com';
  @override
  String get id => 'test-id';
  @override
  String? get photoUrl => null;
  @override
  String? get serverAuthCode => null;
  @override
  Future<GoogleSignInAuthentication> get authentication =>
      throw UnimplementedError();
  @override
  Future<Map<String, String>> get authHeaders => throw UnimplementedError();
  @override
  Future<void> clearAuthCache() => Future.value();
}
