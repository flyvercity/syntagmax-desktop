"""Tests for the threaded session worker (Task 4).

The worker is exercised on a real :class:`~PySide6.QtCore.QThread` with queued
signal connections, exactly as the application wires it, so the tests confirm
the cross-thread contract rather than a same-thread shortcut. ``qtbot`` drives
the Qt event loop and asserts on the emitted signals, and ``QT_QPA_PLATFORM`` is
forced to ``offscreen`` so no display is required (E3).
"""

import os
import shutil
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from PySide6.QtCore import Qt, QThread

from syntagmax.api import AnalysisResult

from syntagmax_desktop.session_worker import SessionWorker, _redact

EXAMPLE_PROJECT = Path(__file__).resolve().parents[1] / 'syntagmax' / 'example' / 'obsidian-driver'


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Copy the example project into a temporary directory, leaving the fixture pristine."""
    destination = tmp_path / 'obsidian-driver'
    shutil.copytree(EXAMPLE_PROJECT, destination)
    return destination


@pytest.fixture
def worker(qtbot):
    """Create a :class:`SessionWorker` moved onto its own running :class:`QThread`."""
    thread = QThread()
    instance = SessionWorker()
    instance.moveToThread(thread)
    thread.start()
    try:
        yield instance
    finally:
        thread.quit()
        thread.wait(5000)


def _invoke(worker: SessionWorker, slot: str, *args) -> None:
    """Trigger a worker slot via a queued connection so it runs on the worker thread."""
    from PySide6.QtCore import QMetaObject

    # A queued connection marshals the call onto the worker thread's event loop,
    # so the session is only ever touched off the UI thread (E3).
    QMetaObject.invokeMethod(worker, slot, Qt.ConnectionType.QueuedConnection, *_as_qt_args(args))


def _as_qt_args(args):
    """Wrap positional arguments as :class:`~PySide6.QtCore.Q_ARG` descriptors."""
    from PySide6.QtCore import Q_ARG

    typed = []
    for value in args:
        if isinstance(value, bool):
            typed.append(Q_ARG(bool, value))
        elif isinstance(value, str):
            typed.append(Q_ARG(str, value))
        else:
            typed.append(Q_ARG('QVariant', value))
    return typed


def test_open_project_success_emits_opened_true(qtbot, worker, project_dir: Path):
    with qtbot.waitSignal(worker.opened, timeout=10000) as blocker:
        _invoke(worker, 'openProject', str(project_dir))
    assert blocker.args == [True]


def test_open_project_bad_path_emits_failed_and_opened_false(qtbot, worker, tmp_path: Path):
    missing = tmp_path / 'does-not-exist'
    with qtbot.waitSignal(worker.failed, timeout=10000) as failed_blocker:
        with qtbot.waitSignal(worker.opened, timeout=10000) as opened_blocker:
            _invoke(worker, 'openProject', str(missing))
    assert opened_blocker.args == [False]
    assert isinstance(failed_blocker.args[0], str)
    assert failed_blocker.args[0]


def test_run_analyse_emits_analysis_ready(qtbot, worker, project_dir: Path):
    with qtbot.waitSignal(worker.opened, timeout=10000):
        _invoke(worker, 'openProject', str(project_dir))

    with qtbot.waitSignal(worker.analysisReady, timeout=20000) as blocker:
        _invoke(worker, 'runAnalyse')
    assert isinstance(blocker.args[0], AnalysisResult)


def test_run_analyse_without_open_emits_failed(qtbot, worker):
    with qtbot.waitSignal(worker.failed, timeout=10000) as blocker:
        _invoke(worker, 'runAnalyse')
    assert 'No project is open' in blocker.args[0]


def test_busy_toggles_true_then_false_around_a_run(qtbot, worker, project_dir: Path):
    states: list[bool] = []
    worker.busyChanged.connect(states.append)

    with qtbot.waitSignal(worker.opened, timeout=10000):
        _invoke(worker, 'openProject', str(project_dir))

    # The busy signal must bracket the run: True first, then False, in order (E3, E5).
    assert states[0] is True
    assert states[-1] is False
    assert states == [True, False]


def test_redact_masks_credentials_and_tokens():
    assert '[REDACTED]' in _redact('postgres://user:supersecret@db.example.com/app')
    assert 'supersecret' not in _redact('postgres://user:supersecret@db.example.com/app')

    masked = _redact('connection failed with password=hunter2 for user bob')
    assert 'hunter2' not in masked
    assert '[REDACTED]' in masked

    long_token = 'abcdef0123456789abcdef0123456789abcd'
    assert long_token not in _redact(f'auth rejected token {long_token}')
