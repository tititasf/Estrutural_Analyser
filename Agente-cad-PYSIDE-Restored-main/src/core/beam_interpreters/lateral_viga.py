"""Contratos isolados dos quatro fluxos de lateral de viga."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from .contracts import InterpreterContract, InterpreterKind

Point = tuple[float, float]
Polyline = list[Point]


class _LateralVigaInterpreter:
    contract: InterpreterContract

    @property
    def side(self) -> str:
        return str(self.contract.side)

    @property
    def behavior(self) -> str:
        return str(self.contract.behavior)

    @property
    def target_suffix(self) -> str:
        return (
            "comprimento_total"
            if self.behavior == "para"
            else "comp_total_passa"
        )

    def output_key(self, segment_index: int) -> str:
        return (
            f"viga_{self.side.lower()}_seg_{int(segment_index)}_"
            f"{self.target_suffix}"
        )

    @property
    def prefix(self) -> str:
        return f"viga_{self.side.lower()}"

    @property
    def raw_slot(self) -> str:
        return f"seg_side_{self.side.lower()}"

    @property
    def contract_key(self) -> str:
        """Identidade estavel do contrato sem misturar lado ou comportamento."""
        return f"{self.side.lower()}_{self.behavior}"

    def _contract_value(
        self,
        classified: dict[str, Any],
        suffix: str,
        fallback: Any,
    ) -> Any:
        """Le geometria semantica do contrato e so entao usa o legado.

        O BeamTracer continua dono da geometria bruta. A camada semantica pode
        publicar ``lv_a_para_*``, ``lv_b_para_*``, ``lv_a_passa_*`` e
        ``lv_b_passa_*``. Isso impede que os quatro interpretadores sejam
        obrigados a reutilizar a mesma topologia quando Para e Passa divergem.
        """
        key = f"lv_{self.contract_key}_{suffix}"
        return classified[key] if key in classified else fallback

    @staticmethod
    def _length(line: Iterable[Point]) -> float:
        points = list(line)
        if len(points) < 2:
            return 0.0
        return math.hypot(
            points[-1][0] - points[0][0],
            points[-1][1] - points[0][1],
        )

    @staticmethod
    def _line_range(line: Polyline, is_horizontal: bool) -> tuple[float, float]:
        axis = 0 if is_horizontal else 1
        values = [float(point[axis]) for point in line]
        return min(values), max(values)

    def _best_overlap(
        self,
        raw_lines: Iterable[Polyline],
        span_min: float,
        span_max: float,
        is_horizontal: bool,
    ) -> Polyline | None:
        best: Polyline | None = None
        best_ratio = 0.0
        for line in raw_lines:
            if len(line) < 2:
                continue
            line_min, line_max = self._line_range(line, is_horizontal)
            line_length = line_max - line_min
            if line_length <= 0:
                continue
            overlap = min(line_max, span_max) - max(line_min, span_min)
            ratio = overlap / line_length
            if ratio > 0.3 and ratio > best_ratio:
                best_ratio, best = ratio, line
        return best

    def _edge_from_fundo(
        self,
        beam: dict[str, Any],
        segment_index: int,
        span_min: float,
        span_max: float,
        is_horizontal: bool,
    ) -> Polyline | None:
        area_key = f"viga_fundo_seg_{segment_index}_area_segs"
        contours = (
            beam.get("links", {}).get(area_key, {}).get("contour", [])
        )
        if not contours or not isinstance(contours[0], dict):
            return None
        points = contours[0].get("points") or []
        if len(points) < 3:
            return None
        if is_horizontal:
            transverse = (
                max(float(point[1]) for point in points)
                if self.side == "A"
                else min(float(point[1]) for point in points)
            )
            return [(span_min, transverse), (span_max, transverse)]
        transverse = (
            min(float(point[0]) for point in points)
            if self.side == "A"
            else max(float(point[0]) for point in points)
        )
        return [(transverse, span_min), (transverse, span_max)]

    def interpret(
        self,
        beam: dict[str, Any],
        classified: dict[str, Any],
    ) -> float:
        """Produz somente o slot lateral declarado pelo contrato."""
        legacy_lengths = classified.get(
            "lv_merged_bottom_lengths",
            classified.get("merged_bottom_lengths", []),
        )
        legacy_coordinates = classified.get(
            "lv_merged_bottom_groups_coords",
            classified.get("merged_bottom_groups_coords", []),
        )
        legacy_raw_lines = classified.get(
            f"lv_{self.raw_slot}",
            classified.get(self.raw_slot, []),
        )
        lengths = self._contract_value(
            classified, "lengths", legacy_lengths
        )
        coordinates = self._contract_value(
            classified, "groups_coords", legacy_coordinates
        )
        raw_lines = self._contract_value(
            classified, "lines", legacy_raw_lines
        )
        is_horizontal = bool(beam.get("lv_is_h", beam.get("is_h", True)))
        beam_pos = beam.get("pos", (0.0, 0.0))
        bottom_runs = classified.get("bottom_runs", [])
        has_lv_contract = "lv_merged_bottom_lengths" in classified
        mixed_orientations = (
            not has_lv_contract
            and len({
                bool(run.get("is_h", is_horizontal))
                for run in bottom_runs
            }) > 1
        )
        segment_orientations = [is_horizontal] * len(lengths)
        segment_positions = [beam_pos] * len(lengths)
        if mixed_orientations:
            lengths = []
            coordinates = []
            segment_orientations = []
            segment_positions = []
            for run in bottom_runs:
                run_lengths = run.get("lengths", [])
                run_coordinates = run.get("coords", [])
                usable = min(len(run_lengths), len(run_coordinates))
                lengths.extend(run_lengths[:usable])
                coordinates.extend(run_coordinates[:usable])
                segment_orientations.extend(
                    [bool(run.get("is_h", is_horizontal))] * usable
                )
                segment_positions.extend(
                    [run.get("pos", beam_pos)] * usable
                )
        links = beam.setdefault("links", {})
        total = 0.0

        if lengths and coordinates:
            for segment_index, length in enumerate(lengths, start=1):
                if segment_index > len(coordinates):
                    break
                span_min, span_max = coordinates[segment_index - 1]
                segment_is_horizontal = segment_orientations[segment_index - 1]
                segment_pos = segment_positions[segment_index - 1]
                beam[f"{self.prefix}_seg_{segment_index}_exists"] = True
                target_key = self.output_key(segment_index)
                target = links.setdefault(target_key, {})
                matched = self._best_overlap(
                    raw_lines, span_min, span_max, segment_is_horizontal
                )
                if matched is None:
                    matched = self._edge_from_fundo(
                        beam,
                        segment_index,
                        span_min,
                        span_max,
                        segment_is_horizontal,
                    )
                if matched is None:
                    matched = (
                        [(span_min, segment_pos[1]), (span_max, segment_pos[1])]
                        if segment_is_horizontal
                        else [(segment_pos[0], span_min), (segment_pos[0], span_max)]
                    )
                    segment_length = float(length)
                else:
                    segment_length = self._length(matched)
                link_entry = {
                    "type": "poly",
                    "points": matched,
                    "len": segment_length,
                    "tag": f"Lado {self.side}",
                    "geometry_role": "lateral",
                    "side": self.side,
                    "behavior": self.behavior.capitalize(),
                    "contract_id": f"LV_{self.side.upper()}_{self.behavior.upper()}",
                    "segment_index": segment_index,
                    "source_slot": self.raw_slot,
                }
                if beam.get("lv_dimension_override"):
                    link_entry["lv_dimensao"] = beam["lv_dimension_override"]
                target[self.raw_slot] = [link_entry]
                total += segment_length
            return total

        candidates = [line for line in raw_lines if len(line) >= 2]
        if not candidates:
            return 0.0
        best_line = max(candidates, key=self._length)
        segment_length = self._length(best_line)
        beam[f"{self.prefix}_seg_1_exists"] = True
        link_entry = {
            "type": "poly",
            "points": best_line,
            "len": segment_length,
            "tag": f"Lado {self.side}",
            "geometry_role": "lateral",
            "side": self.side,
            "behavior": self.behavior.capitalize(),
            "contract_id": f"LV_{self.side.upper()}_{self.behavior.upper()}",
            "segment_index": 1,
            "source_slot": self.raw_slot,
        }
        if beam.get("lv_dimension_override"):
            link_entry["lv_dimensao"] = beam["lv_dimension_override"]
        links.setdefault(self.output_key(1), {})[self.raw_slot] = [link_entry]
        return segment_length


class LateralVigaAParaInterpreter(_LateralVigaInterpreter):
    contract = InterpreterContract(
        InterpreterKind.LATERAL_VIGA_A_PARA,
        owner="LV",
        side="A",
        behavior="para",
        output_slot="seg_side_a",
    )


class LateralVigaBParaInterpreter(_LateralVigaInterpreter):
    contract = InterpreterContract(
        InterpreterKind.LATERAL_VIGA_B_PARA,
        owner="LV",
        side="B",
        behavior="para",
        output_slot="seg_side_b",
    )


class LateralVigaAPassaInterpreter(_LateralVigaInterpreter):
    contract = InterpreterContract(
        InterpreterKind.LATERAL_VIGA_A_PASSA,
        owner="LV",
        side="A",
        behavior="passa",
        output_slot="seg_side_a",
    )


class LateralVigaBPassaInterpreter(_LateralVigaInterpreter):
    contract = InterpreterContract(
        InterpreterKind.LATERAL_VIGA_B_PASSA,
        owner="LV",
        side="B",
        behavior="passa",
        output_slot="seg_side_b",
    )
