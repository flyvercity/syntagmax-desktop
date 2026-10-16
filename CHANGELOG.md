# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Calendar Versioning](https://calver.org/) with the scheme `YYYY.M.D`, matching the Syntagmax core.

## [2026.10.16] - 2026-10-16

### Added

- **New Project**: scaffold a fresh Syntagmax project from the desktop app (File → New Project…, `Ctrl+N`, or the toolbar) via the core's new `syntagmax.api.create_project`. It writes the `.syntagmax/` configuration, a starter metamodel, a `.gitignore`, and a default `REQ/` input directory, then opens the new project. A folder picker guards against overwriting an existing project (detected at either `.syntagmax/config.toml` or a flat `config.toml`) and warns before scaffolding into a non-empty folder. The scaffold runs off the UI thread and rolls back atomically if a write fails; it writes files only and never runs `git init`, commits, or pushes.
- **Reveal Project Folder**: a read-only File-menu action that opens the current project's root in the operating system file manager.
- A first-run hint in the Browser directs the reviewer to add Markdown specification files under `REQ/` when a freshly scaffolded project has no artifacts yet.

### Changed

- The New, Open, Reload, and Recent Projects controls are disabled while a background operation is in flight, so a second request cannot be queued behind an in-flight one.
- Recent Projects records the project root directory rather than the internal `.syntagmax/config.toml` path, consistent with folder-based opens.

### Fixed

- The core's `init` starter metamodel template declared `attribute id is mandatory string`, which the metamodel validator rejected, so a freshly initialised project could not be opened or analysed; corrected to `id is string` (via the `syntagmax` core).

## [2026.10.10] - 2026-10-10

### Added

- Initial release of Syntagmax Desktop: a native, read-only reviewer for Syntagmax projects built with PySide6, consuming the Syntagmax core solely through the `syntagmax.api` embedding surface.
- Reviewer workflow: open a project (by `.syntagmax/config.toml` or folder), reload with `F5`, switch Git branches from the branch bar, and re-open past projects from the Recent Projects menu.
- Analysis panel: metrics strip plus diagnostics grouped by location, with Error, Warning, and Info severity filter toggles.
- Traceability panel: matrix for a chosen child type, parent type, direction (forward or reverse), and an independent flat toggle, with CSV or TSV export.
- Read-only artifact browser grouped by type, with content search, rendered Markdown bodies, and clickable parent and child links.
- Application icon derived from the Syntagmax core logo, wired into the window, taskbar, frozen executable, and MSI shortcuts.
- Windows packaging via cx_Freeze: a per-user MSI installer and a self-contained frozen build that embeds the Syntagmax core, so the installed application never depends on a separately installed core.
- `Build Windows MSI Installer` GitHub Action: builds and releases the MSI on a CalVer tag push.
