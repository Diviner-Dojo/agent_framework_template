"""Tests for mcp_server.server — security-critical paths.

Regression scope: the path-traversal vulnerability and the _build_source_uri
bypass identified in REV-20260512-132622 (Findings 1 and 2). This file covers
those two findings only — the broader 8-test set (Finding 4 from the same
review) lands in a follow-up commit.
"""

from __future__ import annotations

import pytest

from mcp_server.server import (
    PROJECT_ID,
    SOURCE_ROOTS,
    get_source,
    substrate,
)

# After step 4 refactor, _build_source_uri lives as a method on the Substrate
# instance. Bind a module-level alias so the existing test call sites work
# without rewriting each one; the bound method carries `self` automatically.
_build_source_uri = substrate._build_source_uri


class TestBuildSourceUriCanonicalisation:
    """_build_source_uri must always tag with the current PROJECT_ID."""

    def test_bare_path_canonicalises_with_current_project(self):
        result = _build_source_uri("sources/foo.md#L1-L5")
        assert result == f"project://{PROJECT_ID}/sources/foo.md#L1-L5"

    def test_bare_path_without_fragment_canonicalises(self):
        result = _build_source_uri("sources/foo.md")
        assert result == f"project://{PROJECT_ID}/sources/foo.md"

    def test_foreign_project_uri_re_canonicalised(self):
        """Regression for Finding 2 (security-specialist, REV-20260512-132622).

        Prior implementation returned any URI starting with project:// unchanged,
        allowing assertions to be stored with foreign project_ids and corrupting
        project-boundary integrity.
        """
        result = _build_source_uri("project://other-project/sources/foo.md#L1-L5")
        assert result == f"project://{PROJECT_ID}/sources/foo.md#L1-L5"

    def test_malformed_project_uri_raises(self):
        with pytest.raises(ValueError, match="Malformed"):
            _build_source_uri("project://not-a-valid-uri")


class TestBuildSourceUriTraversalRejection:
    """_build_source_uri must reject .. patterns at write time."""

    def test_traversal_in_bare_ref_raises(self):
        """Regression for Finding 2 (security-specialist, REV-20260512-132622).

        Prior implementation passed .. through the bare-path branch without
        validation, smuggling traversal sequences into stored assertions that
        would later be exploited via get_source.
        """
        with pytest.raises(ValueError, match="traversal"):
            _build_source_uri("../../etc/passwd")

    def test_traversal_in_foreign_uri_rejected_after_recanonicalisation(self):
        """Traversal must be caught after stripping the foreign project_id."""
        with pytest.raises(ValueError, match="traversal"):
            _build_source_uri("project://other-project/../../etc/passwd")


class TestGetSourcePathTraversal:
    """get_source must enforce containment under SOURCE_ROOTS.

    Regression for Finding 1 (CRITICAL, qa + architecture-consultant +
    security-specialist convergence, REV-20260512-132622). Prior implementation
    used Path(relpath).read_text() without containment, allowing any caller to
    read arbitrary files (e.g., .env, .ssh/id_rsa, /etc/passwd) by crafting a
    source_ref URI with .. traversal.
    """

    def test_traversal_via_dotdot_rejected(self):
        result = get_source(f"project://{PROJECT_ID}/../../etc/passwd")
        assert "error" in result
        assert "allowed source root" in result["error"]

    def test_path_outside_source_roots_rejected(self):
        """data/ is inside the project but NOT in SOURCE_ROOTS.

        The substrate DB (data/memory.db) is not a citable source — readers
        should query via the substrate's tools, not read the raw file.
        """
        result = get_source(f"project://{PROJECT_ID}/data/memory.db")
        assert "error" in result
        assert "allowed source root" in result["error"]

    def test_dotfile_outside_source_roots_rejected(self):
        """Configuration secrets (.env, .git/config, .claude/settings.local.json)
        must not be readable through this tool even though they live under the
        project root.
        """
        result = get_source(f"project://{PROJECT_ID}/.env")
        assert "error" in result
        assert "allowed source root" in result["error"]


class TestGetSourceHappyPath:
    """Allowed paths must still work — verify the fix did not break the canonical
    test fixture or the contract."""

    def test_canonical_test_fixture_under_sources_resolves(self):
        """The fixture from the canonical MCP test (Phase 4) lives under sources/.

        This test asserts that get_source either succeeds (passage present) or
        returns a 'not found' error — never a containment rejection.
        """
        result = get_source(f"project://{PROJECT_ID}/sources/2026-05-12_discussion.md#L156-L156")
        # The fixture may or may not exist in the test environment; what must
        # NOT happen is a containment rejection for a path that is legitimately
        # under SOURCE_ROOTS.
        if "error" in result:
            assert "not found" in result["error"], (
                f"sources/ path was rejected as outside allowed roots — "
                f"containment check is too strict. Error: {result['error']}"
            )
        else:
            assert result["start_line"] == 156
            assert result["end_line"] == 156
            assert "passage" in result

    def test_source_roots_resolve_under_server_dir(self):
        """Sanity check: every configured SOURCE_ROOT resolves to a path under
        the script-anchored project root, regardless of where pytest is invoked
        from.
        """
        from mcp_server.server import _SERVER_DIR

        for root in SOURCE_ROOTS:
            # is_relative_to allows root == _SERVER_DIR (no escape)
            assert root.is_relative_to(_SERVER_DIR), (
                f"SOURCE_ROOT {root} is not under _SERVER_DIR {_SERVER_DIR}"
            )


class TestGetSourceErrorPaths:
    """Other get_source error returns that callers should be able to rely on."""

    def test_invalid_uri_returns_error_dict(self):
        result = get_source("not-a-valid-uri")
        assert "error" in result
        assert "project://" in result["error"]

    def test_cross_project_uri_returns_error_dict(self):
        result = get_source("project://some-other-project/sources/foo.md#L1-L5")
        assert "error" in result
        assert "cross-project" in result["error"]

    def test_file_not_found_under_allowed_root_returns_error_dict(self):
        """A path inside SOURCE_ROOTS but pointing to a nonexistent file must
        return a 'not found' error, not a containment rejection."""
        result = get_source(f"project://{PROJECT_ID}/sources/this-does-not-exist-xyz.md#L1-L5")
        assert "error" in result
        assert "not found" in result["error"]


class TestSearchSemanticScopeRejection:
    """Phase 4 contract: scope parameter accepts only 'local' in this round."""

    def test_shared_scope_raises_not_implemented(self):
        from mcp_server.server import search_semantic

        with pytest.raises(NotImplementedError, match="scope='shared'"):
            search_semantic(query="anything", scope="shared")

    def test_list_scope_raises_not_implemented(self):
        from mcp_server.server import search_semantic

        with pytest.raises(NotImplementedError):
            search_semantic(query="anything", scope="other-project")


class TestAssertFactInputValidation:
    """Regression for Finding 6 (REV-20260512-132622, qa + security).

    assert_fact previously accepted any framing string (including garbage like
    'hallucinated') and empty subject/predicate/object — both flagged by qa and
    security as data-integrity gaps. Validation must run before any DB write.
    """

    def test_invalid_framing_raises(self):
        from mcp_server.server import assert_fact

        with pytest.raises(ValueError, match="framing must be one of"):
            assert_fact(
                subject="x",
                predicate="y",
                object="z",
                source_ref="sources/foo.md#L1-L5",
                framing="hallucinated",
            )

    def test_empty_subject_raises(self):
        from mcp_server.server import assert_fact

        with pytest.raises(ValueError, match="subject must be a non-empty string"):
            assert_fact(
                subject="",
                predicate="y",
                object="z",
                source_ref="sources/foo.md#L1-L5",
            )

    def test_whitespace_subject_raises(self):
        from mcp_server.server import assert_fact

        with pytest.raises(ValueError, match="subject must be a non-empty string"):
            assert_fact(
                subject="   ",
                predicate="y",
                object="z",
                source_ref="sources/foo.md#L1-L5",
            )

    def test_empty_predicate_raises(self):
        from mcp_server.server import assert_fact

        with pytest.raises(ValueError, match="predicate must be a non-empty string"):
            assert_fact(
                subject="x",
                predicate="",
                object="z",
                source_ref="sources/foo.md#L1-L5",
            )

    def test_empty_object_raises(self):
        from mcp_server.server import assert_fact

        with pytest.raises(ValueError, match="object must be a non-empty string"):
            assert_fact(
                subject="x",
                predicate="y",
                object="",
                source_ref="sources/foo.md#L1-L5",
            )


class TestThreadLocalIsolation:
    """Regression for the cross-thread SQLite defect found during the Phase 4
    canonical MCP test. Each worker thread must receive its own connection.

    If a future refactor collapses _get_db() to a module-level shared
    connection, two threads will receive the same object — this test catches
    that. See memory/bugs/regression-ledger.md for the original defect record.
    """

    @pytest.mark.regression
    def test_two_threads_receive_distinct_connections(self):
        import threading

        results = {}

        def grab(name: str) -> None:
            results[name] = id(substrate._get_conn())

        t1 = threading.Thread(target=grab, args=("a",))
        t2 = threading.Thread(target=grab, args=("b",))
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert results["a"] != results["b"], (
            "Two worker threads received the same connection object — "
            "thread-local isolation has been broken. This is a regression of "
            "the SQLite cross-thread defect found in the Phase 4 canonical test."
        )


class TestRoundtrip:
    """End-to-end: write an assertion, search for it, verify it appears.

    Uses tmp_path to isolate from the production DB. Monkey-patches DB_PATH
    on the server module so _get_db() opens an isolated database for this test.
    """

    def test_assert_and_search_roundtrip(self, tmp_path):
        """After step 4 refactor, Substrate is independently usable — the test
        constructs its own instance with an isolated tmp DB, no monkey-patching
        of module globals needed. This is the value of the substrate/transport
        split: tests get clean isolation, derived projects get the same.
        """
        from assertion_store.substrate import Substrate

        sub = Substrate(
            db_path=tmp_path / "roundtrip.db",
            project_id=PROJECT_ID,
            source_roots=[tmp_path],  # not exercised by this test (no get_source)
        )

        write_result = sub.assert_fact(
            subject="Andrew Howie",
            predicate="was_born_in",
            object="the year 1735",
            source_ref="sources/test-fixture.md#L1-L5",
        )
        assert "fact_id" in write_result
        assert write_result["project_id"] == PROJECT_ID
        assert write_result["source_ref"].startswith(f"project://{PROJECT_ID}/")

        hits = sub.search_semantic(query="When was Andrew Howie born?", k=3)
        assert len(hits) >= 1, "search returned no results for a stored assertion"
        top = hits[0]
        assert top["subject"] == "Andrew Howie"
        assert top["object"] == "the year 1735"
        assert top["framing"] == "asserts"
        # Distance is a vector-similarity metric; lower is closer. We don't
        # pin an absolute value because the model and corpus state evolve;
        # what matters is that the stored assertion ranks above 'no match'.
        assert top["distance"] < 2.0
