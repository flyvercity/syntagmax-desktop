"""Guard that the pinned ``syntagmax`` submodule exposes the embedding API.

This is the R12 / critique-E9 regression guard: the submodule must stay on an
``api.py``-bearing revision (``cca2a29`` on ``more-gui-adaptations`` or later),
never regressing to a pre-API core commit.
"""


def test_syntagmax_api_open_project_importable():
    from syntagmax.api import open_project  # noqa: F401


def test_syntagmax_api_core_surface_present():
    from syntagmax import api

    for name in ('open_project', 'Options', 'Session', 'AnalysisResult', 'TraceResult', 'render_trace'):
        assert hasattr(api, name), f'syntagmax.api is missing {name!r}'
