---
spec_id: SPEC-20260303-010332
title: "Sprint N+1: Intent Classifier Stability + Framework Advisory Resolution"
status: reviewed
reviewed_by: [architecture-consultant, qa-specialist]
discussion_id: DISC-20260303-010442-sprint-n1-intent-classifier-refactor-advisory-resolution-spec-review
risk_level: low
---

## Goal

Two parallel tracks:

1. **Intent classifier stability** — eliminate the class of regression that produced PR #56
   and PR #57 by extracting a shared noun constant and replacing brittle char-limit wildcards
   with word-count wildcards. Prevents Outlook Calendar, iCloud Calendar, and any
   future brand-modifier failure without requiring another targeted patch.

2. **Framework advisory resolution** — close the highest-priority advisories from the
   recent review series that are quick to address: INVARIANT comments in context-brief
   steps, cold-start fallback guidance, privacy filter omission in `build_module.md`, and
   ADR-0030 stub.

## Context

**Intent classifier**: REV-20260302-230547 advisory A3 identified three divergent event
noun lists in `intent_classifier.dart`. REV-20260302-222520 advisory A4 identified that
the `.{0,N}` char-limit pattern is structurally brittle for any modifier exceeding N chars
("an Outlook Calendar " = 20 chars, still fails). Both issues stem from the same root
cause as PR #56 and PR #57. Estimated effort: <1 hour, zero behavior change for existing
passing tests.

**Framework advisories**: PR #58 (context-brief rollout) closed 3 blocking findings but
left 6 advisories. A1/A2 (INVARIANT comment + cold-start fallback) and A4 (privacy filter
omission) are quick (<15 min each) and prevent the next review from re-raising the same
finding. ADR-0030 stub resolves the unresolvable CLAUDE.md reference.

## Requirements

### Track 1 — Intent Classifier Refactor

**R1.1 — Shared event noun constant**
Extract a `static const String _calendarEventNouns` from `intent_classifier.dart` that
contains the union of nouns currently appearing in `_calendarIntentPattern` and
`_hasStrongCalendarSignal` (7 nouns: meeting, appointment, event, dinner, lunch, call,
reservation). All three regex sites that reference this list must use the shared constant.
`_eventNounPattern` may retain its extended list (15 nouns) with a comment documenting
why it differs.

**R1.2 — Word-count wildcard for verb + noun patterns**
In **both** `_calendarIntentPattern` AND `_hasStrongCalendarSignal`, replace the
`^(add|set)\b.{0,15}\b` char-count wildcard with a word-count wildcard:
`^(add|set)\b(\s+[\w-]+){0,4}\s+\b`. Use `[\w-]+` (not `\w+`) so hyphenated modifiers
like "follow-up" are treated as a single token. This allows up to 4 intervening words,
making the pattern brand-agnostic (Outlook Calendar, iCloud Calendar, Apple Calendar all
fit within 4 words). Both locations must be updated in the same commit — failing to update
`_hasStrongCalendarSignal` in sync is the root cause of PR #57. The Google Calendar
sub-pattern `^(add|set)\b.{0,15}\b(google\s+)?calendar\b.{0,20}\b...` is superseded
and can be removed once the word-count pattern covers it.

**R1.3 — Voice preamble anchor**
Advisory A5 from REV-20260302-222520: the `^` anchor blocks "Okay, add a Google Calendar
meeting" in voice mode (preamble precedes "add"). In `_calendarIntentPattern` only,
replace `^(add|set)\b` with `\b(add|set)\b`. Do NOT remove the `^` anchor from
`_hasStrongCalendarSignal` — that method is a short-message guard where start-of-string
matching is intentional. Rely on the word-count wildcard plus event noun requirement to
prevent false positives from de-anchored matching.

**R1.4 — Regression tests**
Add regression tests in `test/services/intent_classifier_test.dart` for:

*Brand-name calendar tests (word-count wildcard, long-message path):*
- "Add an Outlook Calendar meeting" → calendarEvent, confidence >= 0.5
- "Set an iCloud Calendar appointment" → calendarEvent, confidence >= 0.5

*Short-message guard path tests (4-word inputs, exercises `_hasStrongCalendarSignal`):*
- "Add an Outlook meeting" → calendarEvent, confidence >= 0.5 (4 words)
- "Set an iCloud call" → calendarEvent, confidence >= 0.5 (4 words)

*Voice preamble test (anchor removal):*
- "Okay add a meeting tomorrow" → calendarEvent, confidence >= 0.5

*Word-count boundary tests:*
- "Add a new Google Calendar meeting" → calendarEvent (4-word modifier, boundary pass)

*False-positive guards (de-anchored pattern must not match non-calendar uses):*
- "I set a record at the gym today" → journal
- "She asked me to add notes to the doc" → journal

All tests in a new group tagged `@Tags(['regression'])`, confidence assertions included.

### Track 2 — Framework Advisory Resolution

**R2.1 — INVARIANT comment in context-brief steps**
In each of the five command files (review.md, deliberate.md, build_module.md, plan.md,
retro.md), add a comment block immediately before the `write_event.py` call in the
context-brief step:
```
# INVARIANT: This must be the first write_event.py call in this workflow.
# turn_id=1 is required for extraction pipeline integrity. Any reordering
# silently breaks context-brief capture. See DISC-20260302-231156.
```

**R2.2 — Cold-start fallback guidance in context-brief steps**
In the same five command files, add a fallback instruction after the four-field template:
```
# If invoked without prior conversational context (cold start), populate all four
# fields as "(none stated)" and add tag "context-brief-cold-start" so uninstrumented
# invocations are queryable: --tags "context-brief,context-brief-cold-start"
```

**R2.3 — Privacy filter in build_module.md**
Add the sentence "Strip business context (deadlines, client names, regulatory pressures)
— record structural intent only." to the context-brief step in `build_module.md`, matching
the phrasing in `review.md` and `deliberate.md`. (Advisory A4 from REV-20260302-232244.)

**R2.4 — CLAUDE.md context-brief command list**
Add a line to the Capture Pipeline section listing which commands emit context-brief events
and why the two are excluded:
```
Context-brief events (turn_id=1, agent="facilitator", tags="context-brief") are emitted
by: /review, /deliberate, /build_module, /plan, /retro. Excluded: /analyze-project
(outward-facing scouting, no developer request context), /meta-review (aggregate analysis,
no single request context). (Advisory A3 from REV-20260302-232244.)
```

**R2.5 — ADR-0030 stub**
Create `docs/adr/ADR-0030-developer-input-capture.md` with status `proposed`. The stub
must contain: title, status, context (one paragraph referencing SPEC-20260302-192548
Step 3), and a "Decision: pending — requires two-sprint Step 2 evaluation gate" section.
This resolves the unresolvable reference in CLAUDE.md and marks the deferred decision as
an explicit placeholder. (Advisory A5 from REV-20260302-232244.)

## Constraints

- **Zero behavior change for currently-passing tests**: The noun constant refactor must
  not change which messages match. The word-count wildcard must match everything the
  char-count wildcard matched plus broader coverage. Verify with existing regression tests.
- **No new Flutter dependencies**: Dart regex changes only — no pubspec.yaml changes.
- **Framework changes are documentation-only**: R2.1–R2.5 touch `.claude/commands/`,
  `CLAUDE.md`, and `docs/adr/` only. No Python scripts modified.
- **Regression tests required**: Every behavioral change in R1.2/R1.3 requires a tagged
  regression test per `testing_requirements.md`.

## Acceptance Criteria

### Track 1
- [ ] `static const String _calendarEventNouns` exists in `intent_classifier.dart` and is
      referenced by both `_calendarIntentPattern` and `_hasStrongCalendarSignal`.
- [ ] Both `_calendarIntentPattern` and `_hasStrongCalendarSignal` use word-count wildcard
      `(\s+[\w-]+){0,4}` instead of `.{0,15}`. Both locations updated in same commit.
- [ ] All existing calendar regression tests still pass (no regressions from refactor).
- [ ] "Add an Outlook Calendar meeting" → calendarEvent, confidence >= 0.5.
- [ ] "Set an iCloud Calendar appointment" → calendarEvent, confidence >= 0.5.
- [ ] "Add an Outlook meeting" (4 words) → calendarEvent, confidence >= 0.5 (short-msg guard path).
- [ ] "Set an iCloud call" (4 words) → calendarEvent, confidence >= 0.5 (short-msg guard path).
- [ ] "Okay add a meeting tomorrow" → calendarEvent, confidence >= 0.5 (voice preamble).
- [ ] "Add a new Google Calendar meeting" (4-word modifier) → calendarEvent (boundary test).
- [ ] "I set a record at the gym today" → journal (false-positive guard).
- [ ] "She asked me to add notes to the doc" → journal (false-positive guard).
- [ ] `flutter test` passes with coverage ≥ 80%.

### Track 2
- [ ] All five context-brief command steps contain the INVARIANT comment block.
- [ ] All five context-brief command steps contain the cold-start fallback instruction.
- [ ] `build_module.md` context-brief step contains the privacy filter sentence.
- [ ] CLAUDE.md Capture Pipeline section contains the context-brief command list.
- [ ] `docs/adr/ADR-0030-developer-input-capture.md` exists with status `proposed`.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Word-count wildcard introduces false positives | Low | Medium | Existing false-positive tests ("set the table", "set a reminder") must continue to pass; add explicit false-positive tests for new coverage |
| Anchor removal causes false calendar intent from narrative | Low | Medium | `_ambiguousThreshold = 0.5` and confirmation gate (ADR-0020 §8) backstop any increase |
| Noun constant extraction breaks a pattern via incorrect interpolation | Low | Low | Run full test suite before committing; constant is string-only, no regex engine changes |

## Affected Components

### Track 1
- `lib/services/intent_classifier.dart` — constant extraction, pattern update
- `test/services/intent_classifier_test.dart` — new regression tests

### Track 2
- `.claude/commands/review.md`, `deliberate.md`, `build_module.md`, `plan.md`, `retro.md`
- `CLAUDE.md`
- `docs/adr/ADR-0030-developer-input-capture.md` (new)

## Dependencies

- Depends on: PR #56, PR #57 (event noun lists and patterns are now the source of truth)
- Depends on: PR #58 (context-brief rollout is the source of advisory A1–A6)
- Nothing depends on this sprint yet

## Estimated Effort

| Item | Estimate |
|---|---|
| R1.1 Shared constant | 20 min |
| R1.2 Word-count wildcard | 20 min |
| R1.3 Voice preamble anchor | 15 min |
| R1.4 Regression tests | 20 min |
| R2.1 INVARIANT comments (×5 files) | 15 min |
| R2.2 Cold-start fallback (×5 files) | 10 min |
| R2.3 Privacy filter in build_module.md | 5 min |
| R2.4 CLAUDE.md command list | 5 min |
| R2.5 ADR-0030 stub | 15 min |
| **Total** | **~2 hours** |
