---
description: "Promote a lesson from raw discussion into curated memory. Requires human approval."
argument-hint: "<what to remember>"
---

# Remember

`discussions/` holds everything that was said. `memory/` holds the small
fraction worth carrying forward. The gap between them is human judgment, and
this command never closes it automatically (Principle #6).

Find the evidence first. A lesson worth promoting has usually shown up more
than once:

```bash
grep -ril "<keyword>" discussions/ memory/ | head -20
```

Bring the developer a proposal, not a fait accompli:

- **What** the lesson is, in one sentence
- **Where it came from** — the discussions or reviews that produced it, by ID
- **Why now** — what recurrence or cost makes it worth durable space
- **Where it belongs** — `decisions/`, `patterns/`, `lessons/`, `bugs/`,
  `architecture/`, `security/`, `performance/`, `ux/`

Then ask, and mean it. "No" and "not yet" are good outcomes — curated memory
that nobody trusts is worse than none.

On approval, write it with its provenance intact:

```markdown
---
id: <TYPE>-<YYYYMMDD>-<slug>
sources: [DISC-..., REV-...]
promoted: <YYYY-MM-DD>
approved_by: <developer>
---
```

`sources` is not decoration. A promoted claim that can't be traced back to the
reasoning that earned it has lost what made it worth keeping — repair the
pointer or withhold the promotion.
