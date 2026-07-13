"""Worker de background pra buscar o código público (App de Consulta) de
uma obra/pavimento Drive [2026-07-13] — mesmo idioma de `dxf_worker.py`
(QObject + QThread via `moveToThread`), nunca roda na thread de UI. Erros
(portal offline, obra ainda não publicada, etc) viram sinal `error`, nunca
exceção — o chamador trata como "código ainda não disponível", não como
falha da app.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QObject, Signal, Slot


class CodePublicoWorker(QObject):
    finished = Signal(object, object)  # (code: str | None, referencia: str | None)
    error = Signal(str)

    def __init__(self, obra_id: str, pavimento: Optional[str] = None):
        super().__init__()
        self.obra_id = obra_id
        self.pavimento = pavimento

    @Slot()
    def run(self) -> None:
        try:
            from src.core.drive_client import obter_cliente_padrao
            cliente = obter_cliente_padrao()
            if self.pavimento:
                code, referencia = cliente.obter_code_publico_pavimento(self.obra_id, self.pavimento)
            else:
                code, referencia = cliente.obter_code_publico_obra(self.obra_id)
            self.finished.emit(code, referencia)
        except Exception as e:
            self.error.emit(str(e))
