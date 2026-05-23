---
description: "Stage framework updates into derived projects as unmerged/unpushed branches + an advisory assessment doc. Assesses fit and harm per target, stages only what is safe, and escalates to the human only when risk can't be mediated. Push the proposal, pull the apply."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "Task"]
argument-hint: "<target-paths...> [--adr ADR-NNNN | --changelog-since YYYY-MM-DD] [--dry-run]"
---

# Distribute — orderly framework propagation to derived projects

You are acting as the Facilitator. This command propagates a framework change outward to one or
more derived projects ("targets"). It loads each target's *real context* in the hub and runs a
**one-room assessment** here — including a specialist arguing *as the target*. **No prompts land
in the targets.** What lands is a **staged branch + an advisory assessment doc** in each target,
**unmerged and unpushed**.

> **Push the proposal, pull the apply.** The human is always the merge authority. This honors the
> Prime Objective's per-instance assent: nothing accrues value from a derivative without that
> derivative's human-authored, per-instance consent.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any is a workflow failure.

1. **Opt-in is a HARD GATE.** A target is eligible only if it declares
   `custodian.accepts_distribution: true` in its OWN `framework-lineage.yaml`. A non-opted-in
   target is **SKIPPED on the write path** — recorded + low-priority ntfy, never written to.
   (`--dry-run` still computes and shows its predicted route as `SKIPPED (opt-in absent)`.)
2. **Pinned traits are absolute.** A file matching a target's `pinned_traits` is **dropped**,
   never staged, never overwritten. A pinned-trait conflict is an **UNMEDIABLE halt** — never
   downgraded to inert.
3. **NEVER push. NEVER touch a target's main.** Staging branches off main and commits only to
   the new branch. No `git push` anywhere in this workflow.
4. **NEVER auto-merge.** Nothing reaches a target's main without the human's explicit merge act.
5. **Fail-soft per target, fail-closed on ambiguity.** One target's failure must not abort the
   others. Any ambiguity about scope, safety, or consent resolves to *skip / halt*, never to
   *proceed*.
6. **Capture everything.** Every per-target verdict and every escalation decision is recorded via
   `scripts/write_event.py`. Uncaptured assessment is lost assessment.
7. **Confidentiality.** Target context is loaded **read-only** into the hub room and never leaves
   it. Any ntfy carries only **target name + route + file counts** — never target-internal content.

## Pre-Flight Checks

```bash
python -c "
import pathlib, sys
errors = []
for s in ['scripts/distribute/repo_safety_check.py','scripts/distribute/change_package.py','scripts/distribute/stage_branch.py','scripts/create_discussion.py','scripts/write_event.py','scripts/close_discussion.py','scripts/notify.py','scripts/ask_developer.py']:
    if not pathlib.Path(s).exists(): errors.append(f'Missing required script: {s}')
for d in ['discussions','docs/adr']:
    if not pathlib.Path(d).exists(): errors.append(f'Missing required directory: {d}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
print('Pre-flight checks passed.')
"
```

If pre-flight fails, tell the developer what's missing and stop.

## Step 1 — Hub setup

1. **Resolve + contain target paths.** Resolve each argument to an absolute path; confirm each is
   an existing directory. Skip (with a recorded note) anything that is not.
2. **Build the offer set** (the framework files this change wants to propagate):
   - `--adr ADR-NNNN`: read `docs/adr/ADR-NNNN-*.md`; collect the framework files it introduces or
     modifies, plus its "constraints to preserve" clauses (these are harm tripwires for Step 2d).
   - `--changelog-since YYYY-MM-DD`: read `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`; collect
     the framework files referenced by entries on/after that date.
   - **Exclude `scope: project` ADRs and their files. Fail closed:** if you cannot determine an
     offered file's scope, exclude it. The offer set is a list of relative, forward-slash framework
     paths under `.claude/`, `scripts/`, `CLAUDE.md`, `docs/templates/`, `docs/adr/`.
3. **Open the hub discussion:**
   ```bash
   python scripts/create_discussion.py "distribute-<slug>" --risk high --mode adversarial
   ```
   Capture the offer set + target list as the first event (intent `evidence`, tag `distribute-setup`).

## Step 2 — Per target (sequential, fail-soft)

Process each target in turn. Wrap the whole loop body so one target's exception is recorded and the
loop continues to the next.

### 2a. Safety preflight (the HARD GATE)

```bash
python scripts/distribute/repo_safety_check.py "<target_path>"
```

Or in-process: `from scripts.distribute.repo_safety_check import repo_safety_check`.

- `report.opted_in is False` → **SKIP** (`skip_reason="not-opted-in"`). Record + low-priority ntfy
  (target name only). On `--dry-run`, still compute Step 2c and report route `SKIPPED (opt-in absent)`.
- `report.is_safe is False` → **SKIP** (`skip_reason="unsafe"`; dirty tree / detached HEAD / mid
  rebase·merge·cherry·revert·bisect / no manifest). Record + low-priority ntfy. Continue.
- Only when `report.can_proceed is True` does the target reach the write path.

### 2b. Load target context (read-only — confidentiality)

Read the target's `framework-lineage.yaml` (pinned_traits, accept/deny paths, drift), `CLAUDE.md`,
and `PHILOSOPHY.md`. This context informs the room **and stays in the hub** — never echo it into a
notification.

### 2c. Change package

```python
from scripts.distribute.change_package import compute_package, package_report
package = compute_package(template_root=".", target_path="<target_path>", offer_set=<offer_set>)
print(package_report(package))   # content-free counts only
```

Classifications: `value` / `inert` (stageable) · `collision-pinned` (drop) · `collision-diverged`
(assess) · `current` / `denied` / `not-accepted` (skip).

### 2d. One-room assessment (adversarial; target context read-only)

**Principle #8 fast-path:** if `package.has_unmediable_candidates()` is **False** (no
`collision-diverged`), the package is obviously-inert → dispatch a **single** `independent-perspective`
risk-referee to confirm nothing harmful slips through. Do **not** convene the full room.

**Full room** (only when `has_unmediable_candidates()` is True): dispatch in parallel —
- `Task(subagent_type="independent-perspective", prompt=<feature-advocate framing: argue value/inert, goal A>)`
- `Task(subagent_type="independent-perspective", prompt=<target-advocate framing: would-harm / pinned / divergence, goal B; loaded with the target's pinned_traits + modified/deleted drift + the changelog/ADR "constraints to preserve">)`
- `Task(subagent_type="independent-perspective", prompt=<referee: adjudicate>)`

(v1 reuses `independent-perspective` with target-context framing; a first-class `target-advocate`
agent is deferred to v1.1.) Score *value* on the inverse 5-dim rubric (Relevance / Value-add / Fit /
Reversibility / Maintenance, /25). **Binary harm + pinned-conflict gates override the score.** Capture
every finding and the per-target verdict via `write_event.py` (tags `distribute,target-<name>`).

### 2e. Route

**MEDIABLE** — no would-harm on staged files; pinned dropped; additive-only divergence; **and the
post-stage quality gate is GREEN**:

```python
from scripts.distribute.stage_branch import stage, detect_base_branch
from scripts.distribute.repo_safety_check import baseline_gate_green

base = detect_base_branch(Path("<target_path>"))   # orchestrator owns base selection
result = stage("<target_path>", package, assessment_doc, "framework-update/<date>-<slug>",
               template_root=".", base_branch=base)
green, summary = baseline_gate_green("<target_path>")   # MANDATORY post-stage (see below)
```

- The **post-stage gate is mandatory** before routing to the human: `stage()` committed with
  `--no-verify`, so this is the integrity check. If the gate is **RED**, the route becomes UNMEDIABLE.
- `assessment_doc` MUST begin with the ADVISORY header (see below).
- On GREEN: `notify` "ready" — **target name + route + counts only**.

**UNMEDIABLE** — would-harm makes the package incoherent / a pinned trait is load-bearing / a
deliberate divergence would be clobbered / post-stage gate RED / target unsafe → **halt this target**
and escalate (see "Escalation" below). Stage nothing.

> ⚠️ **SECURITY — code-execution surface.** `baseline_gate_green` runs the *target's* own
> `scripts/quality_gate.py`. Only run `/distribute` against targets you trust to run code locally
> (the single-owner model). Surface this to the developer if there is any doubt about a target.

### 2f. Lineage record (on the staged branch only)

When a target was staged, append a `distribution_log` entry **on the staged branch** (offered /
staged / dropped / route / hub-discussion id / `status: staged`). Do **NOT** bump the serial or set
drift `current` — that is the human's merge act.

## Step 3 — Wrap-up

Write a synthesis event, then **always** close the discussion (in a `finally`):

```bash
python scripts/close_discussion.py "<discussion_id>"
```

Present a per-target summary table: **staged-ready** (branch + doc path) / **halted-escalated** /
**skipped (not-opted-in)** / **skipped (busy)**. Include assessment-doc paths. No target-internal
content in the summary that will be sent anywhere external.

## Escalation — the untrusted-reply ALLOW-LIST (load-bearing)

When a target routes UNMEDIABLE and the developer may be AFK, ask via ntfy. **The reply is
unauthenticated external input** (the topic slug is the only access control). It MUST be validated
against a fixed allow-list and **never** passed to a subprocess argument, `eval`/`exec`, a file
path, an env var, or any other code/path sink.

```python
from scripts.ask_developer import ask

# The question text is generic (confidentiality): target name + route only.
answer = ask(f"/distribute: {target_name} is UNMEDIABLE. Reply skip / stage-for-manual-review / merge-anyway-accept-risk")
choice = (answer or "").strip().lower()

ALLOWED = {"skip", "stage-for-manual-review", "merge-anyway-accept-risk"}
if choice not in ALLOWED:
    # Timeout (answer is None) OR an off-list reply → DO NOT ACT. Leave the target halted.
    choice = "halt-no-valid-reply"

# Branch on the validated token only — never on the raw reply string.
if choice == "skip":
    ...                       # record, move on
elif choice == "stage-for-manual-review":
    ...                       # stage WITHOUT the post-stage-green requirement; mark doc "manual review required"
elif choice == "merge-anyway-accept-risk":
    ...                       # stage + record explicit human risk-acceptance; STILL never push/auto-merge
else:                          # halt-no-valid-reply
    ...                       # leave halted; record the timeout/off-list reply for display+capture only
```

- 1-hour hard timeout (the `ask()` default). On timeout: record via `write_event.py` (tags
  `ask-developer,timeout`), leave the target halted, continue the loop.
- The raw reply may be **logged / captured into the discussion for display only** — never used as
  a command, path, branch name, or any executable input.
- `merge-anyway-accept-risk` authorizes *staging* with recorded risk-acceptance; it **never**
  authorizes pushing or merging to the target's main (Rule 3 + 4 are absolute).

## Assessment doc — ADVISORY header (required)

Every staged assessment doc begins with:

```markdown
> **ADVISORY / target-overridable.** This assessment was produced by the hub during /distribute.
> It has **no authority** over this project. The target's developer is free to reject, partially
> accept, edit, or override any conclusion here. Nothing in this branch is merged or pushed.
```

Then: the change package (classifications + counts), the room's verdict and findings, the post-stage
gate result, and the list of dropped (pinned) and assess (diverged) files with reasons.

## `--dry-run`

Pure-read. For each target: run 2a–2d and print the change package + **predicted route**, including
`SKIPPED (opt-in absent)` for non-opted-in targets and `SKIPPED (busy)` for unsafe ones. **No writes,
no staging, no commits, no ntfy.** High value, near-free — use it before any live run.

## v1 scope / deferred

- **v1:** the 4 artifacts; explicit offer set; assessment via `independent-perspective`; routing via
  existing notify/ask; on-branch lineage record; sequential + fail-soft; `--dry-run`.
- **Deferred (v1.1+):** first-class `target-advocate` agent; auto-derived offer set per target's
  `distribution_log`; target-side `/lineage adopt` re-baseline on merge; parallel targets.
