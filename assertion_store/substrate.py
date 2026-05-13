"""SQLite substrate for the sourced-assertion memory layer.

Scope:
    - Defines the schema for sourced assertions, entity authority refs,
      and assertion vectors.
    - Provides a single ``init(db_path)`` entry point that loads the
      sqlite-vec extension and creates schema idempotently.
    - Resolves the current project_id from pyproject.toml so every
      assertion is tagged with which project produced it.
    - Exposes the substrate's three primitives (``assert_fact``,
      ``search_semantic``, ``get_source``) as methods on a ``Substrate``
      class — transports (MCP, CLI, HTTP) construct an instance with their
      own config and call methods. The substrate is transport-agnostic.

Design notes:
    - One file on disk = the entire substrate. This is the portability
      commitment from the Phase 3 decision brief.
    - The schema is graph-shaped (entities + relationships) but stored
      relationally. Migration to a real graph DB later is a schema
      conversion, not a rewrite of the substrate API.
    - ``project_id`` is on every assertion as the design-for-future slot
      for the cross-project shared-knowledge layer (Phase 4 mod #1).
    - ``source_ref`` is stored as a portable URI of the form
      ``project://<project_id>/<relative_path>#L<start>-L<end>`` (Phase 4
      mod #2). The schema accepts any TEXT; ``assert_fact`` enforces the
      URI shape and the get_source containment check enforces source-root
      allow-listing.
"""

from __future__ import annotations

import re
import sqlite3
import threading
import tomllib
from pathlib import Path

import sqlite_vec

from assertion_store.embeddings import embed

EMBEDDING_DIM = 384  # all-MiniLM-L6-v2 default

# Rhetorical postures recognised by assert_fact. Open-vocabulary framing was
# considered and rejected: the schema is queryable, and silent acceptance of
# garbage framings would corrupt downstream filters. Tighten now, expand
# deliberately later if the vocabulary needs to grow.
_VALID_FRAMINGS = frozenset({"asserts", "questions", "denies", "considers"})

# Parses both with-range (project://id/path#L4-L9) and without-range
# (project://id/path) URI forms. The line-range fragment is optional;
# without it, get_source returns the full file.
_URI_RE = re.compile(
    r"^project://(?P<project_id>[^/]+)/(?P<relpath>.+?)(?:#L(?P<start>\d+)-L(?P<end>\d+))?$"
)


def resolve_project_id(project_root: Path | None = None) -> str:
    """Return the current project_id read from pyproject.toml.

    Args:
        project_root: Directory containing ``pyproject.toml``. Defaults to
            the current working directory.

    Returns:
        The ``[project].name`` string from pyproject.toml.

    Raises:
        FileNotFoundError: If pyproject.toml is not found at the given root.
        KeyError: If pyproject.toml has no ``[project].name`` field.
    """
    root = project_root or Path.cwd()
    pyproject_path = root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(
            f"pyproject.toml not found at {pyproject_path}; "
            "cannot resolve project_id for assertion tagging."
        )
    with pyproject_path.open("rb") as fh:
        data = tomllib.load(fh)
    try:
        return data["project"]["name"]
    except KeyError as exc:
        raise KeyError(
            f"pyproject.toml at {pyproject_path} has no [project].name; "
            "set it to enable assertion tagging."
        ) from exc


def init(db_path: str | Path) -> sqlite3.Connection:
    """Open (or create) the memory substrate database and ensure schema exists.

    Args:
        db_path: Filesystem path to the SQLite file. Created if absent.

    Returns:
        A sqlite3.Connection with sqlite-vec loaded and schema applied.
        Caller is responsible for closing it.

    Notes:
        - ``enable_load_extension(True)`` is required before loading sqlite-vec.
        - All DDL is idempotent (IF NOT EXISTS), so init() is safe to call
          repeatedly across processes and threads.
        - The vector dimension is fixed at module load time
          (``EMBEDDING_DIM``); switching embedding models requires a schema
          migration, not just a config change.
    """
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)

    conn.executescript(f"""
        -- Sourced assertions: the atomic unit of extracted meaning.
        -- The source asserts (subject, predicate, object); we record
        -- that the source asserts it. Conflicting assertions coexist —
        -- conclusions are derived views over assertions.
        CREATE TABLE IF NOT EXISTS assertions (
            id                  INTEGER PRIMARY KEY,
            project_id          TEXT    NOT NULL,           -- which project produced this
            subject             TEXT    NOT NULL,
            predicate           TEXT    NOT NULL,
            object              TEXT    NOT NULL,
            source_ref          TEXT    NOT NULL,           -- project://<id>/<path>#L<a>-L<b>
            framing             TEXT    DEFAULT 'asserts',  -- asserts|questions|denies|considers
            valid_from          TEXT,                       -- ISO8601, optional valid-time start
            valid_to            TEXT,                       -- ISO8601, optional valid-time end
            recorded_at         TEXT    DEFAULT CURRENT_TIMESTAMP,
            extraction_run_id   TEXT                        -- which extraction pass produced this
        );

        -- External authority refs per entity. Designed in from day one
        -- per the architectural commitment to authority cross-validation.
        -- project_id present so two projects can resolve the same name to
        -- different external entities without collision.
        CREATE TABLE IF NOT EXISTS entity_authorities (
            project_id  TEXT    NOT NULL,
            entity_name TEXT    NOT NULL,
            authority   TEXT    NOT NULL,                   -- 'wikidata' | 'viaf' | 'geonames' | ...
            ref         TEXT    NOT NULL,                   -- 'Q42' or full URI
            PRIMARY KEY (project_id, entity_name, authority)
        );

        -- Vector index for semantic search over assertions. Filtering by
        -- project_id happens at the JOIN in search_semantic, not here, so
        -- this table stays embedding-only.
        CREATE VIRTUAL TABLE IF NOT EXISTS assertion_vecs USING vec0(
            assertion_id INTEGER PRIMARY KEY,
            embedding    FLOAT[{EMBEDDING_DIM}]
        );

        -- Lookup index for source-based reads (Suchness preservation
        -- primitive: get_source needs to be fast).
        CREATE INDEX IF NOT EXISTS idx_assertions_source
            ON assertions(source_ref);

        -- Filter index: search_semantic always filters by project_id by
        -- default, so this index keeps that path cheap as the corpus grows.
        CREATE INDEX IF NOT EXISTS idx_assertions_project
            ON assertions(project_id);
    """)
    conn.commit()
    return conn


class Substrate:
    """Sourced-assertion memory substrate, transport-agnostic.

    Owns the data model (sourced-assertion schema, source_ref URI format),
    connection lifecycle (thread-local SQLite under transport thread models),
    and the three primitives: ``assert_fact`` (write), ``search_semantic``
    (vector read), ``get_source`` (Suchness preservation).

    Transports (MCP server, CLI scripts, HTTP API, batch ingest jobs)
    construct an instance with their own config and call the methods. Each
    instance manages its own thread-local connection cache — multiple
    Substrate instances can coexist in one process (e.g., framework substrate
    + Insight Journal substrate, each with their own DB and policy).

    Args:
        db_path: SQLite filesystem path. Created if absent.
        project_id: Identifier tagged on every assertion this substrate
            writes. Used to filter cross-project URIs at write/read time.
        source_roots: Resolved absolute paths under which ``get_source`` will
            accept references. Anything outside these roots is rejected —
            the substrate's Suchness primitive must not be a filesystem
            escape. The conventional set for a framework project is
            ``[sources, discussions, docs, memory, src]`` under the repo
            root, but each derived project may differ.
    """

    def __init__(
        self,
        db_path: Path,
        project_id: str,
        source_roots: list[Path],
    ) -> None:
        self.db_path = Path(db_path)
        self.project_id = project_id
        self.source_roots = [Path(r).resolve() for r in source_roots]
        # FastMCP and similar transports dispatch tool calls on worker
        # threads distinct from the import thread; sqlite3 forbids
        # cross-thread connection reuse. Per-instance thread-local cache
        # means multiple Substrate instances in the same process do not
        # share connections either.
        self._thread_local = threading.local()

    @classmethod
    def for_project_root(
        cls,
        project_root: Path,
        project_id: str | None = None,
    ) -> Substrate:
        """Construct a Substrate using the framework's conventional layout.

        Convenience for the common case: ``data/memory.db`` under the project
        root and the five conventional source-bearing directories
        (``sources/``, ``discussions/``, ``docs/``, ``memory/``, ``src/``).

        Args:
            project_root: Path containing pyproject.toml.
            project_id: Override the project_id (defaults to reading it from
                pyproject.toml).

        Returns:
            A configured Substrate instance.
        """
        project_root = Path(project_root).resolve()
        return cls(
            db_path=project_root / "data" / "memory.db",
            project_id=project_id or resolve_project_id(project_root),
            source_roots=[
                (project_root / d).resolve()
                for d in ("sources", "discussions", "docs", "memory", "src")
            ],
        )

    def _get_conn(self) -> sqlite3.Connection:
        """Return the current thread's SQLite connection, opening it lazily.

        ``init()`` is idempotent so concurrent threads do not corrupt each
        other's view of the schema.
        """
        conn = getattr(self._thread_local, "conn", None)
        if conn is None:
            conn = init(self.db_path)
            self._thread_local.conn = conn
        return conn

    def _build_source_uri(self, source_ref: str) -> str:
        """Canonicalise a caller-supplied source reference into the portable URI form.

        Accepts either the bare path-with-fragment form (``sources/foo.md#L4-L9``)
        or the already-canonical URI (``project://<id>/sources/foo.md#L4-L9``).
        Always returns a canonical URI tagged with this Substrate's project_id —
        caller-supplied project_id values are stripped and replaced, preventing
        cross-project URI smuggling.

        Rejects paths containing ``..`` to prevent traversal patterns from being
        smuggled into stored assertions (defense-in-depth alongside the
        ``get_source`` containment check).

        Raises:
            ValueError: If a project:// URI is malformed, or if the bare or
                re-extracted relpath contains ``..`` traversal sequences.
        """
        if source_ref.startswith("project://"):
            m = _URI_RE.match(source_ref)
            if not m:
                raise ValueError(f"Malformed project:// URI: {source_ref!r}")
            relpath = m["relpath"]
            fragment = f"#L{m['start']}-L{m['end']}" if m["start"] else ""
            source_ref = f"{relpath}{fragment}"
        if ".." in source_ref:
            raise ValueError(f"Path traversal rejected in source_ref: {source_ref!r}")
        return f"project://{self.project_id}/{source_ref}"

    def assert_fact(
        self,
        subject: str,
        predicate: str,
        object: str,
        source_ref: str,
        framing: str = "asserts",
    ) -> dict:
        """Record a sourced assertion. The source asserts X.

        The verb form is deliberate: the source asserts something; the substrate
        records that the source asserts it. This preserves the distinction
        between primary-source authority and downstream interpretation.

        Args:
            subject: The entity the source is asserting about (e.g. "Andrew Howie").
            predicate: The relationship (e.g. "born_in").
            object: The value or related entity (e.g. "1735").
            source_ref: Either a bare ``path#Lstart-Lend`` reference or an
                already-canonical ``project://...`` URI. Bare refs are tagged
                with this substrate's project_id automatically.
            framing: Rhetorical posture — one of ``asserts``, ``questions``,
                ``denies``, ``considers``. Defaults to ``asserts``.

        Returns:
            A dict with the inserted ``fact_id`` and the canonical ``source_ref``
            URI (echoed back for caller confirmation).

        Raises:
            ValueError: If ``subject``, ``predicate``, or ``object`` is empty or
                whitespace-only, or if ``framing`` is not one of the four
                recognised values. Validation runs before any DB write so invalid
                input never reaches storage.
        """
        if not subject.strip():
            raise ValueError("subject must be a non-empty string")
        if not predicate.strip():
            raise ValueError("predicate must be a non-empty string")
        if not object.strip():
            raise ValueError("object must be a non-empty string")
        if framing not in _VALID_FRAMINGS:
            raise ValueError(f"framing must be one of {sorted(_VALID_FRAMINGS)}, got {framing!r}")
        canonical_ref = self._build_source_uri(source_ref)
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT INTO assertions(project_id, subject, predicate, object, source_ref, framing)"
            " VALUES (?, ?, ?, ?, ?, ?) RETURNING id",
            (self.project_id, subject, predicate, object, canonical_ref, framing),
        )
        fact_id = cur.fetchone()[0]

        vec = embed(f"{subject} {predicate} {object}")
        conn.execute(
            "INSERT INTO assertion_vecs(assertion_id, embedding) VALUES (?, ?)",
            (fact_id, vec.tobytes()),
        )
        conn.commit()
        return {
            "fact_id": fact_id,
            "source_ref": canonical_ref,
            "project_id": self.project_id,
        }

    def search_semantic(
        self,
        query: str,
        k: int = 5,
        scope: str = "local",
    ) -> list[dict]:
        """Vector-similarity search over recorded assertions.

        Returns up to ``k`` assertions ranked by semantic distance to ``query``.
        Each result includes the assertion's full content AND its ``source_ref``
        URI — callers should follow up with ``get_source()`` when validating an
        assertion against the original passage.

        Args:
            query: Natural-language query (e.g. "Howie's family origins").
            k: How many top results to return. Defaults to 5.
            scope: ``"local"`` filters to this substrate's project_id. Future
                values (``"shared"`` or a list of project_ids) are accepted in
                the signature but not yet implemented.

        Returns:
            A list of dicts, each containing ``fact_id``, ``subject``,
            ``predicate``, ``object``, ``source_ref``, ``framing``, and
            ``distance`` (lower is closer).

        Raises:
            NotImplementedError: If ``scope`` is anything other than ``"local"``.
        """
        if scope != "local":
            raise NotImplementedError(
                f"scope={scope!r} not implemented yet. "
                "Only 'local' (current project) is supported in this round."
            )

        query_vec = embed(query)
        conn = self._get_conn()
        rows = conn.execute(
            """
            SELECT a.id, a.subject, a.predicate, a.object, a.source_ref,
                   a.framing, v.distance
              FROM assertion_vecs v
              JOIN assertions a ON a.id = v.assertion_id
             WHERE v.embedding MATCH ?
               AND k = ?
               AND a.project_id = ?
             ORDER BY v.distance
            """,
            (query_vec.tobytes(), k, self.project_id),
        ).fetchall()
        return [
            {
                "fact_id": r[0],
                "subject": r[1],
                "predicate": r[2],
                "object": r[3],
                "source_ref": r[4],
                "framing": r[5],
                "distance": r[6],
            }
            for r in rows
        ]

    def get_source(self, source_ref: str) -> dict:
        """Suchness preservation primitive: pull the original source passage back.

        This method exists so the user (or the agent) can always *challenge* the
        symbolic version of an assertion, not just view it. It is a first-class
        action by architectural commitment — symbols are lossy, this is the path
        back to canonical truth.

        Args:
            source_ref: A canonical URI of the form
                ``project://<project_id>/<relative_path>#L<start>-L<end>``. The
                line range is optional; without it, the full file is returned.

        Returns:
            A dict with the parsed ``source_ref``, ``project_id``,
            ``relative_path``, ``passage`` (the requested text), and either
            ``start_line``/``end_line`` (when a range was given) or
            ``full_file=True`` (when the whole file was returned). On error,
            returns a dict with an ``error`` key explaining what went wrong.
        """
        match = _URI_RE.match(source_ref)
        if not match:
            return {
                "error": (
                    "source_ref must be of the form "
                    "project://<project_id>/<relative_path>[#L<start>-L<end>]"
                ),
                "source_ref": source_ref,
            }

        project_id = match["project_id"]
        relpath = match["relpath"]
        start = match["start"]
        end = match["end"]

        if project_id != self.project_id:
            return {
                "error": (
                    f"cross-project resolution not implemented (asked for "
                    f"{project_id!r}, substrate is {self.project_id!r}). "
                    "Will be enabled when the shared layer lands."
                ),
                "source_ref": source_ref,
            }

        # Containment check: resolved path must be under an allowed source root.
        # Anchored to source_roots (substrate-config), so traversal via .. or
        # absolute paths cannot escape into .env, .git/, .ssh/, or anywhere
        # else on the host filesystem.
        if not self.source_roots:
            return {
                "error": "no source roots configured; substrate cannot resolve any path",
                "source_ref": source_ref,
            }
        # Anchor relative paths against the first source root's parent
        # (the project root); absolute paths in the URI resolve as-is.
        anchor = self.source_roots[0].parent
        abs_path = (anchor / relpath).resolve()
        if not any(abs_path.is_relative_to(root) for root in self.source_roots):
            return {
                "error": "source_ref does not resolve to an allowed source root",
                "source_ref": source_ref,
                "allowed_roots": [str(r) for r in self.source_roots],
            }

        if not abs_path.exists():
            return {"error": f"source file not found: {relpath}", "source_ref": source_ref}

        text = abs_path.read_text(encoding="utf-8")

        if start is None or end is None:
            return {
                "source_ref": source_ref,
                "project_id": project_id,
                "relative_path": relpath,
                "passage": text,
                "full_file": True,
            }

        lines = text.splitlines()
        start_i = int(start)
        end_i = int(end)
        # 1-indexed inclusive on both ends.
        passage = "\n".join(lines[start_i - 1 : end_i])
        return {
            "source_ref": source_ref,
            "project_id": project_id,
            "relative_path": relpath,
            "passage": passage,
            "start_line": start_i,
            "end_line": end_i,
        }
