---
review_id: REV-20260607-225506
discussion_id: DISC-20260607-225506-review-session-supervisor
date: 2026-06-07
risk_level: medium
verdict: APPROVE-WITH-CHANGES (all changes applied in-session)
panel: [security-specialist]
scope: scripts/session_supervisor.py — autonomous multi-session supervisor (ADR-0018 v2)
---

# Review — session supervisor (autonomous continuation, ADR-0018 v2)

## Change under review
A NEW external supervisor (`scripts/session_supervisor.py`) that chains fresh headless
`claude -p` sessions via a rolling handoff file, replacing ADR-0018's in-session
`subprocess.Popen` self-spawn — which **wedged** (a headless run with no permission flag
hangs on the first tool-permission request; root cause verified 2026-06-07 against CLI
v2.1.143). The fix, also verified by a live de-risk run (`--permission-mode
bypassPermissions` ran a real `Bash` tool, `permission_denials:[]`, exit 0), is the correct
headless flags + an *external* supervisor (a dying session cannot reliably spawn its own
successor). Files: `scripts/session_supervisor.py`, `tests/test_session_supervisor.py`
(30 tests).

## Panel
- **security-specialist — APPROVE-WITH-CHANGES (0.91).** 0 blocking. Verified: `shell=False`
  (no shell injection), fail-closed unknown-sentinel-stop, bounded caps (no runaway), and
  crucially that **`bypassPermissions` does NOT bypass PreToolUse hooks** — so the project's
  `pre-push-main-blocker` / settings.json validator / `pre-commit-gate` still enforce
  no-push / no-settings-edit / review-before-commit on every spawned session.
- qa dimension covered by the test suite (every loop outcome + pure seam via an injected
  runner; no real subprocess in tests) and the green quality gate.

## Findings & resolution (all applied in-session)
| # | Sev | Finding | Resolution |
|---|-----|---------|------------|
| sec-1 | Medium | `bypassPermissions` leaves destructive local `Bash` (`rm -rf`, `git reset --hard`, `git clean`) unguarded → irreversible loss of *uncommitted* work | **Clean-git-tree preflight** (`_is_clean_tree` → `dirty-tree` abort) + `--allow-dirty` escape hatch, so committed state always survives and `git checkout -- .` restores the rest |
| sec-2 | Low | `build_prompt` path interpolation could spoof DONE/ROLL via a newline in the path | **Control-char guard** raises `ValueError` |
| sec-3 | Low | progress-log write failure swallowed silently (loses the monitorability trail) | now **warns on stderr** |
| sec-4 | Low | result snippet (≤120 chars) written to the gitignored progress log | **documented** |

## Safety posture (recorded)
`bypassPermissions` is a real grant (auto-approves tool use so headless runs don't hang).
The defense-in-depth that makes it acceptable for developer-invoked, feature-branch use:
(1) the framework's PreToolUse hooks still fire (no push, no settings edit, quality-gate +
review enforced at commit); (2) the clean-tree preflight makes the run recoverable; (3)
hard caps on sessions / budget / per-session timeout / turns; (4) fail-closed unknown-stop.
Residual risk: destructive local Bash on a *clean* tree could still discard the latest
work — mitigated by committing per phase. Run on a feature branch (never `main`).

## Outcome
30 tests green; quality gate 7/7. Regression-ledger entry added. ADR-0018 amended to record
the wedge root cause + the supervisor-v2 architecture. Approved to commit (no push), then
launch on the session-9 handoff as the live acceptance test.
