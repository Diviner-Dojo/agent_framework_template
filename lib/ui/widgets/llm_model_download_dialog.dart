// ===========================================================================
// file: lib/ui/widgets/llm_model_download_dialog.dart
// purpose: Modal dialog showing LLM model download progress.
//
// Shown when the user taps "Download Local AI" in settings. Offers WiFi-only
// or immediate download options, shows progress, and reports completion
// or errors. Follows the same pattern as ModelDownloadDialog (STT).
//
// See: ADR-0017 (Local LLM Layer Architecture)
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';

import '../../services/llm_model_download_service.dart';
import '../../services/model_download_service.dart'
    show ModelDownloadStatus, ModelDownloadProgress;

/// Shows an LLM model download dialog and returns true if download completed.
///
/// Returns false if the user cancelled or an error occurred.
Future<bool> showLlmModelDownloadDialog({
  required BuildContext context,
  required LlmModelDownloadService downloadService,
}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) =>
        _LlmModelDownloadDialog(downloadService: downloadService),
  );
  return result ?? false;
}

class _LlmModelDownloadDialog extends StatefulWidget {
  final LlmModelDownloadService downloadService;

  const _LlmModelDownloadDialog({required this.downloadService});

  @override
  State<_LlmModelDownloadDialog> createState() =>
      _LlmModelDownloadDialogState();
}

class _LlmModelDownloadDialogState extends State<_LlmModelDownloadDialog> {
  ModelDownloadProgress _progress = const ModelDownloadProgress(
    status: ModelDownloadStatus.idle,
  );
  StreamSubscription<ModelDownloadProgress>? _subscription;
  bool _isOnWifi = true;
  bool _hasStarted = false;

  @override
  void initState() {
    super.initState();
    _checkWifi();
    _subscription = widget.downloadService.downloadProgress.listen((progress) {
      if (mounted) {
        setState(() => _progress = progress);
        if (progress.status == ModelDownloadStatus.completed) {
          Navigator.of(context).pop(true);
        }
      }
    });
  }

  Future<void> _checkWifi() async {
    final onWifi = await widget.downloadService.isOnWifi();
    if (mounted) {
      setState(() => _isOnWifi = onWifi);
    }
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  Future<void> _startDownload({bool forceOverCellular = false}) async {
    setState(() => _hasStarted = true);
    try {
      await widget.downloadService.downloadModel(
        forceOverCellular: forceOverCellular,
      );
    } on Exception {
      // Error is reported via the progress stream.
    }
  }

  void _cancel() {
    widget.downloadService.cancelDownload();
    Navigator.of(context).pop(false);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return AlertDialog(
      title: const Text('Local AI Model'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (!_hasStarted) ...[
              const Text(
                'Download the local AI model (~380 MB) for offline '
                'conversations. This is a one-time download.',
              ),
              const SizedBox(height: 16),
              if (!_isOnWifi)
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: theme.colorScheme.errorContainer,
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Row(
                    children: [
                      Icon(
                        Icons.signal_cellular_alt,
                        color: theme.colorScheme.onErrorContainer,
                        size: 20,
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Text(
                          'You are on cellular data. '
                          'WiFi is recommended for this download.',
                          style: TextStyle(
                            color: theme.colorScheme.onErrorContainer,
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
            ] else ...[
              _buildProgressContent(theme),
            ],
          ],
        ),
      ),
      actions: [
        if (!_hasStarted) ...[
          TextButton(onPressed: _cancel, child: const Text('Cancel')),
          if (!_isOnWifi)
            TextButton(
              onPressed: () => _startDownload(forceOverCellular: true),
              child: const Text('Download Now'),
            ),
          FilledButton(
            onPressed: _isOnWifi ? () => _startDownload() : null,
            child: Text(_isOnWifi ? 'Download' : 'Download on Wi-Fi'),
          ),
        ] else if (_progress.status == ModelDownloadStatus.failed) ...[
          TextButton(onPressed: _cancel, child: const Text('Cancel')),
          FilledButton(
            onPressed: () {
              setState(() => _hasStarted = false);
            },
            child: const Text('Retry'),
          ),
        ] else ...[
          TextButton(onPressed: _cancel, child: const Text('Cancel')),
        ],
      ],
    );
  }

  Widget _buildProgressContent(ThemeData theme) {
    final statusText = switch (_progress.status) {
      ModelDownloadStatus.downloading =>
        'Downloading ${_progress.currentFile ?? 'model'}...',
      ModelDownloadStatus.verifying => 'Verifying file integrity...',
      ModelDownloadStatus.completed => 'Download complete!',
      ModelDownloadStatus.failed => _progress.error ?? 'Download failed',
      _ => 'Preparing...',
    };

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(statusText),
        const SizedBox(height: 12),
        LinearProgressIndicator(
          value: _progress.status == ModelDownloadStatus.failed
              ? null
              : _progress.progress,
        ),
        const SizedBox(height: 8),
        Text(
          '${(_progress.progress * 100).toInt()}%',
          style: theme.textTheme.bodySmall?.copyWith(
            color: theme.colorScheme.onSurfaceVariant,
          ),
        ),
        if (_progress.status == ModelDownloadStatus.failed) ...[
          const SizedBox(height: 8),
          Text(
            _progress.error ?? '',
            style: TextStyle(color: theme.colorScheme.error),
          ),
        ],
      ],
    );
  }
}
