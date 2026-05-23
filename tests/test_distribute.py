"""Tests for the /distribute capability (scripts/distribute/).

Covers the three building blocks with a temp-git fixture:

- repo_safety_check — the opt-in HARD GATE and skip-if-busy git-state check.
- change_package — value / inert / collision-pinned / collision-diverged classification.
- stage_branch — fresh branch off main, copies only stageable files, never pushes, never
  touches main, restores the original branch, rolls back cleanly on failure.
"""

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
from scripts.distribute.change_package import (  # noqa: E402
    ChangeItem,
    ChangePackage,
    compute_package,
)
from scripts.distribute.repo_safety_check import (  # noqa: E402
    baseline_gate_green,
    repo_safety_check,
)
from scripts.distribute.stage_branch import detect_base_branch, stage  # noqa: E402
from scripts.init_db import init_db  # noqa: E402
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
        assert _by_path(pkg, ".claude/agents/f.md").classification == "value"
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
        assert counts["value"] == 1
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
