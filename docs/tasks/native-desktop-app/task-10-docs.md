# [ ] Task 10 — Documentation & licensing note

**Spec**: `docs/specs/native-desktop-app.spec.md` (R15, R16)
**Depends on**: all prior (Wave 6).

## Objective

Document install, launch, and the reviewer workflow across `README.md` **and** `docs/reference/`, and record the PySide6-LGPL/MIT compatibility decision.

## Files

- `README.md`, `docs/reference/desktop-app.md`, `docs/reference/packaging.md`.

## Guidance

- `README.md`: quickstart — `uv sync`, `uv run syntagmax-desktop`, and the MSI build command; a short feature overview (reviewer: open → analysis → traceability → browse); the read-only scope; and a **Licensing** section recording that PySide6 (LGPL) is used via dynamic linking and is compatible with the core's MIT licence (R15).
- `docs/reference/desktop-app.md`: the reviewer workflow and each panel (open/branch/reload/MRU, Analysis with severity filters, Traceability with direction + flat and CSV/TSV export, read-only Browser with clickable links), plus known Markdown-rendering limitations.
- `docs/reference/packaging.md`: the cx_Freeze build, Qt-plugin bundling, the MSI parameters, and the crash-log location.
- Per project rule, documentation must cover README **and** `docs/reference/` — not just the README. Use relative paths only.

## Test requirements

- Docs render; internal links resolve; the licensing decision is explicit.

## Demo

```
# visually verify README and docs/reference/ pages render and cross-link
```
