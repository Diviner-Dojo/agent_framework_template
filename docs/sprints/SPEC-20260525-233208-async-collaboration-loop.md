---
spec_id: SPEC-20260525-233208
title: "Async Human-in-the-Loop Collaboration Loop (ntfy) + Uninterrupted-Autonomy Protocol"
type: spec
scope: framework
status: complete
completed_commit: 915c142
risk_level: medium
origin: "agentic_journal — Journal Modes Phase 2 build (2026-05-25), built end-to-end while the developer was away via this loop"
audience: "any project using the AI-Native Agentic Development Framework template"
original_spec_id: SPEC-FRAMEWORK-async-collaboration-loop
captured: 2026-05-25
reviewed_by: [architecture-consultant, security-specialist, qa-specialist]
discussion_id: DISC-20260526-003910-async-collaboration-loop-spec-review
captured_note: >
  Developer-authored spec from agentic_journal, captured verbatim into the template's
  spec registry pending /plan. Conformance gap analysis recorded in the handoff
  HANDOFF-20260525-233208.md. NOT yet through specialist design review — status is
  draft until /plan runs. See the watcher vision (SPEC-20260525-160115) for the
  related deferred autonomous-dispatch surface.
---

> **Capture note (template):** This is a developer-authored framework spec brought
> over from agentic_journal. It is captured here as a tracked `draft` spec; it has
> **not** yet been through `/plan` specialist review. The build plan + conformance
> gaps are in `docs/handoff/HANDOFF-20260525-233208.md`. Build it via `/plan` in a
> fresh session. Reconcile with the existing `scripts/ask_developer.py` (single-topic
> free-text ask) — do not ship two overlapping inbound-ask tools.

## Goal

Let an autonomous coding agent **keep working for hours while the developer is away from the terminal**, surfacing only *gating decisions* to the developer's **phone** (push notification) and receiving **one-tap answers** — so a multi-step build (`/plan → /build_module → checkpoints → quality gate → smoke test → /review → commit → deploy`) proceeds without the developer babysitting the keyboard.

The developer should be able to: walk away, get a buzz on their phone only when a real decision is needed, tap a button to answer, and come back to finished, reviewed, committed, deployed work — plus a clean status of every decision they made.

This spec defines (1) the **ntfy two-way channel**, (2) the **collaboration protocols**, and (3) the **lessons learned** that make autonomy actually *uninterrupted* rather than stall-prone. It is written to be baked into a template project.

## Why this exists (the problem it solves)

Autonomous agents stall at decision points when the human isn't watching. The naive fixes are bad: blocking forever (wastes the human's time), or guessing on guarded actions (dangerous). The fix is a **low-friction, phone-reachable, two-way channel**: the agent asks a crisp question with tap-to-answer choices, *holds only the gated step*, keeps building everything non-gated, and resumes the gated step the instant the answer arrives.

Origin: in the originating project, an entire HIGH-risk multi-file feature (schema migration + LWW sync + new UI module + a new ADR) was specced, built with 5 mid-build checkpoints, quality-gated, emulator-smoke-tested, multi-agent-reviewed, committed, pushed, and deployed to a physical device — **with the developer away the whole time**, answering ~5 questions by tapping buttons on their phone.

---

## Part 1 — The ntfy two-way channel

### Topics (two, not one)

- **MAIN topic** = `$NTFY_TOPIC` — the developer subscribes to this in the ntfy phone app. The agent's outbound (questions, status, completion pings) publishes here.
- **REPLY topic** = `$NTFY_TOPIC-reply` — a *dedicated* topic for answers. Tap-to-answer action buttons POST here. **Why separate:** the agent's own outbound on MAIN would otherwise pollute the answer stream the poller reads. The reply topic keeps "what the developer said" cleanly separable from "what the agent said."

### Three modes (+ one helper)

1. **`ask "<question>" [choiceA choiceB choiceC]`** — publish a question to MAIN with up to 3 **HTTP action buttons**; each button POSTs its label to the REPLY topic. With no choices, it's an open question (developer free-texts a reply).
2. **`poll`** — long-running. Streams developer answers, one line per answer. Run under a background **Monitor** (a persistent process whose stdout lines become agent notifications). Watches **both** the REPLY topic *and* the MAIN topic (see free-text rule below).
3. **`check [duration]`** — **one-shot lookback** (e.g. `check 48h`). Prints any developer message in the window and exits. **This is the single most important resumption primitive** — see Lesson 1.
4. **`say "<title>" "<body>"`** — push a status/ack/completion to MAIN (no answer expected). Used for "received your answer", milestone pings, completion.

### The empty-title free-text rule (non-obvious, load-bearing)

A developer can answer two ways: **tap a button** (POSTs to REPLY) or **type free text in the ntfy app** (which posts to the *subscribed MAIN* topic, NOT the reply topic). So `poll` must watch MAIN too — but it must ignore the agent's *own* outbound on MAIN. Heuristic that works: **the agent always sets a title on its outbound; an empty-title message on MAIN is therefore developer free-text.** Filter MAIN to empty-title messages only.

### Reference implementation (stdlib-only, portable)

Drop this in `scripts/collab_loop.py` (or `tools/`). No third-party deps. Reads config from `.env`.

```python
#!/usr/bin/env python3
"""Two-way ntfy collaboration loop so an autonomous agent can ask the developer
questions on their phone and keep working while they're away.

Modes:
  ask "<question>" [choice1 choice2 choice3]  push a question (tap-to-answer buttons)
  poll                                        stream answers forever (run under a Monitor)
  check [duration]                            one-shot lookback (e.g. check 48h) — RESUME primitive
  say "<title>" "<body>"                      push a status/ack/completion (no answer expected)

REPLY topic = <NTFY_TOPIC>-reply (dedicated, so the agent's own MAIN-topic
outbound never pollutes the answer stream). stdlib-only; reads .env; NEVER
prints the topic value (treat the topic as a secret — see SECURITY).
"""
import json, sys, time, urllib.error, urllib.request
from pathlib import Path

ENV = Path(".env")          # adjust to the project root if invoked elsewhere
POLL_SECONDS = 20

def load_env():
    cfg = {}
    for line in ENV.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        for k in ("NTFY_TOPIC", "NTFY_SERVER", "NTFY_TOKEN"):
            if line.startswith(k + "="):
                cfg[k] = line.split("=", 1)[1].strip().strip('"')
    server = (cfg.get("NTFY_SERVER") or "https://ntfy.sh").rstrip("/")
    topic = cfg.get("NTFY_TOPIC")
    token = cfg.get("NTFY_TOKEN") or None
    return server, topic, (topic + "-reply" if topic else None), token

def _headers(token, extra=None):
    h = dict(extra or {})
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h

def _post_json(server, payload, token):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        server, data=data,
        headers=_headers(token, {"Content-Type": "application/json"}),
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        r.read()

def ask(server, topic, reply_topic, token, question, choices):
    # Use ntfy's JSON publish endpoint so action labels/bodies may contain
    # commas/punctuation (the header-based Actions format 400s on those).
    reply_url = f"{server}/{reply_topic}"
    actions = [
        {"action": "http", "label": c, "url": reply_url, "method": "POST", "body": c}
        for c in choices[:3]
    ]
    hint = ("\n\n(tap a button, or send text to your <topic>-reply topic)"
            if choices else
            "\n\n(reply: send text to your <topic> topic from the ntfy app)")
    payload = {"topic": topic, "title": "ASK", "message": question + hint,
               "tags": ["robot", "question"]}
    if actions:
        payload["actions"] = actions
    _post_json(server, payload, token)
    print("asked OK")

def say(server, topic, token, title, body):
    # Titled message → poll() ignores it on MAIN (empty-title = developer text).
    _post_json(server, {"topic": topic, "title": title, "message": body,
                        "tags": ["robot"]}, token)
    print("said OK")

def _emit(server, topic, since, token, require_empty_title, seen, label):
    try:
        req = urllib.request.Request(
            f"{server}/{topic}/json?poll=1&since={since}", headers=_headers(token))
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"WARN ntfy HTTP {e.code} ({label})", flush=True); return  # never print the topic
    except Exception as e:  # noqa: BLE001 — a poller must never die silently
        print(f"WARN ntfy {type(e).__name__}: {str(e)[:120]}", flush=True); return
    for line in text.splitlines():
        if not line.strip():
            continue
        msg = json.loads(line)
        if msg.get("event") != "message":
            continue
        mid = msg.get("id")
        if mid in seen:
            continue
        seen.add(mid)
        if require_empty_title and (msg.get("title") or "").strip():
            continue  # agent's own titled outbound on MAIN
        print(f"REPLY: {msg.get('message', '').strip()}", flush=True)

def poll(server, topic, reply_topic, token):
    since, seen = str(int(time.time())), set()
    sources = ((reply_topic, False, "reply"), (topic, True, "main"))
    print("INFO collab loop armed (reply buttons + main free-text)", flush=True)
    while True:
        for t, empty_only, label in sources:
            _emit(server, t, since, token, empty_only, seen, label)
        time.sleep(POLL_SECONDS)

def check(server, topic, reply_topic, token, since):
    # One-shot lookback over BOTH topics: catch any answer sent while no Monitor
    # was armed (the infinite poll baselines since=now and would miss it).
    seen, found = set(), []
    for t, empty_only, label in ((reply_topic, False, "reply"), (topic, True, "main")):
        before = len(seen)
        # reuse _emit but capture prints by temporarily wrapping is overkill;
        # inline a minimal variant:
        try:
            req = urllib.request.Request(
                f"{server}/{t}/json?poll=1&since={since}", headers=_headers(token))
            with urllib.request.urlopen(req, timeout=30) as resp:
                text = resp.read().decode("utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"WARN ntfy {type(e).__name__} ({label})", flush=True); continue
        for line in text.splitlines():
            if not line.strip():
                continue
            msg = json.loads(line)
            if msg.get("event") != "message" or msg.get("id") in seen:
                continue
            seen.add(msg.get("id"))
            if empty_only and (msg.get("title") or "").strip():
                continue
            ts = msg.get("time", 0)
            when = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts)) if ts else "?"
            print(f"ANSWER [{label} @ {when}]: {msg.get('message','').strip()}", flush=True)
            found.append(msg)
    if not found:
        print(f"NONE: no developer messages in the last {since}", flush=True)

def main():
    server, topic, reply_topic, token = load_env()
    if not topic:
        print("WARN: NTFY_TOPIC not set in .env", flush=True); return
    mode = sys.argv[1] if len(sys.argv) > 1 else "poll"
    if mode == "ask":
        ask(server, topic, reply_topic, token,
            sys.argv[2] if len(sys.argv) > 2 else "(no question)", sys.argv[3:])
    elif mode == "say":
        say(server, topic, token,
            sys.argv[2] if len(sys.argv) > 2 else "Status",
            sys.argv[3] if len(sys.argv) > 3 else "")
    elif mode == "check":
        check(server, topic, reply_topic, token, sys.argv[2] if len(sys.argv) > 2 else "1d")
    else:
        poll(server, topic, reply_topic, token)

if __name__ == "__main__":
    main()
```

### Harness wiring (Claude Code Monitor tool; generic otherwise)

- Arm the poller with the harness's **persistent background-monitor** primitive (in Claude Code: the `Monitor` tool with `persistent: true`). Each stdout line becomes an agent notification. The agent keeps working; answers arrive as events.
- For a generic agent runtime, any "run a process, stream its stdout lines back as events" mechanism works (e.g. a subprocess whose lines are fed to the model).
- A **second** persistent monitor is useful for *observing real-world results asynchronously* — e.g. a DB/API poller that reports when the feature under test actually produced data in the field. (Originating project: a Supabase poller that reported new rows every 10 min so the agent could confirm on-device behavior without the developer.)

### Configuration (`.env`, gitignored)

```
NTFY_TOPIC=your-random-unguessable-slug   # the only auth — treat like a key
NTFY_SERVER=https://ntfy.sh               # optional; self-host for privacy
NTFY_TOKEN=tk_xxx                          # optional bearer token for ACL'd servers
```

### Security model (do not skip)

- **The topic slug is the only authentication.** Anyone who knows it can read/publish. Treat it like a secret: random slug, in gitignored `.env`, never committed, **never printed to the transcript/logs**.
- **Never echo the topic in error messages.** (Originating bug: an error handler printed `({topic})` and leaked the slug into the transcript. Fix: print a non-revealing source label like `(reply)`/`(main)` instead. The reference impl above already does this.)
- For real privacy, use `NTFY_TOKEN` bearer auth and/or a self-hosted ntfy with access control. The slug-only model is fine for low-sensitivity decision prompts but the *content* of questions is visible to anyone with the slug.

---

## Part 2 — Collaboration protocols (the human-facing rules)

Bake these into an auto-loaded rule (e.g. `.claude/rules/async_collaboration.md`):

1. **Confirm receipt of every answer + state what it unblocked.** After each developer answer, send a short `say` ack: "Got 'Approve' — starting the build now." The developer must never wonder whether their tap registered.
2. **Prefer tap-to-answer over open questions.** One tap beats typing on a phone. Offer 2–3 concrete, mutually-exclusive choices. Reserve open free-text for genuinely open questions.
3. **Hold on gated actions; keep building everything else.** A pending question blocks only the gated step. While waiting, do all non-gated prep (read code, write the next module's tests, draft the ADR). Never proceed on a guarded action (commit to a protected branch, deploy, merge to main) without the answer.
4. **Ping at milestones, not every step.** Checkpoint outcomes, the review verdict, completion, or a real decision — not per-file progress. Over-notifying trains the developer to ignore the channel.
5. **Surface decisions, not just status.** When you make a judgment the developer would want to weigh in on (a spec deviation, a design trade-off), say so explicitly and offer to revisit — don't bury it.
6. **Close the loop cleanly on request.** When the developer says "close the loop," stop all monitors, send a final ack, and **record the closed state in the session-state file** so the next session does not auto-re-arm a loop the developer ended.
7. **No emoji in notification titles.** ntfy titles go in an HTTP header (latin-1). A ✅ in the title throws `UnicodeEncodeError`. Emoji are fine in the *body*; keep titles ASCII.

---

## Part 3 — Lessons learned: keeping work going *without interruption*

These are the concrete, hard-won lessons. Each names the failure it prevents.

### Loop-mechanics lessons

1. **One-shot `check` BEFORE arming `poll` on every resume.** The infinite `poll` baselines `since=now` at launch, so any answer the developer sent *while no monitor was armed* (e.g. between sessions) is **invisible to it forever**. On resume: run `check <window>` first to catch backlog, *then* arm `poll`. Skipping this silently drops answers. **This is the #1 cause of "the agent ignored my reply."**
2. **Watch both the reply topic and main-topic-empty-title.** Free-text typed in the app lands on MAIN, not the reply topic. A reply-only poller misses it. (Empty-title heuristic distinguishes it from the agent's own outbound.)
3. **The topic is a secret — never print it,** including in error handlers (the leak bug above).
4. **Monitors die at session end; the scripts persist on disk.** Keep the loop scripts *outside the repo* (or in `tools/`, gitignored if throwaway) so they survive across sessions, and **re-arm the monitors at the start of each resume** (after the `check` lookback).
5. **Record loop state in the resume anchor.** The session-state file (see below) must say whether the loop is *armed* or *closed*, so the next session neither re-arms a closed loop nor forgets to re-arm an active one.

### Resume-anchor + autonomy lessons

6. **A single resume anchor file is the spine of uninterrupted work.** A `BUILD_STATUS.md` (or equivalent) read at session start and updated before compaction / after each commit. It records: current task state, the branch tip, what's been verified, loop state, and the ordered next-actions. Without it, a compaction or session boundary loses the thread. **It is the difference between "resume in 10 seconds" and "re-derive everything."**
7. **"Proceed without asking" ≠ "proceed without the workflow."** Autonomous authorization removes *permission gates*, not *process steps*. Keep running plan → build → mid-build checkpoints → quality gate → smoke test → independent review → commit. The async loop lets you do this *unattended*; it does not let you skip steps.
8. **Mid-build checkpoints resolve issues cheaply, in-build.** Dispatch 1–2 independent specialists after each significant build task (max 2 rounds). A REVISE caught mid-build costs minutes; the same issue caught at final review or in production costs hours. This is what lets the agent run long stretches without the human, because quality is enforced continuously rather than in one risky lump at the end.
9. **Self-verify; don't ask the human to look.** Deploy to an emulator/device, capture screenshots, and *read them yourself*. Read logcat for migration/crash errors yourself. The whole point of the loop is to *not* make the developer do QA — only to make *decisions*.
10. **Verify against the repo, never trust the handoff prompt.** Handoff notes and snapshots go stale (a prior commit can land after the snapshot). Re-check the branch tip, the actual file contents, and named "reuse seams" before building on them. Treat a spec's column/API list as a *hypothesis to verify against the source*, not a contract.
11. **Stage only your own files.** When the working tree has pre-existing dirty files from prior sessions, stage *your* changes explicitly — never `git add -A`. Sweeping unrelated dirty files into your commit corrupts attribution and can ship half-baked work. (Keep a "not mine, exclude" note in the resume anchor.)
12. **Background `until`-loop for "tell me when ready"; persistent Monitor for "tell me each time."** A one-shot wait (deploy finished? build up?) is a background command that exits on the condition. A recurring stream (each answer, each new row) is a persistent monitor. Don't use an unbounded `tail -f`/`while true` for a one-shot — it never exits and ties up the slot.
13. **Know the toolchain's failure-recovery.** Concrete example that would otherwise stall an unattended run: an interrupted codegen step (`build_runner` with `--delete-conflicting-outputs`) can corrupt the incremental asset graph so it "skips" a file it just deleted, and a separate builder throws a confusing internal error. Recovery is `build_runner clean` + a full rebuild. Bake known-recovery recipes into the template so the agent self-heals instead of halting.
14. **Pure-function seams make regression-prone logic testable without the human or a live service.** Extract decision logic (classifiers, filters, validators) into pure functions; unit-test them exhaustively. This keeps the test suite fast + deterministic, so the agent can verify itself continuously during an unattended run.

### Collaboration-judgment lessons

15. **Re-send a gating question on resume if delivery is unconfirmed.** If you can't prove the developer received the prior question, re-send it (top-of-stack on their phone) rather than waiting forever on a possibly-undelivered prompt.
16. **When the developer's instruction collides with reality, STOP and surface it — don't guess.** (Originating example: "tag v1.4.0" — but v1.4.0 was already released and the version tags ran ahead of the pubspec. The right move was to present the conflict and ask, not to force a colliding tag.) The async loop makes this cheap: one `ask`, keep everything else moving.
17. **Apply cheap, high-value review fixes in-review rather than deferring.** When an independent review returns *approve-with-changes* with small, sound hardening items, applying them immediately (and re-verifying) keeps the work landable in one pass instead of generating a follow-up backlog the developer has to track.

---

## Part 4 — Integration into the template (what to bake in)

1. **`scripts/collab_loop.py`** — the reference implementation above.
2. **`scripts/notify.py`** (or fold `say` into the above) — one-line push for "long task done" notifications; ASCII titles.
3. **`.claude/rules/async_collaboration.md`** — the Part 2 protocols + the Part 3 loop-mechanics lessons, auto-loaded so every session honors them.
4. **`.env.example`** — `NTFY_TOPIC` / `NTFY_SERVER` / `NTFY_TOKEN` with the security note.
5. **Resume-anchor convention** — a `BUILD_STATUS.md` (or equivalent) with a dedicated **"Async loop state"** section: armed/closed, the `check <window>` + `poll` re-arm recipe, and the throwaway-script paths. Plus a **SessionStart hook** that prompts the agent to read it, and a **PreCompact hook** that prompts updating it.
6. **Autonomous-workflow rule** — encode "proceed-without-asking ≠ skip-steps", the gated-action list (commit to protected branch, deploy, merge to main), and the mid-build-checkpoint protocol (Lesson 8).
7. **Known-recovery recipes** doc (Lesson 13) — codegen-clean, the "stage only your files" rule, and other toolchain gotchas the agent should self-heal.

## Acceptance criteria

- [ ] `ask` delivers a tap-to-answer push to the phone; tapping a button is received by `poll`.
- [ ] Free-text typed in the ntfy app is received by `poll` (empty-title rule).
- [ ] `check <window>` recovers answers sent while no monitor was armed.
- [ ] The topic slug never appears in transcripts/logs, including on error paths.
- [ ] On resume, the agent runs `check` then re-arms `poll`, and does not re-arm a loop the developer closed (state recorded in the resume anchor).
- [ ] The agent holds gated actions until answered and proceeds on non-gated work meanwhile.
- [ ] Every developer answer gets a receipt ack stating what it unblocked.
- [ ] Notification titles are ASCII (no emoji).

## Failure modes + recovery (observed in the originating project)

| Failure | Cause | Fix (baked into the impl/protocol) |
|---|---|---|
| Agent "ignores" a reply after resume | `poll` baselines `since=now`, missed backlog | run `check <window>` before `poll` (Lesson 1) |
| Free-text answer never seen | typed-in-app posts to MAIN, not reply | watch MAIN empty-title too (Lesson 2) |
| Topic slug leaked to transcript | error handler printed `({topic})` | print source label, never the topic (Lesson 3) |
| Notification crashes | emoji in HTTP-header title | ASCII titles only (Protocol 7) |
| Next session re-opens a closed loop | loop state not recorded | record armed/closed in the resume anchor (Lesson 5) |
| Unattended run stalls on a tool error | corrupted incremental codegen state | `clean` + full rebuild recipe (Lesson 13) |
| Wrong/half-baked files committed | `git add -A` swept pre-existing dirt | stage your files explicitly (Lesson 11) |
| Forced a colliding/wrong release tag | followed instruction that collided with reality | STOP + surface + ask (Lesson 16) |

---

## Template conformance gap analysis (as of 2026-05-25, capture time)

> Recorded so `/plan` does not re-derive it. Full detail in `HANDOFF-20260525-233208.md`.

**Already conforms:** one-way push (`scripts/notify.py`, hardened with topic/scheme
validation + the new `--notify` task-boundary hook); "proceed-without-asking ≠
skip-steps" (`.claude/rules/autonomous_workflow.md`, Lesson 7); mid-build checkpoints
(`running-build-checkpoints` skill, Lesson 8); SessionStart resume hook + PreCompact
hook (`.claude/hooks/`, Part 4.5); 1h timeout / trust-boundary allow-list /
confidentiality (`notifying-the-developer` skill).

**Partial / different:** inbound ask is `scripts/ask_developer.py` — **single topic**,
echo-filter by exact title `"Claude needs input"`, **free-text only**, no dedicated
`-reply` topic, no empty-title rule, no `check`-lookback CLI (its `ask()` baselines
`since=now`, so it carries Lesson 1's backlog-miss risk); `notifying-the-developer` is
an **on-demand skill, not an auto-loaded rule**, and omits tap-to-answer preference,
hold-gated-keep-building, milestone cadence, close-the-loop, and ASCII-titles.

**Missing:** `scripts/collab_loop.py` (the two-way loop — reply topic, ≤3 action
buttons, `poll`, `check`, `say`); Monitor-streamed persistent poll wiring;
`.claude/rules/async_collaboration.md`; the empty-title free-text rule; ASCII-title
enforcement (latent `UnicodeEncodeError`); "stage only your files / never `git add -A`"
codification (Lesson 11); generic known-recovery recipes (Lesson 13); the BUILD_STATUS
"Async loop state" section convention.

**Key build decision for `/plan`:** reconcile `collab_loop.py` with `ask_developer.py`.
Do not ship two overlapping inbound-ask tools — either `collab_loop.py` supersedes/wraps
`ask_developer.py`, or `ask_developer.py` is extended with the reply-topic + action
buttons. The template's hardened `notify.py` validation (topic/scheme) and
never-print-topic rule must be preserved in whatever lands.

---

## Specialist review resolutions (/plan, 2026-05-26)

> Reviewed by architecture-consultant, security-specialist, qa-specialist via
> `DISC-20260526-003910-async-collaboration-loop-spec-review`. All three returned
> **approve-with-changes** with no contradictions. These resolutions are **binding on
> `/build_module`** — they supersede the verbatim reference implementation above wherever
> they differ (treat the reference impl as a hypothesis to adapt, per Lesson 10).

### R1 — Reconciliation = Path A: supersede via thin shim (BLOCKING, architecture)
`ask_developer.py` has **zero `src/` callers** and exactly **one real code call site**
(`.claude/commands/distribute.md:183`) plus skill examples and its own test suite.
Therefore:
- **`scripts/collab_loop.py`** is the single two-way implementation (`ask`/`poll`/`check`/`say`).
  It **imports** `validate_topic`, `validate_server`, `send_notification` from `notify.py` —
  it does **not** reimplement them.
- **`scripts/ask_developer.py`** is reduced to a backward-compat **shim**: keep its public
  surface (`ask()`, `send_question()`, `fetch_reply()`) delegating to `collab_loop` primitives,
  so `distribute.md` and the skill examples keep working unchanged and all 17 existing
  `test_ask_developer.py` tests stay green.
- The `distribute.md:183` import and the `notifying-the-developer` skill examples are
  re-pointed in the doc-sync step. Path B (extending `ask_developer.py`) is rejected:
  it would overload one module with two concurrency models and an identity/naming drift.

### R2 — Validation at the config boundary (BLOCKING, architecture+security+qa)
`load_env()` (or a shared `notify.py` resolver both modules call) MUST run
`validate_topic(topic)`, `validate_server(server)`, **and** `validate_topic(reply_topic)`
after deriving `reply_topic = topic + "-reply"`. **Fail closed** on any failure with a
non-revealing message (never print the topic). Reuse `notify.py`'s root-relative `.env`
resolution (`Path(__file__).parent.parent / ".env"`) — **do not** use the reference impl's
CWD-relative `Path(".env")` (a Monitor with a non-root CWD would silently read no topic).

### R3 — Allow-list enforcement is mandatory in the rule (BLOCKING, security)
`.claude/rules/async_collaboration.md` MUST contain an explicit, mandatory clause (not just
a cross-reference to the `notifying-the-developer` skill): *every reply consumed from `poll`
or `check` is validated against the question's fixed allow-list before triggering any gated
action; the **matched label** — not the raw reply text — is the action input; free-text that
matches no allow-list entry triggers no gated action.* Reply text is **untrusted out-of-band
input** (anyone with the slug can publish) and must never reach a shell, path, or eval sink.
Choice strings must come from a hardcoded set, never from reply-derived/external content.

### R4 — Pure-function seams (BLOCKING, qa+architecture; Lesson 14)
Extract decision logic out of I/O before writing other tests:
- `classify_message(msg, *, require_empty_title, seen) -> "skip-event"|"skip-seen"|"skip-titled"|"emit"`
- `parse_ntfy_stream(text) -> list[dict]` and/or `parse_reply_text(msg) -> str`

`_emit`, `poll`, and `check` all consume these (eliminating `check`'s inline duplication of
`_emit`). `poll()` gains injectable `sleep`, `source_fn`, and `max_iterations` seams (mirroring
`ask_developer.ask()`'s injected `sleep`) so the infinite loop is testable.

### R5 — Never-print-topic is a regression (BLOCKING, qa+security)
Confirmed past leak bug. Add `@pytest.mark.regression` tests on **both** error branches
(`HTTPError` + bare `Exception`) asserting the slug never appears in stdout/stderr **and** that
a `WARN` line still prints (not a silent failure). In `_emit`'s broad `except`, replace
`str(e)[:120]` with `type(e).__name__` only (a `urllib` exception's `str()` could embed the
URL+topic). Add a regression-ledger entry.

### R6 — ASCII-title hard guard (ADOPT, security+qa; Protocol 7)
Enforce at the **`notify.py` sending layer** (the single primitive both tools use): sanitize the
HTTP-header `Title` to ASCII (`title.encode("ascii", "replace").decode("ascii")`) or raise a
clear, non-crashing error. `say()` is the risk surface (caller-supplied title); `ask()`
hardcodes `"ASK"`. Add a regression test (same class as the `context_sensor.py` ledger bug,
2026-05-23). Also validate `check`'s `since` argument (`^\d+[smhd]$` or `^\d+$`).

### R7 — ADR-0019 (architecture; Principle #1)
Author **ADR-0019** (framework capability) mirroring ADR-0018's "one core module owns the
logic" precedent. Record: supersede-via-shim, `notify.py` validation as the shared base, the
two-topic + empty-title trust model, and the pure-function seam. `supersedes: null` (additive).

### R8 — Acceptance-criteria reframe (qa)
- **AC-6** (hold gated actions) and **AC-7** (receipt ack) are **agent-behavior protocols**
  enforced by `.claude/rules/async_collaboration.md`, **not** `collab_loop.py` unit tests —
  verified by reading the rule, not by the test suite.
- **AC-1** round-trip (tap → received by `poll`) is a **manual smoke** item; the `ask` JSON
  payload structure (action buttons → reply topic, body == label, ≤3 cap) **is** unit-testable.
- AC-2/AC-3/AC-4/AC-8 are unit-testable once the R4 seams exist.

### Build test target (qa)
~20 blocking + ~3 advisory unit tests in `tests/test_collab_loop.py` (classify_message matrix,
empty-title incl. whitespace boundary, dedup, never-print-topic ×2, check-backlog recovery,
ascii-title raise/pass, load_env validation, ask payload + ≤3 cap, poll bounded-iteration).
All 17 `test_ask_developer.py` tests must remain green.
