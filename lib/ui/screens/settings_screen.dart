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
    show
        QuestionnaireItem,
        QuestionnaireItemsCompanion,
        QuestionnaireTemplate,
        QuestionnaireTemplatesCompanion;
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
import '../../providers/reminder_providers.dart';
import '../../services/reminder_service.dart';
import '../../providers/settings_providers.dart';
import '../../providers/sync_providers.dart';
import '../../providers/task_providers.dart';
import '../../repositories/sync_repository.dart';
import '../../providers/theme_providers.dart';
import '../../providers/voice_providers.dart';
import '../widgets/llm_model_download_dialog.dart';
import '../widgets/theme_preview_card.dart';
import '../../ui/theme/palettes.dart';
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
          _buildThemeCard(context),
          const SizedBox(height: 16),
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
          _buildRemindersCard(context),
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

  /// Build the "Theme & Appearance" settings card.
  ///
  /// Shows palette selection grid at top level, with light/dark toggle.
  /// Font scale, card style, and bubble shape are inside a collapsed
  /// "Advanced" expansion tile (progressive disclosure per spec).
  Widget _buildThemeCard(BuildContext context) {
    final themeState = ref.watch(themeProvider);
    final notifier = ref.read(themeProvider.notifier);

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Section header.
            Row(
              children: [
                Icon(
                  Icons.palette,
                  color: Theme.of(context).colorScheme.primary,
                ),
                const SizedBox(width: 8),
                Text(
                  'Theme & Appearance',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ],
            ),
            const SizedBox(height: 16),

            // Palette selection grid.
            GridView.builder(
              shrinkWrap: true,
              physics: const NeverScrollableScrollPhysics(),
              gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                crossAxisCount: 4,
                mainAxisSpacing: 8,
                crossAxisSpacing: 8,
                childAspectRatio: 0.78,
              ),
              itemCount: appPalettes.length,
              itemBuilder: (context, index) {
                final palette = appPalettes[index];
                return ThemePreviewCard(
                  palette: palette,
                  isSelected: palette.id == themeState.paletteId,
                  onTap: () => notifier.selectPalette(palette.id),
                );
              },
            ),
            const SizedBox(height: 16),

            // Light / Dark / System toggle.
            Text('Appearance', style: Theme.of(context).textTheme.labelLarge),
            const SizedBox(height: 8),
            SegmentedButton<ThemeMode>(
              segments: const [
                ButtonSegment(
                  value: ThemeMode.system,
                  label: Text('System'),
                  icon: Icon(Icons.brightness_auto),
                ),
                ButtonSegment(
                  value: ThemeMode.light,
                  label: Text('Light'),
                  icon: Icon(Icons.light_mode),
                ),
                ButtonSegment(
                  value: ThemeMode.dark,
                  label: Text('Dark'),
                  icon: Icon(Icons.dark_mode),
                ),
              ],
              selected: {themeState.themeMode},
              onSelectionChanged: (selection) {
                notifier.setThemeMode(selection.first);
              },
            ),
            const SizedBox(height: 8),

            // Advanced options (collapsed by default).
            ExpansionTile(
              title: const Text('Advanced'),
              tilePadding: EdgeInsets.zero,
              childrenPadding: const EdgeInsets.only(bottom: 8),
              children: [
                // Font scale.
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Font Size'),
                  trailing: DropdownButton<FontScale>(
                    value: themeState.fontScale,
                    underline: const SizedBox.shrink(),
                    onChanged: (value) {
                      if (value != null) notifier.setFontScale(value);
                    },
                    items: FontScale.values
                        .map(
                          (s) =>
                              DropdownMenuItem(value: s, child: Text(s.label)),
                        )
                        .toList(),
                  ),
                ),
                // Card style.
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Card Style'),
                  trailing: DropdownButton<CardStyle>(
                    value: themeState.cardStyle,
                    underline: const SizedBox.shrink(),
                    onChanged: (value) {
                      if (value != null) notifier.setCardStyle(value);
                    },
                    items: CardStyle.values
                        .map(
                          (s) =>
                              DropdownMenuItem(value: s, child: Text(s.label)),
                        )
                        .toList(),
                  ),
                ),
                // Bubble shape.
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: const Text('Bubble Shape'),
                  trailing: DropdownButton<BubbleShape>(
                    value: themeState.bubbleShape,
                    underline: const SizedBox.shrink(),
                    onChanged: (value) {
                      if (value != null) notifier.setBubbleShape(value);
                    },
                    items: BubbleShape.values
                        .map(
                          (s) =>
                              DropdownMenuItem(value: s, child: Text(s.label)),
                        )
                        .toList(),
                  ),
                ),
              ],
            ),

            // Reset to defaults.
            Align(
              alignment: Alignment.centerRight,
              child: TextButton.icon(
                onPressed: () async {
                  final previous = await notifier.resetToDefaults();
                  if (!context.mounted) return;
                  ScaffoldMessenger.of(context).showSnackBar(
                    SnackBar(
                      content: const Text('Theme reset to defaults'),
                      duration: const Duration(seconds: 8),
                      action: SnackBarAction(
                        label: 'Undo',
                        onPressed: () => notifier.restore(previous),
                      ),
                    ),
                  );
                },
                icon: const Icon(Icons.restore, size: 18),
                label: const Text('Reset to defaults'),
              ),
            ),
          ],
        ),
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
                    value: SttEngine.deepgram,
                    child: Text('Deepgram (Experimental)'),
                  ),
                  DropdownMenuItem(
                    value: SttEngine.speechToText,
                    child: Text('Google (Default)'),
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

  /// Build the "Reminders" settings card (Phase 4D).
  ///
  /// Allows the user to enable a daily journal reminder and choose a
  /// preferred time window (morning / afternoon / evening).
  ///
  /// ADHD clinical UX constraints:
  ///   - Opt-in only (disabled by default).
  ///   - Auto-disabled after 3 consecutive dismissals (non-escalating).
  ///   - "Snooze forever" is available from the home screen card.
  Widget _buildRemindersCard(BuildContext context) {
    final theme = Theme.of(context);
    final service = ref.watch(reminderServiceProvider);
    final enabled = service.isEnabled(ReminderType.dailyJournal);
    final window = service.getWindow(ReminderType.dailyJournal);
    final dismissals = service.consecutiveDismissals(ReminderType.dailyJournal);
    final autoDisabled =
        dismissals >= ReminderService.maxConsecutiveDismissals && !enabled;

    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Reminders', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            SwitchListTile(
              contentPadding: EdgeInsets.zero,
              title: const Text('Daily journal reminder'),
              subtitle: autoDisabled
                  ? const Text(
                      'Auto-disabled after 3 dismissals. Toggle to re-enable.',
                    )
                  : const Text('A gentle nudge at your preferred time of day.'),
              value: enabled,
              onChanged: (value) async {
                await service.setEnabled(
                  ReminderType.dailyJournal,
                  value: value,
                );
                // Invalidate so the home screen card re-evaluates immediately.
                ref.invalidate(dailyReminderVisibleProvider);
                setState(() {});
              },
            ),
            if (enabled) ...[
              const SizedBox(height: 4),
              Text(
                'Reminder time',
                style: theme.textTheme.labelMedium?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                ),
              ),
              const SizedBox(height: 6),
              SegmentedButton<ReminderWindow>(
                segments: ReminderWindow.values
                    .map(
                      (w) => ButtonSegment<ReminderWindow>(
                        value: w,
                        label: Text(switch (w) {
                          ReminderWindow.morning => 'Morning',
                          ReminderWindow.afternoon => 'Afternoon',
                          ReminderWindow.evening => 'Evening',
                        }),
                      ),
                    )
                    .toList(),
                selected: {window},
                onSelectionChanged: (selection) async {
                  await service.setWindow(
                    ReminderType.dailyJournal,
                    selection.first,
                  );
                  setState(() {});
                },
              ),
              const SizedBox(height: 6),
              Text(
                switch (window) {
                  ReminderWindow.morning =>
                    'Appears between 7 AM and 9 AM when you open the app.',
                  ReminderWindow.afternoon =>
                    'Appears between 12 PM and 2 PM when you open the app.',
                  ReminderWindow.evening =>
                    'Appears between 7 PM and 9 PM when you open the app.',
                },
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
    // Template is optional — scale toggle shows only when template is loaded.
    final template = ref.watch(activeDefaultTemplateProvider).valueOrNull;

    return Card(
      child: ExpansionTile(
        leading: const Icon(Icons.monitor_heart_outlined),
        title: const Text('Pulse Check-In'),
        subtitle: const Text('Questionnaire questions and order'),
        children: [
          itemsAsync.when(
            data: (items) =>
                _buildCheckInItemList(context, theme, items, template),
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

  /// Build the list of check-in items with scale toggle, toggle, reorder,
  /// edit, and add controls.
  Widget _buildCheckInItemList(
    BuildContext context,
    ThemeData theme,
    List<QuestionnaireItem> items,
    QuestionnaireTemplate? template,
  ) {
    final dao = ref.read(questionnaireDaoProvider);
    return Padding(
      padding: const EdgeInsets.fromLTRB(0, 0, 0, 8),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Scale configuration (shown when template is loaded).
          if (template != null) ...[
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 4, 16, 8),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Answer scale', style: theme.textTheme.labelLarge),
                  const SizedBox(height: 8),
                  SegmentedButton<String>(
                    style: SegmentedButton.styleFrom(
                      visualDensity: VisualDensity.compact,
                    ),
                    segments: const [
                      ButtonSegment(value: '1-5', label: Text('1 – 5')),
                      ButtonSegment(value: '1-10', label: Text('1 – 10')),
                      ButtonSegment(value: '0-100', label: Text('0 – 100')),
                    ],
                    selected: {_scaleKey(template.scaleMin, template.scaleMax)},
                    onSelectionChanged: (selection) async {
                      final (min, max) = _parseScaleKey(selection.first);
                      try {
                        await dao.updateTemplate(
                          template.id,
                          QuestionnaireTemplatesCompanion(
                            scaleMin: Value(min),
                            scaleMax: Value(max),
                          ),
                        );
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text('Answer scale updated.'),
                            ),
                          );
                        }
                      } on Exception catch (_) {
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            const SnackBar(
                              content: Text(
                                'Could not save scale change. Try again.',
                              ),
                            ),
                          );
                        }
                      }
                    },
                  ),
                  const SizedBox(height: 4),
                  Text(
                    'Applied immediately to all future check-ins.'
                    ' Past answers are unaffected.',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: theme.colorScheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ),
            ),
            const Divider(height: 1),
          ],

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
              try {
                // Persist updated sortOrder values.
                for (var i = 0; i < reordered.length; i++) {
                  await dao.updateItem(
                    reordered[i].id,
                    QuestionnaireItemsCompanion(sortOrder: Value(i)),
                  );
                }
              } on Exception catch (_) {
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Could not reorder questions. Try again.'),
                    ),
                  );
                }
              }
            },
            itemBuilder: (ctx, i) {
              final item = items[i];
              return ListTile(
                key: ValueKey(item.id),
                leading: ReorderableDragStartListener(
                  index: i,
                  child: const Icon(Icons.drag_handle),
                ),
                title: Text(
                  item.questionText,
                  style: theme.textTheme.bodyMedium,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                trailing: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    IconButton(
                      icon: const Icon(Icons.edit_outlined, size: 20),
                      tooltip: 'Edit question',
                      onPressed: () =>
                          _showEditCheckInItemDialog(context, item),
                    ),
                    Switch(
                      value: item.isActive,
                      onChanged: (enabled) async {
                        try {
                          await dao.updateItem(
                            item.id,
                            QuestionnaireItemsCompanion(
                              isActive: Value(enabled),
                            ),
                          );
                        } on Exception catch (_) {
                          if (context.mounted) {
                            ScaffoldMessenger.of(context).showSnackBar(
                              const SnackBar(
                                content: Text(
                                  'Could not update question. Try again.',
                                ),
                              ),
                            );
                          }
                          return; // abort — do not show Undo SnackBar on write failure
                        }
                        // When deactivating, offer an immediate Undo path so
                        // ADHD users aren't caught off-guard by a question
                        // silently disappearing from future check-ins.
                        if (!enabled && context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: const Text('Question deactivated.'),
                              action: SnackBarAction(
                                label: 'Undo',
                                onPressed: () async {
                                  await dao.updateItem(
                                    item.id,
                                    const QuestionnaireItemsCompanion(
                                      isActive: Value(true),
                                    ),
                                  );
                                },
                              ),
                            ),
                          );
                        }
                      },
                    ),
                  ],
                ),
                contentPadding: const EdgeInsets.only(left: 16),
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

  /// Show a dialog to edit the text of an existing check-in item.
  Future<void> _showEditCheckInItemDialog(
    BuildContext context,
    QuestionnaireItem item,
  ) async {
    // Controller is created inside the builder so its lifecycle is tied to
    // the dialog widget. The Save button captures text before popping to
    // avoid reading/disposing the controller after dismiss animation starts.
    final newText = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final controller = TextEditingController(text: item.questionText);
        return AlertDialog(
          title: const Text('Edit question'),
          content: TextField(
            controller: controller,
            decoration: const InputDecoration(border: OutlineInputBorder()),
            autofocus: true,
            maxLength: 120,
            textCapitalization: TextCapitalization.sentences,
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(ctx).pop(controller.text),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );

    final trimmed = newText?.trim() ?? '';
    if (trimmed.isEmpty || trimmed == item.questionText) return;

    await ref
        .read(questionnaireDaoProvider)
        .updateItem(
          item.id,
          QuestionnaireItemsCompanion(questionText: Value(trimmed)),
        );
  }

  /// Show a dialog to add a custom check-in item.
  Future<void> _showAddCheckInItemDialog(BuildContext context) async {
    // Controller is created inside the builder — text captured before pop.
    final result = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final controller = TextEditingController();
        return AlertDialog(
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
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            FilledButton(
              onPressed: () => Navigator.of(ctx).pop(controller.text),
              child: const Text('Add'),
            ),
          ],
        );
      },
    );

    final questionText = result?.trim() ?? '';
    if (questionText.isEmpty) return;

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

  /// Export all journal data to a JSON file in the public Downloads folder.
  ///
  /// On Android writes to `/storage/emulated/0/Download/` (accessible from
  /// the Files app or any file manager). Falls back to the app documents
  /// directory on non-Android platforms.
  ///
  /// Filename: `agentic_journal_export_<UTC-timestamp>.json`
  /// Phase 2C — data sovereignty: users can always export and delete their data.
  /// Includes: sessions, messages, check-in responses/answers, photo paths,
  /// and video paths. All three media arrays are always present (empty when
  /// no data exists), ensuring a stable schema across all users.
  Future<void> _exportData(BuildContext context) async {
    setState(() => _isExporting = true);
    try {
      final sessionDao = ref.read(sessionDaoProvider);
      final messageDao = ref.read(messageDaoProvider);
      final questionnaireDao = ref.read(questionnaireDaoProvider);
      final photoDao = ref.read(photoDaoProvider);
      final videoDao = ref.read(videoDaoProvider);

      // Cache: templateId → {itemId → questionText}
      final itemTextCache = <int, Map<int, String>>{};

      final sessions = await sessionDao.getAllSessionsByDate();
      final exportData = <Map<String, dynamic>>[];

      for (final session in sessions) {
        final messages = await messageDao.getMessagesForSession(
          session.sessionId,
        );

        // Check-in data for this session.
        final checkInResponses = await questionnaireDao
            .getAllResponsesForSession(session.sessionId);
        final checkInsJson = <Map<String, dynamic>>[];
        for (final rwa in checkInResponses) {
          // Resolve item text (cached per template).
          final templateId = rwa.response.templateId;
          if (!itemTextCache.containsKey(templateId)) {
            // Use getAllItemsForTemplate (not getActiveItemsForTemplate) so
            // that deactivated items still show their question text in exports.
            // Matches the same pattern used in checkInHistoryProvider.
            final items = await questionnaireDao.getAllItemsForTemplate(
              templateId,
            );
            itemTextCache[templateId] = {
              for (final it in items) it.id: it.questionText,
            };
          }
          final itemTexts = itemTextCache[templateId]!;
          checkInsJson.add({
            'completed_at': rwa.response.completedAt.toIso8601String(),
            'composite_score': rwa.response.compositeScore,
            'answers': rwa.answers
                .map(
                  (a) => {
                    'question': itemTexts[a.itemId] ?? 'Unknown',
                    'value': a.value,
                  },
                )
                .toList(),
          });
        }

        // Photo paths for this session.
        final photos = await photoDao.getPhotosForSession(session.sessionId);
        final photosJson = photos
            .map(
              (p) => {
                'local_path': p.localPath,
                'timestamp': p.timestamp.toIso8601String(),
                if (p.description != null) 'description': p.description,
              },
            )
            .toList();

        // Video paths for this session.
        final videos = await videoDao.getVideosForSession(session.sessionId);
        final videosJson = videos
            .map(
              (v) => {
                'video_id': v.videoId,
                'local_path': v.localPath,
                'thumbnail_path': v.thumbnailPath,
                'duration_seconds': v.durationSeconds,
                'timestamp': v.timestamp.toIso8601String(),
                if (v.description != null) 'description': v.description,
                if (v.width != null) 'width': v.width,
                if (v.height != null) 'height': v.height,
                if (v.fileSizeBytes != null) 'file_size_bytes': v.fileSizeBytes,
              },
            )
            .toList();

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
          // Always include all three arrays even when empty so the export
          // schema is stable regardless of how much data the user has.
          'check_ins': checkInsJson,
          'photos': photosJson,
          'videos': videosJson,
        });
      }

      // Use the public Downloads folder on Android (accessible via Files app).
      // No WRITE_EXTERNAL_STORAGE permission needed on API 29+.
      final Directory dir;
      if (Platform.isAndroid) {
        dir = Directory('/storage/emulated/0/Download');
        if (!dir.existsSync()) await dir.create(recursive: true);
      } else {
        dir = await getApplicationDocumentsDirectory();
      }

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
          const SnackBar(
            content: Text('Export saved to your Downloads folder.'),
            duration: Duration(seconds: 6),
          ),
        );
      }
    } on FileSystemException {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text(
              'Export failed: could not write to Downloads folder. '
              'Check storage permissions and available space.',
            ),
            duration: Duration(seconds: 8),
          ),
        );
      }
    } on Exception {
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Export failed. Please try again.'),
            duration: Duration(seconds: 8),
          ),
        );
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

// ---------------------------------------------------------------------------
// Scale preset helpers (used by _buildCheckInItemList)
// ---------------------------------------------------------------------------

/// Map (scaleMin, scaleMax) to a canonical preset key string.
///
/// Non-standard combinations fall back to '1-10' to keep the SegmentedButton
/// in a defined state.
String _scaleKey(int min, int max) {
  if (min == 1 && max == 5) return '1-5';
  if (min == 0 && max == 100) return '0-100';
  return '1-10';
}

/// Parse a preset key back to (scaleMin, scaleMax).
(int, int) _parseScaleKey(String key) {
  return switch (key) {
    '1-5' => (1, 5),
    '0-100' => (0, 100),
    _ => (1, 10),
  };
}
