---
paths:
  - "src/**"
  - "scripts/**"
---

# Security Baseline

## Input Validation
- Validate all user input at API boundaries using Pydantic models
- Never trust client-provided data without validation
- Sanitize inputs that will be used in database queries, file paths, or shell commands
- Sanitize data at every trust boundary — not just user input. Data interpolated into LLM prompts, action triggers, or cross-process channels must be validated at the boundary, not assumed safe because it originated internally

## Database Security
- Use parameterized queries exclusively — no string interpolation in SQL
- Never expose raw database errors to API consumers
- Use minimum-privilege database connections

## Secrets Management
- No secrets, API keys, or credentials in source code
- No secrets in configuration files committed to version control
- Use environment variables or dedicated secret management for sensitive values
- **Nothing in this repo blocks a commit containing a secret.** The one automated
  check is a PreToolUse hook that matches 12 patterns
  (`.claude/hooks/validate_tool_use.py` → `SECRET_PATTERNS`). State all four of its
  limits whenever you cite it — measured 2026-08-07 by feeding the hook real
  payloads, re-runnable against `main()` in that file:
  1. **It does not block. It asks.** It emits `permissionDecision: "ask"`, not
     `"deny"` — a prompt to a human, not a refusal. `ask` is also the *weaker*
     decision under `--permission-mode bypassPermissions`, which this framework's
     own `scripts/session_supervisor.py` runs. Treat it as "probably pauses".
  2. **It never sees a commit.** It is wired on the `Write|Edit` matcher, so it
     inspects content *as a file is written*. `git commit` is the `Bash` tool,
     whose matcher runs `pre-commit-gate.sh` and `pre-push-main-blocker.sh` —
     neither reads file contents. A secret written by any other route (a shell
     heredoc, a generated file, an existing file staged later) reaches the commit
     with nothing having looked at it. Measured: a `Bash` payload of
     `git commit -m 'add key'` returns no decision at all.
  3. **Test files are exempt outright.** `is_test_file()` returns before the scan
     for anything matching `TEST_FILE_PATTERNS`, which is exactly
     `test_*.py`, `*_test.py`, `*/tests/*.py`, `*.test.[tj]s(x)`,
     `*.spec.[tj]s(x)`. Measured: the same AWS key + GitHub token that triggers
     `ask` in `src/leak.py` is written to `tests/test_leak.py` with no decision
     emitted. Note the third pattern is `.py`-only — it was written here as
     `tests/**` until 2026-08-08, which overstates it in the safe direction:
     a `tests/fixtures/creds.json` is **not** exempt and is still scanned. Cite
     the regex, not a gloss of it.
  4. **12 regexes are a list, and lists end.** It matches the shapes someone
     thought of (AWS `AKIA…`, `ghp_…`, `sk-ant-…`, JWTs, PEM headers, Slack,
     GCP, bearer tokens, generic `key = "…"` assignments). A base64 blob, a
     split string, a secret in an unlisted vendor format, or one read from a file
     at runtime is invisible.

  This was previously written as "scans for 12 secret patterns and **blocks
  commits** containing them" — a sentence that was wrong in both halves and would
  have been explained back, correctly, as a guarantee the code has never made.
  It is defence-in-depth against *typing a key into a source file by accident*.
  It is not a secret-scanning gate. If you need one, `git secrets`/`gitleaks` in
  the pre-commit hook is the mechanism, and it does not exist here yet.

  > ### ⚠ Owed: every project that received an earlier copy still carries the
  > ### false sentence
  >
  > This correction was made in the framework template on 2026-08-08. **Any
  > project the framework was applied to before that date still has the original
  > line**, because the fix propagates only through `/apply-framework` and the
  > correcting change had no write access to downstream repos. Measured on the
  > 2026-08-08 hub survey: the verbatim line was still live in **every** surveyed
  > downstream copy — the fix covered 1 repo of 5.
  >
  > Check your own copy before trusting this file's history:
  >
  > ```bash
  > grep -n "12 secret patterns" .claude/rules/security_baseline.md
  > ```
  >
  > If that returns the words **"blocks commits"**, this section has not reached
  > you yet and everything above it is what your hook actually does.
  >
  > **This is a propagation obligation, tracked as one.** The per-repo survey
  > (which projects, which line numbers, measured when) lives in
  > `docs/education/governance-mechanisms.md`, Row 3 — this file is CORE and
  > propagates verbatim, so it must not name specific projects. Before pasting
  > the corrected text into any project, **re-measure that project's own
  > `.claude/hooks/validate_tool_use.py`**: the pattern count and the
  > `ask`-vs-`deny` decision are per-repo facts. Copying this file's numbers
  > without checking would repeat the original error in a new place.
  >
  > **Also owed, in the framework template:** `docs/FRAMEWORK_SPECIFICATION.md`
  > was not synced when this rule changed, though the `syncing-framework-docs`
  > skill fires on `.claude/rules/` edits. Its secret-detection sections describe
  > *what is scanned* and never state that the decision is `ask` rather than
  > `deny` — the half of the claim that misleads. Detail and line numbers: Row 3
  > of `docs/education/governance-mechanisms.md`.

## API Security
- Configure CORS explicitly — no wildcard `*` in production
- Authentication required for all non-public endpoints
- Rate limiting on authentication endpoints
- Return generic error messages to prevent information leakage

## Dependencies
- Review new dependencies for known vulnerabilities before adding
- Pin dependency versions in requirements.txt
- Prefer well-maintained, widely-used libraries
