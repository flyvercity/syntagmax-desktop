# [ ] Task 1 — Core: `create_project` on a new submodule branch

**Spec**: `docs/specs/new-project.spec.md` (R11, C1–C9)
**Depends on**: nothing (Wave 0 — blocks Task 6).

## Objective

Add a public `create_project` entry point to `syntagmax.api` on a new branch inside the `syntagmax` submodule, wrapping `syntagmax.init_cmd.init_project` with safety guards, so the desktop app can scaffold a project through the public embedding surface.

## Files

- `syntagmax/src/syntagmax/api.py` (add `create_project`).
- `syntagmax/tests/test_api.py` (add tests).

## Guidance

- Create branch `feat/api-create-project` from the submodule's current pinned HEAD (`cca2a29`, on `more-gui-adaptations`). Do **not** branch from `main`.
- Implement `create_project(path: str | Path) -> Path` per the spec's hardened sketch:
  - resolve `target = Path(path).resolve()`;
  - refuse a filesystem root (`target == target.parent`) with `FatalError` (C6);
  - refuse when **either** `target / '.syntagmax' / 'config.toml'` **or** `target / 'config.toml'` exists, with `FatalError` (C3, dual-config);
  - `target.mkdir(parents=True, exist_ok=True)` (C4);
  - call `init_project(str(target))`, then create `target / 'REQ'` (C7);
  - on any exception after `.syntagmax/` was created by this call, `shutil.rmtree` the created `.syntagmax/` before re-raising (C5 rollback); only remove what this call created;
  - return `target / '.syntagmax' / 'config.toml'`.
- Import `FatalError` from `syntagmax.errors` and `init_project` from `syntagmax.init_cmd`. **Do not modify `init_project`.**

## Test requirements (C8)

In `syntagmax/tests/test_api.py`:
- scaffold into a `tmp_path`; assert `.syntagmax/config.toml`, `.syntagmax/project.syntagmax`, `.syntagmax/.gitignore`, and `REQ/` exist;
- assert `open_project(returned_path)` yields a `Session` whose `analyse()` runs without raising;
- assert a second `create_project` on the same path raises `FatalError`;
- assert `create_project` raises `FatalError` when a flat `config.toml` (no `.syntagmax/`) already exists in the target.

## Remote (critique E8)

Push `feat/api-create-project` to the `syntagmax` remote so the superproject's submodule pointer (Task 6) resolves for CI and fresh clones. Pushing is a remote action — flag it for confirmation; do not push silently.

## Demo

```
cd syntagmax && uv run pytest tests/test_api.py -k create_project -q
```
