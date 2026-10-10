# [ ] Task 4 — Session worker & threading

**Spec**: `docs/specs/native-desktop-app.spec.md` (R9, E5, E3)
**Depends on**: Tasks 2, 3 (Wave 2).

## Objective

`session_worker.py`: run every `core_facade` call off the UI thread, communicating via Qt signals, with busy-masking so a long run never silently queues orphaned requests.

## Files

- `src/syntagmax_desktop/session_worker.py`, `tests/test_session_worker.py`.

## Guidance

- A `QObject` moved onto a `QThread` (or `QRunnable` on a `QThreadPool`). Owns the single `Session`; only the worker thread touches it.
- Slots: `openProject(config_path)`, `runAnalyse()`, `runTrace(child, parent, direction, flat)`, `exportTrace(result, path, delimiter)`, `runQuery(atype)`, `runSearch(q)`.
- Signals: `opened(bool)`, `analysisReady(object)`, `traceReady(object)`, `queryReady(object)`, `searchReady(object)`, `failed(str)`, `busyChanged(bool)`.
- Wrap every call: emit `busyChanged(True)` on entry and `busyChanged(False)` on exit; catch `FatalError`/`RMSException`/`Exception` and emit `failed` with a readable, redacted message (never echo secret values). Busy-masking lets the UI block new requests rather than queue them (E5).

## Test requirements

- `tests/test_session_worker.py` with `pytest-qt` (`qtbot.waitSignal`) and `QT_QPA_PLATFORM=offscreen`: open a fixture → `opened(True)`; `runAnalyse` → `analysisReady`; a bad path → `failed`; assert `busyChanged` toggles `True`→`False` around a run (E3).

## Demo

```
set QT_QPA_PLATFORM=offscreen
uv run pytest tests/test_session_worker.py -q
```
