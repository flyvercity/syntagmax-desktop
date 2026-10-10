"""Application entry point for Syntagmax Desktop."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from syntagmax_desktop.logging_setup import install_excepthook
from syntagmax_desktop.views.main_window import MainWindow


def main() -> int:
    """Launch the desktop application and run the Qt event loop."""
    install_excepthook()
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())
