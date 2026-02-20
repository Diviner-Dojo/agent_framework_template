// ===========================================================================
// file: lib/ui/widgets/sync_status_indicator.dart
// purpose: Small icon indicator showing the sync status of a journal session.
//
// Displays a compact icon:
//   - SYNCED  → green cloud-done icon
//   - PENDING → gray cloud-upload icon
//   - FAILED  → red cloud-off icon
//
// See: ADR-0012 (Optional Auth with Upload-Only Cloud Sync)
// ===========================================================================

import 'package:flutter/material.dart';

import '../../models/sync_status.dart';

/// Compact icon showing the sync status of a session.
///
/// [status] is the sync status from the database.
/// [size] controls the icon size (default 16).
class SyncStatusIndicator extends StatelessWidget {
  final SyncStatus status;
  final double size;

  const SyncStatusIndicator({super.key, required this.status, this.size = 16});

  @override
  Widget build(BuildContext context) {
    final (icon, color, tooltip) = switch (status) {
      SyncStatus.synced => (Icons.cloud_done, Colors.green, 'Synced'),
      SyncStatus.pending => (
        Icons.cloud_upload_outlined,
        Colors.grey,
        'Pending sync',
      ),
      SyncStatus.failed => (Icons.cloud_off, Colors.red, 'Sync failed'),
    };

    return Tooltip(
      message: tooltip,
      child: Icon(icon, size: size, color: color),
    );
  }
}
