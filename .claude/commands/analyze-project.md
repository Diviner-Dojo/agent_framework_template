---
description: "Analyze an external project to discover patterns worth adopting. Dispatches the project-analyst as scout, then runs all core specialists in a round-robin evaluation. Produces a scored recommendation report."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[local path, GitHub owner/repo, or GitHub URL]"
---

# External Project Analysis (Round-Robin Review)

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

## Step 3: Scout Phase (Project Analyst)

Dispatch the project-analyst to survey the target:

```
Task(subagent_type="project-analyst", prompt="Survey this project at <target-path>.
  Produce a complete project profile: directory structure, tech stack, dependencies,
  LOC estimate, maturity signals, AI integration artifacts, key files for specialist
  review, and initial pattern inventory.

  Be thorough but skeptical. Only flag patterns that are genuinely notable —
  not just 'different from ours.' Default assumption: this project's patterns
  are context-specific and not worth generalizing.

  Our project: [brief description of our project's tech stack and purpose]
  Our project path: [path to our project root]")
```

Capture the scout findings:
```bash
python scripts/write_event.py "<discussion_id>" "project-analyst" "proposal" "<scout findings>" --confidence <score>
```

Read the scout's output. If the scout says "No specialist review recommended," skip to Step 6 with a short report.

## Step 4: Round-Robin Specialist Review

Using the project profile and key files from Step 3, dispatch each core specialist to evaluate the external project from their perspective. **Run all specialists in parallel.**

For each specialist, provide:
1. The project profile from the scout
2. The key files the scout identified as relevant to that specialist
3. A reminder to be critical and compare against what our project already does

### Specialists to dispatch:

**architecture-consultant:**
```
Task(subagent_type="architecture-consultant", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Key files to examine:
<paste relevant key files from scout>

Evaluate this external project's architectural patterns. Compare against our project's
architecture. What patterns does this project use that could genuinely improve ours?
What patterns should we actively avoid?

Be critical. Most projects won't have architectural innovations worth importing.
If nothing stands out, say so clearly.")
```

**security-specialist:**
```
Task(subagent_type="security-specialist", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Evaluate this project's security patterns. Is there anything here that would strengthen
our project's security posture? Check: auth patterns, input validation, secret management,
CORS, dependency security. Most projects won't — say so if that's the case.")
```

**qa-specialist:**
```
Task(subagent_type="qa-specialist", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Evaluate this project's testing strategy. Are there testing patterns, fixture approaches,
coverage strategies, or test infrastructure that would improve our test suite?
Be specific about what's better and why.")
```

**performance-analyst:**
```
Task(subagent_type="performance-analyst", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Evaluate this project's performance patterns. Any caching, concurrency, connection pooling,
or optimization approaches worth adopting? Skip with 'nothing notable' if nothing stands out.")
```

**docs-knowledge:**
```
Task(subagent_type="docs-knowledge", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Evaluate this project's documentation approach. ADRs, API docs, README quality, onboarding
experience, inline documentation — anything we should learn from?")
```

**independent-perspective:**
```
Task(subagent_type="independent-perspective", prompt="External Project Analysis: <discussion_id>

Project Profile:
<paste scout's project profile>

Look at this project with completely fresh eyes. What's the most surprising or unconventional
thing about it? What would everyone else miss? Is there a hidden risk in adopting anything
from this project? What's the 'pre-mortem' — if we adopt a pattern from here, what goes wrong?")
```

Capture each specialist's findings:
```bash
python scripts/write_event.py "<discussion_id>" "<agent-name>" "proposal" "<findings>" --confidence <score>
```

## Step 5: Scoring Round

Collect all patterns recommended by any specialist. For each pattern, score using this rubric:

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

## Step 6: Synthesis & Report

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

## Step 7: Present to Developer

Present the findings:

1. **Project Profile** — Quick summary of what we reviewed
2. **Recommended Adoptions** (≥ 20/25) — What to import, where it goes, why it scored high
3. **Deferred Patterns** (15–19) — What's interesting but not ready, what would change our mind
4. **Rejected Patterns** (< 15) — Brief note on what was considered and why it was dropped
5. **Anti-Patterns** — What this project does that we should actively avoid
6. **Specialist consensus** — Did agents agree or disagree? Any surprising dissent?

**Wait for developer approval before making any changes to our project.**

## Step 8: Execute Approved Adoptions

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

## Step 9: Close Discussion + Cleanup

```bash
python scripts/close_discussion.py "<discussion_id>"
```

If the target was a GitHub clone, remove the temporary directory:
```bash
rm -rf /tmp/analyze-<slug>
```

Report the analysis report location to the developer.
