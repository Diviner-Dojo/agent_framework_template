---
review_id: REV-20260523-224536
discussion_id: DISC-20260523-224536-review-session-wrapup
spec_id: SPEC-20260523-110504
adr_id: ADR-0018
date: 2026-05-23
risk_level: high
scope: framework
panel: [security-specialist, architecture-consultant, qa-specialist, independent-perspective]
verdict: APPROVE
---

# Review: Model-Aware Session Wrap-Up & Handoff (ADR-0018)

Final independent gate before commit for the ADR-0018 build. Prior gates: spec-review
(`DISC-20260523-190838`), Steward gate (`DISC-20260523-191709`), mid-build checkpoint
(security + qa on the core). Quality gate **6/6** (coverage 92% on `src/context_sensor.py`,
63 tests).

## Verdict: APPROVE — proceed to commit (2 blocking findings resolved)

| Specialist | Verdict | Confidence |
|---|---|---|
| security-specialist | APPROVE | 0.92 |
| architecture-consultant | APPROVE-WITH-CHANGES | 0.88 |
| qa-specialist | (1 blocking, resolved) | 0.88 |
| independent-perspective | (1 blocking, resolved) | 0.82 |

## Blocking findings (both resolved)

- **IP-B1 — auto-launch argv functionally broken.** `build_launch_command` returned
  `["claude", "--print", instruction, path]` (two positionals); `claude --print` takes a single
  positional prompt, so a continuation would reference a path it cannot read. This directly
  conflicted with the checkpoint's B-SEC-1 "discrete argv element" mandate. **Facilitator
  reconciliation** (SendMessage unavailable): the security threat (shell injection) is closed by
  `shell=False` regardless of discrete-vs-inline, and the path is canonicalized +
  `is_relative_to(HANDOFF_DIR)`-validated — so inlining the validated path into the fixed
  single-positional prompt is both injection-safe **and** functional. Reverted to the inline form;
  updated code, test (`test_valid_returns_single_positional_prompt_with_validated_path`), ADR, and
  spec; retained the "verify exact invocation at first real use" caveat.
- **QA-F1 — weak nudge assertions.** State-machine tests asserted key/label presence but not the
  occupancy + threshold numbers (AC-4/B-QA-7). Added numeric assertions (120/100 soft, 250/200 hard).

## Advisory findings folded now

- **Security:** `transcript_path` from the hook payload now requires a `.jsonl` suffix before use.
- **Architecture:** the config `defaults` comment no longer restates derived token counts (drift risk).

## Advisories deferred to v1.1 (tracked in BUILD_STATUS)

- **IP-A2** — soft cap at ~14% of a 1M window may be too eager and risks being disabled; the
  developer explicitly chose quality-first, so keep the default and revisit with usage data.
- **IP-A3** — every degradation path ends in silence with no liveness canary; add a per-session
  "live / transcript-estimate / no-signal" signal so internals-drift is observable.
- **IP-A4** — no instrumentation of nudge-fired-vs-ignored; off-pattern for a capture framework.
  Add a JSONL signal so the protocol's yield can later be judged.

## Key adoption note (accepted)

The feature ships **inert** until the developer applies the manual `settings.json` wiring
(statusLine + `UserPromptSubmit` hook + `"env"` backstop) — by design (R9; `settings.json` is a
PROTECTED_PATTERNS file, so the wiring cannot be automated or tested). The `/handoff` command works
**without** wiring (manual verb delivers value immediately). The exact activation diff is provided to
the developer at commit hand-off.

## Follow-ups owed before `/ship`

- Doc-sync (`syncing-framework-docs`): `docs/FRAMEWORK_SPECIFICATION.md` §6/§14/§15 + the two
  presentation HTMLs (new `/handoff` command, `wrapping-up-sessions` skill, `model_context_profiles.yaml`).
- Version bump (v3.5 → v3.6) at `/ship` time.
- Later: `/distribute` to the 3 derived targets (opt-in HARD GATE; consent keys never staged).
