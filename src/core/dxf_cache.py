# -*- coding: utf-8 -*-
"""
DXF Cache - Cache LRU em memória para documentos DXF carregados.

Evita re-leitura de arquivos DXF já processados.
Suporta limites de tamanho e memória, com eviction LRU.
Opcionalmente persiste cache em disco via pickle.
"""

import logging
import time
from collections import OrderedDict
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class DXFCache:
    """
    Cache LRU em memória para documentos DXF.

    Armazena documentos ezdxf carregados com eviction automática
    baseada em tamanho máximo e limite de memória.
    """

    def __init__(self, max_size: int = 10, max_memory_mb: float = 500.0):
        """
        Args:
            max_size: Número máximo de documentos no cache.
            max_memory_mb: Limite de memória total do cache em MB.
        """
        self._cache: OrderedDict = OrderedDict()  # path -> (doc, timestamp, size_kb)
        self._max_size = max_size
        self._max_memory_mb = max_memory_mb
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        logger.info(f"DXFCache inicializado: max_size={max_size}, max_memory={max_memory_mb}MB")

    def get(self, path: str) -> Optional[object]:
        """
        Busca documento no cache.

        Args:
            path: Caminho do arquivo DXF.

        Returns:
            Documento ezdxf ou None se não encontrado.
        """
        if path in self._cache:
            doc, _, size = self._cache[path]
            # Move para o final (mais recente no LRU)
            self._cache.move_to_end(path)
            self._hits += 1
            logger.info(f"Cache HIT: {path} (hits={self._hits}, misses={self._misses})")
            return doc

        self._misses += 1
        logger.info(f"Cache MISS: {path}")
        return None

    def set(self, path: str, doc: object, size_estimate: float = None):
        """
        Armazena documento no cache.

        Args:
            path: Caminho do arquivo DXF.
            doc: Documento ezdxf carregado.
            size_estimate: Tamanho estimado em KB (calculado automaticamente se None).
        """
        if size_estimate is None:
            size_estimate = self._estimate_doc_size(doc)

        self._cache[path] = (doc, time.time(), size_estimate)
        self._cache.move_to_end(path)

        logger.info(f"Cache SET: {path} (size={size_estimate:.0f}KB, cache_size={len(self._cache)})")

        self._enforce_limits()

    def clear(self):
        """Limpa todo o cache."""
        self._cache.clear()
        logger.info("Cache cleared")

    def remove(self, path: str):
        """Remove item específico do cache."""
        if path in self._cache:
            del self._cache[path]
            logger.info(f"Cache REMOVE: {path}")

    def get_stats(self) -> Dict:
        """Retorna estatísticas do cache."""
        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0
        total_size_mb = sum(size for _, _, size in self._cache.values()) / 1024

        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1f}%",
            "entries": len(self._cache),
            "max_size": self._max_size,
            "total_size_mb": f"{total_size_mb:.1f}MB",
            "max_memory_mb": f"{self._max_memory_mb}MB",
            "evictions": self._evictions,
        }

    def _enforce_limits(self):
        """
        Aplica limites de size e memória.

        Remove itens mais antigos (LRU) se necessário.
        """
        # Limite de quantidade
        while len(self._cache) > self._max_size:
            self._evict_oldest()

        # Limite de memória
        total_size_mb = sum(size for _, _, size in self._cache.values()) / 1024
        while total_size_mb > self._max_memory_mb and len(self._cache) > 0:
            self._evict_oldest()
            total_size_mb = sum(size for _, _, size in self._cache.values()) / 1024

    def _evict_oldest(self):
        """Remove o item mais antigo do cache (LRU)."""
        if not self._cache:
            return
        path, (doc, ts, size) = self._cache.popitem(last=False)
        self._evictions += 1
        logger.info(f"Cache EVICT: {path} (size={size:.0f}KB, evictions={self._evictions})")

    def _estimate_doc_size(self, doc, default_kb: float = 100.0) -> float:
        """Estima tamanho de um documento ezdxf em KB."""
        try:
            msp = doc.modelspace()
            entity_count = sum(1 for _ in msp)
            # Estimativa: ~0.5KB por entidade
            estimate = entity_count * 0.5
            return max(estimate, 10.0)
        except Exception as e:
            logger.warning(f"Erro ao estimar tamanho do doc: {e}")
            return default_kb

    def print_stats(self):
        """Imprime estatísticas formatadas."""
        stats = self.get_stats()
        print("\n=== DXF Cache Statistics ===")
        print(f"Hits:       {stats['hits']}")
        print(f"Misses:     {stats['misses']}")
        print(f"Hit Rate:   {stats['hit_rate']}")
        print(f"Entries:    {stats['entries']}/{stats['max_size']}")
        print(f"Size:       {stats['total_size_mb']}/{stats['max_memory_mb']}")
        print(f"Evictions:  {stats['evictions']}")


class DXFCacheWithPersistence(DXFCache):
    """
    Extensão do DXFCache com persistência em disco via pickle.

    Salva documentos em disco para recuperação entre sessões.
    """

    def __init__(self, cache_dir: str = None, **kwargs):
        super().__init__(**kwargs)
        import os
        self._cache_dir = cache_dir
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
        logger.info(f"DXFCacheWithPersistence inicializado: cache_dir={cache_dir}")

    def get(self, path: str) -> Optional[object]:
        """Busca no cache em memória, depois em disco."""
        doc = super().get(path)
        if doc is not None:
            return doc

        # Tenta carregar do disco
        doc = self._load_from_disk(path)
        if doc is not None:
            # Coloca de volta no cache em memória
            super().set(path, doc)
            return doc

        return None

    def set(self, path: str, doc: object, size_estimate: float = None, persist: bool = True):
        """Armazena no cache em memória e opcionalmente em disco."""
        super().set(path, doc, size_estimate)
        if persist and self._cache_dir:
            self._save_to_disk(path, doc)

    def _save_to_disk(self, path: str, doc: object):
        """Salva documento em disco (pickle)."""
        try:
            import hashlib
            import pickle

            hash_name = hashlib.md5(path.encode()).hexdigest()
            cache_file = f"{self._cache_dir}/{hash_name}.pkl"

            with open(cache_file, "wb") as f:
                pickle.dump(doc, f)

            logger.info(f"Cache PERSIST: {path} -> {cache_file}")
        except Exception as e:
            logger.warning(f"Erro ao persistir cache: {e}")

    def _load_from_disk(self, path: str) -> Optional[object]:
        """Carrega documento de disco (pickle)."""
        if not self._cache_dir:
            return None

        try:
            import hashlib
            import os
            import pickle

            hash_name = hashlib.md5(path.encode()).hexdigest()
            cache_file = f"{self._cache_dir}/{hash_name}.pkl"

            if not os.path.exists(cache_file):
                return None

            with open(cache_file, "rb") as f:
                doc = pickle.load(f)

            logger.info(f"Cache LOAD FROM DISK: {cache_file}")
            return doc
        except Exception as e:
            logger.warning(f"Erro ao carregar cache de disco: {e}")
            return None


if __name__ == "__main__":
    # Teste básico
    cache = DXFCache(max_size=3)

    for i in range(5):
        path = f"test_{i}.dxf"
        doc = f"Document {i}"
        cache.set(path, doc)

    assert cache.get("test_0.dxf") is None  # evicted
    assert cache.get("test_2.dxf") is not None
    assert cache.get("test_3.dxf") is not None
    assert cache.get("test_4.dxf") is not None

    cache.print_stats()
    print("\n[OK] Cache test passed!")
