# [ ] Task 4 — Desktop: main window command, picker, safety checks, auto-open

**Spec**: `docs/specs/new-project.spec.md` (R3, R4, R5, R5a, R5b, R6, R7a)
**Depends on**: Task 3 (worker slot/signal). Final end-to-end needs Task 6.

## Objective

Wire the New Project user flow into `MainWindow`: the action, directory picker, safety checks, dispatch, auto-open, first-run hint, Reveal Project Folder, and the busy action-lockout.

## Files

- `src/syntagmax_desktop/views/main_window.py`.
- `tests/test_main_window.py` (extend).

## Guidance

- `_build_actions`: add `self._new_action` (`QKeySequence.StandardKey.New` → `new_project_dialog`) and `self._reveal_action` (disabled until a project opens → `reveal_project_folder`).
- `_build_toolbar` / `_build_menu`: add New Project before Open; add Reveal Project Folder to the File menu.
- `_connect_worker`: connect `self._worker.created` → `self._on_created`.
- `_on_busy_changed`: also disable `_new_action`, `_open_action`, `_reload_action` whilst busy (R7a).
- `new_project_dialog`: native `getExistingDirectory` with a guiding title; refuse an existing project at **either** config location (offer Open); guard `any(target.iterdir())` against `OSError` (surface a non-fatal dialog); warn on non-empty with **`No` as the default button**; dispatch `createProject` via queued `QMetaObject.invokeMethod`.
- `reveal_project_folder`: `QDesktopServices.openUrl(QUrl.fromLocalFile(self._project_root_for(self._current_path)))`.
- `_on_created`: open the **project root** (`Path(config_path).parent.parent`) via `open_path` so the MRU stores a folder (E9); the first-run hint (R5a) rides the normal open path when artifact count is zero.
- Import `QDesktopServices` (`PySide6.QtGui`) and `QUrl` (`PySide6.QtCore`).

## Test requirements (R8)

With an injected `SettingsStore(QSettings(...))` scoped to a temp INI and `QT_QPA_PLATFORM=offscreen`:
- empty folder → dispatches `createProject`; on `created`, the project opens and the project **root** is recorded in MRU;
- refusal branch offers Open for both `.syntagmax/config.toml` **and** flat `config.toml`;
- non-empty warning branch blocks dispatch unless confirmed;
- a folder-inspection `OSError` surfaces an error dialog rather than raising;
- New/Open/Reload are disabled while the worker is busy.

## Demo

```
uv run syntagmax-desktop
```
Then File → New Project… into an empty folder; the app scaffolds and opens it, and Reveal Project Folder opens it in the file manager.
