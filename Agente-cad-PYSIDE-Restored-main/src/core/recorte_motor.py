"""
Recorte Motor — Extrator automático de recortes de engenharia reversa.

Suporta 4 classes: PIL (Pilares), LV (Lateral de Viga), FV (Fundo de Viga), LAJ (Laje).

Algoritmo:
- PIL/LV: usa blocos '9999999999' (frame do STOG) para delimitar elementos
- FV/LAJ: usa posição das labels + expansão iterativa de bbox

Uso:
    from src.core.recorte_motor import RecorteMotor
    motor = RecorteMotor(source_dxf_path, er_type='PIL')
    results = motor.run(output_dir, db_path)
"""

from __future__ import annotations

import os
import re
import time
import logging
import sqlite3
import unicodedata
from pathlib import Path
from typing import Optional

import ezdxf
from ezdxf import colors as ezdxf_colors

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────────────────────────
# BLOCO 9999999999 — offsets do frame (PIL / LV)
# Block local space: outer (98139,34190)→(99624,35240)  size 1485x1050
#                    inner (98214,34230)→(99584,35200)  size 1370x970
# Title-block strip at BOTTOM: frame_y0 to frame_y0+254 (empirically measured)
# Content area: x0+variable_left_margin, y0+254, x1, y1
# ──────────────────────────────────────────────────────────────────────────────
BLK_FRAME_INNER = (98214.0, 34230.0, 99584.0, 35200.0)  # x0,y0,x1,y1 em local space
# Offset do title block dentro do inner frame (mesurdo em P1, P11)
FRAME_TITLE_BLOCK_H = 254.0  # altura da área de título/legenda no bottom do frame
FRAME_X_PITCH = 1585.0        # distância entre colunas de frames


class RecorteMotor:
    """Motor de extração automática de recortes por classe ER."""

    ER_TYPES = {'PIL', 'LV', 'FV', 'LAJ'}

    def __init__(self, source_dxf_path: str, er_type: str = None):
        self.source_dxf_path = Path(source_dxf_path)
        if not self.source_dxf_path.exists():
            raise FileNotFoundError(f"DXF não encontrado: {source_dxf_path}")

        # Auto-detectar tipo pelo nome do arquivo
        if er_type is None:
            er_type = self._detect_type(self.source_dxf_path.name)
        self.er_type = er_type.upper()
        if self.er_type not in self.ER_TYPES:
            raise ValueError(f"er_type inválido: {er_type}. Deve ser um de {self.ER_TYPES}")

        self._dxf: ezdxf.Drawing | None = None
        self._pkl: dict | None = None
        self._laj_dimension_hints: dict[str, dict] | None = None
        self._laj_layer_cache: dict[bool, set[str]] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Público: run()
    # ──────────────────────────────────────────────────────────────────────
    def run(
        self,
        output_dir: str | Path,
        db_path: str | Path | None = None,
        *,
        overwrite: bool = False,
    ) -> list[dict]:
        """
        Extrai todos os recortes do DXF fonte.

        Retorna lista de dicts com: elemento_id, recorte_path, bbox_json, entity_count, status.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        log.info("RecorteMotor: %s → %s", self.source_dxf_path.name, self.er_type)

        self._load_source()

        elements = self._discover_elements()
        log.info("Elementos descobertos: %d", len(elements))

        results = []
        for elem_id, label_positions, frame_bboxes in elements:
            try:
                rec = self._extract_one(
                    elem_id, label_positions, frame_bboxes,
                    output_dir, overwrite=overwrite
                )
                results.append(rec)
                log.debug("  ✓ %s: %d entidades", elem_id, rec['entity_count'])
            except Exception as exc:
                log.warning("  ✗ %s: %s", elem_id, exc)

        if db_path:
            self._register_db(results, db_path)

        return results

    # ──────────────────────────────────────────────────────────────────────
    # Carregamento
    # ──────────────────────────────────────────────────────────────────────
    def _load_source(self):
        log.debug("Carregando DXF: %s", self.source_dxf_path.name)
        self._dxf = ezdxf.readfile(str(self.source_dxf_path))

        # [FIX v4] Usar DXFLoader (TRUE_GEOMETRY) como única fonte de geometria.
        # Garante paridade total com o viewer: cores corretas, coordenadas corretas
        # (fix para LWPOLYLINE/ARC com xscale negativo), cache compartilhado.
        # O antigo _extract_geometry_from_dxf() hardcodava aci=7 (branco) para
        # todas as entidades e usava virtual_entities() com o mesmo bug de reflexão.
        from src.core.dxf_loader import DXFLoader, RenderMode
        self._pkl = DXFLoader.load_dxf(str(self.source_dxf_path), mode=RenderMode.TRUE_GEOMETRY)
        log.debug("DXFLoader geometry: %d lines, %d polylines, %d texts, %d circles",
                  len(self._pkl.get('lines', [])),
                  len(self._pkl.get('polylines', [])),
                  len(self._pkl.get('texts', [])),
                  len(self._pkl.get('circles', [])))

    # ──────────────────────────────────────────────────────────────────────
    # Descoberta de elementos
    # ──────────────────────────────────────────────────────────────────────
    def _discover_elements(self) -> list[tuple]:
        """Retorna lista de (elem_id, label_positions, frame_bboxes)."""
        if self.er_type in ('PIL', 'LV'):
            return self._discover_frame_based()
        elif self.er_type == 'FV':
            return self._discover_fv()
        else:  # LAJ
            return self._discover_laj()

    def _discover_frame_based(self) -> list[tuple]:
        """PIL/LV: frames 9999999999 + labels em Texto Seção.

        Estratégia:
        1. Encontrar frames (blocos 9999999999) → bbox de conteúdo (sem title block)
        2. Encontrar labels em 'Texto Seção'
        3. Para cada elemento: merge dos frames que contêm suas labels
        4. Para pilares multi-frame (P27, etc.): detectar frames extras à esquerda
           olhando se face A está mais de 0.7×PITCH à direita do frame que a contém
        """
        msp = self._dxf.modelspace()

        # 1. Frames — bbox de conteúdo: x1 e y1 iguais ao inner frame,
        #             y0 acima do title block, x0 do inner (o left pode ter margem variável)
        bx0, by0, bx1, by1 = BLK_FRAME_INNER
        frames = []  # lista de (x0, y0, x1, y1) — content area
        for e in msp:
            if e.dxftype() == 'INSERT' and e.dxf.name == '9999999999':
                ix, iy = float(e.dxf.insert.x), float(e.dxf.insert.y)
                frames.append((
                    ix + bx0,
                    iy + by0 + FRAME_TITLE_BLOCK_H,
                    ix + bx1,
                    iy + by1,
                ))

        if not frames:
            log.warning("Nenhum frame 9999999999 encontrado — fallback para expansão de bbox")
            return self._discover_by_expansion()

        # 2. Labels
        if self.er_type == 'PIL':
            label_pat = re.compile(r'^(P\d+)\.[A-Z]$')
            pat_multi_sec = None
            pat_extract_names = None
        else:
            # Padrão 1: seção só no final — "V1.A", "V1-V2.A"
            label_pat = re.compile(
                r'^(?:CONT\.\s+)?'
                r'(V[A-Z]?\d+(?:[A-Z])?(?:\s*[-/eE]\s*V[A-Z]?\d+(?:[A-Z])?)*)\s*\.\s*[A-Z]$'
            )
            # Padrão 2: seção em cada viga — "V323.C - V328.C"
            pat_multi_sec = re.compile(
                r'^(?:CONT\.\s+)?'
                r'(V[A-Z]?\d+(?:[A-Z])?)\s*\.\s*[A-Z]'
                r'(\s*[-/eE]\s*V[A-Z]?\d+(?:[A-Z])?\s*\.\s*[A-Z])+$'
            )
            pat_extract_names = re.compile(r'(V[A-Z]?\d+(?:[A-Z])?)\s*\.\s*[A-Z]')

        elem_labels: dict[str, list] = {}
        for e in msp:
            if not hasattr(e.dxf, 'layer'): continue
            if 'Se' not in e.dxf.layer: continue
            if e.dxftype() != 'TEXT': continue
            txt = e.dxf.text.strip()

            eid = None
            m = label_pat.match(txt)
            if m:
                eid_raw = m.group(1)
                eid = re.sub(r'\s*[-/eE]\s*', '-', eid_raw)
            elif pat_multi_sec and pat_multi_sec.match(txt):
                names = pat_extract_names.findall(txt)
                if names:
                    eid = '-'.join(names)

            if eid:
                p = e.dxf.insert
                elem_labels.setdefault(eid, []).append((float(p.x), float(p.y)))

        if not elem_labels:
            log.warning("Nenhuma label encontrada em 'Texto Seção' — fallback")
            return self._discover_by_expansion()

        # 3. Mapear cada elemento → frames com suas labels
        results = []
        for eid, label_pts in sorted(elem_labels.items(), key=lambda x: _sort_key_elem(x[0])):
            # Frames que contêm labels deste elemento
            labeled_idx = set()
            for lx, ly in label_pts:
                for i, (fx0, fy0, fx1, fy1) in enumerate(frames):
                    if fx0 <= lx <= fx1 and fy0 <= ly <= fy1:
                        labeled_idx.add(i)

            if not labeled_idx:
                log.debug("  Label %s não mapeou nenhum frame", eid)
                continue

            labeled_frames = [frames[i] for i in labeled_idx]

            if self.er_type == 'LV':
                # LV: vigas podem continuar em frames de ROWS diferentes (seções CONT.)
                # Agrupar frames por row (mesma faixa Y) e criar UMA bbox por row
                # Isso evita que entidades no gap entre rows sejam capturadas
                lv_row_groups: dict[int, list] = {}
                for f in labeled_frames:
                    placed = False
                    for key_fy0 in list(lv_row_groups.keys()):
                        if abs(f[1] - key_fy0) <= 100:
                            lv_row_groups[key_fy0].append(f)
                            placed = True
                            break
                    if not placed:
                        lv_row_groups[int(f[1])] = [f]
                # Uma bbox por grupo de row (merged apenas dentro do row)
                multi_bboxes = [_merge_bboxes(grp) for grp in lv_row_groups.values()]
                results.append((eid, label_pts, multi_bboxes))
                continue  # pular o merge e append abaixo
            else:
                # PIL: usar apenas o grupo de rows com mais frames (seção primária)
                # Frames na mesma row: |fy0 - fy0_ref| <= 100
                row_groups: dict[int, list] = {}
                for f in labeled_frames:
                    placed = False
                    for key_fy0 in list(row_groups.keys()):
                        if abs(f[1] - key_fy0) <= 100:
                            row_groups[key_fy0].append(f)
                            placed = True
                            break
                    if not placed:
                        row_groups[int(f[1])] = [f]

                primary_row_frames = max(row_groups.values(), key=len)
                if len(row_groups) > 1:
                    log.debug("  %s: labels em %d rows distintas → usando row primária (%d frames)",
                              eid, len(row_groups), len(primary_row_frames))

                # Adicionar frames adjacentes NA MESMA ROW (para elementos multi-frame adjacentes)
                primary_y0 = primary_row_frames[0][1]
                same_row_frames = sorted(
                    [f for f in frames if abs(f[1] - primary_y0) <= 100],
                    key=lambda f: f[0]
                )
                primary_x_set = {f[0] for f in primary_row_frames}
                prim_indices = [i for i, f in enumerate(same_row_frames) if f[0] in primary_x_set]

                if prim_indices:
                    min_idx, max_idx = min(prim_indices), max(prim_indices)
                    merged_frames = same_row_frames[min_idx:max_idx + 1]
                    # Para multi-frame: verificar se leftmost label está perto do left edge
                    # → adicionar frame adjacente à esquerda
                    if len(primary_row_frames) >= 2 and min_idx > 0:
                        leftmost_lf = min(primary_row_frames, key=lambda f: f[0])
                        lf_width = leftmost_lf[2] - leftmost_lf[0]
                        min_lx_in_leftmost = min(
                            lx for lx, ly in label_pts
                            if leftmost_lf[0] <= lx <= leftmost_lf[2]
                        )
                        ratio = (min_lx_in_leftmost - leftmost_lf[0]) / lf_width if lf_width > 0 else 1.0
                        if ratio < 0.40:
                            merged_frames = same_row_frames[min_idx - 1:max_idx + 1]
                            log.debug("  %s: +1 frame extra (multi-frame ratio=%.2f)", eid, ratio)
                else:
                    merged_frames = primary_row_frames

            merged = _merge_bboxes(merged_frames)
            results.append((eid, label_pts, [merged]))

        return results

    def _discover_fv(self) -> list[tuple]:
        """FV: NOMENCLATURA labels → grupos por viga ID.

        Layout FV: labels ficam no TOPO esquerdo de cada fundo de viga.
        Conteúdo estende-se para baixo (y0) e para a direita (x1) da label.

        Medidas empiricamente validadas (Obra TREINO_1 Pav 13):
          - conteúdo estende max ~120 unidades ABAIXO do min(label_y)
          - conteúdo estende max ~50 unidades ACIMA do max(label_y)
          - largura do fundo: ~1250-1345 unidades à direita da label

        Suporta formatos de label:
          - Viga simples:   "V312.A"
          - Multi (final):  "V313-V315V-V317.A"  (seção só no fim)
          - Multi (cada):   "V323.C - V328.C"    (seção em cada viga)
          - Com CONT.:      "CONT. V312.A"
        """
        msp = self._dxf.modelspace()

        # Padrão 1: seção no final — "V1.A", "V1-V2.A", "CONT. V1.A"
        pat_single_sec = re.compile(
            r'^(?:CONT\.\s+)?'
            r'(V[A-Z]?\d+(?:[A-Z])?'        # primeira viga
            r'(?:\s*[-/eE]\s*V[A-Z]?\d+(?:[A-Z])?)*'  # vigas adicionais
            r')\s*\.\s*[A-Z]$'
        )

        # Padrão 2: seção em cada viga — "V323.C - V328.C", "V1.A-V2.A"
        pat_multi_sec = re.compile(
            r'^(?:CONT\.\s+)?'
            r'(V[A-Z]?\d+(?:[A-Z])?)\s*\.\s*[A-Z]'   # primeira viga.seção
            r'(\s*[-/eE]\s*'                             # separador
            r'V[A-Z]?\d+(?:[A-Z])?\s*\.\s*[A-Z]'       # próxima viga.seção
            r')+$'                                       # uma ou mais repetições
        )

        # Extrator de todos os nomes de viga de um texto multi-seção
        pat_extract_names = re.compile(r'(V[A-Z]?\d+(?:[A-Z])?)\s*\.\s*[A-Z]')

        elem_labels: dict[str, list] = {}
        for e in msp:
            if not hasattr(e.dxf, 'layer'): continue
            if e.dxf.layer != 'NOMENCLATURA': continue
            if e.dxftype() not in ('TEXT', 'MTEXT'): continue
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()

            eid = None

            # Tenta padrão 1 (seção apenas no final): "V312.A", "V313-V315V-V317.A"
            m = pat_single_sec.match(txt)
            if m:
                eid_raw = m.group(1)
                eid = re.sub(r'\s*[-/eE]\s*', '-', eid_raw)
            else:
                # Tenta padrão 2 (seção em cada viga): "V323.C - V328.C"
                m2 = pat_multi_sec.match(txt)
                if m2:
                    names = pat_extract_names.findall(txt)
                    if names:
                        eid = '-'.join(names)

            if eid:
                p = e.dxf.insert
                elem_labels.setdefault(eid, []).append((float(p.x), float(p.y)))

        results = []
        for eid, pts in sorted(elem_labels.items(), key=lambda x: _sort_key_elem(x[0])):
            lxs = [p[0] for p in pts]; lys = [p[1] for p in pts]
            # Label ao TOPO esquerdo — conteúdo desce e vai para direita
            x0 = min(lxs) - 30
            y0 = min(lys) - 130     # conteúdo estende max ~120 abaixo da label inferior
            x1 = min(lxs) + 1500   # largura FV ~1250-1345, margem extra
            y1 = max(lys) + 50     # pequena margem acima da label superior
            results.append((eid, pts, [(x0, y0, x1, y1)]))

        return results

    def _discover_laj(self) -> list[tuple]:
        """LAJ: layer '4' labels → grupos por L-ID.

        Layout LAJ: planta de lajes em grid 2D.
        Labels ficam aproximadamente no CENTRO de cada bay de laje.
        Vizinhas compartilham bordas (shared boundary entities).

        Medidas empiricamente validadas (Obra TREINO_1 Pav 13):
          - pitch horizontal entre labels: ~430 unidades
          - pitch vertical entre rows: ~260-280 unidades
          - bbox segura: label ± (400, 230)
        """
        msp = self._dxf.modelspace()
        label_pat = re.compile(r'^L(\d+)$')

        elem_labels: dict[str, list] = {}
        for e in msp:
            if not hasattr(e.dxf, 'layer'): continue
            if e.dxftype() not in ('TEXT', 'MTEXT'): continue
            txt = (e.dxf.text if e.dxftype() == 'TEXT' else e.text).strip()
            if label_pat.match(txt):
                eid = txt
                p = e.dxf.insert
                elem_labels.setdefault(eid, []).append((float(p.x), float(p.y)))

        # Calcular distâncias entre labels para ajustar bbox dinamicamente
        all_xs = sorted(set(round(p, -1) for pts in elem_labels.values() for x, y in pts for p in [x]))
        all_ys = sorted(set(round(p, -1) for pts in elem_labels.values() for x, y in pts for p in [y]))

        # Construir lookup de todos os centroides de laje
        all_centroids = {
            eid2: (sum(p[0] for p in pts2)/len(pts2), sum(p[1] for p in pts2)/len(pts2))
            for eid2, pts2 in elem_labels.items()
        }

        results = []
        for eid in sorted(elem_labels.keys(), key=lambda x: int(x[1:])):
            pts = elem_labels[eid]
            lxs = [p[0] for p in pts]; lys = [p[1] for p in pts]
            cx = sum(lxs) / len(lxs)
            cy = sum(lys) / len(lys)

            # Voronoi com filtragem por proximidade de eixo:
            # Para limites em X: usar apenas vizinhos com |dy| < ROW_TOL (mesmo row)
            # Para limites em Y: usar apenas vizinhos com |dx| < COL_TOL (mesma coluna)
            ROW_TOL = 150   # tolerância vertical para considerar "mesmo row"
            COL_TOL = 400   # tolerância horizontal para considerar "mesma coluna"
            MARGIN_X = 60   # margem extra past midpoint em X (bordas compartilhadas)
            MARGIN_Y = 30   # margem extra past midpoint em Y (linhas de separação mais apertadas)
            MAX_HALF_X = 350
            MAX_HALF_Y = 200

            same_row = [(cx2, cy2) for eid2, (cx2, cy2) in all_centroids.items()
                        if eid2 != eid and abs(cy2 - cy) < ROW_TOL]
            same_col = [(cx2, cy2) for eid2, (cx2, cy2) in all_centroids.items()
                        if eid2 != eid and abs(cx2 - cx) < COL_TOL]

            left_xs  = [c[0] for c in same_row if c[0] < cx - 10]
            right_xs = [c[0] for c in same_row if c[0] > cx + 10]
            below_ys = [c[1] for c in same_col if c[1] < cy - 10]
            above_ys = [c[1] for c in same_col if c[1] > cy + 10]

            x0 = (max(left_xs) + cx) / 2 - MARGIN_X if left_xs  else cx - MAX_HALF_X
            x1 = (min(right_xs) + cx) / 2 + MARGIN_X if right_xs else cx + MAX_HALF_X
            y0 = (max(below_ys) + cy) / 2 - MARGIN_Y if below_ys else cy - MAX_HALF_Y
            y1 = (min(above_ys) + cy) / 2 + MARGIN_Y if above_ys else cy + MAX_HALF_Y

            bbox = (
                self._laj_bbox_from_dimension_hint(eid, cx, cy)
                or self._laj_bbox_from_structural_edges(cx, cy)
                or self._expand_laj_bbox_from_panel_edges(
                    (x0, y0, x1, y1),
                    eid=eid,
                    all_centroids=all_centroids,
                )
            )
            bboxes = [bbox]
            if not _pt_in_bbox(cx, cy, bbox):
                bboxes.append((cx - 2.0, cy - 2.0, cx + 2.0, cy + 2.0))
            results.append((eid, pts, bboxes))

        return results

    def _load_laj_dimension_hints(self) -> dict[str, dict]:
        if self._laj_dimension_hints is not None:
            return self._laj_dimension_hints
        hints: dict[str, tuple[float, float]] = {}
        try:
            parts = list(self.source_dxf_path.parts)
            obra_root = None
            for i, part in enumerate(parts):
                if part == "DADOS-OBRAS" and i + 1 < len(parts):
                    obra_root = Path(*parts[: i + 2])
                    break
            if obra_root:
                json_dir = obra_root / "Fase-4_Sincronizacao" / "JSON_Lajes"
                for path in json_dir.glob("L*.json"):
                    try:
                        import json as _json
                        data = _json.loads(path.read_text(encoding="utf-8"))
                        comp = float(data.get("comprimento") or 0)
                        larg = float(data.get("largura") or 0)
                        if comp > 0 and larg > 0:
                            pose = data.get("_stog_pose") or {}
                            hints[path.stem.upper()] = {
                                "width": comp,
                                "height": larg,
                                "x": pose.get("x"),
                                "y": pose.get("y"),
                            }
                    except Exception:
                        continue
        except Exception:
            hints = {}
        self._laj_dimension_hints = hints
        return hints

    def _laj_geometry_layers(self, *, include_context: bool = False) -> set[str]:
        if include_context in self._laj_layer_cache:
            return self._laj_layer_cache[include_context]
        if not self._pkl:
            return set()
        lengths: dict[str, list[float]] = {}
        numeric: dict[str, int] = {}

        def _add(x0, y0, x1, y1, layer):
            dx = abs(float(x1) - float(x0))
            dy = abs(float(y1) - float(y0))
            length = (dx * dx + dy * dy) ** 0.5
            if length < 2.0 or length > 3300.0 or (dx > 0.75 and dy > 0.75):
                return
            row = lengths.setdefault(str(layer or ""), [0.0, 0.0])
            row[0 if dy <= 0.75 else 1] += length

        for line in self._pkl.get("lines", []):
            start, end = line.get("start"), line.get("end")
            if start and end:
                _add(start[0], start[1], end[0], end[1], line.get("layer"))
        for poly in self._pkl.get("polylines", []):
            points = poly.get("points") or []
            for start, end in zip(points, points[1:]):
                _add(start[0], start[1], end[0], end[1], poly.get("layer"))
        for text in self._pkl.get("texts", []):
            value = str(text.get("text") or "").strip().replace(",", ".")
            if re.fullmatch(r"\d+(?:\.\d+)?", value):
                layer = str(text.get("layer") or "")
                numeric[layer] = numeric.get(layer, 0) + 1

        candidates = [
            (numeric.get(layer, 0), sum(axes), layer)
            for layer, axes in lengths.items()
            if sum(axes) > 0 and axes[0] > 0 and axes[1] > 0
        ]
        if not candidates:
            result = set()
        else:
            candidates.sort(reverse=True)
            primary = candidates[0][2]
            result = {primary}
            if include_context:
                peak = max(sum(axes) for axes in lengths.values())
                result.update(
                    layer for layer, axes in lengths.items()
                    if sum(axes) >= max(20.0, peak * 0.10)
                )
        self._laj_layer_cache[include_context] = result
        return result

    def _laj_bbox_from_dimension_hint(self, eid: str, cx: float, cy: float) -> tuple | None:
        """Escolhe bordas ER locais usando dimensoes N1/SA da mesma laje."""
        hint = self._load_laj_dimension_hints().get(str(eid).upper())
        if not hint or not self._pkl:
            return None
        exp_w = float(hint.get("width") or 0)
        exp_h = float(hint.get("height") or 0)
        if exp_w <= 0 or exp_h <= 0:
            return None
        pose_x = hint.get("x")
        pose_y = hint.get("y")
        if pose_x is not None and pose_y is not None and exp_w <= 1250.0 and exp_h <= 850.0:
            pose_x = float(pose_x)
            pose_y = float(pose_y)
            center_x = pose_x + exp_w / 2.0
            center_y = pose_y + exp_h / 2.0
            if abs(cx - center_x) <= exp_w * 0.75 + 100.0 and abs(cy - center_y) <= exp_h + 150.0:
                return (
                    pose_x - 1.0,
                    pose_y - 1.0,
                    pose_x + exp_w + 1.0,
                    pose_y + exp_h + 1.0,
                )

        def _merged_h_segments(h_segments: list[tuple[float, float, float]]):
            by_y: dict[float, list[tuple[float, float]]] = {}
            for y, x0, x1 in h_segments:
                by_y.setdefault(y, []).append((x0, x1))
            merged: list[tuple[float, float, float]] = []
            for y, spans in by_y.items():
                current: list[list[float]] = []
                for x0, x1 in sorted(spans):
                    if not current or x0 > current[-1][1] + 1.5:
                        current.append([x0, x1])
                    else:
                        current[-1][1] = max(current[-1][1], x1)
                merged.extend((y, x0, x1) for x0, x1 in current)
            return merged

        def _solve(layer_keys: set[str]) -> tuple | None:
            h_segments: list[tuple[float, float, float]] = []
            v_segments: list[tuple[float, float, float]] = []

            def _add_seg(xa, ya, xb, yb, layer):
                if _layer_key(layer) not in layer_keys:
                    return
                xa, ya, xb, yb = map(float, (xa, ya, xb, yb))
                w = abs(xb - xa)
                h = abs(yb - ya)
                if h <= 0.75 and w >= 20.0:
                    h_segments.append((round((ya + yb) / 2.0, 1), min(xa, xb), max(xa, xb)))
                elif w <= 0.75 and h >= 20.0:
                    v_segments.append((round((xa + xb) / 2.0, 1), min(ya, yb), max(ya, yb)))

            for ln in self._pkl.get("lines", []):
                s = ln.get("start")
                e = ln.get("end")
                if s and e:
                    _add_seg(s[0], s[1], e[0], e[1], ln.get("layer"))
            for pl in self._pkl.get("polylines", []):
                pts = pl.get("points") or []
                if len(pts) < 2:
                    continue
                seq = list(pts)
                if pl.get("closed") or pl.get("is_closed"):
                    seq.append(seq[0])
                for a, b in zip(seq, seq[1:]):
                    _add_seg(a[0], a[1], b[0], b[1], pl.get("layer"))

            h_segments.extend(_merged_h_segments(h_segments))

            h_coords = sorted({
                y for y, x0, x1 in h_segments
                if x0 - 10.0 <= cx <= x1 + 10.0
            })
            y_pairs = []
            for y0 in h_coords:
                for y1 in h_coords:
                    if y0 < cy < y1:
                        height = y1 - y0
                        if abs(height - exp_h) <= max(15.0, exp_h * 0.12):
                            score = abs(height - exp_h) + abs((y0 + y1) / 2.0 - cy) * 0.02
                            y_pairs.append((score, y0, y1))
            if not y_pairs:
                return None
            _, y0, y1 = min(y_pairs, key=lambda r: r[0])

            min_overlap = min(max(20.0, (y1 - y0) * 0.18), y1 - y0)
            x_candidates = []
            for x, vy0, vy1 in v_segments:
                overlap = max(0.0, min(y1, vy1) - max(y0, vy0))
                if overlap >= min_overlap:
                    x_candidates.append(x)
            x_candidates = sorted(set(round(x, 1) for x in x_candidates))

            x_pairs = []
            for x0 in x_candidates:
                if x0 >= cx:
                    continue
                for x1 in x_candidates:
                    if x1 <= cx:
                        continue
                    width = x1 - x0
                    if abs(width - exp_w) <= max(18.0, exp_w * 0.08):
                        score = abs(width - exp_w) + abs((x0 + x1) / 2.0 - cx) * 0.02
                        x_pairs.append((score, x0, x1, abs(width - exp_w)))

            spans = [
                (x0, x1, abs((x1 - x0) - exp_w)) for y, x0, x1 in h_segments
                if (abs(y - y0) <= 0.75 or abs(y - y1) <= 0.75)
                and x0 - 10.0 <= cx <= x1 + 10.0
                and abs((x1 - x0) - exp_w) <= max(24.0, exp_w * 0.10)
            ]

            if x_pairs and spans:
                best_pair = min(x_pairs, key=lambda r: r[0])
                best_span = min(spans, key=lambda s: (s[2], abs((s[0] + s[1]) / 2.0 - cx)))
                if best_span[2] + 1.0 < best_pair[3]:
                    x0, x1 = best_span[0], best_span[1]
                else:
                    _, x0, x1, _ = best_pair
            elif x_pairs:
                _, x0, x1, _ = min(x_pairs, key=lambda r: r[0])
            elif spans:
                x0, x1, _ = min(spans, key=lambda s: (s[2], abs((s[0] + s[1]) / 2.0 - cx)))
            else:
                return None

            if not (x0 < cx < x1 and y0 < cy < y1):
                return None
            return (x0 - 1.0, y0 - 1.0, x1 + 1.0, y1 + 1.0)

        primary_layers = {_layer_key(layer) for layer in self._laj_geometry_layers()}
        all_layers = {
            _layer_key(layer)
            for layer in self._laj_geometry_layers(include_context=True)
        }
        bbox = _solve(all_layers - primary_layers)
        return bbox or _solve(all_layers)

    def _laj_bbox_from_structural_edges(self, cx: float, cy: float) -> tuple | None:
        """BBox LAJ fechada por bordas estruturais locais ao redor do label.

        O recorte aprovado de lajes usa o contorno da laje/apoios imediatos.
        A expansao por Voronoi capturava faixas vizinhas; aqui buscamos os
        spans horizontais das layers estruturais e montamos a janela local.
        """
        if not self._pkl:
            return None

        h_segments: list[tuple[float, float, float]] = []
        v_segments: list[tuple[float, float, float]] = []

        def _add_seg(xa, ya, xb, yb, layer):
            key = _layer_key(layer)
            if key not in {_layer_key(value) for value in self._laj_geometry_layers(include_context=True)}:
                return
            xa, ya, xb, yb = map(float, (xa, ya, xb, yb))
            w = abs(xb - xa)
            h = abs(yb - ya)
            if w < 35.0 and h < 35.0:
                return
            if h <= 0.75 and w >= 35.0:
                h_segments.append((round((ya + yb) / 2.0, 1), min(xa, xb), max(xa, xb)))
            elif w <= 0.75 and h >= 35.0:
                v_segments.append((round((xa + xb) / 2.0, 1), min(ya, yb), max(ya, yb)))

        for ln in self._pkl.get("lines", []):
            s = ln.get("start")
            e = ln.get("end")
            if s and e:
                _add_seg(s[0], s[1], e[0], e[1], ln.get("layer"))

        for pl in self._pkl.get("polylines", []):
            pts = pl.get("points") or []
            if len(pts) < 2:
                continue
            seq = list(pts)
            if pl.get("closed") or pl.get("is_closed"):
                seq.append(seq[0])
            for a, b in zip(seq, seq[1:]):
                _add_seg(a[0], a[1], b[0], b[1], pl.get("layer"))

        def _merge_spans(spans: list[tuple[float, float, float]], gap: float = 28.0):
            by_coord: dict[float, list[tuple[float, float]]] = {}
            for coord, a, b in spans:
                by_coord.setdefault(coord, []).append((a, b))
            merged: list[tuple[float, float, float]] = []
            for coord, ranges in by_coord.items():
                current: list[list[float]] = []
                for a, b in sorted(ranges):
                    if not current or a > current[-1][1] + gap:
                        current.append([a, b])
                    else:
                        current[-1][1] = max(current[-1][1], b)
                merged.extend((coord, a, b) for a, b in current)
            return merged

        h_merged = _merge_spans(h_segments)
        v_merged = _merge_spans([(x, y0, y1) for x, y0, y1 in v_segments])

        covering_h = [
            (y, x0, x1) for y, x0, x1 in h_merged
            if x0 - 8.0 <= cx <= x1 + 8.0 and 45.0 <= (x1 - x0) <= 3200.0
        ]
        below = sorted((seg for seg in covering_h if seg[0] < cy - 2.0), key=lambda s: cy - s[0])
        above = sorted((seg for seg in covering_h if seg[0] > cy + 2.0), key=lambda s: s[0] - cy)
        if not below or not above:
            return None

        y0, hx0a, hx1a = below[0]
        y1, hx0b, hx1b = above[0]
        if y1 <= y0:
            return None

        x0 = min(hx0a, hx0b)
        x1 = max(hx1a, hx1b)

        # Ajusta laterais usando verticais estruturais que coincidem com as
        # extremidades dos spans horizontais; evita escolher divisao interna.
        height = y1 - y0
        if height > 0:
            overlap_candidates = []
            for x, vy0, vy1 in v_merged:
                overlap = max(0.0, min(y1, vy1) - max(y0, vy0))
                if overlap >= min(height * 0.55, height - 1.0):
                    overlap_candidates.append((x, vy0, vy1))
            lefts = [x for x, _, _ in overlap_candidates if x <= x0 + 30.0]
            rights = [x for x, _, _ in overlap_candidates if x >= x1 - 30.0]
            if lefts:
                x0 = min(lefts, key=lambda x: abs(x - x0))
            if rights:
                x1 = min(rights, key=lambda x: abs(x - x1))

        width = x1 - x0
        height = y1 - y0
        if width < 45.0 or height < 45.0 or width > 3300.0 or height > 700.0:
            return None

        return (x0 - 6.0, y0 - 6.0, x1 + 6.0, y1 + 6.0)

    def _expand_laj_bbox_from_panel_edges(
        self,
        bbox: tuple,
        *,
        eid: str,
        all_centroids: dict[str, tuple],
    ) -> tuple:
        """Expand LAJ crop to nearby panel geometry so the slab frame closes."""
        if not self._pkl:
            return bbox

        margin = 60.0
        pad = 12.0
        candidates = []
        panel_layers = {_layer_key(value) for value in self._laj_geometry_layers()}

        def _add_segment(x0, y0, x1, y1):
            w = abs(x1 - x0)
            h = abs(y1 - y0)
            if max(w, h) < 20.0 or max(w, h) > 800.0:
                return
            if w >= 1.0 and h >= 1.0:
                return
            mx = (x0 + x1) / 2.0
            my = (y0 + y1) / 2.0
            if _pt_in_bbox(mx, my, bbox, margin=margin):
                candidates.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))

        for ln in self._pkl.get('lines', []):
            if _layer_key(ln.get('layer')) not in panel_layers:
                continue
            s = ln.get('start')
            e = ln.get('end')
            if not s or not e:
                continue
            _add_segment(float(s[0]), float(s[1]), float(e[0]), float(e[1]))

        for pl in self._pkl.get('polylines', []):
            if _layer_key(pl.get('layer')) not in panel_layers:
                continue
            pts = pl.get('points') or []
            for a, b in zip(pts, pts[1:]):
                _add_segment(float(a[0]), float(a[1]), float(b[0]), float(b[1]))

        if len(candidates) < 3:
            return bbox

        panel_bbox = (
            min(b[0] for b in candidates),
            min(b[1] for b in candidates),
            max(b[2] for b in candidates),
            max(b[3] for b in candidates),
        )
        expanded = (
            min(bbox[0], panel_bbox[0]) - pad,
            min(bbox[1], panel_bbox[1]) - pad,
            max(bbox[2], panel_bbox[2]) + pad,
            max(bbox[3], panel_bbox[3]) + pad,
        )
        expanded = _shrink_bbox_away_from_laj_labels(expanded, eid, all_centroids)

        w = expanded[2] - expanded[0]
        h = expanded[3] - expanded[1]
        if w <= 0 or h <= 0 or w > 1250 or h > 850:
            return bbox
        return expanded

    def _discover_by_expansion(self) -> list[tuple]:
        """Fallback: expansão de bbox sem frames."""
        log.warning("_discover_by_expansion não implementado — retornando lista vazia")
        return []

    # ──────────────────────────────────────────────────────────────────────
    # Extração de um elemento
    # ──────────────────────────────────────────────────────────────────────
    def _extract_one(
        self,
        elem_id: str,
        label_positions: list,
        frame_bboxes: list,
        output_dir: Path,
        *,
        overwrite: bool = False,
    ) -> dict:
        ts = int(time.time() * 100)
        fname = f"{self.er_type}_{elem_id}_motor_{ts}.dxf"
        out_path = output_dir / fname

        # Verificar se já existe recorte para este elem_id (skip quando overwrite=False)
        if not overwrite:
            existing = sorted(output_dir.glob(f"{self.er_type}_{elem_id}_motor_*.dxf"))
            if existing:
                existing_path = existing[-1]  # mais recente
                try:
                    check = ezdxf.readfile(str(existing_path))
                    ents_existing = []
                    for entity in check.modelspace():
                        t = entity.dxftype()
                        if t == 'LINE':
                            ents_existing.append(('line', {}))
                        elif t == 'LWPOLYLINE':
                            ents_existing.append(('poly', {'closed': bool(entity.closed)}))
                        elif t in ('TEXT', 'MTEXT'):
                            ents_existing.append(('text', {}))
                        elif t == 'HATCH':
                            ents_existing.append(('hatch', {}))
                    n = len(ents_existing)
                    conf = self._compute_confidence(ents_existing, elem_id=elem_id)
                    return {
                        'elemento_id': elem_id, 'recorte_path': str(existing_path),
                        'bbox_json': '{}', 'entity_count': n, 'status': 'motor',
                        'confidence': conf,
                    }
                except Exception:
                    pass

        # Coletar entidades nas bboxes de frame
        all_ents = []
        search_bboxes = list(frame_bboxes)

        # PIL/LV: coleta dentro dos frames (bbox fixa, sem expansão)
        # FV/LAJ: coleta com bbox fixa calculada em _discover_*
        #   FV/LAJ NÃO usa expansão iterativa — a bbox calculada já é precisa
        all_ents = self._collect_in_bboxes(search_bboxes)

        # 2ª passagem de refinamento apenas para PIL/LV com bbox única
        # (sem risco de capturar entidades entre rows)
        if self.er_type in ('PIL', 'LV') and all_ents and len(search_bboxes) == 1:
            pts = _all_pts_from_ents(all_ents)
            if pts:
                tighter = _pts_to_bbox(pts, margin=5)
                extra = self._collect_in_bboxes([tighter])
                all_ents = _deduplicate(all_ents + extra)

        if not all_ents:
            raise RuntimeError(f"Nenhuma entidade encontrada para {elem_id}")

        # Computar bbox final
        pts = _all_pts_from_ents(all_ents)
        bbox = _pts_to_bbox(pts) if pts else (0, 0, 0, 0)

        # Salvar DXF
        self._save_recorte_dxf(all_ents, out_path)

        confidence = self._compute_confidence(
            all_ents,
            elem_id=elem_id,
            label_positions=label_positions,
            search_bboxes=search_bboxes,
            final_bbox=bbox,
        )

        return {
            'elemento_id': elem_id,
            'recorte_path': str(out_path),
            'bbox_json': f'{{"x0":{bbox[0]:.2f},"y0":{bbox[1]:.2f},"x1":{bbox[2]:.2f},"y1":{bbox[3]:.2f}}}',
            'entity_count': len(all_ents),
            'confidence': confidence,
            'status': 'motor',
        }

    # ──────────────────────────────────────────────────────────────────────
    # Coleta de entidades por bbox
    # ──────────────────────────────────────────────────────────────────────
    def _collect_in_bboxes(self, bboxes: list) -> list:
        """Coleta entidades do pkl dentro de qualquer bbox.

        Critério de captura:
        - Line:     centróide OU qualquer extremidade dentro da bbox
                    (garante bordas de retângulos que cruzam o limite)
        - Polyline: centróide OU qualquer vértice dentro da bbox
        - Text:     posição de inserção dentro da bbox
        - Hatch:    centróide dos pontos do boundary dentro da bbox
        - Circle:   centro dentro da bbox (somente se _include_circles)
        """
        found = []
        seen = set()

        lines = self._pkl.get('lines', [])
        polys = self._pkl.get('polylines', [])

        # ── Lines ────────────────────────────────────────────────────────────
        for i, ln in enumerate(lines):
            if self.er_type == 'LAJ' and not _is_laj_relevant_entity('line', ln):
                continue
            s, e2 = ln['start'], ln['end']
            if self.er_type == 'LAJ':
                clipped = _clip_line_to_bboxes(ln, bboxes)
                if clipped:
                    for j, clipped_ln in enumerate(clipped):
                        key = ('l', i, j)
                        if key not in seen:
                            seen.add(key); found.append(('line', clipped_ln))
                continue
            cx = (s[0] + e2[0]) / 2; cy = (s[1] + e2[1]) / 2
            # Captura se centróide OR qualquer extremidade está dentro
            if any(
                _pt_in_bbox(cx, cy, b)
                or _pt_in_bbox(s[0], s[1], b)
                or _pt_in_bbox(e2[0], e2[1], b)
                for b in bboxes
            ):
                key = ('l', i)
                if key not in seen:
                    seen.add(key); found.append(('line', ln))

        # ── Polylines ─────────────────────────────────────────────────────────
        for i, pl in enumerate(polys):
            if self.er_type == 'LAJ' and not _is_laj_relevant_entity('poly', pl):
                continue
            pts = pl['points']
            if not pts: continue
            # Excluir bordas do frame 9999999999
            if pl.get('is_block', False) and _is_frame_border(pts):
                continue
            if self.er_type == 'LAJ':
                clipped = _clip_poly_to_bboxes(pl, bboxes)
                if clipped:
                    for j, clipped_pl in enumerate(clipped):
                        key = ('p', i, j)
                        if key not in seen:
                            seen.add(key); found.append(('poly', clipped_pl))
                continue
            cx = sum(p[0] for p in pts) / len(pts)
            cy = sum(p[1] for p in pts) / len(pts)
            # Captura se centróide OR qualquer vértice está dentro
            if any(
                _pt_in_bbox(cx, cy, b)
                or any(_pt_in_bbox(p[0], p[1], b) for p in pts)
                for b in bboxes
            ):
                key = ('p', i)
                if key not in seen:
                    seen.add(key); found.append(('poly', pl))

        # ── Textos ───────────────────────────────────────────────────────────
        for i, tx in enumerate(self._pkl.get('texts', [])):
            if self.er_type == 'LAJ' and not _is_laj_relevant_entity('text', tx):
                continue
            pos = tx.get('pos')
            if not pos: continue
            cx, cy = float(pos[0]), float(pos[1])
            if any(_pt_in_bbox(cx, cy, b) for b in bboxes):
                key = ('t', i)
                if key not in seen:
                    seen.add(key); found.append(('text', tx))

        # ── Hatches ──────────────────────────────────────────────────────────
        for i, ht in enumerate(self._pkl.get('hatches', [])):
            if self.er_type == 'LAJ' and not _is_laj_relevant_entity('hatch', ht):
                continue
            paths = ht.get('paths', [])
            if not paths: continue
            # Centróide de todos os pontos do boundary
            all_pts = [pt for path in paths for pt in path]
            if not all_pts: continue
            cx = sum(p[0] for p in all_pts) / len(all_pts)
            cy = sum(p[1] for p in all_pts) / len(all_pts)
            if any(_pt_in_bbox(cx, cy, b) for b in bboxes):
                key = ('h', i)
                if key not in seen:
                    seen.add(key); found.append(('hatch', ht))

        # ── Círculos / arcos ─────────────────────────────────────────────────
        if getattr(self, '_include_circles', False):
            for i, ci in enumerate(self._pkl.get('circles', [])):
                center = ci.get('center')
                if not center: continue
                cx, cy = float(center[0]), float(center[1])
                if any(_pt_in_bbox(cx, cy, b) for b in bboxes):
                    key = ('c', i)
                    if key not in seen:
                        seen.add(key); found.append(('circle', ci))

        return found

    def _collect_with_expansion(self, initial_bboxes: list, max_iters: int = 5) -> list:
        """Expansão iterativa de bbox: coleta, expande, repete até estabilizar."""
        current_bboxes = list(initial_bboxes)

        all_ents = []
        for _ in range(max_iters):
            new_ents = self._collect_in_bboxes(current_bboxes)
            if not new_ents: break

            pts = _all_pts_from_ents(new_ents)
            if not pts: break

            new_bbox = _pts_to_bbox(pts, margin=10)
            current_bboxes = [new_bbox]

            if len(new_ents) == len(all_ents):
                break
            all_ents = new_ents

        return all_ents

    # ──────────────────────────────────────────────────────────────────────
    # Confiança do recorte
    # ──────────────────────────────────────────────────────────────────────
    def _compute_confidence(
        self,
        ents: list,
        *,
        elem_id: str | None = None,
        label_positions: list | None = None,
        search_bboxes: list | None = None,
        final_bbox: tuple | None = None,
    ) -> float:
        """Score 0-100 baseado em completude estrutural do recorte.

        Critérios:
        - Presença de linhas       (base estrutural)
        - Polylines fechadas       (formas completas — PIL/LV critical)
        - Hatches                  (preenchimento concreto)
        - Textos                   (nomenclaturas)
        - Contagem dentro do range esperado para a classe
        """
        if not ents:
            return 0.0

        if self.er_type == 'LAJ':
            return self._compute_laj_confidence(
                ents,
                elem_id=elem_id,
                label_positions=label_positions,
                search_bboxes=search_bboxes,
                final_bbox=final_bbox,
            )

        has_lines  = any(t == 'line'  for t, _ in ents)
        has_closed = any(t == 'poly'  and e.get('closed') for t, e in ents)
        has_hatches = any(t == 'hatch' for t, _ in ents)
        has_text   = any(t == 'text'  for t, _ in ents)

        if self.er_type in ('PIL', 'LV'):
            type_score = (
                (0.30 if has_lines   else 0.0) +
                (0.30 if has_closed  else 0.0) +
                (0.25 if has_hatches else 0.0) +
                (0.15 if has_text    else 0.0)
            )
        else:  # FV, LAJ
            type_score = (
                (0.40 if has_lines   else 0.0) +
                (0.30 if any(t == 'poly' for t, _ in ents) else 0.0) +
                (0.15 if has_hatches else 0.0) +
                (0.15 if has_text    else 0.0)
            )

        # Contagem razoável para a classe (detecta outliers extremos)
        count = len(ents)
        _ranges = {'PIL': (100, 2000), 'LV': (50, 5000), 'FV': (20, 2000), 'LAJ': (10, 800)}
        lo, hi = _ranges.get(self.er_type, (10, 5000))
        if lo <= count <= hi:
            count_score = 1.0
        elif count < lo:
            count_score = max(0.0, count / lo)
        else:
            count_score = max(0.0, hi / count)

        return round((0.6 * type_score + 0.4 * count_score) * 100, 1)

    def _compute_laj_confidence(
        self,
        ents: list,
        *,
        elem_id: str | None = None,
        label_positions: list | None = None,
        search_bboxes: list | None = None,
        final_bbox: tuple | None = None,
    ) -> float:
        """LAJ confidence calibrated against local slab-recorte evidence."""
        texts = [
            str(e.get('text') or '').strip()
            for typ, e in ents
            if typ == 'text' and str(e.get('text') or '').strip()
        ]

        line_count = sum(1 for typ, _ in ents if typ == 'line')
        poly_count = sum(1 for typ, _ in ents if typ == 'poly')
        hatch_count = sum(1 for typ, _ in ents if typ == 'hatch')

        label_re = re.compile(r'^L\d+$')
        own_label_count = sum(1 for text in texts if elem_id and text == elem_id)
        other_label_count = sum(1 for text in texts if label_re.match(text) and text != elem_id)
        numeric_count = sum(
            1 for text in texts
            if re.fullmatch(r'\d+(?:[.,]\d+)?(?:/\d+(?:[.,]\d+)?)?', text)
        )
        has_height = any(re.fullmatch(r'h\s*=\s*\d+(?:[.,]\d+)?', text, re.I) for text in texts)
        has_panel_layer = numeric_count >= 2 and line_count >= 4
        has_form_layer = line_count + poly_count >= 4
        contamination_count = other_label_count

        pts = _all_pts_from_ents(ents)
        bbox = final_bbox or (_pts_to_bbox(pts) if pts else None)
        bbox_score = 0.0
        bbox_penalty = 0.0
        if bbox:
            w = max(0.0, bbox[2] - bbox[0])
            h = max(0.0, bbox[3] - bbox[1])
            area = w * h
            if 120 <= w <= 800 and 80 <= h <= 650:
                bbox_score = 1.0
            elif 80 <= w <= 1100 and 60 <= h <= 800:
                bbox_score = 0.65
            else:
                bbox_score = 0.25
            if w > 1200 or h > 900 or area > 700000:
                bbox_penalty += 25.0

        search_score = 1.0
        if search_bboxes and bbox:
            sx0, sy0, sx1, sy1 = _merge_bboxes(search_bboxes)
            sw = max(1.0, sx1 - sx0)
            sh = max(1.0, sy1 - sy0)
            w = max(0.0, bbox[2] - bbox[0])
            h = max(0.0, bbox[3] - bbox[1])
            if w > sw * 1.35 or h > sh * 1.35:
                search_score = 0.35
            elif w > sw * 1.10 or h > sh * 1.10:
                search_score = 0.70

        count = len(ents)
        if 60 <= count <= 220:
            count_score = 1.0
        elif 35 <= count < 60 or 220 < count <= 320:
            count_score = 0.70
        else:
            count_score = 0.35

        score = (
            (18.0 if own_label_count >= 1 else 0.0) +
            (16.0 if line_count >= 20 else max(0.0, line_count / 20.0) * 16.0) +
            (14.0 if numeric_count >= 5 else max(0.0, numeric_count / 5.0) * 14.0) +
            (10.0 if has_panel_layer else 0.0) +
            (8.0 if has_form_layer else 0.0) +
            (8.0 if has_height else 4.0 if own_label_count else 0.0) +
            (14.0 * bbox_score) +
            (6.0 * count_score) +
            (6.0 * search_score)
        )

        if other_label_count:
            score -= min(35.0, other_label_count * 15.0)
        if contamination_count:
            score -= min(35.0, contamination_count * 3.5)
        if poly_count > 8:
            score -= min(18.0, (poly_count - 8) * 1.5)
        if hatch_count > 2:
            score -= min(15.0, (hatch_count - 2) * 2.0)
        score -= bbox_penalty

        if own_label_count == 0:
            score = min(score, 68.0)
        if numeric_count < 3:
            score = min(score, 78.0)
        if count < 50:
            score = min(score, 89.0)

        return round(max(0.0, min(100.0, score)), 1)

    # ──────────────────────────────────────────────────────────────────────
    # Salvar DXF
    # ──────────────────────────────────────────────────────────────────────
    def _save_recorte_dxf(self, ents: list, out_path: Path):
        doc = ezdxf.new('R2010')
        msp = doc.modelspace()

        # Criar layers necessários
        layers_needed = set()
        for typ, e in ents:
            layers_needed.add(e.get('layer', '0'))

        for lyr in layers_needed:
            if lyr not in doc.layers:
                doc.layers.add(lyr)

        for typ, e in ents:
            lyr = e.get('layer', '0')
            color_aci = e.get('aci', 7)
            lw = e.get('lineweight', 25)
            dxf_attrs = {'layer': lyr, 'color': color_aci, 'lineweight': lw}

            if typ == 'line':
                msp.add_line(e['start'], e['end'], dxfattribs=dxf_attrs)
            elif typ == 'poly':
                pts = e['points']
                if len(pts) >= 2:
                    pline = msp.add_lwpolyline(pts, dxfattribs=dxf_attrs)
                    pline.closed = bool(e.get('closed', False))
            elif typ == 'text':
                pos = e.get('pos', (0, 0))
                txt = e.get('text', '')
                height = e.get('height', 10.0)
                rotation = e.get('rotation', 0.0)
                text_attrs = {**dxf_attrs, 'insert': pos, 'height': height, 'rotation': rotation}
                msp.add_text(txt, dxfattribs=text_attrs)
            elif typ == 'circle':
                center = e.get('center', (0, 0))
                radius = e.get('radius', 1.0)
                sa = e.get('start_angle')
                ea = e.get('end_angle')
                arc_attrs = {'layer': lyr, 'color': color_aci}
                if sa is not None and ea is not None and not (sa == 0 and ea == 360):
                    msp.add_arc(center=center, radius=radius,
                                start_angle=sa, end_angle=ea, dxfattribs=arc_attrs)
                else:
                    msp.add_circle(center=center, radius=radius, dxfattribs=arc_attrs)
            elif typ == 'hatch':
                paths = e.get('paths', [])
                if not paths: continue
                try:
                    hatch = msp.add_hatch(color=color_aci, dxfattribs={'layer': lyr})
                    if e.get('solid', True):
                        hatch.set_solid_fill()
                    else:
                        pattern = e.get('pattern_name', 'ANSI31')
                        try:
                            hatch.set_pattern_fill(pattern, scale=1.0)
                        except Exception:
                            hatch.set_solid_fill()
                    for path_pts in paths:
                        if len(path_pts) >= 2:
                            hatch.paths.add_polyline_path(
                                [(float(p[0]), float(p[1])) for p in path_pts],
                                is_closed=True
                            )
                except Exception:
                    pass  # hatch inválido — pular sem quebrar o recorte

        doc.saveas(str(out_path))

    # ──────────────────────────────────────────────────────────────────────
    # Registro no banco de dados
    # ──────────────────────────────────────────────────────────────────────
    def _register_db(self, results: list[dict], db_path: str | Path):
        db_path = Path(db_path)
        if not db_path.exists():
            log.warning("DB não encontrado: %s — pulando registro", db_path)
            return

        obra_name = self.source_dxf_path.stem  # nome sem extensão

        try:
            conn = sqlite3.connect(str(db_path))
            cur = conn.cursor()
            for r in results:
                if not r.get('recorte_path'): continue
                # Verificar se já existe
                cur.execute(
                    "SELECT id FROM reverse_eng_recortes WHERE obra_name=? AND elemento_id=? AND classe=?",
                    (obra_name, r['elemento_id'], self.er_type)
                )
                row = cur.fetchone()
                if row:
                    cur.execute(
                        """UPDATE reverse_eng_recortes
                           SET recorte_path=?, bbox_json=?, entity_count=?, status=?, confidence=?
                           WHERE id=?""",
                        (r['recorte_path'], r['bbox_json'], r['entity_count'],
                         r['status'], r.get('confidence'), row[0])
                    )
                else:
                    cur.execute(
                        """INSERT INTO reverse_eng_recortes
                           (obra_name, elemento_id, recorte_path, bbox_json,
                            entity_count, classe, status, confidence)
                           VALUES (?,?,?,?,?,?,?,?)""",
                        (obra_name, r['elemento_id'], r['recorte_path'],
                         r['bbox_json'], r['entity_count'], self.er_type,
                         r['status'], r.get('confidence'))
                    )
            conn.commit()
            conn.close()
            if self.er_type == 'LAJ':
                try:
                    from src.core.engrev_laj_recorte_learning_store import (
                        record_engrev_laj_recorte_learning_event,
                    )

                    for r in results:
                        if not r.get('recorte_path'):
                            continue
                        record_engrev_laj_recorte_learning_event(
                            db_path,
                            event_type="motor_generated",
                            obra_name=obra_name,
                            classe=self.er_type,
                            elemento_id=r['elemento_id'],
                            source_recorte_path=r['recorte_path'],
                            notes="recorte_motor._register_db",
                            features_extra={"source": "src.core.recorte_motor"},
                        )
                except Exception as exc:
                    log.warning("Falha ao registrar learning events LAJ: %s", exc)
            log.info("DB registrado: %d recortes para '%s'", len(results), obra_name)
        except Exception as exc:
            log.error("Erro ao registrar DB: %s", exc)

    # ──────────────────────────────────────────────────────────────────────
    # Auto-detecção de tipo
    # ──────────────────────────────────────────────────────────────────────
    @staticmethod
    def _detect_type(filename: str) -> str:
        fn = filename.upper()
        if '- PL -' in fn or ' PL ' in fn:
            return 'PIL'
        if '- LV -' in fn or ' LV ' in fn:
            return 'LV'
        if '- FV -' in fn or ' FV ' in fn:
            return 'FV'
        if '- LJ -' in fn or ' LJ ' in fn:
            return 'LAJ'
        raise ValueError(f"Não foi possível detectar er_type de: {filename}")


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _pt_in_bbox(x: float, y: float, b: tuple, margin: float = 0) -> bool:
    return b[0] - margin <= x <= b[2] + margin and b[1] - margin <= y <= b[3] + margin


def _layer_key(layer: str | None) -> str:
    text = str(layer or '')
    text = ''.join(
        c for c in unicodedata.normalize('NFKD', text)
        if not unicodedata.combining(c)
    )
    return text.upper()


def _shrink_bbox_away_from_laj_labels(
    bbox: tuple,
    eid: str,
    all_centroids: dict[str, tuple],
    *,
    clearance: float = 5.0,
) -> tuple:
    """Shrink the least painful side when expansion captures a neighboring slab label."""
    if eid not in all_centroids:
        return bbox
    cx, cy = all_centroids[eid]
    x0, y0, x1, y1 = bbox

    for other_id, (ox, oy) in all_centroids.items():
        if other_id == eid:
            continue
        if not (x0 <= ox <= x1 and y0 <= oy <= y1):
            continue

        options = []
        if ox < cx and ox + clearance < cx:
            value = ox + clearance
            options.append(('x0', value, abs(value - x0)))
        if ox > cx and ox - clearance > cx:
            value = ox - clearance
            options.append(('x1', value, abs(x1 - value)))
        if oy < cy and oy + clearance < cy:
            value = oy + clearance
            options.append(('y0', value, abs(value - y0)))
        if oy > cy and oy - clearance > cy:
            value = oy - clearance
            options.append(('y1', value, abs(y1 - value)))
        if not options:
            continue

        side, value, _ = min(options, key=lambda item: item[2])
        if side == 'x0':
            x0 = max(x0, value)
        elif side == 'x1':
            x1 = min(x1, value)
        elif side == 'y0':
            y0 = max(y0, value)
        elif side == 'y1':
            y1 = min(y1, value)

    return (x0, y0, x1, y1)


def _is_laj_relevant_entity(typ: str, entity: dict) -> bool:
    """Filter entities that are not local slab-recorte evidence."""
    layer = _layer_key(entity.get('layer'))
    if layer == '0' or 'REAPROVEITAMENTO' in layer:
        return False

    if typ == 'hatch':
        paths = entity.get('paths') or []
        pts = [pt for path in paths for pt in path]
        if not pts:
            return False
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        if max(w, h) > 650:
            return False

    return True


def _clip_line_to_bboxes(line: dict, bboxes: list) -> list[dict]:
    clipped = []
    s = line.get('start')
    e = line.get('end')
    if not s or not e:
        return clipped
    for bbox in bboxes:
        segment = _clip_segment_to_bbox(
            float(s[0]), float(s[1]), float(e[0]), float(e[1]), bbox
        )
        if not segment:
            continue
        (x0, y0), (x1, y1) = segment
        if abs(x1 - x0) < 1e-6 and abs(y1 - y0) < 1e-6:
            continue
        new_line = dict(line)
        new_line['start'] = (x0, y0)
        new_line['end'] = (x1, y1)
        clipped.append(new_line)
    return clipped


def _clip_poly_to_bboxes(poly: dict, bboxes: list) -> list[dict]:
    pts = poly.get('points') or []
    if len(pts) < 2:
        return []

    segments = []
    for a, b in zip(pts, pts[1:]):
        pseudo = dict(poly)
        pseudo['start'] = a
        pseudo['end'] = b
        for line in _clip_line_to_bboxes(pseudo, bboxes):
            new_poly = dict(poly)
            new_poly['points'] = [line['start'], line['end']]
            new_poly['closed'] = False
            segments.append(new_poly)

    if poly.get('closed') and len(pts) > 2:
        pseudo = dict(poly)
        pseudo['start'] = pts[-1]
        pseudo['end'] = pts[0]
        for line in _clip_line_to_bboxes(pseudo, bboxes):
            new_poly = dict(poly)
            new_poly['points'] = [line['start'], line['end']]
            new_poly['closed'] = False
            segments.append(new_poly)

    return segments


def _clip_segment_to_bbox(x0: float, y0: float, x1: float, y1: float, bbox: tuple):
    """Liang-Barsky segment clipping."""
    xmin, ymin, xmax, ymax = bbox
    dx = x1 - x0
    dy = y1 - y0
    p = [-dx, dx, -dy, dy]
    q = [x0 - xmin, xmax - x0, y0 - ymin, ymax - y0]
    u1, u2 = 0.0, 1.0

    for pi, qi in zip(p, q):
        if abs(pi) < 1e-12:
            if qi < 0:
                return None
            continue
        r = qi / pi
        if pi < 0:
            if r > u2:
                return None
            if r > u1:
                u1 = r
        else:
            if r < u1:
                return None
            if r < u2:
                u2 = r

    return ((x0 + u1 * dx, y0 + u1 * dy), (x0 + u2 * dx, y0 + u2 * dy))


def _merge_bboxes(bboxes: list) -> tuple:
    return (
        min(b[0] for b in bboxes),
        min(b[1] for b in bboxes),
        max(b[2] for b in bboxes),
        max(b[3] for b in bboxes),
    )


def _all_pts_from_ents(ents: list) -> list:
    pts = []
    for typ, e in ents:
        if typ == 'line':
            pts.append(e['start']); pts.append(e['end'])
        elif typ == 'poly':
            pts.extend(e['points'])
        elif typ == 'text':
            pos = e.get('pos')
            if pos: pts.append((float(pos[0]), float(pos[1])))
        elif typ == 'circle':
            c = e.get('center')
            r = e.get('radius', 0)
            if c:
                pts.append((float(c[0]) - r, float(c[1]) - r))
                pts.append((float(c[0]) + r, float(c[1]) + r))
        elif typ == 'hatch':
            for path in e.get('paths', []):
                pts.extend((float(p[0]), float(p[1])) for p in path)
    return pts


def _pts_to_bbox(pts: list, margin: float = 0) -> tuple:
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    return (min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin)


def _deduplicate(ents: list) -> list:
    seen = set()
    result = []
    for typ, e in ents:
        key = (typ, id(e))
        if key not in seen:
            seen.add(key); result.append((typ, e))
    return result


def _is_frame_border(pts: list) -> bool:
    """Detecta se uma polilinha é a borda do bloco 9999999999 (frame STOG).
    Critério: 4 pontos formando retângulo de ~1485×1050 (±120).
    """
    if len(pts) < 4: return False
    xs = [p[0] for p in pts]; ys = [p[1] for p in pts]
    w = max(xs) - min(xs); h = max(ys) - min(ys)
    return 1365 <= w <= 1605 and 930 <= h <= 1170


def _sort_key_elem(eid: str) -> tuple:
    """Ordenação: P1 < P2 < P10 < P11; VF301 < V301 < V302; V323-V328 usa primeiro número."""
    # Para IDs compostos como "V323-V328", pegar a primeira parte
    first_part = eid.split('-')[0]
    m = re.match(r'^([A-Z]+)(\d+)', first_part)
    if m:
        return (m.group(1), int(m.group(2)))
    return (eid, 0)


# ──────────────────────────────────────────────────────────────────────────────
# CLI standalone
# ──────────────────────────────────────────────────────────────────────────────

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Motor de extração de recortes ER")
    parser.add_argument("source_dxf", help="Caminho para o DXF fonte")
    parser.add_argument("--type", "-t", help="Tipo ER: PIL, LV, FV, LAJ (auto-detectado se omitido)")
    parser.add_argument("--output", "-o", help="Diretório de saída (padrão: Fase-2_Triagem/recortes_reversos/<stem>)")
    parser.add_argument("--db", help="Caminho para o banco de dados SQLite")
    parser.add_argument("--overwrite", action="store_true", help="Sobrescrever recortes existentes")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s"
    )

    src = Path(args.source_dxf)

    if args.output:
        out_dir = Path(args.output)
    else:
        # Padrão: ao lado da pasta Fase-1_Ingestao
        base = src.parent.parent  # .../Obra_TREINO_1
        out_dir = base / "Fase-2_Triagem" / "recortes_reversos" / src.stem

    motor = RecorteMotor(str(src), er_type=args.type)
    results = motor.run(out_dir, db_path=args.db, overwrite=args.overwrite)

    print(f"\nRecortes extraídos: {len(results)}")
    for r in results:
        cnt = r['entity_count']
        path = Path(r['recorte_path']).name
        print(f"  {r['elemento_id']:12s}  {cnt:4d} ent  {path}")


if __name__ == "__main__":
    main()
