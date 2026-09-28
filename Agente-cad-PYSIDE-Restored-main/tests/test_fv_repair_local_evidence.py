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
