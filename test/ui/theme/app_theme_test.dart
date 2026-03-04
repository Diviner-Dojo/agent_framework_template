import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/theme/app_theme.dart';
import 'package:agentic_journal/ui/theme/palettes.dart';

void main() {
  group('AppTheme', () {
    test('light theme uses Material 3', () {
      expect(AppTheme.light.useMaterial3, isTrue);
    });

    test('dark theme uses Material 3', () {
      expect(AppTheme.dark.useMaterial3, isTrue);
    });

    test('light theme has light brightness', () {
      expect(AppTheme.light.brightness, Brightness.light);
    });

    test('dark theme has dark brightness', () {
      expect(AppTheme.dark.brightness, Brightness.dark);
    });
  });

  group('AppTheme.fromPalette', () {
    test('generates light theme from palette', () {
      final palette = getPaletteById('forest_floor');
      final theme = AppTheme.fromPalette(palette, Brightness.light);
      expect(theme.useMaterial3, isTrue);
      expect(theme.brightness, Brightness.light);
    });

    test('generates dark theme from palette', () {
      final palette = getPaletteById('midnight_ink');
      final theme = AppTheme.fromPalette(palette, Brightness.dark);
      expect(theme.useMaterial3, isTrue);
      expect(theme.brightness, Brightness.dark);
    });

    test('includes ChatBubbleColors extension', () {
      final palette = getPaletteById('still_water');
      final theme = AppTheme.fromPalette(palette, Brightness.light);
      final ext = theme.extension<ChatBubbleColors>();
      expect(ext, isNotNull);
      expect(ext!.userBubble, isNotNull);
      expect(ext.assistantBubble, isNotNull);
      expect(ext.userText, isNotNull);
      expect(ext.assistantText, isNotNull);
    });

    test('bubble colors derive from colorScheme', () {
      final palette = getPaletteById('ember_glow');
      final theme = AppTheme.fromPalette(palette, Brightness.light);
      final ext = theme.extension<ChatBubbleColors>()!;
      // User bubble should be the primary color.
      expect(ext.userBubble, theme.colorScheme.primary);
      // User text should be onPrimary.
      expect(ext.userText, theme.colorScheme.onPrimary);
      // Assistant text should be onSurface.
      expect(ext.assistantText, theme.colorScheme.onSurface);
    });

    test('different palettes produce different themes', () {
      final stillWater = AppTheme.fromPalette(
        getPaletteById('still_water'),
        Brightness.light,
      );
      final midnightInk = AppTheme.fromPalette(
        getPaletteById('midnight_ink'),
        Brightness.light,
      );
      expect(
        stillWater.colorScheme.primary,
        isNot(equals(midnightInk.colorScheme.primary)),
      );
    });

    test('applies standard card theme', () {
      final palette = getPaletteById('still_water');
      final theme = AppTheme.fromPalette(palette, Brightness.light);
      expect(theme.cardTheme.elevation, 1);
    });
  });

  group('AppTheme.withCardElevation', () {
    test('overrides card elevation', () {
      final base = AppTheme.fromPalette(
        getPaletteById('still_water'),
        Brightness.light,
      );
      final flat = AppTheme.withCardElevation(base, 0);
      expect(flat.cardTheme.elevation, 0);

      final raised = AppTheme.withCardElevation(base, 3);
      expect(raised.cardTheme.elevation, 3);
    });

    test('preserves other theme properties', () {
      final base = AppTheme.fromPalette(
        getPaletteById('still_water'),
        Brightness.light,
      );
      final modified = AppTheme.withCardElevation(base, 0);
      expect(modified.useMaterial3, base.useMaterial3);
      expect(modified.colorScheme.primary, base.colorScheme.primary);
    });
  });

  group('ChatBubbleColors', () {
    test('copyWith replaces individual fields', () {
      const colors = ChatBubbleColors(
        userBubble: Colors.blue,
        assistantBubble: Colors.grey,
        userText: Colors.white,
        assistantText: Colors.black,
      );
      final updated = colors.copyWith(userBubble: Colors.red);
      expect(updated.userBubble, Colors.red);
      expect(updated.assistantBubble, Colors.grey);
    });

    test('lerp interpolates at t=0', () {
      const a = ChatBubbleColors(
        userBubble: Color(0xFF0000FF),
        assistantBubble: Color(0xFF888888),
        userText: Color(0xFFFFFFFF),
        assistantText: Color(0xFF000000),
      );
      const b = ChatBubbleColors(
        userBubble: Color(0xFFFF0000),
        assistantBubble: Color(0xFF00FF00),
        userText: Color(0xFFFFFF00),
        assistantText: Color(0xFF800080),
      );
      final result = a.lerp(b, 0);
      expect(result.userBubble, const Color(0xFF0000FF));
    });

    test('lerp interpolates at t=1', () {
      const a = ChatBubbleColors(
        userBubble: Color(0xFF0000FF),
        assistantBubble: Color(0xFF888888),
        userText: Color(0xFFFFFFFF),
        assistantText: Color(0xFF000000),
      );
      const b = ChatBubbleColors(
        userBubble: Color(0xFFFF0000),
        assistantBubble: Color(0xFF00FF00),
        userText: Color(0xFFFFFF00),
        assistantText: Color(0xFF800080),
      );
      final result = a.lerp(b, 1);
      expect(result.userBubble, const Color(0xFFFF0000));
    });

    test('lerp returns self when other is null-typed', () {
      const a = ChatBubbleColors(
        userBubble: Color(0xFF0000FF),
        assistantBubble: Color(0xFF888888),
        userText: Color(0xFFFFFFFF),
        assistantText: Color(0xFF000000),
      );
      final result = a.lerp(null, 0.5);
      expect(result.userBubble, const Color(0xFF0000FF));
    });
  });
}
