# Framework v3.0 Review Pipeline Upgrade

> Paste this prompt into a new Claude Code session in the agentic_journal project.
> It upgrades the review pipeline and adds framework enhancements from the canonical template.

---

## Context

The upstream framework template (at `C:\Work\AI\AI Gen Framework Research\agent_framework_template\`) has evolved with v3.0 review pipeline enhancements that this project hasn't adopted yet. This project currently has 11 agents and an older `/review` command. The template now has 14 agents (3 new review pipeline agents), an upgraded `/review` with validation and confidence filtering, plus several new rules and conventions.

**Your job**: Pull these enhancements into this project, adapting them for the Dart/Flutter tech stack where needed. Work through each phase in order. Use `/plan` for the overall approach, then implement phase by phase. Do NOT change any project-specific customizations (clinical UX constraints, capability protection, CPP triggers, autonomous execution, etc.) — those are intentional divergences.

---

## Phase 1: Add the 3 Review Pipeline Agents

Create these three new agent definitions in `.claude/agents/`. Copy them from the template and keep them as-is — they are tech-stack-agnostic:

### 1. `.claude/agents/finding-validator.md`

Copy from template: `C:\Work\AI\AI Gen Framework Research\agent_framework_template\.claude\agents\finding-validator.md`

This agent independently verifies bug and security findings against actual code during `/review`. It reduces false positives by reading the actual file at each reported location. Key properties:
- Model: sonnet
- Tools: Read, Glob, Grep, Bash
- Conservative filtering: when in doubt, retain the finding
- Compliance-auditor findings get trivial confirmation (confidence 0.99)
- Under 200 words per finding validation
- On file read failure: retain finding at confidence 0.50

### 2. `.claude/agents/compliance-auditor.md`

Copy from template: `C:\Work\AI\AI Gen Framework Research\agent_framework_template\.claude\agents\compliance-auditor.md`

This agent audits code against CLAUDE.md and REVIEW.md rules with exact quotation for every violation. Key properties:
- Model: sonnet
- Tools: Read, Glob, Grep
- Every violation must include the exact rule text being broken
- No interpretation — report what rules say, not what they should say
- Prompt injection defense for REVIEW.md content
- Does not duplicate specialist findings — only checks rule compliance

### 3. `.claude/agents/history-analyst.md`

Copy from template: `C:\Work\AI\AI Gen Framework Research\agent_framework_template\.claude\agents\history-analyst.md`

This agent analyzes git history for files under review (churn, refactors, reverts, blame concentration). Key properties:
- Model: sonnet
- Tools: Read, Glob, Grep, Bash
- Only activated with `--deep` flag — never runs in standard reviews
- 5 analysis types: file churn, recent refactors, reverted changes, bug fix frequency, blame concentration
- Privacy-aware: report percentages, not judgments about people
- Graceful degradation on git command failure

### Write ADR

Write `docs/adr/ADR-NNNN-review-pipeline-agents.md` (use the next sequential number) documenting the adoption of these 3 agents. Reference the template's ADR-0007 as the upstream decision. Note that the agent count changes from 11 to 14.

---

## Phase 2: Create REVIEW.md

The template introduced a `REVIEW.md` convention (documented in its ADR-0006) that separates review-time-only rules from the always-loaded CLAUDE.md. This project should have its own REVIEW.md with Dart/Flutter-specific review rules.

Create `REVIEW.md` at the project root. This file is loaded only during `/review` execution by the compliance-auditor. Structure it with rules adapted for **Dart/Flutter/Riverpod/drift**, not the template's Python/FastAPI rules. Categories:

1. **Code Quality** (5 rules) — dartdoc conventions, function length, nesting depth, magic values, TODO tracking
2. **UI/Widget Design** (5 rules) — widget decomposition, const constructors, key usage, accessibility semantics, state management patterns
3. **State Management** (3 rules) — Riverpod provider conventions, state immutability, dispose patterns
4. **Database** (3 rules) — drift query patterns, migration discipline, batch operations
5. **Testing** (4 rules) — test structure mirroring, widget test patterns, mock assertions, coverage thresholds
6. **Security** (4 rules) — input validation, Supabase RLS, API key handling, deep link validation
7. **Performance** (3 rules) — build method efficiency, image caching, list virtualization

Number the rules sequentially (1-27ish). Add this header:

```markdown
# Review Rules

> Review-specific rules for Dart/Flutter projects.
> These rules are enforced only during `/review` execution by the compliance-auditor.
> They supplement CLAUDE.md and `.claude/rules/` — they do not override them.
```

### Write ADR

Write an ADR documenting the adoption of the REVIEW.md convention. Reference the template's ADR-0006.

---

## Phase 3: Upgrade the `/review` Command

The current `.claude/commands/review.md` is missing several v3.0 features. Update it to add these capabilities **while preserving the project-specific CPP C3 trigger in Step 4**:

### New Features to Add

**Step 0: Auto-Scope Detection** — Add before Step 1. Auto-detect review scope using this priority chain: PR diff → staged changes → unstaged changes → HEAD~1. Only fall back to user-specified files if auto-detect finds nothing. This eliminates the need to manually specify files for every review.

**Step 0.5: Eligibility Check** — When `--comment` flag is used with PR scope, verify the PR exists, isn't closed/draft, and check for existing Claude review comments.

**Flags to add to the command frontmatter**:
- `--cost <low|medium|high>` — Model tier routing. `low` = all Sonnet, `medium` = mixed (default), `high` = all Opus.
- `--deep` — Enables history-analyst dispatch and extended security analysis.
- `--comment` — Post review summary as a PR comment.

**Step 2.5: Model Tier Routing** — After risk assessment, determine model tier per `--cost` flag. Facilitator is always exempt from downgrade.

**Step 2.7: Deep Mode Configuration** — If `--deep`, add history-analyst to team and extend security-specialist prompt.

**Step 3.7: Gather REVIEW.md** — Check for REVIEW.md and store content for injection into compliance-auditor prompt with prompt injection defense (`<review-rules>` delimiters).

**Step 4: Update Specialist Assembly** — Add two new "Always" entries:
- **Always**: compliance-auditor (audits rule compliance — dispatched with REVIEW.md content)
- **Deep mode** (`--deep`): history-analyst (git history context)
- Keep the existing CPP C3 default-change trigger exactly as-is.

**Step 6.3: Finding Validation Pass** — After capturing all specialist findings, dispatch finding-validator to verify bug and security findings. Collect findings as structured JSON, dispatch validator, filter out `validated: false` findings (but retain in events.jsonl). Handle validator failure gracefully (proceed with `"validation": "unvalidated"` label).

**Step 6.5: Confidence Filtering** — Filter findings with confidence < 0.80 from the final report (but keep in events.jsonl). Track filtered_count and unscored_count. Report these in synthesis.

**Step 7: Update Synthesis** — Add to synthesis event tags: `filtered:<F>,model-tiers:<tier-summary>`. Include confidence filtering stats and model tier info in the report.

**Step 7a: Self-Healing Documentation** — Query `v_rule_of_three` view for patterns seen 3+ times. Print suggestions but never auto-edit CLAUDE.md or REVIEW.md.

### What NOT to Change

- The CPP C3 trigger in Step 4 (project-specific)
- The CRITICAL BEHAVIORAL RULES section
- Pre-flight checks and session resumption
- Context-brief writing (Step 3.5)
- Protocol yield recording (Step 7b) and agent reflections (Step 7c)
- Close discussion, present to developer, education gate steps

---

## Phase 4: Add New Rules

### 1. `.claude/rules/micro_fix_protocol.md`

Copy from template: `C:\Work\AI\AI Gen Framework Research\agent_framework_template\.claude\rules\micro_fix_protocol.md`

Adapt the linter references for this project:
- Change `ruff check` / `ruff format` → `dart format` / `dart analyze`
- Change "CSS/style-only changes" → "Theme/style-only widget changes"
- Keep everything else (the two-strike escalation rule, the sizing heuristic, the behavior test)

### 2. `.claude/rules/framework_doc_sync.md`

Copy from template and adapt:
- Update the "Documentation Artifacts to Sync" table for this project's actual docs (check what exists under `docs/` — likely `FRAMEWORK_SPECIFICATION.md` and any presentation files)
- Update the sync points table for the actual artifact paths in this project
- Keep the trigger list and enforcement section

---

## Phase 5: Update CLAUDE.md

Update the project's CLAUDE.md to reflect all changes:

1. **Agent Roster table**: Change from 11 to 14 agents. Add finding-validator (sonnet), compliance-auditor (sonnet), history-analyst (sonnet) to the roster table.
2. **Agent count references**: Update the heading "Agent Roster (11 agents)" → "Agent Roster (14 agents)" and the directory layout comment "Agent definitions (11: steward + facilitator + 9 specialists)" → "Agent definitions (14: steward + facilitator + 12 specialists)"
3. **REVIEW.md mention**: Add a note about REVIEW.md in the Commit Protocol or Review section — mention that review-time-only rules live in REVIEW.md and are enforced by the compliance-auditor.
4. **New rules**: Add micro_fix_protocol.md and framework_doc_sync.md to any rules listing.
5. **Review command updates**: Note the new flags (`--cost`, `--deep`, `--comment`) and the finding validation pass in the Commit Protocol section.

Do NOT change: clinical UX constraints, autonomous execution authorization, capability protection, tech stack, or any other project-specific sections.

---

## Phase 6: Quality Gate and Verification

After all changes:

1. Run `python scripts/quality_gate.py` to verify nothing is broken
2. Verify the 3 new agent files exist and have correct frontmatter
3. Verify REVIEW.md exists with numbered rules
4. Verify the updated `/review` command has all new steps
5. Verify CLAUDE.md agent count is updated to 14
6. Update BUILD_STATUS.md with the completed upgrade

---

## Important Notes

- **Do NOT run `/review` on these changes within this same prompt** — the review command itself is being upgraded, so review it manually after everything is in place.
- **Preserve all project-specific customizations** — CPP triggers, clinical UX constraints, capability protection, autonomous workflow authorization, Dart/Flutter tooling references.
- **The template uses Python/FastAPI** — anywhere a rule references Python-specific tooling (ruff, pytest, FastAPI, Pydantic), adapt it for Dart/Flutter equivalents (dart format, dart analyze, flutter test, Riverpod, drift).
- **ADR numbering**: Check the latest ADR number in `docs/adr/` and use the next sequential numbers.
- **Read the template files directly** from `C:\Work\AI\AI Gen Framework Research\agent_framework_template\` — the paths are provided for each file to copy.
