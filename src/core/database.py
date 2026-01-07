import sqlite3
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path

class DatabaseManager:
    """
    Gerencia a persistência local dos dados do projeto usando SQLite.
    Salva o estado dos elementos identificados (Pilares, Vigas, Lajes).
    """
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Cria as tabelas se não existirem."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        self._create_tables_if_not_exist(cursor)

        # Migração: Verificar se colunas de projeto existem (caso a tabela já existisse sem elas)
        self._migrate_db(cursor)

        conn.commit()
        conn.close()

    def _create_tables_if_not_exist(self, cursor):
        """Define o schema das tabelas."""
        # Tabela de Obras (Persistência independente de projetos)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS works (
                name TEXT PRIMARY KEY,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de Projetos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT,
                dxf_path TEXT,
                work_name TEXT,
                pavement_name TEXT,
                level_arrival TEXT,
                level_exit TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabela de Eventos de Treinamento (Log para Active Learning)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_events (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                type TEXT,        -- 'manual_correction', 'auto_validation'
                role TEXT,        -- 'pillar_dim', 'beam_name'
                context_dna_json TEXT, -- Assinatura vetorial do momento
                target_value TEXT,     -- O valor correto (label)
                status TEXT,           -- 'valid', 'fail'
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Pilares (Schema expandido para IA + Projeto)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pillars (
                id TEXT PRIMARY KEY, 
                project_id TEXT,
                name TEXT,
                type TEXT,
                area REAL,
                points_json TEXT,
                sides_data_json TEXT, 
                links_json TEXT, 
                conf_map_json TEXT, 
                validated_fields_json TEXT, 
                issues_json TEXT, 
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        # Tabela de Lajes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slabs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                area REAL,
                points_json TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Vigas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beams (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                data_json TEXT, 
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

    def _migrate_db(self, cursor):
        """Adiciona colunas necessárias, corrige tipos e migra dados."""
        # ... (previous migration code) ...
        # Migração de Obras existentes em Projetos para a tabela Works
        try:
            cursor.execute("INSERT OR IGNORE INTO works (name) SELECT DISTINCT work_name FROM projects WHERE work_name IS NOT NULL AND work_name != ''")
        except Exception as e:
            logging.error(f"Error migrating works: {e}")

        # ... (rest of migration code)

    # ... (existing methods) ...

    def create_work(self, name: str):
        """Cria uma nova Obra vazia."""
        conn = self._get_conn()
        try:
            conn.execute('INSERT OR IGNORE INTO works (name) VALUES (?)', (name,))
            conn.commit()
        finally:
            conn.close()

    def rename_work(self, old_name: str, new_name: str):
        """Renomeia uma Obra e atualiza referências."""
        conn = self._get_conn()
        try:
            # 1. Update works table
            conn.execute('UPDATE works SET name = ? WHERE name = ?', (new_name, old_name))
            # 2. Update projects reference
            conn.execute('UPDATE projects SET work_name = ? WHERE work_name = ?', (new_name, old_name))
            conn.commit()
        finally:
            conn.close()

    def delete_work(self, name: str):
        """Exclui uma Obra (seus projetos ficam sem obra)."""
        conn = self._get_conn()
        try:
            # 1. Update projects to remove work ref
            conn.execute('UPDATE projects SET work_name = "" WHERE work_name = ?', (name,))
            # 2. Delete from works
            conn.execute('DELETE FROM works WHERE name = ?', (name,))
            conn.commit()
        finally:
            conn.close()

    def get_all_works(self) -> List[str]:
        """Retorna lista de todas as Obras cadastradas."""
        conn = self._get_conn()
        try:
            cursor = conn.execute('SELECT name FROM works ORDER BY name ASC')
            return [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS training_events (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                type TEXT,        -- 'manual_correction', 'auto_validation'
                role TEXT,        -- 'pillar_dim', 'beam_name'
                context_dna_json TEXT, -- Assinatura vetorial do momento
                target_value TEXT,     -- O valor correto (label)
                status TEXT,           -- 'valid', 'fail'
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Pilares (Schema expandido para IA + Projeto)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pillars (
                id TEXT PRIMARY KEY, 
                project_id TEXT,
                name TEXT,
                type TEXT,
                area REAL,
                points_json TEXT,
                sides_data_json TEXT, 
                links_json TEXT, 
                conf_map_json TEXT, 
                validated_fields_json TEXT, 
                issues_json TEXT, 
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        # Tabela de Lajes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS slabs (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                area REAL,
                points_json TEXT,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Vigas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS beams (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                data_json TEXT, 
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

    def _migrate_db(self, cursor):
        """Adiciona colunas necessárias e corrige tipos de dados incompatíveis."""
        
        # Migração de Obras existentes em Projetos para a tabela Works (Executa primeiro para popular)
        try:
            # Seleciona de projects apenas se work_name não for nulo/vazio
            cursor.execute("INSERT OR IGNORE INTO works (name) SELECT DISTINCT work_name FROM projects WHERE work_name IS NOT NULL AND work_name != ''")
        except Exception as e:
            logging.error(f"Error migrating works: {e}")

        # 1. Verificar tipo da coluna ID na tabela pillars
        need_recreation = False
        try:
            cursor.execute("PRAGMA table_info(pillars)")
            cols = cursor.fetchall()  # [(cid, name, type, notnull, dflt_value, pk), ...]
            for c in cols:
                if c[1] == 'id' and 'INT' in c[2].upper():
                    logging.warning("Detectado esquema antigo (ID INTEGER). Tabelas serão recriadas.")
                    need_recreation = True
                    break
        except Exception:
            pass

        if need_recreation:
            tables = ['pillars', 'slabs', 'beams']
            for t in tables:
                try:
                    cursor.execute(f"ALTER TABLE {t} RENAME TO {t}_backup_legacy")
                except Exception as e:
                    logging.warning(f"Erro ao renomear {t}: {e}") # Talvez não exista?
            
            # As tabelas serão recriadas pelo _init_db (re-chamada ou fluxo seguinte)
            self._create_tables_if_not_exist(cursor) # Extrairemos esse método


        tables_to_check = {
            'pillars': ['project_id', 'links_json', 'conf_map_json', 'validated_fields_json', 'issues_json', 'sides_data_json', 'points_json'],
            'slabs': ['project_id'],
            'beams': ['project_id'],
            'projects': ['work_name', 'pavement_name', 'level_arrival', 'level_exit']
        }
        
        for table, columns in tables_to_check.items():
            # (Código de verificação de colunas existente...)
            try:
                cursor.execute(f"PRAGMA table_info({table})")
                existing_cols = [col[1] for col in cursor.fetchall()]
                
                for col in columns:
                    if col not in existing_cols:
                        try:
                            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                            logging.info(f"Migration: Added column {col} to table {table}")
                        except Exception as e:
                            logging.error(f"Migration error on {table}.{col}: {e}")
            except:
                pass 

    def create_work(self, name: str):
        """Cria uma nova Obra vazia."""
        conn = self._get_conn()
        try:
            conn.execute('INSERT OR IGNORE INTO works (name) VALUES (?)', (name,))
            conn.commit()
        finally:
            conn.close()

    def rename_work(self, old_name: str, new_name: str):
        """Renomeia uma Obra e atualiza referências."""
        conn = self._get_conn()
        try:
            # 1. Update works table
            conn.execute('UPDATE works SET name = ? WHERE name = ?', (new_name, old_name))
            # 2. Update projects reference
            conn.execute('UPDATE projects SET work_name = ? WHERE work_name = ?', (new_name, old_name))
            conn.commit()
        finally:
            conn.close()

    def delete_work(self, name: str):
        """Exclui uma Obra (seus projetos ficam sem obra)."""
        conn = self._get_conn()
        try:
            # 1. Update projects to remove work ref
            conn.execute('UPDATE projects SET work_name = "" WHERE work_name = ?', (name,))
            # 2. Delete from works
            conn.execute('DELETE FROM works WHERE name = ?', (name,))
            conn.commit()
        finally:
            conn.close()

    def get_all_works(self) -> List[str]:
        """Retorna lista de todas as Obras cadastradas."""
        conn = self._get_conn()
        try:
            cursor = conn.execute('SELECT name FROM works ORDER BY name ASC')
            return [r[0] for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_project_metadata(self, pid: str, metadata: Dict):
        """Atualiza metadados do projeto (Obra, Pavimento, Níveis)"""
        conn = self._get_conn()
        try:
            conn.execute('''
                UPDATE projects 
                SET work_name=?, pavement_name=?, level_arrival=?, level_exit=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (metadata.get('work_name'), metadata.get('pavement_name'), 
                  metadata.get('level_arrival'), metadata.get('level_exit'), pid))
            conn.commit()
        except Exception as e:
            logging.error(f"Failed to update metadata for {pid}: {e}")
        finally:
            conn.close() 

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def create_project(self, name: str, dxf_path: str) -> str:
        """Cria novo projeto e retorna ID."""
        import uuid
        project_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute('INSERT INTO projects (id, name, dxf_path) VALUES (?, ?, ?)', 
                        (project_id, name, dxf_path))
            conn.commit()
            return project_id
        except Exception as e:
            logging.error(f"Erro criar projeto: {e}")
            return None
        finally:
            conn.close()

    def get_projects(self) -> List[Dict]:
        """Lista projetos recentes."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM projects ORDER BY updated_at DESC')
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """Recupera um projeto pelo ID."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM projects WHERE id = ?', (project_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def log_training_event(self, event_data: Dict):
        """Registra um evento de treinamento."""
        import uuid
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()),
                event_data.get('project_id'),
                event_data.get('type'),
                event_data.get('role'),
                json.dumps(event_data.get('dna', [])),
                event_data.get('value'),
                event_data.get('status')
            ))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro log treino: {e}")
        finally:
            conn.close()

    def get_training_events(self, project_id: str) -> List[Dict]:
        """Recupera eventos de treino para um projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM training_events WHERE project_id = ? ORDER BY timestamp DESC', (project_id,))
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar eventos: {e}")
            return []
        finally:
            conn.close()

    def save_pillar(self, p: Dict[str, Any], project_id: str):
        """Salva ou atualiza um pilar (UPSERT) vinculado a um projeto."""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # Serialização segura
            points_json = json.dumps(p.get('points', []))
            sides_json = json.dumps(p.get('sides_data', {}))
            links_json = json.dumps(p.get('links', {}))
            conf_map_json = json.dumps(p.get('confidence_map', {}))
            val_fields_json = json.dumps(p.get('validated_fields', []))
            issues_json = json.dumps(p.get('issues', []))
            
            p_id = str(p.get('id', ''))
            
            cursor.execute('''
                INSERT INTO pillars (
                    id, project_id, name, type, area, points_json, sides_data_json, 
                    links_json, conf_map_json, validated_fields_json, 
                    issues_json, is_validated
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    type=excluded.type,
                    area=excluded.area,
                    sides_data_json=excluded.sides_data_json,
                    links_json=excluded.links_json,
                    conf_map_json=excluded.conf_map_json,
                    validated_fields_json=excluded.validated_fields_json,
                    issues_json=excluded.issues_json,
                    is_validated=excluded.is_validated
            ''', (
                p_id,
                project_id,
                p.get('name'), 
                p.get('type'), 
                float(p.get('area_val', 0.0)), 
                points_json, 
                sides_json,
                links_json,
                conf_map_json,
                val_fields_json,
                issues_json,
                1 if p.get('is_validated') else 0
            ))
            
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao salvar pilar no DB: {e}")
        finally:
            conn.close()

    def load_pillars(self, project_id: str) -> List[Dict]:
        """Carrega todos os pilares de um projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        pillars = []
        try:
            cursor.execute('SELECT * FROM pillars WHERE project_id = ?', (project_id,))
            rows = cursor.fetchall()
            
            for row in rows:
                p = dict(row)
                p['points'] = json.loads(p['points_json'])
                p['sides_data'] = json.loads(p['sides_data_json'])
                p['links'] = json.loads(p.get('links_json', '{}'))
                p['confidence_map'] = json.loads(p.get('conf_map_json', '{}'))
                p['validated_fields'] = json.loads(p.get('validated_fields_json', '[]'))
                p['issues'] = json.loads(p.get('issues_json', '[]'))
                p['is_validated'] = bool(p['is_validated'])
                pillars.append(p)
        except Exception as e:
            logging.error(f"Erro ao carregar pilares: {e}")
        finally:
            conn.close()
        return pillars

    def clear_project(self, project_id: str):
        """Limpa dados de um projeto específico."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM pillars WHERE project_id = ?', (project_id,))
        cursor.execute('DELETE FROM slabs WHERE project_id = ?', (project_id,))
        cursor.execute('DELETE FROM beams WHERE project_id = ?', (project_id,))
        conn.commit()
        conn.close()

    def save_slab(self, s: Dict[str, Any], project_id: str):
        """Salva uma laje vinculada ao projeto."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO slabs (id, project_id, name, area, points_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    area=excluded.area,
                    points_json=excluded.points_json
            ''', (
                s['id'], project_id, s.get('name'), 
                float(s.get('area', 0.0)), json.dumps(s.get('points', []))
            ))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao salvar laje: {e}")
        finally:
            conn.close()

    def load_slabs(self, project_id: str) -> List[Dict]:
        """Carrega lajes de um projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        slabs = []
        try:
            cursor.execute('SELECT * FROM slabs WHERE project_id = ?', (project_id,))
            for row in cursor.fetchall():
                s = dict(row)
                s['points'] = json.loads(s['points_json'])
                slabs.append(s)
        except Exception as e:
            logging.error(f"Erro ao carregar lajes: {e}")
        finally:
            conn.close()
        return slabs
    def save_beam(self, b: Dict[str, Any], project_id: str):
        """Salva uma viga vinculada ao projeto."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO beams (id, project_id, name, data_json, is_validated)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    data_json=excluded.data_json,
                    is_validated=excluded.is_validated
            ''', (
                b['id'], project_id, b.get('name'), 
                json.dumps(b), 1 if b.get('is_validated') else 0
            ))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao salvar viga: {e}")
        finally:
            conn.close()

    def load_beams(self, project_id: str) -> List[Dict]:
        """Carrega vigas de um projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        beams = []
        try:
            cursor.execute('SELECT * FROM beams WHERE project_id = ?', (project_id,))
            for row in cursor.fetchall():
                b = json.loads(row['data_json'])
                b['is_validated'] = bool(row['is_validated'])
                beams.append(b)
        except Exception as e:
            logging.error(f"Erro ao carregar vigas: {e}")
        finally:
            conn.close()
        return beams
    def export_project_data(self, project_id: str) -> Dict[str, Any]:
        """Exporta TODOS os dados de um projeto para um dicionário (Backup/Sharing)."""
        data = {}
        
        # 1. Project Info
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
            row = cursor.fetchone()
            if row:
                data['project'] = dict(row)
            else:
                return {} # Projeto não encontrado
        finally:
            conn.close()

        # 2. Entities
        data['pillars'] = self.load_pillars(project_id)
        data['slabs'] = self.load_slabs(project_id)
        data['beams'] = self.load_beams(project_id)
        data['training'] = self.get_training_events(project_id)
        
        return data

    def import_project_data(self, data: Dict[str, Any]) -> str:
        """Importa dados de projeto. Atualiza se existir, cria se não."""
        p_info = data.get('project')
        if not p_info: return None
        
        p_id = p_info['id']
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # 1. Upsert Project (Including Metadata)
            cursor.execute('''
                INSERT INTO projects (id, name, dxf_path, work_name, pavement_name, level_arrival, level_exit, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    dxf_path=excluded.dxf_path,
                    work_name=excluded.work_name,
                    pavement_name=excluded.pavement_name,
                    level_arrival=excluded.level_arrival,
                    level_exit=excluded.level_exit
            ''', (
                p_id, 
                p_info['name'], 
                p_info['dxf_path'],
                p_info.get('work_name', ''),
                p_info.get('pavement_name', ''),
                p_info.get('level_arrival', ''),
                p_info.get('level_exit', ''),
                p_info.get('created_at')
            ))
            
            conn.commit() # Commit parcial para garantir ID
            
        except Exception as e:
            logging.error(f"Erro ao importar tabela projeto: {e}")
            return None
        finally:
            conn.close()
            
        # 2. Upsert Entities (Usando métodos existentes)
        for p in data.get('pillars', []):
            self.save_pillar(p, p_id)
            
        for s in data.get('slabs', []):
            self.save_slab(s, p_id)
            
        for b in data.get('beams', []):
            self.save_beam(b, p_id)

        # 3. Upsert Training Events
        self._import_training_events(data.get('training', []))
        
        return p_id

    def _import_training_events(self, events: List[Dict]):
        if not events: return
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            for e in events:
                keys = list(e.keys())
                vals = list(e.values())
                placeholders = ','.join(['?']*len(keys))
                cols = ','.join(keys)
                
                # Tenta INSERT OR IGNORE se tiver ID
                sql = f"INSERT OR IGNORE INTO training_events ({cols}) VALUES ({placeholders})"
                cursor.execute(sql, vals)
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao importar eventos de treino: {e}")
        finally:
            conn.close()

    def delete_project_fully(self, project_id: str):
        """Remove completamente um projeto e seus dados."""
        self.clear_project(project_id) # Remove entities
        
        conn = self._get_conn()
        try:
            conn.execute('DELETE FROM training_events WHERE project_id = ?', (project_id,))
            conn.execute('DELETE FROM projects WHERE id = ?', (project_id,))
            conn.commit()
        finally:
            conn.close()

    def rename_project(self, project_id: str, new_name: str):
        """Renomeia um projeto."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE projects SET name = ? WHERE id = ?', (new_name, project_id))
            conn.commit()
        finally:
            conn.close()

    def update_project_work(self, project_id: str, new_work_name: str):
        """Move projeto para outra Obra."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE projects SET work_name = ? WHERE id = ?', (new_work_name, project_id))
            conn.commit()
        finally:
            conn.close()


    def duplicate_project(self, source_pid: str, target_work_name: str = None) -> str:
        """Duplica um projeto existente."""
        data = self.export_project_data(source_pid)
        if not data: return None
        
        import uuid
        new_id = str(uuid.uuid4())
        
        # Modify ID and Metadata for new project
        data['project']['id'] = new_id
        data['project']['name'] = f"{data['project']['name']} (Cópia)"
        if target_work_name is not None:
             data['project']['work_name'] = target_work_name
             
        # Import as new
        return self.import_project_data(data)
