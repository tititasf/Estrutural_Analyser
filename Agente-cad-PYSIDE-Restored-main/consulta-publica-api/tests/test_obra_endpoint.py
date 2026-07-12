"""Testes do endpoint GET /api/v1/obra/{code} (STORY-07, AC 1-3, 5)."""

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


def _montar_obra_fake(obra_root: Path, nome: str, *, pavimentos_com_itens: dict[str, list[str]], pavimentos_vazios: list[str] = ()) -> Path:
    """`pavimentos_com_itens`: {pavimento: [nomes de pilar]}. `pavimentos_vazios`:
    pavimentos com `estado_<pav>.json` existente mas 0 itens em qualquer classe."""
    obra_dir = obra_root / nome
    obra_dir.mkdir(parents=True)

    for pavimento, nomes_pilares in pavimentos_com_itens.items():
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
        (obra_dir / f"estado_{pavimento}.json").write_text(json.dumps(estado), encoding="utf-8")

    for pavimento in pavimentos_vazios:
        estado_vazio = {
            "pilares": [], "slabs": [], "cortes": [],
            "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                          "lateral_a_passa": [], "lateral_b_passa": []},
        }
        (obra_dir / f"estado_{pavimento}.json").write_text(json.dumps(estado_vazio), encoding="utf-8")

    return obra_dir


def _inserir_publico(conn: sqlite3.Connection, *, code: str, kind: str, obra_id: str,
                      obra_dir: Path, pavimento: str | None = None, classe: str | None = None,
                      item_id: str | None = None, tipo_elemento: str | None = None,
                      titulo_publico: str | None = None, obra_rotulo: str | None = None,
                      revoked: int = 0) -> None:
    conn.execute(
        """
        INSERT INTO public_codes
            (code, kind, obra_id, obra_dir, pavimento, classe, item_id,
             tipo_elemento, titulo_publico, obra_rotulo, revoked)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (code, kind, obra_id, str(obra_dir), pavimento, classe, item_id,
         tipo_elemento, titulo_publico, obra_rotulo, revoked),
    )


def _get(db_path: Path, path: str) -> httpx.Response:
    settings = load_settings(public_consulta_db_path=db_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_indice_obra_estrutura_completa(tmp_path: Path):
    obra_dir = _montar_obra_fake(
        tmp_path, "obra_a",
        pavimentos_com_itens={"TERREO": ["P1", "P2"]},
    )
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_publico(conn, code="OBRACODE", kind="obra", obra_id="obra-a", obra_dir=obra_dir, obra_rotulo="Obra A")
    _inserir_publico(conn, code="ITEMP1", kind="item", obra_id="obra-a", obra_dir=obra_dir,
                      pavimento="TERREO", classe="pilares", item_id="P1",
                      tipo_elemento="pilar", titulo_publico="Pilar P1")
    _inserir_publico(conn, code="ITEMP2", kind="item", obra_id="obra-a", obra_dir=obra_dir,
                      pavimento="TERREO", classe="pilares", item_id="P2",
                      tipo_elemento="pilar", titulo_publico="Pilar P2")
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/obra/OBRACODE")
    assert resp.status_code == 200
    body = resp.json()
    assert body["obra_rotulo"] == "Obra A"
    assert len(body["pavimentos"]) == 1
    pav = body["pavimentos"][0]
    assert pav["pavimento_label"] == "Térreo"
    assert {it["code"] for it in pav["itens"]} == {"ITEMP1", "ITEMP2"}
    for item in pav["itens"]:
        assert set(item.keys()) == {"code", "titulo", "tipo"}

    # nunca item_id/pavimento crus na resposta
    corpo_str = json.dumps(body)
    assert "item_id" not in corpo_str
    assert '"P1"' not in corpo_str  # item_id cru "P1" não deve aparecer (só "Pilar P1")

    assert resp.headers["cache-control"] == "private, max-age=60"


def test_indice_obra_pavimento_vazio_aparece_como_lista_vazia(tmp_path: Path):
    obra_dir = _montar_obra_fake(
        tmp_path, "obra_b",
        pavimentos_com_itens={"TERREO": ["P1"]},
        pavimentos_vazios=["COBERTURA"],
    )
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_publico(conn, code="OBRACODE2", kind="obra", obra_id="obra-b", obra_dir=obra_dir)
    _inserir_publico(conn, code="ITEMP1B", kind="item", obra_id="obra-b", obra_dir=obra_dir,
                      pavimento="TERREO", classe="pilares", item_id="P1",
                      tipo_elemento="pilar", titulo_publico="Pilar P1")
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/obra/OBRACODE2")
    assert resp.status_code == 200
    body = resp.json()
    labels = {p["pavimento_label"]: p["itens"] for p in body["pavimentos"]}
    assert labels["Cobertura"] == []
    assert len(labels["Térreo"]) == 1


def test_indice_obra_404_generico_para_codigo_de_item(tmp_path: Path):
    obra_dir = _montar_obra_fake(tmp_path, "obra_c", pavimentos_com_itens={"TERREO": ["P1"]})
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_publico(conn, code="ITEMCODEC", kind="item", obra_id="obra-c", obra_dir=obra_dir,
                      pavimento="TERREO", classe="pilares", item_id="P1",
                      tipo_elemento="pilar", titulo_publico="Pilar P1")
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/obra/ITEMCODEC")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_indice_obra_404_generico_para_codigo_inexistente(tmp_path: Path):
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/obra/NAOEXISTE1")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
