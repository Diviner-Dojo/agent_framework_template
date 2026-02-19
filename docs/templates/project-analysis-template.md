---
analysis_id: "ANALYSIS-YYYYMMDD-HHMMSS-<slug>"
discussion_id: "<linked discussion ID>"
target_project: "<path or github url>"
target_language: "<primary language>"
target_stars: "<star count if github, N/A if local>"
agents_consulted: []
patterns_evaluated: 0
patterns_recommended: 0
analysis_date: "YYYY-MM-DD"
---

## Project Profile

- **Name**: [project name]
- **Source**: [local path or GitHub URL]
- **Tech Stack**: [language, framework, database, etc.]
- **Size**: [rough LOC estimate, file count]
- **Maturity**: [age, activity level, test presence, CI/CD, documentation quality]
- **AI Integration**: [none / basic (.cursorrules only) / moderate (CLAUDE.md) / sophisticated (multi-agent system)]

### Tech Stack Details

[Notable dependencies, framework versions, architectural choices]

### Key Files Examined

| File | Significance |
|------|-------------|
| `path/to/file` | [Why this file was examined] |

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.XX)

[Initial survey findings, pattern inventory, AI artifact analysis]

### Architecture Consultant (confidence: 0.XX)

[Architectural patterns evaluated, comparison to our project]

### Security Specialist (confidence: 0.XX)

[Security patterns evaluated, posture assessment]

### QA Specialist (confidence: 0.XX)

[Testing strategy evaluation, coverage approach]

### Performance Analyst (confidence: 0.XX)

[Performance patterns, concurrency, caching]

### Documentation & Knowledge (confidence: 0.XX)

[Documentation quality, ADRs, onboarding experience]

### Independent Perspective (confidence: 0.XX)

[Fresh-eyes observations, surprises, risks, pre-mortem]

---

## Pattern Scorecard

Scoring rubric (each dimension 1-5):
- **Prevalence**: How common is the problem this solves?
- **Elegance**: Is the solution minimal and clear?
- **Evidence**: How widely adopted is this approach?
- **Fit**: How easily does it fit our project?
- **Maintenance**: What's the ongoing cost?

Threshold: >= 20 = ADOPT, 15-19 = DEFER, < 15 = SKIP

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|---------|
| [name] | /5 | /5 | /5 | /5 | /5 | /25 | ADOPT / DEFER / SKIP |

---

## Recommended Adoptions

*Only patterns scoring >= 20/25.*

### [Pattern Name] (Score: XX/25)

- **What**: [Description of the pattern]
- **Where it goes**: [Target location in our project]
- **Why it scored high**: [Key dimension scores explained]
- **Implementation notes**: [How to adapt it for our context]
- **Sightings**: [N — how many projects we've seen this in, if tracked]

---

## Anti-Patterns & Warnings

*Things this project does that we should actively avoid.*

### [Anti-Pattern Name]

- **What**: [Description]
- **Where seen**: [file:line in the external project]
- **Why it's bad**: [Risk or consequence]
- **Our safeguard**: [How our project already prevents this, or what we should add]

---

## Deferred Patterns

*Patterns scoring 15-19. Interesting but not ready for adoption.*

### [Pattern Name] (Score: XX/25)

- **What**: [Description]
- **Why deferred**: [Which dimensions scored low]
- **Revisit if**: [What would change the score — e.g., "seen in 2 more projects" or "our project grows to need this"]

---

## Specialist Consensus

- **Agents that agreed**: [Which specialists found similar things]
- **Notable disagreements**: [Where specialists diverged and why]
- **Strongest signal**: [The single most important finding from this analysis]
