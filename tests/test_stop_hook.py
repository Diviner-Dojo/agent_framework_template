"""Tests for scripts/stop_hook.py and scripts/queue_stop_notify.py.

Covers the one-shot-stop-hook back-flow pattern (ADR: dan_research_karpathy_wiki
origin) and its template security adaptations: silent-by-default, one-shot
state deletion, allow-list-only reply injection (matched label, never raw
text), single-poller lockfile discipline, no-slug error paths, ASCII output.
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts to path for import
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import queue_stop_notify  # noqa: E402
import stop_hook  # noqa: E402


@pytest.fixture()
def state_file(tmp_path, monkeypatch):
    """Point the hook at a temp state file and silence stdin."""
    sf = tmp_path / "next-stop-notify.json"
    monkeypatch.setattr(stop_hook, "STATE_FILE", sf)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    monkeypatch.setenv("NTFY_TOPIC", "test-topic-slug-abc123")
    monkeypatch.delenv("STOP_HOOK_DISABLE", raising=False)
    return sf


@pytest.fixture()
def sent_calls(monkeypatch):
    """Capture send_notification calls; default to success."""
    calls: list[dict] = []

    def fake_send(message, **kwargs):
        calls.append({"message": message, **kwargs})
        return True

    monkeypatch.setattr(stop_hook, "send_notification", fake_send)
    return calls


@pytest.fixture()
def no_lock(monkeypatch):
    """Neutralize lockfile I/O (claim is a no-op; we always own the lock)."""
    monkeypatch.setattr(stop_hook, "claim_poll_lock", lambda choices: None)
    monkeypatch.setattr(stop_hook, "owns_poll_lock", lambda: True)


def _write_intent(sf: Path, **overrides) -> None:
    intent = {"title": "T1 done", "body": "Next: review.", **overrides}
    sf.write_text(json.dumps(intent), encoding="utf-8")


class TestSilentByDefault:
    def test_no_state_file_is_silent(self, state_file, sent_calls, capsys):
        assert stop_hook.main() == 0
        assert sent_calls == []
        out = capsys.readouterr()
        assert out.out == ""

    def test_disabled_env_skips_even_with_intent(self, state_file, sent_calls, monkeypatch):
        _write_intent(state_file)
        monkeypatch.setenv("STOP_HOOK_DISABLE", "1")
        assert stop_hook.main() == 0
        assert sent_calls == []
        assert state_file.exists()  # disabled run must not consume the intent

    def test_no_topic_deletes_intent_without_sending(self, state_file, sent_calls, monkeypatch):
        _write_intent(state_file)
        monkeypatch.setenv("NTFY_TOPIC", "")
        assert stop_hook.main() == 0
        assert sent_calls == []
        assert not state_file.exists()


class TestOneShot:
    def test_fires_once_and_deletes(self, state_file, sent_calls):
        _write_intent(state_file, priority="high", tags="rocket")
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1
        assert sent_calls[0]["title"] == "T1 done"
        assert sent_calls[0]["message"] == "Next: review."
        assert sent_calls[0]["priority"] == "high"
        assert sent_calls[0]["tags"] == "rocket"
        assert not state_file.exists()
        # Second stop: silent.
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1

    def test_bad_json_is_discarded(self, state_file, sent_calls, capsys):
        state_file.write_text("{not json", encoding="utf-8")
        assert stop_hook.main() == 0
        assert sent_calls == []
        assert not state_file.exists()
        assert "discarding" in capsys.readouterr().err

    def test_non_object_json_is_discarded(self, state_file, sent_calls):
        state_file.write_text('["a list"]', encoding="utf-8")
        assert stop_hook.main() == 0
        assert sent_calls == []
        assert not state_file.exists()

    @pytest.mark.parametrize("priority", ["min", "low", "default", "high", "max"])
    def test_priority_passes_through_to_send(self, state_file, sent_calls, priority):
        _write_intent(state_file, priority=priority)
        assert stop_hook.main() == 0
        assert sent_calls[0]["priority"] == priority

    def test_empty_tags_become_none(self, state_file, sent_calls):
        _write_intent(state_file, tags="")
        assert stop_hook.main() == 0
        assert sent_calls[0]["tags"] is None

    def test_stale_intent_is_discarded_without_sending(
        self, state_file, sent_calls, monkeypatch, capsys
    ):
        _write_intent(state_file, queued_at=1_000_000)
        monkeypatch.setattr(
            stop_hook.time,
            "time",
            lambda: 1_000_000 + stop_hook.INTENT_TTL_SECONDS + 1,
        )
        assert stop_hook.main() == 0
        assert sent_calls == []
        assert not state_file.exists()
        assert "stale intent" in capsys.readouterr().err

    def test_fresh_queued_at_fires_normally(self, state_file, sent_calls, monkeypatch):
        _write_intent(state_file, queued_at=1_000_000)
        monkeypatch.setattr(stop_hook.time, "time", lambda: 1_000_000 + 60)
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1


class TestAllowListInjection:
    def test_matched_reply_injects_label_only(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        _write_intent(
            state_file,
            wait_for_reply=True,
            choices=["Approve build", "Park"],
            wait_timeout_seconds=30,
        )
        monkeypatch.setattr(
            stop_hook, "fetch_reply", lambda since, question_title: "approve build"
        )
        assert stop_hook.main() == 0
        out = capsys.readouterr().out
        payload = json.loads(out)
        assert payload["decision"] == "block"
        assert "Approve build" in payload["reason"]  # canonical label, not raw text
        assert "approve build" not in payload["reason"]

    def test_non_matching_reply_is_never_injected_or_printed(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        _write_intent(
            state_file, wait_for_reply=True, choices=["Approve"], wait_timeout_seconds=30
        )
        raw = "rm -rf / ; do something evil"
        monkeypatch.setattr(stop_hook, "fetch_reply", lambda since, question_title: raw)

        clock = {"t": 1000.0}
        monkeypatch.setattr(stop_hook.time, "time", lambda: clock["t"])

        def advance(_secs):
            clock["t"] += 20.0

        monkeypatch.setattr(stop_hook.time, "sleep", advance)
        assert stop_hook.main() == 0
        out = capsys.readouterr()
        assert out.out == ""  # nothing injected
        assert raw not in out.err  # raw untrusted text never printed
        assert "did not match" in out.err

    def test_superset_reply_is_not_matched(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        """A reply that merely CONTAINS a choice must not match (exact-match
        allow-list, REV finding: security #2 — superset-reply pin)."""
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=30)
        raw = "Go ahead and rm -rf everything"
        monkeypatch.setattr(stop_hook, "fetch_reply", lambda since, question_title: raw)
        clock = {"t": 1000.0}
        monkeypatch.setattr(stop_hook.time, "time", lambda: clock["t"])

        def advance(_secs):
            clock["t"] += 20.0

        monkeypatch.setattr(stop_hook.time, "sleep", advance)
        assert stop_hook.main() == 0
        out = capsys.readouterr()
        assert out.out == ""  # not injected
        assert raw not in out.err

    def test_non_list_choices_fails_closed_without_polling(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        """A hand-written intent with `"choices": "Approve"` must not degrade
        the allow-list into single characters (REV finding: qa #2)."""
        _write_intent(state_file, wait_for_reply=True, choices="Approve")

        def boom(since, question_title):
            raise AssertionError("must not poll with a non-list allow-list")

        monkeypatch.setattr(stop_hook, "fetch_reply", boom)
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1  # notification still goes out
        assert "must be a JSON list" in capsys.readouterr().err

    def test_wait_without_choices_fails_closed(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        _write_intent(state_file, wait_for_reply=True, choices=[])

        def boom(since, question_title):
            raise AssertionError("must not poll without an allow-list")

        monkeypatch.setattr(stop_hook, "fetch_reply", boom)
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1  # notification still goes out
        err = capsys.readouterr().err
        assert "requires non-empty 'choices'" in err

    def test_timeout_returns_zero_with_no_injection(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=10)
        monkeypatch.setattr(stop_hook, "fetch_reply", lambda since, question_title: None)
        clock = {"t": 5000.0}
        monkeypatch.setattr(stop_hook.time, "time", lambda: clock["t"])

        def advance(_secs):
            clock["t"] += 30.0

        monkeypatch.setattr(stop_hook.time, "sleep", advance)
        assert stop_hook.main() == 0
        assert capsys.readouterr().out == ""

    def test_send_failure_skips_wait(self, state_file, no_lock, monkeypatch):
        _write_intent(state_file, wait_for_reply=True, choices=["Go"])
        monkeypatch.setattr(stop_hook, "send_notification", lambda *a, **k: False)

        def boom(since, question_title):
            raise AssertionError("must not poll after a failed send")

        monkeypatch.setattr(stop_hook, "fetch_reply", boom)
        assert stop_hook.main() == 0


class TestSinglePollerDiscipline:
    # Regression: 2026-06-07 reply-misfiling bug (regression-ledger,
    # scripts/collab_loop.py) — a newer poller must supersede this hook's
    # poller within one cycle so replies are never validated against a
    # stale allow-list.
    @pytest.mark.regression
    def test_superseded_lock_stands_down(self, state_file, sent_calls, monkeypatch, capsys):
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=60)
        claimed: list[list[str]] = []
        monkeypatch.setattr(stop_hook, "claim_poll_lock", lambda choices: claimed.append(choices))
        monkeypatch.setattr(stop_hook, "owns_poll_lock", lambda: False)

        def boom(since, question_title):
            raise AssertionError("must not poll after losing the lock")

        monkeypatch.setattr(stop_hook, "fetch_reply", boom)
        assert stop_hook.main() == 0
        assert claimed == [["Go"]]  # lock was claimed with our allow-list
        captured = capsys.readouterr()
        assert "standing down" in captured.err
        assert captured.out == ""


class TestNoSlugAndAsciiInvariants:
    def test_poll_error_prints_type_only(
        self, state_file, sent_calls, no_lock, monkeypatch, capsys
    ):
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=10)
        topic = "test-topic-slug-abc123"

        def fail(since, question_title):
            raise OSError(f"http://ntfy.sh/{topic}/json failed")

        monkeypatch.setattr(stop_hook, "fetch_reply", fail)
        clock = {"t": 0.0}
        monkeypatch.setattr(stop_hook.time, "time", lambda: clock["t"])

        def advance(_secs):
            clock["t"] += 30.0

        monkeypatch.setattr(stop_hook.time, "sleep", advance)
        assert stop_hook.main() == 0
        err = capsys.readouterr().err
        assert topic not in err
        assert "OSError" in err

    def test_stderr_messages_are_ascii(self, state_file, sent_calls, capsys):
        state_file.write_text("{not json", encoding="utf-8")
        stop_hook.main()
        err = capsys.readouterr().err
        err.encode("ascii")  # raises on violation
        err.encode("cp1252")


class TestQueueCli:
    def test_writes_expected_schema(self, tmp_path, monkeypatch, capsys):
        sf = tmp_path / "next-stop-notify.json"
        monkeypatch.setattr(queue_stop_notify, "STATE_FILE", sf)
        rc = queue_stop_notify.main(
            [
                "--title",
                "Decision needed",
                "--body",
                "Reply to choose.",
                "--priority",
                "high",
                "--wait",
                "--wait-timeout",
                "9999",
                "--choices",
                "Retry",
                "Park",
            ]
        )
        assert rc == 0
        data = json.loads(sf.read_text(encoding="utf-8"))
        assert data["title"] == "Decision needed"
        assert data["wait_for_reply"] is True
        assert data["choices"] == ["Retry", "Park"]
        assert data["wait_timeout_seconds"] == queue_stop_notify.WAIT_TIMEOUT_CAP
        assert "Queued stop notification" in capsys.readouterr().out

    def test_wait_without_choices_is_an_error(self, tmp_path, monkeypatch):
        sf = tmp_path / "next-stop-notify.json"
        monkeypatch.setattr(queue_stop_notify, "STATE_FILE", sf)
        with pytest.raises(SystemExit):
            queue_stop_notify.main(["--title", "X", "--wait"])
        assert not sf.exists()

    def test_no_wait_needs_no_choices(self, tmp_path, monkeypatch):
        sf = tmp_path / "next-stop-notify.json"
        monkeypatch.setattr(queue_stop_notify, "STATE_FILE", sf)
        assert queue_stop_notify.main(["--title", "Done", "--body", "Next: merge."]) == 0
        data = json.loads(sf.read_text(encoding="utf-8"))
        assert data["wait_for_reply"] is False
        assert data["choices"] == []

    def test_timeout_cap_matches_hook_cap(self):
        assert queue_stop_notify.WAIT_TIMEOUT_CAP == stop_hook.WAIT_TIMEOUT_CAP


# --------------------------------------------------------------------------- #
# Telemetry kick (SPEC-20260716-093231 R4/AC5/AC6/AC11)
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def telemetry_calls(tmp_path, monkeypatch):
    """Isolate the telemetry kick for EVERY test in this module.

    Without this, any test calling ``stop_hook.main()`` would stamp the real
    ``.claude/hooks/.state/telemetry-last-attempt`` and spawn a real
    subprocess against the live repo DB/log (write-side isolation, spec R7).
    Returns the recorded subprocess invocations.
    """
    calls: list[dict] = []

    def fake_run(cmd, **kwargs):
        calls.append({"cmd": list(cmd), **kwargs})
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(stop_hook.subprocess, "run", fake_run)
    monkeypatch.setattr(
        stop_hook, "TELEMETRY_STATE_FILE", tmp_path / "tel-state" / "telemetry-last-attempt"
    )
    monkeypatch.delenv("STOP_HOOK_TELEMETRY_DISABLE", raising=False)
    return calls


class TestTelemetryKick:
    def test_kick_runs_on_silent_stop_with_bounded_subprocess(
        self, state_file, sent_calls, telemetry_calls
    ):
        """AC6ii: the kick is a timeout-bounded, output-captured subprocess."""
        assert stop_hook.main() == 0
        assert len(telemetry_calls) == 1
        call = telemetry_calls[0]
        assert call["cmd"][0] == sys.executable
        assert call["cmd"][1] == str(stop_hook.CALL_LOG_SCRIPT)
        assert "--from-hook" in call["cmd"]
        assert "--budget-seconds" in call["cmd"]
        assert call["timeout"] == stop_hook.TELEMETRY_BUDGET_SECONDS
        assert call["capture_output"] is True

    def test_master_disable_skips_entire_hook_including_kick(
        self, state_file, sent_calls, telemetry_calls, monkeypatch
    ):
        """AC6: STOP_HOOK_DISABLE=1 remains the master off-switch (R4a)."""
        _write_intent(state_file)
        monkeypatch.setenv("STOP_HOOK_DISABLE", "1")
        assert stop_hook.main() == 0
        assert telemetry_calls == []
        assert sent_calls == []

    def test_telemetry_disable_skips_only_the_kick(
        self, state_file, sent_calls, telemetry_calls, monkeypatch
    ):
        _write_intent(state_file)
        monkeypatch.setenv("STOP_HOOK_TELEMETRY_DISABLE", "1")
        assert stop_hook.main() == 0
        assert len(sent_calls) == 1  # intent flow unaffected
        assert telemetry_calls == []

    def test_throttle_runs_once_within_floor(self, state_file, sent_calls, telemetry_calls):
        """AC6: two back-to-back stops inside the floor run the ingest once."""
        assert stop_hook.main() == 0
        assert stop_hook.main() == 0
        assert len(telemetry_calls) == 1

    def test_failed_run_still_stamps_eagerly_and_stays_silent(
        self, state_file, sent_calls, telemetry_calls, monkeypatch, capsys
    ):
        """AC6: eager stamp — a broken ingest costs one attempt per floor, and
        the failure path prints the exception TYPE only (no-slug, ASCII)."""
        attempts = {"n": 0}

        def boom(cmd, **kwargs):
            attempts["n"] += 1
            raise RuntimeError("http://ntfy.sh/test-topic-slug-abc123 leaked")

        monkeypatch.setattr(stop_hook.subprocess, "run", boom)
        assert stop_hook.main() == 0  # fail-silent: exit code unchanged
        assert stop_hook.main() == 0  # throttled: no second attempt
        assert attempts["n"] == 1
        err = capsys.readouterr().err
        assert "telemetry kick failed (RuntimeError)" in err
        assert "test-topic-slug-abc123" not in err  # no-slug invariant
        err.encode("ascii")
        err.encode("cp1252")

    def test_timeout_expired_is_swallowed(
        self, state_file, sent_calls, telemetry_calls, monkeypatch, capsys
    ):
        def hang(cmd, **kwargs):
            raise subprocess.TimeoutExpired(cmd="call_log", timeout=15)

        monkeypatch.setattr(stop_hook.subprocess, "run", hang)
        assert stop_hook.main() == 0
        assert "telemetry kick failed (TimeoutExpired)" in capsys.readouterr().err

    def test_corrupt_throttle_stamp_is_eligible_to_run(
        self, state_file, sent_calls, telemetry_calls
    ):
        stop_hook.TELEMETRY_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        stop_hook.TELEMETRY_STATE_FILE.write_text("not-a-float", encoding="utf-8")
        assert stop_hook.main() == 0
        assert len(telemetry_calls) == 1  # fail-open on corrupt stamp (R4b)

    def test_ac5_matched_reply_with_failing_kick_keeps_decision_clean(
        self, state_file, sent_calls, no_lock, telemetry_calls, monkeypatch, capsys
    ):
        """AC5 combined-failure path (review qa F1): an active matched-reply
        intent AND a failing telemetry subprocess in one run — exit 0, stdout
        is exactly the one JSON decision object, stderr is type-only."""
        monkeypatch.setattr(stop_hook, "fetch_reply", lambda since, question_title: "Go")
        monkeypatch.setattr(
            stop_hook.subprocess,
            "run",
            lambda cmd, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
        )
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=30)
        assert stop_hook.main() == 0
        captured = capsys.readouterr()
        payload = json.loads(captured.out)
        assert payload["decision"] == "block"
        assert "telemetry kick failed (RuntimeError)" in captured.err

    def test_unwritable_stamp_fails_open_and_degrades_to_unthrottled(
        self, state_file, sent_calls, telemetry_calls, monkeypatch, capsys
    ):
        """Review qa F6: a persistently unwritable throttle stamp fails open —
        the kick still runs, and (documented accepted bound) runs on EVERY
        stop because the once-per-floor stamp never lands."""

        def broken_replace(src, dst):
            raise OSError("disk full")

        monkeypatch.setattr(stop_hook.os, "replace", broken_replace)
        assert stop_hook.main() == 0
        assert stop_hook.main() == 0
        assert len(telemetry_calls) == 2  # unthrottled: once per stop
        err = capsys.readouterr().err
        assert "telemetry stamp failed (OSError); continuing" in err
        err.encode("ascii")

    def test_ac11_stdout_is_exactly_one_json_object_with_matched_reply(
        self, state_file, sent_calls, no_lock, telemetry_calls, monkeypatch, capsys
    ):
        """AC11 stdout purity: matched reply + telemetry kick in ONE run, and
        stdout parses as exactly one JSON decision object, byte-identical to
        the telemetry-disabled run."""
        monkeypatch.setattr(stop_hook, "fetch_reply", lambda since, question_title: "Go")

        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=30)
        assert stop_hook.main() == 0
        with_kick = capsys.readouterr().out
        assert len(telemetry_calls) == 1
        payload = json.loads(with_kick)  # raises if anything but one JSON object
        assert payload["decision"] == "block"

        monkeypatch.setenv("STOP_HOOK_TELEMETRY_DISABLE", "1")
        _write_intent(state_file, wait_for_reply=True, choices=["Go"], wait_timeout_seconds=30)
        assert stop_hook.main() == 0
        without_kick = capsys.readouterr().out
        assert with_kick == without_kick  # byte-identical decision channel
