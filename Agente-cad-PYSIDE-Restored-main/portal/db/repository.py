"""Camada de acesso a dados do portal (stdlib sqlite3 apenas — sem ORM, HANDOFF §1).

Motor geral: nenhuma função hardcoda obra ou usuário específico. Toda entidade
recebe seus dados por parâmetro. IDs de entidade são TEXT (uuid) para casar com o
padrão do Arete (HANDOFF §2).

Regra de fronteira: nada aqui escreve em project_data.vision. O status de
certificação do N5 é recebido como SNAPSHOT já lido em modo read-only pelo chamador
(HANDOFF §2.6/§5) — o repositório apenas o congela na linha de auditoria.
"""

from __future__ import annotations

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
) -> str:
    """Cria um membro. senha_hash já vem hasheada (bcrypt/argon2) — nunca senha em claro."""
    membro_id = _new_id()
    conn.execute(
        """INSERT INTO portal_membros
           (id, login, nome, email, senha_hash, papel, drive_folder_id)
           VALUES (?,?,?,?,?,?,?)""",
        (membro_id, login, nome, email, senha_hash, papel, drive_folder_id),
    )
    conn.commit()
    return membro_id


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
            pavimento_confirmado, tipo_documento_confirmado, status)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (doc_id, obra_id, arquivo_nome, arquivo_drive_id, arquivo_hash, local_path,
         classe_sugerida, pavimento_sugerido, tipo_documento_sugerido,
         pavimento_confirmado, tipo_documento_confirmado, status),
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


def listar_jobs_por_obra(
    conn: sqlite3.Connection, obra_id: str
) -> list[dict[str, Any]]:
    """Q4: histórico/estado dos jobs de uma obra."""
    rows = conn.execute(
        "SELECT * FROM portal_jobs WHERE obra_id = ? ORDER BY enfileirado_em DESC, id",
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
