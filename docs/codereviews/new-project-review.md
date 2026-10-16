# Local Code Review: new-project — Create a New Project from the Desktop App

**Reviewed**: 2026-10-15
**Author**: Boris Resnick <boris.resnick@gmail.com>
**Branch**: `new-project` (commit `133d9c1`) on superproject; `feat/api-create-project` (commit `a1bef0c`) on `syntagmax` submodule
**Decision**: REQUEST CHANGES

## QA & Verification Guidance
- **Risk Assessment & Migration Notes**:
  - Submodule pointer dependency: Commit `133d9c1` updates the `syntagmax` submodule to commit `a1bef0c`. That commit is currently local only on branch `feat/api-create-project` in `./syntagmax`. It MUST be pushed to the remote `syntagmax` repository before this superproject branch is pushed or shared, or `git submodule update` will fail in CI pipelines and clean checkouts.
  - Filesystem safety: The feature introduces the first write capability into the desktop application. Writes are strictly scoped to one-time project bootstrapping (`.syntagmax/config.toml`, `.syntagmax/project.syntagmax`, `.syntagmax/.gitignore`, and `REQ/`). No artifact mutation, Git commits, or repository pushes are performed.
  - Metamodel template fix: The core submodule commit fixes a previously broken starter metamodel template in `syntagmax.init_cmd` (`id is string` rather than `attribute id is mandatory string`), ensuring newly initialised projects open and analyse cleanly.
- **Behavioral Changes to Verify**:
  - File menu and main toolbar contain the new "New Project…" action (shortcut `Ctrl+N`), positioned before "Open Project…".
  - File menu contains the read-only "Reveal Project Folder" action, which is enabled only when a project is open and opens the operating system file manager at the project root.
  - Selecting an existing Syntagmax project (with either `.syntagmax/config.toml` or root `config.toml`) prompts whether to open the project instead of re-scaffolding.
  - Selecting a non-empty, non-project directory displays a confirmation warning with the `No` button selected by default.
  - Selecting an unreadable or permission-denied directory catches the operating system error and presents a critical error dialogue without crashing the application.
  - During project creation and long worker tasks, "New Project…", "Open Project…", and "Reload" are disabled.
  - Recent Projects persists the project root directory rather than the internal `.syntagmax/config.toml` path.
- **Testing Hints for QA**:
  1. Trigger "New Project…" and choose a clean empty directory. Verify that `.syntagmax/config.toml`, `.syntagmax/project.syntagmax`, `.syntagmax/.gitignore`, and the `REQ/` folder are created, the project opens automatically, and the Recent Projects menu lists the project folder.
  2. With the newly created project open, trigger "Reveal Project Folder" from the File menu and verify that Explorer or the operating system file manager opens focused on the root project directory.
  3. Attempt "New Project…" on the same folder. Verify that a dialogue prompts to open the existing project rather than overwriting. Test again with a folder containing only a flat `config.toml`.
  4. Attempt "New Project…" on a directory containing arbitrary non-project files (e.g. text documents). Verify the warning dialogue appears with `No` focused by default. Pressing `Enter` must dismiss without scaffolding.
  5. Attempt "New Project…" on a restricted directory (e.g. system folder with denied permissions) and confirm that an access error dialogue appears without an unhandled exception or application termination.

> Note: Product-audience narrative (shipped value, deferred items, next iteration) is
> **not** part of the review — it is posted separately by the `Finalize` command.

## Technical Summary
The implementation delivers a clean, well-architected project bootstrapping workflow that strictly honours the separation between core library and desktop host. Submodule commit `a1bef0c` resolves the long-standing invalid metamodel template bug in `init_project`, exposes a robust `create_project` function in `syntagmax.api` with dual-config collision detection, filesystem root rejection, and atomic rollback, whilst the desktop changes correctly marshal writes to `SessionWorker` off the UI thread and normalise recent project paths to the project root. However, the changes cannot be approved in their current state because the submodule commit has not been pushed to its upstream remote, which will break CI and downstream clones, and the mandatory documentation updates required by specification Task 5 and repository guidelines were omitted.

## Findings

### CRITICAL
None

### HIGH

- **H-1: Submodule commit `a1bef0c` is local only and unpushed to upstream remote (`syntagmax`)**
  - **Category**: Completeness / Operational Readiness
  - **Files**: `syntagmax` (submodule reference `a1bef0c`)
  - **Description**: Commit `133d9c1` updates the `syntagmax` submodule reference to commit `a1bef0c` on branch `feat/api-create-project`. This submodule branch is currently present only in the local working repository and has not been pushed to `origin`. Any CI run, remote clone, or peer checkout executing `git submodule update` will immediately fail with an unresolvable commit error.
  - **Required Action**: Push branch `feat/api-create-project` to the `syntagmax` remote repository before the superproject branch is pushed or merged.

- **H-2: Missing documentation updates in `README.md` and `docs/reference/desktop-app.md`**
  - **Category**: Completeness / Pattern Compliance
  - **Files**: `README.md`, `docs/reference/desktop-app.md`
  - **Description**: Task 5 of `docs/specs/new-project.spec.md` (Requirement R9) and project guidelines require documentation updates across both `README.md` and `docs/reference/` pages for every specification. Commit `133d9c1` omitted these documentation changes completely. `README.md` still states under "Read-only scope" that there are "no create, edit, or delete controls anywhere in v1", which is now inaccurate, and neither document mentions the New Project action, the directory picker validation workflow, or the Reveal Project Folder action.
  - **Required Action**: Complete Task 5 by updating `README.md` to clarify the bounded bootstrap write scope alongside the read-only reviewer mode, and add reference documentation for the New Project and Reveal Project Folder features to `docs/reference/desktop-app.md`.

### MEDIUM

- **M-1: Incomplete UI action lockout for Recent Projects menu during worker busy state**
  - **Category**: Correctness / Maintainability
  - **Files**: `src/syntagmax_desktop/views/main_window.py`
  - **Description**: In `MainWindow._on_busy_changed`, `_new_action`, `_open_action`, and `_reload_action` are disabled whilst `busy` is true. However, `self._recent_menu` remains enabled. A user can trigger an item from the Recent Projects menu while `createProject` or `runAnalyse` is actively executing. This invokes `open_path`, immediately overwriting `self._current_path` on the UI thread and queueing an `openProject` invocation behind the active task, leading to state desynchronisation.
  - **Recommended Action**: Disable `self._recent_menu` in `_on_busy_changed` whenever `busy` is true, or check `self._worker` busy status before executing `open_path` from recent actions.

- **M-2: Omission of first-run onboarding guidance for zero-artifact scaffolded projects**
  - **Category**: Completeness / User Experience
  - **Files**: `src/syntagmax_desktop/views/main_window.py`, `src/syntagmax_desktop/views/browser_panel.py`, `src/syntagmax_desktop/views/analysis_panel.py`
  - **Description**: Requirement R5a states that opening a scaffolded project with zero artifacts should present a lightweight onboarding hint directing the reviewer to place Markdown specification files under `REQ/`. The committed implementation relies solely on the default empty panel states (`Select an artifact to view its detail` in the browser panel, and standard metrics in analysis), leaving a newly bootstrapped project without explicit contextual guidance explaining where and how to populate artifacts.
  - **Recommended Action**: Add an informative empty-state message or placeholder banner in the Browser panel when `query()` returns zero artifacts, explaining that the project was scaffolded and directing the reviewer to create requirement files in `REQ/`.

### LOW

- **L-1: Missing automated test for busy action lockout on menu actions**
  - **Category**: Completeness / Testing Strategy
  - **Files**: `tests/test_main_window.py`
  - **Description**: Requirement R8 and Task 4 specify tests asserting that `_new_action`, `_open_action`, and `_reload_action` are disabled whilst the worker is busy. Although the logic is implemented in `MainWindow._on_busy_changed`, no unit test in `tests/test_main_window.py` verifies this lockout behaviour.
  - **Recommended Action**: Add a unit test in `tests/test_main_window.py` that connects to `worker.busyChanged` or simulates a busy worker state and asserts that `_new_action.isEnabled()`, `_open_action.isEnabled()`, and `_reload_action.isEnabled()` evaluate to `False`.

- **L-2: Missing automated unit test for core scaffolding rollback on write failure**
  - **Category**: Completeness / Testing Strategy
  - **Files**: `syntagmax/tests/test_api.py`
  - **Description**: Requirement C5 specifies that if any write fails after `.syntagmax/` has been created during `create_project`, the `.syntagmax/` directory is automatically rolled back via `shutil.rmtree`. While implemented in `syntagmax/src/syntagmax/api.py`, `syntagmax/tests/test_api.py` does not contain a unit test mocking or inducing a write failure to verify that rollback executes cleanly without leaving orphaned directories.
  - **Recommended Action**: Add a test in `syntagmax/tests/test_api.py` monkeypatching `syntagmax.init_cmd.init_project` to raise an `OSError` partway through and asserting that `.syntagmax/` does not persist on disk.

## Validation Results

| Check | Result |
|---|---|
| Type check | Skipped (no dedicated typecheck runner configured) |
| Lint | Skipped (no dedicated lint runner configured) |
| Tests | Pass (Desktop: 69 passed in 7.88s; Core: 1272 passed in 53.07s) |
| Build | Skipped (packaging / freeze build not in local review scope) |

## Files Reviewed

### Superproject (`syntagmax-desktop`)
- `src/syntagmax_desktop/core_facade.py` — Modified
- `src/syntagmax_desktop/session_worker.py` — Modified
- `src/syntagmax_desktop/views/main_window.py` — Modified
- `tests/test_core_facade.py` — Modified
- `tests/test_main_window.py` — Modified
- `tests/test_session_worker.py` — Modified
- `syntagmax` — Modified (submodule pointer updated to `a1bef0c`)

### Submodule (`syntagmax`)
- `docs/reference/embedding-api.md` — Modified
- `src/syntagmax/api.py` — Modified
- `src/syntagmax/init_cmd.py` — Modified
- `tests/test_api.py` — Modified
