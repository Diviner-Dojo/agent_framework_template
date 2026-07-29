---
description: "Look back across recent work and find what should change. Produces proposals, never self-applied edits."
argument-hint: "[since-date|since-tag]"
---

# Retro

Read the captured record and say something true about it.

```bash
python scripts/mine_patterns.py --since <date>
python scripts/compute_agent_effectiveness.py
python scripts/audit_calibration.py --report-only
python scripts/briefing.py regret
python scripts/briefing.py ledger --limit 30
```

Look for what actually recurs:

- Findings that keep reappearing — the codebase is telling you something
- Decisions later reversed — what was missing at decision time
- Briefings repeatedly deferred in one area — either the teaching missed, or
  that area needs simplifying rather than explaining
- Framework friction — a gate that fires without catching anything is costing
  more than it returns, and should be proposed for deletion. **Check that
  before believing it**: `protocol_yield` records what each review actually
  caught. A gate with no recorded yield may be worthless, or may simply never
  have been measured — those look identical and are not the same. Never propose
  deleting a gate on absence of evidence

Prefer the smallest intervention that would work. In this framework, deleting
something is usually available and usually right.

Write proposals to `memory/lessons/RETRO-<date>.md` with `status: pending`.

**Proposals are communication, not instructions.** Changing a rule, a gate, or
this framework's own definition is a developer action. Making those edits off
your own proposal would be self-modification, and the human gate is the point
(Prime Objective). Bring the case; let them decide.
