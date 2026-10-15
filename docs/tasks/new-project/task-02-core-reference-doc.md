# [ ] Task 2 — Core: embedding-API reference doc

**Spec**: `docs/specs/new-project.spec.md` (C9)
**Depends on**: Task 1 (documents its behaviour). Can be drafted in parallel against the agreed signature.

## Objective

Document the new `create_project` entry point in the core's embedding-API reference.

## Files

- `syntagmax/docs/reference/embedding-api.md`.

## Guidance

- Add an entry describing:
  - the signature `create_project(path: str | Path) -> Path` and that it returns the resolved `.syntagmax/config.toml` path;
  - the files written (`.syntagmax/config.toml`, `.syntagmax/project.syntagmax`, `.syntagmax/.gitignore`) plus the default `REQ/` input directory;
  - the dual-config refusal (`.syntagmax/config.toml` **or** flat `config.toml`) and the filesystem-root refusal, both raising `FatalError`;
  - the atomic rollback-on-failure behaviour.
- Relative paths only; no hard-wrapped prose; British English.

## Test requirements

None (documentation). Visual review only.

## Demo

Visual review of the rendered section.
