"""Portal must publish all four independent LV N5 variants or fail the job."""
from pathlib import Path
import json
from types import SimpleNamespace

import pytest

from portal.app import pipeline_runner
from portal.app.config import Settings
from src.core import n5_assembler
from fastapi import HTTPException
from portal.app.n5_lateral_variants import lateral_variant_path


@pytest.fixture(autouse=True)
def mocked_assembler_stays_in_test_process(monkeypatch):
    # These routing tests patch assemble_n5; real process isolation and DXF
    # parity are exercised separately in tests/test_n5_tasks.py.
    from src.core import cad_render_cache
    monkeypatch.setattr(cad_render_cache, 'render_worker_limit', lambda *args: 1)


def _published(tmp_path, behavior='PARA', assembly='gradeadas', **changes):
    path = tmp_path / f'N5_LV_13_PAV_NOVA_{behavior}_{assembly}.dxf'
    path.write_bytes(b'DXF')
    data = dict(classe='LV', visual_mode='NOVA', obra='Test', pavimento='13_PAV',
                lateral_behavior=behavior, lateral_assembly=assembly, ok_count=10, missing_count=0)
    data.update(changes)
    path.with_suffix('.json').write_text(json.dumps(data), encoding='utf-8')
    return path


@pytest.mark.parametrize('behavior', ['PARA', 'PASSA'])
@pytest.mark.parametrize('assembly', ['gradeadas', 'sarrafeadas'])
def test_download_variant_preserves_independent_identity(tmp_path, behavior, assembly):
    source = _published(tmp_path)
    target = _published(tmp_path, behavior, assembly)
    assert lateral_variant_path(source, 'LV', behavior, assembly) == target


@pytest.mark.parametrize('changes', [dict(pavimento='12_PAV'), dict(visual_mode='INI'),
                                    dict(missing_count=1), dict(lateral_assembly='gradeadas')])
def test_variant_rejects_stale_or_incomplete_inventory(tmp_path, changes):
    source = _published(tmp_path)
    _published(tmp_path, 'PASSA', 'sarrafeadas', **changes)
    with pytest.raises(HTTPException) as error:
        lateral_variant_path(source, 'LV', 'PASSA', 'sarrafeadas')
    assert error.value.status_code == 404


def test_variant_requires_both_selectors(tmp_path):
    with pytest.raises(HTTPException) as error:
        lateral_variant_path(_published(tmp_path), 'LV', 'PASSA', None)
    assert error.value.status_code == 422


def test_lateral_preview_carries_selection_to_each_sheet(tmp_path):
    import xml.etree.ElementTree as ET
    from portal.app.routers.jobs_routes import _n5_pl_tiled_svg
    source = _published(tmp_path, 'PASSA', 'sarrafeadas')
    data = json.loads(source.with_suffix('.json').read_text())
    data['frame_layout'] = dict(kind='nova_frames_v1', pages=[dict(origin=[0, 0])])
    source.with_suffix('.json').write_text(json.dumps(data))
    root = ET.fromstring(_n5_pl_tiled_svg('Test', '13_PAV', source, classe='LV',
                       lateral_behavior='PASSA', lateral_assembly='sarrafeadas'))
    href = root.find('{http://www.w3.org/2000/svg}image').attrib['href']
    assert '/n5/LV/foto-sheet/0?' in href
    assert 'lateral_behavior=PASSA&lateral_assembly=sarrafeadas' in href


def test_lateral_cold_sheet_render_uses_nova_dimensions(tmp_path, monkeypatch):
    from portal.app.routers import jobs_routes as routes
    from src.core import n5_sheet_preview
    source = _published(tmp_path)
    data = json.loads(source.with_suffix('.json').read_text())
    data['frame_layout'] = dict(kind='nova_frames_v1', pages=[dict(origin=[0, 0])])
    source.with_suffix('.json').write_text(json.dumps(data))
    folder = source.parent / (source.stem + '_pages')
    folder.mkdir()
    page = folder / 'page_000.dxf'
    page.write_bytes(b'DXF')
    monkeypatch.setattr(routes, '_obra_do_membro', lambda *a: {})
    monkeypatch.setattr(routes.repo, 'listar_n5_releases_por_obra', lambda *a: [])
    monkeypatch.setattr(routes, '_select_n5_release', lambda *a: {'dxf_path': str(source)})
    calls = []
    def render(path, *dimensions):
        calls.append((path, dimensions))
        return b'<svg/>'
    monkeypatch.setattr(n5_sheet_preview, 'render_sheet', render)
    response = routes.n5_pl_foto_sheet('Test', 'LV', 0, None,
        pavimento='13_PAV', visual_mode='NOVA', pillar_group=None,
        lateral_behavior='PARA', lateral_assembly='gradeadas', membro={}, conn=None)
    assert response.body == b'<svg/>'
    assert calls == [(page, ())]


@pytest.mark.parametrize('selected', ['gradeadas', 'sarrafeadas'])
def test_portal_n5_keeps_all_variants_and_selected_output(tmp_path, monkeypatch, selected):
    calls=[]
    def assemble(obra_dir, classe, **kwargs):
        identity=(kwargs['lateral_behavior'],kwargs['lateral_assembly'])
        calls.append(identity)
        path=tmp_path/f'{identity[0]}_{identity[1]}.dxf'
        return SimpleNamespace(output_path=path,manifest_path=path.with_suffix('.json'),
            ok_count=1,missing_count=0,extra_count=0,extra_ids=[])
    monkeypatch.setattr(n5_assembler,'assemble_n5',assemble)
    settings=Settings(dados_obras_dir=tmp_path)
    result=pipeline_runner.executar_n5(settings,{'id':'test','nome':'Test'},classe='LV',
        pavimento='13_PAV',dry_run=False,visual_mode='NOVA',
        vigas_config={'comportamento_laterais_vigas':selected})
    assert result.ok
    assert set(calls)=={(b,a) for b in ('PARA','PASSA') for a in ('gradeadas','sarrafeadas')}
    assert len(calls)==4
    assert Path(result.artefatos['n5_dxf']).name==f'PARA_{selected}.dxf'
    assert set(result.artefatos['lateral_parts'])=={'PARA','PASSA'}
    assert all(set(parts)=={'gradeadas','sarrafeadas'} for parts in result.artefatos['lateral_parts'].values())


def test_one_failed_variant_fails_whole_portal_job(tmp_path,monkeypatch):
    def assemble(obra_dir,classe,**kwargs):
        if kwargs['lateral_behavior']=='PASSA' and kwargs['lateral_assembly']=='sarrafeadas':
            raise ValueError('N3 atual incompleto: V302')
        path=tmp_path/'part.dxf'
        return SimpleNamespace(output_path=path,manifest_path=path.with_suffix('.json'),
            ok_count=1,missing_count=0,extra_count=0,extra_ids=[])
    monkeypatch.setattr(n5_assembler,'assemble_n5',assemble)
    result=pipeline_runner.executar_n5(Settings(dados_obras_dir=tmp_path),
        {'id':'test','nome':'Test'},classe='LV',pavimento='13_PAV',dry_run=False,
        vigas_config={'comportamento_laterais_vigas':'gradeadas'})
    assert not result.ok
    assert 'V302' in result.log_tail
    assert 'n5_dxf' not in result.artefatos
