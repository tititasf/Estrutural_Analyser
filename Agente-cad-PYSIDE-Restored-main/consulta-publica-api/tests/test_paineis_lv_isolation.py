"""Verificação estática — o serviço de painéis LV nunca importa o motor
PySide6/`lv_generation_contract.py` (STORY-12, AC3 / architecture.md §8).
"""

from __future__ import annotations

import re
from pathlib import Path

_ARQUIVOS_ALVO = [
    Path(__file__).resolve().parent.parent / "services" / "paineis_lv_service.py",
    Path(__file__).resolve().parent.parent / "routers" / "paineis_lv_routes.py",
]

_IMPORTS_PROIBIDOS = ("lv_generation_contract", "PySide6", "PyQt", "src.core", "src.ui")
_LINHA_IMPORT_RE = re.compile(r"^\s*(import|from)\s+", re.MULTILINE)


def test_servico_paineis_lv_nao_importa_motor_pyside6():
    """Escaneia só LINHAS DE IMPORT reais (`import ...`/`from ...`) — não o
    texto de docstrings/comentários, que legitimamente MENCIONAM esses nomes
    para explicar por que não são importados."""
    for arquivo in _ARQUIVOS_ALVO:
        linhas_import = [
            linha for linha in arquivo.read_text(encoding="utf-8").splitlines()
            if _LINHA_IMPORT_RE.match(linha)
        ]
        for linha in linhas_import:
            for proibido in _IMPORTS_PROIBIDOS:
                assert proibido not in linha, f"{arquivo.name}: import proibido -> {linha!r}"
