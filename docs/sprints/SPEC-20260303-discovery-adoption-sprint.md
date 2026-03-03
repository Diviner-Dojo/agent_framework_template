---
spec_id: SPEC-20260303-discovery
title: "Discovery Adoption Sprint: Notification System, AI Vocabulary, Export, Resurfacing"
status: queued
risk_level: medium
prerequisite_sprint: "SPEC-20260302-ADHD (current sprint must complete first)"
source_analyses:
  - ANALYSIS-20260303-141104-daily-you
  - ANALYSIS-20260303-144505-mhabit
  - ANALYSIS-20260303-210537-adhd-journal-flutter
value_assessment: "docs/reviews/ANALYSIS-20260303-discovery-value-assessment.md"
patterns_to_implement: 15
required_adrs: []
notes: "Each enhancement to be rationalized by specialist agents before implementation begins"
---

## Goal

Implement 15 adopted patterns from external project discovery (Daily_You, mhabit, ADHD_Journal_Flutter). These patterns fill four major gaps: notification/reminder system, AI vocabulary enrichment, data export, and entry resurfacing. All patterns were scored >= 19/25 by multi-specialist review.

## Pre-Implementation Gate

**Before building, run `/review` or `/deliberate` on each sprint group** to have the specialist agents rationalize each enhancement against the current codebase state. The current sprint (SPEC-20260302-ADHD) must be complete first. The codebase will have evolved — agents need to assess each pattern against the post-sprint reality.

## Sprint Groups (Recommended Order)

### Group A: Notification Subsystem (Patterns 1–8)

**User story**: "Smart reminders that know when I've already journaled and don't nag."

| # | Pattern | Source | Score | Effort |
|---|---|---|---|---|
| 1 | Randomized time-window alarm scheduling | Daily_You | 22/25 | Medium |
| 2 | Entry-existence guard in background callback | Daily_You | 23/25 | Low |
| 3 | Notification auto-dismiss on session creation | Daily_You | 22/25 | Low |
| 4 | whenNeeded data-anchored scheduling | mhabit | 23/25 | Low |
| 5 | Localized notification strings pre-stash | Daily_You | 20/25 | Low |
| 6 | NotificationService abstract interface + fake | mhabit | 22/25 | Low |
| 7 | Injectable AppClock | mhabit | 21/25 | Very Low |
| 8 | Segmented notification ID namespace | mhabit | 19/25 | Very Low |

**New dependencies**: `android_alarm_manager_plus`, `flutter_local_notifications`
**Android manifest**: `SCHEDULE_EXACT_ALARM`, `RECEIVE_BOOT_COMPLETED`, `WAKE_LOCK`
**New files (estimated)**: `lib/services/notification_service.dart`, `lib/services/reminder_service.dart`, `lib/utils/app_clock.dart`, `lib/services/notification_id_range.dart`, `lib/providers/reminder_providers.dart`, `test/fakes/fake_notification_service.dart`
**Settings UI**: Reminder toggle, time-window picker (or fixed-time option), `alwaysRemind` toggle

**Build together**: These 8 patterns form one cohesive subsystem. Building them piecemeal would be less efficient.

### Group B: AI Vocabulary Enrichment (Patterns 11–13)

**User story**: "The AI understands what I'm describing — it names my experience, not just summarizes it."

| # | Pattern | Source | Score | Effort |
|---|---|---|---|---|
| 11 | ADHD symptom taxonomy as AI classification vocabulary | ADHD_Journal_Flutter | 22/25 | Low |
| 12 | Positive ADHD traits as first-class trackable states | ADHD_Journal_Flutter | 21/25 | Low |
| 13 | Day-type taxonomy as AI session classification | ADHD_Journal_Flutter | 20/25 | Low-Med |

**What changes**: Claude Edge Function system prompt updated with classification vocabulary. Pattern 13 also needs a `dayType` enum column in Drift session schema (migration).
**No new dependencies**. No new UI (output changes only — AI responses become more specific).
**License**: All ideas-only (no license on source project). Independently derived from ADHD clinical literature.

**Note**: These are invisible to non-ADHD users. The AI only uses ADHD-specific labels when the session content warrants it.

### Group C: Entry Resurfacing (Pattern 10)

**User story**: "The app shows me a past entry each day — like a memory gift."

| # | Pattern | Source | Score | Effort |
|---|---|---|---|---|
| 10 | Date-seeded daily-stable random for resurfacing | Daily_You | 21/25 | Low |

**What changes**: New `lib/services/resurfacing_service.dart` (~30 lines). Home screen widget showing today's resurfaced entry (card with summary + date). Sentiment filter: only surface positive/neutral sessions.
**No new dependencies**.
**Prerequisite**: Works best with 30+ sessions in the database.

### Group D: Data Export (Pattern 9)

**User story**: "I can take my journal data with me — share it, back it up, or leave."

| # | Pattern | Source | Score | Effort |
|---|---|---|---|---|
| 9 | SessionExporter factory + strategy + mixin | mhabit | 21/25 | Medium |

**What changes**: New `lib/services/session_exporter.dart` with factory dispatching to ExportAll / ExportFiltered. Share sheet via `share_plus`. Format decision needed (JSON, Markdown, CSV, or multi-format).
**New dependencies**: `csv`, `share_plus`, optionally `pdf` + `printing`
**UI**: Export button in settings or session list overflow menu. Date range picker for filtered export.

### Group E: Schema Additions (Patterns 14–15)

**User story**: "Track sleep and medication alongside my journal for richer AI insights."

| # | Pattern | Source | Score | Effort |
|---|---|---|---|---|
| 14 | Sleep quality field on sessions | ADHD_Journal_Flutter | 21/25 | Low |
| 15 | Medication notes field on sessions (OPT-IN ONLY) | ADHD_Journal_Flutter | 20/25 | Low |

**What changes**: Two nullable Drift columns + migration. Sleep quality: optional voice prompt "How did you sleep?" (skippable). Medication notes: **gated behind Settings toggle (default: off)**. When medication tracking is disabled, no medication UI, prompts, or AI analysis shown.
**Settings UI**: Sleep prompt toggle, medication tracking toggle (default off).
**Claude prompt**: Conditionally include sleep/medication context based on settings.

## Developer Constraints

- **Medication tracking is opt-in only**: Settings toggle, default off. When disabled, the feature is completely invisible — no prompts, no UI, no AI references. Developer requirement.
- **No implementation until current sprint completes**: SPEC-20260302-ADHD Phase 1 and remaining tasks must land first.
- **Agent rationalization before build**: Each group must be reviewed by specialist agents against the post-sprint codebase before implementation begins.
- **All patterns are PENDING in adoption log**: `memory/lessons/adoption-log.md` has full details, scores, and source references for each pattern.

## Reference Documents

- **Value assessment**: `docs/reviews/ANALYSIS-20260303-discovery-value-assessment.md` — plain-language walkthrough of each pattern's impact, cost, and audience implications
- **Daily_You analysis**: `docs/reviews/ANALYSIS-20260303-141104-daily-you.md`
- **mhabit analysis**: `docs/reviews/ANALYSIS-20260303-144505-mhabit.md`
- **ADHD_Journal_Flutter analysis**: `docs/reviews/ANALYSIS-20260303-210537-adhd-journal-flutter.md`
- **Adoption log**: `memory/lessons/adoption-log.md` (15 new entries from 2026-03-03)
