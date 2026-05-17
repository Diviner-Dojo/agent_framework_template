---
adr_id: ADR-0015
title: "Prime Objective: serve contributors and users; refuse extraction patterns"
status: accepted
date: 2026-05-16
decision_makers: [steward, architecture-consultant, docs-knowledge, independent-perspective, security-specialist, facilitator]
discussion_id: DISC-20260516-062518-framework-purpose-and-backflow-deliberation
supersedes: null
risk_level: high
scope: framework
confidence: 0.84
tags: [philosophy, prime-objective, refuse-extraction, framework-evolution, cross-instance, propagation]
---

## Context

The framework's eight Non-Negotiable Principles describe operational commitments (reasoning as primary artifact, capture automatic, collaboration before adversarial rigor, independence, ADRs preserved, education gates, human approval for promotion, simplicity). Each principle is mechanically testable in code review.

What the principles do not name is the common root they share. Examination of all eight reveals that each is a structural expression of one underlying claim: the framework serves contributors and users, and must never accumulate value at their expense. The framework has had a quiet political theory since v1 — small-d democratic, user-sovereign, anti-paternalist, refusing extraction by structural design rather than by intention. The political theory is implicit in the architecture; it has never been named in a document that specialists or future maintainers consult.

The developer asked whether the framework should formally adopt the common-good claim as a written first principle, and how derived projects should flow learnings back to the canonical template without the cross-instance mechanism itself becoming an extraction pattern. The /deliberate session DISC-20260516-062518 surfaced three paths and preserved genuine dissent between two camps on where the operational form should live. The developer's subsequent observation — that the existing eight principles already serve a common root — opened a fourth path that the deliberation did not name: restructure CLAUDE.md to make the hierarchy explicit, with a Prime Objective above the eight rather than alongside them. This ADR records the adoption of that fourth path.

Two further forces shaped the decision:

1. **Longevity orientation.** The framework is intended to outlive the current developer's stewardship. Without the prime objective named, future maintainers must re-derive what the framework is for from the eight technical principles alone, and over enough hands and enough years, the re-derivation will diverge.

2. **Cross-instance propagation.** Per `documentation_policy.md`, framework-scoped ADRs receive an entry in `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md`. Future projects spawned from this template will inherit the Prime Objective from birth, without any per-project action required.

## Decision

Adopt **Path 4 — Prime Objective above the eight Non-Negotiable Principles**.

**Changes:**

1. **CLAUDE.md**: a new "Prime Objective" section is added above "Non-Negotiable Principles". The Prime Objective states the framework's purpose (serve contributors and users; never accumulate value at their expense) and provides a three-part operational test (attribution preservation, consent of labor, consent of evolution). Each of the existing eight principles receives a one-sentence italic annotation showing how it serves the Prime Objective.

2. **PHILOSOPHY.md**: a new section "What the framework refuses" extends the founder's voice with the positive moral frame — the common-good claim as the purpose the technical principles already operationalize. The section names the model-provider limit honestly and explicitly authorizes future maintainers to refuse changes that would centralize.

3. **REVIEW.md**: a one-line reference is added pointing specialists to the Prime Objective when reviewing designs that touch attribution, consent of labor, or framework evolution.

4. **FRAMEWORK_CHANGELOG.md** (`~/.claude/shared-memory/`): a new entry propagates the Prime Objective to all derived projects pulling from the shared-memory layer.

**Operational semantics:**

- The Prime Objective is enforced human-mediated at every gate. The framework provides the gates; the human provides the verdict.
- Specialists may cite the Prime Objective as a named instrument in findings (analogous to citing "violates Principle #4 — no independent evaluator").
- The Prime Objective does not subsume any of the eight principles. The eight remain testable, citable, and operative as before.
- The three-part test (a/b/c) is the operational shape of the Prime Objective. Findings of the form "violates Prime Objective: extraction by test (b)" are expected.

## Alternatives Considered

### Path 1: CLAUDE.md Principle #9 alongside the eight
- **Pros**: Operational injection via system prompt. Camp A's argument from the deliberation. Smallest diff.
- **Cons**: A non-mechanically-enforceable principle placed alongside mechanically-enforceable ones risks demoting the eight by association — the framework would teach future agents that "principles" is the category including this aspirational one. Camp B's concern.
- **Reason rejected**: The developer's structural insight ("the other principles serve that first principle") revealed that the new commitment is not a peer of the eight but their unifying root. Adding as peer would be category-confused.

### Path 2: PHILOSOPHY.md "Stance" section only, no CLAUDE.md change
- **Pros**: Categorical clarity preserved. Camp B's argument. Avoids the demotion risk entirely.
- **Cons**: Empirically, PHILOSOPHY.md is rarely cited in specialist outputs. A commitment that lives only in PHILOSOPHY.md is decorative. Camp A's concern.
- **Reason rejected**: The longevity argument requires operational legibility to specialists, not just to humans reading the philosophy. PHILOSOPHY.md alone does not propagate into the framework's reasoning surface.

### Path 3: CLAUDE.md meta-rule delegating to PHILOSOPHY.md Stance section
- **Pros**: Operational + categorical. Allows the named anti-patterns to grow in PHILOSOPHY.md without amending CLAUDE.md per addition.
- **Cons**: Introduces a coupling between two documents that must stay in sync. Specialists must read both to apply the meta-rule. Indirection.
- **Reason rejected**: The user's insight that the eight principles already serve the prime objective made the direct restructure (Path 4) more honest than the delegation. The unifying claim should be visible in the same document as the principles it unifies.

### Path 4 (chosen): Prime Objective above the eight
- **Pros**: Operational (CLAUDE.md is in every specialist's system prompt). Categorical (Prime Objective is above the eight, not alongside, so technical principles retain their bite). Honors the developer's structural insight that the eight already serve a common root. Single source of truth. Cross-instance propagation via FRAMEWORK_CHANGELOG.md.
- **Cons**: Larger diff than Path 1. Derived projects with customized CLAUDE.md will have more to merge when pulling this update. Self-certification of virtue is a known failure mode — the framework's claim must be backed by the structural commitments below it to avoid becoming hollow rhetoric.
- **Reason chosen**: The structural elegance — naming what was already true rather than appending a new claim — matches the framework's existing discipline of capturing what is rather than what should be.

## Consequences

### Positive

- **Specialists gain a named instrument.** Findings that touch attribution, consent, value flow, or framework evolution can be cited against the Prime Objective and its three-part test, rather than reasoned from multiple of the eight principles ad hoc.
- **Future maintainers inherit the framework's purpose explicitly.** The longevity case is served — the next person to maintain this framework will not have to re-derive the unifying claim from the eight principles in isolation.
- **Cross-instance propagation is automatic.** Per `documentation_policy.md` and the `~/.claude/shared-memory/FRAMEWORK_CHANGELOG.md` pattern, derived projects pulling from shared-memory will inherit Principle Zero. This is the lever that converts a single writing into framework-wide policy across all spawned instances.
- **Future ADRs gain an anchor.** Any future ADR that touches value-flow, telemetry, federation, or cross-project sharing can cite "per the Prime Objective" rather than re-deriving the anti-extraction stance each time.
- **The framework's quiet political theory becomes legible.** Outside readers — potential adopters, contributors, forks, regulators — can now read what the framework is for, not just how it operates.

### Negative

- **CLAUDE.md restructure increases diff complexity for derived projects.** Projects with customized CLAUDE.md will need to merge a structural change rather than an append. The framework lineage manifest's `pinned_traits` mechanism may need to track this.
- **The commitment cannot be mechanically enforced.** Enforcement is human-mediated at every gate. Bad-faith use of the framework cannot be prevented by the principle; only friction-tested.
- **The Anthropic-as-threat limit is real.** The Prime Objective is operationally bounded by the model provider. A Claude model retrained to be more extractive, or platform policies requiring telemetry the framework would refuse, cannot be resisted by this ADR. This limit is named in PHILOSOPHY.md and acknowledged in CLAUDE.md.
- **Residual extraction risk in cross-instance learning cannot be zeroed.** Per the Steward's deliberation finding, attribution discipline mitigates but does not eliminate extraction risk in any backflow mechanism. The Prime Objective sets the constraint; downstream mechanism design (voucher/gift, future cross-instance memory) must satisfy it.

### Neutral

- **PHILOSOPHY.md grows by one section.** The "What the framework refuses" addition extends the existing two-doc structure (CLAUDE.md = how, PHILOSOPHY.md = why) without inventing a third top-level doc.
- **The eight existing principles are unchanged in meaning.** Each retains its original text and operational semantics. The italic annotations are additive — they show how each serves the Prime Objective without altering what each requires.
- **The "common good" framing in the developer's original phrasing is preserved in PHILOSOPHY.md.** The negative/operational form ("refuse extraction patterns") lives in CLAUDE.md where specialists will cite it; the positive moral frame lives where humans reading the framework will encounter it. Neither is lost.

## Out of Scope

This ADR adopts the Prime Objective. It does not:

- Wire the voucher/gift cross-instance backflow mechanism (specified in `docs/STEWARD_ARCHITECTURE.md §1.2`, not yet implemented). That is downstream work satisfying this ADR's constraint.
- Address the confabulation problem (specialists confidently misrepresenting framework-wide claims due to single-instance reasoning). Independent-perspective named this as needing a separate structural fix at dispatch time. Reserved for a future ADR.
- Bind the model provider. The framework documents its values; cannot enforce them against Anthropic policy changes; this limit is acknowledged in both CLAUDE.md and PHILOSOPHY.md.
- Tighten sanitisation policy beyond what the existing PreToolUse hook provides. Per the deliberation's security finding, sanitisation lives at the assert_fact call site (Phase 1 spec scope), not here.

## Linked Discussion

See: `discussions/2026-05-16/DISC-20260516-062518-framework-purpose-and-backflow-deliberation/`

The deliberation transcript captures Round 1 specialist proposals (steward, architecture-consultant, docs-knowledge, independent-perspective as Research Scout, security-specialist) and the facilitator synthesis preserving the genuine Camp A vs Camp B dissent. The developer's subsequent observation — that the existing eight principles already serve a common root — is captured in the SESSION-2026-05-16-narrative.md artifact at the project root (uncommitted at the time of this ADR).
