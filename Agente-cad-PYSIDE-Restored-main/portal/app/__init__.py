"""Backend FastAPI do Portal Soberano (gates P1-P3).

Este pacote NUNCA importa PySide6. Ele aciona o pipeline headless existente por
subprocess (scripts.arete.headless_sa_analise) e importa apenas duas bibliotecas
leves do monolito: scripts.arete.single_instance (lock de fila) e
src.core.n5_assembler (montagem do N5, só ezdxf). Ver HANDOFF-ARCHITECT-PORTAL.md.

Fronteira (§3 do masterplan): o portal só grava portal_data.db (obras, jobs,
comentarios equipe:*, releases N5). NUNCA escreve em project_data.vision.
"""

from __future__ import annotations

__all__ = ["create_app"]


def create_app(*args, **kwargs):  # pragma: no cover - fino wrapper de conveniencia
    """Reexporta a app factory de portal.app.main (import tardio evita ciclos)."""
    from .main import create_app as _factory

    return _factory(*args, **kwargs)
