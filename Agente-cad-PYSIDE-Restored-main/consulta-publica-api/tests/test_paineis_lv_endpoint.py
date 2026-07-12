"""Testes do endpoint GET /api/v1/ficha/{code}/paineis-lv (STORY-12)."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import load_settings  # noqa: E402
from main import create_app  # noqa: E402

# Fixture baseada no schema REAL observado em
# sandbox_lv_loop/.../JSON_Vigas_Laterais/V301_A.json (build_lv_generation_contracts,
# src/core/lv_generation_contract.py) — inclui campos internos (points,
# contract_id, structural_segment_index) que o endpoint NUNCA deve repassar.
def _contrato_lv_real(lado: str, largura_total: float) -> dict:
    return {
        "number": "301", "name": f"V301_{lado}_Para", "beam_name": "V301", "floor": "13_PAV",
        "side": lado, "behavior": "Para", "contract_id": f"LV_{lado}_PARA",
        "total_width": largura_total, "total_height": 129.0, "h_section": 51.0,
        "h_face_rule": "section_depth + 4 cm",
        "panels": [
            {
                "width": 122.0, "height1": 125.0, "height2": 0.0, "grade_h1": 0.0, "grade_h2": 0.0,
                "panel_type": "Sarrafeado", "structural_segment_index": 0, "segment_index": 0,
                "panel_index_in_segment": 1, "points": [[0, 0], [122, 0]], "contract_id": "seg-0",
                "source_key": "beamtracer",
            },
            {
                "width": 80.5, "height1": 125.0, "height2": 0.0, "grade_h1": 0.0, "grade_h2": 0.0,
                "panel_type": "recorte", "structural_segment_index": 1, "segment_index": 1,
                "panel_index_in_segment": 1, "points": [[122, 0], [202.5, 0]], "contract_id": "seg-1",
                "source_key": "beamtracer",
            },
        ],
        "structural_segments": [{"segment_index": 0, "width": 122.0}],
        "structural_segment_count": 1, "segment_count": 2, "geometry_length": 202.5,
    }


def _montar_obra_com_lv(obra_root: Path, *, so_lado_a: bool = False) -> Path:
    obra_dir = obra_root / "obra_lv"
    obra_dir.mkdir(parents=True)
    estado = {
        "pilares": [], "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [
            {"uid": "V301", "beam_name": "V301", "points": [[0, 0], [200, 0], [200, 20], [0, 20]]},
        ], "lateral_b_para": [], "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_13_PAV.json").write_text(json.dumps(estado), encoding="utf-8")

    lv_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / "LV-PARA"
    lv_dir.mkdir(parents=True)
    (lv_dir / "V301_A.json").write_text(json.dumps(_contrato_lv_real("A", 202.5)), encoding="utf-8")
    if not so_lado_a:
        (lv_dir / "V301_B.json").write_text(json.dumps(_contrato_lv_real("B", 198.0)), encoding="utf-8")
    return obra_dir


def _inserir_item(conn, *, code, obra_id, obra_dir, classe, item_id="V301", tipo_elemento="viga_lateral"):
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "(?, 'item', ?, ?, '13_PAV', ?, ?, ?, 'Viga V301', 0)",
        (code, obra_id, str(obra_dir), classe, item_id, tipo_elemento),
    )


def _get(db_path: Path, dados_obras_root: Path, path: str) -> httpx.Response:
    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=dados_obras_root)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_paineis_lv_resposta_com_2_lados(tmp_path: Path):
    obra_dir = _montar_obra_com_lv(tmp_path)
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_item(conn, code="ITEMLV01", obra_id="obra-lv", obra_dir=obra_dir, classe="lateral_a_para")
    conn.commit()
    conn.close()

    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMLV01/paineis-lv")
    assert resp.status_code == 200
    body = resp.json()

    assert body["total_width"] == 202.5
    assert body["h_section"] == 51.0
    assert set(body["paineis"].keys()) == {"A", "B"}
    assert len(body["paineis"]["A"]) == 2
    assert body["paineis"]["A"][0] == {
        "width": 122.0, "height1": 125.0, "height2": 0.0, "panel_type": "Sarrafeado",
    }
    # nenhum campo interno de geometria vaza (AC6/isolamento)
    corpo_str = json.dumps(body)
    for proibido in ("points", "contract_id", "source_key", "structural_segment_index", "grade_h1"):
        assert proibido not in corpo_str

    assert resp.headers["cache-control"] == "public, max-age=3600"


def test_paineis_lv_so_lado_a_presente(tmp_path: Path):
    obra_dir = _montar_obra_com_lv(tmp_path, so_lado_a=True)
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_item(conn, code="ITEMLV02", obra_id="obra-lv", obra_dir=obra_dir, classe="lateral_a_para")
    conn.commit()
    conn.close()

    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMLV02/paineis-lv")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body["paineis"].keys()) == {"A"}


def test_paineis_lv_404_generico_sem_contrato(tmp_path: Path):
    obra_dir = tmp_path / "obra_sem_lv"
    obra_dir.mkdir()
    estado = {
        "pilares": [], "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [
            {"uid": "V999", "beam_name": "V999", "points": [[0, 0], [10, 0], [10, 10], [0, 10]]},
        ], "lateral_b_para": [], "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_13_PAV.json").write_text(json.dumps(estado), encoding="utf-8")

    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_item(conn, code="ITEMLV03", obra_id="obra-x", obra_dir=obra_dir, classe="lateral_a_para", item_id="V999")
    conn.commit()
    conn.close()

    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMLV03/paineis-lv")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_paineis_lv_404_para_item_que_nao_e_viga_lateral(tmp_path: Path):
    obra_dir = _montar_obra_com_lv(tmp_path)
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMPILAR', 'item', 'obra-lv', ?, '13_PAV', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()

    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMPILAR/paineis-lv")
    assert resp.status_code == 404


def test_paineis_lv_404_generico_para_codigo_inexistente(tmp_path: Path):
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    resp = _get(db_path, tmp_path, "/api/v1/ficha/NAOEXISTE1/paineis-lv")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_paineis_lv_obra_dir_fora_da_raiz_404(tmp_path: Path):
    raiz_permitida = tmp_path / "DADOS-OBRAS-PERMITIDO"
    raiz_permitida.mkdir()
    obra_fora = tmp_path / "fora" / "obra_lv"
    obra_fora_pai = obra_fora.parent
    obra_fora_pai.mkdir(parents=True)
    obra_dir = _montar_obra_com_lv(obra_fora_pai)
    assert obra_dir == obra_fora  # sanity: mesmo path

    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_item(conn, code="ITEMLV04", obra_id="obra-lv", obra_dir=obra_dir, classe="lateral_a_para")
    conn.commit()
    conn.close()

    resp = _get(db_path, raiz_permitida, "/api/v1/ficha/ITEMLV04/paineis-lv")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
