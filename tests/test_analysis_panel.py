"""Tests for the analysis panel (Task 6, spec R5, P3).

The grouping-and-filtering business logic lives in the pure
:func:`~syntagmax_desktop.views.analysis_panel.group_diagnostics` helper, so the
bulk of these tests construct :class:`~syntagmax.api.Diagnostic` values directly
and assert on the grouped mapping without a ``QApplication``. A single offscreen
smoke test exercises the widget's render path end-to-end: ``QT_QPA_PLATFORM`` is
forced to ``offscreen`` before any Qt import so no display is required (E3).
"""

import os

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from syntagmax.api import AnalysisResult, Diagnostic

from syntagmax_desktop.views.analysis_panel import (
    SEVERITY_FILTERS,
    UNSPECIFIED_LOCATION,
    group_diagnostics,
)


def _diagnostic(severity: str, location: str = '', *, rule: str = 'R1', message: str = 'msg') -> Diagnostic:
    """Build a :class:`Diagnostic` with sensible defaults for the fields under test."""
    return Diagnostic(
        severity=severity,
        artifact_id='A-1',
        rule=rule,
        category='structure',
        location=location,
        message=message,
    )


ALL_SEVERITIES = set(SEVERITY_FILTERS)


# -- group_diagnostics: grouping by location --------------------------------


def test_groups_by_location() -> None:
    diagnostics = [
        _diagnostic('error', 'a.md:1-2'),
        _diagnostic('warning', 'b.md:3-4'),
        _diagnostic('info', 'a.md:1-2'),
    ]
    grouped = group_diagnostics(diagnostics, ALL_SEVERITIES)
    assert set(grouped) == {'a.md:1-2', 'b.md:3-4'}
    assert len(grouped['a.md:1-2']) == 2
    assert len(grouped['b.md:3-4']) == 1


def test_preserves_first_seen_location_order() -> None:
    diagnostics = [
        _diagnostic('error', 'z.md'),
        _diagnostic('warning', 'a.md'),
        _diagnostic('info', 'z.md'),
    ]
    grouped = group_diagnostics(diagnostics, ALL_SEVERITIES)
    assert list(grouped) == ['z.md', 'a.md']


# -- group_diagnostics: unspecified-location fallback -----------------------


def test_blank_location_falls_back_to_unspecified() -> None:
    diagnostics = [_diagnostic('error', ''), _diagnostic('warning', '   ')]
    grouped = group_diagnostics(diagnostics, ALL_SEVERITIES)
    assert set(grouped) == {UNSPECIFIED_LOCATION}
    assert len(grouped[UNSPECIFIED_LOCATION]) == 2


def test_none_location_falls_back_to_unspecified() -> None:
    diagnostic = _diagnostic('error', '')
    diagnostic.location = None  # core should give a string, but tolerate None.
    grouped = group_diagnostics([diagnostic], ALL_SEVERITIES)
    assert set(grouped) == {UNSPECIFIED_LOCATION}


# -- group_diagnostics: severity filtering ----------------------------------


def test_error_only_filter_drops_warnings_and_info() -> None:
    diagnostics = [
        _diagnostic('error', 'a.md'),
        _diagnostic('warning', 'a.md'),
        _diagnostic('info', 'a.md'),
    ]
    grouped = group_diagnostics(diagnostics, {'Error'})
    assert set(grouped) == {'a.md'}
    assert len(grouped['a.md']) == 1
    assert grouped['a.md'][0].severity == 'error'


def test_severity_match_is_case_insensitive() -> None:
    # The core emits lower-case severities; the filter labels are capitalised.
    diagnostics = [_diagnostic('ERROR', 'a.md'), _diagnostic('Warning', 'a.md')]
    grouped = group_diagnostics(diagnostics, {'Error'})
    assert len(grouped['a.md']) == 1


def test_empty_severity_set_drops_everything() -> None:
    diagnostics = [_diagnostic('error', 'a.md'), _diagnostic('warning', 'b.md')]
    assert group_diagnostics(diagnostics, set()) == {}


def test_no_diagnostics_returns_empty_mapping() -> None:
    assert group_diagnostics([], ALL_SEVERITIES) == {}


# -- Offscreen render smoke test --------------------------------------------


def test_panel_renders_result_without_a_display(qtbot) -> None:
    from syntagmax_desktop.session_worker import SessionWorker
    from syntagmax_desktop.views.analysis_panel import AnalysisPanel

    worker = SessionWorker()
    panel = AnalysisPanel(worker)
    qtbot.addWidget(panel)

    # A clean result shows the positive "no issues" confirmation, not the tree.
    clean = AnalysisResult(diagnostics=[], metrics={'artifacts': 3, 'links': 5}, impact=None)
    panel._on_analysis_ready(clean)
    assert panel._empty_label.isVisibleTo(panel) is True
    assert 'cleanly' in panel._empty_label.text()
    assert panel._tree.isVisibleTo(panel) is False

    # A result with diagnostics populates the grouped tree instead.
    noisy = AnalysisResult(
        diagnostics=[_diagnostic('error', 'a.md'), _diagnostic('warning', '')],
        metrics=None,
        impact=None,
    )
    panel._on_analysis_ready(noisy)
    assert panel._tree.isVisibleTo(panel) is True
    assert panel._tree.topLevelItemCount() == 2  # 'a.md' and the Unspecified group.

    # Filtering to Error-only collapses to the single error group.
    panel._severity_checks['Warning'].setChecked(False)
    panel._severity_checks['Info'].setChecked(False)
    assert panel._tree.topLevelItemCount() == 1
