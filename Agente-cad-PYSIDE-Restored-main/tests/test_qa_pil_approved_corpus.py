import json
from pathlib import Path

from scripts.arete.qa_pil_approved_corpus import (
    _extract_tables,
    compare_semantics,
    highest_approved_layer,
)


def test_highest_human_approved_layer_ignores_agent_verdicts():
    doc = {
        "notes": {
            "aten_pil_hl_sa_human_X_P1": "validou",
            "aten_pil_hl_l1_human_X_P1": "validou",
            "aten_pil_hl_l2_human_X_P1": "invalidou",
            "aten_pil_ctx_agent_verdict_l3_X_P1": "validou",
        }
    }
    layer, verdicts = highest_approved_layer(doc)
    assert layer == "L1"
    assert verdicts == {"SA": "validou", "L1": "validou", "L2": "invalidou"}


def test_extract_tables_normalizes_wrappers_empty_rows_and_units():
    payload = {
        "item": "P1",
        "tables": {
            "orientation": "Vertical",
            "faces": {
                "A": {
                    "lajes": [{"nome": "nenhuma"}],
                    "passa": [{"nome": "v1", "dim": "19 / 55", "nivel": "852,19cm", "canto": "ad", "dist_esq": "—"}],
                    "chega": [],
                    "interior": [],
                }
            },
        },
    }
    actual = _extract_tables(payload)
    assert actual["orientation"] == "vertical"
    assert actual["face_ids"] == ["A"]
    assert actual["faces"]["A"]["lajes"] == []
    assert actual["faces"]["A"]["passa"][0]["nome"] == "V1"
    assert actual["faces"]["A"]["passa"][0]["nivel_cm"] == "852.19"


def test_semantic_comparison_is_order_insensitive_but_role_exact():
    one = {"nome": "V1", "dim": "19/55", "canto": "AD", "papel": "passa"}
    two = {"nome": "V2", "dim": "19/55", "canto": "AC", "papel": "passa"}
    expected = _extract_tables({"orientation": "vertical", "faces": {"A": {"passa": [one, two]}}})
    actual = _extract_tables({"orientation": "vertical", "faces": {"A": {"passa": [two, one]}}})
    assert compare_semantics(expected, actual)["status"] == "PASS"
    wrong = _extract_tables({"orientation": "vertical", "faces": {"A": {"chega": [two, one]}}})
    result = compare_semantics(expected, wrong)
    assert result["status"] == "FAIL"
    assert {diff["field"] for diff in result["differences"]} == {"faces.A.passa", "faces.A.chega"}


def test_extensao_pelo_apoio_cruzado_reconhece_a_viga_que_atravessa():
    """Ferramenta pronta para quando a truncagem de corredor for resolvida.

    A viga morre rente a um pilar da própria largura e o corredor continua do
    outro lado: ela atravessa o apoio, e o desenho só não repete o trecho lá
    dentro (V316 × P13, V319 × P23). Ligada no gate hoje, piora — ver
    docs/INTERPRETACAO-VIGA-CHEGA-VAO-E-FACE.md.
    """
    from scripts.arete.qa_pil_approved_corpus import _extend_through_crossed_support

    # V319: sobe até y=2380, onde começa P23 (2380..2480), mesma largura.
    runs = [(3351.4, 2067.0, 3370.4, 2380.0)]
    corridor = (3351.4, 2029.0, 3370.4, 2490.0)
    p23 = (3351.4, 2380.0, 3370.4, 2480.0)

    assert _extend_through_crossed_support(
        runs, corridor, [p23], horizontal=False,
    ) == (3351.4, 2067.0, 3370.4, 2480.0)


def test_apoio_mais_largo_que_a_viga_nao_e_atravessado_por_esta_regra():
    from scripts.arete.qa_pil_approved_corpus import _extend_through_crossed_support

    runs = [(3351.4, 2067.0, 3370.4, 2380.0)]
    corridor = (3351.4, 2029.0, 3370.4, 2490.0)
    largo = (3300.0, 2380.0, 3420.0, 2480.0)

    assert _extend_through_crossed_support(
        runs, corridor, [largo], horizontal=False,
    ) is None


def test_sem_corredor_do_outro_lado_nao_estende():
    from scripts.arete.qa_pil_approved_corpus import _extend_through_crossed_support

    runs = [(3351.4, 2067.0, 3370.4, 2380.0)]
    corridor = (3351.4, 2067.0, 3370.4, 2380.0)
    p23 = (3351.4, 2380.0, 3370.4, 2480.0)

    assert _extend_through_crossed_support(
        runs, corridor, [p23], horizontal=False,
    ) is None


def test_alcance_por_face_mede_distancia_do_corredor():
    """P13: V316 morre na face C e fica a 98 cm da face D."""
    from scripts.arete.qa_pil_approved_corpus import beams_within_reach_of_faces

    p13 = {"points": [[2477.4, 2661.0], [2496.4, 2661.0],
                      [2496.4, 2759.0], [2477.4, 2759.0]]}
    v316 = {
        "name": "V316", "dim": "19/120",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [[2477.4, 2759.0], [2496.4, 2759.0],
                        [2496.4, 3141.0], [2477.4, 3141.0]]},
        ]}},
    }

    alcance = beams_within_reach_of_faces(p13, [v316])

    # Pilar vertical: C ao norte (onde a viga encosta), D ao sul.
    assert "V316" in alcance["C"]
    assert "V316" not in alcance["D"]


def test_alcance_cobre_o_vao_da_regra_r1():
    """V313 para a 38 cm da face C de P29 — pela R1 do dono, chega nela."""
    from scripts.arete.qa_pil_approved_corpus import beams_within_reach_of_faces

    p29 = {"points": [[2037.9, 1963.0], [2061.9, 1963.0],
                      [2061.9, 2029.0], [2037.9, 2029.0]]}
    v313 = {
        "name": "V313", "dim": "19/55",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [[2040.4, 2067.0], [2059.4, 2067.0],
                        [2059.4, 2423.0], [2040.4, 2423.0]]},
        ]}},
    }

    assert "V313" in beams_within_reach_of_faces(p29, [v313])["C"]


def test_viga_do_outro_lado_do_pavimento_nao_alcanca_nada():
    from scripts.arete.qa_pil_approved_corpus import beams_within_reach_of_faces

    p9 = {"points": [[4649.9, 3103.0], [4668.9, 3103.0],
                     [4668.9, 3207.0], [4649.9, 3207.0]]}
    longe = {
        "name": "VF301", "dim": "19/66",
        "geometry": {"classified": {"seg_bottom": [
            {"points": [[1160, 3199], [1260, 3199], [1260, 3223], [1160, 3223]]},
        ]}},
    }

    assert all(not nomes for nomes in beams_within_reach_of_faces(p9, [longe]).values())


def _pilar(x0, y0, x1, y1):
    return {"points": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]}


def _viga(nome, x0, y0, x1, y1, dim="19/55"):
    return {
        "name": nome, "dim": dim,
        "geometry": {"classified": {"seg_bottom": [
            {"points": [(x0, y0), (x1, y0)]},
            {"points": [(x0, y1), (x1, y1)]},
        ]}},
    }


def test_travessia_exige_a_viga_estar_naquela_face():
    """Sem isso, qualquer viga do pavimento com o mesmo y contava como
    atravessando a face — a medida virava lista de nomes soltos."""
    from scripts.arete.qa_pil_approved_corpus import beams_crossing_into_pillar

    pilar = _pilar(2040.0, 2661.0, 2059.0, 2759.0)  # vertical, 19x98
    # Viga do outro lado do pavimento, mesma faixa de y.
    longe = _viga("V999", 100.0, 2700.0, 500.0, 2719.0)

    cruzam = beams_crossing_into_pillar(pilar, [longe])

    assert all("V999" not in nomes for nomes in cruzam.values())


def test_travessia_de_viga_que_entra_pela_face_conta():
    from scripts.arete.qa_pil_approved_corpus import beams_crossing_into_pillar

    pilar = _pilar(2040.0, 2661.0, 2059.0, 2759.0)
    # Horizontal cruzando a face A (oeste) e saindo pela B.
    atravessa = _viga("V302", 1600.0, 2661.0, 3000.0, 2680.0)

    cruzam = beams_crossing_into_pillar(pilar, [atravessa])

    assert "V302" in cruzam["A"] and "V302" in cruzam["B"]


def test_trecho_com_espessura_de_outra_viga_nao_prova_travessia():
    """V329: bbox de 68 cm para seção de 19, por ter absorvido a V304."""
    from scripts.arete.qa_pil_approved_corpus import beams_crossing_into_pillar

    pilar = _pilar(4533.0, 2242.0, 4552.0, 2460.0)
    inflada = _viga("V329", 4533.0, 2441.0, 4601.0, 2601.0, dim="19/60")

    cruzam = beams_crossing_into_pillar(pilar, [inflada])

    assert all("V329" not in nomes for nomes in cruzam.values())
