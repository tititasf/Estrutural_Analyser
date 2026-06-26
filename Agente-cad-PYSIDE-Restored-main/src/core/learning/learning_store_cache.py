# src/core/learning/learning_store_cache.py
"""
Cache singleton thread-safe para o Learning Store.
Evita re-parse de JSON a cada deteccao.

Features:
- Singleton: uma instancia por processo
- Primeira leitura carrega do JSON; subsequentes vêm do cache
- Invalidacao granular por class_type + field_name
- Thread-safe via threading.Lock
- LRU com max 1000 entries por class_type
"""
from __future__ import annotations

import json
import os
import threading
from collections import OrderedDict
from typing import Any, Optional


MAX_ENTRIES_PER_CLASS = 1000


class LearningStoreCache:
    """Cache singleton thread-safe para LearningStore."""

    _instance = None
    _instance_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._instance_lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock = threading.Lock()
        # cache[class_type] = OrderedDict[field_name, stats_dict]
        self._cache: dict[str, OrderedDict] = {}
        # file_cache[path] = (mtime, data)
        self._file_cache: dict[str, tuple[float, dict]] = {}

    def get_field_stats(self, class_type: str, field_name: str,
                        json_path: str, loader_fn) -> dict:
        """Retorna stats de um campo do cache ou carrega do JSON.

        Args:
            class_type: "slab", "pillar", etc.
            field_name: nome do campo
            json_path: caminho do JSON para carregar se cache miss
            loader_fn: funcao que carrega o JSON e retorna os stats

        Returns:
            dict com hit_rate, sample_count, parameters, etc.
        """
        cache_key = f"{class_type}|{field_name}"

        with self._lock:
            # Verificar cache
            class_cache = self._cache.get(class_type)
            if class_cache and cache_key in class_cache:
                return class_cache[cache_key]

        # Cache miss: carregar do JSON (fora do lock para nao bloquear)
        stats = loader_fn()

        with self._lock:
            if class_type not in self._cache:
                self._cache[class_type] = OrderedDict()
            class_cache = self._cache[class_type]

            # LRU: remover mais antigo se exceder limite
            if len(class_cache) >= MAX_ENTRIES_PER_CLASS:
                class_cache.popitem(last=False)

            class_cache[cache_key] = stats

        return stats

    def get_adjusted_parameters(self, class_type: str, json_path: str,
                                 loader_fn) -> dict:
        """Retorna todos os parametros ajustados de uma classe."""
        cache_key = "__all_params__"

        with self._lock:
            class_cache = self._cache.get(class_type)
            if class_cache and cache_key in class_cache:
                return class_cache[cache_key]

        params = loader_fn()

        with self._lock:
            if class_type not in self._cache:
                self._cache[class_type] = OrderedDict()
            self._cache[class_type][cache_key] = params

        return params

    def invalidate(self, class_type: str, field_name: str = None) -> None:
        """Invalida cache granular.
        Se field_name=None, invalida toda a classe.
        """
        with self._lock:
            if field_name is None:
                self._cache.pop(class_type, None)
            else:
                class_cache = self._cache.get(class_type)
                if class_cache:
                    cache_key = f"{class_type}|{field_name}"
                    class_cache.pop(cache_key, None)
                    # Invalidar tambem o all_params
                    class_cache.pop("__all_params__", None)

    def invalidate_all(self, class_type: str = None) -> None:
        """Invalida todo o cache de uma classe ou tudo."""
        with self._lock:
            if class_type:
                self._cache.pop(class_type, None)
            else:
                self._cache.clear()

    def get_cache_stats(self) -> dict:
        """Retorna estatisticas do cache para diagnostico."""
        with self._lock:
            return {
                class_type: len(entries)
                for class_type, entries in self._cache.items()
            }
