"""SA: 2 vigas que passam por esquina + chegadas; sem contorno."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.core.pillar_face_beams import enrich_pillar_report_with_beams  # noqa: E402


def test_face_beams_two_passa_slots_by_corner():
    """Pilar vertical + vigas H no topo → face C com passa por canto CA/CB."""
    report = {
        "P1": {
            "name": "P1",
            "points": [(0, 0), (40, 0), (40, 80), (0, 80)],
            "lajes": [
                {"side": "A", "laje": "L1"},
                {"side": "B", "laje": "L2"},
            ],
        }
    }
    beams = [
        {
            "name": "VF_TOP_ESQ",
            "dim": "19x40",
            # parede inferior da viga em y=80 = face C do pilar
            "points": [(-20, 80), (20, 80), (20, 100), (-20, 100)],
            "is_h": True,
        },
        {
            "name": "VF_TOP_DIR",
            "dim": "19x50",
            "points": [(20, 80), (60, 80), (60, 100), (20, 100)],
            "is_h": True,
        },
        {
            "name": "VF_BASE",
            "dim": "20x40",
            # parede superior da viga em y=0 = face D
            "points": [(-10, -20), (50, -20), (50, 0), (-10, 0)],
            "is_h": True,
        },
    ]
    enrich_pillar_report_with_beams(report, beams)
    fb = report["P1"].get("face_beams") or {}
    assert "C" in fb and "D" in fb
    assert fb["C"]["corner_esq"] == "CA"
    assert fb["C"]["corner_dir"] == "CB"
    # Topo: vigas só de um lado do eixo do pilar → behavior=para (chegada),
    # não passa (eixo não atravessa as duas faces). Aparecem em para[] e/ou
    # passa se forem passantes; o inventário multi-face deve citá-las.
    c_esq = (fb["C"].get("passa_esq") or {}).get("name")
    c_dir = (fb["C"].get("passa_dir") or {}).get("name")
    para_c = {p["name"] for p in (fb["C"].get("para") or [])}
    names_c = {c_esq, c_dir} | para_c - {None}
    assert names_c & {"VF_TOP_ESQ", "VF_TOP_DIR"}
    # Uma viga não ocupa esq e dir ao mesmo tempo
    if c_esq and c_dir:
        assert c_esq != c_dir
    d_names = {
        (fb["D"].get("passa_esq") or {}).get("name"),
        (fb["D"].get("passa_dir") or {}).get("name"),
    } | {p["name"] for p in (fb["D"].get("para") or [])} - {None}
    assert "VF_BASE" in d_names or any(
        (le.get("viga") or {}).get("name") == "VF_BASE"
        for le in report["P1"].get("lajes") or []
    )


def test_face_beams_passante_fills_slot():
    """Viga passante horizontal preenche algum slot passa_*."""
    report = {
        "P9": {
            "points": [(0, 0), (30, 0), (30, 60), (0, 60)],
            "lajes": [],
        }
    }
    beams = [
        {
            "name": "VPASS",
            "dim": "15x40",
            # atravessa o pilar em Y: paredes y=0 e y=60 alinham A/B? 
            # faces longas A/B são verticais em x=0 e x=30
            # viga H atravessando: paredes em y=25 e y=40 — não alinha face.
            # Alinha faces longas se paredes x do beam tocam... beam is H.
            # Passante: beam_min < pillar_min and beam_max > pillar_max no eixo.
            # is_h True → eixo X; beam x -40..70, pillar 0..30 → passa.
            # Face hit: wall y of beam vs face H of C/D
            "points": [(-40, 0), (70, 0), (70, 15), (-40, 15)],
            "is_h": True,
        }
    ]
    enrich_pillar_report_with_beams(report, beams)
    fb = report["P9"].get("face_beams") or {}
    for fid in "ABCD":
        assert fid in fb
        assert "passa_esq" in fb[fid]
        assert "passa_dir" in fb[fid]
        assert "para" in fb[fid]
    filled = [
        fb[f][s]
        for f in "ABCD"
        for s in ("passa_esq", "passa_dir")
        if fb[f].get(s)
    ]
    assert filled, "viga passante deveria preencher algum slot passa_*"
    assert report["P9"].get("viga_que_passa")
    # mesmo passante não duplica esq+dir na mesma face
    for fid, slots in fb.items():
        esq = (slots.get("passa_esq") or {}).get("name")
        dire = (slots.get("passa_dir") or {}).get("name")
        if esq and dire:
            assert esq != dire, f"face {fid} duplicou {esq}"


def test_face_beams_para_goes_to_chegada_not_passa():
    """Viga que PARA no pilar → para[] (chegada), não passa_esq/dir."""
    report = {
        "P2": {
            "points": [(0, 0), (40, 0), (40, 80), (0, 80)],
            "lajes": [],
        }
    }
    beams = [
        {
            "name": "V_CHEGA",
            "dim": "14/50",
            # eixo H: começa dentro/no pilar e sai só para a direita
            # pillar x 0..40; beam x 10..100 → endpoint no pilar + passa_right only
            "points": [(10, 70), (100, 70), (100, 90), (10, 90)],
            "is_h": True,
        }
    ]
    enrich_pillar_report_with_beams(report, beams)
    fb = report["P2"]["face_beams"]
    passa_names = {
        (fb[f].get(s) or {}).get("name")
        for f in "ABCD"
        for s in ("passa_esq", "passa_dir")
    } - {None}
    assert "V_CHEGA" not in passa_names
    para_names = {
        p["name"] for f in "ABCD" for p in (fb[f].get("para") or [])
    }
    assert "V_CHEGA" in para_names
    assert report["P2"].get("viga_que_para")


def test_beam_stopping_on_short_face_materializes_corner_openings_on_long_faces():
    report = {
        "P35": {
            "name": "P35",
            "points": [(100, 0), (160, 0), (160, 19), (100, 19)],
            "lajes": [],
        }
    }
    beams = [{
        "name": "V308",
        "dim": "19/55",
        # Viga horizontal termina em C e suas paredes coincidem com A/B.
        "points": [(0, 0), (100, 0), (100, 19), (0, 19)],
        "is_h": True,
    }]

    enrich_pillar_report_with_beams(report, beams)

    faces = report["P35"]["face_beams"]
    assert faces["A"]["passa_esq"] == {
        "name": "V308", "dim": "19/55", "corner": "AC", "behavior": "para",
    }
    assert faces["B"]["passa_dir"] == {
        "name": "V308", "dim": "19/55", "corner": "BC", "behavior": "para",
    }
    assert {entry["name"] for entry in faces["C"]["para"]} == {"V308"}


def test_multi_run_beam_is_arrival_not_fake_passante():
    """Viga multi-trecho: trecho que nasce na face B é chegada; fragmentos
    distantes não podem fundir num corredor fictício que 'passa' na face D.

    Reprodução geométrica do caso V328×P35 (13_PAV): trecho N-S nasce no topo
    do pilar horizontal e sobe; outros fragmentos ficam ao sul, deslocados.
    O bbox global cruzaria a banda do pilar ao lado da face D.
    """
    report = {
        "P35": {
            "name": "P35",
            "points": [(4492.4, 1963.0), (4552.4, 1963.0),
                       (4552.4, 1982.0), (4492.4, 1982.0)],
            "lajes": [],
        }
    }
    beams = [{
        "name": "V328",
        "dim": "19/55",
        "geometry": {
            "classified": {
                "seg_bottom": [
                    [[4552.4, 1982.0], [4552.4, 2242.0]],
                    [[4533.4, 1982.0], [4533.4, 2242.0]],
                    [[4533.4, 1673.2], [4552.4, 1692.2]],
                    [[4544.2, 1655.1], [4601.9, 1657.7]],
                ],
            }
        },
    }]

    enrich_pillar_report_with_beams(report, beams)

    entry = report["P35"]
    assert not entry.get("viga_que_passa")
    assert {b["name"] for b in entry.get("viga_que_para") or []} == {"V328"}
    fb = entry["face_beams"]
    passa_names = {
        (fb[f].get(s) or {}).get("name")
        for f in "ABCD"
        for s in ("passa_esq", "passa_dir")
    } - {None}
    assert "V328" not in passa_names
    arrivals_b = fb["B"]["para"]
    assert [p["name"] for p in arrivals_b] == ["V328"]
    # canto geométrico: o trecho cobre a extremidade D da face B
    assert arrivals_b[0]["corner"] == "BD"
    assert fb["D"]["para"] == []


def test_head_on_arrival_covering_short_face_is_central():
    """Chegada de frente que cobre a face curta inteira → slot central FF."""
    report = {
        "P35": {
            "name": "P35",
            "points": [(100, 0), (160, 0), (160, 19), (100, 19)],
            "lajes": [],
        }
    }
    beams = [{
        "name": "V308",
        "dim": "19/55",
        "geometry": {
            "classified": {
                "seg_bottom": [
                    [[0.0, 0.0], [100.0, 0.0]],
                    [[0.0, 19.0], [100.0, 19.0]],
                ],
            }
        },
    }]

    enrich_pillar_report_with_beams(report, beams)

    fb = report["P35"]["face_beams"]
    assert [p["corner"] for p in fb["C"]["para"]] == ["CC"]


def test_beam_section_dim_rejects_names():
    from src.core.pillar_face_beams import (
        clean_beam_section_dim,
        is_beam_section_dim,
    )

    assert is_beam_section_dim("14/50")
    assert is_beam_section_dim("19x40")
    assert not is_beam_section_dim("V327")
    assert not is_beam_section_dim("P35")
    assert not is_beam_section_dim("L325")
    assert clean_beam_section_dim("VF301") == ""
    assert clean_beam_section_dim("19/55") == "19/55"


def test_beam_section_dim_prefers_own_bottom_ficha_over_spatial_text():
    """Cota espacial 100/19 não pode vencer a ficha FV 19/55 da própria viga."""
    from src.core.pillar_face_beams import beam_section_dim

    beam = {
        "dim": "100/19",
        "fields": {
            "dimensao": "100/19",
            "viga_fundo_seg_1_dim": "100/19",
        },
        "links": {
            "viga_segs": {
                "seg_bottom": [
                    {"ficha": {"largura_total_fundo": "19", "altura_total": "55"}},
                    {"ficha": {"largura_total_fundo": 19, "altura_total": 55}},
                ]
            }
        },
    }
    assert beam_section_dim(beam) == "19/55"


def test_beam_section_dim_uses_direct_fundo_label_when_ficha_is_not_materialized():
    from src.core.pillar_face_beams import beam_section_dim

    beam = {
        "fields": {"dimensao": "100/19"},
        "links": {
            "viga_segs": {"seg_bottom": []},
            "viga_fundo_seg_1_dim": {"label": [{"text": "19/55"}]},
        },
    }
    assert beam_section_dim(beam) == "19/55"


def test_beam_axis_prefers_current_bottom_runs_over_stale_is_h():
    from src.core.pillar_face_beams import beam_axis_is_horizontal

    beam = {
        "is_h": False,
        "geometry": {
            "classified": {
                "bottom_runs": [{"is_h": True, "coords": [[0, 100]]}],
            }
        },
    }
    assert beam_axis_is_horizontal(beam) is True


def test_reconcile_fundo_facts_repairs_stale_dim_height_and_axis():
    from src.core.pillar_face_beams import reconcile_beam_fundo_facts

    beam = {
        "is_h": False,
        "dim": "100/19",
        "fields": {
            "dimensao": "100/19",
            "altura_h1": 415,
            "viga_fundo_seg_1_dim": "100/19",
        },
        "geometry": {"classified": {"bottom_runs": [{"is_h": True}]}},
        "links": {
            "viga_segs": {
                "seg_bottom": [
                    {"ficha": {"largura_total_fundo": 19, "altura_total": 55}},
                ]
            }
        },
    }
    assert reconcile_beam_fundo_facts([beam]) == 1
    assert beam["dim"] == "19/55"
    assert beam["fields"]["dimensao"] == "19/55"
    assert beam["fields"]["viga_fundo_seg_1_dim"] == "19/55"
    assert beam["fields"]["altura_h1"] == 55.0
    assert beam["is_h"] is True


def test_materialize_face_beams_clears_stale_slots_but_keeps_validated_human_field():
    """Merge antigo nao pode manter V327 quando topologia so confirma V328."""
    from src.core.pillar_face_beams import materialize_face_beams_in_pillars

    pillar = {
        "name": "P35",
        "p_sA_v_passa_esq_n": "V327",
        "p_sA_v_passa_esq_d": "14/50",
        "p_sD_v_passa_dir_n": "V327",
        "p_sD_v_passa_dir_d": "14/50",
        "p_sD_v_passa_esq_n": "VANTIGA",
        "p_sD_v_passa_esq_d": "99/99",
        "sides_data": {
            "A": {"v_passa_esq_n": "V327", "v_passa_esq_d": "14/50"},
            "D": {
                "v_passa_esq_n": "VANTIGA", "v_passa_esq_d": "99/99",
                "v_passa_dir_n": "V327", "v_passa_dir_d": "14/50",
            },
        },
        "links": {
            "p_sA_v_passa_esq_n": {"old": True},
            "p_sD_v_passa_dir_n": {"old": True},
        },
    }
    report = {
        "P35": {
            "face_beams": {
                face: {"passa_esq": None, "passa_dir": None, "para": []}
                for face in "ABCD"
            }
        }
    }
    report["P35"]["face_beams"]["D"]["passa_esq"] = {
        "name": "V328", "dim": "19/55",
    }

    assert materialize_face_beams_in_pillars([pillar], report, item_names={"P35"}) == 1
    assert "p_sA_v_passa_esq_n" not in pillar
    assert "v_passa_esq_n" not in pillar["sides_data"]["A"]
    assert pillar["p_sD_v_passa_esq_n"] == "V328"
    assert pillar["p_sD_v_passa_esq_d"] == "19/55"
    assert "p_sD_v_passa_dir_n" not in pillar
    assert "v_passa_dir_n" not in pillar["sides_data"]["D"]

    # Um campo humano explicitamente validado continua soberano.
    pillar["validated_fields"] = ["p_sA_v_passa_esq_n"]
    pillar["p_sA_v_passa_esq_n"] = "V_HUMANA"
    pillar["sides_data"]["A"]["v_passa_esq_n"] = "V_HUMANA"
    materialize_face_beams_in_pillars([pillar], report, item_names={"P35"})
    assert pillar["p_sA_v_passa_esq_n"] == "V_HUMANA"


def test_materialized_face_beam_link_preserves_geometric_evidence():
    from src.core.pillar_face_beams import materialize_face_beams_in_pillars

    pillar = {"name": "P35", "sides_data": {}, "links": {}}
    evidence = [{
        "type": "line",
        "points": [[1.0, 2.0], [3.0, 4.0]],
        "source": "pillar_face_beams_topology",
    }]
    report = {"P35": {"face_beams": {
        face: {"passa_esq": None, "passa_dir": None, "para": []}
        for face in "ABCD"
    }}}
    report["P35"]["face_beams"]["A"]["passa_esq"] = {
        "name": "V308",
        "dim": "19/55",
        "evidence_segments": evidence,
    }

    assert materialize_face_beams_in_pillars([pillar], report) == 1
    name_link = pillar["links"]["p_sA_v_passa_esq_n"]
    dim_link = pillar["links"]["p_sA_v_passa_esq_d"]
    assert name_link["geometry"] == evidence
    assert dim_link["geometry"] == evidence
    assert name_link["evidence_source"] == "beam_bottom_geometry"


def test_bbox_from_classified_segs():
    from src.core.pillar_face_beams import beam_bbox_from_entity

    beam = {
        "name": "V327",
        "geometry": {
            "classified": {
                "seg_side_a": [
                    [[0.0, 0.0], [100.0, 0.0]],
                    [[100.0, 0.0], [100.0, 20.0]],
                ],
            }
        },
    }
    bb = beam_bbox_from_entity(beam)
    assert bb is not None
    assert bb[0] == 0.0 and bb[2] == 100.0


def test_detail_card_has_passa_esquina_not_contorno():
    """UI: labels de esquina e sem contorno (inspeção estática do source)."""
    src = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "ui"
        / "widgets"
        / "detail_card.py"
    ).read_text(encoding="utf-8")
    assert "Vigas que Passam — Esquina" in src
    assert "passa_esq" in src and "passa_dir" in src
    assert "Viga de Contorno Esquerda" not in src
    assert "Viga de Contorno Direita" not in src
    assert "Viga de Chegada 1" in src
    assert "Viga de Chegada 3" in src
