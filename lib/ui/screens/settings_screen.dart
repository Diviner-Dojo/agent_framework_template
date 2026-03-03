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
import 'package:geolocator/geolocator.dart';
import 'package:path_provider/path_provider.dart';

import 'dart:convert';
import 'dart:io';

import 'package:drift/drift.dart' show Value;

import '../../database/app_database.dart'
    show QuestionnaireItem, QuestionnaireItemsCompanion;
import '../../models/personality_config.dart';
import '../../providers/auth_providers.dart';
import '../../services/google_auth_service.dart';
import '../../providers/database_provider.dart';
import '../../providers/llm_providers.dart';
import '../../providers/personality_providers.dart';
import '../../providers/photo_providers.dart';
import '../../providers/search_providers.dart';
import '../../providers/calendar_providers.dart';
import '../../providers/location_providers.dart';
import '../../providers/questionnaire_providers.dart';
import '../../providers/settings_providers.dart';
import '../../providers/sync_providers.dart';
import '../../providers/task_providers.dart';
import '../../repositories/sync_repository.dart';
import '../../providers/voice_providers.dart';
import '../widgets/llm_model_download_dialog.dart';
import 'diagnostics_screen.dart';

/// Settings screen showing assistant status and app information.
class SettingsScreen extends ConsumerStatefulWidget {
  const SettingsScreen({super.key});

  @override
  ConsumerState<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends ConsumerState<SettingsScreen>
    with WidgetsBindingObserver {
  bool _isClearingLocation = false;
  bool _isSyncing = false;
  bool _isExporting = false;

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
          _buildVoiceCard(context),
          const SizedBox(height: 16),
          _buildAiAssistantCard(context),
          const SizedBox(height: 16),
          _buildCloudSyncCard(context),
          const SizedBox(height: 16),
          _buildLocationCard(context),
          const SizedBox(height: 16),
          _buildCalendarCard(context),
          const SizedBox(height: 16),
          _buildPulseCheckInCard(context),
          const SizedBox(height: 16),
          _buildDataManagementCard(context),
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

  /// Build the "Voice" settings card with toggle, engine selection, and model status.
  Widget _buildVoiceCard(BuildContext context) {
    final voiceEnabled = ref.watch(voiceModeEnabledProvider);
    final autoSave = ref.watch(autoSaveOnExitProvider);
    final modelReadyAsync = ref.watch(sttModelReadyProvider);
    final ttsEngine = ref.watch(ttsEngineProvider);
    final sttEngine = ref.watch(sttEngineProvider);
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Voice', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            SwitchListTile(
              title: const Text('Enable voice mode'),
              subtitle: const Text(
                'Adds mic button; long-press for continuous mode',
              ),
              value: voiceEnabled,
              onChanged: (value) {
                ref.read(voiceModeEnabledProvider.notifier).setEnabled(value);
              },
              contentPadding: EdgeInsets.zero,
            ),
            if (voiceEnabled) ...[
              SwitchListTile(
                title: const Text('Auto-save on exit'),
                subtitle: const Text('Save session when app is backgrounded'),
                value: autoSave,
                onChanged: (value) {
                  ref.read(autoSaveOnExitProvider.notifier).setEnabled(value);
                },
                contentPadding: EdgeInsets.zero,
              ),
              const SizedBox(height: 8),
              // TTS engine selector.
              DropdownButtonFormField<TtsEngine>(
                initialValue: ttsEngine,
                decoration: const InputDecoration(
                  labelText: 'Text-to-speech engine',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                items: const [
                  DropdownMenuItem(
                    value: TtsEngine.elevenlabs,
                    child: Text('Natural (ElevenLabs)'),
                  ),
                  DropdownMenuItem(
                    value: TtsEngine.flutterTts,
                    child: Text('Basic (Offline)'),
                  ),
                ],
                onChanged: (engine) {
                  if (engine != null) {
                    ref.read(ttsEngineProvider.notifier).setEngine(engine);
                  }
                },
              ),
              const SizedBox(height: 12),
              // TTS playback speed slider (applies to all TTS engines).
              Builder(
                builder: (context) {
                  final ttsRate = ref.watch(ttsRateProvider);
                  return Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Playback speed: ${ttsRate.toStringAsFixed(2)}x',
                        style: theme.textTheme.bodyMedium,
                      ),
                      Slider(
                        value: ttsRate,
                        min: 0.5,
                        max: 1.5,
                        divisions: 20,
                        label: '${ttsRate.toStringAsFixed(2)}x',
                        onChanged: (value) {
                          ref.read(ttsRateProvider.notifier).setRate(value);
                        },
                      ),
                    ],
                  );
                },
              ),
              const SizedBox(height: 4),
              // STT engine selector.
              DropdownButtonFormField<SttEngine>(
                initialValue: sttEngine,
                decoration: const InputDecoration(
                  labelText: 'Speech recognition engine',
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
                items: const [
                  DropdownMenuItem(
                    value: SttEngine.speechToText,
                    child: Text('Google (No download)'),
                  ),
                  DropdownMenuItem(
                    value: SttEngine.sherpaOnnx,
                    child: Text('Offline (71MB model)'),
                  ),
                ],
                onChanged: (engine) {
                  if (engine != null) {
                    ref.read(sttEngineProvider.notifier).setEngine(engine);
                  }
                },
              ),
            ],
            const SizedBox(height: 8),
            // STT model download status (only relevant for sherpa_onnx).
            if (sttEngine == SttEngine.sherpaOnnx)
              modelReadyAsync.when(
                data: (isReady) => Row(
                  children: [
                    Icon(
                      isReady ? Icons.check_circle : Icons.download,
                      color: isReady ? Colors.green : theme.colorScheme.primary,
                      size: 20,
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        isReady
                            ? 'Speech model: Downloaded'
                            : 'Speech model: Not downloaded',
                        style: theme.textTheme.bodyMedium,
                      ),
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
                    Text('Checking model status...'),
                  ],
                ),
                error: (_, _) => Text(
                  'Could not check model status',
                  style: TextStyle(color: theme.colorScheme.error),
                ),
              ),
            if (voiceEnabled &&
                sttEngine == SttEngine.sherpaOnnx &&
                modelReadyAsync.valueOrNull != true) ...[
              const SizedBox(height: 8),
              Text(
                'The speech model will be downloaded when you first use voice input.',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  /// Build the "AI Assistant" settings card with layer preferences.
  Widget _buildAiAssistantCard(BuildContext context) {
    final preferClaude = ref.watch(preferClaudeProvider);
    final journalOnly = ref.watch(journalOnlyModeProvider);
    final llmModelReadyAsync = ref.watch(llmModelReadyProvider);
    final personality = ref.watch(personalityConfigProvider);
    final theme = Theme.of(context);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Conversation AI', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            SwitchListTile(
              title: const Text('Prefer Claude when online'),
              subtitle: Text(
                journalOnly
                    ? 'Disabled while Journal only mode is on'
                    : 'Use Claude API for richer conversations when available',
              ),
              value: preferClaude,
              onChanged: journalOnly
                  ? null
                  : (value) {
                      ref.read(preferClaudeProvider.notifier).setEnabled(value);
                    },
              contentPadding: EdgeInsets.zero,
            ),
            SwitchListTile(
              title: const Text('Journal only mode'),
              subtitle: const Text(
                'Skip greetings and follow-ups — just capture your thoughts',
              ),
              value: journalOnly,
              onChanged: (value) {
                ref.read(journalOnlyModeProvider.notifier).setEnabled(value);
              },
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 8),
            // LLM model status.
            llmModelReadyAsync.when(
              data: (isReady) => Row(
                children: [
                  ExcludeSemantics(
                    child: Icon(
                      isReady ? Icons.check_circle : Icons.smart_toy_outlined,
                      color: isReady
                          ? Colors.green
                          : theme.colorScheme.onSurfaceVariant,
                      size: 20,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      isReady ? 'Local AI: Ready' : 'Local AI: Not downloaded',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: isReady
                            ? null
                            : theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                  if (!isReady)
                    TextButton(
                      onPressed: () => _showLlmDownloadDialog(context),
                      child: const Text('Download'),
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
                  Text('Checking model status...'),
                ],
              ),
              error: (_, _) => Text(
                'Could not check model status',
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
            const SizedBox(height: 16),
            // Personality section.
            Text('Personality', style: theme.textTheme.titleSmall),
            const SizedBox(height: 8),
            _buildPersonalitySection(context, personality, journalOnly),
          ],
        ),
      ),
    );
  }

  /// Show the LLM model download dialog and load the model on success.
  // coverage:ignore-start
  Future<void> _showLlmDownloadDialog(BuildContext context) async {
    final downloadService = ref.read(llmModelDownloadServiceProvider);
    final downloaded = await showLlmModelDownloadDialog(
      context: context,
      downloadService: downloadService,
    );
    if (downloaded) {
      ref.invalidate(llmModelReadyProvider);

      // Local LLM loading disabled: llamadart's native library crashes on
      // Snapdragon 888 (SIGILL in ggml_graph_compute). See llmAutoLoadProvider.
      // TODO(local-llm): Re-enable when compatible binary is available.
    }
  }
  // coverage:ignore-end

  /// Build the personality settings section.
  Widget _buildPersonalitySection(
    BuildContext context,
    PersonalityConfig personality,
    bool journalOnly,
  ) {
    final theme = Theme.of(context);

    if (journalOnly) {
      return Text(
        'Personality settings are disabled in journal-only mode',
        style: theme.textTheme.bodySmall?.copyWith(
          color: theme.colorScheme.onSurfaceVariant,
        ),
      );
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        // Name field.
        TextFormField(
          initialValue: personality.name,
          decoration: const InputDecoration(
            labelText: 'Assistant name',
            border: OutlineInputBorder(),
            isDense: true,
          ),
          onFieldSubmitted: (value) {
            if (value.trim().isNotEmpty) {
              ref
                  .read(personalityConfigProvider.notifier)
                  .setName(value.trim());
            }
          },
        ),
        const SizedBox(height: 12),
        // Conversation style dropdown.
        DropdownButtonFormField<ConversationStyle>(
          initialValue: personality.conversationStyle,
          decoration: const InputDecoration(
            labelText: 'Conversation style',
            border: OutlineInputBorder(),
            isDense: true,
          ),
          items: ConversationStyle.values.map((style) {
            return DropdownMenuItem(
              value: style,
              child: Text(_styleLabel(style)),
            );
          }).toList(),
          onChanged: (style) {
            if (style != null) {
              ref
                  .read(personalityConfigProvider.notifier)
                  .setConversationStyle(style);
            }
          },
        ),
        const SizedBox(height: 12),
        // Custom prompt text area.
        TextFormField(
          initialValue: personality.customPrompt ?? '',
          decoration: const InputDecoration(
            labelText: 'Custom prompt (optional)',
            hintText: 'Add extra instructions for the AI...',
            border: OutlineInputBorder(),
            isDense: true,
          ),
          maxLines: 3,
          maxLength: 500,
          onChanged: (value) {
            ref
                .read(personalityConfigProvider.notifier)
                .setCustomPrompt(value.isEmpty ? null : value);
          },
        ),
        const SizedBox(height: 4),
        Text(
          'Changes take effect on the next session',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
      ],
    );
  }

  /// Human-readable label for a conversation style.
  static String _styleLabel(ConversationStyle style) {
    return switch (style) {
      ConversationStyle.warm => 'Warm & Supportive',
      ConversationStyle.professional => 'Professional & Concise',
      ConversationStyle.curious => 'Curious & Exploratory',
    };
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
                    onPressed: _isSyncing ? null : () => _runSyncNow(context),
                    icon: _isSyncing
                        ? const SizedBox(
                            width: 16,
                            height: 16,
                            child: CircularProgressIndicator(
                              strokeWidth: 2,
                              color: Colors.white,
                            ),
                          )
                        : const Icon(Icons.sync),
                    label: Text(_isSyncing ? 'Syncing...' : 'Sync Now'),
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

  /// Run all sync operations with loading state and user feedback.
  Future<void> _runSyncNow(BuildContext context) async {
    setState(() => _isSyncing = true);
    try {
      final syncRepo = ref.read(syncRepositoryProvider);
      final List<SyncResult> results = [
        await syncRepo.syncPendingSessions(),
        await syncRepo.syncPendingPhotos(),
        await syncRepo.syncPendingCalendarEvents(),
      ];

      final totalSynced = results.fold<int>(0, (sum, r) => sum + r.syncedCount);
      final totalFailed = results.fold<int>(0, (sum, r) => sum + r.failedCount);

      // Invalidate to refresh the count.
      ref.invalidate(pendingSyncCountProvider);

      if (!context.mounted) return;
      final String message;
      if (totalFailed > 0) {
        message = 'Synced $totalSynced, $totalFailed failed';
      } else if (totalSynced > 0) {
        message = 'Synced $totalSynced item${totalSynced == 1 ? '' : 's'}';
      } else {
        message = 'Everything is up to date';
      }
      ScaffoldMessenger.of(
        context,
      ).showSnackBar(SnackBar(content: Text(message)));
    } on Exception catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Sync failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _isSyncing = false);
    }
  }

  /// Build the "Data Management" card with storage info and clear all.
  /// Build the "Location" settings card (Phase 10 — ADR-0019).
  Widget _buildLocationCard(BuildContext context) {
    final theme = Theme.of(context);
    final locationEnabled = ref.watch(locationEnabledProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Location', style: theme.textTheme.titleMedium),
            const SizedBox(height: 4),
            Text(
              'Location names are looked up using your device\'s location '
              'service, which may contact Google. Raw coordinates are not '
              'stored in your journal\'s cloud backup.',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 8),
            SwitchListTile(
              title: const Text('Enable location'),
              subtitle: const Text('Record where you journal'),
              value: locationEnabled,
              onChanged: (value) async {
                if (value) {
                  // Request permission at toggle-on time (B4 — review finding).
                  await _requestLocationPermission(context);
                } else {
                  ref.read(locationEnabledProvider.notifier).setEnabled(false);
                }
              },
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 4),
            OutlinedButton.icon(
              onPressed: _isClearingLocation
                  ? null
                  : () => _showClearLocationDialog(context),
              icon: _isClearingLocation
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : Icon(Icons.location_off, color: theme.colorScheme.error),
              label: Text(
                _isClearingLocation ? 'Clearing...' : 'Clear Location Data',
                style: TextStyle(
                  color: _isClearingLocation
                      ? theme.colorScheme.onSurfaceVariant
                      : theme.colorScheme.error,
                ),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(
                  color: _isClearingLocation
                      ? theme.colorScheme.onSurfaceVariant
                      : theme.colorScheme.error,
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Request location permission when the user toggles location on.
  ///
  /// If permission is granted (whileInUse or always), enables the toggle.
  /// If denied, shows a SnackBar and leaves the toggle off.
  /// If deniedForever, directs the user to app settings.
  Future<void> _requestLocationPermission(BuildContext context) async {
    final locationService = ref.read(locationServiceProvider);
    final permission = await locationService.checkAndRequestPermission();

    if (!context.mounted) return;

    if (permission == LocationPermission.whileInUse ||
        permission == LocationPermission.always) {
      ref.read(locationEnabledProvider.notifier).setEnabled(true);
    } else if (permission == LocationPermission.deniedForever) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: const Text(
            'Location permission is permanently denied. '
            'Please enable it in app settings.',
          ),
          action: SnackBarAction(
            label: 'Open Settings',
            onPressed: () => Geolocator.openAppSettings(),
          ),
        ),
      );
    } else {
      // denied — user dismissed the prompt
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Location permission is required to record location.'),
        ),
      );
    }
  }

  /// Show a confirmation dialog for clearing all location data.
  Future<void> _showClearLocationDialog(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Clear location data?'),
        content: const Text(
          'This will remove location information from all journal entries. '
          'Previously synced location names will be cleared on next sync.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Clear'),
          ),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      setState(() => _isClearingLocation = true);
      try {
        final sessionDao = ref.read(sessionDaoProvider);
        final cleared = await sessionDao.clearAllLocationData();
        // Also disable location tracking (per ADR-0019 spec).
        await ref.read(locationEnabledProvider.notifier).setEnabled(false);

        if (context.mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(
              content: Text(
                cleared > 0
                    ? 'Location data cleared from $cleared session${cleared == 1 ? '' : 's'}.'
                    : 'No location data to clear.',
              ),
            ),
          );
        }
      } finally {
        if (mounted) setState(() => _isClearingLocation = false);
      }
    }
  }

  /// Build the "Calendar" settings card (Phase 11 — ADR-0020).
  Widget _buildCalendarCard(BuildContext context) {
    final theme = Theme.of(context);
    final isConnected = ref.watch(isGoogleConnectedProvider);
    final autoSuggest = ref.watch(calendarAutoSuggestProvider);
    final taskAutoSuggest = ref.watch(taskAutoSuggestProvider);
    final requireConfirmation = ref.watch(calendarConfirmationProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Calendar & Tasks', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            // Connection status.
            Row(
              children: [
                Icon(
                  isConnected ? Icons.check_circle : Icons.link_off,
                  color: isConnected
                      ? Colors.green
                      : theme.colorScheme.onSurfaceVariant,
                  size: 20,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    isConnected
                        ? 'Google Calendar & Tasks: Connected'
                        : 'Google Calendar & Tasks: Not connected',
                    style: theme.textTheme.bodyMedium,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 12),
            // Connect/Disconnect button.
            if (isConnected)
              OutlinedButton.icon(
                onPressed: () async {
                  await ref
                      .read(isGoogleConnectedProvider.notifier)
                      .disconnect();
                },
                icon: const Icon(Icons.link_off),
                label: const Text('Disconnect'),
              )
            else
              FilledButton.icon(
                onPressed: () async {
                  try {
                    await ref
                        .read(isGoogleConnectedProvider.notifier)
                        .connect();
                  } on GoogleAuthException catch (e) {
                    if (context.mounted) {
                      ScaffoldMessenger.of(
                        context,
                      ).showSnackBar(SnackBar(content: Text(e.message)));
                    }
                  }
                },
                icon: const Icon(Icons.calendar_month),
                label: const Text('Connect Google'),
              ),
            const SizedBox(height: 12),
            // Auto-suggest calendar events toggle.
            SwitchListTile(
              title: const Text('Auto-suggest calendar events'),
              subtitle: const Text(
                'Detect dates and reminders in conversation',
              ),
              value: autoSuggest,
              onChanged: (value) {
                ref
                    .read(calendarAutoSuggestProvider.notifier)
                    .setEnabled(value);
              },
              contentPadding: EdgeInsets.zero,
            ),
            // Auto-suggest tasks toggle.
            SwitchListTile(
              title: const Text('Auto-suggest tasks'),
              subtitle: const Text(
                'Detect task creation requests in conversation',
              ),
              value: taskAutoSuggest,
              onChanged: (value) {
                ref.read(taskAutoSuggestProvider.notifier).setEnabled(value);
              },
              contentPadding: EdgeInsets.zero,
            ),
            // Confirmation toggle (always on in v1).
            SwitchListTile(
              title: const Text('Require confirmation'),
              subtitle: const Text('Always confirm before creating events'),
              value: requireConfirmation,
              onChanged: null, // Non-disableable in v1 — always confirm.
              contentPadding: EdgeInsets.zero,
            ),
            const SizedBox(height: 4),
            Text(
              'Confirmation is always required in this version',
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Build the "Pulse Check-In" questionnaire configuration card.
  ///
  /// Shows all items for the active default template with enable/disable
  /// toggles, drag-to-reorder, and an add-custom-item button.
  Widget _buildPulseCheckInCard(BuildContext context) {
    final theme = Theme.of(context);
    final itemsAsync = ref.watch(activeCheckInItemsProvider);

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.monitor_heart_outlined),
        title: const Text('Pulse Check-In'),
        subtitle: const Text('Questionnaire questions and order'),
        children: [
          itemsAsync.when(
            data: (items) => _buildCheckInItemList(context, theme, items),
            loading: () => const Padding(
              padding: EdgeInsets.all(16),
              child: Center(child: CircularProgressIndicator()),
            ),
            error: (_, _) => Padding(
              padding: const EdgeInsets.all(16),
              child: Text(
                'Could not load questions.',
                style: TextStyle(color: theme.colorScheme.error),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// Build the list of check-in items with toggle, reorder, and add controls.
  Widget _buildCheckInItemList(
    BuildContext context,
    ThemeData theme,
    List<QuestionnaireItem> items,
  ) {
    final dao = ref.read(questionnaireDaoProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Drag-to-reorder list.
          ReorderableListView.builder(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            itemCount: items.length,
            onReorder: (oldIndex, newIndex) async {
              if (newIndex > oldIndex) newIndex--;
              final reordered = List<QuestionnaireItem>.from(items);
              final moved = reordered.removeAt(oldIndex);
              reordered.insert(newIndex, moved);
              // Persist updated sortOrder values.
              for (var i = 0; i < reordered.length; i++) {
                await dao.updateItem(
                  reordered[i].id,
                  QuestionnaireItemsCompanion(sortOrder: Value(i)),
                );
              }
            },
            itemBuilder: (ctx, i) {
              final item = items[i];
              return SwitchListTile(
                key: ValueKey(item.id),
                title: Text(
                  item.questionText,
                  style: theme.textTheme.bodyMedium,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                secondary: ReorderableDragStartListener(
                  index: i,
                  child: const Icon(Icons.drag_handle),
                ),
                value: item.isActive,
                onChanged: (enabled) async {
                  await dao.updateItem(
                    item.id,
                    QuestionnaireItemsCompanion(isActive: Value(enabled)),
                  );
                },
                contentPadding: const EdgeInsets.symmetric(horizontal: 16),
              );
            },
          ),
          // Add custom item button.
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                TextButton.icon(
                  onPressed: () => _showAddCheckInItemDialog(context),
                  icon: const Icon(Icons.add, size: 18),
                  label: const Text('Add custom question'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Show a dialog to add a custom check-in item.
  Future<void> _showAddCheckInItemDialog(BuildContext context) async {
    final controller = TextEditingController();
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Add question'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            hintText: 'e.g. How motivated do you feel?',
            border: OutlineInputBorder(),
          ),
          autofocus: true,
          maxLength: 120,
          textCapitalization: TextCapitalization.sentences,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text('Add'),
          ),
        ],
      ),
    );

    if (confirmed != true || controller.text.trim().isEmpty) {
      controller.dispose();
      return;
    }

    final questionText = controller.text.trim();
    controller.dispose();

    final dao = ref.read(questionnaireDaoProvider);
    final template = await dao.getActiveDefaultTemplate();
    if (template == null) return;

    // Determine next sortOrder.
    final existingItems = await dao.getActiveItemsForTemplate(template.id);
    final nextSort = existingItems.isEmpty
        ? 0
        : existingItems
                  .map((i) => i.sortOrder)
                  .reduce((a, b) => a > b ? a : b) +
              1;

    await dao.insertItem(
      QuestionnaireItemsCompanion(
        templateId: Value(template.id),
        questionText: Value(questionText),
        sortOrder: Value(nextSort),
        isActive: const Value(true),
        isReversed: const Value(false),
      ),
    );
  }

  Widget _buildDataManagementCard(BuildContext context) {
    final theme = Theme.of(context);
    final sessionCountAsync = ref.watch(sessionCountProvider);
    final photoInfoAsync = ref.watch(photoStorageInfoProvider);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Data Management', style: theme.textTheme.titleMedium),
            const SizedBox(height: 12),
            // Session count.
            sessionCountAsync.when(
              data: (count) => Text(
                'Journal entries: $count session${count == 1 ? '' : 's'}',
                style: theme.textTheme.bodyMedium,
              ),
              loading: () => const Text('Counting entries...'),
              error: (_, _) => const Text('Could not count entries'),
            ),
            const SizedBox(height: 4),
            // Photo storage info.
            photoInfoAsync.when(
              data: (info) => info.count > 0
                  ? Text(
                      'Photos: ${info.count} photo${info.count == 1 ? '' : 's'}, ${info.formattedSize}',
                      style: theme.textTheme.bodyMedium,
                    )
                  : Text('Photos: None', style: theme.textTheme.bodyMedium),
              loading: () => const Text('Counting photos...'),
              error: (_, _) => const Text('Could not count photos'),
            ),
            const SizedBox(height: 12),
            // Export data button (Phase 2C — data sovereignty).
            OutlinedButton.icon(
              onPressed: _isExporting ? null : () => _exportData(context),
              icon: _isExporting
                  ? const SizedBox(
                      width: 16,
                      height: 16,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.download_outlined),
              label: Text(_isExporting ? 'Exporting...' : 'Export My Data'),
            ),
            const SizedBox(height: 8),
            // Clear all button.
            OutlinedButton.icon(
              onPressed: () => _showClearAllDialog(context),
              icon: Icon(Icons.delete_forever, color: theme.colorScheme.error),
              label: Text(
                'Clear All Entries',
                style: TextStyle(color: theme.colorScheme.error),
              ),
              style: OutlinedButton.styleFrom(
                side: BorderSide(color: theme.colorScheme.error),
              ),
            ),
          ],
        ),
      ),
    );
  }

  /// Export all journal data to a JSON file in the app documents directory.
  ///
  /// Writes to `<documents>/agentic_journal_export_<timestamp>.json`.
  /// Phase 2C — data sovereignty: users can always export and delete their data.
  Future<void> _exportData(BuildContext context) async {
    setState(() => _isExporting = true);
    try {
      final sessionDao = ref.read(sessionDaoProvider);
      final messageDao = ref.read(messageDaoProvider);

      final sessions = await sessionDao.getAllSessionsByDate();
      final exportData = <Map<String, dynamic>>[];

      for (final session in sessions) {
        final messages = await messageDao.getMessagesForSession(
          session.sessionId,
        );
        exportData.add({
          'session_id': session.sessionId,
          'start_time': session.startTime.toIso8601String(),
          'end_time': session.endTime?.toIso8601String(),
          'summary': session.summary,
          'mood_tags': session.moodTags,
          'topic_tags': session.topicTags,
          'journaling_mode': session.journalingMode,
          'messages': messages
              .map(
                (m) => {
                  'role': m.role,
                  'content': m.content,
                  'timestamp': m.timestamp.toIso8601String(),
                },
              )
              .toList(),
        });
      }

      final dir = await getApplicationDocumentsDirectory();
      final timestamp = DateTime.now().toUtc().toIso8601String().replaceAll(
        ':',
        '-',
      );
      final file = File('${dir.path}/agentic_journal_export_$timestamp.json');
      await file.writeAsString(
        const JsonEncoder.withIndent('  ').convert(exportData),
        encoding: utf8,
      );

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text('Exported to ${file.path}'),
            duration: const Duration(seconds: 6),
          ),
        );
      }
    } on Exception catch (e) {
      if (context.mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text('Export failed: $e')));
      }
    } finally {
      if (mounted) setState(() => _isExporting = false);
    }
  }

  /// Show a two-step confirmation dialog for clearing all data.
  ///
  /// The user must type "DELETE" to enable the confirm button.
  Future<void> _showClearAllDialog(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => const _ClearAllDialog(),
    );

    if (confirmed == true && context.mounted) {
      final sessionDao = ref.read(sessionDaoProvider);
      final messageDao = ref.read(messageDaoProvider);
      final photoDao = ref.read(photoDaoProvider);
      final photoService = ref.read(photoServiceProvider);

      // Delete photo files from disk before clearing DB records.
      // Best-effort: file cleanup failures don't block DB cleanup.
      try {
        await photoService.deleteAllPhotos();
      } on Exception catch (_) {
        // path_provider or file I/O may be unavailable — continue anyway.
      }

      await sessionDao.deleteAllCascade(messageDao, photoDao: photoDao);
      ref.invalidate(photoStorageInfoProvider);

      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('All journal entries cleared.')),
        );
      }
    }
  }

  /// Build the "About" card with app information.
  Widget _buildAboutCard(BuildContext context) {
    final versionAsync = ref.watch(appVersionProvider);
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
            versionAsync.when(
              data: (version) => Text(
                'Version $version',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              loading: () => Text(
                'Version ...',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
              error: (_, _) => Text(
                'Version Unknown',
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                  color: Theme.of(context).colorScheme.onSurfaceVariant,
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              'AI-powered personal journaling with offline-first architecture',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
            const Divider(height: 24),
            ListTile(
              contentPadding: EdgeInsets.zero,
              leading: const Icon(Icons.bug_report_outlined),
              title: const Text('Developer Diagnostics'),
              subtitle: const Text('Check subsystem health and view logs'),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.of(context).push(
                MaterialPageRoute<void>(
                  builder: (_) => const DiagnosticsScreen(),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Two-step confirmation dialog for clearing all journal entries.
///
/// The user must type "DELETE" in a text field to enable the confirm button.
/// This prevents accidental data loss.
class _ClearAllDialog extends StatefulWidget {
  const _ClearAllDialog();

  @override
  State<_ClearAllDialog> createState() => _ClearAllDialogState();
}

class _ClearAllDialogState extends State<_ClearAllDialog> {
  final _controller = TextEditingController();
  bool _isConfirmEnabled = false;

  @override
  void initState() {
    super.initState();
    _controller.addListener(() {
      final enabled = _controller.text.trim() == 'DELETE';
      if (enabled != _isConfirmEnabled) {
        setState(() => _isConfirmEnabled = enabled);
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: const Text('Clear all entries?'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'This will permanently delete all journal sessions, messages, '
            'and photos. This cannot be undone.',
          ),
          const SizedBox(height: 16),
          const Text('Type DELETE to confirm:'),
          const SizedBox(height: 8),
          TextField(
            controller: _controller,
            decoration: const InputDecoration(
              hintText: 'DELETE',
              border: OutlineInputBorder(),
            ),
            autofocus: true,
          ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isConfirmEnabled
              ? () => Navigator.of(context).pop(true)
              : null,
          style: FilledButton.styleFrom(
            backgroundColor: _isConfirmEnabled
                ? Theme.of(context).colorScheme.error
                : null,
          ),
          child: const Text('Clear All'),
        ),
      ],
    );
  }
}
