# src/core/learning/learning_store_factory.py
"""
Factory para instanciar o Learning Store correto por classe estrutural.
"""
from __future__ import annotations

import os
from typing import Optional

from .learning_store_base import LearningStoreBase


class LearningStoreFactory:
    """Factory para criar instancias de LearningStore por class_type."""

    @staticmethod
    def create(project_uuid: str, class_type: str, base_dir: str = "") -> LearningStoreBase:
        """Cria uma instancia de LearningStore para a classe especificada.

        Args:
            project_uuid: UUID do projeto
            class_type: "slab" | "pillar" | "lateral_beam" | "bottom_beam"
            base_dir: diretorio base do projeto (default: cwd)

        Returns:
            LearningStoreBase configurado para a classe

        Raises:
            ValueError: se class_type nao e valido
        """
        valid_types = {"slab", "pillar", "lateral_beam", "bottom_beam"}
        if class_type not in valid_types:
            raise ValueError(
                f"class_type invalido: {class_type}. Validos: {valid_types}"
            )

        if class_type == "slab":
            from .slab_learning_store import SlabLearningStore
            return SlabLearningStore(project_uuid, base_dir)

        # Outras classes: usar base ate que as subclasses sejam criadas
        # FASE 2: bottom_beam_learning_store.py
        # FASE 3: lateral_beam_learning_store.py
        # FASE 4: pillar_learning_store.py
        return LearningStoreBase(project_uuid, class_type, base_dir)
