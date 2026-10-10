# Packaging — Windows build and MSI

This page documents how the Syntagmax Desktop reviewer is frozen into a standalone Windows executable and packaged as a per-user MSI installer. For the reviewer workflow and panels, see `docs/reference/desktop-app.md`.

## Build command

The frozen build and the MSI are produced with cx_Freeze. The static freeze metadata lives in `pyproject.toml` under `[tool.cxfreeze]`, and `setup_freeze.py` augments it with the dynamically resolved Qt plugins and the MSI shortcut table.

Build the standalone executable tree:

```
uv run python setup_freeze.py build
```

This writes `build/exe.win-amd64-<pyver>/syntagmax-desktop.exe` together with its dependencies and the bundled Qt plugins under `build/exe.win-amd64-<pyver>/lib/PySide6/plugins/`.

Build the per-user MSI installer:

```
uv run python setup_freeze.py bdist_msi
```

This writes the `.msi` under `dist/`.

The `setup_freeze.py` entry point is required because two parts of the configuration cannot be expressed as fixed values in `pyproject.toml`: the Qt plugin source paths (which vary per machine and are resolved from the installed PySide6 at build time) and the MSI shortcut table (which has no TOML representation). When driving the build through the bare `cxfreeze` command line instead, the pyproject `[tool.cxfreeze]` block alone is read and those two augmentations are omitted, so prefer the `setup_freeze.py` invocation above.

## Executable configuration

The executable is built from `src/syntagmax_desktop/app.py` with `base = "gui"`, so a double-click launch opens no console window (R1), and the target is named `syntagmax-desktop`. The `app.py` entry point installs a `sys.excepthook` crash logger before the Qt event loop starts, so an unhandled exception in the frozen build is written to `%LOCALAPPDATA%/Syntagmax/logs/crash.log` (R9a).

## Bundled Qt plugins

PySide6 loads its platform integration, styling, and image-format support from plugin DLLs that are not discovered by cx_Freeze's module scan, so they are bundled explicitly (E4 operational). Without the Windows platform plugin the frozen binary aborts immediately on a clean machine with a `qt.qpa.plugin` error. `setup_freeze.py` resolves and copies the following plugin groups into `lib/PySide6/plugins/`:

- `platforms` — includes `qwindows.dll`, the mandatory Windows platform integration plugin.
- `styles` — the native Windows widget style, so the frozen build does not fall back to the unstyled look.
- `imageformats` — includes `qsvg.dll` for scalable SVG icons and assets.
- `iconengines` — the companion SVG icon engine.

## MSI configuration

The MSI is produced by `bdist_msi` with the product name `Syntagmax Desktop` and a fixed `upgrade_code` of `{CA7AD7F2-157B-4AD6-B2B8-59A3C2F7EE13}`. This GUID is newly minted for the desktop reviewer and is deliberately distinct from the Syntagmax core's `{06253457-3B2E-4FA7-9097-4712F2C507C3}`, so the two products never collide in the Windows Installer upgrade table. The MSI is scoped per user (`all_users = false`) to keep installation out of the forced-UAC path (E4), and it registers both a Start-Menu entry and a desktop shortcut.

## Manual verification on a clean Windows environment

The following checks require a clean Windows machine and are performed manually:

1. Install the MSI, confirm it does not prompt for administrator elevation (per-user scope), and confirm the Start-Menu and desktop shortcuts appear.
2. Launch `syntagmax-desktop.exe` and open a project; a successful open proves the Qt plugins are bundled correctly.
3. Force an exception at start-up and confirm `%LOCALAPPDATA%/Syntagmax/logs/crash.log` is written (R9a).
