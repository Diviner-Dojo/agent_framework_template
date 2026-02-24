// ===========================================================================
// file: lib/ui/widgets/photo_preview_dialog.dart
// purpose: Preview dialog shown after a photo is captured/picked.
//
// Shows the photo with "Add" and "Cancel" buttons. While the photo is
// being processed (EXIF strip + resize + compress), shows a progress
// indicator overlay.
//
// See: ADR-0018 (Photo Storage Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter/material.dart';

/// Show the photo preview dialog.
///
/// Returns true if the user taps "Add", false if "Cancel" or dismissed.
Future<bool> showPhotoPreviewDialog({
  required BuildContext context,
  required File photoFile,
  bool isProcessing = false,
}) async {
  final result = await showDialog<bool>(
    context: context,
    barrierDismissible: !isProcessing,
    builder: (context) =>
        _PhotoPreviewDialog(photoFile: photoFile, isProcessing: isProcessing),
  );
  return result ?? false;
}

class _PhotoPreviewDialog extends StatelessWidget {
  final File photoFile;
  final bool isProcessing;

  const _PhotoPreviewDialog({
    required this.photoFile,
    required this.isProcessing,
  });

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      contentPadding: const EdgeInsets.fromLTRB(12, 16, 12, 0),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // Photo preview.
          ClipRRect(
            borderRadius: BorderRadius.circular(8),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 400),
              child: Image.file(photoFile, fit: BoxFit.contain),
            ),
          ),
          if (isProcessing)
            const Padding(
              padding: EdgeInsets.only(top: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  SizedBox(
                    width: 16,
                    height: 16,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  SizedBox(width: 8),
                  Text('Processing...'),
                ],
              ),
            ),
        ],
      ),
      actions: [
        TextButton(
          onPressed: isProcessing
              ? null
              : () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: isProcessing
              ? null
              : () => Navigator.of(context).pop(true),
          child: const Text('Add'),
        ),
      ],
    );
  }
}
