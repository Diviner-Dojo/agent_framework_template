# Build Configuration (--dart-define flags)

These values are passed to Flutter via `--dart-define` flags at build time.
They are compile-time constants, NOT runtime environment variables.

## Usage

```bash
flutter run \
  --dart-define=SUPABASE_URL=https://your-project.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9... \
  --dart-define=CLAUDE_PROXY_TIMEOUT=30
```

For VS Code, add to `.vscode/launch.json`:
```json
{
  "args": [
    "--dart-define=SUPABASE_URL=https://your-project.supabase.co",
    "--dart-define=SUPABASE_ANON_KEY=your-anon-key-here"
  ]
}
```

## Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SUPABASE_URL` | Yes (for LLM) | `""` | Supabase project URL from Dashboard > Settings > API |
| `SUPABASE_ANON_KEY` | Yes (for LLM) | `""` | Supabase anon key from Dashboard > Settings > API |
| `CLAUDE_PROXY_TIMEOUT` | No | `30` | Timeout in seconds for Claude API calls |

## Security Notes

- The Supabase anon key is **semi-public by design** (safe to include in builds)
- The real secret (`ANTHROPIC_API_KEY`) lives in the Edge Function, never in client code
- Do NOT put `ANTHROPIC_API_KEY` in any client-side file
- When variables are missing, the app uses Layer A (rule-based agent) exclusively
