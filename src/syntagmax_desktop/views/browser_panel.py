# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: Read-only artifact browser — grouped list, type filter, debounced search, and detail view.

"""The read-only artifact browser panel (spec R8, P2, E5, E6, E8).

The panel presents the artifact graph for review: a type-filter combo narrows the
list by ``atype``; an ``atype``-grouped virtual list (backed by
:class:`~syntagmax_desktop.models.artifact_list_model.ArtifactListModel`) scales
to large sets (E6); and a search box drives a debounced content search so a full
linear :meth:`~syntagmax.api.Session.search` scan fires once the reviewer pauses
typing rather than on every keystroke (E5).

Selecting an artifact shows a detail view: a key/value table of its ``fields``
and a rendered-Markdown body (E8). Parent and child ids are rendered as clickable
links that select the target artifact in the list (P2); following a dangling or
filtered-out link clears the type filter first so the target is revealed rather
than silently missed.

The panel never touches ``syntagmax.api`` directly. It drives the shared
:class:`~syntagmax_desktop.session_worker.SessionWorker` through queued slot
invocations and consumes its ``queryReady`` and ``searchReady`` signals, so every
core call runs off the UI thread (R9).
"""

from __future__ import annotations

from html import escape
from pathlib import Path

from PySide6.QtCore import Q_ARG, QItemSelectionModel, QMetaObject, Qt, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QLabel,
    QLineEdit,
    QListView,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from syntagmax.api import ArtifactView

from syntagmax_desktop.models.artifact_list_model import AID_ROLE, IS_HEADER_ROLE, ArtifactListModel
from syntagmax_desktop.session_worker import SessionWorker
from syntagmax_desktop.widgets.markdown_view import MarkdownView

#: The debounce interval, in milliseconds, between the last ``textChanged`` and
#: the search dispatch, so a burst of keystrokes fires a single scan (E5).
SEARCH_DEBOUNCE_MS = 250

#: The URL scheme used for the clickable relationship links in the detail view; a
#: click on ``artifact:REQ-001`` selects that artifact in the list (P2).
_LINK_SCHEME = 'artifact'


class BrowserPanel(QWidget):
    """The read-only artifact browser: grouped list, type filter, search, and detail view.

    The panel owns no session: it drives the shared :class:`SessionWorker` through
    queued slot invocations and reacts to its ``queryReady`` and ``searchReady``
    signals. Call :meth:`set_project_root` so a body's relative images resolve
    (E8), and :meth:`refresh` after a project opens to repopulate the list.
    """

    #: Emitted when an artifact row is selected, carrying its aid. A test and
    #: diagnostics hook; the panel updates its own detail view regardless.
    artifactSelected = Signal(str)

    def __init__(self, worker: SessionWorker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('browserPanel')
        self._worker = worker
        #: All artifacts currently held, keyed by aid, for the detail view.
        self._by_aid: dict[str, ArtifactView] = {}
        #: The project root for Markdown base-URL resolution (E8).
        self._project_root: Path | None = None

        self._model = ArtifactListModel(self)
        self._build_ui()
        self._build_debounce()
        self._connect()

    # -- Construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the filter bar, grouped list, and detail view."""
        layout = QVBoxLayout(self)

        # -- Filter bar: a type-filter combo and a debounced search box. ---
        self._type_combo = QComboBox(self)
        self._type_combo.setObjectName('typeFilterCombo')
        self._type_combo.addItem('All types', userData=None)

        self._search_box = QLineEdit(self)
        self._search_box.setObjectName('searchBox')
        self._search_box.setPlaceholderText('Search artifacts…')
        self._search_box.setClearButtonEnabled(True)

        filter_row = QWidget(self)
        filter_layout = QVBoxLayout(filter_row)
        filter_layout.setContentsMargins(0, 0, 0, 0)
        filter_layout.addWidget(self._type_combo)
        filter_layout.addWidget(self._search_box)
        layout.addWidget(filter_row)

        # -- Body: the grouped list beside the artifact detail view. -------
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self._list_view = QListView(splitter)
        self._list_view.setObjectName('artifactList')
        self._list_view.setModel(self._model)
        self._list_view.setUniformItemSizes(True)
        self._list_view.setSelectionMode(QListView.SelectionMode.SingleSelection)
        splitter.addWidget(self._list_view)

        detail = QWidget(splitter)
        detail_layout = QVBoxLayout(detail)
        detail_layout.setContentsMargins(0, 0, 0, 0)

        self._fields_view = QTextBrowser(detail)
        self._fields_view.setObjectName('fieldsView')
        self._fields_view.setOpenLinks(False)
        self._fields_view.setMaximumHeight(260)

        self._body_view = MarkdownView(detail)

        detail_layout.addWidget(self._fields_view)
        detail_layout.addWidget(self._body_view)
        splitter.addWidget(detail)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)

        layout.addWidget(splitter)
        self._empty_label = QLabel('No project is open.', self)
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _build_debounce(self) -> None:
        """Create the single-shot search timer that coalesces keystrokes (E5)."""
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(SEARCH_DEBOUNCE_MS)
        self._search_timer.timeout.connect(self._dispatch_search)

    def _connect(self) -> None:
        """Wire the controls, the selection model, and the worker's result signals."""
        self._type_combo.currentIndexChanged.connect(self._on_type_filter_changed)
        self._search_box.textChanged.connect(self._on_search_text_changed)
        self._fields_view.anchorClicked.connect(self._on_link_clicked)

        selection = self._list_view.selectionModel()
        selection.currentChanged.connect(self._on_current_row_changed)

        self._worker.queryReady.connect(self._on_query_ready)
        self._worker.searchReady.connect(self._on_search_ready)

    # -- Public API -------------------------------------------------------

    def set_project_root(self, project_root: str | Path | None) -> None:
        """Set the project root for a body's relative-resource resolution (E8)."""
        self._project_root = Path(project_root) if project_root is not None else None
        self._body_view.set_project_root(self._project_root)

    def refresh(self) -> None:
        """Repopulate the list by dispatching a full, unfiltered query (R8)."""
        self._search_box.blockSignals(True)
        self._search_box.clear()
        self._search_box.blockSignals(False)
        self._search_timer.stop()
        self._dispatch_query('')

    # -- Dispatch (off-thread) -------------------------------------------

    def _dispatch_query(self, atype: str) -> None:
        """Marshal ``runQuery`` onto the worker thread via a queued connection (R9)."""
        QMetaObject.invokeMethod(
            self._worker,
            'runQuery',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, atype),
        )

    def _dispatch_search(self) -> None:
        """Marshal ``runSearch`` onto the worker thread via a queued connection (E5, R9).

        An empty query falls back to a full query so clearing the search box
        restores the complete list rather than searching for nothing.
        """
        query = self._search_box.text().strip()
        if not query:
            self._dispatch_query(self._active_atype() or '')
            return
        QMetaObject.invokeMethod(
            self._worker,
            'runSearch',
            Qt.ConnectionType.QueuedConnection,
            Q_ARG(str, query),
        )

    # -- Control handlers -------------------------------------------------

    @Slot(int)
    def _on_type_filter_changed(self, _index: int) -> None:
        """Narrow the visible rows to the selected atype (R8)."""
        self._model.set_type_filter(self._active_atype())

    @Slot(str)
    def _on_search_text_changed(self, _text: str) -> None:
        """Restart the debounce timer so the scan fires once typing pauses (E5)."""
        self._search_timer.start()

    def _active_atype(self) -> str | None:
        """Return the atype selected in the filter combo, or ``None`` for all types."""
        return self._type_combo.currentData()

    # -- Worker result handlers ------------------------------------------

    @Slot(object)
    def _on_query_ready(self, artifacts: list[ArtifactView]) -> None:
        """Adopt a fresh query result, rebuilding the type combo and the list (R8)."""
        self._adopt(artifacts, rebuild_types=True)

    @Slot(object)
    def _on_search_ready(self, artifacts: list[ArtifactView]) -> None:
        """Adopt a search result, keeping the existing type combo intact (E5)."""
        self._adopt(artifacts, rebuild_types=False)

    def _adopt(self, artifacts: list[ArtifactView], *, rebuild_types: bool) -> None:
        """Store ``artifacts`` and feed them to the list model."""
        self._by_aid = {view.aid: view for view in artifacts}
        if rebuild_types:
            self._rebuild_type_combo(artifacts)
        self._model.set_artifacts(artifacts)
        self._model.set_type_filter(self._active_atype())

    def _rebuild_type_combo(self, artifacts: list[ArtifactView]) -> None:
        """Repopulate the type-filter combo from the atypes present, preserving the choice."""
        previous = self._active_atype()
        atypes = sorted({view.atype for view in artifacts})
        self._type_combo.blockSignals(True)
        try:
            self._type_combo.clear()
            self._type_combo.addItem('All types', userData=None)
            for atype in atypes:
                self._type_combo.addItem(atype, userData=atype)
            if previous in atypes:
                self._type_combo.setCurrentIndex(self._type_combo.findData(previous))
        finally:
            self._type_combo.blockSignals(False)

    # -- Selection and detail view ---------------------------------------

    @Slot(object, object)
    def _on_current_row_changed(self, current, _previous) -> None:  # noqa: ANN001 - Qt QModelIndex args.
        """Render the detail view for the newly-selected artifact row (P2)."""
        if current is None or not current.isValid():
            return
        if current.data(IS_HEADER_ROLE):
            self._show_detail(None)
            return
        aid = current.data(AID_ROLE)
        self._show_detail(aid)
        if aid:
            self.artifactSelected.emit(aid)

    def select_artifact(self, aid: str) -> bool:
        """Select the artifact ``aid`` in the list, revealing it if filtered out (P2).

        When ``aid`` is not visible under the active type filter — a dangling or
        cross-type link — the filter is cleared so the target is revealed, then
        selected. Returns ``True`` when a matching row was selected.
        """
        row = self._model.row_for_aid(aid)
        if row is None and aid in self._by_aid:
            # The target exists but is hidden by the type filter; clear the filter
            # so the link resolves rather than silently failing (P2).
            self._type_combo.setCurrentIndex(0)
            row = self._model.row_for_aid(aid)
        if row is None:
            # A genuinely dangling link: show the detail stub so the reviewer sees
            # the id was followed even though no artifact backs it.
            self._show_detail(aid)
            return False
        index = self._model.index(row, 0)
        self._list_view.selectionModel().setCurrentIndex(
            index,
            QItemSelectionModel.SelectionFlag.ClearAndSelect,
        )
        self._list_view.scrollTo(index)
        return True

    def _show_detail(self, aid: str | None) -> None:
        """Render the fields table and the Markdown body for ``aid``."""
        view = self._by_aid.get(aid) if aid else None
        if view is None:
            if aid:
                self._fields_view.setHtml(f'<p>No artifact found for <b>{escape(aid)}</b> (dangling link).</p>')
            else:
                self._fields_view.setHtml('<p>Select an artifact to view its detail.</p>')
            self._body_view.set_body('')
            return
        self._fields_view.setHtml(self._render_fields_html(view))
        self._body_view.set_body(view.body)

    def _render_fields_html(self, view: ArtifactView) -> str:
        """Build the key/value fields table with clickable relationship links (P2)."""
        rows: list[str] = [
            f'<tr><th align="left">aid</th><td>{escape(view.aid)}</td></tr>',
            f'<tr><th align="left">atype</th><td>{escape(view.atype)}</td></tr>',
        ]
        for key, value in view.fields.items():
            rows.append(f'<tr><th align="left">{escape(str(key))}</th><td>{escape(self._field_text(value))}</td></tr>')

        parent_ids = [str(link.get('pid')) for link in view.parents if link.get('pid')]
        rows.append(f'<tr><th align="left">parents</th><td>{self._link_cell(parent_ids)}</td></tr>')
        rows.append(f'<tr><th align="left">children</th><td>{self._link_cell(list(view.children))}</td></tr>')
        return '<table cellspacing="4" width="100%">' + ''.join(rows) + '</table>'

    @staticmethod
    def _field_text(value: str | list[str]) -> str:
        """Flatten a field value to a single display string."""
        if isinstance(value, list):
            return ', '.join(str(item) for item in value)
        return str(value)

    @staticmethod
    def _link_cell(ids: list[str]) -> str:
        """Render a list of ids as clickable ``artifact:`` links, or an em dash when empty (P2)."""
        if not ids:
            return '—'
        links = [f'<a href="{_LINK_SCHEME}:{escape(aid)}">{escape(aid)}</a>' for aid in ids]
        return ', '.join(links)

    @Slot(object)
    def _on_link_clicked(self, url) -> None:  # noqa: ANN001 - Qt QUrl argument.
        """Resolve a clicked relationship link to a selection in the list (P2)."""
        if url.scheme() != _LINK_SCHEME:
            return
        aid = url.path()
        self.select_artifact(aid)
