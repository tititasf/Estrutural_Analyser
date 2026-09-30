"""Geometria manual e exclusões compartilhadas por fichas e estrutural limpo.

O sidecar conserva as decisões humanas nas próximas publicações SA, sem mudar
o schema N1. Snapshots derivados são gravados atomicamente com backup.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import json
import re

from . import fv_operations as fv

CLASSES = {"pilares", "pilares_especiais", "lajes", "fundo",
           "lateral_a_para", "lateral_b_para", "lateral_a_passa", "lateral_b_passa"}


def sidecar_path(obra_dir: Path, pav: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", pav):
        raise ValueError("pavimento inválido")
    return Path(obra_dir) / ".portal_overrides" / "geometry" / f"{pav}.json"


def load(obra_dir: Path, pav: str) -> dict:
    path = sidecar_path(obra_dir, pav)
    return fv._read_json(path) if path.is_file() else {"edits": {}, "deleted": {}}


def collection(state: dict, classe: str) -> list:
    if classe not in CLASSES:
        raise ValueError("classe não editável")
    if classe.startswith("pilares"):
        return state.setdefault("pilares", [])
    if classe == "lajes":
        return state.setdefault("slabs", [])
    return state.setdefault("segmentos", {}).setdefault(classe, [])


def identity(row: dict, classe: str) -> str:
    return str(row.get("name") if classe.startswith("pilares") or classe == "lajes" else row.get("uid") or "")


def canonical(classe: str) -> str:
    if classe not in CLASSES:
        raise ValueError("classe não editável")
    return "pilares" if classe.startswith("pilares") else classe


def apply_state(state: dict, obra_dir: Path, pav: str) -> dict:
    custom = load(obra_dir, pav)
    for classe in set(custom.get("edits", {})) | set(custom.get("deleted", {})):
        rows = collection(state, classe)
        edits = custom.get("edits", {}).get(classe, {})
        deleted = custom.get("deleted", {}).get(classe, [])
        rows[:] = [r for r in rows if identity(r, classe) not in deleted and
                   ("beam:" + str(r.get("beam_name") or "").upper()) not in deleted]
        for row in rows:
            patch = edits.get(identity(row, classe))
            if patch:
                row.update(deepcopy(patch))
    return state


def mutate(obra_dir: Path, pav: str, classe: str, target: str,
           *, points=None, delete=False, whole_beam=False) -> dict:
    classe = canonical(classe)
    with fv._MUTATION_LOCK:
        path = fv._state_path(obra_dir, pav)
        state = apply_state(fv._read_json(path), obra_dir, pav)
        rows = collection(state, classe)
        classes = [classe]
        if whole_beam and classe.startswith("lateral_"):
            # Uma ficha lateral reúne A e B do comportamento escolhido.
            behavior = classe.rsplit("_", 1)[1]
            classes = [f"lateral_a_{behavior}", f"lateral_b_{behavior}"]
        matches = [(c, r) for c in classes for r in collection(state, c)
                   if ((str(r.get("beam_name") or "").upper() == target.upper())
                       if whole_beam else identity(r, c) == target)]
        if not matches or (not whole_beam and len(matches) != 1):
            raise LookupError("item não encontrado ou ambíguo")
        custom = load(obra_dir, pav)
        affected = []
        if delete:
            for c, row in matches:
                collection(state, c).remove(row)
                key = identity(row, c)
                custom.setdefault("deleted", {}).setdefault(c, []).append(key)
                custom.setdefault("edits", {}).setdefault(c, {}).pop(key, None)
                affected.append({"classe": c, "item_id": key})
            if whole_beam:
                for c in classes:
                    custom.setdefault("deleted", {}).setdefault(c, []).append("beam:" + target.upper())
        else:
            polygon = fv._points(points)
            from shapely.geometry import Polygon
            poly = Polygon(polygon)
            if not poly.is_valid or poly.area <= 0:
                raise ValueError("contorno inválido, cruzado ou sem área")
            length, width = fv._dimensions(polygon)
            c, row = matches[0]
            patch = {"points": polygon}
            if c.startswith("lateral_") or c == "fundo":
                patch.update(length=length, width=width, status="valid", atencao="")
            if c == "pilares":
                from src.core.perspective_mapper import PillarPerspectiveMapper
                shape, orientation = PillarPerspectiveMapper.identify_shape([tuple(p) for p in polygon])
                patch.update(shape_type=shape, orientation=orientation)
            row.update(patch)
            key = identity(row, c)
            custom.setdefault("edits", {}).setdefault(c, {})[key] = patch
            affected.append({"classe": c, "item_id": key})
        # Backup do estado e do sidecar antes de substituir somente derivados.
        backup = fv._backup_and_write_state(path, state)
        custom_path = sidecar_path(obra_dir, pav)
        if custom_path.is_file():
            import shutil
            shutil.copy2(custom_path, Path(backup).with_suffix(".geometry.bak"))
        fv._atomic_text(custom_path, json.dumps(custom, ensure_ascii=False, indent=2))
        return {"affected": affected, "backup": str(backup), "remaining": len(rows)}


def apply_window(window, obra_dir: Path, pav: str) -> None:
    """Mantém seleções manuais na entrada e na saída do microciclo canônico."""
    custom = load(obra_dir, pav)
    state = {"pilares": window.pillars_found, "slabs": window.slabs_found}
    apply_state(state, obra_dir, pav)
    # Recalcula contatos a partir do contorno escolhido, reutilizando os motores.
    report = getattr(window, "pavimento_pillar_report", {}) or {}
    for name in custom.get("deleted", {}).get("pilares", []):
        report.pop(name, None)
    for name, patch in custom.get("edits", {}).get("pilares", {}).items():
        pillar = next((p for p in window.pillars_found if p.get("name") == name), None)
        if pillar is None:
            continue
        entry = report.setdefault(name, dict(pillar))
        entry.update(deepcopy(patch))
        pts = patch["points"]
        entry["bbox"] = [min(p[0] for p in pts), min(p[1] for p in pts),
                         max(p[0] for p in pts), max(p[1] for p in pts)]
        entry["lajes"] = window._pillar_laje_entries(pts, window.slabs_found)
        entry.pop("face_beams", None)
    if report and custom.get("edits", {}).get("pilares"):
        window._enrich_pillar_report_with_beams(report, window.beams_found)
        from src.core.pillar_face_beams import materialize_face_beams_in_pillars
        materialize_face_beams_in_pillars(window.pillars_found, report,
            item_names=set(custom.get("edits", {}).get("pilares", {})))
        window.pavimento_pillar_report = report
