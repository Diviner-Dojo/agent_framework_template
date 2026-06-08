---
review_id: REV-20260608-014202
date: 2026-06-08
branch: fix/c-gate-log-integrity
scope: tests-only (src/telemetry/dashboard.py qa F1 live-renderer direct tests fold)
specialists:
  - qa-specialist
  - architecture-consultant
mode: ensemble
verdict: APPROVE-WITH-CHANGES → APPROVE post-fold
folded_in_session: 3
deferred_as_advisory: 4
---

# REV-20260608-014202 — qa F1 live-renderer direct tests fold (REV-20260607-200447 → session 10i)

## Synthesis

Both specialists converged on **APPROVE-WITH-CHANGES** for the 23-test (24 post-fold)
direct-renderer fold; **APPROVE post-fold** after the three in-session
improvements below. The qa-specialist hit two precision findings (one assertion
that pinned the raw constant when it should have pinned the human-facing label;
one missing fallback-branch test); the architecture-consultant hit one
surface-choice rationale finding (the private-renderer import boundary deserves
an inline comment so a future contributor reads the intent, not just the
import). All three are cohering small additions to the same new test section,
folded together without touching production code.

## Findings

### qa-specialist findings (REV-20260608-013905, 0.88)

- **qa F1 MED — Weak badge assertion pinned raw constant, not label contract** (FOLDED in-session)
  - Surface: `tests/test_telemetry.py::test_render_agent_lane_row_emits_status_class_and_badge_label`
  - Root cause: the parametrize used `f'<span class="lane-badge">{status}</span>'` with `status` being the raw constant (`LANE_ORPHANED = "orphaned"`). The `_LANE_STATUS_LABEL` map exists precisely so the constant + the human label can diverge; an f-string-interpolated assertion would silently flip its expectation under a future constant rename.
  - Fold: added `expected_badge_text` literal to the parametrize table; the assertion now pins the literal label.
- **qa F2 MED — Unknown lane status fallback branch had no direct test** (FOLDED in-session)
  - Surface: `src/telemetry/dashboard.py::_render_agent_lane_row` line 788 (`_LANE_STATUS_LABEL.get(lane.status, lane.status)`)
  - Root cause: a future `live.py` extension adding a new status (e.g. `"pending"`) before the dashboard map is updated would take the fallback path silently; no test covered it.
  - Fold: added `test_render_agent_lane_row_unknown_status_falls_back_to_raw_constant` (24 tests total now). The test ALSO guards against a regression that switched to `_LANE_STATUS_LABEL[lane.status]` (which would raise `KeyError`).
- **qa F3 LOW — RUNWAY_OK raw-constant negative guard skipped** (DEFERRED-AS-ADVISORY)
  - Low risk: `"ok"` vs `"OK"` divergence is already caught by the positive `&middot; OK` assertion in the parametrize.
- **qa F4 LOW — `<strong>42</strong>` is intentional markup pinning** (DEFERRED-AS-ADVISORY)
  - No action needed unless there is concrete intent to allow CSS-only weight rewrites; the docstring justification stands.
- **qa F5 INFO — Composition test does not assert single-section count** (DEFERRED-AS-ADVISORY)
  - Empty-state test already pins `count('<section id="live-section"') == 1`; the populated-state test's risk is negligible.
- **qa F6 INFO — Ledger entry quality** (NO ACTION)
  - The session-10i ledger entry is crisp + complete.

### architecture-consultant findings (REV-20260608-013849, 0.82)

- **arch F1 MED — Test surface imports 5 PRIVATE renderers across module boundary** (FOLDED in-session)
  - Surface: `tests/test_telemetry.py` new section header
  - Root cause: the FRICTION-5 fold's "route through public `render_live_fragment`" choice and this fold's "route around the public seam" choice are answering different questions — both legitimate, but the rationale lives only in this review report unless captured inline.
  - Fold: added a "Surface-choice tradeoff" comment block at the top of the new test section naming the FRICTION-5/this-fold tradeoff and the Rule-of-Three rationale for keeping the symbols private.
- **arch F2 LOW INFO — Fold-renderer seam covered only at composition boundary** (DEFERRED-AS-ADVISORY)
  - Observation, not action; a Phase 2 field addition could silently slip past both sides — flag for the Phase 2 build to add seam coverage.
- **arch F3 LOW INFO — Phase 2 prerequisite alignment** (NO ACTION)
  - Tests pin current contracts without boxing in Phase 2 or arch F2 (event-source seam); door correctly open.
- **arch F4 INFO — Regression-ledger classification** (NO ACTION)
  - "Missing Null/Empty Case" is defensible; ~7 tests skew toward Trust Boundary Gap (XSS) or Schema/Serialization Drift (ordering / class emission), but the ledger never demanded perfect partition.
- **arch F5 INFO — `_lane` helper placement** (NO ACTION)
  - Module-local is correct (one caller file, leading underscore, no fixture promotion); aligned with Rule of Three.

## Convergence note

The two specialists hit **complementary surfaces** rather than the same one:
qa landed on assertion precision (test-internal contract correctness);
arch landed on surface-choice rationale (test-vs-source coupling intent).
The three folded changes cohere on the same section header + parametrize
table + new test — one in-session sweep closes both reviewers' MED findings
without touching the new section structure or any production code.

The qa-specialist's F1+F2 fold is **strictly stronger than the original**: the
parametrize table now pins (status constant, CSS class, label literal) as
three independent dimensions, and the new fallback test pins the forward-compat
path the original 23 tests left unguarded. The arch-consultant's F1 fold gives
the section header a tradeoff comment future readers can act on without
re-deriving the design context from this review.

## Post-fold state

- 24 `@pytest.mark.regression` tests covering each sub-renderer + composition,
  plus the `_lane` helper.
- Quality gate 7/7 (265 telemetry+server tests; ledger 35 guards; ruff format +
  check clean).
- 4 LOW/INFO advisories deferred (qa F3, qa F4, qa F5, arch F2 — none blocking;
  arch F2 flagged for Phase 2 build attention).

## Verdict

**APPROVE post-fold.** Both specialists' MED findings closed in-session.
Ready to commit on `fix/c-gate-log-integrity`. NO push.

## REV-20260607-200447 burndown

After this fold: 2 → **1 remaining** (arch F2 event-source seam, the recommended
Phase 2 prerequisite). qa F1 closed this session.
