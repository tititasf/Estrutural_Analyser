# -*- coding: utf-8 -*-
"""
DXF Loader - Carrega arquivos DXF e retorna dicionário de entidades.

Detecta família DXF (TQS = layers numéricos, BIM = layers descritivos).
Extrai: polylines, lines, texts (MTEXT/TEXT), blocks, circles, arcs,
hatches, dimensions, ellipses, meshes, splines.

Modos de renderização controlam filtragem de cor e geometria.
"""

import copy
import logging
import math
import re
from enum import Enum, auto
from typing import Any, Dict, List, Tuple

import ezdxf
from ezdxf.math import Matrix44

logger = logging.getLogger(__name__)


class RenderMode(Enum):
    """
    5 Modos de Fidelidade (Color Debugging).
    Focados em resolver problemas de renderização de cor.
    """
    FIDELITY_1 = auto()
    FIDELITY_2 = auto()
    FIDELITY_3 = auto()
    FIDELITY_4 = auto()
    FIDELITY_5 = auto()
    TRUE_GEOMETRY = auto()
    EDGE_CLEANER = auto()
    COLOR_BASIC = auto()
    COLOR_EXTENDED = auto()
    COLOR_LAYERS = auto()
    COLOR_ORTHO = auto()
    COLOR_FLATTEN = auto()
    COLOR_BLOCKS = auto()
    COLOR_FAN = auto()
    COLOR_OMEGA = auto()


class DXFLoader:
    """
    Carregador principal de arquivos DXF.

    Extrai todas as entidades relevantes do modelspace, incluindo
    entidades dentro de blocos (INSERT), aplicando transformações
    de cor e geometria conforme o RenderMode selecionado.
    """

    def __init__(self, filepath: str, mode: RenderMode = RenderMode.TRUE_GEOMETRY):
        self.filepath = filepath
        self.mode = mode
        self.doc = None
        self.msp = None
        self.hidden_layers: set = set()
        self.entities: Dict[str, list] = {
            "lines": [],
            "polylines": [],
            "circles": [],
            "texts": [],
            "hatches": [],
            "ellipses": [],
            "splines": [],
        }

    def load(self) -> Dict[str, list]:
        """
        Carrega o DXF e extrai todas as entidades.

        Returns:
            Dict com listas de entidades por tipo.
        """
        try:
            self.doc = ezdxf.readfile(self.filepath)
            self.msp = self.doc.modelspace()

            # Identifica layers ocultos/congelados
            self.hidden_layers = set()
            layer_table = {}
            for layer in self.doc.layers:
                if layer.is_off() or layer.is_frozen():
                    self.hidden_layers.add(layer.dxf.name.upper())
                layer_table[layer.dxf.name] = layer.dxf.color

            # Extrai entidades do modelspace
            self.entities = self._extract_entities(self.msp)

            logging.info(
                f"[DXFLoader.load] Total carregado - Linhas: {len(self.entities['lines'])}"
                f", Hatches: {len(self.entities.get('hatches', []))}"
                f", Polylines: {len(self.entities['polylines'])}"
            )

            # Aplica purge global se modo adequado
            if self.mode != RenderMode.TRUE_GEOMETRY:
                self._global_purge()

            logging.info(
                f"[DXFLoader.load] Após _global_purge - Linhas: {len(self.entities['lines'])}"
            )

            return self.entities

        except Exception as e:
            logging.error(f"Failed to load DXF: {e}")
            raise

    def _extract_entities(
        self,
        container,
        override_layer: str = None,
        override_color: int = None,
        total_matrix: Matrix44 = None,
        is_block: bool = False,
    ) -> Dict[str, list]:
        """Extrai entidades de um container (espaço ou bloco) de forma achatada."""

        entities: Dict[str, list] = {
            "lines": [],
            "polylines": [],
            "circles": [],
            "texts": [],
            "hatches": [],
            "ellipses": [],
            "splines": [],
        }

        # ---- helpers locais ----
        def clean_mtext(text: str) -> str:
            """Remove formatação MTEXT (\\P, \\f, etc.)."""
            text = re.sub(r"\\[A-Za-z][^;]*;", "", text)
            text = text.replace("\\P", "\n")
            return text.strip()

        def get_color_info(entity) -> Tuple[Any, int, float]:
            """Retorna (rgb, aci, lineweight) de uma entidade."""
            lw = getattr(entity.dxf, "lineweight", 0)
            layer_name = entity.dxf.layer if hasattr(entity.dxf, "layer") else ""
            aci = entity.dxf.get("color", 256)  # 256 = BYLAYER
            origin = aci

            target_layer = layer_name
            for l in (self.doc.layers if self.doc else []):
                if l.dxf.name == target_layer:
                    if aci == 256:
                        aci = l.dxf.color
                    break

            try:
                aci2rgb = ezdxf.colors.aci2rgb if hasattr(ezdxf, "colors") else None
                if aci2rgb and 1 <= aci <= 255:
                    r, g, b = aci2rgb(aci)
                    return (r, g, b), aci, lw
            except Exception:
                pass
            return None, aci, lw

        # ---- configurações do modo ----
        mesh_keywords = ["MESH", "3DSOLID", "SURFACE"]
        prohibited_suffixes = ["-", "_"]

        use_native_transform = self.mode in (
            RenderMode.TRUE_GEOMETRY,
            RenderMode.EDGE_CLEANER,
        )
        explode_curves = self.mode in (RenderMode.TRUE_GEOMETRY,)
        strict_ortho = self.mode in (RenderMode.COLOR_ORTHO,)
        z_flatten = self.mode in (
            RenderMode.COLOR_FLATTEN,
            RenderMode.TRUE_GEOMETRY,
        )
        color_1_4 = self.mode in (
            RenderMode.FIDELITY_1,
            RenderMode.FIDELITY_2,
            RenderMode.FIDELITY_3,
            RenderMode.FIDELITY_4,
        )
        color_strict = self.mode in (RenderMode.COLOR_BASIC, RenderMode.COLOR_EXTENDED)
        color_1_7 = self.mode in (
            RenderMode.COLOR_LAYERS,
            RenderMode.COLOR_ORTHO,
        )
        int_grid = self.mode in (RenderMode.COLOR_FAN, RenderMode.COLOR_OMEGA)
        micro_threshold = 0.5  # linhas menores que isso são descartadas

        vertex_valence: Dict[Tuple, int] = {}

        # ---- processar LINEs ----
        try:
            if hasattr(container, "query"):
                line_entities = container.query("LINE")
            else:
                line_entities = [e for e in container if e.dxftype() == "LINE"]
        except Exception:
            line_entities = []

        logging.info(
            f"[DXFLoader] Encontradas {len(line_entities)} entidades LINE no container"
        )
        logging.info(
            f"[DXFLoader] Modo atual: {self.mode.name}"
            f", TRUE_GEOMETRY: {self.mode == RenderMode.TRUE_GEOMETRY}"
        )

        lines_before = len(line_entities)
        filter_stats = {
            "hidden_layer": 0,
            "passed": 0,
            "blacklist": 0,
            "whitelist": 0,
            "color_filter": 0,
            "ortho": 0,
            "slope": 0,
            "micro": 0,
            "z_filter": 0,
            "exceptions": 0,
        }

        for line in line_entities:
            try:
                start = line.dxf.start
                end = line.dxf.end
                p1 = (round(start.x, 4), round(start.y, 4))
                p2 = (round(end.x, 4), round(end.y, 4))

                layer = (override_layer or line.dxf.get("layer", "")).upper()

                # Filtro: layer oculto
                if layer in self.hidden_layers:
                    filter_stats["hidden_layer"] += 1
                    continue

                line_copy = copy.copy(line)
                if total_matrix and use_native_transform:
                    line_copy.transform(total_matrix)

                rgb, aci, lw = get_color_info(line)
                if override_color is not None:
                    aci = override_color

                # Filtro: whitelist estrutural
                structural_whitelist = ["VIGA", "PILAR", "LAJE", "PAREDE", "EIXO"]
                is_struct = any(kw in layer for kw in structural_whitelist)

                # Filtro: linhas micro
                dx_raw = abs(p2[0] - p1[0])
                dy_raw = abs(p2[1] - p1[1])
                length = math.hypot(dx_raw, dy_raw)

                if length < micro_threshold and not is_struct:
                    filter_stats["micro"] += 1
                    continue

                # Filtro: ortogonalidade
                is_ortho = dx_raw < 0.01 or dy_raw < 0.01
                is_45 = abs(dx_raw - dy_raw) < 0.01 if dx_raw > 0.01 else False

                if strict_ortho and not is_ortho and not is_45 and not is_struct:
                    filter_stats["ortho"] += 1
                    continue

                # Z-flatten
                if z_flatten:
                    start_flat = ezdxf.math.Vec3(start.x, start.y, 0)
                    end_flat = ezdxf.math.Vec3(end.x, end.y, 0)
                else:
                    start_flat = start
                    end_flat = end

                entities["lines"].append(
                    {
                        "start": (start_flat.x, start_flat.y, start_flat.z),
                        "end": (end_flat.x, end_flat.y, end_flat.z),
                        "layer": layer,
                        "color": aci,
                        "rgb": rgb,
                        "lineweight": lw,
                        "handle": line.dxf.handle if hasattr(line.dxf, "handle") else None,
                    }
                )
                filter_stats["passed"] += 1

                # Valência de vértices
                vertex_valence[p1] = vertex_valence.get(p1, 0) + 1
                vertex_valence[p2] = vertex_valence.get(p2, 0) + 1

            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar linha: {e}")
                filter_stats["exceptions"] += 1

        lines_added = filter_stats["passed"]
        logging.info(
            f"[DXFLoader] Processadas {lines_added} linhas após filtros"
            f" (total acumulado: {len(entities['lines'])})"
        )
        logging.info(f"[DXFLoader] Estatísticas de filtros: {filter_stats}")

        # ---- processar POLYLINES (LWPOLYLINE + POLYLINE) ----
        for poly in list(container.query("LWPOLYLINE POLYLINE") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or poly.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue

                poly_copy = copy.copy(poly)
                if total_matrix and use_native_transform:
                    poly_copy.transform(total_matrix)

                target_poly = poly_copy if use_native_transform else poly

                dxf_type = poly.dxftype()

                if dxf_type == "POLYLINE":
                    if poly.is_polyface_mesh() or poly.is_polygon_mesh() or poly.is_3d_polyline():
                        points = list(poly.get_points(format="xyz"))
                    else:
                        points = [(v.dxf.location.x, v.dxf.location.y, v.dxf.location.z)
                                  for v in poly.vertices]
                else:
                    # LWPOLYLINE
                    if explode_curves:
                        points = [(p.x, p.y, 0) for p in target_poly.flattening(0.01)]
                    else:
                        points = [(p[0], p[1], 0) for p in target_poly.get_points(format="xy")]

                is_closed = target_poly.is_closed if hasattr(target_poly, "is_closed") else target_poly.closed

                rgb, aci, lw = get_color_info(poly)
                if override_color is not None:
                    aci = override_color

                # Detecta keywords de mesh
                current_poly_keywords = [kw for kw in mesh_keywords if kw in layer]

                entities["polylines"].append(
                    {
                        "points": points,
                        "layer": layer,
                        "color": aci,
                        "rgb": rgb,
                        "lineweight": lw,
                        "closed": bool(is_closed),
                        "area": target_poly.area if hasattr(target_poly, "area") else 0,
                        "type": dxf_type,
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar polyline: {e}")

        # ---- processar CIRCLES ----
        for circle in (container.query("CIRCLE") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or circle.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                rgb, aci, lw = get_color_info(circle)
                pts = circle.dxf.center
                entities["circles"].append(
                    {
                        "center": (pts.x, pts.y, pts.z),
                        "radius": circle.dxf.radius,
                        "layer": layer,
                        "color": aci,
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar circle: {e}")

        # ---- processar ARCs ----
        for arc in (container.query("ARC") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or arc.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                rgb, aci, lw = get_color_info(arc)
                entities["circles"].append(
                    {
                        "center": (arc.dxf.center.x, arc.dxf.center.y, arc.dxf.center.z),
                        "radius": arc.dxf.radius,
                        "start_angle": arc.dxf.start_angle,
                        "end_angle": arc.dxf.end_angle,
                        "layer": layer,
                        "color": aci,
                        "type": "ARC",
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar arc: {e}")

        # ---- processar TEXTs e MTEXTs ----
        for text in (container.query("TEXT MTEXT ATTRIB ATTDEF") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or text.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue

                is_mtext = text.dxftype() == "MTEXT"
                content = text.text if is_mtext else text.dxf.get("text", "")
                if is_mtext:
                    content = clean_mtext(content)

                text_copy = copy.copy(text)
                if total_matrix and use_native_transform:
                    text_copy.transform(total_matrix)

                target_text = text_copy if use_native_transform else text

                rotation = getattr(target_text.dxf, "rotation", 0)
                height = getattr(target_text.dxf, "height", 2.5)

                if is_mtext:
                    pos = target_text.dxf.insert
                    attachment = getattr(target_text.dxf, "attachment_point", 1)
                    width_factor = getattr(target_text.dxf, "width", 0)
                    entities["texts"].append(
                        {
                            "text": content,
                            "pos": (pos.x, pos.y, pos.z),
                            "height": height,
                            "rotation": rotation,
                            "layer": layer,
                            "type": "MTEXT",
                            "attachment_point": attachment,
                            "width": width_factor,
                        }
                    )
                else:
                    halign = getattr(target_text.dxf, "halign", 0)
                    valign = getattr(target_text.dxf, "valign", 0)

                    if halign != 0 or valign != 0:
                        base_pt = target_text.dxf.align_point
                    else:
                        base_pt = target_text.dxf.insert

                    if total_matrix and not use_native_transform:
                        trans_pt = total_matrix.transform(base_pt)
                    else:
                        trans_pt = base_pt

                    entities["texts"].append(
                        {
                            "text": content,
                            "pos": (trans_pt.x, trans_pt.y, trans_pt.z if hasattr(trans_pt, "z") else 0),
                            "height": height,
                            "rotation": rotation,
                            "layer": layer,
                            "type": "TEXT",
                            "halign": halign,
                            "valign": valign,
                        }
                    )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar texto: {e}")

        # ---- processar DIMENSIONs ----
        for dim in (container.query("DIMENSION") if hasattr(container, "query") else []):
            try:
                g_name = dim.dxf.get("geometry", "")
                if g_name and g_name.startswith("*D"):
                    block = self.doc.blocks.get(g_name) if self.doc else None
                    if block:
                        sub = self._extract_entities(block, is_block=True)
                        for key in entities:
                            entities[key].extend(sub.get(key, []))
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar dimension: {e}")

        # ---- processar INSERTs (blocos) ----
        for insert in (container.query("INSERT") if hasattr(container, "query") else []):
            try:
                g_name = insert.dxf.name
                if g_name.startswith("*"):
                    continue

                block = self.doc.blocks.get(g_name) if self.doc else None
                if not block:
                    continue

                # Filtro de densidade: blocos com muitas linhas podem ser "noise"
                density_threshold = 500
                line_count = sum(1 for _ in block if _.dxftype() == "LINE")

                # Prefixos de blocos estruturais
                structural_prefixes = ["V", "P", "L", "S", "M"]
                m = any(g_name.upper().startswith(p) for p in structural_prefixes)

                current_override = override_color or insert.dxf.get("color", None)

                sub = self._extract_entities(
                    block,
                    override_layer=insert.dxf.get("layer", None),
                    override_color=current_override,
                    total_matrix=insert.dxf.get("matrix44", total_matrix),
                    is_block=True,
                )
                for key in entities:
                    entities[key].extend(sub.get(key, []))

            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar insert: {e}")

        # ---- processar SOLIDs / TRACE / 3DFACE ----
        for entity in (container.query("SOLID TRACE 3DFACE") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or entity.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                pts_tuples = []
                for attr in ("vtx0", "vtx1", "vtx2", "vtx3"):
                    pt = getattr(entity.dxf, attr, None)
                    if pt:
                        pts_tuples.append((pt.x, pt.y, pt.z))
                if pts_tuples and pts_tuples[-1] == pts_tuples[-2]:
                    pts_tuples.pop()
                entities["hatches"].append(
                    {
                        "vertices": pts_tuples,
                        "layer": layer,
                        "type": entity.dxftype(),
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar solid/trace/3dface: {e}")

        # ---- processar HATCHes ----
        for hatch in (container.query("HATCH") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or hatch.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue

                target_hatch = hatch
                paths_data = []
                for path in target_hatch.paths:
                    current_path = {"edges": []}
                    if hasattr(path, "edges"):
                        for edge in path.edges:
                            edge_pts = []
                            if hasattr(edge, "start") and hasattr(edge, "end"):
                                edge_pts = [
                                    (edge.start.x, edge.start.y),
                                    (edge.end.x, edge.end.y),
                                ]
                            elif hasattr(edge, "center"):
                                edge_pts = [
                                    (edge.center.x, edge.center.y),
                                ]
                            current_path["edges"].append(edge_pts)
                    else:
                        # Polyline path
                        prev_p = None
                        for v in path.vertices:
                            next_p = (v[0], v[1])
                            if prev_p:
                                current_path["edges"].append([prev_p, next_p])
                            prev_p = next_p
                    paths_data.append(current_path)

                entities["hatches"].append(
                    {
                        "paths": paths_data,
                        "layer": layer,
                        "type": "HATCH",
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar hatch: {e}")

        # ---- processar ELLIPSEs ----
        for ellipse in (container.query("ELLIPSE") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or ellipse.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                entities["ellipses"].append(
                    {
                        "center": (
                            ellipse.dxf.center.x,
                            ellipse.dxf.center.y,
                            ellipse.dxf.center.z,
                        ),
                        "major_axis": (
                            ellipse.dxf.major_axis.x,
                            ellipse.dxf.major_axis.y,
                            ellipse.dxf.major_axis.z,
                        ),
                        "ratio": ellipse.dxf.ratio,
                        "start_param": ellipse.dxf.start_param,
                        "end_param": ellipse.dxf.end_param,
                        "layer": layer,
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar ellipse: {e}")

        # ---- processar MESHes ----
        for mesh in (container.query("MESH") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or mesh.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                target_mesh = mesh
                try:
                    face_iterator = target_mesh.faces_as_vertices()
                    face_points = [
                        [(p.x, p.y, p.z) for p in face] for face in face_iterator
                    ]
                except Exception:
                    face_points = []
                    print(f"MESH EXTRACT ERROR: {mesh.dxf.handle if hasattr(mesh.dxf, 'handle') else '?'}")

                entities["hatches"].append(
                    {
                        "faces": face_points,
                        "layer": layer,
                        "type": "MESH",
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar mesh: {e}")

        # ---- processar SPLINEs ----
        for spline in (container.query("SPLINE") if hasattr(container, "query") else []):
            try:
                layer = (override_layer or spline.dxf.get("layer", "")).upper()
                if layer in self.hidden_layers:
                    continue
                control_points = [
                    (p.x, p.y, p.z) for p in spline.control_points
                ]
                entities["splines"].append(
                    {
                        "control_points": control_points,
                        "degree": spline.dxf.degree,
                        "layer": layer,
                    }
                )
            except Exception as e:
                logging.warning(f"[DXFLoader] Erro ao processar spline: {e}")

        return entities

    @staticmethod
    def load_dxf(path: str, mode: RenderMode = RenderMode.TRUE_GEOMETRY) -> Dict[str, list]:
        """Helper estático para carregar e retornar entidades direto."""
        logging.info(f"[DXFLoader.load_dxf] Carregando {path} em modo {mode.name}")
        loader = DXFLoader(path, mode)
        entities = loader.load()
        logging.info(
            f"[DXFLoader.load_dxf] Carregado: {len(entities['lines'])} linhas, "
            f"{len(entities['polylines'])} polylines, "
            f"{len(entities.get('texts', []))} textos"
        )
        return entities

    def get_stats(self) -> str:
        """Retorna estatísticas do carregamento."""
        return (
            f"DXF Loaded: {self.filepath}"
            f"\nPolylines: {len(self.entities.get('polylines', []))}"
            f"\nLines: {len(self.entities.get('lines', []))}"
            f"\nTexts: {len(self.entities.get('texts', []))}"
        )

    def _global_purge(self):
        """
        [NEW v7/v8] Sanitizador Global de Geometria.
        Remove 'fans' e artefatos de todo o Modelspace.
        """
        pre_count = len(self.entities["lines"])
        logging.info(
            f"[Purge] Iniciando com {pre_count} linhas (Modo: {self.mode.name})"
        )

        # Só purge para modos específicos
        if self.mode in (RenderMode.TRUE_GEOMETRY,):
            logging.info(f"[Purge] Pulando purge para modo {self.mode.name}")
            return

        precision = 2

        # Mapeia valência global de vértices
        global_valence: Dict[Tuple, int] = {}
        for line in self.entities["lines"]:
            p1 = (
                round(line["start"][0], precision),
                round(line["start"][1], precision),
            )
            p2 = (
                round(line["end"][0], precision),
                round(line["end"][1], precision),
            )
            global_valence[p1] = global_valence.get(p1, 0) + 1
            global_valence[p2] = global_valence.get(p2, 0) + 1

        threshold = 6  # Fan detection: vértice com muitas conexões

        # Posições de textos estruturais para proteger linhas próximas
        text_positions = []
        for t in self.entities.get("texts", []):
            if re.match(r"^(P|V|L|S|M)\d+", t.get("text", ""), re.I):
                text_positions.append(t.get("pos", (0, 0, 0)))

        def is_near_structural_text(line, positions, dist=50):
            lp = (
                (line["start"][0] + line["end"][0]) / 2,
                (line["start"][1] + line["end"][1]) / 2,
            )
            for tp in positions:
                if math.hypot(lp[0] - tp[0], lp[1] - tp[1]) < dist:
                    return True
            return False

        # Filtra linhas de fan (vértices com alta valência)
        purged = []
        for l in self.entities["lines"]:
            p1 = (round(l["start"][0], precision), round(l["start"][1], precision))
            p2 = (round(l["end"][0], precision), round(l["end"][1], precision))

            v1 = global_valence.get(p1, 0)
            v2 = global_valence.get(p2, 0)

            if (v1 > threshold or v2 > threshold) and not is_near_structural_text(
                l, text_positions
            ):
                continue  # remove fan line
            purged.append(l)

        self.entities["lines"] = purged
        post_count = len(self.entities["lines"])

        logging.info(
            f"[Purge] Finalizado (Modo {self.mode.name}). "
            f"Removidas {pre_count - post_count} linhas. "
            f"Restantes: {post_count}"
        )
