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
    "portal_obra_pavimentos",
    "portal_jobs",
    "portal_drive_sync_state",
    "portal_comentarios_equipe",
    "portal_apontamentos_ui",
    "portal_apontamento_sessoes",
    "portal_apontamento_paginas",
    "portal_n5_releases",
    "portal_n5_validacoes",
    "portal_documentos",  # migration 002 (2026-07-06)
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
    # tabela de versão registrou as migrations 001..017.
    # ver CHANGELOG das migrations
    # em portal/db/migrations/ pro histórico completo)
    ver = conn.execute("SELECT MAX(version) FROM portal_schema_version").fetchone()[0]
    assert ver == 17


def test_init_db_idempotente(tmp_path):
    db_path = tmp_path / "portal_data.db"
    c1 = connection.init_db(db_path)
    c1.close()
    # rodar de novo não duplica versão nem quebra
    c2 = connection.init_db(db_path)
    n = c2.execute("SELECT COUNT(*) FROM portal_schema_version").fetchone()[0]
    assert n == 17  # 001..017, cada migration registra 1 linha
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


def test_ordem_manual_inclui_pavimento_sem_dxf_e_tipo(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Ordem", pasta_drive_id="p")
    assert repo.obter_obra(conn, obra_id)["comportamento"] == "misto"
    rows = repo.salvar_pavimentos_obra(conn, obra_id, [
        {"pavimento": "TERREO"}, {"pavimento": "TIPO", "tipo": {"de": 2, "ate": 10}},
        {"pavimento": "COBERTURA"},
    ])
    assert [r["pavimento"] for r in rows] == ["TERREO", "TIPO", "COBERTURA"]
    assert rows[1]["anterior"] == "TERREO" and rows[1]["proximo"] == "COBERTURA"
    assert rows[1]["tipo"] == {"de": 2, "ate": 10}
    assert repo.listar_pavimentos_obra(conn, obra_id) == rows
    with pytest.raises(ValueError):
        repo.salvar_pavimentos_obra(conn, obra_id, [{"pavimento": "TIPO", "tipo": {"de": 10, "ate": 2}}])
    assert repo.listar_pavimentos_obra(conn, obra_id) == rows


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


def test_enfileirar_job_unico_por_meta_bloqueia_duplicata_ativa(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra Job Unico", pasta_drive_id="pju",
    )
    meta = {"etapa": "sa_item", "secao": "lajes", "item": "L301", "pav": "13_PAV"}
    primeiro, criado = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "secao", "item", "pav"),
    )
    repetido, criado_repetido = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "secao", "item", "pav"),
    )
    assert criado is True
    assert criado_repetido is False
    assert repetido == primeiro
    assert repo.obter_job_meta(conn, primeiro) == meta

    repo.finalizar_job(conn, primeiro, "concluido")
    novo, criado_novo = repo.enfileirar_job_unico_por_meta(
        conn, obra_id=obra_id, meta=meta,
        chaves=("etapa", "secao", "item", "pav"),
    )
    assert criado_novo is True
    assert novo != primeiro


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


def test_aprovacao_n5_fica_vinculada_ao_release(conn, membro_id):
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Obra N5 Validada", pasta_drive_id="pn5v",
    )
    primeiro = repo.registrar_n5_release(
        conn, obra_id=obra_id, classe="LJ", liberado_por=membro_id,
        status_certificacao="beta", pavimento="13_PAV",
    )
    repo.aprovar_n5_release(
        conn, release_id=primeiro, obra_id=obra_id, classe="LJ",
        pavimento="13_PAV", aprovado_por=membro_id,
    )
    segundo = repo.registrar_n5_release(
        conn, obra_id=obra_id, classe="LJ", liberado_por=membro_id,
        status_certificacao="beta", pavimento="13_PAV",
    )
    aprovados = repo.listar_n5_validacoes_por_obra(conn, obra_id)
    assert {item["release_id"] for item in aprovados} == {primeiro}
    assert segundo not in {item["release_id"] for item in aprovados}


# --------------------------------------------------------------------------- #
# portal_documentos — obra vira container de N documentos (2026-07-06)
# --------------------------------------------------------------------------- #

def test_criar_obra_com_descricao_sem_arquivo(conn, membro_id):
    """Fluxo novo: obra criada só com nome+descricao, sem arquivo nenhum ainda."""
    obra_id = repo.criar_obra(
        conn, membro_id=membro_id, nome="Edificio Aurora",
        descricao="Torre residencial 14 pavimentos", pasta_drive_id="pasta-obra-1",
    )
    obra = repo.obter_obra(conn, obra_id)
    assert obra["nome"] == "Edificio Aurora"
    assert obra["descricao"] == "Torre residencial 14 pavimentos"
    assert obra["arquivo_nome"] is None  # nenhum arquivo — é só o container


def test_criar_e_listar_documentos_de_uma_obra(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra X", pasta_drive_id="p")
    d1 = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="13_PAV_PL.dxf",
        classe_sugerida="PIL", pavimento_sugerido="13_PAV", status="classificado",
    )
    d2 = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="13_PAV_LV.dxf",
        classe_sugerida="LV", pavimento_sugerido="13_PAV", status="classificado",
    )
    docs = repo.listar_documentos_por_obra(conn, obra_id)
    assert len(docs) == 2
    assert {d["id"] for d in docs} == {d1, d2}
    assert {d["arquivo_nome"] for d in docs} == {"13_PAV_PL.dxf", "13_PAV_LV.dxf"}


def test_documento_dedup_por_hash_dentro_da_mesma_obra(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Y", pasta_drive_id="p")
    repo.criar_documento(conn, obra_id=obra_id, arquivo_nome="a.dxf", arquivo_hash="h1")
    assert repo.obter_documento_por_hash(conn, obra_id, "h1") is not None
    assert repo.obter_documento_por_hash(conn, obra_id, "h-inexistente") is None


def test_documento_mesmo_hash_em_obras_diferentes_nao_colide(conn, membro_id):
    """Dedup é por (obra_id, hash) — o MESMO arquivo pode ir para obras diferentes."""
    obra_1 = repo.criar_obra(conn, membro_id=membro_id, nome="Obra A", pasta_drive_id="p1")
    obra_2 = repo.criar_obra(conn, membro_id=membro_id, nome="Obra B", pasta_drive_id="p2")
    repo.criar_documento(conn, obra_id=obra_1, arquivo_nome="a.dxf", arquivo_hash="h-comum")
    # não deve levantar (UNIQUE é por obra_id+hash, não só hash)
    repo.criar_documento(conn, obra_id=obra_2, arquivo_nome="a.dxf", arquivo_hash="h-comum")
    assert repo.obter_documento_por_hash(conn, obra_1, "h-comum") is not None
    assert repo.obter_documento_por_hash(conn, obra_2, "h-comum") is not None


def test_sincronizar_dxf_convertido_cria_e_atualiza_sem_duplicar(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Convertida", pasta_drive_id="p")
    origem_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="14_PAV.dwg",
        pavimento_sugerido="14_PAV", tipo_documento_confirmado="Bruto",
        status="revisar",
    )
    origem = repo.obter_documento(conn, origem_id)

    primeiro = repo.sincronizar_documento_dxf_convertido(
        conn, obra_id=obra_id, documento_origem=origem,
        arquivo_nome="14_PAV.dxf", local_path="/obra/entrada/14_PAV.dxf",
        arquivo_hash="hash-dxf-1", status="revisar",
        pavimento_confirmado="14_PAV",
    )
    segundo = repo.sincronizar_documento_dxf_convertido(
        conn, obra_id=obra_id, documento_origem=origem,
        arquivo_nome="14_pav.DXF", local_path="/obra/entrada/14_pav.DXF",
        arquivo_hash="hash-dxf-2", status="classificado",
        pavimento_confirmado="14_PAV",
    )

    assert segundo == primeiro
    docs = repo.listar_documentos_por_obra(conn, obra_id)
    assert len(docs) == 2
    dxf = next(d for d in docs if d["id"] == primeiro)
    assert dxf["status"] == "classificado"
    assert dxf["pavimento_confirmado"] == "14_PAV"
    assert dxf["tipo_documento_confirmado"] == "Bruto"
    assert dxf["local_path"] == "/obra/entrada/14_pav.DXF"


def test_atualizar_classificacao_documento_confirma_sem_apagar_o_resto(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Z", pasta_drive_id="p")
    doc_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="x.dxf",
        classe_sugerida="FV", pavimento_sugerido=None, status="revisar",
    )
    # humano confirma o pavimento que faltava, sem re-informar a classe
    repo.atualizar_classificacao_documento(
        conn, doc_id, pavimento_confirmado="TERREO", status="classificado",
    )
    doc = repo.obter_documento(conn, doc_id)
    assert doc["classe_sugerida"] == "FV"  # preservado
    assert doc["pavimento_confirmado"] == "TERREO"
    assert doc["status"] == "classificado"


# --------------------------------------------------------------------------- #
# tipo_documento (migration 005, 2026-07-07) — eixo novo Bruto/Detalhe/PDF
# --------------------------------------------------------------------------- #

def test_criar_documento_grava_tipo_documento_sugerido(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Tipo", pasta_drive_id="p")
    doc_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="memorial.pdf", tipo_documento_sugerido="PDF",
    )
    doc = repo.obter_documento(conn, doc_id)
    assert doc["tipo_documento_sugerido"] == "PDF"
    assert doc["tipo_documento_confirmado"] is None


def test_criar_documento_com_confirmado_direto_no_upload(conn, membro_id):
    """[2026-07-07] usuário escolhe tipo/pavimento padrão no momento do
    upload (lote inteiro) — grava direto como confirmado, sem esperar a
    triagem revisar depois."""
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Lote Padrao", pasta_drive_id="p")
    doc_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="a.dxf",
        tipo_documento_confirmado="Detalhe", pavimento_confirmado="13_PAV",
    )
    doc = repo.obter_documento(conn, doc_id)
    assert doc["tipo_documento_confirmado"] == "Detalhe"
    assert doc["pavimento_confirmado"] == "13_PAV"
    assert doc["tipo_documento_sugerido"] is None  # nenhuma sugestão automática rodou aqui


def test_atualizar_classificacao_documento_confirma_tipo_documento(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Tipo2", pasta_drive_id="p")
    doc_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="det.dxf", tipo_documento_sugerido="Detalhe",
    )
    repo.atualizar_classificacao_documento(conn, doc_id, tipo_documento_confirmado="Bruto")
    doc = repo.obter_documento(conn, doc_id)
    assert doc["tipo_documento_sugerido"] == "Detalhe"  # sugestão original preservada
    assert doc["tipo_documento_confirmado"] == "Bruto"  # correção humana


def test_mover_documento_para_indeterminado_limpa_pavimento_e_tipo(conn, membro_id):
    """[2026-07-07] Drag-and-drop devolvendo um doc a "Indeterminado" — LIMPA
    de verdade (diferente de atualizar_classificacao_documento, que só
    preserva quando recebe None)."""
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Indet", pasta_drive_id="p")
    doc_id = repo.criar_documento(
        conn, obra_id=obra_id, arquivo_nome="x.dxf",
        pavimento_sugerido="13_PAV", tipo_documento_sugerido="Bruto",
    )
    repo.atualizar_classificacao_documento(
        conn, doc_id, pavimento_confirmado="13_PAV", tipo_documento_confirmado="Bruto",
    )
    repo.mover_documento_para_indeterminado(conn, doc_id)
    doc = repo.obter_documento(conn, doc_id)
    assert doc["pavimento_confirmado"] is None
    assert doc["tipo_documento_confirmado"] is None
    assert doc["pavimento_sugerido"] == "13_PAV"  # sugestão original nunca se apaga


def test_contar_documentos_por_status(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra W", pasta_drive_id="p")
    repo.criar_documento(conn, obra_id=obra_id, arquivo_nome="a.dxf", status="classificado")
    repo.criar_documento(conn, obra_id=obra_id, arquivo_nome="b.dxf", status="classificado")
    repo.criar_documento(conn, obra_id=obra_id, arquivo_nome="c.dxf", status="revisar")
    contagem = repo.contar_documentos_por_status(conn, obra_id)
    assert contagem == {"classificado": 2, "revisar": 1}


# --------------------------------------------------------------------------- #
# Cabeçalho da obra + nome de exibição do documento (migration 004, 2026-07-07)
# --------------------------------------------------------------------------- #

def test_atualizar_cabecalho_obra_grava_todos_os_campos(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Y", pasta_drive_id="p")
    repo.atualizar_cabecalho_obra(
        conn, obra_id,
        nome="Processamento Torre Norte", cliente="Construtora Aurora",
        data_solicitacao="2026-07-01", data_entrega="2026-07-20",
        criterios_cliente="NBR 6118, tolerância 2cm", observacoes="Urgente",
    )
    obra = repo.obter_obra(conn, obra_id)
    assert obra["nome"] == "Processamento Torre Norte"
    assert obra["cliente"] == "Construtora Aurora"
    assert obra["data_solicitacao"] == "2026-07-01"
    assert obra["data_entrega"] == "2026-07-20"
    assert obra["criterios_cliente"] == "NBR 6118, tolerância 2cm"
    assert obra["observacoes"] == "Urgente"


def test_atualizar_cabecalho_obra_parcial_preserva_o_resto(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Z", pasta_drive_id="p")
    repo.atualizar_cabecalho_obra(conn, obra_id, cliente="Cliente A")
    repo.atualizar_cabecalho_obra(conn, obra_id, observacoes="Nota qualquer")
    obra = repo.obter_obra(conn, obra_id)
    assert obra["cliente"] == "Cliente A"  # preservado da 1a chamada
    assert obra["observacoes"] == "Nota qualquer"
    assert obra["nome"] == "Obra Z"  # nunca tocado, preservado


def test_atualizar_nome_exibicao_documento(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Nome Doc", pasta_drive_id="p")
    doc_id = repo.criar_documento(conn, obra_id=obra_id, arquivo_nome="13_PAV_PL_v3_final2.dxf")
    repo.atualizar_nome_exibicao_documento(conn, doc_id, "Pilares - 13o pavimento")
    doc = repo.obter_documento(conn, doc_id)
    assert doc["nome_exibicao"] == "Pilares - 13o pavimento"
    assert doc["arquivo_nome"] == "13_PAV_PL_v3_final2.dxf"  # arquivo real intocado


# --------------------------------------------------------------------------- #
# Validação de campo (migration 008, 2026-07-13 — harmonização selo rosa)
# --------------------------------------------------------------------------- #

def test_set_campo_validado_grava_e_lista(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo", pasta_drive_id="p")
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", True, validado_por="ana")
    campos = repo.listar_campos_validados(conn, obra_id, "Térreo", "pilar", "P1")
    assert [c["field_id"] for c in campos] == ["nivel"]
    assert campos[0]["validado_por"] == "ana"
    assert campos[0]["validado_em"] is not None


def test_set_campo_validado_false_remove_a_linha(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo 2", pasta_drive_id="p")
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", True)
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", False)
    assert repo.listar_campos_validados(conn, obra_id, "Térreo", "pilar", "P1") == []


def test_set_campo_validado_e_idempotente_e_atualiza_validado_por(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo 3", pasta_drive_id="p")
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", True, validado_por="ana")
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", True, validado_por="bruno")
    campos = repo.listar_campos_validados(conn, obra_id, "Térreo", "pilar", "P1")
    assert len(campos) == 1
    assert campos[0]["validado_por"] == "bruno"


def test_set_campo_validado_grava_titulo(conn, membro_id):
    """[2026-07-13, Fase 3.4] titulo persiste pro app desktop regex-parsear
    segmentos de viga ("V101 (segmento N)") no sync."""
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo Titulo", pasta_drive_id="p")
    repo.set_campo_validado(
        conn, obra_id, "Térreo", "fundo", "uid-123", "Comprimento", True,
        validado_por="ana", titulo="V101 (segmento 2)",
    )
    campos = repo.listar_campos_validados(conn, obra_id, "Térreo", "fundo", "uid-123")
    assert campos[0]["titulo"] == "V101 (segmento 2)"


def test_listar_campos_validados_por_obra_agrupa_pavimento_classe_item(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo 4", pasta_drive_id="p")
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "nivel", True)
    repo.set_campo_validado(conn, obra_id, "Térreo", "pilar", "P1", "classificacao", True)
    repo.set_campo_validado(conn, obra_id, "1_PAV", "laje", "L2", "laje_dim", True)
    todos = repo.listar_campos_validados_por_obra(conn, obra_id)
    assert len(todos) == 3
    chaves = {(c["pavimento"], c["classe"], c["item_id"], c["field_id"]) for c in todos}
    assert ("Térreo", "PILAR", "P1", "nivel") in chaves
    assert ("1_PAV", "LAJE", "L2", "laje_dim") in chaves


def test_listar_campos_validados_e_vazia_sem_dado(conn, membro_id):
    obra_id = repo.criar_obra(conn, membro_id=membro_id, nome="Obra Campo 5", pasta_drive_id="p")
    assert repo.listar_campos_validados(conn, obra_id, "Térreo", "pilar", "P9") == []
    assert repo.listar_campos_validados_por_obra(conn, obra_id) == []
