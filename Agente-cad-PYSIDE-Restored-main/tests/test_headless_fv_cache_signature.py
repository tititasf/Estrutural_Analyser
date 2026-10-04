import importlib.util
from pathlib import Path


def test_fv_topology_changes_invalidate_context_cache(tmp_path):
    source = Path(__file__).parents[1] / 'scripts/arete/headless_sa_analise.py'
    spec = importlib.util.spec_from_file_location('fv_cache_signature_test', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    owners = (
        'src/core/beam_interpreters/fundo_viga_lateral_ref.py',
        'src/core/beam_interpreters/fundo_viga_linhas.py',
    )
    assert all(owner in module._FAST_CONTEXT_ENGINE_FILES for owner in owners)
    module._REPO_ROOT = tmp_path
    for relative in module._FAST_CONTEXT_ENGINE_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'initial source')
    dxf = tmp_path / 'source.dxf'
    dxf.write_bytes(b'structural source')
    before = module._fast_context_cache_path(str(dxf))
    for relative in owners:
        target = tmp_path / relative
        target.write_bytes(b'changed topology')
        after = module._fast_context_cache_path(str(dxf))
        assert after != before
        assert module._fast_context_cache_path(str(dxf)) == after
        before = after
