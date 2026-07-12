"""Fixtures compartilhadas da suíte de segurança (STORY-15).

Monta 2 obras publicadas (A e B) com dados propositalmente DIFERENTES e
DISTINGUÍVEIS (títulos únicos, `obra_rotulo` únicos) em cada classe testável
(pilar com N1/N3, viga_lateral com contrato LV materializado) — a base para
todos os testes de isolamento cross-obra (AC3) e blacklist de schema (AC5).
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import load_settings  # noqa: E402
from main import create_app  # noqa: E402


def requisitar(db_path: Path, dados_obras_root: Path, metodo: str, path: str, **kwargs) -> httpx.Response:
    """Cliente HTTP compartilhado por toda a suíte — `httpx.ASGITransport`
    (não `starlette.testclient.TestClient`, incompatível com httpx>=0.28
    deste ambiente, ver test_health.py)."""
    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=dados_obras_root)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(metodo, path, **kwargs)

    return asyncio.run(_run())

_N1_SVG = '<svg class="img-geo" viewbox="0 0 10 10"></svg>'
_N3_SVG = '<svg class="img-n3" viewbox="0 0 10 10"></svg>'


def _contrato_lv(lado: str, largura_total: float) -> dict:
    return {
        "number": "301", "name": f"VIGA_{lado}_Para", "beam_name": "VIGA1", "floor": "TERREO",
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
        ],
        "structural_segments": [{"segment_index": 0, "width": 122.0}],
        "structural_segment_count": 1, "segment_count": 1, "geometry_length": 122.0,
    }


def _montar_obra_completa(obra_root: Path, *, prefixo: str, titulo_pilar: str, titulo_viga: str) -> Path:
    """Obra com 1 pilar (N1+N3 gerados) + 1 viga lateral (com contrato LV
    materializado, comportamento Para, lado A) — cobre todas as classes que
    a suíte de segurança precisa exercitar (ficha/svg/paineis-lv)."""
    obra_dir = obra_root / f"obra_{prefixo}"
    obra_dir.mkdir(parents=True)

    estado = {
        "pilares": [
            {
                "name": titulo_pilar, "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
                "classification": "OK", "lado_A": "V1", "nivel_str": "N1",
            },
        ],
        "slabs": [], "cortes": [],
        "segmentos": {
            "fundo": [],
            "lateral_a_para": [
                {"uid": f"{prefixo}-VIGA1", "beam_name": "VIGA1", "segment_label": "1",
                 "titulo_override": titulo_viga, "points": [[0, 0], [100, 0]]},
            ],
            "lateral_b_para": [], "lateral_a_passa": [], "lateral_b_passa": [],
        },
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")

    run_dir = obra_dir / "TERREO_20260101_000000"
    (run_dir / "pilares").mkdir(parents=True)
    (run_dir / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "pilares" / f"{titulo_pilar}.html").write_text(
        f'<div class="face-card">N1 {_N1_SVG}</div><div class="face-card">N3 {_N3_SVG}</div>',
        encoding="utf-8",
    )

    lv_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / "LV-PARA"
    lv_dir.mkdir(parents=True)
    (lv_dir / "VIGA1_A.json").write_text(json.dumps(_contrato_lv("A", 122.0)), encoding="utf-8")

    return obra_dir


@pytest.fixture
def duas_obras(tmp_path: Path):
    """Retorna `(db_path, dados_obras_root, codigos)` — `codigos` é um dict
    com todos os `code` publicados para as obras A e B, prontos para os
    testes de isolamento/blacklist/revogação."""
    dados_obras_root = tmp_path
    obra_a_dir = _montar_obra_completa(
        dados_obras_root, prefixo="a", titulo_pilar="P1_OBRA_A", titulo_viga="VIGA1_OBRA_A_SEGREDO",
    )
    obra_b_dir = _montar_obra_completa(
        dados_obras_root, prefixo="b", titulo_pilar="P1_OBRA_B", titulo_viga="VIGA1_OBRA_B_SEGREDO",
    )

    db_path = tmp_path / "public_consulta.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))

    def _inserir_obra(code: str, obra_id: str, obra_dir: Path, rotulo: str, revoked: int = 0):
        conn.execute(
            "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
            "VALUES (?, 'obra', ?, ?, ?, ?)",
            (code, obra_id, str(obra_dir), rotulo, revoked),
        )

    def _inserir_item(code, obra_id, obra_dir, classe, item_id, tipo_elemento, titulo, obra_rotulo, revoked=0):
        conn.execute(
            "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
            "tipo_elemento, titulo_publico, obra_rotulo, revoked) VALUES "
            "(?, 'item', ?, ?, 'TERREO', ?, ?, ?, ?, ?, ?)",
            (code, obra_id, str(obra_dir), classe, item_id, tipo_elemento, titulo, obra_rotulo, revoked),
        )

    def _inserir_pavimento(code, obra_id, obra_dir, pavimento, obra_rotulo, revoked=0):
        conn.execute(
            "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, obra_rotulo, revoked) "
            "VALUES (?, 'pavimento', ?, ?, ?, ?, ?)",
            (code, obra_id, str(obra_dir), pavimento, obra_rotulo, revoked),
        )

    ROTULO_A = "Obra A — Cliente Confidencial X"
    ROTULO_B = "Obra B — Cliente Confidencial Y"
    _inserir_obra("OBRACODEA1", "obra-a", obra_a_dir, ROTULO_A)
    _inserir_obra("OBRACODEB1", "obra-b", obra_b_dir, ROTULO_B)
    _inserir_pavimento("PAVCODEA1", "obra-a", obra_a_dir, "TERREO", ROTULO_A)
    _inserir_pavimento("PAVCODEB1", "obra-b", obra_b_dir, "TERREO", ROTULO_B)
    _inserir_item("ITEMPILARA1", "obra-a", obra_a_dir, "pilares", "P1_OBRA_A", "pilar", "Pilar A", ROTULO_A)
    _inserir_item("ITEMPILARB1", "obra-b", obra_b_dir, "pilares", "P1_OBRA_B", "pilar", "Pilar B", ROTULO_B)
    _inserir_item("ITEMVIGAA1", "obra-a", obra_a_dir, "lateral_a_para", "a-VIGA1", "viga_lateral", "Viga A", ROTULO_A)
    _inserir_item("ITEMVIGAB1", "obra-b", obra_b_dir, "lateral_a_para", "b-VIGA1", "viga_lateral", "Viga B", ROTULO_B)
    _inserir_item(
        "ITEMREVOGADO1", "obra-a", obra_a_dir, "pilares", "P1_OBRA_A_REVOGADO", "pilar",
        "Pilar Revogado", ROTULO_A, revoked=1,
    )
    conn.commit()
    conn.close()

    codigos = {
        "obra_a": "OBRACODEA1", "obra_b": "OBRACODEB1",
        "pavimento_a": "PAVCODEA1", "pavimento_b": "PAVCODEB1",
        "pilar_a": "ITEMPILARA1", "pilar_b": "ITEMPILARB1",
        "viga_a": "ITEMVIGAA1", "viga_b": "ITEMVIGAB1",
        "revogado": "ITEMREVOGADO1",
    }
    return db_path, dados_obras_root, codigos
