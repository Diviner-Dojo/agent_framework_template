---
analysis_id: "ANALYSIS-20260219-043753-agenticakm"
discussion_id: "DISC-20260219-042737-analyze-agenticakm"
target_project: "https://github.com/sa4s-serc/AgenticAKM.git"
target_language: "Python (Jupyter Notebook primary)"
target_stars: 1
agents_consulted: [project-analyst, architecture-consultant, docs-knowledge, independent-perspective]
patterns_evaluated: 4
patterns_recommended: 1
analysis_date: "2026-02-19"
---

## Project Profile

- **Name**: AgenticAKM (Agentic Architecture Knowledge Management)
- **Source**: https://github.com/sa4s-serc/AgenticAKM.git
- **Tech Stack**: Python 3.12, Jupyter notebooks, google-generativeai (Gemini 2.5 Pro), openai (GPT-5), pydantic, python-dotenv
- **Size**: ~646 LOC in AdrAgents.py, ~1,500-2,000 LOC across 5 notebooks. 1,446 generated ADR markdown files across 41 repositories.
- **Maturity**: Academic research prototype (ICSE 2025 paper). Single branch, 2 commits, no tests, no CI/CD, no requirements.txt, no linting. Empirically validated: 29 repositories, user study with 29 participants.
- **AI Integration**: The project IS the AI system — multi-agent pipeline for ADR generation. No meta-AI tooling (.claude/, CLAUDE.md, etc.).

### Tech Stack Details

- `google-generativeai`: Gemini 2.5 Pro for generation and verification agents
- `openai`: GPT-5 for cross-model ADR generation comparison
- `pydantic`: BaseModel for ADR schema validation
- `python-dotenv`: Environment-based API key management
- No web framework, no database, no test suite, no package management files

### Key Files Examined

| File | Significance |
|------|-------------|
| `Code/AdrAgents.py` | Core agent pipeline: 5 agents + orchestrator. Generate-verify-regenerate loop. |
| `Code/AgenticAdr.ipynb` | Full working notebook with execution traces. Shows loop behavior on real repos. |
| `Code/evaluations.ipynb` | User study quantitative results. Evidence for agent vs. LLM quality claim. |
| `Code/CodeToAdr.ipynb` | Baseline single-LLM approach for comparison. |
| `Generated_ADRs/stanfordnlp_dspy/dir3/` | Agent-generated ADRs for a well-known project. Quality benchmark. |
| `Generated_ADRs/stanfordnlp_dspy/dir4/` | GPT-generated ADRs for same project. Cross-model comparison. |
| `README.md` | Project structure and workflow description. |

---

## Specialist Findings

### Project Analyst — Scout Report (confidence: 0.88)

AgenticAKM implements a 5-agent pipeline for automated ADR generation from codebases:
1. **RepoSummarizer** — summarizes repository files
2. **SummaryCheckerAgent** — verifies summary quality
3. **AdrGeneratorAgent** — generates ADRs from verified summaries
4. **AdrCheckerAgent** — verifies ADR quality and completeness
5. **OrchestratorAgent** — coordinates the pipeline with bounded retry loops

Key architectural insight: the pipeline uses two sequential generate-verify-regenerate loops. Each loop has max 3 attempts. The verifier returns CORRECT/INCORRECT plus actionable feedback, which is injected verbatim into the generator's next prompt. Persistence (file writes) is deferred until after final verification passes.

Empirical validation: Agent approach scored 4.5/5 vs. 3.5/5 for single-LLM. Completeness dimension improved most dramatically (4.0 vs. 2.5-3.0).

Anti-patterns identified: file-size-based selection heuristic (selects angular.js over app code), no tests, global mutable state, soft failure boundaries (continues past max_attempts), no temp directory cleanup.

### Architecture Consultant (confidence: 0.82)

Two applicable patterns identified:

1. **Generate-verify-regenerate loop** — applicable to `/analyze-project` Phase 1 survey. The facilitator maintains the loop (not a subagent). Survey output gets a quality gate before specialist dispatch. NOT applicable to `/build_module` where pytest already provides deterministic verification.

2. **Save-last pattern** — already implicitly followed in our artifact generation (review reports written once at end). Making it explicit prevents partial artifact contamination on interrupted sessions. Documentation change, not code change.

### Documentation & Knowledge (confidence: 0.85)

Two applicable patterns identified:

1. **Pydantic-validated structured output schema for ADR fields** — addresses a real gap: no machine-checkable ADR completeness validation in our framework. A lightweight validator checking required YAML frontmatter fields and markdown sections would catch malformed ADRs before they enter `docs/adr/`.

2. **Empirical evidence that agentic decomposition outperforms single-LLM** — the quality gap (especially completeness: 4.0 vs. 2.5) suggests our `/analyze-project` single-pass survey phase may leave completeness on the table.

### Independent Perspective (confidence: 0.79)

Most underappreciated finding: the empirical completeness quality gap (Agent: 4.0/5 vs. LLM: 2.5/5). Our `/analyze-project` has no quality gate on the Phase 1 project profile. If the survey is incomplete or inaccurate, all downstream specialist evaluations inherit that error.

Dissent with architecture-consultant: the generate-verify-regenerate loop should NOT be applied to `/build_module` where pytest already verifies. The pattern's value is highest where deterministic verification is unavailable — exactly `/analyze-project` survey (no ground truth) and ADR generation (no test suite for completeness).

This is the 2nd sighting of the "decomposed pipeline with verification" principle (1st: Swarm Plan-Execute-Review, DEFERRED from claude-agentic-framework).

---

## Pattern Scorecard

| Pattern | Prevalence | Elegance | Evidence | Fit | Maintenance | Total | Verdict |
|---------|-----------|----------|----------|-----|-------------|-------|---------|
| Survey Quality Gate (generate-verify-regenerate for Phase 1) | 4/5 | 4/5 | 4/5 | 3/5 | 4/5 | 19/25 | DEFER |
| ADR Completeness Validator | 4/5 | 4/5 | 4/5 | 4/5 | 4/5 | 20/25 | ADOPT |
| Save-Last Artifact Persistence | 3/5 | 4/5 | 3/5 | 3/5 | 3/5 | 16/25 | DEFER |
| CORRECT/INCORRECT Verdict Protocol | 3/5 | 3/5 | 3/5 | 2/5 | 3/5 | 14/25 | SKIP |

---

## Recommended Adoptions

*Only patterns scoring >= 20/25.*

### ADR Completeness Validator (Score: 20/25)

- **What**: A lightweight validation function that checks ADR files for required YAML frontmatter fields (`adr_id`, `title`, `status`, `date`, `decision_makers`, `discussion_id`) and required markdown sections (Context, Decision, Alternatives Considered, Consequences).
- **Where it goes**: `scripts/quality_gate.py` — add as a new check in the existing quality gate pipeline. Runs on any staged ADR files in `docs/adr/`.
- **Why it scored high**: ADRs are the most durable artifact in our four-layer capture stack ("ADRs are never deleted" — Principle #5). A malformed ADR is harder to fix retroactively than a missed test. Prevalence is high (every project with ADRs faces this), fit is good (extends existing quality gate), maintenance is low (~30 lines of Python).
- **Implementation notes**: Not a full Pydantic schema for all agent outputs — scoped specifically to ADR files. Check YAML frontmatter with `yaml.safe_load()`, check markdown sections with simple string search. Architecture-consultant agrees: Pydantic schemas for ephemeral agent output would be over-engineering; for durable artifacts with referential integrity, validation is justified.
- **Sightings**: 1 — first sighting. Pydantic validation for LLM output is increasingly common but this specific ADR-scoped application is novel in our analysis history.
- **Specialist consensus**: docs-knowledge (primary), architecture-consultant (endorsed scoped version), independent-perspective (endorsed)

---

## Anti-Patterns & Warnings

### File Size as Architectural Significance Proxy

- **What**: `RepoSummarizer._summarize_key_files()` selects the 5 largest text files as "key files" for analysis.
- **Where seen**: `AdrAgents.py:138-183`
- **Why it's bad**: File size correlates poorly with architectural significance. Vendored libraries (angular.js, jquery.js) consistently appear as "largest files," drowning out actual application code. Visible in notebook execution traces.
- **Our safeguard**: Our `/analyze-project` uses explicit architectural judgment (project-analyst agent) to identify key files. This is a confirmed superiority of our current approach.

### Soft Failure Boundary (Silent Quality Degradation)

- **What**: `OrchestratorAgent.run()` continues past `max_attempts` even if verification never passed, silently saving unverified output.
- **Where seen**: `AdrAgents.py:601-605, 630-634` (commented-out early returns)
- **Why it's bad**: Produces artifacts of unknown quality without signaling the failure. Downstream consumers assume quality.
- **Our safeguard**: Our quality gate blocks commits on failure. Our review workflow requires explicit verdicts. The principle to maintain: fail loudly, never silently degrade.

### Global Mutable State at Module Level

- **What**: `genai.configure(api_key=...)` and `client = OpenAI(...)` execute at import time.
- **Where seen**: `AdrAgents.py:22-25`
- **Why it's bad**: Any test importing the module triggers API client initialization. Violates testability.
- **Our safeguard**: `coding_standards.md` rule: "No global mutable state." Enforced by review.

### No Test Suite

- **What**: Zero tests. Notebook execution traces serve as the de facto integration tests.
- **Where seen**: Entire project
- **Why it's bad**: Acceptable for a research prototype; unacceptable for production. No regression protection.
- **Our safeguard**: `testing_requirements.md` + quality gate enforces >= 80% coverage.

### No Temp Directory Cleanup

- **What**: `_clone_repo()` creates `tempfile.mkdtemp()` but `run()` never cleans up.
- **Where seen**: `AdrAgents.py` (OrchestratorAgent)
- **Why it's bad**: Resource leak on repeated runs. Disk fills over time.
- **Our safeguard**: Our `/analyze-project` command explicitly cleans up GitHub clones in Step 8.

---

## Deferred Patterns

### Survey Quality Gate — Generate-Verify-Regenerate for Phase 1 (Score: 19/25)

- **What**: Add a verifier step between Phase 1 (survey) and Phase 2 (specialist dispatch) in `/analyze-project`. After the project profile is produced, a lightweight checker evaluates whether: (a) at least 3-5 architecturally significant files were identified, (b) tech stack was identified, (c) no obvious errors. If check fails, survey is refined once (max 2 attempts).
- **Why deferred**: Fit scored 3/5 — implementing the retry loop within our command invocation model requires the facilitator to maintain the loop, adding complexity to the `/analyze-project` command. The benefit is real (empirically validated completeness improvement) but the command restructuring cost is non-trivial.
- **Sightings**: 2 — this is the 2nd sighting of the "decomposed pipeline with verification" principle. 1st sighting: "Swarm Plan→Execute→Review Pipeline" (DEFERRED, 17/25) from claude-agentic-framework. Approaching Rule of Three threshold.
- **Revisit if**: 3rd sighting triggers Rule of Three (+2 bonus → 21/25, crosses adopt threshold). Or if a survey phase produces an incomplete/inaccurate profile that leads to poor specialist analysis (concrete failure).

### Save-Last Artifact Persistence (Score: 16/25)

- **What**: Explicitly document that structured artifacts (ADRs, review reports, analysis reports) are generated in-memory and written once after completion, not incrementally.
- **Why deferred**: Already implicitly followed. Making it explicit is a documentation-only change with low urgency. Evidence score is low (convention, not a widely-discussed pattern).
- **Revisit if**: An interrupted session leaves a partial artifact in `docs/reviews/` or `docs/adr/`.

---

## Specialist Consensus

- **Agents that agreed**: All 3 specialists (architecture-consultant, docs-knowledge, independent-perspective) converged on: (1) Phase 1 survey needs a quality gate, (2) ADR validation is a real gap. Save-last pattern got architecture-consultant + docs-knowledge agreement.
- **Notable disagreements**: Architecture-consultant proposed the generate-verify-regenerate loop for `/build_module`; independent-perspective correctly argued pytest already provides deterministic verification there. This dissent narrows the pattern's applicable scope to tasks without deterministic verifiers. The dissent was constructive and resolved.
- **Strongest signal**: The empirical completeness quality gap (4.0/5 agent vs. 2.5/5 single-LLM) provides quantitative evidence that verification loops materially improve output quality for architecture knowledge extraction — the exact task our `/analyze-project` performs. This is evidence, not just theory.
