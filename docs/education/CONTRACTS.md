# RepoCademy ⇄ Framework — Versioned Data Contracts

> **Owner:** `agent_framework_template` (this repo). **Consumers:** the RepoCademy
> module in the Flutter app (separate repo) and the Phase-2 dev-watcher relay.
>
> This document is the authoritative definition of every payload that crosses the
> repo boundary between the phone app and the repo-side ingest chokepoint. The
> phone app builds against these schemas. **Any breaking change bumps the version
> of the affected format** (see §4, Versioning Policy). See
> `SPEC-20260714-220401-repocademy` §5 and ADR-0029.

Formats defined here:

| Format | Current version | Producer | Consumer |
|---|---|---|---|
| Session-transcript JSON | **v1.1** (wire `contract_version: 1` — see changelog) | phone app (after a walkthrough/quiz session) | `scripts/education/ingest_walkthrough_session.py` |
| Course/chapter frontmatter | **v1** | course-generation service (phone or desk) | phone player + gate-course targeting |
| Knowledge-note | **v1** | tutor (during Q&A / generation) | personal wiki + framework `memory/` (human-promoted) |

### Changelog

- **2026-08-11 — Session-transcript JSON v1.1 (semantic revision, wire-compatible;
  ADR-0035).** §1.4 revised: the LOCKED formula now establishes
  **CLEAR-ELIGIBILITY**; `cleared` requires the developer's explicit
  `gate_registry.py clear` action, recorded with `cleared_by` provenance
  ("I clear it" — the educator/tutor teaches, records, and registers, but never
  marks the gate complete; ratified "Yes, everywhere", so the ingested-transcript
  route stopped auto-clearing too). The payload schema is UNCHANGED — producers
  keep emitting `contract_version: 1` and the ingest keeps pinning it; nothing on
  the wire moved, which is why this is v1.1 and not v2. **Consumer-visible value
  change (the concrete diff for watcher/log-parser authors):** the ingest CLI's
  machine summary line now emits `outcome=clear-eligible` where it emitted
  `outcome=cleared`, and §1.4's Reported-outcome column changed the same value —
  the value `cleared` no longer occurs on the automatic path, so anything
  matching on `outcome=cleared` silently stops matching and must be re-pointed
  at `clear-eligible`. Re-defer on a session-level deferral remains an automatic
  registry action (debt bookkeeping, not clearing). **Downstream consumers (insight_journal builds against this
  contract) must be notified at their next framework update**; the
  tutor-asymmetry question recorded with ADR-0035's Q9 conditions travels with
  that propagation.

- **2026-08-11 — additive `gates.yaml` extension: the `clear_eligible` marker.**
  So a paid-but-unclaimed gate stays distinguishable from unpaid debt after the
  ingest's console is gone, the ingest now records eligibility durably as an
  OPTIONAL additive gate field: `clear_eligible: {session_id, discussion_id,
  eligible_at}`. `status` stays `open` — **eligible is not cleared** —
  `cleared`/`cleared_by` remain reachable only through the developer's own
  `clear` (which removes the marker; so does a re-defer, and the repo-side
  validator rejects the marker on a `cleared` gate). This is an **additive,
  tolerant-reader-safe** change per §4: the phone app ignores unknown gate keys
  by the Reader-discipline rule above, and the strict repo validator was
  updated to accept the key in the same change. `gate_registry.py list
  --eligible` re-prints the developer's paste-ready clear command from the
  marker at any time.

### Reader discipline (LOCKED — checkpoint finding)

- **`docs/education/gates.yaml` readers (the phone app) MUST be TOLERANT
  READERS.** Unknown keys are ignored, not rejected. The app reads the registry
  through `GithubCodeService` to list gates; a future additive field (e.g. a new
  `scope` sub-key) must never break an older app build.
- **The repo-side validators are STRICT.** `gate_registry.py` and
  `ingest_walkthrough_session.py` reject unknown top-level/object keys, enforce
  enum whitelists, and validate ID charset. The strict boundary is the repo; the
  tolerant boundary is the phone. This asymmetry is intentional: the repo is the
  trust root that flips gates and writes the capture stack, so it must reject
  anything it does not understand; the phone only reads and must degrade
  gracefully.

---

## 1. Session-transcript JSON — v1.1 (wire `contract_version: 1`)

The payload the phone app assembles after a walkthrough/quiz (Learn or Gate mode)
session, stored in `tutor_gate_sessions.transcriptJson`, synced up, and handed by
the Phase-2 watcher to the ingest chokepoint. **This is untrusted input at the
repo boundary** — the ingest fully validates it before any write.

**Golden conformance fixture:** `docs/education/fixtures/transcript_v1_valid.json`
is the canonical all-five-shapes passing transcript. It is exercised by the ingest
test suite on every run; the phone repo copies it as its serializer conformance
target. Keep it in lockstep with any contract change.

### 1.1 Top-level object

```jsonc
{
  "contract_version": 1,                 // int, MUST equal 1
  "session_id": "GATE-20260715-...",     // str, charset ^[A-Za-z0-9._-]+$  (feeds DB keys)
  "gate_id": "EDU-20260610-unit-4-1",    // str, charset ^[A-Za-z0-9._-]+$  (feeds file paths + registry key)
  "repo_slug": "owner/agent_framework_template",  // str, 1..200 chars, non-empty
  "mode": "gate",                        // enum: "learn" | "gate"
  "started_at":  "2026-07-15T14:00:00+00:00",  // ISO-8601, parseable
  "completed_at":"2026-07-15T14:42:00+00:00",  // ISO-8601, parseable
  "events": [ /* ordered event objects, see §1.2 */ ],
  "outcome": { /* see §1.3 */ }
}
```

Rules (all enforced by the strict validator, **before any write**):

- **Every top-level key above is REQUIRED. Unknown top-level keys are rejected.**
- `contract_version` MUST be the integer `1` (a Python `bool` is rejected even
  though it subclasses `int`). A mismatch here is the app-vs-repo version gate.
- `session_id` and `gate_id` MUST match `^[A-Za-z0-9._-]+$`. This charset rejects
  path traversal (`../`), path separators, and whitespace — both IDs are
  interpolated into filesystem paths (the discussion directory) and used as SQLite
  keys. This is the primary injection defense.
- `mode` gates registry access: `mode == "gate"` is a **precondition for any
  registry action** — Learn sessions never clear *or re-defer* a gate (§1.4). It
  does not change validation.
- `repo_slug` is validated for **conformance and provenance only** (non-empty,
  ≤ 200 chars); the v1 ingest does not otherwise consume it.
- Timestamps must parse as ISO-8601 (`datetime.fromisoformat`). They are stored
  as strings; no timezone normalization is performed.
- `events` is a list (may be empty structurally; an empty list simply cannot
  satisfy the clearing rule in §1.4).

**Resource caps (enforced, violations = rejection).** The transcript is untrusted,
so producers MUST stay under these limits; exceeding any of them is an exit-2
atomic rejection, not a truncation:

| Limit | Value |
|---|---|
| Transcript file size | 2,000,000 bytes (checked before the file is read) |
| Events per transcript | 500 |
| Any string field | 20,000 chars |
| `session_id` / `gate_id` length | 128 chars |
| `repo_slug` length | 200 chars |

### 1.2 Event objects

Every event is an object with a `type` discriminator plus type-specific fields.
**Unknown event `type` values and unknown per-event keys are rejected.** The
ingest maps each event type onto `events.jsonl` intents (the fixed 7-value
`write_event.py` enum) and, for graded types, onto an `education_results` row.

Score fields are numeric (`int`/`float`; `bool` rejected) and are **CLAMPED** to
`[0.0, 1.0]` — an out-of-range score is clamped, never rejected (LOCKED). Clamping
happens before the `>= 0.70` pass test and before the DB write.

| `type` | Required fields | `events.jsonl` intent(s) → agent | `education_results` row |
|---|---|---|---|
| `narration` | `chapter_id` (str), `text` (str) | `proposal` → tutor | `understand` / `walkthrough` / score `1.0` / passed `true` |
| `qa_exchange` | `question` (str), `answer` (str) | `question` → learner, then `evidence` → tutor | *(none)* |
| `quiz_item` | `item_id` (str), `question` (str), `answer` (str), `score` (num), `bloom` (enum), `question_type` (enum), `variant_of` (str \| null) | `question` → tutor, `evidence` → learner, `critique` → tutor | *item*'s `bloom` / `question_type` / clamped `score` / passed `score >= 0.70` |
| `explain_back` | `prompt` (str), `answer` (str), `score` (num) | `question` → tutor, `evidence` → learner, `critique` → tutor | `evaluate` / `explain-back` / clamped `score` / passed `score >= 0.70` |
| `deferral` | `scope` (enum: `item` \| `session`), `reason` (str) | `decision` → learner | *(none)* |
| `completion` | `summary` (str) | `synthesis` → tutor | *(none)* |

Enum whitelists:

- `bloom` ∈ `{remember, understand, apply, analyze, evaluate, create}`
- `question_type` ∈ `{recall, walkthrough, debug-scenario, change-impact, explain-back}`

These are **not redefined** in the ingest — they are imported from
`scripts/record_education.py` (`BLOOM_LEVELS`, `QUESTION_TYPES`), which is the
single source of truth mirroring the `education_results` CHECK constraints. For
`explain_back`, `bloom`/`question_type` are **fixed** by the ingest to
`evaluate`/`explain-back` and are NOT read from the payload.

Optional per-event keys (accepted, not required):

- `quiz_item.rubric` (str) — grading rubric text, folded into the `critique`
  event content.
- `explain_back.item_id` (str).
- `narration.chapter_title` (str).
- `deferral.item_ref` (str) — for `scope: item`, the `item_id` of the quiz item
  being saved for later. Advisory linkage only; the ingest records it in the
  `decision` event content and does not act on it.

**Variant-after-miss linkage.** A `quiz_item` whose `variant_of` names another
item's `item_id` is the re-teach variant of that item. Both the missed original
and the passing variant get their own `education_results` row (the miss is
preserved in the record). For the gate-clearing average, a variant **supersedes**
the item it replaces: only *terminal* items (those not named by any later event's
`variant_of`) contribute to the quiz average. This prevents a re-taught-and-passed
item from being dragged below threshold by the original miss.

### 1.3 Outcome block

```jsonc
"outcome": {
  "status": "completed",        // enum: "completed" | "session-deferred"
  "summary": "..."              // optional str
}
```

- **REQUIRED key: `status`. Unknown keys rejected.**
- The outcome block is **declarative** — it states what the phone believes
  happened. The ingest **recomputes the aggregate eligibility decision** from the
  graded events (§1.4); it never trusts a `status` claim to flip a gate — and
  since rev 1.1 it never flips a gate to `cleared` at all (§1.4; ADR-0035).
- **Authority split (be precise about what "authoritative" means):** per-item
  *scores* are **producer-authoritative** — they come from the phone-side LLM
  grader and the ingest accepts them as-is (clamped to `[0,1]`, never re-graded).
  What the ingest recomputes is only the *aggregate* rule: walked / terminal-quiz
  average / explain-back threshold / deferral precedence. The trust model and the
  accepted grade-inflation risk are documented in ADR-0029 §Consequences.
- **Consistency (strict):** `status == "session-deferred"` **iff** the events
  contain a session-level deferral (`deferral` with `scope: session`). A mismatch
  is rejected. Exactly zero-or-one session-level deferral is allowed.

### 1.4 Gate-eligibility rule (LOCKED — rev 1.1, 2026-08-11; formerly "Gate-clearing rule")

Computed by the ingest, authoritatively, from the validated events:

```
clear_eligible  ⟺  walked  AND  quiz_avg >= 0.70  AND  explain_back_passed
```

where

- `walked` = at least one `narration` event is present;
- `quiz_avg` = mean of clamped scores over **terminal** `quiz_item` events (see
  variant supersession, §1.2); requires **at least one** terminal quiz item — a
  session with no graded quiz cannot become clear-eligible;
- `explain_back_passed` = at least one `explain_back` event **and** every
  `explain_back` clamped score `>= 0.70`.

**Eligibility is not clearance (rev 1.1; ADR-0035).** The formula passing
establishes **CLEAR-ELIGIBILITY** only. `cleared` requires the **developer's
explicit `gate_registry.py clear` action**, recorded with `cleared_by`
provenance (`session_id`, `discussion_id`, `cleared_at`); the ingest **never
calls `clear_gate()` on the automatic path**. When the formula passes, the
ingest records the **additive `clear_eligible` marker** on the gate
(`{session_id, discussion_id, eligible_at}` — see the changelog; `status` stays
`open`), reports the gate `clear-eligible`, and prints the exact clear command
for the developer to run — re-printable later via `gate_registry.py list
--eligible`.

Decision table — **`mode == "gate"` is a PRECONDITION for ANY registry action
(the two automatic writes: the `re_defer_gate` flip and the additive
`mark_clear_eligible` marker — `clear_gate` is never automatic) and for
eligibility itself**; the mode check is evaluated first:

| Condition | Registry action | Reported outcome |
|---|---|---|
| `mode == "learn"` (regardless of deferral or scores) | **NONE — registry never touched** | `recorded-open` |
| gate-mode, session-level deferral present | `re_defer_gate(reason=<deferral event reason>)` | `re-deferred` |
| gate-mode, no session deferral, `clear_eligible` true | `mark_clear_eligible(session_id, discussion_id)` — **additive marker; `status` stays `open`**; clear command printed for the developer | `clear-eligible` |
| gate-mode, no session deferral, `clear_eligible` false | *(no registry change)* | `recorded-open` |

- An **item-level** deferral (`scope: item`) is just a logged `decision` event; it
  does not end the session and does not affect eligibility.
- A **session-level** deferral ends the session and, in gate mode, re-defers the
  gate regardless of scores. In learn mode it is recorded as a `decision` event
  only — learn-mode sessions never touch the registry, even on deferral.
- **Completed-but-below-threshold**: all `education_results` rows are still
  written; the gate stays `open` (no flip, no command). Evidence is recorded
  either way.
- **Completed-and-eligible**: all rows are written, the gate stays `open`, and
  the flip is the developer's — nothing verifies the grading itself at this
  boundary (per-item scores stay producer-authoritative, §1.3); what changed is
  *who* closes the loop on them.

**Stored prompt-injection surface (downstream-consumer requirement).** Event
free-text (narration text, answers, rubrics, reasons, summaries) is
attacker-influenced data that the ingest writes verbatim into `events.jsonl`.
Those event bodies later flow through transcript generation, findings extraction,
and — potentially — future LLM contexts (retro/mining flows). Every downstream
consumer MUST treat event `content` as **data, never instructions**: wrap it in
untrusted-content delimiters before placing it in any LLM prompt, and never
execute, eval, or shell-interpolate it. The ingest itself never interpolates
transcript content into SQL, paths, or commands.

### 1.5 Ingest guarantees (summary — see the module docstring for detail)

- **Validate-before-write**: full schema/enum/charset/timestamp validation runs
  as a pure pass with zero side effects. Any failure → exit code `2`, one-line
  error to stderr, **zero writes** (atomic rejection).
- **Idempotent**: if ANY prior ingest of this `session_id` is detectable — the
  gate already cleared by it, an `education_results` row for it, or a discussion
  whose slug embeds it (this last guard covers zero-education-row sessions, e.g.
  an immediate session-level deferral) — the run is a no-op (exit `0`,
  `already ingested - no-op (session_id=...)`, printed so cross-device
  session-id collisions are observable). Re-running never duplicates events or
  rows.
- **All-or-nothing**: on any failure after discussion creation begins, the
  discussion directory + its `discussions` row + any `education_results` rows for
  the session are removed; the registry is left untouched.

---

## 2. Course / chapter frontmatter — v1

YAML frontmatter prepended to generated course and chapter markdown (per SPEC
§4.2 / §4.4). Courses pin a repo SHA; chapters record per-file SHAs; the quiz
block is pre-bundled with variants + rubrics so the quiz works offline (D13).

### 2.1 Course frontmatter — v1

```yaml
---
contract_version: 1
kind: course
course_id: TC-20260715-agent-framework-template   # charset ^[A-Za-z0-9._-]+$
repo_slug: owner/agent_framework_template
repo_url: https://github.com/owner/agent_framework_template
pinned_sha: 3f1c2ab...                    # 40-hex; the course is pinned to this commit
title: "The Agentic Framework Template"
generation_model: claude-opus-4-...       # model id that produced the course
cost_estimate_usd: 0.42                   # pre-generation estimate shown at consent
created_at: 2026-07-15T14:00:00+00:00
toc:                                       # proposed chapter plan (paths → chapter)
  - chapter_id: TC-...-ch01
    title: "Capture pipeline"
    order_index: 1
    sources: [scripts/write_event.py, scripts/create_discussion.py]
  - chapter_id: TC-...-ch02
    title: "Education gates"
    order_index: 2
    sources: [scripts/education/gate_registry.py]
---

<course overview markdown, spoken register>
```

### 2.2 Chapter frontmatter — v1

```yaml
---
contract_version: 1
kind: chapter
chapter_id: TC-20260715-...-ch02          # charset ^[A-Za-z0-9._-]+$
course_id: TC-20260715-agent-framework-template
order_index: 2
title: "Education gates"
pinned_sha: 3f1c2ab...                     # inherited from the course
sources:                                   # per-file provenance with SHAs (staleness detection)
  - path: scripts/education/gate_registry.py
    source_sha: a1b2c3d...                 # blob/commit SHA of THIS file at generation time
  - path: docs/education/gates.yaml
    source_sha: e4f5a6b...
qa_context:                                # stable prompt-cache-friendly Q&A prefix material
  persona: "tutor"
  one_pager_ref: TC-...#overview
  token_budget: 7000
quiz:
  # No contract_version of its own: the quiz block RIDES the chapter
  # frontmatter's version (see §4) — one fewer moving part.
  questions:
    - item_id: q1
      bloom: understand                    # ∈ BLOOM_LEVELS
      question_type: walkthrough           # ∈ QUESTION_TYPES
      prompt: "Why is clearing a gate idempotent?"
      rubric: "Mentions re-run safety / cleared_by preserved / no duplicate rows."
      variants:                            # served after a miss (offline-safe)
        - item_id: q1v1
          prompt: "What happens if the same transcript is ingested twice?"
          rubric: "No duplicate events or education rows; exit 0."
    - item_id: q2
      bloom: analyze
      question_type: debug-scenario
      prompt: "A gate never clears despite a passing quiz. Where do you look?"
      rubric: "Non-atomic window between DB commit and registry save; recover via CLI."
      variants: []
  explain_back:
    prompt: "Explain the ingest write-sequence in your own words."
    rubric: "validate → discussion → events → education rows → registry flip; all-or-nothing."
    bloom: evaluate                        # fixed
    question_type: explain-back            # fixed
---

<chapter markdown, spoken register; H2 headers = section checkpoints / duck points>
```

Notes:

- `sources[].source_sha` enables selective regeneration: when the repo moves and a
  file's SHA changes, the chapter is marked `stale` and can be regenerated without
  rebuilding the whole course.
- The `quiz` block is fully self-contained (questions + variants + rubrics) so a
  device with no connectivity can pose questions and serve variants; grading and
  gate-clearing still require connectivity (D13).
- Bloom mix targets follow `review_gates.md` (60–70% Understand/Apply, 30–40%
  Analyze/Evaluate; ≥1 debug-scenario and ≥1 change-impact for gate courses).

---

## 3. Knowledge-note — v1

Notes the tutor emits during Q&A and chapter generation. They feed the personal
wiki (share-sheet export) and, for owned repos, ride the Phase-2 evidence PR as
`memory/` **candidates** — human-promoted per Principle #7, never auto-promoted.

```yaml
---
contract_version: 1
kind: knowledge_note
note_id: KN-20260715-...                    # charset ^[A-Za-z0-9._-]+$
classification: innovation                  # enum: "innovation" | "routine"
taxonomy_tags: [capture-pipeline, idempotency]  # vocabulary from memory/projects/TAXONOMY.md
provenance:
  course_id: TC-20260715-agent-framework-template
  chapter_id: TC-...-ch02                    # nullable (course-level notes)
  source_paths: [scripts/education/ingest_walkthrough_session.py]
created_at: 2026-07-15T14:20:00+00:00
---

<note content markdown>
```

- `classification` distinguishes a genuinely novel pattern (`innovation`) from a
  standard, well-understood approach (`routine`) — only innovations are strong
  promotion candidates.
- `taxonomy_tags` draw from the controlled vocabulary in
  `memory/projects/TAXONOMY.md`.

---

## 4. Versioning policy

- **Additive change** (new optional key, new enum member handled tolerantly) →
  **minor note in this document, no version bump.** Producers may emit it;
  tolerant readers ignore what they do not know. The strict repo validator must be
  updated in the same change to *accept* the new key (adding it to the allowed-key
  set), otherwise it is effectively a breaking change for the repo boundary.
- **Breaking change** (rename/remove a key, change a type, tighten an enum, or
  change the meaning of an existing field *in a way producers or payloads must
  follow*) → **bump the affected format's `contract_version`.** The ingest pins
  `contract_version == 1`; a v2 transcript is rejected by a v1 ingest until the
  ingest is taught v2. This is the deliberate app/repo compatibility gate.
- **Semantic revision, wire-compatible** (the boundary's *meaning* changes while
  the payload schema stays byte-identical and no producer changes — e.g. the
  rev 1.1 shift of §1.4 from clearing to clear-eligibility, ADR-0035) → **the
  DOCUMENT version moves** (minor: v1 → v1.1) with a dated changelog entry and
  the section restated in place; **the wire `contract_version` int does NOT
  move**, so existing producers keep working unchanged; consumers are notified
  at their next framework update. Use this tier only when nothing on the wire
  and nothing in any producer must change; anything touching the payload shape
  or producer behavior falls under the two rules above. **And the tier is not
  notification-free:** when a semantic revision moves a consumer-visible value
  vocabulary (an outcome/status string a watcher or log parser matches on — as
  rev 1.1 moved `outcome=cleared` to `outcome=clear-eligible`), the
  notification obligation must be discharged to a **named carrier** (for this
  framework: the sibling-notification board
  `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`), not merely recorded as
  owed in this document. (Defined 2026-08-11 —
  before this tier existed, this policy and the rev 1.1 changelog entry
  contradicted each other: the clearing-rule change demanded a wire bump the
  change itself made unnecessary.)
- Each format versions **independently** (a transcript v2 does not force a
  frontmatter bump).
- The chapter's embedded **quiz block does NOT version independently** — it rides
  the chapter frontmatter's `contract_version`. A breaking change to the quiz
  shape bumps the chapter frontmatter version.

### Single-writer assumption on `gates.yaml`

`docs/education/gates.yaml` has exactly **one writer**: the ingest/watcher path
(`ingest_walkthrough_session.py`, via the `gate_registry.py` atomic
`save_registry`). Humans use the `gate_registry.py` CLI, but not concurrently with
a watcher run. Since rev 1.1 the routine `cleared` flip is a human CLI action,
and the watcher's automatic writes are the re-defer flip and the additive
`clear_eligible` marker. **Known limit (named, not solved):** this puts a human
paste and a watcher batch on the same file as a matter of routine, and two
load-modify-save writers can silently drop each other's update — atomic replace
prevents *torn* files, not *lost* updates. Whether that race occurs in practice
depends on the developer pasting while a watcher batch is mid-run, which the
current single-watcher, human-at-desk topology makes unlikely but not
impossible. The lockfile decision below is explicitly re-affirmed as
**DEFERRED**, not settled: revisit with an advisory lockfile or a
compare-and-swap revision field if a paste-during-batch collision is ever
observed, or if a second watcher appears. Under this single-watcher topology there is no concurrent writer, so
a lockfile is unnecessary.

A concurrent-writer lockfile was **evaluated at checkpoint and deferred** (Principle
#8, least-complex intervention): `save_registry` is already atomic (temp file +
`os.replace`), so a reader never sees a half-written file, and the watcher processes
gate sessions strictly sequentially (one item per poll cycle). If the topology ever
grows a second concurrent writer, revisit with an advisory lockfile or a
compare-and-swap on a registry revision field.
