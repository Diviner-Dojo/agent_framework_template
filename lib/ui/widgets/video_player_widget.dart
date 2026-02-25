// ===========================================================================
// file: lib/ui/widgets/video_player_widget.dart
// purpose: Full-screen video playback widget with controls.
//
// Shows a video player with play/pause toggle and progress indicator.
// Presented as a full-screen modal when a video thumbnail is tapped
// in the session timeline.
//
// The VideoPlayerController lifecycle is managed by the widget:
//   - Initialized in initState
//   - Disposed in dispose
//
// See: ADR-0021 (Video Capture Architecture)
// ===========================================================================

import 'dart:io';

import 'package:flutter/material.dart';
import 'package:video_player/video_player.dart';

/// Show a full-screen video player modal.
///
/// [videoPath] is the absolute path to the video file on disk.
Future<void> showVideoPlayer({
  required BuildContext context,
  required String videoPath,
}) {
  return Navigator.of(context).push(
    MaterialPageRoute<void>(
      fullscreenDialog: true,
      builder: (context) => VideoPlayerScreen(videoPath: videoPath),
    ),
  );
}

/// Full-screen video player screen.
///
/// Owns the [VideoPlayerController] lifecycle — initializes on creation,
/// disposes on close. Shows a loading indicator until the video is ready.
class VideoPlayerScreen extends StatefulWidget {
  /// Absolute path to the video file on disk.
  final String videoPath;

  const VideoPlayerScreen({super.key, required this.videoPath});

  @override
  State<VideoPlayerScreen> createState() => _VideoPlayerScreenState();
}

class _VideoPlayerScreenState extends State<VideoPlayerScreen> {
  late VideoPlayerController _controller;
  bool _isInitialized = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _controller = VideoPlayerController.file(File(widget.videoPath))
      ..initialize()
          .then((_) {
            if (mounted) {
              setState(() {
                _isInitialized = true;
              });
              _controller.play();
            }
          })
          .catchError((Object error) {
            if (mounted) {
              setState(() {
                _error = 'Unable to play video.';
              });
            }
          });

    _controller.addListener(_onControllerUpdate);
  }

  void _onControllerUpdate() {
    if (mounted) {
      setState(() {});
    }
  }

  @override
  void dispose() {
    _controller.removeListener(_onControllerUpdate);
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        foregroundColor: Colors.white,
        title: const Text('Video'),
      ),
      body: Center(child: _buildContent()),
    );
  }

  Widget _buildContent() {
    if (_error != null) {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.error_outline, color: Colors.white, size: 48),
          const SizedBox(height: 16),
          Text(_error!, style: const TextStyle(color: Colors.white)),
        ],
      );
    }

    if (!_isInitialized) {
      return const CircularProgressIndicator(color: Colors.white);
    }

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Video display with aspect ratio.
        AspectRatio(
          aspectRatio: _controller.value.aspectRatio,
          child: VideoPlayer(_controller),
        ),
        const SizedBox(height: 16),
        // Progress indicator.
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: VideoProgressIndicator(
            _controller,
            allowScrubbing: true,
            colors: VideoProgressColors(
              playedColor: Theme.of(context).colorScheme.primary,
              bufferedColor: Colors.white24,
              backgroundColor: Colors.white12,
            ),
          ),
        ),
        const SizedBox(height: 8),
        // Time display.
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _formatDuration(_controller.value.position),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
              Text(
                _formatDuration(_controller.value.duration),
                style: const TextStyle(color: Colors.white70, fontSize: 12),
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),
        // Play/pause button.
        IconButton(
          iconSize: 48,
          color: Colors.white,
          icon: Icon(
            _controller.value.isPlaying
                ? Icons.pause_circle
                : Icons.play_circle,
          ),
          onPressed: () {
            setState(() {
              _controller.value.isPlaying
                  ? _controller.pause()
                  : _controller.play();
            });
          },
        ),
      ],
    );
  }

  /// Format a Duration as mm:ss.
  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    return '$minutes:$seconds';
  }
}
