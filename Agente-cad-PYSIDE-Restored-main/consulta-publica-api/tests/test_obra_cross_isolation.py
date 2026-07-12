"""Teste de isolamento cross-obra (STORY-07, AC4) — o teste de segurança
mais direto do MVP: código de obra A nunca pode resolver/listar itens de
obra B. Reaproveitado explicitamente pela suíte de segurança da STORY-15.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import httpx

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from config import load_settings  # noqa: E402
from main import create_app  # noqa: E402


def _montar_obra_fake(obra_root: Path, nome: str, nomes_pilares: list[str]) -> Path:
    obra_dir = obra_root / nome
    obra_dir.mkdir(parents=True)
    estado = {
        "pilares": [
            {
                "name": n, "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
                "classification": "OK", "lado_A": f"{n}V", "nivel_str": "N1",
            }
            for n in nomes_pilares
        ],
        "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                      "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    return obra_dir


def _get(db_path: Path, path: str) -> httpx.Response:
    settings = load_settings(public_consulta_db_path=db_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_indice_de_obra_a_nunca_lista_itens_de_obra_b(tmp_path: Path):
    obra_a_dir = _montar_obra_fake(tmp_path, "obra_a", ["P1", "P2"])
    obra_b_dir = _montar_obra_fake(tmp_path, "obra_b", ["P9"])

    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))

    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRACODE_A', 'obra', 'obra-a', ?, 'Obra A', 0)", (str(obra_a_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRACODE_B', 'obra', 'obra-b', ?, 'Obra B', 0)", (str(obra_b_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM_A1', 'item', 'obra-a', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1 (A)', 0)",
        (str(obra_a_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM_A2', 'item', 'obra-a', ?, 'TERREO', 'pilares', 'P2', 'pilar', 'Pilar P2 (A)', 0)",
        (str(obra_a_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM_B1', 'item', 'obra-b', ?, 'TERREO', 'pilares', 'P9', 'pilar', 'Pilar P9 (B)', 0)",
        (str(obra_b_dir),),
    )
    conn.commit()
    conn.close()

    resp_a = _get(db_path, "/api/v1/obra/OBRACODE_A")
    assert resp_a.status_code == 200
    body_a = resp_a.json()
    codes_a = {it["code"] for pav in body_a["pavimentos"] for it in pav["itens"]}
    assert codes_a == {"ITEM_A1", "ITEM_A2"}
    assert "ITEM_B1" not in codes_a
    assert "Pilar P9 (B)" not in json.dumps(body_a)

    resp_b = _get(db_path, "/api/v1/obra/OBRACODE_B")
    assert resp_b.status_code == 200
    body_b = resp_b.json()
    codes_b = {it["code"] for pav in body_b["pavimentos"] for it in pav["itens"]}
    assert codes_b == {"ITEM_B1"}
    assert "ITEM_A1" not in codes_b and "ITEM_A2" not in codes_b


def test_indice_de_obra_ignora_itens_revogados(tmp_path: Path):
    obra_dir = _montar_obra_fake(tmp_path, "obra_rev", ["P1", "P2"])
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRACODE_R', 'obra', 'obra-rev', ?, 'Obra Rev', 0)", (str(obra_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM_R1', 'item', 'obra-rev', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar Ativo', 0)",
        (str(obra_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEM_R2', 'item', 'obra-rev', ?, 'TERREO', 'pilares', 'P2', 'pilar', 'Pilar Revogado', 1)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/obra/OBRACODE_R")
    body = resp.json()
    codes = {it["code"] for pav in body["pavimentos"] for it in pav["itens"]}
    assert codes == {"ITEM_R1"}
