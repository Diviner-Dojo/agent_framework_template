// ===========================================================================
// file: lib/ui/widgets/theme_preview_card.dart
// purpose: Mini-preview widget for the palette selection grid.
//
// Shows a miniature representation of how the app will look with a given
// palette: a small session card shape, a user chat bubble, and an assistant
// bubble, all rendered in the palette's colors. The palette name and
// description appear below the preview.
//
// Used in the Theme & Appearance settings section.
//
// See: SPEC-20260304-063144 (Visual Identity & Theme Personalization)
// ===========================================================================

import 'package:flutter/material.dart';

import '../theme/palettes.dart';

/// A tappable card showing a mini-preview of how a palette looks.
///
/// Renders a miniature session card, user bubble, and assistant bubble
/// using the palette's generated [ColorScheme]. When [isSelected] is true,
/// shows a check mark overlay and a highlighted border.
class ThemePreviewCard extends StatelessWidget {
  /// The palette to preview.
  final AppPalette palette;

  /// Whether this palette is currently active.
  final bool isSelected;

  /// Called when the user taps this card.
  final VoidCallback? onTap;

  const ThemePreviewCard({
    super.key,
    required this.palette,
    this.isSelected = false,
    this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isLight = theme.brightness == Brightness.light;
    final scheme = isLight ? palette.lightScheme() : palette.darkScheme();

    return Semantics(
      label: '${palette.name}: ${palette.description}',
      selected: isSelected,
      button: true,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          curve: Curves.easeInOut,
          decoration: BoxDecoration(
            color: scheme.surface,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isSelected ? scheme.primary : scheme.outlineVariant,
              width: isSelected ? 2.5 : 1,
            ),
          ),
          padding: const EdgeInsets.all(8),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              // Mini preview area.
              SizedBox(
                height: 64,
                child: Stack(
                  children: [
                    // Mini session card.
                    Positioned(
                      top: 0,
                      left: 0,
                      right: 0,
                      child: Container(
                        height: 20,
                        decoration: BoxDecoration(
                          color: scheme.surfaceContainerLow,
                          borderRadius: BorderRadius.circular(4),
                          border: Border.all(
                            color: scheme.outlineVariant.withValues(alpha: 0.3),
                            width: 0.5,
                          ),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 4),
                        child: Row(
                          children: [
                            // Accent bar.
                            Container(
                              width: 2,
                              height: 12,
                              decoration: BoxDecoration(
                                color: scheme.primary,
                                borderRadius: BorderRadius.circular(1),
                              ),
                            ),
                            const SizedBox(width: 3),
                            // Mock text lines.
                            Expanded(
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Container(
                                    height: 3,
                                    width: double.infinity,
                                    decoration: BoxDecoration(
                                      color: scheme.onSurface.withValues(
                                        alpha: 0.4,
                                      ),
                                      borderRadius: BorderRadius.circular(1),
                                    ),
                                  ),
                                  const SizedBox(height: 2),
                                  FractionallySizedBox(
                                    widthFactor: 0.6,
                                    child: Container(
                                      height: 2,
                                      decoration: BoxDecoration(
                                        color: scheme.onSurface.withValues(
                                          alpha: 0.2,
                                        ),
                                        borderRadius: BorderRadius.circular(1),
                                      ),
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    // Mini assistant bubble (left-aligned).
                    Positioned(
                      top: 26,
                      left: 0,
                      child: Container(
                        width: 44,
                        height: 14,
                        decoration: BoxDecoration(
                          color: scheme.surfaceContainerHighest,
                          borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(6),
                            topRight: Radius.circular(6),
                            bottomLeft: Radius.circular(2),
                            bottomRight: Radius.circular(6),
                          ),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 3),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              height: 2,
                              width: 32,
                              decoration: BoxDecoration(
                                color: scheme.onSurface.withValues(alpha: 0.3),
                                borderRadius: BorderRadius.circular(1),
                              ),
                            ),
                            const SizedBox(height: 2),
                            Container(
                              height: 2,
                              width: 20,
                              decoration: BoxDecoration(
                                color: scheme.onSurface.withValues(alpha: 0.2),
                                borderRadius: BorderRadius.circular(1),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    // Mini user bubble (right-aligned).
                    Positioned(
                      top: 44,
                      right: 0,
                      child: Container(
                        width: 36,
                        height: 14,
                        decoration: BoxDecoration(
                          color: scheme.primary,
                          borderRadius: const BorderRadius.only(
                            topLeft: Radius.circular(6),
                            topRight: Radius.circular(6),
                            bottomLeft: Radius.circular(6),
                            bottomRight: Radius.circular(2),
                          ),
                        ),
                        padding: const EdgeInsets.symmetric(horizontal: 3),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Container(
                              height: 2,
                              width: 24,
                              decoration: BoxDecoration(
                                color: scheme.onPrimary.withValues(alpha: 0.6),
                                borderRadius: BorderRadius.circular(1),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                    // Selected check mark.
                    if (isSelected)
                      Positioned(
                        top: 0,
                        right: 0,
                        child: Container(
                          width: 18,
                          height: 18,
                          decoration: BoxDecoration(
                            color: scheme.primary,
                            shape: BoxShape.circle,
                          ),
                          child: Icon(
                            Icons.check,
                            size: 12,
                            color: scheme.onPrimary,
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              const SizedBox(height: 6),
              // Palette name.
              Text(
                palette.name,
                style: TextStyle(
                  fontSize: 11,
                  fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                  color: scheme.onSurface,
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
              // Palette description.
              Text(
                palette.description,
                style: TextStyle(
                  fontSize: 11,
                  color: scheme.onSurface.withValues(alpha: 0.5),
                ),
                textAlign: TextAlign.center,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
