"""Tests for the UI-agnostic core facade (Task 2).

These exercise ``core_facade`` against a copy of the ``obsidian-driver``
project under ``syntagmax/example/`` so the suite never mutates the committed
fixture, and so ``open`` resolves a picked folder exactly as a reviewer would.
"""

import shutil
from pathlib import Path

import pytest

from syntagmax.api import AnalysisResult, TraceResult

from syntagmax_desktop import core_facade

EXAMPLE_PROJECT = Path(__file__).resolve().parents[1] / 'syntagmax' / 'example' / 'obsidian-driver'


@pytest.fixture
def project_dir(tmp_path: Path) -> Path:
    """Copy the example project into a temporary directory."""
    destination = tmp_path / 'obsidian-driver'
    shutil.copytree(EXAMPLE_PROJECT, destination)
    return destination


@pytest.fixture
def session(project_dir: Path):
    """Open a session against the copied fixture via the facade."""
    return core_facade.open(project_dir)


def test_open_resolves_folder_to_config(project_dir: Path):
    session = core_facade.open(project_dir)
    assert session is not None
    # A non-empty artifact graph proves the config.toml under .syntagmax was resolved and loaded.
    assert core_facade.query(session)


def test_open_missing_config_raises(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        core_facade.open(tmp_path)


def test_analyse_returns_analysis_result(session):
    result = core_facade.analyse(session)
    assert isinstance(result, AnalysisResult)
    assert isinstance(result.diagnostics, list)


def test_trace_returns_header_and_rows(session):
    result = core_facade.trace(session, 'REQ', 'SYS')
    assert isinstance(result, TraceResult)
    assert result.direction == 'forward'
    assert result.header
    assert result.rows


def test_trace_direction_and_flat_are_orthogonal(session):
    forward = core_facade.trace(session, 'REQ', 'SYS', direction='forward', flat=False)
    reverse_flat = core_facade.trace(session, 'REQ', 'SYS', direction='reverse', flat=True)
    assert forward.direction == 'forward'
    assert reverse_flat.direction == 'reverse'
    # Direction swaps the lead-and-linked ID header columns independently of flattening.
    assert forward.header[1:3] != reverse_flat.header[1:3]


def test_atypes_non_empty(session):
    types = core_facade.atypes(session)
    assert types
    assert types == sorted(types)
    assert 'REQ' in types
    assert 'SYS' in types


def test_export_trace_csv_has_bom(session, tmp_path: Path):
    result = core_facade.trace(session, 'REQ', 'SYS')
    path = tmp_path / 'trace.csv'
    core_facade.export_trace(result, path, delimiter=',')
    data = path.read_bytes()
    assert data.startswith(b'\xef\xbb\xbf')


def test_export_trace_tsv_has_no_bom(session, tmp_path: Path):
    result = core_facade.trace(session, 'REQ', 'SYS')
    path = tmp_path / 'trace.tsv'
    core_facade.export_trace(result, path, delimiter='\t')
    data = path.read_bytes()
    assert not data.startswith(b'\xef\xbb\xbf')
    assert '\t'.encode() in data


def test_query_filters_by_atype(session):
    reqs = core_facade.query(session, atype='REQ')
    assert reqs
    assert all(view.atype == 'REQ' for view in reqs)


def test_search_passthrough(session):
    results = core_facade.search(session, 'REQ')
    assert isinstance(results, list)



def test_create_scaffolds_and_opens(tmp_path: Path):
    target = tmp_path / 'demo'
    config_path = core_facade.create(target)

    assert config_path == (target / '.syntagmax' / 'config.toml').resolve()
    assert (target / '.syntagmax' / 'config.toml').is_file()
    assert (target / '.syntagmax' / 'project.syntagmax').is_file()
    assert (target / '.syntagmax' / '.gitignore').is_file()
    assert (target / 'REQ').is_dir()

    # The created project opens cleanly through the normal facade path.
    session = core_facade.open(target)
    assert session is not None
    core_facade.analyse(session)


def test_create_refuses_existing_project(tmp_path: Path):
    from syntagmax.errors import FatalError

    target = tmp_path / 'demo'
    core_facade.create(target)
    with pytest.raises(FatalError):
        core_facade.create(target)
