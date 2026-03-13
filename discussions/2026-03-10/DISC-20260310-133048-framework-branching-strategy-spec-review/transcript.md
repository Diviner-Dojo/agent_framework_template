---
discussion_id: DISC-20260310-133048-framework-branching-strategy-spec-review
started: 2026-03-10T13:30:58.897517+00:00
ended: 2026-03-10T13:36:42.161561+00:00
agents: [architecture-consultant, docs-knowledge, facilitator, independent-perspective]
total_turns: 5
---

# Discussion: DISC-20260310-133048-framework-branching-strategy-spec-review

## Turn 1 — facilitator (evidence)
*2026-03-10T13:30:58.897517+00:00 | confidence: 0.8*
*tags: context-brief*

## Request Context
- **What was requested**: Create a branching strategy for maintaining a private development fork of the public framework, enabling experimentation and clean promotion of polished features back to the public repo
- **Files/scope**: Git workflow, framework-lineage.yaml, new BRANCHING.md guide; no source code changes
- **Developer-stated motivation**: Developer wants to experiment with framework features (e.g., building a code review apparatus emulating Anthropic's enterprise Code Review) without polluting the public repo, while having a clear path to promote successful work
- **Explicit constraints**: Developer is new to GitHub — strategy must be simple with explicit commands; solo developer; no CI/CD; leverage existing lineage tracking

---

## Turn 2 — architecture-consultant (critique)
*2026-03-10T13:34:12.199677+00:00 | confidence: 0.82*
*tags: spec-review, architecture*

## Verdict: APPROVE WITH CHANGES (confidence: 0.82)

### Blocking Findings
1. **promote/* push workflow requires clarification** (High): gh pr create --head promote/review-apparatus works because branch is pushed directly to public repo, but spec must clarify: (a) developer needs push access to public repo, (b) promote/* branches are visible on public repo until merged/deleted, (c) add cleanup step: git push public --delete promote/review-apparatus after merge. Also recommend renaming when pushing: git push public promote/review-apparatus:feature/review-apparatus to match public repo conventions.

2. **framework-lineage.yaml guaranteed merge conflict** (Medium): Both repos have this file with different content (type: template vs type: derived). Every upstream sync will produce a merge conflict. Recommend adding to .gitattributes with merge=ours strategy in private repo, or add to pinned_traits.

3. **upstream.locked fields unpopulated** (Medium): After rm + init_lineage.py, upstream.locked.url and commit_hash remain null. The private repo's lineage tracking has no reference point. Either extend init_lineage.py with --upstream-url/--upstream-commit flags, or add manual step to edit manifest after init.

### Advisory Findings
4. **ADR-0003 needed** (Medium): Two-repo dual-remote model is an architectural decision requiring an ADR per documentation policy.
5. **promote/* naming inconsistent with public repo conventions** (Low): Public repo uses feature/*, fix/*, docs/* prefixes. promote/* is novel and will appear alongside them.
6. **lab/* vs feature/* distinction may be premature** (Low): Per Principle 8, consider starting with just lab/* and graduating directly to promote/*.
7. **lineage drift has two dimensions** (Info): /lineage tracks framework file drift; git diff public/main tracks content divergence. BRANCHING.md should clarify.

---

## Turn 3 — docs-knowledge (critique)
*2026-03-10T13:34:22.631596+00:00 | confidence: 0.87*
*tags: spec-review, documentation*

## Verdict: APPROVE WITH CHANGES (confidence: 0.87)

### Blocking Findings
1. **ADR-0003 required** (High): Branching strategy is an architectural decision with lasting consequences. Needs ADR per documentation policy, linked to this discussion.

2. **BRANCHING.md must explain WHY, not just WHAT** (High): Each convention must open with a one-paragraph rationale. Example: why cherry-pick over merge for promotion (merge would pull full private history into public repo). Without WHY, conventions feel arbitrary and will be broken under pressure.

3. **Error recovery procedures missing** (High): Spec lists four risks but no recovery actions. Beginner-critical gaps: how to abort a merge conflict (git merge --abort), how to handle accidental public push, git reflog as recovery mechanism, decision framework for when drift is too large.

### Advisory Findings
4. **Cherry-pick SHA duplication gotcha** (Medium): Cherry-picked commits get new SHAs. During next upstream sync, git may try to re-apply them. Need warning and git log --cherry-pick command.

5. **CLAUDE.md lineage section needs dual-remote topology note** (Medium): Current description assumes single upstream. Should acknowledge limitation.

6. **Git remotes concept needs explanation** (Medium): Beginner needs 3-sentence mental model of what remotes are before executing configuration commands.

7. **Branch naming enforcement should be explicitly optional** (Low): Document that wrong prefix does not break anything, with git branch -m rename command.

---

## Turn 4 — independent-perspective (critique)
*2026-03-10T13:34:32.110516+00:00 | confidence: 0.78*
*tags: spec-review, anti-groupthink*

## Verdict: APPROVE WITH CHANGES (confidence: 0.78)

### Blocking Findings
1. **Remote naming 'public' violates universal Git convention** (Blocking): Every tutorial/docs use 'upstream' for source-of-truth remote. Beginner will be confused when external resources say 'upstream' but BRANCHING.md says 'public'. Must rename to 'upstream' or provide strong documented justification.

2. **No sync trigger defined** (Blocking): Strategy assumes regular syncing but specifies no trigger. Without forcing function, developer will not sync until problems appear. Must state: 'Before opening any promotion PR, first sync from upstream.'

### Advisory Findings
3. **promote/* layer may be unnecessary** (Advisory): Squash-merge on public repo achieves same history cleanliness. Push feature/* directly to public, squash-merge the PR. Saves one branch, two commands, one concept.

4. **lab/* vs feature/* needs concrete examples** (Advisory): Abstract definitions will not survive real workflow. Include 2-3 examples of what makes each type.

5. **Lineage tracking role in private fork undefined** (Advisory): Does developer run /lineage in private fork? Public clone? Both? pinned_traits guidance needed for beginners.

6. **No branch cleanup policy** (Advisory): Accumulated stale branches create confusion. Specify: lab/* deleted when experiment concludes, promote/* deleted after PR merges.

### Alternatives Surfaced
- **Single-repo alternative** should be presented as Option A per Principle 8 (least-complex intervention first). Two-repo is justified only for cloud backup of lab work. Developer should consciously choose, not inherit the more complex strategy by default.
- **Archive-then-rewrite promotion**: Instead of cherry-picking, rewrite the feature cleanly after lab proves the approach. Eliminates cherry-pick complexity entirely.

---

## Turn 5 — facilitator (synthesis)
*2026-03-10T13:36:42.161561+00:00 | confidence: 0.88*
*tags: synthesis*

## Request Context
- **What was requested**: Create a branching strategy for maintaining a private development fork of the public framework, enabling experimentation and clean promotion of polished features back to the public repo
- **Files/scope**: Git workflow documentation, framework-lineage.yaml configuration, BRANCHING.md guide, ADR-0003
- **Developer-stated motivation**: Developer wants to experiment with framework features (e.g., code review apparatus emulating Anthropic's enterprise Code Review) without polluting the public repo, with a clear path to promote successful work
- **Explicit constraints**: Developer is new to GitHub; solo developer; no CI/CD; leverage existing lineage tracking

## Synthesis

Three specialists reviewed the spec (architecture-consultant, docs-knowledge, independent-perspective). All returned APPROVE WITH CHANGES. Key changes incorporated:

### Blocking findings addressed:
1. **Remote naming changed from 'public' to 'upstream'** (independent-perspective): Aligns with universal Git convention. Every tutorial and Stack Overflow answer uses 'upstream' for the source repo.
2. **Sync trigger rule added** (independent-perspective): Mandatory sync before any promotion attempt. Monthly sync cadence for drift prevention.
3. **promote/* layer eliminated** (architecture-consultant + independent-perspective): Replaced with direct push of feature/* branches to upstream + squash-merge on PR. Eliminates one branch namespace, two commands, and the cherry-pick SHA duplication problem.
4. **Error recovery procedures added** (docs-knowledge): Merge conflict resolution, accidental push recovery, git reflog for lost branches, nuclear restart option.
5. **framework-lineage.yaml merge conflict prevented** (architecture-consultant): Added .gitattributes merge=ours strategy.
6. **upstream.locked fields populated** (architecture-consultant): Setup workflow now includes populating URL and commit hash.

### Advisory findings addressed:
7. **Rationale (WHY) added for every convention** (docs-knowledge): Each section now explains why the convention exists.
8. **Concrete examples for lab/* vs feature/* distinction** (independent-perspective): Added 4 examples.
9. **Git remotes concept explained** (docs-knowledge): Added conceptual primer in R1.
10. **Branch cleanup policy added** (independent-perspective): R7 specifies deletion rules for lab/* and feature/* branches.
11. **ADR-0003 added to acceptance criteria** (architecture-consultant + docs-knowledge).
12. **Strategy choice documented** (independent-perspective): Single-repo vs two-repo alternatives explicitly evaluated with rationale for choosing two-repo.

### Deferred:
- CLAUDE.md lineage section update (docs-knowledge advisory) — address during implementation
- Documentation policy update re: WHY requirement (docs-knowledge proposal) — consider at next retro

---
