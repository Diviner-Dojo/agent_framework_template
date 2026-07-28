---
description: "Release workflow: gate, version, changelog, tag."
argument-hint: "<version>"
---

# Ship

```bash
python scripts/quality_gate.py
python scripts/briefing.py ledger
```

Before cutting the release, say out loud what is going out and what could go
wrong with it. Check that anything shipping under a deferred briefing is
something the developer knowingly chose to defer — mention it once, then
respect the answer.

```bash
python scripts/bump_version.py <version>
```

Update `FRAMEWORK_CHANGELOG.md` with what changed and why anyone should care.
Group by what it does for the reader, not by commit.

Tag and stop:

```bash
git tag -a v<version> -m "<summary>"
```

**Pushing is a developer action.** Show them the command; do not run it.
