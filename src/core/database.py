"""
DatabaseManager - Gerencia o banco de dados project_data.vision.

Tabelas: projects, works, clients, team_members, communication_history,
         training_events, pillars, beams, slabs, transformation_rules,
         dxf_entidades, rule_evaluation_log, validation_log
"""
import sqlite3
import json
import logging
import uuid
import os
import sys
import re
import inspect
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Gerencia conexão e operações no banco de dados project_data.vision."""

    def __init__(self, db_path: str = None):
        if db_path is None:
            # Tentar encontrar main.py na pilha de chamadas
            try:
                stack = inspect.stack()
                for frame_info in stack:
                    if os.path.basename(frame_info.filename) == 'main.py':
                        db_path = str(Path(frame_info.filename).parent / 'project_data.vision')
                        break
            except Exception:
                pass

            if db_path is None:
                # Fallback: dois níveis acima do arquivo atual
                db_path = str(Path(__file__).parent.parent / 'project_data.vision')

        self.db_path = db_path
        logger.info(f'DatabaseManager inicializado com path: {db_path}')
        self._init_db()

    def _init_db(self):
        """Cria as tabelas se não existirem."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            self._create_tables_if_not_exist(cursor)
            self._migrate_db(cursor)
            conn.commit()
        finally:
            conn.close()

    def _create_tables_if_not_exist(self, cursor):
        """Define o schema das tabelas."""
        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS works (
                name TEXT PRIMARY KEY,
                client_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT,
                company TEXT,
                email TEXT,
                phone TEXT,
                plan TEXT DEFAULT 'Standard',
                status TEXT DEFAULT 'Ativo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                email TEXT,
                status TEXT DEFAULT 'Offline',
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS communication_history (
                id TEXT PRIMARY KEY,
                source_type TEXT,
                sender_email TEXT,
                client_id TEXT,
                subject TEXT,
                content TEXT,
                attachments_json TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
            );

            CREATE TABLE IF NOT EXISTS project_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                doc_type TEXT,
                filename TEXT,
                path TEXT,
                content_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                dxf_path TEXT,
                author_name TEXT,
                work_name TEXT,
                pavement_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS training_events (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                event_type TEXT,
                entity_type TEXT,
                entity_id TEXT,
                before_json TEXT,
                after_json TEXT,
                correction_reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS pillars (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                type TEXT DEFAULT 'Pilar',
                area REAL,
                points_json TEXT,
                sides_data_json TEXT,
                links_json TEXT DEFAULT '{}',
                conf_map_json TEXT DEFAULT '{}',
                validated_fields_json TEXT DEFAULT '{}',
                validated_link_classes_json TEXT DEFAULT '{}',
                na_fields_json TEXT DEFAULT '{}',
                na_link_classes_json TEXT DEFAULT '{}',
                na_reasons_json TEXT DEFAULT '{}',
                issues_json TEXT DEFAULT '[]',
                id_item TEXT,
                is_validated BOOLEAN DEFAULT FALSE,
                pkl_path TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS beams (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                type TEXT DEFAULT 'Viga',
                data_json TEXT,
                links_json TEXT DEFAULT '{}',
                validated_fields_json TEXT DEFAULT '{}',
                id_item TEXT,
                is_validated BOOLEAN DEFAULT FALSE,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS slabs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                type TEXT DEFAULT 'Laje',
                data_json TEXT,
                links_json TEXT DEFAULT '{}',
                id_item TEXT,
                is_validated BOOLEAN DEFAULT FALSE,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS transformation_rules (
                id TEXT PRIMARY KEY,
                name TEXT,
                entity_type TEXT,
                field_name TEXT,
                rule_logic TEXT,
                coverage_pct REAL DEFAULT 0.0,
                accuracy_pct REAL DEFAULT 0.0,
                version TEXT DEFAULT '1.0',
                status TEXT DEFAULT 'draft',
                is_production BOOLEAN DEFAULT FALSE,
                source_obras TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS dxf_entidades (
                id TEXT PRIMARY KEY,
                obra TEXT,
                pavimento TEXT,
                entity_type TEXT,
                name TEXT,
                label TEXT,
                layer TEXT,
                x REAL,
                y REAL,
                data_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS rule_evaluation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                rule_id TEXT,
                entity_id TEXT,
                entity_type TEXT,
                validation_passed BOOLEAN,
                confidence REAL,
                execution_time_ms REAL,
                constraints_checked INTEGER DEFAULT 0,
                constraints_passed INTEGER DEFAULT 0,
                violations_count INTEGER DEFAULT 0,
                matched BOOLEAN,
                interpretation_result TEXT,
                evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS validation_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                obra TEXT,
                validation_type TEXT,
                entity_type TEXT,
                entity_id TEXT,
                entity_name TEXT,
                pavimento TEXT,
                field_name TEXT,
                field_value TEXT,
                problem_type TEXT,
                problem_detail TEXT,
                severity TEXT,
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def _migrate_db(self, cursor):
        """Adiciona colunas necessárias, corrige tipos e migra dados."""
        # Migrar works a partir de projects
        try:
            cursor.execute("""
                INSERT OR IGNORE INTO works (name)
                SELECT DISTINCT work_name FROM projects
                WHERE work_name IS NOT NULL AND work_name != ''
            """)
        except Exception:
            pass

        # Adicionar colunas faltantes via ALTER TABLE seguro
        migrations = [
            ("slabs", "type", "TEXT DEFAULT 'Laje'"),
            ("pillars", "links_json", "TEXT DEFAULT '{}'"),
            ("beams", "links_json", "TEXT DEFAULT '{}'"),
            ("beams", "validated_fields_json", "TEXT DEFAULT '{}'"),
            ("pillars", "id_item", "TEXT"),
            ("beams", "id_item", "TEXT"),
            ("slabs", "id_item", "TEXT"),
        ]
        for table, col, col_def in migrations:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_def}")
            except Exception:
                pass  # Coluna já existe

    # ── Works ──────────────────────────────────────────────────────────────

    def create_work(self, name: str, client_id: str = None) -> bool:
        """Cria uma nova Obra."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("INSERT OR IGNORE INTO works (name, client_id) VALUES (?, ?)",
                         (name, client_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro ao criar obra {name}: {e}')
            return False
        finally:
            conn.close()

    def rename_work(self, old_name: str, new_name: str) -> bool:
        """Renomeia uma Obra e atualiza referências."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE works SET name = ? WHERE name = ?", (new_name, old_name))
            conn.execute("UPDATE projects SET work_name = ? WHERE work_name = ?", (new_name, old_name))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro ao renomear obra: {e}')
            return False
        finally:
            conn.close()

    def delete_work(self, name: str) -> bool:
        """Exclui uma Obra e TODOS os seus projetos/pavimentos e itens associados."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT id FROM projects WHERE work_name = ?", (name,)).fetchall()
            for row in rows:
                pid = row[0]
                conn.execute("DELETE FROM pillars WHERE project_id = ?", (pid,))
                conn.execute("DELETE FROM beams WHERE project_id = ?", (pid,))
                conn.execute("DELETE FROM slabs WHERE project_id = ?", (pid,))
                conn.execute("DELETE FROM training_events WHERE project_id = ?", (pid,))
            conn.execute("DELETE FROM projects WHERE work_name = ?", (name,))
            conn.execute("DELETE FROM works WHERE name = ?", (name,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro ao deletar obra: {e}')
            return False
        finally:
            conn.close()

    def get_all_works(self) -> List[str]:
        """Retorna lista de todas as Obras cadastradas."""
        conn = sqlite3.connect(self.db_path)
        try:
            rows = conn.execute("SELECT name FROM works ORDER BY name ASC").fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    # ── Clients ────────────────────────────────────────────────────────────

    def add_client(self, client_data: dict) -> Optional[str]:
        """Adiciona um novo cliente manualmente."""
        conn = sqlite3.connect(self.db_path)
        try:
            cid = client_data.get('id', str(uuid.uuid4()))
            conn.execute("""
                INSERT INTO clients (id, name, company, email, phone, plan, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (cid, client_data.get('name'), client_data.get('company'),
                  client_data.get('email'), client_data.get('phone'),
                  client_data.get('plan', 'Standard'), client_data.get('status', 'Ativo')))
            conn.commit()
            return cid
        except Exception as e:
            logger.error(f'Erro ao adicionar cliente: {e}')
            return None
        finally:
            conn.close()

    def get_all_clients(self) -> List[dict]:
        """Retorna todos os clientes cadastrados."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM clients ORDER BY name ASC").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_clients_count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM clients").fetchone()[0]
        finally:
            conn.close()

    def get_works_count(self) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
        finally:
            conn.close()

    # ── Projects ───────────────────────────────────────────────────────────

    def update_project_work(self, project_id: str, work_name: str) -> bool:
        """Atualiza o nome da obra vinculada a um projeto."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("UPDATE projects SET work_name = ? WHERE id = ?", (work_name, project_id))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro ao atualizar project work: {e}')
            return False
        finally:
            conn.close()

    def get_all_projects(self, work_name: str = None) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if work_name:
                rows = conn.execute(
                    "SELECT * FROM projects WHERE work_name = ? ORDER BY work_name, name",
                    (work_name,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM projects ORDER BY work_name, name").fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_project(self, project_id: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def delete_project(self, project_id: str) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            for tbl in ('pillars', 'beams', 'slabs', 'training_events'):
                conn.execute(f"DELETE FROM {tbl} WHERE project_id = ?", (project_id,))
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro ao deletar projeto: {e}')
            return False
        finally:
            conn.close()

    # ── Structural entities ────────────────────────────────────────────────

    def get_pillars(self, project_id: str) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM pillars WHERE project_id = ?", (project_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_beams(self, project_id: str) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM beams WHERE project_id = ?", (project_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def get_slabs(self, project_id: str) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute("SELECT * FROM slabs WHERE project_id = ?", (project_id,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def update_pillar(self, pillar_id: str, data: dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            sets = ', '.join(f"{k} = ?" for k in data)
            vals = list(data.values()) + [pillar_id]
            conn.execute(f"UPDATE pillars SET {sets} WHERE id = ?", vals)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro update_pillar: {e}')
            return False
        finally:
            conn.close()

    def update_beam(self, beam_id: str, data: dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            sets = ', '.join(f"{k} = ?" for k in data)
            vals = list(data.values()) + [beam_id]
            conn.execute(f"UPDATE beams SET {sets} WHERE id = ?", vals)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro update_beam: {e}')
            return False
        finally:
            conn.close()

    def update_slab(self, slab_id: str, data: dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            sets = ', '.join(f"{k} = ?" for k in data)
            vals = list(data.values()) + [slab_id]
            conn.execute(f"UPDATE slabs SET {sets} WHERE id = ?", vals)
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro update_slab: {e}')
            return False
        finally:
            conn.close()

    # ── Training events ────────────────────────────────────────────────────

    def save_training_event(self, event_data: dict) -> Optional[str]:
        conn = sqlite3.connect(self.db_path)
        try:
            eid = event_data.get('id', str(uuid.uuid4()))
            conn.execute("""
                INSERT INTO training_events
                (id, project_id, event_type, entity_type, entity_id,
                 before_json, after_json, correction_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (eid, event_data.get('project_id'), event_data.get('event_type'),
                  event_data.get('entity_type'), event_data.get('entity_id'),
                  json.dumps(event_data.get('before', {})),
                  json.dumps(event_data.get('after', {})),
                  event_data.get('correction_reason', '')))
            conn.commit()
            return eid
        except Exception as e:
            logger.error(f'Erro save_training_event: {e}')
            return None
        finally:
            conn.close()

    def get_training_events(self, limit: int = 100) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "SELECT * FROM training_events ORDER BY created_at DESC LIMIT ?",
                (limit,)).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    # ── Transformation rules ───────────────────────────────────────────────

    def get_transformation_rules(self, entity_type: str = None) -> List[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if entity_type:
                rows = conn.execute(
                    "SELECT * FROM transformation_rules WHERE entity_type = ? ORDER BY accuracy_pct DESC",
                    (entity_type,)).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM transformation_rules ORDER BY entity_type, accuracy_pct DESC"
                ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def upsert_transformation_rule(self, rule_data: dict) -> bool:
        conn = sqlite3.connect(self.db_path)
        try:
            rid = rule_data.get('id', str(uuid.uuid4()))
            conn.execute("""
                INSERT OR REPLACE INTO transformation_rules
                (id, name, entity_type, field_name, rule_logic, coverage_pct,
                 accuracy_pct, version, status, is_production, source_obras, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (rid, rule_data.get('name'), rule_data.get('entity_type'),
                  rule_data.get('field_name'),
                  json.dumps(rule_data.get('rule_logic', {})) if isinstance(rule_data.get('rule_logic'), dict) else rule_data.get('rule_logic', '{}'),
                  rule_data.get('coverage_pct', 0.0),
                  rule_data.get('accuracy_pct', 0.0),
                  rule_data.get('version', '1.0'),
                  rule_data.get('status', 'draft'),
                  rule_data.get('is_production', False),
                  rule_data.get('source_obras', '')))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f'Erro upsert_transformation_rule: {e}')
            return False
        finally:
            conn.close()

    # ── Stats ──────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        conn = sqlite3.connect(self.db_path)
        try:
            stats = {}
            for table in ('works', 'clients', 'projects', 'pillars', 'beams',
                          'slabs', 'training_events', 'transformation_rules'):
                try:
                    stats[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                except Exception:
                    stats[table] = 0
            return stats
        finally:
            conn.close()
