"""Operacoes persistentes e atomicas do SA de fundos de viga.

As funcoes sao independentes da UI/HTTP para tambem poderem ser usadas por
rotinas operacionais. O ``estado_<pavimento>.json`` continua sendo a fonte de
verdade; SVG de camada sem proposta geometrica nunca e promovido.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


_MUTATION_LOCK = threading.RLock()
_LAYER_RE = re.compile(r"^c[123]$")
_BEAM_RE = re.compile(r"^[A-Za-z0-9_.-]+$")


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o664)
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"JSON estrutural invalido: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON estrutural invalido: {path.name}")
    return payload


def _override_path(obra_dir: Path, pavimento: str, beam: str) -> Path:
    if not _BEAM_RE.fullmatch(str(beam or "")):
        raise ValueError("nome de viga invalido")
    return Path(obra_dir) / ".portal_overrides" / "fv" / pavimento / f"{beam}.json"


def load_override(obra_dir: Path, pavimento: str, beam: str) -> dict[str, Any]:
    """Lê a camada de edição web, separada do schema imutável do SA."""
    path = _override_path(obra_dir, pavimento, beam)
    if not path.is_file():
        return {
            "schema": "portal.fv.override/v1", "beam": beam,
            "segments": {}, "notes": {"sa": "", "c1": "", "c2": "", "c3": ""},
            "annotations": [],
        }
    payload = _read_json(path)
    payload.setdefault("segments", {})
    payload.setdefault("notes", {"sa": "", "c1": "", "c2": "", "c3": ""})
    payload.setdefault("annotations", [])
    return payload


def _save_override(obra_dir: Path, pavimento: str, beam: str, payload: dict[str, Any]) -> Path:
    path = _override_path(obra_dir, pavimento, beam)
    payload.update({
        "schema": "portal.fv.override/v1", "beam": beam,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    })
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return path


def _positive(value: Any, label: str, *, zero: bool = False) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} invalido") from exc
    if not math.isfinite(result) or result < (0 if zero else 0.001):
        raise ValueError(f"{label} deve ser {'maior ou igual a zero' if zero else 'maior que zero'}")
    return round(result, 3)


def _finite(value: Any, label: str) -> float:
    """Coordenadas SVG podem ser negativas; exigimos apenas número finito."""
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} invalido") from exc
    if not math.isfinite(result):
        raise ValueError(f"{label} invalido")
    return round(result, 3)


def update_n3_override(
    obra_dir: Path, pavimento: str, beam: str, index: int, details: dict[str, Any],
) -> dict[str, Any]:
    """Persiste painéis/chanfros/aberturas manuais sem alterar o N1."""
    panels = []
    for number, panel in enumerate(details.get("panels") or [], 1):
        if not isinstance(panel, dict):
            raise ValueError("painel N3 invalido")
        panels.append({
            "index": number,
            "length_cm": _positive(panel.get("length_cm"), "comprimento do painel"),
            "width_cm": _positive(panel.get("width_cm"), "largura do painel"),
        })
    if not panels:
        raise ValueError("informe ao menos um painel N3")
    chamfers = []
    for chamfer in details.get("chamfers") or []:
        position = str((chamfer or {}).get("position") or "").lower()
        if position not in {"te", "fe", "td", "fd"}:
            raise ValueError("posicao do chanfro deve ser TE, FE, TD ou FD")
        chamfers.append({"position": position, "size_cm": _positive(chamfer.get("size_cm"), "tamanho do chanfro")})
    openings = []
    for opening in details.get("openings") or []:
        openings.append({
            "position_cm": _positive((opening or {}).get("position_cm"), "posicao da abertura", zero=True),
            "width_cm": _positive(opening.get("width_cm"), "largura da abertura"),
            "height_cm": _positive(opening.get("height_cm"), "altura da abertura"),
        })
    with _MUTATION_LOCK:
        payload = load_override(obra_dir, pavimento, beam)
        payload["segments"][str(index)] = {
            "panels": panels, "chamfers": chamfers, "openings": openings,
        }
        path = _save_override(obra_dir, pavimento, beam, payload)
    return {"beam": beam, "index": index, "override": str(path)}


def save_notes(obra_dir: Path, pavimento: str, beam: str, notes: dict[str, Any]) -> dict[str, str]:
    cleaned = {name: str(notes.get(name) or "")[:8000] for name in ("sa", "c1", "c2", "c3")}
    with _MUTATION_LOCK:
        payload = load_override(obra_dir, pavimento, beam)
        payload["notes"] = cleaned
        _save_override(obra_dir, pavimento, beam, payload)
    return cleaned


def add_annotation(obra_dir: Path, pavimento: str, beam: str, annotation: dict[str, Any]) -> dict[str, Any]:
    layer = str(annotation.get("layer") or "").lower()
    if layer not in {"sa", "c1", "c2", "c3"}:
        raise ValueError("camada do apontamento invalida")
    item = {
        "id": uuid.uuid4().hex,
        "layer": layer,
        "segment": str(annotation.get("segment") or "todos"),
        "x": _finite(annotation.get("x"), "coordenada x"),
        "y": _finite(annotation.get("y"), "coordenada y"),
        "element": str(annotation.get("element") or "elemento SVG")[:300],
        "text": str(annotation.get("text") or "").strip()[:4000],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if not item["text"]:
        raise ValueError("escreva a observacao do apontamento")
    with _MUTATION_LOCK:
        payload = load_override(obra_dir, pavimento, beam)
        payload["annotations"].append(item)
        _save_override(obra_dir, pavimento, beam, payload)
    return item


def delete_annotation(obra_dir: Path, pavimento: str, beam: str, annotation_id: str) -> None:
    with _MUTATION_LOCK:
        payload = load_override(obra_dir, pavimento, beam)
        before = len(payload["annotations"])
        payload["annotations"] = [row for row in payload["annotations"] if row.get("id") != annotation_id]
        if len(payload["annotations"]) == before:
            raise LookupError("apontamento nao encontrado")
        _save_override(obra_dir, pavimento, beam, payload)


def apply_n3_overrides(contract: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Aplica o sidecar no contrato N3 em memória antes do gerador certificado."""
    rows = contract.get("segments_rich") or contract.get("panels") or []
    for index, segment in enumerate(rows, 1):
        custom = (override.get("segments") or {}).get(str(index))
        if not custom or not isinstance(segment, dict):
            continue
        panels = [
            {"width": panel["length_cm"], "height": panel["width_cm"]}
            for panel in custom.get("panels") or []
        ]
        if not panels:
            continue
        for chamfer in custom.get("chamfers") or []:
            pos = chamfer.get("position")
            target = panels[0] if pos in {"te", "fe"} else panels[-1]
            target.setdefault("chanfros", {})[pos] = chamfer.get("size_cm")
        cumulative = 0.0
        for opening in custom.get("openings") or []:
            absolute = float(opening.get("position_cm") or 0)
            target = panels[-1]
            local = absolute - sum(float(p.get("width") or 0) for p in panels[:-1])
            cumulative = 0.0
            for panel in panels:
                width = float(panel.get("width") or 0)
                if absolute <= cumulative + width:
                    target, local = panel, absolute - cumulative
                    break
                cumulative += width
            target.setdefault("aberturas", []).append([
                round(max(0.0, local), 3), opening.get("height_cm"), opening.get("width_cm")
            ])
        segment["panels"] = panels
    contract["segments_rich"] = rows
    contract["panels"] = rows
    return contract


def _points(value: Any) -> list[list[float]]:
    result: list[list[float]] = []
    for point in value or []:
        if not isinstance(point, (list, tuple)) or len(point) < 2:
            continue
        try:
            x, y = float(point[0]), float(point[1])
        except (TypeError, ValueError):
            continue
        if math.isfinite(x) and math.isfinite(y):
            result.append([x, y])
    if len(result) > 1 and result[0] == result[-1]:
        result.pop()
    if len(result) < 3:
        raise ValueError("segmento precisa de ao menos 3 pontos validos")
    result.append(list(result[0]))
    return result


def _dimensions(points: list[list[float]]) -> tuple[float, float]:
    edges = [
        math.hypot(points[index + 1][0] - points[index][0], points[index + 1][1] - points[index][1])
        for index in range(len(points) - 1)
    ]
    longest = max(edges, default=0.0)
    area = abs(sum(
        points[index][0] * points[index + 1][1]
        - points[index + 1][0] * points[index][1]
        for index in range(len(points) - 1)
    )) / 2.0
    if longest <= 0 or area <= 0:
        raise ValueError("geometria do segmento possui area nula")
    return round(longest, 3), round(area / longest, 3)


def normalize_proposed_segments(proposals: Any) -> list[dict[str, Any]]:
    if not isinstance(proposals, list) or not proposals:
        raise ValueError("camada agentica sem segmentos estruturados")
    result = []
    for index, proposal in enumerate(proposals, 1):
        if not isinstance(proposal, dict):
            raise ValueError(f"proposta S{index} invalida")
        points = _points(proposal.get("points"))
        length, width = _dimensions(points)
        result.append({
            "index": index,
            "label": str(proposal.get("label") or index),
            "points": points,
            "length": length,
            "width": width,
        })
    return result


def proposal_segments(proposal_path: Path, beam: str) -> list[dict[str, Any]]:
    payload = _read_json(proposal_path)
    if str(payload.get("beam") or "").upper() != beam.upper():
        raise ValueError("a proposta pertence a outra viga")
    return normalize_proposed_segments(payload.get("proposed"))


def _state_path(obra_dir: Path, pavimento: str) -> Path:
    path = Path(obra_dir) / f"estado_{pavimento}.json"
    if not path.is_file():
        raise FileNotFoundError(f"estado SA ausente para {pavimento}")
    return path


def _backup_and_write_state(path: Path, state: dict[str, Any]) -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = path.parent / ".portal_backups" / "fv"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{path.name}.{stamp}.{uuid.uuid4().hex[:8]}.bak"
    shutil.copy2(path, backup)
    _atomic_text(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return backup


def restore_state_backup(backup: Path, state_path: Path) -> None:
    """Restaura atomically o estado anterior quando a materializacao visual falha."""
    backup = Path(backup)
    if not backup.is_file():
        raise FileNotFoundError("backup do estado SA indisponivel")
    _atomic_text(Path(state_path), backup.read_text(encoding="utf-8"))


def _raw_segments(state: dict[str, Any]) -> list[dict[str, Any]]:
    segmentos = state.setdefault("segmentos", {})
    fundo = segmentos.setdefault("fundo", [])
    if not isinstance(fundo, list):
        raise ValueError("estado SA sem lista segmentos.fundo valida")
    return fundo


def _new_raw_segment(beam: str, index: int, geometry: dict[str, Any], base: dict[str, Any] | None) -> dict[str, Any]:
    item = dict(base or {})
    item.update({
        "uid": item.get("uid") or f"fundo|web|{beam}|{index}|{uuid.uuid4().hex[:12]}",
        "beam_name": beam,
        "segment_label": str(index),
        "side": "Fundo",
        "behavior": "Fundo",
        "length": geometry["length"],
        "width": geometry["width"],
        "status": "valid",
        "atencao": "",
        "points": geometry["points"],
    })
    return item


def adopt_agent_layer(
    obra_dir: Path, pavimento: str, beam: str, html_path: Path, layer: str,
) -> dict[str, Any]:
    layer = layer.lower()
    if not _LAYER_RE.fullmatch(layer):
        raise ValueError("somente C1, C2 ou C3 podem substituir o SA")
    proposals_dir = html_path.parent / "propostas"
    proposal_json = proposals_dir / f"{beam}_qa_proposta_{layer}.json"
    proposal_svg = proposals_dir / f"{beam}_qa_proposta_{layer}.svg"
    proposed = proposal_segments(proposal_json, beam)
    if not proposal_svg.is_file() or "<svg" not in proposal_svg.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("camada agentica sem SVG valido")

    with _MUTATION_LOCK:
        state_path = _state_path(obra_dir, pavimento)
        state = _read_json(state_path)
        all_segments = _raw_segments(state)
        current = [row for row in all_segments if str(row.get("beam_name") or "").upper() == beam.upper()]
        if not current:
            raise LookupError("viga nao encontrada no estado SA")
        bases = {str(row.get("segment_label") or ""): row for row in current}
        replacements = [
            _new_raw_segment(beam, index, geometry, bases.get(str(index)))
            for index, geometry in enumerate(proposed, 1)
        ]
        first = next(index for index, row in enumerate(all_segments)
                     if str(row.get("beam_name") or "").upper() == beam.upper())
        others = [row for row in all_segments
                  if str(row.get("beam_name") or "").upper() != beam.upper()]
        others[first:first] = replacements
        state["segmentos"]["fundo"] = others

        backup = _backup_and_write_state(state_path, state)
    return {"beam": beam, "layer": layer, "segments": len(replacements),
            "adopted_segments": proposed, "backup": str(backup)}


def finalize_agent_adoption(html_path: Path, beam: str, layer: str,
                            segments: list[dict[str, Any]]) -> None:
    """Registra a origem adotada e remove propostas somente após o viewer existir."""
    adopted_meta = html_path.parent / "adotados" / f"{beam}_sa.json"
    _atomic_text(adopted_meta, json.dumps({
        "schema": "portal.fv.sa-adotado/v1",
        "beam": beam,
        "source_layer": layer,
        "adopted_at": datetime.now(timezone.utc).isoformat(),
        "segments": segments,
    }, ensure_ascii=False, indent=2) + "\n")
    proposals_dir = html_path.parent / "propostas"
    for candidate_layer in ("c1", "c2", "c3"):
        for suffix in ("svg", "json"):
            (proposals_dir / f"{beam}_qa_proposta_{candidate_layer}.{suffix}").unlink(missing_ok=True)


def delete_agent_layer(html_path: Path, beam: str, layer: str) -> dict[str, Any]:
    """Retira uma C1/C2/C3 da ficha, preservando os artefatos em lixeira recuperavel."""
    layer = layer.lower()
    if not _LAYER_RE.fullmatch(layer):
        raise ValueError("somente C1, C2 ou C3 podem ser excluidas")
    proposals_dir = html_path.parent / "propostas"
    candidates = [
        proposals_dir / f"{beam}_qa_proposta_{layer}.{suffix}"
        for suffix in ("svg", "json", "png")
    ]
    existing = [path for path in candidates if path.is_file()]
    if not existing:
        raise FileNotFoundError(f"camada {layer.upper()} nao encontrada para {beam}")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    trash = html_path.parent / ".portal_trash" / "camadas_agenticas" / f"{beam}_{layer}_{stamp}_{uuid.uuid4().hex[:8]}"
    trash.mkdir(parents=True, exist_ok=False)
    with _MUTATION_LOCK:
        for source in existing:
            shutil.move(str(source), trash / source.name)
    return {"beam": beam, "layer": layer, "removed": len(existing), "recoverable_at": str(trash)}


def update_segment(obra_dir: Path, pavimento: str, beam: str, index: int, points: Any) -> dict[str, Any]:
    geometry_points = _points(points)
    length, width = _dimensions(geometry_points)
    with _MUTATION_LOCK:
        path = _state_path(obra_dir, pavimento)
        state = _read_json(path)
        matches = [row for row in _raw_segments(state)
                   if str(row.get("beam_name") or "").upper() == beam.upper()
                   and int(str(row.get("segment_label") or "0")) == index]
        if len(matches) != 1:
            raise LookupError("segmento nao encontrado ou ambiguo")
        row = matches[0]
        row.update({"points": geometry_points, "length": length, "width": width,
                    "status": "valid", "atencao": ""})
        backup = _backup_and_write_state(path, state)
    return {"beam": beam, "index": index, "item_id": row.get("uid"),
            "length": length, "width": width, "backup": str(backup)}


def delete_segment(obra_dir: Path, pavimento: str, beam: str, index: int) -> dict[str, Any]:
    with _MUTATION_LOCK:
        path = _state_path(obra_dir, pavimento)
        state = _read_json(path)
        rows = _raw_segments(state)
        target = [row for row in rows
                  if str(row.get("beam_name") or "").upper() == beam.upper()
                  and int(str(row.get("segment_label") or "0")) == index]
        if len(target) != 1:
            raise LookupError("segmento nao encontrado ou ambiguo")
        removed = target[0]
        remaining_beam = [row for row in rows
                          if str(row.get("beam_name") or "").upper() == beam.upper()
                          and row is not removed]
        if not remaining_beam:
            raise ValueError("nao e permitido excluir o ultimo segmento da viga")
        state["segmentos"]["fundo"] = [row for row in rows if row is not removed]
        for new_index, row in enumerate(remaining_beam, 1):
            row["segment_label"] = str(new_index)
        backup = _backup_and_write_state(path, state)
    return {"beam": beam, "removed_item_id": removed.get("uid"),
            "segments": len(remaining_beam), "backup": str(backup)}


def rename_beam(obra_dir: Path, pavimento: str, beam: str, new_name: str) -> dict[str, Any]:
    """Renomeia o pai e todos os segmentos no estado, preservando backup."""
    new_name = str(new_name or "").strip().upper()
    if not _BEAM_RE.fullmatch(new_name):
        raise ValueError("novo nome de viga invalido")
    if new_name == beam.upper():
        return {"beam": beam, "new_name": new_name, "unchanged": True}
    with _MUTATION_LOCK:
        path = _state_path(obra_dir, pavimento)
        state = _read_json(path)
        rows = _raw_segments(state)
        if any(str(row.get("beam_name") or "").upper() == new_name for row in rows):
            raise ValueError("ja existe um fundo de viga com este nome")
        matches = [row for row in rows if str(row.get("beam_name") or "").upper() == beam.upper()]
        if not matches:
            raise LookupError("viga nao encontrada no estado SA")
        for row in matches:
            row["beam_name"] = new_name
        backup = _backup_and_write_state(path, state)
        old_override = _override_path(obra_dir, pavimento, beam)
        payload = _read_json(old_override) if old_override.is_file() else load_override(obra_dir, pavimento, beam)
        payload["source_beam"] = payload.get("source_beam") or beam
        _save_override(obra_dir, pavimento, new_name, payload)
        old_override.unlink(missing_ok=True)
    return {"beam": beam, "new_name": new_name, "segments": len(matches), "backup": str(backup)}


def rename_ficha_artifacts(html_path: Path, beam: str, new_name: str) -> Path:
    """Acompanha a renomeação nos artefatos mutáveis do pack do portal."""
    html_path = Path(html_path)
    target = html_path.with_name(f"{new_name}.html")
    if target.exists():
        raise ValueError("ja existe ficha com o novo nome")
    trash = html_path.parent / ".portal_backups" / "renames"
    trash.mkdir(parents=True, exist_ok=True)
    shutil.copy2(html_path, trash / f"{html_path.name}.{uuid.uuid4().hex[:8]}.bak")
    _atomic_text(target, html_path.read_text(encoding="utf-8", errors="replace").replace(beam, new_name))
    html_path.unlink()
    for folder in ("propostas", "adotados"):
        base = html_path.parent / folder
        if not base.is_dir():
            continue
        for source in list(base.glob(f"{beam}_*")):
            destination = source.with_name(new_name + source.name[len(beam):])
            if not destination.exists():
                shutil.move(str(source), destination)
    return target


def write_sa_visual(html_path: Path, beam: str, transform: Any, raw_segments: list[dict[str, Any]]) -> Path:
    """Materializa o SA editado sobre o estrutural completo, em coordenadas px."""
    svg = transform.svg.decode("utf-8", errors="strict")
    if "</svg>" not in svg:
        raise ValueError("SVG do estrutural limpo invalido")
    drawings = []
    for index, row in enumerate(raw_segments, 1):
        points = _points(row.get("points"))
        pixels = [transform.dxf_para_px(point[0], point[1]) for point in points]
        coords = " ".join(f"{x:.3f},{y:.3f}" for x, y in pixels)
        cx = sum(point[0] for point in pixels[:-1]) / max(1, len(pixels) - 1)
        cy = sum(point[1] for point in pixels[:-1]) / max(1, len(pixels) - 1)
        drawings.append(
            f'<g class="fv-web-sa-segment" data-fv-seg="{index}">'
            f'<polygon points="{coords}" fill="#4ea1ff" fill-opacity=".34" '
            f'stroke="#4ea1ff" stroke-width="2" vector-effect="non-scaling-stroke"/>'
            f'<text x="{cx:.3f}" y="{cy:.3f}" fill="#fff" font-size="13" '
            f'text-anchor="middle" dominant-baseline="middle">S{index}</text></g>'
        )
    overlay = '<g class="fv-web-human-sa-layer">' + "".join(drawings) + "</g>"
    svg = re.sub(r"</svg>\s*$", overlay + "</svg>", svg, count=1)
    target = html_path.parent / "adotados" / f"{beam}_sa.svg"
    _atomic_text(target, svg)
    return target
