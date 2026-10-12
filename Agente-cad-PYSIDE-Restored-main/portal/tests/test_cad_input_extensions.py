from portal.app import recortes_reader
from portal.app.preprocessamento.sources import inventory_floor_sources, raw_level_references


def test_uppercase_dxf_is_inventory_source_and_raw_reference(tmp_path):
    entry = tmp_path / 'entrada'
    entry.mkdir()
    (entry / 'INPUT.DXF').write_bytes(b'original')
    crop = tmp_path / 'Fase-2_Triagem/recortes/INPUT'
    crop.mkdir(parents=True)
    (crop / 'torre_1.dxf').write_bytes(b'crop')
    assert recortes_reader.listar_brutos_recorte(tmp_path)[0]['bruto_id'] == 'INPUT'
    sources = inventory_floor_sources(obra_dir=tmp_path, obra_id='obra', pavimento_id='ANY',
        documents=[{'arquivo_nome': 'INPUT.DXF', 'pavimento_confirmado': 'ANY'}])
    assert len(sources) == 1
    refs = raw_level_references(tmp_path, sources)
    assert len(refs) == 1
    assert refs[0]['relative_path'] == 'entrada/INPUT.DXF'
