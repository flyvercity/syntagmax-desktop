"""Git branch inspection and guarded checkout for Syntagmax Desktop (spec R4, E1/X1).

The reviewer app needs to list local branches, report the current branch, and
switch branches safely. Every operation degrades gracefully: a non-repository
yields an empty branch list so the caller can hide the control, a detached HEAD
reports a descriptive label instead of raising, and a checkout refuses to run
against a dirty tree. On Windows a crashed or interrupted git process can leave
a stale ``.git/index.lock`` behind; we remove it, and we translate low-level
failures into a typed error so the UI can present a clean message.
"""

from __future__ import annotations

from pathlib import Path

from git import GitCommandError, InvalidGitRepositoryError, NoSuchPathError, Repo


class GitBranchError(Exception):
    """Base class for recoverable git branch errors surfaced to the UI."""


class CheckoutRefused(GitBranchError):
    """Raised when a checkout is refused before any mutation is attempted.

    This covers a dirty working tree (uncommitted changes or conflicting
    untracked files) and a detached HEAD that cannot switch cleanly. The repository
    is left untouched.
    """


class CheckoutFailed(GitBranchError):
    """Raised when git refuses or fails to complete an attempted checkout.

    This wraps ``GitCommandError`` and Windows permission or file-lock failures so
    the caller never has to handle library-specific exceptions directly.
    """


def _open(path: str | Path) -> Repo:
    """Open the repository that contains ``path``, searching parent directories."""
    return Repo(path, search_parent_directories=True)


def list_branches(path: str | Path) -> list[str]:
    """Return the names of the local branches for the repository at ``path``.

    Returns an empty list when ``path`` is not inside a git repository so that the
    caller can hide the branch control rather than report an error.
    """
    try:
        repo = _open(path)
    except (InvalidGitRepositoryError, NoSuchPathError):
        return []
    return [head.name for head in repo.heads]


def current_branch(path: str | Path) -> str:
    """Return a human-readable label for the current branch of the repo at ``path``.

    When HEAD is detached (a tag checkout, a mid-rebase state, or a bare commit
    checkout) ``repo.active_branch`` raises ``TypeError``, so we guard
    ``repo.head.is_detached`` first and return ``(HEAD detached at <short-sha>)``.
    """
    repo = _open(path)
    if repo.head.is_detached:
        short_sha = repo.head.commit.hexsha[:7]
        return f'(HEAD detached at {short_sha})'
    return repo.active_branch.name


def _is_dirty(repo: Repo) -> bool:
    """Return ``True`` when the working tree has uncommitted or conflicting changes.

    A dirty tree is any staged or unstaged change to tracked files, as well as
    untracked files that would be overwritten by a checkout. We treat all
    untracked files as a conflict risk because git refuses to overwrite them.
    """
    return repo.is_dirty(index=True, working_tree=True, untracked_files=True)


def _clear_stale_lock(repo: Repo) -> None:
    """Remove a stale ``.git/index.lock`` left behind by an interrupted git process.

    On Windows an interrupted or crashed git invocation can leave the index lock in
    place, which blocks every subsequent operation. We remove it defensively; any
    failure to do so is swallowed because the lock may legitimately belong to a
    concurrent process.
    """
    lock = Path(repo.git_dir) / 'index.lock'
    try:
        lock.unlink(missing_ok=True)
    except OSError:  # pragma: no cover - the lock may belong to a live process
        pass


def checkout(path: str | Path, name: str) -> None:
    """Switch the repository at ``path`` to the local branch ``name``.

    Refuses with :class:`CheckoutRefused` when the working tree is dirty, or when
    HEAD is detached and therefore cannot switch cleanly, leaving the repository
    untouched. Translates ``GitCommandError`` and Windows permission or lock
    failures into :class:`CheckoutFailed`, and never leaves a stale
    ``.git/index.lock`` behind (E1/X1).
    """
    repo = _open(path)

    if _is_dirty(repo):
        raise CheckoutRefused(
            f'Refusing to switch to {name!r}: the working tree has uncommitted changes or conflicting untracked files.'
        )

    if repo.head.is_detached:
        raise CheckoutRefused(
            f'Refusing to switch to {name!r}: HEAD is detached and cannot switch cleanly.'
        )

    try:
        repo.git.checkout(name)
    except GitCommandError as exc:
        _clear_stale_lock(repo)
        raise CheckoutFailed(f'git refused to switch to {name!r}: {exc}') from exc
    except (OSError, PermissionError) as exc:
        _clear_stale_lock(repo)
        raise CheckoutFailed(f'Could not switch to {name!r} because of a file-system error: {exc}') from exc
