---
document_type: Education Gate Kickoff
phase: Step 1 - Walkthrough (You are here)
next_phase: Step 2 - Quiz
duration: 60-90 minutes total (45-60 walkthrough + 25-30 quiz)
---

# Framework Education Gate - Start Here

## What's Happening

You built the **AI-Native Agentic Development Framework v2.1** using intuitive "vibe coding" — iteration without fully planning the architecture first. The result is a thoughtful system that enforces 8 principles across multiple interconnected subsystems.

Now comes the education gate: we're ensuring you deeply understand what you built.

This gate has three steps:

1. **Walkthrough** ← You just received this (WALKTHROUGH.md)
2. **Quiz** ← Next (FRAMEWORK_QUIZ.md)
3. **Explain-Back** ← Final (verbal assessment)

---

## The Walkthrough You Just Received

**File:** `/c/Work/AI/AI Gen Framework Research/agent_framework_template/WALKTHROUGH.md`

**Length:** ~8,000 words, 11 sections, 45-60 minutes to read

**Structure:** Progressive disclosure from high-level architecture to implementation details

**Why this structure?**
- Most walkthroughs narrate code line-by-line ("here's a function, here's what it does")
- This one explains **decisions and design intent** ("why did you choose this pattern over that?")
- Starts with "what is this thing?" (mental model) then builds toward specifics

**Sections:**
1. Mental Model — What's the core insight?
2. Agent Architecture — Why 9 specialists?
3. Rules Stack — What standards do agents enforce?
4. Capture Pipeline — How does reasoning become data?
5. Hooks — What fires automatically?
6. Commands — What's the user interface?
7. Application Code — What's the subject?
8. End-to-End Flow — How does a code change move through the system?
9. Meta Loops — How does the framework improve itself?
10. Philosophy — Why these design choices?
11. Summary — What did you build?

---

## Reading Strategy

Don't try to absorb everything in one sitting. Use this strategy:

### Session 1: Mental Model + Architecture (30 minutes)
- Read Part 1 (Mental Model)
- Read Part 2 (Agent Architecture)
- Stop. Process what you've learned.
- Question: Can you name the 9 agents and one specialty for each?

### Session 2: Systems & Rules (30 minutes)
- Read Part 3 (Rules Stack)
- Read Part 4 (Capture Pipeline)
- Read Part 5 (Hooks)
- Stop.
- Question: What's the difference between Layer 1 and Layer 2 capture? Why both?

### Session 3: Flow & Philosophy (30 minutes)
- Read Part 8 (End-to-End Flow) — this is the most concrete
- Read Part 10 (Philosophy) — this ties it all together
- Read Part 11 (Summary)

### Session 4: Commands & Self (15 minutes)
- Skim Part 6 (Commands) — reference material, not critical
- Skim Part 7 (Application Code) — context, not critical
- Skim Part 9 (Meta Loops) — interesting but can read later

---

## Key Insights to Look For

As you read, pay attention to these concepts:

### 1. "Reasoning is Primary"
Code is the output. Decisions and trade-offs are the artifact. Every significant decision is captured immutably.

**Why?** Because in 2 years, someone reading the code needs to know why it was built that way. The reasoning outlasts the code.

### 2. "Independence Prevents Confirmation Loops"
Multiple agents analyze code independently (isolated context), then findings are synthesized. This prevents groupthink where everyone converges on one answer too quickly.

**Why?** Because when one person writes and another person reviews, they anchor to the same solution. Independence preserves the chance someone asks "but what if...?" and catches a real issue.

### 3. "Capture is Automatic"
When you run `/review`, a discussion directory is created *before* any agent analyzes. There's no way to skip recording. Enforced at the command layer.

**Why?** Because humans are bad at deciding what's "worth recording." You build this discipline into the tools.

### 4. "Specialization Improves Judgment"
9 specialists, not 1 generalist. Security-specialist reviews for threats. Performance-analyst for algorithms. Independent-perspective for hidden assumptions.

**Why?** Because a generalist reviewing code for "any issues" either over-flags (cries wolf) or under-flags (misses specifics). Specialists are sharper.

### 5. "Education Gates Before Merge"
Developers must demonstrate understanding (walkthrough + quiz + explain-back) before shipping complex code.

**Why?** Because code you don't understand breaks in ways you can't predict. If you can't explain the design trade-offs, you can't maintain it.

---

## After Reading: Self-Check

After finishing the walkthrough, ask yourself:

**Understand:**
- Can you explain the 4-layer capture stack?
- Can you name the 9 agents and one specialty for each?
- What's the difference between a "low-risk" change review and a "high-risk" one?

**Apply:**
- Walk through a code change end-to-end (write → review → education gate → commit). At each step, what happens?
- If you add a new security rule to security_baseline.md, how does it affect all future reviews?

**Analyze:**
- Why use model tiering (opus, sonnet, haiku) instead of always using opus?
- Why 4 layers of capture instead of just SQLite?

**Evaluate:**
- Is 80% code coverage the right threshold? Why not 75%? 90%?
- If you removed the independent-perspective agent, what would you lose?

If you can answer these, you're ready for the quiz.

---

## The Quiz

**File:** `/c/Work/AI/AI Gen Framework Research/agent_framework_template/FRAMEWORK_QUIZ.md`

**Length:** 13 questions, 25-30 minutes

**Format:** Open book — reference all framework files as you answer

**Passing Threshold:** 70% (9/13 correct)

**Question Breakdown:**
- 6 Understanding questions (60%) — "Explain X. Why is it designed this way?"
- 3 Apply questions (20%) — "Trace this process. What happens at each step?"
- 2 Analyze questions (15%) — "Compare alternatives. What are the trade-offs?"
- 2 Evaluate questions (5%) — "Assess this solution against the principles."

**Key Rules:**
- Explain in your own words (copy-paste doesn't count as understanding)
- Reference specific files (e.g., "CLAUDE.md, Principle #4")
- For trace questions, walk through step-by-step with concrete examples
- You don't need 100% — 70% passes. You can miss 4 questions.

---

## After Quiz: Explain-Back

If you pass the quiz (≥70%), you'll be asked to explain three things:

1. **Core Philosophy**: Why is "reasoning the primary artifact"? How does this change software development?

2. **A Design Trade-Off**: Pick a principle and explain what it costs and when you might violate it. Example: "Education gates add time but prevent shipping code developers don't understand."

3. **System Interactions**: Pick two subsystems and explain how they reinforce each other. Example: "The capture pipeline records findings. `/meta-review` queries those findings to assess specialist effectiveness. Specialists improve based on feedback."

These are open-ended and assess whether you can **generalize** from specifics to broader thinking.

---

## Educator Notes

I've also created **EDUCATOR_NOTES.md** for your reference. It contains:

- Why the walkthrough is structured this way
- Common knowledge gaps and how to fill them
- Mastery tier assessment (you're working at Tier 2: Complex Systems)
- Practical tips for taking the quiz
- What happens after you pass

Read this if you get stuck on any concept.

---

## Timeline

**Recommended:**

| Phase | Time | Action |
|-------|------|--------|
| Today | 60 min | Read WALKTHROUGH.md (break into 2-3 sessions) |
| Today or Tomorrow | 30 min | Take FRAMEWORK_QUIZ.md |
| Tomorrow | 15 min | Explain-back assessment (if passing quiz) |

**Total time: ~105 minutes spread over 1-2 days**

---

## Files You'll Reference

Keep these open while reading/taking the quiz:

- `/c/Work/AI/AI Gen Framework Research/agent_framework_template/CLAUDE.md` — Constitution + principles
- `/c/Work/AI/AI Gen Framework Research/agent_framework_template/.claude/agents/*.md` — Agent definitions
- `/c/Work/AI/AI Gen Framework Research/agent_framework_template/.claude/rules/*.md` — Standards files
- `/c/Work/AI/AI Gen Framework Research/agent_framework_template/scripts/quality_gate.py` — Enforcement
- `/c/Work/AI/AI Gen Framework Research/agent_framework_template/scripts/create_discussion.py` — Capture pipeline

---

## Success Looks Like

After completing this education gate, you'll be able to:

- **Explain** why each component exists (agent, rule, hook, command)
- **Trace** a complete code change from write to commit
- **Reason about** trade-offs in the design
- **Connect** how subsystems reinforce each other
- **Apply** the framework to improve real code

Most importantly: you'll have transformed intuitive knowledge ("I know this is good design") into explicit knowledge ("I can articulate why this design choice was made").

---

## Struggling? Here's What to Do

### If you find the walkthrough overwhelming:
- This is normal for a complex system. Read in 30-minute chunks.
- After each chunk, pause and summarize: "In one sentence, what did I just learn?"
- Skim the reference section at the end of WALKTHROUGH.md for quick context.

### If you don't understand a concept:
- Go to EDUCATOR_NOTES.md and look for "Knowledge Gaps to Watch For"
- Find the relevant reference file (CLAUDE.md, agent definition, script)
- Read the reference section carefully, not just skimming

### If you're unsure about a quiz question:
- It's open book. Look up the answer in the reference files.
- Explain your reasoning, not just the answer.
- 70% passing threshold means you don't need to get everything right.

### If you fail the quiz:
- Review the walkthrough sections corresponding to your weak areas
- Take the quiz again (it's not a final exam, it's a learning checkpoint)
- Ask clarifying questions about concepts you don't understand

---

## Ready?

1. Read the walkthrough: `/c/Work/AI/AI Gen Framework Research/agent_framework_template/WALKTHROUGH.md`
2. Take the quiz: `/c/Work/AI/AI Gen Framework Research/agent_framework_template/FRAMEWORK_QUIZ.md`
3. Complete explain-back if you pass

**Estimated time: 90 minutes total, spread over 1-2 days**

---

## One Final Note

You built this framework through vibe coding — intuitive iteration. The fact that it's coherent and principled suggests you have strong architectural instincts.

This education gate is ensuring your intuitive knowledge becomes explicit. That's not busywork — it's the difference between "I know this is good" and "I can teach this to someone else."

Let's verify your understanding.

---

**Next Step:** Open WALKTHROUGH.md and begin reading.

Good luck.
