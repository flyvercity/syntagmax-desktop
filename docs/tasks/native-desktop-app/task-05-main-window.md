# [ ] Task 5 — Main window, open flow, branch bar, reload & MRU

**Spec**: `docs/specs/native-desktop-app.spec.md` (R2, R2a, R3, R4, R9, P4)
**Depends on**: Task 4 (Wave 3 — shell for the panels).

## Objective

`main_window.py`: the `QMainWindow` shell — toolbar/menu with Open, Reload, a branch combo, a Recent Projects list, a tabbed panel stack, and a busy/status indicator; wires the `SessionWorker`.

## Files

- `src/syntagmax_desktop/views/main_window.py`, `src/syntagmax_desktop/settings_store.py` (QSettings-backed MRU), `tests/test_main_window.py`.

## Guidance

- Open action → `QFileDialog` (select `config.toml` or a folder; folder resolved per R2) → `worker.openProject`. On `opened(True)`, populate the branch combo via `git_branches.list_branches` (hide if `[]`) and enable the panel tabs; on `opened(False)`/`failed`, show a `QMessageBox` and stay in the empty state (R3).
- Branch combo change → `git_branches.checkout` (guarded) then re-open; a `CheckoutRefused` shows a non-fatal dialog.
- **Reload** action bound to `F5` re-opens the current project (R2a).
- **Recent Projects**: `settings_store.py` persists the last N project paths via `QSettings`; the menu lists them for one-click re-open (P4).
- Subscribe to `busyChanged` to drive a status-bar indicator and disable actions during a run.

## Test requirements

- `tests/test_main_window.py` (offscreen, `pytest-qt`): construct `MainWindow`, invoke open with a fixture path, `qtbot.waitSignal(worker.opened)`, assert tabs enabled and the branch combo populated; assert a successful open pushes the path into the MRU store.

## Demo

```
set QT_QPA_PLATFORM=offscreen
uv run pytest tests/test_main_window.py -q
uv run syntagmax-desktop   # open a project under syntagmax/example/
```
