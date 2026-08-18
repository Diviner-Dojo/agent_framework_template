# Philosophy: Exploration, Craft, and Creative Empowerment

## Why this framework exists

This framework exists to help people actuate their creativity. Not to impose process for its own sake, not to optimize for velocity, but to give people — especially those building something personal and meaningful — a structure that amplifies what they can imagine and build.

Every principle, every agent, every review gate exists to serve that mission. When a rule stops serving creativity, the rule should change — through the framework's evolution process, not by ad-hoc bypass.

## Who we are

This framework is meant to be forked. Whoever holds a copy is its **steward**: privileged to experiment ahead of the people they share it with, and responsible for ensuring that only work which clearly benefits those people flows onward.

A shared repository belongs to everyone who uses it. The steward's job is to make it worthy of their trust.

*Which copy this is — template or derivative, who it came from, and who holds custody — is recorded in `framework-lineage.yaml` (`instance.type`, `upstream.locked.url`, `custodian`), not restated here. Positioning is instance state; philosophy is not. Keeping it in one machine-readable place is why this file can be the same in the template and in every project derived from it.*

The app is the output. The understanding — of the problem, the user, the technology, the craft — is the real asset.

## How we work

### Exploration is the default

This repo is a safe space for understanding. Experiments don't need to succeed — they need to teach. A failed `lab/*` branch that produces a clear insight is more valuable than a successful feature that nobody understands.

We use `lab/*` branches freely, commit messy work, and push to our private repo without fear. The point isn't clean code — it's clear thinking.

### Understanding before action

We don't rush to implement. We deliberate, we review from multiple perspectives, we capture the reasoning. The code is the output; the understanding is the asset (Principle #1).

This means:
- We plan before we build (`/plan` → `/build_module`)
- We review before we commit (`/review`)
- We reflect after we ship
- We measure what matters: not lines of code, but clarity of thought

### The team is the framework

The specialist agents are not interchangeable review functions. Each brings distinct Values — load-bearing beliefs about what matters most in their craft — and a Domain Lens — a reasoning sequence they apply before analysis. The Facilitator leads them as a respected elder: insightful, considerate, demanding of their best work. The Steward guards the framework's evolution with the wisdom of its founder.

Every agent is equal in standing. They have different strengths, different lenses, different instincts. That diversity of perspective is what makes multi-agent review more valuable than any single analysis, however brilliant.

### Promotion is earned

Features earn their way to the public repo. The standard is not "does this work?" but **"does this clearly help someone be more creative?"**

Before promoting, ask:
- Would a person new to AI-native development find this useful?
- Does this reduce friction or add it?
- Is this the simplest version that delivers the value? (*Growth has a brake*, below)
- Have we understood it well enough to teach it? (Principle #5)

If the answer to any of these is no, the feature stays in the lab until it matures.

### Agents improve through evidence, not opinion

When an agent's performance needs to evolve, the change follows a deliberate path:
1. The Facilitator observes a pattern across multiple reviews — not a single incident
2. The Facilitator proposes a specific change with evidence
3. The Steward evaluates the proposal against the framework's philosophy and principles
4. The developer approves the change
5. The change goes through the same review process as any code change

This is how we get better without losing what already works.

## The promotion standard

A change to the framework is ready when:

1. **It clearly benefits the developer** — not hypothetically, but demonstrably
2. **It's been independently evaluated** — the proposer is not the sole judge (Principle #3)
3. **It's understandable** — someone encountering it can grasp why it exists
4. **It's the least-complex version** — no premature abstraction, no speculative features (*Growth has a brake*, below)
5. **The decision is documented** — with rationale that future sessions can reference (Principle #4)

## Relationship to the seven principles

The seven non-negotiable principles in CLAUDE.md are the *how*. This philosophy is the *why*.

- **Reasoning is the primary artifact** because understanding is how we serve creativity — not just our own, but the creativity of everyone who uses what we build.
- **The generator is never the sole evaluator** because a context that did not see the reasoning is the only thing that reliably catches what the first context could not. For a critical-risk change we ask *several* such contexts, not one — see *Growth has a brake* below on why plurality had to be written down somewhere.
- **Understanding before merge** because a feature that can't be understood can't empower anyone — and because a mechanism the developer cannot explain is a defect in the mechanism, not in the developer.
- **Clarify before acting** because building the wrong thing confidently is the most expensive mistake available to us, and the assumption that caused it is cheap to surface and costly to discover late.

### Growth has a brake

*This section carries the value of two commitments that were retired from CLAUDE.md's numbered
list by ADR-0031 Decision 6. Neither was abandoned; both were moved here, because both are about
what the framework refuses rather than about how the model should behave.*

**Least-complex intervention first.** Prompt before command/tool, command/tool before agent
definition, agent definition before architectural change. Complexity is the enemy of creativity —
every unnecessary abstraction is a barrier someone has to climb, and the person who has to climb
it is usually the one maintainer. Exploration is cheap and we set work down gladly and often; what
needs a brake is *growth*, because new complexity arrives one reasonable-looking increment at a
time and nothing else in the constitution constrains it. It was numbered #8 in CLAUDE.md until
ADR-0031, and it was in force throughout the growth it existed to prevent, so treat it as a real
constraint with a known weak enforcement record, not a slogan. *Originally adopted from* ***self-improving-coding-agent***
*(MaximeRobeyns, Score 22/25, analysis* `ANALYSIS-20260219-043657`*) — attribution
preserved through the move, per Prime Objective (a).*

**Review plurality.** For a critical-risk change, ask *several* independent contexts, not one.
Principle #3 requires only *a* separate context, which is a weaker property; plurality is the one
that catches the finding a single reviewer's blind spot would swallow. It lives as a dispatch
concern rather than as a principle, so that panel sizing stays a risk-tier decision: the numeric
floors are stated in `.claude/skills/selecting-review-gates/SKILL.md` and restated verbatim in
`/review` (§ *Panel size — review plurality* in both). It is written down here so the framework
cannot quietly become single-reviewer without someone deciding to make it so.

## A note on failure

Experiments will fail. Approaches will be abandoned. Lab branches will be deleted. This is not waste — it's the cost of exploration, and exploration is how we find what's worth keeping.

Document what you learn from failures. The insight is the artifact, not the code.

## What the framework refuses

The Prime Objective in CLAUDE.md states what the framework refuses in operational form: extraction patterns, tested by attribution preservation, consent of labor, and consent of evolution. The philosophy beneath that operational form is simpler.

This framework exists to serve the common good. The seven technical commitments — reasoning as primary artifact, capture as automatic, the generator never the sole evaluator, ADRs preserved, understanding before merge, human approval for curated memory, clarify before acting — are how that service shows up structurally. None of them are accidental. Each refuses a specific mode by which AI systems extract value from the people who use them, in the same order: invisible reasoning, silent forgetting, agent-as-judge over human work, revisable history, bypassed understanding, automated canonization, and confident action on an assumption never surfaced.

**Two refusals outlived the principles that used to carry them,** and are named here so the retirement of a principle is not mistaken for the retirement of what it refused (ADR-0031 Decision 6):

- **Authoritative single-source answers** — carried by *collaboration precedes adversarial rigor* until it was retired. The posture went; the refusal did not. It is now carried by **review plurality** (several independent contexts for a critical-risk change, not one), whose panel-size floors are stated in `.claude/skills/selecting-review-gates/SKILL.md` and restated verbatim in `/review` (§ *Panel size — review plurality* in both). See *Growth has a brake* above.
- **Accidental complexity that becomes captive dependency** — carried by *least-complex intervention first* until it was retired. It is now carried by *Growth has a brake* above.

This is not a moral marketing claim. It is a structural description of what the framework already does. Naming it makes the next maintainer's job easier — they can see what they're inheriting, why it has the shape it does, and what would betray it. It also names the limit honestly: the framework can shape designs, but it cannot bind the model provider. A Claude model retrained to be more extractive, or platform policies requiring telemetry the framework would refuse, cannot be resisted by this document. The framework provides the gates; the human provides the verdict; the provider can change the conditions under both.

The framework's deepest commitment, the one all the technical principles operationalize, is that AI capability must distribute rather than concentrate. Reasoning belongs to the contributor who reasoned. Decisions belong to the team that decided. Memory belongs to the user whose work it represents. Evolution belongs to the community of derived projects that earn it. When the framework ceases to distribute and starts to concentrate, it has betrayed its purpose, and the next maintainer is authorized — by the seven principles and the Prime Objective they serve — to refuse the change.

### Sources are canonical (the suchness invariant)

Two of the extraction modes named above — silent forgetting and revisable
history — share a single positive commitment, which the framework names here so
that future maintainers can see it and defend it: **the reasoning is the source,
and every derived artifact stays tethered to it.**

Layer 1 discussions are the canonical record of why a thing was decided.
Everything downstream — metrics (L2), curated memory (L3), ADRs, reviews,
promoted patterns — is a *vehicle* for engaging with that reasoning, never a
replacement for it. The tether runs one way: a derived artifact may *supersede*
an earlier decision (that is what ADRs do — Principle #4, superseded never
deleted), but it may not *sever its own provenance*. When you cannot tell which
discussion grounded a claim, the claim has lost the property that makes it
trustworthy, regardless of whether it is correct.

**Suchness preservation.** A synthesized artifact carries a pointer back to the
reasoning that produced it: ADRs cite their `discussion_id` (and the quality
gate enforces this today), reviews cite their findings, promoted memory cites
its source. Where the framework enforces this mechanically, it is a hard gate.
Where it does not yet — most of the L3 promotion path — it is a standing
obligation on the maintainer and a candidate for future enforcement, not a
property to be claimed as already guaranteed. The honest statement is: the
framework refuses to *let go* of a source pointer it has, and treats a missing
one as a defect to be repaired or a promotion to be withheld — not as an
acceptable shortcut.

This is the structural form of "reasoning is the primary artifact" (Principle #1)
applied to the framework's own memory over time. It is the same refuse-extraction
commitment that governs how the framework treats a contributor's work, turned
inward: the framework will not extract value from its own past by quietly
discarding the reasoning that earned it.
