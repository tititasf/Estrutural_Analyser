"""Fonte canônica de entrada do Structural Analyzer.

O SA humano seleciona um registro de ``projects`` e carrega exatamente o
``projects.dxf_path`` desse registro. Automações devem resolver o projeto pelo
mesmo conjunto ordenado retornado por ``DatabaseManager.get_projects()``.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable


def _floor_key(value: str | None):
    text = str(value or "").strip().upper()
    match = re.search(
        r"(?:^|[-_ ])(\d{1,2})(?:_?PAV(?:IMENTO)?|P(?:AV|V)?)(?:$|[-_ ])",
        text,
    )
    if match:
        return ("NUMBER", int(match.group(1)))
    for token, key in (
        ("COB", "COBERTURA"),
        ("ATC", "ATICO"),
        ("TER", "TERREO"),
        ("SUB", "SUBSOLO"),
        ("GAR", "GARAGEM"),
        ("FUN", "FUNDACAO"),
        ("TIP", "TIPO"),
    ):
        if re.search(rf"(?:^|[-_ ]){token}(?:$|[-_ ])", text):
            return ("SPECIAL", key)
    return ("TEXT", re.sub(r"\W+", "", text))


def select_sa_project(
    projects: Iterable[dict],
    obra: str,
    pavimento: str | None = None,
    project_id: str | None = None,
) -> dict:
    """Seleciona o mesmo projeto que aparece primeiro no combo humano do SA.

    ``projects`` deve manter a ordem de ``DatabaseManager.get_projects()``
    (``updated_at DESC``). Assim duplicatas legadas do mesmo pavimento não
    substituem o recorte atualmente usado pela interface.
    """
    work_projects = [
        project for project in projects
        if str(project.get("work_name") or "") == str(obra or "")
    ]
    if project_id:
        selected = next(
            (p for p in work_projects if str(p.get("id")) == str(project_id)),
            None,
        )
        if selected is None:
            raise LookupError(f"Projeto SA não encontrado: {project_id}")
        return _validate_source(selected)

    requested = str(pavimento or "").strip()
    if not requested:
        raise ValueError("Pavimento SA não informado")

    requested_upper = requested.upper()
    exact = [
        p for p in work_projects
        if str(p.get("pavement_name") or p.get("name") or "").strip().upper()
        == requested_upper
    ]
    if exact:
        return _validate_source(exact[0])

    floor_key = _floor_key(requested)
    matched = [
        p for p in work_projects
        if _floor_key(p.get("pavement_name") or p.get("name")) == floor_key
    ]
    if not matched:
        raise LookupError(f"Pavimento SA não encontrado: {obra} / {pavimento}")
    return _validate_source(matched[0])


def _validate_source(project: dict) -> dict:
    source = Path(str(project.get("dxf_path") or ""))
    if not source.is_file():
        raise FileNotFoundError(
            f"Recorte do projeto SA ausente: {project.get('id')} -> {source}"
        )
    result = dict(project)
    result["dxf_path"] = str(source.resolve())
    return result


def resolve_sa_project_from_db(
    db_path: str,
    obra: str,
    pavimento: str | None = None,
    project_id: str | None = None,
) -> dict:
    """Resolve pelo mesmo ``DatabaseManager.get_projects`` usado na UI."""
    from src.core.database import DatabaseManager

    database = DatabaseManager(db_path=db_path)
    return select_sa_project(
        database.get_projects(),
        obra=obra,
        pavimento=pavimento,
        project_id=project_id,
    )

