---
discussion_id: DISC-20260804-191824-walkthrough-greenable-gate-stack-profiles
started: 2026-08-04T19:20:08.802037+00:00
ended: 2026-08-04T19:20:08.802037+00:00
agents: [educator]
total_turns: 1
---

# Discussion: DISC-20260804-191824-walkthrough-greenable-gate-stack-profiles

## Turn 1 — educator (proposal)
*2026-08-04T19:20:08.802037+00:00 | confidence: 0.85*
*tags: walkthrough, education*

Walkthrough (Tier 2) - quality-gate debt baseline + profiles. Educator strategic_mastery s-tier-1 / implementation i-tier-1, confidence 0.85.

1. WHAT RED MEANS NOW: before, RED meant "something is imperfect" -> permanently red (VP 85.5%) -> smoke-alarm-for-burnt-toast effect, battery disconnected (--no-verify habituation). Now pre-existing debt is DECLARED in config/gate_baseline.json (bankruptcy-disclosure analogy); declared debt = WARN with count, visible non-blocking; anything NOT declared fails RED. RED = "this change introduced a new problem."

2. BASELINE = REWARD FUNCTION: an agent that could add its own mistakes to the declared list would launder new failures as old (grading its own homework). Four locks: set-membership not counts (swap case fails); shrink-only ratchet; --rebaseline is developer-consent only (agent must never run it); manual hand-edits require /review (no back door). Honest gap: fingerprints are file+rule (line numbers drift), so a second NEW violation of an already-declared rule in the same file collapses into the existing fingerprint - documented trade-off, canary #5 will probe.

3. PROFILES: stack-specific recipes (python-fastapi / flutter-dart / markdown-corpus) varying ONLY the four stack checks (format/lint/tests/coverage); framework-integrity checks (ADRs, review existence, education) run unconditionally in every profile - the config schema cannot name them. Auto-detect with two loud warnings: markdown-with-.py-files, dual-marker monorepo.

4. ALLOW-LIST LIMIT: fixed program-name list stops typo/substitution, but python/pytest/dart are interpreters (python -c runs anything) - NOT a sandbox. Real safety net = /review on profile-file edits; the meaningful review check is the ARGUMENTS, not the program name.

5. NOT FIXED (honest scope): AJ Flutter coverage 15-20min Windows hang (profile ships coverage disabled, not fixed); VP coverage-threshold erosion 80->40 (nothing forces an honest fail_under). Both carried. --fast is sampled mid-build convenience, never commit evidence.

DECISIONS THE DEVELOPER OWNS: (a) --rebaseline requests - is this genuinely pre-existing debt or new work getting grandfathered? (b) gate-config diffs in /review - read the command arguments, not just the program name; (c) derived-project profile pins / coverage thresholds - does the number reflect real practice or gate-silencing (the 80->40 pattern)?

---
