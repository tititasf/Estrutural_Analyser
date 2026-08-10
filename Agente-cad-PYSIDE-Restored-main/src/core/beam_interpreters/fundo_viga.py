"""Interpretacao exclusiva dos segmentos de fundo de viga (FV)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
import hashlib
import json
import math
import re
from typing import Any

from .contracts import InterpreterContract, InterpreterKind

AxisFn = Callable[[Any], float]
Interval = tuple[float, float]


class FundoVigaInterpreter:
    """Consolida paineis FV sem atravessar fronteiras fisicas.

    Intervalos adjacentes continuam distintos. Apenas representacoes quase
    identicas da mesma geometria sao desduplicadas. Um contorno envolvente de
    fallback e descartado quando existem dois ou mais paineis internos reais.
    """

    contract = InterpreterContract(
        kind=InterpreterKind.FUNDO_VIGA,
        owner="FV",
        output_slot="seg_bottom",
    )

    def __init__(self, equivalence_tolerance: float = 5.0) -> None:
        self.equivalence_tolerance = float(equivalence_tolerance)

    @staticmethod
    def _polygon_area(points: Iterable[tuple[float, float]]) -> float:
        clean = [(float(point[0]), float(point[1])) for point in points]
        if len(clean) < 3:
            return 0.0
        return abs(sum(
            x1 * y2 - x2 * y1
            for (x1, y1), (x2, y2) in zip(clean, clean[1:] + clean[:1])
        )) / 2.0

    @staticmethod
    def _distance(
        first: tuple[float, float],
        second: tuple[float, float],
    ) -> float:
        return math.hypot(first[0] - second[0], first[1] - second[1])

    @staticmethod
    def _bbox_dimensions(points: Iterable[tuple[float, float]]) -> tuple[float, float]:
        clean = [(float(point[0]), float(point[1])) for point in points or []]
        if not clean:
            return 0.0, 0.0
        xs = [point[0] for point in clean]
        ys = [point[1] for point in clean]
        dx = max(xs) - min(xs)
        dy = max(ys) - min(ys)
        return max(dx, dy), min(dx, dy)

    @classmethod
    def _longest_axis_edge(cls, points: Iterable[tuple[float, float]]) -> float:
        """Comprimento canônico útil para fundo especial em L/chanfro.

        O contorno visual pode ser diagonal e, em coordenadas globais, ter um
        bbox transversal grande. Para a ficha, o comprimento de referência do
        trecho especial é a maior borda reta útil, não o perímetro.
        """
        clean = [(float(point[0]), float(point[1])) for point in points or []]
        if len(clean) < 2:
            return 0.0
        return max(
            cls._distance(first, second)
            for first, second in zip(clean, clean[1:])
        )

    @staticmethod
    def _format_measure(value: float) -> str:
        value = float(value)
        if abs(value - round(value)) <= 0.05:
            return str(int(round(value)))
        return f"{value:.2f}".rstrip("0").rstrip(".")

    @classmethod
    def _line_length(cls, line: list[tuple[float, float]]) -> float:
        return sum(
            cls._distance(first, second)
            for first, second in zip(line, line[1:])
        )

    @staticmethod
    def _line_vector(
        line: list[tuple[float, float]],
    ) -> tuple[float, float] | None:
        if len(line) < 2:
            return None
        dx = line[-1][0] - line[0][0]
        dy = line[-1][1] - line[0][1]
        length = math.hypot(dx, dy)
        if length <= 0.01:
            return None
        return dx / length, dy / length

    @classmethod
    def _line_distance(
        cls,
        point: tuple[float, float],
        line: list[tuple[float, float]],
    ) -> float:
        vector = cls._line_vector(line)
        if vector is None:
            return float("inf")
        vx, vy = vector
        px = point[0] - line[0][0]
        py = point[1] - line[0][1]
        return abs(px * vy - py * vx)

    @classmethod
    def _diagonal_pair_contour(
        cls,
        *,
        side_lines: Iterable[Iterable[Any]],
        cap_lines: Iterable[Iterable[Any]],
        extension_lines: Iterable[Iterable[Any]] = (),
        width: float,
    ) -> list[tuple[float, float]]:
        """Fecha FV chanfrado a partir de duas bordas diagonais paralelas.

        Caso V307: o tracer encontra as duas bordas diagonais reais, mas o
        fallback retangular antigo usa só o cap curto. A regra aqui é geral:
        para um par diagonal paralelo, usa o par como corpo longitudinal e
        acrescenta caps próximos quando existirem.
        """
        clean_sides: list[list[tuple[float, float]]] = []
        for line in side_lines:
            clean = []
            for point in line or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) >= 2:
                length = cls._line_length(clean)
                dx = abs(clean[-1][0] - clean[0][0])
                dy = abs(clean[-1][1] - clean[0][1])
                if length >= max(40.0, width * 3.0) and dx > 5.0 and dy > 5.0:
                    clean_sides.append(clean)

        best: tuple[float, list[tuple[float, float]], list[tuple[float, float]]] | None = None
        for index, first in enumerate(clean_sides):
            first_vector = cls._line_vector(first)
            if first_vector is None:
                continue
            for second in clean_sides[index + 1:]:
                second_vector = cls._line_vector(second)
                if second_vector is None:
                    continue
                parallel = abs(
                    first_vector[0] * second_vector[0]
                    + first_vector[1] * second_vector[1]
                )
                if parallel < 0.97:
                    continue
                separation = (
                    cls._line_distance(second[0], first)
                    + cls._line_distance(second[-1], first)
                ) / 2.0
                if not (width * 0.35 <= separation <= width * 2.25):
                    continue
                score = abs(separation - width) - min(
                    cls._line_length(first),
                    cls._line_length(second),
                ) / 1000.0
                if best is None or score < best[0]:
                    best = (score, list(first), list(second))

        if best is None:
            return []

        _, first, second = best
        same = cls._distance(first[0], second[0]) + cls._distance(first[-1], second[-1])
        crossed = cls._distance(first[0], second[-1]) + cls._distance(first[-1], second[0])
        if crossed < same:
            second.reverse()

        endpoint_pairs = [
            (first[0], second[0], 0),
            (first[-1], second[-1], -1),
        ]

        clean_caps: list[list[tuple[float, float]]] = []
        for line in cap_lines:
            clean = []
            for point in line or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) >= 2 and cls._line_length(clean) <= max(width * 3.0, 80.0):
                clean_caps.append(clean)

        def cap_extension(
            endpoint: tuple[float, float],
        ) -> tuple[float, float] | None:
            matches: list[tuple[float, tuple[float, float]]] = []
            for cap in clean_caps:
                for cap_index, cap_point in enumerate((cap[0], cap[-1])):
                    distance = cls._distance(endpoint, cap_point)
                    if distance <= max(2.0, width * 0.20):
                        other = cap[-1] if cap_index == 0 else cap[0]
                        matches.append((distance, other))
            if not matches:
                return None
            return min(matches, key=lambda item: item[0])[1]

        first_start_cap = cap_extension(first[0])
        second_start_cap = cap_extension(second[0])
        first_end_cap = cap_extension(first[-1])
        second_end_cap = cap_extension(second[-1])

        start_has_caps = int(first_start_cap is not None) + int(second_start_cap is not None)
        end_has_caps = int(first_end_cap is not None) + int(second_end_cap is not None)
        if end_has_caps > start_has_caps:
            first.reverse()
            second.reverse()
            first_start_cap = cap_extension(first[0])
            second_start_cap = cap_extension(second[0])

        clean_extensions: list[list[tuple[float, float]]] = []
        for line in extension_lines:
            clean = []
            for point in line or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) >= 2 and cls._line_length(clean) >= max(width * 3.0, 40.0):
                clean_extensions.append(clean)

        def connected_extension_pair() -> tuple[tuple[float, float], tuple[float, float]] | None:
            end_first = first[-1]
            end_second = second[-1]
            diagonal_vector = cls._line_vector(first)
            if diagonal_vector is None:
                return None
            endpoint_tol = max(2.0, width * 0.20)
            candidates: list[
                tuple[float, tuple[float, float], tuple[float, float]]
            ] = []

            def near_and_far(
                line: list[tuple[float, float]],
                endpoint: tuple[float, float],
            ) -> tuple[tuple[float, float], tuple[float, float]] | None:
                first_distance = cls._distance(line[0], endpoint)
                last_distance = cls._distance(line[-1], endpoint)
                if first_distance <= endpoint_tol:
                    return line[0], line[-1]
                if last_distance <= endpoint_tol:
                    return line[-1], line[0]
                return None

            for line_first in clean_extensions:
                match_first = near_and_far(line_first, end_first)
                if match_first is None:
                    continue
                vector_first = cls._line_vector(line_first)
                if vector_first is None:
                    continue
                for line_second in clean_extensions:
                    if line_second is line_first:
                        continue
                    match_second = near_and_far(line_second, end_second)
                    if match_second is None:
                        continue
                    vector_second = cls._line_vector(line_second)
                    if vector_second is None:
                        continue
                    parallel = abs(
                        vector_first[0] * vector_second[0]
                        + vector_first[1] * vector_second[1]
                    )
                    if parallel < 0.97:
                        continue
                    # Continuação deve sair do chanfro, não repetir a diagonal.
                    against_diagonal = abs(
                        vector_first[0] * diagonal_vector[0]
                        + vector_first[1] * diagonal_vector[1]
                    )
                    if against_diagonal > 0.90:
                        continue
                    _, far_first = match_first
                    _, far_second = match_second
                    separation = cls._distance(far_first, far_second)
                    if not (width * 0.35 <= separation <= width * 2.25):
                        continue
                    out_first = (
                        far_first[0] - end_first[0],
                        far_first[1] - end_first[1],
                    )
                    out_second = (
                        far_second[0] - end_second[0],
                        far_second[1] - end_second[1],
                    )
                    len_first = math.hypot(*out_first)
                    len_second = math.hypot(*out_second)
                    if len_first <= 0.01 or len_second <= 0.01:
                        continue
                    same_direction = (
                        out_first[0] * out_second[0]
                        + out_first[1] * out_second[1]
                    ) / (len_first * len_second)
                    if same_direction < 0.80:
                        continue
                    score = (
                        abs(separation - width)
                        - min(len_first, len_second) / 1000.0
                    )
                    candidates.append((score, far_first, far_second))
            if not candidates:
                return None
            _, far_first, far_second = min(candidates, key=lambda item: item[0])
            return far_first, far_second

        extension_pair = connected_extension_pair()

        start_first = first_start_cap or first[0]
        start_second = second_start_cap or second[0]
        contour = [start_first, start_second, second[0], second[-1]]
        if extension_pair is not None:
            far_first, far_second = extension_pair
            contour.extend([far_second, far_first])
        contour.extend([first[-1], first[0], start_first])
        deduped: list[tuple[float, float]] = []
        for point in contour:
            if not deduped or cls._distance(deduped[-1], point) > 0.01:
                deduped.append(point)
        if deduped[0] != deduped[-1]:
            deduped.append(deduped[0])
        if cls._polygon_area(deduped) <= 0.05:
            return []
        return deduped

    @classmethod
    def _clean_polyline_points(
        cls,
        line: Iterable[Any] | None,
    ) -> list[tuple[float, float]]:
        clean: list[tuple[float, float]] = []
        for point in line or []:
            try:
                clean.append((float(point[0]), float(point[1])))
            except (TypeError, ValueError, IndexError):
                continue
        return clean if len(clean) >= 2 else []

    @classmethod
    def _line_transverse(
        cls,
        line: list[tuple[float, float]],
        *,
        is_horizontal: bool,
    ) -> float:
        axis = 1 if is_horizontal else 0
        return sum(point[axis] for point in line) / len(line)

    @classmethod
    def matching_lines_for_span(
        cls,
        lines: Iterable[Iterable[Any]] | None,
        *,
        is_horizontal: bool,
        axial_span: Interval,
        min_overlap: float = 0.0,
    ) -> list[list[tuple[float, float]]]:
        """Linhas DXF com overlap axial no vão — evidência física do contorno."""
        span_min, span_max = sorted((float(axial_span[0]), float(axial_span[1])))
        axis = 0 if is_horizontal else 1
        matching: list[list[tuple[float, float]]] = []
        for line in lines or []:
            clean = cls._clean_polyline_points(line)
            if not clean:
                continue
            line_min = min(point[axis] for point in clean)
            line_max = max(point[axis] for point in clean)
            overlap = min(line_max, span_max) - max(line_min, span_min)
            if overlap > min_overlap:
                matching.append(clean)
        return matching

    @classmethod
    def _cluster_face_positions(
        cls,
        values: Iterable[float],
        *,
        tolerance: float = 0.5,
    ) -> list[float]:
        ordered = sorted(float(value) for value in values)
        if not ordered:
            return []
        clusters: list[list[float]] = [[ordered[0]]]
        for value in ordered[1:]:
            if abs(value - clusters[-1][-1]) <= tolerance:
                clusters[-1].append(value)
            else:
                clusters.append([value])
        return [sum(cluster) / len(cluster) for cluster in clusters]

    @classmethod
    def _rectangle_on_transverse_strip(
        cls,
        *,
        axial_span: Interval,
        is_horizontal: bool,
        low: float,
        high: float,
    ) -> list[tuple[float, float]]:
        start, end = sorted((float(axial_span[0]), float(axial_span[1])))
        low_f, high_f = sorted((float(low), float(high)))
        if end - start <= 0.01 or high_f - low_f <= 0.01:
            return []
        if is_horizontal:
            rectangle = [
                (start, low_f), (end, low_f),
                (end, high_f), (start, high_f),
            ]
        else:
            rectangle = [
                (low_f, start), (high_f, start),
                (high_f, end), (low_f, end),
            ]
        return rectangle + [rectangle[0]]

    @classmethod
    def _strip_edges_from_boundary(
        cls,
        *,
        clean_lines: list[list[tuple[float, float]]],
        width: float,
        is_horizontal: bool,
        transverse_center: float,
    ) -> tuple[float, float] | None:
        """Ancora a faixa transversal em faces DXF reais (nunca flutuando no vazio).

        Preferência:
        1. par de faces com separação ~ largura estrutural
        2. uma face real: a borda do retângulo fica *sobre* a linha; a outra
           borda fica a ``width`` no lado indicado pelo centro/rótulo
        """
        if not clean_lines or width <= 0.01:
            return None

        face_positions = cls._cluster_face_positions(
            cls._line_transverse(line, is_horizontal=is_horizontal)
            for line in clean_lines
        )
        if not face_positions:
            return None

        if len(face_positions) >= 2:
            best: tuple[float, float, float] | None = None
            for index, first in enumerate(face_positions):
                for second in face_positions[index + 1 :]:
                    separation = abs(second - first)
                    if not (width * 0.25 <= separation <= width * 2.0):
                        continue
                    error = abs(separation - width)
                    if best is None or error < best[0]:
                        best = (error, first, second)
            if best is not None:
                return (min(best[1], best[2]), max(best[1], best[2]))

        # Face única (ou faces colineares): uma borda sobre a linha DXF.
        face = min(
            face_positions,
            key=lambda value: abs(value - float(transverse_center)),
        )
        center = float(transverse_center)
        if center <= face + 1e-9:
            return (face - width, face)
        return (face, face + width)

    @classmethod
    def contour_overlays_boundary_lines(
        cls,
        points: Iterable[tuple[float, float]],
        boundary_lines: Iterable[Iterable[Any]] = (),
        *,
        is_horizontal: bool,
        tolerance: float = 0.75,
    ) -> bool:
        """True se ao menos uma borda longitudinal do contorno cai sobre face DXF.

        É o teste que separa retângulo com tamanho certo mas *flutuando* (caso
        típico do SA) de área ancorada nas linhas verdes do desenho.
        """
        clean_points = [
            (float(point[0]), float(point[1]))
            for point in points or []
        ]
        if len(clean_points) < 3:
            return False
        transverse_axis = 1 if is_horizontal else 0
        edge_low = min(point[transverse_axis] for point in clean_points)
        edge_high = max(point[transverse_axis] for point in clean_points)
        face_values: list[float] = []
        for line in boundary_lines or []:
            clean = cls._clean_polyline_points(line)
            if clean:
                face_values.append(
                    cls._line_transverse(clean, is_horizontal=is_horizontal)
                )
        faces = cls._cluster_face_positions(face_values, tolerance=tolerance)
        if not faces:
            return False
        return any(
            abs(edge - face) <= tolerance
            for edge in (edge_low, edge_high)
            for face in faces
        )

    @classmethod
    def build_area_contour(
        cls,
        *,
        axial_span: Interval,
        width: float,
        is_horizontal: bool,
        transverse_center: float,
        boundary_lines: Iterable[Iterable[Any]] = (),
        allow_synthetic: bool = True,
    ) -> list[tuple[float, float]]:
        """Produz área FV fechada ancorada em linhas DXF quando existirem.

        Linhas colineares não formam polígono sozinhas: a segunda borda é
        reconstruída pela largura estrutural, mas a primeira borda permanece
        *sobreposta* à face observada. Sem evidência de linha e com
        ``allow_synthetic=False``, recusa inventar retângulo flutuante.
        """
        start, end = sorted((float(axial_span[0]), float(axial_span[1])))
        width = abs(float(width))
        center = float(transverse_center)
        if end - start <= 0.01 or width <= 0.01:
            return []

        clean_lines: list[list[tuple[float, float]]] = []
        for line in boundary_lines:
            clean = cls._clean_polyline_points(line)
            if clean:
                clean_lines.append(clean)

        def transverse(line: list[tuple[float, float]]) -> float:
            return cls._line_transverse(line, is_horizontal=is_horizontal)

        if len(clean_lines) >= 2:
            ordered = sorted(clean_lines, key=transverse)
            first, second = list(ordered[0]), list(ordered[-1])
            axis = 0 if is_horizontal else 1
            if first[0][axis] > first[-1][axis]:
                first.reverse()
            if second[0][axis] > second[-1][axis]:
                second.reverse()
            candidate = first + list(reversed(second))
            transverse_span = abs(transverse(second) - transverse(first))
            width_plausible = width * 0.25 <= transverse_span <= width * 2.0
            # O vão axial do painel é o contrato (coords canônicos). Faces DXF
            # longas não podem alargar o polígono além de axial_span — senão um
            # split de cruzamento mais fundo vira de novo um over-merge visual
            # (regressão V302 S5/S6/S7, 2026-08).
            if width_plausible and cls._polygon_area(candidate) > 0.05:
                cand_axis = [point[axis] for point in candidate]
                cand_min, cand_max = min(cand_axis), max(cand_axis)
                # se a face cobre bem o vão pedido, recorta ao span canônico
                covers = cand_min - 1.0 <= start and cand_max + 1.0 >= end
                if covers:
                    return cls._rectangle_on_transverse_strip(
                        axial_span=(start, end),
                        is_horizontal=is_horizontal,
                        low=min(transverse(first), transverse(second)),
                        high=max(transverse(first), transverse(second)),
                    )
                if candidate[0] != candidate[-1]:
                    candidate.append(candidate[0])
                return candidate

        # Faces reais (mesmo colineares / face única): ancora a faixa na linha.
        strip = cls._strip_edges_from_boundary(
            clean_lines=clean_lines,
            width=width,
            is_horizontal=is_horizontal,
            transverse_center=center,
        )
        if strip is not None:
            return cls._rectangle_on_transverse_strip(
                axial_span=(start, end),
                is_horizontal=is_horizontal,
                low=strip[0],
                high=strip[1],
            )

        if not allow_synthetic:
            return []

        half = width / 2.0
        return cls._rectangle_on_transverse_strip(
            axial_span=(start, end),
            is_horizontal=is_horizontal,
            low=center - half,
            high=center + half,
        )

    @classmethod
    def build_provenance(
        cls,
        *,
        contour: Iterable[tuple[float, float]],
        boundary_lines: Iterable[Iterable[Any]] = (),
        is_horizontal: bool | None = None,
        segment_index: int | None = None,
    ) -> dict[str, Any]:
        """Cria prova observacional de um contorno FV a partir do DXF N1.

        O loader não preserva handles DXF em todas as entidades. Por isso cada
        face recebe um fingerprint determinístico de sua geometria normalizada,
        que continua rastreável sem inventar uma identidade de N2/N4.
        """
        points = [(float(point[0]), float(point[1])) for point in contour or []]
        if len(points) < 3:
            return {}
        xs = [point[0] for point in points]
        ys = [point[1] for point in points]
        inferred_horizontal = (max(xs) - min(xs)) >= (max(ys) - min(ys))
        horizontal = inferred_horizontal if is_horizontal is None else bool(is_horizontal)
        axis = 0 if horizontal else 1
        transverse_axis = 1 - axis
        span_min = min(point[axis] for point in points)
        span_max = max(point[axis] for point in points)
        width = max(point[transverse_axis] for point in points) - min(
            point[transverse_axis] for point in points
        )

        faces: list[dict[str, Any]] = []
        for raw in boundary_lines or []:
            clean: list[tuple[float, float]] = []
            for point in raw or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) < 2:
                continue
            line_min = min(point[axis] for point in clean)
            line_max = max(point[axis] for point in clean)
            overlap = min(span_max, line_max) - max(span_min, line_min)
            if overlap <= 0.05:
                continue
            normalized = [[round(x, 6), round(y, 6)] for x, y in clean]
            digest = hashlib.sha256(
                json.dumps(normalized, separators=(",", ":")).encode("utf-8")
            ).hexdigest()[:20]
            faces.append({
                "entity_id": f"dxf_geom:{digest}",
                "points": normalized,
                "axis_span": [round(line_min, 6), round(line_max, 6)],
                "transverse": round(
                    sum(point[transverse_axis] for point in clean) / len(clean), 6
                ),
                "axial_overlap": round(overlap, 6),
            })
        faces.sort(key=lambda face: (face["transverse"], face["entity_id"]))
        normalized_contour = [[round(x, 6), round(y, 6)] for x, y in points]
        contour_hash = hashlib.sha256(
            json.dumps(normalized_contour, separators=(",", ":")).encode("utf-8")
        ).hexdigest()[:20]
        return {
            "schema": "fv_provenance/v1",
            "authority": "n1_dxf_observational",
            "segment_index": segment_index,
            "axis": "x" if horizontal else "y",
            "axial_span": [round(span_min, 6), round(span_max, 6)],
            "width": round(width, 6),
            "contour_hash": f"contour:{contour_hash}",
            "source_entity_ids": [face["entity_id"] for face in faces],
            "physical_faces": faces,
        }

    @staticmethod
    def rectangular_contours_align(
        first: Iterable[tuple[float, float]],
        second: Iterable[tuple[float, float]],
        *,
        tolerance: float = 0.05,
    ) -> bool | None:
        """Compara dois retângulos físicos sem reduzir polígonos especiais.

        ``None`` significa que ao menos um contorno não é um retângulo axial;
        nesse caso a regra conservadora não autoriza substituição automática.
        """
        def rectangle_bbox(raw: Iterable[tuple[float, float]]):
            points: list[tuple[float, float]] = []
            for point in raw or []:
                try:
                    candidate = (float(point[0]), float(point[1]))
                except (TypeError, ValueError, IndexError):
                    continue
                if not any(
                    abs(candidate[0] - known[0]) <= tolerance
                    and abs(candidate[1] - known[1]) <= tolerance
                    for known in points
                ):
                    points.append(candidate)
            if len(points) != 4:
                return None
            min_x, max_x = min(x for x, _ in points), max(x for x, _ in points)
            min_y, max_y = min(y for _, y in points), max(y for _, y in points)
            if max_x - min_x <= tolerance or max_y - min_y <= tolerance:
                return None
            corners = ((min_x, min_y), (max_x, min_y), (max_x, max_y), (min_x, max_y))
            if not all(any(
                abs(point[0] - corner[0]) <= tolerance
                and abs(point[1] - corner[1]) <= tolerance
                for point in points
            ) for corner in corners):
                return None
            return min_x, min_y, max_x, max_y

        first_bbox = rectangle_bbox(first)
        second_bbox = rectangle_bbox(second)
        if first_bbox is None or second_bbox is None:
            return None
        return all(
            abs(left - right) <= tolerance
            for left, right in zip(first_bbox, second_bbox)
        )

    @classmethod
    def repair_area_links(
        cls,
        beam: dict,
        context_beams: Iterable[dict] | None = None,
    ) -> int:
        """Converte vínculos FV automáticos degenerados em áreas fechadas.

        Vínculos realmente validados nunca são tocados. O vão vem da topologia
        interpretada e a largura vem da dimensão estrutural do próprio segmento.
        """
        # Topologia: quebrar vãos onde viga mais funda cruza (antes de reparar
        # contornos). Idempotente; preserva validated. Headless e load-on-open
        # passam por aqui — o desktop já aplica em process_beam_fv, mas a
        # chamada aqui cobre o fast-path e o overlay de posição.
        if context_beams:
            cls.apply_deeper_crossing_splits(beam, context_beams=context_beams)

        links = beam.get("links") or {}
        fields = beam.get("fields") or {}
        classified = (beam.get("geometry") or {}).get("classified") or {}
        coords = classified.get("merged_bottom_groups_coords") or []
        raw_lines = classified.get("seg_bottom") or []
        side_lines = (
            list(classified.get("seg_side_a") or [])
            + list(classified.get("seg_side_b") or [])
        )
        context_lines: list[Any] = []
        for other in context_beams or []:
            if other is beam or not isinstance(other, dict):
                continue
            other_classified = (other.get("geometry") or {}).get("classified") or {}
            context_lines.extend(other_classified.get("seg_bottom") or [])
            context_lines.extend(other_classified.get("seg_side_a") or [])
            context_lines.extend(other_classified.get("seg_side_b") or [])
        default_is_horizontal = bool(beam.get("fv_is_h", beam.get("is_h", True)))
        beam_pos = beam.get("pos") or (0.0, 0.0)
        bottom_runs = classified.get("bottom_runs") or []
        run_segments: list[tuple[bool, tuple[float, float], Any]] = []
        for run in bottom_runs:
            run_coords = run.get("coords") or []
            run_lengths = run.get("lengths") or []
            for run_coord in run_coords[:min(len(run_coords), len(run_lengths))]:
                run_segments.append((
                    bool(run.get("is_h", default_is_horizontal)),
                    tuple(float(value) for value in run_coord),
                    run.get("pos", beam_pos),
                ))
        use_run_segments = bool(run_segments) and (
            len({segment[0] for segment in run_segments}) > 1
            or default_is_horizontal != bool(beam.get("is_h", True))
        )
        repaired = 0

        def dimension_width(index: int) -> float:
            texts = (
                fields.get(f"viga_fundo_seg_{index}_dim"),
                fields.get("dimensao"),
                beam.get("dim"),
            )
            for text in texts:
                match = re.search(r"(\d+(?:[.,]\d+)?)\s*[xX/]", str(text or ""))
                if match:
                    return float(match.group(1).replace(",", "."))
            return 20.0

        def _numeric_width(value: Any) -> float | None:
            match = re.search(r"(\d+(?:[.,]\d+)?)", str(value or ""))
            if not match:
                return None
            try:
                width = float(match.group(1).replace(",", "."))
            except ValueError:
                return None
            return width if width > 0.05 else None

        def repair_width(index: int, link: dict) -> float:
            if str(link.get("fv_measure_source") or "").startswith(
                "special_diagonal"
            ) or str(link.get("geometry_source") or "").startswith(
                "fundo_viga_interpreter_special_diagonal"
            ):
                return dimension_width(index)
            ficha = link.get("ficha") or {}
            if isinstance(ficha, dict):
                for key in ("largura_total_fundo", "largura_fundo", "largura"):
                    width = _numeric_width(ficha.get(key))
                    if width is not None:
                        return width
            width = _numeric_width(link.get("dim_width"))
            if width is not None:
                return width
            return dimension_width(index)

        def sync_bottom_segment(index: int, link: dict) -> None:
            """Mantem o espelho legado viga_segs.seg_bottom coerente.

            As fichas/diagnosticos ainda podem ler esse espelho em algumas
            rotas. Se repararmos apenas o link granular, o estado exportado pode
            continuar carregando pontos antigos.
            """
            bottom = links.get("viga_segs", {}).get("seg_bottom")
            if not isinstance(bottom, list) or index < 1 or index > len(bottom):
                return
            existing = bottom[index - 1]
            if not isinstance(existing, dict):
                return
            for key in (
                "type",
                "points",
                "evidence_segments",
                "len",
                "closed",
                "geometry_role",
                "geometry_source",
                "fv_provenance",
            ):
                if key in link:
                    existing[key] = link[key]

        def normalize_area_link(
            link: dict,
            points: list[tuple[float, float]],
            source: str,
            *,
            boundary_lines: Iterable[Iterable[Any]] = (),
            is_horizontal: bool | None = None,
            segment_index: int | None = None,
        ) -> None:
            length, width = cls._bbox_dimensions(points)
            link["points"] = points
            link["type"] = "poly"
            link["closed"] = True
            link["geometry_role"] = "area_fundo"
            link["geometry_source"] = source
            # Metadado observacional do próprio slot FV.  Não usa campos LV,
            # não altera os vértices humanos e permite a ficha distinguir o
            # segmento selecionado do contexto global da viga.
            generated_evidence = {
                "source_segment": int(segment_index or 0),
                "source_slot": "seg_bottom",
                "role": "fv_segment_local_contour",
                "points": [[round(float(x), 6), round(float(y), 6)] for x, y in points],
            }
            # Um reparo automático pode mover o contorno; sua própria prova
            # precisa acompanhar os novos pontos. Preservamos evidências
            # humanas/adicionais e substituímos somente o registro automático
            # deste segmento. ``0`` nunca é índice FV válido e é migrado.
            prior_evidence = list(link.get("evidence_segments") or [])
            def _same_automatic_segment(evidence: Any) -> bool:
                if not isinstance(evidence, dict):
                    return False
                if evidence.get("role") != "fv_segment_local_contour":
                    return False
                try:
                    recorded = int(evidence.get("source_segment") or 0)
                except (TypeError, ValueError):
                    return False
                return recorded in {0, int(segment_index or 0)}

            retained_evidence = [
                evidence for evidence in prior_evidence
                if not _same_automatic_segment(evidence)
            ]
            link["evidence_segments"] = [generated_evidence, *retained_evidence]
            canonical_length = None
            if str(link.get("fv_measure_source") or "").startswith(
                "chamfer_half_cm_snap"
            ):
                try:
                    candidate = float(link.get("fv_measure_length") or 0.0)
                    if candidate > 0.05:
                        canonical_length = candidate
                except (TypeError, ValueError):
                    pass
            if length > 0.01:
                link["len"] = canonical_length or length
                ficha = dict(link.get("ficha") or {})
                ficha["comprimento_total_fundo"] = cls._format_measure(
                    canonical_length or length
                )
                if width > 0.05:
                    ficha["largura_total_fundo"] = cls._format_measure(width)
                link["ficha"] = ficha
            if not link.get("validated"):
                link["fv_provenance"] = cls.build_provenance(
                    contour=points,
                    boundary_lines=boundary_lines,
                    is_horizontal=is_horizontal,
                    segment_index=segment_index,
                )

        def normalize_special_diagonal_link(
            link: dict,
            points: list[tuple[float, float]],
            source: str,
            structural_width: float,
            segment_index: int,
        ) -> None:
            normalize_area_link(
                link, points, source, segment_index=segment_index,
            )
            measure_length = cls._longest_axis_edge(points)
            if measure_length > 0.05:
                link["fv_measure_length"] = measure_length
                if structural_width > 0.05:
                    link["fv_measure_width"] = structural_width
                # A largura declarada do fundo especial deve continuar vindo da
                # ficha/validação quando existir. Não inventamos largura a partir
                # do bbox global de uma diagonal, porque isso vira falso positivo.
                link["fv_measure_source"] = "special_diagonal_longest_edge"
                ficha = dict(link.get("ficha") or {})
                ficha["comprimento_total_fundo"] = cls._format_measure(measure_length)
                if structural_width > 0.05:
                    ficha["largura_total_fundo"] = cls._format_measure(structural_width)
                link["ficha"] = ficha

        for source_key, slots in list(links.items()):
            match = re.match(r"^viga_fundo_seg_(\d+)_area_segs$", str(source_key))
            if not match or not isinstance(slots, dict):
                continue
            index = int(match.group(1))
            contours = slots.get("contour") or []
            if not contours or not isinstance(contours[0], dict):
                continue
            link = contours[0]
            points = []
            for point in link.get("points") or []:
                try:
                    points.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue

            if link.get("validated"):
                length, width = cls._bbox_dimensions(points)
                if length > 0.05:
                    ficha = dict(link.get("ficha") or {})
                    ficha["comprimento_total_fundo"] = cls._format_measure(length)
                    if width > 0.05:
                        ficha["largura_total_fundo"] = cls._format_measure(width)
                    link["ficha"] = ficha
                    link["len"] = length
                    slots["contour"] = [link]
                    sync_bottom_segment(index, link)
                continue

            # Uma geometria de área já válida (inclusive chanfro/obstáculo)
            # é a fonte mais rica e não deve ser substituída por retângulo.
            # Ao reparar retângulos simples, a ficha persistida no próprio link
            # tem prioridade sobre a dimensão automática do segmento: ela pode
            # representar validação/ground truth já feita pelo dono.
            width = repair_width(index, link)
            structural_width = dimension_width(index) or width
            current_area = cls._polygon_area(points)
            diagonal_area_points = cls._diagonal_pair_contour(
                side_lines=side_lines,
                cap_lines=list(raw_lines) + side_lines,
                extension_lines=context_lines,
                width=width,
            )
            diagonal_area = cls._polygon_area(diagonal_area_points)
            if current_area > 0.05:
                diagonal_length, diagonal_width = cls._bbox_dimensions(
                    diagonal_area_points
                )
                _, current_width = cls._bbox_dimensions(points)
                current_length, _ = cls._bbox_dimensions(points)
                diagonal_transverse_explodes = (
                    diagonal_area > current_area * 1.5
                    and diagonal_width > max(
                        width * 4.0,
                        current_width * 4.0,
                        80.0,
                    )
                )
                current_is_short_cap = current_length <= max(width * 3.0, 80.0)
                if diagonal_area > current_area * 1.5 and not diagonal_transverse_explodes:
                    if points != diagonal_area_points:
                        repaired += 1
                    normalize_area_link(
                        link,
                        diagonal_area_points,
                        "fundo_viga_interpreter_diagonal_pair",
                        segment_index=index,
                    )
                    slots["contour"] = [link]
                    sync_bottom_segment(index, link)
                    continue
                if diagonal_area > current_area * 1.5 and current_is_short_cap:
                    if points != diagonal_area_points:
                        repaired += 1
                    normalize_special_diagonal_link(
                        link,
                        diagonal_area_points,
                        "fundo_viga_interpreter_special_diagonal_l",
                        structural_width,
                        index,
                    )
                    slots["contour"] = [link]
                    sync_bottom_segment(index, link)
                    continue
                unique_points = []
                for point in points:
                    if point not in unique_points:
                        unique_points.append(point)
                if unique_points and unique_points[0] == unique_points[-1]:
                    unique_points = unique_points[:-1]
                if 2 <= len(unique_points) <= 4:
                    xs = [point[0] for point in points]
                    ys = [point[1] for point in points]
                    dx = max(xs) - min(xs)
                    dy = max(ys) - min(ys)
                    is_horizontal = dx >= dy
                    current_width = dy if is_horizontal else dx
                    if abs(current_width - width) > 0.05:
                        axis_values = xs if is_horizontal else ys
                        transverse_values = ys if is_horizontal else xs
                        span = (min(axis_values), max(axis_values))
                        center = (
                            min(transverse_values) + max(transverse_values)
                        ) / 2.0
                        evidence_lines = (
                            list(raw_lines) + list(side_lines) + list(context_lines)
                        )
                        matching_lines = cls.matching_lines_for_span(
                            evidence_lines,
                            is_horizontal=is_horizontal,
                            axial_span=span,
                        )
                        # Preferir centro das faces DXF do vão (não só o
                        # rótulo): label deslocado em Y/X gerava marco
                        # "abaixo/à esquerda" da viga real (achados V304/V308/
                        # V309). Com faces, o strip ancora nas linhas; o centro
                        # só desempata face única.
                        face_center = center
                        if matching_lines:
                            face_vals = [
                                cls._line_transverse(
                                    cls._clean_polyline_points(line),
                                    is_horizontal=is_horizontal,
                                )
                                for line in matching_lines
                                if cls._clean_polyline_points(line)
                            ]
                            if face_vals:
                                face_center = sum(face_vals) / len(face_vals)
                        label_center = float(
                            (beam_pos[1] if is_horizontal else beam_pos[0])
                            if isinstance(beam_pos, (list, tuple)) and len(beam_pos) >= 2
                            else face_center
                        )
                        transverse_center = (
                            face_center if matching_lines else label_center
                        )
                        area_points = cls.build_area_contour(
                            axial_span=span,
                            width=width,
                            is_horizontal=is_horizontal,
                            transverse_center=transverse_center,
                            boundary_lines=matching_lines,
                            allow_synthetic=not matching_lines,
                        )
                        if area_points and points != area_points:
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_width_repair",
                                boundary_lines=matching_lines,
                                is_horizontal=is_horizontal,
                                segment_index=index,
                            )
                            slots["contour"] = [link]
                            sync_bottom_segment(index, link)
                            continue
                # Um polígono automático pode estar fechado e ter a largura
                # correta, mas ainda perder parte do vão que o próprio
                # BeamTracer consolidou (tipicamente quando uma face vem
                # quebrada por encontro/cap). Isso NÃO é chanfro especial: os
                # especiais já foram resolvidos acima por diagonal_pair e são
                # marcados com fv_measure_source. Para o caso comum, o span
                # N1 canônico prevalece; nunca aplicar a geometria validada.
                special_measure = str(link.get("fv_measure_source") or "")
                special_geometry = str(link.get("geometry_source") or "")
                if (
                    not use_run_segments
                    and index <= len(coords)
                    and not special_measure.startswith((
                        "special_diagonal", "chamfer_half_cm_snap",
                    ))
                    and "special_diagonal" not in special_geometry
                ):
                    canonical_span = tuple(float(value) for value in coords[index - 1])
                    span_min, span_max = sorted(canonical_span)
                    expected_length = span_max - span_min
                    current_is_horizontal = (
                        max(point[0] for point in points)
                        - min(point[0] for point in points)
                    ) >= (
                        max(point[1] for point in points)
                        - min(point[1] for point in points)
                    )
                    current_axis = 0 if current_is_horizontal else 1
                    current_min = min(point[current_axis] for point in points)
                    current_max = max(point[current_axis] for point in points)
                    current_length = current_max - current_min
                    # Comprimento igual não basta: um contorno reaproveitado de
                    # rodada anterior pode ter o tamanho certo mas cobrir um
                    # trecho diferente (índice trocado, vão vizinho). Sem
                    # checar a posição, o comprimento sozinho deixa esse
                    # deslocamento passar sem reparo.
                    position_mismatch = (
                        abs(current_min - span_min) > 0.05
                        or abs(current_max - span_max) > 0.05
                    )
                    if (
                        expected_length > 0.05
                        and (
                            abs(current_length - expected_length) > 0.05
                            or position_mismatch
                        )
                    ):
                        transverse_axis = 1 if current_is_horizontal else 0
                        center = (
                            max(point[transverse_axis] for point in points)
                            + min(point[transverse_axis] for point in points)
                        ) / 2.0
                        evidence_lines = (
                            list(raw_lines) + list(side_lines) + list(context_lines)
                        )
                        matching_lines = cls.matching_lines_for_span(
                            evidence_lines,
                            is_horizontal=current_is_horizontal,
                            axial_span=(span_min, span_max),
                        )
                        face_center = center
                        if matching_lines:
                            face_vals = [
                                cls._line_transverse(
                                    cls._clean_polyline_points(line),
                                    is_horizontal=current_is_horizontal,
                                )
                                for line in matching_lines
                                if cls._clean_polyline_points(line)
                            ]
                            if face_vals:
                                face_center = sum(face_vals) / len(face_vals)
                        label_center = float(
                            (beam_pos[transverse_axis]
                             if isinstance(beam_pos, (list, tuple))
                             and len(beam_pos) > transverse_axis
                             else face_center)
                        )
                        area_points = cls.build_area_contour(
                            axial_span=(span_min, span_max),
                            width=width,
                            is_horizontal=current_is_horizontal,
                            transverse_center=(
                                face_center if matching_lines else label_center
                            ),
                            boundary_lines=matching_lines,
                            allow_synthetic=not matching_lines,
                        )
                        if area_points and points != area_points:
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_canonical_span_repair",
                                boundary_lines=matching_lines,
                                is_horizontal=current_is_horizontal,
                                segment_index=index,
                            )
                            slots["contour"] = [link]
                            sync_bottom_segment(index, link)
                            continue
                if use_run_segments and index <= len(run_segments):
                    is_horizontal, span, segment_pos = run_segments[index - 1]
                    axis = 0 if is_horizontal else 1
                    transverse_axis = 1 - axis
                    span_min, span_max = sorted(span)
                    expected_length = span_max - span_min
                    current_length = (
                        max(point[axis] for point in points)
                        - min(point[axis] for point in points)
                    ) if points else 0.0
                    if (
                        expected_length > 0.01
                        and abs(current_length - expected_length) > 0.05
                    ):
                        point_transverse_span = (
                            max(point[transverse_axis] for point in points)
                            - min(point[transverse_axis] for point in points)
                            if points else 0.0
                        )
                        if point_transverse_span > 0.05:
                            center = (
                                max(point[transverse_axis] for point in points)
                                + min(point[transverse_axis] for point in points)
                            ) / 2.0
                        else:
                            center = float(segment_pos[transverse_axis])
                        evidence_lines = (
                            list(raw_lines) + list(side_lines) + list(context_lines)
                        )
                        matching_lines = cls.matching_lines_for_span(
                            evidence_lines,
                            is_horizontal=is_horizontal,
                            axial_span=(span_min, span_max),
                        )
                        label_center = float(segment_pos[transverse_axis])
                        area_points = cls.build_area_contour(
                            axial_span=(span_min, span_max),
                            width=width,
                            is_horizontal=is_horizontal,
                            transverse_center=(
                                label_center if matching_lines else center
                            ),
                            boundary_lines=matching_lines,
                            allow_synthetic=not matching_lines,
                        )
                        if area_points and points != area_points:
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_run_span_repair",
                                boundary_lines=matching_lines,
                                is_horizontal=is_horizontal,
                                segment_index=index,
                            )
                            slots["contour"] = [link]
                            sync_bottom_segment(index, link)
                            continue

                # Tamanho/vão já corretos, mas retângulo flutuando fora das
                # linhas verdes do DXF (caso majoritário no SA). Reancora.
                special_measure = str(link.get("fv_measure_source") or "")
                special_geometry = str(link.get("geometry_source") or "")
                if (
                    2 <= len(unique_points) <= 4
                    and not special_measure.startswith((
                        "special_diagonal", "chamfer_half_cm_snap",
                    ))
                    and "special_diagonal" not in special_geometry
                ):
                    xs = [point[0] for point in points]
                    ys = [point[1] for point in points]
                    dx = max(xs) - min(xs)
                    dy = max(ys) - min(ys)
                    is_horizontal = dx >= dy
                    axis = 0 if is_horizontal else 1
                    transverse_axis = 1 - axis
                    span = (
                        min(point[axis] for point in points),
                        max(point[axis] for point in points),
                    )
                    if index <= len(coords) and not use_run_segments:
                        span = tuple(float(value) for value in coords[index - 1])
                    elif use_run_segments and index <= len(run_segments):
                        is_horizontal, span, _segment_pos = run_segments[index - 1]
                        axis = 0 if is_horizontal else 1
                        transverse_axis = 1 - axis
                    evidence_lines = (
                        list(raw_lines) + list(side_lines) + list(context_lines)
                    )
                    matching_lines = cls.matching_lines_for_span(
                        evidence_lines,
                        is_horizontal=is_horizontal,
                        axial_span=span,
                    )
                    bottom_matching = cls.matching_lines_for_span(
                        raw_lines,
                        is_horizontal=is_horizontal,
                        axial_span=span,
                    )
                    if bottom_matching:
                        matching_lines = bottom_matching
                    if matching_lines and not cls.contour_overlays_boundary_lines(
                        points,
                        matching_lines,
                        is_horizontal=is_horizontal,
                    ):
                        face_vals = [
                            cls._line_transverse(
                                cls._clean_polyline_points(line),
                                is_horizontal=is_horizontal,
                            )
                            for line in matching_lines
                            if cls._clean_polyline_points(line)
                        ]
                        if face_vals:
                            face_center = sum(face_vals) / len(face_vals)
                        else:
                            face_center = (
                                min(point[transverse_axis] for point in points)
                                + max(point[transverse_axis] for point in points)
                            ) / 2.0
                        area_points = cls.build_area_contour(
                            axial_span=span,
                            width=width,
                            is_horizontal=is_horizontal,
                            transverse_center=face_center,
                            boundary_lines=matching_lines,
                            allow_synthetic=False,
                        )
                        if (
                            area_points
                            and cls.contour_overlays_boundary_lines(
                                area_points,
                                matching_lines,
                                is_horizontal=is_horizontal,
                            )
                            and cls.rectangular_contours_align(
                                points, area_points, tolerance=0.5,
                            ) is not True
                        ):
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_overlay_position_repair",
                                boundary_lines=matching_lines,
                                is_horizontal=is_horizontal,
                                segment_index=index,
                            )
                            slots["contour"] = [link]
                            sync_bottom_segment(index, link)
                            continue

                if points and points[0] != points[-1]:
                    points.append(points[0])
                    repaired += 1
                normalize_area_link(
                    link,
                    points,
                    link.get("geometry_source") or "fundo_viga_interpreter",
                    segment_index=index,
                )
                slots["contour"] = [link]
                sync_bottom_segment(index, link)
                continue

            if use_run_segments and index <= len(run_segments):
                is_horizontal, span, segment_pos = run_segments[index - 1]
            else:
                is_horizontal = default_is_horizontal
                segment_pos = beam_pos
                if index <= len(coords):
                    span = tuple(float(value) for value in coords[index - 1])
                elif points:
                    axis = 0 if is_horizontal else 1
                    span = (
                        min(point[axis] for point in points),
                        max(point[axis] for point in points),
                    )
                else:
                    continue

            axis = 0 if is_horizontal else 1
            transverse_axis = 1 - axis
            if span[1] - span[0] <= 0.01:
                continue

            point_transverse_span = (
                max(point[transverse_axis] for point in points)
                - min(point[transverse_axis] for point in points)
                if points else 0.0
            )
            if point_transverse_span > 0.05:
                center = (
                    max(point[transverse_axis] for point in points)
                    + min(point[transverse_axis] for point in points)
                ) / 2.0
            else:
                center = float(segment_pos[transverse_axis])

            span_min, span_max = sorted(span)
            evidence_lines = list(raw_lines) + list(side_lines) + list(context_lines)
            matching_lines = cls.matching_lines_for_span(
                evidence_lines,
                is_horizontal=is_horizontal,
                axial_span=(span_min, span_max),
            )
            # Faces longitudinais do fundo têm prioridade sobre laterais
            # soltas, mas laterais entram se o fundo veio colinear/cap.
            bottom_matching = cls.matching_lines_for_span(
                raw_lines,
                is_horizontal=is_horizontal,
                axial_span=(span_min, span_max),
            )
            if bottom_matching:
                matching_lines = bottom_matching

            width = dimension_width(index)
            boundary_values = [
                point[transverse_axis]
                for line in matching_lines
                for point in line
            ]
            if (
                boundary_values
                and max(boundary_values) - min(boundary_values) <= 0.05
            ):
                boundary = sum(boundary_values) / len(boundary_values)
                endpoint_tol = max(2.0, width * 0.25)
                candidates = []
                for line in side_lines:
                    for point in line or []:
                        try:
                            axial = float(point[axis])
                            transverse_value = float(point[transverse_axis])
                        except (TypeError, ValueError, IndexError):
                            continue
                        near_endpoint = min(
                            abs(axial - span_min), abs(axial - span_max)
                        ) <= endpoint_tol
                        distance = abs(transverse_value - boundary)
                        if near_endpoint and distance > 0.05:
                            candidates.append((abs(distance - width), transverse_value))
                if candidates:
                    error, opposite = min(candidates)
                    if error <= max(0.5, width * 0.15):
                        center = (boundary + opposite) / 2.0

            area_points = cls._diagonal_pair_contour(
                side_lines=side_lines,
                cap_lines=list(raw_lines) + side_lines,
                extension_lines=context_lines,
                width=width,
            )
            if not area_points:
                # Sem linha DXF no vão, não inventa retângulo flutuante.
                area_points = cls.build_area_contour(
                    axial_span=span,
                    width=width,
                    is_horizontal=is_horizontal,
                    transverse_center=center,
                    boundary_lines=matching_lines,
                    allow_synthetic=not matching_lines,
                )
            if not area_points:
                continue
            if points != area_points:
                repaired += 1
            normalize_area_link(
                link,
                area_points,
                "fundo_viga_interpreter",
                boundary_lines=matching_lines,
                is_horizontal=is_horizontal,
                segment_index=index,
            )
            slots["contour"] = [link]
            sync_bottom_segment(index, link)
        return repaired

    @staticmethod
    def _fv_existing_contour_is_well_formed(link: Any) -> bool:
        """True se o contorno já persistido é um retângulo fechado plausível.

        Não prova posição — só que os 4 vértices distintos existem e não é
        degenerado. Vínculo humano (``validated``) passa sempre.
        """
        if not isinstance(link, dict):
            return False
        if link.get("validated"):
            return True
        raw_points = link.get("points") or []
        unique: list[tuple[float, float]] = []
        for point in raw_points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            try:
                xy = (round(float(point[0]), 3), round(float(point[1]), 3))
            except (TypeError, ValueError):
                continue
            if xy not in unique:
                unique.append(xy)
        if len(unique) < 4:
            return False
        xs = [point[0] for point in unique]
        ys = [point[1] for point in unique]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        if (max_x - min_x) <= 1.0 or (max_y - min_y) <= 1.0:
            return False
        tolerance = 2.0
        corners = (
            (min_x, min_y), (max_x, min_y),
            (max_x, max_y), (min_x, max_y),
        )
        return all(
            any(
                abs(px - cx) <= tolerance and abs(py - cy) <= tolerance
                for px, py in unique
            )
            for cx, cy in corners
        )

    @staticmethod
    def _fv_existing_contour_overlaps_span(
        link: Any, axis_index: int, span_min: float, span_max: float,
    ) -> bool:
        """Overlap axial mínimo para considerar o contorno candidato ao índice.

        Só decide elegibilidade para comparação; nunca decide sozinho que a
        posição está certa (ver ``_fv_existing_contour_matches_canonical_span``).
        """
        if not isinstance(link, dict):
            return False
        values: list[float] = []
        for point in link.get("points") or []:
            try:
                values.append(float(point[axis_index]))
            except (TypeError, ValueError, IndexError):
                continue
        if not values:
            return False
        current_min, current_max = min(values), max(values)
        proven_min, proven_max = sorted((float(span_min), float(span_max)))
        current_length = current_max - current_min
        proven_length = proven_max - proven_min
        if current_length <= 0.05 or proven_length <= 0.05:
            return False
        overlap = min(current_max, proven_max) - max(current_min, proven_min)
        return overlap >= max(1.0, min(current_length, proven_length) * 0.20)

    @staticmethod
    def _fv_existing_contour_matches_canonical_span(
        link: Any, axis_index: int, span_min: float, span_max: float,
    ) -> bool:
        """Confirma que o contorno existente cobre o MESMO vão do índice atual.

        Regressão V301 (2026-07-18): um contorno reaproveitado de rodada
        anterior pode ter comprimento igual ao índice atual mas estar
        fisicamente na posição de um índice vizinho (fronteira reaproveitada,
        segmentação recalculada). Overlap parcial (20%) prova candidatura,
        nunca identidade — exige as duas bordas dentro de 0.5cm do vão
        canônico atual antes de preservar a geometria existente.
        """
        if not isinstance(link, dict):
            return False
        values: list[float] = []
        for point in link.get("points") or []:
            try:
                values.append(float(point[axis_index]))
            except (TypeError, ValueError, IndexError):
                continue
        if not values:
            return False
        current_min, current_max = min(values), max(values)
        proven_min, proven_max = sorted((float(span_min), float(span_max)))
        tolerance = 0.5
        return (
            abs(current_min - proven_min) <= tolerance
            and abs(current_max - proven_max) <= tolerance
        )

    @staticmethod
    def _fv_automatic_contour_matches_dxf(
        link: Any, inferred_geom: list[list[float]] | None,
    ) -> bool | None:
        """Recusa retângulo automático deslocado em relação às faces DXF.

        Polígonos não retangulares (chanfro/L) retornam ``None`` na
        comparação e permanecem sob a regra especializada do interpretador;
        não são achatados por este guardrail. ``None`` (ambíguo) NÃO prova
        alinhamento — o chamador deve tratá-lo como reprovado, nunca como
        aprovado por omissão.
        """
        if not isinstance(link, dict) or not inferred_geom:
            return True
        return FundoVigaInterpreter.rectangular_contours_align(
            link.get("points") or [], inferred_geom, tolerance=0.05,
        )

    @staticmethod
    def _parse_height_pair(dim_text: Any) -> tuple[float, float] | None:
        """(largura, altura) de um texto tipo ``19/55`` — altura é sempre a maior.

        Mesma convenção de ``scripts/analise_geral_headless.py::_parse_dim_pair``,
        reimplementada aqui para não criar dependência circular (aquele módulo
        importa deste pacote).
        """
        if not dim_text:
            return None
        match = re.search(
            r"(\d+(?:[.,]\d+)?)\s*/\s*(\d+(?:[.,]\d+)?)", str(dim_text)
        )
        if not match:
            return None
        try:
            first = float(match.group(1).replace(",", "."))
            second = float(match.group(2).replace(",", "."))
        except ValueError:
            return None
        return (min(first, second), max(first, second))

    @classmethod
    def split_bottom_spans_at_deeper_crossings(
        cls,
        coords: Iterable[Interval],
        *,
        is_horizontal: bool,
        beam_pos: tuple[float, float],
        own_dim_text: Any,
        context_beams: Iterable[dict],
        own_name: str,
    ) -> list[Interval]:
        """Divide vãos onde uma viga MAIS FUNDA cruza perpendicularmente.

        Regra estrutural (achado do dono, 2026-07-20, caso real V302×V320×V322):
        no cruzamento de dois fundos de viga, o mais fundo (maior altura da
        seção) continua e preenche a área do cruzamento; o mais raso para ali.
        Só a viga MAIS RASA é dividida; a mais funda não é tocada.

        Versão 2 (2026-07-20, pós-regressão): a primeira versão comparava só a
        posição axial do "outro" feixe contra o vão próprio, sem confirmar que
        o outro feixe de fato chegava fisicamente até ali — isso quebrou 3
        vigas (V308/V327/V332, achadas por instrumentação real com
        `scripts/arete/tmp/_fv_crossing_diag.py`) que tinham um feixe mais
        fundo qualquer coincidindo em posição, mas em outra linha do
        pavimento (ex.: V325 a 738cm de distância transversal de V308) ou
        muito perto da borda do próprio vão (produzindo lascas de ~10-19cm
        sem sentido estrutural). Três critérios adicionais, todos verificados
        contra os 36 feixes reais do 13_PAV antes de aceitar:

        1. **Alcance físico** — o outro feixe só interrompe se o PRÓPRIO vão
           dele (`merged_bottom_groups_coords`, no eixo dele) contém a
           posição transversal desta viga; caso contrário ele nunca chega
           fisicamente até aqui, mesmo que sua posição nominal coincida.
        2. **Dominância de profundidade** — o outro feixe precisa ser pelo
           menos ``_DEEPER_CROSSING_RATIO`` (1.5×) mais fundo, não só
           nominalmente maior. A distribuição real de alturas do 13_PAV tem
           um gap claro (50/55/60/66cm vs. 120/192cm, nada entre 70-110) —
           feixes do mesmo patamar (ex. 50 vs 55) não dominam um ao outro;
           só um feixe de um patamar estrutural claramente mais profundo
           justifica interromper o mais raso.
        3. **Fragmento mínimo** — um corte que deixaria um pedaço menor que a
           largura do próprio feixe que cruza não é um painel real, é
           artefato de arredondamento na borda da zona de cruzamento; esse
           pedaço é descartado (equivalente a considerá-lo parte da pegada
           do feixe mais fundo).
        """
        own_pair = cls._parse_height_pair(own_dim_text)
        if own_pair is None or not beam_pos or len(beam_pos) < 2:
            return list(coords)
        own_width, own_height = own_pair
        axis = 0 if is_horizontal else 1
        transverse_axis = 1 - axis
        own_transverse_pos = float(beam_pos[transverse_axis])
        own_half_width = max(own_width / 2.0, 9.5)

        crossing_zones: list[tuple[float, float, float]] = []
        for other in context_beams or []:
            if not isinstance(other, dict):
                continue
            other_name = str(other.get("name") or "").strip().upper()
            if not other_name or other_name == str(own_name or "").strip().upper():
                continue
            other_is_h = bool(other.get("is_h", True))
            if other_is_h == is_horizontal:
                continue  # só cruzamento perpendicular interrompe o fundo
            other_fields = other.get("fields") or {}
            other_pair = cls._parse_height_pair(
                other_fields.get("dimensao") or other.get("dim")
            )
            if other_pair is None or other_pair[1] < own_height * cls._DEEPER_CROSSING_RATIO:
                continue  # não domina o suficiente (mesmo patamar estrutural)
            other_pos = other.get("pos")
            if not other_pos or len(other_pos) < 2:
                continue
            other_width = other_pair[0]
            other_coords = (
                (other.get("geometry") or {}).get("classified") or {}
            ).get("merged_bottom_groups_coords") or []
            other_half_width = max(other_width / 2.0, 9.5)
            reaches = any(
                (min(span) - own_half_width) <= own_transverse_pos <= (max(span) + own_half_width)
                for span in other_coords
            )
            if not reaches:
                continue  # o outro feixe não se estende até este ponto
            other_axis_pos = float(other_pos[axis])
            crossing_zones.append(
                (other_axis_pos - other_half_width, other_axis_pos + other_half_width, other_width)
            )

        if not crossing_zones:
            return list(coords)

        result: list[Interval] = []
        for span in coords:
            span_min, span_max = sorted((float(span[0]), float(span[1])))
            pieces: list[Interval] = [(span_min, span_max)]
            for zone_min, zone_max, other_width in crossing_zones:
                zone_min, zone_max = sorted((zone_min, zone_max))
                next_pieces: list[Interval] = []
                for p_min, p_max in pieces:
                    if zone_max <= p_min or zone_min >= p_max:
                        next_pieces.append((p_min, p_max))
                        continue
                    if zone_min > p_min + 0.5:
                        left = (p_min, zone_min)
                        if (left[1] - left[0]) >= other_width:
                            next_pieces.append(left)
                    if zone_max < p_max - 0.5:
                        right = (zone_max, p_max)
                        if (right[1] - right[0]) >= other_width:
                            next_pieces.append(right)
                pieces = next_pieces
            result.extend(pieces)
        return sorted(result)

    _DEEPER_CROSSING_RATIO = 1.5

    @classmethod
    def _coords_as_tuples(cls, coords: Iterable[Interval]) -> list[Interval]:
        out: list[Interval] = []
        for span in coords or []:
            try:
                out.append((float(span[0]), float(span[1])))
            except (TypeError, ValueError, IndexError):
                continue
        return out

    @classmethod
    def _beam_has_validated_fundo(cls, beam: dict) -> bool:
        links = beam.get("links") or {}
        for key, slots in links.items():
            if not re.match(r"^viga_fundo_seg_\d+_area_segs$", str(key)):
                continue
            if not isinstance(slots, dict):
                continue
            for contour in slots.get("contour") or []:
                if isinstance(contour, dict) and contour.get("validated"):
                    return True
        return False

    @classmethod
    def _rebuild_auto_area_slots_from_coords(
        cls,
        beam: dict,
        coords: list[Interval],
        *,
        is_horizontal: bool,
        beam_pos: tuple[float, float],
        width: float,
    ) -> int:
        """Materializa slots area_segs automáticos a partir dos vãos canônicos.

        Usado após ``split_bottom_spans_at_deeper_crossings`` quando a contagem
        de painéis muda. Nunca remove/sobrescreve contorno ``validated``.
        """
        if cls._beam_has_validated_fundo(beam):
            return 0
        links = beam.setdefault("links", {})
        fields = beam.setdefault("fields", {})
        half = max(float(width) * 0.5, 9.5)
        bx = float(beam_pos[0]) if beam_pos and len(beam_pos) >= 2 else 0.0
        by = float(beam_pos[1]) if beam_pos and len(beam_pos) >= 2 else 0.0
        created = 0
        target_count = len(coords)
        # remove slots automáticos além do novo total
        for key in list(links.keys()):
            match = re.match(r"^viga_fundo_seg_(\d+)_area_segs$", str(key))
            if not match:
                continue
            idx = int(match.group(1))
            if idx > target_count:
                slots = links.get(key) or {}
                contour = (slots.get("contour") or [{}])[0] if isinstance(slots, dict) else {}
                if isinstance(contour, dict) and contour.get("validated"):
                    continue
                links.pop(key, None)
                fields.pop(f"viga_fundo_seg_{idx}_dim", None)
                beam.pop(f"viga_fundo_seg_{idx}_exists", None)
        for index, span in enumerate(coords, start=1):
            span_min, span_max = sorted((float(span[0]), float(span[1])))
            if is_horizontal:
                points = [
                    [span_min, by - half],
                    [span_max, by - half],
                    [span_max, by + half],
                    [span_min, by + half],
                    [span_min, by - half],
                ]
            else:
                points = [
                    [bx - half, span_min],
                    [bx + half, span_min],
                    [bx + half, span_max],
                    [bx - half, span_max],
                    [bx - half, span_min],
                ]
            key = f"viga_fundo_seg_{index}_area_segs"
            length = abs(span_max - span_min)
            link = {
                "type": "poly",
                "points": points,
                "len": length,
                "closed": True,
                "geometry_role": "area_fundo",
                "geometry_source": "fundo_viga_interpreter_deeper_crossing_split",
                "ficha": {
                    "comprimento_total_fundo": cls._format_measure(length),
                    "largura_total_fundo": cls._format_measure(width),
                },
            }
            existing = links.get(key)
            if isinstance(existing, dict):
                contour0 = (existing.get("contour") or [{}])[0]
                if isinstance(contour0, dict) and contour0.get("validated"):
                    continue
            links[key] = {"contour": [link]}
            beam[f"viga_fundo_seg_{index}_exists"] = True
            fields[f"viga_fundo_seg_{index}_dim"] = fields.get("dimensao") or beam.get("dim")
            created += 1
        # espelho legado seg_bottom
        bottom = links.setdefault("viga_segs", {}).setdefault("seg_bottom", [])
        if isinstance(bottom, list):
            new_bottom = []
            for index, span in enumerate(coords, start=1):
                slots = links.get(f"viga_fundo_seg_{index}_area_segs") or {}
                contour = (slots.get("contour") or [{}])[0]
                if isinstance(contour, dict):
                    new_bottom.append(dict(contour))
            links["viga_segs"]["seg_bottom"] = new_bottom
        return created

    @classmethod
    def apply_deeper_crossing_splits(
        cls,
        beam: dict,
        context_beams: Iterable[dict] | None = None,
    ) -> bool:
        """Aplica quebra por viga mais funda na topologia FV do feixe.

        Retorna True se ``merged_bottom_groups_coords`` mudou. Preserva vigas
        com contorno humano validado. Materializa slots automáticos quando a
        contagem de painéis aumenta/diminui para o ``repair_area_links``
        reancorar nas faces DXF.
        """
        if not isinstance(beam, dict):
            return False
        if cls._beam_has_validated_fundo(beam):
            return False
        geometry = beam.setdefault("geometry", {})
        if not isinstance(geometry, dict):
            return False
        classified = geometry.setdefault("classified", {})
        if not isinstance(classified, dict):
            return False
        own_coords = cls._coords_as_tuples(
            classified.get("merged_bottom_groups_coords") or []
        )
        if not own_coords:
            return False
        fields = beam.get("fields") or {}
        is_horizontal = bool(beam.get("fv_is_h", beam.get("is_h", True)))
        beam_pos = tuple(beam.get("pos") or (0.0, 0.0))
        split_coords = cls.split_bottom_spans_at_deeper_crossings(
            own_coords,
            is_horizontal=is_horizontal,
            beam_pos=beam_pos,
            own_dim_text=fields.get("dimensao") or beam.get("dim"),
            context_beams=context_beams or [],
            own_name=str(beam.get("name") or ""),
        )
        split_coords = cls._coords_as_tuples(split_coords)
        if split_coords == own_coords:
            return False
        classified["merged_bottom_groups_coords"] = [
            [start, end] for start, end in split_coords
        ]
        classified["merged_bottom_lengths"] = [
            round(abs(end - start), 6) for start, end in split_coords
        ]
        own_pair = cls._parse_height_pair(fields.get("dimensao") or beam.get("dim"))
        width = float(own_pair[0]) if own_pair else 19.0
        cls._rebuild_auto_area_slots_from_coords(
            beam,
            split_coords,
            is_horizontal=is_horizontal,
            beam_pos=beam_pos,
            width=width,
        )
        return True

    @classmethod
    def apply_deeper_crossing_splits_all(
        cls,
        beams: Iterable[dict],
    ) -> int:
        """Aplica a quebra em todos os feixes com contexto mútuo. Retorna quantos mudaram."""
        beam_list = [b for b in (beams or []) if isinstance(b, dict)]
        changed = 0
        for beam in beam_list:
            if cls.apply_deeper_crossing_splits(beam, context_beams=beam_list):
                changed += 1
        return changed

    @classmethod
    def reconcile_persisted_segments(
        cls,
        beam: dict,
        segments: Iterable[dict],
        *,
        is_horizontal: bool,
        beam_pos: tuple[float, float],
        default_height: float = 20.0,
        geometry_policy: Callable[[dict, str], str | None] | None = None,
        log: Callable[[str], None] | None = None,
    ) -> None:
        """Reconcilia ``viga_fundo_seg_N_area_segs`` com os painéis atuais.

        Único dono da decisão "manter o contorno já persistido" vs "recriar
        a partir do span canônico atual" para cada índice de segmento FV.
        Preserva vínculo humano (``validated``) sempre e recorte da preficha
        (política ``ignore``) sem renascer. Para os demais casos, um contorno
        existente só sobrevive quando cobre o MESMO vão do índice atual
        (``_fv_existing_contour_matches_canonical_span``) e está alinhado às
        faces DXF; caso contrário a geometria é reconstruída a partir do
        contrato fresco (``seg.get('geometry')``), nunca de um retângulo
        centrado apenas no rótulo sem essa prova de posição.
        """
        beam_pos = tuple(beam_pos) if beam_pos else (0.0, 0.0)
        half_height = float(default_height or 20.0) / 2.0
        axis_index = 0 if is_horizontal else 1
        emit = log or (lambda _msg: None)
        links = beam.setdefault("links", {})
        touched_indices: set[int] = set()

        for seg in segments:
            idx = seg.get("seg_index")
            coord = seg.get("coord")
            if not idx or coord is None:
                continue
            touched_indices.add(idx)
            p_min, p_max = coord
            if p_min is None or p_max is None:
                continue

            if is_horizontal:
                fallback_geom = [
                    [p_min, beam_pos[1] - half_height],
                    [p_max, beam_pos[1] - half_height],
                    [p_max, beam_pos[1] + half_height],
                    [p_min, beam_pos[1] + half_height],
                ]
            else:
                fallback_geom = [
                    [beam_pos[0] - half_height, p_min],
                    [beam_pos[0] + half_height, p_min],
                    [beam_pos[0] + half_height, p_max],
                    [beam_pos[0] - half_height, p_max],
                ]
            seg_geom = seg.get("geometry")
            if isinstance(seg_geom, list) and len(seg_geom) >= 3:
                inferred_geom = [
                    [float(point[0]), float(point[1])]
                    for point in seg_geom
                    if isinstance(point, (list, tuple)) and len(point) >= 2
                ]
                if len(inferred_geom) < 3:
                    inferred_geom = fallback_geom
            else:
                inferred_geom = fallback_geom

            link_key = f"viga_fundo_seg_{idx}_area_segs"
            if link_key not in links:
                links[link_key] = {}

            if geometry_policy is not None:
                policy = geometry_policy(beam, link_key)
                if policy == "ignore":
                    beam[f"viga_fundo_seg_{idx}_exists"] = False
                    links[link_key]["contour"] = []
                    continue

            candidates = [
                link
                for link in (links[link_key].get("contour", []) or [])
                if cls._fv_existing_contour_overlaps_span(
                    link, axis_index, p_min, p_max
                )
            ]
            human_contour = next(
                (link for link in candidates if link.get("validated")), None,
            )
            if human_contour:
                good_contour = human_contour
            else:
                good_contour = next(
                    (
                        link for link in candidates
                        if cls._fv_existing_contour_is_well_formed(link)
                        and cls._fv_existing_contour_matches_canonical_span(
                            link, axis_index, p_min, p_max,
                        )
                    ),
                    None,
                )
                if good_contour and not good_contour.get("validated"):
                    match = cls._fv_automatic_contour_matches_dxf(
                        good_contour, inferred_geom,
                    )
                    if match is not True and inferred_geom:
                        good_contour = None

            if not good_contour:
                new_link: dict[str, Any] = {
                    "points": inferred_geom,
                    "type": "polygon",
                    "tag": "Fundo",
                    "ficha": seg.get("ficha", {}),
                    "len": seg.get("length"),
                }
                if seg.get("provenance"):
                    new_link["fv_provenance"] = dict(seg["provenance"])
                if seg.get("measure_source"):
                    new_link["fv_measure_source"] = seg["measure_source"]
                    new_link["fv_measure_length"] = seg.get("measure_length")
                    if seg.get("measure_width") is not None:
                        new_link["fv_measure_width"] = seg["measure_width"]
                links[link_key]["contour"] = [new_link]
                emit(f" -> Added {link_key} contour (span canonico) to Beam {beam.get('name')}")
            else:
                ficha = dict(good_contour.get("ficha") or {})
                ficha.update(seg.get("ficha") or {})
                good_contour["ficha"] = ficha
                good_contour["tag"] = good_contour.get("tag") or "Fundo"
                good_contour["len"] = good_contour.get("len") or seg.get("length")
                if seg.get("provenance") and not good_contour.get("validated"):
                    good_contour["fv_provenance"] = dict(seg["provenance"])
                links[link_key]["contour"] = [good_contour]
                emit(f" -> Kept existing {link_key} contour for Beam {beam.get('name')}")

            field_prefix = f"viga_fundo_seg_{idx}"
            fields = beam.setdefault("fields", {})
            if seg.get("dim_text"):
                fields[f"{field_prefix}_dim"] = seg.get("dim_text")
                if seg.get("dim_link"):
                    links[f"{field_prefix}_dim"] = {"label": [seg.get("dim_link")]}
            if seg.get("apoio_inicial"):
                fields[f"{field_prefix}_local_ini"] = seg.get("apoio_inicial")
                if seg.get("apoio_inicial_link"):
                    local_ini = dict(seg.get("apoio_inicial_link"))
                    local_ini.update({
                        "evidence_role": "fv_segment_local_support",
                        "scope": "segment_local",
                        "source_segment": idx,
                        "source_slot": "seg_bottom",
                    })
                    links[f"{field_prefix}_local_ini"] = {"label": [local_ini]}
            if seg.get("apoio_final"):
                fields[f"{field_prefix}_local_fim"] = seg.get("apoio_final")
                if seg.get("apoio_final_link"):
                    local_fim = dict(seg.get("apoio_final_link"))
                    local_fim.update({
                        "evidence_role": "fv_segment_local_support",
                        "scope": "segment_local",
                        "source_segment": idx,
                        "source_slot": "seg_bottom",
                    })
                    links[f"{field_prefix}_local_fim"] = {"label": [local_fim]}

        # Quando a contagem de segmentos frescos diminui em relação ao que
        # já está persistido (achado real V331, 2026-07-20: o fix do
        # fragmento residual de V310/V331 reduziu 2 vãos físicos para 1),
        # o loop acima só toca os índices que existem NA rodada atual —
        # índices excedentes ficam órfãos no DB e voltam a aparecer como
        # segmento fantasma duplicado na ficha final. Um órfão só pode ser
        # limpo quando NENHUM contorno seu tem `validated=True` (dado
        # humano nunca é apagado silenciosamente, mesmo órfão).
        orphan_pattern = re.compile(r"^viga_fundo_seg_(\d+)_area_segs$")
        for existing_key in list(links.keys()):
            match = orphan_pattern.match(existing_key)
            if not match:
                continue
            existing_idx = int(match.group(1))
            if existing_idx in touched_indices:
                continue
            contours = links[existing_key].get("contour") or []
            if any(contour.get("validated") for contour in contours):
                continue
            beam[f"viga_fundo_seg_{existing_idx}_exists"] = False
            links[existing_key]["contour"] = []
            emit(
                f" -> Cleared orphaned {existing_key} contour "
                f"(sem correspondência na rodada atual) for Beam {beam.get('name')}"
            )

    @staticmethod
    def _normalize(intervals: Iterable[Interval]) -> list[Interval]:
        normalized: list[Interval] = []
        for start, end in intervals:
            start_f, end_f = sorted((float(start), float(end)))
            if end_f - start_f > 0.01:
                normalized.append((start_f, end_f))
        return sorted(normalized)

    def _equivalent(self, first: Interval, second: Interval) -> bool:
        tol = self.equivalence_tolerance
        return (
            abs(first[0] - second[0]) <= tol
            and abs(first[1] - second[1]) <= tol
        )

    def deduplicate(self, intervals: Iterable[Interval]) -> list[Interval]:
        """Remove duplicatas de captura sem unir paineis vizinhos."""
        unique: list[Interval] = []
        for interval in self._normalize(intervals):
            match_index = next(
                (index for index, current in enumerate(unique)
                 if self._equivalent(current, interval)),
                None,
            )
            if match_index is None:
                unique.append(interval)
                continue
            current = unique[match_index]
            unique[match_index] = (
                min(current[0], interval[0]),
                max(current[1], interval[1]),
            )
        return sorted(unique)

    def discard_enclosing_fallbacks(
        self, intervals: Iterable[Interval]
    ) -> list[Interval]:
        """Descarta faixa generica que engloba varios paineis concretos."""
        items = self.deduplicate(intervals)
        if len(items) < 3:
            return items
        tol = self.equivalence_tolerance
        result: list[Interval] = []
        for index, candidate in enumerate(items):
            contained = [
                other
                for other_index, other in enumerate(items)
                if other_index != index
                and candidate[0] <= other[0] + tol
                and candidate[1] >= other[1] - tol
                and not self._equivalent(candidate, other)
            ]
            if len(contained) >= 2:
                continue
            result.append(candidate)
        return result

    def panel_groups(
        self,
        items: Iterable[Any],
        axis_min: AxisFn,
        axis_max: AxisFn,
        *,
        split_support_gaps: bool = False,
    ) -> list[Interval]:
        """Compatibilidade conservadora para os paineis atuais.

        O tipo do encontro ainda nao faz parte do contrato de topologia. Ate
        ele existir, gaps curtos continuam unidos para nao transformar
        cruzamentos atravessados em fronteiras FV.

        Quando o caller ja filtrou candidatos como paineis de fundo fisicos
        (`split_support_gaps=True`), um gap curto entre dois paineis longos
        representa apoio/obstaculo interno, nao continuidade. Esse caso precisa
        permanecer segmentado (ex.: FV com cota multiplicadora 5x).
        """
        intervals = self._normalize(
            (axis_min(item), axis_max(item)) for item in items
        )
        if not intervals:
            return []
        groups: list[Interval] = []
        current_min, current_max = intervals[0]
        for start, end in intervals[1:]:
            gap = start - current_max
            current_length = current_max - current_min
            incoming_length = end - start
            support_gap_between_panels = (
                split_support_gaps
                and 5.0 < gap <= 30.0
                and current_length > 30.0
                and incoming_length > 30.0
            )
            if gap <= 30.0 and not support_gap_between_panels:
                current_max = max(current_max, end)
            else:
                groups.append((current_min, current_max))
                current_min, current_max = start, end
        groups.append((current_min, current_max))
        return groups

    def resolve_attached_support_faces(
        self,
        panels: Iterable[Interval],
        evidence_lines: Iterable[Iterable[tuple[float, float]]],
        *,
        is_horizontal: bool,
        transverse_center: float,
        endpoint_tolerance: float = 0.05,
        max_cap_span: float = 80.0,
        min_face_span: float = 80.0,
    ) -> list[Interval]:
        """Move a extremidade do fundo para a face estrutural do encontro.

        Uma chapa curta fechada pode desenhar o encontro entre duas vigas. A
        borda externa dessa chapa não é necessariamente a fronteira do fundo:
        quando há uma face longa que toca a chapa, a face é a prova física do
        início/fim correto do painel. Sem essa prova a fronteira original é
        preservada. Isso mantém pilares sólidos e cruzamentos visuais fora da
        semântica FV e não depende de N2/N4.

        No terminal, quando a chapa curta invade o próprio painel e não há
        face longa adicional, sua face oposta também é utilizável. Uma chapa
        apenas no vão entre dois painéis não satisfaz essa condição e nunca é
        atravessada.
        """
        normalized = self._normalize(panels)
        if not normalized:
            return []

        axis = 0 if is_horizontal else 1
        transverse = 1 - axis
        raw_lines: list[list[tuple[float, float]]] = []
        for raw in evidence_lines:
            clean: list[tuple[float, float]] = []
            for point in raw or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) >= 2:
                raw_lines.append(clean)

        caps: list[tuple[float, float, float, float]] = []
        faces: list[tuple[float, float, float]] = []
        for line in raw_lines:
            axis_values = [point[axis] for point in line]
            transverse_values = [point[transverse] for point in line]
            axis_min, axis_max = min(axis_values), max(axis_values)
            transverse_min, transverse_max = min(transverse_values), max(transverse_values)
            axis_span = axis_max - axis_min
            transverse_span = transverse_max - transverse_min
            closed = len(line) >= 4 and math.hypot(
                line[0][0] - line[-1][0], line[0][1] - line[-1][1]
            ) <= endpoint_tolerance
            if (
                closed
                and 5.0 <= axis_span <= max_cap_span
                and transverse_span >= 5.0
                and transverse_min - endpoint_tolerance <= transverse_center <= transverse_max + endpoint_tolerance
            ):
                caps.append((axis_min, axis_max, transverse_min, transverse_max))
            if axis_span <= endpoint_tolerance and transverse_span >= min_face_span:
                faces.append((axis_min, transverse_min, transverse_max))

        if not caps:
            return normalized

        adjusted: list[Interval] = []
        for start, end in normalized:
            resolved = [start, end]
            for endpoint_index, endpoint in enumerate((start, end)):
                candidates: list[float] = []
                for cap_min, cap_max, cap_trans_min, cap_trans_max in caps:
                    if min(abs(endpoint - cap_min), abs(endpoint - cap_max)) > endpoint_tolerance:
                        continue
                    # Uma face precisa tocar uma das bordas transversais da
                    # chapa: uma linha distante só na mesma projeção não prova
                    # o encontro.
                    #
                    # A face que fecha a PRÓPRIA chapa fica exatamente na
                    # borda do cap (face_axis == cap_min ou cap_max), não
                    # estritamente dentro — achado real V309A (2026-07-20):
                    # a desigualdade estrita excluía essa face genuína e
                    # sobrava só uma face mais distante (de outra viga,
                    # compartilhando a mesma linha de grade) estritamente
                    # dentro do vão, movendo a fronteira para o lugar
                    # errado. O desempate abaixo (mais perto do limite
                    # atual) já preferiria a face correta quando ela
                    # participa da disputa — só precisava deixar de
                    # descartá-la antes.
                    for face_axis, face_trans_min, face_trans_max in faces:
                        if not (
                            cap_min - endpoint_tolerance
                            <= face_axis
                            <= cap_max + endpoint_tolerance
                        ):
                            continue
                        touches_cap = (
                            abs(face_trans_min - cap_trans_min) <= endpoint_tolerance
                            or abs(face_trans_min - cap_trans_max) <= endpoint_tolerance
                            or abs(face_trans_max - cap_trans_min) <= endpoint_tolerance
                            or abs(face_trans_max - cap_trans_max) <= endpoint_tolerance
                        )
                        if touches_cap:
                            candidates.append(face_axis)
                    if candidates:
                        continue

                    # Sem face longa, somente recua/avança quando a chapa já
                    # ocupa materialmente o interior do mesmo painel. Isso não
                    # converte o vão livre entre dois painéis em uma invasão.
                    #
                    # TENTATIVA 2026-07-21 (achado V320) — remover este
                    # fallback por completo consertava V320 (pilar que a
                    # viga atravessa, corte indevido de 19cm) mas quebrava o
                    # cap TERMINAL genuíno do V301
                    # (`test_fv_uses_proven_inner_support_faces_not_outer_cap_edges`,
                    # painel final 4259→4552 deve virar 4244→4533: ali o
                    # pilar É o apoio real, a viga termina). Revertido:
                    # distinguir os dois casos exige saber se o pilar é
                    # SEGUE (viga atravessa, não deveria cortar) ou
                    # NASCE/apoio real (viga termina, deveria cortar) — essa
                    # classificação não chega até esta função hoje. Fica
                    # documentado para quando a plumbing SEGUE/NASCE puder
                    # ser passada até aqui com segurança.
                    if endpoint_index == 0 and abs(endpoint - cap_min) <= endpoint_tolerance and cap_max < end - 5.0:
                        candidates.append(cap_max)
                    elif endpoint_index == 1 and abs(endpoint - cap_max) <= endpoint_tolerance and cap_min > start + 5.0:
                        candidates.append(cap_min)
                if candidates:
                    resolved[endpoint_index] = min(candidates, key=lambda value: abs(value - endpoint))
            resolved_start, resolved_end = sorted(resolved)
            if resolved_end - resolved_start > 0.01:
                adjusted.append((resolved_start, resolved_end))
            else:
                adjusted.append((start, end))
        return adjusted

    def atomic_panel_groups(
        self,
        items: Iterable[Any],
        axis_min: AxisFn,
        axis_max: AxisFn,
    ) -> list[Interval]:
        """Candidatos atomicos, usados somente apos classificar o encontro."""
        return self.deduplicate(
            (axis_min(item), axis_max(item)) for item in items
        )

    def consolidate_occurrences(
        self, occurrence_groups: Iterable[Iterable[Interval]]
    ) -> list[Interval]:
        intervals = self._normalize(
            interval
            for groups in occurrence_groups
            for interval in groups
        )
        if not intervals:
            return []
        merged: list[Interval] = []
        current_min, current_max = intervals[0]
        for start, end in intervals[1:]:
            current_narrow = current_max - current_min < 30.0
            incoming_narrow = end - start < 30.0
            if start <= current_max - 5.0:
                current_max = max(current_max, end)
            elif (
                current_narrow
                and incoming_narrow
                and start - current_max <= 30.0
            ):
                current_max = max(current_max, end)
            else:
                merged.append((current_min, current_max))
                current_min, current_max = start, end
        merged.append((current_min, current_max))
        return merged

    @staticmethod
    def _opening_width_match(
        length: float,
        structural_width: float | None,
        *,
        max_cap: float,
    ) -> bool:
        if structural_width is None or structural_width <= 0.05:
            return False
        if length > float(max_cap):
            return False
        tolerance = max(2.0, structural_width * 0.12)
        return abs(length - structural_width) <= tolerance

    def discard_attached_narrow_caps(
        self,
        intervals: Iterable[Interval],
        *,
        max_cap: float = 30.0,
        protected_boundaries: Iterable[float] = (),
        structural_width: float | None = None,
    ) -> list[Interval]:
        """Descarta tampa transversal curta colada a um painel longo.

        A borda de encontro de outra viga pode aparecer como uma faixa axial
        da própria largura estrutural (19 cm). Não é área de fundo: o painel
        útil começa após essa tampa. Uma faixa curta isolada é preservada; ela
        só é descartada quando toca diretamente um painel bem mais longo.
        Uma fronteira de divisor geométrico transversal real protege o
        intervalo adjacente: nesse caso a faixa estreita é painel, não tampa.
        O chamador deve provar a fronteira no DXF; N2/N4 nunca participam.

        Quando ``structural_width`` é informado, faixas terminais com comprimento
        ≈ largura da viga são tratadas como recorte/furo (família Δ19 cm): a faixa
        inicial é absorvida no painel vizinho e a faixa final encurta o painel.
        """
        source = self.deduplicate(intervals)
        if len(source) < 2:
            return source
        protected = [float(value) for value in protected_boundaries]

        result: list[Interval] = []
        consumed: set[int] = set()
        for index, candidate in enumerate(source):
            if index in consumed:
                continue
            start, end = candidate
            length = end - start
            attached_to_long_panel = any(
                other_index != index
                and (other_end - other_start) > float(max_cap)
                and (
                    abs(end - other_start) <= 0.05
                    or abs(start - other_end) <= 0.05
                )
                for other_index, (other_start, other_end) in enumerate(source)
            )
            touches_proven_boundary = any(
                abs(boundary - start) <= 0.05
                or abs(boundary - end) <= 0.05
                for boundary in protected
            )
            if (
                length <= float(max_cap)
                and attached_to_long_panel
                and not touches_proven_boundary
            ):
                if self._opening_width_match(
                    length, structural_width, max_cap=max_cap
                ):
                    for other_index, (other_start, other_end) in enumerate(source):
                        if other_index == index or other_index in consumed:
                            continue
                        if (other_end - other_start) <= float(max_cap):
                            continue
                        if index == 0 and abs(end - other_start) <= 0.05:
                            result.append((start, other_end))
                            consumed.add(other_index)
                            break
                        if index == len(source) - 1 and result:
                            panel_start, panel_end = result[-1]
                            if abs(start - panel_end) <= 0.05:
                                break
                            if (
                                panel_end > start + 0.05
                                and abs(end - panel_end) <= 0.05
                            ):
                                result[-1] = (panel_start, start)
                                break
                    else:
                        continue
                else:
                    continue
                continue
            result.append(candidate)

        if (
            len(result) >= 2
            and structural_width
            and self._opening_width_match(
                result[-1][1] - result[-1][0],
                structural_width,
                max_cap=max_cap,
            )
        ):
            panel_start, panel_end = result[-2]
            cap_start, cap_end = result[-1]
            if (
                (panel_end - panel_start) > float(max_cap)
                and panel_end > cap_start + 0.05
                and abs(cap_end - panel_end) <= 0.05
                and not any(
                    abs(boundary - cap_start) <= 0.05
                    or abs(boundary - cap_end) <= 0.05
                    for boundary in protected
                )
            ):
                result = [*result[:-2], (panel_start, cap_start)]

        return result or source

    def merge_unlabeled_short_gaps(
        self,
        intervals: Iterable[Interval],
        *,
        is_horizontal: bool,
        transverse_center: float,
        texts: Iterable[dict[str, Any]],
        current_name: str = "",
        max_gap: float = 30.0,
    ) -> list[Interval]:
        """Une lacunas curtas sem evidência local de apoio estrutural.

        Um vão curto é ambíguo: em V306 coincide com rótulos estruturais e
        separa painéis; em V312 não há apoio na fronteira e o fundo continua.
        A decisão usa a evidência do desenho, nunca o nome do item.
        """
        source = self.deduplicate(intervals)
        if len(source) < 2:
            return source
        # Dois ou três trechos descrevem tipicamente um único encontro local
        # ambíguo. Em uma viga com muitos painéis, a ausência pontual de texto
        # não autoriza atravessar fronteiras: preservar a segmentação é mais
        # seguro do que colapsar uma cadeia contínua.
        if len(source) > 3:
            return source

        current = str(current_name or "").strip().upper()
        structural_label = re.compile(r"^(?:P|V)\d+[A-Z]*$")

        def has_boundary_label(axis_center: float, gap: float) -> bool:
            axis_tolerance = max(15.0, gap / 2.0 + 10.0)
            for text_data in texts or []:
                if not isinstance(text_data, dict):
                    continue
                label = str(text_data.get("text") or "").strip().upper()
                if not structural_label.fullmatch(label) or label == current:
                    continue
                pos = text_data.get("pos")
                if not isinstance(pos, (tuple, list)) or len(pos) < 2:
                    continue
                try:
                    axis = float(pos[0] if is_horizontal else pos[1])
                    transverse = float(pos[1] if is_horizontal else pos[0])
                except (TypeError, ValueError):
                    continue
                if (
                    abs(axis - axis_center) <= axis_tolerance
                    and abs(transverse - float(transverse_center)) <= 80.0
                ):
                    return True
            return False

        merged: list[Interval] = []
        current_min, current_max = source[0]
        for start, end in source[1:]:
            gap = start - current_max
            if (
                0.05 < gap <= float(max_gap)
                and not has_boundary_label((current_max + start) / 2.0, gap)
            ):
                current_max = max(current_max, end)
            else:
                merged.append((current_min, current_max))
                current_min, current_max = start, end
        merged.append((current_min, current_max))
        return merged

    def atomic_occurrences(
        self, occurrence_groups: Iterable[Iterable[Interval]]
    ) -> list[Interval]:
        all_intervals = [
            interval
            for groups in occurrence_groups
            for interval in groups
        ]
        return self.discard_enclosing_fallbacks(all_intervals)

    @staticmethod
    def lengths(intervals: Iterable[Interval], minimum: float = 10.0) -> list[float]:
        return [
            end - start
            for start, end in intervals
            if end - start > minimum
        ]
