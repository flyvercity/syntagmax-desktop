# [ ] Task 3 — Desktop: facade seam + worker slot

**Spec**: `docs/specs/new-project.spec.md` (R1, R2, R7)
**Depends on**: Task 1 for a green end-to-end, but can be written in parallel against the agreed `create_project` signature.

## Objective

Add the UI-agnostic facade function and the off-UI-thread worker slot/signal that drive project creation.

## Files

- `src/syntagmax_desktop/core_facade.py` (add `create`).
- `src/syntagmax_desktop/session_worker.py` (add `created` signal + `createProject` slot).
- `tests/test_core_facade.py`, `tests/test_session_worker.py` (extend).

## Guidance

- `core_facade.create(path: str | Path) -> Path`: one-line passthrough to `syntagmax.api.create_project`. Let `FatalError`/`RMSException`/`OSError` propagate for the worker to surface.
- `SessionWorker`: add `created = Signal(str)`. Add:
  ```python
  @Slot(str)
  def createProject(self, path: str) -> None:
      with self._busy():
          try:
              config_path = core_facade.create(Path(path))
          except Exception as exc:  # noqa: BLE001
              self._fail(exc)
          else:
              self.created.emit(str(config_path))
  ```
- Keep the slot inside `_busy()` and route every failure through `_fail` (redacted), consistent with the other slots.

## Test requirements (R8, partial)

- Facade: scaffold into `tmp_path`, assert the scaffold files **and** `REQ/` exist, and that `core_facade.open` on the returned path (or its project root) opens cleanly.
- Worker: drive `createProject` on the worker thread; assert `busyChanged(True)`/`busyChanged(False)` bracket the run, `created` carries the config path, and a failure (creating into an existing project) emits a redacted `failed` with **no** `created`.
- Use `QT_QPA_PLATFORM=offscreen` and `qtbot` signal spies, consistent with existing worker tests.

## Demo

```
uv run pytest tests/test_core_facade.py tests/test_session_worker.py -k "create" -q
```
