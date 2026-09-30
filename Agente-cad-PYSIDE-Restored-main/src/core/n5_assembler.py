from __future__ import annotations

import json
import logging
import re
import sqlite3
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import ezdxf
from ezdxf import bbox
from ezdxf.addons import Importer

from scripts.visual_modes import apply_visual_mode, normalize_visual_mode

_log = logging.getLogger("src.core.n5_assembler")


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
    extra_ids: list[str] = field(default_factory=list)

    @property
    def ok_count(self) -> int:
        return sum(1 for item in self.items if item.status == "ok")

    @property
    def missing_count(self) -> int:
        return sum(1 for item in self.items if item.status != "ok")

    @property
    def extra_count(self) -> int:
        return len(self.extra_ids)


_PREFIX = {
    "LJ": "LJ_preview_",
    "PL": "PL_preview_",
    "LV": "LV_preview_",
    "FV": "FV_preview_",
}

_CLASSE_DB_ALIASES = {
    "PL": ("PIL", "PL"),
    "LJ": ("LAJ", "LJ"),
    "FV": ("FV", "FUNDO"),
    "LV": ("LV",),
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


def _production_n3_dirs(
    obra_dir: Path, pavimento: str, visual_mode: str | None = None,
) -> list[Path]:
    """Pastas N3 do SA em ordem mais recente primeiro.

    O runner web materializa cada rodada em ``production_sa/<pav>/<run>/n3/dxf``.
    O N5 deve consumir a última rodada do pavimento, sem exigir uma cópia legada
    na raiz de Fase-6.
    """
    if not pavimento:
        return []
    root = obra_dir / "Fase-6_Execucao_CAD" / "production_sa" / pavimento
    if not root.is_dir():
        return []
    requested = normalize_visual_mode(visual_mode) if visual_mode else None
    paths = sorted(
        (path for path in root.glob("*/n3/dxf") if path.is_dir()),
        key=lambda path: path.parent.parent.name,
        reverse=True,
    )
    if not requested:
        return paths
    return [path for path in paths if _run_visual_mode(path.parent.parent) == requested]


def _run_visual_mode(run: Path) -> str:
    try:
        payload = json.loads((run / "production_manifest.json").read_text(encoding="utf-8"))
        return normalize_visual_mode(
            payload.get("visual_mode") or (payload.get("n3") or {}).get("visual_mode")
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return "NOVA"


def _production_pillar_runs(
    obra_dir: Path, pavimento: str, visual_mode: str | None = None,
) -> list[Path]:
    """Pastas ``n3/pil`` publicadas, da mais recente para a mais antiga."""
    if not pavimento:
        return []
    root = obra_dir / "Fase-6_Execucao_CAD" / "production_sa" / pavimento
    if not root.is_dir():
        return []
    requested = normalize_visual_mode(visual_mode) if visual_mode else None
    paths = sorted(
        (path for path in root.glob("*/n3/pil") if path.is_dir()),
        key=lambda path: path.parent.parent.name,
        reverse=True,
    )
    if not requested:
        return paths
    return [path for path in paths if _run_visual_mode(path.parent.parent) == requested]


def _pillar_preview_paths(base: Path, item_id: str) -> list[Path]:
    """Contrato visual do N5 PL: uma linha com cinco vistas, nesta ordem."""
    return [
        base / "para" / f"PL_CIMA_preview_{item_id}.dxf",
        base / "passa" / f"PL_ABCD_preview_{item_id}.dxf",
        base / "passa" / f"PL_GRADES_preview_{item_id}.dxf",
        base / "para" / f"PL_ABCD_preview_{item_id}.dxf",
        base / "para" / f"PL_GRADES_preview_{item_id}.dxf",
    ]


def _find_pillar_n3_previews(
    obra_dir: Path, item_id: str, pavimento: str, visual_mode: str = "NOVA",
) -> list[Path]:
    """Resolve as cinco vistas do pilar sem misturar rodadas nem fallbacks.

    ``n3_variants`` e o contrato consumido pelas cinco abas do viewer web e
    pode conter uma regeneracao granular posterior a ultima rodada completa.
    Ele tem prioridade somente quando as cinco vistas estao presentes. Uma
    rodada parcial nunca e completada com arquivos antigos; arquivos soltos da
    raiz sao o ultimo fallback legado.
    """
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    visual_mode = normalize_visual_mode(visual_mode)
    mode_variants = fase6 / "n3_modes" / visual_mode / "pilares"
    paths = _pillar_preview_paths(mode_variants, item_id)
    if all(path.is_file() for path in paths):
        return paths
    if any(path.is_file() for path in paths):
        return []

    if visual_mode == "NOVA":
        variants = fase6 / "n3_variants"
        paths = _pillar_preview_paths(variants, item_id)
        if all(path.is_file() for path in paths):
            return paths
        if any(path.is_file() for path in paths):
            return []

    for run in _production_pillar_runs(obra_dir, pavimento, visual_mode):
        paths = _pillar_preview_paths(run, item_id)
        if all(path.is_file() for path in paths):
            return paths
        if any(path.is_file() for path in paths):
            return []

    if visual_mode == "INI":
        return []

    item_published = False
    for run in _production_pillar_runs(obra_dir, pavimento, visual_mode):
        paths = _pillar_preview_paths(run, item_id)
        if any(path.is_file() for path in paths):
            item_published = True
        if all(path.is_file() for path in paths):
            return paths
    if item_published:
        return []

    combined = fase6 / f"PL_preview_{item_id}.dxf"
    if combined.is_file():
        return [combined]
    legacy = [
        fase6 / f"PL_{zone}_preview_{item_id}.dxf"
        for zone in ("CIMA", "ABCD", "GRADES", "EFGH")
    ]
    legacy_found = [path for path in legacy if path.is_file()]
    if legacy_found:
        return legacy_found

    fase4 = obra_dir / "Fase-4_Detalhamento"
    for candidate in (
        fase4 / f"PL_preview_{item_id}.dxf",
        fase4 / f"PIL_{item_id}.dxf",
        fase4 / f"PL_{item_id}.dxf",
    ):
        if candidate.is_file():
            return [candidate]
    recortes = obra_dir / "Fase-2_Triagem" / "recortes_web"
    if recortes.is_dir():
        for db_cls in _CLASSE_DB_ALIASES["PL"]:
            matches = list(recortes.rglob(f"{db_cls}_{item_id}.dxf"))
            if matches:
                return [matches[0]]
    return []


def _state_pillar_ids(obra_dir: Path, pavimento: str) -> list[str]:
    """Identidades atuais do SA; evita limitar PL por ficha DB desatualizada."""
    if not pavimento:
        return []
    state = obra_dir / f"estado_{pavimento}.json"
    if not state.is_file():
        return []
    try:
        payload = json.loads(state.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    from src.core.pillar_sa_review import apply_state, eligible
    payload = apply_state(payload, obra_dir, pavimento)
    result = []
    for pillar in payload.get("pilares", []):
        if not isinstance(pillar, dict) or not eligible(pillar):
            continue
        item_id = str(pillar.get("name") or pillar.get("item_id") or "").strip()
        if item_id:
            result.append(item_id)
    return sorted(dict.fromkeys(result), key=natural_key)


def _find_n3_previews(
    obra_dir: Path, classe: str, item_id: str, pavimento: str = "",
    visual_mode: str = "NOVA",
) -> list[Path]:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    pfx = _PREFIX.get(classe)
    if not pfx:
        return []

    if classe == "PL":
        return _find_pillar_n3_previews(obra_dir, item_id, pavimento, visual_mode)

    candidates = _fv_aliases(item_id) if classe == "FV" else [item_id]
    if classe == "LV":
        clean = re.sub(r"_(Para|Passa)$", "", str(item_id), flags=re.I)
        candidates = [clean, clean.replace(".", "_")]
    seen: set[str] = set()
    for cand in candidates:
        if not cand or cand in seen:
            continue
        seen.add(cand)
        # Os viewers FV/LJ resolvem o N3 por rodada de produção, item a item.
        # O N5 precisa usar a mesma fonte autoritativa; cópias históricas na
        # raiz da Fase-6 ficam apenas como fallback para obras ainda não
        # publicadas pelo runner web. Isso também impede que a prancha de lajes
        # misture dimensões antigas com o SA/N3 atualmente exibido no portal.
        if classe in {"FV", "LJ"}:
            for prod_dir in _production_n3_dirs(obra_dir, pavimento, visual_mode):
                produced = prod_dir / f"{pfx}{cand}.dxf"
                if produced.exists():
                    return [produced]
            if normalize_visual_mode(visual_mode) == "INI":
                continue
        path = fase6 / f"{pfx}{cand}.dxf"
        if path.exists():
            return [path]
        # P5: Busca secundária em Fase-4_Detalhamento e Fase-2_Triagem/recortes_web (itens do motor / manuais)
        fase4 = obra_dir / "Fase-4_Detalhamento" / f"{pfx}{cand}.dxf"
        if fase4.exists():
            return [fase4]
        for db_cls in _CLASSE_DB_ALIASES.get(classe, (classe,)):
            fase4_cls = obra_dir / "Fase-4_Detalhamento" / f"{db_cls}_{cand}.dxf"
            if fase4_cls.exists():
                return [fase4_cls]
            recortes_dir = obra_dir / "Fase-2_Triagem" / "recortes_web"
            if recortes_dir.exists():
                matches = list(recortes_dir.rglob(f"{db_cls}_{cand}.dxf"))
                if matches:
                    return [matches[0]]
    return []


def _find_n3_preview(
    obra_dir: Path, classe: str, item_id: str, pavimento: str = "",
    visual_mode: str = "NOVA",
) -> Path | None:
    previews = _find_n3_previews(obra_dir, classe, item_id, pavimento, visual_mode)
    return previews[0] if previews else None


def _discover_item_ids(obra_dir: Path, classe: str, pavimento: str = "") -> list[str]:
    fase6 = obra_dir / "Fase-6_Execucao_CAD"
    pfx = _PREFIX.get(classe)
    if not pfx:
        return []
    ids = []
    if fase6.exists():
        for path in fase6.glob(f"{pfx}*.dxf"):
            stem = path.stem.replace(pfx.rstrip("_"), "", 1).lstrip("_")
            if stem.endswith("_detail_test"):
                continue
            ids.append(stem)

    if classe in {"FV", "LJ"}:
        prod_dirs = _production_n3_dirs(obra_dir, pavimento)
        if prod_dirs:
            for path in prod_dirs[0].glob(f"{pfx}*.dxf"):
                stem = path.stem.replace(pfx.rstrip("_"), "", 1).lstrip("_")
                if not stem.endswith("_detail_test"):
                    ids.append(stem)

    if classe == "PL":
        state_ids = _state_pillar_ids(obra_dir, pavimento)
        if state_ids:
            ids.extend(state_ids)
        else:
            # Sem estado, descobre apenas conjuntos completos da rodada mais
            # recente que publicou pilares. Nao mistura inventarios de rodadas.
            for run in _production_pillar_runs(obra_dir, pavimento):
                run_ids = []
                for path in (run / "para").glob("PL_CIMA_preview_*.dxf"):
                    item_id = path.stem.removeprefix("PL_CIMA_preview_")
                    if all(candidate.is_file() for candidate in _pillar_preview_paths(run, item_id)):
                        run_ids.append(item_id)
                if run_ids:
                    ids.extend(run_ids)
                    break

    # P5: Descobrir também em Fase-4_Detalhamento e recortes_web (itens manuais sem N3 em fase6)
    fase4 = obra_dir / "Fase-4_Detalhamento"
    if fase4.exists():
        for path in fase4.glob(f"{pfx}*.dxf"):
            stem = path.stem.replace(pfx.rstrip("_"), "", 1).lstrip("_")
            if not stem.endswith("_detail_test"):
                ids.append(stem)
    recortes_dir = obra_dir / "Fase-2_Triagem" / "recortes_web"
    if recortes_dir.exists():
        for db_cls in _CLASSE_DB_ALIASES.get(classe, (classe,)):
            for path in recortes_dir.rglob(f"{db_cls}_*.dxf"):
                stem = path.stem.replace(f"{db_cls}_", "", 1)
                if stem and not stem.endswith("_detail_test"):
                    ids.append(stem)

    return sorted(set(ids), key=natural_key)


def _get_db_expected_item_ids(obra_dir: Path, classe: str, pavimento: str, db_path: str | Path | None) -> set[str]:
    """Elemento_ids no banco SA que o N5 DEVE incluir (escape hatch + aprovados).

    Usa só `reverse_eng_fichas` — tem pavimento e é a fonte com UNIQUE por item.
    `reverse_eng_recortes` não tem coluna pavimento no schema oficial; consultar
    lá com SELECT pavimento quebrava a completude em silêncio (except genérico).

    Status `manual` entra de propósito: item criado pelo laço web (P3) precisa
    aparecer na prancha; se o preview N3 sumiu, vira missing_count alto (P5).
    """
    if db_path is None:
        return set()
    caminho_db = Path(db_path)
    if not caminho_db.is_file():
        return set()
    obra_name = obra_dir.name
    db_classes = _CLASSE_DB_ALIASES.get(classe, (classe,))
    placeholders = ",".join("?" for _ in db_classes)
    expected: set[str] = set()
    try:
        from src.core.obra_identity import normalizar_pavimento
    except Exception:  # pragma: no cover - fallback se import falhar em harnesss isolados
        normalizar_pavimento = lambda p: p  # type: ignore[assignment]
    pav_norm = normalizar_pavimento(pavimento) or str(pavimento or "").strip()
    status_ok = {"aprovado", "manual", "manual_sel", "auto_aprovado", "motor", "pendente", "draft"}
    try:
        conn = sqlite3.connect(str(caminho_db))
        try:
            res = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='reverse_eng_fichas'"
            ).fetchone()
            if not res:
                return set()
            sql = (
                "SELECT elemento_id, pavimento, status FROM reverse_eng_fichas "
                f"WHERE obra_name=? AND UPPER(classe) IN ({placeholders})"
            )
            params = [obra_name] + [c.upper() for c in db_classes]
            for row in conn.execute(sql, params).fetchall():
                st = str(row[2] or "").lower()
                if st not in status_ok:
                    continue
                if pav_norm and pav_norm not in ("GERAL", ""):
                    row_pav = normalizar_pavimento(row[1]) or str(row[1] or "").strip()
                    if row_pav != pav_norm:
                        continue
                eid = str(row[0] or "").strip()
                if eid:
                    expected.add(eid)
        finally:
            conn.close()
    except Exception as exc:
        _log.warning("falha ao consultar completude no banco SA %s: %s", caminho_db, exc)
    return expected


def _get_db_lj_item_layouts(
    obra_dir: Path, pavimento: str, db_path: str | Path | None,
) -> dict[str, tuple[float, float, float | None, float | None]]:
    """Retorna ancora e dimensoes logicas STOG de cada laje do pavimento.

    `coordenadas` na ficha sao locais ao item; `_stog_pose` e a fonte canonica
    usada pela tela desktop para recolocar cada preview no pavimento. As
    dimensoes logicas permitem distinguir o corpo principal de degraus que
    ultrapassam o bbox (L318/L319), sem hardcode por item.
    """
    if db_path is None:
        return {}
    caminho_db = Path(db_path)
    if not caminho_db.is_file():
        return {}
    try:
        from src.core.obra_identity import normalizar_pavimento
    except Exception:  # pragma: no cover - fallback de harness isolado
        normalizar_pavimento = lambda p: p  # type: ignore[assignment]
    pav_norm = normalizar_pavimento(pavimento) or str(pavimento or "").strip()
    layouts: dict[str, tuple[float, float, float | None, float | None]] = {}
    try:
        conn = sqlite3.connect(str(caminho_db))
        try:
            columns = {
                str(row[1])
                for row in conn.execute("PRAGMA table_info(reverse_eng_fichas)").fetchall()
            }
            if "campos_json" not in columns:
                return {}
            rows = conn.execute(
                "SELECT elemento_id, pavimento, campos_json FROM reverse_eng_fichas "
                "WHERE obra_name=? AND UPPER(classe) IN ('LAJ','LJ')",
                (obra_dir.name,),
            ).fetchall()
            for elemento_id, row_pavimento, campos_json in rows:
                row_pav = normalizar_pavimento(row_pavimento) or str(row_pavimento or "").strip()
                if pav_norm and pav_norm not in ("GERAL", "") and row_pav != pav_norm:
                    continue
                try:
                    campos = json.loads(campos_json or "{}")
                    coords = campos.get("coordenadas") or []
                    valid_coords = [
                        (float(point[0]), float(point[1]))
                        for point in coords
                        if isinstance(point, (list, tuple)) and len(point) >= 2
                    ]
                    pose = campos.get("_stog_pose") or {}
                    if valid_coords:
                        raw_x = min(point[0] for point in valid_coords)
                        raw_y = min(point[1] for point in valid_coords)
                        raw_width = max(point[0] for point in valid_coords) - raw_x
                        raw_height = max(point[1] for point in valid_coords) - raw_y
                    else:
                        raw_x = raw_y = 0.0
                        raw_width = raw_height = 0.0
                    if pose and abs(raw_x) <= 0.5 and abs(raw_y) <= 0.5:
                        x = float(pose["x"])
                        y = float(pose["y"])
                    elif valid_coords:
                        x, y = raw_x, raw_y
                    else:
                        x = float(pose["x"])
                        y = float(pose["y"])
                except (TypeError, ValueError, KeyError, json.JSONDecodeError):
                    continue
                eid = str(elemento_id or "").strip()
                if eid:
                    width = float(campos.get("comprimento") or raw_width or 0.0) or None
                    height = float(campos.get("largura") or raw_height or 0.0) or None
                    layouts[eid] = (x, y, width, height)
        finally:
            conn.close()
    except Exception as exc:
        _log.warning("falha ao consultar posicoes LJ no banco SA %s: %s", caminho_db, exc)
    return layouts


def _get_db_lj_item_positions(
    obra_dir: Path, pavimento: str, db_path: str | Path | None,
) -> dict[str, tuple[float, float]]:
    """Compatibilidade: retorna somente a ancora global de cada laje."""
    return {
        item_id: (layout[0], layout[1])
        for item_id, layout in _get_db_lj_item_layouts(
            obra_dir, pavimento, db_path,
        ).items()
    }


def _lj_coherent_translations(
    sources: list[tuple[str, object, tuple[float, float, float, float]]],
    layouts: dict[str, tuple[float, float, float | None, float | None]],
) -> dict[str, tuple[float, float]]:
    """Escolhe a ancora de cada eixo que preserva a coesao do pavimento.

    A pose N2 descreve o canto do corpo logico da laje. Um N3 escalonado pode
    ultrapassar esse corpo em apenas um lado; alinhar sempre o minimo do bbox
    desloca o conjunto (L318: 49 cm; L319: 36 cm). A translacao dominante do
    pavimento e estimada pelas ancoras inferiores/esquerdas e, por eixo,
    escolhemos entre alinhar minimo ou maximo a opcao mais proxima desse
    consenso. Assim o contorno N3 permanece intacto e as folgas estruturais
    entre itens sao preservadas.
    """
    base_dx: list[float] = []
    base_dy: list[float] = []
    for item_id, _doc, panel_bbox in sources:
        layout = layouts.get(item_id)
        if layout is None:
            continue
        base_dx.append(float(layout[0]) - panel_bbox[0])
        base_dy.append(float(layout[1]) - panel_bbox[1])
    if not base_dx or not base_dy:
        return {}
    consensus_dx = float(statistics.median(base_dx))
    consensus_dy = float(statistics.median(base_dy))
    result: dict[str, tuple[float, float]] = {}
    for item_id, _doc, panel_bbox in sources:
        layout = layouts.get(item_id)
        if layout is None:
            continue
        x, y, width, height = layout
        dx_candidates = [float(x) - panel_bbox[0]]
        dy_candidates = [float(y) - panel_bbox[1]]
        if width:
            dx_candidates.append(float(x) + width - panel_bbox[2])
        if height:
            dy_candidates.append(float(y) + height - panel_bbox[3])
        result[item_id] = (
            min(dx_candidates, key=lambda value: abs(value - consensus_dx)),
            min(dy_candidates, key=lambda value: abs(value - consensus_dy)),
        )
    return result


def n3_mode_readiness(obra_dir: Path, classe: str, pavimento: str, visual_mode: str, db_path=None) -> dict:
    """Read-only preflight using the same N3 sources and inventory as N5."""
    obra_dir = Path(obra_dir)
    ids = _state_pillar_ids(obra_dir, pavimento) if classe == "PL" else []
    if not ids:
        ids = sorted(_get_db_expected_item_ids(obra_dir, classe, pavimento, db_path) or
                     set(_discover_item_ids(obra_dir, classe, pavimento)), key=natural_key)
    if classe == "PL" and (obra_dir / f"estado_{pavimento}.json").is_file():
        from src.core.pillar_sa_review import apply_state, eligible
        state = apply_state(json.loads((obra_dir / f"estado_{pavimento}.json").read_text(encoding="utf-8")), obra_dir, pavimento)
        excluded = {str(p.get("name") or "") for p in state.get("pilares", []) if not eligible(p)}
        ids = [item for item in ids if item not in excluded]
    missing = []
    for item in ids:
        sources = _find_n3_previews(obra_dir, classe, item, pavimento, visual_mode)
        if not sources or (classe == "PL" and len(sources) != 5):
            missing.append(item)
    return {"ready": bool(ids) and not missing, "total": len(ids), "missing": missing}


def assemble_n5(
    obra_dir: str | Path,
    classe: str,
    item_ids: Iterable[str] | None = None,
    pavimento: str = "",
    row_width: float | None = None,
    visual_mode: str = "NOVA",
    item_positions: dict[str, tuple[float, float]] | None = None,
    db_path: str | Path | None = None,
    pillar_group: str | None = None,
) -> N5AssemblyResult:
    """Monta um DXF N5 consolidado a partir dos previews N3.

    Suporta LJ, PL, LV e FV. LJ registra o modo solicitado, embora os dois
    perfis usem a mesma geometria enquanto seu design alternativo não diverge.
    """
    obra_dir = Path(obra_dir)
    classe = classe.upper().strip()
    if classe not in ("LJ", "PL", "LV", "FV"):
        raise ValueError(f"Classe N5 invalida: {classe}")
    visual_mode = normalize_visual_mode(visual_mode)

    if pillar_group is not None:
        pillar_group = pillar_group.upper()
        if classe != "PL" or pillar_group not in {"PARA", "PASSA"}:
            raise ValueError("Grupo N5 de pilares inválido")

    descoberta_automatica = item_ids is None
    ids = list(item_ids or [])
    if not ids:
        ids = _discover_item_ids(obra_dir, classe, pavimento)
    ids = sorted(dict.fromkeys(str(i).strip() for i in ids if str(i).strip()), key=natural_key)

    # P5: Completude DB × disco — item no banco sem preview N3 NÃO some em silêncio.
    # Inclui ids do banco na montagem; se o arquivo não existir, vira status=missing
    # e missing_count sobe (executar_n5 falha com missing_count > 0).
    expected_ids = _get_db_expected_item_ids(obra_dir, classe, pavimento, db_path)
    discovered_ids = set(ids)
    extra_ids: list[str] = []
    # Em producao, o banco SA e a fonte autoritativa do recorte por pavimento.
    # LV permanece fora desta mudanca porque seu motor esta sob trabalho isolado.
    state_pl_ids = _state_pillar_ids(obra_dir, pavimento) if classe == "PL" else []
    if descoberta_automatica and state_pl_ids:
        ids = state_pl_ids
        discovered_ids = set(ids)
        # reverse_eng_fichas pode representar apenas a amostra treinada de
        # pilares. O estado SA e as publicacoes N3 sao o inventario corrente.
        expected_ids = set(state_pl_ids)
    elif descoberta_automatica and pavimento and expected_ids and classe in {"PL", "FV", "LJ"}:
        extra_ids = sorted(discovered_ids - expected_ids, key=natural_key)
        if extra_ids:
            _log.warning(
                "[N5/PUREZA] Ignorando %d item(ns) fora de %s/%s: %s",
                len(extra_ids), pavimento, classe, extra_ids,
            )
        ids = sorted(expected_ids, key=natural_key)

    if classe == "PL" and pavimento:
        state_path = obra_dir / f"estado_{pavimento}.json"
        if state_path.is_file():
            from src.core.pillar_sa_review import apply_state, eligible
            state = apply_state(json.loads(state_path.read_text(encoding="utf-8")), obra_dir, pavimento)
            excluded = {str(p.get("name") or "") for p in state.get("pilares", []) if not eligible(p)}
            ids = [item for item in ids if item not in excluded]
            expected_ids -= excluded
            discovered_ids -= excluded
    missing_db_ids = expected_ids - discovered_ids
    if missing_db_ids:
        _log.error(
            "[CRITICAL/N5] Completude: %d item(ns) no banco ausentes da descoberta em disco: %s",
            len(missing_db_ids),
            sorted(missing_db_ids, key=natural_key),
        )
        for mid in sorted(missing_db_ids, key=natural_key):
            ids.append(mid)
        ids = sorted(dict.fromkeys(ids), key=natural_key)

    out_dir = obra_dir / "Fase-6_Execucao_CAD" / "n5"
    out_dir.mkdir(parents=True, exist_ok=True)
    pav_tag = _safe_name(pavimento or "GERAL")
    group_tag = f"_{pillar_group}" if pillar_group else ""
    out_path = out_dir / f"N5_{classe}_{pav_tag}_{visual_mode}{group_tag}.dxf"
    manifest_path = out_path.with_suffix(".json")

    dst = _new_doc_like()
    items = []

    if classe == "LJ":
        layouts: dict[str, tuple[float, float, float | None, float | None]] = {}
        if item_positions is None:
            layouts = _get_db_lj_item_layouts(obra_dir, pavimento, db_path)
            item_positions = {
                item_id: (layout[0], layout[1])
                for item_id, layout in layouts.items()
            }

        # Le os previews uma unica vez. Alem de reduzir I/O, isto permite
        # estimar a translacao dominante do pavimento antes de posicionar
        # lajes escalonadas cujo bbox ultrapassa o corpo logico.
        prepared: dict[str, tuple[Path, object, tuple[float, float, float, float] | None]] = {}
        prepare_errors: dict[str, tuple[str, str]] = {}
        for item_id in ids:
            src_path = _find_n3_preview(obra_dir, classe, item_id, pavimento, visual_mode)
            if not src_path:
                prepare_errors[item_id] = ("missing", "preview N3 ausente")
                continue
            try:
                src_doc = ezdxf.readfile(str(src_path))
                prepared[item_id] = (src_path, src_doc, _lj_panel_bbox(src_doc))
            except Exception as exc:
                prepare_errors[item_id] = ("error", str(exc)[:120])

        coherent = _lj_coherent_translations(
            [
                (item_id, src_doc, panel_bbox)
                for item_id, (_src_path, src_doc, panel_bbox) in prepared.items()
                if panel_bbox is not None
            ],
            layouts,
        ) if layouts else {}

        for item_id in ids:
            if item_id in prepare_errors:
                status, message = prepare_errors[item_id]
                items.append(N5ItemResult(item_id, "", status, message))
                continue
            src_path, src_doc, panel_bbox = prepared[item_id]
            try:
                dx = dy = 0.0
                target = (item_positions or {}).get(item_id)
                if target and panel_bbox:
                    dx, dy = coherent.get(
                        item_id,
                        (
                            float(target[0]) - panel_bbox[0],
                            float(target[1]) - panel_bbox[1],
                        ),
                    )
                count = _import_doc_entities(
                    src_doc,
                    dst,
                    dx=dx,
                    dy=dy,
                    skip_fv_helpers=True,
                )
                pose_msg = (
                    f"; posição SA ({target[0]:.1f}, {target[1]:.1f}); "
                    f"translação coerente ({dx:.1f}, {dy:.1f})"
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
    elif classe == "PL":
        # Pilares possuem cinco folhas independentes por item. Cada uma tem
        # coordenadas locais proprias, portanto precisa do seu proprio bbox e
        # translacao. Uma linha corresponde sempre a exatamente um pilar.
        margin = 150.0
        gap_x = 120.0
        gap_y = 220.0
        y_cursor = -margin
        for row_number, item_id in enumerate(ids, start=1):
            src_paths = _find_n3_previews(obra_dir, classe, item_id, pavimento, visual_mode)
            if pillar_group:
                # Cima é universal. Preserva ordem e escala das vistas N3.
                indices = (0, 3, 4) if pillar_group == "PARA" else (0, 1, 2)
                src_paths = [src_paths[i] for i in indices] if len(src_paths) == 5 else []
            if not src_paths:
                items.append(N5ItemResult(
                    item_id, "", "missing",
                    "conjunto N3 de pilares incompleto ou ausente",
                ))
                continue
            try:
                source_docs = []
                for path in src_paths:
                    src_doc = ezdxf.readfile(str(path))
                    source_box = _entity_bbox(src_doc)
                    if source_box is None:
                        raise ValueError(f"bbox vazio: {path.name}")
                    source_docs.append((path, src_doc, source_box))

                x_cursor = margin
                row_height = max(box[3] - box[1] for _, _, box in source_docs)
                count = 0
                for _path, src_doc, source_box in source_docs:
                    min_x, _min_y, max_x, max_y = source_box
                    width = max(max_x - min_x, 1.0)
                    count += _import_doc_entities(
                        src_doc,
                        dst,
                        dx=x_cursor - min_x,
                        dy=y_cursor - max_y,
                    )
                    x_cursor += width + gap_x
                items.append(N5ItemResult(
                    item_id,
                    ";".join(str(path) for path in src_paths),
                    "ok",
                    f"{count} entidades em {len(src_paths)} preview(s); linha {row_number}",
                ))
                y_cursor -= row_height + gap_y
            except Exception as exc:
                items.append(N5ItemResult(
                    item_id,
                    ";".join(str(path) for path in src_paths),
                    "error",
                    str(exc)[:120],
                ))
    else:  # LV e FV: empacota cada item como uma folha/grupo.
        max_row_w = float(row_width or 2000.0)  # 20 metros
        margin = 150.0
        gap_x = 250.0
        gap_y = 300.0
        x_cursor = margin
        y_cursor = -margin
        row_h = 0.0
        for item_id in ids:
            src_paths = _find_n3_previews(obra_dir, classe, item_id, pavimento, visual_mode)
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

    if classe != "LJ":
        apply_visual_mode(dst, visual_mode, classe)
    dst.saveas(str(out_path))
    manifest = {
        "classe": classe,
        "obra": obra_dir.name,
        "pavimento": pavimento,
        "visual_mode": visual_mode,
        "pillar_group": pillar_group,
        "output": str(out_path),
        "ok_count": sum(1 for item in items if item.status == "ok"),
        "missing_count": sum(1 for item in items if item.status != "ok"),
        "extra_count": len(extra_ids),
        "extra_ids": extra_ids,
        "items": [item.__dict__ for item in items],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    resultado = N5AssemblyResult(
        classe, obra_dir.name, pavimento, out_path, manifest_path, items, extra_ids
    )
    if resultado.missing_count > 0:
        ausentes = [i.item_id for i in resultado.items if i.status != "ok"]
        _log.warning("[CRITICAL/N5] ALERTA DE COMPLETUDE: Prancha N5 concluída COM FALHAS/AUSÊNCIAS (%d missing): %s", resultado.missing_count, ausentes)
    return resultado
