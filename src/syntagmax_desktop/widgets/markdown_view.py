# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: Read-only Markdown viewer wrapping QTextBrowser for artifact bodies.

"""A read-only Markdown viewer for artifact bodies (spec R8, E8).

:class:`MarkdownView` wraps :class:`~PySide6.QtWidgets.QTextBrowser` and renders
an artifact's Markdown body via :meth:`QTextBrowser.setMarkdown`. The document's
base URL is set to the project root so relative image references in a body — for
example, ``![diagram](assets/overview.png)`` — resolve against the project on
disk rather than failing to load (E8).

Known v1 constraint: Qt's Markdown engine understands the CommonMark subset
only. GitHub-flavoured Markdown tables and Obsidian-style wikilinks
(``[[Note]]``) are not rendered, so such source appears verbatim rather than
formatted. This is an accepted limitation for v1 of the reviewer, which targets
plain CommonMark bodies.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtWidgets import QTextBrowser, QWidget


class MarkdownView(QTextBrowser):
    """A read-only Markdown renderer with a project-rooted base URL.

    External links are opened by the host browser rather than navigated inside
    the widget, so a reviewer never loses the rendered body by clicking a link.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName('markdownView')
        self.setOpenExternalLinks(True)
        self._project_root: Path | None = None

    def set_project_root(self, project_root: str | Path | None) -> None:
        """Set the base URL used to resolve a body's relative resources (E8).

        ``project_root`` is the directory against which relative image and
        resource references in a Markdown body are resolved. Pass ``None`` to
        clear the base URL — for example, when no project is open.
        """
        if project_root is None:
            self._project_root = None
            self.document().setBaseUrl(QUrl())
            return

        root = Path(project_root)
        self._project_root = root
        # A trailing separator makes the URL a directory, so relative references
        # resolve as children of the project root rather than siblings of it.
        base = QUrl.fromLocalFile(str(root) + '/')
        self.document().setBaseUrl(base)

    def set_body(self, body: str | None) -> None:
        """Render ``body`` as Markdown, clearing the view for an empty body."""
        self.setMarkdown(body or '')
