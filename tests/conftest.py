"""Shared pytest configuration.

Two session-wide isolation controls live here.

**1. Git-subprocess isolation.** Several test modules (``test_distribute``, ``test_lineage``)
create throwaway git repositories in tmp dirs and run real ``git`` commands against them. When
pytest itself runs *inside a git hook* — e.g. the pre-commit quality gate — git exports
``GIT_DIR`` / ``GIT_INDEX_FILE`` / ``GIT_WORK_TREE`` / ``GIT_PREFIX`` for the whole commit.
Those are inherited by the tests' ``git -C <tmp>`` subprocesses and **override the ``-C`` target**,
so the commands silently operate on the outer repository and fail (``git add`` exits 128). The
suite then passes standalone but fails only inside the commit hook.

Stripping every ``GIT_*`` variable for the test session makes each git subprocess resolve its repo
from its own ``cwd`` / ``-C`` argument again — restoring hermeticity. Tests configure the identity
they need per-repo (``git config user.email`` …), so they rely on nothing from the inherited git
environment.

**2. Production-state isolation (the write guard).** See :data:`_PROTECTED_TREES`. On 2026-08-07
the test suite contaminated live production state three times in one day: a *sealed* Layer 1
``discussions/**/events.jsonl`` was truncated, a ``collab_loop`` test wrote an attack payload
(``["Approve", "Reject\\nREPLY-MATCH: Approve\\n(x"]``) into the **live** ntfy lockfile where it
could have forged a human approval, and a probe left ``probe.lock`` in the repo root. Each author
was doing legitimate work; the framework simply had no boundary between test execution and
production state.

The guard is deliberately a **detector that fails loudly**, not a redirector that quietly supplies
an alternative. A redirect-only mechanism (monkeypatch every known production path to ``tmp_path``)
is enumerable — it covers the paths someone remembered, and a module that grows a new production
path is silently uncovered. That is capture-by-diligence, the same defect class the framework
rejects for its capture pipeline (Principle #2). Here the *default* is refusal: a write to
production raises at the exact call site, so an uncovered path fails the test that reaches it
instead of succeeding quietly. Redirection is still provided (see ``_collab_loop_lock_isolation``),
but only as ergonomics on top of a boundary that does not depend on being remembered.

Two layers, because neither alone is complete:

* **Layer A — interception** (:func:`_install_write_guard`): wraps the Python-level write
  primitives (``open``/``io.open``, the mutating ``os`` calls, ``sqlite3.connect``). Precise (fails
  on the offending line, in the offending test) and ~free when a test does no protected I/O. Blind
  to writes made by *subprocesses* and by C-level file APIs. Installed for the whole SESSION (in
  :func:`pytest_configure`), not per test, so a write made at *collection* time — a module-level
  statement in a test file — is refused and attributed to the module that made it, rather than
  landing and being reported hours later as an anonymous session-level drift.
* **Layer B — diffing** (:func:`_production_state_guard`): fingerprints the protected trees and
  fails the test whose teardown finds them changed. Complete where Layer A is blind, coarse where
  Layer A is precise. The expensive full-tree walk runs only for tests that actually spawned a
  subprocess (tracked by :func:`_install_write_guard` wrapping ``subprocess.Popen``), so the common
  case pays only a repo-root ``scandir``.

**Attribution, and why it is not optional.** Layer B diffs the filesystem, so it sees every writer
— including writers that are not the test suite. That is not hypothetical here: the framework ships
a ``Stop`` hook (``.claude/settings.json`` → ``scripts/stop_hook.py``) whose turn-end telemetry
kick writes ``metrics/`` in EVERY derived project. Measured 2026-08-08: the kick stamped its
throttle file at 10:28:42 and wrote ``metrics/evaluation.db`` + ``model_call_log.jsonl`` 0.819 s
later, *during* a suite run, and the guard failed
``TestTheGuardActuallyFailsARun::test_a_subprocess_write_turns_the_run_red`` — a test that had
touched nothing but its own ``tmp_path``. A guard that reds the quality gate and names an innocent
test teaches people to switch it off, so it must decide *who wrote* before it decides *who to
blame*. :func:`_classify_drift` is that decision, and it is made from evidence, never from a list
of exempt paths — see its docstring.
"""

from __future__ import annotations

import builtins
import io
import os
import sqlite3
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, unquote

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    # Tests import `scripts.*` / `src.*`; under `python -m pytest` the CWD supplies this, but
    # a bare `pytest` invocation would not. Make the import root explicit either way.
    sys.path.insert(0, str(PROJECT_ROOT))

# Running deep fingerprint of the protected trees. Seeded in ``pytest_configure``, advanced by
# the per-test guard whenever it re-walks, and re-checked in ``pytest_sessionfinish``.
_DEEP_BASELINE: pytest.StashKey[dict[str, tuple[int, int]]] = pytest.StashKey()

# Undo handle for the session-wide Layer A install (see ``pytest_configure``).
_GUARD_PATCH: pytest.StashKey[pytest.MonkeyPatch] = pytest.StashKey()

# --------------------------------------------------------------------------- #
# What counts as production state
# --------------------------------------------------------------------------- #
# Trees whose contents are live, durable framework state. A test that writes here is
# mutating the developer's real capture stack, not exercising code.
#   discussions/ — Layer 1, immutable + sealed (the truncated-events.jsonl incident)
#   metrics/     — Layer 2, evaluation.db + the append-only trend logs
#   memory/      — Layer 3, curated + human-approved
#   loops/.state — /goal-loop runtime loop-state (ADR-0026)
_PROTECTED_TREES = ("discussions", "metrics", "memory", "loops/.state")

# Trees Layer B FINGERPRINTS but Layer A does not refuse — detection without refusal.
#
# `data/` holds the ADR-0014 assertion-store substrate (`data/memory.db`, 1.6 MB live). Exactly
# ONE test opens it: `tests/test_mcp_server.py::TestThreadLocalIsolation::
# test_two_threads_receive_distinct_connections`, measured 2026-08-08 by authorizer census — it
# prepares `CREATE TABLE IF NOT EXISTS assertions / entity_authorities` against the LIVE file
# through `assertion_store.substrate`'s module-level singleton. Refusing that (adding `data` to
# `_PROTECTED_TREES`) would deny the DDL at prepare time and fail a test that cannot be fixed
# from here — the fix is an injected db_path in `tests/test_mcp_server.py`, a different file.
#
# So the honest position is: not refused yet, but no longer INVISIBLE. Across three full suite
# runs `data/memory.db` kept mtime_ns 1778565145245838200 / 1634304 bytes — the DDL is
# `IF NOT EXISTS` and authorizes at prepare time without touching the file — so watching it costs
# one stat and stays green today, and goes red the first time that test starts really mutating
# the developer's substrate. That is strictly better than the previous `data` entry in
# `_ROOT_ALLOW_NAMES`, which bought nothing: `_ROOT_ALLOW_NAMES` only ever governed the `data`
# DIRECTORY entry, never `data/memory.db` (whose parent is not the repo root), so the file was
# unguarded either way and the allow-list entry only hid the directory from Layer B.
_WATCHED_TREES = ("data",)

# The subset re-walked in EVERY test's teardown. `discussions/` is deliberately absent: at ~380
# files it costs ~13 ms per walk (measured), which would dominate a suite of ~2 300 mostly
# sub-millisecond tests. It is covered instead by the subprocess-triggered deep walk and by
# `pytest_sessionfinish`. The trees listed here total <1 ms.
_CHEAP_TREES = ("metrics", "memory", "loops/.state", *_WATCHED_TREES)

# Direct children of the repo root are protected too — that is where `probe.lock` and the
# live `.collab_loop.lock` landed. Deeper source trees (src/, scripts/, tests/, docs/) are
# NOT guarded here: they are code, a test that rewrites them is a different failure, and
# guarding them would fight ordinary tooling. These names are written at the root by the
# test tooling itself and must stay allowed.
#
# `data` earns its place by measurement, which is what it previously lacked. It is the ADR-0014
# substrate directory: entirely untracked (`git ls-files data/` → 0 files, `data/memory.db`
# matched by the `*.db` ignore), so EVERY fresh clone and every derived project starts without
# it and `assertion_store.substrate` creates it via `db_path.parent.mkdir(parents=True,
# exist_ok=True)` on first use. Refusing that turns `tests/test_mcp_server.py::
# TestThreadLocalIsolation` red on every fresh checkout — measured, not predicted: removing this
# entry produced exactly that failure (`os.mkdir() on the repository root: …\data`).
#
# What the entry does NOT do, and what used to be claimed for it: it does not un-guard
# `data/memory.db`. `_ROOT_ALLOW_NAMES` only ever governed direct children of the root, and the
# substrate file's parent is `<root>/data`, not the root. The file's real coverage comes from
# `_WATCHED_TREES` above, which is Layer B and independent of this list.
_ROOT_ALLOW_NAMES = frozenset(
    {".coverage", "coverage.xml", ".pytest_cache", ".ruff_cache", "__pycache__", ".git", "data"}
)
# `.coverage.<host>.<pid>` — coverage's per-process shards.
# `pytest-cache-files-<rand>` — pytest's cacheprovider stages `.pytest_cache` through a
#   `tempfile.TemporaryDirectory(dir=rootdir)` the first time it builds the cache, i.e. whenever
#   `.pytest_cache` does not exist yet. Layer A runs for the whole session (including
#   `pytest_sessionfinish`, where that write happens), so without this the guard fails pytest's
#   OWN bookkeeping — and it does so only on a tree that has never been tested before, which is
#   every fresh clone and every derived project. Found by running the guard against a scratch
#   repo, which is exactly the check "an isolation mechanism that cannot be tested in isolation
#   is not yet trustworthy" was asking for.
_ROOT_ALLOW_PREFIXES = (".coverage.", "pytest-cache-files-")

# Captured at import, before any test can monkeypatch ``os``. A guard that reads the live
# module attribute is defeatable by the very tests it polices: ``test_telemetry`` patches
# ``os.scandir`` to raise, which made the teardown scan return nothing and report the entire
# repository root as deleted. The guard must observe the real filesystem, always.
_REAL_SCANDIR = os.scandir

# SQLite sidecars. (`Path.suffixes` is not used — `evaluation.db-wal` has no dotted suffix; the
# sidecar marker is a hyphen.)
#
# `-shm` is a shared-memory index rebuilt from the WAL and carries no durable content.
# `-journal` is a rollback journal that exists only mid-transaction: in rollback mode the commit
# itself lands in the `.db` file, so the `.db` fingerprint already covers that write. Both are
# ignored outright.
#
# `-wal` is NOT ignored, and that is the whole point. In WAL mode a COMMITTED write lands in the
# write-ahead log and the `.db` file's mtime and size stay untouched until a checkpoint. Measured
# 2026-08-07 against a scratch twin of this tree: a child process running
# `UPDATE findings …; commit(); os._exit(0)` (no clean close, so no checkpoint) left the database
# durably tampered while the run reported `1 passed`, exit code 0, and every `.db` fingerprint
# identical. Layer A cannot see a child process by construction, so excluding the WAL made
# Layer B blind to precisely the case it exists to catch.
#
# The original reason for excluding it — a read-only test can legitimately be the process that
# checkpoints the sidecar away — is handled without dropping the file: a ZERO-LENGTH `-wal` is
# not recorded at all, so "absent" and "present but empty" produce the same fingerprint. Only a
# WAL carrying actual frames registers, and a WAL carrying frames means an uncheckpointed write.
_IGNORED_SUFFIXES = ("-shm", "-journal")
_WAL_SUFFIX = "-wal"

_ROOT_STR = os.path.normcase(str(PROJECT_ROOT))
_PROTECTED_PREFIXES = tuple(
    os.path.normcase(str(PROJECT_ROOT / t)) + os.sep for t in _PROTECTED_TREES
)
_REPO_PREFIX = _ROOT_STR + os.sep


# --------------------------------------------------------------------------- #
# The declared concurrent writer
# --------------------------------------------------------------------------- #
# The framework's own turn-end telemetry kick (`scripts/stop_hook.py::_run_telemetry_kick`) writes
# `metrics/` while the suite runs, in this project and in every derived one. It stamps this file
# with `int(time.time())` EAGERLY — before spawning the writer — so the stamp is a usable beacon:
# it says "the declared writer started at T". `tests/test_layer1_integrity.py` pins both the path
# and the eagerness against `scripts/stop_hook.py`, so this stops being a guess the moment the hook
# is refactored.
#
# Reading the beacon is how the guard avoids the alternative, which is a list of exempt paths.
# An exempt-path list is the same defect as capture-by-diligence: it covers the paths someone
# remembered, and it stays open forever whether or not the writer ever runs. The beacon opens
# only while there is positive evidence the declared writer was actually running.
_TELEMETRY_BEACON = PROJECT_ROOT / ".claude" / "hooks" / ".state" / "telemetry-last-attempt"

# How long after the stamp the writer's child may still be landing bytes. The hook stamps, then
# runs the instrument as a subprocess bounded by `TELEMETRY_BUDGET_SECONDS = 15`; 30 s doubles
# that for scheduling slack. Measured gap between stamp and the resulting `evaluation.db` write:
# 0.819 s. This is the only tunable in the attribution rule, and widening it only ever widens the
# window in which an UNATTRIBUTED write is downgraded to a warning — it never suppresses a write
# the ledger attributes to a test.
_WRITER_BUDGET_SECONDS = 30.0


def _beacon_time() -> float | None:
    """Epoch seconds at which the declared concurrent writer last announced itself, or None.

    Falls back to the file's mtime if the contents are unreadable or not a number: a corrupt
    stamp still proves the hook touched it. Any failure returns None, which makes the guard
    STRICTER (nothing is excused), so a missing beacon can never be used to hide a write.
    """
    try:
        return float(_TELEMETRY_BEACON.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        pass
    try:
        return _TELEMETRY_BEACON.stat().st_mtime
    except OSError:
        return None


@dataclass
class _Activity:
    """What THIS process did during one test — the evidence Layer B attributes drift with.

    ``written`` is every repo path handed to a wrapped write primitive, whether the guard allowed
    it or refused it. It is the positive proof of authorship: if a drifted path is in here, the
    test wrote it and no beacon excuses it.
    """

    spawned: bool = False
    written: set[str] = field(default_factory=set)
    started: float = 0.0


# Module-level because the wrapped primitives are reached from arbitrary call sites and cannot be
# handed a fixture. Reset at the top of every test by `_production_state_guard`; the session-wide
# union is kept separately for `pytest_sessionfinish`, which has no per-test window to work with.
_ACTIVITY = _Activity()
_SESSION_WRITTEN: set[str] = set()


class ProductionWriteBlocked(BaseException):
    """A test tried to write to live production state.

    Inherits :class:`BaseException`, not :class:`Exception`, on purpose. The code under test
    is full of deliberate best-effort ``except OSError`` / ``except Exception`` handlers
    (``collab_loop.write_lock`` swallows ``OSError`` by design so a lockfile problem cannot
    wedge the loop). If this were an ordinary exception those handlers would absorb the
    guard and the contamination would be reported as a clean pass — exactly the "verification
    that errored is not a verification" failure. pytest reports ``BaseException`` outcomes
    normally (its own ``Failed``/``Skipped`` are ``BaseException`` subclasses).
    """


def _resolve(target: Any) -> str | None:
    """Normalize a filesystem argument to a comparable absolute path, or None if it is not one.

    File descriptors, ``None``, and anything that is not path-like are returned as None
    (nothing to guard). Uses ``abspath``+``normcase`` rather than ``realpath`` so the check
    stays cheap enough to sit on every ``open`` call in the suite.
    """
    if isinstance(target, int) or target is None:
        return None
    try:
        raw = os.fspath(target)
    except TypeError:
        return None
    if isinstance(raw, bytes):
        try:
            raw = raw.decode(sys.getfilesystemencoding())
        except UnicodeDecodeError:
            return None
    return os.path.normcase(os.path.abspath(raw))


# SQLite takes its database argument either as a plain path or as a `file:` URI
# (`sqlite3.connect(..., uri=True)`), and the URI form is the one this repository actually uses:
# every `uri=True` call site in scripts/ and tests/ opens `file:<path>?mode=ro`. `os.fspath` on
# that string yields the nonsense path `<cwd>/file:<path>?mode=ro`, which matches no protected
# prefix — so the guard silently declined to install its authorizer and a single careless
# `mode=rw` tampered with metrics/evaluation.db in-process while the run still reported
# `1 passed` and exit 0 (measured 2026-08-07). The URI must be parsed before the comparison.
_URI_SCHEME = "file:"

# URI modes that name no file on disk. `mode=memory` is a private in-memory database whose
# "path" is only a cache key, so guarding it would refuse writes to something that was never
# production state.
_NON_FILE_URI_MODES = frozenset({"memory"})

# Plain-path `sqlite3.connect` targets that name no file on disk.
_NON_FILE_TARGETS = frozenset({":memory:", ""})

# `uri` is the 8th parameter of `sqlite3.connect`. Passing it positionally is deprecated in
# 3.13 and nothing in this repo does it, but reading the flag only from kwargs would let a
# positional caller slip past — and this guard has to fail closed.
_URI_ARG_INDEX = 6


def _split_sqlite_uri(database: str) -> tuple[str | None, dict[str, str]]:
    """Split a SQLite ``file:`` URI into ``(filesystem path, query parameters)``.

    The path is returned as written (possibly relative — SQLite resolves it against the process
    cwd, and so does :func:`_resolve`). ``None`` is returned when the URI names nothing on disk:
    an in-memory database, or a ``file://<authority>/…`` form whose authority is not local.

    Duplicate query parameters keep the FIRST occurrence, matching ``sqlite3_uri_parameter``.
    A duplicate ``mode`` cannot be used to smuggle a writable handle past the ``mode=ro`` fast
    path: SQLite's URI parser only ever NARROWS the access mode, so the escalating spelling is
    rejected before this code sees a connection (measured on SQLite 3.50.4 —
    ``file:…?mode=ro&mode=rw`` raises ``OperationalError: access mode not allowed: rw``).
    """
    remainder, _, query = database[len(_URI_SCHEME) :].partition("?")
    params: dict[str, str] = {}
    for key, value in parse_qsl(query.split("#", 1)[0], keep_blank_values=True):
        params.setdefault(key, value)
    if remainder.startswith("//"):
        authority, _, rest = remainder[2:].partition("/")
        if authority not in ("", "localhost"):
            return None, params
        remainder = "/" + rest
    remainder = unquote(remainder)
    if not remainder or remainder == ":memory:" or params.get("mode") in _NON_FILE_URI_MODES:
        return None, params
    # `file:/C:/x` (a URI-absolute Windows path) names the file `C:/x`.
    if os.name == "nt" and len(remainder) > 2 and remainder[0] == "/" and remainder[2] == ":":
        remainder = remainder[1:]
    return remainder, params


def _resolve_database(database: Any, uri_enabled: bool) -> tuple[str | None, bool]:
    """Normalize a ``sqlite3.connect`` target to ``(absolute path or None, opened read-only)``.

    The read-only flag is the fast path: a ``mode=ro`` connection cannot write, so it keeps the
    unrestricted authorizer and the ordinary read-only call sites (``test_command_sql``,
    ``test_dashboard_server``, ``scripts/*``) behave exactly as before. Every other form —
    plain path, ``mode=rw``, ``mode=rwc``, no mode at all — is treated as writable and gets the
    authorizer if it points at protected state.

    When ``uri_enabled`` is false the string is NOT parsed as a URI, because SQLite would not
    parse it either: it would open a literal file of that name, which is what gets guarded.
    """
    if uri_enabled and isinstance(database, str) and database.startswith(_URI_SCHEME):
        path, params = _split_sqlite_uri(database)
        if path is None:
            return None, True
        return _resolve(path), params.get("mode") == "ro"
    if database in _NON_FILE_TARGETS:
        # `":memory:"` names no file, but `os.path.abspath` turns it into `<cwd>/:memory:` — and
        # when pytest runs from the repo root that is a direct child of the root, i.e. a
        # "violation". The effect was a read-only authorizer on ordinary in-memory databases:
        # `sqlite3.connect(":memory:")` then `CREATE TABLE` raised `not authorized`. Nothing in
        # this suite happened to do that, which is exactly how a trap survives to reach a
        # derived project.
        return None, True
    return _resolve(database), False


def _violation(path: str) -> str | None:
    """Return a human-readable reason if ``path`` is protected production state, else None."""
    if path.startswith(_PROTECTED_PREFIXES):
        return "a protected production tree"
    parent, name = os.path.split(path)
    if parent == _ROOT_STR:
        if name in _ROOT_ALLOW_NAMES or name.startswith(_ROOT_ALLOW_PREFIXES):
            return None
        return "the repository root"
    return None


def _note_write(resolved: str | None) -> None:
    """Record that this process handed ``resolved`` to a write primitive.

    Recorded for ALLOWED writes as much as refused ones — the point is authorship, not permission.
    Confined to paths inside the repository, which is the only region Layer B fingerprints.
    """
    if resolved is not None and resolved.startswith(_REPO_PREFIX):
        _ACTIVITY.written.add(resolved)
        _SESSION_WRITTEN.add(resolved)


def _refuse(target: Any, operation: str) -> None:
    """Raise :class:`ProductionWriteBlocked` if ``target`` names protected production state."""
    resolved = _resolve(target)
    if resolved is None:
        return
    _note_write(resolved)
    where = _violation(resolved)
    if where is None:
        return
    raise ProductionWriteBlocked(
        f"test attempted {operation} on {where}: {resolved}\n"
        f"Tests must never write live framework state. Use tmp_path (or a scratch copy of "
        f"the real bytes) instead. If this path genuinely is not production state, widen "
        f"the allow-list in tests/conftest.py — deliberately, in review."
    )


_WRITE_MODE_CHARS = frozenset("wxa+")
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC

# SQL actions that cannot change a database file. Everything else (INSERT/UPDATE/DELETE/
# CREATE_*/DROP_*/ALTER/REINDEX/VACUUM/ATTACH …) is denied on a protected DB — an allow-list,
# so a SQLite version that adds a new mutating action code is denied by default rather than
# admitted by an incomplete deny-list.
#
# `SQLITE_PRAGMA` is NOT in this set, and used to be. It was the one entry that falsified the
# sentence above: measured on SQLite 3.50.4, under the old allow-list
# `PRAGMA user_version=1234` was authorized, committed, and read back as 1234 from a fresh
# connection — a durable mutation of a "read-only" handle. `PRAGMA journal_mode`,
# `application_id`, `schema_version` and `wal_checkpoint` are the same shape. Pragmas are
# therefore judged by name (see `_PRAGMA_ALLOW`) rather than admitted wholesale.
_READ_ONLY_SQL_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_FUNCTION,
        sqlite3.SQLITE_TRANSACTION,
        sqlite3.SQLITE_RECURSIVE,
    }
)

# Pragmas allowed on a protected database. Two kinds, and nothing else:
#   * schema introspection — reports on the file, writes nothing to it;
#   * connection-scoped settings — live in this handle's memory, never reach the file.
#
# Deliberately absent, because their setter form edits the file: `user_version`,
# `application_id`, `schema_version`, `journal_mode`, `page_size`, `auto_vacuum`,
# `max_page_count`, `wal_checkpoint`, `optimize`, `incremental_vacuum`, `secure_delete`.
#
# Measured 2026-08-08 by authorizer census over a full suite run: the suite issues ZERO pragmas
# of any kind against a protected database (all 850+ pragma events — `foreign_keys=ON`,
# `journal_mode=WAL`, `table_info` — are on tmp_path databases, which carry no authorizer at
# all). This list is therefore headroom for a derived project's read path, not a compatibility
# requirement here; anything outside it fails loudly with `not authorized` and is widened in
# review, the same discipline as `_ROOT_ALLOW_NAMES`.
_PRAGMA_ALLOW = frozenset(
    {
        # Introspection.
        "table_info",
        "table_xinfo",
        "table_list",
        "index_list",
        "index_info",
        "index_xinfo",
        "foreign_key_list",
        "database_list",
        "collation_list",
        "function_list",
        "module_list",
        "pragma_list",
        "compile_options",
        "integrity_check",
        "quick_check",
        "page_count",
        "freelist_count",
        "data_version",
        # Connection-scoped.
        "foreign_keys",
        "busy_timeout",
        "cache_size",
        "synchronous",
        "temp_store",
        "query_only",
        "recursive_triggers",
        "read_uncommitted",
    }
)


def _read_only_authorizer(action: int, arg1: Any = None, *_rest: Any) -> int:
    """SQLite authorizer for a handle on protected state: reads pass, mutations are denied.

    A denial surfaces as ``sqlite3.DatabaseError: not authorized`` at the statement, not as
    :class:`ProductionWriteBlocked` — measured: an exception raised inside an authorizer callback
    does not propagate, SQLite converts it to a plain denial. So the seam cannot carry the guard's
    own message here, and the tests match on ``not authorized`` accordingly.
    """
    if action == sqlite3.SQLITE_PRAGMA:
        return sqlite3.SQLITE_OK if arg1 in _PRAGMA_ALLOW else sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK if action in _READ_ONLY_SQL_ACTIONS else sqlite3.SQLITE_DENY


def _attach_only_authorizer(action: int, arg1: Any = None, *_rest: Any) -> int:
    """Authorizer for an UNPROTECTED handle: allows everything except ATTACHing protected state.

    Without this, the protected-target check in :func:`guarded_connect` is trivially side-stepped:
    open a scratch database (no authorizer), then ``ATTACH '<repo>/metrics/evaluation.db' AS live``
    and write through the attached name. The connection target was never protected, so nothing
    downgraded it. ``SQLITE_ATTACH``'s first argument is the filename (measured on 3.50.4), which
    is exactly what the same :func:`_violation` rule needs.

    Everything else returns OK, so an ordinary tmp_path database behaves as if unauthorized —
    including ``CREATE TEMP TABLE``, which the read-only authorizer above would refuse.
    """
    if action != sqlite3.SQLITE_ATTACH:
        return sqlite3.SQLITE_OK
    if not arg1:  # `ATTACH ''` is a private temp database, on no protected path.
        return sqlite3.SQLITE_OK
    resolved = _resolve(arg1)
    if resolved is None or _violation(resolved) is None:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


# --------------------------------------------------------------------------- #
# Which primitives Layer A wraps — declared ONCE, so the installer and the
# "is it armed?" census cannot drift apart.
# --------------------------------------------------------------------------- #
# Single-target mutations: `os.<name>(path, …)`.
_SINGLE_TARGET_OS_CALLS = ("remove", "unlink", "rmdir", "truncate", "utime", "chmod")
# Two-target mutations: `os.<name>(src, dst, …)`. BOTH ends are refused — see the installer.
_TWO_TARGET_OS_CALLS = ("rename", "replace", "link", "symlink")

_PRIMITIVE_OWNERS: dict[str, Any] = {
    "builtins": builtins,
    "io": io,
    "os": os,
    "sqlite3": sqlite3,
    "subprocess": subprocess,
}

# Every seam `_install_write_guard` replaces, by dotted name.
_GUARDED_PRIMITIVES: tuple[str, ...] = (
    "builtins.open",
    "io.open",
    "os.open",
    "os.mkdir",
    *(f"os.{name}" for name in _SINGLE_TARGET_OS_CALLS),
    *(f"os.{name}" for name in _TWO_TARGET_OS_CALLS),
    "sqlite3.connect",
    "subprocess.Popen",
)


def _current_primitive(dotted: str) -> Any:
    """The object currently bound at ``<module>.<attr>``, or None if the platform lacks it."""
    owner, _, attr = dotted.partition(".")
    return getattr(_PRIMITIVE_OWNERS[owner], attr, None)


# Captured at IMPORT — conftest is imported before ``pytest_configure`` installs anything, so
# these are the untouched stdlib objects. Identity against them is the only honest answer to
# "is the boundary actually armed?": a boolean flag set by the installer would still read True
# after someone stubbed the installer's body out, and that is precisely the mutation a
# maintainer makes when checking whether a guard test still fails without its guard.
_PRISTINE_PRIMITIVES: dict[str, Any] = {d: _current_primitive(d) for d in _GUARDED_PRIMITIVES}


def _unguarded_primitives() -> tuple[str, ...]:
    """Dotted names of the Layer A seams that are NOT currently wrapped (empty when armed).

    Platform-absent primitives (``os.symlink`` on some Windows configurations) are skipped —
    :func:`_install_write_guard` skips them too, so reporting them would be a false alarm.
    """
    return tuple(
        dotted
        for dotted, pristine in _PRISTINE_PRIMITIVES.items()
        if pristine is not None and _current_primitive(dotted) is pristine
    )


def _guard_installed() -> bool:
    """True iff every Layer A seam is currently wrapped.

    Exists so a test that is about to aim a real write at real production state can REFUSE TO
    FIRE unless the thing meant to stop it is demonstrably in place — see
    ``tests/test_layer1_integrity.py::_require_refusal_is_armed``. Without that precondition the
    incident-replay tests re-commit their own incidents the moment the guard is disabled or
    absent, which makes the regression test for an incident a loaded weapon.
    """
    return not _unguarded_primitives()


def _install_write_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Wrap the Python-level write primitives so a production write raises at its call site.

    Installed once per SESSION. Per-test installation left collection time unguarded, which is a
    real hole and not a theoretical one: a module-level ``os.rename`` in a test file ran before any
    fixture and the contamination could only be reported at ``sessionfinish``, where no test can be
    named. Session scope means the offending *module* is named instead.

    Only *mutating* calls are refused; reads are untouched, because tests legitimately read
    real ``discussions/`` bytes to build scratch fixtures (``test_layer1_integrity``).

    ``builtins.open`` and ``io.open`` are the same object but are looked up through different
    namespaces — ``pathlib.Path.open`` calls ``io.open`` — so both bindings are replaced.
    ``Path.write_text``/``write_bytes`` route through ``Path.open``; ``Path.touch`` through
    ``os.utime``/``os.open``; ``Path.unlink``/``replace``/``rename``/``mkdir`` through the
    matching ``os`` call; ``shutil`` through ``open``/``os``. Wrapping this set therefore
    covers ``pathlib`` and ``shutil`` without patching them directly.

    ``subprocess.Popen`` is wrapped only to RECORD that a subprocess ran (a child process is
    invisible to this layer), which lets the Layer B diff run its expensive full-tree walk
    only for the tests that could have needed it.
    """
    real_open = builtins.open

    def guarded_open(file: Any, mode: str = "r", *args: Any, **kwargs: Any) -> Any:
        if _WRITE_MODE_CHARS & set(mode):
            _refuse(file, f"open(mode={mode!r})")
        return real_open(file, mode, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)

    real_os_open = os.open

    def guarded_os_open(path: Any, flags: int, *args: Any, **kwargs: Any) -> int:
        if flags & _WRITE_FLAGS:
            _refuse(path, f"os.open(flags={flags:#o})")
        return real_os_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(os, "open", guarded_os_open)

    # Single-target mutations.
    for name in _SINGLE_TARGET_OS_CALLS:
        real = getattr(os, name)

        def guarded(path: Any, *args: Any, _real: Any = real, _name: str = name, **kw: Any) -> Any:
            _refuse(path, f"os.{_name}()")
            return _real(path, *args, **kw)

        monkeypatch.setattr(os, name, guarded)

    real_mkdir = os.mkdir

    def guarded_mkdir(path: Any, *args: Any, **kwargs: Any) -> Any:
        # `mkdir` is the one wrapped call with an idempotent form: `Path.mkdir(exist_ok=True)`
        # calls it and swallows `FileExistsError`. Refusing before the real call denies a
        # request that would have changed NOTHING — which is not a boundary, it is a bug. It
        # showed up as `test_mcp_server.py::TestThreadLocalIsolation` failing on
        # `os.mkdir() on the repository root: …\data` for a directory that already existed.
        # Only a mkdir that would really create something is a write.
        resolved = _resolve(path)
        if resolved is not None and not os.path.exists(resolved):
            _refuse(path, "os.mkdir()")
        return real_mkdir(path, *args, **kwargs)

    monkeypatch.setattr(os, "mkdir", guarded_mkdir)

    # Two-target mutations: BOTH ends are checked, for two different reasons.
    #
    #   rename/replace — the source is DESTROYED at its old location. Checking only the
    #     destination missed the flagship incident shape in its move form:
    #     `os.rename(<sealed events.jsonl>, /tmp/x)` carried a sealed Layer 1 record out of
    #     `discussions/` with an innocent destination, and because `discussions/` is not in
    #     `_CHEAP_TREES` the per-test walk did not see it either. A sealed record destroyed by
    #     being moved away is destroyed exactly as much as one truncated in place.
    #   link/symlink — the source is LAUNDERED. These create a second name for the same file at
    #     an unprotected path, and every wrapper above judges the path it was handed, so
    #     `os.link(<sealed record>, tmp_path / "x")` followed by `open(tmp_path / "x", "w")` is a
    #     complete Layer A bypass. This is not theoretical: it was written as a test on
    #     2026-08-08 in the belief that link creation is harmless, and pytest's own tmp_path
    #     garbage collection then chmod'd the link to force-delete it — which cleared the
    #     read-only bit on the REAL sealed record at the other end of the hard link
    #     (DISC-20260313-210858, seal restored by hand; content verified byte-identical). The
    #     guard cannot police an alias it never saw created, so it refuses the alias.
    for name in _TWO_TARGET_OS_CALLS:
        real = getattr(os, name, None)
        if real is None:  # pragma: no cover — platform-dependent (os.symlink)
            continue

        def guarded2(src: Any, dst: Any, *args: Any, _real: Any = real, _n: str = name, **kw: Any):
            _refuse(dst, f"os.{_n}() destination")
            _refuse(src, f"os.{_n}() source (moving or aliasing it puts it beyond this guard)")
            return _real(src, dst, *args, **kw)

        monkeypatch.setattr(os, name, guarded2)

    real_connect = sqlite3.connect

    def guarded_connect(database: Any, *args: Any, **kwargs: Any) -> sqlite3.Connection:
        # SQLite writes through C-level file APIs, so the open()/os wrappers above are blind to
        # it — the seam has to be here, and it has to understand BOTH connect forms. It did not:
        # the earlier version fspath'd `file:…?mode=rw` into a path that matched nothing, so the
        # authorizer was never installed and an in-process URI write durably tampered with
        # metrics/evaluation.db under a green run (see `_URI_SCHEME`). `_resolve_database` parses
        # the URI, so plain paths and URIs are now judged by the same rule.
        #
        # REFUSING a writable connect would be the wrong control: a writable handle is not a
        # write, and the suite legitimately opens metrics/evaluation.db read-write and only
        # SELECTs from it (scripts/surface_candidates.py). Refusing would fail a test that never
        # touched a byte.
        #
        # So the handle is downgraded instead of denied: a read-only SQL authorizer is installed
        # on any connection to protected state that was not already opened `mode=ro`. Reads keep
        # working; the first statement that would actually mutate the file raises
        # `sqlite3.DatabaseError: not authorized` at that statement. Intent is allowed, the write
        # itself is not.
        #
        # Every OTHER connection gets `_attach_only_authorizer`, which allows everything except
        # ATTACHing protected state. That is the seam's second hole: a handle on a tmp_path
        # database is not protected, so nothing downgraded it, and `ATTACH '<repo>/metrics/
        # evaluation.db'` then wrote through the attached name with no authorizer in the way.
        # Measured cost of authorizing every connection: none detectable — a full suite run with
        # an authorizer on every handle finished in 180.6 s against a 219.6 s unauthorized
        # baseline (authorizer callbacks fire at statement PREPARE, not per row).
        uri_enabled = bool(
            kwargs.get("uri", args[_URI_ARG_INDEX] if len(args) > _URI_ARG_INDEX else False)
        )
        connection = real_connect(database, *args, **kwargs)
        resolved, read_only = _resolve_database(database, uri_enabled)
        writable_on_protected = (
            not read_only and resolved is not None and _violation(resolved) is not None
        )
        if writable_on_protected:
            # A writable handle is not yet a write, but it is this process declaring intent
            # toward that file — enough for Layer B to attribute later drift to this test rather
            # than excuse it as somebody else's. A `mode=ro` handle declares nothing.
            _note_write(resolved)
        connection.set_authorizer(
            _read_only_authorizer if writable_on_protected else _attach_only_authorizer
        )
        return connection

    monkeypatch.setattr(sqlite3, "connect", guarded_connect)

    real_popen = subprocess.Popen

    class RecordingPopen(real_popen):  # type: ignore[misc,valid-type]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            _ACTIVITY.spawned = True
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", RecordingPopen)


def _entry_signature(entry: os.DirEntry[str]) -> tuple[int, int] | None:
    """``(mtime_ns, size)`` for a file entry, or None when it must not be fingerprinted.

    Content-free SQLite sidecars are skipped before the stat. A ``-wal`` IS fingerprinted —
    it is the only durable trace of an uncheckpointed commit — but a zero-length one is
    skipped, which makes "no WAL" and "empty WAL" the same fingerprint and keeps a read-only
    test that checkpoints the sidecar away from reading as contamination.
    """
    if entry.name.endswith(_IGNORED_SUFFIXES):
        return None
    stat = entry.stat()
    if stat.st_size == 0 and entry.name.endswith(_WAL_SUFFIX):
        return None
    return (stat.st_mtime_ns, stat.st_size)


def _fingerprint(base: Path) -> dict[str, tuple[int, int]]:
    """Return ``{path: (mtime_ns, size)}`` for every file under ``base`` (empty if absent).

    ``scandir`` rather than ``os.walk``: on Windows the stat comes free from the directory
    enumeration, which roughly halves the cost of the ~380-file ``discussions/`` tree.
    """
    signature: dict[str, tuple[int, int]] = {}
    stack = [str(base)]
    while stack:
        try:
            entries = _REAL_SCANDIR(stack.pop())
        except OSError:
            continue
        with entries:
            for entry in entries:
                try:
                    if entry.is_dir(follow_symlinks=False):
                        stack.append(entry.path)
                        continue
                    value = _entry_signature(entry)
                    if value is not None:
                        signature[entry.path] = value
                except OSError:  # pragma: no cover — file vanished mid-scan
                    continue
    return signature


def _root_entries() -> dict[str, tuple[int, int]]:
    """Fingerprint the repo root's direct children only (cheap: one ``scandir``)."""
    signature: dict[str, tuple[int, int]] = {}
    try:
        entries = _REAL_SCANDIR(PROJECT_ROOT)
    except OSError:  # pragma: no cover
        return signature
    with entries:
        for entry in entries:
            if entry.name in _ROOT_ALLOW_NAMES or entry.name.startswith(_ROOT_ALLOW_PREFIXES):
                continue
            try:
                if not entry.is_file():
                    signature[entry.path] = (0, 0)
                    continue
                value = _entry_signature(entry)
                if value is not None:
                    signature[entry.path] = value
            except OSError:  # pragma: no cover
                continue
    return signature


def _cheap_fingerprint() -> dict[str, tuple[int, int]]:
    """Per-test surface: the repo root's children plus the small protected trees (<1 ms)."""
    signature = _root_entries()
    for tree in _CHEAP_TREES:
        signature.update(_fingerprint(PROJECT_ROOT / tree))
    return signature


def _deep_fingerprint() -> dict[str, tuple[int, int]]:
    """Fingerprint every protected + watched tree plus the repo root's children (~14 ms)."""
    signature = _root_entries()
    for tree in (*_PROTECTED_TREES, *_WATCHED_TREES):
        signature.update(_fingerprint(PROJECT_ROOT / tree))
    return signature


# Layer B compares the filesystem, so it sees ANY writer — including one outside this
# process. Observed 2026-08-07: a second agent editing the working tree during a run failed
# two unrelated subprocess tests. The check is deliberately kept anyway (excluding the
# commonly-edited root files would silently un-guard them, and a loud wrong answer beats a
# quiet miss), but the message must not accuse a test that did nothing.
_CONCURRENCY_CAVEAT = (
    "\nIf nothing in this test touches that path, check for a CONCURRENT writer: this layer "
    "diffs the filesystem, so another process editing the working tree mid-run looks the same. "
    "Re-run on a quiet tree to tell the two apart."
)


def _describe_drift(before: dict[str, tuple[int, int]], after: dict[str, tuple[int, int]]) -> str:
    """Render the added/removed/modified paths between two fingerprints (empty when clean)."""
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    parts = [
        f"{label}: {', '.join(paths[:10])}{' …' if len(paths) > 10 else ''}"
        for label, paths in (("created", added), ("deleted", removed), ("modified", changed))
        if paths
    ]
    return "; ".join(parts)


def _classify_drift(
    before: dict[str, tuple[int, int]],
    after: dict[str, tuple[int, int]],
    written: set[str],
    window_start: float,
    window_end: float,
) -> tuple[bool, str]:
    """Decide whether observed drift is the suite's doing. Returns ``(is_ours, why)``.

    Drift is the suite's — and so fails the test — unless EVERY ONE of five independent
    conditions says the declared concurrent writer (see :data:`_TELEMETRY_BEACON`) did it. All
    five are evidence about *this* run; none is a path someone put on a permanent exemption list:

    1. **No authorship.** No drifted path was handed to a write primitive by this process. This
       is the strong one — positive proof beats every excuse below, so a test that touched the
       file is blamed even if the writer was also running.
    2. **Nothing was deleted.** The declared writer appends rows and log lines; it removes
       nothing. A deletion is always ours.
    3. **Nothing shrank.** Same argument, and it is the one that keeps incident #1 — a sealed
       ``events.jsonl`` truncated to zero — un-excusable no matter what else is running.
    4. **The writer announced itself in this window.** Its throttle stamp has to overlap the
       test, allowing :data:`_WRITER_BUDGET_SECONDS` for the child it then spawns.
    5. **The bytes landed after the announcement.** Every drifted file's new mtime is at or
       after the stamp. A file modified *before* the writer started cannot be its work.

    A residual remains and is deliberate: a test's SUBPROCESS writing an appended or created
    protected file, inside the ~30 s window after a telemetry stamp, is excused. That window
    opens at most once per 600 s throttle. The alternative measured here — treating any drift in
    a subprocess-spawning test as ours — costs a spurious red across 76 % of the suite's wall
    clock (measured: 101.3 s of 133.4 s in-test seconds are inside subprocess-spawning tests),
    and a quality gate that reds one run in four is a quality gate people route around.
    """
    deleted = set(before) - set(after)
    common = set(before) & set(after)
    modified = {p for p in common if before[p] != after[p]}
    drifted = (set(after) - set(before)) | deleted | modified
    if not drifted:
        return False, ""
    # The ledger is keyed by `_resolve` (abspath + NORMCASE); the fingerprints are keyed by
    # `os.scandir`, which preserves the on-disk casing. On Windows those never intersect, so
    # comparing them raw silently made every ledger lookup miss — i.e. authorship, the strongest
    # evidence in this function, was dead code. Caught by `test_the_ledger_beats_the_beacon`,
    # which is aimed at `data/` precisely because Layer A does not mask the ledger there.
    touched = sorted(p for p in drifted if os.path.normcase(p) in written)
    if touched:
        return True, f"this test wrote {touched[0]}"
    if deleted:
        return True, f"{sorted(deleted)[0]} was DELETED; the declared writer never deletes"
    for path in sorted(modified):
        if after[path][1] < before[path][1]:
            return True, f"{path} SHRANK; the declared writer never truncates"
    beacon = _beacon_time()
    if beacon is None:
        return True, "no declared concurrent writer has ever announced itself"
    if beacon + _WRITER_BUDGET_SECONDS < window_start or beacon > window_end:
        return True, (
            f"the declared concurrent writer last announced itself at {beacon:.0f}, outside this "
            f"window ({window_start:.0f}–{window_end:.0f})"
        )
    late = [p for p in drifted & set(after) if after[p][0] < int((beacon - 1) * 1e9)]
    if late:
        return True, f"{late[0]} was modified BEFORE the declared writer announced itself"
    return False, f"the framework's turn-end telemetry announced itself at {beacon:.0f}"


@pytest.fixture(scope="session", autouse=True)
def _isolate_git_environment() -> None:
    """Remove inherited ``GIT_*`` env vars so test git subprocesses stay hermetic.

    See the module docstring: without this, the suite passes standalone but the pre-commit hook —
    which runs pytest while ``GIT_DIR`` etc. are set — breaks every test that shells out to git.
    """
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        os.environ.pop(key, None)


@pytest.fixture(scope="session", autouse=True)
def _collab_loop_lock_isolation(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    """Point the ntfy lockfile at a session scratch path, in-process AND for child processes.

    This is the ergonomic half of the boundary (the guard above is the enforcing half). It exists
    because the lockfile is the one production path the tests genuinely need a *working* stand-in
    for: ``collab_loop``'s ask/poll paths read and write it on nearly every code path, so refusing
    the write is not enough — they need somewhere real to go.

    ``COLLAB_LOOP_LOCK`` is set as well as the module global, so a ``collab_loop`` invoked in a
    SUBPROCESS (or an ad-hoc probe run from a shell that inherited this environment) also lands in
    scratch. The 2026-08-07 payload reached the live lockfile precisely because the module global
    is only reachable in-process.
    """
    scratch = tmp_path_factory.mktemp("collab_lock") / ".collab_loop.lock"
    os.environ["COLLAB_LOOP_LOCK"] = str(scratch)
    from scripts import collab_loop

    previous = collab_loop.LOCK_PATH
    collab_loop.LOCK_PATH = scratch
    try:
        yield scratch
    finally:
        collab_loop.LOCK_PATH = previous
        os.environ.pop("COLLAB_LOOP_LOCK", None)


# Drift this run saw but could not attribute to the suite. Reported loudly at session end and
# NOT failed — see `_classify_drift`. Kept as a list so the report names every occurrence.
_EXTERNAL_DRIFT: list[str] = []

_EXTERNAL_BANNER = "production-state guard: EXTERNAL DRIFT (not caused by the test suite)"
_EXTERNAL_EXPLAIN = (
    "\nThe suite did not write these paths and is not failing for them. Something else on this "
    "machine did — in this framework that is normally the turn-end telemetry kick "
    "(scripts/stop_hook.py). If you did not expect a concurrent writer, treat this as a real "
    "finding and go look."
)


@pytest.fixture(autouse=True)
def _production_state_guard(request: pytest.FixtureRequest) -> Iterator[None]:
    """Verify the protected trees are untouched after the test, and blame only the guilty.

    Layer A (installed for the whole session in :func:`pytest_configure`) raises inside the test.
    This fixture is Layer B: it diffs the trees around the test and, when they moved, asks
    :func:`_classify_drift` whether the suite did it.

    The deep walk runs only for a test that actually spawned a subprocess — the only way a write
    can slip past Layer A — so a shelling-out test pays ~12 ms and every other test pays ~0.1 ms
    for the repo-root scan. Its "before" side is the running deep baseline in the config stash,
    which stays valid precisely because a test that spawned nothing cannot have changed those
    trees without Layer A raising. The baseline is advanced whenever anything moved, attributed or
    not, so one event is reported once instead of being blamed on every test that follows it.
    """
    _ACTIVITY.spawned = False
    _ACTIVITY.written = set()
    _ACTIVITY.started = time.time()
    cheap_before = _cheap_fingerprint()
    yield
    deep = _ACTIVITY.spawned
    before = request.config.stash[_DEEP_BASELINE] if deep else cheap_before
    after = _deep_fingerprint() if deep else _cheap_fingerprint()
    if deep:
        request.config.stash[_DEEP_BASELINE] = after
    drift = _describe_drift(before, after)
    if not drift:
        return
    ours, why = _classify_drift(before, after, _ACTIVITY.written, _ACTIVITY.started, time.time())
    if not deep:
        # A cheap-walk finding leaves the deep baseline stale; refresh it so `sessionfinish`
        # does not re-report the same event with no test to name.
        request.config.stash[_DEEP_BASELINE] = _deep_fingerprint()
    if not ours:
        _EXTERNAL_DRIFT.append(f"{request.node.nodeid}: {drift}  [{why}]")
        return
    pytest.fail(
        "live production state changed while this test ran: "
        + drift
        + f"\nAttributed to this test because: {why}."
        + "\nTests must write only under tmp_path. See tests/conftest.py."
        + _CONCURRENCY_CAVEAT
    )


def pytest_configure(config: pytest.Config) -> None:
    """Install Layer A for the whole session and take the deep production fingerprint."""
    patch = pytest.MonkeyPatch()
    config.stash[_GUARD_PATCH] = patch
    _install_write_guard(patch)
    config.stash[_DEEP_BASELINE] = _deep_fingerprint()
    _ACTIVITY.started = time.time()


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the real write primitives (the session-wide Layer A install is undone here)."""
    patch = config.stash.get(_GUARD_PATCH, None)
    if patch is not None:  # pragma: no branch
        patch.undo()


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Fail the whole run if the SUITE changed the protected trees, even if every test passed.

    This is the backstop for writes made by SUBPROCESSES and by C-level file APIs, which no
    in-process wrapper can see, and for anything that landed between tests. It cannot name the
    offending test, so it prints the drift and forces a non-zero exit — a red run that says what
    changed beats a green run that hides it.

    Drift that :func:`_classify_drift` attributes to the declared concurrent writer is printed
    just as loudly but does NOT fail the run, here or in the per-test guard. That distinction is
    the whole point: this guard is only useful for as long as a red means "the suite did it".
    """
    baseline = session.config.stash.get(_DEEP_BASELINE, None)
    if baseline is None:  # pragma: no cover — configure always runs first
        return
    after = _deep_fingerprint()
    drift = _describe_drift(baseline, after)
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if drift:
        ours, why = _classify_drift(
            baseline, after, _SESSION_WRITTEN, _ACTIVITY.started, time.time()
        )
        if ours:
            message = (
                "PRODUCTION STATE CONTAMINATED BY THE TEST SUITE: "
                + drift
                + f"\nAttributed to the suite because: {why}."
                + "\nTests must write only under tmp_path. See tests/conftest.py."
                + _CONCURRENCY_CAVEAT
            )
            if reporter is not None:  # pragma: no branch
                reporter.write_sep("!", "production-state guard", red=True)
                reporter.write_line(message, red=True)
            session.exitstatus = 1
        else:
            _EXTERNAL_DRIFT.append(f"<between tests / after the last test>: {drift}  [{why}]")
    if _EXTERNAL_DRIFT and reporter is not None:
        reporter.write_sep("!", _EXTERNAL_BANNER, yellow=True)
        for line in _EXTERNAL_DRIFT:
            reporter.write_line(line, yellow=True)
        reporter.write_line(_EXTERNAL_EXPLAIN, yellow=True)
