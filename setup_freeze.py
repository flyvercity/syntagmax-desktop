"""cx_Freeze build script for the Syntagmax Desktop Windows package.

The static freeze metadata (executable, packages, excludes, and the bulk of
the ``bdist_msi`` options) lives in ``pyproject.toml`` under ``[tool.cxfreeze]``
and cx_Freeze merges it automatically. This script exists for the two parts
that cannot be expressed as fixed values in TOML:

1. **The Qt plugins** (``platforms/qwindows.dll``, ``styles``, and the SVG
   image-format plugin). Without the Windows platform plugin the frozen binary
   aborts immediately on a clean machine with a ``qt.qpa.plugin`` error, so the
   plugins must be bundled explicitly (E4 operational). Their source path is
   wherever PySide6 happens to be installed, which differs per machine and CI
   runner, so it is resolved at build time rather than hard-coded.

2. **The MSI shortcut table**, which drives the Start-Menu and desktop
   shortcuts. ``bdist_msi`` reads these from an in-memory ``data`` table that
   has no TOML representation.

Build command (documented in ``docs/reference/packaging.md``)::

    uv run cxfreeze build

The ``[tool.cxfreeze]`` options from ``pyproject.toml`` are applied on top of
whatever this script passes, so the executable, ``packages``, ``excludes``,
``product_name``, ``upgrade_code``, and ``all_users`` need not be repeated here.
"""

from __future__ import annotations

import os
from pathlib import Path

from cx_Freeze import Executable, setup

# ---------------------------------------------------------------------------
# Qt plugins — resolved dynamically from the installed PySide6.
# ---------------------------------------------------------------------------


def _qt_plugin_include_files() -> list[tuple[str, str]]:
    """Return ``(source, destination)`` pairs for the Qt plugins we must ship.

    cx_Freeze lays the application tree out under ``lib/`` in the frozen build,
    and PySide6 looks for its plugins beside the package at
    ``lib/PySide6/plugins/<group>``. We mirror that layout so the Windows
    platform plugin, the native styles, and the SVG image-format plugin are
    discoverable at runtime.
    """
    import PySide6

    plugins_root = Path(PySide6.__file__).resolve().parent / 'plugins'
    destination_root = 'lib/PySide6/plugins'

    include_files: list[tuple[str, str]] = []

    # The Windows platform integration plugin is mandatory — the GUI will not
    # start without it. Bundle the whole `platforms` group so companion plugins
    # (for example the offscreen plugin used by the test suite) travel with it.
    platforms_dir = plugins_root / 'platforms'
    if platforms_dir.is_dir():
        include_files.append((os.fspath(platforms_dir), f'{destination_root}/platforms'))

    # Native widget styling, so the frozen build does not fall back to the
    # unstyled Fusion look on Windows.
    styles_dir = plugins_root / 'styles'
    if styles_dir.is_dir():
        include_files.append((os.fspath(styles_dir), f'{destination_root}/styles'))

    # SVG support, required for scalable icons and any SVG assets rendered in
    # the reviewer views.
    imageformats_dir = plugins_root / 'imageformats'
    if imageformats_dir.is_dir():
        include_files.append((os.fspath(imageformats_dir), f'{destination_root}/imageformats'))
    iconengines_dir = plugins_root / 'iconengines'
    if iconengines_dir.is_dir():
        include_files.append((os.fspath(iconengines_dir), f'{destination_root}/iconengines'))

    return include_files


# ---------------------------------------------------------------------------
# Package data files — non-Python assets the core reads at runtime.
# ---------------------------------------------------------------------------


def _package_data_include_files() -> list[tuple[str, str]]:
    """Return ``(source, destination)`` pairs for every non-Python data file.

    cx_Freeze bundles ``.py``/``.pyc`` modules but not the data files that the
    Syntagmax core loads from disk at import/run time — the Lark grammars
    (``metamodel.lark``, ``extractors/*.lark``, read via
    ``Path(__file__).parent / '*.lark'`` on import), the Jinja templates and
    other ``resources/`` assets, and the compiled gettext catalogues under
    ``resources/locales/``. Without these the frozen build aborts with a
    ``FileNotFoundError`` (e.g. ``markdown.lark``) on a clean install.

    We mirror each file into the frozen tree at ``lib/<package>/<relative path>``
    so the core's ``Path(__file__).parent`` lookups resolve. Discovery is
    generic (every file that is not ``.py``/``.pyc``), so a newly added data
    file is picked up automatically rather than needing a hand-maintained list.
    """
    include_files: list[tuple[str, str]] = []
    package_roots = {
        'syntagmax': Path('syntagmax/src/syntagmax'),
        'syntagmax_desktop': Path('src/syntagmax_desktop'),
    }
    for package, root in package_roots.items():
        if not root.is_dir():
            continue
        for path in root.rglob('*'):
            if not path.is_file():
                continue
            if path.suffix in ('.py', '.pyc'):
                continue
            relative = path.relative_to(root).as_posix()
            include_files.append((os.fspath(path), f'lib/{package}/{relative}'))
    return include_files


# ---------------------------------------------------------------------------
# MSI shortcut table — Start-Menu and desktop entries.
# ---------------------------------------------------------------------------

# Rows follow the Windows Installer `Shortcut` table schema:
# (Shortcut, Directory_, Name, Component_, Target, Arguments, Description,
#  Hotkey, Icon, IconIndex, ShowCmd, WkDir).
_shortcut_table = [
    (
        'StartMenuShortcut',  # Shortcut (primary key)
        'ProgramMenuFolder',  # Directory_ — the Start-Menu Programs folder
        'Syntagmax Desktop',  # Name shown to the user
        'TARGETDIR',  # Component_ anchoring the shortcut
        '[TARGETDIR]syntagmax-desktop.exe',  # Target
        None,  # Arguments
        'Syntagmax Desktop reviewer',  # Description
        None,  # Hotkey
        None,  # Icon
        None,  # IconIndex
        None,  # ShowCmd
        'TARGETDIR',  # WkDir — launch from the install directory
    ),
    (
        'DesktopShortcut',
        'DesktopFolder',  # the user's desktop
        'Syntagmax Desktop',
        'TARGETDIR',
        '[TARGETDIR]syntagmax-desktop.exe',
        None,
        'Syntagmax Desktop reviewer',
        None,
        None,
        None,
        None,
        'TARGETDIR',
    ),
]


# ---------------------------------------------------------------------------
# Build invocation.
# ---------------------------------------------------------------------------

_ICON_PATH = Path('src/syntagmax_desktop/resources/app_icon.ico')

# `base = "gui"` suppresses the console window (R1); the remaining executable
# metadata (script, target_name) and all build_exe/bdist_msi options are
# supplied by [tool.cxfreeze] in pyproject.toml and merged in automatically.
# `icon` sets the .exe icon (and, via the shortcut Icon column, the MSI entries).
_executables = [
    Executable(
        script='src/syntagmax_desktop/app.py',
        base='gui',
        target_name='syntagmax-desktop',
        icon=os.fspath(_ICON_PATH),
    ),
]

_options = {
    'build_exe': {
        # Bundle the Qt plugins and every non-Python package data file (core
        # Lark grammars, Jinja templates, gettext catalogues, and the desktop
        # icon resources) so both the core's on-disk lookups and the runtime
        # QApplication.setWindowIcon resolve inside the frozen tree.
        'include_files': _qt_plugin_include_files() + _package_data_include_files(),
    },
    'bdist_msi': {
        'data': {'Shortcut': _shortcut_table},
    },
}


if __name__ == '__main__':
    setup(
        name='syntagmax-desktop',
        executables=_executables,
        options=_options,
    )
