---
discussion_id: DISC-20260525-170042-notify-hooks-quality-gate-review
started: 2026-05-25T17:01:01.361026+00:00
ended: 2026-05-25T17:04:59.197869+00:00
agents: [facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260525-170042-notify-hooks-quality-gate-review

## Turn 1 — facilitator (evidence)
*2026-05-25T17:01:01.361026+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Replicate the agentic_journal push-notification methodology into the framework template, harvesting the methodology without downgrading the template's better implementations. Workstream 1 (this change): task-boundary notification hooks. The deferred watcher is captured as a type:vision doc, not built.
- **Files/scope**: scripts/quality_gate.py (new opt-in --notify flag + _notify_outcome helper), tests/test_quality_gate.py (new, 6 tests), .claude/skills/notifying-the-developer/SKILL.md (new Task-Boundary Hooks section), docs/sprints/SPEC-20260525-160115-generalized-watcher-daemon-vision.md (vision, context only).
- **Developer-stated motivation**: Framework should benefit from the derived project's methodology, but not at the expense of its own where the template's version is better.
- **Explicit constraints**: notify text must be confidentiality-safe (ntfy.sh is a public relay); the hook must never break the gate (never-crash-caller); silent no-op when NTFY_TOPIC unset; opt-in so the pre-commit hook stays silent.

---

## Turn 2 — qa-specialist (proposal)
*2026-05-25T17:04:10.701825+00:00 | confidence: 0.88*
*tags: qa, testing, blocking:1, advisory:2*

QA review of _notify_outcome + tests. Branch coverage ~95%. Verdict: approve-with-changes (confidence 0.88).

BLOCKING:
- F1 (Rule 15, weak assertion) tests/test_quality_gate.py test_pass_fires_success: 'kwargs.get("priority") != "high"' passes vacuously because the success call passes no priority kwarg (get returns None, None != high is always True). Would not catch a regression adding priority=low/max. Fix: assert 'priority' not in kwargs.

ADVISORY:
- F2 (Low): ImportError path (notify.py absent from sys.path) is swallowed by except Exception but untested; this is the load-bearing never-crash path so deserves coverage.
- F3 (Low): total=0 (all checks skipped) reaches 'passed==total' branch -> success ping 'All 0 checks passed.' Acceptable-but-ambiguous; document in docstring or add a test.

NON-FINDINGS (verified clean): 'except Exception:' is NOT bare-except (excludes BaseException) so does not violate coding standard; args.notify always defined (store_true before parse_args); @patch('notify.send_notification') target is mechanically correct (deferred import resolves at call time). Rule 14 mirror-structure exemption correctly applied (scripts/ file, no src/ counterpart).

STRENGTHS: never-crash contract verified directly with a raising mock; confidentiality is a first-class test; setup_error asserts on title; substantive docstring (Rule 1 satisfied).

---

## Turn 3 — security-specialist (proposal)
*2026-05-25T17:04:22.308650+00:00 | confidence: 0.95*
*tags: security, confidentiality, advisory:2*

Security review of the notification egress. Verdict: approve (confidence 0.95). Zero blocking findings.

ADVISORY:
- F1 (Low/informational, OWASP A09): 'except Exception: pass' swallows even ImportError silently. Not exploitable; operational concern = silent misconfiguration (developer gets no signal that notifications are broken). Suggest a 1-line stderr write in the except to preserve never-crash while restoring debuggability (notify.py logs only if reached; an ImportError on the import line is swallowed before notify.py can log).
- F2 (Low/informational): Confidentiality CONFIRMED SAFE by construction. The three messages interpolate ONLY two integers (passed,total) into static templates; no paths, filenames, project names, secrets, branch names, usernames, or IDs cross the boundary. No change needed.
- F3 (Advisory, future/not-in-this-change): vision doc's security-F1 (sentinel-scoping) and security-F2 (absent-verdict-is-blocking) are faithfully aligned with the CLAUDE.md untrusted-reply invariant; when the watcher is built they must be HARD requirements gated by a dedicated security review.

TRUST BOUNDARIES: egress to ntfy.sh carries only int counts (safe by construction); opt-in default off correctly prevents pre-commit hook from emitting without developer intent; lazy 'from notify import' shadow risk is below threshold (blast radius = notification failure, not code exec; pattern pre-existing).

PRIME OBJECTIVE: clear. No attribution/consent/value-flow surface; only opaque integer counts cross the boundary.

---

## Turn 4 — facilitator (critique)
*2026-05-25T17:04:34.702520+00:00 | confidence: 0.8*
*tags: finding-verification*

Finding verification: 5 verified, 0 inconclusive, 0 discarded. QA-F1 confirmed against tests/test_quality_gate.py:39 (success call passes no priority kwarg; get(priority) is None; None != high is vacuously true). QA-F2/F3 and SEC-F1/F2 all confirmed against scripts/quality_gate.py _notify_outcome (ImportError path untested; total==0 reaches passed==total pass branch; all message strings interpolate only int counts).

---

## Turn 5 — facilitator (synthesis)
*2026-05-25T17:04:59.197869+00:00 | confidence: 0.92*
*tags: blocking:1, advisory:4, speculative:0, model-tiers:qa-specialist:sonnet|security-specialist:sonnet*

## Request Context
- **What was requested**: Replicate agentic_journal push-notification methodology into the template (workstream 1: task-boundary notification hooks); deferred watcher captured as type:vision.
- **Files/scope**: scripts/quality_gate.py (--notify flag + _notify_outcome), tests/test_quality_gate.py (new), notifying-the-developer SKILL.md (doc), watcher vision doc (context only).
- **Developer-stated motivation**: Benefit from the derived project's methodology without downgrading the template's better implementations.
- **Explicit constraints**: confidentiality-safe text (public relay); never break the gate; no-op when NTFY_TOPIC unset; opt-in.

## Synthesis
Verdict: approve-with-changes. Weighted confidence ~0.92 (qa 0.88, security 0.95). Blocking: 1, Advisory: 4, Speculative: 0.

The change is a clean, minimal, opt-in egress addition. Security confirmed confidentiality is safe BY CONSTRUCTION (only int counts cross to ntfy.sh; no paths/secrets/IDs) and the never-crash contract holds; zero blocking from security. QA confirmed ~95% branch coverage and verified the never-crash test, but flagged ONE blocking test-quality defect.

BLOCKING (fix before commit):
- QA-F1 (REVIEW.md Rule 15): test_pass_fires_success assertion 'kwargs.get(priority) != high' is vacuous (success path passes no priority kwarg). Replace with 'assert "priority" not in kwargs'.

ADVISORY (recommended; convergent across both reviewers):
- SEC-F1 + QA-F2 converge: the 'except Exception: pass' swallows ImportError silently. Add a 1-line stderr notice in the except (preserves never-crash, restores debuggability) AND add a test for the import-failure never-raise path.
- QA-F3: document/handle total==0 (all-skipped) -> 'All 0 checks passed' (docstring note suffices).
- SEC-F2: confidentiality confirmed safe (no action).
- SEC-F3 (future): when the watcher vision is built, security-F1/F2 must be hard requirements behind a dedicated security review.

Model tiers: qa-specialist:sonnet, security-specialist:sonnet.

---
