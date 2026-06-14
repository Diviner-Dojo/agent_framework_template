---
review_id: REV-20260607-170117
discussion_id: DISC-20260607-170117-review-qa-f3-f6-parse-layer-fold
pr_id: ""
risk_level: low
collaboration_mode: ensemble
exploration_intensity: light
agents_activated: [qa-specialist, architecture-consultant]
reviewed_files:
  - tests/test_dashboard_server.py
  - memory/bugs/regression-ledger.md
rounds: 1
consensus_reached: true
verdict: approve
confidence: 0.93
review_duration_minutes: 10
---

## Request Context
- **What was requested**: /review of the qa F3 + qa F6 advisory fold from REV-20260607-200447 (Phase 1 of SPEC-20260607-183136, Telemetry Layer B live dashboard daemon). Tests-only change before commit. No push.
- **Files/scope**: `tests/test_dashboard_server.py` (+286 lines: 1 import for `typing.Any`, hoisted `datetime` imports, 2 fixture helpers, 8 new test functions in two sections); `memory/bugs/regression-ledger.md` (+1 entry).
- **Developer-stated motivation**: REV-20260607-200447 advisory burndown — the recommended cohering subset per HANDOFF-supervisor-rolling. qa F3 + qa F6 both target the same file (`scripts/telemetry/dashboard_server.py`), close coverage gaps the daemon depends on, and are sized for one bounded supervised-session unit.
- **Explicit constraints**: NO push; tests-only — no production code change.

## Verdict: APPROVE (consensus, qa 0.93 + arch 0.92)

**0 BLOCKING / 2 advisory / 3 folded in-session.** Both specialists confirmed the 8 new tests cover every dispatch branch qa F3 enumerated + lock the strict-`<` boundary contract qa F6 named, with appropriate coupling depth and isolation. The in-session folds tightened the regression-marker coverage and one composite assertion.

## Specialist Verdicts

| Specialist | Model | Verdict | Confidence | Top finding |
|---|---|---|---|---|
| qa-specialist | sonnet | APPROVE | 0.93 | F1 (low): 3 of the 6 F3 tests lacked `@pytest.mark.regression` despite naming concrete failure modes — a `pytest -m regression` sweep would miss them. **(FIXED pre-commit)** |
| architecture-consultant | sonnet | APPROVE | 0.92 | None. The new tests respect the A-ARCH1 public-surface contract (consume `itu.parse_timestamp` / `itu.coerce_int` only indirectly through the parsers); test/source coupling is at the right depth (parser dispatch contract, not internal data structures); OSError seam at the I/O boundary not in try/except internals. |

## Pre-commit Fixes Applied (3)

1. **`@pytest.mark.regression` added** to `test_parse_main_session_ignores_non_dict_content_items`, `test_parse_subagent_produces_message_event_on_agent_lane`, `test_parse_main_session_returns_empty_on_oserror`, and `test_parse_subagent_returns_empty_on_oserror` — qa F1. All 8 new tests now carry the marker; a `pytest -m regression` sweep covers every named branch.
2. **`agent_type is None` assertion** added to `test_parse_main_session_ignores_non_dict_content_items` — qa F2. Pins the empty-`input` branch: when `input.subagent_type` is absent, `agent_type` must be `None` (not an empty string), so a future change that flipped the `or None` default would not slip through. The composite test now covers both the non-dict-items guard AND the empty-input default in one shot, with the docstring updated to name both contracts.
3. **`from datetime import UTC, datetime, timedelta`** hoisted to module-level — qa P1. The two F6 boundary tests previously imported `datetime` inside the function body, inconsistent with the rest of the file (where the helpers and existing tests use the module-level import). Aligns style and removes a needless local-import scope.

Quality gate after fixes: **7/7** (233 telemetry+server tests pass; ledger 30 guards; ruff format + check clean).

## Required Changes (none — all fixes applied pre-commit)

## Advisory Findings — track in BUILD_STATUS

None. Both specialists returned no follow-up advisories beyond what was folded in-session.

## Strengths (consensus)

- **Coverage accuracy**: all 6 F3 dispatch branches covered individually (tool_use Agent → dispatch; tool_result → result; non-dict items in content; OSError on main; subagent message path; OSError on subagent), plus the per-line `since` filter as the F6 boundary contract. No missed branch.
- **Boundary contract locked at both parsers**: the parametrized `(-1, False), (0, True), (+1, True)` triple is the minimal correct set to pin `<` vs `<=`; the paired three-line subagent test ensures a future divergence (one strict, one inclusive) fails both at once. The docstring at the subagent test explicitly names this intent.
- **OSError seam at the I/O boundary, not implementation internals**: monkeypatching `Path.read_text` rather than reaching into try/except branches means a future refactor that swaps `Path.read_text` for `aiofiles` or a streaming reader needs to update the seam — the correct architectural signal.
- **Public-surface contract preserved**: tests use the public A-ARCH1 names indirectly via the parsers; the existing `test_server_uses_a_arch1_public_helpers_not_underscored` guard at lines 624-648 continues to enforce the contract for production source; no re-coupling to underscored privates.
- **Fixture helpers `_ts` / `_write_main_jsonl`** are correctly file-scoped (4 call sites — no premature promotion to a shared fixtures module); their use keeps the tests readable.
- **Ledger entry**: root cause class (Missing Null/Empty Case) fits both findings; all 8 test function names enumerated; canary language explains the failure modes; does not weaken any existing guard.

## Education Gate

**Recommendation**: skip walkthrough/quiz for this change. The conceptual unit is the same parser code the Phase 1 build already taught against — these are coverage-completing tests, not a new concept. The gatekeeper-mastery story is already met by the Phase 1 education gate.
