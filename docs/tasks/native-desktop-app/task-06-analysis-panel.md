# [ ] Task 6 — Analysis panel

**Spec**: `docs/specs/native-desktop-app.spec.md` (R5, P3)
**Depends on**: Task 5 (Wave 4 — parallel with Tasks 7, 8).

## Objective

`analysis_panel.py`: a metrics strip plus diagnostics grouped by location, with severity filtering.

## Files

- `src/syntagmax_desktop/views/analysis_panel.py`, `tests/test_analysis_panel.py`.

## Guidance

- "Run analysis" → `worker.runAnalyse`; on `analysisReady`, render.
- **Metrics**: `AnalysisResult.metrics` is a `benedict`-or-`None`; render as labelled stat cards tolerant of missing keys / unknown shape (no fixed schema assumption).
- **Diagnostics**: group by `Diagnostic.location`; blank/missing → an explicit "Unspecified location" group. Columns: severity, rule, category, message, artifact_id.
- **Severity filter toggles** (Error / Warning / Info) above the grouped list so blocking issues are not buried among informational notices (P3).
- Empty diagnostics → positive "no issues" confirmation, not a bare empty widget.
- Keep business logic in a pure helper `group_diagnostics(diagnostics, severities) -> dict[str, list[Diagnostic]]` for testability.

## Test requirements

- `tests/test_analysis_panel.py`: unit-test `group_diagnostics` — grouping by location, "Unspecified location" fallback, and severity filtering (e.g. filtering to Error-only drops warnings). Offscreen render smoke test optional.

## Demo

```
uv run pytest tests/test_analysis_panel.py -q
```
