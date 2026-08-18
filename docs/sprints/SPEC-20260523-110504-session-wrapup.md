---
spec_id: SPEC-20260523-110504
title: "Model-Aware Session Wrap-Up & Handoff"
type: spec
status: complete
risk_level: high
intake_ids: []
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260523-190838-session-wrapup-spec-review
completed_at: 2026-05-23
completed_commit: 9601776
status_note: "stamped complete post-hoc 2026-07-16 during the wave-2 spec-budget check (shipping evidence: git log; part of triage #11 bookkeeping debt)"
---

## Goal

Make every session **self-aware of its context-window occupancy** and, once usage crosses a
**model-specific** "optimal working fraction", **cleanly wrap up** — finish the current step,
capture state, write a paste-ready handoff prompt — *before* quality degrades. The **shipped
framework posture is "wrap up + offer to continue"**; **auto-launching a fresh session is the
operative behavior only when the human has authored BOTH consent keys** (the CLAUDE.md Autonomous
Execution Authorization AND a separate `ALLOW_AUTO_LAUNCH_SESSION`) — see R7. Self-awareness +
proactive wrap-up is the default for every session; **spawning a continuation is never the
out-of-box default and is never set by distribution** (Steward gate conditions 1–2). Delivered as a
framework capability (ADR-0018) and later distributed to derived projects via `/distribute`.

## Context

Long sessions silently degrade. As a context window fills, recall drops ("context rot",
"lost-in-the-middle") and **every turn re-pays the resident context** (ADR-0016's core thesis),
so a fuller window costs more per turn *and* answers worse. Today the framework has no awareness
of its own context occupancy: `BUILD_STATUS.md` + the PreCompact hook only react *at* Claude
Code's ~83% auto-compaction — a lossy, late, involuntary event.

**Research grounding (web research, cited in ADR-0018):** Anthropic publishes *no* hard
"% threshold"; third-party benchmarks (RULER/LongBench) place the high-quality "effective"
zone at ~50–65% of the window; Claude degrades slowest among frontier models but is not immune.
Windows: Opus 4.7 / Sonnet 4.6 = 1,000,000; Sonnet 4.5 / Haiku 4.5 = 200,000. Auto-compaction
default ~83% is a backstop we stay below, configurable earlier (never later) via
`CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` / `CLAUDE_CODE_AUTO_COMPACT_WINDOW`.

**Prior art (this repo):**
- `BUILD_STATUS.md` durable session ledger; `pre-compact.ps1` / `session-start.ps1` lifecycle hooks (ADR-0016).
- `scripts/ingest_token_usage.py` already locates Claude Code transcripts and parses `message.usage.*` + `message.model` (offline today; reusable for a fallback occupancy estimate).
- `config/model_pricing.yaml` (ADR-0013) — the tier-alias→model-ID config pattern to mirror.
- `docs/dispatches/phase4-build-handoff.md` — a "paste into a fresh session" handoff structural precedent.
- Existing hooks use a `.sh`→Python delegate pattern with `additionalContext` injection, `permissionDecision`, and timestamped `.state/` debounce files (5-minute verification-cache precedent).

## Requirements

- **R1 — Occupancy sensor.** A `statusLine` command receives Claude Code's `context_window` JSON and
  writes an atomic, per-session sidecar (`.claude/hooks/.state/context-occupancy.<session_id>.json`)
  while also printing a one-line display. statusLine is the only *confirmed* live context signal.
  The `session_id` used in any filename **MUST** be validated against `^[A-Za-z0-9_-]{1,64}$` before
  it touches a path (B-SEC-1/A-SEC-1); a non-matching value → degrade to silence. Atomic write =
  temp-then-rename. If `context_window`/`used_percentage` is absent from the JSON, write no sidecar
  (graceful degrade, B-QA-13).
- **R2 — Core sensor module + transcript fallback.** A single module **`src/context_sensor.py`**
  (placed under `src/` so it is inside the `--cov=src/` perimeter — B-QA-1) is the **SOLE owner** of:
  model resolution, `resolve_threshold()`, sidecar read + freshness check, transcript-estimate
  fallback, and the unified occupancy record (B-ARCH-2). The hook wrappers and the skill stay thin and
  import from it. Freshness is governed by a named constant `SIDECAR_FRESHNESS_SECONDS` (default 300,
  mirroring the existing 5-min `commit-verified` precedent — B-QA-5): a sidecar older than this is
  stale. When the sidecar is missing/stale, the module estimates occupancy from the transcript by
  reusing `scripts/ingest_token_usage.py` (`parse_session_dir`, `MessageRecord.model`), reading **only
  numeric `usage.*` fields and `model`** — never message/tool string content (A-SEC-4) — stamped
  `source:"transcript-estimate"`. If neither signal is available (missing/empty/all-malformed
  transcript), it returns "no signal" and callers degrade to silence — it never errors the session.
- **R3 — Model-specific thresholds.** A new `config/model_context_profiles.yaml` resolves the current
  model → profile (tier × window-class) → soft/hard thresholds, where
  `effective = min(fraction × window, absolute_cap)`. **Each profile carries explicit `*_fraction`
  AND `*_abs_cap_tokens` values** (not just the effective token counts — B-QA-3) so the `min()`
  crossover is exercisable. Comparison is canonical on **integer tokens** with `>=` (inclusive) at both
  soft and hard (B-QA-10). Unknown model IDs fall back to the **most conservative profile**
  (`haiku_200k`, the floor) so an unknown model wraps up *earlier* — its resolved soft/hard MUST be
  ≤ any known model's (B-QA-8).
  The `models:` ID→profile map is **deliberately independent** of `model_pricing.yaml`'s `models:`
  map (different update cadences: pricing on price changes, profiles on new-model windows); ADR-0018
  records this as a conscious duplication (A-ARCH-5).
- **R4 — Self-awareness feedback (v1, advisory).** A `UserPromptSubmit` hook reads the sidecar/fallback
  via `src/context_sensor.py`, resolves the threshold, and at/above the soft threshold (`used ≥ soft_tok`)
  injects an `additionalContext` nudge to begin wrapping up. The nudge is one-shot per crossing,
  debounced via a named flag file `.claude/hooks/.state/context-guard-armed.<session_id>` (present =
  already nudged; **re-armed by deleting the flag** when occupancy drops back below soft, e.g. after a
  manual `/compact` — B-QA-4). A separate `context-guard-hard.<session_id>` flag governs the hard
  message. Below soft it emits nothing (no `additionalContext` key). The injected text **MUST** be a
  fixed template plus numeric occupancy/threshold values only — never interpolated transcript content.
- **R5 — Wrap-up protocol.** A `wrapping-up-sessions` skill defines the procedure: announce trigger →
  finish/checkpoint the current atomic step (never mid-edit; verify no locks) → update `BUILD_STATUS.md`
  (ADR-0016: digest noisy output, stable prefix) → close/checkpoint open discussions
  (`close_discussion.py` / `write_event.py`) → write the handoff artifact → decide continuation → report.
- **R6 — Handoff artifact.** Written to `docs/handoff/HANDOFF-<YYYYMMDD-HHMMSS>.md` from a
  `docs/templates/handoff-template.md` template (modeled on `phase4-build-handoff.md`). Sections:
  What this is · Required reading (ordered) · Settled decisions · Work completed · Work in-progress
  (checkpoint) · Exact next steps (imperatives) · Open questions (flag blockers) · Active DISC/SPEC/ADR
  IDs · Coordination notes · Out of scope · Carry-forward constraints. **Lineage-preservation sections
  (mandatory, Steward condition 3 — Principles #1/#2/#4/#6):** the template MUST also carry
  **(a) open `/review` advisories** (so the continuation cannot resume past a pending independent
  evaluation), **(b) un-completed education-gate deferrals** (owed walkthrough/quiz/explain-back),
  and **(c) an explicit statement that the continuation inherits the full CLAUDE.md + rules and MUST
  run `/review` before any commit and MUST NOT bypass capture.** **Retention cap = exactly
  `HANDOFF_RETENTION_CAP` (default 5), FIFO eviction by filename timestamp** (B-QA-12). **`docs/handoff/`
  and `.claude/hooks/.state/` MUST be added to `.gitignore`** — handoff/state files carry session
  context + model/threshold metadata and must never be committed (B-SEC-2/A-SEC-2). `src/context_sensor.py`
  (or the skill) is the **sole writer** of `docs/handoff/`. `BUILD_STATUS.md`'s `## ⮕ NEXT SESSION` gets a
  one-line pointer (no content duplication).
- **R7 — Auto-launch continuation (default, hardened).** After writing the handoff, spawn a detached
  headless continuation **only when BOTH** (a) the session is under the CLAUDE.md Autonomous Execution
  Authorization **AND** (b) an explicit, separate opt-in `ALLOW_AUTO_LAUNCH_SESSION` is set — the general
  autonomous-auth flag authorizes *workflow steps*, not *process spawning*, so a distinct consent key is
  required (A-SEC-3, ties to Prime Objective (c) per-instance assent + Principle #7). Otherwise fall back
  to handoff + offer (print the `claude --resume` / paste path). **Spawn safety (mandatory, B-SEC-1):**
  (1) `subprocess.run(cmd, shell=False)` where `cmd` is a discrete argv list — no shell parsing; the
  validated handoff path is inlined into a fixed single-positional `--print` prompt (the form the CLI
  accepts; injection-safe because no shell parses it and the only variable element is the validated
  path — reconciled with /review IP-B1, which found a separate trailing path arg is not honored);
  (2) canonicalize and assert `Path(path).resolve().is_relative_to(HANDOFF_DIR)`, abort on failure;
  (3) the `session_id` in the path was already allowlist-validated (R1). The launch
  inherits all Prohibited Actions (no push, no destructive git, no settings edits, no auto-merge), seeds
  only the **validated handoff path** (never untrusted prompt/reply text), enforces a **spawn-chain depth cap**
  `MAX_AUTO_LAUNCH_DEPTH` (default 1) written into the handoff and re-checked before each launch (no
  runaway chains — A-SEC-3), and notifies the developer (ntfy, per `notifying-the-developer`) with the
  handoff path. The launch decision is produced by a pure, unit-testable
  `build_launch_command(handoff_path: Path, auth: bool, allow_launch: bool, depth: int) -> list[str] | None`
  (returns `None` when not authorized — B-QA-2); CI tests the builder and never spawns a process.
- **R8 — Command + backstop.** A thin `/handoff` command (`argument-hint: "[--launch headless|none] [--soft|--hard]"`)
  invokes the skill deterministically. `pre-compact.ps1` gains a one-line reminder so a missed trigger
  still produces a handoff before forced compaction (additive only; a PowerShell parse-check smoke
  verifies the edit doesn't break the existing hook — B-QA-14).
- **R9 — Backstop env wiring (manual, no new tooling).** `.claude/settings.json` `"env"` sets
  `CLAUDE_AUTOCOMPACT_*` above our hard threshold but ≤83%, so proactive wrap-up always fires first.
  `.claude/settings.json` is in `validate_tool_use.py` PROTECTED_PATTERNS, and **no `/update-config`
  skill exists** (B-ARCH-1). v1 therefore applies this as a **documented manual edit** the developer
  performs (the skill ships the exact diff to paste), matching the `/seed` precedent — this feature
  introduces **no config-mutation tool**. No feature hook ever writes to a PROTECTED_PATTERNS file
  (hooks read config only — A-SEC-5).

## Constraints

- **Phased enforcement (Principle #8).** v1 ships advisory self-awareness only (R4). The coercive
  `Stop`-hook block at the hard threshold is **v2**, gated on proving the advisory path and on the
  (undocumented) availability of hook context behavior; it must use bounded retries then yield to the
  ~83% auto-compact backstop to avoid stop-loops. **v2 is NOT authorized by the ADR-0018 Steward gate**
  (Steward condition 4): it returns for a separate Steward gate + developer approval when proposed.
- **Distribution preserves per-instance consent (Steward condition 2, Prime Objective clause c).**
  `/distribute` MUST NEVER stage or set either consent key (`ALLOW_AUTO_LAUNCH_SESSION` or the
  Autonomous Execution Authorization) in a target — the derived project's human authors both keys
  themselves as a fresh per-instance act. `ALLOW_AUTO_LAUNCH_SESSION` and the per-model threshold
  numbers are **pinned-trait candidates** so distribution can never overwrite a target's local consent
  posture or tuning. Recorded as an ADR-0018 Consequence.
- **statusLine is display-only** and cannot halt or inject — all feedback flows through the sidecar +
  hooks. Whether hooks receive `context_window` data is **undocumented**; the design must not depend on it.
- **Transcript-estimate occupancy is approximate** (cache reads, sliding-window eviction, system overhead)
  — labeled lower-confidence; never treated as authoritative when a fresh statusLine sidecar exists.
- **No Anthropic-official threshold exists** — defaults are research-informed heuristics and must be
  one-line tunable in YAML (no schema migration), mirroring ADR-0013.
- **`.sh`→Python delegate** pattern for cross-platform hooks; PowerShell is sandbox-blocked in this
  environment (BUILD_STATUS Gotchas) — new sensor/guard scripts call `python` like
  `pre-tool-use-validator.sh`.
- **Auto-launch is a real OS process** — privileged, never silent, authorization-gated, no-push,
  file-path-seeded, ntfy-notified. `Task` subagents are explicitly **not** a continuation mechanism
  (isolated context, cannot continue the main thread, cannot spawn subagents).
- **Env-var backstop** applies to new sessions only and cannot exceed ~83%.
- **Governance:** changes default session behavior → ADR-0018 (0017 is owed to `/distribute`), Steward
  gate vs PHILOSOPHY.md, developer approval (Principle #7), `/review`, doc sync.

## Acceptance Criteria

- [ ] **AC-1 (thresholds):** `resolve_threshold("claude-opus-4-7")` → `opus_1m` soft=140000/hard=180000;
      unknown ID → `haiku_200k` (the floor) with soft/hard ≤ every known model's. Three parametrized `min()` cases:
      `fraction×window < cap` (fraction governs), `> cap` (cap governs), `== cap` (degenerate).
- [ ] **AC-2 (sensor):** a `_make_statusline_json()` fixture factory pins the expected fields; piping it
      into `context-statusline.sh` writes the sidecar atomically with correct
      `tier`/`soft_tok`/`hard_tok`/`source:"statusline"` and prints one display line. Missing-field JSON
      (`{}`, `{"context_window":{}}`, `used_percentage:null`) → no crash, no sidecar.
- [ ] **AC-2b (session_id guard):** a `session_id` not matching `^[A-Za-z0-9_-]{1,64}$` writes no sidecar
      and the path is never constructed from it.
- [ ] **AC-3 (fallback):** with no sidecar, the sensor estimates from a fixture transcript JSONL stamped
      `source:"transcript-estimate"`; empty / all-malformed / unknown-model transcripts → "no signal" →
      caller silent (no crash, no nudge).
- [ ] **AC-3b (freshness):** sidecar `written_at_epoch = now − SIDECAR_FRESHNESS_SECONDS − 1` → stale
      (falls back); `now − SIDECAR_FRESHNESS_SECONDS + 1` → fresh (used).
- [ ] **AC-4 (nudge oracle):** below soft → stdout has **no** `additionalContext` key; at/above soft →
      stdout JSON `additionalContext` is a **non-empty string containing the occupancy + threshold
      numbers**; a 2nd call with the armed flag present → silent; deleting the flag (occupancy < soft)
      re-arms → nudge re-emitted (4-step state machine). Boundaries tested just-below / at / just-above
      for soft and hard.
- [ ] **AC-4b (concurrency):** two sidecars with different `session_id`s at different occupancies →
      the guard invoked per session reads only its own sidecar.
- [ ] **AC-5 (handoff):** `/handoff --launch none` adds a BUILD_STATUS pointer (matched by regex
      `HANDOFF-\d{8}-\d{6}\.md`, not exact string), creates the file from the template, enforces
      `HANDOFF_RETENTION_CAP` (create 6 → exactly 5 remain, oldest evicted), attempts no push.
- [ ] **AC-5b (lineage preservation, Steward condition 3):** the rendered handoff contains the
      open-`/review`-advisories section, the un-completed-education-deferrals section, and the explicit
      "inherits CLAUDE.md + MUST run `/review` before any commit + MUST NOT bypass capture" statement.
- [ ] **AC-6 (auto-launch builder):** `build_launch_command(...)` returns `None` when auth OFF **or**
      `ALLOW_AUTO_LAUNCH_SESSION` unset **or** depth ≥ `MAX_AUTO_LAUNCH_DEPTH`; otherwise returns a
      `list[str]` whose path element is canonicalized inside `HANDOFF_DIR` and an ntfy notification is
      requested. Unit-tested; **no process spawned in CI**. A path resolving outside `HANDOFF_DIR` →
      builder aborts.
- [ ] **AC-7 (gates):** `tests/test_context_sensor.py` passes; **the new logic lives in `src/` so it is
      inside `--cov=src/`**; `python scripts/quality_gate.py` is green (coverage ≥80%). `.gitignore`
      excludes `docs/handoff/` and `.claude/hooks/.state/`.
- [ ] **AC-8 (ADR):** ADR-0018 records the threshold model (and why 1M needs the cap), the honest
      limitations, the deliberate model-ID-list duplication, the separate `ALLOW_AUTO_LAUNCH_SESSION`
      consent key, the **consent-default decision** (shipped posture = wrap-up + offer; auto-launch only
      when both keys present; *why* clauses (b)/(c) require it — Steward condition 1), the **distribution
      consent rule** (`/distribute` never sets either key; both are pinned-trait candidates — condition 2),
      the **v2-coercion deferral** (not authorized by this gate — condition 4), and the alternatives
      rejected (percentage-only; per-window config files; hook-only mechanical trigger).
- [ ] **AC-9 (docs):** CLAUDE.md updated (Session State, Always-On, Rules Index, Directory Layout,
      Autonomous Execution); doc-sync surface updated (FRAMEWORK_SPECIFICATION §6/§14/§15, the 2
      presentation HTMLs).

## Risk Assessment

- **Threshold values wrong for real workloads** (too eager → handoff churn; too late → degradation).
  *Mitigation:* one-line-tunable YAML; conservative defaults; per-target pinned-trait on distribution.
- **Sidecar staleness / race across parallel sessions/worktrees.** *Mitigation:* per-`session_id`
  filenames, atomic temp-then-rename, `written_at_epoch` freshness check, transcript fallback.
- **Auto-launch runaway / cost / unintended writes.** *Mitigation:* authorization gate, inherited
  Prohibited Actions, no-push, file-path seeding, ntfy notify; default-off outside autonomous auth.
- **Undocumented hook context access breaks v2 coercion.** *Mitigation:* v1 doesn't depend on it; v2 is
  separately gated with bounded retries + backstop.
- **statusLine performance** (fires sub-second). *Mitigation:* writer parses stdin + one atomic write +
  print; transcript work is confined to the guard's fallback path only.
- **Distribution clobbers local tuning.** *Mitigation:* declare per-model numbers a pinned-trait candidate
  (noted in ADR Consequences).

## Affected Components

- **New:** `config/model_context_profiles.yaml`; **`src/context_sensor.py`** (the pure-logic core —
  under `src/` for coverage, B-QA-1/B-ARCH-2); thin hook wrappers `.claude/hooks/context-statusline.sh`
  + `context_statusline.py` and `.claude/hooks/context-guard.sh` + `context_guard.py` (both import the
  core); `.claude/skills/wrapping-up-sessions/SKILL.md`; `.claude/commands/handoff.md`;
  `docs/templates/handoff-template.md`; `docs/adr/ADR-0018-model-aware-session-wrapup.md`;
  `tests/test_context_sensor.py`; `docs/handoff/` (dir, gitignored).
- **Modified:** `.claude/settings.json` (statusLine + UserPromptSubmit hooks + `"env"` — **manual edit**,
  protected file, no `/update-config`); `.claude/hooks/pre-compact.ps1` (backstop reminder, additive);
  `.gitignore` (add `docs/handoff/`, `.claude/hooks/.state/`); `CLAUDE.md` (5 sections);
  `docs/FRAMEWORK_SPECIFICATION.md` + 2 presentation HTMLs (doc sync).
- **Reused (no change expected):** `scripts/ingest_token_usage.py`, `scripts/notify.py` /
  `scripts/ask_developer.py`, `scripts/close_discussion.py` / `scripts/write_event.py`.

## Dependencies

- **Depends on:** Claude Code statusLine JSON schema (confirmed: `context_window.{used_percentage,
  context_window_size,total_input_tokens}`, `transcript_path`, `model`); `ingest_token_usage.py` parse
  helpers; ADR-0013 config pattern; ADR-0016 BUILD_STATUS lifecycle.
- **Depended on by:** later `/distribute` propagation to the 3 derived targets; potential v2 coercive
  Stop-hook; future version bump (v3.5 → v3.6) at `/ship`.
- **Sequencing note:** ADR-0017 is owed to `/distribute` (BUILD_STATUS B5); this feature claims **ADR-0018**.

## Specialist Review Resolutions

Reviewed in `DISC-20260523-190838-session-wrapup-spec-review`. Architecture **APPROVE-WITH-CHANGES (0.82)**;
Security **REVISE (0.87)**; QA **REVISE (0.82)**. All blocking findings resolved into the spec above:

| Finding | Resolution |
|---|---|
| B-ARCH-1 — `/update-config` skill doesn't exist; settings.json protected | R9 → documented **manual** edit (the `/seed` precedent); no config-mutation tool introduced |
| B-ARCH-2 — `context_sensor.py` ownership undefined | R2 makes `src/context_sensor.py` the **sole owner** of model resolution / `resolve_threshold()` / sidecar+freshness / fallback / occupancy record; hooks+skill thin |
| B-SEC-1 — handoff path → spawn injection | R7: `shell=False` + discrete-arg list; canonicalize + `is_relative_to(HANDOFF_DIR)`; `session_id` allowlist `^[A-Za-z0-9_-]{1,64}$` (R1) |
| B-SEC-2 — handoff/state files not gitignored | R6: add `docs/handoff/` + `.claude/hooks/.state/` to `.gitignore`; AC-7 verifies |
| A-SEC-3 — auto-launch consent + runaway | R7: separate explicit `ALLOW_AUTO_LAUNCH_SESSION` key (distinct from autonomous-auth) + `MAX_AUTO_LAUNCH_DEPTH` (default 1) written to handoff and re-checked |
| A-SEC-4 — transcript string injection | R2/R4: read **only numeric `usage.*` + model**; injected text is fixed template + numbers only |
| B-QA-1 — coverage perimeter (`--cov=src/`) | Core logic placed in `src/context_sensor.py`; AC-7 |
| B-QA-2 — command-builder seam undefined | R7: `build_launch_command(handoff_path, auth, allow_launch, depth) -> list[str] | None`; AC-6 |
| B-QA-3 — `min()` crossover untested | R3: explicit `*_fraction` + `*_abs_cap_tokens` per profile; AC-1 three cases |
| B-QA-4 — debounce flag + re-arm | R4: named flags `context-guard-armed/-hard.<session_id>`; delete-to-re-arm; AC-4 4-step |
| B-QA-5 — freshness threshold unnamed | R2: `SIDECAR_FRESHNESS_SECONDS` (default 300); AC-3b boundary |
| B-QA-6 — statusLine shape not pinned | AC-2: `_make_statusline_json()` fixture factory |
| B-QA-7 — nudge oracle undefined | AC-4: assert parsed-stdout `additionalContext` non-empty w/ numbers; 2nd call silent |
| A-ARCH-5 / B-QA-8/10/12/13/14/15 | R3 (`>=`/int tokens; conservative-fallback ≤; deliberate ID-list duplication), R6 (`HANDOFF_RETENTION_CAP`=5 FIFO), AC-2/4/5 (boundary, missing-field, glob-match), R8 (ps1 parse-check) |

**Advisory (deferred, non-blocking):** A-ARCH-6 (guard resolves same `session_id` as writer, else newest
sidecar by `written_at_epoch`) — fold into the build as the documented degradation path.

## Steward Gate Resolutions

Gated in `DISC-20260523-191709-session-wrapup-steward-gate`. Verdict **REVISE (0.88)** — intent + mechanism
sound and mission-aligned; the dual-key consent design is consistent with Prime Objective (c) and
Principle #7. Four precision conditions (not redesign), all folded above; the Steward confirmed it does
**not** need to return after folding → proceed to developer approval, then build.

| Condition | Resolution |
|---|---|
| 1 — Disambiguate "default" | Goal/Context rewritten: shipped posture = **wrap-up + offer**; auto-launch operative **only when both human-authored consent keys present**. ADR-0018 records the consent-default decision (AC-8). |
| 2 — Distribution preserves per-instance consent | New Constraint: `/distribute` never stages/sets either consent key; `ALLOW_AUTO_LAUNCH_SESSION` + threshold numbers are pinned-trait candidates. ADR Consequence (AC-8). |
| 3 — Handoff preserves lineage + open obligations | R6 template adds open-`/review`-advisories, education-deferrals, and "inherits CLAUDE.md + MUST run `/review` before commit + no capture bypass". AC-5b verifies. |
| 4 — v2 coercion behind its own gate | Constraint + AC-8: the coercive Stop-hook (v2) is **not authorized by this gate**; returns for a separate Steward gate + developer approval. |

Governance path confirmed by the Steward: spec-review ✓ → Steward gate ✓ → **developer approval (next)** →
`/build_module` → quality gate → `/review` → doc-sync. ADR-0018 is the correct home (ADR-0017 owed to
`/distribute`); consent-default + v2-deferral recorded as ADR content (Principle #5).
