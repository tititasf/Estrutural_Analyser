"""Contratos dos interpretadores estruturais derivados da topologia de vigas.

O detector de topologia e compartilhado. Cada interpretador possui uma chave
exclusiva e so pode produzir dados para o seu proprio fluxo.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class InterpreterKind(str, Enum):
    FUNDO_VIGA = "fundo_viga"
    LATERAL_VIGA_A_PARA = "lateral_viga_a_para"
    LATERAL_VIGA_B_PARA = "lateral_viga_b_para"
    LATERAL_VIGA_A_PASSA = "lateral_viga_a_passa"
    LATERAL_VIGA_B_PASSA = "lateral_viga_b_passa"
    PILAR_COM_VIGA_PARA = "pilar_com_viga_para"
    PILAR_COM_VIGA_PASSA = "pilar_com_viga_passa"


@dataclass(frozen=True)
class InterpreterContract:
    kind: InterpreterKind
    owner: str
    side: str | None = None
    behavior: str | None = None
    output_slot: str | None = None


class StructuralInterpreter(Protocol):
    contract: InterpreterContract

