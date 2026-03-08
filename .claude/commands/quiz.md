---
description: "Run a Bloom's-taxonomy-based quiz on code to assess developer understanding. Education gate step 2."
allowed-tools: ["Read", "Glob", "Grep", "Bash", "Task", "Write"]
argument-hint: "[file or directory to quiz on]"
---

# Bloom's-Based Code Quiz (Education Gate Step 2)

Delegate to the educator agent to generate and administer a quiz.

## CRITICAL BEHAVIORAL RULES

These rules are pass/fail. Violating any of them is a workflow failure.

1. **NEVER skip capture**: The educator's quiz generation and the facilitator's results summary MUST be recorded via `scripts/write_event.py`. No quiz exists unless captured.
2. **NEVER continue on failure**: If any step fails (script error, agent dispatch failure), HALT immediately. Present the error and ask the user how to proceed.
3. **ALWAYS close the discussion**: Every quiz session MUST end with `scripts/close_discussion.py`, even if abandoned.

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
for script in ['scripts/create_discussion.py', 'scripts/write_event.py', 'scripts/close_discussion.py']:
    if not pathlib.Path(script).exists():
        errors.append(f'Missing required script: {script}')
if errors:
    print('PRE-FLIGHT FAILED:'); [print(f'  - {e}') for e in errors]; sys.exit(1)
else:
    print('Pre-flight checks passed.')
"
```

If the target file or directory specified by the user does not exist, tell the developer and ask for the correct path.

## Workflow

### Step 1: Create Discussion

```
python scripts/create_discussion.py "quiz-<slug>" --risk low --mode ensemble
```

Store the returned discussion ID.

### Step 2: Generate Quiz

Dispatch to the educator agent:
```
Task(subagent_type="educator", prompt="Generate a Bloom's-taxonomy-based quiz for the following code.\n\nRequirements:\n- 6-10 questions\n- 60-70% Understand/Apply level\n- 30-40% Analyze/Evaluate level\n- At least 1 debug scenario question\n- At least 1 change-impact question\n- Tag each question with Bloom's level and question type\n- Include answer key with rubric\n\nCode:\n<code content>")
```

**Capture the generated quiz**:
```
python scripts/write_event.py "<discussion_id>" "educator" "proposal" "<quiz content with answer key>" --confidence <score> --tags "quiz,education,blooms-taxonomy"
```

### Step 3: Administer Quiz

Present questions to the developer one at a time or all at once (developer's preference). This is "open book" — the developer can look at the code but must explain in their own words.

### Step 4: Evaluate Responses

For each answer, assess:
- Does the developer demonstrate understanding at the target Bloom's level?
- Score each question 0-1
- Pass threshold: 70% overall

### Step 5: Record Results

For each question, record via:
```
python scripts/record_education.py "<session_id>" "<discussion_id>" "<bloom_level>" "<question_type>" <score> <passed>
```

Capture the overall results as a facilitator event:
```
python scripts/write_event.py "<discussion_id>" "facilitator" "synthesis" "Quiz results: <overall_score>% (<pass/fail>). Breakdown by Bloom's level: <details>. Strengths: <areas>. Gaps: <areas>." --confidence 0.9 --tags "quiz,results,education"
```

### Step 6: Close Discussion

```
python scripts/close_discussion.py "<discussion_id>"
```

### Step 7: Report

Present results:
- Overall score and pass/fail
- Breakdown by Bloom's level
- Areas of strength and areas needing more study
- If failed, recommend specific areas to review before retaking
