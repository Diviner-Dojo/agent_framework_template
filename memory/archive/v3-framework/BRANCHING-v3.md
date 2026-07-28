# Branching Strategy: Private Framework Development

This guide documents the branching strategy for maintaining a private development fork of the public framework. It enables experimentation in isolation with a clean path to promote polished work back to the public repo.

**Decision record**: [ADR-0003](docs/adr/ADR-0003-private-fork-branching-strategy.md)
**Spec**: [SPEC-20260310-132921](docs/sprints/SPEC-20260310-132921-framework-branching-strategy.md)

---

## Concepts: What You Need to Know First

### What is a "remote"?

A **remote** is a named bookmark pointing to a repository on GitHub. When you clone a repo, Git creates a remote called `origin` that points to where you cloned from.

We use two remotes because we have two repos:

| Remote | Points to | Purpose |
|---|---|---|
| `origin` | Your private repo | Default push target. Safe for experiments. |
| `upstream` | The public repo | Pull improvements from here. Push promotions here. |

These names follow standard Git convention — every tutorial, Stack Overflow answer, and GitHub doc you read will use the same terms.

### Why two repos?

You could keep everything in one local clone and just not push experiments. But if your machine fails, all experimental work is lost. A private GitHub repo gives you cloud backup of everything — messy experiments included — at no cost (GitHub Free supports private repos).

### What are branches for?

Branches let you work on something without affecting `main`. Think of them as "save slots" — you can switch between them freely. We use two types:

- **`lab/*`** branches: "I'm not sure this will work." Explore freely, commit messy code, might abandon it.
- **`feature/*`** branches: "This approach is proven, I'm building the clean version." Polished commits headed for the public repo.

If you pick the wrong prefix, nothing breaks. Rename anytime: `git branch -m old-name new-name`.

---

## One-Time Setup

### Prerequisites

- A GitHub account (Free tier is fine)
- Git installed locally
- GitHub CLI (`gh`) installed — [download here](https://cli.github.com/)
- GitHub CLI authenticated (run `gh auth login` once — follow the prompts to authenticate via browser)
- Push access to the public repo (you're the owner, so you have this)

### Step-by-step

```bash
# 1. Create a new PRIVATE repo on GitHub
#    Go to github.com -> "+" (top right) -> "New repository"
#    Repository name: my-framework-lab (or whatever you prefer)
#    Visibility: Private
#    IMPORTANT: Do NOT add a README, .gitignore, or license
#    Click "Create repository"

# 2. In your existing project folder, rename the remote
#    WHY: Your current "origin" points to the public repo. We rename it
#    to "upstream" (the standard name for "the repo I forked from").
#    No new folder is created — you keep working right where you are.
git remote rename origin upstream

# 3. Add your private repo as "origin"
#    WHY: "origin" is the standard name for "my own repo" — it becomes
#    the default target for git push, so experiments go to the safe place
git remote add origin https://github.com/YOUR-USERNAME/my-framework-lab.git

# 4. Verify your remotes are correct
git remote -v

# You should see exactly this (with your username):
#   origin    https://github.com/YOUR-USERNAME/my-framework-lab.git (fetch)
#   origin    https://github.com/YOUR-USERNAME/my-framework-lab.git (push)
#   upstream  https://github.com/Diviner-Dojo/agent_framework_template.git (fetch)
#   upstream  https://github.com/Diviner-Dojo/agent_framework_template.git (push)
#
# If it looks wrong, see "Error Recovery" below.

# 5. Push everything to your private repo
#    WHY: This copies your entire project (all branches, all history)
#    to the private repo. From now on, "git push" goes here by default.
git push -u origin main

# 6. Initialize lineage tracking for your derived project
#    WHY: This tells the Steward agent that your project is derived from
#    the public template, so it can track how far you've drifted.
#    We delete the template's manifest first because init_lineage.py
#    refuses to overwrite an existing manifest (safety guard).
#    IMPORTANT: --project-type "derived" must be included. Without it,
#    the manifest defaults to type: template, which is wrong for a fork.
rm framework-lineage.yaml
python scripts/lineage/init_lineage.py \
  --project-name "my-framework-lab" \
  --template-version "2.1.0" \
  --project-type "derived"
#    If you see "ERROR: Manifest already exists", a previous partial setup
#    left one behind. Run: rm framework-lineage.yaml   then re-run the command above.

# 7. Record which upstream commit you forked from
#    WHY: This gives the lineage system a reference point for drift detection.
#    We want the public repo's commit hash at the time you cloned — NOT any
#    commits you may have made locally since then.
#    Get the upstream commit hash (safe even if you've made local commits):
git log upstream/main --oneline -1
#    Copy the hash (the short hex string at the start of the output).
#    Now edit framework-lineage.yaml and update the upstream section.
#
#    BEFORE (generated by init_lineage.py — url and commit_hash will be null):
#      upstream:
#        locked:
#          url: null
#          commit_hash: null
#          synced_at: '2026-...'
#
#    AFTER (you fill in the url and paste the hash):
#      upstream:
#        locked:
#          url: https://github.com/Diviner-Dojo/agent_framework_template.git
#          commit_hash: <paste the hash from git log upstream/main>
#          synced_at: '2026-...'

# 8. Enable the merge=ours driver for .gitattributes
#    WHY: Git doesn't recognize merge=ours in .gitattributes by default.
#    This one-time config tells Git what "merge=ours" means: keep our version.
git config merge.ours.driver true

# 9. Commit the setup
git add framework-lineage.yaml .gitattributes
git commit -m "Initialize private fork with lineage tracking"
git push origin main
```

### Verify setup is correct

After setup, run these checks:

```bash
# Check 1: Remotes
git remote -v
# Should show origin (private) and upstream (public)

# Check 2: Default push goes to private repo
git push --dry-run
# Should say "Everything up-to-date" pointing at your private repo

# Check 3: Can fetch from public repo
git fetch upstream
# Should succeed without errors

# Check 4: Lineage is initialized
cat framework-lineage.yaml
# Should show type: derived, your project name
```

### Branch protection (public repo)

This step locks down the public repo's `main` branch so nothing can be pushed directly — the only way in is through an approved Pull Request. This is the professional standard for protecting production/release branches.

**Via GitHub UI:**

1. Go to `github.com/Diviner-Dojo/agent_framework_template`
2. Click **Settings** (top menu bar, far right)
3. Click **Branches** (left sidebar, under "Code and automation")
4. Click **Add branch ruleset** (or "Add rule" if you see the classic interface)
5. Configure:
   - **Branch name pattern**: `main`
   - **Require a pull request before merging**: check this box
   - **Block force pushes**: check this box (prevents `git push --force` from rewriting history)
6. Click **Create** (or **Save changes**)

**Via GitHub CLI** (alternative — same result):

```bash
# This enables branch protection requiring PRs and blocking force-push
gh api repos/Diviner-Dojo/agent_framework_template/branches/main/protection \
  --method PUT \
  --field required_pull_request_reviews='{"required_approving_review_count":0}' \
  --field enforce_admins=true \
  --field restrictions=null \
  --field required_status_checks=null
```

**Why `required_approving_review_count: 0`?** As a solo developer, you don't need someone else to approve your PRs. The protection is about forcing the PR workflow (so you review the diff on GitHub before merging), not about requiring a second person. You can increase this later if you add collaborators.

**Test it works:**

```bash
# This should be REJECTED after protection is enabled:
git push upstream main
# Expected error: "protected branch hook declined"

# This is the correct workflow — push a feature branch and create a PR:
git push upstream feature/test-branch
gh pr create --repo Diviner-Dojo/agent_framework_template \
  --head feature/test-branch --base main \
  --title "Test branch protection" --body "Testing the PR workflow"
```

---

## Daily Workflow: Experimenting

### Starting a new experiment

```bash
# Create a lab branch from main
#   WHY: Starting from main ensures you have the latest code
git checkout -b lab/my-experiment main

# Work freely — commit as often as you want, messy is fine
git add .
git commit -m "WIP: trying out the thing"

# Push to your private repo for cloud backup
#   WHY: -u sets origin as the default push target for this branch,
#   so future pushes just need: git push
git push -u origin lab/my-experiment
```

### Graduating an experiment to a feature

When a lab experiment proves the approach works and you want to build the clean version:

```bash
# Create a clean feature branch from main
git checkout -b feature/my-feature main

# Bring in the lab work
# Option A: Merge everything (simpler)
git merge lab/my-experiment

# Option B: Cherry-pick specific commits (more surgical)
git log lab/my-experiment --oneline    # Find the commits you want
git cherry-pick <commit-hash>          # Pick them one by one
```

### Cleaning up finished experiments

```bash
# Delete the local branch
#   WHY: -d is the safe delete — it won't delete if there are unmerged changes
#   Use -D (capital) only if you're sure you want to discard unmerged work
git branch -d lab/my-experiment

# Delete the remote backup too
git push origin --delete lab/my-experiment
```

---

## Promoting Work to the Public Repo

This is how polished features move from your private repo to the public one.

### Pre-promotion checklist

Before promoting, verify:
- [ ] Quality gate passes: `python scripts/quality_gate.py`
- [ ] Tests pass: `pytest tests/ -v`
- [ ] You've synced from upstream (next section shows how)

### Step-by-step promotion

```bash
# STEP 0: Sync first (MANDATORY — never skip this!)
#   WHY: If upstream has changed since you started, your promotion branch
#   might conflict. Better to resolve conflicts now, in your private repo,
#   than to discover them in the public PR.
git checkout main
git fetch upstream
git merge upstream/main
git push origin main

# STEP 1: Update your feature branch with latest main
git checkout feature/my-feature
git rebase main
# If rebase has conflicts, see "Error Recovery" section below
# Alternative if you prefer merge: git merge main

# STEP 2: Push the feature branch to the PUBLIC repo
#   WHY: This creates the branch on the public repo so you can open a PR from it.
#   The branch uses feature/* naming to match the public repo's conventions.
git push upstream feature/my-feature

# STEP 3: Create a Pull Request
gh pr create --repo Diviner-Dojo/agent_framework_template \
  --head feature/my-feature --base main \
  --title "Add my-feature" \
  --body "Developed and tested in private lab."

# STEP 4: On GitHub, merge the PR using "Squash and merge"
#   WHY: Squash-merge combines all your commits into one clean commit.
#   Your messy "WIP", "fix typo", "try again" commits never appear in
#   the public history. This is why we don't need a separate promote/* branch.

# STEP 5: After the PR is merged, clean up
git push upstream --delete feature/my-feature    # Remove from public repo
git branch -d feature/my-feature                  # Remove local branch

# STEP 6: Sync the merged result back to your private repo
git checkout main
git fetch upstream
git merge upstream/main
git push origin main
```

---

## Syncing Upstream Improvements

When changes are merged to the public repo (by you or others), pull them into your private fork.

### When to sync

- **Before every promotion** (mandatory — this is the sync trigger rule)
- **Monthly** even if not promoting (keeps merges small)
- **When starting a new `feature/*` branch** (start from fresh main)

### How to sync

```bash
# Fetch the latest from public
git fetch upstream

# Merge into your private main
git checkout main
git merge upstream/main
# NOTE: framework-lineage.yaml will auto-resolve to YOUR version
# because .gitattributes has merge=ours for this file.
# IMPORTANT: merge=ours only works with "git merge", not "git rebase".
# Always use merge (not rebase) when syncing main from upstream.

# Push updated main to your private repo
git push origin main

# Update any active feature branches
git checkout feature/active-feature
git rebase main    # or: git merge main
```

---

## Branch Cleanup Policy

Branches accumulate. Clean them up:

| Branch type | When to delete | Command |
|---|---|---|
| `lab/*` (local) | When experiment concludes — success or failure | `git branch -d lab/name` |
| `lab/*` (remote) | Same time as local | `git push origin --delete lab/name` |
| `feature/*` (on upstream) | After PR is merged | `git push upstream --delete feature/name` |
| `feature/*` (local) | After promotion is complete | `git branch -d feature/name` |

Before deleting a `lab/*` branch that taught you something useful, note what you learned in a commit message or discussion capture.

### See all your branches

```bash
git branch            # Local branches
git branch -r         # Remote branches (origin/* and upstream/*)
```

---

## Pinned Traits: Protecting Intentional Divergences

When you **intentionally** change something from the public template (e.g., add domain-specific rules, customize an agent), declare it in `framework-lineage.yaml` under `pinned_traits`:

```yaml
pinned_traits:
  - path: ".claude/agents/security-specialist.md"
    reason: "Custom security rules for my domain"
  - path: "CLAUDE.md"
    reason: "Added domain-specific safety constraints"
```

**Why?** This tells the Steward agent — and you, during merges — that these files should NOT be overwritten during upstream sync. Without pinned traits, `/lineage` will report these as "drift" and you might accidentally revert your intentional changes.

### Using the lineage system

```bash
# Check how far you've drifted from the public template
# (run /lineage in Claude Code, or:)
python scripts/lineage/drift.py

# This shows STRUCTURAL drift: which framework files have changed
# For CONTENT-LEVEL divergence from public, use:
git diff upstream/main
```

---

## Error Recovery

### Merge conflict during sync

```bash
# You ran: git merge upstream/main
# Git says: CONFLICT in some-file.py

# See what's conflicted:
git status

# Option A: Abort and try later (no harm done)
git merge --abort

# Option B: Resolve the conflict
# 1. Open the conflicted file in your editor
# 2. Look for markers like:
#    <<<<<<< HEAD
#    (your version)
#    =======
#    (upstream version)
#    >>>>>>> upstream/main
# 3. Edit the file to keep what you want, remove the markers
# 4. Mark as resolved:
git add some-file.py
# 5. Complete the merge:
git commit
```

### Rebase conflict

```bash
# You ran: git rebase main
# Git says: CONFLICT

# Option A: Abort (puts everything back)
git rebase --abort

# Option B: Resolve
# 1. Fix the conflicted files (same marker format as merge)
# 2. Stage them:
git add some-file.py
# 3. Continue the rebase:
git rebase --continue
```

### Accidentally pushed a private branch to upstream

```bash
# Delete it from the public repo immediately:
git push upstream --delete lab/my-private-experiment

# If the branch contained secrets (API keys, passwords):
# 1. Rotate the secrets immediately
# 2. The branch is removed but may still be in GitHub's cache briefly
```

### Pushed to the wrong remote

```bash
# Check which remote you pushed to:
git remote -v

# If you pushed to upstream by mistake:
git push upstream --delete branch-name

# If you pushed to origin by mistake (not harmful — it's your private repo):
# Nothing to worry about
```

### Lost a branch you deleted

```bash
# Git keeps recent history for ~30 days
git reflog

# Find the commit hash of the branch tip (look for "checkout: moving from...")
# Recover it:
git checkout -b recovered-branch <commit-hash>
```

### Remotes are misconfigured

```bash
# See current remotes:
git remote -v

# Remove a wrong remote:
git remote remove wrong-name

# Add the correct one:
git remote add origin https://github.com/YOUR-USER/my-framework-lab.git
git remote add upstream https://github.com/Diviner-Dojo/agent_framework_template.git
```

### Everything is broken — start over

```bash
# Your private repo on GitHub still has all your pushed work.
# Re-clone from your private repo into a fresh directory:
cd ..
mv agent_framework_template agent_framework_template.bak
git clone https://github.com/YOUR-USER/my-framework-lab.git agent_framework_template
cd agent_framework_template

# Re-add the public repo as upstream:
git remote add upstream https://github.com/Diviner-Dojo/agent_framework_template.git

# Verify:
git remote -v

# Once you've confirmed everything works, remove the backup:
# rm -rf ../agent_framework_template.bak
```

---

## Quick Reference Card

```bash
# === DAILY ===
git checkout -b lab/experiment main          # Start experiment
git push -u origin lab/experiment            # Back up to private
git branch -d lab/experiment                 # Clean up when done

# === PROMOTE ===
git fetch upstream && git merge upstream/main  # Sync first (mandatory!)
git push upstream feature/my-feature           # Push to public
gh pr create --repo Diviner-Dojo/agent_framework_template \
  --head feature/my-feature --base main        # Open PR
# After merge:
git push upstream --delete feature/my-feature  # Clean up public
git fetch upstream && git merge upstream/main  # Sync back

# === SYNC ===
git fetch upstream                           # Get latest public changes
git checkout main && git merge upstream/main # Merge into private main
git push origin main                         # Back up to private

# === STATUS ===
git remote -v                                # Check remote config
git branch                                   # See local branches
git branch -r                                # See remote branches
git log --oneline -10                        # Recent commits
```
