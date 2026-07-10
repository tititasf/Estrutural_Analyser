"""Registro fechado dos sete interpretadores estruturais."""

from __future__ import annotations

from .contracts import InterpreterKind, StructuralInterpreter
from .fundo_viga import FundoVigaInterpreter
from .lateral_viga import (
    LateralVigaAPassaInterpreter,
    LateralVigaAParaInterpreter,
    LateralVigaBPassaInterpreter,
    LateralVigaBParaInterpreter,
)
from .pilar_viga import (
    PilarComVigaParaInterpreter,
    PilarComVigaPassaInterpreter,
)


def build_interpreter_registry() -> dict[InterpreterKind, StructuralInterpreter]:
    interpreters = (
        FundoVigaInterpreter(),
        LateralVigaAParaInterpreter(),
        LateralVigaBParaInterpreter(),
        LateralVigaAPassaInterpreter(),
        LateralVigaBPassaInterpreter(),
        PilarComVigaParaInterpreter(),
        PilarComVigaPassaInterpreter(),
    )
    registry = {
        interpreter.contract.kind: interpreter
        for interpreter in interpreters
    }
    if len(registry) != len(InterpreterKind):
        raise RuntimeError("Registro de interpretadores estruturais incompleto")
    return registry

