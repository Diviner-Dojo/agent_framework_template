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
// ===========================================================================

import 'package:flutter/material.dart';

/// App-wide theme configuration.
///
/// Usage in MaterialApp:
///   theme: AppTheme.light,
///   darkTheme: AppTheme.dark,
///   themeMode: ThemeMode.system,  // Follows device setting
class AppTheme {
  // Private constructor — this class only has static members.
  AppTheme._(); // coverage:ignore-line

  // =========================================================================
  // Color palette
  // =========================================================================

  /// Primary seed color — a calming teal-blue.
  /// Material 3 generates a full color scheme from this seed.
  static const Color _seedColor = Color(0xFF5B8A9A);

  /// User chat bubble color (light theme).
  static const Color userBubbleLight = Color(0xFF5B8A9A);

  /// User chat bubble color (dark theme).
  static const Color userBubbleDark = Color(0xFF3D6B7A);

  /// Assistant chat bubble color (light theme).
  static const Color assistantBubbleLight = Color(0xFFE8EDF0);

  /// Assistant chat bubble color (dark theme).
  static const Color assistantBubbleDark = Color(0xFF2A3036);

  // =========================================================================
  // Light theme
  // =========================================================================

  /// Light theme — used when device is in light mode.
  static final ThemeData light = ThemeData(
    useMaterial3: true,
    // ColorScheme.fromSeed generates a harmonious palette from one color.
    colorScheme: ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: Brightness.light,
    ),
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
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    ),
    // FAB styling for the "new session" button.
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  );

  // =========================================================================
  // Dark theme
  // =========================================================================

  /// Dark theme — used when device is in dark mode.
  static final ThemeData dark = ThemeData(
    useMaterial3: true,
    colorScheme: ColorScheme.fromSeed(
      seedColor: _seedColor,
      brightness: Brightness.dark,
    ),
    appBarTheme: const AppBarTheme(centerTitle: true, elevation: 0),
    cardTheme: CardThemeData(
      elevation: 1,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      border: OutlineInputBorder(
        borderRadius: BorderRadius.circular(24),
        borderSide: BorderSide.none,
      ),
      contentPadding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
    ),
    floatingActionButtonTheme: FloatingActionButtonThemeData(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
    ),
  );
}
