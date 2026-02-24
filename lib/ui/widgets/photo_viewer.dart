// ===========================================================================
// file: lib/ui/widgets/photo_viewer.dart
// purpose: Full-screen photo viewer with pinch-to-zoom and caption overlay.
//
// Uses InteractiveViewer (built-in Flutter) for zoom/pan functionality
// and Hero animation for smooth transition from thumbnail to full-screen.
// Includes a delete button with confirmation dialog.
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter/material.dart';

/// Full-screen photo viewer with zoom, caption, and delete support.
class PhotoViewer extends StatelessWidget {
  /// Path to the photo file on disk.
  final String photoPath;

  /// Optional caption to display at the bottom.
  final String? caption;

  /// Callback when the delete button is tapped and confirmed.
  final VoidCallback? onDelete;

  /// Hero animation tag. Each call site must provide a unique tag to
  /// avoid duplicate Hero tags when multiple screens are in the tree.
  final String? heroTag;

  const PhotoViewer({
    super.key,
    required this.photoPath,
    this.caption,
    this.onDelete,
    this.heroTag,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        actions: [
          if (onDelete != null)
            IconButton(
              icon: const Icon(Icons.delete_outline),
              tooltip: 'Delete photo',
              onPressed: () => _confirmDelete(context),
            ),
        ],
      ),
      body: Stack(
        fit: StackFit.expand,
        children: [
          // Zoomable photo.
          InteractiveViewer(
            minScale: 0.5,
            maxScale: 4.0,
            child: Center(
              child: Hero(
                tag: heroTag ?? 'photo-$photoPath',
                child: Image.file(
                  File(photoPath),
                  fit: BoxFit.contain,
                  errorBuilder: (_, __, ___) => const Center(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(
                          Icons.broken_image,
                          size: 64,
                          color: Colors.white54,
                        ),
                        SizedBox(height: 8),
                        Text(
                          'Photo not available',
                          style: TextStyle(color: Colors.white54),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),

          // Caption overlay at the bottom.
          if (caption != null && caption!.isNotEmpty)
            Positioned(
              left: 0,
              right: 0,
              bottom: 0,
              child: Container(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 24),
                decoration: BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topCenter,
                    end: Alignment.bottomCenter,
                    colors: [
                      Colors.transparent,
                      Colors.black.withValues(alpha: 0.7),
                    ],
                  ),
                ),
                child: Text(
                  caption!,
                  style: const TextStyle(color: Colors.white, fontSize: 14),
                ),
              ),
            ),
        ],
      ),
    );
  }

  /// Show a confirmation dialog before deleting.
  Future<void> _confirmDelete(BuildContext context) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete this photo?'),
        content: const Text('This cannot be undone.'),
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
            child: const Text('Delete'),
          ),
        ],
      ),
    );

    if (confirmed == true) {
      onDelete?.call();
      if (context.mounted) {
        Navigator.of(context).pop(); // Close the viewer.
      }
    }
  }
}
