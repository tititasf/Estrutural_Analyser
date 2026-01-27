import sqlite3
import json
import logging
import uuid
import os
import sys
import inspect
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path

class DatabaseManager:
    """
    Gerencia a persistência local dos dados do projeto usando SQLite.
    Salva o estado dos elementos identificados (Pilares, Vigas, Lajes).
    """
    def __init__(self, db_path: str = None):
        # Garantir caminho absoluto baseado no diretório do script principal
        if db_path is None:
            # Tentar encontrar o diretório do projeto (onde está main.py)
            # Método 1: Procurar main.py no stack trace
            base_dir = None
            for frame_info in inspect.stack():
                filename = frame_info.filename
                if 'main.py' in filename or filename.endswith('main.py'):
                    base_dir = os.path.dirname(os.path.abspath(filename))
                    break
            
            # Método 2: Se não encontrou, usar diretório do arquivo que chamou
            if base_dir is None:
                # Procurar no __main__ module
                main_module = sys.modules.get('__main__', None)
                if main_module and hasattr(main_module, '__file__'):
                    main_file = main_module.__file__
                    if main_file:
                        base_dir = os.path.dirname(os.path.abspath(main_file))
            
            # Método 3: Fallback - diretório atual
            if base_dir is None:
                base_dir = os.getcwd()
            
            db_path = os.path.join(base_dir, "project_data.vision")
        else:
            # Se path fornecido, garantir que seja absoluto
            if not os.path.isabs(db_path):
                # Usar mesmo método para encontrar base_dir
                base_dir = None
                for frame_info in inspect.stack():
                    filename = frame_info.filename
                    if 'main.py' in filename or filename.endswith('main.py'):
                        base_dir = os.path.dirname(os.path.abspath(filename))
                        break
                if base_dir is None:
                    base_dir = os.getcwd()
                db_path = os.path.join(base_dir, db_path)
        
        self.db_path = os.path.abspath(db_path)
        # Log para debug (pode remover depois)
        logging.debug(f"DatabaseManager inicializado com path: {self.db_path}")
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
        # Tabela de Obras
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS works (
                name TEXT PRIMARY KEY,
                client_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de Clientes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS clients (
                id TEXT PRIMARY KEY,
                name TEXT,
                company TEXT,
                email TEXT,
                phone TEXT,
                plan TEXT DEFAULT 'Standard',
                status TEXT DEFAULT 'Ativo',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de Membros da Equipe
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS team_members (
                id TEXT PRIMARY KEY,
                name TEXT,
                role TEXT,
                email TEXT,
                status TEXT DEFAULT 'Offline',
                last_active TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Tabela de Histórico de Comunicação e Documentos Recebidos
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS communication_history (
                id TEXT PRIMARY KEY,
                source_type TEXT, -- 'email', 'upload', 'system'
                sender_email TEXT,
                client_id TEXT,
                subject TEXT,
                content TEXT,
                attachments_json TEXT,
                received_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(client_id) REFERENCES clients(id)
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
                client_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                author_name TEXT,
                sync_status TEXT DEFAULT 'pending'
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
                validated_link_classes_json TEXT,
                na_fields_json TEXT,
                na_link_classes_json TEXT,
                na_reasons_json TEXT,
                issues_json TEXT, 
                id_item TEXT,
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
                type TEXT DEFAULT 'Laje',
                area REAL,
                points_json TEXT,
                links_json TEXT,
                validated_fields_json TEXT,
                validated_link_classes_json TEXT,
                na_fields_json TEXT,
                na_link_classes_json TEXT,
                na_reasons_json TEXT,
                issues_json TEXT,
                id_item TEXT,
                is_validated BOOLEAN DEFAULT 0,
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
                sides_data_json TEXT,
                links_json TEXT,
                validated_fields_json TEXT,
                validated_link_classes_json TEXT,
                na_fields_json TEXT,
                na_link_classes_json TEXT,
                na_reasons_json TEXT,
                issues_json TEXT,
                id_item TEXT,
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Pré-processamento (Marco DXF)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pre_processing (
                project_id TEXT PRIMARY KEY,
                data_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        # Tabela de Contornos (Marcos Separados)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contours (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                data_json TEXT,
                is_validated BOOLEAN DEFAULT 0,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')
        
        # Tabela de Documentos do Projeto
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_documents (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                name TEXT,
                file_path TEXT,
                extension TEXT,
                phase INTEGER,
                category TEXT,
                sync_status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Especificações Técnicas
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS project_specifications (
                project_id TEXT PRIMARY KEY,
                content_json TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id)
            )
        ''')

        # Tabela de Scripts Gerados
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS generated_scripts (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                pavement_name TEXT,
                item_id TEXT,
                item_type TEXT, -- 'pilar', 'viga_lateral', 'viga_fundo', 'laje'
                script_path TEXT,
                generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(project_id) REFERENCES projects(id),
                UNIQUE(project_id, pavement_name, item_id, item_type)
            )
        ''')

    def _migrate_db(self, cursor):
        """Adiciona colunas necessárias, corrige tipos e migra dados."""
        logging.info("Checking database migrations...")
        
        # Helper para verificar e adicionar colunas
        def _check_and_add_column(table_name, column_name, column_type):
            try:
                # Verificar se a coluna já existe
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [info[1] for info in cursor.fetchall()]
                
                if column_name not in columns:
                    cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
                    logging.info(f"✅ Migração: Coluna '{column_name}' adicionada à tabela '{table_name}'.")
                else:
                    logging.debug(f"ℹ️ Coluna '{column_name}' já existe em '{table_name}'.")
            except Exception as e:
                logging.error(f"❌ Erro na migração ({table_name}.{column_name}): {e}")

        # Migração de Obras existentes
        try:
            cursor.execute("INSERT OR IGNORE INTO works (name) SELECT DISTINCT work_name FROM projects WHERE work_name IS NOT NULL AND work_name != ''")
        except Exception as e: pass

        # --- NOVAS COLUNAS ---
        
        # SLABS
        _check_and_add_column('slabs', 'type', "TEXT DEFAULT 'Laje'")
        _check_and_add_column('slabs', 'links_json', 'TEXT')
        _check_and_add_column('slabs', 'validated_fields_json', 'TEXT')
        _check_and_add_column('slabs', 'issues_json', 'TEXT')
        _check_and_add_column('slabs', 'is_validated', 'BOOLEAN DEFAULT 0')
        _check_and_add_column('slabs', 'id_item', 'TEXT')
        
        # PILLARS
        _check_and_add_column('pillars', 'id_item', 'TEXT')
        
        # BEAMS
        _check_and_add_column('beams', 'id_item', 'TEXT')
        _check_and_add_column('beams', 'sides_data_json', 'TEXT')
        _check_and_add_column('beams', 'links_json', 'TEXT')
        _check_and_add_column('beams', 'validated_fields_json', 'TEXT')
        _check_and_add_column('beams', 'issues_json', 'TEXT')
        _check_and_add_column('beams', 'is_validated', 'BOOLEAN DEFAULT 0')

        # PROJECTS
        _check_and_add_column('projects', 'last_sync_at', 'TIMESTAMP')
        _check_and_add_column('projects', 'description', 'TEXT')
        _check_and_add_column('projects', 'client_id', 'TEXT')
        _check_and_add_column('projects', 'deadline', 'TEXT')
        _check_and_add_column('projects', 'author_name', "TEXT DEFAULT 'Local'")

        # WORKS
        _check_and_add_column('works', 'client_id', 'TEXT')
        _check_and_add_column('works', 'num_pavements', 'INTEGER')
        _check_and_add_column('works', 'num_towers', 'INTEGER')
        _check_and_add_column('works', 'total_pilares', 'INTEGER')
        _check_and_add_column('works', 'total_vigas', 'INTEGER')
        _check_and_add_column('works', 'total_lajes', 'INTEGER')
        _check_and_add_column('works', 'technical_specs', 'TEXT')
        _check_and_add_column('works', 'last_sync_at', 'TIMESTAMP')

        # GLOBAL N/A AND VALIDATION COLUMNS FOR ALL CORE TABLES
        for table in ['pillars', 'beams', 'slabs']:
            _check_and_add_column(table, 'validated_link_classes_json', 'TEXT')
            _check_and_add_column(table, 'na_fields_json', 'TEXT')
            _check_and_add_column(table, 'na_link_classes_json', 'TEXT')
            _check_and_add_column(table, 'na_reasons_json', 'TEXT')
            _check_and_add_column(table, 'pkl_path', 'TEXT') # Path to serialized .pkl file

        # DOCUMENTS
        _check_and_add_column('project_documents', 'work_name', 'TEXT')
        _check_and_add_column('project_documents', 'file_data', 'TEXT') # Base64 cache
        _check_and_add_column('project_documents', 'storage_path', 'TEXT') # Supabase Storage Path
        _check_and_add_column('project_documents', 'phase', 'INTEGER')
        _check_and_add_column('project_documents', 'category', 'TEXT')

        # CLIENTS
        _check_and_add_column('clients', 'address', 'TEXT')
        _check_and_add_column('clients', 'description', 'TEXT')


    def create_work(self, name: str, client_id: str = None):
        """Cria uma nova Obra."""
        conn = self._get_conn()
        try:
            conn.execute('INSERT OR IGNORE INTO works (name, client_id) VALUES (?, ?)', (name, client_id))
            conn.commit()
        finally:
            conn.close()

    def rename_work(self, old_name: str, new_name: str):
        """Renomeia uma Obra e atualiza referências."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE works SET name = ? WHERE name = ?', (new_name, old_name))
            conn.execute('UPDATE projects SET work_name = ? WHERE work_name = ?', (new_name, old_name))
            conn.commit()
        finally:
            conn.close()

    def delete_work(self, name: str):
        """Exclui uma Obra e TODOS os seus projetos/pavimentos e itens associados."""
        conn = self._get_conn()
        try:
            # 1. Buscar IDs dos projetos vinculados
            cursor = conn.execute('SELECT id FROM projects WHERE work_name = ?', (name,))
            project_ids = [row[0] for row in cursor.fetchall()]
            
            if project_ids:
                # 2. Excluir itens vinculados a esses projetos
                placeholders = ','.join(['?'] * len(project_ids))
                
                # Excluir documentos
                conn.execute(f'DELETE FROM project_documents WHERE project_id IN ({placeholders})', project_ids)
                
                # Excluir eventos de treino
                conn.execute(f'DELETE FROM training_events WHERE project_id IN ({placeholders})', project_ids)
                
                # Excluir entidades (Pilares, Vigas, Lajes)
                conn.execute(f'DELETE FROM pillars WHERE project_id IN ({placeholders})', project_ids)
                conn.execute(f'DELETE FROM beams WHERE project_id IN ({placeholders})', project_ids)
                conn.execute(f'DELETE FROM slabs WHERE project_id IN ({placeholders})', project_ids)
                conn.execute(f'DELETE FROM contours WHERE project_id IN ({placeholders})', project_ids)
                
                # Excluir Pré-processamento
                conn.execute(f'DELETE FROM pre_processing WHERE project_id IN ({placeholders})', project_ids)
                
                # Excluir especificações
                conn.execute(f'DELETE FROM project_specifications WHERE project_id IN ({placeholders})', project_ids)

                # 3. Excluir os projetos em si
                conn.execute(f'DELETE FROM projects WHERE id IN ({placeholders})', project_ids)

            # 4. Excluir documentos da OBRA (sem projeto específico)
            conn.execute('DELETE FROM project_documents WHERE work_name = ?', (name,))

            # 5. Excluir a Obra
            conn.execute('DELETE FROM works WHERE name = ?', (name,))
            conn.commit()
            logging.info(f"Obra '{name}' e {len(project_ids)} pavimentos excluídos com sucesso.")
        except Exception as e:
            logging.error(f"Erro ao excluir obra '{name}': {e}")
            raise e
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

    def add_client(self, client_data: Dict[str, str]) -> str:
        """Adiciona um novo cliente manualmente."""
        conn = self._get_conn()
        try:
            client_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO clients (id, name, company, email, phone, plan, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (
                client_id,
                client_data.get('name'),
                client_data.get('company'),
                client_data.get('email'),
                client_data.get('phone'),
                client_data.get('size', 'Standard'), # Using 'size' map to 'plan' for now or add column
                'Ativo'
            ))
            
            # Update description if column exists (migration needed if not)
            # For now assuming description goes to a notes field or we add it. 
            # Let's check schema: id, name, company, email, phone, plan, status. 
            # We might need to add 'description' column.
            
            conn.commit()
            return client_id
        except Exception as e:
            logging.error(f"Erro ao adicionar cliente: {e}")
            raise e
        finally:
            conn.close()

    def update_project_work(self, project_id: str, work_name: str):
        """Atualiza o nome da obra vinculada a um projeto."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE projects SET work_name = ? WHERE id = ?', (work_name, project_id))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao atualizar obra do projeto {project_id}: {e}")
            raise e
        finally:
            conn.close()

    def get_all_clients(self) -> List[Dict]:
        """Retorna todos os clientes cadastrados."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM clients ORDER BY name ASC')
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def save_client(self, name, company, email, phone, plan):
        """Wrapper legado/convenience para add_client"""
        return self.add_client({
            "name": name, "company": company, "email": email, "phone": phone, "size": plan
        })
    
    def log_communication(self, client_id, source_type, sender, subject, content, attachments=[], received_at=None, **kwargs):
        """Registra comunicação (Email/Upload)"""
        conn = self._get_conn()
        try:
            comm_id = str(uuid.uuid4())
            
            # Use provided timestamp or current time
            if not received_at:
                received_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Check for duplicates (Sender + Subject + Date + Type)
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id FROM communication_history 
                WHERE sender_email = ? AND subject = ? AND received_at = ? AND source_type = ?
            ''', (sender, subject, received_at, source_type))
            existing = cursor.fetchone()
            
            if existing:
                return existing[0]

            conn.execute('''
                INSERT INTO communication_history (id, source_type, sender_email, client_id, subject, content, attachments_json, received_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (comm_id, source_type, sender, client_id, subject, content, json.dumps(attachments), received_at))
            conn.commit()
            return comm_id
        except Exception as e:
            logging.error(f"Erro ao logar comunicação: {e}")
        finally:
            conn.close()

    def cleanup_duplicates(self):
        """Remove emails duplicados do histórico (mantém apenas 1 de cada)."""
        conn = self._get_conn()
        try:
            conn.execute('''
                DELETE FROM communication_history
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM communication_history
                    GROUP BY sender_email, subject, received_at, source_type
                )
            ''')
            conn.commit()
            # logging.info("Limpeza de duplicatas concluída.")
            logging.debug("Limpeza de duplicatas concluída.")
        except Exception as e:
            logging.error(f"Erro na limpeza: {e}")
        finally:
            conn.close()

    def get_communication_history(self, client_id=None) -> List[Dict]:
        """Busca histórico de comunicação, opcionalmente filtrado por cliente."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            sql = 'SELECT * FROM communication_history'
            params = []
            if client_id:
                sql += ' WHERE client_id = ?'
                params.append(client_id)
            sql += ' ORDER BY received_at DESC'
            
            cursor = conn.execute(sql, tuple(params))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def save_team_member(self, name, role, email, status):
        """Salva ou atualiza membro da equipe (Mock local para cache)"""
        conn = self._get_conn()
        try:
            # Check if exists by email
            cur = conn.execute('SELECT id FROM team_members WHERE email = ?', (email,))
            row = cur.fetchone()
            if row:
                conn.execute('UPDATE team_members SET name=?, role=?, status=?, last_active=CURRENT_TIMESTAMP WHERE email=?', (name, role, status, email))
            else:
                mid = str(uuid.uuid4())
                conn.execute('INSERT INTO team_members (id, name, role, email, status) VALUES (?, ?, ?, ?, ?)', (mid, name, role, email, status))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro save_team_member: {e}")
        finally:
            conn.close()

    def get_team_members(self) -> List[Dict]:
        """Retorna membros da equipe cacheados"""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            return [dict(r) for r in conn.execute('SELECT * FROM team_members').fetchall()]
        finally:
            conn.close()

        """Atualiza metadados do projeto (Obra, Pavimento, Níveis, Cliente)"""
        conn = self._get_conn()
        try:
            conn.execute('''
                UPDATE projects 
                SET work_name=?, pavement_name=?, level_arrival=?, level_exit=?, client_id=?, updated_at=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (metadata.get('work_name'), metadata.get('pavement_name'), 
                  metadata.get('level_arrival'), metadata.get('level_exit'), 
                  metadata.get('client_id'), pid))
            conn.commit()
        except Exception as e:
            logging.error(f"Failed to update metadata for {pid}: {e}")
        finally:
            conn.close() 

    def _get_conn(self):
        return sqlite3.connect(self.db_path)

    def create_project(self, name: str, dxf_path: str = "", author_name: str = "Local", force_id: str = None, 
                       work_name: str = None, pavement_name: str = None, description: str = None, 
                       client_id: str = None, level_arrival: str = None, level_exit: str = None, **kwargs) -> str:
        """Cria novo projeto e retorna ID, aceitando metadados adicionais."""
        import uuid
        project_id = force_id if force_id else str(uuid.uuid4())
        conn = self._get_conn()
        try:
            # Colunas básicas
            cols = ['id', 'name', 'dxf_path', 'author_name', 'sync_status']
            vals = [project_id, name, dxf_path, author_name, 'pending']
            
            # Adicionar campos opcionais se fornecidos
            if work_name:
                cols.append('work_name')
                vals.append(work_name)
            if pavement_name:
                cols.append('pavement_name')
                vals.append(pavement_name)
            if description:
                cols.append('description')
                vals.append(description)
            if client_id:
                cols.append('client_id')
                vals.append(client_id)
            if level_arrival:
                cols.append('level_arrival')
                vals.append(level_arrival)
            if level_exit:
                cols.append('level_exit')
                vals.append(level_exit)

            # Manter compatibilidade com kwargs extras
            allowed = {
                'deadline'
            }
            for k, v in kwargs.items():
                if k in allowed:
                    cols.append(k)
                    vals.append(v)
            
            placeholders = ', '.join(['?'] * len(cols))
            query = f"INSERT INTO projects ({', '.join(cols)}) VALUES ({placeholders})"
            
            conn.execute(query, tuple(vals))
            conn.commit()
            return project_id
        except Exception as e:
            logging.error(f"Erro criar projeto: {e}")
            return None
        finally:
            conn.close()

    def get_projects(self) -> List[Dict]:
        """Lista projetos recentes com estatísticas de itens e nome do cliente."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            sql = """
            SELECT p.*, c.name as client_name,
                (SELECT COUNT(*) FROM pillars WHERE project_id = p.id) as pil_total,
                (SELECT COUNT(*) FROM pillars WHERE project_id = p.id AND is_validated=1) as pil_valid,
                (SELECT COUNT(*) FROM pillars WHERE project_id = p.id AND (is_validated=1 OR (validated_fields_json IS NOT NULL AND length(validated_fields_json) > 2))) as pil_started,
                
                (SELECT COUNT(*) FROM beams WHERE project_id = p.id) as beam_total,
                (SELECT COUNT(*) FROM beams WHERE project_id = p.id AND is_validated=1) as beam_valid,
                (SELECT COUNT(*) FROM beams WHERE project_id = p.id AND (is_validated=1 OR (validated_fields_json IS NOT NULL AND length(validated_fields_json) > 2))) as beam_started,

                (SELECT COUNT(*) FROM slabs WHERE project_id = p.id) as slab_total,
                (SELECT COUNT(*) FROM slabs WHERE project_id = p.id AND is_validated=1) as slab_valid,
                (SELECT COUNT(*) FROM slabs WHERE project_id = p.id AND (is_validated=1 OR (validated_fields_json IS NOT NULL AND length(validated_fields_json) > 2))) as slab_started
            FROM projects p 
            LEFT JOIN clients c ON p.client_id = c.id
            ORDER BY updated_at DESC
            """
            cursor = conn.execute(sql)
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_attachment_data(self, comm_id: str, filename: str) -> Optional[str]:
        """Recupera o base64 de um anexo específico de uma comunicação."""
        conn = self._get_conn()
        try:
            cursor = conn.execute('SELECT attachments_json FROM communication_history WHERE id = ?', (comm_id,))
            row = cursor.fetchone()
            if row and row[0]:
                atts = json.loads(row[0])
                for a in atts:
                    if isinstance(a, dict) and a.get('name') == filename:
                        return a.get('data')
            return None
        except Exception as e:
            logging.error(f"Erro ao recuperar dados do anexo: {e}")
            return None
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

    def save_work_document(self, work_name: str, name: str, file_path: str = None, extension: str = None, storage_path: str = None, phase: int = 1, category: str = "Geral"):
        """Salva um documento diretamente vinculado a uma Obra."""
        doc_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO project_documents (id, work_name, name, file_path, extension, storage_path, sync_status, phase, category)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, work_name, name, file_path, extension, storage_path, 'pending', phase, category))
            conn.commit()
            return doc_id
        finally:
            conn.close()

    def get_work_documents(self, work_name: str) -> List[Dict]:
        """Retorna documentos vinculados a uma Obra."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM project_documents WHERE work_name = ?', (work_name,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def get_project_documents(self, project_id: str) -> List[Dict]:
        """Retorna documentos vinculados a um Projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM project_documents WHERE project_id = ?', (project_id,))
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

    def get_project_by_dxf_path(self, dxf_path: str) -> Optional[Dict]:
        """Recupera um projeto pelo caminho do DXF."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM projects WHERE dxf_path = ?', (dxf_path,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def update_project_sync_status(self, project_id: str, status: str):
        """Atualiza estado de sincronização e timestamp de último sync."""
        conn = self._get_conn()
        try:
            # Se status for synced, atualiza last_sync_at
            if status == 'synced':
                 cur = conn.execute('UPDATE projects SET sync_status = ?, last_sync_at = CURRENT_TIMESTAMP WHERE id = ?', (status, project_id))
            else:
                 # Se for pending (ex: editado), apenas muda status
                 cur = conn.execute('UPDATE projects SET sync_status = ? WHERE id = ?', (status, project_id))
            
            if cur.rowcount == 0:
                logging.warning(f"⚠️ update_project_sync_status: Nenhuma linha afetada para ID {project_id} (Status: {status}). Verifique se o ID existe.")
            else:
                logging.info(f"✅ update_project_sync_status: {cur.rowcount} linhas atualizadas para ID {project_id}.")

            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao atualizar status de sync do projeto {project_id}: {e}")
        finally:
            conn.close()

    def export_project_data(self, project_id: str) -> Optional[Dict]:
        """Empacota todos os dados de um projeto para sincronização/backup."""
        project = self.get_project_by_id(project_id)
        if not project: return None
        
        return {
            "project": project,
            "pillars": self.load_pillars(project_id),
            "beams": self.load_beams(project_id),
            "slabs": self.load_slabs(project_id),
            "training": self.get_training_events(project_id),
            "documents": self.get_project_documents(project_id),
            "specifications": self.get_project_specifications(project_id),
            "work_documents": self.get_work_documents(project.get('work_name')) if project.get('work_name') else []
        }

    def import_project_data(self, data: Dict[str, Any]) -> str:
        """Importa um pacote de dados completo para o banco local (UPSERT)."""
        p_info = data.get('project')
        if not p_info: return None
        
        p_id = p_info['id']
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            # 1. Upsert Project
            cursor.execute('''
                INSERT INTO projects (id, name, dxf_path, work_name, pavement_name, level_arrival, level_exit, description, author_name, created_at, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    dxf_path=excluded.dxf_path,
                    work_name=excluded.work_name,
                    pavement_name=excluded.pavement_name,
                    description=excluded.description,
                    author_name=excluded.author_name,
                    sync_status='synced'
            ''', (
                p_id, p_info['name'], p_info.get('dxf_path'), p_info.get('work_name'),
                p_info.get('pavement_name'), p_info.get('level_arrival'), p_info.get('level_exit'),
                p_info.get('description'), p_info.get('author_name'), p_info.get('created_at'),
                'synced'
            ))
            conn.commit()
            
            # 2. Entidades
            for p in data.get('pillars', []): self.save_pillar(p, p_id)
            for b in data.get('beams', []): self.save_beam(b, p_id)
            for s in data.get('slabs', []): self.save_slab(s, p_id)
            
            # 3. Treinamento
            for t in data.get('training', []):
                self.log_training_event(
                    p_id, t.get('type'), t.get('role'), t.get('context_dna_json'),
                    t.get('target_value'), t.get('status')
                )
            
            # 4. Especificações
            if data.get('specifications'):
                self.update_project_specifications(p_id, data['specifications'])
                
            # 5. Documentos
            for d in data.get('documents', []):
                self._import_single_document(p_id, d)
            
            return p_id
        except Exception as e:
            logging.error(f"Erro no import_project_data: {e}")
            return None
        finally:
            conn.close()

    def _import_single_document(self, project_id: str, d: Dict):
        """Helper para upsert de documentos durante importação."""
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO project_documents (id, project_id, work_name, name, file_path, extension, storage_path, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    work_name=excluded.work_name,
                    storage_path=excluded.storage_path,
                    sync_status=excluded.sync_status
            ''', (
                str(d.get('id')) if d.get('id') else str(uuid.uuid4()), 
                project_id, d.get('work_name'),
                d.get('name'), d.get('file_path'), d.get('extension'), d.get('storage_path'), d.get('sync_status', 'synced')
            ))
            conn.commit()
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
            val_links_json = json.dumps(p.get('validated_link_classes', {}))
            na_fields_json = json.dumps(p.get('na_fields', []))
            na_links_json = json.dumps(p.get('na_link_classes', {}))
            na_reasons_json = json.dumps(p.get('na_reasons', {}))
            issues_json = json.dumps(p.get('issues', []))
            
            p_id = str(p.get('id', ''))
            
            cursor.execute('''
                INSERT INTO pillars (
                    id, project_id, name, type, area, points_json, sides_data_json, 
                    links_json, conf_map_json, validated_fields_json, validated_link_classes_json,
                    na_fields_json, na_link_classes_json, na_reasons_json,
                    issues_json, id_item, is_validated, pkl_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    type=excluded.type,
                    area=excluded.area,
                    sides_data_json=excluded.sides_data_json,
                    links_json=excluded.links_json,
                    conf_map_json=excluded.conf_map_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    issues_json=excluded.issues_json,
                    id_item=excluded.id_item,
                    is_validated=excluded.is_validated,
                    pkl_path=excluded.pkl_path
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
                val_links_json,
                na_fields_json,
                na_links_json,
                na_reasons_json,
                issues_json,
                p.get('id_item'),
                1 if p.get('is_validated') else 0,
                p.get('pkl_path')
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
                p['points'] = json.loads(p.get('points_json') or '[]')
                p['sides_data'] = json.loads(p.get('sides_data_json') or '{}')
                p['links'] = json.loads(p.get('links_json') or '{}')
                p['confidence_map'] = json.loads(p.get('conf_map_json') or '{}')
                p['validated_fields'] = json.loads(p.get('validated_fields_json') or '[]')
                p['validated_link_classes'] = json.loads(p.get('validated_link_classes_json') or '{}')
                p['na_fields'] = json.loads(p.get('na_fields_json') or '[]')
                p['na_link_classes'] = json.loads(p.get('na_link_classes_json') or '{}')
                p['na_reasons'] = json.loads(p.get('na_reasons_json') or '{}')
                p['issues'] = json.loads(p.get('issues_json') or '[]')
                p['id_item'] = p.get('id_item')
                p['is_validated'] = bool(p['is_validated'])
                p['pkl_path'] = p.get('pkl_path')
                pillars.append(p)
        except Exception as e:
            logging.error(f"Erro ao carregar pilares: {e}")
        finally:
            conn.close()
        return pillars

    def delete_pillar(self, pillar_id: str):
        """Exclui um pilar específico pelo ID."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM pillars WHERE id = ?", (pillar_id,))
            conn.commit()
        finally:
            conn.close()

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
                INSERT INTO slabs (
                    id, project_id, name, type, area, points_json, 
                    links_json, validated_fields_json, validated_link_classes_json,
                    na_fields_json, na_link_classes_json, na_reasons_json,
                    issues_json, id_item, is_validated, pkl_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    type=excluded.type,
                    area=excluded.area,
                    points_json=excluded.points_json,
                    links_json=excluded.links_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    issues_json=excluded.issues_json,
                    id_item=excluded.id_item,
                    is_validated=excluded.is_validated,
                    pkl_path=excluded.pkl_path
            ''', (
                s['id'], project_id, s.get('name'), 
                s.get('type', 'Laje'),
                float(s.get('area', 0.0)), 
                json.dumps(s.get('points', [])),
                json.dumps(s.get('links', {})),
                json.dumps(s.get('validated_fields', [])),
                json.dumps(s.get('validated_link_classes', {})),
                json.dumps(s.get('na_fields', [])),
                json.dumps(s.get('na_link_classes', {})),
                json.dumps(s.get('na_reasons', {})),
                json.dumps(s.get('issues', [])),
                s.get('id_item'),
                1 if s.get('is_validated') else 0,
                s.get('pkl_path')
            ))
            
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao salvar laje no DB: {e}")
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
                s['points'] = json.loads(s.get('points_json') or '[]')
                s['links'] = json.loads(s.get('links_json') or '{}')
                s['validated_fields'] = json.loads(s.get('validated_fields_json') or '[]')
                s['validated_link_classes'] = json.loads(s.get('validated_link_classes_json') or '{}')
                s['na_fields'] = json.loads(s.get('na_fields_json') or '[]')
                s['na_link_classes'] = json.loads(s.get('na_link_classes_json') or '{}')
                s['na_reasons'] = json.loads(s.get('na_reasons_json') or '{}')
                s['issues'] = json.loads(s.get('issues_json') or '[]')
                s['id_item'] = s.get('id_item')
                s['is_validated'] = bool(s.get('is_validated', 0))
                s['pkl_path'] = s.get('pkl_path')
                slabs.append(s)
        except Exception as e:
            logging.error(f"Erro ao carregar lajes: {e}")
        finally:
            conn.close()
        return slabs

    def delete_slab(self, slab_id: str):
        """Exclui uma laje específica pelo ID."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM slabs WHERE id = ?", (slab_id,))
            conn.commit()
        finally:
            conn.close()

    def save_beam(self, b: Dict[str, Any], project_id: str):
        """Salva uma viga vinculada ao projeto."""
        conn = self._get_conn()
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO beams (
                    id, project_id, name, data_json, 
                    validated_fields_json, validated_link_classes_json,
                    na_fields_json, na_link_classes_json, na_reasons_json,
                    id_item, is_validated, pkl_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    name=excluded.name,
                    data_json=excluded.data_json,
                    validated_fields_json=excluded.validated_fields_json,
                    validated_link_classes_json=excluded.validated_link_classes_json,
                    na_fields_json=excluded.na_fields_json,
                    na_link_classes_json=excluded.na_link_classes_json,
                    na_reasons_json=excluded.na_reasons_json,
                    id_item=excluded.id_item,
                    is_validated=excluded.is_validated,
                    pkl_path=excluded.pkl_path
            ''', (
                b['id'], project_id, b.get('name'), 
                json.dumps(b), 
                json.dumps(b.get('validated_fields', [])),
                json.dumps(b.get('validated_link_classes', {})),
                json.dumps(b.get('na_fields', [])),
                json.dumps(b.get('na_link_classes', {})),
                json.dumps(b.get('na_reasons', {})),
                b.get('id_item'), 
                1 if b.get('is_validated') else 0,
                b.get('pkl_path')
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
                # Sincronizar com colunas caso existam (Retrocompatibilidade)
                try:
                    b['is_validated'] = bool(row['is_validated'])
                except (IndexError, KeyError):
                    b['is_validated'] = b.get('is_validated', False)
                    
                try:
                    b['id_item'] = row['id_item']
                except (IndexError, KeyError):
                    b['id_item'] = b.get('id_item')
                
                try:
                    b['pkl_path'] = row['pkl_path']
                except (IndexError, KeyError):
                    b['pkl_path'] = b.get('pkl_path')

                # Carregar campos de validação/NA das colunas dedicadas
                for col, key in [('validated_fields_json', 'validated_fields'),
                                 ('validated_link_classes_json', 'validated_link_classes'),
                                 ('na_fields_json', 'na_fields'),
                                 ('na_link_classes_json', 'na_link_classes'),
                                 ('na_reasons_json', 'na_reasons')]:
                    try:
                        if row[col]: b[key] = json.loads(row[col])
                    except (IndexError, KeyError, TypeError):
                        pass
                
                beams.append(b)
        except Exception as e:
            logging.error(f"Erro ao carregar vigas: {e}")
        finally:
            conn.close()
        return beams

    def delete_beam(self, beam_id: str):
        """Exclui uma viga específica pelo ID."""
        conn = self._get_conn()
        try:
            conn.execute("DELETE FROM beams WHERE id = ?", (beam_id,))
            conn.commit()
        finally:
            conn.close()
    def save_pre_processing(self, project_id: str, data: Dict):
        """Salva dados de tratamento prévio (Marco)."""
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO pre_processing (project_id, data_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id) DO UPDATE SET
                    data_json=excluded.data_json,
                    updated_at=excluded.updated_at
            ''', (project_id, json.dumps(data)))
            conn.commit()
        finally:
            conn.close()

    def load_pre_processing(self, project_id: str) -> Optional[Dict]:
        """Carrega dados de tratamento prévio."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute('SELECT data_json FROM pre_processing WHERE project_id = ?', (project_id,))
            row = cursor.fetchone()
            return json.loads(row['data_json']) if row else None
        finally:
            conn.close()


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
        """Duplica um projeto existente, regenerando IDs de entidades para evitar mixing."""
        data = self.export_project_data(source_pid)
        if not data: return None
        
        import uuid
        new_project_id = str(uuid.uuid4())
        
        # 1. Trocar ID do Projeto e Nome
        data['project']['id'] = new_project_id
        data['project']['name'] = f"{data['project']['name']} (Cópia)"
        if target_work_name is not None:
             data['project']['work_name'] = target_work_name
             
        # 2. Regenerar IDs de TODAS as Entidades (Pilares, Vigas, Lajes)
        # Isso evita que o ON CONFLICT(id) do import 'roube' os itens do projeto original
        for p in data.get('pillars', []):
            p['id'] = str(uuid.uuid4())
            p['project_id'] = new_project_id
            
        for s in data.get('slabs', []):
            s['id'] = str(uuid.uuid4())
            s['project_id'] = new_project_id
            
        for b in data.get('beams', []):
            b['id'] = str(uuid.uuid4())
            b['project_id'] = new_project_id

        # 3. Regenerar IDs de Treinamento
        for e in data.get('training', []):
            e['id'] = str(uuid.uuid4())
            e['project_id'] = new_project_id
            
        # 4. Importar como novo projeto
        return self.import_project_data(data)

    def log_training_event(self, project_id: str, event_type: str, role: str, dna_json: str, target_val: str, status: str):
        """Registra um evento de aprendizado Hierárquico."""
        conn = self._get_conn()
        try:
            evt_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO training_events (id, project_id, type, role, context_dna_json, target_value, status, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (evt_id, project_id, event_type, role, dna_json, target_val, status, datetime.now().isoformat()))
            conn.commit()
        except Exception as e:
            logging.error(f"Erro ao logar training_event: {e}")
        finally:
            conn.close()

    def delete_training_event_by_target(self, project_id: str, role: str, target_val: str):
        """Remove um evento de treinamento específico (Undo)."""
        conn = self._get_conn()
        try:
            conn.execute('''
                DELETE FROM training_events 
                WHERE project_id = ? AND role = ? AND target_value = ?
            ''', (project_id, role, target_val))
            conn.commit()
            logging.info(f"🗑️ Evento de treino removido via Undo: {role} -> {target_val}")
        except Exception as e:
            logging.error(f"Erro ao remover evento de treino (Undo): {e}")
        finally:
            conn.close()

    def get_training_events(self, project_id: str) -> List[Dict]:
        """Retorna todos os eventos de treino (valid e fail) para o projeto."""
        conn = self._get_conn()
        try:
            # Join with projects to get work name if needed, but here we focus on raw events
            cursor = conn.execute('''
                SELECT id, type, role, target_value, status, timestamp, context_dna_json 
                FROM training_events 
                WHERE project_id = ? 
                ORDER BY timestamp DESC
            ''', (project_id,))
            
            columns = [c[0] for c in cursor.description]
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            return results
        finally:
            conn.close()

    def delete_training_event(self, event_id: str):
        """Remove um evento de treino específico (Correção de Erro Humano)."""
        conn = self._get_conn()
        try:
            conn.execute('DELETE FROM training_events WHERE id = ?', (event_id,))
            conn.commit()
            logging.info(f"🗑️ Evento de treino {event_id} removido.")
        finally:
            conn.close()
    # --- ADMIN STATS ---
    
    def get_admin_stats(self) -> Dict[str, Any]:
        """Retorna estatísticas detalhadas para o dashboard admin e pipeline de dados (8 Fases)."""
        conn = self._get_conn()
        try:
            stats = {}
            # Base stats
            stats['total_works'] = conn.execute("SELECT COUNT(*) FROM works").fetchone()[0]
            stats['total_projects'] = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]
            
            # Phase 1: Ingestão
            stats['ingestion'] = {
                'works': stats['total_works'],
                'documents': conn.execute("SELECT COUNT(*) FROM project_documents WHERE phase = 1").fetchone()[0],
                'details': {
                    'Obras': stats['total_works'],
                    'Pavimentos': stats['total_projects'],
                    'Documentos Brutos': conn.execute("SELECT COUNT(*) FROM project_documents WHERE category LIKE '%Estrutural%'").fetchone()[0]
                }
            }
            
            # Phase 2: Triagem
            stats['triage'] = {
                'processed': conn.execute("SELECT COUNT(*) FROM project_documents WHERE phase = 2").fetchone()[0],
                'details': {
                    'Estruturais Limpos': conn.execute("SELECT COUNT(*) FROM project_documents WHERE category LIKE '%Limpos%'").fetchone()[0],
                    'Arquivos Classificados': conn.execute("SELECT COUNT(*) FROM project_documents WHERE category IN ('PILARES', 'VIGAS', 'LAJES')").fetchone()[0]
                }
            }
            
            # Phase 3: Extração/Detecção
            p_count = conn.execute("SELECT COUNT(*) FROM pillars").fetchone()[0]
            b_count = conn.execute("SELECT COUNT(*) FROM beams").fetchone()[0]
            s_count = conn.execute("SELECT COUNT(*) FROM slabs").fetchone()[0]
            stats['detection'] = {
                'total_items': p_count + b_count + s_count,
                'details': {
                    'Pilares Detectados': p_count,
                    'Vigas Detectadas': b_count,
                    'Lajes Detectadas': s_count
                }
            }
            
            # Phase 4: Reconhecimento (Johnson Robôs)
            # Nota: Vigas sofrem cisão lógica em Laterais e Fundo
            stats['recognition'] = {
                'total_johnson': p_count + (b_count * 2) + s_count,
                'details': {
                    'JSON Pilares': p_count,
                    'JSON Lajes': s_count,
                    'JSON Vigas (Laterais)': b_count,
                    'JSON Vigas (Fundo)': b_count
                }
            }
            
            # Phase 5: Robot Feed (Scripts .SCR)
            stats['robot_feed'] = {
                'total_scripts': conn.execute("SELECT COUNT(*) FROM generated_scripts").fetchone()[0],
                'details': {
                    'Scripts Pilares': conn.execute("SELECT COUNT(*) FROM generated_scripts WHERE item_type='pilar'").fetchone()[0],
                    'Scripts Lajes': conn.execute("SELECT COUNT(*) FROM generated_scripts WHERE item_type='laje'").fetchone()[0],
                    'Scripts Vigas (Laterais)': conn.execute("SELECT COUNT(*) FROM generated_scripts WHERE item_type='viga_lateral'").fetchone()[0],
                    'Scripts Vigas (Fundo)': conn.execute("SELECT COUNT(*) FROM generated_scripts WHERE item_type='viga_fundo'").fetchone()[0]
                }
            }
            
            # Phase 6: Conversão (SCR -> DXF) - Placeholder
            stats['conversion'] = {
                'total_dxf': 0,
                'details': {
                    'Estilo INI': 0,
                    'Estilo NOVA': 0,
                    'DXF Pilares': 0,
                    'DXF Vigas': 0,
                    'DXF Lajes': 0
                }
            }
            
            # Phase 7: Unificação DXF - Placeholder
            stats['unification'] = {
                'total_unified': 0,
                'details': {
                    'Pavimentos Completos': 0,
                    'Unificações Populadas': 0
                }
            }
            
            # Phase 8: Validação/Entrega - Placeholder
            stats['delivery'] = {
                'total_reviewed': 0,
                'details': {
                    'Projetos Revisados': 0,
                    'Correções Finais': 0
                }
            }

            # Original Validation Stats (can be used elsewhere or combined)
            p_valid = conn.execute("SELECT COUNT(*) FROM pillars WHERE is_validated=1").fetchone()[0]
            b_valid = conn.execute("SELECT COUNT(*) FROM beams WHERE is_validated=1").fetchone()[0]
            s_valid = conn.execute("SELECT COUNT(*) FROM slabs WHERE is_validated=1").fetchone()[0]
            stats['validation_legacy'] = {
                'total_validated': p_valid + b_valid + s_valid,
                'details': {
                    'Pilares Auditados': p_valid,
                    'Vigas Auditadas': b_valid,
                    'Lajes Auditadas': s_valid
                }
            }

            return stats
        except Exception as e:
            logging.error(f"Erro ao buscar admin stats: {e}")
            return {}
        finally:
            conn.close()

    def get_accuracy_report(self) -> List[Dict]:
        """Gera relatório de precisão baseado em eventos de treino."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            sql = """
                SELECT role, status, COUNT(*) as count 
                FROM training_events 
                GROUP BY role, status
            """
            cursor = conn.execute(sql)
            return [dict(r) for r in cursor.fetchall()]
        except Exception as e:
            logging.error(f"Erro ao buscar accuracy report: {e}")
            return []
        finally:
            conn.close()

    # --- DOCUMENT AND SPECIFICATION MANAGEMENT ---

    def save_document(self, project_id: str, name: str, file_path: str, extension: str, phase: int = None, category: str = None, storage_path: str = None, file_data: str = None) -> str:
        """Salva um novo documento vinculado ao projeto."""
        doc_id = str(uuid.uuid4())
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO project_documents (id, project_id, name, file_path, extension, phase, category, storage_path, file_data, sync_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (doc_id, project_id, name, file_path, extension, phase, category, storage_path, file_data, 'pending'))
            conn.commit()
            logging.info(f"📄 Documento salvo: {name} ({extension}) na fase {phase}/{category} para projeto {project_id}")
            return doc_id
        except Exception as e:
            logging.error(f"Erro ao salvar documento: {e}")
            return None
        finally:
            conn.close()

    def get_project_documents(self, project_id: str) -> List[Dict]:
        """Retorna todos os documentos vinculados a um projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT * FROM project_documents WHERE project_id = ? ORDER BY created_at DESC', (project_id,))
            return [dict(r) for r in cursor.fetchall()]
        finally:
            conn.close()

    def update_document_sync(self, doc_id: str, storage_path: str, sync_status: str = 'synced'):
        """Atualiza o caminho remoto e o status de sincronização de um documento."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE project_documents SET storage_path = ?, sync_status = ? WHERE id = ?', 
                         (storage_path, sync_status, doc_id))
            conn.commit()
        finally:
            conn.close()

    def delete_document(self, doc_id: str):
        """Remove um documento do banco de dados."""
        conn = self._get_conn()
        try:
            conn.execute('DELETE FROM project_documents WHERE id = ?', (doc_id,))
            conn.commit()
            logging.info(f"🗑️ Documento {doc_id} removido do banco.")
        finally:
            conn.close()

    def update_project_specifications(self, project_id: str, spec_data: Dict):
        """Atualiza as especificações técnicas do projeto (UPSERT)."""
        conn = self._get_conn()
        try:
            conn.execute('''
                INSERT INTO project_specifications (project_id, content_json, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id) DO UPDATE SET
                    content_json=excluded.content_json,
                    updated_at=excluded.updated_at
            ''', (project_id, json.dumps(spec_data)))
            conn.commit()
            logging.info(f"⚙️ Especificações atualizadas para projeto {project_id}")
        except Exception as e:
            logging.error(f"Erro ao atualizar especificações: {e}")
        finally:
            conn.close()

    def get_project_specifications(self, project_id: str) -> Dict:
        """Recupera as especificações técnicas do projeto."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute('SELECT content_json FROM project_specifications WHERE project_id = ?', (project_id,))
            row = cursor.fetchone()
            return json.loads(row['content_json']) if row else {}
        except Exception as e:
            logging.error(f"Erro ao recuperar especificações: {e}")
            return {}
        finally:
            conn.close()

    def update_project_description(self, project_id: str, description: str):
        """Atualiza a descrição textual do projeto."""
        conn = self._get_conn()
        try:
            conn.execute('UPDATE projects SET description = ? WHERE id = ?', (description, project_id))
            conn.commit()
        finally:
            conn.close()

    def update_project_metadata(self, project_id: str, meta_dict: Dict[str, Any]):
        """Atualiza dinamicamente metadados de um projeto."""
        if not meta_dict: return
        
        conn = self._get_conn()
        try:
            # Filtrar apenas chaves que existem no schema (segurança básica)
            # Colunas permitidas para update dinâmico via este método
            allowed_cols = {
                'name', 'dxf_path', 'work_name', 'pavement_name', 
                'level_arrival', 'level_exit', 'client_id', 'description', 
                'deadline', 'author_name', 'sync_status'
            }
            
            updates = []
            values = []
            for k, v in meta_dict.items():
                if k in allowed_cols:
                    updates.append(f"{k} = ?")
                    values.append(v)
            
            if not updates: return
            
            values.append(project_id)
            query = f"UPDATE projects SET {', '.join(updates)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
            
            conn.execute(query, tuple(values))
            conn.commit()
            logging.info(f"Metadados do projeto {project_id} atualizados.")
        except Exception as e:
            logging.error(f"Erro ao atualizar metadados do projeto: {e}")
        finally:
            conn.close()

    def rotate_project_id(self, old_id: str, new_id: str) -> bool:
        """
        Migra um projeto e todos os seus itens para um novo ID.
        Útil para resolver conflitos de propriedade (Fork).
        """
        conn = self._get_conn()
        try:
            conn.execute("BEGIN TRANSACTION")
            
            # 1. Update Projects table
            conn.execute("UPDATE projects SET id = ?, sync_status='pending', last_sync_at=NULL WHERE id = ?", (new_id, old_id))
            
            # 2. Update dependencies
            tables = ['pillars', 'beams', 'slabs', 'project_documents', 'training_events']
            for table in tables:
                conn.execute(f"UPDATE {table} SET project_id = ? WHERE project_id = ?", (new_id, old_id))
                
            conn.commit()
            logging.info(f"✅ Project migrated from {old_id} to {new_id} to resolve conflicts.")
            return True
        except Exception as e:
            conn.rollback()
            logging.error(f"Failed to rotate project ID: {e}")
            return False
        finally:
            conn.close()

    def update_work_metadata(self, name: str, data: Dict[str, Any]):
        """Atualiza metadados técnicos de uma Obra."""
        conn = self._get_conn()
        try:
            allowed = {'num_pavements', 'num_towers', 'total_pilares', 'total_vigas', 'total_lajes', 'technical_specs', 'client_id', 'last_sync_at'}
            updates = []
            values = []
            for k, v in data.items():
                if k in allowed:
                    updates.append(f"{k} = ?")
                    values.append(v)
            if not updates: return
            values.append(name)
            conn.execute(f"UPDATE works SET {', '.join(updates)} WHERE name = ?", tuple(values))
            conn.commit()
        finally:
            conn.close()

    def get_work_data(self, name: str) -> Optional[Dict]:
        """Retorna todos os dados de uma Obra."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute("SELECT * FROM works WHERE name = ?", (name,))
            row = cur.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def save_generated_script(self, project_id, pavement_name, item_id, item_type, script_path):
        """Salva ou atualiza a informação de um script gerado para um item específico."""
        conn = self._get_conn()
        try:
            script_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO generated_scripts (id, project_id, pavement_name, item_id, item_type, script_path, generated_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(project_id, pavement_name, item_id, item_type) 
                DO UPDATE SET 
                    script_path = excluded.script_path,
                    generated_at = CURRENT_TIMESTAMP
            ''', (script_id, project_id, pavement_name, item_id, item_type, script_path))
            conn.commit()
            return True
        except Exception as e:
            logging.error(f"Erro ao salvar script gerado {item_type}/{item_id}: {e}")
            return False
        finally:
            conn.close()

    def get_generated_scripts(self, project_id, pavement_name):
        """Busca todos os scripts gerados para um determinado pavimento."""
        conn = self._get_conn()
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.execute('''
                SELECT * FROM generated_scripts 
                WHERE project_id = ? AND pavement_name = ?
            ''', (project_id, pavement_name))
            return [dict(row) for row in cur.fetchall()]
        finally:
            conn.close()

    def get_script_generation_stats(self, project_id, pavement_name):
        """Retorna estatísticas de geração de scripts para o progresso."""
        conn = self._get_conn()
        try:
            # 1. Contar itens totais (Pilares + Vigas + Lajes)
            # Nota: Isso assume que os itens estão carregados no DB para este projeto
            total_items = 0
            
            # Pilares: 3 scripts (Cima, Grades, ABCD)
            cur = conn.execute("SELECT COUNT(*) FROM pillars WHERE project_id = ?", (project_id,))
            num_pillars = cur.fetchone()[0]
            total_items += (num_pillars * 3)
            
            # Vigas: 2 scripts (Lateral, Fundo)
            cur = conn.execute("SELECT COUNT(*) FROM beams WHERE project_id = ?", (project_id,))
            num_beams = cur.fetchone()[0]
            total_items += (num_beams * 2)

            # Lajes: 1 script
            cur = conn.execute("SELECT COUNT(*) FROM slabs WHERE project_id = ?", (project_id,))
            num_slabs = cur.fetchone()[0]
            total_items += num_slabs
            
            # 2. Contar scripts gerados
            cur = conn.execute('''
                SELECT COUNT(*) FROM generated_scripts 
                WHERE project_id = ? AND pavement_name = ?
            ''', (project_id, pavement_name))
            generated_count = cur.fetchone()[0]
            
            return {
                "total": total_items,
                "generated": generated_count,
                "percentage": (generated_count / total_items * 100) if total_items > 0 else 0
            }
        except Exception as e:
            logging.error(f"Erro ao obter estatísticas de scripts: {e}")
            return {"total": 0, "generated": 0, "percentage": 0}
        finally:
            conn.close()
