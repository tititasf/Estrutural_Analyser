"""ChannelConfidenceScorer: Mapeamento de sinais de confiança e coincidência espacial entre vínculos de fundo e canais físicos DXF."""

from dataclasses import dataclass
from typing import Sequence
from src.core.beam_interpreters.global_channel_extractor import (
    BeamChannelSlot,
    GlobalBeamChannelMesh,
)


@dataclass(frozen=True)
class ChannelConfidenceResult:
    """Resultado da avaliação de coincidência entre um segmento de fundo e a malha de canais do DXF."""

    confidence_score: float  # 0.0 (sem suporte) a 1.0 (coincidência perfeita)
    matched_slot_id: str | None
    axial_overlap_ratio: float  # 0.0 a 1.0 (proporção do comprimento coberto pelo canal)
    transverse_offset_cm: float  # Deslocamento em relação ao eixo do canal
    width_delta_cm: float  # Diferença entre a largura da viga e do canal
    dim_text_matched: str | None
    status_flag: str  # 'HIGH_CONFIDENCE', 'WARNING_OFFSET', 'WARNING_WIDTH', 'UNSUPPORTED'


class ChannelConfidenceScorer:
    """Calculador determinístico de score de coincidência para validação agentica e depuração."""

    def __init__(self, max_transverse_dist_cm: float = 60.0) -> None:
        self.max_transverse_dist_cm = float(max_transverse_dist_cm)

    def score_segment(
        self,
        segment_bbox: tuple[float, float, float, float],
        beam_width: float,
        is_horizontal: bool,
        channel_mesh: GlobalBeamChannelMesh,
    ) -> ChannelConfidenceResult:
        """Calcula o score de coincidência espacial de um segmento de fundo contra os canais do DXF."""
        if not channel_mesh or not channel_mesh.slots:
            return ChannelConfidenceResult(
                confidence_score=0.0,
                matched_slot_id=None,
                axial_overlap_ratio=0.0,
                transverse_offset_cm=0.0,
                width_delta_cm=0.0,
                dim_text_matched=None,
                status_flag="UNSUPPORTED",
            )

        x1, y1, x2, y2 = segment_bbox
        seg_len = max(x2 - x1, 0.1) if is_horizontal else max(y2 - y1, 0.1)
        seg_span = (x1, x2) if is_horizontal else (y1, y2)
        seg_transverse = (y1 + y2) / 2.0 if is_horizontal else (x1 + x2) / 2.0

        best_slot: BeamChannelSlot | None = None
        best_score = -1.0
        best_overlap = 0.0
        best_offset = 0.0
        best_w_delta = 0.0

        for slot in channel_mesh.slots:
            if slot.is_horizontal != is_horizontal:
                continue

            # Verificação de distância transversal
            t_offset = abs(slot.transverse_pos - seg_transverse)
            if t_offset > self.max_transverse_dist_cm:
                continue

            # Verificação de sobreposição axial
            s_min = max(seg_span[0], slot.axial_span[0])
            s_max = min(seg_span[1], slot.axial_span[1])
            overlap_len = max(0.0, s_max - s_min)
            overlap_ratio = overlap_len / seg_len

            if overlap_ratio < 0.1:
                continue

            w_delta = abs(beam_width - slot.width)

            # Cálculo da pontuação heurística (0.0 a 1.0)
            score = (overlap_ratio * 0.70) - (t_offset * 0.015) - (w_delta * 0.02)
            slot_dim_text = getattr(slot, 'dim_text', None)
            if slot_dim_text:
                score += 0.10  # Bônus para canal com cota pareada

            score = max(0.0, min(1.0, score))

            if score > best_score:
                best_score = score
                best_slot = slot
                best_overlap = overlap_ratio
                best_offset = t_offset
                best_w_delta = w_delta

        if not best_slot or best_score < 0.20:
            return ChannelConfidenceResult(
                confidence_score=0.0,
                matched_slot_id=None,
                axial_overlap_ratio=0.0,
                transverse_offset_cm=0.0,
                width_delta_cm=0.0,
                dim_text_matched=None,
                status_flag="UNSUPPORTED",
            )

        # Determinar flag de status
        if best_offset > 5.0:
            flag = "WARNING_OFFSET"
        elif best_w_delta > 1.5:
            flag = "WARNING_WIDTH"
        elif best_score >= 0.75:
            flag = "HIGH_CONFIDENCE"
        else:
            flag = "MODERATE_CONFIDENCE"

        return ChannelConfidenceResult(
            confidence_score=round(best_score, 3),
            matched_slot_id=best_slot.slot_id,
            axial_overlap_ratio=round(best_overlap, 3),
            transverse_offset_cm=round(best_offset, 2),
            width_delta_cm=round(best_w_delta, 2),
            dim_text_matched=getattr(best_slot, "dim_text", None),
            status_flag=flag,
        )
