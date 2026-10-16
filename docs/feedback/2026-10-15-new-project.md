# Deferred Items — new-project

**Date**: 2026-10-15
**Source spec**: docs/specs/new-project.spec.md
**Mode**: autoflow

## Summary

Autoflow delivered the New Project feature (GitHub issue #1): a public `syntagmax.api.create_project` entry point in the core (on the submodule branch `feat/api-create-project`) plus a desktop New Project flow — a folder picker with dual-config and non-empty safety checks, an atomic scaffold (`.syntagmax/` config, starter metamodel, `.gitignore`, and a default `REQ/` directory), auto-open of the created project, a first-run `REQ/` hint, a Reveal Project Folder action, and a busy action-lockout. All six critique must-address items and both HIGH code-review findings were applied, along with the two MEDIUM and two LOW findings. The items below were consciously set aside and are candidates for a future iteration.

## Deferred Items

| ID | Origin | Priority | Item | Rationale / Next Step |
|----|--------|----------|------|-----------------------|
| D1 | Code Review HIGH (H-1) | High | The core submodule branch `feat/api-create-project` (commit `3009961`) that the superproject now points at is **local only** — not pushed to the `syntagmax` remote. | Push `feat/api-create-project` to `git@github.com:flyvercity/syntagmax.git` and open its PR **before** the superproject branch is pushed, cloned, or run in CI, or `git submodule update` will fail with an unresolvable commit. This is a remote action deliberately left to the user per git-safety. |
| D2 | Critique 💡 (P2) | Medium | The New Project flow uses `QFileDialog.getExistingDirectory`, so the reviewer must create/navigate to the target folder in the OS dialog rather than entering a parent folder plus a project name. | Add a parent-folder + project-name dialog that creates `<parent>/<name>`, matching common IDE "New Project" patterns. Recorded as spec decision D5. |
| D3 | Critique 🤔 (P5) | Low | No option to initialise a Git repository for the new project; the branch bar is simply hidden for a non-repo project. | Optionally offer an "Initialise Git repository" checkbox at the host layer (never in the core, which must not perform Git writes). Conflicts with the current no-git-bootstrap decision (spec D3); evaluate once the flow is in use. |
| D4 | Critique 💡 (P8) | Low | No runtime success metrics (creation success rate, dispatch-to-open latency) are captured; success is verified behaviourally by tests only. | The desktop app ships no metrics backend; if telemetry is ever added, fold in lightweight timing/stability targets. Recorded as spec decision D7. |
| D5 | Scope (spec) | Low | Project *templates* beyond the single core default scaffold are out of scope. | Candidate for a later iteration if reviewers need more than the default `SYS` starter metamodel. |
| D6 | Carried over (prior feedback D8) | Medium | The `syntagmax` submodule is pinned to a feature branch, not upstream `main`. | Once `feat/api-create-project` (and `more-gui-adaptations`) merge upstream, re-pin the submodule to `main`. The `test_api_import` guard catches a bad re-pin. |

## Suggested Follow-up

The immediate, non-negotiable action is **D1** — push the submodule branch and open its PR before any superproject push/clone/CI, otherwise the submodule pointer is unresolvable. After that, **D2** (parent + name picker) is the strongest UX follow-up and a natural v1.1 `Brainstorm`/`Seed` candidate, with **D6** (re-pin the submodule to `main`) folded in once the core branch merges. D3–D5 are lower-priority nice-to-haves.
