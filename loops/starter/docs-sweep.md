---
recipe_id: docs-sweep
title: Documentation drift sweep
contributor: framework (starter)
use_this_when: >
  A docs pass is needed — READMEs, docstrings, or guides may have drifted from the
  current implementation. Good autonomous fit: its work edits docs, not the test/verifier
  surface, so the tamper tripwire stays quiet.
goal: All project documentation reflects the current implementation; stale docs are updated.
success_criteria:
  - id: SC1
    text: The docs build / internal link-check passes (no broken references)
    verify: "python scripts/check_docs.py"   # replace with this project's docs check
    verify_owner: gate
  - id: SC2
    text: Public symbols changed since the last docs update are reflected in the docs
    verify: llm-judge
    verify_owner: checker
termination:
  max_iterations: 6
  no_progress: 2
  no_progress_definition: net-progress
  budget_output_tokens: 120000
max_judge_fraction: 0.5
non_goals:
  - Rewriting docs for unchanged code (keep scope tied to real implementation changes)
  - Editing tests, the quality gate, or coverage config (out of scope for a docs sweep)
anchor_context:
  - README.md
  - docs/
autonomy_level: L1
mandatory_full_review: false
derived_from: null
---

## Why it works
A deterministic link-check (SC1) anchors "done" so the single judge criterion (SC2) cannot
drift the whole contract — exactly the deterministic-first / judge-sparingly discipline the
authoring interview coaches. Scope stays tied to real implementation changes, and because
the work never touches the test/verifier surface, the loop runs without tripping the R5
tamper gate. Ends, like every goal-loop, at goal-met → `/review` → required walkthrough →
human approval (no push, no auto-merge).
