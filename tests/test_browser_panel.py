"""Tests for the read-only artifact browser panel (Task 8, spec R8, P2, E5, E6, E8).

The panel drives a :class:`~syntagmax_desktop.session_worker.SessionWorker` only
through queued slot invocations and reacts to its ``queryReady`` and
``searchReady`` signals, so these tests substitute a lightweight fake worker that
records the slots the panel invokes and lets the test emit the result signals
with real :class:`~syntagmax.api.ArtifactView` fixtures. ``QT_QPA_PLATFORM`` is
forced to ``offscreen`` before any Qt import so no display is required, and
cross-thread timing is observed through ``pytest-qt``'s ``qtbot``.
"""

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from PySide6.QtCore import QObject, Signal, Slot

from syntagmax_desktop import core_facade
from syntagmax_desktop.models.artifact_list_model import AID_ROLE, IS_HEADER_ROLE
from syntagmax_desktop.views.browser_panel import SEARCH_DEBOUNCE_MS, BrowserPanel

EXAMPLE_PROJECT = Path(__file__).resolve().parents[1] / 'syntagmax' / 'example' / 'obsidian-driver'


class FakeWorker(QObject):
    """A stand-in worker that records the panel's queued slot invocations.

    It exposes the same ``queryReady`` and ``searchReady`` signals the panel
    consumes, and ``runQuery``/``runSearch`` slots the panel invokes via
    ``QMetaObject.invokeMethod`` — so a queued invocation lands here on the event
    loop just as it would on the real worker, letting a test count the calls (E5).
    """

    queryReady = Signal(object)
    searchReady = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self.query_calls: list[str] = []
        self.search_calls: list[str] = []

    @Slot(str)
    def runQuery(self, atype: str) -> None:  # noqa: N802 - matches the real worker slot name.
        self.query_calls.append(atype)

    @Slot(str)
    def runSearch(self, q: str) -> None:  # noqa: N802 - matches the real worker slot name.
        self.search_calls.append(q)


@pytest.fixture(scope='module')
def artifacts():
    """Open the committed fixture once and return its artifact views (read-only)."""
    session = core_facade.open(EXAMPLE_PROJECT)
    views = core_facade.query(session)
    assert views  # guard: the fixture must have a non-empty artifact graph.
    return views


@pytest.fixture
def worker(qtbot) -> FakeWorker:
    return FakeWorker()


@pytest.fixture
def panel(qtbot, worker: FakeWorker) -> BrowserPanel:
    instance = BrowserPanel(worker)
    instance.set_project_root(str(EXAMPLE_PROJECT))
    qtbot.addWidget(instance)
    return instance


def _populate(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    """Drive a full query result into the panel as the real worker would."""
    worker.queryReady.emit(artifacts)


def _visible_aids(panel: BrowserPanel) -> list[str]:
    """Return the aids of the artifact (non-header) rows currently in the model."""
    model = panel._model
    aids: list[str] = []
    for row in range(model.rowCount()):
        index = model.index(row, 0)
        if not index.data(IS_HEADER_ROLE):
            aids.append(index.data(AID_ROLE))
    return aids


def test_populates_from_fixture(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    expected = sorted(view.aid for view in artifacts)
    assert sorted(_visible_aids(panel)) == expected
    # The grouped list introduces each atype with a non-selectable header row (E6).
    header_count = sum(1 for row in range(panel._model.rowCount()) if panel._model.index(row, 0).data(IS_HEADER_ROLE))
    assert header_count == len({view.atype for view in artifacts})


def test_type_filter_narrows_to_subset(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    atypes = sorted({view.atype for view in artifacts})
    assert len(atypes) >= 2  # guard: a meaningful filter needs more than one type.
    target = atypes[0]

    index = panel._type_combo.findData(target)
    assert index != -1
    panel._type_combo.setCurrentIndex(index)

    expected = sorted(view.aid for view in artifacts if view.atype == target)
    assert sorted(_visible_aids(panel)) == expected


def test_known_search_term_yields_expected_matches(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    # Pick a real aid, then emit a search result as the worker would for its id.
    target = artifacts[0]
    matches = [view for view in artifacts if view.aid == target.aid]
    worker.searchReady.emit(matches)

    assert _visible_aids(panel) == [target.aid]


def test_search_is_debounced(qtbot, panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    worker.search_calls.clear()

    # A rapid burst of keystrokes must coalesce into a single worker call (E5).
    for fragment in ('R', 'RE', 'REQ'):
        panel._search_box.setText(fragment)

    # Before the debounce elapses, nothing has been dispatched.
    assert worker.search_calls == []

    # After the debounce window, exactly one search fires for the final text.
    qtbot.waitUntil(lambda: worker.search_calls == ['REQ'], timeout=SEARCH_DEBOUNCE_MS * 8)
    assert worker.search_calls == ['REQ']


def test_clicking_parent_id_selects_target(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)

    # Find an artifact that has at least one parent link, and its parent id.
    child = next((view for view in artifacts if view.parents), None)
    assert child is not None, 'the fixture must contain at least one child-with-parent'
    parent_id = str(child.parents[0]['pid'])
    assert parent_id in panel._by_aid, 'the parent id must resolve to a real artifact'

    captured: list[str] = []
    panel.artifactSelected.connect(captured.append)

    # Simulate clicking the parent link rendered in the detail view (P2).
    from PySide6.QtCore import QUrl

    panel._on_link_clicked(QUrl(f'artifact:{parent_id}'))

    current = panel._list_view.selectionModel().currentIndex()
    assert current.isValid()
    assert current.data(AID_ROLE) == parent_id
    assert captured and captured[-1] == parent_id


def test_detail_shows_body_text(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    target = next((view for view in artifacts if view.body), None)
    assert target is not None, 'the fixture must contain at least one artifact with a body'

    panel.select_artifact(target.aid)

    rendered = panel._body_view.toPlainText()
    assert rendered.strip()  # the body renders as non-empty plain text.
    # A distinctive word from the body survives Markdown rendering.
    probe = next((word for word in target.body.split() if word.isalpha() and len(word) >= 4), None)
    if probe is not None:
        assert probe in rendered


def test_dangling_link_returns_false(panel: BrowserPanel, worker: FakeWorker, artifacts) -> None:
    _populate(panel, worker, artifacts)
    # A link to a non-existent id resolves to no selection but does not raise (P2).
    assert panel.select_artifact('NO-SUCH-ARTIFACT-XYZ') is False
