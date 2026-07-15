---
id: EDUCATION-CONTRACTS
title: RepoCademy integration contracts (transcript v1, chapter format, knowledge notes)
status: active
created: 2026-07-15
related_adr: ADR-0029
related_spec: SPEC-20260715-062207
---

# RepoCademy Integration Contracts

The contract — not any client — is the integration point. Anything that emits a
valid **session-transcript JSON v1** can formally clear an education gate
through `scripts/education/ingest_walkthrough_session.py`: the RepoCademy
Flutter module (insight_journal), a future laptop CLI voice loop, or a plain
chat session transcribed by hand. Ingest treats every transcript as
**untrusted input**: full validation before any write, enum whitelists,
score range checks, idempotency per `session_id`.

## 1. Session-transcript JSON — contract v1

```json
{
  "contract_version": 1,
  "session_id": "VWALK-20260715-063000",
  "client": "phone",
  "mode": "gate",
  "gate_id": "GATE-0003",
  "repo": "Diviner-Dojo/agent_framework_template",
  "course_id": "CURR-20260715-framework-full",
  "chapter": {"number": 6, "slug": "education-system", "title": "The education system"},
  "started_at": "2026-07-15T06:30:00Z",
  "ended_at": "2026-07-15T06:58:00Z",
  "narration_completed": true,
  "quiz_summary": {"pass_threshold": 0.70, "average": 0.83},
  "events": [
    {"type": "narration", "section": "01-overview", "text": "…full narration text…"},
    {"type": "question", "text": "Why doesn't /walkthrough write an education row today?"},
    {"type": "answer", "text": "Only /quiz records rows; the walkthrough captures events…"},
    {"type": "parked_question", "text": "Show me the actual CHECK constraint SQL."},
    {"type": "quiz_question", "qid": "q1", "bloom_level": "understand",
     "question_type": "recall", "text": "Where do quiz results land?"},
    {"type": "quiz_answer", "qid": "q1", "text": "The education_results table."},
    {"type": "quiz_grade", "qid": "q1", "score": 1.0, "feedback": "Exactly right."},
    {"type": "explain_back_prompt", "text": "In your own words: why does a human stay in the loop?"},
    {"type": "explain_back_answer", "text": "Because promotion without human assent is extraction…"},
    {"type": "explain_back_grade", "score": 0.9, "feedback": "Pass — you named the principle."},
    {"type": "deferral", "text": "Quiz saved for the next walk — low energy today."}
  ]
}
```

### Field rules (enforced by ingest — rejection lists every defect)

| Field | Rule |
|---|---|
| `contract_version` | Must equal `1`. Breaking changes bump this. |
| `session_id` | `VWALK-YYYYMMDD-HHMMSS`. Idempotency key: a session already present in `education_results` re-ingests as a no-op. |
| `client` | `phone` \| `tablet` \| `laptop` \| `chat` |
| `mode` | `learn` (never touches gates.yaml) \| `gate` (requires valid `gate_id`) |
| `narration_completed` | Must be `true` — only completed sessions are ingested. |
| `events[].type` | One of the 11 types above. Unknown types reject the transcript. |
| `bloom_level` | `remember\|understand\|apply\|analyze\|evaluate\|create` (matches the `education_results` CHECK constraint) |
| `question_type` | `recall\|walkthrough\|debug-scenario\|change-impact\|explain-back` (ditto) |
| `score` | Number in `[0, 1]`. |
| `text` | Non-empty string, ≤ 50,000 chars. Max 2,000 events per transcript. |
| `quiz_answer`/`quiz_grade` `qid` | Must reference a prior `quiz_question` qid (unique per transcript). |

### Event → capture mapping (what ingest writes)

| Transcript event | Layer-1 event (agent/intent/tags) | education_results row |
|---|---|---|
| narration | educator/proposal/`walkthrough,education,voice,course:<id>,chapter-NN` | — |
| (narration_completed) | — | understand / walkthrough / 1.0 / true (once per session) |
| question | developer/question/`voice-qa,…` | — |
| answer | educator/evidence (reply_to question)/`voice-qa,…` | — |
| parked_question | developer/question/`voice-qa,parked,…` (also echoed by the CLI for desk follow-up) | — |
| quiz_question | educator/question/`quiz,q:<qid>,bloom:<level>,…` | — |
| quiz_answer | developer/evidence/`quiz-answer,q:<qid>,…` | — |
| quiz_grade | educator/critique/`quiz-grade,q:<qid>,…` | question's bloom / question's type / score / score ≥ threshold |
| explain_back_* trio | educator/question → developer/evidence → educator/critique/`explain-back,…` | evaluate / explain-back / score / score ≥ threshold |
| deferral | facilitator/decision/`education-deferred,…` | — (gates.yaml re-deferral entry in gate mode) |
| (closing) | facilitator/synthesis/`education,results,…` | — |

### Gate-cleared rule (R5)

`narration_completed` AND quiz average ≥ `pass_threshold` (default **0.70**,
client-supplied values clamped to **[0.5, 1]** — the bar is not
client-nullable) AND every explain-back grade ≥ threshold AND no deferral
event. `quiz_summary.average`, when present, is cross-checked against the
recomputed grade average (±0.01) and rejected on mismatch. Cleared gates get
`cleared_by=<session_id>`, `cleared_at`, `discussion_id` in
`docs/education/gates.yaml`; failed attempts are recorded on the gate's
`attempts` list and the gate stays `open`.

**Trust model (load-bearing):** grades inside a transcript are
**client-asserted** — the client's LLM graded the developer's spoken answers.
Ingest therefore performs *registration*, not *certification*: the
certification step is the human developer reviewing and merging the evidence
PR carrying the transcript (or knowingly running ingest locally). Principle #6
enforcement stays human-mediated; the registry flip is evidence-backed and
auditable via the sealed discussion, never self-certifying. All free text is
additionally stripped of control characters and ANSI escape sequences before
any write (terminal-injection guard), and total transcript text is capped at
2,000,000 chars.

## 2. Course / chapter format (what clients generate and play)

`chapter-NN-<slug>.md` — YAML frontmatter + fully **speakable** body
(H2 sections = TTS chunks and pause/resume checkpoints; identifiers spoken out,
no code dumps):

```yaml
---
course_id: CURR-20260715-framework-full
chapter: 6
slug: education-system
title: The education system
est_minutes: 22
source_sha: e4c8d73          # repo commit the chapter was generated from
sources:                     # drives staleness detection (git diff vs source_sha)
  - scripts/record_education.py
  - .claude/commands/quiz.md
qa_context: >-               # chapter-specific pointers injected into Q&A calls
  education_results schema lives in scripts/init_db.py; deferrals in gates.yaml.
quiz:
  pass_threshold: 0.70
  questions:
    - qid: q1
      bloom_level: understand
      question_type: recall
      question: Where do quiz results land?
      expected_answer: The education_results table in metrics/evaluation.db.
      rubric: Names the table; bonus for naming the CHECK-constrained columns.
  explain_back:
    prompt: In your own words, why does a human stay in the promotion loop?
    bloom_level: evaluate
    rubric: Articulates Principle #7 / the Prime Objective's human-mediated enforcement.
callouts:
  innovations:
    - "Four-layer capture stack: reasoning as the primary artifact"
  routine_patterns:
    - "argparse CLI + library-function split in scripts/"
---

## Section one — why this exists
Speakable prose only…
```

Course-level `course.yaml`: `course_id`, `repo`, `source_sha`, mode
(`learn|gate`), Level-0 overview pointer, ordered chapter list, per-chapter
generation state. Chapter files are immutable per generation; regeneration
creates a new `content_hash`.

## 3. Knowledge-note format (wiki + memory/ feed)

One markdown file per insight, taxonomy-aligned with
`memory/projects/` technology-grid profiles so filing is mechanical:

```yaml
---
repo: karpathy/nanoGPT
concept: single-file model definition
classification: innovation        # innovation | routine
taxonomy_tags: [architecture.simplicity, pedagogy.transparency]
evidence: [model.py]
course_id: CURR-20260716-nanogpt
captured_at: 2026-07-16
---
One-paragraph explanation in the developer's own learning context…
```

Owned-repo notes ride the evidence PR as `memory/projects/` **candidates**
(human promotes per Principle #7); external-repo notes export as a wiki bundle.

## Versioning

Additive changes (new optional fields) keep `contract_version: 1`. Breaking
changes bump the version; ingest rejects versions it does not implement.
