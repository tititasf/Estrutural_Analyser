import json
from portal.app.routers.n1_routes import _robot_pilar, _niveis_absolutos_pilar


def put(root, relative, data):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding='utf8')


def test_current_floor_pack_wins_over_unscoped_and_other_floor(tmp_path):
    put(tmp_path, 'estado_TIPO.json', {})
    put(tmp_path, 'estado_13_PAV.json', {})
    put(tmp_path, 'Fase-4_Sincronizacao/JSON_Pilares/P1.json', {'altura':321})
    put(tmp_path, 'TIPO_2026/pilares/n3_variants/para/P1.json',
        {'pavimento':'TIPO','altura':292,'nivel_saida_abs':534.94,'nivel_chegada_abs':537.86})
    wrong = {'pavimento':'13_PAV','altura':321,'nivel_saida_abs':848.98,'nivel_chegada_abs':852.19}
    put(tmp_path, '13_PAV_2027/pilares/n3_variants/para/P1.json', wrong)
    put(tmp_path, 'Fase-6_Execucao_CAD/n3_variants/para/P1.json', wrong)
    assert _robot_pilar(tmp_path,'P1','para','TIPO')['altura'] == 292
    assert _niveis_absolutos_pilar(tmp_path,'TIPO','P1')['nivel_chegada_abs'] == 537.86


def test_missing_floor_never_reuses_unknown_global_output(tmp_path):
    put(tmp_path, 'estado_TIPO.json', {})
    put(tmp_path, 'estado_TERREO.json', {})
    put(tmp_path, 'Fase-6_Execucao_CAD/n3_variants/para/P1.json', {'altura':321})
    assert _robot_pilar(tmp_path,'P1','para','TIPO') == {}


def test_conflicting_metadata_rejects_even_floor_named_directory(tmp_path):
    put(tmp_path, 'TIPO_2026/pilares/n3_variants/para/P1.json', {'pavimento':'TERREO','altura':321})
    assert _robot_pilar(tmp_path,'P1','para','TIPO') == {}


def test_legacy_without_metadata_requires_single_matching_floor(tmp_path):
    put(tmp_path, 'estado_TERREO.json', {})
    put(tmp_path, 'Fase-6_Execucao_CAD/n3_variants/para/P1.json', {'altura':280})
    assert _robot_pilar(tmp_path,'P1','para','TERREO')['altura'] == 280
    assert _robot_pilar(tmp_path,'P1','para','TIPO') == {}
