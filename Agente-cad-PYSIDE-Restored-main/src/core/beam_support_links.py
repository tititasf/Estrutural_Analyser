"""Normalização neutra dos apoios globais de vigas.

Este módulo não interpreta FV ou LV: apenas copia um candidato de apoio e,
quando o chamador já provou que está no contexto FV, marca sua proveniência de
limite global. Centralizá-lo evita helpers locais em métodos distintos de
``MainWindow`` e mantém os vínculos LV livres de semântica FV.
"""

from __future__ import annotations

from typing import Any


def global_beam_boundary_link(
    candidate: Any,
    *,
    is_fv_context: bool,
) -> dict[str, Any]:
    """Retorna cópia serializável do apoio global de uma viga.

    ``is_fv_context`` é decidido pelo motor chamador; esta função não deduz
    classe nem consulta fichas. Em LV/PIL/LAJ o candidato permanece neutro.
    """
    link = dict(candidate) if isinstance(candidate, dict) else {
        "type": "text",
        "text": str(candidate),
        "name": str(candidate),
    }
    if is_fv_context:
        link["evidence_role"] = "fv_beam_global_boundary"
        link["scope"] = "beam_global"
    return link
