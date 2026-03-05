// ===========================================================================
// file: lib/providers/theme_providers.dart
// purpose: Theme state management with SharedPreferences persistence.
//
// Uses the modern Notifier/NotifierProvider API (not legacy StateNotifier)
// following the pattern established in onboarding_providers.dart and
// voice_providers.dart.
//
// ThemeState bundles all visual customization settings into a single
// cohesive state object — palette, theme mode, font scale, card style,
// bubble shape, and decoration toggle. This is intentionally a composite
// state (vs. individual notifiers per setting as in voice_providers.dart)
// because all settings are configured on the same screen and affect the
// same visual output.
//
// ADR-0029 evaluated: ref.watch() on this provider feeding MaterialApp
// theme/darkTheme/themeMode is safe — theme changes trigger animated
// transitions, not Navigator stack collapses (unlike initialRoute).
//
// See: SPEC-20260304-063144 (Visual Identity & Theme Personalization)
// ===========================================================================

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../ui/theme/palettes.dart';
import 'onboarding_providers.dart' show sharedPreferencesProvider;

// ===========================================================================
// SharedPreferences keys
// ===========================================================================

const _paletteKey = 'theme_palette_id';
const _themeModeKey = 'theme_mode';
const _fontScaleKey = 'theme_font_scale';
const _cardStyleKey = 'theme_card_style';
const _bubbleShapeKey = 'theme_bubble_shape';
const _showDecorationsKey = 'theme_show_decorations';

// ===========================================================================
// Enums
// ===========================================================================

/// Font scale options. Applied as additive offsets to the system text scale,
/// clamped at a maximum effective scale of 2.0.
enum FontScale {
  small('Small', -0.1),
  defaultScale('Default', 0.0),
  large('Large', 0.15),
  extraLarge('Extra Large', 0.3);

  const FontScale(this.label, this.offset);

  /// User-facing label for the settings UI.
  final String label;

  /// Additive offset applied to the system text scale factor.
  final double offset;
}

/// Card elevation style options.
enum CardStyle {
  flat('Flat', 0),
  soft('Soft', 2),
  raised('Raised', 8);

  const CardStyle(this.label, this.elevation);

  /// User-facing label for the settings UI.
  final String label;

  /// Card elevation value in logical pixels.
  final double elevation;
}

/// Chat bubble border radius shape options.
enum BubbleShape {
  rounded('Rounded'),
  softSquare('Soft Square'),
  pill('Pill');

  const BubbleShape(this.label);

  /// User-facing label for the settings UI.
  final String label;
}

// ===========================================================================
// ThemeState
// ===========================================================================

/// Immutable state representing all theme customization settings.
class ThemeState {
  /// The active palette ID (maps to [AppPalette.id]).
  final String paletteId;

  /// Light/dark mode preference.
  final ThemeMode themeMode;

  /// Font scale preference.
  final FontScale fontScale;

  /// Card elevation style.
  final CardStyle cardStyle;

  /// Chat bubble border radius shape.
  final BubbleShape bubbleShape;

  /// Whether Phase 5B decorative elements are shown.
  final bool showDecorations;

  const ThemeState({
    this.paletteId = 'still_water',
    this.themeMode = ThemeMode.system,
    this.fontScale = FontScale.defaultScale,
    this.cardStyle = CardStyle.soft,
    this.bubbleShape = BubbleShape.rounded,
    this.showDecorations = true,
  });

  /// The active [AppPalette] resolved from [paletteId].
  AppPalette get palette => getPaletteById(paletteId);

  /// Create a copy with the given fields replaced.
  ThemeState copyWith({
    String? paletteId,
    ThemeMode? themeMode,
    FontScale? fontScale,
    CardStyle? cardStyle,
    BubbleShape? bubbleShape,
    bool? showDecorations,
  }) {
    return ThemeState(
      paletteId: paletteId ?? this.paletteId,
      themeMode: themeMode ?? this.themeMode,
      fontScale: fontScale ?? this.fontScale,
      cardStyle: cardStyle ?? this.cardStyle,
      bubbleShape: bubbleShape ?? this.bubbleShape,
      showDecorations: showDecorations ?? this.showDecorations,
    );
  }

  /// The default state matching the app's original appearance.
  static const defaults = ThemeState();

  /// Compute the effective font scale factor by combining the user's
  /// preference with the system text scale. Clamped at 0.8–2.0.
  double fontScaleFactor(double systemScale) {
    return (systemScale + fontScale.offset).clamp(0.8, 2.0);
  }

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is ThemeState &&
          runtimeType == other.runtimeType &&
          paletteId == other.paletteId &&
          themeMode == other.themeMode &&
          fontScale == other.fontScale &&
          cardStyle == other.cardStyle &&
          bubbleShape == other.bubbleShape &&
          showDecorations == other.showDecorations;

  @override
  int get hashCode => Object.hash(
    paletteId,
    themeMode,
    fontScale,
    cardStyle,
    bubbleShape,
    showDecorations,
  );
}

// ===========================================================================
// ThemeNotifier
// ===========================================================================

/// Manages theme customization state with SharedPreferences persistence.
///
/// Each setting axis is read independently from SharedPreferences with
/// its own default, so a partial write (e.g., crash mid-save) leaves
/// unwritten axes at their defaults rather than corrupting the whole state.
class ThemeNotifier extends Notifier<ThemeState> {
  @override
  ThemeState build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return ThemeState(
      paletteId: prefs.getString(_paletteKey) ?? defaultPaletteId,
      themeMode: _readThemeMode(prefs.getString(_themeModeKey)),
      fontScale: _readEnum(
        prefs.getString(_fontScaleKey),
        FontScale.values,
        FontScale.defaultScale,
      ),
      cardStyle: _readEnum(
        prefs.getString(_cardStyleKey),
        CardStyle.values,
        CardStyle.soft,
      ),
      bubbleShape: _readEnum(
        prefs.getString(_bubbleShapeKey),
        BubbleShape.values,
        BubbleShape.rounded,
      ),
      showDecorations: prefs.getBool(_showDecorationsKey) ?? true,
    );
  }

  /// Select a color palette by its [id].
  Future<void> selectPalette(String paletteId) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_paletteKey, paletteId);
    state = state.copyWith(paletteId: paletteId);
  }

  /// Set the light/dark mode preference.
  Future<void> setThemeMode(ThemeMode mode) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_themeModeKey, mode.name);
    state = state.copyWith(themeMode: mode);
  }

  /// Set the font scale preference.
  Future<void> setFontScale(FontScale scale) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_fontScaleKey, scale.name);
    state = state.copyWith(fontScale: scale);
  }

  /// Set the card elevation style.
  Future<void> setCardStyle(CardStyle style) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_cardStyleKey, style.name);
    state = state.copyWith(cardStyle: style);
  }

  /// Set the chat bubble border radius shape.
  Future<void> setBubbleShape(BubbleShape shape) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_bubbleShapeKey, shape.name);
    state = state.copyWith(bubbleShape: shape);
  }

  /// Toggle Phase 5B decorative elements.
  Future<void> setShowDecorations(bool show) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setBool(_showDecorationsKey, show);
    state = state.copyWith(showDecorations: show);
  }

  /// Reset all theme settings to factory defaults.
  ///
  /// Returns the previous state so callers can implement an "Undo" action.
  Future<ThemeState> resetToDefaults() async {
    final previous = state;
    final prefs = ref.read(sharedPreferencesProvider);
    await Future.wait([
      prefs.remove(_paletteKey),
      prefs.remove(_themeModeKey),
      prefs.remove(_fontScaleKey),
      prefs.remove(_cardStyleKey),
      prefs.remove(_bubbleShapeKey),
      prefs.remove(_showDecorationsKey),
    ]);
    state = ThemeState.defaults;
    return previous;
  }

  /// Restore a previously saved state (for "Undo" after reset).
  Future<void> restore(ThemeState previous) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await Future.wait([
      prefs.setString(_paletteKey, previous.paletteId),
      prefs.setString(_themeModeKey, previous.themeMode.name),
      prefs.setString(_fontScaleKey, previous.fontScale.name),
      prefs.setString(_cardStyleKey, previous.cardStyle.name),
      prefs.setString(_bubbleShapeKey, previous.bubbleShape.name),
      prefs.setBool(_showDecorationsKey, previous.showDecorations),
    ]);
    state = previous;
  }

  // =========================================================================
  // Helpers
  // =========================================================================

  static ThemeMode _readThemeMode(String? value) {
    return switch (value) {
      'light' => ThemeMode.light,
      'dark' => ThemeMode.dark,
      _ => ThemeMode.system,
    };
  }

  static T _readEnum<T extends Enum>(
    String? value,
    List<T> values,
    T defaultValue,
  ) {
    if (value == null) return defaultValue;
    for (final v in values) {
      if (v.name == value) return v;
    }
    return defaultValue;
  }
}

/// Provider for the theme state notifier.
///
/// Watch for [ThemeState] value; call `.notifier.selectPalette(id)`,
/// `.notifier.setThemeMode(mode)`, etc. to change settings.
final themeProvider = NotifierProvider<ThemeNotifier, ThemeState>(
  ThemeNotifier.new,
);
