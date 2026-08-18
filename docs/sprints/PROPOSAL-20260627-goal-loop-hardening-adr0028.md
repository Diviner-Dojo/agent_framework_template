# Proposal — Goal-loop reliability hardening (ADR-0028, first-real-use backflow from VerificationPortal)

**Status:** proposal (pre-Steward-gate) · **Extends:** ADR-0026 (goal-driven loop orchestration) · **Date:** 2026-06-27
**Driver:** first real `/goal-loop` exercise in VP surfaced concrete defects across two adversarial /review rounds.
**Route:** observation → **this proposal** → Steward gate → developer Principle-#7 approval → /build_module → /review.
**Reference fix:** VP `feature/goal-loop-enforcer-fix` @ `2ab77352` (reconciled, not re-derived). **Commit-scope decision:**
this fork only; public-upstream PR is a tracked follow-on (the confirmed seam-2b bug is live on public main via PR #100).

---

## Context — the hub is NOT uniformly "same bugs as VP" (verified)

Reconciliation against hub source proved a **mix**, so the port is selective and seam-verified:

- VP's `2ab77352` is itself **REQUEST-CHANGES** (round-2 review REV-20260628-003355 left B1–B4 open). It supplies clean
  reference code for the *pure-core* fixes only; the transport fix (B2), always-skeptic (B4), and re-verify-fail test
  (B3) are **not in VP's commit** and are authored fresh here.
- Some "VP defects" were **VP propagation gaps**, already correct in the hub: `tests/test_goal_loop.py` exists (VP's
  copy didn't); the facilitator "Goal-Seeking Loop Mode" subsection exists; `notify.py` validators + the A1 slug-leak
  fix exist; **seam-2a (notify TypeError) does NOT reproduce in the hub** (hub is internally body-first consistent).

## The intervention map (least-complex-first; one combined pass)

| # | Lesson → change | Hub action | Tier | Files |
|---|---|---|---|---|
| **2b** | ntfy gate drops every AFK approval | **author fresh:** `_ntfy_gate_transport` drives a **bounded `poll`** (prints `REPLY-MATCH`) instead of `check 1h` (prints `ANSWER-MATCH`, + stale-replay); add an integration test driving it | code | `scripts/goal_loop.py`, `tests/test_goal_loop.py` |
| **3-H1** | qg-only contract self-grades | **port (clean):** add `non_qg_deterministic`/no-judge rejection in `validate_contract` | code | `scripts/goal_loop.py` |
| **3-B4** | sibling `[quality_gate, "pytest test_x"]` no-judge hole | **author fresh:** driver **always runs the independent skeptic on the goal-met candidate regardless of contract shape** (not per-shape validate) | code (behavioral) | `scripts/goal_loop.py` |
| **3-prot** | tripwire must guard the answer-key | **port + harden:** add `protected_paths` field + `load_contract` parse + `tamper_tripwire` prefix-match (edit/rename/delete via `--name-status`); **harden beyond VP:** reject/normalize leading-slash entries (VP's A2 fails-open, unfixed) | code | `scripts/goal_loop.py` |
| **3-regex** | tamper allow-list gap | **port (clean):** extend `_SENSITIVE_PATH_RE` with `setup.py\|pytest.ini\|.pytest.ini\|noxfile.py` | code | `scripts/goal_loop.py` |
| **H2** | only exact `"main"` blocked | **port (clean):** `_PROTECTED_BRANCHES` + `_is_protected_branch()` (casefold + `refs/heads/` strip + master/develop/trunk) + defense-in-depth re-check in `affirm_l2` | code | `scripts/goal_loop.py` |
| **1** | ship the safety tests | **port test names + B3:** `test_quality_gate_only_rejected`, `test_added_config_files_trip`, `test_protected_answer_key_paths_trip`, `test_protected_branches_never_affirm`, **+ fresh** FlipVerifier re-verify-FAIL test (B3) | test | `tests/test_goal_loop.py` |
| **2a** | settle ONE notify convention | **test-only (NO signature change):** keep hub body-first; add a **bind-shape regression test** pinning `send_notification` + caller shape so a VP-style divergence is caught | test | `tests/test_collab_loop.py` or `tests/test_notify.py` |
| **4** | scope loop to deterministic | **author prose:** authoring skill — fixtures must carry **provenance** (no hand-authored answer keys) + a **mandatory live-confirm at goal-met** | skill prose | `.claude/skills/authoring-goal-contracts/SKILL.md` |
| **6** | lead-with-goal + ask-up-front | **author prose:** new authoring **Step 0** (state plain-language goal + clarifying Qs w/ recommended answers) before the gatekeeper (which becomes Step 1) | skill prose | `.claude/skills/authoring-goal-contracts/SKILL.md` |
| **5** | propagation hygiene | **doc fixes:** remove stale `fixed-red-set` from the template `no_progress_definition` comment (validate_contract rejects it); add `protected_paths` to the template; ADR-0028 carries the lineage pointer | template/doc | `docs/templates/goal-contract-template.md` |
| **1-meta** | new framework gate | **prose rule (Principle #8):** "a new control-flow / safety-critical capability ships its tests in the **same** change" — added as a rule, human-enforced at /review (mechanical check = scoped follow-on) | rule prose | `.claude/rules/testing_requirements.md` (+ pointer from `autonomous_workflow.md`) |

## Deliberate divergences from VP (why this is reconcile, not copy)

1. **Keep body-first `notify.py`** — VP went title-first and broke its own callers (B1). The hub is consistent; copying VP's signature would *introduce* the bug. Lock with a test instead.
2. **Harden `protected_paths` past VP** — VP's normalization fails open on leading-slash entries (its own review's A2, unfixed). Add `lstrip("/")` + `ContractError` on empty-after-normalization.
3. **Author B2/B4/B3 fresh** — VP's commit doesn't contain them; re-deriving from the review findings + the established R5/R8/R10 design (ADR-0026).
4. **Always-skeptic-on-goal-met is driver-side** — moves the integrity guarantee from a per-shape `validate_contract` rule to an unconditional driver behavior at the goal-met candidate (closes the whole reward-hack class, not one shape).

## Scope, risk, sequencing

- **Risk: high** (safety-critical control-flow core; the value prop is provable reliability under autonomy). `/build_module`
  with mid-build checkpoints on the `goal_loop.py` core; full multi-agent `/review` (security + qa + independent at least).
- **One combined pass** (developer choice). **Commit fork-only** on `framework/goal-loop-hardening-0028` off main; **NO push,
  NO merge.** Public-main PR (the live seam-2b) = tracked follow-on.
- **ADR:** new **ADR-0028** extending ADR-0026 (not amending the accepted+published 0026; Principle #5). Credits VP as the
  first-use source; the lineage pointer addresses Lesson 5.

## Open question for the Steward
Does the **always-skeptic-on-goal-met** behavioral change (a stricter, unconditional integrity guard) belong in this
hardening ADR, or does moving integrity enforcement from declarative (`validate_contract`) to imperative (driver runtime)
warrant its own design note? (Proposer's view: it belongs here — it's the direct fix for the verified reward-hack class
and stays within ADR-0026's verifier-integrity mandate.)
