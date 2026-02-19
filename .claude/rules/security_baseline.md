# Security Baseline

## Input Validation
- Validate all user input at the UI layer before passing to business logic
- Never trust client-provided data without validation
- Sanitize inputs used in database queries or displayed in UI (prevent injection and XSS)

## Database Security
- Use drift's type-safe query API — no raw SQL string interpolation
- Never expose raw database errors to users — catch and present friendly messages
- Store sensitive data (auth tokens, API keys) in `flutter_secure_storage`, not SQLite

## Secrets Management
- No secrets, API keys, or credentials in source code
- No secrets in configuration files committed to version control
- Use `flutter_secure_storage` for on-device secrets (auth tokens, encryption keys)
- API keys for Claude must be proxied through Supabase Edge Functions (ADR-0005) — never embedded in the app
- The PreToolUse hook scans for 12 secret patterns and blocks commits containing them

## Network Security (Phase 3+)
- All network communication over HTTPS — no plain HTTP
- Certificate pinning for Supabase endpoints in production
- Auth tokens sent via `Authorization` header, never in query parameters
- Implement request retry with exponential backoff (dio interceptors)
- Validate and sanitize all data received from external APIs

## Supabase Security (Phase 4+)
- Row Level Security (RLS) policies on all tables — users can only access their own data
- Use Supabase Auth for authentication — no custom auth implementation
- Service role key used only in Edge Functions, never in client code
- Enable Supabase's built-in rate limiting

## Dependencies
- Review new dependencies for known vulnerabilities before adding
- Pin dependency versions in `pubspec.yaml` (use exact versions or tight ranges)
- Prefer well-maintained, widely-used packages from pub.dev
- Check package scores and maintenance status on pub.dev before adopting

## Android-Specific
- Set `android:allowBackup="false"` in AndroidManifest.xml for release builds
- Do not store sensitive data in SharedPreferences (use flutter_secure_storage)
- Exclude `.sqlite` and `.db` files from version control (enforced by .gitignore)
