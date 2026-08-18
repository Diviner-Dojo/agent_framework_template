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

### Protocol Yield Coverage

Report which protocols are actually being measured, and how honestly:

```bash
python scripts/efficiency_report.py --coverage-only
```

Exit 0 = rendered; exit 1 = the database is absent or unreadable (a broken instrument —
the output says `BROKEN INSTRUMENT`; report it as such, not as an absence of data, and draw
no conclusion about any protocol's value from that run); exit 2 = a malformed `--since`.

**Reading the output — the distinction this check exists to preserve:**

- `-` in a yield cell = **NEVER MEASURED**. No `protocol_yield` row exists for that bucket.
- `0` in a yield cell = **MEASURED AND CAUGHT NOTHING**. A protocol ran and recorded zero.

> **THE ANTI-DELETION GUARD.** A gate with no recorded yield may be worthless, or may simply
> never have been measured — **those look identical and are not the same. Never propose
> deleting a gate on absence of evidence.** If a protocol shows `NEVER MEASURED`, the only
> honest recommendation is to instrument it (wire in `scripts/record_yield.py`) and re-assess
> once it has data. Unmeasured is a defect in the instrument, not a verdict on the gate.
> Deleting the measurement deletes the ability to ever answer "was that right?".

If the `Recording integrity` block prints an `HONESTY WARNING`, the false-positive rate is
implausibly low. That means false positives are not being recorded — not that the panel is
nearly perfect. Report it as a **pipeline health defect**: a flattering number here silently
corrupts every downstream precision, calibration, and yield metric that reads this table.

### Calibration Drift Audit (ADVISORY — NEVER A GATE)

```bash
python scripts/audit_calibration.py --report-only
```

Exits 0 whenever the audit ran, however many proposals it emits. Exit 1 means the audit
itself failed to run — database absent or unreadable — never that calibration drifted; the
report prints `BROKEN INSTRUMENT`. A failed audit is not a clean bill of health: on exit 1
report the instrument as broken and record no calibration conclusion. **Never treat this as
a gate on its findings.**

`--report-only` suppresses the proposal **queue** artifact, not the run log: every
invocation appends one line to `metrics/calibration_log.jsonl` (including zero-proposal
runs), so "audited, no drift" stays distinguishable from "never audited".

> **THE ADR-0024 HUMAN GATE IS ABSOLUTE.** These proposals are `status: pending`
> **communication artifacts, not instruction files.** The agent must **NEVER** edit a
> classifier surface off its own proposal — not `scripts/extract_findings.py`, not
> `.claude/skills/severity-calibration/SKILL.md`. That is **self-modification**: the system
> tuning the instrument that grades it (Principle #6, curated memory needs human approval;
> the human-mediated Prime Objective).
> Surface the proposals to the developer and stop. A human applies them, or nobody does.

## Step 3: Present Results

Present a summary to the developer:

1. **Pipeline Health**: Layer-by-layer status from the dashboard
2. **Stale Memory**: Files flagged for review or auto-archive
3. **Promotion Candidates**: Patterns qualifying for Rule of Three promotion
4. **Agent Calibration**: Which agents contribute unique findings vs. noise
5. **Yield Coverage**: Which protocols are measured, which are `NEVER MEASURED`, and the
   recorded false-positive rate. State unmeasured protocols as *uninstrumented* — never as
   low-value — and recommend instrumenting them, never relaxing or removing them.
6. **Calibration Proposals**: Any drift proposals, each marked `pending developer decision`.
   Never applied by the agent.
7. **Recommendations**: Suggested actions (run `/retro`, promote patterns, archive stale memory, run `/batch-evaluate`)

## Step 4: Offer Actions

Based on the findings, offer the developer relevant next steps:
- "Run `/retro` to do a full retrospective"
- "Run `/promote` to promote a pattern to curated memory"
- "Run `python scripts/enforce_forgetting_curve.py` to archive stale items"
- "Run `/batch-evaluate` to clear pending adoption evaluations"
