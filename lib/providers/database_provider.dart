// ===========================================================================
// file: lib/providers/database_provider.dart
// purpose: Riverpod provider for the singleton AppDatabase instance.
//
// Why a provider instead of a global variable?
//   1. Testability: Tests can override this provider with an in-memory DB.
//   2. Lifecycle: Riverpod manages creation/disposal automatically.
//   3. Dependency injection: Other providers declare their dependency on this,
//      making the dependency graph explicit and inspectable.
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../database/app_database.dart';
import '../database/daos/session_dao.dart';
import '../database/daos/message_dao.dart';

/// Provides the singleton AppDatabase instance.
///
/// This is created once when first accessed and lives for the entire app
/// lifetime. All DAOs and providers that need database access read from this.
///
/// In tests, override this provider:
///   final container = ProviderContainer(
///     overrides: [
///       databaseProvider.overrideWithValue(
///         AppDatabase.forTesting(NativeDatabase.memory()),
///       ),
///     ],
///   );
final databaseProvider = Provider<AppDatabase>((ref) {
  final db = AppDatabase();
  // Ensure the database is closed when the provider is disposed.
  // This happens when the app is terminated.
  ref.onDispose(() => db.close());
  return db;
});

/// Provides a SessionDao backed by the singleton database.
///
/// Any provider that needs to read/write sessions should depend on this
/// rather than creating its own SessionDao instance.
final sessionDaoProvider = Provider<SessionDao>((ref) {
  return SessionDao(ref.watch(databaseProvider));
});

/// Provides a MessageDao backed by the singleton database.
///
/// Any provider that needs to read/write messages should depend on this
/// rather than creating its own MessageDao instance.
final messageDaoProvider = Provider<MessageDao>((ref) {
  return MessageDao(ref.watch(databaseProvider));
});
