// ===========================================================================
// file: lib/ui/theme/palettes.dart
// purpose: Curated color palette definitions for theme personalization.
//
// Each palette defines a seed color that Material 3's ColorScheme.fromSeed()
// uses to generate a full harmonious color scheme for both light and dark
// modes. Palette names evoke qualities of self-connection, reinforcing the
// app's mission of helping people connect with themselves.
//
// See: SPEC-20260304-063144 (Visual Identity & Theme Personalization)
// ===========================================================================

import 'package:flutter/material.dart';

/// A curated color palette for the app's theme.
///
/// Each palette has a unique [id] for persistence, a user-facing [name],
/// a short [description] of the mood/intention it evokes, and a [seedColor]
/// that Material 3 uses to generate a full color scheme.
class AppPalette {
  /// Unique identifier used for SharedPreferences storage.
  final String id;

  /// User-facing display name shown in the palette selection grid.
  final String name;

  /// Short description of the mood/intention this palette evokes.
  final String description;

  /// The seed color used by [ColorScheme.fromSeed] to generate a full
  /// Material 3 color scheme.
  final Color seedColor;

  const AppPalette({
    required this.id,
    required this.name,
    required this.description,
    required this.seedColor,
  });

  /// Generate a light-mode [ColorScheme] from this palette's seed color.
  ColorScheme lightScheme() =>
      ColorScheme.fromSeed(seedColor: seedColor, brightness: Brightness.light);

  /// Generate a dark-mode [ColorScheme] from this palette's seed color.
  ColorScheme darkScheme() =>
      ColorScheme.fromSeed(seedColor: seedColor, brightness: Brightness.dark);
}

/// The default palette ID used when no preference has been set.
const defaultPaletteId = 'still_water';

/// All available palettes, ordered for display in the selection grid.
const List<AppPalette> appPalettes = [
  AppPalette(
    id: 'still_water',
    name: 'Still Water',
    description: 'Calm reflection',
    seedColor: Color(0xFF5B8A9A),
  ),
  AppPalette(
    id: 'warm_earth',
    name: 'Warm Earth',
    description: 'Grounding, stability',
    seedColor: Color(0xFF8B6F47),
  ),
  AppPalette(
    id: 'soft_lavender',
    name: 'Soft Lavender',
    description: 'Gentle introspection',
    seedColor: Color(0xFF7B6B8D),
  ),
  AppPalette(
    id: 'forest_floor',
    name: 'Forest Floor',
    description: 'Growth, renewal',
    seedColor: Color(0xFF5A7247),
  ),
  AppPalette(
    id: 'ember_glow',
    name: 'Ember Glow',
    description: 'Energy, warmth',
    seedColor: Color(0xFFA0664B),
  ),
  AppPalette(
    id: 'midnight_ink',
    name: 'Midnight Ink',
    description: 'Deep thought, focus',
    seedColor: Color(0xFF3B4A6B),
  ),
  AppPalette(
    id: 'dawn_light',
    name: 'Dawn Light',
    description: 'Optimism, new beginnings',
    seedColor: Color(0xFFC4956A),
  ),
];

/// Look up a palette by its [id]. Returns the default palette if not found.
AppPalette getPaletteById(String id) {
  return appPalettes.firstWhere(
    (p) => p.id == id,
    orElse: () => appPalettes.first,
  );
}
