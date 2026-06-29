# -*- coding: utf-8 -*-
"""
db_bridge.py — Ponte de leitura do SQLite project_data.vision

Camada fina que encapsula todas as queries SQL necessárias
para os 8 loops do MCP Server.  Nenhuma lógica de negócio
vive aqui — apenas leitura/escrita segura ao banco.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Caminho padrão do banco ──────────────────────────────────────────────────
DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")


@contextmanager
def _conn(db_path: Path = DEFAULT_DB):
    """Context manager de leitura com timeout e escrita bloqueada."""
    c = sqlite3.connect(str(db_path), timeout=15.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("PRAGMA query_only=ON")
    try:
        yield c
    finally:
        c.close()


@contextmanager
def _conn_rw(db_path: Path = DEFAULT_DB):
    """Context manager com commit automático para escrita."""
    c = sqlite3.connect(str(db_path), timeout=15.0)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA busy_timeout=15000")
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


# ═══════════════════════════════════════════════════════════════════════════════
# TABELAS DE EVENT SOURCING (criadas sob demanda)
# ═══════════════════════════════════════════════════════════════════════════════

_HUMAN_EVENT_LOGS_DDL = """
CREATE TABLE IF NOT EXISTS human_event_logs (
    log_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    obra_id TEXT NOT NULL,
    classe TEXT NOT NULL,
    item_id TEXT NOT NULL,
    fase_editada TEXT NOT NULL,
    ui_context TEXT NOT NULL,
    estado_anterior_json TEXT NOT NULL,
    estado_novo_json TEXT NOT NULL,
    campos_alterados TEXT,
    processado_por_rag INTEGER DEFAULT 0,
    rag_vector_id TEXT,
    event_kind TEXT NOT NULL DEFAULT 'edit',
    status TEXT NOT NULL DEFAULT 'CAPTURED',
    tier TEXT NOT NULL DEFAULT 'T0',
    validation_origin TEXT NOT NULL DEFAULT 'human_ui',
    user_reason TEXT,
    source_agent TEXT,
    actor_id TEXT,
    session_id TEXT,
    correlation_id TEXT,
    parent_log_id TEXT,
    idempotency_key TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    claimed_at TEXT,
    claimed_by TEXT,
    candidate_path TEXT,
    last_error TEXT,
    approved_at TEXT,
    approved_by TEXT,
    updated_at TEXT
);
"""

_HUMAN_EVENT_MIGRATION_COLUMNS = {
    "event_kind": "TEXT NOT NULL DEFAULT 'edit'",
    "status": "TEXT NOT NULL DEFAULT 'CAPTURED'",
    "tier": "TEXT NOT NULL DEFAULT 'T0'",
    "validation_origin": "TEXT NOT NULL DEFAULT 'human_ui'",
    "user_reason": "TEXT",
    "source_agent": "TEXT",
    "actor_id": "TEXT",
    "session_id": "TEXT",
    "correlation_id": "TEXT",
    "parent_log_id": "TEXT",
    "idempotency_key": "TEXT",
    "attempt_count": "INTEGER NOT NULL DEFAULT 0",
    "claimed_at": "TEXT",
    "claimed_by": "TEXT",
    "candidate_path": "TEXT",
    "last_error": "TEXT",
    "approved_at": "TEXT",
    "approved_by": "TEXT",
    "updated_at": "TEXT",
}

_N4_ATTENTION_FEEDBACK_DDL = """
CREATE TABLE IF NOT EXISTS n4_attention_feedback (
    feedback_id TEXT PRIMARY KEY,
    obra_id TEXT NOT NULL,
    item_id TEXT NOT NULL,
    erro_visual_categoria TEXT,
    descricao_humana TEXT,
    coord_x REAL,
    coord_y REAL,
    status_resolucao TEXT DEFAULT 'PENDENTE',
    codigo_fonte_ajustado TEXT,
    created_at TEXT NOT NULL
);
"""


def ensure_event_sourcing_tables(db_path: Path = DEFAULT_DB) -> None:
    """Garante que as tabelas de Event Sourcing existam."""
    with _conn_rw(db_path) as conn:
        conn.executescript(_HUMAN_EVENT_LOGS_DDL)
        conn.executescript(_N4_ATTENTION_FEEDBACK_DDL)
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(human_event_logs)").fetchall()
        }
        for column, ddl in _HUMAN_EVENT_MIGRATION_COLUMNS.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE human_event_logs ADD COLUMN {column} {ddl}")
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_human_event_idempotency
            ON human_event_logs(idempotency_key)
            WHERE idempotency_key IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_human_event_status_timestamp
            ON human_event_logs(status, timestamp)
            """
        )
        if "processed" in existing:
            conn.execute(
                """
                UPDATE human_event_logs
                SET updated_at=COALESCE(updated_at, CURRENT_TIMESTAMP)
                WHERE COALESCE(processed, 0) != 0
                """
            )
            conn.execute("ALTER TABLE human_event_logs DROP COLUMN processed")
        conn.execute(
            """
            UPDATE human_event_logs
            SET status='TEST_QUARANTINED', tier='T0',
                last_error='legacy MCP smoke test; never index',
                updated_at=COALESCE(updated_at, CURRENT_TIMESTAMP)
            WHERE log_id='52fd248f-c0c4-4893-ade0-47393a2512fb'
            """
        )


# ═══════════════════════════════════════════════════════════════════════════════
# LEITURAS — usadas pelas MCP Tools
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_obras(db_path: Path = DEFAULT_DB) -> List[str]:
    """Retorna todas as obras cadastradas."""
    with _conn(db_path) as conn:
        rows = conn.execute("SELECT name FROM works ORDER BY name").fetchall()
        return [r["name"] for r in rows]


def get_obra_status(obra_id: str, db_path: Path = DEFAULT_DB) -> Dict[str, Any]:
    """
    Loop 1-4: Retorna estado geral da obra nos níveis SA/N1/N2/N3/N4/N5.
    Agrega contagens de fichas, pilares, vigas, lajes e attention notes.
    """
    result: Dict[str, Any] = {
        "obra_id": obra_id,
        "projetos": [],
        "contagens": {},
        "attention_notes_total": 0,
        "training_events_total": 0,
    }
    with _conn(db_path) as conn:
        # Projetos/Pavimentos da obra
        projects = conn.execute(
            "SELECT id, name, pavement_name FROM projects WHERE work_name = ?",
            (obra_id,),
        ).fetchall()
        for p in projects:
            pid = p["id"]
            pil_count = conn.execute(
                "SELECT COUNT(*) as c FROM pillars WHERE project_id = ?", (pid,)
            ).fetchone()["c"]
            beam_count = conn.execute(
                "SELECT COUNT(*) as c FROM beams WHERE project_id = ?", (pid,)
            ).fetchone()["c"]
            slab_count = conn.execute(
                "SELECT COUNT(*) as c FROM slabs WHERE project_id = ?", (pid,)
            ).fetchone()["c"]
            result["projetos"].append({
                "project_id": pid,
                "pavimento": p["name"],
                "pilares": pil_count,
                "vigas": beam_count,
                "lajes": slab_count,
            })

        # Contagens globais da obra
        result["contagens"] = {
            "projetos": len(projects),
            "pilares": sum(p["pilares"] for p in result["projetos"]),
            "vigas": sum(p["vigas"] for p in result["projetos"]),
            "lajes": sum(p["lajes"] for p in result["projetos"]),
        }

        # Attention notes (se a tabela existir)
        try:
            an = conn.execute(
                "SELECT COUNT(*) as c FROM item_attention_notes WHERE obra_name = ?",
                (obra_id,),
            ).fetchone()
            result["attention_notes_total"] = an["c"] if an else 0
        except sqlite3.OperationalError:
            pass

        # Training events
        try:
            project_ids = [p["project_id"] for p in result["projetos"]]
            if project_ids:
                placeholders = ",".join("?" * len(project_ids))
                te = conn.execute(
                    f"SELECT COUNT(*) as c FROM training_events WHERE project_id IN ({placeholders})",
                    project_ids,
                ).fetchone()
                result["training_events_total"] = te["c"] if te else 0
        except sqlite3.OperationalError:
            pass

    return result


def get_attention_notes(
    obra_id: str,
    classe: str = "ALL",
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """
    Loop 1 e 2: Retorna notas de atenção (discrepâncias humanas e automáticas).
    """
    with _conn(db_path) as conn:
        try:
            if classe.upper() == "ALL":
                rows = conn.execute(
                    "SELECT * FROM item_attention_notes WHERE obra_name = ? ORDER BY updated_at DESC",
                    (obra_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM item_attention_notes WHERE obra_name = ? AND classe = ? ORDER BY updated_at DESC",
                    (obra_id, classe.upper()),
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


def get_n4_attention_feedback(
    obra_id: str,
    status: str = "PENDENTE",
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """
    Loop 2: Retorna feedback humano específico para correção do robô N4.
    """
    ensure_event_sourcing_tables(db_path)
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM n4_attention_feedback WHERE obra_id = ? AND status_resolucao = ? ORDER BY created_at DESC",
            (obra_id, status),
        ).fetchall()
        return [dict(r) for r in rows]


def get_training_events(
    obra_id: str,
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """
    Loop 1 e 8: Retorna eventos de treino associados à obra.
    """
    with _conn(db_path) as conn:
        project_ids = [
            r["id"]
            for r in conn.execute(
                "SELECT id FROM projects WHERE work_name = ?", (obra_id,)
            ).fetchall()
        ]
        if not project_ids:
            return []
        placeholders = ",".join("?" * len(project_ids))
        try:
            rows = conn.execute(
                f"SELECT * FROM training_events WHERE project_id IN ({placeholders}) ORDER BY created_at DESC",
                project_ids,
            ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


def get_human_overrides_log(
    obra_id: str = "",
    only_unprocessed: bool = True,
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """
    Loop 8: Retorna edições humanas salvas via UI (Event Sourcing).
    """
    ensure_event_sourcing_tables(db_path)
    with _conn(db_path) as conn:
        query = "SELECT * FROM human_event_logs"
        params: list = []
        conditions: list = []
        if obra_id:
            conditions.append("obra_id = ?")
            params.append(obra_id)
        if only_unprocessed:
            conditions.append(
                "status NOT IN ('INDEXED','REJECTED','TEST_QUARANTINED')"
            )
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC"
        rows = conn.execute(query, params).fetchall()
        return [dict(r) for r in rows]


def get_crop_learning_events(
    obra_id: str = "",
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """
    Loop 7 e 8: Retorna eventos de aprendizado de recorte (crop learning).
    """
    with _conn(db_path) as conn:
        try:
            if obra_id:
                rows = conn.execute(
                    "SELECT * FROM crop_learning_events WHERE obra_name = ? ORDER BY created_at DESC",
                    (obra_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM crop_learning_events ORDER BY created_at DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        except sqlite3.OperationalError:
            return []


# ═══════════════════════════════════════════════════════════════════════════════
# ESCRITAS — usadas pelas MCP Tools de ação
# ═══════════════════════════════════════════════════════════════════════════════

def save_human_event_log(
    obra_id: str,
    classe: str,
    item_id: str,
    fase_editada: str,
    ui_context: str,
    estado_anterior: dict,
    estado_novo: dict,
    campos_alterados: Optional[List[str]] = None,
    *,
    event_kind: str = "edit",
    user_reason: str = "",
    source_agent: str = "",
    actor_id: str = "",
    session_id: str = "",
    correlation_id: str = "",
    parent_log_id: str = "",
    idempotency_key: str = "",
    validation_origin: str = "human_ui",
    db_path: Path = DEFAULT_DB,
) -> str:
    """
    Loop 8: Grava um evento de edição humana (Event Sourcing).
    Retorna o log_id criado.
    """
    ensure_event_sourcing_tables(db_path)
    if event_kind.lower() in {"approval", "validation", "approve"}:
        raise ValueError("edição e aprovação são eventos distintos")
    log_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Calcula campos alterados automaticamente se não fornecidos
    if campos_alterados is None:
        campos_alterados = _diff_keys(estado_anterior, estado_novo)

    if not idempotency_key:
        raw_key = json.dumps(
            {
                "obra": obra_id,
                "classe": classe,
                "item": item_id,
                "fase": fase_editada,
                "contexto": ui_context,
                "antes": estado_anterior,
                "depois": estado_novo,
                "correlation": correlation_id,
                "time_bucket": now,
            },
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
        idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    with _conn_rw(db_path) as conn:
        existing = conn.execute(
            "SELECT log_id FROM human_event_logs WHERE idempotency_key=?",
            (idempotency_key,),
        ).fetchone()
        if existing:
            return str(existing["log_id"])
        conn.execute(
            """
            INSERT INTO human_event_logs
                (log_id, timestamp, obra_id, classe, item_id, fase_editada,
                 ui_context, estado_anterior_json, estado_novo_json, campos_alterados,
                 event_kind, status, tier, validation_origin, user_reason,
                 source_agent, actor_id, session_id, correlation_id, parent_log_id,
                 idempotency_key, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'CAPTURED', 'T0',
                    ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                log_id,
                now,
                obra_id,
                classe.upper(),
                item_id,
                fase_editada,
                ui_context,
                json.dumps(estado_anterior, ensure_ascii=False),
                json.dumps(estado_novo, ensure_ascii=False),
                json.dumps(campos_alterados, ensure_ascii=False),
                event_kind,
                validation_origin,
                user_reason,
                source_agent,
                actor_id,
                session_id,
                correlation_id,
                parent_log_id,
                idempotency_key,
                now,
            ),
        )
    return log_id


def save_human_edit_event(
    obra_id: str,
    classe: str,
    item_id: str,
    fase_editada: str,
    *,
    ui_context: str = "",
    estado_anterior: Optional[dict] = None,
    estado_novo: Optional[dict] = None,
    campo_alterado: str = "",
    valor_antigo: Any = None,
    valor_novo: Any = None,
    nota_usuario: str = "",
    source_agent: str = "",
    actor_id: str = "",
    session_id: str = "",
    correlation_id: str = "",
    db_path: Path = DEFAULT_DB,
) -> str:
    """API estável da UI: registra evidência T0, nunca aprovação."""
    before = dict(estado_anterior or {})
    after = dict(estado_novo or {})
    if campo_alterado:
        before.setdefault(campo_alterado, valor_antigo)
        after.setdefault(campo_alterado, valor_novo)
    return save_human_event_log(
        obra_id,
        classe,
        item_id,
        fase_editada,
        ui_context,
        before,
        after,
        event_kind="edit",
        user_reason=nota_usuario,
        source_agent=source_agent,
        actor_id=actor_id,
        session_id=session_id,
        correlation_id=correlation_id,
        validation_origin="human_ui",
        db_path=db_path,
    )


def claim_events_for_proposal(
    worker_id: str,
    *,
    limit: int = 100,
    db_path: Path = DEFAULT_DB,
) -> List[Dict[str, Any]]:
    """Reserva eventos T0 atomicamente para gerar propostas."""
    ensure_event_sourcing_tables(db_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn_rw(db_path) as conn:
        conn.execute("BEGIN IMMEDIATE")
        ids = [
            str(row["log_id"])
            for row in conn.execute(
                """
                SELECT log_id FROM human_event_logs
                WHERE status IN ('CAPTURED','FAILED') AND tier='T0'
                  AND attempt_count < 5
                ORDER BY timestamp ASC LIMIT ?
                """,
                (max(int(limit), 0),),
            ).fetchall()
        ]
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        conn.execute(
            f"""
            UPDATE human_event_logs
            SET status='PROPOSING', claimed_at=?, claimed_by=?,
                attempt_count=attempt_count+1, last_error=NULL, updated_at=?
            WHERE log_id IN ({placeholders})
              AND status IN ('CAPTURED','FAILED') AND tier='T0'
            """,
            (now, worker_id, now, *ids),
        )
        return [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT * FROM human_event_logs
                WHERE log_id IN ({placeholders})
                  AND status='PROPOSING' AND claimed_by=?
                ORDER BY timestamp ASC
                """,
                (*ids, worker_id),
            ).fetchall()
        ]


def mark_event_proposed(
    log_id: str,
    candidate_path: str,
    *,
    db_path: Path = DEFAULT_DB,
) -> None:
    with _conn_rw(db_path) as conn:
        conn.execute(
            """
            UPDATE human_event_logs
            SET status='PROPOSED', candidate_path=?, claimed_at=NULL, claimed_by=NULL,
                updated_at=CURRENT_TIMESTAMP, last_error=NULL
            WHERE log_id=? AND status='PROPOSING' AND tier='T0'
            """,
            (candidate_path, log_id),
        )


def mark_event_failed(log_id: str, error: str, *, db_path: Path = DEFAULT_DB) -> None:
    with _conn_rw(db_path) as conn:
        conn.execute(
            """
            UPDATE human_event_logs
            SET status='FAILED', claimed_at=NULL, claimed_by=NULL,
                last_error=?, updated_at=CURRENT_TIMESTAMP
            WHERE log_id=? AND status='PROPOSING'
            """,
            (str(error)[:2000], log_id),
        )


def approve_event_candidate(
    log_id: str,
    *,
    approved_by: str,
    reason: str,
    validation_origin: str = "human_ui",
    db_path: Path = DEFAULT_DB,
) -> bool:
    if str(validation_origin or "").strip().lower() not in {
        "human", "human_ui", "manual", "operator", "ui", "ui_click", "user", "user_click"
    }:
        raise ValueError("aprovação exige origem humana explícita")
    if not approved_by.strip() or not reason.strip():
        raise ValueError("aprovação exige autor e justificativa")
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn_rw(db_path) as conn:
        result = conn.execute(
            """
            UPDATE human_event_logs
            SET status='APPROVED', tier='T1', approved_at=?, approved_by=?,
                user_reason=?, validation_origin=?, updated_at=?
            WHERE log_id=? AND status='PROPOSED' AND tier='T0'
            """,
            (now, approved_by, reason, validation_origin, now, log_id),
        )
        return result.rowcount == 1


def reject_event_candidate(
    log_id: str,
    *,
    rejected_by: str,
    reason: str,
    db_path: Path = DEFAULT_DB,
) -> bool:
    if not rejected_by.strip() or not reason.strip():
        raise ValueError("rejeição exige autor e justificativa")
    with _conn_rw(db_path) as conn:
        result = conn.execute(
            """
            UPDATE human_event_logs
            SET status='REJECTED', tier='TX', approved_by=?, user_reason=?,
                updated_at=CURRENT_TIMESTAMP
            WHERE log_id=? AND status IN ('PROPOSED','APPROVED')
            """,
            (rejected_by, reason, log_id),
        )
        return result.rowcount == 1


def mark_event_as_processed(
    log_id: str,
    rag_vector_id: str = "",
    db_path: Path = DEFAULT_DB,
) -> bool:
    """
    Loop 8: Marca um evento de edição como já processado pelo RAG.
    """
    ensure_event_sourcing_tables(db_path)
    with _conn_rw(db_path) as conn:
        result = conn.execute(
            """
            UPDATE human_event_logs
            SET processado_por_rag=1, rag_vector_id=?,
                status='INDEXED',
                updated_at=CURRENT_TIMESTAMP
            WHERE log_id=? AND tier IN ('T1','T2')
              AND status IN ('APPROVED','INDEXED')
            """,
            (rag_vector_id, log_id),
        )
        return result.rowcount == 1


def save_n4_feedback(
    obra_id: str,
    item_id: str,
    erro_visual_categoria: str,
    descricao_humana: str,
    coord_x: Optional[float] = None,
    coord_y: Optional[float] = None,
    db_path: Path = DEFAULT_DB,
) -> str:
    """
    Loop 2: Grava feedback de atenção humana sobre o N4.
    Retorna o feedback_id criado.
    """
    ensure_event_sourcing_tables(db_path)
    fid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with _conn_rw(db_path) as conn:
        conn.execute(
            """
            INSERT INTO n4_attention_feedback
                (feedback_id, obra_id, item_id, erro_visual_categoria,
                 descricao_humana, coord_x, coord_y, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (fid, obra_id, item_id, erro_visual_categoria,
             descricao_humana, coord_x, coord_y, now),
        )
    return fid


def resolve_n4_feedback(
    feedback_id: str,
    codigo_fonte_ajustado: str = "",
    db_path: Path = DEFAULT_DB,
) -> bool:
    """
    Loop 2: Marca um feedback N4 como resolvido pelo agente/desenvolvedor.
    """
    ensure_event_sourcing_tables(db_path)
    with _conn_rw(db_path) as conn:
        conn.execute(
            """
            UPDATE n4_attention_feedback
            SET status_resolucao = 'RESOLVIDO',
                codigo_fonte_ajustado = ?
            WHERE feedback_id = ?
            """,
            (codigo_fonte_ajustado, feedback_id),
        )
    return True


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITÁRIOS INTERNOS
# ═══════════════════════════════════════════════════════════════════════════════

def _diff_keys(old: dict, new: dict) -> List[str]:
    """Retorna lista de chaves que mudaram entre dois dicionários."""
    all_keys = set(old.keys()) | set(new.keys())
    changed = []
    for k in sorted(all_keys):
        if old.get(k) != new.get(k):
            changed.append(k)
    return changed
