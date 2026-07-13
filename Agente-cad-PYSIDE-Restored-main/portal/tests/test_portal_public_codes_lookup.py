"""`public_codes_lookup.py` [2026-07-12] — leitura read-only de
`public_consulta.db` a partir do portal, usada para mostrar o código
público (obra/pavimento/item) direto nas telas do portal.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import httpx
import pytest

from portal.app import auth, public_codes_lookup
from portal.app.main import create_app
from portal.db import connection, repository as repo

_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSULTA_PUBLICA_DIR = _REPO_ROOT / "consulta-publica-api"
if str(_CONSULTA_PUBLICA_DIR) not in sys.path:
    sys.path.insert(0, str(_CONSULTA_PUBLICA_DIR))


def _montar_public_consulta_db(db_path: Path, *, obra_id: str, pavimento: str, item_id: str) -> None:
    schema = (_CONSULTA_PUBLICA_DIR / "publisher" / "schema.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(str(db_path))
    conn.executescript(schema)
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, obra_rotulo, revoked) "
        "VALUES ('OBRACODEX1', 'obra', ?, '/fake', 'Obra X', 0)",
        (obra_id,),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, obra_rotulo, revoked) "
        "VALUES ('PAVCODEX1', 'pavimento', ?, '/fake', ?, 'Obra X', 0)",
        (obra_id, pavimento),
    )
    conn.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "tipo_elemento, titulo_publico, revoked) VALUES "
        "('ITEMCODEX1', 'item', ?, '/fake', ?, 'pilares', ?, 'pilar', 'Pilar X', 0)",
        (obra_id, pavimento, item_id),
    )
    conn.commit()
    conn.close()


class TestBuscaDireta:
    def test_retorna_none_se_arquivo_nao_existe(self, tmp_path: Path):
        db_path = tmp_path / "nao-existe.db"
        assert public_codes_lookup.buscar_code_obra(db_path, "obra-x") is None
        assert public_codes_lookup.buscar_code_pavimento(db_path, "obra-x", "TERREO") is None
        assert public_codes_lookup.buscar_code_item(db_path, "obra-x", "TERREO", "pilares", "P1") is None

    def test_encontra_codes_reais_por_identidade(self, tmp_path: Path):
        db_path = tmp_path / "public.db"
        _montar_public_consulta_db(db_path, obra_id="obra-x", pavimento="TERREO", item_id="P1")

        assert public_codes_lookup.buscar_code_obra(db_path, "obra-x") == "OBRACODEX1"
        assert public_codes_lookup.buscar_code_pavimento(db_path, "obra-x", "TERREO") == "PAVCODEX1"
        assert public_codes_lookup.buscar_code_item(db_path, "obra-x", "TERREO", "pilares", "P1") == "ITEMCODEX1"

    def test_nunca_encontra_code_de_outra_obra(self, tmp_path: Path):
        db_path = tmp_path / "public.db"
        _montar_public_consulta_db(db_path, obra_id="obra-x", pavimento="TERREO", item_id="P1")

        assert public_codes_lookup.buscar_code_obra(db_path, "obra-y") is None
        assert public_codes_lookup.buscar_code_item(db_path, "obra-y", "TERREO", "pilares", "P1") is None

    def test_code_revogado_nao_e_retornado(self, tmp_path: Path):
        db_path = tmp_path / "public.db"
        _montar_public_consulta_db(db_path, obra_id="obra-x", pavimento="TERREO", item_id="P1")
        conn = sqlite3.connect(str(db_path))
        conn.execute("UPDATE public_codes SET revoked=1 WHERE code='ITEMCODEX1'")
        conn.commit()
        conn.close()

        assert public_codes_lookup.buscar_code_item(db_path, "obra-x", "TERREO", "pilares", "P1") is None

    def test_nao_escreve_nada_conexao_e_read_only(self, tmp_path: Path):
        """Reforço: o módulo abre em `mode=ro` de verdade — não é só
        convenção de código, uma tentativa de escrita através dele falha
        fisicamente (mesma disciplina de `consulta-publica-api/db/connection.py`)."""
        db_path = tmp_path / "public.db"
        _montar_public_consulta_db(db_path, obra_id="obra-x", pavimento="TERREO", item_id="P1")

        conn = public_codes_lookup._conectar_ro(db_path)
        assert conn is not None
        try:
            with pytest.raises(sqlite3.OperationalError):
                conn.execute("UPDATE public_codes SET revoked=1 WHERE 1=1")
        finally:
            conn.close()


@pytest.mark.asyncio
async def test_endpoint_n1_item_inclui_code_publico_quando_ja_publicado(settings, tmp_path: Path):
    """Integração — `GET /obras/{id}/n1/{classe}/{item_id}` do portal real
    devolve `code_publico` quando o item já foi publicado na App de
    Consulta (não precisa da obra real em disco — só de um
    `estado_<pav>.json` mínimo sintético)."""
    obra_dir = tmp_path / "obra_com_code"
    obra_dir.mkdir()
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

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana2", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana2",
    )
    ana = repo.obter_membro_por_login(c, "ana2")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComCode", pasta_drive_id="folder-ana2",
        arquivo_hash="hash-com-code", estado="pronta", local_path=str(obra_dir),
    )
    c.close()

    _montar_public_consulta_db(
        settings.public_consulta_db_path, obra_id=obra_id, pavimento="TERREO", item_id="P1",
    )

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana2", "senha": "segredo123"})
            r = await client.get(f"/obras/{obra_id}/n1/pilares/P1")
            assert r.status_code == 200
            body = r.json()
            assert body["code_publico"] == "ITEMCODEX1"
            assert body["referencia"] == "ObraComCode › Térreo › P1"


@pytest.mark.asyncio
async def test_endpoint_obra_code_retorna_code_publico_da_obra(settings, tmp_path: Path):
    obra_dir = tmp_path / "obra_com_code_obra"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana3", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana3",
    )
    ana = repo.obter_membro_por_login(c, "ana3")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComCodeObra", pasta_drive_id="folder-ana3",
        arquivo_hash="hash-com-code-obra", estado="pronta", local_path=str(obra_dir),
    )
    c.close()

    _montar_public_consulta_db(
        settings.public_consulta_db_path, obra_id=obra_id, pavimento="TERREO", item_id="P1",
    )

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana3", "senha": "segredo123"})
            r = await client.get(f"/obras/{obra_id}/obra-code")
            assert r.status_code == 200
            body = r.json()
            assert body["code_publico"] == "OBRACODEX1"
            assert body["referencia"] == "ObraComCodeObra"


@pytest.mark.asyncio
async def test_endpoint_pavimento_code_retorna_code_publico_do_pavimento(settings, tmp_path: Path):
    obra_dir = tmp_path / "obra_com_code_pav"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana4", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana4",
    )
    ana = repo.obter_membro_por_login(c, "ana4")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComCodePav", pasta_drive_id="folder-ana4",
        arquivo_hash="hash-com-code-pav", estado="pronta", local_path=str(obra_dir),
    )
    c.close()

    _montar_public_consulta_db(
        settings.public_consulta_db_path, obra_id=obra_id, pavimento="TERREO", item_id="P1",
    )

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana4", "senha": "segredo123"})
            r = await client.get(f"/obras/{obra_id}/pavimento-code", params={"pavimento": "TERREO"})
            assert r.status_code == 200
            body = r.json()
            assert body["code_publico"] == "PAVCODEX1"
            assert body["referencia"] == "ObraComCodePav › Térreo"

            r_outro = await client.get(f"/obras/{obra_id}/pavimento-code", params={"pavimento": "COBERTURA"})
            assert r_outro.status_code == 200
            assert r_outro.json()["code_publico"] is None


@pytest.mark.asyncio
async def test_endpoint_recorte_code_retorna_code_publico_do_recorte(settings, tmp_path: Path):
    """[2026-07-13] `GET /obras/{id}/recorte-code` — código próprio de 1
    recorte (Torre 1/Detalhes/etc), mintado ao validar."""
    obra_dir = tmp_path / "obra_com_code_recorte"
    obra_dir.mkdir()

    c = connection.init_db(settings.db_path)
    repo.criar_membro(
        c, login="ana5", nome="Ana Silva",
        senha_hash=auth.hash_senha("segredo123"), drive_folder_id="folder-ana5",
    )
    ana = repo.obter_membro_por_login(c, "ana5")
    obra_id = repo.criar_obra(
        c, membro_id=ana["id"], nome="ObraComCodeRecorte", pasta_drive_id="folder-ana5",
        arquivo_hash="hash-com-code-recorte", estado="processando", local_path=str(obra_dir),
    )
    c.close()

    schema = (_CONSULTA_PUBLICA_DIR / "publisher" / "schema.sql").read_text(encoding="utf-8")
    pub = sqlite3.connect(str(settings.public_consulta_db_path))
    pub.executescript(schema)
    pub.execute(
        "INSERT INTO public_codes (code, kind, obra_id, obra_dir, pavimento, classe, item_id, "
        "titulo_publico, obra_rotulo, revoked) VALUES "
        "('RECCODEX1', 'recorte', ?, '/fake', 'TERREO', 'torre_1', 'BRUTO-X', 'Torre 1', 'ObraComCodeRecorte', 0)",
        (obra_id,),
    )
    pub.commit()
    pub.close()

    app = create_app(settings)
    transport = httpx.ASGITransport(app=app)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/login", json={"login": "ana5", "senha": "segredo123"})
            r = await client.get(
                f"/obras/{obra_id}/recorte-code",
                params={"pavimento": "TERREO", "recorte_tipo": "torre_1", "bruto_id": "BRUTO-X"},
            )
            assert r.status_code == 200
            body = r.json()
            assert body["code_publico"] == "RECCODEX1"
            assert body["referencia"] == "ObraComCodeRecorte › Térreo › Torre 1"

            r_outro = await client.get(
                f"/obras/{obra_id}/recorte-code",
                params={"pavimento": "TERREO", "recorte_tipo": "detalhes", "bruto_id": "BRUTO-X"},
            )
            assert r_outro.status_code == 200
            assert r_outro.json()["code_publico"] is None
