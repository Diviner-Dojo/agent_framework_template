// ===========================================================================
// file: lib/ui/widgets/photo_capture_sheet.dart
// purpose: Modal bottom sheet for choosing photo source (camera or gallery).
//
// Shows two options:
//   1. "Take Photo" — launches the camera
//   2. "Choose from Gallery" — opens the photo picker
//
// Returns the selected source as an enum, or null if dismissed.
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'package:flutter/material.dart';

/// The source for a photo capture action.
enum PhotoSource {
  /// Take a new photo using the device camera.
  camera,

  /// Pick an existing photo from the device gallery.
  gallery,
}

/// Show the photo source selection bottom sheet.
///
/// Returns [PhotoSource.camera] or [PhotoSource.gallery],
/// or null if the user dismisses the sheet.
Future<PhotoSource?> showPhotoCaptureSheet(BuildContext context) {
  return showModalBottomSheet<PhotoSource>(
    context: context,
    builder: (context) => const _PhotoCaptureSheet(),
  );
}

class _PhotoCaptureSheet extends StatelessWidget {
  const _PhotoCaptureSheet();

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
              onTap: () => Navigator.of(context).pop(PhotoSource.camera),
            ),
            ListTile(
              leading: const Icon(Icons.photo_library),
              title: const Text('Choose from Gallery'),
              onTap: () => Navigator.of(context).pop(PhotoSource.gallery),
            ),
          ],
        ),
      ),
    );
  }
}
