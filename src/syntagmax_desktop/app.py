"""Application entry point for Syntagmax Desktop."""

from __future__ import annotations

import sys
from importlib.resources import as_file, files

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from syntagmax_desktop.logging_setup import install_excepthook
from syntagmax_desktop.views.main_window import MainWindow


def _set_windows_app_id() -> None:
    """Set an explicit AppUserModelID so Windows shows our taskbar icon (not Python's).

    Without this, a Python-hosted process is grouped under the interpreter's
    identity and the taskbar shows the generic Python icon. This is a no-op off
    Windows and never fatal.
    """
    if sys.platform != 'win32':
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('city.flyver.syntagmax.desktop')
    except Exception:  # pragma: no cover - cosmetic only; must never block launch
        pass


def app_icon() -> QIcon:
    """Return the application :class:`QIcon`, loaded from the bundled resource."""
    resource = files('syntagmax_desktop.resources') / 'app_icon.ico'
    with as_file(resource) as path:
        return QIcon(str(path))


def main() -> int:
    """Launch the desktop application and run the Qt event loop."""
    install_excepthook()
    _set_windows_app_id()
    app = QApplication.instance() or QApplication(sys.argv)
    icon = app_icon()
    app.setWindowIcon(icon)
    window = MainWindow()
    window.setWindowIcon(icon)
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
