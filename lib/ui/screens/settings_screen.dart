// ===========================================================================
// file: lib/ui/screens/settings_screen.dart
// purpose: Settings screen with assistant registration status and app info.
//
// This screen shows:
//   1. A "Digital Assistant" card with the current registration status
//      and a button to open system settings where the user can change it.
//   2. A "Cloud Sync" card with auth state and sync controls (Phase 4).
//   3. An "About" card with app version info.
//
// Lifecycle Handling:
//   When the user goes to system settings and comes back, we need to
//   re-check the assistant status. We use WidgetsBindingObserver to
//   detect app lifecycle changes (specifically AppLifecycleState.resumed)
//   and invalidate the isDefaultAssistantProvider to trigger a re-check.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/auth_providers.dart';
import '../../providers/settings_providers.dart';
import '../../providers/sync_providers.dart';

/// Settings screen showing assistant status and app information.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen>
    with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    // Register as a lifecycle observer so we can re-check assistant status
    // when the user returns from system settings.
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    // When the app resumes (user comes back from system settings),
    // invalidate the assistant status provider to force a re-check.
    if (state == AppLifecycleState.resumed) {
      ref.invalidate(isDefaultAssistantProvider);
    }
  }

  @override
  Widget build(BuildContext context) {
    final assistantStatusAsync = ref.watch(isDefaultAssistantProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _buildAssistantCard(context, assistantStatusAsync),
          const SizedBox(height: 16),
          _buildCloudSyncCard(context),
          const SizedBox(height: 16),
          _buildAboutCard(context),
        ],
      ),
    );
  }

  /// Build the "Digital Assistant" settings card.
  Widget _buildAssistantCard(
    BuildContext context,
    AsyncValue<bool> statusAsync,
  ) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Digital Assistant',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 12),
            // Show the current status with a loading/error fallback.
            statusAsync.when(
              data: (isDefault) => Row(
                children: [
                  Icon(
                    isDefault ? Icons.check_circle : Icons.cancel,
                    color: isDefault ? Colors.green : Colors.orange,
                    size: 20,
                  ),
                  const SizedBox(width: 8),
                  Text(
                    isDefault
                        ? 'Default assistant: Yes'
                        : 'Default assistant: No',
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                ],
              ),
              loading: () => const Row(
                children: [
                  SizedBox(
                    width: 20,
                    height: 20,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 8),
                  Text('Checking status...'),
                ],
              ),
              error: (error, _) => Text(
                'Could not check status',
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ),
            const SizedBox(height: 12),
            // Button to open system settings.
            FilledButton.icon(
              onPressed: () async {
                final service = ref.read(assistantServiceProvider);
                await service.openAssistantSettings();
              },
              icon: const Icon(Icons.settings),
              label: const Text('Set as Default Assistant'),
            ),
            const SizedBox(height: 8),
            // Manual instructions as a fallback.
            Text(
              'Go to Settings \u2192 Apps \u2192 Default Apps \u2192 '
              'Digital Assistant \u2192 Select Agentic Journal',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build the "Cloud Sync" card showing auth state and sync controls.
  Widget _buildCloudSyncCard(BuildContext context) {
    final isAuthenticated = ref.watch(isAuthenticatedProvider);
    final currentUser = ref.watch(currentUserProvider);
    final pendingSyncAsync = ref.watch(pendingSyncCountProvider);
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Cloud Sync', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            if (!isAuthenticated) ...[
              Text(
                'Sign in to sync your journal to the cloud',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: () => Navigator.of(context).pushNamed('/auth'),
                icon: const Icon(Icons.cloud_upload_outlined),
                label: const Text('Sign In'),
              ),
            ] else ...[
              // Authenticated state
              Row(
                children: [
                  const Icon(Icons.check_circle, color: Colors.green, size: 20),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      currentUser?.email ?? 'Signed in',
                      style: theme.textTheme.bodyLarge,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),

              // Pending sync count
              pendingSyncAsync.when(
                data: (count) => count > 0
                    ? Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          '$count session${count == 1 ? '' : 's'} pending sync',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.primary,
                          ),
                        ),
                      )
                    : Padding(
                        padding: const EdgeInsets.only(bottom: 12),
                        child: Text(
                          'All sessions synced',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: Colors.green,
                          ),
                        ),
                      ),
                loading: () => const Padding(
                  padding: EdgeInsets.only(bottom: 12),
                  child: Text('Checking sync status...'),
                ),
                error: (_, _) => const SizedBox.shrink(),
              ),

              // Action buttons
              Row(
                children: [
                  // Sync Now button
                  FilledButton.icon(
                    onPressed: () async {
                      final syncRepo = ref.read(syncRepositoryProvider);
                      await syncRepo.syncPendingSessions();
                      // Invalidate to refresh the count
                      ref.invalidate(pendingSyncCountProvider);
                    },
                    icon: const Icon(Icons.sync),
                    label: const Text('Sync Now'),
                  ),
                  const SizedBox(width: 12),
                  // Sign out button
                  OutlinedButton(
                    onPressed: () async {
                      final service = ref.read(supabaseServiceProvider);
                      await service.signOut();
                    },
                    child: const Text('Sign Out'),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Build the "About" card with app information.
  Widget _buildAboutCard(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('About', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Agentic Journal',
              style: Theme.of(context).textTheme.bodyLarge,
            ),
            const SizedBox(height: 4),
            Text(
              'Version 1.0.0',
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'AI-powered personal journaling with offline-first architecture',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
