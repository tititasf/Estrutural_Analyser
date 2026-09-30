from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

from scripts.visual_modes import apply_visual_mode, normalize_visual_mode


@dataclass
class N5ItemResult:
    item_id: str
    source: str
    status: str
    message: str = ""


@dataclass
class N5AssemblyResult:
    classe: str
    obra: str
    pavimento: str
    output_path: Path
    manifest_path: Path
    items: list[N5ItemResult]

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.items if item.status == "ok")

    @property
    def missing_count(self) -> int:
        return sum(1 for item in self.items if item.status != "ok")


_PREFIX = {
    "LJ": "LJ_preview_",
    "PL": "PL_preview_",
    "LV": "LV_preview_",
    "FV": "FV_preview_",
}

_SENTINEL_X = -5000.0


def natural_key(value: str) -> list[object]:
    parts = re.split(r"(\d+)", str(value).upper())
    return [int(p) if p.isdigit() else p for p in parts]


def _safe_name(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value).strip())
    return safe.strip("_") or "GERAL"


def _entity_extents(entity) -> tuple[float, float, float, float] | None:
    try:
        ext = bbox.extents([entity], fast=True)
        if ext.has_data:
            return (float(ext.extmin.x), float(ext.extmin.y), float(ext.extmax.x), float(ext.extmax.y))
    except Exception:
        pass

    try:
        t = entity.dxftype()
        if t == "LINE":
            return (
                min(float(entity.dxf.start.x), float(entity.dxf.end.x)),
                min(float(entity.dxf.start.y), float(entity.dxf.end.y)),
                max(float(entity.dxf.start.x), float(entity.dxf.end.x)),
                max(float(entity.dxf.start.y), float(entity.dxf.end.y)),
            )
        if t == "LWPOLYLINE":
            pts = list(entity.vertices())
            if pts:
                xs = [float(p[0]) for p in pts]
                ys = [float(p[1]) for p in pts]
                return (min(xs), min(ys), max(xs), max(ys))
        if t in ("TEXT", "MTEXT") and hasattr(entity.dxf, "insert"):
            ix = float(entity.dxf.insert.x)
            iy = float(entity.dxf.insert.y)
            width = 50.0
            height = 10.0
            if t == "TEXT":
                height = float(getattr(entity.dxf, "height", 10.0))
                width = len(str(getattr(entity.dxf, "text", ""))) * height * 0.8
            elif t == "MTEXT":
                width = float(getattr(entity.dxf, "width", 50.0))
                height = float(getattr(entity.dxf, "char_height", 10.0)) * 2
            
            return (
                ix,
                iy - height,
                ix + width,
                iy + height,
            )
        if t == "INSERT" and hasattr(entity.dxf, "insert"):
            return (
                float(entity.dxf.insert.x),
                float(entity.dxf.insert.y),
                float(entity.dxf.insert.x),
                float(entity.dxf.insert.y),
            )
        if t in ("CIRCLE", "ARC") and hasattr(entity.dxf, "center"):
            radius = float(getattr(entity.dxf, "radius", 0.0) or 0.0)
            cx = float(entity.dxf.center.x)
            cy = float(entity.dxf.center.y)
            return (cx - radius, cy - radius, cx + radius, cy + radius)
    except Exception:
        return None
    return None


def _is_fv_helper_entity(entity) -> bool:
    """FV previews may contain off-frame sentinels/boost lines used only for scoring layers."""
    ext = _entity_extents(entity)
    if not ext:
        return False
    return ext[2] < _SENTINEL_X


def _entity_bbox(doc, skip_fv_helpers: bool = False) -> tuple[float, float, float, float] | None:
    try:
        boxes = []
        for entity in doc.modelspace():
            if skip_fv_helpers and _is_fv_helper_entity(entity):
                continue
            ext = _entity_extents(entity)
            if ext:
                boxes.append(ext)
        if not boxes:
            return None
        return (
            min(b[0] for b in boxes),
            min(b[1] for b in boxes),
            max(b[2] for b in boxes),
            max(b[3] for b in boxes),
        )
    except Exception:
        return None


def _lj_panel_bbox(doc) -> tuple[float, float, float, float] | None:
    """Locate the slab outline, excluding dimensions that extend the item bbox."""
    candidates: list[tuple[float, tuple[float, float, float, float]]] = []
    for entity in doc.modelspace().query("LWPOLYLINE"):
        layer = str(entity.dxf.get("layer", "")).casefold()
        if layer not in {"paineis", "painéis", "3"}:
            continue
        ext = _entity_extents(entity)
        if not ext:
            continue
        width = max(ext[2] - ext[0], 0.0)
        height = max(ext[3] - ext[1], 0.0)
        if width > 0 and height > 0:
            candidates.append((width * height, ext))
    return max(candidates, key=lambda item: item[0])[1] if candidates else None


def _new_doc_like() -> ezdxf.EzDxf:
    doc = ezdxf.new("R2018")
    doc.header["$INSUNITS"] = 0
    return doc


def _import_doc_entities(
    src_doc,
    dst_doc,
    dx: float = 0.0,
    dy: float = 0.0,
    skip_fv_helpers: bool = False,
) -> int:
    original_count = len(src_doc.modelspace())
    importer = Importer(src_doc, dst_doc)
    try:
        importer.import_tables(["layers", "linetypes", "styles", "dimstyles"], replace=False)
    except Exception:
        pass
    try:
        block_names = [blk.name for blk in src_doc.blocks if not blk.name.startswith("*")]
        if block_names:
            importer.import_blocks(block_names, rename=False)
    except Exception:
        pass

    if skip_fv_helpers:
        for entity in list(src_doc.modelspace()):
            if _is_fv_helper_entity(entity):
                try:
                    src_doc.modelspace().delete_entity(entity)
                except Exception:
                    pass

    if dx or dy:
        for entity in src_doc.modelspace():
            try:
                entity.translate(dx, dy, 0)
            except Exception:
                pass

    # ezdxf.addons.Importer ignora MLINE. Copiamos essas entidades
    # explicitamente, junto com seus estilos, antes de importar o restante.
    mlines = list(src_doc.modelspace().query("MLINE"))
    for entity in mlines:
        style_name = str(entity.dxf.get("style_name", "Standard"))
        if style_name not in dst_doc.mline_styles:
            try:
                source_style = src_doc.mline_styles.get(style_name)
                target_style = dst_doc.mline_styles.new(style_name)
                target_style.dxf.flags = source_style.dxf.flags
                target_style.dxf.fill_color = source_style.dxf.fill_color
                target_style.dxf.start_angle = source_style.dxf.start_angle
                target_style.dxf.end_angle = source_style.dxf.end_angle
                for element in source_style.elements:
                    target_style.elements.append(
                        element.offset,
                        color=element.color,
                        linetype=element.linetype,
                    )
            except Exception:
                pass
        try:
            copied = entity.copy()
            target_style = dst_doc.mline_styles.get(style_name)
            copied.dxf.style_handle = target_style.dxf.handle
            dst_doc.modelspace().add_entity(copied)
            src_doc.modelspace().delete_entity(entity)
        except Exception:
            pass

    try:
        importer.import_modelspace(dst_doc.modelspace())
    except Exception:
        pass
    importer.finalize()
    for dim in dst_doc.modelspace().query("DIMENSION"):
        try:
            if not getattr(dim.dxf, "geometry", None):
                dim.render()
        except Exception:
            continue
    return original_count


def _fv_aliases(item_id: str) -> list[str]:
    value = str(item_id).strip()
    aliases = [value]
    clean = re.sub(r"_(Para|Passa)$", "", value, flags=re.I)
    aliases.append(clean)
    aliases.append(re.sub(r"[_\.]([A-D])$", "", clean, flags=re.I))
    aliases.append(re.sub(r"_fundo$", "", clean, flags=re.I))
    aliases.append(re.sub(r"[_\.]C[-_]\d+$", "", clean, flags=re.I))
    aliases.append(re.sub(r"[-_]\d+$", "", clean, flags=re.I))
    for alias in list(aliases):
        if alias and not alias.upper().endswith("_FUNDO"):
            aliases.append(f"{alias}_fundo")
    return aliases


def _find_n3_previews(obra_dir: Path, classe: str, item_id: str) -> list[Path]:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    pfx = _PREFIX.get(classe)
    if not pfx:
        return []

    if classe == "PL":
        combined = fase6 / f"PL_preview_{item_id}.dxf"
        if combined.exists():
            return [combined]
        zones = [
            fase6 / f"PL_{zone}_preview_{item_id}.dxf"
            for zone in ("CIMA", "ABCD", "GRADES", "EFGH")
        ]
        return [path for path in zones if path.exists()]

    candidates = _fv_aliases(item_id) if classe == "FV" else [item_id]
    if classe == "LV":
        clean = re.sub(r"_(Para|Passa)$", "", str(item_id), flags=re.I)
        candidates = [clean, clean.replace(".", "_")]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        path = fase6 / f"{pfx}{cand}.dxf"
        if path.exists():
            return [path]
    return []


def _find_n3_preview(obra_dir: Path, classe: str, item_id: str) -> Path | None:
    previews = _find_n3_previews(obra_dir, classe, item_id)
    return previews[0] if previews else None


def _discover_item_ids(obra_dir: Path, classe: str) -> list[str]:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    pfx = _PREFIX.get(classe)
    if not pfx or not fase6.exists():
        return []
    ids = []
    for path in fase6.glob(f"{pfx}*.dxf"):
        stem = path.stem.replace(pfx.rstrip("_"), "", 1).lstrip("_")
        if stem.endswith("_detail_test"):
            continue
        ids.append(stem)
    return sorted(set(ids), key=natural_key)


def assemble_n5(
    obra_dir: str | Path,
    classe: str,
    item_ids: Iterable[str] | None = None,
    pavimento: str = "",
    row_width: float | None = None,
    visual_mode: str = "NOVA",
    item_positions: dict[str, tuple[float, float]] | None = None,
) -> N5AssemblyResult:
    """Monta um DXF N5 consolidado a partir dos previews N3.

    Suporta LJ, PL, LV e FV. O modo visual e aplicado ao documento
    consolidado; LJ permanece sempre no perfil NOVA.
    """
    obra_dir = Path(obra_dir)
    classe = classe.upper().strip()
    if classe not in ("LJ", "PL", "LV", "FV"):
        raise ValueError(f"Classe N5 invalida: {classe}")
    visual_mode = "NOVA" if classe == "LJ" else normalize_visual_mode(visual_mode)

    ids = list(item_ids or [])
    if not ids:
        ids = _discover_item_ids(obra_dir, classe)
    ids = sorted(dict.fromkeys(str(i).strip() for i in ids if str(i).strip()), key=natural_key)

    out_dir = obra_dir / "Fase-6_Execucao_CAD" / "n5"
    out_dir.mkdir(parents=True, exist_ok=True)
    pav_tag = _safe_name(pavimento or "GERAL")
    out_path = out_dir / f"N5_{classe}_{pav_tag}.dxf"
    manifest_path = out_dir / f"N5_{classe}_{pav_tag}.json"

    dst = _new_doc_like()
    items = []

    if classe == "LJ":
        for item_id in ids:
            src_path = _find_n3_preview(obra_dir, classe, item_id)
            if not src_path:
                items.append(N5ItemResult(item_id, "", "missing", "preview N3 ausente"))
                continue
            try:
                src_doc = ezdxf.readfile(str(src_path))
                dx = dy = 0.0
                target = (item_positions or {}).get(item_id)
                panel_bbox = _lj_panel_bbox(src_doc)
                if target and panel_bbox:
                    dx = float(target[0]) - panel_bbox[0]
                    dy = float(target[1]) - panel_bbox[1]
                count = _import_doc_entities(
                    src_doc,
                    dst,
                    dx=dx,
                    dy=dy,
                    skip_fv_helpers=True,
                )
                pose_msg = (
                    f"; posição SA ({target[0]:.1f}, {target[1]:.1f})"
                    if target and panel_bbox
                    else ""
                )
                items.append(N5ItemResult(
                    item_id,
                    str(src_path),
                    "ok",
                    f"{count} entidades{pose_msg}",
                ))
            except Exception as exc:
                items.append(N5ItemResult(item_id, str(src_path), "error", str(exc)[:120]))
    else:  # PL, LV e FV: empacota cada item como uma folha/grupo.
        max_row_w = float(row_width or 2000.0)  # 20 metros
        margin = 150.0
        gap_x = 250.0
        gap_y = 300.0
        x_cursor = margin
        y_cursor = -margin
        row_h = 0.0
        for item_id in ids:
            src_paths = _find_n3_previews(obra_dir, classe, item_id)
            if not src_paths:
                items.append(N5ItemResult(item_id, "", "missing", "preview N3 ausente"))
                continue
            try:
                source_docs = [
                    (path, ezdxf.readfile(str(path)))
                    for path in src_paths
                ]
                boxes = [
                    _entity_bbox(doc, skip_fv_helpers=(classe == "FV"))
                    for _, doc in source_docs
                ]
                boxes = [box for box in boxes if box]
                if not boxes:
                    items.append(N5ItemResult(
                        item_id, str(src_paths[0]), "error", "bbox vazio"
                    ))
                    continue
                min_x = min(box[0] for box in boxes)
                min_y = min(box[1] for box in boxes)
                max_x = max(box[2] for box in boxes)
                max_y = max(box[3] for box in boxes)
                width = max(max_x - min_x, 1.0)
                height = max(max_y - min_y, 1.0)
                if x_cursor > margin and x_cursor + width > max_row_w:
                    x_cursor = margin
                    y_cursor -= row_h + gap_y
                    row_h = 0.0
                dx = x_cursor - min_x
                dy = y_cursor - max_y
                count = sum(
                    _import_doc_entities(
                        src_doc,
                        dst,
                        dx=dx,
                        dy=dy,
                        skip_fv_helpers=(classe == "FV"),
                    )
                    for _, src_doc in source_docs
                )
                items.append(
                    N5ItemResult(
                        item_id,
                        ";".join(str(path) for path in src_paths),
                        "ok",
                        f"{count} entidades em {len(src_paths)} preview(s)",
                    )
                )
                x_cursor += width + gap_x
                row_h = max(row_h, height)
            except Exception as exc:
                items.append(N5ItemResult(
                    item_id,
                    ";".join(str(path) for path in src_paths),
                    "error",
                    str(exc)[:120],
                ))

    apply_visual_mode(dst, visual_mode, classe)
    dst.saveas(str(out_path))
    import json
    manifest = {
        "classe": classe,
        "obra": obra_dir.name,
        "pavimento": pavimento,
        "visual_mode": visual_mode,
        "output": str(out_path),
        "ok_count": sum(1 for item in items if item.status == "ok"),
        "missing_count": sum(1 for item in items if item.status != "ok"),
        "items": [item.__dict__ for item in items],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return N5AssemblyResult(classe, obra_dir.name, pavimento, out_path, manifest_path, items)
