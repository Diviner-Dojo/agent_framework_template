---
description: "Analyze an external project to discover patterns worth adopting. Dispatches the project-analyst to scout the territory and orchestrate a multi-specialist co-review of applicability. Produces a scored recommendation report."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[local path, GitHub owner/repo, or GitHub URL]"
---

# External Project Analysis (Co-Review)

You are acting as the Facilitator. This command points your specialist team outward — at an external project — to evaluate whether it contains patterns that would improve our project.

**Default stance: skeptical.** Most external projects won't have anything worth importing. That's fine. The value is in systematic evaluation, not in finding things to adopt.

## Step 1: Resolve the Target

Accept one of:
- A local filesystem path (e.g., `C:\Work\Projects\SomeProject`)
- A GitHub `owner/repo` slug (e.g., `tiangolo/fastapi`)
- A full GitHub URL (e.g., `https://github.com/tiangolo/fastapi`)

**If GitHub:**
```bash
gh repo view <owner/repo> --json stargazerCount,description,repositoryTopics,primaryLanguage,updatedAt,licenseInfo
```
Display the project summary to the developer: name, stars, language, description, last updated.

Then shallow clone:
```bash
gh repo clone <owner/repo> /tmp/analyze-<slug> -- --depth=1
```
Use the cloned path as the target for all subsequent steps.

**If local path:**
Verify the path exists. Read in-place — never modify the target.

## Step 2: Create Discussion

```bash
python scripts/create_discussion.py "analyze-<slug>" --risk low --mode structured-dialogue
```

Record the discussion_id for all subsequent capture steps.

## Step 3: Dispatch the Project Analyst

The project-analyst serves as both scout and orchestrator. It surveys the target project, then dispatches the relevant specialist agents for a co-review of applicability to our current effort.

Dispatch the project-analyst with full context:

```
Task(subagent_type="project-analyst", prompt="Analyze this external project for applicability to our current effort.

Target project path: <target-path>
Our project path: <path to our project root>
Our project: <brief description of our project's tech stack, purpose, and current state>

Phase 1 — Survey the target project. Produce a complete project profile: directory structure, tech stack, dependencies, LOC estimate, maturity signals, AI integration artifacts, key files, and initial pattern inventory.

Phase 2 — If notable patterns exist, orchestrate a multi-specialist co-review. Dispatch the relevant specialists (architecture-consultant, security-specialist, qa-specialist, performance-analyst, docs-knowledge, independent-perspective) to evaluate the project from their respective domains. Only dispatch specialists whose domain intersects with what you found. Run them in parallel.

After collecting all specialist perspectives, produce a unified applicability assessment: convergence map, points of dissent, blind spots, and an applicability verdict for each pattern.

Be thorough but skeptical. Only recommend patterns that are genuinely applicable to our current effort — not just interesting in the abstract. Default assumption: this project's patterns are context-specific and not worth generalizing.")
```

Capture the full findings (scout report + co-review synthesis):
```bash
python scripts/write_event.py "<discussion_id>" "project-analyst" "proposal" "<scout findings + co-review synthesis>" --confidence <score>
```

Also capture each specialist's perspective referenced in the synthesis:
```bash
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<specialist findings>" --confidence <score>
```

If the project-analyst says "No specialist review recommended" or "No further review recommended," skip to Step 5 with a short report.

## Step 4: Scoring Round

Collect all patterns recommended by any specialist or identified in the co-review synthesis. For each pattern, score using this rubric:

| Dimension | Question | 1 (low) | 5 (high) |
|-----------|----------|---------|----------|
| **Problem prevalence** | How common is the problem this solves? | Edge case / niche | Every project faces this |
| **Solution elegance** | Is this minimal and clear? | Over-engineered | Minimal and clear |
| **Adoption evidence** | How widely adopted is this approach? | Seen in 1 project | Industry standard |
| **Template fit** | How easily does it fit our project? | Heavy customization needed | Drops right in |
| **Maintenance burden** | What's the ongoing cost? | Constant attention | Set and forget |

**Thresholds:**
- **≥ 20/25**: Recommend for adoption
- **15–19**: Note for future (deferred — track in adoption log)
- **< 15**: Skip (briefly note why)

Check `memory/lessons/adoption-log.md` — if we've seen this pattern in previous analyses, note the cumulative sighting count. Patterns with 3+ sightings get +2 bonus to their score (Rule of Three).

Where specialists disagreed (points of dissent from the co-review), note the disagreement in the scoring rationale. Dissent doesn't lower the score automatically — but unresolved dissent caps confidence.

## Step 5: Synthesis & Report

Write the facilitator synthesis event:
```bash
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "<synthesis>" --confidence <score>
```

Generate a timestamp:
```bash
python -c "from datetime import datetime, timezone; print(datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))"
```

Create the analysis report following `docs/templates/project-analysis-template.md`:
```
docs/reviews/ANALYSIS-YYYYMMDD-HHMMSS-<slug>.md
```

## Step 6: Present to Developer

Present the findings:

1. **Project Profile** — Quick summary of what we reviewed
2. **Specialist Team** — Who reviewed and what they focused on
3. **Recommended Adoptions** (≥ 20/25) — What to import, where it goes, why it scored high
4. **Points of Dissent** — Where the team disagreed and why that matters
5. **Deferred Patterns** (15–19) — What's interesting but not ready, what would change our mind
6. **Rejected Patterns** (< 15) — Brief note on what was considered and why it was dropped
7. **Anti-Patterns** — What this project does that we should actively avoid
8. **Specialist Consensus Summary** — Did agents agree or disagree? Any surprising dissent?

**Wait for developer approval before making any changes to our project.**

## Step 7: Execute Approved Adoptions

For each pattern the developer approves:

1. Implement the change in our project:
   - New agent → `.claude/agents/` (or `agents/specialty/` if it exists)
   - New skill → `.claude/skills/`
   - New rule → `.claude/rules/`
   - Code pattern → apply to relevant source files
   - Documentation → update relevant docs

2. Update `memory/lessons/adoption-log.md`:
   ```
   ### Pattern: <name>
   - **Source**: <project name/url>
   - **Analysis**: ANALYSIS-YYYYMMDD-HHMMSS-<slug>
   - **Score**: XX/25 (prevalence:X, elegance:X, evidence:X, fit:X, maintenance:X)
   - **Sightings**: N (list of projects where seen)
   - **Status**: ADOPTED
   - **Location**: <where it was placed in our project>
   - **Date**: YYYY-MM-DD
   ```

For patterns that were deferred or rejected, also log them:
   ```
   ### Pattern: <name>
   - **Source**: <project name/url>
   - **Score**: XX/25
   - **Sightings**: N
   - **Status**: DEFERRED / REJECTED
   - **Reason**: <why>
   - **Revisit if**: <what would change the decision>
   ```

## Step 8: Close Discussion + Cleanup

```bash
python scripts/close_discussion.py "<discussion_id>"
```

If the target was a GitHub clone, remove the temporary directory:
```bash
rm -rf /tmp/analyze-<slug>
```

Report the analysis report location to the developer.
