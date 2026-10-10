"""Crash telemetry for Syntagmax Desktop (spec R9a / critique E4).

The frozen Win32 GUI build runs with ``base = "gui"``, which detaches ``stdout``
and ``stderr``. Without a top-level excepthook an unhandled exception would
terminate the application silently, leaving no diagnostic trace. This module
installs an excepthook that appends uncaught exceptions to a per-user log file.
"""

from __future__ import annotations

import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


def log_dir() -> Path:
    """Return the per-user application log directory.

    On Windows this is ``%LOCALAPPDATA%/Syntagmax/logs``; elsewhere it falls
    back to ``~/.local/state/syntagmax/logs`` (or ``$XDG_STATE_HOME``).
    """
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA') or str(Path.home() / 'AppData' / 'Local')
        return Path(base) / 'Syntagmax' / 'logs'
    state = os.environ.get('XDG_STATE_HOME') or str(Path.home() / '.local' / 'state')
    return Path(state) / 'syntagmax' / 'logs'


def crash_log_path() -> Path:
    """Return the full path to ``crash.log``."""
    return log_dir() / 'crash.log'


def write_crash(exc_type: type[BaseException], exc: BaseException, tb) -> Path:
    """Append a formatted traceback for ``exc`` to the crash log and return its path."""
    path = crash_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat()
    text = ''.join(traceback.format_exception(exc_type, exc, tb))
    with path.open('a', encoding='utf-8') as fh:
        fh.write(f'\n----- {stamp} -----\n')
        fh.write(text)
    return path


def install_excepthook() -> None:
    """Install a chained excepthook that records uncaught exceptions to disk."""
    previous = sys.excepthook

    def _hook(exc_type, exc, tb):
        try:
            write_crash(exc_type, exc, tb)
        except Exception:  # pragma: no cover - logging must never mask the original fault
            pass
        previous(exc_type, exc, tb)

    sys.excepthook = _hook
