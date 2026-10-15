# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: The main reviewer window — open flow, branch bar, reload, MRU, and busy indicator.

"""The main application window (spec R2, R2a, R3, R4, R9, P4).

The window is the :class:`QMainWindow` shell that wires the reviewer workflow
together: an Open action drives a native file/folder dialog, a Reload action
(bound to ``F5``) re-opens the current project, a branch combo lists local
branches and performs a guarded checkout-and-reopen, a Recent Projects menu
offers one-click re-open, and a status-bar indicator reflects the worker's busy
state. Every core call is marshalled onto a :class:`SessionWorker` running on a
dedicated :class:`QThread`, so the UI thread never touches ``syntagmax.api`` and
never freezes during a long operation (R9).

The central area is a tabbed panel stack. The individual Wave-4 panels — the
analysis, traceability, and artifact-browser views — attach to this stack at the
clearly-marked attachment point below; v1 of this task provides the shell and
the open/branch/reload plumbing they depend upon.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QThread, QUrl, Signal, Slot
from PySide6.QtGui import QAction, QDesktopServices, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTabWidget,
    QToolBar,
    QWidget,
)

from syntagmax_desktop import git_branches
from syntagmax_desktop.git_branches import CheckoutRefused, GitBranchError
from syntagmax_desktop.session_worker import SessionWorker
from syntagmax_desktop.settings_store import SettingsStore
from syntagmax_desktop.views.analysis_panel import AnalysisPanel
from syntagmax_desktop.views.browser_panel import BrowserPanel
from syntagmax_desktop.views.trace_panel import TracePanel

#: The names of the panel tabs created in the central stack. The Wave-4 panels
#: attach their widgets to these tabs at the marked attachment point.
PANEL_TAB_NAMES = ('Analysis', 'Traceability', 'Artifacts')


class MainWindow(QMainWindow):
    """The top-level reviewer window.

    The window owns a :class:`SessionWorker` on a background :class:`QThread`
    and never calls ``syntagmax.api`` directly. An optional :class:`SettingsStore`
    may be injected so a test can scope the recent-projects list to a throwaway
    settings backend rather than the real user settings.
    """

    #: Emitted after an Open or Reload request has been dispatched to the worker,
    #: carrying the resolved request path. Primarily a test and diagnostics hook.
    openRequested = Signal(str)

    def __init__(self, settings_store: SettingsStore | None = None) -> None:
        super().__init__()
        self.setWindowTitle('Syntagmax Desktop')
        self.resize(1024, 720)

        self._settings_store = settings_store or SettingsStore()
        #: The path of the currently-open project, or ``None`` in the empty state.
        self._current_path: str | None = None
        #: Guards the branch combo so a programmatic repopulation does not look
        #: like a user-initiated branch switch.
        self._suppress_branch_signal = False
        #: True when the open project's HEAD is detached, so the branch combo
        #: stays disabled even after a busy run ends (R4, H-2).
        self._branch_detached = False
        #: True once a project has successfully opened; drives panel enablement
        #: so a busy cycle restores the correct state rather than enabling tabs
        #: in the empty state (R3, H-3).
        self._project_open = False

        self._worker, self._thread = self._build_worker()
        self._build_actions()
        self._build_toolbar()
        self._build_menu()
        self._build_central()
        self.set_panel('Analysis', AnalysisPanel(self._worker, self))
        self._browser_panel = BrowserPanel(self._worker, self)
        self.set_panel('Artifacts', self._browser_panel)
        self._build_status_bar()
        self._connect_worker()

        # Start in the empty state until a project is opened (R3).
        self._set_panels_enabled(False)
        self._refresh_recent_menu()

    # -- Construction -----------------------------------------------------

    def _build_worker(self) -> tuple[SessionWorker, QThread]:
        """Create the session worker on its own running background thread (R9)."""
        thread = QThread(self)
        worker = SessionWorker()
        worker.moveToThread(thread)
        # Destroy the worker inside its own thread once the thread finishes, so it
        # is never torn down from the UI thread (which triggers cross-thread timer
        # warnings and can race the worker's own event processing).
        thread.finished.connect(worker.deleteLater)
        thread.start()
        return worker, thread

    def _build_actions(self) -> None:
        """Create the New, Open, Reveal, Reload, and Quit actions."""
        self._new_action = QAction('&New Project…', self)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)
        self._new_action.triggered.connect(self.new_project_dialog)

        self._open_action = QAction('&Open Project…', self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self.open_project_dialog)

        self._reveal_action = QAction('Reveal Project &Folder', self)
        self._reveal_action.setEnabled(False)
        self._reveal_action.triggered.connect(self.reveal_project_folder)

        self._reload_action = QAction('&Reload', self)
        self._reload_action.setShortcut(QKeySequence(Qt.Key.Key_F5))
        self._reload_action.setEnabled(False)
        self._reload_action.triggered.connect(self.reload_project)

        self._quit_action = QAction('&Quit', self)
        self._quit_action.setShortcut(QKeySequence.StandardKey.Quit)
        self._quit_action.triggered.connect(self.close)

    def _build_toolbar(self) -> None:
        """Build the toolbar carrying Open, Reload, and the branch combo."""
        toolbar = QToolBar('Main', self)
        toolbar.setObjectName('mainToolbar')
        toolbar.addAction(self._new_action)
        toolbar.addAction(self._open_action)
        toolbar.addAction(self._reload_action)
        toolbar.addSeparator()

        self._branch_label = QLabel('Branch:')
        toolbar.addWidget(self._branch_label)
        self._branch_combo = QComboBox(self)
        self._branch_combo.setObjectName('branchCombo')
        self._branch_combo.setMinimumWidth(180)
        self._branch_combo.currentTextChanged.connect(self._on_branch_changed)
        toolbar.addWidget(self._branch_combo)

        # The branch control is hidden until an open project proves to be a git
        # working tree with at least one local branch (R4).
        self._set_branch_bar_visible(False)
        self.addToolBar(toolbar)

    def _build_menu(self) -> None:
        """Build the File menu with Open, Recent Projects, Reload, and Quit."""
        file_menu = self.menuBar().addMenu('&File')
        file_menu.addAction(self._new_action)
        file_menu.addAction(self._open_action)

        self._recent_menu = QMenu('Open &Recent', self)
        file_menu.addMenu(self._recent_menu)

        file_menu.addAction(self._reveal_action)
        file_menu.addAction(self._reload_action)
        file_menu.addSeparator()
        file_menu.addAction(self._quit_action)

    def _build_central(self) -> None:
        """Build the tabbed panel stack that hosts the Wave-4 panels."""
        self._tabs = QTabWidget(self)
        self._tabs.setObjectName('panelTabs')

        # -- Wave-4 panel attachment point --------------------------------
        # Each named tab below is a placeholder container. A later wave replaces
        # the placeholder widget via ``set_panel(name, widget)`` with the real
        # analysis, traceability, and artifact-browser panels; the open/branch
        # plumbing in this window drives them through the shared worker.
        self._panels: dict[str, QWidget] = {}
        for name in PANEL_TAB_NAMES:
            placeholder = QLabel(f'The {name} panel attaches here (Wave 4).')
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMargin(24)
            self._panels[name] = placeholder
            self._tabs.addTab(placeholder, name)
        # -- End Wave-4 panel attachment point -----------------------------

        self.setCentralWidget(self._tabs)
        self._trace_panel = TracePanel(self._worker, self)
        self.set_panel('Traceability', self._trace_panel)

    def _build_status_bar(self) -> None:
        """Add a status-bar busy indicator driven by ``busyChanged`` (R9)."""
        self._status_label = QLabel('Open a Syntagmax project to begin.')
        self.statusBar().addPermanentWidget(self._status_label)

    def _connect_worker(self) -> None:
        """Wire the worker's signals to the window's slots."""
        self._worker.opened.connect(self._on_opened)
        self._worker.created.connect(self._on_created)
        self._worker.atypesReady.connect(self._on_atypes_ready)
        self._worker.failed.connect(self._on_failed)
        self._worker.busyChanged.connect(self._on_busy_changed)

    # -- Public API -------------------------------------------------------

    @property
    def worker(self) -> SessionWorker:
        """Return the session worker, so callers and tests can observe its signals."""
        return self._worker

    def set_panel(self, name: str, widget: QWidget) -> None:
        """Replace the placeholder for tab ``name`` with a real panel ``widget`` (Wave-4 hook)."""
        if name not in self._panels:
            raise KeyError(f'Unknown panel tab {name!r}; expected one of {PANEL_TAB_NAMES}.')
        index = self._tabs.indexOf(self._panels[name])
        self._tabs.removeTab(index)
        self._panels[name] = widget
        self._tabs.insertTab(index, widget, name)

    def open_project_dialog(self) -> None:
        """Prompt for a ``config.toml`` or a project folder, then open it (R2)."""
        dialog = QFileDialog(self, 'Open Syntagmax Project')
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        dialog.setNameFilter('Syntagmax config (config.toml);;All files (*)')
        if dialog.exec() == QFileDialog.DialogCode.Accepted and dialog.selectedFiles():
            self.open_path(dialog.selectedFiles()[0])

    def open_path(self, path: str) -> None:
        """Open the project at ``path`` through the worker, recording it as current.

        ``path`` may be a ``config.toml`` file or a project folder; folder
        resolution is performed by ``core_facade`` inside the worker (R2). The
        path is retained so Reload and a branch switch can re-open it.
        """
        self._current_path = path
        self._dispatch_open(path)
        self.openRequested.emit(path)

    def new_project_dialog(self) -> None:
        """Pick a target folder, run safety checks, and scaffold a new project (R3, R4).

        The folder is validated on the UI thread before any dispatch: an
        existing project at either config location is refused (offering to open
        it instead), a non-empty non-project folder requires confirmation (with
        ``No`` as the safe default), and the non-empty inspection is guarded
        against OS/permission errors. The scaffold write itself runs off the UI
        thread via the worker (R7).
        """
        folder = QFileDialog.getExistingDirectory(
            self, 'New Syntagmax Project — choose or create an empty folder'
        )
        if not folder:
            return
        target = Path(folder)

        # R4: refuse an existing project at either config location (P7).
        if (target / '.syntagmax' / 'config.toml').is_file() or (target / 'config.toml').is_file():
            answer = QMessageBox.question(
                self,
                'Project exists',
                'This folder already contains a Syntagmax project. Open it instead?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.open_path(str(target))
            return

        # R4: guard the non-empty inspection against OS/permission errors (E3).
        try:
            non_empty = target.is_dir() and any(target.iterdir())
        except OSError as exc:
            QMessageBox.critical(self, 'Access error', f'Cannot access folder: {exc}')
            return

        # R4: default to No so an accidental keypress never scaffolds (P6).
        if non_empty:
            answer = QMessageBox.warning(
                self,
                'Folder not empty',
                'This folder is not empty and is not a Syntagmax project. '
                'Create a project here anyway?',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        QMetaObject.invokeMethod(
            self._worker,
            'createProject',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, str(target)),
        )

    def reveal_project_folder(self) -> None:
        """Open the current project root in the OS file manager (R5b, read-only)."""
        if self._current_path is None:
            return
        root = self._project_root_for(self._current_path)
        QDesktopServices.openUrl(QUrl.fromLocalFile(root))

    @staticmethod
    def _project_root_for(path: str) -> str:
        """Return the project-root directory for ``path`` (for the Markdown base URL, E8).

        ``path`` may be a picked ``config.toml`` file or a project folder. A file
        resolves to its containing directory; when that directory is the
        ``.syntagmax`` config folder, the root is its parent so relative image
        links resolve against the project root rather than ``.syntagmax`` (M-1).
        """
        candidate = Path(path)
        root = candidate.parent if candidate.is_file() else candidate
        if root.name == '.syntagmax':
            root = root.parent
        return str(root)

    def reload_project(self) -> None:
        """Re-open the current project from disk, reflecting external edits (R2a)."""
        if self._current_path is not None:
            self._dispatch_open(self._current_path)
            self.openRequested.emit(self._current_path)

    def _dispatch_open(self, path: str) -> None:
        """Marshal ``openProject`` onto the worker thread via a queued connection (R9).

        A direct call would run on the UI thread; a queued invocation guarantees
        the session is only ever created and touched on the worker thread.
        """
        QMetaObject.invokeMethod(
            self._worker,
            'openProject',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, path),
        )

    # -- Worker signal handlers ------------------------------------------

    @Slot(bool)
    def _on_opened(self, success: bool) -> None:
        """React to an open outcome: enable the UI, or stay in the empty state (R3)."""
        if not success:
            # A ``failed`` signal has already surfaced the diagnostic; clear the
            # current project and remain in the empty state so the reviewer can
            # retry from scratch rather than reload a project that never opened.
            self._current_path = None
            self._set_panels_enabled(False)
            self._reload_action.setEnabled(False)
            self._reveal_action.setEnabled(False)
            self._set_branch_bar_visible(False)
            return

        self._set_panels_enabled(True)
        self._reload_action.setEnabled(True)
        self._reveal_action.setEnabled(True)
        self._populate_branches()
        if self._current_path is not None:
            self._remember_recent(self._current_path)
            self._browser_panel.set_project_root(self._project_root_for(self._current_path))
            self._browser_panel.refresh()
        # Populate the traceability selectors from the project's artifact types
        # on the worker thread (R7, H-1); without this the trace panel is inert.
        QMetaObject.invokeMethod(self._worker, 'runAtypes', Qt.ConnectionType.QueuedConnection)
        self._status_label.setText(f'Opened {self._current_path}')

    @Slot(str)
    def _on_created(self, config_path: str) -> None:
        """Open the freshly scaffolded project through the normal flow (R5, R6, E9).

        The project *root* (the parent of ``.syntagmax``) is passed to
        ``open_path`` rather than the raw ``config.toml`` path, so the MRU stores
        a folder, consistent with folder-based opens; ``core_facade.open``
        resolves it back to the config.
        """
        root = Path(config_path).parent.parent  # <root>/.syntagmax/config.toml -> <root>
        self.open_path(str(root))

    @Slot(object)
    def _on_atypes_ready(self, atypes: object) -> None:
        """Feed discovered artifact types into the traceability selectors (R7, H-1)."""
        self._trace_panel.set_atypes(list(atypes))

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        """Show a non-fatal error dialog and keep the application running (R3)."""
        QMessageBox.critical(self, 'Syntagmax Desktop', message)
        self._status_label.setText('Ready')

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        """Drive the status-bar indicator and mask the UI during a run (R9, E5, H-3).

        Because the worker serialises every request on a single thread, the whole
        interactive surface — the panel tabs (with their Run buttons and the
        artifact search box), the open/reload actions, and the branch combo — is
        disabled while a run is in flight, so secondary requests cannot be queued
        behind a long analysis or trace.
        """
        self._new_action.setEnabled(not busy)
        self._open_action.setEnabled(not busy)
        self._reload_action.setEnabled(not busy and self._current_path is not None)
        self._reveal_action.setEnabled(not busy and self._current_path is not None and self._project_open)
        # Disable the Recent Projects menu too, so a recent re-open cannot be
        # queued behind an in-flight run and overwrite the current path (M-1).
        self._recent_menu.setEnabled(not busy and bool(self._settings_store.recent_projects()))
        self._branch_combo.setEnabled(not busy and not self._branch_detached)
        # While busy, mask the panel stack; when idle, restore it to the
        # project-open state (disabled in the empty state) rather than
        # unconditionally enabling it (R9, E5, H-3).
        self._tabs.setEnabled(not busy and self._current_path is not None and self._project_open)
        self._status_label.setText('Working…' if busy else 'Ready')

    # -- Branch bar -------------------------------------------------------

    def _populate_branches(self) -> None:
        """Populate the branch combo for the current project, hiding it if not a repo (R4)."""
        if self._current_path is None:
            self._set_branch_bar_visible(False)
            return

        branches = git_branches.list_branches(self._current_path)
        if not branches:
            # Not a git working tree (or no local branches); hide the control
            # rather than report an error (R4).
            self._branch_detached = False
            self._set_branch_bar_visible(False)
            return

        try:
            current = git_branches.current_branch(self._current_path)
        except Exception:  # noqa: BLE001 - a label failure must never block the open flow (R4)
            current = ''

        detached = current.startswith('(HEAD detached')
        self._branch_detached = detached

        self._suppress_branch_signal = True
        try:
            self._branch_combo.clear()
            if detached:
                # Show the detached-HEAD label and forbid switching (R4, H-2):
                # the label is not a real branch, so switching from it is unsafe.
                self._branch_combo.addItem(current)
                self._branch_combo.addItems(branches)
                self._branch_combo.setCurrentText(current)
            else:
                self._branch_combo.addItems(branches)
                if current in branches:
                    self._branch_combo.setCurrentText(current)
        finally:
            self._suppress_branch_signal = False
        self._branch_combo.setEnabled(not detached)
        self._set_branch_bar_visible(True)

    @Slot(str)
    def _on_branch_changed(self, name: str) -> None:
        """Perform a guarded checkout to ``name`` and re-open the project (R4)."""
        if self._suppress_branch_signal or not name or self._current_path is None:
            return

        try:
            git_branches.checkout(self._current_path, name)
        except CheckoutRefused as exc:
            QMessageBox.warning(self, 'Branch switch refused', str(exc))
            self._populate_branches()  # revert the combo to the real current branch.
            return
        except GitBranchError as exc:
            QMessageBox.critical(self, 'Branch switch failed', str(exc))
            self._populate_branches()
            return

        # Re-open on the newly checked-out branch with a fresh Session (R4).
        self._dispatch_open(self._current_path)
        self.openRequested.emit(self._current_path)

    def _set_branch_bar_visible(self, visible: bool) -> None:
        """Show or hide the branch label and combo together."""
        self._branch_label.setVisible(visible)
        self._branch_combo.setVisible(visible)

    # -- Recent projects --------------------------------------------------

    def _remember_recent(self, path: str) -> None:
        """Persist ``path`` into the MRU store and rebuild the Recent menu (P4)."""
        self._settings_store.add_recent(path)
        self._refresh_recent_menu()

    def _refresh_recent_menu(self) -> None:
        """Rebuild the Recent Projects menu from the MRU store (P4)."""
        self._recent_menu.clear()
        recents = self._settings_store.recent_projects()
        self._recent_menu.setEnabled(bool(recents))
        for path in recents:
            action = QAction(path, self)
            action.triggered.connect(lambda _checked=False, target=path: self.open_path(target))
            self._recent_menu.addAction(action)

    # -- Panel enablement -------------------------------------------------

    def _set_panels_enabled(self, enabled: bool) -> None:
        """Enable or disable the whole panel tab stack (R3).

        Also records whether a project is open so a subsequent busy cycle
        restores the correct enablement rather than enabling the empty state (H-3).
        """
        self._project_open = enabled
        self._tabs.setEnabled(enabled)

    # -- Lifecycle --------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name.
        """Stop the worker thread cleanly before the window closes."""
        self._thread.quit()
        self._thread.wait(5000)
        super().closeEvent(event)
