---
name: Security Threat Model
type: standing-document
specialist: security-specialist
updated: "[update after each review that identifies security concerns]"
---

# Security Threat Model

Standing document for the security-specialist. Consult before every review dispatch.

## Trust Boundaries

<!-- Document current trust boundaries with trust levels and validation status.
Format:
| Boundary | Trust Level | Validation | Last Reviewed |
|----------|-------------|------------|---------------|
| API input (user) | Untrusted | Pydantic models at route level | [date] |
| Database queries | Internal | Parameterized via SQLAlchemy | [date] |
-->

*Define trust boundaries as the project's API surface develops.*

## Accepted Risks

<!-- Risks identified during review that were accepted rather than mitigated.
Format:
### [Risk Title]
- **Identified**: [date, review ID]
- **Severity**: [low/medium/high]
- **Rationale for acceptance**: Why this risk is tolerable
- **Mitigation if escalated**: What to do if risk materializes
-->

*No accepted risks yet.*

## AI-Specific Threat Surface

<!-- Threats specific to LLM/AI integration: prompt injection, data exfiltration via tool calls, etc.
Document any AI-specific attack vectors relevant to the project.
-->

*Assess when LLM integration is added to the project.*
