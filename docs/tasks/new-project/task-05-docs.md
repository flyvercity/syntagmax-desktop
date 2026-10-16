# [ ] Task 5 — Documentation

**Spec**: `docs/specs/new-project.spec.md` (R9)
**Depends on**: Tasks 3–4 (describes the shipped flow). Can be drafted in parallel and finalised after.

## Objective

Update the desktop app's user-facing documentation to cover the New Project flow and to amend the read-only-scope wording precisely.

## Files

- `README.md`.
- `docs/reference/desktop-app.md`.

## Guidance

- README "Feature overview": mention **New Project** (pick a folder → scaffold → auto-open) and the Reveal Project Folder action.
- README "Read-only scope": carefully reword to state that the **sole** write capability is one-time project creation (bootstrap); artifact review, analysis, traceability, and browsing remain strictly read-only. Do not overstate — this is creation only, not editing.
- `docs/reference/desktop-app.md`: add a New Project section covering the picker, the dual-config and non-empty safety checks, the `REQ/` scaffold, auto-open, the first-run hint, and Reveal Project Folder.
- No hard-wrapped prose; relative paths only; British English, Oxford commas.

## Test requirements

None (documentation). Visual review; confirm the read-only-scope wording is accurate and not overstated.

## Demo

Visual review of both files.
