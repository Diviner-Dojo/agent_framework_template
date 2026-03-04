import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:agentic_journal/providers/onboarding_providers.dart'
    show sharedPreferencesProvider;
import 'package:agentic_journal/providers/theme_providers.dart';
import 'package:agentic_journal/ui/theme/palettes.dart';

void main() {
  group('ThemeState', () {
    test('defaults match expected values', () {
      const state = ThemeState();
      expect(state.paletteId, 'still_water');
      expect(state.themeMode, ThemeMode.system);
      expect(state.fontScale, FontScale.defaultScale);
      expect(state.cardStyle, CardStyle.soft);
      expect(state.bubbleShape, BubbleShape.rounded);
      expect(state.showDecorations, true);
    });

    test('copyWith replaces individual fields', () {
      const state = ThemeState();
      final updated = state.copyWith(
        paletteId: 'midnight_ink',
        themeMode: ThemeMode.dark,
      );
      expect(updated.paletteId, 'midnight_ink');
      expect(updated.themeMode, ThemeMode.dark);
      // Unchanged fields.
      expect(updated.fontScale, FontScale.defaultScale);
      expect(updated.cardStyle, CardStyle.soft);
      expect(updated.bubbleShape, BubbleShape.rounded);
    });

    test('equality works correctly', () {
      const a = ThemeState();
      const b = ThemeState();
      expect(a, equals(b));
      expect(a.hashCode, b.hashCode);

      final c = a.copyWith(paletteId: 'warm_earth');
      expect(a, isNot(equals(c)));
    });

    test('palette getter resolves to AppPalette', () {
      const state = ThemeState(paletteId: 'forest_floor');
      expect(state.palette.name, 'Forest Floor');
    });

    test('palette getter falls back for unknown ID', () {
      const state = ThemeState(paletteId: 'deleted_palette');
      expect(state.palette.id, defaultPaletteId);
    });

    test('fontScaleFactor computes correctly', () {
      const state = ThemeState(fontScale: FontScale.large);
      // 1.0 + 0.15 = 1.15
      expect(state.fontScaleFactor(1.0), closeTo(1.15, 0.001));
    });

    test('fontScaleFactor clamps at minimum 0.8', () {
      const state = ThemeState(fontScale: FontScale.small);
      // 0.5 + (-0.1) = 0.4, clamped to 0.8
      expect(state.fontScaleFactor(0.5), 0.8);
    });

    test('fontScaleFactor clamps at maximum 2.0', () {
      const state = ThemeState(fontScale: FontScale.extraLarge);
      // 2.0 + 0.3 = 2.3, clamped to 2.0
      expect(state.fontScaleFactor(2.0), 2.0);
    });
  });

  group('ThemeNotifier', () {
    late ProviderContainer container;

    setUp(() {
      SharedPreferences.setMockInitialValues({});
    });

    Future<ProviderContainer> createContainer({
      Map<String, Object>? initialPrefs,
    }) async {
      if (initialPrefs != null) {
        SharedPreferences.setMockInitialValues(initialPrefs);
      }
      final prefs = await SharedPreferences.getInstance();
      final c = ProviderContainer(
        overrides: [sharedPreferencesProvider.overrideWithValue(prefs)],
      );
      return c;
    }

    tearDown(() {
      container.dispose();
    });

    test('build() with empty prefs returns defaults', () async {
      container = await createContainer();
      final state = container.read(themeProvider);
      expect(state, equals(ThemeState.defaults));
    });

    test('build() with all keys set returns stored values', () async {
      container = await createContainer(
        initialPrefs: {
          'theme_palette_id': 'ember_glow',
          'theme_mode': 'dark',
          'theme_font_scale': 'large',
          'theme_card_style': 'raised',
          'theme_bubble_shape': 'pill',
          'theme_show_decorations': false,
        },
      );
      final state = container.read(themeProvider);
      expect(state.paletteId, 'ember_glow');
      expect(state.themeMode, ThemeMode.dark);
      expect(state.fontScale, FontScale.large);
      expect(state.cardStyle, CardStyle.raised);
      expect(state.bubbleShape, BubbleShape.pill);
      expect(state.showDecorations, false);
    });

    test('build() with partial prefs defaults unset axes', () async {
      container = await createContainer(
        initialPrefs: {'theme_palette_id': 'midnight_ink'},
      );
      final state = container.read(themeProvider);
      expect(state.paletteId, 'midnight_ink');
      expect(state.themeMode, ThemeMode.system);
      expect(state.fontScale, FontScale.defaultScale);
      expect(state.cardStyle, CardStyle.soft);
    });

    test('build() with invalid enum value returns default', () async {
      container = await createContainer(
        initialPrefs: {
          'theme_font_scale': 'gigantic',
          'theme_mode': 'rainbow',
          'theme_card_style': 'invisible',
          'theme_bubble_shape': 'hexagon',
        },
      );
      final state = container.read(themeProvider);
      expect(state.fontScale, FontScale.defaultScale);
      expect(state.themeMode, ThemeMode.system);
      expect(state.cardStyle, CardStyle.soft);
      expect(state.bubbleShape, BubbleShape.rounded);
    });

    test('selectPalette updates state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);
      await notifier.selectPalette('warm_earth');

      expect(container.read(themeProvider).paletteId, 'warm_earth');

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('theme_palette_id'), 'warm_earth');
    });

    test('setThemeMode updates state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);
      await notifier.setThemeMode(ThemeMode.light);

      expect(container.read(themeProvider).themeMode, ThemeMode.light);

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('theme_mode'), 'light');
    });

    test('setFontScale updates state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);
      await notifier.setFontScale(FontScale.extraLarge);

      expect(container.read(themeProvider).fontScale, FontScale.extraLarge);
    });

    test('setCardStyle updates state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);
      await notifier.setCardStyle(CardStyle.flat);

      expect(container.read(themeProvider).cardStyle, CardStyle.flat);
    });

    test('setBubbleShape updates state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);
      await notifier.setBubbleShape(BubbleShape.pill);

      expect(container.read(themeProvider).bubbleShape, BubbleShape.pill);
    });

    test('resetToDefaults returns previous state and sets defaults', () async {
      container = await createContainer(
        initialPrefs: {
          'theme_palette_id': 'ember_glow',
          'theme_mode': 'dark',
          'theme_font_scale': 'large',
          'theme_card_style': 'raised',
          'theme_bubble_shape': 'pill',
          'theme_show_decorations': false,
        },
      );

      final stateBefore = container.read(themeProvider);
      expect(stateBefore.paletteId, 'ember_glow');

      final notifier = container.read(themeProvider.notifier);
      final previous = await notifier.resetToDefaults();

      expect(previous, equals(stateBefore));
      expect(container.read(themeProvider), equals(ThemeState.defaults));

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('theme_palette_id'), isNull);
      expect(prefs.getString('theme_mode'), isNull);
    });

    test('restore restores previous state and persists', () async {
      container = await createContainer();
      final notifier = container.read(themeProvider.notifier);

      final customState = ThemeState(
        paletteId: 'forest_floor',
        themeMode: ThemeMode.light,
        fontScale: FontScale.large,
        cardStyle: CardStyle.raised,
        bubbleShape: BubbleShape.softSquare,
        showDecorations: false,
      );

      await notifier.restore(customState);

      expect(container.read(themeProvider), equals(customState));

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('theme_palette_id'), 'forest_floor');
      expect(prefs.getString('theme_mode'), 'light');
      expect(prefs.getString('theme_font_scale'), 'large');
      expect(prefs.getString('theme_card_style'), 'raised');
      expect(prefs.getString('theme_bubble_shape'), 'softSquare');
      expect(prefs.getBool('theme_show_decorations'), false);
    });
  });

  group('FontScale', () {
    test('all values have unique labels', () {
      final labels = FontScale.values.map((s) => s.label).toSet();
      expect(labels.length, FontScale.values.length);
    });

    test('offsets are ordered', () {
      final offsets = FontScale.values.map((s) => s.offset).toList();
      for (var i = 1; i < offsets.length; i++) {
        expect(offsets[i], greaterThan(offsets[i - 1]));
      }
    });
  });

  group('CardStyle', () {
    test('all values have unique labels', () {
      final labels = CardStyle.values.map((s) => s.label).toSet();
      expect(labels.length, CardStyle.values.length);
    });

    test('elevations are non-negative and ordered', () {
      final elevations = CardStyle.values.map((s) => s.elevation).toList();
      for (final e in elevations) {
        expect(e, greaterThanOrEqualTo(0));
      }
      for (var i = 1; i < elevations.length; i++) {
        expect(elevations[i], greaterThan(elevations[i - 1]));
      }
    });
  });
}
