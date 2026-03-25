---
review_id: REV-YYYYMMDD-HHMMSS
discussion_id: DISC-YYYYMMDD-HHMMSS-slug
pr_id: ""
risk_level: medium  # low / medium / high / critical
collaboration_mode: structured-dialogue  # ensemble / yes-and / structured-dialogue / dialectic / adversarial
exploration_intensity: medium  # low / medium / high
agents_activated: [architecture-consultant, security-specialist, qa-specialist]
reviewed_files: []  # list of files reviewed (enables commit-to-review traceability)
rounds: 2
consensus_reached: true
verdict: approve-with-changes  # approve / approve-with-changes / request-changes / reject
confidence: 0.80  # weighted average of specialist confidences
review_duration_minutes: 0
---

## Summary

[2-3 sentence overview of the changes reviewed and the key findings.]

## Request Context

- **What was requested**: [verbatim or close paraphrase of the developer's instruction]
- **Files/scope**: [which files or changes were handed to this review]
- **Developer-stated motivation**: [why this change is being made, if stated]
- **Explicit constraints**: [any developer-stated constraints agents should respect; or "none stated"]

## Findings by Specialist

### Architecture Consultant
- [Key findings]
- Confidence: 0.XX

### Security Specialist
- [Key findings]
- Confidence: 0.XX

### QA Specialist
- [Key findings]
- Confidence: 0.XX

### Performance Analyst
- [Key findings, if activated]
- Confidence: 0.XX

### Independent Perspective
- [Key findings, if activated]
- Confidence: 0.XX

## Required Changes Before Merge

1. [Specific required change with finding reference]
2. [Specific required change with finding reference]

## Recommended Improvements (Non-Blocking)

1. [Suggested improvement that doesn't block merge]

## Speculative Findings — Lower Confidence

[Findings with confidence < 0.80, grouped here for developer judgment. These represent possible concerns that warrant consideration but did not meet the high-confidence threshold.]

1. [Speculative finding with confidence score]

## Developer Assessment (Counterfactual)

For each blocking finding, the developer may optionally tag:
- **would-have-caught**: Developer would have found this without the review
- **would-have-missed**: Developer would NOT have found this without the review

This data measures the framework's actual value — not just what it finds, but what it finds that wouldn't have been found otherwise. Assessed at review time or batch-tagged during retro.

## Education Gate

- **Required**: yes / no
- **Scope**: [What the developer needs to demonstrate understanding of]
- **Bloom's levels**: [Which cognitive levels to assess]
- **Mastery tier**: Tier 1 / Tier 2 / Tier 3
