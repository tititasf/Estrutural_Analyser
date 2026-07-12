"""Teste anti-path-traversal do endpoint de SVG (STORY-06, AC 6).

`obra_dir` é sempre o path pré-resolvido armazenado pelo Publisher em
`public_codes` — nunca construído a partir de input do usuário. Ainda assim,
`svg_service.obter_svg` valida defensivamente que o `obra_dir` resolvido é
descendente de `dados_obras_root` antes de ler qualquer arquivo. Este teste
simula o cenário-limite: um `obra_dir` publicado que aponta para FORA da
raiz configurada (ex.: configuração trocada entre publish-time e serve-time,
ou um dado corrompido/malicioso na tabela) — deve sempre resultar em 404
genérico, nunca num path leak ou 500.
"""

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
from services.svg_service import obter_svg  # noqa: E402


def _montar_obra_fake(obra_dir: Path) -> None:
    obra_dir.mkdir(parents=True)
    estado = {
        "pilares": [
            {
                "name": "P1", "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
                "classification": "OK", "lado_A": "V101", "nivel_str": "N1",
            },
        ],
        "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                      "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    run_dir = obra_dir / "TERREO_20260101_000000"
    (run_dir / "pilares").mkdir(parents=True)
    (run_dir / "arete_manifest.json").write_text("{}", encoding="utf-8")
    (run_dir / "pilares" / "P1.html").write_text(
        '<div class="face-card">N1 <svg class="img-geo" viewBox="0 0 10 10"></svg></div>',
        encoding="utf-8",
    )


def test_obra_dir_fora_da_raiz_retorna_none(tmp_path: Path):
    """Unidade — `obter_svg` nunca lê nada fora de `dados_obras_root`."""
    raiz_permitida = tmp_path / "DADOS-OBRAS-PERMITIDO"
    raiz_permitida.mkdir()
    obra_fora = tmp_path / "fora_da_raiz" / "obra_maliciosa"
    _montar_obra_fake(obra_fora)

    row = {
        "kind": "item", "obra_dir": str(obra_fora), "pavimento": "TERREO",
        "classe": "pilares", "item_id": "P1",
    }
    assert obter_svg(row, "n1", raiz_permitida) is None


def test_endpoint_404_generico_quando_obra_dir_foge_da_raiz(tmp_path: Path):
    """End-to-end via HTTP — mesmo com um código válido em `public_codes`,
    se o `obra_dir` armazenado foge de `dados_obras_root`, o endpoint nunca
    vaza dado nem erro 500 — só o 404 genérico padrão."""
    raiz_permitida = tmp_path / "DADOS-OBRAS-PERMITIDO"
    raiz_permitida.mkdir()
    obra_fora = tmp_path / "fora_da_raiz" / "obra_maliciosa"
    _montar_obra_fake(obra_fora)

    db_path = tmp_path / "public_consulta_traversal.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMCODE99', 'item', 'obra-x', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_fora),),
    )
    conn.commit()
    conn.close()

    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=raiz_permitida)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get("/api/v1/ficha/ITEMCODE99/svg/n1")

    resp = asyncio.run(_run())
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_nivel_com_traversal_string_nunca_vira_path(tmp_path: Path):
    """`nivel` com `/` (decodificado de `%2F`) nem chega a bater na rota
    `/ficha/{code}/svg/{nivel}` (path param sem conversor `:path` não casa
    barras) — Starlette responde com o 404 genérico DELE
    (`{"detail": "Not Found"}`), nunca o da aplicação, mas o resultado de
    segurança é o mesmo: nunca 200, nunca leitura de arquivo fora do
    esperado, nunca 500. Mesma ressalva de URL-parsing documentada na
    STORY-03 (caracteres especiais de URL são interceptados antes do
    handler)."""
    raiz_permitida = tmp_path / "DADOS-OBRAS-PERMITIDO"
    raiz_permitida.mkdir()
    obra_dir = raiz_permitida / "obra_ok"
    _montar_obra_fake(obra_dir)

    db_path = tmp_path / "public_consulta_nivel.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMCODE98', 'item', 'obra-x', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()

    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=raiz_permitida)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run(nivel):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(f"/api/v1/ficha/ITEMCODE98/svg/{nivel}")

    resp = asyncio.run(_run("..%2F..%2Fetc%2Fpasswd"))
    assert resp.status_code == 404
    assert "erro" not in resp.json() or resp.json() == {"erro": "nao_encontrado"}
    assert "passwd" not in resp.text
