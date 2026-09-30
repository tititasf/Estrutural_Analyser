"""Reparo FV: evidência local + laterais próprias como referência (não regra).

Caso V323 do 13_PAV (2026-09-27): o reparo de largura juntava as linhas de
TODAS as vigas do pavimento; entre dezenas de pares de 19 cm ganhava o de
menor x — o fundo ia 27 m para o outro lado da torre (paredes da V309).
"""

from src.core.beam_interpreters import FundoVigaInterpreter

SPAN = (1982.0, 2242.0)


def _rect(x0, x1, y0=SPAN[0], y1=SPAN[1]):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def _vline(x):
    return [(x, SPAN[0]), (x, SPAN[1])]


def _beam(points, bottom_lines, name="V323"):
    item = {"points": points, "tag": "fundo", "validated": False,
            "ficha": {"largura_total_fundo": "19"}}
    beam = {
        "name": name, "dim": "19/50", "is_h": False, "fv_is_h": False,
        "pos": (3932.6, 1983.9),
        "geometry": {"classified": {
            "merged_bottom_groups_coords": [list(SPAN)],
            "seg_bottom": bottom_lines,
        }},
        "links": {"viga_fundo_seg_1_area_segs": {"contour": [item]}},
    }
    return beam, item


def _other(x0):
    return {"name": "V309", "geometry": {"classified": {
        "seg_bottom": [_vline(x0), _vline(x0 + 19.0)]}}}


def _xs(item):
    return sorted({round(p[0], 3) for p in item["points"]})


def test_par_de_mesma_largura_do_outro_lado_da_torre_nao_ganha():
    # fundo com 24 cm (dispara reparo de largura) sobre as paredes proprias
    beam, item = _beam(_rect(3936.4, 3960.4), [_vline(3936.4), _vline(3955.4)])
    FundoVigaInterpreter.repair_area_links(beam, context_beams=[beam, _other(1178.9)])
    assert _xs(item) == [3936.4, 3955.4]


def test_lateral_propria_decide_o_lado_da_face_unica():
    # So' uma face no DXF (x 3955.4) e fundo flutuando centrado nela: sem
    # referencia a faixa iria para a esquerda (3936.4 e' so' coincidencia);
    # as laterais proprias em 3955.4/3974.4 dizem que o fundo fica a direita.
    beam, item = _beam(_rect(3945.9, 3964.9), [_vline(3955.4)])
    beam["links"]["viga_segs"] = {"seg_side_a": [{"points": _vline(3955.4)}],
                                  "seg_side_b": [{"points": _vline(3974.4)}]}
    FundoVigaInterpreter.repair_area_links(beam, context_beams=[beam])
    assert _xs(item) == [3955.4, 3974.4]


def test_lateral_antiga_de_outra_faixa_e_ignorada():
    beam, item = _beam(_rect(3936.4, 3960.4), [_vline(3936.4), _vline(3955.4)])
    beam["links"]["viga_segs"] = {"seg_side_a": [{"points": _vline(1178.9)}],
                                  "seg_side_b": [{"points": _vline(1197.9)}]}
    FundoVigaInterpreter.repair_area_links(beam, context_beams=[beam, _other(1178.9)])
    assert _xs(item) == [3936.4, 3955.4]


def test_secao_do_pilar_empilhada_sob_o_rotulo_nao_vira_secao_da_viga():
    # 13_PAV: "80/19" logo abaixo de "P11" e' do pilar; a V312 e' 19/120.
    beam = {"name": "V312", "geometry": {
        "dimension_texts": [{"text": "80/19", "pos": (1641.6, 2697.4)},
                            {"text": "19/120", "pos": (1599.6, 3069.6)}],
        "texts": [{"text": "P11", "pos": (1641.6, 2712.4)}],
    }}
    geo = beam["geometry"]
    kept = FundoVigaInterpreter.drop_pillar_section_texts(geo["dimension_texts"] + geo["texts"])
    texts = [t["text"] for t in kept]
    assert "80/19" not in texts and "19/120" in texts


def test_dimensao_global_fv_volta_para_cota_da_propria_faixa():
    # 13_PAV: VF301 herdava 19/66 de P1; o tracer ja tinha provado 14/55
    # contra o fundo real em y=3193..3207.
    correct = {"text": "14/55", "pos": (1534.8, 3209.8)}
    pillar_dim = {"text": "19/66", "pos": (1110.1, 3168.8)}
    beam = {
        "name": "VF301", "dim": "19/66", "is_h": True, "fv_is_h": True,
        "fields": {"dimensao": "19/66"},
        "geometry": {
            "lv_dimension_text": correct,
            "dimension_texts": [pillar_dim, correct],
            "texts": [{"text": "P1", "pos": (1120.4, 3183.3)}],
            "classified": {
                "merged_bottom_groups_coords": [[1159.0, 4649.9]],
                "seg_bottom": [[(1159.0, 3193.0), (4649.9, 3193.0)],
                               [(1159.0, 3207.0), (4649.9, 3207.0)]],
            },
        },
        "links": {},
    }
    assert FundoVigaInterpreter.normalize_dimension_from_own_geometry(beam)
    assert beam["fields"]["dimensao"] == "14/55"
    assert beam["dim"] == "14/55"
    assert beam["geometry"]["fv_dimension_source"] == "own_classified_geometry"


def test_dimensao_global_fv_validada_nao_muda():
    candidate = {"text": "14/55", "pos": (150.0, 10.0)}
    beam = {
        "name": "V1", "dim": "19/66", "is_h": True,
        "validated_fields": ["dimensao"],
        "fields": {"dimensao": "19/66"},
        "geometry": {
            "lv_dimension_text": candidate,
            "dimension_texts": [candidate],
            "classified": {
                "merged_bottom_groups_coords": [[0.0, 300.0]],
                "seg_bottom": [[(0.0, 0.0), (300.0, 0.0)]],
            },
        },
        "links": {},
    }
    assert not FundoVigaInterpreter.normalize_dimension_from_own_geometry(beam)
    assert beam["fields"]["dimensao"] == "19/66"


def test_parede_partida_por_viga_que_chega_continua_cobrindo_o_vao():
    # V321 do 13_PAV: face esquerda interrompida em 2047..2066 (viga chega).
    left = [[(3788.4, 1982.0), (3788.4, 2047.0)], [(3788.4, 2066.0), (3788.4, 2380.0)]]
    right = [[(3807.4, 2057.5), (3807.4, 2380.0)], [(3807.4, 1982.0), (3807.4, 2040.0)]]
    pts = FundoVigaInterpreter.build_area_contour(
        axial_span=(1982.0, 2380.0), width=19.0, is_horizontal=False,
        transverse_center=3797.9, boundary_lines=left + right, allow_synthetic=False)
    ys = [p[1] for p in pts]
    assert (min(ys), max(ys)) == (1982.0, 2380.0)


def test_cruzamento_corta_nas_paredes_da_viga_funda_nao_no_rotulo():
    # 13_PAV: V312 (19/120) rotulada em x=1599.6, paredes em 1603.4/1622.4.
    v312 = {"name": "V312", "is_h": False, "dim": "19/120", "pos": (1599.6, 2695.0),
            "geometry": {"classified": {
                "merged_bottom_groups_coords": [(2680.0, 3141.0)],
                "seg_bottom": [[(1603.4, 2991.0), (1603.4, 2680.0)],
                               [(1622.4, 2680.0), (1622.4, 2991.0)],
                               [(1622.4, 3010.0), (1622.4, 3141.0)],
                               [(1603.4, 3141.0), (1603.4, 3010.0)]]}}}
    spans = FundoVigaInterpreter.split_bottom_spans_at_deeper_crossings(
        [(1503.4, 1722.4)], is_horizontal=True, beam_pos=(1212.9, 3013.8),
        own_dim_text="19/55", context_beams=[v312], own_name="V301",
    )
    assert spans == [(1503.4, 1603.4), (1622.4, 1722.4)]


def test_face_interrompida_nao_alarga_o_fundo_alem_do_vao():
    # 13_PAV VPS: V301 S6 é 2377-2477; as faces vêm de 2059 e param em
    # 2461.9. O contorno fica no vão canônico, não na extensão da linha.
    faces = [[(2059.4, 2991.0), (2461.9, 2991.0)],
             [(2059.4, 3010.0), (2461.9, 3010.0)]]
    pts = FundoVigaInterpreter.build_area_contour(
        axial_span=(2377.4, 2477.4), width=19.0, is_horizontal=True,
        transverse_center=3000.5, boundary_lines=faces, allow_synthetic=False,
    )
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert (min(xs), max(xs)) == (2377.4, 2477.4)
    assert (min(ys), max(ys)) == (2991.0, 3010.0)


def test_sem_par_no_seg_bottom_o_contorno_de_fundo_da_viga_funda_da_as_paredes():
    # 13_PAV (29/09): V330 (19/120) rotulada em x=4527.7, sem par no seg_bottom;
    # o fundo dela esta' em 4533.4/4552.4. Cortar no rotulo deixava 15 cm sem
    # fundo na VF301 (4518.2..4533.4).
    v330 = {"name": "V330", "is_h": False, "dim": "19/120", "pos": (4527.7, 2682.9),
            "geometry": {"classified": {"merged_bottom_groups_coords": [(2661.0, 3207.0)],
                                        "seg_bottom": []}},
            "links": {"viga_fundo_seg_1_area_segs": {"contour": [{"points": [
                [4533.4, 2661.0], [4552.4, 2661.0], [4552.4, 3207.0],
                [4533.4, 3207.0], [4533.4, 2661.0]]}]}}}
    spans = FundoVigaInterpreter.split_bottom_spans_at_deeper_crossings(
        [(4244.4, 4649.9)], is_horizontal=True, beam_pos=(1209.8, 3210.8),
        own_dim_text="19/66", context_beams=[v330], own_name="VF301",
    )
    assert spans == [(4244.4, 4533.4), (4552.4, 4649.9)]


def test_painel_partido_herda_as_paredes_do_contorno_que_o_contem():
    # O split nao recentra no rotulo o painel que ja' estava entre as paredes.
    beam = {"name": "VF301", "fields": {}, "links": {"viga_fundo_seg_1_area_segs": {"contour": [
        {"points": [[4244.4, 3193.0], [4649.9, 3193.0], [4649.9, 3207.0],
                    [4244.4, 3207.0], [4244.4, 3193.0]]}]}}}
    FundoVigaInterpreter._rebuild_auto_area_slots_from_coords(
        beam, [(4244.4, 4533.4), (4552.4, 4649.9)], is_horizontal=True,
        beam_pos=(1209.8, 3210.8), width=19.0,  # dimensao errada (19/66 do pilar)
    )
    for idx in (1, 2):
        pts = beam["links"][f"viga_fundo_seg_{idx}_area_segs"]["contour"][0]["points"]
        assert sorted({p[1] for p in pts}) == [3193.0, 3207.0]
