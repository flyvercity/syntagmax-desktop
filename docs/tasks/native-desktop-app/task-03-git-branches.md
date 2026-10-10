# [ ] Task 3 — Git branch logic

**Spec**: `docs/specs/native-desktop-app.spec.md` (R4, E1/X1)
**Depends on**: Task 1 (Wave 1 — parallel with Task 2).

## Objective

`git_branches.py`: list local branches, report the current branch, and perform a safe, guarded checkout; handle non-repo, dirty, detached-HEAD, and Windows file-lock states gracefully.

## Files

- `src/syntagmax_desktop/git_branches.py`, `tests/test_git_branches.py`.

## Guidance

- Use `gitpython` (`Repo(path, search_parent_directories=True)`).
- `list_branches(path) -> list[str]`: local heads; return `[]` for a non-repo (`InvalidGitRepositoryError`) so the caller hides the control.
- `current_branch(path) -> str`: guard `repo.head.is_detached` **before** `repo.active_branch` (which raises `TypeError` when detached); return `(HEAD detached at <short-sha>)` for detached/tag/rebase states.
- `checkout(path, name) -> None`: **refuse** on a dirty tree (uncommitted changes or conflicting untracked files) with a typed `CheckoutRefused` error; refuse when HEAD is detached-and-cannot-switch-cleanly; catch `GitCommandError` and Windows permission/lock failures, re-raising a typed error, and never leave a stale `.git/index.lock` (E1/X1).

## Test requirements

- `tests/test_git_branches.py` with temp repos: init + create branches → `list_branches` returns them and `current_branch` is correct; non-repo → `list_branches == []`; dirty tree → `checkout` raises `CheckoutRefused`; **detached HEAD → `current_branch` returns the `(HEAD detached ...)` label and does not raise**.

## Demo

```
uv run pytest tests/test_git_branches.py -q
```
