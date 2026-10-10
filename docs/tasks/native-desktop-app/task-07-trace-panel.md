# [ ] Task 7 — Traceability panel

**Spec**: `docs/specs/native-desktop-app.spec.md` (R6, E2/X3, E6, E7)
**Depends on**: Tasks 5, 2 (Wave 4 — parallel with Tasks 6, 8).

## Objective

`trace_panel.py`: child/parent `atype` selectors, a direction selector, an independent `flat` checkbox, a dense matrix table, and CSV/TSV export.

## Files

- `src/syntagmax_desktop/views/trace_panel.py`, `src/syntagmax_desktop/models/trace_model.py` (`QAbstractTableModel`), `tests/test_trace_panel.py`.

## Guidance

- Populate the child/parent selectors from `core_facade.atypes`.
- **Direction** selector offers `forward`/`reverse`; a **separate `flat` checkbox** is orthogonal — do **not** fold `flat` into direction (E2/X3). "Run" → `worker.runTrace(child, parent, direction, flat)`.
- Render `TraceResult.header` + `rows` through a `TraceTableModel(QAbstractTableModel)` (not an item-based `QTableWidget`) so large matrices stay responsive (E6).
- "Export" → `QFileDialog` with `.csv`/`.tsv` filters → `worker.exportTrace(result, path, delimiter)`; CSV uses `utf-8-sig` (E7). A `PermissionError` (file open in Excel) surfaces a non-fatal dialog.

## Test requirements

- `tests/test_trace_panel.py`: unit-test `TraceTableModel` (`rowCount`/`columnCount`/`data`/`headerData` against a sample `TraceResult`); assert the panel passes `direction` and `flat` as separate arguments to the worker (e.g. via a stub worker capturing the call).

## Demo

```
uv run pytest tests/test_trace_panel.py -q
uv run syntagmax-desktop   # run a trace, toggle Flat, export CSV
```
