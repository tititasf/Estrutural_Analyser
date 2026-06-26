"""
src/ui/dialogs/generate_dxf_dialog.py — CAD-11
Dialog "Gerar DXF STOG" — async via QProcess, com log ao vivo.

Pode ser usado:
  1. A partir do DetailCard (item único pré-selecionado)
  2. A partir do DiagnosticHub (obra completa, múltiplos tipos)

Usage:
    from src.ui.dialogs.generate_dxf_dialog import GenerateDXFDialog
    dlg = GenerateDXFDialog(obra_path, parent=self, item_type='PL', item_id='P1')
    dlg.exec()
"""
import os
import sys
from pathlib import Path

try:
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
        QTextEdit, QProgressBar, QCheckBox, QGroupBox, QMessageBox,
        QFrame, QSizePolicy,
    )
    from PySide6.QtCore import Qt, QProcess, Signal
    from PySide6.QtGui import QFont, QColor
    _QT_AVAILABLE = True
except ImportError:
    _QT_AVAILABLE = False

if _QT_AVAILABLE:
    from src.core.services.dxf_generator import DXFGeneratorService, _GENERATOR_MAP
    try:
        from src.ui.theme import Colors, Accent, Semantic, Text, Border, Surface
    except ImportError:
        class Accent:
            PRIMARY = "#00d4ff"
        class Semantic:
            SUCCESS = "#4caf50"
            WARNING = "#ff9800"
            DANGER = "#f44336"
        class Text:
            PRIMARY = "#e0e0e0"
        class Border:
            DEFAULT = "#333333"
        class Surface:
            CARD = "#252525"
            DEEP = "#121212"
        class Colors:
            ACCENT_MINT        = Semantic.SUCCESS
            ACCENT_WARNING_ALT = Semantic.WARNING
            SUCCESS            = Semantic.SUCCESS
            DANGER             = Semantic.DANGER
            BG_CARD            = Surface.CARD
            TEXT_PRIMARY       = Text.PRIMARY
            BORDER_DEFAULT     = Border.DEFAULT


# ── Type labels shown in UI ───────────────────────────────────────────────────
_TYPE_LABELS = {
    'PL': 'Pilares (PL)',
    'LV': 'Vigas Laterais (LV)',
    'FV': 'Vigas de Fundo (FV)',
    'LJ': 'Lajes (LJ)',
}


if _QT_AVAILABLE:
    class GenerateDXFDialog(QDialog):
        """
        Async DXF generation dialog.

        Parameters
        ----------
        obra_path : str | Path
            Full path to the obra directory.
        parent : QWidget | None
        item_type : str | None
            Generator key ('PL', 'LV', 'FV', 'LJ'). If given, the matching
            checkbox is pre-checked and disabled (single-type mode).
        item_id : str | None
            If given, generates only this item (single-item preview mode).
        """

        generation_finished = Signal(list)  # list of Path generated

        def __init__(self, obra_path, parent=None,
                     item_type: str | None = None,
                     item_id: str | None = None):
            super().__init__(parent)
            self.obra_path = Path(obra_path)
            self.item_type = item_type   # None = obra completa
            self.item_id   = item_id     # None = todos os itens do tipo
            self._svc = DXFGeneratorService(obra_path)
            self._processes: list[QProcess] = []
            self._queue: list[str] = []      # tipos pendentes
            self._current_tipo: str | None = None
            self._generated: list[Path] = []
            self._errors: list[str] = []

            self._build_ui()
            self.setMinimumWidth(520)
            self.setMinimumHeight(400)

        # ── UI ────────────────────────────────────────────────────────────────

        def _build_ui(self):
            title_mode = (
                f"Gerar DXF — {self.item_type} {self.item_id}"
                if self.item_id else
                f"Gerar DXF — Obra: {self.obra_path.name}"
            )
            self.setWindowTitle(title_mode)

            layout = QVBoxLayout(self)
            layout.setSpacing(8)

            # Header
            lbl = QLabel(title_mode)
            lbl.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {Colors.ACCENT_MINT};")
            layout.addWidget(lbl)

            # Fase-6 path info
            out_dir = self.obra_path / 'Fase-6_Execucao_CAD'
            lbl_out = QLabel(f"Saida: {out_dir}")
            lbl_out.setStyleSheet(f"font-size: 10px; color: {Colors.TEXT_PRIMARY}; opacity: 0.7;")
            lbl_out.setWordWrap(True)
            layout.addWidget(lbl_out)

            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setStyleSheet(f"color: {Colors.BORDER_DEFAULT};")
            layout.addWidget(sep)

            # Checkboxes de tipo (desativados no modo item único)
            grp = QGroupBox("Tipos a gerar")
            grp.setStyleSheet(
                f"QGroupBox {{ font-size: 11px; font-weight: bold; "
                f"color: {Colors.ACCENT_MINT}; border: 1px solid {Colors.BORDER_DEFAULT}; "
                f"margin-top: 4px; padding-top: 8px; }}"
            )
            chk_layout = QHBoxLayout(grp)
            self._chks: dict[str, QCheckBox] = {}
            for key, label in _TYPE_LABELS.items():
                chk = QCheckBox(label)
                if self.item_type:
                    # Single-type mode: only this type checked and enabled
                    chk.setChecked(key == self.item_type)
                    chk.setEnabled(key == self.item_type)
                else:
                    chk.setChecked(True)
                self._chks[key] = chk
                chk_layout.addWidget(chk)
            layout.addWidget(grp)

            # Progress bar
            self._progress = QProgressBar()
            self._progress.setRange(0, 100)
            self._progress.setValue(0)
            self._progress.setVisible(False)
            layout.addWidget(self._progress)

            # Log area
            self._log = QTextEdit()
            self._log.setReadOnly(True)
            self._log.setMinimumHeight(160)
            self._log.setStyleSheet(
                f"background: #0d0d1a; color: {Colors.TEXT_PRIMARY}; "  # hardcoded-ok — console terminal dark navy
                f"font-family: Consolas, monospace; font-size: 10px; "
                f"border: 1px solid {Colors.BORDER_DEFAULT};"
            )
            layout.addWidget(self._log)

            # Buttons
            btn_row = QHBoxLayout()

            self._btn_generate = QPushButton("Gerar DXF")
            self._btn_generate.setObjectName("Success")
            self._btn_generate.setFixedHeight(34)
            self._btn_generate.setCursor(Qt.PointingHandCursor)
            self._btn_generate.clicked.connect(self._start_generation)

            self._btn_open = QPushButton("Abrir Pasta DXF")
            self._btn_open.setFixedHeight(34)
            self._btn_open.setCursor(Qt.PointingHandCursor)
            self._btn_open.setEnabled(False)
            self._btn_open.clicked.connect(self._open_output_folder)

            self._btn_close = QPushButton("Fechar")
            self._btn_close.setFixedHeight(34)
            self._btn_close.setCursor(Qt.PointingHandCursor)
            self._btn_close.clicked.connect(self.accept)

            btn_row.addWidget(self._btn_generate)
            btn_row.addWidget(self._btn_open)
            btn_row.addStretch()
            btn_row.addWidget(self._btn_close)
            layout.addLayout(btn_row)

        # ── Generation logic ─────────────────────────────────────────────────

        def _start_generation(self):
            tipos = [k for k, chk in self._chks.items() if chk.isChecked()]
            if not tipos:
                QMessageBox.warning(self, "Aviso", "Selecione ao menos um tipo.")
                return

            # Check Fase-4 data exists
            f4 = self.obra_path / 'Fase-4_Sincronizacao'
            if not f4.exists():
                QMessageBox.critical(
                    self, "Erro",
                    f"Fase-4_Sincronizacao nao encontrada em:\n{self.obra_path}\n\n"
                    "Execute 'Analise Geral' primeiro para gerar os JSONs."
                )
                return

            self._btn_generate.setEnabled(False)
            self._log.clear()
            self._generated = []
            self._errors = []
            self._queue = list(tipos)
            self._progress.setValue(0)
            self._progress.setVisible(True)
            self._log_line(f"Iniciando geracao de {len(tipos)} tipo(s)...\n")
            self._run_next()

        def _run_next(self):
            if not self._queue:
                self._on_all_done()
                return

            self._current_tipo = self._queue.pop(0)
            tipo = self._current_tipo

            try:
                script, args = self._svc.build_args(tipo, self.item_id)
            except ValueError as e:
                self._log_error(str(e))
                self._run_next()
                return

            if not script.exists():
                self._log_error(f"Script nao encontrado: {script}")
                self._run_next()
                return

            self._log_line(f"\n[{tipo}] Gerando... {script.name}")
            if self.item_id:
                self._log_line(f"  Item: {self.item_id}")
            self._log_line(f"  Args: {' '.join(args)}")

            proc = QProcess(self)
            proc.setProcessChannelMode(QProcess.MergedChannels)
            proc.readyReadStandardOutput.connect(
                lambda p=proc: self._on_proc_output(p)
            )
            proc.finished.connect(
                lambda code, _status, t=tipo: self._on_proc_done(code, t)
            )
            self._processes.append(proc)
            proc.start(sys.executable, [str(script)] + args)

        def _on_proc_output(self, proc: 'QProcess'):
            raw = bytes(proc.readAllStandardOutput()).decode('utf-8', 'replace')
            for line in raw.splitlines():
                self._log_line(f"  {line}")

        def _on_proc_done(self, returncode: int, tipo: str):
            out = self._svc.expected_output(tipo, self.item_id)
            if returncode == 0 and out.exists():
                self._log_line(f"[{tipo}] OK -> {out.name}")
                self._generated.append(out)
            else:
                msg = f"[{tipo}] ERRO (returncode={returncode})"
                if not out.exists():
                    msg += f" — DXF nao gerado em {out}"
                self._log_error(msg)
                self._errors.append(tipo)

            # Update progress
            total = len(self._chks)
            done = total - len(self._queue) - (1 if self._current_tipo else 0)
            self._progress.setValue(int(done / total * 100))

            self._run_next()

        def _on_all_done(self):
            self._progress.setValue(100)
            n_ok = len(self._generated)
            n_err = len(self._errors)
            summary = f"\nConcluido: {n_ok} DXF(s) gerado(s)"
            if n_err:
                summary += f", {n_err} erro(s): {', '.join(self._errors)}"
            self._log_line(summary)
            self._btn_generate.setEnabled(True)
            if n_ok > 0:
                self._btn_open.setEnabled(True)
            self.generation_finished.emit(self._generated)

        # ── Helpers ───────────────────────────────────────────────────────────

        def _log_line(self, text: str):
            self._log.append(text)

        def _log_error(self, text: str):
            self._log.append(f'<span style="color:#f44336;">{text}</span>')  # hardcoded-ok

        def _open_output_folder(self):
            out_dir = self.obra_path / 'Fase-6_Execucao_CAD'
            out_dir.mkdir(parents=True, exist_ok=True)
            if self._generated:
                # Open folder with first generated file selected
                import subprocess as sp
                sp.Popen(f'explorer /select,"{self._generated[0]}"', shell=True)
            else:
                os.startfile(str(out_dir))

        @staticmethod
        def open_for_item(obra_path, item_type: str, item_id: str, parent=None):
            """Convenience: open dialog pre-configured for a single item."""
            from src.core.services.dxf_generator import DXFGeneratorService
            key = DXFGeneratorService.key_for_item_type(item_type)
            if not key:
                QMessageBox.warning(
                    parent, "Tipo nao suportado",
                    f"Tipo '{item_type}' nao tem gerador DXF implementado."
                )
                return
            dlg = GenerateDXFDialog(
                obra_path, parent=parent, item_type=key, item_id=item_id
            )
            dlg.exec()

        @staticmethod
        def open_for_obra(obra_path, parent=None):
            """Convenience: open dialog for full obra generation (all types)."""
            dlg = GenerateDXFDialog(obra_path, parent=parent)
            dlg.exec()

else:
    # Stub for headless / no-Qt environments
    class GenerateDXFDialog:  # type: ignore[no-redef]
        def __init__(self, *a, **kw): pass
        def exec(self): pass

        @staticmethod
        def open_for_item(*a, **kw): pass

        @staticmethod
        def open_for_obra(*a, **kw): pass
