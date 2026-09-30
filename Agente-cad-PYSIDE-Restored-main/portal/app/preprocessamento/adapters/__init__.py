"""Adapters puros e isolados do pré-processamento."""

from .pillar_convention import extract_pillar_convention, geometry_signature
from .pillars import inventory_pillars

__all__ = ["extract_pillar_convention", "geometry_signature", "inventory_pillars"]
