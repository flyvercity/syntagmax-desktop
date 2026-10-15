# [ ] Task 6 — Submodule pointer + full verification

**Spec**: `docs/specs/new-project.spec.md` (R10, Task 6)
**Depends on**: Task 1 (pushed), Task 3, Task 4.

## Objective

Point the superproject's `syntagmax` submodule at the new branch commit and verify the whole feature end-to-end.

## Files

- `.gitmodules` is unchanged; the submodule **gitlink** (pointer) is updated.

## Guidance

- Only after Task 1 is committed **and pushed** on `feat/api-create-project` (critique E8 — an unpushed commit breaks CI and fresh clones), update the superproject's submodule reference to that commit so `uv run` resolves the new `create_project`.
- Run `uv sync`, then `uv run pytest` for the desktop app, and `cd syntagmax && uv run pytest` for the core suite.
- Confirm no regression in the v1 review/trace/branch/open flows (R10).

## Test requirements

- Full `uv run pytest` green on both the desktop app and the core.
- Manual: `uv run syntagmax-desktop`, New Project into an empty folder scaffolds and opens; refusal and non-empty warning behave per R4.

## Demo

```
uv sync
uv run pytest -q
cd syntagmax && uv run pytest -q
```
