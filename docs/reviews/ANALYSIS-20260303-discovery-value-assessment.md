---
title: "Discovery Value Assessment: 15 Adopted Patterns from Daily_You, mhabit, and ADHD_Journal_Flutter"
date: "2026-03-03"
purpose: "Developer decision guide — how each pattern adds value, what it costs, and how it fits alongside existing features"
analyses_covered:
  - ANALYSIS-20260303-141104-daily-you
  - ANALYSIS-20260303-144505-mhabit
  - ANALYSIS-20260303-210537-adhd-journal-flutter
---

## What This Report Is

You adopted 15 patterns across 3 project analyses today. This report walks through each one in plain terms: what it does, why it matters for your users, how it fits with what you already have, and what it will cost to build. Patterns are grouped by the user problem they solve, not by which project they came from.

Your app is a general-purpose voice journal that should work especially well for people with ADHD — but it is not an ADHD-only tool. Every recommendation below is evaluated through that lens: does this make the app better for everyone, or does it narrow the audience?

---

## What Your App Already Does Well

Before weighing new features, here's what's already working:

- **Voice-first capture** — full hands-free continuous loop (listen → process → speak → listen) with on-device STT (Sherpa-ONNX) and cloud fallback (Deepgram). This is your core differentiator.
- **6 journaling modes** — Free, Gratitude, Dream Analysis, Mood Check-In, Onboarding, Pulse Check-In. Flexible enough for different emotional states.
- **3-tier AI** — Claude API (rich), on-device LLM (offline), rule-based (guaranteed fallback). Users always get a response.
- **Intent classification** — mid-conversation routing to calendar events, tasks, past-entry recall, and day queries without leaving the journal session.
- **Pulse Check-In** — validated clinical instruments (PHQ-4, WHO-5, BEDS) with slider UI, composite scoring, and fl_chart history visualization. Already built.
- **Offline-first** — local Drift database is the source of truth. Supabase sync is opt-in.
- **No streaks, no gap-shaming** — the app doesn't track or display absence. This is already correct.
- **Progressive disclosure** — search, gallery, and task icons only appear when there's content to show.

The gaps are real but specific: no reminders, no data export, no entry resurfacing, and the AI doesn't speak ADHD vocabulary even though the app is designed with ADHD in mind.

---

## Group 1: "Remind Me Without Nagging Me"

**The problem**: Your app has zero notification infrastructure. Users who want to build a journaling habit have no way to get a gentle nudge. For anyone (not just ADHD users), the absence of reminders means the app relies entirely on the user remembering to open it. For ADHD users specifically, this is a critical gap — task initiation is the core difficulty.

**What you already have**: Nothing. No notification package in pubspec.yaml, no reminder service, no scheduling logic.

### Pattern 1: Randomized Time-Window Alarm (from Daily_You, 22/25)

**What it does**: Instead of firing a reminder at exactly 9:00 AM every day, the user sets a window (say 8 AM – 12 PM) and the app picks a random time within that window each day. Tomorrow it might be 8:47 AM. The next day, 11:22 AM.

**Why this matters for everyone**: Fixed-time reminders become invisible. Your brain learns to ignore the 9:00 AM buzz after a week. Randomized timing preserves novelty — the reminder arrives when you're not expecting it, which makes you actually notice it. This is basic behavioral science (variable-ratio reinforcement is more persistent than fixed-interval), and it benefits anyone who wants a reminder without habituation.

**Why it especially matters for ADHD**: ADHD brains are novelty-seeking. A predictable reminder is easier to tune out. The randomized window is specifically designed to stay effective longer.

**What it costs to build**: Medium. Requires adding `android_alarm_manager_plus` and `flutter_local_notifications` to pubspec.yaml. Needs Android manifest permissions (SCHEDULE_EXACT_ALARM, RECEIVE_BOOT_COMPLETED, WAKE_LOCK). The scheduling logic itself is ~50 lines. The self-rescheduling callback chain (each alarm schedules the next day's) is well-understood from Daily_You's production implementation.

**Does it narrow the audience?** No. This is a universally useful reminder feature with an option (fixed time) for users who prefer predictability.

---

### Pattern 2: Entry-Existence Guard (from Daily_You, 23/25)

**What it does**: Before firing the reminder, the background service checks: "Did the user already journal today?" If yes, the reminder is silently skipped. A separate toggle (`alwaysRemind`) lets users override this if they want the nudge regardless.

**Why this matters for everyone**: Nobody wants to be reminded to do something they've already done. This is basic courtesy in notification design.

**Why it especially matters for ADHD**: Being reminded of a completed task can trigger frustration or the feeling of being "managed." Automatic suppression respects the user's accomplishment without requiring them to manually dismiss anything.

**What it costs to build**: Very low. One Drift DAO query (`sessionDao.hasSessionForDate(today)`) in the background callback. The `alwaysRemind` toggle is a single SharedPreferences boolean exposed in settings.

**Does it narrow the audience?** No. This is standard notification hygiene.

---

### Pattern 3: Notification Auto-Dismiss on Session Start (from Daily_You, 22/25)

**What it does**: The moment the user opens a new journal session, any pending reminder notification is automatically cancelled from the notification tray. No manual swipe-to-dismiss needed.

**Why this matters for everyone**: It closes the loop cleanly. The notification served its purpose (getting the user to open the app). Leaving it in the tray after the user is already journaling is pointless clutter.

**What it costs to build**: Very low. One `flutter_local_notifications` cancel-by-ID call added to the session start method in `session_providers.dart`.

**Does it narrow the audience?** No. Universal UX improvement.

---

### Pattern 4: whenNeeded Data-Anchored Scheduling (from mhabit, 23/25)

**What it does**: Instead of firing every day on a fixed schedule, the reminder only fires on days when the user hasn't journaled yet. If they journaled at 7 AM, no reminder fires at all. If they haven't journaled by their preferred reminder time, it fires.

**Why this matters for everyone**: This is the difference between a dumb alarm and a smart reminder. A fixed daily alarm fires even on days you've already journaled twice. whenNeeded respects context.

**Why it especially matters for ADHD — and this is the critical insight**: Your ADHD spec says reminders must auto-disable after 3 consecutive dismissals. With a fixed-time reminder, a user who journals at 6 PM but has their reminder set for 9 AM will dismiss it every morning — because they haven't journaled yet at 9 AM but plan to journal later. After 3 dismissals, the auto-disable triggers and the user permanently loses their reminder. With whenNeeded, the reminder fires at 9 AM only if they didn't journal yesterday. The user who journals at 6 PM never sees a 9 AM reminder because yesterday's session already happened. The auto-disable never triggers. **This prevents your own ADHD safety rule from accidentally punishing consistent users who happen to journal at a different time than their reminder.**

**What it costs to build**: Low. Pure business logic (~25 lines of date arithmetic). Uses the same SessionDao query as the entry-existence guard. Complements patterns 1-3 — they all work together as one notification subsystem.

**Does it narrow the audience?** No. Smart, context-aware reminders are better for everyone.

---

### Pattern 5: Localized Notification Strings Pre-Stash (from Daily_You, 20/25)

**What it does**: On every app launch, store the current language's notification title and body text in SharedPreferences. The background alarm callback reads these strings because it runs in a separate isolate that has no access to Flutter's localization system.

**Why this matters**: Without this, your reminders will always be in English, even for non-English users. It's a technical necessity, not a UX feature — but getting it wrong means broken localization for a visible surface.

**What it costs to build**: Very low. Store on launch, read in callback. English fallback for first-install edge case.

**Does it narrow the audience?** The opposite — it widens it by supporting non-English users properly.

---

### Pattern 6: NotificationService Abstract Interface (from mhabit, 22/25)

**What it does**: Defines a clean `abstract interface class NotificationService` with methods like `scheduleReminder()`, `cancelReminder()`, etc. A Riverpod provider wraps the real implementation. A `FakeNotificationService` in your test directory records all calls without firing real notifications.

**Why this matters**: This is architectural, not user-facing. But it determines whether your notification code is testable. Without this interface, every test that touches sessions, providers, or settings would either need to mock a concrete notification class or would fire real notifications on the test device. The recording fake means you can write tests like "verify that starting a session cancels the reminder" without any platform dependency.

**What it costs to build**: Low. Two files: the interface definition and the test fake. Follows your existing Riverpod provider pattern.

**Does it narrow the audience?** No. This is invisible to users — it's engineering quality infrastructure.

---

### Pattern 7: Injectable AppClock (from mhabit, 21/25)

**What it does**: A tiny singleton that wraps `DateTime.now()`. Production code calls `AppClock().now()` instead of `DateTime.now()` directly. Tests call `AppClock().setNow(() => fixedTime)` to freeze time.

**Why this matters**: Every pattern above involves scheduling logic that depends on "what time is it now?" Without an injectable clock, your tests either flake (because they depend on real wall-clock time) or you can't test scheduling edge cases (what happens at midnight? what happens across timezone changes?). This is 15 lines of code that makes everything else testable.

**What it costs to build**: Very low. ~15 lines, no new dependency.

**Does it narrow the audience?** No. Invisible to users.

---

### Pattern 8: Segmented Notification ID Namespace (from mhabit, 19/25)

**What it does**: Assigns named constant IDs to different notification types (reminder = ID 1, future AI insights = IDs 100-199). Prevents one subsystem from accidentally cancelling another's notifications by using the same ID.

**Why this matters**: Today you have zero notification IDs. Tomorrow you'll have reminders. Eventually you might add weekly digest notifications or AI-generated insight alerts. Without namespacing, the second notification type you add will collide with the first.

**What it costs to build**: Very low. One file with a few constants. ~10 lines.

**Does it narrow the audience?** No. Invisible infrastructure.

---

### Summary: The Notification Stack

Patterns 1-8 form a single cohesive notification subsystem. Here's how they compose:

```
User sets reminder window (8 AM - 12 PM) in Settings
  ↓
Each day, a random time is picked within the window (Pattern 1)
  ↓
At that time, background callback fires:
  → Check: did user already journal today? (Pattern 2 + 4)
  → If yes: skip silently
  → If no: read localized strings (Pattern 5), fire notification
  ↓
User taps notification → app opens → session starts
  → Pending notification auto-dismissed (Pattern 3)
```

All scheduling logic is testable via AppClock (Pattern 7) and FakeNotificationService (Pattern 6). IDs don't collide (Pattern 8).

**Total build estimate**: One focused sprint. The patterns are complementary — building them together is more efficient than adding them piecemeal. The hardest part is the Android manifest permissions and background isolate setup, not the logic itself.

**Value for general users**: "Smart reminders that know when you've already journaled and don't nag."
**Extra value for ADHD users**: "Randomized timing that stays noticeable, and smart enough to not trigger your own auto-disable safety rule."

---

## Group 2: "Let Me Take My Data With Me"

**The problem**: Your app has zero export capability. Every journal session, transcript, summary, tag, and check-in score is locked inside the app's local database. If users want to share their journal with a therapist, switch to a different app, or just have a backup they can read, they can't. Your ADHD spec calls this a "documented trust-breaker" for data sovereignty.

**What you already have**: Supabase cloud sync (opt-in, partial). But no user-facing export to files.

### Pattern 9: SessionExporter Factory + Strategy + Mixin (from mhabit, 21/25)

**What it does**: A clean code structure for export: a factory class that dispatches to either "export all sessions" or "export filtered sessions" (by date range or selection). Shared serialization logic lives in a mixin, so both export paths produce identical output format without code duplication.

**Why this matters for everyone**: Data portability is a trust signal. Users who know they can leave are more likely to stay. Users who want to share session transcripts with a therapist, coach, or friend need a way to get data out. JSON export enables integration with other tools. Markdown export is human-readable.

**Why it especially matters for ADHD**: ADHD users often cycle through productivity tools. The ability to export means this app doesn't become another abandoned silo. It also enables sharing treatment-relevant data with clinicians without handing over the device.

**What it costs to build**: Medium. The pattern (factory + mixin) is straightforward. The real work is deciding the export format (JSON for machine-readable, Markdown for human-readable, or both) and building the UI (date range picker, export button, share sheet via `share_plus`). The `csv`, `pdf`, `share_plus` dependencies need to be added to pubspec.yaml.

**Does it narrow the audience?** No. Everyone benefits from data portability.

---

## Group 3: "Show Me My Past Entries Without Me Having to Search"

**The problem**: Your app has a search screen and a session list, but no proactive resurfacing. Old entries are effectively invisible unless the user remembers to look for them. There's no "on this day" feature, no gentle surfacing of past reflections.

**What you already have**: Search with filter chips. Session list grouped by month. AI-generated summaries with mood/topic/people tags.

### Pattern 10: Date-Seeded Daily-Stable Random for Resurfacing (from Daily_You, 21/25)

**What it does**: Each day, a "memory" entry is selected using the current date as a random seed. `Random(20260303)` always produces the same result for March 3rd, so the user sees the same resurfaced entry all day — no flickering on every screen rebuild. Tomorrow, a different entry surfaces.

**Why this matters for everyone**: Resurfacing past entries creates moments of unexpected reflection. "Oh, I wrote about that six months ago — interesting to see how things have changed." This is one of the most-loved features in journaling apps (Day One, Google Photos "memories"). It turns a growing archive into a living resource rather than a graveyard.

**Why it especially matters for ADHD**: ADHD often impairs autobiographical memory continuity — the sense of "how I got here." Resurfacing past entries bridges that gap by presenting past experiences without requiring the user to initiate a search. It also provides positive reinforcement ("I dealt with something similar before and it worked out").

**What it costs to build**: Low. The algorithm is ~10 lines of pure Dart. The UI integration (a card on the home screen showing today's resurfaced entry) is a straightforward widget addition.

**Implementation note**: The original Daily_You code has an infinite-loop bug. Our version should use `entries.shuffle(Random(seed)).first` instead of a while loop. We should also filter by positive/neutral sentiment before selecting — no one needs their worst day resurfaced unexpectedly.

**Does it narrow the audience?** No. "On this day" memories are universally appealing. The sentiment filter is a thoughtful default for everyone, not just ADHD users.

---

## Group 4: "Help the AI Understand My ADHD Experience"

**The problem**: Your Claude-based session analysis doesn't speak ADHD vocabulary. When a user describes executive dysfunction ("I just couldn't make myself start"), the AI might summarize it generically ("had difficulty with motivation") rather than recognizing and naming the specific ADHD experience. The AI also has no framework for recognizing ADHD strengths — hyperfocus, flow states, creative bursts. These are just "productive days" in the current analysis.

**What you already have**: Claude session analysis via Edge Function proxy. AI-generated summaries with mood tags, topic tags, and people mentioned. The ADHD spec's clinical UX constraints (epistemic humility framing, no diagnostic language). Pulse Check-In with validated instruments (PHQ-4, WHO-5, BEDS).

**Important framing**: These patterns are about enriching the AI's vocabulary, not adding ADHD-specific UI. Users don't see checkboxes or clinical forms. They speak freely. The AI gets better at understanding what they said.

### Pattern 11: ADHD Symptom Taxonomy as AI Classification Vocabulary (from ADHD_Journal_Flutter, 22/25)

**What it does**: Gives Claude a structured vocabulary for classifying what users describe in sessions. Five categories:
- **Positive States**: Hyperfocus, Flow, Momentum, Emotional Resiliency
- **Inattentive**: Brain Fog, Procrastination, Distraction, Time Blindness
- **Executive Dysfunction**: Working Memory Issues, Task Initiation Failure, Freeze/Mental Paralysis
- **Emotional Dysregulation**: Rejection Sensitivity, Emotional Flooding, Mood Swings
- **Stressors**: Anxiety, Overwhelm, Sensory Overload

**Why this matters — and why it doesn't narrow the audience**: This vocabulary lives in the Claude analysis prompt, not in the UI. Users never see these categories unless the AI mentions them in its output. A non-ADHD user who says "I had a great flow state today" gets a response that names "flow" as a positive state. An ADHD user who says "I couldn't make myself start the report" gets a response that recognizes "task initiation difficulty" rather than generic "low motivation."

The key insight from the independent-perspective specialist: **this is taxonomy-as-output, not taxonomy-as-input.** Users don't navigate symptom checklists. They talk. The AI classifies. This means the taxonomy enriches the experience for ADHD users without adding any friction for non-ADHD users — they simply never encounter the ADHD-specific vocabulary unless it's relevant to what they said.

**What it costs to build**: Low. This is prompt engineering — adding structured classification instructions to the Claude Edge Function system prompt. No Dart code changes. No schema changes. No new UI.

**Does it narrow the audience?** No. Non-ADHD users are unaffected. ADHD users get more precise, clinically-informed AI responses. The AI simply gets smarter at naming specific experiences.

---

### Pattern 12: Positive ADHD Traits as First-Class Trackable States (from ADHD_Journal_Flutter, 21/25)

**What it does**: Explicitly instructs the AI to recognize and affirm positive ADHD-associated states (Hyperfocus, Flow, Momentum, Emotional Resiliency) as named, trackable experiences — not just "had a good day."

**Why this matters**: Without this, the AI treats strengths as unmarked: "You had a productive day." With this, the AI can say: "It sounds like you entered a flow state during your writing session — that's a real strength worth noting." This is the difference between a generic journaling AI and one that understands the full ADHD experience, including the parts that work well.

**For non-ADHD users**: Flow states and creative momentum are universally experienced. Naming them is valuable for anyone. The AI doesn't say "your ADHD hyperfocus kicked in" to a non-ADHD user — it says "you described sustained deep focus." The vocabulary adapts to context.

**What it costs to build**: Near zero. Additional prompt instructions. Same implementation as Pattern 11.

**Does it narrow the audience?** No. Recognizing strengths is universally good. The ADHD-specific framing only surfaces when contextually appropriate.

---

### Pattern 13: Day-Type Taxonomy as AI Session Classification (from ADHD_Journal_Flutter, 20/25)

**What it does**: After analyzing a session, the AI assigns a "day type" label from a short vocabulary: Peak Performance, Successful, Emotional Challenge, Inattentive Struggle, Executive Dysfunction, High Stress, Neutral. This label is stored on the session record and enables trend visualization.

**Why this matters for everyone**: "What kind of day was this?" is a natural question. Having a named classification makes trends visible: "You've had 3 high-stress days this week" is more actionable than "your average mood rating dropped." The labels are descriptive, not judgmental.

**Why it especially matters for ADHD**: ADHD experiences cluster into recognizable types. Being able to see "this was an executive dysfunction day" helps users identify patterns: "My executive dysfunction days always follow poor sleep nights." That's a clinically useful insight for medication timing or lifestyle adjustments.

**For non-ADHD users**: The labels "Peak Performance," "Successful," "Emotional Challenge," "High Stress," and "Neutral" are universally meaningful. "Inattentive Struggle" and "Executive Dysfunction" would only appear when the AI identifies those specific patterns in the session content. A user who never describes ADHD-related experiences would never see those labels.

**What it costs to build**: Low-Medium. Prompt engineering for the AI classification (low). Adding a `dayType` enum column to the Drift session schema (medium — requires a migration). The column enables future trend charting but doesn't require building the chart immediately.

**Does it narrow the audience?** Minimal. Most labels are universal. The ADHD-specific labels only surface for sessions where the content warrants them.

---

## Group 5: "Track What Matters for My Treatment"

**The problem**: Your app captures rich conversation data but doesn't track two variables that are critical for ADHD treatment planning: sleep quality and medication. These aren't just ADHD concerns — sleep and medication are relevant for anyone managing a mental health condition, chronic illness, or even just a fitness routine. But they're especially important for ADHD because medication timing and sleep quality have outsized effects on daily functioning.

**What you already have**: The Pulse Check-In already captures structured self-assessment data (PHQ-4, WHO-5 items including a sleep-related question). Session timestamps, mood tags, and AI summaries. Location data.

### Pattern 14: Sleep Quality Field on Journal Sessions (from ADHD_Journal_Flutter, 21/25)

**What it does**: Adds a `sleepQuality` nullable numeric field (1-5 scale) to each journal session. During session initiation, the voice assistant can optionally ask "How did you sleep?" — the user answers with a number or a word ("great," "terribly"), and the numeric parser service (which you already built for Pulse Check-In sliders) converts it. The field is included in the Claude analysis context so the AI can correlate sleep with session content.

**Why this matters for everyone**: "I had a terrible day" means something different when the AI knows you slept 3 hours versus 8 hours. Sleep context makes AI insights more accurate for any user. It also enables future trend charting: sleep quality overlaid with mood tags or day-type classifications.

**Why it especially matters for ADHD**: Sleep dysregulation is a core ADHD comorbidity. Many ADHD medications (stimulants) directly affect sleep. The correlation between sleep quality and ADHD performance is one of the first things a prescriber wants to see. Having this data per-session, attached to the context of what happened that day, is significantly more useful than a standalone sleep tracker.

**What it costs to build**: Low. One Drift column addition (nullable double), one migration. The voice prompt is optional — skip it if the user doesn't respond. The numeric parser service already exists for Pulse Check-In.

**Overlap with Pulse Check-In**: The WHO-5 instrument includes a sleep-adjacent item ("I woke up feeling fresh and rested"). However, Pulse Check-In is a standalone flow — a user might do a journal session without doing a check-in, and vice versa. The session-level sleep field captures context at the moment of journaling, while the check-in captures a broader well-being snapshot. They complement rather than duplicate.

**Does it narrow the audience?** No. Sleep quality is universally relevant. The field is nullable — users who don't care can ignore it entirely. The voice prompt is skippable.

---

### Pattern 15: Medication Notes Field on Journal Sessions (from ADHD_Journal_Flutter, 20/25)

**What it does**: Adds a `medicationNotes` nullable text field to each journal session. Free text for dose timing, missed doses, medication changes. Included in Claude analysis context.

**Why this matters**: For users on any medication (not just ADHD medication), noting "took my medication late today" or "started a new dose" creates a timeline that the AI can reference when analyzing patterns. "You mentioned switching medication three sessions ago, and your mood tags have shifted since then — worth discussing with your prescriber."

**Why it especially matters for ADHD**: ADHD medication timing (stimulants, non-stimulants) has direct, measurable effects on daily functioning. A journaling app that knows "user took Adderall 2 hours late" can provide genuinely useful pattern analysis: "Your executive dysfunction days correlate with late medication starts."

**Caution — this is the pattern most likely to narrow the audience**: A non-ADHD, non-medicated user would never use this field. It's medication-specific by definition. However:
- The field is nullable and optional. It only appears if the user enables it in settings (or mentions medication in conversation and the AI captures it).
- Many people take daily medications beyond ADHD (antidepressants, blood pressure, insulin). The field is useful for any medication tracking, not ADHD-specific.
- The AI should never proactively ask about medication unless the user has previously mentioned it.

**What it costs to build**: Low. One nullable text column, one migration. One toggle on the Settings page (default: off). When disabled: field not captured, AI doesn't ask about medication, no medication UI shown. When enabled: voice prompts can mention medication, AI includes medication context in analysis.

**Does it narrow the audience?** No — because it's opt-in only. The feature is completely invisible until a user explicitly enables it in Settings. No user will ever encounter medication prompts, fields, or AI analysis unless they chose to turn it on. This is a developer requirement.

---

## Weighing It All: What's Universal vs. What's ADHD-Specific

| Pattern | Benefits Everyone? | Extra ADHD Value? | Audience Impact |
|---|---|---|---|
| **1. Randomized time-window alarm** | Yes — novelty in reminders | High — ADHD brains habituate faster | Universal |
| **2. Entry-existence guard** | Yes — basic notification hygiene | Moderate — respects accomplishment | Universal |
| **3. Auto-dismiss on session start** | Yes — removes clutter | Low | Universal |
| **4. whenNeeded scheduling** | Yes — smart context-aware reminders | Critical — prevents auto-disable trap | Universal |
| **5. Localized strings pre-stash** | Yes — i18n correctness | None specific | Universal |
| **6. NotificationService interface** | N/A — engineering quality | None specific | Invisible |
| **7. Injectable AppClock** | N/A — testing infrastructure | None specific | Invisible |
| **8. Notification ID namespace** | N/A — collision prevention | None specific | Invisible |
| **9. SessionExporter** | Yes — data portability / trust | High — ADHD users cycle tools | Universal |
| **10. Date-seeded resurfacing** | Yes — "on this day" memories | High — bridges memory gaps | Universal |
| **11. ADHD symptom vocabulary** | Neutral — invisible to non-ADHD | High — precise AI understanding | Unnoticeable to non-ADHD |
| **12. Positive traits as states** | Yes — recognizing flow/strengths | High — de-pathologizes ADHD | Universal |
| **13. Day-type classification** | Mostly — 5 of 7 labels universal | High — ADHD-specific labels when relevant | Mostly universal |
| **14. Sleep quality field** | Yes — sleep affects everyone | High — core ADHD comorbidity | Universal |
| **15. Medication notes** | For medicated users (any condition) | High — stimulant timing correlation | Opt-in only (Settings toggle, default off) |

**Bottom line**: 12 of 15 patterns are universally beneficial. The remaining 3 (ADHD vocabulary, day-type labels, medication notes) are designed to be invisible to non-ADHD users — they only surface when contextually relevant. None of these patterns turn your app into an "ADHD-only tool." They make it an excellent general journal that is *especially* good for ADHD users.

---

## Recommended Build Order (When You're Ready)

**Sprint A: Notification subsystem** (Patterns 1-8)
- This is one cohesive feature: "smart, gentle reminders"
- Highest user-facing impact — moves the app from passive to proactive
- Dependencies: `android_alarm_manager_plus`, `flutter_local_notifications`
- Prerequisite: none — can be built independently of everything else

**Sprint B: AI vocabulary enrichment** (Patterns 11, 12, 13)
- This is prompt engineering, not Dart code
- Fastest to build — could be done in a single session
- Pattern 13 (day-type) requires a Drift migration for the enum column
- Prerequisite: none — independent of notification work

**Sprint C: Resurfacing** (Pattern 10)
- Small, self-contained feature
- Depends on having enough sessions to resurface (works best after users have 30+ entries)
- Prerequisite: none

**Sprint D: Data export** (Pattern 9)
- Medium effort — format decisions needed (JSON, Markdown, CSV, PDF?)
- Dependencies: `csv`, `share_plus`, optionally `pdf` and `printing`
- Prerequisite: none — but benefits from having more data types to export (sleep, medication, day-type)

**Sprint E: Schema additions** (Patterns 14, 15)
- Low effort per field, but each requires a Drift migration
- Best bundled with other schema work (like Pattern 13's day-type column)
- Can be built any time — optional fields don't break existing sessions

---

## What These Patterns Do NOT Cover

Gaps that remain open after adopting all 15 patterns:

- **Phase 2A gap-shaming removal** — `daysSinceLast` is still in 3 AI layer files. This is a 5-line fix independent of any discovery work.
- **Home screen widget** — still needs `home_widget` package integration (Pattern from discovery search, not yet analyzed)
- **Charting/trend visualization** — you have `fl_chart` in pubspec already for Pulse Check-In history. The day-type and sleep fields (Patterns 13, 14) create the data for richer trend charts, but the chart UI itself isn't covered by these patterns.
- **Biometric lock** — deferred by your decision. The patterns exist in the adoption log for when you're ready.
- **Deepgram STT** — ADR-0031 still unwritten. Separate from all discovery work.
- **STT pause timeout P0 fix** — the 1-line `pauseFor: Duration(seconds: 2)` change. Still not shipped.
