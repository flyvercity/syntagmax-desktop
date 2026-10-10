# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: A QAbstractTableModel projecting a TraceResult onto a dense matrix view.

"""A :class:`~PySide6.QtCore.QAbstractTableModel` for a traceability matrix (spec R6, E6).

A :class:`~syntagmax.api.TraceResult` is a dense ``header`` plus ``rows`` matrix
that can grow large. Rendering it through a model, rather than materialising a
per-cell :class:`QTableWidgetItem`, keeps a big matrix responsive because the
view pulls only the cells it paints (E6). The model is read-only: a reviewer
inspects and exports the matrix but never edits it in place.
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt

from syntagmax.api import TraceResult


class TraceTableModel(QAbstractTableModel):
    """Expose a :class:`~syntagmax.api.TraceResult` as a read-only Qt table model.

    The model holds the result's ``header`` as horizontal section labels and its
    ``rows`` as the table body, serving each cell on demand so a large matrix is
    never flattened into widgets (E6). Call :meth:`set_result` to swap in a fresh
    trace — the model resets so attached views repaint cleanly.
    """

    def __init__(self, result: TraceResult | None = None, parent: object | None = None) -> None:
        super().__init__(parent)
        self._header: list[str] = []
        self._rows: list[list[str]] = []
        if result is not None:
            self._adopt(result)

    # -- Public API -------------------------------------------------------

    def set_result(self, result: TraceResult | None) -> None:
        """Replace the backing trace result, resetting the model for attached views."""
        self.beginResetModel()
        if result is None:
            self._header = []
            self._rows = []
        else:
            self._adopt(result)
        self.endResetModel()

    def _adopt(self, result: TraceResult) -> None:
        """Copy the result's header and rows into the model's own lists."""
        self._header = list(result.header)
        self._rows = [list(row) for row in result.rows]

    # -- QAbstractTableModel overrides -----------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt override name.
        """Return the number of body rows (zero for a child index)."""
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def columnCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt override name.
        """Return the number of columns, taken from the header width."""
        if parent is not None and parent.isValid():
            return 0
        return len(self._header)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201 - Qt variant return.
        """Return the display text for a cell, or ``None`` for other roles.

        A cell beyond a given row's length renders as an empty string so a ragged
        matrix never raises an index error during painting.
        """
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = index.row()
        column = index.column()
        if not (0 <= row < len(self._rows)):
            return None
        cells = self._rows[row]
        if not (0 <= column < len(cells)):
            return ''
        return cells[column]

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: N802 - Qt override name.
        """Return a horizontal header label, or a 1-based row number vertically."""
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if 0 <= section < len(self._header):
                return self._header[section]
            return None
        return section + 1
