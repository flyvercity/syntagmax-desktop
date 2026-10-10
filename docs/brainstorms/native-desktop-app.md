# Technical Brainstorm: Native, Pythonic Desktop App for Syntagmax

> Status: **Complete (Phases 1–4).** The Open Questions were answered (see the `USER_INPUT` blocks); the approaches, comparison, and recommendation below are built on those answers. Ready to convert to a seed via the `Seed` command.

## Problem Statement & Scope

- **Core Objective:** Give users who are not comfortable on the command line a native desktop application that drives the existing `syntagmax` requirements-management core (analysis, artifact browsing/editing, traceability and publication outputs), delivered and maintained entirely within the Python ecosystem.
- **Scope Boundaries:**
    - **In scope:** A desktop front end over the `syntagmax` core for a single local user on a single machine; opening a local project (a Git working copy with a `.syntagmax/config.toml`); running analysis and viewing structured diagnostics and metrics; browsing, searching, and editing artifacts; generating traceability matrices and Markdown publications; a Pythonic implementation and a native installer.
    - **Explicitly out of scope (this brainstorm):** Multi-user authentication/authorization, OIDC, and the server-hosted collaboration model (these already exist in the sibling `syntagmax-gui`); mobile targets; re-implementing any domain logic (parsing, graph building, validation, impact) — all of that stays in the core; cloud deployment.
    - **Open at the boundary (deferred to Open Questions):** whether Git commit/push and remote PR flows belong in the desktop app, and which operating systems must be supported beyond Windows.
- **Key Constraints:**
    - **Pythonic ecosystem is a hard preference** (stated by the user). The UI layer, build, and packaging should stay in Python/`uv`; a bundled Node/Electron runtime is disfavoured.
    - The core is **synchronous and `click`-based**, but also exposes a **library embedding API** (`syntagmax.api`) intended to be consumed directly rather than by shelling out to the CLI.
    - **Git stays outside the core.** Per the embedding-API contract, the core never commits; any Git writes are the host application's responsibility.
    - **The write seam is Obsidian-driver only.** Mutating artifact operations must be gated on `Session.capabilities(driver)`; other drivers raise `UnsupportedOperation`.
    - Target runtime is **Python 3.13+** (both the core and the desktop scaffold pin `requires-python = ">=3.13"`).

## Technical Baseline & External Research

### Current Architecture

Findings from the local codebase audit (`syntagmax-desktop/` and its sibling projects under `stmx/`):

- **The desktop project is a near-empty scaffold.** `syntagmax-desktop/pyproject.toml` declares `name = "syntagmax-desktop"`, `requires-python = ">=3.13"`, and `dependencies = []`; `README.md` is empty. The `syntagmax` core is wired in as a **Git submodule** (`.gitmodules` → `git@github.com:flyvercity/syntagmax.git`).
- **The core is a `click` CLI plus a library API.** `syntagmax/src/syntagmax/cli.py` exposes the `rms` command group (`init`, `analyze`, `publish`, `change`, `trace`, `edit`, `mcp`, `schema`, `ci`, `ai`) and a `syntagmax` console-script entry point. Core dependencies already include `uvicorn`, `pydantic`, `polars`, `rich`, and an `mcp[cli]` server — so an in-process HTTP/MCP surface already exists.
- **A library-first embedding API is the intended consumption seam.** The pinned factoid and the sibling `syntagmax-gui` confirm `syntagmax.api` with `open_project(config_path, *, options=Options()) -> Session`. `Session` is thread-safe and provides `artifacts()`, `get(aid)`, `query(atype=...)`, `search(q) -> ArtifactView`, `analyse() -> AnalysisResult` (structured `Diagnostics` + metrics + impact), `edit/create/delete_artifact`, `capabilities(driver)`, and `reload()`.
- **A full web application already exists** at `../syntagmax-gui`: a **FastAPI** backend (`src/syntagmax_gui/`, versioned `/api/v1` surface) that embeds the core via `from syntagmax import api` in its `core_gateway.py` — **not** by driving the CLI — plus a **React + Vite** single-page frontend under `frontend/`. It implements workspaces, async jobs, auth modes (`debug`/`local`/`oidc`), `tagth` authorization, and Git-backed collaboration. This is a server-hosted, multi-user product — a different shape from a single-user native desktop companion, but it is the authoritative precedent for how to consume the core correctly.
- **Native packaging precedent already exists in the core.** `syntagmax/pyproject.toml` configures **`cx_Freeze`** (`[tool.cxfreeze]`) with a Windows **MSI** target (`bdist_msi`, `product_name = "Syntagmax"`, `add_to_path = true`). The CLI is already frozen into a native Windows executable/installer today.
- **Diagnostics shape** (to feed any "Analysis" view): `Diagnostic { severity, artifact_id, rule, category, location, message }`, mapped from the core `ReportError`.
- **Domain-model caveat (pinned):** Syntagmax does *not* distinguish "requirements" from "artifacts" — both are an `Artifact` with an `atype`. A "Requirements" view is a typed/filtered view over artifacts; "Artefacts" (generated outputs: matrices, impact views, publications) is a different axis. The desktop UI must model this the same way.

#### Submodule version skew (material finding)

The core submodule checked out under `syntagmax-desktop/syntagmax` is pinned to an **older commit than the one `syntagmax-gui` uses**:

- `git submodule status` reports `ebddff3… (2026.09.16-12-gebddff3)`.
- A content search of `syntagmax-desktop/syntagmax/src` for `syntagmax.api` / `open_project` / `class Session` returns **zero matches** — i.e. `api.py` is **absent** from this checkout.
- By contrast, `syntagmax-gui/syntagmax/src/syntagmax/api.py` **exists** and is imported by the GUI's `core_gateway.py`.

So the embedding API the desktop app should build on is **not present in the currently pinned submodule**. Advancing (or re-pinning) the submodule to an `api.py`-bearing revision is a prerequisite for the "consume the library directly" strategy, and is flagged as an Open Question.

### State of the Art / Industry Standards

For wrapping an existing Python tool in a desktop UI for non-technical users, the field splits into three idioms (sources: PythonGUIs' *Which Python GUI library should you use in 2026?*; dev.to case study *PySide6 vs Electron*; BeeWare Toga and Flet project docs):

1. **Native-widget toolkits** — PySide6/PyQt6 (Qt), Toga (BeeWare), wxPython. PySide6 is the consensus "professional desktop" default: batteries-included, mature tooling, LGPL. The dev.to case study reports shipping a PySide6 Windows tool at ~118 MB versus ~250 MB for an Electron equivalent. Toga is "native-native" and BSD-licensed with a first-class packaging story (Briefcase) but a smaller widget set.
2. **Flutter-via-Python** — Flet. Pure-Python authoring, adaptive/attractive UI, cross-platform including mobile, Apache-2.0. Younger ecosystem; bundles a Flutter runtime.
3. **Webview shells** — pywebview / `pywebview + Flask` / Reflex-desktop. Reuse an HTML/JS front end inside the OS's native webview (no bundled Chromium, unlike Electron), with Python as the backend. This idiom maps directly onto reusing the **existing `syntagmax-gui` React SPA**.

Packaging into installers, in Python land: **cx_Freeze** (already used by the core, MSI on Windows), **PyInstaller** (broadest), and **Briefcase** (BeeWare; signed native installers per-OS).

### Relevant Ecosystem Options

| Option | Language of UI | Native look | Bundled runtime | Packaging | Licence | Fit for "reuse existing React SPA" |
|---|---|---|---|---|---|---|
| **PySide6 / PyQt6 (Qt)** | Python | Yes (styled) | Qt libs | PyInstaller / cx_Freeze | LGPL / GPL‑or‑commercial | No (rebuild UI) |
| **Toga (BeeWare)** | Python | Yes (truly native) | Minimal | Briefcase | BSD‑3 | No (rebuild UI) |
| **Flet** | Python | Adaptive (Flutter) | Flutter | built‑in / PyInstaller | Apache‑2.0 | No (rebuild UI) |
| **pywebview (+ FastAPI/Flask)** | HTML/JS | Via OS webview | OS webview (no Chromium) | PyInstaller / cx_Freeze | BSD‑3 | **Yes** (host the SPA) |
| **Qt WebEngine (PySide6)** | HTML/JS | Chromium‑in‑Qt | Chromium | PyInstaller / cx_Freeze | LGPL (+Chromium) | Yes, but heavy |
| Electron / Tauri | JS / Rust+JS | Chromium / webview | Chromium / none | npm/cargo toolchains | — | (Non-Pythonic — excluded by constraint) |

Observations relevant to this project specifically:

- **Qt's LGPL/commercial split** matters because the core is **MIT**-licensed. PySide6 (LGPL) is generally compatible with dynamic linking, but it is a licensing dimension to confirm before standardising on Qt.
- **pywebview is the only option that lets the project reuse the already-built `syntagmax-gui` React SPA**, turning the desktop app into "the GUI backend + SPA, minus the multi-user/auth layer, wrapped in a native window." That trades a smaller UI build effort for carrying a FastAPI/web stack inside a single-user desktop app.
- A **pure native-widget** build (PySide6/Toga/Flet) consumes the `syntagmax.api` `Session` directly in-process — the simplest possible data path, no HTTP, no SPA — but means authoring a new UI from scratch rather than reusing `syntagmax-gui`.
- **cx_Freeze is already proven in this repo**, which lowers packaging risk for any Python-native option.

## Open Questions & User Clarifications

> Please edit the text inside each `USER_INPUT` block. Leaving a block unchanged means the stated **baseline assumption** will be used.

#### Q1: Relationship to the existing `syntagmax-gui` — reuse or rebuild?

- **Context:** A complete FastAPI + React SPA already exists in the sibling `syntagmax-gui`. A webview shell (pywebview) could reuse that SPA almost wholesale (dropping auth/multi-user), whereas a native-widget toolkit (PySide6/Toga/Flet) means a fresh, from-scratch UI directly on `syntagmax.api`. This single decision dominates the architecture.
    <!-- USER_INPUT_START:Q1 -->
    Keep the desktop app completely independent from Syntagmax GUI.
    <!-- USER_INPUT_END:Q1 -->

#### Q2: "Native" — do you mean native OS widgets, or just a self-contained desktop window?

- **Context:** "Native desktop app" can mean (a) genuinely native OS widgets (Toga, wxPython, or Qt's styled widgets) for a true platform look-and-feel, or (b) simply a standalone, installable, double-click-to-run desktop window (which a webview or Flet app also satisfies) regardless of whether the controls are OS-drawn. This changes which frameworks qualify.
    <!-- USER_INPUT_START:Q2 -->
    (b)
    <!-- USER_INPUT_END:Q2 -->

#### Q3: Which operating systems must the first release support?

- **Context:** The core already ships a Windows MSI via cx_Freeze, and your environment is Windows. Framework and packaging choices (and testing burden) differ sharply between Windows-only and full Windows/macOS/Linux parity. Toga/Briefcase and Flet favour cross-platform; a Windows-first MSI build reuses existing cx_Freeze config.
    <!-- USER_INPUT_START:Q3 -->
    Windows for v1, but portable in future.
    <!-- USER_INPUT_END:Q3 -->

#### Q4: How much write capability should the desktop app expose?

- **Context:** The core's write seam is **Obsidian-driver only** and the core never commits — Git is the host's job. Options range from **read-only** (open project, analyse, browse, generate reports/publications) through **artifact editing** (create/edit/delete via the Obsidian driver) up to **full Git** (stage, commit, and optionally push/PR), which would require re-implementing the Git handling that `syntagmax-gui` already has.
    <!-- USER_INPUT_START:Q4 -->
    Read-only. No Git management, besides basic branch selection.
    <!-- USER_INPUT_END:Q4 -->

#### Q5: Submodule version — may the pinned core be advanced to an `api.py`-bearing revision?

- **Context:** The embedding API (`syntagmax.api`) that the desktop app should build on is **absent** from the currently pinned submodule commit (`ebddff3`, `2026.09.16`), though it exists in the revision `syntagmax-gui` uses. Building directly on the library requires re-pinning the submodule forward. If that is not permitted, the fallback is driving the `click` CLI as a subprocess (slower, string-parsed, and discouraged by the embedding-API design).
    <!-- USER_INPUT_START:Q5 -->
    Switch the submodule to this same revision Systagmax GUI uses, as API there is more mature for external tools.
    <!-- USER_INPUT_END:Q5 -->

#### Q6: Who is the first user, and what single workflow must v1 nail?

- **Context:** "Not-so-CLI-savvy users" is broad. Knowing the primary persona (e.g. a requirements engineer reviewing analysis results, versus an author editing artifacts) and the one workflow v1 must make effortless lets the recommendation optimise the first screen rather than spreading thin across every CLI command.
    <!-- USER_INPUT_START:Q6 -->
    Reviewer: open a project and read analysis + traceability
    <!-- USER_INPUT_END:Q6 -->

### Baseline Assumptions (used if the questions above are left at default)

1. **Native = self-contained, installable, double-click desktop window** (Q2), not a hard requirement for OS-drawn widgets.
2. **Windows-first for v1** (Q3), reusing the core's existing cx_Freeze MSI packaging, with cross-platform treated as a later goal.
3. **Read + analyse + report/publication generation, plus artifact editing via the Obsidian driver** (Q4); **no** Git commit/push in v1 — the user commits through their own tooling, consistent with "Git stays outside the core."
4. **The submodule may be advanced** to a revision that includes `syntagmax.api` (Q5); the app consumes the library in-process rather than shelling out to the CLI.
5. **No strong reuse-vs-rebuild preference** (Q1) — Phase 3 will recommend, weighing the single-user simplicity of a native-widget app on `syntagmax.api` against the UI-reuse leverage of a pywebview shell over the existing SPA.
6. **Primary persona is a reviewer/author on their own machine** (Q6): open a local project, run analysis, read diagnostics and metrics, browse/search/edit artifacts, and export a traceability matrix or publication.

### Resolved constraints (from your Q1–Q6 answers)

Your answers reshape the problem decisively, so they are restated here as the fixed premises for the approaches below:

- **Independent of `syntagmax-gui`** (Q1): no reuse of its FastAPI backend, React SPA, auth, or `tagth` layer. This **removes the single advantage of a webview shell** (SPA reuse), since any webview path would now mean authoring fresh HTML/JS.
- **"Native" = self-contained installable window** (Q2): OS-drawn widgets are not required, but a double-click, no-terminal launch is.
- **Windows v1, portable later** (Q3): no Windows-only lock-in; the framework and packaging must have a credible macOS/Linux path.
- **Read-only + basic branch selection** (Q4): **no artifact editing, no commit/push.** The Obsidian write seam and `capabilities(driver)` gating are therefore **out of scope for v1**. "Branch selection" is a thin Git-read concern (list local branches, check one out, re-open the project) handled by the host, not the core.
- **Advance the submodule** to the `syntagmax-gui` revision (Q5): build directly on the mature `syntagmax.api`.
- **Reviewer persona** (Q6): the one workflow to nail is *open a project → read analysis (metrics + diagnostics) → read traceability*.

A verification of the mature `api.py` (in the GUI's core checkout) confirms it already provides everything this read-only workflow needs: `open_project(...) -> Session`, `Session.analyse() -> AnalysisResult` (metrics + `Diagnostic` list + impact), `render_trace(...) -> TraceResult`, plus `artifacts()/get()/query()/search()` for browsing. No write methods are needed for v1.

---

## Architectural Approaches Evaluated

All three approaches share the same spine: **advance the submodule to the mature core, consume `syntagmax.api` in-process (no CLI subprocess, no HTTP), and package Windows-first with a portable path.** They differ only in the **UI toolkit**. Because the app is read-only and independent, the data path is trivially an in-process `Session` call on a worker thread; the decision reduces almost entirely to the toolkit's fit for a reviewer's read-heavy UI (tables, trees, Markdown-rendered diagnostics) and its portability/packaging story.

### Approach A: PySide6 (Qt) native-widget app

- **Concept:** A `QMainWindow` reviewer shell. A project picker calls `open_project`; a background `QThread`/`QRunnable` runs `analyse()` and `render_trace()` so the UI never blocks. Metrics render as a small cards/stat strip, diagnostics as a `QTreeView`/`QTableView` grouped by `location`, traceability as a `QTableView`, and artifact bodies via Qt's rich-text/Markdown widget. A combo box lists Git branches (read via `gitpython`, already a core dependency) and re-opens the project on change.
- **Component Changes:** New `src/syntagmax_desktop/` package: `app.py` (Qt bootstrap), `session_worker.py` (threaded `syntagmax.api` calls), `views/` (analysis, trace, browser), `widgets/`. Advance the `syntagmax` submodule; wire it as an editable `[tool.uv.sources]` dependency in `pyproject.toml`.
- **Dependencies Introduced:** `PySide6` (LGPL). Packaging via the core's existing **cx_Freeze** or PyInstaller.

### Approach B: Toga (BeeWare) truly-native app

- **Concept:** Same in-process `syntagmax.api` spine, but UI authored in Toga so controls are genuinely OS-native on each platform. Analysis/trace run in a thread or via Toga's async loop; diagnostics in a `Tree`/`Table`, metrics in a box of labels, Markdown shown via a WebView cell or converted to rich text.
- **Component Changes:** Same `src/syntagmax_desktop/` layout; UI in Toga idioms. Packaging via **Briefcase** (produces signed native installers, incl. Windows MSI, macOS `.app`/`.dmg`, Linux).
- **Dependencies Introduced:** `toga` (BSD-3) + `briefcase` for packaging. Replaces cx_Freeze.

### Approach C: Flet (Flutter-via-Python) app

- **Concept:** Same spine; UI authored in Flet's pure-Python Flutter components (`DataTable`, `ListView`, cards). Flet's own build tooling or PyInstaller produces the desktop bundle.
- **Component Changes:** Same package layout; UI in Flet idioms; Markdown via Flet's `Markdown` control (built in).
- **Dependencies Introduced:** `flet` (Apache-2.0) and a bundled Flutter engine.

> **Note — pywebview shell deliberately dropped.** It was the strongest candidate *only* while SPA reuse was on the table (original Q1). With independence (Q1) **and** read-only scope (Q4), it would require authoring a brand-new HTML/JS front end plus carrying a local web server inside a single-user desktop app — strictly more moving parts than a pure-Python widget toolkit, for no remaining upside. It is therefore excluded from the shortlist rather than evaluated.

## Structured Comparison & Methodology

### SWOT Matrix

| Approach | Strengths | Weaknesses | Opportunities | Threats/Risks |
|---|---|---|---|---|
| **A: PySide6** | Richest widget set for dense read-only data (tables/trees/Markdown) out of the box; consensus "professional desktop" default; huge docs/support; reuses the **cx_Freeze packaging already in the repo**; portable (Win/mac/Linux) with no code change. | Largest API surface to learn; bundle ~100 MB+; LGPL compliance needs confirming against the core's MIT. | Qt Model/View fits grouped diagnostics and traceability tables naturally; room to grow (filtering, charts) without new deps. | LGPL/commercial licensing dimension; Qt version churn. |
| **B: Toga** | Truly native look per OS; BSD-3 (no licensing friction); Briefcase gives signed per-OS installers; smallest conceptual surface. | Smaller/less mature widget set — dense tables, grouped trees, and Markdown are weaker and may need WebView workarounds; abandons the repo's cx_Freeze setup. | Best long-term cross-platform story (Q3's "portable later"), incl. a future mobile angle. | Widget gaps could bite exactly on the reviewer's table/tree-heavy screens; smaller community. |
| **C: Flet** | Attractive modern UI with least UI code; built-in `DataTable`/`Markdown`; Apache-2.0; cross-platform. | Youngest ecosystem; bundles a Flutter engine (large); desktop packaging less battle-tested than Qt; diverges from the repo's Python-UI/cx_Freeze norm. | Fast, pretty v1; same codebase could later target web/mobile. | Framework maturity/churn risk on desktop; data-grid limits for very large matrices. |

### Methodology

Weighted against the resolved constraints, in priority order: (1) fit for a **read-heavy reviewer UI** (dense diagnostics tree + traceability table + Markdown) — favours A; (2) **portability without lock-in** (Q3) — all three qualify, B strongest; (3) **packaging leverage** — A reuses the repo's proven cx_Freeze MSI; (4) **ecosystem maturity / support burden** for a solo-maintained companion app — favours A; (5) **licensing** — B/C cleaner, A needs an LGPL check but is standard.

## Recommendation

**Adopt Approach A: a PySide6 native-widget desktop app that consumes `syntagmax.api` in-process, packaged Windows-first with cx_Freeze.**

Rationale — why A wins given *your* constraints, not in the abstract:

- The reviewer workflow (Q6) is **dense, read-only, tabular data**: grouped diagnostics, a traceability matrix, and Markdown-rendered artifact bodies. This is precisely where Qt's Model/View widgets are strongest and where Toga's thinner widget set and Flet's younger data-grid are weakest. The one thing v1 must nail is the thing Qt does best.
- **Independence + read-only (Q1 + Q4)** collapse the hard parts: no auth, no multi-user, no Git writes, no Obsidian write seam. What remains is "open a `Session`, call three read methods on a worker thread, render the results" — a shape Qt handles idiomatically.
- **Portability is preserved (Q3):** the identical PySide6 code runs on macOS and Linux later with no rewrite, so "Windows v1, portable future" costs nothing now.
- **Packaging leverage:** the core *already* ships a Windows MSI via cx_Freeze, so the desktop app can follow the same, proven path rather than introducing a new packager (which B's Briefcase would).
- Toga (B) is the recommended **fallback** if a *genuinely* OS-native look becomes a hard requirement or if clean BSD licensing outweighs widget richness. Flet (C) is the pick only if visual polish and least-code speed are prioritised over data-grid robustness.

Suggested phased execution plan (ready for a seed → full spec):

1. **Foundation.** Advance the `syntagmax` submodule to the `syntagmax-gui` revision (Q5); wire it as an editable `[tool.uv.sources]` dependency; add `PySide6`; stand up a minimal `QMainWindow` that opens on `uv run`.
2. **Project open + branch selection.** Folder/config picker → `open_project`; a branch combo (list local branches via `gitpython`, checkout, re-open). Surface open/parse errors in a non-fatal dialog.
3. **Analysis panel.** Threaded `Session.analyse()`; metrics strip + diagnostics grouped by `location` (severity chip, `rule`, `category`, `message`, `artifact_id`), defensive against empty/unknown shapes.
4. **Traceability panel.** Threaded `render_trace(...)`; direction (forward/reverse/flat) selectors; dense fixed-layout table; optional CSV/TSV export to disk.
5. **Artifact browser (read-only).** `artifacts()/query()/search()` grouped by `atype`; detail view renders the Markdown `body`.
6. **Packaging + docs.** cx_Freeze Windows MSI target for the desktop app; README quickstart; `docs/reference/` page(s). (Per project rule, the full spec must include a documentation-update task covering README **and** `docs/reference/`.)

### Key Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| **Qt (LGPL) vs core (MIT) licensing** | Confirm LGPL dynamic-linking compliance before standardising; PySide6's LGPL is routinely used this way, but record the decision. Toga (BSD) is the fallback if licensing must be friction-free. |
| **Submodule advance introduces API/behaviour drift** vs the old pin | Pin to the *exact* revision `syntagmax-gui` already runs against (known-good), run the core's own test suite after bumping, and smoke-test `open_project`/`analyse`/`render_trace`. |
| **Long-running `analyse()`/`render_trace()` freeze the UI** | Run all core calls on a Qt worker thread; keep the GUI thread for rendering only; show progress and a cancel/retry affordance. |
| **`syntagmax.api` surface differs from the pinned factoid summary** | Treat `api.py` in the GUI's core checkout as the source of truth (verified: `open_project`, `Session.analyse`, `render_trace`, `AnalysisResult`, `TraceResult`, `ArtifactView` all present); design the full spec against the actual signatures. |
| **cx_Freeze packaging gaps** (hidden imports: polars, lark grammars, jinja/babel data) | Reuse the core's existing `[tool.cxfreeze]` package list as the starting point; test the frozen MSI on a clean Windows VM; add missing data files explicitly. |
| **"Portable later" quietly regresses** | Keep all OS-specific concerns (paths, packaging) isolated; run the test suite on Linux CI even while shipping Windows-only, so the portable path does not rot. |

### Summary Table

| Decision | Choice | Rationale |
|----------|--------|-----------|
| UI toolkit | **PySide6 (Qt)** | Best fit for the read-heavy reviewer UI (tables/trees/Markdown); portable; reuses repo packaging. |
| Core consumption | **In-process `syntagmax.api`** | Mature library seam; no CLI subprocess or HTTP; matches the GUI's proven pattern. |
| Submodule | **Advance to the `syntagmax-gui` revision** | That revision carries the mature `api.py` (Q5); known-good. |
| Scope (v1) | **Read-only + branch selection** | Per Q4; drops auth, editing, commit/push, and the Obsidian write seam entirely. |
| Relationship to `syntagmax-gui` | **Fully independent** | Per Q1; no shared backend/SPA/auth. |
| Packaging | **cx_Freeze Windows MSI first** | Reuses the core's existing, proven packaging; portable later. |
| First workflow | **Open project → analysis → traceability** | Per Q6; the one path v1 must make effortless. |
| Fallback toolkit | **Toga (BeeWare)** | If OS-native look or BSD licensing becomes a hard requirement. |

---

## Next Step

This brainstorm is ready to convert into a seed spec. Run the **`Seed`** command (prompt `sc.brainstorm.to.seed.md`) to distil these conclusions into `docs/seed/`, then produce a full spec in `docs/specs/`.
