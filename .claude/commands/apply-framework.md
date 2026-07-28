---
description: "Apply or update this framework on another project. Assess first, deploy only on explicit approval, never push."
argument-hint: "<path-to-target-project>"
---

# Apply Framework

One target at a time. Assessment always precedes deployment.

## Assess

Read the target before proposing anything: its language and toolchain, whether
a framework is already present, and whether the working tree is clean.

Then be honest about fit. This framework costs real tokens and real ceremony
per change. It pays for itself on work where **understanding must outlive the
session** — a codebase someone maintains, decisions someone will question later,
a developer who wants to stay fluent in their own system. It does not pay for
itself on a throwaway script or a weekend prototype, and saying so is more
useful than a sale.

Present value and cost together, then stop and ask.

## Deploy

Only on explicit approval, and only with a clean working tree.

```bash
cd <target> && git checkout -b framework/apply-v4
```

Copy `.claude/`, `scripts/`, and the scaffolding for `docs/adr/`,
`discussions/`, `memory/`, `metrics/`. Then:

```bash
python scripts/init_db.py
```

Write a `CLAUDE.md` **for that project** — its stack, its gates, its real
constraints. Do not copy this one wholesale; a constitution that describes
someone else's repo is exactly the dead scaffolding this version exists to
remove.

Record the relationship in `framework-lineage.yaml` so the target knows where it
came from and can pull later changes.

Leave the branch unpushed and unmerged. Tell them how to back out: the branch is
the back-out.

## Never

Never push, never merge, never modify a target's `.claude/settings.json`, never
apply to more than one project per invocation.
