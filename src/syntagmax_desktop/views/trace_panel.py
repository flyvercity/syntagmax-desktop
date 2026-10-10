# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: The traceability panel — atype and direction selectors, a Flat toggle, a matrix table, and CSV/TSV export.

"""The traceability panel (spec R6, E2/X3, E6, E7).

The panel lets a reviewer pick a child and a parent artifact type, choose a
trace direction, independently toggle a flattened matrix, run the trace off the
UI thread through the shared :class:`~syntagmax_desktop.session_worker.SessionWorker`,
and export the rendered matrix to CSV or TSV.

Two orthogonal controls drive the trace (E2, X3): a **direction** selector
offering ``forward`` and ``reverse``, and a **separate** ``Flat`` checkbox.
``flat`` is never folded into direction — "Run" passes ``direction`` and
``flat`` to :meth:`SessionWorker.runTrace` as distinct arguments. The result is
rendered through a :class:`~syntagmax_desktop.models.trace_model.TraceTableModel`
(not a per-cell widget table) so a large matrix stays responsive (E6). Export
writes CSV as ``utf-8-sig`` for Excel; a :class:`PermissionError` — the file
being open in Excel, for instance — surfaces a non-fatal dialog rather than
crashing (E7).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from syntagmax.api import TraceResult

from syntagmax_desktop.models.trace_model import TraceTableModel
from syntagmax_desktop.session_worker import SessionWorker

#: The two orthogonal trace directions offered by the direction selector (E2, X3).
DIRECTIONS = ('forward', 'reverse')


class TracePanel(QWidget):
    """The traceability matrix panel.

    The panel owns a :class:`TraceTableModel` bound to a :class:`QTableView` and
    drives the shared :class:`SessionWorker` through queued-connected request
    signals, so a trace runs off the UI thread (R9). A signal, rather than a
    bare :func:`QMetaObject.invokeMethod`, is used because a queued signal
    marshals an arbitrary Python payload — such as a :class:`TraceResult` — onto
    the worker thread cleanly, whereas a hand-built ``Q_ARG`` for a ``PyObject``
    slot does not round-trip reliably. The most recent :class:`TraceResult` is
    retained so an export renders exactly what the reviewer sees.
    """

    #: Queued-connected to :meth:`SessionWorker.runTrace`; carries ``child``,
    #: ``parent``, ``direction``, and ``flat`` as four distinct arguments (E2, X3).
    _traceRequested = Signal(str, str, str, bool)
    #: Queued-connected to :meth:`SessionWorker.exportTrace`; carries the result,
    #: destination path, and delimiter (E7).
    _exportRequested = Signal(object, str, str)

    def __init__(self, worker: SessionWorker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        #: The most recent trace result, retained for export; ``None`` until a run completes.
        self._result: TraceResult | None = None

        self._model = TraceTableModel(parent=self)
        self._build_ui()
        self._connect_worker()

    # -- Construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the control bar, the matrix view, and the export button."""
        root = QVBoxLayout(self)

        controls = QHBoxLayout()

        controls.addWidget(QLabel('Child:'))
        self._child_combo = QComboBox(self)
        self._child_combo.setObjectName('childCombo')
        controls.addWidget(self._child_combo)

        controls.addWidget(QLabel('Parent:'))
        self._parent_combo = QComboBox(self)
        self._parent_combo.setObjectName('parentCombo')
        controls.addWidget(self._parent_combo)

        controls.addWidget(QLabel('Direction:'))
        self._direction_combo = QComboBox(self)
        self._direction_combo.setObjectName('directionCombo')
        self._direction_combo.addItems(DIRECTIONS)
        controls.addWidget(self._direction_combo)

        # The Flat toggle is a separate, orthogonal control — never folded into
        # the direction selector (E2, X3).
        self._flat_checkbox = QCheckBox('Flat', self)
        self._flat_checkbox.setObjectName('flatCheckbox')
        controls.addWidget(self._flat_checkbox)

        self._run_button = QPushButton('Run', self)
        self._run_button.setObjectName('runButton')
        self._run_button.clicked.connect(self.run_trace)
        controls.addWidget(self._run_button)

        self._export_button = QPushButton('Export…', self)
        self._export_button.setObjectName('exportButton')
        self._export_button.clicked.connect(self.export_trace)
        self._export_button.setEnabled(False)
        controls.addWidget(self._export_button)

        controls.addStretch(1)
        root.addLayout(controls)

        self._table = QTableView(self)
        self._table.setObjectName('traceTable')
        self._table.setModel(self._model)
        self._table.setAlternatingRowColors(True)
        root.addWidget(self._table)

    def _connect_worker(self) -> None:
        """Wire the panel's request signals and the worker's ``traceReady`` signal.

        The request signals are connected with an explicit queued connection so
        each call is marshalled onto the worker thread, never run inline on the
        UI thread (R9).
        """
        self._traceRequested.connect(self._worker.runTrace, Qt.ConnectionType.QueuedConnection)
        self._exportRequested.connect(self._worker.exportTrace, Qt.ConnectionType.QueuedConnection)
        self._worker.traceReady.connect(self._on_trace_ready)

    # -- Public API -------------------------------------------------------

    def set_atypes(self, atypes: list[str]) -> None:
        """Populate the child and parent selectors from the project's artifact types.

        The current selections are preserved when still valid so re-populating
        after a reload does not reset a reviewer's choice.
        """
        for combo in (self._child_combo, self._parent_combo):
            previous = combo.currentText()
            combo.clear()
            combo.addItems(atypes)
            if previous in atypes:
                combo.setCurrentText(previous)

    def run_trace(self) -> None:
        """Dispatch a trace to the worker with ``direction`` and ``flat`` as separate arguments (E2, X3)."""
        child = self._child_combo.currentText()
        parent = self._parent_combo.currentText()
        if not child or not parent:
            return
        direction = self._direction_combo.currentText()
        flat = self._flat_checkbox.isChecked()
        self._traceRequested.emit(child, parent, direction, flat)

    def export_trace(self) -> None:
        """Prompt for a CSV or TSV destination, then dispatch the export to the worker (E7).

        The delimiter is derived from the chosen filter — a comma for CSV and a
        tab for TSV — so the written file matches the extension. A
        :class:`PermissionError` is surfaced non-fatally; the worker catches it
        and re-raises it as a ``failed`` message, so here the dialog guards the
        reviewer-facing path dialog itself.
        """
        if self._result is None:
            return

        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            'Export Trace Matrix',
            '',
            'CSV (*.csv);;TSV (*.tsv)',
        )
        if not path:
            return

        delimiter = '\t' if selected_filter.startswith('TSV') or path.lower().endswith('.tsv') else ','

        try:
            self._exportRequested.emit(self._result, path, delimiter)
        except PermissionError as exc:
            # A destination locked by another application (Excel holding the file
            # open, for instance) must not crash the panel (E7).
            QMessageBox.warning(self, 'Export failed', f'Could not write {path}: {exc}')

    @property
    def model(self) -> TraceTableModel:
        """Return the table model, so callers and tests can inspect the rendered matrix."""
        return self._model

    @property
    def result(self) -> TraceResult | None:
        """Return the most recent trace result, or ``None`` before the first run."""
        return self._result

    # -- Worker signal handlers ------------------------------------------

    @Slot(object)
    def _on_trace_ready(self, result: TraceResult) -> None:
        """Render a completed trace into the model and enable export."""
        self._result = result
        self._model.set_result(result)
        self._export_button.setEnabled(True)
