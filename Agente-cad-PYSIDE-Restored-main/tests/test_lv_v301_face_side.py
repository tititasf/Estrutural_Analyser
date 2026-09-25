"""V301: unidades da coluna A nao podem sair como face B."""
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "arete"))

from motor_reverso_lv import extrair_ficha_lateral_viga  # noqa: E402
from gerar_lv_dxf_stog import prepare_n4_face_units  # noqa: E402


def _recorte_v301() -> str:
    db = Path(r"D:/Agente-cad-PYSIDE/project_data.vision")
    if not db.is_file():
        pytest.skip("DB de producao ausente")
    with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
        row = conn.execute(
            """
            SELECT recorte_path FROM reverse_eng_recortes
             WHERE UPPER(elemento_id)='V301' AND UPPER(classe)='LV'
             ORDER BY id DESC LIMIT 1
            """
        ).fetchone()
    if not row or not Path(row[0]).is_file():
        pytest.skip("recorte N2 V301 ausente")
    return str(row[0])


def _by_side(units):
    out = {"A": [], "B": []}
    for u in units or []:
        s = str(u.get("side") or "").upper()
        if s in out:
            out[s].append(u)
    return out


def test_v301_b_does_not_clone_a_column():
    ficha = extrair_ficha_lateral_viga(_recorte_v301(), "V301_A")
    by = _by_side(ficha.get("face_units") or [])
    assert len(by["A"]) == 8
    assert len(by["B"]) == 8

    def bbox(u):
        b = u.get("bbox") or {}
        return (
            float(b.get("x_left") or 0),
            float(b.get("x_right") or 0),
            float(b.get("y_bot") or 0),
            float(b.get("y_top") or 0),
        )

    for bu in by["B"]:
        bx0, bx1, by0, by1 = bbox(bu)
        bw = max(1.0, bx1 - bx0)
        bh = max(1.0, by1 - by0)
        for au in by["A"]:
            ax0, ax1, ay0, ay1 = bbox(au)
            ox = min(bx1, ax1) - max(bx0, ax0)
            oy = min(by1, ay1) - max(by0, ay0)
            aw = max(1.0, ax1 - ax0)
            ah = max(1.0, ay1 - ay0)
            assert not (
                ox > 0.80 * min(bw, aw) and oy > 0.50 * min(bh, ah)
            ), (bu.get("label"), au.get("label"), bbox(bu), bbox(au))


def test_v301_n4_counts_match_sa_after_height_split():
    ficha = extrair_ficha_lateral_viga(_recorte_v301(), "V301_A")
    prep = prepare_n4_face_units(ficha.get("face_units") or [], viga_nome="V301")
    by = _by_side(prep)
    assert len(by["A"]) == 16
    assert len(by["B"]) == 16
