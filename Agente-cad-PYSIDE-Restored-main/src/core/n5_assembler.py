from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer


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
        if t in ("TEXT", "MTEXT", "INSERT") and hasattr(entity.dxf, "insert"):
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

    copies = []
    for entity in src_doc.modelspace():
        try:
            if skip_fv_helpers and _is_fv_helper_entity(entity):
                continue
            copied = entity.copy()
            if dx or dy:
                copied.translate(dx, dy, 0)
            copies.append(copied)
        except Exception:
            continue
    if copies:
        importer.import_entities(copies, dst_doc.modelspace())
    importer.finalize()
    for dim in dst_doc.modelspace().query("DIMENSION"):
        try:
            if not getattr(dim.dxf, "geometry", None):
                dim.render()
        except Exception:
            continue
    return len(copies)


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


def _find_n3_preview(obra_dir: Path, classe: str, item_id: str) -> Path | None:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    pfx = _PREFIX.get(classe)
    if not pfx:
        return None
    candidates = _fv_aliases(item_id) if classe == "FV" else [item_id]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        path = fase6 / f"{pfx}{cand}.dxf"
        if path.exists():
            return path
    return None


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
) -> N5AssemblyResult:
    """Monta um DXF N5 consolidado a partir dos previews N3.

    Suportado agora:
      - LJ: copia os N3 nas coordenadas nativas, mantendo a montagem sobre o estrutural.
      - FV: empacota previews em grade de folhas, respeitando ordem natural dos itens.
    """
    obra_dir = Path(obra_dir)
    classe = classe.upper().strip()
    if classe not in ("LJ", "FV"):
        raise ValueError(f"N5 suporta apenas LJ e FV neste ciclo, recebido: {classe}")

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
    items: list[N5ItemResult] = []

    if classe == "LJ":
        for item_id in ids:
            src_path = _find_n3_preview(obra_dir, classe, item_id)
            if not src_path:
                items.append(N5ItemResult(item_id, "", "missing", "preview N3 ausente"))
                continue
            try:
                src_doc = ezdxf.readfile(str(src_path))
                count = _import_doc_entities(src_doc, dst)
                items.append(N5ItemResult(item_id, str(src_path), "ok", f"{count} entidades"))
            except Exception as exc:
                items.append(N5ItemResult(item_id, str(src_path), "error", str(exc)[:120]))

    else:  # FV
        max_row_w = float(row_width or 3200.0)
        margin = 120.0
        gap_x = 160.0
        gap_y = 190.0
        x_cursor = margin
        y_cursor = -margin
        row_h = 0.0
        for item_id in ids:
            src_path = _find_n3_preview(obra_dir, classe, item_id)
            if not src_path:
                items.append(N5ItemResult(item_id, "", "missing", "preview N3 ausente"))
                continue
            try:
                src_doc = ezdxf.readfile(str(src_path))
                bb = _entity_bbox(src_doc, skip_fv_helpers=True)
                if not bb:
                    items.append(N5ItemResult(item_id, str(src_path), "error", "bbox vazio"))
                    continue
                min_x, min_y, max_x, max_y = bb
                width = max(max_x - min_x, 1.0)
                height = max(max_y - min_y, 1.0)
                if x_cursor > margin and x_cursor + width > max_row_w:
                    x_cursor = margin
                    y_cursor -= row_h + gap_y
                    row_h = 0.0
                dx = x_cursor - min_x
                dy = y_cursor - max_y
                count = _import_doc_entities(src_doc, dst, dx=dx, dy=dy, skip_fv_helpers=True)
                items.append(
                    N5ItemResult(
                        item_id,
                        str(src_path),
                        "ok",
                        f"{count} entidades em x={x_cursor:.0f} y={y_cursor:.0f}",
                    )
                )
                x_cursor += width + gap_x
                row_h = max(row_h, height)
            except Exception as exc:
                items.append(N5ItemResult(item_id, str(src_path), "error", str(exc)[:120]))

    dst.saveas(str(out_path))
    manifest = {
        "classe": classe,
        "obra": obra_dir.name,
        "pavimento": pavimento,
        "output": str(out_path),
        "ok_count": sum(1 for item in items if item.status == "ok"),
        "missing_count": sum(1 for item in items if item.status != "ok"),
        "items": [item.__dict__ for item in items],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return N5AssemblyResult(classe, obra_dir.name, pavimento, out_path, manifest_path, items)

