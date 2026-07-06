"""Regras de visibilidade entre membro comum e dono (papel='dono') — 2026-07-06.

O schema (portal_membros.papel CHECK IN ('membro','dono')) já previa o papel
'dono' desde o Data Engineer, mas nenhum endpoint usava isso — cada rota checava
`obra["membro_id"] != membro["id"]` direto, o que bloquearia o dono de ver obras
de outros membros. Centralizado aqui para não duplicar (e não esquecer) a regra
nos 5 lugares que faziam essa checagem (obras/jobs/comentarios/fichas/paginas).
"""

from __future__ import annotations


def eh_dono(membro: dict) -> bool:
    return membro.get("papel") == "dono"


def pode_ver_obra(obra: dict, membro: dict) -> bool:
    """Dono vê qualquer obra; membro comum só a própria."""
    return eh_dono(membro) or obra["membro_id"] == membro["id"]
