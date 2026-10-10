# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: The analysis panel — a metrics strip plus diagnostics grouped by location, with severity filtering.

"""The analysis panel (spec R5, P3).

The panel runs analysis through the shared :class:`SessionWorker` and renders the
result in two parts: a metrics strip of labelled stat cards, tolerant of a
``None`` or unknown-shaped ``metrics`` payload, and a diagnostics view that groups
issues by their source location, with an explicit "Unspecified location" group for
blank or missing locations. A row of severity toggles (Error, Warning, and Info)
sits above the grouped list so a reviewer can hide informational notices and keep
blocking issues visible, rather than burying them (P3). When analysis reports no
issues under the active filter, the panel shows a positive "no issues"
confirmation instead of a bare, empty widget.

The grouping-and-filtering business logic lives in the pure, UI-free helper
:func:`group_diagnostics`, so it can be unit-tested without constructing a
``QApplication``.
"""

from __future__ import annotations

from collections import OrderedDict

from PySide6.QtCore import QMetaObject, Qt, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from syntagmax.api import AnalysisResult, Diagnostic

from syntagmax_desktop.session_worker import SessionWorker

#: The label used for diagnostics whose ``location`` is blank or missing.
UNSPECIFIED_LOCATION = 'Unspecified location'

#: The severity toggles shown above the grouped list, in priority order so the
#: most blocking severity sits first (P3). Matching against a diagnostic's
#: ``severity`` is case-insensitive, since the core emits lower-case values.
SEVERITY_FILTERS = ('Error', 'Warning', 'Info')

#: The diagnostic columns rendered under each location group.
DIAGNOSTIC_COLUMNS = ('Severity', 'Rule', 'Category', 'Message', 'Artifact')


def group_diagnostics(diagnostics: list[Diagnostic], severities: set[str]) -> dict[str, list[Diagnostic]]:
    """Group ``diagnostics`` by location, keeping only the active ``severities`` (R5, P3).

    This is the pure core of the panel, free of any Qt dependency so it can be
    unit-tested directly. A diagnostic survives the filter when its ``severity``
    matches one of ``severities`` case-insensitively; an empty ``severities``
    set therefore drops everything. Survivors are bucketed by ``location``, with
    a blank or missing location mapped to the explicit
    :data:`UNSPECIFIED_LOCATION` group. Insertion order is preserved so the
    rendered groups follow the order in which locations are first seen.
    """
    active = {severity.casefold() for severity in severities}
    grouped: 'OrderedDict[str, list[Diagnostic]]' = OrderedDict()
    for diagnostic in diagnostics:
        severity = (diagnostic.severity or '').casefold()
        if severity not in active:
            continue
        location = (diagnostic.location or '').strip() or UNSPECIFIED_LOCATION
        grouped.setdefault(location, []).append(diagnostic)
    return dict(grouped)


class AnalysisPanel(QWidget):
    """The analysis view: a metrics strip over a severity-filtered, grouped diagnostics tree.

    The panel never touches ``syntagmax.api`` directly; it marshals the analysis
    request onto the shared :class:`SessionWorker` via a queued connection and
    renders the ``analysisReady`` result when it arrives.
    """

    def __init__(self, worker: SessionWorker, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._worker = worker
        #: The most recent diagnostics, retained so a severity-toggle change can
        #: re-render without re-running analysis.
        self._diagnostics: list[Diagnostic] = []
        #: ``True`` once a result has been rendered, so the empty-state copy can
        #: distinguish "not run yet" from "ran, and found nothing".
        self._has_result = False

        self._build_ui()
        self._worker.analysisReady.connect(self._on_analysis_ready)
        self._render()

    # -- Construction -----------------------------------------------------

    def _build_ui(self) -> None:
        """Build the run control, metrics strip, severity toggles, and diagnostics tree."""
        layout = QVBoxLayout(self)

        self._run_button = QPushButton('Run analysis', self)
        self._run_button.setObjectName('runAnalysisButton')
        self._run_button.clicked.connect(self.run_analysis)

        run_row = QHBoxLayout()
        run_row.addWidget(self._run_button)
        run_row.addStretch(1)
        layout.addLayout(run_row)

        # -- Metrics strip -------------------------------------------------
        self._metrics_scroll = QScrollArea(self)
        self._metrics_scroll.setObjectName('metricsStrip')
        self._metrics_scroll.setWidgetResizable(True)
        self._metrics_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._metrics_scroll.setFixedHeight(96)
        self._metrics_host = QWidget(self._metrics_scroll)
        self._metrics_layout = QHBoxLayout(self._metrics_host)
        self._metrics_layout.setContentsMargins(0, 0, 0, 0)
        self._metrics_layout.addStretch(1)
        self._metrics_scroll.setWidget(self._metrics_host)
        layout.addWidget(self._metrics_scroll)

        # -- Severity toggles ----------------------------------------------
        self._severity_checks: dict[str, QCheckBox] = {}
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel('Show:'))
        for severity in SEVERITY_FILTERS:
            check = QCheckBox(severity, self)
            check.setObjectName(f'severity{severity}')
            check.setChecked(True)
            check.toggled.connect(self._render_diagnostics)
            self._severity_checks[severity] = check
            filter_row.addWidget(check)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        # -- Diagnostics area ----------------------------------------------
        self._empty_label = QLabel(self)
        self._empty_label.setObjectName('diagnosticsEmptyLabel')
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_label.setWordWrap(True)
        self._empty_label.setMargin(24)
        layout.addWidget(self._empty_label)

        self._tree = QTreeWidget(self)
        self._tree.setObjectName('diagnosticsTree')
        self._tree.setColumnCount(len(DIAGNOSTIC_COLUMNS))
        self._tree.setHeaderLabels(list(DIAGNOSTIC_COLUMNS))
        self._tree.setAlternatingRowColors(True)
        layout.addWidget(self._tree, 1)

    # -- Public API -------------------------------------------------------

    def run_analysis(self) -> None:
        """Request analysis on the worker thread via a queued connection (R5, R9).

        A direct call would run on the UI thread; the queued invocation keeps the
        session confined to the worker thread, consistent with the rest of the app.
        """
        QMetaObject.invokeMethod(self._worker, 'runAnalyse', Qt.ConnectionType.QueuedConnection)

    def active_severities(self) -> set[str]:
        """Return the set of severity labels whose toggle is currently checked (P3)."""
        return {severity for severity, check in self._severity_checks.items() if check.isChecked()}

    # -- Worker signal handlers ------------------------------------------

    @Slot(object)
    def _on_analysis_ready(self, result: AnalysisResult) -> None:
        """Render a freshly-arrived analysis result (R5)."""
        self._has_result = True
        self._diagnostics = list(getattr(result, 'diagnostics', None) or [])
        self._render_metrics(getattr(result, 'metrics', None))
        self._render_diagnostics()

    # -- Rendering --------------------------------------------------------

    def _render(self) -> None:
        """Render the initial, pre-run state."""
        self._render_metrics(None)
        self._render_diagnostics()

    def _render_metrics(self, metrics: object) -> None:
        """Render the metrics strip as labelled stat cards, tolerant of any shape (R5).

        ``metrics`` is a ``benedict`` or ``None`` passed through unchanged from
        the core, so no fixed schema is assumed: a mapping is rendered as one card
        per top-level key, a non-mapping scalar as a single card, and ``None`` as a
        quiet placeholder. Values that are themselves containers are summarised
        rather than expanded, so the strip stays a glanceable overview.
        """
        self._clear_metrics()

        cards: list[tuple[str, str]] = []
        if isinstance(metrics, dict):
            for key, value in metrics.items():
                cards.append((str(key), self._format_metric_value(value)))
        elif metrics is not None:
            cards.append(('Metrics', self._format_metric_value(metrics)))

        if not cards:
            placeholder = QLabel('No metrics reported.' if self._has_result else 'Run analysis to see metrics.')
            placeholder.setObjectName('metricsPlaceholder')
            self._metrics_layout.insertWidget(0, placeholder)
            return

        for index, (title, value) in enumerate(cards):
            self._metrics_layout.insertWidget(index, self._make_metric_card(title, value))

    @staticmethod
    def _format_metric_value(value: object) -> str:
        """Format a single metric value for a stat card, summarising containers."""
        if isinstance(value, dict):
            return f'{len(value)} item(s)'
        if isinstance(value, (list, tuple, set)):
            return f'{len(value)} item(s)'
        return str(value)

    def _make_metric_card(self, title: str, value: str) -> QFrame:
        """Build a single labelled stat card for the metrics strip."""
        card = QFrame(self._metrics_host)
        card.setObjectName('metricCard')
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(12, 6, 12, 6)

        value_label = QLabel(value, card)
        value_label.setObjectName('metricValue')
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_label = QLabel(title, card)
        title_label.setObjectName('metricTitle')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        card_layout.addWidget(value_label)
        card_layout.addWidget(title_label)
        return card

    def _clear_metrics(self) -> None:
        """Remove every metric card, keeping the trailing stretch in place."""
        while self._metrics_layout.count() > 1:
            item = self._metrics_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    @Slot()
    def _render_diagnostics(self) -> None:
        """Render the grouped, severity-filtered diagnostics tree (R5, P3).

        Delegates the grouping-and-filtering to the pure :func:`group_diagnostics`
        helper, then populates the tree. An empty result shows a positive
        confirmation rather than a bare, empty widget: distinct copy is used for
        "no issues at all" and "nothing matches the current filter", so a reviewer
        is never left wondering whether a filter is hiding something.
        """
        self._tree.clear()
        grouped = group_diagnostics(self._diagnostics, self.active_severities())

        if not grouped:
            self._tree.setVisible(False)
            self._empty_label.setVisible(True)
            self._empty_label.setText(self._empty_message())
            return

        self._empty_label.setVisible(False)
        self._tree.setVisible(True)
        for location, items in grouped.items():
            group_item = QTreeWidgetItem([f'{location}  ({len(items)})'])
            for diagnostic in items:
                group_item.addChild(
                    QTreeWidgetItem(
                        [
                            diagnostic.severity or '',
                            diagnostic.rule or '',
                            diagnostic.category or '',
                            diagnostic.message or '',
                            diagnostic.artifact_id or '',
                        ]
                    )
                )
            self._tree.addTopLevelItem(group_item)
            group_item.setFirstColumnSpanned(True)
            group_item.setExpanded(True)
        self._tree.resizeColumnToContents(0)

    def _empty_message(self) -> str:
        """Return the positive empty-state copy appropriate to the current state (R5)."""
        if not self._has_result:
            return 'Run analysis to review diagnostics.'
        if not self._diagnostics:
            return 'No issues found — the project analysed cleanly.'
        return 'No issues match the current severity filter.'
