from pathlib import Path
import json

from portal.app.routers.viewer_routes import encontrar_estrutural_limpo


def crop(root, stem, name='torre_1'):
    path = root / 'Fase-2_Triagem' / 'recortes' / stem / (name + '.dxf')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b'DXF')
    entry = root / 'entrada' / (stem + '.DXF')
    entry.parent.mkdir(exist_ok=True)
    entry.write_bytes(b'DXF')
    return path


def test_registered_custom_floor_before_sa(tmp_path):
    target = crop(tmp_path, 'EST-TIPO-R01')
    crop(tmp_path, 'EST-6000-13P-R03')
    result = encontrar_estrutural_limpo(tmp_path, {'id': 'work'}, 'EXPERIMENTAL',
        documents=[{'arquivo_nome': 'EST-TIPO-R01.DXF', 'pavimento_confirmado': 'EXPERIMENTAL'}])
    assert Path(result['path']) == target


def test_registration_overrides_filename_and_suggestion(tmp_path):
    crop(tmp_path, 'EST-6000-13P-R03')
    docs = [{'arquivo_nome': 'EST-6000-13P-R03.DXF',
             'pavimento_confirmado': 'OUTRO', 'pavimento_sugerido': '13_PAV'}]
    assert encontrar_estrutural_limpo(tmp_path, {'id': 'work'}, '13_PAV', documents=docs) is None
    assert encontrar_estrutural_limpo(tmp_path, {'id': 'work'}, 'OUTRO', documents=docs)


def test_registered_floor_never_uses_unrelated_tower(tmp_path):
    crop(tmp_path, 'EST-TIPO-R01')
    docs = [{'arquivo_nome': 'EST-TIPO-R01.DXF', 'pavimento_confirmado': 'TIPO'}]
    assert encontrar_estrutural_limpo(tmp_path, {'id': 'work'}, 'CUSTOM', documents=docs) is None


def test_legacy_work_without_document_registration(tmp_path):
    target = crop(tmp_path, 'EST-6000-13P-R03')
    assert Path(encontrar_estrutural_limpo(tmp_path, {'id': 'work'}, '13_PAV', documents=[])['path']) == target


def test_production_provenance_without_portal_connection(tmp_path):
    target = crop(tmp_path, 'EST-TIPO-R01')
    run = tmp_path / 'Fase-6_Execucao_CAD' / 'production_sa' / 'CUSTOM' / 'current'
    run.mkdir(parents=True)
    (run / 'production_manifest.json').write_text(json.dumps({'source_dxf': str(target)}))
    assert Path(encontrar_estrutural_limpo(tmp_path, {}, 'CUSTOM')['path']) == target


def test_production_provenance_cannot_escape_work(tmp_path):
    outside = tmp_path / 'outside.dxf'
    outside.write_bytes(b'DXF')
    crop(tmp_path, 'EST-TIPO-R01')
    run = tmp_path / 'Fase-6_Execucao_CAD' / 'production_sa' / 'CUSTOM' / 'current'
    run.mkdir(parents=True)
    (run / 'production_manifest.json').write_text(json.dumps({'source_dxf': str(outside)}))
    assert encontrar_estrutural_limpo(tmp_path, {}, 'CUSTOM') is None


def test_raw_dxf_extension_case_and_no_other_floor_fallback(tmp_path):
    from portal.app.routers.recortes_routes import _entrada_dxf_bruto
    crop(tmp_path, 'EST-TIPO-R01')
    crop(tmp_path, 'EST-6000-13P-R03')
    assert _entrada_dxf_bruto(tmp_path, 'EST-TIPO-R01') == tmp_path/'entrada'/'EST-TIPO-R01.DXF'
    assert _entrada_dxf_bruto(tmp_path, 'MISSING') is None
    assert _entrada_dxf_bruto(tmp_path, '../EST-TIPO-R01') is None
