# Framework Self-Diagnostic — 2026-05-13

> Subject: AI-Native Agentic Development Framework v3.4 (Diviner-Dojo template, observed via the DanEvans-collab private exploratory fork).
> Worktree: `claude/reverent-lovelace-84e718`. Where worktree state diverges from the parent working tree (notably BUILD_STATUS and substrate Phase 4), the diagnostic uses the parent state and says so.

---

## PART ONE — Framework Identity & Intent

### F1 — Canonical Identity

1. **Repo identity.** This worktree is on branch `claude/reverent-lovelace-84e718`. `git remote -v` shows `origin` pointing at `DanEvans-collab/AGENT_FRAMEWORK_TEMPLATE_EXPLORATORY` and `upstream` at `Diviner-Dojo/agent_framework_template`. The canonical public template is the upstream; this is its **private exploratory fork**. [framework-lineage.yaml:1-27](framework-lineage.yaml) records `instance.type: derived`, `version: 1.0.0+upstream.2.1.0`, `lineage_id: c63b59a2…`. [PHILOSOPHY.md:11-15](PHILOSOPHY.md) names the relationship explicitly: *"We do not own the public repo. We are its first follower and gatekeeper."* Latest tagged release path in [BUILD_STATUS.md (parent)](../../../BUILD_STATUS.md) is **v3.4.0** with Phase 4 (substrate) on the unmerged branch `feature/sourced-assertion-substrate`.

2. **Intent documents.**
   - [PHILOSOPHY.md](PHILOSOPHY.md) (90 lines) — *why* the framework exists: "help people actuate their creativity."
   - [docs/FRAMEWORK_SPECIFICATION.md](docs/FRAMEWORK_SPECIFICATION.md) v3.4 — authoritative specification (per [.claude/rules/framework_doc_sync.md:17-21](.claude/rules/framework_doc_sync.md)).
   - [CLAUDE.md](CLAUDE.md) — operational constitution (eight non-negotiable principles, agent roster, capture pipeline contract).
   - [docs/STEWARD_ARCHITECTURE.md](docs/STEWARD_ARCHITECTURE.md) — bidirectional propagation roadmap (4 pillars, 5 phases).
   - [docs/adr/ADR-0001-adopt-agentic-framework.md](docs/adr/ADR-0001-adopt-agentic-framework.md) and [ADR-0005-v3-framework-evolution.md](docs/adr/ADR-0005-v3-framework-evolution.md) carry the framework-architecture decisions.

3. **Top-level commitments** (extracted verbatim from [CLAUDE.md:12-21](CLAUDE.md) and [PHILOSOPHY.md](PHILOSOPHY.md)):

   | # | Commitment | Verifiable from code? |
   |---|---|---|
   | 1 | Reasoning is the primary artifact | **Partial.** Discussion capture is implemented; promotion to durable memory is broken (see F4). |
   | 2 | Capture is automatic / model can't opt out | **Yes**, via [scripts/create_discussion.py](scripts/create_discussion.py) + [write_event.py](scripts/write_event.py) called by commands; **No** hook enforces it. |
   | 3 | Collaboration precedes adversarial rigor | **Narrative.** No code enforces collaboration mode selection. |
   | 4 | Independence prevents confirmation loops | **Partial.** [.claude/rules/build_review_protocol.md](.claude/rules/build_review_protocol.md) and [review_gates.md](.claude/rules/review_gates.md) prescribe; no instrumentation verifies. |
   | 5 | ADRs are never deleted, only superseded | **Yes**, observable: 12 ADRs in [docs/adr/](docs/adr/), ADR-0007 marked superseded by ADR-0009. |
   | 6 | Education gates before merge | **Partial.** [scripts/record_education.py](scripts/record_education.py) exists; gate enforcement is manual. |
   | 7 | Layer 3 promotion requires human approval | **Yes**, enforced by [.claude/commands/promote.md](.claude/commands/promote.md) wait-for-approval clause. |
   | 8 | Least-complex intervention first | **Narrative.** No code signal. |

### F2 — What the framework says it does vs. does

4. **Specialist roster (12 agents in [.claude/agents/](.claude/agents/)).** steward (opus), facilitator (opus), architecture-consultant (opus), independent-perspective (opus, 4 instance types), docs-knowledge (sonnet), educator (sonnet), history-analyst (sonnet, gated to `/review --deep`), performance-analyst (sonnet), project-analyst (sonnet, can dispatch), qa-specialist (sonnet), security-specialist (sonnet), ux-evaluator (sonnet). All 12 carry the Values + Domain Lens shape that [ADR-0010](docs/adr/ADR-0010-agent-values-domain-lens.md) requires.

5. **Commands (18 in [.claude/commands/](.claude/commands/)).** analyze-project, batch-evaluate, build_module, deliberate, discover-projects, evaluate-repo-security, knowledge-health, lineage, meta-review, onboard, plan, promote, quiz, retro, review, ship, spawn-project, walkthrough.

6. **Rules (14 in [.claude/rules/](.claude/rules/)).** autonomous_workflow, build_review_protocol, coding_standards, commit_protocol, cross_agent_dispatch_protocol, documentation_policy, failure_taxonomy, framework_doc_sync, micro_fix_protocol, multi_instance_protocol, pre_build_search, review_gates, security_baseline, testing_requirements. **Zero are marked SUPERSEDED** (grep for "SUPERSEDED"/"DEPRECATED" returns nothing in `.claude/rules/`).

7. **Hooks & skills.** Hook directory holds 9 executables ([.claude/hooks/](.claude/hooks/)). Wiring lives in [.claude/settings.json:14-80](.claude/settings.json): PreToolUse (validator, commit-gate, push-main-blocker), PostToolUse (auto-format, unlock), PreCompact ([pre-compact.ps1](.claude/hooks/pre-compact.ps1)), SessionStart on `resume|compact` ([session-start.ps1](.claude/hooks/session-start.ps1)). Skills in [.claude/skills/](.claude/skills/) (7): adr-writing, feature-status-registry, performance-playbook, python-project-patterns, security-checklist, testing-playbook. Skills are referenced from agent prompts; no auto-discovery mechanism.

8. **DESIGNED / IMPLEMENTED / INVOKED / EFFECTIVE matrix.**

   | Feature | DESIGNED | IMPLEMENTED | INVOKED | EFFECTIVE |
   |---|---|---|---|---|
   | Capture pipeline (Layer 1→2) | CLAUDE.md; ADR-0001 | [scripts/create_discussion.py](scripts/create_discussion.py), [write_event.py](scripts/write_event.py), [close_discussion.py](scripts/close_discussion.py), [ingest_events.py](scripts/ingest_events.py) | YES — `/review`, `/plan`, `/build_module`, `/deliberate`, `/retro`, `/meta-review`, `/lineage` all call it | **YES** — parent DB shows 33 discussions, 225 turns, 124 findings |
   | Pattern mining | CLAUDE.md | [mine_patterns.py](scripts/mine_patterns.py) | Auto via [close_discussion.py:86](scripts/close_discussion.py) | **YES** — 109 pattern_sightings in parent DB |
   | Promotion surfacing | CLAUDE.md "Layer 3" | [surface_candidates.py](scripts/surface_candidates.py) | Auto via close_discussion.py:95 **but call signature is broken** (see F4 #16) | **NO** — 0 promotion_candidates despite 109 sightings |
   | Layer 3 curated memory | CLAUDE.md, ADR-0011 | Folders exist; [memory/patterns/](memory/patterns/), [reflections/](memory/reflections/), [rules/](memory/rules/) | Writer is `/promote` (manual) | **NOT-EVIDENT** — all three folders empty (`.gitkeep` only) |
   | Substrate (assertion_store) | ADR-0014 + framing memory | On branch `feature/sourced-assertion-substrate` (Phase 4 validated 2026-05-12); NOT on this branch | NOT-INVOKED in main | NOT-EFFECTIVE yet |
   | Propagation (vouchers) | [ADR-0002:44](docs/adr/ADR-0002-adopt-steward-agent.md) Phase 1 only; Phases 2-5 deferred | [scripts/lineage/](scripts/lineage/) implements manifest + drift only | `/lineage` command exists | NOT-EVIDENT — no voucher records, `.claude/custodian/lineage-events.jsonl` has 3 events ever |
   | Token telemetry | ADR-0013 (status: proposed at last sight) | [scripts/ingest_token_usage.py](scripts/ingest_token_usage.py) implemented; turns.tokens_* columns added | Implemented at parent, awaiting merge | NOT-EFFECTIVE in main branch state |
   | Compliance instrumentation | autonomous_workflow.md, pre_build_search.md, micro_fix_protocol.md | NOT-IMPLEMENTED for those rules | NOT-INVOKED | NOT-EFFECTIVE |
   | Quality gate | CLAUDE.md, ADR-0004 | [scripts/quality_gate.py](scripts/quality_gate.py); pre-commit hook | YES — 64 runs in [metrics/quality_gate_log.jsonl](metrics/quality_gate_log.jsonl) | **YES** — last run 2026-05-13 pass on 7 checks |
   | Hooks (lifecycle) | CLAUDE.md "Hooks" section | All 9 implemented | Auto via settings.json | **YES** — secret detection, format, lock release, session-start health dashboard |

---

## PART TWO — Core Architectural Approaches

### F3 — Capture Pipeline

9. **End-to-end trace.** Agent turn → command emits Bash call to [write_event.py:41-98](scripts/write_event.py) → appends JSON line to `discussions/<date>/<id>/events.jsonl`, computes turn_id by line count, validates intent enum. At command close: `/review` Step 8 calls [close_discussion.py:34-159](scripts/close_discussion.py) which orchestrates: generate_transcript → ingest_events (`INSERT OR IGNORE` into `turns`) → mark discussion closed → extract_findings → mine_patterns → surface_candidates → compute_effectiveness → set files read-only → notify.

10. **Schema** (from [scripts/init_db.py](scripts/init_db.py)): tables `discussions`, `turns`, `protocol_yield`, `decisions`, `reflections`, `education_results`, `findings`, `promotion_candidates`, `pattern_sightings`, `agent_effectiveness`, `lineage_nodes`, `lineage_file_drift`. Indexes on `turns.discussion_id`, `findings.discussion_id`, `pattern_sightings.pattern_hash`, `promotion_candidates.category`. Views `v_rule_of_three`, `v_agent_dashboard`, `v_token_efficiency`. No Alembic; init is idempotent (`CREATE … IF NOT EXISTS`).

11. **Guarantees.** Reading [close_discussion.py:73-106](scripts/close_discussion.py) directly: each downstream step is wrapped in `try / except Exception as e: print("Warning: … (non-fatal)")`. Idempotency for re-closure is partial: `ingest_events` is idempotent (UNIQUE on `(discussion_id, turn_id)` + `INSERT OR IGNORE`); `record_yield` is idempotent ([record_yield.py:50-61](scripts/record_yield.py)). [extract_findings.py](scripts/extract_findings.py) and [mine_patterns.py](scripts/mine_patterns.py) lack dedup guards — a second closure would re-insert findings rows. Back-pressure: NONE; no queueing.

12. **Silent failure modes.** Three concrete ones:
    a. **Surface_candidates API drift** ([close_discussion.py:95](scripts/close_discussion.py) calls `surface_candidates(discussion_id=discussion_id)`; [surface_candidates.py:20](scripts/surface_candidates.py) signature is `def surface_candidates(threshold: int = 3)`). Every closure raises `TypeError`, caught at line 96, printed as a warning, swallowed.
    b. **Compute_effectiveness drift** ([close_discussion.py:101](scripts/close_discussion.py) imports `compute_effectiveness` from [compute_agent_effectiveness.py](scripts/compute_agent_effectiveness.py)) — flagged in [parent BUILD_STATUS.md](../../../BUILD_STATUS.md): *"Pipeline scripts: surface_candidates() and compute_effectiveness() have API drift (still open — deferred R5.4)"*. This is a **known, deferred bug from the v3.4 build**, and it is the most plausible explanation for the Verification Portal's 82-sightings/0-candidates incident.
    c. **Notification swallow** ([close_discussion.py:144](scripts/close_discussion.py) `except Exception: pass`).

13. **Schema/tag drift handling.** [write_event.py](scripts/write_event.py) validates intent enum but accepts arbitrary `tags`. [extract_findings.py:91-161](scripts/extract_findings.py) classifies severity/category by regex keyword match on the *content excerpt*. If an agent omits expected category markers, the finding is still ingested but may land in the wrong category bucket. No schema-conformance reporting exists.

### F4 — Promotion Pipeline (Layer 3)

14. **End-to-end path.** Finding (from extract_findings) → cluster by Jaccard similarity (threshold 0.4, [mine_patterns.py:35-135](scripts/mine_patterns.py)) → `pattern_sightings` row → surface_candidates groups by `pattern_hash`, requires `COUNT(DISTINCT discussion_id) >= 3` ([surface_candidates.py:52](scripts/surface_candidates.py)) → `promotion_candidates` row with `promoted = 0` → human runs [.claude/commands/promote.md](.claude/commands/promote.md) → writes a file under `memory/patterns/`, `decisions/`, `reflections/`, or `rules/`.

15. **Thresholds.** Jaccard 0.4 ([mine_patterns.py:23](scripts/mine_patterns.py)); Rule of Three = 3 distinct discussions ([surface_candidates.py:20,52](scripts/surface_candidates.py), default arg).

16. **The 109 / 0 gap.** Parent SQLite shows `pattern_sightings = 109`, `promotion_candidates = 0`. The view `v_rule_of_three` should expose at least one qualifying pattern (the explore agent found `pattern_hash=f44534024422d725` with `sighting_count=3`). The reason it never reached `promotion_candidates` is the API drift in #12a: close_discussion.py's call signature does not match surface_candidates.py's parameter list, so the call raises and the exception is swallowed. **This is the single most damaging bug in the framework right now.**

17. **Automatic invocation evidence.** [close_discussion.py:91-97](scripts/close_discussion.py) does call surface_candidates on every closure (auto). [.claude/commands/knowledge-health.md:31](.claude/commands/knowledge-health.md) invokes it manually. No hook or cron invokes it standalone.

18. **User experience.** Today, a developer would run `/knowledge-health` → see "0 promotion candidates" → see in [adoption-log.md](memory/lessons/adoption-log.md) that 45 entries are PENDING from manual entry → run `/promote` against one of those entries → approve → file lands in `memory/patterns/` (or wherever). The automatic pipeline does not contribute to that walk-through at all.

19. **Has promotion ever produced an artifact automatically?** **NO.** `memory/patterns/`, `memory/reflections/`, and `memory/rules/` contain only `.gitkeep`. [memory/lessons/adoption-log.md](memory/lessons/adoption-log.md) has 45 PENDING / 22 REJECTED / 7 CONFIRMED entries, **all populated by manual `/promote` (or by the `analyze-project` flow into the adoption log)**.

### F5 — Substrate (Assertion Store)

20. **In this worktree:** glob for `assertion_store/**`, `mcp_server/**`, `substrate/**` returns nothing. **Not on this branch.**
21. **In the parent working tree:** [BUILD_STATUS.md (parent)](../../../BUILD_STATUS.md) reports Phase 4 complete on `feature/sourced-assertion-substrate`: `assertion_store/{__init__,substrate,embeddings}.py`, `mcp_server/{__init__,server}.py`, ADR-0014, CLAUDE.md substrate section, 27 tests at 97% coverage, MCP round-trip validated 2026-05-12 (fact_ids 1-3, semantic search distance 1.113, gap-to-runner-up 0.20). Reviews REV-20260512-132622 (request-changes) → fix sequence → REV-20260512-195841 (approve).
22. **Ever invoked by another workflow?** **NO.** No command, hook, or other script references the substrate or MCP server. It exists as a parallel substrate ready for Howie/Layer-3 cross-project use; the rest of the framework does not call it yet.
23. **ADR-0014 promise.** Substrate provides "sourced assertion" primitives (SPO + source_ref + scope + framing); supports `assert_fact`, `search_semantic`, `get_source`; SQLite + sqlite-vec; per-project Layer 2 with a future shared Layer 3+ DB. Round-trip validated, but **no workflow in main consumes it**.
24. **Location.** Built on `feature/sourced-assertion-substrate` (off `feature/project-analysis-backport` HEAD) at the parent path — NOT in any worktree on `claude/*` branches. So: substrate is in code but not in the template-as-shipped until that PR merges.

### F6 — Specialist Roster

25. **Invocation rate.** Parent DB: 225 turns across 33 discussions ≈ 6.8 turns/discussion. Distinct agents that actually filed turns (not measured here; would need a `SELECT agent, COUNT(*) FROM turns GROUP BY agent` to confirm). Steward is "retired founder — activated only for framework evolution" ([.claude/agents/steward.md:4](.claude/agents/steward.md)) so its invocation count is structurally low. history-analyst is gated to `/review --deep` only.
26. **Dispatch logic.** [.claude/rules/review_gates.md:28-47](.claude/rules/review_gates.md) is the canonical dispatch table: risk tier → mandatory agents → domain specialists by change-type. [.claude/commands/review.md](.claude/commands/review.md) Step 5 instructs the facilitator to read the table and dispatch via the Task tool. The logic is **prose + table**, not a state machine.
27. **Shape consistency.** Sampled qa-specialist, security-specialist, ux-evaluator, steward: all have Values + Domain Lens (ADR-0010 compliant). QA and Security additionally carry anti-pattern + bias-safeguard sections; ux-evaluator and steward do not. Output contracts are by convention (YAML verdict + findings) not by schema.
28. **Project-added specialists.** Grep across the repo: only [memory/projects/contractorverification.md](memory/projects/contractorverification.md) mentions state-config-builder, playwright-debugger, plan-reviewer, journal-curator — and only as adopted-pattern notations, not as agent files. No registration mechanism for project-specific specialists exists in the canonical template. Each derived project mints them ad hoc.
29. **Missing-specialist fallback.** None. If a `Task(subagent_type="…")` references an undefined agent, the call fails at the harness layer. No router or fallback chain.

### F7 — Commands & Workflows

30. **18 commands, wiring summary.** All commands are markdown prompts dispatched via the Skill / slash-command harness — none are wired into hooks. Chaining is implicit: `/plan` → `/build_module` → `/review` → `/walkthrough` / `/quiz` → commit is described in narrative form in [.claude/rules/autonomous_workflow.md:6-26](.claude/rules/autonomous_workflow.md). The commands themselves do not enforce the order; the human or the facilitator does.
31. **Chain cleanliness.** No state machine. Each command is independently invocable and assumes the developer knows what phase they are in. There is no `current_phase` artifact (BUILD_STATUS.md substitutes for it informally).
32. **/plan telemetry.** create_discussion.py inserts a row; write_event.py logs each specialist turn; record_yield.py captures protocol outcome; close_discussion.py marks closed. Token telemetry was added in ADR-0013 (parent state) — `discussions.total_tokens_*` columns plus the per-turn columns. Coverage by command type ranges from full (review, plan, build_module, retro) to skeletal (analyze-project context-brief is intentionally omitted).
33. **Idempotency.** `/build_module` rerun on the same spec creates a *new* discussion (with a new timestamp ID). It does not detect duplicate work; the developer must check `discussions/<date>/` for prior runs.

### F8 — Rules System

34. **All 14 rules listed in F2 #6.** Enforcement breakdown — automated for 5 (coding_standards, commit_protocol parts, security_baseline parts, testing_requirements parts, framework_doc_sync via review reminders); manual / facilitator-judged for the other 9.
35. **Loading.** Rules are referenced in CLAUDE.md and injected at session start by virtue of being in the project context window. No conditional loader. Auto-load is via Claude Code's CLAUDE.md preamble (this conversation has them all).
36. **Contradictions/overlaps.** None found. Pairs sampled (commit_protocol/autonomous_workflow, review_gates/build_review_protocol, documentation_policy/framework_doc_sync) are layered (phase-staged) rather than overlapping.
37. **Deprecation lifecycle.** No SUPERSEDED markers in `.claude/rules/`. ADRs use a Supersedes field ([ADR-0009](docs/adr/ADR-0009-steward-review-pipeline-revision.md) supersedes parts of [ADR-0007](docs/adr/ADR-0007-review-pipeline-agents.md)); rules do not.

### F9 — Memory Layers

38. **Layers in use.**

    | Layer | Path | Writer | Reader | Retention |
    |---|---|---|---|---|
    | L0 Auto-memory | `~/.claude/projects/<slug>/memory/MEMORY.md` (19 lines today) | Claude session | Claude session | 200-line truncation warning; **no automated rotation** |
    | L1 Discussions | [discussions/](discussions/) | Capture scripts | Read-only after seal | Read-only flag set; ~28 discussions on disk |
    | L2 SQLite | [metrics/evaluation.db](metrics/evaluation.db) (parent) | Capture scripts + lineage scripts | All commands | Persistent; no archival |
    | L3 Curated memory | [memory/](memory/) | `/promote` (manual) | All agents + humans | Git-tracked |
    | Lineage | [framework-lineage.yaml](framework-lineage.yaml) + `.claude/custodian/lineage-events.jsonl` | lineage scripts | `/lineage` command | YAML mutable; JSONL append-only |
    | Shared memory | `~/.claude/shared-memory/` (12+ files) | Cross-project promote | Any project on this user | Not bound to template (no path constant) |

39. **Conflicts/duplicates.** MEMORY.md (auto-memory) overlaps with [memory/projects/_self.md](memory/projects/_self.md) (Layer 3 self-profile). Precedence is implicit: MEMORY.md is per-session per-user; _self.md is repo-tracked. No precedence rule documents this.
40. **200-line truncation.** MEMORY.md is at 19 lines today; no growth-management hook exists. The policy is **manual pruning by the user or by Claude when the line warning surfaces in a future session** (e.g., the "consolidate-memory" skill in `anthropic-skills:consolidate-memory`, but that is a user-invocable skill not auto-fired).
41. **Cross-project shared memory.** Exists at `~/.claude/shared-memory/` with FRAMEWORK.md, FRAMEWORK_CHANGELOG.md, heritage/, universal-warnings.md. The canonical template *does not encode* this path — [pre-compact.ps1:23-31](.claude/hooks/pre-compact.ps1) invokes a sync script if present; [session-start.ps1:138-158](.claude/hooks/session-start.ps1) reads it if present. Both are graceful-no-op-on-missing.

### F10 — Propagation (Steward / Voucher)

42. **Designed.** [ADR-0002](docs/adr/ADR-0002-adopt-steward-agent.md) defines 5 phases: (1) lineage tracking, (2) version vectors, (3) vouchers, (4) attribution, (5) ecosystem dashboard.
43. **Implementation.** Only Phase 1: [scripts/lineage/manifest.py](scripts/lineage/manifest.py), [scripts/lineage/drift.py](scripts/lineage/drift.py), [scripts/lineage/init_lineage.py](scripts/lineage/init_lineage.py). Manifest validates schema; drift reads `pinned_traits` and tags file-level deltas. No voucher schema, no version vector, no attribution.
44. **Has propagation fired?** `framework-lineage.yaml:14-16` shows `drift.status: current`, `divergence_distance: 0`. `.claude/custodian/lineage-events.jsonl` has 3 events ever — FORK (2026-03-07), FORK derived (2026-03-13), VERSION_TRANSITION 3.0.0→3.1.0 (2026-03-25). **No drift event since 2026-03-25** despite v3.2, v3.3, v3.4 releases and substrate Phase 4 development.
45. **Default state vs. dead system.** The serial=0, pinned_traits=1 (PHILOSOPHY.md only), and missing custodian voucher infrastructure is consistent with **"propagation system designed but never activated past observation."** Not a default state of a recently-forked project — a system that hasn't been driven.
46. **Template-to-instance update mechanism.** `/spawn-project` in [.claude/commands/spawn-project.md](.claude/commands/spawn-project.md) and [scripts/spawn_project.py](scripts/spawn_project.py) copy the template. **There is no documented sync-back or sync-forward mechanism between an existing instance and the template.** ADR-0002's vouchers would be the mechanism; vouchers are not implemented.

### F11 — Telemetry

47. **ADR-0013.** Token-efficiency telemetry. Status was "proposed" at last sight; implementation completed on the parent working tree (Phase 4 work session, BUILD_STATUS shows REV-20260512-033416). Scripts: [ingest_token_usage.py](scripts/ingest_token_usage.py) (parent), `efficiency_report.py` mentioned but not verified.
48. **Metrics actually captured (today, this worktree):** quality_gate runs (64 entries in [metrics/quality_gate_log.jsonl](metrics/quality_gate_log.jsonl)); knowledge-pipeline snapshots ([metrics/knowledge_pipeline_log.jsonl](metrics/knowledge_pipeline_log.jsonl), 1 entry from 2026-03-08, stale); discussion turns/findings/pattern_sightings (SQLite, parent DB); protocol_yield (15 rows in parent).
49. **Token telemetry decision.** Framework-level. ADR-0013 carries it. Forward-looking only: historical discussions remain NULL on the new token columns because content excerpts are truncated and back-fill would be unreliable.
50. **Compliance signal fraction.** 1 of 14 rules has automated compliance signal (commit_protocol via quality_gate). Per-rule: pre_build_search has no logging of search results; autonomous_workflow has no detection of skipped steps; micro_fix_protocol has no instrumentation of micro-fix categorization. **≈7% (1/14) of rules have any compliance signal captured.**

### F12 — Skills & Hooks

51. **Skills (7).** adr-writing, feature-status-registry, performance-playbook, python-project-patterns, security-checklist, testing-playbook. Discovery is via agent prompts (referenced by name). No registry index file.
52. **Hooks (9 wired).** Documented in F2 #7. All implemented; settings.json line 14-80 wiring confirmed.
53. **MEMORY.md growth.** No hook handles it. The 200-line truncation is enforced by the runtime, not by the framework. **Finding:** the framework's auto-memory layer is unmanaged at the framework level.

---

## PART THREE — Adoption & Drift

### F13 — Template-to-Instance Relationship

54. **Copy mechanism.** [scripts/spawn_project.py](scripts/spawn_project.py) (not read in detail here) is the entry point. Files are copied (not symlinked or forked at the git level).
55. **Upstream sync.** Manual: rebase or merge upstream into your fork. Recent commits show `Merge remote-tracking branch 'upstream/main'` (9562ceb) and `Merge pull request #5 from DanEvans-collab/sync/upstream-v3.4.0` (9389500). No automated sync.
56. **divergence_distance: 0.** Conservative-and-incomplete: the manifest reports zero divergence even though significant work has happened on `feature/sourced-assertion-substrate` (substrate, Phase 4) and `feature/project-analysis-backport` (8 project re-analyses). The drift script may be reading only `pinned_traits`-listed paths (PHILOSOPHY.md), missing changes elsewhere. **The drift-detection signal is broken or unused.**
57. **Surveyed-projects divergence.** Prior diagnostics not reachable from this worktree (no `*self_diagnostic*` files found in expected sibling locations). Cannot enumerate per-project divergences from this seat. *Recommendation: pull the Agentic Journal and Verification Portal diagnostics into a shared diagnostics/ index.*

### F14 — Cross-Project Evidence Already Gathered

58. **Prior diagnostic files.** None located by this run. They live (per the prompt) at `/path/to/agentic-journal/diagnostics/*` and `/path/to/verification-portal/diagnostics/*`, neither of which is mountable from this worktree.
59. **Delta.** Without those files in-hand, I cannot precisely diff. The findings *this* diagnostic adds with confidence:
    - The Verification Portal's 82-sightings/0-candidates incident has a **deterministic root cause** in the canonical template: `surface_candidates(discussion_id=...)` API drift, swallowed silently. This is not "the pipeline is mysterious." It is a known, deferred bug in this very repo (BUILD_STATUS, R5.4).
    - The substrate, reported ABSENT in earlier surveys, is now **half-shipped**: built and validated on a feature branch, not merged to main.
    - Compliance instrumentation is structurally absent; the framework relies on rules being followed without measuring whether they are.

---

## PART FOUR — Anticipating Large/Complex Projects

### F15 — Heterogeneity

60. **Document-type assumptions.** None of the 30 Python scripts in [scripts/](scripts/) branches on document type. pipeline_utils.py, mine_patterns.py, extract_findings.py all treat captured text as a single Latin-tokenizable stream. The framework treats all captured content as uniform prose. **A project ingesting genealogical records, photos, or transcribed letters would have to subclass or fork the capture path.**
61. **Where would a type-routed ingest hook live?** Today: nowhere. A clean hook point would be (a) at write_event.py before the JSON line is appended, or (b) at a new "source_ingest" step inside close_discussion.py that runs *before* extract_findings. The framework does not provide this.
62. **Substrate flexibility.** The SPO + source_ref + framing model (ADR-0014) is text-shaped: source_ref is a `project://<id>/<rel>#L<a>-L<b>` URI and framing is a markdown string. A photo with provenance would need a `media://` URI scheme; suchness preservation would mean storing original framing context. The schema is *extensible* but not type-aware out of the box.

### F16 — Scale

63. **Storage growth defaults.** No compression, no archival, no decay. events.jsonl is append-only; SQLite grows monotonically; [scripts/enforce_forgetting_curve.py](scripts/enforce_forgetting_curve.py) exists but is not invoked by any hook or command (grep confirms).
64. **Stress-test data.** No formal stress test in the repo. Parent SQLite: 33 discussions / 225 turns / 124 findings / 109 sightings — modest. Agentic Journal at ~900K tokens + 225 MB jsonl is the closest historical data point and is *outside* this template.
65. **Verification Portal at 749 MB.** The framework offers SQLite (works fine at 1+ GB if vacuumed) but no archival strategy and no query-cost guidance. At that scale, scripts that do `SELECT * FROM turns` for ingestion start to feel it. **No framework primitive helps; each project must invent its own retention pattern.**

### F17 — Long-Horizon Memory

66. **"What did we learn about X three months ago" queries.** No primitive exists. Grep for `WHERE.*created_at`, `BETWEEN`, `DATE(` in scripts/ returns nothing. All retrieval is keyword/tag-based.
67. **Time-windowed retrieval.** None implemented. Even the adoption log is ordered by manual entry, not by SQL date range.
68. **Research-as-deliverable.** No first-class concept. Agentic Journal's "Standing Documents" pattern (referenced in [memory/projects/agentic-journal.md](memory/projects/agentic-journal.md)) is a candidate; it has not been backported. For Howie, where the research itself is the deliverable, **the framework offers no support today** — project-instance custom work would be required.

### F18 — User-Facing Memory

69. **Designed primitive.** None. All current memory is agent-facing. Grep for `user-facing memory` returns only REVIEW.md:39 (input validation rule, not memory).
70. **Primitive(s) the framework should provide.** A "rendered view" layer over Layer 3 — a way to expose curated memory to end-users with provenance and version. This is exactly what the substrate's `get_source` primitive sketches; promoting it to a general framework primitive (not just substrate-internal) would be the right move.

### F19 — Domain Specialization

71. **Designed relationship.** Not specified. The 12 framework agents are general; project-specific agents (state-config-builder, etc.) appear only in derivative projects with no registration mechanism. No ADR addresses this.
72. **Pattern for project specialists.** No framework primitive. Each project mints them in its own `.claude/agents/` and the dispatcher (facilitator) discovers them by name. This is workable but **the framework does not document or test it**.
73. **Dormant specialists.** Without per-agent invocation counts from the parent DB (not queried here), I cannot adjudicate framework-waste vs. project-misfit. *Recommendation: add a `v_agent_invocation_30d` view and report it in `/knowledge-health`.*

---

## PART FIVE — Self-Assessment

### F20 — Coherence Check

74. **Commitments vs. reality.** Commitments 5 (ADR immutability) and 7 (human approval for Layer 3) are well-supported. Commitments 1 (reasoning is the artifact) and 2 (automatic capture) are *half-supported*: capture works; promotion is broken. Commitments 3, 4, 6, 8 are *narrative*: no compliance instrumentation verifies them.
75. **Most internally consistent.** The agent-roster shape (Values + Domain Lens) and the ADR pattern. Twelve agents conform; twelve ADRs follow the template.
76. **"Documentation theater" critique.** **Strongest evidence for the critique:** 109 pattern_sightings / 0 promotion_candidates with a *deferred* known bug in the closure pipeline; three Layer-3 folders empty (`.gitkeep` only); 1-of-14 rules with compliance signal; ADR-0002 promises five propagation phases and delivers one; lineage `divergence_distance: 0` despite real divergence. **Strongest evidence against:** the capture pipeline does run; the quality gate runs and passes; the substrate was actually built and validated end-to-end on a feature branch (with proper review cadence); 33 discussions exist with real specialist turns. The framework is **not** theater — but **the layer between "captured" and "useful" is broken**, and that is exactly where the documents make their boldest promises.

### F21 — Investment Recommendation

77. **ROI-ordered.**
    - **Finish/fix to reach designed potential:**
      1. **Fix surface_candidates / compute_effectiveness API drift** (close_discussion.py:95,101). One-day fix. Single highest ROI in the framework.
      2. **Wire BUILD_STATUS.md freshness check more aggressively** — extend quality_gate from advisory to blocking when BUILD_STATUS is older than the last commit.
      3. **Add per-agent invocation telemetry view** so dormancy is measurable, not anecdotal.
      4. **Bring substrate from `feature/sourced-assertion-substrate` into main** and wire at least one workflow (e.g., facilitator synthesis writes a sourced assertion).
    - **Remove (or honestly mark "future"):**
      1. **ADR-0002 Phases 2-5** (vouchers, version vectors, attribution, ecosystem dashboard) — either schedule them or move them to a backlog ADR and unblock the framework's stated narrative.
      2. **knowledge_pipeline_log.jsonl** if it stays a one-entry artifact from 2026-03-08 — either refresh on every `/knowledge-health` run or remove it.
    - **Quiet wins (maintain):**
      1. Hook system — secret detection, format, lock release. Working as designed.
      2. Quality gate with pre-commit enforcement.
      3. Discussion immutability.
    - **Missing but should exist:**
      1. Compliance instrumentation for autonomous_workflow, pre_build_search, micro_fix_protocol.
      2. Document-type-aware ingest hook (for Howie heterogeneity).
      3. Time-windowed retrieval primitive.
      4. Project-specific specialist registration mechanism (so Howie's genealogist/archivist agents don't have to be ad hoc).

78. **The ONE change.** **Fix the promotion pipeline.** The fix is mechanical — rename the keyword arguments or change the function signatures — and it unblocks Principle #1 ("reasoning is the primary artifact") at the layer where it currently fails. Howie generates a lot of reasoning across heterogeneous sources; the framework's value to Howie depends on that reasoning becoming durable. Right now it does not.

79. **The ONE change to NOT make.** Do not generalize the substrate prematurely to a multi-project, multi-tenant Layer-3 store before it has *one* in-framework consumer. The substrate just round-tripped on 2026-05-12. Let it cure in one workflow (e.g., facilitator synthesis writes a sourced assertion per review) before designing the federated version. Premature generalization is the framework's strongest aesthetic temptation, and Principle #8 ("least-complex intervention first") exists precisely to resist it.

### F22 — Framework Top Signals

1. **109 pattern_sightings → 0 promotion_candidates** is not a mystery. It is a known, deferred API drift between [close_discussion.py:95](scripts/close_discussion.py) and [surface_candidates.py:20](scripts/surface_candidates.py), swallowed by a non-fatal-warning try/except. Fixing this is the single highest-ROI move in the framework. It also retroactively explains the Verification Portal incident.

2. **Layer 3 is empty.** `memory/patterns/`, `memory/reflections/`, `memory/rules/` contain only `.gitkeep`. Layer 3 exists as a folder convention and a Principle #7 gating rule; no artifact has ever traveled the full pipeline end-to-end. The adoption log accumulates manually-entered candidates (45 PENDING) that don't auto-flow to curated memory either.

3. **Compliance instrumentation: ~7% (1/14 rules).** Quality gate enforces the commit protocol. The other 13 rules are honor-system. The framework's claim to "verifiable principles" is, today, mostly aspirational.

4. **Lineage drift is silent.** `divergence_distance: 0` despite three v3.x releases, eight project re-analyses, and a built-and-validated substrate. The propagation system the framework promises (ADR-0002 phases 2-5) is unbuilt, and the phase-1 drift detector is reporting noise-zero rather than measuring real drift.

5. **Substrate is half-shipped.** Built and validated end-to-end (MCP round-trip 2026-05-12, semantic search at 1.113 distance, source_ref canonicalization working) — but on `feature/sourced-assertion-substrate`, not in main, with no in-framework consumer. The next decision is workflow-integration before federation.

6. **No primitive for the things Howie will need.** No type-routed ingest, no time-windowed retrieval, no user-facing memory layer, no project-specialist registration. Each will be project-instance custom work unless the framework adds primitives first. *Order of likely need: project-specialist registration → type-routed ingest → user-facing memory layer → time-windowed retrieval.*

7. **The framework's narrative outruns its code by exactly one layer.** Capture is real. Indexing is real. Promotion is broken. Propagation is unbuilt. The documents describe a five-layer system; the working code reliably delivers two. That gap is fixable in weeks, not quarters — if the API drift is fixed and at least one promotion round-trips end-to-end.

---

*Diagnostic produced 2026-05-13. Worktree `claude/reverent-lovelace-84e718`. Where the worktree state diverges from the parent working tree on `feature/sourced-assertion-substrate`, the parent state has been used and called out.*
