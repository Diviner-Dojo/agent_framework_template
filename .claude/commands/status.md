---
description: "Where things stand: working tree, risk of the current change, and what you haven't been briefed on."
---

# Status

```bash
git status --short && git log --oneline -5
python scripts/assess_risk.py
python scripts/briefing.py ledger
python scripts/briefing.py regret
```

Report it plainly and briefly. Lead with anything that needs a decision.

Deferred briefings are information, not a debt to collect on. Mention the count
once. If one has been sitting a long time and the code it covers is about to
change again, that is worth saying — otherwise leave it alone.
