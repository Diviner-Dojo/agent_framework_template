---
discussion_id: DISC-20260717-063527-greenable-gate-stack-profiles-spec-review
started: 2026-07-17T06:35:48.265811+00:00
ended: 2026-07-17T06:40:49.212771+00:00
agents: [architecture-consultant, facilitator, qa-specialist, security-specialist]
total_turns: 5
---

# Discussion: DISC-20260717-063527-greenable-gate-stack-profiles-spec-review

## Turn 1 — facilitator (evidence)
*2026-07-17T06:35:48.265811+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Developer said 'do it, proceed' to kicking off Wave 2 of the 2026-07-15 review-triage build queue: a paired build in scripts/quality_gate.py combining triage #2 (green-able gate: baseline existing lint debt so RED = NEW debt), #9 (stack-aware gate profiles: python-fastapi / flutter-dart / markdown-corpus), and #14 (harness-ergonomics riders: one-line greppable errors, additive log aggregates, --fast deterministic sampling).
- **Files/scope**: SPEC-20260716-233400 (docs/sprints/SPEC-20260716-233400-greenable-gate-stack-profiles.md); main change in scripts/quality_gate.py + new config/gate_profiles + tests + testing-playbook/CLAUDE.md doc touches. Branch feat/gate-profiles-greenable off main.
- **Developer-stated motivation**: Adopted at 2026-07-15 triage from the 4-repo performance review: VP gate red 282/330 with lint 0/330, AJ ruff firing on Dart 255/191 + abandoned coverage gate, wiki forked --scope wiki; a permanently-red gate has zero signal and trains --no-verify bypass; explicit precondition for reward-hacking canaries (triage #5).
- **Explicit constraints**: Baseline/rebaseline must be human-gated (gate = reward function, Principle #7 surface); framework-integrity checks mandatory in every profile; backward compatible zero-config on this repo (gate stays 7/7); gate-log JSONL additive-only (telemetry consumers); stdlib-only script; pre-commit hook semantics untouched.

---

## Turn 2 — qa-specialist (critique)
*2026-07-17T06:38:16.118955+00:00 | confidence: 0.78*
*tags: spec-review, blocking, qa*

VERDICT: APPROVE-WITH-CHANGES (confidence 0.78). BLOCKING: (1) corrupt/empty/non-dict baseline file behavior undefined — must fail closed (ERROR baseline: <reason>, non-zero exit), never silently treat as empty; add R1.1a + AC + test. (2) AC6 byte-compat needs a golden fixture captured from PRE-change main (tests/fixtures/gate_summary_golden.txt) — a post-refactor test is tautological. (3) Fingerprints presume structured ruff output but check_linting parses plain text today — spec must pin ruff check --output-format=json as the fingerprint source. MEDIUM: (4) Windows path-separator normalization for fingerprints (Path.as_posix() + test). ADVISORY: (5) profile file present-but-empty/malformed needs its own fail-closed AC; (6) name the mock seam — keep profile checks routing through the single _run() so tests patch one target; (7) fingerprint-collision adversarial test low-priority. STRENGTHS: AC7 regex + AC9 schema-pin precise; AC8 asserts determinism not wall-time; hook-never-passes---fast directly testable; R1.4 correctly treats baseline as reward-function-adjacent.

---

## Turn 3 — security-specialist (critique)
*2026-07-17T06:38:52.637779+00:00 | confidence: 0.82*
*tags: spec-review, blocking, security*

VERDICT: APPROVE-WITH-CHANGES (confidence 0.82). BLOCKING: (F1) rebaseline human-gate unenforceable via Edit path — agent can edit config/gate_baseline.json directly; check_review_existence counts only src/tests/scripts+framework .md so a laundered baseline commits unreviewed. Fix: add gate_baseline.json + gate_profiles.* to review-triggering paths (or hash-pin). (F2) ratchet must be fingerprint-SET-membership, not count-based — count comparison lets a 1-for-1 swap launder new debt; AC2 must assert the swap case. ADVISORY: (F3, elevate for CORE propagation) profile command = arbitrary executable; add per-check executable allow-list (ruff/dart/flutter/pytest/coverage/python) + document the trust boundary for external repos. (F4) R2.4 must be enforced in code — profile schema physically unable to disable integrity checks; AC5 asserts a disable attempt has no effect. (F5) exclude --fast runs from the pre-commit 5-min verification cache. (F6) auto-detect falling back to markdown-corpus in a repo containing .py files = check-disable vector; warn loudly. (F7 observation) stdlib-only claim contradicts existing module-scope import yaml at quality_gate.py:23 — resolve deliberately. New trust boundary: committed gate config files = trusted-code, human-review gated.

---

## Turn 4 — architecture-consultant (critique)
*2026-07-17T06:38:52.717496+00:00 | confidence: 0.78*
*tags: spec-review, blocking, architecture*

VERDICT: APPROVE-WITH-CHANGES (confidence 0.78). BLOCKING (cheap fix): (A1) R1×R2 composition gap — baseline fingerprinting assumes ruff structured output while profiles add dart/markdown checks with different shapes; AC1-AC3 never name a profile and AC5 never asserts baseline composition — implementer could satisfy all ACs while baseline no-ops on non-python profiles. Fix: one sentence scoping R1 to python-fastapi ruff checks this build; dart/markdown baselining = explicit follow-on triage item. ADVISORY: (A2) stdlib-only constraint contradicts existing unconditional import yaml + pinned pyyaml dep — commit now to yaml.safe_load for gate_profiles.yaml instead of a build-time format fork. (A3, INFO) 841-line file + 3 requirement sets = growth marker; split to a package only if it crosses ~1200-1500 lines — not now. (A4) extend the verify-at-build doc hedge to docs/FRAMEWORK_SPECIFICATION.md (syncing-framework-docs). STRENGTHS: CORE/SKIN split follows ADR-0021 + config/ precedent; R2.4 draws the governance boundary correctly; R2.6 respects security_baseline proactively.

---

## Turn 5 — facilitator (synthesis)
*2026-07-17T06:40:49.212771+00:00 | confidence: 0.85*

## Request Context
- **What was requested**: Developer 'do it, proceed' on Wave 2 of the review-triage queue: paired quality_gate.py build — green-able gate (#2) + stack profiles (#9) + ergonomics riders (#14).
- **Files/scope**: SPEC-20260716-233400 rev 2; build will touch scripts/quality_gate.py, config/gate_profiles.yaml, tests, testing-playbook, CLAUDE.md.
- **Developer-stated motivation**: permanently-red gates trained --no-verify bypass across derived projects; precondition for reward-hacking canaries (#5).
- **Explicit constraints**: human-gated rebaseline; integrity checks mandatory per profile; zero-config backward compat; additive-only gate-log schema; pre-commit hook untouched.

## Synthesis
Panel: security 0.82, arch 0.78, qa 0.78 — all APPROVE-WITH-CHANGES, 6 blocking findings, ALL folded into spec rev 2:
1. security F1 (enforceability): out-of-band baseline edits now review-gated — gate_baseline.json + gate_profiles.* added to check_review_existence paths (R1.3a, AC3b). The human gate is enforced by the gate, not by instruction.
2. security F2 (laundering): ratchet is fingerprint-set-membership; AC2 asserts the 1-for-1 swap case fails RED.
3. qa 1: corrupt/empty baseline fails closed (R1.1a, AC3a).
4. qa 2: AC6 byte-compat pinned to a golden fixture captured from pre-change main BEFORE build.
5. qa 3: fingerprints sourced from ruff --output-format=json, never text scraping (R1.1).
6. arch A1: baseline scoped to python-fastapi this build; explicit not-supported WARN on other profiles (R1.0); dart/markdown baselining = follow-on triage item.
Advisories folded (cheap): executable allow-list for profile argv[0] + trust-boundary doc (F3); R2.4 enforced-in-code + disable-attempt test (F4); --fast excluded from the pre-commit verification cache (F5); markdown-corpus-with-.py warning (F6); yaml.safe_load committed, stdlib-only framing corrected (F7/A2); Path.as_posix() fingerprints (qa4); empty-profile fail-closed AC (qa5); _run() as the single mock seam (qa6); FRAMEWORK_SPECIFICATION added to doc hedge (A4). Deferred: A3 file-split marker (only if >1200-1500 lines). Spec status → reviewed; awaiting developer approval (Principle #9 / spec Step 8).

---
