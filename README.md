# Syntagmax Desktop

Syntagmax Desktop is a native, read-only reviewer for Syntagmax projects. The base Syntagmax tool is a command-line application; this desktop companion lets a reviewer open a project and read its analysis, traceability, and artifacts through a Qt window, without ever touching a terminal. It is built with PySide6, stays entirely within the Python ecosystem (no Electron, no bundled Node runtime), and consumes the Syntagmax core solely through the public `syntagmax.api` embedding surface.

## Quickstart

The project uses [uv](https://docs.astral.sh/uv/) for dependency management, and the Syntagmax core is included as a Git submodule, so clone with submodules (or run `git submodule update --init --recursive` after cloning).

Install the dependencies, including the editable core submodule:

```
uv sync
```

Launch the reviewer window:

```
uv run syntagmax-desktop
```

Build the standalone Windows executable and the per-user MSI installer (cx_Freeze):

```
uv run python setup_freeze.py build
uv run python setup_freeze.py bdist_msi
```

The `build` command writes `build/exe.win-amd64-<pyver>/syntagmax-desktop.exe` with its bundled Qt plugins, and `bdist_msi` writes the installer under `dist/`. See `docs/reference/packaging.md` for the full packaging reference.

## Feature overview

The reviewer workflow is open, then analysis, traceability, and browse:

- **Open** a project by picking its `.syntagmax/config.toml` (or a folder containing it) through a native dialog, reload the current project with `F5`, switch Git branches from the branch bar, and re-open past projects from the Recent Projects menu.
- **Analysis** runs `Session.analyse()` and renders a metrics strip plus a diagnostics list grouped by location, with severity filter toggles (Error, Warning, and Info) so blocking issues are not buried among informational notices.
- **Traceability** renders the matrix for a chosen child type, parent type, direction (forward or reverse), and an independent flat toggle, and exports the result to CSV or TSV on disk.
- **Browser** is a read-only artifact browser grouped by type, with content search, rendered Markdown bodies, and clickable parent and child links for following traceability directly.

Every core call runs off the UI thread through a single serialising worker, so the window stays responsive and shows a busy indicator during long operations. For the full panel-by-panel reference, see `docs/reference/desktop-app.md`.

## Read-only scope

Syntagmax Desktop is a reviewer, not an editor. There are no create, edit, or delete controls anywhere in v1 — the application only reads a project and renders it. Reviewer sessions open with `allow_dirty_worktree=True` so ordinary working copies with untracked notes or local edits open cleanly, and Git branch checkout is non-destructive and refused when the working tree has uncommitted changes. Authoring remains the responsibility of the Syntagmax command-line tool.

## Licensing

Syntagmax Desktop is distributed under the MIT licence, matching the Syntagmax core.

The application depends on PySide6 (Qt for Python), which is offered under the LGPL. PySide6 is used here through ordinary dynamic linking — the application imports the published PySide6 and Qt shared libraries at runtime and does not modify, statically link, or redistribute a modified Qt. Under the LGPL, dynamic linking against the unmodified library keeps the surrounding application free to carry its own licence, so PySide6's LGPL terms are compatible with the core's MIT licence (R15). The frozen Windows build bundles the unmodified PySide6 and Qt libraries alongside the executable, which is the dynamic-linking case the LGPL permits.
