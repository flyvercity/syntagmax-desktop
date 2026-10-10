"""Tests for ``syntagmax_desktop.git_branches`` (spec R4, E1/X1).

Each test builds a throwaway repository under a pytest ``tmp_path`` so the suite
never touches the developer's real checkout. We configure a local author identity
on every repo because committing requires one and the global config may be absent
on a clean CI runner.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from syntagmax_desktop.git_branches import (
    CheckoutRefused,
    checkout,
    current_branch,
    list_branches,
)


def _init_repo(path: Path) -> Repo:
    """Initialise a repository at ``path`` with a configured author and one commit."""
    repo = Repo.init(path)
    with repo.config_writer() as cfg:
        cfg.set_value('user', 'name', 'Test Reviewer')
        cfg.set_value('user', 'email', 'reviewer@example.com')
    (path / 'README.md').write_text('seed\n', encoding='utf-8')
    repo.index.add(['README.md'])
    repo.index.commit('initial commit')
    return repo


def test_list_branches_returns_created_branches(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    repo.create_head('feature-a')
    repo.create_head('feature-b')

    branches = list_branches(tmp_path)

    assert set(branches) == {repo.active_branch.name, 'feature-a', 'feature-b'}


def test_current_branch_reports_active_branch(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    repo.create_head('feature-a')
    repo.git.checkout('feature-a')

    assert current_branch(tmp_path) == 'feature-a'


def test_list_branches_empty_for_non_repo(tmp_path: Path) -> None:
    plain = tmp_path / 'not-a-repo'
    plain.mkdir()

    assert list_branches(plain) == []


def test_checkout_refused_on_dirty_tree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    repo.create_head('feature-a')
    # Introduce an uncommitted change to make the tree dirty.
    (tmp_path / 'README.md').write_text('seed\ndirty\n', encoding='utf-8')

    with pytest.raises(CheckoutRefused):
        checkout(tmp_path, 'feature-a')

    # The working tree must be left untouched on a refusal.
    assert repo.active_branch.name != 'feature-a'


def test_current_branch_detached_head_label(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    # Detach HEAD onto the current commit SHA.
    sha = repo.head.commit.hexsha
    repo.git.checkout(sha)

    label = current_branch(tmp_path)

    assert label == f'(HEAD detached at {sha[:7]})'


def test_checkout_switches_branch_on_clean_tree(tmp_path: Path) -> None:
    repo = _init_repo(tmp_path)
    repo.create_head('feature-a')

    checkout(tmp_path, 'feature-a')

    assert current_branch(tmp_path) == 'feature-a'
    assert repo.active_branch.name == 'feature-a'
