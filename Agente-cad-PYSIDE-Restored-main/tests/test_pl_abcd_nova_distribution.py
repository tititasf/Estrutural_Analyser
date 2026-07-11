"""Distribuição NOVA de painéis ABCD — genérica (sem hardcode de item)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from pl_abcd_visual_nova import (  # noqa: E402
    MODULO_PAINEL_NOVA_CM,
    distribute_paineis_nova,
    enrich_payload_for_abcd_nova,
    normalize_opening_y_rel,
    paineis_intervals_for_face,
    resolve_top_void_cm,
)


def test_distribute_modulos_122_plus_sobra():
    assert distribute_paineis_nova(302) == [122.0, 122.0, 58.0]
    assert distribute_paineis_nova(278) == [122.0, 122.0, 34.0]
    assert distribute_paineis_nova(122) == [122.0]
    assert distribute_paineis_nova(100) == [100.0]
    assert distribute_paineis_nova(182, split_modules=False) == [182.0]


def test_intervals_long_vs_short_faces():
    # A: pilha até o topo
    assert paineis_intervals_for_face(
        face_id="A", height_cm=304, h1_cm=2
    ) == [122.0, 122.0, 58.0]
    # C passante com void 120
    assert paineis_intervals_for_face(
        face_id="C", height_cm=304, h1_cm=2, top_void_cm=120, has_side_openings=False
    ) == [182.0]
    # C com abertura lateral: pilha completa
    assert paineis_intervals_for_face(
        face_id="C", height_cm=304, h1_cm=2, top_void_cm=120, has_side_openings=True
    ) == [122.0, 122.0, 58.0]


def test_top_void_from_n2_residual_and_beam_dim():
    # residual intervals
    tv = resolve_top_void_cm(
        face_id="C",
        height_cm=280,
        h1_cm=2,
        existing_intervals=[158.0],
    )
    assert abs(tv - 120.0) < 0.1
    # viga passante dim 19/120
    tv2 = resolve_top_void_cm(
        face_id="C",
        height_cm=304,
        h1_cm=2,
        face_data={
            "fontes_n1": {
                "passa": ["Viga: V309  ·  dim: 19/120  ·  corre ao longo da face C"]
            }
        },
    )
    assert abs(tv2 - 120.0) < 0.1


def test_opening_y_rel_preserves_mid_openings():
    # abertura no meio (não colada no topo) — preserva y_rel
    ab = {"lado": "direito", "altura": 59.0, "y_rel": 205.0}
    y = normalize_opening_y_rel(ab, height_cm=280, h1_cm=2)
    assert abs(y - 205.0) < 0.1
    # colada no topo — alinha
    ab2 = {"lado": "direito", "altura": 124.0, "y_rel": 177.8}
    y2 = normalize_opening_y_rel(ab2, height_cm=304, h1_cm=2)
    assert abs(y2 - (304 - 2 - 124)) < 0.5


def test_enrich_any_item_not_only_p1():
    """Dois pilares diferentes → intervals coerentes com a própria altura."""
    p_a = {
        "nome": "PX",
        "altura": 304.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "abertura_A_1": {"lado": "direito", "largura": 11.0, "altura": 124.0, "y_rel": 178.0},
        "paineis_intervals_C": [182.0],
        "modo_distribuicao": "NOVA",
        "_sa_mode_contract": {"faces": {"A": {}, "B": {}, "C": {}, "D": {}}},
    }
    p_b = {
        "nome": "PY",
        "altura": 280.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "abertura_A_1": {"lado": "direito", "largura": 11.0, "altura": 124.0, "y_rel": 140.0},
        "paineis_intervals_C": [158.0],
        "modo_distribuicao": "NOVA",
        "_sa_mode_contract": {"faces": {"A": {}, "B": {}, "C": {}, "D": {}}},
    }
    ea = enrich_payload_for_abcd_nova(dict(p_a))
    eb = enrich_payload_for_abcd_nova(dict(p_b))
    assert ea["paineis_intervals_A"] == [122.0, 122.0, 58.0]
    assert eb["paineis_intervals_A"] == [122.0, 122.0, 34.0]
    # C: void do residual N2 (não hardcode 120)
    assert ea["paineis_intervals_C"] == [182.0]
    assert eb["paineis_intervals_C"] == [158.0]
    # y_rel mid preservado em PY
    assert abs(float(eb["abertura_A_1"]["y_rel"]) - 140.0) < 0.1
    assert ea.get("_pl_nova_enriched") is True
    assert MODULO_PAINEL_NOVA_CM == 122.0


def test_prepare_pj_called_from_motor_zone():
    """generate_pilar_zone enriquece no modo NOVA (smoke)."""
    from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone

    pj = {
        "nome": "PZ",
        "comprimento": 66,
        "largura": 19,
        "altura": 304.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "modo_distribuicao": "NOVA",
        "paineis_intervals_A": [50.0],  # lixo de propósito — deve ser reescrito
        "paineis_intervals_C": [182.0],
    }
    doc = setup_doc()
    n = generate_pilar_zone(doc.modelspace(), pj, "abcd", visual_mode="NOVA")
    assert n > 10
    assert pj["paineis_intervals_A"] == [122.0, 122.0, 58.0]


def test_dual_laje_infers_rebaixo_forma_strip():
    """Dual + vazio laje + aberturas no topo → rebaixo = filete forma (7cm)."""
    from pl_abcd_visual_nova import FORMA_STRIP_ACIMA_LAJE_CM

    pj = {
        "nome": "PREB",
        "altura": 304.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "abertura_B_1": {
            "lado": "esquerdo",
            "largura": 11.0,
            "altura": 124.0,
            "y_rel": 178.0,
        },
        "abertura_B_2": {
            "lado": "direito",
            "largura": 29.0,
            "altura": 124.0,
            "y_rel": 178.0,
        },
        "modo_distribuicao": "NOVA",
        "_sa_mode_contract": {
            "faces": {
                "B": {
                    "fontes_n1": {
                        "lajes": ["Laje: L301  ·  esp: 12cm  ·  N: 852.12"]
                    }
                }
            }
        },
    }
    out = enrich_payload_for_abcd_nova(pj)
    assert float(out["vazio_laje_B"]) == 14.0
    assert abs(float(out["rebaixo_laje_B"]) - FORMA_STRIP_ACIMA_LAJE_CM) < 0.1


def test_dual_laje_mid_y_rel_gets_p1_pattern_any_item():
    """P2-like: dual com y_rel N2 no meio + vazio → rebaixo 7 e aberturas no topo.

    Garante que o padrão do P1 não fica preso ao y_rel 178 do item treino.
    """
    from pl_abcd_visual_nova import FORMA_STRIP_ACIMA_LAJE_CM

    pj = {
        "nome": "P2LIKE",
        "altura": 280.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        # N2 deixou gap = vazio (14cm) sob o topo — motor deve colar no topo
        "abertura_A_1": {
            "lado": "direito",
            "largura": 11.0,
            "altura": 124.0,
            "y_rel": 140.0,
        },
        "abertura_A_2": {
            "lado": "esquerdo",
            "largura": 34.0,
            "altura": 124.0,
            "y_rel": 140.0,
        },
        "modo_distribuicao": "NOVA",
        "_sa_mode_contract": {
            "faces": {
                "A": {
                    "fontes_n1": {
                        "lajes": ["Laje: L301  ·  esp: 12cm  ·  N: 852.12"]
                    }
                }
            }
        },
        "_pl_nova_enriched": True,  # flag stale NÃO deve impedir re-enrich no motor
    }
    out = enrich_payload_for_abcd_nova(pj)
    assert float(out["vazio_laje_A"]) == 14.0
    assert abs(float(out["rebaixo_laje_A"]) - FORMA_STRIP_ACIMA_LAJE_CM) < 0.1
    # coladas no topo: y_rel = height - h1 - altura = 280 - 2 - 124 = 154
    assert abs(float(out["abertura_A_1"]["y_rel"]) - 154.0) < 0.5
    assert abs(float(out["abertura_A_2"]["y_rel"]) - 154.0) < 0.5
    assert out["paineis_intervals_A"] == [122.0, 122.0, 34.0]


def test_prepare_pj_reenriches_stale_flag():
    """Motor re-aplica regras mesmo com _pl_nova_enriched e intervals errados."""
    from gerar_pl_dxf_stog import _prepare_pj_for_visual

    pj = {
        "nome": "PSTALE",
        "altura": 280.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "paineis_intervals_A": [10.0, 10.0],  # stale
        "rebaixo_laje_A": 0.0,
        "abertura_A_1": {
            "lado": "direito",
            "largura": 11.0,
            "altura": 124.0,
            "y_rel": 140.0,
        },
        "abertura_A_2": {
            "lado": "esquerdo",
            "largura": 34.0,
            "altura": 124.0,
            "y_rel": 140.0,
        },
        "_pl_nova_enriched": True,
        "_sa_mode_contract": {
            "faces": {
                "A": {
                    "fontes_n1": {
                        "lajes": ["Laje: L301  ·  esp: 12cm  ·  N: 852.12"]
                    }
                }
            }
        },
    }
    out = _prepare_pj_for_visual(pj, "NOVA")
    assert out["paineis_intervals_A"] == [122.0, 122.0, 34.0]
    assert float(out["rebaixo_laje_A"]) == 7.0
    assert abs(float(out["abertura_A_1"]["y_rel"]) - 154.0) < 0.5


def test_hatch_ar_conc_scale_dense():
    """AR-CONC scale ~0.05 (não 1.0 ralo nem 0.03 chapado)."""
    from pl_abcd_visual_nova import HATCH_AR_CONC_SCALE, draw_void_hatches
    from gerar_pl_dxf_stog import setup_doc

    assert 0.04 <= HATCH_AR_CONC_SCALE <= 0.08
    doc = setup_doc()
    msp = doc.modelspace()
    paths = [[(0, 0), (11, 0), (11, 124), (0, 124)]]
    draw_void_hatches(msp, paths)
    scales = []
    for e in msp:
        if e.dxftype() == "HATCH":
            scales.append(float(e.dxf.pattern_scale))
    assert scales and all(0.035 <= s <= 0.12 for s in scales)


def test_paineis_unidos_expand_mesh_and_n3_total():
    """100+22 no 1º módulo → malha [100,22,...] + total N3 122."""
    from pl_abcd_visual_nova import (
        parse_paineis_unidos,
        expand_intervals_with_unidos,
        DIM_LVL1_OFF,
        DIM_LVL2_OFF,
        DIM_LVL3_OFF,
    )

    assert DIM_LVL1_OFF < DIM_LVL2_OFF < DIM_LVL3_OFF
    payload = {
        "paineis_intervals_A": [122.0, 122.0, 58.0],
        "paineis_unidos_A": [{"interval_index": 0, "parts": [100.0, 22.0]}],
    }
    u = parse_paineis_unidos(payload, "A")
    assert len(u) == 1
    mesh, totals = expand_intervals_with_unidos([122.0, 122.0, 58.0], u)
    assert mesh == [100.0, 22.0, 122.0, 58.0]
    assert len(totals) == 1
    assert abs(totals[0]["total"] - 122.0) < 0.1
    assert totals[0]["parts"] == [100.0, 22.0]


def test_n3_generates_joined_panel_line_and_dims():
    """Com paineis_unidos no JSON, N3 desenha H extra + cotas N2 parts + N3 total."""
    from gerar_pl_dxf_stog import setup_doc, generate_pilar_zone
    import ezdxf

    pj = {
        "nome": "PJOIN",
        "comprimento": 66,
        "largura": 19,
        "altura": 304.0,
        "h1_A": 2.0,
        "h1_B": 2.0,
        "h1_C": 2.0,
        "h1_D": 2.0,
        "modo_distribuicao": "NOVA",
        "paineis_intervals_A": [122.0, 122.0, 58.0],
        "paineis_intervals_B": [122.0, 122.0, 58.0],
        "paineis_intervals_C": [182.0],
        "paineis_intervals_D": [182.0],
        "paineis_unidos_A": [{"interval_index": 0, "parts": [100.0, 22.0]}],
    }
    doc = setup_doc()
    n = generate_pilar_zone(doc.modelspace(), pj, "abcd", visual_mode="NOVA")
    assert n > 10
    # H em y = y_bot + h1 + 100 (junta 100|22 do 1º módulo)
    # y_top gen = base_y - 100; y_bot = y_top - 304; com row 0: y_top=-100, y_bot=-404
    # H after h1 at -402; +100 = -302
    ys_h = []
    dims_m = []
    for e in doc.modelspace():
        if e.dxftype() == "LINE" and e.dxf.layer in ("Painéis", "Paineis"):
            y1, y2 = float(e.dxf.start.y), float(e.dxf.end.y)
            if abs(y1 - y2) < 0.5:
                ys_h.append(round(y1, 1))
        if e.dxftype() == "DIMENSION":
            try:
                dims_m.append(round(e.get_measurement(), 1))
            except Exception:
                pass
    assert any(abs(y + 302.0) < 1.0 for y in ys_h), f"missing join H near -302; got {sorted(set(ys_h))[:20]}"
    assert 100.0 in dims_m or any(abs(m - 100) < 0.6 for m in dims_m)
    assert 22.0 in dims_m or any(abs(m - 22) < 0.6 for m in dims_m)
    # total 122 still present (N3 and/or other modules)
    assert sum(1 for m in dims_m if abs(m - 122) < 0.6) >= 1


def test_dual_void_rects_not_full_width():
    """Dual B: hatch só aberturas + miolo vazio laje — nunca 88 full sobre painel."""
    from pl_abcd_visual_nova import void_rects_for_face

    openings = [
        {"lado": "esquerdo", "larg": 11.0, "y_bot": -200.0, "y_top": -76.0},
        {"lado": "direito", "larg": 29.0, "y_bot": -200.0, "y_top": -76.0},
    ]
    rects = void_rects_for_face(
        x_left=323.0,
        x_right=411.0,
        openings=openings,
        rebaixo_cm=7.0,
        vazio_laje_cm=14.0,
        y_face_top=-76.0,
        y_panel_content_top=-97.0,
    )
    widths = sorted(round(w, 1) for _, _, w, _ in rects)
    # 11 + 29 + 48 (miolo), sem 88
    assert 11.0 in widths
    assert 29.0 in widths
    assert 48.0 in widths
    assert not any(abs(w - 88.0) < 1.0 for w in widths)
    # miolo void height 14
    miolo = [h for _, _, w, h in rects if abs(w - 48) < 1]
    assert miolo and abs(miolo[0] - 14.0) < 0.5
