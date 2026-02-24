// ===========================================================================
// file: lib/ui/screens/photo_gallery_screen.dart
// purpose: Grid view of all photos across all journal sessions.
//
// Displays photos in a 3-column grid, newest first. Tapping a photo
// opens the full-screen PhotoViewer with zoom support.
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/photo_providers.dart';
import '../widgets/photo_viewer.dart';

/// Gallery screen showing all photos in a 3-column grid.
class PhotoGalleryScreen extends ConsumerWidget {
  const PhotoGalleryScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final photosAsync = ref.watch(allPhotosProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Photo Gallery')),
      body: photosAsync.when(
        data: (photos) {
          if (photos.isEmpty) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(32),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Icon(
                      Icons.photo_library_outlined,
                      size: 64,
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                    ),
                    const SizedBox(height: 16),
                    Text(
                      'No photos yet',
                      style: Theme.of(context).textTheme.titleMedium,
                    ),
                    const SizedBox(height: 8),
                    Text(
                      'Photos you add to journal entries will appear here.',
                      style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            );
          }

          return GridView.builder(
            padding: const EdgeInsets.all(4),
            gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
              crossAxisCount: 3,
              crossAxisSpacing: 4,
              mainAxisSpacing: 4,
            ),
            itemCount: photos.length,
            itemBuilder: (context, index) {
              final photo = photos[index];
              return Semantics(
                label:
                    photo.description != null && photo.description!.isNotEmpty
                    ? 'Photo: ${photo.description}. Tap to open.'
                    : 'Photo ${index + 1} of ${photos.length}. Tap to open.',
                button: true,
                child: GestureDetector(
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (_) => PhotoViewer(
                          photoPath: photo.localPath,
                          caption: photo.description,
                          heroTag: 'photo-gallery-${photo.localPath}',
                        ),
                      ),
                    );
                  },
                  child: Hero(
                    tag: 'photo-gallery-${photo.localPath}',
                    child: Image.file(
                      File(photo.localPath),
                      fit: BoxFit.cover,
                      errorBuilder: (_, __, ___) => Container(
                        color: Theme.of(
                          context,
                        ).colorScheme.surfaceContainerHighest,
                        child: const Center(
                          child: Icon(Icons.broken_image, size: 32),
                        ),
                      ),
                    ),
                  ),
                ),
              );
            },
          );
        },
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (error, _) => Center(child: Text('Error: $error')),
      ),
    );
  }
}
