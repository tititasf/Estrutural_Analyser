"""Regressão da distribuição inteira compartilhada por CIMA e GRADES."""

from __future__ import annotations

import math
import itertools
import time
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gerar_pl_dxf_stog as generator  # noqa: E402


def _fractional_count(values: list[float]) -> int:
    return sum(not math.isclose(value, round(value), abs_tol=1e-6) for value in values)


def _boundaries(segments: list[float]) -> list[float]:
    result = []
    cumulative = 0.0
    for segment in segments[:-1]:
        cumulative += segment
        result.append(cumulative)
    return result


def test_p1_integer_distribution_avoids_central_bolt():
    pj = {"grade_1_div_a": [19.5, 19.5, 24.5, 24.5]}

    segments = generator._div_segments(
        pj, 88.0, bolt_offsets=[44.0],
    )

    # Regra atual: menor quantidade de quadrados com vao <= 31 cm.
    assert segments == [29.0, 29.0, 30.0]
    assert sum(segments) == 88.0
    assert all(abs(boundary - 44.0) > 3.0 for boundary in _boundaries(segments))
    assert _fractional_count(segments) == 0


def test_fractional_single_grade_has_only_one_fractional_gap():
    segments = generator._integer_segments_with_avoidance(
        88.5, offsets=[44.0],
    )

    assert math.isclose(sum(segments), 88.5, abs_tol=1e-6)
    assert _fractional_count(segments) == 1
    assert all(abs(boundary - 44.0) > 3.0 for boundary in _boundaries(segments))


def test_fraction_moves_to_gap_when_there_are_two_grades():
    ng, grade_width, gaps = generator._grade_layout_from_inner(104.5)

    assert ng == 2
    assert math.isclose(grade_width, round(grade_width), abs_tol=1e-6)
    assert gaps == [6.5]
    assert math.isclose(ng * grade_width + sum(gaps), 126.5, abs_tol=1e-6)
    divisions = generator._grade_divisions({}, 126.5, ng, grade_width, gaps)
    assert all(_fractional_count(values) == 0 for values in divisions)


def test_three_grades_concentrate_fraction_in_only_one_intergrade_gap():
    ng, grade_width, gaps = generator._grade_layout_from_inner(260.5)

    assert ng == 3
    assert math.isclose(grade_width, round(grade_width), abs_tol=1e-6)
    assert _fractional_count(gaps) == 1
    assert math.isclose(ng * grade_width + sum(gaps), 282.5, abs_tol=1e-6)
    divisions = generator._grade_divisions({}, 282.5, ng, grade_width, gaps)
    assert all(_fractional_count(values) == 0 for values in divisions)


def test_integer_total_never_creates_fraction_without_collision():
    segments = generator._integer_segments_with_avoidance(102.0, offsets=[])

    assert math.isclose(sum(segments), 102.0, abs_tol=1e-6)
    assert _fractional_count(segments) == 0


def test_grade_larga_oito_vaos_termina_sem_explosao_combinatoria():
    start = time.monotonic()
    segments = generator._integer_segments_with_avoidance(227.0, offsets=[44.0, 89.0])
    assert time.monotonic() - start < 3.0
    assert len(segments) == 8
    assert sum(segments) == 227.0
    assert all(abs(boundary - bolt) > 3.0
               for boundary in _boundaries(segments) for bolt in (44.0, 89.0))


def test_solver_cinco_vaos_mantem_a_escolha_exaustiva():
    total, offsets, preferred = 130.0, [35.0, 70.0], [24.0, 25.0, 26.0, 27.0, 28.0]
    options = []
    for prefix in itertools.product(range(24, 29), repeat=4):
        last = 130 - sum(prefix)
        if not 24 <= last <= 28:
            continue
        values = tuple(map(float, (*prefix, last)))
        collisions = [3.0 - abs(boundary - bolt)
                      for boundary in _boundaries(values) for bolt in offsets
                      if abs(boundary - bolt) <= 3.0]
        options.append(((len(collisions), round(sum(c + 1e-6 for c in collisions), 6),
                         round(sum(abs(a-b) for a, b in zip(values, preferred)), 6),
                         round(sum((value-26.0)**2 for value in values), 6), 0, values), values))
    expected = list(min(options)[1])
    assert generator._integer_segments_with_avoidance(
        total, offsets, preferred=preferred, count=5, max_shift=2.0,
    ) == expected
