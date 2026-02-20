---
adr_id: ADR-0012
title: "Optional Auth with Upload-Only Cloud Sync"
status: accepted
date: 2026-02-20
decision_makers: [developer, facilitator]
discussion_id: null  # Direct implementation — planned in Phase 4 spec
relates_to: [ADR-0003, ADR-0004, ADR-0005]
supersedes: null
risk_level: medium
confidence: 0.9
tags: [auth, sync, supabase, cloud, phase4]
---

## Context

Phase 3 delivered Claude API integration via Supabase Edge Functions. The developer wants journal data accessible in the cloud for data work (querying, analysis, Jupyter, Python/pandas). This requires syncing local SQLite data to Supabase PostgreSQL.

Key constraints:
- The app must remain fully functional offline without login (core principle from ADR-0004)
- The developer is the sole user — multi-device sync is not needed yet
- Data should be queryable via Supabase Dashboard, REST API, direct PostgreSQL, or Python clients
- The existing Edge Function (claude-proxy) uses a proxy access key — JWT auth is more secure

## Decision

### 1. Optional Authentication
Auth is optional. The app works fully offline without login. When the user signs in via Supabase Auth (email + password), sync activates. This preserves the instant-on journaling experience.

### 2. Upload-Only Sync (Phone → Cloud)
Sync is unidirectional: phone uploads to Supabase PostgreSQL. Once in Supabase, the data is a real PostgreSQL database queryable via any standard tool. Multi-device download (cloud → phone) is deferred to Phase 4b.

### 3. On-Demand Sync
Sync triggers:
- Automatically after `endSession()` completes (if authenticated and online)
- Manually via "Sync Now" button in Settings

WorkManager background sync (periodic 15-minute) is deferred to Phase 4b to reduce scope.

### 4. JWT-Based Edge Function Auth
The claude-proxy Edge Function upgrades from proxy access key to JWT validation. When a user is authenticated, the Flutter app sends the Supabase JWT as a Bearer token. The Edge Function validates it via `supabase.auth.getUser()`.

Fallback: When not authenticated, the existing anon key + PROXY_ACCESS_KEY mechanism continues to work. This ensures Layer B (Claude API) remains available for unauthenticated users.

### 5. Supabase Auth Provider
Using Supabase's built-in email+password auth (not custom auth). Supabase Auth handles:
- User registration and login
- JWT issuance and refresh
- Token persistence on device (via flutter_secure_storage under the hood)
- RLS policy integration (`auth.uid()`)

### 6. UPSERT for Idempotency
Sync uses `ON CONFLICT DO UPDATE` (UPSERT) per ADR-0004's offline-first design. This ensures:
- Re-syncing a session that failed previously is safe
- No duplicate data in Supabase
- Client-generated UUIDs serve as natural conflict keys

## Alternatives Considered

### 1. Mandatory Auth (Rejected)
Require sign-in before first use. Rejected because it adds friction to the instant-on journaling experience — the core value proposition is capturing thoughts immediately. Optional auth preserves this.

### 2. Firebase Auth (Rejected)
Use Firebase Authentication instead of Supabase Auth. Rejected because the project already uses Supabase for the Edge Function proxy (ADR-0005) and will use Supabase PostgreSQL for cloud storage. Adding Firebase would introduce a second backend with no benefit.

### 3. Bidirectional Sync (Deferred)
Sync both upload and download to support multiple devices. Deferred because the developer is the sole user on one phone — upload-only satisfies the "accessible for data work" requirement. Multi-device adds conflict resolution complexity with no current benefit.

### 4. Background Sync via WorkManager (Deferred)
Periodic 15-minute background sync. Deferred to Phase 4b to reduce scope — on-demand sync (session end + manual) is sufficient for a single-user app.

## Consequences

### Positive
- Journal data becomes queryable from any PostgreSQL-compatible tool
- No login barrier — app works identically without auth
- JWT auth is more secure than the proxy access key approach
- UPSERT makes sync retries safe and idempotent

### Negative
- Two auth paths (authenticated JWT vs unauthenticated anon key) add complexity to the Edge Function
- No background sync means data only uploads when the user ends a session or taps "Sync Now"

### Deferred
- WorkManager background sync (Phase 4b)
- Multi-device download sync (Phase 4b)
- Sync conflict resolution beyond last-write-wins (Phase 4b)

## Dependencies Added
- `supabase_flutter: ^2.8.0` — Supabase client for Flutter (auth, database, realtime)
- `flutter_secure_storage: ^9.2.0` — Secure token storage (used by supabase_flutter internally, explicit for clarity)
