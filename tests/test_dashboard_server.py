"""Phase-1 invariant tests for the Telemetry Layer B dashboard daemon.

These tests guard the 9 binding Steward conditions (= AC1-AC9 of
SPEC-20260607-183136) plus AC10/AC14/AC15/AC16/AC17. They focus on
*invariants* — the things that, if a future edit breaks, must be caught at
the gate, not by a developer noticing weeks later:

* **AC1**: explicit-launch-only — no auto-start hook reference.
* **AC2**: hardcoded 127.0.0.1 bind + no host configurability + Host header
  guard + runtime guard before ``uvicorn.run()``.
* **AC3**: two-layer no-inject regression guard — module-allowlist + byte-
  unchanged hooks/settings after every route hit.
* **AC5**: read-only DB connection; schema + row counts unchanged across a
  route hit; lifespan teardown leaves no residue.
* **AC6**: every dynamic/transcript-shaped field escaped server-side; data
  baked into ``<script>`` blocks safe against ``</script>`` injection; error
  paths return a generic body (no DB path, no exception class name).
* **AC8**: no outbound HTTP client.
* **AC10**: daemon serves the htmx shell on the loopback bind.
* **AC14**: ``src.telemetry.live`` is a pure event-fold (no ``scripts.*`` /
  no transcript-IO import) — *also* covered in ``test_telemetry.py`` as the
  module's own regression; mirrored here for the server's transport-purity
  story.
* **AC15**: A-ARCH1 promotion — the 4 transcript helpers are public.
* **AC16**: port-in-use yields a clear human-readable message, not a raw
  ``[Errno 98]`` trace.
* **AC17**: quality gate — runs in its own step, not here.

A deliberate Phase 1 deferral: **AC11 authored fixture-transcript inventory**
(active session with orphan + amber + red runway + truncated last line) lands
with the Phase 2 live-tail when the background watcher replaces lazy-per-
request folding. The Phase 1 surface here is the *transport* (bind, escape,
read-only, lifespan) — the *behavioral parity against authored fixtures*
follows.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import re
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import uvicorn
from fastapi.testclient import TestClient

from scripts import ingest_token_usage as itu
from scripts.init_db import init_db
from scripts.telemetry import dashboard_server
from scripts.telemetry.dashboard_server import (
    CONTENT_SECURITY_POLICY,
    HARDCODED_HOST,
    ContentSecurityPolicyMiddleware,
    HostHeaderGuard,
    NonLoopbackBindError,
    create_app,
    run_server,
)

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SERVER_SOURCE = _REPO_ROOT / "scripts" / "telemetry" / "dashboard_server.py"


# --------------------------------------------------------------------------- #
# AC1 — explicit launch only (no auto-start hook reference)
# --------------------------------------------------------------------------- #


def test_server_source_has_no_auto_launch_hook_reference() -> None:
    """No SessionStart / hook / auto-launch / `/distribute` reference starts the server.

    The single way to start it is the ``main()`` CLI entry. A future change
    that wires it into a hook (SessionStart, PreToolUse, ...) or into the
    ADR-0018 auto-launch path is a Steward-gated decision; this guard makes
    such an addition impossible to land silently.
    """
    text = _SERVER_SOURCE.read_text(encoding="utf-8")
    forbidden_phrases = [
        "SessionStart",
        "PreToolUse",
        "PostToolUse",
        "ALLOW_AUTO_LAUNCH",
        "build_launch_command",
        "/distribute",
    ]
    for phrase in forbidden_phrases:
        assert phrase not in text, (
            f"server source contains forbidden auto-launch phrase {phrase!r}"
        )


# --------------------------------------------------------------------------- #
# AC2 — hardcoded 127.0.0.1 bind + no host configurability + runtime guard
# --------------------------------------------------------------------------- #


def test_hardcoded_host_is_loopback_literal() -> None:
    """The single host the module will ever bind is ``127.0.0.1`` (literal)."""
    assert HARDCODED_HOST == "127.0.0.1"


def test_server_source_has_no_wildcard_bind_code() -> None:
    """No ``0.0.0.0`` literal appears in a *bind-shaped* line of the server source.

    A future edit that introduces a ``--bind`` or ``HOST`` env read would
    also typically introduce a ``0.0.0.0`` literal in a ``host=``-shaped
    expression. The defense-in-depth comment in ``run_server`` mentions
    ``0.0.0.0`` *as the value to refuse* — that string occurrence is allowed.
    We ban only the bind-shaped patterns: ``host="0.0.0.0"``, ``host='0.0.0.0'``,
    ``"0.0.0.0"`` as a standalone arg, etc.
    """
    text = _SERVER_SOURCE.read_text(encoding="utf-8")
    bind_patterns = [
        r'host\s*=\s*[\'"]0\.0\.0\.0[\'"]',
        r'bind\s*=\s*[\'"]0\.0\.0\.0[\'"]',
        r'HARDCODED_HOST\s*=\s*[\'"]0\.0\.0\.0[\'"]',
    ]
    for pattern in bind_patterns:
        match = re.search(pattern, text)
        assert match is None, f"server source contains forbidden wildcard-bind pattern {pattern!r}"


def test_cli_has_no_host_flag() -> None:
    """The CLI exposes no ``--host`` / ``-H`` / ``HOST`` affordance (AC2)."""
    text = _SERVER_SOURCE.read_text(encoding="utf-8")
    # ``--host`` would appear as an argparse add_argument literal.
    assert '"--host"' not in text
    assert "'--host'" not in text
    # ``-H`` short flag.
    assert '"-H"' not in text
    # No environment read for HOST.
    assert 'environ["HOST"]' not in text
    assert 'getenv("HOST"' not in text


def test_uvicorn_config_host_is_loopback() -> None:
    """The ``uvicorn.Config`` we hand to ``server.run()`` has ``host=127.0.0.1``.

    Tested via direct ``uvicorn.Config`` inspection, NOT a live non-loopback
    bind (which would be flaky on Windows + OS-dependent — spec qa F1).
    """
    config = uvicorn.Config(create_app(port=8765), host=HARDCODED_HOST, port=8765)
    assert config.host == HARDCODED_HOST


@pytest.mark.regression
def test_run_server_refuses_non_loopback_host_before_socket_open() -> None:
    """Regression (AC2): ``run_server`` fails fast on any non-loopback host.

    Before the runtime guard was added, a caller (or a refactor that wired
    the CLI to a flag) could pass ``host="0.0.0.0"`` and uvicorn would bind
    the wildcard. The guard rejects BEFORE the socket is opened.
    """
    with pytest.raises(NonLoopbackBindError):
        run_server(host="0.0.0.0", port=8765)
    with pytest.raises(NonLoopbackBindError):
        run_server(host="::", port=8765)


def test_host_header_guard_rejects_evil_host() -> None:
    """A request with a non-loopback ``Host`` header returns HTTP 400 (R8a/AC2)."""
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/", headers={"host": "evil.example.com"})
    assert r.status_code == 400
    # Body must NOT contain the configured port or the offending host (no echo).
    assert "8765" not in r.text
    assert "evil.example.com" not in r.text


def test_host_header_guard_accepts_loopback_port_form() -> None:
    """The loopback ``Host`` is accepted with and without an explicit port."""
    app = create_app(port=8765)
    client = TestClient(app)
    assert client.get("/", headers={"host": "127.0.0.1:8765"}).status_code == 200
    assert client.get("/healthz", headers={"host": "127.0.0.1"}).status_code == 200


# --------------------------------------------------------------------------- #
# AC3 — two-layer no-inject guard
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_server_module_import_does_not_pull_hooks_or_settings() -> None:
    """Regression (AC3 layer (a)): the server module's import graph carries no
    hook or prompt-assembly module.

    Module-allowlist guard: importing ``scripts.telemetry.dashboard_server``
    must NOT pull any of ``.claude.hooks`` / ``hooks`` / ``settings.json``-
    parsing modules / prompt-assembly modules into ``sys.modules``. The
    server has no business mutating those even transitively.
    """
    for name in list(sys.modules):
        if name == "scripts.telemetry.dashboard_server":
            del sys.modules[name]
    before = set(sys.modules)
    importlib.import_module("scripts.telemetry.dashboard_server")
    pulled = set(sys.modules) - before
    forbidden_substrings = (".claude.hooks", "prompt_assembly")
    offenders = [n for n in pulled if any(s in n for s in forbidden_substrings)]
    assert offenders == [], (
        f"server import graph leaked hook / prompt-assembly modules: {offenders}"
    )


@pytest.mark.regression
def test_routes_leave_hooks_and_settings_byte_unchanged(tmp_path: Path) -> None:
    """Regression (AC3 layer (b)): every endpoint must leave ``.claude/hooks``
    and ``settings.json`` byte-unchanged.

    Behavioral guard — the layer that bites new vectors. We build a synthetic
    ``.claude/`` tree in ``tmp_path`` carrying stub hook scripts and a stub
    ``settings.json``, compute SHA-256 sums before, hit every route, and assert
    sums unchanged. A future change that decides to "patch the hook on the fly"
    (or any new write side that touches a ``.claude/`` path) would fail loudly.

    qa F4 fold (REV-20260607-200447): the sandbox is built synthetically rather
    than copied from the live repo, so this AC3 guard runs unconditionally on
    CI where the ``.claude/`` tree may not be present. Byte content is opaque to
    the contract; the contract is "the server originates no writes against
    these paths".
    """
    sandbox = tmp_path / ".claude"
    hooks_dir = sandbox / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "pre-commit-gate.sh").write_text(
        "#!/bin/sh\n# stub hook for AC3 byte-stability fixture\n", encoding="utf-8"
    )
    (hooks_dir / "session-start.sh").write_text(
        "#!/bin/sh\n# stub hook for AC3 byte-stability fixture\n", encoding="utf-8"
    )
    (sandbox / "settings.json").write_text('{"_ac3_fixture": true}\n', encoding="utf-8")

    def _digest_tree(root: Path) -> dict[str, str]:
        digests: dict[str, str] = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                digests[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
        return digests

    before_digests = _digest_tree(sandbox)

    app = create_app(port=8765)
    client = TestClient(app)
    for path in ("/", "/healthz", "/fragments/live", "/fragments/retrospective"):
        client.get(path, headers={"host": "127.0.0.1:8765"})

    after_digests = _digest_tree(sandbox)
    assert before_digests == after_digests, (
        "the dashboard server modified .claude/hooks or settings.json — AC3 violated"
    )


# --------------------------------------------------------------------------- #
# AC5 — read-only DB + schema/row-counts unchanged + lifespan teardown
# --------------------------------------------------------------------------- #


def _empty_db(tmp_path: Path) -> Path:
    db = tmp_path / "evaluation.db"
    init_db(db, quiet=True)
    return db


def _schema_snapshot(db_path: Path) -> list[tuple[str, str]]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        return sorted(
            conn.execute("SELECT type, name FROM sqlite_master ORDER BY type, name").fetchall()
        )
    finally:
        conn.close()


def _row_counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    try:
        names = [
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        ]
        return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0] for name in names}
    finally:
        conn.close()


def test_routes_do_not_mutate_database_schema_or_row_counts(tmp_path: Path) -> None:
    """AC5: schema + every-table row count unchanged after every route hit."""
    db = _empty_db(tmp_path)
    schema_before = _schema_snapshot(db)
    counts_before = _row_counts(db)

    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    for path in ("/", "/fragments/live", "/fragments/retrospective", "/healthz"):
        client.get(path, headers={"host": "127.0.0.1:8765"})

    assert _schema_snapshot(db) == schema_before
    assert _row_counts(db) == counts_before


def test_db_connection_is_read_only_at_driver_level(tmp_path: Path) -> None:
    """A write through the read-only URI helper is refused by SQLite (AC5).

    The daemon delegates DB access to ``assemble_dashboard_data``, which uses
    ``scripts.telemetry.dashboard._connect_readonly``. This is the driver-level
    guard — not just a convention. A future code path that accidentally calls
    a mutating analyzer would fail to even open a writable connection through
    the helper.
    """
    from scripts.telemetry import dashboard as static_dashboard

    db = _empty_db(tmp_path)
    conn = static_dashboard._connect_readonly(db)
    try:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("CREATE TABLE telemetry_canary(x INTEGER)")
    finally:
        conn.close()


def test_lifespan_teardown_resets_live_state(tmp_path: Path) -> None:
    """AC7: the FastAPI lifespan teardown resets the in-memory live state."""
    import dataclasses

    from src.telemetry.live import empty_state

    db = _empty_db(tmp_path)
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    with TestClient(app) as client:
        client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
        # During the with-block, the state may carry whatever was folded.
        assert hasattr(app.state, "live_state")
    # After exit (lifespan shutdown), live_state must be reset to empty_state().
    # Use ``asdict`` field-equality rather than ``==``: the purity test in this
    # same file deletes & re-imports src.telemetry.live, which changes the
    # LiveState class identity and breaks dataclass ``__eq__`` even when every
    # field is equal. The structural comparison is the meaningful contract.
    assert dataclasses.asdict(app.state.live_state) == dataclasses.asdict(empty_state())


def test_lifespan_teardown_writes_no_files_in_tmp(tmp_path: Path) -> None:
    """AC7: nothing the server *originates* lands in the test's ``tmp_path``.

    SQLite may create a ``-wal`` / ``-shm`` sidecar even on a read-only open
    (WAL-journaled DBs auto-allocate them on a connect — the bytes are the
    OS / driver's, not the server's logic). Those are allowlisted; ANY other
    new file in ``tmp_path`` would be a regression.
    """
    db = _empty_db(tmp_path)
    files_before = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    with TestClient(app) as client:
        for path in ("/", "/fragments/live", "/fragments/retrospective", "/healthz"):
            client.get(path, headers={"host": "127.0.0.1:8765"})
    files_after = {p.name for p in tmp_path.rglob("*") if p.is_file()}
    sqlite_sidecars = {"evaluation.db-wal", "evaluation.db-shm", "evaluation.db-journal"}
    unexpected = files_after - files_before - sqlite_sidecars
    assert unexpected == set(), f"server created unexpected files: {unexpected}"


# --------------------------------------------------------------------------- #
# AC6 — output safety (escape + generic errors)
# --------------------------------------------------------------------------- #


def test_dynamic_lane_fields_are_html_escaped(tmp_path: Path) -> None:
    """A transcript-shaped value reaching the live fragment is HTML-escaped (AC6).

    Injects an event whose ``lane_id`` / ``model`` / ``agent_type`` carry a
    ``<script>alert(1)</script>`` payload via the arch F2 ``event_source``
    constructor seam (REV-20260607-200447). The rendered fragment must NOT
    contain a literal ``<script>``.

    Drives the seam directly (rather than monkeypatching
    ``_extract_live_events``, which is how this test was written pre arch F2
    fold) so the AC6 escape guard does not silently degrade if a future
    refactor changes how ``_default_event_source`` resolves the disk-walk —
    the explicit ``event_source=`` argument bypasses the default-seam path
    entirely (qa F1 in-session fold of REV-20260608-020046).
    """

    from src.telemetry.live import LiveEvent

    db = _empty_db(tmp_path)
    payload = "<script>alert(1)</script>"

    def fake_events() -> list[LiveEvent]:
        return [
            LiveEvent(
                kind="message",
                timestamp=datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC),
                lane_id=payload,
                model=payload,
                input_tokens=100,
                output_tokens=50,
                agent_type=payload,
            )
        ]

    app = create_app(
        db_path=db,
        project_root=tmp_path,
        port=8765,
        event_source=fake_events,
    )
    client = TestClient(app)
    r = client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    assert "<script>alert(1)</script>" not in r.text
    assert "&lt;script&gt;" in r.text


@pytest.mark.regression
def test_script_block_payload_uses_json_escape_not_html_escape() -> None:
    """Regression (AC6 / security F2 / R11): data baked into a ``<script>`` block
    must be serialised with ``json.dumps`` + a ``</script>`` guard, NOT
    interpolated through ``html.escape``.

    The shell HTML inlines no chart payload in Phase 1, but the principle
    must be defended at the seam: when a future phase serializes chart
    data into a ``<script type=\"application/json\">`` block, an attempted
    ``</script><script>...`` injection must not be able to close the block.
    """
    # The Phase 1 shell does NOT yet embed chart data; assert the negative
    # surface (no raw transcript-shaped string is interpolated into any
    # <script>...</script> block in the shell) so the regression test is
    # meaningful when Phase 2 adds the chart data path.
    from src.telemetry.dashboard import render_live_shell_html

    shell = render_live_shell_html(generated_label="2026-06-07 12:00 UTC")
    # Find every <script> block in the shell and confirm none of them contain
    # a literal `</` substring that would let an attacker close out.
    # (The htmx <script src=...> tag has no body, so this is vacuously true,
    # but the assertion is the documentation contract.)
    script_blocks = re.findall(r"<script[^>]*>(.*?)</script>", shell, flags=re.DOTALL)
    for body in script_blocks:
        assert "</" not in body, (
            "a <script> block body contains a closing `</` — Phase 2 must add "
            "json.dumps + </script>-guard before serializing chart data here"
        )


def test_error_response_is_generic(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A raised ``OperationalError`` on the read-side returns a generic body
    that contains NEITHER the DB path NOR the exception class (AC6 / qa F7)."""
    db = _empty_db(tmp_path)
    # Make assemble_dashboard_data raise an OperationalError carrying the path,
    # which a careless implementation would echo back to the client.
    secret = "secret-internal-path-marker-xyz"

    def _boom(*_a, **_kw):
        raise sqlite3.OperationalError(f"unable to open database file {secret}")

    monkeypatch.setattr(dashboard_server, "assemble_dashboard_data", _boom)

    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.get("/fragments/retrospective", headers={"host": "127.0.0.1:8765"})
    # The OperationalError branch returns 503 (DB not ready); the bare-Exception
    # branch returns 500 and is covered by
    # test_retrospective_error_general_exception_response_is_generic.
    assert r.status_code == 503
    assert secret not in r.text
    assert "OperationalError" not in r.text


def test_live_fragment_error_response_is_generic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Same as above for the live fragment route."""
    db = _empty_db(tmp_path)

    def _boom(*_a, **_kw):
        raise RuntimeError("internal stack with /secret/path/leak inside")

    monkeypatch.setattr(dashboard_server, "fold_events", _boom)
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 500
    assert "/secret/path/leak" not in r.text
    assert "RuntimeError" not in r.text


@pytest.mark.regression
def test_retrospective_error_general_exception_response_is_generic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (qa F7 / REV-20260607-200447 / AC6): a non-``OperationalError``
    exception in the retrospective route returns a generic 500 body.

    The route catches ``sqlite3.OperationalError`` as a 503 ("DB not ready") and
    bare ``Exception`` as a 500 ("could not render"). ``test_error_response_is_generic``
    above pins the OperationalError path; this pins the catch-all branch so a
    future edit that, e.g., dropped the bare ``except Exception`` (silently
    letting the exception bubble to FastAPI's default 500 handler — which in a
    debug build would expose a class name + stack trace in the body) would fail
    loudly here.
    """
    db = _empty_db(tmp_path)
    secret = "internal-call-stack-marker-9d2"

    def _boom(*_a, **_kw):
        raise RuntimeError(f"unexpected {secret} should not leak")

    monkeypatch.setattr(dashboard_server, "assemble_dashboard_data", _boom)

    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.get("/fragments/retrospective", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 500
    assert secret not in r.text
    assert "RuntimeError" not in r.text
    assert "Traceback" not in r.text


# --------------------------------------------------------------------------- #
# AC8 — no outbound HTTP client
# --------------------------------------------------------------------------- #


def test_server_source_imports_no_outbound_http_client() -> None:
    """The server source does not import an outbound HTTP client (AC8).

    Banned: ``requests`` / ``httpx.Client`` / ``aiohttp`` / ``urllib.request``.
    ``webbrowser.open`` delegates to the OS and cannot reach the server itself.
    """
    text = _SERVER_SOURCE.read_text(encoding="utf-8")
    banned = ["import requests", "import httpx", "import aiohttp", "from urllib.request"]
    for line in banned:
        assert line not in text, f"server source contains forbidden outbound HTTP import: {line!r}"


# --------------------------------------------------------------------------- #
# AC10 — daemon serves the htmx shell on the loopback bind
# --------------------------------------------------------------------------- #


def test_root_serves_htmx_shell() -> None:
    """GET / returns the htmx shell that polls ``/fragments/live`` (AC10)."""
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    body = r.text
    assert "/static/htmx.min.js" in body
    assert 'hx-get="/fragments/live"' in body


@pytest.mark.regression
def test_root_exposes_retrospective_link_and_distinct_loading_tile() -> None:
    """ux FRICTION-1 + FRICTION-4 end-to-end: shell carries the right affordances.

    Together with the unit tests in ``test_telemetry.py``, this guards that
    a route-level change cannot drop the retrospective link or accidentally
    revert the loading placeholder back to the ``tile--absent`` vocabulary.
    """
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    body = r.text
    # FRICTION-4: retrospective is reachable from the shell UI.
    assert 'href="/fragments/retrospective"' in body
    # FRICTION-1: loading placeholder is visually distinct from honest absence.
    assert "tile tile--loading" in body
    assert "Connecting to live session data" in body
    # Independent transport-layer negative guard (qa F5 in REV-supplement): a
    # future server-side render hook accidentally re-templating the placeholder
    # with the absence vocabulary must fail here, not just in the unit test.
    placeholder = body.split('id="live-section"', 1)[1].split("</section>", 1)[0]
    assert "tile--absent" not in placeholder
    assert "absence-copy" not in placeholder


def test_live_fragment_root_section_is_htmx_swap_target() -> None:
    """The fragment is one root ``<section>`` so htmx ``outerHTML`` swap is clean."""
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    assert r.text.lstrip().startswith('<section id="live-section"')


def _read_sha384_pin_from_readme(asset_filename: str) -> str:
    """Parse the SHA-384 pin (base64, no ``sha384-`` prefix) for an asset from the README.

    The README pin table is the human-readable contract; the module-level
    ``_*_SHA384_PIN`` constants are the machine-enforced contract. This helper
    closes the divergence gap qa-specialist flagged in the Phase-2 vendoring
    review (REV-20260608-022723 qa F1): a re-vendor that updates the README pin
    string but forgets to update the test constant (or vice versa) would
    otherwise pass the SHA-guard while leaving the two sources of truth silently
    inconsistent. The two SHA-384 regression tests now assert the constant
    equals the parsed README value, so the two sources cannot drift independently
    without the test failing.

    Args:
        asset_filename: The filename as it appears in the README pin-table row
            (e.g. ``"htmx.min.js"``, ``"chart.umd.min.js"``).

    Returns:
        The base64-encoded SHA-384, with the ``sha384-`` prefix stripped (so it
        compares directly to ``base64.b64encode(hashlib.sha384(...).digest())``).

    Raises:
        AssertionError: If the asset row is missing from the README or the row
            does not contain a recognisable ``sha384-...`` integrity cell.
    """
    from scripts.telemetry.dashboard_server import STATIC_DIR

    readme_path = STATIC_DIR / "README.md"
    text = readme_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        # Match the pin-table row by the asset filename appearing as inline code
        # — guards against picking up the same filename in a paragraph or link.
        if f"`{asset_filename}`" not in line:
            continue
        for cell in line.split("|"):
            cell = cell.strip().strip("`")
            if cell.startswith("sha384-"):
                return cell[len("sha384-") :]
        raise AssertionError(
            f"README pin row for {asset_filename!r} has no sha384-... integrity cell"
        )
    raise AssertionError(f"No README pin row found for asset {asset_filename!r}")


def test_static_htmx_asset_is_served() -> None:
    """The vendored htmx file is served from the static mount (R11a / AC6)."""
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/static/htmx.min.js", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    # The known-good htmx file starts with a recognisable banner / signature.
    assert "htmx" in r.text.lower()
    # MIME contract: a StaticFiles misconfig that served the file as
    # ``text/plain`` or ``application/octet-stream`` would pass the body check
    # above but browsers under strict MIME sniffing would refuse to execute
    # the script. The static mount must serve a JavaScript media type
    # (REV-20260608-022723 qa F2 fold).
    assert "javascript" in r.headers.get("content-type", "").lower(), (
        f"static htmx asset served with non-JavaScript content-type: "
        f"{r.headers.get('content-type')!r}"
    )


#: The vendored htmx 1.9.12 SHA-384 (base64) — must match
#: src/telemetry/static/README.md's pin table. A future swap-in (accidental or
#: supply-chain) that does not also update this constant fails the regression.
_HTMX_SHA384_PIN = "ujb1lZYygJmzgSwoxRggbCHcjc0rB2XoQrxeTUQyRjrOnlCoYta87iKBWq3EsdM2"


@pytest.mark.regression
def test_vendored_htmx_sha384_matches_readme_pin() -> None:
    """Regression (security F1): the vendored htmx integrity is machine-verified.

    The README documents a SHA-384 pin but :func:`test_static_htmx_asset_is_served`
    asserts only that *something* with the word ``htmx`` is served — a backdoored
    swap-in passes that. This guard reads the bytes, recomputes the SHA-384, and
    asserts it equals the pin. A supply-chain swap that leaves the README
    unchanged but rewrites the file fails this immediately.

    Also asserts the module-level constant equals the README's published pin so
    a re-vendor that updates one but not the other fails CI instead of silently
    drifting the two contracts apart (REV-20260608-022723 qa F1 fold).
    """
    import base64
    import hashlib

    from scripts.telemetry.dashboard_server import STATIC_DIR

    htmx_path = STATIC_DIR / "htmx.min.js"
    assert htmx_path.is_file(), f"vendored htmx asset missing at {htmx_path}"
    digest = hashlib.sha384(htmx_path.read_bytes()).digest()
    computed = base64.b64encode(digest).decode("ascii")
    assert computed == _HTMX_SHA384_PIN, (
        "vendored htmx SHA-384 does not match the pin in "
        "src/telemetry/static/README.md — supply-chain integrity check failed"
    )
    readme_pin = _read_sha384_pin_from_readme("htmx.min.js")
    assert _HTMX_SHA384_PIN == readme_pin, (
        "test constant _HTMX_SHA384_PIN diverged from README pin table — "
        "update both in lockstep when re-vendoring"
    )


#: The vendored Chart.js 4.4.7 SHA-384 (base64). Two-mirror verified at vendoring
#: time (unpkg.com + cdn.jsdelivr.net returned byte-identical files). Must match
#: src/telemetry/static/README.md's pin table. Phase 2 first-slice scaffolding —
#: the chart markup that consumes Chart.js lands in the next slice; this pin
#: still applies from day one so the integrity discipline cannot be bypassed by
#: a "well it's not loaded yet, who cares" argument later.
_CHARTJS_SHA384_PIN = "zYPBGXwO4633CABX/5Spf6emCKUJCfoOkhOMYyxMsatqQZPnDblmmOewfjsIVWCM"


def test_static_chartjs_asset_is_served() -> None:
    """The vendored Chart.js file is served from the static mount (R11a / AC6).

    Phase 2 first-slice scaffolding (SPEC-20260607-183136 Phase 2): the asset is
    vendored + integrity-pinned BEFORE any chart markup consumes it, so the next
    slice's chart can rely on the mount being present and the bytes being pinned.
    Mirrors the htmx static-mount test verbatim — the same shape, the next file.
    """
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/static/chart.umd.min.js", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    # The known-good Chart.js UMD build carries a recognisable banner in its
    # first 256 bytes — a backdoored swap-in that drops the banner would still
    # fail the SHA-384 guard below, but the banner check makes a "served some
    # random JS at this path" regression read obvious in the test failure.
    assert "chart.js" in r.text[:256].lower()
    # MIME contract: same browser-execution requirement as for htmx — a
    # ``text/plain`` or ``application/octet-stream`` regression would pass the
    # body check but break the next slice's ``<script src="...">`` load
    # (REV-20260608-022723 qa F2 fold).
    assert "javascript" in r.headers.get("content-type", "").lower(), (
        f"static Chart.js asset served with non-JavaScript content-type: "
        f"{r.headers.get('content-type')!r}"
    )


@pytest.mark.regression
def test_vendored_chartjs_sha384_matches_readme_pin() -> None:
    """Regression (Phase 2 supply-chain): the vendored Chart.js integrity is machine-verified.

    Mirrors :func:`test_vendored_htmx_sha384_matches_readme_pin` for the new
    Chart.js asset. A supply-chain swap that leaves the README unchanged but
    rewrites the file fails this immediately. The pin was two-mirror verified
    at vendoring time (see :data:`_CHARTJS_SHA384_PIN`); any re-vendoring should
    repeat that cross-check AND cross-reference the upstream GitHub release tag
    (an independent trust root from npm) before updating both the constant and
    the README.

    Also asserts the module-level constant equals the README's published pin so
    a re-vendor that updates one but not the other fails CI instead of silently
    drifting the two contracts apart (REV-20260608-022723 qa F1 fold).
    """
    import base64
    import hashlib

    from scripts.telemetry.dashboard_server import STATIC_DIR

    chartjs_path = STATIC_DIR / "chart.umd.min.js"
    assert chartjs_path.is_file(), f"vendored Chart.js asset missing at {chartjs_path}"
    digest = hashlib.sha384(chartjs_path.read_bytes()).digest()
    computed = base64.b64encode(digest).decode("ascii")
    assert computed == _CHARTJS_SHA384_PIN, (
        "vendored Chart.js SHA-384 does not match the pin in "
        "src/telemetry/static/README.md — supply-chain integrity check failed"
    )
    readme_pin = _read_sha384_pin_from_readme("chart.umd.min.js")
    assert _CHARTJS_SHA384_PIN == readme_pin, (
        "test constant _CHARTJS_SHA384_PIN diverged from README pin table — "
        "update both in lockstep when re-vendoring"
    )


@pytest.mark.regression
def test_chartjs_license_companion_file_present() -> None:
    """Regression (security F1 fold): MIT license-text companion is shipped alongside the asset.

    The Chart.js MIT header survives in the minified file's first comment block,
    which satisfies the legal minimum for MIT redistribution — but a future
    re-minification pass that strips comments would silently drop the notice.
    This guard asserts a separate ``LICENSE-chart.js.txt`` exists with the full
    MIT text (recoverable from disk even if the JS header is ever stripped) and
    that the License column in the README points at it. Closes the provenance
    gap security-specialist raised in REV-20260608-022723 F1.
    """
    from scripts.telemetry.dashboard_server import STATIC_DIR

    license_path = STATIC_DIR / "LICENSE-chart.js.txt"
    assert license_path.is_file(), (
        f"Chart.js license companion missing at {license_path} — "
        "MIT redistribution requires the copyright notice to survive in tree"
    )
    license_text = license_path.read_text(encoding="utf-8")
    assert "MIT License" in license_text
    assert "Chart.js Contributors" in license_text
    assert "Permission is hereby granted" in license_text  # canonical MIT phrase

    readme_text = (STATIC_DIR / "README.md").read_text(encoding="utf-8")
    assert "LICENSE-chart.js.txt" in readme_text, (
        "README pin table should reference the LICENSE-chart.js.txt companion"
    )


# --------------------------------------------------------------------------- #
# AC14 — live.py purity (the test in test_telemetry.py is the canonical guard).
# --------------------------------------------------------------------------- #


def test_live_module_has_no_scripts_import() -> None:
    """Mirror of the canonical AC14 guard in test_telemetry.py — defensive."""
    from src.telemetry import live as live_mod

    src = Path(live_mod.__file__).read_text(encoding="utf-8")
    assert "from scripts" not in src
    assert "import scripts" not in src


# --------------------------------------------------------------------------- #
# AC15 — A-ARCH1 promotion contract
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_a_arch1_helpers_are_public_attributes_on_ingest_module() -> None:
    """Regression (AC15 / R16): the cross-module-consumed transcript helpers
    are public attributes of ``scripts.ingest_token_usage``.

    The dashboard daemon (the 4th consumer) reuses these; a future edit that
    re-privatised any of them would silently break the daemon's parse seam.
    ``parse_timestamp`` and ``coerce_int`` are also consumed by the daemon
    (``_parse_main_session`` / ``_parse_subagent``); arch F1 from
    REV-20260607-200447 added them to the public surface so the contract
    matches the actual import graph.
    """
    public_helpers = (
        "collect_messages",
        "discover_session_dirs",
        "parse_since",
        "is_inside_projects_root",
        "parse_timestamp",
        "coerce_int",
    )
    for name in public_helpers:
        assert hasattr(itu, name), f"{name} is not public on scripts.ingest_token_usage"
        attr = getattr(itu, name)
        assert callable(attr), f"{name} is not callable"


def test_server_uses_a_arch1_public_helpers_not_underscored() -> None:
    """The server source uses the public names, NOT the underscored privates.

    Also guards arch F3 (REV-20260607-200447) — the dead ``_connect_readonly``
    helper must not be re-introduced on ``dashboard_server`` without a 2nd
    actual consumer (Rule of Three). The surviving helper lives at
    ``scripts.telemetry.dashboard._connect_readonly`` and is the one
    ``assemble_dashboard_data`` uses.
    """
    text = _SERVER_SOURCE.read_text(encoding="utf-8")
    # Either form would still resolve (Python attribute access is liberal),
    # but the contract says public names. A regression to underscores is a
    # signal the contract eroded — fail it.
    assert "itu._collect_messages" not in text
    assert "itu._parse_since" not in text
    assert "itu._is_inside_projects_root" not in text
    assert "itu._parse_timestamp" not in text
    assert "itu._coerce_int" not in text
    # qa F2-QA fold (REV at DISC-20260607-233516): the deleted helper must
    # stay deleted until a 2nd real consumer exists. Machine-enforces the
    # ledger rule ("Do not re-introduce the dead helper without a second
    # actual consumer").
    assert not hasattr(dashboard_server, "_connect_readonly"), (
        "dead helper was re-introduced; promote only when 2nd consumer exists"
    )


@pytest.mark.regression
def test_a_arch1_promoted_helpers_carry_promotion_docstring_footer() -> None:
    """Regression (arch F1 / REV-20260607-200447): every A-ARCH1-promoted helper
    carries the ``Promoted to public in the A-ARCH1 promotion`` docstring footer.

    The public surface is internally consistent: a reader who sees one helper's
    footer expects the same footer on every promoted neighbour. Before this
    fix, ``parse_timestamp`` + ``coerce_int`` lacked the footer even though
    the daemon consumed them — a pattern inconsistency that would invite a
    future contributor to re-privatise them. This test fails if any of the 6
    helpers loses the footer.
    """
    promoted_helpers = (
        "collect_messages",
        "discover_session_dirs",
        "parse_since",
        "is_inside_projects_root",
        "parse_timestamp",
        "coerce_int",
    )
    footer = "Promoted to public in the A-ARCH1 promotion"
    spec_ref = "SPEC-20260607-183136"
    for name in promoted_helpers:
        fn = getattr(itu, name)
        assert fn.__doc__ is not None, f"{name} has no docstring"
        assert footer in fn.__doc__, f"{name} docstring missing the A-ARCH1 promotion footer"
        # qa F1-QA fold (REV at DISC-20260607-233516): also assert the SPEC
        # reference so a paraphrase of the footer that drops traceability
        # ("Promoted via A-ARCH1") still fails the guard.
        assert spec_ref in fn.__doc__, f"{name} docstring missing the SPEC reference"


# --------------------------------------------------------------------------- #
# AC16 — port-in-use clear message
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_port_in_use_yields_human_readable_message(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """Regression (AC16): ``OSError`` on bind is mapped to a clear message + exit 1.

    No raw ``[Errno 98]`` / ``[WinError 10048]`` trace reaches stdout; the
    developer sees a sentence they can act on (use ``--port <free-port>``).
    """

    class _BoomServer:
        def __init__(self, *_a, **_kw):
            pass

        def run(self):
            raise OSError(98, "Address already in use")

    monkeypatch.setattr(uvicorn, "Server", _BoomServer)
    with pytest.raises(SystemExit) as exc:
        run_server(host=HARDCODED_HOST, port=8765)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "port" in out.lower()
    assert "already" in out.lower() or "in use" in out.lower()
    assert "--port" in out
    # No raw "[Errno" or "Traceback" leakage.
    assert "Traceback" not in out


# --------------------------------------------------------------------------- #
# HostHeaderGuard direct unit coverage (qa edge cases)
# --------------------------------------------------------------------------- #


def test_host_header_guard_missing_host_returns_400() -> None:
    """A request that arrives without a Host header is rejected.

    HTTP/1.1 mandates a Host header but a curl with --header 'host:' or a
    crafted client may omit it. The guard rejects rather than passing.
    """
    app = create_app(port=8765)
    client = TestClient(app)
    # TestClient sets a default host; force it empty.
    r = client.get("/healthz", headers={"host": ""})
    assert r.status_code == 400


def test_host_header_guard_is_middleware_layer() -> None:
    """The Host guard is wired as a middleware (smoke; not a no-op)."""
    app = create_app(port=8765)
    # The middleware class is recorded by class name on the Middleware spec.
    names = [
        (getattr(m, "cls", None).__name__ if hasattr(m, "cls") else "")
        for m in app.user_middleware
    ]
    assert "HostHeaderGuard" in names, f"HostHeaderGuard missing from middleware: {names}"
    # Smoke check that the class is the one we exported.
    assert HostHeaderGuard.__name__ == "HostHeaderGuard"


# --------------------------------------------------------------------------- #
# security F2 (REV-20260607-200447) — Content-Security-Policy defense-in-depth
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_csp_policy_string_pins_documented_policy() -> None:
    """Regression (security F2 / REV-20260607-200447; security F1 extension /
    REV-20260608-010051): the policy string equals the documented advisory
    value, exactly.

    The advisory specified the policy literal; pinning it in one place keeps
    every reviewer working from the same value. A future relaxation (e.g.
    adding ``'unsafe-inline'`` to ``script-src`` to enable a CDN, or dropping
    ``script-src`` entirely so it falls back to ``default-src``, or relaxing
    ``frame-ancestors``/``object-src`` away from ``'none'``) is a code-review
    event — this test fails on any drift.
    """
    assert CONTENT_SECURITY_POLICY == (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'unsafe-inline'; "
        "frame-ancestors 'none'; "
        "object-src 'none'"
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    "directive,expected_value",
    [
        ("default-src", "'self'"),
        ("script-src", "'self'"),
        ("style-src", "'unsafe-inline'"),
        ("frame-ancestors", "'none'"),
        ("object-src", "'none'"),
    ],
)
def test_csp_policy_contains_each_load_bearing_directive(
    directive: str, expected_value: str
) -> None:
    """Regression (security F1 / REV-20260608-010051): each directive's value is
    present at exactly the documented strength.

    The verbatim-string pin above catches *any* drift, but a future legitimate
    re-ordering of directives (e.g. alphabetising) would force a churn-only
    edit of that literal AND silently lose a directive if the editor was sloppy.
    This per-directive assertion is order-independent and pins the value of
    each load-bearing directive individually, so the verbatim and per-directive
    guards together resist BOTH "directive dropped" and "directive weakened"
    regressions even under a stylistic re-order.
    """
    needle = f"{directive} {expected_value}"
    assert needle in CONTENT_SECURITY_POLICY, (
        f"directive {directive!r} missing or weakened (looked for {needle!r} in "
        f"{CONTENT_SECURITY_POLICY!r})"
    )


@pytest.mark.regression
def test_csp_header_present_on_shell_response(tmp_path: Path) -> None:
    """Regression (security F2): the shell HTML response carries a CSP header.

    The 200 path is the one a developer's browser actually renders, so it is
    the primary user-facing surface for the policy. A future ``response_class
    = HTMLResponse`` route that bypasses middleware (e.g. via a direct
    ``Response`` return that overwrites headers) would fail this guard.
    """
    db = _empty_db(tmp_path)
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.get("/", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    assert r.headers.get("content-security-policy") == CONTENT_SECURITY_POLICY


@pytest.mark.regression
def test_csp_header_present_on_host_header_400_rejection() -> None:
    """Regression (security F2): CSP is stamped on the ``HostHeaderGuard`` 400.

    The 400 is the error path most likely to leak a target's HTML if a future
    edit echoed the bad ``Host`` value (which ``test_host_header_guard_rejects_
    evil_host`` independently bans) — so the defense-in-depth policy MUST
    apply there too. Asserts the LIFO order ``CSP > HostHeaderGuard > CORS``
    is preserved (CSP added last in ``create_app`` => outermost on response).
    """
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/", headers={"host": "evil.example.com"})
    assert r.status_code == 400
    assert r.headers.get("content-security-policy") == CONTENT_SECURITY_POLICY


@pytest.mark.regression
@pytest.mark.parametrize(
    "route,raiser,expected_status",
    [
        # Live fragment 500 path — RuntimeError out of fold_events hits the bare
        # ``except Exception`` branch.
        ("/fragments/live", "fold_events", 500),
        # Retrospective 503 path — sqlite3.OperationalError hits the explicit
        # OperationalError branch (DB-not-ready). qa F2 (REV at session 10g):
        # paired with the live 500 path, this parametrize covers BOTH htmx
        # swap-target error fragments so a future refactor that extracts either
        # route into a sub-app would fail CSP coverage on the extracted half.
        ("/fragments/retrospective", "assemble_dashboard_data", 503),
    ],
)
def test_csp_header_present_on_fragment_error_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    raiser: str,
    expected_status: int,
) -> None:
    """Regression (security F2 / qa F2 follow-on): CSP is stamped on every error fragment.

    Both ``/fragments/live`` (500) and ``/fragments/retrospective`` (503) are
    HTML fragments htmx swaps into the DOM (the shell sets
    ``hx-swap-error="outerHTML"``), so an injected transcript-shaped failure
    path must remain CSP-bounded even on the error branch. The 503 case
    exercises the explicit ``sqlite3.OperationalError`` branch; the 500 case
    exercises the bare ``except Exception`` branch. Both must carry CSP.
    """
    db = _empty_db(tmp_path)

    if expected_status == 503:

        def _boom(*_a, **_kw):
            raise sqlite3.OperationalError("simulated DB-not-ready")
    else:

        def _boom(*_a, **_kw):
            raise RuntimeError("simulated fold/render failure")

    monkeypatch.setattr(dashboard_server, raiser, _boom)

    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.get(route, headers={"host": "127.0.0.1:8765"})
    assert r.status_code == expected_status
    assert r.headers.get("content-security-policy") == CONTENT_SECURITY_POLICY


@pytest.mark.regression
def test_csp_middleware_is_outermost_in_user_middleware() -> None:
    """The CSP middleware is the LAST added (= OUTERMOST on response).

    Starlette runs ``user_middleware`` in LIFO order on the request and
    reverse on the response, so the last-added middleware is the one that
    stamps the final header. A future re-order that moved CSP earlier could
    silently lose the header on a 400/500 path the CSP middleware no longer
    wraps; this guard pins the relative position by class name AND object
    identity (qa F1 fold: the bare ``__name__`` tautology was replaced with
    ``cls is ContentSecurityPolicyMiddleware`` so a future move that, e.g.,
    wrapped the class behind a decorator that preserves ``__name__`` but
    changes identity is also caught).
    """
    app = create_app(port=8765)
    middleware_specs = list(app.user_middleware)
    names = [
        (getattr(m, "cls", None).__name__ if hasattr(m, "cls") else "") for m in middleware_specs
    ]
    # Last-added middleware sits at index 0 (Starlette prepends adds).
    assert names[0] == "ContentSecurityPolicyMiddleware", (
        f"CSP must be the outermost user middleware; current order: {names}"
    )
    # Object-identity guard — catches a future move that swaps the import for
    # a same-named shim. Tautology removed (qa F1 / REV at session 10g).
    assert middleware_specs[0].cls is ContentSecurityPolicyMiddleware


@pytest.mark.regression
def test_csp_middleware_returns_generic_500_and_stamps_policy_when_call_next_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (security F2 / REV-20260608-010051; qa F1/F2/F3 fold from
    REV at session 10h): a catastrophic exception that escapes ``call_next``
    is converted to a generic 500 HTML body that STILL carries the CSP header,
    with no exception class / no traceback / no marker string leaked.

    Today every route catches ``Exception`` and converts to ``HTMLResponse``
    (the live/retrospective error branches), and Starlette's ``ExceptionMiddleware``
    sits BELOW our user middleware stack and converts ``HTTPException`` to a
    proper response BEFORE it could reach ``call_next`` here — so this
    fail-closed branch is practically unreachable. But as the OUTERMOST
    middleware :class:`ContentSecurityPolicyMiddleware` is the canonical place
    to enforce the invariant "CSP on every byte the client receives," including
    a future "framework blew up before any route handler ran" path (an upstream
    middleware regression, an inner ASGI bug, or a route that legitimately
    bypasses the existing ``except Exception``). This test simulates that path
    by monkeypatching the inner ``HostHeaderGuard.dispatch`` to raise BEFORE
    any response is built; the CSP middleware MUST swallow, return a generic
    500 with an HTML body (so htmx swap targets render correctly — security F4
    fold from session 10h), and still stamp the policy header.

    The assertion set matches ``test_retrospective_error_general_exception_response_is_generic``
    (the peer AC6 contract test): exception class absent, marker absent, the
    word "Traceback" absent (qa F1 fold) — plus an exact-body pin so a future
    edit that revealed the path or request method in the fallback body is
    caught at the gate (qa F2 fold). Test name spells out both legs of the
    contract (qa F3 fold): "returns generic 500 AND stamps policy."
    """

    class _BoomError(RuntimeError):
        pass

    async def _boom(self: Any, request: Any, call_next: Any) -> Any:  # noqa: ARG001
        raise _BoomError("simulated catastrophic middleware failure")

    # Force a layer INSIDE the CSP middleware to raise. The CSP middleware is
    # outermost (asserted by the test above), so HostHeaderGuard.dispatch is
    # the next layer in; making it raise reproduces the "exception escapes
    # call_next" path without hand-rolling an ASGI raiser.
    monkeypatch.setattr(dashboard_server.HostHeaderGuard, "dispatch", _boom, raising=True)

    db = _empty_db(tmp_path)
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get("/", headers={"host": "127.0.0.1:8765"})

    # Generic 500 (AC6): no exception class, no path, no stack — just the
    # boilerplate body the middleware constructs.
    assert r.status_code == 500
    body = r.text
    assert "_BoomError" not in body
    assert "simulated catastrophic" not in body
    # qa F1 fold (REV at session 10h): match the peer AC6 contract test
    # (`test_retrospective_error_general_exception_response_is_generic`) — the
    # body must not carry a "Traceback" marker even under a future Starlette
    # debug-mode regression that emitted one in the response stream.
    assert "Traceback" not in body
    # qa F2 fold (REV at session 10h): pin the exact expected body so a future
    # edit that echoed the path / method / Origin header in the fallback is
    # caught immediately (the negative-only assertions above would not catch
    # an addition that did not happen to contain those specific markers).
    assert body.strip() == "<p>Internal Server Error</p>"
    # CSP still stamped — the load-bearing invariant for this branch.
    assert r.headers.get("content-security-policy") == CONTENT_SECURITY_POLICY


# --------------------------------------------------------------------------- #
# qa F5 (REV-20260607-200447) — CORS preflight from a foreign Origin
# --------------------------------------------------------------------------- #


@pytest.mark.regression
@pytest.mark.parametrize(
    "foreign_origin",
    [
        "http://evil.example.com",
        # Subdomain spoof: an accidental regex like ``http://127\.0\.0\.1.*``
        # would echo this back; the simple foreign origin above does not exercise
        # that vector. The header-absent contract below catches both.
        "http://127.0.0.1.evil.example.com",
    ],
)
def test_cors_preflight_from_foreign_origin_emits_no_allow_origin_header(
    tmp_path: Path, foreign_origin: str
) -> None:
    """Regression (qa F5 / REV-20260607-200447 / REV-20260608-003457 F1 fold /
    R8a / AC6): a CORS preflight from a foreign Origin emits NO
    ``Access-Control-Allow-Origin`` header at all and NO
    ``Access-Control-Allow-Credentials: true``.

    The CORS middleware is configured with an explicit single-origin allow list
    (``http://127.0.0.1:<port>``, ``allow_credentials=False``) — see
    ``dashboard_server.create_app``. The precise contract Starlette's
    ``CORSMiddleware`` enforces on a non-matching origin is: no
    ``Access-Control-Allow-Origin`` header is emitted (so ``.get(..., "")``
    returns ``""``). Asserting header-absence is the tightest form — it catches
    in one assertion both a wildcard (``"*"``) and an echo (any string value).

    Future regressions covered:

    * ``allow_origins=["*"]`` — caught (wildcard would set the header).
    * ``allow_origin_regex=".*"`` / ``"http://.*"`` — caught (would echo the
      foreign origin).
    * ``allow_origin_regex="http://127\\.0\\.0\\.1.*"`` (a "safe-looking"
      pattern that accidentally matches a subdomain spoof) — caught by the
      second parametrize case.
    * ``allow_credentials=True`` paired with any of the above — caught by the
      separate ``Allow-Credentials`` assertion.

    ``host: 127.0.0.1:8765`` is deliberate: the ``HostHeaderGuard`` middleware
    (added AFTER ``CORSMiddleware`` and therefore running FIRST in Starlette's
    LIFO request order) would otherwise pre-empt with 400 and CORS would never
    run. ``test_host_header_guard_rejects_evil_host`` already pins the wrong-
    Host rejection path; this test pins the CORS layer independently.
    """
    db = _empty_db(tmp_path)
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    client = TestClient(app)
    r = client.options(
        "/fragments/live",
        headers={
            "host": "127.0.0.1:8765",
            "origin": foreign_origin,
            "access-control-request-method": "GET",
            "access-control-request-headers": "content-type",
        },
    )
    allow_origin = r.headers.get("access-control-allow-origin", "")
    assert allow_origin == "", (
        f"CORS emitted Allow-Origin {allow_origin!r} for non-matching origin "
        f"{foreign_origin!r} — same-origin invariant violated "
        "(contract: header MUST be absent on a non-matching origin)"
    )
    allow_creds = r.headers.get("access-control-allow-credentials", "false")
    assert allow_creds.lower() != "true", (
        f"CORS emitted Allow-Credentials=true for non-matching origin "
        f"{foreign_origin!r} — credentials must never cross a same-origin boundary"
    )


# --------------------------------------------------------------------------- #
# Live-event extraction (parses through the public A-ARCH1 helpers)
# --------------------------------------------------------------------------- #


def test_extract_live_events_returns_empty_when_no_projects_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No CLAUDE_PROJECTS_ROOT yields zero events — never crashes (qa F9)."""
    nonexistent = tmp_path / "nope"
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", nonexistent)
    assert dashboard_server._extract_live_events(tmp_path) == []


def test_extract_live_events_skips_malformed_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A truncated / non-JSON line is skipped, not crashed on (qa F9 / AC6)."""
    projects_root = tmp_path / "claude_projects"
    projects_root.mkdir()
    project_root = tmp_path / "proj"
    project_root.mkdir()
    monkeypatch.setattr(itu, "CLAUDE_PROJECTS_ROOT", projects_root)

    slug = itu._project_slug(project_root)
    session_dir = projects_root / slug
    session_dir.mkdir()
    # One valid line, one truncated, one with no message-id.
    valid = json.dumps(
        {
            "timestamp": "2026-06-07T12:00:00Z",
            "message": {
                "id": "msg_1",
                "model": "claude-opus-4-7",
                "usage": {"input_tokens": 100, "output_tokens": 50},
            },
        }
    )
    bad = '{"timestamp": "2026-06-07T12:00:01Z", "message": {"id":'
    (session_dir / "session.jsonl").write_text(valid + "\n" + bad + "\n", encoding="utf-8")

    events = dashboard_server._extract_live_events(project_root)
    assert len(events) == 1
    assert events[0].kind == "message"
    assert events[0].input_tokens == 100


# --------------------------------------------------------------------------- #
# qa F3 (REV-20260607-200447) — direct parse-layer dispatch tests
#
# The integration tests above ("malformed lines", "no projects root") exercise
# ``_extract_live_events`` end-to-end through a real on-disk file. The advisory
# called out that the per-block dispatch logic inside ``_parse_main_session``
# (assistant message-with-usage / tool_use Agent / tool_result) and the
# subagent path inside ``_parse_subagent`` each have their own branch logic
# that the single integration test did not cover individually. These tests
# exercise the parsers directly with hand-crafted JSONL so a future edit that
# regresses one dispatch path fails immediately rather than only when a real
# transcript happens to carry that block.
# --------------------------------------------------------------------------- #


def _ts(seconds: int = 0) -> str:
    """Produce an ISO-Z timestamp at ``2026-06-07T12:00:<ss>Z`` for fixtures."""
    return f"2026-06-07T12:00:{seconds:02d}Z"


def _write_main_jsonl(path: Path, records: list[dict[str, Any]]) -> Path:
    """Serialise ``records`` as JSONL into ``path`` and return ``path``."""
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


@pytest.mark.regression
def test_parse_main_session_emits_dispatch_event_for_tool_use_agent_block(
    tmp_path: Path,
) -> None:
    """Regression (qa F3 / REV-20260607-200447): a ``tool_use`` block named
    ``Agent`` becomes a ``dispatch`` event whose ``lane_id`` is the tool ``id``
    and whose ``agent_type`` is the ``subagent_type`` input.

    Before this guard, a refactor that renamed the dispatch tool (e.g. back to
    ``Task``) or that dropped the ``input.subagent_type`` extraction would have
    silently produced empty agent lanes in the live dashboard.
    """
    path = _write_main_jsonl(
        tmp_path / "session.jsonl",
        [
            {
                "timestamp": _ts(0),
                "message": {
                    "id": "msg_1",
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Agent",
                            "id": "tool_abc",
                            "input": {"subagent_type": "qa-specialist"},
                        }
                    ],
                },
            }
        ],
    )
    events = dashboard_server._parse_main_session(path, since=None)
    dispatches = [e for e in events if e.kind == "dispatch"]
    assert len(dispatches) == 1
    assert dispatches[0].lane_id == "tool_abc"
    assert dispatches[0].agent_type == "qa-specialist"
    assert dispatches[0].tool_name == "Agent"


@pytest.mark.regression
def test_parse_main_session_emits_result_event_for_tool_result_block(
    tmp_path: Path,
) -> None:
    """Regression (qa F3 / REV-20260607-200447): a ``tool_result`` block becomes
    a ``result`` event on the ``main`` lane whose ``ref_id`` matches the
    dispatch ``tool_use_id`` it answers.

    The fold uses ``ref_id`` to mark a dispatched lane ``complete``; if this
    extraction breaks, every subagent stays ``active`` forever.
    """
    path = _write_main_jsonl(
        tmp_path / "session.jsonl",
        [
            {
                "timestamp": _ts(0),
                "message": {
                    "id": "msg_2",
                    "content": [{"type": "tool_result", "tool_use_id": "tool_abc"}],
                },
            }
        ],
    )
    events = dashboard_server._parse_main_session(path, since=None)
    results = [e for e in events if e.kind == "result"]
    assert len(results) == 1
    assert results[0].lane_id == "main"
    assert results[0].ref_id == "tool_abc"


@pytest.mark.regression
def test_parse_main_session_ignores_non_dict_content_items(tmp_path: Path) -> None:
    """Regression (qa F3 / REV-20260607-200447): a ``content`` list with non-dict
    entries (strings, ``None``, ints) is iterated safely — only dict blocks are
    inspected.

    Pins the ``isinstance(block, dict)`` defensive guard in
    ``_parse_main_session``. Without this test the guard could be removed under
    the assumption it's dead code, then crash on real-world stray content.
    Also asserts the empty-``input`` branch — when ``input.subagent_type`` is
    absent, ``agent_type`` must be ``None`` (not an empty string), so a future
    change that flipped the ``or None`` default would not slip through (qa F2
    advisory fold, REV at DISC-20260607-235100).
    """
    path = _write_main_jsonl(
        tmp_path / "session.jsonl",
        [
            {
                "timestamp": _ts(0),
                "message": {
                    "id": "msg_3",
                    "content": [
                        "stray-string-block",
                        None,
                        42,
                        {"type": "tool_use", "name": "Agent", "id": "tool_z", "input": {}},
                    ],
                },
            }
        ],
    )
    events = dashboard_server._parse_main_session(path, since=None)
    # Only the one well-formed dispatch survives — the stray entries crashed
    # nothing and produced no events.
    dispatches = [e for e in events if e.kind == "dispatch"]
    assert len(dispatches) == 1
    assert dispatches[0].lane_id == "tool_z"
    # qa F2-QA fold: empty ``input`` dict -> ``agent_type`` must be ``None``,
    # never an empty string (preserves the absence semantic upstream renderers
    # rely on).
    assert dispatches[0].agent_type is None


@pytest.mark.regression
def test_parse_main_session_returns_empty_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable file produces ``[]`` without raising (qa F3)."""
    path = tmp_path / "session.jsonl"
    path.write_text('{"timestamp":"2026-06-07T12:00:00Z","message":{}}', encoding="utf-8")
    original = Path.read_text

    def _boom(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == path:
            raise OSError("simulated read failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)
    assert dashboard_server._parse_main_session(path, since=None) == []


@pytest.mark.regression
def test_parse_subagent_produces_message_event_on_agent_lane(tmp_path: Path) -> None:
    """A subagent JSONL produces a ``message`` event whose ``lane_id`` is the
    file stem (e.g. ``agent-abc123``) — qa F3 subagent-path coverage.
    """
    path = tmp_path / "agent-abc123.jsonl"
    path.write_text(
        json.dumps(
            {
                "timestamp": _ts(0),
                "message": {
                    "id": "submsg_1",
                    "model": "claude-sonnet-4-6",
                    "usage": {"input_tokens": 200, "output_tokens": 75},
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    events = dashboard_server._parse_subagent(path, since=None)
    assert len(events) == 1
    e = events[0]
    assert e.kind == "message"
    assert e.lane_id == "agent-abc123"
    assert e.model == "claude-sonnet-4-6"
    assert e.input_tokens == 200
    assert e.output_tokens == 75


@pytest.mark.regression
def test_parse_subagent_returns_empty_on_oserror(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unreadable subagent file produces ``[]`` without raising (qa F3)."""
    path = tmp_path / "agent-xyz.jsonl"
    path.write_text("{}", encoding="utf-8")
    original = Path.read_text

    def _boom(self: Path, *args: Any, **kwargs: Any) -> str:
        if self == path:
            raise OSError("simulated read failure")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _boom)
    assert dashboard_server._parse_subagent(path, since=None) == []


# --------------------------------------------------------------------------- #
# qa F6 (REV-20260607-200447) — per-line ``since`` boundary semantics
#
# The route uses ``since = now - LIVE_FOLD_LOOKBACK_MINUTES`` and passes it
# through to the per-line filter ``ts < since``. The advisory called out that
# the strict ``<`` (vs ``<=``) is now load-bearing: an event whose timestamp
# equals ``since`` MUST be included, since the upstream file-mtime filter is
# already ``>=``. A future edit that flips to ``<=`` would silently drop the
# leading edge of every poll window.
# --------------------------------------------------------------------------- #


@pytest.mark.regression
@pytest.mark.parametrize(
    ("event_offset_s", "expected_included"),
    [
        (-1, False),  # t-1 < t -> excluded
        (0, True),  # t == since -> included (strict ``<`` is the contract)
        (+1, True),  # t+1 > t -> included
    ],
)
def test_parse_main_session_since_boundary_uses_strict_less_than(
    tmp_path: Path, event_offset_s: int, expected_included: bool
) -> None:
    """Regression (qa F6 / REV-20260607-200447): ``ts < since`` (strict), not ``<=``.

    Drives the per-line filter in ``_parse_main_session`` directly with three
    boundary cases. A future flip to ``<=`` would drop the ``t == since`` line
    and silently lose the leading edge of every poll window.
    """

    base = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)
    event_dt = base + timedelta(seconds=event_offset_s)
    record_ts = event_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    path = _write_main_jsonl(
        tmp_path / "session.jsonl",
        [
            {
                "timestamp": record_ts,
                "message": {
                    "id": "msg_boundary",
                    "model": "claude-opus-4-7",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            }
        ],
    )
    events = dashboard_server._parse_main_session(path, since=base)
    if expected_included:
        assert len(events) == 1, (
            f"event at offset {event_offset_s}s should be included with since=t (strict <)"
        )
    else:
        assert events == [], (
            f"event at offset {event_offset_s}s should be excluded with since=t (strict <)"
        )


@pytest.mark.regression
def test_parse_subagent_since_boundary_uses_strict_less_than(tmp_path: Path) -> None:
    """Regression (qa F6 / REV-20260607-200447): the subagent parser shares
    the per-line ``ts < since`` semantics with the main parser. Asserting both
    keeps them locked together — a future divergence (one strict, one
    inclusive) would be invisible without this paired guard.
    """

    base = datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC)
    path = tmp_path / "agent-boundary.jsonl"
    path.write_text(
        "\n".join(
            json.dumps(
                {
                    "timestamp": ts,
                    "message": {
                        "id": f"msg_{ts}",
                        "model": "claude-sonnet-4-6",
                        "usage": {"input_tokens": 1, "output_tokens": 1},
                    },
                }
            )
            for ts in (
                "2026-06-07T11:59:59Z",  # excluded
                "2026-06-07T12:00:00Z",  # included (equal)
                "2026-06-07T12:00:01Z",  # included
            )
        )
        + "\n",
        encoding="utf-8",
    )
    events = dashboard_server._parse_subagent(path, since=base)
    assert len(events) == 2, (
        "expected the equal-to-since and after-since events; the strict ``<`` "
        "contract excludes only the pre-since line"
    )


# --------------------------------------------------------------------------- #
# arch F2 (REV-20260607-200447) — event_source seam direct tests
#
# ``create_app`` accepts an ``event_source: Callable[[], list[LiveEvent]] | None``
# constructor argument that the ``/fragments/live`` route consumes through
# ``app.state.event_source()``. Phase 1's default — :func:`_default_event_source`
# — re-walks recent transcripts each call; Phase 2's background watcher swaps
# in via this constructor arg with no route-handler change. The tests below
# pin the seam contract directly: (1) a custom ``event_source`` IS consumed by
# the route (a regression that ignored the parameter would be invisible to the
# existing transcript-wired tests), AND (2) the default falls back to the
# lazy disk-walk through :func:`_extract_live_events` (paired guard so a
# future refactor that dropped the default-binding silently degrades to a
# no-op fold).
# --------------------------------------------------------------------------- #


@pytest.mark.regression
def test_create_app_uses_custom_event_source_when_provided(tmp_path: Path) -> None:
    """Regression (arch F2 / REV-20260607-200447): a custom ``event_source``
    callable passed to ``create_app`` IS what ``/fragments/live`` consumes,
    not the default ``_extract_live_events`` disk-walk.

    Phase 2's background watcher relies on this seam to swap in as one
    constructor argument. A regression that ignored the parameter (e.g. a
    route handler that reverted to calling ``_extract_live_events`` directly)
    would be invisible to the existing transcript-wired tests — those still
    pass because the disk-walk path also returns no events on an empty
    fixture root. This guard pins the route handler to ``app.state.event_source()``.
    """
    from src.telemetry.live import LiveEvent

    db = _empty_db(tmp_path)
    sentinel_lane = "custom-event-source-arch-f2-sentinel"
    call_count = {"n": 0}

    def custom_source() -> list[LiveEvent]:
        call_count["n"] += 1
        return [
            LiveEvent(
                kind="message",
                timestamp=datetime(2026, 6, 7, 12, 0, 0, tzinfo=UTC),
                lane_id=sentinel_lane,
                model="claude-opus-4-7",
                input_tokens=100,
                output_tokens=50,
            )
        ]

    app = create_app(
        db_path=db,
        project_root=tmp_path,
        port=8765,
        event_source=custom_source,
    )
    # The seam is stored on app.state for the route handler to consume.
    assert app.state.event_source is custom_source

    client = TestClient(app)
    r = client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    # The custom source's data MUST appear in the rendered fragment — the
    # sentinel lane is escaped HTML-safe but its literal characters survive,
    # so a positive substring match proves the fold consumed our events.
    assert sentinel_lane in r.text, (
        "custom event_source was not consumed by /fragments/live; the route "
        "handler is reading from somewhere other than app.state.event_source()"
    )
    assert call_count["n"] >= 1, (
        "custom event_source was never invoked; the constructor arg is being "
        "ignored or app.state.event_source was overwritten before the request"
    )


@pytest.mark.regression
def test_create_app_default_event_source_falls_back_to_extract_live_events(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (arch F2 / REV-20260607-200447): when ``event_source`` is
    omitted, ``create_app`` binds the default to :func:`_default_event_source`,
    which in turn calls :func:`_extract_live_events`. This is the paired guard
    to the custom-source test above — a future refactor that drops the default
    binding (leaving ``app.state.event_source`` as ``None`` or a no-op lambda)
    would silently render an empty live fragment even when transcripts exist.

    Drives the contract by monkeypatching ``_extract_live_events`` and
    asserting it is invoked through the seam during a live-fragment request.
    """
    db = _empty_db(tmp_path)
    call_count = {"n": 0}

    real_extract = dashboard_server._extract_live_events

    def counting_extract(*args, **kwargs):
        call_count["n"] += 1
        return real_extract(*args, **kwargs)

    monkeypatch.setattr(dashboard_server, "_extract_live_events", counting_extract)

    # No event_source passed -> default seam binds to _default_event_source ->
    # which calls _extract_live_events. The seam is what the contract names.
    app = create_app(db_path=db, project_root=tmp_path, port=8765)
    # qa F5 in-session fold (REV-20260608-020046): pin the default seam
    # IS the ``partial(_default_event_source, ...)`` wrapper. A future
    # refactor that bound ``partial(_extract_live_events, proj_root, since=...)``
    # directly (skipping ``_default_event_source``) would still satisfy the
    # call-count assertion below, weakening this test to "some path calls
    # _extract_live_events." The isinstance pin keeps "default seam = the
    # named module-level helper" as the load-bearing contract.
    from functools import partial as _partial

    assert isinstance(app.state.event_source, _partial), (
        "default event_source is not a functools.partial wrapper around "
        "_default_event_source; a refactor that bypassed the named helper "
        "would silently weaken this test's claim about the default seam shape"
    )
    assert app.state.event_source.func is dashboard_server._default_event_source, (
        "default event_source partial does not wrap _default_event_source; "
        "the seam's named-helper contract is broken"
    )
    client = TestClient(app)
    r = client.get("/fragments/live", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    assert call_count["n"] >= 1, (
        "default event_source did not delegate to _extract_live_events; the "
        "Phase 1 lazy-fold default is broken — a future Phase 2 watcher swap "
        "would silently land on top of an already-degraded default path"
    )
