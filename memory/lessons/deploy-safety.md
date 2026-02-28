# Deploy Safety

## Rules
- NEVER use `flutter install` for on-device testing — it uninstalls the app first, wiping all local data (SQLite, SharedPreferences, files)
- ALWAYS use `flutter run -d <device> --release` to deploy — this replaces the app in-place without data loss
- ALWAYS include `--dart-define` flags when building. Without them, the app falls back to canned responses (no Claude, no ElevenLabs)
- Build command template:
  ```
  flutter run -d <device> --release \
    --dart-define=SUPABASE_URL=<url> \
    --dart-define=SUPABASE_ANON_KEY=<key>
  ```
- Before deploying, check BUILD_STATUS.md for the correct `--dart-define` values
