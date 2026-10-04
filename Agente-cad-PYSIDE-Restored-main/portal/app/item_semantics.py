"""Adaptador granular das funções puras do SA; nunca traça ou divide geometria.

Contexto é somente estrutural/N1, nunca recortes N2 ou contratos N3/N4.
O cache guarda textos imutáveis por assinatura do DXF, não resultados de itens.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from pathlib import Path
from time import perf_counter


def canonical_beams(db_path: Path, obra_dir: Path, pav: str):
    """Contexto N1 somente leitura e estritamente do projeto desta obra/pav."""
    import json
    import sqlite3
    if not Path(db_path).is_file():
        return None
    with sqlite3.connect(Path(db_path).resolve().as_uri() + "?mode=ro", uri=True) as conn:
        project = conn.execute("SELECT id FROM projects WHERE work_name=? AND name=? ORDER BY rowid DESC LIMIT 1",
                               (str(obra_dir), pav)).fetchone()
        if not project:
            return None
        conn.row_factory = sqlite3.Row
        result = []
        for record in conn.execute("SELECT * FROM beams WHERE project_id=?", (project[0],)):
            beam = json.loads(record["data_json"])
            if "links_json" in record.keys() and record["links_json"]:
                for key, value in json.loads(record["links_json"]).items():
                    if not beam.setdefault("links", {}).get(key):
                        beam["links"][key] = value
            result.append(beam)
        return result


def slab_contacts(points, slabs):
    """Adjacência por arestas, mesma convenção/tolerâncias do SA canônico.

    MainWindow._pillar_face_from_edge_overlap / _pillar_laje_entries.
    Não decide apoio por centroide nem cria geometria.
    """
    from shapely.geometry import Polygon
    polygon = Polygon(points)
    x0, y0, x1, y1 = polygon.bounds
    edges = ({"A": ("H", y0, x0, x1, "BAIXO"), "B": ("H", y1, x0, x1, "CIMA"),
              "C": ("V", x0, y0, y1, "ESQ"), "D": ("V", x1, y0, y1, "DIR")}
             if x1-x0 >= y1-y0 else
             {"A": ("V", x0, y0, y1, "ESQ"), "B": ("V", x1, y0, y1, "DIR"),
              "C": ("H", y1, x0, x1, "CIMA"), "D": ("H", y0, x0, x1, "BAIXO")})
    result = []
    for slab in slabs:
        pts = slab.get("points") or []
        if len(pts) < 3 or polygon.distance(Polygon(pts)) > 5:
            continue
        best, side, face = 0, "NULO", "NULO"
        for a, b in zip(pts, pts[1:] + pts[:1]):
            axis = "H" if abs(a[1]-b[1]) < 3 else "V" if abs(a[0]-b[0]) < 3 else None
            if axis is None:
                continue
            fixed = (a[1]+b[1])/2 if axis == "H" else (a[0]+b[0])/2
            lo, hi = sorted((a[0], b[0]) if axis == "H" else (a[1], b[1]))
            for sid, (ax, f, r0, r1, label) in edges.items():
                overlap = min(hi, r1)-max(lo, r0)
                if ax == axis and abs(f-fixed) < 4 and overlap > 1 and overlap > best:
                    best, side, face = overlap, sid, label
        result.append({"laje": slab.get("name") or "?", "side": side, "face": face,
                       "source": "canonical_geometry_adjacency"})
    return result


@lru_cache(maxsize=8)
def _texts(path: str, size: int, mtime_ns: int) -> tuple:
    import ezdxf
    doc = ezdxf.readfile(path)
    result = []
    for entity in doc.modelspace().query("TEXT MTEXT"):
        pos = entity.dxf.insert
        value = entity.plain_text() if entity.dxftype() == "MTEXT" else entity.dxf.text
        result.append({"text": value, "pos": [pos.x, pos.y],
                       "layer": entity.dxf.layer, "handle": entity.dxf.handle})
    return tuple(result)


def source_texts(source: Path | None) -> list:
    if source is None:
        return []
    source = Path(source).resolve()
    stat = source.stat()
    return list(_texts(str(source), stat.st_size, stat.st_mtime_ns))


@lru_cache(maxsize=4)
def _pillar_source(path, size, mtime_ns, legend_signature):
    import ezdxf
    from src.core.pillar_convention_recognition import convention_for_source
    doc = ezdxf.readfile(path)
    data = {"lines": [], "polylines": []}
    for entity in doc.modelspace():
        if entity.dxftype() == "LINE":
            data["lines"].append({"start": list(entity.dxf.start), "end": list(entity.dxf.end), "layer": entity.dxf.layer})
        elif entity.dxftype() == "LWPOLYLINE":
            data["polylines"].append({"points": [[p[0], p[1]] for p in entity.get_points()], "closed": entity.closed})
    return data, convention_for_source(path)


def pillar_source(source):
    if source is None:
        return None
    source = Path(source).resolve()
    stat = source.stat()
    legend = tuple((str(p), p.stat().st_size, p.stat().st_mtime_ns)
                   for p in sorted(source.parent.glob('convencao_pilares*.dxf')))
    return _pillar_source(str(source), stat.st_size, stat.st_mtime_ns, legend)


def recognize(row: dict, classe: str, state: dict, texts: list, beams=None, pillar_context=None) -> tuple[dict, dict]:
    """Retorna patch + evidência. Só o caller persiste a linha selecionada."""
    from shapely.geometry import Point, Polygon
    from src.core.fundo_segment_levels import derive_fundo_segment_level
    started = perf_counter()
    polygon = Polygon(row["points"])
    evidence = {"scope": "segment" if classe == "fundo" or classe.startswith("lateral_") else "item",
                "geometry_preserved": True, "needs_human_review": True, "fields": {}}
    patch = {"is_validated": False}
    if evidence["scope"] == "segment":
        # Recalcular pelo contorno, sem herdar o nível de outro segmento.
        level = derive_fundo_segment_level(row["points"], state.get("slabs") or [])
        patch.update(level=level["value"], level_source=level["source"],
                     level_slabs=level["slabs"], level_distance_cm=level.get("distance_cm"))
        evidence["fields"]["level"] = dict(level)
        from src.core.beam_section_texts import dimension_texts
        candidates = dimension_texts(texts)
        # Distância ao polígono funciona também para a faixa diagonal. Cota
        # de pilar é excluída pelo próprio intérprete FV antes da associação.
        near = [(polygon.distance(Point(t["pos"])), i, t)
                for i, t in enumerate(candidates) if polygon.distance(Point(t["pos"])) <= 50.0]
        candidates = sorted(entry for entry in near
                            if abs(entry[2]["width"] - float(row.get("width") or 0)) <= 1.0)
        # Painel curtíssimo: a seção pode ser maior que o comprimento. Não
        # confundir automaticamente o lado maior com o eixo longitudinal.
        swapped = False
        if not candidates and classe == "fundo":
            candidates = sorted(entry for entry in near
                                if abs(entry[2]["width"] - float(row.get("length") or 0)) <= 1.0)
            swapped = bool(candidates)
        if candidates and (len(candidates) == 1 or candidates[1][0] - candidates[0][0] > 0.05
                           or candidates[1][2]["text"] == candidates[0][2]["text"]):
            distance, _, token = candidates[0]
            patch.update(section_dim=token["text"], beam_height=token["height"])
            if swapped:
                patch.update(length=row.get("width"), width=row.get("length"))
            evidence["fields"]["section_dim"] = {"source": "structural_text", "text": token["text"],
                                                     "pos": list(token["pos"]), "distance_cm": distance}
        else:
            patch.update(section_dim=None, beam_height=None)
            evidence["fields"]["section_dim"] = {"source": "unresolved", "candidates": len(candidates)}
    elif classe == "lajes":
        from src.core.analysis_helpers import process_slab_intelligent, extract_float
        item = deepcopy(row)
        # Um rótulo existente só é referência se estiver na nova geometria.
        labels = [t for t in texts if str(t.get("text", "")).strip() == row.get("name")
                  and polygon.covers(Point(t["pos"]))]
        item["pos"] = labels[0]["pos"] if labels else list(polygon.representative_point().coords)[0]
        item.pop("_nivel_candidates", None)
        # Apenas textos dentro do item: não roubar espessura da laje vizinha.
        own_texts = [t for t in texts if polygon.covers(Point(t["pos"]))]
        process_slab_intelligent(item, own_texts)
        patch.update(fields=item["fields"], links=item["links"],
                     height=extract_float(item["fields"].get("laje_dim")),
                     nivel=item["fields"].get("laje_nivel"))
        evidence["fields"]["level"] = item.get("_nivel_provenance") or {"source": "unresolved"}
        evidence["fields"]["height"] = {"source": "structural_text" if patch["height"] is not None else "unresolved"}
    elif classe == "pilares":
        from src.core.perspective_mapper import PillarPerspectiveMapper
        from src.core.pillar_special_faces import classify_pillar_geometry
        shape, orientation = PillarPerspectiveMapper.identify_shape([tuple(p) for p in row["points"]])
        patch.update(shape_type=shape, orientation=orientation,
                     bbox=list(polygon.bounds), area_val=polygon.area)
        patch["lajes"] = slab_contacts(row["points"], state.get("slabs") or [])
        if pillar_context is not None:
            from src.core.pillar_convention_recognition import recognize as classify
            classification, proof = classify(row["points"], *pillar_context)
            # Decisão validada de classificação permanece soberana.
            if "classification" not in (row.get("validated_fields") or []):
                patch["classification"] = classification
                patch["classification_evidence"] = proof
                patch["ignore_in_beams"] = classification.upper() == "NASCE"
            evidence["fields"]["classification"] = {"source": "structural_convention" if classification != "INDETERMINADO" else "unresolved", **proof}
        else:
            evidence["fields"]["classification"] = {"source": "unresolved", "reason": "source_unavailable"}
        evidence["fields"]["shape"] = {"source": "manual_contour", "classification": classify_pillar_geometry(row["points"])}
        if beams is not None:
            from src.core.pillar_face_beams import enrich_pillar_report_with_beams, materialize_face_beams_in_pillars
            item = deepcopy(row)
            item.update(patch)
            # Somente este pilar recebe a materialização. Nenhuma viga é interpretada.
            report = {item["name"]: deepcopy(item)}
            report[item["name"]].pop("face_beams", None)
            enrich_pillar_report_with_beams(report, beams)
            if not beams:
                report[item["name"]]["face_beams"] = {}
            materialize_face_beams_in_pillars([item], report, item_names={item["name"]})
            for key in ("face_beams", "sides_data", "fields", "links"):
                if key in item:
                    patch[key] = item[key]
            # Impede a ficha N1 de preferir a tabela serializada do contorno antigo.
            patch["interpretacao_abcd"] = {}
            evidence["fields"]["beam_contacts"] = {"source": "canonical_beam_context"}
        else:
            evidence["fields"]["beam_contacts"] = {"source": "unresolved", "reason": "canonical_beam_context_required"}
        evidence["fields"]["slab_contacts"] = {"source": "canonical_geometry_adjacency"}
        x0, y0, x1, y1 = polygon.bounds
        if shape.lower().startswith("ret"):
            long_side, short_side = max(x1-x0, y1-y0), min(x1-x0, y1-y0)
            patch.update(lado_A=long_side, lado_B=long_side, lado_C=short_side, lado_D=short_side)
    evidence["elapsed_ms"] = round((perf_counter() - started) * 1000, 2)
    patch["atencao"] = "Interpretação granular: revisar campos sem evidência." if any(
        v.get("source") == "unresolved" for v in evidence["fields"].values()) else ""
    return patch, evidence
