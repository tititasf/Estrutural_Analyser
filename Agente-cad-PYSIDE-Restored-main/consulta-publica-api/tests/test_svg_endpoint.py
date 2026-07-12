"""Testes do endpoint GET /api/v1/ficha/{code}/svg/{nivel} (STORY-06, AC 1-4)."""

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

# viewbox minúsculo (não viewBox) porque `_parse_html_cache` (ficha_reader.py)
# reserializa via BeautifulSoup/html.parser, que normaliza nomes de atributo
# de tags SVG para minúsculas — comportamento pré-existente do parser, não
# desta story.
_N1_SVG = '<svg class="img-geo" viewbox="0 0 10 10"></svg>'
_N3_SVG = '<svg class="img-n3" viewbox="0 0 10 10"></svg>'


def _montar_obra_fake(obra_root: Path, *, com_n3: bool) -> Path:
    obra_dir = obra_root / "obra_fake"
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

    n3_card = f'<div class="face-card">N3 disponível {_N3_SVG}</div>' if com_n3 else ""
    (run_dir / "pilares" / "P1.html").write_text(
        f'<div class="face-card">N1 / SA disponível {_N1_SVG}</div>' + n3_card,
        encoding="utf-8",
    )
    return obra_dir


@pytest.fixture
def contexto(tmp_path: Path):
    obra_dir = _montar_obra_fake(tmp_path, com_n3=True)
    db_path = tmp_path / "public_consulta_svg.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRACODE01', 'obra', 'obra-1', ?, 'Obra Teste', 0)",
        (str(obra_dir),),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMCODE01', 'item', 'obra-1', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()
    return db_path, tmp_path.parent if False else tmp_path, obra_dir


def _get(db_path: Path, dados_obras_root: Path, path: str, headers: dict | None = None) -> httpx.Response:
    settings = load_settings(public_consulta_db_path=db_path, dados_obras_root=dados_obras_root)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path, headers=headers or {})

    return asyncio.run(_run())


def test_svg_n1_puro_com_content_type_correto(contexto):
    db_path, tmp_path, obra_dir = contexto
    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMCODE01/svg/n1")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/svg+xml")
    assert resp.text == _N1_SVG
    # nunca envolto em JSON
    assert not resp.text.strip().startswith("{")


def test_svg_n3_presente(contexto):
    db_path, tmp_path, obra_dir = contexto
    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMCODE01/svg/n3")
    assert resp.status_code == 200
    assert resp.text == _N3_SVG


def test_svg_cache_control_e_etag(contexto):
    db_path, tmp_path, obra_dir = contexto
    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMCODE01/svg/n1")
    assert resp.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert resp.headers["etag"]


def test_svg_304_com_if_none_match(contexto):
    db_path, tmp_path, obra_dir = contexto
    primeira = _get(db_path, tmp_path, "/api/v1/ficha/ITEMCODE01/svg/n1")
    etag = primeira.headers["etag"]
    segunda = _get(
        db_path, tmp_path, "/api/v1/ficha/ITEMCODE01/svg/n1",
        headers={"If-None-Match": etag},
    )
    assert segunda.status_code == 304


def test_svg_n3_ausente_404_generico(tmp_path: Path):
    obra_dir = _montar_obra_fake(tmp_path, com_n3=False)
    db_path = tmp_path / "public_consulta_sem_n3.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript((_PROJECT_ROOT / "publisher" / "schema.sql").read_text(encoding="utf-8"))
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMCODE02', 'item', 'obra-1', ?, 'TERREO', 'pilares', 'P1', 'pilar', 'Pilar P1', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()
    resp = _get(db_path, tmp_path, "/api/v1/ficha/ITEMCODE02/svg/n3")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_svg_nivel_invalido_404_generico(contexto):
    """Strings de 1 segmento (sem "/") fora de {n1,n3} passam pelo roteamento
    e caem no 404 genérico da APLICAÇÃO. Strings com "/" (ex.: "../etc") nem
    chegam a bater na rota — ver test_path_traversal.py, que documenta essa
    diferença (mesma ressalva de URL-parsing já conhecida da STORY-03)."""
    db_path, tmp_path, obra_dir = contexto
    for nivel in ("n2", "svg", "N1"):
        resp = _get(db_path, tmp_path, f"/api/v1/ficha/ITEMCODE01/svg/{nivel}")
        assert resp.status_code == 404, nivel
        assert resp.json() == {"erro": "nao_encontrado"}


def test_svg_codigo_de_obra_404_generico(contexto):
    db_path, tmp_path, obra_dir = contexto
    resp = _get(db_path, tmp_path, "/api/v1/ficha/OBRACODE01/svg/n1")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_svg_codigo_inexistente_404_generico(contexto):
    db_path, tmp_path, obra_dir = contexto
    resp = _get(db_path, tmp_path, "/api/v1/ficha/NAOEXISTE1/svg/n1")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}
