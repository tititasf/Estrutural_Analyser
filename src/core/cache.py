# -*- coding: utf-8 -*-
"""
Sistema de Cache para Pipeline GAP-5
Implementa cache de resultados para evitar reprocessamento de arquivos inalterados.
"""

import hashlib
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Entrada de cache."""
    key: str
    hash_arquivo: str
    dados: Any
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "hash_arquivo": self.hash_arquivo,
            "dados": self.dados,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "hit_count": self.hit_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheEntry":
        return cls(
            key=data["key"],
            hash_arquivo=data["hash_arquivo"],
            dados=data["dados"],
            created_at=data.get("created_at", time.time()),
            expires_at=data.get("expires_at"),
            hit_count=data.get("hit_count", 0)
        )


class DXFCache:
    """
    Cache específico para arquivos DXF processados.
    Usa hash do arquivo para detectar mudanças.
    """
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._ensure_tables()
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _ensure_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_dxf (
                id TEXT PRIMARY KEY,
                arquivo_path TEXT UNIQUE NOT NULL,
                arquivo_hash TEXT NOT NULL,
                arquivo_size INTEGER,
                arquivo_mtime REAL,
                entidades_json TEXT,
                layers_json TEXT,
                blocks_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                hit_count INTEGER DEFAULT 0,
                last_hit_at TIMESTAMP
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_dxf_hash ON cache_dxf(arquivo_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_dxf_path ON cache_dxf(arquivo_path)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_dxf_mtime ON cache_dxf(arquivo_mtime)")
        
        self.conn.commit()
    
    def calcular_hash_arquivo(self, caminho: str) -> str:
        """Calcula hash SHA-256 do arquivo."""
        sha256 = hashlib.sha256()
        try:
            with open(caminho, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
        except Exception as e:
            logger.warning(f"Erro ao calcular hash de {caminho}: {e}")
            return ""
    
    def get_info_arquivo(self, caminho: str) -> Tuple[int, float]:
        """Obtém tamanho e mtime do arquivo."""
        stat = os.stat(caminho)
        return stat.st_size, stat.st_mtime
    
    def exists(self, caminho: str) -> bool:
        """Verifica se arquivo está em cache e não mudou."""
        try:
            tamanho_atual, mtime_atual = self.get_info_arquivo(caminho)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT arquivo_hash, arquivo_size, arquivo_mtime 
                FROM cache_dxf 
                WHERE arquivo_path = ?
            """, (caminho,))
            
            row = cursor.fetchone()
            if not row:
                return False
            
            if row["arquivo_size"] != tamanho_atual or abs(row["arquivo_mtime"] - mtime_atual) > 1.0:
                return False
            
            return True
            
        except Exception as e:
            logger.debug(f"Erro ao verificar cache: {e}")
            return False
    
    def get(self, caminho: str) -> Optional[Dict[str, Any]]:
        """Obtém dados em cache para um arquivo DXF."""
        try:
            if not self.exists(caminho):
                return None
            
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT entidades_json, layers_json, blocks_json 
                FROM cache_dxf 
                WHERE arquivo_path = ?
            """, (caminho,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            cursor.execute("""
                UPDATE cache_dxf 
                SET hit_count = hit_count + 1, last_hit_at = CURRENT_TIMESTAMP
                WHERE arquivo_path = ?
            """, (caminho,))
            self.conn.commit()
            
            return {
                "entidades": json.loads(row["entidades_json"]) if row["entidades_json"] else [],
                "layers": json.loads(row["layers_json"]) if row["layers_json"] else [],
                "blocks": json.loads(row["blocks_json"]) if row["blocks_json"] else []
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter cache: {e}")
            return None
    
    def set(self, caminho: str, entidades: List[Dict], layers: List[str], blocks: List[str]) -> bool:
        """Salva dados em cache para um arquivo DXF."""
        try:
            tamanho, mtime = self.get_info_arquivo(caminho)
            arquivo_hash = self.calcular_hash_arquivo(caminho)
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_dxf 
                (id, arquivo_path, arquivo_hash, arquivo_size, arquivo_mtime, 
                 entidades_json, layers_json, blocks_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                f"dxf_{hashlib.md5(caminho.encode()).hexdigest()}",
                caminho,
                arquivo_hash,
                tamanho,
                mtime,
                json.dumps(entidades),
                json.dumps(layers),
                json.dumps(blocks)
            ))
            
            self.conn.commit()
            logger.debug(f"Cache salvo para {caminho} (hash: {arquivo_hash[:16]}...)")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar cache: {e}")
            self.conn.rollback()
            return False
    
    def invalidate(self, caminho: str) -> bool:
        """Invalida cache para um arquivo específico."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM cache_dxf WHERE arquivo_path = ?", (caminho,))
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Erro ao invalidar cache: {e}")
            return False
    
    def clear(self) -> int:
        """Limpa todo o cache. Retorna número de entradas removidas."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM cache_dxf")
            count = cursor.fetchone()[0]
            cursor.execute("DELETE FROM cache_dxf")
            self.conn.commit()
            logger.info(f"Cache limpo: {count} entradas removidas")
            return count
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtém estatísticas do cache."""
        cursor = self.conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM cache_dxf")
        total_entries = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(hit_count) FROM cache_dxf")
        total_hits = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT SUM(arquivo_size) FROM cache_dxf")
        total_size = cursor.fetchone()[0] or 0
        
        return {
            "total_entries": total_entries,
            "total_hits": total_hits,
            "total_size_bytes": total_size,
            "hit_rate": total_hits / max(total_entries, 1)
        }


class TransformationCache:
    """
    Cache para regras de transformação aplicadas.
    """
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._ensure_tables()
        self._memory_cache: Dict[str, Any] = {}
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _ensure_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_transformacao (
                id TEXT PRIMARY KEY,
                regra_hash TEXT NOT NULL,
                entrada_hash TEXT NOT NULL,
                resultado_json TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                hit_count INTEGER DEFAULT 0
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_trans_regra ON cache_transformacao(regra_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_trans_entrada ON cache_transformacao(entrada_hash)")
        
        self.conn.commit()
    
    def _calcular_hash(self, dados: Any) -> str:
        return hashlib.sha256(json.dumps(dados, sort_keys=True).encode()).hexdigest()
    
    def get(self, regra: str, entrada: Any) -> Optional[Any]:
        regra_hash = self._calcular_hash({"regra": regra})
        entrada_hash = self._calcular_hash(entrada)
        
        cache_key = f"{regra_hash}:{entrada_hash}"
        if cache_key in self._memory_cache:
            return self._memory_cache[cache_key]
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT resultado_json 
                FROM cache_transformacao 
                WHERE regra_hash = ? AND entrada_hash = ?
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (regra_hash, entrada_hash))
            
            row = cursor.fetchone()
            if row:
                resultado = json.loads(row["resultado_json"]) if row["resultado_json"] else None
                
                cursor.execute("""
                    UPDATE cache_transformacao 
                    SET hit_count = hit_count + 1 
                    WHERE regra_hash = ? AND entrada_hash = ?
                """, (regra_hash, entrada_hash))
                self.conn.commit()
                
                self._memory_cache[cache_key] = resultado
                return resultado
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter cache de transformação: {e}")
            return None
    
    def set(self, regra: str, entrada: Any, resultado: Any, ttl_seconds: Optional[int] = None) -> bool:
        regra_hash = self._calcular_hash({"regra": regra})
        entrada_hash = self._calcular_hash(entrada)
        cache_key = f"{regra_hash}:{entrada_hash}"
        
        try:
            cursor = self.conn.cursor()
            
            expires_at = None
            if ttl_seconds:
                expires_at = datetime.now() + timedelta(seconds=ttl_seconds)
            
            cursor.execute("""
                INSERT OR REPLACE INTO cache_transformacao 
                (id, regra_hash, entrada_hash, resultado_json, expires_at, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                cache_key,
                regra_hash,
                entrada_hash,
                json.dumps(resultado) if resultado else None,
                expires_at
            ))
            
            self.conn.commit()
            self._memory_cache[cache_key] = resultado
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar cache de transformação: {e}")
            self.conn.rollback()
            return False
    
    def clear(self, regra: Optional[str] = None) -> int:
        try:
            cursor = self.conn.cursor()
            
            if regra:
                regra_hash = self._calcular_hash({"regra": regra})
                cursor.execute("DELETE FROM cache_transformacao WHERE regra_hash = ?", (regra_hash,))
            else:
                cursor.execute("DELETE FROM cache_transformacao")
                self._memory_cache.clear()
            
            count = cursor.rowcount
            self.conn.commit()
            return count
            
        except Exception as e:
            logger.error(f"Erro ao limpar cache: {e}")
            return 0


class FichaCache:
    """
    Cache para fichas geradas (pilares, vigas, lajes).
    """
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._connect()
        self._ensure_tables()
    
    def _connect(self) -> sqlite3.Connection:
        if not self.conn:
            self.conn = sqlite3.connect(self.db_path, timeout=30.0)
            self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def _ensure_tables(self):
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS cache_fichas (
                id TEXT PRIMARY KEY,
                obra_id TEXT NOT NULL,
                pavimento TEXT,
                tipo TEXT NOT NULL,
                codigo TEXT NOT NULL,
                entidade_hash TEXT NOT NULL,
                ficha_json TEXT,
                confidence REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (obra_id) REFERENCES obras(id)
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_fichas_obra ON cache_fichas(obra_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_fichas_pavimento ON cache_fichas(pavimento)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_fichas_tipo ON cache_fichas(tipo)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_fichas_codigo ON cache_fichas(codigo)")
        
        self.conn.commit()
    
    def exists(self, obra_id: str, tipo: str, codigo: str, entidade_hash: str) -> bool:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT COUNT(*) 
                FROM cache_fichas 
                WHERE obra_id = ? AND tipo = ? AND codigo = ? AND entidade_hash = ?
            """, (obra_id, tipo, codigo, entidade_hash))
            
            return cursor.fetchone()[0] > 0
            
        except Exception as e:
            logger.error(f"Erro ao verificar cache de ficha: {e}")
            return False
    
    def get(self, obra_id: str, tipo: str, codigo: str, entidade_hash: str) -> Optional[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT ficha_json, confidence 
                FROM cache_fichas 
                WHERE obra_id = ? AND tipo = ? AND codigo = ? AND entidade_hash = ?
            """, (obra_id, tipo, codigo, entidade_hash))
            
            row = cursor.fetchone()
            if row:
                return {
                    "dados": json.loads(row["ficha_json"]) if row["ficha_json"] else {},
                    "confidence": row["confidence"]
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao obter ficha do cache: {e}")
            return None
    
    def set(self, obra_id: str, pavimento: str, tipo: str, codigo: str, 
            entidade_hash: str, ficha: Dict[str, Any], confidence: float) -> bool:
        try:
            ficha_id = f"ficha_{obra_id}_{tipo}_{codigo}_{hashlib.md5(entidade_hash.encode()).hexdigest()[:8]}"
            
            cursor = self.conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO cache_fichas 
                (id, obra_id, pavimento, tipo, codigo, entidade_hash, ficha_json, confidence, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (
                ficha_id,
                obra_id,
                pavimento,
                tipo,
                codigo,
                entidade_hash,
                json.dumps(ficha),
                confidence
            ))
            
            self.conn.commit()
            return True
            
        except Exception as e:
            logger.error(f"Erro ao salvar ficha em cache: {e}")
            self.conn.rollback()
            return False
    
    def get_by_obra(self, obra_id: str) -> List[Dict[str, Any]]:
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
                SELECT id, obra_id, pavimento, tipo, codigo, ficha_json, confidence, created_at
                FROM cache_fichas 
                WHERE obra_id = ?
            """, (obra_id,))
            
            fichas = []
            for row in cursor.fetchall():
                fichas.append({
                    "id": row["id"],
                    "obra_id": row["obra_id"],
                    "pavimento": row["pavimento"],
                    "tipo": row["tipo"],
                    "codigo": row["codigo"],
                    "dados": json.loads(row["ficha_json"]) if row["ficha_json"] else {},
                    "confidence": row["confidence"],
                    "created_at": row["created_at"]
                })
            
            return fichas
            
        except Exception as e:
            logger.error(f"Erro ao obter fichas da obra: {e}")
            return []
    
    def invalidate_obra(self, obra_id: str) -> int:
        try:
            cursor = self.conn.cursor()
            cursor.execute("DELETE FROM cache_fichas WHERE obra_id = ?", (obra_id,))
            count = cursor.rowcount
            self.conn.commit()
            return count
        except Exception as e:
            logger.error(f"Erro ao invalidar fichas da obra: {e}")
            return 0


class PipelineCache:
    """
    Cache unificado para todo o pipeline.
    """
    
    def __init__(self, db_path: str = "project_data.vision"):
        self.db_path = db_path
        self.dxf_cache = DXFCache(db_path)
        self.transformation_cache = TransformationCache(db_path)
        self.ficha_cache = FichaCache(db_path)
    
    def close(self):
        self.dxf_cache.close()
        self.transformation_cache.close()
        self.ficha_cache.close()
    
    def get_stats(self) -> Dict[str, Any]:
        return {
            "dxf_cache": self.dxf_cache.get_stats(),
            "transformation_cache": {
                "memory_entries": len(self.transformation_cache._memory_cache)
            },
            "ficha_cache": {
                "db_path": self.db_path
            }
        }
    
    def clear_all(self) -> Dict[str, int]:
        return {
            "dxf_cache": self.dxf_cache.clear(),
            "transformation_cache": self.transformation_cache.clear(),
            "ficha_cache": 0
        }


def calcular_hash_arquivo(caminho: str) -> str:
    """Calcula hash SHA-256 de um arquivo."""
    return DXFCache("").calcular_hash_arquivo(caminho)


def get_cache_stats(db_path: str = "project_data.vision") -> Dict[str, Any]:
    """Obtém estatísticas de cache para um banco de dados."""
    cache = PipelineCache(db_path)
    stats = cache.get_stats()
    cache.close()
    return stats
