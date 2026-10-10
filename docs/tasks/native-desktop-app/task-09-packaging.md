# [ ] Task 9 — Windows packaging (cx_Freeze)

**Spec**: `docs/specs/native-desktop-app.spec.md` (R13, R1, R9a, E4 operational)
**Depends on**: Tasks 5–8 (Wave 5).

## Objective

A frozen Windows build and MSI that launches with no console window, bundles the Qt plugins, and writes a crash log on failure.

## Files

- `pyproject.toml` (`[tool.cxfreeze]`), optionally `setup_freeze.py` if the project style needs it, `docs/reference/packaging.md` (build command, drafted here; expanded in Task 10).

## Guidance

- `[tool.cxfreeze]` reusing the core's `build_exe.packages` plus `PySide6`, `shiboken6`.
- **Explicitly bundle Qt plugins** — the Windows platform plugin (`platforms/qwindows.dll`), styles, and SVG libs via `include_files`/package data — or the frozen binary fails immediately on a clean machine (E4 operational).
- Executable: `script = "src/syntagmax_desktop/app.py"`, `base = "gui"` (no console window, R1), `target_name = "syntagmax-desktop"`.
- `bdist_msi`: `product_name`, a fixed `upgrade_code` (new GUID, distinct from the core's), Start-Menu/desktop shortcuts, and **per-user scope (`all_users=False`)** to avoid forced UAC.
- Verify the `app.py` `sys.excepthook` crash logger (R9a) is active in the frozen build.

## Test requirements

- Build succeeds: `uv run python -m cxfreeze build` produces an exe.
- Manual on a **clean Windows** environment: the exe launches and opens a project (proves Qt plugins bundled). Force an exception at startup and confirm `%LOCALAPPDATA%/Syntagmax/logs/crash.log` is written.

## Demo

```
uv run python -m cxfreeze build
# then launch build\exe.win-amd64-*/syntagmax-desktop.exe
```
