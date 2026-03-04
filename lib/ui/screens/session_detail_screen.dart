// ===========================================================================
// file: lib/ui/screens/session_detail_screen.dart
// purpose: Read-only view of a past session's full transcript.
//
// Shows all messages as chat bubbles (same as the active session screen)
// but without the text input field — this is a view-only screen.
// Includes a "Continue Entry" button to resume the session (ADR-0014).
// Tag chips (mood, people, topics) are editable inline (Phase 4A).
//
// Accessed by tapping a SessionCard in the session list screen.
// The session ID is passed as a route argument.
// ===========================================================================

import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../database/app_database.dart';
import '../../database/daos/message_dao.dart';
import '../../database/daos/photo_dao.dart';
import '../../database/daos/questionnaire_dao.dart';
import '../../database/daos/session_dao.dart';
import '../../database/daos/video_dao.dart';
import '../../providers/database_provider.dart';
import '../../providers/questionnaire_providers.dart';
import '../../providers/session_providers.dart';
import '../../providers/theme_providers.dart';
import '../../utils/timestamp_utils.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/photo_viewer.dart';
import '../widgets/pulse_check_in_summary.dart';
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
  CheckInResponseWithAnswers? _checkInResponse;
  List<QuestionnaireItem> _checkInItems = [];
  bool _isLoading = true;
  bool _isResuming = false;
  bool _isRegenerating = false;

  // Editable tag state (Phase 4A).  Lists are mutable so chip callbacks can
  // modify them in-place and call setState to trigger a rebuild.
  List<String> _moodTags = [];
  List<String> _people = [];
  List<String> _topicTags = [];

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  /// Load the session, messages, photos, and check-in data from the database.
  Future<void> _loadData() async {
    final db = ref.read(databaseProvider);
    final sessionDao = SessionDao(db);
    final messageDao = MessageDao(db);
    final photoDao = PhotoDao(db);
    final videoDao = VideoDao(db);
    final questionnaireDao = ref.read(questionnaireDaoProvider);

    final session = await sessionDao.getSessionById(widget.sessionId);
    final messages = await messageDao.getMessagesForSession(widget.sessionId);
    final photos = await photoDao.getPhotosForSession(widget.sessionId);
    final videos = await videoDao.getVideosForSession(widget.sessionId);

    // Load check-in response for this session (null if none).
    final checkInResponse = await questionnaireDao.getResponseForSession(
      widget.sessionId,
    );
    List<QuestionnaireItem> checkInItems = [];
    if (checkInResponse != null) {
      final template = await questionnaireDao.getTemplateById(
        checkInResponse.response.templateId,
      );
      if (template != null) {
        checkInItems = await questionnaireDao.getActiveItemsForTemplate(
          template.id,
        );
      }
    }

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
        _checkInResponse = checkInResponse;
        _checkInItems = checkInItems;
        _isLoading = false;
        // Parse tag columns from JSON arrays (Phase 4A).
        if (session != null) {
          _moodTags = _parseJsonArray(session.moodTags);
          _people = _parseJsonArray(session.people);
          _topicTags = _parseJsonArray(session.topicTags);
        }
      });
    }
  }

  /// Decode a nullable JSON-array column into a mutable list of strings.
  ///
  /// Returns an empty list for null, empty, or malformed values — never throws.
  static List<String> _parseJsonArray(String? jsonStr) {
    if (jsonStr == null || jsonStr.isEmpty) return [];
    try {
      final decoded = jsonDecode(jsonStr);
      if (decoded is List) {
        return List<String>.from(decoded.whereType<String>());
      }
      return [];
    } on FormatException {
      return [];
    }
  }

  // ---------------------------------------------------------------------------
  // Tag editing helpers (Phase 4A)
  // ---------------------------------------------------------------------------

  /// Persist all three tag lists to the database.
  ///
  /// Encodes each list as a JSON array, or null when empty (consistent with
  /// the format written by [SessionDao.endSession] and AI metadata extraction).
  Future<void> _saveTags() async {
    final db = ref.read(databaseProvider);
    final sessionDao = SessionDao(db);
    await sessionDao.updateSessionTags(
      widget.sessionId,
      moodTags: _moodTags.isEmpty ? null : jsonEncode(_moodTags),
      people: _people.isEmpty ? null : jsonEncode(_people),
      topicTags: _topicTags.isEmpty ? null : jsonEncode(_topicTags),
    );
  }

  /// Remove [tag] from [list] and persist.  Called by InputChip.onDeleted.
  void _deleteTag(String tag, List<String> list) {
    setState(() => list.remove(tag));
    _saveTags(); // fire-and-forget; local SQLite write is low-risk
  }

  /// Open an add-tag dialog and append the entered value to [list].
  ///
  /// The TextEditingController is created inside the builder callback so it
  /// stays valid during the pop animation.  Disposing outside the builder
  /// causes 'TextEditingController used after dispose' crashes (same pattern
  /// as the fix applied to settings_screen.dart in PR #71).
  Future<void> _showAddTagDialog(List<String> list) async {
    final added = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final controller = TextEditingController();
        return AlertDialog(
          title: const Text('Add tag'),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(hintText: 'Enter tag'),
            textCapitalization: TextCapitalization.words,
            onSubmitted: (v) => Navigator.of(ctx).pop(v.trim()),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
              child: const Text('Add'),
            ),
          ],
        );
      },
    );
    if (added != null && added.isNotEmpty && !list.contains(added)) {
      setState(() => list.add(added));
      await _saveTags();
    }
  }

  /// Open an edit-tag dialog pre-filled with [tag] and replace it in [list].
  ///
  /// Controller created inside the builder for the same reason as
  /// [_showAddTagDialog] — avoids dispose-during-animation crashes.
  Future<void> _showEditTagDialog(String tag, List<String> list) async {
    final edited = await showDialog<String>(
      context: context,
      builder: (ctx) {
        final controller = TextEditingController(text: tag);
        return AlertDialog(
          title: const Text('Edit tag'),
          content: TextField(
            controller: controller,
            autofocus: true,
            decoration: const InputDecoration(hintText: 'Enter tag'),
            textCapitalization: TextCapitalization.words,
            onSubmitted: (v) => Navigator.of(ctx).pop(v.trim()),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(),
              child: const Text('Cancel'),
            ),
            TextButton(
              onPressed: () => Navigator.of(ctx).pop(controller.text.trim()),
              child: const Text('Save'),
            ),
          ],
        );
      },
    );
    if (edited != null && edited.isNotEmpty && edited != tag) {
      setState(() {
        final index = list.indexOf(tag);
        if (index >= 0) list[index] = edited;
      });
      await _saveTags();
    }
  }

  // ---------------------------------------------------------------------------
  // Message editing (Phase 4F — voice transcription correction)
  // ---------------------------------------------------------------------------

  /// Long-press a USER message to open an edit sheet.
  ///
  /// On save: updates the DB, reloads the transcript, and regenerates the
  /// AI session summary so the metadata reflects the corrected content.
  Future<void> _showEditMessageSheet(JournalMessage message) async {
    final edited = await showModalBottomSheet<String>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) {
        // Controller created inside builder to avoid dispose-during-animation
        // crashes (same pattern as _showAddTagDialog / PR #71).
        final controller = TextEditingController(text: message.content);
        return Padding(
          padding: EdgeInsets.only(
            left: 16,
            right: 16,
            top: 16,
            bottom: MediaQuery.of(ctx).viewInsets.bottom + 24,
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Edit message', style: Theme.of(ctx).textTheme.titleMedium),
              const SizedBox(height: 12),
              TextField(
                controller: controller,
                autofocus: true,
                maxLines: null,
                decoration: const InputDecoration(
                  border: OutlineInputBorder(),
                  hintText: 'Message text',
                ),
              ),
              const SizedBox(height: 12),
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton(
                    onPressed: () => Navigator.of(ctx).pop(),
                    child: const Text('Cancel'),
                  ),
                  const SizedBox(width: 8),
                  FilledButton(
                    onPressed: () =>
                        Navigator.of(ctx).pop(controller.text.trim()),
                    child: const Text('Save'),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );

    // B3: reject null, empty, or unchanged edits before any DB write.
    if (edited == null ||
        edited.isEmpty ||
        edited == message.content ||
        !mounted) {
      return;
    }

    final db = ref.read(databaseProvider);
    final messageDao = MessageDao(db);
    await messageDao.updateMessageContent(message.messageId, edited);

    // Reload the transcript so the edited bubble is visible immediately.
    await _loadData();

    // Regenerate summary to reflect corrected content.
    // B2: wrap in try/finally for loading state and try/catch for API errors.
    if (!mounted) return;
    setState(() => _isRegenerating = true);
    try {
      await _regenerateSummary();
    } on Exception {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Summary could not be updated — try again later.'),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _isRegenerating = false);
    }
  }

  /// Re-run AI summary generation for a past session and persist the result.
  ///
  /// Called after a message edit so the displayed summary and metadata stay
  /// consistent with the (corrected) transcript.
  Future<void> _regenerateSummary() async {
    final db = ref.read(databaseProvider);
    final messageDao = MessageDao(db);
    final sessionDao = SessionDao(db);
    final agent = ref.read(agentRepositoryProvider);

    final messages = await messageDao.getMessagesForSession(widget.sessionId);
    final userMessages = messages
        .where((m) => m.role == 'USER')
        .map((m) => m.content)
        .toList();

    if (userMessages.isEmpty) return;

    // Reconstruct the full conversation transcript for context.
    final allMessages = messages
        .where((m) => m.role == 'USER' || m.role == 'ASSISTANT')
        .map((m) => {'role': m.role.toLowerCase(), 'content': m.content})
        .toList();

    final response = await agent.generateSummary(
      userMessages: userMessages,
      allMessages: allMessages,
    );

    final metadata = response.metadata;

    // B1: when Claude metadata is absent (rule-based fallback or offline),
    // preserve the existing tag columns by writing back the in-memory state
    // rather than passing null. Passing null to updateSessionMetadata writes
    // Value(null) to the DB column, silently wiping user-edited or AI-extracted
    // tags. Only update tag columns when Claude returns structured metadata.
    final String? newMoodTags;
    final String? newPeople;
    final String? newTopicTags;
    if (metadata != null) {
      newMoodTags = metadata.moodTags != null
          ? jsonEncode(metadata.moodTags)
          : null;
      newPeople = metadata.people != null ? jsonEncode(metadata.people) : null;
      newTopicTags = metadata.topicTags != null
          ? jsonEncode(metadata.topicTags)
          : null;
    } else {
      // Preserve whatever the user last loaded — don't clobber with null.
      newMoodTags = _moodTags.isEmpty ? null : jsonEncode(_moodTags);
      newPeople = _people.isEmpty ? null : jsonEncode(_people);
      newTopicTags = _topicTags.isEmpty ? null : jsonEncode(_topicTags);
    }

    await sessionDao.updateSessionMetadata(
      widget.sessionId,
      summary:
          metadata?.summary ??
          (response.content.isNotEmpty ? response.content : null),
      moodTags: newMoodTags,
      people: newPeople,
      topicTags: newTopicTags,
    );

    // Reload to show the updated summary header.
    if (mounted) await _loadData();
  }

  // ---------------------------------------------------------------------------
  // Tag section widget (Phase 4A)
  // ---------------------------------------------------------------------------

  /// Render the three editable tag rows (Mood, People, Topics).
  ///
  /// Each row has [InputChip]s for existing tags (tap to edit, ×  to remove)
  /// and an [IconButton] to add a new tag.  Rows are always shown so users
  /// can add tags even when the AI extracted none.
  Widget _buildTagSection() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildTagRow('Mood', _moodTags),
          _buildTagRow('People', _people),
          _buildTagRow('Topics', _topicTags),
        ],
      ),
    );
  }

  Widget _buildTagRow(String label, List<String> tags) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.center,
        children: [
          SizedBox(
            width: 56,
            child: Text(
              label,
              style: Theme.of(context).textTheme.labelSmall?.copyWith(
                color: Theme.of(context).colorScheme.onSurfaceVariant,
              ),
            ),
          ),
          Expanded(
            child: Wrap(
              spacing: 4,
              runSpacing: 4,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                ...tags.map(
                  (tag) => InputChip(
                    label: Text(tag),
                    onPressed: () => _showEditTagDialog(tag, tags),
                    onDeleted: () => _deleteTag(tag, tags),
                    // Unique per-tag tooltip so tests can find each delete
                    // button with find.byTooltip('Remove <tag>').
                    deleteButtonTooltipMessage: 'Remove $tag',
                    visualDensity: VisualDensity.compact,
                  ),
                ),
                IconButton(
                  icon: const Icon(Icons.add, size: 20),
                  tooltip: 'Add $label tag',
                  onPressed: () => _showAddTagDialog(tags),
                ),
              ],
            ),
          ),
        ],
      ),
    );
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
          // Shows a subtle spinner while summary regeneration is in progress.
          if (_isRegenerating)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              child: Row(
                children: [
                  const SizedBox(
                    width: 14,
                    height: 14,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  ),
                  const SizedBox(width: 8),
                  Text(
                    'Updating summary\u2026',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ],
              ),
            )
          else if (session.summary != null)
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

          // Editable tag chips (Phase 4A) — mood, people, topics.
          // Always shown so users can add tags even when AI extracted none.
          _buildTagSection(),

          // Pulse Check-In summary — shown when a check-in was recorded for
          // this session (Task 7 / Phase 1 summary card in detail view).
          if (_checkInResponse != null && _checkInItems.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 8),
              child: PulseCheckInSummary(
                responseWithAnswers: _checkInResponse!,
                items: _checkInItems,
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
                      final bubble = ChatBubble(
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
                        bubbleShape: ref.watch(themeProvider).bubbleShape,
                      );
                      // USER messages are long-press editable to correct voice
                      // transcription errors (e.g. "Shawn" vs "Sean").
                      if (msg.role == 'USER') {
                        return GestureDetector(
                          onLongPress: () => _showEditMessageSheet(msg),
                          child: bubble,
                        );
                      }
                      return bubble;
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
