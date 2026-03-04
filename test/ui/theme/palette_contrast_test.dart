import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:agentic_journal/ui/theme/palettes.dart';

/// Compute the relative luminance of a color per WCAG 2.1.
/// https://www.w3.org/TR/WCAG21/#dfn-relative-luminance
double _relativeLuminance(Color color) {
  double linearize(double channel) {
    return channel <= 0.03928
        ? channel / 12.92
        : math.pow((channel + 0.055) / 1.055, 2.4).toDouble();
  }

  final r = linearize(color.r);
  final g = linearize(color.g);
  final b = linearize(color.b);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

/// Compute the contrast ratio between two colors per WCAG 2.1.
/// Returns a value >= 1.0, where higher is more contrast.
double _contrastRatio(Color foreground, Color background) {
  final lumA = _relativeLuminance(foreground);
  final lumB = _relativeLuminance(background);
  final lighter = math.max(lumA, lumB);
  final darker = math.min(lumA, lumB);
  return (lighter + 0.05) / (darker + 0.05);
}

void main() {
  group('WCAG AA contrast validation', () {
    // WCAG AA requires >= 4.5:1 for normal text.
    const minRatio = 4.5;

    // Critical color role pairings to verify.
    final pairings = <String, Color Function(ColorScheme)>{
      'onSurface/surface': (cs) => cs.onSurface,
      'onPrimary/primary': (cs) => cs.onPrimary,
      'onSecondary/secondary': (cs) => cs.onSecondary,
      'onSurfaceVariant/surfaceContainerHighest': (cs) => cs.onSurfaceVariant,
    };

    final backgrounds = <String, Color Function(ColorScheme)>{
      'onSurface/surface': (cs) => cs.surface,
      'onPrimary/primary': (cs) => cs.primary,
      'onSecondary/secondary': (cs) => cs.secondary,
      'onSurfaceVariant/surfaceContainerHighest': (cs) =>
          cs.surfaceContainerHighest,
    };

    for (final palette in appPalettes) {
      for (final brightness in Brightness.values) {
        final scheme = brightness == Brightness.light
            ? palette.lightScheme()
            : palette.darkScheme();
        final modeName = brightness == Brightness.light ? 'light' : 'dark';

        for (final entry in pairings.entries) {
          test('${palette.name} ($modeName): ${entry.key} >= $minRatio:1', () {
            final foreground = entry.value(scheme);
            final background = backgrounds[entry.key]!(scheme);
            final ratio = _contrastRatio(foreground, background);

            expect(
              ratio,
              greaterThanOrEqualTo(minRatio),
              reason:
                  '${palette.name} $modeName ${entry.key}: '
                  'contrast ratio $ratio < $minRatio:1',
            );
          });
        }
      }
    }
  });

  group('Palette definitions', () {
    test('all palette IDs are unique', () {
      final ids = appPalettes.map((p) => p.id).toSet();
      expect(ids.length, appPalettes.length);
    });

    test('default palette ID exists in appPalettes', () {
      expect(appPalettes.any((p) => p.id == defaultPaletteId), isTrue);
    });

    test('getPaletteById returns matching palette', () {
      final palette = getPaletteById('midnight_ink');
      expect(palette.name, 'Midnight Ink');
    });

    test('getPaletteById returns default for unknown ID', () {
      final palette = getPaletteById('nonexistent_palette');
      expect(palette.id, defaultPaletteId);
    });

    test('all palettes generate valid light schemes', () {
      for (final palette in appPalettes) {
        final scheme = palette.lightScheme();
        expect(scheme.brightness, Brightness.light);
        expect(scheme.primary, isNotNull);
      }
    });

    test('all palettes generate valid dark schemes', () {
      for (final palette in appPalettes) {
        final scheme = palette.darkScheme();
        expect(scheme.brightness, Brightness.dark);
        expect(scheme.primary, isNotNull);
      }
    });
  });
}
