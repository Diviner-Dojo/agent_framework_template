"""Tests for the /distribute capability (scripts/distribute/).

Covers the three building blocks with a temp-git fixture:

- repo_safety_check — the opt-in HARD GATE and skip-if-busy git-state check.
- change_package — value / inert / collision-pinned / collision-diverged classification.
- stage_branch — fresh branch off main, copies only stageable files, never pushes, never
  touches main, restores the original branch, rolls back cleanly on failure.
"""

import difflib
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

TEMPLATE_ROOT = Path(__file__).parent.parent
if str(TEMPLATE_ROOT) not in sys.path:
    sys.path.insert(0, str(TEMPLATE_ROOT))

from scripts.distribute import repo_safety_check as rsc_mod  # noqa: E402
from scripts.distribute import stage_branch as stage_mod  # noqa: E402
from scripts.distribute.assessment import (  # noqa: E402
    Interpretation,
    OverwriteDiff,
    build_assessment_doc,
    compute_overwrite_diffs,
    redact_secrets,
    triage_diff,
)
from scripts.distribute.change_package import (  # noqa: E402
    ChangeItem,
    ChangePackage,
    compute_package,
    package_report,
    reclassify_route,
)
from scripts.distribute.repo_safety_check import (  # noqa: E402
    baseline_gate_green,
    repo_safety_check,
)
from scripts.distribute.stage_branch import detect_base_branch, stage  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
from scripts.lineage._utils import hash_file  # noqa: E402
from scripts.lineage.init_lineage import lineage_init  # noqa: E402
from scripts.lineage.manifest import manifest_read  # noqa: E402

# ── Helpers ─────────────────────────────────────────────────────────


def _g(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run a git command against a repo (test helper)."""
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=check
    )


def _init_repo(repo: Path) -> None:
    """Initialise a git repo on branch ``main`` with a deterministic identity."""
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True, text=True)
    _g(repo, "symbolic-ref", "HEAD", "refs/heads/main")
    _g(repo, "config", "user.email", "test@example.com")
    _g(repo, "config", "user.name", "Test User")
    _g(repo, "config", "commit.gpgsign", "false")


def _write(root: Path, rel: str, content: str) -> None:
    """Write a file under root, creating parent directories."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _commit_all(repo: Path, message: str) -> None:
    """Stage and commit everything (no hooks)."""
    _g(repo, "add", "-A")
    _g(repo, "commit", "--no-verify", "-m", message)


def _manifest_text(
    *,
    accepts=True,
    include_custodian: bool = True,
    pinned: list | None = None,
    accept_paths: list | None = None,
    deny_paths: list | None = None,
) -> str:
    """Build a framework-lineage.yaml string with a configurable custodian block."""
    data: dict = {
        "schema_version": "1.0",
        "lineage_id": "test-lineage",
        "serial": 0,
        "instance": {
            "name": "t",
            "version": "1.0.0",
            "type": "derived",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
        "drift": {"status": "current", "divergence_distance": 0},
        "pinned_traits": pinned or [],
    }
    if include_custodian:
        custodian: dict = {}
        if accepts is not None:
            custodian["accepts_distribution"] = accepts
        if accept_paths:
            custodian["accept_paths"] = accept_paths
        if deny_paths:
            custodian["deny_paths"] = deny_paths
        data["custodian"] = custodian
    return yaml.dump(data, default_flow_style=False, sort_keys=False)


def _set_manifest(repo: Path, **kwargs) -> None:
    """Write a manifest and commit it so the tree stays clean."""
    (repo / "framework-lineage.yaml").write_text(_manifest_text(**kwargs), encoding="utf-8")
    _commit_all(repo, "set manifest")


@pytest.fixture
def clean_target(tmp_path: Path) -> Path:
    """An opted-in, clean git target on main with a valid manifest."""
    repo = tmp_path / "target"
    _init_repo(repo)
    _write(repo, ".claude/agents/x.md", "# X")
    (repo / "framework-lineage.yaml").write_text(_manifest_text(accepts=True), encoding="utf-8")
    _commit_all(repo, "init")
    return repo


# ── repo_safety_check ───────────────────────────────────────────────


class TestRepoSafetyCheckOptIn:
    """Opt-in HARD GATE: only a strict boolean True opts a target in."""

    def test_opted_in_clean_can_proceed(self, clean_target: Path) -> None:
        report = repo_safety_check(clean_target)
        assert report.opted_in is True
        assert report.is_safe is True
        assert report.can_proceed is True
        assert report.skip_reason is None
        assert report.branch == "main"

    def test_accepts_string_true_is_rejected(self, clean_target: Path) -> None:
        _set_manifest(clean_target, accepts="true")
        report = repo_safety_check(clean_target)
        assert report.opted_in is False
        assert report.skip_reason == "not-opted-in"

    def test_accepts_integer_one_is_rejected(self, clean_target: Path) -> None:
        _set_manifest(clean_target, accepts=1)
        report = repo_safety_check(clean_target)
        assert report.opted_in is False

    def test_accepts_false_is_not_opted_in(self, clean_target: Path) -> None:
        _set_manifest(clean_target, accepts=False)
        report = repo_safety_check(clean_target)
        assert report.opted_in is False

    def test_missing_custodian_block_is_not_opted_in(self, clean_target: Path) -> None:
        _set_manifest(clean_target, include_custodian=False)
        report = repo_safety_check(clean_target)
        assert report.opted_in is False

    def test_per_path_globs_surfaced(self, clean_target: Path) -> None:
        _set_manifest(
            clean_target,
            accepts=True,
            accept_paths=[".claude/agents/*"],
            deny_paths=["scripts/*"],
        )
        report = repo_safety_check(clean_target)
        assert report.accept_paths == [".claude/agents/*"]
        assert report.deny_paths == ["scripts/*"]


class TestRepoSafetyCheckGitState:
    """Skip-if-busy: any disturbed git state blocks (fail-closed)."""

    def test_dirty_tree_with_untracked_file_blocks(self, clean_target: Path) -> None:
        _write(clean_target, "untracked.txt", "wip")
        report = repo_safety_check(clean_target)
        assert report.is_safe is False
        assert report.can_proceed is False
        assert any("dirty" in b for b in report.blockers)

    def test_detached_head_blocks(self, clean_target: Path) -> None:
        _g(clean_target, "checkout", "--detach", "HEAD")
        report = repo_safety_check(clean_target)
        assert report.is_safe is False
        assert report.branch is None
        assert any("detached" in b for b in report.blockers)

    def test_merge_in_progress_blocks(self, clean_target: Path) -> None:
        head = _g(clean_target, "rev-parse", "HEAD").stdout.strip()
        (clean_target / ".git" / "MERGE_HEAD").write_text(head + "\n", encoding="utf-8")
        report = repo_safety_check(clean_target)
        assert report.is_safe is False
        assert any("merge in progress" in b for b in report.blockers)

    def test_missing_manifest_blocks_and_not_opted_in(self, clean_target: Path) -> None:
        (clean_target / "framework-lineage.yaml").unlink()
        _commit_all(clean_target, "remove manifest")
        report = repo_safety_check(clean_target)
        assert report.opted_in is False
        assert report.is_safe is False
        assert any("no lineage manifest" in b for b in report.blockers)

    def test_malformed_manifest_fails_closed(self, clean_target: Path) -> None:
        # "a: b: c" is a YAML parse error (mapping value not allowed here).
        (clean_target / "framework-lineage.yaml").write_text("a: b: c\n", encoding="utf-8")
        _commit_all(clean_target, "corrupt manifest")
        report = repo_safety_check(clean_target)
        assert report.opted_in is False
        assert report.is_safe is False
        assert any("unreadable" in b for b in report.blockers)

    def test_non_git_directory_blocks(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        (plain / "framework-lineage.yaml").write_text(_manifest_text(), encoding="utf-8")
        report = repo_safety_check(plain)
        assert report.is_safe is False
        assert any("not a git working tree" in b for b in report.blockers)

    def test_missing_target_directory(self, tmp_path: Path) -> None:
        report = repo_safety_check(tmp_path / "does-not-exist")
        assert report.can_proceed is False
        assert any("not a directory" in b for b in report.blockers)

    def test_git_missing_on_path_blocks(self, clean_target: Path, monkeypatch) -> None:
        monkeypatch.setattr(rsc_mod.shutil, "which", lambda _name: None)
        report = repo_safety_check(clean_target)
        assert report.is_safe is False
        assert any("git executable not found" in b for b in report.blockers)


class TestBaselineGate:
    """The optional, slow baseline gate is separate from the cheap preflight."""

    def test_missing_gate_script_returns_false(self, tmp_path: Path) -> None:
        green, summary = baseline_gate_green(tmp_path)
        assert green is False
        assert "no quality_gate.py" in summary


# ── change_package ──────────────────────────────────────────────────


@pytest.fixture
def package_env(tmp_path: Path) -> dict:
    """A target with lineage baselines + a hub offering each classification."""
    target = tmp_path / "target"
    hub = tmp_path / "hub"

    # Target framework files at baseline ("v1" / "same").
    _write(target, ".claude/agents/f.md", "F v1")
    _write(target, ".claude/agents/d.md", "D v1")
    _write(target, ".claude/agents/p.md", "P v1")
    _write(target, ".claude/agents/c.md", "C same")
    _write(target, "CLAUDE.md", "# target")

    db = target / "metrics" / "evaluation.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    init_db(db)
    lineage_init(
        project_root=target,
        template_version="2.1.0",
        project_name="t",
        db_path=db,
        manifest_path=target / "framework-lineage.yaml",
        custodian_dir=target / ".claude" / "custodian",
    )

    # Create a deliberate divergence: modify d after baseline capture.
    _write(target, ".claude/agents/d.md", "D v1 MODIFIED")

    # Pin p and opt in.
    data = manifest_read(target / "framework-lineage.yaml")
    data["pinned_traits"] = [
        {"path": ".claude/agents/p.md", "reason": "project-specific", "adr_reference": "ADR-0001"}
    ]
    data["custodian"] = {"accepts_distribution": True}
    data["serial"] = data.get("serial", 0) + 1
    (target / "framework-lineage.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    # Hub versions.
    _write(hub, ".claude/agents/f.md", "F v2 NEW")  # differs from unchanged target -> value
    _write(hub, ".claude/agents/d.md", "D v2 HUB")  # differs from diverged target -> diverged
    _write(hub, ".claude/agents/p.md", "P v2")  # pinned -> dropped
    _write(hub, ".claude/agents/c.md", "C same")  # identical -> current
    _write(hub, ".claude/agents/g.md", "G new")  # target lacks -> inert

    offer = [
        ".claude/agents/f.md",
        ".claude/agents/d.md",
        ".claude/agents/p.md",
        ".claude/agents/c.md",
        ".claude/agents/g.md",
    ]
    return {"target": target, "hub": hub, "offer": offer}


def _by_path(package: ChangePackage, rel: str) -> ChangeItem:
    return next(i for i in package.items if i.file_path == rel)


class TestChangePackageClassification:
    """Each classification is produced for the right condition."""

    def test_value_inert_pinned_diverged_current(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        # B1 floor: an unprovable overwrite (drift "current", hub differs) is value-unverified,
        # never silent "value".
        assert _by_path(pkg, ".claude/agents/f.md").classification == "value-unverified"
        assert _by_path(pkg, ".claude/agents/g.md").classification == "inert"
        assert _by_path(pkg, ".claude/agents/p.md").classification == "collision-pinned"
        assert _by_path(pkg, ".claude/agents/d.md").classification == "collision-diverged"
        assert _by_path(pkg, ".claude/agents/c.md").classification == "current"

    def test_stageable_excludes_pinned_and_diverged(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        staged = {i.file_path for i in pkg.stageable}
        assert staged == {".claude/agents/f.md", ".claude/agents/g.md"}
        assert {i.file_path for i in pkg.pinned_dropped} == {".claude/agents/p.md"}
        assert {i.file_path for i in pkg.diverged} == {".claude/agents/d.md"}

    def test_has_unmediable_candidates_true_with_diverged(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        assert pkg.has_unmediable_candidates() is True

    def test_fast_path_when_no_diverged(self, package_env: dict) -> None:
        offer = [".claude/agents/f.md", ".claude/agents/g.md", ".claude/agents/c.md"]
        pkg = compute_package(package_env["hub"], package_env["target"], offer)
        assert pkg.has_unmediable_candidates() is False

    def test_counts_are_content_free(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        counts = pkg.counts()
        assert counts["value-unverified"] == 1
        assert counts["inert"] == 1
        assert counts["collision-pinned"] == 1
        assert counts["collision-diverged"] == 1
        assert counts["current"] == 1


class TestChangePackagePerPathRules:
    """Per-path deny / accept globs gate eligibility (deny precedes accept)."""

    def _set_custodian(self, target: Path, **custodian) -> None:
        data = manifest_read(target / "framework-lineage.yaml")
        data["custodian"] = {"accepts_distribution": True, **custodian}
        data["serial"] = data.get("serial", 0) + 1
        (target / "framework-lineage.yaml").write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
        )

    def test_deny_path_excludes_file(self, package_env: dict) -> None:
        self._set_custodian(package_env["target"], deny_paths=[".claude/agents/f.md"])
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        assert _by_path(pkg, ".claude/agents/f.md").classification == "denied"

    def test_accept_allowlist_excludes_non_matching(self, package_env: dict) -> None:
        self._set_custodian(package_env["target"], accept_paths=[".claude/agents/g.md"])
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        assert _by_path(pkg, ".claude/agents/g.md").classification == "inert"
        assert _by_path(pkg, ".claude/agents/f.md").classification == "not-accepted"


# ── stage_branch ────────────────────────────────────────────────────


@pytest.fixture
def stage_env(tmp_path: Path) -> dict:
    """A clean opted-in git target on main + a hub with files to stage."""
    target = tmp_path / "target"
    hub = tmp_path / "hub"
    _init_repo(target)
    _write(target, ".claude/agents/keep.md", "keep original")
    (target / "framework-lineage.yaml").write_text(_manifest_text(accepts=True), encoding="utf-8")
    _commit_all(target, "init")

    _write(hub, ".claude/agents/new.md", "NEW from hub")
    _write(hub, "CLAUDE.md", "# hub claude")
    _write(hub, ".claude/agents/keep.md", "HUB WOULD OVERWRITE")  # pinned — must not be copied
    return {"target": target, "hub": hub}


def _stage_package(stage_env: dict) -> ChangePackage:
    """A package with value + inert stageables plus a pinned + diverged item that must be skipped."""  # noqa: E501
    return ChangePackage(
        target_path=str(stage_env["target"]),
        items=[
            ChangeItem(".claude/agents/new.md", "inert", "h1", None, None, "new"),
            ChangeItem("CLAUDE.md", "value", "h2", "h3", "current", "update"),
            ChangeItem(".claude/agents/keep.md", "collision-pinned", "h4", "h5", "pinned", "pin"),
            ChangeItem(
                ".claude/agents/div.md", "collision-diverged", "h6", "h7", "modified", "div"
            ),
        ],
    )


class TestStageBranch:
    """Staging writes only safe files to a fresh branch, never touching main."""

    def test_detect_base_branch_prefers_main(self, stage_env: dict) -> None:
        assert detect_base_branch(stage_env["target"]) == "main"

    def test_happy_path_stages_only_value_and_inert(self, stage_env: dict) -> None:
        target = stage_env["target"]
        main_before = _g(target, "rev-parse", "main").stdout.strip()

        result = stage(
            target,
            _stage_package(stage_env),
            "DOC BODY",
            "framework-update/2026-05-23-test",
            template_root=stage_env["hub"],
            base_branch="main",
        )

        assert set(result.files_staged) == {".claude/agents/new.md", "CLAUDE.md"}
        assert result.commit_sha
        # Branch exists and carries the staged file; main does not.
        assert (
            _g(
                target, "rev-parse", "--verify", "refs/heads/framework-update/2026-05-23-test"
            ).returncode
            == 0
        )
        assert (
            _g(
                target, "cat-file", "-e", f"{result.branch}:.claude/agents/new.md", check=False
            ).returncode
            == 0
        )
        assert (
            _g(target, "cat-file", "-e", "main:.claude/agents/new.md", check=False).returncode != 0
        )
        # main is byte-for-byte unchanged.
        assert _g(target, "rev-parse", "main").stdout.strip() == main_before

    def test_pinned_file_is_never_overwritten(self, stage_env: dict) -> None:
        target = stage_env["target"]
        result = stage(
            target,
            _stage_package(stage_env),
            "DOC",
            "framework-update/pin-test",
            template_root=stage_env["hub"],
            base_branch="main",
        )
        # keep.md on the staged branch retains the target's original content.
        shown = _g(target, "show", f"{result.branch}:.claude/agents/keep.md").stdout
        assert "keep original" in shown
        assert "HUB WOULD OVERWRITE" not in shown
        assert ".claude/agents/keep.md" not in result.files_staged

    def test_original_branch_restored_and_tree_clean(self, stage_env: dict) -> None:
        target = stage_env["target"]
        stage(
            target,
            _stage_package(stage_env),
            "DOC",
            "framework-update/restore-test",
            template_root=stage_env["hub"],
            base_branch="main",
        )
        assert _g(target, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
        assert _g(target, "status", "--porcelain").stdout.strip() == ""
        assert not (target / ".claude" / "agents" / "new.md").exists()

    def test_assessment_doc_written_on_branch(self, stage_env: dict) -> None:
        target = stage_env["target"]
        result = stage(
            target,
            _stage_package(stage_env),
            "ADVISORY DOC BODY",
            "framework-update/doc-test",
            template_root=stage_env["hub"],
            base_branch="main",
        )
        shown = _g(target, "show", f"{result.branch}:{result.doc_path}").stdout
        assert "ADVISORY DOC BODY" in shown

    def test_never_invokes_git_push(self, stage_env: dict, monkeypatch) -> None:
        calls: list[tuple] = []
        real = stage_mod._git

        def spy(target, *args, check=False):
            calls.append(args)
            return real(target, *args, check=check)

        monkeypatch.setattr(stage_mod, "_git", spy)
        stage(
            stage_env["target"],
            _stage_package(stage_env),
            "DOC",
            "framework-update/push-test",
            template_root=stage_env["hub"],
            base_branch="main",
        )
        assert all("push" not in args for args in calls)
        assert any(args[:2] == ("checkout", "-b") for args in calls)

    def test_existing_branch_raises(self, stage_env: dict) -> None:
        target = stage_env["target"]
        _g(target, "branch", "framework-update/dup", "main")
        with pytest.raises(ValueError, match="already exists"):
            stage(
                target,
                _stage_package(stage_env),
                "DOC",
                "framework-update/dup",
                template_root=stage_env["hub"],
                base_branch="main",
            )

    def test_unsafe_branch_name_raises(self, stage_env: dict) -> None:
        with pytest.raises(ValueError, match="unsafe branch name"):
            stage(
                stage_env["target"],
                _stage_package(stage_env),
                "DOC",
                "-evil",
                template_root=stage_env["hub"],
                base_branch="main",
            )

    def test_dirty_target_raises(self, stage_env: dict) -> None:
        _write(stage_env["target"], "wip.txt", "uncommitted")
        with pytest.raises(RuntimeError, match="not safe to stage"):
            stage(
                stage_env["target"],
                _stage_package(stage_env),
                "DOC",
                "framework-update/dirty-test",
                template_root=stage_env["hub"],
                base_branch="main",
            )

    def test_path_escape_raises_and_rolls_back(self, stage_env: dict) -> None:
        target = stage_env["target"]
        package = ChangePackage(
            target_path=str(target),
            items=[ChangeItem("../escape.md", "inert", "h", None, None, "escape")],
        )
        with pytest.raises(ValueError, match="escapes target root"):
            stage(
                target,
                package,
                "DOC",
                "framework-update/escape-test",
                template_root=stage_env["hub"],
                base_branch="main",
            )
        # Rolled back: original branch restored, partial branch deleted.
        assert _g(target, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip() == "main"
        assert (
            _g(
                target,
                "rev-parse",
                "--verify",
                "refs/heads/framework-update/escape-test",
                check=False,
            ).returncode
            != 0
        )


# ── B1 mechanical floor + interpreted assessment (SPEC-20260523-100224) ──────


def _unified(old: str, new: str, path: str) -> str:
    """Build a target→hub unified diff (test helper)."""
    return "".join(
        difflib.unified_diff(
            old.splitlines(keepends=True),
            new.splitlines(keepends=True),
            fromfile=f"target/{path}",
            tofile=f"hub/{path}",
        )
    )


def _vu_item(path: str) -> ChangeItem:
    """A minimal value-unverified ChangeItem (test helper)."""
    return ChangeItem(path, "value-unverified", "h", "t", "current", "flagged")


@pytest.fixture
def stale_baseline_env(tmp_path: Path) -> dict:
    """Reproduce the B1 trigger: a target that re-baselined AFTER a local edit.

    The DB's ``template_hash`` for q.md is reset to the *customized* content (simulating a
    ``/lineage adopt``), so ``drift_scan`` reports ``drift_status == "current"`` even though the
    target's copy is a deliberate divergence the hub cannot see. Under the old code this silently
    classified as ``value`` and would be clobbered on merge; under the floor it must be flagged.
    """
    target = tmp_path / "target"
    hub = tmp_path / "hub"
    rel = ".claude/agents/q.md"

    _write(target, rel, "Q original")
    _write(hub, rel, "Q hub v2")  # the hub has a newer version

    db = target / "metrics" / "evaluation.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    init_db(db)
    lineage_init(
        project_root=target,
        template_version="2.1.0",
        project_name="t",
        db_path=db,
        manifest_path=target / "framework-lineage.yaml",
        custodian_dir=target / ".claude" / "custodian",
    )
    data = manifest_read(target / "framework-lineage.yaml")
    data["custodian"] = {"accepts_distribution": True}
    (target / "framework-lineage.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )

    # The target dev customizes q.md, THEN re-baselines: the DB template_hash is reset to the
    # customized content, so drift now reads "current" (the dangerous "looks unchanged" state).
    _write(target, rel, "Q customized by target dev")
    customized = hash_file(target / rel)
    conn = sqlite3.connect(db)
    try:
        conn.execute(
            "UPDATE lineage_file_drift SET template_hash = ?, local_hash = ? WHERE file_path = ?",
            (customized, customized, rel),
        )
        conn.commit()
    finally:
        conn.close()

    return {"target": target, "hub": hub, "offer": [rel], "rel": rel}


class TestMechanicalFloor:
    """R1 — the floor flags every unprovable overwrite as value-unverified (never silent value)."""

    def test_unprovable_overwrite_is_value_unverified(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        assert _by_path(pkg, ".claude/agents/f.md").classification == "value-unverified"

    def test_value_is_never_produced_in_v1(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        assert all(i.classification != "value" for i in pkg.items)

    def test_value_unverified_is_stageable_and_flagged(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        f = _by_path(pkg, ".claude/agents/f.md")
        assert f in pkg.stageable  # staged for an easy merge
        assert f in pkg.requires_interpretation  # but always surfaced — not silent
        assert pkg.needs_interpretation() is True

    def test_inert_addition_is_not_flagged(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        g = _by_path(pkg, ".claude/agents/g.md")  # pure addition, no overwrite
        assert g.classification == "inert"
        assert g not in pkg.requires_interpretation


class TestStaleBaselineRegression:
    """The B1 keystone: a re-baselined-after-edit file must be flagged, not silently clobbered."""

    @pytest.mark.regression
    def test_rebaseline_after_edit_is_flagged_not_silent(self, stale_baseline_env: dict) -> None:
        # Regression for B1 (REV-20260523-065900): the old code returned silent "value" here and
        # the target's customization was reverted on merge. The floor must flag it instead.
        env = stale_baseline_env
        pkg = compute_package(env["hub"], env["target"], env["offer"])
        item = _by_path(pkg, env["rel"])
        assert item.drift_status == "current"  # the dangerous "looks unchanged" state
        assert item.target_hash != item.hub_hash  # but the content actually differs
        assert item.classification == "value-unverified"  # FLAGGED
        assert item.classification != "value"  # never silent
        assert item in pkg.requires_interpretation


class TestReclassifyRoute:
    """R4 — the escalate-only routing predicate (pure function)."""

    @pytest.mark.parametrize(
        "verdict,hint,expected",
        [
            ("behavioral-blast-radius", "behavioral", "collision-diverged"),
            ("likely-deliberate", "unknown", "collision-diverged"),
            ("cosmetic", "cosmetic", "value-unverified"),
            ("benign", "unknown", "value-unverified"),
            ("", "unknown", "value-unverified"),
            ("cosmetic", "behavioral", "collision-diverged"),  # hint/agent disagreement co-gate
            ("  BENIGN  ", "BEHAVIORAL", "collision-diverged"),  # case/space-normalized co-gate
        ],
    )
    def test_value_unverified_routing(self, verdict: str, hint: str, expected: str) -> None:
        assert reclassify_route("value-unverified", verdict, hint) == expected

    def test_non_value_unverified_passes_through(self) -> None:
        assert reclassify_route("inert", "behavioral-blast-radius", "behavioral") == "inert"
        assert (
            reclassify_route("collision-diverged", "cosmetic", "cosmetic") == "collision-diverged"
        )
        assert reclassify_route("current", "likely-deliberate", "behavioral") == "current"

    def test_escalate_only_never_demotes_to_silent_value(self) -> None:
        for verdict in (
            "cosmetic",
            "benign",
            "behavioral-blast-radius",
            "likely-deliberate",
            "",
            "x",
        ):
            for hint in ("cosmetic", "behavioral", "unknown"):
                assert reclassify_route("value-unverified", verdict, hint) in (
                    "value-unverified",
                    "collision-diverged",
                )


class TestTriageDiff:
    """R2 — deterministic triage; safe default unknown; never false-positive cosmetic."""

    def test_python_blank_line_is_unknown(self) -> None:
        d = _unified("a = 1\nb = 2\n", "a = 1\n\nb = 2\n", "m.py")
        assert triage_diff(d, "m.py") == "unknown"

    def test_python_indentation_change_is_not_cosmetic(self) -> None:
        d = _unified("def f():\n    return 1\n", "def f():\n        return 1\n", "m.py")
        assert triage_diff(d, "m.py") in ("unknown", "behavioral")  # never cosmetic (semantic)

    def test_python_version_string_is_behavioral(self) -> None:
        d = _unified('VERSION = "3.4.0"\n', 'VERSION = "3.5.0"\n', "m.py")
        assert triage_diff(d, "m.py") == "behavioral"

    def test_markdown_version_line_is_cosmetic(self) -> None:
        d = _unified("version: 3.4.0\n", "version: 3.5.0\n", "notes.md")
        assert triage_diff(d, "notes.md") == "cosmetic"

    def test_comment_only_change_is_cosmetic(self) -> None:
        d = _unified("# a\nx = 1\n", "# b\nx = 1\n", "m.py")
        assert triage_diff(d, "m.py") == "cosmetic"

    def test_logic_change_is_behavioral(self) -> None:
        d = _unified("x = 1\n", "x = compute(2)\n", "m.py")
        assert triage_diff(d, "m.py") == "behavioral"

    def test_mixed_hunks_are_behavioral(self) -> None:
        d = _unified("# a\nx = 1\n", "# b\nx = compute(2)\n", "m.py")
        assert triage_diff(d, "m.py") == "behavioral"  # most-severe wins

    @pytest.mark.parametrize(
        "val", [None, "", "Binary files a/x and b/x differ\n", "--- a/m.py\n+++ b/m.py\n"]
    )
    def test_degenerate_inputs_are_unknown(self, val: str) -> None:
        assert triage_diff(val, "m.py") == "unknown"


class TestComputeOverwriteDiffs:
    """R2 — one diff + triage per flagged overwrite; only value-unverified files."""

    def test_one_diff_per_flagged_overwrite(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        ods = compute_overwrite_diffs(pkg, package_env["hub"], package_env["target"])
        assert {od.file_path for od in ods} == {".claude/agents/f.md"}
        od = ods[0]
        assert od.triage_hint == "behavioral"  # "F v1" -> "F v2 NEW": a non-comment body change
        assert "F v2 NEW" in od.diff_text  # the hub's incoming line
        assert "F v1" in od.diff_text  # the target's current line


class TestRedactSecrets:
    """R8 — secret-bearing diff lines are redacted before reaching the doc."""

    def test_redacts_secret_line_keeps_others(self) -> None:
        out = redact_secrets("safe line\n+AWS = AKIAIOSFODNN7EXAMPLE\nother\n")
        assert "AKIA" not in out
        assert "[REDACTED" in out
        assert "safe line" in out and "other" in out

    def test_clean_text_lines_preserved(self) -> None:
        assert redact_secrets("just\nsome\nlines") == "just\nsome\nlines"

    def test_empty_text(self) -> None:
        assert redact_secrets("") == ""


class TestBuildAssessmentDoc:
    """R5/R6 — disclaimer, consent-stakes ordering, backflow, scrubbing (all deterministic)."""

    def _doc(self) -> str:
        pkg = ChangePackage("/t", [_vu_item("a.md"), _vu_item("b.py")])
        ods = [
            OverwriteDiff("a.md", "-old\n+new\n", "cosmetic"),
            OverwriteDiff("b.py", "-x = 1\n+x = compute()\n", "behavioral"),
        ]
        interps = [
            Interpretation("a.md", "doc tweak", False, "none", 0.9, "cosmetic"),
            Interpretation(
                "b.py", "logic change", True, "callers may break", 0.4, "behavioral-blast-radius"
            ),
        ]
        return build_assessment_doc(pkg, ods, interps, room_summary="RV")

    def test_advisory_header_and_counted_disclaimer(self) -> None:
        doc = self._doc()
        assert "ADVISORY / target-overridable" in doc
        assert "could not be proven safe" in doc
        assert "read these 2 before merging" in doc  # counted (2 overwrites)
        assert "directs your attention; it does not certify safety" in doc

    def test_consent_stakes_ordering_and_cosmetic_still_present(self) -> None:
        doc = self._doc()
        assert doc.index("b.py") < doc.index("a.md")  # behavioral ranked above cosmetic
        assert "a.md" in doc  # cosmetic sorted lower, never dropped

    def test_backflow_section_honest_and_lists_flagged(self) -> None:
        doc = self._doc()
        tail = doc.split("Backflow candidates")[1]
        assert "may be better" in tail and "may be stale" in tail
        assert "b.py" in tail  # flagged backflow=True
        assert "/analyze-project" in tail

    def test_secret_scrubbed_in_doc(self) -> None:
        pkg = ChangePackage("/t", [_vu_item("s.cfg")])
        ods = [OverwriteDiff("s.cfg", "+AWS = AKIAIOSFODNN7EXAMPLE\n", "unknown")]
        interps = [Interpretation("s.cfg", "?", False, "n/a", 0.5, "benign")]
        doc = build_assessment_doc(pkg, ods, interps)
        assert "AKIA" not in doc
        assert "[REDACTED" in doc


class TestCaptureContentFree:
    """R7 — the content-free sinks (counts / package_report) never carry file bodies."""

    def test_counts_and_report_have_no_file_content(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        counts_str = str(pkg.counts())
        report = package_report(pkg)
        for body in ("F v2 NEW", "F v1", "D v2 HUB"):
            assert body not in counts_str
            assert body not in report


class TestChangeItemFieldRegression:
    """R2/qa-F5 — diff data is a SIBLING, so ChangeItem stays structurally unchanged."""

    def test_changeitem_fields_unchanged(self, package_env: dict) -> None:
        pkg = compute_package(package_env["hub"], package_env["target"], package_env["offer"])
        inert = _by_path(pkg, ".claude/agents/g.md")
        assert (inert.classification, inert.target_hash, inert.reason) == (
            "inert",
            None,
            "new file for the target",
        )
        diverged = _by_path(pkg, ".claude/agents/d.md")
        assert diverged.classification == "collision-diverged"
        assert diverged.drift_status == "modified"
        # No diff_text / triage_hint leaked onto ChangeItem.
        assert set(vars(inert)) == {
            "file_path",
            "classification",
            "hub_hash",
            "target_hash",
            "drift_status",
            "reason",
        }


# ── Review REV-20260523-125823 blocking findings ─────────────────────────────


class TestStageExcludesEscalated:
    """Scenario A backstop (independent): stage() refuses an escalated file even when it
    is still in package.stageable — the escalate-only guarantee is mechanical, not prose."""

    def test_excluded_file_is_never_written(self, stage_env: dict) -> None:
        target = stage_env["target"]
        result = stage(
            target,
            _stage_package(stage_env),  # CLAUDE.md is a stageable (value) item
            "DOC",
            "framework-update/exclude-test",
            template_root=stage_env["hub"],
            base_branch="main",
            exclude_paths={"CLAUDE.md"},  # escalated by the bridge → must be held back
        )
        assert set(result.files_staged) == {".claude/agents/new.md"}  # CLAUDE.md skipped
        assert (
            _g(target, "cat-file", "-e", f"{result.branch}:CLAUDE.md", check=False).returncode != 0
        )


class TestRedactSecretsFailClosed:
    """qa F2: redact_secrets must FAIL CLOSED (raise) when secret patterns are unavailable —
    the last line of defence since staging commits with --no-verify."""

    def test_raises_when_patterns_unavailable(self, monkeypatch) -> None:
        import scripts.distribute.assessment as asm

        monkeypatch.setattr(asm, "_SECRET_PATTERNS_LOADED", False)
        with pytest.raises(RuntimeError, match="Fail closed"):
            asm.redact_secrets("AWS = AKIAIOSFODNN7EXAMPLE")


@pytest.fixture
def deleted_drift_env(tmp_path: Path) -> dict:
    """A target that deliberately DELETED a framework file the hub still ships (drift deleted)."""
    target = tmp_path / "target"
    hub = tmp_path / "hub"
    rel = ".claude/agents/del.md"
    _write(target, rel, "DEL original")
    db = target / "metrics" / "evaluation.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    init_db(db)
    lineage_init(
        project_root=target,
        template_version="2.1.0",
        project_name="t",
        db_path=db,
        manifest_path=target / "framework-lineage.yaml",
        custodian_dir=target / ".claude" / "custodian",
    )
    data = manifest_read(target / "framework-lineage.yaml")
    data["custodian"] = {"accepts_distribution": True}
    (target / "framework-lineage.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
    (target / rel).unlink()  # deliberate deletion after baseline → drift "deleted"
    _write(hub, rel, "DEL hub v2")  # the hub still ships it → re-adding clobbers the deletion
    return {"target": target, "hub": hub, "offer": [rel], "rel": rel}


class TestDeletedDriftClassification:
    """qa F3: a file the target deliberately deleted, that the hub re-adds, is collision-diverged
    (assess) — never a silent inert re-addition that clobbers the deletion decision."""

    def test_deleted_then_hub_readds_is_collision_diverged(self, deleted_drift_env: dict) -> None:
        env = deleted_drift_env
        pkg = compute_package(env["hub"], env["target"], env["offer"])
        item = _by_path(pkg, env["rel"])
        assert item.drift_status == "deleted"
        assert item.target_hash is None
        assert item.classification == "collision-diverged"
        assert item not in pkg.stageable  # never auto-staged


@pytest.fixture
def none_drift_env(tmp_path: Path) -> dict:
    """A target whose narrowed ``tracked_paths`` never tracked a file it nonetheless customized.

    The second B1 trigger (REV-20260523-065900): under a narrowed ``tracked_paths`` the lineage
    engine is blind to the file, so ``drift_scan`` returns no entry (``drift_status is None``) even
    though the target's copy exists and differs from the hub. The floor must still flag it
    value-unverified — ``None`` drift proves nothing about ancestry, exactly like ``current``.
    """
    target = tmp_path / "target"
    hub = tmp_path / "hub"
    rel = ".claude/agents/u.md"
    _write(hub, rel, "U hub v2")  # the hub ships its version

    db = target / "metrics" / "evaluation.db"
    db.parent.mkdir(parents=True, exist_ok=True)
    init_db(db)
    lineage_init(
        project_root=target,
        template_version="2.1.0",
        project_name="t",
        db_path=db,
        manifest_path=target / "framework-lineage.yaml",
        custodian_dir=target / ".claude" / "custodian",
    )
    # Target dev customizes u.md AFTER init, but their tracked_paths only covers docs/ — lineage
    # never baselines or scans .claude/agents, so drift_scan reports nothing for u.md (None).
    _write(target, rel, "U customized by target dev")
    data = manifest_read(target / "framework-lineage.yaml")
    data["custodian"] = {"accepts_distribution": True}
    data["tracked_paths"] = ["docs"]  # narrowed: excludes .claude/agents/u.md
    (target / "framework-lineage.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8"
    )
    return {"target": target, "hub": hub, "offer": [rel], "rel": rel}


class TestNoneDriftClassification:
    """qa F5: an untracked (``tracked_paths``-narrowed) overwrite is value-unverified, not silent.

    Complements TestStaleBaselineRegression, which covers the ``drift_status == "current"`` arm of
    finding B1; this covers the ``drift_status is None`` arm.
    """

    def test_untracked_overwrite_is_value_unverified(self, none_drift_env: dict) -> None:
        env = none_drift_env
        pkg = compute_package(env["hub"], env["target"], env["offer"])
        item = _by_path(pkg, env["rel"])
        assert item.drift_status is None  # lineage never tracked it (tracked_paths narrowed)
        assert item.target_hash is not None  # but the target HAS the file
        assert item.target_hash != item.hub_hash  # and it differs from the hub
        assert item.classification == "value-unverified"  # floor flags it, never silent value
        assert item in pkg.requires_interpretation


class TestBoundPatterns:
    """B3: per-path accept/deny globs are bounded at load (fnmatch matching-cost DoS)."""

    def test_overlong_and_overcount_patterns_are_bounded(self) -> None:
        from scripts.distribute.change_package import (
            MAX_PATTERN_LEN,
            MAX_PER_PATH_PATTERNS,
            _bound_patterns,
        )

        overlong = "x" * (MAX_PATTERN_LEN + 1)
        patterns = ["ok.py", overlong] + ["*"] * (MAX_PER_PATH_PATTERNS + 50)
        bounded = _bound_patterns(patterns)
        assert "ok.py" in bounded
        assert overlong not in bounded  # over-long dropped
        assert len(bounded) <= MAX_PER_PATH_PATTERNS  # count capped

    def test_non_list_or_non_string_entries_dropped(self) -> None:
        from scripts.distribute.change_package import _bound_patterns

        assert _bound_patterns("not-a-list") == []
        assert _bound_patterns(None) == []
        assert _bound_patterns(["good", 123, None, "also-good"]) == ["good", "also-good"]
