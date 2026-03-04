import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/onboarding_providers.dart'
    show sharedPreferencesProvider;
import 'package:agentic_journal/providers/theme_providers.dart';
import 'package:agentic_journal/ui/theme/app_theme.dart';

void main() {
  group('MaterialApp theme wiring', () {
    testWidgets('theme provider drives MaterialApp theme', (tester) async {
      SharedPreferences.setMockInitialValues({
        'theme_palette_id': 'midnight_ink',
        'theme_mode': 'dark',
        'onboarding_complete': true,
      });
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
          child: Consumer(
            builder: (context, ref, _) {
              final themeState = ref.watch(themeProvider);
              final palette = themeState.palette;
              return MaterialApp(
                theme: AppTheme.fromPalette(palette, Brightness.light),
                darkTheme: AppTheme.fromPalette(palette, Brightness.dark),
                themeMode: themeState.themeMode,
                home: Builder(
                  builder: (context) {
                    return Scaffold(
                      body: Column(
                        children: [
                          Text('palette:${themeState.paletteId}'),
                          Text('mode:${themeState.themeMode.name}'),
                        ],
                      ),
                    );
                  },
                ),
              );
            },
          ),
        ),
      );

      expect(find.text('palette:midnight_ink'), findsOneWidget);
      expect(find.text('mode:dark'), findsOneWidget);
    });

    testWidgets('default theme uses still_water with system mode', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({'onboarding_complete': true});
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
          child: Consumer(
            builder: (context, ref, _) {
              final themeState = ref.watch(themeProvider);
              return MaterialApp(
                home: Scaffold(body: Text('palette:${themeState.paletteId}')),
              );
            },
          ),
        ),
      );

      expect(find.text('palette:still_water'), findsOneWidget);
    });

    testWidgets('card elevation reflects cardStyle preference', (tester) async {
      SharedPreferences.setMockInitialValues({
        'theme_card_style': 'flat',
        'onboarding_complete': true,
      });
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
          child: Consumer(
            builder: (context, ref, _) {
              final themeState = ref.watch(themeProvider);
              final palette = themeState.palette;
              final theme = AppTheme.withCardElevation(
                AppTheme.fromPalette(palette, Brightness.light),
                themeState.cardStyle.elevation,
              );
              return MaterialApp(
                theme: theme,
                home: Builder(
                  builder: (context) {
                    final cardElevation = Theme.of(context).cardTheme.elevation;
                    return Scaffold(body: Text('elevation:$cardElevation'));
                  },
                ),
              );
            },
          ),
        ),
      );

      expect(find.text('elevation:0.0'), findsOneWidget);
    });

    testWidgets('ChatBubbleColors extension is accessible from theme', (
      tester,
    ) async {
      SharedPreferences.setMockInitialValues({'onboarding_complete': true});
      final prefs = await SharedPreferences.getInstance();

      await tester.pumpWidget(
        ProviderScope(
          overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
          child: Consumer(
            builder: (context, ref, _) {
              final themeState = ref.watch(themeProvider);
              final palette = themeState.palette;
              return MaterialApp(
                theme: AppTheme.fromPalette(palette, Brightness.light),
                home: Builder(
                  builder: (context) {
                    final ext = Theme.of(context).extension<ChatBubbleColors>();
                    return Scaffold(
                      body: Text(
                        ext != null ? 'has_extension' : 'no_extension',
                      ),
                    );
                  },
                ),
              );
            },
          ),
        ),
      );

      expect(find.text('has_extension'), findsOneWidget);
    });
  });
}
