# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project uses [Calendar Versioning](https://calver.org/) with the scheme `YYYY.M.D`, matching the Syntagmax core.

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
