// ===========================================================================
// file: lib/ui/screens/search_screen.dart
// purpose: Dedicated search screen for finding past journal entries.
//
// Features:
//   - Search bar with 300ms debounce
//   - Horizontal filter chips (date range, mood, people, topics)
//   - Three distinct empty states (pre-search, no results, no results + filters)
//   - Offline indicator banner
//   - Progressive disclosure: accessed via search icon at 5+ sessions
//
// See: ADR-0013 (Search + Memory Recall Architecture)
// ===========================================================================

import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../models/search_models.dart';
import '../../providers/search_providers.dart';
import '../../providers/session_providers.dart';
import '../widgets/search_result_card.dart';

/// Dedicated search screen for finding past journal entries.
///
/// Entry point: search icon in session list app bar (visible at 5+ sessions).
/// Search is secondary to journaling — this is a separate screen,
/// not a persistent search bar (per UX research).
class SearchScreen extends ConsumerStatefulWidget {
  const SearchScreen({super.key});

  @override
  ConsumerState<SearchScreen> createState() => _SearchScreenState();
}

class _SearchScreenState extends ConsumerState<SearchScreen> {
  final _searchController = TextEditingController();
  Timer? _debounceTimer;

  /// Duration for search debounce. Injectable for testing via constructor
  /// would require widget refactor — instead, test with pump(350ms).
  static const _debounceDuration = Duration(milliseconds: 300);

  @override
  void dispose() {
    _debounceTimer?.cancel();
    _searchController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String query) {
    _debounceTimer?.cancel();
    _debounceTimer = Timer(_debounceDuration, () {
      ref.read(searchQueryProvider.notifier).state = query;
    });
  }

  void _clearSearch() {
    _searchController.clear();
    ref.read(searchQueryProvider.notifier).state = '';
  }

  void _clearFilters() {
    ref.read(searchFiltersProvider.notifier).state = SearchFilters.empty;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final searchResults = ref.watch(searchResultsProvider);
    final filters = ref.watch(searchFiltersProvider);
    final query = ref.watch(searchQueryProvider);
    final connectivityService = ref.watch(connectivityServiceProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Search Journal')),
      body: Column(
        children: [
          // Search bar
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
            child: TextField(
              controller: _searchController,
              onChanged: _onSearchChanged,
              decoration: InputDecoration(
                hintText: 'Search entries...',
                prefixIcon: const Icon(Icons.search),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear),
                        onPressed: _clearSearch,
                      )
                    : null,
              ),
            ),
          ),

          // Filter chips
          _FilterChipRow(filters: filters, onClearFilters: _clearFilters),

          // Offline banner
          if (!connectivityService.isOnline)
            Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
              color: theme.colorScheme.surfaceContainerHighest,
              child: Row(
                children: [
                  Icon(
                    Icons.cloud_off,
                    size: 16,
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      'Searching local data \u00B7 Natural language recall unavailable offline',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ),
                ],
              ),
            ),

          // Results / empty state
          Expanded(
            child: searchResults.when(
              data: (results) =>
                  _buildResultsBody(context, results, query, filters),
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => Center(
                child: Text(
                  'Something went wrong. Try searching again.',
                  style: theme.textTheme.bodyMedium,
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildResultsBody(
    BuildContext context,
    SearchResults results,
    String query,
    SearchFilters filters,
  ) {
    final theme = Theme.of(context);

    // Pre-search state: no query entered yet.
    if (query.trim().isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.search,
              size: 64,
              color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
            ),
            const SizedBox(height: 16),
            Text('Search your journal', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Find entries by keyword, date, mood, or people',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      );
    }

    // No results with filters active.
    if (results.isEmpty && filters.hasActiveFilters) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.filter_list_off,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
            ),
            const SizedBox(height: 16),
            Text(
              'No entries match your filters',
              style: theme.textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            Text(
              'Try different keywords or adjust your filters',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: 16),
            TextButton.icon(
              onPressed: _clearFilters,
              icon: const Icon(Icons.clear_all),
              label: const Text('Clear filters'),
            ),
          ],
        ),
      );
    }

    // No results without filters.
    if (results.isEmpty) {
      return Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.search_off,
              size: 48,
              color: theme.colorScheme.onSurfaceVariant.withValues(alpha: 0.4),
            ),
            const SizedBox(height: 16),
            Text('No entries found', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(
              'Try different keywords',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurfaceVariant,
              ),
            ),
          ],
        ),
      );
    }

    // Results list.
    return ListView.builder(
      padding: const EdgeInsets.only(bottom: 16),
      itemCount: results.count,
      itemBuilder: (context, index) {
        final item = results.items[index];
        return SearchResultCard(
          item: item,
          query: results.query,
          onTap: () {
            // Navigate to session detail.
            Navigator.of(
              context,
            ).pushNamed('/session/detail', arguments: item.sessionId);
          },
        );
      },
    );
  }
}

/// Horizontally scrollable filter chips.
class _FilterChipRow extends ConsumerWidget {
  final SearchFilters filters;
  final VoidCallback onClearFilters;

  const _FilterChipRow({required this.filters, required this.onClearFilters});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        children: [
          Expanded(
            child: SingleChildScrollView(
              scrollDirection: Axis.horizontal,
              child: Row(
                children: [
                  _buildFilterChip(
                    context,
                    ref,
                    label: filters.dateStart != null ? 'Date range' : 'Date',
                    icon: Icons.calendar_today,
                    isActive:
                        filters.dateStart != null || filters.dateEnd != null,
                    onTap: () => _showDateRangePicker(context, ref),
                  ),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    context,
                    ref,
                    label: 'Mood',
                    icon: Icons.emoji_emotions_outlined,
                    isActive: filters.moodTags?.isNotEmpty == true,
                    onTap: () => _showMultiSelectSheet(
                      context,
                      ref,
                      title: 'Mood',
                      provider: availableMoodTagsProvider,
                      selected: filters.moodTags ?? [],
                      onSelected: (tags) {
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: filters.dateStart,
                          dateEnd: filters.dateEnd,
                          moodTags: tags.isEmpty ? null : tags,
                          people: filters.people,
                          topicTags: filters.topicTags,
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    context,
                    ref,
                    label: 'People',
                    icon: Icons.people_outline,
                    isActive: filters.people?.isNotEmpty == true,
                    onTap: () => _showMultiSelectSheet(
                      context,
                      ref,
                      title: 'People',
                      provider: availablePeopleProvider,
                      selected: filters.people ?? [],
                      onSelected: (tags) {
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: filters.dateStart,
                          dateEnd: filters.dateEnd,
                          moodTags: filters.moodTags,
                          people: tags.isEmpty ? null : tags,
                          topicTags: filters.topicTags,
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  _buildFilterChip(
                    context,
                    ref,
                    label: 'Topics',
                    icon: Icons.label_outline,
                    isActive: filters.topicTags?.isNotEmpty == true,
                    onTap: () => _showMultiSelectSheet(
                      context,
                      ref,
                      title: 'Topics',
                      provider: availableTopicTagsProvider,
                      selected: filters.topicTags ?? [],
                      onSelected: (tags) {
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: filters.dateStart,
                          dateEnd: filters.dateEnd,
                          moodTags: filters.moodTags,
                          people: filters.people,
                          topicTags: tags.isEmpty ? null : tags,
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ),
          // Clear all button when filters are active.
          if (filters.hasActiveFilters) ...[
            const SizedBox(width: 8),
            IconButton(
              icon: const Icon(Icons.clear_all, size: 20),
              onPressed: onClearFilters,
              tooltip: 'Clear all filters',
              visualDensity: VisualDensity.compact,
            ),
          ],
        ],
      ),
    );
  }

  Widget _buildFilterChip(
    BuildContext context,
    WidgetRef ref, {
    required String label,
    required IconData icon,
    required bool isActive,
    required VoidCallback onTap,
  }) {
    final theme = Theme.of(context);
    return FilterChip(
      avatar: Icon(icon, size: 16),
      label: Text(label),
      selected: isActive,
      onSelected: (_) => onTap(),
      selectedColor: theme.colorScheme.primaryContainer,
    );
  }

  Future<void> _showDateRangePicker(BuildContext context, WidgetRef ref) async {
    final theme = Theme.of(context);
    final filters = ref.read(searchFiltersProvider);

    await showModalBottomSheet<void>(
      context: context,
      builder: (context) {
        return SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Date Range', style: theme.textTheme.titleMedium),
                const SizedBox(height: 16),
                // Presets
                Wrap(
                  spacing: 8,
                  children: [
                    _DatePresetChip(
                      label: 'Last 7 days',
                      onTap: () {
                        final now = DateTime.now();
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: now.subtract(const Duration(days: 7)),
                          dateEnd: now,
                          moodTags: filters.moodTags,
                          people: filters.people,
                          topicTags: filters.topicTags,
                        );
                        Navigator.pop(context);
                      },
                    ),
                    _DatePresetChip(
                      label: 'Last 30 days',
                      onTap: () {
                        final now = DateTime.now();
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: now.subtract(const Duration(days: 30)),
                          dateEnd: now,
                          moodTags: filters.moodTags,
                          people: filters.people,
                          topicTags: filters.topicTags,
                        );
                        Navigator.pop(context);
                      },
                    ),
                    _DatePresetChip(
                      label: 'This year',
                      onTap: () {
                        final now = DateTime.now();
                        ref
                            .read(searchFiltersProvider.notifier)
                            .state = SearchFilters(
                          dateStart: DateTime(now.year),
                          dateEnd: now,
                          moodTags: filters.moodTags,
                          people: filters.people,
                          topicTags: filters.topicTags,
                        );
                        Navigator.pop(context);
                      },
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                // Custom date range button
                OutlinedButton.icon(
                  onPressed: () async {
                    Navigator.pop(context);
                    final range = await showDateRangePicker(
                      context: context,
                      firstDate: DateTime(2020),
                      lastDate: DateTime.now(),
                    );
                    if (range != null) {
                      ref
                          .read(searchFiltersProvider.notifier)
                          .state = SearchFilters(
                        dateStart: range.start,
                        dateEnd: range.end,
                        moodTags: filters.moodTags,
                        people: filters.people,
                        topicTags: filters.topicTags,
                      );
                    }
                  },
                  icon: const Icon(Icons.date_range),
                  label: const Text('Custom range...'),
                ),
                if (filters.dateStart != null) ...[
                  const SizedBox(height: 8),
                  TextButton(
                    onPressed: () {
                      ref
                          .read(searchFiltersProvider.notifier)
                          .state = SearchFilters(
                        moodTags: filters.moodTags,
                        people: filters.people,
                        topicTags: filters.topicTags,
                      );
                      Navigator.pop(context);
                    },
                    child: const Text('Clear date filter'),
                  ),
                ],
              ],
            ),
          ),
        );
      },
    );
  }

  Future<void> _showMultiSelectSheet(
    BuildContext context,
    WidgetRef ref, {
    required String title,
    required FutureProvider<List<String>> provider,
    required List<String> selected,
    required void Function(List<String>) onSelected,
  }) async {
    await showModalBottomSheet<void>(
      context: context,
      builder: (context) {
        return _MultiSelectSheet(
          title: title,
          provider: provider,
          selected: selected,
          onSelected: (tags) {
            onSelected(tags);
            Navigator.pop(context);
          },
        );
      },
    );
  }
}

/// Date preset chip for the date range bottom sheet.
class _DatePresetChip extends StatelessWidget {
  final String label;
  final VoidCallback onTap;

  const _DatePresetChip({required this.label, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return ActionChip(label: Text(label), onPressed: onTap);
  }
}

/// Multi-select bottom sheet for mood/people/topic filters.
class _MultiSelectSheet extends ConsumerStatefulWidget {
  final String title;
  final FutureProvider<List<String>> provider;
  final List<String> selected;
  final void Function(List<String>) onSelected;

  const _MultiSelectSheet({
    required this.title,
    required this.provider,
    required this.selected,
    required this.onSelected,
  });

  @override
  ConsumerState<_MultiSelectSheet> createState() => _MultiSelectSheetState();
}

class _MultiSelectSheetState extends ConsumerState<_MultiSelectSheet> {
  late Set<String> _selected;

  @override
  void initState() {
    super.initState();
    _selected = Set.from(widget.selected);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final availableAsync = ref.watch(widget.provider);

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text(widget.title, style: theme.textTheme.titleMedium),
                TextButton(
                  onPressed: () => widget.onSelected(_selected.toList()),
                  child: const Text('Apply'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            availableAsync.when(
              data: (items) {
                if (items.isEmpty) {
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 24),
                    child: Center(
                      child: Text(
                        'No ${widget.title.toLowerCase()} tags found.\n'
                        'Open a past session and add tags using the chip editor.',
                        textAlign: TextAlign.center,
                        style: theme.textTheme.bodyMedium?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ),
                  );
                }
                return Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: items.map((item) {
                    final isSelected = _selected.contains(item);
                    return FilterChip(
                      label: Text(item),
                      selected: isSelected,
                      onSelected: (selected) {
                        setState(() {
                          if (selected) {
                            _selected.add(item);
                          } else {
                            _selected.remove(item);
                          }
                        });
                      },
                    );
                  }).toList(),
                );
              },
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, _) => const Text('Failed to load options'),
            ),
          ],
        ),
      ),
    );
  }
}
