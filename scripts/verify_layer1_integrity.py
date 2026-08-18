"""Layer 1 integrity: record a digest when a discussion is sealed, and detect any
later change to a sealed record — regardless of HOW the change was made.

WHY THIS EXISTS
    On 2026-08-07 a subagent truncated ``discussions/2026-08-07/
    DISC-20260807-063650-.../events.jsonl`` to 0 bytes. The file was already
    read-only on disk. Nothing objected, and nothing could answer the only
    question that matters afterwards: *has the record been altered?*

    The previous answer was a PreToolUse guard that reads the text of shell
    commands and refuses destructive-looking shapes. Three review rounds found
    three successive bypasses in it (shell grouping, ``&&``/``;`` chaining,
    ``bash -lc``, mis-parsed ``robocopy`` destinations, opaque SQL spellings).
    That is not an enumeration gap that one more verb closes: predicting what a
    shell command will do by parsing its text is unwinnable. So this module is
    deliberately a **detective** control, not a preventive one. It never tries
    to guess intent. It compares bytes.

    Consequence: it detects truncation, in-place edit, deletion, re-encoding,
    re-generation, and corruption identically, whether the change arrived via
    ``rm``, an editor, a Python script, a git operation, a background process,
    or a subagent nobody was watching. That is the property command-text
    matching cannot have at any level of effort.

WHERE THE DIGESTS LIVE, AND WHY
    ``metrics/layer1_manifest.jsonl`` — a repo-level, append-only JSONL manifest,
    one line per sealed file.

    Rejected: a per-discussion sidecar (e.g. ``discussions/<id>/.sha256``). It
    lives inside the directory it guards, so the same careless ``rm -rf``,
    ``git checkout``, or regeneration that damages the record updates or removes
    its own witness. A witness you can edit in the same gesture as the evidence
    is not a witness.

    Rejected as the *sole* store: a column on the sealed row in
    ``metrics/evaluation.db``. Measured on this repo: ``.gitignore:13`` matches
    ``*.db``, so ``metrics/evaluation.db`` is NOT tracked by git. Digests kept
    only there would have no independent history to compare against, and the DB
    is binary — a change to it is invisible in review. (Recording there *as well*
    is a reasonable future addition; it is not a substitute.)

    The manifest is git-tracked (measured: ``git check-ignore`` does not match
    it), so every append is visible in ``git diff`` as a plain-text line, and
    ``git log -p metrics/layer1_manifest.jsonl`` is a second, independent
    history of the same claims.

    FIRST RECORD WINS. A sealed record's digest never legitimately changes, so
    ``load_manifest`` keys on path and keeps the *earliest* line. There is no
    CLI path that overwrites or removes a manifest line — ``--baseline`` only
    appends for paths not already present. Appending a second, differing line
    for a path is therefore not a re-blessing: it is reported as a CONFLICT and
    counts as CHANGED.

RESIDUAL RISK — READ THIS BEFORE TRUSTING IT
    There is no perfect answer without a store outside this machine, and
    pretending otherwise would repeat the defect this work exists to remove.

    1. An actor with write access to the working tree can edit a sealed record
       *and* hand-edit its manifest line in place, and this check will then
       report VERIFIED. The cost of that is two coordinated edits in two
       directories instead of one, and the manifest edit appears in
       ``git diff`` as a modified tracked line — but the check itself cannot
       see it.
    2. An actor who also rewrites git history defeats the git corroboration
       described below. Nothing local survives that.
    3. Detection is not prevention. This tells you a record changed; it does not
       stop the change and cannot recover the original bytes. Recovery depends
       on git history or a backup.
    4. Anything sealed before it was ever baselined is baselined *as it is now*.
       Baselining freezes a file; it does not certify that the file was ever
       correct. See "SUSPECT" below — this module refuses to let that
       distinction be silent.

    What removes 1 and 2 is a manifest copy that this machine cannot write:
    a signed tag, a push to a remote, or an append to an external log. That is
    out of scope here and is named as a gap, not quietly omitted.

WHAT IS UNDER WATCH — THE MANIFEST DECIDES, NOT THE SEAL METADATA
    A path in the manifest is under watch *because it is in the manifest*. It is
    hashed and compared no matter what the seal metadata currently says about it.

    This was got wrong once, and the way it was wrong is worth keeping written
    down. The first version enumerated only what it currently classified as
    sealed and treated every *other* manifest path as a change. But "sealed" was
    derived from two things that do not survive a checkout: a row in
    ``metrics/evaluation.db`` (measured: ``.gitignore:13`` matches ``*.db``, so
    the DB is not tracked) and the read-only bit (git does not carry it). So on
    any clone, worktree, CI runner or derived project, 236 of this repo's 278
    byte-identical sealed records were reported ``CHANGED``. Measured:
    ``verify_layer1_integrity.py --manifest <baselined> --db <absent> --no-git``
    -> ``CHANGED 236 / VERIFIED 42`` (42 = the 21 read-only directories x 2
    files), every line reading "no longer sealed". A detective control whose
    central verdict is false on every fresh checkout does not get argued with —
    it gets switched off.

    So: the sealed-set scan only decides what to *add* to the watch list
    (records that exist on disk but have never been baselined). It never decides
    what to drop, and losing the seal metadata is not evidence about bytes.

THREE STATES, NOT TWO
    A two-state check ("intact" / "not intact") has to lie about records it has
    never seen, and the lie always resolves toward "fine".

    - ``UNKNOWN``  — sealed on disk, but no manifest line. Never baselined. This
      is not a pass and not a failure; it is an absence of evidence.
    - ``VERIFIED`` — a manifest line exists and the bytes still hash to it.
    - ``CHANGED``  — a manifest line exists and the bytes no longer hash to it;
      or the file is gone from disk; or the manifest holds conflicting lines for
      it; or git says the file differs from its committed blob.

    Orthogonal to the state, a record may be **SUSPECT**: an anomaly recorded at
    baseline time that makes "VERIFIED" mean only "unchanged since we started
    watching", never "known good". Today exactly one such anomaly is detected —
    ``sealed-empty``, a discussion the DB marks closed whose ``events.jsonl`` is
    0 bytes. A closed discussion with no events cannot be right: the transcript
    is generated *from* those events. Suspect records are counted and printed
    separately and are never folded into the intact total.

    Also orthogonal, and deliberately **never fatal**: ``seal-lost`` — a manifest
    path whose bytes are present but which is no longer classified as sealed
    (no DB row, no read-only bit). That is a statement about metadata, not about
    content, and it is reported as one. It is only meaningful when the seal
    source could be consulted at all: if ``metrics/evaluation.db`` is missing or
    has no ``discussions`` table, ``seal_source_available`` is False and the
    count is expected to cover every manifest record, because neither the DB nor
    the read-only bit survives a clone. The report says which case it is rather
    than letting the number be read as damage.

GIT AS AN INDEPENDENT WITNESS (retroactive, needs no baseline)
    Measured on this repo at build time: of 140 sealed ``events.jsonl``, 136 are
    tracked in the git index and 136 of 136 hash-match their committed blob;
    0 differ; 4 are untracked (three of them created today, one of which is the
    truncated record). So a sealed file that git reports as *modified* is a
    zero-noise signal on this corpus, and it works with no manifest at all —
    it detects damage that happened before this module existed.

    - ``git-differs``      — the file has a blob in ``HEAD`` and the working tree
      or index copy differs from it. Escalates to CHANGED even when the manifest
      says VERIFIED, because it means the file was already wrong when baselined.
    - ``uncorroborated``   — the file has **no blob in HEAD**. No independent
      witness exists; the manifest is self-certifying for that path. Reported,
      never fatal.

    "Has a blob in HEAD" is asked of git directly (``git ls-tree -r HEAD --
    discussions``), not inferred from a porcelain status code. Inferring it was
    the second defect in this module's history: ``git_signal`` returned
    ``uncorroborated`` only for the exact code ``??`` and ``git-differs`` for
    everything else, so ``git add discussions`` — porcelain ``A `` — turned a
    brand-new sealed record RED with the reason "differs from its committed git
    blob" for a file that has no committed blob and matched its baseline byte for
    byte. That is precisely the window the commit-time gate runs in:
    ``check_review_existence`` reads ``git diff --cached``, so the gate is
    designed to run *after* staging.

    Git is optional. If git is missing or this is not a repository, the
    corroboration is skipped and the report says so rather than implying it ran.
    A repository with no commits yet has an empty HEAD tree, so every record
    reads ``uncorroborated`` — which is true.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DISCUSSIONS_DIRNAME = "discussions"
MANIFEST_RELPATH = "metrics/layer1_manifest.jsonl"
DB_RELPATH = "metrics/evaluation.db"

SCHEMA_VERSION = 1

#: The Layer 1 files a seal covers. ``events.jsonl`` is the canonical record;
#: ``transcript.md`` is generated from it and is covered so a mismatch between
#: the two is visible rather than inferred.
SEALED_FILENAMES = ("events.jsonl", "transcript.md")

STATE_VERIFIED = "VERIFIED"
STATE_CHANGED = "CHANGED"
STATE_UNKNOWN = "UNKNOWN"

#: Seal-time anomaly: DB says closed, but events.jsonl is 0 bytes.
SUSPECT_SEALED_EMPTY = "sealed-empty"

#: Verify-time seal-metadata signal. A manifest path whose bytes are present but
#: which is no longer classified as sealed. Metadata, not content — never fatal.
SEAL_LOST = "seal-lost"

#: Verify-time git signals (not stored in the manifest — they describe *now*).
GIT_DIFFERS = "git-differs"
GIT_UNTRACKED = "uncorroborated"

_HASH_CHUNK = 1 << 20
_GIT_TIMEOUT_SECONDS = 30


class ManifestError(Exception):
    """The manifest could not be read as an append-only record of digests.

    Raised for unreadable or malformed lines. This fails closed on purpose: a
    corrupt manifest is itself evidence worth surfacing, and silently ignoring
    bad lines would be a bypass — write garbage over the manifest and every
    record reverts to UNKNOWN.
    """


# --------------------------------------------------------------------------
# Hashing
# --------------------------------------------------------------------------


def sha256_file(path: Path) -> str:
    """Return the lowercase hex sha256 of a file's bytes.

    Args:
        path: File to hash.

    Returns:
        Hex digest string.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Manifest
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ManifestRecord:
    """One append-only manifest line: the digest of one sealed file."""

    path: str
    sha256: str
    size: int
    discussion_id: str
    recorded_at: str
    suspect: str | None
    source: str

    def to_json(self) -> str:
        """Serialize to a single JSONL line (no trailing newline)."""
        return json.dumps(
            {
                "schema": SCHEMA_VERSION,
                "path": self.path,
                "sha256": self.sha256,
                "size": self.size,
                "discussion_id": self.discussion_id,
                "recorded_at": self.recorded_at,
                "suspect": self.suspect,
                "source": self.source,
            },
            sort_keys=True,
        )


def parse_manifest_line(line: str, lineno: int) -> ManifestRecord:
    """Parse one manifest line into a record.

    Args:
        line: Raw line text (newline already stripped).
        lineno: 1-based line number, used in error messages.

    Returns:
        The parsed record.

    Raises:
        ManifestError: The line is not valid JSON or is missing a required key.
    """
    try:
        payload = json.loads(line)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"line {lineno}: not valid JSON ({exc.msg})") from exc
    if not isinstance(payload, dict):
        raise ManifestError(f"line {lineno}: expected a JSON object")
    for key in ("path", "sha256"):
        if not isinstance(payload.get(key), str) or not payload[key]:
            raise ManifestError(f"line {lineno}: missing or empty '{key}'")
    size = payload.get("size")
    return ManifestRecord(
        path=payload["path"],
        sha256=payload["sha256"],
        size=size if isinstance(size, int) else -1,
        discussion_id=str(payload.get("discussion_id", "")),
        recorded_at=str(payload.get("recorded_at", "")),
        suspect=payload.get("suspect") or None,
        source=str(payload.get("source", "")),
    )


def load_manifest(manifest_path: Path) -> tuple[dict[str, ManifestRecord], dict[str, list[str]]]:
    """Load the manifest, keeping the FIRST record for each path.

    First-wins is the anti-re-blessing rule: a sealed record's digest never
    legitimately changes, so a later line claiming a different digest for the
    same path is a conflict to report, not an update to apply.

    Args:
        manifest_path: Path to the JSONL manifest. A missing file is an empty
            manifest, not an error — that is the day-one state.

    Returns:
        ``(records, conflicts)``. ``records`` maps path to its earliest record.
        ``conflicts`` maps path to every *distinct* digest seen for it, and is
        only populated for paths with more than one distinct digest.

    Raises:
        ManifestError: The file exists but cannot be parsed.
    """
    records: dict[str, ManifestRecord] = {}
    seen: dict[str, list[str]] = {}
    if not manifest_path.exists():
        return records, {}
    try:
        text = manifest_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(f"cannot read {manifest_path}: {exc}") from exc

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip():
            continue
        record = parse_manifest_line(raw, lineno)
        digests = seen.setdefault(record.path, [])
        if record.sha256 not in digests:
            digests.append(record.sha256)
        records.setdefault(record.path, record)

    conflicts = {path: digests for path, digests in seen.items() if len(digests) > 1}
    return records, conflicts


def append_records(manifest_path: Path, records: list[ManifestRecord]) -> None:
    """Append records to the manifest, creating it if absent.

    Append-only by construction: this function opens in ``"a"`` mode and never
    reads, rewrites, or truncates. There is no counterpart that removes a line.

    Args:
        manifest_path: Path to the JSONL manifest.
        records: Records to append, in order.
    """
    if not records:
        return
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "a", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json() + "\n")


# --------------------------------------------------------------------------
# Discovering sealed records
# --------------------------------------------------------------------------


def closed_discussion_ids(db_path: Path) -> set[str] | None:
    """Return discussion IDs the metrics DB marks as closed.

    Opened strictly read-only (``mode=ro`` URI). Any failure — missing file,
    missing table, locked DB — returns **None**, not an empty set. The
    distinction is load-bearing: an empty set means "consulted, nothing is
    closed", None means "the seal source could not be consulted at all", and the
    DB is gitignored (``.gitignore:13`` matches ``*.db``) so None is the normal
    state on every clone, worktree, CI runner and derived project. Collapsing
    the two let a missing DB read as "these records stopped being sealed".

    Args:
        db_path: Path to ``metrics/evaluation.db``.

    Returns:
        Set of closed discussion IDs (possibly empty), or None if the DB could
        not be read.
    """
    if not db_path.exists():
        return None
    try:
        conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error:
        return None
    try:
        rows = conn.execute("SELECT discussion_id FROM discussions WHERE status = 'closed'")
        return {row[0] for row in rows if row[0]}
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def is_sealed(disc_dir: Path, closed_ids: set[str]) -> bool:
    """Return True if a discussion directory counts as sealed.

    Sealed means EITHER the metrics DB marks it closed OR one of its Layer 1
    files is read-only on disk — the two things ``close_discussion.py`` does.
    The OR is deliberate: measured on this repo the read-only set (21) is a
    strict subset of the DB-closed set (140), but a derived project may have no
    DB, and a DB row can be lost while the on-disk seal survives. Taking either
    signal baselines more records, which is the safe direction for a detective
    control.

    Args:
        disc_dir: A ``discussions/<date>/<id>`` directory.
        closed_ids: Discussion IDs the DB marks closed.

    Returns:
        True if the discussion is sealed.
    """
    if disc_dir.name in closed_ids:
        return True
    for filename in SEALED_FILENAMES:
        candidate = disc_dir / filename
        if candidate.exists() and not os.access(candidate, os.W_OK):
            return True
    return False


def discussion_dirs(root: Path) -> list[Path]:
    """Return every ``discussions/<date>/<id>`` directory under a repo root.

    Args:
        root: Repository root.

    Returns:
        Sorted list of discussion directories (empty if ``discussions/`` absent).
    """
    base = root / DISCUSSIONS_DIRNAME
    if not base.is_dir():
        return []
    out: list[Path] = []
    for day in sorted(base.iterdir()):
        if not day.is_dir():
            continue
        out.extend(sorted(child for child in day.iterdir() if child.is_dir()))
    return out


def sealed_targets(root: Path, closed_ids: set[str]) -> list[tuple[str, str, Path]]:
    """Enumerate the sealed Layer 1 files under a repo root.

    Args:
        root: Repository root.
        closed_ids: Discussion IDs the DB marks closed.

    Returns:
        List of ``(discussion_id, repo_relative_posix_path, absolute_path)``,
        covering only files that exist.
    """
    out: list[tuple[str, str, Path]] = []
    for disc_dir in discussion_dirs(root):
        if not is_sealed(disc_dir, closed_ids):
            continue
        for filename in SEALED_FILENAMES:
            path = disc_dir / filename
            if path.exists():
                out.append((disc_dir.name, path.relative_to(root).as_posix(), path))
    return out


def seal_time_suspect(path: Path) -> str | None:
    """Return a seal-time anomaly for a file, or None.

    Only one anomaly is detected today, and it is detected because it is real in
    this repo: a sealed ``events.jsonl`` of 0 bytes. ``transcript.md`` is
    generated from the events, so a closed discussion with no events is wrong
    regardless of how it got that way.

    Args:
        path: The sealed file.

    Returns:
        ``SUSPECT_SEALED_EMPTY`` or None.
    """
    if path.name == "events.jsonl" and path.stat().st_size == 0:
        return SUSPECT_SEALED_EMPTY
    return None


# --------------------------------------------------------------------------
# Git corroboration
# --------------------------------------------------------------------------


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str] | None:
    """Run a git command under ``root``, returning None if git could not run."""
    try:
        return subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass(frozen=True)
class GitState:
    """What git says about ``discussions/`` right now.

    Attributes:
        status: Repo-relative path -> two-character porcelain status code, for
            every path git reports as anything other than clean-and-tracked.
        head_paths: Repo-relative paths that have a blob in ``HEAD``. Empty when
            the repository has no commits yet — which is true, not an error.
    """

    status: dict[str, str]
    head_paths: frozenset[str]


def git_state(root: Path) -> GitState | None:
    """Collect the git facts the corroboration pass needs.

    Two questions are asked of git directly rather than inferred from each
    other: *what does git consider dirty* (``git status --porcelain -z``) and
    *what actually has a committed blob* (``git ls-tree -r HEAD``). ``-z``
    avoids git's path-quoting rules entirely.

    The second call is the fix for a measured defect: a staged new file has
    porcelain code ``A ``, and treating "not ``??``" as "differs from its
    committed blob" turned a freshly sealed, byte-identical record RED the
    moment it was ``git add``-ed — inside the exact window the commit-time gate
    runs in.

    Args:
        root: Repository root.

    Returns:
        A :class:`GitState`, or None when git is unavailable or this is not a
        repository. Callers must treat None as "corroboration did not run",
        never as "everything is fine".
    """
    result = _run_git(
        root, "status", "--porcelain", "-z", "--untracked-files=all", "--", DISCUSSIONS_DIRNAME
    )
    if result is None or result.returncode != 0:
        return None

    status: dict[str, str] = {}
    fields = result.stdout.split("\0")
    index = 0
    while index < len(fields):
        entry = fields[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        # Rename/copy entries are followed by the original path in its own field.
        if code[0] in ("R", "C"):
            index += 1
        status[path] = code

    head = _run_git(root, "rev-parse", "--verify", "--quiet", "HEAD")
    if head is None:
        return None
    if head.returncode != 0:
        # A repository with no commits. Nothing has a committed blob, so every
        # record is uncorroborated — which is the honest answer, not a failure.
        return GitState(status=status, head_paths=frozenset())

    tree = _run_git(root, "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", DISCUSSIONS_DIRNAME)
    if tree is None or tree.returncode != 0:
        # HEAD exists but we could not enumerate it. Refuse to guess: report
        # that corroboration did not run rather than inventing a verdict.
        return None
    head_paths = frozenset(p for p in tree.stdout.split("\0") if p)
    return GitState(status=status, head_paths=head_paths)


def git_signal(rel_path: str, state: GitState | None) -> str | None:
    """Classify a watched file against git.

    The order matters. "Does a committed blob exist for this path?" is asked
    FIRST, because ``git-differs`` is a comparison against that blob and is
    meaningless without one. Only a path that HEAD actually holds can be said to
    differ from HEAD.

    Args:
        rel_path: Repo-relative POSIX path.
        state: Output of :func:`git_state`, or None if git did not run.

    Returns:
        ``GIT_UNTRACKED`` (no committed blob — nothing corroborates this path),
        ``GIT_DIFFERS`` (a committed blob exists and the index/worktree copy is
        not it), or None (matches HEAD, or git did not run).
    """
    if state is None:
        return None
    if rel_path not in state.head_paths:
        return GIT_UNTRACKED
    if rel_path not in state.status:
        return None
    return GIT_DIFFERS


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Result:
    """The verdict for one watched Layer 1 file."""

    discussion_id: str
    path: str
    state: str
    reason: str
    suspect: str | None = None
    git: str | None = None
    seal: str | None = None


@dataclass
class Report:
    """The outcome of a verification pass."""

    results: list[Result] = field(default_factory=list)
    git_ran: bool = True
    seal_source_available: bool = True

    @property
    def changed(self) -> list[Result]:
        """Records whose content no longer matches what was sealed."""
        return [r for r in self.results if r.state == STATE_CHANGED]

    @property
    def unknown(self) -> list[Result]:
        """Sealed records that were never baselined."""
        return [r for r in self.results if r.state == STATE_UNKNOWN]

    @property
    def verified(self) -> list[Result]:
        """Watched records whose bytes still match their manifest digest."""
        return [r for r in self.results if r.state == STATE_VERIFIED]

    @property
    def suspect(self) -> list[Result]:
        """Records carrying a seal-time anomaly — frozen, never certified."""
        return [r for r in self.results if r.suspect]

    @property
    def uncorroborated(self) -> list[Result]:
        """Records with no blob in HEAD, so nothing corroborates them."""
        return [r for r in self.results if r.git == GIT_UNTRACKED]

    @property
    def unsealed(self) -> list[Result]:
        """Manifest records present on disk but no longer classified as sealed.

        A statement about seal *metadata*, never about content — the digest
        comparison is unaffected and these are not counted as changed. Read it
        together with :attr:`seal_source_available`: when that is False the seal
        source could not be consulted at all, so this list is expected to cover
        every manifest record and means nothing.
        """
        return [r for r in self.results if r.seal == SEAL_LOST]


def verify(
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
    db_path: Path | None = None,
    use_git: bool = True,
) -> Report:
    """Recompute digests for every watched Layer 1 file and compare to the manifest.

    The watch list is ``manifest paths UNION currently-sealed files on disk``.
    Manifest membership alone is enough: a path in the manifest is hashed and
    compared whatever the seal metadata says about it today. The sealed-set scan
    only *adds* never-baselined records (as UNKNOWN); it can never drop a
    manifest path out of the comparison. See the module docstring — enumerating
    from the sealed set alone reported 236 of this repo's 278 byte-identical
    records as CHANGED on any checkout without ``metrics/evaluation.db``.

    Args:
        root: Repository root (defaults to this repo).
        manifest_path: Manifest location (defaults to ``metrics/`` under root).
        db_path: Metrics DB, opened read-only (defaults to ``metrics/`` under root).
        use_git: Run the git corroboration pass. Disable in tests operating on a
            scratch tree that is not its own repository.

    Returns:
        A :class:`Report`.

    Raises:
        ManifestError: The manifest exists but cannot be parsed.
    """
    root = root or PROJECT_ROOT
    manifest_path = manifest_path or root / MANIFEST_RELPATH
    db_path = db_path or root / DB_RELPATH

    records, conflicts = load_manifest(manifest_path)
    closed_ids = closed_discussion_ids(db_path)
    sealed_now = {
        rel: (disc_id, path) for disc_id, rel, path in sealed_targets(root, closed_ids or set())
    }
    state_git = git_state(root) if use_git else None
    report = Report(git_ran=state_git is not None, seal_source_available=closed_ids is not None)

    for rel_path in sorted(set(records) | set(sealed_now)):
        record = records.get(rel_path)
        on_disk = sealed_now.get(rel_path)
        path = on_disk[1] if on_disk else root / rel_path
        discussion_id = on_disk[0] if on_disk else (record.discussion_id if record else "")
        exists = path.exists()
        git = git_signal(rel_path, state_git)

        # Losing the read-only bit or the DB row says nothing about the bytes,
        # so it is a flag beside the verdict, not the verdict. It is also only
        # observable when the DB could be consulted at all.
        seal = (
            SEAL_LOST
            if (record is not None and on_disk is None and exists and closed_ids is not None)
            else None
        )
        suspect = record.suspect if record else (seal_time_suspect(path) if exists else None)

        if rel_path in conflicts:
            report.results.append(
                Result(
                    discussion_id,
                    rel_path,
                    STATE_CHANGED,
                    f"manifest conflict: {len(conflicts[rel_path])} differing digests recorded",
                    suspect,
                    git,
                    seal,
                )
            )
            continue

        if record is None:
            state, reason = STATE_UNKNOWN, "never baselined"
        elif not exists:
            state, reason = STATE_CHANGED, "sealed record is missing from disk"
        else:
            actual = sha256_file(path)
            if actual == record.sha256:
                state, reason = STATE_VERIFIED, "digest matches"
            else:
                state = STATE_CHANGED
                reason = (
                    f"sha256 {actual[:12]} != sealed {record.sha256[:12]} "
                    f"(size {path.stat().st_size} vs sealed {record.size})"
                )

        # Git holds a committed blob for this path and the working copy is not
        # it. That is positive evidence of change with no baseline required, and
        # it OUTRANKS a matching digest: a match then only proves the file has
        # not moved since baselining — it was already wrong when baselined.
        if git == GIT_DIFFERS and state != STATE_CHANGED:
            state = STATE_CHANGED
            reason = "differs from its committed git blob (changed before baselining)"

        report.results.append(Result(discussion_id, rel_path, state, reason, suspect, git, seal))

    return report


def baseline(
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
    db_path: Path | None = None,
) -> tuple[list[ManifestRecord], int]:
    """Append manifest records for sealed files that have none yet.

    This can only ADD. Paths already in the manifest are left untouched, so
    running it repeatedly is idempotent and it cannot be used to re-bless a
    record that changed. It also does not certify anything: a file that was
    already damaged is frozen in its damaged state, and the ``suspect`` field
    plus the git corroboration in :func:`verify` are what keep that visible.

    Args:
        root: Repository root (defaults to this repo).
        manifest_path: Manifest location.
        db_path: Metrics DB, opened read-only.

    Returns:
        ``(appended_records, already_present_count)``.

    Raises:
        ManifestError: The manifest exists but cannot be parsed.
    """
    root = root or PROJECT_ROOT
    manifest_path = manifest_path or root / MANIFEST_RELPATH
    db_path = db_path or root / DB_RELPATH

    records, _ = load_manifest(manifest_path)
    closed_ids = closed_discussion_ids(db_path) or set()
    now = datetime.now(UTC).isoformat()

    new: list[ManifestRecord] = []
    present = 0
    for discussion_id, rel_path, path in sealed_targets(root, closed_ids):
        if rel_path in records:
            present += 1
            continue
        new.append(
            ManifestRecord(
                path=rel_path,
                sha256=sha256_file(path),
                size=path.stat().st_size,
                discussion_id=discussion_id,
                recorded_at=now,
                suspect=seal_time_suspect(path),
                source="baseline",
            )
        )
    append_records(manifest_path, new)
    return new, present


def record_seal(
    discussion_id: str,
    disc_dir: Path,
    *,
    root: Path | None = None,
    manifest_path: Path | None = None,
) -> list[ManifestRecord]:
    """Record digests for one discussion's Layer 1 files at seal time.

    Called by ``scripts/close_discussion.py`` so coverage of new discussions is
    automatic rather than dependent on anyone remembering — capture is enforced
    at the tooling layer.

    Like :func:`baseline`, this only appends for paths with no record yet, so
    re-running ``close_discussion.py`` on an already-sealed discussion cannot
    overwrite the original digest.

    Args:
        discussion_id: The discussion being sealed.
        disc_dir: Its directory.
        root: Repository root, used to compute the relative manifest key.
        manifest_path: Manifest location.

    Returns:
        The records appended (empty if every file was already recorded).

    Raises:
        ManifestError: The manifest exists but cannot be parsed.
    """
    root = root or PROJECT_ROOT
    manifest_path = manifest_path or root / MANIFEST_RELPATH

    records, _ = load_manifest(manifest_path)
    now = datetime.now(UTC).isoformat()

    new: list[ManifestRecord] = []
    for filename in SEALED_FILENAMES:
        path = disc_dir / filename
        if not path.exists():
            continue
        try:
            rel_path = path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            rel_path = path.as_posix()
        if rel_path in records:
            continue
        new.append(
            ManifestRecord(
                path=rel_path,
                sha256=sha256_file(path),
                size=path.stat().st_size,
                discussion_id=discussion_id,
                recorded_at=now,
                suspect=seal_time_suspect(path),
                source="seal",
            )
        )
    append_records(manifest_path, new)
    return new


# --------------------------------------------------------------------------
# Reporting / CLI
# --------------------------------------------------------------------------


def format_report(report: Report, *, limit: int = 10) -> str:
    """Render a human-readable summary of a verification pass.

    Args:
        report: The report to render.
        limit: Maximum number of individual records listed per bucket.

    Returns:
        Multi-line report text.
    """
    # ASCII-only on purpose: this text is printed to a raw Windows terminal
    # whose codec is cp1252 and which raises UnicodeEncodeError on an em-dash
    # mid-run (the same class as the _format_summary / notify-title crashes
    # already recorded in the regression ledger).
    lines = [
        f"Layer 1 integrity - {len(report.results)} sealed record(s)",
        f"  CHANGED SINCE SEALING      {len(report.changed)}",
        f"  UNKNOWN (never baselined)  {len(report.unknown)}",
        f"  VERIFIED intact            {len(report.verified)}",
        f"  suspect at baseline        {len(report.suspect)}  (frozen, NOT certified intact)",
    ]
    if report.git_ran:
        lines.append(
            f"  uncorroborated by git      {len(report.uncorroborated)}  "
            f"(no blob in HEAD: manifest is the only witness)"
        )
    else:
        lines.append("  git corroboration          DID NOT RUN (git unavailable or not a repo)")

    if report.seal_source_available:
        lines.append(
            f"  no longer sealed           {len(report.unsealed)}  "
            f"(metadata only - bytes still compared, never fatal)"
        )
    else:
        lines.append(
            "  seal-state check           DID NOT RUN (metrics/evaluation.db absent or has no "
            "'discussions' table)"
        )

    for label, bucket in (
        ("CHANGED", report.changed),
        ("SUSPECT", report.suspect),
        ("UNKNOWN", report.unknown),
    ):
        if not bucket:
            continue
        lines.append(f"\n  {label}:")
        for result in bucket[:limit]:
            detail = result.reason
            if label == "SUSPECT":
                detail = f"{result.suspect} [{result.state}] {result.reason}"
            lines.append(f"    {result.path}: {detail}")
        if len(bucket) > limit:
            lines.append(f"    ... and {len(bucket) - limit} more")
    return "\n".join(lines)


def _report_to_dict(report: Report) -> dict:
    """Serialize a report for ``--json`` consumers."""
    return {
        "schema": SCHEMA_VERSION,
        "git_ran": report.git_ran,
        "seal_source_available": report.seal_source_available,
        "counts": {
            "total": len(report.results),
            "changed": len(report.changed),
            "unknown": len(report.unknown),
            "verified": len(report.verified),
            "suspect": len(report.suspect),
            "uncorroborated": len(report.uncorroborated),
            "unsealed": len(report.unsealed),
        },
        "records": [
            {
                "discussion_id": r.discussion_id,
                "path": r.path,
                "state": r.state,
                "reason": r.reason,
                "suspect": r.suspect,
                "git": r.git,
                "seal": r.seal,
            }
            for r in report.results
        ],
    }


def main(argv: list[str] | None = None) -> int:
    """CLI entry point.

    Returns:
        0 when nothing CHANGED (UNKNOWN alone is not a failure — see
        ``--strict-unknown``); 1 on any CHANGED record or manifest error.
    """
    parser = argparse.ArgumentParser(
        description="Record and verify sha256 digests of sealed Layer 1 discussion records"
    )
    parser.add_argument(
        "--baseline",
        action="store_true",
        help=(
            "Append manifest records for sealed files that have none. Only adds; "
            "never overwrites an existing digest, so it cannot re-bless a changed record."
        ),
    )
    parser.add_argument("--json", action="store_true", help="Emit the report as JSON")
    parser.add_argument(
        "--strict-unknown",
        action="store_true",
        help="Also exit non-zero when sealed records have never been baselined",
    )
    parser.add_argument("--no-git", action="store_true", help="Skip the git corroboration pass")
    parser.add_argument("--root", default=None, help="Repository root (defaults to this repo)")
    parser.add_argument("--manifest", default=None, help="Manifest path override")
    parser.add_argument("--db", default=None, help="Metrics DB path override (read-only)")
    args = parser.parse_args(argv)

    root = Path(args.root) if args.root else PROJECT_ROOT
    manifest_path = Path(args.manifest) if args.manifest else root / MANIFEST_RELPATH
    db_path = Path(args.db) if args.db else root / DB_RELPATH

    try:
        if args.baseline:
            new, present = baseline(root=root, manifest_path=manifest_path, db_path=db_path)
            suspect = [r for r in new if r.suspect]
            print(
                f"Baseline: appended {len(new)} record(s); "
                f"{present} already recorded (left untouched)."
            )
            if suspect:
                print(
                    f"  WARNING: {len(suspect)} newly-baselined record(s) carry a seal-time "
                    "anomaly - frozen as-is, NOT certified intact:"
                )
                for record in suspect:
                    print(f"    {record.path}: {record.suspect}")

        report = verify(
            root=root,
            manifest_path=manifest_path,
            db_path=db_path,
            use_git=not args.no_git,
        )
    except ManifestError as exc:
        print(f"ERROR layer1: manifest unreadable: {exc}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(_report_to_dict(report), indent=2, sort_keys=True))
    else:
        print(format_report(report))

    if report.changed:
        return 1
    if args.strict_unknown and report.unknown:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
