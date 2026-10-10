# [ ] Task 2 — Core facade (UI-agnostic)

**Spec**: `docs/specs/native-desktop-app.spec.md` (R2, R5–R8, R7 encapsulation, E7)
**Depends on**: Task 1 (Wave 1 — parallel with Task 3).

## Objective

`core_facade.py`: a thin, UI-agnostic wrapper over `syntagmax.api` for open, analyse, trace, export, atype discovery, query, and search.

## Files

- `src/syntagmax_desktop/core_facade.py`, `tests/test_core_facade.py`.

## Guidance

- `open(config_path) -> Session` via `open_project(..., options=Options(allow_dirty_worktree=True))` — **`allow_dirty_worktree=True` is the default** so a reviewer can open ordinary working copies with untracked/edited files (P1/X2). Resolve a picked folder to `<folder>/.syntagmax/config.toml` then `<folder>/config.toml` (R2).
- `analyse(session) -> AnalysisResult`; `trace(session, child, parent, *, direction='forward', flat=False) -> TraceResult` — `direction` (`'forward'`/`'reverse'`) and `flat` are **orthogonal** (E2/X3).
- `export_trace(result, path, delimiter) -> None`: call `render_trace(result, delimiter=delimiter)`; write CSV with `encoding='utf-8-sig'` (BOM for Excel), TSV with `utf-8`; let `PermissionError`/`OSError` propagate for the worker to surface (E7).
- `atypes(session) -> list[str]`: encapsulate `session._config.metamodel['artifacts']` access here (dict keyed by type name → `sorted(keys)`); fall back to `sorted({v.atype for v in session.query()})` so the UI never touches core internals (E2 encapsulation).
- `query`/`search` passthroughs. Let `FatalError`/`RMSException` propagate.

## Test requirements

- `tests/test_core_facade.py` against a fixture copied from `syntagmax/example/`: `analyse` returns an `AnalysisResult`; `trace` returns expected `header`/`rows`; `atypes` is non-empty; `export_trace` writes a CSV whose bytes **start with the UTF-8 BOM** (`\xef\xbb\xbf`) and a TSV without it.

## Demo

```
uv run pytest tests/test_core_facade.py -q
```
