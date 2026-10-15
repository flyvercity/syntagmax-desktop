# Critique Report: New Project Creation Specification (`docs/specs/new-project.spec.md`)

## Executive Summary

This critique evaluates the specification `docs/specs/new-project.spec.md`, which defines the implementation plan for introducing project scaffolding into Syntagmax Desktop via an upstream extension to `syntagmax.api`. The foundational architecture—delegating filesystem scaffolding to the core library embedding API and executing writes asynchronously on `SessionWorker` off the UI thread—is sound, clean, and appropriately respects the application's layered design.

However, an adversarial review across Product and Engineering lenses identifies significant gaps that must be resolved prior to implementation. On the product side, scaffolding into an empty folder drops the reviewer into an empty, read-only interface with no artifacts, no diagnostics, an inert traceability matrix, no default input directory (`REQ/`), and no mechanism to open the newly scaffolded project in an external editor or file manager, producing an immediate onboarding dead end. On the engineering side, scaffolding lacks write atomicity and rollback on partial failure, fails to detect existing flat projects with `config.toml` at the project root, executes synchronous filesystem inspection on the Qt UI thread without permission guards, and leaves menu actions enabled during background writes, risking UI state desynchronisation.

Overall verdict: ⚠️ **PROCEED WITH UPDATES**. The core approach is viable and well-motivated, but the specification requires targeted updates to guarantee atomic creation, comprehensive collision detection, UI-thread safety, and a coherent first-run user experience.

## Product Lens Findings

### 1a. Problem Validation

- **P1 (🎯 Must-Address) — First-Run Empty State and Lack of Onboarding Guidance**: The specification emphasises that Syntagmax Desktop remains strictly read-only post-creation, with no controls to create, edit, or delete artifacts. Consequently, when a reviewer scaffolds an empty project, the application opens an interface displaying 0 artifacts, 0 diagnostics, and an inert traceability panel. The specification provides no onboarding callout, banner, or workflow instruction indicating how the user should begin authoring requirements (for example, creating Markdown files inside the input directory). Without guidance, first-time reviewers who sought a user-friendly way to start a project encounter a puzzling, unresponsive dead end.
  *Constructive Suggestion*: Amend R5 to specify a first-run empty-state banner or placeholder card in the Browser and Analysis tabs when the total artifact count is zero, detailing the project structure and explaining where to add Markdown files.

- **P2 (💡 Recommendation) — Directory Picker Usability vs Project Naming**: Design decision D1 rejects a project name parameter, relying entirely on `QFileDialog.getExistingDirectory`. On major operating systems (notably Windows and macOS), directory pickers require users to manually create and navigate into a new folder via the OS dialogue. If a reviewer selects an existing workspace folder (such as `projects/`), the dialogue selects that directory itself. This workflow is error-prone compared with standard IDE patterns where the user specifies a parent directory and a project name, from which the application creates `<parent>/<name>`.
  *Constructive Suggestion*: Enhance the New Project dialogue to accept a parent folder and a project name, or clearly specify that if `getExistingDirectory` is retained, the dialogue title and prompt explicitly guide the user to choose or create an empty target folder.

### 1b. User Value Assessment

- **P3 (💡 Recommendation) — Missing Action to Reveal Project in File Manager**: Because the desktop application does not author artifacts, the immediate next action for any reviewer after scaffolding a project is to open the project folder in an operating system file manager (Explorer, Finder) or an external text editor (Obsidian, VS Code). The specification does not provide a "Show in Explorer/Finder" action or link.
  *Constructive Suggestion*: Add a "Reveal in File Manager" / "Open Project Folder" command to the File menu and the first-run empty state to close the loop between project bootstrap and external artifact authoring.

- **P4 (💡 Recommendation) — Input Directory `REQ/` Not Created by Scaffold**: `syntagmax.init_cmd.init_project` generates `.syntagmax/config.toml` with `[[input]] dir = "REQ"`, `.syntagmax/project.syntagmax`, and `.syntagmax/.gitignore`. It does not create the `REQ/` subdirectory. While `syntagmax` tolerates missing input directories without error, leaving the folder uncreated forces the user to manually create both the folder and files before any artifacts can be loaded.
  *Constructive Suggestion*: Extend `create_project` to scaffold the default input directory (`target / 'REQ'`) alongside `.syntagmax/`, ensuring the directory structure matches `config.toml` immediately upon creation.

### 1c. Alternative Approaches

- **P5 (🤔 Question) — Omission of Local Git Initialisation Prompt**: Decision D3 omits Git initialisation to honour the rule that the core never commits. However, Syntagmax Desktop features prominent branch-selection and git-inspection capabilities. When a project is created outside a Git tree, the branch bar is silently hidden, giving no indication of whether the project is version-controlled.
  *Constructive Suggestion*: Evaluate whether the Desktop application (at the host layer, not core) should offer an optional checkbox "Initialise Git repository" during creation, running a local `git init` via `gitpython` if selected.

### 1d. Edge Cases & User Experience

- **P6 (💡 Recommendation) — Unsafe Default Button in Non-Empty Folder Warning**: Requirement R4 specifies a warning confirmation when the selected folder is non-empty: `QMessageBox.warning(self, 'Folder not empty', 'This folder is not empty and is not a Syntagmax project. Create a project here anyway?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)`. In Qt, if the default button is not explicitly set, `Yes` may be focused by default. For an action that mutates a non-empty directory, accidental keypresses (Enter/Space) could pollute user folders.
  *Constructive Suggestion*: Explicitly designate `QMessageBox.StandardButton.No` as the default button in the warning dialogue (`defaultButton=QMessageBox.StandardButton.No`).

- **P7 (🎯 Must-Address) — Collision Hazard with Flat Root `config.toml` Projects**: Requirement R4 checks only `(target / '.syntagmax' / 'config.toml').is_file()`. Syntagmax also supports root configuration files (`target / 'config.toml'`), as handled in `src/syntagmax_desktop/core_facade.py`. If a user selects an existing flat Syntagmax project, R4 will fail to identify it as a project, display the non-empty folder warning, and, if confirmed, scaffold a nested `.syntagmax/config.toml`, corrupting the project structure and shadowing the root configuration.
  *Constructive Suggestion*: Update the R4 safety check and the core C3 refusal check to inspect both `target / '.syntagmax' / 'config.toml'` and `target / 'config.toml'`.

### 1e. Success Measurement

- **P8 (💡 Recommendation) — Absence of Measurable Success Criteria**: The specification lacks quantifiable success criteria and error tracking metrics. There are no defined thresholds for project creation success rate, UI latency during creation, or subsequent project engagement.
  *Constructive Suggestion*: Define measurable targets (for example, 100% clean creation on writable paths, under 200 ms dispatch-to-open latency for local filesystems, zero unhandled UI thread exceptions) and operational logging for creation failures.

## Engineering Lens Findings

### 2a. Architecture Soundness

- **E1 (🎯 Must-Address) — Lack of Atomic File Operations and Rollback on Scaffold Failure**: In `create_project`, the core creates `.syntagmax/` and executes three sequential file writes (`config.toml`, `project.syntagmax`, and `.gitignore`). If an error occurs during the second or third write (such as disk exhaustion, permission errors, or process interruption), the folder is left partially populated. Because `.syntagmax/config.toml` exists, subsequent calls to `create_project` will be refused by C3, and `open_project` will fail due to missing metamodel files, resulting in an unrecoverable corrupted state.
  *Constructive Suggestion*: Implement atomic directory creation by scaffolding into a temporary directory on the same filesystem and renaming it into place via `os.replace`, or clean up created files and directories if any write fails.

- **E2 (🎯 Must-Address) — Incomplete Core Refusal Guard (C3)**: `syntagmax.api.create_project` checks only `(target / '.syntagmax' / 'config.toml').exists()`. If `target / 'config.toml'` exists, the core proceeds to scaffold `.syntagmax/config.toml`. Because `core_facade.open` prefers `.syntagmax/config.toml` over `config.toml`, this creates a configuration conflict.
  *Constructive Suggestion*: Extend C3 in `syntagmax.api.create_project` to raise `FatalError` if either `.syntagmax/config.toml` or `config.toml` is present in `target`.

### 2b. Failure Mode Analysis

- **E3 (🎯 Must-Address) — UI-Thread Filesystem Inspection and Exception Hazards**: The proposed `new_project_dialog` implementation in `src/syntagmax_desktop/views/main_window.py` executes `target = Path(folder)` and `any(target.iterdir())` directly on the main Qt thread. If `target` is inaccessible, unreadable, protected by OS permissions, or located on a disconnected network share, `iterdir()` raises an unhandled `PermissionError` or `OSError`, which will crash or freeze the UI.
  *Constructive Suggestion*: Wrap the filesystem inspection in a guarded try-except block handling `OSError` and `PermissionError`, or delegate all target validation checks to the background worker thread.

- **E4 (💡 Recommendation) — UI Reentrancy and State Desynchronisation During Asynchronous Creation**: While `SessionWorker.createProject` uses `_busy()` to emit `busyChanged(True)`, `main_window._on_busy_changed` only disables `self._tabs`. It does not disable `_new_action`, `_open_action`, or `_reload_action`. A reviewer can trigger "New Project…" or "Open Project…" repeatedly while a creation task is in flight, queueing multiple worker operations and corrupting `self._current_path`.
  *Constructive Suggestion*: In `_on_busy_changed`, ensure menu actions (`_new_action`, `_open_action`, `_reload_action`) and corresponding toolbar buttons are disabled while `busy` is true.

### 2c. Security & Privacy Review

- **E5 (💡 Recommendation) — Absence of Root Directory and System Path Validation**: `syntagmax.api.create_project` and `new_project_dialog` accept any arbitrary path and execute `target.mkdir(parents=True, exist_ok=True)`. Neither layer validates whether `target` is a system root (`/`, `C:\`, `C:\Windows`) or user home directory root (`~`). Accidental selection could scaffold hidden configuration folders into critical system locations.
  *Constructive Suggestion*: Add a path validation check in `create_project` and `new_project_dialog` that rejects filesystem roots and system directories before attempting directory creation.

### 2d. Performance & Scalability

- **E6 (💡 Recommendation) — Synchronous Directory Iteration on Network/Virtual Filesystems**: Calling `any(target.iterdir())` on network shares or directories containing tens of thousands of entries can cause perceptible UI hitches when running synchronously on the Qt event loop.
  *Constructive Suggestion*: Ensure the non-empty check stops immediately after reading the first directory entry (which `any(iterdir())` does for local disks, but should be guarded with a timeout or handled off the UI thread for remote filesystems).

### 2e. Testing Strategy

- **E7 (💡 Recommendation) — Missing Negative and Concurrency Test Scenarios**: Requirement R8 and Task 4 specify tests for the happy path and basic existing-project refusal. Crucial edge cases are omitted: read-only directory creation failures, permission errors during folder inspection, flat root `config.toml` collision refusal, worker cancellation, and menu action disablement under busy states.
  *Constructive Suggestion*: Expand R8 test requirements to explicitly test permission-denied errors, root `config.toml` detection, and UI element disablement during worker busy states.

### 2f. Operational Readiness

- **E8 (💡 Recommendation) — Submodule Branching and CI Integration Risk**: Task 1 and Task 6 propose developing the core change on a submodule branch `feat/api-create-project` and updating the superproject's submodule pointer. If this branch is not pushed to the upstream remote repository, continuous integration runners and peer developers will fail during `git submodule update` with unresolvable commit references.
  *Constructive Suggestion*: Update Task 1 and Task 6 to specify pushing `feat/api-create-project` to the submodule remote prior to updating the superproject submodule reference, and document the upstream PR merge dependency.

### 2g. Dependencies & Integration Risks

- **E9 (🤔 Question) — Recent Projects Representation (Folder Path vs Config Path)**: `_on_created` calls `self.open_path(config_path)`, which records `config_path` (`.../.syntagmax/config.toml`) into the MRU store via `_remember_recent`. However, reviewers conceptually interact with the project folder. Storing `.syntagmax/config.toml` for created projects while direct folder opens record directories creates inconsistency in the MRU menu and status label.
  *Constructive Suggestion*: Align `_remember_recent` and `open_path` to consistently store and display the project root directory rather than internal configuration file paths.

## Cross-Lens Synthesis

- **X1 (🎯 Must-Address — High Priority) [Addresses P7, E1, E2] — Atomic Scaffold and Dual-Config Conflict Detection**: Both lenses converge on the fragility of project scaffolding. If `create_project` fails midway or encounters a flat `config.toml`, it leaves the project in a broken or conflicted state. Staging writes and verifying both `.syntagmax/config.toml` and `config.toml` protects system integrity and prevents user data corruption.
- **X2 (💡 Recommendation — Medium Priority) [Addresses P1, P3, P4] — End-to-End Onboarding Experience**: Scaffolding a project without creating `REQ/`, combined with an empty read-only UI, creates an unsatisfying user experience. Extending the scaffold to include `REQ/` and presenting a clear first-run guidance card with a "Reveal in File Manager" button bridges the gap between project creation and active review.
- **X3 (💡 Recommendation — Medium Priority) [Addresses E3, E4] — Robust UI Threading and Reentrancy Protection**: Moving or guarding filesystem inspections and locking out File menu actions during worker operations prevents both UI freezes and reentrancy bugs.

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|:---|:---|:---:|:---|:---|:---|
| P1 | Product | 🎯 | User Experience | Empty read-only state leaves users stranded with no next steps | Add first-run empty-state guidance and onboarding callout |
| P2 | Product | 💡 | Usability | `getExistingDirectory` requires awkward manual folder creation | Add parent folder + project name input flow or explicit prompt guidance |
| P3 | Product | 💡 | User Value | No mechanism to open the scaffolded folder in an external editor or file manager | Add "Reveal in File Manager" action to File menu and empty state |
| P4 | Product | 💡 | User Value | Scaffold does not create the default `REQ/` directory | Create `REQ/` directory during scaffolding alongside `.syntagmax/` |
| P5 | Product | 🤔 | UX Alignment | No indication or prompt regarding Git version control status | Consider optional checkbox or prompt to run `git init` at host layer |
| P6 | Product | 💡 | User Experience | Non-empty folder warning lacks safe default button (`No`) | Set `QMessageBox.StandardButton.No` as the default dialogue button |
| P7 | Product | 🎯 | Edge Cases | Fails to detect existing flat projects with `target / 'config.toml'` | Check both `target / '.syntagmax' / 'config.toml'` and `target / 'config.toml'` |
| P8 | Product | 💡 | Success Measurement | Lack of quantifiable success criteria and failure rate metrics | Define explicit error rate, latency, and operational logging targets |
| E1 | Engineering | 🎯 | Architecture Soundness | Partial write failure leaves unrecoverable corrupted `.syntagmax` directory | Implement atomic scaffolding or transactional rollback on error |
| E2 | Engineering | 🎯 | Architecture Soundness | Core C3 check misses root `config.toml`, allowing duplicate configs | Extend C3 to refuse creation if either config location exists |
| E3 | Engineering | 🎯 | Failure Modes | Synchronous `target.iterdir()` on UI thread crashes on permission errors | Guard filesystem checks with exception handling or move to worker |
| E4 | Engineering | 💡 | Failure Modes | Menu actions remain enabled during creation, allowing re-entrant races | Disable New/Open/Reload actions during worker busy state |
| E5 | Engineering | 💡 | Security & Privacy | No validation against system root or user home directory targets | Reject filesystem root paths and system directories in validation |
| E6 | Engineering | 💡 | Performance | Synchronous directory iteration can freeze UI on remote shares | Limit iteration depth or execute directory check off-thread |
| E7 | Engineering | 💡 | Testing Strategy | Test suite lacks negative cases for permissions and root config conflicts | Add test cases for permission errors, root `config.toml`, and busy state |
| E8 | Engineering | 💡 | Operational Readiness | Submodule branch pointer without remote push risks CI checkout failures | Explicitly document submodule remote push and CI dependency workflow |
| E9 | Engineering | 🤔 | Architecture Soundness | MRU persists `.syntagmax/config.toml` rather than clean project root path | Normalise project paths stored in MRU to project root directory |
| X1 | Both | 🎯 | Architecture × UX | Atomic creation and dual-config detection prevent corrupted project states | Combine atomic scaffolding with comprehensive config collision checks |
| X2 | Both | 💡 | Value × Simplicity | Scaffold `REQ/` and provide "Reveal in File Manager" to unblock users | Scaffold input directory and provide external editor handoff |
| X3 | Both | 💡 | Robustness × UX | Guard UI thread and disable menu actions during busy state | Protect UI event loop from filesystem exceptions and reentrancy |

## Verdict

⚠️ **PROCEED WITH UPDATES**

The fundamental direction of the specification is sound and builds appropriately on the existing `syntagmax.api` architecture and `SessionWorker` design. However, the five Must-Address items (P1, P7, E1, E2, E3, and X1) must be resolved in `docs/specs/new-project.spec.md` before proceeding to implementation to prevent data corruption, crashes, and a broken first-run user experience.

## Suggested Remediation Edits

### Remediation for E1, E2, P7, and X1 (Core API Refusal and Atomic Creation)

In `docs/specs/new-project.spec.md`, update Section **Core (submodule) requirements** C3 and the `create_project` implementation:

```markdown
- **C3 — Safety: refuse existing project.** If the target already contains `.syntagmax/config.toml` or `config.toml`, `create_project` raises a `FatalError` rather than overwriting or creating a conflicting dual-configuration structure. Scaffolding is atomic: if any file write fails, all created scaffold files and directories are cleaned up before propagating the exception.
```

And amend the implementation sketch:

```python
def create_project(path: str | Path) -> Path:
    from syntagmax.errors import FatalError
    from syntagmax.init_cmd import init_project

    target = Path(path).resolve()
    if (target / '.syntagmax' / 'config.toml').exists() or (target / 'config.toml').exists():
        raise FatalError(f'A Syntagmax project already exists at {target}')
    if target == target.parent:
        raise FatalError('Cannot scaffold a project at the filesystem root')

    target.mkdir(parents=True, exist_ok=True)
    try:
        init_project(str(target))
        # Ensure default input directory exists
        req_dir = target / 'REQ'
        req_dir.mkdir(exist_ok=True)
    except Exception:
        # Roll back partial scaffold
        syntagmax_dir = target / '.syntagmax'
        if syntagmax_dir.is_dir():
            import shutil
            shutil.rmtree(syntagmax_dir, ignore_errors=True)
        raise

    return target / '.syntagmax' / 'config.toml'
```

### Remediation for E3, P6, and P7 (Host Safety Checks and UI-Thread Guard)

In `docs/specs/new-project.spec.md`, update Requirement R4 and `new_project_dialog`:

```python
def new_project_dialog(self) -> None:
    folder = QFileDialog.getExistingDirectory(self, 'New Syntagmax Project')
    if not folder:
        return
    target = Path(folder)
    # Check for existing project (both .syntagmax/config.toml and flat config.toml)
    has_sub_config = (target / '.syntagmax' / 'config.toml').is_file()
    has_root_config = (target / 'config.toml').is_file()
    if has_sub_config or has_root_config:
        if QMessageBox.question(
            self,
            'Project exists',
            'This folder already contains a Syntagmax project. Open it instead?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        ) == QMessageBox.StandardButton.Yes:
            self.open_path(str(target))
        return

    # Guarded non-empty check
    try:
        is_non_empty = target.is_dir() and any(target.iterdir())
    except (OSError, PermissionError) as exc:
        QMessageBox.critical(self, 'Access error', f'Cannot access folder: {exc}')
        return

    if is_non_empty:
        if QMessageBox.warning(
            self,
            'Folder not empty',
            'This folder is not empty and is not a Syntagmax project. Create a project here anyway?',
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return

    QMetaObject.invokeMethod(
        self._worker,
        'createProject',
        Qt.ConnectionType.QueuedConnection,
        Q_ARG(str, str(target)),
    )
```

### Remediation for P1, P3, and X2 (First-Run Guidance and External Handoff)

In `docs/specs/new-project.spec.md`, amend R5:

```markdown
- **R5 — Auto-open and first-run guidance.** On `created`, the window opens the freshly scaffolded project through the existing `open_path` flow. When opening a project with 0 artifacts, the Browser and Analysis tabs display a welcoming placeholder card explaining that the project was scaffolded and directing the reviewer to place Markdown specification files in `REQ/`. A "Reveal Project in File Manager" action is added to the File menu and the placeholder card to allow immediate navigation to the project folder.
```

### Remediation for E4 (UI Busy Lockout)

In `docs/specs/new-project.spec.md`, amend `_on_busy_changed`:

```markdown
- **R2a — Action lockout during worker execution.** In `_on_busy_changed`, `self._new_action`, `self._open_action`, and `self._reload_action` are disabled whenever `busy` is true, preventing re-entrant worker dispatch and state desynchronisation.
```

---

Would you like me to apply these changes? (all / select / none)
