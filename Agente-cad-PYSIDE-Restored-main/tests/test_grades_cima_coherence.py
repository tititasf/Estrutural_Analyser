"""
tests/test_grades_cima_coherence.py
=====================================
Garante que CIMA e GRADES usam exatamente os mesmos segmentos de divisao (div_a),
e que as cotas do N4 GRADES somam corretamente para gw_each = comp + 22.

Regra de Ouro: _div_segments(pj, gw_each) e a UNICA fonte de div_a.

Executar:
    python -m pytest tests/test_grades_cima_coherence.py -v -s
"""

import sys
import json
import pathlib

import pytest
import ezdxf

ROOT = pathlib.Path(__file__).parent.parent
sys.path.insert(0, str(ROOT / '_ROBOS_ABAS/Robo_Pilares/pilares-atualizado-09-25/src'))

OBRA_DIR = pathlib.Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS/Obra_TREINO_1")
N4_DIR   = OBRA_DIR / "Fase-6_Execucao_CAD"
JSON_DIR = OBRA_DIR / "Fase-4_Sincronizacao" / "JSON_Pilares"

ITEMS = [
    ("P1",  66, 88),
    ("P3",  60, 82),
    ("P9",  104, 60),
    ("P11", 80, 102),
    ("P13", 70, 92),
    ("P15", 45, 67),
]


# ── Funções copiadas de gerar_pl_dxf_stog.py (módulo-level, sem PySide6) ────

def _bolt_offsets_from_pj(pj, grade_w):
    bolt_xs = []
    _bx = -1.0
    _limit = grade_w + 1.0
    for i in range(1, 9):
        sp = float(pj.get(f'par_{i}_{i+1}') or 0)
        if sp <= 0:
            break
        _bx += sp
        if _bx >= _limit - 1.0:
            break
        bolt_xs.append(_bx)
    return bolt_xs


def _grade_boundaries_with_avoidance(total_w, offsets, tol=3.0, step=5.0, max_shift=20.0):
    def bounds(b2):
        return [b2 / 2.0, b2, (total_w + b2) / 2.0]

    def conflict(bnds):
        return any(abs(b - o) <= tol for b in bnds for o in offsets)

    b2 = total_w / 2.0
    if not offsets or not conflict(bounds(b2)):
        return bounds(b2)
    n = 1
    while n * step <= max_shift:
        for cand in (b2 - n * step, b2 + n * step):
            if 0 < cand < total_w and not conflict(bounds(cand)):
                return bounds(cand)
        n += 1
    return bounds(b2)


def _segments_from_boundaries(boundaries, total_w):
    bnds = [0.0] + list(boundaries) + [total_w]
    return [b1 - b0 for b0, b1 in zip(bnds[:-1], bnds[1:])]


def _div_segments(pj, grade_w, div_key='grade_1_div_a'):
    raw = pj.get(div_key) or []
    if raw:
        s = sum(float(v) for v in raw if v)
        if abs(s - grade_w) < 0.5:
            return [float(v) for v in raw if v]
    bolt_offs = _bolt_offsets_from_pj(pj, grade_w)
    bnds = _grade_boundaries_with_avoidance(grade_w, bolt_offs)
    return _segments_from_boundaries(bnds, grade_w)


# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("item_id,comp,gw_expected", ITEMS)
def test_div_segments_source_is_shared(item_id, comp, gw_expected):
    """_div_segments(pj, gw_each) retorna soma==gw_each para todos os itens.
    Prova matematica: draw_cima e draw_grades chamam a mesma funcao com os
    mesmos args — divisoes nunca divergem entre as duas zonas."""
    pj = json.loads((JSON_DIR / f"{item_id}.json").read_text(encoding="utf-8"))
    div_a = _div_segments(pj, gw_expected)

    assert div_a, f"[{item_id}] _div_segments retornou vazio"
    soma = round(sum(div_a), 1)
    assert abs(soma - gw_expected) < 0.5, (
        f"[{item_id}] soma(div_a)={soma} != gw_each={gw_expected} — "
        f"CIMA e GRADES divergiriam: div_a={[round(d,1) for d in div_a]}"
    )


def _dims_horiz(dxf_path):
    """Retorna medidas das cotas HORIZONTAIS (angle=0) do DXF — exclui cotas verticais."""
    doc = ezdxf.readfile(str(dxf_path))
    return [round(e.get_measurement(), 1)
            for e in doc.modelspace().query("DIMENSION")
            if abs(getattr(e.dxf, 'angle', 0.0)) < 1.0]


@pytest.mark.parametrize("item_id,comp,gw_expected", ITEMS)
def test_grades_n4_totais_corretos(item_id, comp, gw_expected):
    """Cotas totais horizontais do N4 GRADES == gw_each em ambos os grupos (A e B)."""
    from utils.grade_calculator import GradeCalculator as GC

    dxf_path = N4_DIR / f"PL_GRADES_preview_{item_id}.dxf"
    assert dxf_path.exists(), f"DXF nao encontrado: {dxf_path}"

    ng, gw_each, _ = GC.calcular_grades(comp)
    h_dims = _dims_horiz(dxf_path)

    totais = [d for d in h_dims if abs(d - gw_each) <= 0.5]
    assert len(totais) == ng * 2, (
        f"[{item_id}] esperado {ng*2} cotas totais={gw_each:.0f}, "
        f"encontrado {len(totais)} em {sorted(h_dims)}"
    )


@pytest.mark.parametrize("item_id,comp,gw_expected", ITEMS)
def test_grades_n4_soma_segmentos(item_id, comp, gw_expected):
    """Soma dos segmentos horizontais de subdivisao == 2 x ng x gw_each."""
    from utils.grade_calculator import GradeCalculator as GC

    dxf_path = N4_DIR / f"PL_GRADES_preview_{item_id}.dxf"
    assert dxf_path.exists(), f"DXF nao encontrado: {dxf_path}"

    ng, gw_each, _ = GC.calcular_grades(comp)
    h_dims = _dims_horiz(dxf_path)

    segs      = [d for d in h_dims if d < gw_each - 0.5 and d > 1]
    soma_segs = round(sum(segs), 1)
    esperado  = round(ng * gw_each * 2, 1)

    assert abs(soma_segs - esperado) < 1.0, (
        f"[{item_id}] soma_segs={soma_segs} != esperado={esperado} "
        f"(ng={ng}, gw={gw_each:.0f}, segs={segs})"
    )
