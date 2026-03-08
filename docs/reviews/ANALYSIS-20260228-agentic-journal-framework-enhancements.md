---
id: ANALYSIS-20260228-agentic-journal-framework-enhancements
date: "2026-02-28"
target_project: agentic_journal
target_tech: Flutter/Dart, Riverpod, Supabase
analyst: project-analyst
specialists_dispatched:
  - qa-specialist
  - docs-knowledge
  - architecture-consultant
confidence: 0.97
notable_patterns: 16
all_recommended: true
primary_theme: regression-prevention
supplemental_review_date: "2026-02-28"
supplemental_focus: versioning-and-ship-workflow
---

# External Project Analysis: agentic_journal Framework Enhancements

## Project Profile

**agentic_journal** is the first real-world project built on the AI-Native Agentic Development Framework v2.1. It is a Flutter/Dart journaling application using Riverpod for state management, drift for local SQLite persistence, Supabase for cloud sync, and ElevenLabs for TTS voice mode. The project ran through at least one full sprint cycle, encountered real production-near bugs, and evolved the framework in response. All framework infrastructure (`.claude/`, `scripts/`, `memory/`) is maintained as a parallel discipline — the application code is Dart, but the framework discipline remains Python/Markdown, making all 13 enhancements directly back-portable to the template with minor syntax adaptation.

---

## Enhancement Inventory

### 1. Regression Ledger (`memory/bugs/regression-ledger.md`) — **ADOPT**

A new `memory/bugs/` subdirectory with a markdown table tracking: Bug | File(s) | Root Cause | Fix | Regression Test | Date. Three entries exist documenting ElevenLabs TTS speed bug, voice mode bypass, and a deploy-wipes-data process bug.

**Problem solved**: Without a ledger, the next session has no way to know old bugs existed, how they were fixed, or where their regression tests live. The File(s) column makes it actionable at modify-time — developers check the ledger *before* touching a file.

**Generalizability**: High. Schema is language-agnostic.

**Adoption cost**: Low.

---

### 2. Commit Protocol — Step 1.5: Regression Test Verification — **ADOPT (adapt)**

A new step between the quality gate and code review. Requires bug fixes to: (a) have a regression test that fails without the fix, (b) tag it `@pytest.mark.regression` (adapted from `@Tags(['regression'])`), (c) add a ledger entry, and (d) commit promptly — *"uncommitted fixes are invisible to git and WILL be lost across sessions."*

**Problem solved**: Bug fixes were committable without regression tests. The "commit promptly" directive addresses a real LLM session failure mode no other rule covers.

**Generalizability**: High. Only tag syntax needs adaptation.

**Adoption cost**: Low.

---

### 3. Commit Protocol — Framework-Only Changes Review Threshold — **ADOPT**

Changes to `.claude/`, `scripts/`, `docs/` touching more than 5 files are treated as medium-risk and require `/review`. Also documents a known limitation: the pre-commit hook does not support `--skip-reviews` passthrough; `--no-verify` is the workaround when fewer than 5 framework files are changed (must log reason in commit message).

**Problem solved**: Large framework changes could bypass independent review under the "no product code" rationale.

**Adoption cost**: Low.

---

### 4. Testing Requirements — Regression Tests Section — **ADOPT (adapt)**

A full "Regression Tests" section: every fix needs a regression test, `@pytest.mark.regression` tag required, naming convention specified, and a protection clause: *"Regression tests must NOT be deleted or weakened without explicit developer approval."*

**Problem solved**: Without an explicit rule, regression tests are gradually weakened during refactors with no audit trail.

**Generalizability**: High. Only tag syntax differs.

**Adoption cost**: Low.

---

### 5. Review Gates — Advisory Lifecycle — **ADOPT (revised)**

Advisory findings must be carried forward as "open advisories" in each subsequent review report until resolved or formally accepted as known limitations. Each report must include an "Open Advisories" tally. When accepting, document in CLAUDE.md so future sessions don't re-flag it.

**Problem solved**: Advisory findings were silently lost after filing. The same gap could appear in three consecutive reviews with no escalation mechanism.

**Generalizability**: High. Entirely process-level, language-agnostic.

**Adoption cost**: Low.

*(docs-knowledge REVISE: expanded the rule text to specify where the tally appears and what "formally accepted" requires — revision incorporated above.)*

---

### 6. Build Review Protocol — Dependency/Service Wiring Trigger + Ledger Check — **ADOPT (adapt)**

Adds "Dependency/service wiring" trigger (Riverpod provider wiring → generalized to FastAPI `Depends()` bindings, middleware order, service registrations). Also adds a fourth bullet to the Specialist Prompt Template: *"Whether regression tests exist for any bug fixes in modified files (check memory/bugs/regression-ledger.md)."*

**Problem solved**: Incorrect dependency wiring is silent at boot time. The ledger check closes the feedback loop between checkpoint reviews and the regression ledger.

**Generalizability**: High for ledger check. Medium for trigger (rename to "Dependency/service wiring").

**Adoption cost**: Low.

---

### 7. CLAUDE.md Principle 6 — Education Gate Deferral Accountability — **ADOPT**

Principle 6 extended: *"Deferrals require developer acknowledgment and must be logged in the retro. Deferred gates must be completed before the next phase begins, or formally re-deferred with documented rationale."*

**Problem solved**: Education gates were silently deferred indefinitely. The developer could be three phases past code they were supposed to understand.

**Generalizability**: High. Process rule, language-agnostic.

**Adoption cost**: Low.

---

### 8. CLAUDE.md — Plan Mode Boundary for `/build_module` — **ADOPT (adapt)**

A new rule in the Build Review Protocol section: *"Multi-file builds executed via plan mode (3+ new files under `src/`) must use `/build_module` — plan mode continuation does not substitute for checkpoint coverage."*

**Problem solved**: Plan-mode continuation silently bypasses the checkpoint protocol for multi-file builds.

**Generalizability**: High. Adapt `lib/` → `src/` for the Python template.

**Adoption cost**: Low.

---

### 9. CLAUDE.md — Known Limitations Documentation Pattern — **ADOPT**

Documents known limitations inline with the components they affect: the review existence check limitation ("verifies a report exists for today, not that it covers the specific files being committed"), and data quality notes in the Capture Pipeline section.

**Problem solved**: Without documentation, the next session re-investigates the same gaps. The review existence limitation is directly present in the template.

**Generalizability**: High. The *pattern* — document known limitations in CLAUDE.md alongside affected components — is broadly applicable.

**Adoption cost**: Low.

---

### 10. QA-Specialist Agent — Regression Prevention Responsibility — **ADOPT**

New section "6. Regression Prevention" added to the qa-specialist agent: checks the ledger for known bugs in modified files, verifies regression tests exist on bug fixes, and **classifies missing regression tests as blocking (not advisory) when fixing a confirmed bug**.

**Problem solved**: Without this instruction, the qa-specialist reviews a bug fix and doesn't notice there's no regression test — or classifies the gap as advisory.

**Architecture-consultant note**: Must be adopted together with Enhancement 1 (ledger). Partial adoption creates an agent that checks a ledger that doesn't exist.

**Adoption cost**: Low.

---

### 11. `review.md` Command — Session Resumption — **ADOPT**

A Session Resumption Check step added before Step 1: checks for a `state.json` with `command == 'review'` and `status == 'in_progress'` to detect and resume interrupted reviews. State is tracked at key lifecycle points and cleaned up at completion.

**Problem solved**: Any review interruption (network error, context limit) loses all prior specialist work. A new `/review` invocation creates a duplicate discussion.

**Generalizability**: High. No language dependency.

**Adoption cost**: Medium (requires modifying the command's create/complete lifecycle).

---

### 12. Review Gates — Provably Incorrect Data Threshold — **ADOPT (adapt)**

*"Data displayed in the UI that is provably incorrect at implementation time must be classified as blocking regardless of whether it affects core functionality."* Adapted for the Python template: API responses that return provably incorrect data at implementation time must be blocking.

**Problem solved**: A specialist classified visibly wrong data as advisory because it wasn't in the "critical path." This rule prevents that misclassification.

**Generalizability**: Medium (UI → API response adaptation needed).

**Adoption cost**: Low.

---

### 13. `build_module.md` — Pre-Flight Rule File Verification — **ADOPT**

Pre-flight check extended to verify that the 4 key rule files exist (coding_standards, security_baseline, testing_requirements, build_review_protocol). Fails immediately if any are missing.

**Problem solved**: Accidentally deleted rule files let the build proceed without safeguards silently.

**Generalizability**: High. Same 4 rule files exist in the template.

**Adoption cost**: Low.

---

## Specialist Verdicts

### QA-Specialist
**APPROVE** on Enhancements 1, 2, 4, 10.
Key finding: The protection clause on regression tests ("must NOT be deleted or weakened without explicit developer approval") is the highest-value line in the entire set — it addresses the silent long-term regression suite erosion failure mode. Enhancements 1 and 10 must be adopted together; adopting one without the other leaves the ledger as an orphaned artifact.

### Docs-Knowledge
**APPROVE** on Enhancements 7, 9, 3. **REVISE** on Enhancement 5 (advisory lifecycle text too spare — expanded in Action Plan below). 
Key finding: The known limitations pattern (Enhancement 9) is an excellent institutional memory practice that should be applied retroactively to the review existence gap and established as a standard going forward.

### Architecture-Consultant
**APPROVE** on Enhancements 6, 8, 11, 13.
Key finding: Enhancements 1, 2, 4, 6, 10 form a coherent regression prevention system and should be adopted as a cluster, not piecemeal. The session resumption enhancement (11) is architecturally sound and addresses a real resilience gap in the `/review` workflow.

---

## Convergence Map

All 13 enhancements achieved consensus approval (Enhancement 5 with docs-knowledge revision incorporated). The regression prevention cluster (1, 2, 4, 6, 10) has the strongest convergence signal — all three specialists identified it as the highest-priority back-port.

---

## Back-Port Action Plan

**Ordered by priority. Must implement Actions 1–4 as a cluster.**

### Action 1 — Create `memory/bugs/regression-ledger.md` *(new file)*
**Priority**: Critical | **Cost**: Low

```markdown
# Regression Ledger

Known bugs, their fixes, and the tests that prevent recurrence.
Check this ledger before modifying any file listed below.

| Bug | File(s) | Root Cause | Fix | Regression Test | Date |
|-----|---------|------------|-----|-----------------|------|
```

---

### Action 2 — Update `.claude/rules/testing_requirements.md`
**Priority**: Critical | **Cost**: Low

Append new section at end of file:
```markdown

## Regression Tests
- Every bug fix MUST include a regression test that would fail under the old buggy code
- Tag regression tests with `@pytest.mark.regression` and include a comment referencing the bug
- Regression test names should describe the bug being prevented: `test_<behavior>_regression`
- When modifying a file that has existing regression tests, verify they still pass and still test the right behavior
- Regression tests must NOT be deleted or weakened without explicit developer approval
```

---

### Action 3 — Update `.claude/rules/commit_protocol.md`
**Priority**: Critical | **Cost**: Low

**3a** — Add Step 1.5 between Step 1 and Step 2:
```markdown
### Step 1.5: Regression Test Verification (Required for bug fixes)
When committing a bug fix:
- Verify a regression test exists that fails without the fix and passes with it
- Verify the test is tagged with `@pytest.mark.regression`
- Add an entry to `memory/bugs/regression-ledger.md` documenting the bug, root cause, fix, and test location
- Commit fixes promptly — uncommitted fixes are invisible to git and WILL be lost across sessions
```

**3b** — After the "For documentation-only..." line in Step 2, add:
```markdown

**Framework-only changes** (files under `.claude/`, `scripts/`, `docs/`) touching **more than 5 files** are treated as medium-risk and require `/review`. This prevents large framework changes from bypassing review under the "no product code" rationale.

**Known limitation**: The git pre-commit hook does not support `--skip-reviews` passthrough. When the hook blocks a commit legitimately exempted by the >5-file heuristic (i.e., fewer than 5 framework files changed), `--no-verify` is the current workaround. Always log the exemption reason in the commit message.
```

---

### Action 4 — Update `.claude/agents/qa-specialist.md`
**Priority**: Critical | **Cost**: Low

Add after "### 5. Verification Strategy" / before "## Anti-Patterns to Avoid":
```markdown

### 6. Regression Prevention
- When reviewing bug fixes: verify a regression test exists that would catch re-introduction
- When reviewing modifications to files with existing regression tests: verify those tests are preserved
- Check `memory/bugs/regression-ledger.md` for known bugs in the files being modified
- Classify missing regression tests as **blocking** (not advisory) when fixing a confirmed bug
```

---

### Action 5 — Update `.claude/rules/review_gates.md`
**Priority**: High | **Cost**: Low

**5a** — Append new section at end:
```markdown

## Advisory Lifecycle

Advisory findings must be carried forward in the next review report as "open advisories" until either resolved or formally accepted as known limitations. Each review report must include an "Open Advisories" section tallying unresolved findings from prior reviews. When accepting an advisory as a known limitation, document it in CLAUDE.md alongside the component it affects so future sessions do not re-flag it.
```

**5b** — Add to Minimum Quality Thresholds section:
```markdown
- API responses that return provably incorrect data at implementation time (not hypothetically incorrect under edge conditions) must be classified as blocking regardless of whether they affect core functionality
```

---

### Action 6 — Update `.claude/rules/build_review_protocol.md`
**Priority**: High | **Cost**: Low

**6a** — Add row to Checkpoint Triggers table (after "External API" row):
```markdown
| **Dependency/service wiring** | New `Depends()` bindings, middleware registration, service factory wiring | architecture-consultant, qa-specialist |
```

**6b** — Add fourth bullet to Specialist Prompt Template "Focus on:" list:
```markdown
- Whether regression tests exist for any bug fixes in modified files (check memory/bugs/regression-ledger.md)
```

---

### Action 7 — Update `CLAUDE.md`
**Priority**: High | **Cost**: Low

**7a** — Principle 6: append deferral accountability language to existing sentence.
> Old ending: `"...Proportional to complexity and risk."`  
> New ending: `"...Proportional to complexity and risk. Deferrals require developer acknowledgment and must be logged in the retro. Deferred gates must be completed before the next phase begins, or formally re-deferred with documented rationale."`

**7b** — Build Review Protocol section: add final bullet to the trigger/protocol summary:
```markdown
- **Plan mode boundary**: Multi-file builds executed via plan mode (3+ new files under `src/`) must use `/build_module` — plan mode continuation does not substitute for checkpoint coverage
```

**7c** — Quality Gate section: add after the "trend analysis" sentence:
```markdown

**Known limitation**: The review existence check verifies that a review report exists for today, not that it covers the specific files being committed.
```

**7d** — Commit Protocol section: after the second gate description, add:
```markdown
For low-risk changes (config, docs, simple fixes), the quality gate alone may suffice. For any code change, always run `/review` first. Framework-only changes (`.claude/`, `scripts/`, `docs/`) touching more than 5 files require `/review` — large framework changes are medium-risk regardless of whether they touch product code.
```

---

### Action 8 — Update `.claude/commands/build_module.md` pre-flight
**Priority**: Medium | **Cost**: Low

In the Pre-Flight Checks Python script block, add after the `scripts` path checks:
```python
for rule in ['.claude/rules/coding_standards.md', '.claude/rules/security_baseline.md',
             '.claude/rules/testing_requirements.md', '.claude/rules/build_review_protocol.md']:
    if not pathlib.Path(rule).exists():
        errors.append(f'Missing required rule file: {rule}')
```

---

### Action 9 (Optional) — Add Session Resumption to `.claude/commands/review.md`
**Priority**: Medium | **Cost**: Medium

Add a Session Resumption Check before Step 1 that checks for a `state.json` with `command == 'review'` and `status == 'in_progress'` in today's discussion directory. Initialize state at the create_discussion step and update at synthesis time. This enhancement adds meaningful resilience for long/complex reviews.

---

---

## Supplemental Review: Versioning and Ship Workflow (2026-02-28)

Three additional enhancements were identified in a follow-up review, added after the initial analysis.

---

### Enhancement 14: `/ship` Command — End-to-End Ship Workflow — **ADOPT (adapt)**

**Location**: `.claude/commands/ship.md` (new file — no equivalent in template)

**Problem solved**: Shipping was a manual multi-step process: quality gate → review → commit → branch → PR → merge → sync. Steps were skipped, version bumps forgotten, branch conventions inconsistent.

**Workflow steps**:
1. Analyze changes (categorize code/framework/config; count framework files)
2. **Version bump** — classify and run `scripts/bump_version.py`
3. Quality gate (`python scripts/quality_gate.py --fix`)
4. Review gate (run `/review` if required; stop on rejection)
5. Education gate (prompt if medium-risk or above)
6. Commit (selective staging, auto-generated commit message)
7. Branch + push + PR (`git checkout -b feature/<slug>`, `gh pr create`)
8. Merge + sync (`gh pr merge --merge`, `git checkout main && git pull`)

**Version classification rules** (embedded in Step 1.5):

| Change Type | Bump |
|---|---|
| Bug fixes, framework-only, config, docs, test-only | `--patch` |
| New files in `src/`, new features, new dependencies | `--minor` |
| Breaking changes, DB migrations, API contract changes | `--major` |

- Ambiguous between patch and minor → default to **minor**
- Major → **confirm with developer** before bumping

**Template adaptation**: Replace `dart analyze`/`flutter test`/`lib/` with `ruff check`/`pytest`/`src/`. The `gh` CLI workflow, CRITICAL BEHAVIORAL RULES, pre-flight checks, PR body template, and error recovery are directly portable.

**Generalizability**: High. **Adoption cost**: Medium.

---

### Enhancement 15: `scripts/bump_version.py` — Semantic Version Utility — **ADOPT (adapt)**

**Location**: `scripts/bump_version.py` + `scripts/test_bump_version.py` (both new)

**Design**: Reads/writes `X.Y.Z+B` from `pubspec.yaml`. Supports `--read`, `--patch`, `--minor`, `--major`, `--build`. Build number always increments. Regex-based to preserve YAML comments (`count=1` prevents double-replace). Clean `main() -> int` pattern for subprocess use.

**Test coverage** (8 tests): all bump types, comment preservation, `test_only_version_line_changed` structural invariant (exactly 1 line differs — validates the regex scope), sequential bumps, minor/major reset behavior.

**Template adaptation**:
- Target file: `pyproject.toml` instead of `pubspec.yaml`
- Version format: `version = "X.Y.Z"` (PEP 517 — no `+B` build suffix)
- Adapt `VERSION_RE` regex accordingly; drop `--build` flag
- Test fixture: swap YAML sample for a minimal `pyproject.toml` snippet
- All test patterns (tempfile + assertion + cleanup) are directly portable

**Generalizability**: High for concept and test structure. Medium for implementation (regex/format adaptation). **Adoption cost**: Low.

---

### Enhancement 16: Version Bump Belongs in `/ship`, Not Commit Protocol — **ADOPT**

**Observation**: The version bump step lives inside `/ship` Step 1.5, not in the commit protocol. This is architecturally correct — version bumps are a *ship-time* concern, not a *commit-time* concern. Local/draft commits don't advance the version; only commits going to main do.

**Content to add** in template's `CLAUDE.md`, Commit Protocol section:

```
**Version management**: Use `python scripts/bump_version.py` to bump the version in `pyproject.toml` before shipping. The `/ship` command handles this automatically as Step 1.5. Do not bump versions on local or draft commits — only on commits intended for main.
```

**Generalizability**: High. **Adoption cost**: Low.

---

## Back-Port Action Plan (Complete — Including Versioning)

### Action 10 — Create `.claude/commands/ship.md` *(new file)*
**Priority**: High | **Cost**: Medium

Port the `/ship` command, adapting toolchain references:
- `dart analyze` / `flutter test` / `dart format` → `ruff check` / `pytest` / `ruff format`
- `lib/` → `src/` throughout change categorization
- Step 1.5 version bump references `pyproject.toml` instead of `pubspec.yaml`
- `gh` CLI commands, git flow, CRITICAL BEHAVIORAL RULES, pre-flight checks, PR template, error recovery — all port verbatim

---

### Action 11 — Create `scripts/bump_version.py` + `scripts/test_bump_version.py` *(new files)*
**Priority**: High | **Cost**: Low

Adapt from agentic_journal:
- `PUBSPEC = PROJECT_ROOT / "pubspec.yaml"` → `PYPROJECT = PROJECT_ROOT / "pyproject.toml"`
- Update `VERSION_RE` for PEP 517 `version = "X.Y.Z"` format
- Drop build number suffix; drop `--build` flag
- Keep `--read`, `--patch`, `--minor`, `--major` flags and all docstrings verbatim
- Test fixture: minimal `pyproject.toml` sample; assertions use `X.Y.Z` format (no `+B`)

---

### Action 12 — Update `CLAUDE.md` — Version Management Note
**Priority**: Medium | **Cost**: Low

After the two-gate descriptions in the Commit Protocol section, add:

```
**Version management**: Use `python scripts/bump_version.py` to bump the version in `pyproject.toml` before shipping. The `/ship` command handles this automatically as Step 1.5. Do not bump versions on local or draft commits — only on commits intended for main.
```

---

## Implementation Order

1. **Actions 1–4** together — the regression prevention cluster (must be adopted as a unit)
2. **Action 5** — advisory lifecycle closes the review quality loop
3. **Action 6** — operationalizes the ledger within build checkpoints
4. **Action 7** — CLAUDE.md governance language updates
5. **Action 8** — pre-flight hardening
6. **Actions 10–12** together — the versioning/ship cluster
7. **Action 9** (optional, when time permits — session resumption for `/review`)

**Estimated total time**: 45–60 minutes for Actions 1–8 + 10–12. All changes are additive — no deletions, no structural changes to existing rules.
