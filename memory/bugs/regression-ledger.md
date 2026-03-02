# Regression Ledger

Known bugs, their fixes, and the tests that prevent recurrence.
Check this ledger before modifying any file listed below.

| Bug | File(s) | Root Cause | Fix | Regression Test | Date |
|-----|---------|------------|-----|-----------------|------|
| ElevenLabs speed silently ignored | elevenlabs_tts_service.dart, voice_providers.dart | setSpeechRate called before initialize(); rate lost on setAudioSource | Store _rate field, apply after setAudioSource | test/services/elevenlabs_tts_speed_regression_test.dart | 2026-02-28 |
| Voice mode bypasses Claude | agent_repository.dart | Hardcoded early return skips Claude for voice greetings | Remove bypass, let isVoiceMode flag handle brevity | test/repositories/agent_repository_test.dart:'voice mode greeting uses Claude' | 2026-02-28 |
| Deploy wipes data | N/A (process) | flutter install does uninstall→reinstall | Use flutter run --release, never flutter install | N/A (process rule) | 2026-02-28 |
| Navigator route stack collapse on onboarding complete | lib/app.dart | ref.watch(onboardingNotifierProvider) in build() caused MaterialApp to rebuild on provider change, reassigning initialRoute on an already-mounted Navigator and collapsing the route stack to just the new initialRoute | Use ref.read — onboarding→session transition is handled by Navigator.pushReplacement/pop, not initialRoute | test/app_routing_test.dart:'Navigator stack not collapsed when onboarding completes (regression)' | 2026-03-02 |
