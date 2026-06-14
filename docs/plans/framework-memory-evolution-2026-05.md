# Framework Memory Evolution Plan — 2026-05

> Purpose: Evolve the framework's memory infrastructure to reliably support reasoning and efficiency, so Howie (and future ambitious projects) can be built on top without fighting the foundation.
>
> Authoring date: 2026-05-14.
> Status: Draft for developer approval.
> Derived from: framework_self_diagnostic_2026-05-13.md, three prior project diagnostics, Phase 1–4 substrate research (`docs/research/`), and the architecture framing settled in the architecture framing memory.

## Vision throughline

Memory that actively supports reasoning and efficiency, organized around these load-bearing commitments:

- **Sources are canonical, vehicles serve sources.** Graphs, summaries, and indexes are projections; the source (with original framing) is always recoverable.
- **Suchness is preserved.** Texture survives the round-trip — emphasis, list structure, framing language — not just the bare proposition.
- **Paraphrase-resilient retrieval.** Semantic search surfaces prior reasoning even when wording differs.
- **Source-resurfacing is first-class.** Reading back a fact returns you to the exact source span.
- **Temporally addressable.** Time-windowed queries are first-class, not greps.
- **Cross-AI continuity (future).** A user-owned substrate that bridges Insight Journal, Claude Desktop, and Claude Code without stranding context. Built after Howie validates the per-project shape.
- **Efficient.** Agents stop re-deriving. Token cost trends down because prior reasoning is surfaced, not redone.

## Sequencing principle

Fix broken → cure in vivo → design before build → build before use → use before federate.

Each phase has a measurable outcome and a decision gate. Hard caps on design phases prevent the "more research" trap.

## Time envelope

- Prologue: < 1 day
- Phase 0: 1–2 days
- Phase 1: 3–5 days
- Phase 2: 1 week (hard cap)
- Phase 3: 2–3 weeks
- Phase 4: 3–5 days
- Phase 5: open-ended (multi-week Howie research)
- Phase 6: ongoing, parallel to Phase 5

Total framework work before Howie begins: **~5–7 weeks** of focused effort.

---

## Prologue — Clear the pending pipeline (today)

**What:** Push the two queued commits on `feature/sourced-assertion-substrate` and triage outstanding loose ends.

**Why:** Every subsequent phase assumes substrate is in `main`. The work is already reviewed and approved; failing to merge it makes Phase 1 impossible.

**Steps:**

1. Push commit `00ca129` (Phase 4 substrate end-to-end) → open PR to main → merge after CI passes.
2. Push commit 2 (v3.4.0 backports + CLAUDE.md sync fixes from REV-20260513-051947) → PR → merge.
3. Update BUILD_STATUS.md with "Prologue complete; entering Phase 0."
4. Triage untracked files (`/conversation` command, `/status` command, `discussions/2026-04-07/`, copilot guide, efficiency report, git visualize) — each gets either a commit, a stash with a named branch, or a deletion with explicit rationale logged in BUILD_STATUS.md.

**Acceptance:**

- `git status` clean on main.
- `assertion_store/` and `mcp_server/` present on main (not just on the feature branch).
- BUILD_STATUS.md reflects current state.

---

## Phase 0 — Fix the promotion pipeline (1–2 days)

**What:** Repair the API drift between `close_discussion.py` and the downstream pipeline scripts. Run one promotion end-to-end so Layer 3 has at least one earned artifact.

**Why:** The framework's central narrative claim — *reasoning becomes durable memory* — is broken at this seam. [close_discussion.py:95](scripts/close_discussion.py) calls `surface_candidates(discussion_id=...)` but [surface_candidates.py:20](scripts/surface_candidates.py) signature is `surface_candidates(threshold=3)`. Same shape for `compute_effectiveness` at line 101. Both raise `TypeError`, are caught and logged as warnings, and silently swallowed. This is the highest-ROI fix in the entire framework.

**Steps:**

1. `/plan` a small spec: fix the two signature mismatches. **Recommended approach:** extend `surface_candidates.py` to accept an optional `discussion_id` parameter that, if present, filters surfacing to only patterns touching that discussion. Preserves both call sites.
2. `/build_module`:
   - Edit `surface_candidates.py` signature + filter logic.
   - Edit `compute_agent_effectiveness.py` similarly (verify the function name vs. import name — `compute_effectiveness` vs. `compute_agent_effectiveness`).
   - Add a regression test in `tests/` that runs `close_discussion.py` against a fixture discussion and asserts `promotion_candidates` row appears.
   - Tag the test `@pytest.mark.regression` and add an entry to `memory/bugs/regression-ledger.md`.
3. Run `python scripts/quality_gate.py` — verify 7/7 pass.
4. `/review` (low risk: qa-specialist + architecture-consultant).
5. Manual end-to-end: find one existing pattern with `sighting_count >= 3` in the parent DB, run `/promote`, verify a file lands in `memory/patterns/`.
6. Commit + push.

**Acceptance:**

- `sqlite3 metrics/evaluation.db "SELECT COUNT(*) FROM promotion_candidates"` returns > 0.
- `ls memory/patterns/` returns at least one `.md` file (not just `.gitkeep`).
- Regression test passes; ledger entry written.

**Decision gate:** if a pattern flows discussion → sighting → candidate → memory/ successfully, proceed to Phase 1. If not, debug rather than advance.

---

## Phase 1 — Cure the substrate in one workflow (3–5 days)

**What:** Wire the substrate (assertion_store + MCP transport) into one existing workflow so it has a real consumer.

**Why:** Today the substrate is theoretically validated but has no in-framework user. Memory primitives only prove themselves through consumption. One consumer is enough to know if the design is right — and exposes any rough edges before they multiply.

**Recommended consumer:** facilitator synthesis at `/review` close. Each `/review` produces 5–15 findings; the facilitator currently writes a synthesis turn. Modify that step to also call `assert_fact` for each *blocking* finding, producing sourced assertions tied to the review report. (Blocking only — keeps signal-to-noise high.)

**Steps:**

1. `/plan` the facilitator synthesis enhancement. Inputs: review findings. Outputs: N sourced assertions written to substrate with `source_ref` pointing to the review report file + line range.
2. `/build_module`:
   - Modify [.claude/agents/facilitator.md](.claude/agents/facilitator.md) to include the assert_fact step in the synthesis instructions.
   - Add an MCP tool invocation pattern in the synthesis prompt template.
   - Write integration test: run a mock review, verify N assertions land in substrate, semantic search retrieves them.
3. `/review` (medium risk — touches agent definitions and substrate transport).
4. Run a real `/review` (e.g., reviewing this plan) and confirm assertions appear.

**Acceptance:**

- One `/review` cycle produces sourced assertions visible via `search_semantic`.
- Semantic query on a paraphrased finding returns the original at distance < 1.5.
- `get_source` returns the review report's exact line range verbatim.

**Decision gate:** if substrate is consumed and producing retrievable value, proceed to Phase 2.

---

## Phase 2 — Design the Howie primitives (1 week, hard cap)

**What:** Commit to designs for four primitives without writing implementation code yet.

**Why:** These primitives have requirements (from the diagnostic and prior surveys) but no schemas. Continuing into build without committed designs would mean inventing under time pressure — the exact "hacked together" feeling we want to avoid.

**The four ADRs (numbers tentative; assign next available):**

### ADR-0015 — Type-routed ingest hook

- Where in the capture path does content type get inspected? (Recommendation: a single dispatch point in or before `extract_findings.py`.)
- What types are first-class? (Initial set: prose, source code, structured records, image-with-metadata, citation.)
- How does each type route — same findings table with type tag, or separate tables?
- Outcome: a single hook point with type dispatchers, schema decision documented.

### ADR-0016 — Time-windowed retrieval primitive

- Extend the substrate (and/or `evaluation.db`) to support `WHERE created_at BETWEEN x AND y` queries efficiently.
- Where do indexes live? What's the API surface (CLI? MCP tool? Both)?
- Outcome: a `search_temporal` primitive plus index plan plus example query patterns.

### ADR-0017 — User-facing memory layer

- Distinct from Layer 3 curated memory: a Layer 4 *rendered surface* that exposes facts with provenance to readers who aren't running an agent.
- Schema? Render format (markdown, HTML, both)? Update mechanism (on promotion vs. on demand)?
- Outcome: a rendering primitive built on the substrate's `get_source`, with a worked example.

### ADR-0018 — Project-specialist registration

- How does Howie's archivist / genealogist / Scottish-historian agent become first-class without forking the framework?
- Discovery path (project's `.claude/agents/` alongside template's? convention-based fall-through?).
- Dispatch table extension (how `review.md` and `build_module.md` discover non-template agents).
- Outcome: a registration convention plus a dispatcher change.

**Per-ADR process:**

1. `/plan` the design spec.
2. `/deliberate` with 2–3 specialists (architecture-consultant always; second specialist depends on the ADR).
3. Write the ADR following [docs/templates/adr-template.md](docs/templates/adr-template.md).
4. `/review` the ADR (docs-knowledge + architecture-consultant).
5. Mark accepted; commit.

**Acceptance:** four ADRs in main, status `accepted`, each with explicit `consequences` and `alternatives_considered` sections.

**Decision gate:** if all four feel committed-to (not still-exploring), proceed to Phase 3. If one or more still feels tentative, `/deliberate` again rather than rush to build.

**Time guard:** 1-week hard cap. If a design isn't converging in 5 days, that's a signal the requirements weren't clear enough — fall back to Phase 1 use-data, learn what's missing, redesign.

---

## Phase 3 — Build the Howie primitives (2–3 weeks)

**What:** Implement the four primitives in dependency order.

**Why:** Designs are cheap; implementations expose what's actually doable. The dependency order matters: each primitive enables the next.

**Build order and rough budget:**

1. **Project-specialist registration** (3–4 days). Needed first because subsequent phases assume project-specific agents can register.
2. **Type-routed ingest** (4–5 days). Needed before Howie records get captured.
3. **Time-windowed retrieval** (3–4 days). Needs SQLite + substrate indexes.
4. **User-facing memory layer** (4–5 days). Needs items 1–3 to be useful.

**Per primitive:**

- `/plan` from the ADR.
- `/build_module` with checkpoint reviews per [.claude/rules/build_review_protocol.md](.claude/rules/build_review_protocol.md).
- Tests including end-to-end (quality gate enforces ≥ 80% coverage).
- `/review` (medium risk for each).
- Update BUILD_STATUS.md after each merge.
- Update [docs/FRAMEWORK_SPECIFICATION.md](docs/FRAMEWORK_SPECIFICATION.md) per [.claude/rules/framework_doc_sync.md](.claude/rules/framework_doc_sync.md).

**Acceptance:**

- All four primitives in main with tests + reviews.
- A reference example for each (e.g., a fake "genealogist" agent registered and dispatched; a sample image-with-metadata routed through ingest; a temporal query returning prior reasoning; a rendered user-facing memory page).
- FRAMEWORK_SPECIFICATION.md updated.

**Decision gate:** if all four are merged and producing example behaviors, proceed to Phase 4.

---

## Phase 4 — Compliance instrumentation pass (3–5 days)

**What:** Add lightweight signals for the 13 rules currently uninstrumented.

**Why:** The framework claims principles it can't currently verify. Even basic signals (was `/plan` invoked before `/build_module`? was `pre_build_search.md` grep performed?) turn aspirational rules into measurable ones — and turn Principle #1 ("reasoning is the primary artifact") into a *demonstrably* maintained claim.

**Scope:** low-fidelity is fine. We're not building a compliance dashboard; we're adding event tags so existing capture catches when rules fire (or don't).

**Steps:**

1. `/plan`: identify which rules can be cheaply instrumented. Workflow rules (autonomous_workflow, commit_protocol, build_review_protocol) get tag emission at command invocation. Pre-tool rules (pre_build_search, micro_fix_protocol) get hook-based signals.
2. `/build_module`: add tag-emission to commands; extend the capture pipeline to surface tag presence/absence.
3. Update [.claude/commands/knowledge-health.md](.claude/commands/knowledge-health.md) to report rule-fire rates.
4. `/review` (low–medium risk).

**Acceptance:** at least 8 of 14 rules emit a measurable signal; `/knowledge-health` shows fire rates.

---

## Phase 5 — Begin Howie (open-ended)

**What:** Spawn Howie from the upgraded template and start the first multi-week research arc.

**Why:** This is the framework's first real stress test under conditions it was designed for. Until Howie runs, the value of the prior phases is plausible, not proven.

**Steps:**

1. `/spawn-project` (or `/onboard` if you prefer manual scaffolding).
2. Register Howie's domain specialists per the Phase 3 Item 1 mechanism.
3. Begin first research arc — suggested scope: pick one ancestor line; gather sources; capture reasoning across multiple sessions over 2–3 weeks.
4. Run `/retro` every 1–2 weeks to capture framework friction.

**Acceptance:**

- Howie produces sourced assertions.
- Type-routed ingest handles at least 3 source types (prose, records, photos).
- Time-windowed retrieval surfaces prior reasoning after > 1-week gap.
- User-facing memory renders at least one consumable artifact.

**Decision gate:** when `/retro` consistently produces backflow candidates, Phase 6 starts naturally.

---

## Phase 6 — Backflow (ongoing, parallel to Phase 5)

**What:** Promote primitives and patterns earned through Howie back into the public template per PHILOSOPHY.md's promotion standard.

**Why:** The framework's lineage architecture (ADR-0002) exists for this. Each primitive proven in Howie is a candidate.

**How:** existing `/promote` flow (now working since Phase 0) → `/lineage` tracking → eventual upstream PR to `Diviner-Dojo/agent_framework_template`.

**Acceptance:** at least one Howie-derived primitive lifts to public template within 6–8 weeks of Phase 5 start.

---

## Risks and mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| Scope drift in Phase 2 | High | 1-week hard cap; fall back to learn-by-use if not converging |
| Substrate proves wrong shape under Phase 5 load | Medium | Architecture allows SQLite extension or migration; this is a known fork point |
| Howie research reveals missing primitive | Medium | Add via `/plan` → ADR → build, same path as Phase 2/3 |
| Hyperfocus pull | High (per ADHD profile) | Each phase has a hard cap; finish current phase before starting next |
| Pre-Howie work consumes more than 7 weeks | Medium | Decision gates at every phase boundary; ruthless prioritization |
| Phase 4 instrumentation feels like busywork | Medium | Keep low-fidelity; one signal per rule is enough |

---

## Memory vision throughline

| Phase | Memory facet advanced |
|---|---|
| Prologue | Substrate enters main — memory infrastructure is in the trunk, not on a branch |
| Phase 0 | Memory accumulates at all (promotion pipeline restored end-to-end) |
| Phase 1 | New memory primitives (sourced assertion, semantic search, source-resurfacing) exercised in vivo |
| Phase 2 | Memory primitives for heterogeneity, time, user-facing get committed designs |
| Phase 3 | Memory surface area expands; suchness preservation extends to records & photos |
| Phase 4 | Memory completeness becomes measurable |
| Phase 5 | Memory under real long-horizon load (Howie research arcs) |
| Phase 6 | Memory primitives flow into public template; cross-AI substrate work begins after Howie validates per-project shape |

---

## First concrete action

Clear the Prologue today: push the queued commits, update BUILD_STATUS.md, triage the untracked files. Then start Phase 0 tomorrow.
