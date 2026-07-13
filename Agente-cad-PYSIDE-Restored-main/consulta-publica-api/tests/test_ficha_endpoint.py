"""Testes do endpoint GET /api/v1/ficha/{code} (STORY-05, AC 1-7)."""

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

_BLACKLIST = {
    "cliente", "criterios_cliente", "data_solicitacao", "data_entrega",
    "observacoes", "membro_id", "login", "nome", "email", "senha_hash",
    "descricao", "local_path", "obra_id", "obra_dir", "item_id", "pavimento",
}


def _montar_obra_fake(obra_root: Path, *, com_n3: bool, com_lv: bool) -> Path:
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

    # Pack de fichas HTML — mesmo formato real (arete_manifest.json marca o
    # diretório como válido; svg.img-geo = N1, svg.img-n3 = N3).
    run_dir = obra_dir / "TERREO_20260101_000000"
    (run_dir / "pilares").mkdir(parents=True)
    (run_dir / "arete_manifest.json").write_text("{}", encoding="utf-8")

    n3_card = (
        '<div class="face-card">N3 disponível '
        '<svg class="img-n3" viewBox="0 0 10 10"></svg></div>'
        if com_n3 else ""
    )
    (run_dir / "pilares" / "P1.html").write_text(
        '<div class="face-card">N1 / SA disponível '
        '<svg class="img-geo" viewBox="0 0 10 10"></svg></div>' + n3_card,
        encoding="utf-8",
    )

    if com_lv:
        # `tem_lv` resolve pelo `beam_name` do PRÓPRIO item (aqui "P1", campo
        # `name`/`key` do pilar) — este fixture testa só a checagem de
        # existência de arquivo em isolamento; na prática só itens de classe
        # viga_lateral têm contrato LV real (pilares nunca têm).
        lv_dir = obra_dir / "Fase-4_Sincronizacao" / "JSON_Vigas_Laterais" / "LV-PARA"
        lv_dir.mkdir(parents=True)
        (lv_dir / "P1_A.json").write_text("{}", encoding="utf-8")

    return obra_dir


@pytest.fixture
def public_db_com_item(tmp_path: Path) -> tuple[Path, Path]:
    obra_dir = _montar_obra_fake(tmp_path, com_n3=True, com_lv=True)
    db_path = tmp_path / "public_consulta_ficha.db"
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
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, obra_rotulo, revoked) "
        "VALUES ('PAVCODE01', 'pavimento', 'obra-1', ?, 'TERREO', 'Obra Teste', 0)",
        (str(obra_dir),),
    )
    conn.commit()
    conn.close()
    return db_path, obra_dir


@pytest.fixture
def public_db_sem_n3(tmp_path: Path) -> Path:
    obra_dir = _montar_obra_fake(tmp_path, com_n3=False, com_lv=False)
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
    return db_path


def _get(db_path: Path, path: str) -> httpx.Response:
    settings = load_settings(public_consulta_db_path=db_path)
    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)

    async def _run():
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.get(path)

    return asyncio.run(_run())


def test_ficha_completa_com_n1_n3_lv(public_db_com_item):
    db_path, _ = public_db_com_item
    resp = _get(db_path, "/api/v1/ficha/ITEMCODE01")
    assert resp.status_code == 200
    body = resp.json()

    assert body["code"] == "ITEMCODE01"
    assert body["tipo"] == "pilar"
    assert body["titulo"] == "Pilar P1"
    assert body["obra_rotulo"] is None or isinstance(body["obra_rotulo"], str)
    assert body["pavimento_label"] == "Térreo"
    assert body["pavimento_code"] == "PAVCODE01"
    assert isinstance(body["campos"], dict)
    assert body["atencao"] == ""
    assert body["svg"]["n1"] == "/api/v1/ficha/ITEMCODE01/svg/n1"
    assert body["svg"]["n3"] == "/api/v1/ficha/ITEMCODE01/svg/n3"
    assert body["tem_lv"] is True

    # SVG nunca embutido cru no JSON (AC 1).
    corpo_str = json.dumps(body)
    assert "<svg" not in corpo_str


def test_ficha_svg_n3_null_quando_ausente(public_db_sem_n3: Path):
    resp = _get(public_db_sem_n3, "/api/v1/ficha/ITEMCODE02")
    assert resp.status_code == 200
    body = resp.json()
    assert body["svg"]["n1"] is not None
    assert body["svg"]["n3"] is None
    assert body["tem_lv"] is False
    assert body["pavimento_code"] is None


def test_ficha_404_generico_para_codigo_de_obra(public_db_com_item):
    """AC 3 — código de kind='obra' recebe o mesmo 404 genérico."""
    db_path, _ = public_db_com_item
    resp = _get(db_path, "/api/v1/ficha/OBRACODE01")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_ficha_404_generico_para_codigo_inexistente(public_db_com_item):
    db_path, _ = public_db_com_item
    resp = _get(db_path, "/api/v1/ficha/NAOEXISTE1")
    assert resp.status_code == 404
    assert resp.json() == {"erro": "nao_encontrado"}


def test_ficha_sem_campos_da_blacklist(public_db_com_item):
    """AC 7 — nenhum campo comercial/pessoal/estrutura-interna na resposta."""
    db_path, _ = public_db_com_item
    resp = _get(db_path, "/api/v1/ficha/ITEMCODE01")
    body = resp.json()
    chaves_topo = set(body.keys())
    assert not (chaves_topo & _BLACKLIST)
