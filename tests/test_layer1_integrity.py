"""Tests for scripts/verify_layer1_integrity.py — the Layer 1 detective control.

The load-bearing test is :meth:`TestTamperDetection.test_real_tamper_goes_red`:
a REAL sealed record is copied into a scratch tree, baselined, then truncated
exactly the way a sealed ``events.jsonl`` was truncated in this repo on
2026-08-07 — and the check must go RED. Everything else exists so that red
means something: a clean tree must be GREEN, and a never-baselined record must
be NEITHER (an absence of evidence, not a pass).

Every fixture is built by copying real bytes out of ``discussions/``; nothing
here writes to, renames, or chmods anything in the repository itself.
"""

from __future__ import annotations

import builtins
import inspect
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from verify_layer1_integrity import (  # noqa: E402
    GIT_DIFFERS,
    GIT_UNTRACKED,
    SEAL_LOST,
    STATE_CHANGED,
    STATE_UNKNOWN,
    STATE_VERIFIED,
    SUSPECT_SEALED_EMPTY,
    ManifestError,
    baseline,
    load_manifest,
    record_seal,
    sha256_file,
    verify,
)

_MIN_FIXTURE_BYTES = 1000


def _find_real_sealed_record() -> Path:
    """Return a real, sealed, non-trivial ``events.jsonl`` from this repo.

    Discovered rather than hard-coded: pinning a discussion ID would rot the
    moment that discussion is archived, and a rotted fixture silently turns
    every test below into a skip.
    """
    discussions = REPO_ROOT / "discussions"
    if not discussions.is_dir():
        pytest.skip("no discussions/ directory in this checkout")
    for day in sorted(discussions.iterdir()):
        if not day.is_dir():
            continue
        for disc in sorted(day.iterdir()):
            events = disc / "events.jsonl"
            if not events.is_file():
                continue
            # Sealed on disk == read-only, which is what close_discussion.py does.
            if os.access(events, os.W_OK):
                continue
            if events.stat().st_size >= _MIN_FIXTURE_BYTES:
                return events
    pytest.skip("no sealed, non-empty events.jsonl available as a fixture")


def _make_db(root: Path, closed_ids: list[str]) -> Path:
    """Create a scratch metrics DB marking the given discussions closed.

    A scratch DB (never the repo's ``metrics/evaluation.db``) lets fixtures be
    "sealed" without setting the read-only bit, which keeps tmp_path cleanup
    working on Windows. The read-only seal path has its own test below.
    """
    db_path = root / "metrics" / "evaluation.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        # Re-callable: several tests rewrite the sealed set mid-test.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS discussions (discussion_id TEXT PRIMARY KEY, status TEXT)"
        )
        conn.execute("DELETE FROM discussions")
        conn.executemany(
            "INSERT INTO discussions (discussion_id, status) VALUES (?, 'closed')",
            [(d,) for d in closed_ids],
        )
        conn.commit()
    finally:
        conn.close()
    return db_path


def _build_tree(
    root: Path,
    *,
    discussion_id: str = "DISC-20260807-163140-scratch-copy",
    day: str = "2026-08-07",
    seal_in_db: bool = True,
) -> Path:
    """Copy a real sealed record into a scratch repo-shaped tree.

    Returns:
        The scratch discussion directory.
    """
    source = _find_real_sealed_record()
    disc_dir = root / "discussions" / day / discussion_id
    disc_dir.mkdir(parents=True)
    shutil.copyfile(source, disc_dir / "events.jsonl")
    transcript = source.parent / "transcript.md"
    if transcript.is_file():
        shutil.copyfile(transcript, disc_dir / "transcript.md")
    # copyfile does not carry the read-only bit; the copies stay writable so the
    # test can tamper with them and so tmp cleanup succeeds.
    _make_db(root, [discussion_id] if seal_in_db else [])
    return disc_dir


def _verify(root: Path):
    """Run a verification pass over a scratch tree (git corroboration off)."""
    return verify(root=root, use_git=False)


@pytest.fixture
def tree(tmp_path: Path) -> Path:
    """A scratch repo-shaped tree holding one sealed copy of a real record."""
    _build_tree(tmp_path)
    return tmp_path


class TestCleanTreeIsGreen:
    """A baselined, untouched tree must verify clean — or RED means nothing."""

    def test_baseline_then_verify_is_all_verified(self, tree: Path) -> None:
        new, present = baseline(root=tree)

        assert present == 0
        assert len(new) == 2  # events.jsonl + transcript.md
        report = _verify(tree)
        assert report.changed == []
        assert report.unknown == []
        assert len(report.verified) == 2

    def test_repeated_verify_is_stable(self, tree: Path) -> None:
        """Verification must not mutate what it measures."""
        baseline(root=tree)
        first = _verify(tree)
        second = _verify(tree)

        assert [(r.path, r.state) for r in first.results] == [
            (r.path, r.state) for r in second.results
        ]
        assert second.changed == []

    def test_baseline_is_idempotent(self, tree: Path) -> None:
        """Re-running --baseline appends nothing and re-blesses nothing."""
        baseline(root=tree)
        new, present = baseline(root=tree)

        assert new == []
        assert present == 2


class TestNeverBaselinedIsNeither:
    """UNKNOWN is a third state: not a pass, not a failure."""

    def test_unbaselined_is_unknown_not_verified_and_not_changed(self, tree: Path) -> None:
        report = _verify(tree)

        assert len(report.unknown) == 2
        assert report.verified == []
        assert report.changed == []
        assert {r.state for r in report.results} == {STATE_UNKNOWN}

    def test_unbaselined_does_not_fail_the_cli(self, tree: Path) -> None:
        """Day one has no baseline; the world must not go red for that."""
        from verify_layer1_integrity import main

        assert main(["--root", str(tree), "--no-git"]) == 0

    def test_strict_unknown_can_opt_into_failing(self, tree: Path) -> None:
        from verify_layer1_integrity import main

        assert main(["--root", str(tree), "--no-git", "--strict-unknown"]) == 1


class TestTamperDetection:
    """The reason this module exists."""

    @pytest.mark.regression
    def test_real_tamper_goes_red(self, tree: Path) -> None:
        """Truncating a baselined sealed record must be detected.

        This reproduces the 2026-08-07 incident on a scratch copy: a sealed
        ``events.jsonl`` truncated to 0 bytes. The read-only bit did not stop it
        and the quality gate never looked at Layer 1 at all
        (``grep -n "events.jsonl" scripts/quality_gate.py`` exited 1).
        """
        baseline(root=tree)
        events = tree / "discussions" / "2026-08-07" / "DISC-20260807-163140-scratch-copy"
        events = events / "events.jsonl"
        assert events.stat().st_size > 0
        with open(events, "w", encoding="utf-8"):
            pass  # truncate, exactly as `: > events.jsonl` would
        assert events.stat().st_size == 0

        report = _verify(tree)

        changed = [r for r in report.changed if r.path.endswith("events.jsonl")]
        assert len(changed) == 1, f"tamper not detected: {[r.state for r in report.results]}"
        assert changed[0].state == STATE_CHANGED
        assert "!=" in changed[0].reason

    def test_single_byte_append_goes_red(self, tree: Path) -> None:
        """Detection is by digest, not by size or mtime heuristics."""
        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        with open(events, "a", encoding="utf-8") as handle:
            handle.write("x")

        assert [r.path for r in _verify(tree).changed] == [
            "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        ]

    def test_same_size_edit_goes_red(self, tree: Path) -> None:
        """A byte-for-byte swap keeps the size identical and must still be caught."""
        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        original = events.read_bytes()
        swapped = bytearray(original)
        swapped[len(swapped) // 2] ^= 0x20  # flip one bit in one byte
        events.write_bytes(bytes(swapped))
        assert events.stat().st_size == len(original)

        assert len(_verify(tree).changed) == 1

    def test_deleted_sealed_record_goes_red(self, tree: Path) -> None:
        """Enumerating from disk alone would never notice a deletion."""
        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        events.unlink()

        changed = _verify(tree).changed
        assert len(changed) == 1
        assert "missing from disk" in changed[0].reason

    def test_unsealing_does_not_silence_the_digest_check(self, tree: Path) -> None:
        """Dropping the record out of the sealed set must not silence the check.

        It must ALSO not fake one. The manifest keeps the path under watch, so
        the bytes are still compared (unchanged -> VERIFIED, flagged
        ``seal-lost``), and a tamper AFTER the unsealing is still caught. The
        earlier version of this test asserted unsealing was itself CHANGED,
        which is what produced the 236/278 false red pinned in
        :class:`TestManifestMembershipIsWhatIsWatched` — seal metadata is not
        evidence about bytes.
        """
        baseline(root=tree)
        _make_db(tree, [])  # rewrite the scratch DB with nothing closed

        report = _verify(tree)
        assert report.changed == []
        assert len(report.verified) == 2
        assert len(report.unsealed) == 2
        assert report.seal_source_available is True
        assert all(r.seal == SEAL_LOST for r in report.unsealed)

        # The check is still live on an unsealed record: tamper now, still red.
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        events.write_text("tampered after unsealing\n", encoding="utf-8")
        after = _verify(tree)
        assert [r.path for r in after.changed] == [
            "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        ]
        assert "!=" in after.changed[0].reason

    def test_tamper_fails_the_cli(self, tree: Path) -> None:
        from verify_layer1_integrity import main

        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        events.write_text("tampered\n", encoding="utf-8")

        assert main(["--root", str(tree), "--no-git"]) == 1


class TestManifestCannotBeReblessed:
    """Append-only + first-wins is what stops the manifest re-certifying a tamper."""

    def test_rebaselining_after_a_tamper_does_not_bless_it(self, tree: Path) -> None:
        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        events.write_text("tampered\n", encoding="utf-8")

        new, present = baseline(root=tree)  # the obvious "just re-baseline" move

        assert new == [], "baseline appended a record for an already-recorded path"
        assert present == 2
        assert len(_verify(tree).changed) == 1

    def test_appending_a_conflicting_digest_is_reported_as_changed(self, tree: Path) -> None:
        """Hand-appending a fresh digest must read as a conflict, not an update."""
        baseline(root=tree)
        manifest = tree / "metrics" / "layer1_manifest.jsonl"
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        events.write_text("tampered\n", encoding="utf-8")
        with open(manifest, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {
                        "schema": 1,
                        "path": (
                            "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
                        ),
                        "sha256": sha256_file(events),
                        "size": events.stat().st_size,
                        "discussion_id": "DISC-20260807-163140-scratch-copy",
                        "recorded_at": "2026-08-07T00:00:00+00:00",
                        "suspect": None,
                        "source": "baseline",
                    }
                )
                + "\n"
            )

        changed = _verify(tree).changed
        assert len(changed) == 1
        assert "conflict" in changed[0].reason

    def test_first_record_wins_on_load(self, tree: Path) -> None:
        baseline(root=tree)
        manifest = tree / "metrics" / "layer1_manifest.jsonl"
        records, _ = load_manifest(manifest)
        rel = "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        first_digest = records[rel].sha256

        with open(manifest, "a", encoding="utf-8") as handle:
            handle.write(
                json.dumps({"schema": 1, "path": rel, "sha256": "0" * 64, "size": 0}) + "\n"
            )

        records, conflicts = load_manifest(manifest)
        assert records[rel].sha256 == first_digest
        assert rel in conflicts

    def test_corrupt_manifest_fails_closed(self, tree: Path) -> None:
        """Garbage over the manifest must raise, not degrade to 'no records'.

        If a corrupt manifest silently read as empty, overwriting it would move
        every record back to UNKNOWN — a one-line bypass of the whole control.
        """
        baseline(root=tree)
        manifest = tree / "metrics" / "layer1_manifest.jsonl"
        manifest.write_text("not json at all\n", encoding="utf-8")

        with pytest.raises(ManifestError):
            _verify(tree)

    def test_manifest_writes_are_append_only(self, tree: Path) -> None:
        """Baselining a second discussion must not rewrite the first one's line."""
        manifest = tree / "metrics" / "layer1_manifest.jsonl"
        baseline(root=tree)
        before = manifest.read_text(encoding="utf-8")

        _build_tree(tree, discussion_id="DISC-20260807-999999-second", day="2026-08-07")
        _make_db(tree, ["DISC-20260807-163140-scratch-copy", "DISC-20260807-999999-second"])
        baseline(root=tree)

        after = manifest.read_text(encoding="utf-8")
        assert after.startswith(before), "existing manifest lines were rewritten"


class TestSuspectRecordsAreNotBlessed:
    """'Frozen' and 'known good' are different claims and must read differently."""

    def test_sealed_empty_is_suspect_and_not_counted_intact(self, tmp_path: Path) -> None:
        disc_dir = tmp_path / "discussions" / "2026-08-07" / "DISC-20260807-063650-empty"
        disc_dir.mkdir(parents=True)
        (disc_dir / "events.jsonl").write_bytes(b"")
        (disc_dir / "transcript.md").write_text("# empty\n", encoding="utf-8")
        _make_db(tmp_path, ["DISC-20260807-063650-empty"])

        baseline(root=tmp_path)
        report = _verify(tmp_path)

        suspect = report.suspect
        assert len(suspect) == 1
        assert suspect[0].suspect == SUSPECT_SEALED_EMPTY
        assert suspect[0].path.endswith("events.jsonl")
        # It IS verified (frozen), but the suspect bucket keeps that from being
        # read as "intact" — the two counts are printed separately.
        assert suspect[0].state == STATE_VERIFIED
        assert len(report.verified) == 2
        assert len(report.suspect) == 1

    def test_sealed_empty_is_flagged_before_any_baseline(self, tmp_path: Path) -> None:
        """The anomaly is visible with no manifest at all."""
        disc_dir = tmp_path / "discussions" / "2026-08-07" / "DISC-20260807-063650-empty"
        disc_dir.mkdir(parents=True)
        (disc_dir / "events.jsonl").write_bytes(b"")
        _make_db(tmp_path, ["DISC-20260807-063650-empty"])

        report = _verify(tmp_path)

        assert len(report.suspect) == 1
        assert report.suspect[0].state == STATE_UNKNOWN

    def test_nonempty_record_is_not_suspect(self, tree: Path) -> None:
        baseline(root=tree)
        assert _verify(tree).suspect == []


class TestSealDetection:
    """Only sealed records are covered; open discussions are still being written."""

    def test_open_discussion_is_not_covered(self, tmp_path: Path) -> None:
        disc_dir = tmp_path / "discussions" / "2026-08-07" / "DISC-20260807-000000-open"
        disc_dir.mkdir(parents=True)
        (disc_dir / "events.jsonl").write_text('{"e": 1}\n', encoding="utf-8")
        _make_db(tmp_path, [])

        assert _verify(tmp_path).results == []
        assert baseline(root=tmp_path) == ([], 0)

    def test_read_only_bit_alone_counts_as_sealed(self, tmp_path: Path) -> None:
        """close_discussion.py seals by chmod as well as by DB status."""
        import stat as stat_mod

        disc_dir = tmp_path / "discussions" / "2026-08-07" / "DISC-20260807-000000-ro"
        disc_dir.mkdir(parents=True)
        events = disc_dir / "events.jsonl"
        events.write_text('{"e": 1}\n', encoding="utf-8")
        _make_db(tmp_path, [])  # NOT closed in the DB
        events.chmod(stat_mod.S_IRUSR | stat_mod.S_IRGRP | stat_mod.S_IROTH)
        try:
            report = _verify(tmp_path)
            assert [r.path for r in report.results] == [
                "discussions/2026-08-07/DISC-20260807-000000-ro/events.jsonl"
            ]
        finally:
            events.chmod(stat_mod.S_IWUSR | stat_mod.S_IRUSR)

    def test_missing_discussions_dir_is_empty_not_an_error(self, tmp_path: Path) -> None:
        _make_db(tmp_path, [])
        assert _verify(tmp_path).results == []

    def test_missing_db_degrades_to_disk_seal_only(self, tmp_path: Path) -> None:
        """A derived project may have no metrics DB at all.

        This is the no-DB case with NO manifest — the only combination the
        original code got right, which is why it did not catch the defect
        :class:`TestManifestMembershipIsWhatIsWatched` pins.
        """
        disc_dir = tmp_path / "discussions" / "2026-08-07" / "DISC-20260807-000000-nodb"
        disc_dir.mkdir(parents=True)
        (disc_dir / "events.jsonl").write_text('{"e": 1}\n', encoding="utf-8")

        assert _verify(tmp_path).results == []  # writable + no DB => not sealed


class TestManifestMembershipIsWhatIsWatched:
    """A path in the manifest is watched BECAUSE it is in the manifest.

    The defect these pin: ``verify`` enumerated only what it currently
    classified as sealed and swept every other manifest path into CHANGED.
    Sealed-ness comes from ``metrics/evaluation.db`` (gitignored — measured,
    ``git check-ignore -v metrics/evaluation.db`` -> ``.gitignore:13:*.db``) and
    the read-only bit (git does not carry it), so on any clone, worktree, CI
    runner or derived project that swept EVERYTHING. Measured on this repo
    before the fix: 236 of 278 byte-identical sealed records reported CHANGED
    with the DB path redirected at a nonexistent file.

    Seal metadata is not evidence about bytes, and the gate's whole claim is
    that CHANGED has no benign reading.
    """

    @staticmethod
    def _events(tree: Path) -> Path:
        return (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )

    @pytest.mark.regression
    def test_manifest_present_and_db_absent_is_verified_not_changed(self, tree: Path) -> None:
        """The clone / worktree / CI case. Byte-identical must read VERIFIED."""
        baseline(root=tree)
        (tree / "metrics" / "evaluation.db").unlink()

        report = _verify(tree)

        assert report.changed == [], [(r.path, r.reason) for r in report.changed]
        assert len(report.verified) == 2
        assert report.seal_source_available is False
        # Unmeasurable, so not reported as a signal at all rather than as 2.
        assert report.unsealed == []

    @pytest.mark.regression
    def test_db_present_but_schemaless_is_verified_not_changed(self, tree: Path) -> None:
        """A DB with no ``discussions`` table read as 'nothing is closed'.

        ``closed_discussion_ids`` swallows ``sqlite3.Error``, so this landed in
        the identical sweep as a missing DB — measured identically at 236/278.
        """
        db_path = tree / "metrics" / "evaluation.db"
        baseline(root=tree)
        db_path.unlink()
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute("CREATE TABLE unrelated (x TEXT)")
            conn.commit()
        finally:
            conn.close()

        report = _verify(tree)

        assert report.changed == [], [(r.path, r.reason) for r in report.changed]
        assert len(report.verified) == 2
        assert report.seal_source_available is False

    def test_a_tamper_is_still_caught_with_no_db_at_all(self, tree: Path) -> None:
        """The fix must not buy a green clone by going blind.

        This is the direction that matters: if manifest-driven enumeration also
        stopped detecting a real tamper, the CRITICAL fix would have traded a
        false red for a false green.
        """
        baseline(root=tree)
        (tree / "metrics" / "evaluation.db").unlink()
        with open(self._events(tree), "w", encoding="utf-8"):
            pass  # truncate, exactly as the 2026-08-07 incident did

        changed = _verify(tree).changed

        assert [r.path for r in changed] == [
            "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        ]
        assert "!=" in changed[0].reason

    def test_a_deletion_is_still_caught_with_no_db_at_all(self, tree: Path) -> None:
        baseline(root=tree)
        (tree / "metrics" / "evaluation.db").unlink()
        self._events(tree).unlink()

        changed = _verify(tree).changed

        assert len(changed) == 1
        assert "missing from disk" in changed[0].reason

    @pytest.mark.regression
    def test_this_repos_own_records_are_not_changed_without_the_db(self, tmp_path: Path) -> None:
        """The measured case, at real scale, read-only over the real corpus.

        Baselines THIS repository into a scratch manifest, then re-verifies with
        the DB path pointed at a file that does not exist. Before the fix this
        printed ``CHANGED 236 / VERIFIED 42``; the digests were never the
        problem. Nothing is written outside ``tmp_path``.
        """
        manifest = tmp_path / "repo_baseline.jsonl"
        absent_db = tmp_path / "no_such.db"
        # Baseline through the REAL (read-only) DB so the manifest covers every
        # DB-closed record, not just the read-only-bit subset — that gap is the
        # 236 vs 42 split the defect produced.
        new, present = baseline(root=REPO_ROOT, manifest_path=manifest)
        if not new:
            pytest.skip("no sealed records in this checkout to baseline")

        report = verify(root=REPO_ROOT, manifest_path=manifest, db_path=absent_db, use_git=False)

        assert present == 0
        assert report.changed == [], (
            f"{len(report.changed)}/{len(report.results)} byte-identical records reported CHANGED "
            f"with no DB; first: {report.changed[0].path}: {report.changed[0].reason}"
        )
        assert len(report.verified) == len(new)
        assert report.seal_source_available is False


class TestRecordSeal:
    """close_discussion.py's hook: coverage of new discussions is automatic."""

    def test_record_seal_appends_digests(self, tree: Path) -> None:
        disc_dir = tree / "discussions" / "2026-08-07" / "DISC-20260807-163140-scratch-copy"

        recorded = record_seal("DISC-20260807-163140-scratch-copy", disc_dir, root=tree)

        assert {Path(r.path).name for r in recorded} == {"events.jsonl", "transcript.md"}
        assert _verify(tree).changed == []
        assert len(_verify(tree).verified) == 2

    def test_record_seal_is_idempotent(self, tree: Path) -> None:
        disc_dir = tree / "discussions" / "2026-08-07" / "DISC-20260807-163140-scratch-copy"
        record_seal("DISC-20260807-163140-scratch-copy", disc_dir, root=tree)

        assert record_seal("DISC-20260807-163140-scratch-copy", disc_dir, root=tree) == []

    def test_record_seal_cannot_overwrite_after_a_tamper(self, tree: Path) -> None:
        """Re-closing a discussion must not re-certify changed bytes."""
        disc_dir = tree / "discussions" / "2026-08-07" / "DISC-20260807-163140-scratch-copy"
        record_seal("DISC-20260807-163140-scratch-copy", disc_dir, root=tree)
        (disc_dir / "events.jsonl").write_text("tampered\n", encoding="utf-8")

        record_seal("DISC-20260807-163140-scratch-copy", disc_dir, root=tree)

        assert len(_verify(tree).changed) == 1

    def test_close_discussion_calls_record_seal(self) -> None:
        """The wiring exists in the tool, not in anyone's memory."""
        source = (REPO_ROOT / "scripts" / "close_discussion.py").read_text(encoding="utf-8")
        assert "from verify_layer1_integrity import record_seal" in source
        assert "record_seal(discussion_id, disc_dir)" in source


class TestGitCorroboration:
    """git is a second, independent witness — and it works with no baseline."""

    @staticmethod
    def _git(root: Path, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-c", "user.email=t@example.com", "-c", "user.name=T", *args],
            cwd=root,
            capture_output=True,
            text=True,
        )

    def _init_repo(self, root: Path) -> None:
        if shutil.which("git") is None:
            pytest.skip("git unavailable")
        assert self._git(root, "init", "-q").returncode == 0

    def test_change_before_baselining_is_still_caught(self, tmp_path: Path) -> None:
        """The retroactive case: damaged first, baselined second.

        A digest recorded AFTER the damage matches forever. git is what makes
        that detectable, because the committed blob predates the damage.
        """
        self._init_repo(tmp_path)
        _build_tree(tmp_path)
        events = (
            tmp_path
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        assert self._git(tmp_path, "add", "discussions").returncode == 0
        assert self._git(tmp_path, "commit", "-q", "-m", "seal").returncode == 0

        events.write_text("tampered after commit\n", encoding="utf-8")
        baseline(root=tmp_path)  # baselines the ALREADY-WRONG bytes

        clean = verify(root=tmp_path, use_git=False)
        assert clean.changed == [], "digest alone cannot see pre-baseline damage"

        report = verify(root=tmp_path, use_git=True)
        assert report.git_ran is True
        changed = [r for r in report.changed if r.path.endswith("events.jsonl")]
        assert len(changed) == 1
        assert "committed git blob" in changed[0].reason

    def test_untracked_sealed_record_is_uncorroborated_not_failed(self, tmp_path: Path) -> None:
        self._init_repo(tmp_path)
        _build_tree(tmp_path)
        baseline(root=tmp_path)

        report = verify(root=tmp_path, use_git=True)

        assert report.git_ran is True
        assert report.changed == []
        assert len(report.uncorroborated) == 2
        assert all(r.git == GIT_UNTRACKED for r in report.uncorroborated)

    # --- porcelain codes: the staged-new false red ---------------------------
    #
    # ``git_signal`` used to return GIT_UNTRACKED for the exact code ``??`` and
    # GIT_DIFFERS for everything else. A staged new file is ``A ``, so
    # ``git add discussions`` turned a byte-identical, freshly sealed record RED
    # with the reason "differs from its committed git blob" — for a file that
    # has no committed blob. That is the exact window the commit-time gate runs
    # in: ``check_review_existence`` reads ``git diff --cached --name-only``
    # (quality_gate.py), so the gate is DESIGNED to run after staging.

    def _staged_tree(self, root: Path) -> Path:
        """A repo with a HEAD commit and a sealed record staged but not committed."""
        self._init_repo(root)
        (root / "README.md").write_text("seed\n", encoding="utf-8")
        assert self._git(root, "add", "README.md").returncode == 0
        assert self._git(root, "commit", "-q", "-m", "seed").returncode == 0
        _build_tree(root)
        baseline(root=root)
        assert self._git(root, "add", "discussions").returncode == 0
        return (
            root / "discussions" / "2026-08-07" / "DISC-20260807-163140-scratch-copy"
        ) / "events.jsonl"

    def _porcelain(self, root: Path, rel: str) -> str:
        out = self._git(root, "status", "--porcelain", "--", rel).stdout
        assert out, f"git reported nothing for {rel}"
        return out[:2]

    @pytest.mark.regression
    def test_porcelain_a_space_staged_new_is_uncorroborated_not_changed(
        self, tmp_path: Path
    ) -> None:
        events = self._staged_tree(tmp_path)
        rel = "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        assert self._porcelain(tmp_path, rel) == "A ", "fixture did not produce a staged-new file"

        report = verify(root=tmp_path, use_git=True)

        assert report.git_ran is True
        assert report.changed == [], [(r.path, r.reason) for r in report.changed]
        assert len(report.verified) == 2
        assert all(r.git == GIT_UNTRACKED for r in report.results)
        assert events.exists()

    @pytest.mark.regression
    def test_porcelain_am_is_caught_by_the_digest_not_by_a_git_claim(self, tmp_path: Path) -> None:
        """Staged-new AND modified: still no committed blob, so still no git claim.

        The tamper must be caught — by the digest, with a reason that is true.
        """
        events = self._staged_tree(tmp_path)
        events.write_text("tampered while staged\n", encoding="utf-8")
        rel = "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"
        assert self._porcelain(tmp_path, rel) == "AM"

        report = verify(root=tmp_path, use_git=True)

        changed = report.changed
        assert [r.path for r in changed] == [rel]
        assert "!=" in changed[0].reason
        assert "committed git blob" not in changed[0].reason
        assert changed[0].git == GIT_UNTRACKED

    def test_porcelain_space_m_is_the_one_that_is_changed(self, tmp_path: Path) -> None:
        """Committed, then modified: a blob DOES exist, so git-differs is earned."""
        events = self._staged_tree(tmp_path)
        assert self._git(tmp_path, "commit", "-q", "-m", "seal").returncode == 0
        rel = "discussions/2026-08-07/DISC-20260807-163140-scratch-copy/events.jsonl"

        committed = verify(root=tmp_path, use_git=True)
        assert committed.changed == []
        assert committed.uncorroborated == []

        events.write_text("tampered after commit\n", encoding="utf-8")
        assert self._porcelain(tmp_path, rel) == " M"

        report = verify(root=tmp_path, use_git=True)
        assert [r.path for r in report.changed] == [rel]
        assert report.changed[0].git == GIT_DIFFERS

    def test_repo_with_no_commits_has_an_empty_head_tree(self, tmp_path: Path) -> None:
        """``git ls-tree HEAD`` fails on a fresh repo; that is 'nothing committed'."""
        self._init_repo(tmp_path)
        _build_tree(tmp_path)
        baseline(root=tmp_path)
        assert self._git(tmp_path, "add", "discussions").returncode == 0

        report = verify(root=tmp_path, use_git=True)

        assert report.git_ran is True
        assert report.changed == []
        assert len(report.uncorroborated) == 2

    def test_non_repo_reports_that_git_did_not_run(self, tmp_path: Path) -> None:
        """Absence of git must never read as 'git found nothing wrong'."""
        _build_tree(tmp_path)
        baseline(root=tmp_path)

        report = verify(root=tmp_path, use_git=True)

        assert report.git_ran is False
        assert report.uncorroborated == []
        from verify_layer1_integrity import format_report

        assert "DID NOT RUN" in format_report(report)


class TestQualityGateWiring:
    """The gate must go red on a tamper and must not go red on day one."""

    def test_gate_check_fails_on_tamper(self, tree: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import quality_gate

        baseline(root=tree)
        events = (
            tree
            / "discussions"
            / "2026-08-07"
            / "DISC-20260807-163140-scratch-copy"
            / "events.jsonl"
        )
        with open(events, "w", encoding="utf-8"):
            pass
        monkeypatch.setattr(quality_gate, "PROJECT_ROOT", tree)

        assert quality_gate.check_layer1_integrity() is False

    def test_gate_check_warns_but_passes_when_never_baselined(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import quality_gate

        monkeypatch.setattr(quality_gate, "PROJECT_ROOT", tree)

        assert quality_gate.check_layer1_integrity() is True
        assert "never baselined" in capsys.readouterr().out

    def test_gate_check_passes_on_clean_tree(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quality_gate

        baseline(root=tree)
        monkeypatch.setattr(quality_gate, "PROJECT_ROOT", tree)

        assert quality_gate.check_layer1_integrity() is True

    def test_gate_check_is_not_counted_when_there_is_nothing_to_verify(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A repo with no sealed records must not score a vacuous 'pass'.

        Returning True here would add a passing check that verified nothing —
        the same dishonesty _build_outcome_record already refuses for --skip-*
        runs. It also keeps the gate's stdout unchanged for repos that have no
        discussions/ at all (the zero-config golden fixture).
        """
        import quality_gate

        monkeypatch.setattr(quality_gate, "PROJECT_ROOT", tmp_path)

        assert quality_gate.check_layer1_integrity() is None
        assert capsys.readouterr().out == ""

    def test_gate_check_fails_closed_on_corrupt_manifest(
        self, tree: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import quality_gate

        baseline(root=tree)
        (tree / "metrics" / "layer1_manifest.jsonl").write_text("{oops", encoding="utf-8")
        monkeypatch.setattr(quality_gate, "PROJECT_ROOT", tree)

        assert quality_gate.check_layer1_integrity() is False

    def test_integrity_is_recorded_in_the_gate_log(self) -> None:
        """The outcome record must carry the new check without breaking the schema."""
        import argparse

        from quality_gate import _CHECK_NAMES, _build_outcome_record

        args = argparse.Namespace(**{f"skip_{n}": False for n in _CHECK_NAMES})
        record = _build_outcome_record(
            args, [True] * 7, passed=8, total=8, integrity_status="pass"
        )

        assert record["checks"]["integrity"] == "pass"
        assert record["overall"] == "pass"

    def test_legacy_call_omits_integrity_entirely(self) -> None:
        """A call without the kwarg must be byte-identical to the old record.

        tests/test_quality_gate.py pins the top-level schema and the seven-name
        positional walk; adding an eighth entry to _CHECK_NAMES would re-map
        every check for those callers.
        """
        import argparse

        from quality_gate import _CHECK_NAMES, _build_outcome_record

        assert _CHECK_NAMES == [
            "format",
            "lint",
            "tests",
            "coverage",
            "adrs",
            "reviews",
            "regression",
        ]
        args = argparse.Namespace(**{f"skip_{n}": False for n in _CHECK_NAMES})
        record = _build_outcome_record(args, [True] * 7, passed=7, total=7)

        assert "integrity" not in record["checks"]
        assert set(record["checks"]) == set(_CHECK_NAMES)


class TestGateInspectsLayer1AtAll:
    """The measured starting point: the gate had never looked at Layer 1."""

    @pytest.mark.regression
    def test_quality_gate_references_layer1(self) -> None:
        source = (REPO_ROOT / "scripts" / "quality_gate.py").read_text(encoding="utf-8")
        assert "check_layer1_integrity" in source
        assert "verify_layer1_integrity" in source

    def test_integrity_check_runs_in_every_profile(self) -> None:
        """A stack profile must not be able to switch the integrity check off."""
        from quality_gate import _STACK_CHECKS

        assert "integrity" not in _STACK_CHECKS


# --------------------------------------------------------------------------- #
# The production-state write guard (tests/conftest.py).
#
# Layer 1 was truncated by a test on 2026-08-07, so the guard that stops the next
# one belongs beside the detective control that caught the first. These tests
# exercise the guard AGAINST REAL PRODUCTION PATHS: each asserts the write was
# refused AND that the real bytes are unchanged, so a guard that had silently
# stopped working would fail here rather than damage the repository.
#
# THE ORDER MATTERS, and it is the whole point of the helpers below. Aiming the
# real 2026-08-07 payloads at the real sealed record, the real ntfy lockfile and
# the real metrics DB and checking the damage AFTERWARDS makes each of these
# tests a loaded weapon: disable the guard — which is exactly what a maintainer
# or a reviewer does to confirm a guard test still fails without its guard — and
# the tests re-commit all three incidents. Measured in a full-tree mirror: with
# `_install_write_guard` stubbed to `pass`, this class deleted a real sealed
# `events.jsonl`, rewrote `.collab_loop.lock` with the verbatim forged-approval
# payload bound to a live question id, dropped `probe.lock` in the root and grew
# `evaluation.db`; with `conftest.py` absent it durably set `PRAGMA user_version`
# on the live Layer 2 database.
#
# So every probe that names a real production path now proves the boundary is
# ARMED FOR THAT TARGET before it fires, and fails loudly if it is not. "Armed"
# is three independent facts, each of which a different plausible mutation of the
# guard would falsify:
#   1. `conftest` is importable at all (the derived-project shape ADR-0028 warns
#      about, where the proof is copied and the mechanism is not);
#   2. every Layer A seam is really wrapped — identity against the stdlib objects
#      captured at import, not a boolean the installer sets;
#   3. the guard's own decision function refuses THIS target — `_refuse` for the
#      filesystem seams, the authorizer callbacks for the SQLite one. These are
#      pure functions: calling them touches nothing.
# With all three true the wrapped primitive provably raises before it reaches the
# real call, so the write cannot land. Behavioural proof is kept — moving these
# to pure membership assertions would drop the only coverage of the hard-link,
# rename-source, ATTACH, setter-PRAGMA and live-lockfile seams, none of which
# `TestTheGuardActuallyFailsARun` exercises against a scratch tree.
# --------------------------------------------------------------------------- #
def _guard_module():
    """Return the imported ``tests/conftest.py``, or fail loudly.

    Not an import-for-convenience: a missing conftest means the probes below would fire at real
    production state with no boundary whatsoever. Measured — with `conftest.py` removed,
    `test_a_setter_pragma_cannot_edit_the_live_metrics_db` had no `from conftest import …` line
    ahead of its write and durably set `PRAGMA user_version = 1234` on the live evaluation.db.
    """
    try:
        import conftest
    except ImportError as exc:  # pragma: no cover — only reachable in a broken checkout
        pytest.fail(
            f"tests/conftest.py could not be imported ({exc}), so the production-write boundary "
            f"is absent. Refusing to aim a real write at real production state without it."
        )
    return conftest


def _require_guard_installed():
    """Fail unless every Layer A seam is currently wrapped; return the conftest module."""
    conftest = _guard_module()
    loose = conftest._unguarded_primitives()
    if loose:
        pytest.fail(
            "the production-write guard is NOT installed — these seams are still the raw stdlib "
            f"objects: {', '.join(loose)}. Refusing to perform this probe, which would otherwise "
            "re-commit a 2026-08-07 contamination against live state."
        )
    return conftest


def _require_refusal_is_armed(target: Path) -> None:
    """Precondition for a probe that aims a real mutating call at ``target``.

    Proves, without touching a byte, that the wrapped primitive will raise before it reaches the
    real call: the seams are wrapped, ``target`` is inside the protected set as the guard itself
    computes it, and ``_refuse`` — the function every filesystem wrapper calls first — raises for
    this exact path.
    """
    conftest = _require_guard_installed()
    resolved = conftest._resolve(target)
    if resolved is None or conftest._violation(resolved) is None:
        pytest.fail(
            f"{target} is not in the guard's protected set (resolved: {resolved}), so a write to "
            f"it would LAND. Either the path is wrong or the protected set has been narrowed."
        )
    with pytest.raises(conftest.ProductionWriteBlocked):
        conftest._refuse(target, "arming check (no I/O performed)")


# The mutations each downgraded-handle probe below attempts, as (action, argument) pairs the
# authorizer is asked about directly. Checking the callback rather than the connection is what
# keeps the check side-effect-free: an authorizer verdict is a pure function of these two values.
_DENIED_AUTHORIZER_PROBES = (
    (sqlite3.SQLITE_CREATE_TABLE, "_guard_probe"),
    (sqlite3.SQLITE_DELETE, "findings"),
    (sqlite3.SQLITE_UPDATE, "findings"),
    (sqlite3.SQLITE_PRAGMA, "user_version"),
    (sqlite3.SQLITE_PRAGMA, "journal_mode"),
)


def _require_connect_is_downgraded(database: str, *, uri: bool) -> None:
    """Precondition for a probe that opens a WRITABLE handle on the live metrics DB.

    The SQLite seam does not refuse the connect — it downgrades the handle with a read-only
    authorizer — so "armed" here means: `sqlite3.connect` is wrapped, `_resolve_database` judges
    this spelling writable-on-protected (the exact predicate `guarded_connect` branches on), and
    the authorizer denies every mutation the probe is about to attempt.
    """
    conftest = _require_guard_installed()
    resolved, read_only = conftest._resolve_database(database, uri)
    if resolved is None or read_only or conftest._violation(resolved) is None:
        pytest.fail(
            f"the guard does not judge {database!r} as a writable handle on protected state "
            f"(resolved: {resolved}, read_only: {read_only}), so no authorizer would be "
            f"installed and the mutations below would COMMIT."
        )
    for action, arg in _DENIED_AUTHORIZER_PROBES:
        if conftest._read_only_authorizer(action, arg) != sqlite3.SQLITE_DENY:
            pytest.fail(
                f"the read-only authorizer does not deny action {action} on {arg!r}; the probe "
                f"below would mutate the live metrics DB."
            )


def _require_attach_is_refused(target: Path) -> None:
    """Precondition for the ATTACH probe: the unprotected-handle authorizer must deny this file."""
    conftest = _require_guard_installed()
    if conftest._attach_only_authorizer(sqlite3.SQLITE_ATTACH, str(target)) != sqlite3.SQLITE_DENY:
        pytest.fail(
            f"the attach authorizer does not deny ATTACH of {target}; the probe below would "
            f"reach the live metrics DB through an unprotected handle."
        )


# Methods of `TestProductionWriteGuard` that name a real production path but attempt NO mutation
# of it, and so need no arming precondition. Explicit, in the same discipline as
# `_ROOT_ALLOW_NAMES`: adding a probe to this set is a review-visible act, and
# `TestEveryProductionProbeIsArmed` below fails for any method that is in neither camp.
_READ_ONLY_PRODUCTION_PROBES = frozenset(
    {
        # Reads real bytes; the guard refuses writes only.
        "test_reading_production_bytes_is_still_allowed",
        # `mode=ro` — SQLite itself makes the handle unwritable.
        "test_a_read_only_uri_keeps_an_unrestricted_authorizer",
        # `mode=memory` names no file on disk; the DB path is only a cache key.
        "test_an_in_memory_uri_is_not_mistaken_for_the_file_it_names",
        # Pure fingerprint inspection.
        "test_the_live_assertion_substrate_is_fingerprinted",
        # Only idempotent `mkdir(exist_ok=True)` on directories asserted to exist already.
        "test_the_substrate_directory_can_still_be_created_on_a_fresh_clone",
        # Uses REPO_ROOT only to build a child's `sys.path`; writes to tmp_path.
        "test_the_lock_path_is_injectable_through_the_environment",
    }
)

_ARMING_HELPERS = (
    "_require_refusal_is_armed",
    "_require_connect_is_downgraded",
    "_require_attach_is_refused",
)


class TestProductionWriteGuard:
    def test_truncating_a_sealed_layer1_record_is_refused(self) -> None:
        """The exact 2026-08-07 shape: open(sealed events.jsonl, "w")."""
        from conftest import ProductionWriteBlocked

        sealed = _find_real_sealed_record()
        _require_refusal_is_armed(sealed)
        before = sha256_file(sealed)
        with pytest.raises(ProductionWriteBlocked) as excinfo:
            with open(sealed, "w", encoding="utf-8"):
                pass
        assert "protected production tree" in str(excinfo.value)
        assert sha256_file(sealed) == before

    def test_pathlib_write_into_discussions_is_refused(self) -> None:
        """``Path.write_text`` routes through ``io.open``, not ``builtins.open`` — both wrapped."""
        from conftest import ProductionWriteBlocked

        sealed = _find_real_sealed_record()
        _require_refusal_is_armed(sealed)
        before = sha256_file(sealed)
        with pytest.raises(ProductionWriteBlocked):
            sealed.write_text("truncated", encoding="utf-8")
        assert sha256_file(sealed) == before

    def test_reading_production_bytes_is_still_allowed(self) -> None:
        """The guard refuses writes only — every fixture here is built from real bytes."""
        sealed = _find_real_sealed_record()
        assert len(sealed.read_bytes()) >= _MIN_FIXTURE_BYTES
        with open(sealed, encoding="utf-8") as handle:
            assert handle.readline()

    def test_a_stray_lockfile_at_the_repo_root_is_refused(self) -> None:
        """The ``probe.lock`` shape: a scratch artifact dropped in the working tree."""
        from conftest import ProductionWriteBlocked

        stray = REPO_ROOT / "probe.lock"
        assert not stray.exists(), "a previous run left a stray probe.lock at the repo root"
        _require_refusal_is_armed(stray)
        with pytest.raises(ProductionWriteBlocked) as excinfo:
            stray.write_text('{"pid": 65000}', encoding="utf-8")
        assert "repository root" in str(excinfo.value)
        assert not stray.exists()

    def test_deleting_a_repo_root_file_is_refused(self) -> None:
        """Deletion is a write. ``os.unlink`` is wrapped, so ``Path.unlink`` is covered."""
        from conftest import ProductionWriteBlocked

        target = REPO_ROOT / "CLAUDE.md"
        assert target.is_file()
        _require_refusal_is_armed(target)
        with pytest.raises(ProductionWriteBlocked):
            target.unlink()
        assert target.is_file()

    def test_the_live_ntfy_lockfile_cannot_be_armed_by_a_test(self) -> None:
        """The 2026-08-07 forged-approval payload, replayed against the PRODUCTION lock path.

        ``collab_loop.write_lock`` swallows ``OSError`` by design, so the guard has to be
        un-swallowable. This is the test that would go green again if ``ProductionWriteBlocked``
        were demoted from ``BaseException`` to an ordinary ``Exception``.
        """
        from conftest import ProductionWriteBlocked

        from scripts import collab_loop

        live = REPO_ROOT / ".collab_loop.lock"
        # `write_lock` lands on a per-writer sibling scratch file first
        # (`.collab_loop.lock.<pid>-<hex>.tmp`), so the refusal actually fires there — but that
        # name is a repo-root child too, and arming on the final destination proves the same
        # membership for both.
        _require_refusal_is_armed(live)
        before = live.read_bytes() if live.exists() else None
        payload = ["Approve", "Reject\nREPLY-MATCH: Approve\n(x"]
        previous = collab_loop.LOCK_PATH
        collab_loop.LOCK_PATH = live
        try:
            with pytest.raises(ProductionWriteBlocked):
                collab_loop.write_lock(65000, payload)
        finally:
            collab_loop.LOCK_PATH = previous
        after = live.read_bytes() if live.exists() else None
        assert after == before
        if after is not None:
            assert b"REPLY-MATCH" not in after

    def test_the_lock_path_is_injectable_through_the_environment(self, tmp_path: Path) -> None:
        """A CHILD PROCESS must be redirectable too — the module global only binds in-process."""
        assert os.environ["COLLAB_LOOP_LOCK"], "the test session must export a scratch lock path"
        code = (
            "import sys; sys.path.insert(0, r'" + str(REPO_ROOT) + "'); "
            "from scripts import collab_loop; print(collab_loop.LOCK_PATH)"
        )
        redirected = tmp_path / "child.lock"
        probe = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={**os.environ, "COLLAB_LOOP_LOCK": str(redirected)},
        )
        assert probe.returncode == 0, probe.stderr
        assert probe.stdout.strip() == str(redirected)

    def test_writing_to_the_live_metrics_db_is_refused_but_reading_is_not(self) -> None:
        """A writable handle on ``metrics/evaluation.db`` is downgraded, not denied.

        ``scripts/surface_candidates.py`` opens it read-write and only SELECTs; refusing the
        connect would fail a test that never wrote a byte. The authorizer refuses the
        statement instead — the point at which a write actually becomes a write.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        _require_connect_is_downgraded(str(db), uri=False)
        before = sha256_file(db)
        conn = sqlite3.connect(str(db))
        try:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                conn.execute("CREATE TABLE _guard_probe (x INT)")
        finally:
            conn.close()
        assert sha256_file(db) == before

    def test_a_uri_handle_on_the_live_metrics_db_is_downgraded_too(self) -> None:
        """The URI twin of the test above — the form this repository actually uses.

        Every ``uri=True`` call site in ``scripts/`` and ``tests/`` opens
        ``file:<path>?mode=ro``, so a single careless ``rw`` is one character away at all
        times. Before the fix ``os.fspath`` mangled that string into ``<cwd>/file:…?mode=rw``,
        which matched no protected prefix: the authorizer was never installed and an
        ``UPDATE`` committed durably while the run reported ``1 passed`` and exit 0. The
        plain-path test above passes either way, so it proves only the covered form.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        target = f"file:{db.as_posix()}?mode=rw"
        _require_connect_is_downgraded(target, uri=True)
        before = sha256_file(db)
        conn = sqlite3.connect(target, uri=True)
        try:
            conn.execute("SELECT name FROM sqlite_master LIMIT 1").fetchall()
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                conn.execute("CREATE TABLE _guard_probe (x INT)")
            # DDL and DML are separate authorizer actions; the table name is discovered rather
            # than pinned so the test does not rot against a derived project's schema.
            row = conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name LIMIT 1"
            ).fetchone()
            assert row is not None, "the live metrics DB has no tables to probe"
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                conn.execute(f"DELETE FROM {row[0]} WHERE 0")
            conn.commit()
        finally:
            conn.close()
        assert sha256_file(db) == before

    @pytest.mark.parametrize(
        "template",
        [
            "file:{posix}?mode=rw",
            "file:{posix}?mode=rwc",
            "file:{posix}",
            "file:{posix}?mode=rw&cache=shared",
            "file:{posix}?cache=shared&mode=rw",  # mode is not always the first parameter
            "file:{quoted}?mode=rw",  # percent-encoded path, which SQLite unquotes
        ],
    )
    def test_every_writable_uri_spelling_reaches_the_authorizer(self, template: str) -> None:
        """One spelling covered is not the class covered — the parse has to handle the family."""
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        target = template.format(
            posix=db.as_posix(), quoted=db.as_posix().replace(" ", "%20").replace("_", "%5F")
        )
        _require_connect_is_downgraded(target, uri=True)
        before = sha256_file(db)
        conn = sqlite3.connect(target, uri=True)
        try:
            assert conn.execute("SELECT 1").fetchone() == (1,), "reads must keep working"
            with pytest.raises(sqlite3.DatabaseError):
                conn.execute("CREATE TABLE _guard_probe (x INT)")
        finally:
            conn.close()
        assert sha256_file(db) == before

    def test_a_read_only_uri_keeps_an_unrestricted_authorizer(self) -> None:
        """The ``mode=ro`` fast path must survive: it is how all 12 real call sites connect.

        A ``mode=ro`` handle cannot write, so no authorizer is installed — which is observable,
        because the authorizer's allow-list has no ``CREATE_TEMP_TABLE`` in it. If the fast
        path were dropped this would start raising ``not authorized`` instead of the
        ``readonly database`` error SQLite itself produces, silently changing behaviour for
        ``test_command_sql`` and ``test_dashboard_server``.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            conn.execute("CREATE TEMP TABLE _probe (x INT)")
            conn.execute("INSERT INTO _probe (x) VALUES (1)")
            assert conn.execute("SELECT x FROM _probe").fetchone() == (1,)
        finally:
            conn.close()

    def test_an_in_memory_uri_is_not_mistaken_for_the_file_it_names(self) -> None:
        """``mode=memory`` touches no disk, so guarding it would refuse a legitimate write.

        The cache key can spell a protected path; the database is still purely in memory.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        before = sha256_file(db) if db.is_file() else None
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=memory&cache=shared", uri=True)
        try:
            conn.execute("CREATE TABLE _scratch (x INT)")
            conn.execute("INSERT INTO _scratch (x) VALUES (7)")
            conn.commit()
            assert conn.execute("SELECT x FROM _scratch").fetchone() == (7,)
        finally:
            conn.close()
        if before is not None:
            assert sha256_file(db) == before

    def test_a_setter_pragma_cannot_edit_the_live_metrics_db(self) -> None:
        """``PRAGMA`` used to be on the read-only allow-list, and it is not read-only.

        Measured on SQLite 3.50.4 under the old allow-list: ``PRAGMA user_version=1234`` was
        authorized on a "downgraded" handle, committed, and read back as 1234 from a fresh
        connection. The comment above the list claimed these actions "cannot change a database
        file"; for this one it was false, and the tamper landed with only the Layer B teardown
        diff to notice it — detection after the damage, sold as prevention.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        _require_connect_is_downgraded(str(db), uri=False)
        before = sha256_file(db)
        conn = sqlite3.connect(str(db))
        try:
            for statement in (
                "PRAGMA user_version = 1234",
                "PRAGMA application_id = 99",
                "PRAGMA journal_mode = DELETE",
            ):
                with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                    conn.execute(statement)
            # Introspection still works, or every read path in scripts/ breaks.
            assert conn.execute("PRAGMA table_info('findings')").fetchall() is not None
        finally:
            conn.close()
        assert sha256_file(db) == before

    def test_attaching_the_live_db_to_a_scratch_handle_is_refused(self, tmp_path: Path) -> None:
        """The second admitted bypass: reach protected state through an UNPROTECTED handle.

        ``sqlite3.connect(<tmp>/scratch.db)`` is not protected, so nothing downgrades it — and
        ``ATTACH '<repo>/metrics/evaluation.db'`` then writes through the attached name with no
        authorizer in the way. Closing it needs an authorizer on *every* connection, which is why
        one is installed even on scratch databases.

        The handle is a real tmp_path file, deliberately, not ``":memory:"``: an in-memory
        connection takes a different branch of ``_resolve_database`` and would prove nothing
        about the attach seam.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        _require_attach_is_refused(db)
        before = sha256_file(db)
        conn = sqlite3.connect(str(tmp_path / "scratch.db"))
        try:
            with pytest.raises(sqlite3.DatabaseError, match="not authorized"):
                conn.execute(f"ATTACH DATABASE '{db.as_posix()}' AS live")
        finally:
            conn.close()
        assert sha256_file(db) == before

    def test_an_in_memory_connection_is_not_treated_as_a_repo_root_file(self) -> None:
        """``":memory:"`` names no file, but ``abspath`` makes it look like a repo-root child.

        With pytest's cwd at the repo root, ``os.path.abspath(":memory:")`` is
        ``<root>/:memory:`` — a direct child of the root, i.e. a "violation" — so the seam
        installed the READ-ONLY authorizer on ordinary in-memory databases and ``CREATE TABLE``
        raised ``not authorized``. Nothing in this suite happened to do that, which is precisely
        how such a trap survives long enough to reach a derived project.
        """
        conn = sqlite3.connect(":memory:")
        try:
            conn.execute("CREATE TABLE t (x INT)")
            conn.execute("INSERT INTO t VALUES (1)")
            assert conn.execute("SELECT x FROM t").fetchone() == (1,)
        finally:
            conn.close()

    def test_an_unprotected_handle_is_otherwise_unrestricted(self, tmp_path: Path) -> None:
        """The negative control for the universal authorizer: scratch work must stay free.

        If authorizing every connection made ordinary tmp_path databases behave like protected
        ones, ~2 300 tests would be paying for the ATTACH hole. They must not notice it at all.
        """
        scratch = tmp_path / "scratch.db"
        other = tmp_path / "other.db"
        conn = sqlite3.connect(str(other))
        conn.execute("CREATE TABLE t (x INT)")
        conn.commit()
        conn.close()
        conn = sqlite3.connect(str(scratch))
        try:
            conn.execute("CREATE TABLE a (x INT)")
            conn.execute("INSERT INTO a VALUES (1)")
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute(f"ATTACH DATABASE '{other.as_posix()}' AS other")
            conn.execute("INSERT INTO other.t VALUES (2)")
            conn.commit()
            assert conn.execute("SELECT x FROM other.t").fetchone() == (2,)
        finally:
            conn.close()

    def test_moving_a_sealed_record_out_of_layer1_is_refused(self, tmp_path: Path) -> None:
        """Destroying a record by MOVING it is destroying it.

        The two-target wrappers checked only the destination, so ``os.rename(<sealed>, /tmp/x)``
        passed Layer A with an innocent destination — and ``discussions/`` is deliberately absent
        from the per-test cheap walk, so Layer B did not cover it either.
        """
        from conftest import ProductionWriteBlocked

        sealed = _find_real_sealed_record()
        _require_refusal_is_armed(sealed)
        before = sha256_file(sealed)
        with pytest.raises(ProductionWriteBlocked) as excinfo:
            os.rename(sealed, tmp_path / "carried_off.jsonl")
        assert "source" in str(excinfo.value)
        assert sealed.is_file()
        assert sha256_file(sealed) == before
        assert not (tmp_path / "carried_off.jsonl").exists()

    def test_hard_linking_a_sealed_record_out_of_layer1_is_refused(self, tmp_path: Path) -> None:
        """A hard link is an alias, and an alias LAUNDERS the file past the whole guard.

        Every wrapper judges the path it was handed. Give a protected file a second name under
        ``tmp_path`` and ``open(<that name>, "w")`` truncates the sealed record with nothing to
        refuse it. This is a measured incident, not a hypothetical: on 2026-08-08 a test in THIS
        class linked a real sealed record into ``tmp_path`` on the theory that link creation is
        harmless, and pytest's own tmp_path garbage collection chmod'd the link in order to
        delete it — clearing the read-only seal on ``DISC-20260313-210858``'s ``events.jsonl``
        at the other end. Content survived byte-identical and the seal was restored by hand;
        the rule changed so it cannot happen twice.
        """
        from conftest import ProductionWriteBlocked

        sealed = _find_real_sealed_record()
        _require_refusal_is_armed(sealed)
        before = sha256_file(sealed)
        with pytest.raises(ProductionWriteBlocked) as excinfo:
            os.link(sealed, tmp_path / "alias.jsonl")
        assert "source" in str(excinfo.value)
        assert not (tmp_path / "alias.jsonl").exists()
        assert not os.access(sealed, os.W_OK), "the record must still be sealed"
        assert sha256_file(sealed) == before

    def test_linking_within_scratch_space_is_untouched(self, tmp_path: Path) -> None:
        """The negative control: aliasing is only refused when it launders PROTECTED state.

        Ordinary scratch work must keep working, or the rule above is just a tax on fixtures.
        """
        source = tmp_path / "source.txt"
        source.write_text("scratch\n", encoding="utf-8")
        try:
            os.link(source, tmp_path / "alias.txt")
        except OSError as exc:  # pragma: no cover — unsupported filesystem
            pytest.skip(f"os.link unavailable here: {type(exc).__name__}")
        assert (tmp_path / "alias.txt").read_text(encoding="utf-8") == "scratch\n"

    def test_the_live_assertion_substrate_is_fingerprinted(self) -> None:
        """``data/`` is watched by Layer B even though Layer A does not refuse it.

        The old ``data`` entry in ``_ROOT_ALLOW_NAMES`` was defended as covering the substrate;
        it never did. That list governs only direct children of the repo root, and
        ``data/memory.db``'s parent is ``<root>/data`` — so the live 1.6 MB ADR-0014 substrate
        was invisible to Layer B AND unrefused by Layer A at the same time. Watching the tree is
        the half that can be fixed from this file, and it is what this test pins.
        """
        from conftest import _WATCHED_TREES, _deep_fingerprint

        assert "data" in _WATCHED_TREES
        substrate = REPO_ROOT / "data" / "memory.db"
        if not substrate.is_file():
            pytest.skip("no data/memory.db in this checkout")
        # normcase both sides: this module's REPO_ROOT is unresolved while conftest's
        # PROJECT_ROOT is `.resolve()`d, and on Windows those can differ in case alone. Comparing
        # them raw made this test pass here and fail in a scratch mirror — the same bug class the
        # write ledger had, which is why it is normalized rather than hoped about.
        fingerprinted = {os.path.normcase(p) for p in _deep_fingerprint()}
        assert os.path.normcase(str(substrate.resolve())) in fingerprinted

    def test_the_substrate_directory_can_still_be_created_on_a_fresh_clone(
        self, tmp_path: Path
    ) -> None:
        """...and the reason ``data`` stays in the root allow-list, stated as a check.

        ``data/`` is untracked and gitignored, so every fresh clone and every derived project
        starts without it and ``assertion_store.substrate`` creates it with
        ``parent.mkdir(parents=True, exist_ok=True)``. Refusing that was measured to turn
        ``test_mcp_server.py::TestThreadLocalIsolation`` red. Separately, a ``mkdir`` of a
        directory that ALREADY exists changes nothing and must never be refused.
        """
        from conftest import _ROOT_ALLOW_NAMES

        assert "data" in _ROOT_ALLOW_NAMES
        # The idempotent form must pass straight through, on protected ground and off it.
        (REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / "discussions").mkdir(parents=True, exist_ok=True)
        (tmp_path / "fresh").mkdir()
        assert (tmp_path / "fresh").is_dir()

    def test_creating_a_new_directory_in_a_protected_tree_is_still_refused(self) -> None:
        """The mkdir relaxation is about no-ops only — a real directory creation still fails."""
        from conftest import ProductionWriteBlocked

        target = REPO_ROOT / "discussions" / "2099-01-01"
        assert not target.exists()
        _require_refusal_is_armed(target)
        with pytest.raises(ProductionWriteBlocked):
            target.mkdir(parents=True, exist_ok=True)
        assert not target.exists()

    def test_tmp_path_is_untouched_by_the_guard(self, tmp_path: Path) -> None:
        """The boundary must not make scratch work harder, or it will be worked around."""
        scratch = tmp_path / "nested" / "artifact.jsonl"
        scratch.parent.mkdir(parents=True)
        scratch.write_text('{"ok": true}\n', encoding="utf-8")
        conn = sqlite3.connect(str(tmp_path / "db.sqlite"))
        try:
            conn.execute("CREATE TABLE t (x INT)")
            conn.commit()
        finally:
            conn.close()
        assert scratch.read_text(encoding="utf-8") == '{"ok": true}\n'
        assert (tmp_path / "db.sqlite").stat().st_size > 0


class TestTheArmingPreconditionHolds:
    """The preconditions above are the difference between a regression test and a loaded weapon.

    Two things have to be true of them, and neither is self-evident:

    * **Coverage** — every probe in :class:`TestProductionWriteGuard` that names a real production
      path either arms first or is *declared* to mutate nothing. A new probe added without either
      is the exact regression this class exists to prevent, and it would otherwise be invisible
      until the day someone disabled the guard.
    * **Non-vacuity** — the arming check must actually refuse. A precondition that passes
      unconditionally reads like safety and provides none, which is the failure mode the whole
      slice is about.
    """

    @staticmethod
    def _probe_sources() -> dict[str, str]:
        return {
            name: inspect.getsource(member)
            for name, member in vars(TestProductionWriteGuard).items()
            if name.startswith("test_") and callable(member)
        }

    def test_every_probe_naming_a_production_path_arms_or_is_declared_read_only(self) -> None:
        sources = self._probe_sources()
        assert len(sources) > 10, "census found almost no probes — the reflection above is broken"
        unarmed = sorted(
            name
            for name, source in sources.items()
            if ("REPO_ROOT" in source or "_find_real_sealed_record(" in source)
            and name not in _READ_ONLY_PRODUCTION_PROBES
            and not any(helper in source for helper in _ARMING_HELPERS)
        )
        assert not unarmed, (
            "these probes aim at a real production path without first proving the boundary is "
            f"armed for it: {unarmed}. Call one of {list(_ARMING_HELPERS)} before the write, or "
            "add the probe to _READ_ONLY_PRODUCTION_PROBES with the reason it mutates nothing."
        )

    def test_the_read_only_declarations_have_not_rotted(self) -> None:
        """A declaration that names a deleted test silently widens the exemption."""
        stale = sorted(_READ_ONLY_PRODUCTION_PROBES - set(self._probe_sources()))
        assert not stale, f"_READ_ONLY_PRODUCTION_PROBES names tests that no longer exist: {stale}"

    def test_the_arming_check_refuses_to_fire_when_layer_a_is_off(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Disable one seam and the precondition must FAIL — before any write is attempted.

        This is the mutation the critic measured: ``_install_write_guard`` stubbed to ``pass``,
        the class re-run, and all three 2026-08-07 contaminations re-committed against live state.
        Restoring a single primitive models it without leaving the process unguarded for longer
        than this assertion (``monkeypatch`` undoes it at teardown, and nothing here writes).
        """
        conftest = _guard_module()
        assert conftest._guard_installed(), "the guard must be armed at the start of this test"
        monkeypatch.setattr(builtins, "open", conftest._PRISTINE_PRIMITIVES["builtins.open"])
        assert "builtins.open" in conftest._unguarded_primitives()
        assert not conftest._guard_installed()
        with pytest.raises(pytest.fail.Exception) as excinfo:
            _require_refusal_is_armed(REPO_ROOT / "CLAUDE.md")
        assert "NOT installed" in str(excinfo.value)
        assert (REPO_ROOT / "CLAUDE.md").is_file()

    def test_the_arming_check_refuses_a_target_outside_the_protected_set(
        self, tmp_path: Path
    ) -> None:
        """Membership is checked per TARGET, not once for the tree — a narrowed set must fail."""
        with pytest.raises(pytest.fail.Exception) as excinfo:
            _require_refusal_is_armed(tmp_path / "not_production.txt")
        assert "not in the guard's protected set" in str(excinfo.value)

    def test_the_connect_precondition_rejects_a_handle_that_would_not_be_downgraded(self) -> None:
        """A ``mode=ro`` spelling gets no authorizer, so a probe using one proves nothing.

        The precondition has to notice that, or it would bless a probe whose "refusal" was really
        SQLite's own ``readonly database`` error — and the authorizer could be gone entirely.
        """
        db = REPO_ROOT / "metrics" / "evaluation.db"
        if not db.is_file():
            pytest.skip("no metrics/evaluation.db in this checkout")
        with pytest.raises(pytest.fail.Exception) as excinfo:
            _require_connect_is_downgraded(f"file:{db.as_posix()}?mode=ro", uri=True)
        assert "writable handle on protected state" in str(excinfo.value)

    def test_the_attach_precondition_rejects_an_unprotected_target(self, tmp_path: Path) -> None:
        """The ATTACH authorizer allows scratch files by design; arming on one would be vacuous."""
        with pytest.raises(pytest.fail.Exception) as excinfo:
            _require_attach_is_refused(tmp_path / "scratch.db")
        assert "does not deny ATTACH" in str(excinfo.value)


class TestTheBeaconMatchesTheShippedHook:
    """The attribution rule reads a file the Stop hook writes. Pin that, or it rots silently.

    ``_classify_drift`` downgrades unattributed drift to a warning on the strength of one
    timestamp. If ``scripts/stop_hook.py`` moves or renames its throttle stamp, the beacon goes
    permanently cold — which fails SAFE (nothing is ever excused, the F1 flake returns) but fails
    *silently*, and a silent return to a 1-in-4 flake is exactly how this got shipped once.
    """

    def test_the_beacon_path_is_the_hooks_own_throttle_stamp(self) -> None:
        import stop_hook
        from conftest import _TELEMETRY_BEACON

        assert Path(stop_hook.TELEMETRY_STATE_FILE) == _TELEMETRY_BEACON

    def test_the_hook_stamps_before_it_spawns_the_writer(self) -> None:
        """The beacon is only usable because the stamp is EAGER.

        A stamp written *after* the instrument finished would land after the bytes it is meant to
        explain, and the ``mtime >= beacon`` condition would reject every real case.
        """
        source = (REPO_ROOT / "scripts" / "stop_hook.py").read_text(encoding="utf-8")
        body = source.split("def _run_telemetry_kick", 1)[1]
        stamp_at = body.index("os.replace(tmp, TELEMETRY_STATE_FILE)")
        spawn_at = body.index("subprocess.run(")
        assert stamp_at < spawn_at, "the throttle stamp must be written before the writer runs"

    def test_the_grace_window_covers_the_hooks_own_budget(self) -> None:
        """The 30 s window is not a guess — it doubles the hook's declared subprocess budget."""
        import stop_hook
        from conftest import _WRITER_BUDGET_SECONDS

        assert _WRITER_BUDGET_SECONDS >= stop_hook.TELEMETRY_BUDGET_SECONDS


class TestTheGuardActuallyFailsARun:
    """Proof the guard can go RED — run against a scratch repo, never this one.

    A guard is only worth its runtime if a violation turns a run red, and that cannot be
    demonstrated in-process (the whole point is that the write never happens). So a faithful
    copy of ``tests/conftest.py`` is stood up over a throwaway repo-shaped tree and a
    deliberately-bad test is run under it. ``PROJECT_ROOT`` is derived from the conftest's own
    location, so the copy polices the SCRATCH tree — this repository is never at risk.
    """

    @staticmethod
    def _beacon(root: Path, when: float) -> Path:
        """Stamp the scratch repo's declared-concurrent-writer beacon, as the Stop hook does.

        The hook writes ``str(int(time.time()))`` EAGERLY, before spawning the writer. Modelling
        it here is what makes the F1 attribution rule testable in isolation rather than only
        observable by waiting for a real agent turn to end mid-run.
        """
        stamp = root / ".claude" / "hooks" / ".state" / "telemetry-last-attempt"
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(when)), encoding="utf-8")
        return stamp

    @staticmethod
    def _scratch_repo(tmp_path: Path) -> Path:
        root = tmp_path / "scratch_repo"
        (root / "tests").mkdir(parents=True)
        (root / "scripts").mkdir()
        shutil.copy2(REPO_ROOT / "tests" / "conftest.py", root / "tests" / "conftest.py")
        for name in ("__init__.py", "collab_loop.py", "notify.py"):
            shutil.copy2(REPO_ROOT / "scripts" / name, root / "scripts" / name)
        sealed = root / "discussions" / "2026-08-07" / "DISC-scratch"
        sealed.mkdir(parents=True)
        (sealed / "events.jsonl").write_text('{"event": "sealed"}\n', encoding="utf-8")
        (root / "metrics").mkdir()
        # `data/` is WATCHED by Layer B but not refused by Layer A — the one surface where a
        # write is allowed to land and attribution alone decides who is blamed for it.
        (root / "data").mkdir()
        (root / "data" / "memory.db").write_text("substrate\n", encoding="utf-8")
        # A WAL-mode Layer 2 DB, matching the real one (measured: `PRAGMA journal_mode` on
        # metrics/evaluation.db returns `wal`). Journal mode is the whole subject of the
        # uncheckpointed-write test below, so the scratch twin must not be left in `delete`.
        conn = sqlite3.connect(str(root / "metrics" / "evaluation.db"))
        try:
            assert conn.execute("PRAGMA journal_mode=WAL").fetchone() == ("wal",)
            conn.execute("CREATE TABLE findings (id INTEGER PRIMARY KEY, note TEXT)")
            conn.execute("INSERT INTO findings (id, note) VALUES (1, 'clean')")
            conn.commit()
        finally:
            conn.close()
        return root

    @staticmethod
    def _scratch_note(root: Path) -> str | None:
        """Read ``findings.note`` out of the scratch DB without perturbing its WAL."""
        db = root / "metrics" / "evaluation.db"
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT note FROM findings WHERE id = 1").fetchone()
            return None if row is None else str(row[0])
        finally:
            conn.close()

    @staticmethod
    def _run(
        root: Path, body: str, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        """Write ``test_probe.py`` (plus any ``extra`` test modules) and run pytest over them.

        ``extra`` exists so a contaminating probe can be run ALONGSIDE unrelated clean tests,
        which is the property the guard has to have and the one a scratch mirror of the whole
        suite cannot demonstrate cleanly (a partial mirror fails for mirror-fidelity reasons
        that have nothing to do with the guard).
        """
        (root / "tests" / "test_probe.py").write_text(body, encoding="utf-8")
        for name, source in (extra or {}).items():
            (root / "tests" / name).write_text(source, encoding="utf-8")
        return subprocess.run(
            [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:randomly"],
            cwd=root,
            capture_output=True,
            text=True,
        )

    _GOOD = (
        "from pathlib import Path\n"
        "def test_writes_only_to_tmp(tmp_path: Path) -> None:\n"
        "    (tmp_path / 'ok.txt').write_text('fine', encoding='utf-8')\n"
        "    assert (tmp_path / 'ok.txt').read_text(encoding='utf-8') == 'fine'\n"
    )

    def test_a_clean_test_is_green_under_the_guard(self, tmp_path: Path) -> None:
        """The negative control. Without it, every 'red' below proves nothing."""
        result = self._run(self._scratch_repo(tmp_path), self._GOOD)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout

    def test_truncating_a_sealed_record_turns_the_run_red(self, tmp_path: Path) -> None:
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "def test_truncates_layer1() -> None:\n"
            "    target = ROOT / 'discussions' / '2026-08-07' / 'DISC-scratch' / 'events.jsonl'\n"
            "    target.write_text('', encoding='utf-8')\n",
        )
        assert result.returncode != 0, result.stdout
        assert "ProductionWriteBlocked" in result.stdout
        victim = root / "discussions" / "2026-08-07" / "DISC-scratch" / "events.jsonl"
        assert victim.read_text(encoding="utf-8") == '{"event": "sealed"}\n'

    def test_dropping_a_file_in_the_repo_root_turns_the_run_red(self, tmp_path: Path) -> None:
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "def test_drops_a_probe_lock() -> None:\n"
            "    (ROOT / 'probe.lock').write_text('{}', encoding='utf-8')\n",
        )
        assert result.returncode != 0, result.stdout
        assert "ProductionWriteBlocked" in result.stdout
        assert not (root / "probe.lock").exists()

    def test_a_subprocess_write_turns_the_run_red(self, tmp_path: Path) -> None:
        """Layer B: an in-process wrapper cannot see a child process; the fingerprint can."""
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "import subprocess, sys\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "TARGET = ROOT / 'discussions' / '2026-08-07' / 'DISC-scratch' / 'events.jsonl'\n"
            "def test_child_writes_layer1() -> None:\n"
            '    code = \'open(r"\' + str(TARGET) + \'", "w").write("")\'\n'
            "    assert subprocess.run([sys.executable, '-c', code]).returncode == 0\n",
        )
        assert result.returncode != 0, result.stdout
        assert "live production state changed while this test ran" in result.stdout

    def test_a_uri_write_to_the_metrics_db_turns_the_run_red(self, tmp_path: Path) -> None:
        """Layer A, URI form. Before the fix this probe printed ``1 passed`` and exited 0.

        The database is checked afterwards, not just the exit code: a run that goes red for
        some *other* reason while the tamper still lands would be no fix at all.
        """
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "import sqlite3\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "def test_uri_rw_write() -> None:\n"
            "    uri = 'file:' + (ROOT / 'metrics' / 'evaluation.db').as_posix() + '?mode=rw'\n"
            "    conn = sqlite3.connect(uri, uri=True)\n"
            "    conn.execute(\"UPDATE findings SET note='TAMPERED_IN_PROCESS'\")\n"
            "    conn.commit()\n",
        )
        assert result.returncode != 0, result.stdout
        assert "not authorized" in result.stdout, result.stdout
        assert self._scratch_note(root) == "clean"

    def test_an_uncheckpointed_child_write_turns_the_run_red(self, tmp_path: Path) -> None:
        """Layer B, WAL form. A committed write that is never checkpointed into the ``.db``.

        The child calls ``os._exit`` so SQLite never runs its close-time checkpoint, modelling
        a killed or timed-out subprocess. The ``.db`` file's mtime and size are then *identical*
        while the database content is durably changed, so every fingerprint that skipped the
        ``-wal`` reported a clean pass over a tampered Layer 2 (measured: exit 0, ``1 passed``).
        Layer A cannot see a child process, so this fingerprint is the only defence.
        """
        root = self._scratch_repo(tmp_path)
        db = root / "metrics" / "evaluation.db"
        before = db.stat()
        result = self._run(
            root,
            "import subprocess, sys\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "DB = ROOT / 'metrics' / 'evaluation.db'\n"
            "CHILD = (\n"
            "    'import sqlite3, os\\n'\n"
            "    'c = sqlite3.connect(r\"' + str(DB) + '\")\\n'\n"
            "    'c.execute(\"PRAGMA journal_mode=WAL\")\\n'\n"
            "    'c.execute(\"UPDATE findings SET note=\\'TAMPERED\\'\")\\n'\n"
            "    'c.commit()\\n'\n"
            "    'os._exit(0)\\n'\n"
            ")\n"
            "def test_child_writes_without_checkpointing() -> None:\n"
            "    done = subprocess.run([sys.executable, '-c', CHILD], capture_output=True)\n"
            "    assert done.returncode == 0, done.stderr\n",
        )
        # The premise: the write really did land, and really was invisible in the .db file.
        assert self._scratch_note(root) == "TAMPERED"
        after = db.stat()
        assert (after.st_mtime_ns, after.st_size) == (before.st_mtime_ns, before.st_size)
        assert result.returncode != 0, result.stdout
        assert "live production state changed while this test ran" in result.stdout
        assert "evaluation.db-wal" in result.stdout, result.stdout

    def test_an_empty_wal_sidecar_does_not_turn_the_run_red(self, tmp_path: Path) -> None:
        """The negative control for the WAL fingerprint, and the reason it is size-aware.

        Opening a WAL database creates a zero-length ``-wal`` and closing the last connection
        checkpoints it away again — ordinary SQLite housekeeping a read-only test performs.
        Recording ``-wal`` naively would report that as contamination; recording it only when
        it carries frames makes "absent" and "empty" the same fingerprint.
        """
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "import sqlite3\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "DB = ROOT / 'metrics' / 'evaluation.db'\n"
            "def test_read_only_open_and_close() -> None:\n"
            "    conn = sqlite3.connect('file:' + DB.as_posix() + '?mode=ro', uri=True)\n"
            "    assert conn.execute('SELECT note FROM findings').fetchone() == ('clean',)\n"
            "    conn.close()\n",
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout

    def test_a_collection_time_write_is_refused_and_names_its_module(self, tmp_path: Path) -> None:
        """A module-level write runs before any fixture — so Layer A is installed session-wide.

        This used to be the "unattributable" case: the write landed, every test passed, and the
        session backstop reported an anonymous drift hours later. Refusing it at collection is
        strictly better — the record survives, and the error names the module that did it.

        It is also the MOVE form of the flagship incident (``os.rename`` out of ``discussions/``),
        which the destination-only wrappers used to wave through.
        """
        root = self._scratch_repo(tmp_path)
        result = self._run(
            root,
            "import os\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "SEALED = ROOT / 'discussions' / '2026-08-07' / 'DISC-scratch'\n"
            "os.rename(SEALED / 'events.jsonl', SEALED / 'moved.jsonl')\n"
            "def test_nothing() -> None:\n"
            "    assert True\n",
        )
        assert result.returncode != 0, result.stdout
        assert "ProductionWriteBlocked" in result.stdout
        assert "test_probe.py" in result.stdout, "the offending module must be named"
        victim = root / "discussions" / "2026-08-07" / "DISC-scratch" / "events.jsonl"
        assert victim.read_text(encoding="utf-8") == '{"event": "sealed"}\n'
        assert not (victim.parent / "moved.jsonl").exists()

    def test_a_write_after_the_last_teardown_still_fails_the_session(self, tmp_path: Path) -> None:
        """Layer B's backstop: a detached child that lands its write once the test is over.

        No per-test window contains it and no beacon explains it, so the only thing left that can
        report it is ``pytest_sessionfinish`` — which must go red rather than report a clean pass
        over a mutated tree, even though it cannot name a culprit.
        """
        root = self._scratch_repo(tmp_path)
        # A SESSION-scoped fixture tears down after every function-scoped one, so this write lands
        # after the last per-test window closes and before `pytest_sessionfinish` runs — the exact
        # gap the backstop exists for. Deterministic, unlike sleeping a detached child and hoping.
        result = self._run(
            root,
            "import subprocess, sys\n"
            "import pytest\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "TARGET = ROOT / 'discussions' / '2026-08-07' / 'DISC-scratch' / 'events.jsonl'\n"
            "@pytest.fixture(scope='session', autouse=True)\n"
            "def _late_writer():\n"
            "    yield\n"
            '    code = \'open(r"\' + str(TARGET) + \'", "a").write("late\\\\n")\'\n'
            "    subprocess.run([sys.executable, '-c', code], check=True)\n"
            "def test_nothing() -> None:\n"
            "    assert True\n",
        )
        assert result.returncode != 0, result.stdout
        assert "PRODUCTION STATE CONTAMINATED BY THE TEST SUITE" in result.stdout
        assert "1 passed" in result.stdout, "every test passed; only the session guard went red"

    # ----------------------------------------------------------------------- #
    # Attribution: the guard must not red the gate for somebody else's write.
    # ----------------------------------------------------------------------- #
    _FOREIGN_WRITER = (
        "import subprocess, sys, time\n"
        "from pathlib import Path\n"
        "ROOT = Path(__file__).resolve().parent.parent\n"
        "LOG = ROOT / 'metrics' / 'model_call_log.jsonl'\n"
        "def test_sleeps_while_something_else_writes() -> None:\n"
        "    # Started here only because a scratch repo has no agent harness to end a turn.\n"
        "    # It is foreign to the RUN in the way that matters: the suite never writes LOG,\n"
        "    # so the write appears in no ledger.\n"
        "    code = 'import time; time.sleep(1); "
        'open(r"\' + str(LOG) + \'", "a").write(chr(123) + chr(125) + chr(10))\'\n'
        "    child = subprocess.Popen([sys.executable, '-c', code])\n"
        "    child.wait()\n"
    )

    def test_the_frameworks_own_telemetry_write_does_not_red_the_run(self, tmp_path: Path) -> None:
        """F1, the whole reason attribution exists.

        Measured 2026-08-08 in THIS repository: the shipped ``Stop`` hook stamped its throttle
        file at 10:28:42 and wrote ``metrics/evaluation.db`` + ``metrics/model_call_log.jsonl``
        0.819 s later, mid-run, and the guard failed
        ``test_a_subprocess_write_turns_the_run_red`` — a test that had touched only ``tmp_path``.
        Every derived project inherits that hook, so this is not a local quirk. With the beacon
        stamped, the same drift must be reported and NOT failed.
        """
        root = self._scratch_repo(tmp_path)
        (root / "metrics" / "model_call_log.jsonl").write_text("{}\n", encoding="utf-8")
        self._beacon(root, time.time())
        result = self._run(root, self._FOREIGN_WRITER)
        assert result.returncode == 0, result.stdout + result.stderr
        assert "1 passed" in result.stdout
        assert "EXTERNAL DRIFT" in result.stdout, "silence is not acceptable either"
        assert "model_call_log.jsonl" in result.stdout

    def test_without_a_beacon_the_same_write_still_reds_the_run(self, tmp_path: Path) -> None:
        """The negative control that keeps the escape hatch honest.

        Identical drift, identical ledger — the ONLY difference is that no declared writer
        announced itself. If this went green the mechanism would be a blanket exemption for
        ``metrics/`` wearing an evidence costume.
        """
        root = self._scratch_repo(tmp_path)
        (root / "metrics" / "model_call_log.jsonl").write_text("{}\n", encoding="utf-8")
        assert not (root / ".claude").exists(), "no beacon in this scratch repo"
        result = self._run(root, self._FOREIGN_WRITER)
        assert result.returncode != 0, result.stdout
        assert "live production state changed while this test ran" in result.stdout
        assert "no declared concurrent writer has ever announced itself" in result.stdout

    def test_a_stale_beacon_does_not_excuse_a_write(self, tmp_path: Path) -> None:
        """The beacon is a window, not a permanent pass. An old stamp explains nothing."""
        root = self._scratch_repo(tmp_path)
        (root / "metrics" / "model_call_log.jsonl").write_text("{}\n", encoding="utf-8")
        self._beacon(root, time.time() - 3600)
        result = self._run(root, self._FOREIGN_WRITER)
        assert result.returncode != 0, result.stdout
        assert "outside this window" in result.stdout, result.stdout

    def test_a_truncation_is_never_excused_by_a_beacon(self, tmp_path: Path) -> None:
        """Incident #1 replayed inside a live beacon window: shrinking is always ours.

        The declared writer appends rows and log lines. It does not truncate, so a file that got
        SMALLER cannot be its work no matter how recently it announced itself. Without this rule
        the 30 s window after every telemetry stamp would be an open season on Layer 2.
        """
        root = self._scratch_repo(tmp_path)
        log = root / "metrics" / "model_call_log.jsonl"
        log.write_text("{}\n" * 200, encoding="utf-8")
        self._beacon(root, time.time())
        result = self._run(
            root,
            "import subprocess, sys\n"
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "LOG = ROOT / 'metrics' / 'model_call_log.jsonl'\n"
            "def test_child_truncates() -> None:\n"
            '    code = \'open(r"\' + str(LOG) + \'", "w").write("")\'\n'
            "    assert subprocess.run([sys.executable, '-c', code]).returncode == 0\n",
        )
        assert result.returncode != 0, result.stdout
        assert "SHRANK" in result.stdout, result.stdout

    def test_the_ledger_beats_the_beacon(self, tmp_path: Path) -> None:
        """Positive proof of authorship outranks every excuse.

        Aimed at ``data/``, which Layer A does NOT refuse, so the write really lands and the only
        thing standing between "this test did it" and "somebody else did it" is the write ledger.
        The beacon is as fresh as it can be and the file GREW, so every other condition in
        ``_classify_drift`` votes "external" — and the run must still go red, naming this test.
        """
        root = self._scratch_repo(tmp_path)
        self._beacon(root, time.time())
        result = self._run(
            root,
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "def test_appends_to_the_watched_substrate() -> None:\n"
            "    with open(ROOT / 'data' / 'memory.db', 'a', encoding='utf-8') as handle:\n"
            "        handle.write('appended\\n')\n",
        )
        assert result.returncode != 0, result.stdout
        assert "live production state changed while this test ran" in result.stdout
        assert "this test wrote" in result.stdout, result.stdout
        assert "EXTERNAL DRIFT" not in result.stdout

    def test_one_bad_test_does_not_take_the_clean_ones_with_it(self, tmp_path: Path) -> None:
        """The property the whole slice is judged on: contamination is caught, in isolation.

        A guard that reds the run is only half the answer — if it also breaks the tests around it
        nobody can tell a real finding from collateral damage, and the first response is to switch
        it off. So: four unrelated tests that write only to ``tmp_path``, plus one that truncates a
        sealed Layer 1 record. Exactly one must fail, and the record must survive.
        """
        root = self._scratch_repo(tmp_path)
        clean = "".join(
            f"def test_clean_{i}(tmp_path):\n"
            f"    p = tmp_path / 'f{i}.txt'\n"
            f"    p.write_text('{i}', encoding='utf-8')\n"
            f"    assert p.read_text(encoding='utf-8') == '{i}'\n\n"
            for i in range(4)
        )
        result = self._run(
            root,
            "from pathlib import Path\n"
            "ROOT = Path(__file__).resolve().parent.parent\n"
            "def test_truncates_layer1() -> None:\n"
            "    t = ROOT / 'discussions' / '2026-08-07' / 'DISC-scratch' / 'events.jsonl'\n"
            "    t.write_text('', encoding='utf-8')\n",
            extra={"test_unrelated.py": clean},
        )
        assert result.returncode != 0, result.stdout
        assert "1 failed, 4 passed" in result.stdout, result.stdout
        assert "ProductionWriteBlocked" in result.stdout
        victim = root / "discussions" / "2026-08-07" / "DISC-scratch" / "events.jsonl"
        assert victim.read_text(encoding="utf-8") == '{"event": "sealed"}\n'
