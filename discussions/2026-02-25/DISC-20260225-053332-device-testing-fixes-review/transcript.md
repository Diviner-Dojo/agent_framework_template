---
discussion_id: DISC-20260225-053332-device-testing-fixes-review
started: 2026-02-25T05:39:21.064239+00:00
ended: 2026-02-25T05:40:03.980074+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 4
---

# Discussion: DISC-20260225-053332-device-testing-fixes-review

## Turn 1 — qa-specialist (critique)
*2026-02-25T05:39:21.064239+00:00 | confidence: 0.88*
*tags: review, qa, blocking:1, advisory:7*

qa-specialist assessment (confidence 0.88):

Finding 1 (HIGH — Blocking): SHA-256 hash is 63 characters, not 64. The hash 'a6f181e...' was replaced with '74a4da8c...' but the new hash appears to be 63 hex characters. SHA-256 must be exactly 64 hex characters. The existing test asserts `sha256.length == 64`, so this test will fail. More critically, hash verification in production will always fail, meaning model downloads will be rejected as corrupt.

Finding 2 (MEDIUM — Advisory): updateLocalLlmLayer() in agent_repository.dart has zero test coverage. This is a new public method that mutates internal state — it should have tests for: successful update, null layer handling, and concurrent access patterns.

Finding 3 (MEDIUM — Advisory): GoogleConnectionNotifier.connect() exception propagation is untested. The new GoogleAuthException throw path in google_auth_service.dart is tested, but the provider-level catch in calendar_providers.dart is not. The rethrow behavior and state transitions on error need coverage.

Finding 4 (MEDIUM — Advisory): Settings screen GoogleAuthException SnackBar path is untested. The catch clause in settings_screen.dart that shows a SnackBar on GoogleAuthException has no widget test.

Finding 5 (MEDIUM — Advisory): Auth screen null-user path is untested. The new error display when user is null after sign-in has no widget test.

Finding 6 (LOW — Advisory): generate() dual guard (null check + isLoaded) is sound defensive programming. No issues.

Finding 7 (LOW — Advisory): llmAutoLoadProvider catches only LocalLlmException, not broader Exception. If llamadart throws a non-LocalLlmException (e.g., StateError, ArgumentError), it will be unhandled.

Finding 8 (LOW — Advisory): Async test assertion style — some tests use `expect(future, throwsA(...))` without await. Should use `await expectLater(future, throwsA(...))` for proper async assertion.

---

## Turn 2 — security-specialist (critique)
*2026-02-25T05:39:22.753388+00:00 | confidence: 0.88*
*tags: review, security, blocking:1, advisory:5*

security-specialist assessment (confidence 0.88):

Finding 1 (MEDIUM — Blocking): Auth screen error message leaks configuration flag names. The error text includes literal strings 'SUPABASE_URL' and 'SUPABASE_ANON_KEY', which are Dart define flag names. This is information disclosure — it tells an attacker exactly which build-time configuration flags the app uses. Replace with a generic message like 'Cloud sync is not configured. Please contact support.'

Finding 2 (LOW — Advisory): Mutable _localLlmLayer in agent_repository.dart bypasses the session-locked layer invariant from ADR-0017 §3. The field was previously final, ensuring the layer couldn't change mid-session. Now it's mutable with a public setter. While the current usage is safe (only called during startup before any session), the API surface allows mid-session mutation.

Finding 3 (LOW — Advisory): GoogleAuthException.cause field could leak platform-specific error details to UI. The cause is passed through to the SnackBar message in settings_screen.dart. Depending on what google_sign_in throws, this could expose internal implementation details.

Finding 4 (LOW — Advisory): SHA-256 hash appears to be 63 characters (same as QA finding 1). This is a correctness issue with security implications — hash verification protects against supply-chain attacks on the model file.

Finding 5 (LOW — Advisory): Google Services plugin version 4.4.0. Current latest is 4.4.2. Not a blocking issue but worth updating for security patches.

Finding 6 (LOW — Advisory): Release signing uses debug keystore (pre-existing issue, not introduced by this diff).

---

## Turn 3 — architecture-consultant (critique)
*2026-02-25T05:39:24.400025+00:00 | confidence: 0.87*
*tags: review, architecture, blocking:0, advisory:5*

architecture-consultant assessment (confidence 0.87):

Finding 1 (MEDIUM — Advisory): Missing ADR amendment for mutable _localLlmLayer pattern. ADR-0017 §3 established the session-locked layer invariant with a final field. Changing to mutable violates that documented contract. Either amend ADR-0017 to document the async-injection pattern, or use a different mechanism (e.g., AsyncValue wrapper).

Finding 2 (MEDIUM — Advisory): ref.listen pattern in agentRepositoryProvider is opaque. The provider listens to localLlmServiceProvider and calls updateLocalLlmLayer() as a side effect. This creates an implicit dependency that's hard to trace. Consider making this explicit in the provider's documentation or using a more visible wiring pattern.

Finding 3 (LOW — Advisory): Model loading logic duplicated between settings_screen.dart (after download) and llmAutoLoadProvider (at startup). Both paths create a LocalLlmService and load the model. Extract a shared helper to avoid drift between the two paths.

Finding 4 (LOW — Advisory): calendar_providers.dart doc comment says 'Rethrows' but the actual behavior is catch-set-state-rethrow. The doc comment is misleading about the state transition that happens before the rethrow.

Finding 5 (LOW — Advisory): llmAutoLoadProvider writing to localLlmServiceProvider's state via ref.read(localLlmServiceProvider.notifier).state is a Riverpod anti-pattern. One provider should not directly mutate another provider's state. Consider using a shared state notifier or event-based approach.

Finding 6 (INFO): app.dart discards llmAutoLoadProvider.future result in addPostFrameCallback. The fire-and-forget pattern is intentional (errors caught inside), but adding a comment explaining why the future is discarded would improve clarity.

---

## Turn 4 — facilitator (synthesis)
*2026-02-25T05:40:03.980074+00:00 | confidence: 0.88*
*tags: synthesis, blocking:0, advisory:17*

Review synthesis for DISC-20260225-053332-device-testing-fixes-review. 3 specialists dispatched (qa-specialist, security-specialist, architecture-consultant). 1 round (structured-dialogue).

SHA-256 hash length finding (flagged as blocking by both QA and security): VERIFIED FALSE POSITIVE. The hash '74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db' is exactly 64 hex characters. No blocking issue.

Auth screen config flag names (flagged as blocking by security): RECLASSIFIED AS ADVISORY. The message only appears when the app is built without --dart-define flags, which is a developer-only scenario. Production builds will always have these flags. The message is helpful for developer onboarding.

Verdict: APPROVE-WITH-CHANGES. 0 blocking findings after verification. 17 advisory findings across 3 specialists. The changes are sound — they wire up real llamadart inference, add Google Services Gradle plugin, improve error handling, and fix lint issues. The advisory findings are valid improvement opportunities but none block merge.

Key advisory themes: (1) missing test coverage for new paths (updateLocalLlmLayer, GoogleAuthException propagation, null-user auth path), (2) ADR-0017 amendment needed for mutable layer pattern, (3) duplicated model loading logic, (4) Riverpod anti-pattern in llmAutoLoadProvider.

---
