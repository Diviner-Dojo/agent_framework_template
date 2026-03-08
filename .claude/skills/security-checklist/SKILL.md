---
name: security-checklist
description: "Security review checklist for Python/FastAPI applications. Reference during security reviews, auth code reviews, or API security assessments."
---

# Security Review Checklist

## Input Validation
- [ ] All user input validated via Pydantic models with field constraints
- [ ] String inputs have max_length limits
- [ ] Numeric inputs have min/max bounds where applicable
- [ ] File uploads validated for type, size, and content
- [ ] Path parameters validated (no path traversal via `../`)
- [ ] Query parameters have sensible defaults and limits

## SQL Injection Prevention
- [ ] All database queries use parameterized statements
- [ ] No string formatting or f-strings in SQL queries
- [ ] ORM queries use parameter binding
- [ ] Raw SQL (if any) uses `?` placeholders with parameter tuples

## Authentication & Authorization
- [ ] All non-public endpoints require authentication
- [ ] Authorization checks verify the requesting user has access to the specific resource
- [ ] Tokens have expiration times
- [ ] Token validation checks expiration at consumption point (not just issuance)
- [ ] Failed auth attempts are logged
- [ ] Rate limiting on auth endpoints

## API Security
- [ ] CORS configured with specific allowed origins (no wildcard `*` in production)
- [ ] Response headers don't leak server information
- [ ] Error responses don't expose stack traces or internal details
- [ ] API versioning strategy in place for breaking changes

## Data Protection
- [ ] No secrets, API keys, or credentials in source code
- [ ] No secrets in committed configuration files
- [ ] Sensitive data not logged (passwords, tokens, PII)
- [ ] Database connection strings use environment variables
- [ ] Personally identifiable information (PII) has access controls

## Dependency Security
- [ ] Dependencies pinned to specific versions
- [ ] No dependencies with known critical CVEs
- [ ] Transitive dependencies reviewed for risk
- [ ] Minimal dependency set (no unnecessary packages)

## Error Handling
- [ ] Exceptions caught at appropriate levels
- [ ] Generic error messages returned to clients
- [ ] Detailed errors logged server-side only
- [ ] No information leakage through error responses

## Token Lifecycle (when applicable)
1. **Issuance**: Tokens issued only after successful authentication
2. **Storage**: Tokens stored securely (not in URL parameters or localStorage for sensitive tokens)
3. **Consumption**: Validation at every consumption point
4. **Expiration**: Enforced at both issuance and consumption
5. **Revocation**: Mechanism exists to invalidate tokens before expiration
