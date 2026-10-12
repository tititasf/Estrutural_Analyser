"""Safety and canonical serializer parity for the non-publishing SA path."""
import json
import ast
from pathlib import Path
from types import SimpleNamespace

import pytest
from scripts.arete import headless_sa_analise as sa


def test_analysis_cache_stays_on_canonical_run_owner():
    tree = ast.parse(Path(sa.__file__).read_text(encoding="utf-8"))
    functions = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    assert [ast.unparse(d) for d in functions['run_analysis'].decorator_list] == ['analysis_run_cache']
    assert not functions['_validate_development_run'].decorator_list


@pytest.mark.parametrize("options", [
    {"persist_db": True}, {"generate_n3": True},
    {"sections": {"lajes"}}, {"item_names": {"P34"}},
])
def test_development_rejects_mutating_or_partial_scope(tmp_path, options):
    db = tmp_path / "project.sqlite"
    db.touch()
    params = dict(persist_db=False, generate_n3=False, sections=None, item_names=None)
    params.update(options)
    with pytest.raises(ValueError):
        sa._validate_development_run(str(db), str(tmp_path), **params)


def test_development_requires_isolated_existing_database(tmp_path):
    params = dict(persist_db=False, generate_n3=False, sections=None, item_names=None)
    outside = tmp_path.parent / "external.sqlite"
    with pytest.raises(ValueError):
        sa._validate_development_run(str(outside), str(tmp_path), **params)
    db = tmp_path / "project.sqlite"
    with pytest.raises(ValueError):
        sa._validate_development_run(str(db), str(tmp_path), **params)
    db.touch()
    sa._validate_development_run(str(db), str(tmp_path), **params)
    with pytest.raises(ValueError):
        sa._validate_development_run(str(db), None, **params)


def test_development_api_refuses_before_source_resolution(tmp_path):
    with pytest.raises(ValueError, match="persistence"):
        sa.run_analysis("obra", "pav", development=True)


def test_canonical_serializer_and_published_json_have_same_payload(tmp_path):
    # Use the real owner methods without creating Qt UI or invoking renderers.
    from src.ui.widgets.pre_validation_dialog import PreValidationDialog
    target = tmp_path / "state.json"
    fake = SimpleNamespace(
        _nivel_report={}, _pillar_report={}, _pillar_combos={}, _slabs=[],
        _cut_view_data=[], _cut_combos={}, _cut_status_combos={},
        _cut_attention={}, _segment_data={}, _segment_status_combos={},
        _segment_attention={}, _atencao_notes={}, _obra="fixture", _pavimento="pav",
        _db_path="temporary.sqlite", _build_slab_nivel_map=lambda: {},
        _analysis_state_path=lambda: str(target),
    )
    fake._serialize_analysis_state = lambda: PreValidationDialog._serialize_analysis_state(fake)
    before = fake._serialize_analysis_state()
    assert not target.exists()
    PreValidationDialog._save_analysis_state(fake)
    published = json.loads(target.read_text(encoding="utf-8"))
    before.pop("gerado_em")
    published.pop("gerado_em")
    assert published == before
    assert set(before) == {"obra", "pavimento", "db_path", "pilares", "slabs", "cortes", "segmentos"}
