---
name: severity-calibration
description: Shared severity rubric for review agents. Use when writing any finding in /review or specialist output. The explicit marker is what makes the capture pipeline's severity data trustworthy.
---

# Severity calibration

**State `Severity: <TIER>` on every finding.** `scripts/extract_findings.py`
parses that marker and trusts it over its keyword heuristics. Without it the
pipeline guesses from words in your prose — and it guesses badly, labelling
blocking findings `medium` and filing a correctness bug under `documentation`.

Everything downstream inherits that error: pattern mining, promotion
candidates, agent effectiveness, and `audit_calibration.py`. Getting this right
at the source is the only place it can be fixed.

| Tier | Scope | One-sentence test |
|---|---|---|
| `CRITICAL` | Active exploitability or data loss on the current path, no preconditions | Could a motivated attacker cause data loss, privilege escalation, or unauthorized access by calling this code as-is, today? |
| `HIGH` | Plausible exploitability, or a correctness bug with user-visible consequence — needs a non-trivial precondition | Under a realistic but non-default scenario, does this produce wrong output, corrupt data, or a weakness a defender would fix before the next release? |
| `MEDIUM` | Maintainability or theoretical risk with no realistic immediate exploit path | Would a senior engineer want this fixed next sprint, but not in a hotfix? |
| `LOW` | Style or minor improvement, no functional impact | Would this show up on a lint report rather than a correctness audit? |
| `INFO` | Observation, nothing to remediate | Is this purely informational? |

## Default down

If a finding could reasonably be two adjacent tiers, pick the **lower** one.
CRITICAL-or-HIGH → HIGH. HIGH-or-MEDIUM → MEDIUM.

Inflated severity is not caution — it trains people to discount you, and it
poisons the same data the framework uses to decide whether reviews are worth
running.

## Blocking is a separate axis

Severity describes the defect. Whether it blocks a merge is a judgment the
reviewer synthesizing findings makes, in context. A `MEDIUM` in the one file
this release exists to change may block; a `HIGH` in a path nobody calls may
not. Say both, and keep them distinct:

```
Severity: HIGH — blocking
Severity: MEDIUM — not blocking, worth a follow-up
```
