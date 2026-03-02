---
plan_id: IMPROVEMENT-PLAN-20260301
date: 2026-03-01
basis: ASSESSMENT-20260301-framework-effectiveness
priority: quality-signal-reliability-first
enforcement: mixed (block critical, warn non-critical)
status: draft
---

# Framework Improvement Roadmap (Reliability-First)

## Context

This plan addresses the gaps identified in the [framework effectiveness review](framework-effectiveness-review-20260301.md) (design score 8.6/10, execution score 6.1/10). The primary goal is to close known governance gaps and raise execution quality to match the strong design foundation. Prioritization favors quality-signal reliability first, with mixed enforcement: critical checks block immediately, non-critical checks warn and log for the first iteration.

### External Best Practices Referenced

- [Google Engineering Practices: Code Review](https://google.github.io/eng-practices/review/) — reviewer standards, speed, and quality expectations
- [Google Engineering Practices: The Standard of Code Review](https://google.github.io/eng-practices/review/reviewer/standard.html) — review scope and approval criteria
- [GitHub Docs: About Protected Branches](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) — CI-enforced branch policy patterns
- [DORA: Continuous Integration](https://dora.dev/devops-capabilities/technical/continuous-integration) — integration frequency and automation practices
- [DORA: Working in Small Batches](https://dora.dev/devops-capabilities/process/working-in-small-batches) — batch size and feedback loop speed
- [Google SRE Book: Embracing Risk / Error Budgets](https://sre.google/sre-book/embracing-risk/) — error budget framing for quality thresholds

## Phase 1: Critical Signal Hardening (1–2 weeks)

### 1.1 Review-to-Change Coverage Validation (BLOCKING)

**Problem:** The quality gate verifies that a review report exists for today, not that it covers the specific files being committed. This is a known loophole documented in `CLAUDE.md`.

**Changes:**
- `scripts/quality_gate.py` — extend the reviews check to compare staged/changed file paths against the file list in the most recent REV report's scope section
- `.claude/rules/commit_protocol.md` — update Step 2 to document the file-matching requirement
- `.claude/commands/review.md` — ensure the review command emits a machine-readable file list in the report frontmatter (e.g., `files_reviewed: [...]`)
- `.claude/commands/ship.md` — align ship workflow to use the same file-matching validation

**Enforcement:** blocking — commit rejected if changed files are not covered by a matching review.

**Success metric:** 100% of changed-code commits have review coverage match within 4 weeks.

**Trade-off:** Slightly more false blocks on edge cases (e.g., config-only files staged alongside reviewed code). Mitigate with explicit exempt file patterns.

---

### 1.2 Structured Skip/Bypass Reason Capture (WARN/LOG)

**Problem:** Quality gate skip flags (`--skip-reviews`, `--skip-coverage`, etc.) and `--no-verify` bypasses leave no structured trace, making it impossible to audit gate reliability or distinguish legitimate exemptions from process erosion.

**Changes:**
- `scripts/quality_gate.py` — when any `--skip-*` flag is used, require a `--reason` parameter; append the reason as a field in the JSONL record written to `metrics/quality_gate_log.jsonl`
- `.claude/hooks/pre-commit-gate.sh` — surface bypass reason requirement in the pre-commit hook guidance message
- `.claude/rules/commit_protocol.md` — document the reason requirement for all skip/bypass paths

**Enforcement:** warn/log — skip still works but emits a warning if no reason is provided and logs the gap.

**Success metric:** >90% of skip events include a structured reason within 4 weeks. Retros can query bypass patterns.

---

### 1.3 Standardized Build Checkpoint Summary (BLOCKING)

**Problem:** Only 8 of 11 build discussions include an explicit build-complete synthesis line with checkpoint counts. This makes cross-build comparison and incident tracing inconsistent.

**Changes:**
- `.claude/commands/build_module.md` — define a mandatory build summary payload with required fields: `fired`, `bypassed`, `revise`, `round2`, `unresolved`
- `scripts/write_event.py` — add optional structured payload fields for build-summary events (intent: `synthesis`, tags: `build-complete`)
- `scripts/ingest_events.py` — validate that build discussions contain exactly one build-summary event with the required fields at close time; warn if missing
- `.claude/rules/build_review_protocol.md` — add the summary block requirement to the Capture section

**Enforcement:** blocking on build discussion closure — facilitator cannot close without the summary event.

**Success metric:** 100% of build discussions include the standardized summary block.

---

### 1.4 Advisory Lifecycle Enforcement (WARN/LOG)

**Problem:** Only 7 of 27 REV reports include an Open Advisories section. Advisory carry-forward is inconsistent, allowing silent debt accumulation across phases.

**Changes:**
- `docs/templates/review-report-template.md` — add mandatory `## Open Advisories` section with carry-forward delta format (new / resolved / remaining)
- `.claude/rules/review_gates.md` — add advisory lifecycle requirement: every REV must include open-advisory tally from prior reviews, with disposition (resolved, carried, accepted-as-limitation)
- `.claude/commands/review.md` — update synthesis instructions to require advisory carry-forward lookup from the most recent prior REV report

**Enforcement:** warn/log initially — facilitator is prompted but not blocked. Escalate to blocking after 2-week stabilization if adoption is strong.

**Success metric:** 100% of REV reports include open-advisory section within 4 weeks.

---

## Phase 2: Observability and Metrics (2–4 weeks)

### 2.1 Checkpoint Value Observability

**Problem:** The `protocol_yield` table records blocking/advisory findings but not REVISE-resolved rounds. Checkpoint value from iterative improvement is undercounted, creating removal pressure.

**Changes:**
- `scripts/init_db.py` — add `revise_resolved` and `checkpoint_cycle_time_seconds` columns to the `protocol_yield` table (or a new `checkpoint_detail` table)
- `scripts/record_yield.py` — capture REVISE-resolved counts and time between REVISE dispatch and APPROVE response
- `.claude/commands/meta-review.md` — include checkpoint value trend in meta-review template (fired vs bypassed vs revise-resolved ratio over time)
- `.claude/commands/retro.md` — add checkpoint ROI section to retro template

**Enforcement:** N/A (observability, not enforcement).

**Success metric:** Checkpoint ROI data available in retro/meta-review outputs within one sprint cycle.

**Trade-off:** Requires migration and optional backfill of existing discussions (pre-migration data will have NULLs).

---

### 2.2 Outcome Metrics Layer

**Problem:** The framework measures process compliance (discussions, turns, ADRs) but not outcomes (defect escape, lead time, overhead budget). This makes it hard to assess whether rigor produces proportional quality.

**Changes:**
- Add outcome tracking conventions to retro and meta-review workflows:
  - **Defect escape rate**: post-merge defects found per phase (manual log in retro)
  - **Gate pass trend**: 7-day rolling pass rate computed from `metrics/quality_gate_log.jsonl`
  - **Protocol overhead ratio**: framework minutes vs product minutes per sprint (tracked in retro effort analysis)
  - **Risk-tier staffing calibration**: agents deployed vs risk level per discussion (meta-review)
- `scripts/quality_gate.py` — add a `--trend` flag that prints recent pass/fail trend summary
- `.claude/commands/retro.md` — add Outcome Metrics section to retro template
- `.claude/commands/meta-review.md` — add staffing calibration analysis requirement

**Enforcement:** N/A (reporting).

**Success metric:** Monthly trend data available for all four outcome metrics within 6 weeks.

---

### 2.3 Policy Drift Detection

**Problem:** Rule files can drift from actual hook/command/script behavior (example: early ruff/pytest references in Dart project rules). No automated check detects this.

**Changes:**
- `scripts/quality_gate.py` — add a `policy-drift` check that scans `.claude/rules/*.md` for known stale patterns (configurable pattern list) and cross-references hook/command files for consistency
- `.claude/commands/retro.md` — include policy-drift findings in retro template
- `.claude/rules/documentation_policy.md` — document policy-drift check as part of framework maintenance

**Enforcement:** warn/log — findings reported but not blocking. Escalate to blocking if drift findings persist across 2+ retros.

**Success metric:** Zero stale-policy findings per sprint retro.

**Trade-off:** Requires maintenance of a pattern list (low effort, high signal).

---

## Phase 3: Structural Calibration (1–2 months)

### 3.1 Differential Coverage Policy

**Problem:** Coverage check fails 66 of 130 quality-gate runs (51%). The global 80% threshold creates repeated failures for additive features, while critical write paths may lack coverage without triggering a separate signal.

**Changes:**
- `.claude/rules/testing_requirements.md` — define a two-tier coverage model:
  - **Global floor**: 75% (reduced from 80% to reflect additive-feature reality)
  - **Critical path requirement**: 100% for new/modified write paths (DAOs, state notifiers, API clients)
- `.claude/rules/review_gates.md` — update coverage threshold language to reference the two-tier model
- `scripts/quality_gate.py` — implement differential coverage check: compare per-file coverage for changed files against the critical-path threshold, and global coverage against the floor
- `.claude/commands/build_module.md` — add per-task coverage delta reporting (optional warn)

**Enforcement:** mixed — global floor is blocking; critical-path check is blocking for write paths, warn for others.

**Success metric:** Coverage-check failure frequency drops by >50% while critical write-path coverage is at 100%.

**Trade-off:** Higher implementation complexity. Requires file-level coverage parsing from `lcov.info`.

---

### 3.2 Risk-Tier Agent Staffing Calibration

**Problem:** Meta-review found low-risk discussions averaged more agents (5.4) than medium-risk (3.8). Over-staffing low-risk work increases overhead without proportional quality gain.

**Changes:**
- `.claude/rules/review_gates.md` — tighten agent-count guidance per risk tier:
  - Low: **2** (mandatory qa-specialist + 1 domain)
  - Medium: **3** (mandatory qa-specialist, architecture-consultant + 1 domain)
  - High: **4** (existing policy)
  - Critical: **5–6** (existing policy)
- `.claude/commands/review.md` — update facilitator instructions to enforce tier-to-count mapping before dispatching agents
- `.claude/commands/meta-review.md` — add risk-to-agent-count correlation check as a standing meta-review finding category

**Enforcement:** warn/log — facilitator is guided but can override with documented reason.

**Success metric:** Low-risk discussions average ≤3 agents; medium-risk average ≤4 agents within one phase.

**Trade-off:** May miss edge cases where low-risk work touches multiple domains. Mitigate with documented override path.

---

### 3.3 CI Branch Protection (Optional)

**Problem:** All current enforcement is social (hook-based, agent-prompted). No structural barrier prevents `--no-verify` commits or direct pushes to main.

**Changes:**
- Add `.github/workflows/quality-gate.yml` — CI workflow that runs `python scripts/quality_gate.py` on PR branches
- Configure GitHub branch protection rules for `main`: require passing CI checks, require at least one review artifact
- `.claude/commands/ship.md` — update ship workflow to reference CI status check
- `docs/releases/` — document the branch protection policy

**Enforcement:** blocking at repository level (once enabled).

**Success metric:** 0 direct merges to main without passing required checks.

**Trade-off:** Slower merges for solo high-velocity bursts. Not recommended until Phase 1 + 2 are stable.

---

## Sequencing and Dependencies

```
Phase 1 (weeks 1–2)
├── 1.1 Review-to-change coverage (BLOCKING)
├── 1.2 Skip/bypass reason capture (WARN)
├── 1.3 Checkpoint summary standard (BLOCKING)
└── 1.4 Advisory lifecycle (WARN → BLOCKING)

Phase 2 (weeks 3–4)
├── 2.1 Checkpoint value metrics ← depends on 1.3 summary format
├── 2.2 Outcome metrics layer
└── 2.3 Policy drift detection

Phase 3 (weeks 5–8)
├── 3.1 Differential coverage ← depends on 2.2 trend data
├── 3.2 Agent staffing calibration ← depends on 2.2 meta-review data
└── 3.3 CI branch protection (optional) ← depends on Phase 1+2 stability
```

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Phase 1 blocking checks create friction during urgent fixes | Medium | Medium | Allow `--emergency` flag with mandatory post-hoc review within 24h |
| Differential coverage parsing is fragile across Flutter versions | Low | High | Pin lcov format expectations; add integration test for parser |
| Advisory carry-forward becomes mechanical checkbox | Medium | Low | Retro reviews advisory quality, not just presence |
| Overhead tracking creates meta-overhead | Low | Low | Keep tracking lightweight (single line in retro effort section) |

## Success Criteria (Overall)

After full Phase 1 + 2 implementation:
- Quality-gate 4-week rolling pass rate improves from 40% to >70%
- 100% of REV reports include open-advisory carry-forward
- 100% of build discussions include standardized checkpoint summary
- Checkpoint ROI data available in retro outputs
- Monthly outcome metrics (defect escape, overhead ratio) tracked and trended

After Phase 3:
- Coverage-check failure frequency drops by >50%
- Low-risk discussions average ≤3 agents
- Framework-to-product time ratio tracked and within target band
