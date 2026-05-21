---
name: searching-prior-art
description: Grep-before-you-build checklist for finding existing solution paths, known-broken approaches, ADRs, and promoted patterns before implementing. Use during /plan (prior-art lookup) and /build_module (pre-build enrichment), or whenever deciding how to implement something new.
---

# Pre-Build Search: Grep Before You Build

> Before building something new, check if a solution path already exists in the knowledge base.
> This prevents reinventing approaches that have already been tried, validated, or rejected.

## When This Rule Activates

Before implementing any non-trivial feature, module, or integration:
- During `/plan` (Step 1.5: Prior Art Lookup)
- During `/build_module` (Step 2.5: Pre-Build Enrichment)
- When a developer asks "how should we implement X?"

## What to Search

Search these locations in order:

### 1. Solution Paths (memory/projects/)
```bash
grep -ri "<domain keyword>" memory/projects/
```
Look for `## Solution Paths` sections in project profiles. These document HOW projects solved specific problems — what was tried, what failed, and why the chosen approach won.

### 2. Known-Broken Approaches (memory/bugs/regression-ledger.md)
```bash
grep -i "<approach keyword>" memory/bugs/regression-ledger.md
```
Check the `## Known-Broken Approaches` section. If an approach has been tried and found broken, don't repeat the mistake.

### 3. ADRs (docs/adr/)
```bash
grep -ri "<concept>" docs/adr/
```
Check if an architectural decision already covers this problem space.

### 4. Existing Patterns (memory/patterns/)
```bash
grep -ri "<pattern keyword>" memory/patterns/
```
Check if a promoted pattern addresses this need.

## How to Use Results

- **Solution path found**: Reference it in your plan or build. Explain why you're following or diverging from the documented path.
- **Known-broken approach found**: Do not use that approach. Document why you're using an alternative.
- **No results found**: Proceed normally. After implementation, capture the solution path via the commit protocol (Step 3.5).

## What This Rule Does NOT Do

- It does not block builds if no prior art is found — absence of prior art is normal for novel work.
- It does not require exhaustive search — a quick grep is sufficient. If the first 2-3 searches yield nothing, move on.
- It does not replace architectural review — prior art informs decisions, it doesn't make them.
