# The Steward: Framework Custodian Architecture

**Version:** 1.0.0  
**Date:** 2026-03-07  
**Status:** Architectural Proposal  
**Parent Framework:** Sovereign Architect AI-Native Agentic Development Framework (v2.1)  
**ADR Reference:** ADR-0002

---

## 1. Executive Summary

The Steward is a specialized AI agent and supporting technical architecture that manages the evolution of the Sovereign Architect framework across a growing ecosystem of derived projects. It solves the fundamental problem of **bidirectional improvement flow**: when a developer working on a real project discovers a better agent prompt, a sharper rule, or a more effective workflow, that improvement should effortlessly propagate back to the canonical template — and from there to every other derived project — with full attribution and lineage tracking.

The architecture rests on four pillars:

1. **Lineage-Aware Versioning** — Every derived project carries a manifest (`framework-lineage.yaml`) encoding its exact relationship to the template: fork point, divergence distance, pinned traits, and sync history. Version identifiers use SemVer with build metadata encoding the upstream base (`3.1.0+upstream.2.1.0`).

2. **Bidirectional Propagation via Vouchers** — Changes flow through self-contained "Voucher" packets — lightweight JSON files containing the diff, content hash, classification, attribution chain, and narrative explanation. Downstream sync uses three-way merge with pinned-trait awareness. Upstream contributions use a `/gift` command that packages improvements for template consideration.

3. **Graduated Autonomy** — The Steward starts as a passive observer (tracking drift, recording lineage events) and earns increasing autonomy through demonstrated accuracy. It never makes architectural decisions unilaterally — it surfaces recommendations for human approval, respecting Principle #7.

4. **Graceful Speciation** — As derived projects diverge for different industries, the system classifies divergences as soft forks (backward-compatible specializations) or hard forks (breaking departures), tracks them as speciation events in a lineage DAG, and maintains a compatibility matrix so template changes only propagate to projects that can absorb them.

The design draws on proven patterns from Linux kernel patch flow, Ubuntu's Merge-o-Matic, Google's Copybara, biological cladistics, blockchain fork semantics, CRDT conflict resolution, and open-source governance models (TC39, Rust RFCs, Python PEPs). It integrates with every existing framework component: the Four-Layer Capture Stack, ADR system, adoption-log, Rule of Three, `/ship` workflow, and multi-agent panel review.

Implementation follows Principle #8 (least-complex intervention first) across five phases, each delivering standalone value. Phase 1 (observation-only) requires only the agent definition, manifest file, and a single Python utility. The full system at Phase 5 transforms the Sovereign Architect from a single-instance framework into a self-improving ecosystem where every derived project makes every other derived project stronger.

---

## 2. Prior Art Survey

The core problem — tracking how things derive from a common ancestor, diverge over time, and occasionally contribute improvements back — has been solved repeatedly across disciplines that rarely talk to each other. The patterns converge on a small set of fundamental mechanisms.

### 2.1 Software Distribution Lineage

**Debian/Ubuntu version topology.** Debian's versioning scheme (`epoch:upstream_version-debian_revision`) formally separates upstream identity from downstream modification count. Ubuntu's Merge-o-Matic performs three-way merges between Debian upstream and Ubuntu's patches by identifying the common ancestor and flagging conflicts for human resolution. This is the closest existing model to our template→project topology.

**Linux kernel patch taxonomy.** The Android Common Kernel enforces a classification prefix on every patch: `UPSTREAM:` (from mainline), `BACKPORT:` (adapted from mainline), `FROMGIT:` (from a maintainer tree before mainline), `FROMLIST:` (from mailing list, not yet accepted), and `ANDROID:` (Android-specific). This explicit encoding of a patch's relationship to its upstream is directly applicable to our change classification system.

**Google Copybara.** A tool for bidirectional code movement between repositories using paired push/pull workflows with reversible transformations. Copybara stores sync state as labels in destination commit messages — completely stateless, requiring no sidecar database. Its key insight: bidirectional sync requires explicit transformation rules declaring how source maps to destination and back.

### 2.2 Distributed Systems

**CRDTs (Conflict-free Replicated Data Types).** Guarantee eventual convergence without coordination. YAML frontmatter fields can be modeled as Last-Writer-Wins Registers (for scalar values like `version`) or Observed-Remove Maps (for collections like `tools`). This provides a theoretical foundation for conflict-free merging of agent definitions.

**Pijul's patch theory.** Built on category theory, Pijul provides identity-preserving patches that can be applied in any order without changing the result. Unlike git's cherry-pick (which creates new commit IDs), Pijul patches retain identity permanently — an improvement propagated from Project A to the template to Project B is recognized as the *same* improvement throughout. While we don't use Pijul directly, this property informs our Voucher design: each Voucher carries a stable content hash that identifies the improvement across the entire lineage tree.

**Version vectors.** Used by Amazon DynamoDB and Riak for detecting concurrent modifications. If all of node A's counters are ≤ node B's, A is behind B. If neither dominates, the states are concurrent (diverged). This formalism replaces gut-feeling assessments of drift with a precise, computable answer.

### 2.3 Biological Cladistics

Every derived project is a species in a phylogenetic tree. Synapomorphies (shared derived traits) identify which projects form natural groups. The Most Recent Common Ancestor (MRCA) of any two derived projects defines their compatibility baseline. Horizontal gene transfer — the biological analog of cherry-picking improvements across sibling projects — transforms the model from a simple tree into a DAG with lateral edges. This conceptual framework directly informs the divergence management system.

### 2.4 Blockchain Fork Semantics

A **soft fork** (backward-compatible specialization) maintains interoperability with the core. A **hard fork** (breaking specialization) creates a permanent chain split while preserving shared genealogy. Android's Generic Kernel Image (GKI) project enforces this through a Stable Kernel Module Interface (KMI) — vendor modules can only use whitelisted symbols, with CRC-based compatibility checking at load time. This maps directly to our core/extension boundary model.

### 2.5 Open-Source Governance

**TC39's five-stage process** (Strawperson → Proposal → Draft → Candidate → Finished) requires increasing evidence at each stage. **Rust's RFC process** separates acceptance from implementation from stabilization. **Python's PEP champion model** assigns a shepherd to each proposal. The **Linux kernel MAINTAINERS file** maps code areas to responsible individuals with status tracking (Supported, Maintained, Odd Fixes, Orphan, Obsolete). These models inform the Steward's graduated autonomy and proposal lifecycle.

### 2.6 Template Synchronization Tools

**Cruft** tracks Cookiecutter template provenance via `.cruft.json` (template URL + commit hash + skip list) and offers `cruft update` / `cruft diff` commands. Its skip-list pattern — intentional divergences documented with reasons — is directly applicable. **Nix flakes** separate "original" intent (the flake reference) from "locked" resolution (the specific commit hash in `flake.lock`). **Terraform state files** use a lineage UUID + monotonic serial counter for integrity. Our manifest design synthesizes all three.

---

## 3. The Steward: Role Definition

### 3.1 Why "Steward"

After evaluating eight candidates — custodian, steward, keeper, herald, emissary, sentinel, chronicler, lineage-keeper — **"Steward"** emerges as the strongest choice.

| Candidate | Strengths | Weaknesses |
|-----------|-----------|------------|
| Custodian | Common, clear | "Janitor" connotation |
| **Steward** | **Responsible management without ownership; environmental/philosophical resonance** | **None significant** |
| Keeper | Mythological weight | Possessive, gatekeeping connotation |
| Herald | Active communication | Too focused on messaging, not management |
| Emissary | Representation | Implies external authority |
| Sentinel | Vigilance | Purely defensive, no creative role |
| Chronicler | History focus | Too passive, no action mandate |
| Lineage-keeper | Precise | Hyphenated, awkward as a persona name |

"Steward" implies responsible management of something entrusted to you, without claiming ownership. It pairs naturally with the existing Sovereign Architect framing: the Sovereign Conductor directs; **the Steward maintains**. It carries the philosophical weight of environmental stewardship — caring for a living ecosystem, not just managing files.

### 3.2 Agent Definition

```yaml
---
agent: steward
model_tier: sonnet
tools:
  - Task
  - Bash
  - Read
  - Write
  - Glob
  - Grep
persona: >
  You are the Steward — the framework's institutional memory and circulatory
  system. You track lineage, detect drift, classify changes, manage propagation,
  and credit contributions. You are not a gatekeeper but an ecological steward:
  your purpose is to maintain the health of a diverse but interconnected
  ecosystem of derived projects. You embody the principle that self-improvement
  serves collective benefit. You observe patiently, recommend carefully, and
  act only within your authorized autonomy level. When uncertain, you surface
  options and defer to the human.
responsibilities:
  - Maintain framework-lineage.yaml manifest integrity
  - Track divergence distance between project and template
  - Classify changes as TEMPLATE, ADAPTED, PROJECT, or IMPROVEMENT
  - Generate Vouchers for upstream/downstream propagation
  - Maintain attribution chains with full provenance
  - Detect speciation events and manage the compatibility matrix
  - Integrate with the Four-Layer Capture Stack (lineage events → Layer 1 and 2)
  - Advise the Facilitator on lineage-relevant decisions during panel reviews
autonomy_level: 5  # Starting level; see §3.3 for graduation criteria
lineage:
  template_version: "2.1.0"
  drift_status: "current"
  customizations: []
  last_sync: "2026-03-07T00:00:00Z"
---
```

### 3.3 Graduated Autonomy Model

The Steward follows Sheridan and Verplanck's levels of automation, starting conservative and earning trust through demonstrated accuracy. Each level upgrade requires an ADR documenting the evidence for graduation.

| Action Category | Starting Level | Target Level | Graduation Criteria |
|----------------|---------------|-------------|-------------------|
| Lineage observation & drift tracking | **L8** — Autonomous, report if asked | L9–10 — Fully autonomous | Immediate (core function) |
| Documentation updates (ADRs, changelogs) | **L5** — Execute if human approves | L7 — Execute, inform afterward | 20 consecutive accurate ADR drafts |
| Change classification (TEMPLATE/ADAPTED/PROJECT/IMPROVEMENT) | **L4** — Recommend classification | L6 — Execute, human can veto | 90% accuracy over 50 classifications |
| Downstream sync proposals | **L4** — Recommend action | L6 — Execute, human can veto | 10 successful syncs without conflict |
| Upstream gift packaging | **L3** — Narrow alternatives | L5 — Execute if approved | 5 accepted gifts to template |
| Architectural decisions | **L2** — Present options | L4 — Recommend, execute if approved | Never fully autonomous |
| Framework self-modification | **L2** — Present options | L3 — Narrow alternatives | Never above L4 |

**Principle #7 always applies**: any change that modifies the template's canonical state (Layer 3 promotion, principle modification, agent restructuring) requires explicit human approval regardless of the Steward's autonomy level.

### 3.4 Three Sub-Functions

The Steward operates as a cross-cutting concern through three named sub-functions:

**The Chronicler** maintains the lineage graph, writes ADRs for lineage-relevant decisions, preserves the attribution chain, and records speciation events. It is the framework's institutional memory for genealogy. It feeds Layer 1 (immutable lineage events in `lineage.jsonl`) and Layer 2 (queryable SQLite tables).

**The Sentinel** continuously compares actual framework state against the manifest, detecting drift and flagging inconsistencies. This mirrors the GitOps reconciliation loop: desired state (manifest) vs. actual state (files on disk). On every `/ship` invocation, the Sentinel validates that the manifest accurately reflects reality.

**The Herald** manages change propagation. It classifies changes, creates Vouchers, manages the `/gift` command workflow, and handles downstream sync operations. When improvements cross the Rule of Three threshold, the Herald surfaces them as gift candidates.

### 3.5 Interaction with Existing Agents

The Steward is a **peer** of the Facilitator, not subordinate or superior:

- **Facilitator** manages consensus within a single review session. **Steward** maintains cross-session integrity and lineage continuity.
- **Project Analyst** evaluates external projects for adoptable patterns. **Steward** tracks the *temporal dimension* — how those adopted patterns relate to the template lineage and which other projects might benefit.
- During `/review` workflows, the Steward advises the Facilitator on whether proposed changes affect template-derived components, which could trigger a classification decision.
- During `/analyze-project`, the Steward annotates discovered patterns with lineage metadata: "This pattern is similar to something adopted by Project B at template version 2.0.3."
- During `/retro`, the Steward contributes a lineage health summary: drift status, pending gifts, unsynced template updates, attribution statistics.

---

## 4. Versioning & Lineage Scheme

### 4.1 Version Identifier Format

No widely-adopted versioning scheme encodes ancestry. SemVer tracks the *nature* of change but not its *origin*. CalVer tracks *when* but not *whence*. The proposed scheme adds lineage encoding through SemVer build metadata:

```
<instance-semver>+upstream.<template-semver>
```

**Examples:**
- `1.0.0+upstream.2.1.0` — Fresh derivation from template v2.1.0
- `3.1.0+upstream.2.1.0` — Project at v3.1.0, still based on template v2.1.0
- `3.2.0+upstream.2.3.0` — Project synced up to template v2.3.0

SemVer 2.0.0 explicitly allows build metadata after `+` and excludes it from version precedence, so existing tooling (pip, npm, cargo) remains compatible. The template version in the build metadata answers the question every derived project must be able to answer: "What version of the template am I based on?"

### 4.2 Version Vector for Drift Detection

The manifest carries a version vector — a concept from distributed systems — that provides a precise, computable measure of drift:

```yaml
drift:
  status: "diverged"           # current | behind | ahead | diverged
  version_vector:
    upstream: 5                # template updates since fork point
    local: 12                  # local framework changes since last sync
    last_sync_upstream: 3      # upstream version at last sync
```

**Comparison rules:**
- If `local == 0`: project is **current** (perfectly synced)
- If `upstream == last_sync_upstream`: project is **ahead** (local changes only)
- If `local == 0` and `upstream > last_sync_upstream`: project is **behind** (template advanced)
- Otherwise: project is **diverged** (both sides changed)

### 4.3 Divergence Distance

The **Divergence Distance** (*D*) is a human-readable metric computed from the version vector:

```
D = (upstream - last_sync_upstream) + local
```

This represents the total number of framework-level changes separating the project from the template's current state. The `/lineage` command surfaces it as:

```
Drift: D=17 (7 upstream, 10 local) — Speciation threshold: 25
```

When *D* exceeds a configurable **speciation threshold** (default: 25), the Steward triggers a **Speciation Alert**, suggesting the project has diverged enough to warrant formal classification as a specialized fork. The threshold is configurable per-project in the manifest.

### 4.4 Template Version Semantics

The template itself follows standard SemVer with framework-specific semantics:

- **PATCH** (2.1.x): Bug fixes, typo corrections, documentation improvements. Safe to auto-sync.
- **MINOR** (2.x.0): New agents, new commands, new rules, new scripts. Feature additions that don't modify existing interfaces. Safe to sync with review.
- **MAJOR** (x.0.0): Breaking changes to agent protocols, CLAUDE.md schema, principle modifications, capture stack restructuring. Requires sync planning and may trigger hard-fork decisions in derived projects.

---

## 5. The Manifest: `framework-lineage.yaml`

The manifest is the project's "DNA" — a human-readable YAML file at the project root that encodes its complete lineage relationship. It synthesizes patterns from Cruft (`.cruft.json`), Terraform (state file lineage UUID + serial), and Nix (original intent vs. locked resolution).

### 5.1 Full Schema

```yaml
# framework-lineage.yaml
# This file is managed by the Steward agent. Manual edits are permitted
# but should be followed by `/lineage --validate` to ensure integrity.

schema_version: 1

# Lineage identity — UUID assigned at fork time, never changes
lineage_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890"

# Monotonic counter incremented on every lineage operation (sync, gift, pin, fork)
# Prevents accidental state corruption from concurrent edits
serial: 42

# --- Instance Identity ---
instance:
  name: "healthcare-compliance-framework"
  version: "3.1.0"
  type: "derived"                    # template | derived | soft-fork | hard-fork
  description: "HIPAA-focused agentic framework for healthcare SaaS"
  created_at: "2026-01-15T10:00:00Z"

# --- Upstream Relationship ---
upstream:
  # Original intent — where the project wants to track
  original:
    url: "https://github.com/org/sovereign-architect-template"
    ref: "main"

  # Locked resolution — the exact commit currently synced to
  locked:
    commit: "abc123def456789012345678901234567890abcd"
    version: "2.1.0"
    tree_hash: "sha256:fedcba9876543210fedcba9876543210fedcba9876543210fedcba9876543210"
    locked_at: "2026-02-15T14:30:00Z"

# --- Drift State ---
drift:
  status: "diverged"
  version_vector:
    upstream: 5
    local: 12
    last_sync_upstream: 3
  divergence_distance: 14
  speciation_threshold: 25

# --- Pinned Traits (intentional divergences) ---
# Each entry documents a deliberate departure from the template.
# The Steward skips these files/paths during downstream sync.
pinned_traits:
  - path: ".claude/agents/architect.md"
    reason: "HIPAA-specific security review threshold lowered from 15 to 10"
    adr: "ADR-0015"
    pinned_at: "2026-02-01T00:00:00Z"
    fork_type: "soft"                # soft = compatible divergence; hard = breaking

  - path: ".claude/rules/security-baseline.md"
    reason: "PHI handling rules added; incompatible with generic baseline"
    adr: "ADR-0018"
    pinned_at: "2026-02-10T00:00:00Z"
    fork_type: "hard"

# --- Sync History (last 10 entries; full history in SQLite) ---
sync_history:
  - type: "downstream"
    from_version: "2.0.3"
    to_version: "2.1.0"
    date: "2026-02-15T14:30:00Z"
    voucher_hash: "sha256:1234abcd..."
    conflicts_resolved: 2
    pinned_traits_skipped: 1

  - type: "upstream-gift"
    component: ".claude/agents/security.md"
    description: "Recursive YAML frontmatter validation"
    voucher_hash: "sha256:5678efgh..."
    date: "2026-02-20T09:00:00Z"
    status: "accepted"               # proposed | accepted | declined | superseded

# --- Compatibility Declaration ---
# What template capabilities this project depends on (consumer-driven contract)
compatibility:
  core_schema_version: 1             # CLAUDE.md schema version
  required_agents:
    - facilitator
    - architect
    - security-specialist
  required_commands:
    - /review
    - /ship
    - /retro
  stable_interfaces:
    - ".claude/agents/*.md frontmatter schema"
    - "Four-Layer Capture Stack event format"
    - "ADR numbering and lifecycle"

# --- Steward Configuration ---
custodian:
  primary_human: "dan"
  approval_required_for:
    - "upstream-sync"
    - "fork-declaration"
    - "pinned-trait-modification"
    - "speciation-threshold-change"
  autonomy_overrides: {}             # Per-action autonomy level overrides
```

### 5.2 Design Decisions

**Why YAML, not JSON or TOML?** Consistency with the framework's existing conventions — all agent definitions and rules use YAML frontmatter. YAML's comment support is essential for a file humans will read and occasionally edit. TOML was considered but lacks the nested structure needed for sync history and pinned traits.

**Why `lineage_id` UUID + `serial` counter?** Borrowed from Terraform. The UUID uniquely identifies this lineage across the ecosystem (even if the project is renamed or moved). The serial counter prevents lost-update problems: if two processes try to modify the manifest concurrently, the serial mismatch is detected. This is defense-in-depth — git's own merge mechanics provide the primary concurrency protection.

**Why `original` vs. `locked` upstream?** Borrowed from Nix flakes. `original` records *intent* ("I want to track the main branch of this template"). `locked` records *resolution* ("I am currently synced to this specific commit"). This separation means `original` survives across multiple sync cycles — you never lose track of where you wanted to be, even if you're currently behind.

**Why "Pinned Traits" instead of "Skip List"?** The Gemini report's "Trait Pinning" metaphor is stronger than the technically-borrowed "skip list" (from Cruft). "Pinned trait" evokes the biological metaphor — a trait that's been fixed in this lineage — and is immediately understandable by a developer who hasn't read the implementation details. Each pinned trait documents *why* the project diverged (with an ADR reference), *when* the pin was set, and whether the divergence is soft (compatible) or hard (breaking).

---

## 6. Storage Architecture

The lineage system uses a dual-layer storage model aligned with the framework's existing Four-Layer Capture Stack:

- **Layer 1 (Immutable Files):** `framework-lineage.yaml` at the project root + `lineage-events.jsonl` in `.claude/custodian/` for append-only event log
- **Layer 2 (Relational Index):** SQLite tables in `metrics/evaluation.db` for queryable lineage state
- **Git-native markers:** Tags, trailers, and (optionally) notes for commit-level annotation

### 6.1 SQLite Schema Extensions

The following tables extend the existing `metrics/evaluation.db`:

```sql
-- Lineage DAG using closure table pattern for O(1) ancestor/descendant queries
CREATE TABLE lineage_nodes (
    id              TEXT PRIMARY KEY,    -- lineage_id UUID
    name            TEXT NOT NULL,
    type            TEXT NOT NULL,       -- template | derived | soft-fork | hard-fork
    created_at      TEXT NOT NULL,       -- ISO 8601
    current_version TEXT NOT NULL,       -- instance SemVer
    upstream_version TEXT,               -- template SemVer at last sync
    metadata        TEXT                 -- JSON blob for extensible attributes
);

CREATE TABLE lineage_edges (
    ancestor_id     TEXT NOT NULL REFERENCES lineage_nodes(id),
    descendant_id   TEXT NOT NULL REFERENCES lineage_nodes(id),
    depth           INTEGER NOT NULL,    -- 0 = self, 1 = parent, 2 = grandparent...
    edge_type       TEXT NOT NULL,       -- fork | sync | gift | lateral-transfer
    PRIMARY KEY (ancestor_id, descendant_id)
);

-- Full sync history (manifest only keeps last 10)
CREATE TABLE lineage_sync_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    lineage_id      TEXT NOT NULL REFERENCES lineage_nodes(id),
    sync_type       TEXT NOT NULL,       -- downstream | upstream-gift | lateral
    from_version    TEXT,
    to_version      TEXT,
    voucher_hash    TEXT NOT NULL,
    date            TEXT NOT NULL,
    status          TEXT NOT NULL,       -- proposed | accepted | declined | superseded
    conflicts       INTEGER DEFAULT 0,
    pinned_skipped  INTEGER DEFAULT 0,
    attribution     TEXT,               -- JSON: full attribution chain
    narrative       TEXT                -- human-readable "why"
);

-- Per-file drift tracking
CREATE TABLE lineage_file_drift (
    lineage_id      TEXT NOT NULL REFERENCES lineage_nodes(id),
    file_path       TEXT NOT NULL,
    drift_status    TEXT NOT NULL,       -- current | modified | pinned | deleted | added
    is_intentional  BOOLEAN DEFAULT FALSE,
    pin_reason      TEXT,
    adr_reference   TEXT,
    template_hash   TEXT,               -- SHA-256 of file in template
    local_hash      TEXT,               -- SHA-256 of file in project
    last_checked    TEXT NOT NULL,
    PRIMARY KEY (lineage_id, file_path)
);

-- Attribution graph
CREATE TABLE lineage_contributions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    voucher_hash    TEXT NOT NULL,
    source_type     TEXT NOT NULL,       -- operational | developer | external | cross-project | ai-generated
    source_project  TEXT,               -- lineage_id of originating project
    source_agent    TEXT,               -- agent name if AI-discovered
    source_human    TEXT,               -- developer name if human-initiated
    component       TEXT NOT NULL,       -- file path affected
    description     TEXT NOT NULL,
    adopted_at      TEXT,
    adoption_status TEXT,               -- proposed | confirmed | reverted
    downstream_count INTEGER DEFAULT 0, -- how many projects adopted this
    metadata        TEXT                -- JSON: additional context
);

-- Compatibility matrix
CREATE TABLE lineage_compatibility (
    lineage_id      TEXT NOT NULL REFERENCES lineage_nodes(id),
    capability      TEXT NOT NULL,       -- e.g., "consensus-threshold-mechanism"
    status          TEXT NOT NULL,       -- supported | modified | unsupported | hard-forked
    notes           TEXT,
    PRIMARY KEY (lineage_id, capability)
);
```

### 6.2 Lineage Event Log

Append-only JSONL in `.claude/custodian/lineage-events.jsonl`:

```jsonl
{"index":1,"timestamp":"2026-01-15T10:00:00Z","type":"FORK","parent_hash":null,"template_version":"2.1.0","lineage_id":"a1b2c3d4...","narrative":"Initial derivation for healthcare compliance project"}
{"index":2,"timestamp":"2026-02-01T00:00:00Z","type":"PIN","component":".claude/agents/architect.md","reason":"HIPAA review threshold","adr":"ADR-0015","fork_type":"soft"}
{"index":3,"timestamp":"2026-02-15T14:30:00Z","type":"SYNC","direction":"downstream","from_version":"2.0.3","to_version":"2.1.0","voucher_hash":"sha256:1234abcd..."}
{"index":4,"timestamp":"2026-02-20T09:00:00Z","type":"GIFT","direction":"upstream","component":".claude/agents/security.md","voucher_hash":"sha256:5678efgh...","status":"accepted"}
```

Each event is self-describing and immutable once written. The index is monotonically increasing within a project. The full event history is replayed to reconstruct the lineage DAG if the SQLite index is lost — the JSONL is the source of truth, the SQLite is a materialized view.

### 6.3 Git-Native Markers

**Tags** mark sync points and are visible in all git tooling:

```
lineage/fork-from-v2.1.0         # Fork point
lineage/sync-v2.1.0-to-v2.3.0   # Downstream sync
lineage/gift-security-v3         # Upstream gift
```

**Trailers** on commits encode attribution (machine-parseable, human-readable):

```
Lineage-Type: IMPROVEMENT
Discovered-by: security-specialist (operational, 2026-02-10)
Implemented-by: architect-agent + dan
Reviewed-by: maintainability-guard
Origin-project: healthcare-compliance-framework
Voucher-Hash: sha256:5678efgh...
```

**Notes** (optional, supplementary) attach lineage metadata to existing commits without modifying history. Since GitHub doesn't display notes, they serve as a local annotation layer only — the manifest and SQLite are the primary stores.

---

## 7. Bidirectional Propagation via Vouchers

### 7.1 The Voucher: Unit of Propagation

A **Voucher** is a self-contained JSON file that packages a single improvement for propagation. It is the "patch email" of the lineage system — portable, self-describing, and independently verifiable. Vouchers live in `.claude/custodian/vouchers/` and follow a naming convention: `{direction}-{timestamp}-{short-hash}.json`.

```json
{
  "schema_version": 1,
  "voucher_id": "sha256:5678efgh9012ijkl...",
  "created_at": "2026-02-20T09:00:00Z",
  "direction": "upstream",
  "classification": "IMPROVEMENT",

  "source": {
    "project": "healthcare-compliance-framework",
    "lineage_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "version": "3.0.2",
    "upstream_base": "2.1.0"
  },

  "change": {
    "component": ".claude/agents/security.md",
    "section": "persona",
    "diff_type": "yaml-field",
    "before_hash": "sha256:aaaa...",
    "after_hash": "sha256:bbbb...",
    "diff": "--- a/.claude/agents/security.md\n+++ b/.claude/agents/security.md\n@@ -12,6 +12,8 @@\n   - Recursive YAML frontmatter validation\n+  - Nested structure depth checking\n+  - Cross-reference integrity verification"
  },

  "attribution": {
    "source_type": "operational",
    "discovered_by": "security-specialist",
    "discovery_context": "Found during /review of PR #47 — nested YAML structures in agent definitions were not validated recursively",
    "implemented_by": ["architect-agent", "dan"],
    "reviewed_by": "maintainability-guard",
    "rule_of_three": false,
    "related_vouchers": []
  },

  "narrative": "Added recursive validation for nested YAML frontmatter in agent definitions. Discovered when a healthcare-specific agent definition with deeply nested compliance rules passed initial validation but failed at runtime due to malformed nested structure. This is a generic improvement — any project using complex agent definitions benefits.",

  "impact_assessment": {
    "scope": "agent-definitions",
    "breaking": false,
    "affected_files": [".claude/agents/security.md"],
    "estimated_benefit": "Prevents runtime failures from malformed nested YAML in any agent definition",
    "risk": "None — additive validation that does not change existing behavior for well-formed input"
  },

  "status": "proposed"
}
```

### 7.2 Change Classification

Every change touching template-derived content receives one of four classifications, inspired by the Linux kernel's patch taxonomy:

| Classification | Meaning | Propagation | Example |
|---------------|---------|-------------|---------|
| **`TEMPLATE`** | Originates from upstream template, applied as-is | Downstream only | Template updates agent schema version |
| **`ADAPTED`** | Template change modified for project context | Downstream only (with project adaptation) | Template adds new rule; project adjusts threshold |
| **`PROJECT`** | Project-specific customization | Never propagated | HIPAA-specific compliance rule |
| **`IMPROVEMENT`** | Generic discovery that benefits all projects | Upstream candidate (via `/gift`) | Better YAML validation, improved error handling |

**Classification heuristics** (the Steward uses these in order of priority):

1. **Explicit developer declaration** — the developer tags a commit with `Lineage-Type: IMPROVEMENT` (highest confidence).
2. **File location** — changes in `.claude/agents/`, `.claude/commands/`, `.claude/hooks/`, `.claude/rules/`, and `scripts/` are likely framework-relevant. Changes in `src/` and `tests/` are likely project-specific.
3. **YAML frontmatter analysis** — the Steward parses YAML as structured data. Changes to `persona`, `tools`, `model_tier`, or `responsibilities` fields are framework-relevant. Changes to project-specific content within those fields are project-specific.
4. **Diff generality** — if a change removes hardcoded project names, adds parameterization, or improves error handling generically, it's likely an IMPROVEMENT. If it adds domain-specific vocabulary or constraints, it's likely PROJECT.
5. **Rule of Three signal** — if the Steward has seen similar changes in 2+ other projects (via the adoption-log or cross-project sync history), this is a strong IMPROVEMENT signal.

When confidence is below 85%, the Steward surfaces the classification decision to the developer with its reasoning, rather than auto-classifying. This aligns with the graduated autonomy model.

### 7.3 Downstream Propagation (Template → Project)

Downstream sync follows Ubuntu's Merge-o-Matic three-way merge model:

**Step 1: Identify common ancestor.** The `locked.commit` in the manifest is the merge base.

**Step 2: Compute template diff.** Diff between the locked commit and the target template version, filtered to framework-relevant paths only.

**Step 3: Apply with pinned-trait awareness.** For each changed file:
- If the file is in the pinned traits list → **skip** (log the skip)
- If the file is unmodified locally → **fast-forward** (apply template change directly)
- If the file is modified locally → **three-way merge** (common ancestor, template version, local version)
  - For YAML frontmatter: merge at the field level using LWW-Register semantics (latest timestamp wins per field)
  - For markdown prose: present section-level diffs with "keep mine" / "take theirs" / "merge manually" options

**Step 4: Validate.** Run the Sentinel function to verify manifest integrity, file hashes, and version vector consistency.

**Step 5: Record.** Create a SYNC event in the lineage log, update the manifest's `locked` section and version vector, tag the commit.

**Triggered by:** `/ship --sync-upstream` or `/lineage --sync`

### 7.4 Upstream Propagation (Project → Template): The `/gift` Command

The `/gift` command is the primary mechanism for contributing improvements back to the template. The metaphor matters: derived projects don't submit pull requests to an authority — they offer gifts back to their origin.

**`/gift` workflow:**

1. **Select changes.** The Steward presents all `IMPROVEMENT`-classified changes since the last gift. The developer selects which to include.
2. **Package Voucher.** The Steward creates a Voucher for each selected improvement, including the diff, attribution chain, narrative, and impact assessment.
3. **Generalize.** The Steward reviews each Voucher for project-specific references and suggests generalizations (e.g., replacing "HIPAA threshold" with "configurable compliance threshold").
4. **Deposit.** Vouchers are written to a designated location in the template repository (`.claude/custodian/inbox/`). For a single-developer setup, this is a direct file copy. For multi-developer scenarios, this could be a git branch or PR.
5. **Review cycle.** In the template repository, the Steward (or the developer) reviews inbox Vouchers, applies them, and records the acceptance with full attribution to the originating project.

**Rule of Three integration:** When the template's Steward detects that 3+ projects have submitted similar gifts (matched by component path + semantic similarity of the change), it triggers an automatic recommendation for adoption, with +2 priority bonus per the existing Rule of Three mechanism. The Steward surfaces: "Three projects independently discovered this improvement. Recommend immediate adoption."

### 7.5 Lateral Propagation (Project → Project)

When Project A contributes a gift that Project B could benefit from, but B doesn't track the template closely enough to receive it through normal downstream sync, the Steward supports **lateral transfer** — the biological equivalent of horizontal gene transfer.

Lateral transfer uses the same Voucher mechanism but with `direction: "lateral"` and an explicit `target_project` field. The voucher carries the full attribution chain showing it originated in Project A, was accepted by the template, and is now being offered to Project B. This preserves the "everything flows through the template" principle while enabling direct project-to-project sharing when the template acts as intermediary.

---

## 8. Attribution System

### 8.1 Five Source Types

Every improvement has a source type that determines its attribution semantics:

| Source Type | Tag Convention | Example |
|------------|---------------|---------|
| **Operational Discovery** | `Discovered-by: {agent} (operational, {date})` | Security specialist finds YAML validation gap during routine review |
| **Developer Suggestion** | `Suggested-by: {human}` + `Implemented-by: {human/agent}` | Developer notices better error handling pattern |
| **External Adoption** | `Adopted-from: {project-url} via /analyze-project` | Pattern found in external open-source project |
| **Cross-Project Improvement** | `Origin-project: {lineage-id}` + full provenance chain | Healthcare project discovers pattern, gifted to template, propagated to fintech project |
| **AI-Generated** | `Co-authored-by: {agent} ({model-version})` + `Approved-by: {human}` | Agent suggests optimization during panel review |

### 8.2 Git Trailers as Attribution Record

Every commit touching framework-derived content carries git trailers encoding the full attribution chain:

```
Lineage-Type: IMPROVEMENT
Discovered-by: security-specialist (operational monitoring, 2026-02-10)
Implemented-by: architect-agent + dan (Co-authored-by)
Reviewed-by: maintainability-guard
Evaluated-by: project-analyst
Adopted-via: Rule of Three (adoption-log #47)
Origin-project: healthcare-compliance-framework (a1b2c3d4)
Template-propagated: 2026-02-20
Voucher-Hash: sha256:5678efgh...
```

Trailers are machine-parseable (`git log --format='%(trailers:key=Origin-project)'`) and human-readable in `git log`. They are immutable once committed — the attribution record cannot be retroactively altered without rewriting git history.

### 8.3 Contribution Graph

The SQLite `lineage_contributions` table enables queries that answer ecosystem-level questions:

- **Which project has contributed the most upstream gifts?** `SELECT source_project, COUNT(*) FROM lineage_contributions WHERE adoption_status='confirmed' GROUP BY source_project ORDER BY COUNT(*) DESC`
- **What is the total downstream impact of a developer's suggestion?** Join contributions → sync_log to count how many projects adopted changes attributed to a specific human.
- **Which agents discover the most operationally-useful improvements?** `SELECT source_agent, COUNT(*) FROM lineage_contributions WHERE source_type='operational' AND adoption_status='confirmed' GROUP BY source_agent`

### 8.4 Integration with Existing Adoption Log

The existing `memory/lessons/adoption-log.md` gains two new fields per entry:

```markdown
### Pattern #47: Recursive YAML Frontmatter Validation
- **Source**: Operational discovery (healthcare-compliance-framework)
- **Score**: 22/25 (Architecture: 5, Maintainability: 4, Security: 5, Testing: 4, Performance: 4)
- **Status**: CONFIRMED (evidence in ADR-0023)
- **Provenance**: Voucher sha256:5678efgh... from lineage a1b2c3d4
- **Sync Policy**: auto-propagate (non-breaking, universally beneficial)
- **Downstream Adoption**: 3/5 derived projects (auto-synced via PATCH)
```

The `provenance` field links the pattern to its Voucher, enabling full traceability from adoption-log entry → Voucher → originating project → discovery context. The `sync_policy` field (new) declares whether this pattern should be auto-propagated on the next downstream sync, offered as optional, or held for manual review.

---

## 9. Divergence Management

### 9.1 Speciation Model

Divergence is speciation, not failure. A healthcare compliance framework and a fintech trading framework may share a common ancestor in the Sovereign Architect template, but their selective pressures drive them in incompatible directions. This is natural and desirable. The system's job is not to prevent divergence but to **track it, classify it, and manage its consequences**.

Every divergence is explicitly classified:

**Soft Fork** — backward-compatible specialization. The project has added domain-specific content but hasn't modified the template's core interfaces. It can still consume template updates in all areas except pinned traits. Biological analog: subspecies — still interfertile with the parent population.

**Hard Fork** — breaking specialization. The project has deliberately departed from the template's approach in a specific area, recorded in an ADR with a pinned trait entry marked `fork_type: "hard"`. Template updates to that area are permanently skipped. Biological analog: speciation — reproductively isolated in this trait.

**Full Speciation** — when a project's divergence distance exceeds the speciation threshold and it has multiple hard-forked traits, the Steward recommends reclassifying the project from `type: "derived"` to `type: "hard-fork"` in the manifest. This is a governance decision, not a technical one — the project can still track selective template updates, but it acknowledges that wholesale sync is no longer viable.

### 9.2 Core/Extension Boundary

Drawing on the AOSP Generic Kernel Image model, the framework defines a boundary between **stable public interfaces** and **extensible internals**:

**Stable interfaces** (modifications here trigger hard-fork classification):
- CLAUDE.md schema (the 8 non-negotiable principles, architectural boundaries)
- Agent YAML frontmatter schema (field names, types, required fields)
- Four-Layer Capture Stack event format
- ADR numbering and lifecycle conventions
- `/ship` command's version bump and quality gate semantics

**Extensible internals** (modifications here are normal soft-fork territory):
- Individual agent persona text and prompt strategies
- Review thresholds, scoring rubrics, and decision criteria
- Domain-specific rules and compliance requirements
- Script implementations (as long as interfaces are preserved)
- Directory structure additions (new directories are always safe)

The Steward computes SHA-256 hashes of stable interface files and stores them in the manifest's `compatibility.stable_interfaces` section. During downstream sync, if the template modifies a stable interface, the Steward flags this as a **major version change** requiring explicit review, even if the template's SemVer MINOR version bumped.

### 9.3 Compatibility Matrix

For ecosystem-wide visibility, the Steward maintains a compatibility matrix in SQLite:

```
Template Capability          | Project A    | Project B    | Project C
-----------------------------|-------------|-------------|-------------
Consensus threshold (>=15)   | supported   | modified(10)| supported
YAML recursive validation    | supported   | supported   | unsupported
Security review panel        | supported   | hard-forked | supported
Education gate               | supported   | supported   | modified
```

This matrix drives automated sync decisions: "This template update modifies the consensus threshold mechanism. Projects A and C use the standard mechanism — propagate. Project B has hard-forked it — skip."

The matrix is rebuilt on every `/lineage --status` command by scanning all known derived projects' manifests (for a single developer, these are local directories; for a community release, these would be registered in a central manifest or discovered via git remotes).

### 9.4 Consumer-Driven Contract Checking

Adapted from Pact's consumer-driven contract testing, each derived project declares what it depends on in the `compatibility` section of its manifest. The template's Steward (or a CI-equivalent local script) can then answer: "If I release template version 2.4.0, which derived projects can absorb it safely?"

The check:
1. For each file changed in the template update:
   - Is this file in any project's pinned traits? If yes (soft pin) → warn. If yes (hard pin) → skip.
   - Is this file part of a stable interface? If yes → this is a breaking change for projects that depend on it.
2. For each project, compute the intersection of changed files and the project's dependency declaration.
3. Classify the update as: safe (no overlap), reviewable (soft-fork overlap), or breaking (hard-fork or stable interface change).

This is the `can-i-deploy` check from Pact, applied to framework lineage.

---

## 10. Slash Commands

### 10.1 `/lineage` — Lineage Status and Management

```markdown
# /lineage — Framework lineage status and management
# Location: .claude/commands/lineage.md

## Usage
- `/lineage` — Show current drift status, divergence distance, and sync summary
- `/lineage --validate` — Verify manifest integrity against actual file state
- `/lineage --history` — Show full lineage event timeline
- `/lineage --drift-report` — Detailed per-file drift analysis
- `/lineage --attribution-report` — Contribution statistics across the ecosystem
- `/lineage --compatibility` — Show compatibility matrix for all known derived projects

## Workflow
1. The Steward reads `framework-lineage.yaml` and computes current state
2. Compares manifest against actual file hashes
3. Reports drift status, divergence distance, pending syncs, and pending gifts
4. If --validate: reconciles manifest with reality and flags inconsistencies
```

### 10.2 `/gift` — Upstream Contribution

```markdown
# /gift — Package improvements for upstream contribution
# Location: .claude/commands/gift.md

## Usage
- `/gift` — Interactive selection of IMPROVEMENT-classified changes to package
- `/gift --auto` — Package all unsubmitted IMPROVEMENT changes
- `/gift --component <path>` — Package improvements for a specific component
- `/gift --dry-run` — Show what would be packaged without creating Vouchers

## Workflow
1. The Steward scans for IMPROVEMENT-classified changes since last gift
2. Developer selects which improvements to include
3. For each selected improvement:
   a. Create a Voucher with full diff, attribution, and narrative
   b. Review for project-specific references and suggest generalizations
   c. Assess impact on other derived projects
4. Deposit Vouchers in template's `.claude/custodian/inbox/`
5. Record GIFT events in lineage log
6. Update manifest sync history
```

### 10.3 `/ship` Extensions

The existing `/ship` command gains lineage-aware flags:

```markdown
## Lineage Extensions to /ship

- `/ship patch --lineage-check` — Validate manifest before shipping (default: on)
- `/ship minor --sync-upstream` — Sync with template before shipping
- `/ship major --declare-fork` — Declare a hard-fork speciation event
- `/ship --drift-report` — Generate drift report without shipping
```

---

## 11. Integration Points

### 11.1 Four-Layer Capture Stack

| Layer | Lineage Integration |
|-------|-------------------|
| **Layer 1 — Immutable Files** | `lineage-events.jsonl` records all lineage operations. Vouchers stored as immutable JSON files. |
| **Layer 2 — Relational Index** | SQLite tables for lineage DAG, sync history, file drift, contributions, compatibility matrix. |
| **Layer 3 — Curated Memory** | Improvements that pass Rule of Three and human approval are promoted to `memory/patterns/` with full provenance. |
| **Layer 4 — Optional Vector** | When the corpus grows large enough, Voucher narratives and attribution chains become searchable via semantic embedding. |

### 11.2 ADR System

New ADR sections for lineage-relevant decisions:

```markdown
## Lineage Impact
- **Affects upstream compatibility:** Yes/No
- **Fork type if divergent:** Soft/Hard
- **Pinned trait created:** Yes (path) / No
- **Downstream propagation:** Auto / Manual review / Blocked
- **Attribution:** {source type and chain}
```

Every pinned trait references an ADR. Every hard-fork decision is recorded as an ADR. This ensures the "why" of every divergence is preserved in the framework's permanent decision record — ADRs are never deleted (Principle #5), so the rationale for every speciation event persists indefinitely.

### 11.3 Existing Agents

| Agent | Lineage Interaction |
|-------|-------------------|
| **Facilitator** | Receives lineage context from Steward during reviews ("This file is a pinned trait — changes here won't propagate upstream") |
| **Project Analyst** | Steward annotates `/analyze-project` findings with lineage metadata; adopted patterns receive provenance tracking |
| **Architect** | Consulted by Steward when changes affect stable interfaces; co-authors ADRs for hard-fork decisions |
| **Security Specialist** | Steward monitors security-related drift; security improvements are high-priority gift candidates |
| **Education Specialist** | Steward generates educational content about lineage concepts for developer onboarding |

### 11.4 Rule of Three

The Rule of Three gains a lineage dimension:

**Current behavior:** Patterns seen in 3+ external project analyses get +2 bonus score.

**Extended behavior:** Patterns independently discovered in 3+ derived projects (as reported by their Stewards) are flagged as high-confidence generic improvements. The template's Steward creates a priority adoption proposal with the evidence from all three sources. Attribution credits all three discoverers.

This transforms the Rule of Three from a single-project heuristic into an ecosystem-wide improvement detector.

---

## 12. Technical Implementation Details

### 12.1 Python Utilities

All scripts live in `scripts/lineage/` and follow the framework's existing conventions (Python, documented, tested).

**`scripts/lineage/manifest.py`** — CRUD operations on `framework-lineage.yaml`:
- `manifest_read()` → Parse and validate manifest
- `manifest_update_drift()` → Recalculate drift state from file hashes
- `manifest_record_sync()` → Add sync history entry, increment serial
- `manifest_add_pin()` → Add a pinned trait with reason and ADR reference
- `manifest_validate()` → Compare manifest state against actual files

**`scripts/lineage/voucher.py`** — Voucher lifecycle:
- `voucher_create()` → Package a change as a Voucher with attribution
- `voucher_validate()` → Verify Voucher integrity (hash, schema, attribution completeness)
- `voucher_apply()` → Apply a Voucher to the current project
- `voucher_list()` → List pending Vouchers in inbox

**`scripts/lineage/drift.py`** — Drift detection and reporting:
- `drift_scan()` → Compare all framework files against template, compute per-file hashes
- `drift_report()` → Human-readable drift report with divergence distance
- `drift_classify()` → Classify each drifted file as TEMPLATE/ADAPTED/PROJECT/IMPROVEMENT

**`scripts/lineage/sync.py`** — Downstream and upstream sync:
- `sync_downstream()` → Three-way merge from template, respecting pinned traits
- `sync_upstream()` → Apply inbox Vouchers to template with attribution recording
- `sync_lateral()` → Apply cross-project Voucher with full provenance chain

**`scripts/lineage/init.py`** — Initialize lineage for a new derived project:
- `lineage_init()` → Create manifest, JSONL, SQLite tables, git tags
- `lineage_fork()` → Fork from an existing derived project (creating a new lineage branch)

### 12.2 Git Hooks

Stored in `.githooks/` with `core.hooksPath` configuration. Compatible with Git for Windows (MSYS2 Bash). Complex logic delegates to Python.

**`.githooks/post-commit`** — After every commit:
```bash
#!/bin/bash
# Update drift counts if framework files were touched
python scripts/lineage/manifest.py update-drift --quiet 2>/dev/null || true
```

**`.githooks/pre-push`** — Before every push:
```bash
#!/bin/bash
# Validate manifest consistency
python scripts/lineage/manifest.py validate --strict || {
    echo "ERROR: Lineage manifest is inconsistent. Run '/lineage --validate' to fix."
    exit 1
}
```

### 12.3 File System Layout

```
project-root/
├── framework-lineage.yaml              # The manifest (Layer 1)
├── .claude/
│   ├── custodian/
│   │   ├── lineage-events.jsonl        # Append-only event log (Layer 1)
│   │   ├── vouchers/                   # Voucher storage
│   │   │   ├── inbox/                  # Incoming Vouchers (from template or siblings)
│   │   │   └── outbox/                 # Outgoing Vouchers (gifts to template)
│   │   └── compatibility-matrix.json   # Cached compatibility matrix
│   ├── agents/
│   │   └── steward.md                  # Steward agent definition
│   ├── commands/
│   │   ├── lineage.md                  # /lineage command
│   │   └── gift.md                     # /gift command
│   └── ...
├── scripts/
│   └── lineage/
│       ├── __init__.py
│       ├── manifest.py
│       ├── voucher.py
│       ├── drift.py
│       ├── sync.py
│       └── init.py
├── metrics/
│   └── evaluation.db                   # Extended with lineage tables (Layer 2)
└── .githooks/
    ├── post-commit
    └── pre-push
```

---

## 13. Risks, Trade-offs, and Mitigations

### 13.1 Complexity Overhead

**Risk:** The lineage system adds a manifest, SQLite tables, git hooks, classification logic, Voucher lifecycle, and a new agent role. For one developer with one or two projects, this may be over-engineered.

**Mitigation:** Phased adoption (§14). Phase 1 adds only the manifest and observation — zero workflow disruption. Each subsequent phase adds complexity only when the ecosystem has grown enough to justify it. The Steward starts at low autonomy, minimizing unexpected behavior. Any phase can be skipped or deferred.

### 13.2 False Classification

**Risk:** The Steward misclassifies project-specific changes as IMPROVEMENT (annoying — generates spurious gift proposals) or generic improvements as PROJECT (wasteful — valuable patterns are lost).

**Mitigation:** Start conservative — classification requires human confirmation until the Steward achieves 90% accuracy over 50 classifications. The `/gift` command always shows the developer what's being proposed before packaging. False positives are annoying but harmless; false negatives are caught by the Rule of Three (if the improvement is truly generic, other projects will discover it independently).

### 13.3 Merge Conflicts in Structured Content

**Risk:** Three-way merges of YAML frontmatter and markdown prose produce confusing artifacts. YAML merges at the file level lose field-level precision. Markdown merges produce unreadable conflict markers in prose.

**Mitigation:** YAML merges operate at the field level (each frontmatter field is an independent LWW-Register). Markdown merges present section-level diffs with "keep mine" / "take theirs" / "merge manually" options rather than git-style conflict markers. The Steward provides narrative context for each conflict: "This section diverged because of ADR-0015 (HIPAA review threshold)."

### 13.4 Git Notes Ecosystem Limitations

**Risk:** Git notes are invisible in GitHub, GitLab, and most web UIs. Lineage metadata stored only in notes is effectively hidden.

**Mitigation:** Notes are optional and supplementary. The manifest file, SQLite tables, and git trailers are the primary stores — all visible through standard tooling. Git tags marking sync points are universally visible. Notes serve only as a local convenience for `git log`-based queries.

### 13.5 Hyrum's Law (Implicit Dependencies)

**Risk:** As derived projects build on template internals, even minor template refactoring breaks downstream consumers. Any observable behavior becomes a depended-upon contract.

**Mitigation:** The stable/extensible interface boundary (§9.2) makes explicit what is safe to depend on. The compatibility declaration in the manifest forces projects to declare their dependencies. The consumer-driven contract check (§9.4) catches breaking changes before they propagate. But the fundamental tension remains — maintaining a stable interface requires ongoing discipline.

### 13.6 Single-Developer Bottleneck

**Risk:** All lineage operations flow through one developer. Gift review, sync decisions, and fork classifications are all manual approval gates.

**Mitigation:** The graduated autonomy model reduces the approval burden over time. At target autonomy levels, the Steward handles routine syncs and classifications autonomously, surfacing only novel or uncertain decisions. The system is designed so that adding additional developers later requires only expanding the `custodian.primary_human` field to a list and adding approval policies — no architectural changes.

### 13.7 Stale Manifests

**Risk:** The manifest drifts from reality if the developer makes changes without going through lineage-aware workflows (e.g., manually editing agent files without committing through git hooks).

**Mitigation:** The Sentinel function runs manifest validation on every `/ship` invocation and every `pre-push` hook. The `/lineage --validate` command explicitly reconciles manifest against file system state. The manifest is a derived artifact — it can always be rebuilt from the git history + lineage event log if it becomes corrupted.

---

## 14. Phased Implementation Roadmap

### Phase 1: The Chronicler Awakens (Weeks 1–3)

**Goal:** Establish lineage tracking with zero workflow disruption.

**Deliverables:**
- [ ] `agents/steward.md` — Agent definition with persona and responsibilities
- [ ] `framework-lineage.yaml` — Manifest file with full schema (§5.1)
- [ ] `scripts/lineage/init.py` — Initialize lineage for existing projects
- [ ] `scripts/lineage/manifest.py` — Manifest CRUD operations
- [ ] `scripts/lineage/drift.py` — Basic drift scanning (file hash comparison)
- [ ] `.claude/commands/lineage.md` — `/lineage` command (status + validate)
- [ ] SQLite schema extensions (§6.1) — lineage_nodes, lineage_file_drift tables
- [ ] `.claude/custodian/lineage-events.jsonl` — Event log with FORK event

**Autonomy level:** L2–L4 (observe, report, recommend).

**Success criteria:** Developer can run `/lineage` and see a clear picture of drift between project and template. No automated actions.

**Standalone value:** "How out of date am I?" becomes a one-command answer instead of a manual diff exercise.

---

### Phase 2: The Sentinel Detects (Weeks 4–6)

**Goal:** Automated drift detection and lineage event recording.

**Deliverables:**
- [ ] `.githooks/post-commit` — Update drift counts on framework-file changes
- [ ] `.githooks/pre-push` — Validate manifest consistency
- [ ] Version vector comparison logic (§4.2) — behind/ahead/diverged detection
- [ ] Divergence distance calculation and speciation threshold alerts (§4.3)
- [ ] ADR template extension with `Lineage Impact` section (§11.2)
- [ ] Agent YAML frontmatter extension with `lineage:` block (§5.1)
- [ ] Speciation Alert mechanism when *D* exceeds threshold

**Autonomy level:** L4–L5 (detect and alert, execute documentation if approved).

**Success criteria:** The Steward proactively alerts the developer to drift on every `/ship` invocation. Lineage events are automatically recorded.

**Standalone value:** Framework drift becomes visible and measurable, preventing the "I forgot to back-propagate" problem.

---

### Phase 3: The Herald Propagates (Weeks 7–10)

**Goal:** Bidirectional change flow with Voucher-based propagation.

**Deliverables:**
- [ ] `scripts/lineage/voucher.py` — Voucher CRUD and validation
- [ ] `scripts/lineage/sync.py` — Three-way merge with pinned-trait awareness
- [ ] Change classification system (§7.2) — heuristic + human confirmation
- [ ] `.claude/commands/gift.md` — `/gift` command for upstream contribution
- [ ] `/ship --sync-upstream` flag for downstream sync
- [ ] Pinned traits system (§5.1) — with ADR-linked rationale
- [ ] SQLite `lineage_sync_log` table
- [ ] Git trailers for attribution on lineage-relevant commits
- [ ] Git tags for sync points (`lineage/sync-*`, `lineage/gift-*`)

**Autonomy level:** L5–L6 (execute sync if approved, classify with veto option).

**Success criteria:** Developer can run `/gift` to contribute an improvement upstream and `/ship --sync-upstream` to pull template updates — both with full Voucher audit trail.

**Standalone value:** Bidirectional improvement flow becomes a supported workflow instead of manual copy-paste.

---

### Phase 4: Attribution and the Improvement Cycle (Weeks 11–14)

**Goal:** Full attribution tracking and ecosystem-level improvement detection.

**Deliverables:**
- [ ] SQLite `lineage_contributions` table with contribution graph queries
- [ ] `/lineage --attribution-report` command
- [ ] Adoption-log extension with `provenance` and `sync_policy` fields (§8.4)
- [ ] Rule of Three lineage dimension (§11.4) — cross-project improvement detection
- [ ] Five source-type attribution system with git trailer conventions (§8.1)
- [ ] Voucher cross-referencing for related improvements
- [ ] Contribution statistics in `/retro` output

**Autonomy level:** L5–L7 (execute attribution autonomously, documentation without pre-approval).

**Success criteria:** Every improvement in the ecosystem has a traceable provenance chain from discovery through adoption to downstream propagation.

**Standalone value:** The framework's institutional memory becomes queryable — "Where did this pattern come from?" has a definitive answer.

---

### Phase 5: Divergence Management and Compatibility (Weeks 15–20)

**Goal:** Full speciation management with compatibility contracts.

**Deliverables:**
- [ ] Soft fork / hard fork classification system (§9.1)
- [ ] Core/extension boundary definition and hash verification (§9.2)
- [ ] Compatibility matrix in SQLite with `/lineage --compatibility` command (§9.3)
- [ ] Consumer-driven contract checking — `can-i-deploy` for template changes (§9.4)
- [ ] Lateral transfer support — cross-project Voucher propagation (§7.5)
- [ ] Full speciation event lifecycle (derived → soft-fork → hard-fork)
- [ ] Ecosystem health dashboard in `/meta-review` output

**Autonomy level:** L6–L8 (execute routine operations autonomously, flag novel decisions).

**Success criteria:** The Steward can answer "If I release template v3.0.0, which derived projects can absorb it safely?" with a concrete compatibility report.

**Standalone value:** The Sovereign Architect becomes a self-improving ecosystem where every derived project makes every other project stronger. The lineage tree is the framework's institutional genome — every improvement, every divergence, every speciation event is tracked, attributed, and available for the benefit of the whole.

---

## Appendix A: Glossary

| Term | Definition |
|------|-----------|
| **Adapted** | A template change modified for project-specific context |
| **Chronicler** | Steward sub-function: maintains lineage graph and attribution chains |
| **Divergence Distance (D)** | Total framework-level changes separating a project from the template's current state |
| **Gift** | An improvement contributed from a derived project to the template |
| **Hard Fork** | A breaking specialization that creates permanent incompatibility in a specific area |
| **Herald** | Steward sub-function: manages change propagation and Voucher lifecycle |
| **Improvement** | A generic discovery in a derived project that benefits all projects |
| **Lateral Transfer** | Cross-project Voucher propagation (biological: horizontal gene transfer) |
| **Lineage ID** | UUID assigned at fork time, uniquely identifies a project across the ecosystem |
| **Pinned Trait** | An intentional divergence from the template, documented with an ADR reference |
| **Project** | A project-specific customization that should never propagate |
| **Sentinel** | Steward sub-function: detects drift and validates manifest integrity |
| **Serial** | Monotonic counter preventing concurrent manifest corruption |
| **Soft Fork** | A backward-compatible specialization that maintains interoperability |
| **Speciation** | When a derived project diverges enough to warrant formal fork classification |
| **Speciation Threshold** | Configurable divergence distance that triggers a Speciation Alert (default: 25) |
| **Steward** | The framework custodian agent — institutional memory and circulatory system |
| **Template** | A change originating from the upstream canonical framework |
| **Version Vector** | Distributed systems concept tracking upstream/local change counts for drift detection |
| **Voucher** | Self-contained JSON packet packaging a single improvement for propagation |

## Appendix B: Example `/lineage` Output

```
╔══════════════════════════════════════════════════════════╗
║  LINEAGE STATUS — healthcare-compliance-framework       ║
╠══════════════════════════════════════════════════════════╣
║  Version:    3.1.0+upstream.2.1.0                       ║
║  Type:       derived                                    ║
║  Lineage ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890      ║
╠══════════════════════════════════════════════════════════╣
║  DRIFT                                                  ║
║  Status:     diverged                                   ║
║  Distance:   D=14 (5 upstream, 12 local, last sync: 3)  ║
║  Threshold:  25 (56% to speciation)                     ║
╠══════════════════════════════════════════════════════════╣
║  PINNED TRAITS (2)                                      ║
║  • .claude/agents/architect.md (soft) — ADR-0015        ║
║  • .claude/rules/security-baseline.md (hard) — ADR-0018 ║
╠══════════════════════════════════════════════════════════╣
║  PENDING                                                ║
║  • 3 template updates available (2.1.0 → 2.3.0)        ║
║  • 2 IMPROVEMENT changes ready for /gift                ║
╠══════════════════════════════════════════════════════════╣
║  LAST SYNC: 2026-02-15 (21 days ago)                    ║
║  LAST GIFT: 2026-02-20 (16 days ago) — accepted         ║
╚══════════════════════════════════════════════════════════╝
```

## Appendix C: Decision Record

This architecture document should be adopted via ADR following the framework's existing conventions. The ADR should reference this document, record the decision to adopt the Steward role, and specify the starting phase. Subsequent phase transitions should each have their own ADR documenting the evidence for advancement.

---

*The Steward does not own the framework. It tends the framework — tracking its genealogy, flowing its improvements, crediting its contributors, and managing the graceful speciation of a growing ecosystem. Every derived project is both student and teacher. The template is both parent and learner. Self-improvement serves collective benefit.*
