// ===========================================================================
// file: lib/ui/screens/onboarding_screen.dart
// purpose: First-launch onboarding flow that explains the app and guides
//          the user to set it as the default digital assistant.
//
// Structure:
//   A PageView with 3 pages and dot indicators:
//     Page 1: Welcome — introduces the app concept
//     Page 2: Assistant Setup — guides the user to set as default assistant
//     Page 3: Ready — lets the user start their first journal entry
//
// Navigation:
//   - "Skip" button always visible in the app bar (skips to session list)
//   - "Next" button advances pages
//   - "Begin Journaling" on the last page completes onboarding
//   - All exits (skip, begin) call completeOnboarding() and navigate away
//
// The onboarding flag is persisted via SharedPreferences so this screen
// only shows once — see onboarding_providers.dart for the state management.
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../providers/onboarding_providers.dart';
import '../../providers/session_providers.dart';
import '../../providers/settings_providers.dart';

/// First-launch onboarding screen.
class OnboardingScreen extends ConsumerStatefulWidget {
  const OnboardingScreen({super.key});

  @override
  ConsumerState<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends ConsumerState<OnboardingScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  /// The total number of onboarding pages.
  static const _pageCount = 3;

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      // "Skip" button in the app bar — always available.
      appBar: AppBar(
        automaticallyImplyLeading: false,
        actions: [
          TextButton(
            onPressed: _completeAndNavigate,
            child: const Text('Skip'),
          ),
        ],
      ),
      body: Column(
        children: [
          // Page content — takes all available space.
          Expanded(
            child: PageView(
              controller: _pageController,
              onPageChanged: (page) => setState(() => _currentPage = page),
              children: [
                _buildWelcomePage(context),
                _buildAssistantSetupPage(context),
                _buildReadyPage(context),
              ],
            ),
          ),
          // Bottom navigation: dot indicators + next/begin button.
          _buildBottomNav(context),
        ],
      ),
    );
  }

  /// Page 1: Welcome — introduces the app concept.
  Widget _buildWelcomePage(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.book_outlined,
            size: 80,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 24),
          Text(
            'Welcome to Agentic Journal',
            style: Theme.of(context).textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            'Your AI-powered personal journal.\n'
            'Capture your thoughts through natural conversation.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  /// Page 2: Assistant Setup — guides the user to set as default assistant.
  Widget _buildAssistantSetupPage(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.touch_app_outlined,
            size: 80,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 24),
          Text(
            'Set Up Assistant Gesture',
            style: Theme.of(context).textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            'Long-press the Home button to start journaling instantly.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: () async {
              final service = ref.read(assistantServiceProvider);
              await service.openAssistantSettings();
            },
            icon: const Icon(Icons.settings),
            label: const Text('Set as Default Assistant'),
          ),
          const SizedBox(height: 12),
          Text(
            'You can always change this later in Settings.',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  /// Page 3: Ready — lets the user start their first journal entry.
  Widget _buildReadyPage(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 32),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            Icons.check_circle_outline,
            size: 80,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 24),
          Text(
            "You're All Set!",
            style: Theme.of(context).textTheme.headlineSmall,
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 16),
          Text(
            'Start your first journal entry.',
            style: Theme.of(context).textTheme.bodyLarge?.copyWith(
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 24),
          FilledButton.icon(
            onPressed: _completeAndNavigate,
            icon: const Icon(Icons.edit_note),
            label: const Text('Begin Journaling'),
          ),
        ],
      ),
    );
  }

  /// Build the bottom navigation with dot indicators and next button.
  Widget _buildBottomNav(BuildContext context) {
    final isLastPage = _currentPage == _pageCount - 1;

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 32),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          // Dot indicators showing current page position.
          Row(
            children: List.generate(
              _pageCount,
              (index) => Container(
                margin: const EdgeInsets.symmetric(horizontal: 4),
                width: index == _currentPage ? 12 : 8,
                height: 8,
                decoration: BoxDecoration(
                  color: index == _currentPage
                      ? Theme.of(context).colorScheme.primary
                      : Theme.of(
                          context,
                        ).colorScheme.onSurfaceVariant.withValues(alpha: 0.3),
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
            ),
          ),
          // Next or Begin button depending on the page.
          if (!isLastPage)
            FilledButton(
              onPressed: () {
                _pageController.nextPage(
                  duration: const Duration(milliseconds: 300),
                  curve: Curves.easeInOut,
                );
              },
              child: const Text('Next'),
            ),
        ],
      ),
    );
  }

  /// Complete onboarding and start the first journal session.
  ///
  /// Instead of navigating to the empty session list (where the user has to
  /// discover the FAB), this starts a session and lands directly in a
  /// conversation.
  Future<void> _completeAndNavigate() async {
    await ref.read(onboardingNotifierProvider.notifier).completeOnboarding();
    if (mounted) {
      await ref.read(sessionNotifierProvider.notifier).startSession();
      if (mounted) {
        Navigator.of(context).pushReplacementNamed('/session');
      }
    }
  }
}
