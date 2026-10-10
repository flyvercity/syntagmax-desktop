# Syntagmax Desktop — reviewer reference

Syntagmax Desktop is a read-only reviewer for Syntagmax projects. It opens a project through the public `syntagmax.api` embedding surface and renders its analysis, traceability, and artifacts in a Qt window. This page describes the reviewer workflow and each panel in turn, and records the known Markdown-rendering limitations. For installation and packaging, see `docs/reference/packaging.md`.

## The reviewer workflow

The workflow is open, then analysis, traceability, and browse. A reviewer opens a project once; the three panels then read that single live `Session`. Every core call — open, analyse, trace, query, and search — runs off the UI thread through a single serialising worker, so the window never freezes during a long operation. A status-bar indicator reflects the worker's busy state, and because the worker serialises requests, a long analyse or trace busy-masks the window so later search or filter requests are not silently queued behind it. Failures are surfaced in a dismissible dialog and the window recovers to its previous state rather than crashing.

The application is a reviewer, not an editor: there are no create, edit, or delete controls anywhere in v1.

## Open, branch, reload, and recent projects

The main window hosts the open flow, the branch bar, reload, and the Recent Projects menu.

- **Open** drives a native file or folder dialog. The user can pick a project's `.syntagmax/config.toml` directly, or pick a folder — in which case resolution checks `<folder>/.syntagmax/config.toml` first, then `<folder>/config.toml`. The resolved path is passed to `syntagmax.api.open_project` with `Options(allow_dirty_worktree=True)`, which is the default for reviewer sessions so ordinary working copies that contain untracked notes, editor swap files, or local edits open cleanly rather than raising a fatal error.
- **Open errors are non-fatal.** A fatal error, core exception, or parse error during open is caught and shown in a dismissible dialog; the application stays running and returns to its empty state.
- **Reload** (bound to `F5`, or available as a menu action) re-opens the current project from disk by instantiating a fresh `Session`, so changes authored externally with the command-line tool are reflected without re-navigating the file dialog.
- **Branch bar.** When the opened project is inside a Git working tree, the branch bar lists the local branches and lets the user check one out, which re-opens the project on the selected branch as a new `Session`. The checkout is non-destructive and guarded: it is refused with a non-fatal message when the working tree has uncommitted modifications or conflicting untracked files. A detached HEAD, tag, or rebase state is shown as `(HEAD detached at <short-sha>)` with switching disabled rather than crashing, and Git command, file-lock, or permission failures are caught and surfaced. When the project is not a Git repository, the branch control is hidden rather than reported as an error.
- **Recent Projects** menu offers one-click re-open of previously opened projects.

## Analysis panel

The Analysis panel runs `Session.analyse()` and renders the result in two parts:

- A **metrics strip**, rendered defensively against empty or unknown metric shapes.
- A **diagnostics list** grouped by `location`, each row showing its `severity`, `rule`, `category`, `message`, and `artifact_id`.

**Severity filter toggles** — Error, Warning, and Info — sit above the grouped list so blocking issues are not buried among informational notices. When analysis reports no issues, the panel shows a positive "no issues" confirmation rather than an empty void.

## Traceability panel

The Traceability panel renders the matrix returned by `Session.trace(child_type, parent_type, *, direction=..., flat=...)`. The user selects four orthogonal controls:

- a child artifact type;
- a parent artifact type;
- a **direction**, either forward or reverse; and
- an independent **flat** toggle.

Direction and flat are independent: `flat` is not a direction value. The child and parent selectors are populated from the project's declared artifact types, falling back to the distinct types observed across the project's artifacts when no declared metamodel is available. The result renders as a dense table backed by a virtual Qt table model, so large matrices do not freeze the window.

**Export.** The user can export the matrix to a `.csv` or `.tsv` file on disk via `syntagmax.api.render_trace(result, delimiter=...)`. CSV is written with a UTF-8 BOM (`utf-8-sig`) for Microsoft Excel compatibility. A locked or unwritable target — for example, the file is open in Excel — is caught and surfaced as a non-fatal dialog rather than crashing the application.

## Browser panel

The Browser is a read-only artifact browser. It lists artifacts grouped by type (`Session.query()`), filters by type, and searches by content (`Session.search(q)`, with case-insensitive AND semantics). The search input is debounced (roughly 250–300 ms) so a full linear search scan does not fire on every keystroke.

Selecting an artifact shows its `fields`, its parent and child links, and its rendered Markdown `body`. **Parent and child identifiers are clickable** and select the target artifact in the browser, so a reviewer auditing traceability can follow a dangling or invalid link directly instead of copying and pasting identifiers. There are no create, edit, or delete controls.

### Known Markdown-rendering limitations

The Markdown view wraps `QTextBrowser` and renders a body with `setMarkdown()`. The document's base URL is set to the project root so relative image references in a body — for example, `![diagram](assets/overview.png)` — resolve against the project on disk rather than failing to load.

Qt's Markdown engine understands the CommonMark subset only. The following are accepted v1 limitations, and such source appears verbatim rather than formatted:

- GitHub-flavoured Markdown tables are not rendered.
- Obsidian-style wikilinks (`[[Note]]`) are not rendered.

This is an accepted limitation for v1 of the reviewer, which targets plain CommonMark bodies. External links in a body are opened by the host browser rather than navigated inside the widget, so a reviewer never loses the rendered body by following a link.
