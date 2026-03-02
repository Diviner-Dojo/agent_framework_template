---
discussion_id: DISC-20260302-031919-review-emulator-testing-and-app-fixes
started: 2026-03-02T03:22:43.851109+00:00
ended: 2026-03-02T03:26:32.071046+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, qa-specialist]
total_turns: 7
---

# Discussion: DISC-20260302-031919-review-emulator-testing-and-app-fixes

## Turn 1 — qa-specialist (proposal)
*2026-03-02T03:22:43.851109+00:00 | confidence: 0.87*
*tags: review, qa*

## QA Specialist Review (confidence: 0.87)

### Findings (9 total: 1 high, 5 medium, 3 low)

**HIGH: Missing regression test for ref.watch→ref.read bug fix (app.dart:182)**
The ref.watch→ref.read fix is a confirmed bug fix that requires a regression test tagged @Tags(['regression']) per testing_requirements.md. No such test exists. Also missing from regression-ledger.md.

**MEDIUM: Missing test for getOrCreateTaskList network failure fallthrough (google_tasks_service.dart:96-110)**
tasklists.list() throwing non-API exception causes silent fallthrough to create. No test covers this path.

**MEDIUM: Missing test for getOrCreateTaskList non-404 API error rethrow (google_tasks_service.dart:85-92)**
No test verifies that non-404 DetailedApiRequestError from cached list verification is rethrown.

**MEDIUM: Weak auth screen assertion in smoke_test (smoke_test.dart:396-413)**
Auth failure polling times out silently. Only asserts form is visible, not that error was received.

**MEDIUM: FAB fallback dual-execution risk in manual_test (manual_test_automation.dart:466-484)**
onPressed?.call() fallback could fire even if primary tap partially registered. warnIfMissed:false suppresses the signal.

**MEDIUM: Missing test for createTask without taskListId (google_tasks_service.dart:131-165)**
No test covers the delegation path when taskListId is omitted.

**LOW: _clear_app_data silently swallows failures (test_on_emulator.py:72-87)**
**LOW: _boot_emulator reuses first running emulator regardless of AVD name (deploy.py:217-221)**
**LOW: platformDispatcher.onError never restored (smoke_test.dart:33-39)**

### Strengths
- GoogleTasksService.forTesting constructor is clean testability seam
- safePump() pattern correctly drains build-phase errors
- goHome() FAB+title check prevents false positives through stacked routes
- scrollToFind/scrollUpToFind handle StateError from Scrollable disappearing
- Diagnostic text dumps on assertion failure aid debugging

---

## Turn 2 — architecture-consultant (proposal)
*2026-03-02T03:22:58.898985+00:00 | confidence: 0.87*
*tags: review, architecture*

## Architecture Consultant Review (confidence: 0.87)

### Findings (4 total: 0 high, 1 medium, 3 low)

**MEDIUM: Pattern inconsistency between Google service constructors (google_tasks_service.dart:59-69)**
GoogleTasksService uses private constructor + forTesting named constructor. GoogleCalendarService uses callable injection. Both file headers claim 'Pattern: Injectable callable (matches GoogleCalendarService)' but implementations differ structurally. Should align before a third Google service is added. Not a blocker — ADR-0020 governs, no violation.

**LOW: Private-symbol coupling between scripts (test_on_emulator.py:28-35)**
test_on_emulator.py imports underscore-prefixed functions from deploy.py (_boot_emulator, _find_adb_exe, etc.). If deploy.py refactors these, test_on_emulator.py breaks. Consider extracting shared helpers to scripts/android_device.py.

**LOW: Provider documentation drift (app.dart:182 vs onboarding_providers.dart)**
onboarding_providers.dart doc comment illustrates ref.watch as the example usage pattern. The ref.read exception in app.dart for initialRoute is undocumented there. Future developer could revert to watch.

**LOW: Missing ADR for emulator testing infrastructure**
Two-tier integration test approach (smoke + manual), JSONL test logging, exit code contract, --clean flag represent meaningful test architecture decisions with no ADR. Not a blocker for this change.

### Strengths
- ref.read fix is architecturally sound for initialRoute use case
- GoogleTasksService forTesting constructor is low-ceremony testability seam
- Emulator discovery is robustly layered (local.properties → env → defaults → PATH)
- --emulator implying --debug is architecturally correct (release AOT targets ARM)
- Integration test helper patterns are internally consistent

---

## Turn 3 — docs-knowledge (proposal)
*2026-03-02T03:23:16.320751+00:00 | confidence: 0.87*
*tags: review, docs*

## Docs-Knowledge Review (confidence: 0.87)

### Findings (6 total: 2 high, 2 medium, 2 low)

**HIGH: Missing ADR for ref.watch→ref.read constraint (app.dart:182)**
The rule 'never watch a provider whose value drives initialRoute' is a generalized Flutter/Riverpod principle with lasting consequences. ADR-quality reasoning is embedded in test file comments. Propose ADR-0029: Riverpod Provider Watching Constraints in MaterialApp Build.

**HIGH: Missing ADR for emulator testing infrastructure (deploy.py, test_on_emulator.py)**
Establishes new testing pathway with x86_64 constraints, debug-mode implication, JSONL logging, two-tier test architecture. CLAUDE.md scripts/ description is now incomplete ('capture pipeline utilities' doesn't cover deploy/test tools).

**MEDIUM: Integration test helper duplication undocumented (smoke_test vs manual_test_automation)**
safePump, scrollToFind, scrollUpToFind, goHome are duplicated without documented rationale. goHome implementations differ between files (FAB check only in manual). Should add inline comments explaining why not shared.

**MEDIUM: Missing regression ledger entry (memory/bugs/regression-ledger.md)**
ref.watch→ref.read bug fix has no entry in the regression ledger per commit protocol Step 1.5.

**LOW: CLAUDE.md scripts/ directory description needs update**
Should read: 'Capture pipeline utilities + quality gate + developer workflow tools (deploy.py, test_on_emulator.py, bump_version.py)'

**LOW: GoogleTasksService forTesting constructor missing ADR-0007 citation in file header**

### CLAUDE.md Update Proposals
1. Update scripts/ directory description
2. Add Riverpod watching constraint note after ADR-0029
3. Add Integration Testing section referencing test files and emulator runner

### Strengths
- app.dart inline comment is exemplary 'why' documentation
- manual_test_automation.dart Coverage Map header is outstanding practice
- test_on_emulator.py module-level docstring with usage examples and exit codes
- deploy.py references memory/lessons/deploy-safety.md

---

## Turn 4 — facilitator (synthesis)
*2026-03-02T03:23:29.666086+00:00 | confidence: 0.87*
*tags: blocking:2, advisory:11*

## Review Synthesis: DISC-20260302-031919-review-emulator-testing-and-app-fixes

### Verdict: approve-with-changes

### Blocking Findings (2)
1. **Missing regression test + ledger entry for ref.watch→ref.read bug** (QA + docs-knowledge). The fix is correct but per commit protocol and testing requirements, a regression test tagged @Tags(['regression']) and a regression-ledger.md entry are required before merge.

2. **Missing ADR for the ref.watch→ref.read constraint** (docs-knowledge + architecture). This is a generalized Riverpod principle affecting MaterialApp.initialRoute that drives test architecture patterns. Without an ADR, a future developer could revert to ref.watch.

### Advisory Findings (11)
3. Missing test: getOrCreateTaskList network failure fallthrough (QA, medium)
4. Missing test: getOrCreateTaskList non-404 API error rethrow (QA, medium)
5. Weak auth assertion in smoke_test — only checks form visible, not error received (QA, medium)
6. FAB fallback dual-execution risk with warnIfMissed:false (QA, medium)
7. Missing test: createTask without taskListId (QA, medium)
8. Pattern inconsistency between Google service constructors (arch, medium)
9. Integration test helper duplication undocumented (docs, medium)
10. Missing ADR for emulator testing infrastructure (docs/arch, low)
11. Private-symbol coupling between deploy.py and test_on_emulator.py (arch, low)
12. CLAUDE.md scripts/ description needs update (docs, low)
13. platformDispatcher.onError never restored in tests (QA, low)

---

## Turn 5 — qa-specialist (reflection)
*2026-03-02T03:26:21.830571+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Did not verify whether platformDispatcher.onError teardown could cause cross-test pollution. Inferred missing-test findings from structure rather than exhaustive test file reads.

## Candidate Improvement Rule
When a file has an existing test file, read both source and test completely before classifying missing-test findings.

## Confidence Calibration
Original: 0.87, Revised: 0.82, Delta: -0.05

---

## Turn 6 — architecture-consultant (reflection)
*2026-03-02T03:26:27.295689+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Did not check existing ADR index before concluding new ADR needed. Did not flag integration test helper duplication as concrete coupling concern (fix in one file silently leaves other broken).

## Candidate Improvement Rule
Check existing ADRs before raising a missing-ADR finding. Propose addendum or update rather than new ADR if coverage already exists.

## Confidence Calibration
Original: 0.87, Revised: 0.82, Delta: -0.05

---

## Turn 7 — docs-knowledge (reflection)
*2026-03-02T03:26:32.071046+00:00 | confidence: 0.8*
*tags: reflection*

## What I Missed
Under-weighted emulator ADR — treated tooling decision as lower-priority than code decision when it meets same criteria (lasting workflow consequences). Uniform 0.87 across agents signals insufficient independent calibration.

## Candidate Improvement Rule
ADR-blocking test: An ADR is required (blocking) when a decision introduces a new workflow pathway, establishes non-obvious constraints, or would be expensive to reverse after team adoption. Tooling decisions are not categorically lower priority.

## Confidence Calibration
Original: 0.87, Revised: 0.82, Delta: -0.05

---
