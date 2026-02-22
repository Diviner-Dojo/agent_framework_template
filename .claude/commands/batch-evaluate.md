---
description: "Batch evaluate PENDING pattern adoptions from the adoption log. Reviews evidence, checks artifact existence, and presents verdicts for developer approval."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
---

# Batch Evaluate PENDING Adoptions

You are acting as the Facilitator evaluating PENDING pattern adoptions from the adoption log.

## Purpose

Process stale PENDING patterns from `memory/lessons/adoption-log.md` and present batch verdicts for developer approval. Expected cadence: quarterly at meta-review, or when `/retro` flags stale-pending > 5.

## Step 1: Read Adoption Log

Read `memory/lessons/adoption-log.md` and extract all patterns with `Status: PENDING`.

For each PENDING pattern, note:
- Pattern name and description
- Source analysis (which `/analyze-project` run)
- Adoption date
- Location field (where the artifact should be)
- Age in days since adoption

## Step 2: Check Artifact Existence

For each PENDING pattern, check if the artifact at the `Location` field actually exists:

```bash
# For each pattern's Location, check file existence
ls -la <location_path>
```

If the location references a concept rather than a specific file (e.g., "Riverpod providers"), search for evidence:

```bash
# Search for pattern usage in codebase
```

Use Grep/Glob to find evidence of the pattern being used.

## Step 3: Search for Usage Evidence

For each PENDING pattern, search for evidence in:
1. **Discussion transcripts**: Has the pattern been mentioned in reviews, retros, or builds?
2. **Retro findings**: Has a retro confirmed or questioned this pattern?
3. **Code usage**: Is the pattern actually being exercised in production code?

```bash
python -c "
import sqlite3
conn = sqlite3.connect('metrics/evaluation.db')
# Search for pattern mentions in turns
for row in conn.execute('''
    SELECT t.discussion_id, t.agent, t.intent, t.timestamp
    FROM turns t
    WHERE t.content_hash LIKE ?
    ORDER BY t.timestamp DESC LIMIT 10
''', ('%PATTERN_NAME%',)):
    print(row)
conn.close()
"
```

Also search discussion transcripts directly using Grep.

## Step 4: Classify Patterns

Group each PENDING pattern into one of three categories:

### CONFIRMED-ready
- Artifact exists at the declared location
- Evidence of usage in at least one discussion, retro, or code path
- No contradicting evidence (no revert signals)

### REVERTED-ready
- Artifact has been deleted or never created
- Tech stack has changed making the pattern irrelevant
- A retro or review explicitly questioned or rejected the pattern
- The pattern was superseded by an ADR or alternative approach

### Needs-more-data
- Artifact exists but no usage evidence found
- Pattern is too new to evaluate (< 14 days)
- Mixed signals — some evidence for, some against

## Step 5: Present Batch Assessment

Present the assessment to the developer in this format:

```markdown
## Batch Evaluation: PENDING Adoptions

**Total PENDING**: N
**Evaluated**: M
**Stale (>14 days)**: K

### CONFIRMED-ready (recommend → CONFIRMED)
| Pattern | Source | Age (days) | Evidence |
|---------|--------|-----------|----------|
| ... | ... | ... | ... |

### REVERTED-ready (recommend → REVERTED)
| Pattern | Source | Age (days) | Reason |
|---------|--------|-----------|--------|
| ... | ... | ... | ... |

### Needs More Data (no change)
| Pattern | Source | Age (days) | Status |
|---------|--------|-----------|--------|
| ... | ... | ... | ... |
```

**IMPORTANT**: Do NOT update the adoption log automatically. Present the assessment and wait for the developer to approve each verdict (Principle #7 — human decides).

## Step 6: Update Adoption Log

After receiving developer approval:
1. For each approved CONFIRMED verdict: change `Status: PENDING` → `Status: CONFIRMED` and add `Evidence: <summary>`
2. For each approved REVERTED verdict: change `Status: PENDING` → `Status: REVERTED` and add `Reason: <summary>`
3. Leave needs-more-data patterns unchanged
4. Add a dated note at the bottom: `Batch evaluation: YYYY-MM-DD — N confirmed, M reverted, K deferred`
