---
spec_id: SPEC-20260310-132921
title: "Framework Branching Strategy for Private Development and Public Promotion"
status: reviewed
risk_level: medium
reviewed_by: [architecture-consultant, docs-knowledge, independent-perspective]
discussion_id: DISC-20260310-133048-framework-branching-strategy-spec-review
---

## Goal

Establish a documented Git branching strategy that enables the developer to:
1. Maintain a **private development fork** of the public framework for experimentation
2. Develop framework features (e.g., code review apparatus) in isolation
3. **Promote polished features** back to the public repo when ready
4. Pull **upstream improvements** from the public repo cleanly
5. Keep the public `main` branch always clean and release-worthy

## Context

The framework (`agent_framework_template`) is public on GitHub under Diviner-Dojo. The developer wants to evolve the framework itself — adding capabilities like a code review system that emulates Anthropic's enterprise Code Review feature. This requires a sandbox for experimentation that doesn't pollute the public repo, but with a clear path to promote successful experiments.

The developer is new to GitHub, so the strategy must be:
- Simple enough to follow without deep Git expertise
- Documented with exact commands and rationale (WHY, not just WHAT)
- Recoverable from common mistakes (error recovery procedures included)
- Compatible with the existing lineage tracking infrastructure

### Current State
- Single remote (`origin` → `Diviner-Dojo/agent_framework_template`)
- Branches: `main` plus several feature/fix branches
- Lineage tracking initialized but upstream not yet configured
- No private repo exists yet

### Strategy Choice: Two-Repo vs. Single-Repo

Two approaches were evaluated:

**Option A — Single repo, branch discipline only** (simplest):
Keep one local clone. Never push `lab/*` branches to the public remote. When ready, push clean `feature/*` branches and open PRs. No private GitHub repo needed.
- Pro: Minimal complexity, no remote confusion
- Con: No cloud backup of experimental work; if local machine fails, all lab work is lost

**Option B — Two repos with dual remotes** (chosen):
Private GitHub repo for cloud backup of all work, including experiments. Public repo remains the canonical source.
- Pro: Cloud backup, full experiment history preserved, clear separation
- Con: Remote configuration complexity, sync discipline required

**Decision**: Option B is chosen because cloud backup of experimental work is essential — framework experiments (like building a code review apparatus) represent significant investment that should not depend on a single machine. The additional complexity is manageable with documented commands and the sync trigger rule (R4).

## Requirements

### R1: Two-Repo Architecture
- A **private repo** (e.g., `my-framework-lab`) for experimentation
- The **public repo** (`agent_framework_template`) remains the canonical, clean version
- Git remotes: `origin` = private repo, `upstream` = public repo (standard Git convention)

**Why two remotes?** A "remote" is a named bookmark pointing to a repository on GitHub. We name them so we can say "push to this one, not that one." `origin` = your private home base (default push target). `upstream` = the public framework you forked from (pull improvements from here).

### R2: Branch Naming Convention
A consistent, self-documenting branch naming scheme:
- `main` — always stable, ready for public promotion at any time
- `lab/*` — experimental branches (may be messy, may be abandoned)
- `feature/*` — clean implementation branches headed toward promotion

**When is something a `lab/` vs `feature/`?**
- `lab/` = "I'm not sure this approach will work" — exploring, prototyping, might abandon it
- `feature/` = "The approach is proven, I'm building the polished version" — clean commits, headed for public

Examples:
- `lab/review-hook-experiment` — trying out whether git hooks can capture review data
- `lab/mcp-server-spike` — exploring MCP server integration, unclear if viable
- `feature/review-apparatus` — proven approach, building the clean implementation
- `feature/code-review-ui` — polished UI component ready for promotion

If you use the wrong prefix, nothing breaks — these names are for your own navigation. Rename with `git branch -m old-name new-name`.

### R3: Promotion Workflow
A clear process for moving work from private repo → public repo:
1. **Sync first** (mandatory — see R4)
2. Develop on `lab/*` or `feature/*` in private repo
3. When ready, push the `feature/*` branch to `upstream` using public naming convention
4. Open PR on public repo via `gh pr create`
5. Squash-merge the PR (keeps public history clean automatically)
6. Clean up: delete the feature branch from upstream after merge

**Why squash-merge?** It combines all your commits into one clean commit on the public repo. This means your messy intermediate commits ("WIP", "fix typo", "try different approach") never appear in the public history. This eliminates the need for a separate `promote/*` staging branch — the squash-merge does the cleanup for you.

**Why push as `feature/*` not `promote/*`?** The public repo uses `feature/*`, `fix/*`, `docs/*` naming. Pushing with a matching prefix keeps the public repo's branch namespace consistent. Your private repo can use `lab/*` naming that doesn't exist on the public side.

### R4: Upstream Sync Workflow
A process for pulling improvements from the public repo into the private repo.

**Sync trigger rule**: You MUST sync before any promotion attempt. This prevents drift from accumulating silently.

1. Fetch from upstream remote
2. Merge upstream `main` into private `main`
3. Rebase or merge active feature branches as needed
4. Push updated `main` to `origin` (private backup)

**Additional sync cadence**: Sync at least monthly even if not promoting, or whenever you start a new `feature/*` branch. This keeps merges small and manageable.

### R5: Lineage Integration
- Update `framework-lineage.yaml` in the private repo to track divergence
- Populate `upstream.locked.url` and `upstream.locked.commit_hash` at setup time
- Use `pinned_traits` to protect intentional divergences during sync
- Add `framework-lineage.yaml` to `.gitattributes` with `merge=ours` to prevent sync conflicts
- `/lineage` tracks structural framework drift (file-level hashes against baseline); `git diff upstream/main` tracks content-level divergence between repos

**Note on lineage scope**: The Steward (Phase 1) was designed for template-to-derived-project tracking. In a private fork scenario, it tracks how far your private framework has drifted from the public template. It does NOT model the dual-remote topology itself — that's managed by Git and documented in BRANCHING.md.

### R6: Documentation
- A `BRANCHING.md` guide in the private repo with:
  - Conceptual primer (what remotes are, why branches exist)
  - Step-by-step commands for every workflow
  - **Rationale** for every convention (WHY before WHAT)
  - **Error recovery** procedures for each identified risk
  - Concrete examples of branch naming decisions
- Branch naming rules enforced by convention (documented, not automated)

### R7: Branch Cleanup Policy
- `lab/*` branches: deleted when experiment concludes (regardless of outcome)
- `feature/*` branches on upstream: deleted after PR merges
- Local feature branches: deleted after promotion is complete
- Before deleting a `lab/*` branch with useful learnings, note what was learned in a commit message or discussion

## Constraints

- **Solo developer** — no need for complex access controls or approval gates
- **GitHub-hosted** — both repos on GitHub (private repo requires GitHub Free tier minimum)
- **No CI/CD yet** — strategy should work with manual workflows
- **Git skill level: beginner** — commands must be explicit, no assumed knowledge
- **Framework already has lineage tracking** — leverage existing Steward infrastructure
- **Developer has push access to public repo** — required for pushing feature branches to upstream

## Acceptance Criteria

- [ ] Private repo created with correct remote configuration (`origin` = private, `upstream` = public)
- [ ] Branch naming convention documented with rationale and examples
- [ ] Promotion workflow tested: feature developed privately → PR to public repo (squash-merge)
- [ ] Upstream sync workflow tested: public improvement → merged into private repo
- [ ] `framework-lineage.yaml` updated for private repo (type: `derived`, upstream fields populated)
- [ ] `.gitattributes` configured with `merge=ours` for `framework-lineage.yaml`
- [ ] `BRANCHING.md` written with commands, rationale, error recovery, and examples
- [ ] Pinned traits mechanism demonstrated for protecting intentional divergences
- [ ] ADR-0003 created documenting the dual-remote strategy decision
- [ ] Sync trigger rule documented: must sync before any promotion
- [ ] Branch protection enabled on public repo `main` (require PR, block force-push)

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation | Recovery |
|---|---|---|---|---|
| Merge conflicts during sync | Medium | Low | Pin intentional divergences; sync frequently | `git merge --abort` to cancel; `git status` to find conflicts; always keep your `framework-lineage.yaml` |
| Accidentally pushing to upstream | Low | Medium | Separate remotes with distinct names; verify with `git remote -v` before push | `git push upstream --delete <branch>` to remove; if sensitive, contact repo admin |
| Losing work on abandoned `lab/*` | Low | Low | Push lab branches to `origin` for backup | `git reflog` to recover recently deleted branches |
| Drift becomes too large to sync | Medium | High | Monthly sync cadence; mandatory pre-promotion sync | If severely drifted, start fresh: re-clone public, re-apply private changes selectively |
| Cherry-pick SHA duplication on sync | Medium | Low | Use squash-merge (eliminates cherry-pick) | If encountered: `git log --oneline upstream/main..HEAD` to identify already-promoted commits |

## Affected Components

- `framework-lineage.yaml` — updated for private repo identity
- `.claude/custodian/` — lineage events for fork
- `.gitattributes` — merge strategy for lineage file
- New file: `BRANCHING.md` — developer guide (private repo only)
- New file: `docs/adr/ADR-0003-private-fork-branching-strategy.md`
- No changes to framework source code

## Dependencies

- GitHub account with ability to create private repos (Free tier supports this)
- Git installed and configured locally
- GitHub CLI (`gh`) installed for PR creation
- Push access to the public repo (developer is owner)
- Existing lineage tracking scripts (`scripts/lineage/`)

## Proposed Branch Architecture

```
PUBLIC REPO (agent_framework_template)          PRIVATE REPO (my-framework-lab)
─────────────────────────────────────          ──────────────────────────────────

                                               origin (private, default push)
                                               upstream (public, pull + promote)

main ●─────●─────●─────●──────●                main ●─────●─────●─────●─────●
           │          ↑                               │    ↑           │
           │    feature/      │                               │    │ (sync)     │
           │    review-       │                               │    │            │
           │    apparatus     │                               │    │            │
           │   (squash-merge) │                               │    │            │
           └──────────────────┘                        feature/review-apparatus ●──●──●
              (PR to public)                                       │
                                                            lab/review-experiments ●──●
                                                               (messy, exploratory)
```

## Workflow: Complete Lifecycle Example

### Setting up (one-time)
```bash
# 1. Create private repo on GitHub (empty, no README)
#    Go to github.com → "+" → "New repository"
#    Name: my-framework-lab, Visibility: Private
#    Do NOT add README, .gitignore, or license

# 2. In your existing project folder, reconfigure remotes
#    (no new clone needed — you keep working where you are)
git remote rename origin upstream

# 3. Add private repo as "origin" (your default push target)
git remote add origin https://github.com/YOUR-USER/my-framework-lab.git

# 4. Verify remotes look right
git remote -v
# Expected output:
#   origin    https://github.com/YOUR-USER/my-framework-lab.git (fetch)
#   origin    https://github.com/YOUR-USER/my-framework-lab.git (push)
#   upstream  https://github.com/Diviner-Dojo/agent_framework_template.git (fetch)
#   upstream  https://github.com/Diviner-Dojo/agent_framework_template.git (push)

# 5. Push everything to private repo
git push -u origin main

# 6. Initialize lineage for derived project
rm framework-lineage.yaml
python scripts/lineage/init_lineage.py \
  --project-name "my-framework-lab" \
  --template-version "2.1.0" \
  --project-type "derived"

# 7. Populate upstream reference in lineage manifest
# Edit framework-lineage.yaml and set:
#   upstream.locked.url: https://github.com/Diviner-Dojo/agent_framework_template.git
#   upstream.locked.commit_hash: <output of: git rev-parse HEAD>

# 8. Prevent lineage file merge conflicts on future syncs
echo "framework-lineage.yaml merge=ours" >> .gitattributes

# 9. Commit the setup
git add framework-lineage.yaml .gitattributes
git commit -m "Initialize private fork with lineage tracking"
git push origin main
```

### Experimenting (daily work)
```bash
# Start a messy experiment
git checkout -b lab/review-idea-1 main
# ... hack freely, commit often, no pressure ...

# Push to origin for cloud backup (safe — this is your private repo)
git push -u origin lab/review-idea-1

# If the experiment works, graduate it to a clean feature branch
git checkout -b feature/review-apparatus main
git merge lab/review-idea-1  # or cherry-pick specific commits

# Clean up the lab branch when done
git branch -d lab/review-idea-1
git push origin --delete lab/review-idea-1
```

### Promoting to public
```bash
# STEP 0: Sync first (mandatory!)
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# STEP 1: Make sure your feature branch is up to date with main
git checkout feature/review-apparatus
git rebase main  # or: git merge main

# STEP 2: Push to the PUBLIC repo using public naming convention
git push upstream feature/review-apparatus

# STEP 3: Create PR on GitHub (public repo)
gh pr create --repo Diviner-Dojo/agent_framework_template \
  --head feature/review-apparatus --base main \
  --title "Add review apparatus feature" \
  --body "Developed and tested in private lab."

# STEP 4: After PR is merged (squash-merge on GitHub), clean up
git push upstream --delete feature/review-apparatus
git branch -d feature/review-apparatus

# STEP 5: Sync the merge back to your private repo
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

### Syncing upstream improvements
```bash
# Fetch latest from public
git fetch upstream

# Merge into your private main
git checkout main
git merge upstream/main
# framework-lineage.yaml will auto-resolve to your version (merge=ours)

# Push updated main to private
git push origin main

# Update active feature branches
git checkout feature/my-feature
git rebase main  # or: git merge main
```

## Error Recovery

### Merge conflict during sync
```bash
# If git merge upstream/main produces conflicts:
git status                    # See which files are conflicted
# Option A: Abort and try later
git merge --abort
# Option B: Resolve conflicts
#   Open each conflicted file, look for <<<<<<< markers
#   Edit to keep the version you want, remove the markers
#   Then:
git add <resolved-file>
git commit                    # Completes the merge
```

### Accidentally pushed private branch to upstream
```bash
# Delete the branch from the public repo immediately
git push upstream --delete lab/my-private-experiment
# If the branch contained secrets, rotate them immediately
```

### Lost a branch you deleted
```bash
# Git keeps recent history for ~30 days
git reflog                    # Find the commit hash of the deleted branch
git checkout -b recovered-branch <commit-hash>
```

### Everything is confused and you want to start over
```bash
# Nuclear option: re-clone and re-setup (your private repo backup is safe)
cd ..
rm -rf my-framework-lab
git clone https://github.com/YOUR-USER/my-framework-lab.git
cd my-framework-lab
git remote add upstream https://github.com/Diviner-Dojo/agent_framework_template.git
```
