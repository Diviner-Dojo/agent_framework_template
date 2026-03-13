---
document_type: Education Gate Manifest
phase: "<phase or feature name>"
gates_completed: []  # [walkthrough, quiz, explain-back]
review_reference: "<REV-YYYYMMDD-HHMMSS>"
created_at: "YYYY-MM-DDTHH:MM:SSZ"
---

# Education Gate Manifest: <Phase/Feature Name>

## Executive Summary

<Brief description of the change, why it triggered an education gate, and the risk level.>

**Why this triggered an education gate:**

- <Reason 1: e.g., unfamiliar technology, complex architecture>
- <Reason 2: e.g., review caught critical issues that must be understood>
- <Reason 3: e.g., new patterns introduced>

---

## Gate Structure

### Step 1: Walkthrough

- **Status**: [ ] COMPLETE
- **File**: `<path to walkthrough file>`
- **Length**: ~X,XXX words across N sections
- **Bloom's Levels**: Understand (60%), Apply (30%), Analyze (10%)
- **Estimated reading time**: XX minutes

### Step 2: Quiz

- **Status**: [ ] COMPLETE
- **File**: `<path to quiz file>`
- **Total questions**: N
- **Pass threshold**: 70% (N/N correct)
- **Bloom's distribution**:
  - Remember: N (X%)
  - Understand: N (X%)
  - Apply: N (X%)
  - Analyze: N (X%)
  - Evaluate: N (X%)
  - Debug/Change-Impact: N (X%)
- **Estimated time**: XX minutes

### Step 3: Explain-Back

- **Status**: [ ] COMPLETE
- **File**: `<path to explain-back file>`
- **Format**: Open-ended synthesis (N prompts, 150-250 words each)
- **Pass threshold**: 80% (N/N points)
- **Estimated time**: XX minutes

---

## Core Concepts the Developer Must Understand

### 1. <Concept Name>

**Problem**: <What goes wrong without understanding this>

**Solution**: <How the implementation addresses it>

**Why this matters**: <What breaks if the developer doesn't understand this>

**Key files**: <Relevant source files>

### 2. <Concept Name>

**Problem**: <...>

**Solution**: <...>

**Why this matters**: <...>

**Key files**: <...>

---

## Connection to ADRs

### <ADR-NNNN: Title>

**How this change implements it**: <...>

**What the developer must grasp**: <...>

---

## Mastery Progression

**Before walkthrough**: <Developer's starting knowledge level>

**After walkthrough**: <What the developer can now do>

**After quiz (70%+ pass)**: <What the developer can now apply independently>

**After explain-back (80%+ pass)**: <What the developer understands at a synthesis level>

**Mastery tier**: <Tier 1 (basic) / Tier 2 (intermediate) / Tier 3 (advanced)>

---

## Risk Mitigation

<How the education gate connects to specific review findings and ensures the developer understands the risks.>

---

## Handoff Criteria

Developer passes education gate when:

1. [ ] Reads walkthrough (self-paced, no grading)
2. [ ] Scores 70%+ on quiz
3. [ ] Scores 80%+ on explain-back

At that point:
- Developer is ready to maintain this code
- Developer can debug issues in this area
- Developer can extend patterns to new cases
- Developer understands the architectural rationale

---

## File Locations

- **Walkthrough**: `<path>`
- **Quiz**: `<path>`
- **Explain-Back**: `<path>`
- **Review Report**: `<path>`
- **Related ADRs**: `<paths>`
