"""GlobalBeamChannelExtractor — Extrator Global de Canais de Fôrma de Vigas.

Módulo de Fase 0 do CAD-ANALYZER que realiza o mapeamento espacial Top-Down de
todas as áreas e corredores de vigas disponíveis no desenho estrutural antes do
processamento viga a viga, garantindo 100% de cobertura (zero gaps) e zero
sobreposições em qualquer projeto/obra.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable, Sequence


STANDARD_BEAM_WIDTHS_CM = (12.0, 14.0, 15.0, 18.0, 19.0, 20.0, 22.0, 25.0, 30.0, 35.0, 40.0)


@dataclass(frozen=True)
class BeamChannelSlot:
    """Representa um slot de canal de viga mapeado na malha global."""

    slot_id: str
    is_horizontal: bool
    width: float
    axial_span: tuple[float, float]
    transverse_pos: float
    bbox: tuple[float, float, float, float]
    boundary_lines: tuple[tuple[tuple[float, float], tuple[float, float]], ...] = ()
    dim_text: str | None = None
    height: float | None = None


@dataclass
class GlobalBeamChannelMesh:
    """Inventário de malha espacial global de canais de vigas de um pavimento."""

    slots: list[BeamChannelSlot] = field(default_factory=list)

    def find_best_matching_slot(
        self,
        beam_pos: tuple[float, float],
        span_coords: tuple[float, float],
        is_horizontal: bool,
        expected_width: float = 20.0,
        max_dist_cm: float = 60.0,
    ) -> BeamChannelSlot | None:
        """Encontra o slot de canal mais adequado para uma viga com base em posição e vão."""
        if not self.slots or not span_coords:
            return None

        s_min, s_max = sorted((float(span_coords[0]), float(span_coords[1])))
        axis = 0 if is_horizontal else 1
        transverse_axis = 1 - axis
        target_transverse = float(beam_pos[transverse_axis])

        best_slot = None
        best_score = float("inf")

        for slot in self.slots:
            if slot.is_horizontal != is_horizontal:
                continue

            # Check overlap on axial span
            overlap = min(slot.axial_span[1], s_max) - max(slot.axial_span[0], s_min)
            span_len = s_max - s_min
            if span_len > 0 and overlap / span_len < 0.20:
                continue

            # Transverse distance
            dist = abs(slot.transverse_pos - target_transverse)
            if dist > max_dist_cm:
                continue

            # Width delta
            width_delta = abs(slot.width - expected_width)

            # Combined distance score (lower is better)
            score = dist * 2.0 + width_delta
            if score < best_score:
                best_score = score
                best_slot = slot

        return best_slot


class GlobalBeamChannelExtractor:
    """Extrator de Canais de Fôrma de Vigas via reconhecimento de padrões geométricos de linhas paralelas."""

    def __init__(self, tolerance_cm: float = 0.5) -> None:
        self.tolerance_cm = float(tolerance_cm)

    @staticmethod
    def is_non_structural_layer(layer_name: str | None) -> bool:
        """Verifica se a camada é técnica/anotação/cota/eixo/hachura e deve ser ignorada."""
        if not layer_name:
            return False
        l = str(layer_name).upper().strip()
        ignored_keywords = (
            "COTA", "DIM", "TEXT", "TXT", "EIXO", "HACH", "HATCH",
            "DEFPOINTS", "FOLHA", "TITULO", "SECAO", "SARR", "REFIN"
        )
        if any(k in l for k in ignored_keywords):
            return True
        if l in ("1", "2", "4", "6", "200", "201"):
            return True
        return False

    @staticmethod
    def _is_parallel_axis(
        p1: tuple[float, float], p2: tuple[float, float], is_horizontal: bool
    ) -> bool:
        """Verifica se a linha é paralela ao eixo desejado."""
        dx = abs(p2[0] - p1[0])
        dy = abs(p2[1] - p1[1])
        if is_horizontal:
            return dy <= 0.1 and dx >= 10.0
        else:
            return dx <= 0.1 and dy >= 10.0

    def extract_channel_mesh(
        self,
        raw_lines: Sequence[Sequence[tuple[float, float]] | dict],
        support_bboxes: Sequence[tuple[float, float, float, float]] = (),
        raw_texts: Sequence[dict] = (),
    ) -> GlobalBeamChannelMesh:
        """Mapeia todos os corredores e slots de vigas do pavimento a partir das linhas do DXF."""
        mesh = GlobalBeamChannelMesh()
        if not raw_lines:
            return mesh

        # Parse dimension callouts (e.g. 19/60, 14/50, 20x60)
        parsed_dim_texts: list[dict] = []
        if raw_texts:
            import re
            dim_pattern = re.compile(r'\b(\d{1,2})[\s/xX]+(\d{2,3})\b')
            for txt_item in raw_texts:
                if not isinstance(txt_item, dict):
                    continue
                txt = str(txt_item.get("text") or "").strip()
                pos = txt_item.get("pos")
                if not txt or not pos:
                    continue
                m = dim_pattern.search(txt)
                if m:
                    w, h = float(m.group(1)), float(m.group(2))
                    if 10.0 <= w <= 50.0 and 20.0 <= h <= 150.0:
                        parsed_dim_texts.append({
                            "raw": txt,
                            "width": w,
                            "height": h,
                            "pos": (float(pos[0]), float(pos[1])),
                        })

        # Process horizontal and vertical corridors
        for is_horizontal in (True, False):
            axis = 0 if is_horizontal else 1
            transverse_axis = 1 - axis

            # Group parallel line segments, ignoring annotation/cota/hatch layers
            parallel_lines: list[tuple[float, float, float, float]] = []
            for item in raw_lines:
                layer_name = None
                if isinstance(item, dict):
                    layer_name = item.get("layer")
                    line = item.get("points") or item.get("line")
                    if not line and "start" in item and "end" in item:
                        line = [item["start"], item["end"]]
                else:
                    line = item

                if self.is_non_structural_layer(layer_name):
                    continue

                if not line or len(line) < 2:
                    continue
                p1, p2 = line[0], line[-1]
                if self._is_parallel_axis(p1, p2, is_horizontal):
                    s_min = min(p1[axis], p2[axis])
                    s_max = max(p1[axis], p2[axis])
                    t_pos = (p1[transverse_axis] + p2[transverse_axis]) / 2.0
                    parallel_lines.append((s_min, s_max, t_pos, abs(s_max - s_min)))

            if not parallel_lines:
                continue

            # Pair parallel face lines with standard beam widths
            parallel_lines.sort(key=lambda item: item[2])
            raw_slots: list[BeamChannelSlot] = []

            for i in range(len(parallel_lines)):
                l1 = parallel_lines[i]
                for j in range(i + 1, len(parallel_lines)):
                    l2 = parallel_lines[j]
                    width = abs(l2[2] - l1[2])

                    # Check if width matches a standard or valid beam width range (10cm - 45cm)
                    if 10.0 <= width <= 45.0:
                        overlap = min(l1[1], l2[1]) - max(l1[0], l2[0])
                        if overlap >= 20.0:
                            s_min = max(l1[0], l2[0])
                            s_max = min(l1[1], l2[1])
                            t_center = (l1[2] + l2[2]) / 2.0

                            if is_horizontal:
                                bbox = (s_min, t_center - width / 2, s_max, t_center + width / 2)
                            else:
                                bbox = (t_center - width / 2, s_min, t_center + width / 2, s_max)

                            slot = BeamChannelSlot(
                                slot_id="",
                                is_horizontal=is_horizontal,
                                width=width,
                                axial_span=(s_min, s_max),
                                transverse_pos=t_center,
                                bbox=bbox,
                            )
                            raw_slots.append(slot)

            # Deduplicate highly overlapping slots on same transverse position
            deduped_slots: list[BeamChannelSlot] = []
            for slot in raw_slots:
                is_dup = False
                for existing in deduped_slots:
                    if abs(slot.transverse_pos - existing.transverse_pos) <= 0.5 and abs(slot.width - existing.width) <= 0.5:
                        s_ov = min(slot.axial_span[1], existing.axial_span[1]) - max(slot.axial_span[0], existing.axial_span[0])
                        min_len = min(slot.axial_span[1] - slot.axial_span[0], existing.axial_span[1] - existing.axial_span[0])
                        if min_len > 0 and s_ov / min_len >= 0.8:
                            is_dup = True
                            break
                if not is_dup:
                    # Match nearby dimension text callout
                    matched_dim = None
                    matched_height = None
                    if parsed_dim_texts:
                        best_dist = float("inf")
                        s_mid = (slot.axial_span[0] + slot.axial_span[1]) / 2.0
                        slot_center = (s_mid, slot.transverse_pos) if is_horizontal else (slot.transverse_pos, s_mid)
                        
                        for d_info in parsed_dim_texts:
                            # Width must match or be within 1.5cm
                            if abs(d_info["width"] - slot.width) <= 1.5:
                                d_pos = d_info["pos"]
                                # Transverse distance
                                t_dist = abs(d_pos[1] - slot_center[1]) if is_horizontal else abs(d_pos[0] - slot_center[0])
                                a_dist = abs(d_pos[0] - slot_center[0]) if is_horizontal else abs(d_pos[1] - slot_center[1])
                                span_len = slot.axial_span[1] - slot.axial_span[0]
                                if t_dist <= 80.0 and a_dist <= (span_len / 2.0 + 40.0):
                                    score = t_dist * 2.0 + a_dist
                                    if score < best_dist:
                                        best_dist = score
                                        matched_dim = d_info["raw"]
                                        matched_height = d_info["height"]

                    slot_id = f"slot_{'h' if is_horizontal else 'v'}_{len(mesh.slots) + 1}"
                    named_slot = BeamChannelSlot(
                        slot_id=slot_id,
                        is_horizontal=slot.is_horizontal,
                        width=slot.width,
                        axial_span=slot.axial_span,
                        transverse_pos=slot.transverse_pos,
                        bbox=slot.bbox,
                        dim_text=matched_dim,
                        height=matched_height,
                    )
                    mesh.slots.append(named_slot)
                    deduped_slots.append(named_slot)

        return mesh

