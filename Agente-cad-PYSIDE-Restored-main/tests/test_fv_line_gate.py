"""Gate FV D-60: fundo de viga nao pode ter borda fora das linhas do estrutural."""

from src.core.beam_interpreters.fundo_viga_linhas import (
    STATUS_ANULADO,
    STATUS_REPARADO,
    STATUS_VALIDADO_FORA,
    audit_fv_lines_all,
    gate_attention,
    gate_frozen,
)

# Viga horizontal de 19 cm: paredes em y=0 e y=19, de x=0 a x=300.
LINES = [
    {"start": (0.0, 0.0), "end": (300.0, 0.0)},
    {"start": (0.0, 19.0), "end": (300.0, 19.0)},
]


def _rect(x0, x1, y0, y1):
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]


def _beam(points, validated=False):
    item = {"points": points, "tag": "fundo", "validated": validated}
    return {"name": "V1", "links": {"viga_fundo_seg_1_area_segs": {"contour": [item]}}}, item


def test_fundo_sobre_as_paredes_passa_intocado():
    beam, item = _beam(_rect(20, 280, 0, 19))
    report = audit_fv_lines_all([beam], [], LINES)
    assert report["ok"] == 1
    assert "fv_line_gate" not in item and item["points"] == _rect(20, 280, 0, 19)


def test_fundo_deslocado_uma_largura_e_reparado_no_par_de_linhas():
    # Caso V304/V308 do 13_PAV: uma borda na parede, a outra 19 cm para fora.
    beam, item = _beam(_rect(20, 280, -19, 0))
    report = audit_fv_lines_all([beam], [], LINES)
    gate = item["fv_line_gate"]
    assert gate["status"] == STATUS_REPARADO and report[STATUS_REPARADO]
    ys = sorted({p[1] for p in item["points"]})
    assert ys == [0.0, 19.0]
    assert gate["antes"] == _rect(20, 280, -19, 0)
    assert gate["cobertura_depois"] == [1.0, 1.0]
    assert "reparado" in gate_attention(item)


def test_fundo_no_vazio_e_anulado_com_o_antes_guardado():
    beam, item = _beam(_rect(20, 280, 500, 519))
    report = audit_fv_lines_all([beam], [], LINES)
    assert item["fv_line_gate"]["status"] == STATUS_ANULADO and report[STATUS_ANULADO]
    slots = beam["links"]["viga_fundo_seg_1_area_segs"]
    assert slots["contour"] == [] and slots["anulado_d60"] == [item]
    assert item["points"] == []
    assert item["fv_line_gate"]["antes"] == _rect(20, 280, 500, 519)
    assert "ANULADO" in gate_attention(item)


def test_par_de_linhas_com_largura_diferente_nao_serve_de_reparo():
    # So' ha' par de 19 cm; um fundo de 40 cm nao pode ser "encaixado" nele.
    beam, item = _beam(_rect(20, 280, -40, 0))
    audit_fv_lines_all([beam], [], LINES)
    assert item["fv_line_gate"]["status"] == STATUS_ANULADO


def test_validado_por_humano_nunca_e_alterado_so_registrado():
    beam, item = _beam(_rect(20, 280, -19, 0), validated=True)
    report = audit_fv_lines_all([beam], [], LINES)
    assert item["points"] == _rect(20, 280, -19, 0)
    assert item["fv_line_gate"]["status"] == STATUS_VALIDADO_FORA
    assert report[STATUS_VALIDADO_FORA] and not gate_frozen(item)


def test_contorno_com_vertice_colinear_ainda_e_auditado():
    pts = [[20, -19], [150, -19], [280, -19], [280, 0], [20, 0], [20, -19]]
    beam, item = _beam(pts)
    audit_fv_lines_all([beam], [], LINES)
    assert item["fv_line_gate"]["status"] == STATUS_REPARADO


def test_contorno_diagonal_fica_fora_do_gate():
    beam, item = _beam([[0, 0], [100, 100], [110, 90], [10, -10], [0, 0]])
    report = audit_fv_lines_all([beam], [], LINES)
    assert report["nao_auditavel"] == ["V1 S1"] and "fv_line_gate" not in item


def test_reparador_respeita_decisao_do_gate():
    from src.core.beam_interpreters import FundoVigaInterpreter

    beam, item = _beam(_rect(20, 280, 500, 519))
    audit_fv_lines_all([beam], [], LINES)
    FundoVigaInterpreter.repair_area_links(beam)
    slots = beam["links"]["viga_fundo_seg_1_area_segs"]
    assert slots["contour"] == [] and item["fv_line_gate"]["status"] == STATUS_ANULADO
    # contrato de area fechada nao barra o anulado (ele nao esta' em contour)
    from src.core.sa_db_persistence import fv_area_errors
    assert fv_area_errors([beam]) == []

    reparado, item2 = _beam(_rect(20, 280, -19, 0))
    audit_fv_lines_all([reparado], [], LINES)
    assert gate_frozen(item2)
    FundoVigaInterpreter.repair_area_links(reparado)
    assert sorted({p[1] for p in item2["points"]}) == [0.0, 19.0]


def test_fundo_largo_demais_e_ajustado_a_largura_declarada_da_viga():
    # Caso V327/V331 do 13_PAV: viga 14/xx, fundo nasceu com 19 — uma borda na
    # parede, a outra 5 cm para fora. O par de paredes de 14 so' serve porque
    # a cota lateral do segmento declara 14; o dim do fundo (errado) nao conta.
    walls = [{"start": (0.0, 0.0), "end": (300.0, 0.0)},
             {"start": (0.0, 14.0), "end": (300.0, 14.0)}]
    beam, item = _beam(_rect(20, 280, 0, 19))
    beam.update(viga_a_seg_1_dim="14/40", viga_fundo_seg_1_dim="19/55")
    audit_fv_lines_all([beam], [], walls)
    gate = item["fv_line_gate"]
    assert gate["status"] == STATUS_REPARADO and gate["largura_depois"] == 14.0
    assert sorted({p[1] for p in item["points"]}) == [0.0, 14.0]
    assert gate["dim_fundo_diverge"] == "19/55"

    sem_cota, item2 = _beam(_rect(20, 280, 0, 19))
    audit_fv_lines_all([sem_cota], [], walls)
    assert item2["fv_line_gate"]["status"] == STATUS_ANULADO


def test_fundo_que_passa_do_fim_da_viga_e_aparado():
    # Caso V302 S9: paredes ate' x=300, fundo segue ate' x=600 no vazio; um
    # cruzamento (vao de 19 na parede de baixo) nao corta o trecho.
    walls = [{"start": (0.0, 0.0), "end": (120.0, 0.0)},
             {"start": (139.0, 0.0), "end": (300.0, 0.0)},
             {"start": (0.0, 19.0), "end": (300.0, 19.0)}]
    beam, item = _beam(_rect(20, 600, 0, 19))
    audit_fv_lines_all([beam], [], walls)
    gate = item["fv_line_gate"]
    assert gate["status"] == STATUS_REPARADO and gate["aparado"] == [0.0, 300.0]
    assert sorted({p[0] for p in item["points"]}) == [20.0, 300.0]


def test_cota_lateral_de_outro_segmento_serve_de_largura_declarada():
    # V331: laterais com 1 segmento, fundo com 2 — a cota do seg 1 vale pro S2.
    walls = [{"start": (0.0, 0.0), "end": (300.0, 0.0)},
             {"start": (0.0, 14.0), "end": (300.0, 14.0)}]
    item = {"points": _rect(20, 280, 0, 19), "tag": "fundo"}
    beam = {"name": "V1", "viga_a_seg_1_dim": "14/40",
            "links": {"viga_fundo_seg_2_area_segs": {"contour": [item]}}}
    audit_fv_lines_all([beam], [], walls)
    assert item["fv_line_gate"]["largura_depois"] == 14.0


def test_aparo_que_sobraria_toco_anula():
    # Caso V323 S1: so' 25 de 260 cm tem parede (junto ao pilar) — nao e'
    # fundo que passou do fim, e' fundo no lugar errado.
    walls = [{"start": (0.0, 0.0), "end": (25.0, 0.0)},
             {"start": (0.0, 19.0), "end": (25.0, 19.0)}]
    beam, item = _beam(_rect(0, 260, 0, 19))
    audit_fv_lines_all([beam], [], walls)
    assert item["fv_line_gate"]["status"] == STATUS_ANULADO


def test_fundo_entre_paredes_de_outra_viga_volta_para_as_laterais_proprias():
    # Caso V327 do 13_PAV: o fundo nasceu entre as paredes de OUTRA viga
    # (linha no DXF, cobertura ok), mas as laterais da viga estao em y=100/114.
    walls = LINES + [{"start": (0.0, 100.0), "end": (300.0, 100.0)},
                     {"start": (0.0, 114.0), "end": (300.0, 114.0)}]
    beam, item = _beam(_rect(20, 280, 0, 19))
    beam["viga_a_seg_1_dim"] = "14/50"
    beam["links"]["viga_segs"] = {
        "seg_side_a": [{"points": [[20, 100], [280, 100]]}],
        "seg_side_b": [{"points": [[20, 114], [280, 114]]}]}
    audit_fv_lines_all([beam], [], walls)
    gate = item["fv_line_gate"]
    assert gate["status"] == STATUS_REPARADO and gate["largura_depois"] == 14.0
    assert sorted({p[1] for p in item["points"]}) == [100.0, 114.0]

    # Laterais proprias sem linha no DXF: anula (nao volta para a outra viga).
    beam2, item2 = _beam(_rect(20, 280, 0, 19))
    beam2["links"]["viga_segs"] = beam["links"]["viga_segs"]
    audit_fv_lines_all([beam2], [], LINES)
    assert item2["fv_line_gate"]["status"] == STATUS_ANULADO
