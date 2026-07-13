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
