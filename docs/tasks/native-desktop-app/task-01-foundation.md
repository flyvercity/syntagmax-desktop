# [ ] Task 1 — Project foundation, submodule advance & crash log

**Spec**: `docs/specs/native-desktop-app.spec.md` (R1, R9a, R10–R14, R17)
**Depends on**: none (Wave 0 — blocks everything).

## Objective

Make `syntagmax-desktop` a runnable PySide6 app skeleton on the correct core revision, with crash telemetry installed from the first line.

## Files

- `syntagmax` submodule (advance), `pyproject.toml`, `src/syntagmax_desktop/__init__.py`, `src/syntagmax_desktop/__main__.py`, `src/syntagmax_desktop/app.py`, `src/syntagmax_desktop/views/__init__.py`, `src/syntagmax_desktop/views/main_window.py` (empty shell), `src/syntagmax_desktop/logging_setup.py`, `tests/test_api_import.py`.

## Guidance

- **Advance the `syntagmax` submodule to the exact commit `cca2a29` on branch `more-gui-adaptations`** (the commit `syntagmax-gui` points to; verified `feat(api): expose Session.trace and Session.publish facade methods`). Record the tracking branch in `.gitmodules`/notes. Confirm `from syntagmax.api import open_project` imports.
- `pyproject.toml`: `dependencies = ["PySide6", "gitpython", "syntagmax"]`; `[tool.uv.sources] syntagmax = { path = "syntagmax", editable = true }`; `[project.scripts] syntagmax-desktop = "syntagmax_desktop.app:main"`; hatchling wheel target `src/syntagmax_desktop`; `[tool.pytest.ini_options] pythonpath = ["src"]`; ruff; dev group `pytest`, `pytest-qt`, `cx-freeze`.
- `app.py`: `main()` creates the `QApplication`, installs the `sys.excepthook` crash logger (see `logging_setup.py`), shows an empty `MainWindow`, runs the event loop. `__main__.py` calls `main()` so `python -m syntagmax_desktop` works.
- `logging_setup.py`: `install_excepthook()` writes uncaught exceptions (traceback + timestamp) to `%LOCALAPPDATA%/Syntagmax/logs/crash.log` on Windows, else the platform user-data dir; creates the directory; chains to the previous hook. This matters because the frozen `base="gui"` build detaches stdio (R9a/E4).

## Test requirements

- `tests/test_api_import.py`: assert `from syntagmax.api import open_project` succeeds (R12/E9 regression guard).
- Optional offscreen smoke test: `MainWindow()` constructs without error under `QT_QPA_PLATFORM=offscreen`.

## Demo

```
uv sync
uv run pytest tests/test_api_import.py -q
uv run syntagmax-desktop   # opens an empty window
```
