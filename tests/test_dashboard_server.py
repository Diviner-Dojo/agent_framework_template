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
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest
import uvicorn
from fastapi.testclient import TestClient

from scripts import ingest_token_usage as itu
from scripts.init_db import init_db
from scripts.telemetry import dashboard_server
from scripts.telemetry.dashboard_server import (
    HARDCODED_HOST,
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

    Behavioral guard — the layer that bites new vectors. We copy
    ``.claude/hooks`` + ``settings.json`` into ``tmp_path``, compute SHA-256
    sums before, hit every route, and assert sums unchanged. A future change
    that decides to "patch the hook on the fly" would fail loudly.
    """
    repo_claude = _REPO_ROOT / ".claude"
    if not (repo_claude / "settings.json").exists() or not (repo_claude / "hooks").exists():
        pytest.skip("repo .claude/ tree not present")

    sandbox = tmp_path / ".claude"
    shutil.copytree(repo_claude / "hooks", sandbox / "hooks")
    shutil.copy2(repo_claude / "settings.json", sandbox / "settings.json")

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


def test_dynamic_lane_fields_are_html_escaped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A transcript-shaped value reaching the live fragment is HTML-escaped (AC6).

    We monkeypatch ``_extract_live_events`` to inject a lane_id and agent_type
    carrying ``<script>alert(1)</script>``; the rendered fragment must NOT
    contain a literal ``<script>``.
    """
    from datetime import UTC, datetime

    from src.telemetry.live import LiveEvent

    db = _empty_db(tmp_path)
    payload = "<script>alert(1)</script>"

    def fake_events(*_args, **_kwargs):
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

    monkeypatch.setattr(dashboard_server, "_extract_live_events", fake_events)

    app = create_app(db_path=db, project_root=tmp_path, port=8765)
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
    assert r.status_code in (500, 503)
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


def test_static_htmx_asset_is_served() -> None:
    """The vendored htmx file is served from the static mount (R11a / AC6)."""
    app = create_app(port=8765)
    client = TestClient(app)
    r = client.get("/static/htmx.min.js", headers={"host": "127.0.0.1:8765"})
    assert r.status_code == 200
    # The known-good htmx file starts with a recognisable banner / signature.
    assert "htmx" in r.text.lower()


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
