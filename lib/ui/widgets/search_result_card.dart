// ===========================================================================
// file: lib/ui/widgets/search_result_card.dart
// purpose: Card widget for displaying a search result in the results list.
//
// Shows: date, duration, matched snippet with keyword bolded, match source
// label, mood/people/topic chips. Tapping navigates to the session detail.
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

import 'dart:convert';

import 'package:flutter/material.dart';

import '../../models/search_models.dart';
import '../../utils/timestamp_utils.dart';

/// A card displaying a single search result.
///
/// Shows the session date, duration, and a snippet of matching content with
/// the search keyword bolded. Metadata chips (mood, people, topics) are
/// displayed when present. The match source (Summary vs. Conversation) helps
/// the user understand where the match was found.
class SearchResultCard extends StatelessWidget {
  /// The search result item to display.
  final SearchResultItem item;

  /// The search query (used for keyword bolding in snippets).
  final String query;

  /// Called when the card is tapped.
  final VoidCallback? onTap;

  const SearchResultCard({
    super.key,
    required this.item,
    required this.query,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final session = item.session;
    final duration = session.endTime?.difference(session.startTime);

    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Top row: date, duration, match source label.
              Row(
                children: [
                  Text(
                    formatShortDate(session.startTime),
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  if (duration != null) ...[
                    const SizedBox(width: 8),
                    Text(
                      formatDuration(duration),
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                  const Spacer(),
                  _MatchSourceLabel(source: item.matchSource),
                ],
              ),
              const SizedBox(height: 8),

              // Matched snippet with keyword bolded.
              if (item.matchingSnippets.isNotEmpty) ...[
                _BoldedSnippet(
                  snippet: item.matchingSnippets.first,
                  query: query,
                ),
                const SizedBox(height: 8),
              ] else if (session.summary != null) ...[
                Text(
                  session.summary!,
                  style: theme.textTheme.bodyMedium,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                ),
                const SizedBox(height: 8),
              ],

              // Metadata chips.
              _MetadataChips(session: session),
            ],
          ),
        ),
      ),
    );
  }
}

/// Label showing whether the match came from summary or conversation.
class _MatchSourceLabel extends StatelessWidget {
  final MatchSource source;

  const _MatchSourceLabel({required this.source});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final label = switch (source) {
      MatchSource.summary => 'Summary',
      MatchSource.message => 'Conversation',
    };

    return Text(
      label,
      style: theme.textTheme.bodySmall?.copyWith(
        color: theme.colorScheme.onSurfaceVariant,
      ),
    );
  }
}

/// Displays a text snippet with the search query keyword bolded.
///
/// Performs case-insensitive matching to find and bold the keyword.
/// If the query is not found in the snippet, displays the snippet as-is.
class _BoldedSnippet extends StatelessWidget {
  final String snippet;
  final String query;

  const _BoldedSnippet({required this.snippet, required this.query});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final spans = _buildBoldSpans(
      snippet,
      query,
      theme.textTheme.bodyMedium ?? const TextStyle(),
    );

    return RichText(
      text: TextSpan(children: spans),
      maxLines: 3,
      overflow: TextOverflow.ellipsis,
    );
  }

  /// Build a list of TextSpans with the keyword bolded.
  static List<TextSpan> _buildBoldSpans(
    String text,
    String query,
    TextStyle baseStyle,
  ) {
    if (query.trim().isEmpty) {
      return [TextSpan(text: text, style: baseStyle)];
    }

    final spans = <TextSpan>[];
    final lowerText = text.toLowerCase();
    final lowerQuery = query.toLowerCase();
    var start = 0;

    while (start < text.length) {
      final matchIndex = lowerText.indexOf(lowerQuery, start);
      if (matchIndex == -1) {
        // No more matches — add remaining text.
        spans.add(TextSpan(text: text.substring(start), style: baseStyle));
        break;
      }

      // Add text before the match.
      if (matchIndex > start) {
        spans.add(
          TextSpan(text: text.substring(start, matchIndex), style: baseStyle),
        );
      }

      // Add the matched keyword in bold. Use lowerQuery.length (not
      // query.length) because toLowerCase() can change string length
      // for certain Unicode characters.
      spans.add(
        TextSpan(
          text: text.substring(matchIndex, matchIndex + lowerQuery.length),
          style: baseStyle.copyWith(fontWeight: FontWeight.bold),
        ),
      );

      start = matchIndex + lowerQuery.length;
    }

    return spans;
  }
}

/// Row of metadata chips (mood, people, topics) for a session.
class _MetadataChips extends StatelessWidget {
  final dynamic session;

  const _MetadataChips({required this.session});

  @override
  Widget build(BuildContext context) {
    final chips = <Widget>[];

    // Parse JSON array strings into lists.
    final moods = _parseJsonArray(session.moodTags);
    final people = _parseJsonArray(session.people);
    final topics = _parseJsonArray(session.topicTags);

    for (final mood in moods.take(2)) {
      chips.add(_SmallChip(label: mood, icon: Icons.emoji_emotions_outlined));
    }
    for (final person in people.take(2)) {
      chips.add(_SmallChip(label: person, icon: Icons.person_outline));
    }
    for (final topic in topics.take(2)) {
      chips.add(_SmallChip(label: topic, icon: Icons.label_outline));
    }

    if (chips.isEmpty) return const SizedBox.shrink();

    return Wrap(spacing: 6, runSpacing: 4, children: chips);
  }

  /// Parse a JSON array string into a list, or return empty list on failure.
  static List<String> _parseJsonArray(String? jsonStr) {
    if (jsonStr == null || jsonStr.isEmpty) return [];
    try {
      final decoded = jsonDecode(jsonStr);
      if (decoded is List) {
        return decoded.whereType<String>().toList();
      }
    } on FormatException {
      // Not valid JSON — return empty.
    }
    return [];
  }
}

/// A compact chip for displaying metadata (mood, person, topic).
class _SmallChip extends StatelessWidget {
  final String label;
  final IconData icon;

  const _SmallChip({required this.label, required this.icon});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: theme.colorScheme.onSurfaceVariant),
          const SizedBox(width: 4),
          Text(
            label,
            style: theme.textTheme.labelSmall?.copyWith(
              color: theme.colorScheme.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
