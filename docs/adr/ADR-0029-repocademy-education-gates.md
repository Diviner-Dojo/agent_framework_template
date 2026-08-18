---
adr_id: ADR-0029
title: "Machine-readable education-gate registry + deterministic transcript ingest (RepoCademy Phase 0)"
status: accepted
date: 2026-07-14
decision_makers: [orchestrator, steward]
discussion_id: DISC-20260715-055927-build-education-gate-registry
spec_id: SPEC-20260714-220401-repocademy
supersedes:
extends:
scope: hybrid
risk_level: medium
confidence: 0.85
tags: [education-gates, repocademy, principle-6, trust-boundary, capture-pipeline, deterministic-ingest, versioned-contracts, tolerant-reader-strict-writer]
---

## Context

Principle #6 (education gates before merge: walkthrough → quiz → explain-back → merge) permits
deferral under autonomous execution, but the *record* of a deferred gate has lived only as prose —
scattered across `BUILD_STATUS.md`, rolling handoff notes, and REV report `§Education Gate` sections.
That prose is invisible to tooling: it cannot be queried, counted, or enforced, and it accumulates
silently. A concrete instance is the June 2026 telemetry cohort — six deferred gates from supervised
build sessions (`EDU-20260610-unit-3-3` through `unit-5-1`) sat open for roughly a month with nothing
in the repo able to *report* that they were open. CLAUDE.md Principle #6 says "deferred gates must be
completed before the next phase begins," but there was no artifact against which that sentence could
be tested. The deferral debt was real and growing, and only archaeology through old REV reports could
surface it.

At the same time, **RepoCademy** — a voice repo-walkthrough / tutoring module in the developer's
Flutter journal app (tracked by the external spec `SPEC-20260714-220401-repocademy`, which lives in the
`insight_journal` repo, not here) — needs two things this repo must provide:

1. A **machine-readable list of open gates** so the tutor can generate targeted, gate-clearing audio
   courses (walk the exact files/ADRs a deferred gate covers, then quiz on them).
2. A **trusted way to write completion evidence back** into this repo's capture stack when a learner
   actually walks and passes a gate on the phone — without letting phone-generated content (which is
   untrusted at the repo boundary, and in Phase 2 is routed through an LLM) write directly into Layer 1
   / Layer 2 / the gate state.

This is Phase 0 of that spec: stand up the registry and the ingest chokepoint here, so RepoCademy
Phase 1/2 (in `insight_journal`) has a stable contract to build against. The decision is `hybrid`
scope: the *principle* — a machine-readable education-gate registry plus a single deterministic
evidence-ingest chokepoint at the trust boundary — is universal to any project using this framework's
capture stack and education gates; the *implementation* here is specific to this repo's capture
pipeline (`create_discussion.py` / `write_event.py` / `education_results` / `evaluation.db`) and to
RepoCademy's transcript contract.

## Decision

Introduce four artifacts in this repo, plus one coverage-enforcement extension. The organizing
principle throughout is a **tolerant-reader / strict-writer asymmetry**: the phone (a reader over the
read-only GitHub API) degrades gracefully on anything it does not understand; the repo (the trust root
that flips gate state and writes the capture stack) rejects anything it does not understand.

### 1. `docs/education/gates.yaml` — the versioned registry

A schema-validated YAML registry (`version: 1`) of deferred education gates. Each gate carries:
`gate_id` (charset `^[A-Za-z0-9._-]+$`, unique), `created_at`, `origin` (the REV id / handoff / delivered
walkthrough doc that evidences the deferral), an optional `branch`, a `scope` block
(`files`, `adrs`, `spec`), a one-line `reason_deferred`, a `status` of `open | cleared | re-deferred`,
and `cleared_by` (null, or `{session_id, discussion_id, cleared_at}`). It was **seeded from real
deferral archaeology** — the six-gate June telemetry cohort recovered from REV `§Education Gate`
sections plus the `EDU-20260627-d2-backflow-patterns` gate recovered from its delivered-but-unclosed
walkthrough doc (seven open gates total). Crucially, gates whose deferral could **not** be evidenced
were deliberately omitted: telemetry units 3.1 (its REV carries no Education Gate section) and 3.2 (its
REV explicitly records the gate as waived/"Not needed," redundant with an earlier walkthrough). The
registry records only deferrals it can prove — it is a ledger, not a wishlist.

### 2. `scripts/education/gate_registry.py` — library + CLI

The registry's sole schema authority and writer-side validator. It provides `validate_gate` /
`validate_registry` (strict: unknown top-level, gate, `scope`, and `cleared_by` keys are all rejected;
`gate_id` charset enforced; `bool` rejected where `int` is required, since `bool` subclasses `int`),
`load_registry` / `save_registry` (atomic: temp file + `os.replace` + `fsync`, so a reader never sees a
half-written file), and query/mutate helpers (`list_gates`, `add_gate`, `clear_gate`, `re_defer_gate`).
A CLI exposes `list` / `add` / `clear` / `re-defer`. **`clear_gate` is idempotent**: clearing an
already-cleared gate returns `changed=False` and leaves the existing `cleared_by` untouched — never
overwriting the original clearing attestation. This idempotence is what makes the ingest safe to re-run.

### 3. `scripts/education/ingest_walkthrough_session.py` — the deterministic chokepoint

This is the **single writer** that converts an untrusted phone-generated session transcript into
durable capture-stack state. It is the load-bearing trust-boundary decision of this ADR. Its sequence:

- **Validate-before-write (pure, zero side effects).** Full schema validation of the transcript against
  CONTRACTS.md v1 runs first and writes nothing: required/unknown-key checks, the `contract_version == 1`
  gate, the `^[A-Za-z0-9._-]+$` charset on `session_id` and `gate_id` (both feed filesystem paths *and*
  SQLite keys — this is the path-traversal / injection defense), ISO-8601 timestamp parseability, and
  enum whitelists for `bloom` / `question_type`. Those enums are **imported from
  `scripts/record_education.py`** (`BLOOM_LEVELS`, `QUESTION_TYPES`, hoisted there to be the single
  source mirroring the `education_results` CHECK constraints) — never redefined here, so the ingest and
  the DB constraint can never drift apart. Scores are **clamped** to `[0, 1]`, never rejected (a locked
  decision). Resource caps bound the untrusted payload (2 MB file, checked before read; 500 events;
  20k chars per string field; 128-char IDs — see CONTRACTS.md §1.1); violations are rejected, never
  truncated. Any validation failure → exit code 2, one-line stderr, zero writes.
- **Write, in a fixed order.** A discussion (Layer 1 dir + Layer 2 `discussions` row) → `events.jsonl`
  turns under a **locked 7-intent mapping** (`narration→proposal`, `qa_exchange→question`+`evidence`,
  `quiz_item→question`+`evidence`+`critique`, `explain_back→question`+`evidence`+`critique`,
  `deferral→decision`, `completion→synthesis`) written strictly sequentially (never in parallel) →
  `education_results` rows in a **single transaction** → the registry flip **last**.
- **Recomputed clearing rule (the aggregate is never trusted from the payload).** A gate clears iff the
  session `walked` (≥1 narration) **AND** the terminal-quiz average `>= 0.70` (variant items supersede
  the originals they re-teach, so a re-taught-and-passed item is not dragged down by its original miss)
  **AND** every explain-back scored `>= 0.70` **AND** `mode == gate`. **`mode == gate` is a precondition
  for ANY registry action, evaluated first:** a learn-mode session never touches the registry — not even
  a learn-mode session containing a session-level deferral (it is recorded as a `decision` event only).
  In gate mode, a session-level deferral re-defers instead of clearing; a below-threshold "completed"
  session records all evidence but leaves the gate open. The transcript's own `outcome.status` is
  declarative only — the ingest recomputes the aggregate decision from the graded events and never lets
  a `status` claim flip a gate. Note the precise authority split: per-item *scores* are
  producer-authoritative (the phone-side LLM grader); the ingest clamps them to `[0,1]` and recomputes
  only the *aggregate* rule (see Consequences for the accepted risk).
- **Fail toward under-clearing.** The `education_results` transaction commits *before* the registry
  saves. This one small non-atomic window is deliberate: a crash between the DB commit and the registry
  save leaves evidence recorded but the gate still open (under-clearing), which is manually recoverable
  with `gate_registry.py clear` — never the reverse (a cleared gate with no evidence). Post-write
  failures trigger best-effort compensation (discussion dir + row + this session's education rows
  removed; registry untouched).
- **Idempotent re-runs.** Guarded by `session_id` through three detectors: the gate already cleared by
  this session, an `education_results` row for the session, or a discussion whose deterministic slug
  (`education-<gate_id>-<session_id>`, lowercased) embeds the session — the last covers
  zero-education-row sessions such as an immediate session-level deferral, which would otherwise escape
  the row-based guard. The no-op prints `already ingested - no-op (session_id=...)` so cross-device
  session-id collisions are observable in watcher logs. A window-interrupted session recovers via a
  one-line CLI clear, not a re-ingest.

### 4. `docs/education/CONTRACTS.md` — versioned data contracts

The authoritative, versioned definition of every payload crossing the phone↔repo boundary:
session-transcript JSON (v1), course/chapter frontmatter (v1), and knowledge-note (v1). It codifies the
tolerant-reader / strict-writer split explicitly, documents the single-writer topology of `gates.yaml`,
and states the versioning policy: additive changes are minor notes (tolerant readers ignore unknown
keys; the strict validator must be taught to accept the new key in the same change), while breaking
changes (rename/remove a key, change a type, tighten an enum, change the clearing rule) **bump the
affected format's `contract_version`** — each format versioning independently. The phone app builds
against this document; a v2 transcript is rejected by a v1 ingest until the ingest is taught v2.

### 5. Coverage enforcement extended

The quality gate measures `scripts/education/` for coverage both in the aggregate `--cov` run **and**
with an isolated 80% floor (`coverage report --include=scripts/education/* --fail-under=80`). Without
the isolated floor, `src/`'s much larger statement count could mask a coverage regression inside this
security-sensitive chokepoint behind a green project-wide TOTAL.

## Consequences

- **The deferral debt is now visible and queryable.** `gate_registry.py list --status open` reports
  the seven seeded open gates; Principle #6's "deferred gates must be completed before the next phase
  begins" becomes a testable assertion the `/retro` and `/review` flows can check against a real
  artifact instead of prose archaeology. The registry is the authority for gate state.
- **RepoCademy Phase 1/2 (in `insight_journal`) builds against CONTRACTS.md v1.** The phone app has a
  stable, versioned target for both directions: read open gates over the read-only GitHub API, and
  write evidence back through the ingest.
- **The trust boundary is a single deterministic script, permanently.** Phone-generated (and, in Phase
  2, LLM-packaged) content can never write directly to Layer 1/2 or flip a gate. The LLM step in Phase 2
  only wraps a PR around artifacts this deterministic ingest has already produced and validated.
- **Format evolution has discipline.** Future breaking changes require a `contract_version` bump plus
  continued tolerant-reader behavior on the phone, so an older app build never breaks on an additive
  field and never silently misreads a breaking one.
- **A new maintenance surface.** `gates.yaml`, the registry library, the ingest, and CONTRACTS.md must
  be kept in sync; the imported-enum discipline (`record_education.py` as the single source) and the
  isolated coverage floor are the guardrails that keep drift out.
- **Single-writer assumption is documented, not enforced by a lock.** The registry has exactly one
  writer (the ingest/watcher path); this topology is recorded in CONTRACTS.md and revisited only if a
  second concurrent writer ever appears (see Alternatives). The ingest's temporary redirection of the
  reused capture-helper module globals (`create_discussion.DB_PATH` etc.) is likewise sound *only*
  under this sequential single-writer topology — the mutation site carries a comment tying it to this
  assumption.
- **Accepted risk: grade inflation via self-reported scores.** Per-item scores are
  producer-authoritative — the phone-side LLM grader assigns them, and the ingest accepts them (clamped)
  without re-grading. A gate can therefore auto-clear on scores the repo never independently verified.
  This is **intentional for the single-user BYOK context**: the learner and the repo owner are the same
  person, and the incentive to game one's own education gates is nil. The mitigation is auditability,
  not prevention — every cleared gate carries its full discussion evidence (`events.jsonl` with the
  graded exchanges) reviewable at `/retro` time, and `cleared_by` pins the exact session. **Revisit
  before any multi-user deployment** (an independent repo-side grading pass would then be required).
- **Stored prompt-injection surface (downstream-consumer requirement).** Transcript free-text is
  attacker-influenced data written verbatim into `events.jsonl`, and it later flows through transcript
  generation, findings extraction, and potentially LLM contexts in retro/mining flows. Downstream
  consumers MUST treat event bodies as data, never instructions (untrusted-content delimiters in any
  LLM prompt; no exec/eval/shell interpolation). The ingest itself never interpolates transcript
  content into SQL, paths, or commands. Documented in CONTRACTS.md §1.4.
- **Layer-2 query note: education events reuse the review intents.** The locked mapping emits
  `proposal`/`evidence`/`critique` — the same intents review discussions use — so intent-based mining
  and agent-effectiveness queries would conflate tutoring exchanges with review findings if run
  undiscriminated. The ingest registers its discussions with `command_type='education'` and tags every
  event `education,repocademy,gate:<gate_id>`; **consumers must filter on that `command_type` (or the
  tags) when aggregating review-oriented metrics.**
- **Tracked follow-up: enrollment automation.** Nothing yet calls `add_gate` when a future `/review`
  defers an education gate — the registry only grows via the CLI. Until an enrollment hook is wired
  into the review/deferral flow, **adding the gate via `gate_registry.py add` is a required manual step
  of logging any new deferral** (alongside the BUILD_STATUS/retro note). This is the known gap between
  "the registry exists" and "the registry is automatically complete."

Related: `SPEC-20260714-220401-repocademy` (external, `insight_journal` repo); the checkpoint discussion
`DISC-20260715-055927-build-education-gate-registry`; ADR-0022 / ADR-0023 / ADR-0024 (the subjects of
the `EDU-20260627-d2-backflow-patterns` gate); Principle #4 (independent evaluation — the deterministic
ingest is the independent, non-LLM writer), Principle #6 (education gates — now machine-tracked), and
Principle #8 (least-complex intervention — the deferred lockfile).

## Alternatives Considered

- **Keep prose tracking in `BUILD_STATUS.md` (status quo):** rejected. It fails the core requirement —
  machine-readability. Prose deferrals are unqueryable, uncountable, and accumulate invisibly; the
  month-long six-gate cohort is the direct evidence of that failure mode.
- **Track gates in SQLite only (Layer 2):** rejected. A gate is a decision record that belongs under
  version control where it is diffable and reviewable, and the phone reads it over the GitHub API — it
  cannot reach `evaluation.db`. A DB-only registry would lose git history/reviewability and be
  unreadable by the intended consumer. (Evidence *rows* still land in SQLite via `education_results`;
  the *gate state* is the git-tracked YAML.)
- **Let the Phase-2 watcher's Claude Code dispatch write evidence directly:** rejected as a trust-boundary
  violation. LLM-mediated writes derived from untrusted transcript content must not reach into Layer 1/2
  or flip gate state. The deterministic script is the *only* writer; the Phase-2 LLM step is confined to
  packaging a PR around artifacts this script has already produced and validated. This is the load-bearing
  decision of the ADR.
- **A lockfile for concurrent registry writers:** deferred per Principle #8. `save_registry` is already
  atomic (temp file + `os.replace`), and the watcher processes gate sessions strictly sequentially, so
  under the documented single-watcher topology there is no concurrent writer to guard against. Revisit
  with an advisory lockfile or a compare-and-swap on a revision field only if a second concurrent writer
  is ever introduced.
- **Reject out-of-range scores instead of clamping:** rejected (locked). Clamping to `[0, 1]` keeps a
  malformed-but-well-intentioned score from discarding a whole session's evidence; the pass threshold is
  applied to the clamped value, so clamping cannot manufacture a false pass.
- **Redefine the `bloom` / `question_type` enums in the ingest:** rejected. Importing them from
  `record_education.py` (the single source mirroring the DB CHECK constraints) is the only way to
  guarantee the validator and the database can never disagree about the allowed vocabulary.
