#!/usr/bin/env python3
"""Gate G4 para LAJ: converte o N1 bruto do SA e compara com o N2.

Este harness lê exclusivamente ``slabs`` para o lado N1. ``slab_elements``
não é uma fonte válida aqui: ele pode conter a ficha N3 já enriquecida e,
portanto, dados aprendidos do gabarito N2/N4.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parents[1]
SCRIPTS_DIR = REPO_ROOT / "scripts"
for path in (REPO_ROOT, SCRIPTS_DIR, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from ficha_adapter import extrair_ficha_dinamica, get_recorte_path  # noqa: E402
from src.core.laje_n1_to_robot_ficha import n1_laje_to_robot_ficha  # noqa: E402
from src.core.sa_project_source import resolve_sa_project_from_db  # noqa: E402

DEFAULT_DB = Path("D:/Agente-cad-PYSIDE/project_data.vision")
DEFAULT_OUTPUT_ROOT = SCRIPT_DIR / "relatorios" / "convergencia_laj"
TOL_CM = 0.5
TOL_AREA_CM2 = 1.0

PROVENANCE = {
    "nome": "a",
    "numero": "a",
    "coordenadas": "a",
    "comprimento": "a",
    "largura": "a",
    "area_cm2": "a",
    "linhas_verticais": "b",
    "linhas_horizontais": "b",
    "obstaculos": "b",
    "modo_selecionado": "b",
    "unioes_nos_bordes": "b",
    "pontaletes": "b",
    "cotas_paineis": "c",
    "observacoes": "c",
}


def _json_value(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _same_pavimento(value: str, expected: str) -> bool:
    def key(text: str) -> str:
        return "".join(ch for ch in str(text).upper() if ch.isalnum())

    return key(value) == key(expected)


def load_raw_n1_slabs(
    db_path: str | Path,
    obra: str,
    pavimento: str,
    project_id: str | None = None,
) -> tuple[dict, dict[str, dict]]:
    """Carrega o N1 original; nunca consulta ``slab_elements``."""
    db = Path(db_path).resolve()
    project = resolve_sa_project_from_db(
        str(db), obra=obra, pavimento=pavimento, project_id=project_id
    )
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT * FROM slabs WHERE project_id=? ORDER BY name",
            (project["id"],),
        ).fetchall()
    finally:
        connection.close()

    slabs: dict[str, dict] = {}
    for row in rows:
        data = dict(row)
        data["points"] = _json_value(data.get("points_json"), [])
        data["links"] = _json_value(data.get("links_json"), {})
        extra = _json_value(data.get("extra_data_json"), {})
        if isinstance(extra, dict):
            data.update(extra)
        data["validated_fields"] = _json_value(
            data.get("validated_fields_json"), []
        )
        data["validated_link_classes"] = _json_value(
            data.get("validated_link_classes_json"), {}
        )
        name = str(data.get("name") or data.get("laje_name") or "").upper()
        if not name:
            continue
        data["name"] = name
        data["nome"] = name
        if "area_cm2" not in data and data.get("area") is not None:
            data["area_cm2"] = data["area"]
        slabs[name] = data
    return project, slabs


def load_dynamic_n2_slabs(
    db_path: str | Path,
    obra: str,
    pavimento: str,
) -> tuple[dict[str, dict], dict[str, str]]:
    db = Path(db_path).resolve()
    connection = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT id, obra_name, pavimento, classe, elemento_id, campos_json, "
            "recorte_path, confianca, status FROM reverse_eng_fichas "
            "WHERE obra_name=? AND classe='LAJ' ORDER BY id DESC",
            (obra,),
        ).fetchall()
    finally:
        connection.close()

    fichas: dict[str, dict] = {}
    sources: dict[str, str] = {}
    for raw in rows:
        row = dict(raw)
        item = str(row.get("elemento_id") or "").upper()
        if not item or item in fichas or not _same_pavimento(row.get("pavimento"), pavimento):
            continue
        row["campos_json"] = _json_value(row.get("campos_json"), {})
        recorte = get_recorte_path(item, "LAJ", row=row)
        if recorte is None or not recorte.is_file():
            fichas[item] = {"_extracao_erro": "recorte N2 ausente"}
            continue
        fichas[item] = extrair_ficha_dinamica(recorte, "LAJ", item)
        sources[item] = str(recorte.resolve())
    return fichas, sources


def _points(value: Any) -> list[tuple[float, float]]:
    result = []
    for point in value or []:
        try:
            result.append((float(point[0]), float(point[1])))
        except (TypeError, ValueError, IndexError):
            continue
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    return result


def _normalize_pose(
    points: list[tuple[float, float]], rotation: int
) -> list[tuple[float, float]]:
    angle = math.radians(rotation)
    cos_a, sin_a = round(math.cos(angle)), round(math.sin(angle))
    rotated = [
        (x * cos_a - y * sin_a, x * sin_a + y * cos_a)
        for x, y in points
    ]
    if not rotated:
        return []
    min_x = min(x for x, _ in rotated)
    min_y = min(y for _, y in rotated)
    return [(round(x - min_x, 6), round(y - min_y, 6)) for x, y in rotated]


def compare_outline(n1_value: Any, n2_value: Any) -> dict:
    n1_points = _points(n1_value)
    n2_points = _points(n2_value)
    if len(n1_points) < 3 or len(n2_points) < 3:
        return {
            "pass": False,
            "reason": "contorno ausente ou degenerado",
            "n1_vertices": len(n1_points),
            "n2_vertices": len(n2_points),
        }
    try:
        from shapely.geometry import Polygon

        target = Polygon(_normalize_pose(n2_points, 0)).buffer(0)
        candidates = []
        for rotation in (0, 90, 180, 270):
            polygon = Polygon(_normalize_pose(n1_points, rotation)).buffer(0)
            if polygon.is_empty or target.is_empty:
                continue
            candidates.append(
                {
                    "rotation": rotation,
                    "hausdorff_cm": polygon.hausdorff_distance(target),
                    "symmetric_difference_cm2": polygon.symmetric_difference(target).area,
                    "area_delta_cm2": abs(polygon.area - target.area),
                }
            )
        best = min(
            candidates,
            key=lambda item: (item["hausdorff_cm"], item["symmetric_difference_cm2"]),
        )
        return {
            "pass": best["hausdorff_cm"] <= TOL_CM
            and best["area_delta_cm2"] <= TOL_AREA_CM2,
            **{key: round(value, 4) for key, value in best.items()},
            "n1_vertices": len(n1_points),
            "n2_vertices": len(n2_points),
        }
    except (ImportError, ValueError):
        normalized_n2 = _normalize_pose(n2_points, 0)
        same = any(_normalize_pose(n1_points, rotation) == normalized_n2 for rotation in (0, 90, 180, 270))
        return {"pass": same, "reason": "fallback de vertices exatos"}


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _compare_number(n1: Any, n2: Any, tolerance: float = TOL_CM) -> dict:
    a, b = _number(n1), _number(n2)
    delta = None if a is None or b is None else abs(a - b)
    return {"pass": delta is not None and delta <= tolerance, "delta": delta}


def _line_signature(value: Any) -> list[dict]:
    result = []
    for line in value or []:
        if isinstance(line, dict):
            number = _number(line.get("value"))
            union = bool(line.get("is_union"))
        else:
            number = _number(line)
            union = False
        if number is not None:
            result.append({"value": number, "is_union": union})
    return sorted(result, key=lambda item: (item["value"], item["is_union"]))


def _compare_lines(n1: Any, n2: Any) -> dict:
    left, right = _line_signature(n1), _line_signature(n2)
    same = len(left) == len(right) and all(
        abs(a["value"] - b["value"]) <= TOL_CM
        and a["is_union"] == b["is_union"]
        for a, b in zip(left, right)
    )
    return {"pass": same, "n1": left, "n2": right}


def _canonical_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical_json(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_canonical_json(item) for item in value]
    if isinstance(value, float):
        return round(value, 3)
    return value


def compare_field(field: str, n1: dict, n2: dict) -> dict:
    a, b = n1.get(field), n2.get(field)
    if field == "coordenadas":
        detail = compare_outline(a, b)
    elif field in {"comprimento", "largura"}:
        detail = _compare_number(a, b)
    elif field == "area_cm2":
        detail = _compare_number(a, b, TOL_AREA_CM2)
    elif field in {"linhas_verticais", "linhas_horizontais"}:
        detail = _compare_lines(a, b)
    elif field == "unioes_nos_bordes":
        # O contrato histórico representa "não" como [] no conversor e false
        # no motor reverso; semanticamente são o mesmo valor.
        detail = {"pass": bool(a) == bool(b)}
    elif field == "pontaletes":
        detail = {"pass": _canonical_json(a or {}) == _canonical_json(b or {})}
    else:
        detail = {"pass": _canonical_json(a) == _canonical_json(b)}
    detail.update({"campo": field, "categoria": PROVENANCE[field]})
    if not detail["pass"] and "n1" not in detail:
        detail["n1"] = a
        detail["n2"] = b
    return detail


def diagnose_item(name: str, raw_n1: dict | None, n2: dict | None) -> dict:
    if raw_n1 is None or n2 is None or n2.get("_extracao_erro"):
        return {
            "item": name,
            "resultado": "BLOCKED",
            "motivo": "N1 ou N2 ausente/ilegivel",
            "erro_n2": (n2 or {}).get("_extracao_erro"),
            "campos": [],
        }
    converted = n1_laje_to_robot_ficha(raw_n1)
    fields = [compare_field(field, converted, n2) for field in PROVENANCE]
    required = [field for field in fields if field["categoria"] in {"a", "b"}]
    result = "PASS" if all(field["pass"] for field in required) else "FAIL"
    return {
        "item": name,
        "resultado": result,
        "fonte_n1": "slabs (SA bruto)",
        "anti_vazamento": "slab_elements proibido; aprendizagem N2/N4 não aplicada",
        "ficha_n1_convertida": converted,
        "campos": fields,
    }


def _write_markdown(report: dict, path: Path) -> None:
    summary = report["resumo"]
    lines = [
        "# G4 — Convergência N1×N2 de LAJ",
        "",
        f"- Obra/pavimento: `{report['obra']}` / `{report['pavimento']}`",
        f"- Projeto SA: `{report['fontes']['project_id']}`",
        f"- Resultado: **{summary['resultado']}**",
        f"- Itens: {summary['itens']} — PASS {summary['pass']} / FAIL {summary['fail']} / BLOCKED {summary['blocked']}",
        f"- Campos (a)+(b): {summary['campos_requeridos_pass']} PASS / {summary['campos_requeridos_fail']} FAIL",
        "",
        "| Item | G4 | Deltas (a/b) |",
        "|---|---:|---|",
    ]
    for item in report["itens"]:
        deltas = [
            f"{field['campo']}[{field['categoria']}]"
            for field in item.get("campos", [])
            if field["categoria"] in {"a", "b"} and not field["pass"]
        ]
        lines.append(f"| {item['item']} | {item['resultado']} | {', '.join(deltas) or '—'} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run(
    *,
    obra: str,
    pavimento: str,
    db_path: str | Path = DEFAULT_DB,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
    project_id: str | None = None,
) -> tuple[dict, Path]:
    project, n1 = load_raw_n1_slabs(db_path, obra, pavimento, project_id)
    n2, recortes = load_dynamic_n2_slabs(db_path, obra, pavimento)
    names = sorted(set(n1) | set(n2), key=lambda value: int(value[1:]) if value[1:].isdigit() else value)
    items = [diagnose_item(name, n1.get(name), n2.get(name)) for name in names]
    result_counts = Counter(item["resultado"] for item in items)
    required_fields = [
        field
        for item in items
        for field in item.get("campos", [])
        if field["categoria"] in {"a", "b"}
    ]
    generated = datetime.now().astimezone()
    run_id = generated.strftime("%Y%m%d_%H%M%S")
    db = Path(db_path).resolve()
    report = {
        "schema_version": 1,
        "gate": "G4",
        "gerado_em": generated.isoformat(),
        "run_id": run_id,
        "obra": obra,
        "pavimento": pavimento,
        "fontes": {
            "n1_db": str(db),
            "n1_db_sha256": hashlib.sha256(db.read_bytes()).hexdigest(),
            "n1_table": "slabs",
            "n1_forbidden_table": "slab_elements",
            "project_id": project["id"],
            "project_dxf": project["dxf_path"],
            "n2_recortes": recortes,
        },
        "resumo": {
            "resultado": "PASS" if result_counts["PASS"] == len(items) else "FAIL",
            "itens": len(items),
            "pass": result_counts["PASS"],
            "fail": result_counts["FAIL"],
            "blocked": result_counts["BLOCKED"],
            "campos_requeridos_pass": sum(field["pass"] for field in required_fields),
            "campos_requeridos_fail": sum(not field["pass"] for field in required_fields),
        },
        "itens": items,
    }
    run_dir = Path(output_root) / obra / pavimento / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    json_path = run_dir / "g4_conversao_n1_n2_laj.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_markdown(report, run_dir / "RELATORIO.md")
    return report, run_dir


def main() -> int:
    parser = argparse.ArgumentParser(description="G4 LAJ: convert(N1 SA bruto) vs N2")
    parser.add_argument("--obra", default="Obra_TREINO_1")
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--project-id", default=None)
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    args = parser.parse_args()
    report, run_dir = run(
        obra=args.obra,
        pavimento=args.pav,
        db_path=args.db,
        output_root=args.output_root,
        project_id=args.project_id,
    )
    print(json.dumps(report["resumo"], ensure_ascii=False, indent=2))
    print(f"Relatório: {run_dir}")
    return 0 if report["resumo"]["resultado"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
