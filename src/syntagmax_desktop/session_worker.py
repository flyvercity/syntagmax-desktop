# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: Threaded session worker that runs every core_facade call off the UI thread.

"""Threaded owner of the single :class:`~syntagmax.api.Session` (spec R9, E5, E3).

Every core call a reviewer triggers — open, analyse, trace, export, query, and
search — runs on a dedicated worker thread rather than the UI thread, so a long
analysis never freezes the window. The worker is a :class:`QObject` moved onto a
:class:`QThread`; only the worker thread ever touches the :class:`Session`, which
keeps the single, non-thread-affine handle free of cross-thread races.

Each slot is wrapped by a busy guard: ``busyChanged(True)`` is emitted on entry
and ``busyChanged(False)`` on exit, so the UI can mask new requests whilst a run
is in flight rather than queue orphaned work (E5). Every exception —
``FatalError``, ``RMSException``, or any other ``Exception`` — is caught and
turned into a readable, secret-redacted ``failed`` message, so a core failure
surfaces as a clean diagnostic instead of propagating onto the event loop.
"""

from __future__ import annotations

import os
import re
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from PySide6.QtCore import QObject, Signal, Slot

from syntagmax.api import Session, TraceResult
from syntagmax.errors import FatalError, RMSException

from syntagmax_desktop import core_facade

#: Patterns whose matched span is replaced with a redaction marker before an
#: error message is surfaced, so a secret embedded in a path, URL, or token-like
#: string is never echoed back into the UI.
_REDACTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    # ``scheme://user:secret@host`` — redact the user-info credential segment.
    re.compile(r'(?<=://)[^/@\s]+:[^/@\s]+(?=@)'),
    # ``key=value``/``token: value`` pairs for secret-like keys.
    re.compile(r'(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key|authorization|auth)\b\s*[=:]\s*\S+'),
    # Long bearer-style opaque tokens (20+ URL-safe characters).
    re.compile(r'\b[A-Za-z0-9._\-]{32,}\b'),
)

_REDACTION_MARKER = '[REDACTED]'


def _redact(message: str) -> str:
    """Return ``message`` with secret-like substrings masked (E7, R9).

    Credentials embedded in a connection URL, ``key=value`` secret pairs, and
    long opaque tokens are replaced with a marker so a failure message is safe
    to show to a reviewer. The home directory is collapsed to ``~`` so a user
    name on an absolute path is not leaked either.
    """
    redacted = message
    for pattern in _REDACTION_PATTERNS:
        if pattern.pattern.startswith('(?i)\\b(password'):
            redacted = pattern.sub(lambda match: f'{match.group(1)}={_REDACTION_MARKER}', redacted)
        else:
            redacted = pattern.sub(_REDACTION_MARKER, redacted)

    home = os.path.expanduser('~')
    if home and home != '~':
        redacted = redacted.replace(home, '~')
    return redacted


class SessionWorker(QObject):
    """A :class:`QObject` that owns the single session and runs calls off the UI thread.

    Move an instance onto a :class:`QThread` and invoke the ``run*`` slots via a
    queued connection; the owning session is created and used solely on that
    worker thread. Results are delivered through the typed ``*Ready`` signals,
    failures through ``failed``, and the ``busyChanged`` signal brackets every
    run so the UI can block concurrent requests (E5).
    """

    opened = Signal(bool)
    analysisReady = Signal(object)
    traceReady = Signal(object)
    queryReady = Signal(object)
    searchReady = Signal(object)
    failed = Signal(str)
    busyChanged = Signal(bool)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._session: Session | None = None

    @property
    def session(self) -> Session | None:
        """Return the owned session, or ``None`` before a project is opened.

        Intended for the worker thread only; the UI thread must never touch the
        session directly and should instead drive the ``run*`` slots.
        """
        return self._session

    @contextmanager
    def _busy(self) -> Iterator[None]:
        """Bracket a run with ``busyChanged(True)`` then ``busyChanged(False)`` (E5)."""
        self.busyChanged.emit(True)
        try:
            yield
        finally:
            self.busyChanged.emit(False)

    def _fail(self, exc: Exception) -> None:
        """Emit a readable, redacted ``failed`` message for ``exc`` (R9, E7)."""
        if isinstance(exc, FatalError):
            detail = '\n'.join(exc.errors)
        else:
            detail = str(exc) or exc.__class__.__name__
        self.failed.emit(_redact(detail))

    @Slot(str)
    def openProject(self, config_path: str) -> None:
        """Open a project and emit ``opened`` with the outcome (R2, R9).

        A successful open replaces any previously owned session and emits
        ``opened(True)``; a failure clears the session and emits both
        ``opened(False)`` and a redacted ``failed`` message, so the UI can
        reset without being left in a half-opened state.
        """
        with self._busy():
            try:
                self._session = core_facade.open(Path(config_path))
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._session = None
                self._fail(exc)
                self.opened.emit(False)
            else:
                self.opened.emit(True)

    @Slot()
    def runAnalyse(self) -> None:
        """Run analysis and emit ``analysisReady`` with the structured result (R5)."""
        with self._busy():
            try:
                result = core_facade.analyse(self._require_session())
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._fail(exc)
            else:
                self.analysisReady.emit(result)

    @Slot(str, str, str, bool)
    def runTrace(self, child: str, parent: str, direction: str, flat: bool) -> None:
        """Build a trace matrix and emit ``traceReady`` with the result (R6, E2)."""
        with self._busy():
            try:
                result = core_facade.trace(
                    self._require_session(),
                    child,
                    parent,
                    direction=direction,
                    flat=flat,
                )
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._fail(exc)
            else:
                self.traceReady.emit(result)

    @Slot(object, str, str)
    def exportTrace(self, result: TraceResult, path: str, delimiter: str) -> None:
        """Render and write a trace result to ``path`` (R7).

        No result signal is emitted on success — the write is the effect — but a
        failure (for example, a read-only destination) is surfaced via ``failed``.
        """
        with self._busy():
            try:
                core_facade.export_trace(result, Path(path), delimiter)
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._fail(exc)

    @Slot(str)
    def runQuery(self, atype: str) -> None:
        """Query artifacts, optionally by atype, and emit ``queryReady`` (R8).

        An empty ``atype`` string is treated as "no filter" so a cleared UI
        control queries the whole graph.
        """
        with self._busy():
            try:
                result = core_facade.query(self._require_session(), atype=atype or None)
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._fail(exc)
            else:
                self.queryReady.emit(result)

    @Slot(str)
    def runSearch(self, q: str) -> None:
        """Search artifacts and emit ``searchReady`` with the matches (R8)."""
        with self._busy():
            try:
                result = core_facade.search(self._require_session(), q)
            except Exception as exc:  # noqa: BLE001 - the worker surfaces every failure as a redacted signal (R9)
                self._fail(exc)
            else:
                self.searchReady.emit(result)

    def _require_session(self) -> Session:
        """Return the owned session or raise a readable error when none is open."""
        if self._session is None:
            raise RMSException('No project is open; open a project before running this action.')
        return self._session
