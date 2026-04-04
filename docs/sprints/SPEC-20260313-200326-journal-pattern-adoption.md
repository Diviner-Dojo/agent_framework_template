---
spec_id: SPEC-20260313-200326
title: "Adopt patterns from agentic journal and external project analyses"
status: reviewed
risk_level: medium
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260313-200419-journal-pattern-adoption-spec-review
---

## Goal

Backport 14 patterns from three sources into the framework template:
- **Agentic journal** (C:\Work\AI\agentic_journal\) — a derived project with enhancements to scripts, hooks, commands, and documentation
- **awesome-claude-code** analysis — security evaluation command (22/25 score)
- **awesome-claude-code-subagents** analysis — description framing and documentation rule

## Context

The agentic journal is a Flutter/Dart project built on this framework. It has evolved independently and now has enhancements that should flow back to the template. The external analyses identified additional gaps. The developer specifically values the versioning/bump_version.py pattern and wants all items adopted before starting the next task.

Key discovery: Tier 1 scripts already exist in the template but are older/smaller versions. The journal versions are significantly enhanced (enforce_forgetting_curve: 114→239 lines, unify_sightings: 129→242 lines). redact_secrets.py is already identical (118 lines each).

## Requirements

### Tier 1 — Upgrade existing scripts with journal enhancements
- R1.1: Upgrade `scripts/enforce_forgetting_curve.py` from journal version (adds dual thresholds: 90-day review, 180-day auto-archive, `last_referenced_at` from SQLite, skip logic for `.gitkeep`/`adoption-log.md`)
  - **Testability requirement**: Accept `memory_dir` and `db_path` as optional parameters (defaulting to current constants) so tests can use `tmp_path`
  - **Safety requirement**: Handle NULL `last_referenced_at` gracefully (fall back to mtime). Mandate `--dry-run` as first execution against live memory/
- R1.2: Upgrade `scripts/unify_sightings.py` from journal version (adds pattern_key normalization with stop-word removal, duplicate detection, discussion validation, `--dry-run` mode)
- R1.3: Verify `scripts/check_stale_adoptions.py` — journal has 174 lines vs template 164; diff and merge any improvements
- R1.4: Skip `scripts/redact_secrets.py` — already identical (118 lines each)
- R1.5: Add known limitation note to CLAUDE.md `## Known Limitations` section: pre-commit hook doesn't support `--skip-reviews` passthrough

### Tier 2 — New script + hook enhancements
- R2.1: Create `scripts/bump_version.py` adapted for `pyproject.toml` format (`version = "X.Y.Z"`) with --read, --patch, --minor, --major commands. Regex-based to preserve TOML formatting. This fixes a broken reference — `/ship` already calls this script but it doesn't exist.
  - **Security requirement**: After computing new_version, validate against strict semver regex (`^\d+\.\d+\.\d+$`) before writing to disk. Reject malformed output.
  - **Scoping requirement**: Only modify the `version` key under `[project]` section, not other TOML sections that may contain `version =` lines.
  - **Error handling**: Raise a clear, named error when `version =` is not found under `[project]`.
- R2.2: Enhance `.claude/hooks/pre-commit-gate.sh` with:
  - Regression ledger check: cross-reference staged file **full relative paths** against `memory/bugs/regression-ledger.md` (not basenames, to avoid false positives from same-named files in different directories)
  - Review reminder: check for `docs/reviews/REV-YYYYMMDD-*` matching today's date
  - Path references use `src/` (not `lib/`), marker `@pytest.mark.regression` (not `@Tags`)
  - **Security requirement**: Use `while IFS= read -r` instead of unquoted `for` loop for staged filenames. Use `grep -qF` (fixed string) to prevent regex injection from filenames.
- R2.3: Register `@pytest.mark.regression` marker in `pyproject.toml` markers list.

### Tier 3 — /ship command rebuild
- R3.1: Rebuild `.claude/commands/ship.md` with journal's automation architecture:
  - Auto-classify changes (code vs framework vs config/docs)
  - Auto-decide review requirement — classification logic must derive from and reference `commit_protocol.md` and `review_gates.md`, not encode independent thresholds
  - Auto-version bump via `scripts/bump_version.py` (patch for fixes, minor for features, major requires confirmation)
  - Auto-PR creation with summary
  - Post-merge cleanup (delete feature branch, pull main)
  - Preserve existing `--solo` mode for direct-commit workflow
  - Use portable `gh auth status` for CLI detection — no hardcoded Windows paths (verify: no `C:\Program Files` strings)
  - Error handling: if `bump_version.py` fails, halt before commit — do not proceed with old version
- R3.2: Write ADR-0004 documenting the /ship automation architecture: classification logic, review thresholds, auto-bump rationale, --solo preservation decision. Per ADR-0003 precedent for workflow decisions.

### Tier 4 — Documentation and pattern updates
- R4.1: Add `FEATURE_STATUS.md` pattern to `.claude/skills/` as a reference guide for derived projects
- R4.2: Add autonomous execution authorization scoping format to CLAUDE.md — define the schema/format for how derived projects should scope authorizations (branch scope, authorized actions, prohibited actions). Keep template's own authorization empty/default. Reference journal's example in skills, not in template body.
- R4.3: Add deferred ADR placeholder pattern to `.claude/skills/adr-writing/SKILL.md`
- R4.4: Update `.claude/rules/documentation_policy.md` with agent addition rule: "When adding a new agent definition (`.claude/agents/*.md`), update CLAUDE.md's Agent Architecture section and write an ADR if the new role type is novel."
- R4.5: Update `.claude/agents/project-analyst.md` description to "Use when..." trigger framing
- R4.6: Update `.claude/agents/steward.md` description to "Use when..." trigger framing
- R4.7: Create `.claude/commands/evaluate-repo-security.md` — security-first evaluation command for external repos (adapted from awesome-claude-code's MIT-licensed evaluate-repository.md)
  - Include explicit boundary section: "Use this when..." (security-only, adversarial, no adoption scoring) vs "Use /analyze-project when..." (adoption quality, pattern mining)
  - Threat model must include: hooks/implicit execution, declared vs inferred permissions, dependency chain evaluation, secrets in git history, build/CI script review
  - Wrap external file content in `<external-file>` delimited blocks with untrusted-data framing
  - Invoke `redact_secrets.py` before including file content in prompts
  - Bound file reads to 50KB per file
- R4.8: Add verification cache bypass note to CLAUDE.md Known Limitations: pre-commit hook regression ledger and review reminders are suppressed during the 5-minute cache window after quality gate runs

## Constraints

- All scripts must use Python 3.11+ standard library only (no new dependencies)
- `bump_version.py` must target `pyproject.toml` format, NOT `pubspec.yaml`
- Pre-commit hook must remain advisory (exit 0), not blocking
- `/ship` must preserve `--solo` mode for developers who own their main branch
- Security eval command must complement (not replace) existing `/analyze-project`
- No Flutter/Dart-specific content in any adopted artifact

## Acceptance Criteria

### Scripts
- [ ] `scripts/enforce_forgetting_curve.py` upgraded with journal's dual-threshold logic, injectable `memory_dir`/`db_path` params
- [ ] `scripts/unify_sightings.py` upgraded with journal's normalization and validation
- [ ] `scripts/check_stale_adoptions.py` reviewed and merged (advisory-only, not gated in quality_gate.py)
- [ ] `scripts/bump_version.py` created with --read, --patch, --minor, --major for `pyproject.toml`
- [ ] `bump_version.py` raises clear error when `version =` not found under `[project]`
- [ ] `bump_version.py` validates output against strict semver before writing

### Tests (blocking — required before build is complete)
- [ ] `tests/test_bump_version.py` covers: all 4 CLI modes, missing version line, missing file, TOML formatting preservation, [project] section scoping
- [ ] `tests/test_enforce_forgetting_curve.py` covers: both thresholds, --dry-run, .gitkeep skip, NULL last_referenced_at, injectable paths
- [ ] `tests/test_unify_sightings.py` covers: duplicate detection, --dry-run, empty/missing adoption log, normalization
- [ ] `@pytest.mark.regression` marker registered in `pyproject.toml`

### Hooks
- [ ] Pre-commit hook detects regression ledger matches for staged files (full relative paths, not basenames)
- [ ] Pre-commit hook reminds about review when code files are staged
- [ ] Pre-commit hook uses safe filename handling (`while IFS= read -r`, `grep -qF`)

### Commands
- [ ] `/ship` auto-classifies changes and auto-decides review requirement (deriving from commit_protocol.md)
- [ ] `/ship` auto-bumps version via `bump_version.py`, halts on failure
- [ ] `/ship --solo` still works for direct-commit workflow
- [ ] No `C:\Program Files` or hardcoded Windows paths in rebuilt `ship.md`
- [ ] ADR-0004 written for /ship automation architecture
- [ ] `evaluate-repo-security.md` exists with explicit boundary vs /analyze-project, supply chain coverage, untrusted-data framing

### Documentation
- [ ] Agent descriptions updated for project-analyst and steward ("Use when..." framing)
- [ ] Documentation policy includes agent addition rule (specified text)
- [ ] CLAUDE.md Known Limitations populated (--skip-reviews passthrough + cache bypass)
- [ ] CLAUDE.md Autonomous Execution Authorization has format/schema documentation

### Quality
- [ ] All existing tests pass (`pytest tests/`)
- [ ] Quality gate passes (`python scripts/quality_gate.py`)

## Risk Assessment

- **Medium risk**: `/ship` rebuild is the largest change — touches a core workflow command. Mitigated by preserving `--solo` mode and comparing against working journal version.
- **Low risk**: Script upgrades — the journal versions are battle-tested in a derived project. The template versions are older but share the same schema.
- **Low risk**: Documentation changes — no code impact.
- **Low risk**: Security eval command — new additive command, no impact on existing functionality.

## Affected Components

### Modified files
- `scripts/enforce_forgetting_curve.py` (upgrade)
- `scripts/unify_sightings.py` (upgrade)
- `scripts/check_stale_adoptions.py` (minor merge)
- `.claude/hooks/pre-commit-gate.sh` (enhance)
- `.claude/commands/ship.md` (rebuild)
- `.claude/rules/documentation_policy.md` (add rule)
- `.claude/agents/project-analyst.md` (description update)
- `.claude/agents/steward.md` (description update)
- `.claude/skills/adr-writing/SKILL.md` (add deferred ADR pattern)
- `CLAUDE.md` (known limitations + autonomous auth example)

### New files
- `scripts/bump_version.py`
- `tests/test_bump_version.py`
- `tests/test_enforce_forgetting_curve.py`
- `tests/test_unify_sightings.py`
- `.claude/commands/evaluate-repo-security.md`
- `.claude/skills/feature-status-registry/SKILL.md`
- `docs/adr/ADR-0004-ship-automation-architecture.md`

## Dependencies

- `metrics/evaluation.db` must have `promotion_candidates` and `pattern_sightings` tables (existing)
- `memory/lessons/adoption-log.md` must exist (existing)
- `memory/bugs/regression-ledger.md` must exist for pre-commit hook (existing)
- `gh` CLI required for `/ship` team mode (existing requirement)
