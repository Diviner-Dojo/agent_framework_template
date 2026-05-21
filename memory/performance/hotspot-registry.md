---
name: Performance Hotspot Registry
type: standing-document
specialist: performance-analyst
updated: "[update after each review that identifies performance concerns]"
---

# Performance Hotspot Registry

Standing document for the performance-analyst. Consult before every review dispatch.

## Known Hotspots

<!-- Track performance-sensitive areas identified during reviews.
Format:
| Location | Nature | Review Source | Accepted Trade-off? |
|----------|--------|---------------|---------------------|
| src/routes/search.py | N+1 query risk | REV-20260401-... | Yes — acceptable at current scale |
-->

*No hotspots identified yet. Add entries as reviews flag performance concerns.*

## Accepted Trade-offs

<!-- Performance trade-offs that were explicitly accepted and should not be re-flagged.
Format:
### [Trade-off Title]
- **Location**: file:line
- **Trade-off**: What was sacrificed for what benefit
- **Threshold**: When this should be revisited (e.g., ">1000 records", ">100 concurrent users")
- **Accepted by**: [developer] on [date]
-->

*No accepted trade-offs yet.*

## Performance Patterns to Watch

<!-- Project-specific patterns that tend to cause performance issues.
These are learned from past reviews and should be checked proactively.
-->

- SQLite write contention under concurrent access
- Large JSONL file reads during capture pipeline operations
- Discussion directory scanning during knowledge-health checks
