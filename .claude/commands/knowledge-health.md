---
description: "Run a knowledge pipeline health check. Reports on all 5 pipeline layers: discussions, relational index, findings, patterns, and curated memory."
allowed-tools: ["Read", "Bash", "Glob", "Grep"]
---

# Knowledge Pipeline Health Check

Run the knowledge dashboard to assess the health of the framework's knowledge pipeline.

## Step 1: Run Dashboard

```bash
python scripts/knowledge_dashboard.py
```

## Step 2: Run Supplementary Checks

### Forgetting Curve Status

Check for stale memory items:

```bash
python scripts/enforce_forgetting_curve.py --dry-run
```

### Promotion Candidates

Check for patterns ready for promotion:

```bash
python scripts/surface_candidates.py
```

### Agent Effectiveness

Compute effectiveness for any unprocessed discussions:

```bash
python scripts/compute_agent_effectiveness.py --all
```

### Adoption Log Unification

Merge adoption-log patterns with discussion-derived patterns:

```bash
python scripts/unify_sightings.py
```

## Step 3: Present Results

Present a summary to the developer:

1. **Pipeline Health**: Layer-by-layer status from the dashboard
2. **Stale Memory**: Files flagged for review or auto-archive
3. **Promotion Candidates**: Patterns qualifying for Rule of Three promotion
4. **Agent Calibration**: Which agents contribute unique findings vs. noise
5. **Recommendations**: Suggested actions (run `/retro`, promote patterns, archive stale memory, run `/batch-evaluate`)

## Step 4: Offer Actions

Based on the findings, offer the developer relevant next steps:
- "Run `/retro` to do a full retrospective"
- "Run `/promote` to promote a pattern to curated memory"
- "Run `python scripts/enforce_forgetting_curve.py` to archive stale items"
- "Run `/batch-evaluate` to clear pending adoption evaluations"
