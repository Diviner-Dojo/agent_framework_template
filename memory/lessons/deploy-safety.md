# Deploy Safety Rules

Production-tested deployment safety patterns for Python/FastAPI applications.

## Pre-Deploy Checklist

1. **Quality gate passes**: `python scripts/quality_gate.py` — all checks green
2. **No pending migrations**: Verify database schema is up to date (`python scripts/init_db.py`)
3. **Environment variables verified**: All required env vars documented and present
4. **Dependencies pinned**: `requirements.txt` has exact versions, not ranges
5. **No debug flags**: Search for `debug=True`, `DEBUG`, `TESTING` in production config

## Deployment Order

1. Database migrations first (additive only — never remove columns in the same deploy)
2. Backend services second
3. Verify health endpoints respond
4. Run smoke tests against deployed environment
5. Monitor error rates for 15 minutes post-deploy

## Rollback Strategy

- **Always have a rollback plan before deploying**
- Keep previous container image / release tagged
- Database rollbacks: only if migration was additive (column adds can stay; data transforms need reverse scripts)
- Feature flags: prefer flag-guarded rollout over big-bang deployment

## FastAPI-Specific Safety

- **CORS**: Never use `allow_origins=["*"]` in production; whitelist specific origins
- **Rate limiting**: Apply to auth endpoints and public APIs
- **Middleware order**: Security middleware (CORS, auth) before business logic middleware
- **Startup events**: Use `lifespan` context manager, not deprecated `on_event`
- **Graceful shutdown**: Handle SIGTERM — finish in-flight requests, close DB connections

## Environment Isolation

- **Never share databases** between staging and production
- **Separate secret stores** per environment
- **Config via environment variables**, not committed config files
- **Health check endpoint** (`/health`) that verifies database connectivity

## Post-Deploy Verification

1. Health endpoint returns 200
2. Key API endpoints return expected shapes (smoke test)
3. Error rate in logs does not spike above baseline
4. No new unhandled exception types in error tracker
5. Response latency within acceptable bounds (p95 < threshold)

## Incident Response

- **Log, don't panic**: Structured logging with correlation IDs
- **Circuit breakers**: External API calls should have timeouts and fallbacks
- **Alerting**: Set up alerts for error rate spikes, not just downtime
- **Runbook**: Document common failure modes and their remediation steps
