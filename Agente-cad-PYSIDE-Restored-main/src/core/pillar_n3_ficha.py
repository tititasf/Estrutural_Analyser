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

from scripts.pl_abcd_visual_nova import (
    expand_intervals_with_unidos,
    paineis_intervals_for_face,
    parse_paineis_unidos,
)


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
    # O desenho N3 usa paineis_intervals_* como malha efetiva acima de h1.
    # h2=244 e' apenas a chapa inteira: no modo NOVA ela pode ser duas
    # meias-chapas de 122, e C/D seguem regras diferentes conforme aberturas.
    raw_intervals = robot.get(f"paineis_intervals_{face}")
    if isinstance(raw_intervals, (list, tuple)):
        intervals = [_positive(value) for value in raw_intervals]
    elif raw_intervals is not None:
        intervals = [_positive(raw_intervals)]
    else:
        intervals = []
    intervals = [value for value in intervals if value > 0.0]
    contract = robot.get("_sa_mode_contract") or {}
    face_contract = (contract.get("faces") or {}).get(face) or {}
    if face in "CD" and face_contract and intervals:
        h1 = (_positive(robot.get(f"h1_geom_{face}"))
              or _positive(robot.get(f"h1_{face}")) or min(2.0, height))
        contract_void = (face_contract.get("vazio_topo") or {}).get("valor_cm") or 0.0
        residual_void = max(0.0, height - h1 - sum(intervals))
        intervals = paineis_intervals_for_face(
            face_id=face, height_cm=height, h1_cm=h1,
            top_void_cm=max(_positive(contract_void), residual_void),
        )
    if intervals:
        h1 = (_positive(robot.get(f"h1_geom_{face}"))
              or _positive(robot.get(f"h1_{face}")) or min(2.0, height))
        unidos = parse_paineis_unidos(robot, face)
        expanded, _ = expand_intervals_with_unidos(intervals, unidos)
        heights = [h1] + (expanded or intervals)
    else:
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
    # As aberturas são produzidas pelo payload da variante N3, não pela Fase 4.
    # Mantê-las na ficha é o que faz os boxes refletirem os detalhes do DXF.
    openings = {"left": [], "right": []}
    prefix = f"abertura_{face}_"
    for key, raw in sorted(robot.items()):
        if not str(key).startswith(prefix) or not isinstance(raw, dict):
            continue
        opening_width = _positive(raw.get("largura") or raw.get("width"))
        opening_depth = _positive(raw.get("altura") or raw.get("depth"))
        if opening_width <= 0 or opening_depth <= 0:
            continue
        lado = str(raw.get("origem_portal") or raw.get("lado") or raw.get("side") or "").lower()
        side = "right" if lado in {"direito", "right"} else "left"
        openings[side].append({
            "distance": _positive(raw.get("x_offset") or raw.get("distance")),
            "width": opening_width,
            "depth": opening_depth,
            "level": _positive(raw.get("nivel") or raw.get("level") or raw.get("y_rel")),
            "top_distance": _positive(raw.get("distancia_topo") or raw.get("top_distance")),
        })
    return {"panels": panels, "openings": openings}


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
        # A Fase 4 grava explicitamente ``0.0`` nas faces extras sem medida.
        # Para pilares especiais (mais de quatro arestas), essas faces ainda
        # precisam de uma malha editavel. Trate zero como "medida ausente" e
        # use a aresta/geometria N1; manter zero criaria um painel invalido no
        # pos-processamento do SA completo.
        face_width = _positive(robot.get(f"larg1_{face}")) or _positive(fallback_width)
        if face_width <= 0:
            face_width = width or 20.0
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
        "source": {
            "n1": True, "fase4": bool(robot), "human_override": False,
            "n3_variant": str(robot.get("_portal_n3_variant") or ""),
        },
    }
    if isinstance(saved, dict) and saved.get("schema") == SCHEMA:
        # A edicao humana e' autoridade somente nos blocos editaveis.
        for key in ("dimensions", "faces", "grades", "cima_contract"):
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
                if raw.get("element_level") is not None:
                    openings[side][-1]["element_level"] = _number(raw["element_level"])
                if raw.get("level_source") in {"sa", "sa_related", "n3_geometry", "manual",
                                               "abcd_sa", "abcd_manual", "abcd_inferred",
                                               "pillar_fallback"}:
                    openings[side][-1]["level_source"] = raw["level_source"]
                # O vínculo com a viga faz parte da ficha editável. Perdê-lo ao
                # validar faz a próxima execução N3 gerar aberturas anônimas.
                for key in ("n3_slot", "beam_name", "beam_dimension", "beam_behavior", "n3_kind"):
                    if raw.get(key):
                        openings[side][-1][key] = str(raw[key])
                if raw.get("geometry_level_gap_cm") is not None:
                    openings[side][-1]["geometry_level_gap_cm"] = _number(raw["geometry_level_gap_cm"])
        clean_faces[face] = {"panels": panels, "openings": openings}
        if raw_face.get("top_void_cm") is not None:
            clean_faces[face]["top_void_cm"] = _positive(raw_face["top_void_cm"])
        # Presenca da chave e' significativa: [] remove lajes sugeridas pelo N1.
        # Fichas antigas sem a chave continuam recebendo a sugestao automatica.
        if "slabs" in raw_face:
            raw_slabs = raw_face.get("slabs")
            if not isinstance(raw_slabs, list):
                raise ValueError(f"face {face}: lajes deve ser uma lista")
            clean_faces[face]["slabs"] = [
                {
                    "left_distance": _positive(raw.get("left_distance")),
                    "right_distance": _positive(raw.get("right_distance")),
                    "level": _number(raw.get("level")) if raw.get("level") is not None else None,
                    "top_distance": _positive(raw.get("top_distance")),
                    "width": _positive(raw.get("width")),
                    "height": _positive(raw.get("height")),
                }
                for raw in raw_slabs if isinstance(raw, dict)
            ]
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
        if "slabs" in data:
            patch[f"_portal_slabs_{face}"] = deepcopy(data["slabs"])
            first_slab = next((slab for slab in data["slabs"]
                               if slab["width"] > 0 and slab["height"] > 0), None)
            patch[f"vazio_laje_{face}"] = first_slab["height"] if first_slab else 0.0
            patch[f"rebaixo_laje_{face}"] = first_slab["top_distance"] if first_slab else 0.0
            patch[f"laje_{face}"] = max(0.0, first_slab["height"] - 2.0) if first_slab else 0.0
            patch[f"posicao_laje_{face}"] = 1.0 if first_slab else 0.0
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
                if opening.get("element_level") is not None:
                    # A cota absoluta e a distância ao topo prevalecem sobre
                    # y_rel legado; y_rel do motor começa acima da cinta h1.
                    # Nas faces C/D a malha termina ABAIXO do vazio superior.
                    # Usar a soma dos painéis deslocava a abertura para dentro
                    # da chapa pelo tamanho inteiro desse vazio (P10.C).
                    y_rel = max(0.0, dimensions["height"] - opening["top_distance"]
                                - opening["depth"] - (row_heights[0] if row_heights else 0.0))
                else:
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
                if opening.get("beam_name"):
                    patch[f"abertura_{face}_{opening_index}"]["_viga"] = opening["beam_name"]
                if opening.get("n3_slot"):
                    patch[f"abertura_{face}_{opening_index}"]["_origem"] = opening["n3_slot"]
                if opening.get("element_level") is not None:
                    patch[f"abertura_{face}_{opening_index}"]["_nivel_origem"] = opening["element_level"]
                opening_index += 1
    cima = ficha.get("cima_contract") if isinstance(ficha, dict) else None
    fields = (cima or {}).get("fields") if isinstance(cima, dict) else None
    especial = (fields or {}).get("especial") if isinstance(fields, dict) else None
    if isinstance(fields, dict) and not especial:
        comprimento = _positive(fields.get("comprimento_interno"))
        largura = _positive(fields.get("largura_interna"))
        if comprimento > 0:
            patch["comprimento"] = comprimento
        if largura > 0:
            patch["largura"] = largura

        grade_fields = fields.get("grades") if isinstance(fields.get("grades"), dict) else {}
        widths = [
            _positive(grade_fields.get(f"grade_{index}"))
            for index in range(1, 4)
        ]
        widths = [value for value in widths if value > 0]
        gaps = [
            _positive(grade_fields.get(f"distancia_{index}"))
            for index in range(1, len(widths))
        ]
        if widths:
            patch["_portal_cima_grade_layout"] = {
                "widths": widths,
                "gaps": gaps,
            }
            for index in range(1, 4):
                patch[f"grade_{index}"] = widths[index - 1] if index <= len(widths) else 0.0
                if index <= 2:
                    patch[f"distancia_{index}"] = gaps[index - 1] if index <= len(gaps) else 0.0

        screws = fields.get("parafusos") if isinstance(fields.get("parafusos"), list) else []
        for index in range(1, 8):
            patch[f"par_{index}_{index + 1}"] = (
                _positive(screws[index - 1]) if index <= len(screws) else 0.0
            )

        for side, key in (("a", "quadradinhos_a"), ("b", "quadradinhos_b")):
            groups = fields.get(key)
            if not isinstance(groups, list) and side == "a":
                groups = fields.get("quadradinhos")
            if not isinstance(groups, list):
                groups = []
            for grade_index in range(1, 4):
                values = groups[grade_index - 1] if grade_index <= len(groups) else []
                clean_values = [
                    _positive(value) for value in (values or [])
                    if value is not None and _positive(value) > 0
                ]
                patch[f"grade_{grade_index}_div_{side}"] = clean_values
    if isinstance(especial, dict) and especial:
        try:
            from src.core.cima_l_contract import build_cima_l_contract, flatten_cima_l_into_robot
            shape = fields.get("shape") if isinstance(fields.get("shape"), dict) else {}
            comprimento_1_externo = _positive(shape.get("comprimento_1_externo"))
            comprimento_2_externo = _positive(shape.get("comprimento_2_externo"))
            largura_1 = _positive(shape.get("largura_1"))
            largura_2 = _positive(shape.get("largura_2"))
            secao = {
                "externa_x": comprimento_2_externo,
                "interna_x": largura_1,
                "externa_y": comprimento_1_externo,
                "interna_y": max(0.1, comprimento_1_externo - largura_2),
            }
            saved_contract = {
                "schema": "pil.cima_l/v1",
                "classification": str(fields.get("classificacao_pilar") or "especial_l"),
                "shape": deepcopy(shape),
                "secao": secao,
                "arms": deepcopy(especial),
            }
            seed = dict(patch)
            seed["subtipo_pil"] = "L"
            seed["pilar_especial"] = {
                "cima": saved_contract,
                "secao_l": secao,
                "tipo_pilar_especial": "L",
            }
            built = build_cima_l_contract(seed) or {"schema": "pil.cima_l/v1", "arms": especial}
            patch.update(flatten_cima_l_into_robot({}, built))
        except Exception:
            patch["pilar_especial"] = {
                "cima": {
                    "classification": str(fields.get("classificacao_pilar") or "especial_l"),
                    "shape": deepcopy(fields.get("shape") or {}),
                    "arms": deepcopy(especial),
                },
                "tipo_pilar_especial": "L",
            }
    return patch


def apply_ficha_to_robot(robot: dict, ficha: dict | None) -> dict:
    result = deepcopy(robot or {})
    if ficha:
        result.update(robot_patch(ficha))
        contract = result.get("_sa_mode_contract")
        if isinstance(contract, dict):
            faces = contract.get("faces")
            if isinstance(faces, dict):
                for face, data in (ficha.get("faces") or {}).items():
                    if not isinstance(data, dict) or data.get("top_void_cm") is None:
                        continue
                    face_contract = faces.get(face)
                    if isinstance(face_contract, dict) and isinstance(face_contract.get("vazio_topo"), dict):
                        face_contract["vazio_topo"]["valor_cm"] = _positive(data["top_void_cm"])
    return result
