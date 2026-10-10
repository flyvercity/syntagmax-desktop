# SPDX-License-Identifier: MIT

# Author: Syntagmax Desktop
# Description: Thin, UI-agnostic wrapper over ``syntagmax.api``.

"""UI-agnostic facade over the Syntagmax embedding API.

This module is the single seam between the Syntagmax Desktop application and
``syntagmax.api``. Every core call a reviewer triggers — open, analyse, trace,
export, atype discovery, query, and search — flows through here, so the rest
of the application never touches core internals, and ``FatalError`` and
``RMSException`` propagate unchanged for the worker to surface (R1.8, E7).
"""

from pathlib import Path

from syntagmax.api import (
    AnalysisResult,
    ArtifactView,
    Options,
    Session,
    TraceResult,
    open_project,
    render_trace,
)


def open(config_path: str | Path) -> Session:
    """Open a project and return a :class:`Session` (R2, P1, X2).

    ``allow_dirty_worktree=True`` is the default so a reviewer can open an
    ordinary working copy with untracked, or edited, files. A picked folder is
    resolved to ``<folder>/.syntagmax/config.toml``, then ``<folder>/config.toml``;
    an explicit file path is used as-is.
    """
    resolved = Path(config_path)
    if resolved.is_dir():
        candidates = (resolved / '.syntagmax' / 'config.toml', resolved / 'config.toml')
        for candidate in candidates:
            if candidate.is_file():
                resolved = candidate
                break
        else:
            raise FileNotFoundError(f'No config.toml found under {config_path!r} (.syntagmax/config.toml or config.toml)')

    return open_project(resolved, options=Options(allow_dirty_worktree=True))


def analyse(session: Session) -> AnalysisResult:
    """Run the analysis path and return the structured result (R5)."""
    return session.analyse()


def trace(
    session: Session,
    child: str,
    parent: str,
    *,
    direction: str = 'forward',
    flat: bool = False,
) -> TraceResult:
    """Build a traceability matrix (R6).

    ``direction`` (``'forward'`` or ``'reverse'``) and ``flat`` are orthogonal
    (E2, X3): the direction controls the lead-and-linked column ordering, whilst
    ``flat`` controls whether the matrix is flattened, and either may be set
    independently of the other.
    """
    return session.trace(child, parent, direction=direction, flat=flat)


def export_trace(result: TraceResult, path: str | Path, delimiter: str) -> None:
    """Render a trace result and write it to ``path`` (R7, E7).

    CSV is written as ``utf-8-sig`` so the leading byte-order mark lets Excel
    detect UTF-8 correctly; TSV is written as plain ``utf-8``. ``PermissionError``
    and ``OSError`` propagate for the worker to surface.
    """
    rendered = render_trace(result, delimiter=delimiter)
    encoding = 'utf-8-sig' if delimiter == ',' else 'utf-8'
    with Path(path).open('w', encoding=encoding, newline='') as handle:
        handle.write(rendered)


def atypes(session: Session) -> list[str]:
    """Return the sorted artifact-type names for a session (R7 encapsulation).

    The private ``session._config.metamodel['artifacts']`` access — a dict keyed
    by type name — is encapsulated here so the UI never touches core internals.
    When the project has no static metamodel, this falls back to the distinct
    atypes present in the artifact graph via :meth:`Session.query`.
    """
    metamodel = getattr(session._config, 'metamodel', None)
    if metamodel:
        return sorted(metamodel['artifacts'].keys())
    return sorted({view.atype for view in session.query()})


def query(session: Session, *, atype: str | None = None) -> list[ArtifactView]:
    """Passthrough to :meth:`Session.query` (R8).

    ``FatalError`` and ``RMSException`` propagate.
    """
    return session.query(atype=atype)


def search(session: Session, q: str) -> list[ArtifactView]:
    """Passthrough to :meth:`Session.search` (R8).

    ``FatalError`` and ``RMSException`` propagate.
    """
    return session.search(q)
