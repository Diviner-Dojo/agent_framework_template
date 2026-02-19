---
last_updated: "2026-02-18"
total_analyses: 0
patterns_evaluated: 0
patterns_adopted: 0
patterns_deferred: 0
patterns_rejected: 0
---

# Adoption Log (Learning Ledger)

This file tracks patterns discovered across external project analyses (`/analyze-project`). It serves as the template's learning memory — accumulating evidence across multiple reviews to identify which patterns are worth adopting.

## How This Works

1. Each `/analyze-project` run evaluates an external project and scores its patterns
2. Patterns scoring >= 20/25 are recommended for adoption
3. Patterns scoring 15-19 are deferred — tracked here for future consideration
4. Patterns scoring < 15 are rejected but noted briefly
5. **Rule of Three**: When a pattern is seen in 3+ independent projects, it gets +2 bonus to its score. Three sightings confirm a pattern is real, not coincidental.

## How to Read Entries

Each entry records:
- **Pattern name** and description
- **Source**: Which project(s) it was seen in
- **Score**: 5-dimension score (prevalence, elegance, evidence, fit, maintenance) out of 25
- **Sightings**: How many independent projects exhibit this pattern
- **Status**: ADOPTED / DEFERRED / REJECTED
- **Location**: Where it was placed in our project (if adopted)

## Pattern Log

*Entries are added by `/analyze-project` as patterns are evaluated.*
*Most recent entries appear at the top.*

<!-- Example entry format:

### Pattern: [Name]
- **First seen**: [project name/url] (YYYY-MM-DD)
- **Also seen in**: [project2], [project3]
- **Sightings**: N
- **Score**: XX/25 (prevalence:X, elegance:X, evidence:X, fit:X, maintenance:X)
- **Status**: ADOPTED / DEFERRED / REJECTED
- **Location**: [where in our project, if adopted]
- **Decision**: [reasoning for the status]

-->
