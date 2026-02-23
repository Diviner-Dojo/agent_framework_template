// ===========================================================================
// file: lib/ui/widgets/model_download_dialog.dart
// purpose: Modal dialog showing STT model download progress.
//
// Shown when the user first activates voice mode and the model files
// haven't been downloaded yet. Offers WiFi-only or immediate download
// options, shows progress, and reports completion or errors.
//
// See: ADR-0015 (Voice Mode Architecture)
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';

import '../../services/model_download_service.dart';

/// Shows a model download dialog and returns true if download completed.
///
/// Returns false if the user cancelled or an error occurred.
Future<bool> showModelDownloadDialog({
  required BuildContext context,
  required ModelDownloadService downloadService,
}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: false,
    builder: (context) =>
        _ModelDownloadDialog(downloadService: downloadService),
  );
  return result ?? false;
}

class _ModelDownloadDialog extends StatefulWidget {
  final ModelDownloadService downloadService;

  const _ModelDownloadDialog({required this.downloadService});

  @override
  State<_ModelDownloadDialog> createState() => _ModelDownloadDialogState();
}

class _ModelDownloadDialogState extends State<_ModelDownloadDialog> {
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
    } catch (_) {
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
      title: const Text('Speech Model Required'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!_hasStarted) ...[
            const Text(
              'Voice mode requires a speech recognition model (~71 MB). '
              'This is a one-time download.',
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
            // Download in progress.
            _buildProgressContent(theme),
          ],
        ],
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
      ModelDownloadStatus.verifying => 'Verifying files...',
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
