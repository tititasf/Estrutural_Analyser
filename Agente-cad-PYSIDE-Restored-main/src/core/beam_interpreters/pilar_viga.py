"""Contratos isolados para relacoes pilar-viga."""

from __future__ import annotations

from collections.abc import Sequence

from .contracts import InterpreterContract, InterpreterKind


class _PilarComVigaInterpreter:
    contract: InterpreterContract

    @staticmethod
    def _axis_ranges(
        pillar_bbox: Sequence[float],
        beam_bbox: Sequence[float],
        is_horizontal: bool,
    ) -> tuple[float, float, float, float]:
        axis = (0, 2) if is_horizontal else (1, 3)
        return (
            float(pillar_bbox[axis[0]]),
            float(pillar_bbox[axis[1]]),
            float(beam_bbox[axis[0]]),
            float(beam_bbox[axis[1]]),
        )

    @staticmethod
    def _crosses_transverse_axis(
        pillar_bbox: Sequence[float],
        beam_bbox: Sequence[float],
        is_horizontal: bool,
        tolerance: float,
    ) -> bool:
        axis = (1, 3) if is_horizontal else (0, 2)
        pillar_min, pillar_max = (
            float(pillar_bbox[axis[0]]),
            float(pillar_bbox[axis[1]]),
        )
        beam_min, beam_max = (
            float(beam_bbox[axis[0]]),
            float(beam_bbox[axis[1]]),
        )
        return (
            min(pillar_max, beam_max) - max(pillar_min, beam_min)
            >= -tolerance
        )


class PilarComVigaParaInterpreter(_PilarComVigaInterpreter):
    """Viga cujo eixo termina no volume do pilar."""

    contract = InterpreterContract(
        InterpreterKind.PILAR_COM_VIGA_PARA,
        owner="PIL",
        behavior="para",
        output_slot="viga_que_para",
    )

    def matches(
        self,
        pillar_bbox: Sequence[float],
        beam_bbox: Sequence[float],
        is_horizontal: bool,
        tolerance: float = 4.0,
    ) -> bool:
        if not self._crosses_transverse_axis(
            pillar_bbox, beam_bbox, is_horizontal, tolerance
        ):
            return False
        pillar_min, pillar_max, beam_min, beam_max = self._axis_ranges(
            pillar_bbox, beam_bbox, is_horizontal
        )
        passes_left = beam_min < pillar_min - tolerance
        passes_right = beam_max > pillar_max + tolerance
        endpoint_at_pillar = (
            pillar_min - tolerance <= beam_min <= pillar_max + tolerance
            or pillar_min - tolerance <= beam_max <= pillar_max + tolerance
        )
        return endpoint_at_pillar and passes_left != passes_right


class PilarComVigaPassaInterpreter(_PilarComVigaInterpreter):
    """Viga cujo eixo continua alem das duas faces do pilar."""

    contract = InterpreterContract(
        InterpreterKind.PILAR_COM_VIGA_PASSA,
        owner="PIL",
        behavior="passa",
        output_slot="viga_que_passa",
    )

    def matches(
        self,
        pillar_bbox: Sequence[float],
        beam_bbox: Sequence[float],
        is_horizontal: bool,
        tolerance: float = 4.0,
    ) -> bool:
        if not self._crosses_transverse_axis(
            pillar_bbox, beam_bbox, is_horizontal, tolerance
        ):
            return False
        pillar_min, pillar_max, beam_min, beam_max = self._axis_ranges(
            pillar_bbox, beam_bbox, is_horizontal
        )
        return (
            beam_min < pillar_min - tolerance
            and beam_max > pillar_max + tolerance
        )
