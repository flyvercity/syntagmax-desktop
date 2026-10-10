# PR Review: main — Native Desktop App Implementation

**Reviewed**: 2026-10-10
**Author**: Boris Resnick
**Branch**: main
**Decision**: REQUEST CHANGES

## QA & Verification Guidance
- **Risk Assessment & Migration Notes**: The implementation introduces the initial PySide6 desktop reviewer application alongside cx_Freeze packaging configurations. The application operates in a strictly read-only mode with `allow_dirty_worktree=True` enabled by default. No database migrations, schema alterations, or environment variable modifications are introduced.
- **Behavioral Changes to Verify**:
  - Traceability panel child and parent artifact-type selectors must be populated when a project is opened, allowing the execution of traceability matrices.
  - Detached HEAD repositories must render a disabled `(HEAD detached at <short-sha>)` status in the branch bar without permitting branch switching.
  - Active worker operations must display a busy mask across all interactive UI controls, preventing queued background queries while long operations execute.
  - Relative Markdown images in artifact bodies must resolve correctly when a project is loaded via `<project>/.syntagmax/config.toml`.
- **Testing Hints for QA**:
  1. Open a valid project containing defined artifact types (e.g. `obsidian-driver`). Navigate to the Traceability tab and confirm that the Child and Parent dropdown combos contain artifact types (`REQ`, `SYS`), select distinct types, and verify that selecting "Run" generates the matrix table.
  2. In a test Git repository, detach the HEAD state (`git checkout <commit-sha>`) and open the project in the application. Confirm that the branch bar displays `(HEAD detached at <short-sha>)` with the combo control disabled.
  3. Trigger a project analysis on a large repository and verify that clicking tab buttons, typing in the artifact search field, and clicking the trace run button are blocked until the worker completes.

## Technical Summary
The implementation establishes a modular PySide6 application structure, a dedicated `SessionWorker` on a `QThread`, virtual models for scalable table and list rendering, and comprehensive cx_Freeze packaging. However, `TracePanel` artifact-type discovery is disconnected from the open workflow, detached HEAD state handling in the main window violates requirement R4, and the lack of interactive UI masking during worker execution violates requirement R9.

## Findings

### CRITICAL
None

### HIGH

- **Finding H-1: Traceability panel artifact types are never populated on project open (R6, R7)**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L256-L276`, `src/syntagmax_desktop/views/trace_panel.py#L143-L164`
  - **Category**: Correctness / Completeness
  - **Description**: While `core_facade.atypes(session)` was implemented and `TracePanel.set_atypes(atypes)` exists, `MainWindow` never invokes `core_facade.atypes`, has no signal or worker slot to fetch artifact types, and never calls `set_atypes` on the `TracePanel` instance. Consequently, the Child and Parent selectors in `TracePanel` remain perpetually empty when any project is opened in the desktop application. In `TracePanel.run_trace()`, `if not child or not parent: return` causes the run command to exit silently, rendering the traceability panel entirely inoperable in production. Unit tests in `tests/test_trace_panel.py` bypassed this integration gap by manually injecting mock types on a test stub.
  - **Remediation**: Expose an `atypesReady` signal or include `atypes` in the `opened` payload emitted by `SessionWorker`, retain a reference to `TracePanel` in `MainWindow`, and call `trace_panel.set_atypes(types)` upon project load.

- **Finding H-2: Detached HEAD state is neither displayed nor disabled in the branch bar (R4)**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L294-L320`, `src/syntagmax_desktop/git_branches.py#L58-L70`
  - **Category**: Correctness / Pattern Compliance
  - **Description**: Requirement R4 mandates that a detached HEAD state be displayed as `(HEAD detached at <short-sha>)` with switching disabled. In `MainWindow._populate_branches()`, `branches` is populated strictly from `git_branches.list_branches()`, which returns local branch heads (`repo.heads`). Because `(HEAD detached at <short-sha>)` is not in `repo.heads`, `self._branch_combo.setCurrentText(current)` is skipped, leaving the combo displaying whatever branch is at index 0. Furthermore, `self._branch_combo.setEnabled(False)` is never invoked. Attempting to switch branches prompts a modal refusal error from GitPython rather than presenting the specified disabled state.
  - **Remediation**: In `MainWindow._populate_branches()`, detect when `git_branches.current_branch()` returns a detached HEAD label or when `repo.head.is_detached` is true. Insert the detached HEAD label into `_branch_combo`, set it as current, and disable the combo.

- **Finding H-3: UI controls and panels are not busy-masked during background worker operations (R9, critique E5)**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L284-L290`
  - **Category**: Performance / Correctness
  - **Description**: Requirement R9 and critique E5 stipulate that because `SessionWorker` serialises all operations across a single background thread, long-running operations (`analyse()`, `trace()`) must busy-mask the interface so that secondary search, filter, or trace requests are not queued behind them. `MainWindow._on_busy_changed()` only disables `_open_action`, `_reload_action`, and `_branch_combo`. The tab widget, the "Run analysis" button, the "Run" trace button, and the artifact browser search bar remain fully enabled. Keystrokes entered in `_search_box` during a long analysis dispatch debounced `runSearch` requests into the worker queue, queuing unneeded operations behind active jobs.
  - **Remediation**: In `MainWindow._on_busy_changed(busy)`, disable the central tab widget (`self._tabs.setEnabled(not busy)`) or apply a modal busy overlay widget over the central container while operations are in flight.

### MEDIUM

- **Finding M-1: Project root resolution in `MainWindow._project_root_for` misresolves `.syntagmax/config.toml` (R8, critique E8)**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L224-L233`
  - **Category**: Correctness
  - **Description**: `_project_root_for` resolves `Path(path).parent` when given a file path. When a user opens a project via `<project>/.syntagmax/config.toml`, `candidate.parent` resolves to `<project>/.syntagmax` rather than `<project>`. This directory is passed to `BrowserPanel.set_project_root()` and used as the base URL for `QTextBrowser`. Consequently, relative image links in Markdown documents (e.g. `![diagram](docs/assets/diagram.png)`) attempt to resolve against `<project>/.syntagmax/docs/assets/diagram.png` and fail to render.
  - **Remediation**: Check whether `candidate.parent.name == '.syntagmax'`; if so, set the project root to `candidate.parent.parent`.

- **Finding M-2: File mode in `MainWindow.open_project_dialog` precludes folder selection (R2)**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L206-L212`
  - **Category**: Correctness / Completeness
  - **Description**: Requirement R2 specifies that the user can pick either a project's `.syntagmax/config.toml` or a folder containing it through a native dialog. `open_project_dialog` explicitly sets `dialog.setFileMode(QFileDialog.FileMode.ExistingFile)`. In Qt, this mode restricts selection exclusively to files, preventing users from selecting project folders despite `core_facade.open` having built-in candidate resolution for directory paths.
  - **Remediation**: Provide an "Open Project Folder…" action alongside "Open Project File…", or configure the dialog to permit directory selection.

- **Finding M-3: Worker thread teardown timeout in `MainWindow.closeEvent` risks hard process termination**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L372-L377`
  - **Category**: Maintainability / Qt Lifecycle
  - **Description**: In `closeEvent`, `self._thread.quit()` is followed by `self._thread.wait(5000)`. Because the worker executes blocking Python code inside slots, `_thread.quit()` does not preempt running Python bytecode. If an analysis or trace run exceeds 5,000 ms, `wait()` returns `False` and timeout occurs. The window proceeds with destruction while `_thread` remains running, which causes Qt to invoke `qFatal` ("QThread: Destroyed while thread is still running") and terminate the process abnormally.
  - **Remediation**: Evaluate the return value of `self._thread.wait(5000)`. If the worker fails to stop, decouple the thread from `MainWindow`'s parent hierarchy or warn the user before closing.

- **Finding M-4: Incomplete test coverage for `SessionWorker` and integration flows**
  - **Location**: `tests/test_session_worker.py`, `tests/test_main_window.py`
  - **Category**: Completeness / Test Adequacy
  - **Description**: `test_session_worker.py` only verifies `openProject` and `runAnalyse`. It lacks test cases for `runTrace`, `exportTrace`, `runQuery`, and `runSearch`. Additionally, `tests/test_main_window.py` does not test detached HEAD detection, reload triggers (`F5`), or panel interactions during busy states.
  - **Remediation**: Add unit tests in `test_session_worker.py` verifying each slot and signal round-trip via `qtbot.waitSignal`. Add test assertions in `test_main_window.py` covering detached HEAD handling and reload actions.

### LOW

- **Finding L-1: Ineffective exception catch around asynchronous signal emit in `TracePanel.export_trace`**
  - **Location**: `src/syntagmax_desktop/views/trace_panel.py#L188-L194`
  - **Category**: Correctness
  - **Description**: `TracePanel.export_trace()` encloses `self._exportRequested.emit(...)` in a `try...except PermissionError` block. Because `_exportRequested` is connected via `Qt.ConnectionType.QueuedConnection`, `emit()` queues the event and returns immediately without raising. The worker catches `PermissionError` and emits `failed`, rendering this local `try/except` dead code.
  - **Remediation**: Remove the dead `try...except PermissionError` block from `TracePanel.export_trace()` and rely on the worker's `failed` signal.

- **Finding L-2: Unparented `QAction` instances accumulate on menu rebuild in `MainWindow._refresh_recent_menu`**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L354-L363`
  - **Category**: Maintainability / Qt Memory
  - **Description**: `_refresh_recent_menu` constructs `QAction(path, self)` with `MainWindow` as parent. Calling `self._recent_menu.clear()` removes the actions from the menu visual hierarchy but does not delete the underlying `QObject` instances, creating orphaned objects on each project load.
  - **Remediation**: Parent the actions to `self._recent_menu` or explicitly invoke `deleteLater()` on removed actions.

- **Finding L-3: Retained placeholder widget allocations in `MainWindow.set_panel`**
  - **Location**: `src/syntagmax_desktop/views/main_window.py#L196-L204`
  - **Category**: Maintainability / Qt Memory
  - **Description**: `self._tabs.removeTab(index)` detaches placeholder widgets without calling `deleteLater()`, leaving unused label widgets in memory.
  - **Remediation**: Invoke `self._panels[name].deleteLater()` when substituting placeholders.

- **Finding L-4: Potential `KeyError` in `core_facade.atypes` on non-standard metamodel configurations**
  - **Location**: `src/syntagmax_desktop/core_facade.py#L85-L96`
  - **Category**: Correctness / Defensive Programming
  - **Description**: `core_facade.atypes()` assumes that any truthy `metamodel` contains an `'artifacts'` dictionary (`return sorted(metamodel['artifacts'].keys())`). If a configured metamodel lacks the `'artifacts'` key, a `KeyError` is raised rather than falling back to `session.query()`.
  - **Remediation**: Use `if isinstance(metamodel, dict) and 'artifacts' in metamodel:` before indexing.

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped (no `mypy`/`pyright` configured in dependencies) |
| Lint | Pass (`uv run ruff check src tests` passed with 0 errors) |
| Tests | Pass (`uv run pytest` passed 56/56 in 4.64s) |
| Build | Skipped (packaged via cx_Freeze `setup_freeze.py`) |

## Files Reviewed
- `pyproject.toml` — Modified
- `setup_freeze.py` — Added
- `src/syntagmax_desktop/__init__.py` — Added
- `src/syntagmax_desktop/__main__.py` — Added
- `src/syntagmax_desktop/app.py` — Added
- `src/syntagmax_desktop/logging_setup.py` — Added
- `src/syntagmax_desktop/core_facade.py` — Added
- `src/syntagmax_desktop/git_branches.py` — Added
- `src/syntagmax_desktop/session_worker.py` — Added
- `src/syntagmax_desktop/settings_store.py` — Added
- `src/syntagmax_desktop/models/__init__.py` — Added
- `src/syntagmax_desktop/models/artifact_list_model.py` — Added
- `src/syntagmax_desktop/models/trace_model.py` — Added
- `src/syntagmax_desktop/views/__init__.py` — Added
- `src/syntagmax_desktop/views/main_window.py` — Added
- `src/syntagmax_desktop/views/analysis_panel.py` — Added
- `src/syntagmax_desktop/views/browser_panel.py` — Added
- `src/syntagmax_desktop/views/trace_panel.py` — Added
- `src/syntagmax_desktop/widgets/__init__.py` — Added
- `src/syntagmax_desktop/widgets/markdown_view.py` — Added
- `tests/test_analysis_panel.py` — Added
- `tests/test_api_import.py` — Added
- `tests/test_browser_panel.py` — Added
- `tests/test_core_facade.py` — Added
- `tests/test_git_branches.py` — Added
- `tests/test_main_window.py` — Added
- `tests/test_session_worker.py` — Added
- `tests/test_trace_panel.py` — Added
- `docs/reference/desktop-app.md` — Added
- `docs/reference/packaging.md` — Added
- `README.md` — Modified
