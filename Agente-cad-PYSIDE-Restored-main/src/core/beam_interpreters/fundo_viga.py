"""Interpretacao exclusiva dos segmentos de fundo de viga (FV)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
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
    def build_area_contour(
        cls,
        *,
        axial_span: Interval,
        width: float,
        is_horizontal: bool,
        transverse_center: float,
        boundary_lines: Iterable[Iterable[Any]] = (),
    ) -> list[tuple[float, float]]:
        """Produz área FV fechada; linha colinear nunca vira contorno."""
        start, end = sorted((float(axial_span[0]), float(axial_span[1])))
        width = abs(float(width))
        center = float(transverse_center)
        if end - start <= 0.01 or width <= 0.01:
            return []

        clean_lines: list[list[tuple[float, float]]] = []
        for line in boundary_lines:
            clean = []
            for point in line or []:
                try:
                    clean.append((float(point[0]), float(point[1])))
                except (TypeError, ValueError, IndexError):
                    continue
            if len(clean) >= 2:
                clean_lines.append(clean)

        def transverse(line: list[tuple[float, float]]) -> float:
            axis = 1 if is_horizontal else 0
            return sum(point[axis] for point in line) / len(line)

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
            if (
                width_plausible
                and cls._polygon_area(candidate) > 0.05
            ):
                if candidate[0] != candidate[-1]:
                    candidate.append(candidate[0])
                return candidate

        half = width / 2.0
        if is_horizontal:
            rectangle = [
                (start, center - half), (end, center - half),
                (end, center + half), (start, center + half),
            ]
        else:
            rectangle = [
                (center - half, start), (center + half, start),
                (center + half, end), (center - half, end),
            ]
        return rectangle + [rectangle[0]]

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
                "len",
                "closed",
                "geometry_role",
                "geometry_source",
            ):
                if key in link:
                    existing[key] = link[key]

        def normalize_area_link(link: dict, points: list[tuple[float, float]], source: str) -> None:
            length, width = cls._bbox_dimensions(points)
            link["points"] = points
            link["type"] = "poly"
            link["closed"] = True
            link["geometry_role"] = "area_fundo"
            link["geometry_source"] = source
            if length > 0.01:
                link["len"] = length
                ficha = dict(link.get("ficha") or {})
                ficha["comprimento_total_fundo"] = cls._format_measure(length)
                if width > 0.05:
                    ficha["largura_total_fundo"] = cls._format_measure(width)
                link["ficha"] = ficha

        def normalize_special_diagonal_link(
            link: dict,
            points: list[tuple[float, float]],
            source: str,
            structural_width: float,
        ) -> None:
            normalize_area_link(link, points, source)
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
                        area_points = cls.build_area_contour(
                            axial_span=span,
                            width=width,
                            is_horizontal=is_horizontal,
                            transverse_center=center,
                            boundary_lines=(),
                        )
                        if area_points and points != area_points:
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_width_repair",
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
                        area_points = cls.build_area_contour(
                            axial_span=(span_min, span_max),
                            width=width,
                            is_horizontal=is_horizontal,
                            transverse_center=center,
                            boundary_lines=(),
                        )
                        if area_points and points != area_points:
                            repaired += 1
                            normalize_area_link(
                                link,
                                area_points,
                                "fundo_viga_interpreter_run_span_repair",
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

            matching_lines = []
            span_min, span_max = sorted(span)
            for line in raw_lines:
                clean = [
                    (float(point[0]), float(point[1]))
                    for point in line or []
                    if isinstance(point, (list, tuple)) and len(point) >= 2
                ]
                if len(clean) < 2:
                    continue
                line_min = min(point[axis] for point in clean)
                line_max = max(point[axis] for point in clean)
                if min(line_max, span_max) - max(line_min, span_min) > 0.0:
                    matching_lines.append(clean)

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
                area_points = cls.build_area_contour(
                    axial_span=span,
                    width=width,
                    is_horizontal=is_horizontal,
                    transverse_center=center,
                    boundary_lines=matching_lines,
                )
            if not area_points:
                continue
            if points != area_points:
                repaired += 1
            normalize_area_link(link, area_points, "fundo_viga_interpreter")
            slots["contour"] = [link]
            sync_bottom_segment(index, link)
        return repaired

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
