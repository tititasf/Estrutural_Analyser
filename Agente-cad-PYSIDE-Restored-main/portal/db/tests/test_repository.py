"""Testes da camada de dados do portal (HANDOFF-DATAENGINEER-PORTAL.md).

Cada teste usa um portal_data.db temporário e isolado — nunca toca
project_data.vision. Motor geral: dados de obra/usuário são fixtures genéricas.
"""

from __future__ import annotations

import sqlite3

import pytest

from portal.db import connection, repository as repo

TABELAS_ESPERADAS = {
    "portal_membros",
    "portal_obras",
    "portal_jobs",
    "portal_drive_sync_state",
    "portal_comentarios_equipe",
    "portal_n5_releases",
}


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "portal_data.db"
    c = connection.init_db(db_path)
    yield c
    c.close()


@pytest.fixture()
def membro_id(conn):
    return repo.criar_membro(
        conn, login="ana", nome="Ana Silva", senha_hash="$argon2$fake",
        drive_folder_id="drive-folder-ana",
    )


# --------------------------------------------------------------------------- #
# init_db / schema
# --------------------------------------------------------------------------- #

def test_init_db_cria_as_6_tabelas(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    nomes = {r["name"] for r in rows}
    assert TABELAS_ESPERADAS.issubset(nomes)
    # tabela de versão registrou a migration 001
    ver = conn.execute("SELECT MAX(version) FROM portal_schema_version").fetchone()[0]
    assert ver == 1


def test_init_db_idempotente(tmp_path):
    db_path = tmp_path / "portal_data.db"
    c1 = connection.init_db(db_path)
    c1.close()
    # rodar de novo não duplica versão nem quebra
    c2 = connection.init_db(db_path)
    n = c2.execute("SELECT COUNT(*) FROM portal_schema_version").fetchone()[0]
    assert n == 1
    c2.close()


def test_get_connection_recusa_banco_da_curadoria(tmp_path):
    with pytest.raises(ValueError):
        connection.get_connection(tmp_path / "project_data.vision")


def test_foreign_keys_ativas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


# --------------------------------------------------------------------------- #
# Membros
# --------------------------------------------------------------------------- #

def test_criar_e_listar_membros(conn):
    repo.criar_membro(conn, login="joao", nome="João", senha_hash="h1")
    repo.criar_membro(conn, login="maria", nome="Maria", senha_hash="h2")
    membros = repo.listar_membros(conn)
    logins = [m["login"] for m in membros]
    assert logins == ["joao", "maria"]  # ordenado por login
    assert repo.obter_membro_por_login(conn, "joao")["nome"] == "João"


def test_atualizar_drive_folder_membro(conn):
    """[2026-07-06] membro cadastrado sem pasta (--sem-drive) ganha uma depois,
    sem precisar recriar o membro (preserva id)."""
    membro_id = repo.criar_membro(conn, login="dono1", nome="Dono", senha_hash="h", papel="dono")
    assert repo.obter_membro_por_login(conn, "dono1")["drive_folder_id"] is None

    repo.atualizar_drive_folder_membro(conn, membro_id, "Portal-Obras/dono1")

    membro = repo.obter_membro_por_login(conn, "dono1")
    assert membro["id"] == membro_id  # mesmo id — não recriou
    assert membro["drive_folder_id"] == "Portal-Obras/dono1"


# --------------------------------------------------------------------------- #
# Obras
# --------------------------------------------------------------------------- #

def test_inserir_e_listar_obra(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Edificio A",
        pasta_drive_id="pasta-1", arquivo_hash="hash-abc",
    )
    obras = repo.listar_obras_por_membro(conn, membro_id)
    assert len(obras) == 1
    assert obras[0]["id"] == obra_id
    assert obras[0]["estado"] == "aguardando_ingestao"  # default


def test_atualizar_estado_obra(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Edificio B", pasta_drive_id="pasta-2",
    )
    repo.atualizar_estado_obra(conn, obra_id, "erro", erro_msg="parse falhou")
    obra = repo.obter_obra(conn, obra_id)
    assert obra["estado"] == "erro"
    assert obra["erro_msg"] == "parse falhou"


def test_dedup_obra_por_hash(conn, membro_id):
    repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra Hash", pasta_drive_id="p",
        arquivo_hash="hash-unico",
    )
    assert repo.obter_obra_por_hash(conn, "hash-unico") is not None
    # índice UNIQUE sobre arquivo_hash impede reprocessar o mesmo conteúdo
    with pytest.raises(sqlite3.IntegrityError):
        repo.criar_obra(
            conn, membro_id=membro_id, nome="Obra Dup", pasta_drive_id="p2",
            arquivo_hash="hash-unico",
        )


# --------------------------------------------------------------------------- #
# Jobs — fila respeitando ordem
# --------------------------------------------------------------------------- #

def test_enfileirar_e_consumir_job_respeita_ordem(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra Fila", pasta_drive_id="pf",
    )
    # 3 jobs: prioridade decide, depois ordem de chegada
    j1 = repo.enfileirar_job(conn, obra_id=obra_id, prioridade=0)   # baixa
    j2 = repo.enfileirar_job(conn, obra_id=obra_id, prioridade=5)   # alta → primeiro
    j3 = repo.enfileirar_job(conn, obra_id=obra_id, prioridade=0)   # baixa, depois de j1

    c1 = repo.consumir_job(conn, engine_version="abc123")
    assert c1["id"] == j2
    assert c1["status"] == "executando"
    assert c1["engine_version"] == "abc123"

    c2 = repo.consumir_job(conn)
    assert c2["id"] == j1  # mesma prioridade, mais antigo primeiro

    c3 = repo.consumir_job(conn)
    assert c3["id"] == j3

    assert repo.consumir_job(conn) is None  # fila vazia


def test_finalizar_job_e_historico(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra Job", pasta_drive_id="pj",
    )
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    repo.consumir_job(conn)
    repo.finalizar_job(conn, job_id, "concluido", log_path="/logs/run.jsonl")
    jobs = repo.listar_jobs_por_obra(conn, obra_id)
    assert jobs[0]["status"] == "concluido"
    assert jobs[0]["finalizado_em"] is not None


# --------------------------------------------------------------------------- #
# Drive sync state
# --------------------------------------------------------------------------- #

def test_sync_state_upsert_por_usuario(conn, membro_id):
    repo.registrar_sync_state(
        conn, membro_id=membro_id, pasta_drive_id="pasta-ana",
        ultimo_arquivo_hash="h1",
    )
    repo.registrar_sync_state(
        conn, membro_id=membro_id, pasta_drive_id="pasta-ana",
        ultimo_arquivo_hash="h2", ultimo_scan_status="drive_indisponivel",
    )
    estado = repo.obter_sync_state(conn, membro_id)
    assert estado["ultimo_arquivo_hash"] == "h2"  # upsert, não duplica
    assert estado["ultimo_scan_status"] == "drive_indisponivel"
    n = conn.execute("SELECT COUNT(*) FROM portal_drive_sync_state").fetchone()[0]
    assert n == 1


# --------------------------------------------------------------------------- #
# Comentários T0
# --------------------------------------------------------------------------- #

def test_inserir_comentario_namespace_equipe(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra Coment", pasta_drive_id="pc",
    )
    repo.inserir_comentario(
        conn, obra_id=obra_id, membro_id=membro_id,
        texto="chapa PL_003 errada", tipo="erro", classe="PL", item_id="PL_003",
    )
    coments = repo.listar_comentarios_por_obra(conn, obra_id)
    assert len(coments) == 1
    assert coments[0]["namespace"] == "equipe"
    assert coments[0]["tipo"] == "erro"
    assert coments[0]["exportado_triagem"] == 0

    # bandeja de triagem do dono
    triagem = repo.listar_comentarios_para_triagem(conn)
    assert len(triagem) == 1
    repo.marcar_comentario_exportado(conn, coments[0]["id"])
    assert repo.listar_comentarios_para_triagem(conn) == []


def test_comentario_rejeita_namespace_diferente_de_equipe(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra NS", pasta_drive_id="pns",
    )
    # CHECK (namespace = 'equipe') no schema deve barrar qualquer outro valor
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            """INSERT INTO portal_comentarios_equipe
               (id, obra_id, membro_id, namespace, texto)
               VALUES ('x', ?, ?, 'dono', 'teste')""",
            (obra_id, membro_id),
        )


# --------------------------------------------------------------------------- #
# N5 releases — snapshot de certificação (R9)
# --------------------------------------------------------------------------- #

def test_registrar_n5_release_com_snapshot(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra N5", pasta_drive_id="pn5",
    )
    job_id = repo.enfileirar_job(conn, obra_id=obra_id)
    rel_id = repo.registrar_n5_release(
        conn, obra_id=obra_id, classe="FV", liberado_por=membro_id,
        status_certificacao="beta", pavimento="13", engine_version="commit-abc",
        job_id=job_id, dxf_hash="dxf-hash-xyz",
    )
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    assert len(releases) == 1
    assert releases[0]["id"] == rel_id
    assert releases[0]["status_certificacao"] == "beta"  # snapshot congelado
    assert releases[0]["classe"] == "FV"

    # auditoria R9: expõe login + rótulo do momento
    aud = repo.auditoria_n5(conn)
    assert aud[0]["liberado_por"] == "ana"
    assert aud[0]["status_no_momento_da_liberacao"] == "beta"
    assert aud[0]["obra"] == "Obra N5"


def test_n5_snapshot_nao_muda_com_reliberacao(conn, membro_id):
    """Re-liberações são eventos distintos append-only; o snapshot antigo não muda."""
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra N5 Re", pasta_drive_id="pn5r",
    )
    repo.registrar_n5_release(
        conn, obra_id=obra_id, classe="PL", liberado_por=membro_id,
        status_certificacao="beta",
    )
    repo.registrar_n5_release(
        conn, obra_id=obra_id, classe="PL", liberado_por=membro_id,
        status_certificacao="certificado",
    )
    releases = repo.listar_n5_releases_por_obra(conn, obra_id)
    status = {r["status_certificacao"] for r in releases}
    assert status == {"beta", "certificado"}  # dois eventos preservados
    assert len(releases) == 2


def test_n5_rejeita_classe_invalida(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra N5 Inv", pasta_drive_id="pn5i",
    )
    with pytest.raises(ValueError):
        repo.registrar_n5_release(
            conn, obra_id=obra_id, classe="XX", liberado_por=membro_id,
            status_certificacao="beta",
        )
