// ===========================================================================
// file: lib/providers/sync_providers.dart
// purpose: Riverpod providers for sync state and operations.
//
// These providers wire up the SyncRepository and expose reactive state
// for the sync UI (pending count, sync trigger).
//
// See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
// ===========================================================================

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../repositories/sync_repository.dart';
import 'auth_providers.dart';
import 'database_provider.dart';

/// Provides the SyncRepository for uploading data to Supabase.
///
/// Depends on SupabaseService (auth + client), SessionDao, and MessageDao.
final syncRepositoryProvider = Provider<SyncRepository>((ref) {
  final supabaseService = ref.watch(supabaseServiceProvider);
  final sessionDao = ref.watch(sessionDaoProvider);
  final messageDao = ref.watch(messageDaoProvider);
  return SyncRepository(
    supabaseService: supabaseService,
    sessionDao: sessionDao,
    messageDao: messageDao,
  );
});

/// Streams the count of sessions that need syncing.
///
/// Used by the Settings Cloud Sync card to show how many sessions
/// are pending upload. Returns 0 when not authenticated.
final pendingSyncCountProvider = StreamProvider<int>((ref) {
  final isAuthenticated = ref.watch(isAuthenticatedProvider);
  if (!isAuthenticated) return Stream.value(0);

  final sessionDao = ref.watch(sessionDaoProvider);
  return sessionDao.watchPendingSyncCount();
});
