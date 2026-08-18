"""Compile-and-run every SQL statement embedded in ``.claude/commands/*.md``.

Why this test exists
--------------------
Slash-command markdown files carry *live* SQL inside fenced code blocks. Nothing type-checks
them and nothing imports them, so a column rename in ``scripts/init_db.py`` silently rots the
read path and the command keeps "working". Three of these queries were broken simultaneously:

* ``SELECT * FROM v_agent_dashboard ORDER BY total_findings DESC``   (no such column, in the hub)
* ``SELECT * FROM v_rule_of_three ORDER BY discussion_count DESC``   (no such column, in the hub)
* ``SELECT status, COUNT(*) FROM promotion_candidates GROUP BY status`` (no such column, in hub)

and a bare ``except:`` in ``meta-review.md`` printed ``(v_agent_dashboard not available)``
instead of the error — teaching every reader that absence of data was normal. The same defect
was recorded once in ``memory/archive/build-status/BUILD_STATUS-archive-20260612.md`` and was
never fixed, because nothing enforced it. This test is that enforcement.

.. warning::

   **THIS GUARD DOES NOT TRAVEL WITH THE THING IT GUARDS.**

   ``.claude/commands/*.md`` is a *propagating framework tier*: ``/apply-framework`` copies it
   into every derived project (``scripts/distribute/assessment.py`` lists ``.claude/commands``
   in its interpolating tiers). ``tests/`` is **not** in ``FRAMEWORK_PATHS``
   (``scripts/distribute/change_package.py``), so this file stays in the hub. The rot this test
   exists to prevent is therefore prevented **only in the hub** — the one repo that was never
   going to forget.

   Two durable fixes, both outside this file and both requiring developer sign-off:

   1. add ``tests/test_command_sql.py`` to ``FRAMEWORK_PATHS`` so the guard propagates, or
   2. move the extraction + execution into a ``scripts/`` module (``scripts/`` *does*
      propagate) and leave this file as a thin wrapper around it.

   Until one of those lands, treat a green run here as evidence about the hub only.

The five kinds of check here
----------------------------
1. ``test_embedded_sql_runs_against_metrics_db`` — every extracted statement resolves against
   the *local* ``metrics/evaluation.db``. Skips when that file is absent.
2. ``test_command_object_names_exist_in_metrics_db`` — every table/view name passed as a bare
   literal to a command's own SQL helper (``dump_ordered``, ``dump_grouped``, ``columns_of``,
   ``resolve``, ``dump``) must exist in ``sqlite_master``. Check 1 cannot see these: the SQL
   there is built by concatenation, so it resolves through
   :data:`DYNAMIC_SQL_RECONSTRUCTIONS`, whose key is a *shape* (``SELECT * FROM <expr> LIMIT
   0``) — three different tables collapse to one hand-written statement and a table **rename
   or typo never reaches the database**. This check closes that hole.
3. ``test_command_block_survives_schema_variant`` — **hermetic**: builds a throwaway DB for
   each known schema generation (``modern`` = current hub, ``legacy`` = the pre-migration
   shape still live in derived projects, ``modern_no_dashboard`` = modern minus one view, which
   pins how an absent-but-known object must be *classified*) and *executes the real command
   blocks* against it in a subprocess, asserting the exit code that (block, variant) owes. This
   is the check that catches a "fix" which is correct in the hub and fatal everywhere else, and
   the one that catches a command contradicting itself about what an absent view means. It
   never skips. ``test_review_prior_findings_survives_an_empty_scope_list`` is its sibling for
   the other axis: caller input, where "you asked me nothing" must not read as "I am broken".
4. ``test_instrument_block_prints_every_column_the_view_offers`` — the completeness guard, and
   the only one that can see a repair which *narrows* an instrument. Seeds one row into each
   rendered view (``v_agent_dashboard``, ``v_rule_of_three``) per schema generation and asserts
   that every column the view answers appears in the block's stdout. A dropped ``print`` is
   invisible to every SQL check above; this is what caught ``agent_count`` (cross-agent
   corroboration) vanishing from ``retro.md`` 4b on the schema ``agentic_journal`` actually
   runs. Blocks are matched to views by the string literals they execute, not by substring, so
   a prose comment naming a view cannot drag a block under the wrong seed.
5. ``test_command_blocks_never_swallow_instrument_failures`` — semantic, AST-level. A bare
   ``except:`` is only the crudest form of the defect; ``except sqlite3.Error: print('… not
   available')`` is the *same bug wearing a jacket*, and an earlier regex-only guard was blind
   to it. See "the handler contract" below for what this now actually requires.

The handler contract (what check 4 enforces)
--------------------------------------------
An earlier version of this guard fired only when a handler *printed a phrase* from
:data:`_SWALLOW_PHRASES`. That let two strictly worse mutants through:

* a handler that prints **nothing at all** (``except sqlite3.Error: rows = []``) — the block
  falls through to its ``else:`` branch and reports "readable and empty", with no error text
  anywhere;
* a handler that exits **zero** (``print('… skipping'); sys.exit(0)``) — the command files'
  own prose defines exit 0 as "every instrument answered", so this reads to the caller as a
  clean run.

The contract is therefore about **termination, not wording**. Every ``except`` handler inside a
DB-touching command block must do one of:

a. re-raise (bare ``raise``, or raise anything that is not ``SystemExit(0)``);
b. exit with a **non-zero integer literal** (``sys.exit(1)`` / ``sys.exit(2)``). ``sys.exit()``
   and ``sys.exit(0)`` are swallows, and so is ``sys.exit(code)`` — a non-literal argument
   cannot be proven non-zero by inspection;
c. append the failure to an accumulator that the same block provably drains into a non-zero
   exit (``broken.append(label)`` … ``if broken: … sys.exit(1)``). This is the "keep reading
   the other instruments, then fail" pattern that ``retro.md`` and ``meta-review.md`` use, and
   it is a real escalation — the process still ends non-zero;
d. delegate to a helper defined in the same block that itself does one of the above
   (``meta-review.md`` factors its classification into ``note_error(label, e, ctx)``);
e. carry the explicit ``# instrument-optional: <reason>`` marker, for a genuinely optional path.

Known over-approximation: escalation is proved per *subtree*, not per path — a handler with
``sys.exit(1)`` on one branch and a silent fallthrough on another is accepted. Narrowing that
means path-sensitive analysis; the shapes this guard exists to catch (print-and-continue,
print-and-exit-0, assign-and-continue) have no escalating branch at all.

:data:`_SWALLOW_PHRASES` survives only as **extra evidence text** in the failure message, and as
the (weaker) trigger for handlers in blocks that never touch sqlite3 — those are not instrument
reads, and their files are outside this guard's repair scope.

Scope boundary (deliberate, not an oversight)
---------------------------------------------
Only SQL inside **fenced code blocks** is executed. That is where SQL that actually runs lives.
SQL quoted inline in prose is illustrative — e.g. ``retro.md`` documents
``SELECT COUNT(*) FROM findings WHERE disposition != 'open'`` as a query against a column that
*deliberately does not exist yet* (pending ADR-0030). Executing prose SQL would make that a
failure. ``test_sql_sites_are_discovered`` guards the other direction: if the extractor ever
stops finding statements, the suite fails rather than passing vacuously.

Safety
------
The local database is opened read-only (``mode=ro`` URI). ``SELECT``/``WITH`` statements are
executed and a few rows fetched; every mutating statement is only ``EXPLAIN``-prepared, which
resolves table and column names without running the statement. The schema-variant test runs
command blocks only against a **throwaway DB in a temp dir**, never the repo's own.
"""

from __future__ import annotations

import ast
import hashlib
import pathlib
import re
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMANDS_DIR = REPO_ROOT / ".claude" / "commands"
DB_PATH = REPO_ROOT / "metrics" / "evaluation.db"

#: Marker substituted for a non-literal sub-expression inside a concatenated SQL string.
DYNAMIC_MARKER = "<expr>"

_SQL_START = re.compile(r"^\s*(SELECT|WITH|INSERT|UPDATE|DELETE|REPLACE)\b", re.IGNORECASE)
_READ_ONLY_START = re.compile(r"^\s*(SELECT|WITH)\b", re.IGNORECASE)
#: ``<SCOPE_FILES>``, ``<candidate_id>``, ``<memory/patterns/file.md>`` … author placeholders
#: that make the snippet un-parseable as Python. They never appear inside the SQL itself.
_PLACEHOLDER = re.compile(r"<[^<>\n]{1,60}>")
_SQL_STRING_LITERAL = re.compile(r"'(?:[^']|'')*'")

#: Hand-written reconstructions for SQL that the command builds by string concatenation and
#: therefore cannot be recovered statically. Keyed by the *whitespace-normalised marker form*
#: of the statement, so the key changes exactly when the SQL changes — forcing a re-check.
#: An unregistered dynamic site is a hard failure, never a skip (see ``_resolve``).
#:
#: .. warning::
#:
#:    A key is a **shape**, not a statement. ``SELECT * FROM <expr> LIMIT 0`` matches every
#:    ``dump_ordered`` / ``dump_grouped`` / ``resolve`` probe regardless of which table it
#:    names, so misspelling a table name here changes nothing about what this registry
#:    executes. That blind spot is covered by
#:    :func:`test_command_object_names_exist_in_metrics_db`, which checks the literal table
#:    names directly against ``sqlite_master``. Do not rely on this registry to catch a rename.
DYNAMIC_SQL_RECONSTRUCTIONS: dict[str, str] = {
    # .claude/commands/review.md, Step 1.5 "Prior Findings on These Files".
    # `noise_clause` is "is_noise = 0 AND " when the column exists and "" when this project's
    # DB predates that migration; the OR-chain is built over the scope file list. Both the
    # filtered and unfiltered forms are registered — the degraded form must stay runnable.
    (
        "SELECT severity, category, summary, discussion_id FROM findings "
        "WHERE <expr>(<expr>) ORDER BY created_at DESC LIMIT 10"
    ): (
        "SELECT severity, category, summary, discussion_id FROM findings "
        "WHERE is_noise = 0 AND (raw_excerpt LIKE ? OR summary LIKE ?) "
        "ORDER BY created_at DESC LIMIT 10"
    ),
    # .claude/commands/retro.md 4b + meta-review.md, and review.md Step 7a: the ORDER BY /
    # WHERE column is resolved from the live schema, so only the shape is static here.
    "SELECT * FROM v_rule_of_three ORDER BY <expr> DESC": (
        "SELECT * FROM v_rule_of_three ORDER BY sighting_count DESC"
    ),
    "SELECT * FROM v_agent_dashboard ORDER BY <expr> DESC": (
        "SELECT * FROM v_agent_dashboard ORDER BY total_unique_findings DESC"
    ),
    "SELECT * FROM v_rule_of_three WHERE <expr> >= 3 ORDER BY <expr> DESC LIMIT 10": (
        "SELECT * FROM v_rule_of_three WHERE sighting_count >= 3 "
        "ORDER BY sighting_count DESC LIMIT 10"
    ),
    # meta-review.md Step 1 helpers: `dump_ordered` / `dump_grouped` / `resolve` build the
    # statement from a table name AND a resolved column name.
    "SELECT * FROM <expr> LIMIT 0": "SELECT * FROM v_agent_dashboard LIMIT 0",
    "SELECT * FROM <expr> ORDER BY <expr><expr>": (
        "SELECT * FROM v_agent_dashboard ORDER BY total_unique_findings DESC"
    ),
    "SELECT <expr>, COUNT(*) FROM <expr> GROUP BY <expr>": (
        "SELECT promoted, COUNT(*) FROM promotion_candidates GROUP BY promoted"
    ),
}

#: Command files known to embed SQL. Used only as a floor: if the extractor stops finding
#: statements in one of these, the extractor itself has regressed.
FILES_EXPECTED_TO_CONTAIN_SQL = (
    "batch-evaluate.md",
    "meta-review.md",
    "promote.md",
    "retro.md",
    "review.md",
)

#: Command files whose runnable blocks are exercised against every schema variant.
#: Scoped to the files this guard was written for. ``promote.md`` and ``batch-evaluate.md``
#: also embed schema-coupled SQL and SHOULD join this list — doing so requires editing those
#: command files to introspect first, which is follow-on work, not a silent exemption.
FILES_UNDER_SCHEMA_VARIANT_GUARD = ("retro.md", "meta-review.md", "review.md")

#: Phrases that turn an instrument failure into "there is simply no data here". Matching one
#: of these inside an ``except`` handler that neither re-raises nor exits is THE defect.
_SWALLOW_PHRASES = re.compile(
    r"not available|not yet created|not found|skipping|skipped|proceeding with manual|"
    r"falling back|fall back",
    re.IGNORECASE,
)

#: Opt-out for a genuinely optional path. Put this exact comment inside the handler body.
_SWALLOW_OK_MARKER = "instrument-optional:"

#: Handlers that swallow today and live OUTSIDE this guard's repair scope. This is an
#: EXACT-MATCH registry, not a filter: a new swallow fails the test, and *fixing* a listed
#: one ALSO fails the test until it is deleted from here. That is deliberate — an allowlist
#: that can rot into a permanent exemption is how the original defect survived for months.
#:
#: Keyed **per handler** (``<file>::<12 hex of sha256 over the whitespace-normalised handler
#: source>``, see :func:`_handler_identity`), NOT per file. A filename key would mean that once
#: ``promote.md`` is listed, a brand-new second swallowing handler anywhere in ``promote.md``
#: passes silently — the registry absorbing exactly the defect it exists to surface. Run
#: :func:`_find_swallowing_handlers` to print the key for a handler you intend to register.
KNOWN_UNFIXED_SWALLOWS: frozenset[str] = frozenset(
    {
        # promote.md Step 1: `except sqlite3.OperationalError:` ->
        #   "promotion_candidates table not available — proceeding with manual promotion."
        # Same defect class as the ones repaired in retro/meta-review/review, but promote.md
        # is outside this change's file scope. Reported to the developer as follow-on work.
        "promote.md::9116480b0f9a",
    }
)


@dataclass(frozen=True)
class SqlSite:
    """One SQL statement found in a command file."""

    file: str
    block_line: int
    sql: str
    dynamic: bool

    def __str__(self) -> str:  # pragma: no cover - pytest id only
        kind = "dynamic" if self.dynamic else "static"
        return f"{self.file}:~{self.block_line} [{kind}] {' '.join(self.sql.split())[:70]}"


def _normalise(sql: str) -> str:
    """Collapse all whitespace runs to single spaces."""
    return " ".join(sql.split())


def _iter_fenced_blocks(text: str) -> list[tuple[int, str, str]]:
    """Return ``(1-based start line, info string, body)`` for each fenced code block."""
    blocks: list[tuple[int, str, str]] = []
    lines = text.splitlines()
    idx = 0
    while idx < len(lines):
        if lines[idx].startswith("```"):
            info = lines[idx][3:].strip()
            start = idx + 1
            body: list[str] = []
            idx += 1
            while idx < len(lines) and not lines[idx].startswith("```"):
                body.append(lines[idx])
                idx += 1
            blocks.append((start, info, "\n".join(body)))
        idx += 1
    return blocks


def _unwrap_python_dash_c(body: str) -> str:
    r"""Strip a ``python -c "`` … ``"`` bash wrapper and undo its ``\"`` escaping."""
    lines = body.splitlines()
    if not lines:
        return body
    if lines[0].strip().rstrip("\\").strip() not in ('python -c "', 'python3 -c "'):
        return body
    # Drop the wrapper's opening line and its closing lone `"`.
    inner = lines[1:]
    while inner and inner[-1].strip() == "":
        inner.pop()
    if inner and inner[-1].strip() == '"':
        inner.pop()
    return "\n".join(inner).replace('\\"', '"')


def _fold_concatenation(node: ast.BinOp) -> str | None:
    """Fold an ``a + b + c`` chain into a string, marking non-literal parts.

    Returns ``None`` when the chain contains no string literal at all.
    """
    parts: list[str] = []
    saw_literal = False

    def walk(inner: ast.AST) -> None:
        nonlocal saw_literal
        if isinstance(inner, ast.BinOp) and isinstance(inner.op, ast.Add):
            walk(inner.left)
            walk(inner.right)
            return
        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
            saw_literal = True
            parts.append(inner.value)
            return
        parts.append(DYNAMIC_MARKER)

    walk(node)
    return "".join(parts) if saw_literal else None


def _parse_block(source: str, block_line: int, filename: str) -> ast.Module:
    """Parse a command code block as Python, failing loudly if it cannot be parsed."""
    try:
        return ast.parse(source)
    except SyntaxError:
        # Only now rewrite author placeholders such as `<SCOPE_FILES>`. Doing this
        # unconditionally would corrupt legitimate SQL comparisons like `a < b AND c > d`.
        try:
            return ast.parse(_PLACEHOLDER.sub("PLACEHOLDER", source))
        except SyntaxError as exc:
            pytest.fail(
                f"{filename}: code block starting at line {block_line} mentions sqlite3 but "
                f"could not be parsed as Python, so its SQL is UNVERIFIED: {exc}"
            )


def _collect_sql_from_python(source: str, block_line: int, filename: str) -> list[SqlSite]:
    """Parse ``source`` as Python and return every SQL-looking string it contains.

    Deliberately matches on *string literals that look like SQL* rather than on
    ``.execute(...)`` call sites: the command files pass SQL through helper functions, and an
    ``.execute``-keyed extractor would go blind the moment someone refactors.
    """
    tree = _parse_block(source, block_line, filename)
    sites: list[SqlSite] = []

    def walk(node: ast.AST) -> None:
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            folded = _fold_concatenation(node)
            if folded is not None and _SQL_START.match(folded):
                sites.append(SqlSite(filename, block_line, folded, dynamic=True))
                return
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and _SQL_START.match(node.value)
        ):
            sites.append(SqlSite(filename, block_line, node.value, dynamic=False))
            return
        for child in ast.iter_child_nodes(node):
            walk(child)

    walk(tree)
    return sites


def collect_sql_sites() -> list[SqlSite]:
    """Extract every SQL statement embedded in a fenced code block under ``.claude/commands``."""
    sites: list[SqlSite] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block_line, _info, body in _iter_fenced_blocks(text):
            if "sqlite3" not in body and ".execute(" not in body:
                continue
            source = _unwrap_python_dash_c(body)
            sites.extend(_collect_sql_from_python(source, block_line, path.name))
    return sites


#: Helpers the command files use to read a schema object whose name is passed as a *literal*
#: and then concatenated into SQL. Those names never reach :data:`SQL_SITES` as themselves —
#: they are absorbed into a ``<expr>`` shape — so they get their own existence check.
_OBJECT_ARG_HELPERS = frozenset({"dump", "dump_ordered", "dump_grouped", "columns_of", "resolve"})

#: A literal argument to one of those helpers is treated as a schema object name when it is a
#: bare lower-snake identifier. Human-readable labels ("Rule of Three", "Agent Effectiveness
#: (dashboard)") never match; SQL statements are excluded separately by :data:`_SQL_START`.
_OBJECT_NAME = re.compile(r"^[a-z_][a-z0-9_]*$")


@dataclass(frozen=True)
class ObjectRef:
    """A schema object named as a bare literal in a command file."""

    file: str
    line: int
    name: str

    def __str__(self) -> str:  # pragma: no cover - pytest id only
        return f"{self.file}:~{self.line} {self.name}"


def _iter_db_blocks() -> list[tuple[str, int, str]]:
    """Yield ``(filename, block start line, python source)`` for DB-touching command blocks."""
    out: list[tuple[str, int, str]] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        for block_line, info, body in _iter_fenced_blocks(path.read_text(encoding="utf-8")):
            if "sqlite3" not in body:
                continue
            source = body if info == "python" else _unwrap_python_dash_c(body)
            out.append((path.name, block_line, source))
    return out


def collect_object_refs() -> list[ObjectRef]:
    """Collect every table/view name passed as a bare literal to a command's SQL helper."""
    refs: list[ObjectRef] = []
    for filename, block_line, source in _iter_db_blocks():
        try:
            tree = ast.parse(_PLACEHOLDER.sub("PLACEHOLDER", source))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func_name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if func_name not in _OBJECT_ARG_HELPERS:
                continue
            for arg in node.args:
                if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                    continue
                if _SQL_START.match(arg.value) or not _OBJECT_NAME.match(arg.value):
                    continue
                refs.append(ObjectRef(filename, block_line + (node.lineno or 0), arg.value))
    return refs


OBJECT_REFS = collect_object_refs()


def _resolve(site: SqlSite) -> str:
    """Return an executable statement for ``site``, failing loudly on unknown dynamic SQL."""
    if not site.dynamic:
        return site.sql
    key = _normalise(site.sql)
    reconstruction = DYNAMIC_SQL_RECONSTRUCTIONS.get(key)
    if reconstruction is None:
        pytest.fail(
            f"{site.file}: SQL near line {site.block_line} is built by concatenation and has no "
            f"entry in DYNAMIC_SQL_RECONSTRUCTIONS, so it is UNVERIFIED. Add one keyed by:\n"
            f"    {key!r}"
        )
    return reconstruction


def _placeholder_count(sql: str) -> int:
    """Count ``?`` bind parameters, ignoring any inside SQL string literals."""
    return _SQL_STRING_LITERAL.sub("''", sql).count("?")


SQL_SITES = collect_sql_sites()

requires_db = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason=(
        "metrics/evaluation.db is absent — a derived project may not have one yet. "
        "This is the ONLY condition under which these checks skip."
    ),
)


@pytest.fixture(scope="module")
def readonly_conn():
    """Read-only connection to the metrics database."""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        yield conn
    finally:
        conn.close()


def test_sql_sites_are_discovered() -> None:
    """The extractor must keep finding SQL, or every other check here passes vacuously."""
    assert SQL_SITES, "no SQL extracted from .claude/commands/*.md — the extractor regressed"
    files_with_sql = {site.file for site in SQL_SITES}
    missing = [name for name in FILES_EXPECTED_TO_CONTAIN_SQL if name not in files_with_sql]
    assert not missing, (
        f"extractor found no SQL in {missing}, but those files embed SQL. "
        f"Files it did find: {sorted(files_with_sql)}"
    )


#: Sequences bash still rewrites inside a double-quoted string.
#: ``$`` alone is harmless (``re.compile(r'…$')`` is fine) — only ``$name``, ``${…}`` and
#: ``$(…)`` expand. A lone ``"`` closes the wrapper and silently truncates the program.
_SHELL_ACTIVE_IN_DQ = (
    (re.compile(r"`"), "backtick — bash runs the text between backticks as a command"),
    (re.compile(r"\$[A-Za-z_{(]"), "bash expands this as a variable / command substitution"),
    (re.compile(r'(?<!\\)"'), 'unescaped quote — closes the `python -c "` string early'),
)


def _python_dash_c_body_lines(body: str) -> list[str] | None:
    """Raw (still bash-escaped) lines inside a ``python -c "`` wrapper, or ``None``.

    Deliberately returns the lines *before* :func:`_unwrap_python_dash_c` un-escapes ``\\"``,
    because the whole point is to inspect what bash sees, not what Python receives.
    """
    lines = body.splitlines()
    if not lines or lines[0].strip().rstrip("\\").strip() not in ('python -c "', 'python3 -c "'):
        return None
    inner = lines[1:]
    while inner and inner[-1].strip() == "":
        inner.pop()
    if inner and inner[-1].strip() == '"':
        inner.pop()  # the wrapper's own closing quote is not part of the program
    return inner


@pytest.mark.regression
def test_python_dash_c_blocks_have_no_shell_active_characters() -> None:
    r"""A ``python -c "…"`` instrument block must survive bash's double-quote rules unchanged.

    Real defect this caught: a Python comment written as ``# `obj` is the …`` inside
    ``retro.md`` made bash execute ``obj`` as a command and splice its (empty) output into the
    program — printing ``obj: command not found`` and silently mangling that line. Nothing else
    in this suite could see it, because every other check unwraps the block and runs it as a
    ``.py`` file, which skips bash entirely.

    Scope: DB-touching blocks only. Other command files intentionally rely on shell expansion
    inside ``python -c`` (``ship.md`` reads ``'$ARGUMENTS'`` that way), and those files are
    outside this guard's repair scope — widening it would break them without fixing anything.
    """
    offenders: list[str] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        for block_line, info, body in _iter_fenced_blocks(path.read_text(encoding="utf-8")):
            if info != "bash" or "sqlite3" not in body:
                continue
            lines = _python_dash_c_body_lines(body)
            if lines is None:
                continue
            for offset, line in enumerate(lines, start=1):
                for pattern, why in _SHELL_ACTIVE_IN_DQ:
                    for match in pattern.finditer(line):
                        offenders.append(
                            f"{path.name}:~{block_line + offset} col {match.start()}: "
                            f"{match.group()!r} — {why}: {line.strip()[:80]}"
                        )
    assert not offenders, (
        'these `python -c "…"` instrument blocks contain text bash rewrites before Python ever '
        "sees it:\n" + "\n".join(offenders)
    )


def test_object_refs_are_discovered() -> None:
    """Guards the object-name check against passing vacuously if the helpers get renamed."""
    assert OBJECT_REFS, (
        "no table/view names extracted from helper calls in .claude/commands/*.md. Either the "
        "commands stopped using dump/dump_ordered/dump_grouped/columns_of/resolve (update "
        "_OBJECT_ARG_HELPERS) or the extractor regressed — either way this check is now blind "
        "to a table rename."
    )
    names = {ref.name for ref in OBJECT_REFS}
    assert {"v_agent_dashboard", "v_rule_of_three"} <= names, (
        f"expected the two dashboards among the extracted object names, got {sorted(names)}"
    )


@requires_db
@pytest.mark.regression
@pytest.mark.parametrize("ref", OBJECT_REFS, ids=str)
def test_command_object_names_exist_in_metrics_db(ref: ObjectRef, readonly_conn) -> None:
    """A table/view a command names as a literal must actually exist.

    Regression guard for the reconstruction hole: ``dump_ordered(label, 'v_agent_dashbord',
    …)`` builds its SQL by concatenation, so :func:`test_embedded_sql_runs_against_metrics_db`
    resolves it through the *shape* key ``SELECT * FROM <expr> LIMIT 0`` and executes a
    hand-written statement naming the correct table. The misspelled name never reaches SQLite,
    and at runtime the command reports the typo as a benign "pre-migration" absence. This
    check reads the literal name and asks the database directly.
    """
    names = {
        row[0]
        for row in readonly_conn.execute(
            "SELECT name FROM sqlite_master WHERE type IN ('table', 'view')"
        )
    }
    assert ref.name in names, (
        f"{ref.file} (near line {ref.line}) reads schema object {ref.name!r}, which does not "
        f"exist in metrics/evaluation.db. In the hub — the repo that DEFINES the schema — that "
        f"is a typo or an un-propagated rename, never a missing migration. Existing objects: "
        f"{sorted(names)}"
    )


@requires_db
@pytest.mark.parametrize("site", SQL_SITES, ids=str)
def test_embedded_sql_runs_against_metrics_db(site: SqlSite, readonly_conn) -> None:
    """Every embedded statement must resolve against the real schema.

    ``SELECT``/``WITH`` are executed; mutating statements are ``EXPLAIN``-prepared, which
    resolves names without writing.
    """
    sql = _resolve(site)
    params = tuple("%" for _ in range(_placeholder_count(sql)))
    try:
        if _READ_ONLY_START.match(sql):
            readonly_conn.execute(sql, params).fetchmany(5)
        else:
            readonly_conn.execute("EXPLAIN " + sql, params)
    except sqlite3.Error as exc:
        pytest.fail(
            f"{site.file} (code block starting line {site.block_line}) embeds SQL that fails "
            f"against metrics/evaluation.db:\n"
            f"  {type(exc).__name__}: {exc}\n"
            f"  statement: {_normalise(sql)}"
        )


# --------------------------------------------------------------------------------------
# Schema-variant execution
# --------------------------------------------------------------------------------------
# The hub's own evaluation.db is only ONE schema generation. Derived projects created before
# the pattern_sightings / agent_effectiveness / findings migrations still carry the older
# column names, and `.claude/commands/*.md` propagates INTO those projects. A repair that is
# correct against the hub and fatal against a derived project is not a repair. The DDL below
# is transcribed from the two live generations (`SELECT sql FROM sqlite_master`).

_MODERN_SCHEMA = """
CREATE TABLE discussions (
    discussion_id TEXT PRIMARY KEY, created_at DATETIME, closed_at DATETIME,
    risk_level TEXT, collaboration_mode TEXT, exploration_intensity TEXT, status TEXT,
    linked_decision TEXT, linked_pr TEXT, agent_count INTEGER, command_type TEXT,
    duration_minutes REAL, related_discussion_id TEXT,
    total_tokens_in INTEGER, total_tokens_out INTEGER, total_cache_tokens INTEGER);
CREATE TABLE turns (
    id INTEGER PRIMARY KEY, discussion_id TEXT, turn_id INTEGER, agent TEXT,
    reply_to INTEGER, intent TEXT, timestamp DATETIME, confidence REAL,
    content_hash TEXT, content_excerpt TEXT, tags TEXT,
    tokens_in INTEGER, tokens_out INTEGER, cache_read_tokens INTEGER,
    cache_create_tokens INTEGER);
CREATE TABLE findings (
    id INTEGER PRIMARY KEY, discussion_id TEXT, turn_id INTEGER, agent TEXT,
    severity TEXT, category TEXT, summary TEXT, raw_excerpt TEXT,
    resolved BOOLEAN NOT NULL DEFAULT 0, created_at DATETIME,
    is_noise INTEGER NOT NULL DEFAULT 0);
CREATE TABLE reflections (
    reflection_id TEXT PRIMARY KEY, discussion_id TEXT, agent TEXT, missed_signal TEXT,
    improvement_rule TEXT, confidence_delta REAL, promoted BOOLEAN, created_at DATETIME);
CREATE TABLE education_results (
    id INTEGER PRIMARY KEY, session_id TEXT, discussion_id TEXT, bloom_level TEXT,
    question_type TEXT, score REAL, passed BOOLEAN, timestamp DATETIME);
CREATE TABLE protocol_yield (
    id INTEGER PRIMARY KEY, discussion_id TEXT, protocol_type TEXT,
    findings_blocking INTEGER, findings_advisory INTEGER, findings_false_positive INTEGER,
    agent_turns_used INTEGER, outcome TEXT, timestamp DATETIME);
CREATE TABLE pattern_sightings (
    id INTEGER PRIMARY KEY, pattern_hash TEXT NOT NULL, discussion_id TEXT,
    category TEXT NOT NULL, summary TEXT NOT NULL, source TEXT NOT NULL,
    created_at DATETIME NOT NULL);
CREATE TABLE agent_effectiveness (
    id INTEGER PRIMARY KEY, agent TEXT NOT NULL, discussion_id TEXT NOT NULL,
    findings_unique INTEGER NOT NULL DEFAULT 0,
    findings_duplicate INTEGER NOT NULL DEFAULT 0,
    findings_false_positive INTEGER NOT NULL DEFAULT 0,
    confidence_avg REAL, confidence_calibration REAL, computed_at DATETIME NOT NULL);
CREATE TABLE promotion_candidates (
    id INTEGER PRIMARY KEY, finding_pattern TEXT NOT NULL, category TEXT NOT NULL,
    sighting_count INTEGER NOT NULL DEFAULT 1, first_seen DATETIME NOT NULL,
    last_seen DATETIME NOT NULL, promoted BOOLEAN NOT NULL DEFAULT 0,
    promoted_at DATETIME, promoted_to TEXT, evidence_ids TEXT NOT NULL DEFAULT '[]');
CREATE VIEW v_rule_of_three AS
    SELECT category, pattern_hash, summary,
           COUNT(DISTINCT discussion_id) AS sighting_count,
           MIN(created_at) AS first_seen, MAX(created_at) AS last_seen,
           GROUP_CONCAT(DISTINCT discussion_id) AS discussion_ids
    FROM pattern_sightings GROUP BY pattern_hash
    HAVING COUNT(DISTINCT discussion_id) >= 3 ORDER BY sighting_count DESC;
CREATE VIEW v_agent_dashboard AS
    SELECT ae.agent,
           COUNT(DISTINCT ae.discussion_id) AS discussions_participated,
           SUM(ae.findings_unique) AS total_unique_findings,
           SUM(ae.findings_duplicate) AS total_duplicate_findings,
           SUM(ae.findings_false_positive) AS total_false_positives,
           ROUND(AVG(ae.confidence_avg), 3) AS avg_confidence,
           ROUND(AVG(ae.confidence_calibration), 3) AS avg_calibration,
           ROUND(CAST(SUM(ae.findings_unique) AS REAL) /
                 NULLIF(SUM(ae.findings_unique) + SUM(ae.findings_duplicate), 0), 3)
               AS uniqueness_ratio
    FROM agent_effectiveness ae GROUP BY ae.agent ORDER BY total_unique_findings DESC;
"""

_LEGACY_SCHEMA = """
CREATE TABLE discussions (
    discussion_id TEXT PRIMARY KEY, created_at DATETIME, closed_at DATETIME,
    risk_level TEXT, collaboration_mode TEXT, exploration_intensity TEXT, status TEXT,
    linked_decision TEXT, linked_pr TEXT, agent_count INTEGER, command_type TEXT,
    duration_minutes REAL, related_discussion_id TEXT);
CREATE TABLE turns (
    id INTEGER PRIMARY KEY, discussion_id TEXT, turn_id INTEGER, agent TEXT,
    reply_to INTEGER, intent TEXT, timestamp DATETIME, confidence REAL,
    content_hash TEXT, content_excerpt TEXT, tags TEXT);
CREATE TABLE findings (
    id INTEGER PRIMARY KEY, finding_id TEXT, discussion_id TEXT, turn_id INTEGER,
    agent TEXT, severity TEXT, category TEXT, summary TEXT, content_excerpt TEXT,
    disposition TEXT NOT NULL DEFAULT 'open', resolution_ref TEXT, tags TEXT,
    created_at DATETIME, promoted_at DATETIME);
CREATE TABLE reflections (
    reflection_id TEXT PRIMARY KEY, discussion_id TEXT, agent TEXT, missed_signal TEXT,
    improvement_rule TEXT, confidence_delta REAL, promoted BOOLEAN, created_at DATETIME);
CREATE TABLE education_results (
    id INTEGER PRIMARY KEY, session_id TEXT, discussion_id TEXT, bloom_level TEXT,
    question_type TEXT, score REAL, passed BOOLEAN, timestamp DATETIME);
CREATE TABLE protocol_yield (
    id INTEGER PRIMARY KEY, discussion_id TEXT, protocol_type TEXT,
    findings_blocking INTEGER, findings_advisory INTEGER, findings_false_positive INTEGER,
    agent_turns_used INTEGER, outcome TEXT, timestamp DATETIME);
CREATE TABLE pattern_sightings (
    id INTEGER PRIMARY KEY, pattern_key TEXT NOT NULL, finding_id TEXT,
    discussion_id TEXT NOT NULL, agent TEXT NOT NULL, source_type TEXT NOT NULL,
    sighted_at DATETIME NOT NULL);
CREATE TABLE agent_effectiveness (
    id INTEGER PRIMARY KEY, discussion_id TEXT NOT NULL, agent TEXT NOT NULL,
    findings_produced INTEGER NOT NULL DEFAULT 0,
    findings_unique INTEGER NOT NULL DEFAULT 0,
    findings_survived INTEGER NOT NULL DEFAULT 0,
    findings_dropped INTEGER NOT NULL DEFAULT 0,
    confidence_avg REAL, confidence_accuracy REAL, computed_at DATETIME NOT NULL);
CREATE TABLE promotion_candidates (
    id INTEGER PRIMARY KEY, candidate_id TEXT, candidate_type TEXT, source_type TEXT,
    source_refs TEXT, title TEXT, summary TEXT, evidence_count INTEGER,
    target_path TEXT, status TEXT NOT NULL DEFAULT 'pending', human_verdict TEXT,
    created_at DATETIME, reviewed_at DATETIME, promoted_at DATETIME,
    last_referenced_at DATETIME);
CREATE VIEW v_rule_of_three AS
    SELECT pattern_key,
           COUNT(DISTINCT discussion_id) AS discussion_count,
           COUNT(DISTINCT agent) AS agent_count,
           MIN(sighted_at) AS first_seen, MAX(sighted_at) AS last_seen,
           GROUP_CONCAT(DISTINCT discussion_id) AS discussions
    FROM pattern_sightings GROUP BY pattern_key
    HAVING COUNT(DISTINCT discussion_id) >= 3;
CREATE VIEW v_agent_dashboard AS
    SELECT agent, COUNT(*) AS discussions,
           SUM(findings_produced) AS total_findings,
           SUM(findings_unique) AS total_unique,
           ROUND(CAST(SUM(findings_unique) AS REAL) /
                 NULLIF(SUM(findings_produced), 0) * 100, 1) AS uniqueness_pct,
           ROUND(CAST(SUM(findings_survived) AS REAL) /
                 NULLIF(SUM(findings_produced), 0) * 100, 1) AS survival_pct,
           ROUND(AVG(confidence_avg), 3) AS avg_confidence,
           ROUND(AVG(confidence_accuracy), 3) AS avg_calibration
    FROM agent_effectiveness GROUP BY agent;
"""

#: The modern schema with ``v_agent_dashboard`` removed. Not a hypothetical: it is the shape a
#: project has when it ran the ``pattern_sightings`` migration but not the
#: ``agent_effectiveness`` one. It exists here because both other DDLs supply every object the
#: blocks read, so *no test could see* ``meta-review.md`` classifying one absent view as
#: DEGRADED in Step 1 and INSTRUMENT FAILURE in Step 2 — the command contradicting itself.
_MODERN_SCHEMA_NO_DASHBOARD = _MODERN_SCHEMA.split("CREATE VIEW v_agent_dashboard")[0]

SCHEMA_VARIANTS = {
    "modern": _MODERN_SCHEMA,
    "legacy": _LEGACY_SCHEMA,
    "modern_no_dashboard": _MODERN_SCHEMA_NO_DASHBOARD,
}

#: Substituted for the author placeholder in review.md Step 1.5 so the block can be run.
_SCOPE_FILES_SAMPLE = "['src/context_sensor.py', 'scripts/quality_gate.py']"


@dataclass(frozen=True)
class CommandBlock:
    """One runnable Python block extracted from a command file."""

    file: str
    block_line: int
    source: str

    def __str__(self) -> str:  # pragma: no cover - pytest id only
        return f"{self.file}:~{self.block_line}"


def collect_runnable_blocks() -> list[CommandBlock]:
    """Return every DB-touching Python block from the files under the schema-variant guard."""
    blocks: list[CommandBlock] = []
    for name in FILES_UNDER_SCHEMA_VARIANT_GUARD:
        path = COMMANDS_DIR / name
        for block_line, info, body in _iter_fenced_blocks(path.read_text(encoding="utf-8")):
            if "sqlite3" not in body:
                continue
            source = body if info == "python" else _unwrap_python_dash_c(body)
            if source is body and info not in ("python",):
                continue  # a bash block that mentions sqlite3 but is not `python -c`
            source = source.replace("<SCOPE_FILES>", _SCOPE_FILES_SAMPLE)
            blocks.append(CommandBlock(name, block_line, source))
    return blocks


RUNNABLE_BLOCKS = collect_runnable_blocks()


def _build_variant_db(target: pathlib.Path, ddl: str) -> None:
    """Create an empty-but-well-formed DB of one schema generation."""
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    try:
        conn.executescript(ddl)
        conn.commit()
    finally:
        conn.close()


def test_runnable_blocks_are_discovered() -> None:
    """Guards the schema-variant test against passing vacuously."""
    assert RUNNABLE_BLOCKS, "no runnable command blocks found — the extractor regressed"
    found = {b.file for b in RUNNABLE_BLOCKS}
    expected = set(FILES_UNDER_SCHEMA_VARIANT_GUARD)
    assert found == expected, (
        f"expected runnable blocks in {sorted(expected)}, found {sorted(found)}"
    )


def _block_reads(source: str, view: str) -> bool:
    """True when ``source`` reads schema object ``view`` — judged from STRING LITERALS only.

    Deliberately not ``view in source``: a prose comment ("the same idiom 4c uses for
    v_agent_dashboard") would then make a block look like a reader of a view it never touches,
    which silently mis-classifies its expected exit code and drags it under the wrong
    completeness seed. Two literal forms count, because the commands use both: the bare object
    name passed to a helper (``columns_of(label, probe, 'v_agent_dashboard')``,
    ``dump_ordered(label, 'v_agent_dashboard', …)``) and an inline ``FROM <view>``.
    """
    try:
        tree = ast.parse(_PLACEHOLDER.sub("PLACEHOLDER", source))
    except SyntaxError:  # pragma: no cover - runnable blocks always parse
        return view in source
    inline = re.compile(r"\bFROM\s+" + re.escape(view) + r"\b", re.IGNORECASE)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == view or inline.search(node.value):
                return True
    return False


def _expected_variant_exit(block: CommandBlock, variant: str) -> int:
    """The exit code a block MUST produce on ``variant``.

    ``modern`` and ``legacy`` supply every object every block reads, so the answer is always 0.
    ``modern_no_dashboard`` deliberately withholds one view that the framework itself ships in a
    later migration: a block that reads ``v_agent_dashboard`` must call that **DEGRADED (exit
    2)** — a known object this project has not migrated to yet — and every other block must be
    unaffected (exit 0). Pinning 2 rather than "0 or 2" is the point: it is what makes a
    command that classifies the same absence as INSTRUMENT FAILURE (exit 1) go red.
    """
    if variant == "modern_no_dashboard" and _block_reads(block.source, "v_agent_dashboard"):
        return 2
    return 0


@pytest.mark.regression
@pytest.mark.parametrize("variant", sorted(SCHEMA_VARIANTS), ids=str)
@pytest.mark.parametrize("block", RUNNABLE_BLOCKS, ids=str)
def test_command_block_survives_schema_variant(block: CommandBlock, variant: str) -> None:
    """A command block must RUN against every known schema generation, not just the hub's.

    Regression guard for the inversion where repairs pinned to hub column names
    (``total_unique_findings``, ``sighting_count``, ``promoted``, ``is_noise``) turned
    ``/retro``, ``/meta-review`` and ``/review`` into ``sys.exit(1)`` in derived projects
    whose ``evaluation.db`` predates those migrations.

    Contract: the exit code recorded by :func:`_expected_variant_exit`, never "any of 0/2". The
    ``modern`` and ``legacy`` DDLs contain every table and view these blocks read, so every
    instrument must answer (exit 0); ``modern_no_dashboard`` withholds exactly one known view
    and pins the classification of that absence to DEGRADED (exit 2).

    This used to accept ``in (0, 2)`` unconditionally, which was a hole: a *misspelled* view
    name degraded to exit 2 and the guard stayed green while the command silently lost that
    instrument. Do not loosen it back. If a genuinely modern-only instrument is added later,
    the fix is to add the object to :data:`_LEGACY_SCHEMA` (if derived projects really have it)
    or to extend :func:`_expected_variant_exit` — never to widen the accepted set.
    """
    expected = _expected_variant_exit(block, variant)
    with tempfile.TemporaryDirectory(prefix="cmd-sql-variant-") as tmp:
        work = pathlib.Path(tmp)
        _build_variant_db(work / "metrics" / "evaluation.db", SCHEMA_VARIANTS[variant])
        script = work / "_block.py"
        script.write_text(block.source, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, script.name],
            cwd=work,
            capture_output=True,
            text=True,
            timeout=120,
        )
    combined = proc.stdout + proc.stderr
    assert "Traceback (most recent call last)" not in combined, (
        f"{block} crashed with an unhandled exception on the '{variant}' schema:\n"
        f"{combined[-1500:]}"
    )
    assert proc.returncode == expected, (
        f"{block} exited {proc.returncode} on the '{variant}' schema; the contract for this "
        f"(block, variant) pair is exit {expected}. Exit 1 means INSTRUMENT FAILURE (the block "
        f"declared a query broken, or declared a MISSING-but-known object to be a broken query "
        f"— which is the self-contradiction modern_no_dashboard exists to catch); exit 2 means "
        f"DEGRADED (it declared an object missing that this DDL provides — often a misspelled "
        f"table name).\n{combined[-1500:]}"
    )


#: Substituted for ``<SCOPE_FILES>`` to reproduce "the caller handed this step nothing".
_SCOPE_FILES_EMPTY = "[]"


def _extract_block_source(filename: str, needle: str, scope_files: str) -> str:
    """Return one DB-touching block's Python source, chosen by a substring of its body."""
    path = COMMANDS_DIR / filename
    for _block_line, info, body in _iter_fenced_blocks(path.read_text(encoding="utf-8")):
        if "sqlite3" not in body or needle not in body:
            continue
        source = body if info == "python" else _unwrap_python_dash_c(body)
        return source.replace("<SCOPE_FILES>", scope_files)
    raise AssertionError(f"no DB block in {filename} containing {needle!r}")


@pytest.mark.regression
@pytest.mark.parametrize("variant", sorted(SCHEMA_VARIANTS), ids=str)
def test_review_prior_findings_survives_an_empty_scope_list(variant: str) -> None:
    """An empty caller scope is "nothing was asked", never "the instrument is broken".

    Regression guard: ``" OR ".join(per_file for _ in files)`` yields ``""`` when ``files`` is
    empty, producing ``WHERE is_noise = 0 AND ()`` — a syntax error the handler reported as
    ``INSTRUMENT FAILURE``, whose prose tells the reader to "stop and fix it". There was nothing
    to fix, and ``/review`` runs on every commit, so this was a new hard stop on caller input.

    The discrimination this pins: **instrument broken** (stop) vs **caller asked nothing**
    (continue) are different outcomes and must not share an exit code.
    """
    source = _extract_block_source("review.md", "PRAGMA table_info(findings)", _SCOPE_FILES_EMPTY)
    with tempfile.TemporaryDirectory(prefix="cmd-sql-empty-scope-") as tmp:
        work = pathlib.Path(tmp)
        _build_variant_db(work / "metrics" / "evaluation.db", SCHEMA_VARIANTS[variant])
        script = work / "_block.py"
        script.write_text(source, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, script.name], cwd=work, capture_output=True, text=True, timeout=120
        )
    combined = proc.stdout + proc.stderr
    assert proc.returncode == 0, (
        f"review.md Step 1.5 exited {proc.returncode} on an EMPTY scope list ('{variant}' "
        f"schema). An empty file list is caller input, not a broken instrument.\n{combined}"
    )
    assert "INSTRUMENT FAILURE" not in combined, (
        "review.md Step 1.5 called an empty scope list an INSTRUMENT FAILURE, which tells the "
        f"reader to stop and fix a query that is not broken:\n{combined}"
    )
    assert "empty" in proc.stdout.lower(), (
        f"review.md Step 1.5 must SAY the scope list was empty rather than printing a bare "
        f"'0 matches', which is indistinguishable from 'this file has no history':\n{combined}"
    )


# --------------------------------------------------------------------------------------
# Instrument-completeness guard
# --------------------------------------------------------------------------------------
# The queries were only half the defect. The other half is a repair that *narrows* the
# instrument: reading a column the database can still answer and declining to print it. That
# leaves every query green while the retro quietly reports less than it used to.
#
# An earlier version of this guard was hard-coded to ``v_agent_dashboard``. That scoping is
# precisely what let a repair drop ``agent_count`` from ``retro.md`` 4b — cross-agent
# corroboration, the number that distinguishes a pattern three agents independently saw from
# one agent repeating itself, and the entire premise of a Rule of Three — on the pre-migration
# schema, which is the LIVE schema of the derived project that runs ``/retro`` most. Deleting
# the date range, the category, or ``review.md`` 7a's provenance line were all invisible too.
# So the guard is now keyed off the *view a block renders*, not off one view's name.
#
# The rule: if the view exposes a column in this schema generation, the block prints its value.

#: Seed script per (view, schema generation). Values are chosen so that every column the view
#: derives yields a DISTINCT, unambiguous token — the earlier ``_ROT``-shaped attempt had
#: ``discussion_count == agent_count == 3``, which satisfied a set-membership assertion without
#: the block ever printing the second one.
_INSTRUMENT_SEEDS: dict[str, dict[str, str]] = {
    "v_agent_dashboard": {
        "modern": (
            "INSERT INTO agent_effectiveness (agent, discussion_id, findings_unique, "
            "findings_duplicate, findings_false_positive, confidence_avg, "
            "confidence_calibration, computed_at) VALUES "
            "('qa-specialist', 'DISC-1', 317, 41, 58, 0.734, 0.629, '2026-01-01');"
        ),
        "legacy": (
            "INSERT INTO agent_effectiveness (agent, discussion_id, findings_produced, "
            "findings_unique, findings_survived, findings_dropped, confidence_avg, "
            "confidence_accuracy, computed_at) VALUES "
            "('qa-specialist', 'DISC-1', 1000, 250, 125, 0, 0.611, 0.422, '2026-01-01');"
        ),
    },
    # 5 sightings of one pattern across 5 distinct discussions and 2 distinct agents:
    #   sighting_count / discussion_count -> 5   (never collides with…)
    #   agent_count                       -> 2   (…the legacy-only corroboration number)
    # Dates are exactly 10 characters so a block that prints ``str(value)[:10]`` still prints
    # the whole value, and the years are far enough out that no digit run collides.
    "v_rule_of_three": {
        "modern": "".join(
            "INSERT INTO pattern_sightings (pattern_hash, discussion_id, category, summary, "
            f"source, created_at) VALUES ('rotprobehash77', 'DISC-ROT-{tag}', 'rotcat', "
            f"'rot probe summary', 'review', '{when}');"
            for tag, when in zip(
                "ABCDE",
                ("2091-07-14", "2091-09-03", "2092-01-28", "2092-11-06", "2093-08-19"),
                strict=True,
            )
        ),
        "legacy": "".join(
            "INSERT INTO pattern_sightings (pattern_key, discussion_id, agent, source_type, "
            f"sighted_at) VALUES ('rotprobe:alpha', 'DISC-ROT-{tag}', '{agent}', 'review', "
            f"'{when}');"
            for tag, agent, when in zip(
                "ABCDE",
                (
                    "qa-specialist",
                    "security-specialist",
                    "qa-specialist",
                    "security-specialist",
                    "qa-specialist",
                ),
                ("2091-07-14", "2091-09-03", "2092-01-28", "2092-11-06", "2093-08-19"),
                strict=True,
            )
        ),
    },
}

#: ``(block, view)`` for every block that renders an instrument row FIELD BY FIELD — i.e. every
#: block that is capable of narrowing one. Derived from the view names the block actually reads,
#: so adding a renderer for a new view puts it under the guard automatically.
#: ``meta-review.md`` Step 1 is excluded by the ``get(row,`` test on purpose: it prints whole
#: raw tuples, so it cannot drop a column.
INSTRUMENT_RENDER_BLOCKS: list[tuple[CommandBlock, str]] = [
    (block, view)
    for block in RUNNABLE_BLOCKS
    for view in sorted(_INSTRUMENT_SEEDS)
    if _block_reads(block.source, view) and "get(row," in block.source
]

#: Flattened to ``(block, view, variant)`` so each schema generation is its own test id.
INSTRUMENT_RENDER_CASES = [
    (block, view, variant)
    for block, view in INSTRUMENT_RENDER_BLOCKS
    for variant in sorted(_INSTRUMENT_SEEDS[view])
]

#: A value counts as printed when it appears bounded by non-word characters, so ``5`` matches
#: ``"5 discussions"`` but not the ``5`` inside an identifier or a longer number.
_WORD_CHAR = "[0-9A-Za-z_]"


def _prints_value(stdout: str, value: object) -> bool:
    """True when every comma-separated atom of ``value`` appears in ``stdout`` as a token.

    Splitting on commas is for ``GROUP_CONCAT`` columns (``discussion_ids`` / ``discussions``):
    SQLite does not promise an order for the concatenation, so asserting the joined string
    verbatim would be flaky. Requiring every element makes the check order-independent without
    weakening it — a block that drops the provenance list still fails.
    """
    for atom in str(value).split(","):
        atom = atom.strip()
        if not atom:
            continue
        pattern = f"(?<!{_WORD_CHAR}){re.escape(atom)}(?!{_WORD_CHAR})"
        if not re.search(pattern, stdout):
            return False
    return True


def test_instrument_render_blocks_are_discovered() -> None:
    """Guards the completeness check against passing vacuously."""
    found = sorted(f"{block.file}:{view}" for block, view in INSTRUMENT_RENDER_BLOCKS)
    expected = sorted(
        [
            "meta-review.md:v_agent_dashboard",
            "retro.md:v_agent_dashboard",
            "retro.md:v_rule_of_three",
            "review.md:v_rule_of_three",
        ]
    )
    assert found == expected, (
        f"expected the four field-by-field instrument renderers (retro.md 4b + 4c, "
        f"meta-review.md Step 2, review.md Step 7a), found {found}. If a renderer was removed "
        f"or renamed, the completeness guard just went blind to it."
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    ("block", "view", "variant"),
    INSTRUMENT_RENDER_CASES,
    ids=[f"{b}-{v}-{s}" for b, v, s in INSTRUMENT_RENDER_CASES],
)
def test_instrument_block_prints_every_column_the_view_offers(
    block: CommandBlock, view: str, variant: str
) -> None:
    """A repair may widen an instrument. It may never narrow one.

    Regression guard for two measurement losses found in review, one per view:

    * ``v_agent_dashboard`` — the repaired blocks kept ``uniqueness`` and ``calibration`` but
      dropped ``total_findings`` (raw volume) and ``survival_pct`` (did the finding survive into
      synthesis) on the pre-migration schema.
    * ``v_rule_of_three`` — ``retro.md`` 4b dropped ``agent_count`` on that same schema, which
      is ``agentic_journal``'s live one (measured: its ``v_rule_of_three`` columns are
      ``pattern_key, discussion_count, agent_count, first_seen, last_seen, discussions``).
      Against a read-only copy of that project's real database, "``…untested-phase-silently:
      5 discussions, 1 agents``" had become "``5 discussions``" — the cross-agent corroboration
      number, which is the entire premise of a Rule of Three, silently gone.

    Every query stayed green in both cases, because a dropped *print* is invisible to a SQL
    check. The invariant: for every column the view exposes in this schema generation, the
    block's output contains that column's value.
    """
    with tempfile.TemporaryDirectory(prefix="cmd-sql-complete-") as tmp:
        work = pathlib.Path(tmp)
        db = work / "metrics" / "evaluation.db"
        _build_variant_db(db, SCHEMA_VARIANTS[variant])
        conn = sqlite3.connect(str(db))
        try:
            conn.executescript(_INSTRUMENT_SEEDS[view][variant])
            conn.commit()
            conn.row_factory = sqlite3.Row
            row = conn.execute(f"SELECT * FROM {view}").fetchone()
        finally:
            conn.close()
        assert row is not None, (
            f"the seed for {view}/{variant} produced no row, so this check would pass "
            f"vacuously — fix _INSTRUMENT_SEEDS, not the assertion"
        )
        expected = dict(row)
        script = work / "_block.py"
        script.write_text(block.source, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, script.name], cwd=work, capture_output=True, text=True, timeout=120
        )

    assert proc.returncode == 0, f"{block} exited {proc.returncode}:\n{proc.stdout}{proc.stderr}"

    missing = [
        f"{col}={value!r}"
        for col, value in expected.items()
        if value is not None and not _prints_value(proc.stdout, value)
    ]
    assert not missing, (
        f"{block} on the '{variant}' schema does not print {missing}. {view} can answer those "
        f"columns and this block declines to read them — that is measurement deleted by a fix, "
        f"which this slice exists to prevent. Add a conditional append using the has()/get() "
        f"helpers already in the block.\nExpected: {expected}\nOutput:\n{proc.stdout}"
    )


# --------------------------------------------------------------------------------------
# Anti-swallow guard
# --------------------------------------------------------------------------------------


def _is_failing_exit_call(node: ast.AST) -> bool:
    """True for an exit call that terminates the process **non-zero**.

    ``sys.exit(1)`` / ``sys.exit(2)`` qualify. ``sys.exit()`` and ``sys.exit(0)`` do not — the
    command files' own prose defines exit 0 as "every instrument answered", so exiting zero
    from an error handler reads to the caller as a clean run and is a swallow. A non-literal
    argument (``sys.exit(code)``) also does not qualify: it cannot be proven non-zero here.
    """
    if not isinstance(node, ast.Call):
        return False
    name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
    if name not in {"exit", "_exit"}:
        return False
    if len(node.args) != 1:
        return False  # bare exit() is exit(0)
    arg = node.args[0]
    if isinstance(arg, ast.Constant) and isinstance(arg.value, bool) is False:
        if isinstance(arg.value, int):
            return arg.value != 0
    return False


def _is_failing_raise(node: ast.AST) -> bool:
    """True for a ``raise`` that terminates the process non-zero (or propagates)."""
    if not isinstance(node, ast.Raise):
        return False
    exc = node.exc
    if exc is None:
        return True  # bare `raise` — re-raises the original error
    if isinstance(exc, ast.Call):
        name = getattr(exc.func, "id", None) or getattr(exc.func, "attr", None)
        if name == "SystemExit":
            if not exc.args:
                return False  # SystemExit() == exit code 0
            arg = exc.args[0]
            if isinstance(arg, ast.Constant):
                if arg.value is None:
                    return False
                if isinstance(arg.value, int) and not isinstance(arg.value, bool):
                    return arg.value != 0
            return True  # a message argument means exit code 1
    return True  # any other exception propagates as a traceback


def _drained_accumulators(tree: ast.AST) -> set[str]:
    """Names of failure accumulators the block provably drains into a non-zero exit.

    ``retro.md`` and ``meta-review.md`` deliberately keep reading the remaining instruments
    after one fails: the handler does ``broken.append(label)`` and the block ends with
    ``if broken: … sys.exit(1)``. That IS an escalation — the process still ends non-zero — so
    it satisfies the handler contract. Accepting it requires proving the drain exists, which
    is what this does: a name ``N`` qualifies only when some ``if N:`` statement's body
    performs a failing exit.
    """
    drained: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.If) and isinstance(node.test, ast.Name)):
            continue
        if any(
            _is_failing_exit_call(inner) or _is_failing_raise(inner) for inner in ast.walk(node)
        ):
            drained.add(node.test.id)
    return drained


def _body_escalates(node: ast.AST, drained: set[str], escalating_funcs: set[str]) -> bool:
    """True if ``node``'s subtree makes a failure reach the caller.

    Three shapes count: a failing ``raise``/``exit``, an append to a *drained* accumulator, or
    a call to a helper defined in the same block that itself escalates. That last one matters
    because ``meta-review.md`` factors its classification into ``note_error(label, e, ctx)`` —
    the escalation is one call frame away, and a guard that could not see through it would
    force the command back into copy-pasted handlers to stay green.
    """
    for inner in ast.walk(node):
        if _is_failing_raise(inner) or _is_failing_exit_call(inner):
            return True
        if not isinstance(inner, ast.Call):
            continue
        if (
            getattr(inner.func, "attr", None) == "append"
            and getattr(getattr(inner.func, "value", None), "id", None) in drained
        ):
            return True
        name = getattr(inner.func, "id", None)
        if name is not None and name in escalating_funcs:
            return True
    return False


def _escalating_functions(tree: ast.AST, drained: set[str]) -> set[str]:
    """Names of block-local functions that escalate, resolved to a fixpoint."""
    funcs = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    escalating: set[str] = set()
    changed = True
    while changed:
        changed = False
        for name, fn in funcs.items():
            if name in escalating:
                continue
            if _body_escalates(fn, drained, escalating):
                escalating.add(name)
                changed = True
    return escalating


def _handler_escalates(
    handler: ast.ExceptHandler, drained: set[str], escalating_funcs: set[str]
) -> bool:
    """True if the handler makes the failure reach the caller (see the module docstring)."""
    return _body_escalates(handler, drained, escalating_funcs)


def _handler_swallow_text(handler: ast.ExceptHandler) -> str | None:
    """Return the first printed string in ``handler`` that reads as 'there is just no data'."""
    for node in ast.walk(handler):
        if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "print"):
            continue
        for arg in ast.walk(node):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if _SWALLOW_PHRASES.search(arg.value):
                    return arg.value
            if isinstance(arg, ast.JoinedStr):
                literal = "".join(
                    v.value
                    for v in arg.values
                    if isinstance(v, ast.Constant) and isinstance(v.value, str)
                )
                if _SWALLOW_PHRASES.search(literal):
                    return literal
    return None


def _handler_identity(filename: str, segment: str) -> str:
    """A stable key for ONE handler: file plus a hash of its whitespace-normalised source.

    Keying the registry on the *filename* alone was a hole: ``promote.md`` is listed, so a
    brand-new second swallowing handler added anywhere in ``promote.md`` was absorbed silently
    and the suite stayed green — the exact "allowlist rots into a permanent exemption" failure
    the registry's own docstring claims to prevent. Whitespace is normalised so reindenting is
    not a diff; anything else about the handler (including a comment inside it) changes the key
    and forces a re-decision.
    """
    digest = hashlib.sha256(" ".join(segment.split()).encode("utf-8")).hexdigest()[:12]
    return f"{filename}::{digest}"


def find_swallowing_handlers_in(
    source: str, filename: str, block_line: int, db_block: bool
) -> list[tuple[str, str, int, str]]:
    """Return ``(handler key, file, approx line, evidence)`` for one block's swallowing handlers.

    Factored out of :func:`_find_swallowing_handlers` so the contract itself can be unit-tested
    on synthetic handlers — a guard nobody has ever watched fail is not a guard.
    """
    offenders: list[tuple[str, str, int, str]] = []
    try:
        tree = ast.parse(_PLACEHOLDER.sub("PLACEHOLDER", source))
    except SyntaxError:
        return offenders  # not a Python block (bash, yaml, prose) — the regex guard covers it
    drained = _drained_accumulators(tree)
    escalating_funcs = _escalating_functions(tree, drained)
    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler):
            continue
        segment = ast.get_source_segment(source, node) or ""
        if _SWALLOW_OK_MARKER in segment:
            continue
        if _handler_escalates(node, drained, escalating_funcs):
            continue
        evidence = _handler_swallow_text(node)
        # ``ast.dump`` is the fallback when the source segment cannot be recovered: it still
        # distinguishes two different handlers, which is all the key has to do.
        key = _handler_identity(filename, segment or ast.dump(node))
        if db_block:
            # In a DB block the contract is termination, not wording: a handler that neither
            # escalates nor is marked is an offender whatever it prints — including nothing.
            reason = (
                f"prints {evidence.strip()[:100]!r} and does not escalate"
                if evidence is not None
                else "neither re-raises, exits non-zero, drains into a non-zero exit, nor is "
                "marked instrument-optional — the failure is invisible to the caller"
            )
            offenders.append((key, filename, block_line + (node.lineno or 0), reason))
        elif evidence is not None:
            # Non-DB block: not an instrument read, so keep only the older phrase-based check
            # rather than silently widening this guard onto files outside its repair scope.
            offenders.append(
                (key, filename, block_line + (node.lineno or 0), evidence.strip()[:120])
            )
    return offenders


def _find_swallowing_handlers() -> list[tuple[str, str, int, str]]:
    """Return ``(handler key, file, approx line, evidence)`` for every swallowing handler."""
    offenders: list[tuple[str, str, int, str]] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        for block_line, info, body in _iter_fenced_blocks(text):
            source = body if info == "python" else _unwrap_python_dash_c(body)
            if "except" not in source:
                continue
            offenders.extend(
                find_swallowing_handlers_in(
                    source, path.name, block_line, db_block="sqlite3" in source
                )
            )
    return offenders


@pytest.mark.regression
def test_no_bare_except_in_command_code_blocks() -> None:
    """Bare ``except:`` in a command turns an instrument failure into a silent no-op.

    The crudest form of the defect. ``test_command_blocks_never_swallow_instrument_failures``
    covers the same bug written with a specific exception type.
    """
    offenders: list[str] = []
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        for block_line, _info, body in _iter_fenced_blocks(path.read_text(encoding="utf-8")):
            for offset, line in enumerate(body.splitlines()):
                if re.match(r"^\s*except\s*:", line):
                    offenders.append(f"{path.name}:~{block_line + offset}: {line.strip()}")
    assert not offenders, "bare `except:` swallows instrument failures:\n" + "\n".join(offenders)


@pytest.mark.regression
def test_command_blocks_never_swallow_instrument_failures() -> None:
    """An ``except`` handler must never let an instrument failure reach the caller as success.

    This is the *semantic* form of the guard. ``except sqlite3.Error: print('… not
    available')`` is the identical defect to a bare ``except:`` — it teaches the reader that
    missing data is normal, which is exactly how three broken queries survived for months. A
    regex looking for ``except:`` cannot see it.

    **The contract is termination, not wording.** Inside a DB-touching block, a handler is an
    offender unless it re-raises, exits with a non-zero integer *literal*, appends to an
    accumulator the block provably drains into a non-zero exit, or carries an explicit
    ``# instrument-optional: <reason>`` comment. It does not matter what it prints:

    * ``except sqlite3.Error: rows = []`` — prints nothing, so the block falls through to its
      ``else:`` and reports "readable and empty". Strictly worse than "(not available)",
      because now there is no error text anywhere. **Offender.**
    * ``except sqlite3.Error: print('… skipping'); sys.exit(0)`` — the command prose defines
      exit 0 as "every instrument answered", so this reads as a clean run. **Offender.**

    :data:`_SWALLOW_PHRASES` is now only evidence text quoted in the failure message, plus the
    weaker trigger for handlers in blocks that never touch sqlite3.

    The assertion is an EXACT match against :data:`KNOWN_UNFIXED_SWALLOWS`, which is keyed
    **per handler** (``<file>::<hash of the normalised handler source>``), so it fails in both
    directions: a NEW swallow fails *even in a file that is already listed*, and repairing a
    listed one also fails until the entry is removed. Keying by filename alone used to let a
    second, independent swallow slip into ``promote.md`` unnoticed — an allowlist that silently
    absorbs new defects is how the original bug became invisible.
    """
    offenders = _find_swallowing_handlers()
    offending_keys = {key for key, _name, _line, _evidence in offenders}

    new = sorted(offending_keys - KNOWN_UNFIXED_SWALLOWS)
    assert not new, (
        "these command handlers swallow an instrument failure as 'no data available':\n"
        + "\n".join(
            f"  {name}:~{line}  [{key}]: {evidence!r}"
            for key, name, line, evidence in offenders
            if key in set(new)
        )
        + "\n\nName the error and fail loudly, degrade explicitly (exit 2), or — only for a "
        "genuinely optional path — add `# instrument-optional: <reason>` inside the handler. "
        "If a handler is deliberately left unfixed (outside this change's file scope), add its "
        "key above to KNOWN_UNFIXED_SWALLOWS with a comment naming the follow-on work."
    )

    fixed = sorted(KNOWN_UNFIXED_SWALLOWS - offending_keys)
    assert not fixed, (
        f"{fixed} no longer swallow instrument failures (or the handler was edited, which "
        f"changes its key) — update KNOWN_UNFIXED_SWALLOWS so the registry cannot rot into a "
        f"permanent exemption."
    )


# --------------------------------------------------------------------------------------
# The guard's own regression suite
# --------------------------------------------------------------------------------------
# `test_command_blocks_never_swallow_instrument_failures` is only worth its runtime if it can
# actually go red. These cases pin the exact mutants that an earlier, phrase-based version of
# the guard waved through, so the hole cannot silently reopen.

_HANDLER_PROLOGUE = "import sqlite3, sys\nconn = sqlite3.connect('x.db')\n"

#: ``(id, handler body, is_offender)`` — the body is spliced into a try/except in a DB block.
_HANDLER_CASES = [
    # --- must be caught -----------------------------------------------------------------
    ("silent_no_print", "    rows = []", True),
    ("silent_pass", "    pass", True),
    ("print_only", "    print('(v_rule_of_three not available)')", True),
    ("exit_zero_with_message", "    print('… skipping')\n    sys.exit(0)", True),
    ("bare_exit", "    sys.exit()", True),
    ("raise_systemexit_zero", "    raise SystemExit(0)", True),
    ("raise_systemexit_empty", "    raise SystemExit()", True),
    ("exit_non_literal", "    code = 0\n    sys.exit(code)", True),
    ("append_to_undrained_list", "    broken.append('x')", True),
    # --- must be accepted ---------------------------------------------------------------
    ("exit_one", "    print('INSTRUMENT FAILURE')\n    sys.exit(1)", False),
    ("exit_two", "    print('SCHEMA SKEW')\n    sys.exit(2)", False),
    ("bare_raise", "    raise", False),
    ("raise_systemexit_message", "    raise SystemExit('INSTRUMENT FAILURE: ' + str(e))", False),
    (
        "marked_optional",
        "    # instrument-optional: telemetry is genuinely opt-in\n    pass",
        False,
    ),
]


@pytest.mark.regression
@pytest.mark.parametrize(
    ("case_id", "body", "is_offender"),
    _HANDLER_CASES,
    ids=[case[0] for case in _HANDLER_CASES],
)
def test_handler_contract_classifies_each_form(case_id: str, body: str, is_offender: bool) -> None:
    """The handler contract must go red on every known swallow shape, not just phrased ones.

    ``exit_zero_with_message`` and ``silent_no_print`` are the two mutants that survived the
    earlier phrase-based guard: one exits 0 (which the command prose defines as "every
    instrument answered"), the other prints nothing at all so the block reports "readable and
    empty" with no error text anywhere.
    """
    source = (
        _HANDLER_PROLOGUE
        + "try:\n    rows = conn.execute('SELECT 1').fetchall()\n"
        + f"except sqlite3.Error as e:\n{body}\n"
    )
    offenders = find_swallowing_handlers_in(source, "synthetic.md", 0, db_block=True)
    assert bool(offenders) is is_offender, (
        f"handler case {case_id!r} should {'FAIL' if is_offender else 'PASS'} the contract; "
        f"guard returned {offenders}\n--- source ---\n{source}"
    )


@pytest.mark.regression
def test_handler_contract_accepts_a_drained_accumulator() -> None:
    """The 'collect failures, then exit non-zero at the end' pattern is a real escalation.

    ``retro.md`` and ``meta-review.md`` use it so one dead instrument does not blind the rest
    of the run. It is accepted only because the drain is *proved*: some ``if broken:`` must
    perform a failing exit. The companion case above (``append_to_undrained_list``) shows the
    append alone is not enough.
    """
    source = (
        _HANDLER_PROLOGUE + "broken = []\n"
        "try:\n    rows = conn.execute('SELECT 1').fetchall()\n"
        "except sqlite3.Error as e:\n    print('INSTRUMENT FAILURE: ' + str(e))\n"
        "    broken.append('thing')\n"
        "if broken:\n    print('BROKEN INSTRUMENTS')\n    sys.exit(1)\n"
    )
    assert find_swallowing_handlers_in(source, "synthetic.md", 0, db_block=True) == []

    # …and the same block whose drain exits ZERO is not a drain at all.
    zero_drain = source.replace("sys.exit(1)", "sys.exit(0)")
    assert find_swallowing_handlers_in(zero_drain, "synthetic.md", 0, db_block=True), (
        "an accumulator drained into sys.exit(0) still reports success to the caller and must "
        "not satisfy the handler contract"
    )


@pytest.mark.regression
def test_handler_contract_follows_delegation_one_frame() -> None:
    """Delegating classification to a helper is fine — delegating it to a no-op is not.

    ``meta-review.md`` routes both of its handlers through ``note_error``, which appends to a
    drained accumulator. The guard must see through that call, and must NOT bless a call to a
    helper that merely prints.
    """
    escalating = (
        _HANDLER_PROLOGUE + "broken = []\n"
        "def note_error(label, e):\n    print('INSTRUMENT FAILURE ' + str(e))\n"
        "    broken.append(label)\n"
        "try:\n    rows = conn.execute('SELECT 1').fetchall()\n"
        "except sqlite3.Error as e:\n    note_error('thing', e)\n"
        "if broken:\n    sys.exit(1)\n"
    )
    assert find_swallowing_handlers_in(escalating, "synthetic.md", 0, db_block=True) == []

    inert = escalating.replace("    broken.append(label)\n", "")
    assert find_swallowing_handlers_in(inert, "synthetic.md", 0, db_block=True), (
        "a handler that delegates to a helper which only prints has not escalated anything"
    )


@pytest.mark.regression
def test_known_unfixed_swallows_is_keyed_per_handler_not_per_file() -> None:
    """A NEW swallow in an already-registered file must not be absorbed by the registry.

    The registry used to be keyed on the FILENAME, so ``"promote.md"`` in
    :data:`KNOWN_UNFIXED_SWALLOWS` exempted every present and future swallowing handler in
    ``promote.md`` — a second, independent one could be added and the suite stayed green while
    the docstring claimed "a NEW swallow fails". This pins the per-handler identity that closes
    it: two different handlers in one file yield two different keys, so only the registered one
    is exempt.
    """
    one = (
        _HANDLER_PROLOGUE + "try:\n    rows = conn.execute('SELECT 1').fetchall()\n"
        "except sqlite3.Error:\n    print('promotion_candidates table not available')\n"
    )
    two = one + (
        "try:\n    extra = conn.execute('SELECT 2').fetchone()\n"
        "except sqlite3.Error:\n    print('brand new second swallow - skipping')\n"
    )
    keys_one = {k for k, *_ in find_swallowing_handlers_in(one, "promote.md", 0, db_block=True)}
    keys_two = {k for k, *_ in find_swallowing_handlers_in(two, "promote.md", 0, db_block=True)}

    assert len(keys_one) == 1, f"expected one handler key, got {keys_one}"
    assert len(keys_two) == 2, f"expected two distinct handler keys, got {keys_two}"
    assert keys_one < keys_two, "the original handler's key must be stable when another is added"

    # The registry-difference the real test performs: with only the FIRST handler registered,
    # the second one is still reported as new.
    registered = keys_one
    assert sorted(keys_two - registered), (
        "a second swallowing handler in an already-registered file must surface as NEW; if this "
        "is empty the registry has gone back to absorbing new defects"
    )

    # …and a pure REINDENT of the same handler must NOT look like a new one, or every
    # cosmetic edit would demand a registry update and the registry would be abandoned.
    reindented = (
        _HANDLER_PROLOGUE + "if True:\n"
        "    try:\n        rows = conn.execute('SELECT 1').fetchall()\n"
        "    except sqlite3.Error:\n        print('promotion_candidates table not available')\n"
    )
    keys_reindent = {
        k for k, *_ in find_swallowing_handlers_in(reindented, "promote.md", 0, db_block=True)
    }
    assert keys_reindent == keys_one, (
        f"reindenting a handler changed its registry key ({keys_reindent} != {keys_one}); the "
        f"key must normalise whitespace or every formatting pass invalidates the registry"
    )


@pytest.mark.regression
@pytest.mark.parametrize(
    "broken_fragment",
    [
        # Hub-schema breakages: these columns do not exist in the current hub schema.
        "v_agent_dashboard ORDER BY total_findings",
        "v_rule_of_three ORDER BY discussion_count",
        "FROM promotion_candidates GROUP BY status",
        # Fixed positional unpacks / name-pinned access that break on the other generation.
        'row["pattern_key"]',
        'row[\\"pattern_key\\"]',
        'row["sighting_count"]',
        'row[\\"sighting_count\\"]',
    ],
)
def test_known_broken_column_references_stay_gone(broken_fragment: str) -> None:
    """Text-level guard so the known-bad references cannot return without a DB present."""
    offenders = [
        path.name
        for path in sorted(COMMANDS_DIR.glob("*.md"))
        if broken_fragment in path.read_text(encoding="utf-8")
    ]
    assert not offenders, (
        f"{broken_fragment!r} reappeared in {offenders} — it is wrong in at least one schema "
        f"generation (see tests/test_command_sql.py module docstring)"
    )
