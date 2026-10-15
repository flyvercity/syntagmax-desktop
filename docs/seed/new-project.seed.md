# Seed Spec: Create a New Project from the Desktop App

Source: GitHub issue #1 "New Project" (Tildon) — *"A user-friendly app. How can I create a new project quickly?"*

Right now the only way to start a Syntagmax project is the command line (`syntagmax init`, or equivalent). A reviewer who lives entirely in the desktop window has no way to go from "empty folder" to "a project I can open and analyse" without dropping to a terminal — which is exactly the thing the desktop app exists to avoid. We want a one-click **New Project** flow: pick an empty folder, and the app scaffolds a minimal, valid Syntagmax project and opens it.

## Intent

- A reviewer who has never touched the CLI can create a brand-new, valid project from the desktop app in a few clicks.
- "Quickly" is the point: pick a location, (optionally) name it, confirm — and the project is created and opened, ready to browse and analyse.
- The scaffold must be a *real*, openable project: a `.syntagmax/config.toml`, a starter metamodel, and the standard `.gitignore` — the same shape the CLI `init` produces, so a project created in the app is indistinguishable from one created on the command line.

## Important scope note (read first)

This is the **first write capability** in Syntagmax Desktop. The v1 seed (`docs/seed/native-desktop-app.seed.md`) fixed the scope as strictly **read-only** — "No artifact editing, no commit, no push." Creating a project is a filesystem write, so this feature deliberately **extends** that scope. It should be framed as a **post-v1 (v2) addition**, and it must not weaken the read-only guarantees of the existing review flow:

- No artifact create/edit/delete controls are introduced — only one-time project *bootstrap*.
- Once a project is open, the app remains a read-only reviewer exactly as before.

## Known constraint: the core API gap

The core already knows how to scaffold a project — `syntagmax/src/syntagmax/init_cmd.py` has `init_project(cwd)`, which writes `.syntagmax/config.toml` (via `generate_toml()`), a starter `project.syntagmax` metamodel, and a `reports/` `.gitignore`.

However, the desktop app is only allowed to consume the core through the public `syntagmax.api` surface (per README and the v1 spec), and `api.py` does **not** currently re-export `init_project` — it exposes `open_project` / `Session` only. So this feature depends on a small upstream decision:

- **Preferred:** add a thin, public `syntagmax.api` entry point (e.g. `api.init_project(path)` or `api.create_project(path, *, name=...)`) that wraps the existing `init_cmd.init_project`, so the desktop app stays on the public embedding surface. This should be raised with the core.
- **Fallback (if the API cannot be extended in time):** the desktop app calls `init_cmd.init_project` directly as a documented, temporary exception, with a tracking note to migrate to the public API later.

The full spec should settle which path is taken.

## Primary Workflow

1. From the main window (menu / toolbar: **New Project…**), the reviewer picks a target folder via a native dialog.
2. The app checks the folder is a safe target:
   - If it already contains a `.syntagmax/config.toml`, refuse (offer to *open* it instead of overwriting).
   - If it is non-empty but not a Syntagmax project, warn before scaffolding.
3. The app scaffolds the project (via the core) — `.syntagmax/config.toml`, starter metamodel, `.gitignore`.
4. The app immediately **opens** the new project (reusing the existing open flow and the off-UI-thread worker) so the reviewer lands in the normal analysis / browse view.
5. The new project is added to **Recent Projects**.

## Expected result

Given an empty folder `C:\work\demo`, choosing **New Project… → C:\work\demo** produces:

```
C:\work\demo\.syntagmax\config.toml
C:\work\demo\.syntagmax\project.syntagmax
C:\work\demo\.syntagmax\.gitignore
```

and the app opens `C:\work\demo` showing an empty-but-valid project (analysis runs cleanly, browser shows no artifacts yet).

## Out of scope

- Project *templates* beyond the single core default scaffold (future idea).
- Creating or editing artifacts after the project exists (still CLI's job; the app stays read-only post-creation).
- Git `init` / first commit of the new project (the scaffold writes files only; versioning stays manual / CLI).
- Any change to the v1 read-only review, traceability, or branch-selection behaviour.

## Follow-up tasks

- Raise the `syntagmax.api` project-creation entry point with the core; decide preferred-vs-fallback (see constraint above).
- Add the **New Project…** command (menu + toolbar) and the folder-picker + safety checks.
- Reuse the existing open flow / worker to open the freshly created project and add it to Recent Projects.
- Update `README.md` ("Read-only scope" needs a careful amendment acknowledging the one bootstrap write) and `docs/reference/desktop-app.md`.
- Tests: scaffold into a temp dir and assert the three files exist and the project opens and analyses cleanly; assert refusal on an existing project folder.
