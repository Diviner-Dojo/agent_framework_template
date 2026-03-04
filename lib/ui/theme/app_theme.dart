// ===========================================================================
// file: lib/ui/theme/app_theme.dart
// purpose: Material 3 theme definitions for the app.
//
// Design choice: Calming, journaling-appropriate colors.
//   - Light theme: Soft blue-grey tones with warm accents
//   - Dark theme: Muted dark surfaces with the same accent palette
//
// Both themes use Material 3 (useMaterial3: true) which provides
// modern, rounded components and dynamic color support.
//
// The fromPalette() factory builds ThemeData from any AppPalette,
// enabling dynamic theme switching. The static light/dark getters
// are convenience wrappers for the default "Still Water" palette.
//
// See: SPEC-20260304-063144 (Visual Identity & Theme Personalization)
// ===========================================================================

import 'package:flutter/material.dart';

import '../../providers/theme_providers.dart' show CardStyle;
import 'palettes.dart';

/// Chat bubble colors that vary per palette.
///
/// This [ThemeExtension] allows chat bubbles to derive their colors from
/// the active palette via [Theme.of(context).extension<ChatBubbleColors>()],
/// instead of hardcoded static constants.
class ChatBubbleColors extends ThemeExtension<ChatBubbleColors> {
  /// Background color for user-sent message bubbles.
  final Color userBubble;

  /// Background color for assistant message bubbles.
  final Color assistantBubble;

  /// Text color for user-sent message bubbles.
  final Color userText;

  /// Text color for assistant message bubbles.
  final Color assistantText;

  const ChatBubbleColors({
    required this.userBubble,
    required this.assistantBubble,
    required this.userText,
    required this.assistantText,
  });

  @override
  ChatBubbleColors copyWith({
    Color? userBubble,
    Color? assistantBubble,
    Color? userText,
    Color? assistantText,
  }) {
    return ChatBubbleColors(
      userBubble: userBubble ?? this.userBubble,
      assistantBubble: assistantBubble ?? this.assistantBubble,
      userText: userText ?? this.userText,
      assistantText: assistantText ?? this.assistantText,
    );
  }

  @override
  ChatBubbleColors lerp(ChatBubbleColors? other, double t) {
    if (other is! ChatBubbleColors) return this;
    return ChatBubbleColors(
      userBubble: Color.lerp(userBubble, other.userBubble, t)!,
      assistantBubble: Color.lerp(assistantBubble, other.assistantBubble, t)!,
      userText: Color.lerp(userText, other.userText, t)!,
      assistantText: Color.lerp(assistantText, other.assistantText, t)!,
    );
  }
}

/// App-wide theme configuration.
///
/// Usage in MaterialApp:
///   theme: AppTheme.light,
///   darkTheme: AppTheme.dark,
///   themeMode: ThemeMode.system,  // Follows device setting
///
/// For dynamic theming with palettes:
///   theme: AppTheme.fromPalette(palette, Brightness.light),
///   darkTheme: AppTheme.fromPalette(palette, Brightness.dark),
class AppTheme {
  // Private constructor — this class only has static members.
  AppTheme._(); // coverage:ignore-line

  // =========================================================================
  // Default palette reference
  // =========================================================================

  static final AppPalette _defaultPalette = getPaletteById(defaultPaletteId);

  // =========================================================================
  // Factory method — builds ThemeData from any palette
  // =========================================================================

  /// Build a [ThemeData] from the given [palette] and [brightness].
  ///
  /// This is the primary entry point for dynamic theming. The palette's
  /// seed color generates a full [ColorScheme] via Material 3, and
  /// component-level theme customizations (cards, inputs, FAB) are applied
  /// on top.
  static ThemeData fromPalette(AppPalette palette, Brightness brightness) {
    final colorScheme = brightness == Brightness.light
        ? palette.lightScheme()
        : palette.darkScheme();

    final isLight = brightness == Brightness.light;

    // Derive chat bubble colors from the palette's color scheme.
    final bubbleColors = ChatBubbleColors(
      userBubble: colorScheme.primary,
      assistantBubble: isLight
          ? colorScheme.surfaceContainerHighest
          : colorScheme.surfaceContainerHigh,
      userText: colorScheme.onPrimary,
      assistantText: colorScheme.onSurface,
    );

    return ThemeData(
      useMaterial3: true,
      colorScheme: colorScheme,
      // App bar styling — slightly elevated with surface tint.
      appBarTheme: const AppBarTheme(centerTitle: true, elevation: 0),
      // Card styling for session cards.
      cardTheme: CardThemeData(
        elevation: 1,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
        margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      ),
      // Input field styling for the chat text field.
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(24),
          borderSide: BorderSide.none,
        ),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: 20,
          vertical: 12,
        ),
      ),
      // FAB styling for the "new session" button.
      floatingActionButtonTheme: FloatingActionButtonThemeData(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      // Theme extensions for custom component colors.
      extensions: [bubbleColors],
    );
  }

  /// Build a [ThemeData] with the given [CardStyle] applied.
  ///
  /// Flat gets a 1dp outline border (visible without shadow on modern phones).
  /// Soft (2dp) and Raised (8dp) use shadow only — no border.
  static ThemeData withCardStyle(ThemeData base, CardStyle style) {
    final shape = style == CardStyle.flat
        ? RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(12),
            side: BorderSide(color: base.colorScheme.outlineVariant, width: 1),
          )
        : const RoundedRectangleBorder(
            borderRadius: BorderRadius.all(Radius.circular(12)),
          );
    return base.copyWith(
      cardTheme: base.cardTheme.copyWith(
        elevation: style.elevation,
        shape: shape,
      ),
    );
  }

  // =========================================================================
  // Convenience getters for the default palette
  // =========================================================================

  /// Light theme using the default "Still Water" palette.
  static final ThemeData light = fromPalette(_defaultPalette, Brightness.light);

  /// Dark theme using the default "Still Water" palette.
  static final ThemeData dark = fromPalette(_defaultPalette, Brightness.dark);
}
