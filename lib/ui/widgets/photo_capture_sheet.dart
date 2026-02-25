// ===========================================================================
// file: lib/ui/widgets/photo_capture_sheet.dart
// purpose: Modal bottom sheet for choosing media source (photo or video,
//          from camera or gallery).
//
// Shows four options:
//   1. "Take Photo" — launches the camera for a still photo
//   2. "Choose Photo from Gallery" — opens the photo picker
//   3. "Record Video" — launches the camera for video recording
//   4. "Choose Video from Gallery" — opens the video picker
//
// Returns the selected source as a MediaSource enum, or null if dismissed.
//
// See: ADR-0018 (Photo Storage Architecture), ADR-0021 (Video Capture)
// ===========================================================================

import 'package:flutter/material.dart';

/// The source for a media capture action.
///
/// Extended from PhotoSource in Phase 12 (ADR-0021) to include video options.
enum MediaSource {
  /// Take a new photo using the device camera.
  photoCamera,

  /// Pick an existing photo from the device gallery.
  photoGallery,

  /// Record a new video using the device camera.
  videoCamera,

  /// Pick an existing video from the device gallery.
  videoGallery,
}

/// Show the media source selection bottom sheet.
///
/// Returns a [MediaSource] value, or null if the user dismisses the sheet.
Future<MediaSource?> showMediaCaptureSheet(BuildContext context) {
  return showModalBottomSheet<MediaSource>(
    context: context,
    builder: (context) => const _MediaCaptureSheet(),
  );
}

/// Legacy alias for backward compatibility with existing callers.
///
/// Calls [showMediaCaptureSheet] internally.
Future<MediaSource?> showPhotoCaptureSheet(BuildContext context) {
  return showMediaCaptureSheet(context);
}

class _MediaCaptureSheet extends StatelessWidget {
  const _MediaCaptureSheet();

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Handle bar.
            Container(
              width: 32,
              height: 4,
              margin: const EdgeInsets.only(bottom: 16),
              decoration: BoxDecoration(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
            ListTile(
              leading: const Icon(Icons.camera_alt),
              title: const Text('Take Photo'),
              onTap: () => Navigator.of(context).pop(MediaSource.photoCamera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Choose Photo from Gallery'),
              onTap: () => Navigator.of(context).pop(MediaSource.photoGallery),
            ),
            const Divider(height: 1),
            ListTile(
              leading: const Icon(Icons.videocam),
              title: const Text('Record Video'),
              subtitle: const Text('Up to 60 seconds'),
              onTap: () => Navigator.of(context).pop(MediaSource.videoCamera),
            ),
            ListTile(
              leading: const Icon(Icons.video_library),
              title: const Text('Choose Video from Gallery'),
              onTap: () => Navigator.of(context).pop(MediaSource.videoGallery),
            ),
          ],
        ),
      ),
    );
  }
}
