---
adr_id: ADR-0003
title: "Adopt Dual-Remote Branching Strategy for Private Framework Development"
status: accepted
date: 2026-03-10
decision_makers: [facilitator, architecture-consultant, docs-knowledge, independent-perspective]
discussion_id: DISC-20260310-133048-framework-branching-strategy-spec-review
supersedes: null
risk_level: medium
confidence: 0.85
tags: [git, branching, workflow, lineage, private-fork]
---

## Context

The framework (`agent_framework_template`) is public on GitHub. The developer needs to evolve the framework itself — adding capabilities like a code review apparatus — without polluting the public repo with half-finished experiments. At the same time, successful experiments must have a clear promotion path back to the public repo.

Key forces:

1. **Experimentation requires freedom**: Framework evolution involves messy, exploratory work that should not be visible on the public repo.
2. **Cloud backup is essential**: Framework experiments represent significant investment that should not depend on a single machine.
3. **Promotion must be clean**: The public repo's history should contain only polished, reviewed changes.
4. **Upstream sync must be manageable**: Public improvements must flow into the private fork without excessive merge conflicts.
5. **Developer is a GitHub beginner**: The strategy must use standard conventions and be documented with exact commands.
6. **Lineage tracking exists**: The Steward agent (ADR-0002) provides drift detection infrastructure that should be leveraged, not duplicated.

## Decision

Adopt a **dual-remote, two-repository branching strategy**:

- **Private repo** (`origin`): cloud-backed sandbox for all experimental and feature work
- **Public repo** (`upstream`): canonical framework, receives only polished promotions

### Remote Naming

Use standard Git convention: `origin` for the developer's own repo, `upstream` for the source-of-truth repo. This aligns with every Git tutorial, GitHub documentation page, and Stack Overflow answer the developer will encounter.

### Branch Naming

Two tiers in the private repo:

- `lab/*` — exploratory experiments (may be abandoned)
- `feature/*` — clean implementations headed for promotion

The `main` branch in the private repo stays synced with `upstream/main` and is always promotion-ready.

### Promotion via Squash-Merge

Push `feature/*` branches to `upstream`, open a PR, and squash-merge. This eliminates the need for a `promote/*` staging branch — the squash-merge provides clean public history automatically.

### Mandatory Pre-Promotion Sync

Before any promotion attempt, the developer must sync `main` from `upstream`. This prevents drift from accumulating silently.

### Lineage File Conflict Prevention

Add `framework-lineage.yaml` to `.gitattributes` with `merge=ours` strategy. This prevents a guaranteed merge conflict on every upstream sync (the private repo's manifest has `type: derived` while the public repo has `type: template`).

## Alternatives Considered

### Alternative 1: Single repo with branch discipline only

- **Pros**: Simplest possible approach — no private repo, no remote confusion, no sync workflow
- **Cons**: No cloud backup of experimental work; if the local machine fails, all lab work is lost
- **Reason rejected**: Framework experiments (like building a code review apparatus) represent significant time investment. Depending on a single machine for backup is an unacceptable risk. The additional complexity of a second repo is manageable with documented commands.

### Alternative 2: GitHub's native fork model

- **Pros**: GitHub provides built-in fork infrastructure (PR across forks, sync button)
- **Cons**: GitHub does not allow private forks of public repositories on the Free tier. The developer would need a paid plan or a workaround (mirror clone). Additionally, GitHub's fork model creates a visible link between the repos that may not be desired.
- **Reason rejected**: GitHub Free tier limitation makes this infeasible. The mirror-clone + dual-remote approach achieves the same result without platform constraints.

### Alternative 3: Two repos with a `promote/*` staging branch

- **Pros**: Explicit staging layer for cherry-picking clean commits before pushing to public
- **Cons**: Adds a third branch namespace, two extra git commands per promotion, and introduces cherry-pick SHA duplication (cherry-picked commits get new SHAs, causing potential confusion on the next upstream sync)
- **Reason rejected**: Squash-merge on the public repo PR achieves the same history cleanliness without the extra branch layer. Per Principle #8, the simpler intervention is preferred.

## Consequences

### Positive

- All experimental work is cloud-backed on the private repo
- Public repo history remains clean (squash-merge ensures this)
- Standard Git remote naming reduces confusion when consulting external resources
- Lineage tracking (ADR-0002) integrates naturally — the private repo is a `derived` instance
- Mandatory pre-promotion sync prevents drift accumulation
- `merge=ours` on `framework-lineage.yaml` eliminates the most common merge conflict

### Negative

- Two repos require sync discipline (mitigated by mandatory pre-promotion sync rule)
- Remote configuration is a one-time complexity that could confuse a beginner (mitigated by step-by-step BRANCHING.md guide)
- Developer must remember which remote to push to (mitigated by `origin` as default push target — experiments go to the safe place by default)

### Neutral

- The Steward's Phase 1 lineage tracking (see ADR-0002) models a single upstream relationship. The dual-remote topology introduces a second axis (private fork ↔ public source) that the current manifest schema does not fully represent. This is a known limitation deferred to Phase 2+. Additionally, `merge=ours` on `framework-lineage.yaml` will prevent upstream schema version changes from propagating — the developer must manually reconcile schema changes if the template updates to a newer manifest schema.
- Branch naming is enforced by convention (documented), not by automation (git hooks). This is intentional — a git hook would be disproportionate overhead for a solo developer.

## Linked Discussion

See: discussions/2026-03-10/DISC-20260310-133048-framework-branching-strategy-spec-review/
