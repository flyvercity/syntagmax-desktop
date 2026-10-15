"""Tests for the main reviewer window (Task 5, spec R2, R2a, R3, R4, P4).

The window owns a :class:`~syntagmax_desktop.session_worker.SessionWorker` on a
background :class:`~PySide6.QtCore.QThread`, so these tests drive the real
cross-thread open flow through ``qtbot.waitSignal`` with Qt's offscreen platform
(E3). ``QT_QPA_PLATFORM`` is forced to ``offscreen`` before any Qt import so no
display is required.

The committed example project under ``syntagmax/example`` is opened read-only
(the app never mutates it), so pointing the window straight at the fixture is
safe and also exercises the real ``git_branches.list_branches`` path — the
fixture lives inside the outer repository's submodule, which reports at least one
local branch so the branch combo is populated and shown.
"""

import os
from pathlib import Path

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

import pytest

from PySide6.QtCore import QSettings

from syntagmax_desktop import git_branches
from syntagmax_desktop.settings_store import SettingsStore
from syntagmax_desktop.views.main_window import PANEL_TAB_NAMES, MainWindow

EXAMPLE_PROJECT = Path(__file__).resolve().parents[1] / 'syntagmax' / 'example' / 'obsidian-driver'


@pytest.fixture
def settings_store(tmp_path: Path) -> SettingsStore:
    """A :class:`SettingsStore` scoped to a throwaway INI, never the real user settings."""
    ini_path = tmp_path / 'settings.ini'
    return SettingsStore(QSettings(str(ini_path), QSettings.Format.IniFormat))


@pytest.fixture
def window(qtbot, settings_store: SettingsStore) -> MainWindow:
    """Construct the main window and ensure its worker thread is stopped on teardown."""
    instance = MainWindow(settings_store=settings_store)
    qtbot.addWidget(instance)
    try:
        yield instance
    finally:
        instance.close()


def test_starts_in_empty_state(window: MainWindow) -> None:
    # The panel stack is disabled and reload is unavailable until a project opens (R3).
    assert window._tabs.isEnabled() is False
    assert window._reload_action.isEnabled() is False
    assert [window._tabs.tabText(i) for i in range(window._tabs.count())] == list(PANEL_TAB_NAMES)


def test_open_enables_tabs_and_populates_branches(qtbot, window: MainWindow) -> None:
    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.open_path(str(EXAMPLE_PROJECT))
    assert blocker.args == [True]

    # The window's own ``opened`` slot may run after ``waitSignal`` returns, so
    # wait for its visible effect rather than racing the slot delivery order.
    qtbot.waitUntil(lambda: window._tabs.isEnabled(), timeout=15000)

    # The panel tabs are enabled and reload becomes available after a successful open (R3, R2a).
    assert window._tabs.isEnabled() is True
    assert window._reload_action.isEnabled() is True

    # The fixture is inside a git working tree, so the branch combo is populated and shown (R4).
    expected = git_branches.list_branches(str(EXAMPLE_PROJECT))
    assert expected  # guard: the fixture really is a repo with at least one branch.
    combo_items = [window._branch_combo.itemText(i) for i in range(window._branch_combo.count())]
    # Every local branch is offered; the submodule fixture may be in a detached
    # HEAD state (it is pinned to a specific commit), in which case the combo
    # also carries a leading '(HEAD detached ...)' label and is disabled (R4, H-2).
    assert set(expected).issubset(set(combo_items))
    detached = any(item.startswith('(HEAD detached') for item in combo_items)
    assert window._branch_combo.isEnabled() is (not detached)
    assert window._branch_combo.isVisibleTo(window) is True


def test_successful_open_pushes_path_into_mru(qtbot, window: MainWindow, settings_store: SettingsStore) -> None:
    with qtbot.waitSignal(window.worker.opened, timeout=15000):
        window.open_path(str(EXAMPLE_PROJECT))

    # The MRU is written by the window's ``opened`` slot, which may run after
    # ``waitSignal`` returns; wait for the write to land.
    qtbot.waitUntil(lambda: bool(settings_store.recent_projects()), timeout=15000)

    recents = settings_store.recent_projects()
    assert recents
    assert recents[0] == str(EXAMPLE_PROJECT)

    # The Recent menu is rebuilt from the store and lists the opened project (P4).
    recent_actions = [action.text() for action in window._recent_menu.actions()]
    assert str(EXAMPLE_PROJECT) in recent_actions


def test_open_failure_stays_in_empty_state(qtbot, window: MainWindow, tmp_path: Path, monkeypatch) -> None:
    # Suppress the modal error dialog so the headless run does not block (R3).
    from PySide6.QtWidgets import QMessageBox

    monkeypatch.setattr(QMessageBox, 'critical', staticmethod(lambda *a, **k: QMessageBox.StandardButton.Ok))

    missing = tmp_path / 'does-not-exist'
    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.open_path(str(missing))
    assert blocker.args == [False]

    # The app returns to the empty state rather than crashing (R3). The state is
    # reset by the window's ``opened`` slot, so give it a chance to run.
    qtbot.wait(50)
    assert window._tabs.isEnabled() is False
    assert window._reload_action.isEnabled() is False


def test_branch_bar_hidden_for_non_repo(qtbot, window: MainWindow, tmp_path: Path) -> None:
    # Copy the project out of the git working tree so it is not a repository.
    import shutil

    destination = tmp_path / 'obsidian-driver'
    shutil.copytree(EXAMPLE_PROJECT, destination)

    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.open_path(str(destination))
    assert blocker.args == [True]

    # A non-repository hides the branch control rather than reporting an error (R4).
    qtbot.waitUntil(lambda: window._tabs.isEnabled(), timeout=15000)
    assert git_branches.list_branches(str(destination)) == []
    assert window._branch_combo.isVisibleTo(window) is False


def test_open_populates_trace_atypes(qtbot, window: MainWindow) -> None:
    # Regression for review finding H-1: opening a project must populate the
    # traceability child/parent selectors via the worker's atypesReady signal.
    with qtbot.waitSignal(window.worker.atypesReady, timeout=15000) as blocker:
        window.open_path(str(EXAMPLE_PROJECT))
    assert blocker.args  # a non-empty atypes payload was emitted.

    qtbot.waitUntil(lambda: bool(window._trace_panel.child_atypes()), timeout=15000)
    assert window._trace_panel.child_atypes() == list(blocker.args[0])


def test_detached_head_labelled_and_combo_disabled(qtbot, window: MainWindow, tmp_path: Path) -> None:
    # Regression for review finding H-2: a detached HEAD must show the
    # '(HEAD detached at <sha>)' label and disable branch switching (R4).
    import shutil

    from git import Repo

    destination = tmp_path / 'detached-project'
    shutil.copytree(EXAMPLE_PROJECT, destination)
    repo = Repo.init(destination)
    repo.index.add(['*'])
    repo.index.commit('initial')
    first = repo.head.commit
    (destination / 'second.txt').write_text('second', encoding='utf-8')
    repo.index.add(['second.txt'])
    repo.index.commit('second')
    repo.git.checkout(first.hexsha)  # detach HEAD at the first commit.

    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.open_path(str(destination))
    assert blocker.args == [True]

    qtbot.waitUntil(lambda: window._branch_combo.isVisibleTo(window), timeout=15000)
    assert window._branch_combo.currentText().startswith('(HEAD detached')
    assert window._branch_combo.isEnabled() is False



# --- New Project flow (R3, R4, R5, R5b, R6, R7a) ---


def test_new_project_empty_folder_scaffolds_opens_and_records_mru(
    qtbot, window: MainWindow, settings_store: SettingsStore, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog

    target = tmp_path / 'demo'
    target.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(target)))

    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.new_project_dialog()
    assert blocker.args == [True]

    # The scaffold was written and the project opened through the normal flow.
    assert (target / '.syntagmax' / 'config.toml').is_file()
    assert (target / 'REQ').is_dir()
    qtbot.waitUntil(lambda: window._tabs.isEnabled(), timeout=15000)

    # The MRU records the project ROOT (folder), not the internal config path (E9).
    qtbot.waitUntil(lambda: bool(settings_store.recent_projects()), timeout=15000)
    recents = settings_store.recent_projects()
    assert recents[0] == str(target)
    assert '.syntagmax' not in Path(recents[0]).name


def test_new_project_existing_project_offers_open(
    qtbot, window: MainWindow, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    from syntagmax_desktop import core_facade

    target = tmp_path / 'existing'
    core_facade.create(target)  # pre-existing project.

    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(target)))
    asked = {}

    def fake_question(*args, **kwargs):
        asked['called'] = True
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, 'question', staticmethod(fake_question))

    with qtbot.waitSignal(window.worker.opened, timeout=15000) as blocker:
        window.new_project_dialog()
    # The refusal offered Open, and the existing project opened rather than being re-scaffolded.
    assert asked.get('called') is True
    assert blocker.args == [True]


def test_new_project_flat_config_also_detected(
    qtbot, window: MainWindow, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / 'flat'
    target.mkdir()
    (target / 'config.toml').write_text('# flat\n', encoding='utf-8')

    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(target)))
    questioned = {'n': 0}

    def fake_question(*args, **kwargs):
        questioned['n'] += 1
        return QMessageBox.StandardButton.No  # decline opening.

    monkeypatch.setattr(QMessageBox, 'question', staticmethod(fake_question))

    window.new_project_dialog()
    qtbot.wait(50)
    # A flat config.toml is recognised as an existing project (dual-config, P7),
    # so the "open instead?" question was shown and no .syntagmax/ was created.
    assert questioned['n'] == 1
    assert not (target / '.syntagmax').exists()


def test_new_project_non_empty_warns_and_defaults_to_no(
    qtbot, window: MainWindow, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / 'populated'
    target.mkdir()
    (target / 'notes.txt').write_text('hello', encoding='utf-8')

    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(target)))

    captured = {}

    def fake_warning(parent, title, text, buttons, default):
        captured['default'] = default
        return QMessageBox.StandardButton.No  # user declines.

    monkeypatch.setattr(QMessageBox, 'warning', staticmethod(fake_warning))

    window.new_project_dialog()
    qtbot.wait(50)
    # The warning used No as the safe default (P6) and, declined, no project was written.
    assert captured.get('default') == QMessageBox.StandardButton.No
    assert not (target / '.syntagmax').exists()


def test_new_project_handles_inaccessible_folder(
    qtbot, window: MainWindow, tmp_path: Path, monkeypatch
) -> None:
    from PySide6.QtWidgets import QFileDialog, QMessageBox

    target = tmp_path / 'denied'
    target.mkdir()
    monkeypatch.setattr(QFileDialog, 'getExistingDirectory', staticmethod(lambda *a, **k: str(target)))

    def boom(self):
        raise PermissionError('access denied')

    monkeypatch.setattr(Path, 'iterdir', boom)
    criticals = {'n': 0}
    monkeypatch.setattr(
        QMessageBox, 'critical',
        staticmethod(lambda *a, **k: criticals.__setitem__('n', criticals['n'] + 1)),
    )

    window.new_project_dialog()
    qtbot.wait(50)
    # The OSError was caught and surfaced as a dialog rather than crashing (E3).
    assert criticals['n'] == 1


def test_reveal_action_opens_project_root(qtbot, window: MainWindow, monkeypatch) -> None:
    from PySide6.QtGui import QDesktopServices

    opened = {}
    monkeypatch.setattr(QDesktopServices, 'openUrl', staticmethod(lambda url: opened.setdefault('url', url)))

    with qtbot.waitSignal(window.worker.opened, timeout=15000):
        window.open_path(str(EXAMPLE_PROJECT))
    qtbot.waitUntil(lambda: window._reveal_action.isEnabled(), timeout=15000)

    window.reveal_project_folder()
    assert 'url' in opened
    assert opened['url'].toLocalFile().replace('\\', '/').endswith('obsidian-driver')



def test_busy_disables_new_open_reload_and_recent(qtbot, window: MainWindow) -> None:
    # L-1: the busy handler must lock out New/Open/Reload (and Recent) so a
    # second request cannot be queued behind an in-flight run (R7a, E4, M-1).
    window._on_busy_changed(True)
    assert window._new_action.isEnabled() is False
    assert window._open_action.isEnabled() is False
    assert window._reload_action.isEnabled() is False
    assert window._recent_menu.isEnabled() is False

    window._on_busy_changed(False)
    # When idle, New/Open re-enable unconditionally; Reload stays gated on an open project.
    assert window._new_action.isEnabled() is True
    assert window._open_action.isEnabled() is True
