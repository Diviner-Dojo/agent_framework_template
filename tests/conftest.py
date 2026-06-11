"""Shared pytest configuration.

**Git-subprocess isolation.** Several test modules (``test_distribute``, ``test_lineage``) create
throwaway git repositories in tmp dirs and run real ``git`` commands against them. When pytest
itself runs *inside a git hook* — e.g. the pre-commit quality gate — git exports ``GIT_DIR`` /
``GIT_INDEX_FILE`` / ``GIT_WORK_TREE`` / ``GIT_PREFIX`` into the environment for the whole commit.
Those are inherited by the tests' ``git -C <tmp>`` subprocesses and **override the ``-C`` target**,
so the commands silently operate on the outer repository and fail (``git add`` exits 128). The
suite then passes standalone but fails only inside the commit hook.

Stripping every ``GIT_*`` variable for the test session makes each git subprocess resolve its repo
from its own ``cwd`` / ``-C`` argument again — restoring hermeticity. Tests configure the identity
they need per-repo (``git config user.email`` …), so they rely on nothing from the inherited git
environment.
"""

from __future__ import annotations

import os

import pytest


@pytest.fixture(scope="session", autouse=True)
def _isolate_git_environment() -> None:
    """Remove inherited ``GIT_*`` env vars so test git subprocesses stay hermetic.

    See the module docstring: without this, the suite passes standalone but the pre-commit hook —
    which runs pytest while ``GIT_DIR`` etc. are set — breaks every test that shells out to git.
    """
    for key in [k for k in os.environ if k.startswith("GIT_")]:
        os.environ.pop(key, None)
