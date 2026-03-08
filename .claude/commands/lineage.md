---
description: "Show framework lineage status, drift analysis, and manifest validation."
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
argument-hint: "[--validate | --drift-report]"
---

# Lineage Status Workflow

You are acting as the Facilitator. Dispatch the Steward agent to report on framework lineage.

## CRITICAL BEHAVIORAL RULES

1. **NEVER modify the manifest without developer confirmation**: The Steward observes and reports; changes require approval.
2. **ALWAYS capture results**: Create a discussion and record the Steward's findings.
3. **ALWAYS close the discussion**: Every lineage check must end with `scripts/close_discussion.py`.

## Pre-Flight Checks

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('framework-lineage.yaml').exists():
    errors.append('No framework-lineage.yaml found. Run: python scripts/lineage/init_lineage.py --project-name YOUR_PROJECT --template-version 2.1.0')
for script in ['scripts/lineage/manifest.py', 'scripts/lineage/drift.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the manifest doesn't exist, tell the developer to initialize lineage first:
```bash
python scripts/lineage/init_lineage.py --project-name "project-name" --template-version "2.1.0"
```

## Step 1: Create Discussion

```bash
python scripts/create_discussion.py "lineage-status" --risk low --mode ensemble
```

Store the returned discussion ID.

## Step 2: Determine Mode

Parse the arguments to determine which mode to run:

- **No arguments** (bare `/lineage`): Show summary status
- **`--validate`**: Validate manifest integrity
- **`--drift-report`**: Full drift scan with per-file details

## Step 3: Dispatch Steward

Dispatch the Steward agent via Task to perform the requested operation:

```
Task(subagent_type="steward", prompt="Lineage Check: <discussion_id>
Mode: <status|validate|drift-report>

Perform a lineage <mode> check for this project.

For status: Read framework-lineage.yaml and report the summary (project name, version, type, drift status, divergence distance, pinned traits count, serial).

For validate: Run `python scripts/lineage/manifest.py --validate` and report the results. Also verify that the drift status in the manifest matches reality by running a quick drift scan.

For drift-report: Run `python scripts/lineage/drift.py` and present the full drift report. Highlight any files that may need attention (modified but not pinned).

Report your findings in the standard Steward output format.")
```

## Step 4: Capture Results

```bash
python scripts/write_event.py "<discussion_id>" "steward" "evidence" "<steward_findings>" --confidence <score> --tags "lineage,<mode>"
```

## Step 5: Present to Developer

Present the Steward's findings:
1. Summary status (always shown)
2. Validation results (if `--validate`)
3. Drift report (if `--drift-report`)
4. Recommendations (if any drift detected)

## Step 6: Close Discussion

```bash
python scripts/close_discussion.py "<discussion_id>"
```
