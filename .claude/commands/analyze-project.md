---
description: "Analyze an external project to discover patterns worth adopting. Dispatches the project-analyst to scout the territory and orchestrate a multi-specialist co-review of applicability. Produces a scored recommendation report."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "[local path, GitHub owner/repo, or GitHub URL]"
---

# External Project Analysis (Co-Review)

You are acting as the Facilitator. This command points your specialist team outward — at an external project — to evaluate whether it contains patterns that would improve our project.

**Default stance: skeptical.** Most external projects won't have anything worth importing. That's fine. The value is in systematic evaluation, not in finding things to adopt.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER modify the target project**: Read-only access to the external project. No writes, no edits, no file creation in the target.
2. **NEVER skip the adoption log check**: Before scoring, ALWAYS read `memory/lessons/adoption-log.md` and check for prior sightings. Rule of Three applies.
3. **NEVER continue on failure**: If any step fails, HALT immediately. Present the error and ask the user how to proceed. Do NOT silently continue.
4. **ALWAYS capture all specialist events**: Every specialist finding MUST be recorded via `scripts/write_event.py`. Uncaptured analysis is lost analysis.
5. **ALWAYS wait for developer approval**: NEVER modify our project files based on analysis results without explicit developer approval.
6. **ALWAYS clean up**: If the target was a GitHub clone, remove the temporary directory after analysis completes.

## Pre-Flight Checks

Before starting the analysis, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
for d in ['discussions', 'docs/reviews', 'docs/templates', 'memory/lessons']:
    if not pathlib.Path(d).exists():
        errors.append(f'Missing required directory: {d}')
if not pathlib.Path('memory/lessons/adoption-log.md').exists():
    errors.append('Missing adoption log: memory/lessons/adoption-log.md')
if not pathlib.Path('docs/templates/project-analysis-template.md').exists():
    errors.append('Missing analysis template: docs/templates/project-analysis-template.md')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and suggest running `/onboard` to set up the framework structure.

## Session Resumption Check

Before creating a new discussion, check for an in-progress analysis:

```bash
python -c "
import pathlib, json
for d in sorted(pathlib.Path('discussions').glob('*/*/state.json'), reverse=True):
    state = json.loads(d.read_text())
    if state.get('command') == 'analyze-project' and state.get('status') == 'in_progress':
        print(f'FOUND IN-PROGRESS ANALYSIS: {state[\"discussion_id\"]} (phase: {state.get(\"current_phase\", \"unknown\")})')
        print(f'  Target: {state.get(\"target\", \"unknown\")}')
        print(f'  Path: {d.parent}')
        break
else:
    print('No in-progress analysis sessions found.')
"
```

If an in-progress session is found, ask the developer: **Resume the previous session or start fresh?** If resuming, read phase output files from the discussion directory to restore context.

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

## Step 1b: License Check

Before investing time in full analysis, check the target project's license status. Unlicensed projects default to full copyright — adopting code from them carries legal risk.

**If GitHub:**
The `licenseInfo` field from Step 1's `gh repo view` provides the license. Evaluate it:

```bash
gh api "repos/<owner>/<repo>/license" --jq '.license.spdx_id // "NONE"' 2>/dev/null || echo "NONE"
```

**If local path:**
```bash
python -c "
import pathlib
target = pathlib.Path('<target-path>')
license_files = list(target.glob('LICENSE*')) + list(target.glob('LICENCE*')) + list(target.glob('COPYING*'))
if license_files:
    content = license_files[0].read_text(errors='replace')[:500]
    print(f'LICENSE FILE FOUND: {license_files[0].name}')
    print(content[:500])
else:
    # Check pyproject.toml, package.json, setup.cfg for license metadata
    for meta in ['pyproject.toml', 'package.json', 'setup.cfg', 'Cargo.toml']:
        meta_path = target / meta
        if meta_path.exists():
            text = meta_path.read_text(errors='replace')
            import re
            match = re.search(r'license\s*[=:]\s*[\"'\''](.*?)[\"'\'']', text, re.IGNORECASE)
            if match:
                print(f'LICENSE IN METADATA ({meta}): {match.group(1)}')
                break
    else:
        print('NO LICENSE FOUND')
"
```

**Classify the result and present to the developer:**

| License Category | Examples | Risk Level | Action |
|-----------------|----------|------------|--------|
| **Permissive** | MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC, Unlicense | Low | Proceed. Note attribution requirements in analysis report. |
| **Copyleft** | GPL-2.0, GPL-3.0, AGPL-3.0, LGPL, MPL-2.0 | Medium | Warn developer: adopting code (not just ideas) may impose license obligations on this project. Proceed with analysis but flag in report. |
| **No license** | NOASSERTION, NONE, no file found | High | **HALT and warn the developer**: "This project has no license. Under copyright law, no license means all rights reserved. Analyzing for architectural *ideas* is fine, but adopting any code carries legal risk. Proceed with analysis? If yes, the report will flag all recommendations as ideas-only." |
| **Unknown/custom** | Custom text, unclear terms | Medium | Present the license text to the developer and ask how to proceed. |

Record the license status — it will be included in the analysis report frontmatter and affects how recommendations are framed in Step 5.

If the developer chooses not to proceed, skip to cleanup (remove any cloned repo) and exit.

## Step 2: Create Discussion

```bash
python scripts/create_discussion.py "analyze-<slug>" --risk low --mode structured-dialogue
```

Record the discussion_id for all subsequent capture steps.

Initialize the workflow state file:

```bash
python -c "
import json, pathlib
from datetime import datetime, timezone
state = {
    'command': 'analyze-project',
    'discussion_id': '<discussion_id>',
    'status': 'in_progress',
    'started_at': datetime.now(timezone.utc).isoformat(),
    'current_phase': 'project_analyst_dispatch',
    'completed_phases': ['target_resolved', 'discussion_created'],
    'target': '<target path or URL>'
}
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state_path.write_text(json.dumps(state, indent=2))
print(f'State initialized: {state_path}')
"
```

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

Create the analysis report following `docs/templates/project-analysis-template.md`. Include the `target_license` and `license_risk` fields in the frontmatter. Populate the License section of the report.

**License framing for recommendations:**
- **No license (high risk)**: Prefix each recommendation with "**Ideas-only**:" and note that implementations must be independently authored. Do not recommend direct code adaptation.
- **Copyleft (medium risk)**: Note the specific license obligations in each recommendation. Flag if adopting code would impose obligations on this project.
- **Permissive (low risk)**: Note attribution requirements (e.g., "include MIT notice if code is adapted").
- **Own project**: No license constraints.

```
docs/reviews/ANALYSIS-YYYYMMDD-HHMMSS-<slug>.md
```

## Step 6: Present to Developer

Present the findings:

1. **Project Profile** — Quick summary of what we reviewed
2. **License** — License type, risk level, and adoption constraints. If high-risk (no license), remind the developer that recommendations are ideas-only.
3. **Specialist Team** — Who reviewed and what they focused on
4. **Recommended Adoptions** (≥ 20/25) — What to import, where it goes, why it scored high
5. **Points of Dissent** — Where the team disagreed and why that matters
6. **Deferred Patterns** (15–19) — What's interesting but not ready, what would change our mind
7. **Rejected Patterns** (< 15) — Brief note on what was considered and why it was dropped
8. **Anti-Patterns** — What this project does that we should actively avoid
9. **Specialist Consensus Summary** — Did agents agree or disagree? Any surprising dissent?

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

Update the workflow state:
```bash
python -c "
import json, pathlib
state_path = pathlib.Path('discussions') / '<date>' / '<discussion_id>' / 'state.json'
state = json.loads(state_path.read_text())
state['current_phase'] = 'complete'
state['completed_phases'].append('adoptions_executed')
state['status'] = 'complete'
state_path.write_text(json.dumps(state, indent=2))
"
```

```bash
python scripts/close_discussion.py "<discussion_id>"
```

If the target was a GitHub clone, remove the temporary directory:
```bash
rm -rf /tmp/analyze-<slug>
```

Report the analysis report location to the developer.
