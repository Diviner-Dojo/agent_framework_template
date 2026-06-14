---
review_id: REV-20260607-190709
discussion_id: DISC-20260607-190709-review-collab-loop-single-poller-lock
date: 2026-06-07
risk_level: medium
verdict: APPROVE-WITH-CHANGES (all changes applied in-session)
panel: [security-specialist, qa-specialist]
scope: scripts/collab_loop.py single-poller coordination lockfile (ntfy reply-misfiling fix)
---

# Review — collab_loop single-poller lockfile (ntfy reliability fix)

## Change under review
A structural fix for the 2026-06-07 ntfy reply-misfiling bug (regression ledger,
`scripts/collab_loop.py`): two concurrent `poll` processes on one topic with different
allow-lists caused a stale poller to validate the developer's phone reply against the
wrong question's choices and drop it. Fix: a single-poller coordination lockfile
(`.collab_loop.lock`, gitignored) — `poll` claims it with its PID and self-exits when a
newer poller takes over; each `ask` retargets the lockfile's choices so the live poller
always validates against the current question's allow-list. Files: `scripts/collab_loop.py`
(+helpers + ask/poll integration), `tests/test_collab_loop.py` (+12 tests, 3 regression),
`.gitignore`.

## Verdicts
- **security-specialist — APPROVE (0.92).** The fix preserves the always-on untrusted-reply
  allow-list invariant under concurrency (poll validates against the lockfile's current
  choices each iteration; raw unmatched text never surfaced); no topic slug in the lockfile;
  fail-open is the correct posture. 0 blocking.
- **qa-specialist — APPROVE-WITH-CHANGES (0.88).** All 3 `@pytest.mark.regression` tests fail
  under the old code and are non-tautological; fixture isolation sound. 2 quick hardening
  gaps (below), both applied in-session.

## Findings & resolution
| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| qa-F2 | Blocking* | Non-list `choices` value in a corrupt/edited lockfile untested | **Applied** — `test_lock_choices_non_list_value_falls_back` |
| qa-F3 | Medium | `write_lock` OSError fail-open path untested | **Applied** — `test_write_lock_oserror_does_not_raise` |
| qa-F1 | Advisory | `ask`→running-poller retarget is a two-test chain | Cross-ref note added |
| qa-F4 | Advisory | Keep `LOCK_PATH` call-time-resolved (not a default arg) | Maintainer comment added to the fixture |
| sec-1 | Low | Shared-workstation lock-injection (not our single-user model) | Accepted/scoped-out; documented |
| sec-2 | Low | `ask`/`claim` read-then-write race (one-ask-at-a-time → unreachable) | Accepted/scoped-out; documented |

\* "blocking" per the project's confirmed-bug-fix testing standard, not a design defect.

## Outcome
76 collab_loop tests green; quality gate 7/7. Regression ledger entry written
(`scripts/collab_loop.py`). Two security advisories carried as documented, no-action-now
items (would matter only in a shared-workstation / CI deployment). Approved to commit (no push).
