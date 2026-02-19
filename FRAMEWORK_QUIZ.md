---
quiz_id: QUIZ-FRAMEWORK-20260218
module: AI-Native Agentic Development Framework
target_audience: Developer with vibe-coding background
bloom_distribution: {understand: 6, apply: 3, analyze: 2, evaluate: 2}
pass_threshold: 0.70
question_count: 13
time_estimate: 25-30 minutes
open_book: true
---

# Framework Architecture Quiz

## Instructions

This is an **open book** quiz. You may refer to CLAUDE.md, the agent definitions, rules files, and source code while answering. The goal is not to test memory but to verify that you can **apply and analyze** the framework's concepts in context.

**Passing threshold: 70% (9/13 correct)**

For each question, explain your reasoning in your own words. Correct answers should reference specific files, principles, or design patterns from the framework.

---

## Understanding (60-70% of quiz) - Questions 1-6

### Question 1: Four-Layer Capture Stack [Understand]

**Question:**
Explain the purpose of each layer in the 4-layer capture stack. Why is immutability (Layer 1) important? Why can't you just use SQLite (Layer 2)?

**Reference:** CLAUDE.md, "Four-Layer Capture Stack"

**Your Answer:**

---

### Question 2: Agent Specialization [Understand]

**Question:**
Why does the framework have 9 separate agents instead of one powerful generalist agent? Name at least 3 agents and explain what each specializes in and why that specialism matters.

**Reference:** CLAUDE.md, ".claude/agents/" directory

**Your Answer:**

---

### Question 3: When Specialists Activate [Understand]

**Question:**
The facilitator doesn't activate all 9 specialists for every change. Explain the principle behind *when* specialists are activated. Give an example: what specialists would review a documentation-only change vs. a security-critical authentication change?

**Reference:** facilitator.md, "Dynamic Activation"

**Your Answer:**

---

### Question 4: The Quality Gate as Enforcement [Understand]

**Question:**
The quality gate (quality_gate.py) is both a standalone script AND a git pre-commit hook. Explain:
- What 5 checks does the quality gate run?
- Why is it important that it's automated (not manual)?
- What happens if it fails?

**Reference:** quality_gate.py, CLAUDE.md "Quality Gate"

**Your Answer:**

---

### Question 5: Secret Scanning: Flag vs. Block [Understand]

**Question:**
The secret detection hook detects 12 API key patterns but **flags** them instead of hard-blocking. Why is flagging (human review) better than blocking automatically? Under what circumstances might a developer intentionally write content that matches secret patterns?

**Reference:** CLAUDE.md, "Hooks" → "File Locking + Secret Detection"

**Your Answer:**

---

### Question 6: Education Gate Progression [Understand]

**Question:**
The educator recommends different intensities based on developer competence:
- **New developers or new domains:** full walkthrough + quiz + explain-back
- **Demonstrated competence:** abbreviated walkthrough + targeted questions
- **Expert level:** quick summary + "anything surprising?" check

Why does intensity adapt? What does "scaffolding should fade" mean?

**Reference:** educator.md, "Adaptive Intensity" and "Anti-Patterns to Avoid"

**Your Answer:**

---

## Apply (20-30% of quiz) - Questions 7-9

### Question 7: Trace a Code Change End-to-End [Apply]

**Question:**
You've added a new API endpoint `/todos/{id}/share` that allows users to share todos with other users. This involves authentication, database writes, and potential permission issues.

Trace the entire flow from "you write code" to "commit lands on main":

1. What hooks fire as you write the code?
2. When you run `/review`, which specialists would the facilitator activate? Why each one?
3. What findings would you expect from each specialist?
4. What gates must pass before the code commits?
5. Why might the education gate be recommended?

**Reference:** CLAUDE.md all sections, facilitator.md, educator.md, quality_gate.py

**Your Answer:**

---

### Question 8: External Project Analysis [Apply]

**Question:**
You discover an open-source project that implements a sophisticated caching layer. You want to evaluate if you should adopt their pattern.

Walk through the process:
1. What command would you use to analyze it?
2. How does project-analyst differ from other agents (specifically, what permission do they have)?
3. What 5 dimensions are patterns scored on?
4. What threshold must be met for a recommendation?
5. What's the "Rule of Three" and why does it matter?

**Reference:** CLAUDE.md "External Project Analysis", project-analyst.md

**Your Answer:**

---

### Question 9: Debugging a Commit That Failed [Apply]

**Question:**
You run `git commit` and it fails with a message from the pre-commit gate. The output says:

```
Quality Gate: FAILED (3/5 passed)
  PASS  Formatting (ruff format)
  FAIL  Linting (ruff check)
  PASS  Tests (pytest)
  FAIL  Coverage (>= 80%)
  SKIP  ADR completeness
```

What do you do next? Walk through the steps to get the commit to succeed, referencing specific commands and files.

**Reference:** quality_gate.py, commit_protocol.md

**Your Answer:**

---

## Analyze (15-20% of quiz) - Questions 10-11

### Question 10: Why Model Tiering? [Analyze]

**Question:**
The framework uses three model tiers:
- **Opus**: Facilitator, architecture-consultant (complex reasoning)
- **Sonnet**: 6 other specialists (analysis, evaluation)
- **Haiku**: Educator (mechanical verification)

Why is this better than using the same model (e.g., always opus) for everything? Consider both cost and quality.

**Reference:** CLAUDE.md "Agent Architecture" → "model: tier"

**Your Answer:**

---

### Question 11: Independence vs. Collaboration [Analyze]

**Question:**
The framework emphasizes "independence prevents confirmation loops" (Principle #4). But it also has 5 collaboration modes (Ensemble, Yes And, Structured Dialogue, Dialectic, Adversarial).

How can both independence AND collaboration be true? When would you use Ensemble (most independent) vs. Structured Dialogue (most collaborative)? What are the trade-offs?

**Reference:** CLAUDE.md "Collaboration Mode Spectrum", facilitator.md "Core Responsibilities"

**Your Answer:**

---

## Evaluate (5-10% of quiz) - Questions 12-13

### Question 12: Least-Complex Intervention [Evaluate]

**Question:**
Principle #8 says: "When improving the framework, prefer prompt changes before command/tool changes before agent definition changes before architectural changes."

You notice that specialists are over-flagging issues in their domains (crying wolf). For example, security-specialist flags every use of `os.system` as a vulnerability, even when arguments are hardcoded.

**Evaluate these solutions in order of complexity:**

A) Update the security-specialist's prompt to be clearer about when `os.system` is actually risky
B) Add a new rule to security_baseline.md explaining the criteria for flagging `os.system`
C) Modify security-specialist.md to add anti-patterns (e.g., "Do NOT flag hardcoded os.system calls")
D) Reorganize the agent architecture to split security-specialist into two agents (one for critical risks, one for best practices)

Which would you try first? Second? Why? Are there cases where you'd jump to C or D?

**Reference:** CLAUDE.md "Least-Complex Intervention First" and Principle #8

**Your Answer:**

---

### Question 13: Change Impact - What If? [Evaluate]

**Question:**
Scenario: You're considering whether to **remove the independent-perspective agent** to save token cost.

Evaluate the impact:
1. What role does independent-perspective play that other agents don't?
2. What types of bugs or architectural issues would you lose the ability to catch?
3. What principle would this violate?
4. Is there a less complex intervention that could reduce cost without removing the agent?

**Reference:** independent-perspective.md, facilitator.md "Persona Bias Detection", Principle #3

**Your Answer:**

---

## Scoring Guide (for Self-Assessment)

### Understanding Questions (1-6)

Each question should demonstrate you can:
- Define the concept clearly
- Explain the rationale behind the design
- Reference specific files or principles

**Acceptable answer criteria:**
- Accurate definition (not vague or incomplete)
- At least one reason given for the design choice
- Specific reference to documentation (file or principle name)

### Apply Questions (7-9)

Each question should demonstrate you can:
- Trace a multi-step process
- Make decisions about which specialists/gates are involved
- Explain why each decision was made

**Acceptable answer criteria:**
- Complete step-by-step walkthrough
- Justification for each specialist/tool choice
- Reference to specific commands or principles

### Analyze Questions (10-11)

Each question should demonstrate you can:
- Compare alternatives and their trade-offs
- Understand why one design was chosen over another
- Reason about costs and benefits

**Acceptable answer criteria:**
- Identifies at least 2 trade-offs
- References both cost and quality dimensions
- Explains the decision rationale

### Evaluate Questions (12-13)

Each question should demonstrate you can:
- Assess solutions against criteria (cost, reversibility, impact)
- Identify second-order effects
- Make principled decisions

**Acceptable answer criteria:**
- Ranks solutions with clear reasoning
- Identifies risks or second-order effects
- References principles or design philosophy

---

## Debug Scenario (Bonus - Understand + Apply)

**Bonus Question: 0.5 points**

You run `/review` on a new feature. The discussion captures these events:

```json
{"timestamp": "14:30:00", "agent": "security-specialist", "intent": "proposal", "confidence": 0.95, "content": "Found SQL injection vulnerability..."}
{"timestamp": "14:31:00", "agent": "qa-specialist", "intent": "proposal", "confidence": 0.90, "content": "Test coverage gap in error handling..."}
{"timestamp": "14:32:00", "agent": "facilitator", "intent": "synthesis", "confidence": 0.88, "content": "..."}
{"timestamp": "14:33:00", "agent": "architecture-consultant", "intent": "critique", "confidence": 0.92, "content": "I don't think this is SQL injection..."}
```

What happened here? Why did architecture-consultant critique security-specialist's finding? How should the facilitator handle this disagreement?

**Your Answer:**

---

## Reflection Questions (Optional - For Your Own Learning)

After finishing the quiz, reflect on:

1. What part of the framework was hardest to understand? Why?
2. What surprised you most about the design choices?
3. Are there any principles you disagree with? Why?
4. What would you change if redesigning from scratch?

These don't affect your score but help consolidate learning.

---

## Next Steps

- **If you score ≥ 70%:** You understand the framework architecture. Proceed to explain-back assessment.
- **If you score < 70%:** Review the walkthrough sections corresponding to incorrect answers, then re-attempt.
- **After passing:** Run `/build_module` to put the framework in practice. Build something small and observe how the system works end-to-end.

---

## Explain-Back Assessment (After Quiz)

Once you've passed the quiz, you'll be asked to explain back:

1. **Core Philosophy**: Why is "reasoning is the primary artifact"? How does this change how you develop software?

2. **A Design Trade-Off**: Pick one principle and explain a trade-off it creates. Example: "Education gates before merge adds time but prevents shipping code developers don't understand. When might you skip the education gate?"

3. **System Interactions**: Pick two subsystems (e.g., hooks + quality gate, capture stack + agents, rules + specialists) and explain how they reinforce each other.

These are open-ended and want to assess whether you can generalize from specifics to broader architectural thinking.

---

**Quiz ID:** QUIZ-FRAMEWORK-20260218
**Duration:** 25-30 minutes
**Pass Threshold:** 70% (9/13 correct)
**Format:** Open book, reference all framework files as needed
