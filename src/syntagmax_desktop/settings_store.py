# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: QSettings-backed Most-Recently-Used project list.

"""Persistent Most-Recently-Used (MRU) project list for Syntagmax Desktop (spec P4).

The reviewer workflow benefits from one-click re-open of recently inspected
projects, so the last ``MAX_RECENT`` opened project paths are persisted through
:class:`~PySide6.QtCore.QSettings`. ``QSettings`` is used because it writes to the
platform-native location — the registry on Windows, ``~/Library/Preferences`` on
macOS, and an INI file under ``~/.config`` on Linux — without any bespoke
file-handling, which keeps the store portable (R14) and free of hand-rolled I/O.

The list is ordered most-recent-first, de-duplicated case-insensitively on
Windows via :func:`os.path.normcase`, and capped at a small bound so the menu
stays short.
"""

from __future__ import annotations

import os

from PySide6.QtCore import QSettings

#: The application and organisation identifiers used to scope the stored settings.
ORGANISATION = 'Syntagmax'
APPLICATION = 'Syntagmax Desktop'

#: The settings key under which the recent-project list is stored.
_RECENT_KEY = 'recent/projects'

#: The maximum number of recent projects retained; older entries are discarded.
MAX_RECENT = 10


class SettingsStore:
    """A thin wrapper over :class:`QSettings` for the recent-projects list.

    An explicit :class:`QSettings` instance may be injected for testing (so a
    test can scope the store to a throwaway INI file and never touch the real
    user settings); otherwise a default instance scoped to the application and
    organisation identifiers is created.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self._settings = settings or QSettings(ORGANISATION, APPLICATION)

    def recent_projects(self) -> list[str]:
        """Return the stored project paths, most-recent-first.

        A missing or malformed value yields an empty list so the caller never
        has to guard against a cold, never-written store.
        """
        stored = self._settings.value(_RECENT_KEY, [])
        if isinstance(stored, str):
            # A single stored entry can be returned by some QSettings backends as
            # a bare string rather than a one-element list.
            return [stored] if stored else []
        if stored is None:
            return []
        return [str(item) for item in stored if str(item)]

    def add_recent(self, path: str) -> list[str]:
        """Record ``path`` as the most-recently-opened project and persist the list.

        The path is moved to the front, any case-insensitive duplicate is removed
        so a re-open does not create a second entry, and the list is truncated to
        :data:`MAX_RECENT`. The updated list is returned for convenience.
        """
        normalised = os.path.normcase(os.path.abspath(path))
        kept = [existing for existing in self.recent_projects() if os.path.normcase(os.path.abspath(existing)) != normalised]
        updated = [path, *kept][:MAX_RECENT]
        self._settings.setValue(_RECENT_KEY, updated)
        self._settings.sync()
        return updated

    def clear_recent(self) -> None:
        """Remove every stored recent project."""
        self._settings.remove(_RECENT_KEY)
        self._settings.sync()
