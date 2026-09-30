"""Contrato editavel N1 -> N3 para pilares no portal.

O estado do SA continua sendo a fonte estrutural. A ficha salva somente a
sobreposicao humana necessaria ao robo N3 e pode ser reaplicada depois que a
Fase 4 for regenerada. Nada deste modulo le ou grava ``project_data.vision``.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA = "pil.n3.web_ficha/v1"
KINDS = {"panel", "slab_void", "beam_void"}
HATCHES = {"none", "checker", "striped"}


def _number(value: Any, default: float = 0.0) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    return result if math.isfinite(result) else default


def _positive(value: Any, default: float = 0.0) -> float:
    return round(max(0.0, _number(value, default)), 4)


def _atomic_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink(missing_ok=True)
        except OSError:
            pass


def ficha_path(obra_dir: Path, pavimento: str, pilar: str) -> Path:
    safe_pav = "".join(c for c in str(pavimento) if c.isalnum() or c in "_- ").strip()
    safe_pilar = "".join(c for c in str(pilar) if c.isalnum() or c in "_-.").strip()
    if not safe_pav or not safe_pilar:
        raise ValueError("pavimento/pilar invalido")
    return obra_dir / "Fase-3_Interpretacao_Extracao" / "Pilares" / "portal_n3" / safe_pav / f"{safe_pilar}.json"


def _edge_lengths(points: list) -> list[float]:
    clean = [p for p in points if isinstance(p, (list, tuple)) and len(p) >= 2]
    if len(clean) > 1 and clean[0][:2] == clean[-1][:2]:
        clean = clean[:-1]
    lengths: list[float] = []
    for index, current in enumerate(clean):
        nxt = clean[(index + 1) % len(clean)]
        length = math.hypot(_number(nxt[0]) - _number(current[0]), _number(nxt[1]) - _number(current[1]))
        if length > 0.1:
            lengths.append(round(length, 2))
    return lengths


def _face_ids(pillar: dict, robot: dict) -> list[str]:
    special = str(pillar.get("formato") or pillar.get("classification") or "").lower()
    edge_count = len(_edge_lengths(pillar.get("points") or []))
    has_extra = any(_positive(robot.get(f"larg1_{face}")) for face in "EFGH")
    return list("ABCDEFGH" if has_extra or edge_count > 4 or "especial" in special or " l" in f" {special}" else "ABCD")


def _default_face(face: str, width: float, height: float, robot: dict) -> dict:
    heights = [_positive(robot.get(f"h{i}_{face}")) for i in range(1, 6)]
    heights = [value for value in heights if value > 0.0]
    if not heights:
        first = min(2.0, height)
        heights = [first]
        remaining = max(0.0, height - first)
        while remaining > 0.01:
            part = min(244.0, remaining)
            heights.append(round(part, 4))
            remaining -= part
    widths = [_positive(robot.get(f"larg{i}_{face}")) for i in range(1, 4)]
    widths = [value for value in widths if value > 0.0] or [width]
    panels = []
    for row, panel_height in enumerate(heights, start=1):
        for column, panel_width in enumerate(widths, start=1):
            panels.append({
                "id": f"{face}{row}-{column}", "row": row, "column": column,
                "distance": 0.0, "width": panel_width, "height": panel_height,
                "kind": "panel", "hatch": "none",
            })
    return {"panels": panels, "openings": {"left": [], "right": []}}


def build_ficha(pillar: dict, robot: dict | None = None, saved: dict | None = None, *, pavimento: str = "") -> dict:
    """Monta a ficha inicial usando primeiro Fase 4 e depois geometria N1."""
    robot = deepcopy(robot or {})
    edge_lengths = _edge_lengths(pillar.get("points") or [])
    length = _positive(robot.get("comprimento"), max(edge_lengths, default=60.0))
    width = _positive(robot.get("largura"), min(edge_lengths, default=20.0))
    height = _positive(robot.get("pd_pavimento_cm") or robot.get("altura"), 280.0)
    faces: dict[str, dict] = {}
    for index, face in enumerate(_face_ids(pillar, robot)):
        fallback_width = length if face in "AB" else width
        if index < len(edge_lengths):
            fallback_width = edge_lengths[index]
        face_width = _positive(robot.get(f"larg1_{face}"), fallback_width)
        faces[face] = _default_face(face, face_width, height, robot)
    ficha = {
        "schema": SCHEMA,
        "revision": 0,
        "pillar": str(pillar.get("name") or pillar.get("key") or robot.get("nome") or ""),
        "pavimento": pavimento,
        "special": len(faces) > 4,
        "top_view": {
            "points": deepcopy(pillar.get("points") or []),
            "classification": str(pillar.get("classification") or ""),
            "orientation": str(pillar.get("orientation") or ""),
        },
        "dimensions": {
            "length": length, "width": width, "height": height,
            "nivel_chegada": _number(robot.get("nivel_chegada"), 0.0),
            "nivel_saida": _number(robot.get("nivel_saida"), height),
        },
        "faces": faces,
        "grades": {
            "grade_1": _positive(robot.get("grade_1")),
            "distance_1": _positive(robot.get("distancia_1")),
            "grade_2": _positive(robot.get("grade_2")),
            "distance_2": _positive(robot.get("distancia_2")),
            "grade_3": _positive(robot.get("grade_3")),
            "vertical_slats": [],
            "horizontal_slats": [],
        },
        "source": {"n1": True, "fase4": bool(robot), "human_override": False},
    }
    if isinstance(saved, dict) and saved.get("schema") == SCHEMA:
        # A edicao humana e' autoridade somente nos blocos editaveis.
        for key in ("dimensions", "faces", "grades"):
            if isinstance(saved.get(key), dict):
                ficha[key] = deepcopy(saved[key])
        ficha["revision"] = int(saved.get("revision") or 0)
        ficha["source"]["human_override"] = True
    return validate_ficha(ficha)


def validate_ficha(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("ficha deve ser um objeto")
    result = deepcopy(payload)
    result["schema"] = SCHEMA
    dimensions = result.setdefault("dimensions", {})
    for key in ("length", "width", "height"):
        dimensions[key] = _positive(dimensions.get(key))
        if dimensions[key] <= 0:
            raise ValueError(f"dimensions.{key} deve ser maior que zero")
    dimensions["nivel_chegada"] = _number(dimensions.get("nivel_chegada"))
    dimensions["nivel_saida"] = _number(dimensions.get("nivel_saida"), dimensions["height"])
    faces = result.get("faces")
    if not isinstance(faces, dict) or not faces:
        raise ValueError("faces deve conter ao menos uma face")
    clean_faces = {}
    for face, raw_face in faces.items():
        face = str(face).upper()
        if face not in "ABCDEFGH" or not isinstance(raw_face, dict):
            continue
        panels = []
        for index, raw in enumerate(raw_face.get("panels") or [], start=1):
            if not isinstance(raw, dict):
                continue
            width = _positive(raw.get("width"))
            height = _positive(raw.get("height"))
            if width <= 0 or height <= 0:
                raise ValueError(f"face {face}: painel com largura/altura invalida")
            kind = str(raw.get("kind") or "panel")
            hatch = str(raw.get("hatch") or "none")
            panels.append({
                "id": str(raw.get("id") or f"{face}-{index}"),
                "row": max(1, int(_positive(raw.get("row"), 1))),
                "column": max(1, int(_positive(raw.get("column"), 1))),
                "distance": _positive(raw.get("distance")), "width": width, "height": height,
                "kind": kind if kind in KINDS else "panel",
                "hatch": hatch if hatch in HATCHES else "none",
            })
        openings = {"left": [], "right": []}
        raw_openings = raw_face.get("openings") or {}
        for side in openings:
            for raw in list(raw_openings.get(side) or [])[:4]:
                if not isinstance(raw, dict):
                    continue
                openings[side].append({
                    "distance": _positive(raw.get("distance")),
                    "width": _positive(raw.get("width")),
                    "depth": _positive(raw.get("depth")),
                    "level": _positive(raw.get("level")),
                    "top_distance": _positive(raw.get("top_distance")),
                })
        clean_faces[face] = {"panels": panels, "openings": openings}
    result["faces"] = clean_faces
    grades = result.setdefault("grades", {})
    for key in ("grade_1", "distance_1", "grade_2", "distance_2", "grade_3"):
        grades[key] = _positive(grades.get(key))
    grades["vertical_slats"] = [
        {"width": _positive(row.get("width")), "height": _positive(row.get("height")),
         "distance": _positive(row.get("distance"))}
        for row in (grades.get("vertical_slats") or []) if isinstance(row, dict)
    ]
    grades["horizontal_slats"] = [
        {"left_distance": _positive(row.get("left_distance")),
         "right_distance": _positive(row.get("right_distance")),
         "width": _positive(row.get("width")), "height": _positive(row.get("height"))}
        for row in (grades.get("horizontal_slats") or []) if isinstance(row, dict)
    ]
    result["grades"] = grades
    return result


def save_ficha(obra_dir: Path, pavimento: str, pilar: str, payload: dict) -> dict:
    clean = validate_ficha(payload)
    clean["pillar"] = pilar
    clean["pavimento"] = pavimento
    path = ficha_path(obra_dir, pavimento, pilar)
    previous = load_ficha(obra_dir, pavimento, pilar)
    clean["revision"] = int((previous or {}).get("revision") or 0) + 1
    clean["source"] = {"n1": True, "fase4": True, "human_override": True}
    _atomic_json(path, clean)
    return clean


def load_ficha(obra_dir: Path, pavimento: str, pilar: str) -> dict | None:
    path = ficha_path(obra_dir, pavimento, pilar)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) and data.get("schema") == SCHEMA else None


def materialize_pavimento(obra_dir: Path, pavimento: str) -> dict:
    """Materializa antecipadamente todas as fichas PIL de um snapshot SA/N1.

    Fichas humanas existentes nunca sao sobrescritas. Fichas automaticas podem
    ser reconstruidas a partir do snapshot/Fase 4 mais recente enquanto ainda
    estiverem em ``revision=0`` e sem ``human_override``.
    """
    obra_dir = Path(obra_dir)
    state_path = obra_dir / f"estado_{pavimento}.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"pavimento": pavimento, "total": 0, "created": 0, "refreshed": 0,
                "preserved": 0, "errors": [f"snapshot ausente/invalido: {state_path.name}"]}
    pillars = state.get("pilares") or []
    result = {"pavimento": pavimento, "total": len(pillars), "created": 0,
              "refreshed": 0, "preserved": 0, "errors": []}
    for pillar in pillars:
        if not isinstance(pillar, dict):
            continue
        name = str(pillar.get("name") or pillar.get("key") or "").strip()
        if not name:
            result["errors"].append("pilar sem nome")
            continue
        robot_path = obra_dir / "Fase-4_Sincronizacao" / "JSON_Pilares" / f"{name}.json"
        try:
            robot = json.loads(robot_path.read_text(encoding="utf-8"))
            if not isinstance(robot, dict):
                robot = {}
        except (OSError, json.JSONDecodeError):
            robot = {}
        previous = load_ficha(obra_dir, pavimento, name)
        is_human = bool(
            previous and (
                int(previous.get("revision") or 0) > 0
                or (previous.get("source") or {}).get("human_override")
            )
        )
        if is_human:
            result["preserved"] += 1
            continue
        try:
            generated = build_ficha(pillar, robot, None, pavimento=pavimento)
            generated["revision"] = 0
            generated["source"] = {"n1": True, "fase4": bool(robot), "human_override": False}
            _atomic_json(ficha_path(obra_dir, pavimento, name), generated)
            result["refreshed" if previous else "created"] += 1
        except (OSError, ValueError) as exc:
            result["errors"].append(f"{name}: {exc}")
    return result


def robot_patch(ficha: dict) -> dict:
    """Converte a ficha web para chaves ja consumidas pelo robo PL."""
    ficha = validate_ficha(ficha)
    dimensions = ficha["dimensions"]
    patch: dict[str, Any] = {
        "comprimento": dimensions["length"], "largura": dimensions["width"],
        "altura": dimensions["height"], "pd_pavimento_cm": dimensions["height"],
        "nivel_chegada": dimensions["nivel_chegada"], "nivel_saida": dimensions["nivel_saida"],
        "_portal_n3_ficha": {"schema": SCHEMA, "revision": ficha.get("revision", 0)},
    }
    grades = ficha["grades"]
    for source, target in (("grade_1", "grade_1"), ("grade_2", "grade_2"),
                           ("grade_3", "grade_3"), ("distance_1", "distancia_1"),
                           ("distance_2", "distancia_2")):
        patch[target] = grades[source]
    patch["sarrafos_verticais"] = deepcopy(grades["vertical_slats"])
    patch["sarrafos_horizontais"] = deepcopy(grades["horizontal_slats"])
    for face, data in ficha["faces"].items():
        panels = data["panels"]
        rows = sorted({panel["row"] for panel in panels})
        columns = sorted({panel["column"] for panel in panels})
        row_heights = [max(panel["height"] for panel in panels if panel["row"] == row) for row in rows]
        col_widths = [max(panel["distance"] + panel["width"] for panel in panels if panel["column"] == col) for col in columns]
        for index in range(1, 6):
            patch[f"h{index}_{face}"] = row_heights[index - 1] if index <= len(row_heights) else 0.0
        for index in range(1, 4):
            patch[f"larg{index}_{face}"] = col_widths[index - 1] if index <= len(col_widths) else 0.0
        patch[f"paineis_intervals_{face}"] = row_heights[1:] if len(row_heights) > 1 else row_heights
        patch[f"portal_cells_{face}"] = deepcopy(panels)
        total_width = sum(col_widths) or max((p["width"] for p in panels), default=0.0)
        total_height = sum(row_heights)
        opening_index = 1
        for side in ("left", "right"):
            for opening in data["openings"][side]:
                if opening["width"] <= 0 or opening["depth"] <= 0:
                    continue
                x_offset = opening["distance"] if side == "left" else max(
                    0.0, total_width - opening["distance"] - opening["width"]
                )
                y_rel = opening["level"] or max(
                    0.0, total_height - opening["top_distance"] - opening["depth"]
                )
                # Distancia zero fica dentro da borda correspondente. Distancia
                # positiva vira abertura central com x_offset explicito.
                side_robot = ("esquerdo" if side == "left" else "direito") if opening["distance"] <= 0 else "meio"
                patch[f"abertura_{face}_{opening_index}"] = {
                    "lado": side_robot, "largura": opening["width"], "altura": opening["depth"],
                    "y_rel": y_rel, "x_offset": x_offset,
                    "nivel": opening["level"], "distancia_topo": opening["top_distance"],
                    "distancia_borda": opening["distance"], "origem_portal": side,
                }
                opening_index += 1
    return patch


def apply_ficha_to_robot(robot: dict, ficha: dict | None) -> dict:
    result = deepcopy(robot or {})
    if ficha:
        result.update(robot_patch(ficha))
    return result
