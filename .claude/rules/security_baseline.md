# Security Baseline

## Input Validation
- Validate all user input at API boundaries using Pydantic models
- Never trust client-provided data without validation
- Sanitize inputs that will be used in database queries, file paths, or shell commands

## Database Security
- Use parameterized queries exclusively — no string interpolation in SQL
- Never expose raw database errors to API consumers
- Use minimum-privilege database connections

## Secrets Management
- No secrets, API keys, or credentials in source code
- No secrets in configuration files committed to version control
- Use environment variables or dedicated secret management for sensitive values

## API Security
- Configure CORS explicitly — no wildcard `*` in production
- Authentication required for all non-public endpoints
- Rate limiting on authentication endpoints
- Return generic error messages to prevent information leakage

## Dependencies
- Review new dependencies for known vulnerabilities before adding
- Pin dependency versions in requirements.txt
- Prefer well-maintained, widely-used libraries
