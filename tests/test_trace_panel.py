"""Tests for the traceability panel and its table model (Task 7, spec R6, E2/X3, E6, E7).

The model tests exercise :class:`~syntagmax_desktop.models.trace_model.TraceTableModel`
directly against a hand-built :class:`~syntagmax.api.TraceResult`, so they need no
Qt event loop beyond a constructed :class:`~PySide6.QtWidgets.QApplication`. The
panel test drives the real queued-connection path through a stub worker that
captures the ``runTrace`` arguments, proving that ``direction`` and ``flat`` are
passed as separate arguments rather than one being folded into the other (E2,
X3). ``QT_QPA_PLATFORM`` is forced to ``offscreen`` before any Qt import so no
display is required (E3).
"""

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtWidgets import QFileDialog

from syntagmax.api import TraceResult

from syntagmax_desktop.models.trace_model import TraceTableModel
from syntagmax_desktop.views.trace_panel import DIRECTIONS, TracePanel


def _sample_result(direction: str = 'forward') -> TraceResult:
    """Build a small, deterministic :class:`TraceResult` for the model tests."""
    return TraceResult(
        direction=direction,
        child_type='REQ',
        parent_type='SYS',
        header=['RecordNumber', 'ChildID', 'ParentID', 'Title'],
        rows=[
            ['1', 'REQ-1', 'SYS-1', 'First requirement'],
            ['2', 'REQ-2', 'SYS-2', 'Second requirement'],
            ['3', 'REQ-3', '', 'Orphan'],
        ],
        record_names={'REQ-1': 'req-one', 'SYS-1': 'sys-one'},
    )


# -- TraceTableModel --------------------------------------------------------


def test_model_row_and_column_counts() -> None:
    model = TraceTableModel(_sample_result())
    assert model.rowCount() == 3
    assert model.columnCount() == 4


def test_model_data_returns_cell_text() -> None:
    model = TraceTableModel(_sample_result())
    assert model.data(model.index(0, 1)) == 'REQ-1'
    assert model.data(model.index(1, 2)) == 'SYS-2'
    assert model.data(model.index(2, 3)) == 'Orphan'


def test_model_header_data_horizontal_and_vertical() -> None:
    model = TraceTableModel(_sample_result())
    assert model.headerData(0, Qt.Orientation.Horizontal) == 'RecordNumber'
    assert model.headerData(3, Qt.Orientation.Horizontal) == 'Title'
    # Vertical headers are 1-based row numbers.
    assert model.headerData(0, Qt.Orientation.Vertical) == 1
    assert model.headerData(2, Qt.Orientation.Vertical) == 3


def test_model_set_result_resets_contents() -> None:
    model = TraceTableModel()
    assert model.rowCount() == 0
    assert model.columnCount() == 0

    model.set_result(_sample_result())
    assert model.rowCount() == 3

    model.set_result(None)
    assert model.rowCount() == 0
    assert model.columnCount() == 0


def test_model_data_ignores_non_display_roles() -> None:
    model = TraceTableModel(_sample_result())
    assert model.data(model.index(0, 0), Qt.ItemDataRole.EditRole) is None


# -- TracePanel -------------------------------------------------------------


class _StubWorker(QObject):
    """A minimal worker double that captures the ``runTrace`` call arguments.

    It carries the same ``traceReady`` signal and a ``runTrace`` slot with the
    identical ``(str, str, str, bool)`` signature as the real worker, so the
    panel's queued invocation reaches it unchanged and the test can assert that
    ``direction`` and ``flat`` arrive as separate arguments (E2, X3).
    """

    traceReady = Signal(object)
    captured = Signal()
    exported = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str, str, str, bool]] = []
        self.exports: list[tuple[object, str, str]] = []

    @Slot(str, str, str, bool)
    def runTrace(self, child: str, parent: str, direction: str, flat: bool) -> None:  # noqa: N802 - mirrors the worker slot.
        self.calls.append((child, parent, direction, flat))
        self.captured.emit()

    @Slot(object, str, str)
    def exportTrace(self, result: object, path: str, delimiter: str) -> None:  # noqa: N802 - mirrors the worker slot.
        self.exports.append((result, path, delimiter))
        self.exported.emit()


@pytest.fixture
def panel(qtbot) -> tuple[TracePanel, _StubWorker]:
    """Construct a :class:`TracePanel` wired to a stub worker, populated with atypes."""
    worker = _StubWorker()
    widget = TracePanel(worker)
    qtbot.addWidget(widget)
    widget.set_atypes(['REQ', 'SYS'])
    return widget, worker


def test_panel_populates_selectors_from_atypes(panel) -> None:
    widget, _worker = panel
    child_items = [widget._child_combo.itemText(i) for i in range(widget._child_combo.count())]
    parent_items = [widget._parent_combo.itemText(i) for i in range(widget._parent_combo.count())]
    assert child_items == ['REQ', 'SYS']
    assert parent_items == ['REQ', 'SYS']
    # The direction selector offers both orthogonal directions.
    direction_items = [widget._direction_combo.itemText(i) for i in range(widget._direction_combo.count())]
    assert direction_items == list(DIRECTIONS)


def test_run_passes_direction_and_flat_as_separate_arguments(qtbot, panel) -> None:
    widget, worker = panel
    widget._child_combo.setCurrentText('REQ')
    widget._parent_combo.setCurrentText('SYS')
    widget._direction_combo.setCurrentText('reverse')
    widget._flat_checkbox.setChecked(True)

    with qtbot.waitSignal(worker.captured, timeout=5000):
        widget.run_trace()

    # The worker received four distinct arguments; ``flat`` is never folded into
    # ``direction`` (E2, X3).
    assert worker.calls == [('REQ', 'SYS', 'reverse', True)]


def test_run_passes_forward_unflattened_independently(qtbot, panel) -> None:
    widget, worker = panel
    widget._child_combo.setCurrentText('REQ')
    widget._parent_combo.setCurrentText('SYS')
    widget._direction_combo.setCurrentText('forward')
    widget._flat_checkbox.setChecked(False)

    with qtbot.waitSignal(worker.captured, timeout=5000):
        widget.run_trace()

    assert worker.calls == [('REQ', 'SYS', 'forward', False)]


def test_trace_ready_renders_into_model_and_enables_export(panel) -> None:
    widget, worker = panel
    assert widget._export_button.isEnabled() is False

    worker.traceReady.emit(_sample_result())

    assert widget.model.rowCount() == 3
    assert widget.result is not None
    assert widget._export_button.isEnabled() is True


def test_export_uses_matching_delimiter_for_tsv(qtbot, panel, monkeypatch, tmp_path) -> None:
    widget, worker = panel
    worker.traceReady.emit(_sample_result())

    target = tmp_path / 'matrix.tsv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(target), 'TSV (*.tsv)')))

    with qtbot.waitSignal(worker.exported, timeout=5000):
        widget.export_trace()

    # TSV is written with a tab delimiter, matching the chosen filter (E7).
    assert len(worker.exports) == 1
    _result, path, delimiter = worker.exports[0]
    assert path == str(target)
    assert delimiter == '\t'


def test_export_uses_comma_for_csv(qtbot, panel, monkeypatch, tmp_path) -> None:
    widget, worker = panel
    worker.traceReady.emit(_sample_result())

    target = tmp_path / 'matrix.csv'
    monkeypatch.setattr(QFileDialog, 'getSaveFileName', staticmethod(lambda *a, **k: (str(target), 'CSV (*.csv)')))

    with qtbot.waitSignal(worker.exported, timeout=5000):
        widget.export_trace()

    assert len(worker.exports) == 1
    _result, _path, delimiter = worker.exports[0]
    assert delimiter == ','
