# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: A virtual QAbstractListModel over artifacts, grouped by atype with a type filter.

"""A virtual list model over artifacts, grouped by ``atype`` (spec R8, E6, P2).

:class:`ArtifactListModel` adapts a flat list of :class:`~syntagmax.api.ArtifactView`
objects to Qt's model-view framework. Rows are presented grouped by ``atype`` —
each group introduced by a non-selectable header row — so a reviewer scanning a
large graph sees artifacts clustered by type rather than in insertion order. A
type filter narrows the visible rows to a single ``atype`` without rebuilding the
backing data, and the model serves each row on demand so a large set stays
responsive (E6).

Two custom roles are exposed alongside the display text: ``AID_ROLE`` carries an
artifact's id (``None`` for a header row), and ``IS_HEADER_ROLE`` flags whether a
row is a group header. A view uses these to resolve a clicked row back to an
artifact and to render, or skip, header rows (P2).
"""

from __future__ import annotations

from PySide6.QtCore import QAbstractListModel, QModelIndex, Qt

from syntagmax.api import ArtifactView

#: Role carrying the artifact id for a row, or ``None`` for a group header row.
AID_ROLE = Qt.ItemDataRole.UserRole + 1
#: Role carrying ``True`` for a group-header row and ``False`` for an artifact row.
IS_HEADER_ROLE = Qt.ItemDataRole.UserRole + 2


class _Row:
    """A single visible row: either a group header, or an artifact entry."""

    __slots__ = ('atype', 'aid', 'label', 'is_header')

    def __init__(self, atype: str, aid: str | None, label: str, is_header: bool) -> None:
        self.atype = atype
        self.aid = aid
        self.label = label
        self.is_header = is_header


class ArtifactListModel(QAbstractListModel):
    """Expose artifacts as an ``atype``-grouped, filterable, read-only list model.

    Call :meth:`set_artifacts` to adopt a fresh set of views, and
    :meth:`set_type_filter` to narrow the visible rows to a single ``atype`` (or
    to all types with ``None``). The flattened, grouped rows are recomputed on
    each change and served on demand, so the view materialises only what it
    paints (E6).
    """

    def __init__(self, parent: object | None = None) -> None:
        super().__init__(parent)
        #: All adopted artifacts, in a stable, grouped order.
        self._artifacts: list[ArtifactView] = []
        #: The active atype filter, or ``None`` for "all types".
        self._type_filter: str | None = None
        #: The flattened, visible rows (headers interleaved with artifact rows).
        self._rows: list[_Row] = []

    # -- Public API -------------------------------------------------------

    def set_artifacts(self, artifacts: list[ArtifactView]) -> None:
        """Adopt ``artifacts`` and rebuild the grouped, filtered rows."""
        self.beginResetModel()
        # Group by atype, then order each group by aid, for a stable layout.
        self._artifacts = sorted(artifacts, key=lambda view: (view.atype, view.aid))
        self._rebuild_rows()
        self.endResetModel()

    def set_type_filter(self, atype: str | None) -> None:
        """Narrow the visible rows to ``atype``, or show all types with ``None``."""
        normalised = atype or None
        if normalised == self._type_filter:
            return
        self.beginResetModel()
        self._type_filter = normalised
        self._rebuild_rows()
        self.endResetModel()

    @property
    def type_filter(self) -> str | None:
        """Return the active atype filter, or ``None`` when all types are shown."""
        return self._type_filter

    def atypes(self) -> list[str]:
        """Return the sorted, distinct atypes across all adopted artifacts."""
        return sorted({view.atype for view in self._artifacts})

    def aid_at(self, row: int) -> str | None:
        """Return the artifact id at ``row``, or ``None`` for a header or an out-of-range row."""
        if 0 <= row < len(self._rows):
            return self._rows[row].aid
        return None

    def row_for_aid(self, aid: str) -> int | None:
        """Return the row index for ``aid``, or ``None`` when it is not currently visible.

        A dangling or filtered-out id returns ``None`` so a caller can decide to
        widen the filter before trying again (P2).
        """
        for index, row in enumerate(self._rows):
            if not row.is_header and row.aid == aid:
                return index
        return None

    def is_header(self, row: int) -> bool:
        """Return whether ``row`` is a group-header row."""
        if 0 <= row < len(self._rows):
            return self._rows[row].is_header
        return False

    # -- Internal ---------------------------------------------------------

    def _rebuild_rows(self) -> None:
        """Flatten the adopted artifacts into grouped, filtered rows."""
        rows: list[_Row] = []
        current_type: str | None = None
        for view in self._artifacts:
            if self._type_filter is not None and view.atype != self._type_filter:
                continue
            if view.atype != current_type:
                current_type = view.atype
                rows.append(_Row(atype=view.atype, aid=None, label=view.atype, is_header=True))
            label = self._label_for(view)
            rows.append(_Row(atype=view.atype, aid=view.aid, label=label, is_header=False))
        self._rows = rows

    @staticmethod
    def _label_for(view: ArtifactView) -> str:
        """Build a one-line label for an artifact row.

        A ``name`` or ``title`` field, when present, is appended after the id so
        a reviewer recognises the artifact without opening the detail view.
        """
        name = view.fields.get('name') or view.fields.get('title')
        if isinstance(name, list):
            name = name[0] if name else None
        if name:
            return f'{view.aid} — {name}'
        return view.aid

    # -- QAbstractListModel overrides ------------------------------------

    def rowCount(self, parent: QModelIndex | None = None) -> int:  # noqa: N802 - Qt override name.
        """Return the number of visible rows (zero for a child index)."""
        if parent is not None and parent.isValid():
            return 0
        return len(self._rows)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):  # noqa: ANN201 - Qt variant return.
        """Serve the display text and the custom aid and header roles for a row."""
        if not index.isValid():
            return None
        row = index.row()
        if not (0 <= row < len(self._rows)):
            return None
        entry = self._rows[row]
        if role == Qt.ItemDataRole.DisplayRole:
            return entry.label
        if role == AID_ROLE:
            return entry.aid
        if role == IS_HEADER_ROLE:
            return entry.is_header
        return None

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        """Mark header rows as non-selectable so only artifact rows are chosen."""
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        entry = self._rows[index.row()]
        if entry.is_header:
            return Qt.ItemFlag.ItemIsEnabled
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
