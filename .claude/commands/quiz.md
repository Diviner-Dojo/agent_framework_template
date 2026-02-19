---
description: "Run a Bloom's-taxonomy-based quiz on code to assess developer understanding. Education gate step 2."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task", "Write"]
argument-hint: "[file or directory to quiz on]"
---

# Bloom's-Based Code Quiz (Education Gate Step 2)

Delegate to the educator agent to generate and administer a quiz.

## Pre-Flight Checks

Before starting the quiz, verify prerequisites:

```bash
python -c "
import pathlib, sys
errors = []
if not pathlib.Path('.claude/agents/educator.md').exists():
    errors.append('Missing educator agent definition: .claude/agents/educator.md')
if not pathlib.Path('scripts/record_education.py').exists():
    errors.append('Missing education recording script: scripts/record_education.py')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the target file or directory specified by the user does not exist, tell the developer and ask for the correct path.

## Workflow

### Step 1: Generate Quiz

Dispatch to the educator agent:
```
Task(subagent_type="educator", prompt="Generate a Bloom's-taxonomy-based quiz for the following code.\n\nRequirements:\n- 6-10 questions\n- 60-70% Understand/Apply level\n- 30-40% Analyze/Evaluate level\n- At least 1 debug scenario question\n- At least 1 change-impact question\n- Tag each question with Bloom's level and question type\n- Include answer key with rubric\n\nCode:\n<code content>")
```

### Step 2: Administer Quiz

Present questions to the developer one at a time or all at once (developer's preference). This is "open book" — the developer can look at the code but must explain in their own words.

### Step 3: Evaluate Responses

For each answer, assess:
- Does the developer demonstrate understanding at the target Bloom's level?
- Score each question 0-1
- Pass threshold: 70% overall

### Step 4: Record Results

For each question, record via:
```
python scripts/record_education.py "<session_id>" "<discussion_id>" "<bloom_level>" "<question_type>" <score> <passed>
```

### Step 5: Report

Present results:
- Overall score and pass/fail
- Breakdown by Bloom's level
- Areas of strength and areas needing more study
- If failed, recommend specific areas to review before retaking
