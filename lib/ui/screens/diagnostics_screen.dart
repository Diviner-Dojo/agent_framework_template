// ===========================================================================
// file: lib/ui/screens/diagnostics_screen.dart
// purpose: Developer diagnostics screen for runtime observability.
//
// Provides:
//   - "Run Diagnostics" button that probes all subsystems
//   - Results list with pass/fail icons, detail text, elapsed time
//   - AppLogger ring buffer viewer (most recent first)
//   - "Copy Log" to clipboard
//
// Accessible from Settings → Developer Diagnostics.
//
// See: Runtime Observability plan
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../providers/onboarding_providers.dart';
import '../../providers/session_providers.dart';
import '../../services/app_logger.dart';
import '../../services/diagnostic_service.dart';

/// Developer diagnostics screen showing subsystem health and log buffer.
class DiagnosticsScreen extends ConsumerStatefulWidget {
  /// Creates a diagnostics screen.
  const DiagnosticsScreen({super.key});

  @override
  ConsumerState<DiagnosticsScreen> createState() => _DiagnosticsScreenState();
}

class _DiagnosticsScreenState extends ConsumerState<DiagnosticsScreen> {
  List<DiagnosticResult>? _results;
  bool _isRunning = false;

  Future<void> _runDiagnostics() async {
    setState(() {
      _isRunning = true;
      _results = null;
    });

    final connectivityService = ref.read(connectivityServiceProvider);
    final agentRepository = ref.read(agentRepositoryProvider);

    SharedPreferences? prefs;
    try {
      prefs = ref.read(sharedPreferencesProvider);
    } on Exception {
      // Provider may not be overridden in test contexts.
    }

    final service = DiagnosticService(
      connectivityService: connectivityService,
      agentRepository: agentRepository,
      prefs: prefs,
    );

    final results = await service.runAll();

    if (mounted) {
      setState(() {
        _results = results;
        _isRunning = false;
      });
    }
  }

  void _copyLog() {
    final entries = AppLogger.entries.reversed;
    final text = entries.map((e) => e.toString()).join('\n');
    Clipboard.setData(ClipboardData(text: text));
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(const SnackBar(content: Text('Log copied to clipboard')));
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(title: const Text('Developer Diagnostics')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Run / Re-run button
          FilledButton.icon(
            onPressed: _isRunning ? null : _runDiagnostics,
            icon: _isRunning
                ? const SizedBox(
                    width: 18,
                    height: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: Colors.white,
                    ),
                  )
                : const Icon(Icons.play_arrow),
            label: Text(
              _results == null ? 'Run Diagnostics' : 'Re-run Diagnostics',
            ),
          ),
          const SizedBox(height: 16),

          // Results
          if (_results != null) ...[
            Text('Results', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            ..._results!.map(_buildResultCard),
            const SizedBox(height: 24),
          ],

          // Log buffer
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Log Buffer', style: theme.textTheme.titleMedium),
              TextButton.icon(
                onPressed: _copyLog,
                icon: const Icon(Icons.copy, size: 16),
                label: const Text('Copy Log'),
              ),
            ],
          ),
          const SizedBox(height: 8),
          _buildLogView(theme),
        ],
      ),
    );
  }

  Widget _buildResultCard(DiagnosticResult result) {
    return Card(
      child: ListTile(
        leading: Icon(
          result.passed ? Icons.check_circle : Icons.cancel,
          color: result.passed ? Colors.green : Colors.red,
        ),
        title: Text(result.name),
        subtitle: Text(result.detail),
        trailing: Text(
          '${result.elapsed.inMilliseconds}ms',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      ),
    );
  }

  Widget _buildLogView(ThemeData theme) {
    final entries = AppLogger.entries.reversed.toList();

    if (entries.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
        ),
        child: const Text(
          'No log entries yet. Start using the app to see logs.',
        ),
      );
    }

    return Container(
      height: 300,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: ListView.builder(
        itemCount: entries.length,
        itemBuilder: (context, index) {
          final entry = entries[index];
          final color = switch (entry.level) {
            LogLevel.error => Colors.red,
            LogLevel.warn => Colors.orange,
            LogLevel.info => theme.colorScheme.onSurface,
          };

          return Padding(
            padding: const EdgeInsets.symmetric(vertical: 1),
            child: Text(
              entry.toString(),
              style: TextStyle(
                fontFamily: 'monospace',
                fontSize: 11,
                color: color,
              ),
            ),
          );
        },
      ),
    );
  }
}
