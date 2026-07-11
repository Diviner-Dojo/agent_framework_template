# Framework Changelog

Human-readable record of framework-level changes (agents, rules, hooks, capture, governance).
Detail and rationale live in the referenced ADRs; this file is the at-a-glance index.

> Created 2026-06-13 alongside D2 backflow pattern 2 (the mission's named deliverable). The
> pattern-1 entry below is backfilled — pattern 1 shipped 2026-06-12 using its ADR + commit
> message as the de-facto changelog before this file existed.

## Back-flow from `dan_research_karpathy_wiki` (SPEC-20260610-205507, decision D2)

Patterns this satellite built and hardened first, returned to the hub. Origin credited per the
Prime Objective attribution test; each delivery flips the wiki's `back_flow` ledger `owed → delivered`.

### 2026-06-27 — Pattern 5 of 5: suchness invariant (ADR-0027)
- **What:** names the **source-canonical / provenance-tether** property in `PHILOSOPHY.md` — a new closing
  subsection of "What the framework refuses." L1 discussions are canonical; downstream artifacts (L2/L3,
  ADRs, reviews, promoted memory) are *vehicles* that must stay tethered to the discussion that grounded
  them. Doc-only, behavior-neutral; no new principle, invariant, or gate.
- **Deliberate deviation from the wiki:** the wiki's "raw wins" is an external-ground-truth rule; the
  template's L1 discussions are internally produced, so the port preserves the **provenance tether** (the
  link is canonical/immutable) without importing "the earlier artifact is always more correct" —
  supersession via Principle #5 stays intact. Claims mechanical enforcement only where it exists (the ADR
  `discussion_id` gate); types the L3 path as a standing obligation, not a guarantee.
- **Scope:** **this fork only** (PHILOSOPHY.md is a pinned, divergent trait). Public-upstream promotion is
  **deferred-with-trigger** (next custodian upstream batch, or an L3 source-pointer gate). The wiki-side
  `owed → delivered` flip must still be applied in the wiki repo.
- **Status:** **3 of 5 delivered** (patterns 1, 2, 5). Patterns 3 (extraction-miss-log) and 4
  (sha256-freshness manifest) remain owed.
- **Review:** REV-20260627-201200 (approve-with-changes, 0 blocking; docs-knowledge 0.92,
  independent-perspective 0.84). Steward-gated (REVISE → addressed). Discussion DISC-20260627-200311.

### 2026-06-13 — Pattern 2 of 5: confidence-calibration loop (ADR-0024)
- **What:** `scripts/audit_calibration.py` closes the audit→tighten loop the template left open —
  it reads the already-computed-but-unread `agent_effectiveness.confidence_calibration` plus
  findings classifications and emits **human-gated proposals** to tighten the classifier surfaces.
  Adds a "Calibration Loop" procedure to `.claude/rules/autonomous_workflow.md` (the named donor
  target) and `tests/test_audit_calibration.py`.
- **Deliberate deviation from the wiki:** the wiki auto-proposes prompt edits; the template writes
  `status: pending` proposals to `memory/calibration-proposals/` that a **human** applies — the
  agent never edits a classifier surface (Principle #7; Prime Objective human-mediated enforcement).
  Independent invariant/deviation enumeration: DISC-20260613-234253 (independent-perspective).
- **Behaviour-neutral:** a read-only audit + an advisory rule section; nothing changes until a
  human runs the audit and chooses to apply a proposal.

### 2026-06-12 — Pattern 1 of 5: one-shot Stop hook (ADR-0023)
- **What:** `scripts/stop_hook.py` + `scripts/queue_stop_notify.py` — a silent-by-default Stop hook
  that fires exactly one queued, intent-described ntfy notification when a session stops, with
  allow-list-gated reply injection. The `.claude/settings.json` Stop block is parked as a draft
  diff for the developer (`docs/drafts/DRAFT-20260612-settings-stop-hook.diff`).
- **Deliberate deviation from the wiki:** allow-list-only injection of the matched canonical label
  (never raw reply text), single-poller discipline, no-slug error paths, bounded wait cap, intent
  TTL — the wiki injects raw reply text, which the template's untrusted-reply invariant forbids.
- **Behaviour-neutral:** inert until the developer applies the settings diff.
