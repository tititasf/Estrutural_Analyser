"""
Obra Knowledge - Modulo 3 do Pipeline de Vetorizacao
======================================================
Base de conhecimento persistente (SQLite) de uma obra.
Armazena entidades vetorizadas, perfil da obra, estatisticas
por pavimento, e serve como interface de consulta para o
Structural Analyzer e os Robos de geracao DXF.

Tabelas:
  - obra_profile: metadados gerais da obra
  - pavimentos: lista de pavimentos detectados
  - structural_entities: entidades classificadas com features
  - ingestion_log: historico de ingestoes
  - text_annotations: textos extraidos e classificados

Interface de consulta:
  - Buscar vigas/pilares/lajes por pavimento
  - Estatisticas agregadas
  - Export para dict (alimentar Structural Analyzer)
  - Resumo para display
"""

import os
import json
import sqlite3
import logging
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS obra_profile (
    obra_id     TEXT PRIMARY KEY,
    name        TEXT,
    client_id   TEXT,
    root_path   TEXT,
    family      TEXT,
    created_at  TEXT,
    updated_at  TEXT,
    extra       TEXT
);

CREATE TABLE IF NOT EXISTS pavimentos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id     TEXT REFERENCES obra_profile(obra_id),
    name        TEXT,
    dxf_path    TEXT,
    ingested_at TEXT,
    entity_count INTEGER DEFAULT 0,
    UNIQUE(obra_id, name)
);

CREATE TABLE IF NOT EXISTS structural_entities (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id         TEXT REFERENCES obra_profile(obra_id),
    pavimento       TEXT,
    entity_id       TEXT,
    entity_type     TEXT,
    layer           TEXT,
    dxf_type        TEXT,
    bbox_xmin       REAL, bbox_xmax REAL,
    bbox_ymin       REAL, bbox_ymax REAL,
    features_json   TEXT,
    dna_key         TEXT,
    confidence      REAL,
    name            TEXT,
    dim_str         TEXT,
    text_content    TEXT,
    extra           TEXT,
    created_at      TEXT
);

CREATE TABLE IF NOT EXISTS text_annotations (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id     TEXT,
    pavimento   TEXT,
    text        TEXT,
    entity_hint TEXT,
    layer       TEXT,
    x           REAL, y REAL,
    created_at  TEXT
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    obra_id     TEXT,
    file_path   TEXT,
    family      TEXT,
    entity_count INTEGER,
    error       TEXT,
    ingested_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_entities_obra ON structural_entities(obra_id);
CREATE INDEX IF NOT EXISTS idx_entities_pav ON structural_entities(obra_id, pavimento);
CREATE INDEX IF NOT EXISTS idx_entities_type ON structural_entities(obra_id, entity_type);
CREATE INDEX IF NOT EXISTS idx_entities_dna ON structural_entities(dna_key);
"""


@dataclass
class PavimentoData:
    """Dados agregados de um pavimento."""
    name: str
    pilares: List[Dict] = field(default_factory=list)
    vigas: List[Dict] = field(default_factory=list)
    lajes: List[Dict] = field(default_factory=list)
    outros: List[Dict] = field(default_factory=list)

    @property
    def total_entities(self) -> int:
        return len(self.pilares) + len(self.vigas) + len(self.lajes) + len(self.outros)


@dataclass
class ObraProfile:
    """Perfil geral de uma obra."""
    obra_id: str
    name: str
    client_id: str = ""
    root_path: str = ""
    family: str = ""
    created_at: str = ""
    updated_at: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def summary(self) -> str:
        return f"Obra '{self.name}' [{self.obra_id[:8]}] family={self.family}"


class ObraKnowledge:
    """
    Base de conhecimento persistente para uma obra estrutural.

    Cada obra tem seu proprio arquivo SQLite em:
        {obra_root}/{obra_id}.knowledge.db

    Uso:
        knowledge = ObraKnowledge(obra_root=Path('/obras/proj1'))
        knowledge.register_obra('proj1', 'Edificio Sao Paulo', ...)
        knowledge.store_entities(pavimento='P-1', entities=structural_entities)

        # Consulta
        pav_data = knowledge.get_pavimento('P-1')
        print(len(pav_data.vigas), 'vigas em P-1')
    """

    def __init__(self, obra_root: Path, obra_id: str = ""):
        self.obra_root = Path(obra_root)
        self.obra_id = obra_id
        self._db_path: Optional[Path] = None
        self._conn: Optional[sqlite3.Connection] = None

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            db_path = self.obra_root / f"{self.obra_id or 'obra'}.knowledge.db"
            db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(SCHEMA_SQL)
            self._conn.commit()
            self._db_path = db_path
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    # ------------------------------------------------------------------
    # Registro e ingestao
    # ------------------------------------------------------------------

    def register_obra(
        self,
        obra_id: str,
        name: str,
        client_id: str = "",
        root_path: str = "",
        family: str = "",
        extra: Optional[Dict] = None,
    ):
        """Registra ou atualiza o perfil da obra."""
        self.obra_id = obra_id
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""
            INSERT OR REPLACE INTO obra_profile
            (obra_id, name, client_id, root_path, family, created_at, updated_at, extra)
            VALUES (?, ?, ?, ?, ?, COALESCE(
                (SELECT created_at FROM obra_profile WHERE obra_id=?), ?
            ), ?, ?)
        """, (obra_id, name, client_id, root_path, family,
              obra_id, now, now, json.dumps(extra or {})))
        conn.commit()
        logger.info(f"Registered obra: {obra_id} '{name}'")

    def store_entities(self, pavimento: str, entities: List[Any]):
        """
        Armazena StructuralEntity vetorizadas no knowledge base.

        Args:
            pavimento: Nome do pavimento (ex: 'P-1', '2o PAV')
            entities: Lista de StructuralEntity (do structural_vectorizer)
        """
        conn = self._get_conn()
        now = datetime.now(timezone.utc).isoformat()

        # Upsert pavimento
        conn.execute("""
            INSERT OR IGNORE INTO pavimentos (obra_id, name, ingested_at)
            VALUES (?, ?, ?)
        """, (self.obra_id, pavimento, now))

        rows = []
        text_rows = []

        for e in entities:
            raw = e.raw
            features_json = json.dumps(e.features.to_list())
            dna_key = e.features.to_dna_key()

            rows.append((
                self.obra_id, pavimento, raw.entity_id,
                e.entity_type.value, raw.layer, raw.dxf_type,
                raw.bbox_xmin, raw.bbox_xmax, raw.bbox_ymin, raw.bbox_ymax,
                features_json, dna_key, e.confidence,
                e.name, e.dim_str, raw.text_content,
                json.dumps(raw.extra), now
            ))

            if raw.text_content and raw.dxf_type in ('TEXT', 'MTEXT'):
                ip_x = (raw.bbox_xmin + raw.bbox_xmax) / 2
                ip_y = (raw.bbox_ymin + raw.bbox_ymax) / 2
                text_rows.append((
                    self.obra_id, pavimento, raw.text_content,
                    raw.entity_type_hint, raw.layer, ip_x, ip_y, now
                ))

        conn.executemany("""
            INSERT OR REPLACE INTO structural_entities
            (obra_id, pavimento, entity_id, entity_type, layer, dxf_type,
             bbox_xmin, bbox_xmax, bbox_ymin, bbox_ymax,
             features_json, dna_key, confidence, name, dim_str,
             text_content, extra, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        if text_rows:
            conn.executemany("""
                INSERT INTO text_annotations
                (obra_id, pavimento, text, entity_hint, layer, x, y, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, text_rows)

        # Atualizar contagem no pavimento
        conn.execute("""
            UPDATE pavimentos SET entity_count = ?
            WHERE obra_id = ? AND name = ?
        """, (len(entities), self.obra_id, pavimento))

        conn.commit()
        logger.info(f"Stored {len(entities)} entities for pavimento '{pavimento}'")

    def log_ingestion(self, file_path: str, family: str, entity_count: int, error: str = ""):
        """Registra log de uma ingestao."""
        conn = self._get_conn()
        conn.execute("""
            INSERT INTO ingestion_log (obra_id, file_path, family, entity_count, error, ingested_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (self.obra_id, file_path, family, entity_count, error,
              datetime.now(timezone.utc).isoformat()))
        conn.commit()

    # ------------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------------

    def get_pavimento(self, pavimento: str) -> PavimentoData:
        """Retorna dados de um pavimento completo."""
        conn = self._get_conn()
        cur = conn.execute("""
            SELECT * FROM structural_entities
            WHERE obra_id = ? AND pavimento = ?
            ORDER BY entity_type, id
        """, (self.obra_id, pavimento))
        rows = cur.fetchall()

        data = PavimentoData(name=pavimento)
        for r in rows:
            d = dict(r)
            t = d.get('entity_type', '')
            if t == 'Pilar':
                data.pilares.append(d)
            elif t == 'Viga':
                data.vigas.append(d)
            elif t == 'Laje':
                data.lajes.append(d)
            else:
                data.outros.append(d)

        return data

    def get_entities_by_type(
        self, entity_type: str, pavimento: Optional[str] = None
    ) -> List[Dict]:
        """Busca entidades por tipo, opcionalmente por pavimento."""
        conn = self._get_conn()
        if pavimento:
            cur = conn.execute("""
                SELECT * FROM structural_entities
                WHERE obra_id = ? AND entity_type = ? AND pavimento = ?
            """, (self.obra_id, entity_type, pavimento))
        else:
            cur = conn.execute("""
                SELECT * FROM structural_entities
                WHERE obra_id = ? AND entity_type = ?
            """, (self.obra_id, entity_type))
        return [dict(r) for r in cur.fetchall()]

    def search_by_dna(self, dna_key: str) -> List[Dict]:
        """Busca entidades com DNA key especifico."""
        conn = self._get_conn()
        cur = conn.execute("""
            SELECT * FROM structural_entities WHERE dna_key = ?
        """, (dna_key,))
        return [dict(r) for r in cur.fetchall()]

    def get_statistics(self) -> Dict[str, Any]:
        """Estatisticas gerais da obra."""
        conn = self._get_conn()
        cur = conn.execute("""
            SELECT entity_type, COUNT(*) as cnt
            FROM structural_entities WHERE obra_id = ?
            GROUP BY entity_type
        """, (self.obra_id,))
        stats = {r['entity_type']: r['cnt'] for r in cur.fetchall()}

        cur = conn.execute("""
            SELECT name FROM pavimentos WHERE obra_id = ?
        """, (self.obra_id,))
        pavimentos = [r['name'] for r in cur.fetchall()]

        return {
            'obra_id': self.obra_id,
            'pavimentos': pavimentos,
            'entity_counts': stats,
            'total': sum(stats.values()),
        }

    def get_profile(self) -> Optional[ObraProfile]:
        """Retorna perfil da obra."""
        conn = self._get_conn()
        cur = conn.execute("SELECT * FROM obra_profile WHERE obra_id = ?", (self.obra_id,))
        row = cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d['extra'] = json.loads(d.get('extra') or '{}')
        return ObraProfile(**d)

    def resume(self) -> str:
        """Resumo human-readable da obra."""
        stats = self.get_statistics()
        counts = stats.get('entity_counts', {})
        return (
            f"Obra {self.obra_id[:8]} | "
            f"Pavimentos: {len(stats['pavimentos'])} | "
            f"Pilares: {counts.get('Pilar', 0)} | "
            f"Vigas: {counts.get('Viga', 0)} | "
            f"Lajes: {counts.get('Laje', 0)} | "
            f"Total: {stats['total']}"
        )


def criar_conhecimento_obra(
    obra_id: str,
    obra_name: str,
    obra_root: Path,
    **kwargs,
) -> ObraKnowledge:
    """
    Factory function para criar e registrar um novo ObraKnowledge.

    Args:
        obra_id: ID unico da obra
        obra_name: Nome legivel da obra
        obra_root: Diretorio raiz da obra
        **kwargs: Campos extras do ObraProfile

    Returns:
        ObraKnowledge registrado e pronto para uso
    """
    knowledge = ObraKnowledge(obra_root=obra_root, obra_id=obra_id)
    knowledge.register_obra(
        obra_id=obra_id,
        name=obra_name,
        root_path=str(obra_root),
        **kwargs,
    )
    return knowledge
