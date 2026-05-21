---
name: Architecture Drift Log
type: standing-document
specialist: architecture-consultant
updated: "[update after each review that flags architectural concerns]"
---

# Architecture Drift Log

Standing document for the architecture-consultant. Consult before every review dispatch.

## Recurring Boundary Violations

<!-- Track modules with 3+ boundary violation flags — these indicate architectural problems, not one-off code issues.
Format:
| Module | Violation Count | Nature | ADR Deviation? | Last Flagged |
|--------|----------------|--------|----------------|--------------|
-->

*No entries yet. Add entries when architectural boundary violations are flagged in reviews.*

## Accepted ADR Deviations

<!-- Intentional deviations from ADR decisions that should NOT be re-flagged in future reviews.
Format:
### ADR-NNNN — [deviation description]
- **Reason**: Why this deviation is accepted
- **Scope**: Which modules/files are affected
- **Accepted by**: [developer] on [date]
-->

*No accepted deviations yet.*

## Dependency Direction Rules

<!-- Document which modules may depend on which. Flag violations during review.
Format:
- `src/routes/` → `src/models/` (allowed)
- `src/models/` → `src/routes/` (NEVER — model layer must not depend on route layer)
-->

*Define dependency direction rules as the project's module structure stabilizes.*
