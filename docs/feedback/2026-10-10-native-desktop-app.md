# Deferred Items — native-desktop-app

**Date**: 2026-10-10
**Source spec**: docs/specs/native-desktop-app.spec.md
**Mode**: autoflow

## Summary

Autoflow delivered v1 of Syntagmax Desktop: a read-only PySide6 reviewer that opens a project through `syntagmax.api` in-process, lists and switches Git branches, runs analysis (metrics plus severity-filtered diagnostics), builds and exports traceability matrices, and browses artifacts with clickable relationship links. All critique must-address items and all HIGH code-review findings were applied. The items below were consciously set aside — chiefly the MEDIUM and LOW code-review findings and a few critique recommendations — and are candidates for a future iteration.

## Deferred Items

| ID | Origin | Priority | Item | Rationale / Next Step |
|----|--------|----------|------|-----------------------|
| D1 | Code Review MEDIUM (M-2) | Medium | The Open dialog uses `ExistingFile` mode, so a project *folder* cannot be picked despite `core_facade.open` resolving folders. | Add an explicit "Open Project Folder…" action (or a folder-mode dialog) alongside "Open Project File…". Fully satisfies R2's folder-open path. |
| D2 | Code Review MEDIUM (M-3) | Medium | `closeEvent` calls `self._thread.wait(5000)`; a core call exceeding 5 s could let the window destroy a still-running `QThread`, risking a `qFatal` on exit. | Check the `wait()` return; if the worker has not stopped, warn the user or detach the thread from the window's parent hierarchy before closing. |
| D3 | Code Review MEDIUM (M-4) | Medium | `test_session_worker.py` covers only `openProject`/`runAnalyse`; `runTrace`, `exportTrace`, `runQuery`, `runSearch`, and `runAtypes` lack direct round-trip tests, and `test_main_window.py` does not cover the `F5` reload path. | Add `qtbot.waitSignal` round-trip tests for every worker slot and a reload-action test. (H-1/H-2 regressions were added this iteration.) |
| D4 | Code Review LOW (L-1) | Low | Dead `try/except PermissionError` around a queued `emit()` in `TracePanel.export_trace` — the exception can only arise in the worker, which already surfaces it via `failed`. | Remove the dead block and rely on the worker's `failed` signal. |
| D5 | Code Review LOW (L-2, L-3) | Low | Recent-menu `QAction`s and replaced placeholder widgets are not explicitly `deleteLater()`-ed, so stale `QObject`s accumulate on repeated opens. | Parent recent actions to the menu (or `deleteLater()` on clear) and `deleteLater()` replaced placeholders in `set_panel`. |
| D6 | Code Review LOW (L-4) | Low | `core_facade.atypes` indexes `metamodel['artifacts']` on any truthy metamodel; a metamodel lacking that key would `KeyError` rather than fall back to `query()`. | Guard with `isinstance(metamodel, dict) and 'artifacts' in metamodel` before indexing. |
| D7 | Critique 💡 (E6/perf) | Low | Trace and browser models are virtual, but very large matrices/listings have not been load-tested. | Benchmark with a multi-thousand-artifact project; add fetch-more or lazy paging if needed. |
| D8 | Critique 🤔 (E9) | Medium | The `syntagmax` submodule is pinned to `cca2a29` on `more-gui-adaptations`, not upstream `main`. | Re-pin to `main` once `more-gui-adaptations` merges; the `test_api_import` guard will catch a bad re-pin. |
| D9 | Critique 💡 (success metrics) | Low | No measurable launch/open/stability targets were codified (e.g. launch < 2 s, open 1,000 artifacts < 3 s). | Add lightweight timing assertions or a manual benchmark checklist in a later iteration. |
| D10 | Scope (spec) | Low | Publication export (`Session.publish`) and impact visualisation are out of scope for v1. | Candidate features for v2 if reviewers need consolidated Markdown output in-app. |

## Suggested Follow-up

The strongest next-iteration candidates are **D2** (thread-teardown safety — the only item with a crash risk), **D1** (folder-open, completing R2), **D3** (worker-slot test coverage), and **D8** (re-pin the submodule to `main` once the API branch merges). D4–D6 are safe, trivial clean-ups suitable for a single tidy-up pass. Fold these into a future `Brainstorm`/`Seed` for a v1.1 maintenance iteration.
