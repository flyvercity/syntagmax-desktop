# Seed Spec: Native Desktop App for Syntagmax

The base Syntagmax tool is a command-line application. Users who are not comfortable on the command line need a native desktop companion that lets them open a project and read its analysis and traceability without ever touching a terminal. We want to stay entirely within the Python ecosystem — no Electron, no bundled Node runtime.

This lives in its own project, `syntagmax-desktop`, with the `syntagmax` core wired in as a Git submodule. It is **completely independent** of the `syntagmax-gui` web application: it shares none of its backend, SPA, authentication, or multi-user machinery.

## Decisions

These were settled during brainstorming (see `docs/brainstorms/native-desktop-app.md`) and are fixed intent for the first version:

- **UI toolkit: PySide6 (Qt).** Chosen for its strength with dense, read-only tabular data (grouped diagnostics, traceability matrices, Markdown bodies), its portability, and because it can reuse the core's existing packaging. "Native" here means a self-contained, installable, double-click desktop window — OS-drawn widgets are a nice-to-have, not a requirement. Toga (BeeWare) is the documented fallback if a genuinely OS-native look or clean BSD licensing later becomes a hard requirement.
- **Core consumption: in-process via `syntagmax.api`.** The app imports the library and calls it directly (`open_project` → `Session`), never shelling out to the CLI and never standing up an HTTP server. This mirrors how `syntagmax-gui` consumes the core.
- **Submodule: advance to the revision `syntagmax-gui` uses.** The currently pinned core submodule predates the embedding API; it must be moved forward to the same, known-good revision `syntagmax-gui` builds against, where `syntagmax.api` is mature.
- **Scope: read-only.** Open a project, run analysis, read diagnostics and metrics, read traceability. No artifact editing, no commit, no push. The only Git capability is **basic branch selection** — list the local branches, check one out, and re-open the project.
- **Platforms: Windows first, portable later.** Package a Windows installer for v1, but choose nothing that blocks a later macOS/Linux build. The identical PySide6 code should run on the other platforms without a rewrite.
- **Packaging: reuse the core's cx_Freeze approach.** The core already ships a Windows MSI via cx_Freeze; the desktop app should follow the same proven path.

## Primary Workflow (the one v1 must nail)

Persona: a **reviewer**. The effortless path is:

1. Open a local Syntagmax project (pick its folder / `config.toml`).
2. Optionally pick a Git branch; the project re-opens on that branch.
3. Read the **analysis**: summary metrics plus diagnostics grouped by location, each showing severity, rule, category, message, and the artifact id.
4. Read the **traceability**: a dense matrix (forward / reverse / flat), with an optional export to CSV/TSV on disk.
5. Browse artifacts read-only (grouped by `atype`, searchable), viewing a selected artifact's fields and rendered Markdown body.

Remember the domain model: Syntagmax does not distinguish "requirements" from "artifacts" — both are an `Artifact` with an `atype`. A "requirements" view is just a typed/filtered view over artifacts; "traceability" and generated matrices are a different axis (generated outputs), not a different kind of object.

## Out of Scope (v1)

- Any dependency on, or integration with, `syntagmax-gui`.
- Authentication, authorization, multi-user, OIDC.
- Artifact editing and the Obsidian write seam; Git commit, push, or pull/merge requests.
- Mobile targets and cloud deployment.
- A bundled web/HTML front end or a local web server (the pywebview idea was dropped once the app became independent and read-only).

## Tasks

- Advance the `syntagmax` submodule to the `syntagmax-gui` revision and wire it as an editable `uv` source dependency; add `PySide6`.
- Stand up a minimal `QMainWindow` reviewer shell that launches via `uv run` with no terminal interaction.
- Project-open flow: a folder / `config.toml` picker calling `open_project`, with non-fatal error reporting for open/parse failures.
- Branch selection: list local branches (via `gitpython`), check out, and re-open the project.
- Analysis panel: run `Session.analyse()` off the UI thread; render a metrics strip and diagnostics grouped by location, defensive against empty or unknown shapes.
- Traceability panel: run `render_trace(...)` off the UI thread; direction selectors; dense table; optional CSV/TSV export.
- Read-only artifact browser: `artifacts()` / `query()` / `search()` grouped by `atype`, with a detail view that renders the Markdown body.
- Package a Windows MSI via cx_Freeze (reusing the core's package list as the starting point); verify the frozen build on a clean Windows environment.
- Confirm PySide6 (LGPL) licensing compatibility with the core's MIT licence and record the decision.
- Update documentation: `README.md` **and** `docs/reference/` pages covering install, launch, and the reviewer workflow.
