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

from PySide6.QtCore import Q_ARG, QMetaObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QAction, QKeySequence
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
        """Create the Open, Reload, and Quit actions."""
        self._open_action = QAction('&Open Project…', self)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)
        self._open_action.triggered.connect(self.open_project_dialog)

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
        file_menu.addAction(self._open_action)

        self._recent_menu = QMenu('Open &Recent', self)
        file_menu.addMenu(self._recent_menu)

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
        self.set_panel('Traceability', TracePanel(self._worker, self))

    def _build_status_bar(self) -> None:
        """Add a status-bar busy indicator driven by ``busyChanged`` (R9)."""
        self._status_label = QLabel('Open a Syntagmax project to begin.')
        self.statusBar().addPermanentWidget(self._status_label)

    def _connect_worker(self) -> None:
        """Wire the worker's signals to the window's slots."""
        self._worker.opened.connect(self._on_opened)
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

    @staticmethod
    def _project_root_for(path: str) -> str:
        """Return the project-root directory for ``path`` (for the Markdown base URL, E8).

        ``path`` may be a picked ``config.toml`` file or a project folder; a file
        resolves to its containing directory, a directory is used as-is.
        """
        candidate = Path(path)
        return str(candidate.parent if candidate.is_file() else candidate)

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
            self._set_branch_bar_visible(False)
            return

        self._set_panels_enabled(True)
        self._reload_action.setEnabled(True)
        self._populate_branches()
        if self._current_path is not None:
            self._remember_recent(self._current_path)
            self._browser_panel.set_project_root(self._project_root_for(self._current_path))
            self._browser_panel.refresh()
        self._status_label.setText(f'Opened {self._current_path}')

    @Slot(str)
    def _on_failed(self, message: str) -> None:
        """Show a non-fatal error dialog and keep the application running (R3)."""
        QMessageBox.critical(self, 'Syntagmax Desktop', message)
        self._status_label.setText('Ready')

    @Slot(bool)
    def _on_busy_changed(self, busy: bool) -> None:
        """Drive the status-bar indicator and disable actions during a run (R9)."""
        self._open_action.setEnabled(not busy)
        self._reload_action.setEnabled(not busy and self._current_path is not None)
        self._branch_combo.setEnabled(not busy)
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
            self._set_branch_bar_visible(False)
            return

        try:
            current = git_branches.current_branch(self._current_path)
        except Exception:  # noqa: BLE001 - a label failure must never block the open flow (R4)
            current = ''

        self._suppress_branch_signal = True
        try:
            self._branch_combo.clear()
            self._branch_combo.addItems(branches)
            if current in branches:
                self._branch_combo.setCurrentText(current)
        finally:
            self._suppress_branch_signal = False
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
        """Enable or disable the whole panel tab stack (R3)."""
        self._tabs.setEnabled(enabled)

    # -- Lifecycle --------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override name.
        """Stop the worker thread cleanly before the window closes."""
        self._thread.quit()
        self._thread.wait(5000)
        super().closeEvent(event)
