"""Nível de laje por delta de corte: unidade (cm→m) e portões de coerência.

Casos reais do 13_PAV (Obra_TREINO_1) que o bug de unidade deslocou em 2026-09.
"""
from src.core.slab_level_inference import cut_delta_level, gate_cut_delta_level
from src.core.slab_level_inference import paired_cut_level_source


def test_regional_wing_does_not_borrow_principal_altitude():
    cut = {'ficha': {'side_a_laje_name':'own', 'side_b_laje_name':'other',
        'own_slab_height':12, 'neigh_slab_height':10, 'own_dist_top':2, 'neighbor_dist_top':2}}
    source = {'slab':'other', 'value':537.86}
    own = {'fields':{'laje_dim':'h=12'}}
    other = {'fields':{'laje_dim':'12'}}
    assert paired_cut_level_source(cut,'own',source,own_slab=own,source_slab=other) is None
    cut['ficha']['neigh_slab_height'] = 12
    assert paired_cut_level_source(cut,'own',source,own_slab=own,source_slab=other)['value'] == 537.86


def test_named_neighbor_without_measured_wing_cannot_make_a_false_step():
    cut = {'ficha': {'side_a_laje_name': 'own', 'side_b_laje_name': 'other',
                     'own_dist_top': 75, 'neighbor_dist_top': 0,
                     'own_slab_height': 12, 'neigh_slab_height': 0}}
    assert paired_cut_level_source(cut, 'own', {'slab': 'other', 'value': 0}) is None
    cut['ficha']['neigh_slab_height'] = 12
    assert paired_cut_level_source(cut, 'own', {'slab': 'other', 'value': 0})['value'] == -.75


def test_secondary_delta_path_requires_named_pair_and_both_measurements():
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).parents[1] / 'main.py').read_text(encoding='utf8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_cut_view_level_delta')
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), namespace)
    delta = namespace['_cut_view_level_delta']
    cut = {'ficha': {'side_a_laje_name':'own', 'side_b_laje_name':'other', 'own_dist_top':7}}
    args = (None,cut,'centro','topo',{'name':'own'},{'name':'other'})
    assert delta(*args) is None
    cut['ficha']['neighbor_dist_top'] = 0
    assert delta(*args) == -7
    cut['ficha']['neigh_slab_height'] = 0
    assert delta(*args) is None
    cut['ficha']['neigh_slab_height'] = 12
    assert delta(*args) == -7
    assert delta(None,cut,'centro','topo',{'name':'unrelated'},{'name':'other'}) is None


def test_shared_cut_transports_step_instead_of_copying_neighbor_level():
    cut = {'ficha': {'side_a_laje_name': 'own', 'side_b_laje_name': 'other',
                     'own_dist_top': '7', 'neighbor_dist_top': '0'}}
    source = {'slab': 'other', 'value': 852.19, 'human': False}
    result = paired_cut_level_source(cut, 'own', source)
    assert result['value'] == 852.12
    assert result['source_level'] == 852.19 and result['delta_cm'] == -7
    assert result['human'] is False
    assert source['value'] == 852.19
    assert paired_cut_level_source(cut, 'unrelated', source) is None


def test_shared_cut_requires_both_dimensions_and_named_opposite_slab():
    ficha = {'side_a_laje_name': 'own', 'side_b_laje_name': 'other',
             'own_dist_top': 0, 'neighbor_dist_top': 0}
    source = {'slab': 'other', 'value': 852.12}
    assert paired_cut_level_source({'ficha': ficha}, 'own', source)['value'] == 852.12
    del ficha['neighbor_dist_top']
    assert paired_cut_level_source({'ficha': ficha}, 'own', source) is None
    ficha['neighbor_dist_top'] = float('nan')
    assert paired_cut_level_source({'ficha': ficha}, 'own', source) is None


def test_inverted_delta_requires_physical_regional_slab_contact():
    cut = {'section_semantics': {'confirmed':True,'beam_type':'inverted',
        'width_cm':19,'frame':{'base_center':[0,0],'ex':[1,0],'ey':[0,1]},
        'flanges':{'left':{'height_cm':10,'bottom_cm':0},
                   'right':{'height_cm':13,'bottom_cm':0}}}}
    own = {'name':'own','points':[(10,0),(30,0),(30,15),(10,15)]}
    other = {'name':'other','points':[(-30,0),(-10,0),(-10,15),(-30,15)],
             'fields':{'laje_dim':'h=13'},'slab_steps':[
                 {'points':[(-30,0),(-10,0),(-10,15),(-30,15)],
                  'height_cm':10,'level_m':852.16,'status':'same_bottom'}]}
    source = {'slab':'other','value':852.19}
    result = paired_cut_level_source(cut,'own',source,own_slab=own,source_slab=other)
    assert result['value']==852.19 and result['source_level']==852.16
    assert result['delta_cm']==3
    assert source['value']==852.19
    assert paired_cut_level_source(cut,'own',source) is None
    remote = {**other,'points':[(-30,100),(-10,100),(-10,115),(-30,115)]}
    assert paired_cut_level_source(cut,'own',source,own_slab=own,source_slab=remote) is None
    assert paired_cut_level_source(cut,'own',source,own_slab=own,source_slab={**other,'slab_steps':[]}) is None


def test_canonical_context_consensus_keeps_distinct_centimetre_levels_separate():
    # Execute the canonical method without importing the desktop window.
    import ast
    from pathlib import Path
    tree = ast.parse((Path(__file__).parents[1] / 'main.py').read_text(encoding='utf8'))
    method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                  and n.name == '_choose_consensus_level')
    namespace = {}
    exec(compile(ast.Module(body=[method], type_ignores=[]), 'main.py', 'exec'), namespace)
    consensus = namespace['_choose_consensus_level']
    result = consensus(None, [{'value': 852.12}, {'value': 852.16}])
    assert result['ambiguous'] is True
    result = consensus(None, [{'value': 852.12}, {'value': 852.122}])
    assert not result.get('ambiguous')
    assert len(result['items']) == 2


def test_delta_em_cm_vira_metro():
    assert cut_delta_level(852.12, 7.0) == 852.19      # L324 (antes saía 859.12)
    assert cut_delta_level(852.12, 3.0) == 852.15      # L317 (antes 855.12)
    assert cut_delta_level(852.19, -30.0) == 851.89    # L318 (antes 822.19)


def test_planta_concorda_confirma():
    v = gate_cut_delta_level(852.19, 7.0, reference_level_m=852.12, own_label_level_m=852.19)
    assert v["accepted"] and v["status"] == "confirmed" and v["confirmed_by_label"]


def test_sem_planta_passa_como_inferido():
    v = gate_cut_delta_level(852.15, 3.0, reference_level_m=852.12)
    assert v["accepted"] and v["status"] == "inferred"
    assert any(g["gate"] == "P4_planta" and g["ok"] is None for g in v["gates"])


def test_valor_do_bug_e_barrado_pelo_pavimento():
    v = gate_cut_delta_level(859.12, 7.0, reference_level_m=852.12)
    assert not v["accepted"] and v["status"] == "needs_review"
    assert [g["gate"] for g in v["gates"] if g["ok"] is False] == ["P3_pavimento"]


def test_delta_absurdo_e_barrado_pela_magnitude():
    v = gate_cut_delta_level(852.12 + 1.5, 150.0, reference_level_m=852.12)
    assert not v["accepted"]
    assert any(g["gate"] == "P2_magnitude" and g["ok"] is False for g in v["gates"])


def test_planta_discorda_vai_para_revisao():
    v = gate_cut_delta_level(852.15, 3.0, reference_level_m=852.12, own_label_level_m=852.40)
    assert not v["accepted"] and v["status"] == "needs_review"
