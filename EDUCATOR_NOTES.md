---
document_type: Educator Notes
target: Framework Developer (you)
created: 2026-02-18
phase: Education Gate - Walkthrough Complete, Quiz Pending
---

# Educator's Notes: Framework Learning Path

## What You Just Read

The **WALKTHROUGH.md** you received is a 11-part guided walkthrough of the AI-Native Agentic Development Framework. It was structured progressively:

1. **Mental Model** (Part 1) — What does this thing actually do?
2. **Agent Architecture** (Part 2) — Why 9 agents? How do they work?
3. **Rules Stack** (Part 3) — What standards do agents enforce?
4. **Capture Pipeline** (Part 4) — How does reasoning become data?
5. **Hooks** (Part 5) — What fires automatically?
6. **Commands** (Part 6) — What's the user interface?
7. **Application Code** (Part 7) — What's the subject?
8. **End-to-End Flow** (Part 8) — How does a code change move through the system?
9. **Meta Loops** (Part 9) — How does the framework improve itself?
10. **Philosophy** (Part 10) — Why were these design choices made?
11. **Summary** (Part 11) — What did you actually build?

Each section explained **decisions and design intent**, not line-by-line code narration.

---

## The Quiz: What It Tests

**FRAMEWORK_QUIZ.md** has 13 questions distributed across Bloom's levels:

- **6 Understanding questions** (60%): Can you explain concepts?
- **3 Apply questions** (20%): Can you trace processes and make decisions?
- **2 Analyze questions** (15%): Can you compare alternatives and trade-offs?
- **2 Evaluate questions** (5%): Can you assess solutions against principles?

The quiz is **open book** — you should reference CLAUDE.md, agent definitions, and code while answering. The goal is not memorization but **demonstrating you can apply the framework's concepts**.

**Pass threshold: 70% (9/13 correct)**

---

## Why This Structure? (Educator Perspective)

### Scaffolding

The walkthrough starts with "what is this?" (mental model) and progressively builds toward "how does it all work together?" (end-to-end flow). This is **progressive disclosure** — you see the big picture first, then details in context.

Without this scaffolding, diving directly into agent definitions or hook scripts would feel like drowning in specifics without understanding why they exist.

### Mix of Question Types

The quiz is intentionally unbalanced:
- **60% Understanding/Apply** because that's what matters for day-to-day work
- **40% Analyze/Evaluate** because that's what matters for improving the framework

You don't need to memorize obscure implementation details. You need to understand when to activate which specialist and why certain principles exist.

### Open Book

This isn't a test of your memory. It's a test of whether you can **read the code/docs, connect concepts, and explain them in your own words**. If you need to check something, that's fine — that's actually the expected workflow.

---

## Mastery Tier Assessment

You're working at **Tier 2: Complex Systems Design**.

Your framework involves:
- Async patterns (parallel agents)
- Distributed systems concepts (multi-agent orchestration)
- State management (capture stack, BUILD_STATUS.md)
- Complex decision logic (risk assessment, specialist activation)

For Tier 2, the educator assesses:
- Do you understand concurrency/parallelism implications?
- Can you trace failure modes?
- Do you recognize second-order effects (e.g., "if independent-perspective fails, what else breaks?")?

---

## After the Quiz: Explain-Back

Once you pass the quiz (≥70%), you'll be asked to explain back three things:

### 1. Core Philosophy: "Reasoning is Primary"

Explain in your own words:
- What does it mean to treat reasoning as the primary artifact?
- How is this different from traditional code review?
- When should you violate this principle (if ever)?

**Example good answer:**
> "Instead of code being the permanent record and reasoning being ephemeral (forgotten), we reverse it. Every significant decision is captured immutably. In 2 years, someone reads the discussion not just the code. This means decisions are explainable and defensible — we're not trapped in 'but why is it like that? dunno, it was like that when I started.'"

### 2. A Design Trade-Off

Pick one principle or design choice and explain:
- Why was this choice made?
- What does it cost?
- When might you make a different choice?

**Example:** Principle #6 (Education gates before merge)
> "Education gates add time but prevent shipping code developers don't understand. The trade-off: slower shipping but fewer surprise bugs down the road. You might skip the gate for a trivial typo fix, but not for security-critical code. The intensity adapts."

### 3. System Interactions

Pick two subsystems and explain how they reinforce each other.

**Example:** Capture Pipeline + Specialists
> "When security-specialist makes a finding, it's recorded in events.jsonl. Later, `/meta-review` can query 'how often did security-specialist flag SQL injection?' This feedback loop lets you assess specialist effectiveness. If a specialist's flags never result in bugs, maybe they're over-flagging. The capture system makes this visible."

**Example:** Hooks + Quality Gate
> "Hooks auto-format after every save. The quality gate checks formatting. Because formatting is automatic, the quality gate almost always passes formatting checks, which means developers can focus on substantive issues (logic, security, performance). The automation removes noise."

---

## Then What? (Mastery Progression)

After explain-back, you've completed the education gate for the framework. The next steps:

### Level A: Apply the Framework (Hands-On)

Try this exercise:

1. Create a small feature (e.g., "add filtering to the Todo list")
2. Run `/review` on your changes
3. Observe:
   - Which specialists activate?
   - What findings emerge?
   - How does the capture pipeline work in practice?
   - Do the findings make sense?
4. Address findings
5. Run the full education gate if warranted

This grounds abstract knowledge in concrete experience.

### Level B: Extend the Framework (Deliberate Improvement)

Once familiar, identify one thing to improve:
- Add a new specialist for a domain you care about (accessibility, performance, user experience)?
- Refine an existing specialist's anti-patterns?
- Add a new rule to an existing rules file?
- Create a new command that orchestrates existing specialists?

Start with **Principle #8: Least-Complex Intervention First**. Don't redesign the agent architecture; just improve a prompt or add a rule.

### Level C: Reflect on the Meta-Loop

Run:
```
/meta-review
```

This evaluates the framework itself. Read the reflection. Do you agree with the assessment? Are there improvements you'd recommend?

---

## Knowledge Gaps to Watch For

As you work through the quiz, you'll discover what you already know deeply vs. what's still fuzzy. Here are common gaps:

### Gap 1: "I don't fully understand the 4-layer capture stack"

This is normal — it's the most abstract part. Go back to CLAUDE.md and read:
- "Four-Layer Capture Stack" section
- "Capture Pipeline" section
- Read actual scripts: `create_discussion.py`, `write_event.py`, `close_discussion.py`

The key insight: Layer 1 (immutable files) + Layer 2 (queryable index) + Layer 3 (curated knowledge) form a progression from "raw data" to "actionable insight."

### Gap 2: "I'm confused about when specialists activate"

Go back to **facilitator.md** and read "Dynamic Activation." The rule is simple:
- Low risk → fewer specialists
- Medium risk → standard team
- High risk → full panel + independent-perspective

Match the change type (API change, security, architecture, etc.) to specialists. Facilitator does this assessment.

### Gap 3: "I don't understand the collaboration mode spectrum"

Go back to CLAUDE.md "Collaboration Mode Spectrum" and facilitator.md. The spectrum is:
1. **Ensemble** (independent, no exchange) ← use for low-risk
2. **Yes, And** (sequential building)
3. **Structured Dialogue** (multi-round, default) ← use for medium
4. **Dialectic** (thesis-antithesis-synthesis)
5. **Adversarial** (red team) ← use for security reviews only

Higher collaboration modes cost more tokens but catch more issues. Use the lowest mode that matches the risk level.

### Gap 4: "I don't understand why the independent-perspective agent exists"

Read **independent-perspective.md** carefully. The agent operates with **minimal prior context** — it's not anchored to your existing solution. While others say "looks fine," it asks "but what if that assumption breaks?"

This prevents groupthink. Example: 3 specialists say "this SQL is fine," but independent-perspective asks "what if the database is slow?" and catches an N+1 query that would cause outages at scale.

---

## Success Criteria for This Education Gate

You've completed the walkthrough successfully if:

- [ ] You can explain the 4-layer capture stack and why it's designed that way
- [ ] You can name all 9 agents and one specialty for each
- [ ] You understand why specialists activate dynamically (risk-based)
- [ ] You can trace a code change from write → review → education gate → commit
- [ ] You understand the philosophy (reasoning is primary, independence prevents groupthink, etc.)

If you can do these things, you're ready to pass the quiz.

---

## The Quiz: Practical Tips

### Before Starting

1. Have CLAUDE.md open in one window
2. Have the `.claude/agents/` directory open in another
3. Have `quality_gate.py` open for reference
4. Have `scripts/` directory open for capture pipeline scripts

### While Answering

- **Type in your own words.** Copy-pasting from docs means you haven't synthesized the knowledge.
- **Reference specific files.** "As stated in CLAUDE.md under Principle #1..." is better than vague references.
- **Trace concrete examples.** For apply questions, walk through a specific scenario step-by-step.
- **Explain your reasoning.** "I chose this because..." is better than just the answer.

### For Questions You're Unsure About

- Read the reference file carefully
- Try to trace a concrete example
- If still stuck, move on and come back later

You don't need 100% — 70% is passing. Missing 4 questions is fine.

---

## After Quiz: Feedback Loop

Once you submit answers:

1. I (the educator) score each answer against the rubric
2. I note which Bloom's levels you're strong in (and which need work)
3. I provide feedback: "Your Apply answers were excellent, but your Analyze answers were shallow"
4. I recommend targeted follow-up

---

## Final Note: On "Vibe Coding"

You mentioned building this framework via "vibe coding" — intuitive iteration without fully scripting the architecture.

That's actually a **strength**, not a weakness. It means you have strong architectural intuition. The reason this walkthrough works is because *the framework is coherent* — you built something that hangs together logically.

This education gate is ensuring that your intuitive knowledge becomes explicit knowledge (something you can articulate and teach). That's the value.

Once you've passed the quiz and explain-back, you'll have both intuitive understanding AND explicit reasoning. That's expertise.

---

**Next Step:** Open FRAMEWORK_QUIZ.md and work through the 13 questions.

**Time Estimate:** 25-30 minutes

**Passing Threshold:** 70% (9/13 correct)

**Pass → Explain-Back → Framework Mastery ✓**

Good luck. You've built something thoughtful.
