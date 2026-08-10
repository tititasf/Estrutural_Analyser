"""Painel mínimo: abrir dossiê QA (prova) sem reimplementar o motor.

A UI só apresenta; a prova permanece nos scripts/dossiês Arete.
"""
from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from src.core.qa_presentation_notice import DISCLAIMER_SHORT

try:
    from scripts.arete.qa_open_latest_dossier import (
        find_latest_evidence_dossier,
        find_latest_loop_run,
    )
except Exception:  # pragma: no cover - path/import flexibility
    find_latest_evidence_dossier = None  # type: ignore
    find_latest_loop_run = None  # type: ignore


class QaGlobalDossierPanel(QWidget):
    """Entrada UI mínima para harmonização app ↔ agente QA."""

    def __init__(self, parent=None, db=None, project_id: str | None = None):
        super().__init__(parent)
        self.db = db
        self.setObjectName("QaGlobalDossierPanel")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        title = QLabel("QA Global de Evidências — dossiê")
        title.setStyleSheet("font-weight: bold; font-size: 13px;")
        layout.addWidget(title)

        notice = QLabel(DISCLAIMER_SHORT)
        notice.setWordWrap(True)
        notice.setStyleSheet(
            "color: #f0d78c; background: #2a2110; border: 1px solid #b8860b; "
            "padding: 8px; border-radius: 4px;"
        )
        layout.addWidget(notice)

        row = QHBoxLayout()
        row.addWidget(QLabel("project_id:"))
        self.project_id = QLineEdit()
        self.project_id.setPlaceholderText("UUID do processamento (preferir a obra+pav ambíguo)")
        if project_id:
            self.project_id.setText(str(project_id))
        row.addWidget(self.project_id, 1)
        layout.addLayout(row)

        buttons = QHBoxLayout()
        self.btn_evidence = QPushButton("Abrir último dossiê review")
        self.btn_loop = QPushButton("Abrir último run de loop")
        self.btn_relatorios = QPushButton("Abrir pasta relatórios Arete")
        self.btn_evidence.clicked.connect(self._open_evidence)
        self.btn_loop.clicked.connect(self._open_loop)
        self.btn_relatorios.clicked.connect(self._open_relatorios)
        buttons.addWidget(self.btn_evidence)
        buttons.addWidget(self.btn_loop)
        buttons.addWidget(self.btn_relatorios)
        buttons.addStretch()
        layout.addLayout(buttons)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        self.status.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.status)
        layout.addStretch()

    def _pid(self) -> str | None:
        value = self.project_id.text().strip()
        return value or None

    def _open_dir(self, path: Path | None, kind: str) -> None:
        if path is None or not path.exists():
            QMessageBox.information(
                self,
                "Dossiê QA",
                f"Nenhum {kind} encontrado para o filtro atual.\n"
                "Rode review/loop via CLI ou skill qa-global-evidencias.",
            )
            self.status.setText(f"NONE ({kind})")
            return
        self.status.setText(str(path.resolve()))
        try:
            os.startfile(str(path.resolve()))  # type: ignore[attr-defined]
        except OSError as exc:
            QMessageBox.warning(self, "Dossiê QA", f"Não foi possível abrir:\n{exc}")

    def _open_evidence(self) -> None:
        if find_latest_evidence_dossier is None:
            QMessageBox.warning(self, "Dossiê QA", "Módulo qa_open_latest_dossier indisponível.")
            return
        self._open_dir(find_latest_evidence_dossier(project_id=self._pid()), "dossiê de evidência")

    def _open_loop(self) -> None:
        if find_latest_loop_run is None:
            QMessageBox.warning(self, "Dossiê QA", "Módulo qa_open_latest_dossier indisponível.")
            return
        self._open_dir(find_latest_loop_run(project_id=self._pid()), "run de loop")

    def _open_relatorios(self) -> None:
        # .../src/ui/widgets/this.py → parents[3] = repo root
        rel = Path(__file__).resolve().parents[3] / "scripts" / "arete" / "relatorios"
        self._open_dir(rel if rel.is_dir() else None, "pasta scripts/arete/relatorios")
