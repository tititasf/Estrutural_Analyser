"""Camada de acesso a dados do portal (stdlib sqlite3 apenas — sem ORM, HANDOFF §1).

Motor geral: nenhuma função hardcoda obra ou usuário específico. Toda entidade
recebe seus dados por parâmetro. IDs de entidade são TEXT (uuid) para casar com o
padrão do Arete (HANDOFF §2).

Regra de fronteira: nada aqui escreve em project_data.vision. O status de
certificação do N5 é recebido como SNAPSHOT já lido em modo read-only pelo chamador
(HANDOFF §2.6/§5) — o repositório apenas o congela na linha de auditoria.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from typing import Any, Optional

# Domínio real de assemble_n5 (src/core/n5_assembler.py:332) — validado aqui também.
CLASSES_N5 = ("PL", "LV", "FV", "LJ")
_STATUS_CERT = ("certificado", "beta")


def _new_id() -> str:
    return str(uuid.uuid4())


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[dict[str, Any]]:
    return dict(row) if row is not None else None


# --------------------------------------------------------------------------- #
# Membros (DP-3)
# --------------------------------------------------------------------------- #

def criar_membro(
    conn: sqlite3.Connection,
    *,
    login: str,
    nome: str,
    senha_hash: str,
    email: Optional[str] = None,
    papel: str = "membro",
    drive_folder_id: Optional[str] = None,
    trocar_senha: bool = False,
) -> str:
    """Cria um membro. senha_hash já vem hasheada (bcrypt/argon2) — nunca senha em claro."""
    membro_id = _new_id()
    conn.execute(
        """INSERT INTO portal_membros
           (id, login, nome, email, senha_hash, papel, drive_folder_id, trocar_senha)
           VALUES (?,?,?,?,?,?,?,?)""",
        (membro_id, login, nome, email, senha_hash, papel, drive_folder_id,
         1 if trocar_senha else 0),
    )
    conn.commit()
    return membro_id


def atualizar_senha_membro(
    conn: sqlite3.Connection, membro_id: str, senha_hash: str, *, trocar_senha: bool = False,
) -> None:
    """Grava a nova senha (já hasheada) e liga/desliga a troca obrigatória."""
    conn.execute(
        """UPDATE portal_membros
           SET senha_hash = ?, trocar_senha = ?,
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (senha_hash, 1 if trocar_senha else 0, membro_id),
    )
    conn.commit()


def listar_membros(
    conn: sqlite3.Connection, *, apenas_ativos: bool = False
) -> list[dict[str, Any]]:
    sql = "SELECT * FROM portal_membros"
    if apenas_ativos:
        sql += " WHERE ativo = 1"
    sql += " ORDER BY login"
    return [dict(r) for r in conn.execute(sql).fetchall()]


def obter_membro_por_login(
    conn: sqlite3.Connection, login: str
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM portal_membros WHERE login = ?", (login,)
    ).fetchone()
    return _row_to_dict(row)


def obter_membro_por_login_normalizado(
    conn: sqlite3.Connection, login: str
) -> Optional[dict[str, Any]]:
    """Busca tolerante a espaços e maiúsculas — só para o caminho de LOGIN.

    A busca exata (`obter_membro_por_login`) continua sendo a usada pelo cookie,
    que sempre carrega o valor canônico gravado no banco. Aqui é o humano
    digitando: "Thierry.tasf@gmail.com" e "thierry.tasf@gmail.com " são a mesma
    pessoa, e recusar isso só produz "usuário incorreto" sem explicação.
    """
    alvo = (login or "").strip()
    if not alvo:
        return None
    row = conn.execute(
        "SELECT * FROM portal_membros WHERE LOWER(TRIM(login)) = LOWER(?)", (alvo,)
    ).fetchone()
    return _row_to_dict(row)


def atualizar_drive_folder_membro(
    conn: sqlite3.Connection, membro_id: str, drive_folder_id: str
) -> None:
    """[2026-07-06] Associa/troca a pasta do Drive de um membro JA existente.

    seed.py só sabia CRIAR membro com pasta; o dono também quer pasta própria
    depois de já ter sido cadastrado (--sem-drive) — sem isso teria que apagar
    e recriar o membro (perderia o id, jobs, comentários já ligados a ele).
    """
    conn.execute(
        """UPDATE portal_membros
           SET drive_folder_id = ?,
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (drive_folder_id, membro_id),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Obras
# --------------------------------------------------------------------------- #

def criar_obra(
    conn: sqlite3.Connection,
    *,
    membro_id: str,
    nome: str,
    pasta_drive_id: str,
    arquivo_drive_id: Optional[str] = None,
    arquivo_nome: Optional[str] = None,
    arquivo_hash: Optional[str] = None,
    estado: str = "aguardando_ingestao",
    local_path: Optional[str] = None,
    descricao: Optional[str] = None,
) -> str:
    """[2026-07-06] `descricao` novo — obra virou CONTAINER de documentos
    (portal_documentos), não mais "1 arquivo = 1 obra". `arquivo_*` seguem
    aceitos por compat (fluxo legado / obras já existentes antes da migration
    002), mas o fluxo novo (POST /obras/criar) não os popula."""
    obra_id = _new_id()
    conn.execute(
        """INSERT INTO portal_obras
           (id, membro_id, nome, descricao, pasta_drive_id, arquivo_drive_id,
            arquivo_nome, arquivo_hash, estado, local_path)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (obra_id, membro_id, nome, descricao, pasta_drive_id, arquivo_drive_id,
         arquivo_nome, arquivo_hash, estado, local_path),
    )
    conn.commit()
    return obra_id


# --------------------------------------------------------------------------- #
# Documentos (portal_documentos) — 2026-07-06: obra vira container de N docs.
# --------------------------------------------------------------------------- #

def criar_documento(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    arquivo_nome: str,
    arquivo_drive_id: Optional[str] = None,
    arquivo_hash: Optional[str] = None,
    local_path: Optional[str] = None,
    classe_sugerida: Optional[str] = None,
    pavimento_sugerido: Optional[str] = None,
    tipo_documento_sugerido: Optional[str] = None,
    classe_confirmada: Optional[str] = None,
    pavimento_confirmado: Optional[str] = None,
    tipo_documento_confirmado: Optional[str] = None,
    status: str = "pendente",
) -> str:
    """`*_confirmado` no momento da criação [2026-07-07] — quando o usuário já
    escolhe tipo/pavimento no upload (em vez de só confirmar depois na
    triagem), grava direto como confirmado, não como sugestão."""
    doc_id = _new_id()
    conn.execute(
        """INSERT INTO portal_documentos
           (id, obra_id, arquivo_nome, arquivo_drive_id, arquivo_hash, local_path,
            classe_sugerida, pavimento_sugerido, tipo_documento_sugerido,
            classe_confirmada, pavimento_confirmado, tipo_documento_confirmado, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (doc_id, obra_id, arquivo_nome, arquivo_drive_id, arquivo_hash, local_path,
         classe_sugerida, pavimento_sugerido, tipo_documento_sugerido,
         classe_confirmada, pavimento_confirmado, tipo_documento_confirmado, status),
    )
    conn.commit()
    return doc_id


def obter_documento(conn: sqlite3.Connection, doc_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT * FROM portal_documentos WHERE id = ?", (doc_id,)).fetchone()
    return _row_to_dict(row)


def obter_documento_por_hash(
    conn: sqlite3.Connection, obra_id: str, arquivo_hash: str
) -> Optional[dict[str, Any]]:
    """Dedup: mesmo arquivo (hash) já enviado para ESTA obra."""
    row = conn.execute(
        "SELECT * FROM portal_documentos WHERE obra_id = ? AND arquivo_hash = ?",
        (obra_id, arquivo_hash),
    ).fetchone()
    return _row_to_dict(row)


def listar_documentos_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM portal_documentos WHERE obra_id = ? ORDER BY created_at, id",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def contar_documentos_por_status(conn: sqlite3.Connection, obra_id: str) -> dict[str, int]:
    """Resumo pra tela da obra (ex.: "3 classificados, 1 a revisar")."""
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM portal_documentos WHERE obra_id = ? GROUP BY status",
        (obra_id,),
    ).fetchall()
    return {r["status"]: r["n"] for r in rows}


def obter_sa_validacao(conn: sqlite3.Connection, obra_id: str, bruto_id: str) -> dict[str, Any]:
    """Validação "item completo" do Structural Analyzer pra 1 pavimento
    (bruto_id). Sempre devolve um dict — {'validado': False} se nunca validado."""
    row = conn.execute(
        "SELECT * FROM portal_sa_validacao WHERE obra_id = ? AND bruto_id = ?",
        (obra_id, bruto_id),
    ).fetchone()
    if row is None:
        return {"obra_id": obra_id, "bruto_id": bruto_id, "validado": False, "validado_por": None, "validado_em": None}
    d = dict(row)
    d["validado"] = bool(d["validado"])
    return d


def listar_sa_validacoes_por_obra(conn: sqlite3.Connection, obra_id: str) -> dict[str, bool]:
    """{bruto_id: validado} pra TODOS os pavimentos já tocados dessa obra —
    usado pela app pra espelhar em lote sem 1 GET por pavimento."""
    rows = conn.execute(
        "SELECT bruto_id, validado FROM portal_sa_validacao WHERE obra_id = ?", (obra_id,)
    ).fetchall()
    return {r["bruto_id"]: bool(r["validado"]) for r in rows}


def obter_validacao_classe(conn: sqlite3.Connection, obra_id: str, classe: str) -> dict[str, Any]:
    """Estado de validação N1+N3 (etapa 5) pra 1 classe — {'n1_ok': False,
    'n3_ok': False, 'validado': False, ...} se nunca validada."""
    row = conn.execute(
        "SELECT * FROM portal_validacoes WHERE obra_id = ? AND classe = ?",
        (obra_id, classe.upper()),
    ).fetchone()
    if row is None:
        return {"obra_id": obra_id, "classe": classe.upper(), "n1_ok": False, "n3_ok": False,
                "validado": False, "validado_por": None, "validado_em": None, "item_id": None}
    d = dict(row)
    d["n1_ok"] = bool(d["n1_ok"])
    d["n3_ok"] = bool(d["n3_ok"])
    d["validado"] = d["n1_ok"] and d["n3_ok"]
    return d


def listar_validacoes_por_obra(conn: sqlite3.Connection, obra_id: str) -> dict[str, dict]:
    """{classe: {n1_ok, n3_ok, validado}} de todas as classes já tocadas —
    usado pela app pra espelhar em lote."""
    rows = conn.execute("SELECT * FROM portal_validacoes WHERE obra_id = ?", (obra_id,)).fetchall()
    out = {}
    for r in rows:
        d = dict(r)
        d["n1_ok"] = bool(d["n1_ok"])
        d["n3_ok"] = bool(d["n3_ok"])
        d["validado"] = d["n1_ok"] and d["n3_ok"]
        out[d["classe"]] = d
    return out


def set_validacao_classe(
    conn: sqlite3.Connection, obra_id: str, classe: str, n1_ok: bool, n3_ok: bool,
    item_id: Optional[str], validado_por: Optional[str],
) -> dict[str, Any]:
    """Grava a validação — merge protetivo: NUNCA rebaixa `n1_ok`/`n3_ok` já
    True (protege validação já feita, seja pela web seja puxada da app)."""
    conn.execute(
        """
        INSERT INTO portal_validacoes (obra_id, classe, n1_ok, n3_ok, item_id, validado_por, validado_em)
        VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        ON CONFLICT(obra_id, classe) DO UPDATE SET
            n1_ok=CASE WHEN portal_validacoes.n1_ok=1 THEN 1 ELSE excluded.n1_ok END,
            n3_ok=CASE WHEN portal_validacoes.n3_ok=1 THEN 1 ELSE excluded.n3_ok END,
            item_id=excluded.item_id,
            validado_por=excluded.validado_por,
            validado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now')
        """,
        (obra_id, classe.upper(), int(n1_ok), int(n3_ok), item_id, validado_por),
    )
    conn.commit()
    return obter_validacao_classe(conn, obra_id, classe)


def set_sa_validado(
    conn: sqlite3.Connection, obra_id: str, bruto_id: str, validado: bool, validado_por: Optional[str] = None
) -> None:
    conn.execute(
        """
        INSERT INTO portal_sa_validacao (obra_id, bruto_id, validado, validado_por, validado_em)
        VALUES (?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'))
        ON CONFLICT(obra_id, bruto_id) DO UPDATE SET
            validado=excluded.validado,
            validado_por=excluded.validado_por,
            validado_em=excluded.validado_em
        """,
        (obra_id, bruto_id, int(validado), validado_por),
    )
    conn.commit()


def set_campo_validado(
    conn: sqlite3.Connection, obra_id: str, pavimento: str, classe: str, item_id: str,
    field_id: str, validado: bool, validado_por: Optional[str] = None,
    titulo: Optional[str] = None,
) -> None:
    """Marca/desmarca a validação de 1 campo específico de 1 item (granularidade
    real de campo — gera a origem `humano_portal` no app desktop via sync,
    ver docs/CONVENCAO-SELOS-VALIDACAO.md). `validado=False` remove a linha
    (campo some da lista de validados, igual `remover_validacao_campo`).
    `titulo` [2026-07-13, Fase 3.4] — só relevante pra classes de segmento
    (fundo/lateral_*): o app desktop regex-parseia "V101 (segmento N)" pra
    resolver o field_id real (`{prefix}_seg_{idx}{sufixo}`), já que o
    `item_id` de segmento é um uid geométrico opaco."""
    if not validado:
        conn.execute(
            "DELETE FROM portal_validacoes_campo WHERE obra_id=? AND pavimento=? AND classe=? AND item_id=? AND field_id=?",
            (obra_id, pavimento, classe.upper(), item_id, field_id),
        )
        conn.commit()
        return
    conn.execute(
        """
        INSERT INTO portal_validacoes_campo (obra_id, pavimento, classe, item_id, field_id, validado_por, validado_em, titulo)
        VALUES (?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)
        ON CONFLICT(obra_id, pavimento, classe, item_id, field_id) DO UPDATE SET
            validado_por=excluded.validado_por,
            validado_em=excluded.validado_em,
            titulo=excluded.titulo
        """,
        (obra_id, pavimento, classe.upper(), item_id, field_id, validado_por, titulo),
    )
    conn.commit()


def listar_campos_validados(
    conn: sqlite3.Connection, obra_id: str, pavimento: str, classe: str, item_id: str,
) -> list[dict[str, Any]]:
    """Campos validados de 1 item — [{field_id, validado_por, validado_em, titulo}, ...]."""
    rows = conn.execute(
        "SELECT field_id, validado_por, validado_em, titulo FROM portal_validacoes_campo "
        "WHERE obra_id=? AND pavimento=? AND classe=? AND item_id=?",
        (obra_id, pavimento, classe.upper(), item_id),
    ).fetchall()
    return [dict(r) for r in rows]


def listar_campos_validados_por_obra(conn: sqlite3.Connection, obra_id: str) -> list[dict[str, Any]]:
    """Todos os campos validados dessa obra (todas classes/pavimentos/itens) —
    usado pela app pra espelhar em lote, igual `listar_sa_validacoes_por_obra`."""
    rows = conn.execute(
        "SELECT pavimento, classe, item_id, field_id, validado_por, validado_em, titulo "
        "FROM portal_validacoes_campo WHERE obra_id=?",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def atualizar_classificacao_documento(
    conn: sqlite3.Connection,
    doc_id: str,
    *,
    classe_confirmada: Optional[str] = None,
    pavimento_confirmado: Optional[str] = None,
    tipo_documento_confirmado: Optional[str] = None,
    status: Optional[str] = None,
    erro_msg: Optional[str] = None,
) -> None:
    """Confirma/edita a classificação de UM documento (triagem manual ou em lote).

    Só atualiza os campos passados (COALESCE preserva o resto) — permite chamar
    só com `status` (ex.: marcar 'erro') sem apagar uma classificação já feita.
    `None` = "não mexeu" (contrato original, testado); pra LIMPAR um campo de
    propósito pra NULL (drag-and-drop devolvendo um doc a "Indeterminado"),
    use `mover_documento_para_indeterminado` abaixo.
    """
    conn.execute(
        """UPDATE portal_documentos
           SET classe_confirmada = COALESCE(?, classe_confirmada),
               pavimento_confirmado = COALESCE(?, pavimento_confirmado),
               tipo_documento_confirmado = COALESCE(?, tipo_documento_confirmado),
               status = COALESCE(?, status),
               erro_msg = COALESCE(?, erro_msg),
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (classe_confirmada, pavimento_confirmado, tipo_documento_confirmado, status, erro_msg, doc_id),
    )
    conn.commit()


def mover_documento_para_indeterminado(conn: sqlite3.Connection, doc_id: str) -> None:
    # [FIX] usava '' (string vazia) em vez de NULL — quebrava o contrato
    # testado (pavimento_confirmado/tipo_documento_confirmado devem virar
    # None de verdade). A docstring da função vizinha (atualizar_classificacao_
    # documento) já dizia que a intenção era NULL.
    conn.execute(
        """UPDATE portal_documentos
           SET pavimento_confirmado = NULL, tipo_documento_confirmado = NULL,
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (doc_id,),
    )
    conn.commit()


def atualizar_nome_exibicao_documento(conn: sqlite3.Connection, doc_id: str, nome_exibicao: str) -> None:
    """[2026-07-07, migration 004] Nome de exibição editável do documento —
    diferente de arquivo_nome (o nome real do arquivo em disco, imutável)."""
    conn.execute(
        """UPDATE portal_documentos
           SET nome_exibicao = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (nome_exibicao, doc_id),
    )
    conn.commit()


def atualizar_estado_obra(
    conn: sqlite3.Connection,
    obra_id: str,
    estado: str,
    *,
    erro_msg: Optional[str] = None,
    processada_em: Optional[str] = None,
    etapa_concluida: Optional[str] = None,
) -> None:
    """Atualiza o estado da obra. erro_msg preenchido quando estado='erro' (R6).

    `etapa_concluida` [2026-07-06, migration 003] — só sobrescreve quando
    passada (COALESCE); é a última etapa (triagem/recortes/sa) que terminou
    com sucesso, usada por `_etapa_atual` pra saber precisamente em qual passo
    a obra está (o enum `estado` sozinho não distingue os passos intermediários).
    """
    conn.execute(
        """UPDATE portal_obras
           SET estado = ?,
               erro_msg = ?,
               processada_em = COALESCE(?, processada_em),
               etapa_concluida = COALESCE(?, etapa_concluida),
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (estado, erro_msg, processada_em, etapa_concluida, obra_id),
    )
    conn.commit()


def atualizar_cabecalho_obra(
    conn: sqlite3.Connection,
    obra_id: str,
    *,
    nome: Optional[str] = None,
    cliente: Optional[str] = None,
    data_solicitacao: Optional[str] = None,
    data_entrega: Optional[str] = None,
    criterios_cliente: Optional[str] = None,
    observacoes: Optional[str] = None,
) -> None:
    """[2026-07-07, migration 004] Cabeçalho de referência do processamento —
    quem pediu, prazo, critérios do cliente. Só atualiza os campos passados
    (COALESCE preserva o resto), mesmo padrão de atualizar_classificacao_documento."""
    conn.execute(
        """UPDATE portal_obras
           SET nome = COALESCE(?, nome),
               cliente = COALESCE(?, cliente),
               data_solicitacao = COALESCE(?, data_solicitacao),
               data_entrega = COALESCE(?, data_entrega),
               criterios_cliente = COALESCE(?, criterios_cliente),
               observacoes = COALESCE(?, observacoes),
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (nome, cliente, data_solicitacao, data_entrega, criterios_cliente, observacoes, obra_id),
    )
    conn.commit()


def obter_obra(conn: sqlite3.Connection, obra_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM portal_obras WHERE id = ?", (obra_id,)
    ).fetchone()
    return _row_to_dict(row)


def listar_obras_por_membro(
    conn: sqlite3.Connection, membro_id: str
) -> list[dict[str, Any]]:
    """Q1: tela principal do membro — obras por usuário, mais recentes primeiro."""
    rows = conn.execute(
        "SELECT * FROM portal_obras WHERE membro_id = ? ORDER BY created_at DESC, id",
        (membro_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def listar_todas_obras(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Q1-ADMIN [2026-07-06]: obras de TODOS os membros (papel='dono' só).

    Junta login/nome do membro dono da obra — a tela do dono precisa saber
    de quem é cada obra, não só ver tudo misturado.
    """
    rows = conn.execute(
        """SELECT portal_obras.*,
                  portal_membros.login AS membro_login,
                  portal_membros.nome AS membro_nome
           FROM portal_obras
           JOIN portal_membros ON portal_membros.id = portal_obras.membro_id
           ORDER BY portal_obras.created_at DESC, portal_obras.id"""
    ).fetchall()
    return [dict(r) for r in rows]


def obter_obra_por_hash(
    conn: sqlite3.Connection, arquivo_hash: str
) -> Optional[dict[str, Any]]:
    """Dedup do poller (Q2): antes de inserir, checa se o hash já existe."""
    row = conn.execute(
        "SELECT * FROM portal_obras WHERE arquivo_hash = ?", (arquivo_hash,)
    ).fetchone()
    return _row_to_dict(row)


# --------------------------------------------------------------------------- #
# Jobs (fila 1 por vez — exclusão real via single_instance.py; aqui só o estado)
# --------------------------------------------------------------------------- #

def enfileirar_job(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    prioridade: int = 0,
    engine_version: Optional[str] = None,
) -> str:
    job_id = _new_id()
    conn.execute(
        """INSERT INTO portal_jobs (id, obra_id, prioridade, engine_version)
           VALUES (?,?,?,?)""",
        (job_id, obra_id, prioridade, engine_version),
    )
    conn.commit()
    return job_id


def salvar_job_meta(conn: sqlite3.Connection, job_id: str, meta: dict[str, Any]) -> None:
    """Persiste o tipo/escopo do job; sobrevive a restart do portal."""
    conn.execute(
        """INSERT INTO portal_job_meta(job_id, meta_json) VALUES(?,?)
           ON CONFLICT(job_id) DO UPDATE SET
             meta_json=excluded.meta_json,
             updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
        (job_id, json.dumps(meta, ensure_ascii=False, sort_keys=True)),
    )
    conn.commit()


def limpar_erro_documento(conn: sqlite3.Connection, doc_id: str) -> None:
    """Limpa explicitamente o erro anterior após conversão/triagem bem-sucedida."""
    conn.execute(
        """UPDATE portal_documentos
           SET erro_msg = NULL,
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (doc_id,),
    )
    conn.commit()


def enfileirar_job_unico_por_meta(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    meta: dict[str, Any],
    chaves: tuple[str, ...],
    prioridade: int = 0,
    engine_version: Optional[str] = None,
) -> tuple[str, bool]:
    """Enfileira job + metadados atomicamente, reutilizando um equivalente ativo.

    O ``BEGIN IMMEDIATE`` serializa solicitações concorrentes antes da consulta.
    Assim, dois cliques/requisições simultâneos para o mesmo escopo não conseguem
    criar dois jobs, e o worker nunca enxerga um job antes de seus metadados.
    """
    job_id = _new_id()
    try:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute(
            """SELECT j.id, m.meta_json
                 FROM portal_jobs j
                 JOIN portal_job_meta m ON m.job_id=j.id
                WHERE j.obra_id=? AND (
                      j.status IN ('na_fila','executando') OR
                      (j.status='cancelado' AND j.erro_msg=?)
                )
                ORDER BY j.enfileirado_em DESC, j.rowid DESC""",
            (obra_id, PAUSA_OPERADOR),
        ).fetchall()
        for row in rows:
            try:
                existente = json.loads(row["meta_json"] or "{}")
            except (TypeError, json.JSONDecodeError):
                continue
            if all(existente.get(chave) == meta.get(chave) for chave in chaves):
                conn.commit()
                return str(row["id"]), False
        conn.execute(
            """INSERT INTO portal_jobs (id, obra_id, prioridade, engine_version)
               VALUES (?,?,?,?)""",
            (job_id, obra_id, prioridade, engine_version),
        )
        conn.execute(
            "INSERT INTO portal_job_meta(job_id, meta_json) VALUES(?,?)",
            (job_id, json.dumps(meta, ensure_ascii=False, sort_keys=True)),
        )
        conn.commit()
        return job_id, True
    except Exception:
        conn.rollback()
        raise


def obter_job_meta(conn: sqlite3.Connection, job_id: str) -> dict[str, Any]:
    row = conn.execute(
        "SELECT meta_json FROM portal_job_meta WHERE job_id=?", (job_id,)
    ).fetchone()
    if row is None:
        return {}
    try:
        value = json.loads(row["meta_json"])
    except (TypeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def criar_qa_round(
    conn: sqlite3.Connection,
    *,
    round_id: str,
    job_id: str,
    obra_id: str,
    membro_id: str,
    classe: str,
    pavimento: str,
    layer: str,
    items: list[str],
) -> None:
    with conn:
        conn.execute(
            """INSERT INTO portal_qa_rounds
               (id,job_id,obra_id,membro_id,classe,pavimento,layer)
               VALUES(?,?,?,?,?,?,?)""",
            (round_id, job_id, obra_id, membro_id, classe, pavimento, layer),
        )
        for ordinal, item in enumerate(items):
            conn.execute(
                """INSERT INTO portal_qa_items(id,round_id,item_id,ordinal)
                   VALUES(?,?,?,?)""",
                (_new_id(), round_id, item, ordinal),
            )


def enfileirar_qa_round(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    membro_id: str,
    classe: str,
    pavimento: str,
    layer: str,
    items: list[str],
    engine_version: Optional[str] = None,
) -> tuple[str, str]:
    """Cria job, metadados e rodada em uma transacao indivisivel.

    Sem esta fronteira, o worker pode consumir ``portal_jobs`` entre o commit do
    job e a gravacao do ``round_id`` e interpretar a tarefa como SA completo.
    """
    job_id = _new_id()
    round_id = _new_id()
    meta = {"etapa": "qa_agentico", "round_id": round_id}
    with conn:
        conn.execute(
            """INSERT INTO portal_jobs (id, obra_id, prioridade, engine_version)
               VALUES(?,?,?,?)""",
            (job_id, obra_id, 0, engine_version),
        )
        conn.execute(
            "INSERT INTO portal_job_meta(job_id, meta_json) VALUES(?,?)",
            (job_id, json.dumps(meta, ensure_ascii=False, sort_keys=True)),
        )
        conn.execute(
            """INSERT INTO portal_qa_rounds
               (id,job_id,obra_id,membro_id,classe,pavimento,layer)
               VALUES(?,?,?,?,?,?,?)""",
            (round_id, job_id, obra_id, membro_id, classe, pavimento, layer),
        )
        for ordinal, item in enumerate(items):
            conn.execute(
                """INSERT INTO portal_qa_items(id,round_id,item_id,ordinal)
                   VALUES(?,?,?,?)""",
                (_new_id(), round_id, item, ordinal),
            )
    return round_id, job_id


def obter_qa_round(conn: sqlite3.Connection, round_id: str) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM portal_qa_rounds WHERE id=?", (round_id,)
    ).fetchone()
    return _row_to_dict(row)


def listar_qa_items(conn: sqlite3.Connection, round_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        "SELECT * FROM portal_qa_items WHERE round_id=? ORDER BY ordinal", (round_id,)
    ).fetchall()
    return [dict(row) for row in rows]


def iniciar_qa_round(conn: sqlite3.Connection, round_id: str) -> None:
    conn.execute(
        """UPDATE portal_qa_rounds SET status='running',
           iniciado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
        (round_id,),
    )
    conn.commit()


def gravar_resultado_qa_item(conn: sqlite3.Connection, round_id: str, result: Any) -> None:
    row = conn.execute(
        "SELECT id FROM portal_qa_items WHERE round_id=? AND item_id=?",
        (round_id, result.item),
    ).fetchone()
    if row is None:
        raise KeyError(f"item QA ausente: {round_id}/{result.item}")
    qa_item_id = row["id"]
    with conn:
        conn.execute("DELETE FROM portal_qa_attempts WHERE qa_item_id=?", (qa_item_id,))
        for ordinal, attempt in enumerate(result.attempts):
            conn.execute(
                """INSERT INTO portal_qa_attempts
                   (id,qa_item_id,ordinal,provider,model_requested,effort_requested,
                    model_reported,status,failure_category,error,duration_s,
                    provider_version,raw_response_text,raw_response_sha256)
                   VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    _new_id(), qa_item_id, ordinal, attempt.provider,
                    attempt.model_requested, attempt.effort_requested,
                    attempt.model_reported, attempt.status, attempt.failure_category,
                    attempt.error, attempt.duration_s,
                    attempt.provider_version, attempt.raw_response,
                    attempt.raw_response_sha256,
                ),
            )
        conn.execute(
            """UPDATE portal_qa_items SET status=?, provider=?, model=?, verdict=?,
               note=?, suggestion_json=?, prompt_text=?, prompt_sha256=?,
               evidence_json=?, adapter_version=?, decision_authority=?,
               training_eligible=?,
               updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
            (
                result.status, result.provider, result.model, result.verdict,
                result.note,
                json.dumps(result.suggestion, ensure_ascii=False) if result.suggestion is not None else None,
                result.prompt, result.prompt_sha256,
                json.dumps(result.evidence, ensure_ascii=False), result.adapter_version,
                result.decision_authority, int(result.training_eligible),
                qa_item_id,
            ),
        )


def gravar_falha_qa_item(
    conn: sqlite3.Connection, round_id: str, item_id: str, erro: str,
) -> None:
    """Fecha apenas o item com falha operacional; a rodada continua."""
    with conn:
        cursor = conn.execute(
            """UPDATE portal_qa_items SET status='failed', verdict=NULL,
               note=?, decision_authority='PENDENTE', training_eligible=0,
               updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
               WHERE round_id=? AND item_id=?""",
            (erro, round_id, item_id),
        )
    if cursor.rowcount != 1:
        raise KeyError(f"item QA ausente: {round_id}/{item_id}")


def finalizar_qa_round(conn: sqlite3.Connection, round_id: str, status: str) -> None:
    conn.execute(
        """UPDATE portal_qa_rounds SET status=?,
           finalizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
           updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?""",
        (status, round_id),
    )
    conn.commit()


def detalhe_qa_round(conn: sqlite3.Connection, round_id: str) -> Optional[dict[str, Any]]:
    round_row = obter_qa_round(conn, round_id)
    if round_row is None:
        return None
    items = listar_qa_items(conn, round_id)
    for item in items:
        item["suggestion"] = None
        if item.get("suggestion_json"):
            try:
                item["suggestion"] = json.loads(item["suggestion_json"])
            except json.JSONDecodeError:
                pass
        item["confidence_percent"] = (item["suggestion"] or {}).get("confidence_percent")
        item.pop("suggestion_json", None)
        item["evidence"] = []
        if item.get("evidence_json"):
            try:
                item["evidence"] = json.loads(item["evidence_json"])
            except json.JSONDecodeError:
                pass
        item.pop("evidence_json", None)
        item["training_eligible"] = bool(item.get("training_eligible"))
        attempts = conn.execute(
            "SELECT * FROM portal_qa_attempts WHERE qa_item_id=? ORDER BY ordinal",
            (item["id"],),
        ).fetchall()
        item["attempts"] = [dict(row) for row in attempts]
    round_row["items"] = items
    return round_row


def listar_qa_resumos(
    conn: sqlite3.Connection, obra_id: str, pavimento: str, classe: str,
) -> dict[str, dict[str, dict[str, Any]]]:
    """Último veredito por item/camada para feedback compacto da interface."""
    rows = conn.execute(
        """SELECT qi.item_id, qr.layer, qi.status, qi.verdict, qi.note,
                  qi.suggestion_json, qi.provider, qi.model, qr.criado_em
             FROM portal_qa_items qi
             JOIN portal_qa_rounds qr ON qr.id=qi.round_id
            WHERE qr.obra_id=? AND qr.pavimento=? AND qr.classe=?
            ORDER BY qr.criado_em DESC, qr.rowid DESC""",
        (obra_id, pavimento, classe.upper()),
    ).fetchall()
    result: dict[str, dict[str, dict[str, Any]]] = {}
    for row in rows:
        item_layers = result.setdefault(row["item_id"], {})
        if row["layer"] in item_layers:
            continue
        suggestion = {}
        try:
            suggestion = json.loads(row["suggestion_json"] or "{}")
        except json.JSONDecodeError:
            pass
        item_layers[row["layer"]] = {
            "status": row["status"], "verdict": row["verdict"],
            "confidence_percent": suggestion.get("confidence_percent"),
            "note": row["note"], "provider": row["provider"], "model": row["model"],
        }
    return result


def proximo_job(conn: sqlite3.Connection) -> Optional[dict[str, Any]]:
    """Q3: próximo job da fila (maior prioridade, depois mais antigo). Não muda estado.

    [FIX 2026-07-06] `enfileirado_em` só tem precisão de segundo (strftime sem
    milissegundos) — dois jobs enfileirados no mesmo segundo empatavam nesse
    campo, e o desempate seguinte era `id` (UUID), que não guarda ordem de
    inserção nenhuma (achado real pelo teste `test_enfileirar_e_consumir_job_
    respeita_ordem`, que falhava de forma intermitente por causa disso).
    `rowid` do SQLite é monotonicamente crescente na ordem de inserção mesmo
    com PK TEXT — usado aqui como desempate real de FIFO.
    """
    row = conn.execute(
        """SELECT * FROM portal_jobs
           WHERE status = 'na_fila'
           ORDER BY prioridade DESC, enfileirado_em, rowid
           LIMIT 1"""
    ).fetchone()
    return _row_to_dict(row)


def consumir_job(
    conn: sqlite3.Connection,
    *,
    engine_version: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    """Pega o próximo job da fila e marca como 'executando' atomicamente.

    engine_version gravado ao iniciar é o P5 do masterplan (reprodutibilidade).
    Retorna o job consumido (já em 'executando') ou None se a fila estiver vazia.

    [FIX 2026-07-05] O padrão anterior (`with conn:` + SELECT depois UPDATE por id)
    tinha JANELA DE CORRIDA sob concorrência real: com o `sqlite3` do Python em
    isolation_level='' o `with conn` abre a transação como BEGIN DEFERRED, então o
    SELECT toma só lock de LEITURA — duas threads/conexões podiam ler a MESMA linha
    'na_fila' antes de qualquer UPDATE, e ambas retornavam o mesmo job (o segundo
    UPDATE virava no-op, mas o job já tinha sido entregue 2x). Achado real pelo teste
    `test_i2_1_consumo_concorrente_nunca_duplica` (8 threads, 40 jobs → 47 consumos,
    1 duplicado). Isso quebrava o contrato §2 do handoff ("2 chamadas concorrentes
    nunca retornam o mesmo job") e, na prática, podia disparar o mesmo headless 2x.

    Fix: o UPDATE é a operação de CLAIM atômica — `WHERE id=? AND status='na_fila'`.
    Só UMA transação consegue rowcount==1 nessa linha (a transição na_fila→executando
    é a serialização); as perdedoras veem rowcount==0 e re-tentam o próximo job. Não
    depende de timing de lock nem de BEGIN IMMEDIATE.
    """
    while True:
        with conn:  # transação: claim atômico via UPDATE condicional
            # rowid como desempate real de FIFO — ver nota em proximo_job().
            row = conn.execute(
                """SELECT * FROM portal_jobs
                   WHERE status = 'na_fila'
                   ORDER BY prioridade DESC, enfileirado_em, rowid
                   LIMIT 1"""
            ).fetchone()
            if row is None:
                return None
            cur = conn.execute(
                """UPDATE portal_jobs
                   SET status = 'executando',
                       engine_version = COALESCE(?, engine_version),
                       run_id = COALESCE(?, run_id),
                       iniciado_em = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                       updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
                   WHERE id = ? AND status = 'na_fila'""",
                (engine_version, run_id, row["id"]),
            )
            if cur.rowcount != 1:
                # outra transação venceu a corrida por esta linha — tenta o próximo.
                continue
            return dict(conn.execute(
                "SELECT * FROM portal_jobs WHERE id = ?", (row["id"],)
            ).fetchone())


def finalizar_job(
    conn: sqlite3.Connection,
    job_id: str,
    status: str,
    *,
    erro_msg: Optional[str] = None,
    log_path: Optional[str] = None,
) -> None:
    """Fecha o job: status em {concluido, falhou, cancelado}."""
    conn.execute(
        """UPDATE portal_jobs
           SET status = ?,
               erro_msg = ?,
               log_path = COALESCE(?, log_path),
               finalizado_em = strftime('%Y-%m-%dT%H:%M:%SZ','now'),
               updated_at = strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id = ?""",
        (status, erro_msg, log_path, job_id),
    )
    conn.commit()


PAUSA_OPERADOR = "pausado pelo operador"
CANCELAMENTO_OPERADOR = "cancelado pelo operador"


def pausar_job(conn: sqlite3.Connection, job_id: str) -> Optional[dict[str, Any]]:
    """Pausa duravelmente um job na fila ou uma execução cooperativa.

    O schema legado permite cinco estados apenas. A pausa usa ``cancelado`` com
    motivo inequívoco; a API apresenta essa combinação como ``pausado``.
    """
    with conn:
        cur = conn.execute(
            """UPDATE portal_jobs
                  SET status='cancelado', erro_msg=?,
                      finalizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                      updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                WHERE id=? AND status IN ('na_fila','executando')""",
            (PAUSA_OPERADOR, job_id),
        )
    if cur.rowcount != 1:
        return None
    return _row_to_dict(conn.execute("SELECT * FROM portal_jobs WHERE id=?", (job_id,)).fetchone())


def continuar_job(conn: sqlite3.Connection, job_id: str) -> Optional[dict[str, Any]]:
    """Recoloca uma pausa do operador na fila, preservando resultados parciais."""
    with conn:
        cur = conn.execute(
            """UPDATE portal_jobs
                  SET status='na_fila', erro_msg=NULL, iniciado_em=NULL,
                      finalizado_em=NULL,
                      updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                WHERE id=? AND status='cancelado' AND erro_msg=?""",
            (job_id, PAUSA_OPERADOR),
        )
        if cur.rowcount == 1:
            conn.execute(
                """UPDATE portal_qa_rounds
                      SET status='queued', finalizado_em=NULL,
                          updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                    WHERE job_id=?""",
                (job_id,),
            )
    if cur.rowcount != 1:
        return None
    return _row_to_dict(conn.execute("SELECT * FROM portal_jobs WHERE id=?", (job_id,)).fetchone())


def cancelar_job_operador(conn: sqlite3.Connection, job_id: str) -> Optional[dict[str, Any]]:
    """Cancela um job pendente/pausado (ou uma execução QA cooperativa)."""
    with conn:
        cur = conn.execute(
            """UPDATE portal_jobs
                  SET status='cancelado', erro_msg=?,
                      finalizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                      updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                WHERE id=? AND (
                    status='na_fila' OR status='executando' OR
                    (status='cancelado' AND erro_msg=?)
                )""",
            (CANCELAMENTO_OPERADOR, job_id, PAUSA_OPERADOR),
        )
        if cur.rowcount == 1:
            conn.execute(
                """UPDATE portal_qa_rounds
                      SET status=CASE WHEN EXISTS(
                            SELECT 1 FROM portal_qa_items qi
                             WHERE qi.round_id=portal_qa_rounds.id AND qi.status='completed'
                          ) THEN 'partial_failed' ELSE 'failed' END,
                          finalizado_em=strftime('%Y-%m-%dT%H:%M:%SZ','now'),
                          updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
                    WHERE job_id=? AND status!='running'""",
                (job_id,),
            )
    if cur.rowcount != 1:
        return None
    return _row_to_dict(conn.execute("SELECT * FROM portal_jobs WHERE id=?", (job_id,)).fetchone())


def listar_jobs_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    """Q4: histórico/estado dos jobs de uma obra."""
    rows = conn.execute(
        "SELECT * FROM portal_jobs WHERE obra_id = ? ORDER BY enfileirado_em DESC, rowid DESC",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


# --------------------------------------------------------------------------- #
# Drive sync state (memória do poller — 1 por usuário, DP-10)
# --------------------------------------------------------------------------- #

def registrar_sync_state(
    conn: sqlite3.Connection,
    *,
    membro_id: str,
    pasta_drive_id: str,
    ultimo_arquivo_id: Optional[str] = None,
    ultimo_arquivo_hash: Optional[str] = None,
    ultimo_modified_time: Optional[str] = None,
    ultimo_page_token: Optional[str] = None,
    ultimo_scan_status: str = "ok",
) -> None:
    """Upsert do estado do poller por usuário. Chave = membro_id (1 pasta por usuário)."""
    conn.execute(
        """INSERT INTO portal_drive_sync_state
           (membro_id, pasta_drive_id, ultimo_arquivo_id, ultimo_arquivo_hash,
            ultimo_modified_time, ultimo_page_token, ultimo_scan_em, ultimo_scan_status)
           VALUES (?,?,?,?,?,?, strftime('%Y-%m-%dT%H:%M:%SZ','now'), ?)
           ON CONFLICT(membro_id) DO UPDATE SET
               pasta_drive_id      = excluded.pasta_drive_id,
               ultimo_arquivo_id   = excluded.ultimo_arquivo_id,
               ultimo_arquivo_hash = excluded.ultimo_arquivo_hash,
               ultimo_modified_time = excluded.ultimo_modified_time,
               ultimo_page_token   = excluded.ultimo_page_token,
               ultimo_scan_em      = excluded.ultimo_scan_em,
               ultimo_scan_status  = excluded.ultimo_scan_status,
               updated_at          = strftime('%Y-%m-%dT%H:%M:%SZ','now')""",
        (membro_id, pasta_drive_id, ultimo_arquivo_id, ultimo_arquivo_hash,
         ultimo_modified_time, ultimo_page_token, ultimo_scan_status),
    )
    conn.commit()


def obter_sync_state(
    conn: sqlite3.Connection, membro_id: str
) -> Optional[dict[str, Any]]:
    """Lookup O(1) do 'último visto' por usuário (PK = membro_id)."""
    row = conn.execute(
        "SELECT * FROM portal_drive_sync_state WHERE membro_id = ?", (membro_id,)
    ).fetchone()
    return _row_to_dict(row)


# --------------------------------------------------------------------------- #
# Comentários T0 (evidência assinada equipe:<login> — imutável por convenção)
# --------------------------------------------------------------------------- #

def inserir_comentario(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    membro_id: str,
    texto: str,
    tipo: str = "observacao",
    classe: Optional[str] = None,
    pavimento: Optional[str] = None,
    item_id: Optional[str] = None,
    run_id: Optional[str] = None,
    engine_version: Optional[str] = None,
) -> str:
    """Insere comentário T0. namespace é sempre 'equipe' (funil T0, §3).

    marcado_por = 'equipe:<login>' é reconstruído por namespace + membro.login.
    """
    coment_id = _new_id()
    conn.execute(
        """INSERT INTO portal_comentarios_equipe
           (id, obra_id, membro_id, namespace, classe, pavimento, item_id,
            texto, tipo, run_id, engine_version)
           VALUES (?,?,?, 'equipe', ?,?,?,?,?,?,?)""",
        (coment_id, obra_id, membro_id, classe, pavimento, item_id,
         texto, tipo, run_id, engine_version),
    )
    conn.commit()
    return coment_id


def listar_comentarios_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    """Q6: comentários de uma obra para render na página de ficha."""
    rows = conn.execute(
        "SELECT * FROM portal_comentarios_equipe WHERE obra_id = ? ORDER BY created_at, id",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def listar_comentarios_para_triagem(
    conn: sqlite3.Connection,
) -> list[dict[str, Any]]:
    """Q5: bandeja do dono — comentários ainda não exportados para o funil Arete."""
    rows = conn.execute(
        """SELECT * FROM portal_comentarios_equipe
           WHERE exportado_triagem = 0 ORDER BY created_at, id"""
    ).fetchall()
    return [dict(r) for r in rows]


def marcar_comentario_exportado(conn: sqlite3.Connection, coment_id: str) -> None:
    """Ponto de entrega para triagem do dono — NÃO escreve em training_events (§3)."""
    conn.execute(
        "UPDATE portal_comentarios_equipe SET exportado_triagem = 1 WHERE id = ?",
        (coment_id,),
    )
    conn.commit()


# --------------------------------------------------------------------------- #
# Apontamentos visuais globais da interface (feedback comunitario por usuario)
# --------------------------------------------------------------------------- #

def inserir_apontamento_ui(
    conn: sqlite3.Connection,
    *,
    obra_id: Optional[str],
    membro_id: str,
    texto: str,
    pagina_url: str,
    pagina_titulo: Optional[str],
    seletor_elemento: Optional[str],
    elemento_tag: Optional[str],
    elemento_role: Optional[str],
    elemento_texto: Optional[str],
    elemento_json: str,
    clique_x: float,
    clique_y: float,
    pagina_x: float,
    pagina_y: float,
    viewport_largura: int,
    viewport_altura: int,
    captura_mime: Optional[str],
    captura_blob: Optional[bytes],
    sessao_id: Optional[str] = None,
    pagina_id: Optional[str] = None,
    ordem_ponto: Optional[int] = None,
    commit: bool = True,
) -> str:
    apontamento_id = _new_id()
    conn.execute(
        """INSERT INTO portal_apontamentos_ui
           (id,obra_id,membro_id,texto,pagina_url,pagina_titulo,
            seletor_elemento,elemento_tag,elemento_role,elemento_texto,
            elemento_json,clique_x,clique_y,pagina_x,pagina_y,
            viewport_largura,viewport_altura,captura_mime,captura_blob,
            sessao_id,pagina_id,ordem_ponto)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            apontamento_id, obra_id, membro_id, texto, pagina_url, pagina_titulo,
            seletor_elemento, elemento_tag, elemento_role, elemento_texto,
            elemento_json, clique_x, clique_y, pagina_x, pagina_y,
            viewport_largura, viewport_altura, captura_mime, captura_blob,
            sessao_id, pagina_id, ordem_ponto,
        ),
    )
    if commit:
        conn.commit()
    return apontamento_id


def inserir_sessao_apontamento_ui(
    conn: sqlite3.Connection, *, obra_id: Optional[str], membro_id: str,
    titulo: Optional[str], paginas: list[dict[str, Any]],
) -> str:
    """Persiste uma sessão inteira; nenhuma página fica salva pela metade."""
    sessao_id = _new_id()
    with conn:
        conn.execute(
            "INSERT INTO portal_apontamento_sessoes(id,obra_id,membro_id,titulo) VALUES(?,?,?,?)",
            (sessao_id, obra_id, membro_id, titulo),
        )
        for page_order, page in enumerate(paginas, start=1):
            pagina_id = _new_id()
            conn.execute(
                """INSERT INTO portal_apontamento_paginas
                   (id,sessao_id,ordem,pagina_url,pagina_titulo) VALUES(?,?,?,?,?)""",
                (pagina_id, sessao_id, page_order, page["pagina_url"], page.get("pagina_titulo")),
            )
            for point_order, point in enumerate(page["pontos"], start=1):
                inserir_apontamento_ui(
                    conn, obra_id=obra_id, membro_id=membro_id,
                    sessao_id=sessao_id, pagina_id=pagina_id,
                    ordem_ponto=point_order, commit=False, **point,
                )
    return sessao_id


def listar_sessoes_apontamento_ui(
    conn: sqlite3.Connection, *, membro: dict[str, Any], somente_meus: bool = False,
) -> list[dict[str, Any]]:
    if somente_meus:
        filtro, params = "WHERE s.membro_id = ?", (membro["id"],)
    elif membro.get("papel") == "dono":
        filtro, params = "", ()
    else:
        # [2026-09-28] Isolamento entre perfis: a captura de tela de um
        # apontamento mostra obras de quem apontou — membro só vê os próprios.
        filtro, params = "WHERE s.membro_id = ?", (membro["id"],)
    sessions = [dict(row) for row in conn.execute(
        """SELECT s.*,m.login AS autor_login,m.nome AS autor_nome,o.nome AS obra_nome
             FROM portal_apontamento_sessoes s
             JOIN portal_membros m ON m.id=s.membro_id
             LEFT JOIN portal_obras o ON o.id=s.obra_id
        """ + filtro + " ORDER BY s.created_at DESC,s.id DESC", params,
    ).fetchall()]
    for session in sessions:
        pages = [dict(row) for row in conn.execute(
            "SELECT * FROM portal_apontamento_paginas WHERE sessao_id=? ORDER BY ordem",
            (session["id"],),
        ).fetchall()]
        for page in pages:
            page["pontos"] = [dict(row) for row in conn.execute(
                """SELECT id,texto,seletor_elemento,elemento_tag,elemento_role,
                          elemento_texto,elemento_json,clique_x,clique_y,pagina_x,pagina_y,
                          viewport_largura,viewport_altura,captura_mime,ordem_ponto,created_at
                     FROM portal_apontamentos_ui WHERE pagina_id=? ORDER BY ordem_ponto,id""",
                (page["id"],),
            ).fetchall()]
        session["paginas"] = pages
    return sessions


def listar_apontamentos_ui(
    conn: sqlite3.Connection, *, membro: dict[str, Any], somente_meus: bool = False,
) -> list[dict[str, Any]]:
    if somente_meus:
        filtro = "WHERE a.membro_id = ?"
        params: tuple[Any, ...] = (membro["id"],)
    elif membro.get("papel") == "dono":
        filtro = ""
        params = ()
    else:
        # [2026-09-28] Isolamento entre perfis: membro só vê os próprios.
        filtro = "WHERE a.membro_id = ?"
        params = (membro["id"],)
    rows = conn.execute(
        """SELECT a.id,a.obra_id,a.membro_id,a.texto,a.pagina_url,
                  a.pagina_titulo,a.seletor_elemento,a.elemento_tag,
                  a.elemento_role,a.elemento_texto,a.elemento_json,
                  a.clique_x,a.clique_y,a.pagina_x,a.pagina_y,
                  a.viewport_largura,a.viewport_altura,a.captura_mime,
                  a.sessao_id,a.pagina_id,a.ordem_ponto,
                  a.created_at,m.login AS autor_login,m.nome AS autor_nome,
                  o.nome AS obra_nome
           FROM portal_apontamentos_ui a
           JOIN portal_membros m ON m.id = a.membro_id
           LEFT JOIN portal_obras o ON o.id = a.obra_id
           """ + filtro +
        " ORDER BY a.created_at DESC, a.id DESC",
        params,
    ).fetchall()
    return [dict(row) for row in rows]


def obter_apontamento_ui(
    conn: sqlite3.Connection, apontamento_id: str,
) -> Optional[dict[str, Any]]:
    row = conn.execute(
        "SELECT * FROM portal_apontamentos_ui WHERE id = ?", (apontamento_id,),
    ).fetchone()
    return _row_to_dict(row)


def pode_ver_apontamento_ui(
    conn: sqlite3.Connection, apontamento: dict[str, Any], membro: dict[str, Any],
) -> bool:
    return membro.get("papel") == "dono" or apontamento["membro_id"] == membro["id"]


# --------------------------------------------------------------------------- #
# N5 releases (auditoria self-service — snapshot congelado de certificação, R9)
# --------------------------------------------------------------------------- #

def registrar_n5_release(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    classe: str,
    liberado_por: str,
    status_certificacao: str,
    pavimento: str = "GERAL",
    engine_version: Optional[str] = None,
    job_id: Optional[str] = None,
    dxf_path: Optional[str] = None,
    dxf_hash: Optional[str] = None,
) -> str:
    """Registra uma liberação N5 (append-only). status_certificacao é SNAPSHOT congelado.

    O snapshot preserva o rótulo Arete NAQUELE momento (R9): auditar "o que ele sabia
    quando liberou" independe do estado atual da curadoria. classe validada contra o
    domínio real de assemble_n5 (PL/LV/FV/LJ).
    """
    if classe not in CLASSES_N5:
        raise ValueError(
            f"classe {classe!r} inválida para N5 — domínio de assemble_n5 é {CLASSES_N5}."
        )
    if status_certificacao not in _STATUS_CERT:
        raise ValueError(
            f"status_certificacao {status_certificacao!r} inválido — use {_STATUS_CERT}."
        )
    release_id = _new_id()
    conn.execute(
        """INSERT INTO portal_n5_releases
           (id, obra_id, classe, pavimento, liberado_por, status_certificacao,
            engine_version, job_id, dxf_path, dxf_hash)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (release_id, obra_id, classe, pavimento, liberado_por, status_certificacao,
         engine_version, job_id, dxf_path, dxf_hash),
    )
    conn.commit()
    return release_id


def listar_n5_releases_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT * FROM portal_n5_releases
           WHERE obra_id = ? ORDER BY liberado_em DESC, id""",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def sincronizar_documento_dxf_convertido(
    conn: sqlite3.Connection,
    *,
    obra_id: str,
    documento_origem: dict[str, Any],
    arquivo_nome: str,
    local_path: str,
    arquivo_hash: Optional[str] = None,
    status: str = "revisar",
    classe_confirmada: Optional[str] = None,
    pavimento_confirmado: Optional[str] = None,
) -> str:
    """Registra o DXF materializado a partir de um DWG na lista da obra.

    A conversao sempre produziu o arquivo em disco, mas historicamente nao
    criava uma linha em ``portal_documentos``. O upsert por nome torna a
    operacao idempotente: repetir triagem/conversao atualiza o mesmo DXF em vez
    de duplica-lo. Confirmacoes humanas ja existentes no DXF sao preservadas.
    """
    existente = conn.execute(
        """SELECT * FROM portal_documentos
           WHERE obra_id=? AND lower(arquivo_nome)=lower(?)
           ORDER BY created_at, id LIMIT 1""",
        (obra_id, arquivo_nome),
    ).fetchone()
    if existente is None:
        return criar_documento(
            conn,
            obra_id=obra_id,
            arquivo_nome=arquivo_nome,
            arquivo_hash=arquivo_hash,
            local_path=local_path,
            classe_sugerida=documento_origem.get("classe_sugerida"),
            pavimento_sugerido=documento_origem.get("pavimento_sugerido"),
            tipo_documento_sugerido=documento_origem.get("tipo_documento_sugerido"),
            classe_confirmada=(
                classe_confirmada or documento_origem.get("classe_confirmada")
            ),
            pavimento_confirmado=(
                pavimento_confirmado or documento_origem.get("pavimento_confirmado")
            ),
            tipo_documento_confirmado=documento_origem.get("tipo_documento_confirmado"),
            status=status,
        )

    doc_id = existente["id"]
    status_final = "classificado" if existente["status"] == "classificado" else status
    conn.execute(
        """UPDATE portal_documentos
           SET local_path=?,
               arquivo_hash=COALESCE(arquivo_hash, ?),
               classe_sugerida=COALESCE(classe_sugerida, ?),
               pavimento_sugerido=COALESCE(pavimento_sugerido, ?),
               tipo_documento_sugerido=COALESCE(tipo_documento_sugerido, ?),
               classe_confirmada=COALESCE(classe_confirmada, ?),
               pavimento_confirmado=COALESCE(pavimento_confirmado, ?),
               tipo_documento_confirmado=COALESCE(tipo_documento_confirmado, ?),
               status=?, erro_msg=NULL,
               updated_at=strftime('%Y-%m-%dT%H:%M:%SZ','now')
           WHERE id=?""",
        (
            local_path,
            arquivo_hash,
            documento_origem.get("classe_sugerida"),
            documento_origem.get("pavimento_sugerido"),
            documento_origem.get("tipo_documento_sugerido"),
            classe_confirmada or documento_origem.get("classe_confirmada"),
            pavimento_confirmado or documento_origem.get("pavimento_confirmado"),
            documento_origem.get("tipo_documento_confirmado"),
            status_final,
            doc_id,
        ),
    )
    conn.commit()
    return doc_id


def aprovar_n5_release(
    conn: sqlite3.Connection,
    *,
    release_id: str,
    obra_id: str,
    classe: str,
    pavimento: str,
    aprovado_por: str,
) -> dict[str, Any]:
    """Aprova um release N5 específico; idempotente para duplo clique/retry."""
    conn.execute(
        """INSERT OR IGNORE INTO portal_n5_validacoes
           (release_id, obra_id, classe, pavimento, aprovado_por)
           VALUES (?,?,?,?,?)""",
        (release_id, obra_id, classe.upper(), pavimento, aprovado_por),
    )
    conn.commit()
    row = conn.execute(
        "SELECT * FROM portal_n5_validacoes WHERE release_id = ?", (release_id,)
    ).fetchone()
    return dict(row)


def listar_n5_validacoes_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    rows = conn.execute(
        """SELECT * FROM portal_n5_validacoes
           WHERE obra_id = ? ORDER BY aprovado_em DESC, release_id""",
        (obra_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def auditoria_n5(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Trilha de auditoria R9: quem liberou o quê, quando, e o rótulo NAQUELE momento."""
    rows = conn.execute(
        """SELECT
               r.liberado_em,
               m.login               AS liberado_por,
               o.nome                AS obra,
               r.classe,
               r.pavimento,
               r.status_certificacao AS status_no_momento_da_liberacao,
               r.engine_version,
               r.dxf_hash
           FROM portal_n5_releases r
           JOIN portal_membros m ON m.id = r.liberado_por
           JOIN portal_obras   o ON o.id = r.obra_id
           ORDER BY r.liberado_em DESC, r.id"""
    ).fetchall()
    return [dict(r) for r in rows]
