---
discussion_id: DISC-20260223-002154-quiz-phase5-search-memory-recall
started: 2026-02-23T00:23:24.282509+00:00
ended: 2026-02-23T00:23:24.282509+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260223-002154-quiz-phase5-search-memory-recall

## Turn 1 — educator (proposal)
*2026-02-23T00:23:24.282509+00:00 | confidence: 0.88*
*tags: quiz, education, blooms-taxonomy*

```yaml
quiz_id: QUIZ-20260223-002154
module: Phase 5 - Search + Memory Recall
files_covered:
  - lib/models/search_models.dart
  - lib/services/intent_classifier.dart
  - lib/repositories/search_repository.dart
  - lib/providers/search_providers.dart
  - lib/ui/screens/search_screen.dart
  - lib/ui/widgets/search_result_card.dart
bloom_distribution: {understand: 3, apply: 3, analyze: 2, evaluate: 2}
pass_threshold: 0.70
question_count: 10
```

---

## Questions

### Q1 [Understand] - Data Flow
**Explain the end-to-end data flow when a user types "What did I write about anxiety last week?" into the chat. Trace through the components: which classes are involved, in what order, and what does each one produce?**

Focus on: IntentClassifier -> SearchRepository -> ClaudeApiService recall, and where the offline boundary sits.

---

### Q2 [Understand] - Conservative Default
**Why does IntentClassifier default to `IntentType.journal` rather than `IntentType.query`? What user experience problem would the opposite default create?**

Reference the confidence tiers and explain what happens at each tier (< 0.5, 0.5-0.8, >= 0.8).

---

### Q3 [Understand] - Type Separation
**Why is `RecallResponse` a separate type from `AgentResponse` rather than extending it or adding a `citedSessionIds` field to `AgentResponse`? What are the two different things they model?**

---

### Q4 [Apply] - LIKE Escape Tracing
**A user searches for the string `100% done_`. Trace what happens to this query string as it passes through `escapeLikeWildcards()` and then into a `LikeWithEscape` expression. What SQL would be generated, and what would happen if the escaping were missing?**

---

### Q5 [Apply] - Dedup Tracing
**Session "sess-42" has the word "hiking" in both its summary AND in a message. Walk through the dedup logic in `SearchRepository.searchEntries()`. How many times does "sess-42" appear in the final results, and with what `MatchSource` value? Why is the dedup rule designed this way?**

---

### Q6 [Apply] - Filter Provider Chain
**A user selects the "Last 7 days" date preset and the mood tag "anxious" on the search screen. Trace how these filter selections propagate from the UI through the provider chain to the actual database query. Name each provider touched and what it does.**

---

### Q7 [Analyze] - Debug Scenario
**A user reports: "I searched for 'meeting with Sarah' and got zero results, but I know I wrote about meeting Sarah last Tuesday." The session exists in the database with summary "Talked about the meeting with Sarah at work" and a message containing "Had a great meeting with Sarah today." List at least three possible causes for the zero-result bug, ordered by likelihood. For each cause, describe how you would verify it.**

---

### Q8 [Analyze] - Offline Architecture
**Compare the search experience when the device is online vs. offline. Which specific components and providers still function offline, which ones fail, and how does the UI communicate the degradation to the user? Why was it designed as ambient degradation rather than a blocking error modal?**

---

### Q9 [Evaluate] - Change Impact
**Suppose you need to add a new filter dimension: "location" (e.g., "home", "office", "cafe"). List every file you would need to modify across the Phase 5 codebase, what change you would make in each, and identify which change carries the most risk of breaking existing functionality.**

---

### Q10 [Evaluate] - Design Critique
**The intent classifier uses rule-based pattern matching instead of an LLM call. ADR-0013 gives three reasons for this choice. Do you agree with all three? Can you identify a scenario where pattern matching would fail badly enough to justify adding LLM-based classification, and what would the cost (latency, connectivity, complexity) be?**

---

## Answer Key

### A1 [Understand] - Data Flow
Expected answer covers:
1. IntentClassifier.classify() receives the message, scores it across 4 categories: question+past (+0.4) and temporal+question (+0.3) = 0.7 -> IntentType.query with ambiguous confidence
2. UI shows inline confirmation prompt (0.5-0.8 range)
3. User confirms -> SearchRepository.searchEntries() runs parallel LIKE queries (SessionDao + MessageDao)
4. Results deduplicated, ranked (summary first, then message-only)
5. SearchRepository.getSessionContext() formats top 10 sessions as maps (USER messages only, truncated)
6. ClaudeApiService.recall() sends question + context to Edge Function
7. RecallResponse returned with answer + citedSessionIds
8. Citation validation: IDs checked against local DB before display
**Offline boundary**: Steps 1-5 work offline. Step 6 requires connectivity. Offline fallback shows local results as tappable cards.
**Scoring**: 1.0 for full trace with offline boundary. 0.5 for partial trace missing key steps. 0.0 for incorrect ordering or missing components.

### A2 [Understand] - Conservative Default
Expected answer:
- Journal default prevents jarring mode switches during active journaling. If the default were query, common conversational messages ("What?", "Really?", "I remember feeling happy") would trigger search mode, interrupting the journaling flow.
- Confidence tiers: < 0.5 = continue journaling (inverse confidence for journal), 0.5-0.8 = show inline confirmation ("Did you want to search?"), >= 0.8 = auto-route to recall
- The missed-query cost is low (user can always use the dedicated search screen), but the false-positive cost is high (disrupts journaling UX)
**Scoring**: 1.0 for explaining the asymmetric cost of false positives vs false negatives, plus all three tiers. 0.5 for getting the tiers but missing the UX rationale. 0.0 for incorrect tier behavior.

### A3 [Understand] - Type Separation
Expected answer:
- AgentResponse models a conversational turn (content, layer, metadata) in the journaling flow
- RecallResponse models a search-grounded answer with citations (answer text + cited session IDs)
- Merging them would force citations into metadata (semantic mismatch), require nullable citedSessionIds on every AgentResponse, and create confusion about when the field is meaningful
- Different display requirements: conversation turns show in chat bubbles, recall answers need citation chips
**Scoring**: 1.0 for identifying both abstractions and explaining why merging dilutes them. 0.5 for partial explanation. 0.0 for suggesting they should be merged.

### A4 [Apply] - LIKE Escape Tracing
Expected answer:
- Input: "100% done_"
- After escapeLikeWildcards(): "100!% done!_" (! escapes itself first, then % and _)
- The LIKE pattern becomes: "%100!% done!_%" (wrapped in wildcards for substring match)
- Generated SQL: `column LIKE '%100!% done!_%' ESCAPE '!'`
- Without escaping: "100% done_" would be interpreted as "100" + any chars + " done" + any single char, matching far more than intended. The % would match any string and _ would match any single character.
**Scoring**: 1.0 for correct escape sequence, correct SQL output, and correct description of unescaped behavior. 0.5 for mostly correct with minor errors. 0.0 for fundamental misunderstanding of LIKE escaping.

### A5 [Apply] - Dedup Tracing
Expected answer:
- SessionDao.searchSessions("hiking") returns sess-42 (summary match)
- MessageDao.searchMessages("hiking") returns a message with sessionId = "sess-42"
- summaryMatchIds set contains "sess-42"
- sess-42 is added to results with MatchSource.summary
- When processing message results, sess-42 is in summaryMatchIds, so it is SKIPPED (not added again)
- Final: sess-42 appears ONCE with MatchSource.summary
- Design rationale: Summary match is a stronger signal (AI already distilled what was important). Showing duplicate results for the same session wastes screen space.
**Scoring**: 1.0 for correct single appearance, correct MatchSource, and rationale. 0.5 for correct result but missing rationale. 0.0 for saying it appears twice.

### A6 [Apply] - Filter Provider Chain
Expected answer:
1. User taps "Last 7 days" -> _showDateRangePicker creates SearchFilters with dateStart/dateEnd, writes to searchFiltersProvider.notifier.state
2. User selects "anxious" mood -> _showMultiSelectSheet -> onSelected callback creates new SearchFilters with existing date range + moodTags: ["anxious"], writes to searchFiltersProvider.notifier.state
3. searchResultsProvider watches both searchQueryProvider and searchFiltersProvider; it re-evaluates when either changes
4. searchResultsProvider calls searchRepo.searchEntries(query, filters: filters)
5. SearchRepository passes filters to SessionDao.searchSessions() which applies dateStart/dateEnd as WHERE clauses and moodTags as LIKE substring match against the JSON moodTags column
**Scoring**: 1.0 for full chain from UI through providers to DAO. 0.5 for getting the provider chain but missing the DAO filter application. 0.0 for incorrect provider dependencies.

### A7 [Analyze] - Debug Scenario
Expected answer should include at least 3 of:
1. **Search query too long / multi-word LIKE limitation**: LIKE "%meeting with Sarah%" requires the exact phrase. If the summary has "meeting with Sarah" but LIKE is applied per-word, each word matches separately. Verify: check how the search query is passed to LIKE -- is it the full phrase or individual words?
2. **Date filter active**: User may have a date filter active that excludes last Tuesday. Verify: check searchFiltersProvider state for active date range.
3. **Session not yet synced / created after last search index update**: The session exists but may not have been committed to the local database yet. Verify: query SessionDao directly for the session ID.
4. **Case sensitivity issue**: Though LIKE is case-insensitive in SQLite by default for ASCII, verify the query and content case handling.
5. **LIKE escape bug**: If the query contains special characters that get incorrectly escaped. Verify: check escapeLikeWildcards output for the query.
**Scoring**: 1.0 for 3+ plausible causes with verification steps. 0.5 for 2 causes with verification. 0.0 for fewer than 2 or implausible causes.

### A8 [Analyze] - Offline Architecture
Expected answer:
- **Online**: Full functionality -- keyword search (local), filters (local), recall synthesis (Claude API), citation navigation
- **Offline**: IntentClassifier works (pattern matching, no network). SearchRepository works (local SQLite). All filter providers work. searchResultsProvider works. recallAnswerProvider FAILS (depends on claudeApiServiceProvider which needs connectivity). sessionCountProvider works.
- **UI degradation**: Non-blocking banner "Searching local data - Natural language recall unavailable offline" using connectivityServiceProvider.isOnline check. NOT a blocking error modal.
- **Why ambient**: Blocking modals interrupt the user and suggest the app is broken. Search still works locally, only synthesis is unavailable. The banner informs without blocking. Per ADR-0013 section 7: "No error state -- ambient offline indicator, not blocking modal."
**Scoring**: 1.0 for correct online/offline component breakdown plus UX rationale. 0.5 for correct breakdown but missing rationale. 0.0 for saying search does not work offline.

### A9 [Evaluate] - Change Impact
Expected answer should identify at minimum:
1. **search_models.dart**: Add `location` field to SearchFilters, update hasActiveFilters, update SearchFilters.empty
2. **JournalSessions table / drift schema**: Add `location` column (or use existing metadata)
3. **session_dao.dart**: Add location parameter to searchSessions(), add LIKE filter clause
4. **search_providers.dart**: Add availableLocationsProvider (like availableMoodTagsProvider)
5. **search_screen.dart**: Add location FilterChip to _FilterChipRow, add _showMultiSelectSheet call for locations
6. **session_dao.dart**: Add getDistinctLocations() method
7. **Existing tests**: Update SearchFilters construction in tests

**Highest risk change**: The drift schema migration (adding a column) -- requires a database migration, could fail on existing installs if migration is incorrect, and is the hardest to roll back.
**Scoring**: 1.0 for 5+ correct files with specific changes and identifying the schema migration as highest risk. 0.5 for 3-4 files or missing the risk assessment. 0.0 for fewer than 3 files.

### A10 [Evaluate] - Design Critique
Expected answer should engage with:
- ADR-0013's three reasons: latency (LLM call on every message), connectivity requirement (breaks offline-first), cost (unnecessary for pattern-matchable problem)
- A scenario where pattern matching fails: non-English input (known limitation), highly novel phrasings ("Tell me the vibe of my February"), indirect queries ("I wonder if I have been talking about work too much lately")
- Cost assessment: LLM classification would add 1-3 seconds latency per message, require connectivity for ALL classification (not just recall), and need a separate Edge Function mode or client-side model
- Reasonable conclusion: Pattern matching is the right v1 choice because the miss cost is low (dedicated search screen as escape valve), but LLM classification could be layered on later for the ambiguous 0.3-0.5 confidence zone
**Scoring**: 1.0 for engaging critically with all three reasons plus a plausible failure scenario with cost analysis. 0.5 for partial engagement. 0.0 for uncritical acceptance or rejection without reasoning.

---
