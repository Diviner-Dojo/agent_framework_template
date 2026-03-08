---
document_type: Education Gate Manifest
target: Developer onboarding to the framework
created: 2026-02-18
phase: Complete Education Gate Package (Steps 1-3)
---

# Education Gate Complete Package

## What You're Looking At

This is a **complete education gate** for the AI-Native Agentic Development Framework. It verifies that you understand how the framework works and why it's designed this way.

The gate has 3 steps:

1. **Walkthrough** — Guided reading path through the framework
2. **Quiz** — 13 questions spanning Bloom's taxonomy (Understanding through Evaluate)
3. **Explain-Back** — Verbal/written assessment of deep comprehension

---

## Start Here

**File:** `EDUCATION_GATE_START.md`

**What it does:** Explains what's about to happen, why it matters, and recommended reading strategy

**Read time:** 5-10 minutes

**Next step:** Follow the instructions in EDUCATION_GATE_START.md

---

## The Four Documents

### 1. EDUCATION_GATE_START.md
**Purpose:** Kickoff and orientation
**Length:** ~3,000 words
**Contains:**
- Explanation of the 3-step gate
- Reading strategy for the walkthrough
- Key concepts to look for
- Timeline
- Success criteria

**When to read:** First (right now)
**Time:** 5-10 minutes

---

### 2. WALKTHROUGH.md
**Purpose:** Guided reading path through the entire framework
**Length:** ~8,000 words across 11 sections
**Contains:**
- Part 1: Mental Model — What does this thing do?
- Part 2: Agent Architecture — Why 9 specialists?
- Part 3: Rules Stack — What standards do agents enforce?
- Part 4: Capture Pipeline — How does reasoning become data?
- Part 5: Hooks — What fires automatically?
- Part 6: Commands — What's the user interface?
- Part 7: Application Code — What's the subject?
- Part 8: End-to-End Flow — How does a code change move through the system?
- Part 9: Meta Loops — How does the framework improve itself?
- Part 10: Philosophy — Why these design choices?
- Part 11: Summary — What did you build?

**When to read:** After EDUCATION_GATE_START.md (step 1 of 3)
**Time:** 45-60 minutes (break into 2-3 sessions)
**Strategy:**
- Session 1: Parts 1-2 (30 min)
- Session 2: Parts 3-5 (30 min)
- Session 3: Parts 8-11 (20 min)
- Parts 6-7: Reference material (skim as needed)

**After reading:** Self-check with the "After Reading: Self-Check" section

---

### 3. FRAMEWORK_QUIZ.md
**Purpose:** Verify understanding across Bloom's taxonomy
**Length:** 13 questions + scoring guide
**Contains:**
- 6 Understanding questions (60%)
- 3 Apply questions (20%)
- 2 Analyze questions (15%)
- 2 Evaluate questions (5%)
- 1 Bonus debug scenario (0.5 points)

**Question types:**
- Understanding: "Explain the concept. Why is it designed this way?"
- Apply: "Trace this process end-to-end. Make decisions at each step."
- Analyze: "Compare alternatives. What are the trade-offs?"
- Evaluate: "Assess this solution. When might you make a different choice?"

**When to take:** After WALKTHROUGH.md (step 2 of 3)
**Time:** 25-30 minutes
**Format:** Open book — reference CLAUDE.md, agent definitions, scripts as needed
**Pass threshold:** 70% (9/13 correct)
**Scoring guide:** Included in the quiz document

**After quiz:** If ≥70%, proceed to Explain-Back. If <70%, review walkthrough and try again.

---

### 4. EDUCATOR_NOTES.md
**Purpose:** Guidance for the educator (me) and reference for you
**Length:** ~4,000 words
**Contains:**
- Why the walkthrough is structured this way
- The quiz: what it tests and how
- Mastery tier assessment (you're at Tier 2: Complex Systems)
- Common knowledge gaps and how to fill them
- Practical tips for taking the quiz
- Feedback loop after quiz
- What happens next (mastery progression)

**When to read:** As needed (reference document)
**Time:** 5-15 minutes (skim or read sections relevant to you)

---

## The Education Gate Flow

```
START HERE: EDUCATION_GATE_START.md
           ↓
         Read WALKTHROUGH.md (45-60 min)
           ↓
      Self-Check: Can you answer the 4 levels?
           ↓
    NO → Re-read relevant sections
         ↓
      YES → Take FRAMEWORK_QUIZ.md (25-30 min)
           ↓
    ≥70% PASS?
           ↓ YES
      Explain-Back Assessment (15 min)
           ↓
      GATE COMPLETE ✓

    ≥70% FAIL?
           ↓
      Review weak areas
      Take quiz again
           ↓ PASS
      Explain-Back Assessment
           ↓
      GATE COMPLETE ✓
```

---

## Files Not Included (But Referenced)

During the walkthrough and quiz, you'll reference these existing framework files:

**Core Documents:**
- `CLAUDE.md` — Project constitution

**Agent Definitions:**
- `.claude/agents/facilitator.md`
- `.claude/agents/educator.md`
- `.claude/agents/security-specialist.md`
- (and 6 others in `.claude/agents/`)

**Rules:**
- `.claude/rules/coding_standards.md`
- `.claude/rules/testing_requirements.md`
- `.claude/rules/security_baseline.md`
- `.claude/rules/review_gates.md`
- `.claude/rules/commit_protocol.md`
- `.claude/rules/documentation_policy.md`

**Scripts:**
- `scripts/quality_gate.py`
- `scripts/create_discussion.py`
- `scripts/write_event.py`
- (and others in `scripts/`)

Keep these open while reading and taking the quiz.

---

## Learning Objectives

After completing this education gate, you will be able to:

### Understand
- Explain the 4-layer capture stack and why it's structured that way
- Name the 9 agents and describe what each specializes in
- Describe the capture pipeline (create → write_event → close → ingest)
- Explain what each of the 6 rules files covers
- Describe the 7 hooks and when they fire

### Apply
- Trace a complete code change from write → review → education gate → commit
- Determine which specialists the facilitator would activate for a given change
- Use the quality gate to validate code
- Identify when an education gate would be recommended
- Make decisions about specialist activation based on risk level

### Analyze
- Compare the trade-offs of different collaboration modes (Ensemble vs. Structured Dialogue vs. Dialectic)
- Explain why model tiering (opus, sonnet, haiku) is used instead of single powerful model
- Analyze why Layer 1 + Layer 2 capture are both needed (not just SQLite)
- Assess the design trade-offs of key principles (e.g., independence vs. collaboration)

### Evaluate
- Assess whether 80% code coverage is the right threshold
- Determine when to skip education gates vs. requiring them
- Evaluate whether new specializations should be added to the agent team
- Make principled decisions about which improvement interventions to try first

---

## What Success Looks Like

You've completed the education gate successfully when:

- [ ] You read all of WALKTHROUGH.md (or at least Parts 1-5 and 8-11)
- [ ] You can self-check against all 4 Bloom's levels
- [ ] You score ≥70% on FRAMEWORK_QUIZ.md (9/13 correct)
- [ ] You can explain-back the 3 core concepts:
  1. Why "reasoning is the primary artifact"
  2. A design trade-off and its justification
  3. How two subsystems reinforce each other

---

## What Happens Next

After you pass the education gate:

### Immediate (Day 1-2)
- Understand the framework deeply
- Ready to use it for real code reviews

### Short-term (Week 1)
- Try the framework on a real feature
- Observe how specialists activate and what findings emerge
- Identify one small improvement to make (new rule, refined prompt)

### Medium-term (Week 2-4)
- Run `/meta-review` and read the framework assessment
- Consider running `/analyze-project` on an external codebase
- Evaluate whether to extend the framework with new specialists or commands

### Long-term (Month 2+)
- The framework becomes second nature
- You're improving it based on observed patterns
- You're teaching others how to use it

---

## Troubleshooting

**"I don't understand something in the walkthrough"**
→ Go to EDUCATOR_NOTES.md and find "Knowledge Gaps to Watch For"

**"I'm scoring poorly on the quiz"**
→ The quiz is open book. Look up answers in CLAUDE.md and referenced files. Explain your reasoning, not just the answer. 70% threshold means you can miss 4 questions.

**"The framework feels overwhelming"**
→ Normal. Read in 30-minute chunks. After each chunk, summarize in one sentence. The walkthrough builds progressively for this reason.

**"I disagree with a design choice"**
→ Good. That disagreement is what Explain-Back wants to hear. Be ready to articulate why you'd choose differently and what trade-offs that creates.

---

## How This Relates to Your Framework's Own Principles

Ironically, this education gate *applies* principles from your own framework:

- **Reasoning is Primary**: This gate captures your reasoning about what you built
- **Independence**: Quiz is open book (you look up answers independently)
- **Education Gates Before Merge**: You understand code before shipping it
- **Specialization**: The educator (this guide) specializes in knowledge transfer
- **Progressive Disclosure**: Walkthrough starts with mental model, builds to implementation

Your framework teaches how to review code. This education gate teaches how to review yourself.

---

## Files in This Package

| File | Purpose | Time | Step |
|------|---------|------|------|
| EDUCATION_GATE_START.md | Orientation & strategy | 5-10 min | 0 |
| WALKTHROUGH.md | Guided reading | 45-60 min | 1 |
| FRAMEWORK_QUIZ.md | Verification quiz | 25-30 min | 2 |
| EDUCATOR_NOTES.md | Reference & guidance | 5-15 min | ref |
| EDUCATION_GATE_MANIFEST.md | This document | 5 min | ref |

**Total Time: ~90 minutes across 1-2 days**

---

## Ready?

1. Read this document (you just did ✓)
2. Open EDUCATION_GATE_START.md
3. Follow the instructions

Let's verify your understanding of the framework.

---

**Start here:** `EDUCATION_GATE_START.md`
