# Agent Framework Template

> AI-native development for people who think well and want to ship well.

A structured, multi-agent development framework for
[Claude Code](https://claude.ai/claude-code) that turns AI-assisted
development into a disciplined, self-improving engineering methodology.

You bring the thinking. The agents handle the rest.

## Who Should Use This

| You are... | You get... |
|---|---|
| A business wanting controlled AI development | Auditable decisions, enforced quality gates, no cowboy coding |
| A builder learning a new stack | AI that builds *and* teaches, with explanations at every step |
| A solo dev who wants senior-level guardrails | Specialist agent review without hiring a team |

## Quick Start

```bash
# Clone the template
git clone https://github.com/Diviner-Dojo/agent_framework_template myproject
cd myproject

# Install framework dependencies
pip install -r requirements.txt

# Initialize the metrics database
python scripts/init_db.py

# Open in Claude Code and start building
claude .
```

Then tell Claude what you want to build. The framework takes it from there.

## The Development Loop

```
  Plan  -->  Build  -->  Review  -->  Learn  -->  Ship
   |                                                |
   +------------------------------------------------+
                   Every decision captured.
                   Every trade-off documented.
```

1. **Plan** -- Spec the feature before a line of code is written
2. **Build** -- AI agents generate code with mid-build checkpoint reviews
3. **Review** -- Independent specialist agents evaluate every change
4. **Learn** -- Education gates ensure you understand what was built
5. **Ship** -- Quality gates enforce standards before anything merges

## Framework Commands

In Claude Code:

| Command | What It Does |
|---|---|
| `/plan "feature"` | Plan a feature with spec-driven development |
| `/build_module spec` | Build from a spec with integrated quality gates |
| `/review src/` | Run a multi-agent code review |
| `/deliberate "topic"` | Start a structured multi-agent discussion |
| `/walkthrough src/` | Get a guided code walkthrough |
| `/quiz src/` | Take a comprehension quiz on the code |
| `/retro` | Run a sprint retrospective |
| `/ship` | Quality gate, review, commit, PR, merge -- end to end |

## The Agent Panel

Eight specialist agents, each with a distinct professional perspective:

| Agent | Focus | Activated When |
|---|---|---|
| **Facilitator** | Orchestration, synthesis | Every workflow |
| **Architecture Consultant** | Structural alignment, drift | Architecture changes, new modules |
| **Security Specialist** | Vulnerabilities, threats | Auth, API, data handling |
| **QA Specialist** | Test coverage, reliability | Every code review |
| **Performance Analyst** | Efficiency, scalability | Data processing, DB, API |
| **Docs/Knowledge** | Documentation, ADRs | Every review (light), arch changes (full) |
| **Educator** | Developer understanding | Every merge gate |
| **Independent Perspective** | Anti-groupthink | Medium/high risk changes |

Agents collaborate through **coopetition** -- shared goals with different
professional priorities, producing natural productive tension without
manufactured opposition.

## Key Concepts

- **Four-Layer Capture**: Immutable event logs, SQLite index, curated
  memory, optional vector search -- nothing gets lost
- **Education Gates**: Walkthrough, quiz, explain-back, then merge.
  The AI teaches you what it built before you ship it.
- **Nested Improvement Loops**: Per-discussion (micro), per-sprint
  retrospective (meso), quarterly meta-review (macro)
- **Spec-Driven Development**: Every significant change starts with
  an approved spec -- not a vague prompt

## Directory Structure

```
.claude/
  agents/       -- Specialist agent definitions
  commands/     -- Workflow commands (/review, /plan, /build, etc.)
  rules/        -- Auto-loaded standards (all agents inherit these)
  skills/       -- Reference knowledge playbooks

docs/
  adr/          -- Architecture Decision Records
  reviews/      -- Review reports
  sprints/      -- Sprint plans, retrospectives
  templates/    -- Reusable artifact templates

discussions/    -- Immutable discussion capture (events + transcripts)
memory/         -- Curated knowledge (human-approved patterns and rules)
metrics/        -- SQLite relational index for querying and trends
scripts/        -- Capture pipeline and quality gate (Python)

src/            -- Your application source code goes here
tests/          -- Your test suite goes here
```

## Framework Spec

See the full framework specification:
`AI_Native_Agentic_Development_Framework_v2.1.md`

---

Built by [Diviner Dojo](https://github.com/Diviner-Dojo) --
*where great thinking becomes great software.*
