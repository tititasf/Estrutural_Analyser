import base64

# Helper de ofuscação corrigido
def _get_obf_str(key):
    """Retorna string ofuscada (Versão Corrigida)"""
    try:
        _obf_map = {
            "script.google.com": base64.b64decode("=02bj5SZsd2bvdmL0BXayN2c"[::-1].encode()).decode(),
            "macros/s/": base64.b64decode("vM3Lz9mcjFWb"[::-1].encode()).decode(),
            "AKfycbz": base64.b64decode("==geiNWemtUQ"[::-1].encode()).decode(),
            "credit": base64.b64decode("0lGZlJ3Y"[::-1].encode()).decode(),
            "saldo": base64.b64decode("=8GZsF2c"[::-1].encode()).decode(),
            "consumo": base64.b64decode("==wbtV3cu92Y"[::-1].encode()).decode(),
            "api_key": base64.b64decode("==Qelt2XpBXY"[::-1].encode()).decode(),
            "user_id": base64.b64decode("==AZp9lclNXd"[::-1].encode()).decode(),
            "calcular_creditos": base64.b64decode("=M3b0lGZlJ3YfJXYsV3YsF2Y"[::-1].encode()).decode(),
            "confirmar_consumo": base64.b64decode("=8Wb1NnbvN2XyFWbylmZu92Y"[::-1].encode()).decode(),
            "consultar_saldo": base64.b64decode("vRGbhN3XyFGdsV3cu92Y"[::-1].encode()).decode(),
            "debitar_creditos": base64.b64decode("==wcvRXakVmcj9lchRXaiVGZ"[::-1].encode()).decode(),
            "CreditManager": base64.b64decode("==gcldWYuFWT0lGZlJ3Q"[::-1].encode()).decode(),
            "obter_hwid": base64.b64decode("==AZpdHafJXZ0J2b"[::-1].encode()).decode(),
            "generate_signature": base64.b64decode("lJXd0Fmbnl2cfVGdhJXZuV2Z"[::-1].encode()).decode(),
            "encrypt_string": base64.b64decode("=cmbpJHdz9Fdwlncj5WZ"[::-1].encode()).decode(),
            "decrypt_string": base64.b64decode("=cmbpJHdz9FdwlncjVGZ"[::-1].encode()).decode(),
            "integrity_check": base64.b64decode("rNWZoN2X5RXaydWZ05Wa"[::-1].encode()).decode(),
            "security_utils": base64.b64decode("=MHbpRXdflHdpJXdjV2c"[::-1].encode()).decode(),
            "https://": base64.b64decode("=8yL6MHc0RHa"[::-1].encode()).decode(),
            "google.com": base64.b64decode("==QbvNmLlx2Zv92Z"[::-1].encode()).decode(),
            "apps.script": base64.b64decode("=QHcpJ3Yz5ycwBXY"[::-1].encode()).decode(),
        }
        return _obf_map.get(key, key)
    except Exception:
        return key


import os
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, Any, Optional
from src.core.infra.supabase_client import SupabaseClient
from src.core.auth.models import AuthSession
from src.core.database import DatabaseManager
from src.core.services.storage_service import StorageService

class SyncService:
    """
    Serviço responsável pela sincronização de projetos e dados de treino com a nuvem.
    Focado em backup individual e isolamento para curadoria do admin.
    """
    
    PROJECTS_BUCKET = "user_projects"
    
    def __init__(self):
        self.supabase = SupabaseClient.get_instance().client
        self.storage = StorageService()
        self.logger = logging.getLogger(__name__)

    def sync_project(self, project_data: Dict[str, Any], user_session: AuthSession) -> bool:
        """
        Faz o backup do projeto (.cadproj) para o Supabase Storage.
        Registra metadados na tabela public.cloud_projects para listagem do admin.
        """
        if not user_session or not user_session.user:
            self.logger.error("Sincronização falhou: Usuário não autenticado.")
            return False

        user_id = user_session.user.id
        project_name = project_data.get('project', {}).get('name', 'Projeto_Sem_Nome')
        project_id = project_data.get('project', {}).get('id')
        work_name = project_data.get('project', {}).get('work_name') or "Sem Obra"
        self.logger.info(f"[DEBUG] Syncing Project: {project_name}, Work Name: {work_name}")
        
        # 0. Deduplicação: Verificar se já existe projeto com mesmo Nome + Obra deste usuário
        try:
            # Buscar projetos do usuário com mesmo nome
            # Note: Como não temos work_name na tabela raiz, vamos filtrar localmente ou confiar no nome
            # O ideal seria ter work_name na tabela cloud_projects. 
            # Vou confiar que o usuário quer unicidade por Nome+Obra.
            # Workaround: Usar metadata->work_name filter é difícil sem índice.
            # Vou buscar todos os projetos deste usuário com este nome.
            res = self.supabase.table("cloud_projects").select("id, metadata").eq(_get_obf_str("user_id"), user_id).eq("project_name", project_name).execute()
            
            existing_projects = res.data
            for p in existing_projects:
                meta = p.get('metadata', {})
                remote_work = meta.get('work_name', 'Sem Obra')
                
                # Se for a mesma Obra e ID diferente, é uma duplicata (ex: re-criado localmente)
                if remote_work == work_name and p['id'] != project_id:
                    self.logger.info(f"Removendo duplicata antiga na nuvem: {p['id']} ({project_name} - {work_name})")
                    try:
                        # Remove files first? Or generic delete cascades?
                        # Storage clean up is hard without listing.
                        # Assuming 'cloud_projects' delete triggers or we just leave orphan files for now.
                        self.supabase.table("cloud_projects").delete().eq("id", p['id']).execute()
                        
                        # Tentar limpar arquivo antigo se caminho for dedutivel ou salvo
                        # O path antigo provavelmente era {user_id}/{p['id']}_{project_name}.cadproj
                        old_path = _get_obf_str("user_id")
                        self.supabase.storage.from_(self.PROJECTS_BUCKET).remove([old_path])
                    except Exception as ex_del:
                        self.logger.warning(f"Erro limpando duplicata: {ex_del}")
                        
        except Exception as e_check:
             self.logger.warning(f"Erro checando duplicatas: {e_check}")

        project_info = project_data.get('project', {})
        project_id = project_info.get('id')
        project_name = project_info.get('name', 'Sem Nome')
        work_name = project_info.get('work_name') or "Sem Obra"
        dxf_path = project_info.get('dxf_path', '')

        # 1. Upload Documents to Storage first
        db = DatabaseManager()
        all_docs_to_sync = project_data.get('documents', []) + project_data.get('work_documents', [])
        
        for doc in all_docs_to_sync:
            # Se já tem storage_path e não é pendente, pula (otimização)
            if doc.get('storage_path') and doc.get('sync_status') == 'synced':
                continue
                
            local_path = doc.get('file_path')
            if local_path and os.path.exists(local_path):
                file_name = doc.get('name')
                # Path: {user_id}/docs/{doc_id}_{name}
                doc_remote_path = f"{user_id}/docs/{doc['id']}_{file_name}"
                
                self.logger.info(f"Subindo documento para Storage: {file_name}")
                stored_path = self.storage.upload_file(self.storage.BUCKETS["DOCS"], doc_remote_path, local_path)
                
                if stored_path:
                    doc['storage_path'] = stored_path
                    doc['sync_status'] = 'synced'
                    # Atualiza no banco local para não subir de novo na próxima
                    db.update_document_sync(doc['id'], stored_path)
        
        # 2. Preparar arquivo JSON (Agora com storage_paths nos docs)
        try:
            content = json.dumps(project_data, indent=2, ensure_ascii=False).encode('utf-8')
            json_remote_path = f"{user_id}/projects/{project_id}_{project_name}.cadproj"
            
            # 3. Upload Projeto para Storage
            self.storage.upload_content(
                self.storage.BUCKETS["PROJECTS"], 
                json_remote_path, 
                content, 
                content_type="application/json"
            )
            
            # 2.5 Calculate Stats for Metadata (Rich Preview)
            pillars = project_data.get('pillars', [])
            beams = project_data.get('beams', [])
            slabs = project_data.get('slabs', [])
            all_items = pillars + beams + slabs
            
            # --- NEW STATISTICS CALCULATION (Alignment with AdminDashboard) ---
            total_items = len(all_items)
            started_items = 0
            finished_items = 0
            total_links_expected = 0
            total_links_validated = 0
            
            for item in all_items:
                # Heuristic Type Detection
                itype = 'pillar'
                if 'points' in item and 'section' not in item: itype = 'slab'
                elif 'section' not in item: itype = 'beam'
                
                # Estimated Expected Fields
                expected = 10 
                if itype == 'pillar': expected = 12
                elif itype == 'slab': expected = 6
                elif itype == 'beam': expected = 15
                
                total_links_expected += expected
                
                # Count validated + NA fields
                v_fields = item.get('validated_fields') or {}
                if isinstance(v_fields, list): v_fields = {}
                
                na_fields = item.get('na_fields') or {}
                if isinstance(na_fields, list): na_fields = {}
                
                # Unique valid/NA keys
                done_keys = set(v_fields.keys()) | set(na_fields.keys())
                count_done = len(done_keys)
                
                total_links_validated += count_done
                
                # Determine Status
                is_explicit_finish = item.get('is_fully_validated', False)
                is_legacy_valid = item.get('is_validated', False)
                
                if is_explicit_finish or is_legacy_valid or count_done >= expected:
                    finished_items += 1
                     # FIX: Legacy items might lack fields but be validated. Force link count to 100%
                    if count_done < expected:
                         total_links_validated += (expected - count_done) if (expected - count_done) > 0 else 0
                         
                # Inclusive Started: If it has progress OR is finished, it counts as Started
                if count_done > 0 or is_explicit_finish or is_legacy_valid:
                    started_items += 1
            
            # --- 2.6 Document Stats (Global + Project documents) ---
            # Classes unificadas conforme pedido: ESTRUTURAL, DETALHE, PILAR, VIGA, LAJE, FUNDO
            doc_stats = {
                "ESTRUTURAL": 0, 
                "DETALHES E VISÕES DE CORTES": 0, 
                "PILARES": 0,
                "LATERAIS DE VIGAS": 0, 
                "FUNDOS DE VIGA": 0, 
                "LAJES": 0
            }
            
            # 1. Main DXF is always ESTRUTURAL
            if dxf_path: 
                doc_stats["ESTRUTURAL"] += 1
            
            # 2. Project Documents (Current Pavilion)
            docs = project_data.get('documents', [])
            for d in docs:
                nm = d.get('name', '').upper()
                if "ESTRUTURAL" in nm or ".DXF" in nm: doc_stats["ESTRUTURAL"] += 1
                elif "DETALHE" in nm or "CORTE" in nm: doc_stats["DETALHES E VISÕES DE CORTES"] += 1
                elif "PILAR" in nm: doc_stats["PILARES"] += 1
                elif "LATERAL" in nm or "LATERAIS" in nm or ("VIGA" in nm and "FUNDO" not in nm): 
                    doc_stats["LATERAIS DE VIGAS"] += 1
                elif "FUNDO" in nm: doc_stats["FUNDOS DE VIGA"] += 1
                elif "LAJE" in nm: doc_stats["LAJES"] += 1

            # 3. Work Documents (Level Obra)
            # Buscamos no banco local se há documentos vinculados apenas à obra selecionada
            db = DatabaseManager()
            work_docs = db.get_work_documents(work_name)
            for wd in work_docs:
                nm = wd.get('name', '').upper()
                if "ESTRUTURAL" in nm: doc_stats["ESTRUTURAL"] += 1
                elif "DETALHE" in nm or "CORTE" in nm: doc_stats["DETALHES E VISÕES DE CORTES"] += 1
                elif "PILAR" in nm: doc_stats["PILARES"] += 1
                elif "LATERAL" in nm or "LATERAIS" in nm or ("VIGA" in nm and "FUNDO" not in nm): 
                    doc_stats["LATERAIS DE VIGAS"] += 1
                elif "FUNDO" in nm: doc_stats["FUNDOS DE VIGA"] += 1
                elif "LAJE" in nm: doc_stats["LAJES"] += 1

            # 3. Registrar na tabela de metadados para o Admin ver
            work_meta = db.get_work_data(work_name) or {}
            
            metadata = {
                "num_pillars": len(pillars),
                "num_beams": len(beams),
                "num_slabs": len(slabs),
                "user_email": user_session.user.email,
                "author_name": project_info.get('author_name', 'Local'),
                "work_name": work_name,
                "work_info": {
                    "pavements": work_meta.get('num_pavements'),
                    "towers": work_meta.get('num_towers'),
                    "total_pilares": work_meta.get('total_pilares'),
                    "total_vigas": work_meta.get('total_vigas'),
                    "total_lajes": work_meta.get('total_lajes'),
                    "specs": work_meta.get('technical_specs')
                },
                "dxf_path": dxf_path, # Store path for reference
                "last_sync": "now",
                # Enhanced Stats
                "stats": {
                    "total_items": total_items,
                    "started_items": started_items,
                    "finished_items": finished_items,
                    "total_links_expected": total_links_expected,
                    "total_links_validated": total_links_validated
                },
                "doc_stats": doc_stats
            }
            
            # DEBUG RLS:
            self.logger.info(f"--- DEBUG SYNC ---")
            self.logger.info(_get_obf_str("user_id"))
            current_sess = self.supabase.auth.get_session()
            tokens_match = current_sess and current_sess.access_token == user_session.access_token
            
            if not current_sess or not tokens_match:
                self.logger.info("Session token mismatch or missing. Refreshing Supabase Client session...")
                self.supabase.auth.set_session(user_session.access_token, user_session.refresh_token)
            
            # 4. Check existence for manual Upsert (Better RLS handling)
            try:
                # Select ID AND user_id to verify ownership
                exists_check = self.supabase.table("cloud_projects").select("id, user_id").eq("id", project_id).execute()
                exists = len(exists_check.data) > 0
                
                payload = {
                     "project_name": project_name,
                     "storage_path": json_remote_path,
                     "metadata": metadata, # Contains work_name
                     "user_id": user_id,   # Fix RLS on INSERT/Retry
                     "updated_at": "now()"
                }
                
                if exists:
                    existing_row = exists_check.data[0]
                    existing_uid = existing_row.get("user_id")
                    
                    if existing_uid != user_id:
                        self.logger.error(f"❌ OWNERSHIP MISMATCH! Cloud Project {project_id} belongs to {existing_uid}. Resolving by rotating ID...")
                        
                        # --- AUTO-FIX: Rotate ID ---
                        new_id = str(uuid.uuid4())
                        db = DatabaseManager()
                        if db.rotate_project_id(project_id, new_id):
                            self.logger.info(f"✅ Local Project ID rotated to {new_id}. Retrying as NEW insertion.")
                            project_id = new_id
                            payload["id"] = new_id
                            # Now it's a new project, so we INSERT
                            res = self.supabase.table("cloud_projects").insert(payload).execute()
                            self.logger.info(f"✅ Insert success (Forked): {len(res.data)} rows affected.")
                            
                            self.logger.info(f"Projeto '{project_name}' (Obra: {work_name}) sincronizado com sucesso (Novo ID).")
                            return True
                        else:
                            self.logger.error("Failed to rotate project ID locally. Sync aborted.")
                            return False
                        # ---------------------------

                    else:
                        self.logger.info(f"✅ Ownership Validated. Owner: {existing_uid}")
                        
                        self.logger.info(f"Updating existing project {project_id}...")
                        res = self.supabase.table("cloud_projects").update(payload).eq("id", project_id).execute()
                        if not res.data:
                             self.logger.warning(f"⚠️ Update returned 0 rows! Check RLS policies for ID {project_id}.")
                        else:
                             self.logger.info(f"✅ Update success: {len(res.data)} rows affected.")
                         
                else:
                    self.logger.info(f"Inserting new project {project_id}...")
                    payload["id"] = project_id
                    res = self.supabase.table("cloud_projects").insert(payload).execute()
                    self.logger.info(f"✅ Insert success: {len(res.data)} rows affected.")
                    
                self.logger.info(f"Projeto '{project_name}' (Obra: {work_name}) sincronizado com sucesso.")
                return True
                
            except Exception as e_db:
                self.logger.error(f"DB Operation Failed: {e_db}")
                # Fallback to original upsert if manual fail (though likely same error)
                if "policy" in str(e_db): raise e_db
                return False
            
        except Exception as e:
            self.logger.error(f"Erro ao sincronizar projeto: {e}")
            return False

    def list_community_projects(self) -> list:
        """
        Lista projetos de todos os usuários (Apenas para Admin).
        Baseado na política de RLS definida no banco.
        """
        try:
            # Join com profiles (public) em vez de auth.users (protegido)
            res = self.supabase.table("cloud_projects").select("*, profiles(email, full_name)").order("created_at", desc=True).execute()
            self.logger.info(f"Supabase List returned {len(res.data)} items.")
            if not res.data:
                self.logger.warning("Supabase returned empty list for community projects.")
            return res.data
        except Exception as e:
            self.logger.error(f"Erro ao listar projetos da comunidade: {e}")
            try:
                # Fallback Debug: Try to list without join to see if it works
                res_fallback = self.supabase.table("cloud_projects").select("*").execute()
                self.logger.error(f"Fallback Check: Without join, found {len(res_fallback.data)} items.")
            except:
                pass
            return []

    def download_project(self, storage_path: str) -> Optional[Dict]:
        """
        Baixa um projeto da nuvem para curadoria.
        """
        try:
            data = self.supabase.storage.from_(self.PROJECTS_BUCKET).download(storage_path)
            return json.loads(data)
        except Exception as e:
            self.logger.error(f"Erro ao baixar projeto {storage_path}: {e}")
            return None
