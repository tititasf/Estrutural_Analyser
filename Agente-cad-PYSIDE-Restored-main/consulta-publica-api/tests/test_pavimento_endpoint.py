"""Testes do endpoint GET /api/v1/pavimento/{code} [2026-07-12].

"Ficha do pavimento"/recorte limpo da torre — cada pavimento resolve
direto pra sua própria lista de itens, sem precisar do código da obra.
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


def _estado_com_pilar(nome: str) -> dict:
    return {
        "pilares": [
            {"name": nome, "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
             "classification": "OK", "lado_A": f"{nome}V", "nivel_str": "N1"},
        ],
        "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                      "lateral_a_passa": [], "lateral_b_passa": []},
    }


def _montar_db_com_pavimento(tmp_path: Path) -> tuple[Path, Path]:
    obra_dir = tmp_path / "obra_pav"
    obra_dir.mkdir(parents=True)
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(_estado_com_pilar("P1")), encoding="utf-8")
    (obra_dir / "estado_COBERTURA.json").write_text(json.dumps(_estado_com_pilar("P2")), encoding="utf-8")
    db_path = tmp_path / "public.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    _inserir_publico(conn, code="OBRACODEP", kind="obra", obra_id="obra-pav", obra_dir=obra_dir,
                      obra_rotulo="Obra Pavimento")
    _inserir_publico(conn, code="PAVCODE01", kind="pavimento", obra_id="obra-pav", obra_dir=obra_dir,
                      pavimento="TERREO", obra_rotulo="Obra Pavimento")
    _inserir_publico(conn, code="ITEMP1PAV", kind="item", obra_id="obra-pav", obra_dir=obra_dir,
                      pavimento="TERREO", classe="pilares", item_id="P1",
                      tipo_elemento="pilar", titulo_publico="Pilar P1")
    _inserir_publico(conn, code="ITEMP2PAV", kind="item", obra_id="obra-pav", obra_dir=obra_dir,
                      pavimento="COBERTURA", classe="pilares", item_id="P2",
                      tipo_elemento="pilar", titulo_publico="Pilar P2 (outro pavimento)")
    conn.commit()
    conn.close()
    return db_path, obra_dir


def test_pavimento_resolve_direto_para_seus_proprios_itens(tmp_path: Path):
    db_path, _obra_dir = _montar_db_com_pavimento(tmp_path)

    resp = _get(db_path, "/api/v1/pavimento/PAVCODE01")
    assert resp.status_code == 200
    body = resp.json()
    assert body["obra_rotulo"] == "Obra Pavimento"
    assert body["pavimento_label"] == "Térreo"
    assert {it["code"] for it in body["itens"]} == {"ITEMP1PAV"}
    # nunca o item do OUTRO pavimento (COBERTURA) vaza aqui
    assert "ITEMP2PAV" not in json.dumps(body)
    assert "Pilar P2" not in json.dumps(body)

    assert resp.headers["cache-control"] == "private, max-age=60"


def test_pavimento_404_generico_para_codigo_de_obra(tmp_path: Path):
    db_path, _obra_dir = _montar_db_com_pavimento(tmp_path)
    resp = _get(db_path, "/api/v1/pavimento/OBRACODEP")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_pavimento_404_generico_para_codigo_de_item(tmp_path: Path):
    db_path, _obra_dir = _montar_db_com_pavimento(tmp_path)
    resp = _get(db_path, "/api/v1/pavimento/ITEMP1PAV")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_pavimento_404_generico_para_codigo_inexistente(tmp_path: Path):
    db_path, _obra_dir = _montar_db_com_pavimento(tmp_path)
    resp = _get(db_path, "/api/v1/pavimento/NAOEXISTE9")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_pavimento_revogado_404_identico(tmp_path: Path):
    db_path, obra_dir = _montar_db_com_pavimento(tmp_path)
    conn = sqlite3.connect(str(db_path))
    conn.execute("UPDATE public_codes SET revoked=1 WHERE code='PAVCODE01'")
    conn.commit()
    conn.close()

    resp = _get(db_path, "/api/v1/pavimento/PAVCODE01")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_indice_de_obra_inclui_code_de_cada_pavimento(tmp_path: Path):
    """O `/obra/{code}` também expõe o code de cada pavimento — permite
    navegar da lista geral direto pra ficha de 1 pavimento."""
    db_path, _obra_dir = _montar_db_com_pavimento(tmp_path)
    resp = _get(db_path, "/api/v1/obra/OBRACODEP")
    assert resp.status_code == 200
    body = resp.json()
    pav_terreo = next(p for p in body["pavimentos"] if p["pavimento_label"] == "Térreo")
    assert pav_terreo["code"] == "PAVCODE01"
