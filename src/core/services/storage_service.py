import os
import logging
import math
from typing import Optional, List
from src.core.infra.supabase_client import SupabaseClient

class StorageService:
    """
    Serviço para gerenciar o Supabase Storage com suporte a fragmentação de arquivos.
    Limite de upload por requisição no Supabase é geralmente ~50MB.
    Fragmentamos arquivos > 49MB em partes de 40MB.
    """
    
    BUCKETS = {
        "DOCS": "project-documents",
        "PROJECTS": "user_projects"
    }
    CHUNK_SIZE = 40 * 1024 * 1024 # 40MB
    MAX_SINGLE_UPLOAD = 49 * 1024 * 1024 # 49MB

    def __init__(self):
        self.supabase = SupabaseClient.get_instance().client
        self.logger = logging.getLogger(__name__)

    def _ensure_bucket(self, bucket_name: str):
        """Garante que o bucket existe (Supabase via API)"""
        try:
            # Note: supabase-py não tem um 'get_bucket' simples que retorne boolean sem exception
            self.supabase.storage.get_bucket(bucket_name)
        except Exception:
            try:
                self.supabase.storage.create_bucket(bucket_name, options={"public": False})
                self.logger.info(f"Bucket '{bucket_name}' criado com sucesso.")
            except Exception as e:
                self.logger.error(f"Falha ao criar bucket '{bucket_name}': {e}")

    def upload_file(self, bucket: str, remote_path: str, local_path: str) -> Optional[str]:
        """
        Upload de arquivo com detecção de tamanho para fragmentação.
        Retorna o remote_path base se sucesso.
        """
        if not os.path.exists(local_path):
            self.logger.error(f"Arquivo local não encontrado: {local_path}")
            return None

        file_size = os.path.getsize(local_path)
        self._ensure_bucket(bucket)

        try:
            if file_size <= self.MAX_SINGLE_UPLOAD:
                # Upload Simples
                with open(local_path, 'rb') as f:
                    self.supabase.storage.from_(bucket).upload(
                        path=remote_path,
                        file=f,
                        file_options={"upsert": "true"}
                    )
                self.logger.info(f"Upload simples concluído: {remote_path}")
                return remote_path
            else:
                # Upload Fragmentado
                return self._upload_in_chunks(bucket, remote_path, local_path, file_size)
        except Exception as e:
            self.logger.error(f"Erro no upload de {local_path}: {e}")
            return None

    def upload_content(self, bucket: str, remote_path: str, content: bytes, content_type: str = "application/octet-stream") -> Optional[str]:
        """Upload direto de bytes em memória."""
        self._ensure_bucket(bucket)
        try:
            self.supabase.storage.from_(bucket).upload(
                path=remote_path,
                file=content,
                file_options={"content-type": content_type, "upsert": "true"}
            )
            self.logger.info(f"Upload de conteúdo concluído: {remote_path}")
            return remote_path
        except Exception as e:
            self.logger.error(f"Erro no upload de conteúdo para {remote_path}: {e}")
            return None

    def _upload_in_chunks(self, bucket: str, remote_path: str, local_path: str, file_size: int) -> Optional[str]:
        """Divide o arquivo e sobe as partes."""
        num_chunks = math.ceil(file_size / self.CHUNK_SIZE)
        self.logger.info(f"Iniciando upload fragmentado ({num_chunks} partes) para {remote_path}")

        try:
            with open(local_path, 'rb') as f:
                for i in range(num_chunks):
                    chunk_data = f.read(self.CHUNK_SIZE)
                    part_path = f"{remote_path}.part{i+1}"
                    
                    self.supabase.storage.from_(bucket).upload(
                        path=part_path,
                        file=chunk_data,
                        file_options={"upsert": "true"}
                    )
                    self.logger.info(f"Parte {i+1}/{num_chunks} enviada.")
            
            # Marcador de arquivo fragmentado (opcional, ou apenas inferir pelo sUfixo)
            # Vamos subir um pequeno metadata/json se necessário futuramente.
            return remote_path
        except Exception as e:
            self.logger.error(f"Erro no upload fragmentado: {e}")
            return None

    def download_file(self, bucket: str, remote_path: str, local_path: str) -> bool:
        """
        Download de arquivo detectando partes fragmentadas se necessário.
        """
        try:
            # Tentar baixar como arquivo único primeiro
            try:
                data = self.supabase.storage.from_(bucket).download(remote_path)
                with open(local_path, 'wb') as f:
                    f.write(data)
                self.logger.info(f"Download simples concluído: {remote_path}")
                return True
            except Exception:
                # Se falhar, tentar buscar partes .part1, .part2...
                return self._download_and_reassemble(bucket, remote_path, local_path)
        except Exception as e:
            self.logger.error(f"Erro no download de {remote_path}: {e}")
            return False

    def _download_and_reassemble(self, bucket: str, remote_path: str, local_path: str) -> bool:
        """Busca partes no storage e remonta localmente."""
        self.logger.info(f"Tentando reconstruir arquivo fragmentado: {remote_path}")
        
        part_idx = 1
        found_any = False
        
        try:
            with open(local_path, 'wb') as target:
                while True:
                    part_path = f"{remote_path}.part{part_idx}"
                    try:
                        data = self.supabase.storage.from_(bucket).download(part_path)
                        target.write(data)
                        self.logger.info(f"Parte {part_idx} baixada e unificada.")
                        part_idx += 1
                        found_any = True
                    except Exception:
                        # Quando não encontrar mais partes, encerra o loop
                        break
            
            if found_any:
                self.logger.info(f"Arquivo reconstruído com sucesso: {local_path}")
                return True
            else:
                self.logger.warning(f"Nenhuma parte encontrada para {remote_path}")
                if os.path.exists(local_path): os.remove(local_path)
                return False
        except Exception as e:
            self.logger.error(f"Erro na reconstrução do arquivo: {e}")
            return False

    def delete_file(self, bucket: str, remote_path: str):
        """Remove o arquivo e suas possíveis partes."""
        try:
            # Tentar remover o base
            self.supabase.storage.from_(bucket).remove([remote_path])
            
            # Tentar remover partes (até um limite razoável ou listar e filtrar)
            # Para simplificar, tentamos remover as primeiras 20 partes se existirem
            parts_to_del = [f"{remote_path}.part{i}" for i in range(1, 21)]
            self.supabase.storage.from_(bucket).remove(parts_to_del)
            
            self.logger.info(f"Cleanup concluído para {remote_path}")
        except Exception as e:
            self.logger.warning(f"Erro ao deletar arquivo(s): {e}")
