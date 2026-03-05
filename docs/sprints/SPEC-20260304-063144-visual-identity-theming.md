---
spec_id: SPEC-20260304-063144
title: "Visual Identity & Theme Personalization"
status: reviewed
risk_level: medium
reviewed_by: [ux-evaluator, independent-perspective, architecture-consultant, qa-specialist]
discussion_id: DISC-20260304-063144-visual-identity-theming-spec-review
---

## Goal

Elevate the app's visual identity from "functional Material 3 default" to a polished, emotionally resonant journaling experience — while giving users the ability to personalize their visual environment through a Theme & Appearance settings panel. The design language should reinforce the app's core mission: helping people connect with themselves.

## Context

The current UI uses Material 3 with a single teal seed color (`#5B8A9A`), system-driven light/dark mode, and standard card/bubble styling. While functional and clean, the visual identity lacks the warmth, personality, and polish that distinguishes a thoughtful journaling app from a generic Material scaffold. Users who journal regularly develop an emotional relationship with their tools — the visual environment should support that intimacy.

The app targets adults with ADHD, where visual comfort, reduced cognitive friction, and a sense of ownership over the environment are particularly important. Theme personalization also serves as a low-stakes way for users to engage with settings without touching anything functional.

### What Exists Today
- Single seed color (`#5B8A9A` teal) generates full Material 3 palette
- Light/dark follows system setting only
- Cards use 12px border radius, 1pt elevation
- Chat bubbles have asymmetric radius (4px on sender corner)
- Chat bubbles use hardcoded `AppTheme.userBubbleLight/Dark` static constants (not palette-derived)
- No user-facing theme or appearance settings
- No decorative elements on journal entries
- No typography customization

### What This Spec Does NOT Change
- Navigation structure
- Feature behavior
- Data model (no new database tables)
- ADHD clinical UX constraints (no streaks, no gap-shaming)
- Core interaction patterns

## Design Options (For Developer Review)

### Option A: "Curated Palettes" — Preset Theme Packs

**Concept**: 7 curated color palettes, each tied to a journaling mood/intention. User picks one from a visual grid in settings. Each palette name evokes a quality of self-connection — the naming is intentional, not decorative.

**Palettes** (each defines a seed color + optional surface tint):

| Name | Seed Color | Mood/Intention | Description |
|---|---|---|---|
| **Still Water** | `#5B8A9A` (current) | Calm reflection | The existing teal — serene, grounded |
| **Warm Earth** | `#8B6F47` | Grounding, stability | Warm browns and amber — feels like a leather journal |
| **Soft Lavender** | `#7B6B8D` | Gentle introspection | Muted purple-grey — contemplative and soft |
| **Forest Floor** | `#5A7247` | Growth, renewal | Deep sage green — natural, organic |
| **Ember Glow** | `#A0664B` | Energy, warmth | Terracotta/copper — warm and inviting |
| **Midnight Ink** | `#3B4A6B` | Deep thought, focus | Deep navy-blue — classic journal aesthetic |
| **Dawn Light** | `#C4956A` | Optimism, new beginnings | Golden peach — warm and hopeful |

**Pre-validation required**: All 7 seed colors must be pre-validated both visually (does the generated palette match the mood association?) and programmatically (WCAG AA contrast for all critical color role pairings). If a seed color fails either test, adjust before implementation.

**Implementation**: Each palette is a `ColorScheme.fromSeed()` call with a different seed. Light/dark variants auto-generated. User selection stored in SharedPreferences.

**Pros**: Low complexity, visually cohesive (Material 3 does the harmony math), impossible to create ugly combinations
**Cons**: Limited personalization, no custom colors

### Option B: "Your Space" — Palette + Surface Customization

**Everything in Option A**, plus:

- **Font scale**: Small / Default / Large / Extra Large (accessibility + preference)
- **Card style**: Choose between Flat (no elevation), Soft (current 1pt), Raised (3pt with shadow)
- **Chat bubble shape**: Rounded (current), Soft Square, Pill
- **Light/Dark override**: System (current) / Always Light / Always Dark

**Note**: "Scheduled (sunrise-sunset)" light/dark mode was removed from this phase per specialist review — it requires location permissions and is out of scope for the theming feature. May be considered for a future phase.

**Pros**: Meaningful personalization without overwhelming choices
**Cons**: Moderate complexity, more settings surface area

### Option C: "Journal Craft" — Full Visual Identity System

**Everything in Options A + B**, plus:

- **Journal entry decorations**: Subtle decorative elements on session cards
  - Edge accents: thin colored side-bar on cards (palette primary color, not data-derived)
  - Corner flourishes: subtle decorative corners on session detail views
  - Dividers: styled section dividers between monthly groups (botanical line, gentle wave, simple dot pattern)
- **Chat environment mood**: Background tint/texture in the conversation view
  - Subtle paper texture or faint gradient wash behind messages (user-toggleable)
  - Must use `Stack` with `RepaintBoundary`-wrapped `ListView` above texture layer
- **Entry card personality**: Session cards get visual richness
  - Journaling mode icon (in session detail view only — not on list cards per UX review)

**Pros**: Transforms the visual experience, creates emotional warmth, makes the app feel intentionally designed
**Cons**: Highest complexity, potential performance impact from decorative layers, needs careful ADHD review (decorations must not become distracting)

### Recommendation

**Option C with phased delivery**: Ship Options A+B together as the settings panel (Phase 5A), then layer in Option C's decorative elements as Phase 5B. This gives users immediate personalization while the polish work continues.

### Alternative Approaches Considered (from specialist review)

1. **Android Dynamic Color** (`dynamic_color` package): Reads the user's system wallpaper palette on Android 12+ and auto-generates a Material 3 scheme. Zero UI surface area, zero settings panel needed. Provides automatic personalization that reflects choices the user already made. Limitation: Android 12+ only, requires fallback. **Verdict**: Could complement curated palettes as an additional option (e.g., "System Colors" as palette #8) rather than replace them.

2. **Single exceptional default**: Rather than 7 palettes, invest all effort in making the default "Still Water" theme genuinely polished — refined typography, correct Material 3 surface roles, better spacing. Ship palette choice later. **Verdict**: The structural polish (fixing hardcoded colors, proper Material 3 surface usage) IS Phase 5A Step 1 regardless of palette count. The additional palettes are incremental on top of that foundation.

3. **Fix structural issues first**: The independent-perspective agent identified that some of the "generic" feel comes from hardcoded color constants, duplicated theme definitions, and widgets not using the `ColorScheme`. Fixing these structural issues may have a bigger visual impact than adding palettes. **Verdict**: Adopted — Phase 5A Task 1 is now explicitly "structural color migration" before palette support.

## Requirements

### Phase 5A: Theme Settings Panel + Curated Palettes

#### Step 1: Structural Color Migration (prerequisite)
- R0a: Migrate chat bubble colors from `AppTheme.userBubbleLight/Dark` static constants to palette-derived colors via `ThemeExtension<ChatBubbleColors>` or `ColorScheme` role mapping
- R0b: Audit all widgets for hardcoded color references to `AppTheme.*` and migrate to `Theme.of(context)` access
- R0c: Refactor `AppTheme` to expose `static ThemeData fromPalette(AppPalette palette, Brightness brightness)` factory method while retaining current `light`/`dark` getters as convenience wrappers

#### Step 2: Theme Settings Panel
- R1: Theme selection grid in Settings as the **first card** in the settings list, showing palette swatches with names. Each swatch renders a `ThemePreviewCard` mini-preview containing a miniature session card shape, user chat bubble, and assistant bubble at that palette's colors
- R2: Real-time preview — theme changes apply instantly (no restart). Palette selection grid provides inline mini-preview; theme also applies live to the surrounding UI
- R3: Light/Dark mode override (System / Light / Dark)
- R4: Font scale adjustment (Small / Default / Large / Extra Large), implemented as additive offsets (`Small=-0.1`, `Default=0`, `Large=+0.15`, `Extra Large=+0.3`) applied to the system text scale, clamped at max effective scale of 2.0
- R5: Card elevation style (Flat / Soft / Raised) — **Note**: Flat (0pt) may be visually indistinguishable from surface in some palettes; verify on emulator
- R6: Chat bubble shape (Rounded / Soft Square / Pill)
- R7: Persist all selections in SharedPreferences
- R8: Default to current appearance (Still Water, System, Default font, Soft cards, Rounded bubbles) — zero migration needed
- R8b: `ThemeState` includes `showDecorations` field from the start (defaults to `true`), even though Phase 5B decorations are not yet implemented. This avoids a breaking change when Phase 5B ships.

#### Settings Panel Organization
- Font scale, card style, and bubble shape are placed inside a collapsed "Advanced" `ExpansionTile` within the Theme & Appearance card. Only palette selection and light/dark toggle are visible at the top level. This follows the app's existing progressive disclosure pattern.
- "Reset to defaults" button at the bottom of the Theme & Appearance card. Confirmation via snackbar with "Undo" action (proportionate to stakes — no dialog needed).

### Phase 5B: Visual Polish & Decorative Elements
- R9: Themed side-accent on session cards (thin vertical bar, palette primary color — NOT mood-data-derived)
- R10: Journaling mode icon on session detail view only (not on list cards — avoids visual noise per UX review)
- R11: Styled monthly group dividers on home screen (botanical line, gentle wave, or simple dot pattern)
- R12: Subtle background treatment in conversation view (gradient wash, user-toggleable). Must use `Stack` with `RepaintBoundary`-wrapped `ListView`, not `Container` decoration. Add performance criterion: no jank (under 16ms frame budget) scrolling 50+ messages with treatment enabled.
- R13: Corner accent on session detail transcript view
- R14: **REMOVED** — ~~Mood-colored accent stripe on session cards~~ — Violates ADHD clinical UX constraint. Presence/absence of mood-colored decoration implicitly encodes check-in compliance, creating a visual gap-shaming calendar. Replaced by R9 (palette-primary accent, always present when decorations enabled).
- R15: All decorative elements respect system "Reduce Motion" accessibility setting
- R16: All decorative elements toggleable via `showDecorations` preference

## Constraints

- **ADHD clinical UX**: All decorative elements must be subtle, not flashy. No animations that loop or demand attention. All decorations toggleable or removable. Visual noise must not increase cognitive load. Decorative elements must NEVER encode user behavioral data (check-in completion, mood scores, session frequency).
- **Performance**: Decorative overlays must not add jank. Test on low-end devices. Background treatments must use `Stack` + `RepaintBoundary` architecture, not container-level decoration.
- **Accessibility**: Font scale uses additive offsets on system scale, clamped at max effective 2.0. Contrast ratios must pass WCAG AA (4.5:1 for normal text) for all palettes in both light and dark mode, verified programmatically.
- **No data model changes**: Theme preferences stored in SharedPreferences only. No Drift tables, no sync.
- **Reversible**: Users can always return to defaults with one tap ("Reset to defaults" button with snackbar undo).
- **Architecture**: Widgets access colors exclusively through `Theme.of(context).colorScheme` or `ThemeExtension`. No widget may import `palettes.dart` directly.
- **ADR-0029 acknowledged**: `ref.watch()` on the theme provider feeding `MaterialApp.theme`/`darkTheme`/`themeMode` is safe — theme changes trigger animated transitions, not Navigator stack collapses (unlike `initialRoute` per ADR-0029).

## Acceptance Criteria

### Phase 5A
- [ ] Chat bubble colors derive from active palette (no hardcoded AppTheme.* constants)
- [ ] All widgets use `Theme.of(context)` for colors (no direct AppTheme.* imports in widgets)
- [ ] Settings screen has "Theme & Appearance" as the first settings card
- [ ] Palette selection grid shows 7 palettes with mini-preview cards
- [ ] User can select from 7 curated palettes with instant live preview
- [ ] Light/Dark/System toggle works correctly
- [ ] Font scale applies globally, persists across restarts, and clamps at max 2.0 effective
- [ ] UI renders without overflow at system font scale 200% with in-app Large setting active
- [ ] Card style and bubble shape preferences apply correctly
- [ ] All 7 palettes pass WCAG AA contrast (automated test: 7 palettes x 2 modes x 4 role pairings)
- [ ] `ThemeNotifier` has full test coverage (defaults, persistence, reset, partial prefs)
- [ ] `MaterialApp` theme wiring has test verifying provider-driven values reach the widget
- [ ] "Reset to defaults" returns all settings to factory state (snackbar with undo)
- [ ] No regression in existing tests
- [ ] Emulator smoke test passes for 3 representative palettes (warm, cool, dark) in light and dark mode

### Phase 5B
- [ ] Session cards show themed side-accent bar (palette primary, not mood-derived)
- [ ] Session detail shows journaling mode icon
- [ ] Monthly group dividers have styled appearance
- [ ] Background treatment in conversation view toggleable and jank-free
- [ ] Decorative elements respect system "Reduce Motion" setting (automated test)
- [ ] All decorations disabled when `showDecorations=false`

## Risk Assessment

- **Medium risk**: Theme system touches the root `MaterialApp` widget, so a bug could affect every screen. Mitigated by: (a) building on Material 3's `ColorScheme.fromSeed()`, (b) explicit `MaterialApp` wiring test, (c) ADR-0029 evaluation confirming `ref.watch` safety.
- **Visual regression risk**: Decorative elements could interact poorly with existing widgets. Mitigated by phased delivery (settings panel ships before decorations).
- **Accessibility risk**: Custom palettes could fail contrast requirements. Mitigated by automated WCAG contrast unit tests for all 56 palette/mode/role combinations.
- **ADHD UX risk**: Decorations could add visual noise. Mitigated by progressive disclosure, toggleability, and removal of mood-data-derived decorations (R14).
- **Cold-start flash risk**: SharedPreferences async initialization may cause a brief theme flash for non-default palette users. Documented as known limitation; can be mitigated with splash screen or `AsyncNotifierProvider` in future.

## Affected Components

### Phase 5A (Theme Settings)
- `lib/ui/theme/app_theme.dart` — Refactor to `fromPalette()` factory + `ThemeExtension<ChatBubbleColors>`
- `lib/ui/widgets/chat_bubble.dart` — Migrate from `AppTheme.*` constants to `Theme.of(context)` / theme extension
- `lib/app.dart` — Wire dynamic theme from provider via `ref.watch(themeProvider)`
- `lib/ui/screens/settings_screen.dart` — Add Theme & Appearance section as first card
- New: `lib/providers/theme_providers.dart` — Riverpod `Notifier<ThemeState>` (modern API, under `lib/providers/` per project convention)
- New: `lib/ui/theme/palettes.dart` — Curated palette definitions
- New: `lib/ui/widgets/theme_preview_card.dart` — Palette selection widget with mini-preview

### Phase 5B (Visual Polish)
- `lib/ui/widgets/session_card.dart` — Add side-accent
- `lib/ui/screens/session_list_screen.dart` — Styled group dividers
- `lib/ui/screens/journal_session_screen.dart` — Background treatment
- `lib/ui/screens/session_detail_screen.dart` — Corner accent + mode icon
- `lib/ui/widgets/chat_bubble.dart` — Bubble shape variants
- New: `lib/ui/theme/decorations.dart` — Shared decoration definitions

### New Tests Required
- `test/ui/theme/palette_contrast_test.dart` — WCAG AA contrast for all 56 combinations
- `test/ui/theme/theme_provider_test.dart` — ThemeNotifier state management + persistence
- `test/app_theme_wiring_test.dart` — Provider-driven theme reaches MaterialApp
- Updates to `test/ui/chat_bubble_test.dart` — Color assertions with explicit palette
- Updates to `test/ui/settings_screen_test.dart` — Theme & Appearance section

## Dependencies

- Depends on: Nothing — standalone feature
- Blocked by: Nothing
- Does not block: Any existing roadmap items
- Phase 5B depends on Phase 5A (palettes must exist before decorations reference them)

## Implementation Notes

### Dynamic Theming Architecture
```dart
// lib/providers/theme_providers.dart sketch (modern Notifier API)
final themeProvider = NotifierProvider<ThemeNotifier, ThemeState>(() {
  return ThemeNotifier();
});

class ThemeNotifier extends Notifier<ThemeState> {
  @override
  ThemeState build() {
    final prefs = ref.watch(sharedPreferencesProvider);
    return ThemeState.fromPrefs(prefs); // reads each key with independent defaults
  }

  void selectPalette(String paletteId) { ... }
  void setThemeMode(ThemeMode mode) { ... }
  void setFontScale(FontScale scale) { ... }
  void setCardStyle(CardStyle style) { ... }
  void setBubbleShape(BubbleShape shape) { ... }
  void resetToDefaults() { ... }
}

class ThemeState {
  final String paletteId;       // e.g., 'still_water'
  final ThemeMode themeMode;    // system/light/dark
  final FontScale fontScale;    // small/default/large/extraLarge
  final CardStyle cardStyle;    // flat/soft/raised
  final BubbleShape bubbleShape; // rounded/softSquare/pill
  final bool showDecorations;   // Phase 5B toggle (included from start)
}
```

### Chat Bubble Color Migration
```dart
// ThemeExtension approach
class ChatBubbleColors extends ThemeExtension<ChatBubbleColors> {
  final Color userBubble;
  final Color assistantBubble;
  // ... copyWith, lerp
}

// In AppTheme.fromPalette():
ThemeData.light.copyWith(
  extensions: [ChatBubbleColors(
    userBubble: colorScheme.primary,
    assistantBubble: colorScheme.surfaceContainerHighest,
  )],
)

// In ChatBubble widget:
final colors = Theme.of(context).extension<ChatBubbleColors>()!;
```

### Palette Definition Pattern
```dart
// lib/ui/theme/palettes.dart sketch
class AppPalette {
  final String id;
  final String name;
  final String description;
  final Color seedColor;

  const AppPalette({required this.id, required this.name,
    required this.description, required this.seedColor});

  ColorScheme lightScheme() => ColorScheme.fromSeed(
    seedColor: seedColor, brightness: Brightness.light);
  ColorScheme darkScheme() => ColorScheme.fromSeed(
    seedColor: seedColor, brightness: Brightness.dark);
}

const palettes = [
  AppPalette(id: 'still_water', name: 'Still Water',
    description: 'Calm reflection', seedColor: Color(0xFF5B8A9A)),
  // ... etc
];
```

### Font Scale Implementation
```dart
// Additive offset, clamped at max 2.0
double effectiveScale(double systemScale, FontScale userChoice) {
  final offset = switch (userChoice) {
    FontScale.small => -0.1,
    FontScale.defaultScale => 0.0,
    FontScale.large => 0.15,
    FontScale.extraLarge => 0.3,
  };
  return (systemScale + offset).clamp(0.8, 2.0);
}
```

## Review Findings Summary

### Blocking Findings (all addressed in spec)
1. **R14 mood-colored accent removed** — UX-evaluator + independent-perspective: implicit gap-shaming
2. **Chat bubble color migration** — architecture-consultant + independent-perspective + qa-specialist: hardcoded constants bypass palettes
3. **ThemePreviewCard mini-preview** — UX-evaluator: preview must show bubbles + cards, not just color circles
4. **Font scale clamping** — UX-evaluator + qa-specialist: multiplicative overflow risk
5. **Modern Notifier API** — architecture-consultant: legacy StateNotifier pattern
6. **Provider location** — architecture-consultant: must be `lib/providers/`, not `lib/ui/theme/`
7. **Test coverage** — qa-specialist: 4 blocking test gaps (bubble color, provider, MaterialApp wiring, WCAG contrast)

### Open Advisories (carry forward to implementation)
- A1: Settings panel should use section grouping long-term (11+ cards)
- A2: Pre-validate palette visuals before implementation (Dawn Light and Warm Earth are high-risk seeds)
- A3: SharedPreferences async init flash — known limitation
- A4: Flat card style may be indistinguishable from surface — verify on emulator
- A5: Background texture (Phase 5B) — consider gradient wash over image assets for memory on low-RAM devices
- A6: Consider `dynamic_color` package as future "System Colors" palette option
