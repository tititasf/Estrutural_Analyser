"""
src/ui/dialogs/delivery_dialog.py -- CAD-12
Dialog "Entregar Obra" -- async via QProcess, com log ao vivo.

Usage:
    from src.ui.dialogs.delivery_dialog import DeliveryDialog
    DeliveryDialog.open_for_obra(obra_path, parent=self)
"""
import os
import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QProgressBar, QMessageBox, QFrame,
    )
    from PySide6.QtCore import Qt, QProcess, Signal
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

if _QT_AVAILABLE:
    try:
        from src.ui.theme import Colors
    except ImportError:
        class Colors:
            ACCENT_MINT = '#00e5cc'
            SUCCESS = '#4caf50'
            DANGER = '#f44336'
            BG_CARD = '#1a1a2e'
            TEXT_PRIMARY = '#e0e0e0'
            BORDER_DEFAULT = '#333355'


if _QT_AVAILABLE:
    class DeliveryDialog(QDialog):
        """
        Async delivery dialog: DXF generation + ODA DWG conversion.
        Uses a QProcess running a helper script to keep the UI responsive.
        """

        delivery_finished = Signal(dict)

        def __init__(self, obra_path, parent=None):
            super().__init__(parent)
            self.obra_path = Path(obra_path)
            self._process: QProcess | None = None
            self._output_lines: list[str] = []

            self._build_ui()
            self.setMinimumWidth(540)
            self.setMinimumHeight(420)

        def _build_ui(self):
            self.setWindowTitle(f"Entregar Obra -- {self.obra_path.name}")

            layout = QVBoxLayout(self)
            layout.setSpacing(8)

            # Header
            lbl = QLabel(f"Entregar Obra: {self.obra_path.name}")
            lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.ACCENT_MINT};")
            layout.addWidget(lbl)

            out_dir = self.obra_path / 'Fase-6_Execucao_CAD'
            lbl_out = QLabel(f"Saida: {out_dir}")
            lbl_out.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_PRIMARY}; opacity: 0.7;")
            lbl_out.setWordWrap(True)
            layout.addWidget(lbl_out)

            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
            layout.addWidget(sep)

            info = QLabel(
                "Etapas:\n"
                "  1. Gerar DXFs STOG (PL + LV + FV + LJ)\n"
                "  2. Converter para DWG via ODA (se disponivel)\n"
                "  3. Gerar delivery_report.json"
            )
            info.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_PRIMARY};")
            layout.addWidget(info)

            # Progress
            self._progress = QProgressBar()
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._progress.setVisible(False)
            layout.addWidget(self._progress)

            # Log
            self._log = QTextEdit()
            self._log.setReadOnly(True)
            self._log.setMinimumHeight(180)
            self._log.setStyleSheet(
                f"background: #0d0d1a; color: {Colors.TEXT_PRIMARY}; "
                f"font-family: Consolas, monospace; font-size: 10px; "
                f"border: 1px solid {Colors.BORDER_DEFAULT};"
            )
            layout.addWidget(self._log)

            # Buttons
            btn_row = QHBoxLayout()

            self._btn_deliver = QPushButton("Entregar")
            self._btn_deliver.setObjectName("Success")
            self._btn_deliver.setFixedHeight(34)
            self._btn_deliver.setCursor(Qt.PointingHandCursor)
            self._btn_deliver.clicked.connect(self._start_delivery)

            self._btn_open = QPushButton("Abrir Pasta")
            self._btn_open.setFixedHeight(34)
            self._btn_open.setCursor(Qt.PointingHandCursor)
            self._btn_open.setEnabled(False)
            self._btn_open.clicked.connect(self._open_output_folder)

            self._btn_close = QPushButton("Fechar")
            self._btn_close.setFixedHeight(34)
            self._btn_close.setCursor(Qt.PointingHandCursor)
            self._btn_close.clicked.connect(self.accept)

            btn_row.addWidget(self._btn_deliver)
            btn_row.addWidget(self._btn_open)
            btn_row.addStretch()
            btn_row.addWidget(self._btn_close)
            layout.addLayout(btn_row)

        def _start_delivery(self):
            f4 = self.obra_path / 'Fase-4_Sincronizacao'
            if not f4.exists():
                QMessageBox.critical(
                    self, "Erro",
                    f"Fase-4_Sincronizacao nao encontrada em:\n{self.obra_path}\n\n"
                    "Execute 'Analise Geral' primeiro."
                )
                return

            self._btn_deliver.setEnabled(False)
            self._log.clear()
            self._output_lines = []
            self._progress.setValue(0)
            self._progress.setVisible(True)
            self._log_line("Iniciando entrega...\n")

            # Run delivery in a subprocess to keep UI responsive
            script_code = (
                "import sys; sys.path.insert(0, '.');"
                "import json;"
                "from src.core.services.delivery_service import DeliveryService;"
                f"svc = DeliveryService(r'{self.obra_path}');"
                "result = svc.build_delivery();"
                "print('DELIVERY_RESULT:' + json.dumps(result));"
            )

            self._process = QProcess(self)
            self._process.setWorkingDirectory(
                str(Path(__file__).parent.parent.parent.parent)
            )
            self._process.setProcessChannelMode(QProcess.MergedChannels)
            self._process.readyReadStandardOutput.connect(self._on_output)
            self._process.finished.connect(self._on_finished)
            self._process.start(sys.executable, ['-c', script_code])

        def _on_output(self):
            if not self._process:
                return
            raw = bytes(self._process.readAllStandardOutput()).decode('utf-8', 'replace')
            for line in raw.splitlines():
                if not line.strip():
                    continue
                self._output_lines.append(line)

                # Progress heuristics
                upper = line.upper()
                if 'GERANDO' in upper or 'GENERATING' in upper:
                    self._progress.setValue(min(self._progress.value() + 10, 60))
                elif 'ODA' in upper or 'DWG' in upper:
                    self._progress.setValue(min(self._progress.value() + 10, 85))
                elif 'DELIVERY_RESULT:' in line:
                    self._progress.setValue(95)

                if not line.startswith('DELIVERY_RESULT:'):
                    self._log_line(f"  {line}")

        def _on_finished(self, returncode, _status=None):
            self._progress.setValue(100)

            # Parse result from stdout
            result = None
            for line in self._output_lines:
                if line.startswith('DELIVERY_RESULT:'):
                    try:
                        import json
                        result = json.loads(line[len('DELIVERY_RESULT:'):])
                    except Exception:
                        pass

            if returncode != 0 or result is None:
                self._log_error(f"Processo terminou com codigo {returncode}")
                if result is None:
                    self._log_error("Nao foi possivel ler resultado da entrega.")
                self._btn_deliver.setEnabled(True)
                return

            # Show summary
            dxfs = result.get('dxfs_ok', 0)
            dwgs = result.get('dwgs_ok', 0)
            erros = result.get('erros', [])
            tempo = result.get('tempo_ms', 0)

            self._log_line(f"\n=== ENTREGA CONCLUIDA ===")
            self._log_line(f"DXFs gerados: {dxfs}")
            self._log_line(f"DWGs convertidos: {dwgs}")
            self._log_line(f"Tempo: {tempo}ms")
            if erros:
                self._log_line(f"\nErros ({len(erros)}):")
                for e in erros:
                    self._log_error(f"  - {e}")

            self._btn_deliver.setEnabled(True)
            self._btn_open.setEnabled(True)
            self.delivery_finished.emit(result)

        def _log_line(self, text: str):
            self._log.append(text)

        def _log_error(self, text: str):
            self._log.append(f'<span style="color:#f44336;">{text}</span>')  # hardcoded-ok

        def _open_output_folder(self):
            out_dir = self.obra_path / 'Fase-6_Execucao_CAD'
            out_dir.mkdir(parents=True, exist_ok=True)
            os.startfile(str(out_dir))

        @staticmethod
        def open_for_obra(obra_path, parent=None):
            """Convenience: open dialog for obra delivery."""
            dlg = DeliveryDialog(obra_path, parent=parent)
            dlg.exec()

else:
    class DeliveryDialog:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def exec(self): pass

        @staticmethod
        def open_for_obra(*a, **kw): pass
