---
discussion_id: DISC-20260302-222128-review-intent-classifier-google-calendar-fix
started: 2026-03-02T22:21:43.881810+00:00
ended: 2026-03-02T22:26:42.088585+00:00
agents: [facilitator, independent-perspective, qa-specialist]
total_turns: 6
---

# Discussion: DISC-20260302-222128-review-intent-classifier-google-calendar-fix

## Turn 1 — facilitator (evidence)
*2026-03-02T22:21:43.881810+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Fix intent classifier to handle 'Add a Google Calendar meeting' (user-reported: device showed Claude's 'I can't access your Google Calendar' response instead of the calendar card)
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: User confirmed Google Calendar is connected in Settings; the phrase 'Add a Google Calendar meeting' was bypassing intent routing because 'a Google Calendar ' (19 chars) exceeds the .{0,15} character limit in the calendarIntentPattern regex
- **Explicit constraints**: Must not introduce false positives (e.g., 'add a note about my team meeting' should not trigger calendar intent); conservative fix targeted at the specific pattern gap

---

## Turn 2 — qa-specialist (proposal)
*2026-03-02T22:24:32.582596+00:00 | confidence: 0.88*
*tags: qa, low-risk*

## QA Review — Intent Classifier Google Calendar Fix
confidence: 0.88

### Coverage Assessment
The new regression group (4 tests) directly covers both changed sub-patterns. 81.2% total coverage clears the 80% threshold. Untested paths: bare 'add calendar meeting' (google\s+ optional making google optional), the .{0,20} right-limit boundary, and some case-variant inputs (handled by caseSensitive: false but not explicitly tested).

### Findings

**Finding 1 (Low/Advisory): Missing false-positive guard test**
The developer-stated constraint ('add a note about my team meeting → journal') is not tested. The new sub-pattern's ^add + required calendar keyword correctly prevents this false positive, but there is no test codifying the constraint. A future widening could silently break it.
Recommendation: Add test: '"Add a note about my team meeting" → journal (false-positive guard)'.

**Finding 2 (Low/Advisory): Confidence floor comment**
The test at line 273 asserts confidence >= 0.5 with no margin signal. This is correct since 0.5 is the routing threshold. No change needed, but a test comment documenting this is the floor (no temporal context) would aid future maintainers.

**Finding 3 (Low/Advisory): 'invitation' not in event noun list**
'Add a Google Calendar invitation' falls through to journal by design. This is acceptable conservative scope, but the gap between design intent and user natural speech is unverified by test.

**Finding 4 (Low/Advisory): 'Add it to Google Calendar' untested**
Change 1 makes (my\s+|the\s+)? optional, so 'add it to Google Calendar' (no possessive) should match. No test verifies end-to-end optionality chain.

**Protocol gap (Low/Advisory):** @Tags(['regression']) annotation absent from the 4 new tests. Appears to be a project-wide pattern (test group naming used instead). Not blocking merge.

### Regression Risk
Low. Change 2 is strictly more specific than the existing ^add sub-pattern (requires 'calendar' keyword). Change 1 adds only optional (google\s+) to an existing 40-char-latitude branch. All 1925 tests pass. Prior regression suite (20 journal/query cases) shows no regressions.

### Strengths
Conservative fix scope, correct false-positive handling via ^anchor + required 'calendar' keyword, complete ledger entry, well-structured test group with positive + high-confidence + inverse-phrasing + third-verb-variant cases.

---

## Turn 3 — independent-perspective (proposal)
*2026-03-02T22:24:49.496996+00:00 | confidence: 0.72*
*tags: independent, structural-concern*

## Independent Perspective — Intent Classifier Google Calendar Fix
confidence: 0.72

### Hidden Assumptions

1. **Only Google Calendar brand is handled.** 'Microsoft Outlook Calendar' (20 chars) and 'Apple iCloud Calendar' have the same structural failure — a named-calendar modifier exceeds .{0,15} between 'add' and the event noun. Enterprise users (Wells Fargo context) commonly have Outlook Calendar. This remains broken after this fix.

2. **The .{0,15} magic number has no documented rationale.** No code comment explains why 15 was chosen. The fix introduces .{0,20} for the new sub-pattern without explaining the bound. If the original limit prevented false positives, the reasoning for 20 being safe is absent.

3. **^add anchor breaks for voice preambles.** 'Okay, add a Google Calendar meeting' fails the ^add anchor. Voice mode is live. This is a pre-existing limitation not introduced by this fix, but the fix does not address it.

4. **No defense-in-depth at routing boundary.** A message containing 'calendar' that falls through to Claude produces a confusing response. No log/debug signal exists to detect future pattern gaps before user reports.

### Pre-Mortem Scenarios

**Scenario 1 (Medium likelihood): Outlook Calendar fails identically**
'Add an Outlook Calendar meeting' — 'an Outlook Calendar ' = 20 chars, exceeds the new .{0,20} sub-pattern's .{0,15} left limit too. Enterprise users get same silent fallthrough to Claude.

**Scenario 2 (Medium likelihood): Voice preamble breaks ^add anchor**
'Hey, add a Google Calendar meeting for tomorrow' — ^add anchor fails. Fix ships but same symptom reappears in voice mode.

**Scenario 3 (Low likelihood): .{0,20} widening admits false positive**
Unlikely in realistic speech. Confirmation gate (ADR-0020 §8) provides backstop — user sees dismissable card, no silent action.

**Scenario 4 (Low likelihood): 'Put a Google Calendar meeting on my schedule'**
'schedule' as calendar synonym not matched by either change. Pre-existing gap.

### Structural Alternative
Replace character-count wildcard with word-count: ^add\b(\s+\w+){0,5}\s+\b(meeting|appointment|...) handles any modifier phrase up to 5 words regardless of character count. Would eliminate the entire class of character-count boundary bugs. Trade-off: slightly broader false-positive surface (mitigated by confirmation gate).

### Consensus Check
The fix is correct for its stated scope. The concern is scope narrowness: the next user who says 'Add an Outlook Calendar meeting' will file the same bug report. On record: .{0,N} character counting should be revisited as the structural approach for intent patterns with variable-length modifiers.

### Strengths
Change 1 (google\s+? addition to existing branch) is the cleaner of the two changes — purely additive, no new sub-pattern, no new character limit. Confirmation gate backstop makes the false-positive risk genuinely low. Regression test group is more thorough than minimally required. Ledger entry is complete.

---

## Turn 4 — facilitator (synthesis)
*2026-03-02T22:25:15.482213+00:00 | confidence: 0.85*
*tags: blocking:0, advisory:6*

## Request Context
- **What was requested**: Fix intent classifier to handle 'Add a Google Calendar meeting' (user-reported on device: phrase bypassed intent routing, Claude responded 'I can't access your Google Calendar')
- **Files/scope**: lib/services/intent_classifier.dart, test/services/intent_classifier_test.dart, memory/bugs/regression-ledger.md
- **Developer-stated motivation**: The phrase 'a Google Calendar ' (19 chars) exceeded the .{0,15} character limit in _calendarIntentPattern, causing silent fallthrough to Claude despite Google Calendar being connected in Settings
- **Explicit constraints**: No false positives (e.g., 'add a note about my team meeting' must not trigger calendar intent); conservative, targeted fix

## Verdict: approve-with-changes

**Blocking findings: 0**
**Advisory findings: 6**

## Advisory Findings (non-blocking)

**A1 (QA):** Add false-positive guard test — 'Add a note about my team meeting → journal'. Developer-stated constraint is correctly handled by the regex but not codified in a test. One-liner addition.

**A2 (QA):** Add test for 'Add it to Google Calendar' (no possessive) to confirm optionality chain in Change 1 works end-to-end.

**A3 (QA):** Protocol gap — @Tags(['regression']) absent from 4 new tests. Project-wide pattern (group naming used instead), not blocking merge.

**A4 (Independent):** Other named-calendar brands (Outlook Calendar, iCloud Calendar) have the same structural failure. 'Add an Outlook Calendar meeting' still falls through to Claude after this fix. Known scope limitation. Consider a follow-up structural fix (word-count wildcard or brand-agnostic approach).

**A5 (Independent):** ^add anchor breaks for voice preambles ('Okay, add a Google Calendar meeting'). Pre-existing limitation, not introduced by this fix. Worth a TODO comment or follow-up.

**A6 (Independent):** Defense-in-depth logging at the routing boundary — if a message containing 'calendar' falls through to journal/Claude, a debug log would surface future pattern gaps earlier than user reports.

## Strengths

- Correct fix for the reported case — 'Add a Google Calendar meeting' now routes to the calendar handler
- Change 1 (google\s+? in to/on...calendar branch) is cleanly additive; no new sub-pattern, no new character limit
- The ^add + required 'calendar' keyword in Change 2 prevents the stated false positive ('add a note about my team meeting') without requiring a separate test to confirm at regex-match level
- 4-test regression group covers positive case, high-confidence case, inverse phrasing, and third verb variant
- Confirmation gate (ADR-0020 §8) backstops any false positive from the .{0,20} widening — user sees a dismissable card, no silent action
- Regression ledger entry is complete (bug, root cause, fix, test location, date)
- 1925 tests pass, 81.2% coverage, 7/7 quality gate checks

## Structural Note on Record

The independent-perspective correctly identifies that .{0,N} character counting is structurally brittle for intent patterns with variable-length modifiers. This fix correctly addresses the reported symptom. The class of problem (any brand-named calendar modifier exceeding the character limit) remains open. Recommend Sprint N+1 consideration: replace ^add\b.{0,15} with a word-count approach ^add\b(\s+\w+){0,5}\s+\b.

---

## Turn 5 — qa-specialist (reflection)
*2026-03-02T22:26:42.029285+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The four advisory findings I raised were real, but I underweighted the structural brittleness issue that independent-perspective surfaced: the .{0,N} character-counting approach is an entire class of latent bugs, not just an edge case. I noted the .{0,20} boundary had no documented rationale, but I treated it as advisory rather than flagging it as a maintainability risk that deserves a TODO comment at minimum. I also did not check whether voice preamble patterns ('Okay, add a...') affected the fix — a pre-existing gap that voice mode made newly relevant.

## Candidate Improvement Rule
For regex-based intent classifiers: when reviewing a character-limit wildcard fix (.{0,N}), always check (1) whether the bound is documented with rationale in a comment, and (2) whether the same limit applies to structurally equivalent phrases not covered by the fix. If both fail, escalate the finding from advisory to medium.

## Confidence Calibration
Original: 0.88, Revised: 0.82, Delta: -0.06

---

## Turn 6 — independent-perspective (reflection)
*2026-03-02T22:26:42.088585+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
The most significant gap was not verifying whether google\s+ was already present in the Change 1 branch before the fix. I relied on the facilitator's context brief rather than reading the pre-fix regex directly. If the original pattern had already contained it, Change 1 would have been a no-op and the bug's actual root cause would have been elsewhere. Next time: read the pre-fix regex directly and confirm what changed verbatim.

## Candidate Improvement Rule
When reviewing a regex bug fix, always diff the old pattern against the new pattern explicitly. State the before/after strings verbatim in the review event. Never rely solely on the developer's narrative description — the review record should be self-contained evidence that the fix addresses the stated root cause.

## Confidence Calibration
Original: 0.72, Revised: 0.74, Delta: +0.02. Small upward revision: after re-reading the actual regex, the false-positive risk from .{0,20} widening is even lower — the ^add anchor plus required calendar keyword is a tighter gate than prose suggested. Core uncertainty about scope narrowness remains.

---
