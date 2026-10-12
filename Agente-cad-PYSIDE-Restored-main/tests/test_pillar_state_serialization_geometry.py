"""Exercise the real serializer without Qt rendering or production data."""
import ast
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace


def serializer():
    source = Path(__file__).parents[1] / 'src/ui/widgets/pre_validation_dialog.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_serialize_analysis_state')
    from src.core.preficha_segments import slab_height_cm
    namespace = {'datetime': datetime, 'SEGMENT_TAB_SPECS': {}, 'slab_height_cm': slab_height_cm}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    return namespace['_serialize_analysis_state']


def test_serialized_arrival_measures_original_local_wall_offset():
    pillar = {'name': 'PX', 'orientation': 'vertical',
              'points': [[0, 0], [22, 0], [22, 154], [0, 154]],
              'face_beams': {'B': {'para': [{'name': 'VX', 'dim': '19/120', 'corner': 'BC'}]}}}
    beam = {'name': 'VX', 'dim': '19/120',
            '_verified_wall_runs': [((22, 40, 482, 59), '19/120')],
            '_measured_corridor': (22, 40, 482, 59)}
    runner = SimpleNamespace(
        _nivel_report={}, _pillar_report={'PX': pillar}, _pillar_combos={},
        _natural_sort_key=lambda key: key, _slab_height_map={}, _slab_nivel_map={},
        _slab_poly_map={}, _beams=[beam], _atencao_notes={},
        _get_side_cell=lambda *args: '', _slabs=[], _build_slab_nivel_map=lambda: {},
        _cut_view_data=[], _obra='', _pavimento='', _db_path='')
    state = serializer()(runner)
    rows = state['pilares'][0]['interpretacao_abcd']['faces']['B']['chega']
    row = next(r for r in rows if r['nome'] == 'VX')
    assert (row['dist_esq'], row['dist_dir']) == ('40cm', '95cm')
    assert '_verified_wall_runs' not in str(state)


def test_serializer_preserves_region_and_local_contact_top():
    polygon = [(20,0),(200,0),(200,100),(20,100)]
    step = {'uid':'region-owned', 'points':polygon, 'height_cm':10,
            'level_m':855.22, 'method':'owner_confirmed_scoped_same_bottom',
            'owner_review':{'decision_id':'source-scoped-verdict'},
            'evidence_checks':{'closed_cad_boundary':True,'internal_height':True}}
    pillar = {'name':'PX','points':[(0,0),(20,0),(20,100),(0,100)],
              'lajes':[{'side':'B','laje':'LX'}], 'face_beams':{'B':{'para':[]}}}
    slab = {'name':'LX','height':'13','points':polygon,'slab_steps':[step]}
    runner = SimpleNamespace(_nivel_report={}, _pillar_report={'PX':pillar},
        _pillar_combos={}, _natural_sort_key=lambda key:key, _slab_height_map={'LX':'13'},
        _slab_nivel_map={'LX':'855.25'}, _slab_poly_map={'LX':polygon}, _beams=[],
        _atencao_notes={}, _get_side_cell=lambda *args:'', _slabs=[slab],
        _build_slab_nivel_map=lambda:{'LX':'855.25'}, _cut_view_data=[],
        _obra='', _pavimento='', _db_path='')
    state = serializer()(runner)
    assert state['slabs'][0]['slab_steps'] == [step]
    row = next(r for r in state['pilares'][0]['interpretacao_abcd']['faces']['B']['lajes']
               if r['nome']=='LX')
    assert row['dim']=='10' and row['nivel']=='855,22'
    assert row['_contact_intervals'][0]['level_m']==855.22
    assert slab['height']=='13' and runner._slab_nivel_map['LX']=='855.25'


def test_serializer_uses_verified_beam_datum_without_changing_explicit_level(monkeypatch):
    from src.core import niveis_extractor
    monkeypatch.setattr(niveis_extractor, 'get_pavimento_niveis_abs',
                        lambda *args: (_ for _ in ()).throw(AssertionError('Wrong convention used')))
    pillar = {'name': 'PX', 'orientation': 'vertical',
              'points': [[0, 0], [22, 0], [22, 154], [0, 154]],
              'face_beams': {'B': {'para': [
                  {'name': 'VX', 'dim': '19/55', 'corner': 'BC'},
                  {'name': 'VY', 'dim': '19/55', 'corner': 'BD', 'nivel': '855,18 m'}]}}}
    runner = SimpleNamespace(
        _nivel_report={}, _pillar_report={'PX': pillar}, _pillar_combos={},
        _natural_sort_key=lambda key: key, _slab_height_map={}, _slab_nivel_map={},
        _slab_poly_map={}, _beams=[], _atencao_notes={},
        _get_side_cell=lambda *args: '', _slabs=[], _build_slab_nivel_map=lambda: {},
        _cut_view_data=[], _obra='/actual/obra', _pavimento='TIPO', _db_path='',
        _sa_floor_level_reference=dict(base=852.19, top=855.25, height=3.06,
                                      unit='m', source_id='verified-source'))
    state = serializer()(runner)
    rows = state['pilares'][0]['interpretacao_abcd']['faces']['B']['chega']
    assert next(r for r in rows if r['nome'] == 'VX')['nivel'] == '855,25 m'
    assert next(r for r in rows if r['nome'] == 'VY')['nivel'] == '855,18 m'


def test_face_detail_uses_verified_datum_and_preserves_local_exception():
    source = Path(__file__).parents[1] / 'src/ui/widgets/pre_validation_dialog.py'
    tree = ast.parse(source.read_text(encoding='utf-8-sig'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_entry_viga_detail')
    namespace = {'self': SimpleNamespace(
        _sa_floor_level_reference=dict(base=852.19, top=855.25, height=3.06,
                                      unit='m', source_id='verified-source'))}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(source), 'exec'), namespace)
    detail = namespace['_entry_viga_detail']
    assert 'N: 855,25 m' in detail({'viga': {'name': 'VX', 'dim': '19/55'}})
    assert 'N: 855,18 m' in detail({'viga': {'name': 'VX', 'nivel': '855,18 m'}})
    namespace['self'] = SimpleNamespace()
    assert 'N:' not in detail({'viga': {'name': 'VX'}})
