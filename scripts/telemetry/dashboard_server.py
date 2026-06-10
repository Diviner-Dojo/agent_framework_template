"""Telemetry Layer B — live, localhost-only dashboard daemon (SPEC-20260607-183136).

User-launched persistent FastAPI app that renders the framework's telemetry
(A1 cost / A2 failure signals / A3 value) in real time during a Claude Code
session, and the durable retrospective views from history when no session is
live. The single point of access is a developer-owned process bound to
``127.0.0.1``; the server has no outbound HTTP client and never injects telemetry
into any agent prompt.

Security-critical invariants enforced here (Steward conditions, AC1-AC9):

* **AC2 (bind):** :data:`HARDCODED_HOST` is the literal ``"127.0.0.1"``. The
  CLI has NO ``--host`` flag and NO ``HOST`` env read; a runtime guard asserts
  the resolved ``uvicorn.Config.host`` equals the hardcoded value BEFORE
  ``uvicorn.run()``. No request can ever reach this server from another host.
* **AC3 (no-inject):** the server has no write side. Importing this module
  pulls only stdlib, fastapi/starlette/uvicorn, and the pure ``src.telemetry.*``
  modules. It does NOT import any ``.claude/hooks/`` module or any
  ``settings.json``-touching code (a regression test asserts this).
* **AC5 (read-only DB):** SQLite is opened ``file:...?mode=ro`` (the same path
  the static dashboard's ``assemble_dashboard_data`` uses). The server never
  creates, alters, or drops a column.
* **AC6 (output safety):** every dynamic field flows through the
  ``src.telemetry.dashboard`` escape helpers. Error responses are generic — the
  exception class name and DB path never reach the response body.
* **AC8 (no outbound surface):** this module imports no HTTP client and makes
  no outbound network call.
* **R8a (loopback request-origin guard):** the CORS middleware is configured
  same-origin-only (no wildcard); a ``HostHeaderGuard`` middleware returns 400
  on any ``Host`` header other than ``127.0.0.1:<port>`` to blunt DNS-rebinding
  / localhost-CSRF from a malicious page the developer visits.
* **AC16 (port-in-use):** :func:`main` catches ``OSError``-on-bind and prints
  a clear "port already in use" message rather than a raw traceback.

Usage:
    python scripts/telemetry/dashboard_server.py
    python scripts/telemetry/dashboard_server.py --port 8765
    python scripts/telemetry/dashboard_server.py --no-open
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import webbrowser
from collections.abc import Callable
from contextlib import asynccontextmanager
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from functools import partial
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from scripts import ingest_token_usage as itu  # noqa: E402
from scripts.telemetry.dashboard import (  # noqa: E402
    assemble_dashboard_data,
    load_cost_report,
    load_weekly_trends,
)
from src.telemetry.dashboard import (  # noqa: E402
    LiveFragmentPanels,
    render_dashboard_html,
    render_hook_health_chip,
    render_live_fragment,
    render_live_shell_html,
    render_model_cost_donut_panel,
    render_weekly_trends_chart_panel,
)
from src.telemetry.hooks_health import (  # noqa: E402
    HookHealthReport,
    assess_hook_health,
    parse_hook_script_refs,
)
from src.telemetry.live import LiveEvent, empty_state, fold_events  # noqa: E402
from src.telemetry.pricing import PricingTable, load_pricing  # noqa: E402

#: The ONLY host this server will ever bind. NEVER read from env, NEVER passed
#: as a CLI flag — the absence of those affordances is the binding security
#: invariant (AC2 / spec R8). A change to this literal is a code-review event.
HARDCODED_HOST = "127.0.0.1"

#: Default port (above the ephemeral range to avoid conflict). The developer
#: may override via ``--port`` when launching, but the host literal stays.
DEFAULT_PORT = 8765

#: htmx polling interval — server-specified, NOT client-overridable (security
#: F5 — a client-controlled interval would let a tab burn CPU on the daemon).
LIVE_POLL_INTERVAL_S = 3.0

#: Defense-in-depth Content-Security-Policy applied to every response (security
#: F2 / REV-20260607-200447, extended security F1 / REV-20260608-010051). The
#: dashboard is loopback-only and routes are read-only, so this is genuinely
#: defense-in-depth — a future contributor who inlines a CDN ``<script>`` or
#: stores a transcript-shaped string into an ``onclick`` attribute is denied by
#: the browser even if a ``_esc`` regression lands. Inline ``<style>`` blocks +
#: the ``style="width:..."`` runway bar need ``'unsafe-inline'`` for style-src;
#: scripts are vendored at ``/static/`` so ``script-src 'self'`` suffices and
#: inline scripts are intentionally banned. ``frame-ancestors 'none'`` blocks
#: any other page (even a localhost-rebinding one) from embedding this dashboard
#: in an ``<iframe>`` / ``<frame>`` / ``<object>``, which is the modern clickjacking
#: + DNS-rebinding hardening (replaces ``X-Frame-Options: DENY``). ``object-src
#: 'none'`` shuts the legacy ``<object>`` / ``<embed>`` / ``<applet>`` surface —
#: the dashboard never serves Flash / Java / arbitrary plugin payloads, and the
#: default-src fallback alone is not authoritative for these elements in older
#: browsers.
#:
#: **Directives evaluated and intentionally OMITTED** (security F2-INFO note,
#: REV at session 10h): ``base-uri`` is omitted because the dashboard renders
#: no ``<base>`` element and htmx does not require one — re-evaluate if a
#: ``<base>`` tag is ever added (an injected ``<base href="...">`` would redirect
#: every relative URL on the page regardless of ``default-src``, so adding
#: ``base-uri 'self'`` then becomes load-bearing). ``connect-src`` /
#: ``img-src`` / ``font-src`` / ``form-action`` are omitted because they all
#: fall back to ``default-src 'self'`` and the dashboard makes no outbound
#: fetch, loads no remote images, bundles no web fonts, and renders no
#: ``<form>`` — adding them explicitly buys no attack-surface reduction over
#: ``default-src 'self'`` while raising the maintenance cost of every future
#: edit. Adding one of these surfaces (a chart endpoint, a CDN image, a form)
#: MUST add the matching directive in the same change.
#:
#: **Scope of the ``style-src 'unsafe-inline'`` permission** (security F3 note,
#: REV at session 10g): the inline-style attribute surface is currently bounded
#: to ONE site — ``src/telemetry/dashboard.py`` line ~709's runway-bar
#: ``style="width:{_esc(bar_width)}%"`` — and the value is ``max(0.0, min(100.0,
#: runway.fill_pct))``, a Python float numerically clamped to ``[0, 100]``
#: BEFORE ``_esc``. That means the inline-style permission cannot carry a
#: CSS-injection vector today (no string content, no ``}`` / ``;`` escape).
#: A future ``style=...`` attribute whose value is a STRING field (lane id,
#: agent name, model name, etc.) MUST go through a CSS-aware sanitizer, not
#: just ``_esc`` — ``html.escape`` does not neutralise CSS-context injection.
#: Adding such a field without that review is a regression.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'unsafe-inline'; "
    "frame-ancestors 'none'; "
    "object-src 'none'"
)

#: Default "look back this far" window for the live fold (independent-perspective
#: Phase 1 advisory). Without this, each poll walks every session JSONL Claude
#: Code ever wrote for the project — on this repo's own ~94 MB transcript root
#: that is unusable. Ten minutes is generous enough to cover a typical paused
#: session but tight enough that a fresh poll stays fast. Phase 2 replaces this
#: with a background watcher; the cutoff stays as the cold-start fallback.
LIVE_FOLD_LOOKBACK_MINUTES = 10

#: Bounded tail-read window for the quality-gate log recency evidence
#: (SPEC-20260610-005602 arch F4 / security F4): the log is append-only and
#: grows monotonically, so the loader reads at most this many bytes from the
#: END of the file per poll — never the whole file. 4 KB comfortably covers
#: many gate entries (~300 bytes each) while keeping the per-poll cost flat
#: regardless of log age.
_GATE_LOG_TAIL_BYTES = 4096

#: Default DB path (same as the static dashboard).
DB_PATH = _REPO_ROOT / "metrics" / "evaluation.db"

#: Vendored static asset directory served at ``/static/``.
STATIC_DIR = _REPO_ROOT / "src" / "telemetry" / "static"


class NonLoopbackBindError(RuntimeError):
    """Raised when something tries to bind a non-loopback host.

    The CLI never accepts a host argument, but this raises on any caller of
    :func:`run_server` whose ``host`` is not exactly :data:`HARDCODED_HOST` —
    fails fast at startup, BEFORE uvicorn ever opens a socket.
    """


class HostHeaderGuard(BaseHTTPMiddleware):
    """Reject any request whose ``Host`` header is not the loopback bind.

    Blunts DNS-rebinding / localhost-CSRF: a malicious page the developer
    visits cannot trick the browser into ``Host: evil.example.com`` while
    routing to ``127.0.0.1``. A bad ``Host`` returns HTTP 400 with a generic
    body — neither the configured port nor the bad header value is echoed.
    """

    def __init__(self, app: Any, *, allowed_hosts: set[str]) -> None:
        super().__init__(app)
        self._allowed = allowed_hosts

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        host_header = request.headers.get("host", "")
        if host_header not in self._allowed:
            return PlainTextResponse("Bad host", status_code=400)
        return await call_next(request)


class ContentSecurityPolicyMiddleware(BaseHTTPMiddleware):
    """Stamp a defense-in-depth ``Content-Security-Policy`` header on every response.

    Registered LAST in :func:`create_app` so it is the outermost middleware
    (Starlette runs added middleware in LIFO order on the response path), which
    means it ALSO stamps the header on the 400 :class:`HostHeaderGuard`
    rejection and on every error fragment — a future regression that drops
    inline-script protection on an error page is caught.

    The policy is read from :data:`CONTENT_SECURITY_POLICY` so test code can
    pin the exact string in one place. The header is set unconditionally
    (overwrites any upstream value) — there is no scenario in which a route
    handler should override the policy, so the simpler write-always semantics
    are correct here.

    A catastrophic exception escaping ``call_next`` (security F2 follow-on /
    REV-20260608-010051) — e.g. a future middleware regression, an inner
    framework bug, or a route that bypasses the existing route-level
    ``except Exception`` and bubbles out — is caught here and converted to a
    generic 500 that STILL carries the CSP header. Today every route catches
    ``Exception`` and returns an ``HTMLResponse``, so this branch is
    practically unreachable; but as the OUTERMOST middleware this is the
    canonical place to ensure the policy is on every byte the client receives,
    including a "framework blew up before any route ran" path.
    """

    def __init__(self, app: Any, *, policy: str) -> None:
        super().__init__(app)
        self._policy = policy

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        try:
            response = await call_next(request)
        except Exception:
            # Fail-closed with CSP still stamped (AC6: generic body, no
            # exception class, no path). Practically unreachable today —
            # every route catches Exception, AND Starlette's
            # ``ExceptionMiddleware`` is registered automatically BELOW the
            # user middleware stack and converts ``HTTPException`` into a
            # proper response BEFORE it could bubble up to this ``call_next``.
            # So an exception arriving here is by definition catastrophic
            # (inner-middleware regression, ASGI bug, or a route that
            # bypassed the existing ``except Exception``). Catching
            # ``Exception`` rather than narrowing to specific types is
            # deliberate at this surface — there is no legitimate framework
            # control-flow signal that should pass through the outermost
            # response stamper (``BaseException`` subclasses like
            # ``asyncio.CancelledError`` propagate by design, not blocked
            # here). Body is HTMLResponse so htmx ``hx-swap`` targets handle
            # it gracefully (security F4 fold, REV at session 10h).
            response = HTMLResponse("<p>Internal Server Error</p>", status_code=500)
        response.headers["Content-Security-Policy"] = self._policy
        return response


def _allowed_hosts(port: int) -> set[str]:
    """Return the set of valid ``Host`` header values for this bind."""
    return {f"{HARDCODED_HOST}:{port}", HARDCODED_HOST}


def _safe_text(line: str) -> dict[str, Any] | None:
    """Parse one transcript JSONL line; ``None`` on malformed/truncated (qa F9)."""
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _extract_live_events(project_root: Path, since: datetime | None = None) -> list[LiveEvent]:
    """Walk the project's session transcripts into a chronological event list.

    Reuses the public transcript helpers promoted via A-ARCH1 (R16/AC15):
    :func:`itu.discover_session_dirs`, :func:`itu.is_inside_projects_root`, and
    :func:`itu.parse_timestamp`. Each main-session line becomes an event by
    inspection of its top-level shape (assistant ``message`` -> ``message``
    event; tool-use ``Agent`` -> ``dispatch``; ``tool_result`` -> ``result``).
    Subagent JSONL files contribute ``message`` events on their lane.

    A malformed line or a missing field is skipped (the fold ignores unknown
    kinds, but here we filter at parse-time too). For Phase 1 the route handler
    passes a ``since`` cutoff (default 10 minutes); files whose mtime is older
    than ``since`` are skipped entirely BEFORE the per-line parse — the
    independent-perspective advisory called this out as the load-bearing
    optimisation that turns the lazy fold from "walks 94 MB every 3 s" into
    "walks only recently-active sessions every 3 s." The per-line timestamp
    filter inside :func:`_parse_main_session` / :func:`_parse_subagent` then
    handles the boundary case (a file whose mtime is newer than ``since`` but
    whose recent lines are not — e.g. one assistant message inside a paused
    session).
    """
    events: list[LiveEvent] = []
    if not itu.CLAUDE_PROJECTS_ROOT.exists():
        return events
    session_paths = itu.discover_session_dirs(project_root)

    def _is_recent(p: Path) -> bool:
        """Return True iff ``p``'s mtime is at or after ``since`` (no filter -> True)."""
        if since is None:
            return True
        try:
            return datetime.fromtimestamp(p.stat().st_mtime, tz=UTC) >= since
        except OSError:
            return False

    for path in session_paths:
        if not itu.is_inside_projects_root(path):
            continue
        if path.is_file() and path.suffix == ".jsonl":
            if _is_recent(path):
                events.extend(_parse_main_session(path, since))
        elif path.is_dir():
            main = path / f"{path.name}.jsonl"
            if main.is_file() and itu.is_inside_projects_root(main) and _is_recent(main):
                events.extend(_parse_main_session(main, since))
            sub = path / "subagents"
            if sub.is_dir() and itu.is_inside_projects_root(sub):
                for entry in sub.iterdir():
                    if (
                        entry.is_file()
                        and entry.suffix == ".jsonl"
                        and entry.name.startswith("agent-")
                        and itu.is_inside_projects_root(entry)
                        and _is_recent(entry)
                    ):
                        events.extend(_parse_subagent(entry, since))
    events.sort(key=lambda e: e.timestamp)
    return events


def _parse_main_session(path: Path, since: datetime | None) -> list[LiveEvent]:
    """Parse a main-session JSONL into ``message`` / ``dispatch`` / ``result`` events."""
    out: list[LiveEvent] = []
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        record = _safe_text(line)
        if not isinstance(record, dict):
            continue
        ts = itu.parse_timestamp(record.get("timestamp", ""))
        if ts is None or (since is not None and ts < since):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        # Assistant message with usage -> message event on lane "main".
        usage = message.get("usage")
        if isinstance(usage, dict):
            out.append(
                LiveEvent(
                    kind="message",
                    timestamp=ts,
                    lane_id="main",
                    model=message.get("model") if isinstance(message.get("model"), str) else None,
                    input_tokens=itu.coerce_int(usage.get("input_tokens")),
                    output_tokens=itu.coerce_int(usage.get("output_tokens")),
                    cache_read_tokens=itu.coerce_int(usage.get("cache_read_input_tokens")),
                    cache_create_tokens=itu.coerce_int(usage.get("cache_creation_input_tokens")),
                )
            )
        # Tool-use blocks: Agent dispatches -> dispatch event; results elsewhere.
        content = message.get("content")
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") == "tool_use" and block.get("name") == "Agent":
                    inp = block.get("input") if isinstance(block.get("input"), dict) else {}
                    out.append(
                        LiveEvent(
                            kind="dispatch",
                            timestamp=ts,
                            lane_id=str(block.get("id") or ""),
                            agent_type=str(inp.get("subagent_type") or "") or None,
                            tool_name="Agent",
                        )
                    )
                elif block.get("type") == "tool_result":
                    ref = block.get("tool_use_id") or block.get("id")
                    if isinstance(ref, str) and ref:
                        out.append(
                            LiveEvent(kind="result", timestamp=ts, lane_id="main", ref_id=ref)
                        )
    return out


def _parse_subagent(path: Path, since: datetime | None) -> list[LiveEvent]:
    """Parse a subagent JSONL: produce ``message`` events on the agent lane."""
    out: list[LiveEvent] = []
    lane_id = path.stem  # e.g. "agent-abc123"
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return out
    for line in text.splitlines():
        record = _safe_text(line)
        if not isinstance(record, dict):
            continue
        ts = itu.parse_timestamp(record.get("timestamp", ""))
        if ts is None or (since is not None and ts < since):
            continue
        message = record.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        out.append(
            LiveEvent(
                kind="message",
                timestamp=ts,
                lane_id=lane_id,
                model=message.get("model") if isinstance(message.get("model"), str) else None,
                input_tokens=itu.coerce_int(usage.get("input_tokens")),
                output_tokens=itu.coerce_int(usage.get("output_tokens")),
                cache_read_tokens=itu.coerce_int(usage.get("cache_read_input_tokens")),
                cache_create_tokens=itu.coerce_int(usage.get("cache_creation_input_tokens")),
            )
        )
    return out


def _default_event_source(project_root: Path) -> list[LiveEvent]:
    """Phase 1 default seam: lazy-walk recent transcripts each call.

    Used as the default ``event_source`` when :func:`create_app` is not given
    one. Re-reads session JSONL files whose mtime is within
    :data:`LIVE_FOLD_LOOKBACK_MINUTES` of "now" via :func:`_extract_live_events`,
    so the per-poll cost stays bounded even when the project has years of
    sealed history on disk.

    Phase 2's background watcher replaces this with a snapshot callable that
    returns the watcher's currently-folded events without touching disk; the
    swap is one constructor arg (``event_source=watcher.snapshot``) — the
    seam this helper defines is what lets the route handler stay unchanged
    across that swap (arch F2 fold, REV-20260607-200447).
    """
    since = datetime.now(UTC) - timedelta(minutes=LIVE_FOLD_LOOKBACK_MINUTES)
    return _extract_live_events(project_root, since=since)


def _read_last_gate_timestamp(log_path: Path) -> datetime | None:
    """Bounded, read-only tail of the gate log for the last well-formed entry.

    Seeks to the last :data:`_GATE_LOG_TAIL_BYTES` of ``log_path`` and scans
    the lines in that window BACKWARD for the last *well-formed* entry —
    defined (spec qa F4, a definite contract rather than an implementation
    choice) as a JSON object whose ``"timestamp"`` is an ISO-8601 string that
    parses to a **timezone-aware** datetime; a naive timestamp is treated as
    malformed. Trailing malformed lines therefore fall back to the previous
    well-formed entry within the window; no well-formed entry in the window or
    a missing/unreadable file yields ``None`` (the honest-absence input).

    Only the ``timestamp`` field is consumed — the entry's ``overall`` field
    has known skip-semantics subtleties (see the ``scripts/quality_gate.py``
    regression-ledger entry) and the chip makes no pass/fail claim from it.
    """
    try:
        with log_path.open("rb") as fh:
            fh.seek(0, 2)
            size = fh.tell()
            fh.seek(max(0, size - _GATE_LOG_TAIL_BYTES))
            window = fh.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    for line in reversed(window.splitlines()):
        record = _safe_text(line)
        if not isinstance(record, dict):
            continue
        stamp = record.get("timestamp")
        if not isinstance(stamp, str):
            continue
        try:
            parsed = datetime.fromisoformat(stamp)
        except ValueError:
            continue
        if parsed.tzinfo is None:
            continue
        return parsed
    return None


def load_hook_health(repo_root: Path) -> HookHealthReport:
    """Resolve the hook-health facts read-only and assemble the pure report.

    The transport half of SPEC-20260610-005602 R-4.1.2 (public, mirroring the
    :func:`load_weekly_trends` precedent in SHAPE: public name + direct unit
    tests + route consumer). It deliberately does NOT live next to
    ``load_weekly_trends`` in ``scripts/telemetry/dashboard.py`` — that module
    is the DB read-side surface (single ``_connect_readonly`` seam,
    REV-20260607-200447 arch F3) and this is a FILESYSTEM read; co-locating
    them would widen that module's concern boundary (REV arch F1, this unit).
    Strictly read-only — ``read_text`` / ``open``-for-read / ``is_file`` only;
    never executes a hook, never opens anything for write, never imports a
    hook module. The parent spec's AC3(b) byte-unchanged behavioral test is
    the authoritative guard on that promise.

    Args:
        repo_root: The framework repo root containing ``.claude/`` and
            ``metrics/`` (injectable so tests drive ``tmp_path`` fixture
            trees).

    Returns:
        The assembled :class:`HookHealthReport`.
    """
    settings_path = repo_root / ".claude" / "settings.json"
    try:
        settings_text: str | None = settings_path.read_text(encoding="utf-8")
    except OSError:
        settings_text = None
    parsed = parse_hook_script_refs(settings_text)
    hooks_dir = repo_root / ".claude" / "hooks"
    missing: dict[str, None] = {}
    for ref in parsed.script_refs:
        # Basename re-normalized at the stat site (spec security F2): even if
        # a crafted config smuggled path separators past the parser's charset,
        # no path component from config can escape ``.claude/hooks/``. A
        # dot-only ref (``.`` / ``..`` — note ``Path("..").name == ".."``) is
        # a traversal artifact, not a script name: statting it would resolve
        # to a DIRECTORY outside/above ``hooks/`` and reporting it would
        # surface the artifact in the chip — skipped instead.
        basename = Path(ref).name
        if not basename.strip("."):
            continue
        if not (hooks_dir / basename).is_file():
            missing.setdefault(basename)
    last_gate_run = _read_last_gate_timestamp(repo_root / "metrics" / "quality_gate_log.jsonl")
    return assess_hook_health(parsed, tuple(missing), last_gate_run)


def create_app(
    *,
    db_path: Path = DB_PATH,
    project_root: Path | None = None,
    pricing: PricingTable | None = None,
    static_dir: Path = STATIC_DIR,
    port: int = DEFAULT_PORT,
    event_source: Callable[[], list[LiveEvent]] | None = None,
    hook_health_root: Path | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    Pure constructor — no port bound, no socket opened. ``run_server`` ties
    this to a uvicorn server. Test code calls this directly and exercises the
    routes via ``starlette.testclient.TestClient``.

    Args:
        db_path: Read-only path to the telemetry DB.
        project_root: The framework project root whose transcripts feed the
            live state (defaults to the repo root the script lives in).
        pricing: Resolved pricing (defaults to loading the YAML once).
        static_dir: The vendored frontend asset directory.
        port: Port number, ONLY used to validate the ``Host`` header — the
            actual binding happens in :func:`run_server`.
        event_source: Optional zero-argument callable that returns the current
            list of :class:`LiveEvent` to fold into the live state. When
            ``None`` (default), each ``/fragments/live`` request re-walks
            recent transcripts via :func:`_default_event_source` (the Phase 1
            lazy fold within :data:`LIVE_FOLD_LOOKBACK_MINUTES`). Phase 2's
            background watcher swaps in by passing ``watcher.snapshot`` here;
            the route handler does not change. This is the seam called out by
            REV-20260607-200447 arch F2.
        hook_health_root: Repo root for the read-only hook-health facts
            (``.claude/settings.json`` + ``.claude/hooks/`` presence + the
            gate-log tail; SPEC-20260610-005602). Defaults to the repo root
            this script lives in; tests point it at a ``tmp_path`` fixture
            tree. Deliberately SEPARATE from ``project_root``, which
            addresses the transcript store under ``~/.claude/projects``.

    Returns:
        A configured :class:`FastAPI` app.
    """
    pricing = pricing or load_pricing()
    proj_root = project_root or _REPO_ROOT
    # Resolve the event-source seam once at construction time. The default is
    # a partial bound to ``proj_root`` so the route handler simply calls
    # ``app.state.event_source()`` with no awareness of whether it is the
    # lazy disk-walk or a Phase 2 watcher snapshot — that ignorance is the
    # arch F2 guarantee (route handler stable across Phase 1 → Phase 2 swap).
    resolved_event_source: Callable[[], list[LiveEvent]] = event_source or partial(
        _default_event_source, proj_root
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):  # noqa: ARG001 - FastAPI signature
        """Server lifespan: nothing to open at startup; reset live state at exit.

        Phase 2 attaches ``watcher.start()`` here BEFORE ``yield`` and
        ``watcher.stop()`` AFTER it (in teardown), paired with the
        ``event_source=watcher.snapshot`` constructor argument of arch F2.
        The watcher's lifecycle belongs on this surface — NOT on the seam
        itself — so the seam stays a pure ``Callable`` and the dashboard
        owns ``start/stop`` ordering relative to request handling.
        """
        app.state.live_state = empty_state()
        yield
        # Teardown (AC7): release in-memory live state so it does not linger
        # in process memory after the loop closes (e.g. test isolation).
        app.state.live_state = empty_state()

    app = FastAPI(lifespan=lifespan)

    # Same-origin CORS only — explicit allow list of one (R8a / AC6).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[f"http://{HARDCODED_HOST}:{port}"],
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )
    # Host-header guard — blunts DNS-rebinding / localhost-CSRF (R8a / AC2 plus).
    app.add_middleware(HostHeaderGuard, allowed_hosts=_allowed_hosts(port))
    # Defense-in-depth CSP header (security F2 / REV-20260607-200447). Added
    # LAST so it is the OUTERMOST middleware in Starlette's LIFO request stack
    # — meaning it stamps the header on EVERY response, including the 400 the
    # HostHeaderGuard returns on a bad Host and the 500/503 error fragments.
    app.add_middleware(
        ContentSecurityPolicyMiddleware,
        policy=CONTENT_SECURITY_POLICY,
    )

    # Vendored frontend assets (R11a / AC6). Mounted only if present so the
    # app is still constructable in a test environment without the directory.
    if static_dir.is_dir():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.state.db_path = db_path
    # ``proj_root`` is intentionally NOT mirrored onto ``app.state`` post arch F2
    # fold (REV-20260607-200447): the live-event seam captures it into the default
    # ``partial(_default_event_source, proj_root)`` at construction, so no route
    # handler needs to re-read it. Mirroring it would create a second source of
    # truth that could diverge from the seam (e.g. a Phase 2 watcher bound to a
    # different root via its own constructor) — keep the seam authoritative.
    app.state.pricing = pricing
    app.state.poll_interval_s = LIVE_POLL_INTERVAL_S
    app.state.event_source = resolved_event_source
    # Hook-health facts root (SPEC-20260610-005602). Deliberately SEPARATE
    # from ``proj_root``: that addresses the transcript store under
    # ``~/.claude/projects``; this addresses the repo tree carrying
    # ``.claude/settings.json`` + ``.claude/hooks/`` + the gate log. Tests
    # point it at a ``tmp_path`` fixture tree.
    app.state.hook_health_root = hook_health_root or _REPO_ROOT

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    """Bind GET routes (the only methods we serve)."""

    @app.get("/", response_class=HTMLResponse)
    async def root() -> HTMLResponse:
        """Serve the htmx shell that polls the live fragment."""
        label = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
        return HTMLResponse(render_live_shell_html(generated_label=label))

    @app.get("/fragments/live", response_class=HTMLResponse)
    async def live_fragment() -> HTMLResponse:
        """Compute the current LiveState and return its HTML fragment.

        Reads events through the ``app.state.event_source`` seam (arch F2 fold,
        REV-20260607-200447). The Phase 1 default — :func:`_default_event_source`
        — re-walks recent transcripts within :data:`LIVE_FOLD_LOOKBACK_MINUTES`
        each call, keeping per-poll cost bounded to genuinely active sessions.
        Phase 2's background watcher swaps in via the ``event_source``
        constructor argument; this route handler does not change.
        """
        try:
            events = app.state.event_source()
            state = fold_events(events, app.state.pricing)
            # NOT calling mark_orphans on a lazy per-request fold: orphan
            # transition needs a "session ended" signal (file-mtime quiet
            # window or an explicit stop) which the Phase 1 transport does
            # not have. The A2 analyzer + retrospective view detect orphans
            # from sealed history. A subagent whose result event has not yet
            # landed is correctly shown as ``active``, not falsely
            # ``orphaned``. mark_orphans returns to use in Phase 2 once the
            # background watcher signals session end.
            app.state.live_state = state
            # Weekly trends panel: persisted-corpus derived view, computed
            # at the transport layer (DB IO) and passed in as pre-rendered
            # HTML. Keeps live.py and dashboard.py pure (AC14 + render-layer
            # purity). Per-poll DB-read decision rationale + caching
            # triggers live in :func:`load_weekly_trends`'s docstring.
            trends = load_weekly_trends(app.state.db_path, app.state.pricing)
            weekly_panel = render_weekly_trends_chart_panel(trends)
            # Hook-health chip (SPEC-20260610-005602): read-only facts
            # resolved per poll (one small JSON read + ~10 stats + a bounded
            # <=4KB log tail), rendered by the pure helper and passed in as
            # pre-rendered HTML — same composition seam as the weekly panel.
            hook_chip = render_hook_health_chip(load_hook_health(app.state.hook_health_root))
            # Model-cost donut (SPEC-20260610-015114): persisted-corpus
            # per-tier cost split; same bounded per-poll read scale as
            # load_weekly_trends (caching triggers recorded there).
            report, cost_has_run = load_cost_report(app.state.db_path, app.state.pricing)
            donut_panel = render_model_cost_donut_panel(report, cost_has_run)
            return HTMLResponse(
                render_live_fragment(
                    state,
                    LiveFragmentPanels(
                        hook_health_chip_html=hook_chip,
                        weekly_panel_html=weekly_panel,
                        model_cost_donut_html=donut_panel,
                    ),
                )
            )
        except Exception:
            # Generic error (AC6): no exception class, no DB path, no stack.
            return HTMLResponse(
                '<section id="live-section" class="live-section" data-state="error">'
                '<div class="tile tile--absent">'
                "<h3>Live state</h3>"
                '<p class="absence-copy">'
                "Could not compute live state right now. Check the server logs."
                "</p></div></section>",
                status_code=500,
            )

    @app.get("/fragments/retrospective", response_class=HTMLResponse)
    async def retrospective_fragment() -> HTMLResponse:
        """Return the full retrospective dashboard (A1/A2/A3) as an HTML fragment.

        Reuses the EXISTING ``assemble_dashboard_data`` + ``render_dashboard_html``
        path (spec R15 — single render path), so the retrospective view served
        here is byte-identical to the static dashboard for the same DB state.
        """
        try:
            label = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
            data = assemble_dashboard_data(app.state.db_path, generated_label=label)
            return HTMLResponse(render_dashboard_html(data))
        except sqlite3.OperationalError:
            # No DB / read failure -> honest absence, generic message.
            return HTMLResponse(
                "<!DOCTYPE html><html><body>"
                "<p>Telemetry database is not available. "
                "Run <code>scripts/init_db.py</code> + an analyzer first.</p>"
                "</body></html>",
                status_code=503,
            )
        except Exception:
            return HTMLResponse(
                "<!DOCTYPE html><html><body>"
                "<p>Could not render the retrospective view right now.</p>"
                "</body></html>",
                status_code=500,
            )

    @app.get("/healthz", response_class=PlainTextResponse)
    async def healthz() -> PlainTextResponse:
        """Liveness probe (no telemetry surface — returns ``ok``)."""
        return PlainTextResponse("ok")


def run_server(*, host: str, port: int) -> None:
    """Start uvicorn on the validated host/port.

    Fails fast (BEFORE socket open) on any ``host`` other than
    :data:`HARDCODED_HOST` — this is the load-bearing runtime guard for AC2.
    Wraps :class:`OSError` (port in use, permission denied) into a human-
    readable message so the developer is not surprised by a raw traceback
    (AC16).

    Args:
        host: MUST be the literal :data:`HARDCODED_HOST`. Any other value
            raises :class:`NonLoopbackBindError`.
        port: TCP port to bind.
    """
    if host != HARDCODED_HOST:
        raise NonLoopbackBindError(
            f"refusing to bind {host!r}: the dashboard daemon is loopback-only "
            f"and may only listen on {HARDCODED_HOST!r}"
        )
    app = create_app(port=port)
    config = uvicorn.Config(
        app, host=HARDCODED_HOST, port=port, log_level="info", access_log=False
    )
    if config.host != HARDCODED_HOST:
        # Belt-and-braces (config.host is normalised by uvicorn; if a future
        # uvicorn rewrites loopback to "0.0.0.0" we want to refuse to launch).
        raise NonLoopbackBindError(
            f"uvicorn normalised host to {config.host!r}; refusing to launch"
        )
    print(
        f"Telemetry dashboard listening on http://{HARDCODED_HOST}:{port} "
        f"(loopback only). Press Ctrl-C to stop."
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    except OSError as exc:
        # AC16: clear, human-readable port-in-use message instead of a raw
        # [Errno 98 / WinError 10048] trace. No host/port stack disclosure
        # beyond the literals the developer already chose.
        print(
            f"Could not bind {HARDCODED_HOST}:{port} — is the dashboard already "
            "running, or is another local app using this port? "
            "Pass --port <free-port> to use a different one. "
            f"(underlying error: {exc.strerror or 'OSError'})"
        )
        sys.exit(1)


def main() -> None:
    """CLI entry point.

    Note (spec R8 / AC2): there is intentionally NO ``--host``/``-H`` flag and
    NO ``HOST`` env read. The single-host invariant is enforced in this CLI
    by the *absence* of any affordance to configure it.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Telemetry Layer B — live, localhost-only dashboard daemon. "
            "Binds 127.0.0.1 only; no host configuration."
        )
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"TCP port (default {DEFAULT_PORT}). Host is hardcoded to 127.0.0.1.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Do not auto-open the browser at startup.",
    )
    args = parser.parse_args()

    if not args.no_open:
        webbrowser.open(f"http://{HARDCODED_HOST}:{args.port}/")

    run_server(host=HARDCODED_HOST, port=args.port)


if __name__ == "__main__":
    main()
