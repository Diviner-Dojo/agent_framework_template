---
discussion_id: DISC-20260223-001852-walkthrough-phase5-search-memory-recall
started: 2026-02-23T00:21:22.300030+00:00
ended: 2026-02-23T00:21:22.300030+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260223-001852-walkthrough-phase5-search-memory-recall

## Turn 1 — educator (proposal)
*2026-02-23T00:21:22.300030+00:00 | confidence: 0.85*
*tags: walkthrough, education*

# Phase 5 Walkthrough: Search + Memory Recall

## High-Level Summary

Phase 5 adds **search and memory recall** to the journal app -- the ability for users to find past entries and ask natural-language questions about their journal history. This implements Layer C from ADR-0006, deferred from earlier phases.

**Core idea**: The app must distinguish between two kinds of user input:
1. **Journal entries** -- continuing the conversation (default behavior)
2. **Recall queries** -- searching past entries ("What did I write about last week?")

This is a fundamentally different UX flow than Phases 1-4. The architecture introduces a classification gate before message routing, a local search pipeline, and a recall pipeline that uses Claude to synthesize answers grounded in retrieved journal context.

**Key architectural decision**: The entire search feature works offline except for Claude synthesis. Intent classification is pattern-based (no LLM call), and keyword search runs locally via SQLite LIKE queries.

---

## Reading Path

### Stop 1: Data Models (lib/models/search_models.dart)
**Start here.** This file defines the vocabulary of Phase 5 -- every other file references these types.

**Key types:**
- `SearchFilters` -- Optional AND-combined filter criteria (date range, mood tags, people, topic tags). The `hasActiveFilters` getter drives UI decisions (e.g., "No results with filters" vs "No results").
- `MatchSource` enum -- `summary` or `message`. A result matched in the summary/metadata is ranked higher than one matched only in message content (per dedup rule in SearchRepository).
- `SearchResultItem` -- One matching session: the session record, snippets for preview, and how it matched.
- `SearchResults` -- The full result set with original query (needed for keyword bolding in UI).
- `RecallResponse` -- Separate from `AgentResponse` (ADR-0013 section 4). A recall answer is a grounded synthesis with cited session IDs, not a conversation turn. This is a deliberate type separation -- merging them would dilute both abstractions.

**Design decision to notice**: `RecallResponse.citedSessionIds` carries a doc comment about validating against the local DB before display -- this is the hallucination guard (Claude may return session IDs that do not exist locally).

---

### Stop 2: Intent Classifier (lib/services/intent_classifier.dart)
**The classification gate.** Every user message passes through this before routing.

**Architecture (ADR-0013 section 2):** Rule-based pattern matching, NOT an LLM call. This is a deliberate deviation from what you might expect -- adding an LLM call to classify every message would add latency, require connectivity, and over-engineer a problem solvable by patterns at personal journal scale.

**How classification works -- multi-signal scoring:**
The classifier does NOT fire on a single pattern match. It accumulates a score across four signal categories:

| Category | Score | Example |
|----------|-------|---------|
| Question words + past tense | +0.4 | "What did I write about...?" |
| Temporal references (only with question structure) | +0.3 | "When did I go to the gym last week?" |
| Recall verbs in query context | +0.35 | "Find entries about anxiety" |
| Meta-questions | +0.45 | "How often do I mention Sarah?" |

Scores are clamped to [0.0, 1.0] and compared against confidence tiers:
- >= 0.8: Auto-route to recall
- 0.5-0.8: Show inline confirmation ("Did you want to search?")
- < 0.5: Continue normal journaling

**Conservative default** is the critical design principle. Messages default to `journal` unless the classifier has high confidence. This prevents the app from suddenly switching into search mode mid-journaling, which would feel jarring.

**Subtle details to understand:**
1. **Short message filter** (lines 83-87): Messages of 4 words or fewer default to journal UNLESS they start with "find", "search", "look up", or "look for". This prevents "What?", "Really?", "Tell me more" from triggering recall.
2. **Temporal + question guard** (lines 100-109): "I talked to her last week" is narrative (journal), NOT a query. Temporal references only count as query signals when combined with question structure.
3. **Recall verb disambiguation** (lines 212-244): "I remember feeling happy" is journaling; "Do you remember when I..." is a query. The _isRecallAsQuery() method disambiguates by checking sentence structure.
4. **Search term extraction** (lines 250-272): Strips question scaffolding and stop words to isolate actual search content. If extraction produces nothing, falls back to the full trimmed message.

**i18n note** (line 17): All patterns are English-only. Non-English input silently defaults to journal (no error, no recall). This is a known limitation called out for future work.

---

### Stop 3: Search Repository (lib/repositories/search_repository.dart)
**The search orchestrator.** Combines session-level and message-level search results.

**Two search paths run in parallel** (lines 54-66):
1. `SessionDao.searchSessions()` -- matches against summary, mood tags, people, topic tags
2. `MessageDao.searchMessages()` -- matches against message content

**Dedup rule** (lines 68-97): If a session matches in BOTH summary and messages, it appears once with `MatchSource.summary` (summary match wins because it is a more specific signal -- the AI already distilled what was important).

**Ranking**: Summary matches first, then message-only matches. Within each group, sorted by date descending (newest first).

**Context formatting for recall** (`getSessionContext`, lines 139-184):
This method prepares structured context maps for the Claude recall API call. Key constraints from ADR-0013 section 5:
- Max 10 sessions per recall query
- Summaries truncated to 500 chars
- Max 5 message snippets per session at 300 chars each
- Only USER messages included (AI follow-up questions excluded to keep context signal-dense)

**Why USER messages only** (lines 165-166): The context sent to Claude should be the journaler's own voice and thoughts, not the AI's follow-up questions. This keeps recall grounded in what the user actually said.

---

### Stop 4: LIKE-Based Search with Escape (lib/database/search_query_utils.dart)
**Supporting the search layer.** This is not one of the six target files but is essential context.

**Why LIKE and not FTS5** (ADR-0013 section 1): Personal journal scale (hundreds to low thousands of messages) does not need full-text search. LIKE is simpler, works with drift's type-safe API, and avoids raw SQL setup complexity. FTS5 can be added later non-disruptively.

**The escape problem**: User search queries can contain `%` and `_`, which are LIKE wildcards. Without escaping, searching for "100% sure" would match everything (because `%` matches any string). The solution:
- `escapeLikeWildcards()` escapes `!`, `%`, and `_` with `!` prefix
- `LikeWithEscape` is a custom drift Expression that generates `column LIKE ? ESCAPE '!'`
- drift's built-in `like()` does NOT support the ESCAPE clause -- this custom expression was necessary

---

### Stop 5: Riverpod Providers (lib/providers/search_providers.dart)
**The wiring layer.** Connects models, services, and repositories to the UI.

**Provider inventory:**
- `searchRepositoryProvider` -- Depends on SessionDao and MessageDao
- `intentClassifierProvider` -- Stateless service, provider exists for testability (can override in tests)
- `searchQueryProvider` -- StateProvider holding current search text (debounced at UI layer)
- `searchFiltersProvider` -- StateProvider holding active SearchFilters
- `searchResultsProvider` -- FutureProvider that auto-evaluates when query or filters change (reactive chain)
- `recallAnswerProvider` -- FutureProvider.family keyed by question string. This is the recall pipeline entry point.
- `availableMoodTagsProvider`, `availablePeopleProvider`, `availableTopicTagsProvider` -- For populating filter chip options
- `sessionCountProvider` -- Drives progressive disclosure (search icon appears at 5+ sessions)

**The recall pipeline** (`recallAnswerProvider`, lines 70-91):
1. Search for relevant sessions using the question as query
2. If no results, return a "could not find" message (no Claude call)
3. Get formatted context for top results via `getSessionContext`
4. Call `claudeService.recall()` for synthesis

**Key design choice**: The recall provider depends on `claudeApiServiceProvider` -- this is where the offline boundary is. If Claude is unreachable, this provider errors, and the UI shows the offline fallback (local results as tappable chips).

---

### Stop 6: Search Screen (lib/ui/screens/search_screen.dart)
**The dedicated search UI.** A separate screen (not a persistent search bar) because search is secondary to journaling.

**Three distinct empty states** (lines 147-237):
1. **Pre-search**: "Search your journal" with search icon -- user has not typed anything yet
2. **No results + filters active**: "No entries match your filters" with "Clear filters" button
3. **No results, no filters**: "No entries found" -- try different keywords

These are distinct because each needs different guidance text. Collapsing them would confuse users ("Should I change my keywords or my filters?").

**Search debounce** (lines 43, 52-57): 300ms debounce via Timer. The provider is not updated on every keystroke -- only after 300ms of no typing. This prevents rapid-fire SQLite queries.

**Offline indicator** (lines 102-126): A non-blocking banner that says "Searching local data - Natural language recall unavailable offline". Not an error modal -- ambient degradation per ADR-0013 section 7.

**Filter chips** (_FilterChipRow, lines 261-543): Horizontal scrollable row with date, mood, people, and topics. Date filter offers presets (Last 7 days, Last 30 days, This year) plus custom range. Mood/people/topics use multi-select bottom sheets populated by the available*Provider providers.

---

### Stop 7: Search Result Card (lib/ui/widgets/search_result_card.dart)
**The result display widget.**

**Key features:**
- **Match source label** (lines 108-128): Shows "Summary" or "Conversation" so the user knows where the match was found.
- **Keyword bolding** (_BoldedSnippet, lines 134-200): Case-insensitive find-and-bold of the search query within the snippet text. Uses RichText with TextSpan children -- each match segment gets FontWeight.bold.
- **Metadata chips** (_MetadataChips, lines 204-246): Shows up to 2 mood, 2 people, and 2 topic chips. Parses JSON array strings from the session record.
- **JSON parsing guard** (lines 234-245): Uses try/on FormatException when parsing metadata JSON. Gracefully returns empty list on invalid JSON rather than crashing.

**Unicode awareness** (line 188 comment): The bolding logic notes that toLowerCase() can change string length for certain Unicode characters. It uses lowerQuery.length for the match span calculation.

---

## Recall Pipeline End-to-End

The full recall flow, connecting all pieces:

1. User types "What did I write about anxiety last week?" in the chat
2. **IntentClassifier.classify()** scores: question+past (+0.4) + temporal+question (+0.3) = 0.7 -> IntentType.query with ambiguous confidence -> show confirmation prompt
3. User confirms they want to search
4. **SearchRepository.searchEntries()** runs parallel LIKE queries against sessions and messages
5. Results deduplicated (summary matches win), ranked by relevance
6. **SearchRepository.getSessionContext()** formats top 10 sessions as structured maps (USER messages only, truncated)
7. **ClaudeApiService.recall()** sends question + context to Edge Function with prompt injection mitigations (structural delimiters, data-not-instruction framing)
8. Claude returns answer + cited session IDs
9. **Citation validation**: citedSessionIds verified against local DB before navigation (hallucination guard)
10. Answer displayed with tappable session citations

**Offline fallback** (at step 6): If Claude is unreachable, steps 4-5 still work (local search). The UI shows matching sessions as tappable cards instead of a synthesized answer.

---

## Key ADR Connections

- **ADR-0013**: The governing ADR for all Phase 5 decisions. Every file header references it.
- **ADR-0006**: The original three-layer agent design. Phase 5 implements Layer C (deferred in ADR-0006).
- **ADR-0005**: Claude API proxy via Supabase Edge Functions -- recall uses the same proxy pattern with a new "recall" mode.

---

## Things That Might Surprise You

1. **Intent classification is NOT an LLM call.** It is pure regex pattern matching. This is deliberate (latency, offline-first, cost).
2. **RecallResponse is a separate type from AgentResponse.** They look similar but model different things (grounded answer vs conversation turn).
3. **Only USER messages go into recall context.** AI follow-up questions are excluded to keep context signal-dense.
4. **The search screen is hidden until 5+ sessions.** Progressive disclosure -- new users do not need search yet.
5. **LIKE escape required a custom drift Expression.** drift's built-in like() does not support the ESCAPE clause.
6. **Metadata tag filters use substring LIKE matching on JSON strings.** A filter for "happ" would match "happy". Acceptable at personal scale, noted as a known limitation.

---
