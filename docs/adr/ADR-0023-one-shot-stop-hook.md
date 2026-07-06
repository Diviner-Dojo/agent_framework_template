---
adr_id: ADR-0023
title: "One-shot Stop hook — silent-by-default, intent-queued, allow-list-gated reply injection"
status: accepted
date: 2026-06-12
decision_makers: [orchestrator, security-specialist, steward]
discussion_id: DISC-20260612-d2-pattern1-review
spec_id: SPEC-20260610-205507
supersedes:
scope: framework
risk_level: high
confidence: 0.88
tags: [backflow, hooks, stop-hook, ntfy, notifications, untrusted-input, dan-research-wiki]
---

## Context

The template has no `Stop` hook at all (only PreToolUse/PostToolUse/UserPromptSubmit/
PreCompact/SessionStart). Autonomous and AFK sessions therefore end silently unless the
orchestrator remembers to send an ntfy message in-turn — and there is no mechanism for
"when this session actually stops, tell the developer what happened and what's next."

**Origin (back-flow, SPEC-20260610-205507 decision D2, pattern 1 of 5).** This design is
harvested from **dan_research_karpathy_wiki** (a derived satellite), which built and
hardened it first: wiki sources `tools/stop-hook.py`, `tools/queue-stop-notify.py`,
`tools/state/next-stop-notify.json`, and its `.claude/settings.json` Stop block. The
wiki's key insight (its memory `feedback_stop_hook_must_be_actionable`): a Stop hook
that auto-fires "Claude turn ended" on every stop is non-actionable spam. The fix is an
**explicit intent file**: the orchestrator queues exactly one notification *before*
stopping, describing what finished and what's next; the Stop hook fires it once,
deletes the intent, and stays silent otherwise. Attribution per the Prime Objective
test (a): the wiki repo is credited as the design's origin; the back-flow ledger line
in its `framework-lineage.yaml` flips `owed → delivered` with this ADR.

## Decision

Port the pattern as two scripts plus a developer-applied settings change:

1. **`scripts/stop_hook.py`** — Stop-hook entry point. Reads
   `.claude/hooks/.state/next-stop-notify.json` (a gitignored, per-machine path the
   repo already excludes). Absent → exit 0 silently. Present → send one ntfy
   notification via the existing hardened `scripts/notify.py`, delete the file
   (one-shot), optionally poll for a reply.
2. **`scripts/queue_stop_notify.py`** — CLI that writes the intent file
   (`--title --body --priority --tags --wait --wait-timeout --choices`).
3. **`.claude/settings.json` Stop block — NOT applied by the agent.** The PreToolUse
   validator denies agent edits to settings.json by design; the exact change is parked
   as a draft diff at `docs/drafts/DRAFT-20260612-settings-stop-hook.diff` for the
   developer to apply manually.

### Template adaptations (deliberate deviations from the wiki version)

The wiki's `--wait` path injects the **raw ntfy reply text** into the next prompt
(`decision: block`). In this template that is prohibited: out-of-band replies are
unauthenticated, untrusted input (CLAUDE.md Always-On Invariant; regression ledger
2026-05-26 and 2026-06-07 entries). Adaptations, all load-bearing:

- **Allow-list-only injection.** A waiting intent MUST declare `choices`. Replies are
  matched via `collab_loop.match_choice`; only the **matched canonical label** is
  injected ("Developer ... selected the allow-listed choice: <label>"), never raw
  reply text. A non-matching reply triggers nothing (logged type-free to stderr,
  polling continues). `--wait` without `--choices` is a CLI error; an intent file with
  `wait_for_reply` but no choices sends the notification and **fails closed** (no poll).
- **Single-poller discipline.** The wait path claims the `collab_loop` lockfile
  (`claim_poll_lock`) and stands down within one poll cycle when superseded
  (`owns_poll_lock`), so it can never misvalidate a reply meant for a different
  question's allow-list (the 2026-06-07 reply-misfiling bug class).
- **No-slug + ASCII console invariants.** All error paths print `type(exc).__name__`
  only (never `str(exc)`, which can embed the topic URL — the only auth); all console
  output is plain ASCII (the recurring cp1252 Windows terminal crash class).
- **Wait cap 600 s** (wiki: 3600 s) so the hook's settings `timeout` (660 s in the
  draft diff) genuinely bounds it; a Stop hook that can park for an hour invites
  harness-level kills mid-poll. The 60 s margin budget = one send (10 s HTTP
  timeout) + one in-flight final poll (15 s HTTP timeout) + spawn slack.
- **Intent TTL (4 h).** The hook discards intents older than `INTENT_TTL_SECONDS`
  (stamped `queued_at` by the queue CLI), so a forgotten `STOP_HOOK_DISABLE=1` or a
  crashed session cannot fire a stale gated question into a later, unrelated session.
- **Non-list `choices` fails closed.** A hand-written intent with a string `choices`
  would otherwise iterate into single characters, silently degrading the allow-list.
- **Send-failure short-circuit.** If the notification could not be sent, the hook does
  not poll (no question was delivered, so any "reply" would be stale traffic).

### Residual risks (accepted, from REV-20260613 security review)

- **Slug-as-auth forgery window.** The ntfy topic slug is the only authentication on
  the reply channel (same model as `collab_loop`/`ask_developer`). An attacker who
  learns the slug can publish a string matching a declared choice during the wait
  window — a one-tap gated-action forgery bounded to the developer's own pre-declared
  labels. Mitigations: non-obvious labels for destructive actions, short wait windows;
  the allow-list bounds *influence*, it does not *authenticate*.
- **`fetch_reply` is the deliberately-unsafe primitive.** Allow-list enforcement for
  this hook lives at the caller: every `fetch_reply` result MUST be wrapped in
  `collab_loop.match_choice` before any injection (pinned by the superset-reply and
  non-match tests). ADR-0019's boundary-enforcing `collab_loop.poll/check` remain the
  preferred seams for new code; this hook accepts caller-enforcement because it needs
  a bounded in-process wait and the invariant is regression-tested.
- **First stop wins.** With matcher `""` the first Stop after queuing consumes the
  one-shot intent (subagent stops included). Queue intents immediately before the
  intended stop. Anything that can write the intent file already has in-repo
  authority — the file structures an existing capability, it is not an escalation.

## Consequences

- Autonomous sessions get an actionable end-of-session signal with zero per-turn spam;
  gated decisions can ride the stop boundary with one-tap allow-listed replies.
- The hook is inert until the developer applies the parked settings diff — shipping the
  scripts is behavior-neutral.
- The intent file is per-machine and gitignored; nothing in capture or CI depends on it.
- `STOP_HOOK_DISABLE=1` is a clean kill switch; a disabled run preserves the queued
  intent (it fires on the next enabled stop).
- Tests: `tests/test_stop_hook.py` (18 tests) lock the silent-default, one-shot,
  fail-closed, allow-list, single-poller, no-slug, and ASCII invariants.

## Alternatives Considered

- **Verbatim port (raw reply injection):** rejected — violates the untrusted-reply
  invariant; a phone reply could steer the next prompt with arbitrary text.
- **Reusing `collab_loop.poll` wholesale for the wait path:** rejected for now — `poll`
  is a long-running monitor CLI with its own emit contract; the hook needs a bounded
  in-process wait. It reuses `collab_loop`'s lock + `match_choice` primitives instead,
  so the allow-list and single-poller logic stay single-sourced.
- **Auto-firing Stop notification (the wiki's own first design):** rejected by the
  wiki's documented experience — non-actionable spam.
