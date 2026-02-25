// ===========================================================================
// file: lib/ui/screens/session_detail_screen.dart
// purpose: Read-only view of a past session's full transcript.
//
// Shows all messages as chat bubbles (same as the active session screen)
// but without the text input field — this is a view-only screen.
// Includes a "Continue Entry" button to resume the session (ADR-0014).
//
// Accessed by tapping a SessionCard in the session list screen.
// The session ID is passed as a route argument.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../database/daos/message_dao.dart';
import '../../database/daos/photo_dao.dart';
import '../../database/daos/session_dao.dart';
import '../../database/daos/video_dao.dart';
import '../../providers/database_provider.dart';
import '../../providers/session_providers.dart';
import '../../utils/timestamp_utils.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/photo_viewer.dart';
import '../widgets/video_player_widget.dart';

/// Read-only transcript view for a past session.
class SessionDetailScreen extends ConsumerStatefulWidget {
  final String sessionId;

  const SessionDetailScreen({super.key, required this.sessionId});

  @override
  ConsumerState<SessionDetailScreen> createState() =>
      _SessionDetailScreenState();
}

class _SessionDetailScreenState extends ConsumerState<SessionDetailScreen> {
  JournalSession? _session;
  List<JournalMessage>? _messages;
  Map<String, Photo> _photosByMessageId = {};
  Map<String, Video> _videosByVideoId = {};
  bool _isLoading = true;
  bool _isResuming = false;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  /// Load the session, messages, and photos from the database.
  Future<void> _loadData() async {
    final db = ref.read(databaseProvider);
    final sessionDao = SessionDao(db);
    final messageDao = MessageDao(db);
    final photoDao = PhotoDao(db);
    final videoDao = VideoDao(db);

    final session = await sessionDao.getSessionById(widget.sessionId);
    final messages = await messageDao.getMessagesForSession(widget.sessionId);
    final photos = await photoDao.getPhotosForSession(widget.sessionId);
    final videos = await videoDao.getVideosForSession(widget.sessionId);

    // Index photos by messageId for fast lookup.
    final photoMap = <String, Photo>{};
    for (final photo in photos) {
      if (photo.messageId != null) {
        photoMap[photo.messageId!] = photo;
      }
    }

    // Index videos by videoId for fast lookup.
    final videoMap = <String, Video>{};
    for (final video in videos) {
      videoMap[video.videoId] = video;
    }

    if (mounted) {
      setState(() {
        _session = session;
        _messages = messages;
        _photosByMessageId = photoMap;
        _videosByVideoId = videoMap;
        _isLoading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    // Watch active session to know if another session is in progress.
    final activeSessionId = ref.watch(activeSessionIdProvider);

    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Session')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_session == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Session')),
        body: const Center(child: Text('Session not found.')),
      );
    }

    final session = _session!;
    final messages = _messages ?? [];
    // Show Continue Entry if this session has an endTime (completed)
    // and no other session is currently active.
    final canResume = session.endTime != null && activeSessionId == null;

    return Scaffold(
      appBar: AppBar(
        title: Text(formatShortDate(session.startTime)),
        actions: [
          if (canResume)
            _isResuming
                ? const Padding(
                    padding: EdgeInsets.all(12),
                    child: SizedBox(
                      width: 20,
                      height: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    ),
                  )
                : TextButton(
                    onPressed: () => _resumeSession(context),
                    child: const Text('Continue Entry'),
                  ),
        ],
      ),
      body: Column(
        children: [
          // Session summary header (if available).
          if (session.summary != null)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: Theme.of(context).colorScheme.surfaceContainerHighest,
              child: Text(
                session.summary!,
                style: Theme.of(
                  context,
                ).textTheme.bodyMedium?.copyWith(fontStyle: FontStyle.italic),
              ),
            ),

          // Location pill (Phase 10 — ADR-0019).
          if (session.locationName != null)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Chip(
                  avatar: Icon(
                    Icons.location_on_outlined,
                    size: 18,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                  label: Text(session.locationName!),
                  visualDensity: VisualDensity.compact,
                ),
              ),
            ),

          // Message list — the full conversation transcript.
          Expanded(
            child: messages.isEmpty
                ? const Center(child: Text('No messages in this session.'))
                : ListView.builder(
                    padding: const EdgeInsets.only(top: 8, bottom: 16),
                    itemCount: messages.length,
                    itemBuilder: (context, index) {
                      final msg = messages[index];
                      final photo = msg.photoId != null
                          ? _photosByMessageId[msg.messageId]
                          : null;
                      final video = msg.videoId != null
                          ? _videosByVideoId[msg.videoId!]
                          : null;
                      return ChatBubble(
                        content: msg.content,
                        role: msg.role,
                        timestamp: msg.timestamp,
                        photoPath: photo?.localPath,
                        photoCaption: photo?.description,
                        photoHeroPrefix: 'photo-detail',
                        onPhotoTap: photo != null
                            ? () => _openPhotoViewer(photo)
                            : null,
                        videoThumbnailPath: video?.thumbnailPath,
                        videoDuration: video?.durationSeconds,
                        onVideoTap: video != null
                            ? () => showVideoPlayer(
                                context: context,
                                videoPath: video.localPath,
                              )
                            : null,
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }

  /// Open the full-screen photo viewer.
  void _openPhotoViewer(Photo photo) {
    Navigator.of(context).push(
      MaterialPageRoute(
        builder: (context) => PhotoViewer(
          photoPath: photo.localPath,
          caption: photo.description,
          heroTag: 'photo-detail-${photo.localPath}',
        ),
      ),
    );
  }

  /// Resume the session and navigate to the active session screen.
  Future<void> _resumeSession(BuildContext context) async {
    setState(() => _isResuming = true);
    try {
      final notifier = ref.read(sessionNotifierProvider.notifier);
      final resumed = await notifier.resumeSession(widget.sessionId);
      if (resumed != null && context.mounted) {
        // Replace this detail screen with the active session screen.
        Navigator.of(context).pushReplacementNamed('/session');
      }
    } finally {
      if (mounted) {
        setState(() => _isResuming = false);
      }
    }
  }
}
