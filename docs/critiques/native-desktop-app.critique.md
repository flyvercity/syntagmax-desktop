# Adversarial Critique: Native Desktop App for Syntagmax (Reviewer, v1)

**Target Specification**: `docs/specs/native-desktop-app.spec.md`
**Reviewer Role**: Adversarial Technical & Product Lead (Antigravity)
**Skill**: Scartill SDD Lite (`sc.critique.spec.md`)
**Date**: 2026-10-10

---

## Executive Summary

The specification `docs/specs/native-desktop-app.spec.md` outlines a coherent, focused blueprint for a self-contained, read-only PySide6 desktop companion. It appropriately leverages the library embedding API (`syntagmax.api`) exposed by the core rather than executing CLI commands via sub-processes or introducing web runtimes.

However, an adversarial review grounded in the actual `syntagmax.api` implementation (specifically commit `cca2a29` on branch `more-gui-adaptations`) and the sibling `syntagmax-gui` `core_gateway.py` pattern reveals critical operational, architectural, and user-experience vulnerabilities. Primary issues include: an in-place `git checkout` mechanism that induces working-tree corruption and permission errors on Windows, a default `allow_dirty_worktree=False` policy that will prevent reviewers from opening everyday working copies, an interface mismatch between the specification's trace direction parameters and `Session.trace`, omission of an asynchronous event-loop driver (`pytest-qt`) in the test strategy, and a lack of crash telemetry or logging when bundled as a Win32 GUI executable.

Readiness to proceed: **⚠️ PROCEED WITH UPDATES**. The core trajectory is sound, but the specification requires targeted amendments before proceeding to task execution.

---

## Product Lens Review

### 1a. Problem Validation & Scope

The persona is defined as a **reviewer** inspecting Syntagmax models, rule diagnostics, and traceability matrices without operating a terminal. While read-only consumption matches this persona, the specification overlooks essential reviewer ergonomics:

1. **Absence of a Project Reload / Refresh Affordance**: Reviewers regularly inspect repositories whilst document authors amend files or switch branches externally. Under the current specification, the only mechanism to incorporate disk changes is to reopen the project through the file picker or toggle Git branches. A dedicated "Reload Project" action (accelerator `F5`), leveraging `Session.reload()` or instantiating a fresh `Session`, is essential.
2. **Missing Recent Projects (MRU) List**: Launching `syntagmax-desktop` always starts in an empty state, requiring the reviewer to navigate the OS file dialogue to find `.syntagmax/config.toml`. Persisting the most recently opened project paths via `QSettings` eliminates recurring startup friction.
3. **Ambiguity in Project Folder Selection (R2)**: R2 states that users may pick a `.syntagmax/config.toml` file or "a folder containing it". If a folder is picked, the specification does not declare whether the lookup resolves `<folder>/.syntagmax/config.toml`, `<folder>/config.toml`, or traverses downwards. `Config` in `syntagmax.config` expects the exact path to `config.toml`. The resolution rule must be stated explicitly.

### 1b. User Value Assessment

1. **Artifact Relationship Traversal (R8, Assumption 3)**: Assumption 3 states that "the reviewer never needs artifact navigation-by-link in v1; parent/child are shown as plain labels". For a reviewer conducting traceability audits, discovering an invalid parent or dangling child (`pid`) and being unable to click or double-click to view that artifact in the browser breaks the primary analytical workflow. Reviewers are forced to manually copy the identifier, switch focus, and paste it into the search box.
2. **Diagnostics Severity Filtering (R5)**: In non-trivial projects, analysis can emit hundreds of informational notices or warnings alongside a handful of blocking errors. Grouping diagnostics solely by `location` forces the reviewer to expand every location node to find critical errors. Adding a severity toggle (Errors, Warnings, Info) is vital for reviewer efficiency.
3. **Traceability Matrix Usability (R6)**: Large traceability matrices contain dozens of columns and hundreds of rows. While CSV/TSV export is defined, viewing in-app without column sorting or row filtering renders the on-screen table unwieldy, forcing immediate offloading to external spreadsheet software.

### 1c. Alternative Approaches

1. **In-Place `git checkout` versus Isolated Working Copies**: In `syntagmax-gui`, branch switching is performed on isolated clones or worktrees (`<workspaces-root>/<project>/<user>/<branch>`), avoiding modifications to a developer's active working tree. While full isolated clones may be excessive for a local desktop companion, performing in-place `repo.git.checkout(branch)` in the user's primary repository carries data-loss hazards, risks dirty-tree conflicts, and can fail due to OS file locks.

### 1d. Edge Cases & User Experience

1. **Fatal Failure on Dirty Repositories (R2, R3)**: By default, `syntagmax.api.Options` sets `allow_dirty_worktree=False`. In `syntagmax.git_utils.GitContext`, any untracked file or uncommitted modification causes `extract()` to append an error and raise `FatalError`. If `syntagmax-desktop` invokes `open_project(..., options=Options(no_git=False))` without setting `allow_dirty_worktree=True`, opening any working copy containing untracked notes, temporary artefacts, or editor swap files will abort with a fatal dialogue. For a read-only viewer, this default is overly restrictive; `allow_dirty_worktree=True` must be the default.
2. **Detached HEAD and Git Edge States (R4)**: If a project repository is checked out on a specific tag, detached commit, or rebase state, `repo.active_branch` in GitPython raises a `TypeError`. The branch selector must gracefully display `(HEAD detached at <commit>)` rather than terminating or disabling unexpectedly.
3. **Empty States**: The specification lacks clear UX definitions for zero-state scenarios: a project with no defined artefacts, an analysis result with zero diagnostics (explicitly confirmed as positive), a trace matrix query that yields no matching pairs, and search queries with zero hits.

### 1e. Success Measurement

1. The specification lacks measurable launch, runtime, and stability metrics. Concrete criteria must be established: application launch in under 2.0 seconds, initial project open for 1,000 artefacts in under 3.0 seconds, and zero unhandled UI thread exceptions.

---

## Engineering Lens Review

### 2a. Architecture Soundness

1. **`SessionWorker` Queue Serialisation and Request Concurrency**: Task 4 designs `SessionWorker` as a `QObject` residing on a single `QThread`. Core operations such as `Session.analyse()` and `Session.trace()` are CPU-bound and synchronous. If a user triggers an analysis that runs for several seconds and subsequently attempts to filter or search artefacts in the browser, those requests are queued sequentially behind the analysis task. The architecture must either introduce cancellation tokens, maintain separate worker routines, or provide unambiguous UI busy-masking that prevents queuing orphaned search requests.
2. **Encapsulation Breach in Metamodel Extraction (R7)**: Task 2 and R7 state that artefact types are discovered via `config.metamodel['artifacts']`. However, `syntagmax.api.Session` encapsulates `_config` as a private attribute and exposes no public `metamodel` accessor. Reaching into `session._config.metamodel` mirrors the sibling `core_gateway.py`, but bypasses public encapsulation. `core_facade.py` must encapsulate this access cleanly and provide fallback to `Session.query()` if `_config` is refactored upstream.
3. **Qt Model/View Scalability**: Task 7 proposes rendering trace rows in `QTableView`, and Task 8 proposes listing artefacts in views. To prevent UI freezing when handling thousands of artefacts or trace cells, custom subclasses of `QAbstractTableModel` and `QAbstractListModel` must be implemented rather than populating item-based container widgets (`QTableWidget`, `QListWidget`).

### 2b. Failure Mode Analysis

1. **Windows File Locking During Git Checkout**: On Windows, file handles held by language servers, indexers, antivirus scanners, or the application itself will cause `git.checkout()` to fail with permission errors, leaving the working tree in an inconsistent state. `git_branches.py` must catch `GitCommandError`, verify repository status, and inform the user without leaving orphaned lock files (`.git/index.lock`).
2. **CSV Export File Locking and Character Encoding**: 
   - Exporting a matrix to a path currently open in Microsoft Excel on Windows triggers an unhandled `PermissionError` (OS error code 13). The worker must trap filesystem exceptions and emit structured error notifications to the UI.
   - `render_trace` outputs UTF-8 strings. Microsoft Excel on Windows assumes the local ANSI code page for standard CSV files unless a Byte Order Mark (BOM) is present. Writing export files using `encoding='utf-8-sig'` is required to avoid character corruption in international text.
3. **Silent Failures in Frozen Win32 GUI Executables**: Task 9 configures cx_Freeze with `base = "gui"`, which disconnects standard output and standard error streams. Any unhandled exception arising during module import, Qt bootstrap, or signal dispatch will terminate the application silently without console output or diagnostic logs. An explicit `sys.excepthook` logging to `%LOCALAPPDATA%/Syntagmax/logs/crash.log` is required.

### 2c. Security & Privacy Review

1. **Credential Redaction in Configuration Presentation**: Sibling module `core_gateway.py` implements regex redaction (`_SECRET_KEY_RE`) for token, password, and secret keys found in TOML configurations. If `syntagmax-desktop` surfaces configuration errors or displays raw configuration snippets, sensitive credentials stored in environment variables or configuration blocks must not be exposed.
2. **Export Path Validation**: File export dialogues must validate that target paths reside in writable locations and do not attempt to write outside user-permitted boundaries.

### 2d. Performance & Scalability

1. **Search Query Flooding**: `Session.search(q)` performs a full linear scan over all artefacts and their markdown contents. Connecting a `QLineEdit.textChanged` signal directly to worker search invocations will trigger repeated redundant scans on every keystroke. A debounce timer (e.g., 250–300 ms via `QTimer`) must throttle search dispatches.
2. **Markdown Rendering Limitations in `QTextBrowser`**: `QTextBrowser.setMarkdown()` implements a strict CommonMark subset. It does not parse GFM tables, strikethrough syntax, or Obsidian wikilinks (`[[ArtifactID]]`, `![[image.png]]`). Furthermore, relative image references will fail to resolve unless `document().setBaseUrl()` is assigned to the project root directory.

### 2e. Testing Strategy

1. **Asynchronous Signal Testing Deficit**: Tasks 1, 4, and 5 propose executing headless pytest runs with `QT_QPA_PLATFORM=offscreen`. When testing cross-thread Qt signals (such as `SessionWorker` executing on a background thread), signals are dispatched via queued connections. Without an active Qt event loop or the `pytest-qt` plugin (`qtbot.waitSignal()`), synchronous test assertions will evaluate before background workers emit signals, causing test deadlocks or race conditions. `pytest-qt` must be incorporated into development dependencies.
2. **Submodule Revision Verification**: Task 1 requires advancing the `syntagmax` submodule to the revision containing `syntagmax.api`. Automated tests must include a sanity test asserting the presence of `syntagmax.api.open_project`, ensuring the repository never regresses to an incompatible core commit.

### 2f. Operational Readiness

1. **cx_Freeze Qt Plugin Bundling Pitfalls**: Freezing PySide6 applications with cx_Freeze frequently omits the Windows platform plugin (`platforms/qwindows.dll`), styles, and SVG libraries, causing the frozen binary to fail immediately on clean systems. The build configuration must explicitly declare `include_files` or verify Qt plugin directory inclusion.
2. **MSI Installation Parameters**: Task 9 must define `upgrade_code`, desktop and Start Menu shortcut configurations, and per-user installation scope (`all_users=False` to avoid mandatory UAC escalation).

### 2g. Dependencies & Integration Risks

1. **Trace Parameter Mismatch (R6 vs `syntagmax.api`)**: In R6, the specification states: "The user can select a child atype, a parent atype, and a direction (forward/reverse/flat)". In `syntagmax.api.Session.trace`, the method signature is:
   ```python
   def trace(self, child_type: str, parent_type: str, *, direction: str = 'forward', attributes: list[str] | None = None, flat: bool = False) -> TraceResult
   ```
   `direction` accepts `'forward'` or `'reverse'`, whilst `flat` is an orthogonal boolean flag. Describing `flat` as a direction value is an interface mismatch that must be rectified in the UI design and facade signature.
2. **Submodule Branch Origin**: The required commit (`cca2a29`) containing `Session.trace`, `Session.publish`, and `ArtifactView.body` exists on branch `more-gui-adaptations`, not on the upstream `main` branch of `flyvercity/syntagmax`. The specification must explicitly document this dependency and note the tracking branch for submodule updates.

---

## Cross-Lens Insights

1. **X1: Safe Git Branch Switching vs In-Place Mutation (Product × Engineering)**: In-place `git checkout` creates both user data risk (modifying files in active IDE workspaces) and severe technical risk (Windows file lock permission errors, index locks, detached HEAD crashes). The specification must enforce strict pre-flight guards: checkouts must be aborted if uncommitted changes exist, if untracked files conflict, or if HEAD is detached.
2. **X2: Defaulting `allow_dirty_worktree=True` (Product × Engineering)**: The core CLI mandates clean trees for CI verification, but imposing this constraint on a local read-only desktop viewer causes frequent fatal error dialogues for users. Setting `allow_dirty_worktree=True` in `Options` removes this hurdle without compromising core integrity.
3. **X3: Trace Matrix Parameter Clarification (Product × Engineering)**: Splitting the selector into a `Direction` control (`Forward` / `Reverse`) and a `Flat Matrix` checkbox aligns the UI directly with the underlying `syntagmax.api.Session.trace` contract.

---

## Findings Summary Table

| ID | Lens | Severity | Category | Finding | Suggestion |
|:---|:-----|:---------|:---------|:--------|:-----------|
| P1 | Product | 🎯 | Failure Modes | `Options.allow_dirty_worktree` defaults to `False`, causing fatal errors when opening ordinary working directories containing untracked or edited files. | Configure `Options(allow_dirty_worktree=True)` as the default in `core_facade.open()`. |
| P2 | Product | 💡 | User Value | Assumption 3 specifies parent and child links as static non-navigable text, impeding traceability analysis. | Make parent/child identifiers clickable in the detail view to navigate directly to the target artifact in the browser. |
| P3 | Product | 💡 | User Value | Diagnostics panel groups solely by `location` without severity filtering, obscuring high-priority errors among voluminous warnings. | Add severity filter toggles (`Error`, `Warning`, `Info`) above the diagnostics tree. |
| P4 | Product | 💡 | Edge Cases | Absence of a project reload action and recent projects list causes friction during iterative authoring workflows. | Add a "Reload Project" command (`F5`) and persist recent projects using `QSettings`. |
| E1 | Engineering | 🎯 | Failure Modes | In-place `git checkout` can trigger Windows file-lock permission errors, crash on detached HEAD states, or corrupt intermediate states. | Add pre-flight validation in `git_branches.py`: verify `not repo.head.is_detached`, guard against `GitCommandError`, and refuse checkout on dirty state with clear UI feedback. |
| E2 | Engineering | 🎯 | Interface Contract | R6 and Task 7 treat `flat` as a direction option (`forward`/`reverse`/`flat`), conflicting with `Session.trace(direction, flat=bool)`. | Clarify UI controls: a direction selector (`forward` / `reverse`) plus an independent `Flat` checkbox. |
| E3 | Engineering | 🎯 | Testing Strategy | Asynchronous Qt signal testing with offscreen platform without an active event loop or `pytest-qt` will cause deadlocks or race conditions. | Add `pytest-qt` to test dependencies and use `qtbot.waitSignal` for asynchronous worker tests. |
| E4 | Engineering | 🎯 | Operational Readiness | cx_Freeze `base = "gui"` suppresses standard output/error, causing silent crashes without diagnostic traces if startup fails on Windows. | Implement `sys.excepthook` to write unhandled crashes to an application log directory (`%LOCALAPPDATA%/Syntagmax/logs/`). |
| E5 | Engineering | 💡 | Architecture | A single worker thread serialises all requests without debouncing, leading to query floods on rapid search inputs. | Introduce a 250 ms `QTimer` debounce on the search input field before dispatching `runSearch`. |
| E6 | Engineering | 💡 | Performance | Populating standard table and list widgets for large artifact datasets causes UI thread freezing. | Implement custom `QAbstractTableModel` for trace matrices and virtual models for artifact listings. |
| E7 | Engineering | 💡 | Failure Modes | Exporting CSV files open in Microsoft Excel triggers unhandled `PermissionError`; raw UTF-8 causes character encoding issues in Windows Excel. | Trap filesystem exceptions during export with descriptive error dialogues and export CSV using `encoding='utf-8-sig'`. |
| E8 | Engineering | 💡 | Performance | `QTextBrowser.setMarkdown()` does not resolve relative image links and lacks GFM/Obsidian wikilink handling. | Set `document().setBaseUrl(QUrl.fromLocalFile(project_dir))` and document rendering constraints for complex markdown. |
| E9 | Engineering | 🤔 | Dependencies | Core API commit (`cca2a29`) resides on branch `origin/more-gui-adaptations` rather than upstream `main`. | Clarify in Task 1 whether the submodule tracks `more-gui-adaptations` or when that branch merges upstream. |
| X1 | Both | 🎯 | Scope × Risk | In-place branch switching carries worktree disruption and file lock risks in a read-only companion tool. | Enforce strict non-destructive git checkouts, verifying clean working trees before checkout. |
| X2 | Both | 🎯 | User Experience | Overly strict clean worktree checks impede everyday reviewer adoption. | Set `allow_dirty_worktree=True` by default in desktop open operations. |
| X3 | Both | 💡 | Usability | Inaccurate trace parameter abstraction leads to fragile facade and UI controls. | Align UI controls explicitly with `Session.trace` parameter signatures. |

---

## Verdict

**⚠️ PROCEED WITH UPDATES**

The overall architectural direction—using PySide6 and consuming the in-process `syntagmax.api` facade—is solid. However, the identified must-address items (E1, E2, E3, E4, P1, X1, X2) must be incorporated into `docs/specs/native-desktop-app.spec.md` to prevent implementation failures, Windows packaging crashes, and hostile user workflows.

---

## Suggested Remediation

To resolve the critique findings, apply the following updates to `docs/specs/native-desktop-app.spec.md`:

### 1. Amend R2 and R3 (Address P1, X2)
Update R2 and R3 to mandate `allow_dirty_worktree=True` as default for reviewer sessions:
```markdown
- **R2 — Open project.** The user can pick a project's `.syntagmax/config.toml` (or a folder containing `.syntagmax/config.toml` or `config.toml`) through a native file/folder dialog; the app calls `syntagmax.api.open_project(..., options=Options(allow_dirty_worktree=True))` and holds the resulting `Session`. If a folder is picked, resolution checks `<folder>/.syntagmax/config.toml` first, then `<folder>/config.toml`.
- **R2a — Reload project.** The user can trigger a project reload (`F5` or menu action) which clears the session cache via `Session.reload()` or instantiates a fresh `Session`, reflecting changes made to existing files on disk.
```

### 2. Amend R4 and Task 3 (Address E1, X1)
Strengthen branch selection safeguards against detached HEAD and Windows file locking:
```markdown
- **R4 — Branch selection.** When the opened project is inside a Git working tree, the app lists local branches (via `gitpython`), lets the user check one out, and re-opens the project (new `Session`) on the selected branch. If the repository is in a detached HEAD state, the selector indicates the detached commit and disables switching. Checkout is refused if the working tree has uncommitted modifications or untracked file conflicts, surfacing a non-fatal message.
```

### 3. Amend R6 and Task 7 (Address E2, X3, E7)
Correct trace parameter mapping and add export protections:
```markdown
- **R6 — Traceability panel.** The user can select a child `atype`, a parent `atype`, a direction (`forward` or `reverse`), and an optional `flat` toggle, run `Session.trace(...)`, and view the resulting matrix as a dense table powered by a `QAbstractTableModel`. The user can export the matrix to a `.csv` (using UTF-8 with BOM `utf-8-sig` for Windows Excel compatibility) or `.tsv` file on disk via `syntagmax.api.render_trace(result, delimiter=...)`. File write permissions (e.g. file locked by Excel) are caught and surfaced via dialogue.
```

### 4. Amend R17 and Task 1 / Task 4 (Address E3)
Include `pytest-qt` in test dependencies and update worker test specifications:
```markdown
- **R17 — Tests.** Headless pytest coverage exists for the non-UI logic and signal interactions using `pytest-qt` (`qtbot`) with Qt's offscreen platform (`QT_QPA_PLATFORM=offscreen`).
```

### 5. Amend Task 9 and Packaging Architecture (Address E4)
Incorporate crash logging and Qt plugin verification for cx_Freeze:
```markdown
- **Guidance (Task 9)**: Add `[tool.cxfreeze]` to `pyproject.toml` reusing the core's `build_exe.packages` plus `PySide6`, `shiboken6`; ensure Qt platform plugins (`platforms/qwindows.dll`) are included. Implement a top-level `sys.excepthook` in `app.py` writing uncaught exceptions to `%LOCALAPPDATA%/Syntagmax/logs/crash.log` before terminating.
```

### 6. Amend Assumption 3 and R8 (Address P2, E5, E8)
Add artifact link navigation, search debouncing, and base URL resolution:
```markdown
- **R8 — Read-only artifact browser.** The user can browse artifacts grouped by `atype` (`Session.query()`), filter by type, search by content (`Session.search(q)` debounced by 250 ms), select one, and view its `fields`, parent/child links (clickable to select the target artifact), and rendered Markdown `body` (with `setBaseUrl` configured to resolve local images).
```

---

Would you like me to apply these changes? (all / select / none)
