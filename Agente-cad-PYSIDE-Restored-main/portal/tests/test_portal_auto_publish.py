"""Auto-publicação automática para a App de Consulta Pública [2026-07-12].

Confirma que: (1) obra com estado='pronta' é publicada sozinha, sem chamada
manual ao endpoint `/admin/publicar`; (2) obra não-'pronta' é ignorada;
(3) `auto_publish_enabled=False` (default de teste) nunca sobe a task;
(4) o `db_path` usado é sempre o configurável (`settings.public_consulta_db_path`),
nunca o `public_consulta.db` de produção.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

from portal.app.main import create_app
from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_CONSULTA_PUBLICA_DIR = _REPO_ROOT / "consulta-publica-api"
if str(_CONSULTA_PUBLICA_DIR) not in sys.path:
    sys.path.insert(0, str(_CONSULTA_PUBLICA_DIR))


def _montar_obra_dir_real(base: Path, nome: str) -> Path:
    obra_dir = base / nome
    obra_dir.mkdir(parents=True)
    estado = {
        "pilares": [
            {"name": "P1", "points": [[0, 0], [30, 0], [30, 30], [0, 30]],
             "classification": "OK", "lado_A": "V1", "nivel_str": "N1"},
        ],
        "slabs": [], "cortes": [],
        "segmentos": {"fundo": [], "lateral_a_para": [], "lateral_b_para": [],
                      "lateral_a_passa": [], "lateral_b_passa": []},
    }
    (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")
    return obra_dir


def _criar_obra(settings, *, nome: str, estado_obra: str, local_path: Path | None) -> str:
    c = connection.init_db(settings.db_path)
    try:
        membro_id = repo.criar_membro(
            c, login=f"membro-{nome}", nome="Fulano",
            senha_hash="x", drive_folder_id=f"folder-{nome}",
        )
        obra_id = repo.criar_obra(
            c, membro_id=membro_id, nome=nome, pasta_drive_id=f"pasta-{nome}",
            arquivo_hash=f"hash-{nome}", estado=estado_obra,
            local_path=str(local_path) if local_path else None,
        )
        return obra_id
    finally:
        c.close()


def test_auto_publish_desabilitado_por_padrao_no_fixture_de_teste(settings):
    """Confirma a disciplina de isolamento — `auto_publish_enabled=False` é
    o default da fixture compartilhada (mesma regra do `poll_enabled`)."""
    assert settings.auto_publish_enabled is False


@pytest.mark.asyncio
async def test_obra_pronta_e_publicada_automaticamente_sem_acao_manual(settings, tmp_path):
    obra_dir = _montar_obra_dir_real(tmp_path, "ObraAutoPub")
    obra_id = _criar_obra(settings, nome="ObraAutoPub", estado_obra="pronta", local_path=obra_dir)

    settings.auto_publish_enabled = True
    settings.auto_publish_interval_s = 1

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        assert app.state.auto_publish_task is not None
        await asyncio.sleep(1.5)  # deixa 1 ciclo completo rodar

    # Confirma no banco público de TESTE (nunca o de produção — settings
    # aponta pra tmp_path via conftest.py).
    conn = sqlite3.connect(str(settings.public_consulta_db_path))
    conn.row_factory = sqlite3.Row
    try:
        row_obra = conn.execute(
            "SELECT * FROM public_codes WHERE kind='obra' AND obra_id=?", (obra_id,)
        ).fetchone()
        assert row_obra is not None, "obra 'pronta' deveria ter sido auto-publicada"
        assert row_obra["revoked"] == 0

        itens = conn.execute(
            "SELECT * FROM public_codes WHERE kind='item' AND obra_id=?", (obra_id,)
        ).fetchall()
        assert len(itens) >= 1, "pilar P1 deveria ter sido publicado como item"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_obra_nao_pronta_nunca_e_publicada(settings, tmp_path):
    obra_dir = _montar_obra_dir_real(tmp_path, "ObraRascunho")
    obra_id = _criar_obra(
        settings, nome="ObraRascunho", estado_obra="aguardando_ingestao", local_path=obra_dir,
    )

    settings.auto_publish_enabled = True
    settings.auto_publish_interval_s = 1

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(1.5)

    # Nenhuma obra elegível foi publicada — o arquivo do banco público de
    # teste sequer chega a ser criado (schema só existe após 1º INSERT real
    # do Publisher). Ausência do arquivo já É a prova de "nunca publicada".
    if not settings.public_consulta_db_path.exists():
        return
    conn = sqlite3.connect(str(settings.public_consulta_db_path))
    try:
        row = conn.execute(
            "SELECT 1 FROM public_codes WHERE obra_id=?", (obra_id,)
        ).fetchone()
        assert row is None, "obra não-'pronta' NUNCA deve ser publicada automaticamente"
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_obra_com_pasta_inexistente_nao_derruba_o_ciclo(settings, tmp_path):
    """Obra 'pronta' mas com `local_path` apontando pra pasta que não existe
    em disco — o ciclo deve ignorá-la silenciosamente, nunca lançar exceção
    que derrube o loop (outras obras válidas continuam sendo publicadas)."""
    obra_fantasma_id = _criar_obra(
        settings, nome="ObraFantasma", estado_obra="pronta",
        local_path=tmp_path / "nao-existe-de-verdade",
    )
    obra_real_dir = _montar_obra_dir_real(tmp_path, "ObraReal")
    obra_real_id = _criar_obra(settings, nome="ObraReal", estado_obra="pronta", local_path=obra_real_dir)

    settings.auto_publish_enabled = True
    settings.auto_publish_interval_s = 1

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(1.5)

    conn = sqlite3.connect(str(settings.public_consulta_db_path))
    try:
        assert conn.execute(
            "SELECT 1 FROM public_codes WHERE obra_id=?", (obra_fantasma_id,)
        ).fetchone() is None
        assert conn.execute(
            "SELECT 1 FROM public_codes WHERE obra_id=?", (obra_real_id,)
        ).fetchone() is not None
    finally:
        conn.close()


@pytest.mark.asyncio
async def test_correcao_de_titulo_republicada_no_proximo_ciclo(settings, tmp_path):
    """Simula uma 'correção feita na web': muda o `estado_TERREO.json` do
    pilar entre 2 ciclos — o próximo ciclo automático deve refletir o novo
    título sem nenhuma ação manual de publicação."""
    obra_dir = _montar_obra_dir_real(tmp_path, "ObraCorrigida")
    obra_id = _criar_obra(settings, nome="ObraCorrigida", estado_obra="pronta", local_path=obra_dir)

    settings.auto_publish_enabled = True
    settings.auto_publish_interval_s = 1

    app = create_app(settings)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(1.5)  # 1º ciclo

        # "correção via web" — muda o nome do pilar no estado real.
        estado = json.loads((obra_dir / "estado_TERREO.json").read_text(encoding="utf-8"))
        estado["pilares"][0]["name"] = "P1-CORRIGIDO"
        (obra_dir / "estado_TERREO.json").write_text(json.dumps(estado), encoding="utf-8")

        await asyncio.sleep(1.5)  # 2º ciclo pega a correção

    conn = sqlite3.connect(str(settings.public_consulta_db_path))
    conn.row_factory = sqlite3.Row
    try:
        item = conn.execute(
            "SELECT * FROM public_codes WHERE kind='item' AND obra_id=? AND revoked=0",
            (obra_id,),
        ).fetchone()
        assert item is not None
        assert item["titulo_publico"] == "P1-CORRIGIDO"
    finally:
        conn.close()
