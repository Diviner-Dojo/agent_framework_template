#!/usr/bin/env python3
"""Claude Code Stop hook -- fires only when an actionable intent was queued.

Silent-by-default: reads ``.claude/hooks/.state/next-stop-notify.json``. If
present, fires the ntfy notification described there (and optionally polls for
a developer reply), then **deletes the file** so it is a one-shot. If absent,
exits silently -- the hook produces no spam on turn ends without an explicit
intent.

Origin: back-flow pattern ``one-shot-stop-hook`` from dan_research_karpathy_wiki
(wiki sources: tools/stop-hook.py, tools/queue-stop-notify.py). The wiki's
design note applies here too: an auto-fired "turn ended" notification on every
stop is non-actionable spam; the orchestrator must declare intent *before*
stopping via ``scripts/queue_stop_notify.py``, describing WHAT finished and
WHAT'S NEXT.

Template adaptations (these are load-bearing, do not weaken without an ADR):

* **Allow-list reply injection.** The wiki version injects the raw ntfy reply
  text as the next prompt. Here, out-of-band replies are untrusted (CLAUDE.md
  Always-On Invariant): the intent file must declare ``choices``; only a reply
  matching that allow-list (via ``collab_loop.match_choice``) is acted on, and
  only the **matched label** is injected -- never the raw reply text. A
  wait request without choices does not poll at all (fail closed).
* **Single-poller discipline.** Polling claims the ``collab_loop`` lockfile
  and self-exits when superseded, so a concurrent ``poll`` monitor can never
  misvalidate this hook's reply against a different allow-list (regression
  ledger 2026-06-07, reply-misfiling bug).
* **No-slug + ASCII console invariants.** Error paths print exception types
  only (never ``str(exc)``, which can embed the topic URL), and all console
  output is plain ASCII (cp1252 terminal class, regression ledger).

JSON schema (``.claude/hooks/.state/next-stop-notify.json``)::

    {
      "title":   "string (required) -- short notification title",
      "body":    "string (required) -- what happened AND what's next",
      "priority": "min|low|default|high|urgent  (optional, default 'default')",
      "tags":    "comma-separated emoji shortcodes (optional)",
      "wait_for_reply": false,        // optional -- poll ntfy for a reply
      "wait_timeout_seconds": 120,    // optional, default 120, capped at 600
      "choices": ["Approve", "Park"]  // REQUIRED when wait_for_reply is true
    }

Telemetry kick (SPEC-20260716-093231): after the intent flow, the hook also
runs the per-call cost/cache instrument (``scripts/telemetry/call_log.py``)
as a throttled, timeout-bounded subprocess with captured output — see
``_run_telemetry_kick``. It shares none of the intent state and cannot write
to this hook's stdout (the decision channel).

Env-var knobs:
  STOP_HOOK_DISABLE=1            skip the hook entirely (telemetry included)
  STOP_HOOK_TELEMETRY_DISABLE=1  skip only the telemetry kick
  STOP_HOOK_POLL_INTERVAL=3      poll cadence (seconds) when waiting
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import time

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from ask_developer import fetch_reply  # noqa: E402
from collab_loop import claim_poll_lock, match_choice, owns_poll_lock  # noqa: E402
from notify import send_notification  # noqa: E402

PROJECT_ROOT = SCRIPTS_DIR.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "hooks" / ".state" / "next-stop-notify.json"
# The settings.json Stop-hook timeout must exceed this by the margin budget:
# cap + one send (10s) + one in-flight poll HTTP timeout (15s) + spawn slack.
# The parked draft uses 660. (REV-20260613 security finding 4.)
WAIT_TIMEOUT_CAP = 600
# A queued intent older than this is stale — a forgotten STOP_HOOK_DISABLE=1 or a
# crashed session must not fire an old gated question into an unrelated session.
INTENT_TTL_SECONDS = 4 * 3600

# --- Telemetry kick (SPEC-20260716-093231 R4) -------------------------------
# The per-call cost/cache instrument runs on turn end as a timeout-bounded
# subprocess (never inline: keeps this hook's import/fault surface unchanged
# and makes stdout pollution of the decision channel structurally impossible).
# STOP_HOOK_DISABLE=1 remains the master off-switch for the ENTIRE hook,
# telemetry included; STOP_HOOK_TELEMETRY_DISABLE=1 disables only the kick.
# Accepted bound: if the throttle stamp is persistently unwritable (perms,
# disk full), the kick fails open and runs on EVERY stop — the once-per-floor
# guarantee degrades to once-per-turn, each bounded by the subprocess timeout.
TELEMETRY_STATE_FILE = PROJECT_ROOT / ".claude" / "hooks" / ".state" / "telemetry-last-attempt"
TELEMETRY_THROTTLE_SECONDS = 600
TELEMETRY_BUDGET_SECONDS = 15
CALL_LOG_SCRIPT = SCRIPTS_DIR / "telemetry" / "call_log.py"


def _poll_interval() -> int:
    try:
        return max(1, int(os.environ.get("STOP_HOOK_POLL_INTERVAL", "3")))
    except ValueError:
        return 3


def _delete_state(state_file: pathlib.Path) -> None:
    try:
        state_file.unlink()
    except FileNotFoundError:
        pass
    except OSError as e:
        # Type only -- never str(exc) (no-slug invariant).
        print(f"[stop-hook] could not delete state file: {type(e).__name__}", file=sys.stderr)


def _load_intent(state_file: pathlib.Path) -> dict | None:
    try:
        raw = json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"[stop-hook] bad state file ({type(e).__name__}); discarding", file=sys.stderr)
        return None
    if not isinstance(raw, dict):
        print("[stop-hook] state file is not a JSON object; discarding", file=sys.stderr)
        return None
    return raw


def _wait_for_choice(
    *,
    sent_at: int,
    title: str,
    choices: list[str],
    deadline: float,
) -> str | None:
    """Poll ntfy until a reply matches the allow-list, the deadline passes,
    or a newer poller supersedes us. Returns the matched LABEL or None."""
    claim_poll_lock(choices)
    interval = _poll_interval()
    warned_nonmatch = False
    while time.time() < deadline:
        if not owns_poll_lock():
            # A newer ask/poll took the lock -- stand down within one cycle
            # (single-poller invariant, regression ledger 2026-06-07).
            print("[stop-hook] superseded by a newer poller; standing down", file=sys.stderr)
            return None
        try:
            reply = fetch_reply(sent_at, question_title=title)
        except Exception as e:
            print(f"[stop-hook] poll error ({type(e).__name__}); retrying", file=sys.stderr)
            reply = None
        if reply:
            label = match_choice(reply, choices)
            if label is not None:
                return label
            if not warned_nonmatch:
                # Raw reply text is untrusted -- never printed, never acted on.
                print(
                    "[stop-hook] reply did not match the allow-list; ignoring",
                    file=sys.stderr,
                )
                warned_nonmatch = True
        time.sleep(interval)
    return None


def _run_telemetry_kick() -> None:
    """Run the per-call cost/cache instrument, throttled and fail-silent.

    SPEC-20260716-093231 R4: eager atomic throttle stamp (a persistently
    broken ingest costs at most one budget per floor, never one per turn;
    no data is lost — the emitter's watermark advances only on success),
    then a timeout-bounded subprocess with captured output. Any failure
    prints the exception TYPE only (no-slug invariant) and never blocks
    the stop.
    """
    try:
        if os.environ.get("STOP_HOOK_TELEMETRY_DISABLE", "").strip() == "1":
            return
        now = time.time()
        try:
            last_attempt = float(TELEMETRY_STATE_FILE.read_text(encoding="utf-8").strip())
            if now - last_attempt < TELEMETRY_THROTTLE_SECONDS:
                return
        except (OSError, ValueError):
            pass  # Missing/corrupt stamp -- eligible to run (fail open, R4b).
        try:
            TELEMETRY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            tmp = TELEMETRY_STATE_FILE.with_name(TELEMETRY_STATE_FILE.name + ".tmp")
            tmp.write_text(str(int(now)), encoding="utf-8")
            os.replace(tmp, TELEMETRY_STATE_FILE)
        except OSError as e:
            # Type only -- never str(exc) (no-slug invariant).
            print(
                f"[stop-hook] telemetry stamp failed ({type(e).__name__}); continuing",
                file=sys.stderr,
            )
        # An already-printed decision must reach Claude Code before we spend
        # up to the budget in the child (buffering could otherwise delay it).
        sys.stdout.flush()
        subprocess.run(
            [
                sys.executable,
                str(CALL_LOG_SCRIPT),
                "--from-hook",
                "--budget-seconds",
                str(max(TELEMETRY_BUDGET_SECONDS - 3, 1)),
            ],
            timeout=TELEMETRY_BUDGET_SECONDS,
            capture_output=True,
            check=False,
        )
    except Exception as e:
        # Fail-silent contract (R4e): the hook must never block a session stop.
        print(f"[stop-hook] telemetry kick failed ({type(e).__name__})", file=sys.stderr)


def main() -> int:
    # Drain stdin (Claude Code passes session metadata; currently unused).
    try:
        _ = sys.stdin.read()
    except Exception:
        pass

    if os.environ.get("STOP_HOOK_DISABLE", "").strip() == "1":
        # Master off-switch: skips the ENTIRE hook, telemetry kick included
        # (preserves the docstring guarantee; SPEC-20260716-093231 R4a).
        return 0

    exit_code = _handle_intent()
    # After the intent flow, so a gated notification is never delayed; the
    # kick writes nothing to this process's stdout (decision channel) by
    # construction -- child output is captured and discarded (AC11).
    _run_telemetry_kick()
    return exit_code


def _handle_intent() -> int:
    """Run the one-shot ntfy-intent flow (behavior unchanged; ADR-0023)."""
    if not STATE_FILE.exists():
        return 0  # No intent declared -- silent.

    intent = _load_intent(STATE_FILE)
    if intent is None:
        _delete_state(STATE_FILE)
        return 0

    queued_at = intent.get("queued_at")
    if isinstance(queued_at, int | float) and time.time() - queued_at > INTENT_TTL_SECONDS:
        print("[stop-hook] stale intent (older than TTL); discarding", file=sys.stderr)
        _delete_state(STATE_FILE)
        return 0

    title = str(intent.get("title", "Claude session update")).strip()
    body = str(intent.get("body", "")).strip()
    priority = str(intent.get("priority", "default"))
    tags = str(intent.get("tags", "")) or None
    wait = bool(intent.get("wait_for_reply", False))
    choices = intent.get("choices") or []
    if not isinstance(choices, list):
        # A non-list (e.g. a hand-written string) would otherwise iterate into
        # single characters, silently degrading the allow-list. Fail closed.
        print("[stop-hook] 'choices' must be a JSON list; will not poll", file=sys.stderr)
        choices = []
    try:
        wait_timeout = min(int(intent.get("wait_timeout_seconds", 120)), WAIT_TIMEOUT_CAP)
    except (TypeError, ValueError):
        wait_timeout = 120

    # If NTFY_TOPIC isn't configured, skip cleanly (delete the queued intent
    # so it doesn't pile up).
    if not os.environ.get("NTFY_TOPIC", "").strip():
        _delete_state(STATE_FILE)
        return 0

    sent_at = int(time.time())
    sent = send_notification(body, title=title, priority=priority, tags=tags)

    # One-shot: delete immediately so we don't re-fire on the next turn end.
    _delete_state(STATE_FILE)

    if not sent or not wait or wait_timeout <= 0:
        return 0

    valid_choices = [str(c).strip() for c in choices if str(c).strip()]
    if not valid_choices:
        # Fail closed: waiting without an allow-list would force free-text
        # handling of untrusted input. Notify went out; we just don't poll.
        print(
            "[stop-hook] wait_for_reply requires non-empty 'choices'; not polling",
            file=sys.stderr,
        )
        return 0

    label = _wait_for_choice(
        sent_at=sent_at,
        title=title,
        choices=valid_choices,
        deadline=sent_at + wait_timeout,
    )
    if label is not None:
        # Stop-hook contract (Claude Code hooks reference): printing
        # {"decision": "block", "reason": ...} on stdout prevents the stop and
        # continues the session with `reason` as guidance. Empirically confirmed
        # by the wiki's deployment of the original pattern.
        output = {
            "decision": "block",
            "reason": (
                f"Developer replied via ntfy and selected the allow-listed choice: "
                f"{label}. Act on this choice."
            ),
        }
        print(json.dumps(output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
