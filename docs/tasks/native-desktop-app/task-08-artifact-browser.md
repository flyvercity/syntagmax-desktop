# [ ] Task 8 — Read-only artifact browser

**Spec**: `docs/specs/native-desktop-app.spec.md` (R8, P2, E5, E6, E8)
**Depends on**: Task 5 (Wave 4 — parallel with Tasks 6, 7).

## Objective

`browser_panel.py` + `markdown_view.py`: an atype-grouped artifact list, type filter, debounced content search, and a detail view with clickable relationship links and rendered Markdown.

## Files

- `src/syntagmax_desktop/views/browser_panel.py`, `src/syntagmax_desktop/widgets/markdown_view.py`, `src/syntagmax_desktop/models/artifact_list_model.py`, `tests/test_browser_panel.py`.

## Guidance

- List from `worker.runQuery` grouped by `atype`, backed by a virtual model (`QAbstractListModel`) for large sets (E6); a type-filter combo narrows by `atype`.
- Search box → `worker.runSearch`, **debounced ~250 ms via `QTimer`** so a full linear `Session.search` scan does not fire per keystroke (E5).
- Detail view: `ArtifactView.fields` as a key/value table; **parent/child ids rendered as clickable links** that select the target artifact in the list (P2) — follow a dangling/invalid link to reveal it.
- `markdown_view.py`: `QTextBrowser.setMarkdown(body)` with `document().setBaseUrl(QUrl.fromLocalFile(project_root))` so relative images resolve (E8). Document the CommonMark-subset limitation (no GFM tables / Obsidian wikilinks) as a known v1 constraint.

## Test requirements

- `tests/test_browser_panel.py` (offscreen, `pytest-qt`): populate from a fixture; filter by an atype → expected subset; a known search term → expected matches; clicking a parent id selects that artifact; detail shows the body text. Assert the search is debounced (rapid `textChanged` fires a single worker call via `qtbot`).

## Demo

```
set QT_QPA_PLATFORM=offscreen
uv run pytest tests/test_browser_panel.py -q
```
